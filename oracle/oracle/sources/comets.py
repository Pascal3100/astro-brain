"""Load comet orbital elements from an MPC CometEls.txt file."""

from pathlib import Path

import pandas as pd
from skyfield.api import load
from skyfield.data import mpc


def load_comets(path: Path) -> pd.DataFrame:
    """Parse an MPC CometEls.txt file into a de-duplicated DataFrame.

    Keeps only the most recent orbit per comet (MPC ships multiple epochs),
    indexed by ``designation``.
    """
    with load.open(str(path)) as f:
        comets = mpc.load_comets_dataframe(f)
    comets = (
        comets.sort_values("reference")
        .groupby("designation", as_index=False)
        .last()
        .set_index("designation", drop=False)
    )
    comets.index.name = "designation"
    return comets
