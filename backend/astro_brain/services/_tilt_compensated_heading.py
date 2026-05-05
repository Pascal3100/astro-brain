"""Tilt-compensated magnetic heading helper (LIS3MDL + ADXL mount).

Pure functions, zero I/O, zero state.

Sensor frame: +x forward, +y right, +z down. When level the accelerometer
reads (0, 0, +1g). Convention: +x = magnetic north → 0°, +y = east → 90°.
"""

import math


def _to_deg_360(rad: float) -> float:
    return (math.degrees(rad) + 360.0) % 360.0


def naive_heading(mag_corrected: tuple[float, float, float]) -> float:
    """Heading in degrees [0, 360) without tilt compensation.

    Used as a fallback when the ADXL mount is not yet calibrated.
    """
    mx, my, _ = mag_corrected
    return _to_deg_360(math.atan2(my, mx))


def tilt_compensated_heading(
    mag_corrected: tuple[float, float, float],
    accel_corrected: tuple[float, float, float],
) -> float:
    """Tilt-compensated magnetic heading in degrees [0, 360).

    Derives pitch/roll from the accelerometer and rotates the magnetic vector
    back to the horizontal plane before computing atan2(my', mx').
    """
    mx, my, mz = mag_corrected
    ax, ay, az = accel_corrected

    pitch = math.atan2(-ax, math.sqrt(ay * ay + az * az))
    roll = math.atan2(ay, az)

    cp, sp = math.cos(pitch), math.sin(pitch)
    cr, sr = math.cos(roll), math.sin(roll)

    mx_p = mx * cp + mz * sp
    my_p = mx * sr * sp + my * cr - mz * sr * cp

    return _to_deg_360(math.atan2(my_p, mx_p))
