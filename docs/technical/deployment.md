# Déploiement Pi

## Prérequis Pi OS

Pi OS 64-bit Lite (install fraîche). Voir [hardware.md](hardware.md) pour la config matérielle (UART, I2C, désactivation Bluetooth/serial-getty).

## Installation

```bash
# 1. Cloner le repo
mkdir -p ~/code && cd ~/code
git clone <url> astro-brain
cd astro-brain/backend

# 2. Installer uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# 3. Sync deps avec extra hardware
uv sync --extra hardware

# 4. Lancer en dev
uv run uvicorn astro_brain.main:app --host 0.0.0.0 --port 8000 --reload
```

## Service systemd

Service `astro-brain.service` actif sur le Pi (lancé au boot, restart-on-failure, logs vers journald).

```bash
# Status / logs
systemctl status astro-brain.service
journalctl -u astro-brain.service -f

# Redémarrage après pull
git pull && sudo systemctl restart astro-brain.service
```

## mDNS

Hostname : `astro-brain` (résolvable via `astro-brain.local` depuis tout client mDNS — `avahi-daemon` installé sur le Pi).

App Flutter :
- Défaut : `astro-brain.local:8000`
- Override possible via `--dart-define=PI_HOST=...` / `--dart-define=PI_PORT=...` (utile en dev pour tunnel SSH ou IP en dur).

## Accès SSH

```bash
ssh pascal3100@astro-brain
# clé SSH configurée dans ~/.ssh/config
```

## Workflow de déploiement

Aujourd'hui : édition workstation → commit/push → SSH Pi → `git pull && systemctl restart`.

À automatiser post-v0.2 (cf. backlog) : script `deploy.sh` ou cible Make.
