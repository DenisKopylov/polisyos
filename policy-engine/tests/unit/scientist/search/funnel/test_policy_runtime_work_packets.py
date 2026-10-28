from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from polisyos.core.artifacts import (
    artifact_manifest_profile_sha256,
    input_ref_from_artifact_ref,
    load_core_json_artifact,
)
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
from polisyos.scientist.methods.search.objective import (
    GDPGrowthObjective,
    ObjectiveScoreStatus,
    _project_score_assessment_source,
    score_assessment_matches_source,
)
from polisyos.scientist.methods.search.voi_scheduler import (
    PredictiveVOIScheduler,
    _policy_evaluation_vector_source_chain_matches_store,
    _policy_runtime_source_concordance,
    _policy_runtime_vector_schema_supported,
)
from polisyos.scientist.nodes.builtins.decide.policy_runtime_metrics import (
    _budget_deficit_measurement,
    _build_policy_simulation_results_impl,
    _policy_runtime_execution_metadata,
)
from polisyos.scientist.nodes.builtins.decide.policy_runtime_support import (
    PolicyRuntimeEvaluationArtifact,
    PolicyRuntimeProvenance,
    ProductionPolicyEvaluationBackend,
    persist_funnel_executed_work_packet,
    persist_policy_evaluation_vector_to_store,
)
from polisyos.scientist.nodes.builtins.decide.run_policy_blueprint_runtime import (
    _PolicyRuntimeWorkflowEngine,
)
from polisyos.scientist.policy_design.objectives import (
    ObjectiveChannelValue,
    ObjectiveDirection,
    ObjectiveKind,
    PolicyEvaluationVector,
    _policy_vector_channel_assessment,
)
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
        metrics = {"gdp_change": 0.1, "gov_balance": 0.0}
        fiscal_measurement = _budget_deficit_measurement(metrics)
        vector = PolicyEvaluationVector(
            candidate_id=candidate.candidate_id,
            feasible=True,
            metadata={
                "policy_runtime_invocation": execution,
                "policy_runtime_fiscal_measurement": fiscal_measurement,
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
        simulation_results = _build_policy_simulation_results_impl(
            vector,
            fidelity=fidelity,
            uncertainty=uncertainty,
            base_metrics=metrics,
            provenance=provenance,
            runtime_execution=execution,
        )
        vector = vector.with_score_source_results(simulation_results)
        return PolicyRuntimeEvaluationArtifact(
            simulation_metrics=metrics,
            simulation_results=simulation_results,
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


def _runtime_vector_for_fiscal_source(metrics: dict[str, Any]) -> PolicyEvaluationVector:
    """Build the real runtime score-source projection around supplied fiscal aliases."""
    invocation = _policy_runtime_execution_metadata(
        evaluation_attempt_id="attempt-fiscal-source",
        effective_estimation_config={"n_bootstrap": 0},
    )
    fiscal_measurement = _budget_deficit_measurement(metrics)
    vector = PolicyEvaluationVector(
        candidate_id="candidate_fiscal_source_contract",
        primary={
            "policy_value": ObjectiveChannelValue(
                name="policy_value",
                kind=ObjectiveKind.PRIMARY,
                value=0.1,
                direction=ObjectiveDirection.MAXIMIZE,
                expected_unit="fixture-unit",
            )
        },
        metadata={
            "policy_runtime_invocation": invocation,
            "policy_runtime_fiscal_measurement": fiscal_measurement,
        },
    )
    source = {
        "objective_channels": {"policy_value": 0.1},
        "metric_units": {"channel:primary:policy_value": "fixture-unit"},
        "feasible": True,
        "blocking_reasons": [],
        "bootstrap": dict(invocation),
        "budget_deficit_objective_usable": fiscal_measurement["usable"],
        "budget_deficit_objective_value": fiscal_measurement["normalized_value"],
        **metrics,
    }
    return vector.with_score_source_results(source)


def _empty_channel_runtime_source() -> tuple[PolicyEvaluationVector, dict[str, Any]]:
    """Build a complete runtime source whose execution has no objective channels."""
    invocation = _policy_runtime_execution_metadata(
        evaluation_attempt_id="attempt-empty-runtime-channels",
        effective_estimation_config={"n_bootstrap": 0},
    )
    fiscal_measurement = _budget_deficit_measurement({"gov_balance": 0.0})
    vector = PolicyEvaluationVector(
        candidate_id="candidate_empty_runtime_channels",
        metadata={
            "policy_runtime_invocation": invocation,
            "policy_runtime_fiscal_measurement": fiscal_measurement,
        },
    )
    source = {
        "objective_channels": {},
        "metric_units": {},
        "feasible": vector.feasible,
        "blocking_reasons": list(vector.blocking_reasons),
        "bootstrap": dict(invocation),
        "budget_deficit_objective_usable": fiscal_measurement["usable"],
        "budget_deficit_objective_value": fiscal_measurement["normalized_value"],
        **fiscal_measurement["source_values"],
    }
    return vector, source


def test_complete_empty_runtime_channels_preserve_execution_without_score() -> None:
    vector, source = _empty_channel_runtime_source()

    bound = vector.with_score_source_results(source)

    assert bound.score_source is not None
    assert bound.score_source["objective_channels"] == {}
    assert bound.score_source["bootstrap"] == vector.metadata["policy_runtime_invocation"]
    assert bound.metadata == vector.metadata
    assert bound._runtime_source_invocation_binding_status(source) is ObjectiveScoreStatus.AVAILABLE
    assert bound.score_assessment is not None
    assert bound.score_assessment.status is ObjectiveScoreStatus.NOT_ESTABLISHED
    assert bound.score_assessment.value is None
    assert bound.runtime_score_available_for_search(source) is False
    concordance = _policy_runtime_source_concordance(bound)
    assert concordance == {
        **bound.score_source,
        "policy_evaluation": bound,
        "simulation_results": bound.score_source,
    }


def test_runtime_source_concordance_replays_selected_typed_channel_with_fiscal_unknown() -> None:
    vector = _runtime_vector_for_fiscal_source({})
    channel = vector.primary["policy_value"]
    assessment = _policy_vector_channel_assessment(channel, "primary", vector.score_source)

    concordance = _policy_runtime_source_concordance(vector)

    assert vector.metadata["policy_runtime_fiscal_measurement"] == {
        "usable": False,
        "normalized_value": None,
        "source_values": {},
    }
    assert assessment.status is ObjectiveScoreStatus.AVAILABLE
    assert assessment.value == channel.value
    assert concordance is not None
    assert concordance["policy_evaluation"] is vector
    assert concordance["simulation_results"] == vector.score_source
    assert all(concordance.get(key) == value for key, value in vector.score_source.items())
    assert score_assessment_matches_source(assessment, concordance)
    assert _project_score_assessment_source(assessment, concordance) == {
        "metric_units": {"channel:primary:policy_value": "fixture-unit"},
        "policy_evaluation": {"primary": {"policy_value": channel.model_dump(mode="python")}},
        "simulation_results": {
            "objective_channels": {"policy_value": channel.value},
            "metric_units": {"channel:primary:policy_value": "fixture-unit"},
        },
    }

    changed_source = dict(concordance)
    changed_simulation_results = dict(concordance["simulation_results"])
    changed_channels = dict(changed_simulation_results["objective_channels"])
    changed_channels["policy_value"] = channel.value + 1.0
    changed_simulation_results["objective_channels"] = changed_channels
    changed_source["simulation_results"] = changed_simulation_results
    assert not score_assessment_matches_source(assessment, changed_source)

    changed_vector = vector.model_copy(
        update={
            "primary": {"policy_value": channel.model_copy(update={"value": channel.value + 1.0})}
        }
    )
    assert not score_assessment_matches_source(
        assessment,
        {
            "policy_evaluation": changed_vector,
            "simulation_results": concordance["simulation_results"],
        },
    )


@pytest.mark.parametrize(
    "case",
    [
        ("absent",),
        ("null",),
        ("list",),
        ("non_string_key",),
        ("blank_key",),
        ("nonfinite",),
    ],
)
def test_missing_or_malformed_runtime_channels_fail_closed(case: str) -> None:
    vector, source = _empty_channel_runtime_source()
    if case == "absent":
        source.pop("objective_channels")
    elif case == "null":
        source["objective_channels"] = None
    elif case == "list":
        source["objective_channels"] = []
    elif case == "non_string_key":
        source["objective_channels"] = {1: 0.1}
    elif case == "blank_key":
        source["objective_channels"] = {" ": 0.1}
    else:
        source["objective_channels"] = {"policy_value": float("nan")}

    bound = vector.with_score_source_results(source)

    assert bound.score_source is None
    assert bound.metadata == vector.metadata
    assert bound._runtime_source_invocation_binding_status(source) is ObjectiveScoreStatus.AVAILABLE
    assert bound.score_assessment is not None
    assert bound.score_assessment.status is ObjectiveScoreStatus.NOT_ESTABLISHED
    assert bound.score_assessment.value is None
    assert bound.runtime_score_available_for_search(source) is False
    assert _policy_runtime_source_concordance(bound) is None


@pytest.mark.parametrize(
    ("metrics", "present_alias"),
    [
        ({}, None),
        ({"gov_balance": None}, "gov_balance"),
        ({"budget_deficit": "malformed"}, "budget_deficit"),
        ({"budget_deficit": 0.0}, "budget_deficit"),
    ],
    ids=("absent", "explicit-null", "malformed-present", "numeric-present"),
)
def test_runtime_source_concordance_recomputes_fiscal_projection_and_keeps_presence(
    metrics: dict[str, Any], present_alias: str | None
) -> None:
    vector = _runtime_vector_for_fiscal_source(metrics)

    concordance = _policy_runtime_source_concordance(vector)

    assert concordance is not None
    assert concordance["policy_evaluation"] is vector
    concordant = concordance["simulation_results"]
    measurement = vector.metadata["policy_runtime_fiscal_measurement"]
    assert measurement["source_values"] == metrics
    fiscal_aliases = ("gov_balance", "government_balance", "budget_deficit", "deficit")
    assert {key for key in fiscal_aliases if key in concordant} == set(metrics)
    if present_alias is not None:
        assert present_alias in concordant
        assert concordant[present_alias] == metrics[present_alias]
    assert concordant["budget_deficit_objective_usable"] is measurement["usable"]
    assert concordant["budget_deficit_objective_value"] == measurement["normalized_value"]


@pytest.mark.parametrize(
    "tamper",
    [
        "marker_only",
        "metadata_absent",
        "metadata_null",
        "metadata_wrong_type",
        "source_value_drift",
        "source_value_marker_absent",
    ],
)
def test_runtime_source_concordance_rejects_unbound_fiscal_projection(tamper: str) -> None:
    vector = _runtime_vector_for_fiscal_source({})
    metadata = dict(vector.metadata)
    score_source = dict(vector.score_source or {})
    if tamper == "marker_only":
        score_source["budget_deficit_objective_usable"] = True
        score_source["budget_deficit_objective_value"] = 1.0
    elif tamper == "source_value_marker_absent":
        score_source.pop("budget_deficit_objective_value")
    elif tamper == "metadata_absent":
        metadata.pop("policy_runtime_fiscal_measurement")
    elif tamper == "metadata_null":
        metadata["policy_runtime_fiscal_measurement"] = None
    elif tamper == "metadata_wrong_type":
        measurement = dict(metadata["policy_runtime_fiscal_measurement"])
        measurement["usable"] = "false"
        metadata["policy_runtime_fiscal_measurement"] = measurement
    else:
        measurement = dict(metadata["policy_runtime_fiscal_measurement"])
        measurement["source_values"] = {"gov_balance": None}
        metadata["policy_runtime_fiscal_measurement"] = measurement

    tampered = vector.model_copy(update={"metadata": metadata, "score_source": score_source})

    assert _policy_runtime_source_concordance(tampered) is None


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
    for packet_ref in (direct_packet_ref, chain_l3_packet_ref, chain_l4_packet_ref):
        packet_manifest = store.get_manifest(packet_ref)
        assert packet_ref.manifest_profile_sha256 is not None
        assert packet_ref.manifest_profile_sha256 == artifact_manifest_profile_sha256(
            packet_manifest
        )
        assert all(item.manifest_profile_sha256 is not None for item in packet_manifest.inputs)
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
    for packet_ref, packet in (
        (direct_packet_ref, direct_packet),
        (chain_l3_packet_ref, chain_l3_packet),
        (chain_l4_packet_ref, chain_l4_packet),
    ):
        for input_ref in (packet.candidate_ref, packet.source_result_ref):
            assert input_ref.manifest_profile_sha256 is not None
            assert input_ref.manifest_profile_sha256 == artifact_manifest_profile_sha256(
                store.get_manifest(input_ref)
            )
    direct_source = from_canonical_bytes(
        store.get_bytes(direct_packet.source_result_ref.artifact_id)
    )
    chain_l4_source = from_canonical_bytes(
        store.get_bytes(chain_l4_packet.source_result_ref.artifact_id)
    )
    direct_source_manifest = store.get_manifest(direct_packet.source_result_ref)
    assert direct_source_manifest.kind == "scientist.policy_evaluation_vector"
    assert direct_source_manifest.media_type == "application/json"
    assert direct_source_manifest.artifact_schema is not None
    assert direct_source_manifest.artifact_schema.name == (
        "polisyos.scientist.policy_design.PolicyEvaluationVector"
    )
    assert direct_source_manifest.artifact_schema.version == "1.2"
    direct_vector = PolicyEvaluationVector.model_validate(direct_source)
    assert _policy_runtime_vector_schema_supported("1.2", direct_vector)
    assert not _policy_runtime_vector_schema_supported("1.1", direct_vector)
    assert not _policy_runtime_vector_schema_supported("1.3", direct_vector)
    alternate_version_ref = store.put_json(
        direct_vector,
        PutOptions(
            kind=direct_source_manifest.kind,
            media_type=direct_source_manifest.media_type,
            schema=SchemaInfo(
                name=direct_source_manifest.artifact_schema.name,
                version="1.3",
            ),
            producer=direct_source_manifest.producer,
            inputs=list(direct_source_manifest.inputs),
        ),
        canon_spec=CanonSpec(forbid_floats=False, exclude_none=False),
        return_selected_profile=True,
    )
    assert alternate_version_ref.artifact_id == direct_packet.source_result_ref.artifact_id
    assert alternate_version_ref.manifest_profile_sha256 != (
        direct_packet.source_result_ref.manifest_profile_sha256
    )
    assert not _policy_evaluation_vector_source_chain_matches_store(
        store,
        alternate_version_ref,
        direct_packet.candidate_ref,
        candidate.candidate_id,
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
        "usable": False,
        "normalized_value": None,
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


@pytest.mark.integration
def test_actual_runtime_writer_keeps_unavailable_draw_nulls_with_issued_attempt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Persist a valid issued attempt with absent draw config without claiming a score."""
    from polisyos.scientist.nodes.builtins.decide import policy_runtime_support

    monkeypatch.setattr(
        policy_runtime_support,
        "_production_policy_evaluation_safety_blockers",
        lambda **_: (),
    )
    store = FileSystemCAS(tmp_path / "cas")
    candidate = _policy_candidate()
    candidate_ref = persist_policy_candidate_schema(store, candidate, return_selected_profile=True)
    context = _context(store, candidate, candidate_ref)
    context.pop("estimation_config")
    engine = _PolicyRuntimeWorkflowEngine(
        fidelity="full",
        backend=ProductionPolicyEvaluationBackend(),
    )
    orchestrator = FunnelOrchestrator(
        [Level4FullFidelity(workflow_engine=engine, estimated_cost_usd=0.2)]
    )

    outcome = orchestrator.advance(
        orchestrator.submit(_candidate_payload(candidate), context),
        target_level=4,
    )

    result = outcome.stage_results[4]
    assert result.executed_work_packet_status == "available"
    assert result.executed_work_packet_ref is not None
    assert result.score_status is not ObjectiveScoreStatus.AVAILABLE
    assert result.objective_value is None
    assert result.is_promising is False
    packet = FunnelExecutedWorkPacket.model_validate(
        from_canonical_bytes(store.get_bytes(result.executed_work_packet_ref.artifact_id))
    )
    assert packet.evaluation_attempt_id
    assert packet.requested_draw_count is None
    assert packet.requested_draw_source == "unavailable"
    assert packet.effective_estimation_config_sha256 is None

    source_ref = packet.source_result_ref
    assert source_ref.manifest_profile_sha256 is not None
    source_manifest = store.get_manifest(source_ref)
    assert source_manifest.canon is not None
    assert source_manifest.canon.exclude_none is False
    vector_payload = load_core_json_artifact(store, source_ref)
    invocation = vector_payload["metadata"]["policy_runtime_invocation"]
    bootstrap = vector_payload["score_source"]["bootstrap"]
    expected = {
        "evaluation_attempt_id": packet.evaluation_attempt_id,
        "requested_draw_count": None,
        "requested_draw_source": "unavailable",
        "effective_estimation_config_sha256": None,
    }
    assert invocation == expected
    assert set(expected) <= set(bootstrap)
    assert {field: bootstrap[field] for field in expected} == expected
    restored = PolicyEvaluationVector.model_validate(vector_payload)
    assert restored.metadata["policy_runtime_invocation"] == expected
    assert restored.legacy_scalar_proxy_for_search()[1] is not ObjectiveScoreStatus.AVAILABLE


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
        return_selected_profile=True,
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


class _TerminalRejectedFullFidelity(Level4FullFidelity):
    """Retain a real evaluator packet under a test-owned terminal rejection."""

    def evaluate(self, candidate: dict[str, Any], context: dict[str, Any]) -> FunnelStageResult:
        return replace(super().evaluate(candidate, context), terminal_action="reject")


def test_cached_native_result_keeps_the_original_selected_work_identity(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    candidate = _policy_candidate()
    candidate_ref = persist_policy_candidate_schema(store, candidate, return_selected_profile=True)
    context = _context(store, candidate, candidate_ref)
    engine = _RecordingWorkflowEngine(fidelity="full")
    runtime = FunnelOrchestrator([_TerminalRejectedFullFidelity(workflow_engine=engine)])
    first = runtime.submit(_candidate_payload(candidate), context)
    first_outcome = runtime.advance(first)
    first_ref = first_outcome.stage_results[4].executed_work_packet_ref
    assert first_ref is not None
    physical = FunnelExecutedWorkPacket.model_validate(load_core_json_artifact(store, first_ref))
    original_packet_bytes = store.get_bytes(first_ref)
    second = runtime.submit(_candidate_payload(candidate), context)
    reused = runtime.advance(second)
    result = reused.stage_results[4]
    assert second.ticket_id != first.ticket_id
    source = result.feedback["funnel_result_reuse"]

    assert first_outcome.final_action == reused.final_action == "reject"
    assert second.parent_ticket_id == first.ticket_id
    assert reused.lineage == (first.ticket_id, second.ticket_id)
    assert result.executed_work_packet_status == "available"
    assert result.executed_work_packet_ref == first_ref
    assert source["request_ticket_id"] == second.ticket_id
    assert source["new_physical_work"] is False
    assert source["execution_ticket_id"] == physical.ticket_id == first.ticket_id
    assert source["execution_run_id"] == physical.run_id
    assert source["evaluation_attempt_id"] == physical.evaluation_attempt_id
    assert source["source_result_ref"] == physical.source_result_ref.model_dump(mode="json")
    assert source["executed_work_packet_ref"] == first_ref.model_dump(mode="json")
    assert store.get_bytes(first_ref) == original_packet_bytes
    assert len(engine.effective_config_inputs) == 1
    assert reused.compute_cost_usd is None
    assert reused.compute_cost_origin == "unknown"


@pytest.mark.parametrize("selected_ref_state", ["wrong_profile", "missing"])
def test_reused_work_ref_must_reopen_its_selected_profile_despite_copied_markers(
    tmp_path: Path, selected_ref_state: str
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    candidate = _policy_candidate()
    candidate_ref = persist_policy_candidate_schema(store, candidate, return_selected_profile=True)
    context = _context(store, candidate, candidate_ref)
    engine = _RecordingWorkflowEngine(fidelity="full")
    runtime = FunnelOrchestrator([_TerminalRejectedFullFidelity(workflow_engine=engine)])
    first = runtime.submit(_candidate_payload(candidate), context)
    first_outcome = runtime.advance(first)
    second = runtime.submit(_candidate_payload(candidate), context)
    source_ref = second.stage_results[4].executed_work_packet_ref
    assert source_ref is not None and source_ref.manifest_profile_sha256 is not None
    copied_feedback = deepcopy(second.stage_results[4].feedback)
    wrong_profile = source_ref.model_copy(update={"manifest_profile_sha256": "sha256:" + "f" * 64})
    second.stage_results[4].executed_work_packet_ref = (
        wrong_profile if selected_ref_state == "wrong_profile" else None
    )
    # The status and source feedback remain present. Only the consumed selected
    # CAS view differs; those copied markers must not carry the fresh projection.
    assert second.stage_results[4].executed_work_packet_status == "available"
    assert second.stage_results[4].feedback == copied_feedback
    refused = runtime.get_outcome(second)

    assert refused.final_action == "defer"
    assert refused.evaluation_status == "partial"
    assert refused.final_result is not None
    assert refused.final_result.objective_value is None
    assert refused.final_result.score_status is ObjectiveScoreStatus.NOT_ESTABLISHED
    assert refused.final_result.executed_work_packet_status == "rejected"
    assert (
        refused.final_result.feedback["funnel_result_reuse"]["executed_work_status"] == "rejected"
    )
    assert "execution_ticket_id" not in refused.final_result.feedback["funnel_result_reuse"]
    if selected_ref_state == "missing":
        assert "policy_runtime_work_packet_ref" not in refused.final_result.feedback
    assert first.stage_results[4].executed_work_packet_ref == source_ref
    assert first_outcome.stage_results[4].executed_work_packet_status == "available"
    assert refused.trace[0].executed_work_packet_ref == source_ref
    assert refused.trace[0].executed_work_packet_status == "available"
    assert refused.result_reuse_source_ticket_id == first.ticket_id
    assert len(engine.effective_config_inputs) == 1


class _ScoredTerminalFullFidelity(Level4FullFidelity):
    """Keep real engineering work with a separate declared bounded score fixture."""

    def evaluate(self, candidate: dict[str, Any], context: dict[str, Any]) -> FunnelStageResult:
        result = super().evaluate(candidate, context)
        source = {**result.simulation_results, "metric_units": {"gdp_change": "fixture-unit"}}
        assessment = GDPGrowthObjective(expected_unit="fixture-unit").evaluate(source)
        return replace(
            result,
            simulation_results=source,
            objective_value=assessment.raw_value,
            score_status=assessment.score_status,
            score_assessment=assessment.score_assessment,
            score_admission=None,
            is_promising=True,
            terminal_action="complete",
        )


class _DenySelectedWorkManifest:
    """Expose the real current store except for one denied selected work view."""

    def __init__(self, store: FileSystemCAS, denied_ref: ArtifactRef) -> None:
        self.store = store
        self.denied_ref = denied_ref

    def __getattr__(self, name: str) -> Any:
        return getattr(self.store, name)

    def get_manifest(self, ref: ArtifactRef | str) -> Any:
        if ref == self.denied_ref:
            raise OSError("selected_work_access_denied")
        return self.store.get_manifest(ref)


@pytest.mark.parametrize("selected_view", ["missing", "wrong_profile", "current_store_denied"])
def test_stage_a_uses_the_same_selected_level_from_the_current_work_projection(
    tmp_path: Path, selected_view: str
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    candidate = _policy_candidate()
    candidate_ref = persist_policy_candidate_schema(store, candidate, return_selected_profile=True)
    context = _context(store, candidate, candidate_ref)
    engine = _RecordingWorkflowEngine(fidelity="full")
    runtime = FunnelOrchestrator(
        [_ScoredTerminalFullFidelity(workflow_engine=engine)], stage_a_max_level=4
    )
    payload = _candidate_payload(candidate)
    first = runtime.submit(payload, context)
    original = runtime.advance(first)
    source_ref = first.stage_results[4].executed_work_packet_ref
    assert source_ref is not None
    assert original.final_action == "complete"
    assert original.final_result is not None
    assert original.final_result.score_status is ObjectiveScoreStatus.AVAILABLE
    assert original.final_result.executed_work_packet_status == "available"
    historical_trace = deepcopy(first.trace)
    second = runtime.submit(payload, context)
    if selected_view == "missing":
        second.stage_results[4].executed_work_packet_ref = None
    elif selected_view == "wrong_profile":
        second.stage_results[4].executed_work_packet_ref = source_ref.model_copy(
            update={"manifest_profile_sha256": "sha256:" + "f" * 64}
        )
    else:
        context = {**context, "store": _DenySelectedWorkManifest(store, source_ref)}
    # The scalar source, available marker and copied source metadata stay valid.
    # Refusal must come from the current selected work view of this same level.
    assert second.stage_results[4].score_status is ObjectiveScoreStatus.AVAILABLE
    assert second.stage_results[4].executed_work_packet_status == "available"

    bundle = runtime.as_stage_a_callable()(payload, context)

    assert bundle.score_status is ObjectiveScoreStatus.NOT_ESTABLISHED
    assert bundle.objective_value is None
    assert bundle.is_promising is False
    assert bundle.stage_a_passed is False
    assert bundle.metadata["funnel_action"] == "defer"
    assert first.trace == historical_trace
    assert all(ticket.trace == historical_trace for ticket in runtime._tickets.values())
    assert store.get_manifest(source_ref).kind == "scientist.search.funnel_native_work_packet"
    assert len(engine.effective_config_inputs) == 1
