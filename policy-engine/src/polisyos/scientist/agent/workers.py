"""Worker task envelopes, result contracts, and worker-as-tool adapters."""

from __future__ import annotations

import inspect
import time
import urllib.parse
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import asdict
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from polisyos.scholar.search.models import SearchBudgetControls, SearchConstraints
from polisyos.scientist.agent.protocols import (
    CritiqueIssue,
    CritiqueReport,
    DraftResult,
    ProblemFrame,
)
from polisyos.scientist.agent.reflexion_evaluator import RubricReflexionEvaluator
from polisyos.scientist.agent.tools.registry import ToolRegistry
from polisyos.scientist.agent.tools.schema import ToolDefinition

if TYPE_CHECKING:
    from polisyos.ir.trinity import TrinityBundle
    from polisyos.scholar.search.service import ScholarDeepSearchService

__all__ = [
    "WorkerBudgetHints",
    "WorkerCitation",
    "WorkerExecutionMode",
    "WorkerResultPayload",
    "WorkerSourcePolicy",
    "WorkerTaskEnvelope",
    "WorkerTaskResult",
    "build_critic_worker_handler",
    "build_drafter_worker_handler",
    "build_reflexion_evaluator_worker_handler",
    "build_scholar_search_worker_handler",
    "build_sectioned_worker_envelopes",
    "build_self_moa_worker_envelopes",
    "build_worker_tool_registry",
    "critique_from_payload",
    "draft_from_payload",
    "register_worker_tool",
]


class WorkerExecutionMode(StrEnum):
    """Supervisor execution mode attached to a worker task envelope."""

    SECTIONING = "sectioning"
    VOTING = "voting"
    SELF_MOA = "self_moa"


class WorkerSourcePolicy(BaseModel):
    """Source and citation policy expected from one worker task."""

    model_config = ConfigDict(extra="forbid")

    require_citations: bool = False
    require_snippets: bool = False
    min_citations: int = Field(default=0, ge=0, le=128)
    max_citations: int = Field(default=16, ge=1, le=256)
    allowed_domains: list[str] = Field(default_factory=list)
    blocked_domains: list[str] = Field(default_factory=list)
    source_types: list[str] = Field(default_factory=list)
    recency_days: int | None = Field(default=None, ge=1, le=3650)
    locale: str = "en-US"
    user_location: str | None = None
    allow_private_networks: bool = False

    @field_validator("allowed_domains", "blocked_domains", "source_types")
    @classmethod
    def _normalize_text_list(cls, values: list[str]) -> list[str]:
        cleaned = [value.strip().lower() for value in values if value and value.strip()]
        return sorted(dict.fromkeys(cleaned))


class WorkerBudgetHints(BaseModel):
    """Budget and timeout hints for one worker invocation."""

    model_config = ConfigDict(extra="forbid")

    max_cost_usd: Decimal | None = Field(default=None, ge=Decimal("0"))
    max_tokens: int | None = Field(default=None, ge=1)
    timeout_s: float | None = Field(default=None, ge=1.0, le=3600.0)
    model_id: str | None = None

    @property
    def reserved_cost_usd(self) -> Decimal:
        """Return an explicit per-task cost reservation."""
        return self.max_cost_usd or Decimal("0")


class WorkerTaskEnvelope(BaseModel):
    """Supervisor → worker task envelope."""

    model_config = ConfigDict(extra="forbid")

    task_id: str = Field(..., min_length=1, max_length=128)
    worker_name: str = Field(..., pattern=r"^[a-z][a-z0-9_]*$")
    objective: str = Field(..., min_length=1)
    constraints: list[str] = Field(default_factory=list)
    expected_output_schema: dict[str, Any] = Field(default_factory=dict)
    source_policy: WorkerSourcePolicy = Field(default_factory=WorkerSourcePolicy)
    budget_hints: WorkerBudgetHints = Field(default_factory=WorkerBudgetHints)
    input_payload: dict[str, Any] = Field(default_factory=dict)
    mode: WorkerExecutionMode = WorkerExecutionMode.SECTIONING
    section_id: str | None = None
    vote_group_id: str | None = None
    depends_on_task_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class WorkerCitation(BaseModel):
    """Citation payload returned by worker tools."""

    model_config = ConfigDict(extra="forbid")

    url: str
    title: str = ""
    snippet: str = ""
    source_id: str = ""
    start_char: int | None = Field(default=None, ge=0)
    end_char: int | None = Field(default=None, ge=0)
    score: float = 0.0

    @property
    def domain(self) -> str:
        """Extract a lower-cased domain for source-policy checks."""
        return (urllib.parse.urlparse(self.url).hostname or "").lower()


