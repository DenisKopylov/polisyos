from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.canon import from_canonical_bytes
from polisyos.ir.governance.policy_spec import PolicySpec
from polisyos.ir.governance.problem_frame import ProblemDomain, ProblemFrame
from polisyos.ir.model_layer.model_spec import ModelSpec
from polisyos.ir.trinity import TrinityBundle
from polisyos.scientist.methods.search.funnel.level3_medium import Level3MediumFidelity
from polisyos.scientist.methods.search.funnel.level4_full import Level4FullFidelity
from polisyos.scientist.methods.search.funnel.orchestrator import FunnelOrchestrator
from polisyos.scientist.methods.search.funnel.types import (
    FunnelExecutedWorkPacket,
    FunnelStageResult,
)
from polisyos.scientist.nodes.builtins.decide.policy_runtime_support import (
    PolicyRuntimeEvaluationArtifact,
    PolicyRuntimeProvenance,
    build_policy_simulation_results,
    persist_funnel_executed_work_packet,
    persist_policy_evaluation_vector_to_store,
)
from polisyos.scientist.nodes.builtins.decide.run_policy_blueprint_runtime import (
    _PolicyRuntimeWorkflowEngine,
)
from polisyos.scientist.policy_design.objectives import PolicyEvaluationVector
from polisyos.scientist.policy_design.schema import (
    PolicyCandidateSchema,
    persist_policy_candidate_schema,
)

_FULL_CONFIG = {
    "data_config": {"subsample_fraction": 1.0, "stratified": False},
    "estimation_config": {"estimator": "matching", "n_bootstrap": 500},
    "scenario_config": {"grid": "full"},
    "subgroup_config": {"top_k": 99},
    "model_config": {"scm_complexity": "full"},
}
_CONFIG_KEYS = tuple(_FULL_CONFIG)


class _PassingPolicyEvaluationBackend:
    backend_kind = "test_policy_evaluator"

    def evaluate(
        self,
        candidate: PolicyCandidateSchema,
        *,
        fidelity: str,
        simulation_metrics: dict[str, float] | None,
        uncertainty: Any,
        distributional_report: Any,
        causal_effect_report: Any,
        cross_graph_profile: Any,
        governance_report: Any,
        ambiguity_certificate: Any = None,
    ) -> PolicyRuntimeEvaluationArtifact:
        del (
            simulation_metrics,
            distributional_report,
            causal_effect_report,
            cross_graph_profile,
            governance_report,
            ambiguity_certificate,
        )
        vector = PolicyEvaluationVector(candidate_id=candidate.candidate_id, feasible=True)
        provenance = PolicyRuntimeProvenance(
            backend_kind=self.backend_kind,
            fidelity_mode=fidelity,
            promotable_source=False,
            degradation_mode="test_fixture",
            source_components=("test_policy_evaluator",),
            notes=("Test fixture; no scientific draw loop is exercised.",),
        )
        metrics = {"gdp_change": 0.1, "gov_balance": 0.0}
        return PolicyRuntimeEvaluationArtifact(
            simulation_metrics=metrics,
            simulation_results=build_policy_simulation_results(
                vector,
                fidelity=fidelity,
                uncertainty=uncertainty,
                base_metrics=metrics,
                provenance=provenance,
            ),
            evaluation_vector=vector,
            fidelity=fidelity,
            provenance=provenance,
        )


class _RecordingWorkflowEngine(_PolicyRuntimeWorkflowEngine):
    def __init__(self, *, fidelity: str) -> None:
        super().__init__(fidelity=fidelity, backend=_PassingPolicyEvaluationBackend())
        self.effective_config_inputs: list[dict[str, Any]] = []

    def run(self, initial_state: dict[str, Any]) -> dict[str, Any]:
        self.effective_config_inputs.append(
            deepcopy({key: initial_state.get(key) for key in _CONFIG_KEYS})
        )
        return super().run(initial_state)


def _policy_candidate() -> PolicyCandidateSchema:
    return PolicyCandidateSchema.from_trinity_bundle(
        TrinityBundle(
            problem_frame=ProblemFrame(
                problem_id="problem_work_packet_test",
                domain=ProblemDomain.FISCAL,
            ),
            policy_spec=PolicySpec(policy_id="policy_work_packet_test"),
            model_spec=ModelSpec(
                model_id="model_work_packet_test",
                data_snapshot_ref="sha256:" + "1" * 64,
            ),
        ),
        candidate_id="candidate_work_packet_test",
    )


