# Câblage GPIO — Astro-Brain

Référence pratique pour le branchement physique du GPS et du compass sur le Raspberry Pi 3 B+.

## Décision d'archi

Les 4 ports USB du Pi sont réservés pour :
- la **monture Celestron** (USB-série via adaptateur, port HC) ;
- la ou les **caméras** astrophoto (v0.5).

Le GPS DroTek Ublox M8N + compass est donc branché **via les broches GPIO** (UART0 pour le GPS, I2C1 pour le compass), pas en USB.

## Plan du header GPIO (Pi 3 B+, vue du dessus, USB en bas)

```
         3V3  (1) (2)  5V
       GPIO2  (3) (4)  5V          ← SDA1
       GPIO3  (5) (6)  GND         ← SCL1
       GPIO4  (7) (8)  GPIO14      ← TXD0
         GND  (9) (10) GPIO15      ← RXD0
      ...
```

Broches utilisées dans ce projet :

| Pin | BCM | Fonction | Usage |
|-----|-----|----------|-------|
| 2   | —   | 5V       | VCC GPS (si le module accepte 5V — voir note) |
| 1   | —   | 3V3      | VCC GPS (si le module est 3.3V) |
| 6   | —   | GND      | GND GPS |
| 8   | GPIO14 | TXD0  | Pi TX → GPS RX |
| 10  | GPIO15 | RXD0  | Pi RX ← GPS TX |
| 3   | GPIO2  | SDA1  | Compass SDA |
| 5   | GPIO3  | SCL1  | Compass SCL |

## GPS — UART0

### Câblage

| GPS (fil dupont)       | Pi header        | Sens                  |
|------------------------|------------------|-----------------------|
| VCC                    | Pin 2 (5V)*      | alimentation          |
| GND                    | Pin 6 (GND)      | masse                 |
| TX   *(GPS émet)*      | Pin 10 (RXD0)    | GPS → Pi              |
| RX   *(GPS reçoit)*    | Pin 8 (TXD0)     | Pi → GPS (config)     |

*\*Note VCC : la plupart des DroTek Ublox M8N acceptent 5V en entrée (régulateur LDO intégré). Vérifier avant de brancher en 5V. En cas de doute, utiliser Pin 1 (3V3).*

### Config Pi OS

```bash
# 1. Désactiver le serial console, activer l'UART hardware
sudo raspi-config
  # → Interface Options → Serial Port
  #   • "Would you like a login shell to be accessible over serial?" → No
  #   • "Would you like the serial port hardware to be enabled?"    → Yes

# 2. Libérer l'UART0 matériel du Bluetooth
# (sur Pi 3 B+, le BT squatte /dev/ttyAMA0 = vrai PL011 UART ;
#  sans disable-bt, /dev/serial0 pointe vers le mini-UART, timing moins précis)
sudo nano /boot/firmware/config.txt
# ajouter à la fin :
#   enable_uart=1
#   dtoverlay=disable-bt

sudo systemctl disable hciuart
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
# après reboot + câblage
dmesg | grep -i tty                  # /dev/ttyAMA0 doit être listé
cat /dev/serial0                     # NMEA brut : $GPGGA, $GPRMC…  (Ctrl-C pour sortir)
gpsmon                               # dashboard gpsd : mode, satellites, fix
cgps -s                              # vue simple : lat/lon/altitude
```

`FTX` LED du module clignote ~1 Hz quand la puce émet → bon signe même sans fix. La LED `PWR` doit être allumée fixe.

## Compass — I2C1

Le compass intégré au module "Ublox GPS + compass Version XL" (clone DroTek) est un **LIS3MDL** (ST Microelectronics, 3 axes, 16-bit, ±4/8/12/16 G). Identifié en live sur le hardware réel le 2026-04-21 :

- Adresse I2C : `0x1E` (pas `0x0D`, pas `0x1C`)
- Registre `WHO_AM_I` (0x0F) : `0x3D` (signature LIS3MDL)
- Power-down par défaut — nécessite init via `CTRL_REG1-3` avant de lire des mesures

**Utilisé à partir de v0.2** (alignement auto / pointage nord). Câbler dès maintenant pour éviter un démontage.

### Câblage

| Compass (fil dupont)   | Pi header        |
|------------------------|------------------|
| SDA                    | Pin 3 (SDA1)     |
| SCL                    | Pin 5 (SCL1)     |

*VCC et GND sont partagés avec le GPS (même module → mêmes fils).*

### Config Pi OS

```bash
sudo raspi-config
  # → Interface Options → I2C → Yes

sudo apt install i2c-tools python3-smbus
sudo reboot
```

### Vérification

```bash
# bus accessible et chip répond
sudo i2cdetect -y 1
# → LIS3MDL détecté à 0x1E (sur cette carte XL)

# signature WHO_AM_I
sudo i2cget -y 1 0x1e 0x0F
# → 0x3d (LIS3MDL confirmé)

# réveil en mode continu + lecture d'un échantillon 3 axes
sudo i2cset -y 1 0x1e 0x20 0x1C   # CTRL_REG1 : high-perf X/Y, 10 Hz
sudo i2cset -y 1 0x1e 0x23 0x0C   # CTRL_REG4 : high-perf Z
sudo i2cset -y 1 0x1e 0x22 0x00   # CTRL_REG3 : mode continu
python3 -c "
import smbus2
data = smbus2.SMBus(1).read_i2c_block_data(0x1e, 0x28, 6)
x = int.from_bytes(bytes(data[0:2]), 'little', signed=True)
y = int.from_bytes(bytes(data[2:4]), 'little', signed=True)
z = int.from_bytes(bytes(data[4:6]), 'little', signed=True)
print(f'X={x/6842:+.3f}G Y={y/6842:+.3f}G Z={z/6842:+.3f}G')
"
# → valeurs de l'ordre du champ terrestre (~0.3–0.6 G en intérieur) qui
#   varient quand le module est tourné
```

## Récap branchement complet

Fils dupont qui sortent du module DroTek → pins Pi :

```
GPS  VCC  ──────── Pin 2   (5V)     [ou Pin 1 si 3V3]
GPS  GND  ──────── Pin 6   (GND)
GPS  TX   ──────── Pin 10  (RXD0)
GPS  RX   ──────── Pin 8   (TXD0)
Mag  SDA  ──────── Pin 3   (SDA1)
Mag  SCL  ──────── Pin 5   (SCL1)
```

6 fils au total.

## Dépannage rapide

| Symptôme | Cause probable | Action |
|----------|---------------|--------|
| `cat /dev/serial0` affiche rien | UART pas activé / serial console encore là | refaire `raspi-config` + reboot |
| Caractères illisibles dans `cat /dev/serial0` | baudrate (mini-UART instable) | ajouter `dtoverlay=disable-bt` + reboot |
| `gpsmon` bloque sur "NO FIX" > 10 min en intérieur | normal, le GPS voit mal le ciel derrière un toit | tester dehors, ou au bord d'une fenêtre |
| `i2cdetect -y 1` = tout des `--` | I2C pas activé, ou câble SDA/SCL inversés | raspi-config + vérifier câblage |
| LED `PWR` éteinte | VCC débranché ou mauvaise tension | tester la continuité, basculer 5V ↔ 3V3 |
