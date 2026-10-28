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
from polisyos.scientist.methods.search.contracts import EvaluationBundle
from polisyos.scientist.methods.search.funnel import level3_medium
from polisyos.scientist.methods.search.objective import (
    MethodMetricObservation,
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
    METHOD_METRIC_PROJECTION_VERIFIER_REVISION,
    MethodMetricProjectionRefOutcome,
    _admit_method_metric_binding,
    _BoundedExecutionSourceReader,
    _InvalidProjectionError,
    _is_exact_json_result_container_unit,
    _load_method_metric_model,
    _MethodMetricSourceTuple,
    _ProjectionReadBudget,
    _registered_method_metric_output_slot_contract_matches,
    _RegisteredMethodMetricBindingContract,
    _selected_returned_slot,
    _source_tuple_sha256,
    _UnestablishedProjectionError,
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
    source_candidate_ref: ArtifactRef
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
    expected_job_id: str = "job-1"

    def resolve_method_metric_projection_store(self, *, work: _ProjectionWork) -> Any:
        assert work.job_id == self.expected_job_id
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

    def open_member_bounded(
        self,
        artifact_id: ArtifactRef,
        member: Literal["blob"],
        *,
        max_manifest_bytes: int,
        expected_manifest_sha256: str,
        max_member_bytes: int,
    ) -> Any:
        self.read_blob_ids.append(str(artifact_id.artifact_id))
        return self.store.open_member_bounded(
            artifact_id,
            member,
            max_manifest_bytes=max_manifest_bytes,
            expected_manifest_sha256=expected_manifest_sha256,
            max_member_bytes=max_member_bytes,
        )


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
        schema_name="polisyos.core.artifacts.environment.EnvironmentManifest",
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
    candidate = _put(
        cas_store,
        kind="scientist.policy_design.candidate",
        schema_name="polisyos.scientist.policy_design.PolicyCandidateSchema",
    )
    return {
        "candidate": candidate,
        "binding": binding,
        "graph": graph,
        "environment": environment,
        "output": output,
        "plan": plan,
        "bundle": bundle,
        "simulation": simulation,
    }


def _persist_vector(cas_store: ArtifactStore, source: dict[str, Any]) -> ArtifactRef:
    """Persist a test vector around the actual public execution observation."""
    from polisyos.core.canon import CanonSpec

    work = source["work"]
    source_tuple = _MethodMetricSourceTuple(
        job_id=work.job_id,
        run_id=work.run_id,
        attempt=work.attempt,
        method_result_ref=None,
        simulation_result_ref=source["simulation"],
        method_execution_bundle_ref=source["bundle"],
        method_metric_binding_set_ref=source["binding"],
    )
    observation = source["observation"]
    vector = PolicyEvaluationVector(
        metadata={
            "source_tuple_sha256": _source_tuple_sha256(source_tuple),
            "source_candidate_ref": source["candidate"].model_dump(mode="json"),
        },
        method_metric_observations=(observation,),
    )
    return cas_store.put_json(
        vector,
        PutOptions(
            kind="scientist.policy_evaluation_vector",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.scientist.policy_design.PolicyEvaluationVector",
                version="1.3",
            ),
            inputs=[
                input_ref_from_artifact_ref(ref, role=role)
                for role, ref in method_metric_observation_input_refs(
                    vector.method_metric_observations
                )
            ],
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )


def _persist_malformed_method_metric_value(
    cas_store: ArtifactStore,
    source: dict[str, Any],
) -> ArtifactRef:
    """Change only the persisted value on an otherwise public typed vector."""
    from json import loads

    from polisyos.core.canon import CanonSpec

    valid_ref = _persist_vector(cas_store, source)
    valid_manifest = cas_store.get_manifest(valid_ref)
    valid_payload = loads(cas_store.get_bytes(valid_ref))
    malformed_payload = deepcopy(valid_payload)
    observations = malformed_payload["method_metric_observations"]
    assert len(observations) == 1
    valid_value = observations[0]["value"]
    assert isinstance(valid_value, dict)
    assert valid_value.get("_type") == "float"
    assert isinstance(valid_value.get("repr"), str)
    observations[0]["value"] = "malformed-runtime-metric-value"

    restored_payload = deepcopy(malformed_payload)
    restored_payload["method_metric_observations"][0]["value"] = valid_payload[
        "method_metric_observations"
    ][0]["value"]
    assert restored_payload == valid_payload

    malformed_ref = cas_store.put_json(
        malformed_payload,
        PutOptions(
            kind=valid_manifest.kind,
            media_type=valid_manifest.media_type,
            schema=valid_manifest.artifact_schema,
            producer=valid_manifest.producer,
            env=valid_manifest.env,
            inputs=valid_manifest.inputs,
            canon=valid_manifest.canon,
            governance=valid_manifest.governance,
            tenant_context=valid_manifest.tenant_context,
            same_input_closure=valid_manifest.same_input_closure,
            authority=valid_manifest.authority,
            warnings=valid_manifest.warnings,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    malformed_manifest = cas_store.get_manifest(malformed_ref)
    assert malformed_manifest.kind == valid_manifest.kind
    assert malformed_manifest.media_type == valid_manifest.media_type
    assert malformed_manifest.artifact_schema == valid_manifest.artifact_schema
    assert malformed_manifest.inputs == valid_manifest.inputs
    assert malformed_manifest.producer == valid_manifest.producer
    assert malformed_manifest.env == valid_manifest.env
    assert malformed_manifest.canon == valid_manifest.canon
    assert malformed_manifest.governance == valid_manifest.governance
    assert malformed_manifest.tenant_context == valid_manifest.tenant_context
    assert malformed_manifest.same_input_closure == valid_manifest.same_input_closure
    assert malformed_manifest.authority == valid_manifest.authority
    assert malformed_manifest.warnings == valid_manifest.warnings
    return malformed_ref


def _selection(source: dict[str, Any], vector_ref: ArtifactRef) -> _Selection:
    work = source.get("work") or _projection_work(source)
    return _Selection(
        selection_kind="graph_method",
        job_id=work.job_id,
        run_id=work.run_id,
        attempt=work.attempt,
        source_candidate_ref=source["candidate"],
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
    public_method_metric_source: dict[str, Any],
) -> None:
    """A cold consumer validates the selected chain without reopening output payloads."""
    source = public_method_metric_source
    vector_ref = _persist_vector(cas_store, source)
    recorder = _ReadRecorder(cas_store)

    result = _read_current_projection(recorder, _selection(source, vector_ref))

    assert result.status == "selected"
    assert len(result.observations) == 1
    assert result.observations[0].value == pytest.approx(1.0)
    assert recorder.read_blob_ids == [str(vector_ref.artifact_id)], recorder.read_blob_ids


def test_reader_reselects_after_read_and_withholds_revoked_selection(
    cas_store, public_method_metric_source: dict[str, Any]
) -> None:
    """A current selection revoked while vector bytes are read cannot be emitted."""
    source = public_method_metric_source
    vector_ref = _persist_vector(cas_store, source)
    selection = _selection(source, vector_ref)

    class Owner:
        calls = 0

        def get_method_execution_selection(self, **kwargs):
            self.calls += 1
            return selection if self.calls == 1 else None

    owner = Owner()
    result = read_current_admitted_method_metric_projection(
        cas_store, owner=owner, run_id="run-1", tenant_id="tenant-1", cell_id="cell-1"
    )
    assert result.status == "verification_missing"
    assert result.vector_ref is None and result.observations == ()
    assert result.limitations == ("current_method_execution_selection_changed_during_read",)
    assert owner.calls == 2


def test_reader_integrity_fails_closed_when_bundle_output_edge_is_removed(
    cas_store,
    public_method_metric_source: dict[str, Any],
) -> None:
    """A vector cannot stand in for the bundle's occurrence-and-slot output edge."""
    source = _without_selected_output_edge(cas_store, public_method_metric_source)
    vector_ref = _persist_vector(cas_store, source)

    result = _read_current_projection(cas_store, _selection(source, vector_ref))

    assert result.status == "invalid", result
    assert result.limitations == (
        "selected_manifest_requires_one_method_output:"
        "graph-invocation.000001:0:ex_ante_node:result_edge",
    ), result


def test_legacy_vector_and_direct_hte_without_metric_selection_remain_limited(
    cas_store,
    public_method_metric_source: dict[str, Any],
) -> None:
    """Older fiscal vectors and HTE refs do not create an AD01 method metric selection."""
    source = public_method_metric_source
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


def test_reader_integrity_rejects_owner_run_mismatch(
    cas_store,
    public_method_metric_source: dict[str, Any],
) -> None:
    """A sibling run's selected vector cannot satisfy the requested current run."""
    source = public_method_metric_source
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
    source_unit = MethodMetricSourceUnit(dimension="value", symbol="amount", scale=1)
    actual_source_unit = MethodMetricSourceUnit(
        dimension="value",
        symbol="amount",
        scale=1.0,
    )
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
        actual_input_units=(
            ("baseline", actual_source_unit),
            ("scenario", actual_source_unit),
        ),
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
            complete,
            actual_input_units=(
                ("baseline", actual_source_unit),
                ("scenario", currency_unit),
            ),
        ),
        replace(
            complete,
            actual_input_units=(
                ("baseline", actual_source_unit),
                (
                    "scenario",
                    MethodMetricSourceUnit(
                        dimension="value",
                        symbol="amount",
                        scale=1.0000000001,
                    ),
                ),
            ),
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


def test_observed_method_metric_requires_a_selected_environment(
    public_method_metric_source: dict[str, Any],
) -> None:
    """An output cannot become an observed method metric without its selected environment."""
    observation_payload = public_method_metric_source["observation"].model_dump(mode="python")
    observation_payload["environment_manifest_ref"] = None

    with pytest.raises(ValidationError, match="observed_method_metric_source_basis_is_incomplete"):
        MethodMetricObservation.model_validate(observation_payload)


def test_present_malformed_metric_carrier_is_invalid_not_a_fiscal_fallback(
    cas_store: ArtifactStore,
    public_method_metric_source: dict[str, Any],
) -> None:
    """A malformed current observation cannot become absent or open a fiscal fallback."""
    source = public_method_metric_source
    output_bytes = cas_store.get_bytes(source["output"])
    malformed_vector = _persist_malformed_method_metric_value(cas_store, source)
    malformed_manifest = cas_store.get_manifest(malformed_vector)

    assert malformed_manifest.artifact_schema == SchemaInfo(
        name="polisyos.scientist.policy_design.PolicyEvaluationVector",
        version="1.3",
    )
    assert cas_store.get_bytes(source["output"]) == output_bytes

    result = _read_current_projection(cas_store, _selection(source, malformed_vector))

    assert result.status == "invalid"
    assert result.limitations == ("selected_method_metric_artifact_payload_invalid",)


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
    public_method_metric_source: dict[str, Any],
) -> None:
    """A valid public source chain reaches and refuses only its malformed selected output."""
    source = _with_malformed_selected_output(cas_store, public_method_metric_source)
    recorder = _ReadRecorder(cas_store)

    result = prepare_method_metric_projection_work(
        work=source["work"],
        resolver=_ProjectionStoreResolver(recorder),
    )

    assert result.status == "invalid"
    assert result.admission is None
    assert result.limitations == ("selected_method_metric_artifact_payload_invalid",)
    assert str(source["malformed_output_ref"].artifact_id) in recorder.read_blob_ids


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
    execution_data_snapshot_ref: ArtifactRef | None = None,
    candidate_data_snapshot_edge_ref: ArtifactRef | None = None,
    expected_executed_mean: float | None = None,
    execution_seed: int = 41,
    job_id: str = "job-public-execute",
    run_id: str = "run-public-execute",
    attempt: int = 1,
    capture_only: bool = False,
    prepare_only: bool = False,
    canonical_compile: bool = False,
    request: pytest.FixtureRequest | None = None,
    scenario_values: tuple[float, ...] | None = None,
    baseline_values: tuple[float, ...] | None = None,
) -> dict[str, Any]:
    """Exercise compiler-backed capture or explicit scalar projection through Foundry."""
    import hashlib
    import inspect
    import logging

    import numpy as np

    from polisyos.common.async_tools import run_coro_sync
    from polisyos.core.artifacts import validate_core_model_json_artifact
    from polisyos.core.artifacts.async_store import ensure_async_artifact_store
    from polisyos.core.artifacts.manifest import input_ref_from_artifact_ref
    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.core.canon import CanonSpec
    from polisyos.core.contracts.execution_plan import ExecutionPlan, MethodDagNode
    from polisyos.core.contracts.fabric import DataSnapshot
    from polisyos.core.contracts.foundry import (
        ExecPlan,
        ExecPlanRef,
        ExecuteRequest,
        FoundryExecConfig,
        FoundryExecutionInputBasis,
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
    )
    from polisyos.core.registry import build_registry_bundle
    from polisyos.core.run.context import RunContext
    from polisyos.fabric.data_plane.orchestrator import _build_snapshot_from_evidence_async
    from polisyos.fabric.evidence.evidence import build_evidence_bundle, persist_evidence_bundle
    from polisyos.foundry.data_plane import build_input_bindings
    from polisyos.foundry.execute.api import execute as execute_foundry
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
        registered_method_metric_semantics_match,
        registered_method_metric_unit_adapter_metadata,
        resolve_registered_method_metric_unit_adapter,
    )
    from polisyos.ir.kernel.metrics import MetricRegistry, MetricSpec
    from polisyos.ir.kernel.slots import (
        SlotKind,
        SlotRegistry,
        SlotScope,
        SlotSpec,
        SlotValueType,
    )
    from polisyos.ir.kernel.units import GenericUnit
    from polisyos.ir.model_layer.model_spec import ModelSpec
    from polisyos.ir.model_layer.types import OptimizationDirection
    from polisyos.ir.trinity import TrinityBundle
    from polisyos.scientist.nodes.builtins.compile.compile_foundry import CompileFoundryNode
    from polisyos.scientist.nodes.builtins.planning.build_execution_plan import (
        BuildExecutionPlanNode,
    )
    from polisyos.scientist.nodes.builtins.state_keys import (
        ARTIFACT_EXEC_PLAN_REF,
        ARTIFACT_METHOD_METRIC_BINDING_SET_REF,
        ARTIFACT_PROGRAM_GRAPH_REF,
        INPUT_REGISTRY_BUNDLE_REF,
        INPUT_TRINITY_BUNDLE_REF,
    )
    from polisyos.scientist.orchestration.engine.context import ExecutionContext
    from polisyos.scientist.orchestration.engine.state import ExperimentState
    from polisyos.scientist.policy_design.schema import (
        PolicyCandidateSchema,
        TargetPopulationSpec,
        persist_policy_candidate_schema,
    )

    store = artifact_store if artifact_store is not None else FileSystemCAS(tmp_path / "cas")
    method_registry = MethodRegistry.get_instance()
    method_registry.register(ExAnteSimulationEstimator, override=True)

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

    baseline = np.asarray(
        baseline_values if baseline_values is not None else [10.0, 20.0, 40.0],
        dtype=np.float64,
    )
    scenario = np.asarray(
        scenario_values if scenario_values is not None else [11.0, 18.0, 44.0],
        dtype=np.float64,
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
    method_execution_outputs: list[dict[str, Any]] = []
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
    slots["scenario"] = SlotSpec(
        slot_id="scenario",
        scope=SlotScope.PER_AGENT,
        value_type=SlotValueType.DECIMAL,
        unit=DEFAULT_SLOT_REGISTRY.slots["agents.income"].unit,
        kind=SlotKind.STOCK,
        merge_rule=DEFAULT_SLOT_REGISTRY.slots["agents.income"].merge_rule,
        state_path="agents.savings",
        description="Agent savings stock used as the selected scenario input.",
        reset_rule="carry",
    )
    assert slots["scenario"].scope is SlotScope.PER_AGENT
    assert slots["scenario"].value_type is SlotValueType.DECIMAL
    assert slots["scenario"].unit is not None
    assert slots["scenario"].unit.unit_id == "usd"
    assert slots["scenario"].kind is SlotKind.STOCK
    assert slots["scenario"].state_path == "agents.savings"
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

    source_payload_ref = _put_selected(
        {"baseline": baseline.tolist(), "scenario": scenario.tolist()},
        kind="test.method_metric_observational_input",
        schema_name="polisyos.tests.MethodMetricObservationalInput",
        schema_version="1.0",
    )
    evidence_ref = persist_evidence_bundle(
        store,
        build_evidence_bundle(
            sources=[source_payload_ref],
            notes=["network-free selected input for public Foundry execution"],
        ),
        return_selected_profile=True,
    )
    data_snapshot_ref = run_coro_sync(
        _build_snapshot_from_evidence_async(
            store=ensure_async_artifact_store(store),
            evidence_ref=evidence_ref,
            datasets_fetched=1,
            source="method_metric_owner_fixture",
        )
    )
    assert data_snapshot_ref is not None
    snapshot = validate_core_model_json_artifact(DataSnapshot, store, data_snapshot_ref)
    assert snapshot.data_ref.artifact_id == source_payload_ref.artifact_id
    assert snapshot.data_ref.manifest_profile_sha256 == source_payload_ref.manifest_profile_sha256
    snapshot_manifest = store.get_manifest(data_snapshot_ref)
    assert any(
        edge.role == "data_ref"
        and edge.artifact_id == source_payload_ref.artifact_id
        and edge.manifest_profile_sha256 == source_payload_ref.manifest_profile_sha256
        for edge in snapshot_manifest.inputs
    )
    input_bindings = build_input_bindings(
        store,
        data_snapshot_ref=execution_data_snapshot_ref or data_snapshot_ref,
        registry_bundle_ref=registry.bundle_ref,
        return_selected_profile=True,
    )
    assert input_bindings.input_bindings_ref.manifest_profile_sha256 is not None
    assert input_bindings.bound_state_snapshot_ref.manifest_profile_sha256 is not None
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
                candidate_data_snapshot_edge_ref or data_snapshot_ref,
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
    if prepare_only:
        # Inputs only: no Foundry execute, owner selection, or fabricated finalization.
        return {
            "store": store,
            "data_snapshot_ref": data_snapshot_ref,
            "registry_ref": registry.bundle_ref,
            "trinity_ref": trinity_ref,
            "candidate_ref": candidate_ref,
            "candidate": candidate,
            "method_fqn": method_signature.fqn,
            "method_version": method_signature.version,
            "method_backend": method_signature.execution_backend.value,
        }
    if capture_only:
        unseen_signature = replace(
            method_signature,
            name="runtime_unseen_probe",
            namespace="tests.capture_only",
            version="1.0.0",
            family="tests.capture_only",
            variant="runtime_unseen_probe",
        )

        def _capture_unseen_method_output(state, params):
            computed = ExAnteSimulationEstimator.pure_step(state, params)
            method_execution_outputs.append(computed)
            return computed

        unseen_method = type(
            "_UnseenRuntimeCaptureMethod",
            (ExAnteSimulationEstimator,),
            {
                "signature": unseen_signature,
                "pure_step": staticmethod(_capture_unseen_method_output),
            },
        )
        if request is None:
            raise AssertionError("capture_only_method_requires_test_cleanup_fixture")
        if method_registry.get_signature(unseen_signature.fqn) is not None:
            raise AssertionError("capture_only_method_fqn_already_registered")
        request.addfinalizer(lambda: method_registry.unregister(unseen_signature.fqn))
        method_registry.register(unseen_method, override=False)
        method_signature = unseen_signature

        class _LocalFoundryPort:
            def compile(self, artifact_store, request):
                from polisyos.foundry.compile.api import compile

                return compile(artifact_store, request)

            def execute(self, artifact_store, request):
                return execute_foundry(artifact_store, request)

        active_foundry = foundry_port or _LocalFoundryPort()
        compile_run_id = f"{run_id}-method-compile"
        plan = ExecutionPlan(
            plan_id=f"{compile_run_id}-selected-plan",
            run_id=compile_run_id,
            method_dag=[
                MethodDagNode(
                    node_id="ex_ante_node",
                    method_fqn=method_signature.fqn,
                    method_version=method_signature.version,
                    backend=method_signature.execution_backend.value,
                    params={"poverty_line": None},
                    reads_slots=["baseline", "scenario"],
                    writes_slots=["result"],
                )
            ],
        )
        compile_run = RunContext.start(
            store=store,
            registry_bundle=registry.bundle_ref,
            run_id=compile_run_id,
            run_dir=tmp_path / f"{compile_run_id}-run",
        )
        compile_context = ExecutionContext(
            store=store,
            run=compile_run,
            logger=logging.getLogger("tests.capture_only_compiler_bridge"),
            foundry=active_foundry,
        )
        initial_state = ExperimentState(
            run_id=compile_run_id,
            inputs={
                INPUT_TRINITY_BUNDLE_REF: trinity_ref,
                INPUT_REGISTRY_BUNDLE_REF: registry.bundle_ref,
            },
            params={"execution_plan": plan.model_dump(mode="json")},
        )
        built = BuildExecutionPlanNode().execute(compile_context, initial_state)
        assert built.status == "ok", built.error
        selected_method_plan_ref = built.state.execution_plan_ref
        assert selected_method_plan_ref is not None
        compiled = CompileFoundryNode().execute(compile_context, built.state)
        assert compiled.status == "ok", compiled.error
        compiled_graph_ref = compiled.state.artifacts_index[ARTIFACT_PROGRAM_GRAPH_REF]
        compiled_exec_plan_ref = compiled.state.artifacts_index[ARTIFACT_EXEC_PLAN_REF]
        compiled_binding_ref = compiled.state.artifacts_index[
            ARTIFACT_METHOD_METRIC_BINDING_SET_REF
        ]
        compiled_binding_set = validate_core_model_json_artifact(
            MethodMetricBindingSet, store, compiled_binding_ref
        )
        assert compiled_binding_set.bindings == []
        assert compiled_binding_set.program_graph_ref == compiled_graph_ref
        source_plan_edges = [
            edge
            for edge in store.get_manifest(compiled_graph_ref).inputs
            if edge.role == "execution_plan_source"
        ]
        assert len(source_plan_edges) == 1
        assert source_plan_edges[0].artifact_id == selected_method_plan_ref.artifact_id
        assert (
            source_plan_edges[0].manifest_profile_sha256
            == selected_method_plan_ref.manifest_profile_sha256
        )
        binding_edges = [
            edge
            for edge in store.get_manifest(compiled_exec_plan_ref).inputs
            if edge.role == "method_metric_bindings"
        ]
        assert len(binding_edges) == 1
        assert binding_edges[0].artifact_id == compiled_binding_ref.artifact_id
        assert (
            binding_edges[0].manifest_profile_sha256 == compiled_binding_ref.manifest_profile_sha256
        )
        request = ExecuteRequest(
            exec_plan_ref=compiled_exec_plan_ref,
            input_bindings_ref=input_bindings.input_bindings_ref,
            registry_bundle_ref=registry.bundle_ref,
            exec_config=FoundryExecConfig(seed=execution_seed, mode="dev", capture_env=True),
            return_selected_profile=True,
        )
        execute = getattr(active_foundry, "execute", None)
        if not callable(execute):
            raise TypeError("public_execute_foundry_port_missing_execute")
        result = execute(store, request)
        assert result.ok is True
        assert result.schema_version == "1.1"
        assert result.method_execution_bundle_ref is not None
        assert result.simulation_result_ref is not None
        bundle_ref = result.method_execution_bundle_ref
        bundle = validate_core_model_json_artifact(MethodExecutionBundle, store, bundle_ref)
        occurrence = next(item for item in bundle.occurrences if item.node_id == "ex_ante_node")
        assert occurrence.method_fqn == method_signature.fqn
        assert occurrence.method_fqn == "tests.capture_only.runtime_unseen_probe@1.0.0"
        assert occurrence.method_version == "1.0.0"
        assert occurrence.dispatch is not None and occurrence.dispatch.outcome == "succeeded"
        assert occurrence.output_slots == []
        returned_result = next(
            item for item in occurrence.returned_slots if item.slot_id == "result"
        )
        assert returned_result.returned == "returned"
        assert returned_result.runtime_type == "builtins.dict"
        assert len(method_execution_outputs) == 1
        computed_result = method_execution_outputs[0]["result"]
        assert computed_result["mean_change"] == pytest.approx(float(np.mean(scenario - baseline)))
        assert computed_result["n_agents"] == len(baseline)
        derived_binding_refs = [
            item.ref for item in result.derived_refs if item.role == "method_metric_binding_set"
        ]
        assert derived_binding_refs == [compiled_binding_ref]
        return {
            "store": store,
            "execute_result": result,
            "candidate_ref": candidate_ref,
            "experiment_state_ref": None,
            "binding_ref": compiled_binding_ref,
            "bundle_ref": bundle_ref,
            "projection_admission": None,
            "projection": None,
            "observation": None,
            "compiled_program_graph_ref": compiled_graph_ref,
            "compiled_exec_plan_ref": compiled_exec_plan_ref,
            "selected_method_plan_ref": selected_method_plan_ref,
            "method_fqn": method_signature.fqn,
            "computed_method_outputs": method_execution_outputs.copy(),
        }
    if canonical_compile:
        from polisyos.core.contracts.foundry import CompileRequest, MethodMetricBindingRequest
        from polisyos.foundry.compile import compile as compile_actual
        from polisyos.scientist.orchestration.llm.cycle import persist_candidate_execution_plan

        selected_plan = ExecutionPlan(
            plan_id=f"{run_id}-comparison-method-plan",
            run_id=run_id,
            method_dag=[
                MethodDagNode(
                    node_id="ex_ante_node",
                    method_fqn=method_signature.fqn,
                    method_version=method_signature.version,
                    backend=method_signature.execution_backend.value,
                    params={"poverty_line": None},
                    reads_slots=["baseline", "scenario"],
                    writes_slots=["result"],
                )
            ],
        )
        selected_plan_ref, trinity_ref = persist_candidate_execution_plan(
            store, selected_plan, trinity_ref
        )
        compiled = compile_actual(
            store,
            CompileRequest(
                schema_version="1.2",
                policy_ref=trinity_ref,
                registry_bundle_ref=registry.bundle_ref,
                method_execution_plan_ref=selected_plan_ref,
                method_metric_bindings=[
                    MethodMetricBindingRequest(
                        objective_id=objective_id, node_id="ex_ante_node", output_slot_id="result"
                    )
                ],
                return_selected_profile=True,
            ),
        )
        assert compiled.ok is True, compiled.notes
        compiled_refs = {item.role: item.ref for item in compiled.derived_refs}
        graph_ref = ProgramGraphRef.model_validate(
            compiled_refs["program_graph"].model_dump(mode="python")
        )
        graph = validate_core_model_json_artifact(ProgramGraph, store, graph_ref)
        compiled_plan = validate_core_model_json_artifact(ExecPlan, store, compiled.exec_plan_ref)
        compiled_bindings = validate_core_model_json_artifact(
            MethodMetricBindingSet, store, compiled_refs["method_metric_binding_set"]
        )
        assert len(compiled_bindings.bindings) == 1
    else:
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
    assert _registered_method_metric_output_slot_contract_matches(
        binding=binding,
        slot=output_slot,
        registered_law_identity=law_identity,
        registered_semantics_match=True,
    )
    if canonical_compile:
        binding = compiled_bindings.bindings[0]
    actual_method_output = ExAnteSimulationEstimator.pure_step(
        {"baseline": baseline, "scenario": scenario},
        {"poverty_line": None},
    )["result"]

    def _numeric_mapping_paths(value: object, prefix: tuple[str, ...] = ()) -> set[tuple[str, ...]]:
        if isinstance(value, dict):
            return {
                path
                for key, child in value.items()
                for path in _numeric_mapping_paths(child, (*prefix, str(key)))
            }
        if isinstance(value, bool):
            return set()
        if isinstance(value, (int, float, np.integer, np.floating)):
            return {prefix} if prefix else set()
        return set()

    actual_numeric_paths = _numeric_mapping_paths(actual_method_output)
    assert tuple(binding.output_value_path) in actual_numeric_paths
    sibling_numeric_paths = actual_numeric_paths - {tuple(binding.output_value_path)}
    assert sibling_numeric_paths
    for sibling_path in sibling_numeric_paths:
        sibling_semantics = binding.semantics.model_copy(update={"output_value_path": sibling_path})
        assert not registered_method_metric_semantics_match(
            binding.law_id,
            sibling_semantics,
        )

    if canonical_compile:
        binding_set = compiled_bindings
        binding_ref = compiled_refs["method_metric_binding_set"]
        plan_ref = compiled.exec_plan_ref
        assert plan_ref is not None
    else:
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
    request = ExecuteRequest(
        exec_plan_ref=plan_ref,
        input_bindings_ref=input_bindings.input_bindings_ref,
        registry_bundle_ref=registry.bundle_ref,
        exec_config=FoundryExecConfig(seed=execution_seed, mode="dev", capture_env=True),
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
    assert result.schema_version == "1.1"
    assert result.method_execution_bundle_ref is not None
    assert result.simulation_result_ref is not None
    bundle_ref = next(
        item.ref for item in result.derived_refs if item.role == "method_execution_bundle"
    )
    assert result.method_execution_bundle_ref == bundle_ref
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
        resolver=_ProjectionStoreResolver(store, expected_job_id=work.job_id),
    )
    assert outcome.status == "verified", outcome.limitations
    assert outcome.admission is not None
    assert outcome.admission.source_candidate_ref == candidate_ref
    vector = validate_core_model_json_artifact(
        PolicyEvaluationVector,
        store,
        outcome.admission.vector_ref,
    )
    assert len(vector.method_metric_observations) == 1
    observation = vector.method_metric_observations[0]
    captured_bundle = validate_core_model_json_artifact(MethodExecutionBundle, store, bundle_ref)
    captured_occurrence = next(
        item for item in captured_bundle.occurrences if item.node_id == "ex_ante_node"
    )
    # Derive the expected scalar independently from the actual selected dispatch
    # inputs, including deliberate source-snapshot swaps. Requested arrays and
    # a caller-supplied expected number cannot establish the producer arithmetic.
    from fractions import Fraction

    from polisyos.foundry.execute import read_state_snapshot_inputs_bounded

    dispatch = captured_occurrence.dispatch
    assert dispatch is not None and dispatch.input_state_ref is not None
    captured_inputs = read_state_snapshot_inputs_bounded(
        store,
        snapshot_ref=dispatch.input_state_ref,
        slot_ids=("baseline", "scenario"),
        max_manifest_bytes=16 * 1024 * 1024,
        max_snapshot_payload_bytes=16 * 1024 * 1024,
        max_state_blob_bytes=16 * 1024 * 1024,
        max_entries=32,
        max_elements=1_000_000,
    )
    captured_arrays = dict(captured_inputs.arrays)
    captured_baseline = captured_arrays["baseline"].tolist()
    captured_scenario = captured_arrays["scenario"].tolist()
    assert captured_baseline and len(captured_baseline) == len(captured_scenario)
    exact_mean = sum(
        (
            Fraction(right) - Fraction(left)
            for left, right in zip(captured_baseline, captured_scenario, strict=True)
        ),
        Fraction(),
    ) / len(captured_baseline)
    expected_from_capture = float(exact_mean)
    assert Fraction(expected_from_capture) == exact_mean, (
        "Observed-source fixture must stay inside the exact-float mean profile; "
        f"actual selected rows produce {exact_mean}"
    )
    if execution_data_snapshot_ref is None:
        assert captured_baseline == baseline.tolist()
        assert captured_scenario == scenario.tolist()
    if expected_executed_mean is not None:
        assert expected_executed_mean == expected_from_capture
    returned_inventory = [
        {
            "slot_id": item.slot_id,
            "runtime_shape_status": item.runtime_shape_status,
            "runtime_shape": item.runtime_shape,
            "runtime_type": item.runtime_type,
            "codec_status": item.codec_status,
            "retention_status": item.retention_status,
            "declared_slot_type": item.declared_slot_type,
            "declared_shape": item.declared_shape,
        }
        for item in captured_occurrence.returned_slots
    ]
    assert observation.source_status == "observed", (
        f"{observation.source_status}:{','.join(observation.limitations)}; "
        f"returned_inventory={returned_inventory!r}"
    )
    assert observation.value == expected_from_capture
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
            "law_code_digest": "sha256:" + "0" * 64,
            "adapter_id": "unregistered.compiler.adapter",
            "adapter_version": "0",
            "adapter_code_digest": "sha256:" + "1" * 64,
            "availability": "unavailable",
            "limitation": "registered_method_metric_law_unavailable",
        }
    )
    unavailable_binding_set = binding_set.model_copy(update={"bindings": [unavailable_binding]})
    declared_unavailable_binding_ref = MethodMetricBindingSetRef.model_validate(
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
                order=compiled_plan.order if canonical_compile else ["ex_ante_node"],
                policy_fidelity_level=compiled_plan.policy_fidelity_level
                if canonical_compile
                else None,
                mode="dev",
                jit=False,
            ),
            kind=ExecPlan.ARTIFACT_KIND,
            schema_name=ExecPlan.ARTIFACT_SCHEMA_NAME,
            schema_version=ExecPlan.ARTIFACT_SCHEMA_VERSION,
            inputs=[
                input_ref_from_artifact_ref(graph_ref, role="program_graph"),
                input_ref_from_artifact_ref(
                    declared_unavailable_binding_ref,
                    role="method_metric_bindings",
                ),
            ],
        ).model_dump(mode="python")
    )
    current_bundle = validate_core_model_json_artifact(MethodExecutionBundle, store, bundle_ref)
    method_occurrence = next(
        item for item in current_bundle.occurrences if item.node_id == "ex_ante_node"
    )
    returned_result_slot = next(
        item for item in method_occurrence.returned_slots if item.slot_id == "result"
    )
    selected_slot, slot_limitation = _selected_returned_slot(
        occurrence=method_occurrence,
        signature=MethodRegistry.get_instance().get_signature(method_signature.fqn),
        output_slot_id="result",
        expected_value_path=tuple(binding.output_value_path),
    )
    assert selected_slot == returned_result_slot
    assert slot_limitation is None
    assert _is_exact_json_result_container_unit(output_slot.unit)
    for wrong_container_unit in (
        replace(output_slot.unit, dimension="value"),
        replace(output_slot.unit, symbol="amount"),
        replace(output_slot.unit, scale=2.0),
    ):
        wrong_container_signature = replace(
            method_signature,
            output_slots=frozenset(
                replace(slot, unit=wrong_container_unit) if slot.name == "result" else slot
                for slot in method_signature.output_slots
            ),
        )
        wrong_container_slot, wrong_container_limitation = _selected_returned_slot(
            occurrence=method_occurrence,
            signature=wrong_container_signature,
            output_slot_id="result",
            expected_value_path=tuple(binding.output_value_path),
        )
        assert wrong_container_slot is None
        assert wrong_container_limitation == "selected_method_scalar_return_not_fully_captured"
        assert not _is_exact_json_result_container_unit(wrong_container_unit)
        assert not _registered_method_metric_output_slot_contract_matches(
            binding=binding,
            slot=replace(output_slot, unit=wrong_container_unit),
            registered_law_identity=law_identity,
            registered_semantics_match=True,
        )
    wrong_declared_slot = returned_result_slot.model_copy(
        update={"declared_slot_type": str(returned_result_slot.declared_slot_type).lower()}
    )
    wrong_type_occurrence = method_occurrence.model_copy(
        update={
            "returned_slots": [
                wrong_declared_slot if item.slot_id == "result" else item
                for item in method_occurrence.returned_slots
            ]
        }
    )
    with pytest.raises(
        _InvalidProjectionError,
        match="returned_method_slot_inventory_disagrees_with_current_method_abi",
    ):
        _selected_returned_slot(
            occurrence=wrong_type_occurrence,
            signature=MethodRegistry.get_instance().get_signature(method_signature.fqn),
            output_slot_id="result",
            expected_value_path=tuple(binding.output_value_path),
        )

    without_value_path, without_value_path_limitation = _selected_returned_slot(
        occurrence=method_occurrence,
        signature=MethodRegistry.get_instance().get_signature(method_signature.fqn),
        output_slot_id="result",
        expected_value_path=(),
    )
    assert without_value_path is None
    assert without_value_path_limitation == "selected_method_scalar_return_not_fully_captured"

    structured_return_occurrence = method_occurrence.model_copy(
        update={
            "returned_slots": [
                item.model_copy(update={"runtime_shape": (2,)})
                if item.slot_id == "result"
                else item
                for item in method_occurrence.returned_slots
            ]
        }
    )
    selected_structured_slot, structured_slot_limitation = _selected_returned_slot(
        occurrence=structured_return_occurrence,
        signature=MethodRegistry.get_instance().get_signature(method_signature.fqn),
        output_slot_id="result",
        expected_value_path=tuple(binding.output_value_path),
    )
    assert selected_structured_slot is None
    assert structured_slot_limitation == "selected_method_scalar_return_not_fully_captured"
    unavailable_result = execute_foundry(
        store,
        request.model_copy(update={"exec_plan_ref": unavailable_plan_ref}),
    )
    assert unavailable_result.ok is True
    assert unavailable_result.schema_version == "1.1"
    assert unavailable_result.simulation_result_ref is not None
    assert unavailable_result.method_execution_bundle_ref is not None
    unavailable_simulation_ref = unavailable_result.simulation_result_ref
    unavailable_bundle_ref = unavailable_result.method_execution_bundle_ref
    unavailable_binding_ref = next(
        item.ref
        for item in unavailable_result.derived_refs
        if item.role == "method_metric_binding_set"
    )
    assert unavailable_binding_ref == declared_unavailable_binding_ref
    unavailable_bundle_manifest = store.get_manifest(unavailable_bundle_ref)
    # Foundry may bounded-read the source StateSnapshot JSON to reconcile provenance;
    # keep its NPZ values and every selected output/input payload behind this removal guard.
    blocked_payload_edges = [
        edge
        for edge in unavailable_bundle_manifest.inputs
        if edge.role == "environment_manifest"
        or edge.role.startswith(
            (
                "method_output:",
                "method_artifact:",
                "method_prestate:",
                "method_metric_input_capture:",
            )
        )
    ]
    assert any(edge.role == "environment_manifest" for edge in blocked_payload_edges)
    assert any(edge.role.startswith("method_output:") for edge in blocked_payload_edges)

    class _ForbiddenPayloadReadTracker:
        def __init__(self, wrapped: object, forbidden_artifact_roles: dict[str, str]) -> None:
            self._wrapped = wrapped
            self._forbidden_artifact_roles = forbidden_artifact_roles
            self.blocked_reads: list[str] = []

        def __getattr__(self, name: str) -> Any:
            return getattr(self._wrapped, name)

        def _check(self, method_name: str, *args: Any, **kwargs: Any) -> Any:
            artifact_ref = args[0] if args else kwargs.get("artifact_id")
            artifact_id = getattr(artifact_ref, "artifact_id", None)
            artifact_key = None if artifact_id is None else str(artifact_id)
            role = self._forbidden_artifact_roles.get(artifact_key or "")
            if role is not None:
                self.blocked_reads.append(f"{method_name}:{role}")
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
        {str(edge.artifact_id): edge.role for edge in blocked_payload_edges},
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
    assert unavailable_outcome.status == "verified", unavailable_outcome.limitations
    assert unavailable_outcome.admission is not None
    assert payload_tracker.blocked_reads == [], payload_tracker.blocked_reads
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
        resolver=_ProjectionStoreResolver(store, expected_job_id="job-legacy-bundle"),
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
    assert completed_projection.status == "selected", completed_projection.limitations
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
        "completed_source": completed_source,
        "observation": observation,
    }


