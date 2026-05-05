"""Typed CRUD on the ``mount_limits`` table."""

from __future__ import annotations

from datetime import UTC, datetime

import aiosqlite

from astro_brain.models.calibration import AltLimits


async def get_alt_limits(db: aiosqlite.Connection) -> AltLimits | None:
    """Return the stored altitude limits, or ``None`` if never set."""
    cursor = await db.execute(
        "SELECT min_deg, max_deg FROM mount_limits WHERE axis = 'alt'"
    )
    row = await cursor.fetchone()
    await cursor.close()

    if row is None:
        return None

    min_deg, max_deg = row
    return AltLimits(min_deg=min_deg, max_deg=max_deg)


async def set_alt_limits(db: aiosqlite.Connection, limits: AltLimits) -> None:
    """Insert or replace the altitude limits row."""
    set_at = datetime.now(UTC).isoformat()

    await db.execute(
        "INSERT INTO mount_limits (axis, min_deg, max_deg, set_at) "
        "VALUES ('alt', ?, ?, ?) "
        "ON CONFLICT(axis) DO UPDATE SET "
        "min_deg = excluded.min_deg, "
        "max_deg = excluded.max_deg, "
        "set_at = excluded.set_at",
        (limits.min_deg, limits.max_deg, set_at),
    )
    await db.commit()
