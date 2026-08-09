"""Unified output model for the reference.sqlite v2 artifact.

One dataclass per target table. Every writer input and every compute/source
output is expressed with these types, so the schema has a single source of
truth on the Python side too.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ObjectRow:
    """Identity row, common to every catalogue object (table ``objects``)."""

    id: str  # stable id: packed MPC / "planet:mars" / "moon" / "NGC1976" / "star:HIP32349"
    kind: str  # comet | planet | moon | sun | dso | star
    name: str | None
    designation: str | None


@dataclass(frozen=True)
class FixedRow:
    """Static position + attributes for a fixed object (table ``fixed_object``)."""

    object_id: str
    ra_deg: float  # of-date JNow at generation time
    dec_deg: float
    apparent_mag: float | None
    object_type: str | None  # galaxy / nebula / cluster / double-star / star / ...
    size_arcmin: float | None
    constellation: str | None
    messier: str | None  # "M42" if applicable
    ngc_ic: str | None  # "NGC1976" / "IC434"


@dataclass(frozen=True)
class EphemRow:
    """One daily apparent-position sample for an ephemeral object (table ``ephemeris``)."""

    object_id: str
    sample_utc: str  # ISO-8601 UTC, "Z" suffix
    ra_deg: float  # of-date JNow
    dec_deg: float
    earth_dist_au: float | None
    sun_dist_au: float | None
    apparent_mag: float | None  # reliable for planets/luminaries; estimate for comets
    illumination: float | None  # illuminated fraction 0..1 (Moon/Venus/Mercury); NULL otherwise
    constellation: str | None


@dataclass(frozen=True)
class CometElements:
    """Comet-specific orbital elements (table ``comet_elements``)."""

    object_id: str
    epoch_jd: float | None
    perihelion_q_au: float
    eccentricity: float
    inclination_deg: float
    arg_perihelion_deg: float
    node_deg: float
    # mag_h/mag_k = comet total-magnitude params (g, k),
    # m = g + 5*log10(delta) + 2.5*k*log10(r); NOT the asteroid H,G system.
    mag_h: float | None
    mag_k: float | None
