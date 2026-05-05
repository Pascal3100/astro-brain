import pytest

from astro_brain.adapters.adxl345_adapter import (
    ADXL345_MOUNT_ADDR,
    ADXL345_TUBE_ADDR,
    Adxl345Adapter,
    mount_adapter,
    tube_adapter,
)
from tests.fakes.fake_i2c import make_fake_i2c, preload_int16_le


async def test_start_writes_init_sequence() -> None:
    bus = make_fake_i2c()
    adapter = Adxl345Adapter(addr=ADXL345_MOUNT_ADDR, fake=bus)
    await adapter.start()
    assert bus.registers[(ADXL345_MOUNT_ADDR, 0x2D)] == 0x08  # POWER_CTL — measure mode
    assert bus.registers[(ADXL345_MOUNT_ADDR, 0x31)] == 0x0B  # DATA_FORMAT — full-res ±16 g
    assert bus.registers[(ADXL345_MOUNT_ADDR, 0x2C)] == 0x0A  # BW_RATE — 100 Hz


async def test_read_raw_g_parses_signed_int16_le() -> None:
    bus = make_fake_i2c()
    # ADXL345 streams 6 bytes natively from 0x32 — no auto-increment mask needed.
    preload_int16_le(bus, ADXL345_MOUNT_ADDR, 0x32, [1000, -2000, 500])
    adapter = Adxl345Adapter(addr=ADXL345_MOUNT_ADDR, fake=bus)
    await adapter.start()
    x_g, y_g, z_g = await adapter.read_raw_g()
    assert x_g == pytest.approx(1000 * 0.004)
    assert y_g == pytest.approx(-2000 * 0.004)
    assert z_g == pytest.approx(500 * 0.004)


async def test_stop_powers_down() -> None:
    bus = make_fake_i2c()
    adapter = Adxl345Adapter(addr=ADXL345_MOUNT_ADDR, fake=bus)
    await adapter.start()
    await adapter.stop()
    assert bus.registers[(ADXL345_MOUNT_ADDR, 0x2D)] == 0x00  # POWER_CTL — standby


async def test_factories_use_correct_addresses() -> None:
    bus_mount = make_fake_i2c()
    bus_tube = make_fake_i2c()
    adap_mount = mount_adapter(fake=bus_mount)
    adap_tube = tube_adapter(fake=bus_tube)
    await adap_mount.start()
    await adap_tube.start()
    # Writes must land on the expected addresses — validates factory mapping is not swapped.
    assert (ADXL345_MOUNT_ADDR, 0x2D) in bus_mount.registers
    assert (ADXL345_TUBE_ADDR, 0x2D) in bus_tube.registers
    assert (ADXL345_TUBE_ADDR, 0x2D) not in bus_mount.registers
    assert (ADXL345_MOUNT_ADDR, 0x2D) not in bus_tube.registers
