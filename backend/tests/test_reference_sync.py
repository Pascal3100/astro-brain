# backend/tests/test_reference_sync.py
from __future__ import annotations

import hashlib
import logging
import sqlite3
from pathlib import Path

import httpx

from astro_brain.app import _boot_reference_sync
from astro_brain.repository.reference_db import ReferenceDb, local_sha256
from astro_brain.services.reference.sync import ReferenceSync
from tests.reference_fixtures import build_reference_v2


def _sqlite_bytes(tmp_path: Path) -> bytes:
    p = tmp_path / "src.sqlite"
    build_reference_v2(p)
    return p.read_bytes()


def _client_factory(manifest: dict, sqlite: bytes):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("manifest.json"):
            return httpx.Response(200, json=manifest)
        return httpx.Response(200, content=sqlite)

    return lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_updated_downloads_and_swaps(tmp_path: Path) -> None:
    data = _sqlite_bytes(tmp_path)
    sha = hashlib.sha256(data).hexdigest()
    manifest = {"schema_version": 2, "generated_at": "x",
                "sqlite_url": "https://h/reference.sqlite", "sqlite_sha256": sha,
                "window_start": "2026-08-08", "window_end": "2026-10-07"}
    ref = ReferenceDb(tmp_path / "reference.sqlite")
    await ref.open()
    sync = ReferenceSync(reference=ref, manifest_url="https://h/manifest.json",
                         client_factory=_client_factory(manifest, data))
    result = await sync.sync()
    assert result.status == "updated"
    assert local_sha256(ref.path) == sha
    assert ref.ready is True
    await ref.close()


async def test_up_to_date_when_sha_matches(tmp_path: Path) -> None:
    data = _sqlite_bytes(tmp_path)
    sha = hashlib.sha256(data).hexdigest()
    p = tmp_path / "reference.sqlite"
    p.write_bytes(data)
    manifest = {"schema_version": 2, "generated_at": "x",
                "sqlite_url": "https://h/reference.sqlite", "sqlite_sha256": sha,
                "window_start": "2026-08-08", "window_end": "2026-10-07"}
    ref = ReferenceDb(p)
    await ref.open()
    sync = ReferenceSync(reference=ref, manifest_url="https://h/manifest.json",
                         client_factory=_client_factory(manifest, data))
    assert (await sync.sync()).status == "up_to_date"
    await ref.close()


async def test_offline_keeps_cache(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline", request=request)

    ref = ReferenceDb(tmp_path / "reference.sqlite")
    await ref.open()
    sync = ReferenceSync(
        reference=ref, manifest_url="https://h/manifest.json",
        client_factory=lambda: httpx.AsyncClient(
            transport=httpx.MockTransport(handler)),
    )
    assert (await sync.sync()).status == "offline"


async def test_rejects_future_schema(tmp_path: Path) -> None:
    data = _sqlite_bytes(tmp_path)
    manifest = {"schema_version": 3, "generated_at": "x",
                "sqlite_url": "https://h/reference.sqlite",
                "sqlite_sha256": hashlib.sha256(data).hexdigest(),
                "window_start": "x", "window_end": "y"}
    ref = ReferenceDb(tmp_path / "reference.sqlite")
    await ref.open()
    sync = ReferenceSync(reference=ref, manifest_url="https://h/manifest.json",
                         client_factory=_client_factory(manifest, data))
    result = await sync.sync()
    assert result.status == "rejected_schema"
    assert local_sha256(ref.path) is None  # rien n'a été écrit


async def test_rejects_downloaded_file_schema_mismatch(tmp_path: Path) -> None:
    # Le manifeste MENT : il annonce schema_version=2 avec le sha256 correct
    # d'un payload en réalité schema_version=3 (bascule le guard manifeste et
    # le hash check ; seul le guard sur le fichier téléchargé doit rejeter).
    p = tmp_path / "src.sqlite"
    build_reference_v2(p)
    con = sqlite3.connect(p)
    con.execute("UPDATE meta SET schema_version = 3")
    con.commit()
    con.close()
    data = p.read_bytes()
    sha = hashlib.sha256(data).hexdigest()
    manifest = {"schema_version": 2, "generated_at": "x",
                "sqlite_url": "https://h/reference.sqlite", "sqlite_sha256": sha,
                "window_start": "x", "window_end": "y"}
    ref = ReferenceDb(tmp_path / "reference.sqlite")
    await ref.open()
    sync = ReferenceSync(reference=ref, manifest_url="https://h/manifest.json",
                         client_factory=_client_factory(manifest, data))
    result = await sync.sync()
    assert result.status == "rejected_schema"
    assert local_sha256(ref.path) is None  # le mauvais fichier n'a pas remplacé le cache
    assert not ref.path.with_suffix(".sqlite.tmp").exists()  # tmp nettoyé


async def test_rejects_hash_mismatch(tmp_path: Path) -> None:
    data = _sqlite_bytes(tmp_path)
    manifest = {"schema_version": 2, "generated_at": "x",
                "sqlite_url": "https://h/reference.sqlite",
                "sqlite_sha256": "deadbeef", "window_start": "x",
                "window_end": "y"}
    ref = ReferenceDb(tmp_path / "reference.sqlite")
    await ref.open()
    sync = ReferenceSync(reference=ref, manifest_url="https://h/manifest.json",
                         client_factory=_client_factory(manifest, data))
    assert (await sync.sync()).status == "rejected_hash"
    assert local_sha256(ref.path) is None


async def test_updated_is_logged(tmp_path: Path, caplog) -> None:
    """Un succès doit parler : le boot-sync était totalement muet en prod."""
    data = _sqlite_bytes(tmp_path)
    manifest = {"schema_version": 2, "generated_at": "x",
                "sqlite_url": "https://h/reference.sqlite",
                "sqlite_sha256": hashlib.sha256(data).hexdigest(),
                "window_start": "x", "window_end": "y"}
    ref = ReferenceDb(tmp_path / "reference.sqlite")
    await ref.open()
    sync = ReferenceSync(reference=ref, manifest_url="https://h/manifest.json",
                         client_factory=_client_factory(manifest, data))
    with caplog.at_level(logging.INFO, logger="astro_brain.services.reference.sync"):
        assert (await sync.sync()).status == "updated"
    assert any("mis à jour" in r.getMessage() for r in caplog.records)


class _ExplodingSync:
    """Stand-in whose `sync()` raises what `ReferenceSync` never expects."""

    async def sync(self) -> None:
        raise OSError("No space left on device")


async def test_boot_sync_logs_unexpected_failure_instead_of_dying(caplog) -> None:
    """An unexpected error must reach journald, not vanish as a lost task.

    `asyncio.create_task(sync())` used to be fired bare: anything outside the
    handled (HTTPError, KeyError, ValueError) set died as a never-retrieved
    task exception.
    """
    with caplog.at_level(logging.ERROR, logger="astro_brain.app"):
        await _boot_reference_sync(_ExplodingSync())  # type: ignore[arg-type]

    errors = [r for r in caplog.records if r.levelno >= logging.ERROR]
    assert len(errors) == 1
    assert "No space left on device" in caplog.text
