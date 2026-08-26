# Hardware et câblage

Référence pratique pour le matériel et les branchements physiques.

## Composants

| Composant | Rôle | Connexion |
|---|---|---|
| **Raspberry Pi 3 B+** | Backend FastAPI, calculs astro, plate solving (Macro 5+) | — |
| **Monture Celestron NexStar SLT** | GoTo + suivi sidéral | Bus AUX (port HAND CONTROL RJ-12) via **pont ESP32 filaire** : interface single-wire **RX comparateur LM2902 + TX buffer 74AHCT125** → ESP32 → **liaison série 3 fils** (UART0 du Pi, `/dev/ttyAMA0`) → driver INDI `indi_celestron_aux` en mode Serial. Schémas : [cablage-interface-aux.html](cablage-interface-aux.html) + [cablage-pont-esp32.html](cablage-pont-esp32.html) |
| **Caméras astrophoto** (Macro 5+) | T7C, StarShoot Autoguider, lunette guide SV165 | USB |
| **Alimentation** | 3 sources : (1) secteur 220 V → 5 V/2,5 A pour le **Pi seul** ; (2) **rail 5 V** (12 V → 5 V) pour **tout le reste du 5 V** (ESP32, interface AUX, pull-ups, VCC capteurs) ; (3) **3,3 V fourni par le Pi** (logique). Masses communes. | [cablage-alimentation.html](cablage-alimentation.html) |

