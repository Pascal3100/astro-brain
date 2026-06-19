// esp32-aux-bridge — pont WiFi (station) <-> UART single-wire pour bus Celestron AUX
//
// Le driver indi_celestron_aux parle le protocole AUX binaire à travers une
// socket TCP (mode "Celestron WiFi", port 2000). Ce pont transporte les octets
// dans les deux sens entre TCP et le bus AUX (Serial2), avec DEUX rôles actifs
// que la version transparente n'avait pas (cf. journal S29->S31) :
//
//   1. SUPPRESSION D'ÉCHO half-duplex — le bus est single-wire : chaque octet
//      qu'on émet via l'étage BC547 nous revient sur le RX (4093). On l'avale
//      par comptage pour ne relayer au driver QUE la vraie réponse moteur.
//      (Sinon : GET_VER "écho seul", la monture semble muette — blocage S27->S31.)
//
//   2. ROBUSTESSE WiFi — reconnexion événementielle + watchdog reboot (sort de
//      l'état "zombie jusqu'au power-cycle" observé S29/S30) + fermeture des
//      sockets morts pour que le driver puisse toujours se reconnecter.
//
// Câblage (cf. docs/technical/esp32-aux-bridge.html) :
//   GPIO17 (TX) -> étage BC547 open-collector -> DATA (RJ-12 br.4)
//   GPIO16 (RX) <- buffer HEF4093BP @5V + diviseur -> DATA
//   GND -> br.5   |   +12V (br.3) : NE JAMAIS connecter

#include <WiFi.h>
#include "secrets.h"   // WIFI_SSID, WIFI_PASS — fichier hors repo (gitignore)

// ---- Bus AUX ----
constexpr int      AUX_RX_PIN = 16;     // lit DATA via buffer 4093
constexpr int      AUX_TX_PIN = 17;     // attaque DATA via étage BC547
constexpr uint32_t AUX_BAUD   = 19200;  // bus Celestron : 19200 8N2

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
constexpr uint32_t TURNAROUND_MS       = 50;     // si l'écho ne revient pas -> on déverrouille le compteur

WiFiServer server(TCP_PORT);
WiFiClient client;

uint32_t echoPending   = 0;   // octets émis dont l'écho reste à avaler
uint32_t lastTxMs      = 0;   // dernier octet poussé sur le bus
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

void setup() {
  Serial.begin(115200);
  delay(200);

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
      echoPending  = 0;            // nouveau dialogue -> on repart propre
      Serial.println("[tcp] client connecté");
    }
  }

  // socket zombie (Pi qui décroche) : muet trop longtemps -> on ferme pour libérer le port
  if (client && client.connected() && now - lastClientMs > CLIENT_IDLE_MS) {
    Serial.println("[tcp] client inactif -> close");
    client.stop();
  }

  // --- TCP -> bus AUX (chaque octet émis devra voir son écho avalé) ---
  while (client && client.available()) {
    uint8_t b = client.read();
    Serial2.write(b);
    echoPending++;
    lastTxMs     = now;
    lastClientMs = now;
  }

  // --- bus AUX -> TCP, en avalant notre propre écho half-duplex ---
  while (Serial2.available()) {
    uint8_t b = Serial2.read();
    lastClientMs = now;
    if (echoPending > 0) {
      echoPending--;               // c'est l'écho de ce qu'on vient d'émettre -> jeté
      continue;
    }
    if (client && client.connected()) client.write(b);   // vraie réponse moteur -> driver
  }

  // --- garde-fou turnaround : si un octet d'écho s'est perdu, on ne reste pas
  //     bloqué à avaler la réponse réelle (resync passé le temps de turnaround) ---
  if (echoPending > 0 && now - lastTxMs > TURNAROUND_MS) {
    echoPending = 0;
  }
}
