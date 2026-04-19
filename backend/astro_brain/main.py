"""CLI entry point.

Usable either as a module (``python -m astro_brain.main``) or via uvicorn
directly (``uvicorn astro_brain.main:app``). ``app`` is re-exported from
:mod:`astro_brain.app` for the latter.
"""

from __future__ import annotations

import os

import uvicorn

from astro_brain.app import app

__all__ = ["app", "run"]


def run() -> None:
    """Launch the ASGI server using env-driven host/port settings."""
    host = os.environ.get("ASTRO_BRAIN_HOST", "0.0.0.0")
    port = int(os.environ.get("ASTRO_BRAIN_PORT", "8000"))
    uvicorn.run("astro_brain.main:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    run()
