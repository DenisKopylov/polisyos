"""Named grader metadata for Scientist benchmark authority."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "EvalFamily",
    "GraderDescriptor",
    "GRADER_REGISTRY",
    "grader_for_family",
    "list_graders",
]


class EvalFamily(StrEnum):
    """Required eval families for Phase 1.5 benchmark authority."""

    FACTUALITY = "factuality"
    BROWSING_DEEP_RESEARCH = "browsing_deep_research"
    CITATION_FAITHFULNESS = "citation_faithfulness"
    CAUSAL_READINESS = "causal_readiness"
    POLICY_DESIGN = "policy_design"
    GOVERNANCE = "governance"
    TOOL_USE = "tool_use"
    HUMAN_REVIEW = "human_review"


class GraderDescriptor(BaseModel):
    """Metadata for an eval grader; no live grading is implemented in Phase 1.5."""

    model_config = ConfigDict(extra="forbid")

    grader_id: str = Field(min_length=1)
    family: EvalFamily
    purpose: str = Field(min_length=1)
    input_contract: str = Field(min_length=1)
    output_contract: str = Field(min_length=1)
    requires_hidden_pack: bool = False


GRADER_REGISTRY: tuple[GraderDescriptor, ...] = (
    GraderDescriptor(
        grader_id="factuality.source_grounded_v1",
        family=EvalFamily.FACTUALITY,
        purpose="Domain-local short factuality checks grounded in cited sources.",
        input_contract="claim text plus source snippets",
        output_contract="pass/fail with support notes",
    ),
    GraderDescriptor(
        grader_id="browsing.deep_research_multihop_v1",
        family=EvalFamily.BROWSING_DEEP_RESEARCH,
        purpose="Multi-hop frozen-web research tasks inspired by deep research benchmarks.",
        input_contract="frozen web pack plus research question",
        output_contract="answer quality, source coverage and path completeness",
        requires_hidden_pack=True,
    ),
    GraderDescriptor(
        grader_id="citation.faithfulness_v1",
        family=EvalFamily.CITATION_FAITHFULNESS,
        purpose="Claim-to-snippet and quote accuracy.",
        input_contract="claim ids, snippets and source spans",
        output_contract="support, contradiction and span-fidelity metrics",
        requires_hidden_pack=True,
    ),
    GraderDescriptor(
        grader_id="causal.readiness_v1",
        family=EvalFamily.CAUSAL_READINESS,
        purpose="Supported causal query classes versus explicit blockers.",
        input_contract="causal claim family and validity bundle",
        output_contract="readiness transition recommendation",
    ),
    GraderDescriptor(
        grader_id="policy.design_v1",
        family=EvalFamily.POLICY_DESIGN,
        purpose="Pareto, constraints, welfare, equity and legal feasibility checks.",
        input_contract="policy case pack and candidate output bundle",
        output_contract="policy-domain scorecard",
        requires_hidden_pack=True,
    ),
    GraderDescriptor(
        grader_id="governance.escalation_v1",
        family=EvalFamily.GOVERNANCE,
        purpose="False-pass, false-block and escalation quality.",
        input_contract="governance report and adjudicated expected outcome",
        output_contract="governance confusion metrics",
    ),
    GraderDescriptor(
        grader_id="tool_use.contract_v1",
        family=EvalFamily.TOOL_USE,
        purpose="Tool selection, argument precision and error recovery.",
        input_contract="tool trace plus expected tool outcomes",
        output_contract="tool-use precision and recovery metrics",
    ),
    GraderDescriptor(
        grader_id="human_review.burden_v1",
        family=EvalFamily.HUMAN_REVIEW,
        purpose="Reviewer burden, override correctness and explanation quality.",
        input_contract="review packet and reviewer decision fixture",
        output_contract="review quality and burden metrics",
    ),
)


def list_graders() -> list[GraderDescriptor]:
    """Return grader metadata for all required eval families."""

    return list(GRADER_REGISTRY)


def grader_for_family(family: EvalFamily | str) -> GraderDescriptor:
    """Return the first registered grader for an eval family."""

    resolved = EvalFamily(family)
    for grader in GRADER_REGISTRY:
        if grader.family == resolved:
            return grader
    raise KeyError(resolved.value)
