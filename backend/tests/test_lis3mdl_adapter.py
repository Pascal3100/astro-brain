import asyncio
import time

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


async def test_i2c_io_does_not_block_the_event_loop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`start`/`read_raw`/`stop` must offload blocking I2C calls to a thread.

    A Pi 3 B+ is single-core: if `write_byte`/`read_bytes` ran directly on
    the event loop, a slow I2C transaction would freeze everything else
    (SSE, mount commands). This simulates a slow I2C bus (blocking
    `time.sleep`) and asserts a concurrent coroutine keeps making progress
    while the adapter talks to the bus — proof the blocking calls run in a
    worker thread, not on the loop.
    """
    block_duration = 0.05

    def slow_write_byte(bus: object, addr: int, reg: int, value: int) -> None:
        time.sleep(block_duration)

    def slow_read_bytes(bus: object, addr: int, reg: int, n: int) -> bytes:
        time.sleep(block_duration)
        return bytes(n)

    monkeypatch.setattr(
        "astro_brain.adapters.lis3mdl_adapter.write_byte", slow_write_byte
    )
    monkeypatch.setattr(
        "astro_brain.adapters.lis3mdl_adapter.read_bytes", slow_read_bytes
    )

    adapter = Lis3mdlAdapter(fake=make_fake_i2c())

    ticks = 0

    async def ticker() -> None:
        nonlocal ticks
        while True:
            await asyncio.sleep(0.01)
            ticks += 1

    ticker_task = asyncio.create_task(ticker())
    await adapter.start()  # 4 slow write_byte calls
    await adapter.read_raw()  # 1 slow read_bytes call
    await adapter.stop()  # 1 slow write_byte call
    ticker_task.cancel()

    # 6 blocking calls x 0.05 s = 0.3 s of I/O; if offloaded to a thread the
    # event loop stays free and the ticker fires well over 10 times at a
    # 0.01 s cadence. If the I/O ran on the loop instead, `ticks` stays 0.
    assert ticks >= 10
