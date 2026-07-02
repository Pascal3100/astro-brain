# Hardware et câblage

Référence pratique pour le matériel et les branchements physiques.

## Composants

| Composant | Rôle | Connexion |
|---|---|---|
| **Raspberry Pi 3 B+** | Backend FastAPI, GPS, calculs astro, plate solving (Macro 5+) | — |
| **Monture Celestron NexStar SLT** | GoTo + suivi sidéral | Bus AUX (port HAND CONTROL RJ-12) via **pont ESP32 WiFi** : interface single-wire **RX comparateur LM2902 + TX buffer 74AHCT125** → ESP32 (`192.168.1.200:2000`) → driver INDI `indi_celestron_aux` en mode Network. Schémas : [cablage-interface-aux.html](cablage-interface-aux.html) + [cablage-pont-esp32.html](cablage-pont-esp32.html) |
| **GPS DroTek Ublox M8N + compass XL** | Géolocalisation, heure UTC, cap magnétique | UART0 GPIO (GPS) + I2C1 GPIO (compass LIS3MDL) |
| **ADXL345 tube** (`0x53`) | Zéro ALT + détection butées d'inclinaison | I2C1 GPIO |
| **ADXL345 monture** (`0x1D`) | Mise à niveau pré-session (bulle virtuelle) | I2C1 GPIO |
| **Caméras astrophoto** (Macro 5+) | T7C, StarShoot Autoguider, lunette guide SV165 | USB |
| **Alimentation** | 3 sources : (1) secteur 220 V → 5 V/2,5 A pour le **Pi seul** ; (2) **rail 5 V** (12 V → 5 V) pour **tout le reste du 5 V** (ESP32, interface AUX, pull-ups, VCC capteurs) ; (3) **3,3 V fourni par le Pi** (logique). Masses communes. | [cablage-alimentation.html](cablage-alimentation.html) |

La monture passe désormais par le **WiFi** (pont ESP32 sur le bus AUX), plus par l'USB → les ports USB du Pi sont réservés aux **caméras** (Macro 5+). **Tous les capteurs passent par les GPIO** ; leur **VCC vient du rail 5 V externe** (12 V → 5 V), pas des broches 5 V du Pi — seul le 3,3 V vient du Pi.

## Bus I2C1

| Device | Adresse | Usage |
|---|---|---|
| LIS3MDL (compass) | `0x1E` | Cap magnétique, alignement assisté (Macro 3+) |
| ADXL345 tube | `0x53` | Zéro ALT, butées (Macro 2+) |
| ADXL345 monture | `0x1D` | Niveau trépied (Macro 2+) |

