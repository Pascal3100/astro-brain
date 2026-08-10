from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from astro_brain.repository.reference_db import ReferenceDb
from astro_brain.routes.reference import router
from astro_brain.services.reference.sync import ReferenceSync, SyncResult
from tests.reference_fixtures import build_reference_v2


class _FakeSync(ReferenceSync):
    def __init__(self) -> None:  # pas d'I/O
        pass

    async def sync(self) -> SyncResult:
        return SyncResult("up_to_date", 2)


def _client(ref: ReferenceDb) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.state.reference_db = ref
    app.state.reference_sync = _FakeSync()
    return TestClient(app)


async def test_status_ready(tmp_path: Path) -> None:
    p = tmp_path / "reference.sqlite"
    build_reference_v2(p)
    ref = ReferenceDb(p)
    await ref.open()
    r = _client(ref).get("/reference/status")
    assert r.status_code == 200
    body = r.json()
    assert body["ready"] is True
    assert body["schema_version"] == 2
    assert body["window_end"] == "2026-10-07"
    await ref.close()


async def test_status_not_ready(tmp_path: Path) -> None:
    ref = ReferenceDb(tmp_path / "absent.sqlite")
    await ref.open()
    r = _client(ref).get("/reference/status")
    assert r.json() == {"ready": False, "schema_version": None,
                        "generated_at": None, "window_start": None,
                        "window_end": None}


async def test_post_sync_returns_status(tmp_path: Path) -> None:
    ref = ReferenceDb(tmp_path / "absent.sqlite")
    await ref.open()
    r = _client(ref).post("/reference/sync")
    assert r.status_code == 200
    assert r.json() == {"status": "up_to_date", "schema_version": 2}
