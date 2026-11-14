"""Actual derived method inputs reach a limited WMR and its public consumer."""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from polisyos.core import artifacts
from polisyos.core.contracts.foundry import ExecuteRequest, FoundryInputBindingsRef
from polisyos.foundry.data_plane import load_input_bindings
from polisyos.foundry.execute import execute
from polisyos.foundry.methods.catalog.policy.accounting import PeriodFlowToStock
from polisyos.ir.model_layer.model_spec import ModelSpec
from polisyos.runtime.quality import data_state_substrate as owner
from polisyos.runtime.quality.world_model_record import (
    load_world_model_record,
    world_model_artifact_views,
)
from tests._helpers import world_model_record as world_fixture
from tests._helpers.derived_input_world import build_selected_method_base_world
from tests._helpers.selected_method_input import prepare_selected_method_input_case
from tests.unit.foundry.runtime.test_selected_method_inputs import _fresh_process_read


def test_derived_publisher_preserves_exact_canonical_decimal_bytes(tmp_path: Path) -> None:
    """The exported view declares its codec and retains the selected CAS bytes."""
    from polisyos.core.artifacts import CanonInfo
    from polisyos.core.canon import CanonSpec, from_canonical_bytes, to_canonical_bytes

    payload = {"value": Decimal("0.12345678901234567890123456789"), "label": "Δ"}
    spec = CanonSpec(forbid_floats=False)
    raw = to_canonical_bytes(payload, spec)
    digest = "sha256:" + hashlib.sha256(raw).hexdigest()
    profile = CanonInfo.from_spec(spec)
    owner._write_data_forge_snapshot_binding(
        workspace_dir=tmp_path,
        snapshot_id="canonical-view",
        payload=payload,
        payload_content_hash=digest,
        payload_bytes=raw,
        payload_canon=profile,
        corpus_id="test-canonical-payload",
        builder_revision="test.derived-canonical-view",
        lineage_refs=("cas://sha256/" + hashlib.sha256(raw).hexdigest(),),
        claim_requirement_bindings=(
            {
                "claim_id": "test-canonical-view",
                "requirement_id": "test-canonical-view",
                "requirement_kind": "candidate_model_input",
                "authority_level": "candidate",
                "time_role": "transaction_time",
            },
        ),
    )
    root = tmp_path / "canonical-view" / "ukraine"
    published = (root / "data_state_payload.json").read_bytes()
    assert published == raw
    assert from_canonical_bytes(published) == payload
    manifest = json.loads((root / "publish" / "manifest.json").read_text())
    assert manifest["extra"]["payload_encoding"] == {
        "codec": "polisyos.core.canon",
        "decoder": "from_canonical_bytes",
        "canon": profile.model_dump(mode="json"),
    }
    with pytest.raises(owner.DataStateSubstrateError, match="canonical_bytes_mismatch"):
        owner._write_data_forge_snapshot_binding(
            workspace_dir=tmp_path / "grafted",
            snapshot_id="canonical-view",
            payload=payload,
            payload_content_hash=digest,
            payload_bytes=raw + b"\n",
            payload_canon=profile,
        )
    assert not (tmp_path / "grafted").exists()
    with pytest.raises(owner.DataStateSubstrateError, match="canonical_profile_required"):
        owner._write_data_forge_snapshot_binding(
            workspace_dir=tmp_path / "missing-profile",
            snapshot_id="canonical-view",
            payload=payload,
            payload_content_hash=digest,
            payload_bytes=raw,
        )
    assert not (tmp_path / "missing-profile").exists()
    with pytest.raises(owner.DataStateSubstrateError, match="canonical_bytes_mismatch"):
        owner._write_data_forge_snapshot_binding(
            workspace_dir=tmp_path / "changed-profile",
            snapshot_id="canonical-view",
            payload=payload,
            payload_content_hash=digest,
            payload_bytes=raw,
            payload_canon=profile.model_copy(update={"ensure_ascii": True}),
        )
    assert not (tmp_path / "changed-profile").exists()
    with pytest.raises(ValueError, match="unsupported_canonical_codec_version"):
        owner._write_data_forge_snapshot_binding(
            workspace_dir=tmp_path / "unsupported-version",
            snapshot_id="canonical-view",
            payload=payload,
            payload_content_hash=digest,
            payload_bytes=raw,
            payload_canon=profile.model_copy(update={"version": "999.0.0"}),
        )
    assert not (tmp_path / "unsupported-version").exists()


