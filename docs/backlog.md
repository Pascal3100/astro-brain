# Backlog — Astro-Brain

Réflexions transverses et idées à creuser pour les versions post-v0.1. Rien ici n'est figé en spec ; l'objectif est de capturer les pistes pour ne pas les perdre et pouvoir les arbitrer plus tard.

Quand un sujet devient prêt à être conçu, il migre vers un spec dans `docs/superpowers/specs/`.

## Cartographie des pages Flutter par version

Vue d'ensemble pour éviter la dispersion au fil des specs. La roadmap canonique est dans `CLAUDE.md` ; cette section mappe les pages UI sur chaque version.

**v0.1** (en cours)
- *Dashboard / Contrôle* — joystick, tracking on/off, état monture, GPS/heure, stop d'urgence
- *Settings app* — URL backend, thème jour/nuit

**v0.2 — GoTo + alignement 3 étoiles**
- *Alignement 3 étoiles* — procédure guidée, exploite GPS + compass + niveau pour pré-pointer chaque étoile de référence
- Enrichissement du dashboard avec l'état d'alignement

**v0.3 — Catalogue intelligent + setup tube** (parité raquette atteinte ici)
- *Setup tube* — focale, diamètre, obstruction (prérequis du filtrage)
- *Catalogue* — recherche/sélection d'objet + filtrage visuel selon le tube, GoTo

**v0.4 — Caméras + Plate solving**
- *Configuration caméras* — 3 cams + lunette guide (pixel size, focale, gain, bin)
- *Framing / Plate solve* — snap, résultat coordonnées/orientation capteur overlay

**v0.5 — Focus + Mise en station complète**
- *Focus* — live loop, zoom ROI, HFR/FWHM, histogramme, optionnel Bahtinov
- *Mise en station* (wizard complet) — niveau, cap nord, alignement assisté par plate solve
- *Réglages techniques monture* — courses ALT/AZ, backlash

**v0.6 — Astrophoto**
- *Guidage* — graphe RA/DEC live, calibration PHD2, agressivité
- *Séquenceur* — plan de pose, dithering, progression, autofocus périodique

**Transverse (tout du long)**
- Overlay mode nuit rouge
- Indicateur global d'état (connecté Pi + mode actif : idle/focus/guide/image), bloque les actions incompatibles

## Page "Réglages techniques monture" (v0.5)

Paramétrage persistant côté Pi, exposé par l'app :

- **Courses min/max ALT/AZ** — safety pour éviter collision tube/trépied. Côté ALT : alimenté par l'ADXL345 tube (cf. section dédiée). Côté AZ : à traiter (probablement soft via position monture, pas de capteur dédié a priori).
- **Caractéristiques du tube** (focale, diamètre, obstruction) — prérequis pour filtrage catalogue (v0.4) et calculs FOV astrophoto (v0.5)
- **Compensation de backlash** — améliore tracking et futur GoTo (v0.3)
- **TODO : auditer la raquette Celestron** — passer en revue tous les menus/réglages techniques exposés par le hand controller (backlash, anti-backlash, cone error, PEC, filter limits, custom slew rates, etc.) pour identifier ce qu'il faut exposer/récupérer côté app et/ou lire/écrire via NexStar

## Configuration des caméras (v0.4)

Trois caméras dans le setup final, chacune avec ses paramètres propres :

- **Imageur principal** (T7C) : taille pixel, résolution, gain/offset, binning, temps d'expo par défaut
- **Caméra de guidage** (Orion StarShoot Autoguider) : taille pixel, résolution, agressivité/min-move du guidage
- **Plate solving** (même caméra que le guidage en pratique, sur la SV165) : résolution, échelle attendue (arcsec/pixel)
- **Lunette guide** (SV165) : focale — combinée au pixel size de la caméra guide → échelle d'image, indispensable pour calibrer le plate solver (v0.2) et le guideur (v0.5)

Ces réglages sont un prérequis direct du plate solving v0.4 — à spécifier dans le spec v0.4. Note : les caractéristiques du **tube** (focale, diamètre, obstruction) sortent plus tôt, en v0.3, car elles conditionnent le filtrage du catalogue intelligent.

## Stack caméras & guidage : Flutter télécommande + INDI/PHD2 headless (v0.4 / v0.6)

