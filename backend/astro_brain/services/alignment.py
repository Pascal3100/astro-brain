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
        tracking: Any,
        sensors: Any,
        repo_save: Callable[..., Any],
        repo_load: Callable[..., Any],
        repo_clear: Callable[..., Any] | None = None,
        db: Any,
        now_utc: Callable[[], datetime],
    ) -> None:
        self._select = select_candidates
        self._mount = mount
        self._tracking = tracking
        self._sensors = sensors
        self._repo_save = repo_save
        self._repo_load = repo_load
        self._repo_clear = repo_clear
        self._db = db
        self._now = now_utc
        self._session: AlignmentSession | None = None
        self._is_aligned: bool = False

    def session(self) -> AlignmentSession | None:
        return self._session

    @property
    def is_aligned(self) -> bool:
        return self._is_aligned

    def invalidate(self) -> None:
        """Perte du modèle natif (reconnexion monture / redémarrage driver)."""
        self._is_aligned = False

    async def rehydrate(self) -> bool:
        """Restaure ``is_aligned`` depuis le modèle SQLite persisté s'il est
        encore valide.

        Source de vérité = ``alignment_repo.load`` avec ses garde-fous de
        fraîcheur (Δt > 12 h / déplacement du site > 20 m). Best-effort et
        idempotent : ne met ``is_aligned`` qu'à ``True``. L'invalidation reste
        le rôle de :class:`AlignmentInvalidator`. Sans site d'observation
        réglé, ``load()`` renvoie ``None`` → pas de restauration. Ne touche
        jamais une session wizard en cours.

        Renvoie ``True`` si un modèle valide a été restauré.
        """
        if self._session is not None:
            return False
        current_gps = self._sensors.position() if self._sensors else None
        model = await self._repo_load(
            self._db, now_utc=self._now(), current_gps=current_gps
        )
        if model is None:
            return False
        self._is_aligned = True
        return True

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
        raw = self._sensors.sky_az_alt_for(star)
        if raw is None:
            raise ConflictError(
                "position indisponible — impossible d'enregistrer sans observateur"
            )
        sky_az, sky_alt = raw
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

        # Dès la PREMIÈRE étoile validée, la monture sait où elle pointe :
        # on arme le suivi, comme la raquette Celestron le fait à la
        # validation de son alignement (sniff du bus AUX, journal S57 — elle
        # envoie MC_SET_POS_GUIDERATE non nul juste après avoir écrit le
        # modèle dans les contrôleurs moteur, et jamais avant).
        #
        # Armement EXPLICITE et à chaque étoile, pas seulement à la première :
        # le driver ne réengage le suivi qu'en fin de slew (isTrackingRequested()
        # dans ReadScopeStatus()), or un sync n'est pas un slew — s'en remettre
        # à cet effet de bord laisserait la monture figée entre deux étoiles.
        # Rejouer l'armement est idempotent : l'adaptateur filtre les échos.
        await self._tracking.set_tracking(True)

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

        # Clés `gps_*` : noms de colonnes historiques, la valeur est le site.
        site = self._sensors.position() if self._sensors else None
        model = model.model_copy(
            update={
                "validated_at_utc": self._now(),
                "gps_lat": site[0] if site else None,
                "gps_lon": site[1] if site else None,
            }
        )
        await self._repo_save(self._db, model)
        self._session = None
        self._is_aligned = True
        return model

    async def cancel(self) -> None:
        """Annule la session ET révoque l'alignement, y compris persisté.

        Annuler exprime « je ne suis plus aligné » : sans l'effacement du
        modèle SQLite, ``rehydrate()`` restaurerait ``is_aligned`` au boot
        suivant — c'est ce qui a laissé un modèle poubelle actif après les
        records erronés du test terrain S58.
        """
        self._session = None
        self._is_aligned = False
        if self._repo_clear is not None:
            await self._repo_clear(self._db)

    def _require_session(self) -> AlignmentSession:
        if self._session is None:
            raise ConflictError("no active alignment session")
        return self._session
