# Hardware et câblage

Référence pratique pour le matériel et les branchements physiques.

## Composants

| Composant | Rôle | Connexion |
|---|---|---|
| **Raspberry Pi 3 B+** | Backend FastAPI, GPS, calculs astro, plate solving (Macro 5+) | — |
| **Monture Celestron NexStar SLT** | GoTo + suivi sidéral | Bus AUX (port HAND CONTROL RJ-12) via **pont ESP32 WiFi** : interface single-wire **RX comparateur LM2902 + TX buffer 74AHCT125** → ESP32 (`192.168.1.200:2000`) → driver INDI `indi_celestron_aux` en mode Network. Schémas : [cablage-interface-aux.html](cablage-interface-aux.html) + [cablage-pont-esp32.html](cablage-pont-esp32.html) |
| **GPS DroTek Ublox M8N + compass XL** | Géolocalisation, heure UTC, cap magnétique | UART0 GPIO (GPS) + I2C1 GPIO (compass LIS3MDL) |
| **Caméras astrophoto** (Macro 5+) | T7C, StarShoot Autoguider, lunette guide SV165 | USB |
| **Alimentation** | 3 sources : (1) secteur 220 V → 5 V/2,5 A pour le **Pi seul** ; (2) **rail 5 V** (12 V → 5 V) pour **tout le reste du 5 V** (ESP32, interface AUX, pull-ups, VCC capteurs) ; (3) **3,3 V fourni par le Pi** (logique). Masses communes. | [cablage-alimentation.html](cablage-alimentation.html) |

La monture passe désormais par le **WiFi** (pont ESP32 sur le bus AUX), plus par l'USB → les ports USB du Pi sont réservés aux **caméras** (Macro 5+). **Tous les capteurs passent par les GPIO** ; leur **VCC vient du rail 5 V externe** (12 V → 5 V), pas des broches 5 V du Pi — seul le 3,3 V vient du Pi.

