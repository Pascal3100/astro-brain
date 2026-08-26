"""Integration tests pour ``GET /site`` et ``PUT /site``.

Montés sur l'app complète (``build_app``) plutôt qu'un ``FastAPI()`` nu : le
``PUT`` touche à la fois la base et le provider de position en mémoire, et
c'est précisément ce couplage qu'on veut vérifier.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from astro_brain.app import build_app


@pytest.fixture
def client() -> Iterator[TestClient]:
    app = build_app(use_hardware=False, db_path_override=":memory:", sync_on_boot=False)
    with TestClient(app) as test_client:
        yield test_client


def test_get_site_returns_null_when_never_set(client: TestClient) -> None:
    """L'absence de site est un état nominal : 200 + ``null``, pas un 404."""
    response = client.get("/site")
    assert response.status_code == 200
    assert response.json() is None


def test_put_then_get_round_trip(client: TestClient) -> None:
    put = client.put("/site", json={"lat": 43.6, "lon": 1.44})
    assert put.status_code == 204

    body = client.get("/site").json()
    assert body["lat"] == 43.6
    assert body["lon"] == 1.44
    assert body["set_at"]


def test_put_rejects_out_of_range_latitude(client: TestClient) -> None:
    response = client.put("/site", json={"lat": 91.0, "lon": 1.44})
    assert response.status_code == 422
    assert client.get("/site").json() is None


def test_put_updates_the_in_memory_position_provider(client: TestClient) -> None:
    """Sans ça, ``/align/start`` resterait en 409 jusqu'au redémarrage.

    On observe ``site()`` et non ``position()`` : tant que le GPS existe, son
    fix garde la précédence dans la chaîne. Cette précédence disparaît avec le
    GPS (Task 3), et ``position()`` se réduira alors à ``site()``.
    """
    provider = client.app.state.position_provider
    assert provider.site() is None

    client.put("/site", json={"lat": 48.85, "lon": 2.35})
    assert provider.site() == (48.85, 2.35)


def test_site_survives_a_restart_of_the_app(tmp_path) -> None:
    """Le site est relu au boot et resemé dans le provider de position."""
    db_file = tmp_path / "state.db"

    app = build_app(use_hardware=False, db_path_override=db_file, sync_on_boot=False)
    with TestClient(app) as client:
        assert client.put("/site", json={"lat": 43.6, "lon": 1.44}).status_code == 204

    app2 = build_app(use_hardware=False, db_path_override=db_file, sync_on_boot=False)
    with TestClient(app2) as client2:
        assert client2.get("/site").json()["lat"] == 43.6
        assert client2.app.state.position_provider.site() == (43.6, 1.44)


def test_align_location_client_persists_the_site(client: TestClient) -> None:
    """L'alias historique du wizard écrit bien en base, plus seulement en RAM."""
    response = client.post("/align/location/client", json={"lat": 43.6, "lon": 1.44})
    assert response.status_code == 200

    assert client.get("/site").json()["lat"] == 43.6
