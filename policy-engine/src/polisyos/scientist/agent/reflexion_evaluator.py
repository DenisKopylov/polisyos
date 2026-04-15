"""Rubric-based Reflexion evaluator and trajectory replay helpers."""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any
import urllib.parse

from pydantic import BaseModel, ConfigDict, Field

from polisyos.scientist.agent.tools.registry import ToolCallResult

__all__ = [
    "ReflexionEvaluatorConfig",
    "ReflexionReplayCase",
    "ReflexionReplayEvaluation",
    "ReflexionScorecard",
    "ReflexionTrajectoryStep",
    "RubricReflexionEvaluator",
    "build_reflexion_summary_text",
    "evaluate_reflexion_replay_cases",
    "extract_tool_error_patterns",
]


class ReflexionEvaluatorConfig(BaseModel):
    """Rubric thresholds and scoring weights for Reflexion evaluation."""

    model_config = ConfigDict(extra="forbid")

    min_quality_score: float = Field(default=0.55, ge=0.0, le=1.0)
    min_grounding_score: float = Field(default=0.50, ge=0.0, le=1.0)
    min_schema_score: float = Field(default=0.80, ge=0.0, le=1.0)
    min_compliance_score: float = Field(default=0.95, ge=0.0, le=1.0)
    min_overall_score: float = Field(default=0.70, ge=0.0, le=1.0)
    min_improvement_delta: float = Field(default=0.01, ge=0.0, le=1.0)
    required_citation_count: int = Field(default=0, ge=0, le=128)
    rubric_weights: dict[str, float] = Field(
        default_factory=lambda: {
            "quality": 0.35,
            "grounding": 0.30,
            "schema": 0.20,
            "compliance": 0.15,
        }
    )
    compliance_blocklist: list[str] = Field(
        default_factory=lambda: [
            "ignore previous instructions",
            "system prompt",
            "developer message",
            "secret key",
            "api key",
            "password",
        ]
    )


class ReflexionScorecard(BaseModel):
    """One evaluator output over a candidate response or trajectory step."""

    model_config = ConfigDict(extra="forbid")

    quality_score: float = Field(default=0.0, ge=0.0, le=1.0)
    grounding_score: float = Field(default=0.0, ge=0.0, le=1.0)
    schema_score: float = Field(default=0.0, ge=0.0, le=1.0)
    compliance_score: float = Field(default=0.0, ge=0.0, le=1.0)
    overall_score: float = Field(default=0.0, ge=0.0, le=1.0)
    evidence_count: int = Field(default=0, ge=0)
    passed: bool = False
    blocking_issues: list[str] = Field(default_factory=list)
    retry_advice: str = ""
    tool_error_patterns: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ReflexionTrajectoryStep(BaseModel):
    """One attempt in a Reflexion trajectory replay suite."""

    model_config = ConfigDict(extra="forbid")

    iteration: int = Field(ge=1)
    output_text: str = ""
    output_data: dict[str, Any] = Field(default_factory=dict)
    citations: list[dict[str, Any]] = Field(default_factory=list)
    tool_results: list[dict[str, Any]] = Field(default_factory=list)
    scorecard: ReflexionScorecard | None = None


class ReflexionReplayCase(BaseModel):
    """Held-out replay trajectory for regression evaluation."""

    model_config = ConfigDict(extra="forbid")

    case_id: str
    objective: str
    steps: list[ReflexionTrajectoryStep] = Field(default_factory=list)
    expected_success: bool = True


class ReflexionReplayEvaluation(BaseModel):
    """Aggregate metrics over a set of replayed Reflexion trajectories."""

    model_config = ConfigDict(extra="forbid")

    sample_count: int = 0
    avg_first_score: float = 0.0
    avg_final_score: float = 0.0
    avg_best_score: float = 0.0
    improvement_rate: float = 0.0
    repeated_error_rate: float = 0.0
    pass_rate: float = 0.0


