from pathlib import Path

import pytest

import oracle


@pytest.fixture
def kernel_path() -> Path:
    return oracle.data_dir() / "de421.bsp"


@pytest.fixture
def fallback_comets_path() -> Path:
    return oracle.data_dir() / "CometEls.fallback.txt"


@pytest.fixture
def fallback_open_ngc_path() -> Path:
    return oracle.data_dir() / "OpenNGC.fallback.csv"


@pytest.fixture
def fallback_iau_csn_path() -> Path:
    return oracle.data_dir() / "IAU-CSN.fallback.txt"
