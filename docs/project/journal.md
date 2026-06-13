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

**Reprise — jalon C (INDI réel) :** prérequis = **IP stables** (réservation DHCP box ou IP statique pour le Pi *et* l'ESP32 — le Pi change d'IP à chaque bail, injoignable en fin de S29 : `.36` muet, absent du scan ARP, aucun OUI `b8:27:eb`) + **ESP32 en mode station** sur le réseau maison (reflash, identifiants WiFi hors repo). Puis `indi_celestron_aux` en **mode Network** (IP ESP32 : 2000) sur le Pi → connexion + slew continu. Jalon D : backend série→réseau, sketch dans `firmware/`, ADR pivot ESP32.

**À faire (doc) :** journal en surcapacité (sessions 20→29 visibles) → archiver le milestone Macro 3 software (S20-25) à la prochaine occasion.

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

### Session 25 — Macro 3 #2 : aide « étoile dans sa constellation » + chaîne de position (software) (2026-06-05)

Plan `docs/superpowers/plans/2026-06-04-constellation-star-aid.md` (15 tasks) exécuté en mode `superpowers:subagent-driven-development` (implémenteur + double revue spec/qualité par task) sur branche `feat/constellation-star-aid`. Spec : `docs/superpowers/specs/2026-06-04-constellation-star-aid-design.md`. Feature complète « aide à la reconnaissance de l'étoile dans sa constellation » pour le wizard d'alignement.

**Backend** : `constellation_of()` (abréviation IAU dérivée du champ `bayer`) + `visible_stars()` (étoiles d'alignement pointables groupées par constellation) ajoutés à `_alignment_catalog.py` ; asset autonome `astro_brain/data/constellation_figures.json` (23 figures couvrant les 32 étoiles d'alignement) généré une fois par `scripts/build_constellation_figures.py` (sources Stellarium constellationship + HYG, csv non commité) ; loader `services/constellation_figures.py` (figure + matching cible par proximité angulaire + projection alt/az) ; `POST /align/location/client` pour recevoir la position GPS du téléphone, garde 409 sur `/align/start` sans aucune position connue ; `GET /align/constellation/{abbr}` + `GET /align/stars/visible`. **Décision clé** : la chaîne de position devient fix GPS Pi → GPS téléphone → sinon le wizard n'est pas proposé — le fallback Paris codé en dur est supprimé (ADR à consigner si jugé structurant).

**Frontend** : DTOs `ConstellationFigure/Node` ; `AlignmentRepository.fetchConstellation/fetchVisibleStars/postClientLocation` ; widget `ConstellationChart` (CustomPaint, schéma au trait orienté ciel/atlas, étoile cible en halo) ; intégration `per_star_screen` (nom constellation dans le hero + bouton « Voir dans la constellation » → bottom sheet) ; `StarNavigatorScreen` (swap : filtre par constellation **visible** + liste + chart) ; repli position téléphone via `geolocator` (abstraction `PhoneLocation`, fallback 409 dans `AlignmentBloc._onStarted`) ; bandeau « Position GPS requise » sur la carte ALIGNER du Hub quand pas de fix Pi ni position téléphone.

**Tests et incident** : backend 342 passed, app 226 passed, `flutter analyze` clean. TDD strict, double revue par task. Incident notable : l'agent de la dernière task (T14) a timeout avant commit ; travail récupéré et finalisé manuellement — 3 tests Hub réparés (provider `AppBloc` manquant + `pump` vs `pumpAndSettle` + scroll). Validation matérielle (wizard sur ciel réel) reportée derrière déblocage dongle CP2102 (Macro 1).

### Session 24 — Macro 3 #3 GoTo réel + #5 Page Catalogue (software) (2026-06-01)

Plan `docs/superpowers/plans/2026-05-31-catalogue-goto.md` (19 tasks) exécuté en mode `superpowers:subagent-driven-development` (implémenteur + revue spec/qualité par task) sur branche `feat/catalogue-goto`. Brainstorm + spec validés en amont (`docs/superpowers/specs/2026-05-31-catalogue-goto-design.md`, companion visuel pour la mise en page). Feature complète « parcourir le catalogue → pointer ».

