from __future__ import annotations

import logging
from copy import deepcopy

import pytest

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef, ProducerInfo, SchemaInfo
from polisyos.core.artifacts.registry import RegistryBundlePayload
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.contracts.fabric import DataSnapshot, DataSnapshotRef
from polisyos.core.contracts.foundry import (
    FoundryInputBindings,
    FoundryInputBindingsRef,
    Metrics,
    StateSnapshot,
    StateSnapshotRef,
)
from polisyos.core.contracts.scholar import ResearchIntent
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.ir.governance.gate import GateContext, GatePriority, GateRequest
from polisyos.ir.governance.policy_spec import PolicySpec
from polisyos.ir.governance.problem_frame import ProblemDomain, ProblemFrame
from polisyos.ir.loading.norm_pack import NormPack
from polisyos.ir.model_layer.model_spec import ModelSpec
from polisyos.ir.trinity import TrinityBundle
from polisyos.scholar.types import KnowledgeBundlePayloadV1
from polisyos.scientist.nodes.builtins.governance.governance_gate_requests import (
    _create_gate_request,
    _ensure_human_review_gate_request,
    _gate_replay_readiness,
    _gate_replay_summary,
)
from polisyos.scientist.nodes.builtins.governance.run_governance import (
    _handle_initial_gate_request,
)
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_METRICS_REF,
    INPUT_DATA_SNAPSHOT_REF,
    INPUT_INPUT_BINDINGS_REF,
    INPUT_KNOWLEDGE_BUNDLE_REF,
    INPUT_MODEL_SPEC_REF,
    INPUT_NORM_PACK_REF,
    INPUT_REGISTRY_BUNDLE_REF,
    INPUT_RESEARCH_INTENT_REF,
    INPUT_STATE_SNAPSHOT_REF,
    INPUT_TRINITY_BUNDLE_REF,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.kernel.gate_protocol import HumanGateProtocol


def test_replay_readiness_moves_from_incomplete_to_partial_to_complete(tmp_path) -> None:
    store, ctx, protocol, registry_ref = _build_gate_context(
        tmp_path,
        run_id="R_gate_replay_basis",
    )
    replay_refs = _build_valid_replay_inputs(store, registry_ref)
    trinity_ref = replay_refs[INPUT_TRINITY_BUNDLE_REF]
    state = ExperimentState(
        run_id="R_gate_replay_basis",
        inputs={
            INPUT_TRINITY_BUNDLE_REF: trinity_ref,
            INPUT_REGISTRY_BUNDLE_REF: registry_ref,
        },
        params={"governance_profile": "strict"},
    )

    readiness, missing_refs, invalid_refs = _gate_replay_readiness(ctx, state)
    assert readiness == "incomplete"
    assert missing_refs == [
        "state_source_ref",
        INPUT_INPUT_BINDINGS_REF,
        INPUT_NORM_PACK_REF,
        INPUT_KNOWLEDGE_BUNDLE_REF,
        INPUT_RESEARCH_INTENT_REF,
    ]
    assert invalid_refs == {}
    assert _gate_replay_summary(ctx, state) == {
        "readiness": "incomplete",
        "missing_refs": [
            "state_source_ref",
            INPUT_INPUT_BINDINGS_REF,
            INPUT_NORM_PACK_REF,
            INPUT_KNOWLEDGE_BUNDLE_REF,
            INPUT_RESEARCH_INTENT_REF,
        ],
        "invalid_refs": {},
        "why_partial": ["missing_state_source"],
        "suggested_next_step": "Persist input_bindings_ref for replay-grade completeness.",
        "determinism_tier": None,
        "seed_source": None,
    }

    state.inputs[INPUT_DATA_SNAPSHOT_REF] = replay_refs[INPUT_DATA_SNAPSHOT_REF]
    readiness, missing_refs, invalid_refs = _gate_replay_readiness(ctx, state)
    assert readiness == "partial"
    assert invalid_refs == {}
    assert missing_refs == [
        INPUT_INPUT_BINDINGS_REF,
        "norm_pack_ref",
        "knowledge_bundle_ref",
        "research_intent_ref",
    ]

    for key in (
        INPUT_INPUT_BINDINGS_REF,
        INPUT_NORM_PACK_REF,
        INPUT_KNOWLEDGE_BUNDLE_REF,
        INPUT_RESEARCH_INTENT_REF,
    ):
        state.inputs[key] = replay_refs[key]

    readiness, missing_refs, invalid_refs = _gate_replay_readiness(ctx, state)
    assert readiness == "complete"
    assert missing_refs == []
    assert invalid_refs == {}

    state.params["governance_profile"] = "changed_profile"
    assert _gate_replay_readiness(ctx, state) == ("complete", [], {})

    request, _ = _create_gate_request(ctx=ctx, protocol=protocol, state=state)
    assert request.context.governance_profile == "changed_profile"
    assert request.context.replay_summary == {
        "readiness": "complete",
        "missing_refs": [],
        "invalid_refs": {},
        "why_partial": [],
        "suggested_next_step": None,
        "determinism_tier": None,
        "seed_source": None,
    }


