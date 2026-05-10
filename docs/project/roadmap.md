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
- 🌫 Passe physique mount-branchée (sections 3 et 7 de `backend/deploy/INTEGRATION_CHECKLIST.md`) — fermable une fois Macro 1 validée sur dongle.

---

## Macro 1 — Migration INDI 🚧

Refonte technique du `MountAdapter` pour pivoter de `nexstarpy` vers la stack INDI (`indiserver` + `indi_celestron_aux` + `pyindi-client`). Pas de nouvelle feature côté Flutter — l'API REST/SSE reste identique. Pré-requis aux macros suivantes (backlash, cordwrap, sync RA/Dec, `is_aligned`, `goto_in_progress`).

- ✅ Stack INDI installée sur le Pi (repo Astroberry Trixie arm64) — voir ADR 2026-05-04
- ✅ Backend refactor `MountAdapter` INDI + bus thread-safe (89/89 tests verts)
- ✅ `MountService.sync_radec(ra_deg, dec_deg)` (`ON_COORD_SET=SYNC` + `EQUATORIAL_EOD_COORD`) — livré 2026-05-10 (alimente le modèle natif Celestron pour Macro 3 #2, cf. ADR 2026-05-10)
- ⛔ Smoke test E2E sur dongle CP2102 + monture branchée (en attente livraison dongle)
- 🌫 Fork upstream patch backlash mount-axis (`MC_*_BACKLASH`, ~70 lignes C++) — différable, le driver fonctionne sans

*Done quand* : Macro 0 reste fonctionnelle, monture pilotée via INDI, `nexstarpy` retiré du backend.

Spec : [`docs/superpowers/specs/2026-05-01-mount-indi-design.md`](../superpowers/specs/2026-05-01-mount-indi-design.md). Onboarding : [`docs/technical/indi-reference.md`](../technical/indi-reference.md).

---

## Macro 2 — Setup

Page Setup unifiée + toutes les calibrations et configurations préalables à un alignement sérieux. Pré-requis : Macro 1.

- ✅ Page Setup unifiée (hub des cards) — scaffold Session 14
- ✅ Slice INFRA backend (sqlite `state.db` + repos calibration/limits) — livré 2026-05-05 (Session 17)
- ✅ Calibration ADXL345 monture (item #1 — niveau monture, planéité absolue) — livré 2026-05-07 (Session 18)
- ✅ Calibration compass LIS3MDL (item #2 — soft-iron offsets, heading tilt-compensé via fusion ADXL co-localisé) — livré 2026-05-07 (Session 18)
- ✅ Calibration ADXL345 tube (item #3 — zéro ALT, tube horizontal) — livré 2026-05-07 (Session 18)
- ✅ Courses ALT min/max (alimentées par ADXL345 tube, anti-collision) — livré 2026-05-07 (Session 19)
- 📦 Backlash compensation ALT + AZ (mount-side, **bloqué dongle CP2102**)
- ✅ Network/IP config — livré Session 14 (carte #8 Setup)
- ✅ À propos (versions, IP, uptime) — livré 2026-05-07 (Session 19)

*Done quand* : toutes les calibrations/courses/configs sont accessibles depuis l'app, valeurs persistées, et permettent de tenter un alignement avec confiance.

Spec validée : [`docs/superpowers/specs/2026-05-01-astro-brain-v02-setup-design.md`](../superpowers/specs/2026-05-01-astro-brain-v02-setup-design.md). Plan : [`docs/superpowers/plans/2026-05-04-v02-setup-implementation.md`](../superpowers/plans/2026-05-04-v02-setup-implementation.md).

Optionnels à arbitrer plus tard : slew rates personnalisés, cone error, PEC.

---

## Macro 3 — Mise en station + GoTo basique

Première mise en station effective, GoTo réel, catalogue d'objets brillants. Hub central remplace le HomeScreen comme landing post-Splash. Pré-requis : Macro 2.

- ✅ Hub central (landing post-Splash, 4 cartes Manuel / Setup / Status / À propos) — livré 2026-05-08 (Session 20)
- 🚧 Wizard alignement 3 étoiles assisté capteurs (compass + tilt + GPS pour pré-pointage, validation auto via résiduel SVD < ~1°, fallback manuel) — software livré 2026-05-10 (Session 22, backend + Flutter, 180 tests app + tests backend), validation matérielle bloquée dongle CP2102 (Macro 1)
- 📦 GoTo réel (`/goto {ra_deg, dec_deg}` sur monture alignée — set `EQUATORIAL_EOD_COORD` avec `ON_COORD_SET=TRACK`, le driver gère slew + tracking sidéral natif) — statut `goto_in_progress` exposé via SSE
- 🚧 Catalogue minimal backend : tranche A (stars étendues IAU CSN cap mag 3, 140 entrées) livrée 2026-05-10 — tranches Messier + planètes (skyfield) à suivre
- 📦 Page Catalogue minimal (recherche/sélection + GoTo)

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
- **Night planner offline** (snapshot/cache) : à cliper sur la macro qui héberge le planner — à déterminer.

---

## Notes

Cette roadmap remplace celle versionnée v0.1–v0.7 (abandonnée 2026-05-05, voir ADR du même jour). Le contenu est conservé, simplement réorganisé en macro-étapes ordonnables. Les commits, journaux et ADRs antérieurs continuent de référencer les noms `v0.X` historiquement — c'est normal.
