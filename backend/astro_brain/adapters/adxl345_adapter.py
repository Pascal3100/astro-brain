"""ADXL345 accelerometer I2C adapter — raw readings in g (no calibration).

TODO confirmer la séquence init (POWER_CTL/DATA_FORMAT/BW_RATE) avant smoke test capteur.
"""

import struct
from typing import Any

from astro_brain.adapters._i2c_helpers import open_bus, read_bytes, write_byte

ADXL345_TUBE_ADDR = 0x53   # SDO/ALT à GND
ADXL345_MOUNT_ADDR = 0x1D  # SDO/ALT à VDD

_POWER_CTL = 0x2D
_DATA_FORMAT = 0x31
_BW_RATE = 0x2C
_DATAX0 = 0x32
_SCALE_G = 0.004  # 4 mg/LSB en full-resolution ±16 g


class Adxl345Adapter:
    def __init__(
        self,
        *,
        bus_number: int = 1,
        addr: int,
        fake: Any | None = None,
    ) -> None:
        self._bus_number = bus_number
        self._addr = addr
        self._fake = fake
        self._bus: Any | None = None

    async def start(self) -> None:
        self._bus = self._fake if self._fake is not None else open_bus(self._bus_number)
        write_byte(self._bus, self._addr, _BW_RATE, 0x0A)       # 100 Hz output rate
        write_byte(self._bus, self._addr, _DATA_FORMAT, 0x0B)   # full-res, ±16 g
        write_byte(self._bus, self._addr, _POWER_CTL, 0x08)     # measure mode

    async def stop(self) -> None:
        if self._bus is not None:
            write_byte(self._bus, self._addr, _POWER_CTL, 0x00)  # standby

    async def read_raw_g(self) -> tuple[float, float, float]:
        assert self._bus is not None, "start() must be called before read_raw_g()"
        raw = read_bytes(self._bus, self._addr, _DATAX0, 6)
        x, y, z = struct.unpack("<hhh", raw)
        return (x * _SCALE_G, y * _SCALE_G, z * _SCALE_G)


def mount_adapter(*, fake: Any | None = None) -> Adxl345Adapter:
    """Factory pour l'accéléromètre monture (addr 0x1D, SDO/ALT à VDD)."""
    return Adxl345Adapter(addr=ADXL345_MOUNT_ADDR, fake=fake)


def tube_adapter(*, fake: Any | None = None) -> Adxl345Adapter:
    """Factory pour l'accéléromètre tube (addr 0x53, SDO/ALT à GND)."""
    return Adxl345Adapter(addr=ADXL345_TUBE_ADDR, fake=fake)
