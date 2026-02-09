from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from polisyos.core.artifacts.manifest import InputRef
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.foundry.methods.causal import (
    HTEObservationalData,
    PanelObservationalData,
    RDDObservationalData,
    ensure_causal_methods_registered,
)
from polisyos.ir.analytics.causal import CausalEffectReport, persist_causal_effect_report
from polisyos.ir.analytics.hte import (
    HTEResult,
    PolicyRecommendation,
    persist_hte_result,
    persist_policy_recommendation,
)
from polisyos.ir.analytics.uncertainty import UncertaintyEnvelope, persist_uncertainty_envelope
from polisyos.scientist.compute.job_spec import JobSpec
from polisyos.scientist.compute.runner import run_job
from polisyos.scientist.engine.context import ExecutionContext
from polisyos.scientist.engine.protocol import NodeError, NodeEvent, NodeOutcome, NodeSpec
from polisyos.scientist.engine.state import ExperimentState
from polisyos.scientist.nodes.builtins import errors as node_errors
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_CAUSAL_ENVELOPE_REF,
    ARTIFACT_CAUSAL_METHOD_EVIDENCE_REF,
    ARTIFACT_CAUSAL_METHOD_RESULT_REF,
    ARTIFACT_CAUSAL_REPORT_REF,
    ARTIFACT_HTE_RESULT_REF,
    ARTIFACT_POLICY_RECOMMENDATION_REF,
)

_METADATA = ComponentMetadata(
    component_id=ComponentId.parse("scientist.node_run_causal_evaluation@1.1.0"),
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
    ],
    state_writes=[
        f"artifacts_index.{ARTIFACT_CAUSAL_REPORT_REF}",
        f"artifacts_index.{ARTIFACT_CAUSAL_ENVELOPE_REF}",
        f"artifacts_index.{ARTIFACT_CAUSAL_METHOD_RESULT_REF}",
        f"artifacts_index.{ARTIFACT_CAUSAL_METHOD_EVIDENCE_REF}",
        f"artifacts_index.{ARTIFACT_HTE_RESULT_REF}",
        f"artifacts_index.{ARTIFACT_POLICY_RECOMMENDATION_REF}",
    ],
    produces=[
        ARTIFACT_CAUSAL_REPORT_REF,
        ARTIFACT_CAUSAL_ENVELOPE_REF,
        ARTIFACT_CAUSAL_METHOD_RESULT_REF,
        ARTIFACT_CAUSAL_METHOD_EVIDENCE_REF,
        ARTIFACT_HTE_RESULT_REF,
        ARTIFACT_POLICY_RECOMMENDATION_REF,
    ],
)


def _is_rdd_method(method_fqn: str) -> bool:
    return "regression_discontinuity" in method_fqn


def _is_hte_method(method_fqn: str) -> bool:
    return method_fqn.startswith("causal.hte.") or method_fqn.startswith("causal.targeting.")


def _coerce_method_params(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return {str(key): value for key, value in raw.items()}
    return {}


def _load_observational_data(
    ctx: ExecutionContext,
    state: ExperimentState,
    method_fqn: str,
) -> PanelObservationalData | RDDObservationalData | HTEObservationalData:
    assert state.observational_data_ref is not None
    payload = from_canonical_bytes(ctx.store.get_bytes(state.observational_data_ref.artifact_id))
    if _is_rdd_method(method_fqn):
        return RDDObservationalData.model_validate(payload)
    if _is_hte_method(method_fqn):
        return HTEObservationalData.model_validate(payload)
    return PanelObservationalData.model_validate(payload)


@dataclass(frozen=True)
class RunCausalEvaluationNode:
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
            )

        method_fqn = state.causal_method_fqn or str(
            state.params.get("causal_method_fqn", "causal.inference.synthetic_control")
        )
        method_params = {}
        method_params.update(_coerce_method_params(state.causal_method_params))
        if not method_params:
            method_params.update(_coerce_method_params(state.params.get("causal_method_params")))
        seed = int(state.params.get("random_seed", 0) or 0)

        try:
            ensure_causal_methods_registered()
            observational_data = _load_observational_data(ctx, state, method_fqn)
        except Exception as exc:
            return NodeOutcome(
                status="fail",
                state=state,
                error=NodeError(
                    code=node_errors.ERROR_MISSING_INPUT,
                    message=f"Failed to load observational data for causal evaluation: {exc}",
                ),
            )

        spec = JobSpec(
            job_kind="method",
            method_fqn=method_fqn,
            method_params=method_params,
            seed=seed,
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

        report = CausalEffectReport.model_validate(report_raw)
        input_refs: list[InputRef] = []
        if result.method_result_ref is not None:
            input_refs.append(
                InputRef(
                    artifact_id=result.method_result_ref.artifact_id, role="causal_method_result"
                )
            )
        report_ref = persist_causal_effect_report(
            ctx.store,
            report,
            inputs=input_refs or None,
        )

        envelope_ref = None
        envelope_raw = output.get("envelope")
        envelope = None
        if envelope_raw is not None:
            envelope = UncertaintyEnvelope.model_validate(envelope_raw)
        else:
            envelope = report.to_uncertainty_envelope()
        if envelope is not None:
            envelope_ref = persist_uncertainty_envelope(
                ctx.store,
                envelope,
                inputs=input_refs or None,
            )

        hte_ref = None
        hte_raw = output.get("hte_result")
        if hte_raw is not None:
            hte_result = HTEResult.model_validate(hte_raw)
            hte_ref = persist_hte_result(
                ctx.store,
                hte_result,
                inputs=input_refs or None,
            )

        recommendation_ref = None
        recommendation_raw = output.get("policy_recommendation")
        if recommendation_raw is not None:
            recommendation = PolicyRecommendation.model_validate(recommendation_raw)
            recommendation_ref = persist_policy_recommendation(
                ctx.store,
                recommendation,
                inputs=input_refs or None,
            )

        new_state = state.model_copy(deep=True)
        new_state.artifacts_index[ARTIFACT_CAUSAL_REPORT_REF] = report_ref
        if envelope_ref is not None:
            new_state.artifacts_index[ARTIFACT_CAUSAL_ENVELOPE_REF] = envelope_ref
        if result.method_result_ref is not None:
            new_state.artifacts_index[ARTIFACT_CAUSAL_METHOD_RESULT_REF] = result.method_result_ref
        if result.method_evidence_ref is not None:
            new_state.artifacts_index[ARTIFACT_CAUSAL_METHOD_EVIDENCE_REF] = (
                result.method_evidence_ref
            )
        if hte_ref is not None:
            new_state.artifacts_index[ARTIFACT_HTE_RESULT_REF] = hte_ref
        if recommendation_ref is not None:
            new_state.artifacts_index[ARTIFACT_POLICY_RECOMMENDATION_REF] = recommendation_ref

        produced = [report_ref]
        if envelope_ref is not None:
            produced.append(envelope_ref)
        if result.method_result_ref is not None:
            produced.append(result.method_result_ref)
        if result.method_evidence_ref is not None:
            produced.append(result.method_evidence_ref)
        if hte_ref is not None:
            produced.append(hte_ref)
        if recommendation_ref is not None:
            produced.append(recommendation_ref)

        return NodeOutcome(
            status="ok",
            state=new_state,
            artifacts=produced,
            events=[
                NodeEvent(
                    level="info",
                    message=(
                        f"Causal evaluation completed: method={report.method.value}, "
                        f"status={report.status.value}"
                    ),
                )
            ],
        )


__all__ = ["RunCausalEvaluationNode"]
