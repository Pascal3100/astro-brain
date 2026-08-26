# Firmware

Sketches embarqués du projet Astro-Brain.

## `esp32-aux-bridge/`

Relais **série ↔ bus Celestron AUX** single-wire. L'ESP32 se pose sur le bus via
l'interface électrique (buffer TX tri-state `74AHCT125` + comparateur RX
`LM2902`) et l'expose au Pi sur un **lien série filaire 3 fils**, que le driver
`indi_celestron_aux` pilote en mode **Serial** (`/dev/ttyAMA0`, `PORT_TYPE =
AUX_PC`).

Le WiFi/TCP a été retiré le 2026-08-26 ([ADR](../docs/project/decisions.md)) : il
reliait deux cartes distantes de 10 cm en passant par la box, et son
`tcpReadResponse()` côté driver renvoyait **toujours `true`** — une absence de
réponse passait pour un succès. Le lien série restaure la détection d'erreur.
Point de retour : tag git `firmware-wifi-final`.

Deux rôles actifs au-delà du simple relais (cf. `docs/project/journal.md`, S29→S36) :

1. **Turnaround half-duplex piloté (`/OE`)** — le buffer tri-state n'est activé
   que le temps strict de l'émission, puis relâché en Hi-Z pour laisser le moteur
   répondre. **Aucune garde après `Serial2.flush()`** : le moteur répond dès la
   fin du flush.
2. **Suppression d'écho half-duplex** — par comptage : chaque octet émis voit son
   écho avalé (exactement N octets, borné par `ECHO_DRAIN_MS`), seule la vraie
   réponse moteur remonte au driver. Corrige le `GET_VER` « écho seul » qui
   bloquait le jalon C.

🔴 Ces deux séquences ne se « simplifient » pas : elles ont coûté quatre sessions
et toute retouche est une régression jusqu'à preuve du contraire sur le banc.

### Câblage vers le Pi (3 fils, masse commune obligatoire)

| Pi                       | ESP32                   | Rôle                       |
|--------------------------|-------------------------|----------------------------|
| GPIO14 / TXD0 (broche 8) | GPIO25 (RX de `Serial1`) | Pi → pont                  |
| GPIO15 / RXD0 (broche 10)| GPIO26 (TX de `Serial1`) | pont → Pi                  |
| GND (broche 6, 9, 14…)   | GND                     | référentiel des niveaux    |

**Croisement TX/RX** — c'est l'erreur classique, relire avant mise sous tension.
Les deux côtés sont en **3,3 V** : connexion directe, aucun adaptateur de niveau.
19200 8N2 des deux côtés (imposé par le driver). Détails et brochage complet :
[`docs/technical/hardware.md`](../docs/technical/hardware.md).

### Build & flash (workstation Linux, USB)

L'OTA est parti avec le WiFi : le flash repasse en USB.

🔴 **Débrancher la carte du bench avant de la relier en USB** — le 5 V du bench
et celui de l'USB entrent en conflit. Rebrancher sur le bench après le flash.

```sh
# carte = ESP32 DevKit (puce CP2102) -> /dev/ttyUSB0
arduino-cli compile --upload -p /dev/ttyUSB0 \
  --fqbn esp32:esp32:esp32 firmware/esp32-aux-bridge
```

Toolchain : `arduino-cli` + core `esp32:esp32`. Accès port via le groupe `dialout`.

Le port USB (`Serial`, 115200) reste ouvert pour les **traces de debug
uniquement** — jamais dans le chemin de données : il partage le port de flash, et
une trace bavarde décalerait le timing du bus.

### Sauvegarde de la flash avant reflash (filet de sécurité)

Pour pouvoir restaurer un firmware connu-bon en cas de régression :

```sh
esptool.py --port /dev/ttyUSB0 read_flash 0x0 0x400000 firmware/backup.bin
# restauration : esptool.py --port /dev/ttyUSB0 write_flash 0x0 firmware/backup.bin
```

Les `*.bin` sont gitignorés.
