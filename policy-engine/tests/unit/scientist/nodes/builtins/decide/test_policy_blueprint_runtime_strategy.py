from __future__ import annotations

import logging
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace

from polisyos.core.artifacts import artifact_manifest_profile_sha256
from polisyos.core.artifacts import ensure_ir_artifact_store as _ensure_ir_artifact_store
from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.ir.analytics.strategic import (
    FiniteStrategicPayoffTable,
    StrategicSCM,
    load_strategic_payoff_table,
    load_strategic_scm,
    persist_strategic_payoff_table,
)
from polisyos.ir.governance.policy_spec import (
    InterventionSpec,
    ParameterSpec,
    PolicySpec,
)
from polisyos.ir.governance.problem_frame import (
    ObjectiveSpec,
    ProblemDomain,
    ProblemFrame,
)
from polisyos.ir.governance.schedule import ScheduleSpec
from polisyos.ir.governance.selector_expr import SelectorPredicate
from polisyos.ir.model_layer.model_spec import ModelSpec
from polisyos.ir.model_layer.types import OptimizationDirection, SelectorOperator
from polisyos.ir.registry.refs import ArtifactRefModel
from polisyos.ir.trinity import TrinityBundle
from polisyos.scientist.methods.search.calibration_report import (
    FunnelCalibrationReport,
    load_funnel_calibration_report,
)
from polisyos.scientist.methods.search.stages import CorrelationTracker, StageResult
from polisyos.scientist.nodes.builtins.decide.policy_blueprint_runtime_strategy import (
    _candidate_search_payload,
    _ensure_calibration_report,
    _persist_runtime_strategic_artifacts,
    _resolve_runtime_correlation_tracker,
)
from polisyos.scientist.nodes.builtins.decide.policy_runtime_support import (
    persist_policy_evaluation_vector_to_store,
)
from polisyos.scientist.nodes.builtins.state_keys import ARTIFACT_CAUSAL_REPORT_REF
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.kernel.budgets import ComputeBudget
from polisyos.scientist.policy_design.objectives import PolicyEvaluationVector
from polisyos.scientist.policy_design.schema import (
    PolicyCandidateSchema,
    persist_policy_candidate_schema,
)


def _candidate() -> PolicyCandidateSchema:
    bundle = TrinityBundle(
        problem_frame=ProblemFrame(
            problem_id="problem_strategy_projection",
            domain=ProblemDomain.FISCAL,
            objectives=[
                ObjectiveSpec(
                    objective_id="employment_gain",
                    metric_id="employment",
                    direction=OptimizationDirection.MAXIMIZE,
                )
            ],
        ),
        policy_spec=PolicySpec(
            policy_id="policy_strategy_projection",
            interventions=[
                InterventionSpec(
                    intervention_id="income_support",
                    kind="cash_transfer",
                    target=SelectorPredicate(
                        field="region",
                        operator=SelectorOperator.EQUALS,
                        value="eligible",
                    ),
                    schedule=ScheduleSpec(start_step=0, duration_steps=1),
                    params={"amount": 100},
                )
            ],
            parameters=[
                ParameterSpec(
                    param_id="transfer_amount",
                    intervention_id="income_support",
                    param_path="amount",
                    default_value=100,
                    min_value=0,
                    max_value=500,
                )
            ],
        ),
        model_spec=ModelSpec(
            model_id="model_strategy_projection",
            data_snapshot_ref="sha256:" + "2" * 64,
        ),
    )
    return PolicyCandidateSchema.from_trinity_bundle(
        bundle,
        candidate_id="candidate_strategy_projection",
        metadata={"domain": "fiscal"},
    )


def _context(tmp_path: Path, run_id: str) -> ExecutionContext:
    store = FileSystemCAS(tmp_path / run_id)
    from polisyos.core.registry import build_default_registry_bundle
    from polisyos.core.run.context import RunContext

    registry_ref = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(store=store, registry_bundle=registry_ref, run_id=run_id)
    return ExecutionContext(
        store=store,
        run=run,
        logger=logging.getLogger(f"test.{run_id}"),
    )


def _artifact_ref(seed: str, *, kind: str) -> ArtifactRef:
    digest = sha256(seed.encode("utf-8")).hexdigest()
    return ArtifactRef(
        artifact_id=ArtifactID.model_validate(f"sha256:{digest}"),
        kind=kind,
        media_type="application/json",
    )


def _strategic_ref_model(seed: str, *, kind: str) -> ArtifactRefModel:
    digest = sha256(seed.encode("utf-8")).hexdigest()
    return ArtifactRefModel.model_validate(
        {
            "artifact_id": f"sha256:{digest}",
            "kind": kind,
            "media_type": "application/json",
        }
    )


