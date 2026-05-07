import pytest

from astro_brain.adapters.lis3mdl_adapter import LIS3MDL_I2C_ADDR, Lis3mdlAdapter
from tests.fakes.fake_i2c import make_fake_i2c, preload_int16_le


async def test_start_writes_init_sequence() -> None:
    bus = make_fake_i2c()
    adapter = Lis3mdlAdapter(fake=bus)
    await adapter.start()
    assert bus.registers[(LIS3MDL_I2C_ADDR, 0x20)] == 0x70
    assert bus.registers[(LIS3MDL_I2C_ADDR, 0x21)] == 0x00
    assert bus.registers[(LIS3MDL_I2C_ADDR, 0x22)] == 0x00
    assert bus.registers[(LIS3MDL_I2C_ADDR, 0x23)] == 0x0C


async def test_read_raw_parses_signed_int16_le() -> None:
    bus = make_fake_i2c()
    # Preload at 0x28 | 0x80 = 0xA8 to mirror the read path (auto-increment flag OR'd on).
    preload_int16_le(bus, LIS3MDL_I2C_ADDR, 0x28 | 0x80, [1000, -2000, 3000])
    adapter = Lis3mdlAdapter(fake=bus)
    await adapter.start()
    x_ut, y_ut, z_ut = await adapter.read_raw()
    scale = 100.0 / 6842.0
    assert x_ut == pytest.approx(1000 * scale)
    assert y_ut == pytest.approx(-2000 * scale)
    assert z_ut == pytest.approx(3000 * scale)


async def test_stop_powers_down() -> None:
    bus = make_fake_i2c()
    adapter = Lis3mdlAdapter(fake=bus)
    await adapter.start()
    await adapter.stop()
    assert bus.registers[(LIS3MDL_I2C_ADDR, 0x22)] == 0x03
