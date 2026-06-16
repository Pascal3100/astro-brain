# Journal de sessions — Astro-Brain DIY

Fil rouge du projet. **Plafond : 5-6 sessions max ici** ; au-delà, on archive par milestone dans `journal/archive/`.

## État du projet

**Roadmap restructurée 2026-05-05** : abandon du versioning v0.X, passage à un train de macro-étapes (voir [`roadmap.md`](roadmap.md) + ADR du 2026-05-05). Les sessions antérieures continuent de référencer `v0.X` ; correspondance : v0.1 = Macro 0 Socle, v0.2 = Macro 2 Setup, v0.3 = Macro 3 Mise en station, v0.4 = Macro 4 Catalogue, v0.5 = Macro 5 Caméras, v0.6 = Macro 6 Focus + MES, v0.7 = Macro 7 Astrophoto. La migration INDI devient sa propre Macro 1 (technique).

**Macro 0 — Socle ✅** (livré 2026-04-25) : parité joystick + tracking via app Flutter native. Backend **89 tests** verts (64 socle + 25 migration INDI), app 53 tests. Smoke téléphone Moto g54 5G. Validation physique GPS + compass I2C + network + system ; **monture pas encore branchée** (sections 3 et 7 de `backend/deploy/INTEGRATION_CHECKLIST.md` — dongle CP2102 en attente).

**Macro 1 — Migration INDI 🚧**
- ✅ Stack INDI installée sur le Pi (Session 15) : `libindi` 2.2.0 + `indi_celestron_aux` 1.5 + `indi-gpsd` 0.6 via repo Astroberry Trixie arm64. Driver fonctionnel en test isolé (port 7624, plugins SVD + Nearest).
- ✅ Backend INDI atterri sur main (Session 16) : `MountIndiAdapter` + `AstroBrainIndiClient` + helpers + `FakeIndiClient`, `indiserver.service` systemd, script build driver patché, doc bascule. `nexstarpy` retiré du `pyproject.toml`. Patch C++ backlash mount-axis prêt (`/tmp/indi-research/indi-3rdparty/`, commit `538810c`, branche `astro-brain-backlash`).
- ⛔ **Cap suivant** : smoke test E2E sur le Pi (Task 14 du plan migration). Blocage **précisé Session 26** : ce n'est pas le dongle CP2102 en soi, mais l'**interface single-wire** manquante entre le dongle et la broche 4 (DATA) du bus AUX (le bus est half-duplex 19200 8N2 — voir `hardware.md`). Décision interface en attente (diode Schottky / 74HC125 / Nano répéteur). Une fois l'interface en place : câblage sur le port HAND CONTROL, `bash deploy/install.sh`, fork upstream du patch backlash + build sur le Pi, `INTEGRATION_CHECKLIST.md` sections 0+3+Backlash+Cordwrap. Une fois la checklist verte, ouverture du chantier Macro 2 Setup.
- 🔬 **Session 27** : interface diode 1N4007 + pull-up câblée et débuguée jusqu'au bout. **Cause racine identifiée** : la 1N4007 (silicium) laisse le niveau bas du bus à **0,97 V** (mesuré), au-dessus du seuil `VIL` des PIC moteurs (~0,8–1,0 V) → les contrôleurs ne décodent jamais nos trames (le RX du CH340, plus permissif, lit l'écho → écho OK, monture muette). Dongle/interface/software **prouvés bons** (test série brut). **Pas de Schottky/transistor dispo → décision : option (c) Nano dédoubleur open-drain** (firmware + schéma prêts, déroge à l'ADR « pas d'Arduino » → ADR à acter une fois validé). Détail ↓ Session 27.
- 🔬 **Session 28 (2026-06-11) — niveau résolu, mais le dongle perturbe le bus** : transistors récupérés (2× **BC547A**) → interface single-wire **driver open-collector 2× NPN**, niveau bas mesuré **0,05 V** (vs 0,97 V diode S27) → **cause racine S27 RÉSOLUE électriquement**, montage transistor bon. **MAIS monture toujours muette** : le 1er « smoke test réussi » était un **faux positif** (`CONNECT=On` = port ouvert + écho ; positions = défauts driver) — le `GET_VER` brut donne **écho seul** comme S27. RX **prouvé bon** (sniffer capte le trafic HC réel ; octets de slew AZM `0x24`/`0x25` capturés). **Nouveau mur isolé** : le **dongle CH340 lui-même perturbe le bus** dès le tap `RX + GND` (sans transistors) → erreur raquette « No Response » + dérive monture. Donc le blocage n'est **pas** notre montage (validé) mais le **couplage dongle ↔ bus**. Nano toujours inutile, ADR « pas d'Arduino » préservé. Détail ↓ Session 28.
- 🔬 **Session 30 (2026-06-14) — CAUSE RACINE ÉLECTRIQUE confirmée (recherche de fond) ; tentative diviseur RX en cours** : le blocage S26→S29 est **électrique, pas protocole**. Le bus single-wire surveille un **écho non-déformé** ; tout tap pas vraiment haute-Z **charge/déforme la ligne** → tue le retour (réponses moteurs) **et** fait planter la raquette (« No Response »). Mécanisme précis : un **GPIO 3,3 V (ou 74HC@3,3 V) face au bus 4,4 V** voit ses **diodes de clamp internes conduire** (plafond ~3,8 V) — une résistance série RX ne coupe pas ce chemin. Circuit de référence éprouvé (Mark Lord rtr.ca / g7ltt HBG3) : **buffer tri-state 74HCT125 @ 5,0 V**, 470 Ω série sur TX/BUSY, **ligne BUSY broche 6 jamais câblée chez nous**, suppression d'écho firmware obligatoire. Les MC **répondent sans la raquette** (archi voulue du driver ; le module SkyPortal WiFi vendu pour la SLT le prouve). **Suite 2026-06-15 : diviseur passif tranché impasse** (mesure DATA 3,42 V → pull-up monture ~139 k ; écho corrompu = fronts montants trop lents, prouvé bit-à-bit) → **pivot buffer Schmitt `HEF4093BP` @ 5 V** (en stock), page [`aux-rx-buffer-4093.html`](../technical/aux-rx-buffer-4093.html). À câbler + tester. Détail ↓ Session 30.

