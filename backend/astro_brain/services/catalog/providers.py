"""Catalog providers — abstraction + sqlite-backed implementation."""
from __future__ import annotations

import json
from typing import Any, Protocol

import aiosqlite

from astro_brain.services.catalog.models import CatalogFilter, CatalogObject

_SELECT_COLUMNS = (
    "id, kind, name, designation, ra_deg, dec_deg, mag, "
    "constellation, object_type, angular_size_arcmin, extras_json"
)


def _row_to_object(row: tuple[Any, ...]) -> CatalogObject:
    (
        qid,
        kind,
        name,
        designation,
        ra_deg,
        dec_deg,
        mag,
        constellation,
        object_type,
        angular_size_arcmin,
        extras_json,
    ) = row
    extras: dict[str, Any] = {}
    if extras_json:
        extras = json.loads(extras_json)
    return CatalogObject(
        qualified_id=qid,
        kind=kind,
        name=name,
        designation=designation,
        ra_deg=ra_deg,
        dec_deg=dec_deg,
        mag=mag,
        constellation=constellation,
        object_type=object_type,
        angular_size_arcmin=angular_size_arcmin,
        extras=extras,
    )


class CatalogProvider(Protocol):
    """A source of CatalogObjects for one specific kind."""

    kind: str

    async def list_objects(self, filter: CatalogFilter) -> list[CatalogObject]:
        ...

    async def get_object(self, raw_id: str) -> CatalogObject | None:
        ...


class SqliteCatalogProvider:
    """Reads from `catalog_objects` rows whose `kind` matches `self.kind`."""

    def __init__(self, db: aiosqlite.Connection, *, kind: str) -> None:
        self._db = db
        self.kind = kind

    async def list_objects(self, filter: CatalogFilter) -> list[CatalogObject]:
        sql = f"SELECT {_SELECT_COLUMNS} FROM catalog_objects WHERE kind = ?"
        params: list[Any] = [self.kind]

        if filter.max_mag is not None:
            sql += " AND mag IS NOT NULL AND mag <= ?"
            params.append(filter.max_mag)

        if filter.search:
            like = f"%{filter.search}%"
            sql += " AND (name LIKE ? OR designation LIKE ?)"
            params.extend([like, like])

        sql += (
            " ORDER BY CASE WHEN mag IS NULL THEN 1 ELSE 0 END, mag, name"
            " LIMIT ? OFFSET ?"
        )
        params.extend([filter.limit, filter.offset])

        cursor = await self._db.execute(sql, tuple(params))
        rows = await cursor.fetchall()
        await cursor.close()
        return [_row_to_object(row) for row in rows]

    async def get_object(self, raw_id: str) -> CatalogObject | None:
        qid = f"{self.kind}:{raw_id}"
        cursor = await self._db.execute(
            f"SELECT {_SELECT_COLUMNS} FROM catalog_objects WHERE id = ?",
            (qid,),
        )
        row = await cursor.fetchone()
        await cursor.close()
        if row is None:
            return None
        return _row_to_object(row)
