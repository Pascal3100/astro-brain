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
- *Niveau monture*, *Calibration ADXL345 monture*, *Calibration ADXL345 tube*, *Calibration compass*, *Courses ALT/AZ*, *Backlash*, *Network/IP* (livré), *À propos*

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

- **Courses min/max ALT/AZ** — safety pour éviter collision tube/trépied. Côté ALT : alimenté par l'ADXL345 tube. Côté AZ : soft via position monture, pas de capteur dédié.
- **Caractéristiques du tube** (focale, diamètre, obstruction) — prérequis pour filtrage catalogue (Macro 4) et calculs FOV astrophoto (Macro 5).
- **Compensation de backlash** — améliore tracking et GoTo (Macro 2).
- **TODO : auditer la raquette Celestron** — passer en revue tous les menus/réglages techniques exposés par le hand controller (backlash, anti-backlash, cone error, PEC, filter limits, custom slew rates, etc.) pour identifier ce qu'il faut exposer/récupérer côté app et/ou lire/écrire via NexStar.

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

## Capteurs d'inclinaison tube + monture (ADXL345 × 2)

**Décision 2026-04-24** : ajout de 2 accéléromètres **ADXL345** (I2C) au setup. Commandés.

**Rôles distincts**
- **ADXL345 tube** (adresse `0x53`, SDO=VCC) — mesure l'inclinaison du tube par rapport à l'horizontale. Sert à :
    - Définir/retrouver le **zéro ALT** (tube à plat)
    - Détecter l'approche des **butées ALT** (safety, complément des courses min/max de la page "Réglages techniques monture")
- **ADXL345 monture** (adresse `0x1D`, SDO=GND) — mesure la planéité de l'embase. Sert à :
    - **Mise à niveau pré-session** (remplace/complète la bulle physique sur trépied)
    - Alimenter une page "Niveau monture" style HUD (bulle virtuelle XY, feedback < 0.5°)

**Justification du choix** : usage statique pur, la gravité suffit (`atan2(ay, az)`). Pas besoin de fusion 9DOF ni de gyro. L'ADXL345 = accéléromètre simple ~2-3 €, très courant, **deux adresses I2C sélectionnables via la pin SDO** → les 2 modules cohabitent sur le même bus sans multiplexeur. Précision typique < 0.5° brute, < 0.1° après calibration statique — largement suffisant pour retrouver le zéro et poser des butées soft.

**Bus I2C1 final**
| Device | Adresse |
|---|---|
| LIS3MDL (compass DroTek) | `0x1E` |
| ADXL345 tube | `0x53` |
| ADXL345 monture | `0x1D` |

**Pages UI associées** (à détailler dans les specs correspondants quand on y arrivera)
- **Page "Niveau monture"** — bulle virtuelle XY, feedback rouge/vert < 0.5°. Intégrée à Macro 2 (Setup).
- **Page "Calibration tube"** — bouton "définir le zéro" quand tube horizontal + affichage live de l'angle + alerte à l'approche des butées. Probablement rattachée à la page "Setup tube" (Macro 4) ou à la Macro 2.

Cette décision remplace la piste IMU 9DOF évoquée ci-dessous : on n'a pas besoin d'un cap tilt-compensé pour le pointage, le plate solve (Macro 5) prendra le relais avec bien plus de précision.

## Position persistante + retour à l'origine (Macro 5+)

- "Home position" définie physiquement par capteurs (distincte de l'alignement logique Celestron)
- Utilité : reprise après coupure, commande "retour à l'origine"
- À clarifier : peut-on lire directement la position depuis la monture via NexStar (`get_position`) une fois alignée, ou faut-il des encodeurs/capteurs externes indépendants ? Lien avec le plate solving (Macro 5) qui donnera aussi une position absolue.
- **Inclinaison** : tranché (cf. section "Capteurs d'inclinaison tube + monture" plus haut) → 2 × ADXL345. La piste IMU 9DOF (MPU6050/ICM-20948/BNO055) pour un cap tilt-compensé est écartée : le plate solve fournira le pointage précis, on n'a pas besoin de reconstituer un cap absolu par capteurs.

## Safety & robustesse (Macro 2+, continu)

- **Arrêt d'urgence** — bouton soft dans l'app (et/ou hardware GPIO) qui force un `stop` sur tous les axes, indépendamment du reste du système. Complément naturel des courses min/max. À concevoir comme un chemin de commande prioritaire, contournant la logique métier.
- **Logs persistants côté Pi** — journalisation structurée des commandes monture, transitions d'état, erreurs série/GPS, événements orchestrateur. Rotation (journald ou logrotate). Permet le post-mortem d'une session ("pourquoi le tracking a décroché à 22h13 ?"). À prévoir dès qu'on aura des sessions réelles.

## Night planner offline (post-Macro 2)

Problème identifié : impossible de planifier une soirée sans Pi allumé / accessible (canapé, bureau, déplacement), alors que le catalogue + les calculs astro étaient côté Pi (ADR 2026-04-29).

**Résolu par le plan de référence Oracle** ([ADR 2026-07-24](decisions.md)). Le night planner s'appuiera sur le bundle **`reference.sqlite`** (généré hors-Pi par GitHub Actions, mis en cache localement par l'app) → planification **hors ligne, Pi éteint**, avec projection alt/az côté client.

