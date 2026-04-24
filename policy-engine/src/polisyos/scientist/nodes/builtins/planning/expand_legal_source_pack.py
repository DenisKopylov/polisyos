"""Public planning expand legal source pack module API."""

from __future__ import annotations

from dataclasses import dataclass

from polisyos.core.artifacts.manifest import InputRef
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.core.contracts.scientist import LegalCandidatePackRef
from polisyos.scientist.engine.context import ExecutionContext
from polisyos.scientist.engine.protocol import NodeEvent, NodeOutcome, NodeSpec
from polisyos.scientist.engine.state import ExperimentState
from polisyos.scientist.engine.state_branching import branch_state
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_LEGAL_CANDIDATE_PACK_REF,
    ARTIFACT_LEGAL_SOURCE_PACK_REF,
)
from polisyos.scientist.policy_verified import (
    load_legal_candidate_pack,
    persist_legal_source_pack,
)
from polisyos.scientist.policy_verified.service import expand_legal_source_pack

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
        "legal_candidate_pack_ref",
        f"artifacts_index.{ARTIFACT_LEGAL_CANDIDATE_PACK_REF}",
        "params.max_source_docs",
        "params.max_reference_hops",
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
        if (
            state.legal_source_pack_ref is not None
            and ARTIFACT_LEGAL_SOURCE_PACK_REF in state.artifacts_index
        ):
            return NodeOutcome(status="ok", state=state)

        raw_ref = state.legal_candidate_pack_ref or state.artifacts_index.get(
            ARTIFACT_LEGAL_CANDIDATE_PACK_REF
        )
        if raw_ref is None:
            return NodeOutcome(
                status="skip",
                state=state,
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
            inputs=[InputRef(artifact_id=raw_ref.artifact_id, role="legal_candidate_pack")],
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


__all__ = ["ExpandLegalSourcePackNode"]
