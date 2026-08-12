# backend/tests/test_logging_config.py
"""Le backend doit configurer le root logger, sinon les INFO sont perdus.

Constaté sur le Pi le 2026-08-12 : uvicorn ne configure que ses propres
loggers, le root restait à WARNING, et tous les `logger.info` du package
(transitions GPS, issue du sync `reference.sqlite`) n'atteignaient jamais
journald.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator

import pytest

from astro_brain.main import LOG_LEVEL_ENV, configure_logging


@pytest.fixture(autouse=True)
def _restore_root_level() -> Iterator[None]:
    """Rendre son niveau au root logger : il est global au process pytest."""
    root = logging.getLogger()
    previous = root.level
    try:
        yield
    finally:
        root.setLevel(previous)


def test_package_info_logs_are_enabled_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(LOG_LEVEL_ENV, raising=False)
    logging.getLogger().setLevel(logging.WARNING)  # le défaut Python nu

    configure_logging()

    assert logging.getLogger("astro_brain.app").isEnabledFor(logging.INFO)


def test_level_is_overridable_by_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(LOG_LEVEL_ENV, "warning")  # casse insensible

    configure_logging()

    logger = logging.getLogger("astro_brain.app")
    assert not logger.isEnabledFor(logging.INFO)
    assert logger.isEnabledFor(logging.WARNING)
