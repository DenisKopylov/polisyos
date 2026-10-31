"""Selected, predictive-only replay of Foundry state over a historical prefix.

The observed slots are a model simulation, not empirical calibration or causal
validation. Fresh reads reconcile the selected source, materialization, execution
basis and state chain before returning the trajectory.
"""

from __future__ import annotations

import math
from copy import deepcopy
from dataclasses import fields, is_dataclass, replace
from typing import TYPE_CHECKING, Any, ClassVar, Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.core import artifacts as cas
from polisyos.core import canon, registry
from polisyos.core.contracts import (
    DataSnapshot,
    DerivedArtifact,
    ExecuteRequest,
    ExecuteResult,
    FoundryInputBindingRule,
    FoundryInputBindings,
    FoundryInputBindingsRef,
    SimulationResultRef,
    StateSnapshotRef,
    data_snapshot_manifest_inputs_match,
)
from polisyos.foundry.data_plane import prepare_input_bindings
from polisyos.foundry.execute import (
    admit_execution_source,
    apply_state_delta,
    get_state_path,
    load_state_snapshot,
    put_state_snapshot,
)
from polisyos.ir.trinity import load_trinity_bundle_artifact, persist_trinity_bundle_artifact
from polisyos.scientist.methods.backtesting.masking import OutcomeMasker
from polisyos.scientist.policy_design.schema import PolicyCandidateSchema

if TYPE_CHECKING:
    from polisyos.ir.analytics.backtest import BacktestReport
    from polisyos.ir.registry.refs import ArtifactRefModel
    from polisyos.scientist.methods.backtesting.plan import HistoricalValidationPlan
    from polisyos.scientist.orchestration.engine.context import ExecutionContext

PROFILE_KEY = "backtest_native_forecast"
REQUEST_KEY = "backtest_native_forecast_request_ref"
FORECAST_KEY = "backtest_native_forecast_ref"
type NativeLimitation = Literal[
    "native_external_source_provenance_not_established",
    "native_model_provenance_not_established",
    "native_producer_authenticity_not_established",
    "native_temporal_mapping_not_established",
    "native_observation_independence_not_established",
    "native_stochastic_continuity_not_established",
    "native_empirical_calibration_not_established",
    "native_causal_validity_not_established",
]
_SCOPE_LIMITATIONS: tuple[NativeLimitation, ...] = (
    "native_external_source_provenance_not_established",
    "native_model_provenance_not_established",
    "native_producer_authenticity_not_established",
    "native_temporal_mapping_not_established",
    "native_observation_independence_not_established",
    "native_stochastic_continuity_not_established",
    "native_empirical_calibration_not_established",
    "native_causal_validity_not_established",
)


class NativeForecastTarget(BaseModel):
    """A requested observable and its registry-owned state slot and unit."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    metric: str = Field(min_length=1)
    slot_id: str = Field(min_length=1)
    unit_id: str = Field(min_length=1)
    reduction: Literal["mean", "sum", "identity"]


class NativeForecastProfile(BaseModel):
    """Ordered model-simulation coordinates and permitted history columns."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    purpose: Literal["predictive_simulation"]
    origin: str = Field(min_length=1)
    time_index: list[str] = Field(min_length=1)
    history_columns: list[str] = Field(min_length=1)
    targets: list[NativeForecastTarget] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_axes(self) -> NativeForecastProfile:
        """Reject ambiguous coordinates or duplicate semantic axes."""
        for values in (self.time_index, self.history_columns, [x.metric for x in self.targets]):
            if any(not value for value in values) or len(set(values)) != len(values):
                raise ValueError("native forecast axes and target metrics must be unique")
        if self.origin != self.time_index[0]:
            raise ValueError("native forecast origin must be the first future coordinate")
        return self


class NativeForecastRequest(BaseModel):
    """Immutable source, model, prefix and actual execution selection."""

    ARTIFACT_KIND: ClassVar[str] = "scientist.backtest.native_forecast_request"
    ARTIFACT_MEDIA_TYPE: ClassVar[str] = "application/json"
    ARTIFACT_SCHEMA_NAME: ClassVar[str] = "polisyos.scientist.backtesting.NativeForecastRequest"
    ARTIFACT_SCHEMA_VERSION: ClassVar[str] = "1.0"
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"]
    randomness_scope: Literal["same_seed_submitted_each_step"]
    limitations: list[NativeLimitation]
    profile: NativeForecastProfile
    source_snapshot_ref: cas.ArtifactRef
    source_data_ref: cas.ArtifactRef
    original_trinity_ref: cas.ArtifactRef
    candidate_ref: cas.ArtifactRef
    registry_ref: cas.ArtifactRef
    data_snapshot_ref: cas.ArtifactRef
    trinity_ref: cas.ArtifactRef
    cutoff: int = Field(strict=True, gt=0)
    row_ids: list[str]
    history_time_index: list[str]
    rules: list[FoundryInputBindingRule] = Field(min_length=1)
    run_id: str = Field(min_length=1)
    seed: int = Field(strict=True, ge=0)

    @model_validator(mode="after")
    def validate_limitations(self) -> NativeForecastRequest:
        """Keep all unestablished claims explicit in the persisted request."""
        if tuple(self.limitations) != _SCOPE_LIMITATIONS:
            raise ValueError("native replay requires the complete declared limitations")
        return self


class NativeForecastTrajectory(BaseModel):
    """Selected native results and recomputable state observations."""

    ARTIFACT_KIND: ClassVar[str] = "scientist.backtest.native_forecast"
    ARTIFACT_MEDIA_TYPE: ClassVar[str] = "application/json"
    ARTIFACT_SCHEMA_NAME: ClassVar[str] = "polisyos.scientist.backtesting.NativeForecastTrajectory"
    ARTIFACT_SCHEMA_VERSION: ClassVar[str] = "1.0"
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"]
    request_ref: cas.ArtifactRef
    submitted_execution: ExecuteRequest
    submitted_request_fields_set: tuple[str, ...]
    submitted_exec_config_fields_set: tuple[str, ...]
    execution_bindings_refs: list[FoundryInputBindingsRef]
    simulation_refs: list[SimulationResultRef]
    state_snapshot_refs: list[StateSnapshotRef]
    values: dict[str, list[float]]


