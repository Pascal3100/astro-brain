"""Tests for catalog seed_runner.apply_seeds."""
from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from pathlib import Path

import aiosqlite
import pytest

from astro_brain.repository.state_db import run_migrations
from astro_brain.services.catalog.seed_runner import apply_seeds


@pytest.fixture
async def db() -> AsyncIterator[aiosqlite.Connection]:
    conn = await aiosqlite.connect(":memory:")
    try:
        await run_migrations(conn)
        yield conn
    finally:
        await conn.close()


def _write_seed(dir: Path, name: str, body: str) -> Path:
    path = dir / name
    path.write_text(body, encoding="utf-8")
    return path


async def _count(db: aiosqlite.Connection, kind: str) -> int:
    cursor = await db.execute(
        "SELECT COUNT(*) FROM catalog_objects WHERE kind = ?", (kind,)
    )
    row = await cursor.fetchone()
    await cursor.close()
    assert row is not None
    return int(row[0])


async def test_apply_seeds_loads_inserts(tmp_path: Path, db: aiosqlite.Connection) -> None:
    _write_seed(
        tmp_path,
        "seed_stars.sql",
        "INSERT OR REPLACE INTO catalog_objects "
        "(id, kind, name, ra_deg, dec_deg, mag) "
        "VALUES ('star:sirius', 'star', 'Sirius', 101.287, -16.716, -1.46);\n",
    )

    await apply_seeds(db, tmp_path)

    assert await _count(db, "star") == 1


async def test_apply_seeds_idempotent_via_insert_or_replace(
    tmp_path: Path, db: aiosqlite.Connection
) -> None:
    _write_seed(
        tmp_path,
        "seed_stars.sql",
        "INSERT OR REPLACE INTO catalog_objects "
        "(id, kind, name, ra_deg, dec_deg, mag) "
        "VALUES ('star:sirius', 'star', 'Sirius', 101.287, -16.716, -1.46);\n",
    )

    await apply_seeds(db, tmp_path)
    await apply_seeds(db, tmp_path)

    assert await _count(db, "star") == 1


async def test_apply_seeds_replaces_updated_row(
    tmp_path: Path, db: aiosqlite.Connection
) -> None:
    seed = tmp_path / "seed_stars.sql"
    seed.write_text(
        "INSERT OR REPLACE INTO catalog_objects "
        "(id, kind, name, ra_deg, dec_deg, mag) "
        "VALUES ('star:sirius', 'star', 'Sirius', 101.287, -16.716, -1.46);\n",
        encoding="utf-8",
    )
    await apply_seeds(db, tmp_path)

    seed.write_text(
        "INSERT OR REPLACE INTO catalog_objects "
        "(id, kind, name, ra_deg, dec_deg, mag) "
        "VALUES ('star:sirius', 'star', 'Sirius', 101.287, -16.716, -1.50);\n",
        encoding="utf-8",
    )
    await apply_seeds(db, tmp_path)

    cursor = await db.execute(
        "SELECT mag FROM catalog_objects WHERE id = 'star:sirius'"
    )
    row = await cursor.fetchone()
    await cursor.close()
    assert row is not None
    assert row[0] == pytest.approx(-1.50)


async def test_apply_seeds_missing_dir_is_noop(
    tmp_path: Path, db: aiosqlite.Connection
) -> None:
    missing = tmp_path / "does_not_exist"

    await apply_seeds(db, missing)

    assert await _count(db, "star") == 0


async def test_apply_seeds_no_matching_files_is_noop(
    tmp_path: Path, db: aiosqlite.Connection
) -> None:
    (tmp_path / "not_a_seed.txt").write_text("garbage", encoding="utf-8")

    await apply_seeds(db, tmp_path)

    assert await _count(db, "star") == 0


async def test_apply_seeds_logs_and_continues_on_broken_seed(
    tmp_path: Path,
    db: aiosqlite.Connection,
    caplog: pytest.LogCaptureFixture,
) -> None:
    _write_seed(tmp_path, "seed_a_broken.sql", "THIS IS NOT VALID SQL;\n")
    _write_seed(
        tmp_path,
        "seed_b_ok.sql",
        "INSERT OR REPLACE INTO catalog_objects "
        "(id, kind, name, ra_deg, dec_deg, mag) "
        "VALUES ('star:vega', 'star', 'Vega', 279.235, 38.784, 0.03);\n",
    )

    with caplog.at_level(logging.ERROR):
        await apply_seeds(db, tmp_path)

    assert any("seed_a_broken.sql" in rec.message for rec in caplog.records)
    assert await _count(db, "star") == 1


async def test_apply_seeds_processes_files_in_lexical_order(
    tmp_path: Path, db: aiosqlite.Connection
) -> None:
    _write_seed(
        tmp_path,
        "seed_b.sql",
        "INSERT OR REPLACE INTO catalog_objects "
        "(id, kind, name, ra_deg, dec_deg, mag) "
        "VALUES ('star:x', 'star', 'X', 0, 0, 1.0);\n",
    )
    _write_seed(
        tmp_path,
        "seed_a.sql",
        "INSERT OR REPLACE INTO catalog_objects "
        "(id, kind, name, ra_deg, dec_deg, mag) "
        "VALUES ('star:x', 'star', 'X', 0, 0, 9.99);\n",
    )

    await apply_seeds(db, tmp_path)

    cursor = await db.execute("SELECT mag FROM catalog_objects WHERE id = 'star:x'")
    row = await cursor.fetchone()
    await cursor.close()
    assert row is not None
    # seed_a runs first, seed_b last → final value from seed_b
    assert row[0] == pytest.approx(1.0)
