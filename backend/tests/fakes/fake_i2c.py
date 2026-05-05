"""In-memory I2C bus fake for tests."""

from astro_brain.adapters._i2c_helpers import _StubBus


def make_fake_i2c() -> _StubBus:
    """Return a fresh in-memory I2C bus stub usable by adapters via the `fake=` kwarg."""
    return _StubBus()


def preload_int16_le(bus: _StubBus, addr: int, reg: int, values: list[int]) -> None:
    """Preload N int16 little-endian values starting at `reg`. Used to seed device registers."""
    for i, val in enumerate(values):
        if val < 0:
            val += 1 << 16
        bus.registers[(addr, reg + 2 * i)] = val & 0xFF
        bus.registers[(addr, reg + 2 * i + 1)] = (val >> 8) & 0xFF
