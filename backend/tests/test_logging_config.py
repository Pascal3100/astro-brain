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

from astro_brain.main import _QUIET_LOGGERS, LOG_LEVEL_ENV, configure_logging


@pytest.fixture(autouse=True)
def _restore_levels() -> Iterator[None]:
    """Rendre leur niveau aux loggers touchés : ils sont globaux au process."""
    names = [None, *_QUIET_LOGGERS]
    previous = {name: logging.getLogger(name).level for name in names}
    try:
        yield
    finally:
        for name, level in previous.items():
            logging.getLogger(name).setLevel(level)


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


def test_chatty_libraries_are_quieted_at_info(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """httpx logue l'URL signée complète de la release Oracle (~700 car.)."""
    monkeypatch.delenv(LOG_LEVEL_ENV, raising=False)

    configure_logging()

    assert logging.getLogger("astro_brain.app").isEnabledFor(logging.INFO)
    for name in _QUIET_LOGGERS:
        assert not logging.getLogger(name).isEnabledFor(logging.INFO)


def test_debug_wins_over_the_quiet_list(monkeypatch: pytest.MonkeyPatch) -> None:
    """Demander DEBUG explicitement, c'est vouloir tout voir, httpx compris.

    Part d'un état déjà réduit au silence : un appel doit reconfigurer, pas
    seulement s'abstenir de re-réduire.
    """
    for name in _QUIET_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)
    monkeypatch.setenv(LOG_LEVEL_ENV, "DEBUG")

    configure_logging()

    for name in _QUIET_LOGGERS:
        assert logging.getLogger(name).isEnabledFor(logging.DEBUG)