def test_gate_request_persists_context_and_scopes_identity_to_phase_and_iteration(
    tmp_path,
) -> None:
    store, ctx, protocol, registry_ref = _build_gate_context(
        tmp_path,
        run_id="R_gate_request_context",
    )
    trinity_ref = store.put_json(
        {"policy_spec": {"interventions": [{"id": "one"}, {"id": "two"}]}},
        PutOptions(
            kind="ir.trinity_bundle",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.ir.TrinityBundle", version="1.0"),
        ),
    )
    metrics_ref = store.put_json(
        Metrics(
            values={
                "alpha": 1,
                "beta": 2,
                "gamma": 3,
                "delta": 4,
                "epsilon": 5,
                "zeta": 6,
            }
        ),
        PutOptions(
            kind="foundry.metrics",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.foundry.Metrics", version="1.0"),
        ),
    )
    model_spec_ref = store.put_json(
        ModelSpec(
            model_id="model_gate_request_context",
            data_snapshot_ref=str(trinity_ref.artifact_id),
        ),
        PutOptions(
            kind="ir.model_spec",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.ir.ModelSpec", version="1.0"),
        ),
    )
    state = ExperimentState(
        run_id="R_gate_request_context",
        inputs={
            INPUT_TRINITY_BUNDLE_REF: trinity_ref,
            INPUT_REGISTRY_BUNDLE_REF: registry_ref,
            INPUT_MODEL_SPEC_REF: model_spec_ref,
        },
        artifacts_index={ARTIFACT_METRICS_REF: metrics_ref},
        params={
            "workflow_id": "policy_design",
            "phase": "PREPUBLISH",
            "gate_iteration": 4,
            "gate_escalated": True,
            "gate_timeout_seconds": 90,
            "governance_profile": "strict",
            "random_seed": 42,
            "determinism_tier": "replayable",
        },
    )

    request, request_ref = _create_gate_request(ctx=ctx, protocol=protocol, state=state)
    assert request_ref.kind == "ir.gate_request"
    assert request.schema_version == "1.2"
    assert request.reason == "governance_profile_requires_approval"
    assert request.priority == GatePriority.CRITICAL
    assert request.timeout_seconds == 90
    assert request.context.workflow_id == "policy_design"
    assert request.context.phase == "PREPUBLISH"
    assert request.context.iteration == 4
    assert request.context.governance_profile == "strict"
    assert request.context.policy_summary == "Policy with 2 intervention(s)"
    assert request.context.simulation_results == {
        "alpha": 1,
        "beta": 2,
        "delta": 4,
        "epsilon": 5,
        "gamma": 3,
    }
    assert request.context.replay_summary["readiness"] == "incomplete"
    assert request.context.replay_summary["seed_source"] == "params.random_seed"
    selected_replay_refs = request.context.selected_replay_refs
    assert selected_replay_refs is not None
    assert set(selected_replay_refs) == {
        INPUT_TRINITY_BUNDLE_REF,
        INPUT_REGISTRY_BUNDLE_REF,
        INPUT_MODEL_SPEC_REF,
    }
    assert str(selected_replay_refs[INPUT_TRINITY_BUNDLE_REF].artifact_id) == str(
        trinity_ref.artifact_id
    )
    assert (
        selected_replay_refs[INPUT_REGISTRY_BUNDLE_REF].manifest_profile_sha256
        == registry_ref.manifest_profile_sha256
    )
    assert str(selected_replay_refs[INPUT_MODEL_SPEC_REF].artifact_id) == str(
        model_spec_ref.artifact_id
    )
    persisted = GateRequest.model_validate(
        from_canonical_bytes(store.get_bytes(request_ref.artifact_id))
    )
    assert persisted == request

    repeated, _ = _create_gate_request(ctx=ctx, protocol=protocol, state=state)
    assert repeated.request_id == request.request_id

    missing_non_replay_input = state.model_copy(deep=True)
    missing_non_replay_input.inputs.pop(INPUT_MODEL_SPEC_REF)
    changed_inputs, _ = _create_gate_request(
        ctx=ctx,
        protocol=protocol,
        state=missing_non_replay_input,
    )
    assert changed_inputs.request_id != request.request_id

    malformed_non_replay_input = state.model_copy(deep=True)
    malformed_non_replay_input.inputs[INPUT_MODEL_SPEC_REF] = {
        "artifact_id": "malformed-but-present",
        "kind": "ir.model_spec",
        "media_type": "application/json",
    }
    with pytest.raises(ValueError, match="Malformed gate input reference for 'model_spec_ref'"):
        _create_gate_request(
            ctx=ctx,
            protocol=protocol,
            state=malformed_non_replay_input,
        )

    changed_phase = state.model_copy(deep=True)
    changed_phase.params["phase"] = "POSTFLIGHT_GOV"
    phase_request, _ = _create_gate_request(ctx=ctx, protocol=protocol, state=changed_phase)
    assert phase_request.request_id != request.request_id

    changed_iteration = state.model_copy(deep=True)
    changed_iteration.params["gate_iteration"] = 5
    iteration_request, _ = _create_gate_request(
        ctx=ctx,
        protocol=protocol,
        state=changed_iteration,
    )
    assert iteration_request.request_id != request.request_id

    malformed_epoch = state.model_copy(deep=True)
    malformed_epoch.params["gate_iteration"] = "not-an-integer"
    malformed_epoch.params["gate_timeout_seconds"] = 0
    malformed_epoch.params["governance_profile"] = {"name": "strict"}
    malformed_request, _ = _create_gate_request(
        ctx=ctx,
        protocol=protocol,
        state=malformed_epoch,
    )
    assert malformed_request.context.iteration == 1
    assert malformed_request.timeout_seconds is None
    assert malformed_request.context.governance_profile is None


