from pathlib import Path

import oracle
from oracle.sources.comets import fetch_comet_els


class _FakeResponse:
    def __init__(self, body: bytes) -> None:
        self._body = body

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc) -> None:
        return None


def test_fetch_writes_remote_body(tmp_path: Path) -> None:
    dest = tmp_path / "CometEls.txt"

    def opener(url):  # noqa: ANN001
        return _FakeResponse(b"FRESH-CONTENT")

    result = fetch_comet_els(dest, opener=opener)
    assert result == dest
    assert dest.read_bytes() == b"FRESH-CONTENT"


def test_fetch_falls_back_on_error(tmp_path: Path) -> None:
    dest = tmp_path / "CometEls.txt"

    def opener(url):  # noqa: ANN001
        raise OSError("network down")

    result = fetch_comet_els(dest, opener=opener)
    assert result == dest
    # fell back to the bundled snapshot -> bytes match exactly
    assert dest.read_bytes() == (oracle.data_dir() / "CometEls.fallback.txt").read_bytes()
