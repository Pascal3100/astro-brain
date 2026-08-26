# Roadmap

Pas de versions numérotées. Train d'**étapes** atomiques, regroupées en **macro-étapes**. Une étape se déplace ; une macro est "done" quand le télescope reste utilisable end-to-end à la fin.

**Statuts** : ✅ done · 🚧 en cours · 📦 prête · ⛔ bloquée hardware · 🌫 à préciser

> **Maintenance** : ce document est tenu à jour à chaque livraison d'étape (statut + date) et à chaque réorganisation du train. Les changements structurants (ajout/retrait/déplacement entre macros) sont aussi consignés en ADR dans [decisions.md](decisions.md).

---

## Macro 0 — Socle ✅

App Flutter manuelle + tracking + GPS, livrée 2026-04-25. Établit la chaîne `téléphone → FastAPI → monture` et les conventions UI (AppBar template, thème jour/nuit).

- ✅ Joystick D-Pad + tracking sidéral
- ✅ GPS/heure auto au boot, sync vers monture
- ✅ App Flutter native + AppBar template + thème jour/nuit
- ✅ Service systemd, mDNS `astro-brain.local:8000`, override `--dart-define`
- ✅ Backend 64 tests verts, app 53 tests verts, smoke test téléphone (Moto g54 5G)
- 🌫 Passe physique mount-branchée (sections 3 et 7 de `backend/deploy/INTEGRATION_CHECKLIST.md`) — Macro 1 étant validée (pont ESP32, S37), reste à cocher formellement la checklist.

---

## Macro 1 — Migration INDI ✅

Refonte technique du `MountAdapter` pour pivoter de `nexstarpy` vers la stack INDI (`indiserver` + `indi_celestron_aux` + `pyindi-client`). Pas de nouvelle feature côté Flutter — l'API REST/SSE reste identique. Pré-requis aux macros suivantes (backlash, cordwrap, sync RA/Dec, `is_aligned`, `goto_in_progress`).