def test_replay_readiness_refuses_invalid_present_optional_reference(tmp_path) -> None:
    store, ctx, _, registry_ref = _build_gate_context(
        tmp_path,
        run_id="R_gate_replay_invalid_optional",
    )
    replay_refs = _build_valid_replay_inputs(store, registry_ref)
    state = ExperimentState(
        run_id="R_gate_replay_invalid_optional",
        inputs={
            INPUT_TRINITY_BUNDLE_REF: replay_refs[INPUT_TRINITY_BUNDLE_REF],
            INPUT_REGISTRY_BUNDLE_REF: registry_ref,
            INPUT_DATA_SNAPSHOT_REF: replay_refs[INPUT_DATA_SNAPSHOT_REF],
            INPUT_NORM_PACK_REF: replay_refs[INPUT_NORM_PACK_REF],
            INPUT_RESEARCH_INTENT_REF: replay_refs[INPUT_RESEARCH_INTENT_REF],
        },
    )
    state.inputs[INPUT_KNOWLEDGE_BUNDLE_REF] = {
        "artifact_id": "not-a-content-address",
        "kind": "scholar.knowledge_bundle",
        "media_type": "application/json",
    }

    readiness, missing_refs, invalid_refs = _gate_replay_readiness(ctx, state)

    assert readiness == "partial"
    assert INPUT_KNOWLEDGE_BUNDLE_REF not in missing_refs
    assert missing_refs == [INPUT_INPUT_BINDINGS_REF]
    assert invalid_refs == {INPUT_KNOWLEDGE_BUNDLE_REF: "malformed_ref"}
    summary = _gate_replay_summary(ctx, state)
    assert summary["invalid_refs"] == invalid_refs
    assert summary["why_partial"] == ["invalid_replay_inputs", "missing_optional_inputs"]
    assert "Repair the invalid replay refs" in summary["suggested_next_step"]


