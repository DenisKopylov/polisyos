from __future__ import annotations

import pickle
from copy import copy, deepcopy
from dataclasses import asdict, dataclass, replace
from typing import Any, Literal

import pytest
from pydantic import ValidationError

from polisyos.core.artifacts import ArtifactStore, input_ref_from_artifact_ref
from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactManifest, ArtifactRef, InputRef, SchemaInfo
from polisyos.core.artifacts.store import PutOptions
from polisyos.core.contracts.control import WorkflowRunRequest
from polisyos.ir.kernel.units import MoneyUnit
from polisyos.scientist.methods.search.contracts import EvaluationBundle
from polisyos.scientist.methods.search.funnel import level3_medium
from polisyos.scientist.methods.search.objective import (
    MethodMetricObservation,
    MethodMetricPredicateEvidence,
    MethodMetricSourceUnit,
    ObjectiveScoreAdmission,
    ObjectiveScoreAssessment,
    ObjectiveScoreStatus,
    SelectedMethodMetricArtifactRef,
    _unestablished_score_assessment,
    canonical_objective_rule_spec,
    method_metric_observation_input_refs,
    reconcile_objective_score_assessment,
)
from polisyos.scientist.methods.search.strategies.types import Evaluation
from polisyos.scientist.nodes.builtins.decide.policy_runtime_method_metrics import (
    METHOD_METRIC_PROJECTION_VERIFIER_ID,
    METHOD_METRIC_PROJECTION_VERIFIER_REVISION,
    MethodMetricProjectionRefOutcome,
    _admit_method_metric_binding,
    _InvalidProjectionError,
    _MethodMetricSourceTuple,
    _RegisteredMethodMetricBindingContract,
    _source_tuple_sha256,
    _validate_bundle_output_edges,
    _verifier_implementation_sha256,
    admit_funnel_method_metric_objective_score,
    prepare_method_metric_projection_admission,
    prepare_method_metric_projection_work,
    read_completed_admitted_method_metric_projection,
)
from polisyos.scientist.nodes.builtins.decide.policy_runtime_request import (
    _parse_method_metric_source_request,
)
from polisyos.scientist.nodes.builtins.decide.policy_runtime_support import (
    ProductionPolicyEvaluationBackend,
    read_current_admitted_method_metric_projection,
)
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.policy_design.objectives import PolicyEvaluationVector


def _runtime_method_metric_context(
    request_status: str,
    *,
    source_run_id: str | None = None,
    projection_basis: object | None = None,
    selected_source: dict[str, Any] | None = None,
    score_required: bool | None = None,
) -> dict[str, Any]:
    """Build the complete four-key capsule emitted by Runtime's funnel producer."""
    if score_required is None:
        score_required = request_status != "absent"
    identity: dict[str, Any] = {
        "request_status": request_status,
        "requested_source_run_id": source_run_id,
        "resolved_status": "available" if projection_basis is not None else "verification_missing",
        "tenant_id": "tenant-test",
        "cell_id": "cell-test",
    }
    if projection_basis is not None:
        identity["selected_source"] = selected_source or {"run_id": source_run_id}
    else:
        identity["limitations"] = ["completed_method_metric_source_not_established"]
    return {
        "_funnel_method_metric_projection_identity": identity,
        "_funnel_method_metric_projection_basis": projection_basis,
        "_funnel_method_metric_score_required": score_required,
        "_funnel_method_metric_source_request_status": request_status,
    }


@dataclass(frozen=True)
class _ScoreAdmissionEnvelope:
    admission: ObjectiveScoreAdmission


def _contains_object_identity(value: object, target: object) -> bool:
    if value is target:
        return True
    if isinstance(value, dict):
        return any(
            _contains_object_identity(key, target) or _contains_object_identity(item, target)
            for key, item in value.items()
        )
    if isinstance(value, (tuple, list, set, frozenset)):
        return any(_contains_object_identity(item, target) for item in value)
    return False


def test_score_owner_basis_stays_ephemeral_across_strategy_serializers() -> None:
    """History omits owner context; pickle uses only this test's locally built DTO."""
    owner_context = object()
    assessment = _unestablished_score_assessment("serialization_fixture")
    admission = reconcile_objective_score_assessment(
        assessment,
        {},
        owner_context=owner_context,
    )

    assert admission._owner_context is owner_context
    assert not hasattr(admission, "__dict__")
    assert "_policyos_ephemeral_score_owner_context" not in asdict(admission)
    assert "_owner_context" not in asdict(admission)
    strategy_payload = asdict(
        Evaluation(
            candidate_id="candidate-1",
            params={},
            params_normalized=(),
            objectives=[],
            scalar_score=None,
            stage_a_passed=False,
            score_status=ObjectiveScoreStatus.NOT_ESTABLISHED,
            score_assessment=assessment,
            score_admission=admission,
        )
    )
    assert not _contains_object_identity(strategy_payload, owner_context)
    public_payload = EvaluationBundle(
        objective_value=None,
        is_promising=False,
        score_status=ObjectiveScoreStatus.NOT_ESTABLISHED,
        score_assessment=assessment,
        score_admission=admission,
    ).model_dump(mode="python")
    assert not _contains_object_identity(public_payload, owner_context)
    assert admission.to_payload().get("_owner_context") is None
    assert copy(admission)._owner_context is None
    assert deepcopy(admission)._owner_context is None
    assert replace(admission)._owner_context is None
    assert pickle.loads(pickle.dumps(admission))._owner_context is None  # noqa: S301


def test_runtime_backend_copy_and_history_projection_drop_method_metric_basis() -> None:
    """An owner basis never survives copies, dataclass exports, or local pickle round-trips."""
    owner_basis = object()
    selected_candidate = ArtifactRef(
        artifact_id="sha256:" + "a" * 64,
        kind="scientist.policy_design.candidate",
        media_type="application/json",
        manifest_profile_sha256="sha256:" + "b" * 64,
    )
    backend = ProductionPolicyEvaluationBackend().with_method_metric_projection_basis(
        basis=owner_basis,
        candidate_ref=selected_candidate,
    )

    assert backend._policyos_method_metric_projection_basis is owner_basis
    assert not hasattr(backend, "__dict__")
    assert "_policyos_method_metric_projection_basis" not in asdict(backend)
    assert getattr(copy(backend), "_policyos_method_metric_projection_basis", None) is None
    assert getattr(deepcopy(backend), "_policyos_method_metric_projection_basis", None) is None
    assert getattr(replace(backend), "_policyos_method_metric_projection_basis", None) is None
    restored = pickle.loads(pickle.dumps(backend))  # noqa: S301
    assert getattr(restored, "_policyos_method_metric_projection_basis", None) is None


def test_reloaded_completed_method_metric_assessment_is_limited_without_owner_basis() -> None:
    """A serialized method score cannot replay after its private owner basis is gone."""
    rule_spec = canonical_objective_rule_spec(
        {"kind": "completed_method_metric_objectives", "version": "1.0"}
    )
    assessment = ObjectiveScoreAssessment(
        objective_ref="configured-objective-set",
        rule_spec=rule_spec,
        required_input_groups=(("objective-a",),),
        source_field_names=("objective-a", "metric_units.objective-a"),
        source_values=(("objective-a", 1.0),),
        source_sha256="a" * 64,
        value=1.0,
        status=ObjectiveScoreStatus.AVAILABLE,
        source_unit_bindings=(("objective-a", "value"),),
    )
    serialized = ObjectiveScoreAdmission(
        status=ObjectiveScoreStatus.AVAILABLE,
        predicate_status="recomputed",
        reported_assessment=assessment,
        recomputed_assessment=assessment,
        reason="selected_score_source_recomputed",
    ).to_payload()
    restored = ObjectiveScoreAdmission.from_payload(serialized)

    replay = reconcile_objective_score_assessment(
        restored.reported_assessment,
        {},
        prior_admission=restored,
    )

    assert replay.status is ObjectiveScoreStatus.NOT_ESTABLISHED
    assert replay.reason == "completed_method_metric_owner_context_not_retained"
    assert replay.recomputed_assessment is None


@dataclass(frozen=True)
class _Association:
    vector_ref: ArtifactRef
    verifier_revision: str = METHOD_METRIC_PROJECTION_VERIFIER_REVISION
    verifier_implementation_sha256: str = _verifier_implementation_sha256()


@dataclass(frozen=True)
class _Selection:
    selection_kind: Literal["graph_method", "direct_method"]
    job_id: str
    run_id: str
    attempt: int
    method_result_ref: ArtifactRef | None
    simulation_result_ref: ArtifactRef | None
    method_execution_bundle_ref: ArtifactRef | None
    method_metric_binding_set_ref: ArtifactRef | None
    metric_verification_status: Literal["verified", "verification_missing"]
    method_metric_projection: _Association | None


@dataclass(frozen=True)
class _SelectionOwner:
    selection: _Selection | None

    def get_method_execution_selection(
        self,
        *,
        run_id: str,
        tenant_id: str,
        cell_id: str,
    ) -> _Selection | None:
        assert (run_id, tenant_id, cell_id) == ("run-1", "tenant-1", "cell-1")
        return self.selection


@dataclass(frozen=True)
class _ProjectionWork:
    job_id: str
    run_id: str
    attempt: int
    simulation_result_ref: ArtifactRef
    method_execution_bundle_ref: ArtifactRef
    method_metric_binding_set_ref: ArtifactRef
    method_result_ref: ArtifactRef | None = None


@dataclass(frozen=True)
class _ProjectionStoreResolver:
    store: Any

    def resolve_method_metric_projection_store(self, *, work: _ProjectionWork) -> Any:
        assert work.job_id == "job-1"
        return self.store


class _MissingManifestStore:
    def get_manifest(self, _ref: ArtifactRef) -> ArtifactManifest:
        raise FileNotFoundError("selected artifact is absent")


@dataclass(frozen=True)
class _MissingStoreResolver:
    def resolve_method_metric_projection_store(
        self,
        *,
        work: _ProjectionWork,
    ) -> None:
        assert work.job_id == "job-1"
        return None


