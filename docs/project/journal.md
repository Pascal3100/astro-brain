# Journal de sessions — Astro-Brain DIY

Fil rouge du projet. **Plafond : 5-6 sessions max ici** ; au-delà, on archive par milestone dans `journal/archive/`.

## État du projet

**Roadmap restructurée 2026-05-05** : abandon du versioning v0.X, passage à un train de macro-étapes (voir [`roadmap.md`](roadmap.md) + ADR du 2026-05-05). Les sessions antérieures continuent de référencer `v0.X` ; correspondance : v0.1 = Macro 0 Socle, v0.2 = Macro 2 Setup, v0.3 = Macro 3 Mise en station, v0.4 = Macro 4 Catalogue, v0.5 = Macro 5 Caméras, v0.6 = Macro 6 Focus + MES, v0.7 = Macro 7 Astrophoto. La migration INDI devient sa propre Macro 1 (technique).

**Macro 0 — Socle ✅** (livré 2026-04-25) : parité joystick + tracking via app Flutter native. Backend **89 tests** verts (64 socle + 25 migration INDI), app 53 tests. Smoke téléphone Moto g54 5G. Validation physique GPS + compass I2C + network + system. **Monture désormais pilotée end-to-end** (pont ESP32, Macro 1 bouclée S37) ; la passe physique mount-branchée de l'`INTEGRATION_CHECKLIST.md` (sections 3 et 7) reste à cocher formellement.

**Macro 1 — Migration INDI ✅** (bouclée 2026-07-05, S37) : `MountAdapter` `nexstarpy` → stack INDI (`indiserver` + `indi_celestron_aux` 1.5 + `pyindi-client`), `nexstarpy` retiré. La liaison Pi↔monture — bloquée ~10 sessions (S26→S33) par le bus AUX single-wire — a été résolue par un **pont ESP32** (WiFi↔TCP 2000) + interface RX LM2902 / TX 74AHCT125 ([ADR 2026-07-05](decisions.md)). Chaîne `app REST → FastAPI → pyindi-client → indiserver → pont ESP32 → bus AUX → moteur` **prouvée end-to-end** (`POST /slew` fait tourner la vraie monture). Détail archivé : [S26→S33](journal/archive/2026-06-bus-aux.md) + [S34→S37](journal/archive/2026-07-macro1-liaison.md). Reconnexion auto + manuelle ajoutées et validées (S38→S39, archivées [S38→S41](journal/archive/2026-07-deploy-reconnexion.md)).

