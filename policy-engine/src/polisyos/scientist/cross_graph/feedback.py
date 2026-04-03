"""Public cross graph feedback module API."""
from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field

from polisyos.ir.analytics.cross_graph import (
    CrossGraphEvidenceProfile,
    EvidenceNeedAssessment,
    EvidenceNeedType,
    EvidenceStatus,
    TransportStatus,
)

if TYPE_CHECKING:
    from polisyos.academic.knowledge.search import ScholarKnowledgeGraph


class BenchmarkCausalEdge(BaseModel):
    """Benchmark causal edge public type."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    cause: str
    effect: str


class BenchmarkScholarQuery(BaseModel):
    """Benchmark scholar query public type."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    cause: str
    effect: str
    min_trust: float = Field(default=0.5, ge=0.0, le=1.0)
    support_mode: str = "hybrid"
    min_results: int = 2


class BenchmarkCredibilityPolicy(BaseModel):
    """Thresholds that decide when academic evidence is strong enough to count in benchmark review."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    min_confidence: float = Field(default=0.7, ge=0.0, le=1.0)
    min_unique_works: int = Field(default=2, ge=1)
    require_conflict_free: bool = True
    min_design_tier: int | None = Field(default=3, ge=1, le=4)
    max_evidence_age_years: int | None = Field(default=None, ge=1)


class AcademicBenchmarkScenario(BaseModel):
    """Academic benchmark scenario public type."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    scenario_id: str
    title: str
    policy_domain: str = ""
    weight: float = Field(default=1.0, ge=0.1)
    credibility_policy: BenchmarkCredibilityPolicy = Field(default_factory=BenchmarkCredibilityPolicy)
    causal_edges: list[BenchmarkCausalEdge] = Field(default_factory=list)
    parameters: list[str] = Field(default_factory=list)
    scholar_queries: list[BenchmarkScholarQuery] = Field(default_factory=list)


class AcademicBenchmarkSuite(BaseModel):
    """Academic benchmark suite public type."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    suite_id: str = "academic_usefulness"
    scenarios: list[AcademicBenchmarkScenario] = Field(default_factory=list)


def load_benchmark_suite(path: Path) -> AcademicBenchmarkSuite:
    """Load benchmark suite."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict) and "scenarios" in payload:
        return AcademicBenchmarkSuite.model_validate(payload)
    if isinstance(payload, list):
        return AcademicBenchmarkSuite(scenarios=[AcademicBenchmarkScenario.model_validate(item) for item in payload])
    raise ValueError(f"Unsupported benchmark suite payload at {path}")


def build_need_backlog(
    profile: CrossGraphEvidenceProfile,
    *,
    max_items: int | None = None,
) -> list[dict[str, Any]]:
    """Build need backlog."""
    items: list[dict[str, Any]] = []
    for assessment in profile.needs:
        priority = _assessment_priority(assessment)
        if priority <= 0.0:
            continue
        terms = _assessment_terms(assessment)
        if not terms:
            continue
        item = {
            "need_id": assessment.need.need_id,
            "need_type": assessment.need.need_type.value,
            "priority_weight": round(priority, 4),
            "terms": terms,
            "cause": assessment.need.cause,
            "effect": assessment.need.effect,
            "parameter_name": assessment.need.parameter_name,
            "blocking_reasons": list(assessment.blocking_reasons),
            "recommended_actions": list(assessment.recommended_actions),
            "labels": list(assessment.need.labels),
            "evidence_status": assessment.evidence_status.value,
            "transport_status": assessment.transport_status.value,
            "confidence": float(assessment.confidence),
        }
        items.append(item)
    items.sort(
        key=lambda item: (
            -float(item["priority_weight"]),
            str(item.get("need_type") or ""),
            str(item.get("need_id") or ""),
        )
    )
    return items[:max_items] if max_items is not None else items


