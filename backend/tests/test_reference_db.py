from __future__ import annotations

import sqlite3
from pathlib import Path

import aiosqlite
import pytest

from astro_brain.repository.reference_db import (
    SUPPORTED_SCHEMA_VERSION,
    ReferenceDb,
    local_sha256,
)


def _write_min_v2(path: Path, schema_version: int = 2) -> None:
    con = sqlite3.connect(path)
    con.executescript(
        "CREATE TABLE meta (schema_version INTEGER NOT NULL, generated_at TEXT,"
        " mpc_epoch TEXT, window_start TEXT NOT NULL, window_end TEXT NOT NULL,"
        " skyfield_kernel TEXT);"
    )
    con.execute(
        "INSERT INTO meta (schema_version, generated_at, window_start, window_end)"
        " VALUES (?, ?, ?, ?)",
        (schema_version, "2026-08-09T00:00:00Z", "2026-08-09", "2026-10-08"),
    )
    con.commit()
    con.close()


async def test_open_absent_file_is_not_ready(tmp_path: Path) -> None:
    ref = ReferenceDb(tmp_path / "reference.sqlite")
    await ref.open()
    assert ref.ready is False
    assert ref.current() is None


async def test_open_v2_is_ready_and_reads_meta(tmp_path: Path) -> None:
    p = tmp_path / "reference.sqlite"
    _write_min_v2(p, schema_version=2)
    ref = ReferenceDb(p)
    await ref.open()
    assert ref.ready is True
    meta = await ref.meta()
    assert meta is not None
    assert meta.schema_version == SUPPORTED_SCHEMA_VERSION
    assert meta.window_end == "2026-10-08"
    await ref.close()


async def test_open_future_schema_is_rejected(tmp_path: Path) -> None:
    p = tmp_path / "reference.sqlite"
    _write_min_v2(p, schema_version=3)
    ref = ReferenceDb(p)
    await ref.open()
    assert ref.ready is False


def test_local_sha256_absent_is_none(tmp_path: Path) -> None:
    assert local_sha256(tmp_path / "nope.sqlite") is None


async def test_open_failure_after_ready_resets_ready_to_false(tmp_path: Path) -> None:
    p = tmp_path / "reference.sqlite"
    _write_min_v2(p, schema_version=2)
    ref = ReferenceDb(p)
    await ref.open()
    assert ref.ready is True

    async def _boom() -> aiosqlite.Connection | None:
        raise RuntimeError("boom")

    ref._open_supported = _boom  # type: ignore[method-assign]

    with pytest.raises(RuntimeError):
        await ref.open()

    assert ref.ready is False
    assert ref.current() is None
