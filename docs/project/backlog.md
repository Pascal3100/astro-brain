# Backlog — Astro-Brain

Réflexions transverses et idées à creuser pour les macros à venir. Rien ici n'est figé en spec ; l'objectif est de capturer les pistes pour ne pas les perdre et pouvoir les arbitrer plus tard.

Quand un sujet devient prêt à être conçu, il migre vers un spec dans `docs/superpowers/specs/`. La roadmap canonique (train de macros) est dans [roadmap.md](roadmap.md).

## Cartographie des pages Flutter par macro-étape

Vue d'ensemble pour éviter la dispersion au fil des specs.

**Macro 0 — Socle** (livré)
- *Dashboard / Contrôle* — joystick, tracking on/off, état monture, GPS/heure, stop d'urgence
- *Settings app* — URL backend, thème jour/nuit

**Macro 2 — Setup**
- *Page Setup* (hub des cards) — scaffold déjà en place
- *Calibration compass*, *Backlash*, *Network/IP* (livré), *À propos* (niveau monture, calibrations ADXL345 ×2 et courses ALT/AZ retirés le 2026-07-17, voir [ADR](decisions.md))

**Macro 3 — Mise en station + GoTo basique**
- *Hub central* — agrégateur post-Splash
- *Wizard alignement 3 étoiles* — exploite GPS + compass + niveau pour pré-pointer
- *Catalogue minimal* — Messier + planètes + étoiles brillantes, recherche/sélection + GoTo
- Enrichissement de l'AppBar avec l'état d'alignement

**Macro 4 — Catalogue intelligent** (parité raquette atteinte ici)
- *Setup tube* — focale, diamètre, obstruction (prérequis du filtrage)
- *Catalogue complet* — NGC/IC + filtrage visuel selon le tube

**Macro 5 — Caméras + plate solving**
- *Configuration caméras* — 3 cams + lunette guide (pixel size, focale, gain, bin)
- *Framing / Plate solve* — snap, résultat coordonnées/orientation capteur overlay

**Macro 6 — Focus + mise en station complète**
- *Focus* — live loop, zoom ROI, HFR/FWHM, histogramme, optionnel Bahtinov
- *Mise en station* (wizard complet) — niveau, cap nord, alignement assisté par plate solve
- *Assistant alignement optique* (chercheur ↔ guide ↔ tube)

**Macro 7 — Astrophoto**
- *Guidage* — graphe RA/DEC live, calibration PHD2, agressivité
- *Séquenceur* — plan de pose, dithering, progression, autofocus périodique

**Transverse (tout du long)**
- Overlay mode nuit rouge
- Indicateur global d'état (connecté Pi + mode actif : idle/focus/guide/image), bloque les actions incompatibles
- *Oracle / Éphémères* — liste comètes + événements observables, notifs locales, alimenté par le plan de référence autonome (`reference.sqlite`, module `oracle/`). Fil transverse, tranche 1 = infra + comètes (voir [ADR 2026-07-24](decisions.md))

## Page "Réglages techniques monture"

Paramétrage persistant côté Pi, exposé par l'app. La majorité atterrit dans la **Macro 2 — Setup** (courses, backlash). Les caractéristiques tube atterrissent dans **Macro 4** car elles conditionnent le filtrage catalogue.

- **Courses min/max AZ** — safety pour éviter la torsion des câbles ; soft via position monture, pas de capteur dédié. **La monture sait déjà le faire nativement** : le sniff du 2026-08-27 montre la raquette armer `MC_ENABLE_CORDWRAP` + `MC_SET_CORDWRAP_POS 0` à la validation de l'alignement, et `indi_celestron_aux` expose la fonction (`CORDWRAP` / `CORDWRAP_POS` / `CW_BASE`) — **arbitré le 2026-08-27 : on délègue à la monture**, pas de garde-fou soft en doublon ([ADR](decisions.md)). L'item se replie donc sur l'étape cordwrap de [Macro 3](roadmap.md). (Le volet **ALT** — anti-collision tube/trépied, alimenté par l'ADXL345 tube — a été **retiré le 2026-07-17** ; repoussé en Macro 3 via la position monture rapportée par le driver, voir [ADR](decisions.md).)
- **Caractéristiques du tube** (focale, diamètre, obstruction) — prérequis pour filtrage catalogue (Macro 4) et calculs FOV astrophoto (Macro 5).
- **Compensation de backlash** — améliore tracking et GoTo (Macro 2).
- **TODO : auditer la raquette Celestron** — passer en revue tous les menus/réglages techniques exposés par le hand controller (backlash, anti-backlash, cone error, PEC, filter limits, custom slew rates, etc.) pour identifier ce qu'il faut exposer/récupérer côté app. À trier en deux colonnes ([ADR 2026-08-27](decisions.md)) : **ce que le driver expose déjà** (à câbler) et **ce qu'il faudrait porter en amont** (à chiffrer, comme le backlash). **Amorcé le 2026-08-27** : le sniff passif du bus AUX (`hardware/aux-bridge/auxsniff.py`) donne la méthode — on lit ce que la raquette *fait* au lieu de lire ce qu'elle *affiche*. Premier passage (boot + alignement rapide) → suivi et cordwrap, cf. journal S57. Reste à sniffer les menus de réglage eux-mêmes.

## Configuration des caméras (Macro 5)

Trois caméras dans le setup final, chacune avec ses paramètres propres :

- **Imageur principal** (T7C) : taille pixel, résolution, gain/offset, binning, temps d'expo par défaut
- **Caméra de guidage** (Orion StarShoot Autoguider) : taille pixel, résolution, agressivité/min-move du guidage
- **Plate solving** (même caméra que le guidage en pratique, sur la SV165) : résolution, échelle attendue (arcsec/pixel)
- **Lunette guide** (SV165) : focale — combinée au pixel size de la caméra guide → échelle d'image, indispensable pour calibrer le plate solver et le guideur

