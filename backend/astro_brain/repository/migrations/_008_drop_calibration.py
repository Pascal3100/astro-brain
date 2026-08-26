"""Retire la table `calibration_sensor`.

Le module DroTek est déposé (ADR 2026-08-26) : plus de compass LIS3MDL,
donc plus rien à calibrer ni à persister. Forward-only.
"""
from __future__ import annotations

VERSION = 8

SQL = """
DROP TABLE IF EXISTS calibration_sensor;
"""