**Macro 2 — Setup 🚧** :
- ✅ Carte #8 RÉSEAU livrée (Session 14).
- ✅ Slice INFRA livré (Session 17, 8 commits, +29 tests) — sqlite `state.db` + repos calibration/limits.
- ✅ **Slice A capteurs livré** (Session 18, 2026-05-07) : items #1 niveau monture, #2 compass LIS3MDL, #3 zéro ALT. Fixes review v0.2 (B1, B2, I1-I7, N1-N10) + refactor I8 (`CalibrationBloc` partagé entre les 3 capteurs, -784 LOC). Tests : 178 backend + 115 frontend.
- ✅ **Slice B Courses ALT livré** (Session 19, 2026-05-07) : item #4. Backend `/limits/alt` GET/PUT + écran Flutter capture ALT_min/max via `TiltStreamService`. Tests : 183 backend + 130 frontend.
- ✅ **Slice C About livré** (Session 19, 2026-05-07) : item #9. Backend `GET /about` (versions, IP/SSID, uptime, started_at) + écran Flutter read-only avec bouton RAFRAÎCHIR. Tests : 191 backend + 133 frontend.
- ⛔ Slice D (mount tuning — backlash + cordwrap) bloqué dongle CP2102. Reste à livrer : courses AZ (software, sans hardware) — repoussé à Macro 2 mineure.

