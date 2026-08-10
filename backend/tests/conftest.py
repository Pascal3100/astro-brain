"""Shared test fixtures."""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _isolated_state_dir(tmp_path_factory, monkeypatch: pytest.MonkeyPatch) -> None:
    """Point `ASTRO_BRAIN_STATE_DIR` at a throwaway directory for every test.

    `build_app(db_path_override=":memory:")` (used throughout the test suite
    for an ephemeral state DB) still resolves a real on-disk path for the
    separate `reference.sqlite` file via `reference_path()`. Without this
    fixture that call falls back to the production default
    (`/var/lib/astro-brain`), which does not exist and is not writable
    outside the Pi. A test can still override the env var itself (e.g.
    `test_db_path_honors_env`); `monkeypatch.setenv` composes fine either way.
    """
    monkeypatch.setenv(
        "ASTRO_BRAIN_STATE_DIR", str(tmp_path_factory.mktemp("state"))
    )
