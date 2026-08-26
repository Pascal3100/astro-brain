// esp32-aux-bridge — relais série (Pi) <-> UART single-wire du bus Celestron AUX
//
// Le driver indi_celestron_aux parle le protocole AUX binaire sur un port série
// (mode "Serial", PORT_TYPE = AUX_PC). Ce pont transporte les octets dans les
// deux sens entre le Pi (Serial1) et le bus AUX (Serial2), avec DEUX rôles
// actifs que la version transparente n'avait pas (cf. journal S29->S36) :
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
// 🔴 NE PAS "SIMPLIFIER" LA SÉQUENCE /OE NI LE DRAIN D'ÉCHO. En particulier :
//    aucune garde après Serial2.flush() (le moteur répond dès la fin du flush —
//    fix S36, obtenu en quatre sessions), et le drain lit EXACTEMENT N octets,
//    borné par ECHO_DRAIN_MS. Toute retouche ici est une régression jusqu'à
//    preuve du contraire sur le banc.
//
// Le WiFi/TCP a été retiré le 2026-08-26 (ADR « Pont ESP32 relié au Pi en série
// filaire ») : il reliait deux cartes distantes de 10 cm en passant par la box,
// et son tcpReadResponse() côté driver renvoyait TOUJOURS true — une absence de
// réponse passait pour un succès. Le lien série restaure la détection d'erreur.
// Point de retour : tag git `firmware-wifi-final`.
//
// Câblage :
//   Pi (cf. docs/technical/hardware.md) — 3 fils, masse commune OBLIGATOIRE :
//     Pi GPIO14/TXD0 (br.8)  -> GPIO25 (RX de Serial1)
//     GPIO26 (TX de Serial1) -> Pi GPIO15/RXD0 (br.10)
//     GND <-> GND   |   19200 8N2 des deux côtés
//   Bus AUX (cf. docs/technical/cablage-interface-aux.html) :
//     TX — buffer tri-state 74AHCT125 @5V, drive push-pull :
//       GPIO17 -> 1A (pin 2, entrée gate)   |   GPIO32 -> /OE (pin 1, actif bas)
//       1Y (pin 3) -> 470 Ω -> DATA (RJ-12 br.4)
//     RX — comparateur LM2902 @5V (haute-Z, renifle DATA sans le charger) :
//       sortie ramenée à ~2,9 V -> GPIO16
//     GND -> br.5   |   +12V (br.3) : NE JAMAIS connecter

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

// ---- Lien série vers le Pi (Serial1) ----
// GPIO25/26 : libres dans la netlist (hardware/aux-bridge/aux-bridge.net),
// ni broches de strapping (0, 2, 12, 15) ni entrées seules (34-39), adjacentes
// sur le connecteur. La vitesse est imposée par le driver INDI, qui configure
// son port aux paramètres du bus (setDefaultBaudRate(B_19200)) : le pont relaie
// à la même cadence des deux côtés, aucun tampon d'adaptation de débit.
constexpr int      PI_RX_PIN = 25;      // <- TX du Pi (GPIO14)
constexpr int      PI_TX_PIN = 26;      // -> RX du Pi (GPIO15)
constexpr uint32_t PI_BAUD   = 19200;   // 8N2, comme le bus

// /OE est actif bas : LOW = le buffer pilote le bus (TX) ; HIGH = Hi-Z (RX).
constexpr int OE_DRIVE = LOW;
constexpr int OE_HIZ   = HIGH;

constexpr uint32_t ECHO_DRAIN_MS = 5;   // garde : au-delà, on cesse d'attendre l'écho
constexpr uint32_t RX_FRAME_MS   = 20;  // réponse incomplète au-delà -> on abandonne la trame
constexpr uint32_t WRITE_MS      = 20;  // pousse le reste d'une écriture courte, borné

uint8_t  txFrame[32];         // réassemblage d'une trame AUX avant émission contiguë
uint8_t  txLen         = 0;   // octets accumulés dans txFrame
uint16_t txNeed        = 0;   // longueur totale attendue de la trame courante
uint8_t  rxFrame[32];         // réassemblage d'une trame de réponse avant relais vers le Pi
uint8_t  rxLen         = 0;   // octets accumulés dans rxFrame
uint16_t rxNeed        = 0;   // longueur totale attendue de la réponse courante
uint32_t rxLastByteMs  = 0;   // date du dernier octet reçu (garde RX_FRAME_MS)

