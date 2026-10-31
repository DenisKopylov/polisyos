"""Public planning expand legal source pack module API."""

from __future__ import annotations

from dataclasses import dataclass

from polisyos.core.artifacts.manifest import input_ref_from_artifact_ref
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.core.contracts.scientist import LegalCandidatePackRef
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_LEGAL_CANDIDATE_PACK_REF,
    ARTIFACT_LEGAL_SOURCE_PACK_REF,
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
    load_legal_candidate_pack,
    persist_legal_source_pack,
)
from polisyos.scientist.validation.policy_verified.selection import select_policy_source_ref
from polisyos.scientist.validation.policy_verified.service import expand_legal_source_pack

_METADATA = ComponentMetadata(
    component_id=ComponentId.parse("scientist.node_expand_legal_source_pack@1.0.0"),
    kind=ComponentKind.SCIENTIST_NODE,
    abi_targets={"world_abi": "1.x"},
    display_name="Expand Legal Source Pack",
    description="Resolve candidate hits into source bundles with references, version chain, and appendix context.",
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
        "legal_candidate_pack_ref",
    ],
    state_writes=[
        "legal_source_pack_ref",
        f"artifacts_index.{ARTIFACT_LEGAL_SOURCE_PACK_REF}",
    ],
    produces=[ARTIFACT_LEGAL_SOURCE_PACK_REF],
)


@dataclass(frozen=True)
class ExpandLegalSourcePackNode:
    """Planning DAG node that expands legal candidates into source bundles ready for verification.

    Requires a candidate pack, respects source-depth params, and writes the
    `legal_source_pack_ref` artifact that later verification and gap-review nodes reuse.
    """

    @property
    def spec(self) -> NodeSpec:
        return _SPEC

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        try:
            raw_ref = select_policy_source_ref(
                state.legal_candidate_pack_ref,
                state.artifacts_index.get(ARTIFACT_LEGAL_CANDIDATE_PACK_REF),
            )
        except ValueError:
            return NodeOutcome(
                status="fail",
                state=_without_current_source(state),
                error=NodeError(
                    code="policy_source_selection_conflict",
                    message="Policy-source selectors disagree.",
                ),
            )
        if raw_ref is None:
            return NodeOutcome(
                status="skip",
                state=_without_current_source(state),
                events=[
                    NodeEvent(
                        level="warn",
                        message="Missing legal candidate pack; source expansion skipped.",
                    )
                ],
            )
        pack = load_legal_candidate_pack(
            ctx.store, LegalCandidatePackRef.model_validate(raw_ref.model_dump())
        )
        source_pack = expand_legal_source_pack(ctx, state, pack)
        pack_ref = persist_legal_source_pack(
            ctx.store,
            source_pack,
            inputs=[input_ref_from_artifact_ref(raw_ref, role="legal_candidate_pack")],
        )
        new_state = branch_state(state, write_paths=_SPEC.state_writes).state
        new_state.legal_source_pack_ref = pack_ref
        new_state.artifacts_index[ARTIFACT_LEGAL_SOURCE_PACK_REF] = pack_ref
        return NodeOutcome(
            status="ok",
            state=new_state,
            artifacts=[pack_ref],
            events=[
                NodeEvent(
                    level="info",
                    message="Legal source pack expanded.",
                    attrs={"source_bundles": len(source_pack.source_bundles)},
                )
            ],
        )


def _without_current_source(state: ExperimentState) -> ExperimentState:
    """Keep an unverified prior pack out of this direct output projection."""
    if (
        state.legal_source_pack_ref is None
        and ARTIFACT_LEGAL_SOURCE_PACK_REF not in state.artifacts_index
    ):
        return state
    projected = branch_state(state, write_paths=_SPEC.state_writes).state
    projected.legal_source_pack_ref = None
    projected.artifacts_index.pop(ARTIFACT_LEGAL_SOURCE_PACK_REF, None)
    return projected


__all__ = ["ExpandLegalSourcePackNode"]
