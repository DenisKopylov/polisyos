"""Semantic epoch owner graph binds every live-acquisition passport reference."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from polisyos.core.contracts.chronology import _split_framed_records
from polisyos.runtime.quality import semantic_epoch
from polisyos.runtime.quality.acquisition_executor import (
    AdmissionPassport,
    build_admission_passport,
)
from tests._helpers.semantic_epoch_native import _build_acquisition_epoch_fixture_service
from tests.unit.data_forge.domains.catalog.knowledge.test_acquisition_authority import (
    _live_execution_fixture,
    _live_semantic_handshake,
)


def test_existing_owner_receipt_reference_schemas_have_complete_roles() -> None:
    """Derived ArtifactRef subclasses participate in the owner-wide census."""
    for model_type, roles in semantic_epoch._OWNER_RECEIPT_REFERENCE_ROLES.items():
        declared: set[tuple[str, ...]] = set()
        for name, field in model_type.model_fields.items():
            if name != "query":
                declared.update(
                    semantic_epoch._declared_artifact_ref_paths(field.annotation, (name,))
                )
        assert declared == set(roles), model_type.__name__


def test_live_passport_source_role_survives_owner_snapshot_and_refuses_wrong_kind(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Replay the selected source profile through the real Catalog owner graph."""
    authority, _, store, evidence, _, _ = _live_execution_fixture(tmp_path / "source")
    candidate, prepared = _live_semantic_handshake(store, evidence, authority=authority)
    passport = build_admission_passport(
        epoch_id=1,
        raw_evidence_ref=evidence.raw_evidence_ref,
        artifact_store=store,
        raw_artifact_id=str(evidence.raw_artifact_id),
        authority=authority,
        boundary_candidate=candidate,
        prepared_epoch=prepared,
        live_source_execution=evidence,
    )
    service, overlay, _ = _build_acquisition_epoch_fixture_service(
        store=store, authority=authority, root=tmp_path / "epoch"
    )
    try:
        overlay.admit_epoch(
            passport=passport,
            prepared_epoch=prepared,
            boundary_candidate=candidate,
            artifact_store=store,
            authority=authority,
        )
        query = service.acquisition_owner_query(query=prepared.query)
        membership = overlay.resolve_native_membership(query=query)
        raw_snapshot = overlay.load_acquisition_owner_snapshot(
            ref=membership.owner_source_snapshot_ref
        )
        (raw_record,) = _split_framed_records(raw_snapshot)
        snapshot = json.loads(raw_record)
        semantic_epoch._validate_owner_snapshot_reference_graph(
            snapshot, owner_kind="catalog_acquisition"
        )

        prefix = ("rows", "*", "observed_passport_json")
        role_path = (*prefix, "live_source_execution", "raw_artifact_ref")
        roles = semantic_epoch._OWNER_SNAPSHOT_REFERENCE_ROLES["catalog_acquisition"]
        declared = semantic_epoch._model_artifact_ref_paths(AdmissionPassport)
        recorded = {path[len(prefix) :] for path in roles if path[: len(prefix)] == prefix}
        assert declared == recorded
        raw_ref = evidence.raw_artifact_ref
        assert raw_ref is not None and raw_ref.manifest_profile_sha256 is not None
        for field, actual_ref, expected_kind in (
            ("raw_artifact_ref", raw_ref, "fabric.acquisition.raw_evidence"),
            ("evidence_bundle_ref", evidence.evidence_bundle_ref, "fabric.evidence_bundle"),
            ("data_snapshot_ref", evidence.data_snapshot_ref, "fabric.data_snapshot"),
        ):
            ref_path = (*prefix, "live_source_execution", field)
            assert roles[ref_path] == expected_kind
            assert ("live_source_execution", field) in declared
            semantic_epoch._require_owner_reference_role(actual_ref, expected_kind=expected_kind)
            wrong_ref = actual_ref.model_copy(update={"kind": "fabric.world_payload"})
            with pytest.raises(ValueError, match="owner artifact role mismatch"):
                semantic_epoch._require_owner_reference_role(wrong_ref, expected_kind=expected_kind)

        missing_roles = dict(roles)
        del missing_roles[role_path]
        monkeypatch.setitem(
            semantic_epoch._OWNER_SNAPSHOT_REFERENCE_ROLES,
            "catalog_acquisition",
            missing_roles,
        )
        with pytest.raises(ValueError, match="passport schema reference roles are incomplete"):
            semantic_epoch._validate_owner_snapshot_reference_graph(
                snapshot, owner_kind="catalog_acquisition"
            )
    finally:
        overlay.close()
