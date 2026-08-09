"""Build the reference.sqlite v2 artifact from the unified record model."""

import sqlite3
from dataclasses import asdict, dataclass
from pathlib import Path

import oracle
from oracle.records import CometElements, EphemRow, FixedRow, ObjectRow

SCHEMA_VERSION = 2


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


def build_reference_db(
    out_path: Path,
    objects: list[ObjectRow],
    fixed: list[FixedRow],
    ephem: list[EphemRow],
    comet_elements: list[CometElements],
    meta: BuildMeta,
) -> Path:
    """Write the full unified catalogue into a fresh ``reference.sqlite`` at ``out_path``."""
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
            "INSERT INTO objects (id, kind, name, designation) VALUES (?,?,?,?)",
            [(o.id, o.kind, o.name, o.designation) for o in objects],
        )
        con.executemany(
            "INSERT INTO fixed_object (object_id, ra_deg, dec_deg, apparent_mag, "
            "object_type, size_arcmin, constellation, messier, ngc_ic) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            [
                (
                    f.object_id, f.ra_deg, f.dec_deg, f.apparent_mag, f.object_type,
                    f.size_arcmin, f.constellation, f.messier, f.ngc_ic,
                )
                for f in fixed
            ],
        )
        con.executemany(
            "INSERT INTO ephemeris (object_id, sample_utc, ra_deg, dec_deg, "
            "earth_dist_au, sun_dist_au, apparent_mag, illumination, constellation) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            [
                (
                    r.object_id, r.sample_utc, r.ra_deg, r.dec_deg, r.earth_dist_au,
                    r.sun_dist_au, r.apparent_mag, r.illumination, r.constellation,
                )
                for r in ephem
            ],
        )
        con.executemany(
            "INSERT INTO comet_elements (object_id, epoch_jd, perihelion_q_au, "
            "eccentricity, inclination_deg, arg_perihelion_deg, node_deg, mag_h, mag_k) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            [
                (
                    c.object_id, c.epoch_jd, c.perihelion_q_au, c.eccentricity,
                    c.inclination_deg, c.arg_perihelion_deg, c.node_deg, c.mag_h, c.mag_k,
                )
                for c in comet_elements
            ],
        )
        con.commit()
    finally:
        con.close()
    return out_path
