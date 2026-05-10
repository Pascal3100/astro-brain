"""Tests du repo alignment_model (load/save + garde-fous Δt et ΔGPS)."""
from __future__ import annotations

from datetime import UTC, datetime

import pytest

from astro_brain.models.alignment import AlignmentModel, StarRecord
from astro_brain.repository import alignment_repo
from astro_brain.repository.state_db import get_db, run_migrations


def _sample_model(
    *, validated_at_utc: str, gps: tuple[float, float] | None
) -> AlignmentModel:
    rec = StarRecord(star_id="vega", sky_az=0, sky_alt=30, mount_az=0, mount_alt=30)
    return AlignmentModel(
        recorded_stars=[rec, rec, rec],
        svd_matrix=[[1, 0, 0], [0, 1, 0], [0, 0, 1]],
        rms_arcmin=4.2,
        residuals={"vega": 4.2},
        validated_at_utc=validated_at_utc,
        gps_lat=gps[0] if gps else None,
        gps_lon=gps[1] if gps else None,
        quality="good",
    )


async def test_save_then_load_roundtrip(tmp_path) -> None:
    async with get_db(tmp_path / "x.db") as db:
        await run_migrations(db)
        m = _sample_model(validated_at_utc="2026-05-09T22:00:00+00:00", gps=(48.0, 2.0))
        await alignment_repo.save(db, m)
        loaded = await alignment_repo.load(
            db,
            now_utc=datetime(2026, 5, 9, 22, 30, tzinfo=UTC),
            current_gps=(48.0, 2.0),
        )
    assert loaded is not None
    assert loaded.rms_arcmin == pytest.approx(4.2)


async def test_load_returns_none_if_too_old(tmp_path) -> None:
    async with get_db(tmp_path / "x.db") as db:
        await run_migrations(db)
        m = _sample_model(validated_at_utc="2026-05-09T22:00:00+00:00", gps=(48.0, 2.0))
        await alignment_repo.save(db, m)
        loaded = await alignment_repo.load(
            db,
            now_utc=datetime(2026, 5, 10, 11, 0, tzinfo=UTC),  # 13h plus tard
            current_gps=(48.0, 2.0),
        )
    assert loaded is None


async def test_load_returns_none_if_gps_moved(tmp_path) -> None:
    async with get_db(tmp_path / "x.db") as db:
        await run_migrations(db)
        m = _sample_model(validated_at_utc="2026-05-09T22:00:00+00:00", gps=(48.0, 2.0))
        await alignment_repo.save(db, m)
        loaded = await alignment_repo.load(
            db,
            now_utc=datetime(2026, 5, 9, 22, 30, tzinfo=UTC),
            current_gps=(48.0, 2.001),  # ~111m plus loin
        )
    assert loaded is None


async def test_load_no_gps_in_stored_returns_none(tmp_path) -> None:
    async with get_db(tmp_path / "x.db") as db:
        await run_migrations(db)
        m = _sample_model(validated_at_utc="2026-05-09T22:00:00+00:00", gps=None)
        await alignment_repo.save(db, m)
        loaded = await alignment_repo.load(
            db,
            now_utc=datetime(2026, 5, 9, 22, 30, tzinfo=UTC),
            current_gps=(48.0, 2.0),
        )
    assert loaded is None


async def test_save_overwrites_previous(tmp_path) -> None:
    async with get_db(tmp_path / "x.db") as db:
        await run_migrations(db)
        m1 = _sample_model(validated_at_utc="2026-05-09T22:00:00+00:00", gps=(48.0, 2.0))
        m2 = _sample_model(validated_at_utc="2026-05-09T23:00:00+00:00", gps=(48.0, 2.0))
        await alignment_repo.save(db, m1)
        await alignment_repo.save(db, m2)
        cursor = await db.execute("SELECT COUNT(*) FROM alignment_model")
        row = await cursor.fetchone()
        await cursor.close()
    assert row[0] == 1
