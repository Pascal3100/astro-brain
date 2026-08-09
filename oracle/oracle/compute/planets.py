"""Compute daily apparent (of-date) ephemeris for planets, Moon and Sun."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from skyfield.api import Loader, load_constellation_map, position_of_radec
from skyfield.magnitudelib import planetary_magnitude

from oracle.records import EphemRow, ObjectRow


@dataclass(frozen=True)
class Body:
    """One de421 target and how to describe it in the catalogue."""

    id: str
    kind: str  # planet | moon | sun
    name: str
    target: str  # de421 body key
    mag: bool  # compute apparent magnitude via planetary_magnitude
    illum: bool  # compute illuminated fraction via fraction_illuminated


# Pluto is excluded on purpose (mag ~14, out of reach of a 127 mm; de421 has
# only its barycentre).
BODIES: list[Body] = [
    Body("planet:mercury", "planet", "Mercury", "mercury", True, True),
    Body("planet:venus", "planet", "Venus", "venus", True, True),
    Body("planet:mars", "planet", "Mars", "mars", True, False),
    Body("planet:jupiter", "planet", "Jupiter", "jupiter barycenter", True, False),
    Body("planet:saturn", "planet", "Saturn", "saturn barycenter", True, False),
    Body("planet:uranus", "planet", "Uranus", "uranus barycenter", True, False),
    Body("planet:neptune", "planet", "Neptune", "neptune barycenter", True, False),
    Body("moon", "moon", "Moon", "moon", False, True),
    Body("sun", "sun", "Sun", "sun", False, False),
]


def compute_planet_ephemeris(
    kernel_path: Path,
    start_utc: datetime,
    days: int = 60,
) -> tuple[list[ObjectRow], list[EphemRow]]:
    """Daily apparent RA/Dec (of-date) for every body in ``BODIES`` over ``days`` days."""
    if start_utc.tzinfo is None:
        start_utc = start_utc.replace(tzinfo=timezone.utc)
    else:
        start_utc = start_utc.astimezone(timezone.utc)

    loader = Loader(str(kernel_path.parent))
    eph = loader(kernel_path.name)
    ts = loader.timescale()
    sun, earth = eph["sun"], eph["earth"]
    constellation_at = load_constellation_map()

    objects = [ObjectRow(id=b.id, kind=b.kind, name=b.name, designation=None) for b in BODIES]

    rows: list[EphemRow] = []
    for b in BODIES:
        target = eph[b.target]
        for day in range(days):
            when = start_utc + timedelta(days=day)
            t = ts.from_datetime(when)
            astrometric = earth.at(t).observe(target)
            apparent = astrometric.apparent()
            ra, dec, delta = apparent.radec(epoch="date")
            mag = float(planetary_magnitude(astrometric)) if b.mag else None
            illum = float(apparent.fraction_illuminated(sun)) if b.illum else None
            sun_dist = (
                None if b.kind == "sun"
                else float(sun.at(t).observe(target).distance().au)
            )
            try:
                const = constellation_at(position_of_radec(ra.hours, dec.degrees))
            except Exception:
                const = None
            rows.append(
                EphemRow(
                    object_id=b.id,
                    sample_utc=when.isoformat().replace("+00:00", "Z"),
                    ra_deg=ra.degrees % 360.0,
                    dec_deg=dec.degrees,
                    earth_dist_au=float(delta.au),
                    sun_dist_au=sun_dist,
                    apparent_mag=mag,
                    illumination=illum,
                    constellation=const,
                )
            )
    return objects, rows
