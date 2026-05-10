"""Tests du router /align/* via FastAPI TestClient."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from astro_brain import deps
from astro_brain.models.alignment import (
    AlignmentModel,
    AlignmentSession,
    Star,
    StarRecord,
)
from astro_brain.routes.alignment import router
from astro_brain.services.interfaces import ConflictError


def _stub_session() -> AlignmentSession:
    return AlignmentSession(
        session_id="s1",
        candidates=[
            Star(id=f"x{i}", name=f"X{i}", bayer="-", ra_deg=i * 100, dec_deg=10, mag=1)
            for i in range(3)
        ],
        recorded_stars=[],
        current_idx=0,
    )


def _client_with_service(service) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.state.alignment = service
    return TestClient(app)


def test_get_session_returns_null_when_idle() -> None:
    svc = MagicMock()
    svc.session = MagicMock(return_value=None)
    client = _client_with_service(svc)
    r = client.get("/align/session")
    assert r.status_code == 200
    assert r.json() == {"session": None}


def test_post_start_returns_candidates() -> None:
    svc = MagicMock()
    svc.start = AsyncMock(return_value=_stub_session())
    client = _client_with_service(svc)
    r = client.post("/align/start")
    assert r.status_code == 200
    body = r.json()
    assert len(body["candidates"]) == 3
    assert body["current_idx"] == 0


def test_post_record_idx_mismatch_returns_409() -> None:
    svc = MagicMock()
    svc.record = AsyncMock(side_effect=ConflictError("idx mismatch"))
    client = _client_with_service(svc)
    r = client.post("/align/record", json={"idx": 5})
    assert r.status_code == 409


def test_post_finalize_before_3_returns_409() -> None:
    svc = MagicMock()
    svc.finalize = AsyncMock(side_effect=ConflictError("need 3 stars"))
    client = _client_with_service(svc)
    r = client.post("/align/finalize")
    assert r.status_code == 409


def test_post_finalize_returns_model() -> None:
    rec = StarRecord(star_id="a", sky_az=0, sky_alt=0, mount_az=0, mount_alt=0)
    model = AlignmentModel(
        recorded_stars=[rec, rec, rec],
        svd_matrix=[[1, 0, 0], [0, 1, 0], [0, 0, 1]],
        rms_arcmin=4.2,
        residuals={"a": 4.2},
        validated_at_utc="2026-05-09T22:00:00+00:00",
        gps_lat=48.0,
        gps_lon=2.0,
        quality="good",
    )
    svc = MagicMock()
    svc.finalize = AsyncMock(return_value=model)
    client = _client_with_service(svc)
    r = client.post("/align/finalize")
    assert r.status_code == 200
    assert r.json()["rms_arcmin"] == pytest.approx(4.2)


def test_delete_session_returns_204() -> None:
    svc = MagicMock()
    svc.cancel = AsyncMock()
    client = _client_with_service(svc)
    r = client.delete("/align/session")
    assert r.status_code == 204
    svc.cancel.assert_awaited_once()
