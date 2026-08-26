"""Tests du router /align/* via FastAPI TestClient."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from astro_brain.bus import StateBus
from astro_brain.models.alignment import (
    AlignmentModel,
    AlignmentSession,
    Star,
    StarRecord,
)
from astro_brain.routes import alignment as alignment_routes
from astro_brain.routes.alignment import router
from astro_brain.services._ephemeris import Observer
from astro_brain.services.interfaces import (
    ConflictError,
    SensorUnavailableError,
)


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


def _client_with_service(
    service, position_provider=None
) -> tuple[TestClient, StateBus]:
    app = FastAPI()
    app.include_router(router)
    app.state.alignment = service
    bus = StateBus()
    app.state.bus = bus
    if position_provider is None:
        pp = MagicMock()
        pp.position = MagicMock(return_value=(43.6, 1.44))
    else:
        pp = position_provider
    app.state.position_provider = pp
    app.state.db = MagicMock()
    return TestClient(app), bus


def test_get_session_returns_null_when_idle() -> None:
    svc = MagicMock()
    svc.session = MagicMock(return_value=None)
    client, _ = _client_with_service(svc)
    r = client.get("/align/session")
    assert r.status_code == 200
    assert r.json() == {"session": None}


def test_post_start_returns_candidates() -> None:
    svc = MagicMock()
    svc.start = AsyncMock(return_value=_stub_session())
    svc.session = MagicMock(return_value=_stub_session())
    client, _ = _client_with_service(svc)
    r = client.post("/align/start")
    assert r.status_code == 200
    body = r.json()
    assert len(body["candidates"]) == 3
    assert body["current_idx"] == 0


def test_post_record_idx_mismatch_returns_409() -> None:
    svc = MagicMock()
    svc.record = AsyncMock(side_effect=ConflictError("idx mismatch"))
    client, _ = _client_with_service(svc)
    r = client.post("/align/record", json={"idx": 5})
    assert r.status_code == 409


def test_post_record_returns_503_when_mount_unreadable() -> None:
    """Encodeurs monture illisibles → 503, pas un 500 opaque (journal S51)."""
    svc = MagicMock()
    svc.record = AsyncMock(
        side_effect=SensorUnavailableError("encoder angles unavailable")
    )
    client, _ = _client_with_service(svc)
    r = client.post("/align/record", json={"idx": 0})
    assert r.status_code == 503
    assert "encoder" in r.json()["detail"]


def test_post_finalize_before_3_returns_409() -> None:
    svc = MagicMock()
    svc.finalize = AsyncMock(side_effect=ConflictError("need 3 stars"))
    client, _ = _client_with_service(svc)
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
    svc.session = MagicMock(return_value=None)
    client, _ = _client_with_service(svc)
    r = client.post("/align/finalize")
    assert r.status_code == 200
    assert r.json()["rms_arcmin"] == pytest.approx(4.2)


def test_post_swap_returns_session() -> None:
    svc = MagicMock()
    svc.swap = AsyncMock(return_value=_stub_session())
    svc.session = MagicMock(return_value=_stub_session())
    client, _ = _client_with_service(svc)
    star = {
        "id": "y",
        "name": "Y",
        "bayer": "-",
        "ra_deg": 50.0,
        "dec_deg": 20.0,
        "mag": 1.0,
    }
    r = client.post("/align/swap/2", json={"star": star})
    assert r.status_code == 200
    svc.swap.assert_awaited_once()
    args = svc.swap.await_args.args
    assert args[0] == 2
    assert args[1].id == "y"


def test_post_restart_star_returns_session() -> None:
    svc = MagicMock()
    svc.restart_star = AsyncMock(return_value=_stub_session())
    svc.session = MagicMock(return_value=_stub_session())
    client, _ = _client_with_service(svc)
    r = client.post("/align/restart_star", json={"idx": 1})
    assert r.status_code == 200
    svc.restart_star.assert_awaited_once_with(1)


def test_delete_session_returns_204() -> None:
    svc = MagicMock()
    svc.cancel = AsyncMock()
    svc.session = MagicMock(return_value=None)
    client, _ = _client_with_service(svc)
    r = client.delete("/align/session")
    assert r.status_code == 204
    svc.cancel.assert_awaited_once()


def test_post_start_publishes_active_subsystem_state() -> None:
    svc = MagicMock()
    svc.start = AsyncMock(return_value=_stub_session())
    svc.session = MagicMock(return_value=_stub_session())
    client, bus = _client_with_service(svc)
    r = client.post("/align/start")
    assert r.status_code == 200
    full = bus.get_full_state()
    align = full.subsystems["alignment"]
    assert align.state == "active"
    assert align.details["session_id"] == "s1"
    assert align.details["current_idx"] == 0
    assert align.details["recorded_count"] == 0
    assert align.details["candidate_ids"] == ["x0", "x1", "x2"]


def test_delete_session_publishes_idle_subsystem_state() -> None:
    svc = MagicMock()
    svc.cancel = AsyncMock()
    svc.session = MagicMock(return_value=None)
    client, bus = _client_with_service(svc)
    r = client.delete("/align/session")
    assert r.status_code == 204
    full = bus.get_full_state()
    assert full.subsystems["alignment"].state == "idle"


class _FakePositionProvider:
    """Fake position provider for tests.

    Starts with no position (simulates no GPS fix, no client location set).
    ``set_site`` stores the coordinates so that ``position`` returns them
    on the next call, and ``observer`` returns an ``Observer`` instance once
    a position is available.
    """

    def __init__(self) -> None:
        self._pos: tuple[float, float] | None = None

    def position(self) -> tuple[float, float] | None:
        return self._pos

    def set_site(self, lat: float, lon: float) -> None:
        self._pos = (lat, lon)

    def observer(self) -> Observer | None:
        if self._pos is None:
            return None
        return Observer(lat_deg=self._pos[0], lon_deg=self._pos[1])


def test_post_client_location_then_start_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """L'alias du wizard persiste le site puis débloque ``/align/start``.

    La persistance elle-même est couverte par ``test_site_routes`` sur une
    vraie base ; ici on ne veut que le contrat de la route, d'où le stub.
    """
    svc = MagicMock()
    svc.start = AsyncMock(return_value=_stub_session())
    svc.session = MagicMock(return_value=_stub_session())
    pp = _FakePositionProvider()
    saved: list[tuple[float, float]] = []

    async def _fake_set_site(_db, lat: float, lon: float):
        saved.append((lat, lon))
        return SimpleNamespace(lat=lat, lon=lon)

    monkeypatch.setattr(alignment_routes.site_repo, "set_site", _fake_set_site)

    client, _ = _client_with_service(svc, position_provider=pp)
    r = client.post("/align/location/client", json={"lat": 43.6, "lon": 1.44})
    assert r.status_code == 200
    assert saved == [(43.6, 1.44)]
    r2 = client.post("/align/start", json={})
    assert r2.status_code == 200


def test_start_without_position_returns_409() -> None:
    svc = MagicMock()
    svc.start = AsyncMock(return_value=_stub_session())
    svc.session = MagicMock(return_value=_stub_session())
    pp = _FakePositionProvider()  # ni fix GPS, ni site réglé
    client, _ = _client_with_service(svc, position_provider=pp)
    r = client.post("/align/start", json={})
    assert r.status_code == 409


# ---------------------------------------------------------------------------
# Fixtures for constellation / visible-stars routes
# ---------------------------------------------------------------------------


@pytest.fixture()
def client_located() -> TestClient:
    """TestClient with a located _FakePositionProvider (lat=43.6, lon=1.44)."""
    svc = MagicMock()
    svc.session = MagicMock(return_value=None)
    pp = _FakePositionProvider()
    pp.set_site(43.6, 1.44)
    client, _ = _client_with_service(svc, position_provider=pp)
    return client


# ---------------------------------------------------------------------------
# GET /align/constellation/{abbr}
# ---------------------------------------------------------------------------


def test_get_constellation_known_marks_target(
    client_located: TestClient,
) -> None:
    r = client_located.get(
        "/align/constellation/UMa",
        params={"target_ra": 165.932, "target_dec": 61.751},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["abbr"] == "UMa"
    assert body["name"] == "Grande Ourse"
    assert sum(1 for n in body["nodes"] if n["is_target"]) == 1
    assert body["oriented"] is True


def test_get_constellation_unknown_404(
    client_located: TestClient,
) -> None:
    r = client_located.get(
        "/align/constellation/ZZZ",
        params={"target_ra": 0.0, "target_dec": 0.0},
    )
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# GET /align/stars/visible
# ---------------------------------------------------------------------------


def test_get_visible_stars_grouped(client_located: TestClient) -> None:
    r = client_located.get("/align/stars/visible")
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body["constellations"], dict)
    for stars in body["constellations"].values():
        for s in stars:
            assert {"id", "name", "bayer", "ra_deg", "dec_deg", "mag", "az", "alt"} <= set(s)


def test_get_visible_stars_without_position_returns_409() -> None:
    svc = MagicMock()
    svc.session = MagicMock(return_value=None)
    pp = _FakePositionProvider()  # ni fix GPS, ni site réglé
    client, _ = _client_with_service(svc, position_provider=pp)
    r = client.get("/align/stars/visible")
    assert r.status_code == 409
