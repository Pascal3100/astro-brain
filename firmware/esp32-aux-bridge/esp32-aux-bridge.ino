// esp32-aux-bridge — pont WiFi (station) <-> UART single-wire pour bus Celestron AUX
//
// Le driver indi_celestron_aux parle le protocole AUX binaire à travers une
// socket TCP (mode "Celestron WiFi", port 2000). Ce pont transporte les octets
// dans les deux sens entre TCP et le bus AUX (Serial2), avec DEUX rôles actifs
// que la version transparente n'avait pas (cf. journal S29->S35) :
//
//   1. TURNAROUND HALF-DUPLEX PILOTÉ (/OE) — le bus est single-wire : on ne peut
//      pas piloter et écouter en même temps. Le buffer tri-state 74AHCT125 est
//      activé (/OE=LOW) le temps STRICT de l'émission, puis relâché en Hi-Z
//      (/OE=HIGH) pour laisser le moteur répondre. On sépare ainsi nettement TX
//      et RX au lieu de laisser le buffer piloter en permanence (blocage S35 :
//      en-tête de réponse écrasé faute de fenêtre de retournement propre).
//
//   2. SUPPRESSION D'ÉCHO half-duplex — chaque octet qu'on émet nous revient sur
//      le RX (comparateur LM2902 qui renifle DATA). On l'avale en DRAINANT
//      exactement N octets juste après l'émission (N = taille de la trame émise),
//      de façon synchrone et bornée : le driver ne voit QUE la vraie réponse.
//      (Sinon : GET_VER "écho seul", la monture semble muette — blocage S27->S31.)
//
//   3. ROBUSTESSE WiFi — reconnexion événementielle + watchdog reboot (sort de
//      l'état "zombie jusqu'au power-cycle" observé S29/S30) + fermeture des
//      sockets morts pour que le driver puisse toujours se reconnecter.
//
// Câblage (cf. docs/technical/cablage-interface-aux.html) :
//   TX — buffer tri-state 74AHCT125 @5V, drive push-pull :
//     GPIO17 -> 1A (pin 2, entrée gate)   |   GPIO32 -> /OE (pin 1, actif bas)
//     1Y (pin 3) -> 470 Ω -> DATA (RJ-12 br.4)
//   RX — comparateur LM2902 @5V (haute-Z, renifle DATA sans le charger) :
//     sortie ramenée à ~2,9 V -> GPIO16
//   GND -> br.5   |   +12V (br.3) : NE JAMAIS connecter

#include <WiFi.h>
#include "secrets.h"   // WIFI_SSID, WIFI_PASS — fichier hors repo (gitignore)

// ---- Drapeau diagnostic (cf. S33) ----
// 1 = normal : suppression d'écho half-duplex (drain de N octets après émission).
// 0 = relaie TOUT (écho + réponse) — utilisé S33/S36 pour VOIR le flux brut :
//     combien d'octets d'écho reviennent, s'il y a un octet-glitch de turnaround,
//     et si le préambule 0x3b de la réponse est présent (→ drain fautif) ou
//     absent/corrompu (→ glitch de framing au retournement TX->RX).
#define ECHO_SUPPRESS 1

// ---- Bus AUX ----
constexpr int      AUX_RX_PIN = 16;     // lit DATA via comparateur LM2902
constexpr int      AUX_TX_PIN = 17;     // attaque 1A du 74AHCT125
constexpr int      AUX_OE_PIN = 32;     // /OE du 74AHCT125 (actif bas)
constexpr uint32_t AUX_BAUD   = 19200;  // bus Celestron : 19200 8N2

// /OE est actif bas : LOW = le buffer pilote le bus (TX) ; HIGH = Hi-Z (RX).
constexpr int OE_DRIVE = LOW;
constexpr int OE_HIZ   = HIGH;

constexpr uint32_t ECHO_DRAIN_MS = 5;   // garde : au-delà, on cesse d'attendre l'écho

