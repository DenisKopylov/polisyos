from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from polisyos.core.artifacts import (
    ArtifactRef,
    artifact_manifest_profile_sha256,
    resolve_manifest_by_profile,
)
from polisyos.core.artifacts.manifest import InputRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.contracts.execution_plan import (
    ExecutionPlan,
    ExecutionPlanRef,
    MethodCatalogEntry,
    MethodCatalogSnapshot,
    MethodCatalogSnapshotRef,
    MethodDagNode,
)
from polisyos.foundry.methods.catalog.snapshot import persist_method_catalog_snapshot
from polisyos.ir.governance.policy_spec import PolicySpec
from polisyos.ir.governance.problem_frame import ProblemDomain, ProblemFrame
from polisyos.ir.model_layer.model_spec import ModelSpec
from polisyos.ir.trinity import TrinityBundle
from polisyos.scientist.methods.search.funnel.types import FunnelExecutedWorkPacket
from polisyos.scientist.methods.search.uncertainty import (
    SearchInputDependency,
    _validate_search_owner_task_context,
    reconcile_search_method_selection_sources,
)
from polisyos.scientist.nodes.builtins.decide.policy_blueprint_runtime_engine import (
    _build_search_uncertainty_owner_context,
    _persist_policy_runtime_work_packet,
)
from polisyos.scientist.nodes.builtins.decide.policy_runtime_support import (
    PolicyRuntimeEvaluationArtifact,
    PolicyRuntimeProvenance,
)
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.llm.cycle import persist_execution_plan
from polisyos.scientist.policy_design.objectives import PolicyEvaluationVector
from polisyos.scientist.policy_design.schema import (
    PolicyCandidateSchema,
    persist_policy_candidate_schema,
)


def _candidate(candidate_id: str) -> PolicyCandidateSchema:
    return PolicyCandidateSchema.from_trinity_bundle(
        TrinityBundle(
            problem_frame=ProblemFrame(
                problem_id=f"problem_{candidate_id}",
                domain=ProblemDomain.FISCAL,
            ),
            policy_spec=PolicySpec(policy_id=f"policy_{candidate_id}"),
            model_spec=ModelSpec(
                model_id=f"model_{candidate_id}",
                data_snapshot_ref="sha256:" + "1" * 64,
            ),
        ),
        candidate_id=candidate_id,
    )


def _runtime_artifact(
    candidate: PolicyCandidateSchema, fidelity: str
) -> PolicyRuntimeEvaluationArtifact:
    runtime_invocation = {
        "evaluation_attempt_id": f"attempt:{fidelity}",
        "requested_draw_count": 17,
        "requested_draw_source": "effective_estimation_config",
        "effective_estimation_config_sha256": "c" * 64,
    }
    vector = PolicyEvaluationVector(
        candidate_id=candidate.candidate_id,
        feasible=True,
        metadata={
            "fidelity_observed": fidelity,
            "policy_runtime_invocation": runtime_invocation,
            "policy_runtime_fiscal_measurement": {
                "usable": False,
                "normalized_value": None,
                "source_values": {},
            },
        },
    )
    provenance = PolicyRuntimeProvenance(
        backend_kind="typed_work_packet_fixture",
        fidelity_mode=fidelity,
        promotable_source=False,
        notes=("Test fixture; no scientific draw loop is exercised.",),
    )
    return PolicyRuntimeEvaluationArtifact(
        simulation_metrics={"gdp_change": 0.2},
        simulation_results={
            "gdp_change": 0.2,
            "budget_deficit_objective_usable": False,
            "budget_deficit_objective_value": None,
            "bootstrap": {
                **runtime_invocation,
                "draw_execution_status": "not_instrumented",
                "attempted_draw_count": None,
                "successful_draw_count": None,
                "failed_draw_count": None,
                "unattempted_draw_count": None,
            },
        },
        evaluation_vector=vector,
        fidelity=fidelity,
        provenance=provenance,
    )


def _initial_state(store: FileSystemCAS, candidate_ref, *, run_id: str) -> dict[str, Any]:
    return {
        "store": store,
        "policy_candidate_ref": candidate_ref,
        "pinned_input_signature": f"signature:{run_id}",
        "policy_runtime_work_identity": {
            "candidate_ref": candidate_ref,
            "run_id": run_id,
            "ticket_id": f"ticket:{run_id}",
            "candidate_hash": f"candidate-hash:{run_id}",
        },
    }


