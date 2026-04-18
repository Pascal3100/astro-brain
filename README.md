# Astro-Brain

Autonomous control system for a DIY astronomy setup — FastAPI backend on Raspberry Pi + Flutter app on phone.

Controls a Maksutov Bresser 127/1900 tube on a Celestron mount, talks to the mount via USB-serial (NexStar protocol) and reads GPS from a DroTek module.

## Structure

- `backend/` — Python/FastAPI backend that runs on the Raspberry Pi. Exposes REST commands (`/slew`, `/stop`, `/tracking`) and an SSE state stream (`/events`).
- `app/` — Flutter application installed on a phone. Joystick UI, system diagnostics, and (v0.3+) an observation planner. *(to come)*
- `docs/` — Specs, plans, journal, hardware architecture.

See `docs/superpowers/specs/` for design specs and `docs/superpowers/plans/` for implementation plans. Session-by-session progress lives in `docs/journal.md`.

## Roadmap

- **v0.1** — Joystick + tracking + GPS/time sync + system state stream
- **v0.2** — Motorized focuser + plate solving + auto-alignment
- **v0.3** — GoTo + object catalog + observation planner (offline-capable)
- **v0.4** — Smart catalog (visual/photo filtering per tube)
- **v0.5** — Astrophoto module (sequences, autofocus, guiding)
