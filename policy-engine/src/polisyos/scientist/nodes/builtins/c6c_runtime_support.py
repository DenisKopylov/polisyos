"""Public builtins c 6 c runtime support module API."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Mapping

from pydantic import ValidationError

from polisyos.common.logger import get_logger
from polisyos.core.artifacts.manifest import ArtifactRef, InputRef, SchemaInfo
from polisyos.core.artifacts.store import PutOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.core.contracts.foundry import (
    LoweredIR,
    LoweredIRRef,
    ParameterOverrideBundle,
    ProgramGraph,
    ProgramGraphRef,
)
from polisyos.foundry.methods.catalog.causal.strategic import (
    solve_strategic_response,
    strategic_result_summary,
)
from polisyos.ir.analytics.abstraction import (
    AbstractionCertificate,
    abstraction_allowed_intervention_family,
    abstraction_error_bound_spec,
    abstraction_estimand_error_bounds,
    abstraction_recommendation_margin_required,
    load_abstraction_certificate,
)
from polisyos.ir.analytics.strategic import (
    FiniteStrategicPayoffTable,
    StrategicSCM,
    load_strategic_payoff_table,
    persist_strategic_payoff_table,
    persist_strategic_solve_artifacts,
    persist_strategic_scm,
)
from polisyos.ir.artifacts import InputRef as IRInputRef
from polisyos.ir.refs import ArtifactRefModel
from polisyos.lex.intervention_artifacts import LexPolicyBundleInput
from polisyos.lex.interventions import CompiledLexIntervention
from polisyos.scientist.engine.context import ExecutionContext
from polisyos.scientist.engine.state import ExperimentState
from polisyos.scientist.error_semantics import emit_degraded_path
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_ABSTRACTION_CERTIFICATE_REF,
    ARTIFACT_CAUSAL_REPORT_REF,
    ARTIFACT_LOWERED_IR_REF,
    ARTIFACT_PROGRAM_GRAPH_REF,
    ARTIFACT_STRATEGIC_RESPONSE_BUNDLE_REF,
    ARTIFACT_STRATEGIC_SCM_REF,
    INPUT_PARAMETER_OVERRIDE_BUNDLE_REF,
    INPUT_TRINITY_BUNDLE_REF,
)
from polisyos.scientist.policy_design.schema import PolicyCandidateSchema

_module_logger = get_logger(__name__)
_RUNTIME_SUPPORT_VALIDATION_ERRORS = (TypeError, ValidationError, ValueError)
_RUNTIME_SUPPORT_LOAD_ERRORS = (
    AttributeError,
    OSError,
    RuntimeError,
    TypeError,
    ValidationError,
    ValueError,
)


@dataclass(frozen=True)
class StrategicRuntimeOutput:
    """Persisted strategic-runtime artifacts produced during C6c execution."""

    strategic_scm_ref: ArtifactRef | None = None
    strategic_response_bundle_ref: ArtifactRef | None = None
    strategic_response_summary: dict[str, Any] | None = None
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class ParameterOverrideMaterialization:
    """Result of materializing a Foundry parameter-override bundle."""

    bundle_ref: ArtifactRef | None = None
    bundle: ParameterOverrideBundle | None = None
    warnings: tuple[str, ...] = ()


def _runtime_support_degraded(
    *,
    operation: str,
    reason: str,
    exc: BaseException,
    details: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return emit_degraded_path(
        component="scientist.decision_runtime",
        operation=operation,
        reason=reason,
        exc=exc,
        details=details,
        log=_module_logger,
    )


def _context_run_id(ctx: ExecutionContext) -> str | None:
    return getattr(ctx.run, "run_id", None)


def _blocked_strategic_runtime_output(
    *,
    blocked_reason: str,
    warning_prefix: str,
    exc: BaseException,
    details: Mapping[str, Any] | None = None,
) -> StrategicRuntimeOutput:
    envelope = _runtime_support_degraded(
        operation="persist_runtime_strategic_artifacts",
        reason=blocked_reason,
        exc=exc,
        details=details,
    )
    summary = build_blocked_strategic_summary(blocked_reason=blocked_reason)
    summary["degraded_path"] = envelope
    return StrategicRuntimeOutput(
        strategic_response_summary=summary,
        warnings=(f"{warning_prefix}:{exc}",),
    )


def maybe_materialize_policy_override_bundle(
    ctx: ExecutionContext,
    state: ExperimentState,
) -> ParameterOverrideMaterialization:
    """Build and persist parameter overrides when a policy candidate is present.

    The helper inspects the candidate policy, optional Lex intervention bundle,
    lowered IR, and program graph to translate policy-parameter choices into
    node-level Foundry override payloads.
    """

    existing = state.inputs.get(INPUT_PARAMETER_OVERRIDE_BUNDLE_REF)
    if existing is not None:
        return ParameterOverrideMaterialization(bundle_ref=existing)

    candidate = _coerce_candidate(state.params.get("policy_candidate_schema"))
    lex_bundle = _coerce_lex_bundle(state.params.get("lex_policy_bundle_input"))
    if candidate is None and lex_bundle is None:
        return ParameterOverrideMaterialization()

    lowered_ir = _load_lowered_ir(ctx, state)
    program_graph = _load_program_graph(ctx, state)
    if lowered_ir is None or program_graph is None:
        return ParameterOverrideMaterialization()

    resolved_candidate = candidate
    if resolved_candidate is None and lex_bundle is not None:
        from polisyos.lex.interventions import HierarchicalPolicySearchAdapter

        resolved_candidate = HierarchicalPolicySearchAdapter().build_candidate(lex_bundle)
    if resolved_candidate is None:
        return ParameterOverrideMaterialization()

    bundle = build_policy_parameter_override_bundle(
        candidate=resolved_candidate,
        lowered_ir=lowered_ir,
        program_graph=program_graph,
        compiled_interventions=(
            tuple(lex_bundle.compiled_interventions)
            if lex_bundle is not None
            else ()
        ),
    )
    if bundle is None:
        return ParameterOverrideMaterialization()

    input_refs = []
    lowered_ref = state.artifacts_index.get(ARTIFACT_LOWERED_IR_REF)
    if lowered_ref is not None:
        input_refs.append(
            InputRef(artifact_id=str(lowered_ref.artifact_id), role="lowered_ir")
        )
    program_ref = state.artifacts_index.get(ARTIFACT_PROGRAM_GRAPH_REF)
    if program_ref is not None:
        input_refs.append(
            InputRef(artifact_id=str(program_ref.artifact_id), role="program_graph")
        )
    trinity_ref = state.inputs.get(INPUT_TRINITY_BUNDLE_REF)
    if trinity_ref is not None:
        input_refs.append(
            InputRef(artifact_id=str(trinity_ref.artifact_id), role="trinity_bundle")
        )
    bundle_ref = ctx.store.put_json(
        bundle,
        PutOptions(
            kind="foundry.parameter_override_bundle",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.foundry.ParameterOverrideBundle",
                version=bundle.schema_version,
            ),
            inputs=input_refs,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return ParameterOverrideMaterialization(bundle_ref=bundle_ref, bundle=bundle)


def build_policy_parameter_override_bundle(
    *,
    candidate: PolicyCandidateSchema,
    lowered_ir: LoweredIR,
    program_graph: ProgramGraph,
    compiled_interventions: tuple[CompiledLexIntervention, ...] = (),
) -> ParameterOverrideBundle | None:
    """Translate a policy candidate into a Foundry `ParameterOverrideBundle`."""

    node_ids_by_binding = _program_node_ids_by_binding(program_graph)
    intervention_bindings: dict[str, list[str]] = {}
    for mechanism in lowered_ir.mechanisms:
        resolved_node_ids = node_ids_by_binding.get(mechanism.binding_id)
        if not resolved_node_ids:
            continue
        for intervention_id in mechanism.intervention_ids:
            intervention_bindings.setdefault(intervention_id, []).extend(resolved_node_ids)

    overrides: dict[str, dict[str, Any]] = {}
    sources: dict[str, list[str]] = {}

    interventions_by_id = {
        intervention.intervention_id: intervention
        for intervention in candidate.trinity_bundle.policy_spec.interventions
    }
    schedule_by_param_id: dict[str, tuple[Any, str]] = {}
    for entry in candidate.parameter_schedule:
        existing = schedule_by_param_id.get(entry.param_id)
        if existing is not None and _normalize_for_compare(existing[0]) != _normalize_for_compare(
            entry.scheduled_value
        ):
            raise ValueError(
                f"ambiguous scheduled override for param_id '{entry.param_id}'"
            )
        schedule_by_param_id[entry.param_id] = (entry.scheduled_value, entry.entry_id)

    for parameter in candidate.trinity_bundle.policy_spec.parameters:
        intervention = interventions_by_id.get(parameter.intervention_id)
        if intervention is None:
            raise ValueError(
                f"parameter '{parameter.param_id}' references unknown intervention "
                f"'{parameter.intervention_id}'"
            )
        current_value, ok = _resolve_mapping_path(intervention.params, parameter.param_path)
        if not ok:
            raise ValueError(
                f"parameter '{parameter.param_id}' references unknown param_path "
                f"'{parameter.param_path}'"
            )
        schedule_entry = schedule_by_param_id.get(parameter.param_id)
        if schedule_entry is not None and _normalize_for_compare(schedule_entry[0]) != _normalize_for_compare(
            current_value
        ):
            current_value = schedule_entry[0]
            source_tag = f"parameter_schedule:{schedule_entry[1]}"
        else:
            source_tag = f"policy_parameter:{parameter.param_id}"
        _apply_policy_override(
            overrides=overrides,
            sources=sources,
            intervention_bindings=intervention_bindings,
            intervention_id=parameter.intervention_id,
            param_path=parameter.param_path,
            value=current_value,
            source_tag=source_tag,
        )

    for compiled in compiled_interventions:
        for parameter in compiled.parameters:
            current_value, ok = _resolve_mapping_path(
                compiled.intervention.params,
                parameter.param_path,
            )
            if not ok:
                raise ValueError(
                    f"compiled intervention '{compiled.intervention.intervention_id}' "
                    f"references unknown param_path '{parameter.param_path}'"
                )
            _apply_policy_override(
                overrides=overrides,
                sources=sources,
                intervention_bindings=intervention_bindings,
                intervention_id=compiled.intervention.intervention_id,
                param_path=parameter.param_path,
                value=current_value,
                source_tag=(
                    "compiled_intervention:"
                    f"{compiled.intervention.intervention_id}:{parameter.param_id}"
                ),
            )

    if not overrides:
        return None
    return ParameterOverrideBundle(
        overrides=overrides,
        sources=sources,
        notes=["materialized_from_c6c_policy_candidate"],
    )


def persist_runtime_strategic_artifacts(
    ctx: ExecutionContext,
    state: ExperimentState,
    *,
    artifacts_index: Mapping[str, ArtifactRef],
    candidate_ref: ArtifactRef | None = None,
    evidence_ref: ArtifactRef | None = None,
    evidence_role: str = "policy_evaluation",
    baseline_payload: Any = None,
) -> StrategicRuntimeOutput:
    """Persist strategic-runtime artifacts for the current policy evaluation.

    This helper validates strategic inputs, persists payoff tables and the
    normalized `StrategicSCM`, executes the strategic-response solve path, and
    returns refs plus a summary suitable for state insertion.
    """

    strategic_payload = state.params.get("strategic_scm")
    if strategic_payload is None:
        return StrategicRuntimeOutput()

    fallback_candidate_ref = candidate_ref
    if fallback_candidate_ref is None:
        fallback_candidate_ref = state.inputs.get(INPUT_TRINITY_BUNDLE_REF)
    inputs = _runtime_strategic_inputs(
        candidate_ref=fallback_candidate_ref,
        evidence_ref=evidence_ref,
        evidence_role=evidence_role,
        abstraction_certificate_ref=artifacts_index.get(ARTIFACT_ABSTRACTION_CERTIFICATE_REF),
    )
    try:
        contract = (
            strategic_payload
            if isinstance(strategic_payload, StrategicSCM)
            else StrategicSCM.model_validate(strategic_payload)
        )
        payoff_tables = _coerce_runtime_payoff_tables(state.params.get("strategic_payoff_tables"))
        macro_payload = state.params.get("macro_strategic_payoff_tables")
        macro_payoff_tables = (
            None if macro_payload is None else _coerce_runtime_payoff_tables(macro_payload)
        )
    except _RUNTIME_SUPPORT_VALIDATION_ERRORS as exc:
        return _blocked_strategic_runtime_output(
            blocked_reason="strategic_runtime_invalid_input",
            warning_prefix="strategic_runtime_invalid_input",
            exc=exc,
            details={"run_id": state.run_id},
        )

    try:
        utility_ref_status = _compare_existing_payoff_refs(
            ctx,
            refs=contract.utility_refs,
            raw_tables=payoff_tables,
        )
        macro_ref_status = None
        if macro_payoff_tables is not None and contract.macro_utility_refs is not None:
            macro_ref_status = _compare_existing_payoff_refs(
                ctx,
                refs=contract.macro_utility_refs,
                raw_tables=macro_payoff_tables,
            )
        blocked_reason = _strategic_payoff_ref_block_reason(
            utility_ref_status=utility_ref_status,
            macro_ref_status=macro_ref_status,
        )
        if blocked_reason is not None:
            strategic_scm_ref = ArtifactRef.model_validate(
                persist_strategic_scm(ctx.store, contract, inputs=inputs).model_dump(mode="json")
            )
            return StrategicRuntimeOutput(
                strategic_scm_ref=strategic_scm_ref,
                strategic_response_summary=build_blocked_strategic_summary(
                    blocked_reason=blocked_reason,
                    strategic_scm_ref=strategic_scm_ref,
                ),
                warnings=(f"strategic_runtime_blocked:{blocked_reason}",),
            )

        causal_report_ref = artifacts_index.get(ARTIFACT_CAUSAL_REPORT_REF)
        if causal_report_ref is None:
            blocked_reason = "missing_causal_report_for_strategic_decomposition"
            strategic_scm_ref = ArtifactRef.model_validate(
                persist_strategic_scm(ctx.store, contract, inputs=inputs).model_dump(mode="json")
            )
            return StrategicRuntimeOutput(
                strategic_scm_ref=strategic_scm_ref,
                strategic_response_summary=build_blocked_strategic_summary(
                    blocked_reason=blocked_reason,
                    strategic_scm_ref=strategic_scm_ref,
                ),
                warnings=(f"strategic_runtime_blocked:{blocked_reason}",),
            )

        persisted_utility_refs = _persist_runtime_payoff_tables(
            ctx,
            tables=payoff_tables,
            inputs=inputs,
        )
        persisted_macro_refs = (
            None
            if macro_payoff_tables is None
            else _persist_runtime_payoff_tables(
                ctx,
                tables=macro_payoff_tables,
                inputs=inputs,
            )
        )
        normalized_contract = contract.model_copy(
            update={
                "utility_refs": persisted_utility_refs,
                "macro_utility_refs": persisted_macro_refs,
            }
        )
        strategic_scm_ref = ArtifactRef.model_validate(
            persist_strategic_scm(ctx.store, normalized_contract, inputs=inputs).model_dump(mode="json")
        )
        abstraction_certificate = load_runtime_abstraction_certificate(
            ctx,
            dict(artifacts_index),
        )
        baseline_policy_value = resolve_baseline_policy_value(baseline_payload)
        result = solve_strategic_response(
            normalized_contract,
            payoff_tables,
            baseline_policy_value=baseline_policy_value,
            abstraction_certificate=abstraction_certificate,
            macro_payoff_tables=macro_payoff_tables,
            performative_loop_spec=state.params.get("performative_loop_spec"),
            mean_field_inputs=state.params.get("mean_field_game"),
        )
        causal_component_ref = ArtifactRefModel.model_validate(causal_report_ref.model_dump(mode="json"))
        bundle, bundle_ref = persist_strategic_solve_artifacts(
            ctx.store,
            causal_component_ref=causal_component_ref,
            result=result,
            equilibrium_concept=normalized_contract.equilibrium_concept,
            equilibrium_descriptor=normalized_contract.equilibrium_descriptor,
            baseline_policy_value=baseline_policy_value,
            inputs=inputs,
            metadata={
                "run_id": state.run_id,
                "strategic_scm_ref": strategic_scm_ref.model_dump(mode="json"),
            },
            mfg_equilibrium_certificate=result.mfg_equilibrium_certificate,
            mfg_macro_simulation_config=result.mfg_macro_simulation_config,
            mfg_solver_residual_report=result.mfg_solver_residual_report,
            mfg_mass_conservation_report=result.mfg_mass_conservation_report,
        )
        strategic_response_bundle_ref = ArtifactRef.model_validate(bundle_ref.model_dump(mode="json"))
        summary = strategic_result_summary(result)
        summary.update(
            {
                "strategic_scm_ref": strategic_scm_ref.model_dump(mode="json"),
                "strategic_response_bundle_ref": strategic_response_bundle_ref.model_dump(
                    mode="json"
                ),
                "causal_component_ref": bundle.causal_component_ref.model_dump(mode="json"),
                "strategic_closure_ref": bundle.strategic_closure_ref.model_dump(mode="json"),
                "equilibrium_set_ref": bundle.equilibrium_set_ref.model_dump(mode="json"),
                "post_adaptation_policy_value_ref": bundle.post_adaptation_policy_value_ref.model_dump(
                    mode="json"
                ),
                "selected_equilibrium_ref": (
                    None
                    if bundle.selected_equilibrium_ref is None
                    else bundle.selected_equilibrium_ref.model_dump(mode="json")
                ),
                "mfg_equilibrium_ref": (
                    None
                    if bundle.mfg_equilibrium_ref is None
                    else bundle.mfg_equilibrium_ref.model_dump(mode="json")
                ),
                "performative_shift_ref": (
                    None
                    if bundle.performative_shift_ref is None
                    else bundle.performative_shift_ref.model_dump(mode="json")
                ),
                "decomposition_status": bundle.decomposition_status.value,
                "decomposition_semantics": bundle.decomposition_semantics.value,
                "decomposition_certificate_ref": (
                    None
                    if bundle.decomposition_certificate_ref is None
                    else bundle.decomposition_certificate_ref.model_dump(mode="json")
                ),
                "decomposition_failure_card_ref": (
                    None
                    if bundle.decomposition_failure_card_ref is None
                    else bundle.decomposition_failure_card_ref.model_dump(mode="json")
                ),
                "anchor_equilibrium_ref": (
                    None
                    if bundle.anchor_equilibrium_ref is None
                    else bundle.anchor_equilibrium_ref.model_dump(mode="json")
                ),
            }
        )
        return StrategicRuntimeOutput(
            strategic_scm_ref=strategic_scm_ref,
            strategic_response_bundle_ref=strategic_response_bundle_ref,
            strategic_response_summary=summary,
            warnings=tuple(str(item) for item in result.warnings),
        )
    except _RUNTIME_SUPPORT_LOAD_ERRORS as exc:
        return _blocked_strategic_runtime_output(
            blocked_reason="strategic_runtime_persistence_failed",
            warning_prefix="strategic_runtime_persistence_failed",
            exc=exc,
            details={"run_id": state.run_id},
        )


def resolve_existing_strategic_output(
    state: ExperimentState,
) -> StrategicRuntimeOutput | None:
    """Reuse strategic-runtime artifacts already attached to workflow state."""

    raw_summary = state.params.get("strategic_response")
    summary = dict(raw_summary) if isinstance(raw_summary, Mapping) else None
    strategic_scm_ref = state.artifacts_index.get(ARTIFACT_STRATEGIC_SCM_REF)
    strategic_response_bundle_ref = state.artifacts_index.get(ARTIFACT_STRATEGIC_RESPONSE_BUNDLE_REF)
    source = str(state.params.get("strategic_response_source") or "").strip().lower()
    if summary is None and source not in {"run_simulation", "policy_runtime"}:
        return None
    if summary is None and strategic_scm_ref is None and strategic_response_bundle_ref is None:
        return None
    warnings: tuple[str, ...] = ()
    if summary is not None:
        raw_warnings = summary.get("warnings")
        if isinstance(raw_warnings, list):
            warnings = tuple(str(item) for item in raw_warnings)
    return StrategicRuntimeOutput(
        strategic_scm_ref=strategic_scm_ref,
        strategic_response_bundle_ref=strategic_response_bundle_ref,
        strategic_response_summary=summary,
        warnings=warnings,
    )


def build_blocked_strategic_summary(
    *,
    blocked_reason: str,
    strategic_scm_ref: ArtifactRef | None = None,
) -> dict[str, Any]:
    """Build a normalized blocked strategic-response summary payload."""

    summary: dict[str, Any] = {
        "fallback_mode": "blocked",
        "equilibrium_selection_dependence": "runtime_precondition_blocked",
        "multiplicity_note": None,
        "blocked_reason": str(blocked_reason),
        "decomposition_status": "blocked",
        "decomposition_semantics": "frozen_baseline_strategy",
        "decomposition_failure_code": "decomposition_no_equilibrium",
        "decomposition_message": (
            "Strategic runtime did not produce a decomposition certificate that would "
            "license separate causal and strategic components."
        ),
        "closure_summary": {
            "mode": "blocked",
            "blocked_reason": str(blocked_reason),
        },
        "warnings": [],
    }
    if strategic_scm_ref is not None:
        summary["strategic_scm_ref"] = strategic_scm_ref.model_dump(mode="json")
    return summary


def resolve_baseline_policy_value(payload: Any) -> float | None:
    """Extract a scalar baseline welfare metric from simulation-like payloads."""

    if payload is None:
        return None
    metric_map: Mapping[str, Any] | None = None
    if isinstance(payload, Mapping):
        metric_map = payload
    else:
        simulation_results = getattr(payload, "simulation_results", None)
        if isinstance(simulation_results, Mapping):
            metric_map = simulation_results
    if metric_map is None:
        return None
    for key in ("net_social_welfare", "welfare", "policy_value", "gdp_change"):
        raw = metric_map.get(key)
        if raw is None:
            continue
        try:
            return float(raw)
        except (TypeError, ValueError):
            continue
    return None


def load_runtime_abstraction_certificate(
    ctx: ExecutionContext,
    artifacts_index: Mapping[str, ArtifactRef],
) -> AbstractionCertificate | None:
    """Load the runtime abstraction certificate when the workflow persisted one."""

    ref = artifacts_index.get(ARTIFACT_ABSTRACTION_CERTIFICATE_REF)
    if ref is None:
        return None
    try:
        return load_abstraction_certificate(ctx.store, ref)
    except _RUNTIME_SUPPORT_LOAD_ERRORS as exc:
        _runtime_support_degraded(
            operation="load_runtime_abstraction_certificate",
            reason="abstraction_certificate_unreadable",
            exc=exc,
            details={
                "artifact_id": str(ref.artifact_id),
                "run_id": _context_run_id(ctx),
            },
        )
        return None


def build_runtime_abstraction_metadata(
    ctx: ExecutionContext,
    *,
    artifacts_index: Mapping[str, ArtifactRef],
) -> dict[str, Any]:
    """Build small metadata payloads describing runtime abstraction evidence."""

    metadata: dict[str, Any] = {}
    certificate_ref = artifacts_index.get(ARTIFACT_ABSTRACTION_CERTIFICATE_REF)
    if certificate_ref is not None:
        metadata["abstraction_certificate_ref"] = certificate_ref.model_dump(mode="json")
        certificate = load_runtime_abstraction_certificate(ctx, artifacts_index)
        if certificate is not None:
            metadata["abstraction_preservation_type"] = certificate.preservation_type.value
            metadata["abstraction_preserved_queries"] = list(certificate.preserved_queries)
            if certificate.error_bound is not None:
                metadata["abstraction_error_bound"] = float(certificate.error_bound)
            allowed_intervention_family = abstraction_allowed_intervention_family(certificate)
            if allowed_intervention_family is not None:
                metadata["abstraction_allowed_intervention_family"] = (
                    allowed_intervention_family
                )
            estimand_error_bounds = abstraction_estimand_error_bounds(certificate)
            if estimand_error_bounds:
                metadata["abstraction_estimand_error_bounds"] = estimand_error_bounds
            error_bound_spec = abstraction_error_bound_spec(certificate)
            if error_bound_spec:
                metadata["abstraction_error_bound_spec"] = error_bound_spec
            recommendation_margin_required = abstraction_recommendation_margin_required(
                certificate
            )
            if recommendation_margin_required is not None:
                metadata["abstraction_recommendation_margin_required"] = (
                    recommendation_margin_required
                )
    return metadata


def _runtime_strategic_inputs(
    *,
    candidate_ref: ArtifactRef | None,
    evidence_ref: ArtifactRef | None,
    evidence_role: str,
    abstraction_certificate_ref: ArtifactRef | None,
) -> list[IRInputRef]:
    inputs: list[IRInputRef] = []
    if candidate_ref is not None:
        inputs.append(IRInputRef(artifact_id=candidate_ref.artifact_id, role="candidate"))
    if evidence_ref is not None:
        inputs.append(IRInputRef(artifact_id=evidence_ref.artifact_id, role=evidence_role))
    if abstraction_certificate_ref is not None:
        inputs.append(
            IRInputRef(
                artifact_id=abstraction_certificate_ref.artifact_id,
                role="abstraction_certificate",
            )
        )
    return inputs


def _coerce_runtime_payoff_tables(payload: Any) -> dict[str, FiniteStrategicPayoffTable]:
    if not isinstance(payload, dict) or not payload:
        raise ValueError("strategic_payoff_tables must be a non-empty mapping")
    tables: dict[str, FiniteStrategicPayoffTable] = {}
    for agent, table_payload in payload.items():
        tables[str(agent)] = (
            table_payload
            if isinstance(table_payload, FiniteStrategicPayoffTable)
            else FiniteStrategicPayoffTable.model_validate(table_payload)
        )
    return tables


def _persist_runtime_payoff_tables(
    ctx: ExecutionContext,
    *,
    tables: dict[str, FiniteStrategicPayoffTable],
    inputs: list[IRInputRef],
) -> dict[str, ArtifactRefModel]:
    return {
        agent: persist_strategic_payoff_table(ctx.store, table, inputs=inputs)
        for agent, table in tables.items()
    }


def _payoff_table_signature(table: FiniteStrategicPayoffTable) -> dict[str, Any]:
    return {
        "agent": table.agent,
        "strategic_agents": tuple(table.strategic_agents),
        "action_spaces": {
            agent: tuple(actions) for agent, actions in table.action_spaces.items()
        },
        "payoffs": {key: float(value) for key, value in table.payoffs.items()},
    }


def _strategic_payoff_ref_block_reason(
    *,
    utility_ref_status: str,
    macro_ref_status: str | None,
) -> str | None:
    statuses = (utility_ref_status, macro_ref_status)
    if "unreadable_ref" in statuses:
        return "strategic_contract_payoff_ref_unreadable"
    if "mismatch" in statuses:
        return "strategic_contract_payoff_ref_mismatch"
    return None


def _compare_existing_payoff_refs(
    ctx: ExecutionContext,
    *,
    refs: dict[str, ArtifactRefModel],
    raw_tables: dict[str, FiniteStrategicPayoffTable],
) -> str:
    loaded_tables: dict[str, FiniteStrategicPayoffTable] = {}
    try:
        for agent, ref in refs.items():
            loaded_tables[agent] = load_strategic_payoff_table(ctx.store, ref)
    except _RUNTIME_SUPPORT_LOAD_ERRORS as exc:
        _runtime_support_degraded(
            operation="compare_existing_payoff_refs",
            reason="strategic_payoff_ref_unreadable",
            exc=exc,
            details={
                "agents": sorted(str(agent) for agent in refs),
                "run_id": _context_run_id(ctx),
            },
        )
        return "unreadable_ref"
    if set(loaded_tables) != set(raw_tables):
        return "mismatch"
    matches = all(
        _payoff_table_signature(loaded_tables[agent]) == _payoff_table_signature(raw_tables[agent])
        for agent in raw_tables
    )
    return "match" if matches else "mismatch"


def _load_lowered_ir(
    ctx: ExecutionContext,
    state: ExperimentState,
) -> LoweredIR | None:
    raw_ref = state.artifacts_index.get(ARTIFACT_LOWERED_IR_REF)
    if raw_ref is None:
        return None
    try:
        ref = LoweredIRRef.model_validate(raw_ref.model_dump(mode="json"))
        payload = from_canonical_bytes(ctx.store.get_bytes(ref.artifact_id))
        return LoweredIR.model_validate(payload)
    except _RUNTIME_SUPPORT_LOAD_ERRORS as exc:
        _runtime_support_degraded(
            operation="load_lowered_ir",
            reason="lowered_ir_unreadable",
            exc=exc,
            details={"run_id": state.run_id},
        )
        return None


def _load_program_graph(
    ctx: ExecutionContext,
    state: ExperimentState,
) -> ProgramGraph | None:
    raw_ref = state.artifacts_index.get(ARTIFACT_PROGRAM_GRAPH_REF)
    if raw_ref is None:
        return None
    try:
        ref = ProgramGraphRef.model_validate(raw_ref.model_dump(mode="json"))
        payload = from_canonical_bytes(ctx.store.get_bytes(ref.artifact_id))
        return ProgramGraph.model_validate(payload)
    except _RUNTIME_SUPPORT_LOAD_ERRORS as exc:
        _runtime_support_degraded(
            operation="load_program_graph",
            reason="program_graph_unreadable",
            exc=exc,
            details={"run_id": state.run_id},
        )
        return None


def _coerce_candidate(payload: Any) -> PolicyCandidateSchema | None:
    if payload is None:
        return None
    if isinstance(payload, PolicyCandidateSchema):
        return payload
    try:
        return PolicyCandidateSchema.model_validate(payload)
    except _RUNTIME_SUPPORT_VALIDATION_ERRORS:
        return None


def _coerce_lex_bundle(payload: Any) -> LexPolicyBundleInput | None:
    if payload is None:
        return None
    if isinstance(payload, LexPolicyBundleInput):
        return payload
    try:
        return LexPolicyBundleInput.model_validate(payload)
    except _RUNTIME_SUPPORT_VALIDATION_ERRORS:
        return None


def _program_node_ids_by_binding(program_graph: ProgramGraph) -> dict[str, list[str]]:
    mapping: dict[str, list[str]] = {}
    for node in program_graph.nodes:
        op = node.op
        if op is None or op.op_kind != "apply_mechanism":
            continue
        binding_id = op.params.get("binding_id")
        if not isinstance(binding_id, str) or not binding_id:
            continue
        mapping.setdefault(binding_id, []).append(str(node.node_id))
    return mapping


def _apply_policy_override(
    *,
    overrides: dict[str, dict[str, Any]],
    sources: dict[str, list[str]],
    intervention_bindings: Mapping[str, list[str]],
    intervention_id: str,
    param_path: str,
    value: Any,
    source_tag: str,
) -> None:
    node_ids = intervention_bindings.get(intervention_id)
    if not node_ids:
        raise ValueError(f"no lowered mechanism found for intervention_id '{intervention_id}'")
    param_key = _terminal_param_key(param_path)
    for node_id in sorted(set(node_ids)):
        existing_value = overrides.setdefault(node_id, {}).get(param_key)
        if existing_value is not None and _normalize_for_compare(existing_value) != _normalize_for_compare(
            value
        ):
            raise ValueError(
                f"ambiguous override for node '{node_id}' and param '{param_key}'"
            )
        overrides[node_id][param_key] = value
        sources.setdefault(node_id, []).append(source_tag)


def _resolve_mapping_path(
    params: Mapping[str, Any],
    param_path: str,
) -> tuple[Any, bool]:
    parts = [part for part in param_path.removeprefix("params.").split(".") if part]
    if not parts:
        return None, False
    current: Any = dict(params)
    for part in parts:
        if not isinstance(current, Mapping) or part not in current:
            return None, False
        current = current[part]
    return current, True


def _terminal_param_key(param_path: str) -> str:
    normalized = param_path.removeprefix("params.")
    parts = [part for part in normalized.split(".") if part]
    if not parts:
        raise ValueError(f"invalid param_path '{param_path}'")
    return parts[-1]


def _normalize_for_compare(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if hasattr(value, "model_dump"):
        try:
            return value.model_dump(mode="json")
        except (AttributeError, TypeError, ValidationError, ValueError):
            return repr(value)
    if isinstance(value, Mapping):
        return {
            str(key): _normalize_for_compare(item)
            for key, item in sorted(value.items(), key=lambda item: str(item[0]))
        }
    if isinstance(value, (list, tuple)):
        return [_normalize_for_compare(item) for item in value]
    return value


__all__ = [
    "ParameterOverrideMaterialization",
    "StrategicRuntimeOutput",
    "build_blocked_strategic_summary",
    "build_policy_parameter_override_bundle",
    "build_runtime_abstraction_metadata",
    "load_runtime_abstraction_certificate",
    "maybe_materialize_policy_override_bundle",
    "persist_runtime_strategic_artifacts",
    "resolve_baseline_policy_value",
    "resolve_existing_strategic_output",
]