- ✅ Stack INDI installée sur le Pi (repo Astroberry Trixie arm64) — voir ADR 2026-05-04
- ✅ Backend refactor `MountAdapter` INDI + bus thread-safe (89/89 tests verts)
- ✅ `MountService.sync_radec(ra_deg, dec_deg)` (`ON_COORD_SET=SYNC` + `EQUATORIAL_EOD_COORD`) — livré 2026-05-10 (alimente le modèle natif Celestron pour Macro 3 #2, cf. ADR 2026-05-10)
- ✅ **Smoke test E2E — pivot ESP32, jalons A+B verts : LA MONTURE BOUGE (2026-06-13, S29)** : le RX du dongle CH340 perturbe le bus de façon non découplable passivement (masse seule propre, mais R série 4,7 k insuffisant — S29). **Pivot vers un pont ESP32 WiFi↔bus AUX** (mode « Celestron WiFi » du driver = TCP port 2000, GPIO haute-Z → supprime le défaut CH340). **Jalon A** : firmware pont transparent (`Serial2` 16/17, TCP 2000) flashé via `arduino-cli`, chaîne flash→WiFi→`TCP 192.168.4.1:2000 OPEN`. **Jalon B** : étage **BC547** (0,05 V, S28) piloté par GPIO17, RX GPIO16 via R 3,5 k, raquette débranchée → **rejeu des octets de slew capturés S28 → l'AZM tourne physiquement dans les deux sens sur commande**. ⇒ **blocage matériel S26→S28 levé.** (`GET_VER` reste écho seul ; slew ~0,5 s/commande, le slew continu via half-duplex turnaround est géré par le vrai driver → jalon C.) Reste : jalon C `indi_celestron_aux` Network sur le Pi (prérequis IP stables + ESP32 mode station), jalon D backend série→réseau. Détail : [`../technical/cablage-pont-esp32.html`](../technical/cablage-pont-esp32.html). **ADR pivot ESP32 à acter au jalon C** (déroge à « pas d'Arduino »).
- 🟢 **Round-trip TX validé — la monture RÉPOND (2026-07-01, S35)** : après le fil RX/TX (RX prouvé par comparateur **LM2902** S33), le TX est passé du **BC547 open-collector** (fronts trop lents, moteur muet S33) au **buffer tri-state 74AHCT125** (drive push-pull, 470 Ω série, `/OE` sur GPIO32). **`GET_VER` round-trip OK** : l'azimut `0x10` répond `3b 05 10 0d fe 05 09 d2` (firmware v5.09) → **blocage électrique S26→S33 levé**. Câblage : [`../technical/cablage-interface-aux.html`](../technical/cablage-interface-aux.html).
- 🟢 **Turnaround TX→RX fiabilisé — round-trip 30/30 (2026-07-02, S36)** : la fiabilité ~1/3 de S35 était une **collision de bus** (garde `delayMicroseconds` après `flush()` retenant le buffer piloté HIGH dans la fenêtre de réponse → 1ᵉʳ octet `3b` détruit). Firmware `/OE` (jamais committé en S35, perdu) **reconstruit** dans le repo ; fix = relâcher `/OE` immédiatement après `flush()`. Diagnostic par dump brut (`ECHO_SUPPRESS=0`) → écho 6/6 propre, `3b` absent du brut = framing, pas le drain. **Bus AUX fiable de bout en bout.**
- 🎉 **JALON C VALIDÉ — la monture est pilotée par INDI (2026-07-05, S37)** : OTA bootstrappé (flash WiFi opérationnel, `AUTH` OK). Le driver `indi_celestron_aux` (v1.5) en mode Network (`.200:2000`) **dialogue avec la vraie monture** à travers le pont ESP32 : `CONNECTION._STATE=Ok` (handshake), lecture d'encodeur stable au repos + poll continu, **slew réel bidirectionnel confirmé visuellement** (8x → ~2°/s). **Blocage central S26→S33 totalement levé** ; chaîne `Driver INDI → TCP → ESP32 → 74AHCT125/LM2902 → bus AUX → moteur` opérationnelle. Câblage : [`../technical/cablage-interface-aux.html`](../technical/cablage-interface-aux.html).
- ✅ **END-TO-END validé via le backend (2026-07-05, S37)** : `POST /slew` (path de l'app) → FastAPI → pyindi-client → indiserver → pont ESP32 → monture **fait tourner la vraie monture** (AZ 9,3°→11,3° en 2 s, `mount:ready`). Le test a démasqué 2 bugs adapter (masqués par un `FakeIndiClient` trop permissif), corrigés en TDD : (a) accès éléments INDI (`findWidgetByName` + états switch entiers `ISS_ON/OFF` + vrais noms `1x`…`8x`/`ABORT` — corrige aussi `set_time`/`set_location` S27) ; (b) device pyindi caché trop tôt = handle périmé → re-fetch à chaque opération. **ADR pivot ESP32** acté (2026-07-05).
- ✅ Fix backend `set_time`/`set_location` (`TypeError __getitem__`) — corrigé S37 (même cause que le bug d'accès aux éléments INDI : subscript chaîne → `findWidgetByName`)
- 🌫 Fork upstream patch backlash mount-axis (`MC_*_BACKLASH`, ~70 lignes C++) — différable, le driver fonctionne sans. **Suivi désormais en Macro 5** (le backlash mount-side y est rattaché, ADR 2026-07-08).

- 🚧 **Pont ESP32 relié au Pi en série filaire — retrait du WiFi** (ADR 2026-08-26) : les deux cartes ont toujours été dans le même boîtier sur la partie fixe du trépied ; le lien WiFi reliait deux voisines de 10 cm en passant par la box. Le pont garde son interface électrique (74AHCT125 / LM2902), son retournement `/OE` et sa suppression d'écho ; il perd son transport TCP au profit d'`UART0` (`/dev/ttyAMA0`, 19200 8N2), libéré par le retrait du DroTek. Gains : provisionnement hors domicile réglé à la racine, détection d'erreur restaurée (`serialReadResponse()` renvoie `false`, là où `tcpReadResponse()` renvoyait toujours `true`), une dépendance réseau quittant le chemin critique, défaut #5 (ARP Pi→pont) sans objet. Plan : [`2026-08-26-pont-esp32-serie.md`](../superpowers/plans/2026-08-26-pont-esp32-serie.md).

*Done quand* : Macro 0 reste fonctionnelle, monture pilotée via INDI, `nexstarpy` retiré du backend.

Spec : [`docs/superpowers/specs/2026-05-01-mount-indi-design.md`](../superpowers/specs/2026-05-01-mount-indi-design.md). Onboarding : [`docs/technical/indi-reference.md`](../technical/indi-reference.md).

---

## Macro 2 — Setup ✅

Page Setup unifiée + toutes les calibrations et configurations préalables à un alignement sérieux. Pré-requis : Macro 1. **Done 2026-07-08.**

- ✅ Page Setup unifiée (hub des cards) — scaffold Session 14
- ✅ Slice INFRA backend (sqlite `state.db` + repos calibration/limits) — livré 2026-05-05 (Session 17)
- ~~✅ Calibration ADXL345 monture (item #1 — niveau monture, planéité absolue) — livré 2026-05-07 (Session 18)~~ (capteur retiré — voir ADR 2026-07-17)
- ~~✅ Calibration compass LIS3MDL (item #2 — soft-iron offsets) — livré 2026-05-07 (Session 18)~~ (module DroTek retiré — voir ADR 2026-08-26)
- ~~✅ Calibration ADXL345 tube (item #3 — zéro ALT, tube horizontal) — livré 2026-05-07 (Session 18)~~ (capteur retiré — voir ADR 2026-07-17)
- ~~✅ Courses ALT min/max (alimentées par ADXL345 tube, anti-collision) — livré 2026-05-07 (Session 19)~~ (capteur retiré — voir ADR 2026-07-17)
- ➡️ ~~Backlash compensation ALT + AZ (mount-side)~~ **déplacé en Macro 5** (2026-07-08) : le driver `indi-celestronaux` v1.5 n'expose pas `MOUNT_AXIS_BACKLASH` → nécessite un fork/patch C++ ; valeur réelle seulement en imaging/guidage. Cartes Setup 5/6 marquées « Reporté — Macro 5 ». Cf. ADR 2026-07-08.
- ✅ Network/IP config — livré Session 14 (carte #8 Setup)
- ✅ À propos (versions, IP, uptime) — livré 2026-05-07 (Session 19)

*Done quand* : ~~toutes les calibrations/courses/configs sont accessibles depuis l'app, valeurs persistées, et permettent de tenter un alignement avec confiance.~~ **Atteint 2026-07-08** : calibration compass, réseau et à-propos accessibles depuis l'app + persistés. (Niveau monture, zéro ALT et courses ALT — livrés à date puis **retirés le 2026-07-17** ; calibration compass **retirée le 2026-08-26** avec le module DroTek — voir ADRs — n'entrent plus dans ce critère. Il reste réseau et à-propos.) Le backlash mount-side est reporté en Macro 5 (dépend d'un fork driver, sans valeur avant l'imaging).

Spec validée : [`docs/superpowers/specs/2026-05-01-astro-brain-v02-setup-design.md`](../superpowers/specs/2026-05-01-astro-brain-v02-setup-design.md). Plan : [`docs/superpowers/plans/2026-05-04-v02-setup-implementation.md`](../superpowers/plans/2026-05-04-v02-setup-implementation.md).

Optionnels à arbitrer plus tard : slew rates personnalisés, cone error, PEC.

---

## Macro 3 — Mise en station + GoTo basique

Première mise en station effective, GoTo réel, catalogue d'objets brillants. Hub central remplace le HomeScreen comme landing post-Splash. Pré-requis : Macro 2.

- ✅ Hub central (landing post-Splash, 4 cartes Manuel / Setup / Status / À propos) — livré 2026-05-08 (Session 20)
- 🚧 Wizard alignement 3 étoiles (1ʳᵉ étoile pointée à la main, #2/#3 pré-pointées par le modèle 1 puis 2 étoiles ; validation auto via résiduel SVD < ~1°, fallback manuel) — software livré 2026-05-10 (Session 22, backend + Flutter, 180 tests app + tests backend), validation matérielle à valider sur matériel (liaison OK depuis S37). **Reformulé le 2026-08-26** : plus « assisté capteurs (compass + GPS) » — le module DroTek est retiré (ADR), la position vient du téléphone ou du site d'observation persisté, et le cap magnétique n'a jamais eu de consommateur puisque la 1ʳᵉ étoile est manuelle
- 🚧 GoTo réel sur monture alignée (`EQUATORIAL_EOD_COORD` + `ON_COORD_SET=TRACK`, slew + tracking sidéral natif) — software livré 2026-06-01 (Session 24 : `MountService.goto_radec`, garde `is_aligned`, complétion BUSY→OK via `updateProperty`, `goto_in_progress` exposé via SSE, abort réutilise `/stop`) ; **contrat de route passé de `{ra_deg, dec_deg, target_name}` à `{id, confirm_solar}` avec Oracle SP2** (résolution par id côté Pi, cf. fil Oracle) ; **slew réel validé sur les deux axes (2026-08-23, S54)** — reste le GoTo sur monture alignée
- 🚧 Catalogue minimal backend : tranche A (stars étendues IAU CSN cap mag 3, 140 entrées) livrée 2026-05-10 ; enrichissement visibilité `visible_now` (alt/az courants via `_ephemeris` + `VisibilityEnricher`, dégradation gracieuse sans fix GPS) livré 2026-06-01 (Session 24) — tranches Messier + planètes (skyfield) à suivre
- 🚧 Page Catalogue minimal (recherche + filtres magnitude/visible-now, détail bottom sheet, GoTo + slew bar, bandeau non-aligné) — software livré 2026-06-01 (Session 24, Flutter) ; slew réel **validé (S54)** ; validation visuelle Android à faire
- 🚧 Aide identification étoile dans sa constellation (rattachée #2 wizard) : schéma au trait orienté ciel dans le wizard (`ConstellationChart`, asset `constellation_figures.json` 23 figures), navigateur par constellation visible au swap, bandeau « Position GPS requise » dans la carte ALIGNER du Hub ; **chaîne de position revue : fix GPS Pi → GPS téléphone (geolocator) → sinon pas de wizard (fallback Paris supprimé)** — devient *site d'observation persisté → GPS téléphone → sinon pas de wizard* avec le retrait du DroTek (ADR 2026-08-26) — software livré 2026-06-05 (Session 25, 342 tests backend + 226 tests app) ; validation matérielle à valider sur matériel (liaison OK depuis S37)

- 🌫 **Pré-pointage auto des étoiles #2/#3 — conçu, jamais câblé** : aucun appel `goto`/`slew` dans `app/lib/features/alignment/`, et `routes/goto.py` refuse par `409 not_aligned` (garde `is_aligned`, vraie seulement après `finalize()`). Devenu porteur depuis le retrait du DroTek — c'est la seule aide au pointage restante avant Macro 5. **Question de conception ouverte avant tout code** (goto sur modèle 1 point vs chemin de pré-pointage borné, et anti-collision ALT jamais reprise depuis l'ADR 2026-07-17) → spec + plan dédiés, cf. [backlog](backlog.md)

*Done quand* : on peut faire une mise en station 3 étoiles puis pointer fiablement Messier/planètes/étoiles brillantes en session réelle.

---

## Macro 4 — Catalogue intelligent (parité raquette Celestron)

Extension du catalogue à NGC/IC + intégration des caractéristiques du tube pour filtrer la visibilité. À la fin de cette macro, l'app couvre tout ce que fait la raquette Celestron. Pré-requis : Macro 3.

- 📦 Setup tube (focale, diamètre, obstruction)
- 📦 Catalogue NGC/IC complet
- 📦 Filtrage visibilité par tube (focale → champ, diamètre → magnitude limite, obstruction → contraste)

*Done quand* : la raquette HC peut être laissée dans le tiroir.

---

## Macro 5 — Caméras + plate solving

Stack INDI étendue aux caméras, pipeline preview, plate solving local. Première fois qu'on voit une image dans l'app. Pré-requis : Macro 4 (ou parallélisable une fois Macro 2 livrée si on accepte de différer la parité raquette).

- 📦 Stack INDI drivers caméras (T7C imageur, Orion StarShoot Autoguider sur SV165)
- 📦 Configuration caméras (3 cams + lunette guide : pixel size, focale, gain, bin)
- 📦 Pipeline FITS → auto-stretch (MTF/STF) → debayer → downsample → JPEG (Pi-side)
- 📦 Endpoint preview (`GET /preview/{cam}/latest.jpg`) + MJPEG live
- 📦 Machine d'état backend `idle / focusing / guiding / imaging` (verrou par caméra)
- 📦 Astrometry.net local + endpoint `/solve`
- 📦 Page Framing (snap + overlay coords centre + orientation capteur)
- 📦 Backlash mount-side ALT/AZ (déplacé de Macro 2, 2026-07-08) : **prérequis fork driver** `indi_celestron_aux` (`MC_*_BACKLASH` → propriété `MOUNT_AXIS_BACKLASH`, ~70 lignes C++, absent en v1.5) ; puis REST GET/PUT + persistance + écran Flutter + bloc. Adapter backend `get/set_backlash` + 5 tests **déjà écrits** (attendent la propriété driver). Cf. ADR 2026-07-08.

*Done quand* : snap → image lisible dans l'app → plate solve renvoie coordonnées exactes du centre.

---

## Macro 6 — Focus + mise en station complète

Aides à la mise au point fines + wizard de mise en station orchestrant tout le pipeline (niveau, cap, alignement) avec option plate solve. Pré-requis : Macro 5.

- 📦 Page Focus live (loop court 1–3 s, zoom ROI, star picking tactile)
- 📦 HFR/FWHM côté Pi → courbe live SSE
- 🌫 Optionnel : analyseur masque Bahtinov
- 📦 Wizard mise en station complet (orchestre niveau + cap + alignement, ergonomie nuit soignée)
- 📦 Option alignement par plate solve (alternative au 3-star : centrage automatique après snap + solve)
- 📦 Assistant alignement optique (chercheur ↔ guide ↔ tube principal, version chiffrée arcmin via plate solve)

*Done quand* : une session est préparée end-to-end depuis l'app, à la mise au point près, sans la raquette ni intervention oculaire.

---

## Macro 7 — Astrophoto

Boucle de guidage temps-réel + séquenceur autonome. Pré-requis : Macro 6.

- 📦 Intégration PHD2 headless + proxy via FastAPI (start/stop/settings, events SSE)
- 📦 Page Guidage (graphe RA/DEC live, calibration, agressivité)
- 📦 Séquenceur (plan de pose, progression)
- 📦 Dithering
- 📦 Autofocus périodique

*Done quand* : nuit d'astrophoto autonome, depuis l'app, du framing au stack final.

---

## Fils transverses

Pas dans le train ; courent en continu et se densifient avec les macros.

- **Safety** : arrêt d'urgence soft (chemin de commande prioritaire), logs persistants journald structurés. À amorcer dès Macro 2.
- **Mode nuit rouge** : généralisé sur tous les écrans à mesure de leur livraison.
- **Indicateur global d'état** : pastille `overall` dans l'AppBar, déjà amorcée — étendue à `idle/focusing/guiding/imaging` dès Macro 5.
- **Ops** : `deploy.sh` SSH → `git pull && systemctl restart`, build APK Flutter. À enrichir au fil de l'eau.
- **Oracle / Éphémères** : plan de données de référence **autonome du Pi** — module `oracle/` généré par GitHub Actions (skyfield + MPC/OpenNGC/IAU-CSN + `de421.bsp`) → `reference.sqlite`, consommé par l'app et le Pi (cache local, hors ligne). ✅ **Tranche 1 producteur livrée 2026-07-24** (comètes, schéma v1, release rolling `almanac-latest` par CI hebdo — vérifié vert 2026-08-08). ✅ **SP1 base commune livrée 2026-08-09** (`feat/oracle-base-commune`) : **schéma v2 unifié, source unique du catalogue complet** — toutes les familles (comètes, planètes, Lune, Soleil, deep-sky Messier/NGC/IC, étoiles nommées), **tube-agnostique, sans filtrage producteur** ; tables `objects`/`fixed_object`/`ephemeris`/`comet_elements` ; RA/Dec apparentes of-date (JNow) calculées au build ; revue finale Opus PASS, 37 tests verts. ✅ **SP2 consommateur backend livré 2026-08-10** (`oracle-sp2-backend`, mergé `main`) : le Pi devient consommateur read-only de `reference.sqlite` v2 — download/vérif (sha256 + garde schéma ≤ 2)/swap atomique online-first non-bloquant, cache offline conservé ; catalogue = source unique `reference.sqlite` (seeds + table `catalog_objects` supprimés, migration `_004`) ; **GoTo par `id`** (vocabulaire partagé app↔Pi) avec gardes reference/stale/solar. 14 tâches SDD + revue finale Opus PASS, 324 tests verts. Minors différés au [backlog](backlog.md) (M-3 format `sample_utc`, M-6 test e2e route). ✅ **SP3-A consommateur app en ligne livré 2026-08-10** (`sp3a-app-contract`, mergé `main`) : l'app Flutter devient consommateur REST **en ligne** correct du contrat SP2 — `ApiException.detail`, DTO catalogue v2 (`angular_size_arcmin`/`messier`/`ngc_ic`/`illumination`/`ephemeris_stale`), **GoTo par `id`** non destructif (échec surfacé via `gotoOutcome`→SnackBar, jamais d'écrasement de la liste chargée), flux **confirmation solaire piloté serveur** (`detail=solar_ack_required` → dialog → re-dispatch `confirm_solar`), `ReferenceRepository` + UI statut/almanach (bandeau + carte Setup + resync), filtres famille (`kind`) + Messier. 7 tâches SDD + revue finale Opus « ready to merge » (0 Critical/Important), 234 tests app verts. Minors différés au [backlog](backlog.md). ✅ **SP3-B cache local hors ligne livré 2026-08-11** (`oracle-sp3b-local-catalogue`) : l'app **lit le catalogue et calcule la visibilité (alt/az) localement** depuis sa copie de `reference.sqlite` (téléchargée de la release `almanac-latest`) → **catalogue navigable Pi éteint**. Acquisition `lib/oracle_cache/` (manifest, store `path_provider`+sha256, sync non-bloquant online-first, DI `wiring.dart`) + moteur `lib/features/catalogue/local/` (interpolation éphéméride, projection RA/Dec→alt/az, DB read-only, providers fixe/éphémère, façade, visibilité) ; les deux repositories réécrits en interne (signatures publiques préservées). **GoTo reste EN LIGNE** (l'app envoie `{id, confirm_solar}`, le Pi résout sur sa propre copie). 12 tâches SDD + revue finale Opus (0 blocker ; 1 fix contrat sync non-throwing) + 268 tests app verts. Minors différés au [backlog](backlog.md). ✅ **SP3-B bis nettoyage backend livré 2026-08-11** (`oracle-sp3b-bis-drop-catalog-endpoint`) : endpoint `GET /catalog/objects` (plus aucun consommateur) + cascade code mort (`VisibilityEnricher`, `list_all`/`list_objects`, `CatalogFilter`, alt/az) retirés côté Pi ; chemin GoTo (`resolve` par `id` → `get_object`) intact. Branche légère, 298 tests backend verts. **Reste : SP3-C/D = night planner offline + notifs locales** (planif Pi éteint, GoTo par `id`), puis événements calculés (conjonctions/oppositions/éclipses/showers) puis appulses. Discriminant oculaire/photo couplé **Macro 4** (seuil visuel via Setup tube) / **Macro 5** (seuil photo via Setup caméras). Notifs locales d'abord, FCM différé. Voir [ADR 2026-07-24](decisions.md) + [spec base commune](../superpowers/specs/2026-08-09-oracle-base-commune-design.md) + [spec SP2](../superpowers/specs/2026-08-09-oracle-sp2-backend-design.md) + [plan SP2](../superpowers/plans/2026-08-09-oracle-sp2-backend.md).
- **Night planner offline** : s'appuie désormais sur le **plan de référence Oracle** (bundle `reference.sqlite` local, dispo Pi éteint). Le pattern *snapshot/cache-depuis-le-Pi* est **supersédé** (ADR 2026-07-24 : un snapshot exige le Pi allumé, or on planifie Pi éteint). À cliper sur la macro qui héberge le planner.

---

## Notes

Cette roadmap remplace celle versionnée v0.1–v0.7 (abandonnée 2026-05-05, voir ADR du même jour). Le contenu est conservé, simplement réorganisé en macro-étapes ordonnables. Les commits, journaux et ADRs antérieurs continuent de référencer les noms `v0.X` historiquement — c'est normal.
