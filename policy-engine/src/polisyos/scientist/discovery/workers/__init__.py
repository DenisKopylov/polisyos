"""Bounded discovery workers for refutation and data diagnostics."""

from __future__ import annotations

import asyncio
import hashlib
import json
import time
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from polisyos.ir.analytics.causal_discovery import DataCharacteristics
from polisyos.scientist.discovery.aggregator import EdgeConfidenceMatrix
from polisyos.scientist.discovery.priors import GraphPriorBundle, PriorKnowledgeBundle
from polisyos.scientist.discovery.schema import GraphHypothesis
from polisyos.scientist.discovery.stability import BootstrapStabilityReport
from polisyos.scientist.discovery.utility_judge import DownstreamUtilityReport
from polisyos.scientist.llm.factory import create_traced_gateway_client


class DiscoveryWorkerBudget(BaseModel):
    """Fixed execution budget for bounded discovery workers."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    max_hypotheses: int = Field(default=5, ge=1, le=20)
    max_disputed_edges: int = Field(default=8, ge=1, le=20)
    max_findings: int = Field(default=8, ge=1, le=20)
    max_gateway_calls: int = Field(default=1, ge=0, le=5)
    max_tokens: int = Field(default=1200, ge=128, le=4000)
    max_wall_seconds: float = Field(default=20.0, ge=0.1, le=120.0)


class DiscoveryWorkerContext(BaseModel):
    """Run context shared by worker executions."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: str = Field(default="discovery_workers", min_length=1)
    task_id: str = Field(default="discovery", min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class WorkerExecutionProvenance(BaseModel):
    """Replay-oriented execution metadata for one worker."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    worker_name: str = Field(min_length=1)
    mode: str = Field(min_length=1)
    fallback_used: bool = False
    duration_seconds: float = Field(default=0.0, ge=0.0)
    prompt_hash: str | None = None
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class DataProfileDiagnostic(BaseModel):
    """Structured data-plane diagnostic relevant to discovery."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str = Field(min_length=1)
    severity: str = Field(default="warning", min_length=1)
    message: str = Field(min_length=1)
    hypothesis_id: str | None = None
    edge_key: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class DataProfileReport(BaseModel):
    """Deterministic summary of discovery-relevant data diagnostics."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: str = Field(default="ready", min_length=1)
    diagnostics: list[DataProfileDiagnostic] = Field(default_factory=list)
    recommended_checks: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SkepticFinding(BaseModel):
    """Structured refutation or falsification suggestion."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    finding_id: str = Field(min_length=1)
    category: str = Field(min_length=1)
    severity: str = Field(default="warning", min_length=1)
    message: str = Field(min_length=1)
    falsification_suggestion: str = Field(default="", min_length=1)
    alternative_explanation: str = Field(default="", min_length=1)
    hypothesis_id: str | None = None
    edge_key: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class DataProfilerWorkerInput(BaseModel):
    """Inputs for the deterministic data-profiler worker."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    data_characteristics: DataCharacteristics | None = None
    data_quality_report: Any | None = None
    evidence_bundle: Any | None = None
    bootstrap_stability_report: BootstrapStabilityReport
    downstream_utility_report: DownstreamUtilityReport
    graph_prior_bundle: GraphPriorBundle
    prior_knowledge_bundle: PriorKnowledgeBundle | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SkepticWorkerInput(BaseModel):
    """Inputs for the bounded skeptic/refuter worker."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    hypotheses: list[GraphHypothesis] = Field(default_factory=list)
    edge_confidence_matrix: EdgeConfidenceMatrix
    bootstrap_stability_report: BootstrapStabilityReport
    downstream_utility_report: DownstreamUtilityReport
    graph_prior_bundle: GraphPriorBundle
    prior_knowledge_bundle: PriorKnowledgeBundle | None = None
    data_profile: DataProfileReport | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class DiscoveryWorkerBundle(BaseModel):
    """Combined bounded-worker output folded into discovery artifacts."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: str = Field(default="ready", min_length=1)
    data_profile: DataProfileReport = Field(default_factory=DataProfileReport)
    skeptic_findings: list[SkepticFinding] = Field(default_factory=list)
    targeted_hypothesis_ids: list[str] = Field(default_factory=list)
    targeted_edge_keys: list[str] = Field(default_factory=list)
    recommended_checks: list[str] = Field(default_factory=list)
    worker_provenance: list[WorkerExecutionProvenance] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def active_planner_context(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "targeted_hypothesis_ids": list(self.targeted_hypothesis_ids),
            "targeted_edge_keys": list(self.targeted_edge_keys),
            "recommended_checks": list(self.recommended_checks),
            "skeptic_categories": [finding.category for finding in self.skeptic_findings[:10]],
            "data_diagnostic_codes": [
                diagnostic.code for diagnostic in self.data_profile.diagnostics[:10]
            ],
        }


class SkepticWorkerConfig(BaseModel):
    """Gateway configuration for the skeptic worker."""

    model_config = ConfigDict(extra="forbid")

    model_name: str = "gpt-5.4"
    provider_hint: str | None = None
    max_tokens: int = Field(default=1200, ge=128, le=4000)
    temperature: float = Field(default=0.1, ge=0.0, le=1.0)
    fallback_on_error: bool = True


class DataProfilerWorker:
    """Deterministic discovery data profiler."""

    def profile(
        self,
        bundle: DataProfilerWorkerInput,
        *,
        budget: DiscoveryWorkerBudget | None = None,
        context: DiscoveryWorkerContext | None = None,
    ) -> tuple[DataProfileReport, WorkerExecutionProvenance]:
        del budget
        started = time.perf_counter()
        diagnostics: list[DataProfileDiagnostic] = []
        checks: list[str] = []
        notes: list[str] = []
        status = "ready"

        characteristics = bundle.data_characteristics
        if characteristics is None:
            status = "degraded"
            notes.append("data_characteristics_missing")
        else:
            sample_floor = max(30, characteristics.n_variables * 10)
            if characteristics.n_samples < sample_floor:
                diagnostics.append(
                    DataProfileDiagnostic(
                        code="sample_adequacy_low",
                        severity="warning",
                        message=(
                            f"Sample count {characteristics.n_samples} is below the "
                            f"heuristic floor {sample_floor} for {characteristics.n_variables} variables."
                        ),
                        metadata={
                            "n_samples": characteristics.n_samples,
                            "n_variables": characteristics.n_variables,
                        },
                    )
                )
                checks.append("Collect additional observations before trusting edge orientation.")
            if characteristics.suspected_latent_confounders:
                diagnostics.append(
                    DataProfileDiagnostic(
                        code="latent_confounding_suspected",
                        severity="warning",
                        message="Input data characteristics already flag likely latent confounding.",
                    )
                )
                checks.append("Stress latent-confounding-sensitive hypotheses with refuters.")
            if characteristics.has_mixed_types:
                diagnostics.append(
                    DataProfileDiagnostic(
                        code="mixed_types_present",
                        severity="info",
                        message="Mixed variable types may distort orientation confidence for some methods.",
                    )
                )

        quality_grade = _extract_quality_grade(bundle.data_quality_report)
        quality_score = _extract_quality_score(bundle.data_quality_report)
        if quality_grade is not None:
            metadata = {"quality_grade": quality_grade}
            if quality_score is not None:
                metadata["quality_score"] = quality_score
            if quality_grade.lower() in {"d", "e", "bronze", "poor"}:
                diagnostics.append(
                    DataProfileDiagnostic(
                        code="data_quality_low",
                        severity="warning",
                        message=f"Data quality report grade '{quality_grade}' is below the preferred bar.",
                        metadata=metadata,
                    )
                )
                checks.append("Repair or exclude low-quality evidence before promotion.")

        evidence_proxy_flags = _proxy_signals_from_evidence_bundle(bundle.evidence_bundle)
        for code, message in evidence_proxy_flags:
            diagnostics.append(
                DataProfileDiagnostic(
                    code=code,
                    severity="warning",
                    message=message,
                )
            )
            checks.append(
                "Inspect proxy coverage and missingness assumptions in the evidence bundle."
            )

        for disputed in bundle.graph_prior_bundle.disputed_edges[:4]:
            diagnostics.append(
                DataProfileDiagnostic(
                    code="disputed_edge_support_gap",
                    severity="warning",
                    message=f"Discovery prior still contains disputed edge group '{disputed.skeleton_key}'.",
                    edge_key=(
                        disputed.candidate_edges[0].edge_key if disputed.candidate_edges else None
                    ),
                    metadata={"dispute_id": disputed.dispute_id},
                )
            )
            checks.append("Acquire more targeted evidence for disputed-edge regions.")

        if bundle.prior_knowledge_bundle is not None:
            for edge_key in bundle.prior_knowledge_bundle.unresolved_edges[:4]:
                diagnostics.append(
                    DataProfileDiagnostic(
                        code="academic_support_unresolved",
                        severity="info",
                        message=f"Academic support remains unresolved for edge '{edge_key}'.",
                        edge_key=edge_key,
                    )
                )

        for score in bundle.downstream_utility_report.scores[:5]:
            if score.identification_status != "identified":
                diagnostics.append(
                    DataProfileDiagnostic(
                        code="identification_gap",
                        severity="warning",
                        message=(
                            f"Hypothesis '{score.hypothesis_id}' is only "
                            f"'{score.identification_status}' downstream."
                        ),
                        hypothesis_id=score.hypothesis_id,
                        metadata={"identification_status": score.identification_status},
                    )
                )
                checks.append(
                    "Validate missing measurements or transport assumptions for top-ranked hypotheses."
                )

        report = DataProfileReport(
            status=status,
            diagnostics=_dedupe_diagnostics(diagnostics),
            recommended_checks=_dedupe_text(checks),
            notes=notes,
            metadata={
                "run_context": (context.model_dump(mode="json") if context is not None else {}),
                **bundle.metadata,
            },
        )
        provenance = WorkerExecutionProvenance(
            worker_name="data_profiler",
            mode="deterministic",
            fallback_used=False,
            duration_seconds=time.perf_counter() - started,
            metadata={
                "diagnostic_count": len(report.diagnostics),
            },
        )
        return report, provenance


class SkepticWorker:
    """Bounded skeptic/refuter with deterministic fallback."""

    def __init__(
        self,
        config: SkepticWorkerConfig | None = None,
    ) -> None:
        self._config = config or SkepticWorkerConfig()

    async def critique_async(
        self,
        bundle: SkepticWorkerInput,
        *,
        budget: DiscoveryWorkerBudget | None = None,
        context: DiscoveryWorkerContext | None = None,
    ) -> tuple[list[SkepticFinding], WorkerExecutionProvenance]:
        worker_budget = budget or DiscoveryWorkerBudget()
        started = time.perf_counter()
        payload = self._build_payload(bundle, worker_budget)
        prompt_hash = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
        ).hexdigest()[:16]
        warnings: list[str] = []

        if worker_budget.max_gateway_calls <= 0:
            findings = self._fallback_findings(bundle, worker_budget)
            return findings, WorkerExecutionProvenance(
                worker_name="skeptic",
                mode="deterministic",
                fallback_used=True,
                duration_seconds=time.perf_counter() - started,
                prompt_hash=prompt_hash,
                warnings=["gateway_calls_disabled"],
            )

        client = create_traced_gateway_client(
            model_name=self._config.model_name,
            provider_hint=self._config.provider_hint,
            run_id=(context.run_id if context is not None else "discovery_skeptic"),
        )
        if client is None:
            findings = self._fallback_findings(bundle, worker_budget)
            return findings, WorkerExecutionProvenance(
                worker_name="skeptic",
                mode="deterministic",
                fallback_used=True,
                duration_seconds=time.perf_counter() - started,
                prompt_hash=prompt_hash,
                warnings=["gateway_unavailable"],
            )

        try:
            response = await client.generate(
                system=(
                    "You are a bounded discovery skeptic. "
                    "Return JSON with key 'findings' only. "
                    "Each finding must include category, severity, message, "
                    "falsification_suggestion, alternative_explanation, hypothesis_id, edge_key."
                ),
                user=json.dumps(payload, sort_keys=True, default=str),
                response_format={"type": "json_object"},
                temperature=self._config.temperature,
                max_tokens=min(self._config.max_tokens, worker_budget.max_tokens),
                _run_id=(context.run_id if context is not None else "discovery_skeptic"),
            )
            parsed = _parse_json_object(getattr(response, "content", response))
            raw_findings = parsed.get("findings", [])
            findings = [
                SkepticFinding.model_validate(
                    {
                        "finding_id": f"skeptic_{index + 1}",
                        **item,
                    }
                )
                for index, item in enumerate(raw_findings[: worker_budget.max_findings])
                if isinstance(item, dict)
            ]
            if not findings:
                warnings.append("empty_gateway_response")
                findings = self._fallback_findings(bundle, worker_budget)
                fallback_used = True
                mode = "gateway_json_fallback"
            else:
                findings = self._limit_findings(findings, worker_budget)
                fallback_used = False
                mode = "gateway_json"
            return findings, WorkerExecutionProvenance(
                worker_name="skeptic",
                mode=mode,
                fallback_used=fallback_used,
                duration_seconds=time.perf_counter() - started,
                prompt_hash=prompt_hash,
                warnings=warnings,
                metadata={"finding_count": len(findings)},
            )
        except Exception:
            if not self._config.fallback_on_error:
                raise
            findings = self._fallback_findings(bundle, worker_budget)
            return findings, WorkerExecutionProvenance(
                worker_name="skeptic",
                mode="deterministic",
                fallback_used=True,
                duration_seconds=time.perf_counter() - started,
                prompt_hash=prompt_hash,
                warnings=["gateway_error_fallback"],
                metadata={"finding_count": len(findings)},
            )

    def critique(
        self,
        bundle: SkepticWorkerInput,
        *,
        budget: DiscoveryWorkerBudget | None = None,
        context: DiscoveryWorkerContext | None = None,
    ) -> tuple[list[SkepticFinding], WorkerExecutionProvenance]:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.critique_async(bundle, budget=budget, context=context))
        findings = self._fallback_findings(bundle, budget or DiscoveryWorkerBudget())
        return findings, WorkerExecutionProvenance(
            worker_name="skeptic",
            mode="deterministic",
            fallback_used=True,
            duration_seconds=0.0,
            warnings=["async_loop_active_using_fallback"],
            metadata={"finding_count": len(findings)},
        )

    def _build_payload(
        self,
        bundle: SkepticWorkerInput,
        budget: DiscoveryWorkerBudget,
    ) -> dict[str, Any]:
        ranked_ids = bundle.downstream_utility_report.recommended_shortlist[: budget.max_hypotheses]
        ranked_scores = [
            score.model_dump(mode="json")
            for score in bundle.downstream_utility_report.scores[: budget.max_hypotheses]
        ]
        disputed_edges = [
            {
                "dispute_id": disputed.dispute_id,
                "skeleton_key": disputed.skeleton_key,
                "edge_keys": [edge.edge_key for edge in disputed.candidate_edges],
                "reasons": list(disputed.dispute_reasons),
            }
            for disputed in bundle.graph_prior_bundle.disputed_edges[: budget.max_disputed_edges]
        ]
        return {
            "recommended_shortlist": ranked_ids,
            "ranked_scores": ranked_scores,
            "disputed_edges": disputed_edges,
            "data_profile": (
                bundle.data_profile.model_dump(mode="json")
                if bundle.data_profile is not None
                else None
            ),
            "prior_warnings": (
                bundle.prior_knowledge_bundle.warnings
                if bundle.prior_knowledge_bundle is not None
                else []
            ),
            "metadata": dict(bundle.metadata),
        }

    def _fallback_findings(
        self,
        bundle: SkepticWorkerInput,
        budget: DiscoveryWorkerBudget,
    ) -> list[SkepticFinding]:
        findings: list[SkepticFinding] = []
        seen_keys: set[tuple[str | None, str | None, str]] = set()

        for disputed in bundle.graph_prior_bundle.disputed_edges[: budget.max_disputed_edges]:
            edge_key = disputed.candidate_edges[0].edge_key if disputed.candidate_edges else None
            key = (None, edge_key, "orientation_conflict")
            if key in seen_keys:
                continue
            seen_keys.add(key)
            findings.append(
                SkepticFinding(
                    finding_id=f"skeptic_prior_{len(findings) + 1}",
                    category="orientation_conflict",
                    severity="warning",
                    message=f"Disputed edge group '{disputed.skeleton_key}' still lacks a stable orientation.",
                    falsification_suggestion="Run a targeted intervention or collect a dataset slice that orients the edge.",
                    alternative_explanation="Observed direction may be an artifact of mixed family support.",
                    edge_key=edge_key,
                    metadata={"dispute_id": disputed.dispute_id},
                )
            )

        for score in bundle.downstream_utility_report.scores[: budget.max_hypotheses]:
            if score.identification_status == "identified":
                continue
            key = (score.hypothesis_id, None, "identification_gap")
            if key in seen_keys:
                continue
            seen_keys.add(key)
            findings.append(
                SkepticFinding(
                    finding_id=f"skeptic_ident_{len(findings) + 1}",
                    category="identification_gap",
                    severity="warning",
                    message=(
                        f"Top hypothesis '{score.hypothesis_id}' remains "
                        f"'{score.identification_status}', so downstream utility may be overstated."
                    ),
                    falsification_suggestion="Re-run identification under tighter measurement and transport assumptions.",
                    alternative_explanation="The graph may fit edge evidence but still miss the estimand structure.",
                    hypothesis_id=score.hypothesis_id,
                    metadata={"identification_status": score.identification_status},
                )
            )

        for entry in bundle.edge_confidence_matrix.entries[: budget.max_disputed_edges]:
            if not entry.disputed and float(entry.orientation_confidence) >= 0.55:
                continue
            key = (None, entry.edge_key, "low_margin_orientation")
            if key in seen_keys:
                continue
            seen_keys.add(key)
            findings.append(
                SkepticFinding(
                    finding_id=f"skeptic_matrix_{len(findings) + 1}",
                    category="low_margin_orientation",
                    severity="info",
                    message=f"Edge '{entry.edge_key}' has low orientation margin and may be brittle under resampling.",
                    falsification_suggestion="Validate the orientation on a new bootstrap slice or natural experiment.",
                    alternative_explanation="Equivalent-class ambiguity may explain the current edge ranking.",
                    edge_key=entry.edge_key,
                    metadata={"orientation_confidence": entry.orientation_confidence},
                )
            )

        if bundle.data_profile is not None:
            for diagnostic in bundle.data_profile.diagnostics[: budget.max_findings]:
                if diagnostic.severity not in {"warning", "error"}:
                    continue
                key = (diagnostic.hypothesis_id, diagnostic.edge_key, diagnostic.code)
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                findings.append(
                    SkepticFinding(
                        finding_id=f"skeptic_profile_{len(findings) + 1}",
                        category="data_support_gap",
                        severity="warning",
                        message=diagnostic.message,
                        falsification_suggestion="Verify the claim against the flagged data-quality or support issue.",
                        alternative_explanation="The discovery signal may come from incomplete or mismatched support.",
                        hypothesis_id=diagnostic.hypothesis_id,
                        edge_key=diagnostic.edge_key,
                        metadata={"diagnostic_code": diagnostic.code},
                    )
                )

        return self._limit_findings(findings, budget)

    @staticmethod
    def _limit_findings(
        findings: list[SkepticFinding],
        budget: DiscoveryWorkerBudget,
    ) -> list[SkepticFinding]:
        ordered = sorted(
            findings,
            key=lambda item: (
                {"critical": 3, "warning": 2, "info": 1}.get(item.severity, 0),
                item.category,
                item.finding_id,
            ),
            reverse=True,
        )
        return ordered[: budget.max_findings]


def run_bounded_discovery_workers(
    *,
    data_profiler_input: DataProfilerWorkerInput,
    skeptic_input: SkepticWorkerInput,
    budget: DiscoveryWorkerBudget | None = None,
    context: DiscoveryWorkerContext | None = None,
    skeptic_worker: SkepticWorker | None = None,
    data_profiler_worker: DataProfilerWorker | None = None,
) -> DiscoveryWorkerBundle:
    """Run bounded discovery workers in the prescribed order."""

    worker_budget = budget or DiscoveryWorkerBudget()
    worker_context = context or DiscoveryWorkerContext()
    profiler = data_profiler_worker or DataProfilerWorker()
    skeptic = skeptic_worker or SkepticWorker()

    data_profile, profiler_provenance = profiler.profile(
        data_profiler_input,
        budget=worker_budget,
        context=worker_context,
    )
    skeptic_findings, skeptic_provenance = skeptic.critique(
        skeptic_input.model_copy(update={"data_profile": data_profile}),
        budget=worker_budget,
        context=worker_context,
    )

    targeted_hypothesis_ids = sorted(
        {
            item
            for item in (
                [
                    score.hypothesis_id
                    for score in data_profiler_input.downstream_utility_report.scores[
                        : worker_budget.max_hypotheses
                    ]
                ]
                + [finding.hypothesis_id for finding in skeptic_findings]
            )
            if item
        }
    )
    targeted_edge_keys = sorted(
        {
            item
            for item in (
                [finding.edge_key for finding in skeptic_findings]
                + [diagnostic.edge_key for diagnostic in data_profile.diagnostics]
            )
            if item
        }
    )
    status = "ready"
    notes: list[str] = []
    if data_profile.status != "ready":
        status = "degraded"
        notes.extend(data_profile.notes)
    recommended_checks = _dedupe_text(
        list(data_profile.recommended_checks)
        + [
            finding.falsification_suggestion
            for finding in skeptic_findings
            if finding.falsification_suggestion
        ]
    )
    return DiscoveryWorkerBundle(
        status=status,
        data_profile=data_profile,
        skeptic_findings=skeptic_findings,
        targeted_hypothesis_ids=targeted_hypothesis_ids,
        targeted_edge_keys=targeted_edge_keys,
        recommended_checks=recommended_checks,
        worker_provenance=[profiler_provenance, skeptic_provenance],
        notes=notes,
        metadata=worker_context.metadata,
    )


def _dedupe_diagnostics(
    diagnostics: list[DataProfileDiagnostic],
) -> list[DataProfileDiagnostic]:
    deduped: list[DataProfileDiagnostic] = []
    seen: set[tuple[str, str | None, str | None]] = set()
    for diagnostic in diagnostics:
        key = (diagnostic.code, diagnostic.hypothesis_id, diagnostic.edge_key)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(diagnostic)
    return deduped


def _dedupe_text(values: list[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = str(value).strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)
    return deduped


def _extract_quality_grade(report: Any) -> str | None:
    if report is None:
        return None
    if isinstance(report, dict):
        value = report.get("grade") or report.get("composite_grade")
        return None if value is None else str(value)
    for attr in ("grade", "composite_grade"):
        value = getattr(report, attr, None)
        if value is not None:
            return str(value)
    return None


def _extract_quality_score(report: Any) -> float | None:
    if report is None:
        return None
    raw = report.get("score") if isinstance(report, dict) else getattr(report, "score", None)
    try:
        return None if raw is None else float(raw)
    except (TypeError, ValueError):
        return None


def _proxy_signals_from_evidence_bundle(bundle: Any) -> list[tuple[str, str]]:
    if bundle is None:
        return []
    flags: list[tuple[str, str]] = []
    quality = (
        bundle.get("quality_report")
        if isinstance(bundle, dict)
        else getattr(bundle, "quality_report", None)
    )
    if isinstance(quality, dict):
        status = str(quality.get("availability_status", "")).lower()
        if "proxy" in status:
            flags.append(
                (
                    "proxy_only_coverage",
                    "Evidence bundle indicates proxy-only coverage for at least part of the estimand surface.",
                )
            )
    sources = (
        bundle.get("sources", []) if isinstance(bundle, dict) else getattr(bundle, "sources", [])
    )
    for source in sources or []:
        text = json.dumps(source, default=str).lower()
        if "proxy" in text:
            flags.append(
                (
                    "proxy_signal_present",
                    "Evidence bundle source metadata references proxy-based coverage or measurement.",
                )
            )
            break
    return flags


def _parse_json_object(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        return json.loads(raw)
    if hasattr(raw, "model_dump"):
        dumped = raw.model_dump(mode="json")
        if isinstance(dumped, dict):
            return dumped
    raise ValueError("Expected JSON object payload from gateway.")


__all__ = [
    "DataProfileDiagnostic",
    "DataProfileReport",
    "DataProfilerWorker",
    "DataProfilerWorkerInput",
    "DiscoveryWorkerBudget",
    "DiscoveryWorkerBundle",
    "DiscoveryWorkerContext",
    "SkepticFinding",
    "SkepticWorker",
    "SkepticWorkerConfig",
    "SkepticWorkerInput",
    "WorkerExecutionProvenance",
    "run_bounded_discovery_workers",
]