class _ReadRecorder:
    def __init__(self, store: ArtifactStore) -> None:
        self.store = store
        self.read_blob_ids: list[str] = []

    def get_manifest(self, artifact_id: ArtifactID | ArtifactRef | str) -> ArtifactManifest:
        return self.store.get_manifest(artifact_id)

    def __getattr__(self, name: str) -> Any:
        return getattr(self.store, name)

    def get_bytes(self, artifact_id: ArtifactID | ArtifactRef | str) -> bytes:
        self.read_blob_ids.append(
            str(artifact_id.artifact_id if isinstance(artifact_id, ArtifactRef) else artifact_id)
        )
        return self.store.get_bytes(artifact_id)


def _put(
    cas_store: ArtifactStore,
    *,
    kind: str,
    schema_name: str,
    schema_version: str = "1.0",
    inputs: list[InputRef] | None = None,
) -> ArtifactRef:
    return cas_store.put_json(
        {"schema_version": schema_version},
        PutOptions(
            kind=kind,
            media_type="application/json",
            schema=SchemaInfo(name=schema_name, version=schema_version),
            inputs=inputs or [],
        ),
        return_selected_profile=True,
    )


def _selected(ref: ArtifactRef) -> SelectedMethodMetricArtifactRef:
    return SelectedMethodMetricArtifactRef.model_validate(ref.model_dump(mode="python"))


def _sources(
    cas_store: ArtifactStore, *, include_output_edge: bool = True
) -> dict[str, ArtifactRef]:
    policy = _put(
        cas_store,
        kind="ir.trinity_bundle",
        schema_name="polisyos.ir.TrinityBundle",
    )
    metric_registry = _put(
        cas_store,
        kind="ir.metric_registry",
        schema_name="polisyos.ir.kernel.MetricRegistry",
    )
    units_registry = _put(
        cas_store,
        kind="ir.units_registry",
        schema_name="polisyos.ir.kernel.UnitsRegistry",
    )
    registry_bundle = _put(
        cas_store,
        kind="core.registry_bundle",
        schema_name="polisyos.core.RegistryBundlePayload",
        inputs=[
            input_ref_from_artifact_ref(metric_registry, role="metric_registry"),
            input_ref_from_artifact_ref(units_registry, role="units_registry"),
        ],
    )
    graph = _put(
        cas_store,
        kind="foundry.program_graph",
        schema_name="polisyos.core.ProgramGraph",
        schema_version="0.2.0",
        inputs=[
            input_ref_from_artifact_ref(policy, role="ir"),
            input_ref_from_artifact_ref(registry_bundle, role="registry_bundle"),
        ],
    )
    binding = _put(
        cas_store,
        kind="foundry.method_metric_binding_set",
        schema_name="polisyos.core.MethodMetricBindingSet",
        inputs=[
            input_ref_from_artifact_ref(graph, role="program_graph"),
            input_ref_from_artifact_ref(policy, role="policy"),
            input_ref_from_artifact_ref(registry_bundle, role="registry_bundle"),
            input_ref_from_artifact_ref(metric_registry, role="metric_registry"),
            input_ref_from_artifact_ref(units_registry, role="units_registry"),
        ],
    )
    environment = _put(
        cas_store,
        kind="foundry.environment_manifest",
        schema_name="polisyos.core.EnvironmentManifest",
    )
    output = _put(
        cas_store,
        kind="foundry.method_output",
        schema_name="polisyos.core.MethodOutputPayload",
    )
    plan = _put(
        cas_store,
        kind="foundry.exec_plan",
        schema_name="polisyos.core.ExecPlan",
        schema_version="0.2.0",
        inputs=[
            input_ref_from_artifact_ref(graph, role="program_graph"),
            input_ref_from_artifact_ref(binding, role="method_metric_bindings"),
        ],
    )
    bundle_inputs = [
        input_ref_from_artifact_ref(graph, role="program_graph"),
        input_ref_from_artifact_ref(plan, role="exec_plan"),
        input_ref_from_artifact_ref(binding, role="method_metric_binding_set"),
        input_ref_from_artifact_ref(environment, role="environment_manifest"),
    ]
    if include_output_edge:
        bundle_inputs.append(
            input_ref_from_artifact_ref(
                output,
                role="method_output:invocation-1:0:income-method:income-slot",
            )
        )
    bundle = _put(
        cas_store,
        kind="foundry.method_execution_bundle",
        schema_name="polisyos.core.MethodExecutionBundle",
        inputs=bundle_inputs,
    )
    simulation = _put(
        cas_store,
        kind="foundry.simulation_result",
        schema_name="polisyos.core.SimulationResult",
        schema_version="1.4",
        inputs=[input_ref_from_artifact_ref(bundle, role="method_execution")],
    )
    return {
        "binding": binding,
        "graph": graph,
        "environment": environment,
        "output": output,
        "plan": plan,
        "bundle": bundle,
        "simulation": simulation,
    }


def _observation(source: dict[str, ArtifactRef]) -> MethodMetricObservation:
    selected_output = _selected(source["output"])
    return MethodMetricObservation(
        source_status="observed",
        binding_set_ref=_selected(source["binding"]),
        execution_bundle_ref=_selected(source["bundle"]),
        simulation_result_ref=_selected(source["simulation"]),
        environment_manifest_ref=_selected(source["environment"]),
        output_ref=selected_output,
        binding_id="income-binding",
        objective_id="income-growth",
        metric_id="income",
        occurrence_id="invocation-1:0:income-method",
        invocation_id="invocation-1",
        plan_index=0,
        node_id="income-method",
        method_fqn="policy.methods.income",
        method_version="2.1.0",
        method_abi_digest="b" * 64,
        method_abi_digest_algorithm="blake2b",
        method_build_digest="sha256:" + "f" * 64,
        method_build_digest_scope="class_source_only",
        slot_id="income-slot",
        population_id="households",
        axes=("region", "period"),
        denominator_id="households-at-baseline",
        time_role="post_intervention_period",
        quantity_kind="flow",
        quantity_role="outcome",
        source_unit=MethodMetricSourceUnit(dimension="currency", symbol="USD", scale=1.0),
        target_unit=MoneyUnit(currency="USD"),
        value=42.5,
        law_id="income-unit-law",
        law_version="1.0",
        law_code_digest="c" * 64,
        adapter_id="usd-normalizer",
        adapter_version="1.0",
        adapter_code_digest="d" * 64,
        verifier_id=METHOD_METRIC_PROJECTION_VERIFIER_ID,
        verifier_revision=METHOD_METRIC_PROJECTION_VERIFIER_REVISION,
        verifier_code_digest=_verifier_implementation_sha256(),
        checked_context_sha256="e" * 64,
        predicate_evidence=(
            MethodMetricPredicateEvidence(
                predicate_id="selected_output_profile",
                classification="recomputed",
                evidence_ref=selected_output,
            ),
        ),
    )


def _persist_vector(cas_store: ArtifactStore, source: dict[str, ArtifactRef]) -> ArtifactRef:
    source_tuple = _MethodMetricSourceTuple(
        job_id="job-1",
        run_id="run-1",
        attempt=1,
        method_result_ref=None,
        simulation_result_ref=source["simulation"],
        method_execution_bundle_ref=source["bundle"],
        method_metric_binding_set_ref=source["binding"],
    )
    vector = PolicyEvaluationVector(
        metadata={"source_tuple_sha256": _source_tuple_sha256(source_tuple)},
        method_metric_observations=(_observation(source),),
    )
    return cas_store.put_json(
        vector,
        PutOptions(
            kind="scientist.policy_evaluation_vector",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.scientist.policy_design.PolicyEvaluationVector",
                version="1.2",
            ),
            inputs=[
                input_ref_from_artifact_ref(ref, role=role)
                for role, ref in method_metric_observation_input_refs(
                    vector.method_metric_observations
                )
            ],
        ),
        return_selected_profile=True,
    )


def _selection(source: dict[str, ArtifactRef], vector_ref: ArtifactRef) -> _Selection:
    return _Selection(
        selection_kind="graph_method",
        job_id="job-1",
        run_id="run-1",
        attempt=1,
        method_result_ref=None,
        simulation_result_ref=source["simulation"],
        method_execution_bundle_ref=source["bundle"],
        method_metric_binding_set_ref=source["binding"],
        metric_verification_status="verified",
        method_metric_projection=_Association(vector_ref=vector_ref),
    )


def _projection_work(source: dict[str, ArtifactRef]) -> _ProjectionWork:
    return _ProjectionWork(
        job_id="job-1",
        run_id="run-1",
        attempt=1,
        simulation_result_ref=source["simulation"],
        method_execution_bundle_ref=source["bundle"],
        method_metric_binding_set_ref=source["binding"],
    )


def _read_current_projection(store: ArtifactStore, selection: _Selection | None):
    return read_current_admitted_method_metric_projection(
        store,
        owner=_SelectionOwner(selection),
        run_id="run-1",
        tenant_id="tenant-1",
        cell_id="cell-1",
    )


def test_reader_integrity_reads_only_vector_blob_and_checks_selected_source_chain(
    cas_store,
) -> None:
    """A cold consumer validates the selected chain without reopening output payloads."""
    source = _sources(cas_store)
    vector_ref = _persist_vector(cas_store, source)
    recorder = _ReadRecorder(cas_store)

    result = _read_current_projection(recorder, _selection(source, vector_ref))

    assert result.status == "selected"
    assert len(result.observations) == 1
    assert result.observations[0].value == 42.5
    assert recorder.read_blob_ids == [str(vector_ref.artifact_id)]


def test_reader_integrity_fails_closed_when_bundle_output_edge_is_removed(cas_store) -> None:
    """A vector cannot stand in for the bundle's occurrence-and-slot output edge."""
    source = _sources(cas_store, include_output_edge=False)
    vector_ref = _persist_vector(cas_store, source)

    result = _read_current_projection(cas_store, _selection(source, vector_ref))

    assert result.status == "invalid"
    assert result.limitations == ("execution_bundle_output_edge_missing",)


