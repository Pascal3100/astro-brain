"""Apply `seed_*.sql` files from a data directory at boot, idempotently."""
from __future__ import annotations

import logging
from pathlib import Path

import aiosqlite

logger = logging.getLogger(__name__)


async def apply_seeds(db: aiosqlite.Connection, data_dir: Path) -> None:
    """Run every `seed_*.sql` under ``data_dir`` against ``db``.

    Idempotent par construction (les seeds utilisent `INSERT OR REPLACE`).
    Une seed cassée logge l'erreur et n'interrompt pas le boot — un Pi sans
    catalogue est dégradé mais reste manœuvrable.
    """
    if not data_dir.is_dir():
        return

    for sql_path in sorted(data_dir.glob("seed_*.sql")):
        sql = sql_path.read_text(encoding="utf-8")
        try:
            await db.executescript(sql)
            await db.commit()
        except Exception:
            logger.exception("catalog seed failed: %s", sql_path.name)
