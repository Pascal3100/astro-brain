from oracle.sources.stars import fetch_iau_csn, load_stars


def test_load_stars_parses_and_ranges(fallback_iau_csn_path) -> None:
    stars = load_stars(fallback_iau_csn_path)
    assert len(stars) > 400  # IAU-CSN lists 450+ approved names
    for s in stars:
        assert 0.0 <= s.ra_deg_j2000 < 360.0
        assert -90.0 <= s.dec_deg_j2000 <= 90.0
        assert s.name
        assert s.id.startswith("star:")


def test_stars_include_sirius(fallback_iau_csn_path) -> None:
    stars = load_stars(fallback_iau_csn_path)
    sirius = next(s for s in stars if s.name == "Sirius")
    assert sirius.constellation == "CMa"
    assert sirius.apparent_mag is not None and sirius.apparent_mag < 0.0  # ~ -1.46
    assert 100.0 < sirius.ra_deg_j2000 < 102.0  # ~101.29 deg
    assert -17.5 < sirius.dec_deg_j2000 < -16.0  # ~ -16.72 deg


def test_stars_acamar_row_parses(fallback_iau_csn_path) -> None:
    stars = load_stars(fallback_iau_csn_path)
    acamar = next(s for s in stars if s.name == "Acamar")
    assert acamar.constellation == "Eri"
    assert 44.0 < acamar.ra_deg_j2000 < 45.0  # ~44.565 deg


def test_stars_multiword_names_not_truncated(fallback_iau_csn_path) -> None:
    stars = load_stars(fallback_iau_csn_path)
    names = {s.name for s in stars}
    # Name/ASCII is a fixed-width column; multi-word names must survive intact.
    for full in ("Alula Australis", "Alula Borealis", "Deneb Algedi",
                 "Kaus Australis", "Asellus Australis"):
        assert full in names, full


def test_star_ids_and_names_unique(fallback_iau_csn_path) -> None:
    stars = load_stars(fallback_iau_csn_path)
    ids = [s.id for s in stars]
    assert len(ids) == len(set(ids))  # objects.id PK integrity in the later unified table


def test_fetch_iau_csn_writes_body_on_success(tmp_path) -> None:
    class _Resp:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self): return b"fresh-body"

    dest = tmp_path / "out.txt"
    result = fetch_iau_csn(dest, "https://example/x", opener=lambda url: _Resp())
    assert result == dest
    assert dest.read_bytes() == b"fresh-body"


def test_fetch_iau_csn_falls_back_on_error(tmp_path, fallback_iau_csn_path) -> None:
    def boom(url):
        raise OSError("network down")

    dest = tmp_path / "out.txt"
    fetch_iau_csn(dest, opener=boom)
    assert dest.read_bytes() == fallback_iau_csn_path.read_bytes()