class WorkerResultPayload(BaseModel):
    """Structured output content produced by one worker."""

    model_config = ConfigDict(extra="allow")

    text: str = ""
    data: dict[str, Any] = Field(default_factory=dict)


class WorkerTaskResult(BaseModel):
    """Normalized result of one worker tool invocation."""

    model_config = ConfigDict(extra="forbid")

    task_id: str
    worker_name: str
    success: bool = True
    output_text: str = ""
    output_data: dict[str, Any] = Field(default_factory=dict)
    citations: list[WorkerCitation] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    duration_ms: int = Field(default=0, ge=0)
    cost_usd: Decimal = Field(default=Decimal("0"), ge=Decimal("0"))
    token_usage: dict[str, int] = Field(default_factory=dict)
    section_id: str | None = None
    vote_group_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    error: str | None = None
    error_type: str | None = None

    @property
    def normalized_vote_key(self) -> str:
        """Canonicalize textual output for self-consistency voting."""
        text = self.output_text.strip().lower()
        return " ".join(text.split())


WorkerToolHandler = Callable[
    [WorkerTaskEnvelope],
    WorkerTaskResult | Mapping[str, Any] | Awaitable[WorkerTaskResult | Mapping[str, Any]],
]


_WORKER_TOOL_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["envelope"],
    "additionalProperties": False,
    "properties": {
        "envelope": {
            "type": "object",
            "required": ["task_id", "worker_name", "objective"],
        }
    },
}


def register_worker_tool(
    registry: ToolRegistry,
    worker_name: str,
    handler: WorkerToolHandler,
    *,
    description: str | None = None,
    timeout_s: float = 60.0,
    domain: str = "swarm",
) -> None:
    """Register one worker callback as a tool that accepts a `WorkerTaskEnvelope`."""

    async def _invoke_worker(envelope: dict[str, Any]) -> WorkerTaskResult:
        started = time.perf_counter()
        task = WorkerTaskEnvelope.model_validate(envelope)
        if task.worker_name != worker_name:
            raise ValueError(
                f"worker_name mismatch: expected {worker_name}, got {task.worker_name}"
            )

        raw = handler(task)
        if inspect.isawaitable(raw):
            raw = await raw
        result = _coerce_worker_result(raw, task)
        if result.duration_ms <= 0:
            result.duration_ms = int((time.perf_counter() - started) * 1000)
        return _enforce_worker_contract(task, result)

    registry.register(
        ToolDefinition(
            name=worker_name,
            description=description or f"Swarm worker tool: {worker_name}",
            parameters=_WORKER_TOOL_SCHEMA,
            domain=domain,
            timeout_s=timeout_s,
        ),
        _invoke_worker,
    )


def build_worker_tool_registry(
    handlers: Mapping[str, WorkerToolHandler],
    *,
    descriptions: Mapping[str, str] | None = None,
    timeout_s: float = 60.0,
) -> ToolRegistry:
    """Build a worker tool registry from a mapping of worker names to handlers."""
    registry = ToolRegistry()
    for worker_name, handler in handlers.items():
        register_worker_tool(
            registry,
            worker_name,
            handler,
            description=(descriptions or {}).get(worker_name),
            timeout_s=timeout_s,
        )
    return registry


