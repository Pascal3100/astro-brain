from oracle.sources.deep_sky import load_deep_sky


def test_load_deep_sky_parses_and_ranges(fallback_open_ngc_path) -> None:
    records = load_deep_sky(fallback_open_ngc_path)
    assert len(records) > 10000  # OpenNGC ships ~13k physical objects
    for r in records[:200]:
        assert 0.0 <= r.ra_deg_j2000 < 360.0
        assert -90.0 <= r.dec_deg_j2000 <= 90.0
        assert r.ngc_ic  # every deep-sky object carries an NGC/IC-style designation


def test_deep_sky_covers_all_110_messier(fallback_open_ngc_path) -> None:
    records = load_deep_sky(fallback_open_ngc_path)
    messier = {r.messier for r in records if r.messier}
    assert len(messier) == 110  # M1..M110, all present exactly once as a set


def test_deep_sky_m42_is_the_orion_nebula(fallback_open_ngc_path) -> None:
    records = load_deep_sky(fallback_open_ngc_path)
    m42 = next(r for r in records if r.messier == "M42")
    assert m42.ngc_ic == "NGC1976"
    assert m42.object_type == "nebula"
    assert m42.constellation == "Ori"
    # of-date projection happens later; here RA/Dec are raw J2000
    assert 83.0 < m42.ra_deg_j2000 < 84.5
    assert -6.0 < m42.dec_deg_j2000 < -5.0


def test_deep_sky_skips_non_physical_types(fallback_open_ngc_path) -> None:
    records = load_deep_sky(fallback_open_ngc_path)
    types = {r.object_type for r in records}
    # Dup / NonEx / Other are dropped, so no record maps to them
    assert None not in types
