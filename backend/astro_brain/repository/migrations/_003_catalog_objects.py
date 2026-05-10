"""Catalogue d'objets célestes — table unifiée `catalog_objects`.

Discriminée par `kind` (star, messier, ngc, …). En tranche A, seed `kind='star'`
uniquement (~100-150 IAU named stars cap mag ≤ 3). Voir spec
docs/superpowers/specs/2026-05-10-catalog-backend-stars-design.md.
"""
from __future__ import annotations

VERSION = 3

SQL = """
CREATE TABLE IF NOT EXISTS catalog_objects (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    name TEXT NOT NULL,
    designation TEXT,
    ra_deg REAL NOT NULL,
    dec_deg REAL NOT NULL,
    mag REAL,
    constellation TEXT,
    object_type TEXT,
    angular_size_arcmin REAL,
    extras_json TEXT
);
CREATE INDEX IF NOT EXISTS idx_catalog_kind ON catalog_objects(kind);
CREATE INDEX IF NOT EXISTS idx_catalog_name ON catalog_objects(name);
CREATE INDEX IF NOT EXISTS idx_catalog_mag ON catalog_objects(mag);
"""
