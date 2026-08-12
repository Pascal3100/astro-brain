"""LIS3MDL magnetometer I2C adapter — raw readings (no calibration).

TODO confirmer la séquence init (CTRL_REG1..4 + auto-increment OUT_X_L) avant smoke test capteur #2.

Un capteur absent ou non alimenté fait lever ``OSError`` à smbus2 (``[Errno 5]
Input/output error``). C'est un état *nominal* — le bench débranché — donc il
est traduit en :class:`SensorUnavailableError`, que les routes savent rendre en
``503``. Sans cette traduction, l'``OSError`` remontait en ``500`` (et, sur la
route SSE, en corps chunké tronqué côté client).
"""

import asyncio
import struct
from typing import Any

from astro_brain.adapters._i2c_helpers import open_bus, read_bytes, write_byte
from astro_brain.services.interfaces import SensorUnavailableError

LIS3MDL_I2C_ADDR = 0x1E

_CTRL_REG1 = 0x20
_CTRL_REG2 = 0x21
_CTRL_REG3 = 0x22
_CTRL_REG4 = 0x23
_OUT_X_L = 0x28
_AUTO_INC = 0x80
_LSB_PER_GAUSS = 6842.0
_GAUSS_TO_UT = 100.0  # 1 gauss = 100 µT


class Lis3mdlAdapter:
    def __init__(
        self,
        *,
        bus_number: int = 1,
        addr: int = LIS3MDL_I2C_ADDR,
        fake: Any | None = None,
    ) -> None:
        self._bus_number = bus_number
        self._addr = addr
        self._fake = fake
        self._bus: Any | None = None

    async def _i2c(self, fn: Any, *args: Any) -> Any:
        """Run one I2C access off the event loop, translating an absent chip."""
        try:
            return await asyncio.to_thread(fn, *args)
        except OSError as exc:
            raise SensorUnavailableError(
                f"LIS3MDL muet à 0x{self._addr:02X} sur i2c-{self._bus_number} ({exc})"
            ) from exc

    async def start(self) -> None:
        self._bus = self._fake if self._fake is not None else open_bus(self._bus_number)
        await self._i2c(write_byte, self._bus, self._addr, _CTRL_REG1, 0x70)
        await self._i2c(write_byte, self._bus, self._addr, _CTRL_REG2, 0x00)
        await self._i2c(write_byte, self._bus, self._addr, _CTRL_REG3, 0x00)
        await self._i2c(write_byte, self._bus, self._addr, _CTRL_REG4, 0x0C)

    async def stop(self) -> None:
        if self._bus is not None:
            await self._i2c(write_byte, self._bus, self._addr, _CTRL_REG3, 0x03)

    async def read_raw(self) -> tuple[float, float, float]:
        if self._bus is None:
            raise RuntimeError("start() must be called before read_raw()")
        raw = await self._i2c(
            read_bytes, self._bus, self._addr, _OUT_X_L | _AUTO_INC, 6
        )
        x, y, z = struct.unpack("<hhh", raw)
        scale = _GAUSS_TO_UT / _LSB_PER_GAUSS
        return (x * scale, y * scale, z * scale)
