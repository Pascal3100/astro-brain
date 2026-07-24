# Décisions d'architecture (ADRs)

Décisions structurantes du projet, sous forme de notes courtes. Une décision = un titre + contexte + choix + rationale. Pas un journal — uniquement les décisions qui méritent d'être retrouvables.

---

## 2026-07-24 — Plan de données de référence indépendant du Pi + module `oracle/`

**Contexte** : le besoin « proposer à l'utilisateur les événements éphémères observables (comètes, conjonctions, appulses, novæ…) selon sa position et son matériel » a fait apparaître une limite d'architecture de fond. L'app Flutter a un mode offline, mais il est inutile pour la **planification** : toutes les données astro sont servies par le Pi (ADR [2026-04-29](decisions.md) « catalogue + calculs astro côté backend »), or **le Pi n'est allumé qu'en session d'observation**. Planifier une soirée, consulter les éphémères, recevoir des alertes se fait typiquement **loin du télescope, Pi éteint** (canapé, bureau, déplacement) — exactement quand la source de données est indisponible. Le pattern *snapshot/cache-depuis-le-Pi* envisagé dans [`backlog.md`](backlog.md) pour le night planner **ne survit pas** à ce constat : pour obtenir un snapshot il faut le Pi allumé. Faire transiter la planification par le Pi est une **API à contre-sens du flux de données**. Sans plan de planification autonome, l'app ne fait que singer la raquette Celestron.

