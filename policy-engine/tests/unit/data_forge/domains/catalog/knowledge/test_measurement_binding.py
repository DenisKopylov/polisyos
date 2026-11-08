"""Catalog binding requires the selected definition's evidence bytes."""

from __future__ import annotations

from pathlib import Path

import pytest

from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.contracts.variable_binding import (
    SelectedVariableBindingRef,
    VariableSemanticDefinition,
)
from polisyos.data_forge.domains.catalog.knowledge.measurement_binding import (
    _AssessmentRefusal,
    _reopen_definition_evidence,
)


def _definition_with_selected_evidence(
    store: FileSystemCAS,
) -> tuple[VariableSemanticDefinition, SelectedVariableBindingRef]:
    source_document = b"Meaning: a bounded test-owned semantic definition.\n"
    selected_ref = store.put_bytes(
        source_document,
        PutOptions(kind="test.semantic_definition_evidence", media_type="text/plain"),
        return_selected_profile=True,
    )
    evidence_ref = SelectedVariableBindingRef.model_validate(selected_ref.model_dump(mode="json"))
    return (
        VariableSemanticDefinition(
            namespace="test",
            stable_id="measurement",
            revision="1",
            meaning="A test-owned semantic meaning.",
            definition_evidence_refs=(evidence_ref,),
        ),
        evidence_ref,
    )


def test_catalog_reopens_content_bound_definition_evidence(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    definition, _ = _definition_with_selected_evidence(store)

    _reopen_definition_evidence(store, definition)


def test_catalog_refuses_when_selected_definition_evidence_bytes_are_removed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    definition, selected_ref = _definition_with_selected_evidence(store)

    def missing_selected_bytes(ref):
        if ref.artifact_id == selected_ref.artifact_id:
            raise FileNotFoundError("removed selected source documentation bytes")
        return store.get_bytes(ref)

    monkeypatch.setattr(store, "get_bytes", missing_selected_bytes)

    with pytest.raises(_AssessmentRefusal, match="evidence_bytes_unavailable"):
        _reopen_definition_evidence(store, definition)
