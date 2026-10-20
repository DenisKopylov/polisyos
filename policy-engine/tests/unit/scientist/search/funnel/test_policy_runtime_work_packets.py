from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from polisyos.core.artifacts import input_ref_from_artifact_ref
from polisyos.core.artifacts.manifest import (
    ArtifactRef,
    InputRef,
    ProducerInfo,
    SchemaInfo,
)
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes
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
from polisyos.scientist.methods.search.objective import ObjectiveScoreStatus
from polisyos.scientist.methods.search.voi_scheduler import PredictiveVOIScheduler
from polisyos.scientist.nodes.builtins.decide.policy_runtime_metrics import (
    _build_policy_simulation_results_impl,
    _policy_runtime_execution_metadata,
)
from polisyos.scientist.nodes.builtins.decide.policy_runtime_support import (
    PolicyRuntimeEvaluationArtifact,
    PolicyRuntimeProvenance,
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
        evaluation_attempt_id: str | None = None,
        effective_estimation_config: dict[str, Any] | None = None,
    ) -> PolicyRuntimeEvaluationArtifact:
        del (
            simulation_metrics,
            distributional_report,
            causal_effect_report,
            cross_graph_profile,
            governance_report,
            ambiguity_certificate,
        )
        execution = _policy_runtime_execution_metadata(
            evaluation_attempt_id=evaluation_attempt_id,
            effective_estimation_config=effective_estimation_config,
        )
        vector = PolicyEvaluationVector(
            candidate_id=candidate.candidate_id,
            feasible=True,
            metadata={
                "policy_runtime_invocation": execution,
                "policy_runtime_fiscal_measurement": {
                    "usable": True,
                    "normalized_value": 0.0,
                    "source_values": {"gov_balance": 0.0},
                },
            },
        )
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
            simulation_results=_build_policy_simulation_results_impl(
                vector,
                fidelity=fidelity,
                uncertainty=uncertainty,
                base_metrics=metrics,
                provenance=provenance,
                runtime_execution=execution,
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


def test_same_run_direct_l4_and_l3_to_l4_persist_joined_invocations(
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    candidate = _policy_candidate()
    candidate_ref = persist_policy_candidate_schema(store, candidate, return_selected_profile=True)
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
    chain_voi = PredictiveVOIScheduler()
    chain = FunnelOrchestrator(
        [
            Level3MediumFidelity(
                workflow_engine=chain_l3_engine,
                subsample_fraction=0.35,
                bootstrap_draws=64,
            ),
            Level4FullFidelity(workflow_engine=chain_l4_engine, estimated_cost_usd=0.2),
        ],
        voi_scheduler=chain_voi,
    )
    chain_outcome = chain.advance(chain.submit(candidate_payload, caller_context), target_level=4)

    # The engine has no selected source-unit contract. Its packet is real and
    # admitted, but the fiscal scalar remains limited and cannot enter VOI.
    for outcome, level in ((direct_outcome, 4), (chain_outcome, 4)):
        result = outcome.stage_results[level]
        assert result.executed_work_packet_status == "available"
        assert result.executed_work_packet_ref is not None
        assert result.score_status is ObjectiveScoreStatus.UNAVAILABLE
        assert result.objective_value is None
        assert result.score_assessment is not None
        assert result.is_promising is False
        assert result.simulation_results["metric_units"] == {}
        assert result.feedback["selected_objective_admission"] == "unavailable"
    assert chain_outcome.stage_results[3].score_status is ObjectiveScoreStatus.UNAVAILABLE
    assert chain_outcome.stage_results[3].objective_value is None
    assert chain_outcome.stage_results[3].is_promising is False
    assert chain_voi.snapshot().observations == []
    assert chain_voi.snapshot().observations == []
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
    direct_source = from_canonical_bytes(
        store.get_bytes(direct_packet.source_result_ref.artifact_id)
    )
    chain_l4_source = from_canonical_bytes(
        store.get_bytes(chain_l4_packet.source_result_ref.artifact_id)
    )
    for packet, source in (
        (direct_packet, direct_source),
        (chain_l4_packet, chain_l4_source),
    ):
        invocation = source["metadata"]["policy_runtime_invocation"]
        assert invocation == {
            "evaluation_attempt_id": packet.evaluation_attempt_id,
            "requested_draw_count": packet.requested_draw_count,
            "requested_draw_source": packet.requested_draw_source,
            "effective_estimation_config_sha256": (packet.effective_estimation_config_sha256),
        }
    direct_fiscal_measurement = direct_source["metadata"]["policy_runtime_fiscal_measurement"]
    assert chain_l4_source["metadata"]["policy_runtime_fiscal_measurement"] == (
        direct_fiscal_measurement
    )
    assert direct_fiscal_measurement == {
        "usable": True,
        "normalized_value": 0.0,
        "source_values": {"gov_balance": 0.0},
    }
    assert direct_outcome.stage_results[4].simulation_results["gov_balance"] == 0.0
    assert all(
        packet.requested_draw_source == "effective_estimation_config"
        and packet.effective_estimation_config_sha256 is not None
        for packet in (direct_packet, chain_l3_packet, chain_l4_packet)
    )
    assert direct_packet.effective_estimation_config_sha256 == (
        chain_l4_packet.effective_estimation_config_sha256
    )
    for packet in (direct_packet, chain_l3_packet, chain_l4_packet):
        assert packet.attempted_invocation_count == 1
        assert packet.completed_invocation_count == 1
        assert packet.draw_execution_status == "not_instrumented"
        assert packet.attempted_draw_count is None
        assert packet.successful_draw_count is None
        assert packet.failed_draw_count is None
        assert packet.unattempted_draw_count is None

    direct_metrics = deepcopy(direct_outcome.stage_results[4].simulation_results)
    chain_l4_metrics = deepcopy(chain_outcome.stage_results[4].simulation_results)
    direct_bootstrap = direct_metrics["bootstrap"]
    chain_l4_bootstrap = chain_l4_metrics["bootstrap"]
    assert isinstance(direct_bootstrap, dict)
    assert isinstance(chain_l4_bootstrap, dict)
    direct_attempt_id = direct_bootstrap.pop("evaluation_attempt_id")
    chain_l4_attempt_id = chain_l4_bootstrap.pop("evaluation_attempt_id")
    assert direct_attempt_id == direct_packet.evaluation_attempt_id
    assert chain_l4_attempt_id == chain_l4_packet.evaluation_attempt_id
    assert direct_attempt_id != chain_l4_attempt_id
    # Only the invocation identity varies; every physical result and the rest of
    # the bootstrap record must agree across direct and promoted full-fidelity runs.
    assert direct_metrics == chain_l4_metrics

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
    for packet_ref, packet in (
        (direct_packet_ref, direct_packet),
        (chain_l3_packet_ref, chain_l3_packet),
        (chain_l4_packet_ref, chain_l4_packet),
    ):
        assert store.get_manifest(packet_ref).inputs == [
            input_ref_from_artifact_ref(packet.candidate_ref, role="candidate"),
            input_ref_from_artifact_ref(packet.source_result_ref, role="source_result"),
        ]


def test_default_l3_requested_count_comes_from_effective_config_only(
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    candidate = _policy_candidate()
    candidate_ref = persist_policy_candidate_schema(store, candidate)
    engine = _RecordingWorkflowEngine(fidelity="medium")
    stage = Level3MediumFidelity(workflow_engine=engine)
    orchestrator = FunnelOrchestrator([stage])
    ticket = orchestrator.submit(
        _candidate_payload(candidate), _context(store, candidate, candidate_ref)
    )
    outcome = orchestrator.advance(ticket, target_level=3)

    result = outcome.stage_results[3]
    packet_ref = result.executed_work_packet_ref
    assert packet_ref is not None
    packet = FunnelExecutedWorkPacket.model_validate(
        from_canonical_bytes(store.get_bytes(packet_ref.artifact_id))
    )
    assert engine.effective_config_inputs[0]["estimation_config"]["n_bootstrap"] == 50
    assert packet.requested_draw_count == 50
    assert packet.requested_draw_source == "effective_estimation_config"
    assert packet.draw_execution_status == "not_instrumented"
    assert packet.attempted_draw_count is None
    assert packet.successful_draw_count is None
    assert packet.failed_draw_count is None
    assert packet.unattempted_draw_count is None


def test_legacy_fidelity_default_packet_is_not_admitted_as_current_config_evidence(
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    candidate = _policy_candidate()
    candidate_ref = persist_policy_candidate_schema(store, candidate)
    context = _context(store, candidate, candidate_ref)
    evaluation_ref = persist_policy_evaluation_vector_to_store(
        store,
        candidate_ref=candidate_ref,
        evaluation_vector=PolicyEvaluationVector(candidate_id=candidate.candidate_id),
    )
    stage = Level3MediumFidelity(workflow_engine=_RecordingWorkflowEngine(fidelity="medium"))
    orchestrator = FunnelOrchestrator([stage])
    ticket = orchestrator.submit(_candidate_payload(candidate), context)
    packet = FunnelExecutedWorkPacket(
        schema_version="1.0",
        run_id="run_work_packet_test",
        ticket_id=ticket.ticket_id,
        candidate_hash=ticket.candidate_hash,
        candidate_ref=candidate_ref,
        stage_level=3,
        stage_name="funnel_L3_medium",
        fidelity="medium",
        evaluation_attempt_id="attempt-legacy",
        observed_at=datetime.now(UTC),
        backend_kind="synthetic",
        source_result_ref=evaluation_ref,
        requested_draw_count=64,
        requested_draw_source="fidelity_default",
        input_signature=context["pinned_input_signature"],
    )
    packet_ref = persist_funnel_executed_work_packet(store, packet)
    stage.evaluate = lambda _candidate, _context: FunnelStageResult(
        policy_candidate=_candidate,
        objective_value=0.0,
        is_promising=True,
        stage_name="funnel_L3_medium",
        duration_seconds=0.01,
        simulation_results={"bootstrap": {"requested_draw_count": 64}},
        feedback={
            "policy_runtime_fidelity": "medium",
            "policy_runtime_backend_kind": "synthetic",
        },
        fidelity_level=3,
        executed_work_packet_ref=packet_ref,
        executed_work_packet_status="available",
    )

    outcome = orchestrator.advance(ticket, target_level=3)

    assert outcome.trace[0].executed_work_packet_status == "rejected"
    assert outcome.stage_results[3].feedback["policy_runtime_work_packet_rejection_reason"] == (
        "work_packet_binding_mismatch"
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
    source_invocation = {
        "evaluation_attempt_id": "attempt-source-bound",
        "requested_draw_count": 50,
        "requested_draw_source": "effective_estimation_config",
        "effective_estimation_config_sha256": "e" * 64,
    }
    evaluation_ref = persist_policy_evaluation_vector_to_store(
        store,
        candidate_ref=candidate_ref,
        evaluation_vector=PolicyEvaluationVector(
            candidate_id=candidate.candidate_id,
            metadata={
                "policy_runtime_invocation": source_invocation,
                "policy_runtime_fiscal_measurement": {
                    "usable": False,
                    "normalized_value": None,
                    "source_values": {},
                },
            },
        ),
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
        evaluation_attempt_id=(
            "wrong-run-attempt"
            if packet_run_id != "run_work_packet_test"
            else "attempt-source-bound"
        ),
        observed_at=datetime.now(UTC),
        backend_kind="synthetic",
        source_result_ref=evaluation_ref,
        requested_draw_count=packet_draw_count,
        requested_draw_source="effective_estimation_config",
        effective_estimation_config_sha256="e" * 64,
        input_signature=context["pinned_input_signature"],
    )
    wrong_run_ref = persist_funnel_executed_work_packet(store, wrong_run_packet)
    stage.evaluate = lambda _candidate, _context: stage_result_with_packet(
        wrong_run_ref,
        evaluation_attempt_id="attempt-source-bound",
        requested_draw_count=50,
        config_digest="e" * 64,
    )

    outcome = orchestrator.advance(ticket, target_level=3)

    assert outcome.trace[0].executed_work_packet_status == "rejected"
    assert outcome.trace[0].executed_work_packet_ref == wrong_run_ref
    assert (
        outcome.stage_results[3].feedback["policy_runtime_work_packet_rejection_reason"]
        == "work_packet_binding_mismatch"
    )


@pytest.mark.parametrize("mismatch", ["attempt", "config_digest"])
def test_work_packet_consumer_rejects_rebound_attempt_or_config_digest(
    tmp_path: Path,
    mismatch: str,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    candidate = _policy_candidate()
    candidate_ref = persist_policy_candidate_schema(store, candidate)
    context = _context(store, candidate, candidate_ref)
    source_attempt = "attempt-source-bound"
    config_digest = "e" * 64
    vector = PolicyEvaluationVector(
        candidate_id=candidate.candidate_id,
        metadata={
            "policy_runtime_invocation": {
                "evaluation_attempt_id": source_attempt,
                "requested_draw_count": 50,
                "requested_draw_source": "effective_estimation_config",
                "effective_estimation_config_sha256": config_digest,
            },
            "policy_runtime_fiscal_measurement": {
                "usable": False,
                "normalized_value": None,
                "source_values": {},
            },
        },
    )
    evaluation_ref = persist_policy_evaluation_vector_to_store(
        store,
        candidate_ref=candidate_ref,
        evaluation_vector=vector,
    )
    packet_attempt = "rebound-attempt" if mismatch == "attempt" else source_attempt
    packet_digest = "f" * 64 if mismatch == "config_digest" else config_digest
    stage = Level3MediumFidelity(workflow_engine=_RecordingWorkflowEngine(fidelity="medium"))
    orchestrator = FunnelOrchestrator([stage])
    ticket = orchestrator.submit(_candidate_payload(candidate), context)
    packet = FunnelExecutedWorkPacket(
        run_id="run_work_packet_test",
        ticket_id=ticket.ticket_id,
        candidate_hash=ticket.candidate_hash,
        candidate_ref=candidate_ref,
        stage_level=3,
        stage_name="funnel_L3_medium",
        fidelity="medium",
        evaluation_attempt_id=packet_attempt,
        observed_at=datetime.now(UTC),
        backend_kind="synthetic",
        source_result_ref=evaluation_ref,
        requested_draw_count=50,
        requested_draw_source="effective_estimation_config",
        effective_estimation_config_sha256=packet_digest,
        input_signature=context["pinned_input_signature"],
    )
    packet_ref = persist_funnel_executed_work_packet(store, packet)
    stage.evaluate = lambda _candidate, _context: FunnelStageResult(
        policy_candidate=_candidate,
        objective_value=0.0,
        is_promising=True,
        stage_name="funnel_L3_medium",
        duration_seconds=0.01,
        simulation_results={
            "budget_deficit_objective_usable": False,
            "budget_deficit_objective_value": None,
            "bootstrap": {
                "evaluation_attempt_id": source_attempt,
                "requested_draw_count": 50,
                "requested_draw_source": "effective_estimation_config",
                "effective_estimation_config_sha256": config_digest,
            },
        },
        feedback={
            "policy_runtime_fidelity": "medium",
            "policy_runtime_backend_kind": "synthetic",
        },
        fidelity_level=3,
        executed_work_packet_ref=packet_ref,
        executed_work_packet_status="available",
    )

    outcome = orchestrator.advance(ticket, target_level=3)

    assert outcome.trace[0].executed_work_packet_status == "rejected"
    assert outcome.stage_results[3].feedback["policy_runtime_work_packet_rejection_reason"] == (
        "work_packet_binding_mismatch"
    )


@pytest.mark.parametrize(
    "edge_variant",
    ["same_id_foreign_profile", "duplicate_role", "missing_role", "extra_role"],
)
def test_work_packet_consumer_rejects_nonexact_input_edge_multiset(
    tmp_path: Path,
    edge_variant: str,
) -> None:
    """Fresh admission requires the complete input-edge multiset from the typed body."""
    store = FileSystemCAS(tmp_path / "cas")
    candidate = _policy_candidate()
    candidate_ref = persist_policy_candidate_schema(
        store,
        candidate,
        return_selected_profile=True,
    )
    foreign_store = FileSystemCAS(tmp_path / "foreign-cas")
    foreign_ref = foreign_store.put_json(
        candidate,
        PutOptions(
            kind=candidate_ref.kind,
            media_type=candidate_ref.media_type,
            schema=SchemaInfo(name="tests.ForeignCandidateProfile", version="99.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    assert foreign_ref.artifact_id == candidate_ref.artifact_id
    assert foreign_ref.manifest_profile_sha256 != candidate_ref.manifest_profile_sha256

    edge_invocation = {
        "evaluation_attempt_id": "attempt-foreign-profile-edge",
        "requested_draw_count": 64,
        "requested_draw_source": "effective_estimation_config",
        "effective_estimation_config_sha256": "d" * 64,
    }
    evaluation_ref = persist_policy_evaluation_vector_to_store(
        store,
        candidate_ref=candidate_ref,
        evaluation_vector=PolicyEvaluationVector(
            candidate_id=candidate.candidate_id,
            metadata={
                "policy_runtime_invocation": edge_invocation,
                "policy_runtime_fiscal_measurement": {
                    "usable": False,
                    "normalized_value": None,
                    "source_values": {},
                },
            },
        ),
    )
    context = _context(store, candidate, candidate_ref)
    stage = Level3MediumFidelity(workflow_engine=_RecordingWorkflowEngine(fidelity="medium"))
    orchestrator = FunnelOrchestrator([stage])
    ticket = orchestrator.submit(_candidate_payload(candidate), context)
    packet = FunnelExecutedWorkPacket(
        run_id="run_work_packet_test",
        ticket_id=ticket.ticket_id,
        candidate_hash=ticket.candidate_hash,
        candidate_ref=candidate_ref,
        stage_level=3,
        stage_name="funnel_L3_medium",
        fidelity="medium",
        evaluation_attempt_id="attempt-foreign-profile-edge",
        observed_at=datetime.now(UTC),
        backend_kind="synthetic",
        source_result_ref=evaluation_ref,
        requested_draw_count=64,
        requested_draw_source="effective_estimation_config",
        effective_estimation_config_sha256="d" * 64,
        input_signature=context["pinned_input_signature"],
    )
    candidate_input = input_ref_from_artifact_ref(candidate_ref, role="candidate")
    source_result_input = input_ref_from_artifact_ref(evaluation_ref, role="source_result")
    if edge_variant == "same_id_foreign_profile":
        packet_inputs = [
            InputRef(
                artifact_id=foreign_ref.artifact_id,
                role="candidate",
                manifest_profile_sha256=foreign_ref.manifest_profile_sha256,
            ),
            source_result_input,
        ]
    elif edge_variant == "duplicate_role":
        packet_inputs = [candidate_input, source_result_input, candidate_input]
    elif edge_variant == "missing_role":
        packet_inputs = [candidate_input]
    else:
        packet_inputs = [
            candidate_input,
            source_result_input,
            InputRef(artifact_id=candidate_ref.artifact_id, role="extra"),
        ]
    packet_ref = store.put_json(
        packet,
        PutOptions(
            kind="scientist.search.funnel_native_work_packet",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.scientist.search.FunnelExecutedWorkPacket",
                version=packet.schema_version,
            ),
            producer=ProducerInfo(
                component="scientist.policy_runtime_work_packet",
                version="1.0.0",
            ),
            inputs=packet_inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    stage.evaluate = lambda _candidate, _context: stage_result_with_packet(
        packet_ref,
        evaluation_attempt_id=edge_invocation["evaluation_attempt_id"],
        requested_draw_count=edge_invocation["requested_draw_count"],
        config_digest=edge_invocation["effective_estimation_config_sha256"],
    )

    outcome = orchestrator.advance(ticket, target_level=3)

    assert outcome.trace[0].executed_work_packet_status == "rejected"
    assert outcome.stage_results[3].feedback["policy_runtime_work_packet_rejection_reason"] == (
        "work_packet_binding_mismatch"
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


def stage_result_with_packet(
    ref: ArtifactRef,
    *,
    evaluation_attempt_id: str,
    requested_draw_count: int,
    config_digest: str,
) -> FunnelStageResult:
    return FunnelStageResult(
        policy_candidate={},
        objective_value=0.0,
        is_promising=True,
        stage_name="funnel_L3_medium",
        simulation_results={
            "budget_deficit_objective_usable": False,
            "budget_deficit_objective_value": None,
            "bootstrap": {
                "evaluation_attempt_id": evaluation_attempt_id,
                "requested_draw_count": requested_draw_count,
                "requested_draw_source": "effective_estimation_config",
                "effective_estimation_config_sha256": config_digest,
            },
        },
        feedback={
            "policy_runtime_fidelity": "medium",
            "policy_runtime_backend_kind": "synthetic",
        },
        fidelity_level=3,
        executed_work_packet_ref=ref,
        executed_work_packet_status="available",
    )


class _UnavailableFiscalWorkflowEngine:
    def run(self, initial_state: dict[str, Any]) -> dict[str, Any]:
        del initial_state
        return {
            "simulation_results": {
                "gdp_change": 0.1,
                "budget_deficit_objective_usable": False,
                "budget_deficit_objective_value": None,
            },
            "feedback": {"verdict": "APPROVE"},
        }


class _ObjectiveRecordingVOI:
    def observe_stage_result(self, **kwargs: Any) -> None:
        self.actual_objective_value = kwargs["actual_objective_value"]


def test_unavailable_fiscal_signal_is_labeled_and_withheld_from_scalar_voi_consumer() -> None:
    scheduler = _ObjectiveRecordingVOI()
    stage = Level3MediumFidelity(workflow_engine=_UnavailableFiscalWorkflowEngine())
    orchestrator = FunnelOrchestrator([stage], voi_scheduler=scheduler)
    candidate = _policy_candidate()
    outcome = orchestrator.advance(
        orchestrator.submit(_candidate_payload(candidate), {}),
        target_level=3,
    )

    result = outcome.stage_results[3]
    limitation = "search_objective_fiscal_measurement_unavailable"
    assert result.simulation_results["budget_deficit_objective_usable"] is False
    assert result.feedback["objective_limitations"] == [limitation]
    assert result.score_status is ObjectiveScoreStatus.UNAVAILABLE
    assert result.objective_value is None
    assert outcome.trace[0].score_status is ObjectiveScoreStatus.UNAVAILABLE
    assert outcome.trace[0].objective_value is None
    assert not hasattr(scheduler, "actual_objective_value")
