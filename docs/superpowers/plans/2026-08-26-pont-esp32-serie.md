# Pont ESP32 relié au Pi en série filaire (retrait du WiFi) — Plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Retirer le WiFi du pont ESP32 et le relier au Pi par un lien série filaire sur UART0 (GPIO14/15), 19200 8N2. Le driver `indi_celestron_aux` passe de **Network** (`192.168.1.200:2000`) à **Serial** (`/dev/ttyAMA0`), ce qui restaure la détection d'erreur perdue en TCP. Cf. ADR [2026-08-26 « Pont ESP32 relié au Pi en série filaire »](../../project/decisions.md). **À exécuter APRÈS** le plan [2026-08-26-retrait-drotek.md](2026-08-26-retrait-drotek.md), qui libère `/dev/ttyAMA0`.

**Architecture :** Le pont ESP32 fait **trois** métiers, et un seul devient obsolète :

| # | Métier | Devenir |
|---|---|---|
| 1 | Transport WiFi/TCP port 2000 | **supprimé** — remplacé par un fil |
| 2 | Retournement half-duplex `/OE` du 74AHCT125 (`drive` → `write` → `flush()` → `Hi-Z` **sans garde**) | **conservé à l'identique** |
| 3 | Suppression d'écho (drainage d'exactement N octets, borné par `ECHO_DRAIN_MS`) | **conservé à l'identique** |

Le firmware devient un **relais série ↔ série** : `Serial1` (vers le Pi, GPIO libres) ↔ `Serial2` (vers le bus AUX, IO16/IO17 + `/OE` sur IO32). Le réassemblage de trames (`0x3b`, octet `len`, `txNeed = txFrame[1] + 3`) reste dans les deux sens : le lien Pi est fiable mais reste orienté octets, et le retournement `/OE` exige toujours d'écrire une trame **entière** en une seule prise de bus.

Côté backend, l'adaptateur pousse `CONNECTION_MODE = Serial`, `DEVICE_PORT = /dev/ttyAMA0` et `PORT_TYPE = AUX_PC` **depuis le code**, ce qui rend enfin vivant `_serial_device` (aujourd'hui assigné et jamais lu) et supprime la dépendance à `~/.indi/Celestron AUX_config.xml`, fichier non versionné qui a déjà coûté du temps de debug.

**Tech Stack :** Firmware Arduino-ESP32 (`esp32-aux-bridge.ino`, flash USB depuis la workstation). Backend FastAPI / `pyindi-client`. `indiserver` + `indi_celestron_aux` v1.5 sur le Pi. Docs Markdown + schémas HTML.

## Décisions actées (baked-in, ne pas re-débattre en exécution)

