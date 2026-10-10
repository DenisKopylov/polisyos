"""Public simulate run distributional analysis module API."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from pydantic import ValidationError

from polisyos.core.artifacts import ensure_ir_artifact_store as _ensure_ir_artifact_store
from polisyos.core.artifacts.manifest import InputRef
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.core.contracts.fabric import DataSnapshot
from polisyos.core.contracts.foundry import FoundryInputBindings, SimulationResult, StateSnapshotRef
from polisyos.foundry.analysis.distributional import (
    build_distributional_report,
    build_income_quintile_breakdown,
)
from polisyos.foundry.execute.executor import load_state_snapshot
from polisyos.foundry.methods.catalog.causal.density_ratio import (
    compute_scalar_distributional_effect,
)
from polisyos.ir.analytics.distributional import (
    DistributionalEffectBundle,
    DistributionalJustification,
    persist_distributional_effect_bundle,
    persist_distributional_report,
)
from polisyos.scientist.nodes.builtins.simulate.distributional_analysis_artifacts import (
    _coupling_diagnostics as _coupling_diagnostics,
)
from polisyos.scientist.nodes.builtins.simulate.distributional_analysis_artifacts import (
    _coupling_summary as _coupling_summary,
)
from polisyos.scientist.nodes.builtins.simulate.distributional_analysis_artifacts import (
    _distribution_summary as _distribution_summary,
)
from polisyos.scientist.nodes.builtins.simulate.distributional_analysis_artifacts import (
    _maybe_none as _maybe_none,
)
from polisyos.scientist.nodes.builtins.simulate.distributional_analysis_artifacts import (
    _persist_scalar_artifacts as _persist_scalar_artifacts,
)
from polisyos.scientist.nodes.builtins.simulate.distributional_analysis_artifacts import (
    _persist_subgroup_artifacts as _persist_subgroup_artifacts,
)
from polisyos.scientist.nodes.builtins.simulate.distributional_analysis_artifacts import (
    _persist_subgroup_comparison as _persist_subgroup_comparison,
)
from polisyos.scientist.nodes.builtins.simulate.distributional_analysis_artifacts import (
    _PersistedScalarArtifacts as _PersistedScalarArtifacts,
)
from polisyos.scientist.nodes.builtins.simulate.distributional_analysis_artifacts import (
    _quantile_summary as _quantile_summary,
)
from polisyos.scientist.nodes.builtins.simulate.distributional_analysis_artifacts import (
    _recommended_n_bins as _recommended_n_bins,
)
from polisyos.scientist.nodes.builtins.simulate.distributional_analysis_artifacts import (
    _tail_summary as _tail_summary,
)
from polisyos.scientist.nodes.builtins.simulate.distributional_analysis_bounds import (
    _axis_values_from_request as _axis_values_from_request,
)
from polisyos.scientist.nodes.builtins.simulate.distributional_analysis_bounds import (
    _distributional_bounds_config as _distributional_bounds_config,
)
from polisyos.scientist.nodes.builtins.simulate.distributional_analysis_bounds import (
    _distributional_bounds_functional_axes as _distributional_bounds_functional_axes,
)
from polisyos.scientist.nodes.builtins.simulate.distributional_analysis_bounds import (
    _distributional_bounds_requests as _distributional_bounds_requests,
)
from polisyos.scientist.nodes.builtins.simulate.distributional_analysis_bounds import (
    _distributional_bounds_state_payload as _distributional_bounds_state_payload,
)
from polisyos.scientist.nodes.builtins.simulate.distributional_analysis_bounds import (
    _distributional_bounds_uniformity as _distributional_bounds_uniformity,
)
from polisyos.scientist.nodes.builtins.simulate.distributional_analysis_bounds import (
    _DistributionalBoundsResolution as _DistributionalBoundsResolution,
)
from polisyos.scientist.nodes.builtins.simulate.distributional_analysis_bounds import (
    _empty_distributional_bounds_resolution as _empty_distributional_bounds_resolution,
)
from polisyos.scientist.nodes.builtins.simulate.distributional_analysis_bounds import (
    _float_tuple as _float_tuple,
)
from polisyos.scientist.nodes.builtins.simulate.distributional_analysis_bounds import (
    _makarov_marginals_licensed as _makarov_marginals_licensed,
)
from polisyos.scientist.nodes.builtins.simulate.distributional_analysis_bounds import (
    _numeric_array as _numeric_array,
)
from polisyos.scientist.nodes.builtins.simulate.distributional_analysis_bounds import (
    _resolve_distributional_bounds as _resolve_distributional_bounds,
)
from polisyos.scientist.nodes.builtins.simulate.distributional_analysis_bounds import (
    _stable_unique as _stable_unique,
)
from polisyos.scientist.nodes.builtins.simulate.distributional_analysis_bounds import (
    _string_list as _string_list,
)
from polisyos.scientist.nodes.builtins.simulate.distributional_analysis_justification import (
    _ASSUMPTION_DESCRIPTIONS as _ASSUMPTION_DESCRIPTIONS,
)
from polisyos.scientist.nodes.builtins.simulate.distributional_analysis_justification import (
    _BASE_CAUSAL_ASSUMPTIONS as _BASE_CAUSAL_ASSUMPTIONS,
)
from polisyos.scientist.nodes.builtins.simulate.distributional_analysis_justification import (
    _TESTABLE_ASSUMPTIONS as _TESTABLE_ASSUMPTIONS,
)
from polisyos.scientist.nodes.builtins.simulate.distributional_analysis_justification import (
    _assumption_description as _assumption_description,
)
from polisyos.scientist.nodes.builtins.simulate.distributional_analysis_justification import (
    _assumption_scope as _assumption_scope,
)
from polisyos.scientist.nodes.builtins.simulate.distributional_analysis_justification import (
    _assumption_status as _assumption_status,
)
from polisyos.scientist.nodes.builtins.simulate.distributional_analysis_justification import (
    _assumption_theorem_family as _assumption_theorem_family,
)
from polisyos.scientist.nodes.builtins.simulate.distributional_analysis_justification import (
    _bound_uniformity_for_justification as _bound_uniformity_for_justification,
)
from polisyos.scientist.nodes.builtins.simulate.distributional_analysis_justification import (
    _causal_assumptions as _causal_assumptions,
)
from polisyos.scientist.nodes.builtins.simulate.distributional_analysis_justification import (
    _coupling_assumptions as _coupling_assumptions,
)
from polisyos.scientist.nodes.builtins.simulate.distributional_analysis_justification import (
    _coupling_negative_certificate as _coupling_negative_certificate,
)
from polisyos.scientist.nodes.builtins.simulate.distributional_analysis_justification import (
    _coupling_status_for_justification as _coupling_status_for_justification,
)
from polisyos.scientist.nodes.builtins.simulate.distributional_analysis_justification import (
    _distributional_theorem_family as _distributional_theorem_family,
)
from polisyos.scientist.nodes.builtins.simulate.distributional_analysis_justification import (
    _DistributionalJustificationResolution as _DistributionalJustificationResolution,
)
from polisyos.scientist.nodes.builtins.simulate.distributional_analysis_justification import (
    _maybe_persist_distributional_estimand_ast as _maybe_persist_distributional_estimand_ast,
)
from polisyos.scientist.nodes.builtins.simulate.distributional_analysis_justification import (
    _merge_assumptions as _merge_assumptions,
)
from polisyos.scientist.nodes.builtins.simulate.distributional_analysis_justification import (
    _persist_distributional_assumption_cards as _persist_distributional_assumption_cards,
)
from polisyos.scientist.nodes.builtins.simulate.distributional_analysis_justification import (
    _persist_distributional_proof_artifacts as _persist_distributional_proof_artifacts,
)
from polisyos.scientist.nodes.builtins.simulate.distributional_analysis_justification import (
    _PersistedAssumptionCards as _PersistedAssumptionCards,
)
from polisyos.scientist.nodes.builtins.simulate.distributional_analysis_justification import (
    _resolve_distributional_graph as _resolve_distributional_graph,
)
from polisyos.scientist.nodes.builtins.simulate.distributional_analysis_justification import (
    _resolve_distributional_justification as _resolve_distributional_justification,
)
from polisyos.scientist.nodes.builtins.simulate.distributional_analysis_justification import (
    _resolve_distributional_treatment_variable as _resolve_distributional_treatment_variable,
)
from polisyos.scientist.nodes.builtins.simulate.distributional_analysis_ordinal import (
    _coerce_optional_bool as _coerce_optional_bool,
)
from polisyos.scientist.nodes.builtins.simulate.distributional_analysis_ordinal import (
    _coerce_ordinal_category_matrix as _coerce_ordinal_category_matrix,
)
from polisyos.scientist.nodes.builtins.simulate.distributional_analysis_ordinal import (
    _coerce_ordinal_weights as _coerce_ordinal_weights,
)
from polisyos.scientist.nodes.builtins.simulate.distributional_analysis_ordinal import (
    _maybe_build_ordinal_poverty_report as _maybe_build_ordinal_poverty_report,
)
from polisyos.scientist.nodes.builtins.simulate.distributional_analysis_ordinal import (
    _ordinal_estimate_summary as _ordinal_estimate_summary,
)
from polisyos.scientist.nodes.builtins.simulate.distributional_analysis_ordinal import (
    _ordinal_poverty_summary_from_report as _ordinal_poverty_summary_from_report,
)
from polisyos.scientist.nodes.builtins.simulate.distributional_analysis_ordinal import (
    _OrdinalPovertyResolution as _OrdinalPovertyResolution,
)
from polisyos.scientist.nodes.builtins.simulate.distributional_analysis_ordinal import (
    _run_ordinal_poverty_estimate as _run_ordinal_poverty_estimate,
)
from polisyos.scientist.nodes.builtins.simulate.distributional_analysis_subgroups import (
    _GEOGRAPHY_MIN_GROUP_SIZE as _GEOGRAPHY_MIN_GROUP_SIZE,
)
from polisyos.scientist.nodes.builtins.simulate.distributional_analysis_subgroups import (
    _aligned_geography_subgroups as _aligned_geography_subgroups,
)
from polisyos.scientist.nodes.builtins.simulate.distributional_analysis_subgroups import (
    _build_aligned_geography_breakdown as _build_aligned_geography_breakdown,
)
from polisyos.scientist.nodes.builtins.simulate.distributional_analysis_subgroups import (
    _income_quintile_subgroups as _income_quintile_subgroups,
)
from polisyos.scientist.nodes.builtins.simulate.distributional_analysis_subgroups import (
    _SubgroupSpec as _SubgroupSpec,
)
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_DISTRIBUTIONAL_EFFECT_BUNDLE_REF,
    ARTIFACT_DISTRIBUTIONAL_REPORT_REF,
    ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF,
    ARTIFACT_SIMULATION_RESULT_REF,
    INPUT_DATA_SNAPSHOT_REF,
    INPUT_INPUT_BINDINGS_REF,
    INPUT_STATE_SNAPSHOT_REF,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.protocol import (
    NodeError,
    NodeEvent,
    NodeOutcome,
    NodeSpec,
)
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.state_branching import branch_state

_DISTRIBUTIONAL_VALIDATION_ERRORS = (TypeError, ValueError, ValidationError)
_DISTRIBUTIONAL_LOAD_ERRORS = (OSError, RuntimeError, TypeError, ValueError, ValidationError)
_DISTRIBUTIONAL_EXECUTION_ERRORS = (RuntimeError, TypeError, ValueError, ValidationError)

_METADATA = ComponentMetadata(
    component_id=ComponentId.parse("scientist.node_run_distributional_analysis@1.0.0"),
    kind=ComponentKind.SCIENTIST_NODE,
    abi_targets={"world_abi": "1.x"},
    display_name="Run Distributional Analysis",
    description="Build DistributionalReport and DistributionalEffectBundle from simulation state snapshots.",
    tags=["builtin", "simulate", "distributional"],
    capabilities=Capability.SCIENTIST_NODE,
)

_SPEC = NodeSpec(
    metadata=_METADATA,
    state_reads=[
        "run_id",
        f"artifacts_index.{ARTIFACT_SIMULATION_RESULT_REF}",
        f"artifacts_index.{ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF}",
        f"inputs.{INPUT_STATE_SNAPSHOT_REF}",
        f"inputs.{INPUT_INPUT_BINDINGS_REF}",
        f"inputs.{INPUT_DATA_SNAPSHOT_REF}",
        "params.distributional_treatment_variable",
        "params.query_treatment",
        "params.treatment_variable",
    ],
    state_writes=[
        f"artifacts_index.{ARTIFACT_DISTRIBUTIONAL_REPORT_REF}",
        f"artifacts_index.{ARTIFACT_DISTRIBUTIONAL_EFFECT_BUNDLE_REF}",
    ],
    produces=[
        ARTIFACT_DISTRIBUTIONAL_REPORT_REF,
        ARTIFACT_DISTRIBUTIONAL_EFFECT_BUNDLE_REF,
    ],
)


@dataclass(frozen=True)
class RunDistributionalAnalysisNode:
    """Run distributional analysis node implementation."""

    @property
    def spec(self) -> NodeSpec:
        return _SPEC

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        sim_result_ref = state.artifacts_index.get(ARTIFACT_SIMULATION_RESULT_REF)
        if sim_result_ref is None:
            return NodeOutcome(
                status="skip",
                state=state,
                events=[
                    NodeEvent(
                        level="info",
                        message="No simulation_result_ref; skip distributional analysis",
                    )
                ],
            )

        try:
            sim_payload = from_canonical_bytes(ctx.store.get_bytes(sim_result_ref))
            sim_result = SimulationResult.model_validate(sim_payload)
        except _DISTRIBUTIONAL_LOAD_ERRORS as exc:
            return NodeOutcome(
                status="skip",
                state=state,
                events=[NodeEvent(level="warn", message=f"Unable to load SimulationResult: {exc}")],
            )

        if sim_result.state_snapshot_ref is None:
            return NodeOutcome(
                status="skip",
                state=state,
                events=[
                    NodeEvent(
                        level="info",
                        message="SimulationResult has no state_snapshot_ref; skip distributional analysis",
                    )
                ],
            )

        baseline_ref = _resolve_baseline_snapshot_ref(ctx, state)
        if baseline_ref is None:
            return NodeOutcome(
                status="skip",
                state=state,
                events=[
                    NodeEvent(
                        level="info",
                        message="No baseline snapshot available; skip distributional analysis",
                    )
                ],
            )

        try:
            baseline_state = load_state_snapshot(ctx.store, snapshot_ref=baseline_ref)
            simulated_state = load_state_snapshot(
                ctx.store, snapshot_ref=sim_result.state_snapshot_ref
            )
        except _DISTRIBUTIONAL_LOAD_ERRORS as exc:
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
                events=[
                    NodeEvent(
                        level="info", message="Insufficient agents for distributional analysis"
                    )
                ],
            )

        geography_groups, geography_skipped_reasons = _aligned_geography_subgroups(
            baseline_state=baseline_state,
            simulated_state=simulated_state,
        )
        breakdowns = [build_income_quintile_breakdown(incomes_before, incomes_after)]

        geography_breakdown = _build_aligned_geography_breakdown(
            baseline_state=baseline_state,
            incomes_before=incomes_before,
            incomes_after=incomes_after,
            geography_groups=geography_groups,
        )
        if geography_breakdown is not None:
            breakdowns.append(geography_breakdown)

        artifact_inputs = _distributional_inputs(
            sim_result_ref=sim_result_ref,
            simulated_snapshot_ref=sim_result.state_snapshot_ref,
            baseline_snapshot_ref=baseline_ref,
        )
        ordinal_poverty = _maybe_build_ordinal_poverty_report(
            ctx,
            state,
            artifact_inputs=artifact_inputs,
            sim_result_ref=sim_result_ref,
            baseline_agent_count=int(incomes_before.size),
            counterfactual_agent_count=int(incomes_after.size),
        )
        report = build_distributional_report(
            breakdowns,
            incomes_before=incomes_before,
            incomes_after=incomes_after,
            ordinal_poverty_summary=ordinal_poverty.summary,
            source_simulation_ref=str(sim_result_ref.artifact_id),
            metadata={
                "run_id": state.run_id,
                "geography_breakdown_status": "included"
                if geography_breakdown is not None
                else "skipped",
                "geography_breakdown_skipped_reasons": list(geography_skipped_reasons),
                "geography_group_ids": [group.subgroup_id for group in geography_groups],
                **ordinal_poverty.metadata,
            },
        )

        try:
            overall_result = compute_scalar_distributional_effect(
                incomes_before,
                incomes_after,
                n_bins=_recommended_n_bins(min(incomes_before.size, incomes_after.size)),
            )
            justification_resolution = _resolve_distributional_justification(
                ctx,
                state,
                outcome_name="income",
                weighting_mode=overall_result.weighting_mode,
            )
            bounds_resolution = _resolve_distributional_bounds(
                ctx,
                state,
                baseline_values=incomes_before,
                counterfactual_values=incomes_after,
                inputs=artifact_inputs,
            )
            if (
                bounds_resolution.refs
                and justification_resolution.marginal_justification
                is not DistributionalJustification.IDENTIFIED
            ):
                bounded_assumptions = [
                    assumption
                    for assumption in justification_resolution.causal_assumptions
                    if assumption != "distributional_estimand_not_proof_kernel_identified"
                ]
                justification_resolution = _DistributionalJustificationResolution(
                    marginal_justification=DistributionalJustification.BOUNDED,
                    coupling_justification=justification_resolution.coupling_justification,
                    causal_assumptions=_merge_assumptions(
                        bounded_assumptions,
                        bounds_resolution.assumptions,
                    ),
                    coupling_assumptions=justification_resolution.coupling_assumptions,
                    metadata={
                        **justification_resolution.metadata,
                        "marginal_law_justification": DistributionalJustification.BOUNDED.value,
                        "distributional_bounds": bounds_resolution.metadata,
                        "bounded_functionals": bounds_resolution.functionals,
                        "bounds_theorem_families": bounds_resolution.theorem_families,
                        "bound_uniformity": bounds_resolution.bound_uniformity.value,
                    },
                    proof_bundle=justification_resolution.proof_bundle,
                    coupling_negative_certificate=justification_resolution.coupling_negative_certificate,
                )
            marginal_assumptions = list(justification_resolution.causal_assumptions)
            causal_assumptions = _merge_assumptions(
                marginal_assumptions,
                justification_resolution.coupling_assumptions,
            )
            overall_refs = _persist_scalar_artifacts(
                ctx,
                outcome_name="income",
                baseline_values=incomes_before,
                counterfactual_values=incomes_after,
                result=overall_result,
                inputs=artifact_inputs,
                coupling_assumptions=justification_resolution.coupling_assumptions,
                metadata={"scope": "overall", "run_id": state.run_id},
            )
            subgroup_refs, subgroup_events = _persist_subgroup_artifacts(
                ctx,
                incomes_before=incomes_before,
                incomes_after=incomes_after,
                inputs=artifact_inputs,
                base_assumptions=marginal_assumptions,
                coupling_assumptions=justification_resolution.coupling_assumptions,
                geography_groups=geography_groups,
                geography_skip_reasons=geography_skipped_reasons,
            )
            assumption_cards = _persist_distributional_assumption_cards(
                ctx,
                inputs=artifact_inputs,
                marginal_assumptions=justification_resolution.causal_assumptions,
                coupling_assumptions=justification_resolution.coupling_assumptions,
                marginal_justification=justification_resolution.marginal_justification,
                default_theorem_family=_distributional_theorem_family(
                    proof_bundle=justification_resolution.proof_bundle,
                    metadata=justification_resolution.metadata,
                ),
            )
            distributional_proof_ref, coupling_proof_ref = _persist_distributional_proof_artifacts(
                ctx,
                inputs=artifact_inputs,
                proof_bundle=justification_resolution.proof_bundle,
                metadata=justification_resolution.metadata,
                marginal_justification=justification_resolution.marginal_justification,
                coupling_justification=justification_resolution.coupling_justification,
                marginal_assumption_refs=assumption_cards.marginal_refs,
                coupling_assumption_refs=assumption_cards.coupling_refs,
                coupling_negative_certificate=justification_resolution.coupling_negative_certificate,
                distributional_bounds_refs=bounds_resolution.refs,
                distributional_bounds_metadata=bounds_resolution.metadata,
                distributional_bounds_uniformity=bounds_resolution.bound_uniformity,
                distributional_bounds_target=bounds_resolution.proof_target,
            )
            bundle = DistributionalEffectBundle(
                outcome_name="income",
                distributional_query_kind="interventional_law",
                justification=justification_resolution.marginal_justification,
                marginal_justification=justification_resolution.marginal_justification,
                marginal_law_justification=justification_resolution.marginal_justification,
                coupling_justification=justification_resolution.coupling_justification,
                baseline_distribution_ref=overall_refs.baseline_distribution_ref,
                counterfactual_distribution_ref=overall_refs.counterfactual_distribution_ref,
                coupling_ref=overall_refs.coupling_ref,
                coupling_diagnostics=overall_refs.coupling_diagnostics,
                wasserstein_distance=float(overall_result.wasserstein_distance),
                quantile_shift_ref=overall_refs.quantile_shift_ref,
                tail_risk_delta_ref=overall_refs.tail_risk_delta_ref,
                ordinal_poverty_ref=ordinal_poverty.ref,
                subgroup_distribution_refs=subgroup_refs,
                marginal_law_proof_ref=distributional_proof_ref,
                distributional_proof_ref=distributional_proof_ref,
                coupling_proof_ref=coupling_proof_ref,
                distributional_bounds_refs=bounds_resolution.refs,
                causal_assumption_refs=assumption_cards.all_refs,
                causal_assumptions=causal_assumptions,
                readiness_cap="simulation_ready",
                metadata={
                    "run_id": state.run_id,
                    "source_simulation_ref": str(sim_result_ref.artifact_id),
                    "weighting_mode": overall_result.weighting_mode,
                    "distributional_query_kind": "interventional_law",
                    **ordinal_poverty.metadata,
                    **justification_resolution.metadata,
                },
            )
            bundle_ref = persist_distributional_effect_bundle(
                _ensure_ir_artifact_store(ctx.store), bundle, inputs=artifact_inputs
            )
            report_ref = persist_distributional_report(
                _ensure_ir_artifact_store(ctx.store), report, inputs=artifact_inputs
            )
        except _DISTRIBUTIONAL_EXECUTION_ERRORS as exc:
            return NodeOutcome(
                status="fail",
                state=state,
                events=[
                    NodeEvent(level="error", message=f"Distributional D.1 build failed: {exc}")
                ],
                error=NodeError(
                    code="distributional_analysis_failed",
                    message="Failed to build OT distributional artifacts",
                    details={"reason": str(exc)},
                ),
            )

        new_state = branch_state(state, write_paths=("artifacts_index",)).state
        new_state.artifacts_index[ARTIFACT_DISTRIBUTIONAL_REPORT_REF] = report_ref
        new_state.artifacts_index[ARTIFACT_DISTRIBUTIONAL_EFFECT_BUNDLE_REF] = bundle_ref
        return NodeOutcome(
            status="ok",
            state=new_state,
            artifacts=[
                report_ref,
                bundle_ref,
                *([ordinal_poverty.ref] if ordinal_poverty.ref is not None else []),
            ],
            events=[
                NodeEvent(
                    level="info",
                    message=(
                        f"Distributional report generated with {len(report.breakdowns)} breakdown(s) "
                        f"and OT bundle with {len(subgroup_refs)} subgroup comparison(s)"
                    ),
                ),
                *ordinal_poverty.events,
                *subgroup_events,
            ],
        )


def _distributional_inputs(
    *,
    sim_result_ref: Any,
    simulated_snapshot_ref: StateSnapshotRef,
    baseline_snapshot_ref: StateSnapshotRef,
) -> list[InputRef]:
    return [
        InputRef(artifact_id=sim_result_ref.artifact_id, role="simulation_result"),
        InputRef(artifact_id=simulated_snapshot_ref.artifact_id, role="simulated_state_snapshot"),
        InputRef(artifact_id=baseline_snapshot_ref.artifact_id, role="baseline_state_snapshot"),
    ]


def _resolve_baseline_snapshot_ref(
    ctx: ExecutionContext,
    state: ExperimentState,
) -> StateSnapshotRef | None:
    explicit = state.inputs.get(INPUT_STATE_SNAPSHOT_REF)
    if explicit is not None:
        try:
            return StateSnapshotRef.model_validate(explicit.model_dump())
        except _DISTRIBUTIONAL_VALIDATION_ERRORS:
            return None

    input_bindings_ref = state.inputs.get(INPUT_INPUT_BINDINGS_REF)
    if input_bindings_ref is not None:
        try:
            payload = from_canonical_bytes(ctx.store.get_bytes(input_bindings_ref))
            bindings = FoundryInputBindings.model_validate(payload)
            return bindings.bound_state_snapshot_ref
        except _DISTRIBUTIONAL_LOAD_ERRORS:
            return None

    data_snapshot_ref = state.inputs.get(INPUT_DATA_SNAPSHOT_REF)
    if data_snapshot_ref is None:
        return None
    try:
        payload = from_canonical_bytes(ctx.store.get_bytes(data_snapshot_ref))
        snapshot = DataSnapshot.model_validate(payload)
    except _DISTRIBUTIONAL_LOAD_ERRORS:
        return None
    if snapshot.data_ref.kind != "foundry.state_snapshot":
        return None
    return StateSnapshotRef(artifact_id=snapshot.data_ref.artifact_id)


__all__ = ["RunDistributionalAnalysisNode"]
