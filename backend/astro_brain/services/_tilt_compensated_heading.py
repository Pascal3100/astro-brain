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

    Convention (Honeywell AN-203, NED frame): le repère sensor est obtenu
    par roll autour de +x puis pitch autour du nouveau +y, soit la rotation
    active ``R = R_y(pitch) @ R_x(roll)``. Le vecteur monde m_w est obtenu
    par ``R @ m_sensor`` ; on ne garde que les composantes horizontales.
    """
    mx, my, mz = mag_corrected
    ax, ay, az = accel_corrected

    pitch = math.atan2(-ax, math.sqrt(ay * ay + az * az))
    roll = math.atan2(ay, az)

    cp, sp = math.cos(pitch), math.sin(pitch)
    cr, sr = math.cos(roll), math.sin(roll)

    # m_world = R_y(pitch) @ R_x(roll) @ m_sensor → ligne x et ligne y :
    mx_h = cp * mx + sp * sr * my + sp * cr * mz
    my_h = cr * my - sr * mz

    return _to_deg_360(math.atan2(my_h, mx_h))
