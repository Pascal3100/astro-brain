"""Load deep-sky objects (Messier + NGC/IC) from an OpenNGC CSV file."""

import re
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from oracle.sources._fetch import fetch_with_fallback

OPEN_NGC_URL = (
    "https://raw.githubusercontent.com/mattiaverga/OpenNGC/master/database_files/NGC.csv"
)

# OpenNGC Type codes → coarse object_type used by the catalogue.
_TYPE_MAP = {
    "G": "galaxy", "GPair": "galaxy", "GTrpl": "galaxy", "GGroup": "galaxy",
    "PN": "nebula", "HII": "nebula", "EmN": "nebula", "RfN": "nebula",
    "Neb": "nebula", "SNR": "nebula", "DrkN": "nebula",
    # "Cl+N" (cluster embedded in nebulosity, e.g. M42/Orion, IC1805/Heart,
    # IC1848/Soul, NGC1333) is dominated by the nebula visually and in
    # amateur usage, so it is classed as "nebula" rather than "cluster".
    "Cl+N": "nebula", "OCl": "cluster", "GCl": "cluster", "*Ass": "cluster",
    "*": "star", "**": "double-star",
}
# Non-physical / bookkeeping rows we never expose.
_SKIP_TYPES = {"Dup", "NonEx", "Other"}

_DESIG = re.compile(r"([A-Za-z]+)0*(\d.*)")
_MESSIER_NAME = re.compile(r"^M0*(\d+)$")


@dataclass(frozen=True)
class OpenNgcRecord:
    """One deep-sky object, J2000 (position projected to of-date later)."""

    id: str
    name: str | None
    designation: str
    object_type: str
    ra_deg_j2000: float
    dec_deg_j2000: float
    apparent_mag: float | None
    size_arcmin: float | None
    constellation: str | None
    messier: str | None
    ngc_ic: str


def _normalize_designation(name: str) -> str:
    """"NGC0224" -> "NGC224", "IC0434" -> "IC434", "Mel022" -> "Mel22"."""
    m = _DESIG.match(name)
    return f"{m.group(1)}{m.group(2)}" if m else name


def _hms_to_deg(value: str) -> float:
    """Sexagesimal RA "HH:MM:SS.SS" -> degrees."""
    h, m, s = value.split(":")
    return (int(h) + int(m) / 60.0 + float(s) / 3600.0) * 15.0


def _dms_to_deg(value: str) -> float:
    """Sexagesimal Dec "+DD:MM:SS.S" -> degrees."""
    sign = -1.0 if value.strip().startswith("-") else 1.0
    d, m, s = value.replace("+", "").replace("-", "").split(":")
    return sign * (int(d) + int(m) / 60.0 + float(s) / 3600.0)


def _float_or_none(value: object) -> float | None:
    return float(value) if pd.notna(value) and str(value).strip() != "" else None


def _messier_number(name: str, m_column: str) -> str | None:
    """Return the Messier id ("M42"), preferring a self-identifying ``Name``.

    OpenNGC's addendum marks the disputed M102 row as a "Dup" whose ``M``
    cross-reference column points at 101 (NED's assumption that M102 is a
    duplicate observation of M101). That cross-reference would otherwise
    make M102 unreachable, so a row whose own ``Name`` already reads
    "M<number>" (e.g. "M102", "M040") is trusted over the ``M`` column.
    """
    name_match = _MESSIER_NAME.match(name)
    if name_match:
        return f"M{int(name_match.group(1))}"
    return f"M{int(m_column)}" if m_column else None


def load_deep_sky(path: Path) -> list[OpenNgcRecord]:
    """Parse an OpenNGC CSV into deep-sky records (J2000, non-physical rows dropped)."""
    df = pd.read_csv(path, sep=";", dtype=str, keep_default_na=False)
    records: list[OpenNgcRecord] = []
    for _, row in df.iterrows():
        type_code = row["Type"].strip()
        messier = _messier_number(row["Name"].strip(), row["M"].strip())
        # A row carrying an M number is always a valid catalogue target (it is
        # one of the 110 Messier objects), even when its OpenNGC Type is a
        # bookkeeping code (Dup/NonEx/Other) or otherwise unmapped — e.g. M24
        # (star cloud), M40 (double star), M73 (asterism), M102 (disputed
        # duplicate). Such rows are kept and coarsely typed as "other"
        # instead of being dropped by the skip/unmapped-type filters below.
        if messier is None:
            if type_code in _SKIP_TYPES:
                continue
            object_type = _TYPE_MAP.get(type_code)
            if object_type is None:
                continue
        else:
            object_type = _TYPE_MAP.get(type_code, "other")
        ra_raw, dec_raw = row["RA"].strip(), row["Dec"].strip()
        if not ra_raw or not dec_raw:
            continue  # rows without a position are not usable targets
        designation = _normalize_designation(row["Name"].strip())
        common = row["Common names"].strip()
        name = common.split(",")[0] if common else None
        v_mag = _float_or_none(row["V-Mag"])
        b_mag = _float_or_none(row["B-Mag"])
        records.append(
            OpenNgcRecord(
                id=designation,
                name=name,
                designation=designation,
                object_type=object_type,
                ra_deg_j2000=_hms_to_deg(ra_raw),
                dec_deg_j2000=_dms_to_deg(dec_raw),
                apparent_mag=v_mag if v_mag is not None else b_mag,
                size_arcmin=_float_or_none(row["MajAx"]),
                constellation=row["Const"].strip() or None,
                messier=messier,
                ngc_ic=designation,
            )
        )
    return records


def fetch_open_ngc(
    dest: Path,
    url: str = OPEN_NGC_URL,
    *,
    opener: Callable[[str], object] = urllib.request.urlopen,
) -> Path:
    """Fetch fresh OpenNGC to ``dest``; fall back to the bundled snapshot on failure."""
    return fetch_with_fallback(dest, url, "OpenNGC.fallback.csv", opener=opener)
