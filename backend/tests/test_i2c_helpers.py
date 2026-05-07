"""Tests for the I2C helper module (lazy smbus2 import + stub bus)."""

import sys
from unittest.mock import MagicMock

import pytest

from astro_brain.adapters._i2c_helpers import open_bus, read_bytes, write_byte


def test_open_bus_returns_stub_when_hardware_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ASTRO_BRAIN_HARDWARE", raising=False)
    bus = open_bus()
    write_byte(bus, 0x1E, 0x20, 0x42)
    assert read_bytes(bus, 0x1E, 0x20, 1) == b"\x42"


def test_open_bus_treats_zero_as_stub(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ASTRO_BRAIN_HARDWARE", "0")
    bus = open_bus()
    write_byte(bus, 0x53, 0x31, 0x0B)
    assert read_bytes(bus, 0x53, 0x31, 1) == b"\x0b"


def test_open_bus_imports_smbus2_when_hardware_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ASTRO_BRAIN_HARDWARE", "1")
    sentinel = object()
    fake_smbus2 = MagicMock()
    fake_smbus2.SMBus.return_value = sentinel
    monkeypatch.setitem(sys.modules, "smbus2", fake_smbus2)

    bus = open_bus(1)

    assert bus is sentinel
    fake_smbus2.SMBus.assert_called_once_with(1)


def test_write_byte_then_read_bytes_roundtrip_stub(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ASTRO_BRAIN_HARDWARE", raising=False)
    bus = open_bus()
    write_byte(bus, 0x1E, 0x28, 0x01)
    write_byte(bus, 0x1E, 0x29, 0x02)
    write_byte(bus, 0x1E, 0x2A, 0x03)
    assert read_bytes(bus, 0x1E, 0x28, 3) == b"\x01\x02\x03"


def test_read_bytes_returns_zero_for_unwritten_registers_stub(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ASTRO_BRAIN_HARDWARE", raising=False)
    bus = open_bus()
    assert read_bytes(bus, 0x53, 0x32, 3) == b"\x00\x00\x00"


def test_write_byte_masks_to_8_bits_stub(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ASTRO_BRAIN_HARDWARE", raising=False)
    bus = open_bus()
    write_byte(bus, 0x1E, 0x20, 0x1FF)
    assert read_bytes(bus, 0x1E, 0x20, 1) == b"\xff"


def test_read_bytes_delegates_to_smbus2_block_read() -> None:
    bus = MagicMock()
    bus.read_i2c_block_data.return_value = [0x10, 0x20, 0x30, 0x40, 0x50, 0x60]

    result = read_bytes(bus, 0x1E, 0x28, 6)

    assert result == bytes([0x10, 0x20, 0x30, 0x40, 0x50, 0x60])
    bus.read_i2c_block_data.assert_called_once_with(0x1E, 0x28, 6)


def test_write_byte_delegates_to_smbus2_write_byte_data() -> None:
    bus = MagicMock()

    write_byte(bus, 0x1E, 0x20, 0x70)

    bus.write_byte_data.assert_called_once_with(0x1E, 0x20, 0x70)