La monture passe par une **liaison série filaire** vers le pont ESP32 posé sur le bus AUX (plus de WiFi ni d'USB depuis le [2026-08-26](../project/decisions.md)) → les ports USB du Pi restent réservés aux **caméras** (Macro 5+). Le Pi n'embarque **plus aucun capteur** depuis le retrait du module DroTek ([ADR 2026-08-26](../project/decisions.md)) : la position vient du **site d'observation** persisté en base (réglé depuis le GPS du téléphone) et l'heure vient de **NTP**. Le 5 V des périphériques restants vient du **rail 5 V externe** (12 V → 5 V), pas des broches 5 V du Pi ; seul le 3,3 V vient du Pi.

![Raspberry Pi 3 B+ — vue d'ensemble](../introduction-to-raspberry-pi-3-b-plus-2.png)

## Plan du header GPIO (Pi 3 B+, vue du dessus)

Brochage complet du header 40 broches (référence) :

![Brochage GPIO du Raspberry Pi 3 B+](../R-Pi-3-B-Pinout.webp)

Extrait des broches du haut du header (celles qu'on utilise) :

```
         3V3  (1) (2)  5V
       GPIO2  (3) (4)  5V
       GPIO3  (5) (6)  GND
       GPIO4  (7) (8)  GPIO14      ← TXD0
         GND  (9) (10) GPIO15      ← RXD0
```

Broches utilisées :

| Pin | BCM | Fonction | Usage |
|-----|-----|----------|-------|
| 2   | —   | 5V       | **non utilisé** (VCC périphériques ← rail 5 V externe) |
| 1   | —   | 3V3      | logique 3,3 V (référence) |
| 6   | —   | GND      | GND commun |
| 8   | GPIO14 | TXD0  | UART0 TX — réservé au pont AUX filaire |
| 10  | GPIO15 | RXD0  | UART0 RX — réservé au pont AUX filaire |

## UART0 (GPIO14/15)

L'UART0 matériel du Pi n'alimente plus aucun capteur : il porte la **liaison
série vers le pont ESP32** ([ADR 2026-08-26](../project/decisions.md)). La
configuration ci-dessous — UART hardware activé, Bluetooth déplacé, console
série et getty désactivés — reste en place telle quelle : elle a été posée pour
le GPS, elle sert maintenant au pont.

### Câblage Pi ↔ pont ESP32 (3 fils)

| Pi (header 40 broches) | ESP32 | Rôle |
|---|---|---|
| **GPIO14 / TXD0** — broche **8** | **GPIO25** (RX de `Serial1`) | Pi → pont |
| **GPIO15 / RXD0** — broche **10** | **GPIO26** (TX de `Serial1`) | pont → Pi |
| **GND** — broche **6** (ou 9, 14…) | **GND** | masse commune, obligatoire |

**Croisé** (le TX d'un côté va sur le RX de l'autre) et **3,3 V des deux côtés**
→ liaison directe, aucun adaptateur de niveau. Sans masse commune les niveaux
n'ont pas de référence : ce troisième fil n'est pas optionnel.

⚠️ Ne pas alimenter l'ESP32 par l'USB de la workstation pendant qu'il est sur le
rail 5 V du banc (conflit d'alimentation) — voir « Flash » plus bas.

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

# 3. Désactiver la console série kernel (elle squatterait la ligne)
sudo nano /boot/firmware/cmdline.txt
# retirer console=serial0,115200

# 4. Désactiver le serial-getty (sinon "already opened" côté client)
sudo systemctl disable --now serial-getty@ttyAMA0.service

# Note : hciuart.service n'existe plus sur Pi OS 64-bit Lite récent ;
#        dtoverlay=disable-bt suffit.

sudo reboot
```

### Vérification

```bash
dmesg | grep -i tty                  # /dev/ttyAMA0 doit être listé
sudo lsof /dev/ttyAMA0               # vide : personne ne squatte la ligne
```

## Monture — bus AUX via pont ESP32 (port HAND CONTROL de la base SLT)

La **NexStar SLT** expose deux jacks **RJ-12 6P6C** sur la base — `AUX` et `HAND CONTROL` — **câblés en parallèle sur le même bus AUX interne**. On se branche sur le port **HAND CONTROL** : on n'entre **pas** dans le cerveau de la raquette, on se pose directement sur le bus, en face des contrôleurs moteur ALT/AZ. La raquette est alors **hors boucle** (débranchée) ; `indi_celestron_aux` devient maître du bus et gère lui-même alignement/GoTo.

Le bus AUX est un **single-wire half-duplex** (une seule ligne DATA, cf. section suivante) : un dongle USB-TTL posé direct perturbe le bus (investigation S26→S29). La liaison passe donc par un **pont ESP32** qui porte l'interface électrique (RX LM2902 / TX 74AHCT125) et relaie le bus vers le Pi sur une **liaison série 3 fils**. Le driver `indi_celestron_aux` s'y connecte en **mode Serial** sur `/dev/ttyAMA0` (19200 8N2). Pivot ESP32 acté en [ADR 2026-07-05](../project/decisions.md) ; passage du WiFi au filaire en [ADR 2026-08-26](../project/decisions.md).

> Config driver (mode Serial, `DEVICE_PORT`, `PORT_TYPE=AUX_PC`) : voir [indi-reference.md](indi-reference.md). Le backend (`mount_indi_adapter.py`) ne touche **pas** la couche liaison — tout est délégué à `indi_celestron_aux`.

### Nature du bus AUX (≠ UART point-à-point)

- **5V TTL**, série asynchrone **19200 baud, 8N2**, tri-state au repos, multi-maître avec ligne de handshake.
- **DATA = une seule ligne bidirectionnelle (half-duplex)** : TX *et* RX partagent le même fil (broche 4). Pas de RX/TX croisés comme un UART classique.
- Conséquence : un TX *push-pull* posé direct sur DATA entre en conflit avec les réponses des moteurs → il faut une **interface single-wire**. La voie a été tranchée par une longue investigation (S26→S33) ; les essais écartés (diode 1N4007, Nano, 2× BC547, buffer Schmitt 4093) sont tracés dans le [journal](../project/journal.md) et son [archive S26→S30](../project/journal/archive/2026-06-bus-aux.md).

### Interface single-wire — montage courant (RX LM2902 + TX 74AHCT125, via pont ESP32)

Un **pont ESP32** se pose sur le bus AUX et le relaie au driver `indi_celestron_aux` par une **liaison série filaire** (mode Serial, `/dev/ttyAMA0`) — l'ESP32 lit le bus avec un vrai GPIO haute-Z, supprime l'écho half-duplex par firmware, et gère le turnaround. L'interface analogique entre l'ESP32 et la ligne DATA combine deux composants aux rôles complémentaires :

- **RX — comparateur LM2902** (✓ prouvé S33) : lecture **haute impédance** à seuil bas (~0,9 V), insensible aux **fronts montants lents** du bus (pull-up monture faible, ~139 kΩ) qui aveuglaient un buffer logique à seuil figé. `DATA → 1M/1M → entrée+`, `Vréf 0,9 V (10k/2k2) → entrée−`, `sortie → 1k/4k7 → ~2,9 V → GPIO16`.
- **TX — buffer tri-state 74AHCT125** (✅ validé S36, round-trip 30/30 ; schéma éprouvé g7ltt/Mark Lord) : drive **actif push-pull** (HIGH *et* LOW) pendant l'émission → fronts rapides (corrige le TX round-trip négatif S33). `GPIO17 → 1A`, `GPIO32 → /OE (actif bas)`, `1Y → 470 Ω → DATA`. La ligne BUSY (broche 6) n'est pas câblée (mono-maître). **Turnaround** : `/OE` relâché immédiatement après `Serial2.flush()` (tout délai supplémentaire = collision qui détruit le 1ᵉʳ octet de réponse, cf. S36).

Tout est en logique 5 V (rail externe), masses communes. **Schémas détaillés (netlist, brochages, valeurs)** : [cablage-interface-aux.html](cablage-interface-aux.html) (étages RX/TX) + [cablage-pont-esp32.html](cablage-pont-esp32.html) (GPIO, liaison série vers le Pi, rôles firmware).

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

⚠️ **Un silence total ne discrimine pas** : nœud RX bloqué **haut** → UART au repos → 0 octet ; bloqué **bas** → erreurs de framing → 0 octet aussi. Il faut le voltmètre, la trace série ne suffit pas.

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
| `PI_TX` | `J3.1` (← Pi GPIO14/TXD0) · `ESP32.GPIO25` |
| `PI_RX` | `ESP32.GPIO26` · `J3.2` (→ Pi GPIO15/RXD0) |
| `+5V` | `J2.1` · `U1.4` · `U2.14` · `U2.4/10/13` · `ESP32.VIN` · `R3`(haut) · `C1+ C2+ C3+` |
| `GND` | `J2.2` · `J1.5` · `U1.11` · `U2.7` · `U2.5/9/12` · `ESP32.GND` · `J3.3` (masse Pi) · `R2 R4 R6`(bas) · `C1– C2– C3–` |

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
# Pont ESP32 alimenté (rail 5 V), câblé au Pi, monture ALIMENTÉE, raquette débranchée :
ls -l /dev/ttyAMA0                        # la ligne existe
sudo lsof /dev/ttyAMA0                    # vide : personne ne squatte le port
# Le protocole AUX est binaire (préambule 0x3b) et single-wire : NE PAS tester
# avec un echo brut (le test 'K' NexStar n'a de sens que sur le port PC de la raquette).
# Valider via la stack INDI (driver en mode Serial) :
indiserver -v indi_celestron_aux          # doit énumérer le device "Celestron AUX"
# puis connexion INDI (CONNECTION_MODE=Serial, DEVICE_PORT=/dev/ttyAMA0,
# PORT_TYPE=AUX_PC) : un GET_VER vers le contrôleur AZM (0x10) doit répondre.
```

Le pont ESP32 se flashe en USB sur la workstation (`/dev/ttyUSB0`, FQBN `esp32:esp32:esp32`), pas sur le Pi. Tests **depuis le Pi** (vrai client du driver).

#### Le contournement ARP n'a plus lieu d'être

Tant que le pont était en WiFi, le Pi n'arrivait pas à résoudre `192.168.1.200`
en ARP broadcast (entrée `INCOMPLETE`) alors que la workstation y arrivait au
même instant : il a fallu une entrée de voisinage statique, puis un hook
dispatcher NetworkManager (`/etc/NetworkManager/dispatcher.d/50-arp-esp32-bridge`)
pour la rejouer à chaque reconnexion (S53 → S54). **La liaison filaire supprime
le problème avec le réseau** : plus d'IP, plus d'ARP, plus de hook. Le fichier
dispatcher doit être retiré du Pi (il n'était pas versionné). Le détail de
l'investigation reste dans le [journal](../project/journal.md) S53/S54.

#### Test de mouvement : rate 7 minimum pour une validation à l'œil

**En dessous de `rate 7`, le déplacement n'est pas observable à l'œil nu** sur cette monture (constaté en S53). Un smoke test de mouvement dont le critère est visuel doit donc se faire en **rate 7 ou 8** (`TELESCOPE_SLEW_RATE` s'arrête à `8x`, il n'y a pas de `9x`) — sinon un « je n'ai rien vu » ne vaut pas mesure, et on risque de conclure à une panne d'émission qui n'existe pas.

Critère non visuel, préférable quand il est disponible : le **delta d'encodeur** avant/après (`TELESCOPE_ENCODER_ANGLES`), qui prouve la boucle complète commande → monture → encodeurs → Pi. Script : `~/slew_smoke.py` sur le Pi (mouvements bornés à 2 s, `stop` garanti en `finally`).

#### Sonde AUX brute — juge de paix du bus

Quand la question est « la monture répond-elle, oui ou non », court-circuiter INDI : on parle directement les trames AUX sur la ligne série. Script persistant sur le Pi : `~/aux_probe.py`.

```python
import serial, time
APP, AZM, ALT = 0x20, 0x10, 0x11
def frame(src, dst, cmd, data=b""):
    body = bytes([3 + len(data), src, dst, cmd]) + data
    return b"\x3b" + body + bytes([(-sum(body)) & 0xff])
s = serial.Serial("/dev/ttyAMA0", 19200, bytesize=8, stopbits=serial.STOPBITS_TWO,
                  timeout=3)
for dst in (AZM, ALT):
    for cmd in (0xfe, 0x05, 0x01):      # GET_VER, MC_GET_MODEL, MC_GET_POSITION
        s.write(frame(APP, dst, cmd)); time.sleep(0.05)
```

⚠️ **19200 8N2** des deux côtés, comme le bus : le driver impose ce format
(`setDefaultBaudRate(B_19200)`), et le firmware ouvre `Serial1` pareil.

**Arrêter `indiserver` d'abord** (client TCP unique, cf. plus bas). Réponses attendues avec le firmware nominal (`ECHO_SUPPRESS 1`, monture allumée, raquette débranchée) — firmware moteur 5.9 :

```
3b 05 10 20 fe 05 09 bf     # AZM version 5.9
3b 05 11 20 fe 05 09 be     # ALT version 5.9
```

Interprétation :

| Observation | Conclusion |
|---|---|
| Réponses des deux axes | bus OK **dans les deux sens** — le problème est au-dessus (driver, backend) |
| **0 octet** | chemin RX mort → passer au voltmètre (tableau des mesures plus haut), la trace série ne discriminera pas |
| Trames + écho de nos propres octets | normal si `ECHO_SUPPRESS 0` — ce mode sert justement de test RX **sans dépendre d'une réponse monture** : tout octet revenu prouve que le RX conduit |

### Flash du firmware (USB, sur la workstation)

L'OTA est parti avec le WiFi le 2026-08-26 : le pont se reflashe **en USB depuis
la workstation**. ⚠️ **Débrancher l'ESP32 du banc avant de le brancher en USB** —
sinon conflit entre le 5 V du rail et le 5 V de l'USB.

```bash
cd firmware/esp32-aux-bridge
OUT=/tmp/fw-aux
arduino-cli compile --clean --fqbn esp32:esp32:esp32 --output-dir "$OUT" .
stat -c '%y %s %n' "$OUT/esp32-aux-bridge.ino.bin"   # DATE et TAILLE : à vérifier
arduino-cli upload -p /dev/ttyUSB0 --fqbn esp32:esp32:esp32 --input-dir "$OUT" .
```

🔴 **`--output-dir` n'est pas optionnel.** Sans lui, `arduino-cli compile` écrit dans un répertoire temporaire, **pas** dans `build/` local. Un `build/esp32.esp32.esp32/*.bin` d'une compilation antérieure survit alors indéfiniment et on reflashe indéfiniment le même binaire périmé, en annonçant « Success ». En S53, trois flashs consécutifs ont ainsi rechargé un binaire de trois heures plus tôt — d'où un « bug » de firmware entièrement imaginaire, diagnostiqué puis corrigé, avant de constater qu'il n'existait pas. Réflexe : **`stat` le `.bin` après compilation**.

- Rollback vers la dernière version WiFi/OTA : tag git `firmware-wifi-final`
  (`git checkout firmware-wifi-final -- firmware/esp32-aux-bridge/`), qui suppose
  de recréer `secrets.h` à partir de l'ancien `secrets.h.example` du tag.
- **`/dev/ttyAMA0` est un port exclusif** : une sonde manuelle lancée pendant que
  `indiserver` est connecté échoue ou renvoie zéro octet — faux négatif qui a
  coûté un diagnostic entier en S51 (à l'époque sur le port TCP, même piège).
  **Arrêter `indiserver` avant toute sonde directe.**
- La liaison série ne « tombe » pas comme un socket : si le pont redémarre, le Pi
  ne le voit pas. Un silence prolongé côté driver se diagnostique au voltmètre et
  à la sonde brute, pas à l'état du lien.

## Récap fils

```
Mount    HAND CONTROL/AUX (RJ-12) — bus AUX, via pont ESP32 filaire :
  Pin 3 (+12V) ──── NE PAS connecter
  Pin 4 (DATA single-wire) ──┬── RX LM2902 ──► GPIO16 ┐         GPIO25 ◄── GPIO14/TXD0 (br. 8)
                             ├── TX 74AHCT125 ◄── GPIO17/GPIO32 ┤ ESP32   GPIO26 ──► GPIO15/RXD0 (br. 10)
  Pin 5 (GND)  ──────────────┴── GND commun (Pi ↔ rail 5 V ↔ bus) ┘        GND    ◄─► GND (br. 6)
```

## Dépannage rapide

| Symptôme | Cause probable | Action |
|---|---|---|
| `cat /dev/serial0` rien | UART pas activé / serial console encore là | refaire `raspi-config` + reboot |
| Caractères illisibles | mini-UART instable | `dtoverlay=disable-bt` + reboot |
| `/dev/ttyAMA0` "already opened by another process" | serial-getty squatte le port | `systemctl disable serial-getty@ttyAMA0` |
| Driver muet, aucun octet dans les deux sens | liaison série mal câblée (TX/RX non croisés, masse absente) | vérifier br. 8 → GPIO25, GPIO26 → br. 10, GND commun |
| Monture muette, TX OK (joystick fonctionne) | prélèvement RX non connecté | voltmètre sur `U1.3` : ≈2,2 V attendu |
| Flash « Success » mais comportement inchangé | binaire périmé rechargé | recompiler avec `--output-dir`, `stat` le `.bin` |
| Sonde brute = 0 octet alors que le driver tourne | `/dev/ttyAMA0` déjà ouvert par le driver | `systemctl stop`/kill `indiserver` avant de sonder |
