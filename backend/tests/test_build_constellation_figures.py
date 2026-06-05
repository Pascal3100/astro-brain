from pathlib import Path

from scripts.build_constellation_figures import parse_fab_lines


def test_parse_fab_lines_returns_segments_as_hip_pairs():
    fab = (Path(__file__).parent / "fixtures" / "western_lines_sample.fab").read_text()
    figures = parse_fab_lines(fab)
    assert set(figures) == {"UMa", "CMa"}
    assert len(figures["UMa"]) == 6
    assert figures["UMa"][0] == (4301, 4295)
    assert figures["CMa"] == [(2491, 2657), (2657, 2693)]
