"""Catalog providers — abstraction + sqlite-backed implementation."""
from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any, Protocol

import aiosqlite

from astro_brain.repository.reference_db import ReferenceDb
from astro_brain.services.catalog.interpolation import interpolate_radec, parse_utc
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


class EphemerisProvider:
    """Objets éphémères (comet/planet/moon/sun), RA/Dec interpolé à `now`."""

    KINDS = ("comet", "planet", "moon", "sun")

    def __init__(
        self, reference: ReferenceDb, *, now_utc: Callable[[], datetime]
    ) -> None:
        """Store the `ReferenceDb` handle and the injected "now" clock."""
        self._reference = reference
        self._now_utc = now_utc

    def _kinds_clause(self, filter: CatalogFilter) -> tuple[str, list[Any]]:
        """Return a `(sql_fragment, params)` pair restricting `o.kind`."""
        if filter.kind in self.KINDS:
            return "o.kind = ?", [filter.kind]
        placeholders = ", ".join("?" for _ in self.KINDS)
        return f"o.kind IN ({placeholders})", list(self.KINDS)

    async def _rows_for(
        self, conn: aiosqlite.Connection, where: str, params: list[Any]
    ) -> dict[str, list[tuple[Any, ...]]]:
        """Fetch ephemeris rows matching `where`, grouped by `object_id`."""
        cursor = await conn.execute(
            "SELECT e.object_id, o.kind, o.name, o.designation, e.sample_utc,"
            " e.ra_deg, e.dec_deg, e.apparent_mag, e.illumination,"
            " e.constellation FROM ephemeris e JOIN objects o"
            f" ON o.id = e.object_id WHERE {where} ORDER BY e.object_id,"
            " e.sample_utc",
            tuple(params),
        )
        rows = await cursor.fetchall()
        await cursor.close()
        grouped: dict[str, list[tuple[Any, ...]]] = {}
        for r in rows:
            grouped.setdefault(r[0], []).append(r)
        return grouped

    def _build(
        self, samples: list[tuple[Any, ...]], now: datetime
    ) -> CatalogObject | None:
        """Build a `CatalogObject` interpolated at `now` from `samples`."""
        if not samples:
            return None
        parsed = [(parse_utc(s[4]), s) for s in samples]
        before = [p for p in parsed if p[0] <= now]
        after = [p for p in parsed if p[0] >= now]
        stale = not (before and after)
        if not stale:
            b, a = before[-1], after[0]
            ra, dec = interpolate_radec(
                (b[0], b[1][5], b[1][6]), (a[0], a[1][5], a[1][6]), now
            )
            src = b[1]
        else:
            # échantillon-frontière le plus proche de `now`
            src = min(parsed, key=lambda p: abs((p[0] - now).total_seconds()))[1]
            ra, dec = src[5], src[6]
        return CatalogObject(
            qualified_id=src[0],
            kind=src[1],
            name=src[2] if src[2] is not None else (src[3] or src[0]),
            designation=src[3],
            ra_deg=ra,
            dec_deg=dec,
            mag=src[7],
            illumination=src[8],
            constellation=src[9],
            ephemeris_stale=stale,
        )

    async def list_objects(self, filter: CatalogFilter) -> list[CatalogObject]:
        """Return interpolated ephemeris objects matching `filter`.

        Only objects with a sample before *and* after `now` (within the
        query window) are returned; out-of-window objects are omitted.
        """
        conn = self._reference.current()
        if conn is None:
            return []
        now = self._now_utc()
        clause, params = self._kinds_clause(filter)
        lo = (now - timedelta(days=1, hours=12)).isoformat()
        hi = (now + timedelta(days=1, hours=12)).isoformat()
        where = f"{clause} AND e.sample_utc BETWEEN ? AND ?"
        grouped = await self._rows_for(conn, where, params + [lo, hi])
        objs: list[CatalogObject] = []
        for samples in grouped.values():
            obj = self._build(samples, now)
            if obj is None or obj.ephemeris_stale:
                continue  # list n'affiche que du plaçable
            if filter.max_mag is not None and (
                obj.mag is None or obj.mag > filter.max_mag
            ):
                continue
            if filter.search:
                needle = filter.search.lower()
                hay = f"{obj.name} {obj.designation or ''}".lower()
                if needle not in hay:
                    continue
            objs.append(obj)
        objs.sort(key=lambda o: (o.mag if o.mag is not None else float("inf"),
                                 o.name))
        return objs[filter.offset : filter.offset + filter.limit]

    async def get_object(self, obj_id: str) -> CatalogObject | None:
        """Return the ephemeris object `obj_id`, interpolated or stale.

        `None` if the id has no ephemeris sample at all; otherwise
        interpolated (`ephemeris_stale=False`) when `now` falls within its
        samples, or the nearest boundary sample with `ephemeris_stale=True`
        when `now` is outside the sampled window.
        """
        conn = self._reference.current()
        if conn is None:
            return None
        now = self._now_utc()
        grouped = await self._rows_for(conn, "e.object_id = ?", [obj_id])
        samples = grouped.get(obj_id)
        if not samples:
            return None
        return self._build(samples, now)