def _candidate_payload(candidate: PolicyCandidateSchema) -> dict[str, Any]:
    return {
        "candidate_id": candidate.candidate_id,
        "semantic": {
            "interventions": [{"type": "tax_reform", "parameters": {"rate": 0.2}}],
            "objectives": [{"name": "gdp_growth"}],
        },
    }


def _context(
    store: FileSystemCAS, candidate: PolicyCandidateSchema, ref: ArtifactRef
) -> dict[str, Any]:
    return {
        **deepcopy(_FULL_CONFIG),
        "store": store,
        "pinned_input_signature": "input-signature-work-packet-test",
        "policy_candidate_schema": candidate,
        "policy_candidate_ref": ref,
        "transfer_context": {
            "run_id": "run_work_packet_test",
            "task_family": "policy",
            "domain": "fiscal",
            "tenant_hash": "tenant-test",
        },
    }


def test_same_run_direct_l4_and_l3_to_l4_persist_joined_invocations(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    candidate = _policy_candidate()
    candidate_ref = persist_policy_candidate_schema(store, candidate)
    candidate_payload = _candidate_payload(candidate)
    caller_context = _context(store, candidate, candidate_ref)
    caller_snapshot = deepcopy(
        {key: value for key, value in caller_context.items() if key != "store"}
    )

    direct_l4_engine = _RecordingWorkflowEngine(fidelity="full")
    direct = FunnelOrchestrator(
        [Level4FullFidelity(workflow_engine=direct_l4_engine, estimated_cost_usd=0.2)]
    )
    direct_outcome = direct.advance(
        direct.submit(candidate_payload, caller_context), target_level=4
    )

    chain_l3_engine = _RecordingWorkflowEngine(fidelity="medium")
    chain_l4_engine = _RecordingWorkflowEngine(fidelity="full")
    chain = FunnelOrchestrator(
        [
            Level3MediumFidelity(
                workflow_engine=chain_l3_engine,
                subsample_fraction=0.35,
                bootstrap_draws=64,
            ),
            Level4FullFidelity(workflow_engine=chain_l4_engine, estimated_cost_usd=0.2),
        ]
    )
    chain_outcome = chain.advance(chain.submit(candidate_payload, caller_context), target_level=4)

    assert direct_outcome.stage_results[4].is_promising
    assert chain_outcome.stage_results[3].is_promising
    assert chain_outcome.stage_results[4].is_promising
    assert (
        direct_outcome.stage_results[4].simulation_results
        == chain_outcome.stage_results[4].simulation_results
    )
    assert direct_l4_engine.effective_config_inputs == chain_l4_engine.effective_config_inputs
    l3_config = chain_l3_engine.effective_config_inputs[0]
    assert l3_config["data_config"]["subsample_fraction"] == 0.35
    assert l3_config["estimation_config"]["n_bootstrap"] == 64
    assert l3_config["model_config"]["scm_complexity"] == "reduced"
    assert {
        key: value for key, value in caller_context.items() if key != "store"
    } == caller_snapshot

    direct_packet_ref = direct_outcome.stage_results[4].executed_work_packet_ref
    chain_l3_packet_ref = chain_outcome.stage_results[3].executed_work_packet_ref
    chain_l4_packet_ref = chain_outcome.stage_results[4].executed_work_packet_ref
    assert direct_packet_ref is not None
    assert chain_l3_packet_ref is not None
    assert chain_l4_packet_ref is not None
    direct_packet = FunnelExecutedWorkPacket.model_validate(
        from_canonical_bytes(store.get_bytes(direct_packet_ref.artifact_id))
    )
    chain_l3_packet = FunnelExecutedWorkPacket.model_validate(
        from_canonical_bytes(store.get_bytes(chain_l3_packet_ref.artifact_id))
    )
    chain_l4_packet = FunnelExecutedWorkPacket.model_validate(
        from_canonical_bytes(store.get_bytes(chain_l4_packet_ref.artifact_id))
    )
    assert direct_packet.run_id == chain_l4_packet.run_id == "run_work_packet_test"
    assert direct_packet.candidate_hash == chain_l4_packet.candidate_hash
    assert chain_l3_packet.ticket_id == chain_l4_packet.ticket_id
    assert chain_l3_packet.stage_level == 3
    assert chain_l4_packet.stage_level == direct_packet.stage_level == 4
    assert (
        len(
            {
                direct_packet.evaluation_attempt_id,
                chain_l3_packet.evaluation_attempt_id,
                chain_l4_packet.evaluation_attempt_id,
            }
        )
        == 3
    )
    assert chain_l3_packet.requested_draw_count == 64
    assert direct_packet.requested_draw_count == chain_l4_packet.requested_draw_count == 500
    for packet in (direct_packet, chain_l3_packet, chain_l4_packet):
        assert packet.attempted_invocation_count == 1
        assert packet.completed_invocation_count == 1
        assert packet.draw_execution_status == "not_instrumented"
        assert packet.attempted_draw_count is None
        assert packet.successful_draw_count is None
        assert packet.failed_draw_count is None
        assert packet.unattempted_draw_count is None
    assert all(
        step.executed_work_packet_status == "available"
        for step in chain_outcome.trace
        if step.fidelity_level in {3, 4}
    )
    from polisyos.scientist.nodes.builtins.decide.run_policy_blueprint_runtime import (
        _serialize_funnel_outcome,
    )

    projected = _serialize_funnel_outcome(chain_outcome)
    assert projected["trace"][0]["executed_work_packet_status"] == "available"
    assert projected["stage_results"]["4"]["executed_work_packet_ref"] == (
        chain_l4_packet_ref.model_dump(mode="json")
    )


@pytest.mark.parametrize(
    ("packet_run_id", "packet_draw_count"),
    [("another-run", 64), ("run_work_packet_test", 500)],
)
def test_work_packet_consumer_rejects_wrong_run_or_draw_binding(
    tmp_path: Path,
    packet_run_id: str,
    packet_draw_count: int,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    candidate = _policy_candidate()
    candidate_ref = persist_policy_candidate_schema(store, candidate)
    evaluation_ref = persist_policy_evaluation_vector_to_store(
        store,
        candidate_ref=candidate_ref,
        evaluation_vector=PolicyEvaluationVector(candidate_id=candidate.candidate_id),
    )
    context = _context(store, candidate, candidate_ref)
    stage = Level3MediumFidelity(workflow_engine=_RecordingWorkflowEngine(fidelity="medium"))
    orchestrator = FunnelOrchestrator([stage])
    ticket = orchestrator.submit(_candidate_payload(candidate), context)
    wrong_run_packet = FunnelExecutedWorkPacket(
        run_id=packet_run_id,
        ticket_id=ticket.ticket_id,
        candidate_hash=ticket.candidate_hash,
        candidate_ref=candidate_ref,
        stage_level=3,
        stage_name="funnel_L3_medium",
        fidelity="medium",
        evaluation_attempt_id="wrong-run-attempt",
        observed_at=datetime.now(UTC),
        backend_kind="synthetic",
        source_result_ref=evaluation_ref,
        requested_draw_count=packet_draw_count,
        input_signature=context["pinned_input_signature"],
    )
    wrong_run_ref = persist_funnel_executed_work_packet(store, wrong_run_packet)
    stage.evaluate = lambda _candidate, _context: stage_result_with_packet(
        wrong_run_ref,
    )

    outcome = orchestrator.advance(ticket, target_level=3)

    assert outcome.trace[0].executed_work_packet_status == "rejected"
    assert outcome.trace[0].executed_work_packet_ref == wrong_run_ref
    assert (
        outcome.stage_results[3].feedback["policy_runtime_work_packet_rejection_reason"]
        == "work_packet_binding_mismatch"
    )


def test_policy_runtime_reports_work_packet_unavailable_without_run_binding() -> None:
    result = _PolicyRuntimeWorkflowEngine(
        fidelity="medium",
        backend=_PassingPolicyEvaluationBackend(),
    ).run({"policy_candidate_schema": _policy_candidate()})

    assert result["feedback"]["policy_runtime_work_packet_status"] == "unavailable"
    assert (
        result["feedback"]["policy_runtime_work_packet_unavailability_reason"]
        == "execution_identity_unavailable"
    )
    assert "policy_runtime_work_packet_ref" not in result["feedback"]


def stage_result_with_packet(ref: ArtifactRef) -> FunnelStageResult:
    return FunnelStageResult(
        policy_candidate={},
        objective_value=0.0,
        is_promising=True,
        stage_name="funnel_L3_medium",
        simulation_results={"bootstrap": {"requested_draw_count": 64}},
        feedback={
            "policy_runtime_fidelity": "medium",
            "policy_runtime_backend_kind": "synthetic",
        },
        fidelity_level=3,
        executed_work_packet_ref=ref,
        executed_work_packet_status="available",
    )
