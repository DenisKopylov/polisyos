"""Configured CAS intake and actual orchestrator/cache current/history consumers."""

import hashlib
import json
from collections.abc import Mapping
from dataclasses import replace
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from polisyos.core.artifacts.ir_adapter import CoreToIRArtifactStoreAdapter
from polisyos.core.artifacts.manifest import ArtifactRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.ir import UncertaintyType
from polisyos.scientist.methods.search.funnel.orchestrator import (
    FunnelOrchestrator,
    _admit_search_uncertainty_task,
)
from polisyos.scientist.methods.search.funnel.types import (
    CheapSignalVector,
    FunnelStage,
    FunnelStageResult,
)
from polisyos.scientist.methods.search.objective import (
    GDPGrowthObjective,
    ObjectiveScoreAssessment,
    ObjectiveScoreStatus,
)
from polisyos.scientist.methods.search.stages import CorrelationTracker
from polisyos.scientist.methods.search.uncertainty import (
    SearchAssessedObservationV2,
    SearchAssessedTargetRelation,
    SearchInputDependency,
    SearchOwnerSelectedSourceGraph,
    SearchRuntimeStageConfiguration,
    SearchUncertaintyAdmissionError,
    SearchUncertaintyBasis,
    SearchUncertaintyCompletionReceipt,
    SearchUncertaintyObservation,
    SearchUncertaintyOwnerTaskContext,
    SearchUncertaintyRoutingScore,
    SearchUncertaintyTicketState,
    StaleSearchTicketGenerationError,
    UncertaintyEnvelope,
    UncertaintyEstimate,
    _canonical_sha256,
    _point_candidate_routing_score,
    _resolved_hte_params_sha256,
    consume_completed_search_hte_attempt,
    derive_search_uncertainty_ticket_id,
    persist_search_uncertainty,
    persist_search_uncertainty_v2,
    produce_search_task_admission,
)
from polisyos.scientist.methods.search.voi_scheduler import SimpleVOIScheduler, VOICostOrigin


def test_assessed_target_relation_cannot_claim_unbound_estimand_as_recomputed():
    with pytest.raises(ValidationError, match="literal_error|Input should be 'not_established'"):
        SearchAssessedTargetRelation(
            requested_scope_status="declared",
            requested_scope="selected_evaluation_rows",
            requested_guarantee_status="declared",
            requested_guarantee="backend_conditional_interval",
            computed_scope_status="recomputed",
            computed_scope="selected_evaluation_rows",
            computed_guarantee_status="computed",
            computed_guarantee="backend_conditional_interval",
            source_content_status="content_bound",
            row_order_status="recomputed",
            contrast_status="recomputed",
            estimand_status="recomputed",
            alpha_status="recomputed",
            profile_status="qualified",
            scope_disposition="satisfied",
            guarantee_disposition="satisfied",
            overall_disposition="satisfied",
        )


def test_population_scope_mismatch_survives_unknown_source_identity():
    mismatch = SearchAssessedTargetRelation(
        requested_scope_status="declared",
        requested_scope="population",
        requested_guarantee_status="declared",
        requested_guarantee="candidate_point",
        computed_scope_status="recomputed",
        computed_scope="selected_evaluation_rows",
        computed_guarantee_status="computed",
        computed_guarantee="candidate_point",
        source_content_status="not_established",
        row_order_status="not_established",
        contrast_status="not_established",
        estimand_status="not_established",
        alpha_status="not_applicable",
        profile_status="point_only",
        scope_disposition="requested_claim_not_satisfied",
        guarantee_disposition="satisfied",
        overall_disposition="requested_claim_not_satisfied",
    )
    assert mismatch.scope_disposition == "requested_claim_not_satisfied"

    matching_but_unbound = SearchAssessedTargetRelation(
        requested_scope_status="declared",
        requested_scope="selected_evaluation_rows",
        requested_guarantee_status="declared",
        requested_guarantee="candidate_point",
        computed_scope_status="recomputed",
        computed_scope="selected_evaluation_rows",
        computed_guarantee_status="computed",
        computed_guarantee="candidate_point",
        source_content_status="not_established",
        row_order_status="not_established",
        contrast_status="not_established",
        estimand_status="not_established",
        alpha_status="not_applicable",
        profile_status="point_only",
        scope_disposition="not_established",
        guarantee_disposition="satisfied",
        overall_disposition="not_established",
    )
    assert matching_but_unbound.scope_disposition == "not_established"


def test_population_guarantee_mismatch_survives_unknown_source_identity():
    relation = SearchAssessedTargetRelation(
        requested_scope_status="declared",
        requested_scope="selected_evaluation_rows",
        requested_guarantee_status="declared",
        requested_guarantee="population_sampling_coverage",
        computed_scope_status="recomputed",
        computed_scope="selected_evaluation_rows",
        computed_guarantee_status="computed",
        computed_guarantee="backend_conditional_interval",
        source_content_status="not_established",
        row_order_status="not_established",
        contrast_status="not_established",
        estimand_status="not_established",
        alpha_status="not_established",
        profile_status="not_established",
        scope_disposition="not_established",
        guarantee_disposition="requested_claim_not_satisfied",
        overall_disposition="requested_claim_not_satisfied",
    )

    assert relation.guarantee_disposition == "requested_claim_not_satisfied"
    assert relation.overall_disposition == "requested_claim_not_satisfied"


