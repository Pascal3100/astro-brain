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


def test_dedup_keeps_whole_newest_row_not_per_column_mix() -> None:
    import numpy as np
    import pandas as pd

    from oracle.sources.comets import _latest_orbit_per_comet

    df = pd.DataFrame(
        {
            "designation": ["1P/Halley", "1P/Halley"],
            "reference": ["MPEC 2020-A1", "MPEC 2021-A1"],
            "eccentricity": [0.9, 0.8],
            "magnitude_g": [5.0, np.nan],  # newest row has NaN magnitude
        }
    )
    result = _latest_orbit_per_comet(df)
    assert len(result) == 1
    row = result.loc["1P/Halley"]
    assert row["reference"] == "MPEC 2021-A1"
    assert row["eccentricity"] == 0.8
    # the NaN in the newest row must NOT be back-filled from the older row
    assert pd.isna(row["magnitude_g"])