class RubricReflexionEvaluator:
    """Deterministic rubric evaluator for quality, grounding, schema, and compliance."""

    def __init__(self, config: ReflexionEvaluatorConfig | None = None) -> None:
        self.config = config or ReflexionEvaluatorConfig()

    def evaluate_candidate(
        self,
        *,
        objective: str,
        output_text: str,
        output_data: Mapping[str, Any] | None = None,
        citations: Sequence[Mapping[str, Any]] | None = None,
        tool_results: Sequence[ToolCallResult | Mapping[str, Any]] | None = None,
        expected_output_schema: Mapping[str, Any] | None = None,
    ) -> ReflexionScorecard:
        """Evaluate one candidate response against the Reflexion rubric."""
        normalized_output_data = dict(output_data or {})
        normalized_citations = [dict(item) for item in (citations or [])]
        normalized_tools = [
            _coerce_tool_result_payload(item)
            for item in (tool_results or [])
        ]
        quality_score = _quality_score(objective=objective, output_text=output_text)
        grounding_score = _grounding_score(
            output_text=output_text,
            output_data=normalized_output_data,
            citations=normalized_citations,
            required_citation_count=self.config.required_citation_count,
        )
        schema_score = _schema_score(
            output_data=normalized_output_data,
            tool_results=normalized_tools,
            expected_output_schema=expected_output_schema or {},
        )
        compliance_score = _compliance_score(
            output_text=output_text,
            output_data=normalized_output_data,
            blocklist=self.config.compliance_blocklist,
        )
        overall_score = _weighted_score(
            {
                "quality": quality_score,
                "grounding": grounding_score,
                "schema": schema_score,
                "compliance": compliance_score,
            },
            self.config.rubric_weights,
        )
        evidence_count = _count_evidence_items(
            output_text=output_text,
            output_data=normalized_output_data,
            citations=normalized_citations,
        )
        tool_error_patterns = extract_tool_error_patterns(normalized_tools)
        blocking_issues = _blocking_issues(
            quality_score=quality_score,
            grounding_score=grounding_score,
            schema_score=schema_score,
            compliance_score=compliance_score,
            overall_score=overall_score,
            tool_error_patterns=tool_error_patterns,
            config=self.config,
        )
        return ReflexionScorecard(
            quality_score=quality_score,
            grounding_score=grounding_score,
            schema_score=schema_score,
            compliance_score=compliance_score,
            overall_score=overall_score,
            evidence_count=evidence_count,
            passed=not blocking_issues,
            blocking_issues=blocking_issues,
            retry_advice=_retry_advice(blocking_issues, normalized_tools),
            tool_error_patterns=tool_error_patterns,
            metadata={
                "required_citation_count": self.config.required_citation_count,
                "tool_result_count": len(normalized_tools),
            },
        )

    def should_stop(
        self,
        current: ReflexionScorecard,
        previous: ReflexionScorecard | None = None,
    ) -> tuple[bool, str]:
        """Score/evidence-based stop policy."""
        if current.passed:
            return True, "rubric_passed"
        if previous is not None:
            score_delta = current.overall_score - previous.overall_score
            evidence_delta = current.evidence_count - previous.evidence_count
            if (
                score_delta < self.config.min_improvement_delta
                and evidence_delta <= 0
            ):
                return True, "score_plateau"
        return False, ""

    def evaluate_replay_cases(
        self,
        cases: Sequence[ReflexionReplayCase | Mapping[str, Any]],
    ) -> ReflexionReplayEvaluation:
        """Evaluate held-out Reflexion replay trajectories."""
        return evaluate_reflexion_replay_cases(cases, evaluator=self)


def extract_tool_error_patterns(
    tool_results: Sequence[ToolCallResult | Mapping[str, Any]],
) -> list[str]:
    """Normalize tool failures into compact `tool_name:error_type` signatures."""
    patterns: list[str] = []
    for item in tool_results:
        payload = _coerce_tool_result_payload(item)
        if payload.get("error") is None:
            continue
        tool_name = str(payload.get("tool_name") or "unknown_tool").strip().lower()
        error_type = str(payload.get("error_type") or "tool_error").strip().lower()
        patterns.append(f"{tool_name}:{error_type}")
    return sorted(dict.fromkeys(patterns))


def build_reflexion_summary_text(
    *,
    objective: str,
    scorecard: ReflexionScorecard,
    failure_summary: str = "",
    remediation: str = "",
    tool_error_patterns: Sequence[str] = (),
) -> str:
    """Build a compact memory-ready Reflexion summary."""
    lines = [
        f"Objective signature: {objective.strip()[:240]}",
        (
            "Scores: "
            f"overall={scorecard.overall_score:.3f}, "
            f"quality={scorecard.quality_score:.3f}, "
            f"grounding={scorecard.grounding_score:.3f}, "
            f"schema={scorecard.schema_score:.3f}, "
            f"compliance={scorecard.compliance_score:.3f}"
        ),
    ]
    if failure_summary.strip():
        lines.append(f"Failure: {failure_summary.strip()[:400]}")
    if remediation.strip():
        lines.append(f"Fix: {remediation.strip()[:500]}")
    if scorecard.retry_advice.strip():
        lines.append(f"Evaluator advice: {scorecard.retry_advice.strip()[:500]}")
    patterns = list(dict.fromkeys(tool_error_patterns or scorecard.tool_error_patterns))
    if patterns:
        lines.append(f"Tool error patterns: {', '.join(patterns[:12])}")
    return "\n".join(lines)


