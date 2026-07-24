# oracle/ — Astro-Brain reference data generator

Produces `reference.sqlite` (+ `manifest.json`) from a **GitHub Actions** cron
job. Runs **only in CI** — never on the Pi. `backend/` and `app/` consume the
published artifact; they never import from this package.

## What it does
Fetch MPC comet elements → skyfield ephemeris (daily apparent RA/Dec, of-date,
60-day rolling window) → SQLite → manifest.

## The contract (consumers read only this)
- `manifest.json`: `{ schema_version, generated_at, sqlite_url, sqlite_sha256,
  window_start, window_end }`. Poll it; download the SQLite only when
  `sqlite_sha256` changes. Refuse a `schema_version` newer than you support.
- `reference.sqlite`: tables `meta`, `comets`, `comet_ephemeris` (see
  `schema.sql`). **RA/Dec are apparent, of-date (JNow)** — consumers do only
  LST→alt/az. Daily samples → interpolate linearly.
- `predicted_mag` is an **estimate** (comet outbursts). Display as such; never
  a hard filter.

## Run locally
```bash
cd oracle && uv sync && uv run python -m oracle   # writes build_output/
```

## Publication
Release assets under the rolling tag `almanac-latest`. No binary is committed to
`main` (avoids history bloat).
