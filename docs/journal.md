# Journal de sessions - Astro-Brain DIY

## 2026-04-15 - Session 1 : Initialisation du projet

- Lecture de la documentation d'architecture hardware/software
- Création du `CLAUDE.md` avec la description du projet, la stack et les conventions
- Création du journal de sessions (`docs/journal.md`)
- Le projet est au stade de conception : la feuille de route est posée, pas encore de code

## 2026-04-15 / 2026-04-16 - Session 2 : Brainstorm et design v0.1

### Décisions d'architecture
- **Arduino retiré** de l'architecture : le Pi communique directement avec la monture, pas besoin d'intermédiaire
- **Port HC** (RS-232, protocole NexStar) choisi pour la communication monture — on remplace la raquette
- **nexstarpy** comme driver monture (protocole NexStar v1.2 complet)
- **REST uniquement** pour la v0.1 (pas de WebSocket) — le D-Pad fonctionne en start/stop
- **App Flutter native** sur téléphone (pas une PWA servie par le Pi)
- Le Pi gère la **sync GPS → monture automatiquement** au boot — l'app ne fait que lire l'état

### Design UI
- Style **HUD spatial** avec thème double : bleu (jour) / rouge (nuit, préservation vision nocturne)
- Un seul écran : status bar, télémétrie, D-Pad + slider vitesse, toggle tracking
- Switch jour/nuit dans la status bar
- Mockups validés via visual companion

### Matériel
- T7C pour l'imagerie principale (disponible)
- **Orion StarShoot Autoguider commandée** (40€) — plate solving + futur guidage
- **SVBONY SV165** choisie comme lunette guide
- PiCam écartée (problème de nappe rigide sur tube mobile)

### Roadmap définie
- v0.1 → v0.5, du joystick basique jusqu'au module astrophoto complet

### Config dev
- VS Code Remote-SSH configuré vers le Pi (astro-brain / pascal3100)
- Contexte 1M désactivé dans settings.json Claude Code

### Livrables
- Spec design v0.1 : `docs/superpowers/specs/2026-04-16-astro-brain-v01-design.md`
- CLAUDE.md mis à jour avec la nouvelle architecture

### Setup Pi
- Pi OS 64-bit Lite, install brute
- VS Code Remote-SSH configuré (astro-brain / pascal3100)
- `apt install python3-pip python3-venv gpsd gpsd-clients`
- venv créé : `~/astro-brain`
- Packages installés dans le venv : fastapi, uvicorn, nexstarpy, gpsd-py3, pyserial
- Contexte 1M désactivé dans settings.json Claude Code

### Prochaine session
- Écrire le plan d'implémentation v0.1
- Inspecter l'API nexstarpy sur le Pi (Python 3.13 disponible)
- Commencer l'implémentation