class _NativeReplicaProjection(BaseModel):
    """Describe a complete cohort's arithmetic projection without interval claims."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    method: Literal["arithmetic_mean_complete_cohort_v1"]
    plan_ref: cas.ArtifactRef
    forecast_refs: list[cas.ArtifactRef] = Field(min_length=2)


_NATIVE_PLAN_KIND = "scientist.backtest.historical_validation_plan"
_NATIVE_PLAN_SCHEMA = "polisyos.scientist.backtesting.HistoricalValidationPlan"


def _selected(ref: cas.ArtifactRef) -> cas.ArtifactRef:
    if ref.manifest_profile_sha256 is None:
        raise ValueError("native replay requires selected artifact profiles")
    return ref


def _edge(
    store: cas.ArtifactStore, parent: cas.ArtifactRef, child: cas.ArtifactRef, role: str
) -> None:
    _selected(parent)
    _selected(child)
    expected = cas.input_ref_from_artifact_ref(child, role=role)
    matches = [item for item in store.get_manifest(parent).inputs if item.role == role]
    if matches != [expected]:
        raise ValueError(f"native replay exact lineage mismatch: {role}")
    store.get_bytes(child)


def _edge_ref(
    store: cas.ArtifactStore, parent: cas.ArtifactRef, role: str, kind: str
) -> cas.ArtifactRef:
    edges = [item for item in store.get_manifest(_selected(parent)).inputs if item.role == role]
    if len(edges) != 1:
        raise ValueError(f"native replay selected lineage missing: {role}")
    edge = edges[0]
    profile = edge.manifest_profile_sha256
    if profile is None:
        raise ValueError(f"native replay selected lineage missing: {role}")
    manifest = cas.resolve_manifest_by_profile(store, edge.artifact_id, profile)
    if manifest.kind != kind:
        raise ValueError(f"native replay lineage kind mismatch: {role}")
    return cas.ArtifactRef(
        artifact_id=edge.artifact_id,
        kind=manifest.kind,
        media_type=manifest.media_type,
        manifest_profile_sha256=profile,
    )


def _put(
    store: cas.ArtifactStore,
    payload: BaseModel | dict[str, Any],
    *,
    kind: str,
    schema: str,
    version: str,
    inputs: list[tuple[cas.ArtifactRef, str]],
) -> cas.ArtifactRef:
    return _selected(
        store.put_json(
            payload,
            cas.PutOptions(
                kind=kind,
                media_type="application/json",
                schema=cas.SchemaInfo(name=schema, version=version),
                inputs=[
                    cas.input_ref_from_artifact_ref(_selected(ref), role=role)
                    for ref, role in inputs
                ],
            ),
            canon_spec=canon.CanonSpec(forbid_floats=False),
            return_selected_profile=True,
        )
    )


def _persist_native_plan(
    store: cas.ArtifactStore, plan: HistoricalValidationPlan
) -> cas.ArtifactRef:
    """Retain the actual typed request that fixes the cohort denominator."""
    state = plan.scientist_state
    if not isinstance(state, dict) or not isinstance(state.get("inputs"), dict):
        raise ValueError("native replay plan inputs are missing")
    inputs = state["inputs"]
    return _put(
        store,
        plan,
        kind=_NATIVE_PLAN_KIND,
        schema=_NATIVE_PLAN_SCHEMA,
        version="1.0",
        inputs=[
            (cas.ArtifactRef.model_validate(inputs[key]), role)
            for key, role in (
                ("data_snapshot_ref", "source_snapshot"),
                ("trinity_bundle_ref", "original_trinity"),
                ("registry_bundle_ref", "registry"),
            )
        ],
    )


def _mean_native_values(values: list[dict[str, list[float]]]) -> dict[str, list[float]]:
    """Recompute a pointwise mean only over a complete, aligned selected cohort."""
    if not values:
        raise ValueError("native replica projection has no trajectories")
    metrics = set(values[0])
    if not metrics or any(set(item) != metrics for item in values):
        raise ValueError("native replica projection metric axes differ")
    result: dict[str, list[float]] = {}
    for metric in sorted(metrics):
        size = len(values[0][metric])
        if not size or any(len(item[metric]) != size for item in values):
            raise ValueError("native replica projection time axes differ")
        rows = [item[metric] for item in values]
        if any(not math.isfinite(value) for row in rows for value in row):
            raise ValueError("native replica projection contains nonfinite values")
        result[metric] = [
            math.fsum(row[index] / len(rows) for row in rows) for index in range(size)
        ]
    return result


def _require_shared_native_basis(requests: list[NativeForecastRequest]) -> None:
    """Require exact shared selections while allowing each run and seed to differ."""
    if not requests:
        raise ValueError("native replica projection has no requests")
    first = requests[0].model_dump(mode="json", exclude={"run_id", "seed"})
    if any(
        request.model_dump(mode="json", exclude={"run_id", "seed"}) != first
        for request in requests[1:]
    ):
        raise ValueError("native replica shared execution basis differs")


def _require_shared_native_execution(forecasts: list[NativeForecastTrajectory]) -> None:
    """Allow only the per-replica binding and seed to vary in submitted execution."""
    if not forecasts:
        raise ValueError("native replica projection has no executions")

    def basis(
        forecast: NativeForecastTrajectory,
    ) -> tuple[dict[str, Any], tuple[str, ...], tuple[str, ...]]:
        request = forecast.submitted_execution.model_dump(
            mode="json", exclude={"input_bindings_ref"}
        )
        request["exec_config"].pop("seed")
        return (
            request,
            forecast.submitted_request_fields_set,
            forecast.submitted_exec_config_fields_set,
        )

    first = basis(forecasts[0])
    if any(basis(forecast) != first for forecast in forecasts[1:]):
        raise ValueError("native replica submitted execution differs across cohort")


def _project_source(
    source: dict[str, Any], profile: NativeForecastProfile, cutoff: int
) -> dict[str, Any]:
    times, ids = source.get("time_index"), source.get("row_ids")
    if (
        not isinstance(times, list)
        or not isinstance(ids, list)
        or any(not isinstance(v, str) or not v for v in [*times, *ids])
        or len(times) != len(ids)
        or len(set(times)) != len(times)
        or len(set(ids)) != len(ids)
        or cutoff <= 0
        or times[cutoff : cutoff + len(profile.time_index)] != profile.time_index
    ):
        raise ValueError("native replay source row/time axis or cutoff mismatch")
    projected: dict[str, Any] = {"time_index": times[:cutoff], "row_ids": ids[:cutoff]}
    for column in profile.history_columns:
        if column in projected:
            raise ValueError("native replay history column conflicts with an identity axis")
        values = source.get(column)
        if not isinstance(values, list) or len(values) != len(times):
            raise ValueError(f"native replay history column is not time-aligned: {column}")
        prefix = values[:cutoff]
        if any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in prefix):
            raise ValueError(f"native replay history column is not numeric: {column}")
        if not np.all(np.isfinite(np.asarray(prefix, dtype=float))):
            raise ValueError(f"native replay history column is nonfinite: {column}")
        projected[column] = prefix
    return projected


def _source_holdout(
    source: dict[str, Any], profile: NativeForecastProfile, cutoff: int
) -> dict[str, list[float]]:
    """Resolve declared target observations at the exact withheld coordinates."""
    times = source.get("time_index")
    if not isinstance(times, list):
        raise ValueError("native replay source time axis is missing")
    horizon = len(profile.time_index)
    result: dict[str, list[float]] = {}
    for target in profile.targets:
        values = source.get(target.metric)
        if not isinstance(values, list) or len(values) != len(times):
            raise ValueError(f"native replay target observations are not aligned: {target.metric}")
        holdout = values[cutoff : cutoff + horizon]
        if len(holdout) != horizon or any(
            isinstance(value, bool) or not isinstance(value, (int, float)) for value in holdout
        ):
            raise ValueError(f"native replay target observations are not numeric: {target.metric}")
        numeric = [float(value) for value in holdout]
        if not all(np.isfinite(value) for value in numeric):
            raise ValueError(f"native replay target observations are nonfinite: {target.metric}")
        result[target.metric] = numeric
    return result


def _check_rules(
    rules: list[FoundryInputBindingRule], profile: NativeForecastProfile, cutoff: int
) -> None:
    if not rules:
        raise ValueError("native replay requires explicit historical binding rules")
    for rule in rules:
        tokens = rule.source_path.split(".")
        if (
            len(tokens) != 2
            or tokens[0] not in profile.history_columns
            or not tokens[1].isdigit()
            or int(tokens[1]) >= cutoff
            or not rule.required
            or rule.default_value is not None
            or rule.transforms
        ):
            raise ValueError("native replay binding is outside the admitted historical prefix")


def _check_targets(store: cas.ArtifactStore, request: NativeForecastRequest) -> Any:
    bundle = registry.load_registry_bundle_content(store, _selected(request.registry_ref))
    slots_owner: Any = bundle.slot_registry
    slots: dict[str, Any] = slots_owner.slots
    for target in request.profile.targets:
        slot = slots.get(target.slot_id)
        if slot is None or not slot.state_path or slot.unit.unit_id != target.unit_id:
            raise ValueError(f"native replay target/slot/unit mismatch: {target.metric}")
    return bundle


def _check_request(store: cas.ArtifactStore, request: NativeForecastRequest) -> None:
    for ref in (
        request.source_snapshot_ref,
        request.source_data_ref,
        request.original_trinity_ref,
        request.candidate_ref,
        request.registry_ref,
        request.data_snapshot_ref,
        request.trinity_ref,
    ):
        _selected(ref)
    source = cas.validate_core_model_json_artifact(DataSnapshot, store, request.source_snapshot_ref)
    source_manifest = store.get_manifest(request.source_snapshot_ref)
    if source.data_ref != request.source_data_ref or not data_snapshot_manifest_inputs_match(
        source,
        source_manifest.inputs,
        schema_version=source_manifest.artifact_schema.version
        if source_manifest.artifact_schema
        else None,
    ):
        raise ValueError("native replay source snapshot lineage mismatch")
    source_data = cas.load_core_json_artifact(store, request.source_data_ref)
    if not isinstance(source_data, dict):
        raise ValueError("native replay source data must be an object")
    projected = _project_source(source_data, request.profile, request.cutoff)
    if (
        request.row_ids != projected["row_ids"]
        or request.history_time_index != projected["time_index"]
    ):
        raise ValueError("native replay request prefix identities differ from source")
    _check_rules(request.rules, request.profile, request.cutoff)
    original = load_trinity_bundle_artifact(
        cas.ensure_ir_artifact_store(store), request.original_trinity_ref
    )
    candidate = cas.validate_core_model_json_artifact(
        PolicyCandidateSchema, store, request.candidate_ref
    )
    _edge(store, request.original_trinity_ref, request.candidate_ref, "policy_candidate")
    _edge(store, request.candidate_ref, request.source_snapshot_ref, "world_model_data_snapshot")
    _edge(store, request.candidate_ref, request.registry_ref, "world_model_registry")
    if candidate.trinity_bundle.model_dump(mode="json") != original.model_dump(mode="json"):
        raise ValueError("native replay candidate differs from original Trinity")
    if (
        original.model_spec.data_snapshot_ref != str(request.source_snapshot_ref.artifact_id)
        or original.model_spec.registry_bundle_ref != str(request.registry_ref.artifact_id)
        or original.model_spec.agent_config.network_graph_ref
        or any(param.time_series_ref for param in original.model_spec.environment_config.params)
    ):
        raise ValueError("native replay original model source/registry/dependencies mismatch")
    masked = cas.validate_core_model_json_artifact(DataSnapshot, store, request.data_snapshot_ref)
    _edge(store, request.data_snapshot_ref, masked.data_ref, "data_ref")
    _edge(store, masked.data_ref, request.source_data_ref, "source_data")
    if cas.load_core_json_artifact(store, masked.data_ref) != projected:
        raise ValueError("native replay persisted masked prefix differs from source")
    derived = load_trinity_bundle_artifact(cas.ensure_ir_artifact_store(store), request.trinity_ref)
    expected_model = original.model_spec.model_copy(
        update={"data_snapshot_ref": str(request.data_snapshot_ref.artifact_id)}
    )
    if derived.model_dump(mode="json") != original.model_copy(
        update={"model_spec": expected_model}
    ).model_dump(mode="json"):
        raise ValueError("native replay derived Trinity differs from original model and prefix")
    _edge(store, request.trinity_ref, request.original_trinity_ref, "original_trinity")
    _edge(store, request.trinity_ref, request.data_snapshot_ref, "masked_snapshot")
    _edge(store, request.trinity_ref, request.candidate_ref, "policy_candidate")
    _check_targets(store, request)


def prepare_native_replay(
    store: cas.ArtifactStore,
    plan: HistoricalValidationPlan,
    historical_data: dict[str, Any],
    *,
    run_id: str,
    seed: int,
) -> dict[str, Any]:
    """Create a selected source-prefix and derived Trinity before workflow execution."""
    state = deepcopy(plan.scientist_state)
    if not isinstance(state, dict) or set(state) - {"run_id", "inputs", "params"}:
        raise ValueError("native replay refuses preexisting workflow state")
    params, inputs = state.get("params"), state.get("inputs")
    if not isinstance(params, dict) or not isinstance(inputs, dict):
        raise ValueError("native replay requires Scientist inputs and params")
    if set(params) - {
        "workflow_id",
        "foundry_input_binding_rules",
        PROFILE_KEY,
        "random_seed",
        "n_simulation_runs",
    }:
        raise ValueError("native replay refuses unscoped Scientist parameters")
    if set(inputs) != {"data_snapshot_ref", "trinity_bundle_ref", "registry_bundle_ref"}:
        raise ValueError("native replay requires exactly source, Trinity and registry inputs")
    if params.get("workflow_id", "scientist_default") != "scientist_default":
        raise ValueError("native replay requires the default Scientist workflow")
    if plan.masking_strategy.value not in {"drop_post", "truncate"}:
        raise ValueError("native replay requires a finite historical prefix")
    profile = NativeForecastProfile.model_validate(params[PROFILE_KEY])
    if set(target.metric for target in profile.targets) != set(plan.target_metrics):
        raise ValueError("native replay target metrics differ from plan")
    if set(plan.target_metrics) != set(plan.ground_truth_outcomes):
        raise ValueError("native replay outcomes differ from declared target metrics")
    if any(
        len(plan.ground_truth_outcomes[target.metric]) != len(profile.time_index)
        for target in profile.targets
    ):
        raise ValueError("native replay forecast horizon differs from outcomes")
    cutoff = OutcomeMasker._resolve_cutoff(historical_data, plan)
    if cutoff is None or (plan.intervention_date and profile.origin != plan.intervention_date):
        raise ValueError("native replay requires a consistent cutoff and forecast origin")
    projected = _project_source(historical_data, profile, cutoff)
    if _source_holdout(historical_data, profile, cutoff) != plan.ground_truth_outcomes:
        raise ValueError("native replay supplied outcomes differ from selected source holdout")
    raw_rules = params.get("foundry_input_binding_rules")
    if not isinstance(raw_rules, list):
        raise ValueError("native replay requires explicit binding rules")
    rules = [FoundryInputBindingRule.model_validate(item) for item in raw_rules]
    _check_rules(rules, profile, cutoff)
    source_ref = _selected(cas.ArtifactRef.model_validate(inputs["data_snapshot_ref"]))
    source = cas.validate_core_model_json_artifact(DataSnapshot, store, source_ref)
    source_data_ref = _selected(source.data_ref)
    if not plan.historical_data_ref or plan.historical_data_ref != str(source_data_ref.artifact_id):
        raise ValueError("native replay requires the selected historical source data")
    if cas.load_core_json_artifact(store, source_data_ref) != historical_data:
        raise ValueError("native replay historical source bytes differ from plan")
    original_ref = _selected(cas.ArtifactRef.model_validate(inputs["trinity_bundle_ref"]))
    registry_ref = _selected(cas.ArtifactRef.model_validate(inputs["registry_bundle_ref"]))
    candidate_ref = _edge_ref(
        store, original_ref, "policy_candidate", "scientist.policy_design.candidate"
    )
    original = load_trinity_bundle_artifact(cas.ensure_ir_artifact_store(store), original_ref)
    data_ref = _put(
        store,
        projected,
        kind="scientist.backtest.masked_historical_view",
        schema="polisyos.scientist.backtesting.MaskedHistoricalView",
        version="1.0",
        inputs=[(source_data_ref, "source_data")],
    )
    snapshot_ref = _put(
        store,
        DataSnapshot(data_ref=data_ref),
        kind=DataSnapshot.ARTIFACT_KIND,
        schema=DataSnapshot.ARTIFACT_SCHEMA_NAME,
        version=DataSnapshot.ARTIFACT_SCHEMA_VERSION,
        inputs=[(data_ref, "data_ref")],
    )
    derived = original.model_copy(
        update={
            "model_spec": original.model_spec.model_copy(
                update={"data_snapshot_ref": str(snapshot_ref.artifact_id)}
            )
        }
    )
    trinity_ref = cas.ArtifactRef.model_validate(
        persist_trinity_bundle_artifact(
            cas.ensure_ir_artifact_store(store),
            derived,
            inputs=[
                cas.input_ref_from_artifact_ref(ref, role=role)
                for ref, role in [
                    (original_ref, "original_trinity"),
                    (snapshot_ref, "masked_snapshot"),
                    (candidate_ref, "policy_candidate"),
                ]
            ],
        ).model_dump(mode="json")
    )
    request = NativeForecastRequest(
        schema_version="1.0",
        randomness_scope="same_seed_submitted_each_step",
        limitations=list(_SCOPE_LIMITATIONS),
        profile=profile,
        source_snapshot_ref=source_ref,
        source_data_ref=source_data_ref,
        original_trinity_ref=original_ref,
        candidate_ref=candidate_ref,
        registry_ref=registry_ref,
        data_snapshot_ref=snapshot_ref,
        trinity_ref=trinity_ref,
        cutoff=cutoff,
        row_ids=projected["row_ids"],
        history_time_index=projected["time_index"],
        rules=rules,
        run_id=run_id,
        seed=seed,
    )
    _check_request(store, request)
    refs = [
        (source_ref, "source_snapshot"),
        (source_data_ref, "source_data"),
        (original_ref, "original_trinity"),
        (candidate_ref, "candidate"),
        (registry_ref, "registry"),
        (snapshot_ref, "masked_snapshot"),
        (trinity_ref, "derived_trinity"),
    ]
    request_ref = _put(
        store,
        request,
        kind=request.ARTIFACT_KIND,
        schema=request.ARTIFACT_SCHEMA_NAME,
        version=request.ARTIFACT_SCHEMA_VERSION,
        inputs=refs,
    )
    state["run_id"] = run_id
    inputs.update(
        data_snapshot_ref=snapshot_ref.model_dump(mode="json"),
        trinity_bundle_ref=trinity_ref.model_dump(mode="json"),
    )
    params.update(
        random_seed=seed, n_simulation_runs=1, **{REQUEST_KEY: request_ref.model_dump(mode="json")}
    )
    return state


def _same_state(left: Any, right: Any) -> bool:
    if is_dataclass(left) and not isinstance(left, type):
        return type(left) is type(right) and all(
            _same_state(getattr(left, f.name), getattr(right, f.name)) for f in fields(left)
        )
    try:
        a, b = np.asarray(left), np.asarray(right)
        return a.shape == b.shape and a.dtype == b.dtype and bool(np.array_equal(a, b))
    except (TypeError, ValueError):
        return False


def load_native_request(
    store: cas.ArtifactStore, request_ref: cas.ArtifactRef
) -> NativeForecastRequest:
    """Reconcile the selected request and its complete source before execution."""
    request = cas.validate_core_model_json_artifact(
        NativeForecastRequest, store, _selected(request_ref)
    )
    for role, ref in (
        ("source_snapshot", request.source_snapshot_ref),
        ("source_data", request.source_data_ref),
        ("original_trinity", request.original_trinity_ref),
        ("candidate", request.candidate_ref),
        ("registry", request.registry_ref),
        ("masked_snapshot", request.data_snapshot_ref),
        ("derived_trinity", request.trinity_ref),
    ):
        _edge(store, request_ref, ref, role)
    _check_request(store, request)
    return request


def _observations(
    store: cas.ArtifactStore, request: NativeForecastRequest, snapshots: list[StateSnapshotRef]
) -> dict[str, list[float]]:
    bundle = _check_targets(store, request)
    values: dict[str, list[float]] = {target.metric: [] for target in request.profile.targets}
    for snapshot in snapshots:
        state = load_state_snapshot(store, snapshot_ref=_selected(snapshot))
        for target in request.profile.targets:
            slot = bundle.slot_registry.slots[target.slot_id]
            value = np.asarray(get_state_path(state, slot.state_path), dtype=float)
            if (
                value.size == 0
                or not np.all(np.isfinite(value))
                or (target.reduction == "identity" and value.size != 1)
            ):
                raise ValueError("native replay state observable has failed support")
            values[target.metric].append(
                float(np.sum(value) if target.reduction == "sum" else np.mean(value))
            )
    return values


def _admit_initial_binding(
    store: cas.CoreJSONArtifactStore,
    request: NativeForecastRequest,
    binding_ref: FoundryInputBindingsRef,
) -> tuple[FoundryInputBindings, Any]:
    """Recompute the first materialized state before it reaches Foundry."""
    binding = cas.validate_core_model_json_artifact(
        FoundryInputBindings, store, _selected(binding_ref)
    )
    if (
        binding.data_snapshot_ref != request.data_snapshot_ref
        or binding.registry_bundle_ref != request.registry_ref
        or binding.rules != request.rules
    ):
        raise ValueError("native replay initial input bindings differ from request")
    _edge(store, binding_ref, request.data_snapshot_ref, "input.data_snapshot_ref")
    _edge(store, binding_ref, request.registry_ref, "input.registry_bundle_ref")
    _edge(store, binding_ref, binding.bound_state_snapshot_ref, "artifact.bound_state_snapshot_ref")
    _edge(
        store,
        binding.bound_state_snapshot_ref,
        request.data_snapshot_ref,
        "input.data_snapshot_ref",
    )
    _edge(
        store, binding.bound_state_snapshot_ref, request.registry_ref, "input.registry_bundle_ref"
    )
    state = load_state_snapshot(store, snapshot_ref=binding.bound_state_snapshot_ref)
    recomputed = prepare_input_bindings(
        store,
        data_snapshot_ref=request.data_snapshot_ref,
        registry_bundle_ref=request.registry_ref,
        rules=request.rules,
    )
    if not _same_state(state, recomputed.materialized_state):
        raise ValueError("native replay initial materialization differs from source")
    return binding, state


def _check_execution_scope(execution: ExecuteRequest) -> None:
    if (
        execution.feedback_config_ref is not None
        or execution.parameter_override_bundle_ref is not None
        or execution.observed_range_bundle_ref is not None
        or execution.welfare_bound_mode != "ex_ante"
        or execution.welfare_bound_required
    ):
        raise ValueError("native replay execution contains unscoped inputs")


def execute_native_forecast(
    ctx: ExecutionContext, execution: ExecuteRequest, request_ref: cas.ArtifactRef
) -> ExecuteResult:
    """Run each step through the configured Foundry executor with selected inputs."""
    request = load_native_request(ctx.store, request_ref)
    if request.run_id != ctx.run.run_manifest.run_id or request.seed != execution.exec_config.seed:
        raise ValueError("native replay actual run or seed differs from request")
    _check_execution_scope(execution)
    if ctx.foundry is None:
        raise ValueError("native replay requires the configured Foundry port")
    core_store: Any = ctx.store
    bindings, initial = _admit_initial_binding(core_store, request, execution.input_bindings_ref)
    execution = execution.model_copy(update={"return_selected_profile": True})
    submitted_execution = execution.model_copy(deep=True)
    snapshots: list[StateSnapshotRef] = []
    simulations: list[SimulationResultRef] = []
    execution_bindings: list[FoundryInputBindingsRef] = []
    initial_step = int(np.asarray(initial.step))
    result: ExecuteResult | None = None
    for index in range(len(request.profile.time_index)):
        if index:
            previous = load_state_snapshot(ctx.store, snapshot_ref=snapshots[-1])
            advanced = replace(
                previous,
                step=np.asarray(initial_step + index, dtype=np.asarray(previous.step).dtype),
            )
            advanced_ref = put_state_snapshot(
                ctx.store,
                state=advanced,
                step=initial_step + index,
                inputs=[
                    cas.input_ref_from_artifact_ref(snapshots[-1], role="previous_forecast_state")
                ],
                return_selected_profile=True,
            )
            next_binding = bindings.model_copy(update={"bound_state_snapshot_ref": advanced_ref})
            binding_ref = _put(
                ctx.store,
                next_binding,
                kind=FoundryInputBindings.ARTIFACT_KIND,
                schema=FoundryInputBindings.ARTIFACT_SCHEMA_NAME,
                version=next_binding.schema_version,
                inputs=[
                    (request.data_snapshot_ref, "input.data_snapshot_ref"),
                    (request.registry_ref, "input.registry_bundle_ref"),
                    (advanced_ref, "artifact.bound_state_snapshot_ref"),
                ],
            )
            execution = execution.model_copy(
                update={
                    "input_bindings_ref": FoundryInputBindingsRef.model_validate(
                        binding_ref.model_dump(mode="python")
                    )
                }
            )
        execution_bindings.append(execution.input_bindings_ref)
        result = ctx.foundry.execute(ctx.store, execution)
        if not result.ok or result.simulation_result_ref is None:
            raise ValueError("native replay execution produced no successful simulation")
        admission = admit_execution_source(ctx.store, result.simulation_result_ref)
        simulation = admission.simulation_result
        if admission.mode != "single_step_basis" or simulation.state_snapshot_ref is None:
            raise ValueError("native replay requires a selected single-step execution basis")
        simulations.append(result.simulation_result_ref)
        snapshots.append(simulation.state_snapshot_ref)
    trajectory = NativeForecastTrajectory(
        schema_version="1.0",
        request_ref=request_ref,
        submitted_execution=submitted_execution,
        submitted_request_fields_set=tuple(sorted(submitted_execution.model_fields_set)),
        submitted_exec_config_fields_set=tuple(
            sorted(submitted_execution.exec_config.model_fields_set)
        ),
        execution_bindings_refs=execution_bindings,
        simulation_refs=simulations,
        state_snapshot_refs=snapshots,
        values=_observations(ctx.store, request, snapshots),
    )
    forecast_ref = _put(
        ctx.store,
        trajectory,
        kind=trajectory.ARTIFACT_KIND,
        schema=trajectory.ARTIFACT_SCHEMA_NAME,
        version=trajectory.ARTIFACT_SCHEMA_VERSION,
        inputs=[
            (request_ref, "request"),
            *[(ref, f"binding.{i}") for i, ref in enumerate(execution_bindings)],
            *[(ref, f"simulation.{i}") for i, ref in enumerate(simulations)],
            *[(ref, f"state.{i}") for i, ref in enumerate(snapshots)],
        ],
    )
    # Admit the trajectory before the ordinary simulation result is exposed to
    # downstream workflow nodes or any proof/metrics bridge.
    load_native_forecast(core_store, forecast_ref, request_ref)
    assert result is not None
    return result.model_copy(
        update={
            "derived_refs": [
                *result.derived_refs,
                DerivedArtifact(role=FORECAST_KEY, ref=forecast_ref),
            ]
        }
    )


def load_native_forecast(
    store: cas.CoreJSONArtifactStore, forecast_ref: cas.ArtifactRef, request_ref: cas.ArtifactRef
) -> tuple[NativeForecastTrajectory, NativeForecastRequest]:
    """Reopen selected bytes and independently reconcile the complete trajectory."""
    forecast = cas.validate_core_model_json_artifact(
        NativeForecastTrajectory, store, _selected(forecast_ref)
    )
    if forecast.request_ref != request_ref:
        raise ValueError("native replay request identity mismatch")
    _edge(store, forecast_ref, request_ref, "request")
    request = load_native_request(store, request_ref)
    horizon = len(request.profile.time_index)
    if any(
        len(axis) != horizon
        for axis in (
            forecast.execution_bindings_refs,
            forecast.simulation_refs,
            forecast.state_snapshot_refs,
        )
    ):
        raise ValueError("native replay trajectory axis mismatch")
    if (
        forecast.submitted_execution.input_bindings_ref != forecast.execution_bindings_refs[0]
        or forecast.submitted_execution.exec_config.seed != request.seed
        or forecast.submitted_execution.return_selected_profile is not True
    ):
        raise ValueError("native replay submitted execution differs from request")
    _check_execution_scope(forecast.submitted_execution)
    previous = None
    initial_step = None
    plan_ref = None
    bundle = _check_targets(store, request)
    for index, (binding_ref, simulation_ref, state_ref) in enumerate(
        zip(
            forecast.execution_bindings_refs,
            forecast.simulation_refs,
            forecast.state_snapshot_refs,
            strict=True,
        )
    ):
        for role, ref in (
            (f"binding.{index}", binding_ref),
            (f"simulation.{index}", simulation_ref),
            (f"state.{index}", state_ref),
        ):
            _edge(store, forecast_ref, ref, role)
        binding = cas.validate_core_model_json_artifact(FoundryInputBindings, store, binding_ref)
        if (
            binding.data_snapshot_ref != request.data_snapshot_ref
            or binding.registry_bundle_ref != request.registry_ref
            or binding.rules != request.rules
        ):
            raise ValueError("native replay persisted binding differs from request")
        bound = load_state_snapshot(store, snapshot_ref=binding.bound_state_snapshot_ref)
        if index == 0:
            _admit_initial_binding(store, request, binding_ref)
            initial_step = int(np.asarray(bound.step))
        else:
            assert previous is not None
            assert initial_step is not None
            _edge(
                store,
                binding.bound_state_snapshot_ref,
                forecast.state_snapshot_refs[index - 1],
                "previous_forecast_state",
            )
            advanced = replace(
                previous,
                step=np.asarray(initial_step + index, dtype=np.asarray(previous.step).dtype),
            )
            if not _same_state(bound, advanced):
                raise ValueError("native replay predecessor state or clock mismatch")
        admission = admit_execution_source(store, simulation_ref)
        basis = admission.basis
        if admission.mode != "single_step_basis" or basis is None:
            raise ValueError("native replay selected execution basis unavailable")
        if (
            basis.request.model_dump(mode="json", exclude={"input_bindings_ref"})
            != forecast.submitted_execution.model_dump(mode="json", exclude={"input_bindings_ref"})
            or basis.request_fields_set != forecast.submitted_request_fields_set
            or basis.request_exec_config_fields_set != forecast.submitted_exec_config_fields_set
        ):
            raise ValueError("native replay execution differs from submitted request")
        if (
            basis.trinity_bundle_ref != request.trinity_ref
            or basis.candidate_ref != request.candidate_ref
            or basis.candidate_data_snapshot_ref != request.source_snapshot_ref
            or basis.data_snapshot_ref != request.data_snapshot_ref
            or basis.input_bindings_ref != binding_ref
            or any(
                cas.artifact_ref_identity_key(ref)
                != cas.artifact_ref_identity_key(request.registry_ref)
                for ref in (
                    basis.binding_registry_ref,
                    basis.compile_registry_ref,
                    basis.runtime_registry_ref,
                    basis.candidate_registry_bundle_ref,
                )
            )
            or basis.effective_seed != request.seed
            or basis.effective_seed_source != "exec_config.seed"
            or basis.effective_step != initial_step + index
            or admission.simulation_result.state_snapshot_ref != state_ref
        ):
            raise ValueError("native replay execution basis differs from declared trajectory")
        if plan_ref is not None and plan_ref != basis.exec_plan_ref:
            raise ValueError("native replay execution plan changed during trajectory")
        plan_ref = basis.exec_plan_ref
        _edge(store, state_ref, binding.bound_state_snapshot_ref, "base_state")
        delta_ref = _edge_ref(store, simulation_ref, "state_delta", "foundry.state_delta")
        _edge(store, state_ref, delta_ref, "state_delta")
        previous = load_state_snapshot(store, snapshot_ref=state_ref)
        recomputed_state = apply_state_delta(
            store,
            base_state=bound,
            state_delta_ref=delta_ref,
            slot_registry=bundle.slot_registry,
            merge_registry=bundle.merge_registry,
        )
        if not _same_state(previous, recomputed_state):
            raise ValueError("native replay output state differs from applied state delta")
        if int(np.asarray(previous.step)) != initial_step + index:
            raise ValueError("native replay output clock mismatch")
    if forecast.values != _observations(store, request, forecast.state_snapshot_refs):
        raise ValueError("native replay values differ from recomputed state observations")
    return forecast, request


def _load_native_workflow_report(
    store: cas.CoreJSONArtifactStore, ref: cas.ArtifactRef, run_ref: cas.ArtifactRef
) -> dict[str, Any]:
    """Reconcile terminal status to the actual selected workflow and its node census."""
    from polisyos.core.run import RunManifest
    from polisyos.scientist.orchestration.engine.executor import (
        WorkflowExecutionStatus,
        WorkflowReport,
    )
    from polisyos.scientist.orchestration.engine.finalization import (
        FINAL_WORKFLOW_REPORT_STATE_PATH,
        FINALIZATION_KIND,
        FINALIZATION_SCHEMA_NAME,
        WorkflowStateFinalization,
    )
    from polisyos.scientist.orchestration.engine.state import ExperimentState
    from polisyos.scientist.orchestration.engine.workflow_spec import WorkflowSpec

    def selected_model(
        model: Any,
        selected_ref: cas.ArtifactRef,
        kind: str,
        schema: str,
        version: str | None = "1.0",
    ) -> Any:
        selected_manifest = store.get_manifest(_selected(selected_ref))
        if (
            selected_manifest.kind != kind
            or selected_manifest.media_type != "application/json"
            or selected_manifest.artifact_schema is None
            or selected_manifest.artifact_schema.name != schema
            or (version is not None and selected_manifest.artifact_schema.version != version)
        ):
            raise ValueError("native workflow selected source profile mismatch")
        selected = cas.validate_core_model_json_artifact(model, store, selected_ref)
        if getattr(selected, "schema_version", None) != selected_manifest.artifact_schema.version:
            raise ValueError("native workflow source schema version mismatch")
        return selected

    run_manifest = store.get_manifest(_selected(run_ref))
    if (
        run_manifest.kind != "core.run_manifest"
        or run_manifest.media_type != "application/json"
        or run_manifest.artifact_schema
        != cas.SchemaInfo(name="polisyos.core.RunManifest", version="0.1.0")
    ):
        raise ValueError("native workflow run manifest profile mismatch")
    run = cas.validate_core_model_json_artifact(RunManifest, store, run_ref)
    finalizations = [output for output in run.outputs if output.kind == FINALIZATION_KIND]
    if len(finalizations) != 1 or ref not in run.outputs:
        raise ValueError("native workflow finalization or report is not in the selected run")
    finalization = selected_model(
        WorkflowStateFinalization, finalizations[0], FINALIZATION_KIND, FINALIZATION_SCHEMA_NAME
    )
    report_bindings = [
        binding
        for binding in finalization.output_bindings
        if binding.state_path == FINAL_WORKFLOW_REPORT_STATE_PATH
    ]
    if (
        finalization.run_id != run.run_id
        or finalization.workflow_id != "scientist_default"
        or finalization.workflow_spec_ref not in run.inputs
        or finalization.final_state_ref not in run.outputs
        or len(report_bindings) != 1
        or report_bindings[0].artifact_ref != ref
    ):
        raise ValueError("native workflow finalization binding mismatch")
    spec = selected_model(
        WorkflowSpec,
        finalization.workflow_spec_ref,
        "scientist.workflow_spec",
        "polisyos.scientist.orchestration.engine.WorkflowSpec",
    )
    final_state = selected_model(
        ExperimentState,
        finalization.final_state_ref,
        "scientist.experiment_state",
        "polisyos.scientist.orchestration.engine.ExperimentState",
        version=None,
    )
    if final_state.run_id != run.run_id or final_state.reports_index.get("workflow_report") != ref:
        raise ValueError("native workflow final state does not retain its report")

    manifest = store.get_manifest(_selected(ref))
    if (
        manifest.kind != "scientist.workflow_report"
        or manifest.media_type != "application/json"
        or manifest.artifact_schema
        != cas.SchemaInfo(
            name="polisyos.scientist.orchestration.engine.WorkflowReport", version="1.0"
        )
    ):
        raise ValueError("native report workflow profile mismatch")
    typed = cas.validate_core_model_json_artifact(WorkflowReport, store, ref)
    expected_nodes = {(node.alias, str(node.node_id)) for node in spec.nodes}
    actual_nodes = {(node.alias, node.node_id) for node in typed.nodes}
    if (
        spec.workflow_id != "scientist_default"
        or spec.error_policy != "continue"
        or typed.error_policy != spec.error_policy
        or len(expected_nodes) != len(spec.nodes)
        or len(actual_nodes) != len(typed.nodes)
        or actual_nodes != expected_nodes
    ):
        raise ValueError("native workflow node census differs from selected workflow")
    actual_status = WorkflowExecutionStatus.from_failures(
        any(node.status == "fail" for node in typed.nodes)
    ).value
    if typed.workflow_id != "scientist_default" or typed.run_id != run.run_id:
        raise ValueError("native workflow identity differs from admitted route")
    if typed.status != actual_status or run.status != actual_status:
        raise ValueError("native workflow status differs from its node failures")
    payload = cas.load_core_json_artifact(store, ref)
    if not isinstance(payload, dict):
        raise ValueError("native report workflow evidence is malformed")
    return payload


def _load_native_plan(
    store: cas.CoreJSONArtifactStore, ref: cas.ArtifactRef
) -> HistoricalValidationPlan:
    from polisyos.scientist.methods.backtesting.plan import HistoricalValidationPlan

    manifest = store.get_manifest(_selected(ref))
    if (
        manifest.kind != _NATIVE_PLAN_KIND
        or manifest.media_type != "application/json"
        or manifest.artifact_schema != cas.SchemaInfo(name=_NATIVE_PLAN_SCHEMA, version="1.0")
    ):
        raise ValueError("native replica plan profile mismatch")
    plan = cas.validate_core_model_json_artifact(HistoricalValidationPlan, store, ref)
    state = plan.scientist_state
    if not isinstance(state, dict) or not isinstance(state.get("inputs"), dict):
        raise ValueError("native replica plan inputs are missing")
    for key, role in (
        ("data_snapshot_ref", "source_snapshot"),
        ("trinity_bundle_ref", "original_trinity"),
        ("registry_bundle_ref", "registry"),
    ):
        _edge(store, ref, cas.ArtifactRef.model_validate(state["inputs"].get(key)), role)
    return plan


def _check_native_plan_request(
    store: cas.CoreJSONArtifactStore,
    plan: HistoricalValidationPlan,
    request: NativeForecastRequest,
    *,
    index: int,
) -> None:
    from polisyos.scientist.methods.backtesting.plan import PredictionSource

    state = plan.scientist_state
    if not isinstance(state, dict) or set(state) - {"run_id", "inputs", "params"}:
        raise ValueError("native replica plan state mismatch")
    inputs, params = state.get("inputs"), state.get("params")
    if (
        not isinstance(inputs, dict)
        or set(inputs) != {"data_snapshot_ref", "trinity_bundle_ref", "registry_bundle_ref"}
        or not isinstance(params, dict)
        or set(params)
        - {
            "workflow_id",
            "foundry_input_binding_rules",
            PROFILE_KEY,
            "random_seed",
            "n_simulation_runs",
        }
        or params.get("workflow_id", "scientist_default") != "scientist_default"
        or plan.prediction_source is not PredictionSource.SCIENTIST
        or plan.masking_strategy.value not in {"drop_post", "truncate"}
    ):
        raise ValueError("native replica plan scope mismatch")
    base_seed = plan.random_seed if plan.random_seed is not None else params.get("random_seed", 0)
    if type(base_seed) is not int or request.seed != base_seed + index - 1:
        raise ValueError("native replica plan seed mismatch")
    if (
        cas.ArtifactRef.model_validate(inputs["data_snapshot_ref"]) != request.source_snapshot_ref
        or cas.ArtifactRef.model_validate(inputs["trinity_bundle_ref"])
        != request.original_trinity_ref
        or cas.ArtifactRef.model_validate(inputs["registry_bundle_ref"]) != request.registry_ref
        or NativeForecastProfile.model_validate(params[PROFILE_KEY]) != request.profile
        or [
            FoundryInputBindingRule.model_validate(item)
            for item in params["foundry_input_binding_rules"]
        ]
        != request.rules
        or plan.historical_data_ref != str(request.source_data_ref.artifact_id)
        or set(plan.target_metrics) != {target.metric for target in request.profile.targets}
        or set(plan.ground_truth_outcomes) != set(plan.target_metrics)
    ):
        raise ValueError("native replica request differs from selected plan")
    source_data = cas.load_core_json_artifact(store, request.source_data_ref)
    if (
        not isinstance(source_data, dict)
        or OutcomeMasker._resolve_cutoff(source_data, plan) != request.cutoff
        or (plan.intervention_date and plan.intervention_date != request.profile.origin)
        or _source_holdout(source_data, request.profile, request.cutoff)
        != plan.ground_truth_outcomes
    ):
        raise ValueError("native replica selected plan holdout mismatch")


def _selected_replica_evidence(
    store: cas.CoreJSONArtifactStore, cohort_ref: cas.ArtifactRef, replica: Any, *, index: int
) -> tuple[dict[str, Any], list[dict[str, Any]]] | None:
    """Reconcile every retained cohort edge and workflow, including failures."""
    expected_roles = set()
    if replica.physical_request is not None:
        request = ExecuteRequest.model_validate(replica.physical_request)
        for ref, role in (
            (request.exec_plan_ref, f"replica_{index}_exec_plan"),
            (request.input_bindings_ref, f"replica_{index}_input_bindings"),
        ):
            _edge(store, cohort_ref, ref, role)
            expected_roles.add(role)
    for ref, role in (
        (replica.simulation_result_ref, f"replica_{index}_simulation_result"),
        (replica.metrics_ref, f"replica_{index}_metrics"),
        (replica.workflow_report_ref, f"replica_{index}_workflow_report"),
        (replica.run_manifest_ref, f"replica_{index}_run_manifest"),
    ):
        if ref is not None:
            _edge(store, cohort_ref, ref, role)
            expected_roles.add(role)
    actual_roles = [
        edge.role
        for edge in store.get_manifest(cohort_ref).inputs
        if edge.role.startswith(f"replica_{index}_")
    ]
    if len(actual_roles) != len(expected_roles) or set(actual_roles) != expected_roles:
        raise ValueError("native replica retained evidence census mismatch")
    if replica.workflow_report_ref is None or replica.run_manifest_ref is None:
        return None
    workflow = _load_native_workflow_report(
        store, replica.workflow_report_ref, replica.run_manifest_ref
    )
    failures = [
        {
            "alias": node.get("alias"),
            "status": node.get("status"),
            "error": node.get("error") if isinstance(node.get("error"), dict) else None,
        }
        for node in workflow["nodes"]
        if isinstance(node, dict) and node.get("status") == "fail"
    ]
    if (
        replica.index != index
        or replica.workflow_started is not True
        or workflow.get("run_id") != replica.run_id
        or workflow.get("status") != replica.workflow_status
        or failures != replica.workflow_failures
    ):
        raise ValueError("native report workflow status or forecast evidence mismatch")
    return workflow, failures


def _verify_native_replica(
    store: cas.CoreJSONArtifactStore,
    cohort_ref: cas.ArtifactRef,
    cohort: Any,
    replica: Any,
    forecast_ref: cas.ArtifactRef,
    request_ref: cas.ArtifactRef,
    *,
    index: int,
) -> tuple[NativeForecastTrajectory, NativeForecastRequest, list[dict[str, Any]]]:
    """Reconcile one selected trajectory to its real workflow and cohort record."""
    from polisyos.scientist.methods.backtesting.orchestrator import _resolve_replica_failure

    forecast, request = load_native_forecast(store, forecast_ref, request_ref)
    if cas.artifact_ref_identity_key(cohort.masked_data_snapshot_ref) != (
        cas.artifact_ref_identity_key(request.data_snapshot_ref)
    ):
        raise ValueError("native report replica cohort differs from request")
    _edge(store, cohort_ref, forecast_ref, f"native_forecast:{index}")
    selected_workflow = _selected_replica_evidence(store, cohort_ref, replica, index=index)
    if selected_workflow is None:
        raise ValueError("native report workflow evidence is missing")
    workflow, failures = selected_workflow
    simulation_nodes = [
        node
        for node in workflow["nodes"]
        if isinstance(node, dict) and node.get("alias") == "run_simulation"
    ]
    if (
        workflow.get("run_id") != request.run_id
        or replica.run_id != request.run_id
        or replica.seed != request.seed
        or len(simulation_nodes) != 1
        or simulation_nodes[0].get("status") != "ok"
        or not any(
            cas.ArtifactRef.model_validate(ref) == forecast_ref
            for ref in simulation_nodes[0].get("artifacts", [])
        )
    ):
        raise ValueError("native report workflow status or forecast evidence mismatch")
    final_ref = forecast.simulation_refs[-1]
    final_admission = admit_execution_source(store, final_ref)
    final_basis = final_admission.basis
    if replica.simulation_result_ref is None or replica.metrics_ref is None:
        raise ValueError("native report replica execution outputs are missing")
    expected_failure = (
        None
        if replica.workflow_status == "ok"
        else _resolve_replica_failure(
            None, failures, f"scientist_workflow_status:{replica.workflow_status}"
        )
    )
    if (
        replica.index != index
        or replica.workflow_started is not True
        or replica.status != ("completed" if replica.workflow_status == "ok" else "failed")
        or replica.failure != expected_failure
        or replica.seed_source != "exec_config.seed"
        or cas.artifact_ref_identity_key(replica.simulation_result_ref)
        != cas.artifact_ref_identity_key(final_ref)
        or cas.artifact_ref_identity_key(replica.metrics_ref)
        != cas.artifact_ref_identity_key(final_admission.simulation_result.metrics_ref)
        or final_basis is None
        or replica.physical_request != final_basis.request.model_dump(mode="json")
    ):
        raise ValueError("native report replica status or candidate limitation mismatch")
    return forecast, request, failures


def _load_selected_native_cohort(store: cas.CoreJSONArtifactStore, ref: cas.ArtifactRef) -> Any:
    from polisyos.scientist.methods.backtesting.orchestrator import _BacktestReplicaCohort

    manifest = store.get_manifest(_selected(ref))
    if (
        manifest.kind != "scientist.backtest.replica_cohort"
        or manifest.media_type != "application/json"
        or manifest.artifact_schema
        != cas.SchemaInfo(name="polisyos.scientist.backtesting.ReplicaCohort", version="1.0")
    ):
        raise ValueError("native report replica cohort profile mismatch")
    cohort = cas.validate_core_model_json_artifact(_BacktestReplicaCohort, store, ref)
    _edge(store, ref, cohort.masked_data_snapshot_ref, "masked_data")
    replica_prefixes = tuple(f"replica_{item.index}_" for item in cohort.replicas)
    if any(
        edge.role.startswith("replica_") and not edge.role.startswith(replica_prefixes)
        for edge in manifest.inputs
    ):
        raise ValueError("native replica retained evidence census mismatch")
    return cohort


def _reconcile_complete_native_cohort(
    store: cas.CoreJSONArtifactStore,
    cohort_ref: cas.ArtifactRef,
    projection: _NativeReplicaProjection,
) -> tuple[Any, list[NativeForecastTrajectory], list[NativeForecastRequest]]:
    """Reopen the selected complete cohort for both publication and fresh reads."""
    cohort = _load_selected_native_cohort(store, cohort_ref)
    _edge(store, cohort_ref, projection.plan_ref, "native_plan")
    plan = _load_native_plan(store, projection.plan_ref)
    count = len(projection.forecast_refs)
    if (
        plan.plan_id != cohort.plan_id
        or plan.n_simulation_runs != count
        or cohort.requested_count != count
        or cohort.started_count != count
        or cohort.foundry_execute_count != count
        or cohort.completed_count != count
        or cohort.failed_count != 0
        or len(cohort.replicas) != count
        or [replica.index for replica in cohort.replicas] != list(range(1, count + 1))
        or len({replica.run_id for replica in cohort.replicas}) != count
        or len({cas.artifact_ref_identity_key(ref) for ref in projection.forecast_refs}) != count
    ):
        raise ValueError("native replica projection cohort census mismatch")
    cohort_roles = [
        edge.role
        for edge in store.get_manifest(cohort_ref).inputs
        if edge.role.startswith("native_forecast:")
    ]
    if sorted(cohort_roles) != sorted(f"native_forecast:{index}" for index in range(1, count + 1)):
        raise ValueError("native replica projection trajectory census mismatch")

    forecasts: list[NativeForecastTrajectory] = []
    requests: list[NativeForecastRequest] = []
    for index, (replica, forecast_ref) in enumerate(
        zip(cohort.replicas, projection.forecast_refs, strict=True), start=1
    ):
        stored_forecast = cas.validate_core_model_json_artifact(
            NativeForecastTrajectory, store, _selected(forecast_ref)
        )
        forecast, request, _ = _verify_native_replica(
            store,
            cohort_ref,
            cohort,
            replica,
            forecast_ref,
            stored_forecast.request_ref,
            index=index,
        )
        _check_native_plan_request(store, plan, request, index=index)
        if replica.status != "completed":
            raise ValueError("native replica projection includes an incomplete workflow")
        forecasts.append(forecast)
        requests.append(request)
    _require_shared_native_basis(requests)
    _require_shared_native_execution(forecasts)
    return cohort, forecasts, requests


def _verify_native_projection(
    store: cas.CoreJSONArtifactStore,
    report_ref: cas.ArtifactRef,
    cohort_ref: cas.ArtifactRef,
    scenario: Any,
    scenario_reasons: list[str],
) -> list[str]:
    """Reconcile the report's mean against the selected complete cohort."""
    projection = _NativeReplicaProjection.model_validate(
        scenario.metadata.get("native_replica_projection")
    )
    if any(
        key in scenario.metadata
        for key in (
            "native_forecast_ref",
            "native_request_ref",
            "native_workflow_status",
            "native_workflow_failures",
            "native_requested_replicas",
            "native_started_replicas",
            "native_requested_count_status",
            "native_started_count_status",
        )
    ):
        raise ValueError("native replica projection contains conflicting scenario fields")
    cohort, forecasts, requests = _reconcile_complete_native_cohort(store, cohort_ref, projection)
    if cohort.plan_id != scenario.scenario_id:
        raise ValueError("native replica projection cohort census mismatch")
    roles = []
    for index, forecast_ref in enumerate(projection.forecast_refs, start=1):
        role = f"native_forecast:{scenario.scenario_id}:{index}"
        _edge(store, report_ref, forecast_ref, role)
        roles.append(role)
    first = requests[0]
    if (
        scenario.metadata.get("prediction_source_effective") != "scientist"
        or scenario.metadata.get("degraded") is not True
        or scenario.metadata.get("native_forecast_purpose") != first.profile.purpose
        or scenario.metadata.get("native_randomness_scope") != first.randomness_scope
        or scenario.metadata.get("native_limitations") != first.limitations
        or any(request.limitations != first.limitations for request in requests)
        or scenario.metadata.get("native_foundry_step_count")
        != sum(len(forecast.simulation_refs) for forecast in forecasts)
        or "native_predictive_simulation_only" not in scenario_reasons
        or any(limitation not in scenario_reasons for limitation in first.limitations)
    ):
        raise ValueError("native replica projection limitations or step count mismatch")
    actual: dict[str, list[float]] = {}
    truth: dict[str, list[float]] = {}
    for row in scenario.outcome_comparisons:
        if row.ci_lower is not None or row.ci_upper is not None or row.within_ci is not None:
            raise ValueError("native replay does not establish predictive intervals")
        actual.setdefault(row.metric_name, []).append(row.y_pred)
        truth.setdefault(row.metric_name, []).append(row.y_true)
    mean = _mean_native_values([forecast.values for forecast in forecasts])
    if actual != mean or scenario.compared_count != sum(len(values) for values in mean.values()):
        raise ValueError("native report predictions differ from verified replica projection")
    source = cas.load_core_json_artifact(store, first.source_data_ref)
    if not isinstance(source, dict) or truth != _source_holdout(
        source, first.profile, first.cutoff
    ):
        raise ValueError("native report outcomes differ from selected source holdout")
    return roles