// Émission d'une trame AUX complète avec turnaround half-duplex piloté par /OE.
// On pilote le bus le temps STRICT de l'émission, on repasse en Hi-Z dès que le
// dernier octet est sorti (avant que le moteur réponde), puis on avale notre écho.
void busSend(const uint8_t* buf, uint8_t n) {
  while (Serial2.available()) Serial2.read();    // repartir d'un RX propre
  rxLen = 0; rxNeed = 0;                        // la purge invalide tout réassemblage en cours

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
  Serial.begin(115200);   // USB : traces de debug UNIQUEMENT, jamais le chemin de données
  delay(200);

  pinMode(AUX_OE_PIN, OUTPUT);
  digitalWrite(AUX_OE_PIN, OE_HIZ);              // au repos : Hi-Z, on écoute le bus
  Serial2.begin(AUX_BAUD, SERIAL_8N2, AUX_RX_PIN, AUX_TX_PIN);
  Serial1.begin(PI_BAUD, SERIAL_8N2, PI_RX_PIN, PI_TX_PIN);

  Serial.printf("[bridge] série Pi rx=%d tx=%d baud=%lu 8N2 — prêt\n",
                PI_RX_PIN, PI_TX_PIN, (unsigned long)PI_BAUD);
}

void loop() {
  uint32_t now = millis();

  // --- Pi -> bus AUX : on RÉASSEMBLE la trame AUX complète puis on l'émet via
  //     busSend() (émission contiguë + turnaround /OE + drain d'écho).
  //     Le lien est fiable mais reste orienté octets, et le retournement /OE
  //     exige d'écrire une trame ENTIÈRE en une seule prise de bus : des trous
  //     inter-octets font jeter la trame par le moteur (timeout), alors qu'un
  //     UART lit quand même -> écho parfait mais réponse absente (S33). ---
  while (Serial1.available()) {
    uint8_t b = Serial1.read();
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

  // --- bus AUX -> Pi : après le turnaround, l'écho est déjà avalé par busSend()
  //     -> tout ce qui arrive ici est la vraie réponse moteur. On la
  //     RÉASSEMBLE avant de la relayer, symétriquement au sens Pi -> bus.
  //     Relayée octet par octet, une réponse de 9 octets partait autrefois en
  //     9 segments étalés sur ~5 ms (1 octet / 573 us à 19200) : le driver
  //     lisait une trame tronquée et la jetait ("Partial message recv.
  //     dropping (i=0 9/8)"), donc la position ALT restait figée sur un
  //     cache — 0/25 trames acceptées en 30 s alors que l'AZM passait à
  //     28/28 (diagnostic S54).
  //
  //     EFFET DE BORD ASSUMÉ : avant, un octet d'écho qui échappait au
  //     drain de busSend() partait brut et la chasse au 0x3b du driver
  //     le sautait. Nos trames COMMENÇANT par 0x3b, un écho qui fuit
  //     peut désormais s'assembler en trame complète et être relayé
  //     comme une fausse réponse (src=0x20, que le driver ignore). On
  //     ne filtre pas src : ça n'attraperait que la fuite propre (un
  //     écho tronqué donne un src quelconque), donc une fausse
  //     assurance. Le vrai garde-fou reste un drain d'écho correct. ---
  if (rxLen > 0 && now - rxLastByteMs > RX_FRAME_MS) {
    rxLen = 0; rxNeed = 0;         // trame qui ne se complète pas : sans ça, un
  }                                // len corrompu bloquerait le RX jusqu'au reboot

  while (Serial2.available()) {
    uint8_t b = Serial2.read();
    rxLastByteMs = now;
    if (rxLen == 0 && b != 0x3b) continue;           // attend le préambule 0x3b
    rxFrame[rxLen++] = b;
    if (rxLen == 2) rxNeed = (uint16_t)rxFrame[1] + 3;
    if (rxLen >= 2 && rxLen == rxNeed) {             // complète -> Pi en un bloc
      // Une écriture courte retronquerait la trame — le défaut même
      // qu'on corrige. Serial1.write peut écrire court quand le tampon
      // TX est plein : on pousse le reste, borné dans le temps.
      size_t   sent     = 0;
      uint32_t deadline = millis() + WRITE_MS;
      while (sent < rxLen && (int32_t)(millis() - deadline) < 0) {
        size_t n = Serial1.write(rxFrame + sent, rxLen - sent);
        if (n == 0) { delay(1); continue; }
        sent += n;
      }
      if (sent < rxLen) {
        Serial.printf("[pi] trame tronquée %u/%u\n",
                      (unsigned)sent, (unsigned)rxLen);
      }
      rxLen = 0; rxNeed = 0;
    } else if (rxLen >= sizeof(rxFrame)) {           // garde-fou (len corrompue)
      rxLen = 0; rxNeed = 0;
    }
  }
}
