"""Content-bound predictive trajectories through the existing Foundry executor.

This adapter advances the declared forecast clock and reads registered state
slots after each native execution. It does not interpret execution counters,
treatment effects or uncertainty intervals as future observations.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from typing import TYPE_CHECKING, Any, Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.core import artifacts as core_artifacts
from polisyos.core import canon as core_canon
from polisyos.core import registry as core_registry
from polisyos.core.contracts import (
    DataSnapshot,
    DerivedArtifact,
    ExecPlan,
    ExecuteRequest,
    ExecuteResult,
    FoundryExecConfig,
    FoundryInputBindingRule,
    FoundryInputBindings,
    FoundryInputBindingsRef,
    LoweredIR,
    ProgramGraph,
    SimulationResult,
    StateSnapshotRef,
)
from polisyos.foundry.execute.executor import (
    get_state_path,
    load_state_snapshot,
    put_state_snapshot,
)
from polisyos.ir import TrinityBundle

if TYPE_CHECKING:
    from polisyos.scientist.methods.backtesting.plan import HistoricalValidationPlan
    from polisyos.scientist.orchestration.engine.context import ExecutionContext

PROFILE_KEY = "backtest_native_forecast"
REQUEST_KEY = "backtest_native_forecast_request_ref"
FORECAST_KEY = "backtest_native_forecast_ref"
_REQUEST_KIND = "scientist.backtest.native_forecast_request"
_FORECAST_KIND = "scientist.backtest.native_forecast"


class NativeForecastTarget(BaseModel):
    """Declared future observable resolved against a registered state slot/unit."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    metric: str = Field(min_length=1)
    slot_id: str = Field(min_length=1)
    unit_id: str = Field(min_length=1)
    reduction: Literal["mean", "sum", "identity"]


class NativeForecastProfile(BaseModel):
    """Predictive simulation scope with explicit history columns and future times."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    purpose: Literal["predictive_simulation"]
    origin: str = Field(min_length=1)
    time_index: list[str] = Field(min_length=1)
    history_columns: list[str] = Field(min_length=1)
    targets: list[NativeForecastTarget] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_axes(self) -> NativeForecastProfile:
        for values in [self.time_index, self.history_columns, [x.metric for x in self.targets]]:
            if len(set(values)) != len(values):
                raise ValueError("native forecast axes and target metrics must be unique")
        if self.origin != self.time_index[0]:
            raise ValueError("native forecast origin must be the first future time")
        return self


class NativeForecastRequest(BaseModel):
    """Immutable admitted profile and exact historical/model/runtime identities."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal["1.0"] = "1.0"
    profile: NativeForecastProfile
    data_snapshot_ref: core_artifacts.ArtifactRef
    trinity_bundle_ref: core_artifacts.ArtifactRef
    registry_bundle_ref: core_artifacts.ArtifactRef
    row_ids: list[str]
    history_time_index: list[str]
    run_id: str = Field(min_length=1)
    seed: int = Field(strict=True, ge=0)


