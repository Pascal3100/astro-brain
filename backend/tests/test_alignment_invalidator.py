"""Tests de l'AlignmentInvalidator (clear is_aligned sur reco monture)."""
from __future__ import annotations

from astro_brain.alignment_invalidator import AlignmentInvalidator


class _Alignment:
    def __init__(self) -> None:
        self.invalidated = 0
        self._aligned = True

    @property
    def is_aligned(self) -> bool:
        return self._aligned

    def invalidate(self) -> None:
        self.invalidated += 1
        self._aligned = False


def test_invalidates_when_mount_leaves_ready():
    align = _Alignment()
    inv = AlignmentInvalidator(alignment=align)

    inv.on_mount_state("ready")  # armé
    inv.on_mount_state("disconnected")
    assert align.invalidated == 1

    inv.on_mount_state("ready")
    inv.on_mount_state("connecting")
    assert align.invalidated == 2


def test_no_invalidate_while_staying_ready():
    align = _Alignment()
    inv = AlignmentInvalidator(alignment=align)
    inv.on_mount_state("ready")
    inv.on_mount_state("moving")
    inv.on_mount_state("ready")
    assert align.invalidated == 0


def test_error_does_not_invalidate_but_disconnect_after_error_does():
    align = _Alignment()
    inv = AlignmentInvalidator(alignment=align)
    inv.on_mount_state("ready")
    inv.on_mount_state("error")  # échec de commande transitoire → pas d'invalidation
    assert align.invalidated == 0
    inv.on_mount_state("disconnected")  # vraie reconnexion → invalide
    assert align.invalidated == 1
