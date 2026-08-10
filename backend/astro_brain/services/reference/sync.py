"""Sync de `reference.sqlite` : fetch conditionnel (sha256), verify, swap atomique.

Online-first, non bloquant : toute erreur réseau garde le cache courant. Le
téléchargement du fichier sqlite est bufferisé en mémoire (pas de streaming)
puis écrit dans un fichier temporaire avant le swap atomique.
"""
from __future__ import annotations

import hashlib
import logging
import os
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import httpx

from astro_brain.repository.reference_db import (
    SUPPORTED_SCHEMA_VERSION,
    ReferenceDb,
    local_sha256,
)

logger = logging.getLogger(__name__)

_Status = Literal["updated", "up_to_date", "offline", "rejected_schema",
                  "rejected_hash"]


@dataclass(frozen=True)
class SyncResult:
    """Outcome of a single `ReferenceSync.sync()` call."""

    status: _Status
    schema_version: int | None = None


def _default_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=60.0, follow_redirects=True)


class ReferenceSync:
    """Fetch, verify and atomically swap `reference.sqlite` from the manifest."""

    def __init__(
        self,
        *,
        reference: ReferenceDb,
        manifest_url: str,
        client_factory: Callable[[], httpx.AsyncClient] | None = None,
    ) -> None:
        """Bind the sync to `reference` and the manifest/client to fetch from."""
        self._reference = reference
        self._manifest_url = manifest_url
        self._client_factory = client_factory or _default_client

    def _temp_schema_version(self, path: Path) -> int | None:
        """Return the `schema_version` found in the downloaded file at `path`."""
        con = sqlite3.connect(path)
        try:
            cur = con.execute("SELECT schema_version FROM meta LIMIT 1")
            row = cur.fetchone()
        except sqlite3.DatabaseError:
            return None
        finally:
            con.close()
        return int(row[0]) if row is not None else None

    async def sync(self) -> SyncResult:
        """Run one sync cycle: manifest fetch, conditional download, atomic swap.

        Any network/parsing error keeps the current cache (`"offline"`). A
        manifest or downloaded-file schema above `SUPPORTED_SCHEMA_VERSION`,
        or a sha256 mismatch, is rejected without touching the cache.
        """
        try:
            async with self._client_factory() as client:
                resp = await client.get(self._manifest_url)
                resp.raise_for_status()
                manifest = resp.json()
                sv = int(manifest["schema_version"])
                if sv > SUPPORTED_SCHEMA_VERSION:
                    logger.warning("reference: schema_version %s > %s, gardé cache",
                                   sv, SUPPORTED_SCHEMA_VERSION)
                    return SyncResult("rejected_schema", sv)
                sha = manifest["sqlite_sha256"]
                if local_sha256(self._reference.path) == sha:
                    return SyncResult("up_to_date", sv)
                dl = await client.get(manifest["sqlite_url"])
                dl.raise_for_status()
                data = dl.content
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            logger.warning("reference: sync offline/invalide (%s)", exc)
            return SyncResult("offline")

        if hashlib.sha256(data).hexdigest() != sha:
            logger.warning("reference: sha256 mismatch, rejet")
            return SyncResult("rejected_hash")

        tmp = self._reference.path.with_suffix(".sqlite.tmp")
        tmp.write_bytes(data)
        tmp_sv = self._temp_schema_version(tmp)
        if tmp_sv is None or tmp_sv > SUPPORTED_SCHEMA_VERSION:
            tmp.unlink(missing_ok=True)
            return SyncResult("rejected_schema", tmp_sv)
        os.replace(tmp, self._reference.path)
        await self._reference.reopen()
        return SyncResult("updated", sv)