def _verify_unavailable_native_cohort(
    store: cas.CoreJSONArtifactStore,
    cohort_ref: cas.ArtifactRef,
    cohort: Any,
    scenario_id: str,
    requested: int,
    started: int,
) -> None:
    """Check retained successful trajectories without projecting a partial cohort."""
    if (
        cohort.plan_id != scenario_id
        or cohort.requested_count != requested
        or cohort.started_count != started
        or cohort.failed_count < 1
        or [replica.index for replica in cohort.replicas] != list(range(1, requested + 1))
        or len({replica.run_id for replica in cohort.replicas}) != requested
        or sum(replica.workflow_started for replica in cohort.replicas) != started
        or cohort.foundry_execute_count
        != sum(replica.physical_request is not None for replica in cohort.replicas)
        or any(replica.status == "failed" and not replica.failure for replica in cohort.replicas)
    ):
        raise ValueError("native unavailable scenario cohort denominator mismatch")
    plan = None
    if requested > 1:
        plan_ref = _edge_ref(store, cohort_ref, "native_plan", _NATIVE_PLAN_KIND)
        plan = _load_native_plan(store, plan_ref)
        if plan.plan_id != scenario_id or plan.n_simulation_runs != requested:
            raise ValueError("native unavailable scenario selected plan mismatch")

    roles = [
        edge.role
        for edge in store.get_manifest(cohort_ref).inputs
        if edge.role.startswith("native_forecast:")
    ]
    valid_roles = {f"native_forecast:{index}" for index in range(1, requested + 1)}
    if len(roles) != len(set(roles)) or not set(roles) <= valid_roles:
        raise ValueError("native unavailable scenario trajectory census mismatch")
    requests: list[NativeForecastRequest] = []
    forecasts: list[NativeForecastTrajectory] = []
    for replica in cohort.replicas:
        role = f"native_forecast:{replica.index}"
        if role not in roles:
            selected_workflow = _selected_replica_evidence(
                store, cohort_ref, replica, index=replica.index
            )
            if replica.status == "completed":
                raise ValueError("native completed replica trajectory is missing")
            if selected_workflow is not None:
                workflow, _ = selected_workflow
                simulation = next(
                    node for node in workflow["nodes"] if node["alias"] == "run_simulation"
                )
                if simulation["status"] == "ok":
                    raise ValueError("native succeeded simulation trajectory is missing")
            continue
        forecast_ref = _edge_ref(store, cohort_ref, role, NativeForecastTrajectory.ARTIFACT_KIND)
        stored = cas.validate_core_model_json_artifact(
            NativeForecastTrajectory, store, forecast_ref
        )
        forecast, request, _ = _verify_native_replica(
            store,
            cohort_ref,
            cohort,
            replica,
            forecast_ref,
            stored.request_ref,
            index=replica.index,
        )
        if plan is not None:
            _check_native_plan_request(store, plan, request, index=replica.index)
        requests.append(request)
        forecasts.append(forecast)
    if requests:
        _require_shared_native_basis(requests)
        _require_shared_native_execution(forecasts)


