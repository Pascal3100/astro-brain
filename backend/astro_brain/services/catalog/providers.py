"""Catalog providers — abstraction + sqlite-backed implementation."""
from __future__ import annotations

import json
from typing import Any, Protocol

import aiosqlite

from astro_brain.repository.reference_db import ReferenceDb
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


_FIXED_COLUMNS = (
    "o.id, o.kind, o.name, o.designation, f.ra_deg, f.dec_deg, f.apparent_mag,"
    " f.object_type, f.size_arcmin, f.constellation, f.messier, f.ngc_ic"
)


def _fixed_row_to_object(row: tuple[Any, ...]) -> CatalogObject:
    (oid, kind, name, designation, ra, dec, mag, otype, size, const, messier,
     ngc_ic) = row
    return CatalogObject(
        qualified_id=oid,
        kind=kind,
        name=name if name is not None else (designation or oid),
        designation=designation,
        ra_deg=ra,
        dec_deg=dec,
        mag=mag,
        constellation=const,
        object_type=otype,
        angular_size_arcmin=size,
        messier=messier,
        ngc_ic=ngc_ic,
    )


class FixedObjectProvider:
    """Objets fixes (dso, star) lus dans `fixed_object` de reference.sqlite."""

    KINDS = ("dso", "star")

    def __init__(self, reference: ReferenceDb) -> None:
        """Store the `ReferenceDb` handle to query against."""
        self._reference = reference

    async def list_objects(self, filter: CatalogFilter) -> list[CatalogObject]:
        """Return fixed objects (dso/star) matching `filter`."""
        conn = self._reference.current()
        if conn is None:
            return []
        sql = f"SELECT {_FIXED_COLUMNS} FROM fixed_object f" \
              " JOIN objects o ON o.id = f.object_id WHERE "
        params: list[Any] = []
        if filter.kind in self.KINDS:
            sql += "o.kind = ?"
            params.append(filter.kind)
        else:
            sql += "o.kind IN ('dso', 'star')"
        if filter.max_mag is not None:
            sql += " AND f.apparent_mag IS NOT NULL AND f.apparent_mag <= ?"
            params.append(filter.max_mag)
        if filter.messier_only:
            sql += " AND f.messier IS NOT NULL"
        if filter.search:
            like = f"%{filter.search}%"
            sql += (" AND (o.name LIKE ? OR o.designation LIKE ?"
                    " OR f.messier LIKE ? OR f.ngc_ic LIKE ?)")
            params.extend([like, like, like, like])
        sql += (" ORDER BY CASE WHEN f.apparent_mag IS NULL THEN 1 ELSE 0 END,"
                " f.apparent_mag, o.name LIMIT ? OFFSET ?")
        params.extend([filter.limit, filter.offset])
        cursor = await conn.execute(sql, tuple(params))
        rows = await cursor.fetchall()
        await cursor.close()
        return [_fixed_row_to_object(r) for r in rows]

    async def get_object(self, obj_id: str) -> CatalogObject | None:
        """Return the fixed object with id `obj_id`, or `None` if absent."""
        conn = self._reference.current()
        if conn is None:
            return None
        cursor = await conn.execute(
            f"SELECT {_FIXED_COLUMNS} FROM fixed_object f"
            " JOIN objects o ON o.id = f.object_id WHERE f.object_id = ?",
            (obj_id,),
        )
        row = await cursor.fetchone()
        await cursor.close()
        return _fixed_row_to_object(row) if row is not None else None