def write_need_backlog(path: Path, items: list[dict[str, Any]]) -> None:
    """Write prioritized evidence needs to a JSONL backlog for offline sourcing or analyst triage."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        for item in items:
            fh.write(json.dumps(item, ensure_ascii=False) + "\n")


def append_need_backlog(path: Path, items: list[dict[str, Any]]) -> int:
    """Append new demand items to backlog, deduplicating by need_id.

    Returns the number of new items appended.
    """
    existing_ids: set[str] = set()
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                existing_ids.add(str(entry.get("need_id") or ""))
            except json.JSONDecodeError:
                continue

    path.parent.mkdir(parents=True, exist_ok=True)
    appended = 0
    with open(path, "a", encoding="utf-8") as fh:
        for item in items:
            need_id = str(item.get("need_id") or "")
            if need_id and need_id not in existing_ids:
                fh.write(json.dumps(item, ensure_ascii=False) + "\n")
                existing_ids.add(need_id)
                appended += 1
    return appended


def evaluate_benchmark_suite(
    profile: CrossGraphEvidenceProfile,
    suite: AcademicBenchmarkSuite,
    *,
    scholar_graph: ScholarKnowledgeGraph | None = None,
) -> dict[str, Any]:
    """Score a benchmark suite against the compiled evidence profile and optional scholar coverage."""
    scenario_results: list[dict[str, Any]] = []
    summary = {
        "scenarios": len(suite.scenarios),
        "causal_needs_total": 0,
        "causal_needs_supported": 0,
        "causal_needs_mixed": 0,
        "parameter_needs_total": 0,
        "parameter_needs_supported": 0,
        "parameter_needs_mixed": 0,
        "governance_blockers_due_to_academic": 0,
        "scholar_queries_total": 0,
        "scholar_queries_supported": 0,
    }
    for scenario in suite.scenarios:
        result = _evaluate_scenario(profile, scenario, scholar_graph=scholar_graph)
        scenario_results.append(result)
        summary["causal_needs_total"] += int(result["causal_needs_total"])
        summary["causal_needs_supported"] += int(result["causal_needs_supported"])
        summary["causal_needs_mixed"] += int(result["causal_needs_mixed"])
        summary["parameter_needs_total"] += int(result["parameter_needs_total"])
        summary["parameter_needs_supported"] += int(result["parameter_needs_supported"])
        summary["parameter_needs_mixed"] += int(result["parameter_needs_mixed"])
        summary["governance_blockers_due_to_academic"] += int(result["governance_blockers_due_to_academic"])
        summary["scholar_queries_total"] += int(result["scholar_queries_total"])
        summary["scholar_queries_supported"] += int(result["scholar_queries_supported"])

    summary["causal_supported_ratio"] = _ratio(
        summary["causal_needs_supported"],
        summary["causal_needs_total"],
    )
    summary["causal_mixed_ratio"] = _ratio(
        summary["causal_needs_mixed"],
        summary["causal_needs_total"],
    )
    summary["parameter_supported_ratio"] = _ratio(
        summary["parameter_needs_supported"],
        summary["parameter_needs_total"],
    )
    summary["parameter_mixed_ratio"] = _ratio(
        summary["parameter_needs_mixed"],
        summary["parameter_needs_total"],
    )
    summary["scholar_query_coverage_ratio"] = _ratio(
        summary["scholar_queries_supported"],
        summary["scholar_queries_total"],
    )
    return {
        "suite_id": suite.suite_id,
        "summary": summary,
        "scenarios": scenario_results,
    }


def _evaluate_scenario(
    profile: CrossGraphEvidenceProfile,
    scenario: AcademicBenchmarkScenario,
    *,
    scholar_graph: ScholarKnowledgeGraph | None,
) -> dict[str, Any]:
    causal_assessments = [
        _find_causal_assessment(profile, edge.cause, edge.effect)
        for edge in scenario.causal_edges
    ]
    parameter_assessments = [
        _find_parameter_assessment(profile, parameter_name)
        for parameter_name in scenario.parameters
    ]
    scholar_results: list[dict[str, Any]] = []
    if scholar_graph is not None:
        for query in scenario.scholar_queries:
            rows = scholar_graph.find_causal_evidence(
                query.cause,
                query.effect,
                min_trust=query.min_trust,
                support_mode=query.support_mode,
            )
            scholar_results.append(
                {
                    "cause": query.cause,
                    "effect": query.effect,
                    "results": len(rows),
                    "supported": len(rows) >= int(query.min_results),
                }
            )

    governance_blockers = 0
    governance_blockers += sum(
        1
        for assessment in causal_assessments + parameter_assessments
        if assessment is not None
        and (
            assessment.evidence_status is EvidenceStatus.UNSUPPORTED
            or assessment.transport_status is TransportStatus.UNSUPPORTED
        )
    )
    return {
        "scenario_id": scenario.scenario_id,
        "title": scenario.title,
        "policy_domain": scenario.policy_domain,
        "weight": float(scenario.weight),
        "causal_needs_total": len(scenario.causal_edges),
        "causal_needs_supported": sum(
            1
            for assessment in causal_assessments
            if assessment is not None and assessment.evidence_status is EvidenceStatus.SUPPORTED
        ),
        "causal_needs_mixed": sum(
            1
            for assessment in causal_assessments
            if assessment is not None and assessment.evidence_status is EvidenceStatus.MIXED
        ),
        "parameter_needs_total": len(scenario.parameters),
        "parameter_needs_supported": sum(
            1
            for assessment in parameter_assessments
            if assessment is not None and assessment.evidence_status is EvidenceStatus.SUPPORTED
        ),
        "parameter_needs_mixed": sum(
            1
            for assessment in parameter_assessments
            if assessment is not None and assessment.evidence_status is EvidenceStatus.MIXED
        ),
        "governance_blockers_due_to_academic": governance_blockers,
        "scholar_queries_total": len(scenario.scholar_queries),
        "scholar_queries_supported": sum(1 for row in scholar_results if bool(row["supported"])),
        "scholar_queries": scholar_results,
    }


def _find_causal_assessment(
    profile: CrossGraphEvidenceProfile,
    cause: str,
    effect: str,
) -> EvidenceNeedAssessment | None:
    clean_cause = str(cause).strip()
    clean_effect = str(effect).strip()
    for assessment in profile.needs:
        if assessment.need.need_type is not EvidenceNeedType.CAUSAL_EDGE_NEED:
            continue
        if assessment.need.cause == clean_cause and assessment.need.effect == clean_effect:
            return assessment
    return None


def _find_parameter_assessment(
    profile: CrossGraphEvidenceProfile,
    parameter_name: str,
) -> EvidenceNeedAssessment | None:
    clean_name = str(parameter_name).strip()
    for assessment in profile.needs:
        if assessment.need.need_type is not EvidenceNeedType.PARAMETER_NEED:
            continue
        if assessment.need.parameter_name == clean_name or assessment.need.param_path == clean_name:
            return assessment
    return None


def _assessment_priority(assessment: EvidenceNeedAssessment) -> float:
    evidence_weight = {
        EvidenceStatus.UNSUPPORTED: 1.0,
        EvidenceStatus.MIXED: 0.8,
        EvidenceStatus.INSUFFICIENT: 0.55,
        EvidenceStatus.SUPPORTED: 0.0,
    }[assessment.evidence_status]
    transport_bonus = 0.15 if assessment.transport_status is TransportStatus.UNSUPPORTED else 0.0
    need_bonus = (
        0.12
        if assessment.need.need_type in {EvidenceNeedType.CAUSAL_EDGE_NEED, EvidenceNeedType.PARAMETER_NEED}
        else 0.0
    )
    confidence_penalty = max(0.0, 0.1 - float(assessment.confidence) * 0.1)
    return round(evidence_weight + transport_bonus + need_bonus + confidence_penalty, 4)


def _assessment_terms(assessment: EvidenceNeedAssessment) -> list[str]:
    terms: list[str] = []
    if assessment.need.parameter_name:
        terms.append(str(assessment.need.parameter_name))
    if assessment.need.cause:
        terms.append(str(assessment.need.cause))
    if assessment.need.effect:
        terms.append(str(assessment.need.effect))
    if assessment.need.cause and assessment.need.effect:
        terms.append(f"{assessment.need.cause} {assessment.need.effect}")
    for label in assessment.need.labels:
        clean = str(label).strip()
        if clean:
            terms.append(clean)
    deduped: list[str] = []
    for term in terms:
        clean = str(term).strip()
        if clean and clean not in deduped:
            deduped.append(clean)
    return deduped


def _ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(float(numerator) / float(denominator), 4)


__all__ = [
    "AcademicBenchmarkScenario",
    "AcademicBenchmarkSuite",
    "BenchmarkCausalEdge",
    "BenchmarkScholarQuery",
    "build_need_backlog",
    "evaluate_benchmark_suite",
    "load_benchmark_suite",
    "write_need_backlog",
]