def _payoff_tables() -> dict[str, FiniteStrategicPayoffTable]:
    action_spaces = {"leader": ("low", "high"), "follower": ("stay", "switch")}
    return {
        "leader": FiniteStrategicPayoffTable(
            agent="leader",
            strategic_agents=("leader", "follower"),
            action_spaces=action_spaces,
            payoffs={
                "leader=low|follower=stay": 1.0,
                "leader=low|follower=switch": 0.0,
                "leader=high|follower=stay": 2.0,
                "leader=high|follower=switch": 3.0,
            },
        ),
        "follower": FiniteStrategicPayoffTable(
            agent="follower",
            strategic_agents=("leader", "follower"),
            action_spaces=action_spaces,
            payoffs={
                "leader=low|follower=stay": 2.0,
                "leader=low|follower=switch": 1.0,
                "leader=high|follower=stay": 0.0,
                "leader=high|follower=switch": 3.0,
            },
        ),
    }


def test_candidate_search_payload_projects_typed_interventions_objectives_and_live_graph() -> None:
    candidate = _candidate()
    state = ExperimentState(
        run_id="run_strategy_payload",
        params={"causal_graph": {"nodes": ["income", "employment"]}},
    )

    first_payload = _candidate_search_payload(candidate, state)

    assert first_payload["semantic"]["interventions"] == [
        {
            "id": "income_support",
            "type": "cash_transfer",
            "variable": "amount",
            "parameters": {"amount": 100},
        }
    ]
    assert first_payload["semantic"]["objectives"] == [
        {"name": "employment_gain", "variable": "employment"}
    ]
    assert first_payload["causal_graph"] == {"nodes": ["income", "employment"]}
    assert first_payload["metadata"]["task_family"] == "policy"
    assert first_payload["metadata"]["domain"] == "fiscal"

    state.params["causal_graph"] = {"nodes": ["income", "employment", "budget"]}
    second_payload = _candidate_search_payload(candidate, state)
    assert first_payload["causal_graph"]["nodes"] == ["income", "employment"]
    assert second_payload["causal_graph"]["nodes"] == ["income", "employment", "budget"]


def test_calibration_projection_is_fresh_in_core_cas_without_ir_profile_claim(
    tmp_path: Path,
) -> None:
    ctx = _context(tmp_path, "run_strategy_calibration")
    state = ExperimentState(
        run_id="run_strategy_calibration",
        params={
            "correlation_metrics": {
                "sample_count": 0,
                "routing_mode": "no_promotion",
                "calibration_state": "not_established",
                "promotion_ban_active": False,
            }
        },
    )

    empty_ref = _ensure_calibration_report(ctx, state)
    empty_report = load_funnel_calibration_report(ctx.store, empty_ref)
    assert empty_report.current_mode == "no_promotion"
    assert empty_report.routing_health["sample_count"] == 0
    assert empty_report.routing_health["calibration_state"] == "not_established"
    empty_manifest = ctx.store.get_manifest(empty_ref)
    assert empty_ref.manifest_profile_sha256 is None
    assert empty_manifest.artifact_id == empty_ref.artifact_id
    assert empty_manifest.kind == "scientist.search.calibration_report"
    assert empty_manifest.artifact_schema is not None
    assert empty_manifest.artifact_schema.name == (
        "polisyos.scientist.search.FunnelCalibrationReport"
    )
    assert empty_manifest.inputs == []

    state.params["correlation_metrics"] = {
        "sample_count": 8,
        "routing_mode": "normal",
        "promotion_ban_active": False,
    }
    observed_ref = _ensure_calibration_report(ctx, state)
    observed_report = load_funnel_calibration_report(ctx.store, observed_ref)
    assert observed_report.current_mode == "normal"
    assert observed_report.routing_health["sample_count"] == 8
    assert observed_ref.artifact_id != empty_ref.artifact_id
    observed_manifest = ctx.store.get_manifest(observed_ref)
    assert observed_ref.manifest_profile_sha256 is None
    assert observed_manifest.artifact_id == observed_ref.artifact_id
    assert observed_manifest.kind == "scientist.search.calibration_report"
    assert observed_manifest.artifact_schema == empty_manifest.artifact_schema
    assert observed_manifest.inputs == []


def test_tracker_restore_uses_persisted_snapshot_and_rejects_malformed_snapshot() -> None:
    tracker = CorrelationTracker(drift_window_size=5)
    tracker.record(
        StageResult(
            policy_candidate={},
            objective_value=0.4,
            predicted_score=0.4,
            is_promising=True,
            stage_name="funnel_L2_causal",
        ),
        StageResult(
            policy_candidate={},
            objective_value=0.3,
            actual_score=0.3,
            is_promising=False,
            stage_name="funnel_L4_full",
        ),
        "candidate_strategy_tracker",
    )
    persisted_report = FunnelCalibrationReport(
        current_mode="normal",
        metadata={"correlation_tracker_snapshot": tracker.to_snapshot().model_dump(mode="json")},
    )

    restored = _resolve_runtime_correlation_tracker(persisted_report)
    malformed = _resolve_runtime_correlation_tracker(
        FunnelCalibrationReport(
            current_mode="normal",
            metadata={"correlation_tracker_snapshot": {"max_records": 1}},
        )
    )

    assert restored is not None
    assert restored.record_count == 1
    assert restored.records()[0].candidate_hash == "candidate_strategy_tracker"
    assert malformed is None