def build_scholar_search_worker_handler(
    search_service: ScholarDeepSearchService,
) -> WorkerToolHandler:
    """Adapt `ScholarDeepSearchService.deep_search()` to a generic worker tool."""

    async def _handler(task: WorkerTaskEnvelope) -> WorkerTaskResult:
        bundle = await search_service.deep_search(
            question=task.objective,
            claim_texts=[task.objective, *task.constraints],
            constraints=SearchConstraints(
                allowed_domains=list(task.source_policy.allowed_domains),
                blocked_domains=list(task.source_policy.blocked_domains),
                source_types=list(task.source_policy.source_types),
                recency_days=task.source_policy.recency_days,
                locale=task.source_policy.locale,
                user_location=task.source_policy.user_location,
                allow_private_networks=task.source_policy.allow_private_networks,
            ),
            budgets=_search_budgets_from_hints(task.budget_hints),
        )
        title_by_source_id = {
            source.source_id: source.title
            for source in bundle.sources
            if source.title
        }
        citations = [
            WorkerCitation(
                url=str(snippet.url),
                title=title_by_source_id.get(snippet.source_id, snippet.source_id),
                snippet=snippet.text,
                source_id=snippet.source_id,
                start_char=snippet.start_char,
                end_char=snippet.end_char,
                score=snippet.relevance_score,
            )
            for snippet in bundle.snippets[: task.source_policy.max_citations]
        ]
        summary_lines = [
            f"[{citation.source_id}] {citation.snippet}".strip()
            for citation in citations
            if citation.snippet.strip()
        ]
        uncertainty_notes = "; ".join(bundle.uncertainty_notes)
        if uncertainty_notes:
            summary_lines.append(f"Uncertainty: {uncertainty_notes}")
        return WorkerTaskResult(
            task_id=task.task_id,
            worker_name=task.worker_name,
            success=True,
            output_text="\n".join(summary_lines).strip(),
            output_data={
                "bundle_id": bundle.bundle_id,
                "query_traces": [trace.model_dump(mode="json") for trace in bundle.query_traces],
                "claim_supports": [link.model_dump(mode="json") for link in bundle.claim_supports],
                "sources": [source.model_dump(mode="json") for source in bundle.sources],
                "uncertainty_notes": list(bundle.uncertainty_notes),
                "partial": bundle.partial,
            },
            citations=citations,
            confidence=max(
                (support.support_score for support in bundle.claim_supports),
                default=0.0,
            ),
            section_id=task.section_id,
            vote_group_id=task.vote_group_id,
            metadata={"mode": task.mode.value, **task.metadata},
        )

    return _handler


def build_reflexion_evaluator_worker_handler(
    evaluator: RubricReflexionEvaluator | None = None,
) -> WorkerToolHandler:
    """Adapt `RubricReflexionEvaluator` to a worker tool handler."""
    active_evaluator = evaluator or RubricReflexionEvaluator()

    async def _handler(task: WorkerTaskEnvelope) -> WorkerTaskResult:
        payload = dict(task.input_payload)
        output_data = payload.get("output_data")
        citations = payload.get("citations")
        tool_results = payload.get("tool_results")
        scorecard = active_evaluator.evaluate_candidate(
            objective=str(payload.get("objective") or task.objective),
            output_text=str(payload.get("output_text") or ""),
            output_data=output_data if isinstance(output_data, dict) else {},
            citations=citations if isinstance(citations, list) else [],
            tool_results=tool_results if isinstance(tool_results, list) else [],
            expected_output_schema=(
                payload.get("expected_output_schema")
                if isinstance(payload.get("expected_output_schema"), dict)
                else task.expected_output_schema
            ),
        )
        return WorkerTaskResult(
            task_id=task.task_id,
            worker_name=task.worker_name,
            success=True,
            output_text=scorecard.retry_advice,
            output_data={"scorecard": scorecard.model_dump(mode="json")},
            confidence=scorecard.overall_score,
            section_id=task.section_id,
            vote_group_id=task.vote_group_id,
            metadata={"mode": task.mode.value, **task.metadata},
        )

    return _handler


