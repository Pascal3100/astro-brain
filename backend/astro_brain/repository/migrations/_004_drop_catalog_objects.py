"""Retire la table `catalog_objects` : le catalogue vient désormais de
`reference.sqlite` (SP2). Forward-only."""
from __future__ import annotations

VERSION = 4

SQL = """
DROP TABLE IF EXISTS catalog_objects;
"""
