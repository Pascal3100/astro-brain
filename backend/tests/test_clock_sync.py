"""Tests de la sonde de synchronisation d'horloge."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from astro_brain.adapters import clock_sync


@pytest.fixture(autouse=True)
def _clear_cache() -> None:
    clock_sync.reset_cache()


def _use_timesyncd(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, *, synced: bool):
    """Simule un hôte sous systemd-timesyncd, synchronisé ou non."""
    timesync_dir = tmp_path / "timesync"
    timesync_dir.mkdir()
    flag = timesync_dir / "synchronized"
    if synced:
        flag.touch()
    monkeypatch.setattr(clock_sync, "TIMESYNCD_FLAG", flag)


def test_timesyncd_flag_present_means_synced(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _use_timesyncd(monkeypatch, tmp_path, synced=True)
    assert clock_sync.is_clock_synced() is True


def test_timesyncd_flag_absent_means_not_synced(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Le démon tourne mais n'a jamais réussi de synchro : on refuse."""
    _use_timesyncd(monkeypatch, tmp_path, synced=False)
    assert clock_sync.is_clock_synced() is False


def _use_timedatectl(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, stdout: str,
                     returncode: int = 0) -> list[list[str]]:
    """Simule un hôte sans timesyncd (chrony…) : seul `timedatectl` répond."""
    monkeypatch.setattr(clock_sync, "TIMESYNCD_FLAG", tmp_path / "absent" / "synchronized")
    calls: list[list[str]] = []

    def _fake_run(cmd, **_kwargs):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, returncode, stdout=stdout, stderr="")

    monkeypatch.setattr(clock_sync.subprocess, "run", _fake_run)
    return calls


def test_falls_back_to_timedatectl_when_timesyncd_is_absent(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls = _use_timedatectl(monkeypatch, tmp_path, stdout="yes\n")
    assert clock_sync.is_clock_synced() is True
    assert calls and calls[0][0] == "timedatectl"


def test_timedatectl_reporting_no_means_not_synced(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _use_timedatectl(monkeypatch, tmp_path, stdout="no\n")
    assert clock_sync.is_clock_synced() is False


def test_timedatectl_result_is_cached(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Le sous-processus ne doit pas repartir à chaque tick de 5 s."""
    calls = _use_timedatectl(monkeypatch, tmp_path, stdout="yes\n")
    for _ in range(5):
        clock_sync.is_clock_synced()
    assert len(calls) == 1


def test_unreadable_probe_is_treated_as_not_synced(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Une sonde en échec vaut « non synchronisé » : on ne pousse pas au hasard."""
    monkeypatch.setattr(clock_sync, "TIMESYNCD_FLAG", tmp_path / "absent" / "synchronized")

    def _boom(*_args, **_kwargs):
        raise FileNotFoundError("timedatectl")

    monkeypatch.setattr(clock_sync.subprocess, "run", _boom)
    assert clock_sync.is_clock_synced() is False
