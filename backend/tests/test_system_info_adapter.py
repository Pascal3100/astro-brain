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


def test_publish_includes_clock_synced(monkeypatch) -> None:
    """`clock_synced` sort dans les détails, sans peser sur l'état système.

    Une horloge non synchronisée est légitime hors réseau : elle informe
    l'app et bloque la poussée d'heure, elle ne dégrade pas `system`.
    """
    from astro_brain.adapters import system_info
    from astro_brain.bus import StateBus

    monkeypatch.setattr(system_info, "_read_temp_c", lambda: 45.0)
    monkeypatch.setattr(system_info, "_read_loadavg_1min", lambda: 0.2)
    monkeypatch.setattr(system_info, "_read_uptime_s", lambda: 1234)
    monkeypatch.setattr(system_info, "is_clock_synced", lambda: False)

    bus = StateBus()
    system_info.SystemInfoAdapter(bus)._publish_current()

    published = bus.get_full_state().subsystems["system"]
    assert published.details["clock_synced"] is False
    assert published.state == "ok"
