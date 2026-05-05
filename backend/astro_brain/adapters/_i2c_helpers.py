"""I2C bus helpers with lazy smbus2 import and in-memory stub for non-hardware mode."""

import os
from typing import Any


class _StubBus:
    def __init__(self) -> None:
        self.registers: dict[tuple[int, int], int] = {}


def open_bus(bus_number: int = 1) -> Any:
    if os.environ.get("ASTRO_BRAIN_HARDWARE") != "1":
        return _StubBus()
    import smbus2

    return smbus2.SMBus(bus_number)


def read_bytes(bus: Any, addr: int, reg: int, n: int) -> bytes:
    if isinstance(bus, _StubBus):
        return bytes(bus.registers.get((addr, reg + i), 0) for i in range(n))
    return bytes(bus.read_i2c_block_data(addr, reg, n))


def write_byte(bus: Any, addr: int, reg: int, value: int) -> None:
    if isinstance(bus, _StubBus):
        bus.registers[(addr, reg)] = value & 0xFF
        return
    bus.write_byte_data(addr, reg, value)