@pytest.mark.parametrize(
    ("fidelity", "stage_level", "stage_name"),
    [
        ("medium", 3, "funnel_L3_medium"),
        ("full", 4, "funnel_L4_full"),
    ],
)
def test_engine_persists_typed_work_packet_with_candidate_and_result_cas_lineage(
    tmp_path: Path,
    fidelity: str,
    stage_level: int,
    stage_name: str,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    candidate = _candidate("candidate_engine_positive")
    candidate_ref = persist_policy_candidate_schema(store, candidate)

    packet_ref, unavailable_reason = _persist_policy_runtime_work_packet(
        initial_state=_initial_state(store, candidate_ref, run_id="run_engine_positive"),
        fidelity=fidelity,
        evaluation_attempt_id=f"attempt:{fidelity}",
        runtime_artifact=_runtime_artifact(candidate, fidelity),
    )

    assert unavailable_reason is None
    assert packet_ref is not None
    packet = FunnelExecutedWorkPacket.model_validate(
        from_canonical_bytes(store.get_bytes(packet_ref))
    )
    assert packet.run_id == "run_engine_positive"
    assert packet.ticket_id == "ticket:run_engine_positive"
    assert packet.candidate_hash == "candidate-hash:run_engine_positive"
    assert packet.candidate_ref.artifact_id == candidate_ref.artifact_id
    assert (packet.stage_level, packet.stage_name, packet.fidelity) == (
        stage_level,
        stage_name,
        fidelity,
    )
    assert packet.input_signature == "signature:run_engine_positive"
    assert packet.schema_version == "1.1"
    assert packet.requested_draw_count == 17
    assert packet.requested_draw_source == "effective_estimation_config"
    assert packet.effective_estimation_config_sha256 == "c" * 64
    assert packet.draw_execution_status == "not_instrumented"
    assert packet.attempted_draw_count is None
    assert packet.successful_draw_count is None
    # Honor each producer's persisted selector instead of requiring both refs to
    # carry an explicit manifest profile.
    result_profile = packet.source_result_ref.manifest_profile_sha256
    assert result_profile is not None
    result_manifest = resolve_manifest_by_profile(
        store, packet.source_result_ref.artifact_id, result_profile
    )
    assert result_profile == artifact_manifest_profile_sha256(result_manifest)

    packet_profile = packet_ref.manifest_profile_sha256
    if packet_profile is None:
        packet_manifest = store.get_manifest(packet_ref)
    else:
        packet_manifest = resolve_manifest_by_profile(store, packet_ref.artifact_id, packet_profile)
        assert packet_profile == artifact_manifest_profile_sha256(packet_manifest)

    result_payload = from_canonical_bytes(store.get_bytes(packet.source_result_ref))
    assert result_payload["candidate_id"] == candidate.candidate_id
    assert result_payload["metadata"]["fidelity_observed"] == fidelity
    assert (
        result_payload["metadata"]["policy_runtime_invocation"]["evaluation_attempt_id"]
        == f"attempt:{fidelity}"
    )
    assert result_manifest.artifact_id == packet.source_result_ref.artifact_id
    assert packet_manifest.artifact_id == packet_ref.artifact_id
    assert result_manifest.kind == "scientist.policy_evaluation_vector"
    assert packet_manifest.kind == "scientist.search.funnel_native_work_packet"
    assert any(
        item.artifact_id == candidate_ref.artifact_id and item.role == "candidate"
        for item in result_manifest.inputs
    )
    assert {(str(item.artifact_id), item.role) for item in packet_manifest.inputs} == {
        (str(candidate_ref.artifact_id), "candidate"),
        (str(packet.source_result_ref.artifact_id), "source_result"),
    }


def test_engine_rejects_candidate_ref_drift_before_any_cas_write(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    selected_candidate = _candidate("candidate_engine_selected")
    other_candidate = _candidate("candidate_engine_other")
    selected_ref = persist_policy_candidate_schema(store, selected_candidate)
    other_ref = persist_policy_candidate_schema(store, other_candidate)
    initial_state = _initial_state(store, selected_ref, run_id="run_engine_mismatch")
    initial_state["policy_runtime_work_identity"]["candidate_ref"] = other_ref
    artifacts_before = _artifact_id_snapshot(store)

    packet_ref, unavailable_reason = _persist_policy_runtime_work_packet(
        initial_state=initial_state,
        fidelity="full",
        evaluation_attempt_id="attempt:mismatched-candidate",
        runtime_artifact=_runtime_artifact(selected_candidate, "full"),
    )

    assert packet_ref is None
    assert unavailable_reason == "candidate_ref_unavailable_or_mismatched"
    assert _artifact_id_snapshot(store) == artifacts_before


def test_engine_does_not_publish_selection_as_an_executed_work_packet(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    candidate = _candidate("candidate_engine_selection")
    candidate_ref = persist_policy_candidate_schema(store, candidate)
    artifacts_before = _artifact_id_snapshot(store)

    packet_ref, unavailable_reason = _persist_policy_runtime_work_packet(
        initial_state=_initial_state(store, candidate_ref, run_id="run_engine_selection"),
        fidelity="selection",
        evaluation_attempt_id="attempt:selection",
        runtime_artifact=_runtime_artifact(candidate, "selection"),
    )

    assert packet_ref is None
    assert unavailable_reason == "unsupported_fidelity"
    assert _artifact_id_snapshot(store) == artifacts_before


def test_search_owner_context_carries_all_selected_top_level_state_artifact_refs(
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    candidate = _candidate("candidate_search_owner_state_refs")
    candidate_ref = persist_policy_candidate_schema(store, candidate, return_selected_profile=True)
    method_fqn = "polisyos.methods.example.Estimator"
    method_params = {"regularization": "0.2"}
    plan = ExecutionPlan(
        plan_id="plan-owner-context",
        run_id="run_search_owner_state_refs",
        method_dag=[
            MethodDagNode(
                node_id="selected-estimator",
                method_fqn=method_fqn,
                method_version="1.0.0",
                params=method_params,
            )
        ],
    )
    catalog = MethodCatalogSnapshot(
        snapshot_id="catalog-owner-context",
        run_id="run_search_owner_state_refs",
        entries=[
            MethodCatalogEntry(
                fqn=method_fqn,
                namespace="polisyos.methods.example",
                name="Estimator",
                version="1.0.0",
                backend="python",
                execution_backend="python",
                kind="causal",
                family="estimator",
                variant="default",
                fidelity_tier="standard",
            )
        ],
    )
    plan_ref = persist_execution_plan(store, plan)
    catalog_ref = persist_method_catalog_snapshot(store, catalog)
    history_probe_ref = store.put_json(
        {"history_probe": "selected_input"},
        PutOptions(
            kind="test.history_probe",
            media_type="application/json",
            schema=SchemaInfo(name="test.HistoryProbe", version="1.0"),
        ),
        return_selected_profile=True,
    )
    assert history_probe_ref.manifest_profile_sha256 is not None
    history_input = InputRef(
        artifact_id=history_probe_ref.artifact_id,
        role="same_bytes_new_manifest_view",
        manifest_profile_sha256=history_probe_ref.manifest_profile_sha256,
    )
    rewritten_plan_ref = persist_execution_plan(store, plan, inputs=[history_input])
    rewritten_catalog_ref = persist_method_catalog_snapshot(store, catalog, inputs=[history_input])
    assert plan_ref.artifact_id == rewritten_plan_ref.artifact_id
    assert plan_ref.manifest_profile_sha256 != rewritten_plan_ref.manifest_profile_sha256
    assert catalog_ref.artifact_id == rewritten_catalog_ref.artifact_id
    assert catalog_ref.manifest_profile_sha256 != rewritten_catalog_ref.manifest_profile_sha256
    assert store.get_manifest(plan_ref).inputs == []
    assert store.get_manifest(catalog_ref).inputs == []
    assert (
        store.get_manifest(rewritten_plan_ref).inputs[0].manifest_profile_sha256
        == history_probe_ref.manifest_profile_sha256
    )
    assert (
        store.get_manifest(rewritten_catalog_ref).inputs[0].manifest_profile_sha256
        == history_probe_ref.manifest_profile_sha256
    )
    assert store.get_manifest(plan_ref).kind == "scientist.execution_plan"
    assert store.get_manifest(catalog_ref).kind == "foundry.method_catalog_snapshot"

    def selected_ref(kind: str, name: str, *, profiled: bool = True) -> ArtifactRef:
        return store.put_json(
            {"owner_context_ref": name},
            PutOptions(
                kind=kind,
                media_type="application/json",
                schema=SchemaInfo(name=f"test.{name}", version="1.0"),
            ),
            return_selected_profile=profiled,
        )

    capability_ref = selected_ref("ir.causal_capability_contract", "CausalCapabilityContract")
    preflight_ref = selected_ref("scientist.preflight_report", "PreflightReport")
    evaluator_ref = selected_ref("scientist.evaluator_report", "EvaluatorReport")
    iteration_ref = selected_ref("scientist.iteration_state", "IterationState", profiled=False)
    reproducibility_ref = selected_ref(
        "scientist.reproducibility_manifest", "ReproducibilityManifest"
    )
    policy_request_ref = selected_ref("scientist.policy_request", "PolicyRequest")
    legal_source_pack_ref = selected_ref("legal.source_pack", "LegalSourcePack")
    state_input_ref = selected_ref("test.state_input", "StateInput")
    state_artifact_ref = selected_ref("test.state_artifact", "StateArtifact")
    state_report_ref = selected_ref("test.state_report", "StateReport")
    state = ExperimentState(
        run_id="run_search_owner_state_refs",
        execution_plan_ref=plan_ref,
        method_catalog_snapshot_ref=catalog_ref,
        causal_capability_contract_ref=capability_ref,
        preflight_report_ref=preflight_ref,
        evaluator_report_ref=evaluator_ref,
        iteration_state_ref=iteration_ref,
        reproducibility_manifest_ref=reproducibility_ref,
        policy_request_ref=policy_request_ref,
        legal_source_pack_ref=legal_source_pack_ref,
        causal_method_fqn=method_fqn,
        causal_method_params=method_params,
        execution_profile="workflow-profile-only",
        inputs={"selected_dataset": state_input_ref},
        artifacts_index={"method_result": state_artifact_ref},
        reports_index={"selection_report": state_report_ref},
    )
    session_context = SimpleNamespace(
        store=store,
        run=SimpleNamespace(tenant_id="tenant-owner-context", cell_id="cell-owner-context"),
    )

    def make_session(selected_state: ExperimentState) -> SimpleNamespace:
        return SimpleNamespace(
            ctx=session_context,
            state=selected_state,
            runtime_request=SimpleNamespace(),
            candidate_ref=candidate_ref,
            selection_ref=None,
        )

    stage = SimpleNamespace(stage_name="funnel_L0_static", fidelity_level=0)

    context = _build_search_uncertainty_owner_context(make_session(state), [stage])

    assert context.status == "not_established"
    assert context.selected_method_fqn == "polisyos.methods.example.Estimator"
    assert context.selected_method_params == {"regularization": "0.2"}
    assert context.selected_method_abi_version is None
    assert context.semantic_scope is None
    assert context.selected_profile_ref is None
    assert context.selected_rule_ref is None
    assert context.selected_procedure_ref is None
    assert context.selected_inference_profile_id is None
    assert {
        "owned_hte_request_projection",
        "selected_method_seed",
        "selected_method_input_owner",
        "selected_method_input_content_digest",
        "selected_method_abi_params_profile",
        "selected_inference_profile_owner",
        "selected_source_ref_manifest_profile:state.iteration_state_ref",
    }.issubset(context.missing_slices)
    source_graph = from_canonical_bytes(store.get_bytes(context.selected_source_graph_ref))
    selected_roles = {item["role_path"] for item in source_graph["roots"]}
    assert {
        "state.causal_capability_contract_ref",
        "state.preflight_report_ref",
        "state.evaluator_report_ref",
        "state.reproducibility_manifest_ref",
        "state.policy_request_ref",
        "state.legal_source_pack_ref",
        "state_input.selected_dataset",
        "state_artifact.method_result",
        "state_report.selection_report",
        "method_catalog_snapshot",
        "state.method_catalog_snapshot_ref",
        "execution_plan",
    }.issubset(selected_roles)
    assert "state.iteration_state_ref" not in selected_roles
    selected_by_role = {item["role_path"]: item["ref"] for item in source_graph["roots"]}
    assert (
        selected_by_role["execution_plan"]["manifest_profile_sha256"]
        == plan_ref.manifest_profile_sha256
    )
    assert (
        selected_by_role["method_catalog_snapshot"]["manifest_profile_sha256"]
        == catalog_ref.manifest_profile_sha256
    )
    assert context.selected_inference_profile_id != state.execution_profile
    assert _validate_search_owner_task_context(store, context) == ()

    absent_node_plan_ref = persist_execution_plan(
        store,
        plan.model_copy(update={"method_dag": []}),
    )
    absent_node_context = _build_search_uncertainty_owner_context(
        make_session(state.model_copy(update={"execution_plan_ref": absent_node_plan_ref})),
        [stage],
    )
    assert "selected_method_plan_node_unique" in absent_node_context.missing_slices
    assert "selected_method_plan_catalog_content_join" in absent_node_context.missing_slices
    assert _validate_search_owner_task_context(store, absent_node_context) == tuple(
        sorted(
            {
                "selected_method_plan_node_unique",
                "selected_method_plan_catalog_content_join",
            }
        )
    )

    mismatched_version_plan_ref = persist_execution_plan(
        store,
        plan.model_copy(
            update={
                "method_dag": [plan.method_dag[0].model_copy(update={"method_version": "2.0.0"})]
            }
        ),
    )
    mismatched_version_context = _build_search_uncertainty_owner_context(
        make_session(state.model_copy(update={"execution_plan_ref": mismatched_version_plan_ref})),
        [stage],
    )
    assert "selected_method_plan_catalog_version_match" in mismatched_version_context.missing_slices

    unversioned_plan_ref = persist_execution_plan(
        store,
        plan.model_copy(
            update={"method_dag": [plan.method_dag[0].model_copy(update={"method_version": None})]}
        ),
    )
    unversioned_context = _build_search_uncertainty_owner_context(
        make_session(state.model_copy(update={"execution_plan_ref": unversioned_plan_ref})),
        [stage],
    )
    assert "selected_method_plan_catalog_version_match" in unversioned_context.missing_slices

    drifted_context = context.model_copy(update={"selected_plan_ref": rewritten_plan_ref})
    with pytest.raises(ValueError, match="selected Search source graph differs"):
        _validate_search_owner_task_context(store, drifted_context)

    malformed_profile_ref = plan_ref.model_copy(
        update={"manifest_profile_sha256": "sha256:malformed"}
    )
    malformed_context = context.model_copy(update={"selected_plan_ref": malformed_profile_ref})
    with pytest.raises((TypeError, ValueError)):
        _validate_search_owner_task_context(store, malformed_context)

    legacy_state = state.model_copy(
        update={
            "execution_plan_ref": ExecutionPlanRef(artifact_id=plan_ref.artifact_id),
            "method_catalog_snapshot_ref": MethodCatalogSnapshotRef(
                artifact_id=catalog_ref.artifact_id
            ),
        }
    )
    legacy_context = _build_search_uncertainty_owner_context(make_session(legacy_state), [stage])
    assert legacy_context.status == "not_established"
    assert legacy_context.selected_plan_ref is None
    assert "selected_source_ref_manifest_profile:execution_plan" in legacy_context.missing_slices
    assert "selected_source_ref_manifest_profile:method_catalog_snapshot" in (
        legacy_context.missing_slices
    )
    legacy_missing = _validate_search_owner_task_context(store, legacy_context)
    assert "selected_execution_plan_owner" in legacy_missing
    assert "selected_method_catalog_owner" in legacy_missing


@pytest.mark.parametrize(
    ("plan_run_id", "catalog_run_id"),
    [
        ("run-other", "run-search-owner-scope"),
        ("run-search-owner-scope", "run-other"),
    ],
)
def test_search_owner_context_rejects_plan_or_catalog_from_another_run(
    tmp_path: Path,
    plan_run_id: str,
    catalog_run_id: str,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    run_id = "run-search-owner-scope"
    candidate = _candidate("search_owner_scope")
    candidate_ref = persist_policy_candidate_schema(
        store,
        candidate,
        return_selected_profile=True,
    )
    method_fqn = "polisyos.methods.example.Estimator"
    params = {"regularization": "0.2"}
    plan_ref = persist_execution_plan(
        store,
        ExecutionPlan(
            plan_id="plan-owner-scope",
            run_id=plan_run_id,
            method_dag=[
                MethodDagNode(
                    node_id="selected-estimator",
                    method_fqn=method_fqn,
                    method_version="1.0.0",
                    params=params,
                )
            ],
        ),
    )
    catalog_ref = persist_method_catalog_snapshot(
        store,
        MethodCatalogSnapshot(
            snapshot_id="catalog-owner-scope",
            run_id=catalog_run_id,
            entries=[
                MethodCatalogEntry(
                    fqn=method_fqn,
                    namespace="polisyos.methods.example",
                    name="Estimator",
                    version="1.0.0",
                    backend="python",
                    execution_backend="python",
                    kind="causal",
                    family="estimator",
                    variant="default",
                    fidelity_tier="standard",
                )
            ],
        ),
    )
    selection_ref = store.put_json(
        {"selected": True},
        PutOptions(kind="scientist.policy_selection", media_type="application/json"),
        return_selected_profile=True,
    )
    state = ExperimentState(
        run_id=run_id,
        execution_plan_ref=plan_ref,
        method_catalog_snapshot_ref=catalog_ref,
        causal_method_fqn=method_fqn,
        causal_method_params=params,
    )
    session = SimpleNamespace(
        ctx=SimpleNamespace(
            store=store,
            run=SimpleNamespace(tenant_id="tenant-owner-scope", cell_id=None),
        ),
        state=state,
        selection_ref=selection_ref,
        candidate_ref=candidate_ref,
    )
    context = _build_search_uncertainty_owner_context(
        session,
        [SimpleNamespace(stage_name="funnel_L0_static", fidelity_level=0)],
    )

    assert context.status == "not_established"
    assert ("selected_execution_plan_run_scope_match" in context.missing_slices) is (
        plan_run_id != run_id
    )
    assert ("selected_method_catalog_run_scope_match" in context.missing_slices) is (
        catalog_run_id != run_id
    )


def test_search_method_join_accepts_versioned_fqn_when_node_version_is_omitted(
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    method_fqn = "polisyos.methods.example.Estimator@1.0.0"
    plan_ref = persist_execution_plan(
        store,
        ExecutionPlan(
            plan_id="plan-versioned-fqn",
            run_id="run-versioned-fqn",
            method_dag=[
                MethodDagNode(
                    node_id="selected-estimator",
                    method_fqn=method_fqn,
                    params={"regularization": "0.2"},
                )
            ],
        ),
    )
    catalog_ref = persist_method_catalog_snapshot(
        store,
        MethodCatalogSnapshot(
            snapshot_id="catalog-versioned-fqn",
            run_id="run-versioned-fqn",
            entries=[
                MethodCatalogEntry(
                    fqn=method_fqn,
                    namespace="polisyos.methods.example",
                    name="Estimator",
                    version="1.0.0",
                    backend="python",
                    execution_backend="python",
                    kind="causal",
                    family="estimator",
                    variant="default",
                    fidelity_tier="standard",
                )
            ],
        ),
    )

    missing = reconcile_search_method_selection_sources(
        store,
        expected_run_id="run-versioned-fqn",
        plan_ref=plan_ref,
        selected_state_input_refs=(
            SearchInputDependency(role_path="method_catalog_snapshot", ref=catalog_ref),
        ),
        selected_method_fqn=method_fqn,
        selected_method_params={"regularization": "0.2"},
    )

    assert "selected_method_plan_catalog_version_match" not in missing


def _artifact_id_snapshot(store: FileSystemCAS) -> tuple[str, ...]:
    return tuple(sorted(str(artifact_id) for artifact_id in store.iter_artifact_ids()))