Ces réglages sont un prérequis direct du plate solving (Macro 5) — à spécifier dans le spec correspondant. Note : les caractéristiques du **tube** (focale, diamètre, obstruction) sortent plus tôt, en Macro 4, car elles conditionnent le filtrage du catalogue intelligent.

## Stack caméras & guidage : Flutter télécommande + INDI/PHD2 headless (Macros 5 / 7)

Décision d'archi à valider quand on attaquera le plate solving (Macro 5) puis l'astrophoto (Macro 7) : **ne pas réimplémenter le guiding/contrôle caméra dans Flutter**, orchestrer des outils matures côté Pi.

- **INDI server** sur le Pi : standard de l'écosystème astro Linux, drivers unifiés caméras (T7C, StarShoot) + monture. Tourne en headless.
- **PHD2 headless** (ou lin_guider) sur le Pi pour la boucle de guidage temps-réel (détection étoile, PID, dithering, calibration). PHD2 expose une API serveur (JSON-RPC sur TCP) → le backend FastAPI peut piloter start/stop/settings et relayer les events vers l'app.
- **Astrometry.net** local pour le plate solving, prévu en Macro 5.
- **App Flutter = télécommande** : pages de config (sélection caméra, expo, gain, bin, ROI, agressivité guiding), start/stop, graphe RA/DEC live, preview frames. Pas de logique image temps-réel dans l'app.

Pourquoi : PHD2 = ~15 ans de dev sur un problème difficile (traitement image temps-réel + boucle de correction). Réimplémenter en Dart/Flutter serait des mois de dev pour un résultat inférieur. Le tradeoff est que l'app devient un front pour des services Linux plutôt qu'une app "qui fait tout" — cohérent avec l'archi actuelle (Pi = backend, téléphone = UI).