def test_assessment_selects_one_value_carrier_and_retains_point_diagnostic_basis():
    now = datetime(2026, 10, 21, tzinfo=UTC)

    def ref(seed, kind):
        return ArtifactRef(
            artifact_id=f"sha256:{seed * 64}",
            kind=kind,
            media_type="application/json",
            manifest_profile_sha256=f"sha256:{'f' * 64}",
        )

    refs = {
        "basis": ref("1", "scientist.search.uncertainty_basis"),
        "predecessor": ref("2", "scientist.search.uncertainty_observation"),
        "binding": ref("3", "scientist.search.uncertainty_task_binding"),
        "anchor": ref("4", "runtime.owned_attempt_anchor"),
        "outcome": ref("5", "ir.hte_outcome"),
        "point": ref("6", "ir.hte_point_result"),
        "hte": ref("7", "ir.hte_result"),
        "inference": ref("8", "ir.ate_inference_basis"),
        "materialization": ref("a", "foundry.hte.physical_source_materialization_binding"),
        "route": ref("b", "scientist.search.uncertainty_routing_profile"),
        "source": ref("c", "ir.observational_data"),
        "method": ref("d", "scientist.method_result.causal.hte"),
        "evidence": ref("e", "scientist.method_evidence"),
    }

    def relation(*, interval):
        guarantee = "backend_conditional_interval" if interval else "candidate_point"
        return SearchAssessedTargetRelation(
            requested_scope_status="declared",
            requested_scope="selected_evaluation_rows",
            requested_guarantee_status="declared",
            requested_guarantee=guarantee,
            computed_scope_status="recomputed",
            computed_scope="selected_evaluation_rows",
            computed_guarantee_status="computed",
            computed_guarantee=guarantee,
            source_content_status="content_bound",
            row_order_status="recomputed",
            contrast_status="not_established",
            estimand_status="not_established",
            alpha_status="recomputed" if interval else "not_applicable",
            profile_status="qualified" if interval else "point_only",
            scope_disposition="satisfied",
            guarantee_disposition="satisfied",
            overall_disposition="not_established",
        )

    def payload(*, interval):
        theta = 0.25
        lower, upper, confidence = (0.1, 0.4, 0.95) if interval else (None, None, None)
        if interval:
            score = SearchUncertaintyRoutingScore(
                profile_ref=refs["route"],
                status="unavailable",
                unavailable_reason="scope_not_comparable",
                theta=theta,
                lower_bound=lower,
                upper_bound=upper,
                confidence_level=confidence,
                interval_semantics="native_mean_confidence_interval",
                comparison_key="a" * 64,
                limitations=("candidate_only",),
            )
        else:
            score = _point_candidate_routing_score(profile_ref=refs["route"], theta=theta)
        return {
            "basis_ref": refs["basis"],
            "obligation_id": "obligation-1",
            "ticket_id": "ticket-1",
            "ticket_generation": 0,
            "outcome_kind": "interval_estimate" if interval else "point_estimate",
            "predecessor_ref": refs["predecessor"],
            "search_uncertainty_task_binding_ref": refs["binding"],
            "owned_attempt_anchor_ref": refs["anchor"],
            "hte_outcome_ref": refs["outcome"],
            "point_result_ref": None if interval else refs["point"],
            "hte_result_ref": refs["hte"] if interval else None,
            "inference_basis_ref": refs["inference"],
            "materialization_binding_ref": refs["materialization"],
            "producer_method_fqn": "causal.hte.causal_forest@2.0.0",
            "producer_method_abi_version": "2.0.0",
            "producer_method_abi_digest": "1" * 64,
            "producer_params_sha256": "2" * 64,
            "inference_profile_id": "econml.causal_forest_dml.native_mean@2.0",
            "runtime_summary_sha256": "3" * 64,
            "input_profile_id": "all_source_rows_in_input_order@1.0",
            "selected_input_sha256": "4" * 64,
            "selected_rows_sha256": "5" * 64,
            "resolved_params_sha256": "2" * 64,
            "target_relation": relation(interval=interval),
            "run_id": "run-1",
            "job_id": "job-1",
            "attempt": 1,
            "completed_event_id": 1,
            "completed_event_payload_sha256": "6" * 64,
            "completed_at": now,
            "source_data_ref": refs["source"],
            "method_result_ref": refs["method"],
            "method_evidence_ref": refs["evidence"],
            "selected_x_sha256": "7" * 64,
            "selected_row_order_sha256": "8" * 64,
            "n_selected_rows": 1,
            "treatment_variable_id": "treatment",
            "outcome_variable_id": "outcome",
            "control_value": 0.0,
            "treated_value": 1.0,
            "theta": theta,
            "lower_bound": lower,
            "upper_bound": upper,
            "confidence_level": confidence,
            "unit_binding_status": "unknown",
            "interval_semantics": "native_mean_confidence_interval" if interval else None,
            "routing_score": score,
            "source_observation_interval_status": "not_established",
            "computed_at": now,
            "admitted_at": now,
            "limitations": ("candidate_only",),
        }

    interval = SearchAssessedObservationV2.model_validate(payload(interval=True))
    assert interval.hte_result_ref == refs["hte"]
    assert interval.point_result_ref is None

    wrong_kind = payload(interval=True)
    wrong_kind["hte_result_ref"] = refs["point"]
    with pytest.raises(ValidationError, match="HTE refs have the wrong artifact kind"):
        SearchAssessedObservationV2.model_validate(wrong_kind)

    duplicate = payload(interval=True)
    duplicate["point_result_ref"] = refs["point"]
    with pytest.raises(ValidationError, match="unique HTEResult v1 value carrier"):
        SearchAssessedObservationV2.model_validate(duplicate)

    point = SearchAssessedObservationV2.model_validate(payload(interval=False))
    assert point.point_result_ref == refs["point"]
    assert point.hte_result_ref is None
    assert point.inference_basis_ref == refs["inference"]
    assert point.lower_bound is None


def test_point_only_routing_score_rejects_every_interval_quantity():
    profile_ref = ArtifactRef(
        artifact_id=f"sha256:{'b' * 64}",
        kind="scientist.search.uncertainty_routing_profile",
        media_type="application/json",
        manifest_profile_sha256=f"sha256:{'f' * 64}",
    )
    point = _point_candidate_routing_score(profile_ref=profile_ref, theta=0.25)
    assert point.status == "unavailable"
    assert point.unavailable_reason == "interval_not_qualified"
    assert point.theta == 0.25

    allowed_fields = {
        "profile_ref",
        "status",
        "unavailable_reason",
        "theta",
        "limitations",
    }
    mutations = {
        "schema_version": "2.0",
        "profile_id": "forged_profile@1.0",
        "lower_bound": 0.1,
        "upper_bound": 0.4,
        "width": 0.3,
        "width_decimal": "0.3",
        "width_overflow": True,
        "raw_ratio_decimal": "1.2",
        "raw_ratio_overflow": True,
        "saturated": True,
        "score": 0.7,
        "confidence_level": 0.95,
        "interval_semantics": "native_mean_confidence_interval",
        "comparison_key": "a" * 64,
    }
    assert set(mutations) == set(type(point).model_fields) - allowed_fields
    for field_name, replacement in mutations.items():
        forged = point.model_dump(mode="python")
        forged[field_name] = replacement
        with pytest.raises(ValidationError):
            SearchUncertaintyRoutingScore.model_validate(forged)


def test_hte_execution_digest_keeps_seed_distinct_from_search_params_only_digest():
    params = {"max_depth": 3, "min_samples_leaf": 4}
    params_only = _canonical_sha256(params)
    with_seed_17 = _resolved_hte_params_sha256(params, 17)
    with_seed_18 = _resolved_hte_params_sha256(params, 18)

    assert with_seed_17 == _canonical_sha256({"params": params, "seed": 17})
    assert with_seed_17 != params_only
    assert with_seed_17 != with_seed_18


def test_completion_receipt_does_not_treat_missing_binding_as_absence():
    with pytest.raises(ValidationError, match="owner-proven Search absence"):
        SearchUncertaintyCompletionReceipt(
            status="not_applicable",
            job_id="job-1",
            completed_event_id=19,
        )

    pending = SearchUncertaintyCompletionReceipt(
        status="not_established",
        job_id="job-1",
        completed_event_id=19,
        reason_code="search_binding_missing",
        next_check="Re-resolve the Search task binding from the exact completed owner event.",
    )
    assert pending.status == "not_established"


def test_consumer_does_not_infer_absence_from_missing_historical_binding(tmp_path):
    backend = FileSystemCAS(tmp_path / "cas")

    class ConfiguredStoreProxy:
        @property
        def root(self):
            return backend.root

        def __getattr__(self, name):
            return getattr(backend, name)

    completed_at = datetime(2026, 10, 21, tzinfo=UTC)
    association = SimpleNamespace(
        schema_version="1.0",
        status="owner_selection_reconciled",
        job_id="job-1",
        search_uncertainty_task_binding_ref=None,
        search_binding_status="not_applicable",
        job_completed_event=SimpleNamespace(
            event_id=19,
            job_id="job-1",
            event_type="job_completed",
            payload_sha256="a" * 64,
            created_at=completed_at,
        ),
    )
    owner = SimpleNamespace(
        resolve_historical_completed_method_execution=lambda **_kwargs: association
    )

    receipt = consume_completed_search_hte_attempt(
        store=ConfiguredStoreProxy(),
        owner=owner,
        job_id="job-1",
        completed_event_id=19,
        tenant_id="tenant-1",
        cell_id=None,
    )

    assert receipt.status == "not_established"
    assert receipt.reason_code == "search_binding_missing"


def test_consumer_rejects_nonpositive_completion_event_id(tmp_path):
    owner = SimpleNamespace(resolve_historical_completed_method_execution=lambda **_kwargs: None)

    with pytest.raises(ValueError, match="positive Runtime event ID"):
        consume_completed_search_hte_attempt(
            store=FileSystemCAS(tmp_path / "cas"),
            owner=owner,
            job_id="job-1",
            completed_event_id=0,
            tenant_id="tenant-1",
            cell_id=None,
        )


