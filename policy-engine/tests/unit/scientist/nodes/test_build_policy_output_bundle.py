from __future__ import annotations

import logging
import os
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import NoReturn
from unittest.mock import patch

import pytest

from polisyos.core.artifacts import ensure_ir_artifact_store as _ensure_ir_artifact_store
from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.contracts.scientist import GovernanceAccountabilityArtifactRef
from polisyos.ir.analytics.decision_layer import (
    SocialWeightManifestArtifact,
    build_optimization_ambiguity_certificate,
    persist_optimization_ambiguity_certificate,
    persist_social_weight_manifest,
)
from polisyos.ir.analytics.welfare import (
    GEUncertaintyBundle,
    GEUncertaintyRepresentation,
    WelfareBundle,
    WelfareIntervalSemantics,
    WelfareMethod,
    WelfareStatus,
    persist_ge_uncertainty_bundle,
    persist_welfare_bundle,
)
from polisyos.ir.governance.policy_spec import InterventionSpec, ParameterSpec, PolicySpec
from polisyos.ir.governance.problem_frame import (
    ConstraintSpec,
    ConstraintType,
    ObjectiveSpec,
    ProblemDomain,
    ProblemFrame,
)
from polisyos.ir.kernel.values import MoneyValue
from polisyos.ir.model_layer.model_spec import AssumptionSpec, AssumptionType, ModelSpec
from polisyos.ir.model_layer.types import OptimizationDirection, SelectorOperator
from polisyos.ir.registry.refs import ArtifactRefModel
from polisyos.ir.trinity import TrinityBundle
from polisyos.scientist.evidence.claims.head_index import (
    ClaimLedgerOwnerPort,
    build_default_claim_ledger_owner,
)
from polisyos.scientist.governance.backtest_matrix import BacktestKind, BacktestMatrixResult
from polisyos.scientist.governance.calibration_leaderboard import (
    CalibrationLeaderboardEntry,
    CalibrationLeaderboardMetrics,
)
from polisyos.scientist.governance.calibration_validation import (
    CalibrationValidationBundle,
    persist_calibration_validation_bundle,
)
from polisyos.scientist.governance.stress_scenarios import StressScenarioKind, StressScenarioResult
from polisyos.scientist.methods.search import (
    ActionableSideInformation,
    persist_actionable_side_information,
)
from polisyos.scientist.methods.search.funnel.orchestrator import FunnelOutcome
from polisyos.scientist.methods.search.funnel.types import FunnelStageResult, UncertaintyEnvelope
from polisyos.scientist.methods.search.readiness import DecisionReadiness, DecisionReadinessContract
from polisyos.scientist.nodes.builtins.decide.build_decision_packet import BuildDecisionPacketNode
from polisyos.scientist.nodes.builtins.decide.build_policy_output_bundle import (
    BuildPolicyOutputBundleNode,
    _dedupe_artifact_refs,
    _resolve_candidate,
)
from polisyos.scientist.nodes.builtins.planning.run_hierarchical_policy_search import (
    _persist_frontier_report,
)
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_CALIBRATION_VALIDATION_BUNDLE_REF,
    ARTIFACT_CAUSAL_ENVELOPE_REF,
    ARTIFACT_CLAIMS_REF,
    ARTIFACT_DISTRIBUTIONAL_REPORT_REF,
    ARTIFACT_OPTIMIZATION_AMBIGUITY_CERTIFICATE_REF,
    ARTIFACT_POLICY_BRIEF_REF,
    ARTIFACT_POLICY_FRONTIER_REPORT_REF,
    ARTIFACT_POLICY_OUTPUT_BUNDLE_REF,
    ARTIFACT_WELFARE_BUNDLE_REF,
    INPUT_DATA_SNAPSHOT_REF,
    INPUT_REGISTRY_BUNDLE_REF,
    INPUT_TRINITY_BUNDLE_REF,
)
from polisyos.scientist.orchestration.engine.context import (
    ClaimCapableExecutionContext,
    ExecutionContext,
)
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.state_branching import (
    branch_state as real_branch_state,
)
from polisyos.scientist.policy_design.objectives import (
    ConstraintStatus,
    ObjectiveChannelValue,
    ObjectiveDirection,
    ObjectiveKind,
    PolicyEvaluationVector,
)
from polisyos.scientist.policy_design.output import (
    PolicyArtifactBuilder,
    PolicyArtifactBuildInput,
    PolicyBrief,
    load_champion_policy_dossier,
    load_policy_artifact_bundle,
    load_policy_frontier_report,
    load_replayable_audit_bundle,
)
from polisyos.scientist.policy_design.schema import PolicyCandidateSchema, TargetPopulationSpec
from polisyos.scientist.policy_design.translator import TranslatorComplianceResult


def test_policy_output_ref_deduplication_keeps_distinct_selected_views() -> None:
    artifact_id = ArtifactID.model_validate("sha256:" + "a" * 64)
    default_ref = ArtifactRef(
        artifact_id=artifact_id,
        kind="scientist.side_information",
        media_type="application/json",
    )
    selected_a = default_ref.model_copy(update={"manifest_profile_sha256": "sha256:" + "b" * 64})
    selected_b = default_ref.model_copy(update={"manifest_profile_sha256": "sha256:" + "c" * 64})

    assert _dedupe_artifact_refs([default_ref, selected_a, selected_b, selected_a]) == [
        default_ref,
        selected_a,
        selected_b,
    ]


def _claim_capable_context(ctx: ExecutionContext) -> ClaimCapableExecutionContext:
    """Appoint the real Claim owner port only for positive policy-output cases."""

    return ClaimCapableExecutionContext(
        store=ctx.store,
        run=ctx.run,
        logger=ctx.logger,
        tracer=ctx.tracer,
        metrics=ctx.metrics,
        audit=ctx.audit,
        depth=ctx.depth,
        fabric=ctx.fabric,
        foundry=ctx.foundry,
        scholar=ctx.scholar,
        lex=ctx.lex,
        memory=ctx.memory,
        claim_ledger_owner=build_default_claim_ledger_owner(store=ctx.store),
    )


def _passing_judge_verdict() -> dict[str, object]:
    return {
        "per_judge": {
            name: {"judge_name": name, "passed": True, "is_fatal": True}
            for name in (
                "structural",
                "statistical",
                "robustness",
                "governance",
                "reproducibility",
                "compute",
            )
        },
        "composite_decision": "promote",
        "blocking_failures": [],
        "warnings": [],
    }


def _bundle() -> TrinityBundle:
    return TrinityBundle(
        problem_frame=ProblemFrame(
            problem_id="problem_policy",
            domain=ProblemDomain.FISCAL,
            objectives=[
                ObjectiveSpec(
                    objective_id="welfare",
                    metric_id="welfare_metric",
                    direction=OptimizationDirection.MAXIMIZE,
                )
            ],
            hard_constraints=[
                ConstraintSpec(
                    constraint_id="budget_cap",
                    constraint_type=ConstraintType.HARD,
                    value=MoneyValue(amount=Decimal("100"), currency="USD"),
                    operator="<=",
                    notes=["budget ceiling"],
                )
            ],
        ),
        policy_spec=PolicySpec(
            policy_id="policy_policy",
            interventions=[
                InterventionSpec(
                    intervention_id="tax_cut",
                    kind="tax_policy",
                    target={
                        "kind": "predicate",
                        "field": "id",
                        "operator": SelectorOperator.EQUALS,
                        "value": "all",
                    },
                    schedule={"start_step": 0, "duration_steps": 2},
                    params={"rate": Decimal("0.1")},
                )
            ],
            parameters=[
                ParameterSpec(
                    param_id="tax_rate",
                    intervention_id="tax_cut",
                    param_path="rate",
                    default_value=Decimal("0.1"),
                )
            ],
        ),
        model_spec=ModelSpec(
            model_id="model_policy",
            data_snapshot_ref="sha256:" + "1" * 64,
            assumptions=[
                AssumptionSpec(
                    assumption_id="elasticity",
                    assumption_type=AssumptionType.PARAMETRIC,
                    description="Elasticity remains stable in the policy horizon.",
                )
            ],
        ),
    )


def test_policy_output_candidate_resolution_refuses_foreign_trinity_schema(tmp_path) -> None:
    from polisyos.core.registry import build_default_registry_bundle
    from polisyos.core.run.context import RunContext
    from polisyos.scientist.orchestration.engine.context import ExecutionContext
    from polisyos.scientist.orchestration.engine.state import ExperimentState

    store = FileSystemCAS(tmp_path)
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(
        store=store,
        registry_bundle=registry_bundle,
        run_id="R_policy_candidate_schema",
    )
    ctx = ExecutionContext(
        store=store,
        run=run,
        logger=logging.getLogger("test.policy-output.schema"),
    )
    valid_ref = store.put_json(
        _bundle(),
        PutOptions(
            kind=TrinityBundle.ARTIFACT_KIND,
            media_type=TrinityBundle.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=TrinityBundle.ARTIFACT_SCHEMA_NAME,
                version=TrinityBundle.ARTIFACT_SCHEMA_VERSION,
            ),
        ),
    )
    foreign_schema_ref = store.put_json(
        _bundle(),
        PutOptions(
            kind=TrinityBundle.ARTIFACT_KIND,
            media_type=TrinityBundle.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(name=TrinityBundle.ARTIFACT_SCHEMA_NAME, version="9.0"),
        ),
    )

    valid_candidate, selected_ref = _resolve_candidate(
        ctx,
        ExperimentState(
            run_id="R_policy_candidate_schema",
            inputs={INPUT_TRINITY_BUNDLE_REF: valid_ref},
            params={"policy_candidate_id": "policy_schema_candidate"},
        ),
    )
    assert valid_candidate is not None
    assert selected_ref == valid_ref
    with pytest.raises(ValueError, match="manifest does not match its IR owner"):
        _resolve_candidate(
            ctx,
            ExperimentState(
                run_id="R_policy_candidate_schema",
                inputs={INPUT_TRINITY_BUNDLE_REF: foreign_schema_ref},
                params={"policy_candidate_id": "policy_schema_candidate"},
            ),
        )