// ---- Réseau (station, IP fixe hors plage DHCP) ----
constexpr uint16_t TCP_PORT = 2000;     // port attendu par le mode "Celestron WiFi"
IPAddress staIP  (192, 168, 1, 200);
IPAddress staGW  (192, 168, 1, 254);
IPAddress staMask(255, 255, 255, 0);
IPAddress staDNS (192, 168, 1, 254);

// ---- Repli AP si la station échoue (jamais verrouillé / toujours joignable) ----
const char* AP_SSID = "AstroBrain-AUX";
const char* AP_PASS = "astrobrain";     // WPA2 : 8 caractères mini

// ---- Garde-temps ----
constexpr uint32_t STA_JOIN_MS         = 10000;  // délai d'attente STA au boot avant repli AP
constexpr uint32_t WIFI_DOWN_REBOOT_MS = 30000;  // STA down > 30s -> ESP.restart() (tue le zombie)
constexpr uint32_t CLIENT_IDLE_MS      = 60000;  // socket muet > 60s -> close (libère le port)

WiFiServer server(TCP_PORT);
WiFiClient client;

uint8_t  txFrame[32];         // réassemblage d'une trame AUX avant émission contiguë
uint8_t  txLen         = 0;   // octets accumulés dans txFrame
uint16_t txNeed        = 0;   // longueur totale attendue de la trame courante
uint32_t lastClientMs  = 0;   // dernière activité du client TCP
uint32_t wifiDownSince = 0;   // 0 = connecté ; sinon date du décrochage
bool     apFallback    = false;

void onWiFiEvent(WiFiEvent_t event) {
  switch (event) {
    case ARDUINO_EVENT_WIFI_STA_GOT_IP:
      Serial.printf("[wifi] STA up ip=%s\n", WiFi.localIP().toString().c_str());
      wifiDownSince = 0;
      break;
    case ARDUINO_EVENT_WIFI_STA_DISCONNECTED:
      Serial.println("[wifi] STA down -> reconnect");
      WiFi.reconnect();
      break;
    default:
      break;
  }
}

void startSTA() {
  WiFi.mode(WIFI_STA);
  WiFi.onEvent(onWiFiEvent);
  WiFi.setAutoReconnect(true);
  WiFi.setSleep(false);                          // latence : pas de modem sleep
  WiFi.config(staIP, staGW, staMask, staDNS);    // IP fixe -> pas d'aléa de bail DHCP
  WiFi.begin(WIFI_SSID, WIFI_PASS);
}

// Émission d'une trame AUX complète avec turnaround half-duplex piloté par /OE.
// On pilote le bus le temps STRICT de l'émission, on repasse en Hi-Z dès que le
// dernier octet est sorti (avant que le moteur réponde), puis on avale notre écho.
void busSend(const uint8_t* buf, uint8_t n) {
  while (Serial2.available()) Serial2.read();    // repartir d'un RX propre

  digitalWrite(AUX_OE_PIN, OE_DRIVE);            // 74AHCT125 pilote le bus (push-pull)
  Serial2.write(buf, n);
  Serial2.flush();                               // bloque jusqu'à TX terminé (shift register vidé)
  digitalWrite(AUX_OE_PIN, OE_HIZ);              // Hi-Z IMMÉDIAT : le moteur répond dès qu'il a reçu
  // PAS de garde ici : le moteur commence à répondre dès la fin du flush ; tout délai
  // supplémentaire garderait le bus piloté HIGH pendant son start-bit LOW -> collision
  // qui détruit le 1er octet de réponse (0x3b) -> en-tête perdu (diagnostic S36).

#if ECHO_SUPPRESS
  // Notre trame push-pull nous est revenue via le LM2902 : on draine exactement
  // n octets d'écho (borné dans le temps). Le moteur ne répond qu'après avoir
  // traité la trame (latence ms) -> pas de risque d'avaler la réponse.
  int      left     = n;
  uint32_t deadline = millis() + ECHO_DRAIN_MS;
  while (left > 0 && (int32_t)(millis() - deadline) < 0) {
    if (Serial2.available()) { Serial2.read(); left--; }
  }
#endif
}

