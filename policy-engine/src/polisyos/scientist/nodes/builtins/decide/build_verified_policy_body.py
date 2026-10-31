"""Build a restricted candidate body for staged verified-policy composition."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from polisyos.core.artifacts import (
    ensure_ir_artifact_store,
    input_ref_from_artifact_ref,
    validate_core_model_json_artifact,
)
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.core.contracts.foundry import Metrics
from polisyos.core.contracts.scientist import (
    PolicyOptionSetRef,
    PolicyRequestFrameRef,
    SourceVerificationReportRef,
)
from polisyos.ir.analytics.causal import load_causal_effect_report
from polisyos.ir.registry.refs import CausalEffectReportRef
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_CAUSAL_REPORT_REF,
    ARTIFACT_METRICS_REF,
    ARTIFACT_POLICY_OPTION_SET_REF,
    ARTIFACT_POLICY_REQUEST_FRAME_REF,
    ARTIFACT_SOURCE_VERIFICATION_REPORT_REF,
    ARTIFACT_VERIFIED_POLICY_BODY_REF,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.protocol import (
    InputAwareNodeSpec,
    NodeError,
    NodeEvent,
    NodeInputContract,
    NodeOutcome,
)
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.state_branching import branch_state
from polisyos.scientist.validation.policy_verified import (
    load_policy_option_set,
    load_policy_request_frame,
    load_source_verification_report,
    persist_verified_policy_body,
)
from polisyos.scientist.validation.policy_verified.selection import (
    require_selected_policy_source_bindings,
    select_policy_source_ref,
)
from polisyos.scientist.validation.policy_verified.service import build_verified_policy_report

if TYPE_CHECKING:
    from polisyos.scientist.orchestration.engine.input_ports import NodeInputSelection

_BODY_COMPONENT_ID = "scientist.node_build_verified_policy_body@1.0.0"
_BODY_CONTRACT_ID = "policy_verified_body.v1"
_BODY_INDEX_KEYS = (
    ARTIFACT_POLICY_REQUEST_FRAME_REF,
    ARTIFACT_POLICY_OPTION_SET_REF,
    ARTIFACT_SOURCE_VERIFICATION_REPORT_REF,
    ARTIFACT_METRICS_REF,
    ARTIFACT_CAUSAL_REPORT_REF,
)
_BODY_INPUT_PATHS = (
    "schema_version",
    "run_id",
    "execution_profile",
    "policy_request_ref",
    "policy_option_set_ref",
    "source_verification_report_ref",
    *(f"artifacts_index.{key}" for key in _BODY_INDEX_KEYS),
)
_METADATA = ComponentMetadata(
    component_id=ComponentId.parse(_BODY_COMPONENT_ID),
    kind=ComponentKind.SCIENTIST_NODE,
    abi_targets={"world_abi": "1.x"},
    display_name="Build Verified Policy Candidate Body",
    description="Build a source-bound candidate body before governance assessment.",
    tags=["builtin", "decide", "policy_verified", "candidate"],
    capabilities=Capability.SCIENTIST_NODE,
)
_SPEC = InputAwareNodeSpec(
    metadata=_METADATA,
    state_reads=list(_BODY_INPUT_PATHS),
    state_writes=[f"artifacts_index.{ARTIFACT_VERIFIED_POLICY_BODY_REF}"],
    produces=[ARTIFACT_VERIFIED_POLICY_BODY_REF],
    input_contract=NodeInputContract(
        contract_id=_BODY_CONTRACT_ID,
        component_id=_BODY_COMPONENT_ID,
        state_paths=_BODY_INPUT_PATHS,
        artifact_ref_paths=(
            "policy_request_ref",
            "policy_option_set_ref",
            "source_verification_report_ref",
            *(f"artifacts_index.{key}" for key in _BODY_INDEX_KEYS),
        ),
    ),
)


@dataclass(frozen=True)
class BuildVerifiedPolicyBodyNode:
    """Produce a candidate body from the restricted, selected source port."""

    @property
    def spec(self) -> InputAwareNodeSpec:
        """Return the versioned physical input and output contract."""
        return _SPEC

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        """Persist a body bound to the actual selected input and attempt."""
        from polisyos.scientist.orchestration.engine.input_ports import read_input_port_basis

        try:
            selection = read_input_port_basis(ctx, state)
            if (
                selection.run_id != state.run_id
                or selection.component_id != _BODY_COMPONENT_ID
                or selection.contract_id != _BODY_CONTRACT_ID
            ):
                raise ValueError("policy_body_attempt_not_established")
        except (AttributeError, OSError, RuntimeError, TypeError, ValueError):
            return _fail(
                state,
                "policy_body_attempt_not_established",
                "Candidate body attempt is not established.",
            )
        return _build_candidate_body(ctx, state, selection=selection)


def _build_candidate_body(
    ctx: ExecutionContext, state: ExperimentState, *, selection: NodeInputSelection | None = None
) -> NodeOutcome:
    """Build candidate content; a direct helper call has no Engine provenance."""
    restricted = ExperimentState(
        schema_version=state.schema_version,
        run_id=state.run_id,
        execution_profile=state.execution_profile,
        policy_request_ref=state.policy_request_ref,
        policy_option_set_ref=state.policy_option_set_ref,
        source_verification_report_ref=state.source_verification_report_ref,
        artifacts_index={
            key: state.artifacts_index[key]
            for key in _BODY_INDEX_KEYS
            if key in state.artifacts_index
        },
    )
    if state.model_dump(mode="json") != restricted.model_dump(mode="json"):
        return _fail(
            state, "policy_body_port_not_projected", "Candidate body input is not restricted."
        )
    try:
        request_ref = select_policy_source_ref(
            state.policy_request_ref,
            state.artifacts_index.get(ARTIFACT_POLICY_REQUEST_FRAME_REF),
        )
        option_ref = select_policy_source_ref(
            state.policy_option_set_ref,
            state.artifacts_index.get(ARTIFACT_POLICY_OPTION_SET_REF),
        )
        source_ref = select_policy_source_ref(
            state.source_verification_report_ref,
            state.artifacts_index.get(ARTIFACT_SOURCE_VERIFICATION_REPORT_REF),
        )
    except ValueError:
        return _fail(state, "policy_source_selection_conflict", "Policy-source selectors disagree.")
    if request_ref is None or option_ref is None or source_ref is None:
        return NodeOutcome(status="skip", state=state)

    optional_refs = [
        (key, state.artifacts_index[key])
        for key in (ARTIFACT_METRICS_REF, ARTIFACT_CAUSAL_REPORT_REF)
        if key in state.artifacts_index
    ]
    all_refs = [request_ref, option_ref, source_ref, *(ref for _, ref in optional_refs)]
    try:
        if any(
            ref.manifest_profile_sha256 is None or not ctx.store.verify(ref).ok for ref in all_refs
        ):
            return _fail(
                state,
                "policy_body_source_not_established",
                "A selected source profile is unavailable.",
            )
        frame = load_policy_request_frame(
            ctx.store, PolicyRequestFrameRef.model_validate(request_ref.model_dump(mode="json"))
        )
        options = load_policy_option_set(
            ctx.store, PolicyOptionSetRef.model_validate(option_ref.model_dump(mode="json"))
        )
        verification = load_source_verification_report(
            ctx.store,
            SourceVerificationReportRef.model_validate(source_ref.model_dump(mode="json")),
        )
        for role, ref in optional_refs:
            if role == ARTIFACT_METRICS_REF:
                validate_core_model_json_artifact(Metrics, ctx.store, ref)
            else:
                load_causal_effect_report(
                    ensure_ir_artifact_store(ctx.store),
                    CausalEffectReportRef.model_validate(ref.model_dump(mode="json")),
                )
    except (OSError, RuntimeError, TypeError, ValueError):
        return _fail(
            state, "policy_body_source_invalid", "A selected source failed owner admission."
        )
    if options.request_id != frame.request_id or verification.request_id != frame.request_id:
        return _fail(
            state,
            "policy_request_source_mismatch",
            "Policy sources belong to different requests.",
        )

    try:
        require_selected_policy_source_bindings(
            ctx.store,
            request_ref=request_ref,
            option_ref=option_ref,
            source_report_ref=source_ref,
        )
    except (AttributeError, OSError, RuntimeError, TypeError, ValueError):
        return _fail(
            state,
            "policy_source_binding_not_established",
            "Policy sources do not bind the selected request and verification report.",
        )

    body = build_verified_policy_report(restricted, frame, verification, options)
    inputs = [
        input_ref_from_artifact_ref(request_ref, role="policy_request_frame"),
        input_ref_from_artifact_ref(option_ref, role="policy_option_set"),
        input_ref_from_artifact_ref(source_ref, role="source_verification_report"),
        *(input_ref_from_artifact_ref(ref, role=key) for key, ref in optional_refs),
    ]
    if selection is not None:
        inputs.extend(
            [
                input_ref_from_artifact_ref(selection.input_state_ref, role="selected_input"),
                input_ref_from_artifact_ref(selection.basis_ref, role="selected_attempt"),
            ]
        )
    body_ref = persist_verified_policy_body(ctx.store, body, inputs=inputs)
    result = branch_state(state, write_paths=_SPEC.state_writes).state
    result.artifacts_index[ARTIFACT_VERIFIED_POLICY_BODY_REF] = body_ref
    return NodeOutcome(
        status="ok",
        state=result,
        artifacts=[body_ref],
        events=[NodeEvent(level="info", message="Verified-policy candidate body created.")],
    )


def _fail(state: ExperimentState, code: str, message: str) -> NodeOutcome:
    return NodeOutcome(status="fail", state=state, error=NodeError(code=code, message=message))


__all__ = ["BuildVerifiedPolicyBodyNode"]
