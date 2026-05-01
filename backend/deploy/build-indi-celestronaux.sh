#!/usr/bin/env bash
# Build the patched indi_celestron_aux .deb on the Pi.
# Pre-req: ~/code/indi-3rdparty checked out on branch astro-brain-backlash.
set -euo pipefail

REPO="${HOME}/code/indi-3rdparty"
test -d "${REPO}" || { echo "Expected ${REPO} (clone of indilib/indi-3rdparty)"; exit 1; }
cd "${REPO}"

git fetch origin
git checkout astro-brain-backlash
git pull --ff-only origin astro-brain-backlash || true

mkdir -p build && cd build
cmake -DCMAKE_INSTALL_PREFIX=/usr -DCMAKE_BUILD_TYPE=Release -DCPACK_GENERATOR=DEB ..
make -j"$(nproc)" indi_celestron_aux
cpack -G DEB -D CPACK_PACKAGE_NAME=indi-celestronaux

DEB="$(ls -t indi-celestronaux*.deb | head -1)"
echo "Built: ${DEB}"
sudo apt install -y "./${DEB}"
sudo apt-mark hold indi-celestronaux

echo "Installed and held. Restart indiserver: sudo systemctl restart indiserver"