**Backend (B1→B9)** : extraction `_ephemeris.py` (conversion RA/Dec→Az/Alt, partagé alignement + catalogue, ré-export depuis `_alignment_catalog.py`) ; `CatalogObject` gagne `altitude_deg`/`azimuth_deg` ; `VisibilityEnricher` (alt/az courants + filtre `visible_now`, dégradation gracieuse sans fix GPS) au-dessus du `CatalogRegistry`, câblé sur `/catalog/objects?visible_now=` via `sensors_bridge.gps_fix` ; `MountService.goto_radec(ra,dec,target_name)` (`ON_COORD_SET=TRACK` + `EQUATORIAL_EOD_COORD`, publie `moving`+`goto_in_progress`+`goto`) ; détection de fin de slew en activant `AstroBrainIndiClient.updateProperty` (no-op jusqu'ici) → `handle_property_update` adapter (EQUATORIAL_EOD_COORD BUSY→Ok/Idle → `ready`+`tracking=sidereal`) ; flag `is_aligned` en RAM (`finalize`→vrai, `cancel`/`invalidate`→faux), publié dans l'état SSE `alignment` ; `AlignmentInvalidator` (abonné bus, invalide à la reconnexion monture `disconnected`/`connecting` — **pas** sur `error` transitoire, fix de revue) ; router `POST /goto` (gardes 409 non-aligné / 409 slew en cours, 422 coords), abort réutilise `POST /stop`.

**Frontend (F1→F10)** : `SystemState` parse le sous-système `alignment` (getters `isAligned`/`gotoInProgress`/`gotoTarget`) ; feature `lib/features/catalogue/` (DTO, `CatalogueRepository`, `CatalogueBloc` recherche debounce + filtres + goto/abort) ; `CatalogueScreen` (bandeau non-aligné + CTA wizard, recherche, chips magnitude/visible-now désactivée sans GPS, liste de cartes, détail en bottom sheet, bouton GoTo grisé si non aligné, slew bar pilotée SSE + STOP) ; carte Hub CATALOGUE + wiring `app.dart`.

**Corrections de revue notables** : `error` retiré des états d'invalidation alignement (un échec de commande INDI transitoire ne doit pas perdre l'alignement) ; `_onGoTo`/`_onAbort` capturent les erreurs → `CatalogueError` (convention codebase) ; `TextField` de recherche extrait dans un widget stateful avec contrôleur (hors `BlocBuilder`) pour ne pas perdre le curseur ; **revue finale (Opus)** a trouvé un défaut masqué par les fakes : `stop_slew(None)` ne réinitialisait pas le latch goto → complétion fantôme `sidereal` après un STOP — corrigé + test de régression.

**Tests** : backend 300 → 322 verts ; app 182 → 196 verts ; `ruff`/`flutter analyze` clean. Validation matérielle (slew réel sur monture) et validation visuelle Android reportées dongle CP2102 (Macro 1).

**Raffinements différés** consignés dans [`backlog.md`](backlog.md) (feedback d'échec GoTo en SnackBar, `buildWhen` slew bar, seuil de visibilité par obstruction).

**Validation sur device (Moto g54, Pi déployé à jour, sans dongle)** : le smoke téléphone a remonté plusieurs points, corrigés dans la foulée. (1) **Bug 404 catalogue** : `CatalogueRepository` collait la query dans le path (`/catalog/objects?…`) passé à `getJson` → `PiHost.restUri` faisait `Uri.http(authority, path)` qui encode le `?` en `%3F` → `/catalog/objects%3F…` → 404. Premier endpoint à utiliser une query string ; le test du repo mockait `getJson` sans exercer `restUri`. Fix : query passée via `Uri.http(queryParameters)` + tests de régression `restUri`. (2) **UX cartes** : passage à la version aérée (design B), nom de constellation en toutes lettres (table abréviation IAU → français), bouton POINTER du bottom sheet rendu visible via `SafeArea`. (3) **Filtre par constellation** (menu déroulant client-side, ne liste que les constellations présentes). Aussi : mDNS `astro-brain.local` non résolu par Android → host renseigné en IP dans Setup → Réseau. Tests app 198 → 204. Commits `f179db4`, `b53bde9`, `d51d123`.

### Session 23 — Macro 3 #4 catalogue backend tranche A (stars IAU CSN) (2026-05-10)

Plan `docs/superpowers/plans/2026-05-10-catalog-backend-stars.md` (11 tasks) exécuté en mode `superpowers:subagent-driven-development` directement sur `main`. Tranche A du #4 : pipeline catalogue backend + seed étoiles brillantes IAU CSN cap mag ≤ 3. Tranches Messier + planètes (skyfield) reportées.

**Architecture catalogue** : table sqlite unifiée `catalog_objects` (migration `_003_catalog_objects`, 3 indexes : kind, kind+mag, kind+constellation) ; `CatalogProvider` Protocol + `SqliteCatalogProvider(db, kind=...)` qui requête la table avec filtres `kind`/`search` (sur `name`/`designation`)/`max_mag`, trié par mag puis name ; `CatalogRegistry({"star": provider})` dispatch par kind avec merge+widen pour la pagination cross-kind ; `apply_seeds(db, data_dir)` au boot, lexical glob `seed_*.sql`, idempotent via `INSERT OR REPLACE`, log-and-continue par fichier. Wire dans `astro_brain/app.py` lifespan : `apply_seeds` après `run_migrations` via `as_file(files("astro_brain.data"))`, registry exposé sur `app.state.catalog_registry`.

**Endpoint REST** (`/catalog/objects`) : `GET /catalog/objects?kind=&search=&max_mag=&limit=&offset=` retourne `CatalogListResponse(objects, count, limit, offset)` avec validation Pydantic (limit 1-500, offset≥0, max_mag réaliste). `GET /catalog/objects/{qualified_id:path}` (path converter pour le `:` dans `star:sirius`) → 200 ou 404 `"object not found"`.

**Seed pipeline** : workstation tool `backend/tools/seed_stars.py` télécharge l'IAU CSN (mirror Rochester `pas.rochester.edu/~emamajek/WGSN/IAU-CSN.txt` — l'URL canonique iau.org a été retirée fin 2026), parse le whitespace fixed-width via date-anchored back-parsing (regex `^\d{4}-\d{2}-\d{2}$` localise la colonne 15, puis `date_idx-N` pour récupérer les champs en remontant), filtre V mag ≤ 3.0, sort dans `astro_brain/data/seed_stars.sql` (140 INSERT OR REPLACE déterministes triés par slug). Pipeline déterministe : re-run produit un fichier byte-identique. Ce `.sql` est committé.