def test_human_gate_consumer_carries_malformed_present_replay_input(tmp_path) -> None:
    _, ctx, protocol, registry_ref = _build_gate_context(
        tmp_path,
        run_id="R_gate_replay_consumer_invalid",
    )
    state = ExperimentState(
        run_id="R_gate_replay_consumer_invalid",
        params={"require_human_gate": True},
        inputs={INPUT_REGISTRY_BUNDLE_REF: registry_ref},
    )
    malformed_ref = {
        "artifact_id": "malformed-but-present",
        "kind": "ir.trinity_bundle",
        "media_type": "application/json",
        "manifest_profile_sha256": "sha256:" + "a" * 64,
        "schema": {"name": "polisyos.ir.TrinityBundle", "version": "1.0"},
        "reported_hash": "sha256:" + "b" * 64,
    }
    state.inputs[INPUT_TRINITY_BUNDLE_REF] = malformed_ref
    issues: list[dict[str, object]] = []
    events = []

    verdict = _handle_initial_gate_request(
        ctx=ctx,
        protocol=protocol,
        state=state,
        verdict="approve",
        issues=issues,
        events=events,
    )

    request = GateRequest.model_validate(state.params["gate_request"])
    assert verdict == "human_gate"
    assert request.run_id == state.run_id
    assert request.context.replay_summary is not None
    assert request.context.replay_summary["readiness"] == "incomplete"
    assert request.context.replay_summary["invalid_refs"] == {
        INPUT_TRINITY_BUNDLE_REF: "malformed_ref"
    }
    assert INPUT_TRINITY_BUNDLE_REF not in request.context.replay_summary["missing_refs"]
    original_digests = request.context.replay_summary["invalid_input_digests"]
    assert set(original_digests) == {INPUT_TRINITY_BUNDLE_REF}
    assert original_digests[INPUT_TRINITY_BUNDLE_REF].startswith("sha256:")
    assert request.context.selected_replay_refs is not None
    assert INPUT_TRINITY_BUNDLE_REF not in request.context.selected_replay_refs
    assert "gate_decision_typed" not in state.params

    reordered_state = state.model_copy(deep=True)
    reordered_state.inputs[INPUT_TRINITY_BUNDLE_REF] = dict(reversed(list(malformed_ref.items())))
    reordered_request, _ = _create_gate_request(
        ctx=ctx,
        protocol=protocol,
        state=reordered_state,
    )
    assert reordered_request.request_id == request.request_id
    assert reordered_request.context.replay_summary["invalid_input_digests"] == original_digests

    tagged_raw_state = state.model_copy(deep=True)
    tagged_raw_state.inputs[INPUT_TRINITY_BUNDLE_REF] = dict(
        malformed_ref,
        extension={"_type": "float", "repr": "1"},
    )
    numeric_raw_state = state.model_copy(deep=True)
    numeric_raw_state.inputs[INPUT_TRINITY_BUNDLE_REF] = dict(
        malformed_ref,
        extension=1.0,
    )
    tagged_raw_request, _ = _create_gate_request(
        ctx=ctx,
        protocol=protocol,
        state=tagged_raw_state,
    )
    numeric_raw_request, _ = _create_gate_request(
        ctx=ctx,
        protocol=protocol,
        state=numeric_raw_state,
    )
    assert tagged_raw_request.request_id != numeric_raw_request.request_id

    state.params["gate_decision"] = {
        "request_id": request.request_id,
        "run_id": state.run_id,
        "verdict": "approve",
        "approver_id": "reviewer",
    }
    changed_malformed_ref = dict(
        malformed_ref,
        reported_hash="sha256:" + "c" * 64,
    )
    state.inputs[INPUT_TRINITY_BUNDLE_REF] = changed_malformed_ref
    changed_verdict = _handle_initial_gate_request(
        ctx=ctx,
        protocol=protocol,
        state=state,
        verdict="approve",
        issues=issues,
        events=events,
    )
    changed_request = GateRequest.model_validate(state.params["gate_request"])
    assert changed_verdict == "human_gate"
    assert changed_request.request_id != request.request_id
    assert (
        changed_request.context.replay_summary["invalid_input_digests"][INPUT_TRINITY_BUNDLE_REF]
        != original_digests[INPUT_TRINITY_BUNDLE_REF]
    )
    assert "gate_decision" not in state.params
    assert any(issue["code"] == "gate.request.unverified" for issue in issues)


def test_unrepresentable_malformed_replay_input_refuses_gate_request_identity(tmp_path) -> None:
    _, ctx, protocol, registry_ref = _build_gate_context(
        tmp_path,
        run_id="R_gate_replay_unrepresentable",
    )
    state = ExperimentState(
        run_id="R_gate_replay_unrepresentable",
        inputs={INPUT_REGISTRY_BUNDLE_REF: registry_ref},
    )
    state.inputs[INPUT_TRINITY_BUNDLE_REF] = object()

    with pytest.raises(
        ValueError,
        match="Cannot bind invalid replay input 'trinity_bundle_ref' to the gate request identity",
    ):
        _create_gate_request(ctx=ctx, protocol=protocol, state=state)