def build_drafter_worker_handler(
    drafter: object,
    *,
    problem_frame: ProblemFrame,
    data_context: Mapping[str, Any] | None = None,
    prior_drafts: Sequence[DraftResult] | None = None,
) -> WorkerToolHandler:
    """Adapt a Drafter agent to a worker tool handler."""
    shared_data_context = dict(data_context or {})
    shared_prior_drafts = list(prior_drafts or [])

    async def _handler(task: WorkerTaskEnvelope) -> WorkerTaskResult:
        hints = [
            item
            for item in [*task.constraints, *list(task.input_payload.get("hints") or [])]
            if isinstance(item, str) and item.strip()
        ]
        draft = await drafter.draft_policy(
            problem_frame,
            data_context=shared_data_context or None,
            hints=hints or None,
            prior_drafts=shared_prior_drafts or None,
        )
        citations = [
            WorkerCitation(
                url=str(citation.get("url") or ""),
                title=str(citation.get("title") or ""),
                snippet=str(citation.get("snippet") or ""),
                source_id=str(citation.get("source_id") or ""),
                start_char=_coerce_optional_int(citation.get("start_char")),
                end_char=_coerce_optional_int(citation.get("end_char")),
                score=_coerce_float(citation.get("score")),
            )
            for citation in draft.citations[: task.source_policy.max_citations]
            if isinstance(citation, Mapping) and str(citation.get("url") or "").strip()
        ]
        return WorkerTaskResult(
            task_id=task.task_id,
            worker_name=task.worker_name,
            success=True,
            output_text=draft.narrative,
            output_data={
                "draft": _draft_to_payload(draft),
                "claim_supports": list(draft.claim_supports),
                "grounding_notes": list(draft.grounding_notes),
            },
            citations=citations,
            confidence=max(0.0, min(1.0, float(draft.confidence))),
            section_id=task.section_id,
            vote_group_id=task.vote_group_id,
            metadata={"mode": task.mode.value, **task.metadata},
        )

    return _handler


def build_critic_worker_handler(
    critic: object,
    *,
    problem_frame: ProblemFrame,
    trinity_bundle: TrinityBundle,
) -> WorkerToolHandler:
    """Adapt a Critic agent to a worker tool handler."""

    async def _handler(task: WorkerTaskEnvelope) -> WorkerTaskResult:
        critique = await critic.critique(
            trinity_bundle,
            problem_frame,
            depth=str(task.input_payload.get("depth") or "standard"),
        )
        citations = [
            WorkerCitation(
                url=str(citation.get("url") or ""),
                title=str(citation.get("title") or ""),
                snippet=str(citation.get("snippet") or ""),
                source_id=str(citation.get("source_id") or ""),
                start_char=_coerce_optional_int(citation.get("start_char")),
                end_char=_coerce_optional_int(citation.get("end_char")),
                score=_coerce_float(citation.get("score")),
            )
            for citation in critique.citations[: task.source_policy.max_citations]
            if isinstance(citation, Mapping) and str(citation.get("url") or "").strip()
        ]
        summary = [
            f"Verdict: {critique.verdict}",
            f"Issues: {len(critique.issues)}",
            critique.reflexion_hint.strip(),
        ]
        return WorkerTaskResult(
            task_id=task.task_id,
            worker_name=task.worker_name,
            success=True,
            output_text="\n".join(item for item in summary if item).strip(),
            output_data={
                "critique": _critique_to_payload(critique),
                "verdict": critique.verdict,
                "issue_count": len(critique.issues),
            },
            citations=citations,
            confidence=max(0.0, min(1.0, float(critique.overall_quality))),
            section_id=task.section_id,
            vote_group_id=task.vote_group_id,
            metadata={"mode": task.mode.value, **task.metadata},
        )

    return _handler


def build_sectioned_worker_envelopes(
    *,
    worker_name: str,
    objective: str,
    sections: Mapping[str, str],
    shared_constraints: Sequence[str] = (),
    expected_output_schema: Mapping[str, Any] | None = None,
    source_policy: WorkerSourcePolicy | None = None,
    budget_hints: WorkerBudgetHints | None = None,
    shared_input_payload: Mapping[str, Any] | None = None,
) -> list[WorkerTaskEnvelope]:
    """Create one worker envelope per independent section/facet."""
    envelopes: list[WorkerTaskEnvelope] = []
    for index, (section_id, section_objective) in enumerate(sections.items(), start=1):
        envelopes.append(
            WorkerTaskEnvelope(
                task_id=f"{worker_name}_{section_id}_{index}",
                worker_name=worker_name,
                objective=section_objective,
                constraints=list(shared_constraints),
                expected_output_schema=dict(expected_output_schema or {}),
                source_policy=source_policy or WorkerSourcePolicy(),
                budget_hints=budget_hints or WorkerBudgetHints(),
                input_payload=dict(shared_input_payload or {}),
                mode=WorkerExecutionMode.SECTIONING,
                section_id=section_id,
                metadata={"parent_objective": objective, "section_order": index},
            )
        )
    return envelopes