**Tests** : 247 → 300 verts (+53). Migration (3), models (3), `SqliteCatalogProvider` (5), `CatalogRegistry` (4), `apply_seeds` (7), routes (6), tool de seed (7), wire app (3), smoke réel (4 : ≥50 stars chargés, Sirius/Vega/Polaris présents avec noms, RA/Dec dans les bornes, filter `max_mag=2.0` retourne ≥10 entrées toutes sous le seuil). Smoke test passe à travers la chaîne réelle (`run_migrations` → `apply_seeds` → `SqliteCatalogProvider`) — il fail loudly si le seed se corrompt.

**Adaptations notables au plan** :
- L'URL canonique `iau.org/.../IAU-CSN.txt` du plan retournait HTTP 403 (site IAU restructuré). Bascule vers le mirror Rochester maintenu par le secrétaire WGSN, autorisée par l'utilisateur en cours de session.
- Plan supposait un format pipe-separated dans la fixture du tool ; le vrai CSN est whitespace fixed-width. Plan Step 3 anticipait la divergence — parser réécrit en date-anchored back-parsing (5 lignes IAU réelles dans la fixture incluant Sirius/Vega/Polaris/Bételgeuse), expected values ajustées sur les vraies données IAU (Sirius mag=-1.45, ra=101.287155, dec=-16.716116, constellation="CMa").
- Code review post-Task-9 : minor off-by-one corrigé (`< 14` au lieu de `< 13` pour le minimum legal `date_idx`) + URL constante `CSN_URL` réalignée sur Rochester (commit polish post-review).
- Tranche A+1 du plan (refactor `wizard_alignment` pour consommer `CatalogRegistry` au lieu de `_alignment_stars.json`) reportée — backlog Macro 3 #2 / #4. `_alignment_catalog.py` reste en place et inchangé pour l'instant.

**Documentation** : roadmap Macro 3 #4 mise à jour (`📦` → `🚧 tranche A livrée 2026-05-10`). Journal : Sessions 17-19 archivées dans `journal/archive/2026-05-macro2-setup.md` (milestone Macro 2 Setup Slices INFRA/A/B/C). Plafond ramené à 4 sessions visibles (20-23).

### Session 22 — Macro 3 #2 wizard 3 étoiles, implémentation software (2026-05-10)

Plan `docs/superpowers/plans/2026-05-09-wizard-3star-alignment.md` (22 tasks) exécuté en mode `superpowers:subagent-driven-development` (implementer + spec reviewer + code-reviewer par task) directement sur `main`. Le wizard va du Hub jusqu'à la validation finale ; restore mid-wizard si une session backend existe.

