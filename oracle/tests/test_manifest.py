import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from oracle.build_db import SCHEMA_VERSION, BuildMeta
from oracle.manifest import write_manifest


def _meta(now: str) -> BuildMeta:
    return BuildMeta(SCHEMA_VERSION, now, None, now, now, "de421.bsp")


def test_manifest_matches_file(tmp_path: Path) -> None:
    sqlite_path = tmp_path / "reference.sqlite"
    sqlite_path.write_bytes(b"not-a-real-db-but-hashable")
    now = datetime(2026, 8, 1, tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")

    manifest = write_manifest(
        sqlite_path, tmp_path / "manifest.json", _meta(now), "https://example/x.sqlite"
    )

    expected_sha = hashlib.sha256(sqlite_path.read_bytes()).hexdigest()
    assert manifest["sqlite_sha256"] == expected_sha
    assert manifest["schema_version"] == SCHEMA_VERSION
    assert manifest["sqlite_url"] == "https://example/x.sqlite"
    on_disk = json.loads((tmp_path / "manifest.json").read_text())
    assert on_disk == manifest
