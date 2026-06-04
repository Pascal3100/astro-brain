from datetime import UTC, datetime

from astro_brain.services._ephemeris import Observer
from astro_brain.services.constellation_figures import (
    figure_for, load_figures, render_figure,
)


def test_load_figures_integrity_segments_reference_existing_nodes():
    figures = load_figures()
    assert figures, "asset non vide attendu"
    for abbr, fig in figures.items():
        n = len(fig["nodes"])
        for a, b in fig["segments"]:
            assert 0 <= a < n and 0 <= b < n, f"{abbr}: segment hors bornes"


def test_figure_for_known_constellation():
    fig = figure_for("UMa")
    assert fig is not None
    assert fig["name"] == "Grande Ourse"


def test_figure_for_unknown_returns_none():
    assert figure_for("ZZZ") is None


def test_render_figure_marks_target_by_proximity_and_computes_altaz():
    obs = Observer(lat_deg=43.6, lon_deg=1.44)
    t = datetime(2026, 1, 1, 22, 0, tzinfo=UTC)
    fig = figure_for("UMa")
    out = render_figure(fig, target_ra=165.932, target_dec=61.751,
                        observer=obs, t_utc=t)
    assert out["oriented"] is True
    targets = [n for n in out["nodes"] if n["is_target"]]
    assert len(targets) == 1
    assert "Dubhe" in targets[0]["label"]
    for node in out["nodes"]:
        assert "az" in node and "alt" in node


def test_render_figure_without_observer_is_not_oriented():
    fig = figure_for("UMa")
    out = render_figure(fig, target_ra=165.932, target_dec=61.751,
                        observer=None, t_utc=None)
    assert out["oriented"] is False
    assert all(n["az"] is None and n["alt"] is None for n in out["nodes"])
