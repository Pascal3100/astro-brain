"""Shared fetch-with-fallback helper for reference data sources.

A build must never fail because a source is unreachable: on any error (or an
empty response), the bundled snapshot named ``fallback_name`` under
``oracle.data_dir()`` is copied in place.
"""

import logging
import shutil
import urllib.request
from collections.abc import Callable
from pathlib import Path

import oracle

logger = logging.getLogger(__name__)


def with_fallback(
    dest: Path,
    fallback_name: str,
    produce: Callable[[], bytes],
) -> Path:
    """Write ``produce()``'s bytes to ``dest``; on any error copy the bundled fallback.

    ``produce`` performs the network work (one or more fetches, optional merge)
    and returns the bytes to write. Any exception it raises — or an empty
    result — triggers a byte-for-byte copy of ``oracle.data_dir() / fallback_name``.
    """
    try:
        body = produce()
        if not body:
            raise OSError("empty response body")
        dest.write_bytes(body)
    except Exception as exc:
        logger.warning(
            "fetch failed, using bundled fallback %s: %s", fallback_name, exc
        )
        shutil.copyfile(oracle.data_dir() / fallback_name, dest)
    return dest


def fetch_with_fallback(
    dest: Path,
    url: str,
    fallback_name: str,
    *,
    opener: Callable[[str], object] = urllib.request.urlopen,
) -> Path:
    """Fetch ``url`` to ``dest``; on failure copy the bundled ``fallback_name``."""

    def produce() -> bytes:
        with opener(url) as response:  # type: ignore[attr-defined]
            return response.read()

    return with_fallback(dest, fallback_name, produce)