Décision d'archi à valider quand on attaquera le plate solving (v0.4) puis l'astrophoto (v0.6) : **ne pas réimplémenter le guiding/contrôle caméra dans Flutter**, orchestrer des outils matures côté Pi.

- **INDI server** sur le Pi : standard de l'écosystème astro Linux, drivers unifiés caméras (T7C, StarShoot) + monture. Tourne en headless.
- **PHD2 headless** (ou lin_guider) sur le Pi pour la boucle de guidage temps-réel (détection étoile, PID, dithering, calibration). PHD2 expose une API serveur (JSON-RPC sur TCP) → le backend FastAPI peut piloter start/stop/settings et relayer les events vers l'app.
- **Astrometry.net** local pour le plate solving, déjà prévu en v0.2.
- **App Flutter = télécommande** : pages de config (sélection caméra, expo, gain, bin, ROI, agressivité guiding), start/stop, graphe RA/DEC live, preview frames. Pas de logique image temps-réel dans l'app.

Pourquoi : PHD2 = ~15 ans de dev sur un problème difficile (traitement image temps-réel + boucle de correction). Réimplémenter en Dart/Flutter serait des mois de dev pour un résultat inférieur. Le tradeoff est que l'app devient un front pour des services Linux plutôt qu'une app "qui fait tout" — cohérent avec l'archi actuelle (Pi = backend, téléphone = UI).

