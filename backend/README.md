# Astro-Brain Backend

FastAPI backend that runs on the Raspberry Pi and controls the Celestron mount.

Dependencies are managed with [`uv`](https://docs.astral.sh/uv/). The lockfile (`uv.lock`) is committed for reproducibility.

## Dev setup (workstation)

```bash
cd backend
uv sync
uv run pytest
```

All tests run against fake services — no hardware required.

## Run locally with fakes

```bash
cd backend
uv run uvicorn astro_brain.main:app --reload --host 0.0.0.0 --port 8000
```

`ASTRO_BRAIN_HARDWARE=0` (default) wires in the fake adapters.

## Run on the Pi with real hardware

```bash
ssh astro-brain
cd ~/code/astro-brain/backend
uv sync --extra hardware
ASTRO_BRAIN_HARDWARE=1 uv run uvicorn astro_brain.main:app --host 0.0.0.0 --port 8000
```

The `[hardware]` extra pulls in `pyindi-client` (INDI client) and `smbus2` (I2C compass). GPS needs no package: the adapter speaks the gpsd JSON protocol over TCP directly. The mount is controlled via INDI (`MountIndiAdapter` / `indiserver`) through the ESP32 bridge that exposes the AUX bus on TCP 2000 — see `docs/technical/hardware.md`.

## Deployment (Pi, systemd)

See `deploy/install.sh` and `deploy/astro-brain.service` *(created in Task 16 of the backend plan)*.