void setup() {
  Serial.begin(115200);
  delay(200);

  pinMode(AUX_OE_PIN, OUTPUT);
  digitalWrite(AUX_OE_PIN, OE_HIZ);              // au repos : Hi-Z, on écoute le bus
  Serial2.begin(AUX_BAUD, SERIAL_8N2, AUX_RX_PIN, AUX_TX_PIN);

  startSTA();
  uint32_t t0 = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - t0 < STA_JOIN_MS) delay(100);

  if (WiFi.status() != WL_CONNECTED) {
    // station injoignable au boot -> repli AP pour rester accessible (debug / SSID changé)
    apFallback = true;
    WiFi.mode(WIFI_AP);
    WiFi.softAP(AP_SSID, AP_PASS);
    Serial.printf("[wifi] repli AP=%s ip=%s\n", AP_SSID, WiFi.softAPIP().toString().c_str());
  }

  server.begin();
  server.setNoDelay(true);
  Serial.printf("[bridge] tcp=%u baud=%lu 8N2 — prêt\n", TCP_PORT, (unsigned long)AUX_BAUD);
}

void loop() {
  uint32_t now = millis();

  // --- watchdog connectivité (station uniquement) : sort du zombie en rebootant ---
  if (!apFallback) {
    if (WiFi.status() == WL_CONNECTED) {
      wifiDownSince = 0;
    } else if (wifiDownSince == 0) {
      wifiDownSince = now;
    } else if (now - wifiDownSince > WIFI_DOWN_REBOOT_MS) {
      Serial.println("[wifi] down >30s -> restart");
      delay(50);
      ESP.restart();
    }
  }

  // --- accueil d'un client TCP (un seul suffit au driver) ---
  if (!client || !client.connected()) {
    WiFiClient c = server.available();
    if (c) {
      client = c;
      client.setNoDelay(true);     // trames AUX minuscules : envoi immédiat (pas de Nagle)
      lastClientMs = now;
      txLen = 0; txNeed = 0;        // nouveau dialogue -> on repart propre
      Serial.println("[tcp] client connecté");
    }
  }

  // socket zombie (Pi qui décroche) : muet trop longtemps -> on ferme pour libérer le port
  if (client && client.connected() && now - lastClientMs > CLIENT_IDLE_MS) {
    Serial.println("[tcp] client inactif -> close");
    client.stop();
  }

  // --- TCP -> bus AUX : on RÉASSEMBLE la trame AUX complète puis on l'émet via
  //     busSend() (émission contiguë + turnaround /OE + drain d'écho).
  //     La fragmentation TCP/WiFi créait des trous inter-octets -> le moteur
  //     jetait la trame (timeout), alors qu'un UART lit quand même -> écho
  //     parfait mais réponse absente (blocage tranché S33). ---
  while (client && client.available()) {
    uint8_t b = client.read();
    lastClientMs = now;
    if (txLen == 0 && b != 0x3b) continue;             // attend le préambule 0x3b
    txFrame[txLen++] = b;
    if (txLen == 2) txNeed = (uint16_t)txFrame[1] + 3; // 0x3b + len + (len octets) + cksum
    if (txLen >= 2 && txLen == txNeed) {               // trame complète -> bus
      busSend(txFrame, txLen);
      txLen = 0; txNeed = 0;
    } else if (txLen >= sizeof(txFrame)) {             // garde-fou (len corrompue)
      txLen = 0; txNeed = 0;
    }
  }

  // --- bus AUX -> TCP : après le turnaround, l'écho est déjà avalé par busSend()
  //     -> tout ce qui arrive ici est la vraie réponse moteur, on la relaie. ---
  while (Serial2.available()) {
    uint8_t b = Serial2.read();
    lastClientMs = now;
    if (client && client.connected()) client.write(b);
  }
}
