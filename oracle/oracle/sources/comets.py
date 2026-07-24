"""Load comet orbital elements from an MPC CometEls.txt file."""

from pathlib import Path

import pandas as pd
from skyfield.api import load
from skyfield.data import mpc


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