1. **On garde l'ESP32, on ne le remplace pas par un Arduino Nano.** Le Nano est 5 V (le Pi n'est pas 5 V-tolérant), et surtout il n'a **qu'un seul UART matériel, partagé avec l'USB** : le second lien passerait en `SoftwareSerial`, dont le `flush()` ne garantit pas la fin d'émission au bit près. Ça détruirait le déterminisme `flush → Hi-Z` qui est exactement ce qui a été gagné en S36. La carte d'interface est déjà câblée pour l'ESP32 : le remplacer coûterait un redesign pour une régression.
2. **On ne met pas le Pi directement sur le bus AUX.** Il faudrait re-payer le retournement `/OE` depuis l'espace utilisateur contre une fenêtre de ~0,57 ms/octet, ou dépendre du RS-485 noyau (`TIOCSRS485`) dont le support sur le PL011 du Pi doit être **vérifié, pas supposé**. L'ESP32 fait déjà ce travail et le fait bien.
3. **Le lien Pi ↔ ESP32 tourne à 19200 8N2**, pas 115200. Le driver configure son port série aux paramètres du bus AUX (`serialConnection->setDefaultBaudRate(B_19200)`, `celestronaux.cpp:489`) : c'est lui qui impose la vitesse, pas nous. Le pont relaie à la même cadence des deux côtés — aucun tampon d'adaptation de débit à écrire.
4. **La séquence `/OE` et la suppression d'écho ne sont pas retouchées, pas « nettoyées », pas « améliorées ».** Elles sont recopiées telles quelles. En particulier : **aucune garde après `Serial2.flush()`** — le moteur répond dès la fin du flush (fix S36) ; et le drainage d'écho lit **exactement N octets**, borné par `ECHO_DRAIN_MS`.
5. **`enable_uart=1`, `dtoverlay=disable-bt` et le `serial-getty@ttyAMA0` désactivé sont RECYCLÉS** du GPS vers le pont AUX. Ils ont été explicitement conservés par le plan DroTek. Ne rien reconfigurer, seulement vérifier.
6. **Le mode Serial est poussé depuis le code**, pas laissé au fichier de config INDI. `~/.indi/Celestron AUX_config.xml` n'est pas versionné : s'y fier fait dépendre le comportement d'un état de machine invisible du repo. `_serial_device` existe déjà dans l'adaptateur — on le branche.
7. **La suppression du WiFi supprime aussi l'OTA.** Le flash repasse en USB depuis la workstation, **carte débranchée du bench** (conflit d'alimentation 5 V — mémoire projet). C'est un coût assumé : on flashe le pont rarement, et le gain de fiabilité en vaut la peine.
8. **Le contournement ARP et le hook dispatcher NetworkManager disparaissent** (posés en S54/S55 pour l'entrée ARP du pont). Plus d'IP, plus de problème d'ARP.
9. **La branche WiFi est archivée par un tag git, pas conservée derrière un `#ifdef`.** Un `#define WIFI_BRIDGE 0` laisserait deux chemins dont un seul serait testé. `git tag firmware-wifi-final` avant de couper suffit à revenir en arrière.

## Global Constraints

- **Ne jamais toucher** au bloc `/OE` ni au drainage d'écho autrement qu'en les déplaçant tels quels (Décision 4). Toute modification à cet endroit est une régression jusqu'à preuve du contraire sur le banc.
- **`firmware/esp32-aux-bridge/secrets.h` est gitignoré et le reste** : il est supprimé du disque, jamais commité, et `.gitignore` conserve sa ligne (le fichier peut réapparaître si on ressort le tag WiFi).
- Vitesse **19200 8N2 des deux côtés** — toute divergence donne des trames corrompues silencieuses, pas une erreur franche.
- **Masse commune obligatoire** entre le Pi et la carte du pont. À **vérifier physiquement**, pas déduire d'un « ils sont dans le même boîtier ».
- **Aucun GPIO de strapping** (0, 2, 12, 15) ni entrée seule (34-39) pour `Serial1` (cf. Task 1 étape 1).
- Tests firmware = **banc réel avec la monture alimentée**. Il n'y a pas de test unitaire de firmware ici, et prétendre le contraire serait mentir sur la couverture.
- Commits atomiques par tâche, en français, style du repo.
- Ordre **non permutable** : 1 (firmware) → 2 (câblage) → 3 (backend) → 4 (déploiement/banc) → 5 (docs).
- 🔴 **Point de non-retour** : entre la fin de Task 2 et la fin de Task 4, la monture n'est pilotable **ni** par WiFi (firmware coupé) **ni** par série (backend pas encore basculé). Prévoir la séquence en une seule séance.

---

## Task 1 : Firmware — relais série ↔ série

**Files:**
- Modify: `firmware/esp32-aux-bridge/esp32-aux-bridge.ino`
- Delete: `firmware/esp32-aux-bridge/secrets.h` (disque uniquement — jamais versionné)
- Delete: `firmware/esp32-aux-bridge/secrets.h.example` (versionné, devient sans objet)
- Modify: `firmware/esp32-aux-bridge/README.md`

**Interfaces:**
- Consumes: `Serial1` depuis le Pi (trames AUX brutes, 19200 8N2).
- Produces: `Serial2` vers le bus AUX (trames complètes, `/OE` piloté), et le retour dans l'autre sens.

- [ ] **Étape 1 : Figer le point de retour et choisir les GPIO**

```bash
git tag firmware-wifi-final
```
Le tag est le chemin de rollback (Décision 9).

GPIO occupés d'après la netlist `hardware/aux-bridge/aux-bridge.net` — **vérifié, pas supposé** : `IO16` (RX bus), `IO17` (TX_DATA), `IO32` (TX_OE), `VIN` (+5 V), `GND`.
Retenu pour `Serial1` : **RX = GPIO25** (← TX du Pi, GPIO14), **TX = GPIO26** (→ RX du Pi, GPIO15). Libres, ni strapping ni input-only, adjacents sur le connecteur.

Run: `grep -nE "IO25|IO26|GPIO25|GPIO26" hardware/aux-bridge/aux-bridge.net hardware/aux-bridge/gen_netlist.py`
Expected: **aucun hit** — si un hit apparaît, s'arrêter et rechoisir dans {27, 33}.

- [ ] **Étape 2 : Retirer tout le WiFi et l'OTA**

Supprimer : `#include <WiFi.h>`, `#include <ArduinoOTA.h>`, `#include "secrets.h"` ; les constantes `TCP_PORT`, `staIP`/`staGW`/`staDNS`, `AP_SSID`/`AP_PASS`, `OTA_HOSTNAME`/`OTA_PASS`, `STA_JOIN_MS`, `WIFI_DOWN_REBOOT_MS`, `CLIENT_IDLE_MS` ; les objets `WiFiServer server` / `WiFiClient client` ; les fonctions `onWiFiEvent()` et `startSTA()` ; le repli AP ; le bloc `ArduinoOTA.*` de `setup()` ; dans `loop()`, le watchdog de connectivité, l'acceptation de client et la fermeture sur inactivité.

`rm firmware/esp32-aux-bridge/secrets.h` (hors dépôt ; **laisser sa ligne dans `.gitignore`** — le fichier réapparaîtra si on ressort le tag WiFi) et `git rm firmware/esp32-aux-bridge/secrets.h.example`, qui n'a plus d'objet.

- [ ] **Étape 3 : Ouvrir `Serial1` vers le Pi**

Constantes en tête, dans le style des existantes :

```c
static const int  PI_RX_PIN = 25;   // <- TX du Pi (GPIO14)
static const int  PI_TX_PIN = 26;   // -> RX du Pi (GPIO15)
static const long PI_BAUD   = 19200;  // imposé par le driver INDI (B_19200)
```

Dans `setup()` : `Serial1.begin(PI_BAUD, SERIAL_8N2, PI_RX_PIN, PI_TX_PIN);` — **8N2 comme le bus**, pas 8N1.

`Serial` (USB) est conservé mais **strictement pour les traces de debug**, jamais dans le chemin de données : il partage le port de flash et une trace bavarde à 19200 décalerait le timing. Garder les `Serial.printf` existants uniquement hors des sections critiques.

- [ ] **Étape 4 : Remplacer le transport dans `loop()`**

Substitution mécanique, la logique de trame ne bouge pas :
- `client.available()` / `client.read()` → `Serial1.available()` / `Serial1.read()` ;
- `client.write(...)` → `Serial1.write(...)` ; le push borné `TCP_WRITE_MS` (fix S54 sur les écritures courtes) devient une boucle `WRITE_MS` sur `Serial1` — **la garder** : `Serial1.write` peut lui aussi écrire court quand le tampon TX est plein ;
- `if (!client) ...` → supprimé (le lien série n'a pas de notion de connexion) ;
- `RX_FRAME_MS` (péremption de trame partielle) et le réassemblage `txNeed = txFrame[1] + 3` : **inchangés**.

Le bloc suivant est recopié **octet pour octet** :

```c
digitalWrite(AUX_OE_PIN, OE_DRIVE);   // 74AHCT125 pilote le bus (push-pull)
Serial2.write(buf, n);
Serial2.flush();                      // bloque jusqu'à TX terminé
digitalWrite(AUX_OE_PIN, OE_HIZ);     // Hi-Z IMMÉDIAT
// PAS de garde ici : le moteur répond dès la fin du flush
```

Idem pour le drainage d'écho borné par `ECHO_DRAIN_MS`.

- [ ] **Étape 5 : En-tête et README**

Réécrire le commentaire d'en-tête du `.ino` : rôle (relais série ↔ bus AUX half-duplex), brochage complet des deux côtés, vitesses, et la phrase qui protège la séquence `/OE` de la prochaine « simplification ».
`firmware/esp32-aux-bridge/README.md` : retirer WiFi/OTA/IP fixe, documenter le flash USB (**carte débranchée du bench**, conflit 5 V) et le brochage vers le Pi.

- [ ] **Étape 6 : Compilation + commit**

Run: `arduino-cli compile --fqbn esp32:esp32:esp32 firmware/esp32-aux-bridge` *(ou Vérifier dans l'IDE)*
Expected: compilation OK, **zéro warning de symbole WiFi/OTA résiduel**.
Run: `grep -niE "wifi|ota|tcp|wificlient|secrets" firmware/esp32-aux-bridge/esp32-aux-bridge.ino`
Expected: **aucun hit**.

```bash
git add -A
git commit -m "feat(firmware): le pont AUX passe en relais série vers le Pi (retrait WiFi/OTA)"
```

---

## Task 2 : Câblage physique Pi ↔ pont

**Files:**
- Modify: `hardware/aux-bridge/gen_netlist.py` (schéma-as-code — **le `.net` est généré, jamais édité à la main**)
- Modify: `hardware/aux-bridge/gen_perfboard.py` (si le connecteur Pi y figure)
- Regenerate: `hardware/aux-bridge/aux-bridge.net`, `hardware/aux-bridge/perfboard_preview.html`
- Modify: `docs/technical/cablage-carte-aux-pcb.html` (source de vérité lisible citée par `gen_netlist.py`)
- Modify: `docs/technical/hardware.md` (section pont)
- Modify: `docs/technical/cablage-pont-esp32.html`, `cablage-global.html`

**Interfaces:** Pi GPIO14 (TXD0) → ESP32 GPIO25 ; ESP32 GPIO26 → Pi GPIO15 (RXD0) ; GND ↔ GND.

- [ ] **Étape 1 : Vérifier la masse commune — AVANT de brancher quoi que ce soit**

Alimentation coupée, multimètre en continuité entre une masse du Pi (broche 6, 9, 14…) et la masse de la carte du pont.
Expected: **continuité**. Si le pont est alimenté par une source distincte du Pi, **poser un fil de masse dédié** avant de connecter les lignes de données. Sans masse commune, les niveaux logiques n'ont aucun référentiel : le lien peut sembler marcher puis corrompre des trames de façon erratique.

- [ ] **Étape 2 : Vérifier les niveaux**

Pi GPIO = **3,3 V**, ESP32 = **3,3 V** → connexion directe, **aucun adaptateur de niveau, aucune résistance série**. Confirmer que le pont est bien alimenté en 5 V sur `VIN` (le régulateur embarqué produit le 3,3 V) et que **rien** de 5 V ne touche un GPIO du Pi.

- [ ] **Étape 3 : Poser les trois fils**

TX Pi (GPIO14, broche 8) → RX ESP32 (GPIO25) ; TX ESP32 (GPIO26) → RX Pi (GPIO15, broche 10) ; GND ↔ GND. **Croisement TX/RX** — c'est l'erreur classique ; relire avant de mettre sous tension.

- [ ] **Étape 4 : Mettre la netlist à jour — par le générateur, pas à la main**

⚠️ `aux-bridge.net` est **produit** par `gen_netlist.py` (schéma-as-code, en-tête `(source "gen_netlist.py")`). L'éditer directement serait écrasé au prochain run. On modifie **la description de données dans `gen_netlist.py`** : ajouter le connecteur Pi et les nets `PI_TX` (→ IO25), `PI_RX` (← IO26) et la liaison de masse Pi ↔ carte. Répercuter dans `docs/technical/cablage-carte-aux-pcb.html`, que le script désigne comme sa source de vérité lisible.

Run: `python3 hardware/aux-bridge/gen_netlist.py && python3 hardware/aux-bridge/gen_perfboard.py`
Expected: régénération sans erreur ; les trois nouveaux nets apparaissent dans `aux-bridge.net` ; aperçu perfboard cohérent avec les trois fils.

- [ ] **Étape 5 : Schémas HTML**

`cablage-pont-esp32.html` : remplacer la branche « WiFi → 192.168.1.200:2000 » par le lien série 3 fils, avec les numéros de broches. `cablage-global.html` : idem sur la vue d'ensemble.
Vérifier le rendu dans un navigateur.

- [ ] **Étape 6 : Commit**

```bash
git add -A
git commit -m "feat(hardware): liaison série filaire Pi <-> pont AUX (3 fils, masse commune)"
```

---

## Task 3 : Backend — driver INDI en mode Serial

**Files:**
- Modify: `backend/astro_brain/adapters/mount_indi_adapter.py`
- Modify: `backend/tests/test_mount_indi_adapter.py`
- Modify: `backend/deploy/astro-brain.service` (si `ASTRO_BRAIN_SERIAL_DEVICE` doit y être posé)

**Interfaces:**
- Consumes: `ASTRO_BRAIN_SERIAL_DEVICE` (défaut à corriger : `/dev/ttyAMA0`).
- Produces: propriétés INDI `CONNECTION_MODE`, `DEVICE_PORT`, `PORT_TYPE` poussées avant `connectDevice`.

- [ ] **Étape 1 : Corriger le défaut et rendre `_serial_device` vivant**

`SERIAL_DEVICE_DEFAULT` passe de `/dev/ttyUSB0` à **`/dev/ttyAMA0`** (UART0 GPIO, libéré par le plan DroTek). Aujourd'hui `self._serial_device` est **assigné et jamais lu** — un grep dépôt entier le confirme. Il devient la source du `DEVICE_PORT`.

- [ ] **Étape 2 : Pousser le mode Serial avant la connexion**

Dans la séquence de connexion, **avant** `connectDevice` et avant tout `CONNECTION` : attendre la définition des propriétés puis pousser, dans l'ordre —
1. `CONNECTION_MODE` → switch `CONNECTION_SERIAL` à `ISS_ON` (et `CONNECTION_TCP` à `ISS_OFF`) ;
2. `DEVICE_PORT` → texte `PORT` = `self._serial_device` ;
3. `PORT_TYPE` → switch `PORT_AUX_PC` (on est sur le bus AUX via le pont, **pas** sur l'USB de la raquette).

Réutiliser les helpers d'envoi de propriétés déjà présents dans l'adaptateur ; ne pas introduire un second mécanisme.

⚠️ `CONNECTION_MODE` doit être poussé **avant** `DEVICE_PORT` : le driver ne (re)définit `DEVICE_PORT` qu'une fois en mode Serial. Loguer chaque poussée en `info` — c'est ce qui manquera le jour où le pont ne répond pas.

- [ ] **Étape 3 : Mettre à jour la docstring de module**

L'en-tête décrit encore une connexion réseau vers `192.168.1.200:2000`. Le remplacer par : mode Serial, `/dev/ttyAMA0`, 19200 8N2 imposé par le driver, pont ESP32 en relais, et **la raison** du changement — en TCP, `tcpReadResponse()` renvoie **toujours `true`** (une absence de réponse passe pour un succès, ce qui a coûté une demi-session en S51), là où `serialReadResponse()` bloque avec timeout et renvoie `false`. C'est le vrai gain de la bascule.

- [ ] **Étape 4 : Tests**

`tests/test_mount_indi_adapter.py` : le fake client INDI vérifie que `CONNECTION_MODE=Serial`, `DEVICE_PORT=/dev/ttyAMA0` et `PORT_TYPE=AUX_PC` sont poussés **dans cet ordre** et **avant** `connectDevice` ; et que `ASTRO_BRAIN_SERIAL_DEVICE` surcharge bien le défaut.

- [ ] **Étape 5 : Vert + non-régression + commit**

Run: `uv run pytest -q`
Expected: PASS.
Run: `grep -rn "192.168.1.200\|ttyUSB0\|CONNECTION_TCP" astro_brain`
Expected: hits uniquement dans les commentaires historiques explicitement datés, sinon aucun.

```bash
git add -A
git commit -m "feat(backend): driver INDI en mode Serial sur /dev/ttyAMA0 (pont filaire)"
```

---

## Task 4 : Déploiement Pi + validation sur banc

**Files:**
- Modify: `backend/deploy/indiserver.service` (si une option de port y figure)
- Modify: `backend/deploy/INTEGRATION_CHECKLIST.md`

**Interfaces:** N/A (validation terrain).

- [ ] **Étape 1 : Flasher le pont**

**Débrancher la carte du bench** (conflit d'alimentation 5 V), la relier en USB à la workstation, flasher, rebrancher sur le bench. L'OTA n'existe plus.
Run: `arduino-cli upload -p /dev/ttyACM0 --fqbn esp32:esp32:esp32 firmware/esp32-aux-bridge`
Expected: upload OK.

- [ ] **Étape 2 : Vérifier que le Pi tient bien `/dev/ttyAMA0`**

Run (Pi) : `grep -E "enable_uart|disable-bt" /boot/firmware/config.txt; systemctl is-enabled serial-getty@ttyAMA0.service; sudo lsof /dev/ttyAMA0`
Expected: les deux lignes présentes, getty `disabled`/`masked`, **aucun processus** sur le port. Si un getty tourne, il mangera les octets du pont et le symptôme ressemblera à un problème de câblage.

- [ ] **Étape 3 : Boucle sèche, monture éteinte**

Depuis le Pi, envoyer une trame AUX simple et lire la réponse (petit script Python `pyserial`, 19200 8N2, ou `stty` + `cat`).
Expected: pas de réponse (la monture est éteinte) **mais aucune erreur d'ouverture de port**. Puis, en activant les traces USB du pont : constater que la trame est bien **reçue** côté ESP32. Ce test isole le lien Pi ↔ pont du bus AUX — le faire **avant** d'allumer la monture évite de débugger deux liens à la fois.

- [ ] **Étape 4 : Bout en bout, monture alimentée**

Run (Pi) : `sudo systemctl restart indiserver.service astro-brain.service && journalctl -u astro-brain -f`
Expected: connexion driver OK en mode Serial, `ENCODER_ANGLES` qui remontent, pas de timeout.
Puis, depuis l'app : joystick sur les deux axes, tracking, `GET /state` cohérent.
Expected: mouvement fluide, **et surtout** — une commande vers une monture éteinte doit maintenant produire une **vraie erreur** (timeout `serialReadResponse`), pas un faux « connecté ». C'est le critère d'acceptation qui justifie la bascule.

- [ ] **Étape 5 : Retirer le contournement ARP et le hook dispatcher**

Run (Pi) : `sudo rm -f /etc/NetworkManager/dispatcher.d/*astro*aux* && sudo systemctl reload NetworkManager` *(nom exact à confirmer par `ls`)*
Retirer aussi l'entrée ARP statique si elle a été posée en dur.
Expected: plus aucun artefact réseau lié au pont. Vérifier ensuite qu'un redémarrage complet du Pi laisse le système fonctionnel.

- [ ] **Étape 6 : Mettre à jour la checklist + commit**

`INTEGRATION_CHECKLIST.md` : remplacer les vérifications IP/TCP par les vérifications série (port libre, getty désactivé, masse commune, croisement TX/RX).

```bash
git add -A
git commit -m "chore(deploy): checklist d'intégration du pont série ; retrait du contournement ARP"
```

---

## Task 5 : Docs vivantes

**Files:**
- Modify: `CLAUDE.md`, `README.md`
- Modify: `docs/technical/hardware.md`, `architecture.md`, `deployment.md`, `indi-reference.md`
- Modify: `docs/project/roadmap.md` (Macro 1 : la puce 🚧 devient livrée), `docs/project/journal.md`

**Interfaces:** N/A.

- [ ] **Étape 1 : `hardware.md`**

Section pont AUX : retirer le mode Network, l'IP fixe `192.168.1.200:2000`, le contournement ARP, le hook dispatcher NetworkManager et la section flash OTA. Documenter le lien série 3 fils avec brochage, vitesse et la **masse commune**. Le diagramme ASCII passe de `--[WiFi/TCP]-->` à `--[série 19200 8N2]-->`. Table de dépannage : remplacer les symptômes réseau par les symptômes série (getty qui mange les octets, TX/RX inversés, masse absente, 8N1 au lieu de 8N2).

- [ ] **Étape 2 : `architecture.md`, `CLAUDE.md`, `README.md`**

Le schéma d'architecture devient `FastAPI (Pi) --[série UART0 → pont ESP32]--> bus AUX → Monture`. Dans `CLAUDE.md`, réécrire la puce **Communication Pi ↔ Monture** : mode **Serial** sur `/dev/ttyAMA0`, plus de WiFi, plus de port 2000 ; garder 19200 8N2 half-duplex single-wire côté bus.

- [ ] **Étape 3 : `deployment.md` et `indi-reference.md`**

`deployment.md` : la procédure de mise en service décrit le lien série et la vérification `lsof /dev/ttyAMA0` ; retirer les étapes WiFi du pont.
`indi-reference.md` : la section `DEVICE_PORT`/`PORT_TYPE`/`CONNECTION_MODE` devient le mode **nominal** du projet ; garder telle quelle la note sur l'asymétrie `tcpReadResponse()` toujours-vrai vs `serialReadResponse()` — c'est désormais la justification du choix, pas un avertissement.

- [ ] **Étape 4 : Roadmap et journal**

`roadmap.md` : Macro 1 — la puce 🚧 « pont relié au Pi en série » passe livrée avec sa date. `journal.md` : bullet de session (bascule effectuée, résultat du banc, ce qui a été mesuré et pas seulement supposé).

- [ ] **Étape 5 : Vérif + commit**

Run: `grep -rniE "192\.168\.1\.200|port 2000|OTA|ArduinoOTA|mode Network|dispatcher" docs CLAUDE.md README.md | grep -viE "archive|superpowers/(specs|plans)|decisions\.md|journal\.md"`
Expected: **aucune mention vivante**.

```bash
git add -A
git commit -m "docs: acter le pont ESP32 en série filaire (docs vivantes, roadmap, journal)"
```

---

## Self-Review (exécutée à la rédaction)

- **Couverture périmètre** : firmware (T1), câblage physique et schémas (T2), backend mode Serial (T3), déploiement et validation banc (T4), docs vivantes (T5). ✅
- **Les trois métiers du pont** sont explicitement triés dès l'en-tête, et les deux qui restent sont protégés par une décision actée et un rappel dans l'étape qui les touche. C'était le risque principal : « tant qu'on y est, on nettoie » aurait re-cassé le fix S36. ✅
- **Pièges couverts** : masse commune vérifiée au multimètre avant branchement (T2 étape 1) ; croisement TX/RX signalé (T2 étape 3) ; 8N2 et non 8N1 sur `Serial1` (T1 étape 3) ; 19200 imposé par le driver, pas choisi (Décision 3) ; getty qui mangerait les octets (T4 étape 2) ; `CONNECTION_MODE` **avant** `DEVICE_PORT` (T3 étape 2) ; écriture série courte, comme le fix S54 en TCP (T1 étape 4) ; fenêtre où la monture n'est pilotable par aucun des deux chemins (Global Constraints, point de non-retour) ; rollback par tag git (Décision 9). ✅
- **Dépendance au plan DroTek** : déclarée en tête et re-vérifiée en T4 étape 2. Exécuter ce plan avant l'autre laisserait `gpsd` sur `/dev/ttyAMA0` et le pont muet.
- **Honnêteté sur les tests** : il n'y a **aucun test automatisé de firmware** dans ce plan. La validation est un banc réel, décrit étape par étape. Ne pas la présenter autrement.
- **Placeholders** : aucun TODO/TBD. Les seuls éléments à confirmer sur place sont explicitement marqués comme vérifications (nom du fichier dispatcher, présence du connecteur Pi dans `gen_perfboard.py`).

## Décision ouverte (une seule)

**Alimentation du pont.** Il est aujourd'hui en 5 V sur `VIN` depuis le bench. Une fois le WiFi retiré, sa consommation chute nettement et l'alimenter depuis le rail 5 V du Pi devient envisageable — ce qui résoudrait la masse commune par construction. Ça ne bloque rien : Task 2 étape 1 traite le cas des deux alimentations séparées. À trancher sur pièce, en mesurant la conso réelle du pont après flash, pas en l'estimant.
