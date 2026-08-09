"""Naive magnetic heading helper (LIS3MDL).

Pure functions, zero I/O, zero state.

Sensor frame: +x forward, +y right, +z down. Convention: +x = magnetic
north → 0°, +y = east → 90°. No tilt compensation is applied — the
accelerometer that used to provide pitch/roll for tilt compensation has
been removed; heading is derived directly from the (corrected) magnetometer
vector projected onto the sensor's horizontal plane.
"""

import math


def _to_deg_360(rad: float) -> float:
    return (math.degrees(rad) + 360.0) % 360.0


def naive_heading(mag_corrected: tuple[float, float, float]) -> float:
    """Heading in degrees [0, 360) without tilt compensation."""
    mx, my, _ = mag_corrected
    return _to_deg_360(math.atan2(my, mx))