- **Snapshot/cache-depuis-le-Pi** (ancienne piste préférée) : **supersédé** — un snapshot exige le Pi allumé, or on planifie justement Pi éteint (API à contre-sens du flux de données).
- **Lib éphémérides Dart** (Meeus/VSOP côté client) : **reste écartée** — duplication de la logique astro ; l'astro reste unique en Python/skyfield côté `oracle/`, l'app ne fait que la projection alt/az triviale.

À spécifier quand on attaquera la macro qui héberge le night planner (bâti sur le socle Oracle).

## Ops & déploiement (à automatiser post-Macro 0)

- **Service systemd** pour le backend — livré (`astro-brain.service`).
- **Déploiement backend** — script `deploy.sh` ou cible Make (SSH → `git pull && systemctl restart astro-brain`). Évite le workflow manuel actuel.
- **Mise à jour app Flutter** — pipeline build APK (+ TestFlight/iOS si concerné). À traiter séparément, pas via le Pi.

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
- **Niveau** : via l'ADXL345 monture (cf. section "Capteurs d'inclinaison tube + monture"). Bulle virtuelle dans l'UI, feedback < 0.5°. La bulle physique sur trépied reste un fallback manuel.
- **Alignement 3 étoiles** procédure NexStar assistée (le backend pilote le slew vers l'étoile proposée, l'utilisateur centre manuellement, valide, passe à la suivante)

**Macro 6 — wizard complet**
- Mêmes étapes mais réorchestrées comme assistant guidé end-to-end
- **Alignement par plate solve** (option alternative au 3-star) — centrage automatique après snap + solve
- UX critique : utilisé dans le noir, avec lampe rouge, parfois à l'aveugle → ergonomie soignée, instructions courtes, pas de couleurs vives en mode nuit
- Lien fort avec le compass et le plate solving (Macro 5).

## Raffinements UX Page Catalogue (issus Session 24)

- **Feedback d'échec GoTo** : aujourd'hui un échec `POST /goto` (409/422/réseau) fait émettre `CatalogueError` au `CatalogueBloc`, ce qui remplace toute la liste par un message plein écran. Préférable : surfacer l'erreur via un `SnackBar` (BlocListener sur un sous-état dédié) sans détruire la liste chargée.
- **`_SlewBarSlot.buildWhen`** compare `gotoTarget` (map re-castée à chaque accès) par identité → rebuild quasi systématique quand un goto est en cours. Bénin (over-rebuild), mais à nettoyer (comparer une clé stable, ex. `target_name`).
- **Seuil de visibilité** : le filtre `visible_now` utilise l'horizon géométrique (alt > 0°). Quand le Setup tube arrivera (Macro 4), brancher un seuil pratique (obstruction / min-alt).

## [Macro 3 #5] Bug filtre constellation page Catalogue

Le menu déroulant de filtrage par constellation de `CatalogueScreen` est client-side et liste **toutes** les constellations présentes dans la liste chargée, sans tenir compte de la visibilité depuis la latitude courante. Le navigateur du wizard d'alignement, lui, s'appuie sur `GET /align/stars/visible` calculé backend (filtrage alt/az réel). À corriger : filtrer le déroulant catalogue par visibilité réelle (appel backend similaire, ou réutilisation d'une logique de visibilité partagée). Hors scope de la feature constellation-aid (qui ne touchait que le wizard).

## [Macro 3 #2] Projection ConstellationChart près du nord (azimut wrap-around)

La projection orientée-ciel de `ConstellationChart` mappe l'azimut directement en x. Une constellation à cheval sur l'azimut 0°/360° (ex. circumpolaires près du pôle nord) produit une plage x dégénérée → figure écrasée ou coupée. Acceptable pour une aide de reconnaissance visuelle (le chart n'est pas une carte astrométrique de précision). À corriger seulement si ça devient un vrai problème UX : détecter le straddle (écart entre az_min et az_max > 180°), unwrapper les azimuts autour du centre de la figure, tester en isolation sur des données synthétiques circumpolaires.
