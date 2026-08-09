# oracle/ — Astro-Brain reference data generator

Produces `reference.sqlite` (+ `manifest.json`) from a **GitHub Actions** cron
job. Runs **only in CI** — never on the Pi. `backend/` and `app/` consume the
published artifact; they never import from this package.

## What it does
Fetch reference data (MPC comets, OpenNGC deep-sky, IAU-CSN named stars) +
de421 kernel (planets/Moon/Sun) → skyfield → SQLite v2 → manifest.
- **Fixed objects** (deep-sky, stars): one RA/Dec, apparent of-date (JNow).
- **Ephemeral objects** (comets, planets, Moon, Sun): daily apparent RA/Dec,
  of-date, 60-day rolling window. Interpolate linearly between samples.

## The contract (consumers read only this)
- `manifest.json`: `{ schema_version, generated_at, sqlite_url, sqlite_sha256,
  window_start, window_end }`. Poll it; download the SQLite only when
  `sqlite_sha256` changes. Refuse a `schema_version` newer than you support.
- `reference.sqlite` (`schema_version = 2`): tables `meta`, `objects`,
  `fixed_object`, `ephemeris`, `comet_elements` (see `schema.sql`). Every
  `fixed_object` / `ephemeris` / `comet_elements` row references `objects(id)`;
  `objects.kind` is one of `comet | planet | moon | sun | dso | star`.
  **All RA/Dec are apparent, of-date (JNow)** — consumers do only LST→alt/az.
- `apparent_mag` is **reliable for planets/luminaries** but an **estimate for
  comets** (outbursts). By convention, treat `kind = comet` magnitudes as an
  estimate; never a hard filter. `illumination` is set for the Moon/Venus/Mercury.
- The **base is complete and tube-agnostic**: no magnitude/size/type pre-filter
  is applied by the producer. Filtering "what my tube shows" is a consumer
  decision.
- `ngc_ic` and `designation` are **opaque catalogue ids**: do not assume they
  parse as `NGC<n>` / `IC<n>` — some rows are Messier-only or other-catalogue
  designations (e.g. M40, Mel22, ESO/PGC/UGC…).

## Run locally
```bash
cd oracle && uv sync && uv run python -m oracle   # writes build_output/
```

## Publication
Release assets under the rolling tag `almanac-latest`. No binary is committed to
`main` (avoids history bloat).
