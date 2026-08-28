"""Public simulate run causal evaluation module API."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import numpy as np
from pydantic import ValidationError

from polisyos.core.artifacts.manifest import ArtifactRef, InputRef
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.core.contracts import build_skip_blocker_record
from polisyos.foundry.methods.catalog import (
    ensure_all_methods_registered as ensure_causal_methods_registered,
)
from polisyos.foundry.methods.causal import (
    GraphCausalData,
    GraphCausalDataV1,
    HTEObservationalData,
    PanelObservationalData,
    RDDObservationalData,
)
from polisyos.ir.analytics.causal import (
    CausalEffectReport,
    CausalMethod,
    EstimationStatus,
    persist_causal_effect_report,
)
from polisyos.ir.analytics.hte import (
    HTEResult,
    PolicyRecommendation,
    persist_hte_result,
    persist_policy_recommendation,
)
from polisyos.ir.analytics.sensitivity import SensitivityResult, persist_sensitivity_result
from polisyos.ir.analytics.uncertainty import UncertaintyEnvelope, persist_uncertainty_envelope
from polisyos.runtime.quality import (
    EvalSafetyAdmissionChallenge,
    evaluation_safety_consumer_admission_is_verified,
    resolve_evaluation_mode,
)
from polisyos.scientist.compute.job_spec import JobSpec
from polisyos.scientist.compute.runner import run_job
from polisyos.scientist.evidence.claims.projections import project_causal_effect_claims
from polisyos.scientist.evidence.claims.validators import is_claim_spine_enabled
from polisyos.scientist.methods.causal.validity import persist_causal_validity_bundle
from polisyos.scientist.nodes.builtins import errors as node_errors
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_CAUSAL_ENVELOPE_REF,
    ARTIFACT_CAUSAL_METHOD_EVIDENCE_REF,
    ARTIFACT_CAUSAL_METHOD_RESULT_REF,
    ARTIFACT_CAUSAL_REPORT_REF,
    ARTIFACT_CAUSAL_VALIDITY_BUNDLE_REF,
    ARTIFACT_CLAIMS_REF,
    ARTIFACT_HTE_RESULT_REF,
    ARTIFACT_POLICY_RECOMMENDATION_REF,
    ARTIFACT_SENSITIVITY_RESULT_REF,
    INPUT_UKRAINE_FOUNDRY_METHOD_BUNDLE_REF,
    INPUT_UKRAINE_SELECTED_METHOD_CONTRACT_REF,
)
from polisyos.scientist.orchestration.engine.context import ClaimCapableExecutionContext
from polisyos.scientist.orchestration.engine.protocol import (
    NodeError,
    NodeEvent,
    NodeOutcome,
    NodeSpec,
)
from polisyos.scientist.orchestration.engine.state_branching import branch_state

if TYPE_CHECKING:
    from polisyos.runtime.quality import EvaluationExecutionContext
    from polisyos.scientist.orchestration.engine.context import ExecutionContext
    from polisyos.scientist.orchestration.engine.state import ExperimentState

_METADATA = ComponentMetadata(
    component_id=ComponentId.parse("scientist.node_run_causal_evaluation@1.2.0"),
    kind=ComponentKind.SCIENTIST_NODE,
    abi_targets={"world_abi": "1.x"},
    display_name="Run Causal Evaluation",
    description="Execute causal inference method job and persist report/envelope artifacts.",
    tags=["builtin", "simulate", "causal"],
    capabilities=Capability.SCIENTIST_NODE,
)

_SPEC = NodeSpec(
    metadata=_METADATA,
    state_reads=[
        "run_id",
        "observational_data_ref",
        "causal_method_fqn",
        "causal_method_params",
        "params.random_seed",
        "params.causal_method_fqn",
        "params.causal_method_params",
        "params.enable_causal_refutation",
        "params.causal_refutation_params",
        "params.enable_causal_sensitivity",
        "params.causal_sensitivity_params",
        "params.causal_validity",
        f"inputs.{INPUT_UKRAINE_FOUNDRY_METHOD_BUNDLE_REF}",
        f"inputs.{INPUT_UKRAINE_SELECTED_METHOD_CONTRACT_REF}",
        "artifacts_index.ukraine_foundry_intake_receipt_ref",
    ],
    state_writes=[
        "params.query_treatment",
        "params.claim_ledger_status",
        "params.claim_ledger_limitation_code",
        f"artifacts_index.{ARTIFACT_CAUSAL_REPORT_REF}",
        f"artifacts_index.{ARTIFACT_CAUSAL_ENVELOPE_REF}",
        f"artifacts_index.{ARTIFACT_CAUSAL_METHOD_RESULT_REF}",
        f"artifacts_index.{ARTIFACT_CAUSAL_METHOD_EVIDENCE_REF}",
        f"artifacts_index.{ARTIFACT_CAUSAL_VALIDITY_BUNDLE_REF}",
        f"artifacts_index.{ARTIFACT_CLAIMS_REF}",
        f"artifacts_index.{ARTIFACT_HTE_RESULT_REF}",
        f"artifacts_index.{ARTIFACT_POLICY_RECOMMENDATION_REF}",
        f"artifacts_index.{ARTIFACT_SENSITIVITY_RESULT_REF}",
    ],
    produces=[
        ARTIFACT_CAUSAL_REPORT_REF,
        ARTIFACT_CAUSAL_ENVELOPE_REF,
        ARTIFACT_CAUSAL_METHOD_RESULT_REF,
        ARTIFACT_CAUSAL_METHOD_EVIDENCE_REF,
        ARTIFACT_CAUSAL_VALIDITY_BUNDLE_REF,
        ARTIFACT_CLAIMS_REF,
        ARTIFACT_HTE_RESULT_REF,
        ARTIFACT_POLICY_RECOMMENDATION_REF,
        ARTIFACT_SENSITIVITY_RESULT_REF,
    ],
)

_MARKET_WIDE_TREATMENT_KEYWORDS: tuple[str, ...] = (
    "tax_rate",
    "monetary_policy",
    "interest_rate",
    "trade_policy",
    "exchange_rate",
    "minimum_wage",
    "fiscal_policy",
    "subsidy",
    "tariff",
    "regulation",
    "licensing",
    "antitrust",
    "market_wide",
)

_CAUSAL_EVALUATION_LOAD_ERRORS = (
    TypeError,
    ValueError,
    ValidationError,
    FileNotFoundError,
    OSError,
)
_CAUSAL_EVALUATION_VALIDATION_ERRORS = (TypeError, ValueError, ValidationError)
_UKRAINE_INTAKE_RECEIPT_KEY = "ukraine_foundry_intake_receipt_ref"
_EVAL_SAFETY_BLOCKER_PREFIX = "polisyos.eval_safety"


def _eval_safety_blocker(name: str) -> str:
    return f"{_EVAL_SAFETY_BLOCKER_PREFIX}.{name}@1.0.0"


def _actual_causal_input_identities(state: ExperimentState) -> tuple[tuple[str, str], ...]:
    refs = (
        state.observational_data_ref,
        state.inputs.get(INPUT_UKRAINE_SELECTED_METHOD_CONTRACT_REF),
        state.inputs.get(INPUT_UKRAINE_FOUNDRY_METHOD_BUNDLE_REF),
        state.artifacts_index.get(_UKRAINE_INTAKE_RECEIPT_KEY),
    )
    return tuple((str(ref.artifact_id), str(ref.artifact_id)) for ref in refs if ref is not None)


def _causal_evaluation_safety_blockers(
    ctx: ExecutionContext,
    state: ExperimentState,
    *,
    evaluator_owner_id: ComponentId,
) -> tuple[str, ...]:
    context: EvaluationExecutionContext | None = ctx.eval_safety_execution_context
    if context is None:
        return (_eval_safety_blocker("execution_context_missing"),)

    mode_resolution = resolve_evaluation_mode(context.evaluation_mode)
    if mode_resolution.status != "accepted":
        return (mode_resolution.blocker_code or _eval_safety_blocker("evaluation_mode_unknown"),)
    if context.evaluator_owner_id != evaluator_owner_id:
        return (_eval_safety_blocker("evaluator_owner_mismatch"),)

    actual_identities = _actual_causal_input_identities(state)
    context_identities = tuple(
        (ref.artifact_id, ref.content_hash) for ref in context.evaluation_input_refs
    )
    provenance_identities = tuple(
        (row.input_ref.artifact_id, row.input_ref.content_hash)
        for row in context.evaluation_input_provenance
    )
    inputs_bind = bool(
        actual_identities
        and len(actual_identities) == len(set(actual_identities))
        and len(context_identities) == len(set(context_identities))
        and len(provenance_identities) == len(set(provenance_identities))
        and set(actual_identities) == set(context_identities) == set(provenance_identities)
        and all(
            row.predicate_provenance in {"recomputed", "independently_reconciled"}
            for row in context.evaluation_input_provenance
        )
    )
    if not inputs_bind or context.attempt_class != "non_simulation":
        return (_eval_safety_blocker("execution_context_binding_mismatch"),)
    if context.evaluation_mode == "simulate_only":
        return (_eval_safety_blocker("simulation_provenance_not_established"),)

    verifier = ctx.eval_safety_verifier
    if verifier is None:
        return (_eval_safety_blocker("verifier_unresolved"),)
    challenge = EvalSafetyAdmissionChallenge.fresh(consumer_component_id=evaluator_owner_id)
    receipt = verifier.require_admission(context, challenge)
    if not evaluation_safety_consumer_admission_is_verified(receipt, context, challenge):
        return receipt.blocker_codes or (_eval_safety_blocker("consumer_admission_blocked"),)
    return ()


def _is_rdd_method(method_fqn: str) -> bool:
    return "regression_discontinuity" in method_fqn


def _is_hte_method(method_fqn: str) -> bool:
    return method_fqn.startswith("causal.hte.") or method_fqn.startswith("causal.targeting.")


def _is_dowhy_method(method_fqn: str) -> bool:
    return "dowhy_identify_estimate" in method_fqn


def _is_dowhy_method_v1(method_fqn: str) -> bool:
    return "dowhy_identify_estimate@1." in method_fqn


def _coerce_method_params(raw: object) -> dict[str, Any]:
    if isinstance(raw, dict):
        return {str(key): value for key, value in raw.items()}
    return {}


def _supports_dowhy_refutation(report: CausalEffectReport) -> bool:
    return report.method in {
        CausalMethod.DOWHY_BACKDOOR,
        CausalMethod.DOWHY_IV,
        CausalMethod.DOWHY_FRONTDOOR,
    }


def _coerce_refutation_input(
    data: (
        PanelObservationalData
        | RDDObservationalData
        | HTEObservationalData
        | GraphCausalData
        | GraphCausalDataV1
    ),
) -> GraphCausalData | None:
    if isinstance(data, GraphCausalData):
        return data
    if isinstance(data, GraphCausalDataV1):
        return GraphCausalData(
            data=data.data,
            column_names=list(data.column_names),
            treatment=data.treatment,
            outcome=data.outcome,
            graph_dot=data.graph_gml,
            graph_ref=data.graph_ref,
            covariates=list(data.covariates),
        )
    return None


def _coerce_sensitivity_input(
    data: (
        PanelObservationalData
        | RDDObservationalData
        | HTEObservationalData
        | GraphCausalData
        | GraphCausalDataV1
    ),
) -> GraphCausalData | None:
    if isinstance(data, (GraphCausalData, GraphCausalDataV1)):
        return _coerce_refutation_input(data)
    if not isinstance(data, HTEObservationalData):
        return None

    feature_names = (
        [str(item) for item in data.feature_names]
        if data.feature_names is not None
        else [f"x{idx}" for idx in range(data.covariates.shape[1])]
    )
    confounder_names: list[str] = []
    matrices = [
        np.asarray(data.treatment, dtype=float).reshape(-1, 1),
        np.asarray(data.outcome, dtype=float).reshape(-1, 1),
        np.asarray(data.covariates, dtype=float),
    ]
    if data.confounders is not None:
        confounder_names = (
            [str(item) for item in data.confounder_names]
            if data.confounder_names is not None
            else [f"w{idx}" for idx in range(data.confounders.shape[1])]
        )
        matrices.append(np.asarray(data.confounders, dtype=float))
    return GraphCausalData(
        data=np.column_stack(matrices),
        column_names=["treatment", "outcome", *feature_names, *confounder_names],
        treatment="treatment",
        outcome="outcome",
        covariates=[*feature_names, *confounder_names],
    )


def _build_refutation_params(
    *,
    method_params: dict[str, Any],
    state: ExperimentState,
) -> dict[str, Any]:
    params: dict[str, Any] = {}
    if "method_name" in method_params:
        params["method_name"] = method_params["method_name"]
    if "estimand_type" in method_params:
        params["estimand_type"] = method_params["estimand_type"]
    params.update(_coerce_method_params(state.params.get("causal_refutation_params")))
    return params


def _build_sensitivity_params(
    *,
    report: CausalEffectReport,
    method_params: dict[str, Any],
    state: ExperimentState,
    data: GraphCausalData,
) -> dict[str, Any]:
    params: dict[str, Any] = {
        "point_estimate": report.point_estimate,
        "sample_size": data.sample_size,
        "covariates": list(data.covariates),
    }
    if report.confidence_interval is not None:
        params["confidence_interval"] = [
            float(report.confidence_interval[0]),
            float(report.confidence_interval[1]),
        ]
    if report.standard_error is not None:
        params["standard_error"] = float(report.standard_error)
    if "baseline_risk" in method_params:
        params["baseline_risk"] = method_params["baseline_risk"]
    params.update(_coerce_method_params(state.params.get("causal_sensitivity_params")))
    return params


def _append_input_ref(
    refs: list[InputRef],
    *,
    artifact_id: object | None,
    role: str,
) -> None:
    if artifact_id is None:
        return
    refs.append(InputRef(artifact_id=str(artifact_id), role=role))


def _to_core_artifact_ref(ref: object | None) -> ArtifactRef | None:
    if ref is None:
        return None
    if isinstance(ref, ArtifactRef):
        return ref
    model_dump = getattr(ref, "model_dump", None)
    if callable(model_dump):
        return ArtifactRef.model_validate(model_dump(mode="json"))
    return ArtifactRef.model_validate(ref)


def _load_observational_data(
    ctx: ExecutionContext,
    state: ExperimentState,
    method_fqn: str,
) -> (
    PanelObservationalData
    | RDDObservationalData
    | HTEObservationalData
    | GraphCausalData
    | GraphCausalDataV1
):
    if state.observational_data_ref is None:
        raise ValueError("observational_data_ref is required for causal evaluation")
    payload = from_canonical_bytes(ctx.store.get_bytes(state.observational_data_ref.artifact_id))
    if _is_rdd_method(method_fqn):
        return RDDObservationalData.model_validate(payload)
    if _is_hte_method(method_fqn):
        return HTEObservationalData.model_validate(payload)
    if _is_dowhy_method(method_fqn):
        if _is_dowhy_method_v1(method_fqn):
            return GraphCausalDataV1.model_validate(payload)
        return GraphCausalData.model_validate(payload)
    return PanelObservationalData.model_validate(payload)


def _extract_query_treatment(
    data: (
        PanelObservationalData
        | RDDObservationalData
        | HTEObservationalData
        | GraphCausalData
        | GraphCausalDataV1
    ),
    *,
    method_params: dict[str, Any],
) -> str | None:
    if isinstance(data, (GraphCausalData, GraphCausalDataV1)):
        candidate = str(data.treatment).strip()
        return candidate or None

    for key in ("treatment", "treatment_name", "query_treatment"):
        raw = method_params.get(key)
        if isinstance(raw, str) and raw.strip():
            return raw.strip()
    return None


def _infer_sutva_risk(query_treatment: str | None) -> str | None:
    if not query_treatment:
        return None
    lowered = query_treatment.lower()
    if any(keyword in lowered for keyword in _MARKET_WIDE_TREATMENT_KEYWORDS):
        return "high"
    return None


@dataclass(frozen=True)
class RunCausalEvaluationNode:
    """Run causal evaluation node implementation."""

    @property
    def spec(self) -> NodeSpec:
        return _SPEC

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        if state.observational_data_ref is None:
            return NodeOutcome(
                status="skip",
                state=state,
                events=[
                    NodeEvent(
                        level="info", message="No observational_data_ref; skip causal evaluation"
                    )
                ],
                skip_blocker=_phase2_missing_input_blocker(
                    missing_input="observational_data_ref",
                    reason="No observational measurement root was produced for causal evaluation.",
                    phase="run_causal_evaluation",
                ),
            )

        method_fqn = state.causal_method_fqn or str(
            state.params.get("causal_method_fqn", "causal.inference.synthetic_control")
        )
        method_params = {}
        method_params.update(_coerce_method_params(state.causal_method_params))
        if not method_params:
            method_params.update(_coerce_method_params(state.params.get("causal_method_params")))
        seed = int(state.params.get("random_seed", 0) or 0)

        safety_blockers = _causal_evaluation_safety_blockers(
            ctx,
            state,
            evaluator_owner_id=self.spec.metadata.component_id,
        )
        if safety_blockers:
            return NodeOutcome(
                status="fail",
                state=state,
                error=NodeError(
                    code=node_errors.ERROR_FOUNDRY_EXECUTE_FAILED,
                    message="Attempted-evaluation safety admission blocked causal evaluation.",
                    details={"blocker_codes": list(safety_blockers)},
                ),
            )

        try:
            ensure_causal_methods_registered()
            observational_data = _load_observational_data(ctx, state, method_fqn)
        except _CAUSAL_EVALUATION_LOAD_ERRORS as exc:
            return NodeOutcome(
                status="fail",
                state=state,
                error=NodeError(
                    code=node_errors.ERROR_MISSING_INPUT,
                    message=f"Failed to load observational data for causal evaluation: {exc}",
                ),
            )

        method_job_input_refs = {}
        selected_contract_ref = state.inputs.get(INPUT_UKRAINE_SELECTED_METHOD_CONTRACT_REF)
        method_input_bundle_ref = state.inputs.get(INPUT_UKRAINE_FOUNDRY_METHOD_BUNDLE_REF)
        intake_receipt_ref = state.artifacts_index.get(_UKRAINE_INTAKE_RECEIPT_KEY)
        if selected_contract_ref is not None:
            method_job_input_refs["ukraine_selected_method_contract"] = selected_contract_ref
        if method_input_bundle_ref is not None:
            method_job_input_refs["ukraine_method_input_bundle"] = method_input_bundle_ref
        if intake_receipt_ref is not None:
            method_job_input_refs["ukraine_intake_receipt"] = intake_receipt_ref

        spec = JobSpec(
            job_kind="method",
            method_fqn=method_fqn,
            method_params=method_params,
            seed=seed,
            input_refs=method_job_input_refs,
        )
        result = run_job(
            spec,
            cas_root=ctx.store.root,
            method_state=observational_data,
        )
        if result.issues:
            return NodeOutcome(
                status="fail",
                state=state,
                error=NodeError(
                    code=node_errors.ERROR_FOUNDRY_EXECUTE_FAILED,
                    message="Causal method job failed",
                    details={"issues": result.issues},
                ),
            )

        output = result.final_state if isinstance(result.final_state, dict) else {}
        report_raw = output.get("report")
        if report_raw is None:
            return NodeOutcome(
                status="fail",
                state=state,
                error=NodeError(
                    code=node_errors.ERROR_FOUNDRY_EXECUTE_FAILED,
                    message="Causal method output missing report",
                ),
            )

        try:
            report = CausalEffectReport.model_validate(report_raw)
        except _CAUSAL_EVALUATION_VALIDATION_ERRORS as exc:
            return NodeOutcome(
                status="fail",
                state=state,
                error=NodeError(
                    code=node_errors.ERROR_FOUNDRY_EXECUTE_FAILED,
                    message=f"Causal method output report is invalid: {exc}",
                ),
            )
        query_treatment = _extract_query_treatment(
            observational_data,
            method_params=method_params,
        )
        inferred_sutva_risk = _infer_sutva_risk(query_treatment)
        report_update: dict[str, Any] = {}
        if report.sutva_violation_risk is None and inferred_sutva_risk is not None:
            report_update["sutva_violation_risk"] = inferred_sutva_risk
        if query_treatment:
            metadata = dict(report.metadata)
            metadata.setdefault("query_treatment", query_treatment)
            report_update["metadata"] = metadata
        if report_update:
            report = report.model_copy(update=report_update)
        input_refs: list[InputRef] = []
        if result.method_result_ref is not None:
            _append_input_ref(
                input_refs,
                artifact_id=result.method_result_ref.artifact_id,
                role="causal_method_result",
            )
        if result.method_evidence_ref is not None:
            _append_input_ref(
                input_refs,
                artifact_id=result.method_evidence_ref.artifact_id,
                role="causal_method_evidence",
            )

        refutation_result = None
        refutation_auto: dict[str, Any] = {
            "enabled": state.params.get("enable_causal_refutation", True) is not False,
            "attempted": False,
            "status": "skipped",
            "method_fqn": "causal.refutation.dowhy_refute@1.0.0",
        }
        should_refute = (
            _is_dowhy_method(method_fqn)
            and report.status == EstimationStatus.SUCCESS
            and _supports_dowhy_refutation(report)
            and state.params.get("enable_causal_refutation", True) is not False
        )
        if should_refute:
            refutation_auto["attempted"] = True
            refutation_input = _coerce_refutation_input(observational_data)
            if refutation_input is None:
                refutation_auto["status"] = "failed"
                refutation_auto["reason"] = "unsupported_refutation_input"
            else:
                refutation_spec = JobSpec(
                    job_kind="method",
                    method_fqn="causal.refutation.dowhy_refute@1.0.0",
                    method_params=_build_refutation_params(
                        method_params=method_params,
                        state=state,
                    ),
                    seed=seed,
                )
                refutation_result = run_job(
                    refutation_spec,
                    cas_root=ctx.store.root,
                    method_state=refutation_input,
                )
                if refutation_result.method_result_ref is not None:
                    _append_input_ref(
                        input_refs,
                        artifact_id=refutation_result.method_result_ref.artifact_id,
                        role="causal_refutation_method_result",
                    )
                if refutation_result.method_evidence_ref is not None:
                    _append_input_ref(
                        input_refs,
                        artifact_id=refutation_result.method_evidence_ref.artifact_id,
                        role="causal_refutation_method_evidence",
                    )
                if refutation_result.issues:
                    refutation_auto["status"] = "failed"
                    refutation_auto["issues"] = list(refutation_result.issues)
                else:
                    ref_output = (
                        refutation_result.final_state
                        if isinstance(refutation_result.final_state, dict)
                        else {}
                    )
                    ref_report_raw = ref_output.get("report")
                    if ref_report_raw is None:
                        refutation_auto["status"] = "failed"
                        refutation_auto["reason"] = "missing_refutation_report"
                    else:
                        try:
                            ref_report = CausalEffectReport.model_validate(ref_report_raw)
                        except _CAUSAL_EVALUATION_VALIDATION_ERRORS as exc:
                            refutation_auto["status"] = "failed"
                            refutation_auto["reason"] = f"invalid_refutation_report: {exc}"
                        else:
                            diagnostics = list(report.diagnostics)
                            diagnostics.extend(ref_report.diagnostics)
                            metadata = dict(report.metadata)
                            metadata["refutation_auto"] = {
                                **refutation_auto,
                                "status": "success",
                                "refutation_tests_total": len(ref_report.refutation_results),
                                "refutation_tests_passed": sum(
                                    1 for item in ref_report.refutation_results if item.passed
                                ),
                            }
                            report = report.model_copy(
                                update={
                                    "refutation_results": list(ref_report.refutation_results),
                                    "diagnostics": diagnostics,
                                    "metadata": metadata,
                                }
                            )
                            refutation_auto = metadata["refutation_auto"]

        if (
            _is_dowhy_method(method_fqn)
            and _supports_dowhy_refutation(report)
            and "refutation_auto" not in report.metadata
        ):
            metadata = dict(report.metadata)
            metadata["refutation_auto"] = refutation_auto
            report = report.model_copy(update={"metadata": metadata})

        sensitivity_ref = None
        sensitivity_auto: dict[str, Any] = {
            "enabled": state.params.get("enable_causal_sensitivity", True) is not False,
            "attempted": False,
            "status": "skipped",
            "method_fqn": "causal.sensitivity.sensitivity_metrics@1.0.0",
        }
        should_sensitivity = (
            report.status == EstimationStatus.SUCCESS
            and state.params.get("enable_causal_sensitivity", True) is not False
        )
        if should_sensitivity:
            sensitivity_auto["attempted"] = True
            sensitivity_input = _coerce_sensitivity_input(observational_data)
            if sensitivity_input is None:
                sensitivity_auto["status"] = "failed"
                sensitivity_auto["reason"] = "unsupported_sensitivity_input"
            else:
                sensitivity_spec = JobSpec(
                    job_kind="method",
                    method_fqn="causal.sensitivity.sensitivity_metrics@1.0.0",
                    method_params=_build_sensitivity_params(
                        report=report,
                        method_params=method_params,
                        state=state,
                        data=sensitivity_input,
                    ),
                    seed=seed,
                )
                sensitivity_job = run_job(
                    sensitivity_spec,
                    cas_root=ctx.store.root,
                    method_state=sensitivity_input,
                )
                if sensitivity_job.method_result_ref is not None:
                    _append_input_ref(
                        input_refs,
                        artifact_id=sensitivity_job.method_result_ref.artifact_id,
                        role="causal_sensitivity_method_result",
                    )
                if sensitivity_job.method_evidence_ref is not None:
                    _append_input_ref(
                        input_refs,
                        artifact_id=sensitivity_job.method_evidence_ref.artifact_id,
                        role="causal_sensitivity_method_evidence",
                    )
                if sensitivity_job.issues:
                    sensitivity_auto["status"] = "failed"
                    sensitivity_auto["issues"] = list(sensitivity_job.issues)
                else:
                    sensitivity_output = (
                        sensitivity_job.final_state
                        if isinstance(sensitivity_job.final_state, dict)
                        else {}
                    )
                    sensitivity_raw = sensitivity_output.get("sensitivity_result")
                    if sensitivity_raw is None:
                        sensitivity_auto["status"] = "failed"
                        sensitivity_auto["reason"] = "missing_sensitivity_result"
                    else:
                        try:
                            sensitivity_result = SensitivityResult.model_validate(sensitivity_raw)
                        except _CAUSAL_EVALUATION_VALIDATION_ERRORS as exc:
                            sensitivity_auto["status"] = "failed"
                            sensitivity_auto["reason"] = f"invalid_sensitivity_result: {exc}"
                        else:
                            sensitivity_ref = _to_core_artifact_ref(
                                persist_sensitivity_result(
                                    ctx.store,
                                    sensitivity_result,
                                    inputs=input_refs or None,
                                )
                            )
                            sensitivity_auto = {
                                **sensitivity_auto,
                                "status": "success",
                                "is_robust": sensitivity_result.is_robust,
                                "e_value": sensitivity_result.e_value,
                                "rosenbaum_gamma": sensitivity_result.rosenbaum_gamma,
                                "artifact_id": str(sensitivity_ref.artifact_id),
                                "warnings": (
                                    list(sensitivity_output.get("warnings", []))
                                    if isinstance(sensitivity_output.get("warnings"), list)
                                    else []
                                ),
                            }

        metadata = dict(report.metadata)
        metadata["sensitivity_auto"] = sensitivity_auto
        report = report.model_copy(update={"metadata": metadata})

        validity_bundle_ref = persist_causal_validity_bundle(
            ctx=ctx,
            state=state,
            report=report,
            method_fqn=method_fqn,
            method_params=method_params,
            observational_data=observational_data,
            seed=seed,
            sensitivity_ref=sensitivity_ref,
            sensitivity_auto=sensitivity_auto,
            inputs=input_refs,
        )

        report_ref = _to_core_artifact_ref(
            persist_causal_effect_report(
                ctx.store,
                report,
                inputs=input_refs or None,
            )
        )

        envelope_ref = None
        envelope_raw = output.get("envelope")
        envelope = None
        if envelope_raw is not None:
            try:
                envelope = UncertaintyEnvelope.model_validate(envelope_raw)
            except _CAUSAL_EVALUATION_VALIDATION_ERRORS as exc:
                return NodeOutcome(
                    status="fail",
                    state=state,
                    error=NodeError(
                        code=node_errors.ERROR_FOUNDRY_EXECUTE_FAILED,
                        message=f"Causal method output envelope is invalid: {exc}",
                    ),
                )
        else:
            envelope = report.to_uncertainty_envelope()
        if envelope is not None:
            envelope_ref = _to_core_artifact_ref(
                persist_uncertainty_envelope(
                    ctx.store,
                    envelope,
                    inputs=input_refs or None,
                )
            )

        hte_ref = None
        hte_raw = output.get("hte_result")
        if hte_raw is not None:
            try:
                hte_result = HTEResult.model_validate(hte_raw)
            except _CAUSAL_EVALUATION_VALIDATION_ERRORS as exc:
                return NodeOutcome(
                    status="fail",
                    state=state,
                    error=NodeError(
                        code=node_errors.ERROR_FOUNDRY_EXECUTE_FAILED,
                        message=f"Causal method output hte_result is invalid: {exc}",
                    ),
                )
            hte_ref = _to_core_artifact_ref(
                persist_hte_result(
                    ctx.store,
                    hte_result,
                    inputs=input_refs or None,
                )
            )

        recommendation_ref = None
        recommendation_raw = output.get("policy_recommendation")
        if recommendation_raw is not None:
            try:
                recommendation = PolicyRecommendation.model_validate(recommendation_raw)
            except _CAUSAL_EVALUATION_VALIDATION_ERRORS as exc:
                return NodeOutcome(
                    status="fail",
                    state=state,
                    error=NodeError(
                        code=node_errors.ERROR_FOUNDRY_EXECUTE_FAILED,
                        message=f"Causal method output policy_recommendation is invalid: {exc}",
                    ),
                )
            recommendation_ref = _to_core_artifact_ref(
                persist_policy_recommendation(
                    ctx.store,
                    recommendation,
                    inputs=input_refs or None,
                )
            )

        claims_ref = None
        if is_claim_spine_enabled(state.params):
            claim_source_refs = [
                ref
                for ref in (
                    report_ref,
                    envelope_ref,
                    _to_core_artifact_ref(result.method_result_ref),
                    _to_core_artifact_ref(result.method_evidence_ref),
                    validity_bundle_ref,
                    sensitivity_ref,
                    hte_ref,
                    recommendation_ref,
                )
                if ref is not None
            ]
            claim_ledger = project_causal_effect_claims(
                report,
                run_id=state.run_id,
                source_artifact_refs=claim_source_refs,
            )
            if isinstance(ctx, ClaimCapableExecutionContext):
                claims_ref = ctx.claim_ledger_owner.persist_candidate_ledger(ledger=claim_ledger)

        new_state = branch_state(
            state,
            write_paths=(
                "params.query_treatment",
                "params.claim_ledger_status",
                "params.claim_ledger_limitation_code",
                f"artifacts_index.{ARTIFACT_CAUSAL_REPORT_REF}",
                f"artifacts_index.{ARTIFACT_CAUSAL_ENVELOPE_REF}",
                f"artifacts_index.{ARTIFACT_CAUSAL_METHOD_RESULT_REF}",
                f"artifacts_index.{ARTIFACT_CAUSAL_METHOD_EVIDENCE_REF}",
                f"artifacts_index.{ARTIFACT_CAUSAL_VALIDITY_BUNDLE_REF}",
                f"artifacts_index.{ARTIFACT_CLAIMS_REF}",
                f"artifacts_index.{ARTIFACT_HTE_RESULT_REF}",
                f"artifacts_index.{ARTIFACT_POLICY_RECOMMENDATION_REF}",
                f"artifacts_index.{ARTIFACT_SENSITIVITY_RESULT_REF}",
            ),
        ).state
        if query_treatment:
            new_state.params["query_treatment"] = query_treatment
        else:
            new_state.params.pop("query_treatment", None)
        if is_claim_spine_enabled(state.params) and not isinstance(
            ctx, ClaimCapableExecutionContext
        ):
            new_state.params["claim_ledger_status"] = "not_established"
            new_state.params["claim_ledger_limitation_code"] = "claim_ledger_owner_not_established"
        new_state.artifacts_index[ARTIFACT_CAUSAL_REPORT_REF] = report_ref
        if envelope_ref is not None:
            new_state.artifacts_index[ARTIFACT_CAUSAL_ENVELOPE_REF] = envelope_ref
        if result.method_result_ref is not None:
            new_state.artifacts_index[ARTIFACT_CAUSAL_METHOD_RESULT_REF] = result.method_result_ref
        if result.method_evidence_ref is not None:
            new_state.artifacts_index[ARTIFACT_CAUSAL_METHOD_EVIDENCE_REF] = (
                result.method_evidence_ref
            )
        if validity_bundle_ref is not None:
            new_state.artifacts_index[ARTIFACT_CAUSAL_VALIDITY_BUNDLE_REF] = validity_bundle_ref
        if claims_ref is not None:
            new_state.artifacts_index[ARTIFACT_CLAIMS_REF] = claims_ref
        if hte_ref is not None:
            new_state.artifacts_index[ARTIFACT_HTE_RESULT_REF] = hte_ref
        if recommendation_ref is not None:
            new_state.artifacts_index[ARTIFACT_POLICY_RECOMMENDATION_REF] = recommendation_ref
        if sensitivity_ref is not None:
            new_state.artifacts_index[ARTIFACT_SENSITIVITY_RESULT_REF] = sensitivity_ref

        produced = [report_ref]
        if envelope_ref is not None:
            produced.append(envelope_ref)
        if result.method_result_ref is not None:
            produced.append(result.method_result_ref)
        if result.method_evidence_ref is not None:
            produced.append(result.method_evidence_ref)
        if validity_bundle_ref is not None:
            produced.append(validity_bundle_ref)
        if claims_ref is not None:
            produced.append(claims_ref)
        if hte_ref is not None:
            produced.append(hte_ref)
        if recommendation_ref is not None:
            produced.append(recommendation_ref)
        if sensitivity_ref is not None:
            produced.append(sensitivity_ref)

        return NodeOutcome(
            status="ok",
            state=new_state,
            artifacts=produced,
            events=[
                NodeEvent(
                    level="info",
                    message=(
                        f"Causal evaluation completed: method={report.method.value}, "
                        f"status={report.status.value}, "
                        f"refutation={report.metadata.get('refutation_auto', {}).get('status')}, "
                        f"sensitivity={report.metadata.get('sensitivity_auto', {}).get('status')}, "
                        f"claims={'yes' if claims_ref is not None else 'no'}, "
                        f"validity_bundle={'yes' if validity_bundle_ref is not None else 'no'}"
                    ),
                )
            ],
        )


def _phase2_missing_input_blocker(
    *,
    missing_input: str,
    reason: str,
    phase: str,
):
    return build_skip_blocker_record(
        node_id=str(_SPEC.metadata.component_id),
        alias="run_causal_evaluation",
        node_kind="causal",
        reason=reason,
        missing_input=missing_input,
        owner="gy_phase2_blocked_input_producer",
        phase=phase,
        downstream_impact="Phase-2 ESTIMATE cannot consume Foundry output without this input.",
        allowed_profile="dev",
        closeout_blocking_policy="blocks_authority",
        scorecard_blocking_policy="blocks_authority",
        approval_blocking_policy="blocks_authority",
        public_export_blocking_policy="blocks_authority",
        blocker_code="gy_phase2_blocked_input_producer_missing",
    )


__all__ = ["RunCausalEvaluationNode"]