![Raspberry Pi 3 B+ — vue d'ensemble](../introduction-to-raspberry-pi-3-b-plus-2.png)

## Bus I2C1

| Device | Adresse | Usage |
|---|---|---|
| LIS3MDL (compass) | `0x1E` | Cap magnétique, alignement assisté (Macro 3+) |

## Plan du header GPIO (Pi 3 B+, vue du dessus)

Brochage complet du header 40 broches (référence) :

![Brochage GPIO du Raspberry Pi 3 B+](../R-Pi-3-B-Pinout.webp)

Extrait des broches du haut du header (celles qu'on utilise) :

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
| 3   | GPIO2  | SDA1  | I2C data (compass) |
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

## Monture — bus AUX via pont ESP32 (port HAND CONTROL de la base SLT)

La **NexStar SLT** expose deux jacks **RJ-12 6P6C** sur la base — `AUX` et `HAND CONTROL` — **câblés en parallèle sur le même bus AUX interne**. On se branche sur le port **HAND CONTROL** : on n'entre **pas** dans le cerveau de la raquette, on se pose directement sur le bus, en face des contrôleurs moteur ALT/AZ. La raquette est alors **hors boucle** (débranchée) ; `indi_celestron_aux` devient maître du bus et gère lui-même alignement/GoTo.

Le bus AUX est un **single-wire half-duplex** (une seule ligne DATA, cf. section suivante) : un dongle USB-TTL posé direct perturbe le bus (investigation S26→S29). La liaison passe donc par un **pont ESP32** qui expose le bus en **TCP :2000** (WiFi) et porte l'interface électrique (RX LM2902 / TX 74AHCT125). Le driver `indi_celestron_aux` s'y connecte en **mode Network** (`192.168.1.200:2000`) — pas de `/dev/ttyUSB*`. Acté en [ADR 2026-07-05](../project/decisions.md).

> Config driver (mode Network, `DEVICE_ADDRESS`) : voir [indi-reference.md](indi-reference.md). Le backend (`mount_indi_adapter.py`) ne touche **pas** la couche liaison — tout est délégué à `indi_celestron_aux`.

### Nature du bus AUX (≠ UART point-à-point)

- **5V TTL**, série asynchrone **19200 baud, 8N2**, tri-state au repos, multi-maître avec ligne de handshake.
- **DATA = une seule ligne bidirectionnelle (half-duplex)** : TX *et* RX partagent le même fil (broche 4). Pas de RX/TX croisés comme un UART classique.
- Conséquence : un TX *push-pull* posé direct sur DATA entre en conflit avec les réponses des moteurs → il faut une **interface single-wire**. La voie a été tranchée par une longue investigation (S26→S33) ; les essais écartés (diode 1N4007, Nano, 2× BC547, buffer Schmitt 4093) sont tracés dans le [journal](../project/journal.md) et son [archive S26→S30](../project/journal/archive/2026-06-bus-aux.md).

### Interface single-wire — montage courant (RX LM2902 + TX 74AHCT125, via pont ESP32)

Un **pont ESP32** se pose sur le bus AUX et l'expose au driver `indi_celestron_aux` en **TCP** (mode Network, `192.168.1.200:2000`) — l'ESP32 lit le bus avec un vrai GPIO haute-Z, supprime l'écho half-duplex par firmware, et gère le turnaround. L'interface analogique entre l'ESP32 et la ligne DATA combine deux composants aux rôles complémentaires :

- **RX — comparateur LM2902** (✓ prouvé S33) : lecture **haute impédance** à seuil bas (~0,9 V), insensible aux **fronts montants lents** du bus (pull-up monture faible, ~139 kΩ) qui aveuglaient un buffer logique à seuil figé. `DATA → 1M/1M → entrée+`, `Vréf 0,9 V (10k/2k2) → entrée−`, `sortie → 1k/4k7 → ~2,9 V → GPIO16`.
- **TX — buffer tri-state 74AHCT125** (✅ validé S36, round-trip 30/30 ; schéma éprouvé g7ltt/Mark Lord) : drive **actif push-pull** (HIGH *et* LOW) pendant l'émission → fronts rapides (corrige le TX round-trip négatif S33). `GPIO17 → 1A`, `GPIO32 → /OE (actif bas)`, `1Y → 470 Ω → DATA`. La ligne BUSY (broche 6) n'est pas câblée (mono-maître). **Turnaround** : `/OE` relâché immédiatement après `Serial2.flush()` (tout délai supplémentaire = collision qui détruit le 1ᵉʳ octet de réponse, cf. S36).

Tout est en logique 5 V (rail externe), masses communes. **Schémas détaillés (netlist, brochages, valeurs)** : [cablage-interface-aux.html](cablage-interface-aux.html) (étages RX/TX) + [cablage-pont-esp32.html](cablage-pont-esp32.html) (GPIO, réseau, rôles firmware).

#### ⚠️ Topologie du bus DATA : un TX sain ne prouve **rien** sur le RX

Les deux étages attaquent DATA par des **straps physiquement distincts** — c'est la source du plus long faux diagnostic du projet (S51→S53). Sur la perfboard, la **rangée 11 est le bus DATA** : le 74AHCT125 s'y raccorde via son propre 470 Ω, **en aval** du point où R1 prélève la ligne pour le comparateur. Donc :

- le TX peut fonctionner parfaitement (la monture bouge au joystick) alors que **le prélèvement RX n'a jamais été connecté** ;
- « la monture ne répond pas » a été attribué pendant plusieurs sessions au driver, au turnaround, au protocole — alors que le diviseur d'entrée du LM2902 était ouvert.

Deux soudures manquaient sur la carte courante, découvertes successivement en S52 puis S53, et **aucune n'a jamais existé** (omissions de montage, pas des reprises) :

1. le strap `(23,11) → (49,11)` qui amène le bus DATA jusqu'à R1 ;
2. le strap `(20,11) → (20,7)` qui porte le **nœud du diviseur** vers `U1.3` (pin 3, IN+).

La deuxième est particulièrement traître : R1 **et** R2 mesurent bon, le nœud est électriquement correct (~2,2 V), et pourtant l'ampli ne le voit pas.

**Mesures qui discriminent, dans cet ordre** (monture allumée, carte alimentée) :

| Point | Attendu au repos | Si faux |
|---|---|---|
| DATA (RJ-12 br.4, rangée 11) | ≈ **4,4 V** (pull-up monture) | ligne morte ou en court — problème de bus, pas d'interface |
| `U1.3` (IN+) | ≈ **2,2 V** (moitié de DATA via R1/R2) | ~0,1 V → diviseur ouvert **ou** nœud non relié à pin 3 |
| `U1.2` (IN−, Vréf) | ≈ **0,9 V** | diviseur R3/R4 |
| `U1.1` (OUT) | ≈ 4,4 V (car IN+ > IN−) | 0 V = conséquence normale d'un IN+ à 0,1 V, **pas** un ampli HS |
| `ESP32.GPIO16` | haut | 0 V = break UART permanent → l'IDF jette les octets en erreur de framing, donc **0 octet relayé** |

⚠️ **Un silence total ne discrimine pas** : nœud RX bloqué **haut** → UART au repos → 0 octet ; bloqué **bas** → erreurs de framing → 0 octet aussi. Il faut le voltmètre, la trace TCP ne suffit pas.

⚠️ **Piège de calibre** sur les 1 MΩ : sur une gamme 200 kΩ, 1 MΩ affiche un dépassement qu'on lit à tort comme « rien ». Utiliser 2 MΩ ou 20 MΩ. Et en circuit, un chemin parallèle ne peut que **baisser** une lecture, jamais la monter.

**Passe de continuité complète** (hors tension) — à faire intégralement sur toute carte neuve, l'expérience S52/S53 montre qu'une omission unique se cache derrière un symptôme qui ressemble à autre chose. Netlist de référence : [`hardware/aux-bridge/README.md`](../../hardware/aux-bridge/README.md).

| Net | Doit relier |
|---|---|
| `DATA` | `J1.4` · `R1`(haut) · `R7` 470 Ω → `U2.3` |
| `IN+` | `R1`(bas) · `R2`(haut) · `U1.3` |
| `VREF` | `R3`(bas) · `R4`(haut) · `U1.2` |
| `RX` | `U1.1` → `R5` 1k → nœud · `R6` 4k7 → GND · `ESP32.GPIO16` |
| `TX_DATA` | `ESP32.GPIO17` · `U2.2` |
| `TX_OE` | `ESP32.GPIO32` · `U2.1` |
| `+5V` | `J2.1` · `U1.4` · `U2.14` · `U2.4/10/13` · `ESP32.VIN` · `R3`(haut) · `C1+ C2+ C3+` |
| `GND` | `J2.2` · `J1.5` · `U1.11` · `U2.7` · `U2.5/9/12` · `ESP32.GND` · `R2 R4 R6`(bas) · `C1– C2– C3–` |

Plus les deux contrôles **négatifs** : `DATA` ne doit toucher ni `+5V` ni `GND`, et `J1.3` (**+12 V**) doit être isolée de tout.

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

#### Prérequis réseau : entrée ARP statique côté Pi (S53)

Le Pi peut voir le pont **injoignable** (`No route to host` sur `ping` comme sur `nc`) alors que la workstation le joint parfaitement au même instant. La résolution ARP `192.168.1.200` échoue depuis le Pi (l'entrée reste `INCOMPLETE`) ; tout le reste du réseau du Pi est sain (SSH, passerelle). Contournement immédiat :

```bash
# sur le Pi — MAC du pont : 30:ae:a4:40:a8:38
sudo ip neigh replace 192.168.1.200 lladdr 30:ae:a4:40:a8:38 dev wlan0 nud permanent
ip neigh show 192.168.1.200      # doit afficher PERMANENT
ping -c3 192.168.1.200           # 0% packet loss
nc -vz 192.168.1.200 2000        # open
```

⚠️ Cette entrée est **en RAM** : elle disparaît à chaque reboot du Pi (constaté en séance). À rendre durable (unit systemd / hook NetworkManager) — cf. [`backlog.md`](../project/backlog.md).

⚠️ Ne pas confondre avec le power-save WiFi du **Pi** (S50), qui rend le Pi injoignable *depuis l'extérieur*. Ici c'est le chemin **Pi → pont** qui casse, et le côté fautif n'est pas encore tranché (broadcast ARP du Pi qui ne sort pas, ou pont qui n'y répond pas). Test discriminant à faire : `arping` unicast vers la MAC connue — s'il répond alors que le broadcast échoue, c'est le broadcast qui ne parvient pas au pont.

#### Test de mouvement : rate 7 minimum pour une validation à l'œil

**En dessous de `rate 7`, le déplacement n'est pas observable à l'œil nu** sur cette monture (constaté en S53). Un smoke test de mouvement dont le critère est visuel doit donc se faire en **rate 7 ou 8** (`TELESCOPE_SLEW_RATE` s'arrête à `8x`, il n'y a pas de `9x`) — sinon un « je n'ai rien vu » ne vaut pas mesure, et on risque de conclure à une panne d'émission qui n'existe pas.

Critère non visuel, préférable quand il est disponible : le **delta d'encodeur** avant/après (`TELESCOPE_ENCODER_ANGLES`), qui prouve la boucle complète commande → monture → encodeurs → Pi. Script : `~/slew_smoke.py` sur le Pi (mouvements bornés à 2 s, `stop` garanti en `finally`).

#### Sonde AUX brute — juge de paix du bus

Quand la question est « la monture répond-elle, oui ou non », court-circuiter INDI : on parle directement les trames AUX en TCP. Script persistant sur le Pi : `~/aux_probe.py`.

```python
import socket, time
APP, AZM, ALT = 0x20, 0x10, 0x11
def frame(src, dst, cmd, data=b""):
    body = bytes([3 + len(data), src, dst, cmd]) + data
    return b"\x3b" + body + bytes([(-sum(body)) & 0xff])
s = socket.create_connection(("192.168.1.200", 2000), timeout=3)
for dst in (AZM, ALT):
    for cmd in (0xfe, 0x05, 0x01):      # GET_VER, MC_GET_MODEL, MC_GET_POSITION
        s.sendall(frame(APP, dst, cmd)); time.sleep(0.05)
```

**Arrêter `indiserver` d'abord** (client TCP unique, cf. plus bas). Réponses attendues avec le firmware nominal (`ECHO_SUPPRESS 1`, monture allumée, raquette débranchée) — firmware moteur 5.9 :

```
3b 05 10 20 fe 05 09 bf     # AZM version 5.9
3b 05 11 20 fe 05 09 be     # ALT version 5.9
```

Interprétation :

| Observation | Conclusion |
|---|---|
| Réponses des deux axes | bus OK **dans les deux sens** — le problème est au-dessus (driver, backend) |
| **0 octet** | chemin RX mort → passer au voltmètre (tableau des mesures plus haut), la trace TCP ne discriminera pas |
| Trames + écho de nos propres octets | normal si `ECHO_SUPPRESS 0` — ce mode sert justement de test RX **sans dépendre d'une réponse monture** : tout octet revenu prouve que le RX conduit |

### Flash OTA (sans débrancher la carte)

Le firmware embarque `ArduinoOTA` depuis S37 : une fois le pont sur le WiFi, on reflashe sans le sortir du banc (le débranchement du bench est sinon nécessaire — conflit 5 V).

```bash
cd firmware/esp32-aux-bridge
OUT=/tmp/fw-aux
arduino-cli compile --clean --fqbn esp32:esp32:esp32 --output-dir "$OUT" .
ls -l "$OUT/esp32-aux-bridge.ino.bin"     # vérifier la DATE et la TAILLE
python3 ~/.arduino15/packages/esp32/hardware/esp32/3.3.10/tools/espota.py \
  -d -i 192.168.1.200 -p 3232 -a astrobrain \
  -f "$OUT/esp32-aux-bridge.ino.bin" | grep -E 'Upload size|Success|ERROR'
```

🔴 **`--output-dir` n'est pas optionnel.** Sans lui, `arduino-cli compile` écrit dans un répertoire temporaire, **pas** dans `build/` local. Un `build/esp32.esp32.esp32/*.bin` d'une compilation antérieure survit alors indéfiniment et **chaque flash OTA renvoie le même binaire périmé**, en annonçant « Success ». En S53, trois flashs consécutifs ont ainsi rechargé un binaire de trois heures plus tôt — d'où un « bug » de firmware entièrement imaginaire, diagnostiqué puis corrigé, avant de constater qu'il n'existait pas. Réflexe : **`stat` le `.bin` après compilation**, et croiser `Upload size` renvoyé par `espota` avec la taille du fichier attendu. Une taille inchangée après un `--clean` = on flashe le mauvais fichier.

- `espota.py` est bavard mais son verdict est en fin de flux : garder `-d` et grepper (`Upload size`, `Success`), sinon un `tail`/`tr` tronque justement la ligne qui compte.

- Hostname OTA `astro-brain-aux`, mot de passe `astrobrain` (`OTA_HOSTNAME`/`OTA_PASS` dans le sketch).
- **Le service OTA écoute en UDP 3232** : un `nc -z 192.168.1.200 3232` (TCP) répond toujours « refused ». Ce n'est **pas** une panne — ne pas en conclure que l'OTA est mort.
- Le pont ne sert **qu'un seul client TCP** sur le port 2000 et ne remplace le courant que s'il est déconnecté (`if (!client || !client.connected())`). Une deuxième connexion reste dans le backlog, jamais lue : toute sonde manuelle du bus lancée pendant que le driver est connecté renvoie **zéro octet** — faux négatif qui a coûté un diagnostic entier en S51. Arrêter `indiserver` avant toute sonde directe, ou passer par un proxy TCP inséré dans le chemin du driver.

## Récap fils

```
GPS  VCC  ──── rail 5 V externe   (PAS le Pi)
GPS  GND  ──── Pin 6  (GND)        (masse commune)
GPS  TX   ──── Pin 10 (RXD0)
GPS  RX   ──── Pin 8  (TXD0)
Mag  SDA  ──── Pin 3  (SDA1)       VCC ── rail 5 V
Mag  SCL  ──── Pin 5  (SCL1)
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
| `No route to host` vers `.200` **depuis le Pi seul** | résolution ARP KO | `ip neigh replace … nud permanent` (voir Vérification) |
| Monture muette, TX OK (joystick fonctionne) | prélèvement RX non connecté | voltmètre sur `U1.3` : ≈2,2 V attendu |
| Flash OTA « Success » mais comportement inchangé | binaire périmé rechargé | recompiler avec `--output-dir`, croiser `Upload size` |
| Sonde brute = 0 octet alors que le driver tourne | client TCP unique du pont | `systemctl stop`/kill `indiserver` avant de sonder |
