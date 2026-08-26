"""Réhydratation de l'alignement au boot, depuis le site persisté.

Avant le retrait du DroTek, la réhydratation attendait un premier fix GPS 3D
sur le bus (la garde ΔGPS de ``alignment_repo.load`` exige une position
courante). Le site étant maintenant lu dans SQLite avant même que le service
d'alignement soit construit, la garde est évaluable dès le boot : la
réhydratation est devenue un simple ``await`` dans le lifespan.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi import FastAPI

from astro_brain.app import build_app
from astro_brain.models.alignment import AlignmentModel, StarRecord
from astro_brain.repository import alignment_repo, site_repo


def _model(lat: float, lon: float, *, age: timedelta = timedelta()) -> AlignmentModel:
    rec = StarRecord(star_id="a", sky_az=0, sky_alt=0, mount_az=0, mount_alt=0)
    return AlignmentModel(
        recorded_stars=[rec, rec, rec],
        svd_matrix=[[1, 0, 0], [0, 1, 0], [0, 0, 1]],
        rms_arcmin=4.2,
        residuals={"a": 4.2},
        validated_at_utc=datetime.now(UTC) - age,
        gps_lat=lat,
        gps_lon=lon,
    )


def _app(db_path: Path) -> FastAPI:
    return build_app(use_hardware=False, db_path_override=db_path, sync_on_boot=False)


async def _seed(db_path: Path, model: AlignmentModel, site: tuple[float, float]) -> None:
    app = _app(db_path)
    async with app.router.lifespan_context(app):
        await site_repo.set_site(app.state.db, *site)
        await alignment_repo.save(app.state.db, model)


async def test_boot_restores_alignment_when_site_unchanged(tmp_path: Path) -> None:
    db_path = tmp_path / "state.db"
    await _seed(db_path, _model(43.6, 1.44), site=(43.6, 1.44))

    app = _app(db_path)
    async with app.router.lifespan_context(app):
        assert app.state.alignment.is_aligned is True
        aligned = app.state.bus.get_full_state().subsystems["alignment"]
        assert aligned.details["is_aligned"] is True


async def test_boot_does_not_restore_when_site_moved(tmp_path: Path) -> None:
    """Site déplacé de ~1 km → au-delà des 20 m tolérés, pas de restauration."""
    db_path = tmp_path / "state.db"
    await _seed(db_path, _model(43.6, 1.44), site=(43.61, 1.44))

    app = _app(db_path)
    async with app.router.lifespan_context(app):
        assert app.state.alignment.is_aligned is False
        aligned = app.state.bus.get_full_state().subsystems["alignment"]
        assert aligned.details["is_aligned"] is False


async def test_boot_does_not_restore_without_site(tmp_path: Path) -> None:
    """Sans site réglé, ``load`` n'a rien à comparer : pas de restauration."""
    db_path = tmp_path / "state.db"
    app = _app(db_path)
    async with app.router.lifespan_context(app):
        await alignment_repo.save(app.state.db, _model(43.6, 1.44))

    app2 = _app(db_path)
    async with app2.router.lifespan_context(app2):
        assert app2.state.alignment.is_aligned is False


async def test_boot_does_not_restore_stale_model(tmp_path: Path) -> None:
    """Δt > 12 h → le modèle est périmé, quel que soit le site."""
    db_path = tmp_path / "state.db"
    await _seed(
        db_path, _model(43.6, 1.44, age=timedelta(hours=13)), site=(43.6, 1.44)
    )

    app = _app(db_path)
    async with app.router.lifespan_context(app):
        assert app.state.alignment.is_aligned is False
