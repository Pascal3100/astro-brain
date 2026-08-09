from pathlib import Path

import oracle
from oracle.sources._fetch import fetch_with_fallback


def test_fetch_writes_body_on_success(tmp_path: Path) -> None:
    class _Resp:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self): return b"fresh-body"

    dest = tmp_path / "out.txt"
    result = fetch_with_fallback(dest, "https://example/x", "CometEls.fallback.txt", opener=lambda url: _Resp())
    assert result == dest
    assert dest.read_bytes() == b"fresh-body"


def test_fetch_falls_back_on_error(tmp_path: Path) -> None:
    def _boom(url):
        raise OSError("network down")

    dest = tmp_path / "out.txt"
    fetch_with_fallback(dest, "https://example/x", "CometEls.fallback.txt", opener=_boom)
    # dest must equal the bundled fallback byte-for-byte
    assert dest.read_bytes() == (oracle.data_dir() / "CometEls.fallback.txt").read_bytes()


def test_fetch_falls_back_on_empty_body(tmp_path: Path) -> None:
    class _Empty:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self): return b""

    dest = tmp_path / "out.txt"
    fetch_with_fallback(dest, "https://example/x", "CometEls.fallback.txt", opener=lambda url: _Empty())
    assert dest.read_bytes() == (oracle.data_dir() / "CometEls.fallback.txt").read_bytes()
