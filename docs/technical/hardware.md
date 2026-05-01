# Hardware et câblage

Référence pratique pour le matériel et les branchements physiques.

## Composants

| Composant | Rôle | Connexion |
|---|---|---|
| **Raspberry Pi 3 B+** | Backend FastAPI, GPS, calculs astro, plate solving (v0.5+) | — |
| **Monture Celestron** | GoTo + suivi sidéral | USB-série via dongle CP2102 (port HC RJ12 → `/dev/ttyUSB0`, driver INDI `indi_celestron_aux`) |
| **GPS DroTek Ublox M8N + compass XL** | Géolocalisation, heure UTC, cap magnétique | UART0 GPIO (GPS) + I2C1 GPIO (compass LIS3MDL) |
| **ADXL345 tube** (`0x53`) | Zéro ALT + détection butées d'inclinaison | I2C1 GPIO |
| **ADXL345 monture** (`0x1D`) | Mise à niveau pré-session (bulle virtuelle) | I2C1 GPIO |
| **Caméras astrophoto** (v0.5+) | T7C, StarShoot Autoguider, lunette guide SV165 | USB |
| **Alimentation** | 12 V batterie → buck 5 V/3 A vers Pi | — |

Les 4 ports USB du Pi sont réservés pour la monture + caméras. **Tous les capteurs passent par les GPIO.**

## Bus I2C1

| Device | Adresse | Usage |
|---|---|---|
| LIS3MDL (compass) | `0x1E` | Cap magnétique, alignement assisté (v0.3+) |
| ADXL345 tube | `0x53` | Zéro ALT, butées (v0.4+) |
| ADXL345 monture | `0x1D` | Niveau trépied (v0.2+) |

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
| 2   | —   | 5V       | VCC GPS / capteurs |
| 1   | —   | 3V3      | VCC alternative |
| 6   | —   | GND      | GND commun |
| 8   | GPIO14 | TXD0  | Pi TX → GPS RX |
| 10  | GPIO15 | RXD0  | Pi RX ← GPS TX |
| 3   | GPIO2  | SDA1  | I2C data (compass + ADXL345 ×2) |
| 5   | GPIO3  | SCL1  | I2C clock |

## GPS — UART0

### Câblage

| GPS | Pi header | Sens |
|---|---|---|
| VCC | Pin 2 (5V)\* | alimentation |
| GND | Pin 6 (GND) | masse |
| TX | Pin 10 (RXD0) | GPS → Pi |
| RX | Pin 8 (TXD0) | Pi → GPS (config) |

*\*La plupart des DroTek M8N acceptent 5V (LDO intégré). En cas de doute, utiliser Pin 1 (3V3).*

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

## Monture — USB-série via dongle CP2102 (port HC)

Le HC Celestron parle en TTL **5V** sur connecteur RJ12 6P6C. Pour éviter un level shifter + un conflit UART avec le GPS (qui occupe `ttyAMA0`), on passe par un dongle USB-TTL CP2102 (ou FT232RL) en mode 5V, branché sur un port USB du Pi. Le HC apparaît alors en `/dev/ttyUSB0`.

### Brochage RJ12 HC Celestron → dongle CP2102

Vue clip vers le bas, broches numérotées 1→6 de gauche à droite :

| Broche RJ12 | Fonction | Côté dongle |
|---|---|---|
| 1 | N/C | — |
| 2 | N/C **ou +12V selon HC** ⚠️ | **ne pas connecter** |
| 3 | RX (HC reçoit) | TX du dongle |
| 4 | TX (HC envoie) | RX du dongle |
| 5 | GND | GND du dongle |
| 6 | N/C | — |

⚠️ **À valider au multimètre avant mise sous tension.** Certains HC NexStar+ exposent +12 V sur la broche 2 ; un contact accidentel grille le dongle voire le port USB du Pi.

⚠️ **Sélecteur du dongle sur 5V**, pas 3.3V. Un dongle qui ne sort qu'en 3.3V ne dialoguera pas correctement avec le HC.

### Vérification

```bash
# Avec dongle branché côté Pi, monture ALIMENTÉE et HC connectée au dongle :
ls -l /dev/ttyUSB0                        # doit exister, owner dialout
dmesg | grep -i cp2102                    # vu côté kernel
echo -e -n '\x4b\xa5' > /dev/ttyUSB0      # commande HC Echo (K + byte 0xA5)
                                          # (alternative : tester via INDI une fois en place)
```

L'utilisateur Pi (`pascal3100`) doit être dans le groupe `dialout` (`groups | grep dialout`, sinon `sudo usermod -aG dialout pascal3100` + re-login).

## ADXL345 ×2 — I2C1

Câblage identique au compass (SDA/SCL partagés). Sélection d'adresse via pin SDO :

- **Tube** : SDO = VCC → adresse `0x53`
- **Monture** : SDO = GND → adresse `0x1D`

Justification du choix accéléromètres simples vs IMU 9DOF : usage statique pur, la gravité suffit (`atan2(ay, az)`). Précision < 0.5° brute, < 0.1° après calibration statique. Voir [project/decisions.md](../project/decisions.md).

## Récap fils

```
GPS  VCC  ──── Pin 2  (5V)     [ou Pin 1 si 3V3]
GPS  GND  ──── Pin 6  (GND)
GPS  TX   ──── Pin 10 (RXD0)
GPS  RX   ──── Pin 8  (TXD0)
Mag  SDA  ──── Pin 3  (SDA1)
Mag  SCL  ──── Pin 5  (SCL1)
ADXL ×2   ──── Pin 3 + Pin 5 (parallèle sur I2C1)
HC RJ12   ──── dongle CP2102 (5V) ──── port USB Pi (→ /dev/ttyUSB0)
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
