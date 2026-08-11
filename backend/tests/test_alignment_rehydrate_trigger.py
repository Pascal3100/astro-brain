"""Test du déclencheur one-shot de réhydratation d'alignement au boot."""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

from astro_brain.app import _rehydrate_alignment_once
from astro_brain.bus import StateBus
from astro_brain.subsystems import GpsState, SubsystemState


async def test_trigger_rehydrates_and_publishes_on_first_gps_fix() -> None:
    bus = StateBus()
    alignment = MagicMock()
    alignment.rehydrate = AsyncMock(return_value=True)

    task = asyncio.create_task(_rehydrate_alignment_once(bus, alignment))
    # Un état GPS sans fix ne doit PAS déclencher la réhydratation.
    bus.publish("gps", SubsystemState(state=GpsState.NO_FIX.value, since=datetime.now(UTC)))
    await asyncio.sleep(0)
    # Premier fix → réhydratation + republication, puis la task se termine seule.
    bus.publish("gps", SubsystemState(state=GpsState.FIX_3D.value, since=datetime.now(UTC)))
    await asyncio.wait_for(task, timeout=1.0)

    alignment.rehydrate.assert_awaited_once()
    aligned = bus.get_full_state().subsystems["alignment"]
    assert aligned.details["is_aligned"] is True


async def test_trigger_does_not_publish_when_nothing_to_restore() -> None:
    bus = StateBus()
    alignment = MagicMock()
    alignment.rehydrate = AsyncMock(return_value=False)  # rien de valide sur disque

    task = asyncio.create_task(_rehydrate_alignment_once(bus, alignment))
    bus.publish("gps", SubsystemState(state=GpsState.FIX_3D.value, since=datetime.now(UTC)))
    await asyncio.wait_for(task, timeout=1.0)

    alignment.rehydrate.assert_awaited_once()
    assert "alignment" not in bus.get_full_state().subsystems  # aucune republication
