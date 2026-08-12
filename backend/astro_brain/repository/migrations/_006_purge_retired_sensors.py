"""Purge les calibrations de capteurs retirés.

Les 2× ADXL345 ont été retirés le 2026-07-17 (cf. ADR) mais leur ligne de
calibration survivait dans `calibration_sensor` — jamais relue, puisque
`calibration_repo.SENSOR_IDS` ne contient plus que `lis3mdl` et rejette
tout autre identifiant. Constatée sur le Pi lors du déploiement 2026-08-12.

Forward-only, et figée : elle ne s'exécute qu'une fois, donc un capteur
ajouté plus tard à `SENSOR_IDS` ne risque pas d'être balayé.
"""
from __future__ import annotations

VERSION = 6

SQL = """
DELETE FROM calibration_sensor WHERE sensor_id NOT IN ('lis3mdl');
"""
