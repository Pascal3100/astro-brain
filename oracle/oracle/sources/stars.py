"""Load named stars from an IAU Catalog of Star Names (IAU-CSN.txt) file."""

import re
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from oracle.sources._fetch import fetch_with_fallback

IAU_CSN_URL = "https://www.pas.rochester.edu/~emamajek/WGSN/IAU-CSN.txt"

# IAU-CSN.txt is fixed-width; the Name/ASCII field occupies characters [0:18]
# (the next field, Name/Diacritics, begins at column 18). Splitting on
# whitespace would truncate multi-word names like "Alula Australis".
_NAME_ASCII_END = 18

_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@dataclass(frozen=True)
class StarRecord:
    """One IAU-named star, J2000 (position projected to of-date later)."""

    id: str
    name: str
    designation: str | None
    ra_deg_j2000: float
    dec_deg_j2000: float
    apparent_mag: float | None
    constellation: str | None


def _tok_or_none(token: str) -> str | None:
    return None if token == "_" else token


def _float_or_none(token: str) -> float | None:
    return None if token == "_" else float(token)


def load_stars(path: Path) -> list[StarRecord]:
    """Parse an IAU-CSN.txt file into star records (J2000 decimal degrees).

    Columns are whitespace-aligned; the trailing block is fixed-order and
    one token each: ``... Con # WDS_J mag bnd HIP HD RA Dec Date [Notes]``.
    We find the Date token and index the rest relative to it.
    """
    stars: list[StarRecord] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.rstrip()
        if not line or line.startswith("#"):
            continue
        toks = line.split()
        date_idx = next((i for i, t in enumerate(toks) if _DATE.match(t)), None)
        if date_idx is None or date_idx < 9:
            continue  # malformed / non-data line
        ra = _float_or_none(toks[date_idx - 2])
        dec = _float_or_none(toks[date_idx - 1])
        if ra is None or dec is None:
            continue
        name = line[:_NAME_ASCII_END].strip()
        hip = _tok_or_none(toks[date_idx - 4])
        mag = _float_or_none(toks[date_idx - 6])
        con = _tok_or_none(toks[date_idx - 9])
        star_id = f"star:HIP{hip}" if hip is not None else f"star:{name}"
        stars.append(
            StarRecord(
                id=star_id,
                name=name,
                designation=f"HIP {hip}" if hip is not None else None,
                ra_deg_j2000=ra % 360.0,
                dec_deg_j2000=dec,
                apparent_mag=mag,
                constellation=con,
            )
        )
    return stars


def fetch_iau_csn(
    dest: Path,
    url: str = IAU_CSN_URL,
    *,
    opener: Callable[[str], object] = urllib.request.urlopen,
) -> Path:
    """Fetch fresh IAU-CSN to ``dest``; fall back to the bundled snapshot on failure."""
    return fetch_with_fallback(dest, url, "IAU-CSN.fallback.txt", opener=opener)
