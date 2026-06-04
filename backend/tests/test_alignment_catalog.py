"""Tests pour _alignment_catalog (chargement + sélection candidates)."""
from __future__ import annotations

from datetime import UTC, datetime

from astro_brain.services._alignment_catalog import (
    MountLimits,
    Observer,
    load_catalog,
    select_candidates,
    sky_az_alt_from_ra_dec,
)


def test_load_catalog_returns_at_least_30_stars() -> None:
    stars = load_catalog()
    assert len(stars) >= 30
    assert all(s.mag < 2.5 for s in stars)


def test_load_catalog_ids_unique() -> None:
    stars = load_catalog()
    ids = [s.id for s in stars]
    assert len(set(ids)) == len(ids)


def test_sky_az_alt_known_value() -> None:
    """Vega vue de Paris à 22:00 UTC le 1er juin 2026 doit être au-dessus
    de l'horizon (vérification sanity-check, pas précision arc-min)."""
    obs = Observer(lat_deg=48.8566, lon_deg=2.3522)
    when = datetime(2026, 6, 1, 22, 0, tzinfo=UTC)
    az, alt = sky_az_alt_from_ra_dec(279.234, 38.784, obs, when)
    assert -360 < az < 360
    assert alt > 20  # Vega bien visible en juin tard


def test_select_candidates_filters_below_horizon() -> None:
    obs = Observer(lat_deg=48.8566, lon_deg=2.3522)
    when = datetime(2026, 6, 1, 22, 0, tzinfo=UTC)
    limits = MountLimits(alt_min=10.0, alt_max=85.0, az_min=0.0, az_max=360.0)
    candidates = select_candidates(obs, when, limits, exclude_ids=set())
    assert len(candidates) == 3
    for star in candidates:
        _, alt = sky_az_alt_from_ra_dec(star.ra_deg, star.dec_deg, obs, when)
        assert alt > 20


def test_select_candidates_distribution_around_120_az() -> None:
    obs = Observer(lat_deg=48.8566, lon_deg=2.3522)
    when = datetime(2026, 6, 1, 22, 0, tzinfo=UTC)
    limits = MountLimits(alt_min=10.0, alt_max=85.0, az_min=0.0, az_max=360.0)
    candidates = select_candidates(obs, when, limits, exclude_ids=set())
    azs = sorted(
        sky_az_alt_from_ra_dec(s.ra_deg, s.dec_deg, obs, when)[0] % 360.0
        for s in candidates
    )
    # Spans entre voisins (cyclique) : on attend 3 spans dont chacun > 60° et < 200°
    cyclic_diffs = [
        (azs[(i + 1) % 3] - azs[i]) % 360.0 for i in range(3)
    ]
    for d in cyclic_diffs:
        assert 60 <= d <= 200


def test_select_candidates_excludes_ids() -> None:
    obs = Observer(lat_deg=48.8566, lon_deg=2.3522)
    when = datetime(2026, 6, 1, 22, 0, tzinfo=UTC)
    limits = MountLimits(alt_min=10.0, alt_max=85.0, az_min=0.0, az_max=360.0)
    first = select_candidates(obs, when, limits, exclude_ids=set())
    excluded = {first[0].id}
    second = select_candidates(obs, when, limits, exclude_ids=excluded)
    assert all(s.id not in excluded for s in second)


def test_constellation_of_extracts_iau_abbr() -> None:
    from astro_brain.services._alignment_catalog import constellation_of
    from astro_brain.models.alignment import Star

    def _star(bayer: str) -> Star:
        return Star(id="x", name="X", bayer=bayer, ra_deg=0.0, dec_deg=0.0, mag=1.0)

    assert constellation_of(_star("α CMa")) == "CMa"
    assert constellation_of(_star("β UMa")) == "UMa"


def test_constellation_of_handles_no_greek_prefix() -> None:
    from astro_brain.services._alignment_catalog import constellation_of
    from astro_brain.models.alignment import Star

    def _star(bayer: str) -> Star:
        return Star(id="x", name="X", bayer=bayer, ra_deg=0.0, dec_deg=0.0, mag=1.0)

    # Certains bayer n'ont pas de lettre grecque (ex. designation Flamsteed).
    assert constellation_of(_star("51 Peg")) == "Peg"


def test_constellation_of_returns_none_when_unparseable() -> None:
    from astro_brain.services._alignment_catalog import constellation_of
    from astro_brain.models.alignment import Star

    def _star(bayer: str) -> Star:
        return Star(id="x", name="X", bayer=bayer, ra_deg=0.0, dec_deg=0.0, mag=1.0)

    assert constellation_of(_star("")) is None
    assert constellation_of(_star("Sirius")) is None


def test_gmst_known_epoch() -> None:
    """GMST à J2000.0 (2000-01-01 12:00 UTC) ≈ 280.4606° (textbook IAU 1982).

    Pin pour empêcher régression du bug de 0.5° (T₀ doit être évalué à 0h UT,
    pas à l'instant complet).
    """
    from astro_brain.services._ephemeris import _gmst_deg

    when = datetime(2000, 1, 1, 12, 0, tzinfo=UTC)
    gmst = _gmst_deg(when)
    assert abs(gmst - 280.4606) < 0.01
