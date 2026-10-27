"""Source collection owner/schema and namespaced semantics checks."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from polisyos.fabric.ingestion.source_collection import SourceCollection, source_namespace


def test_source_collection_schema_matches_actual_owner_and_rejects_drift() -> None:
    product_root = Path(__file__).resolve().parents[4]
    actual = json.loads((product_root / "schemas/fabric/source_collection.schema.json").read_text())
    expected = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://polisyos.local/schemas/fabric/source_collection.schema.json",
        **SourceCollection.model_json_schema(),
    }
    assert actual == expected
    corrupted = deepcopy(actual)
    corrupted["properties"]["production_currentness"] = {"const": "established"}
    with pytest.raises(AssertionError):
        assert corrupted == expected


def test_source_namespaces_are_unambiguous_and_safe_for_real_binding_paths() -> None:
    first = source_namespace("fixture.A", "B.C")
    second = source_namespace("fixture.A.B", "C")
    assert first != second
    assert "." not in first and "." not in second
    assert len(first) == 64 and len(second) == 64
