from pathlib import Path

import pytest

import oracle


@pytest.fixture
def kernel_path() -> Path:
    return oracle.data_dir() / "de421.bsp"


@pytest.fixture
def fallback_comets_path() -> Path:
    return oracle.data_dir() / "CometEls.fallback.txt"
