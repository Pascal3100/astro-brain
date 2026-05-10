"""Tests for the catalog Pydantic models."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from astro_brain.services.catalog.models import CatalogFilter, CatalogObject


def test_catalog_object_minimal_fields() -> None:
    obj = CatalogObject(
        qualified_id="star:sirius",
        kind="star",
        name="Sirius",
        ra_deg=101.287,
        dec_deg=-16.716,
    )
    assert obj.qualified_id == "star:sirius"
    assert obj.kind == "star"
    assert obj.designation is None
    assert obj.mag is None
    assert obj.constellation is None
    assert obj.extras == {}


def test_catalog_object_full_fields() -> None:
    obj = CatalogObject(
        qualified_id="messier:m31",
        kind="messier",
        name="Andromeda Galaxy",
        designation="M 31",
        ra_deg=10.6847,
        dec_deg=41.269,
        mag=3.4,
        constellation="Andromeda",
        object_type="galaxy",
        angular_size_arcmin=178.0,
        extras={"distance_kly": 2540},
    )
    assert obj.designation == "M 31"
    assert obj.object_type == "galaxy"
    assert obj.extras == {"distance_kly": 2540}


def test_catalog_object_rejects_unknown_kind() -> None:
    with pytest.raises(ValidationError):
        CatalogObject(
            qualified_id="foo:x",
            kind="foo",  # type: ignore[arg-type]
            name="X",
            ra_deg=0.0,
            dec_deg=0.0,
        )


def test_catalog_filter_defaults() -> None:
    f = CatalogFilter()
    assert f.kind is None
    assert f.search is None
    assert f.max_mag is None
    assert f.limit == 100
    assert f.offset == 0


def test_catalog_filter_limit_max_500() -> None:
    f = CatalogFilter(limit=500)
    assert f.limit == 500
    with pytest.raises(ValidationError):
        CatalogFilter(limit=501)


def test_catalog_filter_limit_must_be_positive() -> None:
    with pytest.raises(ValidationError):
        CatalogFilter(limit=0)


def test_catalog_filter_offset_must_be_non_negative() -> None:
    with pytest.raises(ValidationError):
        CatalogFilter(offset=-1)
