"""Public planning assemble legal candidate pack module API."""

from __future__ import annotations

from dataclasses import dataclass

from polisyos.core.artifacts.manifest import input_ref_from_artifact_ref
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.core.contracts.scientist import PolicyRequestFrameRef
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_CROSS_GRAPH_EVIDENCE_PROFILE_REF,
    ARTIFACT_LEGAL_CANDIDATE_PACK_REF,
    ARTIFACT_POLICY_REQUEST_FRAME_REF,
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
from polisyos.scientist.validation.policy_verified import (
    load_policy_request_frame,
    persist_legal_candidate_pack,
)
from polisyos.scientist.validation.policy_verified.selection import select_policy_source_ref
from polisyos.scientist.validation.policy_verified.service import assemble_legal_candidate_pack

_METADATA = ComponentMetadata(
    component_id=ComponentId.parse("scientist.node_assemble_legal_candidate_pack@1.0.0"),
    kind=ComponentKind.SCIENTIST_NODE,
    abi_targets={"world_abi": "1.x"},
    display_name="Assemble Legal Candidate Pack",
    description="Use lex graph recall to assemble high-value legal candidates for source verification.",
    tags=["builtin", "planning", "policy_verified", "legal"],
    capabilities=Capability.SCIENTIST_NODE,
)

_SPEC = NodeSpec(
    metadata=_METADATA,
    state_reads=[
        "run_id",
        "execution_profile",
        "inputs",
        "params",
        "artifacts_index",
        "policy_request_ref",
    ],
    state_writes=[
        "legal_candidate_pack_ref",
        f"artifacts_index.{ARTIFACT_LEGAL_CANDIDATE_PACK_REF}",
    ],
    produces=[ARTIFACT_LEGAL_CANDIDATE_PACK_REF],
)


@dataclass(frozen=True)
class AssembleLegalCandidatePackNode:
    """Planning DAG node that turns a policy request into candidate legal queries and anchors.

    Reads the request frame and optional cross-graph evidence profile, then writes
    `legal_candidate_pack_ref` plus the persisted candidate-pack artifact consumed
    by source expansion and verification.
    """

    @property
    def spec(self) -> NodeSpec:
        return _SPEC

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        try:
            raw_ref = select_policy_source_ref(
                state.policy_request_ref,
                state.artifacts_index.get(ARTIFACT_POLICY_REQUEST_FRAME_REF),
            )
        except ValueError:
            return NodeOutcome(
                status="fail",
                state=_without_current_candidate(state),
                error=NodeError(
                    code="policy_source_selection_conflict",
                    message="Policy-source selectors disagree.",
                ),
            )
        if raw_ref is None:
            return NodeOutcome(
                status="skip",
                state=_without_current_candidate(state),
                events=[
                    NodeEvent(
                        level="warn",
                        message="Missing policy request frame; legal candidate pack skipped.",
                    )
                ],
            )
        frame = load_policy_request_frame(
            ctx.store, PolicyRequestFrameRef.model_validate(raw_ref.model_dump())
        )
        pack = assemble_legal_candidate_pack(ctx, state, frame)
        inputs = [input_ref_from_artifact_ref(raw_ref, role="policy_request_frame")]
        profile_ref = state.artifacts_index.get(ARTIFACT_CROSS_GRAPH_EVIDENCE_PROFILE_REF)
        if profile_ref is not None:
            inputs.append(
                input_ref_from_artifact_ref(profile_ref, role="cross_graph_evidence_profile")
            )
        pack_ref = persist_legal_candidate_pack(ctx.store, pack, inputs=inputs)
        new_state = branch_state(state, write_paths=_SPEC.state_writes).state
        new_state.legal_candidate_pack_ref = pack_ref
        new_state.artifacts_index[ARTIFACT_LEGAL_CANDIDATE_PACK_REF] = pack_ref
        return NodeOutcome(
            status="ok",
            state=new_state,
            artifacts=[pack_ref],
            events=[
                NodeEvent(
                    level="info",
                    message="Legal candidate pack assembled.",
                    attrs={
                        "fact_hits": len(pack.fact_hits),
                        "provision_hits": len(pack.provision_hits),
                    },
                )
            ],
        )


def _without_current_candidate(state: ExperimentState) -> ExperimentState:
    """Keep an unverified prior pack out of this direct output projection."""
    if (
        state.legal_candidate_pack_ref is None
        and ARTIFACT_LEGAL_CANDIDATE_PACK_REF not in state.artifacts_index
    ):
        return state
    projected = branch_state(state, write_paths=_SPEC.state_writes).state
    projected.legal_candidate_pack_ref = None
    projected.artifacts_index.pop(ARTIFACT_LEGAL_CANDIDATE_PACK_REF, None)
    return projected


__all__ = ["AssembleLegalCandidatePackNode"]