Les 2 ADXL345 cohabitent sur le même bus grâce à la pin SDO (sélection d'adresse). Pas de multiplexeur nécessaire.

## Plan du header GPIO (Pi 3 B+, vue du dessus)

```
         3V3  (1) (2)  5V
       GPIO2  (3) (4)  5V          ← SDA1
       GPIO3  (5) (6)  GND         ← SCL1
       GPIO4  (7) (8)  GPIO14      ← TXD0
         GND  (9) (10) GPIO15      ← RXD0
```

Broches utilisées :

| Pin | BCM | Fonction | Usage |
|-----|-----|----------|-------|
| 2   | —   | 5V       | **non utilisé** (VCC capteurs ← rail 5 V externe) |
| 1   | —   | 3V3      | logique 3,3 V (référence) |
| 6   | —   | GND      | GND commun |
| 8   | GPIO14 | TXD0  | Pi TX → GPS RX |
| 10  | GPIO15 | RXD0  | Pi RX ← GPS TX |
| 3   | GPIO2  | SDA1  | I2C data (compass + ADXL345 ×2) |
| 5   | GPIO3  | SCL1  | I2C clock |

## GPS — UART0

### Câblage

| GPS | Pi header | Sens |
|---|---|---|
| VCC | **rail 5 V externe**\* | alimentation |
| GND | Pin 6 (GND) | masse commune |
| TX | Pin 10 (RXD0) | GPS → Pi |
| RX | Pin 8 (TXD0) | Pi → GPS (config) |

*\*VCC depuis le **rail 5 V** (12 V → 5 V), pas les broches 5 V du Pi. La plupart des DroTek M8N acceptent 5V (LDO intégré, logique I2C/UART en 3,3 V). Masse commune Pi ↔ rail obligatoire.*

### Config Pi OS

```bash
# 1. Désactiver le serial console, activer l'UART hardware
sudo raspi-config
  # → Interface Options → Serial Port
  #   • login shell over serial → No
  #   • serial port hardware enabled → Yes

# 2. Libérer l'UART0 matériel du Bluetooth (sinon timing instable sur mini-UART)
sudo nano /boot/firmware/config.txt
# ajouter :
#   enable_uart=1
#   dtoverlay=disable-bt

# 3. Désactiver la console série kernel (pollue les trames NMEA)
sudo nano /boot/firmware/cmdline.txt
# retirer console=serial0,115200

# 4. Désactiver le serial-getty (sinon "already opened" sur gpsd)
sudo systemctl disable --now serial-getty@ttyAMA0.service

# Note : hciuart.service n'existe plus sur Pi OS 64-bit Lite récent ;
#        dtoverlay=disable-bt suffit.

sudo reboot
```

### Config gpsd

```bash
sudo apt install gpsd gpsd-clients
sudo nano /etc/default/gpsd
# contenu :
#   START_DAEMON="true"
#   DEVICES="/dev/serial0"
#   GPSD_OPTIONS="-n"
#   USBAUTO="false"

sudo systemctl restart gpsd
```

### Vérification

```bash
dmesg | grep -i tty                  # /dev/ttyAMA0 doit être listé
cat /dev/serial0                     # NMEA brut : $GPGGA, $GPRMC… (Ctrl-C)
gpsmon                               # dashboard gpsd
cgps -s                              # vue simple lat/lon/altitude
```

LED `FTX` du module clignote ~1 Hz quand la puce émet (bon signe même sans fix). LED `PWR` doit être fixe.

## Compass LIS3MDL — I2C1

Identifié en live le 2026-04-21 sur le module DroTek "Ublox + compass Version XL" :

- Adresse : `0x1E`
- `WHO_AM_I` (0x0F) : `0x3D` (signature LIS3MDL)
- Power-down par défaut — init via `CTRL_REG1-3` avant lecture

**Câblage** (VCC + GND partagés avec le GPS) :

| Compass | Pi header |
|---|---|
| SDA | Pin 3 (SDA1) |
| SCL | Pin 5 (SCL1) |

### Config Pi OS

```bash
sudo raspi-config
  # → Interface Options → I2C → Yes

# Charger le module en persistance (sinon /dev/i2c-1 absent au boot)
echo 'i2c-dev' | sudo tee /etc/modules-load.d/i2c-dev.conf

sudo apt install i2c-tools python3-smbus
sudo reboot
```

### Vérification

```bash
sudo i2cdetect -y 1                  # LIS3MDL à 0x1E
sudo i2cget -y 1 0x1e 0x0F           # → 0x3d (WHO_AM_I LIS3MDL)

# Réveil mode continu + lecture 3 axes
sudo i2cset -y 1 0x1e 0x20 0x1C      # CTRL_REG1 : high-perf X/Y, 10 Hz
sudo i2cset -y 1 0x1e 0x23 0x0C      # CTRL_REG4 : high-perf Z
sudo i2cset -y 1 0x1e 0x22 0x00      # CTRL_REG3 : mode continu
```

## Monture — USB-série sur le bus AUX (port HAND CONTROL de la base SLT)

La **NexStar SLT** expose deux jacks **RJ-12 6P6C** sur la base — `AUX` et `HAND CONTROL` — **câblés en parallèle sur le même bus AUX interne**. On se branche sur le port **HAND CONTROL** : on n'entre **pas** dans le cerveau de la raquette, on se pose directement sur le bus, en face des contrôleurs moteur ALT/AZ. La raquette est alors **hors boucle** (débranchée) ; `indi_celestron_aux` devient maître du bus et gère lui-même alignement/GoTo.

Pour éviter un conflit UART avec le GPS (qui occupe `ttyAMA0`), on passe par un dongle USB-TTL en mode **5V**, branché sur un port USB du Pi → `/dev/ttyUSB0`. Le dongle réel est un **CH340** (`1a86:7523`, énuméré `1a86_USB_Serial`) — n'importe quel CH340/CP2102/FT232RL 5V conviendrait.

> Config driver (baud, `DEVICE_PORT`, `PORT_TYPE`) : voir [indi-reference.md](indi-reference.md). Le backend (`mount_indi_adapter.py`) ne touche **pas** la couche série — tout est délégué à `indi_celestron_aux`.

### Nature du bus AUX (≠ UART point-à-point)

- **5V TTL**, série asynchrone **19200 baud, 8N2**, tri-state au repos, multi-maître avec ligne de handshake.
- **DATA = une seule ligne bidirectionnelle (half-duplex)** : TX *et* RX partagent le même fil (broche 4). Pas de RX/TX croisés comme un UART classique.
- Conséquence : un TX *push-pull* posé direct sur DATA entre en conflit avec les réponses des moteurs → il faut une **interface single-wire**. La voie a été tranchée par une longue investigation (S26→S33) ; les essais écartés (diode 1N4007, Nano, 2× BC547, buffer Schmitt 4093) sont tracés dans le [journal](../project/journal.md) et son [archive S26→S30](../project/journal/archive/2026-06-bus-aux.md).

### Interface single-wire — montage courant (RX LM2902 + TX 74AHCT125, via pont ESP32)

Un **pont ESP32** se pose sur le bus AUX et l'expose au driver `indi_celestron_aux` en **TCP** (mode Network, `192.168.1.200:2000`) — l'ESP32 lit le bus avec un vrai GPIO haute-Z, supprime l'écho half-duplex par firmware, et gère le turnaround. L'interface analogique entre l'ESP32 et la ligne DATA combine deux composants aux rôles complémentaires :

- **RX — comparateur LM2902** (✓ prouvé S33) : lecture **haute impédance** à seuil bas (~0,9 V), insensible aux **fronts montants lents** du bus (pull-up monture faible, ~139 kΩ) qui aveuglaient un buffer logique à seuil figé. `DATA → 1M/1M → entrée+`, `Vréf 0,9 V (10k/2k2) → entrée−`, `sortie → 1k/4k7 → ~2,9 V → GPIO16`.
- **TX — buffer tri-state 74AHCT125** (✅ validé S36, round-trip 30/30 ; schéma éprouvé g7ltt/Mark Lord) : drive **actif push-pull** (HIGH *et* LOW) pendant l'émission → fronts rapides (corrige le TX round-trip négatif S33). `GPIO17 → 1A`, `GPIO32 → /OE (actif bas)`, `1Y → 470 Ω → DATA`. La ligne BUSY (broche 6) n'est pas câblée (mono-maître). **Turnaround** : `/OE` relâché immédiatement après `Serial2.flush()` (tout délai supplémentaire = collision qui détruit le 1ᵉʳ octet de réponse, cf. S36).

Tout est en logique 5 V (rail externe), masses communes. **Schémas détaillés (netlist, brochages, valeurs)** : [cablage-interface-aux.html](cablage-interface-aux.html) (étages RX/TX) + [cablage-pont-esp32.html](cablage-pont-esp32.html) (GPIO, réseau, rôles firmware).

> ⚠️ Pièges historiques à connaître : le « smoke test INDI réussi » initial était un **faux positif** (`CONNECT=On` = port ouvert + écho ; positions AZ=360/ALT=0 = défauts driver). Et le **dongle USB-TTL CH340** posé direct perturbait le bus (broche RX non haute-Z) — c'est ce qui a motivé le pivot ESP32. Détails : journal S26→S29.

### Brochage RJ-12 6P6C du port AUX/HAND CONTROL

| Broche | Couleur typique | Fonction | Côté interface |
|---|---|---|---|
| 1 | — | non utilisé | — |
| 2 | — | non utilisé | — |
| 3 | vert | **+12V** (alim raquette) | **ne JAMAIS connecter** ⚠️ |
| 4 | jaune | **DATA** (single-wire bidirectionnel) | RX (LM2902) **et** TX (74AHCT125) |
| 5 | rose/blanc | **GND** | masse commune |
| 6 | gris/noir | SELECT / BUSY (handshake bus) | non câblée (maître unique) |

⚠️ **Orientation à confirmer au multimètre avant mise sous tension.** Le n° de broche dépend du sens de vue, et un câble RJ-12 *reversed* inverse tout. Repère d'abord le **+12V (broche 3)** monture allumée → ça cale l'orientation. Un contact +12V → grille l'interface voire le port USB du Pi.

⚠️ Toute la logique d'interface est en **5 V** (rail externe ↔ bus AUX 5 V), masses communes obligatoires.

### Vérification

```bash
# Pont ESP32 alimenté (rail 5 V), sur le réseau, monture ALIMENTÉE, raquette débranchée :
nc -vz 192.168.1.200 2000                 # le port TCP du pont doit être OPEN
# Le protocole AUX est binaire (préambule 0x3b) et single-wire : NE PAS tester
# avec un echo brut (le test 'K' NexStar n'a de sens que sur le port PC de la raquette).
# Valider via la stack INDI (driver en mode Network) :
indiserver -v indi_celestron_aux          # doit énumérer le device "Celestron AUX"
# puis connexion INDI (CONNECTION_TCP=On, DEVICE_ADDRESS=192.168.1.200:2000) :
# un GET_VER vers le contrôleur AZM (0x10) doit répondre.
```

Le pont ESP32 se flashe en USB sur la workstation (`/dev/ttyUSB0`, FQBN `esp32:esp32:esp32`), pas sur le Pi. Tests réseau **depuis le Pi** (vrai client du driver).

## ADXL345 ×2 — I2C1

Câblage identique au compass (SDA/SCL partagés). Sélection d'adresse via pin SDO :

- **Tube** : SDO = VCC → adresse `0x53`
- **Monture** : SDO = GND → adresse `0x1D`

Justification du choix accéléromètres simples vs IMU 9DOF : usage statique pur, la gravité suffit (`atan2(ay, az)`). Précision < 0.5° brute, < 0.1° après calibration statique. Voir [project/decisions.md](../project/decisions.md).

## Récap fils

```
GPS  VCC  ──── rail 5 V externe   (PAS le Pi)
GPS  GND  ──── Pin 6  (GND)        (masse commune)
GPS  TX   ──── Pin 10 (RXD0)
GPS  RX   ──── Pin 8  (TXD0)
Mag  SDA  ──── Pin 3  (SDA1)       VCC ── rail 5 V
Mag  SCL  ──── Pin 5  (SCL1)
ADXL ×2   ──── Pin 3 + Pin 5 (parallèle sur I2C1)   VCC ── rail 5 V
Mount    HAND CONTROL/AUX (RJ-12) — bus AUX, via pont ESP32 WiFi :
  Pin 3 (+12V) ──── NE PAS connecter
  Pin 4 (DATA single-wire) ──┬── RX LM2902 ──► GPIO16 ┐
                             ├── TX 74AHCT125 ◄── GPIO17/GPIO32 ┤ ESP32 ─WiFi→ Pi (TCP .200:2000)
  Pin 5 (GND)  ──────────────┴── GND commun (Pi ↔ rail 5 V ↔ bus)
```

## Dépannage rapide

| Symptôme | Cause probable | Action |
|---|---|---|
| `cat /dev/serial0` rien | UART pas activé / serial console encore là | refaire `raspi-config` + reboot |
| Caractères illisibles | mini-UART instable | `dtoverlay=disable-bt` + reboot |
| `gpsmon` "NO FIX" > 10 min en intérieur | normal sous toit | tester dehors / fenêtre |
| `i2cdetect -y 1` tout `--` | I2C off ou SDA/SCL inversés | raspi-config + recâblage |
| LED `PWR` éteinte | VCC débranché ou mauvaise tension | continuité + 5V↔3V3 |
| `gpsd` "already opened by another process" | serial-getty squatte le port | `systemctl disable serial-getty@ttyAMA0` |
