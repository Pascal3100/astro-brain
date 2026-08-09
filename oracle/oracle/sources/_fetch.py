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


def fetch_with_fallback(
    dest: Path,
    url: str,
    fallback_name: str,
    *,
    opener: Callable[[str], object] = urllib.request.urlopen,
) -> Path:
    """Fetch ``url`` to ``dest``; on failure copy the bundled ``fallback_name``."""
    try:
        with opener(url) as response:  # type: ignore[attr-defined]
            body = response.read()
        if not body:
            raise OSError("empty response body")
        dest.write_bytes(body)
    except Exception as exc:
        logger.warning(
            "%s fetch failed, using bundled fallback %s: %s", url, fallback_name, exc
        )
        shutil.copyfile(oracle.data_dir() / fallback_name, dest)
    return dest
