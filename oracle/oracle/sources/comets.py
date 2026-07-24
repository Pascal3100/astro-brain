"""Load comet orbital elements from an MPC CometEls.txt file."""

import logging
import shutil
import urllib.request
from collections.abc import Callable
from pathlib import Path

import pandas as pd
from skyfield.api import load
from skyfield.data import mpc

import oracle

logger = logging.getLogger(__name__)

COMET_ELS_URL = "https://www.minorplanetcenter.net/iau/MPCORB/CometEls.txt"


def _latest_orbit_per_comet(comets: pd.DataFrame) -> pd.DataFrame:
    """Keep one whole row per comet — the most recently referenced orbit.

    ``reference`` is a best-effort recency signal (MPC ships essentially one
    orbit per designation; duplicates are rare). We use ``drop_duplicates``
    rather than ``groupby().last()`` so the kept row is a single coherent
    orbit solution, never a per-column mix across epochs (``magnitude_g``/
    ``magnitude_k`` are often NaN and would otherwise be back-filled from an
    older row).
    """
    return (
        comets.sort_values("reference")
        .drop_duplicates(subset="designation", keep="last")
        .set_index("designation", drop=False)
    )


def load_comets(path: Path) -> pd.DataFrame:
    """Parse an MPC CometEls.txt file into a de-duplicated DataFrame.

    Keeps only the most recent orbit per comet (MPC ships multiple epochs),
    indexed by ``designation``.
    """
    with load.open(str(path)) as f:
        comets = mpc.load_comets_dataframe(f)
    return _latest_orbit_per_comet(comets)


def fetch_comet_els(
    dest: Path,
    url: str = COMET_ELS_URL,
    *,
    opener: Callable[[str], object] = urllib.request.urlopen,
) -> Path:
    """Fetch fresh comet elements to ``dest``; fall back to the bundled snapshot.

    A build must never fail because the MPC is unreachable.
    """
    try:
        with opener(url) as response:  # type: ignore[attr-defined]
            body = response.read()
        if not body:
            raise OSError("empty response body")
        dest.write_bytes(body)
    except Exception as exc:
        logger.warning("comet fetch failed, using bundled fallback: %s", exc)
        fallback = oracle.data_dir() / "CometEls.fallback.txt"
        shutil.copyfile(fallback, dest)
    return dest
