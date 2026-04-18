# Astro-Brain DIY

## Description du projet

Système de contrôle autonome pour télescope Maksutov Bresser 127/1900 sur monture Celestron. Le Raspberry Pi communique directement avec la monture (pas d'Arduino) et sert de backend pour une app Flutter sur téléphone.

## Documentation

- Architecture hardware initiale : `docs/architecture_hardware.txt`
- Spec design v0.1 : `docs/superpowers/specs/2026-04-16-astro-brain-v01-design.md`

## Stack technique

- **Backend** : FastAPI (Python 3.13) sur Raspberry Pi 3 B+
- **Frontend** : App Flutter native sur téléphone (pas une PWA)
- **Communication Pi <-> Monture** : nexstarpy via USB-série (port HC, protocole NexStar, 9600 baud)
- **GPS** : Module DroTek (USB sur Pi)
- **Plate Solving** (v0.2+) : Astrometry.net (local)

## Architecture

```
App Flutter (téléphone) --[Wi-Fi / REST]--> FastAPI (Pi) --[USB-série]--> Monture Celestron
                                                 │ USB
                                                 ▼
                                           DroTek GPS
```

- Pas d'Arduino dans la chaîne
- REST uniquement pour la v0.1 (WebSocket ajouté plus tard si besoin)
- Le Pi gère la sync GPS → monture automatiquement au boot

## Accès Pi

- Hostname : `astro-brain`
- User : `pascal3100`
- SSH configuré avec clé (`~/.ssh/config`)

## Roadmap

- **v0.1** : Joystick + tracking + GPS/heure
- **v0.2** : Focuseur + plate solving + alignement auto
- **v0.3** : GoTo + catalogue d'objets
- **v0.4** : Catalogue intelligent (filtrage visuel/photo selon le tube)
- **v0.5** : Module astrophoto (séquences, autofocus, guidage)

## Conventions

- Le journal de session est dans `docs/journal.md` — y consigner le résumé de chaque session de travail
- Les specs de design sont dans `docs/superpowers/specs/`
- Design UI : style HUD spatial, Material Design 3, thème bleu (jour) / rouge (nuit)
