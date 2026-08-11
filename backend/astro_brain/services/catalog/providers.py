"""Catalog providers — reference.sqlite-backed implementations (fixed/ephemeris)."""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any

import aiosqlite

from astro_brain.repository.reference_db import ReferenceDb
from astro_brain.services.catalog.interpolation import interpolate_radec, parse_utc
from astro_brain.services.catalog.models import CatalogObject

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
