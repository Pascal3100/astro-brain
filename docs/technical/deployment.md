# Déploiement Pi

## Prérequis Pi OS

Pi OS 64-bit Lite (install fraîche). Voir [hardware.md](hardware.md) pour la config matérielle (UART, I2C, désactivation Bluetooth/serial-getty).

## Stack INDI (prérequis pour la monture, à partir de v0.2)

Le backend pilote la monture via `indiserver` local + driver `indi_celestron_aux`. Paquets fournis par le repo Astroberry Trixie arm64 (cf. ADR 2026-05-04).

```bash
# Clé GPG + source apt (deb822)
sudo install -d -m0755 /etc/apt/keyrings
curl -fsSL https://astroberry.io/debian/astroberry-archive-keyring.asc \
  | sudo gpg --dearmor -o /etc/apt/keyrings/astroberry.gpg

sudo tee /etc/apt/sources.list.d/astroberry.sources >/dev/null <<'EOF'
Types: deb
URIs: https://astroberry.io/debian/
Architectures: arm64
Suites: trixie
Components: main
Signed-By: /etc/apt/keyrings/astroberry.gpg
EOF

sudo apt update
sudo apt install -y indi-bin indi-celestronaux indi-gpsd libindi-dev
sudo usermod -aG dialout pascal3100   # accès /dev/ttyUSB0 monture
```

Sanity check : `indiserver -v indi_celestron_aux` doit démarrer, écouter sur **port 7624**, et énumérer les math plugins SVD + Nearest. Service systemd dédié à câbler dans le plan migration INDI (cf. `docs/superpowers/plans/2026-05-01-mount-indi-migration.md`).

## Installation backend

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
