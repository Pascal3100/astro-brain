"""Emit manifest.json — the small sync point consumers poll."""

import hashlib
import json
from pathlib import Path

from oracle.build_db import BuildMeta


def write_manifest(
    sqlite_path: Path, out_path: Path, meta: BuildMeta, sqlite_url: str
) -> dict:
    digest = hashlib.sha256(sqlite_path.read_bytes()).hexdigest()
    manifest = {
        "schema_version": meta.schema_version,
        "generated_at": meta.generated_at,
        "sqlite_url": sqlite_url,
        "sqlite_sha256": digest,
        "window_start": meta.window_start,
        "window_end": meta.window_end,
    }
    out_path.write_text(json.dumps(manifest, indent=2, sort_keys=True))
    return manifest