Une distinction structure la solution : on avait conflaté **trois natures de données** sous un seul « serveur Pi ». (1) **Live/contrôle** (monture, slew, capteurs, SSE) — le Pi seul peut la servir, Pi allumé, OK. (2) **Config/calibration** (compass, IP, courses, tube, modèle d'alignement) — écrite/lue au télescope, spécifique à la monture physique, vit dans `state.db` sur le Pi. (3) **Référence** (catalogue, comètes, événements, éphémérides) — read-mostly, identique pour tous, générée centralement, nécessaire **loin du Pi (planif) comme au télescope (session)**.

**Décision** :

1. **Extraire un plan de données de référence (nature 3) autonome du Pi.** Il est **généré hors-Pi** par un job **GitHub Actions** (skyfield + fetch MPC), qui publie un artefact **`reference.sqlite`** (fichier SQLite indexé, versionné) + un `manifest.json`. Coût 0 € (Actions gratuit + Release/Pages).
2. **Distribution = fichier mis en cache localement, pas BDD interrogée en direct.** L'app **et** le Pi téléchargent `reference.sqlite` (sync conditionnelle sur version/etag) et l'interrogent **en local, hors ligne**. Une BDD hébergée interrogée en direct est **rejetée** : elle réintroduit la dépendance qu'on supprime (« besoin Internet » au lieu de « besoin Pi »), or un site d'observation sombre n'a souvent aucun réseau ; et la fraîcheur des éphémères est à l'échelle du jour → une sync locale quotidienne = « toujours frais » pour ce domaine.
3. **Répartition du calcul** : le CI pré-calcule le dur (éléments orbitaux → échantillons RA/Dec, magnitude prédite, événements). Les consommateurs font la **projection alt/az** triviale pour leur site/heure. Aucune réimplémentation de mécanique orbitale en Dart (l'astro reste **unique, en Python/skyfield**).
4. **Nouveau module `oracle/`** dans le monorepo (pair de `backend/` et `app/`), producteur de `reference.sqlite`. Frontière nette producteur/consommateur : `oracle/` ne dépend de **rien** dans `backend/`/`app/` ; **le schéma SQLite EST l'interface**. Reste dans le monorepo (pas un repo séparé) pour versionner le contrat au même endroit que ses consommateurs ; extraction ultérieure triviale (`git subtree`) si besoin.
5. **Notifications** : canal par défaut **local programmé** (l'app lit le bundle et programme ses notifs via `flutter_local_notifications`) — couvre tout le prévisible (comète du mois, conjonction, showers), zéro cloud. Canal **FCM optionnel** (gratuit, poussé par le job Actions) **différé**, à greffer si le besoin de transitoire temps réel « ce soir, n'importe où » se confirme.
6. **Placement roadmap** : nouveau **fil transverse « Oracle / Éphémères »** (comme *safety*, *mode nuit*, *night planner*), livré en tranches — **tranche 1 = infra `oracle/` + comètes** (le seul cas « fetch »), puis événements calculés, puis appulses. Le **discriminant oculaire/photo** se branche au fil des macros : seuil visuel avec le *Setup tube* (Macro 4), seuil photo avec le *Setup caméras* (Macro 5).

**Rationale** :
1. **C'est ce qui donne sa valeur au système** : un compagnon qui dit quoi/quand/avec quel matos observer, même Pi éteint et hors ligne — ce que la raquette ne fait pas.
2. **Archi affûtée** : chaque plan de données est servi par la source légitime ; le Pi ne fait plus que ce que lui seul peut faire (la monture). On supprime l'API à contre-sens du flux.
3. **Logique astro unique** : skyfield reste la seule implémentation ; les consommateurs ne font que projeter/afficher. Pas de duplication Dart (la piste « éphémérides Dart » du backlog reste écartée, pour une meilleure raison).
4. **Coût nul et git-natif** : Actions gratuit, artefact versionné, aucun serveur à maintenir. Le serverless (Cloud Run/Lambda) et le cloud (Firebase Functions) n'apportent rien de plus pour une charge **périodique** et ajoutent carte bancaire + infra.
5. **Résilience carte SD** : `reference.sqlite` est **jetable/re-synchronisable** → sa corruption est un non-événement ; seule `state.db` (petite, privée) reste précieuse et sauvegardable.

**Conséquences** :
- Nouveau répertoire `oracle/` (pyproject.toml, workflow `.github/workflows/oracle.yml`, tests, README propres). `backend/` et `app/` gagnent un consommateur de `reference.sqlite` (cache local + sync conditionnelle + projection alt/az).
- **Nuance l'ADR [2026-04-29](decisions.md)** (« catalogue + calculs astro côté backend ») : le *live* (visibilité à l'instant courant via GPS) reste calculable côté Pi, mais la **donnée de référence** (catalogue, éphémères) n'est plus servie **exclusivement** par le Pi — elle a une source autonome que le Pi consomme aussi.
- **À répercuter** (prochaine étape, hors de cet ADR) : `roadmap.md` (ajout du fil transverse « Oracle / Éphémères » + couplage Macro 4/5) ; `backlog.md` (section *Night planner offline* → le snapshot-depuis-le-Pi est **supersédé** par le plan de référence oracle ; l'alternative « éphémérides Dart » reste écartée).
- Spec de la tranche 1 : [`docs/superpowers/specs/2026-07-24-oracle-ephemeres-design.md`](../superpowers/specs/2026-07-24-oracle-ephemeres-design.md).

**Cross-références** : nuance l'ADR [2026-04-29](decisions.md) (catalogue/astro backend) et touche l'ADR [2026-04-29](decisions.md) (Hub central listait « Night planner » parmi les entrées agrégées — la source de ses données change). Indépendant de la chaîne monture (ADR 2026-07-05 pont ESP32).

---

## 2026-04-15 — Pas d'Arduino dans la chaîne

**Contexte** : design initial prévoyait un Arduino comme intermédiaire entre Pi et monture pour temps-réel.

**Décision** : Pi communique directement avec la monture via série (port HC NexStar). _Lib révisée par l'ADR du 2026-05-01 (INDI)._ _**Dérogée par l'ADR du 2026-07-05** (pont ESP32) : un micro-contrôleur est finalement introduit, non pour le temps-réel moteur mais comme interface électrique/WiFi sur le bus AUX single-wire._

**Rationale** : la monture Celestron a déjà son micro-contrôleur interne pour le temps-réel moteur. Un Arduino ajouterait une couche série de plus, sans valeur. Le Pi reste réactif côté FastAPI via les patterns asyncio.

---

## 2026-04-15 — REST + SSE, pas de WebSocket

**Décision** : commandes via REST (`/slew`, `/stop`, `/tracking`, `/goto`), état via SSE (`/events`).

**Rationale** : simple à implémenter en FastAPI, simple à consommer en Flutter, compatible HTTP/1.1 partout. Le D-Pad fonctionne en start/stop (pas besoin de bidirectionnel temps-réel). SSE supporte la reconnexion auto.

---

## 2026-04-21 — Capteurs hardware via GPIO uniquement

**Contexte** : le Pi 3 B+ a 4 ports USB. Le projet final aura 3 caméras + monture (USB), ce qui sature.

**Décision** : tous les capteurs (GPS DroTek, compass LIS3MDL, ADXL345 ×2) passent par les GPIO (UART0 + I2C1), pas via USB.

**Rationale** : préserve les ports USB pour la monture et les caméras. Les bus GPIO ont la bande passante nécessaire (NMEA en UART à 9600/38400 bauds, I2C à 400 kHz).

---

## 2026-04-24 — Accéléromètres simples (ADXL345 ×2) plutôt que IMU 9DOF

**Contexte** : besoin de mesurer l'inclinaison du tube (zéro ALT, butées) et la planéité de la monture (mise à niveau).

**Décision** : 2 × ADXL345 (I2C, ~3 € pièce). Pas d'IMU 9DOF (MPU6050/BNO055).

**Rationale** : usage statique pur, la gravité suffit (`atan2(ay, az)`). Pas de fusion de capteurs ni cap tilt-compensé nécessaires (le plate solve v0.5 prendra le relais pour le pointage précis). Les 2 ADXL345 cohabitent sur I2C1 grâce à la pin SDO (`0x53` tube, `0x1D` monture). Précision < 0.5° brute, < 0.1° après calibration.

---

## 2026-04-24 — App Flutter native (pas PWA)

**Décision** : app Flutter native compilée pour Android (et iOS plus tard), pas une PWA servie par le Pi.

**Rationale** : performance et sensation native, accès USB-debug pour smoke test, pas besoin d'un serveur web servant l'app sur le Pi (la complexité d'un setup PWA n'apporte rien de plus qu'un APK installé).

---

## 2026-04-24 — Pattern BLoC pour Flutter

**Décision** : `flutter_bloc` (pattern BLoC, MVVM-like) avec `equatable` pour les états.

**Rationale** : pattern le plus idiomatique pour une app Flutter à état partagé entre écrans (status système global, thème, alignement). Documentation officielle dense (`docs.flutter.dev`), testable via `bloc_test`. Alternatives écartées : Provider seul (pas assez structuré), Riverpod (overkill ici, communauté plus jeune), Redux (verbeux pour le besoin).

---

## 2026-04-29 — Catalogue + calculs astro côté backend

**Décision** : Pi sert le catalogue (Messier, planètes, étoiles brillantes) via REST. Calculs astro (Alt/Az, éphémérides) faits en Python avec `skyfield` / `astropy`. App = client de présentation.

**Rationale** : le Pi a déjà l'heure GPS exacte + la position. Les libs Python d'astro sont matures et précises. Centraliser la logique astro dès maintenant prépare le night planner et le filtrage par visibilité (v0.4+). Inconvénient identifié pour le night planner offline : traité plus tard via pattern snapshot/cache (cf. backlog).

---

## 2026-04-29 — Hub central comme nouveau landing post-Splash

**Décision** : à partir de v0.3, l'app n'arrive plus directement sur le HomeScreen manuel. Splash → Hub agrégateur → écran feature.

**Rationale** : permet d'agréger Manuel / GoTo / Catalogues / Status / Setup / Night planner au fur et à mesure, sans charger un écran feature avec des boutons d'autres modes. Le hub n'affiche que les entrées actives — les autres apparaissent quand elles ont un contenu.

---

## 2026-04-29 — AppBar partagée sur tous les écrans

**Décision** : convention de template — tous les écrans Flutter affichent une AppBar commune contenant pastille de status global + toggle jour/nuit + bouton reconnect conditionnel.

**Rationale** : l'utilisateur veut garder l'état système et le toggle thème accessibles en permanence (utilisation terrain de nuit). Évite la duplication par écran et garantit la cohérence visuelle HUD.

---

## 2026-04-30 — Setup devient v0.2 (avant l'alignement)

**Contexte** : le brainstorm initial visait v0.2 = mise en station 3 étoiles + GoTo + catalogue minimal. En détaillant les prérequis, il est apparu qu'on ne peut pas faire un alignement sérieux sans : compass calibré, ADXL345 calibré, courses définies, backlash compensé.

**Décision** : Setup devient le milestone v0.2. La mise en station + GoTo passe en v0.3. Le décalage propage sur tout le reste.

**Rationale** : shipper un alignement sans calibration capteurs serait shipper une feature qui ne marche pas en pratique. Mieux vaut un Setup robuste qui débloque l'alignement, que l'inverse.

---

## 2026-05-01 — Pilotage monture via INDI (drop nexstarpy)

**Contexte** : v0.1 utilise `nexstarpy` 0.1.0 (HC-only, mono-auteur, pas d'AUX). v0.2 a besoin de backlash + cordwrap + sync RA/Dec + `is_aligned` + `goto_in_progress`, qui passent par les commandes AUX (pass-through `'P'`/0x50 du HC). v0.5 amène les caméras → INDI sera de toute façon dans la stack pour le plate solving / framing / capture.

**Décision** : pivoter dès v0.2 sur l'écosystème **INDI** — `indiserver` + driver `indi_celestron_aux` (BETA, repo `indi-3rdparty`) + client Python `pyindi-client`. Le nouveau backend wrappe INDI derrière la même interface `MountAdapter` (REST `/slew`, `/stop`, `/tracking`, `/goto` inchangés côté Flutter).

**Rationale** : tout code écrit autour de `nexstarpy` serait jeté à v0.5 — coût zéro de jeter maintenant vs cycle complet plus tard. INDI couvre 6 des 7 besoins v0.2/v0.3 nativement (vérifié par lecture source). Manque uniquement le mount-axis backlash (opcodes `MC_*_BACKLASH` non câblés dans `auxproto.h`) → patch upstream estimé ~70 lignes C++. Spec : [`docs/superpowers/specs/2026-05-01-mount-indi-design.md`](../superpowers/specs/2026-05-01-mount-indi-design.md). Doc onboarding : [`docs/technical/indi-reference.md`](../technical/indi-reference.md).

---

## 2026-05-01 — Câblage monture via dongle CP2102 USB-TTL 5V (port HC RJ12)

> ⚠️ **SUPERSEDÉ par l'ADR du 2026-07-05 (pont ESP32).** Le dongle USB-TTL (CP2102 puis CH340) s'est avéré incapable de dialoguer avec le bus : le bus AUX est **single-wire half-duplex** (pas RX/TX séparés) et tout tap pas vraiment haute-Z perturbe la ligne (cause racine électrique, S26→S30). Conservé pour l'historique.

**Contexte** : la monture s'attache au Pi par le port HC en RJ12 (TTL 5V). Le DroTek GPS occupe déjà l'UART matériel (PL011, `ttyAMA0`) en GPIO. Pas de level shifter ni de câble Celestron #93920 dans le tiroir au moment de la décision.

**Décision** : interfacer le HC par un dongle USB-TTL **CP2102** (sélecteur sur **5V**) branché côté Pi sur un port USB libre, et côté HC sur un bornier maison RJ12 6P6C. Le HC apparaît en `/dev/ttyUSB0`. Les broches RX/TX/GND sont câblées 3↔TX-dongle / 4↔RX-dongle / 5↔GND ; broche 2 **non connectée** (peut exposer +12 V selon HC, à valider au multimètre).

**Rationale** : (1) zéro conflit avec le GPS (qui garde l'UART matériel pour lui), (2) coût équivalent à un level shifter + câble UART, (3) compatible avec le standard INDI (`/dev/ttyUSBx`), (4) chaud-débranchable contrairement au GPIO. Câblage et avertissements : [`docs/technical/hardware.md`](../technical/hardware.md). _(ADR supersédée le 2026-07-05 — pivot ESP32 ; le dongle USB-TTL ne fonctionne pas sur ce bus single-wire.)_

---

## 2026-05-05 — Abandon du versioning v0.X, passage à un train de macro-étapes

**Contexte** : la roadmap était structurée en versions numérotées (v0.1 livrée, v0.2 Setup, …, v0.7 Astrophoto), avec la philosophie "chaque version = un livrable utilisable en session réelle". Au fil des sessions, plusieurs effets non désirés sont apparus : (1) le découpage forçait à laisser des étapes derrière dès qu'un blocage hardware tombait (cas concret : v0.2 Setup bloquée par l'attente du dongle CP2102 → impossible d'avancer le compass/ADXL sans rebattre l'ordre, alors que d'autres cards Setup ne dépendent pas du dongle), (2) la promesse "version = livrable" devenait fictive quand il fallait sortir des morceaux non livrés en bricolant des sous-versions, (3) la moindre réorganisation (déplacer une étape entre versions) demandait une mise à jour cross-fichiers (roadmap, backlog, journal, ADRs, specs).

**Décision** : abandon de la numérotation v0.X. La roadmap devient un **train d'étapes atomiques regroupées en macro-étapes** thématiques (Socle, Migration INDI, Setup, Mise en station + GoTo basique, Catalogue intelligent, Caméras + plate solving, Focus + MES complète, Astrophoto, plus des fils transverses). Une étape se déplace ; une macro est "done" quand le télescope reste utilisable end-to-end à la fin (la discipline "livrable utilisable" est conservée mais au niveau macro, pas étape).

**Rationale** : le train d'étapes est trivial à réordonner quand un blocage hardware tombe — on déplace l'étape concernée à la fin de la macro, on continue. Les macros restent assez grosses pour porter la discipline "ne jamais shipper un état cassé" (Macro 4 garde le jalon explicite "parité raquette Celestron atteinte"). Les commits, journal et ADRs antérieurs continuent de référencer `v0.X` — ces noms sont historiques et ne sont pas réécrits. La roadmap [`roadmap.md`](roadmap.md) est désormais l'unique source de vérité ; CLAUDE.md la résume et impose sa mise à jour à chaque livraison d'étape.

---

## 2026-05-04 — Stack INDI installée via repo Astroberry Debian Trixie arm64

**Contexte** : exécution de la Task 0 du plan migration INDI (Session 15). Trois sources possibles pour `libindi` 2.x + `indi_celestron_aux` sur Pi 3 B+ Debian Trixie arm64 : (1) compilation source `indi-3rdparty`, (2) PPA officielle `ppa:mutlaqja/ppa`, (3) repo Astroberry. La compilation source à `-j3 / -j4` finit par tourner mais reste laborieuse sur 1 GB RAM même avec swap, et n'apporte rien tant qu'on ne patche pas le driver. La PPA mutlaqja `ppa.launchpadcontent.net:443` rejette activement les TCP depuis ce Pi (reset 47 ms IPv4 et IPv6, le reste du net OK) — pas exploitable aujourd'hui. Le repo Astroberry "old" `astroberry.io/repo/` est mort (404). Le repo "new" `astroberry.io/debian/` est documenté sur `indilib.org/download/raspberry-pi.html`, actif, signé GPG, et fournit `libindi 2.2.0` + `indi-celestronaux 1.5` + `indi-gpsd 0.6` pour Trixie arm64.

**Décision** : utiliser le repo Astroberry `https://astroberry.io/debian/` (suite `trixie`, composant `main`, archi `arm64`) comme source apt pour les paquets INDI sur le Pi. Source au format deb822 dans `/etc/apt/sources.list.d/astroberry.sources`, clé GPG dans `/etc/apt/keyrings/astroberry.gpg`. Paquets installés : `indi-bin`, `indi-celestronaux`, `indi-gpsd`, `libindi-dev`.

**Rationale** : (1) install en < 2 min, 0 conflit avec Debian Trixie (0 `apt-pin` requis, seules deps Debian tirées : `libxisf0`, `librtlsdr0`), (2) versions cohérentes avec la cible (`libindi 2.2.0`, plus récente que la 1.9.9 de Trixie qui ne contient pas le driver AUX), (3) repo restreint au scope INDI (pas tout l'écosystème astrophoto Astroberry, donc empreinte raisonnable malgré le RAM 1 GB), (4) déblocage du chantier migration sans dépendre de la PPA inaccessible. Compilation source restera l'option de fallback **uniquement** si on doit patcher upstream (typiquement les opcodes `MC_*_BACKLASH` mount-axis manquants dans `auxproto.h`). Détail repro Session 15 du journal : `docs/project/journal.md`.

---

## 2026-05-09 — Retrait des courses AZ logicielles (Macro 2)

**Contexte** : la roadmap Macro 2 prévoyait des "Courses AZ min/max (software, persistant Pi-side)" en miroir des courses ALT livrées Session 19. La capture des bornes AZ posait un problème de spec : aucun capteur tube ne donne la position AZ (le compass LIS3MDL est sur la base, pas sur le tube), et la valeur n'a de sens qu'avec une monture branchée — ce qui ramènerait le travail dans la dépendance dongle CP2102.

**Décision** : retirer "Courses AZ logicielles" du train d'étapes Macro 2. Le cordwrap (Slice D, mount-side) couvre le besoin réel d'empêcher la torsion des câbles en azimut. La compensation côté GoTo (Macro 3) prend la responsabilité d'éviter que la monture fasse plus d'un tour sur elle-même pour atteindre une cible — path planning AZ avec recherche du plus court chemin angulaire respectant la zone cordwrap configurée.

**Rationale** : (1) deux mécanismes redondants pour la même contrainte physique = surface d'erreur inutile, (2) les courses ALT existent à cause d'une butée mécanique tube/monture ; en AZ il n'y a pas de butée mécanique sur la Celestron, juste un risque de torsion câbles que le cordwrap gère nativement, (3) la responsabilité "ne pas faire trop de tours" se gère mieux dans le calcul de trajectoire GoTo (position courante AZ + cible AZ + zone cordwrap connues) que dans une borne min/max statique appliquée à l'envers.

**Conséquence** : la ligne GoTo de Macro 3 dans `roadmap.md` intègre désormais explicitement la contrainte de path planning AZ minimisant la rotation cumulée.

---

## 2026-05-10 — Wizard 3 étoiles : sync natif INDI, modèle SVD comme indicateur qualité

**Contexte** : la spec wizard 3 étoiles (`docs/superpowers/specs/2026-05-09-wizard-3star-alignment-design.md`, exécutée plan `2026-05-09-wizard-3star-alignment.md`, T1→T22 livrés Session 22) construit un modèle de transformation `(sky_az, sky_alt) ↔ (mount_az, mount_alt)` via SVD côté backend, persisté dans `state.db`. Ce modèle a été conçu comme **source de vérité** pour le futur GoTo (Macro 3 #3) : `goto_service` aurait appliqué la transformée localement puis envoyé du raw `mount.goto(mount_az, mount_alt)`. Aucun appel à un sync mount-side n'était prévu.

Cette approche entre en contradiction directe avec le rationale de la migration INDI (ADR 2026-05-01 + spec `2026-05-01-mount-indi-design.md`) qui motive INDI précisément par l'accès à l'**interface native Celestron** — alignement, sync, tracking, cordwrap, backlash — en plus du futur écosystème caméras. La spec INDI cite explicitement `sync_radec(ra, dec)` via `ON_COORD_SET=SYNC` + `EQUATORIAL_EOD_COORD` comme livrable v0.3 (ligne 97). En construisant un modèle parallèle, on dédoublait la fonction d'alignement et on se privait du tracking sidéral natif (essentiel sur monture alt-az : les vitesses AZ/ALT à appliquer dépendent de la position visée en RA/Dec, calculées par le driver).

**Décision** : repositionner le wizard pour s'appuyer sur le sync natif Celestron via INDI, et requalifier le modèle SVD en indicateur de qualité.

1. À chaque `AlignmentService.record(idx)`, en plus de stocker la paire `(sky, mount)`, pousser `EQUATORIAL_EOD_COORD = (sky_ra, sky_dec)` avec `ON_COORD_SET=SYNC` côté `MountIndiAdapter`. Après les 3 syncs, le driver `indi_celestron_aux` construit son modèle interne (équivalent NexStar 3-stars).
2. Le futur GoTo (Macro 3 #3) utilise INDI standard : set `EQUATORIAL_EOD_COORD = (target_ra, target_dec)` avec `ON_COORD_SET=TRACK`. Le driver gère le slew + tracking. Plus de tracking maison à écrire.
3. Le tracking sidéral livré Macro 0 (qui fonctionnait via une zero-pose implicite du driver) bénéficie automatiquement du modèle après les 3 syncs.
4. Le modèle SVD reste calculé et persisté dans `state.db`, mais **change de rôle** : sanity check / RMS / résiduels / détection outlier / diagnostic UX (`ValidationScreen`). Il n'est plus consommé par `goto_service`. La transformée `(sky_az, sky_alt) ↔ (mount_az, mount_alt)` reste utile au moment du wizard pour valider que les 3 captures sont cohérentes avant de finaliser, et fournit un RMS chiffré que le driver Celestron n'expose pas.

**Rationale** :

1. **Cohérence avec la migration INDI** : on adopte INDI précisément pour profiter des capacités natives ; bypasser l'alignement natif annule la moitié du bénéfice et oblige à réécrire en software ce que le driver fait déjà (tracking alt-az, GoTo, gestion cordwrap couplée à la position).
2. **Tracking sidéral correct** : sur alt-az, le tracking sans alignement n'a aucune chance d'être juste à plus de quelques minutes. En délégant au driver, on hérite directement de son modèle 3-stars et de ses corrections de cone error si on les active plus tard.
3. **Compatibilité écosystème** : tout l'outillage tiers (KStars/Ekos pour debug, plate solving INDI standard en Macro 5, PHD2 Macro 7) attend une monture alignée au sens INDI. Si la monture reste "non-alignée" du point de vue du driver, ces outils ne trouveront pas la cible attendue.
4. **Le modèle SVD garde de la valeur** : le driver Celestron n'expose pas le RMS de son modèle, n'a pas de notion d'outlier, n'a pas de diagnostic UI. Notre modèle SVD calculé en parallèle devient un indicateur de qualité qu'aucune lib externe ne fournit, et reste affiché à l'utilisateur sur `ValidationScreen` (tout le wizard UX livré est conservé tel quel).
5. **Coût de bascule faible** : ~1 méthode à ajouter dans `MountIndiAdapter` (`sync_radec`), 1 appel à câbler dans `AlignmentService.record()`, mise à jour de la spec wizard et du checklist d'intégration. Aucun changement Flutter. Tests à étendre côté backend pour vérifier le push INDI.

**Conséquences** :

- Spec `docs/superpowers/specs/2026-05-09-wizard-3star-alignment-design.md` à amender pour acter le double rôle (sync natif + indicateur SVD). Section "Architecture du modèle" à réécrire.
- `MountService` interface à étendre avec `sync_radec(ra, dec)` (déjà listé v0.3 dans la spec INDI, on le tire en avant).
- Roadmap Macro 3 #3 (GoTo réel) à reformuler : "set `EQUATORIAL_EOD_COORD` avec `ON_COORD_SET=TRACK`" remplace "appliquer la transformée SVD puis raw goto".
- Smoke test post-dongle (checklist d'intégration) à enrichir d'un check explicite "après wizard, la monture est `is_aligned=true` côté INDI" et "tracking sidéral garde la cible centrée 5 min sans correction".
- Macro 1 INDI : la livraison de `sync_radec` devient un livrable de Macro 1 (pas de Macro 3). Le smoke test E2E migration INDI doit valider le sync.

**Travail T1→T22 livré** : conservé en l'état. Le wizard fonctionne tel quel. Le repositionnement se fera lors de la reprise de la Macro 3 #2 (un slice court : ajout du `sync_radec` dans l'adapter, branchement dans `AlignmentService.record`, mise à jour spec + checklist + tests). Tracé dans le journal Session 22 + suivi via une étape dédiée à insérer dans la roadmap.

---

## 2026-04-30 — Arborescence de docs en 3 vues

**Décision** : `docs/INDEX.md` référence trois vues — `technical/`, `project/`, `product/`. Chaque vue a un `README.md` index, et regroupe des docs courts et ciblés (1 sujet = 1 fichier).

**Rationale** : faciliter la navigation et minimiser le contexte chargé à chaque session. Un long document monolithique est dur à maintenir et oblige à charger trop de contexte. Trois angles de lecture (technique / projet / produit) couvrent les besoins du dev hybride humain + IA.

---

## 2026-07-05 — Pont ESP32 WiFi↔bus AUX (dérogation à « pas d'Arduino »)

**Contexte** : la liaison Pi↔monture prévue par l'ADR du 2026-05-01 (dongle USB-TTL CP2102 sur le port HAND CONTROL) n'a jamais fonctionné. Le fil matériel S26→S36 (~10 sessions, archives `2026-06-bus-aux.md` + journal S33+) a établi, recherche de fond à l'appui, que le port HC de la base SLT expose le **bus AUX interne single-wire half-duplex** (un seul fil DATA, 19200 8N2, TX et RX partagés, idle tiré HIGH par le pull-up monture ~139 k) — **pas** une paire RX/TX séparée. Sur un tel bus, chaque appareil surveille l'**écho non déformé** de sa propre émission ; tout tap qui n'est pas réellement haute-Z **charge/déforme la ligne** (les diodes de clamp d'un GPIO 3,3 V face au bus 4,4 V conduisent) → réponses moteur tuées **et** raquette en « No Response ». Le dongle (CP2102 puis CH340) perturbe le bus de façon non découplable passivement (diviseurs, résistances série, pull-ups bridés : tous tranchés en impasse S27→S32). Le circuit de référence éprouvé (Mark Lord rtr.ca / g7ltt HBG3, module SkyPortal WiFi officiel) confirme qu'il faut un **buffer tri-state actif @ 5 V** + suppression d'écho firmware, et que les contrôleurs moteurs répondent **sans la raquette** (archi voulue du driver `indi_celestron_aux`).

**Décision** : interposer un **ESP32 (DevKit CP2102)** entre le Pi et le bus AUX, comme **pont WiFi↔série** exposant le bus en **TCP port 2000** — exactement le mode « Celestron WiFi / SkyPortal » que le driver `indi_celestron_aux` pilote nativement (`CONNECTION_MODE=TCP`, `DEVICE_ADDRESS=192.168.1.200:2000`). L'ESP32 porte l'**interface électrique** sur le bus single-wire : **TX** par buffer tri-state **74AHCT125** (drive push-pull actif HIGH+LOW, 470 Ω série, `/OE` piloté par GPIO32, relâché immédiatement après `flush()` pour éviter la collision de turnaround), **RX** par **comparateur LM2902** (entrée haute-Z 1M/1M, seuil ~0,9 V, renifle sans charger ni sur-piloter). Firmware `firmware/esp32-aux-bridge` : suppression d'écho half-duplex par comptage, robustesse WiFi (reconnect + watchdog + IP fixe), OTA (flash par WiFi). Cela **déroge à l'ADR du 2026-04-15 « pas d'Arduino »** et **supersède l'ADR du 2026-05-01 (dongle CP2102)**.

**Rationale** :
1. **C'est la seule voie qui marche** — validée bout en bout au jalon C (2026-07-05, S37) : le driver dialogue avec la vraie monture (handshake, lecture encodeur, slew réel bidirectionnel). Toutes les alternatives passives ont été épuisées méthodiquement.
2. **La dérogation est mineure sur le fond de l'ADR d'origine** : « pas d'Arduino » visait à ne pas ajouter une couche série redondante pour le temps-réel moteur. L'ESP32 **ne fait pas de temps-réel moteur** (les MC internes s'en chargent) — il est un **transceiver/pont de liaison physique**, rôle qui n'existait pas dans le design initial (on croyait le port HC directement pilotable en TTL série standard).
3. **Aligné avec la stack INDI** : le mode Network du driver est prévu pour ça (module SkyPortal officiel), donc zéro code custom de protocole — le driver gère le binaire AUX, le pont ne fait que relayer les octets.
4. **Bénéfice collatéral** : le WiFi supprime le câble Pi↔monture et l'OTA supprime le cycle de reflash physique.

**Conséquences** :
- ADR 2026-04-15 (« pas d'Arduino ») annoté « dérogé » ; ADR 2026-05-01 (dongle CP2102) annoté « supersédé ».
- Reste avant clôture Macro 1 : valider end-to-end via le backend (`pyindi-client` → `indiserver` → pont), un client backend flappe actuellement sur `indiserver` (à investiguer).
- Câblage de référence : [`docs/technical/cablage-interface-aux.html`](../technical/cablage-interface-aux.html) + [`cablage-pont-esp32.html`](../technical/cablage-pont-esp32.html). Firmware : `firmware/esp32-aux-bridge`.

---

## 2026-07-08 — Backlash mount-side différé hors Macro 2 (dépend d'un fork driver)

**Contexte** : Macro 2 (Setup) listait « Backlash compensation ALT + AZ (mount-side) » comme dernier item, historiquement bloqué par la liaison monture (dongle CP2102). Macro 1 étant bouclée (S37, pont ESP32), le blocage liaison est levé — mais la vérification du driver installé sur le Pi (`indi-celestronaux` **v1.5**, `indi-bin 2.2.0`) montre que le binaire n'expose **que** `FocuserInterface::SetFocuserBacklash` : **aucune propriété `MOUNT_AXIS_BACKLASH`, aucun `MC_*_BACKLASH` d'axe**. Le code adapter backend (`get_backlash`/`set_backlash` via le vecteur `MOUNT_AXIS_BACKLASH`) est déjà écrit et testé, mais `set_backlash` lève volontairement `RuntimeError` tant que le driver n'advertise pas la propriété. Exposer le backlash d'axe exige donc un **fork + patch C++ du driver** (~70 lignes : commandes `MC_SET_POS/NEG_BACKLASH` + propriété INDI), puis build/install sur le Pi.

**Décision** : **sortir le backlash mount-side du train Macro 2** et le rattacher à **Macro 5** (caméras + guidage), où il apporte sa valeur réelle. Macro 2 est déclarée **done** sur son critère (calibrations/courses/configs accessibles depuis l'app + persistées + permettent un alignement avec confiance) sans le backlash. Les cartes Setup 5/6 restent visibles mais marquées « Reporté — Macro 5 » (placeholders inertes) ; le code adapter + les 5 tests sont **conservés en l'état** (prêts pour le jour où le driver est patché).

**Rationale** :
1. **Le backlash ne paie qu'en imaging/guidage** (GoTo précis, dithering) — inutile pour manuel + 3 étoiles + GoTo basique (Macro 3). La roadmap le classait déjà 🌫 « différable, le driver fonctionne sans ».
2. **Le vrai coût est du C++ driver, pas de l'app** : forker/builder `indi_celestron_aux` est une tâche de la famille « stack INDI » (comme le pivot ESP32), pas du chantier Setup. La ranger sous Macro 5 évite de dépenser une session de C++ dont le bénéfice n'arrive qu'à Macro 5.
3. **Aucun code jeté** : l'adapter et ses tests restent ; seul le câblage REST/UI/persistance est reporté avec le patch driver.

**Conséquences** :
- Roadmap : item backlash retiré de Macro 2, ajouté à Macro 5 (« Backlash mount-side ALT/AZ — fork driver `MC_*_BACKLASH` + REST + UI »). Macro 2 marquée done.
- Setup : cartes 5/6 « Reporté — Macro 5 » ; carte 7 (cordwrap) reste « À implémenter » (indépendante, le driver la gère).
- Le fork driver reste noté comme prérequis dans Macro 5.