def test_replay_readiness_uses_selected_artifact_kind_schema_and_payload(tmp_path) -> None:
    store, ctx, _, registry_ref = _build_gate_context(
        tmp_path,
        run_id="R_gate_replay_contracts",
    )
    replay_refs = _build_valid_replay_inputs(store, registry_ref)
    all_inputs = dict(replay_refs)

    wrong_kind_state = ExperimentState(
        run_id="R_gate_replay_contracts",
        inputs=all_inputs.copy(),
    )
    wrong_kind_state.inputs[INPUT_KNOWLEDGE_BUNDLE_REF] = store.put_json(
        KnowledgeBundlePayloadV1(bundle_id="wrong-kind"),
        PutOptions(kind="test.not_knowledge_bundle", media_type="application/json"),
    )
    readiness, missing_refs, invalid_refs = _gate_replay_readiness(ctx, wrong_kind_state)
    assert readiness == "partial"
    assert INPUT_KNOWLEDGE_BUNDLE_REF not in missing_refs
    assert invalid_refs[INPUT_KNOWLEDGE_BUNDLE_REF] == "wrong_kind"

    dangling_state = ExperimentState(
        run_id="R_gate_replay_contracts",
        inputs=all_inputs.copy(),
    )
    dangling_state.inputs[INPUT_TRINITY_BUNDLE_REF] = ArtifactRef(
        artifact_id=ArtifactID("sha256:" + "f" * 64),
        kind="ir.trinity_bundle",
        media_type="application/json",
    )
    readiness, missing_refs, invalid_refs = _gate_replay_readiness(ctx, dangling_state)
    assert readiness == "incomplete"
    assert INPUT_TRINITY_BUNDLE_REF not in missing_refs
    assert invalid_refs[INPUT_TRINITY_BUNDLE_REF] == "unresolvable_ref_or_invalid_payload"

    trinity_payload = TrinityBundle.model_validate(
        from_canonical_bytes(store.get_bytes(replay_refs[INPUT_TRINITY_BUNDLE_REF]))
    ).model_copy(update={"compatible": False})
    wrong_schema_trinity = store.put_json(
        trinity_payload,
        PutOptions(
            kind="ir.trinity_bundle",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.test.TrinityBundle", version="9.9"),
        ),
    )
    wrong_schema_trinity_state = ExperimentState(
        run_id="R_gate_replay_contracts",
        inputs=all_inputs.copy(),
    )
    wrong_schema_trinity_state.inputs[INPUT_TRINITY_BUNDLE_REF] = wrong_schema_trinity
    readiness, _, invalid_refs = _gate_replay_readiness(ctx, wrong_schema_trinity_state)
    assert readiness == "incomplete"
    assert invalid_refs[INPUT_TRINITY_BUNDLE_REF] == "wrong_schema"

    registry_payload = RegistryBundlePayload.model_validate(
        from_canonical_bytes(store.get_bytes(registry_ref))
    ).model_copy(update={"metric_registry": None})
    wrong_schema_registry = store.put_json(
        registry_payload,
        PutOptions(
            kind="core.registry_bundle",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.test.RegistryBundlePayload", version="9.9"),
        ),
    )
    wrong_schema_registry_state = ExperimentState(
        run_id="R_gate_replay_contracts",
        inputs=all_inputs.copy(),
    )
    wrong_schema_registry_state.inputs[INPUT_REGISTRY_BUNDLE_REF] = wrong_schema_registry
    readiness, _, invalid_refs = _gate_replay_readiness(ctx, wrong_schema_registry_state)
    assert readiness == "incomplete"
    assert invalid_refs[INPUT_REGISTRY_BUNDLE_REF] == "wrong_schema"

    data_payload = DataSnapshot.model_validate(
        from_canonical_bytes(store.get_bytes(replay_refs[INPUT_DATA_SNAPSHOT_REF]))
    ).model_copy(update={"notes": ["wrong schema probe"]})
    wrong_schema_snapshot = store.put_json(
        data_payload,
        PutOptions(
            kind="fabric.data_snapshot",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.test.DataSnapshot", version="9.9"),
        ),
    )
    wrong_schema_snapshot_state = ExperimentState(
        run_id="R_gate_replay_contracts",
        inputs={
            INPUT_TRINITY_BUNDLE_REF: replay_refs[INPUT_TRINITY_BUNDLE_REF],
            INPUT_REGISTRY_BUNDLE_REF: registry_ref,
            INPUT_DATA_SNAPSHOT_REF: wrong_schema_snapshot,
        },
    )
    readiness, _, invalid_refs = _gate_replay_readiness(ctx, wrong_schema_snapshot_state)
    assert readiness == "incomplete"
    assert invalid_refs[INPUT_DATA_SNAPSHOT_REF] == "wrong_schema"

    reused_state = ExperimentState(run_id="R_gate_replay_other_run", inputs=all_inputs.copy())
    assert _gate_replay_readiness(ctx, reused_state) == ("complete", [], {})