**Décision prise** : tout passera par FastAPI (point de contrôle unique, pas de double surface d'API côté app). Le backend proxifie les commandes vers INDI et PHD2 et relaie leurs events via le flux SSE existant.

## Previews caméras (MAP, cadrage, framing) (Macros 5 / 6)

Pipeline preview et framing basique : **Macro 5**. Aides à la MAP (HFR/FWHM, zoom ROI, Bahtinov) : **Macro 6**. À spécifier dans les specs correspondants.

- **Source** : INDI diffuse les frames en FITS via subscription BLOB sur le driver caméra. Backend FastAPI les capture à la demande (snap) ou en boucle courte (live loop, 1–3s d'expo).
- **Transformation côté Pi** : FITS → auto-stretch d'histogramme (type MTF/STF) → debayer si capteur couleur → downsample → JPEG/PNG. Ne jamais envoyer du FITS brut au téléphone (T7C ≈ 12 Mpx, ~24 Mo par frame — inutilisable en Wi-Fi).
- **Transport vers Flutter** : endpoint HTTP binaire (`GET /preview/{cam}/latest.jpg`) pour un snap, ou MJPEG stream pour le live loop. Pas besoin de SSE/WebSocket pour le binaire ; SSE reste pour les métriques (HFR, timestamp, expo utilisée).
- **Aides à la mise au point** dans l'UI :
  - Zoom sur ROI (star picking tactile, l'utilisateur tape sur une étoile)
  - **HFR / FWHM** calculés côté Pi et poussés dans l'event SSE → courbe live (descend = on tourne dans le bon sens)
  - Histogramme
  - Optionnel : analyseur de masque Bahtinov
- **Framing / cadrage** : snap simple + overlay des coordonnées du centre et de l'orientation du capteur une fois plate-solvé.
- **Point d'archi subtil** : le live focus loop et le guidage PHD2 ne peuvent pas tourner simultanément sur la même caméra (un seul "client" possède le driver INDI à un instant T). Implique une **machine d'état côté backend** : `idle` / `focusing` / `guiding` / `imaging`, avec transitions propres et verrou par caméra. À poser dès Macro 5 dans le modèle d'état, même si les modes `focusing`/`guiding` ne sont activés qu'en Macro 6/7.

## Assistant d'alignement optique (chercheur / lunette guide / tube principal)

Procédure casse-pieds à faire manuellement, typiquement en début de session, à refaire dès qu'on touche à la config optique. Un wizard dans l'app éviterait les allers-retours à tâtons. Version complète en **Macro 6** (après plate solve) ; amorce possible plus tôt en Macro 3.

**Ce qu'il faut aligner**
- **Chercheur** ↔ tube principal (Maksutov 127/1900)
- **Lunette guide SV165** (+ caméra de guidage/solver) ↔ tube principal
- Objectif : quand le tube principal vise un point, chercheur et guide voient le même point (au décalage près assumé)

**Version minimale (amorce possible dès Macro 2/3, pas de caméra requise)**
- Wizard texte : sélection d'une étoile brillante, slew de la monture vers la cible, instructions pas-à-pas ("centre dans l'oculaire", "regarde le chercheur, ajuste les vis jusqu'au centrage", etc.)
- Valeur ajoutée modeste mais non nulle : le backend peut au moins piloter le slew, chronométrer, et rappeler la séquence dans le bon ordre.

**Version complète (Macro 6, après plate solving)**
- Snap sur la caméra guide + plate solve → coordonnées exactes du centre de la guide cam
- Comparaison avec la position annoncée par la monture (centre supposé du tube principal) → **offset chiffré en arcmin** affiché dans l'UI
- Instructions de correction avec sens de rotation des vis et amplitude attendue
- Possibilité de boucler (ajuste → re-snap → nouvel offset) jusqu'à convergence sous un seuil paramétrable

**Rangements UX**
- Probablement une sous-section de la page "Setup" ou un onglet dédié dans le wizard de mise en station
- À refaire "sporadiquement" (pas à chaque session), donc n'a pas besoin d'être au premier plan

## Capteurs d'inclinaison tube + monture (ADXL345 × 2) — retiré

**Décision 2026-04-24** : ajout de 2 accéléromètres ADXL345 (I2C) au setup, pour le zéro ALT/butées (tube) et la mise à niveau (monture). **Retiré le 2026-07-17** — voir [ADR](decisions.md) pour le contexte et les conséquences (compass en heading non tilt-compensé, niveau = bulle physique, anti-collision ALT repoussée en Macro 3). Les pistes de reprise identifiées à ce retrait sont capturées dans la section [« Reprise / résilience & aide au pré-pointage »](#reprise--résilience--aide-au-pré-pointage-post-retrait-adxl-macro-3) plus bas.

## Position persistante + retour à l'origine (Macro 5+)

- "Home position" définie physiquement par capteurs (distincte de l'alignement logique Celestron)
- Utilité : reprise après coupure, commande "retour à l'origine"
- À clarifier : peut-on lire directement la position depuis la monture via NexStar (`get_position`) une fois alignée, ou faut-il des encodeurs/capteurs externes indépendants ? Lien avec le plate solving (Macro 5) qui donnera aussi une position absolue.
- **Cap magnétique** : la piste compass a été retirée le 2026-08-26 (ADR) en même temps que le module DroTek. Reconstituer un cap absolu par capteurs reste écarté pour la même raison que l'IMU ci-dessous : le plate solve donne le pointage précis.
- **Inclinaison** : la piste 2 × ADXL345 envisagée ici a été retirée le 2026-07-17 (voir ADR) — hors chemin de pointage depuis l'ADR 2026-05-10, jamais enforcée. La piste IMU 9DOF (MPU6050/ICM-20948/BNO055) pour un cap tilt-compensé reste écartée pour la même raison : le plate solve fournira le pointage précis, on n'a pas besoin de reconstituer un cap absolu par capteurs.

## Reprise / résilience & aide au pré-pointage (post-retrait ADXL, Macro 3+)

Distillation de la discussion de retrait des ADXL345 (ADR 2026-07-17) : le vrai problème à résoudre n'était pas capteur, mais résilience logicielle et pré-pointage. Pistes capturées ici pour arbitrage futur.

> **Arbitré le 2026-08-26** (ADR retrait du DroTek). Les items **2, 3 et 4 sont sans objet** : la pose de parking est abandonnée (elle n'économisait qu'une acquisition manuelle par séance) et le compass est retiré. L'item **1 survit intact** — c'est de la persistance logicielle, jamais un problème de capteur — et reste **la priorité** de cette section. L'item **5 est renforcé** : c'est le plate solve (Macro 5) qui absorbe le besoin auquel la pose de parking prétendait répondre.

1. **⭐ Résilience reboot Pi (priorité)** — persister/restaurer l'alignement à chaud. Contexte : un reboot Pi n'affecte pas la monture (alims séparées Pi ≠ monture) → la monture ne bouge pas, ses encodeurs restent dans le même repère. C'est donc un problème de **persistance logicielle** (le driver perd son modèle en mémoire), **pas** un problème de capteur. Approche : persister le modèle/points de sync (déjà partiellement fait, ADR 2026-05-10) ; au redémarrage, si on détecte que la monture est restée sous tension (cohérence de la position rapportée vs dernière position trackée), restaurer l'alignement sans ré-aligner. **À vérifier d'abord (Macro 3)** : `indi_celestron_aux` stocke-t-il le modèle en mémoire driver (perdu au reboot → restauration nécessaire) ou dans les contrôleurs moteur (survit nativement) ?
2. ~~**Home = pose de parking motorisée + seed-sync au boot**~~ — **sans objet (2026-08-26)** : la 1ʳᵉ étoile est pointée à la main et son `record` appelle `sync_radec`, qui *est* la graine ; la pose n'économisait qu'un pointage manuel par séance, contre un mouvement motorisé, un état persisté, un chemin de récupération, une garde d'amplitude, un écran d'annonce, une carte Setup et une action Hub. Descriptif d'origine conservé pour mémoire : fin de séance : GoTo park motorisé (nord + 45°). Boot : **seed-sync** = convertir (alt 45° de la pose de parking + azimut compass + lat/lon/heure GPS) → RA/Dec → `EQUATORIAL_EOD_COORD` avec `ON_COORD_SET=SYNC` (même chemin que le wizard 3 étoiles). Donne un modèle 1-point grossier suffisant pour amener la 1ʳᵉ étoile dans le chercheur. Altitude portable (pose tenue au transport, trépied de niveau) ; azimut au compass (trépied reposé différemment). Prérequis : monture alignée en fin de séance pour parker.
3. ~~**« Set 0° tube au niveau »**~~ — **sans objet (2026-08-26)**, c'était le bootstrap de la pose de parking, abandonnée. Descriptif d'origine : calibration ponctuelle / bootstrap de la référence d'altitude au niveau à bulle (sync ALT à 0°). Pas un geste par séance : utile la 1ʳᵉ fois ou si la pose de parking est perdue.
4. ~~**Support compass déporté + correction de déclinaison**~~ — **sans objet (2026-08-26)** : le compass LIS3MDL est retiré (aucun consommateur — `naive_heading()` n'alimentait qu'un flux d'affichage). Descriptif d'origine : éloigner le magnétomètre (co-localisé GPS) des moteurs/acier (source dominante d'erreur azimut, le vrai goulot du pré-pointage) ; corriger magnétique → vrai nord via la position GPS (modèle WMM) ; calibration soft/hard-iron in situ. Contrainte : longueur de câble I2C (~30-50 cm, sinon soin câblage / horloge réduite).
5. **Coupure totale (Pi + monture) = non gérée** — décision assumée. Recovery : re-home manuel vers une pose connue (maintenant) → plate-solve (Macro 5), qui résout ce cas mieux qu'un capteur (position exacte depuis l'image, sans re-home).

## Safety & robustesse (Macro 2+, continu)

- **Arrêt d'urgence** — bouton soft dans l'app (et/ou hardware GPIO) qui force un `stop` sur tous les axes, indépendamment du reste du système. Complément naturel des courses min/max. À concevoir comme un chemin de commande prioritaire, contournant la logique métier.
- **Logs persistants côté Pi** — journalisation structurée des commandes monture, transitions d'état, erreurs série/GPS, événements orchestrateur. Rotation (journald ou logrotate). Permet le post-mortem d'une session ("pourquoi le tracking a décroché à 22h13 ?"). À prévoir dès qu'on aura des sessions réelles.

## Night planner offline (post-Macro 2)

Problème identifié : impossible de planifier une soirée sans Pi allumé / accessible (canapé, bureau, déplacement), alors que le catalogue + les calculs astro étaient côté Pi (ADR 2026-04-29).

**Résolu par le plan de référence Oracle** ([ADR 2026-07-24](decisions.md)). Le night planner s'appuiera sur le bundle **`reference.sqlite`** (généré hors-Pi par GitHub Actions, mis en cache localement par l'app) → planification **hors ligne, Pi éteint**, avec projection alt/az côté client.

- **Snapshot/cache-depuis-le-Pi** (ancienne piste préférée) : **supersédé** — un snapshot exige le Pi allumé, or on planifie justement Pi éteint (API à contre-sens du flux de données).
- **Lib éphémérides Dart** (Meeus/VSOP côté client) : **reste écartée** — duplication de la logique astro ; l'astro reste unique en Python/skyfield côté `oracle/`, l'app ne fait que la projection alt/az triviale.

À spécifier quand on attaquera la macro qui héberge le night planner (bâti sur le socle Oracle).

## Oracle — dette technique producteur (post-tranche 1)

Minors relevés à la revue finale du plan producteur ([ADR 2026-07-24](decisions.md)), différés car non bloquants pour un artefact correct. À arbitrer quand Oracle gagne des sources (tranche 2) ou avant d'y adosser un consommateur critique.

- **M-2 — Pas de plancher sur le nombre de comètes.** Une réponse HTTP-200 malformée du MPC (tronquée, vide, garbage) passerait le fetch sans lever d'erreur et produirait un artefact appauvri. Piste : asserter `len(comets) >= seuil_plancher` avant de publier, sinon retomber sur le snapshot bundlé.
- **M-4 — `epoch_jd` / `mpc_epoch` toujours NULL.** Les colonnes existent au schéma mais ne sont jamais peuplées (l'époque orbitale du MPC n'est pas propagée jusqu'à l'insert). Sans impact tant que le consommateur ne s'en sert pas ; à brancher si on expose l'époque.
- **M-5 — Drift d'environnement local.** Le venv local a tourné en Python 3.14 alors que la cible est 3.13 ; DeprecationWarnings skyfield / NumPy 2.5 (hors notre code) bruitent les runs. Aligner le local sur 3.13 et surveiller les deprecations avant une montée de version skyfield.

## Oracle — unifier la source d'étoiles du wizard 3 étoiles (post-SP2)

Le wizard d'alignement 3 étoiles garde sa **source propre** (`backend/astro_brain/services/_alignment_stars.json`), indépendante du catalogue. Depuis SP2, le catalogue vient de `reference.sqlite` (étoiles IAU-CSN incluses) → deux sources d'étoiles cohabitent, entorse au principe « une seule source ». Laissé tel quel en SP2 (autre sous-système, hors mandat « bascule catalogue »). Piste : faire dériver les candidats du wizard de `reference.sqlite` (`kind=star`, filtre magnitude/répartition ciel) et retirer le JSON. À arbitrer après SP2/SP3.

## Oracle — dette technique consommateur (post-SP2)

Minors différés à la revue finale du plan SP2 backend (bascule catalogue vers `reference.sqlite`), non bloquants pour un consommateur correct. À arbitrer avant d'y adosser un usage critique ou lors d'une évolution du format d'échantillonnage.

- **M-3 — `ephemeris.sample_utc` : comparaison de bornes lexicale (`BETWEEN`).** Le filtrage de fenêtre éphéméride compare des chaînes ISO ; correct aujourd'hui car les échantillons sont journaliers et au même format que les bornes, mais fragile si le producteur (SP1) émet un jour du `...Z` là où le consommateur attend `+00:00` (ou l'inverse) — l'ordre lexical divergerait. Piste : normaliser le format d'`sample_utc` **des deux côtés** (fixer un format canonique unique dans le contrat SP1↔SP2), ou parser en `datetime` avant comparaison plutôt que comparer les chaînes. Nécessite une coordination de format avec le producteur SP1.
- **M-6 — Pas de test e2e route sur `reference.sqlite` peuplé via `build_app`.** La logique (interpolation, gardes GoTo, résolution par `id`) est couverte unité par unité via fixtures, mais aucun test ne monte l'app complète (`build_app`) sur un `reference.sqlite` peuplé pour exercer le chemin route→resolver→provider de bout en bout. Couverture, pas correctness. Piste : un test d'intégration montant `build_app(db_path_override=...)` + un `reference.sqlite` de fixture, assertant `POST /goto` sur un objet réel. _(La partie `GET /catalog/objects` + enrichissement alt de cet item est caduque depuis SP3-B bis : endpoint et couche liste/visibilité retirés côté Pi.)_
- **M-7 — Garde version référence au moment du GoTo.** Si le Pi renvoie 404 sur un `id` que le téléphone connaît (référence Pi désynchronisée/plus ancienne que le cache app), surfacer explicitement « référence Pi périmée » plutôt qu'un échec GoTo générique. Alternative légère à un écran de statut Pi dédié (cf. revue archi A3).

## Oracle — dette technique app (post-SP3-A)

Minors + findings latents relevés aux task-reviews et à la revue finale Opus du plan SP3-A (bascule app sur le contrat SP2, en ligne). Aucun bloquant (revue finale *ready to merge*) ; à arbitrer lors de SP3-B (cache offline) ou d'un durcissement du chemin GoTo.

- **`_onGoTo` — capture de `current` avant l'`await`.** `current = state` est capturé avant `await repo.goto(...)` (timeout ~3 s) ; le handler utilise le transformer *concurrent* par défaut. Si un handler `_query` émettait un `CatalogueLoaded` frais pendant l'attente, l'`emit(current.copyWith(...))` suivant réverterait la liste visible à l'instantané périmé avant de la nettoyer. **Non atteignable via l'UI actuelle** (GoTo n'est déclenché que depuis la bottom-sheet modale qui recouvre les filtres, et le bloc catalogue ne consomme pas de SSE) → fragilité latente, pas un bug actif. Fix : re-lire `state` après l'`await` (garde `if (state is! CatalogueLoaded) return;`) avant d'émettre.
- **GoTo idempotence / debounce.** `_onGoTo` n'est pas debouncé ; un double-tap rapide peut faire dédupliquer (Equatable) et donc « avaler » un SnackBar d'erreur identique. Bénin aujourd'hui (non atteignable depuis la sheet), à revoir si GoTo devient déclenchable en rafale.
- **DRY / polish** (task-reviews) : extraire un helper `_emitOutcome` (le pattern emit-then-clear est dupliqué entre branche solaire et branche générique de `_onGoTo`) ; remplacer le `catch(_)` hardcodant `'GoTo impossible.'` par `messageForGotoDetail(null)` ; titre du dialog solaire en `Icon` plutôt que glyphe `⚠` brut ; assertions de test à durcir (préservation explicite de `.objects` après échec GoTo ; `schemaVersion` dans le test de `sync`) ; `getStatus()` appelé dans `build()` (`ReferenceBanner`/carte almanach) refait un GET par rebuild — cohérent avec la convention existante (`_buildCompassCard`), à revoir globalement.
- **Champs DTO catalogue v2 non affichés.** `angularSizeArcmin`/`messier`/`ngcIc`/`illumination`/`ephemerisStale` sont parsés (T2) mais pas encore surfacés dans l'UI ; l'affichage relève d'une tranche ultérieure (catalogue intelligent, Macro 4).
- **Statut référence : passer du polling REST au SSE.** `ReferenceBanner`/`AlmanacScreen` interrogent `GET /reference/status` à la demande. Quand le flux SSE d'état s'étoffera, replier le statut de référence dedans (cohérent avec « REST commandes / SSE état »).

## Oracle — dette technique app (post-SP3-B, cache local hors ligne)

Minors différés à la revue finale Opus du plan SP3-B (l'app lit `reference.sqlite` localement + calcule alt/az côté téléphone). Aucun bloquant (0 Critical/Important ; l'unique finding Important — queue FS de `sync()` hors garde non-throwing — a été corrigé avant merge). À arbitrer si le volume de l'almanach grossit ou lors d'un durcissement du chemin de sync.

- **Moteur + sync sur un isolate dédié (si le volume l'exige).** Le décodage `reference.sqlite`, `sha256.convert(data)` et `writeAsBytesSync` de la sync tournent sur le **main isolate** → jank UI bref le temps d'un swap d'almanach multi-Mo, et le merge/tri/pagination du catalogue local grossit avec le nombre d'objets. Piste : déporter le moteur de lecture et/ou la vérif+écriture de sync sur un `Isolate` (ou `compute`) quand la taille réelle de l'almanach le justifie. **Non requis** aux volumes actuels.
- **`AlmanacSync.reopen()` dans le `try` de swap (cosmétique).** Si `reopen()` levait *après* un `renameSync` réussi, `sync()` renvoie `offline` alors que le fichier a bien été swappé sur disque. Auto-réparant (`reopen`/`open`/`_adopt` avalent déjà `SqliteException` ; la sync suivante voit `localSha256` == manifest → `upToDate`) → pas un bug actif, cohérence de statut seulement.
- **Mocks hub non stubbés (piège latent de test).** `hub_screen_test.dart` construit un `CatalogueRepository` avec `_MockCatalogue`/`_MockVisibility` non stubbés — sûr aujourd'hui car aucun test hub ne pilote le `CatalogueBloc` (lazy). Le premier test hub qui navigue vers l'écran catalogue heurtera des appels mocktail non stubbés → prévoir `when(() => catalogue.listAll(any())).thenReturn([])` + `registerFallbackValue`.
- **Couverture à élargir (non-correctness).** Tests non ajoutés, logique jugée fidèle au portage backend : merge avec `offset>0` et tie-break magnitude égale (name asc) ; frontière `alt==0.0` ; `messierOnly`/branches search-null au niveau repository. `parseUtc` ne gère pas l'offset ISO court `+hh` (hors données Oracle, toujours offset complet/`Z`).
- **Fold état référence dans le SSE** — déjà tracké dans « dette app (post-SP3-A) » ci-dessus (`ReferenceBanner`/`AlmanacScreen` interrogent `GET /reference/status` à la demande) ; reste valable en local-first (le statut vient désormais de `meta()` local, mais le principe « état via un flux » tient).

## Ops & déploiement (à automatiser post-Macro 0)

- **Service systemd** pour le backend — livré (`astro-brain.service`).
- **Déploiement backend** — script `deploy.sh` ou cible Make (SSH → `git pull && systemctl restart astro-brain`). Évite le workflow manuel actuel. Le script devrait embarquer les deux étapes découvertes en S50 : sauvegarde `state.db` avant un pull qui apporte des migrations (forward-only et parfois destructrices), et `uv sync --extra hardware` si `pyproject.toml`/`uv.lock` bougent.
- **Mise à jour app Flutter** — pipeline build APK (+ TestFlight/iOS si concerné). À traiter séparément, pas via le Pi.
- **Power-save WiFi du Pi à désactiver (S50, en attente de validation).** `wlan0` tourne avec `Power save: on` (défaut `brcmfmac` — NetworkManager est à `powersave: 0`, « laisse le driver décider »). Au repos le Pi rate les ARP broadcast : tout client au cache ARP froid se prend un `No route to host` et le Pi paraît éteint alors qu'il tourne (constaté en S50 : `ping` et `ssh` morts, `nmap` le réveille au 2ᵉ SYN). **Impact terrain** : l'app téléphone se heurtera au même mur à la première requête après une inactivité. Correctif retenu : drop-in `/etc/NetworkManager/conf.d/wifi-powersave-off.conf` avec `[connection] wifi.powersave = 2` — global, donc il survit à la re-génération netplan (la connexion active est générée par netplan, un `nmcli con modify` serait perdu) et à un changement de SSID en sortie terrain.
- **ARP Pi → pont ESP32 : côté fautif tranché, hook posé, cause racine ouverte (S53 → S54).** ⚠️ **Phénomène distinct du power-save ci-dessus, ne pas les confondre — c'est maintenant prouvé, plus seulement prudent.** Le chemin **Pi → 192.168.1.200** casse : résolution ARP `INCOMPLETE`, `No route to host` sur `ping` comme sur TCP 2000, alors que la workstation joint le pont au même instant. **Tranché en S54** : la sonde ARP **unicast** du noyau (entrée forcée `nud stale`) est **répondue** par le pont → `REACHABLE`, tandis que la résolution **broadcast** à froid reste `INCOMPLETE` à 100 % — y compris avec `power_save off` sur `wlan0`, donc le power-save est **hors de cause**. Le pont répond donc bien à l'ARP et `WiFi.setSleep(false)` est déjà dans le firmware : **le correctif n'est pas côté pont**, et l'entrée statique est cohérente (IP fixe → entrée fixe), pas un pis-aller. **Fait en S54** : hook `/etc/NetworkManager/dispatcher.d/50-arp-esp32-bridge` (dispatcher et pas unit systemd — une reconnexion WiFi vide la table de voisinage, un `After=network-online.target` ne rejouerait qu'au boot) ; logique du hook vérifiée à la main, **son déclenchement sur un vrai événement `up` reste à confirmer au prochain reboot du Pi**. **Reste ouvert** : la cause racine du broadcast qui n'aboutit pas — la workstation est sur le **même BSSID / canal 100** et résout dynamiquement, donc ni la bande ni l'AP n'expliquent l'asymétrie ; épingler demande une capture, donc `tcpdump` (absent du Pi). ⚠️ Piège d'outillage : `iputils-arping` ne sait pas faire ce test (broadcast d'abord, unicast seulement après une première réponse) et une sonde raw-socket maison a produit un **faux négatif** — l'instrument fiable est la machine à états de voisinage du noyau (`nud stale` + trafic, puis `ip neigh`).
- **Verser le banc de smoke test dans le repo (S50).** `smoke.py` (32 contrôles REST/SSE avec attendu déclaré, y compris les codes d'erreur) a trouvé le défaut « capteur absent → 500 » ; il vit encore hors du repo. Cible : `backend/deploy/smoke.py`, IP en argument, à lancer après chaque déploiement.
- **Déploiements espacés = surprises accumulées (S50).** Le Pi avait 133 commits de retard : 5 migrations d'un coup, et 4 défauts d'observabilité découverts seulement en production, dont un vrai bug de correctness (fix GPS périmé). Piste : redéployer à chaque fin de session, même sans validation matérielle — c'est le seul endroit où le code tourne avec de vrais capteurs.

## [Macro 3] AlignmentService publish hook (symétrie architecturale)

**Constat** : `routes/alignment.py` publie l'état `alignment` sur la bus depuis la couche route (au lieu du service comme tous les autres subsystems — `FakeMount`, `FakeGps`, etc.). Ce choix a été fait pour préserver la pureté de `AlignmentServiceImpl` (T7) — sans dépendance au `StateBus`.

**Risque** : si une autre voie mute la session (orchestrateur, timer de timeout, restore au cold start), la bus dérivera silencieusement.

**Piste** : injecter un hook optionnel `on_state_change: Callable[[], None] | None` dans `AlignmentServiceImpl`. Le service appelle le hook après chaque mutation. `app.py` câble le hook vers une closure qui fait le publish. Le service reste découplé du `StateBus`, et toute mutation passe par le bon edge.

**Quand** : à arbitrer après Macro 3 quand on saura si d'autres voies mutent la session (cold-start restore notamment).

## [Macro 3] Axis-bar markers on PerStarScreen

Le mockup D2 et la prose du spec T16 demandent un marker `current` (textMuted, 2px) et un marker `target` (accent, 2px + glow) superposés sur la barre 6px. Le code Dart de référence du plan ne les a pas implémentés ; PerStarScreen affiche actuellement la track sans markers. Le delta numérique reste la source de vérité.

**Décision pour plus tard** : soit ajouter les markers (Stack + Positioned avec mapping current↔target sur la fraction de la barre), soit simplifier la barre en pure décoration (et le clarifier dans le doc).

## Mode "Mise en station" (important — Macro 3 puis Macro 6)

Scindé en deux livraisons :

**Macro 3 — version minimale (intégrée à l'alignement 3 étoiles)**
- **Cap nord** via compass (LIS3MDL DroTek) pour pré-pointer la première étoile
- **Niveau** : bulle physique du trépied (l'ADXL345 monture envisagé pour une bulle virtuelle logicielle a été retiré le 2026-07-17, voir [ADR](decisions.md)).
- **Alignement 3 étoiles** procédure NexStar assistée (le backend pilote le slew vers l'étoile proposée, l'utilisateur centre manuellement, valide, passe à la suivante)

**Macro 6 — wizard complet**
- Mêmes étapes mais réorchestrées comme assistant guidé end-to-end
- **Alignement par plate solve** (option alternative au 3-star) — centrage automatique après snap + solve
- UX critique : utilisé dans le noir, avec lampe rouge, parfois à l'aveugle → ergonomie soignée, instructions courtes, pas de couleurs vives en mode nuit
- Lien fort avec le compass et le plate solving (Macro 5).

## Raffinements UX Page Catalogue (issus Session 24)

- ~~**Feedback d'échec GoTo** : aujourd'hui un échec `POST /goto` (409/422/réseau) fait émettre `CatalogueError` au `CatalogueBloc`, ce qui remplace toute la liste par un message plein écran. Préférable : surfacer l'erreur via un `SnackBar` (BlocListener sur un sous-état dédié) sans détruire la liste chargée.~~ **Résolu (SP3-A, 2026-08-10)** : `CatalogueLoaded.gotoOutcome` (`GotoError`/`GotoSolarAck`) + `BlocListener`→SnackBar, la liste chargée est préservée via `copyWith`, `CatalogueError` n'est plus jamais émis sur un échec GoTo.
- **`_SlewBarSlot.buildWhen`** compare `gotoTarget` (map re-castée à chaque accès) par identité → rebuild quasi systématique quand un goto est en cours. Bénin (over-rebuild), mais à nettoyer (comparer une clé stable, ex. `target_name`).
- **Seuil de visibilité** : le filtre `visible_now` utilise l'horizon géométrique (alt > 0°). Quand le Setup tube arrivera (Macro 4), brancher un seuil pratique (obstruction / min-alt).

## [Macro 3 #5] Bug filtre constellation page Catalogue

Le menu déroulant de filtrage par constellation de `CatalogueScreen` est client-side et liste **toutes** les constellations présentes dans la liste chargée, sans tenir compte de la visibilité depuis la latitude courante. Le navigateur du wizard d'alignement, lui, s'appuie sur `GET /align/stars/visible` calculé backend (filtrage alt/az réel). À corriger : filtrer le déroulant catalogue par visibilité réelle (appel backend similaire, ou réutilisation d'une logique de visibilité partagée). Hors scope de la feature constellation-aid (qui ne touchait que le wizard).

## [Macro 3 #2] Projection ConstellationChart près du nord (azimut wrap-around)

La projection orientée-ciel de `ConstellationChart` mappe l'azimut directement en x. Une constellation à cheval sur l'azimut 0°/360° (ex. circumpolaires près du pôle nord) produit une plage x dégénérée → figure écrasée ou coupée. Acceptable pour une aide de reconnaissance visuelle (le chart n'est pas une carte astrométrique de précision). À corriger seulement si ça devient un vrai problème UX : détecter le straddle (écart entre az_min et az_max > 180°), unwrapper les azimuts autour du centre de la figure, tester en isolation sur des données synthétiques circumpolaires.

## Adresse du pont ESP32 : seule source = un fichier non versionné du Pi (S52)

Le backend ne pousse **jamais** `DEVICE_ADDRESS` / `CONNECTION_MODE` au driver : l'adresse du pont
(`192.168.1.200:2000`) ne vit que dans `~/.indi/Celestron AUX_config.xml`, hors git, sur le Pi.
Conséquence constatée en S52 : une session de debug avait laissé le driver pointé sur
`127.0.0.1:2001` (un proxy mort depuis), et rien côté backend ne pouvait le savoir ni le dire —
la seule trace était un échec de connexion générique.

Piste : faire de l'adresse du pont une **configuration du backend** (env ou table `state.db`), que
l'adaptateur pousse — ou au minimum vérifie et signale — à la connexion. À arbitrer avec le reste
du chantier « config du driver » (le `MOUNT_TYPE` de S51/S52 est de la même famille : des réglages
structurants du pointage vivent dans un fichier que personne ne relit).

**Mise à jour 2026-08-26** (ADR pont filaire) : l'item **change de nature sans disparaître**.
`DEVICE_PORT` (`/dev/ttyAMA0`) remplace `DEVICE_ADDRESS`/`CONNECTION_MODE` dans le **même** fichier
non versionné. Le mode de défaillance de S52 se rejoue à l'identique avec un port erroné, à ceci
près qu'il devient au moins détectable : `serialReadResponse()` renvoie `false` en timeout, là où
`tcpReadResponse()` renvoyait toujours `true`.

**Résolu le 2026-08-26** (Task 3 du plan pont série) : `MountIndiAdapter._configure_serial_link()`
pousse `CONNECTION_MODE` → `DEVICE_PORT` → `PORT_TYPE` **depuis le code**, avant `CONNECT`, et
logue chaque poussée. Le fichier `~/.indi/Celestron AUX_config.xml` n'est plus la source du lien :
un port erroné qui y traînerait est écrasé au démarrage. Reste ouvert, de la même famille mais
distinct : le `MOUNT_TYPE` de S51/S52, toujours non poussé (cosmétique, cf. `indi-reference.md`).

## `current_position()` n'a aucune garantie de fraîcheur (S54)

`MountIndiAdapter.current_position()` attend via `_await_widgets` que le vecteur
`TELESCOPE_ENCODER_ANGLES` **existe** avec ses deux widgets, puis lit `getValue()`. Rien ne dit que
la valeur lue vient d'une réponse récente de la monture : quand le driver rejette une trame, il
republie simplement sa valeur en cache, et l'adaptateur la renvoie comme une mesure fraîche.

C'est exactement ce qui a mordu en S54 : le pont relayait bus→TCP octet par octet, le driver
rejetait toutes les réponses ALT (`Partial message recv. dropping`) et `AXIS_ALT` restait figé —
bit pour bit identique après un mouvement de 2 s. Le correctif firmware (réassemblage des trames,
commit `c3f647e`) a supprimé **cette** cause, pas le mode de défaillance : n'importe quelle autre
perte de trames (bruit sur le bus, moteur qui ne répond plus, socket TCP saturée) reproduira le
même silence. Enjeu réel pour Macro 3 : le wizard 3 étoiles enregistrerait une position fausse
sans le moindre signal d'erreur.

Pistes : comparer le timestamp du vecteur INDI à `now` et lever `SensorUnavailableError` au-delà
d'un seuil ; ou exiger que la valeur ait bougé sur un déplacement connu avant de la valider. La
première est la moins intrusive — reste à vérifier que `pyindi-client` expose bien le timestamp de
dernière mise à jour du vecteur, et que le driver l'actualise seulement sur trame acceptée (sinon
le timestamp ne vaut pas mieux que la valeur).

## Pré-pointage auto des étoiles #2/#3 du wizard : conçu, jamais câblé (2026-08-26)

Le wizard est spécifié comme « 1ʳᵉ étoile pointée à la main, #2 et #3 pré-pointées automatiquement
par le modèle 1 étoile puis 2 étoiles ». **Ce n'est pas implémenté** : aucun appel `goto`/`slew`
dans `app/lib/features/alignment/` (`per_star_screen.dart` affiche le D-pad et le bouton « centré »
pour les trois étoiles à l'identique), et `routes/goto.py:41` refuserait de toute façon la demande
par `409 not_aligned` — la garde exige `alignment.is_aligned`, vrai seulement après `finalize()`.

Devenu porteur depuis le **retrait du DroTek** (ADR 2026-08-26) : le modèle est désormais la seule
aide au pointage avant Macro 5.

**Question de conception à trancher avant tout code** : relâcher la garde en « au moins un point de
sync enregistré » ouvre le goto sur un modèle 1 point, dont l'erreur peut être de plusieurs degrés
— avec un tube qui peut aller taper la fourche ou le trépied. Options à peser : un chemin de
pré-pointage **distinct** de `/goto` (borné en amplitude, réservé au wizard, sans tracking) plutôt
qu'un assouplissement de la garde du goto public ; et la question de l'anti-collision ALT, repoussée
en Macro 3 par l'ADR 2026-07-17 et jamais reprise depuis. Mérite une spec + un plan dédiés, pas une
tâche greffée sur un autre chantier.

## Observer hors WiFi domestique : le sujet se réduit au Pi (2026-08-26)

Avec le retrait du WiFi du pont (ADR 2026-08-26), plus rien à provisionner côté ESP32 — la monture
répond sans aucun réseau. Reste à donner du réseau au **Pi** sur un site distant, pour deux besoins
seulement : que le téléphone atteigne le backend, et que NTP tienne l'horloge.

Pistes : partage de connexion du téléphone (le Pi rejoint le hotspot — nécessite de saisir un SSID
au chevet, donc une UI ou un fichier de conf) ; ou le Pi en point d'accès et le téléphone qui s'y
connecte (pas d'Internet, donc pas de NTP → renvoie à l'item RTC ci-dessous). À traiter quand une
sortie réelle hors domicile sera programmée, pas avant.

## Horloge sans réseau : RTC DS3231 (2026-08-26)

Le Pi 3 B+ n'a pas d'horloge temps réel ; l'heure poussée à la monture est `datetime.now(UTC)`,
tenue par NTP. Le retrait du GPS ne change rien à ça (le GPS n'était qu'un *déclencheur* de sync,
jamais une source de temps disciplinée — ni chrony ni gpsd n'ont jamais été configurés pour ça).

Un DS3231 (`dtoverlay=i2c-rtc,ds3231`, zéro code applicatif) ne devient nécessaire que sur un site
**sans couverture cellulaire** : pas de partage de connexion, donc pas de NTP, donc `fake-hwclock`
restaure l'heure du dernier arrêt. **À trancher sur constat terrain, pas par anticipation** — et
l'I2C1 est libre depuis le retrait du DroTek. Note : la garde « horloge non synchronisée → refus de
sync monture » (livrée avec le retrait) rend ce cas **visible** au lieu de silencieux, ce qui suffit
tant qu'on n'a pas rencontré le site en question.

## Flasher le pont sans le démonter du banc (2026-08-27)

Aujourd'hui, reflasher l'ESP32 impose de sortir la carte du banc : la netlist
(`hardware/aux-bridge/aux-bridge.net`) met `A1.VIN` sur le **même net `+5V`** que le LM2902
(`U1.4`), le 74AHCT125 (`U2.4/10/13/14`) et le découplage, alimentés par le bornier `J2`. Brancher
l'USB pose VBUS sur ce nœud face à l'alim du banc — le conflit retombe donc sur *toute* solution
passant par USB, et il faut le traiter à la source.

Options pesées le 2026-08-27, **aucune retenue** : le firmware ne bouge pas tous les quatre matins,
on rouvrira le sujet si le besoin se fait sentir.

- **USB permanent Pi ↔ ESP32, `VIN` détaché du rail du banc** (masse commune, le rail continue
  d'alimenter les deux CI). Flash = `ssh astro-brain` + `esptool`, plus aucun geste physique, et la
  console de debug de la carte (`[bus] écho incomplet`, bandeau de boot) tombe dans le journal du
  Pi — ce qui aurait fait gagner du temps en S57. Contreparties : l'ESP32 ne vit que si le Pi est
  allumé (sans importance, le pont ne sert à rien sans lui), `esptool` à installer sur le Pi, et un
  port USB occupé — l'ADR 2026-04-21 les réservait aux caméras, règle déjà déclarée sans objet
  depuis le retrait des capteurs, mais à réacter.
- **Schottky entre `J2` et `VIN`** : les deux sources coexistent sans rien débrancher (la plupart
  des DevKitC ont déjà une diode sur VBUS → broche 5V, d'où un OU propre ; ~0,3 V de chute, sans
  effet sur l'AMS1117). Un seul composant, mais le câble USB reste à porter jusqu'à la carte.
- **Cavalier sur `VIN`**, retiré avant chaque branchement USB : le moins cher, mais un geste par
  flash — et un geste qu'on oublie.
- **OTA WiFi : écarté.** C'est exactement ce que l'ADR 2026-08-26 a retiré ; le rétablir pour le
  confort de flash ramènerait la radio, `secrets.h` et une connexion au boot.
- **Flash par les trois fils existants : impossible** sans rework. Le bootloader ESP32 écoute sur
  *son* UART0 (GPIO1/3), pas sur GPIO25/26, et exige qu'on pilote `EN` et `GPIO0`.

Si une option est retenue un jour : ADR + régénération de la netlist par `gen_netlist.py` (ne jamais
éditer le `.net`).