class ProducerStage(FunnelStage):
    """Permitted injected callback on the actual orchestrator, not its surrogate."""

    def __init__(self, level, result):
        self.level, self.result, self.calls = level, result, 0

    @property
    def stage_name(self):
        return f"producer-{self.level}"

    @property
    def fidelity_level(self):
        return self.level

    @property
    def estimated_cost_usd(self):
        return 0.0

    def evaluate(self, candidate, context):
        self.calls += 1
        return replace(self.result, policy_candidate=candidate)


def _envelope(level):
    return UncertaintyEnvelope.from_partial(
        {
            kind: UncertaintyEstimate(
                level=level,
                source="fixture producer",
                quantification_method="supplied fixture measurement",
                is_reducible=True,
            )
            for kind in UncertaintyType
        }
    )


@pytest.fixture
def packet(tmp_path):
    store = FileSystemCAS(tmp_path / "cas")

    def ref(name):
        return store.put_json(
            {"fixture": name}, PutOptions(kind="scientist.test", media_type="application/json")
        )

    basis = SearchUncertaintyBasis(
        subject_ref=ref("candidate"),
        value_ref=ref("value"),
        input_refs=(ref("input"),),
        rule_ref=ref("rule"),
        producer_ref=ref("producer"),
        valid_time=datetime(2026, 10, 8, tzinfo=UTC),
        estimand="ATE",
        unit="kg",
    )
    basis_ref = persist_search_uncertainty(store, basis)

    def stage(level, envelope, *, supplied_basis=basis_ref, producer=None, risk=None):
        observation = SearchUncertaintyObservation(
            basis_ref=supplied_basis,
            producer_ref=producer or basis.producer_ref,
            risk_ref=risk or ref(f"risk-{level}"),
            envelope=envelope,
        )
        observation_ref = persist_search_uncertainty(store, observation)
        return ProducerStage(
            level,
            FunnelStageResult(
                policy_candidate={},
                objective_value=1.0,
                is_promising=True,
                stage_name=f"producer-{level}",
                fidelity_level=level,
                uncertainty_envelope=envelope,
                uncertainty_observation_ref=observation_ref,
            ),
        )

    return store, basis, basis_ref, ref, stage


def _context(packet):
    store, basis, basis_ref, _, _ = packet
    return {
        "store": store,
        "uncertainty_basis_ref": basis_ref,
        "policy_candidate_ref": basis.subject_ref,
    }


def test_legacy_v1_observations_remain_routing_history_without_current_claim(packet):
    _, _, _, _, stage = packet
    early, late = stage(0, _envelope(0.9)), stage(1, _envelope(0.1))
    runtime = FunnelOrchestrator([early, late])
    ticket = runtime.submit({"candidate": "a"}, _context(packet))
    outcome = runtime.advance(ticket)
    assert outcome.current_uncertainty_envelope is None
    assert outcome.uncertainty_envelope == _envelope(0.9)
    assert outcome.uncertainty_observation_refs == []
    assert "legacy_v1_observations_route_only" in outcome.uncertainty_intake_failures
    assert outcome.final_result.feedback["uncertainty_current"] is None
    assert early.result.feedback == late.result.feedback == {}
    fresh = runtime.get_outcome(ticket)
    assert fresh.current_uncertainty_envelope is None
    assert fresh.uncertainty_envelope == _envelope(0.9)


@pytest.mark.parametrize(
    "field",
    [
        "value_ref",
        "input_refs",
        "rule_ref",
        "valid_time",
        "unit",
        "estimand",
        "subject_ref",
        "producer_ref",
    ],
)
def test_legacy_changed_producer_basis_cannot_change_current_claim(packet, field):
    store, basis, basis_ref, ref, stage = packet
    change = {
        "unit": "USD",
        "estimand": "foreign population",
        "valid_time": datetime(2027, 1, 1, tzinfo=UTC),
        "input_refs": (ref("foreign-input"),),
    }
    foreign = basis.model_copy(update={field: change.get(field, ref("foreign"))})
    foreign_ref = persist_search_uncertainty(store, foreign)
    early, late = stage(0, _envelope(0.9)), stage(1, _envelope(0.1), supplied_basis=foreign_ref)
    runtime = FunnelOrchestrator([early, late])
    outcome = runtime.advance(runtime.submit({}, _context(packet)))
    assert outcome.current_uncertainty_envelope is None
    assert outcome.uncertainty_envelope == _envelope(0.9)
    assert "legacy_v1_observations_route_only" in outcome.uncertainty_intake_failures
    assert outcome.final_result.feedback["uncertainty_current_status"] == "not_established"


def test_missing_and_substituted_envelope_do_not_become_current(packet):
    _, _, _, _, stage = packet
    producer = stage(0, _envelope(0.9))
    producer.result = replace(producer.result, uncertainty_envelope=_envelope(0.1))
    runtime = FunnelOrchestrator([producer])
    outcome = runtime.advance(runtime.submit({}, _context(packet)))
    assert outcome.current_uncertainty_envelope is None
    assert "legacy_v1_observations_route_only" in outcome.uncertainty_intake_failures
    producer.result = replace(producer.result, uncertainty_observation_ref=None)
    runtime = FunnelOrchestrator([producer])
    outcome = runtime.advance(runtime.submit({}, _context(packet)))
    assert outcome.current_uncertainty_envelope is None
    assert outcome.final_result.feedback["uncertainty_current"] is None


def test_same_request_reuses_real_cache_changed_version_executes_callback(packet):
    store, basis, _, _, stage = packet
    producer = stage(0, _envelope(0.3))
    runtime = FunnelOrchestrator([producer])
    context = _context(packet)
    first = runtime.submit({"a": 1}, context)
    runtime.advance(first)
    second = runtime.submit({"a": 1}, context)
    runtime.advance(second)
    assert producer.calls == 1
    changed = persist_search_uncertainty(store, basis.model_copy(update={"unit": "USD"}))
    third = runtime.submit({"a": 1}, {**context, "uncertainty_basis_ref": changed})
    outcome = runtime.advance(third)
    assert producer.calls == 2
    assert outcome.current_uncertainty_envelope is None


