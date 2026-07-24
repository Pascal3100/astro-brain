"""Astro-Brain reference data generator."""

from pathlib import Path

__version__ = "0.1.0"


def data_dir() -> Path:
    """Return the bundled data directory (kernel + fallback comet elements)."""
    return Path(__file__).resolve().parent.parent / "data"
