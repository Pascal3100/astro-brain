"""Tests for :func:`astro_brain.adapters.system_info.compute_state`.

Only the pure threshold-classification function is exercised here —
sysfs/procfs reads are covered by manual smoke tests on the Pi (see the
deployment checklist in Task 17).
"""

from __future__ import annotations

from astro_brain.adapters.system_info import (
    CRIT_TEMP_C,
    WARN_LOAD,
    WARN_TEMP_C,
    compute_state,
)


def test_compute_state_ok_when_below_all_thresholds() -> None:
    assert compute_state(cpu_temp_c=45.0, cpu_load=0.3) == "ok"


def test_compute_state_warning_above_temp_threshold() -> None:
    assert compute_state(cpu_temp_c=WARN_TEMP_C, cpu_load=0.1) == "warning"


def test_compute_state_warning_above_load_threshold() -> None:
    assert compute_state(cpu_temp_c=40.0, cpu_load=WARN_LOAD) == "warning"


def test_compute_state_critical_above_crit_temp() -> None:
    assert compute_state(cpu_temp_c=CRIT_TEMP_C, cpu_load=0.0) == "critical"


def test_compute_state_critical_trumps_load() -> None:
    # critical temp wins even when load is high
    assert compute_state(cpu_temp_c=CRIT_TEMP_C + 5, cpu_load=10.0) == "critical"
