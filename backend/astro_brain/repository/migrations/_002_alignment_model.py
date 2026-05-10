"""Schéma alignment_model (modèle d'alignement 3 étoiles persisté)."""
from __future__ import annotations

VERSION = 2

SQL = """
CREATE TABLE IF NOT EXISTS alignment_model (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  recorded_stars TEXT NOT NULL,
  svd_matrix TEXT NOT NULL,
  rms_arcmin REAL NOT NULL,
  residuals TEXT NOT NULL,
  validated_at TEXT NOT NULL,
  gps_lat REAL,
  gps_lon REAL,
  quality TEXT NOT NULL DEFAULT 'good'
);
"""