**Backend** (Tasks T1→T10) : Pydantic models `Star`/`StarRecord`/`AlignmentSession`/`AlignmentModel` (résiduel SVD, `quality` good/marginal/bad), mini-catalogue 30 étoiles brillantes en JSON, `CatalogSelector` (filtrage altitude/séparation), `SvdAlignSolver` (résolution Procrustes orthogonal), repository sqlite `alignment_sessions` (migration `_002_alignment`), `AlignmentService` (machine d'état idle / candidates / pre_pointing / fine_tuning / validating / done), router REST `/align/*` (start, swap, record, restart_star, finalize, cancel) avec 409/422 mappings, wiring dans `build_app`, événement SSE `alignment.session` publié à chaque mutation. Approche défensive : `_publish_session` idempotent, deepcopy du snapshot avant publish.

**Frontend** (Tasks T11→T19) : refactor `DPadControl` API (`onPress: ValueChanged<DPadDirection>` / `onRelease`) et `RateControl` (4 paliers via `ValueChanged<int>`) — préparatoires partagés Manuel/Wizard. DTOs Flutter miroirs des Pydantic, `AlignmentRepository` (REST), `AlignmentBloc` (9 events, 7 states sealed, `existing ?? await repo.start()` pour cold-start restore). Écrans : `IntroScreen` (DÉMARRER), `PerStarScreen` (D-Pad + RateControl + axis bars AZ/ALT + bouton CENTRÉ ✓), `ValidationScreen` (RMS + 3 résiduels barres, bloc diagnostic conditionnel sur outlier `>3× moyenne autres`, REFAIRE/ACCEPTER), `DoneScreen` (RETOUR HUB via `popUntil((r) => r.isFirst)`). Wizard host BlocBuilder route les 7 states. `AstroScreen.alignment` ajouté au enum AppBar. Wire app.dart : `BlocProvider<AlignmentBloc>` (4ème provider) + tuile "ALIGNER" insérée entre MANUEL et SETUP dans le Hub (icône `strokeRoundedTarget02`, hint "3 étoiles · mise en station").

**Adaptations récurrentes au plan** (notées en cours d'exécution) : nom de package `astro_brain` (le plan référençait `astro_brain_app`), `colors.textPrimary` (pas `colors.text`), `text.hudCaption.copyWith()` plutôt que `fontFamily: 'JetBrainsMono'` inline, `bloc_test seed:` (jamais `..emit()`, `@protected`), helper `_wrap` providant AppBloc + ThemeCubit + AlignmentBloc pour les widget tests qui montent l'AppBar. Spec self-contradiction sur les markers d'axis-bars (prose vs Dart de référence) → différée dans `backlog.md`.

**Couverture restante** : T20 cold-start restore — déjà couvert par `existing ?? await repo.start()` + bloc test "WizardStarted resumes existing session" (le plan défère explicitement le dialog visuel "réutiliser modèle finalisé" à Macro 3 #4). T21 ce point. T22 manual integration checklist (validation matérielle reportée derrière dongle CP2102).

**Tests** : app 144 → 180 verts (+36 entre Hub et fin du wizard), backend 191 → 243 verts (+52 sur les 10 tasks backend). `flutter analyze` clean à chaque commit. Validation matérielle reportée Macro 1 INDI.

**Correction architecturale (fin de session, ADR 2026-05-10)** : revue post-implémentation a remonté que le wizard tel que livré construisait un modèle SVD parallèle ignorant l'interface native Celestron, alors que la migration INDI (ADR 2026-05-01) avait été motivée précisément par l'accès à cette interface. Décision : conserver INDI, repositionner le SVD comme indicateur qualité (RMS/résiduels/outlier) et alimenter le modèle natif du driver à chaque record via `MountService.sync_radec(ra_deg, dec_deg)` (`ON_COORD_SET=SYNC` puis `EQUATORIAL_EOD_COORD = (ra/15, dec)`). Patch livré dans la même session : extension `MountService` Protocol, implémentation `MountIndiAdapter.sync_radec` (`set_switch_one_of_many("SYNC")` + push `EQUATORIAL_EOD_COORD`), `FakeMount.sync_radec` enregistre `(ra_deg, dec_deg)` pour testabilité, wire dans `AlignmentServiceImpl.record()` après l'append `StarRecord`. Tests : 3 nouveaux pour l'adapter (sync arme `SYNC`, push RA en heures + DEC en degrés ; erreur si propriété absente ; no-op si device absent), 2 pour le service (3 syncs ordonnés, pas de sync si idx invalide). Backend 248 verts. Spec amendée + checklist enrichie d'un step 10b (validation native Celestron) + roadmap Macro 1 += `sync_radec`, Macro 3 #3 reformulé en `EQUATORIAL_EOD_COORD` + `ON_COORD_SET=TRACK`.

Plafond journal atteint (6 sessions visibles : 17→22) — la prochaine session déclenchera une archive `2026-05-macro2-setup.md` (Sessions 17-19 candidates).

### Session 21 — UX fixes post-Hub : propagation offline + libellés FR + nav back (2026-05-09)

Suite directe de Session 20 (Hub mergé). Smoke téléphone a remonté 3 frictions UX, corrigées en mode debug-pose-correctif sur main (pas de feature branch — fixes courts, validés un par un).

**Symptômes** : pastille AppBar "BLEU" clignotant en hors-ligne (label = nom de couleur), Setup card RÉSEAU figée verte Pi injoignable, aucune flèche de retour sur les pages enfants.

**Cause racine identifiée au 4ème commit** : `SplashCubit.continueOffline()` ne dispatchait pas `AppStarted`. L'utilisateur cliquant "Continuer offline" depuis le splash quittait l'écran sans jamais activer la souscription SSE. AppBloc restait en `connecting` initial à perpétuité, aucune erreur ne pouvait remonter puisque rien n'écoutait. Les 3 premiers fix étaient nécessaires mais pas suffisants — leçon : **tracer le chemin event end-to-end avant d'optimiser les sous-couches**.

| # | Commit | Fix |
|---|---|---|
| 1 | `9cdd778` | `EventStreamService._scheduleReconnect` propage `_SseConnectionLost` au stream + Setup card RÉSEAU branchée sur `state.connection` (BlocBuilder) + `AstroAppBar` leading back-arrow conditionnel via `Navigator.canPop()`. Test régression `_FailingClient`. |
| 2 | `a114ae8` | `OverallStatus.displayLabel` getter (FR sémantique : OK / EN COURS / ALERTE / ERREUR / INACTIF / INCONNU). `AstroAppBar` utilise `displayLabel` au lieu de `name.toUpperCase()`. |
| 3 | `246a1d9` | `.timeout(5s)` sur le connect SSE initial. `http.Client.send()` Dart n'a pas de timeout par défaut → blocage indéfini possible si DNS résout sans SYN-ACK (mDNS dans le vide, gateway droppant). |
| 4 | `325e2b6` | **Cause racine** : `SplashCubit.continueOffline()` dispatche maintenant `AppStarted`. La souscription SSE démarre, le timeout frappe, l'erreur propage. |

144/144 verts à chaque commit, `flutter analyze` clean. Smoke téléphone confirmé OK utilisateur.

**Roadmap — retrait courses AZ logicielles** : décision prise en fin de session. L'item "Courses AZ min/max (software)" Macro 2 est retiré du train. Sur cette monture il n'y a pas de butée mécanique en azimut, juste un risque de torsion câbles que le cordwrap (Slice D) gère nativement. La contrainte "ne pas faire de tours inutiles" est reportée sur le path planning du GoTo Macro 3 (ligne amendée). ADR daté 2026-05-09 dans `decisions.md`.

**Archive** : Sessions 15+16 (install INDI Pi + backend mount migration) déplacées vers [`journal/archive/2026-05-macro1-indi.md`](journal/archive/2026-05-macro1-indi.md) pour respecter plafond 5-6.

### Session 20 — Hub central, Macro 3 item #1 livré (2026-05-08)

Première étape de la Macro 3. Mode `superpowers:subagent-driven-development` (implementer + spec reviewer + code-reviewer par task). Branche `feat/macro3-hub-central` partie de `de454e4`.

**Décision design** : Hub évolutif (pas anticipateur). Le Hub n'affiche que les features vivantes ; pas de cartes "Coming soon". Chaque feature livrée ajoute sa carte au moment d'arriver. Stratégie validée en brainstorm contre une variante "anticipative" qui aurait pré-affiché Wizard / GoTo / Catalogue grisés.

**Refactors préliminaires** (Tasks 1-4 — commits `826b586` → `22b45b9`)

- Enum `AstroScreen` étendu : ajout `hub`, `manual` (transitionnel), puis `about`. Suppression `home`. Ordre final : `hub, manual, system, setup, about`.
- `features/home/` → `features/manual/` (rename complet : `HomeScreen` → `ManualScreen`, `HomeBloc` → `ManualBloc`, events/states/widgets).
- `features/setup/about/` → `features/about/` : About sort de Setup, devient feature racine accessible directement depuis le Hub. Setup passe de 9 à 8 cartes.
- Tests adaptés à chaque renommage. 31 → 143 verts à chaque étape, `flutter analyze` clean.

**Task 5 — `HubCard`** (commit `bfe759b`) — TDD 3 tests (rendu, tap, primary chevron). Hero icon HugeIcons (28 px) + label JetBrains Mono + hint Inter + chevron Phosphor. Variant `primary` : gradient accent + glow. **Bug plan corrigé en cours d'exécution** : `hugeicons 1.1.6` expose ses icônes comme `static const List<List<dynamic>>` rendues via `HugeIcon(icon: …)`, **pas comme `IconData`**. Plan amendé inline (Tasks 5 et 6) ; tests adaptés à `find.byWidgetPredicate` au lieu de `find.byIcon`.

**Task 6 — `HubScreen`** (commit `4c0b142`) — TDD 7 tests (4 cartes en ordre, primary, header, 4 navigations). `StatelessWidget`, `ListView.separated` de 4 `HubCard`, AstroAppBar(current: hub), header `// ASTRO-BRAIN` + question `Que fait-on ce soir ?`. Adaptations test-side : ajout `BlocProvider<ManualBloc>` au wrap (ManualScreen le réclame via context), remplacement `pumpAndSettle()` par `pump() + pump(400ms)` dans les tests de navigation (les destinations Setup/About ont des Futures async qui ne settlent jamais sous test).

**Code review feedback** (commit `dfcdc1b`) : remplacement d'un `TextStyle(fontSize: 18, …)` inline pour le sous-titre par `Theme.of(context).textTheme.titleMedium?.copyWith(...)` — laisse le design system contrôler la taille et la famille.

**Task 7 — wire root** (commit `72be076`) — `app.dart::_RootRouter.build` retourne `const HubScreen()` au lieu de `const ManualScreen()`. Splash → Hub par défaut.

**Dépendance ajoutée en parenthèse** : `hugeicons: ^1.1.6` pour fournir le vocabulaire astro (telescope, satellite, radar, orbit, constellation…). Convention double set documentée dans `design-system.md` : Phosphor reste pour l'UI utilitaire (chevrons, gear, info), HugeIcons exclusivement pour les hero icons domaine (cartes Hub, splash, headers de feature).

**Validation Android USB** : à faire — pas exécutée par les subagents (validation visuelle reportée à l'utilisateur). Tests automatisés OK : 143/143 verts, `flutter analyze` clean.

## Archives

- [`2026-04-backend-v0.1.md`](journal/archive/2026-04-backend-v0.1.md) — Sessions 1→7 : brainstorm, spec design, monorepo + uv, Tasks 1-17 du plan backend, revue/renforcement, validation physique GPS + compass, décision capteurs ADXL345.
- [`2026-04-frontend-v0.1.md`](journal/archive/2026-04-frontend-v0.1.md) — Sessions 8→10 : démarrage app Flutter (thème + design system), livraison v0.1 (Splash / Home / System, blocs, services REST + SSE, 47 tests), smoke test Moto g54 5G + 4 fixes UX (53 tests).
- [`2026-04-v02-setup-prep.md`](journal/archive/2026-04-v02-setup-prep.md) — Sessions 11→14 : préparation v0.2 Setup — brainstorm v0.2, réorganisation roadmap + arborescence docs en 3 vues, recherche exhaustive du protocole NexStar + assainissement repo, scaffold Flutter + carte #8 Réseau livrée.
- [`2026-05-macro1-indi.md`](journal/archive/2026-05-macro1-indi.md) — Sessions 15→16 : install stack INDI 2.2.0 + driver Celestron AUX sur le Pi (Astroberry Trixie arm64), rebase + merge backend `MountIndiAdapter` + `pyindi-client` sur main (89 tests verts, `nexstarpy` retiré). Smoke test E2E reste bloqué par dongle CP2102.
- [`2026-05-macro2-setup.md`](journal/archive/2026-05-macro2-setup.md) — Sessions 17→19 : Macro 2 Setup Slices INFRA (sqlite `state.db` + repos calibration/limits, 8 tasks INFRA), A capteurs (ADXL345 ×2 + LIS3MDL, refactor `CalibrationBloc` partagé -784 LOC), B (courses ALT) + C (À propos). Items #1 #2 #3 #4 #8 #9 livrés ; Slice D backlash/cordwrap reste bloqué dongle CP2102.