def test_malformed_human_review_request_is_replaced_and_persisted_pair_is_reused(
    tmp_path,
) -> None:
    store, ctx, protocol, _ = _build_gate_context(
        tmp_path,
        run_id="R_gate_human_review_request",
    )
    state = ExperimentState(
        run_id="R_gate_human_review_request",
        params={
            "human_review_request": {"request_id": "missing-required-fields"},
            "human_review_request_ref": "not-an-artifact-id",
            "governance_profile": "strict",
            "human_review_phase": "POSTFLIGHT_GOV_REVIEW",
            "human_review_iteration": 3,
            "human_review_timeout_seconds": 120,
        },
    )
    pass_state = {
        "human_review_request": {
            "items": [
                {"kind": "legal_conflict"},
                {"kind": "legal_conflict"},
                {"kind": "rights_review"},
                "ignored_non_object",
            ]
        }
    }
    events = []

    _ensure_human_review_gate_request(
        ctx=ctx,
        protocol=protocol,
        state=state,
        pass_state=pass_state,
        events=events,
    )

    request_ref = ArtifactRef.model_validate(state.params["human_review_request_ref"])
    request = GateRequest.model_validate(from_canonical_bytes(store.get_bytes(request_ref)))
    assert request.reason == "strict_human_review"
    assert request.priority == GatePriority.HIGH
    assert request.timeout_seconds == 120
    assert request.context.governance_profile == "strict"
    assert request.context.phase == "POSTFLIGHT_GOV_REVIEW"
    assert request.context.iteration == 3
    assert request.context.risk_indicators == ["legal_conflict", "rights_review"]
    assert request.context.issue_summary == {
        "requested_items": 3,
        "risk_indicator_count": 2,
    }
    assert len(events) == 1

    _ensure_human_review_gate_request(
        ctx=ctx,
        protocol=protocol,
        state=state,
        pass_state=pass_state,
        events=events,
    )
    assert ArtifactRef.model_validate(state.params["human_review_request_ref"]) == request_ref
    assert len(events) == 1

    for field in ("request_id", "run_id", "context.phase"):
        altered_request = deepcopy(state.params["human_review_request"])
        target = altered_request
        if field == "context.phase":
            target = altered_request["context"]
            target["phase"] = "CONTRADICTORY_PHASE"
        else:
            target[field] = "contradictory-value"
        state.params["human_review_request"] = altered_request
        previous_event_count = len(events)
        _ensure_human_review_gate_request(
            ctx=ctx,
            protocol=protocol,
            state=state,
            pass_state=pass_state,
            events=events,
        )
        current_ref = ArtifactRef.model_validate(state.params["human_review_request_ref"])
        recovered = GateRequest.model_validate(from_canonical_bytes(store.get_bytes(current_ref)))
        assert recovered.model_dump(mode="json") == state.params["human_review_request"]
        assert recovered.run_id == state.run_id
        assert recovered.context.phase == "POSTFLIGHT_GOV_REVIEW"
        assert len(events) == previous_event_count + 1

    current_request = deepcopy(state.params["human_review_request"])
    other_state = state.model_copy(deep=True)
    other_state.params["phase"] = "OTHER_PHASE"
    foreign_request, foreign_ref = _create_gate_request(
        ctx=ctx,
        protocol=protocol,
        state=other_state,
    )
    assert foreign_request.context.phase == "OTHER_PHASE"
    state.params["human_review_request"] = current_request
    state.params["human_review_request_ref"] = foreign_ref.model_dump(mode="json")
    previous_event_count = len(events)
    _ensure_human_review_gate_request(
        ctx=ctx,
        protocol=protocol,
        state=state,
        pass_state=pass_state,
        events=events,
    )
    rebound_ref = ArtifactRef.model_validate(state.params["human_review_request_ref"])
    rebound = GateRequest.model_validate(from_canonical_bytes(store.get_bytes(rebound_ref)))
    assert rebound.model_dump(mode="json") == state.params["human_review_request"]
    assert rebound.context.phase == "POSTFLIGHT_GOV_REVIEW"
    assert len(events) == previous_event_count + 1


def test_initial_gate_decision_requires_a_current_persisted_request(tmp_path) -> None:
    _, ctx, protocol, _ = _build_gate_context(
        tmp_path,
        run_id="R_gate_decision_binding",
    )
    state = ExperimentState(
        run_id="R_gate_decision_binding",
        params={"require_human_gate": True},
    )
    issues: list[dict[str, object]] = []
    events = []
    pending = _handle_initial_gate_request(
        ctx=ctx,
        protocol=protocol,
        state=state,
        verdict="approve",
        issues=issues,
        events=events,
    )
    assert pending == "human_gate"
    gate_request = state.params["gate_request"]
    assert isinstance(gate_request, dict)

    state.params["gate_decision"] = {
        "request_id": "another-request",
        "run_id": state.run_id,
        "verdict": "approve",
        "approver_id": "reviewer",
    }
    mismatched = _handle_initial_gate_request(
        ctx=ctx,
        protocol=protocol,
        state=state,
        verdict="approve",
        issues=issues,
        events=events,
    )
    assert mismatched == "human_gate"
    assert any(issue["code"] == "gate.decision.request_mismatch" for issue in issues)
    assert "gate_decision_typed" not in state.params
    assert "gate_decision" not in state.params

    state.params["gate_decision"] = {
        "request_id": gate_request["request_id"],
        "run_id": state.run_id,
        "verdict": "approve",
        "approver_id": "reviewer",
    }
    approved = _handle_initial_gate_request(
        ctx=ctx,
        protocol=protocol,
        state=state,
        verdict="approve",
        issues=issues,
        events=events,
    )
    assert approved == "approve"
    assert state.params["gate_decision_typed"]["request_id"] == gate_request["request_id"]


def test_cross_run_gate_request_is_regenerated_before_decision_admission(tmp_path) -> None:
    store, first_ctx, first_protocol, registry_ref = _build_gate_context(
        tmp_path,
        run_id="R_gate_request_source",
    )
    original_state = ExperimentState(
        run_id="R_gate_request_source",
        params={"require_human_gate": True},
    )
    first_events = []
    _handle_initial_gate_request(
        ctx=first_ctx,
        protocol=first_protocol,
        state=original_state,
        verdict="approve",
        issues=[],
        events=first_events,
    )
    original_request = original_state.params["gate_request"]
    original_ref = original_state.params["gate_request_ref"]

    other_run = RunContext.start(
        store=store,
        registry_bundle=registry_ref,
        run_id="R_gate_request_other_run",
    )
    other_ctx = ExecutionContext(
        store=store,
        run=other_run,
        logger=logging.getLogger("test.governance.gate_request_other_run"),
    )
    other_state = ExperimentState(
        run_id="R_gate_request_other_run",
        params={
            "require_human_gate": True,
            "gate_request": original_request,
            "gate_request_ref": original_ref,
            "gate_decision": {
                "request_id": original_request["request_id"],
                "run_id": original_request["run_id"],
                "verdict": "approve",
                "approver_id": "reviewer",
            },
        },
    )
    other_protocol = HumanGateProtocol(other_run)
    issues: list[dict[str, object]] = []
    other_events = []
    verdict = _handle_initial_gate_request(
        ctx=other_ctx,
        protocol=other_protocol,
        state=other_state,
        verdict="approve",
        issues=issues,
        events=other_events,
    )

    current_request = GateRequest.model_validate(other_state.params["gate_request"])
    current_ref = ArtifactRef.model_validate(other_state.params["gate_request_ref"])
    persisted_request = GateRequest.model_validate(
        from_canonical_bytes(store.get_bytes(current_ref))
    )
    assert verdict == "human_gate"
    assert current_request.run_id == other_state.run_id
    assert persisted_request == current_request
    assert current_ref != original_ref
    assert "gate_decision" not in other_state.params
    assert any(issue["code"] == "gate.request.unverified" for issue in issues)