def load_native_backtest_report(
    store: cas.CoreJSONArtifactStore, report_ref: cas.ArtifactRef
) -> BacktestReport:
    """Load a report and reconcile each native comparison against its CAS trajectory.

    This proves the native prediction projection for selected report bytes. It
    does not establish independent empirical observations or calibration.
    """
    from polisyos.ir.analytics.backtest import load_backtest_report_candidate
    from polisyos.ir.registry.refs import BacktestReportRef

    report = load_backtest_report_candidate(
        cas.ensure_ir_artifact_store(store),
        BacktestReportRef.model_validate(_selected(report_ref).model_dump(mode="json")),
    )
    if "metric_diagnostics" not in report.model_fields_set:
        raise ValueError("native report requires source-bound metric diagnostics")
    scenario_rmses: list[float] = []
    for scenario in report.scenarios:
        rows = scenario.outcome_comparisons
        if not rows:
            if (
                scenario.rmse is not None
                or scenario.mae is not None
                or scenario.squared_error_sum not in (None, 0.0)
                or scenario.absolute_error_sum not in (None, 0.0)
            ):
                raise ValueError("native report empty scenario cannot claim error metrics")
            continue
        scenario_rmses.append(
            math.sqrt(math.fsum((row.y_pred - row.y_true) ** 2 for row in rows) / len(rows))
        )
    expected_macro = math.fsum(scenario_rmses) / len(scenario_rmses) if scenario_rmses else None
    if expected_macro is None:
        if (
            report.overall_macro_rmse is not None
            or report.overall_rmse is not None
            or report.overall_mae is not None
        ):
            raise ValueError("native report empty outcomes cannot claim error metrics")
    elif report.overall_macro_rmse is None or not math.isclose(
        report.overall_macro_rmse, expected_macro, rel_tol=1e-9, abs_tol=1e-12
    ):
        raise ValueError("native report macro RMSE differs from source outcomes")
    if report.overall_r_squared is not None:
        raise ValueError("native report does not establish R-squared")
    manifest = store.get_manifest(report_ref)
    native_roles = [
        edge.role for edge in manifest.inputs if edge.role.startswith("native_forecast:")
    ]
    scenario_ids = [scenario.scenario_id for scenario in report.scenarios]
    if len(set(scenario_ids)) != len(scenario_ids):
        raise ValueError("native report scenario identifiers are not unique")
    cohort_roles = [
        edge.role for edge in manifest.inputs if edge.role.startswith("replica_cohort:")
    ]
    valid_cohort_roles = {f"replica_cohort:{scenario_id}" for scenario_id in scenario_ids}
    if len(set(cohort_roles)) != len(cohort_roles) or not set(cohort_roles) <= valid_cohort_roles:
        raise ValueError("native report scenario cohort edge census differs from scenarios")
    single_native_fields = {
        "native_forecast_ref",
        "native_request_ref",
        "native_forecast_purpose",
        "native_workflow_status",
        "native_workflow_failures",
        "native_foundry_step_count",
        "native_randomness_scope",
        "native_limitations",
    }
    native_fields = single_native_fields | {"native_replica_projection"}
    native_count = 0
    unavailable_count = 0
    verified_roles: list[str] = []
    for scenario in report.scenarios:
        forecast_role = f"native_forecast:{scenario.scenario_id}"
        cohort_role = f"replica_cohort:{scenario.scenario_id}"
        cohort_edges = [edge for edge in manifest.inputs if edge.role == cohort_role]
        if len(cohort_edges) > 1:
            raise ValueError("native report has duplicate scenario cohort edges")
        cohort_names_native = False
        if cohort_edges:
            selected_cohort = _edge_ref(
                store, report_ref, cohort_role, "scientist.backtest.replica_cohort"
            )
            cohort_names_native = any(
                edge.role == "native_plan" or edge.role.startswith("native_forecast:")
                for edge in store.get_manifest(selected_cohort).inputs
            )
        raw_forecast = scenario.metadata.get("native_forecast_ref")
        scenario_reasons = [
            reason.removeprefix(f"{scenario.scenario_id}: ")
            for reason in report.degraded_reasons
            if reason.startswith(f"{scenario.scenario_id}: ")
        ]
        scenario_mode = scenario.metadata.get("prediction_source_effective")
        is_native = (
            bool(native_fields.intersection(scenario.metadata))
            or forecast_role in native_roles
            or cohort_names_native
        )
        if not is_native or (
            scenario_mode == "scientist_unavailable"
            and raw_forecast is None
            and scenario.metadata.get("native_replica_projection") is None
        ):
            unavailable = (
                "native_requested_replicas" in scenario.metadata
                or "native_started_replicas" in scenario.metadata
                or "native_requested_count_status" in scenario.metadata
                or "native_started_count_status" in scenario.metadata
                or scenario_mode == "scientist_unavailable"
                or any(
                    reason == "native_replica_projection_unsupported"
                    or reason.startswith("native_forecast_unavailable:")
                    for reason in scenario_reasons
                )
            )
            if unavailable:
                requested = scenario.metadata.get("native_requested_replicas")
                started = scenario.metadata.get("native_started_replicas")
                if (
                    type(requested) is not int
                    or type(started) is not int
                    or requested < 1
                    or not 0 <= started <= requested
                    or scenario.outcome_comparisons
                    or scenario.compared_count != 0
                    or scenario.metadata.get("prediction_source_effective")
                    != "scientist_unavailable"
                    or scenario.metadata.get("degraded") is not True
                    or scenario.metadata.get("native_requested_count_status") != "not_established"
                    or scenario.metadata.get("native_started_count_status") != "not_established"
                ):
                    raise ValueError("native unavailable scenario denominator or status mismatch")
                if started == 0:
                    valid_reason = (
                        "native_replica_projection_unsupported" in scenario_reasons
                        or any(
                            reason.startswith("native_forecast_unavailable:")
                            for reason in scenario_reasons
                        )
                    )
                else:
                    valid_reason = "scientist_replica_cohort_incomplete" in scenario_reasons
                if (
                    not valid_reason
                    or "native_requested_count_not_established" not in scenario_reasons
                    or "native_started_count_not_established" not in scenario_reasons
                ):
                    raise ValueError("native unavailable scenario reason mismatch")
                if started == 0:
                    if cohort_edges or "replica_cohort_ref" in scenario.metadata:
                        raise ValueError("native unavailable scenario has an unstarted cohort")
                else:
                    if len(cohort_edges) != 1:
                        raise ValueError("native unavailable scenario cohort is missing")
                    cohort_ref = cas.ArtifactRef.model_validate(
                        scenario.metadata.get("replica_cohort_ref")
                    )
                    _edge(store, report_ref, cohort_ref, cohort_role)
                    cohort = _load_selected_native_cohort(store, cohort_ref)
                    _verify_unavailable_native_cohort(
                        store, cohort_ref, cohort, scenario.scenario_id, requested, started
                    )
                unavailable_count += 1
            elif scenario_mode == "scientist_candidate" or any(
                reason.startswith("native_") for reason in scenario_reasons
            ):
                raise ValueError("native scenario trajectory metadata is missing")
            continue
        projection_payload = scenario.metadata.get("native_replica_projection")
        if projection_payload is not None:
            cohort_ref = cas.ArtifactRef.model_validate(scenario.metadata.get("replica_cohort_ref"))
            _edge(store, report_ref, cohort_ref, cohort_role)
            verified_roles.extend(
                _verify_native_projection(store, report_ref, cohort_ref, scenario, scenario_reasons)
            )
            native_count += 1
            continue
        if not single_native_fields.issubset(scenario.metadata) or raw_forecast is None:
            raise ValueError("native scenario trajectory metadata is missing")
        forecast_ref = cas.ArtifactRef.model_validate(raw_forecast)
        request_ref = cas.ArtifactRef.model_validate(scenario.metadata.get("native_request_ref"))
        _edge(store, report_ref, forecast_ref, forecast_role)
        cohort_ref = cas.ArtifactRef.model_validate(scenario.metadata.get("replica_cohort_ref"))
        _edge(store, report_ref, cohort_ref, cohort_role)
        cohort = _load_selected_native_cohort(store, cohort_ref)
        if (
            cohort.plan_id != scenario.scenario_id
            or cohort.requested_count != 1
            or cohort.started_count != 1
            or cohort.foundry_execute_count != 1
            or len(cohort.replicas) != 1
        ):
            raise ValueError("native report replica cohort differs from request")
        replica = cohort.replicas[0]
        forecast, request, failures = _verify_native_replica(
            store, cohort_ref, cohort, replica, forecast_ref, request_ref, index=1
        )
        step_count = scenario.metadata.get("native_foundry_step_count")
        if type(step_count) is not int or step_count != len(forecast.simulation_refs):
            raise ValueError("native report step count differs from verified trajectory")
        expected_mode = "scientist" if replica.workflow_status == "ok" else "scientist_candidate"
        if (
            scenario.metadata.get("native_workflow_status") != replica.workflow_status
            or scenario.metadata.get("native_workflow_failures") != failures
        ):
            raise ValueError("native report workflow status or forecast evidence mismatch")
        if (
            scenario.metadata.get("prediction_source_effective") != expected_mode
            or scenario.metadata.get("degraded") is not True
            or (
                replica.workflow_status != "ok"
                and not any(
                    reason == "scientist_replica_cohort_incomplete" for reason in scenario_reasons
                )
            )
        ):
            raise ValueError("native report replica status or candidate limitation mismatch")
        if scenario.metadata.get("native_forecast_purpose") != request.profile.purpose:
            raise ValueError("native report purpose differs from forecast request")
        if scenario.metadata.get("native_randomness_scope") != request.randomness_scope:
            raise ValueError("native report randomness scope differs from forecast request")
        if (
            scenario.metadata.get("native_limitations") != request.limitations
            or "native_predictive_simulation_only" not in scenario_reasons
            or any(limitation not in scenario_reasons for limitation in request.limitations)
        ):
            raise ValueError("native report declared limitations are incomplete")
        actual: dict[str, list[float]] = {}
        for row in scenario.outcome_comparisons:
            if row.ci_lower is not None or row.ci_upper is not None or row.within_ci is not None:
                raise ValueError("native replay does not establish predictive intervals")
            actual.setdefault(row.metric_name, []).append(row.y_pred)
        if actual != forecast.values or scenario.compared_count != sum(
            len(values) for values in forecast.values.values()
        ):
            raise ValueError("native report predictions differ from verified trajectory")
        source_data = cas.load_core_json_artifact(store, request.source_data_ref)
        if not isinstance(source_data, dict):
            raise ValueError("native report source data must be an object")
        actual_truth: dict[str, list[float]] = {}
        for row in scenario.outcome_comparisons:
            actual_truth.setdefault(row.metric_name, []).append(row.y_true)
        if actual_truth != _source_holdout(source_data, request.profile, request.cutoff):
            raise ValueError("native report outcomes differ from selected source holdout")
        native_count += 1
        verified_roles.append(forecast_role)
    if not native_count and not unavailable_count:
        raise ValueError("native report has no selected native forecast or unavailable scenario")
    if sorted(native_roles) != sorted(verified_roles):
        raise ValueError("native report forecast edge census differs from scenarios")
    modes = [scenario.metadata.get("prediction_source_effective") for scenario in report.scenarios]
    if any(not isinstance(mode, str) or not mode for mode in modes):
        raise ValueError("native report scenario prediction mode is missing")
    unique_modes = set(modes)
    expected_report_mode = next(iter(unique_modes)) if len(unique_modes) == 1 else "mixed"
    if report.prediction_mode_effective != expected_report_mode:
        raise ValueError("native report prediction mode differs from its scenarios")
    if (
        not report.degraded
        or report.trust_eligible
        or report.trust_score is not None
        or report.trust_grade is not None
    ):
        raise ValueError("native predictive simulation cannot establish trust authority")
    return report


def load_backtest_report_for_consumption(
    store: cas.CoreJSONArtifactStore, report_ref: ArtifactRefModel | cas.ArtifactRef
) -> BacktestReport:
    """Load a legacy report or verify every selected native source before use."""
    from polisyos.ir.analytics.backtest import (
        NativeBacktestVerificationRequiredError,
        load_backtest_report,
    )
    from polisyos.ir.registry.refs import BacktestReportRef

    selected = BacktestReportRef.model_validate(
        report_ref.model_dump(mode="json")
        if isinstance(report_ref, cas.ArtifactRef)
        else report_ref
    )
    try:
        return load_backtest_report(cas.ensure_ir_artifact_store(store), selected)
    except NativeBacktestVerificationRequiredError:
        core_ref = cas.ArtifactRef.model_validate(selected.model_dump(mode="json"))
        return load_native_backtest_report(store, core_ref)