**Macro 3 — Mise en station + GoTo basique 🚧** :
- ✅ Item #1 Hub central (Session 20).
- 🚧 Item #2 Wizard alignement 3 étoiles : implémentation software complète (backend + Flutter, 22 tasks plan, Session 22). Validation matérielle bloquée dongle CP2102.
- 🚧 Item #3 GoTo réel + #5 Page Catalogue : software livré (backend + Flutter, 19 tasks plan, Session 24). Validation matérielle (slew réel) bloquée dongle CP2102.
- 🚧 Item #4 Catalogue : tranche A stars (Session 23) + enrichissement visibilité `visible_now` (Session 24). Messier/planètes à suivre.
- 🚧 Aide étoile/constellation (rattachée #2 wizard) : `ConstellationChart` au trait + navigateur par constellation + chaîne de position fix Pi → téléphone → sinon pas de wizard (fallback Paris supprimé) — software livré Session 25.

**Doc tree** : nouvelle arborescence `docs/INDEX.md` → 3 vues (`technical/`, `project/`, `product/`). Petits docs ciblés, navigation par liens. Voir Session 12.

## Session en cours

### Session 30 — Cause racine ÉLECTRIQUE prouvée (recherche de fond) ; tentative diviseur RX (2026-06-14)

Thread matériel + recherche (suite directe S29), **sur la workstation**, pont ESP32 en mode station (`192.168.1.200:2000`), Pi à `192.168.1.36`.

**Diagnostic brut (raquette débranchée, seul maître, requêtes via socket TCP directe sur l'ESP32) :** `GET_VER` (0xfe) et `GET_POSITION` (0x01), source `0x0d` ET `0x20`, AZM (0x10) + ALT (0x11) → **écho seul partout, AUCUNE réponse moteur** (confirme S27/S28/S29). **Retirer la pull-up Rpu 4,7k n'a rien changé.** Sniff du boot raquette : seulement des trames `HCP→ALT cmd 0x05` répétées (retry), **zéro réponse moteur capturée** → **la raquette tombe en « No Response » dès que notre tap est branché**. ⇒ « **on a l'aller, pas le retour** » : TX OK (la monture bouge sur slew), RX des réponses mort.

**🔬 Recherche de fond (harnais deep-research, 101 agents, 22/25 claims vérifiés) — verdict : problème ÉLECTRIQUE, pas protocole.**
- Bus AUX = **fil unique partagé half-duplex**, RX/TX hardwirés côté monture, idle tiré HIGH par pull-up monture. Chaque appareil surveille un **écho non-déformé** de son TX ; un tap pas vraiment haute-Z **charge/déforme la ligne** → casse l'écho → **retour mort + raquette « No Response »** (nos deux symptômes).
- Défaut précis = **diodes de clamp** d'un GPIO 3,3 V (ou 74HC@3,3 V) face au bus 4,4 V (plafond ~3,8 V) — **exactement ce qu'on mesure**. Une résistance série RX **ne supprime pas** le chemin de clamp.
- **Circuit de référence éprouvé** (Mark Lord rtr.ca / g7ltt HBG3, fil Cloudy Nights 743750) : **buffer tri-state 74HCT125 alimenté en 5,0 V** (pas 74HC en 3,3 V) ; drive LOW pour un 0, tri-state pour un 1 ; **470 Ω série** sur TX et BUSY ; **ligne BUSY (broche 6)** vérifiée HIGH puis tirée LOW pendant l'émission — **jamais câblée chez nous** ; firmware **supprime l'écho** (mémorise le dernier TX, jette son écho — esp32_wifi-V3.8.ino).
- **Les MC répondent sans la raquette** : archi voulue du driver (*« works directly with mount and axis controllers, without any help from the Hand Controller »*) ; le **module SkyPortal WiFi est vendu pour la SLT** → preuve que les MC répondent à une interface AUX propre sans HC. Donc notre retour mort = 100 % le tap électrique.
- Nuance clé : recevoir **seulement l'écho n'est PAS normal** (bus sain = écho PUIS réponse) → confirme le défaut électrique, pas firmware. Issue GitHub indilib #310 (même symptôme « Got no response from target ALT or AZM ») fermée **sans cause racine**, topologie différente.
- **Deux options tranchées** : (a) **DIY 74HCT125 @ 5V** (~1 €, schéma+BOM+firmware g7ltt dispo) ; (b) **module SkyPortal WiFi officiel** (~80-120 €, plug-and-play sur AUX, **même driver** en mode WiFi IP:2000, contourne tout). Rapport complet : `/tmp/.../tasks/wyxvhc2oy.output` (volatile).

**Tentative « se débrouiller avec ce qu'on a » — diviseur RX (en cours, à finir demain) :** principe = un **diviseur de tension** (≠ résistance série) maintient le GPIO **sous 3,3 V** en permanence → la diode de clamp ne conduit jamais → vrai haute-Z. Câblé `DATA →[R1=100k]→ GPIO16 →[R2]→ GND`, étage BC547 TX inchangé. **Découverte : les « 200k » étaient en fait des 133k.** Avec R1=100k / R2=133k → **nœud mesuré 2,24 V**, **sous le seuil HIGH de l'ESP32 (VIH ≈ 2,48 V)** → lecture **corrompue** (flot de `00`, préfixe constant `32 02 00 00`, pas l'écho propre). Calcul : **pull-up interne monture ≈ 64 kΩ**.

**🔜 Reprise demain (ordonnée) :**
1. **Remonter R2 à ~233–266k** (ajouter un 133k, ou un 100k, en série côté GND) → viser **nœud ~3,0 V**, **re-mesurer** au multimètre.
2. Relancer le `GET_VER` (raquette débranchée) → si **écho propre**, regarder s'il y a une **réponse moteur derrière**.
3. **Rebrancher la raquette** → test décisif : le diviseur a-t-il **arrêté de perturber** le bus (raquette OK = vraie victoire) ?
4. Si le diviseur reste marginal → ça **confirme la recherche** → trancher **74HCT125 @ 5V** (câbler aussi BUSY br.6 + 470Ω série) vs **achat module SkyPortal**.

**Ops / incidents :** **WiFi très instable ce soir** — Pi 3 B+ pingue à 1-2 s, l'ESP32 a **décroché 3× après reboot** (ARP FAILED, pas d'AP de secours visible au scan, revient après power-cycle). → fiabiliser : **réservation DHCP** (figer Pi `.36`) + antenne/canal, ou **bench de test USB sans WiFi** (firmware passthrough USB↔bus, prêt à flasher). Snippet de test brut (socket TCP `192.168.1.200:2000`, frame AUX `3b LEN SRC DST CMD CHK`, checksum `-(somme)&0xff`) utilisé toute la session, à reproduire.

**🔬 Suite S30 (2026-06-15) — diviseur RX tranché : impasse PROUVÉE, pivot buffer Schmitt HEF4093BP.** Reprise du diviseur avec **R2 remonté à 200k** (R1=100k). Le `GET_VER` revient en écho **toujours corrompu mais déterministe** (`3b 03 0d 10 fe e2` → `32 02 08 00 fc c0`, **identique sur 6 tirs**). Deux preuves chiffrées scellent le verdict :
- **Mesure `DATA chargé = 3,42 V`** → le pull-up interne monture est **~139 k** (et non 64 k estimé S30). Le nœud GPIO16 retombe donc à **2,28 V**, sous le VIH (~2,48 V) → relecture sous le seuil, malgré le 200k.
- **Décodage bit-à-bit de l'écho** : **9 bits « 1 » mangés, tous précédés d'un « 0 » (front montant)** ; les 13 bits « 1 » en régime établi gardés ; zéro « 0→1 ». Signature **textbook d'un front montant trop lent** : la ligne haute-impédance chargée par un pull-up faible ne franchit pas le seuil en un temps bit (52 µs @ 19200). **Monter R2 corrige le niveau mais aggrave l'impédance source** (73-82 k) → fronts encore plus lents. **Le diviseur passif est un cul-de-sac**, pas un réglage à affiner → confirme l'étape 4 pré-actée S30.
- **Décision (stock utilisateur : LM2902, MAX232, HEF4093BP, BC547/557/548, PIC16F876) → `HEF4093BP`** (quad NAND Schmitt CMOS, DIP14). Alimenté en **5 V** : entrée haute-Z lit le bus 4,4 V sans le charger (plus de droop, plus de perturbation raquette) ; **2 portes en inverseur = buffer non-inverseur** (polarité UART préservée) ; sortie 0/5 V ramenée à **3,33 V** par les **100k/200k recyclés** — mais désormais attaqués par une **sortie CMOS raide** → fronts rapides. L'hystérésis est un bonus net vs un 74HCT125 nu. Écartés : LM2902 (comparateur lent, slew 0,5 V/µs marginal, sans hystérésis), MAX232 (RS-232 ±, hors sujet), PIC16F876 (MCU → programmateur + firmware, redondant avec l'ESP32), 2N7000 (pas en stock ; sortie inversée).
- **Page de câblage autonome créée** : [`../technical/aux-rx-buffer-4093.html`](../technical/aux-rx-buffer-4093.html) (schéma DIP14 + netlist + chiffres de validation + procédure + jour/nuit).

**Vigilance (retour utilisateur, intégrée à la page) :** (a) **condensateur de découplage 100 nF céramique** entre pin 14 (VDD) et pin 7 (VSS) du 4093, **au plus près du boîtier** (pics de commutation CMOS) ; (b) **écho local half-duplex** promu en contrainte de fond — l'étage RX écoutant en permanence, chaque TX via le BC547 revient en octets fantômes sur GPIO16 → le firmware ESP32 **doit** les purger/rejeter (+ respecter le turnaround), sinon le dialogue driver reste pollué (cause du `GET_VER` écho-seul S27→S30).

**🔜 Reprise prochaine session (ordonnée) :** (1) câbler le 4093 (alim 5 V, **découplage 100 nF VDD/VSS**, GND commun, portes 3+4 inutilisées à GND), **mesurer le nœud du diviseur de sortie au repos → doit lire ~3,3 V** (et non 2,28 V) ; (2) relier GPIO16, raquette débranchée → `GET_VER` → **écho enfin propre** attendu ; (3) **rebrancher la raquette** → test décisif : pilote-t-elle sans « No Response » (buffer haute-Z = vraie victoire S28) ; (4) jalon C logiciel (driver mode Network + slew continu) — sachant qu'il **reste le nœud « la monture n'ACK pas le `GET_VER` à travers le pont »** (collision half-duplex / écho relayé) à traiter côté firmware ESP32 (suppression d'écho + fenêtre de turnaround).

### Session 29 — Pivot ESP32 : jalons A+B verts — la monture bouge via le pont (2026-06-13)

Thread matériel (suite directe S28), **sur la workstation** (le Pi est resté éteint). Reprise du test de découplage du RX CH340, puis **pivot vers l'ESP32** récupéré — comme l'utilisateur l'avait anticipé en début de session.

**Diagnostic RX confirmé (établi, multimètre/raquette de référence) :**
- **Masse seule propre** : tap `GND` (broche 5) uniquement, RX débranché → la raquette pilote sans erreur → **la masse n'est pas en cause, le RX du CH340 est le coupable**.
- **R série 4,7 kΩ insuffisant** : intercalé entre DATA et le RX → ça reperturbe le bus. Le RX du CH340 injecte trop de courant même à travers 4,7 k → **découplage passif mort**. (Pistes 10 k / opto non tentées : seuil « galère » atteint.)

**Décision (utilisateur) : pivot ESP32.** Un ESP32 se pose sur le bus AUX et l'expose en TCP ; le driver `indi_celestron_aux` a un mode « Celestron WiFi » (= TCP, IP `1.2.3.4`, **port 2000**) qui parle le protocole AUX binaire à travers la socket. Avantage décisif : l'ESP32 lit le bus avec un **vrai GPIO haute-Z** → supprime par construction le défaut du RX CH340.

**Firmware retenu — pont transparent minimal** (≠ Mark Lord/g7ltt lourd GPS+BT, ≠ alex-vg AP-only) : ~50 lignes, zéro dépendance externe (`WiFi.h` seul), `Serial2` sur **GPIO16 (RX) / GPIO17 (TX)** en 19200 8N2, AP WiFi + `WiFiServer` port 2000, boucle de relais TCP↔UART bidirectionnelle (l'écho single-wire est filtré côté driver). Page autonome : [`../technical/esp32-aux-bridge.html`](../technical/esp32-aux-bridge.html) (firmware + câblage + jour/nuit).

**Toolchain + flash (workstation Linux) :** `arduino-cli` 1.5.1 (tarball officiel, pas de `curl|sh` — bloqué par le classifier), core `esp32:esp32` 3.3.10. Carte = **ESP32 DevKit puce CP2102** (`10c4:ea60`) sur `/dev/ttyUSB0`, FQBN `esp32:esp32:esp32`. Compile clean (69 % flash, partition par défaut), flash OK. Accès port : utilisateur ajouté à `dialout`, flash sans re-login via `sg dialout -c "…"`.

**🟢 Jalon A vert** — toute la chaîne ESP32 prouvée depuis le PC, **sans toucher à la monture** : boot → bannière série `AP=AstroBrain-AUX ip=192.168.4.1 tcp=2000`, puis **`TCP 192.168.4.1:2000 → OPEN`**. Test fait via un **script à `trap`** qui bascule sur l'AP, teste le port, puis **rebascule garanti sur le WiFi normal** (sinon la perte d'internet coupait la session API) — réflexe de l'utilisateur, payant.

**Enseignement réseau :** l'AP de l'ESP32 est en **2,4 GHz canal 1**, invisible tant que le PC reste associé en 5 GHz (il a fallu déconnecter la radio pour la voir). → **confirme le mode station** pour le déploiement : l'ESP32 rejoindra le réseau/hotspot du Pi (le Pi garde sa liaison téléphone), pas l'inverse. Smoke jalon C possible en faisant temporairement rejoindre l'AP par le Pi.

**🟢 Jalon B validé — la monture bouge.** Câblage : étage **BC547** (validé S28, 0,05 V) **piloté par GPIO17** (3,3 V sature Q1), **RX GPIO16 via R série 3,5 k** (protège le GPIO 3,3 V du ~4,4 V idle bus), alim 5 V via **VIN (5 V du Pi, USB débranché)**, GND broche 5, +12 V (broche 3) jamais. Raquette **débranchée** (sinon 2 maîtres sur le bus → conflit / erreur « No Response » du HC — c'est ce que voyait l'utilisateur, pas le défaut CH340). Test via la workstation rejoignant l'AP (script à trap) :
- `GET_VER` (AZM + ALT) → **écho seul** (les contrôleurs n'ACK pas notre requête, comme S27/S28).
- Test **décisif fire-and-forget** : rejeu des octets de slew capturés S28 (`3b 04 0d 10 24/25 09`) via TCP → **l'AZM tourne physiquement, dans les deux sens, sur commande** (confirmé visuellement). Mouvement **~0,5 s par commande puis arrêt** ; réémettre toutes les 250 ms ne prolonge pas → le bus est **half-duplex**, il faut attendre la libération (turnaround) après chaque trame, ce que le rejeu brut ne fait pas mais que le vrai driver `indi_celestron_aux` gère. Slew continu donc déféré au jalon C.

**⇒ Le blocage matériel S26→S28 est LEVÉ : on pilote la monture via le pont ESP32.** Le couple « pont transparent ESP32 + étage BC547 » fonctionne de bout en bout.

**ADR :** le pivot ESP32 déroge à l'ADR « pas d'Arduino » → **ADR à acter au jalon C** (slew continu via INDI), même discipline que le Nano S27.

**Reprise — jalon C (INDI réel) :** prérequis = **IP stables** + **ESP32 en mode station** sur le réseau maison. Puis `indi_celestron_aux` en **mode Network** (IP ESP32 : 2000) sur le Pi → connexion + slew continu. Jalon D : backend série→réseau, sketch dans `firmware/`, ADR pivot ESP32.

**🟢 Prérequis réseau du jalon C LEVÉS (suite de soirée, 2026-06-13) :**
- **Firmware ESP32 réécrit en mode station** (`WIFI_STA`, repli AP auto si la station échoue → jamais verrouillé, `WiFi.setSleep(false)` pour la latence). Identifiants dans `secrets.h` séparé (hors repo, à gitignore au jalon D). Flashé : bannière série `mode=STA ip=192.168.1.200 tcp=2000`.
- **IP de l'ESP32 figée à `192.168.1.200`** (statique dans le firmware, hors plage DHCP, GW `.254`). **Plus de valse WiFi** : l'ESP32 est un nœud permanent du réseau, joignable sans bascule → la session API reste vivante pendant les tests. `TCP 192.168.1.200:2000 → OPEN` confirmé depuis la workstation.
- **Pi joignable** : il était bien à `192.168.1.36` (MAC `b8:27:eb:11:e7:93`) — le « no route » initial venait d'une entrée ARP périmée, résolue par un ping sweep. SSH OK ; `indiserver.service` + `astro-brain.service` **actifs**. (Pi toujours en DHCP → réservation box recommandée pour figer le `.36`.)
- **Driver diagnostiqué** : `Celestron AUX` chargé mais `CONNECTION_MODE=SERIAL` pointant sur l'ancien chemin CH340 mort (`/dev/serial/by-id/usb-1a86…`). **Fix connu** = basculer `CONNECTION_TCP=On` + `DEVICE_ADDRESS=192.168.1.200:2000`.
- Driver basculé en TCP : `CONNECTION_TCP=On` + `DEVICE_ADDRESS=192.168.1.200:2000` (config cible, conservée).

**🟢 Tentative jalon C (même soirée) — chaîne réseau→monture PROUVÉE, blocage isolé au driver :** montage physique remonté (ESP32 sur le bus via étage BC547, alim 5 V du Pi, **monture sous tension, raquette débranchée**).
- **La chaîne complète marche de bout en bout** : `astro-brain.service` stoppé (systemctl), driver INDI déconnecté pour libérer le pont, puis **rejeu brut des octets de slew depuis la workstation → ESP32 `192.168.1.200:2000` → bus → LA MONTURE BOUGE** (AZM, confirmé visuellement). ⇒ **le cœur du jalon C est atteint : on commande la monture à distance, par le réseau, depuis le Pi.**
- **Le driver INDI, lui, ne pilote pas** : `CONNECT=On` est un **faux positif** (socket ouvert ≠ monture qui répond). Symptômes : positions = défauts driver (`AZ=360`, `DEC=90`), et un `TELESCOPE_MOTION_WE.MOTION_WEST=On` de 2 s à 5x **ne bouge rien**. Cause = la rengaine S27→S29 : `GET_VER` revient en **écho seul**, la monture n'ACK pas notre requête de version *à travers le pont* → le driver ne détecte jamais les axes et **ignore silencieusement** le mouvement. Les commandes fire-and-forget (MOVE) passent ; le dialogue question/réponse (handshake) ne récupère pas la réponse.
- **Problème isolé à 100 % dans le logiciel** (driver/pont), plus le hardware. **Piste n°1** : le pont transparent relaie notre propre écho et **avale / court-circuite la réponse de la monture** (collision half-duplex) → le driver ne voit jamais l'ACK. À régler côté firmware ESP32 (suppression d'écho / fenêtre de turnaround) et/ou options driver.
- **Ops** : WiFi du Pi a **décroché transitoirement** en cours de test (Pi introuvable sur tout le /24 alors que l'ESP32 tenait son `.200`) puis revenu seul — WiFi Pi 3 B+ instable, à fiabiliser (réservation DHCP + investiguer). `astro-brain.service` **relancé** en fin de test (systemctl), services actifs.

**Reprise — finir le jalon C (logiciel) :** (1) activer le **debug FILE** du driver `Celestron AUX` et **capturer l'échange `GET_VER`** sur le Pi pour voir si la monture répond et où la réponse se perd ; (2) tester une **suppression d'écho** côté pont ESP32 (ne pas réémettre vers TCP les octets qu'on vient d'envoyer au bus) pour que la réponse du contrôleur arrive propre ; (3) reCONNECT + slew. Puis ADR pivot ESP32 + jalon D (backend série→réseau, sketch dans `firmware/`).

**À faire (doc) :** ~~journal en surcapacité → archiver Macro 3 software (S20-25)~~ **fait** (→ `journal/archive/2026-05-macro3-software.md`, S26→S29 visibles).

### Session 28 — Single-wire 2× BC547 : niveau résolu (0,05 V), mais le dongle CH340 perturbe le bus (2026-06-11)

Thread matériel (suite directe S27). L'utilisateur a **récupéré des composants** dont 2 transistors — ce qui manquait pour l'option open-collector. Identification au multimètre : marquage `C547A` + `PH90` = **BC547A NPN** (PH90 = code date Philips), base centrale (~0,9 V des deux côtés en test diode), brochage **C-B-E** (≠ E-B-C des 2N…). Zener récupérées écartées (Vz basse claquerait sous 5 V).

**Montage construit — driver open-collector 2× NPN** : Q1 inverseur + Q2 driver, 4× **4,7 kΩ** (Rb1/Rc/Rb2/Rpu). Page câblage autonome créée : [`../technical/aux-single-wire-cablage.html`](../technical/aux-single-wire-cablage.html) (schéma SVG + netlist + brochage + toggle jour/nuit). Test logique sur table OK (TX→GND → DATA bascule).

**⚠️ Faux positif corrigé.** Le 1er « smoke test INDI réussi » (`CONNECT=On` + `HORIZONTAL_COORD` AZ=360/ALT≈0) était **trompeur** : `CONNECT=On` = ouverture du port + écho, et les positions sont des **défauts driver**, pas une vraie réponse. Le **test série brut `GET_VER`** (méthode S27, pyserial hors INDI) tranche : **écho seul (6 o), monture muette**, comme S27. Docs `hardware.md`/`roadmap.md` rectifiées en conséquence.

**Acquis solides de la soirée :**
- **Niveau bas du bus = 0,05 V** (break série, mesuré multimètre) avec le transistor, vs 0,97 V avec la diode S27 → la **cause racine S27 (niveau > VIL des PIC) est bel et bien résolue électriquement**. Le montage transistor est bon.
- **Câblage confirmé** (multimètre, notre fil débranché) : broche 4 (DATA) idle à **4,4 V** (= pull-up interne de la monture), broche 3 = +12V, le reste 0V → on est bien **sur le bus DATA vivant**.
- **Sweep baud × stop bits × contrôleur** (redevenu pertinent une fois les niveaux bons — celui de S27 était invalidé par le 0,97 V) : **écho seul sur les 8 combos** (19200/9600 × 8N1/8N2 × 0x10/0x11).
- **RX prouvé bon** : en **sniffer pur** (`DATA→RX` + `GND`, sans transistors), capture de **trafic externe réel** — au boot `3b 03 0d 11 05 da`, puis les slews du HC : `3b 04 0d 10 24 09 b2` (cmd **0x24 SET_POS_GUIDERATE** rate 9), `…24 00 bb` (STOP), `…25 09 b1` (**0x25 SET_NEG_GUIDERATE**). **Source du HC = `0x0d`** (= la nôtre → bonne). Ces commandes sont **fire-and-forget** (aucune réponse attendue) → pour *bouger* la monture il suffit de les émettre, pas de handshake. **Octets de slew AZM capturés.**

**🧱 Nouveau mur (cœur du blocage) :** même un **simple tap `DATA→RX dongle + GND`** (sans transistors, sans Rpu, sans TX) **perturbe le bus** → erreur raquette « No Response » + dérive monture (le STOP ne passe plus). Donc **le coupable n'est PAS notre montage transistor** (validé électriquement) mais **le dongle CH340 qui charge/déforme le bus** rien qu'en s'y posant. Hypothèses : broche RX du CH340 **non haute-Z** (pull-up/clamp interne vers 5V) qui déforme la forme d'onde pour les entrées **strictes** des contrôleurs ; ou **problème de masse/domaine d'alim** (raquette alimentée *par le bus* = masse native ; notre dongle alimenté *par le Pi* = autre masse). Thème récurrent de S27+S28 : **notre RX CH340 permissif, entrées monture strictes.**

**ADR « pas d'Arduino »** : toujours préservé, Nano toujours inutile (le niveau est résolu) — le blocage a juste migré vers le couplage dongle↔bus.

**Ops** : tests via `indiserver` ad-hoc puis service systemctl ; un `pkill -x indiserver` du début a tué l'instance systemd (rappel S27 : **passer par `systemctl`**). Backend `astro-brain.service` arrêté pendant les tests. Services `indiserver.service` + `astro-brain.service` **remis en route via `systemctl`** en fin de session.

**Reprise (demain) :**
1. **Test d'isolation masse vs RX** : connecter d'abord *seulement* `GND` (broche 5), RX débranché → la raquette marche-t-elle ? **Propre** = masse OK, **broche RX coupable** → découpler le RX (résistance série kΩ / buffer haute-Z / **optocoupleur**). **Perturbe déjà** = problème masse/domaine d'alim.
2. Tap rendu non-perturbant → en **maître unique**, **rejouer les octets de slew capturés** `3b 04 0d 10 24 09 b2` puis STOP `…24 00 bb` → si l'AZM bouge, on **pilote la monture en AUX brut** (sans dépendre du handshake INDI).
3. Pistes matériel : essayer un **autre dongle** (CP2102/FT232, entrée RX différente), ou interposer un **buffer/optocoupleur**.
4. Bug backend `set_time`/`set_location` (`TypeError __getitem__`, S27) toujours en attente.

### Session 27 — Smoke test interface single-wire : diagnostic diode + pivot Nano (2026-06-07)

Thread matériel (pas de code), suite directe de Session 26 : câblage et smoke test de l'interface single-wire sur breadboard, sur le port **HAND CONTROL** via un breakout RJ-12 à borniers à vis. **Reprise = câbler + flasher le Nano (voir « décision » plus bas), puis valider.**

**Découvertes hardware en cours de route :**
- Le dongle réel est un **CH340** (`1a86:7523`), **pas un CP2102** comme l'écrit la doc partout → `hardware.md` + `CLAUDE.md` à corriger.
- `hardware.md` a une **erreur de polarité** : il dit « diode (cathode vers DATA) » — c'est l'**inverse**. Correct = **anneau/cathode côté TX/dongle**, anode côté DATA. À corriger.
- Bus muet d'abord à cause de défauts d'interface successifs (diode morte OL, puis diode non reliée au bon nœud breadboard, puis orientation) — tous résolus.

**Diagnostic décisif (test série brut, hors INDI)** : `pyserial` dispo system-wide sur le Pi (`python3-serial`). Envoi direct d'une trame AUX `GET_VER` (`3b 03 0d 10 fe e2`) sur `/dev/ttyUSB0` en 8N2 → **écho exact reçu, aucune réponse monture**. Sweep baud (9600→115200) × format (8N1/8N2) × 2 moteurs (AZM 0x10 / ALT 0x11) × 4 adresses source = **écho seul partout**. ⟹ interface dongle, trame, baud, format, **software/driver tous hors de cause**.

**Cause racine** : niveau bas du bus mesuré à **0,97 V** (break-test, ligne tenue basse) — `Vol(TX) + Vf(1N4007)` ≈ 0,2 + 0,75. C'est **au-dessus du `VIL` des PIC** moteurs (~0,8 V TTL / 1,0 V Schmitt) → ils ne voient jamais un vrai 0. Le RX du CH340 (seuil permissif) lit quand même → d'où « écho parfait, monture muette ». **Monture saine** (la raquette la pilote nominalement, branchée en direct). Doubler la 1N4007 ne sauve pas (silicium plafonne à ~0,7 V ; parallèle ne gagne que ~20–40 mV). Breadboard hors de cause (parasites négligeables à 19200).

**Décision — Nano dédoubleur open-drain** (option (c) de Session 26, retenue faute de Schottky/transistor) : le Nano (5V) tire le bus à **~0,1 V franc** en open-drain. Topologie affinée — le Nano fait **tout**, on **retire diode ET pull-up externe** : `dongle TX → D2`, `D3 → RX dongle`, `D4 ↔ DATA (br.4)` open-drain + **pull-up interne**, GND commun (dongle+Nano+monture br.5), Nano alimenté par le 5V du dongle. Firmware ~15 lignes (port direct, `DDRD`/`PORTD`/`PIND` sur D2/D3/D4). Schéma + firmware + procédure : [`docs/technical/astro-nano-interface.html`](../technical/astro-nano-interface.html). Caveat : pull-up interne faible (~30–50 kΩ) → si `GET_VER` flaky, ajouter **une** pull-up externe 1k–4.7k. **Déroge à l'ADR « pas d'Arduino » → ADR à acter une fois validé.**

**Bug backend repéré** (séparé du hardware) : `mount_indi_adapter.py` `set_time`/`set_location` crashent en boucle — `TypeError` sur `PropertyBasicText/Number.__getitem__` (mauvais type d'argument) → le client INDI du backend se reconnecte/EOF toutes les ~2 s. À corriger côté Macro 1.

**Ops / incident** : un `pkill -f indiserver` (nettoyage) a tué `indiserver.service` (que `astro-brain.service` `Requires`) → app « mount error / indiserver disconnected ». **Leçon : ne jamais `pkill` indiserver, passer par `systemctl`.** Backend `astro-brain.service` *stoppé* (pas *disabled*) en fin de session pour des tests propres → repart seul au prochain boot ; sinon `sudo systemctl start astro-brain.service`.

**Reprise prochaine session** : (1) câbler + flasher le Nano ; (2) break-test (DATA↔GND doit tomber à ~0,1–0,2 V) → `GET_VER` (réponse = octets en plus de l'écho) → slew réel ; (3) si OK : nettoyer la doc (**CP2102→CH340**, **corriger « cathode vers DATA »** dans `hardware.md`), **acter l'ADR Nano**, puis reprendre `INTEGRATION_CHECKLIST.md` (Macro 1).

### Session 26 — Investigation liaison monture : bus AUX NexStar SLT (2026-06-05)

Thread matériel (pas de code), déclenché par la lecture d'un doc reverse-engineering HC Celestron. **Monture identifiée formellement** (photos) : **NexStar 127 SLT**, raquette **NexStar+ pré-2016** (port PC en bas = RJ-22 RS-232, **pas d'USB**). Les deux jacks RJ-12 de la base (`AUX` + `HAND CONTROL`) sont en parallèle sur le **bus AUX interne**.

**Corrections de doc** (`CLAUDE.md` + `docs/technical/hardware.md`) : l'ancienne description « port HC, 9600 baud, pass-through `P` » était fausse pour le chemin retenu. Réalité du bus AUX : **5V TTL, 19200 8N2, ligne DATA unique bidirectionnelle (half-duplex)** sur la broche 4 ; **+12V sur broche 3 (à ne jamais brancher)** ; GND broche 5 ; SELECT broche 6. Brochage refait, test `K` Echo retiré (invalide en AUX direct — c'est une commande de la raquette, pas du bus), test remplacé par validation stack INDI. `indi-reference.md` était déjà correct (19200, AUX direct, SLT reconnu).

**Le vrai blocage n'est pas le dongle CP2102** : le bus est single-wire, un TX push-pull nu y crée un conflit avec les moteurs. Il faut une **interface single-wire** entre le dongle et la broche 4. Options comparées : (a) **diode Schottky + pull-up** (le plus sain, ~0 firmware, 1 composant à sourcer) ; (b) **74HC125** (n'existe pas en breakout prêt façon ADXL — puce DIP à câbler) ; (c) **Nano en répéteur open-drain bit-à-bit** (~15 lignes, 0 commande si Nano dispo, mais déroge à l'ADR « pas d'Arduino »). **Décision en attente** : l'utilisateur arbitre selon les pièces qu'il trouve.

**Impact backend = nul** : le série (baud, port, `PORT_TYPE`, single-wire) est 100 % géré par `indi_celestron_aux` ; `mount_indi_adapter.py` ne pousse ni baud ni `PORT_TYPE` (champ `_serial_device` stocké mais non utilisé pour configurer le driver — petit TODO connexion à prévoir). À noter : `nexstar-protocol-reference.md` + `nexstar-capabilities.md` décrivent encore l'ancien chemin série nexstarpy (9600/RJ-22/pass-through, `nexstar_adapter.py` supprimé) — à marquer historiques ou conserver comme réf du jeu de commandes AUX (non tranché).

## Archives

- [`2026-04-backend-v0.1.md`](journal/archive/2026-04-backend-v0.1.md) — Sessions 1→7 : brainstorm, spec design, monorepo + uv, Tasks 1-17 du plan backend, revue/renforcement, validation physique GPS + compass, décision capteurs ADXL345.
- [`2026-04-frontend-v0.1.md`](journal/archive/2026-04-frontend-v0.1.md) — Sessions 8→10 : démarrage app Flutter (thème + design system), livraison v0.1 (Splash / Home / System, blocs, services REST + SSE, 47 tests), smoke test Moto g54 5G + 4 fixes UX (53 tests).
- [`2026-04-v02-setup-prep.md`](journal/archive/2026-04-v02-setup-prep.md) — Sessions 11→14 : préparation v0.2 Setup — brainstorm v0.2, réorganisation roadmap + arborescence docs en 3 vues, recherche exhaustive du protocole NexStar + assainissement repo, scaffold Flutter + carte #8 Réseau livrée.
- [`2026-05-macro1-indi.md`](journal/archive/2026-05-macro1-indi.md) — Sessions 15→16 : install stack INDI 2.2.0 + driver Celestron AUX sur le Pi (Astroberry Trixie arm64), rebase + merge backend `MountIndiAdapter` + `pyindi-client` sur main (89 tests verts, `nexstarpy` retiré). Smoke test E2E reste bloqué par dongle CP2102.
- [`2026-05-macro2-setup.md`](journal/archive/2026-05-macro2-setup.md) — Sessions 17→19 : Macro 2 Setup Slices INFRA (sqlite `state.db` + repos calibration/limits, 8 tasks INFRA), A capteurs (ADXL345 ×2 + LIS3MDL, refactor `CalibrationBloc` partagé -784 LOC), B (courses ALT) + C (À propos). Items #1 #2 #3 #4 #8 #9 livrés ; Slice D backlash/cordwrap reste bloqué dongle CP2102.
- [`2026-05-macro3-software.md`](journal/archive/2026-05-macro3-software.md) — Sessions 20→25 : Macro 3 tranche logicielle — Hub central (#1), wizard alignement 3 étoiles (#2, modèle natif Celestron via `sync_radec`), GoTo réel + page Catalogue (#3/#5), catalogue backend stars IAU CSN (#4 tranche A), aide étoile/constellation + chaîne de position fix Pi→téléphone. Validation matérielle de tout reportée derrière la liaison monture (Macro 1, fil S26+).
