"""CalibrationService — state machine + sampling loop for ADXL345 & LIS3MDL.

State machine per session: idle → sampling → computing → done | aborted | error.

A single session is active at a time across all sensors. Clients may open
multiple SSE streams (via ``progress``) simultaneously; disconnecting from the
stream does NOT terminate the session — explicit ``abort`` is required.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from typing import Literal
from uuid import uuid4

import aiosqlite

from astro_brain.adapters.adxl345_adapter import Adxl345Adapter
from astro_brain.adapters.lis3mdl_adapter import Lis3mdlAdapter
from astro_brain.models.calibration import (
    Adxl345Offsets,
    CalibrationProgress,
    CalibrationStatus,
    Lis3mdlOffsets,
)
from astro_brain.repository import calibration_repo
from astro_brain.repository.calibration_repo import SENSOR_IDS
from astro_brain.services._bias_fit import compute_bias_and_sigma
from astro_brain.services._ellipsoid_fit import compute_ellipsoid_offsets, coverage_pct
from astro_brain.services.interfaces import ConflictError

_log = logging.getLogger(__name__)

_SessionState = Literal["idle", "sampling", "computing", "done", "aborted", "error"]

_ADXL_SENSORS = frozenset({"adxl345_mount", "adxl345_tube"})

# Convention v0.2 : la position « tube horizontal » est définie par l'instant
# du clic VALIDER côté client, donc le payload sérialise toujours 0°.
_TUBE_ZERO_ALT_DEG = 0.0


class CalibrationServiceImpl:
    """Concrete implementation of the :class:`CalibrationService` protocol.

    Constructor arguments let tests override timing constants so samples
    accumulate in milliseconds rather than seconds.
    """

    def __init__(
        self,
        *,
        db: aiosqlite.Connection,
        adxl_mount: Adxl345Adapter,
        adxl_tube: Adxl345Adapter,
        lis3mdl: Lis3mdlAdapter,
        sample_period_s: float = 0.02,
        progress_period_s: float = 0.2,
        adxl_min_samples: int = 100,
        adxl_sigma_threshold: float = 0.05,
        lis3mdl_min_samples: int = 500,
        lis3mdl_coverage_threshold: float = 80.0,
    ) -> None:
        self._db = db
        self._adapters: dict[str, Adxl345Adapter | Lis3mdlAdapter] = {
            "adxl345_mount": adxl_mount,
            "adxl345_tube": adxl_tube,
            "lis3mdl": lis3mdl,
        }
        self._sample_period_s = sample_period_s
        self._progress_period_s = progress_period_s
        self._adxl_min_samples = adxl_min_samples
        self._adxl_sigma_threshold = adxl_sigma_threshold
        self._lis3mdl_min_samples = lis3mdl_min_samples
        self._lis3mdl_coverage_threshold = lis3mdl_coverage_threshold

        self._lock = asyncio.Lock()
        self._current_session: tuple[str, str] | None = None  # (session_id, sensor_id)

        # Per-session mutable state — only valid while _current_session is not None.
        self._samples: list[tuple[float, float, float]] = []
        self._state: _SessionState = "idle"
        self._hint: str | None = None
        self._sigma: float = 0.0
        self._coverage: float = 0.0
        self._residual: float | None = None
        self._sampling_task: asyncio.Task[None] | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def start(self, sensor_id: str) -> str:
        """Begin a calibration session for *sensor_id*.

        Returns:
            Opaque session id string.

        Raises:
            ValueError: Unknown *sensor_id*.
            ConflictError: Another session is already active.
        """
        if sensor_id not in SENSOR_IDS:
            raise ValueError(f"unknown sensor_id: {sensor_id!r}")

        async with self._lock:
            if self._current_session is not None:
                sid, existing = self._current_session
                raise ConflictError(
                    f"session {sid!r} active on {existing!r}"
                )

            session_id = uuid4().hex
            self._current_session = (session_id, sensor_id)

            # Initialise per-session state.
            self._samples = []
            self._sigma = 0.0
            self._coverage = 0.0
            self._residual = None
            self._state = "sampling"
            if sensor_id in _ADXL_SENSORS:
                self._hint = "Maintenir immobile"
            else:
                self._hint = "Tournez le module dans toutes les directions"

            adapter = self._adapters[sensor_id]
            # adapter.start() reste sous le lock : sinon abort()/start() peuvent
            # se croiser et appeler stop() sur un adapter pas encore démarré.
            try:
                await adapter.start()
            except Exception:
                self._current_session = None
                self._state = "idle"
                raise

            self._sampling_task = asyncio.create_task(
                self._sample_loop(sensor_id, adapter),
                name=f"calibration-{session_id[:8]}",
            )

        _log.info("Calibration session %s started for %s", session_id, sensor_id)
        return session_id

    async def progress(self, session_id: str) -> AsyncIterator[CalibrationProgress]:
        """Async generator that yields :class:`CalibrationProgress` snapshots.

        Yields every *progress_period_s* until the session ends or the
        session_id no longer matches (e.g. after finalize/abort).

        Raises:
            ValueError: If *session_id* does not match the active session.
        """
        if (
            self._current_session is None
            or self._current_session[0] != session_id
        ):
            raise ValueError(f"session {session_id!r} is not active")

        while (
            self._current_session is not None
            and self._current_session[0] == session_id
        ):
            # Snapshot atomique : on capture tous les champs dans des
            # variables locales avant de construire le modèle pour éviter
            # qu'un _clear_session() concurrent ne change l'état entre la
            # lecture de samples et celle de state/hint.
            state = self._state
            samples_n = len(self._samples)
            coverage = self._coverage
            sigma = self._sigma
            hint = self._hint
            residual = self._residual
            yield CalibrationProgress(
                state=state,
                samples_n=samples_n,
                coverage_pct=coverage,
                sigma=sigma,
                hint=hint,
                residual=residual,
            )
            await asyncio.sleep(self._progress_period_s)

    async def finalize(self, session_id: str) -> CalibrationStatus:
        """Stop sampling, run math, persist to DB, and return the result.

        Raises:
            ValueError: Session mismatch, insufficient samples, sigma too
                        high (ADXL), or coverage too low (LIS3MDL).
        """
        if (
            self._current_session is None
            or self._current_session[0] != session_id
        ):
            raise ValueError(f"session {session_id!r} is not active")

        _, sensor_id = self._current_session
        adapter = self._adapters[sensor_id]

        await self._stop_sampling()

        self._state = "computing"
        samples = list(self._samples)  # snapshot

        try:
            payload: Adxl345Offsets | Lis3mdlOffsets
            if sensor_id in _ADXL_SENSORS:
                payload = self._compute_adxl(sensor_id, samples)
            else:
                payload = self._compute_lis3mdl(samples)

            await calibration_repo.upsert_offsets(self._db, sensor_id, payload)
            status = await calibration_repo.get_offsets(self._db, sensor_id)
        finally:
            await self._clear_session(adapter)

        self._state = "done"
        _log.info("Calibration session %s finalized for %s", session_id, sensor_id)
        return status

    async def abort(self, session_id: str) -> None:
        """Cancel the active session without writing to the DB.

        Silently returns if there is no active session.  Raises
        ``ValueError`` only if a *different* session_id is given while
        another session is active, so callers can detect programming errors.
        """
        if self._current_session is None:
            return
        if self._current_session[0] != session_id:
            raise ValueError(
                f"session {session_id!r} is not active "
                f"(active: {self._current_session[0]!r})"
            )

        _, sensor_id = self._current_session
        adapter = self._adapters[sensor_id]
        await self._clear_session(adapter)
        self._state = "aborted"
        _log.info("Calibration session %s aborted", session_id)

    async def current_session(self) -> tuple[str, str] | None:
        """Return the active ``(session_id, sensor_id)`` pair, or ``None``."""
        return self._current_session

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _sample_loop(
        self, sensor_id: str, adapter: Adxl345Adapter | Lis3mdlAdapter
    ) -> None:
        """Background task: read one sample per tick, update hint/stats."""
        is_adxl = sensor_id in _ADXL_SENSORS
        # Resolve the read callable once to avoid branching in the hot loop.
        read_fn = getattr(adapter, "read_raw_g" if is_adxl else "read_raw")
        while (
            self._current_session is not None
            and self._state == "sampling"
        ):
            try:
                sample: tuple[float, float, float] = await read_fn()
            except Exception as exc:
                _log.exception("Adapter read error during calibration: %s", exc)
                self._state = "error"
                self._hint = str(exc)
                break

            self._samples.append(sample)
            n = len(self._samples)

            if is_adxl:
                self._update_adxl_hint(n)
            else:
                # coverage_pct rebuild un set sur l'ensemble des samples ;
                # tickrate 25 garde ça tolérable (≤ ~20 ms à 500 samples).
                if n % 25 == 0 and n > 0:
                    self._coverage = coverage_pct(self._samples)
                self._update_lis3mdl_hint()

            await asyncio.sleep(self._sample_period_s)

    def _update_adxl_hint(self, n: int) -> None:
        """Recompute sigma every 10 samples (once >= 5) and update hint."""
        if n >= 5 and n % 10 == 0:
            with contextlib.suppress(ValueError):
                _, self._sigma = compute_bias_and_sigma(self._samples)

        if n < 20:
            self._hint = "Maintenir immobile"
        elif n < self._adxl_min_samples and self._sigma >= self._adxl_sigma_threshold:
            self._hint = "Réduire les vibrations"
        elif self._sigma < self._adxl_sigma_threshold:
            self._hint = "Prêt à valider"

    def _update_lis3mdl_hint(self) -> None:
        """Update hint from current coverage percentage."""
        if self._coverage < 30:
            self._hint = "Tournez le module dans toutes les directions"
        elif self._coverage < 80:
            self._hint = "Continuez les rotations"
        else:
            self._hint = "Couverture suffisante, validez"

    def _compute_adxl(
        self, sensor_id: str, samples: list[tuple[float, float, float]]
    ) -> Adxl345Offsets:
        """Run ADXL math; raise ValueError on bad samples."""
        if len(samples) < self._adxl_min_samples:
            raise ValueError(
                f"insufficient samples: {len(samples)} < {self._adxl_min_samples}"
            )
        bias, sigma = compute_bias_and_sigma(samples)
        if sigma >= self._adxl_sigma_threshold:
            raise ValueError(f"sigma too high: {sigma:.4f}")
        zero_alt_deg: float | None = (
            _TUBE_ZERO_ALT_DEG if sensor_id == "adxl345_tube" else None
        )
        return Adxl345Offsets(bias=bias, sigma=sigma, zero_alt_deg=zero_alt_deg)

    def _compute_lis3mdl(
        self, samples: list[tuple[float, float, float]]
    ) -> Lis3mdlOffsets:
        """Run ellipsoid fit; raise ValueError on bad samples or coverage."""
        if len(samples) < self._lis3mdl_min_samples:
            raise ValueError(
                f"insufficient samples: {len(samples)} < {self._lis3mdl_min_samples}"
            )
        cov = coverage_pct(samples)
        if cov < self._lis3mdl_coverage_threshold:
            raise ValueError(
                f"coverage too low: {cov:.1f}% < {self._lis3mdl_coverage_threshold}%"
            )
        offsets, scale_matrix, residual = compute_ellipsoid_offsets(samples)
        return Lis3mdlOffsets(
            offsets=offsets,
            scale_matrix=scale_matrix,
            coverage_pct=cov,
            residual=residual,
        )

    async def _stop_sampling(self) -> None:
        """Cancel the sampling task and wait for it to finish."""
        if self._sampling_task is not None and not self._sampling_task.done():
            self._sampling_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await self._sampling_task
            self._sampling_task = None

    async def _clear_session(
        self, adapter: Adxl345Adapter | Lis3mdlAdapter
    ) -> None:
        """Cancel sampling, stop adapter, reset session state."""
        await self._stop_sampling()
        try:
            await adapter.stop()
        except Exception as exc:
            _log.warning("Adapter stop error during session clear: %s", exc)
        self._current_session = None
        self._samples = []
