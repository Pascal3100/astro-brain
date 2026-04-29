# Roadmap

Philosophie : **chaque version = un livrable utilisable en session réelle**. On vise d'abord la parité avec la raquette Celestron (v0.1 → v0.4, sans caméra), puis on greffe la chaîne caméra/plate solve/guidage.

## v0.1 — Manuel + tracking ✓ (livré 2026-04-25)

Joystick D-Pad, tracking sidéral, GPS/heure auto au boot, app Flutter native, monorepo backend/app, service systemd.

Livré :
- Backend FastAPI 64 tests verts, service actif sur le Pi
- App Flutter 53 tests verts, smoke test téléphone fait (Moto g54 5G)
- mDNS `astro-brain.local:8000`, override via `--dart-define`

À fermer : passe physique avec monture branchée (sections 3 et 7 de `backend/deploy/INTEGRATION_CHECKLIST.md` — connecteurs en attente).

## v0.2 — Setup (réorganisation 2026-04-30)

Page Setup unifiée, prérequis pour pouvoir aligner et pointer proprement par la suite. Inclut :
- **Calibration compass LIS3MDL** (collecte soft-iron offsets, persistance disque)
- **Calibration ADXL345 monture** (zéro horizontal absolu)
- **Calibration ADXL345 tube** (zéro ALT, tube horizontal)
- **Courses ALT min/max** (alimenté par ADXL345 tube, safety anti-collision)
- **Courses AZ min/max** (software, persistant Pi-side)
- **Backlash compensation ALT + AZ** (tracking + GoTo plus précis)
- **Network/IP config** (host/port app, mode hotspot Pi)
- **À propos** (versions, IP courante, redémarrage service)

Optionnels à arbitrer : slew rates personnalisés (dépend de ce que NexStar expose), cone error / PEC (probablement pas dans v0.2).

## v0.3 — Mise en station + GoTo + catalogue minimal

- **Wizard d'alignement 3 étoiles** assisté par capteurs (compass + tilt + GPS) — 6 étapes, validation auto via résiduel SVD < ~1°
- **GoTo réel** (`/goto {ra_deg, dec_deg}` sur monture alignée)
- **Catalogue minimal** côté backend : Messier (110 objets) + planètes (skyfield) + ~50-100 étoiles brillantes (alignement)
- **Hub central** entre Splash et écrans feature, agrégateur d'entrées (Manuel, GoTo, Status…)

## v0.4 — Catalogue intelligent + setup tube (parité raquette atteinte)

- Catalogue complet (NGC, IC) + filtrage par tube (focale, diamètre, obstruction)
- Page "Setup tube" (focale, diamètre, obstruction)

## v0.5 — Caméras + Plate solving

- Stack INDI (drivers caméras + monture)
- Pipeline preview FITS → JPEG (auto-stretch, debayer, downsample)
- Page framing, machine d'état backend `idle / focus / guide / image`
- Astrometry.net local

## v0.6 — Focus + Mise en station complète

- Page focus live + HFR/FWHM, zoom ROI
- Wizard mise en station complet (option alignement par plate solve)
- Réglages techniques monture étendus (courses, backlash déjà en v0.2)

## v0.7 — Astrophoto

- Intégration PHD2 guidage
- Séquenceur de poses, dithering
- Autofocus périodique

## Notes

Cette roadmap remplace la version précédente. Le décalage de v0.2 vers Setup (vs alignement initialement) tient au constat qu'on ne peut pas faire d'alignement sérieux sans calibration capteurs ni courses ni backlash. Voir [decisions.md](decisions.md) pour le rationale.
