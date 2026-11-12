"""Read back the exact phase and input selection persisted before protected N5."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from pydantic import ValidationError

from polisyos.common.canonical_profile import CanonicalProfileRefusalError
from polisyos.core import canon
from polisyos.core.artifacts import ArtifactRef, PutOptions, SchemaInfo, read_core_json_artifact
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.contracts import FoundryInputBindingsRef
from polisyos.runtime.quality.model_input_successor_selection import (
    ModelInputSuccessorSelection,
    ModelInputUseActionPhase,
    persist_model_input_successor_selection,
    persist_model_input_use_action_phase,
    read_model_input_successor_selection,
    read_model_input_use_action_phase,
)


def _selected_input(
    store: FileSystemCAS, kind: str, *, media_type: str = "application/json"
) -> ArtifactRef:
    return store.put_bytes(
        canon.to_canonical_bytes({"fixture_edge": kind}),
        PutOptions(kind=kind, media_type=media_type),
        return_selected_profile=True,
    )


def test_model_input_phase_and_selection_reopen_exact_wire_and_profile(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    phase = ModelInputUseActionPhase(
        tenant_id="tenant-a",
        cell_id="cell-a",
        run_id="run-a",
        source_job_id="source-job",
        action_job_id="use-job",
        route_id="sha256:" + "a" * 64,
        action_payload_ref=_selected_input(store, "runtime.control_job_payload.acquisition"),
        authority_decision_ref=_selected_input(
            store, "runtime_quality.agent_action_authority_decision"
        ),
    )
    phase_ref = persist_model_input_use_action_phase(store, phase)
    foundry_ref = _selected_input(store, "foundry.input_bindings")
    selection = ModelInputSuccessorSelection(
        tenant_id=phase.tenant_id,
        cell_id=phase.cell_id,
        run_id=phase.run_id,
        source_job_id=phase.source_job_id,
        compiled_ref=_selected_input(store, "runtime.compiled_recursive_generation_cycle"),
        blocked_execution_ref=_selected_input(
            store, "runtime.quality.generic_cycle_simulation_n5_execution"
        ),
        routing_report_ref=_selected_input(store, "runtime.quality.model_input_routing_report"),
        activation_receipt_ref=_selected_input(
            store,
            "epoch.activated_overlay_admission_receipt",
            media_type="application/vnd.polisyos.epoch+json",
        ),
        observation_id="stock-1",
        observation_content_sha256="sha256:" + "b" * 64,
        route_id=phase.route_id,
        action_job_id=phase.action_job_id,
        action_worker_id="worker-a",
        action_attempt=1,
        action_phase_ref=phase_ref,
        authority_decision_ref=phase.authority_decision_ref,
        reentry_budget_window_id="c" * 64,
        reentry_budget_window_digest="d" * 64,
        semantic_foundry_input_bindings_ref=FoundryInputBindingsRef.model_validate(
            foundry_ref.model_dump(mode="python")
        ),
    )
    selection_ref = persist_model_input_successor_selection(store, selection)
    reopened = FileSystemCAS(tmp_path / "cas")
    for expected, ref, read, wire_version in (
        (
            phase,
            phase_ref,
            read_model_input_use_action_phase,
            "polisyos.runtime.ModelInputUseActionPhase@1.0",
        ),
        (
            selection,
            selection_ref,
            read_model_input_successor_selection,
            "polisyos.runtime.ModelInputSuccessorSelection@1.0",
        ),
    ):
        assert read(reopened, ref) == expected
        manifest = reopened.get_manifest(ref)
        schema = manifest.artifact_schema
        payload = read_core_json_artifact(reopened, ref).value
        assert schema is not None and schema.version == "1.0"
        assert payload["schema_version"] == wire_version
        if expected is selection:
            assert "routing_use_decision_ref" not in payload
        options = PutOptions(
            kind=manifest.kind,
            media_type=manifest.media_type,
            schema=schema,
            canon=manifest.canon,
            producer=manifest.producer,
            tenant_context=manifest.tenant_context,
            inputs=manifest.inputs,
        )
        wrong_wire_ref = store.put_json(
            {**payload, "schema_version": "1.0"}, options, return_selected_profile=True
        )
        with pytest.raises(ValidationError) as wrong_wire:
            read(reopened, wrong_wire_ref)
        (issue,) = wrong_wire.value.errors()
        assert issue["type"] == "literal_error"
        assert issue["input"] == "1.0"
        if expected is selection:
            assert (
                repr("polisyos.runtime.ModelInputSuccessorSelection@1.0")
                in issue["ctx"]["expected"]
            )
            assert (
                repr("polisyos.runtime.ModelInputSuccessorSelection@2.0")
                in issue["ctx"]["expected"]
            )
        else:
            assert issue["ctx"]["expected"] == repr(wire_version)

        other_profile = store.put_bytes(
            store.get_bytes(ref),
            replace(options, schema=SchemaInfo(name=schema.name, version="2.0")),
            return_selected_profile=True,
        )
        assert other_profile.artifact_id == ref.artifact_id
        assert other_profile.manifest_profile_sha256 != ref.manifest_profile_sha256
        profile_error = (
            "canon_profile_typed_artifact_schema_version_mismatch"
            if expected is selection
            else "canon_profile_typed_artifact_schema_version_unsupported"
        )
        with pytest.raises(
            CanonicalProfileRefusalError,
            match=profile_error,
        ):
            read(reopened, other_profile)

    v2_payload = selection.model_dump(mode="python")
    v2_payload["schema_version"] = "polisyos.runtime.ModelInputSuccessorSelection@2.0"
    with pytest.raises(
        ValidationError,
        match="model_input_successor_use_decision_version_mismatch",
    ):
        ModelInputSuccessorSelection.model_validate(v2_payload)
    decision_ref = _selected_input(store, "runtime.quality.model_input_routing_use_decision")
    v2_payload["routing_use_decision_ref"] = decision_ref
    v2_selection = ModelInputSuccessorSelection.model_validate(v2_payload)
    assert v2_selection.routing_use_decision_ref == decision_ref
    assert v2_selection.model_dump(mode="python")[
        "routing_use_decision_ref"
    ] == decision_ref.model_dump(mode="python")