def test_candidate_source_recomputes_from_owner_attempt_after_generic_selection_event(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A later caller event cannot relabel the exact input that selected the candidate."""
    import logging
    from dataclasses import replace

    from polisyos.core.artifacts.manifest import InputRef
    from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
    from polisyos.core.registry import build_default_registry_bundle
    from polisyos.core.run.context import RunContext
    from polisyos.core.trace.record import TraceRecord
    from polisyos.scientist.nodes.builtins.decide.build_policy_output_bundle import (
        _candidate_source_pointer,
        _resolve_candidate,
    )
    from polisyos.scientist.orchestration.engine.async_executor import AsyncWorkflowExecutor
    from polisyos.scientist.orchestration.engine.context import (
        ExecutionContext,
        _EngineInvocationBinding,
    )
    from polisyos.scientist.orchestration.engine.executor import WorkflowExecutor
    from polisyos.scientist.orchestration.engine.protocol import NodeOutcome, NodeSpec
    from polisyos.scientist.orchestration.engine.registry import NodeRegistry
    from polisyos.scientist.orchestration.engine.state import ExperimentState
    from polisyos.scientist.orchestration.engine.workflow_spec import NodeInvocation, WorkflowSpec
    from polisyos.scientist.policy_design.phase3 import (
        _resolve_candidate as _resolve_phase3_candidate,
    )
    from polisyos.scientist.policy_design.schema import persist_policy_candidate_schema

    store = FileSystemCAS(tmp_path)
    registry_bundle_ref = build_default_registry_bundle(
        store,
        return_selected_profile=True,
    ).bundle_ref
    candidate_a = _candidate().model_copy(update={"candidate_id": "candidate_a"})
    candidate_b = _candidate().model_copy(update={"candidate_id": "candidate_b"})
    ref_a = persist_policy_candidate_schema(store, candidate_a, return_selected_profile=True)
    ref_b = persist_policy_candidate_schema(store, candidate_b, return_selected_profile=True)
    anchor_a = store.put_json(
        {"anchor": "a"},
        PutOptions(kind="test.candidate_anchor", media_type="application/json"),
    )
    ref_a_same_content_other_profile = persist_policy_candidate_schema(
        store,
        candidate_a,
        inputs=[InputRef(artifact_id=anchor_a.artifact_id, role="candidate_basis")],
        return_selected_profile=True,
    )
    assert ref_a_same_content_other_profile.artifact_id == ref_a.artifact_id
    assert ref_a_same_content_other_profile.manifest_profile_sha256 != ref_a.manifest_profile_sha256
    component_id = ComponentId.parse("scientist.node_candidate_origin_probe@1.0.0")
    selections: list[tuple[str | None, ArtifactRef | None, str | None]] = []
    phase3_selections: list[str | None] = []

    class CandidateOriginProbeNode:
        def __init__(self, forged_ref: ArtifactRef) -> None:
            self.forged_ref = forged_ref
            self._spec = NodeSpec(
                metadata=ComponentMetadata(
                    component_id=component_id,
                    kind=ComponentKind.SCIENTIST_NODE,
                    abi_targets={"world_abi": "1.x"},
                    display_name="Candidate Origin Probe",
                    description="Resolves one candidate from the current invocation input.",
                    capabilities=Capability.SCIENTIST_NODE,
                )
            )

        @property
        def spec(self) -> NodeSpec:
            return self._spec

        def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
            candidate, selected_ref = _resolve_candidate(ctx, state)
            phase3_candidate = _resolve_phase3_candidate(ctx, state)
            phase3_selections.append(
                phase3_candidate.candidate_id if phase3_candidate is not None else None
            )
            selections.append(
                (
                    candidate.candidate_id if candidate is not None else None,
                    selected_ref,
                    _candidate_source_pointer(state),
                )
            )
            # Caller-owned labels can claim an inline branch with the same candidate bytes,
            # then append a cross-candidate selection. Neither event is an owner basis.
            ctx.run.emit(
                "runtime.parameters",
                "RUNTIME_PARAMETER_SELECTED_PARAMS_POLICY_CANDIDATE_SCHEMA",
                outputs=[selected_ref] if selected_ref is not None else None,
            )
            ctx.run.emit(
                "runtime.parameters",
                "RUNTIME_PARAMETER_SELECTED",
                outputs=[self.forged_ref],
            )
            return NodeOutcome(status="ok", state=state)

    for index, (selected_ref, expected_candidate_id, forged_ref) in enumerate(
        (
            (ref_a, "candidate_a", ref_b),
            (ref_b, "candidate_b", ref_a),
            (ref_a, "candidate_a", ref_a_same_content_other_profile),
        ),
        start=1,
    ):
        run_id = f"R_candidate_origin_{index}"
        run = RunContext.start(
            store=store,
            registry_bundle=registry_bundle_ref,
            run_id=run_id,
        )
        ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger(run_id))
        node = CandidateOriginProbeNode(forged_ref)
        registry = NodeRegistry()
        registry.register(node)
        workflow = WorkflowSpec(
            workflow_id="candidate_origin_probe",
            nodes=[NodeInvocation(alias="resolve", node_id=component_id)],
        )
        state = ExperimentState(
            run_id=run_id,
            params={"policy_candidate_ref": selected_ref.model_dump(mode="json")},
        )

        if index != 2:
            WorkflowExecutor(ctx, registry).execute(workflow, state)
        else:
            import asyncio

            asyncio.run(AsyncWorkflowExecutor(ctx, registry).execute(workflow, state))
        attempts = run.read_runtime_invocation_attempts()
        matching = [attempt for attempt in attempts if attempt.basis.node_alias == "resolve"]
        assert len(matching) == 1
        attempt = matching[0]
        assert attempt.outcome is not None and attempt.outcome.status == "ok"
        assert selections[-1] == (
            expected_candidate_id,
            selected_ref,
            "/params/policy_candidate_ref",
        )
        assert phase3_selections[-1] == expected_candidate_id

        # Fresh CAS and trace reads reconstruct the source from the owner-linked basis.
        source_state = ExperimentState.model_validate_json(
            store.get_bytes(attempt.basis.input_state_ref)
        )
        fresh_ctx = ExecutionContext(
            store=store,
            run=run,
            logger=logging.getLogger(f"{run_id}.fresh"),
            _engine_invocation=_EngineInvocationBinding(
                run_id=run_id,
                attempt_id=attempt.basis.attempt_id,
                basis_ref=attempt.basis_ref,
                require_successful_completion=True,
            ),
        )
        fresh_candidate, fresh_ref = _resolve_candidate(fresh_ctx, source_state)
        assert fresh_candidate is not None
        assert (fresh_candidate.candidate_id, fresh_ref) == (expected_candidate_id, selected_ref)
        fresh_phase3_candidate = _resolve_phase3_candidate(fresh_ctx, source_state)
        assert fresh_phase3_candidate is not None
        assert fresh_phase3_candidate.candidate_id == expected_candidate_id
        assert _candidate_source_pointer(source_state) == "/params/policy_candidate_ref"
        legacy_candidate, legacy_ref = _resolve_candidate(
            ExecutionContext(store=store, run=run, logger=logging.getLogger(f"{run_id}.legacy")),
            source_state,
        )
        assert legacy_candidate is not None
        assert (legacy_candidate.candidate_id, legacy_ref) == (expected_candidate_id, selected_ref)
        fake_ctx = ExecutionContext(
            store=store,
            run=run,
            logger=logging.getLogger(f"{run_id}.fake"),
            _engine_invocation=_EngineInvocationBinding(
                run_id=run_id,
                attempt_id=attempt.basis.attempt_id,
                basis_ref=forged_ref,
            ),
        )
        with pytest.raises(ValueError, match="runtime_candidate_invocation_basis_not_owner_linked"):
            _resolve_candidate(fake_ctx, source_state)
        changed_source_state = source_state.model_copy(
            update={
                "params": {
                    **source_state.params,
                    "policy_candidate_ref": forged_ref.model_dump(mode="json"),
                }
            }
        )
        with pytest.raises(ValueError, match="runtime_candidate_input_state_basis_mismatch"):
            _resolve_candidate(fresh_ctx, changed_source_state)
        with pytest.raises(ValueError, match="runtime_candidate_input_state_basis_mismatch"):
            _resolve_phase3_candidate(fresh_ctx, changed_source_state)

        failed_attempt = replace(
            attempt,
            outcome=attempt.outcome.model_copy(update={"status": "fail"}),
        )
        failed_ctx = ExecutionContext(
            store=store,
            run=run,
            logger=logging.getLogger(f"{run_id}.failed"),
            _engine_invocation=_EngineInvocationBinding(
                run_id=run_id,
                attempt_id=attempt.basis.attempt_id,
                basis_ref=attempt.basis_ref,
                require_successful_completion=True,
            ),
        )
        with monkeypatch.context() as status_probe:
            status_probe.setattr(
                RunContext,
                "read_runtime_invocation_attempts",
                lambda _run, exact=failed_attempt: [exact],
            )
            with pytest.raises(ValueError, match="runtime_candidate_invocation_not_successful"):
                _resolve_phase3_candidate(failed_ctx, source_state)

        trace_path = run.trace_path
        assert trace_path is not None
        trace_records = [
            TraceRecord.model_validate_json(line)
            for line in trace_path.read_bytes().splitlines()
            if line.strip()
        ]
        selection_events = [
            record for record in trace_records if record.event == "RUNTIME_PARAMETER_SELECTED"
        ]
        assert selection_events[-1].refs.outputs == [forged_ref]
        inline_labeled_events = [
            record
            for record in trace_records
            if record.event == "RUNTIME_PARAMETER_SELECTED_PARAMS_POLICY_CANDIDATE_SCHEMA"
        ]
        assert inline_labeled_events[-1].refs.outputs == [selected_ref]
        assert {record.event for record in trace_records}.issuperset(
            {
                "RUNTIME_PARAMETER_SELECTED_PARAMS_POLICY_CANDIDATE_SCHEMA",
                "RUNTIME_PARAMETER_SELECTED",
            }
        )

        # Removing the owner-recomputed attempt while preserving both trace labels
        # must make the fresh consumer refuse rather than fall back to marker order.
        with monkeypatch.context() as removal_probe:
            removal_probe.setattr(RunContext, "read_runtime_invocation_attempts", lambda _run: [])
            with pytest.raises(
                ValueError,
                match="runtime_candidate_invocation_basis_not_owner_linked",
            ):
                _resolve_candidate(fresh_ctx, source_state)
            with pytest.raises(
                ValueError,
                match="runtime_candidate_invocation_basis_not_owner_linked",
            ):
                _resolve_phase3_candidate(fresh_ctx, source_state)


def _candidate() -> PolicyCandidateSchema:
    return PolicyCandidateSchema.from_trinity_bundle(
        _bundle(),
        candidate_id="candidate_policy",
        metadata={"policy_family": "core_family", "evidence_depth": "replicated"},
    ).model_copy(
        update={
            "target_population": TargetPopulationSpec(
                population_id="population_policy",
                description="General population",
                geography="national",
            )
        }
    )


def _evaluation_vector(candidate: PolicyCandidateSchema) -> PolicyEvaluationVector:
    return PolicyEvaluationVector(
        candidate_id=candidate.candidate_id,
        primary={
            "policy_value": ObjectiveChannelValue(
                name="policy_value",
                kind=ObjectiveKind.PRIMARY,
                value=1.2,
                direction=ObjectiveDirection.MAXIMIZE,
            )
        },
        hard_constraints={
            "policy_budget_constraint": ObjectiveChannelValue(
                name="policy_budget_constraint",
                kind=ObjectiveKind.HARD_CONSTRAINT,
                value=0.95,
                direction=ObjectiveDirection.MINIMIZE,
                threshold=1.0,
                status=ConstraintStatus.NEAR_BINDING,
            )
        },
        feasible=True,
        metadata={"candidate_hash": candidate.candidate_hash()},
    )


def _hierarchical_search_result_with_unknown(
    known: PolicyCandidateSchema,
    unknown: PolicyCandidateSchema,
) -> SimpleNamespace:
    """Build the hierarchy owner's real result shape with one missing evaluation."""
    known_id = "known"
    unknown_id = "unknown"

    def _history(candidate: PolicyCandidateSchema, evaluation: PolicyEvaluationVector | None):
        return SimpleNamespace(
            history=[
                SimpleNamespace(
                    candidate=candidate.model_dump(mode="json"),
                    best_candidate=None,
                    policy_evaluation=evaluation,
                    objective_value=0.0,
                    is_promising=evaluation is not None and evaluation.feasible,
                    stage_b_result={},
                )
            ]
        )

    return SimpleNamespace(
        state=SimpleNamespace(
            structure_candidates=[
                SimpleNamespace(structure_id=known_id, candidate=known, accepted=True),
                SimpleNamespace(structure_id=unknown_id, candidate=unknown, accepted=True),
            ],
            parameter_search_results={
                known_id: _history(known, _evaluation_vector(known)),
                unknown_id: _history(unknown, None),
            },
        ),
        pareto_projection=None,
    )


def _readiness_contract() -> DecisionReadinessContract:
    return DecisionReadinessContract(
        readiness_level=DecisionReadiness.RECOMMENDATION_READY,
        required_judges_passed=["structural"],
        required_uncertainty_bounds={},
        mandatory_human_gate=False,
        assumptions_must_be_surfaced=["Elasticity remains stable in the policy horizon."],
        expiry_conditions=["freshness_violation"],
        evidence_depth_required="replicated",
    )


def _policy_brief() -> PolicyBrief:
    return PolicyBrief(
        title="Policy brief for candidate_policy",
        executive_summary="Candidate improves welfare while keeping the budget constraint near binding.",
        readiness_level=DecisionReadiness.RECOMMENDATION_READY.value,
        surfaced_assumptions=["Elasticity remains stable in the policy horizon."],
        subgroup_harms=["Low income"],
        hard_constraint_notes=["policy_budget_constraint"],
    )


def _translator_compliance() -> TranslatorComplianceResult:
    return TranslatorComplianceResult(passed=True, findings=[])


def _phase3_ready_refs(cas_store) -> tuple[ArtifactRef, ArtifactRef]:
    matrix_ref = cas_store.put_json(
        {"matrix": [[1]]},
        PutOptions(kind="ir.welfare_multiplier_matrix", media_type="application/json"),
    )
    social_weight_ref = persist_social_weight_manifest(
        _ensure_ir_artifact_store(cas_store),
        SocialWeightManifestArtifact(
            manifest_ref="swr://policy.welfare/test@1.0.0#phase3",
            method_fqn="policy.welfare.state_dependent_inverse_social_weights@1.0.0",
            normalization="mean_one",
            income_grid=(0.0, 1.0),
            weights_on_grid=(1.0, 1.0),
            state_keys=("income",),
            manifest_payload={
                "ref": "swr://policy.welfare/test@1.0.0#phase3",
                "income_grid": [0.0, 1.0],
                "weights_on_grid": [1.0, 1.0],
            },
        ),
    )
    ge_ref = persist_ge_uncertainty_bundle(
        _ensure_ir_artifact_store(cas_store),
        GEUncertaintyBundle(
            model_class="linearized_ge_io",
            representation=GEUncertaintyRepresentation.MULTIPLIER_INTERVALS,
            multiplier_shape=(1, 1),
            point_multiplier_ref=ArtifactRefModel.model_validate(
                matrix_ref.model_dump(mode="json")
            ),
            lower_multiplier_ref=ArtifactRefModel.model_validate(
                matrix_ref.model_dump(mode="json")
            ),
            upper_multiplier_ref=ArtifactRefModel.model_validate(
                matrix_ref.model_dump(mode="json")
            ),
        ),
    )
    welfare_ref = persist_welfare_bundle(
        _ensure_ir_artifact_store(cas_store),
        WelfareBundle(
            welfare_measure="net_social_welfare",
            model_class="linearized_ge_io",
            ge_multiplier_semantics="leontief_inverse",
            social_weight_ref=social_weight_ref,
            ge_uncertainty_ref=ge_ref,
            point_estimate=1.0,
            credible_interval=(0.9, 1.1),
            robust_interval=(0.8, 1.2),
            interval_semantics=WelfareIntervalSemantics.MIXED_NESTED,
            method_used=WelfareMethod.MIXED_NESTED,
            status=WelfareStatus.OK,
        ),
    )
    ambiguity_ref = persist_optimization_ambiguity_certificate(
        _ensure_ir_artifact_store(cas_store),
        build_optimization_ambiguity_certificate(
            {"mode": "not_applicable", "note": "deterministic path"},
            mode="not_applicable",
            source_kind="test",
            overall_status="pass",
            note="deterministic path",
        ),
    )
    return welfare_ref, ambiguity_ref


def test_build_policy_output_bundle_skips_outside_policy_mode(
    execution_context: ExecutionContext, minimal_state: ExperimentState
) -> None:
    outcome = BuildPolicyOutputBundleNode().execute(execution_context, minimal_state)
    assert outcome.status == "skip"


def test_build_policy_output_bundle_writes_refs(
    execution_context: ExecutionContext,
    minimal_state: ExperimentState,
    cas_store: FileSystemCAS,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate = _candidate()
    welfare_ref, ambiguity_ref = _phase3_ready_refs(cas_store)
    state = minimal_state.model_copy(deep=True)
    state.params.update(
        {
            "workflow_id": "scientist_policy_design",
            "policy_mode": True,
            "policy_candidate_schema": candidate.model_dump(mode="json"),
            "policy_evaluation": _evaluation_vector(candidate).model_dump(mode="json"),
            "decision_readiness_contract": _readiness_contract().model_dump(mode="json"),
            "policy_brief": _policy_brief().model_dump(mode="json"),
            "translator_compliance": _translator_compliance().model_dump(mode="json"),
            "judge_verdict": _passing_judge_verdict(),
        }
    )
    state.artifacts_index[ARTIFACT_WELFARE_BUNDLE_REF] = welfare_ref
    state.artifacts_index[ARTIFACT_OPTIMIZATION_AMBIGUITY_CERTIFICATE_REF] = ambiguity_ref

    ownerless = BuildPolicyOutputBundleNode().execute(execution_context, state)
    assert ownerless.status == "fail"
    assert ownerless.error is not None
    assert ownerless.error.code == "claim_ledger_owner_not_established"

    mutant = os.environ.get("POLISYOS_B111_FALLBACK_MUTANT")
    if mutant not in (None, "membership"):
        raise ValueError(f"Unsupported B111 fallback mutant: {mutant}")
    if mutant == "membership":
        build_frontier_report = PolicyArtifactBuilder._build_frontier_report

        def _without_fallback_membership(builder, build_input):
            report = build_frontier_report(builder, build_input)
            if (
                build_input.pareto_snapshot is None
                and build_input.run_local_frontier_report_ref is None
            ):
                assert report.schema_version == "3.0"
                assert report.source_feasible_candidate_hashes == ()
                limited = report.view_projections["global_feasible"]
                assert limited.assessment.status == "basis_limited"
                assert limited.assessment.basis_scope.scope == "not_established"
                payload = report.model_dump(mode="python")
                payload["view_membership"] = {}
                return type(report).model_validate(payload)
            return report

        monkeypatch.setattr(
            PolicyArtifactBuilder,
            "_build_frontier_report",
            _without_fallback_membership,
        )

    outcome = BuildPolicyOutputBundleNode().execute(
        _claim_capable_context(execution_context), state
    )

    assert outcome.status == "ok", outcome.error
    assert ARTIFACT_POLICY_OUTPUT_BUNDLE_REF in outcome.state.artifacts_index
    assert ARTIFACT_CLAIMS_REF in outcome.state.artifacts_index
    assert ARTIFACT_POLICY_BRIEF_REF in outcome.state.artifacts_index
    bundle = load_policy_artifact_bundle(
        cas_store,
        outcome.state.artifacts_index[ARTIFACT_POLICY_OUTPUT_BUNDLE_REF],
    )
    assert bundle.policy_brief_ref is not None
    assert bundle.claims_ref == outcome.state.artifacts_index[ARTIFACT_CLAIMS_REF]
    assert bundle.welfare_bundle_ref == welfare_ref
    assert bundle.ambiguity_certificate_ref == ambiguity_ref
    frontier_report = load_policy_frontier_report(cas_store, bundle.policy_frontier_report_ref)
    assert frontier_report.schema_version == "3.0"
    assert frontier_report.source_feasible_candidate_hashes == ()
    assert frontier_report.view_membership == {
        view_key: list(view_projection.ranked_frontier_hashes)
        for view_key, view_projection in frontier_report.view_projections.items()
    }
    assert frontier_report.global_frontier == []
    assert frontier_report.candidate_frontier == []
    limited_projection = frontier_report.view_projections["global_feasible"]
    assert limited_projection.ranked_frontier_hashes == ()
    assert limited_projection.assessment.status == "basis_limited"
    assert limited_projection.assessment.basis_scope.scope == "not_established"
    assert (
        outcome.state.policy_output_bundle_ref
        == outcome.state.artifacts_index[ARTIFACT_POLICY_OUTPUT_BUNDLE_REF]
    )


def test_build_policy_output_bundle_preserves_run_local_candidate_frontier(
    execution_context,
    minimal_state,
    cas_store,
):
    known = _candidate()
    unknown = known.model_copy(update={"candidate_id": "candidate_without_evaluation"})
    source_state = minimal_state.model_copy(deep=True)
    source_ref = _persist_frontier_report(
        execution_context,
        state=source_state,
        loop_id=f"{source_state.run_id}:policy_search",
        search_result=_hierarchical_search_result_with_unknown(known, unknown),
    )
    source_report = load_policy_frontier_report(cas_store, source_ref)
    known_hash = known.candidate_hash()
    unknown_hash = unknown.candidate_hash()
    assert source_report.source_feasible_candidate_hashes == (known_hash,)
    assert source_report.eligibility_unknown_candidate_hashes == (unknown_hash,)
    assert source_report.global_frontier == []

    welfare_ref, ambiguity_ref = _phase3_ready_refs(cas_store)
    state = minimal_state.model_copy(deep=True)
    state.params.update(
        {
            "workflow_id": "scientist_policy_design",
            "policy_mode": True,
            "policy_candidate_schema": known.model_dump(mode="json"),
            "policy_evaluation": _evaluation_vector(known).model_dump(mode="json"),
            "decision_readiness_contract": _readiness_contract().model_dump(mode="json"),
            "policy_brief": _policy_brief().model_dump(mode="json"),
            "translator_compliance": _translator_compliance().model_dump(mode="json"),
            "judge_verdict": _passing_judge_verdict(),
        }
    )
    state.artifacts_index[ARTIFACT_POLICY_FRONTIER_REPORT_REF] = source_ref
    state.artifacts_index[ARTIFACT_WELFARE_BUNDLE_REF] = welfare_ref
    state.artifacts_index[ARTIFACT_OPTIMIZATION_AMBIGUITY_CERTIFICATE_REF] = ambiguity_ref

    outcome = BuildPolicyOutputBundleNode().execute(
        _claim_capable_context(execution_context), state
    )

    assert outcome.status == "ok"
    bundle = load_policy_artifact_bundle(
        cas_store,
        outcome.state.artifacts_index[ARTIFACT_POLICY_OUTPUT_BUNDLE_REF],
    )
    assert bundle.policy_frontier_report_ref == source_ref
    assert outcome.state.artifacts_index[ARTIFACT_POLICY_FRONTIER_REPORT_REF] == source_ref
    report = load_policy_frontier_report(cas_store, bundle.policy_frontier_report_ref)
    assert report.source_feasible_candidate_hashes == (known_hash,)
    assert report.eligibility_unknown_candidate_hashes == (unknown_hash,)
    assert {entry.candidate_hash for entry in report.candidate_frontier} == {
        known_hash,
        unknown_hash,
    }
    projection = report.view_projections["global_feasible"]
    assert report.global_frontier == []
    assert projection.ranked_frontier_hashes == ()
    assert projection.assessment.status == "denominator_limited"
    assert projection.assessment.basis_scope.scope == "not_established"


def test_build_policy_output_bundle_removal_probe_keeps_report_but_loses_candidate_rows(
    execution_context,
    minimal_state,
    cas_store,
):
    known = _candidate()
    unknown = known.model_copy(update={"candidate_id": "candidate_without_evaluation"})
    source_state = minimal_state.model_copy(deep=True)
    source_ref = _persist_frontier_report(
        execution_context,
        state=source_state,
        loop_id=f"{source_state.run_id}:policy_search",
        search_result=_hierarchical_search_result_with_unknown(known, unknown),
    )
    source_report = load_policy_frontier_report(cas_store, source_ref)
    assert source_report.candidate_frontier

    welfare_ref, ambiguity_ref = _phase3_ready_refs(cas_store)
    state = minimal_state.model_copy(deep=True)
    state.params.update(
        {
            "workflow_id": "scientist_policy_design",
            "policy_mode": True,
            "policy_candidate_schema": known.model_dump(mode="json"),
            "policy_evaluation": _evaluation_vector(known).model_dump(mode="json"),
            "decision_readiness_contract": _readiness_contract().model_dump(mode="json"),
            "policy_brief": _policy_brief().model_dump(mode="json"),
            "translator_compliance": _translator_compliance().model_dump(mode="json"),
            "judge_verdict": _passing_judge_verdict(),
        }
    )
    # Keep the report, ref, and content markers in CAS and state. Remove only the
    # validated handoff from the actual output node into the actual builder.
    state.artifacts_index[ARTIFACT_POLICY_FRONTIER_REPORT_REF] = source_ref
    state.artifacts_index[ARTIFACT_WELFARE_BUNDLE_REF] = welfare_ref
    state.artifacts_index[ARTIFACT_OPTIMIZATION_AMBIGUITY_CERTIFICATE_REF] = ambiguity_ref

    original_build = PolicyArtifactBuilder.build
    captured_build_input: PolicyArtifactBuildInput | None = None

    def _build_without_run_local_frontier_handoff(
        builder: PolicyArtifactBuilder,
        store: FileSystemCAS,
        build_input: PolicyArtifactBuildInput,
        *,
        claim_owner: ClaimLedgerOwnerPort,
    ) -> ArtifactRef:
        nonlocal captured_build_input
        captured_build_input = build_input
        return original_build(
            builder,
            store,
            build_input.model_copy(
                update={
                    "run_local_frontier_report_ref": None,
                    "run_local_frontier_report_loop_id": None,
                }
            ),
            claim_owner=claim_owner,
        )

    with patch.object(
        PolicyArtifactBuilder,
        "build",
        _build_without_run_local_frontier_handoff,
    ):
        outcome = BuildPolicyOutputBundleNode().execute(
            _claim_capable_context(execution_context), state
        )

    assert outcome.status == "ok"
    assert captured_build_input is not None
    assert captured_build_input.run_local_frontier_report_ref == source_ref
    assert state.artifacts_index[ARTIFACT_POLICY_FRONTIER_REPORT_REF] == source_ref
    assert load_policy_frontier_report(cas_store, source_ref).candidate_frontier
    bundle = load_policy_artifact_bundle(
        cas_store,
        outcome.state.artifacts_index[ARTIFACT_POLICY_OUTPUT_BUNDLE_REF],
    )
    assert bundle.policy_frontier_report_ref != source_ref
    limited_report = load_policy_frontier_report(cas_store, bundle.policy_frontier_report_ref)
    assert limited_report.candidate_frontier == []
    assert limited_report.global_frontier == []
    assert limited_report.view_projections["global_feasible"].assessment.status == "basis_limited"


def test_build_policy_output_bundle_mismatched_frontier_run_does_not_block_candidate_output(
    execution_context,
    minimal_state,
    cas_store,
):
    known = _candidate()
    unknown = known.model_copy(update={"candidate_id": "candidate_without_evaluation"})
    prior_run_state = minimal_state.model_copy(update={"run_id": "R_prior"}, deep=True)
    prior_ref = _persist_frontier_report(
        execution_context,
        state=prior_run_state,
        loop_id=f"{prior_run_state.run_id}:policy_search",
        search_result=_hierarchical_search_result_with_unknown(known, unknown),
    )
    prior_report = load_policy_frontier_report(cas_store, prior_ref)
    assert prior_report.metadata["source_run_id"] == "R_prior"
    assert prior_report.candidate_frontier

    welfare_ref, ambiguity_ref = _phase3_ready_refs(cas_store)
    state = minimal_state.model_copy(deep=True)
    state.params.update(
        {
            "workflow_id": "scientist_policy_design",
            "policy_mode": True,
            "policy_candidate_schema": known.model_dump(mode="json"),
            "policy_evaluation": _evaluation_vector(known).model_dump(mode="json"),
            "decision_readiness_contract": _readiness_contract().model_dump(mode="json"),
            "policy_brief": _policy_brief().model_dump(mode="json"),
            "translator_compliance": _translator_compliance().model_dump(mode="json"),
            "judge_verdict": _passing_judge_verdict(),
        }
    )
    state.artifacts_index[ARTIFACT_POLICY_FRONTIER_REPORT_REF] = prior_ref
    state.artifacts_index[ARTIFACT_WELFARE_BUNDLE_REF] = welfare_ref
    state.artifacts_index[ARTIFACT_OPTIMIZATION_AMBIGUITY_CERTIFICATE_REF] = ambiguity_ref

    outcome = BuildPolicyOutputBundleNode().execute(
        _claim_capable_context(execution_context), state
    )

    assert outcome.status == "ok"
    assert any(
        event.code == "policy_output_bundle.frontier_source_not_preserved"
        and event.attrs.get("reason") == "frontier_source_report_run_mismatch"
        for event in outcome.events
    )
    bundle = load_policy_artifact_bundle(
        cas_store,
        outcome.state.artifacts_index[ARTIFACT_POLICY_OUTPUT_BUNDLE_REF],
    )
    limited_report = load_policy_frontier_report(cas_store, bundle.policy_frontier_report_ref)
    assert limited_report.schema_version == "3.0"
    assert limited_report.source_feasible_candidate_hashes == ()
    assert limited_report.view_membership == {
        view_key: list(view_projection.ranked_frontier_hashes)
        for view_key, view_projection in limited_report.view_projections.items()
    }
    assert limited_report.global_frontier == []
    assert limited_report.candidate_frontier == []
    limited_projection = limited_report.view_projections["global_feasible"]
    assert limited_projection.ranked_frontier_hashes == ()
    assert limited_projection.assessment.status == "basis_limited"
    assert limited_projection.assessment.basis_scope.scope == "not_established"


def test_build_policy_output_bundle_propagates_actionable_side_information(
    execution_context,
    minimal_state,
    cas_store,
):
    candidate = _candidate()
    welfare_ref, ambiguity_ref = _phase3_ready_refs(cas_store)
    side_info_ref = persist_actionable_side_information(
        cas_store,
        ActionableSideInformation(candidate_id=candidate.candidate_id),
    )
    funnel_outcome = FunnelOutcome(
        ticket_id="ticket_policy",
        candidate_hash=candidate.candidate_hash(),
        trace=[],
        stage_results={},
        final_result=FunnelStageResult(
            policy_candidate={},
            objective_value=1.0,
            is_promising=True,
            stage_name="funnel_L6_promotion",
            uncertainty_envelope=UncertaintyEnvelope.deterministic(),
        ),
        failure_cards=[],
        uncertainty_envelope=UncertaintyEnvelope.deterministic(),
        compute_cost_usd=0.5,
        compute_cost_origin="estimated",
        degradation_mode="normal",
        final_action="complete",
        completed=True,
        audit_refs=[side_info_ref],
        actionable_side_information_refs=[side_info_ref],
    )

    state = minimal_state.model_copy(deep=True)
    state.params.update(
        {
            "workflow_id": "scientist_policy_design",
            "policy_mode": True,
            "policy_candidate_schema": candidate.model_dump(mode="json"),
            "policy_evaluation": _evaluation_vector(candidate).model_dump(mode="json"),
            "decision_readiness_contract": _readiness_contract().model_dump(mode="json"),
            "policy_brief": _policy_brief().model_dump(mode="json"),
            "translator_compliance": _translator_compliance().model_dump(mode="json"),
            "judge_verdict": _passing_judge_verdict(),
            "funnel_outcome": funnel_outcome,
        }
    )
    state.artifacts_index[ARTIFACT_WELFARE_BUNDLE_REF] = welfare_ref
    state.artifacts_index[ARTIFACT_OPTIMIZATION_AMBIGUITY_CERTIFICATE_REF] = ambiguity_ref

    outcome = BuildPolicyOutputBundleNode().execute(
        _claim_capable_context(execution_context), state
    )

    assert outcome.status == "ok"
    bundle = load_policy_artifact_bundle(
        cas_store,
        outcome.state.artifacts_index[ARTIFACT_POLICY_OUTPUT_BUNDLE_REF],
    )
    audit_bundle = load_replayable_audit_bundle(cas_store, bundle.replayable_audit_bundle_ref)

    assert [ref.artifact_id for ref in bundle.actionable_side_information_refs] == [
        side_info_ref.artifact_id
    ]
    assert [ref.artifact_id for ref in bundle.audit_refs] == [side_info_ref.artifact_id]
    assert [ref.artifact_id for ref in audit_bundle.actionable_side_information_refs] == [
        side_info_ref.artifact_id
    ]


def test_build_policy_output_bundle_fails_when_required_inputs_missing(
    execution_context, minimal_state
):
    state = minimal_state.model_copy(deep=True)
    state.params.update({"workflow_id": "scientist_policy_design", "policy_mode": True})

    outcome = BuildPolicyOutputBundleNode().execute(
        _claim_capable_context(execution_context), state
    )

    assert outcome.status == "fail"
    assert outcome.error is not None


def test_build_policy_output_bundle_refuses_when_phase3_gate_missing(
    execution_context,
    minimal_state,
):
    candidate = _candidate()
    state = minimal_state.model_copy(deep=True)
    state.params.update(
        {
            "workflow_id": "scientist_policy_design",
            "policy_mode": True,
            "policy_candidate_schema": candidate.model_dump(mode="json"),
            "policy_evaluation": _evaluation_vector(candidate).model_dump(mode="json"),
            "decision_readiness_contract": _readiness_contract().model_dump(mode="json"),
            "policy_brief": _policy_brief().model_dump(mode="json"),
            "translator_compliance": _translator_compliance().model_dump(mode="json"),
            "judge_verdict": _passing_judge_verdict(),
        }
    )

    outcome = BuildPolicyOutputBundleNode().execute(
        _claim_capable_context(execution_context), state
    )

    assert outcome.status == "fail"
    assert outcome.error is not None
    assert "phase3.welfare_missing" in outcome.error.message
    assert ARTIFACT_POLICY_OUTPUT_BUNDLE_REF not in outcome.state.artifacts_index


def test_build_policy_output_bundle_embeds_calibration_validation_summary(
    execution_context,
    minimal_state,
    cas_store,
) -> None:
    candidate = _candidate()
    welfare_ref, ambiguity_ref = _phase3_ready_refs(cas_store)
    state = minimal_state.model_copy(deep=True)
    candidate_ref = ArtifactRef(
        artifact_id="sha256:" + "1" * 64,
        kind="scientist.test",
        media_type="application/json",
    )
    calibration_validation_ref = persist_calibration_validation_bundle(
        cas_store,
        CalibrationValidationBundle(
            run_id="R_policy_c5b",
            candidate_ref=candidate_ref,
            governance_verdict="approve",
            status="completed",
            backtest_matrix=BacktestMatrixResult(
                report_id="BTM_policy",
                composite_score=0.79,
                worst_kind=BacktestKind.DISTRESS,
            ),
            stress_scenarios=StressScenarioResult(
                report_id="stress_policy",
                robustness_score=0.73,
                worst_scenario=StressScenarioKind.TRADE_DISRUPTION,
            ),
            leaderboard_entry=CalibrationLeaderboardEntry(
                entry_id="leaderboard_policy",
                run_id="R_policy_c5b",
                candidate_ref=candidate_ref,
                metrics=CalibrationLeaderboardMetrics(
                    calibration_fit_score=0.88,
                    backtest_matrix_score=0.79,
                    stress_robustness_score=0.73,
                    specification_curve_robustness=0.7,
                    transportability_score=0.81,
                    interference_fit=0.76,
                    strategic_response_plausibility=0.82,
                    governance_verdict="approve",
                    adversarial_passed=True,
                    eligible_for_promotion=True,
                    composite_score=0.8,
                ),
                worst_backtest_kind=BacktestKind.DISTRESS,
                worst_stress_scenario=StressScenarioKind.TRADE_DISRUPTION,
            ),
            governance_accountability_ref=GovernanceAccountabilityArtifactRef(
                artifact_id="sha256:" + "9" * 64
            ),
            governance_accountability_summary={
                "risk_weighted_verdict": "needs_revision",
                "requires_human_review": False,
                "selected_threshold": 0.55,
            },
        ),
    )
    state.params.update(
        {
            "workflow_id": "scientist_policy_design",
            "policy_mode": True,
            "policy_candidate_schema": candidate.model_dump(mode="json"),
            "policy_evaluation": _evaluation_vector(candidate).model_dump(mode="json"),
            "decision_readiness_contract": _readiness_contract().model_dump(mode="json"),
            "policy_brief": _policy_brief().model_dump(mode="json"),
            "translator_compliance": _translator_compliance().model_dump(mode="json"),
            "judge_verdict": _passing_judge_verdict(),
        }
    )
    state.artifacts_index[ARTIFACT_CALIBRATION_VALIDATION_BUNDLE_REF] = calibration_validation_ref
    state.artifacts_index[ARTIFACT_WELFARE_BUNDLE_REF] = welfare_ref
    state.artifacts_index[ARTIFACT_OPTIMIZATION_AMBIGUITY_CERTIFICATE_REF] = ambiguity_ref

    outcome = BuildPolicyOutputBundleNode().execute(
        _claim_capable_context(execution_context), state
    )

    assert outcome.status == "ok"
    bundle = load_policy_artifact_bundle(
        cas_store,
        outcome.state.artifacts_index[ARTIFACT_POLICY_OUTPUT_BUNDLE_REF],
    )
    dossier = load_champion_policy_dossier(cas_store, bundle.champion_policy_dossier_ref)
    assert dossier.calibration_validation_summary["composite_score"] == 0.8
    assert dossier.calibration_validation_summary["worst_backtest_kind"] == "distress"
    assert dossier.accountability_summary["risk_weighted_verdict"] == "needs_revision"
    assert bundle.governance_accountability_artifact_ref is not None


def test_build_policy_output_bundle_degrades_invalid_distributional_report(
    execution_context,
    minimal_state,
    cas_store,
) -> None:
    candidate = _candidate()
    welfare_ref, ambiguity_ref = _phase3_ready_refs(cas_store)
    invalid_ref = cas_store.put_json(
        ["invalid"],
        PutOptions(kind="ir.distributional_report", media_type="application/json"),
    )
    state = minimal_state.model_copy(deep=True)
    state.params.update(
        {
            "workflow_id": "scientist_policy_design",
            "policy_mode": True,
            "policy_candidate_schema": candidate.model_dump(mode="json"),
            "policy_evaluation": _evaluation_vector(candidate).model_dump(mode="json"),
            "decision_readiness_contract": _readiness_contract().model_dump(mode="json"),
            "policy_brief": _policy_brief().model_dump(mode="json"),
            "translator_compliance": _translator_compliance().model_dump(mode="json"),
            "judge_verdict": _passing_judge_verdict(),
        }
    )
    state.artifacts_index[ARTIFACT_DISTRIBUTIONAL_REPORT_REF] = invalid_ref
    state.artifacts_index[ARTIFACT_WELFARE_BUNDLE_REF] = welfare_ref
    state.artifacts_index[ARTIFACT_OPTIMIZATION_AMBIGUITY_CERTIFICATE_REF] = ambiguity_ref

    outcome = BuildPolicyOutputBundleNode().execute(
        _claim_capable_context(execution_context), state
    )

    assert outcome.status == "ok"
    assert ARTIFACT_POLICY_OUTPUT_BUNDLE_REF in outcome.state.artifacts_index
    assert any(
        event.code == "policy_output_bundle.optional_artifact_degraded"
        and event.attrs.get("reason") == "distributional_report_load_failed"
        for event in outcome.events
    )


def test_build_policy_output_bundle_degrades_invalid_uncertainty_envelope(
    execution_context,
    minimal_state,
    cas_store,
) -> None:
    candidate = _candidate()
    welfare_ref, ambiguity_ref = _phase3_ready_refs(cas_store)
    invalid_ref = cas_store.put_json(
        ["invalid"],
        PutOptions(kind="ir.uncertainty_envelope", media_type="application/json"),
    )
    state = minimal_state.model_copy(deep=True)
    state.params.update(
        {
            "workflow_id": "scientist_policy_design",
            "policy_mode": True,
            "policy_candidate_schema": candidate.model_dump(mode="json"),
            "policy_evaluation": _evaluation_vector(candidate).model_dump(mode="json"),
            "decision_readiness_contract": _readiness_contract().model_dump(mode="json"),
            "policy_brief": _policy_brief().model_dump(mode="json"),
            "translator_compliance": _translator_compliance().model_dump(mode="json"),
            "judge_verdict": _passing_judge_verdict(),
        }
    )
    state.artifacts_index[ARTIFACT_CAUSAL_ENVELOPE_REF] = invalid_ref
    state.artifacts_index[ARTIFACT_WELFARE_BUNDLE_REF] = welfare_ref
    state.artifacts_index[ARTIFACT_OPTIMIZATION_AMBIGUITY_CERTIFICATE_REF] = ambiguity_ref

    outcome = BuildPolicyOutputBundleNode().execute(
        _claim_capable_context(execution_context), state
    )

    assert outcome.status == "ok"
    assert ARTIFACT_POLICY_OUTPUT_BUNDLE_REF in outcome.state.artifacts_index
    assert any(
        event.code == "policy_output_bundle.optional_artifact_degraded"
        and event.attrs.get("reason") == "uncertainty_envelope_load_failed"
        for event in outcome.events
    )


def test_build_policy_output_bundle_uses_branch_state_for_declared_outputs(
    execution_context,
    minimal_state,
):
    candidate = _candidate()
    welfare_ref, ambiguity_ref = _phase3_ready_refs(execution_context.store)
    state = minimal_state.model_copy(deep=True)
    state.params.update(
        {
            "workflow_id": "scientist_policy_design",
            "policy_mode": True,
            "policy_candidate_schema": candidate.model_dump(mode="json"),
            "policy_evaluation": _evaluation_vector(candidate).model_dump(mode="json"),
            "decision_readiness_contract": _readiness_contract().model_dump(mode="json"),
            "policy_brief": _policy_brief().model_dump(mode="json"),
            "translator_compliance": _translator_compliance().model_dump(mode="json"),
            "judge_verdict": _passing_judge_verdict(),
            "nested": {"baseline": True},
        }
    )
    state.artifacts_index[ARTIFACT_WELFARE_BUNDLE_REF] = welfare_ref
    state.artifacts_index[ARTIFACT_OPTIMIZATION_AMBIGUITY_CERTIFICATE_REF] = ambiguity_ref
    observed: dict[str, tuple[str, ...]] = {}

    def _spy_branch(base_state, *, write_paths=()):
        observed["write_paths"] = tuple(write_paths)
        return real_branch_state(base_state, write_paths=write_paths)

    with patch(
        "polisyos.scientist.nodes.builtins.decide.build_policy_output_bundle.branch_state",
        _spy_branch,
    ):
        outcome = BuildPolicyOutputBundleNode().execute(
            _claim_capable_context(execution_context), state
        )

    assert outcome.status == "ok"
    assert observed["write_paths"] == (
        "policy_output_bundle_ref",
        "policy_brief_ref",
        "champion_policy_dossier_ref",
        "artifacts_index.policy_output_bundle_ref",
        "artifacts_index.policy_frontier_report_ref",
        "artifacts_index.champion_policy_dossier_ref",
        "artifacts_index.claims_ref",
        "artifacts_index.policy_brief_ref",
        "artifacts_index.constraint_satisfaction_report_ref",
        "artifacts_index.subgroup_impact_report_ref",
        "artifacts_index.policy_uncertainty_report_ref",
        "artifacts_index.policy_transportability_report_ref",
        "artifacts_index.governance_gate_packet_ref",
        "artifacts_index.implementation_plan_ref",
        "artifacts_index.rejected_alternatives_summary_ref",
        "artifacts_index.replayable_audit_bundle_ref",
        "artifacts_index.decision_readiness_contract_ref",
        "artifacts_index.validation_report_ref",
        "artifacts_index.judge_verdict_ref",
    )
    assert state.params["nested"] == {"baseline": True}
    assert state.policy_output_bundle_ref is None
    assert ARTIFACT_POLICY_OUTPUT_BUNDLE_REF not in state.artifacts_index
    assert outcome.state.policy_output_bundle_ref is not None
    assert ARTIFACT_POLICY_OUTPUT_BUNDLE_REF in outcome.state.artifacts_index


def test_decision_packet_not_mutated_when_policy_bundle_absent(tmp_path) -> None:
    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.core.registry import build_default_registry_bundle
    from polisyos.core.run.context import RunContext
    from polisyos.scientist.orchestration.engine.context import ExecutionContext
    from polisyos.scientist.orchestration.engine.state import ExperimentState

    store = FileSystemCAS(tmp_path)
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(
        store=store, registry_bundle=registry_bundle, run_id="R_packet_no_policy"
    )
    import logging

    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger("test.packet"))

    trinity_ref = store.put_json(
        {"trinity": {}},
        PutOptions(
            kind="ir.trinity_bundle",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.ir.TrinityBundle", version="1.0"),
        ),
    )
    data_snapshot_ref = store.put_json(
        {"data_ref": None},
        PutOptions(kind="fabric.data_snapshot", media_type="application/json"),
    )
    state = ExperimentState(
        run_id="R_packet_no_policy",
        inputs={
            INPUT_TRINITY_BUNDLE_REF: trinity_ref,
            INPUT_REGISTRY_BUNDLE_REF: registry_bundle,
            INPUT_DATA_SNAPSHOT_REF: data_snapshot_ref,
        },
        params={"random_seed": 1},
    )

    outcome = BuildDecisionPacketNode().execute(ctx, state)
    payload = from_canonical_bytes(store.get_bytes(outcome.artifacts[0].artifact_id))

    assert "policy_output_bundle" not in payload


def test_decision_packet_records_degraded_path_for_invalid_policy_bundle(tmp_path) -> None:
    import logging

    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.core.registry import build_default_registry_bundle
    from polisyos.core.run.context import RunContext
    from polisyos.scientist.orchestration.engine.context import ExecutionContext
    from polisyos.scientist.orchestration.engine.state import ExperimentState

    store = FileSystemCAS(tmp_path)
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(
        store=store,
        registry_bundle=registry_bundle,
        run_id="R_packet_invalid_policy_bundle",
    )
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger("test.packet.policy"))

    trinity_ref = store.put_json(
        {"trinity": {}},
        PutOptions(
            kind="ir.trinity_bundle",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.ir.TrinityBundle", version="1.0"),
        ),
    )
    data_snapshot_ref = store.put_json(
        {"data_ref": None},
        PutOptions(kind="fabric.data_snapshot", media_type="application/json"),
    )
    invalid_policy_bundle_ref = store.put_json(
        ["invalid"],
        PutOptions(kind="scientist.policy_output_bundle", media_type="application/json"),
    )
    state = ExperimentState(
        run_id="R_packet_invalid_policy_bundle",
        inputs={
            INPUT_TRINITY_BUNDLE_REF: trinity_ref,
            INPUT_REGISTRY_BUNDLE_REF: registry_bundle,
            INPUT_DATA_SNAPSHOT_REF: data_snapshot_ref,
        },
        artifacts_index={ARTIFACT_POLICY_OUTPUT_BUNDLE_REF: invalid_policy_bundle_ref},
        params={"random_seed": 1, "judge_verdict": _passing_judge_verdict()},
    )

    outcome = BuildDecisionPacketNode().execute(ctx, state)
    payload = from_canonical_bytes(store.get_bytes(outcome.artifacts[0].artifact_id))
    degraded_reasons = [item["reason"] for item in payload["degraded_paths"]]

    assert "policy_output_bundle" not in payload
    assert "policy_output_bundle_load_failed" in degraded_reasons
    assert payload["analysis_limits"]["decision_packet_degraded"] is True


