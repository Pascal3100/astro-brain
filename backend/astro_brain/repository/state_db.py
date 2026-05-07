"""aiosqlite connection helpers and migration runner."""

from __future__ import annotations

import importlib
import os
import pkgutil
import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path

import aiosqlite

DB_FILENAME = "state.db"
STATE_DIR_ENV = "ASTRO_BRAIN_STATE_DIR"
STATE_DIR_DEFAULT = "/var/lib/astro-brain"

_MIGRATION_RE = re.compile(r"^_(\d+)_")


def db_path() -> Path:
    """Return the on-disk path to the state DB, ensuring the parent dir exists."""
    state_dir = Path(os.environ.get(STATE_DIR_ENV, STATE_DIR_DEFAULT))
    state_dir.mkdir(parents=True, exist_ok=True)
    return state_dir / DB_FILENAME


@asynccontextmanager
async def get_db(path: Path | None = None) -> AsyncIterator[aiosqlite.Connection]:
    """Open an aiosqlite connection to ``path`` (or :func:`db_path`)."""
    target = path if path is not None else db_path()
    conn = await aiosqlite.connect(target)
    try:
        yield conn
    finally:
        await conn.close()


async def _current_version(db: aiosqlite.Connection) -> int:
    cursor = await db.execute("SELECT MAX(version) FROM schema_version")
    row = await cursor.fetchone()
    await cursor.close()
    if row is None or row[0] is None:
        return 0
    return int(row[0])


def _discover_migrations() -> list[tuple[int, object]]:
    """Return ``(version, module)`` pairs sorted by lexical module name.

    L'ordre lexical des noms de module détermine l'ordre d'exécution :
    pad les numéros sur 3 chiffres (``_001_init``, ``_002_calibration``…)
    pour que l'ordre lexical = l'ordre numérique au-delà de 10 migrations.
    """
    from astro_brain.repository import migrations as migrations_pkg

    found: list[tuple[str, int, object]] = []
    for info in pkgutil.iter_modules(migrations_pkg.__path__):
        if _MIGRATION_RE.match(info.name) is None:
            continue
        module = importlib.import_module(f"{migrations_pkg.__name__}.{info.name}")
        found.append((info.name, int(module.VERSION), module))

    found.sort(key=lambda item: item[0])
    return [(version, module) for _, version, module in found]


async def run_migrations(db: aiosqlite.Connection) -> int:
    """Apply pending migrations in lexical order. Return the latest version."""
    await db.execute(
        "CREATE TABLE IF NOT EXISTS schema_version ("
        "version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)"
    )
    await db.commit()

    current = await _current_version(db)
    latest = current

    for version, module in _discover_migrations():
        if version <= current:
            continue
        sql = module.SQL
        await db.executescript(sql)
        await db.execute(
            "INSERT OR IGNORE INTO schema_version (version, applied_at) VALUES (?, ?)",
            (version, datetime.now(UTC).isoformat()),
        )
        await db.commit()
        latest = version

    return latest
