#!/usr/bin/env bash
# Install or update the astro-brain systemd service on the Pi.
# Run this from the repository's backend/ directory on the Pi:
#   bash deploy/install.sh
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_DIR"

if ! command -v uv >/dev/null 2>&1; then
    echo "ERROR: 'uv' is not installed or not on PATH."
    echo "Install it first: curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

echo "Syncing Python dependencies with uv (hardware extra)..."
uv sync --extra hardware

echo "Installing systemd unit..."
sudo cp deploy/astro-brain.service /etc/systemd/system/astro-brain.service
sudo systemctl daemon-reload
sudo systemctl enable astro-brain.service
sudo systemctl restart astro-brain.service

echo "Status:"
sudo systemctl --no-pager status astro-brain.service || true
