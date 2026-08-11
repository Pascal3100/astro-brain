"""Retire la table `mount_limits`.

Résidu Courses ALT / limites monture jamais lues ni écrites (cf. revue
archi 2026-08). Forward-only.
"""
from __future__ import annotations

VERSION = 5

SQL = """
DROP TABLE IF EXISTS mount_limits;
"""
