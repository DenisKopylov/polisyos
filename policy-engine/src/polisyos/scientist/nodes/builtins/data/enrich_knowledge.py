from __future__ import annotations

from dataclasses import dataclass

from polisyos.core.canon import from_canonical_bytes
from polisyos.core.components import Capability, ComponentId, ComponentMetadata
from polisyos.core.contracts.scholar import ResearchIntent, ResearchIntentRef
from polisyos.scientist.engine.context import ExecutionContext
from polisyos.scientist.engine.protocol import NodeError, NodeEvent, NodeOutcome, NodeSpec
from polisyos.scientist.engine.state import ExperimentState
from polisyos.scientist.nodes.builtins import errors as node_errors
from polisyos.scientist.nodes.builtins.state_keys import (
    INPUT_KNOWLEDGE_BUNDLE_REF,
    INPUT_RESEARCH_INTENT_REF,
)

_METADATA = ComponentMetadata(
    component_id=ComponentId.parse("scientist.node_enrich_knowledge@1.0.0"),
    display_name="Enrich Knowledge",
    description="Build knowledge_bundle_ref from research_intent_ref via Scholar.",
    tags=["builtin", "scholar"],
    capabilities=Capability.SCIENTIST_NODE,
)

_SPEC = NodeSpec(
    metadata=_METADATA,
    state_reads=[
        f"inputs.{INPUT_KNOWLEDGE_BUNDLE_REF}",
        f"inputs.{INPUT_RESEARCH_INTENT_REF}",
    ],
    state_writes=[f"inputs.{INPUT_KNOWLEDGE_BUNDLE_REF}"],
    produces=[INPUT_KNOWLEDGE_BUNDLE_REF],
)


@dataclass(frozen=True)
class EnrichKnowledgeNode:
    @property
    def spec(self) -> NodeSpec:
        return _SPEC

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        if INPUT_KNOWLEDGE_BUNDLE_REF in state.inputs:
            return NodeOutcome(status="ok", state=state)

        if ctx.scholar is None:
            return NodeOutcome(
                status="fail",
                state=state,
                error=NodeError(
                    code=node_errors.ERROR_FOUNDATION_MISSING,
                    message="Scholar port is not configured",
                ),
            )

        intent_ref_raw = state.inputs.get(INPUT_RESEARCH_INTENT_REF)
        if intent_ref_raw is None:
            return NodeOutcome(
                status="fail",
                state=state,
                error=NodeError(
                    code=node_errors.ERROR_MISSING_INPUT,
                    message="Missing research_intent_ref",
                    details={"required": [INPUT_RESEARCH_INTENT_REF]},
                ),
            )

        try:
            intent_ref = ResearchIntentRef.model_validate(intent_ref_raw.model_dump())
            payload = from_canonical_bytes(ctx.store.get_bytes(intent_ref.artifact_id))
            if not isinstance(payload, dict):
                raise ValueError("research_intent_ref must point to JSON object payload")
            intent = ResearchIntent.model_validate(payload)
            bundle_ref = ctx.scholar.enrich(ctx.store, intent)
        except Exception as exc:
            return NodeOutcome(
                status="fail",
                state=state,
                error=NodeError(
                    code="scholar.enrich_failed",
                    message=f"Scholar enrich failed: {exc}",
                ),
            )

        new_state = state.model_copy(deep=True)
        new_state.inputs[INPUT_KNOWLEDGE_BUNDLE_REF] = bundle_ref
        return NodeOutcome(
            status="ok",
            state=new_state,
            artifacts=[bundle_ref],
            events=[NodeEvent(level="info", message="Knowledge bundle enriched")],
        )


__all__ = ["EnrichKnowledgeNode"]
