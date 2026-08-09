from datetime import datetime, timezone

from oracle.compute.planets import compute_planet_ephemeris


def test_nine_bodies_over_window(kernel_path) -> None:
    start = datetime(2026, 8, 1, tzinfo=timezone.utc)
    objects, rows = compute_planet_ephemeris(kernel_path, start, days=3)
    ids = {o.id for o in objects}
    assert ids == {
        "planet:mercury", "planet:venus", "planet:mars", "planet:jupiter",
        "planet:saturn", "planet:uranus", "planet:neptune", "moon", "sun",
    }
    assert len({o.kind for o in objects}) == 3  # planet / moon / sun
    assert len(rows) == 9 * 3  # 9 bodies x 3 daily samples


def test_planet_ranges_and_magnitude(kernel_path) -> None:
    start = datetime(2026, 8, 1, tzinfo=timezone.utc)
    _, rows = compute_planet_ephemeris(kernel_path, start, days=2)
    for r in rows:
        assert 0.0 <= r.ra_deg < 360.0
        assert -90.0 <= r.dec_deg <= 90.0
        assert r.sample_utc.endswith("Z")
    # Mars carries a real apparent magnitude (planetary_magnitude)
    mars = [r for r in rows if r.object_id == "planet:mars"]
    assert all(r.apparent_mag is not None for r in mars)


def test_moon_has_illumination_planets_may_not(kernel_path) -> None:
    start = datetime(2026, 8, 1, tzinfo=timezone.utc)
    _, rows = compute_planet_ephemeris(kernel_path, start, days=1)
    moon = next(r for r in rows if r.object_id == "moon")
    assert moon.illumination is not None and 0.0 <= moon.illumination <= 1.0
    jupiter = next(r for r in rows if r.object_id == "planet:jupiter")
    assert jupiter.illumination is None
    # the Sun has no "distance to Sun"
    sun = next(r for r in rows if r.object_id == "sun")
    assert sun.sun_dist_au is None
