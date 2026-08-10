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
        """Open a RO connection to `self._path` if present and schema-supported."""
        if not self._path.exists():
            return None
        uri = f"file:{self._path}?mode=ro&immutable=1"
        conn = await aiosqlite.connect(uri, uri=True)
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

        `self._conn` is reset to `None` before attempting to open the new
        connection, so that an unexpected exception from `_open_supported`
        (bad path, permission error, TOCTOU race where the file disappears
        between `exists()` and `connect()`) never leaves `ready` reporting
        `True` while `current()` would return a closed connection.
        """
        async with self._lock:
            if self._conn is not None:
                await self._conn.close()
            self._conn = None
            self._conn = await self._open_supported()

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
        """Close the current connection, if any, under the instance lock."""
        async with self._lock:
            if self._conn is not None:
                await self._conn.close()
                self._conn = None