def evaluate_reflexion_replay_cases(
    cases: Sequence[ReflexionReplayCase | Mapping[str, Any]],
    *,
    evaluator: RubricReflexionEvaluator | None = None,
) -> ReflexionReplayEvaluation:
    """Replay held-out Reflexion trajectories and compute regression metrics."""
    active_evaluator = evaluator or RubricReflexionEvaluator()
    parsed_cases = [
        case if isinstance(case, ReflexionReplayCase) else ReflexionReplayCase.model_validate(case)
        for case in cases
    ]
    if not parsed_cases:
        return ReflexionReplayEvaluation()

    first_scores: list[float] = []
    final_scores: list[float] = []
    best_scores: list[float] = []
    improvement_count = 0
    repeated_error_count = 0
    pass_count = 0

    for case in parsed_cases:
        step_cards: list[ReflexionScorecard] = []
        step_errors: list[set[str]] = []
        for step in sorted(case.steps, key=lambda item: item.iteration):
            scorecard = step.scorecard or active_evaluator.evaluate_candidate(
                objective=case.objective,
                output_text=step.output_text,
                output_data=step.output_data,
                citations=step.citations,
                tool_results=step.tool_results,
            )
            step_cards.append(scorecard)
            step_errors.append(set(scorecard.tool_error_patterns))

        if not step_cards:
            first_scores.append(0.0)
            final_scores.append(0.0)
            best_scores.append(0.0)
            continue

        first_score = step_cards[0].overall_score
        final_score = step_cards[-1].overall_score
        best_score = max(item.overall_score for item in step_cards)
        first_scores.append(first_score)
        final_scores.append(final_score)
        best_scores.append(best_score)
        if final_score > first_score + active_evaluator.config.min_improvement_delta:
            improvement_count += 1
        if step_cards[-1].passed == case.expected_success:
            pass_count += 1

        repeated = False
        for previous, current in zip(step_errors, step_errors[1:]):
            if previous and previous & current:
                repeated = True
                break
        if repeated:
            repeated_error_count += 1

    sample_count = len(parsed_cases)
    return ReflexionReplayEvaluation(
        sample_count=sample_count,
        avg_first_score=sum(first_scores) / sample_count,
        avg_final_score=sum(final_scores) / sample_count,
        avg_best_score=sum(best_scores) / sample_count,
        improvement_rate=improvement_count / sample_count,
        repeated_error_rate=repeated_error_count / sample_count,
        pass_rate=pass_count / sample_count,
    )


def _quality_score(*, objective: str, output_text: str) -> float:
    text = output_text.strip()
    if not text:
        return 0.0

    objective_terms = {
        token
        for token in objective.lower().replace("/", " ").replace("-", " ").split()
        if len(token) > 3
    }
    output_terms = {
        token
        for token in text.lower().replace("/", " ").replace("-", " ").split()
        if len(token) > 3
    }
    overlap = 0.0
    if objective_terms:
        overlap = len(objective_terms & output_terms) / len(objective_terms)

    length_score = min(1.0, len(text) / 320.0)
    structure_score = 0.0
    if any(marker in text for marker in ("\n", "- ", "1.", "##")):
        structure_score = 1.0
    elif len(text.split()) >= 12:
        structure_score = 0.7

    generic_penalty = 0.15 if text.lower() in {"done", "ok", "final answer"} else 0.0
    return _clamp01(
        0.50 * overlap + 0.35 * length_score + 0.15 * structure_score - generic_penalty
    )


def _grounding_score(
    *,
    output_text: str,
    output_data: Mapping[str, Any],
    citations: Sequence[Mapping[str, Any]],
    required_citation_count: int,
) -> float:
    evidence_count = _count_evidence_items(
        output_text=output_text,
        output_data=output_data,
        citations=citations,
    )
    if required_citation_count > 0:
        coverage = min(1.0, evidence_count / required_citation_count)
    else:
        coverage = min(1.0, evidence_count / 3.0)

    citation_quality = 0.0
    if citations:
        valid = 0
        for citation in citations:
            url = str(citation.get("url") or "")
            snippet = str(citation.get("snippet") or citation.get("text") or "")
            host = urllib.parse.urlparse(url).hostname
            if host and snippet.strip():
                valid += 1
        citation_quality = valid / len(citations)

    return _clamp01(0.65 * coverage + 0.35 * citation_quality)


