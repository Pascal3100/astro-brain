"""Load comet orbital elements from an MPC CometEls.txt file."""

import urllib.request
from collections.abc import Callable
from pathlib import Path

import pandas as pd
from skyfield.api import load
from skyfield.data import mpc

from oracle.records import CometElements, ObjectRow
from oracle.sources._fetch import fetch_with_fallback

COMET_ELS_URL = "https://www.minorplanetcenter.net/iau/MPCORB/CometEls.txt"


def _opt(row: pd.Series, key: str) -> float | None:
    """Return ``row[key]`` as a float, or ``None`` when missing/NaN."""
    value = row.get(key)
    return float(value) if pd.notna(value) else None


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
    """Fetch fresh comet elements to ``dest``; fall back to the bundled snapshot."""
    return fetch_with_fallback(dest, url, "CometEls.fallback.txt", opener=opener)


def comet_objects(comets: pd.DataFrame) -> tuple[list[ObjectRow], list[CometElements]]:
    """Split a comet DataFrame into identity rows + orbital-element rows.

    The id is the MPC designation (also used as the ephemeris ``object_id``),
    so ephemeris FK integrity holds against ``objects``.
    """
    objs: list[ObjectRow] = []
    elems: list[CometElements] = []
    for designation, row in comets.iterrows():
        oid = str(designation)
        name = str(row["name"]) if pd.notna(row.get("name")) else None
        objs.append(
            ObjectRow(
                id=oid,
                kind="comet",
                name=name,
                designation=str(row.get("designation", designation)),
            )
        )
        elems.append(
            CometElements(
                object_id=oid,
                epoch_jd=_opt(row, "epoch_jd"),
                perihelion_q_au=float(row["perihelion_distance_au"]),
                eccentricity=float(row["eccentricity"]),
                inclination_deg=float(row["inclination_degrees"]),
                arg_perihelion_deg=float(row["argument_of_perihelion_degrees"]),
                node_deg=float(row["longitude_of_ascending_node_degrees"]),
                mag_h=_opt(row, "magnitude_g"),
                mag_k=_opt(row, "magnitude_k"),
            )
        )
    return objs, elems