def test_legacy_vector_and_direct_hte_without_metric_selection_remain_limited(cas_store) -> None:
    """Older fiscal vectors and HTE refs do not create an AD01 method metric selection."""
    source = _sources(cas_store)
    old_vector = cas_store.put_json(
        {
            "candidate_id": "candidate-legacy",
            "metadata": {"policy_runtime_source_measurement": {"source_status": "observed"}},
        },
        PutOptions(
            kind="scientist.policy_evaluation_vector",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.scientist.policy_design.PolicyEvaluationVector",
                version="1.1",
            ),
        ),
        return_selected_profile=True,
    )
    legacy = _read_current_projection(cas_store, _selection(source, old_vector))
    direct_hte_selection = replace(
        _selection(source, old_vector),
        selection_kind="direct_method",
        method_result_ref=source["simulation"],
        metric_verification_status="verification_missing",
    )
    direct_hte = _read_current_projection(cas_store, direct_hte_selection)

    assert legacy.status == "verification_missing"
    assert legacy.limitations == ("legacy_policy_evaluation_vector_1.1_is_limited",)
    assert direct_hte.status == "verification_missing"
    assert direct_hte.limitations == ("direct_method_selection_has_no_graph_metric_projection",)


def test_reader_integrity_rejects_owner_run_mismatch(cas_store) -> None:
    """A sibling run's selected vector cannot satisfy the requested current run."""
    source = _sources(cas_store)
    vector_ref = _persist_vector(cas_store, source)
    wrong_run = replace(_selection(source, vector_ref), run_id="sibling-run")

    result = read_current_admitted_method_metric_projection(
        cas_store,
        owner=_SelectionOwner(wrong_run),
        run_id="run-1",
        tenant_id="tenant-1",
        cell_id="cell-1",
    )

    assert result.status == "invalid"
    assert result.limitations == ("runtime_owner_returned_a_different_run_selection",)


def test_method_metric_vector_rejects_empty_null_and_legacy_alias_carriers() -> None:
    """Absence means no method observation; explicit empty carriers are not absence."""
    assert "method_metric_observations" not in PolicyEvaluationVector().model_dump(mode="json")
    with pytest.raises(
        ValidationError, match="method_metric_observations_must_be_nonempty_or_absent"
    ):
        PolicyEvaluationVector.model_validate({"method_metric_observations": None})
    with pytest.raises(
        ValidationError, match="method_metric_observations_must_be_nonempty_or_absent"
    ):
        PolicyEvaluationVector.model_validate({"method_metric_observations": []})


def test_binding_availability_gate_conditions_all_positive_checks_on_available() -> None:
    """Unavailable rows stay limited; available rows require the complete owner contract."""
    from polisyos.ir.kernel.method_metrics import MethodMetricSourceUnit

    semantics = object()
    law_identity = ("law.ex_ante", "1.0", "a" * 64)
    adapter_identity = ("adapter.unit", "1.0", "b" * 64)
    source_unit = MethodMetricSourceUnit(dimension="value", symbol="amount", scale=1.0)
    currency_unit = MethodMetricSourceUnit(dimension="currency", symbol="USD", scale=1.0)
    expected_input_contract = (
        ("baseline", "baseline", source_unit),
        ("scenario", "scenario", source_unit),
    )

    limited = _admit_method_metric_binding(
        binding_availability="unavailable",
        binding_limitation="registered_method_input_unit_set_mismatch",
        binding_semantics=semantics,
        metric_semantics=semantics,
        binding_law_identity=("unregistered.compiler.claim", "0", "c" * 64),
        binding_adapter_identity=("unregistered.adapter.claim", "0", "d" * 64),
    )
    assert limited.status == "unavailable"
    assert limited.limitation == "registered_method_input_unit_set_mismatch"
    assert limited.law_identity[0] == "unregistered.compiler.claim"

    pending = _admit_method_metric_binding(
        binding_availability="available",
        binding_limitation=None,
        binding_semantics=semantics,
        metric_semantics=semantics,
        binding_law_identity=law_identity,
        binding_adapter_identity=adapter_identity,
    )
    assert pending.status == "requires_positive_validation"

    complete = _RegisteredMethodMetricBindingContract(
        law_identity=law_identity,
        semantics_match=True,
        adapter_identity=adapter_identity,
        input_unit_contract=expected_input_contract,
        actual_input_units=(("baseline", source_unit), ("scenario", source_unit)),
        actual_input_slot_ids=("baseline", "scenario"),
        input_contract_resolved=True,
        output_slot_contract_matches=True,
    )
    admitted = _admit_method_metric_binding(
        binding_availability="available",
        binding_limitation=None,
        binding_semantics=semantics,
        metric_semantics=semantics,
        binding_law_identity=law_identity,
        binding_adapter_identity=adapter_identity,
        positive_contract=complete,
    )
    assert admitted.status == "admitted"

    invalid_positive_contracts = (
        replace(complete, law_identity=None),
        replace(complete, semantics_match=False),
        replace(complete, adapter_identity=("wrong.adapter", "1.0", "e" * 64)),
        replace(complete, input_unit_contract=None),
        replace(
            complete, actual_input_units=(("baseline", source_unit), ("scenario", currency_unit))
        ),
        replace(complete, actual_input_slot_ids=("baseline", "scenario", "extra")),
        replace(complete, output_slot_contract_matches=False),
    )
    for positive_contract in invalid_positive_contracts:
        with pytest.raises(_InvalidProjectionError):
            _admit_method_metric_binding(
                binding_availability="available",
                binding_limitation=None,
                binding_semantics=semantics,
                metric_semantics=semantics,
                binding_law_identity=law_identity,
                binding_adapter_identity=adapter_identity,
                positive_contract=positive_contract,
            )

    with pytest.raises(
        _InvalidProjectionError,
        match="method_metric_binding_semantics_registry_mismatch",
    ):
        _admit_method_metric_binding(
            binding_availability="unavailable",
            binding_limitation="compiler_limitation",
            binding_semantics=semantics,
            metric_semantics=None,
            binding_law_identity=law_identity,
            binding_adapter_identity=adapter_identity,
        )


def test_observed_method_metric_requires_a_selected_environment(cas_store: ArtifactStore) -> None:
    """An output cannot become an observed method metric without its selected environment."""
    observation_payload = _observation(_sources(cas_store)).model_dump(mode="python")
    observation_payload["environment_manifest_ref"] = None

    with pytest.raises(ValidationError, match="observed_method_metric_source_basis_is_incomplete"):
        MethodMetricObservation.model_validate(observation_payload)


def test_present_malformed_metric_carrier_is_invalid_not_a_fiscal_fallback(cas_store) -> None:
    """Malformed v1.2 content cannot fall back to the unrelated government-balance source."""
    source = _sources(cas_store)
    malformed_vector = cas_store.put_json(
        {
            "candidate_id": "candidate-malformed",
            "metadata": {"policy_runtime_source_measurement": {"source_status": "observed"}},
            "method_metric_observations": [{"source_status": "observed"}],
        },
        PutOptions(
            kind="scientist.policy_evaluation_vector",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.scientist.policy_design.PolicyEvaluationVector",
                version="1.2",
            ),
            inputs=[
                input_ref_from_artifact_ref(source["binding"], role="method_metric_binding_set")
            ],
        ),
        return_selected_profile=True,
    )

    result = _read_current_projection(cas_store, _selection(source, malformed_vector))

    assert result.status == "invalid"
    assert result.limitations == ("selected_method_metric_projection_readback_failed",)


def test_refs_only_worker_distinguishes_absent_source_from_malformed_present_bytes(
    cas_store: ArtifactStore,
) -> None:
    """Only absence is limited; supplied but malformed source bytes remain invalid."""
    source = _sources(cas_store)
    work = _projection_work(source)
    source_tuple = _MethodMetricSourceTuple(
        job_id=work.job_id,
        run_id=work.run_id,
        attempt=work.attempt,
        method_result_ref=None,
        simulation_result_ref=work.simulation_result_ref,
        method_execution_bundle_ref=work.method_execution_bundle_ref,
        method_metric_binding_set_ref=work.method_metric_binding_set_ref,
    )

    absent = prepare_method_metric_projection_admission(
        _MissingManifestStore(), source_tuple=source_tuple
    )
    malformed = prepare_method_metric_projection_admission(cas_store, source_tuple=source_tuple)

    assert absent.status == "verification_missing"
    assert absent.admission is None
    assert malformed.status == "invalid"
    assert malformed.admission is None


def test_fixed_worker_resolves_only_server_owned_store_and_returns_no_receipt_when_missing(
    cas_store: ArtifactStore,
) -> None:
    """A descriptor cannot name a CAS root and a missing resolver yields no token."""
    work = _projection_work(_sources(cas_store))

    result = prepare_method_metric_projection_work(
        work=work,
        resolver=_MissingStoreResolver(),
    )

    assert result.status == "verification_missing"
    assert result.admission is None
    assert result.limitations == ("configured_method_metric_projection_store_not_available",)


def test_fixed_worker_uses_configured_store_but_rejects_malformed_source_bytes(
    cas_store: ArtifactStore,
) -> None:
    """The refs-only bridge reaches the configured CAS and never turns malformed bytes into a receipt."""
    work = _projection_work(_sources(cas_store))

    result = prepare_method_metric_projection_work(
        work=work,
        resolver=_ProjectionStoreResolver(cas_store),
    )

    assert result.status == "invalid"
    assert result.admission is None
    assert result.limitations == ("selected_method_metric_artifact_payload_invalid",)


def test_source_tuple_snapshots_mutable_artifact_refs_and_verified_outcome_requires_token(
    cas_store: ArtifactStore,
) -> None:
    """The executor descriptor cannot mutate a staged tuple or forge its seal."""
    source = _sources(cas_store)
    simulation_ref = source["simulation"]
    source_tuple = _MethodMetricSourceTuple(
        job_id="job-1",
        run_id="run-1",
        attempt=1,
        method_result_ref=None,
        simulation_result_ref=simulation_ref,
        method_execution_bundle_ref=source["bundle"],
        method_metric_binding_set_ref=source["binding"],
    )
    original_kind = simulation_ref.kind
    simulation_ref.kind = "forged.kind"

    assert source_tuple.simulation_result_ref.kind == original_kind
    with pytest.raises(
        ValueError, match="verified_method_metric_projection_requires_worker_receipt"
    ):
        MethodMetricProjectionRefOutcome(status="verified", admission=None)