@pytest.fixture
def public_method_metric_source(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
    cas_store: ArtifactStore,
) -> dict[str, Any]:
    """Build selected source refs and the observation through public Foundry execution."""
    artifacts = _exercise_public_execute_method_metric_source(
        tmp_path,
        monkeypatch,
        artifact_store=cas_store,
        job_id="job-1",
        run_id="run-1",
        attempt=1,
    )
    observation = artifacts["observation"]
    work = artifacts["work"]
    assert observation.output_ref is not None
    assert observation.environment_manifest_ref is not None
    assert observation.input_capture_ref is not None
    return {
        "binding": artifacts["binding_ref"],
        "bundle": work.method_execution_bundle_ref,
        "simulation": work.simulation_result_ref,
        "environment": observation.environment_manifest_ref,
        "output": observation.output_ref,
        "candidate": artifacts["candidate_ref"],
        "observation": observation,
        "work": work,
        "vector_ref": artifacts["projection_admission"].vector_ref,
    }


def _without_selected_output_edge(store: ArtifactStore, source: dict[str, Any]) -> dict[str, Any]:
    """Remove only the selected output edge from an otherwise public typed source chain."""

    bundle_manifest = store.get_manifest(source["bundle"])
    output_ref = source["observation"].output_ref
    assert output_ref is not None
    selected_output_edges = [
        edge
        for edge in bundle_manifest.inputs
        if edge.role.startswith("method_output:") and edge.artifact_id == output_ref.artifact_id
    ]
    assert len(selected_output_edges) == 1
    removed_edge = selected_output_edges[0]
    bundle_inputs = [
        edge
        for edge in bundle_manifest.inputs
        if (edge.role, edge.artifact_id) != (removed_edge.role, removed_edge.artifact_id)
    ]
    bundle_ref = store.put_bytes(
        store.get_bytes(source["bundle"]),
        PutOptions(
            kind=bundle_manifest.kind,
            media_type=bundle_manifest.media_type,
            schema=bundle_manifest.artifact_schema,
            producer=bundle_manifest.producer,
            env=bundle_manifest.env,
            inputs=bundle_inputs,
            canon=bundle_manifest.canon,
            governance=bundle_manifest.governance,
            tenant_context=bundle_manifest.tenant_context,
            same_input_closure=bundle_manifest.same_input_closure,
            authority=bundle_manifest.authority,
            warnings=bundle_manifest.warnings,
        ),
        return_selected_profile=True,
    )

    simulation_manifest = store.get_manifest(source["simulation"])
    execution_edges = [
        edge for edge in simulation_manifest.inputs if edge.role == "method_execution"
    ]
    assert len(execution_edges) == 1
    simulation_inputs = [
        input_ref_from_artifact_ref(bundle_ref, role=edge.role)
        if edge.role == "method_execution"
        else edge
        for edge in simulation_manifest.inputs
    ]
    simulation_ref = store.put_bytes(
        store.get_bytes(source["simulation"]),
        PutOptions(
            kind=simulation_manifest.kind,
            media_type=simulation_manifest.media_type,
            schema=simulation_manifest.artifact_schema,
            producer=simulation_manifest.producer,
            env=simulation_manifest.env,
            inputs=simulation_inputs,
            canon=simulation_manifest.canon,
            governance=simulation_manifest.governance,
            tenant_context=simulation_manifest.tenant_context,
            same_input_closure=simulation_manifest.same_input_closure,
            authority=simulation_manifest.authority,
            warnings=simulation_manifest.warnings,
        ),
        return_selected_profile=True,
    )
    observation = source["observation"].model_copy(
        update={
            "execution_bundle_ref": _selected(bundle_ref),
            "simulation_result_ref": _selected(simulation_ref),
        }
    )
    work = replace(
        source["work"],
        simulation_result_ref=simulation_ref,
        method_execution_bundle_ref=bundle_ref,
    )
    return {
        **source,
        "bundle": bundle_ref,
        "simulation": simulation_ref,
        "observation": observation,
        "work": work,
    }


