"""Tests du AlignmentServiceImpl (start/record/swap/finalize/restart_star/cancel)."""
from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from astro_brain.models.alignment import Star
from astro_brain.services.alignment import AlignmentServiceImpl
from astro_brain.services.interfaces import ConflictError


def _stub_candidates() -> list[Star]:
    return [
        Star(id="a", name="A", bayer="α", ra_deg=0, dec_deg=10, mag=1.0),
        Star(id="b", name="B", bayer="β", ra_deg=120, dec_deg=20, mag=1.2),
        Star(id="c", name="C", bayer="γ", ra_deg=240, dec_deg=30, mag=1.4),
    ]


def _build_service(candidates: list[Star] | None = None) -> AlignmentServiceImpl:
    """Service avec mocks pour repo, mount, sensors et catalog."""
    selector = MagicMock(return_value=candidates or _stub_candidates())
    mount = MagicMock()
    mount.current_position = AsyncMock(return_value=(100.0, 50.0))
    mount.sync_radec = AsyncMock()
    sensors = MagicMock()
    sensors.gps_fix = MagicMock(return_value=(48.8, 2.3))
    sensors.sky_az_alt_for = MagicMock(side_effect=lambda s: (s.ra_deg % 360, s.dec_deg))
    repo_save = AsyncMock()
    return AlignmentServiceImpl(
        select_candidates=selector,
        mount=mount,
        sensors=sensors,
        repo_save=repo_save,
        db=MagicMock(),
        now_utc=lambda: datetime(2026, 5, 9, 22, 0, tzinfo=UTC),
    )


async def test_start_creates_session_with_3_candidates() -> None:
    svc = _build_service()
    sess = await svc.start()
    assert len(sess.candidates) == 3
    assert sess.current_idx == 0
    assert sess.recorded_count == 0


async def test_record_appends_then_increments_current_idx() -> None:
    svc = _build_service()
    await svc.start()
    sess = await svc.record(0)
    assert sess.recorded_count == 1
    assert sess.current_idx == 1


async def test_record_pushes_sync_to_native_alignment_model() -> None:
    """Each record must feed the INDI/Celestron native alignment model.

    Cf. ADR 2026-05-10 : `sync_radec(ra_deg, dec_deg)` à chaque record.
    """
    svc = _build_service()
    await svc.start()
    await svc.record(0)
    await svc.record(1)
    await svc.record(2)
    # 3 syncs poussés, dans l'ordre, avec les coords des candidates en degrés.
    actual = [call.args for call in svc._mount.sync_radec.await_args_list]
    assert actual == [(0.0, 10.0), (120.0, 20.0), (240.0, 30.0)]


async def test_record_skips_sync_when_idx_invalid() -> None:
    svc = _build_service()
    await svc.start()
    with pytest.raises(ConflictError):
        await svc.record(1)
    svc._mount.sync_radec.assert_not_awaited()


async def test_record_wrong_idx_raises_conflict() -> None:
    svc = _build_service()
    await svc.start()
    with pytest.raises(ConflictError):
        await svc.record(1)  # current_idx=0 → idx 1 invalide


async def test_swap_replaces_current_candidate() -> None:
    svc = _build_service()
    await svc.start()
    new_star = Star(id="z", name="Z", bayer="ζ", ra_deg=300, dec_deg=40, mag=1.0)
    sess = await svc.swap(0, new_star)
    assert sess.candidates[0].id == "z"


async def test_swap_after_record_raises_conflict() -> None:
    svc = _build_service()
    await svc.start()
    await svc.record(0)
    with pytest.raises(ConflictError):
        await svc.swap(0, Star(id="z", name="Z", bayer="ζ", ra_deg=300, dec_deg=40, mag=1.0))


async def test_finalize_before_3_records_raises_conflict() -> None:
    svc = _build_service()
    await svc.start()
    await svc.record(0)
    with pytest.raises(ConflictError):
        await svc.finalize()


async def test_finalize_persists_and_returns_model() -> None:
    svc = _build_service()
    await svc.start()
    await svc.record(0)
    await svc.record(1)
    await svc.record(2)
    model = await svc.finalize()
    assert model.rms_arcmin >= 0
    svc._repo_save.assert_awaited_once()


async def test_restart_star_truncates_recorded() -> None:
    svc = _build_service()
    await svc.start()
    await svc.record(0)
    await svc.record(1)
    await svc.record(2)
    sess = await svc.restart_star(1)
    assert sess.recorded_count == 1  # garde s0
    assert sess.current_idx == 1


async def test_cancel_clears_session_only() -> None:
    svc = _build_service()
    await svc.start()
    await svc.cancel()
    assert svc.session() is None
    svc._repo_save.assert_not_awaited()


async def test_record_raises_conflict_when_position_unavailable() -> None:
    """sky_az_alt_for returning None must raise ConflictError, not crash with TypeError."""
    svc = _build_service()
    await svc.start()
    # Simulate GPS drop / no observer position mid-session
    svc._sensors.sky_az_alt_for = MagicMock(return_value=None)
    with pytest.raises(ConflictError):
        await svc.record(0)


@pytest.mark.asyncio
async def test_is_aligned_lifecycle() -> None:
    """is_aligned: False at start, True after finalize, False after invalidate."""
    svc = _build_service()
    assert svc.is_aligned is False

    await svc.start()
    for i in range(3):
        await svc.record(i)

    await svc.finalize()
    assert svc.is_aligned is True

    svc.invalidate()
    assert svc.is_aligned is False
