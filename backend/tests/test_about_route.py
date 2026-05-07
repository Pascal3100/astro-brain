"""Integration tests for GET /about."""

from __future__ import annotations

from fastapi.testclient import TestClient

from astro_brain.app import build_app


def test_about_returns_200() -> None:
    app = build_app(use_hardware=False, db_path_override=":memory:")
    with TestClient(app) as client:
        r = client.get("/about")
        assert r.status_code == 200, r.text


def test_about_has_all_expected_keys() -> None:
    app = build_app(use_hardware=False, db_path_override=":memory:")
    with TestClient(app) as client:
        r = client.get("/about")
        data = r.json()
        for key in (
            "backend_version",
            "app_version_seen",
            "mount_firmware",
            "ip",
            "ssid",
            "uptime_s",
            "started_at",
        ):
            assert key in data, f"missing key: {key}"


def test_about_backend_version() -> None:
    app = build_app(use_hardware=False, db_path_override=":memory:")
    with TestClient(app) as client:
        r = client.get("/about")
        assert r.json()["backend_version"] == "0.2.0"


def test_about_app_version_seen_is_null() -> None:
    app = build_app(use_hardware=False, db_path_override=":memory:")
    with TestClient(app) as client:
        r = client.get("/about")
        assert r.json()["app_version_seen"] is None


def test_about_mount_firmware_is_null() -> None:
    """FakeMount path — mount_firmware stays null for v0.2."""
    app = build_app(use_hardware=False, db_path_override=":memory:")
    with TestClient(app) as client:
        r = client.get("/about")
        assert r.json()["mount_firmware"] is None


def test_about_network_comes_from_fake() -> None:
    """ip and ssid come from FakeNetwork defaults."""
    app = build_app(use_hardware=False, db_path_override=":memory:")
    with TestClient(app) as client:
        r = client.get("/about")
        data = r.json()
        assert data["ip"] == "192.168.1.10"
        assert data["ssid"] == "fake-wifi"


def test_about_uptime_comes_from_fake() -> None:
    """uptime_s comes from FakeSystemInfo default (120)."""
    app = build_app(use_hardware=False, db_path_override=":memory:")
    with TestClient(app) as client:
        r = client.get("/about")
        assert r.json()["uptime_s"] == 120


def test_about_started_at_is_iso8601_utc_string() -> None:
    """started_at is a non-empty ISO 8601 UTC string ending with '+00:00' or 'Z'."""
    app = build_app(use_hardware=False, db_path_override=":memory:")
    with TestClient(app) as client:
        r = client.get("/about")
        started_at = r.json()["started_at"]
        assert isinstance(started_at, str)
        assert started_at  # not empty
        # datetime.isoformat() on a UTC datetime ends with '+00:00'
        assert "+00:00" in started_at or started_at.endswith("Z")
