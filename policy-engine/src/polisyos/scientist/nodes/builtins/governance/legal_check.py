"""Public governance legal check module API."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

from polisyos.common.logger import get_logger
from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.core.contracts.foundry import SimulationResultRef
from polisyos.core.contracts.lex import LegalEvaluationRequest
from polisyos.core.contracts.trinity import ModelSpecRef, PolicySpecRef, TrinityBundleRef
from polisyos.lex.api import assemble_norm_pack, evaluate_legality
from polisyos.lex.types import NormPackBuildRequest
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.error_semantics import emit_degraded_path
from polisyos.scientist.orchestration.engine.protocol import NodeError, NodeEvent, NodeOutcome, NodeSpec
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.state_branching import branch_state
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_SIMULATION_RESULT_REF,
    INPUT_MODEL_SPEC_REF,
    INPUT_NORM_PACK_REF,
    INPUT_POLICY_SPEC_REF,
    INPUT_TRINITY_BUNDLE_REF,
    REPORT_CHANGE_PROPOSAL_REF,
    REPORT_LEGAL_REPORT_REF,
)

logger = get_logger(__name__)
_LEGAL_CHECK_READ_ERRORS = (
    AttributeError,
    KeyError,
    OSError,
    RuntimeError,
    TypeError,
    ValidationError,
    ValueError,
)
_LEGAL_EVALUATION_ERRORS = (
    AttributeError,
    KeyError,
    OSError,
    RuntimeError,
    TypeError,
    ValidationError,
    ValueError,
)

_METADATA = ComponentMetadata(
    component_id=ComponentId.parse("scientist.node_legal_check@1.0.1"),
    kind=ComponentKind.SCIENTIST_NODE,
    abi_targets={"world_abi": "1.x"},
    display_name="Legal Check",
    description="Evaluate policy legality and emit legal report/change proposals.",
    tags=["builtin", "governance", "lex"],
    capabilities=Capability.SCIENTIST_NODE,
)

_SPEC = NodeSpec(
    metadata=_METADATA,
    state_reads=[
        "run_id",
        f"inputs.{INPUT_TRINITY_BUNDLE_REF}",
        f"inputs.{INPUT_POLICY_SPEC_REF}",
        f"inputs.{INPUT_MODEL_SPEC_REF}",
        f"inputs.{INPUT_NORM_PACK_REF}",
        f"artifacts_index.{ARTIFACT_SIMULATION_RESULT_REF}",
        "params.jurisdiction",
        "params.as_of",
        "params.strict_legal",
        "params.fact_log_root",
    ],
    state_writes=[
        f"inputs.{INPUT_NORM_PACK_REF}",
        f"reports_index.{REPORT_LEGAL_REPORT_REF}",
        f"reports_index.{REPORT_CHANGE_PROPOSAL_REF}",
    ],
    produces=[REPORT_LEGAL_REPORT_REF, REPORT_CHANGE_PROPOSAL_REF],
)


def _coerce_trinity_ref(value: ArtifactRef | None) -> TrinityBundleRef | None:
    if value is None:
        return None
    return TrinityBundleRef.model_validate(value.model_dump())


def _coerce_policy_ref(value: ArtifactRef | None) -> PolicySpecRef | None:
    if value is None:
        return None
    return PolicySpecRef.model_validate(value.model_dump())


def _coerce_model_ref(value: ArtifactRef | None) -> ModelSpecRef | None:
    if value is None:
        return None
    return ModelSpecRef.model_validate(value.model_dump())


def _coerce_simulation_result_ref(value: ArtifactRef | None) -> SimulationResultRef | None:
    if value is None:
        return None
    return SimulationResultRef.model_validate(value.model_dump())


def _fact_log_root(ctx: ExecutionContext, state: ExperimentState) -> Path:
    candidate = state.params.get("fact_log_root")
    if isinstance(candidate, str) and candidate.strip():
        return Path(candidate.strip())
    return Path(ctx.store.root).parent


def _read_compliance_grade(
    ctx: ExecutionContext,
    state: ExperimentState,
    report_ref: ArtifactRef,
) -> tuple[str | None, dict[str, object] | None]:
    try:
        payload = from_canonical_bytes(ctx.store.get_bytes(report_ref.artifact_id))
    except _LEGAL_CHECK_READ_ERRORS as exc:
        return None, emit_degraded_path(
            component="scientist.legal_check",
            operation="read_compliance_grade",
            reason="legal_report_grade_load_failed",
            exc=exc,
            details={
                "run_id": state.run_id,
                "artifact_id": str(report_ref.artifact_id),
            },
            log=logger,
            metrics=ctx.metrics,
        )
    if not isinstance(payload, dict):
        return None, None
    summary = payload.get("summary")
    if not isinstance(summary, dict):
        return None, None
    grade = summary.get("compliance_grade")
    if isinstance(grade, str):
        return grade, None
    return None, None


def _skip_legal_check(
    *,
    state: ExperimentState,
    message: str,
    reason: str,
    details: dict[str, object] | None = None,
) -> NodeOutcome:
    attrs = {"skip_reason": reason}
    if details:
        attrs.update(details)
    return NodeOutcome(
        status="skip",
        state=state,
        events=[NodeEvent(level="info", message=message, attrs=attrs)],
    )


@dataclass(frozen=True)
class LegalCheckNode:
    """Legal check node implementation."""

    @property
    def spec(self) -> NodeSpec:
        return _SPEC

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        simulation_result_artifact_ref = state.artifacts_index.get(ARTIFACT_SIMULATION_RESULT_REF)
        if simulation_result_artifact_ref is None:
            return _skip_legal_check(
                state=state,
                message="Legal check skipped: missing simulation_result_ref",
                reason="missing_simulation_result",
                details={"required": ARTIFACT_SIMULATION_RESULT_REF},
            )
        simulation_result_ref = _coerce_simulation_result_ref(simulation_result_artifact_ref)
        if simulation_result_ref is None:
            return NodeOutcome(
                status="fail",
                state=state,
                error=NodeError(
                    code="lex.invalid_simulation_result_ref",
                    message="Legal check received an invalid simulation_result_ref",
                    details={"required": ARTIFACT_SIMULATION_RESULT_REF},
                ),
            )

        jurisdiction = state.params.get("jurisdiction")
        as_of = state.params.get("as_of")
        if not isinstance(jurisdiction, str) or not jurisdiction.strip():
            return _skip_legal_check(
                state=state,
                message="Legal check skipped: missing params.jurisdiction",
                reason="missing_jurisdiction",
                details={"required": "params.jurisdiction"},
            )
        if not isinstance(as_of, str) or not as_of.strip():
            return _skip_legal_check(
                state=state,
                message="Legal check skipped: missing params.as_of",
                reason="missing_as_of",
                details={"required": "params.as_of"},
            )

        trinity_bundle_ref = _coerce_trinity_ref(state.inputs.get(INPUT_TRINITY_BUNDLE_REF))
        policy_spec_ref = _coerce_policy_ref(state.inputs.get(INPUT_POLICY_SPEC_REF))
        model_spec_ref = _coerce_model_ref(state.inputs.get(INPUT_MODEL_SPEC_REF))
        if trinity_bundle_ref is None and policy_spec_ref is None:
            return _skip_legal_check(
                state=state,
                message=(
                    "Legal check skipped: missing policy source "
                    "(provide trinity_bundle_ref or policy_spec_ref)"
                ),
                reason="missing_policy_source",
                details={"required": [INPUT_TRINITY_BUNDLE_REF, INPUT_POLICY_SPEC_REF]},
            )

        norm_pack_ref = state.inputs.get(INPUT_NORM_PACK_REF)
        new_state = branch_state(state, write_paths=_SPEC.state_writes).state
        fact_log_root = _fact_log_root(ctx, state)

        if norm_pack_ref is None:
            norm_request = NormPackBuildRequest(
                jurisdiction=jurisdiction,
                as_of=as_of,
            )
            norm_result = assemble_norm_pack(
                cas=ctx.store,
                fact_log_root=fact_log_root,
                request=norm_request,
            )
            norm_pack_ref = ArtifactRef(
                artifact_id=ArtifactID.model_validate(norm_result.norm_pack_artifact_id),
                kind="lex.norm_pack",
                media_type="application/json",
            )
            new_state.inputs[INPUT_NORM_PACK_REF] = norm_pack_ref

        strict_legal = state.params.get("strict_legal", True)
        strict = bool(strict_legal)

        request = LegalEvaluationRequest(
            jurisdiction=jurisdiction,
            as_of=as_of,
            trinity_bundle_ref=trinity_bundle_ref,
            policy_spec_ref=policy_spec_ref,
            model_spec_ref=model_spec_ref,
            simulation_result_ref=simulation_result_ref,
            norm_pack_ref=norm_pack_ref,
            strict=strict,
        )

        try:
            report_ref, proposal_refs = evaluate_legality(
                cas=ctx.store,
                fact_log_root=fact_log_root,
                request=request,
            )
        except _LEGAL_EVALUATION_ERRORS as exc:
            return NodeOutcome(
                status="fail",
                state=state,
                error=NodeError(
                    code="lex.evaluate_failed",
                    message=f"Legal evaluation failed: {exc}",
                    details={
                        "error_type": exc.__class__.__name__,
                        "run_id": state.run_id,
                    },
                ),
            )

        new_state.reports_index[REPORT_LEGAL_REPORT_REF] = report_ref
        artifacts: list[ArtifactRef] = [report_ref]
        if proposal_refs:
            first = proposal_refs[0]
            new_state.reports_index[REPORT_CHANGE_PROPOSAL_REF] = first
            artifacts.extend(proposal_refs)

        events: list[NodeEvent] = []
        grade, degraded = _read_compliance_grade(ctx, state, report_ref)
        if degraded is not None:
            events.append(
                NodeEvent(
                    level="warn",
                    code="legal_check.report_degraded",
                    message="Legal check report grade degraded",
                    attrs={
                        "reason": str(degraded.get("reason", "legal_report_grade_load_failed")),
                        "error_type": str(degraded.get("error_type", "runtime_error")),
                    },
                )
            )
        if strict and grade is not None and grade != "pass":
            events.append(
                NodeEvent(
                    level="warn",
                    message=f"Legal compliance grade is {grade}",
                    attrs={"strict_legal": True},
                )
            )

        return NodeOutcome(
            status="ok",
            state=new_state,
            artifacts=artifacts,
            events=events,
        )


__all__ = ["LegalCheckNode"]
