# Firmware

Sketches embarqués du projet Astro-Brain.

## `esp32-aux-bridge/`

Pont WiFi (mode **station**) ↔ bus Celestron **AUX** single-wire. L'ESP32 se pose
sur le bus via l'interface électrique (étage TX `BC547` open-collector + buffer RX
`HEF4093BP`) et l'expose en TCP sur le port **2000**, que le driver
`indi_celestron_aux` pilote en mode « Celestron WiFi ».

Deux rôles actifs au-delà du simple relais (cf. `docs/project/journal.md`, S29→S31) :

1. **Suppression d'écho half-duplex** — par comptage : chaque octet émis voit son
   écho avalé, seule la vraie réponse moteur remonte au driver. Corrige le
   `GET_VER` « écho seul » qui bloquait le jalon C.
2. **Robustesse WiFi** — reconnexion sur événement `STA_DISCONNECTED`, **watchdog
   reboot** (`ESP.restart()` si la station est down > 30 s, pour sortir de l'état
   zombie), fermeture des sockets morts, IP fixe `192.168.1.200`, repli AP au boot.

### Configuration

```sh
cp esp32-aux-bridge/secrets.h.example esp32-aux-bridge/secrets.h
# éditer secrets.h : SSID + mot de passe du réseau du Pi
```

`secrets.h` est **gitignoré** (jamais committé).

### Build & flash (workstation Linux)

```sh
# carte = ESP32 DevKit (puce CP2102) -> /dev/ttyUSB0
arduino-cli compile --upload -p /dev/ttyUSB0 \
  --fqbn esp32:esp32:esp32 firmware/esp32-aux-bridge
```

Toolchain : `arduino-cli` + core `esp32:esp32`. Accès port via le groupe `dialout`.

### Sauvegarde de la flash avant reflash (filet de sécurité)

Pour pouvoir restaurer un firmware connu-bon en cas de régression :

```sh
esptool.py --port /dev/ttyUSB0 read_flash 0x0 0x400000 firmware/backup.bin
# restauration : esptool.py --port /dev/ttyUSB0 write_flash 0x0 firmware/backup.bin
```

Les `*.bin` sont gitignorés.