class NativeForecastTrajectory(BaseModel):
    """Native state observations with every simulation/snapshot/config reference."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal["1.0"] = "1.0"
    request_ref: core_artifacts.ArtifactRef
    exec_config_ref: core_artifacts.ArtifactRef
    input_bindings_ref: core_artifacts.ArtifactRef
    execution_bindings_refs: list[core_artifacts.ArtifactRef]
    simulation_refs: list[core_artifacts.ArtifactRef]
    state_snapshot_refs: list[core_artifacts.ArtifactRef]
    values: dict[str, list[float]]


def _schema_version(value: str) -> tuple[int, ...]:
    parts = [int(x) for x in value.split(".")]
    while len(parts) > 2 and parts[-1] == 0:
        parts.pop()
    return tuple(parts)


def _read(
    store: core_artifacts.ArtifactStore,
    ref: core_artifacts.ArtifactRef,
    kind: str,
    schema: str | None = None,
) -> Any:
    manifest = store.get_manifest(ref)
    if ref.kind != kind or manifest.kind != kind or manifest.media_type != "application/json":
        raise ValueError(f"native replay artifact kind/media mismatch: {kind}")
    if schema is not None and (
        manifest.artifact_schema is None or manifest.artifact_schema.name != schema
    ):
        raise ValueError(f"native replay artifact schema mismatch: {schema}")
    payload = core_canon.from_canonical_bytes(store.get_bytes(ref))
    if (
        manifest.artifact_schema is not None
        and isinstance(payload, dict)
        and (
            "schema_version" in payload
            and _schema_version(manifest.artifact_schema.version)
            != _schema_version(str(payload["schema_version"]))
        )
    ):
        raise ValueError("native replay artifact schema version differs from payload")
    return payload


def _put(
    store: core_artifacts.ArtifactStore,
    payload: BaseModel | dict[str, Any],
    kind: str,
    schema: str,
    *,
    inputs: list[core_artifacts.ArtifactRef],
    version: str = "1.0",
) -> core_artifacts.ArtifactRef:
    return store.put_json(
        payload,
        core_artifacts.PutOptions(
            kind=kind,
            media_type="application/json",
            schema=core_artifacts.SchemaInfo(name=schema, version=version),
            inputs=[
                core_artifacts.input_ref_from_artifact_ref(ref, role=f"input.{index}")
                for index, ref in enumerate(inputs)
            ],
        ),
        canon_spec=core_canon.CanonSpec(forbid_floats=False),
    )


def _targets(
    store: core_artifacts.ArtifactStore,
    profile: NativeForecastProfile,
    registry_ref: core_artifacts.ArtifactRef,
):
    registry = core_registry.load_registry_bundle_content(store, registry_ref)
    for target in profile.targets:
        slot = registry.slot_registry.slots.get(target.slot_id)
        if slot is None or not slot.state_path or slot.unit.unit_id != target.unit_id:
            raise ValueError(f"native forecast target/slot/unit mismatch: {target.metric}")
    return registry


def prepare_native_replay(
    store: core_artifacts.ArtifactStore,
    plan: HistoricalValidationPlan,
    historical_data: dict[str, Any],
) -> dict[str, Any]:
    """Reconcile original identities, project the full declared history and derive Trinity.

    The original Trinity is validated before deriving its immutable masked child.
    Existing input bindings and stale forecast artifacts are refused, so they
    cannot bypass the default input-binding node.
    """
    state = deepcopy(plan.scientist_state)
    if not isinstance(state, dict):
        raise ValueError("native replay requires Scientist state")
    params = state.setdefault("params", {})
    inputs = state.setdefault("inputs", {})
    if set(state) - {"run_id", "inputs", "params"}:
        raise ValueError("native replay refuses preexisting workflow artifacts or state")
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
        raise ValueError("native replay requires the existing default Scientist workflow")
    if plan.masking_strategy.value not in {"drop_post", "truncate"}:
        raise ValueError("native replay requires an immutable finite historical prefix")
    profile = NativeForecastProfile.model_validate(params[PROFILE_KEY])
    if set(x.metric for x in profile.targets) != set(plan.target_metrics):
        raise ValueError("native forecast target metrics differ from backtest plan")
    horizon = len(profile.time_index)
    if any(len(plan.ground_truth_outcomes[x.metric]) != horizon for x in profile.targets):
        raise ValueError("native forecast horizon differs from backtest outcomes")
    if inputs.get("input_bindings_ref") or state.get("artifacts_index", {}).get(FORECAST_KEY):
        raise ValueError("native replay refuses prebound inputs or preexisting forecasts")
    source_ref = core_artifacts.ArtifactRef.model_validate(inputs["data_snapshot_ref"])
    source = DataSnapshot.model_validate(
        _read(store, source_ref, "fabric.data_snapshot", "polisyos.core.DataSnapshot")
    )
    source_rows = _read(store, source.data_ref, source.data_ref.kind)
    if source_rows != historical_data or (
        plan.historical_data_ref is not None
        and str(source.data_ref.artifact_id) != plan.historical_data_ref
    ):
        raise ValueError("native replay source snapshot differs from historical source")
    original_trinity_ref = core_artifacts.ArtifactRef.model_validate(inputs["trinity_bundle_ref"])
    trinity = TrinityBundle.model_validate(
        _read(store, original_trinity_ref, "ir.trinity_bundle", "polisyos.ir.TrinityBundle")
    )
    registry_ref = core_artifacts.ArtifactRef.model_validate(inputs["registry_bundle_ref"])
    if trinity.model_spec.data_snapshot_ref != str(source_ref.artifact_id):
        raise ValueError("native replay original Trinity data snapshot mismatch")
    if trinity.model_spec.registry_bundle_ref != str(registry_ref.artifact_id):
        raise ValueError("native replay original Trinity registry mismatch")
    if trinity.model_spec.agent_config.network_graph_ref or any(
        parameter.time_series_ref for parameter in trinity.model_spec.environment_config.params
    ):
        raise ValueError("native replay refuses unscoped model data dependencies")
    _targets(store, profile, registry_ref)
    full_time = historical_data.get("time_index")
    full_ids = historical_data.get("row_ids")
    cutoff = (
        plan.intervention_step
        if plan.intervention_step is not None
        else plan.pre_intervention_periods
    )
    if (
        not isinstance(full_time, list)
        or not isinstance(full_ids, list)
        or cutoff is None
        or cutoff <= 0
    ):
        raise ValueError("native replay requires row IDs, time coordinates and a nonempty prefix")
    if len(full_ids) != len(full_time) or len(set(full_ids)) != len(full_ids):
        raise ValueError("native replay historical row identity mismatch")
    if (
        full_time[cutoff : cutoff + horizon] != profile.time_index
        or profile.origin != plan.intervention_date
    ):
        raise ValueError(
            "native replay future time coordinates differ from declared cutoff/horizon"
        )
    projected: dict[str, Any] = {"time_index": full_time[:cutoff], "row_ids": full_ids[:cutoff]}
    for column in profile.history_columns:
        values = historical_data.get(column)
        if not isinstance(values, list) or len(values) != len(full_time):
            raise ValueError(f"native replay history column is not time-aligned: {column}")
        if not np.all(np.isfinite(np.asarray(values[:cutoff], dtype=float))):
            raise ValueError(f"native replay history has nonfinite support: {column}")
        projected[column] = values[:cutoff]
    rules = params.get("foundry_input_binding_rules")
    if not isinstance(rules, list) or not rules:
        raise ValueError("native replay requires explicit input-binding rules")
    for raw_rule in rules:
        rule = FoundryInputBindingRule.model_validate(raw_rule)
        tokens = rule.source_path.split(".")
        if (
            len(tokens) != 2
            or tokens[0] not in profile.history_columns
            or not tokens[1].isdigit()
            or int(tokens[1]) >= cutoff
            or rule.default_value is not None
        ):
            raise ValueError(
                "native replay input binding is outside the admitted historical prefix"
            )
    data_ref = _put(
        store,
        projected,
        "scientist.backtest.masked_historical_view",
        "polisyos.scientist.backtesting.MaskedHistoricalView",
        inputs=[source.data_ref],
    )
    snapshot_ref = _put(
        store,
        DataSnapshot(data_ref=data_ref),
        "fabric.data_snapshot",
        "polisyos.core.DataSnapshot",
        inputs=[data_ref, source_ref],
        version="0.2.0",
    )
    model = trinity.model_spec.model_copy(
        update={"data_snapshot_ref": str(snapshot_ref.artifact_id)}
    )
    child = trinity.model_copy(update={"model_spec": model})
    trinity_ref = _put(
        store,
        child,
        "ir.trinity_bundle",
        "polisyos.ir.TrinityBundle",
        inputs=[original_trinity_ref, snapshot_ref],
        version=child.schema_version,
    )
    request = NativeForecastRequest(
        profile=profile,
        data_snapshot_ref=snapshot_ref,
        trinity_bundle_ref=trinity_ref,
        registry_bundle_ref=registry_ref,
        row_ids=full_ids[:cutoff],
        history_time_index=full_time[:cutoff],
        run_id=state["run_id"],
        seed=plan.random_seed,
    )
    request_ref = _put(
        store,
        request,
        _REQUEST_KIND,
        "polisyos.scientist.backtesting.NativeForecastRequest",
        inputs=[snapshot_ref, trinity_ref, registry_ref],
    )
    inputs.update(
        data_snapshot_ref=snapshot_ref.model_dump(mode="json"),
        trinity_bundle_ref=trinity_ref.model_dump(mode="json"),
    )
    params.update(
        random_seed=request.seed,
        n_simulation_runs=1,
        backtest_native_forecast_request_ref=request_ref.model_dump(mode="json"),
    )
    return state


def _observations(
    store: core_artifacts.ArtifactStore,
    request: NativeForecastRequest,
    snapshots: list[core_artifacts.ArtifactRef],
) -> dict[str, list[float]]:
    registry = _targets(store, request.profile, request.registry_bundle_ref)
    values = {target.metric: [] for target in request.profile.targets}
    for snapshot in snapshots:
        state = load_state_snapshot(store, snapshot_ref=snapshot)
        for target in request.profile.targets:
            slot = registry.slot_registry.slots[target.slot_id]
            array = np.asarray(get_state_path(state, slot.state_path), dtype=float)
            if array.size == 0 or not np.all(np.isfinite(array)):
                raise ValueError("native forecast state observable has failed support")
            if target.reduction == "identity" and array.size != 1:
                raise ValueError("native forecast identity requires one scalar observable")
            value = float(np.sum(array) if target.reduction == "sum" else np.mean(array))
            values[target.metric].append(value)
    return values


def _same_ref(left: core_artifacts.ArtifactRef, right: core_artifacts.ArtifactRef) -> bool:
    return left.model_dump(mode="json") == right.model_dump(mode="json")


def _require_lineage(
    store: core_artifacts.ArtifactStore,
    ref: core_artifacts.ArtifactRef,
    parent: core_artifacts.ArtifactRef,
    role: str,
) -> None:
    expected = core_artifacts.input_ref_from_artifact_ref(parent, role=role).model_dump(mode="json")
    if not any(edge.model_dump(mode="json") == expected for edge in store.get_manifest(ref).inputs):
        raise ValueError(f"native forecast missing exact {role} lineage")


def _validate_compiled_model(
    store: core_artifacts.ArtifactStore,
    request: NativeForecastRequest,
    exec_plan_ref: core_artifacts.ArtifactRef,
) -> None:
    """Resolve the actual execution program back to its compiled Trinity/model."""
    plan = ExecPlan.model_validate(_read(store, exec_plan_ref, "foundry.exec_plan"))
    program = ProgramGraph.model_validate(_read(store, plan.program_ref, "foundry.program_graph"))
    if not _same_ref(program.ir_ref, request.trinity_bundle_ref) or program.lowered_ir_ref is None:
        raise ValueError("native forecast executed program differs from declared Trinity")
    lowered = LoweredIR.model_validate(_read(store, program.lowered_ir_ref, "foundry.lowered_ir"))
    if not _same_ref(lowered.ir_ref, request.trinity_bundle_ref):
        raise ValueError("native forecast executed LoweredIR differs from declared Trinity")
    trinity = TrinityBundle.model_validate(
        _read(store, request.trinity_bundle_ref, "ir.trinity_bundle")
    )
    if trinity.model_spec.data_snapshot_ref != str(
        request.data_snapshot_ref.artifact_id
    ) or trinity.model_spec.registry_bundle_ref != str(request.registry_bundle_ref.artifact_id):
        raise ValueError("native forecast compiled model source/registry mismatch")


def execute_native_forecast(
    ctx: ExecutionContext,
    execution: ExecuteRequest,
    request_ref: core_artifacts.ArtifactRef,
) -> ExecuteResult:
    """Execute each declared future step through the configured native Foundry port."""
    request = NativeForecastRequest.model_validate(_read(ctx.store, request_ref, _REQUEST_KIND))
    bindings = FoundryInputBindings.model_validate(
        _read(ctx.store, execution.input_bindings_ref, "foundry.input_bindings")
    )
    if request.run_id != ctx.run.run_manifest.run_id or request.seed != execution.exec_config.seed:
        raise ValueError("native forecast actual run/seed differs from admitted request")
    if (
        bindings.data_snapshot_ref != request.data_snapshot_ref
        or bindings.registry_bundle_ref != request.registry_bundle_ref
    ):
        raise ValueError("native forecast actual input bindings differ from admitted request")
    trinity = TrinityBundle.model_validate(
        _read(ctx.store, request.trinity_bundle_ref, "ir.trinity_bundle")
    )
    if trinity.model_spec.data_snapshot_ref != str(bindings.data_snapshot_ref.artifact_id):
        raise ValueError("native forecast Trinity is not bound to the consumed snapshot")
    _targets(ctx.store, request.profile, request.registry_bundle_ref)
    config_ref = _put(
        ctx.store,
        execution.exec_config,
        "foundry.exec_config",
        "polisyos.core.FoundryExecConfig",
        inputs=[request_ref],
    )
    initial_ref = bindings.bound_state_snapshot_ref
    initial_bindings_ref = execution.input_bindings_ref
    execution_bindings_refs: list[core_artifacts.ArtifactRef] = []
    simulation_refs: list[core_artifacts.ArtifactRef] = []
    snapshots: list[core_artifacts.ArtifactRef] = []
    result: ExecuteResult | None = None
    base = load_state_snapshot(ctx.store, snapshot_ref=initial_ref)
    initial_step = int(np.asarray(base.step))
    _validate_compiled_model(ctx.store, request, execution.exec_plan_ref)
    for index in range(len(request.profile.time_index)):
        if index:
            base = load_state_snapshot(ctx.store, snapshot_ref=snapshots[-1])
            advanced = replace(
                base, step=np.asarray(initial_step + index, dtype=np.asarray(base.step).dtype)
            )
            advanced_ref = put_state_snapshot(
                ctx.store,
                state=advanced,
                step=initial_step + index,
                inputs=[
                    core_artifacts.input_ref_from_artifact_ref(
                        snapshots[-1], role="previous_forecast_state"
                    )
                ],
            )
            next_bindings = bindings.model_copy(
                update={
                    "bound_state_snapshot_ref": StateSnapshotRef.model_validate(
                        advanced_ref.model_dump()
                    )
                }
            )
            binding_ref = _put(
                ctx.store,
                next_bindings,
                "foundry.input_bindings",
                "polisyos.core.FoundryInputBindings",
                inputs=[execution.input_bindings_ref, advanced_ref],
            )
            execution = execution.model_copy(
                update={
                    "input_bindings_ref": FoundryInputBindingsRef.model_validate(
                        binding_ref.model_dump()
                    )
                }
            )
        if ctx.foundry is None:
            raise ValueError("native forecast requires configured Foundry port")
        execution_bindings_refs.append(execution.input_bindings_ref)
        result = ctx.foundry.execute(ctx.store, execution)
        if not result.ok or result.simulation_result_ref is None:
            raise ValueError("native forecast execution produced no successful simulation")
        simulation = SimulationResult.model_validate(
            _read(ctx.store, result.simulation_result_ref, "foundry.simulation_result")
        )
        if (
            simulation.exec_plan_ref != execution.exec_plan_ref
            or simulation.state_snapshot_ref is None
        ):
            raise ValueError("native forecast requires actual matching post-execution state")
        simulation_refs.append(result.simulation_result_ref)
        snapshots.append(simulation.state_snapshot_ref)
    trajectory = NativeForecastTrajectory(
        request_ref=request_ref,
        exec_config_ref=config_ref,
        input_bindings_ref=initial_bindings_ref,
        execution_bindings_refs=execution_bindings_refs,
        simulation_refs=simulation_refs,
        state_snapshot_refs=snapshots,
        values=_observations(ctx.store, request, snapshots),
    )
    forecast_ref = _put(
        ctx.store,
        trajectory,
        _FORECAST_KIND,
        "polisyos.scientist.backtesting.NativeForecastTrajectory",
        inputs=[request_ref, config_ref, *execution_bindings_refs, *simulation_refs, *snapshots],
    )
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
    store: core_artifacts.ArtifactStore,
    forecast_ref: core_artifacts.ArtifactRef,
    request_ref: core_artifacts.ArtifactRef,
) -> tuple[NativeForecastTrajectory, NativeForecastRequest]:
    """Read the persisted trajectory and independently recompute its state observations."""
    forecast = NativeForecastTrajectory.model_validate(
        _read(
            store,
            forecast_ref,
            _FORECAST_KIND,
            "polisyos.scientist.backtesting.NativeForecastTrajectory",
        )
    )
    if forecast.request_ref != request_ref:
        raise ValueError("native forecast request identity mismatch")
    request = NativeForecastRequest.model_validate(_read(store, request_ref, _REQUEST_KIND))
    config = FoundryExecConfig.model_validate(
        _read(store, forecast.exec_config_ref, "foundry.exec_config")
    )
    if config.seed != request.seed or len(forecast.state_snapshot_refs) != len(
        request.profile.time_index
    ):
        raise ValueError("native forecast seed/horizon mismatch")
    if len(forecast.simulation_refs) != len(forecast.state_snapshot_refs) or len(
        forecast.execution_bindings_refs
    ) != len(forecast.state_snapshot_refs):
        raise ValueError("native forecast simulation/snapshot axis mismatch")
    if not _same_ref(forecast.input_bindings_ref, forecast.execution_bindings_refs[0]):
        raise ValueError("native forecast initial binding anchor differs from first execution")
    initial_binding = FoundryInputBindings.model_validate(
        _read(store, forecast.input_bindings_ref, "foundry.input_bindings")
    )
    _require_lineage(
        store, forecast.input_bindings_ref, request.data_snapshot_ref, "input.data_snapshot_ref"
    )
    _require_lineage(
        store, forecast.input_bindings_ref, request.registry_bundle_ref, "input.registry_bundle_ref"
    )
    _require_lineage(
        store,
        forecast.input_bindings_ref,
        initial_binding.bound_state_snapshot_ref,
        "artifact.bound_state_snapshot_ref",
    )
    _require_lineage(
        store,
        initial_binding.bound_state_snapshot_ref,
        request.data_snapshot_ref,
        "input.data_snapshot_ref",
    )
    _require_lineage(
        store,
        initial_binding.bound_state_snapshot_ref,
        request.registry_bundle_ref,
        "input.registry_bundle_ref",
    )
    initial_step = int(
        np.asarray(
            load_state_snapshot(store, snapshot_ref=initial_binding.bound_state_snapshot_ref).step
        )
    )
    previous_snapshot: core_artifacts.ArtifactRef | None = None
    exec_plan_ref: core_artifacts.ArtifactRef | None = None
    for index, (simulation_ref, snapshot, binding_ref) in enumerate(
        zip(
            forecast.simulation_refs,
            forecast.state_snapshot_refs,
            forecast.execution_bindings_refs,
            strict=True,
        )
    ):
        binding = FoundryInputBindings.model_validate(
            _read(store, binding_ref, "foundry.input_bindings")
        )
        if (
            binding.data_snapshot_ref != request.data_snapshot_ref
            or binding.registry_bundle_ref != request.registry_bundle_ref
        ):
            raise ValueError("native forecast persisted bindings changed source/registry")
        # Each future coordinate advances the anchored materializer's native
        # clock by one step, preserving the actual predecessor state chain.
        bound = load_state_snapshot(store, snapshot_ref=binding.bound_state_snapshot_ref)
        observed = load_state_snapshot(store, snapshot_ref=snapshot)
        if (
            int(np.asarray(bound.step)) != initial_step + index
            or int(np.asarray(observed.step)) != initial_step + index
        ):
            raise ValueError("native forecast chronological clock/order mismatch")
        if previous_snapshot is not None:
            _require_lineage(
                store,
                binding.bound_state_snapshot_ref,
                previous_snapshot,
                "previous_forecast_state",
            )
        _require_lineage(store, snapshot, binding.bound_state_snapshot_ref, "base_state")
        simulation = SimulationResult.model_validate(
            _read(store, simulation_ref, "foundry.simulation_result")
        )
        lineage = store.get_manifest(simulation_ref).inputs
        if not any(
            edge.role == "input.input_bindings_ref" and edge.artifact_id == binding_ref.artifact_id
            for edge in lineage
        ):
            raise ValueError("native forecast simulation did not consume declared bindings")
        _validate_compiled_model(store, request, simulation.exec_plan_ref)
        if exec_plan_ref is not None and not _same_ref(exec_plan_ref, simulation.exec_plan_ref):
            raise ValueError("native forecast execution plan changed along the trajectory")
        exec_plan_ref = simulation.exec_plan_ref
        if simulation.state_snapshot_ref is None or simulation.state_snapshot_ref.model_dump(
            mode="json"
        ) != snapshot.model_dump(mode="json"):
            raise ValueError("native forecast state is not a consumed simulation output")
        previous_snapshot = snapshot
    if forecast.values != _observations(store, request, forecast.state_snapshot_refs):
        raise ValueError("native forecast values differ from recomputed state observations")
    return forecast, request