def build_self_moa_worker_envelopes(
    base_envelope: WorkerTaskEnvelope,
    *,
    replicas: int,
    vote_group_id: str | None = None,
) -> list[WorkerTaskEnvelope]:
    """Create same-model Self-MoA replicas for one base task envelope."""
    replica_count = max(1, replicas)
    group_id = vote_group_id or base_envelope.vote_group_id or f"vote_{base_envelope.task_id}"
    return [
        base_envelope.model_copy(
            deep=True,
            update={
                "task_id": f"{base_envelope.task_id}__replica_{index}",
                "mode": WorkerExecutionMode.SELF_MOA,
                "vote_group_id": group_id,
                "metadata": {
                    **base_envelope.metadata,
                    "self_moa_replica_index": index,
                    "self_moa_replicas": replica_count,
                },
            },
        )
        for index in range(replica_count)
    ]


def _search_budgets_from_hints(hints: WorkerBudgetHints) -> SearchBudgetControls:
    """Map worker budget hints to Scholar search budgets."""
    max_search_queries = 12
    max_fetch_pages = 24
    if hints.max_tokens is not None:
        max_search_queries = max(2, min(64, hints.max_tokens // 2048))
        max_fetch_pages = max(4, min(256, hints.max_tokens // 1024))
    return SearchBudgetControls(
        max_search_queries=max_search_queries,
        max_fetch_pages=max_fetch_pages,
        max_parallel_queries=3,
        max_parallel_fetches=8,
        max_depth=2,
        max_wall_time_s=hints.timeout_s or 60.0,
    )


def _coerce_worker_result(
    raw: WorkerTaskResult | Mapping[str, Any],
    task: WorkerTaskEnvelope,
) -> WorkerTaskResult:
    """Normalize raw worker payloads to `WorkerTaskResult`."""
    if isinstance(raw, WorkerTaskResult):
        result = raw
    elif isinstance(raw, Mapping):
        result = WorkerTaskResult.model_validate(dict(raw))
    else:
        result = WorkerTaskResult(
            task_id=task.task_id,
            worker_name=task.worker_name,
            success=True,
            output_text=str(raw),
            section_id=task.section_id,
            vote_group_id=task.vote_group_id,
        )

    if result.task_id != task.task_id or result.worker_name != task.worker_name:
        result = result.model_copy(
            update={
                "task_id": task.task_id,
                "worker_name": task.worker_name,
            }
        )
    if result.section_id is None and task.section_id is not None:
        result.section_id = task.section_id
    if result.vote_group_id is None and task.vote_group_id is not None:
        result.vote_group_id = task.vote_group_id
    return result


def _enforce_worker_contract(
    task: WorkerTaskEnvelope,
    result: WorkerTaskResult,
) -> WorkerTaskResult:
    """Validate worker output schema and source policy."""
    if result.success:
        schema_error = _validate_expected_output(result.output_data, task.expected_output_schema)
        if schema_error is not None:
            result.success = False
            result.error = schema_error
            result.error_type = "invalid_worker_output"

    if result.success:
        policy_error = _validate_source_policy(result.citations, task.source_policy)
        if policy_error is not None:
            result.success = False
            result.error = policy_error
            result.error_type = "source_policy_violation"

    if len(result.citations) > task.source_policy.max_citations:
        result.citations = result.citations[: task.source_policy.max_citations]
        result.warnings.append(
            f"citations truncated to max_citations={task.source_policy.max_citations}"
        )
    return result


def _validate_source_policy(
    citations: Sequence[WorkerCitation],
    policy: WorkerSourcePolicy,
) -> str | None:
    """Check that worker citations satisfy source-policy constraints."""
    if policy.require_citations and len(citations) < max(1, policy.min_citations):
        return (
            f"expected at least {max(1, policy.min_citations)} citation(s), "
            f"got {len(citations)}"
        )
    if policy.require_snippets and any(not citation.snippet.strip() for citation in citations):
        return "all citations must include non-empty snippets"

    allowed_domains = set(policy.allowed_domains)
    blocked_domains = set(policy.blocked_domains)
    for citation in citations:
        domain = citation.domain
        if blocked_domains and any(_domain_matches(domain, item) for item in blocked_domains):
            return f"blocked citation domain: {domain}"
        if allowed_domains and not any(_domain_matches(domain, item) for item in allowed_domains):
            return f"citation domain not allowed: {domain}"
    return None


def _validate_expected_output(
    output_data: Mapping[str, Any],
    expected_schema: Mapping[str, Any],
) -> str | None:
    """Validate worker `output_data` against a tiny JSON-schema subset."""
    if not expected_schema:
        return None
    try:
        schema = dict(expected_schema)
    except Exception:
        return "expected_output_schema must be a JSON object"
    if schema.get("type") == "object" and not isinstance(output_data, Mapping):
        return "output_data must be object"

    required = schema.get("required")
    if isinstance(required, list):
        missing = [
            key for key in required
            if isinstance(key, str) and key not in output_data
        ]
        if missing:
            return f"output_data missing required keys: {', '.join(missing)}"

    properties = schema.get("properties")
    if not isinstance(properties, Mapping):
        return None
    for key, nested_schema in properties.items():
        if key not in output_data or not isinstance(nested_schema, Mapping):
            continue
        nested_type = nested_schema.get("type")
        if nested_type and not _matches_schema_type(output_data[key], nested_type):
            return f"output_data.{key} must be {nested_type}"
    return None


def _matches_schema_type(value: object, expected_type: object) -> bool:
    if isinstance(expected_type, list):
        return any(_matches_schema_type(value, item) for item in expected_type)
    return {
        "object": lambda candidate: isinstance(candidate, Mapping),
        "array": lambda candidate: isinstance(candidate, list),
        "string": lambda candidate: isinstance(candidate, str),
        "integer": lambda candidate: isinstance(candidate, int) and not isinstance(candidate, bool),
        "number": lambda candidate: isinstance(candidate, int | float | Decimal)
        and not isinstance(candidate, bool),
        "boolean": lambda candidate: isinstance(candidate, bool),
        "null": lambda candidate: candidate is None,
    }.get(expected_type, lambda _candidate: True)(value)


def _domain_matches(domain: str, rule: str) -> bool:
    """Match `domain` against exact or parent-domain policy rules."""
    needle = rule.strip().lower()
    if not domain or not needle:
        return False
    return domain == needle or domain.endswith(f".{needle}")


def _draft_to_payload(draft: DraftResult) -> dict[str, Any]:
    return asdict(draft)


def _critique_to_payload(report: CritiqueReport) -> dict[str, Any]:
    return asdict(report)


def draft_from_payload(payload: Mapping[str, Any]) -> DraftResult:
    """Rehydrate ``DraftResult`` from a worker payload."""
    normalized = dict(payload)
    normalized["created_at"] = _coerce_datetime(normalized.get("created_at"))
    return DraftResult(**normalized)


def critique_from_payload(payload: Mapping[str, Any]) -> CritiqueReport:
    """Rehydrate ``CritiqueReport`` from a worker payload."""
    issues_payload = payload.get("issues")
    issues = []
    if isinstance(issues_payload, list):
        issues = [
            item if isinstance(item, CritiqueIssue) else CritiqueIssue(**dict(item))
            for item in issues_payload
            if isinstance(item, (CritiqueIssue, Mapping))
        ]
    normalized = dict(payload)
    normalized["issues"] = issues
    normalized["created_at"] = _coerce_datetime(normalized.get("created_at"))
    return CritiqueReport(**normalized)


def _coerce_optional_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return max(parsed, 0)


def _coerce_float(value: object) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, parsed)


def _coerce_datetime(value: object) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            pass
    return datetime.now(UTC)