**Macro 2 — Setup ✅** (done 2026-07-08) :
- ✅ Carte #8 RÉSEAU livrée (Session 14).
- ✅ Slice INFRA livré (Session 17, 8 commits, +29 tests) — sqlite `state.db` + repos calibration/limits.
- ✅ **Slice A capteurs livré** (Session 18, 2026-05-07) : items #1 niveau monture, #2 compass LIS3MDL, #3 zéro ALT. Fixes review v0.2 (B1, B2, I1-I7, N1-N10) + refactor I8 (`CalibrationBloc` partagé entre les 3 capteurs, -784 LOC). Tests : 178 backend + 115 frontend.
- ✅ **Slice B Courses ALT livré** (Session 19, 2026-05-07) : item #4. Backend `/limits/alt` GET/PUT + écran Flutter capture ALT_min/max via `TiltStreamService`. Tests : 183 backend + 130 frontend.
- ✅ **Slice C About livré** (Session 19, 2026-05-07) : item #9. Backend `GET /about` (versions, IP/SSID, uptime, started_at) + écran Flutter read-only avec bouton RAFRAÎCHIR. Tests : 191 backend + 133 frontend.
- ➡️ **Backlash mount-side déplacé en Macro 5** (Session 41, 2026-07-08) : le driver `indi-celestronaux` v1.5 n'expose pas `MOUNT_AXIS_BACKLASH` → nécessite un fork/patch C++ ; valeur réelle en imaging seulement. Macro 2 déclarée **done** sans lui. Cf. ADR 2026-07-08.
- ➡️ **Retrait des 2× ADXL345 + feature Courses ALT** (Session 42, 2026-07-17) : items niveau monture (#1), zéro ALT (#3) et Courses ALT (#4) ci-dessus **retirés** (capteurs jamais installés physiquement, hors chemin de pointage depuis l'ADR 2026-05-10, garde-fou ALT jamais enforcé). Compass LIS3MDL (#2) conservé, désormais en heading non tilt-compensé. Cf. ADR 2026-07-17.

**Macro 3 — Mise en station + GoTo basique 🚧** :
- ✅ Item #1 Hub central (Session 20).
- 🚧 Item #2 Wizard alignement 3 étoiles : implémentation software complète (backend + Flutter, 22 tasks plan, Session 22). Validation matérielle à faire (liaison monture OK depuis Macro 1 / S37) — **prochain vrai jalon**.
- 🚧 Item #3 GoTo réel + #5 Page Catalogue : software livré (backend + Flutter, 19 tasks plan, Session 24). Validation matérielle (slew réel) à faire (liaison OK depuis S37).
- 🚧 Item #4 Catalogue : tranche A stars (Session 23) + enrichissement visibilité `visible_now` (Session 24). Messier/planètes à suivre.
- 🚧 Aide étoile/constellation (rattachée #2 wizard) : `ConstellationChart` au trait + navigateur par constellation + chaîne de position fix Pi → téléphone → sinon pas de wizard (fallback Paris supprimé) — software livré Session 25.

**Fil transverse Oracle — plan de données de référence 🚧** (hors train de macros, [ADR 2026-07-24](decisions.md)) : `reference.sqlite` généré en CI (release rolling `almanac-latest`), consommé par le backend et l'app en cache local hors ligne. **Livré S43→S47** (archivé [`2026-08-oracle.md`](journal/archive/2026-08-oracle.md)) : producteur + CI hebdo (SP1), schéma v2 source unique toutes familles, backend consommateur id-only (SP2), app en ligne (SP3-A), **cache local hors ligne → catalogue navigable Pi éteint** (SP3-B) + nettoyage endpoint backend mort (SP3-B bis). **Reste : SP3-C/D** = night planner offline + notifs locales, puis événements calculés (conjonctions/oppositions/éclipses/showers), puis appulses. **Validation device manuelle en attente** (APK release : 1er lancement almanach, catalogue Pi éteint, GoTo Pi allumé).

**Doc tree** : nouvelle arborescence `docs/INDEX.md` → 3 vues (`technical/`, `project/`, `product/`). Petits docs ciblés, navigation par liens. Voir Session 12.

## Session en cours

_Toutes les sessions livrées sont archivées (voir plus bas). La prochaine session — **SP3-C, night planner offline** — s'ouvre ici._

## Archives

- [`2026-04-backend-v0.1.md`](journal/archive/2026-04-backend-v0.1.md) — Sessions 1→7 : brainstorm, spec design, monorepo + uv, Tasks 1-17 du plan backend, revue/renforcement, validation physique GPS + compass, décision capteurs ADXL345.
- [`2026-04-frontend-v0.1.md`](journal/archive/2026-04-frontend-v0.1.md) — Sessions 8→10 : démarrage app Flutter (thème + design system), livraison v0.1 (Splash / Home / System, blocs, services REST + SSE, 47 tests), smoke test Moto g54 5G + 4 fixes UX (53 tests).
- [`2026-04-v02-setup-prep.md`](journal/archive/2026-04-v02-setup-prep.md) — Sessions 11→14 : préparation v0.2 Setup — brainstorm v0.2, réorganisation roadmap + arborescence docs en 3 vues, recherche exhaustive du protocole NexStar + assainissement repo, scaffold Flutter + carte #8 Réseau livrée.
- [`2026-05-macro1-indi.md`](journal/archive/2026-05-macro1-indi.md) — Sessions 15→16 : install stack INDI 2.2.0 + driver Celestron AUX sur le Pi (Astroberry Trixie arm64), rebase + merge backend `MountIndiAdapter` + `pyindi-client` sur main (89 tests verts, `nexstarpy` retiré). Smoke test E2E reste bloqué par dongle CP2102.
- [`2026-05-macro2-setup.md`](journal/archive/2026-05-macro2-setup.md) — Sessions 17→19 : Macro 2 Setup Slices INFRA (sqlite `state.db` + repos calibration/limits, 8 tasks INFRA), A capteurs (ADXL345 ×2 + LIS3MDL, refactor `CalibrationBloc` partagé -784 LOC), B (courses ALT) + C (À propos). Items #1 #2 #3 #4 #8 #9 livrés ; Slice D backlash/cordwrap reste bloqué dongle CP2102.
- [`2026-05-macro3-software.md`](journal/archive/2026-05-macro3-software.md) — Sessions 20→25 : Macro 3 tranche logicielle — Hub central (#1), wizard alignement 3 étoiles (#2, modèle natif Celestron via `sync_radec`), GoTo réel + page Catalogue (#3/#5), catalogue backend stars IAU CSN (#4 tranche A), aide étoile/constellation + chaîne de position fix Pi→téléphone. Validation matérielle de tout reportée derrière la liaison monture (Macro 1, fil S26+).
- [`2026-06-bus-aux.md`](journal/archive/2026-06-bus-aux.md) — Sessions 26→33 : fil matériel liaison monture (Macro 1), bring-up — identification du bus AUX NexStar SLT, diagnostic single-wire (diode 1N4007 → 0,97 V, puis 2× BC547 → 0,05 V), **cause racine ÉLECTRIQUE prouvée** (tap pas haute-Z déforme la ligne, diodes de clamp GPIO 3,3 V vs bus 4,4 V), **pivot ESP32** (jalons A+B verts, la monture bouge via le pont TCP), étage RX HEF4093BP prouvé de bout en bout (S31-S32) + perturbation du bus résolue (Rpu retiré), RX comparateur LM2902 prouvée + TX round-trip tranché → 74HC125 (S33).
- [`2026-07-macro1-liaison.md`](journal/archive/2026-07-macro1-liaison.md) — Sessions 34→37 : fil liaison monture (Macro 1), 2ᵉ moitié — refonte des schémas de câblage HTML + pivot TX 74AHCT125 acté en doc (S34), **hardware AUX validé, le moteur répond** (round-trip TX via 74AHCT125/LM2902, S35), turnaround TX→RX résolu (round-trip 30/30, S36), OTA bootstrappé + **JALON C : la monture est pilotée par INDI, end-to-end via le backend REST — Macro 1 bouclée** (S37).
- [`2026-07-deploy-reconnexion.md`](journal/archive/2026-07-deploy-reconnexion.md) — Sessions 38→41 : post-Macro 1, fiabilisation du chemin `app → backend → driver` et refermeture Macro 2 — cause racine « mode manuel muet » (driver non reconnecté) + fix auto-connexion (S38), déploiement + validation matérielle auto-connexion boot/reconnexion (S39), app release muette = permission `INTERNET` manquante (S40), **Macro 2 refermée** (backlash mount-side différé en Macro 5, S41).
- [`2026-07-adxl-retrait.md`](journal/archive/2026-07-adxl-retrait.md) — Session 42 : retrait des 2× ADXL345 + feature Courses ALT (capteurs jamais installés, hors chemin de pointage depuis l'ADR 2026-05-10) ; compass LIS3MDL conservé en heading non tilt-compensé ; ADR 2026-07-17.
- [`2026-08-oracle.md`](journal/archive/2026-08-oracle.md) — Sessions 43→47 : fil transverse Oracle (plan de données de référence autonome du Pi) — producteur `oracle/` + CI hebdo comètes (SP1, S43), schéma v2 source unique toutes familles (S44), backend consommateur id-only (SP2, S45), app en ligne contrat SP2 (SP3-A, S46), cache local hors ligne → catalogue navigable Pi éteint (SP3-B) + nettoyage endpoint mort (SP3-B bis, S47).
