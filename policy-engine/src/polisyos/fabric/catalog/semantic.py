"""Deterministic semantic catalog index used by metric discovery and retrieval fallback."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any, Iterable, Mapping, Sequence

from .contract import DataContract
from .providers import resolve_catalog_providers
from .source_bindings import SourceBinding

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_STOPWORDS = {
    "a",
    "an",
    "and",
    "as",
    "at",
    "by",
    "for",
    "from",
    "in",
    "into",
    "is",
    "metric",
    "of",
    "on",
    "or",
    "per",
    "the",
    "to",
    "with",
}
_SYNONYMS = {
    "employment": ("employment", "labor", "work"),
    "jobless": ("jobless", "unemployment", "labor"),
    "jobs": ("job", "employment", "labor"),
    "salary": ("salary", "wage", "income"),
    "wages": ("wage", "salary", "income"),
    "income": ("income", "salary", "wage"),
    "gross": ("gross", "gdp"),
    "gdp": ("gdp", "gross", "domestic", "product"),
    "inflation": ("inflation", "prices", "cpi"),
    "population": ("population", "people", "demography"),
    "health": ("health", "wellbeing", "outcomes"),
    "education": ("education", "school", "learning"),
    "without": ("without", "lack"),
    "work": ("work", "employment", "labor"),
}


@dataclass(frozen=True)
class SemanticVectorMetadata:
    """Metadata required to explain and invalidate semantic vectors."""

    source: str
    schema_version: str
    embedding_model: str
    timestamp: str
    invalidation_policy: str
    fingerprint: str


@dataclass(frozen=True)
class SemanticCatalogDocument:
    """One enriched metric-level document inside the semantic index."""

    metric_id: str
    text: str
    vector: tuple[float, ...]
    tokens: tuple[str, ...]
    vector_metadata: SemanticVectorMetadata
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class SemanticSearchMatch:
    """Semantic match result with explainable evidence."""

    metric_id: str
    score: float
    supporting_tokens: tuple[str, ...]
    vector_metadata: SemanticVectorMetadata
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class SemanticEvaluationCase:
    """One semantic catalog evaluation prompt."""

    query: str
    expected_metric_id: str | None = None
    max_rank: int = 1
    max_false_positive_score: float = 0.25
    case_id: str = ""
    category: str = "relevance"
    notes: str = ""


@dataclass(frozen=True)
class SemanticEvaluationOutcome:
    """Outcome of one semantic evaluation case."""

    case: SemanticEvaluationCase
    matched_metric_id: str | None
    matched_score: float
    matched_rank: int | None
    passed: bool
    supporting_tokens: tuple[str, ...] = ()


@dataclass(frozen=True)
class SemanticEvaluationReport:
    """Compact report for semantic relevance and false-positive checks."""

    outcomes: tuple[SemanticEvaluationOutcome, ...]
    benchmark_id: str = ""
    benchmark_version: str = ""

    @property
    def passed(self) -> bool:
        return all(item.passed for item in self.outcomes)

    @property
    def passed_cases(self) -> int:
        return sum(1 for item in self.outcomes if item.passed)

    @property
    def total_cases(self) -> int:
        return len(self.outcomes)

    @property
    def failed_cases(self) -> int:
        return self.total_cases - self.passed_cases

    @property
    def pass_rate(self) -> float:
        if not self.outcomes:
            return 1.0
        return self.passed_cases / self.total_cases

    @property
    def expected_recall(self) -> float:
        expected_cases = [
            item for item in self.outcomes if item.case.expected_metric_id is not None
        ]
        if not expected_cases:
            return 1.0
        passed_expected = sum(1 for item in expected_cases if item.passed)
        return passed_expected / len(expected_cases)

    @property
    def false_positive_failures(self) -> int:
        return sum(
            1
            for item in self.outcomes
            if item.case.expected_metric_id is None and not item.passed
        )

    @property
    def category_summary(self) -> dict[str, dict[str, int]]:
        summary: dict[str, dict[str, int]] = {}
        for item in self.outcomes:
            category = item.case.category or "relevance"
            bucket = summary.setdefault(category, {"total": 0, "passed": 0})
            bucket["total"] += 1
            if item.passed:
                bucket["passed"] += 1
        return summary

    def meets_thresholds(self, benchmark: "SemanticEvaluationBenchmarkPack") -> bool:
        return (
            self.pass_rate >= benchmark.minimum_pass_rate
            and self.expected_recall >= benchmark.minimum_expected_recall
            and self.false_positive_failures <= benchmark.maximum_false_positive_failures
        )


@dataclass(frozen=True)
class SemanticEvaluationBenchmarkPack:
    """Reusable semantic benchmark pack with explicit quality thresholds."""

    benchmark_id: str
    benchmark_version: str
    cases: tuple[SemanticEvaluationCase, ...]
    minimum_pass_rate: float = 1.0
    minimum_expected_recall: float = 1.0
    maximum_false_positive_failures: int = 0
    metadata: dict[str, object] = field(default_factory=dict)

    @classmethod
    def from_mapping(
        cls,
        payload: Mapping[str, Any],
    ) -> "SemanticEvaluationBenchmarkPack":
        case_payloads = payload.get("cases", ())
        cases = tuple(
            SemanticEvaluationCase(
                query=str(item["query"]),
                expected_metric_id=(
                    None
                    if item.get("expected_metric_id") is None
                    else str(item.get("expected_metric_id"))
                ),
                max_rank=max(1, int(item.get("max_rank", 1))),
                max_false_positive_score=float(item.get("max_false_positive_score", 0.25)),
                case_id=str(item.get("case_id", "")),
                category=str(item.get("category", "relevance") or "relevance"),
                notes=str(item.get("notes", "")),
            )
            for item in case_payloads
        )
        return cls(
            benchmark_id=str(payload.get("benchmark_id") or "semantic_catalog_benchmark"),
            benchmark_version=str(payload.get("benchmark_version") or "1"),
            cases=cases,
            minimum_pass_rate=float(payload.get("minimum_pass_rate", 1.0)),
            minimum_expected_recall=float(payload.get("minimum_expected_recall", 1.0)),
            maximum_false_positive_failures=max(
                0, int(payload.get("maximum_false_positive_failures", 0))
            ),
            metadata=dict(payload.get("metadata", {})),
        )

    @classmethod
    def from_path(
        cls,
        path: str | Path,
    ) -> "SemanticEvaluationBenchmarkPack":
        payload = json.loads(Path(path).read_text("utf-8"))
        return cls.from_mapping(payload)


def _canonical_contract_payload(contract: DataContract) -> dict[str, object]:
    return contract.model_dump(mode="json")


def _resolve_profile_payloads(
    bindings: Sequence[SourceBinding],
    *,
    source_profiles: Any | None = None,
) -> dict[str, dict[str, object]]:
    if not any(binding.profile_id for binding in bindings):
        return {}

    registry = resolve_catalog_providers(
        source_profiles=source_profiles,
    ).source_profiles
    payloads: dict[str, dict[str, object]] = {}
    for binding in bindings:
        if not binding.profile_id or binding.profile_id in payloads:
            continue
        profile = registry.get(binding.profile_id)
        if profile is not None:
            payloads[binding.profile_id] = profile.model_dump(mode="json")
    return payloads


def _canonical_binding_payload(
    bindings: Sequence[SourceBinding],
    *,
    profile_payloads: dict[str, dict[str, object]],
) -> list[dict[str, object]]:
    payload = [binding.model_dump(mode="json") for binding in bindings]
    for item in payload:
        profile_id = str(item.get("profile_id") or "")
        if profile_id and profile_id in profile_payloads:
            item["profile"] = profile_payloads[profile_id]
    payload.sort(
        key=lambda item: (
            str(item.get("connector_id") or ""),
            str(item.get("dataset_id") or ""),
            str(item.get("profile_id") or ""),
        )
    )
    return payload


def _metric_fingerprint(contract: DataContract, bindings: Sequence[SourceBinding]) -> str:
    profile_payloads = _resolve_profile_payloads(bindings)
    payload = {
        "contract": _canonical_contract_payload(contract),
        "bindings": _canonical_binding_payload(
            bindings,
            profile_payloads=profile_payloads,
        ),
    }
    encoded = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _hash_index(token: str, *, dimensions: int) -> int:
    digest = hashlib.sha256(token.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") % dimensions


def _normalize_tokens(text: str) -> list[str]:
    raw_tokens = [match.group(0) for match in _TOKEN_RE.finditer(text.lower())]
    tokens: list[str] = []
    for token in raw_tokens:
        if token in _STOPWORDS:
            continue
        tokens.append(token)
        for synonym in _SYNONYMS.get(token, ()):
            if synonym not in tokens:
                tokens.append(synonym)
    return tokens


def _vectorize(tokens: Iterable[str], *, dimensions: int) -> tuple[float, ...]:
    counts = [0.0] * dimensions
    for token in tokens:
        counts[_hash_index(token, dimensions=dimensions)] += 1.0
    magnitude = math.sqrt(sum(value * value for value in counts))
    if magnitude <= 0.0:
        return tuple(0.0 for _ in range(dimensions))
    return tuple(value / magnitude for value in counts)


def _cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right):
        raise ValueError("semantic vectors must share the same dimensionality")
    return float(sum(l * r for l, r in zip(left, right)))


def _binding_profile_context(bindings: Sequence[SourceBinding]) -> dict[str, dict[str, object]]:
    return _resolve_profile_payloads(bindings)


def _profile_capability_tokens(profile_payload: dict[str, object]) -> list[str]:
    capability_bits: list[str] = []
    for key in (
        "connector_family",
        "preferred_transport",
        "preferred_core_transport",
        "preferred_backfill_transport",
        "bulk_format",
        "source_organization",
    ):
        value = str(profile_payload.get(key) or "").strip()
        if value:
            capability_bits.append(value)
    for key in (
        "supports_async_fetch",
        "supports_async_large_responses",
        "schema_preflight",
        "supports_content_constraints",
        "supports_availability_constraints",
    ):
        if bool(profile_payload.get(key)):
            capability_bits.append(key.replace("_", " "))
    capability_bits.extend(str(item) for item in profile_payload.get("tags", []) if str(item).strip())
    capability_bits.extend(
        str(item) for item in profile_payload.get("dataset_discovery_hints", []) if str(item).strip()
    )
    return capability_bits


def _enriched_metric_text(contract: DataContract, bindings: Sequence[SourceBinding]) -> str:
    lines = [
        contract.metric_id,
        contract.display_name,
        contract.description,
        contract.display_name,
        contract.description,
        contract.unit or "",
        contract.source_system,
        contract.source_table or "",
        contract.source_column or "",
        " ".join(contract.aliases),
        " ".join(contract.tags),
        " ".join(contract.dimensions),
        contract.jurisdiction or "",
    ]
    connector_ids: list[str] = []
    dataset_ids: list[str] = []
    profile_ids: list[str] = []
    enrichment_bits: list[str] = []
    profile_payloads = _binding_profile_context(bindings)
    for binding in bindings:
        connector_ids.append(binding.connector_id)
        dataset_ids.append(binding.dataset_id)
        if binding.profile_id:
            profile_ids.append(binding.profile_id)
        enrichment_bits.extend(binding.aliases)
        enrichment_bits.extend(binding.tags)
        enrichment_bits.extend(binding.metadata.keys())
        enrichment_bits.extend(str(value) for value in binding.metadata.values())
        enrichment_bits.extend(binding.filters_template.keys())
        enrichment_bits.extend(
            value for values in binding.filters_template.values() for value in values
        )
        if binding.profile_id and binding.profile_id in profile_payloads:
            profile_payload = profile_payloads[binding.profile_id]
            enrichment_bits.extend(
                part
                for part in (
                    str(profile_payload.get("display_name") or ""),
                    str(profile_payload.get("description") or ""),
                    str(profile_payload.get("source_url") or ""),
                )
                if part
            )
            enrichment_bits.extend(_profile_capability_tokens(profile_payload))
    lines.extend(connector_ids)
    lines.extend(dataset_ids)
    lines.extend(profile_ids)
    lines.append(" ".join(enrichment_bits))
    return "\n".join(part for part in lines if part)


class SemanticCatalogIndex:
    """Small deterministic vector index with explicit invalidation semantics."""

    def __init__(
        self,
        contracts: Sequence[DataContract],
        bindings: Sequence[SourceBinding] | None = None,
        *,
        embedding_model: str = "hashing-bow-v1",
        dimensions: int = 96,
    ) -> None:
        self._embedding_model = embedding_model
        self._dimensions = max(16, dimensions)
        self._documents: dict[str, SemanticCatalogDocument] = {}
        self._bindings_by_metric: dict[str, list[SourceBinding]] = defaultdict(list)
        self.refresh(contracts, bindings or [])

    @property
    def embedding_model(self) -> str:
        return self._embedding_model

    def document(self, metric_id: str) -> SemanticCatalogDocument | None:
        return self._documents.get(metric_id)

    def refresh(
        self,
        contracts: Sequence[DataContract],
        bindings: Sequence[SourceBinding] | None = None,
    ) -> list[str]:
        """Rebuild only stale metric documents and return invalidated metric ids."""

        current_bindings: dict[str, list[SourceBinding]] = defaultdict(list)
        for binding in bindings or []:
            current_bindings[binding.metric_id].append(binding)
        self._bindings_by_metric = current_bindings

        changed: list[str] = []
        next_documents: dict[str, SemanticCatalogDocument] = {}
        for contract in contracts:
            metric_bindings = tuple(current_bindings.get(contract.metric_id, ()))
            fingerprint = _metric_fingerprint(contract, metric_bindings)
            existing = self._documents.get(contract.metric_id)
            if existing is None or existing.vector_metadata.fingerprint != fingerprint:
                changed.append(contract.metric_id)
            next_documents[contract.metric_id] = self._build_document(
                contract,
                metric_bindings,
                fingerprint=fingerprint,
            )
        self._documents = next_documents
        return changed

    def search(
        self,
        query: str,
        *,
        limit: int = 10,
        min_score: float = 0.2,
    ) -> list[SemanticSearchMatch]:
        normalized = query.strip().lower()
        if not normalized:
            return []
        query_tokens = _normalize_tokens(normalized)
        if not query_tokens:
            return []
        query_vector = _vectorize(query_tokens, dimensions=self._dimensions)
        query_token_set = set(query_tokens)
        matches: list[SemanticSearchMatch] = []
        for document in self._documents.values():
            score = _cosine_similarity(query_vector, document.vector)
            support = tuple(sorted(query_token_set & set(document.tokens)))
            if score < min_score or not support:
                continue
            matches.append(
                SemanticSearchMatch(
                    metric_id=document.metric_id,
                    score=score,
                    supporting_tokens=support[:8],
                    vector_metadata=document.vector_metadata,
                    metadata=dict(document.metadata),
                )
            )
        matches.sort(key=lambda item: (-item.score, item.metric_id))
        return matches[: max(1, limit)]

    def evaluate(
        self,
        cases: Sequence[SemanticEvaluationCase],
        *,
        limit: int = 5,
        benchmark_id: str = "",
        benchmark_version: str = "",
    ) -> SemanticEvaluationReport:
        outcomes: list[SemanticEvaluationOutcome] = []
        for case in cases:
            matches = self.search(case.query, limit=limit, min_score=0.0)
            best = matches[0] if matches else None
            if case.expected_metric_id is None:
                passed = best is None or best.score <= float(case.max_false_positive_score)
                matched_rank = None if best is None else 1
            else:
                matched_rank = next(
                    (
                        index + 1
                        for index, match in enumerate(matches[: max(1, case.max_rank)])
                        if match.metric_id == case.expected_metric_id
                    ),
                    None,
                )
                passed = matched_rank is not None
            outcomes.append(
                SemanticEvaluationOutcome(
                    case=case,
                    matched_metric_id=None if best is None else best.metric_id,
                    matched_score=0.0 if best is None else best.score,
                    matched_rank=matched_rank,
                    passed=passed,
                    supporting_tokens=() if best is None else best.supporting_tokens,
                )
            )
        return SemanticEvaluationReport(
            outcomes=tuple(outcomes),
            benchmark_id=benchmark_id,
            benchmark_version=benchmark_version,
        )

    def evaluate_benchmark(
        self,
        benchmark: SemanticEvaluationBenchmarkPack,
        *,
        limit: int = 5,
    ) -> SemanticEvaluationReport:
        return self.evaluate(
            benchmark.cases,
            limit=limit,
            benchmark_id=benchmark.benchmark_id,
            benchmark_version=benchmark.benchmark_version,
        )

    def _build_document(
        self,
        contract: DataContract,
        bindings: Sequence[SourceBinding],
        *,
        fingerprint: str,
    ) -> SemanticCatalogDocument:
        text = _enriched_metric_text(contract, bindings)
        tokens = tuple(_normalize_tokens(text))
        connector_ids = sorted({binding.connector_id for binding in bindings})
        dataset_ids = sorted({binding.dataset_id for binding in bindings})
        profile_ids = sorted(
            {binding.profile_id for binding in bindings if binding.profile_id}
        )
        profile_payloads = _binding_profile_context(bindings)
        vector_metadata = SemanticVectorMetadata(
            source=",".join(connector_ids) or contract.source_system,
            schema_version="catalog-semantic-v1",
            embedding_model=self._embedding_model,
            timestamp=datetime.now(timezone.utc).isoformat(),
            invalidation_policy="rebuild_on_contract_or_binding_change",
            fingerprint=fingerprint,
        )
        return SemanticCatalogDocument(
            metric_id=contract.metric_id,
            text=text,
            vector=_vectorize(tokens, dimensions=self._dimensions),
            tokens=tokens,
            vector_metadata=vector_metadata,
            metadata={
                "connector_ids": connector_ids,
                "dataset_ids": dataset_ids,
                "profile_ids": profile_ids,
                "schema_description": ".".join(
                    part for part in (contract.source_system, contract.source_table, contract.source_column) if part
                ),
                "metadata_enrichment": {
                    "contract_aliases": list(contract.aliases),
                    "contract_tags": list(contract.tags),
                    "binding_aliases": sorted({alias for binding in bindings for alias in binding.aliases}),
                    "binding_tags": sorted({tag for binding in bindings for tag in binding.tags}),
                    "binding_metadata_keys": sorted(
                        {key for binding in bindings for key in binding.metadata}
                    ),
                    "binding_metadata_values": sorted(
                        {str(value) for binding in bindings for value in binding.metadata.values() if str(value).strip()}
                    ),
                    "profile_display_names": sorted(
                        {
                            str(payload.get("display_name") or profile_id)
                            for profile_id, payload in profile_payloads.items()
                        }
                    ),
                    "profile_descriptions": {
                        profile_id: str(payload.get("description") or "")
                        for profile_id, payload in sorted(profile_payloads.items())
                    },
                    "profile_capabilities": {
                        profile_id: _profile_capability_tokens(payload)
                        for profile_id, payload in sorted(profile_payloads.items())
                    },
                },
            },
        )


__all__ = [
    "SemanticCatalogDocument",
    "SemanticEvaluationBenchmarkPack",
    "SemanticEvaluationCase",
    "SemanticEvaluationOutcome",
    "SemanticEvaluationReport",
    "SemanticCatalogIndex",
    "SemanticSearchMatch",
    "SemanticVectorMetadata",
]
