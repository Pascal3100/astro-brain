"""Build the reference.sqlite artifact from comets + ephemeris rows."""

import sqlite3
from dataclasses import asdict, dataclass
from pathlib import Path

import pandas as pd

import oracle
from oracle.compute.ephemeris import EphemRow

SCHEMA_VERSION = 1


@dataclass(frozen=True)
class BuildMeta:
    """Provenance metadata stored in the ``meta`` table of the artifact."""

    schema_version: int
    generated_at: str
    mpc_epoch: str | None
    window_start: str
    window_end: str
    skyfield_kernel: str


def _schema_sql() -> str:
    """Return the DDL from ``oracle/schema.sql`` (one level above the package)."""
    return (Path(oracle.__file__).resolve().parent.parent / "schema.sql").read_text()


def _opt(row: pd.Series, key: str) -> float | None:
    """Return ``row[key]`` as a float, or ``None`` when missing/NaN."""
    value = row.get(key)
    return float(value) if pd.notna(value) else None


def build_reference_db(
    out_path: Path,
    comets: pd.DataFrame,
    ephem_rows: list[EphemRow],
    meta: BuildMeta,
) -> Path:
    """Write comets + ephemeris rows into a fresh ``reference.sqlite`` at ``out_path``."""
    if out_path.exists():
        out_path.unlink()
    con = sqlite3.connect(out_path)
    try:
        con.execute("PRAGMA foreign_keys = ON")
        con.executescript(_schema_sql())
        con.execute(
            "INSERT INTO meta (schema_version, generated_at, mpc_epoch, "
            "window_start, window_end, skyfield_kernel) VALUES "
            "(:schema_version, :generated_at, :mpc_epoch, :window_start, "
            ":window_end, :skyfield_kernel)",
            asdict(meta),
        )
        con.executemany(
            "INSERT INTO comets (id, designation, name, epoch_jd, perihelion_q_au, "
            "eccentricity, inclination_deg, arg_perihelion_deg, node_deg, mag_h, "
            "mag_k) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            [
                (
                    str(designation),
                    str(row.get("designation", designation)),
                    (str(row["name"]) if pd.notna(row.get("name")) else None),
                    _opt(row, "epoch_jd"),
                    _opt(row, "perihelion_distance_au"),
                    _opt(row, "eccentricity"),
                    _opt(row, "inclination_degrees"),
                    _opt(row, "argument_of_perihelion_degrees"),
                    _opt(row, "longitude_of_ascending_node_degrees"),
                    _opt(row, "magnitude_g"),
                    _opt(row, "magnitude_k"),
                )
                for designation, row in comets.iterrows()
            ],
        )
        con.executemany(
            "INSERT INTO comet_ephemeris (comet_id, sample_utc, ra_deg, dec_deg, "
            "earth_dist_au, sun_dist_au, predicted_mag, constellation) "
            "VALUES (?,?,?,?,?,?,?,?)",
            [
                (
                    r.comet_id,
                    r.sample_utc,
                    r.ra_deg,
                    r.dec_deg,
                    r.earth_dist_au,
                    r.sun_dist_au,
                    r.predicted_mag,
                    r.constellation,
                )
                for r in ephem_rows
            ],
        )
        con.commit()
    finally:
        con.close()
    return out_path