def test_derived_model_transport_law_preserves_fields_and_is_idempotent(tmp_path: Path) -> None:
    """Data transport must not silently change the compiled model's other fields."""
    store = artifacts.FileSystemCAS(tmp_path / "cas")
    original_ref = world_fixture._data_snapshot_ref(store, snapshot_id="original")
    next_ref = world_fixture._data_snapshot_ref(store, snapshot_id="next")
    original_notes = [f"author-owned modeling note {index}" for index in range(50)]
    source = ModelSpec(
        model_id="model_transport_unrelated",
        data_snapshot_ref=str(original_ref.artifact_id),
        registry_bundle_ref="sha256:" + "a" * 64,
        calibrated=False,
        calibration_ref=None,
        notes=original_notes,
    )
    result = owner.materialize_derived_candidate_model_spec(source, next_ref)
    expected = source.model_dump(mode="json")
    expected["data_snapshot_ref"] = str(next_ref.artifact_id)
    assert result.model_dump(mode="json") == expected
    assert owner.materialize_derived_candidate_model_spec(result, next_ref) == result
    assert source.data_snapshot_ref == str(original_ref.artifact_id)
    assert result.notes == source.notes == original_notes
    assert len(result.notes) == 50


@pytest.mark.parametrize(
    ("calibrated", "calibration_ref"),
    [(True, None), (False, "sha256:" + "b" * 64)],
)
def test_derived_model_transport_requires_recompile_for_calibration(
    tmp_path: Path, calibrated: bool, calibration_ref: str | None
) -> None:
    """A changed source cannot relabel an existing calibrated compiled program."""
    store = artifacts.FileSystemCAS(tmp_path / "cas")
    next_ref = world_fixture._data_snapshot_ref(store, snapshot_id="next")
    source = ModelSpec(
        model_id="model_calibrated",
        data_snapshot_ref=str(next_ref.artifact_id),
        registry_bundle_ref="sha256:" + "a" * 64,
        calibrated=calibrated,
        calibration_ref=calibration_ref,
    )
    with pytest.raises(owner.DataStateSubstrateError, match="calibration_recompile_required"):
        owner.materialize_derived_candidate_model_spec(source, next_ref)


def test_versioned_method_base_world_keeps_selected_initial_bindings(tmp_path: Path) -> None:
    """Finish a real compiler/WMR preflight before acquiring derivation operands."""
    case, _metadata = prepare_selected_method_input_case(
        tmp_path / "method", method_class=PeriodFlowToStock, snapshot_id="derived-method-base"
    )
    try:
        built, _registry, _registry_ref = build_selected_method_base_world(
            case, tmp_path / "base-world"
        )
        views = world_model_artifact_views(built.record)
        assert artifacts.artifact_ref_identity_key(views.data_snapshot_ref) == (
            artifacts.artifact_ref_identity_key(case.data_snapshot_ref)
        )
        assert artifacts.artifact_ref_identity_key(views.bound_state_snapshot_ref) == (
            artifacts.artifact_ref_identity_key(case.bound_state_snapshot_ref)
        )
        assert built.record.region_or_jurisdiction == "UA"
        assert built.record.authority_status == "limited"
    finally:
        case.close()


