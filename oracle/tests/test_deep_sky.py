from oracle.sources.deep_sky import fetch_open_ngc, load_deep_sky


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


def _fake_opener(bodies: dict[str, bytes]):
    """Return an opener that yields ``bodies[url]`` as a context-managed reader."""
    def opener(url: str):
        body = bodies[url]

        class _Resp:
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def read(self): return body

        return _Resp()

    return opener


def test_fetch_open_ngc_merges_main_and_addendum(tmp_path) -> None:
    opener = _fake_opener({
        "http://x/NGC.csv": b"H\nmain1\nmain2\n",
        "http://x/addendum.csv": b"H\nadd1\n",
    })
    dest = tmp_path / "out.csv"
    fetch_open_ngc(dest, "http://x/NGC.csv", "http://x/addendum.csv", opener=opener)
    # addendum header dropped, its body appended once after the main body
    assert dest.read_bytes() == b"H\nmain1\nmain2\nadd1\n"


def test_fetch_open_ngc_falls_back_on_error(tmp_path, fallback_open_ngc_path) -> None:
    def opener(url):
        raise OSError("network down")

    dest = tmp_path / "out.csv"
    fetch_open_ngc(dest, opener=opener)
    assert dest.read_bytes() == fallback_open_ngc_path.read_bytes()


def test_fetch_open_ngc_falls_back_on_empty_addendum(tmp_path, fallback_open_ngc_path) -> None:
    opener = _fake_opener({
        "http://x/NGC.csv": b"H\nmain1\n",
        "http://x/addendum.csv": b"",
    })
    dest = tmp_path / "out.csv"
    fetch_open_ngc(dest, "http://x/NGC.csv", "http://x/addendum.csv", opener=opener)
    assert dest.read_bytes() == fallback_open_ngc_path.read_bytes()
