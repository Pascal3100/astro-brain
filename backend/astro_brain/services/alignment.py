"""AlignmentServiceImpl — orchestration du wizard 3 étoiles côté backend.

Une seule session en RAM à la fois. Le modèle final est persisté via le repo
(save asynchrone). Cette classe ne touche pas le mount directement pour les
slews — l'orchestration goto/jog reste portée par les routes existantes ;
on lit juste la position courante au moment du `record`.
"""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any
from uuid import uuid4

from astro_brain.models.alignment import (
    AlignmentModel,
    AlignmentSession,
    Star,
    StarRecord,
)
from astro_brain.services._alignment_solver import compute_alignment
from astro_brain.services.interfaces import ConflictError


class AlignmentServiceImpl:
    def __init__(
        self,
        *,
        select_candidates: Callable[[], list[Star]],
        mount: Any,
        sensors: Any,
        repo_save: Callable[..., Any],
        db: Any,
        now_utc: Callable[[], datetime],
    ) -> None:
        self._select = select_candidates
        self._mount = mount
        self._sensors = sensors
        self._repo_save = repo_save
        self._db = db
        self._now = now_utc
        self._session: AlignmentSession | None = None

    def session(self) -> AlignmentSession | None:
        return self._session

    async def start(self) -> AlignmentSession:
        candidates = self._select()
        self._session = AlignmentSession(
            session_id=uuid4().hex,
            candidates=list(candidates),
            recorded_stars=[],
            current_idx=0,
        )
        return self._session

    async def swap(self, idx: int, new_star: Star) -> AlignmentSession:
        sess = self._require_session()
        if idx < sess.current_idx:
            raise ConflictError("cannot swap a recorded star")
        if not (0 <= idx < len(sess.candidates)):
            raise ConflictError("idx out of range")
        sess.candidates[idx] = new_star
        return sess

    async def record(self, idx: int) -> AlignmentSession:
        sess = self._require_session()
        if idx != sess.current_idx:
            raise ConflictError(
                f"idx {idx} != current_idx {sess.current_idx}"
            )
        if idx >= len(sess.candidates):
            raise ConflictError("idx beyond candidates")

        # Lit la position courante de la monture
        mount_az, mount_alt = await self._mount.current_position()

        star = sess.candidates[idx]
        sky_az, sky_alt = self._sensors.sky_az_alt_for(star)
        sess.recorded_stars.append(
            StarRecord(
                star_id=star.id,
                sky_az=sky_az,
                sky_alt=sky_alt,
                mount_az=mount_az,
                mount_alt=mount_alt,
            )
        )
        # Pousse le sync vers le modèle d'alignement natif INDI/Celestron.
        # Après 3 syncs, le driver indi_celestron_aux a son modèle 3-étoiles
        # complet et tracking + GoTo passent par EQUATORIAL_EOD_COORD.
        await self._mount.sync_radec(star.ra_deg, star.dec_deg)
        sess.current_idx = idx + 1
        return sess

    async def restart_star(self, idx: int) -> AlignmentSession:
        sess = self._require_session()
        if not (0 <= idx <= len(sess.candidates) - 1):
            raise ConflictError("idx out of range")
        sess.recorded_stars = sess.recorded_stars[:idx]
        sess.current_idx = idx
        return sess

    async def finalize(self) -> AlignmentModel:
        sess = self._require_session()
        if len(sess.recorded_stars) < 3:
            raise ConflictError("need 3 recorded stars before finalize")

        model = compute_alignment(sess.recorded_stars)

        gps = self._sensors.gps_fix() if self._sensors else None
        model = model.model_copy(
            update={
                "validated_at_utc": self._now(),
                "gps_lat": gps[0] if gps else None,
                "gps_lon": gps[1] if gps else None,
            }
        )
        await self._repo_save(self._db, model)
        self._session = None
        return model

    async def cancel(self) -> None:
        self._session = None

    def _require_session(self) -> AlignmentSession:
        if self._session is None:
            raise ConflictError("no active alignment session")
        return self._session
