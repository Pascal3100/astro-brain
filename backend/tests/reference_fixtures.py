"""Builder d'un petit `reference.sqlite` v2 pour les tests (SQL brut, temp).

Ne dépend pas de `oracle/`. Valeurs choisies pour rendre l'interpolation et la
visibilité déterministes (voir SP2 plan, Task 3).
"""
from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

FIX_NOW = datetime(2026, 8, 9, 12, 0, 0, tzinfo=UTC)

_SCHEMA = """
CREATE TABLE meta (schema_version INTEGER NOT NULL, generated_at TEXT NOT NULL,
  mpc_epoch TEXT, window_start TEXT NOT NULL, window_end TEXT NOT NULL,
  skyfield_kernel TEXT);
CREATE TABLE objects (id TEXT PRIMARY KEY, kind TEXT NOT NULL, name TEXT,
  designation TEXT);
CREATE TABLE fixed_object (object_id TEXT PRIMARY KEY REFERENCES objects(id),
  ra_deg REAL NOT NULL, dec_deg REAL NOT NULL, apparent_mag REAL,
  object_type TEXT, size_arcmin REAL, constellation TEXT, messier TEXT,
  ngc_ic TEXT);
CREATE TABLE ephemeris (object_id TEXT NOT NULL REFERENCES objects(id),
  sample_utc TEXT NOT NULL, ra_deg REAL NOT NULL, dec_deg REAL NOT NULL,
  earth_dist_au REAL, sun_dist_au REAL, apparent_mag REAL, illumination REAL,
  constellation TEXT, PRIMARY KEY (object_id, sample_utc));
CREATE INDEX idx_ephem_time ON ephemeris(sample_utc);
CREATE TABLE comet_elements (object_id TEXT PRIMARY KEY REFERENCES objects(id),
  epoch_jd REAL, perihelion_q_au REAL NOT NULL, eccentricity REAL NOT NULL,
  inclination_deg REAL NOT NULL, arg_perihelion_deg REAL NOT NULL,
  node_deg REAL NOT NULL, mag_h REAL, mag_k REAL);
"""

_OBJECTS = [
    ("star:HIP91262", "star", "Vega", "α Lyr"),
    ("NGC1976", "dso", "Orion Nebula", "NGC 1976"),
    ("planet:mars", "planet", "Mars", None),
    ("moon", "moon", "Moon", None),
    ("sun", "sun", "Sun", None),
    ("comet:CK20N020", "comet", "NEOWISE", "C/2020 N2"),
]

# Vega : ra=279.23, dec=+38.78 (au-dessus de l'horizon depuis Paris, été)
# M42 : ra=83.82, dec=-5.39, messier M42
_FIXED = [
    ("star:HIP91262", 279.23, 38.78, 0.03, "star", None, "Lyr", None, None),
    ("NGC1976", 83.82, -5.39, 4.0, "nebula", 85.0, "Ori", "M42", "NGC1976"),
]

# Échantillons journaliers. Mars : ra 149.0→152.0 (+1/j), dec 10.0→13.0 (+1/j)
# sur 08→11 août → à FIX_NOW (09 12:00) ra=150.5, dec=11.5.
def _ephem_rows() -> list[tuple]:
    days = ["2026-08-08", "2026-08-09", "2026-08-10", "2026-08-11"]
    rows: list[tuple] = []
    for i, day in enumerate(days):
        ts = f"{day}T00:00:00Z"
        rows.append(("planet:mars", ts, 149.0 + i, 10.0 + i, 0.5, 1.5, -1.2,
                     None, "Cnc"))
        rows.append(("moon", ts, 200.0 + i, -10.0 + i, None, None, -12.0,
                     0.6 + 0.01 * i, "Vir"))
        rows.append(("sun", ts, 138.0 + i, 16.0 - i, None, None, -26.7,
                     None, "Leo"))
        rows.append(("comet:CK20N020", ts, 45.0 + 2 * i, 20.0 + i, None, None,
                     11.5, None, "Ari"))
    return rows


def build_reference_v2(path: Path) -> None:
    con = sqlite3.connect(path)
    try:
        con.executescript(_SCHEMA)
        con.execute(
            "INSERT INTO meta (schema_version, generated_at, window_start,"
            " window_end, skyfield_kernel) VALUES (?, ?, ?, ?, ?)",
            (2, "2026-08-09T00:00:00Z", "2026-08-08", "2026-10-07", "de421.bsp"),
        )
        con.executemany(
            "INSERT INTO objects (id, kind, name, designation)"
            " VALUES (?, ?, ?, ?)",
            _OBJECTS,
        )
        con.executemany(
            "INSERT INTO fixed_object (object_id, ra_deg, dec_deg, apparent_mag,"
            " object_type, size_arcmin, constellation, messier, ngc_ic)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            _FIXED,
        )
        con.executemany(
            "INSERT INTO ephemeris (object_id, sample_utc, ra_deg, dec_deg,"
            " earth_dist_au, sun_dist_au, apparent_mag, illumination,"
            " constellation) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            _ephem_rows(),
        )
        con.commit()
    finally:
        con.close()
