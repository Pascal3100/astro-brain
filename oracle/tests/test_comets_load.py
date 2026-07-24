from oracle.sources.comets import load_comets


def test_load_comets_returns_unique_designations(fallback_comets_path) -> None:
    df = load_comets(fallback_comets_path)
    assert len(df) > 0
    # dedup: one orbit per comet
    assert df.index.is_unique
    assert df.index.name == "designation"
    # sanity on required orbital columns
    for col in ("perihelion_distance_au", "eccentricity", "inclination_degrees"):
        assert col in df.columns