def test_selected_replay_view_change_reissues_request_and_discards_approval(tmp_path) -> None:
    store, ctx, protocol, default_registry_ref = _build_gate_context(
        tmp_path,
        run_id="R_gate_selected_view_change",
    )
    registry_payload = from_canonical_bytes(store.get_bytes(default_registry_ref))
    selected_registry_ref = store.put_json(
        registry_payload,
        PutOptions(
            kind="core.registry_bundle",
            media_type="application/json",
            producer=ProducerInfo(component="test.selected_registry_view", version="1.0.0"),
        ),
    )
    assert selected_registry_ref.artifact_id == default_registry_ref.artifact_id
    assert selected_registry_ref.manifest_profile_sha256 is not None

    state = ExperimentState(
        run_id="R_gate_selected_view_change",
        inputs={INPUT_REGISTRY_BUNDLE_REF: default_registry_ref},
        params={"require_human_gate": True},
    )
    issues: list[dict[str, object]] = []
    events = []
    assert (
        _handle_initial_gate_request(
            ctx=ctx,
            protocol=protocol,
            state=state,
            verdict="approve",
            issues=issues,
            events=events,
        )
        == "human_gate"
    )
    original_request = GateRequest.model_validate(state.params["gate_request"])
    assert original_request.context.selected_replay_refs is not None
    assert (
        original_request.context.selected_replay_refs[
            INPUT_REGISTRY_BUNDLE_REF
        ].manifest_profile_sha256
        == default_registry_ref.manifest_profile_sha256
    )
    state.params["gate_decision"] = {
        "request_id": original_request.request_id,
        "run_id": state.run_id,
        "verdict": "approve",
        "approver_id": "reviewer",
    }
    state.inputs[INPUT_REGISTRY_BUNDLE_REF] = selected_registry_ref

    verdict = _handle_initial_gate_request(
        ctx=ctx,
        protocol=protocol,
        state=state,
        verdict="approve",
        issues=issues,
        events=events,
    )

    current_request = GateRequest.model_validate(state.params["gate_request"])
    assert verdict == "human_gate"
    assert current_request.request_id != original_request.request_id
    assert current_request.context.selected_replay_refs is not None
    assert (
        current_request.context.selected_replay_refs[
            INPUT_REGISTRY_BUNDLE_REF
        ].manifest_profile_sha256
        == selected_registry_ref.manifest_profile_sha256
    )
    assert isinstance(state.params["gate_request_ref"], dict)
    assert "gate_decision" not in state.params
    assert any(issue["code"] == "gate.request.unverified" for issue in issues)


def test_legacy_gate_request_is_read_but_not_reused_for_a_decision(tmp_path) -> None:
    store, ctx, protocol, registry_ref = _build_gate_context(
        tmp_path,
        run_id="R_gate_legacy_request",
    )
    legacy_request = GateRequest(
        schema_version="1.1",
        request_id="legacy-gate-request",
        run_id="R_gate_legacy_request",
        reason="historical request",
        context=GateContext(
            workflow_id="scientist_default",
            node_alias="run_governance",
            phase="POSTFLIGHT_GOV",
        ),
    )
    legacy_ref = store.put_json(
        legacy_request.model_dump(mode="json"),
        PutOptions(
            kind="ir.gate_request",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.ir.GateRequest", version="1.1"),
        ),
    )
    loaded_legacy = GateRequest.model_validate(from_canonical_bytes(store.get_bytes(legacy_ref)))
    assert loaded_legacy.schema_version == "1.1"
    assert loaded_legacy.context.selected_replay_refs is None

    state = ExperimentState(
        run_id="R_gate_legacy_request",
        inputs={INPUT_REGISTRY_BUNDLE_REF: registry_ref},
        params={
            "require_human_gate": True,
            "gate_request": legacy_request.model_dump(mode="json"),
            "gate_request_ref": str(legacy_ref.artifact_id),
            "gate_decision": {
                "request_id": legacy_request.request_id,
                "run_id": legacy_request.run_id,
                "verdict": "approve",
                "approver_id": "reviewer",
            },
        },
    )
    issues: list[dict[str, object]] = []

    verdict = _handle_initial_gate_request(
        ctx=ctx,
        protocol=protocol,
        state=state,
        verdict="approve",
        issues=issues,
        events=[],
    )

    current_request = GateRequest.model_validate(state.params["gate_request"])
    assert verdict == "human_gate"
    assert current_request.schema_version == "1.2"
    assert current_request.request_id != legacy_request.request_id
    assert isinstance(state.params["gate_request_ref"], dict)
    assert "gate_decision" not in state.params
    assert any(issue["code"] == "gate.request.unverified" for issue in issues)