def _schema_score(
    *,
    output_data: Mapping[str, Any],
    tool_results: Sequence[Mapping[str, Any]],
    expected_output_schema: Mapping[str, Any],
) -> float:
    if any(item.get("error") is not None for item in tool_results):
        tool_success_score = (
            sum(1 for item in tool_results if item.get("error") is None)
            / max(len(tool_results), 1)
        )
    else:
        tool_success_score = 1.0

    if not expected_output_schema:
        return _clamp01(0.6 + 0.4 * tool_success_score)

    if expected_output_schema.get("type") == "object" and not isinstance(output_data, Mapping):
        return 0.0

    required = expected_output_schema.get("required")
    if isinstance(required, list) and required:
        present = sum(1 for key in required if isinstance(key, str) and key in output_data)
        field_score = present / len(required)
    else:
        field_score = 1.0 if isinstance(output_data, Mapping) else 0.0

    return _clamp01(0.7 * field_score + 0.3 * tool_success_score)


def _compliance_score(
    *,
    output_text: str,
    output_data: Mapping[str, Any],
    blocklist: Sequence[str],
) -> float:
    blob = f"{output_text}\n{json.dumps(dict(output_data), ensure_ascii=True, default=str)}".lower()
    if not blob.strip():
        return 0.0
    hits = sum(1 for marker in blocklist if marker.lower() in blob)
    if hits == 0:
        return 1.0
    return _clamp01(1.0 - 0.5 * hits)


def _count_evidence_items(
    *,
    output_text: str,
    output_data: Mapping[str, Any],
    citations: Sequence[Mapping[str, Any]],
) -> int:
    count = len(citations)
    claim_supports = output_data.get("claim_supports")
    if isinstance(claim_supports, Sequence) and not isinstance(claim_supports, str | bytes):
        count += len(claim_supports)
    count += output_text.count("http://") + output_text.count("https://")
    return count


def _weighted_score(scores: Mapping[str, float], weights: Mapping[str, float]) -> float:
    denom = sum(max(0.0, float(value)) for value in weights.values())
    if denom <= 0:
        return 0.0
    total = 0.0
    for key, weight in weights.items():
        total += max(0.0, float(weight)) * _clamp01(float(scores.get(key, 0.0)))
    return _clamp01(total / denom)


def _blocking_issues(
    *,
    quality_score: float,
    grounding_score: float,
    schema_score: float,
    compliance_score: float,
    overall_score: float,
    tool_error_patterns: Sequence[str],
    config: ReflexionEvaluatorConfig,
) -> list[str]:
    issues: list[str] = []
    if quality_score < config.min_quality_score:
        issues.append(f"quality_below_threshold:{quality_score:.3f}")
    if grounding_score < config.min_grounding_score:
        issues.append(f"grounding_below_threshold:{grounding_score:.3f}")
    if schema_score < config.min_schema_score:
        issues.append(f"schema_below_threshold:{schema_score:.3f}")
    if compliance_score < config.min_compliance_score:
        issues.append(f"compliance_below_threshold:{compliance_score:.3f}")
    if overall_score < config.min_overall_score:
        issues.append(f"overall_below_threshold:{overall_score:.3f}")
    issues.extend(tool_error_patterns)
    return sorted(dict.fromkeys(issues))


def _retry_advice(
    blocking_issues: Sequence[str],
    tool_results: Sequence[Mapping[str, Any]],
) -> str:
    hints: list[str] = []
    if any(issue.startswith("quality_below_threshold") for issue in blocking_issues):
        hints.append("Expand the answer with concrete task-specific reasoning and conclusions.")
    if any(issue.startswith("grounding_below_threshold") for issue in blocking_issues):
        hints.append("Fetch or attach more source-backed evidence and cite snippets/URLs explicitly.")
    if any(issue.startswith("schema_below_threshold") for issue in blocking_issues):
        hints.append("Repair the output schema and avoid repeating invalid tool arguments.")
    if any(issue.startswith("compliance_below_threshold") for issue in blocking_issues):
        hints.append("Remove policy-unsafe or prompt-injection-like content from the response.")
    tool_errors = extract_tool_error_patterns(tool_results)
    if tool_errors:
        hints.append(
            "Do not repeat these failed tool/error patterns: "
            + ", ".join(tool_errors[:12])
            + "."
        )
    return " ".join(hints).strip()


def _coerce_tool_result_payload(
    value: ToolCallResult | Mapping[str, Any],
) -> dict[str, Any]:
    if isinstance(value, ToolCallResult):
        return value.model_dump(mode="json", exclude_none=True)
    return dict(value)


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))
