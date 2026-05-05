"""Initial schema: schema_version, calibration_sensor, mount_limits."""

from __future__ import annotations

VERSION = 1

SQL = """
CREATE TABLE IF NOT EXISTS schema_version (
  version INTEGER PRIMARY KEY,
  applied_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS calibration_sensor (
  sensor_id TEXT PRIMARY KEY,
  payload_json TEXT NOT NULL,
  calibrated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS mount_limits (
  axis TEXT PRIMARY KEY,
  min_deg REAL NOT NULL,
  max_deg REAL NOT NULL,
  set_at TEXT NOT NULL
);
"""
