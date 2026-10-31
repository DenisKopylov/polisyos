"""Bind an explicit policy candidate to an Engine-selected input attempt."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass

from pydantic import BaseModel

from polisyos.core.artifacts import (
    ArtifactRef,
    ArtifactStore,
    ensure_ir_artifact_store,
    input_ref_from_artifact_ref,
    read_core_json_artifact_bytes,
)
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.ir.trinity import load_trinity_bundle_artifact
from polisyos.scientist.nodes.builtins.state_keys import INPUT_TRINITY_BUNDLE_REF
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
from polisyos.scientist.policy_design.schema import (
    PolicyCandidateSchema,
    load_policy_candidate_schema,
    persist_selected_policy_candidate_payload,
    policy_candidate_contents_match,
    policy_candidate_trinity_contents_match,
    reissue_policy_candidate_schema,
    validate_policy_candidate_payload,
)

_COMPONENT_ID = "scientist.node_select_policy_candidate@1.0.0"
_CONTRACT_ID = "policy_candidate_selection.v1"
_CANDIDATE_REF = "verified_policy_candidate_ref"
_PARAM_KEYS = ("policy_candidate_schema", "policy_candidate_ref")
_INPUT_PATHS = (
    "schema_version",
    "run_id",
    "execution_profile",
    *(f"params.{key}" for key in _PARAM_KEYS),
    f"inputs.{INPUT_TRINITY_BUNDLE_REF}",
)
_METADATA = ComponentMetadata(
    component_id=ComponentId.parse(_COMPONENT_ID),
    kind=ComponentKind.SCIENTIST_NODE,
    abi_targets={"world_abi": "1.x"},
    display_name="Select Policy Candidate",
    description="Bind an explicit candidate to its exact selected Engine input attempt.",
    tags=["builtin", "decide", "policy_verified", "candidate"],
    capabilities=Capability.SCIENTIST_NODE,
)
_SPEC = InputAwareNodeSpec(
    metadata=_METADATA,
    state_reads=list(_INPUT_PATHS),
    state_writes=[f"artifacts_index.{_CANDIDATE_REF}"],
    produces=[_CANDIDATE_REF],
    input_contract=NodeInputContract(
        contract_id=_CONTRACT_ID,
        component_id=_COMPONENT_ID,
        state_paths=_INPUT_PATHS,
        artifact_ref_paths=("params.policy_candidate_ref", f"inputs.{INPUT_TRINITY_BUNDLE_REF}"),
    ),
)


def _selected_candidate(
    store: ArtifactStore,
    inline: object,
    raw_ref: object,
    trinity_ref: ArtifactRef | None,
) -> tuple[PolicyCandidateSchema, list[tuple[str, ArtifactRef]]]:
    """Admit explicit candidate inputs; selected source profiles remain distinct."""
    inline_payload = None if inline is None else _candidate_payload(inline)
    candidate = (
        None if inline_payload is None else validate_policy_candidate_payload(inline_payload)
    )
    selected_payload = inline_payload
    inputs: list[tuple[str, ArtifactRef]] = []
    if raw_ref is not None:
        ref = ArtifactRef.model_validate(raw_ref)
        if ref.manifest_profile_sha256 is None or not store.verify(ref).ok:
            raise ValueError("policy_candidate_source_not_established")
        sourced = load_policy_candidate_schema(store, ref)
        source_payload = json.loads(read_core_json_artifact_bytes(store, ref))
        if not isinstance(source_payload, dict):
            raise ValueError("policy_candidate_source_not_established")
        if inline_payload is not None and not policy_candidate_contents_match(
            inline_payload, source_payload
        ):
            raise ValueError("policy_candidate_selection_conflict")
        candidate = sourced
        selected_payload = source_payload
        inputs.append(("candidate_source", ref))
    if candidate is None:
        raise ValueError("policy_candidate_not_established")
    if candidate.schema_version != PolicyCandidateSchema.ARTIFACT_SCHEMA_VERSION:
        raise ValueError("policy_candidate_version_not_established")
    if trinity_ref is not None:
        if trinity_ref.manifest_profile_sha256 is None or not store.verify(trinity_ref).ok:
            raise ValueError("policy_candidate_trinity_not_established")
        load_trinity_bundle_artifact(ensure_ir_artifact_store(store), trinity_ref)
        trinity_payload = json.loads(read_core_json_artifact_bytes(store, trinity_ref))
        if (
            selected_payload is None
            or not isinstance(trinity_payload, dict)
            or not policy_candidate_trinity_contents_match(selected_payload, trinity_payload)
        ):
            raise ValueError("policy_candidate_trinity_mismatch")
        inputs.append(("candidate_trinity", trinity_ref))
    return candidate, inputs


def _candidate_payload(value: object) -> dict[str, object]:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, Mapping):
        return dict(value)
    raise ValueError("policy_candidate_not_established")


@dataclass(frozen=True)
class SelectPolicyCandidateNode:
    """Persist an explicitly selected candidate without granting decision authority."""

    @property
    def spec(self) -> InputAwareNodeSpec:
        """Return the versioned selected-input contract."""
        return _SPEC

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        """Persist a candidate occurrence bound to the actual Engine input basis."""
        from polisyos.scientist.orchestration.engine.input_ports import read_input_port_basis

        payload = state.model_dump(mode="python")
        restricted = ExperimentState(
            schema_version=state.schema_version,
            run_id=state.run_id,
            execution_profile=state.execution_profile,
            params={key: payload["params"][key] for key in _PARAM_KEYS if key in state.params},
            inputs=(
                {INPUT_TRINITY_BUNDLE_REF: state.inputs[INPUT_TRINITY_BUNDLE_REF]}
                if INPUT_TRINITY_BUNDLE_REF in state.inputs
                else {}
            ),
        )
        if payload != restricted.model_dump(mode="python"):
            return _fail(state, "policy_candidate_port_not_projected")
        try:
            selection = read_input_port_basis(ctx, state)
            if (
                selection.run_id != state.run_id
                or selection.component_id != _COMPONENT_ID
                or selection.contract_id != _CONTRACT_ID
            ):
                return _fail(state, "policy_candidate_attempt_not_established")
            _candidate, source_refs = _selected_candidate(
                ctx.store,
                state.params.get("policy_candidate_schema"),
                state.params.get("policy_candidate_ref"),
                state.inputs.get(INPUT_TRINITY_BUNDLE_REF),
            )
            inputs = [
                input_ref_from_artifact_ref(selection.input_state_ref, role="selected_input"),
                input_ref_from_artifact_ref(selection.basis_ref, role="selected_attempt"),
                *(input_ref_from_artifact_ref(ref, role=role) for role, ref in source_refs),
            ]
            raw_candidate_ref = state.params.get("policy_candidate_ref")
            if raw_candidate_ref is not None:
                candidate_ref = reissue_policy_candidate_schema(
                    ctx.store, ArtifactRef.model_validate(raw_candidate_ref), inputs=inputs
                )
            else:
                candidate_ref = persist_selected_policy_candidate_payload(
                    ctx.store,
                    _candidate_payload(state.params.get("policy_candidate_schema")),
                    inputs=inputs,
                )
        except (OSError, RuntimeError, TypeError, ValueError):
            return _fail(state, "policy_candidate_not_established")
        result = branch_state(state, write_paths=_SPEC.state_writes).state
        result.artifacts_index[_CANDIDATE_REF] = candidate_ref
        return NodeOutcome(
            status="ok",
            state=result,
            artifacts=[candidate_ref],
            events=[NodeEvent(level="info", message="Explicit policy candidate selected.")],
        )


def _fail(state: ExperimentState, code: str) -> NodeOutcome:
    return NodeOutcome(
        status="fail",
        state=state,
        error=NodeError(code=code, message="Candidate is not established."),
    )


__all__ = ["SelectPolicyCandidateNode"]
