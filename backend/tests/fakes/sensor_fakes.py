"""Fakes partagés pour ADXL345 / LIS3MDL — utilisés par les tests calibration
service, calibration routes, et sensors routes.

Chaque fake :

- Expose la signature attendue par l'adapter (``read_raw_g`` ou ``read_raw``).
- Cycle sur une séquence pré-enregistrée de samples (le dernier sample est
  retourné indéfiniment quand l'index dépasse la liste).
- Expose à la fois des compteurs ``start_calls``/``stop_calls`` *et* des
  booléens ``started``/``stopped`` pour s'adapter à tous les call sites.
"""

from __future__ import annotations


class FakeAdxl345:
    """Fake programmable du driver ADXL345 (3-axis, en g)."""

    def __init__(self, samples: list[tuple[float, float, float]]) -> None:
        self._samples = list(samples)
        self._idx = 0
        self.start_calls = 0
        self.stop_calls = 0

    @property
    def started(self) -> bool:
        return self.start_calls > 0

    @property
    def stopped(self) -> bool:
        return self.stop_calls > 0

    async def start(self) -> None:
        self.start_calls += 1

    async def stop(self) -> None:
        self.stop_calls += 1

    async def read_raw_g(self) -> tuple[float, float, float]:
        if not self._samples:
            raise RuntimeError("FakeAdxl345 has no samples")
        sample = self._samples[min(self._idx, len(self._samples) - 1)]
        self._idx += 1
        return sample


class FakeLis3mdl:
    """Fake programmable du driver LIS3MDL (3-axis, en µT)."""

    def __init__(self, samples: list[tuple[float, float, float]]) -> None:
        self._samples = list(samples)
        self._idx = 0
        self.start_calls = 0
        self.stop_calls = 0

    @property
    def started(self) -> bool:
        return self.start_calls > 0

    @property
    def stopped(self) -> bool:
        return self.stop_calls > 0

    async def start(self) -> None:
        self.start_calls += 1

    async def stop(self) -> None:
        self.stop_calls += 1

    async def read_raw(self) -> tuple[float, float, float]:
        if not self._samples:
            raise RuntimeError("FakeLis3mdl has no samples")
        sample = self._samples[min(self._idx, len(self._samples) - 1)]
        self._idx += 1
        return sample
