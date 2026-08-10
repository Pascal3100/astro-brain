from __future__ import annotations

from pathlib import Path

from astro_brain.repository.reference_db import ReferenceDb
from tests.reference_fixtures import build_reference_v2


async def test_fixture_builds_supported_v2(tmp_path: Path) -> None:
    p = tmp_path / "reference.sqlite"
    build_reference_v2(p)
    ref = ReferenceDb(p)
    await ref.open()
    assert ref.ready is True
    meta = await ref.meta()
    assert meta is not None and meta.schema_version == 2
    await ref.close()