def _exercise_public_execute_method_metric_source(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    artifact_store: ArtifactStore | None = None,
    foundry_port: object | None = None,
    job_id: str = "job-public-execute",
    run_id: str = "run-public-execute",
    attempt: int = 1,
) -> dict[str, Any]:
    """A real execute result yields a candidate observation only through its full CAS chain."""
    import hashlib
    import inspect

    import numpy as np

    from polisyos.core.artifacts import validate_core_model_json_artifact
    from polisyos.core.artifacts.manifest import input_ref_from_artifact_ref
    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.core.canon import CanonSpec
    from polisyos.core.contracts.fabric import DataSnapshot
    from polisyos.core.contracts.foundry import (
        ExecPlan,
        ExecPlanRef,
        ExecuteRequest,
        FoundryExecConfig,
        FoundryExecutionInputBasis,
        FoundryExecutionInputBasisRef,
        FoundryInputBindings,
        FoundryInputBindingsRef,
        LoweredIR,
        LoweredIRRef,
        MethodExecutionBundle,
        MethodMetricBinding,
        MethodMetricBindingSet,
        MethodMetricBindingSetRef,
        ProgramGraph,
        ProgramGraphRef,
        ProgramNode,
        SimulationResult,
        StateSnapshotRef,
    )
    from polisyos.core.registry import build_registry_bundle
    from polisyos.foundry.contracts.state import GlobalState
    from polisyos.foundry.execute.api import execute as execute_foundry
    from polisyos.foundry.execute.executor import put_state_snapshot
    from polisyos.foundry.methods.catalog.policy.evaluation import ExAnteSimulationEstimator
    from polisyos.foundry.methods.registry import MethodRegistry
    from polisyos.ir.governance.policy_spec import PolicySpec
    from polisyos.ir.governance.problem_frame import ObjectiveSpec, ProblemDomain, ProblemFrame
    from polisyos.ir.kernel import (
        DEFAULT_CONSTRAINT_REGISTRY,
        DEFAULT_MECHANISM_REGISTRY,
        DEFAULT_MERGE_RULE_REGISTRY,
        DEFAULT_METRIC_REGISTRY,
        DEFAULT_SELECTOR_FIELD_REGISTRY,
        DEFAULT_SLOT_REGISTRY,
        DEFAULT_UNITS_REGISTRY,
    )
    from polisyos.ir.kernel.method_metrics import (
        METHOD_METRIC_EX_ANTE_MEAN_CHANGE_LAW_ID,
        MethodMetricInputRole,
        MethodMetricSemanticContract,
        MethodMetricSourceUnit,
        registered_method_metric_law_metadata_for,
        registered_method_metric_unit_adapter_metadata,
        resolve_registered_method_metric_unit_adapter,
    )
    from polisyos.ir.kernel.metrics import MetricRegistry, MetricSpec
    from polisyos.ir.kernel.slots import SlotRegistry
    from polisyos.ir.kernel.units import GenericUnit
    from polisyos.ir.model_layer.model_spec import ModelSpec
    from polisyos.ir.model_layer.types import OptimizationDirection
    from polisyos.ir.trinity import TrinityBundle
    from polisyos.scientist.policy_design.schema import (
        PolicyCandidateSchema,
        TargetPopulationSpec,
        persist_policy_candidate_schema,
    )

    store = artifact_store if artifact_store is not None else FileSystemCAS(tmp_path / "cas")
    MethodRegistry.get_instance().register(ExAnteSimulationEstimator, override=True)

    def _put_selected(
        payload: object,
        *,
        kind: str,
        schema_name: str,
        schema_version: str,
        inputs: list[InputRef] | None = None,
    ) -> ArtifactRef:
        return store.put_json(
            payload,
            PutOptions(
                kind=kind,
                media_type="application/json",
                schema=SchemaInfo(name=schema_name, version=schema_version),
                inputs=inputs,
            ),
            canon_spec=CanonSpec(forbid_floats=False),
            return_selected_profile=True,
        )

    baseline = np.asarray([10.0, 20.0, 40.0], dtype=np.float64)
    scenario = np.asarray([11.0, 18.0, 44.0], dtype=np.float64)
    state = GlobalState.empty(n_agents=len(baseline), n_firms=1)
    state = state.replace(
        agents=state.agents.replace(income=baseline, savings=scenario),
    )
    state_ref = StateSnapshotRef.model_validate(
        put_state_snapshot(
            store,
            state=state,
            step=0,
            return_selected_profile=True,
        ).model_dump(mode="python")
    )

    semantics = MethodMetricSemanticContract(
        quantity_kind="value",
        quantity_role="scenario_delta",
        population_id="captured_model_input_rows",
        axes=("n_agents",),
        denominator_id="n_agents",
        time_role="pre_dispatch_state",
        producer_contract_id=METHOD_METRIC_EX_ANTE_MEAN_CHANGE_LAW_ID,
        input_roles=(
            MethodMetricInputRole(role_id="baseline", method_input_slot_id="baseline"),
            MethodMetricInputRole(role_id="scenario", method_input_slot_id="scenario"),
        ),
        output_value_path=("mean_change",),
    )
    method_signature = ExAnteSimulationEstimator.signature
    law_identity = registered_method_metric_law_metadata_for(
        method_signature.fqn,
        method_signature.version,
    )
    assert law_identity is not None
    source_slot = method_signature.get_input_slot("baseline")
    output_slot = method_signature.get_output_slot("result")
    assert source_slot is not None and output_slot is not None
    source_unit = MethodMetricSourceUnit(
        dimension=source_slot.unit.dimension,
        symbol=source_slot.unit.symbol,
        scale=float(source_slot.unit.scale),
    )
    target_unit = GenericUnit(label="value")
    adapter = resolve_registered_method_metric_unit_adapter(
        source_unit,
        target_unit,
        law_id=law_identity[0],
        semantics=semantics,
    )
    adapter_identity = registered_method_metric_unit_adapter_metadata()
    metric_id = "metric_ex_ante_mean_change"
    objective_id = "objective_ex_ante_mean_change"
    metric_registry = MetricRegistry(
        schema_version="1.1",
        metrics={
            **DEFAULT_METRIC_REGISTRY.metrics,
            metric_id: MetricSpec(
                metric_id=metric_id,
                unit_id="value",
                description="Candidate-only model-input mean scenario delta",
                method_semantics=semantics,
            ),
        },
    )
    units_registry = DEFAULT_UNITS_REGISTRY.model_copy(
        update={"units": {**DEFAULT_UNITS_REGISTRY.units, "value": target_unit}},
    )
    slots = dict(DEFAULT_SLOT_REGISTRY.slots)
    slots["baseline"] = slots["agents.income"].model_copy(
        update={"slot_id": "baseline", "state_path": "agents.income"},
    )
    slots["scenario"] = slots["agents.savings"].model_copy(
        update={"slot_id": "scenario", "state_path": "agents.savings"},
    )
    registry = build_registry_bundle(
        store,
        slot_registry=SlotRegistry(slots=slots),
        merge_registry=DEFAULT_MERGE_RULE_REGISTRY,
        mechanism_registry=DEFAULT_MECHANISM_REGISTRY,
        constraint_registry=DEFAULT_CONSTRAINT_REGISTRY,
        selector_field_registry=DEFAULT_SELECTOR_FIELD_REGISTRY,
        metric_registry=metric_registry,
        units_registry=units_registry,
        return_selected_profile=True,
    )

    data_snapshot_ref = _put_selected(
        DataSnapshot(data_ref=state_ref),
        kind=DataSnapshot.ARTIFACT_KIND,
        schema_name=DataSnapshot.ARTIFACT_SCHEMA_NAME,
        schema_version=DataSnapshot.ARTIFACT_SCHEMA_VERSION,
        inputs=[input_ref_from_artifact_ref(state_ref, role="state_snapshot")],
    )
    problem_frame = ProblemFrame(
        problem_id="method_metric_execute_problem",
        domain=ProblemDomain.SOCIAL,
        objectives=[
            ObjectiveSpec(
                objective_id=objective_id,
                metric_id=metric_id,
                direction=OptimizationDirection.MAXIMIZE,
            )
        ],
    )
    policy_spec = PolicySpec(policy_id="method_metric_execute_policy", interventions=[])
    trinity = TrinityBundle(
        problem_frame=problem_frame,
        policy_spec=policy_spec,
        model_spec=ModelSpec(
            model_id="method_metric_execute_model",
            data_snapshot_ref=str(data_snapshot_ref.artifact_id),
            registry_bundle_ref=str(registry.bundle_ref.artifact_id),
        ),
    )
    candidate = PolicyCandidateSchema(
        candidate_id="method_metric_execute_candidate",
        trinity_bundle=trinity,
        target_population=TargetPopulationSpec(
            population_id="captured_model_input_rows",
            description="Rows provided to the Ex-Ante method execution fixture.",
        ),
    )
    candidate_ref = persist_policy_candidate_schema(
        store,
        candidate,
        inputs=[
            input_ref_from_artifact_ref(
                data_snapshot_ref,
                role="world_model_data_snapshot",
            ),
            input_ref_from_artifact_ref(registry.bundle_ref, role="world_model_registry"),
        ],
        return_selected_profile=True,
    )
    trinity_ref = _put_selected(
        trinity,
        kind=TrinityBundle.ARTIFACT_KIND,
        schema_name=TrinityBundle.ARTIFACT_SCHEMA_NAME,
        schema_version=TrinityBundle.ARTIFACT_SCHEMA_VERSION,
        inputs=[input_ref_from_artifact_ref(candidate_ref, role="policy_candidate")],
    )
    lowered_ir = LoweredIR(ir_ref=trinity_ref, mechanisms=[], constraints=[])
    lowered_ir_ref = store.put_json(
        lowered_ir,
        PutOptions(
            kind="foundry.lowered_ir",
            media_type="application/json",
            inputs=[input_ref_from_artifact_ref(trinity_ref, role="ir")],
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    graph = ProgramGraph(
        ir_ref=trinity_ref,
        lowered_ir_ref=LoweredIRRef.model_validate(lowered_ir_ref.model_dump(mode="python")),
        nodes=[
            ProgramNode(
                node_id="ex_ante_node",
                node_kind="method",
                method_fqn=method_signature.fqn,
                method_version=method_signature.version,
                inputs=["baseline", "scenario"],
            )
        ],
        edges=[],
        entrypoints=["ex_ante_node"],
    )
    graph_ref_raw = _put_selected(
        graph,
        kind=ProgramGraph.ARTIFACT_KIND,
        schema_name=ProgramGraph.ARTIFACT_SCHEMA_NAME,
        schema_version=ProgramGraph.ARTIFACT_SCHEMA_VERSION,
        inputs=[
            input_ref_from_artifact_ref(trinity_ref, role="ir"),
            input_ref_from_artifact_ref(lowered_ir_ref, role="lowered_ir"),
            input_ref_from_artifact_ref(registry.bundle_ref, role="registry_bundle"),
        ],
    )
    graph_ref = ProgramGraphRef.model_validate(graph_ref_raw.model_dump(mode="python"))
    binding = MethodMetricBinding(
        binding_id="method_metric_ex_ante_binding",
        objective_id=objective_id,
        metric_id=metric_id,
        node_id="ex_ante_node",
        method_fqn=method_signature.fqn,
        method_version=method_signature.version,
        method_abi_digest=method_signature.abi_digest(),
        method_abi_digest_algorithm="blake2b",
        method_build_digest=(
            "sha256:"
            + hashlib.sha256(
                inspect.getsource(ExAnteSimulationEstimator).encode("utf-8")
            ).hexdigest()
        ),
        method_build_digest_scope="class_source_only",
        output_slot_id="result",
        output_value_path=("mean_change",),
        output_contract_id=output_slot.contract_id,
        output_shape="scalar",
        semantics=semantics,
        source_unit=source_unit,
        target_unit=target_unit,
        law_id=law_identity[0],
        law_version=law_identity[1],
        law_code_digest=law_identity[2],
        adapter_id=adapter.adapter_id,
        adapter_version=adapter.adapter_version,
        adapter_code_digest=adapter.code_digest or adapter_identity[2],
        conversion_operation=adapter.operation,
        conversion_factor_numerator=adapter.factor_numerator,
        conversion_factor_denominator=adapter.factor_denominator,
        availability="available",
    )
    binding_set = MethodMetricBindingSet(
        program_graph_ref=graph_ref,
        policy_ref=trinity_ref,
        registry_bundle_ref=registry.bundle_ref,
        metric_registry_ref=registry.metric_registry,
        units_registry_ref=registry.units_registry,
        bindings=[binding],
    )
    binding_ref = _put_selected(
        binding_set,
        kind=MethodMetricBindingSet.ARTIFACT_KIND,
        schema_name=MethodMetricBindingSet.ARTIFACT_SCHEMA_NAME,
        schema_version=MethodMetricBindingSet.ARTIFACT_SCHEMA_VERSION,
        inputs=[
            input_ref_from_artifact_ref(graph_ref, role="program_graph"),
            input_ref_from_artifact_ref(trinity_ref, role="policy"),
            input_ref_from_artifact_ref(registry.bundle_ref, role="registry_bundle"),
            input_ref_from_artifact_ref(registry.metric_registry, role="metric_registry"),
            input_ref_from_artifact_ref(registry.units_registry, role="units_registry"),
        ],
    )
    plan_raw_ref = _put_selected(
        ExecPlan(
            program_ref=graph_ref,
            order=["ex_ante_node"],
            mode="dev",
            jit=False,
        ),
        kind=ExecPlan.ARTIFACT_KIND,
        schema_name=ExecPlan.ARTIFACT_SCHEMA_NAME,
        schema_version=ExecPlan.ARTIFACT_SCHEMA_VERSION,
        inputs=[
            input_ref_from_artifact_ref(graph_ref, role="program_graph"),
            input_ref_from_artifact_ref(binding_ref, role="method_metric_bindings"),
        ],
    )
    plan_ref = ExecPlanRef.model_validate(plan_raw_ref.model_dump(mode="python"))
    bindings_raw_ref = _put_selected(
        FoundryInputBindings(
            data_snapshot_ref=data_snapshot_ref,
            registry_bundle_ref=registry.bundle_ref,
            rules=[],
            bound_state_snapshot_ref=state_ref,
        ),
        kind=FoundryInputBindings.ARTIFACT_KIND,
        schema_name=FoundryInputBindings.ARTIFACT_SCHEMA_NAME,
        schema_version=FoundryInputBindings.ARTIFACT_SCHEMA_VERSION,
        inputs=[
            input_ref_from_artifact_ref(data_snapshot_ref, role="data_snapshot"),
            input_ref_from_artifact_ref(state_ref, role="bound_state_snapshot"),
            input_ref_from_artifact_ref(registry.bundle_ref, role="registry_bundle"),
        ],
    )
    request = ExecuteRequest(
        exec_plan_ref=plan_ref,
        input_bindings_ref=FoundryInputBindingsRef.model_validate(
            bindings_raw_ref.model_dump(mode="python")
        ),
        registry_bundle_ref=registry.bundle_ref,
        exec_config=FoundryExecConfig(seed=41, mode="dev", capture_env=True),
        return_selected_profile=True,
    )

    if foundry_port is None:
        result = execute_foundry(store, request)
    else:
        execute = getattr(foundry_port, "execute", None)
        if not callable(execute):
            raise TypeError("public_execute_foundry_port_missing_execute")
        result = execute(store, request)
    assert result.ok is True
    assert result.simulation_result_ref is not None
    bundle_ref = next(
        item.ref for item in result.derived_refs if item.role == "method_execution_bundle"
    )
    binding_ref = next(
        item.ref for item in result.derived_refs if item.role == "method_metric_binding_set"
    )
    assert all(
        ref.manifest_profile_sha256 is not None
        for ref in (candidate_ref, result.simulation_result_ref, bundle_ref, binding_ref)
    )
    simulation_manifest = store.get_manifest(result.simulation_result_ref)
    method_execution_edges = [
        edge for edge in simulation_manifest.inputs if edge.role == "method_execution"
    ]
    assert len(method_execution_edges) == 1
    assert method_execution_edges[0].artifact_id == bundle_ref.artifact_id
    assert method_execution_edges[0].manifest_profile_sha256 == bundle_ref.manifest_profile_sha256
    simulation = validate_core_model_json_artifact(
        SimulationResult,
        store,
        result.simulation_result_ref,
    )
    assert simulation.execution_input_basis_ref is not None
    basis = validate_core_model_json_artifact(
        FoundryExecutionInputBasis,
        store,
        simulation.execution_input_basis_ref,
    )
    assert basis.candidate_ref == candidate_ref

    work = _ProjectionWork(
        job_id=job_id,
        run_id=run_id,
        attempt=attempt,
        simulation_result_ref=result.simulation_result_ref,
        method_execution_bundle_ref=bundle_ref,
        method_metric_binding_set_ref=binding_ref,
    )
    outcome = prepare_method_metric_projection_work(
        work=work,
        resolver=_ProjectionStoreResolver(store),
    )
    assert outcome.status == "verified"
    assert outcome.admission is not None
    assert outcome.admission.source_candidate_ref == candidate_ref
    vector = validate_core_model_json_artifact(
        PolicyEvaluationVector,
        store,
        outcome.admission.vector_ref,
    )
    assert len(vector.method_metric_observations) == 1
    observation = vector.method_metric_observations[0]
    assert observation.source_status == "observed"
    assert observation.value == pytest.approx(1.0)
    assert "external_causal_validity_not_established" in observation.limitations
    assert "external_empirical_calibration_not_established" in observation.limitations
    assert "external_legal_permission_not_established" in observation.limitations

    # A structurally consistent compiler-unavailable binding remains a useful
    # limitation row. Its persisted law/adapter identities are not authority and
    # therefore must not cause the consumer to open environment, output, or
    # dispatch-prestate payloads.
    unavailable_binding = binding.model_copy(
        update={
            "law_id": "unregistered.compiler.law",
            "law_version": "0",
            "law_code_digest": "0" * 64,
            "adapter_id": "unregistered.compiler.adapter",
            "adapter_version": "0",
            "adapter_code_digest": "1" * 64,
            "availability": "unavailable",
            "limitation": "registered_method_metric_law_unavailable",
        }
    )
    unavailable_binding_set = binding_set.model_copy(update={"bindings": [unavailable_binding]})
    unavailable_binding_ref = MethodMetricBindingSetRef.model_validate(
        _put_selected(
            unavailable_binding_set,
            kind=MethodMetricBindingSet.ARTIFACT_KIND,
            schema_name=MethodMetricBindingSet.ARTIFACT_SCHEMA_NAME,
            schema_version=MethodMetricBindingSet.ARTIFACT_SCHEMA_VERSION,
            inputs=[
                input_ref_from_artifact_ref(graph_ref, role="program_graph"),
                input_ref_from_artifact_ref(trinity_ref, role="policy"),
                input_ref_from_artifact_ref(registry.bundle_ref, role="registry_bundle"),
                input_ref_from_artifact_ref(registry.metric_registry, role="metric_registry"),
                input_ref_from_artifact_ref(registry.units_registry, role="units_registry"),
            ],
        ).model_dump(mode="python")
    )
    unavailable_plan_ref = ExecPlanRef.model_validate(
        _put_selected(
            ExecPlan(
                program_ref=graph_ref,
                order=["ex_ante_node"],
                mode="dev",
                jit=False,
            ),
            kind=ExecPlan.ARTIFACT_KIND,
            schema_name=ExecPlan.ARTIFACT_SCHEMA_NAME,
            schema_version=ExecPlan.ARTIFACT_SCHEMA_VERSION,
            inputs=[
                input_ref_from_artifact_ref(graph_ref, role="program_graph"),
                input_ref_from_artifact_ref(
                    unavailable_binding_ref,
                    role="method_metric_bindings",
                ),
            ],
        ).model_dump(mode="python")
    )
    current_bundle = validate_core_model_json_artifact(MethodExecutionBundle, store, bundle_ref)
    current_bundle_manifest = store.get_manifest(bundle_ref)
    unavailable_bundle = current_bundle.model_copy(
        update={
            "exec_plan_ref": unavailable_plan_ref,
            "method_metric_binding_set_ref": unavailable_binding_ref,
        }
    )
    unavailable_bundle_inputs = []
    for edge in current_bundle_manifest.inputs:
        if edge.role == "exec_plan":
            unavailable_bundle_inputs.append(
                input_ref_from_artifact_ref(unavailable_plan_ref, role="exec_plan")
            )
        elif edge.role == "method_metric_binding_set":
            unavailable_bundle_inputs.append(
                input_ref_from_artifact_ref(
                    unavailable_binding_ref,
                    role="method_metric_binding_set",
                )
            )
        else:
            unavailable_bundle_inputs.append(edge)
    assert sum(edge.role == "exec_plan" for edge in unavailable_bundle_inputs) == 1
    assert sum(edge.role == "method_metric_binding_set" for edge in unavailable_bundle_inputs) == 1
    unavailable_bundle_ref = _put_selected(
        unavailable_bundle,
        kind=MethodExecutionBundle.ARTIFACT_KIND,
        schema_name=MethodExecutionBundle.ARTIFACT_SCHEMA_NAME,
        schema_version=MethodExecutionBundle.ARTIFACT_SCHEMA_VERSION,
        inputs=unavailable_bundle_inputs,
    )
    assert simulation.execution_input_basis_ref is not None
    current_basis = validate_core_model_json_artifact(
        FoundryExecutionInputBasis,
        store,
        simulation.execution_input_basis_ref,
    )
    unavailable_basis = current_basis.model_copy(
        update={
            "exec_plan_ref": unavailable_plan_ref,
            "request": current_basis.request.model_copy(
                update={"exec_plan_ref": unavailable_plan_ref}
            ),
        }
    )
    current_basis_manifest = store.get_manifest(simulation.execution_input_basis_ref)
    unavailable_basis_inputs = []
    for edge in current_basis_manifest.inputs:
        if edge.role == "exec_plan":
            unavailable_basis_inputs.append(
                input_ref_from_artifact_ref(unavailable_plan_ref, role="exec_plan")
            )
        else:
            unavailable_basis_inputs.append(edge)
    assert sum(edge.role == "exec_plan" for edge in unavailable_basis_inputs) == 1
    unavailable_basis_ref = FoundryExecutionInputBasisRef.model_validate(
        _put_selected(
            unavailable_basis,
            kind=FoundryExecutionInputBasis.ARTIFACT_KIND,
            schema_name=FoundryExecutionInputBasis.ARTIFACT_SCHEMA_NAME,
            schema_version=FoundryExecutionInputBasis.ARTIFACT_SCHEMA_VERSION,
            inputs=unavailable_basis_inputs,
        ).model_dump(mode="python")
    )
    unavailable_simulation = simulation.model_copy(
        update={
            "exec_plan_ref": unavailable_plan_ref,
            "execution_input_basis_ref": unavailable_basis_ref,
        }
    )
    unavailable_simulation_manifest = store.get_manifest(result.simulation_result_ref)
    unavailable_simulation_inputs = []
    for edge in unavailable_simulation_manifest.inputs:
        if edge.role == "exec_plan":
            unavailable_simulation_inputs.append(
                input_ref_from_artifact_ref(unavailable_plan_ref, role="exec_plan")
            )
        elif edge.role == "execution_input_basis":
            unavailable_simulation_inputs.append(
                input_ref_from_artifact_ref(
                    unavailable_basis_ref,
                    role="execution_input_basis",
                )
            )
        elif edge.role == "method_execution":
            unavailable_simulation_inputs.append(
                input_ref_from_artifact_ref(unavailable_bundle_ref, role="method_execution")
            )
        else:
            unavailable_simulation_inputs.append(edge)
    assert sum(edge.role == "exec_plan" for edge in unavailable_simulation_inputs) == 1
    assert sum(edge.role == "execution_input_basis" for edge in unavailable_simulation_inputs) == 1
    assert sum(edge.role == "method_execution" for edge in unavailable_simulation_inputs) == 1
    unavailable_simulation_ref = _put_selected(
        unavailable_simulation,
        kind=SimulationResult.ARTIFACT_KIND,
        schema_name=SimulationResult.ARTIFACT_SCHEMA_NAME,
        schema_version=simulation.schema_version,
        inputs=unavailable_simulation_inputs,
    )

    blocked_payload_edges = [
        edge
        for edge in current_bundle_manifest.inputs
        if edge.role == "environment_manifest"
        or edge.role.startswith(
            (
                "method_output:",
                "method_artifact:",
                "method_prestate:",
                "method_prestate_source:",
                "method_metric_input_capture:",
            )
        )
    ]
    assert any(edge.role == "environment_manifest" for edge in blocked_payload_edges)
    assert any(edge.role.startswith("method_output:") for edge in blocked_payload_edges)
    assert any(edge.role.startswith("method_prestate:") for edge in blocked_payload_edges)
    assert any(
        edge.role.startswith("method_metric_input_capture:") for edge in blocked_payload_edges
    )

    class _ForbiddenPayloadReadTracker:
        def __init__(self, wrapped: object, forbidden_artifact_ids: set[str]) -> None:
            self._wrapped = wrapped
            self._forbidden_artifact_ids = forbidden_artifact_ids
            self.blocked_reads: list[str] = []

        def __getattr__(self, name: str) -> Any:
            return getattr(self._wrapped, name)

        def _check(self, method_name: str, *args: Any, **kwargs: Any) -> Any:
            artifact_ref = args[0] if args else kwargs.get("artifact_id")
            artifact_id = getattr(artifact_ref, "artifact_id", None)
            if artifact_id in self._forbidden_artifact_ids:
                self.blocked_reads.append(artifact_id)
            method = getattr(self._wrapped, method_name)
            return method(*args, **kwargs)

        def open_member_bounded(self, *args: Any, **kwargs: Any) -> Any:
            return self._check("open_member_bounded", *args, **kwargs)

        def open_member(self, *args: Any, **kwargs: Any) -> Any:
            return self._check("open_member", *args, **kwargs)

        def get_bytes(self, *args: Any, **kwargs: Any) -> Any:
            return self._check("get_bytes", *args, **kwargs)

    payload_tracker = _ForbiddenPayloadReadTracker(
        store,
        {edge.artifact_id for edge in blocked_payload_edges},
    )

    def _unexpected_registry_lookup(cls: type[Any]) -> Any:
        pytest.fail("unavailable_method_binding_must_not_load_positive_method_signature")

    with monkeypatch.context() as patch:
        patch.setattr(MethodRegistry, "get_instance", classmethod(_unexpected_registry_lookup))
        unavailable_outcome = prepare_method_metric_projection_admission(
            payload_tracker,
            source_tuple=_MethodMetricSourceTuple(
                job_id="job-public-execute-unavailable",
                run_id="run-public-execute-unavailable",
                attempt=1,
                method_result_ref=None,
                simulation_result_ref=unavailable_simulation_ref,
                method_execution_bundle_ref=unavailable_bundle_ref,
                method_metric_binding_set_ref=unavailable_binding_ref,
            ),
        )
    assert unavailable_outcome.status == "verified"
    assert unavailable_outcome.admission is not None
    assert payload_tracker.blocked_reads == []
    unavailable_vector = validate_core_model_json_artifact(
        PolicyEvaluationVector,
        store,
        unavailable_outcome.admission.vector_ref,
    )
    assert len(unavailable_vector.method_metric_observations) == 1
    unavailable_observation = unavailable_vector.method_metric_observations[0]
    assert unavailable_observation.source_status == "unavailable"
    assert unavailable_observation.value is None
    assert unavailable_observation.output_ref is None
    assert unavailable_observation.input_capture_ref is None
    assert "registered_method_metric_law_unavailable" in unavailable_observation.limitations

    # A v1.0 label cannot self-upgrade even when copied edges happen to resemble
    # the newer contract. Older production bundles remain a bounded limitation.
    original_bundle_manifest = store.get_manifest(bundle_ref)
    legacy_bundle_payload = current_bundle.model_dump(mode="python")
    legacy_bundle_payload["schema_version"] = "1.0"
    legacy_bundle_ref = store.put_json(
        legacy_bundle_payload,
        PutOptions(
            kind=MethodExecutionBundle.ARTIFACT_KIND,
            media_type=MethodExecutionBundle.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=MethodExecutionBundle.ARTIFACT_SCHEMA_NAME,
                version="1.0",
            ),
            inputs=list(original_bundle_manifest.inputs),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    with pytest.raises(
        _InvalidProjectionError,
        match="observed_method_metric_requires_current_prestate_bundle_schema",
    ):
        _validate_bundle_output_edges(store.get_manifest(legacy_bundle_ref), (observation,))
    original_simulation_manifest = store.get_manifest(result.simulation_result_ref)
    legacy_simulation_inputs = [
        edge for edge in original_simulation_manifest.inputs if edge.role != "method_execution"
    ]
    legacy_simulation_inputs.append(
        input_ref_from_artifact_ref(legacy_bundle_ref, role="method_execution")
    )
    legacy_simulation_ref = store.put_json(
        simulation,
        PutOptions(
            kind=SimulationResult.ARTIFACT_KIND,
            media_type=SimulationResult.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=SimulationResult.ARTIFACT_SCHEMA_NAME,
                version=simulation.schema_version,
            ),
            inputs=legacy_simulation_inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    legacy_outcome = prepare_method_metric_projection_work(
        work=_ProjectionWork(
            job_id="job-legacy-bundle",
            run_id="run-legacy-bundle",
            attempt=1,
            simulation_result_ref=legacy_simulation_ref,
            method_execution_bundle_ref=legacy_bundle_ref,
            method_metric_binding_set_ref=binding_ref,
        ),
        resolver=_ProjectionStoreResolver(store),
    )
    assert legacy_outcome.status == "verification_missing"
    assert legacy_outcome.admission is None
    assert legacy_outcome.limitations == (
        "legacy_method_execution_bundle_v1_0_lacks_current_prestate_contract",
    )

    # Exercise the cold completed-source reader and the same owner-basis hook used
    # by L3/L4. The Runtime contract is represented by this narrow test double; the
    # source refs and projection are the actual public-execute worker outputs above.
    from types import SimpleNamespace

    experiment_state_ref = _put_selected(
        {"schema_version": "1.0"},
        kind="scientist.experiment_state",
        schema_name="polisyos.scientist.experiment.ExperimentState",
        schema_version="1.0",
    )
    selection = SimpleNamespace(
        selection_kind="graph_method",
        job_id=work.job_id,
        run_id=work.run_id,
        attempt=work.attempt,
        method_result_ref=None,
        simulation_result_ref=result.simulation_result_ref,
        method_execution_bundle_ref=bundle_ref,
        method_metric_binding_set_ref=binding_ref,
        source_candidate_ref=candidate_ref,
        source_experiment_state_ref=experiment_state_ref,
        metric_verification_status="verified",
        method_metric_projection=SimpleNamespace(
            vector_ref=outcome.admission.vector_ref,
            verifier_revision=outcome.admission.verifier_revision,
            verifier_implementation_sha256=outcome.admission.verifier_implementation_sha256,
        ),
    )
    completed_source = SimpleNamespace(
        source_run_id=work.run_id,
        source_candidate_ref=candidate_ref,
        source_experiment_state_ref=experiment_state_ref,
        selection=selection,
    )

    class _CompletedSourceOwner:
        def resolve_completed_method_metric_selection(
            self,
            *,
            source_run_id: str,
            candidate_ref: ArtifactRef,
            tenant_id: str,
            cell_id: str | None,
        ) -> object:
            assert source_run_id == work.run_id
            assert candidate_ref == candidate_ref_expected
            assert (tenant_id, cell_id) == ("tenant-public-execute", "cell-public-execute")
            return completed_source

    candidate_ref_expected = candidate_ref
    completed_projection = read_completed_admitted_method_metric_projection(
        store,
        owner=_CompletedSourceOwner(),
        source_run_id=work.run_id,
        candidate_ref=candidate_ref,
        tenant_id="tenant-public-execute",
        cell_id="cell-public-execute",
    )
    assert completed_projection.status == "selected"
    assert completed_projection.basis is not None
    score_admission = admit_funnel_method_metric_objective_score(
        {
            **_runtime_method_metric_context(
                "requested",
                source_run_id=work.run_id,
                projection_basis=completed_projection.basis,
            ),
            "policy_candidate_ref": candidate_ref,
        }
    )
    assert score_admission is not None
    assert score_admission.status is ObjectiveScoreStatus.AVAILABLE
    assert score_admission.recomputed_assessment is not None
    assert score_admission.recomputed_assessment.status is ObjectiveScoreStatus.AVAILABLE

    absent_with_admitted_basis = admit_funnel_method_metric_objective_score(
        {
            **_runtime_method_metric_context(
                "absent",
                source_run_id=work.run_id,
                projection_basis=completed_projection.basis,
            ),
            "policy_candidate_ref": candidate_ref,
        }
    )
    assert absent_with_admitted_basis is not None
    assert absent_with_admitted_basis.status is ObjectiveScoreStatus.INVALID

    without_owner = admit_funnel_method_metric_objective_score(
        {
            **_runtime_method_metric_context("requested", source_run_id=work.run_id),
            "policy_candidate_ref": candidate_ref,
        }
    )
    assert without_owner is not None
    assert without_owner.status is ObjectiveScoreStatus.NOT_ESTABLISHED

    bundle = current_bundle
    occurrence = next(item for item in bundle.occurrences if item.node_id == "ex_ante_node")
    prestate_role = f"method_prestate:{occurrence.occurrence_id}"
    original_bundle_manifest = store.get_manifest(bundle_ref)
    assert sum(edge.role == prestate_role for edge in original_bundle_manifest.inputs) == 1
    stripped_bundle_ref = store.put_json(
        bundle,
        PutOptions(
            kind=MethodExecutionBundle.ARTIFACT_KIND,
            media_type=MethodExecutionBundle.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=MethodExecutionBundle.ARTIFACT_SCHEMA_NAME,
                version=MethodExecutionBundle.ARTIFACT_SCHEMA_VERSION,
            ),
            inputs=[edge for edge in original_bundle_manifest.inputs if edge.role != prestate_role],
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    original_simulation_manifest = store.get_manifest(result.simulation_result_ref)
    stripped_simulation_inputs = [
        edge for edge in original_simulation_manifest.inputs if edge.role != "method_execution"
    ]
    assert len(original_simulation_manifest.inputs) - len(stripped_simulation_inputs) == 1
    stripped_simulation_inputs.append(
        input_ref_from_artifact_ref(stripped_bundle_ref, role="method_execution")
    )
    stripped_simulation_ref = store.put_json(
        simulation,
        PutOptions(
            kind=SimulationResult.ARTIFACT_KIND,
            media_type=SimulationResult.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=SimulationResult.ARTIFACT_SCHEMA_NAME,
                version=simulation.schema_version,
            ),
            inputs=stripped_simulation_inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    stripped_outcome = prepare_method_metric_projection_admission(
        store,
        source_tuple=_MethodMetricSourceTuple(
            job_id="job-public-execute-stripped",
            run_id="run-public-execute-stripped",
            attempt=1,
            method_result_ref=None,
            simulation_result_ref=stripped_simulation_ref,
            method_execution_bundle_ref=stripped_bundle_ref,
            method_metric_binding_set_ref=binding_ref,
        ),
    )
    assert stripped_outcome.status in {"invalid", "verification_missing"}
    assert stripped_outcome.admission is None

    return {
        "store": store,
        "execute_result": result,
        "work": work,
        "candidate_ref": candidate_ref,
        "experiment_state_ref": experiment_state_ref,
        "binding_ref": binding_ref,
        "bundle_ref": bundle_ref,
        "projection_admission": outcome.admission,
        "projection": completed_projection,
        "observation": observation,
    }


def test_public_execute_source_is_admitted_and_missing_prestate_edge_is_refused(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _exercise_public_execute_method_metric_source(tmp_path, monkeypatch)


@pytest.mark.parametrize(
    ("params", "expected"),
    [
        pytest.param({}, (None, "absent"), id="omitted"),
        pytest.param(
            {"method_metric_source_run_id": "r"},
            ("r", "requested"),
            id="short-valid-string",
        ),
        pytest.param(
            {"method_metric_source_run_id": "x" * 256},
            ("x" * 256, "requested"),
            id="maximum-valid-string",
        ),
        pytest.param(
            {"method_metric_source_run_id": None},
            (None, "invalid"),
            id="explicit-null",
        ),
        pytest.param(
            {"method_metric_source_run_id": ""},
            (None, "invalid"),
            id="empty-string",
        ),
        pytest.param(
            {"method_metric_source_run_id": " \t\n"},
            (None, "invalid"),
            id="whitespace-string",
        ),
        pytest.param(
            {"method_metric_source_run_id": "x" * 257},
            (None, "invalid"),
            id="overlong-string",
        ),
        pytest.param(
            {"method_metric_source_run_id": True},
            (None, "invalid"),
            id="boolean",
        ),
        pytest.param(
            {"method_metric_source_run_id": 17},
            (None, "invalid"),
            id="integer",
        ),
        pytest.param(
            {"method_metric_source_run_id": 1.25},
            (None, "invalid"),
            id="number",
        ),
        pytest.param(
            {"method_metric_source_run_id": []},
            (None, "invalid"),
            id="empty-list",
        ),
        pytest.param(
            {"method_metric_source_run_id": ["source-run"]},
            (None, "invalid"),
            id="nested-list",
        ),
        pytest.param(
            {"method_metric_source_run_id": {}},
            (None, "invalid"),
            id="empty-object",
        ),
        pytest.param(
            {"method_metric_source_run_id": {"source_run_id": "source-run"}},
            (None, "invalid"),
            id="nested-object",
        ),
    ],
)
def test_method_metric_source_request_preserves_presence_through_workflow_state(
    params: dict[str, Any],
    expected: tuple[str | None, str],
) -> None:
    """The POST DTO and typed workflow state preserve explicit malformed values."""
    request = WorkflowRunRequest(
        data_source={"data_snapshot_ref": "sha256:" + "a" * 64},
        params=params,
    )
    state = ExperimentState(params=request.params)

    assert state.params == params
    assert _parse_method_metric_source_request(state.params) == expected


@pytest.mark.parametrize(
    ("raw_value", "label"),
    [
        (None, "null"),
        ("", "empty"),
        (" \t\n", "whitespace"),
        ("x" * 257, "overlong"),
        (True, "boolean"),
        (17, "integer"),
        (1.25, "number"),
        ([], "empty-list"),
        (["source-run"], "nested-list"),
        ({}, "empty-object"),
        ({"source_run_id": "source-run"}, "nested-object"),
    ],
)
def test_present_invalid_selector_never_reaches_l3_default_score(
    monkeypatch: pytest.MonkeyPatch,
    raw_value: Any,
    label: str,
) -> None:
    """POST-shaped malformed input stays invalid and cannot fall through in L3."""
    request = WorkflowRunRequest(
        data_source={"data_snapshot_ref": "sha256:" + "a" * 64},
        params={"method_metric_source_run_id": raw_value},
    )
    state = ExperimentState(params=request.params)
    _, request_status = _parse_method_metric_source_request(state.params)
    assert request_status == "invalid"

    class _Workflow:
        def run(self, initial_state: dict[str, Any]) -> dict[str, Any]:
            del initial_state
            return {
                "simulation_results": {"gdp_change": 0.5},
                "feedback": {"verdict": "APPROVE"},
            }

    def _forbid_default_score(*args: Any, **kwargs: Any) -> Any:
        pytest.fail(f"invalid selector {label} reached the legacy default scorer")

    monkeypatch.setattr(level3_medium, "_assess_default_search_objective", _forbid_default_score)
    result = level3_medium.Level3MediumFidelity(_Workflow()).evaluate(
        {"candidate_id": "candidate-selector-presence"},
        {
            # The complete owner-emitted family carries the parser's invalid state.
            **_runtime_method_metric_context(request_status),
        },
    )

    assert result.score_status is ObjectiveScoreStatus.INVALID
    assert result.objective_value is None
    assert result.terminal_action == "reject"
    assert result.feedback["completed_method_metric_objective_score"]["status"] == "invalid"


def test_only_true_selector_absence_keeps_l3_legacy_default_route(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A coherent typed absent request preserves the existing default-score route."""
    request = WorkflowRunRequest(
        data_source={"data_snapshot_ref": "sha256:" + "a" * 64},
        params={},
    )
    state = ExperimentState(params=request.params)
    _, request_status = _parse_method_metric_source_request(state.params)
    assert request_status == "absent"
    observed: list[bool] = []

    class _Workflow:
        def run(self, initial_state: dict[str, Any]) -> dict[str, Any]:
            del initial_state
            return {"simulation_results": {}, "feedback": {"verdict": "UNKNOWN"}}

    def _legacy_default_probe(*args: Any, **kwargs: Any) -> Any:
        del args, kwargs
        observed.append(True)
        return type(
            "_DefaultAssessment",
            (),
            {
                "score_assessment": None,
                "score_status": ObjectiveScoreStatus.NOT_ESTABLISHED,
                "objective_value": None,
                "limitations": ("legacy_default_probe",),
            },
        )()

    monkeypatch.setattr(level3_medium, "_assess_default_search_objective", _legacy_default_probe)
    result = level3_medium.Level3MediumFidelity(_Workflow()).evaluate(
        {"candidate_id": "candidate-selector-omitted"},
        _runtime_method_metric_context(request_status),
    )

    legacy_result = level3_medium.Level3MediumFidelity(_Workflow()).evaluate(
        {"candidate_id": "candidate-historical-empty-context"},
        {},
    )

    assert observed == [True, True]
    assert result.score_admission is None
    assert result.score_status is ObjectiveScoreStatus.NOT_ESTABLISHED
    assert legacy_result.score_admission is None


def test_requested_selector_without_completed_owner_never_reaches_l3_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A valid request with a coherent capsule but no admitted owner remains limited."""
    request = WorkflowRunRequest(
        data_source={"data_snapshot_ref": "sha256:" + "a" * 64},
        params={"method_metric_source_run_id": "source-run"},
    )
    state = ExperimentState(params=request.params)
    source_run_id, request_status = _parse_method_metric_source_request(state.params)
    assert source_run_id == "source-run"
    assert request_status == "requested"

    class _Workflow:
        def run(self, initial_state: dict[str, Any]) -> dict[str, Any]:
            del initial_state
            return {"simulation_results": {"gdp_change": 0.5}, "feedback": {"verdict": "APPROVE"}}

    def _forbid_default_score(*args: Any, **kwargs: Any) -> Any:
        del args, kwargs
        pytest.fail("requested selector without owner reached the legacy default scorer")

    monkeypatch.setattr(level3_medium, "_assess_default_search_objective", _forbid_default_score)
    result = level3_medium.Level3MediumFidelity(_Workflow()).evaluate(
        {"candidate_id": "candidate-requested-without-owner"},
        _runtime_method_metric_context(request_status, source_run_id=source_run_id),
    )

    assert result.score_status is ObjectiveScoreStatus.NOT_ESTABLISHED
    assert result.objective_value is None
    assert result.terminal_action == "defer"
    assert result.feedback["completed_method_metric_objective_score"]["status"] == "not_established"


@pytest.mark.parametrize(
    ("context", "expected"),
    [
        pytest.param(
            {
                "_funnel_method_metric_score_required": True,
                "_funnel_method_metric_source_request_status": "absent",
            },
            ObjectiveScoreStatus.INVALID,
            id="required-marker-conflicts-with-absent",
        ),
        pytest.param(
            {"_funnel_method_metric_score_required": True},
            ObjectiveScoreStatus.INVALID,
            id="required-marker-with-missing-status",
        ),
        pytest.param(
            {"_funnel_method_metric_score_required": False},
            ObjectiveScoreStatus.INVALID,
            id="false-marker-with-missing-status",
        ),
        pytest.param(
            {
                "_funnel_method_metric_score_required": False,
                "_funnel_method_metric_source_request_status": None,
            },
            ObjectiveScoreStatus.INVALID,
            id="malformed-status",
        ),
        pytest.param(
            {
                "_funnel_method_metric_score_required": False,
                "_funnel_method_metric_source_request_status": "invalid",
            },
            ObjectiveScoreStatus.INVALID,
            id="invalid-status-outvotes-marker",
        ),
        pytest.param(
            {
                "_funnel_method_metric_score_required": "false",
                "_funnel_method_metric_source_request_status": "absent",
            },
            ObjectiveScoreStatus.INVALID,
            id="malformed-required-marker-cannot-claim-absence",
        ),
        pytest.param(
            {
                "_funnel_method_metric_score_required": False,
                "_funnel_method_metric_source_request_status": "requested",
            },
            ObjectiveScoreStatus.INVALID,
            id="requested-status-conflicts-with-false-marker",
        ),
    ],
)
def test_inconsistent_selector_status_cannot_enable_legacy_fallback(
    context: dict[str, Any],
    expected: ObjectiveScoreStatus,
) -> None:
    """Only coherent absence or the exact pre-protocol empty context can return None."""
    outcome = admit_funnel_method_metric_objective_score(context)
    assert outcome is not None
    assert outcome.status is expected


@pytest.mark.parametrize(
    "missing_key",
    [
        "_funnel_method_metric_source_request_status",
        "_funnel_method_metric_score_required",
        "_funnel_method_metric_projection_identity",
        "_funnel_method_metric_projection_basis",
    ],
)
def test_runtime_metric_capsule_is_atomic_before_legacy_fallback(missing_key: str) -> None:
    """Any partial Runtime-owned family fails closed, including a lost status."""
    context = _runtime_method_metric_context("absent")
    del context[missing_key]

    outcome = admit_funnel_method_metric_objective_score(context)

    assert outcome is not None
    assert outcome.status is ObjectiveScoreStatus.INVALID


@pytest.mark.parametrize(
    ("request_status", "source_run_id"),
    [("invalid", None), ("requested", "source-run"), ("absent", None)],
    ids=["malformed-present", "requested", "explicit-absent"],
)
def test_lost_status_and_required_marker_cannot_open_l3_legacy_fallback(
    monkeypatch: pytest.MonkeyPatch,
    request_status: str,
    source_run_id: str | None,
) -> None:
    """Capsule identity/basis left after status loss cannot become legacy."""

    class _Workflow:
        def run(self, initial_state: dict[str, Any]) -> dict[str, Any]:
            del initial_state
            return {"simulation_results": {}, "feedback": {"verdict": "UNKNOWN"}}

    def _forbid_default_score(*args: Any, **kwargs: Any) -> Any:
        del args, kwargs
        pytest.fail("lost method-metric request status reached the legacy default scorer")

    monkeypatch.setattr(level3_medium, "_assess_default_search_objective", _forbid_default_score)
    context = _runtime_method_metric_context(request_status, source_run_id=source_run_id)
    del context["_funnel_method_metric_source_request_status"]
    del context["_funnel_method_metric_score_required"]
    result = level3_medium.Level3MediumFidelity(_Workflow()).evaluate(
        {"candidate_id": "candidate-lost-method-metric-status"},
        context,
    )

    assert result.score_status is ObjectiveScoreStatus.INVALID
    assert result.objective_value is None
    assert result.terminal_action == "reject"


def test_complete_capsule_erasure_is_the_documented_legacy_residual() -> None:
    """The consumer cannot distinguish total metadata loss from pre-protocol input."""
    context = _runtime_method_metric_context("invalid")
    legacy_visible_context = {
        key: value for key, value in context.items() if not key.startswith("_funnel_method_metric_")
    }

    assert legacy_visible_context == {}
    assert admit_funnel_method_metric_objective_score(legacy_visible_context) is None


def test_absent_status_requires_coherent_runtime_owner_state() -> None:
    """An explicit absent status cannot override contradictory capsule evidence."""
    for contradiction in (
        "requested_status",
        "source_id",
        "selected_source",
        "basis",
        "new_marker",
    ):
        context = _runtime_method_metric_context("absent")
        identity = context["_funnel_method_metric_projection_identity"]
        if contradiction == "requested_status":
            identity["request_status"] = "requested"
        elif contradiction == "source_id":
            identity["requested_source_run_id"] = "unexpected-source"
        elif contradiction == "selected_source":
            identity["selected_source"] = {"run_id": "unexpected-source"}
        elif contradiction == "required":
            context["_funnel_method_metric_score_required"] = True
        elif contradiction == "basis":
            context["_funnel_method_metric_projection_basis"] = object()
        else:
            context["_funnel_method_metric_future_marker"] = True

        outcome = admit_funnel_method_metric_objective_score(context)

        assert outcome is not None, contradiction
        assert outcome.status is ObjectiveScoreStatus.INVALID, contradiction


def test_absent_selector_status_without_required_flag_keeps_legacy_admission() -> None:
    """A complete absent capsule and a true old empty context keep legacy scoring."""
    outcome = admit_funnel_method_metric_objective_score(_runtime_method_metric_context("absent"))
    assert outcome is None
    assert admit_funnel_method_metric_objective_score({}) is None
