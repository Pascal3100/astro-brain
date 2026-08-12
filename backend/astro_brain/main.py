"""CLI entry point.

Usable either as a module (``python -m astro_brain.main``) or via uvicorn
directly (``uvicorn astro_brain.main:app``). ``app`` is re-exported from
:mod:`astro_brain.app` for the latter.

Process-wide logging is configured *here*, at import time, because this
module is the only entry point every deployment goes through (the systemd
unit runs ``uvicorn astro_brain.main:app``). Uvicorn configures its own
loggers and leaves the root logger alone, so without this the root stays at
``WARNING`` and every ``logger.info`` in the package is silently dropped in
production — as it was until 2026-08-12. Overridable via
``ASTRO_BRAIN_LOG_LEVEL``; no timestamp in the format, journald stamps every
line already.
"""

from __future__ import annotations

import logging
import os

import uvicorn

from astro_brain.app import app

__all__ = ["app", "configure_logging", "run"]

LOG_LEVEL_ENV = "ASTRO_BRAIN_LOG_LEVEL"


def configure_logging() -> None:
    """Send package logs to stderr at ``ASTRO_BRAIN_LOG_LEVEL`` (default INFO)."""
    level = os.environ.get(LOG_LEVEL_ENV, "INFO").upper()
    logging.basicConfig(
        level=level, format="%(levelname)s: %(name)s: %(message)s"
    )
    # basicConfig is a no-op once the root logger has a handler, so set the
    # level explicitly: the requested verbosity must hold even if something
    # else configured logging first.
    logging.getLogger().setLevel(level)


configure_logging()


def run() -> None:
    """Launch the ASGI server using env-driven host/port settings."""
    host = os.environ.get("ASTRO_BRAIN_HOST", "0.0.0.0")
    port = int(os.environ.get("ASTRO_BRAIN_PORT", "8000"))
    uvicorn.run("astro_brain.main:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    run()
