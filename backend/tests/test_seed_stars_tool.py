"""Tests offline du dev tool tools/seed_stars.py."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
sys.path.insert(0, str(TOOLS))

from seed_stars import build_sql, parse_csn  # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "iau_csn_excerpt.txt"


def test_parse_csn_extracts_named_stars() -> None:
    rows = parse_csn(FIXTURE.read_text(encoding="utf-8"))

    by_name = {r.name: r for r in rows}
    assert "Sirius" in by_name
    assert "Vega" in by_name
    assert by_name["Sirius"].mag == pytest.approx(-1.45)
    assert by_name["Sirius"].ra_deg == pytest.approx(101.287155)
    assert by_name["Sirius"].dec_deg == pytest.approx(-16.716116)
    assert by_name["Sirius"].constellation == "CMa"


def test_parse_csn_skips_comments_and_blank() -> None:
    text = "# header\n\n# another\n"
    assert parse_csn(text) == []


def test_build_sql_filters_by_max_mag() -> None:
    rows = parse_csn(FIXTURE.read_text(encoding="utf-8"))

    sql = build_sql(rows, max_mag=3.0)

    # Faintstar (mag 4.5) excluded; Sirius/Vega/Polaris/Betelgeuse included
    assert "Sirius" in sql
    assert "Vega" in sql
    assert "Polaris" in sql
    assert "Betelgeuse" in sql
    assert "Faintstar" not in sql


def test_build_sql_uses_insert_or_replace() -> None:
    rows = parse_csn(FIXTURE.read_text(encoding="utf-8"))
    sql = build_sql(rows, max_mag=3.0)
    assert "INSERT OR REPLACE INTO catalog_objects" in sql


def test_build_sql_qualifies_id_with_kind_prefix() -> None:
    rows = parse_csn(FIXTURE.read_text(encoding="utf-8"))
    sql = build_sql(rows, max_mag=3.0)
    assert "'star:sirius'" in sql.lower()


def test_build_sql_is_deterministic() -> None:
    rows = parse_csn(FIXTURE.read_text(encoding="utf-8"))
    sql1 = build_sql(rows, max_mag=3.0)
    sql2 = build_sql(rows, max_mag=3.0)
    assert sql1 == sql2


def test_build_sql_escapes_single_quotes() -> None:
    from seed_stars import StarRow

    row = StarRow(
        slug="weird", name="O'Brian Star", designation="alf X",
        constellation="X", ra_deg=0.0, dec_deg=0.0, mag=1.0,
    )
    sql = build_sql([row], max_mag=3.0)
    assert "O''Brian Star" in sql
