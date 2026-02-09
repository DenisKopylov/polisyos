from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from polisyos.core.artifacts.manifest import InputRef
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.core.contracts.fabric import DataSnapshot
from polisyos.core.contracts.foundry import SimulationResult, StateSnapshotRef
from polisyos.foundry.analysis.distributional import (
    build_distributional_report,
    build_geography_breakdown,
    build_income_quintile_breakdown,
)
from polisyos.foundry.executor import load_state_snapshot
from polisyos.ir.analytics.distributional import persist_distributional_report
from polisyos.scientist.engine.context import ExecutionContext
from polisyos.scientist.engine.protocol import NodeEvent, NodeOutcome, NodeSpec
from polisyos.scientist.engine.state import ExperimentState
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_DISTRIBUTIONAL_REPORT_REF,
    ARTIFACT_SIMULATION_RESULT_REF,
    INPUT_DATA_SNAPSHOT_REF,
    INPUT_STATE_SNAPSHOT_REF,
)

_METADATA = ComponentMetadata(
    component_id=ComponentId.parse("scientist.node_run_distributional_analysis@1.0.0"),
    kind=ComponentKind.SCIENTIST_NODE,
    abi_targets={"world_abi": "1.x"},
    display_name="Run Distributional Analysis",
    description="Build DistributionalReport from simulation state snapshots.",
    tags=["builtin", "simulate", "distributional"],
    capabilities=Capability.SCIENTIST_NODE,
)

_SPEC = NodeSpec(
    metadata=_METADATA,
    state_reads=[
        f"artifacts_index.{ARTIFACT_SIMULATION_RESULT_REF}",
        f"inputs.{INPUT_STATE_SNAPSHOT_REF}",
        f"inputs.{INPUT_DATA_SNAPSHOT_REF}",
    ],
    state_writes=[f"artifacts_index.{ARTIFACT_DISTRIBUTIONAL_REPORT_REF}"],
    produces=[ARTIFACT_DISTRIBUTIONAL_REPORT_REF],
)


@dataclass(frozen=True)
class RunDistributionalAnalysisNode:
    @property
    def spec(self) -> NodeSpec:
        return _SPEC

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        sim_result_ref = state.artifacts_index.get(ARTIFACT_SIMULATION_RESULT_REF)
        if sim_result_ref is None:
            return NodeOutcome(
                status="skip",
                state=state,
                events=[NodeEvent(level="info", message="No simulation_result_ref; skip distributional analysis")],
            )

        try:
            sim_payload = from_canonical_bytes(ctx.store.get_bytes(sim_result_ref.artifact_id))
            sim_result = SimulationResult.model_validate(sim_payload)
        except Exception as exc:
            return NodeOutcome(
                status="skip",
                state=state,
                events=[NodeEvent(level="warn", message=f"Unable to load SimulationResult: {exc}")],
            )

        if sim_result.state_snapshot_ref is None:
            return NodeOutcome(
                status="skip",
                state=state,
                events=[NodeEvent(level="info", message="SimulationResult has no state_snapshot_ref; skip distributional analysis")],
            )

        baseline_ref = _resolve_baseline_snapshot_ref(ctx, state)
        if baseline_ref is None:
            return NodeOutcome(
                status="skip",
                state=state,
                events=[NodeEvent(level="info", message="No baseline snapshot available; skip distributional analysis")],
            )

        try:
            baseline_state = load_state_snapshot(ctx.store, snapshot_ref=baseline_ref)
            simulated_state = load_state_snapshot(ctx.store, snapshot_ref=sim_result.state_snapshot_ref)
        except Exception as exc:
            return NodeOutcome(
                status="skip",
                state=state,
                events=[NodeEvent(level="warn", message=f"Unable to load state snapshots: {exc}")],
            )

        incomes_before = np.asarray(baseline_state.agents.income, dtype=np.float64)
        incomes_after = np.asarray(simulated_state.agents.income, dtype=np.float64)
        if incomes_before.size < 10 or incomes_after.size < 10:
            return NodeOutcome(
                status="skip",
                state=state,
                events=[NodeEvent(level="info", message="Insufficient agents for distributional analysis")],
            )

        breakdowns = [build_income_quintile_breakdown(incomes_before, incomes_after)]

        geography_breakdown = _try_build_geography_breakdown(
            incomes_before=incomes_before,
            incomes_after=incomes_after,
            simulated_state=simulated_state,
        )
        if geography_breakdown is not None:
            breakdowns.append(geography_breakdown)

        report = build_distributional_report(
            breakdowns,
            incomes_before=incomes_before,
            incomes_after=incomes_after,
            source_simulation_ref=str(sim_result_ref.artifact_id),
            metadata={"run_id": state.run_id},
        )
        report_inputs = [
            InputRef(artifact_id=sim_result_ref.artifact_id, role="simulation_result"),
            InputRef(artifact_id=sim_result.state_snapshot_ref.artifact_id, role="simulated_state_snapshot"),
            InputRef(artifact_id=baseline_ref.artifact_id, role="baseline_state_snapshot"),
        ]
        report_ref = persist_distributional_report(ctx.store, report, inputs=report_inputs)

        new_state = state.model_copy(deep=True)
        new_state.artifacts_index[ARTIFACT_DISTRIBUTIONAL_REPORT_REF] = report_ref
        return NodeOutcome(
            status="ok",
            state=new_state,
            artifacts=[report_ref],
            events=[
                NodeEvent(
                    level="info",
                    message=f"Distributional report generated with {len(report.breakdowns)} breakdown(s)",
                )
            ],
        )


def _resolve_baseline_snapshot_ref(
    ctx: ExecutionContext,
    state: ExperimentState,
) -> StateSnapshotRef | None:
    explicit = state.inputs.get(INPUT_STATE_SNAPSHOT_REF)
    if explicit is not None:
        try:
            return StateSnapshotRef.model_validate(explicit.model_dump())
        except Exception:
            return None

    data_snapshot_ref = state.inputs.get(INPUT_DATA_SNAPSHOT_REF)
    if data_snapshot_ref is None:
        return None
    try:
        payload = from_canonical_bytes(ctx.store.get_bytes(data_snapshot_ref.artifact_id))
        snapshot = DataSnapshot.model_validate(payload)
    except Exception:
        return None
    if snapshot.data_ref.kind != "foundry.state_snapshot":
        return None
    return StateSnapshotRef(artifact_id=snapshot.data_ref.artifact_id)


def _try_build_geography_breakdown(
    *,
    incomes_before: np.ndarray,
    incomes_after: np.ndarray,
    simulated_state: object,
):
    region_ids = getattr(simulated_state.agents, "employer_id", None)
    if region_ids is None:
        return None
    region_ids_arr = np.asarray(region_ids)
    if region_ids_arr.ndim != 1:
        return None
    if region_ids_arr.shape[0] != incomes_after.shape[0]:
        return None
    mask = region_ids_arr >= 0
    if int(np.sum(mask)) < 2:
        return None
    region_ids_clean = region_ids_arr[mask]
    if np.unique(region_ids_clean).size < 2:
        return None
    labels = {int(region): f"Employer Region {int(region)}" for region in np.unique(region_ids_clean)}
    try:
        return build_geography_breakdown(
            region_ids_clean,
            labels,
            incomes_before[mask],
            incomes_after[mask],
            primary_metric="regional_income_change_pct",
        )
    except Exception:
        return None


__all__ = ["RunDistributionalAnalysisNode"]