def test_owner_basis_covers_inline_and_trinity_sources_across_resolver_routes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fresh consumers recompute inline and Trinity source branches from attempt inputs."""
    import asyncio
    import logging

    from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
    from polisyos.core.registry import build_default_registry_bundle
    from polisyos.core.run.context import RunContext
    from polisyos.core.trace.record import TraceRecord
    from polisyos.scientist.nodes.builtins.decide import (
        policy_runtime_request as runtime_request_module,
    )
    from polisyos.scientist.nodes.builtins.decide import (
        run_policy_translation as translation_module,
    )
    from polisyos.scientist.nodes.builtins.decide import (
        run_translator_compliance as compliance_module,
    )
    from polisyos.scientist.nodes.builtins.decide.build_policy_output_bundle import (
        _candidate_source_pointer,
    )
    from polisyos.scientist.nodes.builtins.decide.build_policy_output_bundle import (
        _resolve_candidate as build_resolve_candidate,
    )
    from polisyos.scientist.nodes.builtins.decide.policy_runtime_request import (
        resolve_policy_runtime_request,
    )
    from polisyos.scientist.nodes.builtins.decide.run_policy_translation import (
        RunPolicyTranslationNode,
    )
    from polisyos.scientist.nodes.builtins.decide.run_translator_compliance import (
        RunTranslatorComplianceNode,
    )
    from polisyos.scientist.orchestration.engine.async_executor import AsyncWorkflowExecutor
    from polisyos.scientist.orchestration.engine.context import (
        ExecutionContext,
        _EngineInvocationBinding,
    )
    from polisyos.scientist.orchestration.engine.executor import WorkflowExecutor
    from polisyos.scientist.orchestration.engine.protocol import NodeError, NodeOutcome, NodeSpec
    from polisyos.scientist.orchestration.engine.registry import NodeRegistry
    from polisyos.scientist.orchestration.engine.retry import RetryPolicy
    from polisyos.scientist.orchestration.engine.state import ExperimentState
    from polisyos.scientist.orchestration.engine.workflow_spec import NodeInvocation, WorkflowSpec
    from polisyos.scientist.policy_design.phase3 import (
        _resolve_candidate as phase3_resolve_candidate,
    )
    from polisyos.scientist.policy_design.schema import persist_policy_candidate_schema

    store = FileSystemCAS(tmp_path)
    registry_bundle_ref = build_default_registry_bundle(
        store, return_selected_profile=True
    ).bundle_ref
    candidate_a = _candidate().model_copy(update={"candidate_id": "inline_candidate_a"})
    candidate_b = _candidate().model_copy(update={"candidate_id": "inline_candidate_b"})
    ref_b = persist_policy_candidate_schema(store, candidate_b, return_selected_profile=True)
    trinity_ref = store.put_json(
        _bundle(),
        PutOptions(
            kind=TrinityBundle.ARTIFACT_KIND,
            media_type=TrinityBundle.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=TrinityBundle.ARTIFACT_SCHEMA_NAME,
                version=TrinityBundle.ARTIFACT_SCHEMA_VERSION,
            ),
        ),
    )
    component_id = ComponentId.parse("scientist.node_candidate_origin_branches@1.0.0")
    selected: list[tuple[str | None, ArtifactRef | None]] = []
    route_selections: list[tuple[str, ArtifactRef | None]] = []

    class _CandidateResolverReached(Exception):
        """Stop a public caller immediately after its shared candidate resolution."""

    def _capture_candidate(
        _ctx: ExecutionContext,
        _state: ExperimentState,
        candidate: PolicyCandidateSchema,
        candidate_ref: ArtifactRef | None,
        *_args: object,
    ) -> NoReturn:
        route_selections.append((candidate.candidate_id, candidate_ref))
        raise _CandidateResolverReached

    class CandidateOriginBranchNode:
        def __init__(self) -> None:
            self.calls = 0
            self._spec = NodeSpec(
                metadata=ComponentMetadata(
                    component_id=component_id,
                    kind=ComponentKind.SCIENTIST_NODE,
                    abi_targets={"world_abi": "1.x"},
                    display_name="Candidate Origin Branch Probe",
                    description="Exercises the real candidate source selection branches.",
                    capabilities=Capability.SCIENTIST_NODE,
                )
            )

        @property
        def spec(self) -> NodeSpec:
            return self._spec

        def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
            self.calls += 1
            candidate, candidate_ref = build_resolve_candidate(ctx, state)
            phase3_candidate = phase3_resolve_candidate(ctx, state)
            assert candidate is not None and phase3_candidate is not None
            assert phase3_candidate.candidate_id == candidate.candidate_id
            selected.append((candidate.candidate_id, candidate_ref))
            # This user-emitted event claims another branch after selection.
            ctx.run.emit("runtime.parameters", "RUNTIME_PARAMETER_SELECTED", outputs=[ref_b])
            if self.calls == 1:
                return NodeOutcome(
                    status="fail",
                    state=state,
                    error=NodeError(code="node.exception", message="retry origin probe"),
                )
            return NodeOutcome(status="ok", state=state)

    cases: tuple[
        tuple[str, dict[str, object], dict[str, object], tuple[str, ArtifactRef | None], str, bool],
        ...,
    ] = (
        (
            "inline",
            {
                "policy_candidate_schema": candidate_a.model_dump(mode="json"),
                "policy_candidate_ref": ref_b.model_dump(mode="json"),
            },
            {},
            ("inline_candidate_a", None),
            "/params/policy_candidate_schema",
            False,
        ),
        (
            "trinity",
            {"policy_candidate_id": "candidate_from_trinity"},
            {INPUT_TRINITY_BUNDLE_REF: trinity_ref},
            ("candidate_from_trinity", trinity_ref),
            f"/inputs/{INPUT_TRINITY_BUNDLE_REF}",
            True,
        ),
    )
    for run_name, params, inputs, expected, expected_pointer, use_async in cases:
        run_id = f"R_candidate_origin_{run_name}"
        run = RunContext.start(
            store=store,
            registry_bundle=registry_bundle_ref,
            run_id=run_id,
        )
        ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger(run_id))
        state = ExperimentState(run_id=run_id, params=params, inputs=inputs)
        registry = NodeRegistry()
        registry.register(CandidateOriginBranchNode())
        workflow = WorkflowSpec(
            workflow_id="candidate_origin_branches",
            nodes=[
                NodeInvocation(
                    alias="resolve",
                    node_id=component_id,
                    retry=RetryPolicy(max_retries=1, backoff_base_s=0.1, jitter="none"),
                )
            ],
        )
        if use_async:
            asyncio.run(AsyncWorkflowExecutor(ctx, registry).execute(workflow, state))
        else:
            WorkflowExecutor(ctx, registry).execute(workflow, state)

        attempts = run.read_runtime_invocation_attempts()
        matching = sorted(
            (attempt for attempt in attempts if attempt.basis.node_alias == "resolve"),
            key=lambda attempt: attempt.basis.attempt_number,
        )
        assert len(matching) == 2
        assert [attempt.outcome.status for attempt in matching if attempt.outcome is not None] == [
            "fail",
            "ok",
        ]
        failed_attempt, attempt = matching
        assert failed_attempt.outcome is not None
        for recorded_attempt in matching:
            source_state = ExperimentState.model_validate(
                from_canonical_bytes(store.get_bytes(recorded_attempt.basis.input_state_ref))
            )
            attempt_ctx = ExecutionContext(
                store=store,
                run=run,
                logger=logging.getLogger(f"{run_id}.attempt"),
                _engine_invocation=_EngineInvocationBinding(
                    run_id=run_id,
                    attempt_id=recorded_attempt.basis.attempt_id,
                    basis_ref=recorded_attempt.basis_ref,
                ),
            )
            source_candidate, source_ref = build_resolve_candidate(attempt_ctx, source_state)
            assert source_candidate is not None
            assert (source_candidate.candidate_id, source_ref) == expected
            if recorded_attempt.outcome is failed_attempt.outcome:
                success_required_ctx = ExecutionContext(
                    store=store,
                    run=run,
                    logger=logging.getLogger(f"{run_id}.failed"),
                    _engine_invocation=_EngineInvocationBinding(
                        run_id=run_id,
                        attempt_id=recorded_attempt.basis.attempt_id,
                        basis_ref=recorded_attempt.basis_ref,
                        require_successful_completion=True,
                    ),
                )
                with pytest.raises(
                    ValueError,
                    match="runtime_candidate_invocation_not_successful",
                ):
                    build_resolve_candidate(success_required_ctx, source_state)
        source_state = ExperimentState.model_validate(
            from_canonical_bytes(store.get_bytes(attempt.basis.input_state_ref))
        )
        fresh_ctx = ExecutionContext(
            store=store,
            run=run,
            logger=logging.getLogger(f"{run_id}.fresh"),
            _engine_invocation=_EngineInvocationBinding(
                run_id=run_id,
                attempt_id=attempt.basis.attempt_id,
                basis_ref=attempt.basis_ref,
                require_successful_completion=True,
            ),
        )
        assert _candidate_source_pointer(source_state) == expected_pointer
        candidate, candidate_ref = build_resolve_candidate(fresh_ctx, source_state)
        assert candidate is not None
        assert (candidate.candidate_id, candidate_ref) == expected

        route_state = source_state.model_copy(deep=True)
        route_state.params["policy_brief"] = _policy_brief().model_dump(mode="json")

        with monkeypatch.context() as route_probe:
            route_probe.setattr(
                runtime_request_module, "ensure_policy_candidate_ref", _capture_candidate
            )
            with pytest.raises(_CandidateResolverReached):
                resolve_policy_runtime_request(fresh_ctx, source_state)
        assert route_selections.pop() == expected

        def _always_policy_mode(_state: ExperimentState) -> bool:
            return True

        def _always_brief_required(_readiness: object) -> bool:
            return True

        def _parsed_runner_model(_value: object, _model_type: type[object]) -> object:
            from types import SimpleNamespace

            return SimpleNamespace(
                promotion_decision=SimpleNamespace(promoted=True),
            )

        def _readiness_for_route(
            _ctx: ExecutionContext,
            _state: ExperimentState,
            _readiness_ref: ArtifactRef | None,
        ) -> DecisionReadinessContract:
            return _readiness_contract()

        for caller_module, caller_node in (
            (translation_module, RunPolicyTranslationNode()),
            (compliance_module, RunTranslatorComplianceNode()),
        ):
            with monkeypatch.context() as route_probe:
                route_probe.setattr(caller_module, "_is_policy_mode", _always_policy_mode)
                route_probe.setattr(
                    caller_module, "_resolve_readiness_contract", _readiness_for_route
                )
                route_probe.setattr(caller_module, "_brief_required", _always_brief_required)
                route_probe.setattr(caller_module, "_parse_model", _parsed_runner_model)
                route_probe.setattr(caller_module, "_policy_build_input", _capture_candidate)
                with pytest.raises(_CandidateResolverReached):
                    caller_node.execute(fresh_ctx, route_state)
            assert route_selections.pop() == expected
        phase3_candidate = phase3_resolve_candidate(fresh_ctx, source_state)
        assert phase3_candidate is not None
        assert phase3_candidate.candidate_id == expected[0]
        assert selected[-1] == expected

        # The generic trace can be removed without changing the recomputed selection.
        trace_path = run.trace_path
        assert trace_path is not None
        trace_records = [
            TraceRecord.model_validate_json(line)
            for line in trace_path.read_bytes().splitlines()
            if line.strip()
        ]
        assert any(record.event == "RUNTIME_PARAMETER_SELECTED" for record in trace_records)
        retained = [
            record.model_dump_json().encode("utf-8")
            for record in trace_records
            if record.event != "RUNTIME_PARAMETER_SELECTED"
        ]
        trace_path.write_bytes(b"\n".join(retained) + b"\n")
        candidate_after_trace_removal, ref_after_trace_removal = build_resolve_candidate(
            fresh_ctx,
            source_state,
        )
        assert candidate_after_trace_removal is not None
        assert (candidate_after_trace_removal.candidate_id, ref_after_trace_removal) == expected

        # Duplicate owner records are ambiguous and must not select a convenient match.
        with monkeypatch.context() as duplicate_probe:
            duplicate_probe.setattr(
                RunContext,
                "read_runtime_invocation_attempts",
                lambda _run, exact=attempt: [exact, exact],
            )
            with pytest.raises(
                ValueError,
                match="runtime_candidate_invocation_basis_not_owner_linked",
            ):
                build_resolve_candidate(fresh_ctx, source_state)


def test_engine_accepted_output_bundle_retains_the_exact_candidate_source(
    execution_context: ExecutionContext,
    minimal_state: ExperimentState,
    cas_store: FileSystemCAS,
) -> None:
    """The completed engine attempt joins its exact candidate to the persisted bundle."""
    import logging

    from polisyos.core.registry import build_default_registry_bundle
    from polisyos.core.run.context import RunContext
    from polisyos.scientist.nodes.builtins.decide.build_policy_output_bundle import (
        BuildPolicyOutputBundleNode,
    )
    from polisyos.scientist.nodes.builtins.state_keys import (
        ARTIFACT_OPTIMIZATION_AMBIGUITY_CERTIFICATE_REF,
        ARTIFACT_POLICY_OUTPUT_BUNDLE_REF,
        ARTIFACT_WELFARE_BUNDLE_REF,
    )
    from polisyos.scientist.orchestration.engine.context import (
        ExecutionContext,
        _EngineInvocationBinding,
    )
    from polisyos.scientist.orchestration.engine.executor import WorkflowExecutor
    from polisyos.scientist.orchestration.engine.registry import NodeRegistry
    from polisyos.scientist.orchestration.engine.state import ExperimentState
    from polisyos.scientist.orchestration.engine.workflow_spec import NodeInvocation, WorkflowSpec
    from polisyos.scientist.policy_design.output import load_replayable_audit_bundle
    from polisyos.scientist.policy_design.schema import persist_policy_candidate_schema

    registry_bundle_ref = build_default_registry_bundle(
        cas_store,
        return_selected_profile=True,
    ).bundle_ref
    run = RunContext.start(
        store=cas_store,
        registry_bundle=registry_bundle_ref,
        run_id="R_candidate_output_origin",
    )
    execution_context = ExecutionContext(
        store=cas_store,
        run=run,
        logger=logging.getLogger("test.candidate-output-origin"),
    )
    candidate = _candidate()
    expected_candidate_id = candidate.candidate_id
    selected_ref = persist_policy_candidate_schema(
        cas_store,
        candidate,
        return_selected_profile=True,
    )
    forged_candidate = candidate.model_copy(update={"candidate_id": "forged_candidate_b"})
    forged_ref = persist_policy_candidate_schema(
        cas_store,
        forged_candidate,
        return_selected_profile=True,
    )
    execution_context.run.emit(
        "runtime.parameters",
        "RUNTIME_PARAMETER_SELECTED",
        outputs=[forged_ref],
    )
    welfare_ref, ambiguity_ref = _phase3_ready_refs(cas_store)
    state = minimal_state.model_copy(
        update={"run_id": run.run_manifest.run_id},
        deep=True,
    )
    state.inputs["registry_bundle_ref"] = registry_bundle_ref
    state.params.update(
        {
            "workflow_id": "scientist_policy_design",
            "policy_mode": True,
            "policy_candidate_ref": selected_ref.model_dump(mode="json"),
            "policy_evaluation": _evaluation_vector(candidate).model_dump(mode="json"),
            "decision_readiness_contract": _readiness_contract().model_dump(mode="json"),
            "policy_brief": _policy_brief().model_dump(mode="json"),
            "translator_compliance": _translator_compliance().model_dump(mode="json"),
            "judge_verdict": _passing_judge_verdict(),
        }
    )
    state.artifacts_index[ARTIFACT_WELFARE_BUNDLE_REF] = welfare_ref
    state.artifacts_index[ARTIFACT_OPTIMIZATION_AMBIGUITY_CERTIFICATE_REF] = ambiguity_ref

    node = BuildPolicyOutputBundleNode()
    registry = NodeRegistry()
    registry.register(node)
    workflow = WorkflowSpec(
        workflow_id="candidate_output_origin_probe",
        nodes=[NodeInvocation(alias="build_bundle", node_id=node.spec.metadata.component_id)],
    )
    WorkflowExecutor(_claim_capable_context(execution_context), registry).execute(
        workflow,
        state,
    )
    attempts = execution_context.run.read_runtime_invocation_attempts()
    matching = [attempt for attempt in attempts if attempt.basis.node_alias == "build_bundle"]
    assert len(matching) == 1
    attempt = matching[0]
    assert attempt.outcome is not None and attempt.outcome.status == "ok"
    assert attempt.outcome.output_refs
    assert attempt.outcome.outcome_state_ref is not None
    outcome_state = ExperimentState.model_validate(
        from_canonical_bytes(cas_store.get_bytes(attempt.outcome.outcome_state_ref))
    )
    bundle_ref = outcome_state.artifacts_index[ARTIFACT_POLICY_OUTPUT_BUNDLE_REF]
    assert bundle_ref in attempt.outcome.output_refs
    bundle = load_policy_artifact_bundle(cas_store, bundle_ref)
    audit = load_replayable_audit_bundle(cas_store, bundle.replayable_audit_bundle_ref)
    assert audit.candidate_ref == selected_ref

    builder_output_refs = (
        bundle_ref,
        bundle.policy_frontier_report_ref,
        bundle.champion_policy_dossier_ref,
        bundle.policy_brief_ref,
        bundle.constraint_satisfaction_report_ref,
        bundle.subgroup_impact_report_ref,
        bundle.uncertainty_report_ref,
        bundle.transportability_report_ref,
        bundle.governance_gate_packet_ref,
        bundle.implementation_plan_ref,
        bundle.rejected_alternatives_summary_ref,
        bundle.replayable_audit_bundle_ref,
        bundle.claims_ref,
    )
    for output_ref in builder_output_refs:
        if output_ref is None:
            continue
        output_manifest = cas_store.get_manifest(output_ref)
        candidate_inputs = [item for item in output_manifest.inputs if item.role == "candidate"]
        assert len(candidate_inputs) == 1, output_ref.kind
        assert candidate_inputs[0].artifact_id == selected_ref.artifact_id, output_ref.kind
        assert (
            candidate_inputs[0].manifest_profile_sha256 == selected_ref.manifest_profile_sha256
        ), output_ref.kind

    basis_state = ExperimentState.model_validate(
        from_canonical_bytes(cas_store.get_bytes(attempt.basis.input_state_ref))
    )
    fresh_ctx = ExecutionContext(
        store=cas_store,
        run=execution_context.run,
        logger=execution_context.logger,
        _engine_invocation=_EngineInvocationBinding(
            run_id=execution_context.run.run_manifest.run_id,
            attempt_id=attempt.basis.attempt_id,
            basis_ref=attempt.basis_ref,
            require_successful_completion=True,
        ),
    )
    resolved_candidate, candidate_ref = _resolve_candidate(fresh_ctx, basis_state)
    assert resolved_candidate is not None
    assert resolved_candidate.candidate_id == expected_candidate_id
    assert audit.candidate_ref == selected_ref and candidate_ref == selected_ref


def test_translator_cache_key_includes_the_candidate_source_before_reuse(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A cache hit must not reuse candidate A's compliance after the input changes to B."""
    import logging
    from types import SimpleNamespace

    from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
    from polisyos.core.registry import build_default_registry_bundle
    from polisyos.core.run.context import RunContext
    from polisyos.core.trace.record import TraceRecord
    from polisyos.scientist.nodes.builtins.decide.run_translator_compliance import (
        RunTranslatorComplianceNode,
        TranslatorComplianceResult,
    )
    from polisyos.scientist.orchestration.engine.context import (
        ExecutionContext,
    )
    from polisyos.scientist.orchestration.engine.executor import WorkflowExecutor
    from polisyos.scientist.orchestration.engine.protocol import NodeOutcome, NodeSpec
    from polisyos.scientist.orchestration.engine.registry import NodeRegistry
    from polisyos.scientist.orchestration.engine.state import ExperimentState
    from polisyos.scientist.orchestration.engine.state_branching import branch_state
    from polisyos.scientist.orchestration.engine.workflow_spec import NodeInvocation, WorkflowSpec
    from polisyos.scientist.policy_design.schema import persist_policy_candidate_schema

    store = FileSystemCAS(tmp_path)
    registry_bundle_ref = build_default_registry_bundle(
        store, return_selected_profile=True
    ).bundle_ref
    run = RunContext.start(
        store=store,
        registry_bundle=registry_bundle_ref,
        run_id="R_candidate_cache_origin",
    )
    base_ctx = ExecutionContext(
        store=store,
        run=run,
        logger=logging.getLogger("test.candidate-cache-origin"),
    )
    ctx = _claim_capable_context(base_ctx)
    candidate_a = _candidate().model_copy(update={"candidate_id": "cache_candidate_a"})
    candidate_b = _candidate().model_copy(update={"candidate_id": "cache_candidate_b"})
    ref_a = persist_policy_candidate_schema(store, candidate_a, return_selected_profile=True)
    ref_b = persist_policy_candidate_schema(store, candidate_b, return_selected_profile=True)
    brief = _policy_brief()
    readiness = _readiness_contract()
    promotion = SimpleNamespace(
        promotion_decision=SimpleNamespace(promoted=True),
        readiness_ref=None,
        judge_verdict=None,
    )
    evaluated_candidates: list[str] = []
    builder = SimpleNamespace(
        _build_constraint_report=lambda _source: object(),
        _build_subgroup_report=lambda _source: object(),
        _build_uncertainty_report=lambda _source: object(),
        _build_transportability_report=lambda _source: object(),
        _build_governance_gate_packet=lambda _source: object(),
        _build_implementation_plan=lambda _source: object(),
        _build_dossier=lambda *, source, **_kwargs: SimpleNamespace(
            candidate_id=source.candidate.candidate_id
        ),
    )

    class CandidateSourceSwitchNode:
        def __init__(self) -> None:
            self._spec = NodeSpec(
                metadata=ComponentMetadata(
                    component_id=ComponentId.parse("scientist.node_candidate_source_switch@1.0.0"),
                    kind=ComponentKind.SCIENTIST_NODE,
                    abi_targets={"world_abi": "1.x"},
                    display_name="Candidate Source Switch",
                    description="Changes only the selected candidate artifact input.",
                    capabilities=Capability.SCIENTIST_NODE,
                ),
                state_reads=["params.policy_candidate_ref"],
                state_writes=["params.policy_candidate_ref"],
            )

        @property
        def spec(self) -> NodeSpec:
            return self._spec

        def execute(self, _ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
            next_state = branch_state(
                state,
                write_paths=self._spec.state_writes,
            ).state
            next_state.params["policy_candidate_ref"] = ref_b.model_dump(mode="json")
            return NodeOutcome(status="ok", state=next_state)

    compliance_node = RunTranslatorComplianceNode()
    switch_node = CandidateSourceSwitchNode()
    registry = NodeRegistry()
    registry.register(compliance_node)
    registry.register(switch_node)
    state = ExperimentState(
        run_id=run.run_manifest.run_id,
        inputs={"registry_bundle_ref": registry_bundle_ref},
        params={
            "workflow_id": "scientist_policy_design",
            "policy_mode": True,
            "policy_candidate_ref": ref_a.model_dump(mode="json"),
            "policy_brief": brief.model_dump(mode="json"),
            "policy_promotion_result": {"promotion_decision": {"promoted": True}},
        },
    )
    workflow = WorkflowSpec(
        workflow_id="candidate_cache_origin_probe",
        nodes=[
            NodeInvocation(
                alias="compliance_a",
                node_id=compliance_node.spec.metadata.component_id,
            ),
            NodeInvocation(
                alias="switch_candidate",
                node_id=switch_node.spec.metadata.component_id,
                depends_on=["compliance_a"],
            ),
            NodeInvocation(
                alias="compliance_b",
                node_id=compliance_node.spec.metadata.component_id,
                depends_on=["switch_candidate"],
            ),
            NodeInvocation(
                alias="compliance_b_cached",
                node_id=compliance_node.spec.metadata.component_id,
                depends_on=["compliance_b"],
            ),
        ],
    )

    from unittest.mock import patch

    def build_input(_ctx, _state, candidate, candidate_ref, _readiness, _promotion):
        return SimpleNamespace(candidate=candidate, candidate_ref=candidate_ref)

    def evaluate(_brief, *, dossier, **_kwargs):
        evaluated_candidates.append(dossier.candidate_id)
        return TranslatorComplianceResult(
            passed=True,
            metadata={"candidate_id": dossier.candidate_id},
        )

    with (
        patch(
            "polisyos.scientist.nodes.builtins.decide.run_translator_compliance._resolve_readiness_contract",
            return_value=readiness,
        ),
        patch(
            "polisyos.scientist.nodes.builtins.decide.run_translator_compliance._brief_required",
            return_value=True,
        ),
        patch(
            "polisyos.scientist.nodes.builtins.decide.run_translator_compliance._parse_model",
            side_effect=[brief, promotion, brief, promotion],
        ),
        patch(
            "polisyos.scientist.nodes.builtins.decide.run_translator_compliance._policy_build_input",
            side_effect=build_input,
        ),
        patch(
            "polisyos.scientist.nodes.builtins.decide.run_translator_compliance.PolicyArtifactBuilder",
            return_value=builder,
        ),
        patch(
            "polisyos.scientist.nodes.builtins.decide.run_translator_compliance.TranslatorCompliancePass.evaluate",
            side_effect=evaluate,
        ),
    ):
        result = WorkflowExecutor(ctx, registry).execute(workflow, state)

    attempts = run.read_runtime_invocation_attempts()
    compliance_attempts = [
        attempt for attempt in attempts if attempt.basis.node_alias.startswith("compliance_")
    ]
    assert [attempt.basis.node_alias for attempt in compliance_attempts] == [
        "compliance_a",
        "compliance_b",
    ]
    assert evaluated_candidates == ["cache_candidate_a", "cache_candidate_b"]
    assert result.state.params["policy_candidate_ref"] == ref_b.model_dump(mode="json")
    compliance_value = result.state.params.get("translator_compliance")
    assert isinstance(compliance_value, dict)
    metadata = compliance_value.get("metadata")
    assert isinstance(metadata, dict)
    assert metadata.get("candidate_id") == "cache_candidate_b"
    trace_path = run.trace_path
    assert trace_path is not None
    trace_records = [
        TraceRecord.model_validate_json(line)
        for line in trace_path.read_bytes().splitlines()
        if line.strip()
    ]
    assert not any(
        record.phase == "scientist.node.compliance_b" and record.event == "NODE_CACHE_HIT"
        for record in trace_records
    )
    assert any(
        record.phase == "scientist.node.compliance_b_cached" and record.event == "NODE_CACHE_HIT"
        for record in trace_records
    )
    assert not any(attempt.basis.node_alias == "compliance_b_cached" for attempt in attempts)


def test_candidate_selector_state_reads_bind_every_shared_cache_key(tmp_path: Path) -> None:
    """Each runtime source selector changes cache identity at all four consumers."""
    from polisyos.core.artifacts.manifest import InputRef
    from polisyos.scientist.nodes.builtins.decide.run_policy_blueprint_runtime import (
        RunPolicyBlueprintRuntimeNode,
    )
    from polisyos.scientist.nodes.builtins.decide.run_policy_translation import (
        RunPolicyTranslationNode,
    )
    from polisyos.scientist.nodes.builtins.decide.run_translator_compliance import (
        RunTranslatorComplianceNode,
    )
    from polisyos.scientist.orchestration.engine.idempotency import compute_idempotency_key
    from polisyos.scientist.orchestration.engine.state import ExperimentState
    from polisyos.scientist.policy_design.schema import persist_policy_candidate_schema

    store = FileSystemCAS(tmp_path)
    candidate_a = _candidate().model_copy(update={"candidate_id": "cache_selector_a"})
    candidate_b = _candidate().model_copy(update={"candidate_id": "cache_selector_b"})
    ref_a = persist_policy_candidate_schema(store, candidate_a, return_selected_profile=True)
    ref_b = persist_policy_candidate_schema(store, candidate_b, return_selected_profile=True)
    anchor_ref = store.put_json(
        {"anchor": "candidate-trinity-profile"},
        PutOptions(kind="test.candidate_anchor", media_type="application/json"),
    )
    trinity_options = PutOptions(
        kind=TrinityBundle.ARTIFACT_KIND,
        media_type=TrinityBundle.ARTIFACT_MEDIA_TYPE,
        schema=SchemaInfo(
            name=TrinityBundle.ARTIFACT_SCHEMA_NAME,
            version=TrinityBundle.ARTIFACT_SCHEMA_VERSION,
        ),
    )
    trinity_a = store.put_json(_bundle(), trinity_options, return_selected_profile=True)
    trinity_b = store.put_json(
        _bundle(),
        PutOptions(
            kind=TrinityBundle.ARTIFACT_KIND,
            media_type=TrinityBundle.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=TrinityBundle.ARTIFACT_SCHEMA_NAME,
                version=TrinityBundle.ARTIFACT_SCHEMA_VERSION,
            ),
            inputs=[InputRef(artifact_id=anchor_ref.artifact_id, role="basis")],
        ),
        return_selected_profile=True,
    )
    assert trinity_a.artifact_id == trinity_b.artifact_id
    assert trinity_a.manifest_profile_sha256 != trinity_b.manifest_profile_sha256

    def selected_state(params: dict[str, object], inputs: dict[str, object]) -> ExperimentState:
        return ExperimentState(run_id="R_candidate_cache_selectors", params=params, inputs=inputs)

    selector_pairs = {
        "inline-schema": (
            selected_state(
                {"policy_candidate_schema": candidate_a.model_dump(mode="json")},
                {},
            ),
            selected_state(
                {"policy_candidate_schema": candidate_b.model_dump(mode="json")},
                {},
            ),
        ),
        "artifact-ref": (
            selected_state({"policy_candidate_ref": ref_a.model_dump(mode="json")}, {}),
            selected_state({"policy_candidate_ref": ref_b.model_dump(mode="json")}, {}),
        ),
        "trinity-id": (
            selected_state(
                {"policy_candidate_id": "trinity_candidate_a"},
                {INPUT_TRINITY_BUNDLE_REF: trinity_a},
            ),
            selected_state(
                {"policy_candidate_id": "trinity_candidate_b"},
                {INPUT_TRINITY_BUNDLE_REF: trinity_a},
            ),
        ),
        "trinity-full-ref": (
            selected_state(
                {"policy_candidate_id": "trinity_candidate"},
                {INPUT_TRINITY_BUNDLE_REF: trinity_a},
            ),
            selected_state(
                {"policy_candidate_id": "trinity_candidate"},
                {INPUT_TRINITY_BUNDLE_REF: trinity_b},
            ),
        ),
    }
    nodes = (
        BuildPolicyOutputBundleNode(),
        RunPolicyTranslationNode(),
        RunTranslatorComplianceNode(),
        RunPolicyBlueprintRuntimeNode(),
    )
    for node in nodes:
        for selector, (source_a, source_b) in selector_pairs.items():
            assert compute_idempotency_key(node.spec, source_a) != compute_idempotency_key(
                node.spec, source_b
            ), (str(node.spec.metadata.component_id), selector)