def _build_gate_context(
    tmp_path,
    *,
    run_id: str,
) -> tuple[FileSystemCAS, ExecutionContext, HumanGateProtocol, ArtifactRef]:
    store = FileSystemCAS(tmp_path)
    registry_ref = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(
        store=store,
        registry_bundle=registry_ref,
        run_id=run_id,
    )
    ctx = ExecutionContext(
        store=store,
        run=run,
        logger=logging.getLogger("test.governance.gate_requests"),
    )
    return store, ctx, HumanGateProtocol(run), registry_ref


def _build_valid_replay_inputs(
    store: FileSystemCAS,
    registry_ref: ArtifactRef,
) -> dict[str, ArtifactRef]:
    state_payload_ref = store.put_json(
        {"source": "controlled-replay-fixture"},
        PutOptions(
            kind="foundry.state_payload",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.foundry.StatePayload", version="0.1.0"),
        ),
    )
    state_snapshot = StateSnapshot(schema_version="2.0", state_ref=state_payload_ref)
    state_snapshot_ref = store.put_json(
        state_snapshot,
        PutOptions(
            kind="foundry.state_snapshot",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.StateSnapshot", version="1.0"),
        ),
    )
    typed_state_snapshot_ref = StateSnapshotRef(artifact_id=state_snapshot_ref.artifact_id)
    data_snapshot = DataSnapshot(data_ref=state_payload_ref)
    data_snapshot_ref = store.put_json(
        data_snapshot,
        PutOptions(
            kind="fabric.data_snapshot",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.DataSnapshot", version="0.2.0"),
        ),
    )
    typed_data_snapshot_ref = DataSnapshotRef(artifact_id=data_snapshot_ref.artifact_id)
    input_bindings = FoundryInputBindings(
        data_snapshot_ref=typed_data_snapshot_ref,
        registry_bundle_ref=registry_ref,
        bound_state_snapshot_ref=typed_state_snapshot_ref,
    )
    input_bindings_ref = store.put_json(
        input_bindings,
        PutOptions(
            kind="foundry.input_bindings",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.FoundryInputBindings", version="1.0"),
        ),
    )
    norm_pack_ref = store.put_json(
        NormPack(pack_id="replay_norm_pack", jurisdiction="test", norms=[]),
        PutOptions(
            kind="lex.norm_pack",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.ir.NormPack", version="1.0"),
        ),
    )
    knowledge_bundle_ref = store.put_json(
        KnowledgeBundlePayloadV1(bundle_id="controlled-replay-knowledge"),
        PutOptions(
            kind="scholar.knowledge_bundle",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.scholar.KnowledgeBundlePayloadV1", version="1.0"),
        ),
    )
    research_intent_ref = store.put_json(
        ResearchIntent(domain="labor"),
        PutOptions(
            kind="scholar.research_intent",
            media_type="application/json",
        ),
    )
    trinity = TrinityBundle(
        problem_frame=ProblemFrame(problem_id="problem_gate_replay", domain=ProblemDomain.FISCAL),
        policy_spec=PolicySpec(policy_id="policy_gate_replay"),
        model_spec=ModelSpec(
            model_id="model_gate_replay",
            data_snapshot_ref=str(typed_data_snapshot_ref.artifact_id),
            registry_bundle_ref=str(registry_ref.artifact_id),
        ),
    )
    trinity_ref = store.put_json(
        trinity,
        PutOptions(
            kind="ir.trinity_bundle",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.ir.TrinityBundle", version="1.0"),
        ),
    )
    return {
        INPUT_TRINITY_BUNDLE_REF: trinity_ref,
        INPUT_REGISTRY_BUNDLE_REF: registry_ref,
        INPUT_DATA_SNAPSHOT_REF: typed_data_snapshot_ref,
        INPUT_STATE_SNAPSHOT_REF: typed_state_snapshot_ref,
        INPUT_INPUT_BINDINGS_REF: FoundryInputBindingsRef(
            artifact_id=input_bindings_ref.artifact_id
        ),
        INPUT_NORM_PACK_REF: norm_pack_ref,
        INPUT_KNOWLEDGE_BUNDLE_REF: knowledge_bundle_ref,
        INPUT_RESEARCH_INTENT_REF: research_intent_ref,
    }