def test_registered_native_derived_input_builds_limited_world_and_real_consumer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The method input changes the calculation without changing its base state."""
    from tests._helpers.registered_derived_method_input import (
        materialize_registered_method_input_case,
    )

    case, metadata = prepare_selected_method_input_case(
        tmp_path / "method", method_class=PeriodFlowToStock, snapshot_id="derived-method-base"
    )
    try:
        base, registry, registry_ref = build_selected_method_base_world(
            case, tmp_path / "base-world"
        )
        materialize_registered_method_input_case(case, metadata)
        materialized = metadata["batch_materialization"]
        original_state = case.store.get_bytes(case.bound_state_snapshot_ref)
        new_world = owner.build_derived_model_input_candidate_world(
            case.store,
            base_world_model=base.record,
            substrate_registry=registry,
            substrate_registry_artifact_ref=registry_ref,
            materialization=materialized,
            workspace_dir=tmp_path / "derived-world",
            transaction_time=datetime(2026, 11, 14, 0, 1, tzinfo=UTC),
        )
        views = world_model_artifact_views(new_world.world_model.record)
        actual = load_input_bindings(case.store, views.input_bindings_ref)
        assert actual.schema_version == "1.4"
        assert artifacts.artifact_ref_identity_key(actual.resolved_binding_manifest_ref) == (
            artifacts.artifact_ref_identity_key(materialized.resolved_binding_manifest_ref)
        )
        assert artifacts.artifact_ref_identity_key(views.bound_state_snapshot_ref) == (
            artifacts.artifact_ref_identity_key(case.bound_state_snapshot_ref)
        )
        assert case.store.get_bytes(views.bound_state_snapshot_ref) == original_state
        assert {rule.binding_id for rule in actual.rules} == {"opening-stock"}
        assert new_world.world_model.record.authority_status == "limited"
        assert "causal_coupling_not_established" in (
            new_world.world_model.record.limitations.admissibility_blockers
        )
        assert owner.DERIVED_MODEL_INPUT_CANDIDATE_PROFILE in (
            new_world.world_model.record.limitations.transport_limits
        )
        reader = artifacts.FileSystemCAS.open_existing_read_only(case.store.root)
        reopened = load_world_model_record(reader, new_world.world_model.record_ref)
        assert reopened.model_dump(mode="json") == new_world.world_model.record.model_dump(
            mode="json"
        )

        result = execute(
            case.store,
            ExecuteRequest(
                exec_plan_ref=case.exec_plan_ref,
                registry_bundle_ref=case.registry_bundle_ref,
                input_bindings_ref=FoundryInputBindingsRef.model_validate(
                    views.input_bindings_ref.model_dump(mode="python")
                ),
                return_selected_profile=True,
            ),
        )
        assert result.ok, result.notes
        assert result.simulation_result_ref is not None
        fresh = _fresh_process_read(case, result.simulation_result_ref)
        assert fresh["stock"] == 4_000_000_000

        forbidden_world = tmp_path / "foreign-input-world"
        with pytest.raises(owner.DataStateSubstrateError, match="selected_basis_mismatch"):
            owner.build_derived_model_input_candidate_world(
                case.store,
                base_world_model=base.record,
                substrate_registry=registry,
                substrate_registry_artifact_ref=registry_ref,
                materialization=replace(materialized, input_bindings_ref=case.input_bindings_ref),
                workspace_dir=forbidden_world,
                transaction_time=datetime(2026, 11, 14, 0, 1, tzinfo=UTC),
            )
        assert not forbidden_world.exists()

        actual_get = case.store.get_bytes

        def removed_manifest(ref):
            if isinstance(ref, artifacts.ArtifactRef) and artifacts.artifact_ref_identity_key(
                ref
            ) == artifacts.artifact_ref_identity_key(materialized.resolved_binding_manifest_ref):
                raise FileNotFoundError("test removed the selected semantic manifest")
            return actual_get(ref)

        with monkeypatch.context() as context:
            context.setattr(case.store, "get_bytes", removed_manifest)
            with pytest.raises((ValueError, FileNotFoundError)):
                owner.build_derived_model_input_candidate_world(
                    case.store,
                    base_world_model=base.record,
                    substrate_registry=registry,
                    substrate_registry_artifact_ref=registry_ref,
                    materialization=materialized,
                    workspace_dir=tmp_path / "missing-manifest-world",
                    transaction_time=datetime(2026, 11, 14, 0, 1, tzinfo=UTC),
                )
        assert case.store.get_bytes(case.bound_state_snapshot_ref) == original_state
    finally:
        for history in metadata.get("native_histories", ()):
            history.overlay.close()
        case.close()