def _with_malformed_selected_output(store: ArtifactStore, source: dict[str, Any]) -> dict[str, Any]:
    """Corrupt one selected output payload while preserving the typed source graph."""
    from polisyos.core.artifacts import validate_core_model_json_artifact
    from polisyos.core.canon import CanonSpec
    from polisyos.core.contracts.foundry import (
        MethodExecutionBundle,
        MethodOutputPayload,
        MethodOutputRef,
    )

    output_ref = source["observation"].output_ref
    assert output_ref is not None
    stable_refs = (
        source["candidate"],
        source["binding"],
        source["environment"],
        source["observation"].input_capture_ref,
    )
    assert all(ref is not None for ref in stable_refs)
    stable_payloads = tuple(store.get_bytes(ref) for ref in stable_refs)
    original_simulation_bytes = store.get_bytes(source["simulation"])
    original_output_bytes = store.get_bytes(output_ref)
    output_manifest = store.get_manifest(output_ref)
    output_payload = validate_core_model_json_artifact(
        MethodOutputPayload, store, output_ref
    ).model_dump(mode="python")
    output_payload["value"] = "malformed-selected-output"
    malformed_output_ref = store.put_json(
        output_payload,
        PutOptions(
            kind=output_manifest.kind,
            media_type=output_manifest.media_type,
            schema=output_manifest.artifact_schema,
            producer=output_manifest.producer,
            env=output_manifest.env,
            inputs=output_manifest.inputs,
            canon=output_manifest.canon,
            governance=output_manifest.governance,
            tenant_context=output_manifest.tenant_context,
            same_input_closure=output_manifest.same_input_closure,
            authority=output_manifest.authority,
            warnings=output_manifest.warnings,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    import json

    original_output_json = json.loads(original_output_bytes)
    malformed_output_json = json.loads(store.get_bytes(malformed_output_ref))
    malformed_output_json["value"] = original_output_json["value"]
    assert malformed_output_json == original_output_json

    bundle_manifest = store.get_manifest(source["bundle"])
    output_edges = [
        edge
        for edge in bundle_manifest.inputs
        if edge.artifact_id == output_ref.artifact_id and edge.role.startswith("method_output:")
    ]
    assert len(output_edges) == 1
    selected_output_edge = output_edges[0]
    original_bundle = validate_core_model_json_artifact(
        MethodExecutionBundle, store, source["bundle"]
    )
    selected_output_ref = MethodOutputRef.model_validate(
        malformed_output_ref.model_dump(mode="python")
    )
    replacement_count = 0
    updated_occurrences = []
    for occurrence in original_bundle.occurrences:
        output_slots = []
        occurrence_changed = False
        for slot in occurrence.output_slots:
            if (
                slot.output_ref is not None
                and slot.output_ref.artifact_id == output_ref.artifact_id
                and slot.output_ref.manifest_profile_sha256 == output_ref.manifest_profile_sha256
            ):
                replacement_count += 1
                occurrence_changed = True
                output_slots.append(slot.model_copy(update={"output_ref": selected_output_ref}))
            else:
                output_slots.append(slot)
        updated_occurrences.append(
            occurrence.model_copy(update={"output_slots": output_slots})
            if occurrence_changed
            else occurrence
        )
    assert replacement_count == 1
    bundle_payload = MethodExecutionBundle.model_validate(
        original_bundle.model_copy(update={"occurrences": updated_occurrences}).model_dump(
            mode="python"
        )
    )
    expected_bundle_payload = original_bundle.model_copy(
        update={
            "occurrences": [
                occurrence.model_copy(
                    update={
                        "output_slots": [
                            slot.model_copy(update={"output_ref": selected_output_ref})
                            if (
                                slot.output_ref is not None
                                and slot.output_ref.artifact_id == output_ref.artifact_id
                                and slot.output_ref.manifest_profile_sha256
                                == output_ref.manifest_profile_sha256
                            )
                            else slot
                            for slot in occurrence.output_slots
                        ]
                    }
                )
                for occurrence in original_bundle.occurrences
            ]
        }
    )
    assert bundle_payload.model_dump(mode="json") == expected_bundle_payload.model_dump(mode="json")

    bundle_inputs = [
        input_ref_from_artifact_ref(malformed_output_ref, role=edge.role)
        if edge is selected_output_edge
        else edge
        for edge in bundle_manifest.inputs
    ]
    bundle_ref = store.put_json(
        bundle_payload,
        PutOptions(
            kind=bundle_manifest.kind,
            media_type=bundle_manifest.media_type,
            schema=bundle_manifest.artifact_schema,
            producer=bundle_manifest.producer,
            env=bundle_manifest.env,
            inputs=bundle_inputs,
            canon=bundle_manifest.canon,
            governance=bundle_manifest.governance,
            tenant_context=bundle_manifest.tenant_context,
            same_input_closure=bundle_manifest.same_input_closure,
            authority=bundle_manifest.authority,
            warnings=bundle_manifest.warnings,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )

    simulation_manifest = store.get_manifest(source["simulation"])
    simulation_inputs = [
        input_ref_from_artifact_ref(bundle_ref, role=edge.role)
        if edge.role == "method_execution"
        else edge
        for edge in simulation_manifest.inputs
    ]
    simulation_ref = store.put_bytes(
        original_simulation_bytes,
        PutOptions(
            kind=simulation_manifest.kind,
            media_type=simulation_manifest.media_type,
            schema=simulation_manifest.artifact_schema,
            producer=simulation_manifest.producer,
            env=simulation_manifest.env,
            inputs=simulation_inputs,
            canon=simulation_manifest.canon,
            governance=simulation_manifest.governance,
            tenant_context=simulation_manifest.tenant_context,
            same_input_closure=simulation_manifest.same_input_closure,
            authority=simulation_manifest.authority,
            warnings=simulation_manifest.warnings,
        ),
        return_selected_profile=True,
    )

    assert store.get_bytes(simulation_ref) == original_simulation_bytes
    assert tuple(store.get_bytes(ref) for ref in stable_refs) == stable_payloads
    assert store.get_bytes(malformed_output_ref) != original_output_bytes

    work = replace(
        source["work"],
        simulation_result_ref=simulation_ref,
        method_execution_bundle_ref=bundle_ref,
    )
    return {
        **source,
        "bundle": bundle_ref,
        "simulation": simulation_ref,
        "work": work,
        "malformed_output_ref": malformed_output_ref,
    }


def test_public_execute_source_is_admitted_and_missing_prestate_edge_is_refused(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _exercise_public_execute_method_metric_source(tmp_path, monkeypatch)


def test_registry_bundle_uses_exact_schema_absence_with_typed_selected_profile(
    cas_store: ArtifactStore,
) -> None:
    """The real RegistryBundle owner is schema-less but remains a strict typed read."""
    from polisyos.core.artifacts.registry import RegistryBundlePayload
    from polisyos.core.canon import CanonSpec
    from polisyos.core.registry import build_default_registry_bundle

    produced = build_default_registry_bundle(cas_store, return_selected_profile=True)
    manifest = cas_store.get_manifest(produced.bundle_ref)
    assert manifest.artifact_schema is None
    assert produced.bundle_ref.manifest_profile_sha256 is not None

    selected_ref = SelectedMethodMetricArtifactRef.model_validate(
        produced.bundle_ref.model_dump(mode="python")
    )
    loaded_manifest, loaded_payload = _load_method_metric_model(
        cas_store,
        ref=selected_ref,
        model=RegistryBundlePayload,
        expected_kind="core.registry_bundle",
        expected_schema_name=None,
        expected_schema_versions=None,
        max_bytes=1024 * 1024,
        read_budget=_ProjectionReadBudget(),
    )
    assert loaded_manifest.artifact_schema is None
    assert isinstance(loaded_payload, RegistryBundlePayload)
    assert loaded_payload == RegistryBundlePayload(
        slot_registry=produced.slot_registry,
        merge_registry=produced.merge_registry,
        constraint_registry=produced.constraint_registry,
        selector_field_registry=produced.selector_field_registry,
        metric_registry=produced.metric_registry,
        mechanism_registry=produced.mechanism_registry,
        trust_registry=produced.trust_registry,
        units_registry=produced.units_registry,
        predicate_registry=produced.predicate_registry,
        privacy_registry=produced.privacy_registry,
    )

    wrong_schema_ref = cas_store.put_json(
        loaded_payload,
        PutOptions(
            kind="core.registry_bundle",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.core.RegistryBundlePayload",
                version="1.0",
            ),
            inputs=manifest.inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    wrong_selected_ref = SelectedMethodMetricArtifactRef.model_validate(
        wrong_schema_ref.model_dump(mode="python")
    )
    with pytest.raises(
        _InvalidProjectionError,
        match="selected_method_metric_artifact_schema_or_kind_mismatch",
    ):
        _load_method_metric_model(
            cas_store,
            ref=wrong_selected_ref,
            model=RegistryBundlePayload,
            expected_kind="core.registry_bundle",
            expected_schema_name=None,
            expected_schema_versions=None,
            max_bytes=1024 * 1024,
            read_budget=_ProjectionReadBudget(),
        )


def test_state_blob_manifest_is_read_only_through_its_selected_snapshot_parent(
    cas_store: ArtifactStore,
) -> None:
    """A real Foundry snapshot selects the only binary edge eligible for absent CanonInfo."""
    import numpy as np

    from polisyos.foundry.execute._internal.snapshots import put_state_snapshot

    snapshot_ref = put_state_snapshot(
        cas_store,
        state={"baseline": np.asarray([1.0]), "scenario": np.asarray([2.0])},
        return_selected_profile=True,
    )
    snapshot_manifest = cas_store.get_manifest(snapshot_ref)
    edges = [edge for edge in snapshot_manifest.inputs if edge.role == "state_blob"]
    assert len(edges) == 1

    budget = _ProjectionReadBudget()
    reader = _BoundedExecutionSourceReader(cas_store, budget)
    selected_manifest, parent_bytes = reader.read_selected_manifest(snapshot_ref)
    state_ref, state_manifest, child_bytes = reader.read_edge_manifest(snapshot_ref, edges[0])

    assert selected_manifest.kind == "foundry.state_snapshot"
    assert state_ref.kind == "foundry.state_blob"
    assert state_ref.media_type == "application/x-npz"
    assert state_ref.manifest_profile_sha256 == edges[0].manifest_profile_sha256
    assert state_manifest.canon is None
    assert state_manifest.artifact_schema is None
    assert parent_bytes > 0
    assert child_bytes > 0
    assert budget.observed_execution_source_bytes == parent_bytes + child_bytes


def test_state_blob_absence_exception_rejects_wrong_parent_profile_and_json(
    cas_store: ArtifactStore,
) -> None:
    """The binary exception cannot be borrowed across parents or used for JSON."""
    import numpy as np

    from polisyos.foundry.execute._internal.snapshots import put_state_snapshot

    first_ref = put_state_snapshot(
        cas_store,
        state={"baseline": np.asarray([1.0])},
        step=1,
        return_selected_profile=True,
    )
    second_ref = put_state_snapshot(
        cas_store,
        state={"baseline": np.asarray([1.0])},
        step=2,
        return_selected_profile=True,
    )
    first_manifest = cas_store.get_manifest(first_ref)
    second_manifest = cas_store.get_manifest(second_ref)
    first_edge = next(edge for edge in first_manifest.inputs if edge.role == "state_blob")
    second_edge = next(edge for edge in second_manifest.inputs if edge.role == "state_blob")
    assert first_edge == second_edge
    assert first_ref != second_ref

    reader = _BoundedExecutionSourceReader(cas_store, _ProjectionReadBudget())
    reader.read_selected_manifest(first_ref)
    with pytest.raises(ValueError):
        reader.read_edge_manifest(second_ref, first_edge)

    reader = _BoundedExecutionSourceReader(cas_store, _ProjectionReadBudget())
    reader.read_selected_manifest(first_ref)
    wrong_profile = first_edge.model_copy(update={"manifest_profile_sha256": "sha256:" + "0" * 64})
    with pytest.raises(ValueError):
        reader.read_edge_manifest(first_ref, wrong_profile)

    absent_json_ref = cas_store.put_bytes(
        b'{"candidate":true}',
        PutOptions(kind="test.profileless_json", media_type="application/json"),
        return_selected_profile=True,
    )
    absent_json_edge = input_ref_from_artifact_ref(absent_json_ref, role="state_blob")
    reader = _BoundedExecutionSourceReader(cas_store, _ProjectionReadBudget())
    with pytest.raises(_InvalidProjectionError, match="canon_profile_absent"):
        reader.read_edge_manifest(first_ref, absent_json_edge)


def test_small_profileless_json_refusal_is_invalid_not_budget_exhaustion(
    cas_store: ArtifactStore,
) -> None:
    """A small Core selection refusal is invalid even with the byte budget available."""
    from polisyos.core.contracts.foundry import SimulationResult

    simulation_ref = cas_store.put_bytes(
        b"{}",
        PutOptions(
            kind=SimulationResult.ARTIFACT_KIND,
            media_type=SimulationResult.ARTIFACT_MEDIA_TYPE,
        ),
        return_selected_profile=True,
    )
    budget = _ProjectionReadBudget()
    reader = _BoundedExecutionSourceReader(cas_store, budget)

    with pytest.raises(_InvalidProjectionError, match="canon_profile_absent"):
        reader.read_selected_manifest(simulation_ref)

    assert 0 < budget.observed_execution_source_bytes < 1024
    assert budget.remaining_bytes > 0

    outcome = prepare_method_metric_projection_admission(
        cas_store,
        source_tuple=_MethodMetricSourceTuple(
            job_id="job-profileless-json",
            run_id="run-profileless-json",
            attempt=1,
            method_result_ref=None,
            simulation_result_ref=simulation_ref,
            method_execution_bundle_ref=ArtifactRef(
                artifact_id="sha256:" + "a" * 64,
                kind="foundry.method_execution_bundle",
                media_type="application/json",
                manifest_profile_sha256="sha256:" + "b" * 64,
            ),
            method_metric_binding_set_ref=ArtifactRef(
                artifact_id="sha256:" + "c" * 64,
                kind="foundry.method_metric_binding_set",
                media_type="application/json",
                manifest_profile_sha256="sha256:" + "d" * 64,
            ),
        ),
    )
    assert outcome.status == "invalid"
    assert outcome.admission is None
    assert any("canon_profile_absent" in reason for reason in outcome.limitations)
    assert not any("source_bytes_exceed" in reason for reason in outcome.limitations)


def test_core_manifest_cap_and_missing_bounded_receipt_keep_distinct_statuses(
    cas_store: ArtifactStore,
) -> None:
    """A measured cap overrun is bounded; an unavailable reader is unestablished."""
    from polisyos.core.contracts.foundry import SimulationResult
    from polisyos.foundry.execute import ExecutionSourceBoundedReadRefusal

    simulation_ref = cas_store.put_bytes(
        b"{}",
        PutOptions(
            kind=SimulationResult.ARTIFACT_KIND,
            media_type=SimulationResult.ARTIFACT_MEDIA_TYPE,
        ),
        return_selected_profile=True,
    )
    bounded_reader = _BoundedExecutionSourceReader(
        cas_store,
        _ProjectionReadBudget(max_bytes=64),
    )
    with pytest.raises(ExecutionSourceBoundedReadRefusal) as bounded:
        bounded_reader.read_selected_manifest(simulation_ref)
    assert bounded.value.limit_bytes == 64

    class _UnavailableManifestReader:
        def __init__(self, wrapped: ArtifactStore) -> None:
            self._wrapped = wrapped

        def __getattr__(self, name: str) -> Any:
            return getattr(self._wrapped, name)

        def read_raw_manifest_bytes_bounded(self, *_args: Any, **_kwargs: Any) -> Any:
            raise NotImplementedError("bounded_manifest_reader_unavailable")

    unavailable = _BoundedExecutionSourceReader(
        _UnavailableManifestReader(cas_store),
        _ProjectionReadBudget(),
    )
    with pytest.raises(
        _UnestablishedProjectionError,
        match="core_store_transfer_accounting_not_established",
    ):
        unavailable.read_selected_manifest(simulation_ref)


@pytest.mark.parametrize(
    ("ref_change", "edge_role"),
    [
        pytest.param({"kind": "foundry.other_blob"}, "state_blob", id="wrong-kind"),
        pytest.param({"media_type": "application/octet-stream"}, "state_blob", id="wrong-media"),
        pytest.param({}, "other_blob", id="wrong-parent-edge"),
    ],
)
def test_snapshot_parent_kind_media_and_edge_are_recomputed(
    cas_store: ArtifactStore,
    ref_change: dict[str, str],
    edge_role: str,
) -> None:
    """Only the actual selected snapshot schema and exact state_blob edge can qualify."""
    from polisyos.core.canon import CanonSpec
    from polisyos.core.contracts.foundry import StateSnapshot

    state_ref = cas_store.put_bytes(
        b"npz-placeholder",
        PutOptions(kind="foundry.state_blob", media_type="application/x-npz"),
        return_selected_profile=True,
    )
    changed_ref = state_ref.model_copy(update=ref_change) if ref_change else state_ref
    edge = input_ref_from_artifact_ref(changed_ref, role=edge_role)
    snapshot = StateSnapshot(
        schema_version="2.3",
        state_ref=changed_ref,
        format_version="npz-v2",
        entry_count=1,
        codec="numpy-npz",
        lineage_inputs=[edge],
        layout="method_input_slots",
    )
    snapshot_ref = cas_store.put_json(
        snapshot,
        PutOptions(
            kind="foundry.state_snapshot",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.StateSnapshot", version="2.3.0"),
            inputs=[edge],
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    reader = _BoundedExecutionSourceReader(cas_store, _ProjectionReadBudget())

    with pytest.raises(ValueError):
        reader.read_selected_manifest(snapshot_ref)


def test_state_blob_malformed_present_canon_is_not_treated_as_absent(
    cas_store: ArtifactStore,
) -> None:
    """The explicit binary absence path still rejects a malformed present profile."""
    import json
    from dataclasses import replace

    import numpy as np

    from polisyos.core.artifacts import ArtifactBoundedManifestRead
    from polisyos.foundry.execute._internal.snapshots import put_state_snapshot

    snapshot_ref = put_state_snapshot(
        cas_store,
        state={"baseline": np.asarray([1.0])},
        return_selected_profile=True,
    )
    snapshot_manifest = cas_store.get_manifest(snapshot_ref)
    edge = next(edge for edge in snapshot_manifest.inputs if edge.role == "state_blob")
    state_ref = cas_store.get_manifest_by_profile(
        edge.artifact_id,
        edge.manifest_profile_sha256,
    )
    state_ref = ArtifactRef(
        artifact_id=state_ref.artifact_id,
        kind=state_ref.kind,
        media_type=state_ref.media_type,
        manifest_profile_sha256=edge.manifest_profile_sha256,
    )

    class _MalformedPresentCanonStore:
        def __init__(self) -> None:
            self.target_reads = 0

        def __getattr__(self, name: str) -> object:
            return getattr(cas_store, name)

        def read_raw_manifest_bytes_bounded(
            self,
            selected: object,
            *,
            max_manifest_bytes: int,
            manifest_profile_sha256: str | None = None,
        ) -> ArtifactBoundedManifestRead:
            receipt = cas_store.read_raw_manifest_bytes_bounded(
                selected,
                max_manifest_bytes=max_manifest_bytes,
                manifest_profile_sha256=manifest_profile_sha256,
            )
            if (
                isinstance(selected, ArtifactRef)
                and selected.artifact_id == state_ref.artifact_id
                and selected.manifest_profile_sha256 == state_ref.manifest_profile_sha256
            ):
                self.target_reads += 1
                raw = json.loads(receipt.raw_manifest_bytes)
                raw["canon"] = {"name": 7}
                mutated = json.dumps(raw, separators=(",", ":")).encode("utf-8")
                usage = replace(
                    receipt.usage,
                    observed_manifest_selection_bytes=len(mutated),
                )
                return ArtifactBoundedManifestRead(
                    raw_manifest_bytes=mutated,
                    usage=usage,
                )
            return receipt

    malformed_store = _MalformedPresentCanonStore()
    reader = _BoundedExecutionSourceReader(malformed_store, _ProjectionReadBudget())
    reader.read_selected_manifest(snapshot_ref)
    with pytest.raises(
        _InvalidProjectionError,
        match="state_blob_manifest_refused:canon_profile_bounded_manifest_invalid",
    ):
        reader.read_edge_manifest(snapshot_ref, edge)

    assert malformed_store.target_reads == 1


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
    state = ExperimentState(run_id="run-1", params=request.params)

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
    state = ExperimentState(run_id="run-1", params=request.params)
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
    state = ExperimentState(run_id="run-1", params=request.params)
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
    state = ExperimentState(run_id="run-1", params=request.params)
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
    ("request_status", "source_run_id", "feedback_verdict", "expected_terminal_action"),
    [
        pytest.param("invalid", None, "UNKNOWN", None, id="malformed-present-unknown"),
        pytest.param("requested", "source-run", "UNKNOWN", None, id="requested-unknown"),
        pytest.param("absent", None, "UNKNOWN", None, id="explicit-absent-unknown"),
        pytest.param("invalid", None, "APPROVE", "reject", id="malformed-present-approve"),
        pytest.param("requested", "source-run", "APPROVE", "reject", id="requested-approve"),
        pytest.param("absent", None, "APPROVE", "reject", id="explicit-absent-approve"),
    ],
)
def test_lost_status_and_required_marker_cannot_open_l3_legacy_fallback(
    monkeypatch: pytest.MonkeyPatch,
    request_status: str,
    source_run_id: str | None,
    feedback_verdict: Literal["UNKNOWN", "APPROVE"],
    expected_terminal_action: str | None,
) -> None:
    """Capsule identity/basis left after status loss cannot become legacy."""

    class _Workflow:
        def run(self, initial_state: dict[str, Any]) -> dict[str, Any]:
            del initial_state
            return {"simulation_results": {}, "feedback": {"verdict": feedback_verdict}}

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
    assert result.is_promising is False
    assert result.terminal_action == expected_terminal_action


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


def test_search_hte_receiver_normalizes_core_owner_outcome_ref_and_rejects_drift(
    tmp_path,
):
    from types import SimpleNamespace

    from polisyos.core.artifacts import ensure_ir_artifact_store
    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.core.contracts.owned_attempt_anchor import SelectedArtifactRef
    from polisyos.ir.analytics.hte import (
        HTEOutcome,
        HTERefusalOutcome,
        persist_hte_outcome,
    )
    from polisyos.ir.registry.refs import (
        HTEPhysicalSourceMaterializationBindingRef,
        HTERefusalDiagnosticRef,
        MethodExecutionEvidenceRef,
        MethodResultEvidenceRef,
        OwnedAttemptAnchorRef,
    )
    from polisyos.scientist.methods.search.uncertainty import (
        SearchUncertaintyAdmissionError,
        _build_hte_assessment_candidate,
        _load_hte_outcome_from_owner_ref,
    )

    def profiled_ref(ref_type, value):
        return ref_type.model_validate(
            {
                "artifact_id": f"sha256:{value:064x}",
                "manifest_profile_sha256": f"sha256:{value + 1000:064x}",
            },
            strict=True,
        )

    refusal = HTERefusalOutcome(
        method_fqn="causal.hte.causal_forest@2.0.0",
        method_abi="2.0.0",
        method_abi_digest="c" * 64,
        method_profile_id="econml.causal_forest_dml.native_mean@2.0",
        refusal_stage="prepare",
        refusal_reason="required_input_unavailable",
        diagnostic_code="contrast_not_established",
        owned_attempt_anchor_ref=profiled_ref(OwnedAttemptAnchorRef, 1),
        anchor_status="pre_output_anchor_resolved",
        requested_source_ref=None,
        requested_source_status="not_established",
        source_data_ref=None,
        source_data_status="not_established",
        materialization_binding_ref=profiled_ref(HTEPhysicalSourceMaterializationBindingRef, 2),
        input_profile_id=None,
        selected_input_sha256=None,
        selected_rows_sha256=None,
        selected_x_sha256=None,
        selected_row_order_sha256=None,
        resolved_params_sha256=None,
        n_selected_rows=None,
        selected_rows_status="not_established",
        method_result_ref=profiled_ref(MethodResultEvidenceRef, 3),
        method_result_status="available",
        method_evidence_ref=profiled_ref(MethodExecutionEvidenceRef, 4),
        method_evidence_status="available",
        resource_evidence=None,
        invocation_basis_ref=None,
        invocation_basis_status="not_established",
        invocation_basis_reason="not_available_at_refusal_stage",
        refusal_diagnostic_ref=profiled_ref(HTERefusalDiagnosticRef, 5),
        request_estimand_status="not_established",
        request_estimand=None,
        request_target_scope_status="not_established",
        request_target_scope=None,
        outcome_variable_status="not_established",
        outcome_variable_id=None,
        treatment_variable_status="not_established",
        treatment_variable_id=None,
        contrast_status="not_established",
        control_value=None,
        treated_value=None,
        request_alpha_status="not_established",
        requested_alpha=None,
        requested_guarantee_status="not_established",
        requested_guarantee=None,
        target_relation=None,
        limitations=("required_input_unavailable",),
    )
    store = ensure_ir_artifact_store(FileSystemCAS(tmp_path / "hte-cas"))
    ir_ref = persist_hte_outcome(store, HTEOutcome(root=refusal))
    core_selected_ref = SelectedArtifactRef.model_validate(
        ir_ref.model_dump(mode="python"),
        strict=True,
    )

    loaded = _load_hte_outcome_from_owner_ref(store, core_selected_ref)
    assert loaded.kind == "refusal"
    assert loaded.root.diagnostic_code == "contrast_not_established"

    def receive(ref):
        return _build_hte_assessment_candidate(
            store=store,
            association=SimpleNamespace(outcome_ref=ref),
            binding_ref=core_selected_ref,
            binding=SimpleNamespace(selected_method_params={}, selected_method_seed=0),
            basis=None,
            predecessor=None,
            predecessor_ref=core_selected_ref,
            completed_at=None,
        )

    # The real candidate consumer path must load the selected owner ref and
    # preserve typed refusal rather than treating it as absence.
    with pytest.raises(SearchUncertaintyAdmissionError) as refusal_error:
        receive(core_selected_ref)
    assert refusal_error.value.reason_code == "hte_method_refusal"

    wrong_kind = core_selected_ref.model_copy(update={"kind": "ir.other_outcome"})
    with pytest.raises(ValidationError):
        receive(wrong_kind)

    wrong_media = core_selected_ref.model_copy(update={"media_type": "text/plain"})
    with pytest.raises(ValidationError):
        receive(wrong_media)

    wrong_profile = core_selected_ref.model_copy(
        update={"manifest_profile_sha256": "sha256:" + "0" * 64}
    )
    from polisyos.ir.model_layer.canon import CanonViolation

    with pytest.raises(CanonViolation, match="ir_owned_artifact_read_refused"):
        receive(wrong_profile)

    malformed = SelectedArtifactRef.model_construct(
        artifact_id=core_selected_ref.artifact_id,
        kind=core_selected_ref.kind,
        media_type=core_selected_ref.media_type,
        manifest_profile_sha256="malformed-profile",
    )
    with pytest.raises(ValidationError):
        receive(malformed)


def test_search_hte_receiver_projects_ir_physical_ref_for_core_bounded_read(tmp_path):
    from polisyos.core.artifacts import (
        CanonInfo,
        CoreJsonReadLimits,
        read_core_json_artifact_bounded,
    )
    from polisyos.core.artifacts.manifest import (
        ArtifactRef as CoreArtifactRef,
    )
    from polisyos.core.artifacts.manifest import (
        SchemaInfo,
    )
    from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
    from polisyos.core.canon import CanonSpec, to_canonical_bytes
    from polisyos.core.contracts.owned_attempt_anchor import SelectedArtifactRef
    from polisyos.ir.registry.refs import HTEPhysicalSourceMaterializationBindingRef
    from polisyos.scientist.methods.search.uncertainty import (
        _core_artifact_ref_from_owner_ref,
    )

    store = FileSystemCAS(tmp_path / "physical-cas")
    payload = {"scope": "physical_materialization_only"}
    spec = CanonSpec(forbid_floats=False)
    raw = to_canonical_bytes(payload, spec)
    core_ref = store.put_bytes(
        raw,
        PutOptions(
            kind="foundry.hte.physical_source_materialization_binding",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.foundry.HTEPhysicalSourceMaterializationBinding",
                version="1.0",
            ),
            canon=CanonInfo.from_spec(spec),
        ),
        return_selected_profile=True,
    )
    ir_ref = HTEPhysicalSourceMaterializationBindingRef.model_validate(
        core_ref.model_dump(mode="python"),
        strict=True,
    )
    projected_ir_ref = _core_artifact_ref_from_owner_ref(ir_ref)
    core_subtype = SelectedArtifactRef.model_validate(
        core_ref.model_dump(mode="python"),
        strict=True,
    )
    projected_core_ref = _core_artifact_ref_from_owner_ref(core_subtype)

    assert type(projected_ir_ref) is CoreArtifactRef
    assert type(projected_core_ref) is CoreArtifactRef
    assert projected_ir_ref == core_ref == projected_core_ref
    bounded = read_core_json_artifact_bounded(
        store,
        projected_ir_ref,
        limits=CoreJsonReadLimits(
            max_bytes=len(raw),
            max_depth=8,
            max_elements=8,
            max_manifest_bytes=4096,
        ),
    )
    assert bounded.value == payload
    assert bounded.effective_ref == core_ref


def test_returned_runtime_type_mismatch_limits_persisted_metric_at_both_search_consumers(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A persisted return-type contradiction cannot promote a selected numeric sidecar."""
    from types import SimpleNamespace

    from polisyos.core.artifacts import validate_core_model_json_artifact
    from polisyos.core.canon import CanonSpec
    from polisyos.core.contracts.foundry import (
        MethodExecutionBundle,
        MethodOutputPayload,
        SimulationResult,
    )
    from polisyos.scientist.methods.search.funnel.level3_medium import Level3MediumFidelity
    from polisyos.scientist.methods.search.stages import ExpensiveStage

    artifacts = _exercise_public_execute_method_metric_source(tmp_path, monkeypatch)
    store = artifacts["store"]
    work = artifacts["work"]
    candidate_ref = artifacts["candidate_ref"]
    experiment_state_ref = artifacts["experiment_state_ref"]
    execute_result = artifacts["execute_result"]
    original_observation = artifacts["observation"]
    bundle_ref = artifacts["bundle_ref"]
    binding_ref = artifacts["binding_ref"]
    assert execute_result.simulation_result_ref is not None

    original_bundle = validate_core_model_json_artifact(
        MethodExecutionBundle,
        store,
        bundle_ref,
    )
    occurrence = next(
        item for item in original_bundle.occurrences if item.node_id == "ex_ante_node"
    )
    returned_row = next(item for item in occurrence.returned_slots if item.slot_id == "result")
    output_slot = next(item for item in occurrence.output_slots if item.slot_id == "result")
    assert returned_row.runtime_type == "builtins.dict"
    assert output_slot.status == "captured"
    assert output_slot.output_ref is not None
    sidecar = validate_core_model_json_artifact(
        MethodOutputPayload,
        store,
        output_slot.output_ref,
    )
    assert tuple(sidecar.value_path) == ("mean_change",)
    assert type(sidecar.value) is float
    assert sidecar.value == pytest.approx(1.0)

    mutated_occurrences = [
        item.model_copy(
            update={
                "returned_slots": [
                    row.model_copy(update={"runtime_type": "builtins.str"})
                    if row.slot_id == "result"
                    else row
                    for row in item.returned_slots
                ]
            }
        )
        if item.occurrence_id == occurrence.occurrence_id
        else item
        for item in original_bundle.occurrences
    ]
    mutated_bundle = original_bundle.model_copy(update={"occurrences": mutated_occurrences})
    original_dump = original_bundle.model_dump(mode="python")
    mutated_dump = mutated_bundle.model_dump(mode="python")
    original_result = next(
        row
        for item in original_dump["occurrences"]
        for row in item["returned_slots"]
        if row["slot_id"] == "result"
    )
    mutated_result = next(
        row
        for item in mutated_dump["occurrences"]
        for row in item["returned_slots"]
        if row["slot_id"] == "result"
    )
    assert original_result.pop("runtime_type") == "builtins.dict"
    assert mutated_result.pop("runtime_type") == "builtins.str"
    assert original_dump == mutated_dump

    original_bundle_manifest = store.get_manifest(bundle_ref)
    malformed_bundle_ref = store.put_json(
        mutated_bundle,
        PutOptions(
            kind=MethodExecutionBundle.ARTIFACT_KIND,
            media_type=MethodExecutionBundle.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=MethodExecutionBundle.ARTIFACT_SCHEMA_NAME,
                version=MethodExecutionBundle.ARTIFACT_SCHEMA_VERSION,
            ),
            inputs=original_bundle_manifest.inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    simulation = validate_core_model_json_artifact(
        SimulationResult,
        store,
        execute_result.simulation_result_ref,
    )
    simulation_manifest = store.get_manifest(execute_result.simulation_result_ref)
    simulation_inputs = [
        edge for edge in simulation_manifest.inputs if edge.role != "method_execution"
    ]
    simulation_inputs.append(
        input_ref_from_artifact_ref(malformed_bundle_ref, role="method_execution")
    )
    malformed_simulation_ref = store.put_json(
        simulation,
        PutOptions(
            kind=SimulationResult.ARTIFACT_KIND,
            media_type=SimulationResult.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=SimulationResult.ARTIFACT_SCHEMA_NAME,
                version=simulation.schema_version,
            ),
            inputs=simulation_inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    outcome = prepare_method_metric_projection_admission(
        store,
        source_tuple=_MethodMetricSourceTuple(
            job_id=work.job_id,
            run_id=work.run_id,
            attempt=work.attempt,
            method_result_ref=None,
            simulation_result_ref=malformed_simulation_ref,
            method_execution_bundle_ref=malformed_bundle_ref,
            method_metric_binding_set_ref=binding_ref,
        ),
    )
    assert outcome.status == "verified", outcome.limitations
    assert outcome.admission is not None
    projected_vector = validate_core_model_json_artifact(
        PolicyEvaluationVector,
        store,
        outcome.admission.vector_ref,
    )
    assert len(projected_vector.method_metric_observations) == 1
    rejected_observation = projected_vector.method_metric_observations[0]
    assert rejected_observation.source_status == "not_established"
    assert rejected_observation.value is None
    assert rejected_observation.output_ref == original_observation.output_ref
    assert rejected_observation.output_ref is not None

    selection = SimpleNamespace(
        selection_kind="graph_method",
        job_id=work.job_id,
        run_id=work.run_id,
        attempt=work.attempt,
        method_result_ref=None,
        simulation_result_ref=malformed_simulation_ref,
        method_execution_bundle_ref=malformed_bundle_ref,
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

    expected_candidate_ref = candidate_ref

    class _CompletedMetricOwner:
        def resolve_completed_method_metric_selection(
            self,
            *,
            source_run_id: str,
            candidate_ref: object,
            tenant_id: str,
            cell_id: str | None,
        ) -> object:
            assert source_run_id == work.run_id
            assert candidate_ref == expected_candidate_ref
            assert (tenant_id, cell_id) == ("tenant-r2", "cell-r2")
            return completed_source

    completed = read_completed_admitted_method_metric_projection(
        store,
        owner=_CompletedMetricOwner(),
        source_run_id=work.run_id,
        candidate_ref=candidate_ref,
        tenant_id="tenant-r2",
        cell_id="cell-r2",
    )
    assert completed.status == "selected", completed.limitations
    assert completed.basis is not None
    limited_score = admit_funnel_method_metric_objective_score(
        {
            **_runtime_method_metric_context(
                "requested",
                source_run_id=work.run_id,
                projection_basis=completed.basis,
            ),
            "policy_candidate_ref": candidate_ref,
        }
    )
    assert limited_score is not None
    assert limited_score.status in {
        ObjectiveScoreStatus.NOT_ESTABLISHED,
        ObjectiveScoreStatus.UNAVAILABLE,
    }

    class _Workflow:
        def run(self, state: dict[str, object]) -> dict[str, object]:
            return {
                "simulation_results": {},
                "feedback": {"verdict": "APPROVE"},
            }

    def _evaluate_both(basis: object):
        context = _runtime_method_metric_context(
            "requested",
            source_run_id=work.run_id,
            projection_basis=basis,
        )
        context["policy_candidate_ref"] = candidate_ref
        engine = _Workflow()
        return (
            Level3MediumFidelity(engine).evaluate({"candidate": "runtime-type"}, context),
            ExpensiveStage(engine).evaluate({"candidate": "runtime-type"}, context),
        )

    positive_basis = artifacts["projection"].basis
    assert positive_basis is not None
    positive_stages = _evaluate_both(positive_basis)
    assert all(stage.score_status is ObjectiveScoreStatus.AVAILABLE for stage in positive_stages)
    assert all(stage.objective_value is not None for stage in positive_stages)

    negative_stages = _evaluate_both(completed.basis)
    assert all(
        stage.score_status
        in {ObjectiveScoreStatus.NOT_ESTABLISHED, ObjectiveScoreStatus.UNAVAILABLE}
        for stage in negative_stages
    )
    assert all(stage.objective_value is None for stage in negative_stages)
    assert all(not stage.is_promising for stage in negative_stages)


@pytest.mark.parametrize(
    ("runtime_type", "selected_value", "admitted"),
    [
        ("builtins.float", 1.0, True),
        ("builtins.int", 1, True),
        ("builtins.int", 1.0, False),
        ("builtins.float", None, False),
        ("builtins.str", 1.0, False),
    ],
)
def test_direct_scalar_returned_type_matches_selected_typed_value(
    runtime_type: str,
    selected_value: int | float | None,
    admitted: bool,
) -> None:
    """A direct scalar path binds the returned owner type to its content-read value."""
    from types import SimpleNamespace

    from polisyos.core.contracts.foundry import MethodExecutionReturnedSlot
    from polisyos.foundry.methods.base import SlotType

    returned = MethodExecutionReturnedSlot(
        slot_id="value",
        declared_by_signature=True,
        declared_slot_type="SCALAR",
        declared_shape=(),
        returned="returned",
        runtime_type=runtime_type,
        runtime_shape=(),
        runtime_shape_status="captured",
        codec_status="json_scalar_supported",
        retention_status="selected_metric_output",
    )
    occurrence = SimpleNamespace(
        returned_slot_inventory_status="captured",
        returned_slot_inventory_limitation=None,
        returned_slots=[returned],
    )
    signature = SimpleNamespace(
        output_slots=[
            SimpleNamespace(
                name="value",
                slot_type=SlotType.SCALAR,
                shape=(),
                unit=None,
            )
        ]
    )

    selected_slot, limitation = _selected_returned_slot(
        occurrence=occurrence,
        signature=signature,
        output_slot_id="value",
        expected_value_path=(),
        selected_value=selected_value,
    )
    if admitted:
        assert selected_slot == returned
        assert limitation is None
    else:
        assert selected_slot is None
        assert limitation == "selected_method_scalar_return_not_fully_captured"


def test_voi_refuses_real_producer_13_method_observation_vector(
    public_method_metric_source: dict[str, Any],
    cas_store: ArtifactStore,
) -> None:
    """VOI admits the scalar 1.2 view and refuses a real producer-emitted 1.3 view."""
    from polisyos.core.artifacts import load_core_json_artifact
    from polisyos.scientist.methods.search.voi_scheduler import (
        _policy_evaluation_vector_source_chain_matches_store,
        _policy_runtime_source_concordance,
        _policy_runtime_vector_schema_supported,
    )
    from polisyos.scientist.nodes.builtins.decide.policy_runtime_metrics import (
        _budget_deficit_measurement,
        _policy_runtime_execution_metadata,
    )
    from polisyos.scientist.nodes.builtins.decide.policy_runtime_support import (
        persist_policy_evaluation_vector_to_store,
    )

    candidate_ref = public_method_metric_source["candidate"]
    candidate = load_core_json_artifact(cas_store, candidate_ref)
    candidate_id = candidate["candidate_id"]
    observation = public_method_metric_source["observation"]
    assert observation.source_status == "observed"
    assert observation.value == pytest.approx(1.0)

    invocation = _policy_runtime_execution_metadata(
        evaluation_attempt_id="attempt-voi-schema-boundary",
        effective_estimation_config={"n_bootstrap": 64},
    )
    metrics = {"gov_balance": 0.0}
    fiscal_measurement = _budget_deficit_measurement(metrics)
    scalar = PolicyEvaluationVector(
        candidate_id=candidate_id,
        metadata={
            "policy_runtime_invocation": invocation,
            "policy_runtime_fiscal_measurement": fiscal_measurement,
        },
    )
    scalar = scalar.with_score_source_results(
        {
            "objective_channels": {},
            "metric_units": {},
            "feasible": scalar.feasible,
            "blocking_reasons": list(scalar.blocking_reasons),
            "bootstrap": dict(invocation),
            "budget_deficit_objective_usable": fiscal_measurement["usable"],
            "budget_deficit_objective_value": fiscal_measurement["normalized_value"],
            **metrics,
        }
    )
    scalar_ref = persist_policy_evaluation_vector_to_store(
        cas_store, candidate_ref=candidate_ref, evaluation_vector=scalar
    )
    scalar_manifest = cas_store.get_manifest(scalar_ref)
    assert scalar_manifest.artifact_schema is not None
    assert scalar_manifest.artifact_schema.version == "1.2"
    assert _policy_runtime_source_concordance(scalar) is not None
    assert _policy_runtime_vector_schema_supported("1.2", scalar)
    assert _policy_evaluation_vector_source_chain_matches_store(
        cas_store, scalar_ref, candidate_ref, candidate_id
    )

    rich = PolicyEvaluationVector.model_validate(
        {
            **scalar.model_dump(mode="python"),
            "method_metric_observations": [observation],
        }
    )
    rich_ref = persist_policy_evaluation_vector_to_store(
        cas_store, candidate_ref=candidate_ref, evaluation_vector=rich
    )
    rich_manifest = cas_store.get_manifest(rich_ref)
    assert rich_manifest.artifact_schema is not None
    assert rich_manifest.artifact_schema.version == "1.3"
    assert rich_ref.artifact_id != scalar_ref.artifact_id
    assert load_core_json_artifact(cas_store, rich_ref)["method_metric_observations"]
    assert {item.role for item in rich_manifest.inputs} >= {
        "candidate",
        "method_metric_binding_set",
        "method_execution_bundle",
    }
    assert _policy_runtime_source_concordance(rich) is not None
    assert not _policy_runtime_vector_schema_supported("1.3", rich)
    assert not _policy_evaluation_vector_source_chain_matches_store(
        cas_store, rich_ref, candidate_ref, candidate_id
    )


def test_completed_ex_ante_rank_projection_replays_selected_source_and_refuses_swap(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Actual Foundry source plus test-double owner exercises only the C06 seam."""
    from polisyos.core.artifacts.manifest import ArtifactRef
    from polisyos.scientist.nodes.builtins.decide.policy_runtime_method_metrics import (
        recompute_completed_ex_ante_rank_projection,
    )

    artifacts = _exercise_public_execute_method_metric_source(
        tmp_path, monkeypatch, canonical_compile=True
    )
    basis = artifacts["projection"].basis
    candidate_ref = artifacts["candidate_ref"]
    projection = recompute_completed_ex_ante_rank_projection(
        artifacts["store"], basis=basis, candidate_ref=candidate_ref
    )
    assert projection.status == "selected", projection.limitations
    assert projection.authority_status == "candidate_only"
    assert projection.minimized_score == pytest.approx(-1.0)
    assert projection.maximizing_coordinate == pytest.approx(1.0)
    assert projection.comparison_contract_sha256

    changed = ArtifactRef.model_validate(
        {
            **candidate_ref.model_dump(mode="json"),
            "manifest_profile_sha256": "sha256:" + "f" * 64,
        }
    )
    wrong = recompute_completed_ex_ante_rank_projection(
        artifacts["store"], basis=basis, candidate_ref=changed
    )
    assert wrong.status != "selected"
    assert wrong.minimized_score is None
    assert wrong.maximizing_coordinate is None
    # Persist the same candidate bytes under a genuinely different selected
    # manifest profile. An artifact ID alone does not identify the selected source.
    store = artifacts["store"]
    manifest = store.get_manifest(candidate_ref)
    alternate = store.put_bytes(
        store.get_bytes(candidate_ref),
        PutOptions(
            kind=manifest.kind,
            media_type=manifest.media_type,
            schema=manifest.artifact_schema,
            producer=manifest.producer,
            env=manifest.env,
            inputs=[
                *manifest.inputs,
                input_ref_from_artifact_ref(candidate_ref, role="profile_variant_source"),
            ],
            canon=manifest.canon,
            governance=manifest.governance,
            tenant_context=manifest.tenant_context,
            same_input_closure=manifest.same_input_closure,
            authority=manifest.authority,
            warnings=manifest.warnings,
        ),
        return_selected_profile=True,
    )
    assert alternate.artifact_id == candidate_ref.artifact_id
    assert alternate.manifest_profile_sha256 != candidate_ref.manifest_profile_sha256
    selected_sibling = recompute_completed_ex_ante_rank_projection(
        store, basis=basis, candidate_ref=alternate
    )
    assert selected_sibling.status != "selected"
    assert selected_sibling.minimized_score is None
    missing = recompute_completed_ex_ante_rank_projection(
        artifacts["store"], basis=None, candidate_ref=candidate_ref
    )
    assert missing.status == "verification_missing"
    assert missing.comparison_contract_sha256 is None


def test_completed_reader_reselects_after_bounded_source_read(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An owner revoked during source CAS read cannot yield a selected basis."""
    artifacts = _exercise_public_execute_method_metric_source(tmp_path, monkeypatch)

    class Owner:
        calls = 0

        def resolve_completed_method_metric_selection(self, **kwargs):
            self.calls += 1
            return artifacts["completed_source"] if self.calls == 1 else None

    owner = Owner()
    read = read_completed_admitted_method_metric_projection(
        artifacts["store"],
        owner=owner,
        source_run_id=artifacts["work"].run_id,
        candidate_ref=artifacts["candidate_ref"],
        tenant_id="tenant-public-execute",
        cell_id="cell-public-execute",
    )
    assert read.status == "verification_missing"
    assert read.basis is None
    assert read.limitations == ("completed_method_metric_source_changed_during_read",)
    assert owner.calls == 2


def test_two_ex_ante_sources_require_same_complete_comparison_basis(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Real paired-array law; its completed-owner doubles establish only this unit seam."""
    from polisyos.scientist.nodes.builtins.decide.policy_runtime_method_metrics import (
        recompute_completed_ex_ante_rank_projection,
    )

    sources = [
        _exercise_public_execute_method_metric_source(
            tmp_path / name,
            monkeypatch,
            job_id=f"job-{name}",
            run_id=f"run-{name}",
            scenario_values=values,
            canonical_compile=True,
        )
        for name, values in (
            ("a", (11.0, 18.0, 44.0)),
            ("b", (12.0, 20.0, 44.0)),
        )
    ]
    projections = [
        recompute_completed_ex_ante_rank_projection(
            source["store"],
            basis=source["projection"].basis,
            candidate_ref=source["candidate_ref"],
        )
        for source in sources
    ]
    assert all(item.status == "selected" for item in projections)
    assert projections[0].comparison_contract_sha256 == projections[1].comparison_contract_sha256
    assert [item.maximizing_coordinate for item in projections] == pytest.approx([1.0, 2.0])


def test_ex_ante_rank_comparison_detects_changed_baseline(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An independently executed different baseline is not the same comparison basis."""
    from polisyos.scientist.nodes.builtins.decide.policy_runtime_method_metrics import (
        recompute_completed_ex_ante_rank_projection,
    )

    first = _exercise_public_execute_method_metric_source(
        tmp_path / "a",
        monkeypatch,
        job_id="job-baseline-a",
        run_id="run-baseline-a",
        canonical_compile=True,
    )
    second = _exercise_public_execute_method_metric_source(
        tmp_path / "b",
        monkeypatch,
        job_id="job-baseline-b",
        run_id="run-baseline-b",
        # Mean0 is exactly representable; mean2/3 belongs to the law's honest precision refusal.
        baseline_values=(10.0, 20.0, 43.0),
        canonical_compile=True,
    )
    a, b = (
        recompute_completed_ex_ante_rank_projection(
            source["store"],
            basis=source["projection"].basis,
            candidate_ref=source["candidate_ref"],
        )
        for source in (first, second)
    )
    assert a.status == b.status == "selected"
    assert (a.maximizing_coordinate, b.maximizing_coordinate) == (1.0, 0.0)
    assert a.comparison_contract_sha256 != b.comparison_contract_sha256


def test_ex_ante_rank_refuses_actual_snapshot_different_from_candidate(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A real Foundry execution on B cannot be ranked as candidate A's source."""
    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.scientist.nodes.builtins.decide.policy_runtime_method_metrics import (
        recompute_completed_ex_ante_rank_projection,
    )

    store = FileSystemCAS(tmp_path / "shared-cas")
    b = _exercise_public_execute_method_metric_source(
        tmp_path / "b",
        monkeypatch,
        artifact_store=store,
        scenario_values=(12.0, 20.0, 44.0),
        prepare_only=True,
        canonical_compile=True,
    )
    mismatched = _exercise_public_execute_method_metric_source(
        tmp_path / "a",
        monkeypatch,
        artifact_store=store,
        execution_data_snapshot_ref=b["data_snapshot_ref"],
        expected_executed_mean=2.0,
        canonical_compile=True,
    )
    # The seam uses the existing test-double owner; it establishes a real
    # Foundry source join, not an actual completed Runtime-job receipt.
    assert mismatched["projection"].status == "selected"
    result = recompute_completed_ex_ante_rank_projection(
        store,
        basis=mismatched["projection"].basis,
        candidate_ref=mismatched["candidate_ref"],
    )
    assert result.status == "verification_missing"
    assert result.limitations == ("completed_ex_ante_source_inputs_not_comparable",)
    assert result.maximizing_coordinate is None


def test_ex_ante_rank_refuses_body_to_selected_snapshot_edge_mismatch(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A candidate declaring A cannot acquire B by changing only its manifest edge."""
    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.scientist.nodes.builtins.decide.policy_runtime_method_metrics import (
        recompute_completed_ex_ante_rank_projection,
    )

    store = FileSystemCAS(tmp_path / "shared-cas")
    b = _exercise_public_execute_method_metric_source(
        tmp_path / "b",
        monkeypatch,
        artifact_store=store,
        scenario_values=(12.0, 20.0, 44.0),
        prepare_only=True,
        canonical_compile=True,
    )
    mismatch = _exercise_public_execute_method_metric_source(
        tmp_path / "a",
        monkeypatch,
        artifact_store=store,
        candidate_data_snapshot_edge_ref=b["data_snapshot_ref"],
        execution_data_snapshot_ref=b["data_snapshot_ref"],
        expected_executed_mean=2.0,
        canonical_compile=True,
    )
    assert mismatch["projection"].status == "selected"
    result = recompute_completed_ex_ante_rank_projection(
        store, basis=mismatch["projection"].basis, candidate_ref=mismatch["candidate_ref"]
    )
    assert result.status == "verification_missing"
    assert result.limitations == ("completed_ex_ante_candidate_model_source_mismatch",)
    assert result.maximizing_coordinate is None


def test_candidate_comparison_reselects_each_source_before_return(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test-double scope exercises the reselect seam, never Runtime authority."""
    from types import SimpleNamespace

    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.core.contracts.runtime import CompletedExAnteCandidateSource
    from polisyos.scientist.methods.search.pareto_registry import ParetoRegistry

    store = FileSystemCAS(tmp_path / "shared-cas")
    results = [
        _exercise_public_execute_method_metric_source(
            tmp_path / name,
            monkeypatch,
            artifact_store=store,
            job_id=f"job-{name}",
            run_id=f"run-{name}",
            scenario_values=values,
            canonical_compile=True,
        )
        for name, values in (("a", (11.0, 18.0, 44.0)), ("b", (12.0, 20.0, 44.0)))
    ]
    source_rows = tuple(
        CompletedExAnteCandidateSource(
            source_run_id=item["work"].run_id, candidate_ref=item["candidate_ref"]
        )
        for item in results
    )

    class ScopedOwnerDouble:
        def __init__(self, revoke_during_final_read: bool) -> None:
            self.calls = 0
            self.revoke_during_final_read = revoke_during_final_read

        def resolve_completed_method_metric_selection(
            self, *, source_run_id, candidate_ref, tenant_id, cell_id
        ):
            assert (tenant_id, cell_id) == ("tenant-public-execute", "cell-public-execute")
            self.calls += 1
            # Two owner lookups per source in initial replay; revoke on the
            # post-read lookup of source A during the final re-selection.
            if self.revoke_during_final_read and self.calls >= 6:
                return None
            for item in results:
                if item["work"].run_id == source_run_id and item["candidate_ref"] == candidate_ref:
                    return item["completed_source"]
            return None

    def compare(owner):
        context = SimpleNamespace(
            store=store,
            method_metric_selection_owner=owner,
            run=SimpleNamespace(tenant_id="tenant-public-execute", cell_id="cell-public-execute"),
        )
        return ParetoRegistry.rank_completed_ex_ante_candidates(ctx=context, sources=source_rows)

    positive = compare(ScopedOwnerDouble(False))
    assert positive.status == "complete", positive.limitations
    assert positive.authority_status == "candidate_only"
    assert [item.maximizing_coordinate for item in positive.observations] == pytest.approx(
        [1.0, 2.0]
    )
    revoked = compare(ScopedOwnerDouble(True))
    assert revoked.status == "verification_missing"
    assert revoked.frontier_candidate_hashes == ()


def test_ex_ante_rank_comparison_detects_actual_seed_drift(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Even an unchanged observed mean cannot erase the actual execution seed."""
    from polisyos.scientist.nodes.builtins.decide.policy_runtime_method_metrics import (
        recompute_completed_ex_ante_rank_projection,
    )

    first = _exercise_public_execute_method_metric_source(
        tmp_path / "a",
        monkeypatch,
        job_id="job-seed-a",
        run_id="run-seed-a",
        execution_seed=41,
        canonical_compile=True,
    )
    second = _exercise_public_execute_method_metric_source(
        tmp_path / "b",
        monkeypatch,
        job_id="job-seed-b",
        run_id="run-seed-b",
        execution_seed=42,
        canonical_compile=True,
    )
    a, b = (
        recompute_completed_ex_ante_rank_projection(
            source["store"], basis=source["projection"].basis, candidate_ref=source["candidate_ref"]
        )
        for source in (first, second)
    )
    assert a.status == b.status == "selected"
    assert a.maximizing_coordinate == b.maximizing_coordinate == pytest.approx(1.0)
    assert a.comparison_contract_sha256 != b.comparison_contract_sha256


def test_actual_compiler_rank_comparison_accepts_identical_sources(tmp_path, monkeypatch):
    """A/A is established before testing the bounded A/B model-input contrast."""
    from polisyos.scientist.nodes.builtins.decide.policy_runtime_method_metrics import (
        recompute_completed_ex_ante_rank_projection,
    )

    sources = [
        _exercise_public_execute_method_metric_source(
            tmp_path / name,
            monkeypatch,
            run_id=f"run-{name}",
            job_id=f"job-{name}",
            canonical_compile=True,
        )
        for name in ("same-a", "same-b")
    ]
    ranks = [
        recompute_completed_ex_ante_rank_projection(
            item["store"], basis=item["projection"].basis, candidate_ref=item["candidate_ref"]
        )
        for item in sources
    ]
    assert all(item.status == "selected" for item in ranks), ranks
    assert [item.maximizing_coordinate for item in ranks] == pytest.approx([1.0, 1.0])
    assert ranks[0].comparison_contract_sha256 == ranks[1].comparison_contract_sha256


def test_actual_compiler_comparison_reconciles_whole_operator_closure(tmp_path, monkeypatch):
    """Real compiled models admit once; auxiliary/edge/order/profile edits fail closed."""
    from polisyos.core.artifacts import validate_core_model_json_artifact
    from polisyos.core.artifacts.registry import RegistryBundlePayload
    from polisyos.core.contracts.foundry import (
        ExecPlan,
        MethodExecutionBundle,
        MethodMetricBindingSet,
        ProgramGraph,
    )
    from polisyos.ir.trinity import TrinityBundle
    from polisyos.scientist.nodes.builtins.decide.policy_runtime_method_metrics import (
        _compiled_method_comparison_graph,
        _ProjectionReadBudget,
        _selected_ref,
    )

    source = _exercise_public_execute_method_metric_source(
        tmp_path, monkeypatch, canonical_compile=True
    )
    store = source["store"]
    bundle = validate_core_model_json_artifact(MethodExecutionBundle, store, source["bundle_ref"])
    bindings = validate_core_model_json_artifact(
        MethodMetricBindingSet, store, source["binding_ref"]
    )
    graph = validate_core_model_json_artifact(ProgramGraph, store, bundle.program_graph_ref)
    plan = validate_core_model_json_artifact(ExecPlan, store, bundle.exec_plan_ref)
    manifest = store.get_manifest(bundle.program_graph_ref)
    policy = validate_core_model_json_artifact(TrinityBundle, store, bindings.policy_ref)
    registry = validate_core_model_json_artifact(
        RegistryBundlePayload, store, bindings.registry_bundle_ref
    )
    methods = {node.node_id for node in graph.nodes if node.node_kind == "method"}
    assert methods == {"ex_ante_node"}
    ops = {
        node.op.op_kind: node.node_id
        for node in graph.nodes
        if node.node_kind == "op" and node.op is not None
    }
    assert {"merge_state", "check_constraints"} <= ops.keys()
    edges = {(edge.src, edge.dst, edge.relation) for edge in graph.edges}
    assert ("ex_ante_node", ops["merge_state"], "depends_on") in edges
    assert (ops["merge_state"], ops["check_constraints"], "depends_on") in edges
    assert set(plan.order) == {node.node_id for node in graph.nodes}

    def replay(current_graph=graph, current_plan=plan, current_manifest=manifest):
        return _compiled_method_comparison_graph(
            store,
            graph=current_graph,
            graph_manifest=current_manifest,
            plan=current_plan,
            policy=policy,
            policy_ref=_selected_ref(bindings.policy_ref, kind="ir.trinity_bundle"),
            registry_bundle=registry,
            registry_bundle_ref=_selected_ref(
                bindings.registry_bundle_ref, kind="core.registry_bundle"
            ),
            registry_bundle_manifest=store.get_manifest(bindings.registry_bundle_ref),
            read_budget=_ProjectionReadBudget(),
        )

    admitted = replay()
    assert admitted is not None
    assert admitted["graph"]["nodes"] == graph.model_dump(mode="json")["nodes"]
    assert admitted["plan"]["order"] == plan.order
    assert "constraints" in admitted["lowering"]
    check = next(node for node in graph.nodes if node.node_id == ops["check_constraints"])
    changed_check = check.model_copy(
        update={"op": check.op.model_copy(update={"params": {"constraint_ids": ["invented"]}})}
    )
    variants = [
        (
            graph.model_copy(
                update={
                    "nodes": [node for node in graph.nodes if node.node_id != ops["merge_state"]]
                }
            ),
            plan,
            manifest,
        ),
        (
            graph.model_copy(
                update={
                    "nodes": [
                        changed_check if node.node_id == check.node_id else node
                        for node in graph.nodes
                    ]
                }
            ),
            plan,
            manifest,
        ),
        (graph.model_copy(update={"edges": graph.edges[:-1]}), plan, manifest),
        (graph, plan.model_copy(update={"order": list(reversed(plan.order))}), manifest),
        (graph, plan.model_copy(update={"order": plan.order[:-1]}), manifest),
        (
            graph,
            plan,
            manifest.model_copy(
                update={
                    "inputs": [
                        edge for edge in manifest.inputs if edge.role != "execution_plan_source"
                    ]
                }
            ),
        ),
        (
            graph,
            plan,
            manifest.model_copy(
                update={
                    "inputs": [
                        edge.model_copy(update={"manifest_profile_sha256": "sha256:" + "f" * 64})
                        if edge.role == "execution_plan_source"
                        else edge
                        for edge in manifest.inputs
                    ]
                }
            ),
        ),
    ]
    for changed_graph, changed_plan, changed_manifest in variants:
        with pytest.raises((ValueError, OSError)):
            replay(changed_graph, changed_plan, changed_manifest)
    from polisyos.core.artifacts.manifest import ArtifactRef
    from polisyos.core.contracts.execution_plan import ExecutionPlan
    from polisyos.core.contracts.foundry import LoweredConstraint, LoweredIR, LoweredIRRef
    from polisyos.foundry.compile import replay_method_program_graph
    from polisyos.ir.kernel import ConstraintRegistry

    lowered = validate_core_model_json_artifact(LoweredIR, store, graph.lowered_ir_ref)
    constraint_registry = validate_core_model_json_artifact(
        ConstraintRegistry, store, registry.constraint_registry
    )
    source_edge = next(edge for edge in manifest.inputs if edge.role == "execution_plan_source")
    method_plan = validate_core_model_json_artifact(
        ExecutionPlan,
        store,
        ArtifactRef(
            artifact_id=source_edge.artifact_id,
            kind="scientist.execution_plan",
            media_type="application/json",
            manifest_profile_sha256=source_edge.manifest_profile_sha256,
        ),
    )
    for lowering_update in (
        {"constraint_mode": "invented"},
        {"environment_config": {"invented": True}},
        {"parameter_specs": [{"invented": True}]},
        {
            "constraints": [
                LoweredConstraint(
                    constraint_id="invented",
                    severity="hard",
                    slot_id="baseline",
                    operator=">=",
                    expected="9",
                )
            ]
        },
    ):
        with pytest.raises(ValueError, match="method_graph_replay_lowering_mismatch"):
            replay_method_program_graph(
                policy=policy,
                policy_ref=bindings.policy_ref,
                lowered_ir=lowered.model_copy(update=lowering_update),
                lowered_ir_ref=LoweredIRRef.model_validate(
                    graph.lowered_ir_ref.model_dump(mode="python")
                ),
                method_plan=method_plan,
                constraint_registry=constraint_registry,
            )
    second_method = next(node for node in graph.nodes if node.node_kind == "method").model_copy(
        update={"node_id": "other_method"}
    )
    assert replay(graph.model_copy(update={"nodes": [*graph.nodes, second_method]})) is None