def test_selected_manifest_view_change_executes_real_callback(packet):
    from polisyos.core.artifacts.manifest import SchemaInfo
    from polisyos.core.canon import CanonSpec

    store, basis, basis_ref, _, stage = packet
    producer = stage(0, _envelope(0.3))
    runtime = FunnelOrchestrator([producer])
    context = _context(packet)
    runtime.advance(runtime.submit({"a": 1}, context))
    different_view = store.put_json(
        basis,
        PutOptions(
            kind="scientist.search.uncertainty_basis",
            media_type="application/json",
            schema=SchemaInfo(name="SameScientificContentDifferentView", version="1.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    assert different_view.artifact_id == basis_ref.artifact_id
    assert different_view.manifest_profile_sha256 != basis_ref.manifest_profile_sha256
    outcome = runtime.advance(
        runtime.submit({"a": 1}, {**context, "uncertainty_basis_ref": different_view})
    )
    assert producer.calls == 2
    assert outcome.current_uncertainty_envelope is None
    assert "legacy_v1_observations_route_only" in outcome.uncertainty_intake_failures


def test_pre_dispatch_admission_resolves_native_owner_through_ir_adapter(tmp_path):
    store = FileSystemCAS(tmp_path / "cas")
    subject_ref = store.put_json(
        {"fixture": "candidate"},
        PutOptions(kind="scientist.test", media_type="application/json"),
        return_selected_profile=True,
    )
    owner_context = SearchUncertaintyOwnerTaskContext(
        owner_fqn=(
            "polisyos.scientist.nodes.builtins.decide.policy_blueprint_runtime_engine."
            "run_runtime_funnel"
        ),
        run_id="run_native_owner",
        subject_ref=subject_ref,
        selected_stage_config_sha256="a" * 64,
        status="not_established",
        missing_slices=(
            "selected_executable_plan_configuration_graph_rule_profile_procedure_selection",
            "selected_method_abi_params_profile",
            "semantic_scope_owner",
            "owned_hte_request_projection",
            "owner_tenant_scope",
            "selected_method_seed",
            "selected_method_input_owner",
            "selected_method_input_content_digest",
        ),
    )
    ticket_id = derive_search_uncertainty_ticket_id(owner_context.run_id, subject_ref)

    admitted_ticket_id, generation, binding_ref, error = _admit_search_uncertainty_task(
        funnel_ticket_id=ticket_id,
        owner_context=owner_context,
        context={"store": CoreToIRArtifactStoreAdapter(store)},
        owned_attempt_association_resolver=None,
        owned_historical_attempt_association_resolver=None,
    )

    assert error is None
    assert admitted_ticket_id == ticket_id
    assert generation == 1
    assert binding_ref is None
    current = SearchUncertaintyTicketState(store).read_current_snapshot(ticket_id)
    assert current is not None
    assert current.status == "available_as_of_task_epoch"
    assert current.task_admission is not None
    assert current.task_admission.status == "not_established"
    assert current.task_admission.basis_ref is None


def test_pre_dispatch_admission_rejects_store_without_native_search_capabilities(tmp_path):
    store = FileSystemCAS(tmp_path / "cas")
    subject_ref = store.put_json(
        {"fixture": "candidate"},
        PutOptions(kind="scientist.test", media_type="application/json"),
        return_selected_profile=True,
    )
    owner_context = SearchUncertaintyOwnerTaskContext(
        owner_fqn=(
            "polisyos.scientist.nodes.builtins.decide.policy_blueprint_runtime_engine."
            "run_runtime_funnel"
        ),
        run_id="run_incompatible_owner",
        subject_ref=subject_ref,
        selected_stage_config_sha256="b" * 64,
        status="not_established",
        missing_slices=(
            "selected_executable_plan_configuration_graph_rule_profile_procedure_selection",
            "selected_method_abi_params_profile",
            "semantic_scope_owner",
            "owned_hte_request_projection",
            "owner_tenant_scope",
            "selected_method_seed",
            "selected_method_input_owner",
            "selected_method_input_content_digest",
        ),
    )
    ticket_id = derive_search_uncertainty_ticket_id(owner_context.run_id, subject_ref)
    ticket_state_root = store.root / "scientist-funnel" / "ticket-owner-state"
    assert not ticket_state_root.exists()

    result = _admit_search_uncertainty_task(
        funnel_ticket_id=ticket_id,
        owner_context=owner_context,
        context={"store": SimpleNamespace()},
        owned_attempt_association_resolver=None,
        owned_historical_attempt_association_resolver=None,
    )

    assert result == (None, None, None, "artifact_store_incompatible")
    assert not ticket_state_root.exists()


class _RecordingSimpleVOIScheduler(SimpleVOIScheduler):
    def __init__(self) -> None:
        super().__init__()
        self.observed_candidate_ids: list[str] = []
        self.calibration_states: list[Mapping[str, object]] = []

    def observe_stage_result(
        self,
        *,
        candidate_id: str,
        task_family: str = "policy",
        domain: str = "",
        tenant_hash: str = "",
        stage_level: int,
        frontier_position: str = "unknown",
        cheap_signal: CheapSignalVector | None = None,
        actual_objective_value: float | None,
        score_assessment: ObjectiveScoreAssessment | None = None,
        objective_source: Mapping[str, object] | None = None,
        actual_promising: bool,
        duration_seconds: float,
        compute_cost_usd: float | None,
        compute_cost_origin: VOICostOrigin,
        timeout_occurred: bool = False,
        disagreement: float | None = None,
        metadata: dict[str, object] | None = None,
    ) -> None:
        self.observed_candidate_ids.append(candidate_id)

    def update_calibration_state(self, metrics: Mapping[str, object]) -> None:
        self.calibration_states.append(dict(metrics))


def test_simple_scheduler_subclass_optional_callbacks_are_consumed() -> None:
    simulation_results = {
        "gdp_change": 1.0,
        "metric_units": {"gdp_change": "percentage-points"},
    }
    score = GDPGrowthObjective(expected_unit="percentage-points").evaluate(simulation_results)
    assessment = score.score_assessment
    assert assessment is not None
    assert assessment.value is not None
    assert assessment.status is ObjectiveScoreStatus.AVAILABLE
    result = FunnelStageResult(
        policy_candidate={"candidate": "callback"},
        objective_value=assessment.value,
        is_promising=True,
        stage_name="callback-stage",
        score_status=ObjectiveScoreStatus.AVAILABLE,
        score_assessment=assessment,
        duration_seconds=0.25,
        simulation_results=simulation_results,
        fidelity_level=1,
    )
    tracker = CorrelationTracker()
    scheduler = _RecordingSimpleVOIScheduler()
    runtime = FunnelOrchestrator(
        [],
        voi_scheduler=scheduler,
        correlation_tracker=tracker,
    )
    ticket = runtime.submit({"candidate": "callback"}, {})
    runtime._maybe_record_voi_observation(ticket, result, stage_level=1)
    runtime._maybe_update_voi_calibration_state()
    assert scheduler.observed_candidate_ids == [ticket.candidate_hash]
    assert scheduler.calibration_states == [tracker.compute_metrics()]

    simple_scheduler = SimpleVOIScheduler()
    simple_runtime = FunnelOrchestrator(
        [],
        voi_scheduler=simple_scheduler,
        correlation_tracker=CorrelationTracker(),
    )
    simple_ticket = simple_runtime.submit({"candidate": "simple"}, {})
    simple_runtime._maybe_record_voi_observation(simple_ticket, result, stage_level=1)
    simple_runtime._maybe_update_voi_calibration_state()


def test_pre_dispatch_task_admission_is_durable_and_reissued_by_generation(tmp_path):
    store = FileSystemCAS(tmp_path / "cas")

    def selected_ref(name):
        return store.put_json(
            {"fixture": name},
            PutOptions(kind="scientist.test", media_type="application/json"),
            return_selected_profile=True,
        )

    subject_ref = selected_ref("candidate")
    source_input_ref = selected_ref("selected-input")
    stage_payload = {
        "owner_fqn": (
            "polisyos.scientist.nodes.builtins.decide.policy_blueprint_runtime_engine."
            "run_runtime_funnel"
        ),
        "stages": ({"stage_name": "L0", "fidelity_level": 0},),
        "unresolved_bindings": (),
    }
    stage_digest = hashlib.sha256(
        json.dumps(
            stage_payload,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()
    stage_configuration_ref = persist_search_uncertainty_v2(
        store,
        SearchRuntimeStageConfiguration(
            owner_fqn=stage_payload["owner_fqn"],
            stages=stage_payload["stages"],
            unresolved_bindings=(),
            configuration_sha256=stage_digest,
        ),
    )
    source_graph = SearchOwnerSelectedSourceGraph(
        roots=(
            SearchInputDependency(role_path="candidate", ref=subject_ref),
            SearchInputDependency(role_path="stage_configuration", ref=stage_configuration_ref),
            SearchInputDependency(role_path="state_input.fixture", ref=source_input_ref),
        )
    )
    source_graph_ref = persist_search_uncertainty_v2(store, source_graph)
    owner_context = SearchUncertaintyOwnerTaskContext(
        owner_fqn=(
            "polisyos.scientist.nodes.builtins.decide.policy_blueprint_runtime_engine."
            "run_runtime_funnel"
        ),
        run_id="run_ad06_durable",
        subject_ref=subject_ref,
        selected_configuration_ref=stage_configuration_ref,
        selected_source_graph_ref=source_graph_ref,
        selected_stage_config_sha256=stage_digest,
        selected_state_input_refs=(
            SearchInputDependency(role_path="state_input.fixture", ref=source_input_ref),
        ),
        status="not_established",
        missing_slices=(
            "selected_executable_plan_configuration_graph_rule_profile_procedure_selection",
            "selected_method_abi_params_profile",
            "semantic_scope_owner",
            "owned_hte_request_projection",
            "owner_tenant_scope",
            "selected_method_seed",
            "selected_method_input_owner",
            "selected_method_input_content_digest",
        ),
    )
    ticket_id = derive_search_uncertainty_ticket_id(owner_context.run_id, subject_ref)
    state = SearchUncertaintyTicketState(store)
    initial_row = state.initialize(ticket_id)
    _, _, admission_ref, basis_ref = produce_search_task_admission(
        store,
        owner_context,
        ticket_id=ticket_id,
        ticket_generation=initial_row.ticket_generation,
        selected_at=datetime(2026, 10, 21, tzinfo=UTC),
    )
    assert basis_ref is None
    first = state.record_task_admission(
        ticket_id=ticket_id,
        expected_generation=initial_row.ticket_generation,
        expected_projection_revision=initial_row.projection_revision,
        admission_ref=admission_ref,
    )
    duplicate = state.record_task_admission(
        ticket_id=ticket_id,
        expected_generation=initial_row.ticket_generation,
        expected_projection_revision=initial_row.projection_revision,
        admission_ref=admission_ref,
    )
    assert duplicate == first

    restarted = SearchUncertaintyTicketState(store)
    fresh = restarted.read_current_snapshot(ticket_id)
    assert fresh is not None
    assert fresh.status == "available_as_of_task_epoch"
    assert fresh.task_admission is not None
    assert fresh.task_admission.status == "not_established"
    assert fresh.task_admission.basis_ref is None
    assert fresh.projection is not None
    assert fresh.projection.current_obligations == ()
    assert fresh.projection.active_unknown_obligation_ids == ()
    assert fresh.projection.incomplete_obligation_ids == ()

    reissued = restarted.bump_ticket_generation(
        ticket_id, expected_generation=initial_row.ticket_generation
    )
    assert reissued.ticket_generation == initial_row.ticket_generation + 1
    with pytest.raises(StaleSearchTicketGenerationError):
        restarted.record_task_admission(
            ticket_id=ticket_id,
            expected_generation=initial_row.ticket_generation,
            expected_projection_revision=initial_row.projection_revision,
            admission_ref=admission_ref,
        )
    after_reissue = SearchUncertaintyTicketState(store).read_current_snapshot(ticket_id)
    assert after_reissue is not None
    assert after_reissue.status == "available_as_of_task_epoch"
    assert after_reissue.ticket_generation == initial_row.ticket_generation + 1
    assert after_reissue.admission_status == "missing"
    assert after_reissue.projection is not None
    assert after_reissue.projection.current_obligations == ()


def test_pre_dispatch_admission_rejects_owner_context_source_graph_substitution(tmp_path):
    store = FileSystemCAS(tmp_path / "cas")

    def selected_ref(name):
        return store.put_json(
            {"fixture": name},
            PutOptions(kind="scientist.test", media_type="application/json"),
            return_selected_profile=True,
        )

    subject_ref = selected_ref("candidate")
    graph_input_ref = selected_ref("graph-input")
    owner_input_ref = selected_ref("different-owner-input")
    stage_payload = {
        "owner_fqn": (
            "polisyos.scientist.nodes.builtins.decide.policy_blueprint_runtime_engine."
            "run_runtime_funnel"
        ),
        "stages": ({"stage_name": "L0", "fidelity_level": 0},),
        "unresolved_bindings": (),
    }
    stage_digest = hashlib.sha256(
        json.dumps(
            stage_payload,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()
    stage_configuration_ref = persist_search_uncertainty_v2(
        store,
        SearchRuntimeStageConfiguration(
            owner_fqn=stage_payload["owner_fqn"],
            stages=stage_payload["stages"],
            unresolved_bindings=(),
            configuration_sha256=stage_digest,
        ),
    )
    source_graph_ref = persist_search_uncertainty_v2(
        store,
        SearchOwnerSelectedSourceGraph(
            roots=(
                SearchInputDependency(role_path="candidate", ref=subject_ref),
                SearchInputDependency(role_path="stage_configuration", ref=stage_configuration_ref),
                SearchInputDependency(role_path="state_input.fixture", ref=graph_input_ref),
            )
        ),
    )
    context = SearchUncertaintyOwnerTaskContext(
        owner_fqn=(
            "polisyos.scientist.nodes.builtins.decide.policy_blueprint_runtime_engine."
            "run_runtime_funnel"
        ),
        run_id="run_ad06_graph_substitution",
        subject_ref=subject_ref,
        selected_configuration_ref=stage_configuration_ref,
        selected_source_graph_ref=source_graph_ref,
        selected_stage_config_sha256=stage_digest,
        selected_state_input_refs=(
            SearchInputDependency(role_path="state_input.fixture", ref=owner_input_ref),
        ),
        status="not_established",
        missing_slices=(
            "selected_executable_plan_configuration_graph_rule_profile_procedure_selection",
            "selected_method_abi_params_profile",
            "semantic_scope_owner",
            "owned_hte_request_projection",
            "owner_tenant_scope",
            "selected_method_seed",
            "selected_method_input_owner",
            "selected_method_input_content_digest",
        ),
    )
    with pytest.raises(ValueError, match="source graph differs"):
        produce_search_task_admission(
            store,
            context,
            ticket_id=derive_search_uncertainty_ticket_id(context.run_id, context.subject_ref),
            ticket_generation=0,
            selected_at=datetime(2026, 10, 21, tzinfo=UTC),
        )


def test_pre_dispatch_source_graph_must_bind_instantiated_stage_configuration(tmp_path):
    store = FileSystemCAS(tmp_path / "cas")
    subject_ref = store.put_json(
        {"fixture": "candidate"},
        PutOptions(kind="scientist.test", media_type="application/json"),
        return_selected_profile=True,
    )
    stage_payload = {
        "owner_fqn": (
            "polisyos.scientist.nodes.builtins.decide.policy_blueprint_runtime_engine."
            "run_runtime_funnel"
        ),
        "stages": ({"stage_name": "L0", "fidelity_level": 0},),
        "unresolved_bindings": (),
    }
    stage_digest = hashlib.sha256(
        json.dumps(
            stage_payload,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()
    stage_configuration_ref = persist_search_uncertainty_v2(
        store,
        SearchRuntimeStageConfiguration(
            owner_fqn=stage_payload["owner_fqn"],
            stages=stage_payload["stages"],
            unresolved_bindings=(),
            configuration_sha256=stage_digest,
        ),
    )
    # The graph is internally valid but deliberately omits the real selected L0 stack.
    source_graph_ref = persist_search_uncertainty_v2(
        store,
        SearchOwnerSelectedSourceGraph(
            roots=(SearchInputDependency(role_path="candidate", ref=subject_ref),)
        ),
    )
    context = SearchUncertaintyOwnerTaskContext(
        owner_fqn=stage_payload["owner_fqn"],
        run_id="run_ad06_missing_stage_root",
        subject_ref=subject_ref,
        selected_configuration_ref=stage_configuration_ref,
        selected_source_graph_ref=source_graph_ref,
        selected_stage_config_sha256=stage_digest,
        status="not_established",
        missing_slices=(
            "selected_executable_plan_configuration_graph_rule_profile_procedure_selection",
            "selected_method_abi_params_profile",
            "semantic_scope_owner",
            "owned_hte_request_projection",
            "owner_tenant_scope",
            "selected_method_seed",
            "selected_method_input_owner",
            "selected_method_input_content_digest",
        ),
    )
    with pytest.raises(ValueError, match="source graph differs"):
        produce_search_task_admission(
            store,
            context,
            ticket_id=derive_search_uncertainty_ticket_id(context.run_id, context.subject_ref),
            ticket_generation=0,
            selected_at=datetime(2026, 10, 21, tzinfo=UTC),
        )


def test_assessment_owner_join_fails_closed_without_or_on_mismatched_runtime_reader(tmp_path):
    store = FileSystemCAS(tmp_path / "cas")
    now = datetime(2026, 10, 21, tzinfo=UTC)

    def artifact_ref(seed, kind):
        return ArtifactRef(
            artifact_id=f"sha256:{seed * 64}",
            kind=kind,
            media_type="application/json",
            manifest_profile_sha256=f"sha256:{'f' * 64}",
        )

    refs = {
        "anchor": artifact_ref("1", "runtime.owned_attempt_anchor"),
        "outcome": artifact_ref("2", "ir.hte_outcome"),
        "source": artifact_ref("3", "ir.observational_data"),
        "method_result": artifact_ref("4", "scientist.method_result.causal.hte"),
        "method_evidence": artifact_ref("5", "scientist.method_evidence"),
        "inference_basis": artifact_ref("6", "ir.ate_inference_basis"),
        "hte_result": artifact_ref("b", "ir.hte_result"),
        "materialization": artifact_ref("a", "foundry.hte.physical_source_materialization_binding"),
        "binding": artifact_ref("9", "scientist.search.uncertainty_task_binding"),
    }
    assessment = SearchAssessedObservationV2.model_construct(
        owned_attempt_anchor_ref=refs["anchor"],
        hte_outcome_ref=refs["outcome"],
        invocation_basis_ref=None,
        source_data_ref=refs["source"],
        method_result_ref=refs["method_result"],
        method_evidence_ref=refs["method_evidence"],
        inference_basis_ref=refs["inference_basis"],
        point_result_ref=None,
        hte_result_ref=refs["hte_result"],
        materialization_binding_ref=refs["materialization"],
        search_uncertainty_task_binding_ref=refs["binding"],
        job_id="job-1",
        run_id="run-1",
        attempt=4,
        completed_event_id=19,
        completed_event_payload_sha256="a" * 64,
        completed_at=now,
    )
    missing = SearchUncertaintyTicketState(store)
    with pytest.raises(SearchUncertaintyAdmissionError) as unavailable:
        missing._verify_owned_attempt_association(assessment)
    assert unavailable.value.reason_code == "runtime_attempt_association_unavailable"

    marker_only = SearchUncertaintyTicketState(
        store,
        owned_attempt_association_resolver=lambda **_kwargs: True,
    )
    with pytest.raises(SearchUncertaintyAdmissionError) as refused:
        marker_only._verify_owned_attempt_association(assessment)
    assert refused.value.reason_code == "runtime_attempt_association_mismatch"

    association = SimpleNamespace(
        schema_version="1.0",
        status="owner_selection_reconciled",
        anchor_ref=refs["anchor"],
        outcome_ref=refs["outcome"],
        outcome_kind="interval_estimate",
        invocation_basis_ref=None,
        refusal_diagnostic_ref=None,
        source_data_ref=refs["source"],
        materialization_binding_ref=refs["materialization"],
        search_uncertainty_task_binding_ref=refs["binding"],
        method_result_ref=refs["method_result"],
        method_evidence_ref=refs["method_evidence"],
        inference_basis_ref=refs["inference_basis"],
        point_result_ref=None,
        hte_result_ref=refs["hte_result"],
        job_id="job-1",
        run_id="run-1",
        attempt=4,
        job_completed_event=SimpleNamespace(
            event_id=19,
            job_id="job-1",
            event_type="job_completed",
            payload_sha256="a" * 64,
            created_at=now,
        ),
    )
    wrong_attempt_fields = vars(association).copy()
    wrong_attempt_fields["attempt"] = 3
    wrong_attempt = SimpleNamespace(**wrong_attempt_fields)
    mismatched = SearchUncertaintyTicketState(
        store,
        owned_attempt_association_resolver=lambda *, anchor_ref: wrong_attempt,
    )
    with pytest.raises(SearchUncertaintyAdmissionError) as attempt_refused:
        mismatched._verify_owned_attempt_association(assessment)
    assert attempt_refused.value.reason_code == "runtime_attempt_association_mismatch"

    wrong_event_fields = vars(association).copy()
    wrong_event_fields["job_completed_event"] = SimpleNamespace(
        event_id=19,
        job_id="job-1",
        event_type="job_completed",
        payload_sha256="b" * 64,
        created_at=now,
    )
    wrong_event = SimpleNamespace(**wrong_event_fields)
    mismatched_event = SearchUncertaintyTicketState(
        store,
        owned_attempt_association_resolver=lambda *, anchor_ref: wrong_event,
    )
    with pytest.raises(SearchUncertaintyAdmissionError) as event_refused:
        mismatched_event._verify_owned_attempt_association(assessment)
    assert event_refused.value.reason_code == "runtime_attempt_association_mismatch"


def test_search_cannot_admit_caller_scalar_assessment_without_persisted_hte_content(tmp_path):
    state = SearchUncertaintyTicketState(FileSystemCAS(tmp_path / "cas"))
    row = state.initialize("ticket-with-no-content-reader")
    placeholder = ArtifactRef(
        artifact_id=f"sha256:{'8' * 64}",
        kind="scientist.search.uncertainty_observation",
        media_type="application/json",
        manifest_profile_sha256=f"sha256:{'9' * 64}",
    )

    with pytest.raises(ValueError, match="failed integrity verification"):
        state.record_first_assessment(
            ticket_id=row.ticket_id,
            expected_generation=row.ticket_generation,
            expected_projection_revision=row.projection_revision,
            predecessor_ref=placeholder,
            successor_ref=placeholder,
            refinement_ref=placeholder,
            completion_owner=SimpleNamespace(),
            tenant_id="tenant-1",
            cell_id=None,
        )
    assert state._read_row(row.ticket_id) == row


def test_current_snapshot_rejects_task_admission_mixed_with_selected_projection(tmp_path):
    """The persisted owner row and its selected projection must name one admission."""
    store = FileSystemCAS(tmp_path / "cas")
    owner_fqn = (
        "polisyos.scientist.nodes.builtins.decide.policy_blueprint_runtime_engine."
        "run_runtime_funnel"
    )

    def selected_ref(name):
        return store.put_json(
            {"fixture": name},
            PutOptions(
                kind="scientist.test",
                media_type="application/json",
                schema=SchemaInfo(name="test.SearchOwnerInput", version="1.0"),
            ),
            return_selected_profile=True,
        )

    subject_ref = selected_ref("candidate")
    first_input_ref = selected_ref("first-input")
    substituted_input_ref = selected_ref("substituted-input")
    stage_payload = {
        "owner_fqn": owner_fqn,
        "stages": ({"stage_name": "L0", "fidelity_level": 0},),
        "unresolved_bindings": (),
    }
    stage_digest = hashlib.sha256(
        json.dumps(
            stage_payload,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()
    stage_configuration_ref = persist_search_uncertainty_v2(
        store,
        SearchRuntimeStageConfiguration(
            owner_fqn=owner_fqn,
            stages=stage_payload["stages"],
            unresolved_bindings=(),
            configuration_sha256=stage_digest,
        ),
    )

    def owner_context(input_ref):
        source_graph_ref = persist_search_uncertainty_v2(
            store,
            SearchOwnerSelectedSourceGraph(
                roots=(
                    SearchInputDependency(role_path="candidate", ref=subject_ref),
                    SearchInputDependency(
                        role_path="stage_configuration",
                        ref=stage_configuration_ref,
                    ),
                    SearchInputDependency(role_path="state_input.fixture", ref=input_ref),
                )
            ),
        )
        return SearchUncertaintyOwnerTaskContext(
            owner_fqn=owner_fqn,
            run_id="run_ad06_admission_pointer_substitution",
            subject_ref=subject_ref,
            selected_configuration_ref=stage_configuration_ref,
            selected_source_graph_ref=source_graph_ref,
            selected_stage_config_sha256=stage_digest,
            selected_state_input_refs=(
                SearchInputDependency(role_path="state_input.fixture", ref=input_ref),
            ),
            status="not_established",
            missing_slices=(
                "selected_executable_plan_configuration_graph_rule_profile_procedure_selection",
                "selected_method_abi_params_profile",
                "semantic_scope_owner",
                "owned_hte_request_projection",
                "owner_tenant_scope",
                "selected_method_seed",
                "selected_method_input_owner",
                "selected_method_input_content_digest",
            ),
        )

    ticket_id = "ticket_ad06_admission_pointer_substitution"
    state = SearchUncertaintyTicketState(store)
    initial = state.initialize(ticket_id)
    _, _, selected_admission_ref, _ = produce_search_task_admission(
        store,
        owner_context(first_input_ref),
        ticket_id=ticket_id,
        ticket_generation=initial.ticket_generation,
        selected_at=datetime(2026, 10, 21, tzinfo=UTC),
    )
    assert selected_admission_ref is not None
    state.record_task_admission(
        ticket_id=ticket_id,
        expected_generation=initial.ticket_generation,
        expected_projection_revision=initial.projection_revision,
        admission_ref=selected_admission_ref,
    )
    admitted_read = state.read_current_snapshot(ticket_id)
    assert admitted_read is not None
    assert admitted_read.status == "available_as_of_task_epoch"
    assert admitted_read.task_admission_ref == selected_admission_ref

    _, _, foreign_admission_ref, _ = produce_search_task_admission(
        store,
        owner_context(substituted_input_ref),
        ticket_id=ticket_id,
        ticket_generation=initial.ticket_generation,
        selected_at=datetime(2026, 10, 21, tzinfo=UTC),
    )
    assert foreign_admission_ref is not None
    selected_row = state._read_row(ticket_id)
    assert selected_row is not None
    state._write_row(selected_row.model_copy(update={"task_admission_ref": foreign_admission_ref}))

    refused_read = state.read_current_snapshot(ticket_id)
    assert refused_read is not None
    assert refused_read.status == "not_established"
    assert refused_read.reason_code == "search_projection_mismatch"


def _ready_current_projection_packet(store: FileSystemCAS, *, run_id: str):
    """Build a complete test-owned task basis through the real admission producer."""
    from polisyos.core.contracts.execution_plan import (
        ExecutionPlan,
        MethodCatalogEntry,
        MethodCatalogSnapshot,
        MethodDagNode,
    )
    from polisyos.foundry.methods.catalog.snapshot import persist_method_catalog_snapshot
    from polisyos.scientist.methods.search.uncertainty import (
        SearchRuntimeStageConfiguration,
        SearchUncertaintyHTERequestProjection,
        SearchUncertaintySemanticScope,
        _canonical_sha256,
        persist_search_uncertainty_v2,
        produce_search_task_admission,
    )
    from polisyos.scientist.orchestration.llm.cycle import persist_execution_plan

    def selected_ref(name: str, kind: str = "scientist.test.current_projection_input"):
        return store.put_json(
            {"fixture": name},
            PutOptions(kind=kind, media_type="application/json"),
            return_selected_profile=True,
        )

    method_fqn = "causal.hte.causal_forest@2.0.0"
    method_params = {"n_estimators": 11}
    method_params_sha256 = _canonical_sha256(method_params)
    method_input_ref = selected_ref("selected-method-input")
    plan_ref = persist_execution_plan(
        store,
        ExecutionPlan(
            plan_id=f"plan-{run_id}",
            run_id=run_id,
            method_dag=[
                MethodDagNode(
                    node_id="selected-hte",
                    method_fqn=method_fqn,
                    method_version="2.0.0",
                    params=method_params,
                )
            ],
        ),
    )
    catalog_ref = persist_method_catalog_snapshot(
        store,
        MethodCatalogSnapshot(
            snapshot_id=f"catalog-{run_id}",
            run_id=run_id,
            entries=[
                MethodCatalogEntry(
                    fqn=method_fqn,
                    namespace="polisyos.methods.causal.hte",
                    name="CausalForest",
                    version="2.0.0",
                    backend="python",
                    execution_backend="python",
                    kind="causal",
                    family="hte",
                    variant="causal_forest",
                    fidelity_tier="standard",
                )
            ],
        ),
    )
    subject_ref = selected_ref("candidate")
    quantity_ref = selected_ref("causal-treatment-effect-contrast")
    contrast_ref = selected_ref("treatment-control-contrast")
    population_ref = selected_ref("selected-evaluation-rows")
    outcome_ref = selected_ref("employment-outcome")
    rule_ref = selected_ref("selected-rule")
    profile_ref = selected_ref("selected-inference-profile")
    procedure_ref = selected_ref("selected-procedure")
    selection_ref = selected_ref("selected-policy-selection")
    stage_payload = {
        "owner_fqn": (
            "polisyos.scientist.nodes.builtins.decide.policy_blueprint_runtime_engine."
            "run_runtime_funnel"
        ),
        "stages": ({"stage_name": "L0", "fidelity_level": 0},),
        "unresolved_bindings": (),
    }
    stage_configuration_sha256 = _canonical_sha256(stage_payload)
    configuration_ref = persist_search_uncertainty_v2(
        store,
        SearchRuntimeStageConfiguration(
            owner_fqn=stage_payload["owner_fqn"],
            stages=stage_payload["stages"],
            unresolved_bindings=stage_payload["unresolved_bindings"],
            configuration_sha256=stage_configuration_sha256,
        ),
    )
    source_graph_ref = persist_search_uncertainty_v2(
        store,
        SearchOwnerSelectedSourceGraph(
            roots=(
                SearchInputDependency(role_path="candidate", ref=subject_ref),
                SearchInputDependency(role_path="execution_plan", ref=plan_ref),
                SearchInputDependency(role_path="stage_configuration", ref=configuration_ref),
                SearchInputDependency(role_path="selected_rule", ref=rule_ref),
                SearchInputDependency(role_path="selected_profile", ref=profile_ref),
                SearchInputDependency(role_path="selected_procedure", ref=procedure_ref),
                SearchInputDependency(role_path="policy_selection", ref=selection_ref),
                SearchInputDependency(role_path="selected_method_input", ref=method_input_ref),
                SearchInputDependency(role_path="quantity", ref=quantity_ref),
                SearchInputDependency(role_path="treatment_contrast", ref=contrast_ref),
                SearchInputDependency(role_path="population", ref=population_ref),
                SearchInputDependency(role_path="outcome", ref=outcome_ref),
                SearchInputDependency(role_path="method_catalog_snapshot", ref=catalog_ref),
            )
        ),
    )
    scope = SearchUncertaintySemanticScope(
        quantity_ref=quantity_ref,
        treatment_contrast_ref=contrast_ref,
        population_ref=population_ref,
        outcome_ref=outcome_ref,
        unit_binding_status="unknown",
        treatment_variable_id="program_access",
        outcome_variable_id="employment",
        control_value=0.0,
        treated_value=1.0,
        requested_target_scope="selected_evaluation_rows",
    )
    owner_context = SearchUncertaintyOwnerTaskContext(
        owner_fqn=stage_payload["owner_fqn"],
        run_id=run_id,
        subject_ref=subject_ref,
        selected_plan_ref=plan_ref,
        selected_configuration_ref=configuration_ref,
        selected_source_graph_ref=source_graph_ref,
        selected_rule_ref=rule_ref,
        selected_profile_ref=profile_ref,
        selected_procedure_ref=procedure_ref,
        selected_selection_ref=selection_ref,
        selected_method_fqn=method_fqn,
        selected_method_abi_version="2.0.0",
        selected_method_abi_digest="b" * 64,
        selected_method_params_sha256=method_params_sha256,
        selected_method_params=method_params,
        selected_method_seed=41,
        selected_inference_profile_id="econml.causal_forest_dml.native_mean@2.0",
        selected_method_input_ref=method_input_ref,
        selected_method_input_content_sha256=method_input_ref.artifact_id.hex,
        request_projection=SearchUncertaintyHTERequestProjection(
            estimand="mean_effect_over_selected_x",
            target_scope="selected_evaluation_rows",
            outcome_variable_id="employment",
            treatment_variable_id="program_access",
            control_value=0.0,
            treated_value=1.0,
            alpha=0.05,
            requested_guarantee="candidate_point",
        ),
        tenant_id="tenant-current-projection",
        semantic_scope=scope,
        selected_stage_config_sha256=stage_configuration_sha256,
        selected_state_input_refs=(
            SearchInputDependency(role_path="method_catalog_snapshot", ref=catalog_ref),
        ),
        status="ready",
    )
    ticket_id = derive_search_uncertainty_ticket_id(run_id, subject_ref)
    state = SearchUncertaintyTicketState(store)
    row = state.initialize(ticket_id)
    _, _, admission_ref, basis_ref = produce_search_task_admission(
        store,
        owner_context,
        ticket_id=ticket_id,
        ticket_generation=row.ticket_generation,
        selected_at=datetime(2026, 10, 21, tzinfo=UTC),
    )
    assert basis_ref is not None
    state.record_task_admission(
        ticket_id=ticket_id,
        expected_generation=row.ticket_generation,
        expected_projection_revision=row.projection_revision,
        admission_ref=admission_ref,
    )
    return state, ticket_id


def test_current_read_resolves_persisted_unassessed_payload_and_refuses_removed_child(tmp_path):
    store = FileSystemCAS(tmp_path / "cas")
    state, ticket_id = _ready_current_projection_packet(store, run_id="run-current-read-resolved")

    # The actual admission producer persists a numeric-free unassessed observation;
    # the owner reloads selected bytes and returns the typed payload with its basis.
    cold = SearchUncertaintyTicketState(store).read_current_snapshot(ticket_id)
    assert cold is not None
    assert cold.status == "available_as_of_task_epoch"
    assert cold.schema_version == "2.0"
    assert cold.resolved_projection is not None
    resolved = cold.resolved_projection
    assert len(resolved.selected_unassessed_observations) == 1
    current = resolved.selected_unassessed_observations[0]
    assert current.observation.state == "unassessed"
    assert current.observation.obligation_id == current.basis.obligation_id
    assert current.basis.selected_method_fqn == "causal.hte.causal_forest@2.0.0"
    assert resolved.current_obligations == ()
    assert resolved.projection.active_unknown_obligation_ids == (current.observation.obligation_id,)
    assert resolved.projection.live_currentness_status == "not_established"
    serialized = cold.model_dump(mode="json", exclude_none=False)
    assert (
        serialized["resolved_projection"]["selected_unassessed_observations"][0]["observation"][
            "state"
        ]
        == "unassessed"
    )

    # Removing the selected current child while leaving the projection markers
    # intact must withhold the complete current read after a cold owner lookup.
    row = state._read_row(ticket_id)
    assert row is not None and row.current_projection_ref is not None
    selected = resolved.projection.model_copy(update={"unassessed_observation_refs": ()})
    removed_projection_ref = persist_search_uncertainty_v2(store, selected)
    state._write_row(
        row.model_copy(
            update={
                "current_projection_ref": removed_projection_ref,
                "projection_ticket_generation": row.ticket_generation,
            }
        )
    )
    refused = SearchUncertaintyTicketState(store).read_current_snapshot(ticket_id)
    assert refused is not None
    assert refused.status == "not_established"
    assert refused.reason_code == "search_projection_mismatch"
    assert refused.projection is None
    assert refused.resolved_projection is None


def test_completed_result_reuse_reconciles_a_new_owner_task_without_new_assessment(tmp_path):
    from polisyos.core.artifacts import load_core_json_artifact

    store = FileSystemCAS(tmp_path / "cas")
    seed_state, seed_ticket_id = _ready_current_projection_packet(store, run_id="reuse-owner-run")
    seed_read = seed_state.read_current_snapshot(seed_ticket_id)
    assert seed_read is not None and seed_read.task_admission is not None
    owner_context = SearchUncertaintyOwnerTaskContext.model_validate(
        load_core_json_artifact(store, seed_read.task_admission.owner_context_ref)
    )
    source = {"gdp_change": 0.0, "metric_units": {"gdp_change": "fixture-unit"}}
    assessment = GDPGrowthObjective(expected_unit="fixture-unit").evaluate(source).score_assessment
    assert assessment is not None and assessment.status is ObjectiveScoreStatus.AVAILABLE
    producer = ProducerStage(
        0,
        FunnelStageResult(
            policy_candidate={},
            objective_value=0.0,
            is_promising=True,
            stage_name="producer-0",
            fidelity_level=0,
            simulation_results=source,
            score_status=assessment.status,
            score_assessment=assessment,
        ),
    )
    runtime = FunnelOrchestrator([producer])
    context = {"store": store, "policy_candidate_ref": owner_context.subject_ref}
    first = runtime.submit(
        {"candidate": "same"}, context, search_uncertainty_owner_context=owner_context
    )
    first_outcome = runtime.advance(first)
    first_row = SearchUncertaintyTicketState(store)._read_row(first.ticket_id)
    second = runtime.submit(
        {"candidate": "same"}, context, search_uncertainty_owner_context=owner_context
    )
    second_outcome = runtime.advance(second)
    cold = SearchUncertaintyTicketState(FileSystemCAS(store.root)).read_current_snapshot(
        second.ticket_id
    )

    assert second.ticket_id != first.ticket_id
    assert second.search_uncertainty_ticket_id == second.ticket_id
    assert second.search_uncertainty_generation == 1
    assert second.search_uncertainty_task_binding_ref is not None
    assert second.search_uncertainty_task_binding_ref != first.search_uncertainty_task_binding_ref
    assert cold is not None and cold.task_admission is not None
    assert cold.ticket_id == second.ticket_id
    assert first_outcome.search_uncertainty_current_read is not None
    assert first_outcome.search_uncertainty_current_read.task_admission is not None
    assert (
        cold.task_admission.owner_context_ref
        == first_outcome.search_uncertainty_current_read.task_admission.owner_context_ref
    )
    assert cold.task_admission.owner_context_ref == seed_read.task_admission.owner_context_ref
    assert second_outcome.search_uncertainty_current_read is not None
    assert second_outcome.search_uncertainty_current_read.ticket_id == second.ticket_id
    assert second_outcome.current_uncertainty_envelope is None
    assert cold.resolved_projection is not None
    assert cold.resolved_projection.current_obligations == ()
    assert all(
        item.observation.state == "unassessed"
        for item in cold.resolved_projection.selected_unassessed_observations
    )
    assert SearchUncertaintyTicketState(store)._read_row(first.ticket_id) == first_row
    assert producer.calls == 1
