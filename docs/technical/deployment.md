# Déploiement Pi

## Prérequis Pi OS

Pi OS 64-bit Lite (install fraîche). Voir [hardware.md](hardware.md) pour la config matérielle (UART, I2C, désactivation Bluetooth/serial-getty).

## Stack INDI (prérequis pour la monture, à partir de Macro 1)

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

# 2b. Rendre uv atteignable en SSH non-interactif
# L'installeur le pose dans ~/.local/bin, absent du PATH d'un `ssh pi '<cmd>'`
# (le early-return non-interactif de ~/.bashrc empêche tout export d'agir).
# /usr/local/bin, lui, y est toujours :
sudo ln -sf ~/.local/bin/uv /usr/local/bin/uv

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

# Si le pull touche les dépendances (pyproject.toml / uv.lock)
cd ~/code/astro-brain/backend && uv sync --extra hardware
```

Verbosité des logs : `ASTRO_BRAIN_LOG_LEVEL` (défaut `INFO`, configuré par
`main.py` — uvicorn ne configure que ses propres loggers). Le backend confirme
son niveau effectif au démarrage (`logging configuré au niveau INFO`), ce qui
permet de distinguer un journal muet d'un journal réduit au silence. `httpx` et
`httpcore` sont maintenus à `WARNING` sauf en `DEBUG` (ils loguent l'URL signée
complète de chaque requête, ~700 caractères pour la release Oracle).

Les migrations SQLite (`repository/migrations/_00N_*.py`) s'appliquent
automatiquement au démarrage du service. Certaines sont destructrices
(`DROP TABLE`, `DELETE`) et forward-only : sauvegarder `state.db` avant un
pull qui en apporte de nouvelles.

```bash
cp /var/lib/astro-brain/state.db /var/lib/astro-brain/state.db.bak-$(date +%F)
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

Le déploiement reste **manuel** à ce jour (Macros 0→3 livrées). L'automatisation (script `deploy.sh` ou cible Make) demeure un fil transverse ops non priorisé — cf. [backlog](../project/backlog.md).

## Driver INDI patché (backlash mount-axis)

Le driver upstream `indi_celestron_aux` n'expose pas le backlash mount-axis. Astro-Brain en utilise un fork patché jusqu'au merge de la PR upstream.

Procédure de (re)build sur le Pi :

```bash
~/code/astro-brain/backend/deploy/build-indi-celestronaux.sh
sudo systemctl restart indiserver
```

Le paquet est tenu (`apt-mark hold`) pour qu'`apt upgrade` ne l'écrase pas. Quand la PR upstream est mergée :

```bash
sudo apt-mark unhold indi-celestronaux
sudo apt update && sudo apt upgrade indi-celestronaux
```