@pytest.mark.parametrize("interruption", ["cancel", "timeout"])
def test_interrupted_async_attempt_retains_input_but_not_successful_binding(
    tmp_path: Path, interruption: str
) -> None:
    """Cancelled or timed-out attempts remain source attempts, not successful outputs."""
    import asyncio
    import logging
    from uuid import uuid4

    from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
    from polisyos.core.registry import build_default_registry_bundle
    from polisyos.core.run.context import RunContext
    from polisyos.scientist.nodes.builtins.decide.build_policy_output_bundle import (
        _resolve_candidate,
    )
    from polisyos.scientist.orchestration.engine.async_executor import AsyncWorkflowExecutor
    from polisyos.scientist.orchestration.engine.context import (
        ExecutionContext,
        _EngineInvocationBinding,
    )
    from polisyos.scientist.orchestration.engine.protocol import NodeOutcome, NodeSpec
    from polisyos.scientist.orchestration.engine.registry import NodeRegistry
    from polisyos.scientist.orchestration.engine.state import ExperimentState
    from polisyos.scientist.orchestration.engine.workflow_spec import NodeInvocation, WorkflowSpec
    from polisyos.scientist.policy_design.schema import persist_policy_candidate_schema

    async def exercise() -> None:
        store = FileSystemCAS(tmp_path / interruption)
        bundle_ref = build_default_registry_bundle(store, return_selected_profile=True).bundle_ref
        run_id = f"R_candidate_interrupted_{interruption}_{uuid4().hex[:8]}"
        run = RunContext.start(store=store, registry_bundle=bundle_ref, run_id=run_id)
        ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger(run_id))
        candidate = _candidate().model_copy(update={"candidate_id": f"candidate_{interruption}"})
        candidate_ref = persist_policy_candidate_schema(
            store, candidate, return_selected_profile=True
        )
        started = asyncio.Event()
        component_id = ComponentId.parse("scientist.node_candidate_interruption_probe@1.0.0")

        class WaitingCandidateNode:
            _spec = NodeSpec(
                metadata=ComponentMetadata(
                    component_id=component_id,
                    kind=ComponentKind.SCIENTIST_NODE,
                    abi_targets={"world_abi": "1.x"},
                    display_name="Candidate Interruption Probe",
                    description="Stops after the engine captures the exact input basis.",
                    capabilities=Capability.SCIENTIST_NODE,
                )
            )

            @property
            def spec(self) -> NodeSpec:
                return self._spec

            def execute(self, _ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
                return NodeOutcome(status="fail", state=state)

            async def execute_async(
                self, _ctx: ExecutionContext, state: ExperimentState
            ) -> NodeOutcome:
                started.set()
                await asyncio.Event().wait()
                return NodeOutcome(status="ok", state=state)

        node = WaitingCandidateNode()
        registry = NodeRegistry()
        registry.register(node)
        invocation = NodeInvocation(
            alias="resolve",
            node_id=component_id,
            timeout_s=1.0 if interruption == "timeout" else None,
        )
        workflow = WorkflowSpec(workflow_id="candidate_interruption_probe", nodes=[invocation])
        state = ExperimentState(
            run_id=run_id,
            params={"policy_candidate_ref": candidate_ref.model_dump(mode="json")},
        )
        task = asyncio.create_task(AsyncWorkflowExecutor(ctx, registry).execute(workflow, state))
        await asyncio.wait_for(started.wait(), timeout=3.0)
        if interruption == "cancel":
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        else:
            result = await asyncio.wait_for(task, timeout=3.0)
            assert result.report.status == "fail"

        attempts = run.read_runtime_invocation_attempts()
        matching = [attempt for attempt in attempts if attempt.basis.node_alias == "resolve"]
        assert len(matching) == 1
        attempt = matching[0]
        assert attempt.outcome is not None
        assert attempt.outcome.status == "unknown"
        assert attempt.outcome.outcome_state_ref is None
        source_state = ExperimentState.model_validate(
            from_canonical_bytes(store.get_bytes(attempt.basis.input_state_ref))
        )
        bound_ctx = ExecutionContext(
            store=store,
            run=run,
            logger=logging.getLogger(f"{run_id}.bound"),
            _engine_invocation=_EngineInvocationBinding(
                run_id=run_id,
                attempt_id=attempt.basis.attempt_id,
                basis_ref=attempt.basis_ref,
            ),
        )
        resolved, resolved_ref = _resolve_candidate(bound_ctx, source_state)
        assert resolved is not None
        assert resolved.candidate_id == candidate.candidate_id
        assert resolved_ref == candidate_ref
        success_required_ctx = ExecutionContext(
            store=store,
            run=run,
            logger=logging.getLogger(f"{run_id}.completed-only"),
            _engine_invocation=_EngineInvocationBinding(
                run_id=run_id,
                attempt_id=attempt.basis.attempt_id,
                basis_ref=attempt.basis_ref,
                require_successful_completion=True,
            ),
        )
        with pytest.raises(ValueError, match="runtime_candidate_invocation_not_successful"):
            _resolve_candidate(success_required_ctx, source_state)

    asyncio.run(exercise())