def test_strategic_receipt_rebinds_same_payoff_bytes_to_fresh_input_profile(tmp_path: Path) -> None:
    ctx = _context(tmp_path, "run_strategy_receipt")
    tables = _payoff_tables()
    old_refs = {
        agent: persist_strategic_payoff_table(ctx.store, table) for agent, table in tables.items()
    }
    contract = StrategicSCM(
        base_graph_ref=_strategic_ref_model("base-graph", kind="ir.causal_graph_model"),
        strategic_agents=("leader", "follower"),
        utility_refs=old_refs,
        policy_rule_ref=_strategic_ref_model("policy-rule", kind="ir.policy_recommendation"),
        equilibrium_concept="stackelberg",
        compute_budget=ComputeBudget(max_llm_calls=0.0, max_sim_runs=16.0, max_wall_time_s=30.0),
    )
    candidate_ref = persist_policy_candidate_schema(ctx.store, _candidate())
    state = ExperimentState(
        run_id="run_strategy_receipt",
        params={
            "strategic_scm": contract.model_dump(mode="json"),
            "strategic_payoff_tables": {
                agent: table.model_dump(mode="json") for agent, table in tables.items()
            },
        },
        artifacts_index={
            ARTIFACT_CAUSAL_REPORT_REF: _artifact_ref(
                "causal-report", kind="scientist.causal_effect_report"
            )
        },
    )
    first_evidence_ref = persist_policy_evaluation_vector_to_store(
        ctx.store,
        candidate_ref=candidate_ref,
        evaluation_vector=PolicyEvaluationVector(
            candidate_id="candidate_strategy_projection",
            feasible=True,
            metadata={"selection_generation": 1},
        ),
    )
    second_evidence_ref = persist_policy_evaluation_vector_to_store(
        ctx.store,
        candidate_ref=candidate_ref,
        evaluation_vector=PolicyEvaluationVector(
            candidate_id="candidate_strategy_projection",
            feasible=True,
            metadata={"selection_generation": 2},
        ),
    )

    first = _persist_runtime_strategic_artifacts(
        ctx,
        state,
        candidate_ref=candidate_ref,
        selection_vector_ref=first_evidence_ref,
        selection_artifact=SimpleNamespace(simulation_results={"policy_value": 2.0}),
        artifacts_index=dict(state.artifacts_index),
    )
    second = _persist_runtime_strategic_artifacts(
        ctx,
        state,
        candidate_ref=candidate_ref,
        selection_vector_ref=second_evidence_ref,
        selection_artifact=SimpleNamespace(simulation_results={"policy_value": 2.0}),
        artifacts_index=dict(state.artifacts_index),
    )

    assert first.strategic_scm_ref is not None
    assert second.strategic_scm_ref is not None
    ir_store = _ensure_ir_artifact_store(ctx.store)
    first_contract = load_strategic_scm(ir_store, first.strategic_scm_ref)
    second_contract = load_strategic_scm(ir_store, second.strategic_scm_ref)
    first_ref = first_contract.utility_refs["leader"]
    second_ref = second_contract.utility_refs["leader"]
    assert first_ref.artifact_id == second_ref.artifact_id == old_refs["leader"].artifact_id
    assert first_ref.manifest_profile_sha256 not in {
        None,
        old_refs["leader"].manifest_profile_sha256,
    }
    assert second_ref.manifest_profile_sha256 not in {
        None,
        first_ref.manifest_profile_sha256,
    }
    assert load_strategic_payoff_table(ir_store, first_ref) == tables["leader"]
    assert load_strategic_payoff_table(ir_store, second_ref) == tables["leader"]

    first_manifest = ctx.store.get_manifest_by_profile(
        first_ref.artifact_id,
        first_ref.manifest_profile_sha256,
    )
    second_manifest = ctx.store.get_manifest_by_profile(
        second_ref.artifact_id,
        second_ref.manifest_profile_sha256,
    )
    for manifest, evidence_ref, expected_profile in (
        (first_manifest, first_evidence_ref, first_ref.manifest_profile_sha256),
        (second_manifest, second_evidence_ref, second_ref.manifest_profile_sha256),
    ):
        assert artifact_manifest_profile_sha256(manifest) == expected_profile
        assert {(str(item.artifact_id), item.role) for item in manifest.inputs} == {
            (str(candidate_ref.artifact_id), "candidate"),
            (str(evidence_ref.artifact_id), "policy_evaluation"),
        }
