"""CLI: python -m oracle -> build reference.sqlite + manifest.json."""

import os
from datetime import datetime, timezone
from pathlib import Path

from oracle.build import build

if __name__ == "__main__":
    out_dir = Path(os.environ.get("ORACLE_OUT_DIR", "build_output"))
    sqlite_url = os.environ.get(
        "ORACLE_SQLITE_URL",
        "https://github.com/OWNER/REPO/releases/download/almanac-latest/reference.sqlite",
    )
    sqlite_path, manifest_path = build(
        out_dir, datetime.now(timezone.utc), sqlite_url=sqlite_url
    )
    print(f"built {sqlite_path} + {manifest_path}")
