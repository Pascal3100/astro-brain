"""Crée la table `observing_site` — position d'observation persistée.

Remplace la chaîne « fix GPS Pi → position client » par une source unique :
le site d'observation, écrit sur action explicite de l'utilisateur (carte
Setup, ou rattrapage 409 du wizard depuis le GPS du téléphone). Posée en
amont du retrait du module DroTek (cf. ADR 2026-08-26), pour que la position
existe avant que le GPS disparaisse.

Singleton matérialisé dans le schéma (`CHECK (id = 1)`) plutôt que dans le
code appelant. Forward-only.
"""
from __future__ import annotations

VERSION = 7

SQL = """
CREATE TABLE IF NOT EXISTS observing_site (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  lat REAL NOT NULL,
  lon REAL NOT NULL,
  set_at TEXT NOT NULL
);
"""
