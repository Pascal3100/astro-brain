"""Connexion lecture seule à `reference.sqlite` (artefact SP1, jetable).

Fichier distinct de `state.db` : RO, remplacé en bloc par la sync. Le handle
courant est swappable sous verrou (une sync réouvre sans perturber les
requêtes en cours). Le backend refuse d'adopter un schema_version > 2.
"""
from __future__ import annotations

import asyncio
import hashlib
import os
from dataclasses import dataclass
from pathlib import Path

import aiosqlite

from astro_brain.repository.state_db import STATE_DIR_DEFAULT, STATE_DIR_ENV

REFERENCE_FILENAME = "reference.sqlite"
MANIFEST_URL_ENV = "ASTRO_BRAIN_REFERENCE_MANIFEST_URL"
DEFAULT_MANIFEST_URL = (
    "https://github.com/Pascal3100/astro-brain/releases/download/"
    "almanac-latest/manifest.json"
)
SUPPORTED_SCHEMA_VERSION = 2


def reference_path() -> Path:
    """Return the on-disk path to `reference.sqlite`, ensuring the parent dir exists."""
    state_dir = Path(os.environ.get(STATE_DIR_ENV, STATE_DIR_DEFAULT))
    state_dir.mkdir(parents=True, exist_ok=True)
    return state_dir / REFERENCE_FILENAME


def manifest_url() -> str:
    """Return the reference manifest URL from env, or the built-in default."""
    return os.environ.get(MANIFEST_URL_ENV, DEFAULT_MANIFEST_URL)


def local_sha256(path: Path) -> str | None:
    """Return the hex SHA-256 digest of `path`, or `None` if it does not exist."""
    if not path.exists():
        return None
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


@dataclass(frozen=True)
class ReferenceMeta:
    """Snapshot of the `meta` table of a `reference.sqlite` file."""

    schema_version: int
    generated_at: str
    window_start: str
    window_end: str


class ReferenceDb:
    """Swappable read-only handle to a `reference.sqlite` almanac file."""

    def __init__(self, path: Path) -> None:
        """Store the target `path`; no connection is opened until `open()`."""
        self._path = path
        self._conn: aiosqlite.Connection | None = None
        self._stale_conn: aiosqlite.Connection | None = None
        self._lock = asyncio.Lock()

    @property
    def path(self) -> Path:
        """Return the on-disk path this handle targets."""
        return self._path

    @property
    def ready(self) -> bool:
        """Return whether a supported connection is currently open."""
        return self._conn is not None

    def current(self) -> aiosqlite.Connection | None:
        """Return the current open connection, or `None` if not ready."""
        return self._conn

    async def _open_supported(self) -> aiosqlite.Connection | None:
        """Open a RO connection to `self._path` if present and schema-supported.

        Never raises: an absent, locked, or corrupt file (the file may even
        vanish between the exists() check and connect()) yields `None`, so
        `open()` degrades cleanly to `ready=False` instead of propagating.
        """
        if not self._path.exists():
            return None
        uri = f"file:{self._path}?mode=ro&immutable=1"
        try:
            conn = await aiosqlite.connect(uri, uri=True)
        except Exception:
            return None
        try:
            cursor = await conn.execute("SELECT schema_version FROM meta LIMIT 1")
            row = await cursor.fetchone()
            await cursor.close()
        except Exception:
            await conn.close()
            return None
        if row is None or int(row[0]) > SUPPORTED_SCHEMA_VERSION:
            await conn.close()
            return None
        return conn

    async def open(self) -> None:
        """Open (or replace) the current connection under the instance lock.

        The connection being replaced is NOT closed eagerly: an in-flight
        request may have read it via `current()` and still be awaiting a query
        on it. We swap `self._conn` to the freshly-opened handle and defer the
        old one's close by one cycle (`self._stale_conn`) — the handle retired
        at the *previous* `open()` is idle by now and is the one closed here.
        The handoff runs in a `finally` so the retired handle is never leaked
        even on an unexpected failure; `self._conn` is set to `None` before
        `_open_supported()` so `ready` never lies while `current()` is None.
        """
        async with self._lock:
            retired = self._conn
            self._conn = None
            try:
                self._conn = await self._open_supported()
            finally:
                stale, self._stale_conn = self._stale_conn, retired
                if stale is not None:
                    await stale.close()

    async def reopen(self) -> None:
        """Re-open the connection, e.g. after a sync replaced the file on disk."""
        await self.open()

    async def meta(self) -> ReferenceMeta | None:
        """Return the current file's `meta` row, or `None` if not ready."""
        conn = self._conn
        if conn is None:
            return None
        cursor = await conn.execute(
            "SELECT schema_version, generated_at, window_start, window_end"
            " FROM meta LIMIT 1"
        )
        row = await cursor.fetchone()
        await cursor.close()
        if row is None:
            return None
        return ReferenceMeta(
            schema_version=int(row[0]),
            generated_at=row[1],
            window_start=row[2],
            window_end=row[3],
        )

    async def close(self) -> None:
        """Close the current and any retired connection, under the instance lock."""
        async with self._lock:
            for conn in (self._conn, self._stale_conn):
                if conn is not None:
                    await conn.close()
            self._conn = None
            self._stale_conn = None
