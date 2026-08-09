import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from oracle.build_db import SCHEMA_VERSION, BuildMeta, build_reference_db
from oracle.records import CometElements, EphemRow, FixedRow, ObjectRow


def _meta() -> BuildMeta:
    now = datetime(2026, 8, 1, tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")
    return BuildMeta(
        schema_version=SCHEMA_VERSION,
        generated_at=now,
        mpc_epoch=None,
        window_start=now,
        window_end=now,
        skyfield_kernel="de421.bsp",
    )


def test_schema_version_is_2() -> None:
    assert SCHEMA_VERSION == 2


def test_unified_writer_populates_all_tables(tmp_path: Path) -> None:
    objects = [
        ObjectRow("NGC1976", "dso", "Orion Nebula", "NGC1976"),
        ObjectRow("star:HIP32349", "star", "Sirius", "HR 2491"),
        ObjectRow("planet:mars", "planet", "Mars", None),
        ObjectRow("moon", "moon", "Moon", None),
        ObjectRow("C/2023 A3", "comet", "Tsuchinshan-ATLAS", "C/2023 A3"),
    ]
    fixed = [
        FixedRow("NGC1976", 83.8, -5.4, 4.0, "nebula", 85.0, "Ori", "M42", "NGC1976"),
        FixedRow("star:HIP32349", 101.3, -16.7, -1.46, "star", None, "CMa", None, None),
    ]
    ephem = [
        EphemRow("planet:mars", "2026-08-01T00:00:00Z", 120.0, 20.0, 1.5, 1.6, -1.0, None, "Leo"),
        EphemRow("moon", "2026-08-01T00:00:00Z", 200.0, -10.0, 0.0026, 1.0, None, 0.42, "Vir"),
        EphemRow("C/2023 A3", "2026-08-01T00:00:00Z", 45.0, 15.0, 1.2, 0.9, 8.5, None, "Ari"),
    ]
    elements = [
        CometElements("C/2023 A3", 2460000.5, 0.39, 1.0001, 139.1, 308.5, 21.6, 5.0, 4.0),
    ]

    out = build_reference_db(tmp_path / "reference.sqlite", objects, fixed, ephem, elements, _meta())
    assert out.exists()

    con = sqlite3.connect(out)
    try:
        (version,) = con.execute("SELECT schema_version FROM meta").fetchone()
        assert version == 2
        assert con.execute("SELECT COUNT(*) FROM objects").fetchone()[0] == 5
        assert con.execute("SELECT COUNT(*) FROM fixed_object").fetchone()[0] == 2
        assert con.execute("SELECT COUNT(*) FROM ephemeris").fetchone()[0] == 3
        assert con.execute("SELECT COUNT(*) FROM comet_elements").fetchone()[0] == 1
        # FK integrity: every child row references an existing object
        for child, col in (("fixed_object", "object_id"), ("ephemeris", "object_id"), ("comet_elements", "object_id")):
            (orphans,) = con.execute(
                f"SELECT COUNT(*) FROM {child} c "
                f"LEFT JOIN objects o ON c.{col} = o.id WHERE o.id IS NULL"
            ).fetchone()
            assert orphans == 0, child
        # illumination present for the Moon, NULL for the comet
        (illum_moon,) = con.execute(
            "SELECT illumination FROM ephemeris WHERE object_id='moon'"
        ).fetchone()
        assert illum_moon == 0.42
        (illum_comet,) = con.execute(
            "SELECT illumination FROM ephemeris WHERE object_id='C/2023 A3'"
        ).fetchone()
        assert illum_comet is None
    finally:
        con.close()