**Décision prise** : tout passera par FastAPI (point de contrôle unique, pas de double surface d'API côté app). Le backend proxifie les commandes vers INDI et PHD2 et relaie leurs events via le flux SSE existant.

## Previews caméras (MAP, cadrage, framing) (v0.4 / v0.5)

Pipeline preview et framing basique : **v0.4**. Aides à la MAP (HFR/FWHM, zoom ROI, Bahtinov) : **v0.5**. À spécifier dans les specs correspondants.

- **Source** : INDI diffuse les frames en FITS via subscription BLOB sur le driver caméra. Backend FastAPI les capture à la demande (snap) ou en boucle courte (live loop, 1–3s d'expo).
- **Transformation côté Pi** : FITS → auto-stretch d'histogramme (type MTF/STF) → debayer si capteur couleur → downsample → JPEG/PNG. Ne jamais envoyer du FITS brut au téléphone (T7C ≈ 12 Mpx, ~24 Mo par frame — inutilisable en Wi-Fi).
- **Transport vers Flutter** : endpoint HTTP binaire (`GET /preview/{cam}/latest.jpg`) pour un snap, ou MJPEG stream pour le live loop. Pas besoin de SSE/WebSocket pour le binaire ; SSE reste pour les métriques (HFR, timestamp, expo utilisée).
- **Aides à la mise au point** dans l'UI :
  - Zoom sur ROI (star picking tactile, l'utilisateur tape sur une étoile)
  - **HFR / FWHM** calculés côté Pi et poussés dans l'event SSE → courbe live (descend = on tourne dans le bon sens)
  - Histogramme
  - Optionnel : analyseur de masque Bahtinov
- **Framing / cadrage** : snap simple + overlay des coordonnées du centre et de l'orientation du capteur une fois plate-solvé (v0.2).
- **Point d'archi subtil** : le live focus loop et le guidage PHD2 ne peuvent pas tourner simultanément sur la même caméra (un seul "client" possède le driver INDI à un instant T). Implique une **machine d'état côté backend** : `idle` / `focusing` / `guiding` / `imaging`, avec transitions propres et verrou par caméra. À poser dès v0.4 dans le modèle d'état, même si les modes `focusing`/`guiding` ne sont activés qu'en v0.5/v0.6.

## Assistant d'alignement optique (chercheur / lunette guide / tube principal) (v0.4, amorce possible v0.2)

Procédure casse-pieds à faire manuellement, typiquement en début de session, à refaire dès qu'on touche à la config optique. Un wizard dans l'app éviterait les allers-retours à tâtons.

**Ce qu'il faut aligner**
- **Chercheur** ↔ tube principal (Maksutov 127/1900)
- **Lunette guide SV165** (+ caméra de guidage/solver) ↔ tube principal
- Objectif : quand le tube principal vise un point, chercheur et guide voient le même point (au décalage près assumé)

**Version minimale (amorce possible dès v0.2/v0.3, pas de caméra requise)**
- Wizard texte : sélection d'une étoile brillante, slew de la monture vers la cible, instructions pas-à-pas ("centre dans l'oculaire", "regarde le chercheur, ajuste les vis jusqu'au centrage", etc.)
- Valeur ajoutée modeste mais non nulle : le backend peut au moins piloter le slew, chronométrer, et rappeler la séquence dans le bon ordre.

**Version complète (v0.4, après plate solving)**
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
- **Page "Niveau monture"** — bulle virtuelle XY, feedback rouge/vert < 0.5°. Probablement v0.2 (pré-session mise en station) ou v0.5 (wizard complet).
- **Page "Calibration tube"** — bouton "définir le zéro" quand tube horizontal + affichage live de l'angle + alerte à l'approche des butées. Probablement rattachée à la page "Setup tube" (v0.3) ou aux "Réglages techniques monture" (v0.5).

Cette décision remplace la piste IMU 9DOF évoquée ci-dessous : on n'a pas besoin d'un cap tilt-compensé pour le pointage, le plate solve v0.4 prendra le relais avec bien plus de précision.

## Position persistante + retour à l'origine (v0.4+)

- "Home position" définie physiquement par capteurs (distincte de l'alignement logique Celestron)
- Utilité : reprise après coupure, commande "retour à l'origine"
- À clarifier : peut-on lire directement la position depuis la monture via NexStar (`get_position`) une fois alignée, ou faut-il des encodeurs/capteurs externes indépendants ? Lien avec le plate solving v0.4 qui donnera aussi une position absolue.
- **Inclinaison** : tranché (cf. section "Capteurs d'inclinaison tube + monture" plus haut) → 2 × ADXL345. La piste IMU 9DOF (MPU6050/ICM-20948/BNO055) pour un cap tilt-compensé est écartée : le plate solve v0.4 fournira le pointage précis, on n'a pas besoin de reconstituer un cap absolu par capteurs.

## Safety & robustesse (v0.2+, continu)

- **Arrêt d'urgence** — bouton soft dans l'app (et/ou hardware GPIO) qui force un `stop` sur tous les axes, indépendamment du reste du système. Complément naturel des courses min/max. À concevoir comme un chemin de commande prioritaire, contournant la logique métier.
- **Logs persistants côté Pi** — journalisation structurée des commandes monture, transitions d'état, erreurs série/GPS, événements orchestrateur. Rotation (journald ou logrotate). Permet le post-mortem d'une session ("pourquoi le tracking a décroché à 22h13 ?"). À prévoir dès qu'on aura des sessions réelles.

## Ops & déploiement (à automatiser post-v0.1)

- **Service systemd** pour le backend — aujourd'hui `uv run uvicorn` est lancé à la main sur le Pi. Passer à une unit systemd (start au boot, restart on-failure, logs vers journald).
- **Déploiement backend** — script `deploy.sh` ou cible Make (SSH → `git pull && systemctl restart astro-brain`). Évite le workflow manuel actuel.
- **Mise à jour app Flutter** — pipeline build APK (+ TestFlight/iOS si concerné). À traiter séparément, pas via le Pi.

## Mode "Mise en station" (important — v0.2 puis v0.5)

Scindé en deux livraisons selon la nouvelle roadmap :

**v0.2 — version minimale (intégrée à l'alignement 3 étoiles)**
- **Cap nord** via compass (LIS3MDL DroTek) pour pré-pointer la première étoile
- **Niveau** : via l'ADXL345 monture (cf. section "Capteurs d'inclinaison tube + monture"). Bulle virtuelle dans l'UI, feedback < 0.5°. La bulle physique sur trépied reste un fallback manuel.
- **Alignement 3 étoiles** procédure NexStar assistée (le backend pilote le slew vers l'étoile proposée, l'utilisateur centre manuellement, valide, passe à la suivante)

**v0.5 — wizard complet**
- Même étapes mais réorchestrées comme assistant guidé end-to-end
- **Alignement par plate solve** (option alternative au 3-star) — centrage automatique après snap + solve
- UX critique : utilisé dans le noir, avec lampe rouge, parfois à l'aveugle → ergonomie soignée, instructions courtes, pas de couleurs vives en mode nuit
- Lien fort avec l'IMU (si ajouté), le compass, et le plate solving v0.4
