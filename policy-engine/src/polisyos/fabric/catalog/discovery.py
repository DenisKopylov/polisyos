"""SourceContract-backed semantic discovery and explainable dataset resolution.

This module is deliberately offline-first. The default "embedding" path uses a
deterministic hashing vector so Phase 9 can run while external LLM/embedding
capacity is reserved for legal-document processing.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal

from polisyos.fabric.connectors.contracts.source_contract import SourceContract
from polisyos.fabric.connectors.profiles.models import SourceProfile

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_STOPWORDS = {
    "a",
    "an",
    "and",
    "as",
    "at",
    "by",
    "dataset",
    "for",
    "from",
    "in",
    "into",
    "is",
    "of",
    "on",
    "or",
    "source",
    "the",
    "to",
    "with",
}
_SYNONYMS = {
    "bank": ("bank", "worldbank", "wdi"),
    "development": ("development", "wdi", "indicators"),
    "event": ("event", "stream", "jsonl"),
    "events": ("event", "stream", "jsonl"),
    "gdp": ("gdp", "gross", "domestic", "product", "macro"),
    "graph": ("graph", "graphql"),
    "indicator": ("indicator", "metric"),
    "indicators": ("indicator", "metric"),
    "json": ("json", "rest"),
    "jsonl": ("jsonl", "stream", "event"),
    "population": ("population", "demography", "unpd"),
    "sparql": ("sparql", "rdf", "linked"),
    "stream": ("stream", "event", "jsonl"),
    "unesco": ("unesco", "education"),
    "who": ("who", "health"),
    "worldbank": ("worldbank", "world", "bank", "wdi"),
}


@dataclass(frozen=True)
class DatasetCatalogVectorMetadata:
    """Metadata needed to explain and invalidate dataset discovery vectors."""

    source_contract_id: str
    source_contract_version: str
    profile_id: str
    embedding_model: str
    timestamp: str
    invalidation_policy: str
    fingerprint: str
    stale: bool = False
    stale_reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class DatasetCatalogEntry:
    """One SourceContract-backed semantic catalog document."""

    entry_id: str
    source_contract_id: str
    source_contract_version: str
    connector_id: str
    dataset_pattern: str
    profile_id: str
    title: str
    text: str
    tokens: tuple[str, ...]
    vector: tuple[float, ...]
    vector_metadata: DatasetCatalogVectorMetadata
    quality_contract_ref: str
    required_quality_checks: tuple[str, ...]
    access_classification: str
    pii_tier: str
    source_trust_tier: str
    owner: str
    reviewer: str
    profile_status: Literal["resolved", "missing"]
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class DatasetDiscoveryEvidence:
    """Evidence block attached to one ranked dataset discovery candidate."""

    source_contract_id: str
    source_contract_version: str
    profile_id: str
    profile_status: Literal["resolved", "missing"]
    quality_contract_ref: str
    required_quality_checks: tuple[str, ...]
    access_classification: str
    pii_tier: str
    source_trust_tier: str
    owner: str
    reviewer: str
    supporting_tokens: tuple[str, ...]
    score_breakdown: dict[str, float]
    vector_metadata: DatasetCatalogVectorMetadata


@dataclass(frozen=True)
class DatasetDiscoveryCandidate:
    """Ranked NL-to-dataset candidate with contract-bound evidence."""

    rank: int
    score: float
    route: Literal["lexical_exact", "semantic", "lexical_fallback", "hybrid"]
    connector_id: str
    dataset_id: str
    source_contract_id: str
    profile_id: str
    title: str
    evidence: DatasetDiscoveryEvidence


@dataclass(frozen=True)
class DatasetResolutionPlan:
    """Explainable ranked plan for resolving natural language into datasets."""

    query: str
    route: Literal["none", "lexical_exact", "semantic", "lexical_fallback", "hybrid"]
    candidates: tuple[DatasetDiscoveryCandidate, ...]
    plan_steps: tuple[dict[str, object], ...]
    total_candidates: int
    needs_disambiguation: bool

    @property
    def best_candidate(self) -> DatasetDiscoveryCandidate | None:
        return self.candidates[0] if self.candidates else None


@dataclass(frozen=True)
class DatasetCatalogStalenessReport:
    """Current stale-vector state for the dataset semantic catalog."""

    stale_entry_ids: tuple[str, ...]
    stale_reasons_by_entry: dict[str, tuple[str, ...]]
    checked_at: str

    @property
    def has_stale_entries(self) -> bool:
        return bool(self.stale_entry_ids)


@dataclass(frozen=True)
class DatasetDiscoveryEvalCase:
    """One relevance or false-positive case for dataset discovery."""

    query: str
    expected_source_contract_id: str | None = None
    max_rank: int = 1
    max_false_positive_score: float = 0.25
    case_id: str = ""
    category: str = "relevance"
    notes: str = ""

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> DatasetDiscoveryEvalCase:
        expected = payload.get("expected_source_contract_id")
        return cls(
            query=str(payload["query"]),
            expected_source_contract_id=None if expected is None else str(expected),
            max_rank=max(1, int(payload.get("max_rank", 1))),
            max_false_positive_score=float(payload.get("max_false_positive_score", 0.25)),
            case_id=str(payload.get("case_id", "")),
            category=str(payload.get("category", "relevance") or "relevance"),
            notes=str(payload.get("notes", "")),
        )


@dataclass(frozen=True)
class DatasetDiscoveryEvalOutcome:
    """Outcome of one dataset discovery evaluation case."""

    case: DatasetDiscoveryEvalCase
    matched_source_contract_id: str | None
    matched_score: float
    matched_rank: int | None
    passed: bool
    route: str = "none"


@dataclass(frozen=True)
class DatasetDiscoveryEvalReport:
    """Compact relevance/false-positive report for dataset discovery."""

    outcomes: tuple[DatasetDiscoveryEvalOutcome, ...]
    benchmark_id: str = ""
    benchmark_version: str = ""

    @property
    def passed(self) -> bool:
        return all(outcome.passed for outcome in self.outcomes)

    @property
    def total_cases(self) -> int:
        return len(self.outcomes)

    @property
    def passed_cases(self) -> int:
        return sum(1 for outcome in self.outcomes if outcome.passed)

    @property
    def pass_rate(self) -> float:
        return 1.0 if not self.outcomes else self.passed_cases / len(self.outcomes)

    @property
    def false_positive_failures(self) -> int:
        return sum(
            1
            for outcome in self.outcomes
            if outcome.case.expected_source_contract_id is None and not outcome.passed
        )


@dataclass(frozen=True)
class DatasetDiscoveryBenchmarkPack:
    """Reusable eval pack with explicit relevance and false-positive thresholds."""

    benchmark_id: str
    benchmark_version: str
    cases: tuple[DatasetDiscoveryEvalCase, ...]
    minimum_pass_rate: float = 1.0
    maximum_false_positive_failures: int = 0
    metadata: dict[str, object] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> DatasetDiscoveryBenchmarkPack:
        return cls(
            benchmark_id=str(payload.get("benchmark_id") or "fabric_discovery_eval"),
            benchmark_version=str(payload.get("benchmark_version") or "1"),
            cases=tuple(
                DatasetDiscoveryEvalCase.from_mapping(item)
                for item in payload.get("cases", ())
            ),
            minimum_pass_rate=float(payload.get("minimum_pass_rate", 1.0)),
            maximum_false_positive_failures=max(
                0,
                int(payload.get("maximum_false_positive_failures", 0)),
            ),
            metadata=dict(payload.get("metadata", {})),
        )

    def meets_thresholds(self, report: DatasetDiscoveryEvalReport) -> bool:
        return (
            report.pass_rate >= self.minimum_pass_rate
            and report.false_positive_failures <= self.maximum_false_positive_failures
        )


class SemanticDatasetCatalog:
    """SourceContract-backed semantic index for NL-to-dataset discovery."""

    def __init__(
        self,
        contracts: Sequence[SourceContract],
        *,
        profiles: Sequence[SourceProfile] = (),
        embedding_model: str = "hashing-bow-dataset-v1",
        dimensions: int = 96,
        disambiguation_margin: float = 0.08,
        confidence_threshold: float = 0.35,
    ) -> None:
        self._embedding_model = embedding_model
        self._dimensions = max(16, int(dimensions))
        self._profiles_by_id = {profile.profile_id: profile for profile in profiles}
        self._entries: dict[str, DatasetCatalogEntry] = {}
        self._stale_reasons: dict[str, tuple[str, ...]] = {}
        self._disambiguation_margin = max(0.0, float(disambiguation_margin))
        self._confidence_threshold = max(0.0, float(confidence_threshold))
        self.refresh(contracts, profiles=profiles)

    @property
    def embedding_model(self) -> str:
        return self._embedding_model

    def list_entries(self) -> tuple[DatasetCatalogEntry, ...]:
        return tuple(sorted(self._entries.values(), key=lambda item: item.entry_id))

    def get_entry(self, source_contract_id: str) -> DatasetCatalogEntry | None:
        return self._entries.get(source_contract_id)

    def mark_stale(self, source_contract_id: str, reason: str) -> None:
        """Mark one entry stale; default searches filter stale vectors."""

        if source_contract_id not in self._entries:
            raise KeyError(f"unknown source contract id: {source_contract_id}")
        reasons = tuple(
            dict.fromkeys((*self._stale_reasons.get(source_contract_id, ()), str(reason)))
        )
        self._stale_reasons[source_contract_id] = reasons
        self._entries[source_contract_id] = self._with_stale_metadata(
            self._entries[source_contract_id],
            stale=True,
            stale_reasons=reasons,
        )

    def staleness_report(self) -> DatasetCatalogStalenessReport:
        return DatasetCatalogStalenessReport(
            stale_entry_ids=tuple(sorted(self._stale_reasons)),
            stale_reasons_by_entry={
                key: tuple(value) for key, value in sorted(self._stale_reasons.items())
            },
            checked_at=datetime.now(UTC).isoformat(),
        )

    def refresh(
        self,
        contracts: Sequence[SourceContract],
        *,
        profiles: Sequence[SourceProfile] | None = None,
    ) -> list[str]:
        """Rebuild changed entries and return invalidated SourceContract ids."""

        if profiles is not None:
            self._profiles_by_id = {profile.profile_id: profile for profile in profiles}
        changed: list[str] = []
        next_entries: dict[str, DatasetCatalogEntry] = {}
        for contract in sorted(contracts, key=lambda item: item.id):
            profile = self._profiles_by_id.get(contract.source.profile_id)
            fingerprint = _source_contract_fingerprint(contract, profile)
            existing = self._entries.get(contract.id)
            if existing is None or existing.vector_metadata.fingerprint != fingerprint:
                changed.append(contract.id)
            next_entries[contract.id] = self._build_entry(
                contract,
                profile=profile,
                fingerprint=fingerprint,
            )
        self._entries = next_entries
        self._stale_reasons = {
            entry_id: reasons
            for entry_id, reasons in self._stale_reasons.items()
            if entry_id in self._entries and entry_id not in changed
        }
        for entry_id, reasons in self._stale_reasons.items():
            self._entries[entry_id] = self._with_stale_metadata(
                self._entries[entry_id],
                stale=True,
                stale_reasons=reasons,
            )
        return changed

    def search(
        self,
        query: str,
        *,
        limit: int = 5,
        allow_stale: bool = False,
        min_score: float = 0.12,
    ) -> DatasetResolutionPlan:
        """Resolve natural language into ranked dataset candidates."""

        normalized = query.strip().lower()
        if not normalized:
            return DatasetResolutionPlan(
                query=query,
                route="none",
                candidates=(),
                plan_steps=(
                    {
                        "step": "validate_query",
                        "route": "none",
                        "status": "empty_query",
                        "candidate_count": 0,
                    },
                ),
                total_candidates=len(self._entries),
                needs_disambiguation=True,
            )

        query_tokens = tuple(_normalize_tokens(normalized))
        query_vector = _vectorize(query_tokens, dimensions=self._dimensions)
        scored: list[tuple[float, float, float, float, DatasetCatalogEntry, tuple[str, ...]]] = []
        stale_filtered = 0
        for entry in self.list_entries():
            if entry.vector_metadata.stale and not allow_stale:
                stale_filtered += 1
                continue
            exact_score = _exact_match_score(normalized, entry)
            semantic_score = _cosine_similarity(query_vector, entry.vector) if query_tokens else 0.0
            supporting_tokens = tuple(sorted(set(query_tokens) & set(entry.tokens)))[:12]
            coverage = len(supporting_tokens) / max(1, len(set(query_tokens)))
            lexical_score = _lexical_similarity(set(query_tokens), set(entry.tokens))
            combined = max(
                exact_score,
                min(1.0, semantic_score * 0.68 + coverage * 0.20 + lexical_score * 0.12),
            )
            if combined < min_score and exact_score <= 0.0:
                continue
            scored.append(
                (
                    combined,
                    semantic_score,
                    coverage,
                    lexical_score,
                    entry,
                    supporting_tokens,
                )
            )

        scored.sort(key=lambda item: (-item[0], item[4].source_contract_id))
        candidates = tuple(
            self._candidate_from_score(
                rank=index + 1,
                combined_score=combined,
                semantic_score=semantic_score,
                coverage=coverage,
                lexical_score=lexical_score,
                entry=entry,
                supporting_tokens=supporting_tokens,
                route=_route_for_score(normalized, entry, semantic_score, lexical_score),
            )
            for index, (
                combined,
                semantic_score,
                coverage,
                lexical_score,
                entry,
                supporting_tokens,
            ) in enumerate(scored[: max(1, int(limit))])
        )
        route = _plan_route(candidates)
        plan_steps = (
            {
                "step": "offline_embedding_rank",
                "route": "semantic",
                "status": "matched" if scored else "no_match",
                "embedding_model": self._embedding_model,
                "candidate_count": len(scored),
                "llm_calls": 0,
            },
            {
                "step": "lexical_fallback",
                "route": "lexical",
                "status": "available",
                "candidate_count": len(scored),
            },
            {
                "step": "stale_filter",
                "route": "governance",
                "status": "filtered" if stale_filtered else "clear",
                "candidate_count": stale_filtered,
            },
        )
        return DatasetResolutionPlan(
            query=query,
            route=route,
            candidates=candidates,
            plan_steps=plan_steps,
            total_candidates=len(self._entries),
            needs_disambiguation=self._needs_disambiguation(candidates),
        )

    def resolve(
        self,
        query: str,
        *,
        max_candidates: int = 5,
        allow_stale: bool = False,
    ) -> DatasetResolutionPlan:
        """Alias for NL-to-dataset planning."""

        return self.search(query, limit=max_candidates, allow_stale=allow_stale)

    def evaluate(
        self,
        cases: Sequence[DatasetDiscoveryEvalCase],
        *,
        limit: int = 5,
        benchmark_id: str = "",
        benchmark_version: str = "",
    ) -> DatasetDiscoveryEvalReport:
        outcomes: list[DatasetDiscoveryEvalOutcome] = []
        for case in cases:
            plan = self.resolve(case.query, max_candidates=limit)
            best = plan.best_candidate
            if case.expected_source_contract_id is None:
                passed = best is None or best.score <= case.max_false_positive_score
                matched_rank = None if best is None else best.rank
            else:
                matched_rank = next(
                    (
                        candidate.rank
                        for candidate in plan.candidates[: case.max_rank]
                        if candidate.source_contract_id == case.expected_source_contract_id
                    ),
                    None,
                )
                passed = matched_rank is not None
            outcomes.append(
                DatasetDiscoveryEvalOutcome(
                    case=case,
                    matched_source_contract_id=(
                        None if best is None else best.source_contract_id
                    ),
                    matched_score=0.0 if best is None else best.score,
                    matched_rank=matched_rank,
                    passed=passed,
                    route=plan.route,
                )
            )
        return DatasetDiscoveryEvalReport(
            outcomes=tuple(outcomes),
            benchmark_id=benchmark_id,
            benchmark_version=benchmark_version,
        )

    def evaluate_benchmark(
        self,
        benchmark: DatasetDiscoveryBenchmarkPack,
        *,
        limit: int = 5,
    ) -> DatasetDiscoveryEvalReport:
        return self.evaluate(
            benchmark.cases,
            limit=limit,
            benchmark_id=benchmark.benchmark_id,
            benchmark_version=benchmark.benchmark_version,
        )

    def _build_entry(
        self,
        contract: SourceContract,
        *,
        profile: SourceProfile | None,
        fingerprint: str,
    ) -> DatasetCatalogEntry:
        text = _entry_text(contract, profile)
        tokens = tuple(_normalize_tokens(text))
        metadata = DatasetCatalogVectorMetadata(
            source_contract_id=contract.id,
            source_contract_version=contract.version,
            profile_id=contract.source.profile_id,
            embedding_model=self._embedding_model,
            timestamp=datetime.now(UTC).isoformat(),
            invalidation_policy=(
                "rebuild_on_source_contract_schema_metadata_profile_quality_access_change"
            ),
            fingerprint=fingerprint,
        )
        return DatasetCatalogEntry(
            entry_id=contract.id,
            source_contract_id=contract.id,
            source_contract_version=contract.version,
            connector_id=contract.source.connector_id,
            dataset_pattern=contract.source.dataset_pattern,
            profile_id=contract.source.profile_id,
            title=contract.source.source_name or contract.id,
            text=text,
            tokens=tokens,
            vector=_vectorize(tokens, dimensions=self._dimensions),
            vector_metadata=metadata,
            quality_contract_ref=contract.quality.contract_ref,
            required_quality_checks=tuple(contract.quality.required_checks),
            access_classification=contract.security.classification,
            pii_tier=contract.security.pii_tier,
            source_trust_tier=contract.source_trust.tier,
            owner=contract.owner,
            reviewer=contract.reviewer,
            profile_status="resolved" if profile is not None else "missing",
            metadata={
                "semantics_domain": contract.semantics.domain,
                "metric_definitions": [
                    item.model_dump(mode="json") for item in contract.semantics.metric_definitions
                ],
                "canonical_ids": list(contract.semantics.canonical_ids),
                "terms_url": contract.terms.terms_url,
                "allowed_uses": list(contract.terms.allowed_uses),
                "status": contract.status,
                "refresh_frequency": contract.sla.refresh_frequency,
                "processing_guarantee": contract.processing.guarantee_value,
            },
        )

    @staticmethod
    def _with_stale_metadata(
        entry: DatasetCatalogEntry,
        *,
        stale: bool,
        stale_reasons: tuple[str, ...],
    ) -> DatasetCatalogEntry:
        metadata = DatasetCatalogVectorMetadata(
            source_contract_id=entry.vector_metadata.source_contract_id,
            source_contract_version=entry.vector_metadata.source_contract_version,
            profile_id=entry.vector_metadata.profile_id,
            embedding_model=entry.vector_metadata.embedding_model,
            timestamp=entry.vector_metadata.timestamp,
            invalidation_policy=entry.vector_metadata.invalidation_policy,
            fingerprint=entry.vector_metadata.fingerprint,
            stale=stale,
            stale_reasons=stale_reasons,
        )
        return DatasetCatalogEntry(
            entry_id=entry.entry_id,
            source_contract_id=entry.source_contract_id,
            source_contract_version=entry.source_contract_version,
            connector_id=entry.connector_id,
            dataset_pattern=entry.dataset_pattern,
            profile_id=entry.profile_id,
            title=entry.title,
            text=entry.text,
            tokens=entry.tokens,
            vector=entry.vector,
            vector_metadata=metadata,
            quality_contract_ref=entry.quality_contract_ref,
            required_quality_checks=entry.required_quality_checks,
            access_classification=entry.access_classification,
            pii_tier=entry.pii_tier,
            source_trust_tier=entry.source_trust_tier,
            owner=entry.owner,
            reviewer=entry.reviewer,
            profile_status=entry.profile_status,
            metadata=dict(entry.metadata),
        )

    def _candidate_from_score(
        self,
        *,
        rank: int,
        combined_score: float,
        semantic_score: float,
        coverage: float,
        lexical_score: float,
        entry: DatasetCatalogEntry,
        supporting_tokens: tuple[str, ...],
        route: Literal["lexical_exact", "semantic", "lexical_fallback", "hybrid"],
    ) -> DatasetDiscoveryCandidate:
        evidence = DatasetDiscoveryEvidence(
            source_contract_id=entry.source_contract_id,
            source_contract_version=entry.source_contract_version,
            profile_id=entry.profile_id,
            profile_status=entry.profile_status,
            quality_contract_ref=entry.quality_contract_ref,
            required_quality_checks=entry.required_quality_checks,
            access_classification=entry.access_classification,
            pii_tier=entry.pii_tier,
            source_trust_tier=entry.source_trust_tier,
            owner=entry.owner,
            reviewer=entry.reviewer,
            supporting_tokens=supporting_tokens,
            score_breakdown={
                "semantic": round(float(semantic_score), 6),
                "coverage": round(float(coverage), 6),
                "lexical": round(float(lexical_score), 6),
                "combined": round(float(combined_score), 6),
            },
            vector_metadata=entry.vector_metadata,
        )
        return DatasetDiscoveryCandidate(
            rank=rank,
            score=round(float(combined_score), 6),
            route=route,
            connector_id=entry.connector_id,
            dataset_id=entry.dataset_pattern,
            source_contract_id=entry.source_contract_id,
            profile_id=entry.profile_id,
            title=entry.title,
            evidence=evidence,
        )

    def _needs_disambiguation(
        self,
        candidates: tuple[DatasetDiscoveryCandidate, ...],
    ) -> bool:
        if not candidates:
            return True
        if candidates[0].score < self._confidence_threshold:
            return True
        if len(candidates) >= 2:
            return candidates[0].score - candidates[1].score < self._disambiguation_margin
        return False


def build_semantic_dataset_catalog(
    contracts: Sequence[SourceContract],
    *,
    profiles: Sequence[SourceProfile] = (),
) -> SemanticDatasetCatalog:
    """Build the Phase 9 SourceContract-backed discovery catalog."""

    return SemanticDatasetCatalog(contracts, profiles=profiles)


def _entry_text(contract: SourceContract, profile: SourceProfile | None) -> str:
    parts: list[str] = [
        contract.id,
        contract.source.connector_id,
        contract.source.dataset_pattern,
        contract.source.profile_id,
        contract.source.source_name,
        contract.source.source_organization,
        contract.source.source_url or "",
        contract.semantics.domain,
        " ".join(contract.semantics.canonical_ids),
        " ".join(
            f"{metric.metric_id} {metric.description} {metric.unit or ''} {metric.canonical_field or ''}"
            for metric in contract.semantics.metric_definitions
        ),
        contract.quality.contract_ref,
        " ".join(contract.quality.required_checks),
        contract.security.classification,
        contract.security.pii_tier,
        contract.source_trust.tier,
        contract.source_trust.calibration_status,
        contract.source_trust.rationale,
        contract.sla.refresh_frequency,
        contract.terms.terms_url or "",
        " ".join(contract.terms.allowed_uses),
        contract.processing.guarantee_value,
    ]
    if profile is not None:
        parts.extend(
            [
                profile.profile_id,
                profile.display_name,
                profile.description,
                profile.connector_family,
                profile.base_url,
                profile.source_organization,
                profile.source_url,
                profile.preferred_transport,
                profile.preferred_core_transport,
                profile.preferred_backfill_transport,
                profile.bulk_format,
                " ".join(profile.dataset_discovery_hints),
                " ".join(profile.tags),
            ]
        )
    return "\n".join(part for part in parts if part)


def _source_contract_fingerprint(
    contract: SourceContract,
    profile: SourceProfile | None,
) -> str:
    payload = {
        "source_contract": contract.model_dump(
            mode="json",
            by_alias=True,
            exclude={"created_at"},
        ),
        "content_hash": contract.content_hash,
        "profile": None if profile is None else profile.model_dump(mode="json"),
    }
    encoded = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    return hashlib.sha256(encoded).hexdigest()


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


def _hash_index(token: str, *, dimensions: int) -> int:
    digest = hashlib.sha256(token.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") % dimensions


def _vectorize(tokens: Sequence[str], *, dimensions: int) -> tuple[float, ...]:
    counts = [0.0] * dimensions
    for token in tokens:
        counts[_hash_index(token, dimensions=dimensions)] += 1.0
    magnitude = math.sqrt(sum(value * value for value in counts))
    if magnitude <= 0.0:
        return tuple(0.0 for _ in range(dimensions))
    return tuple(value / magnitude for value in counts)


def _cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right):
        raise ValueError("dataset discovery vectors must share dimensionality")
    return float(
        sum(left_value * right_value for left_value, right_value in zip(left, right, strict=False))
    )


def _lexical_similarity(query_tokens: set[str], candidate_tokens: set[str]) -> float:
    if not query_tokens or not candidate_tokens:
        return 0.0
    return len(query_tokens & candidate_tokens) / len(query_tokens | candidate_tokens)


def _exact_match_score(query: str, entry: DatasetCatalogEntry) -> float:
    exact_values = {
        entry.source_contract_id.lower(),
        entry.connector_id.lower(),
        entry.dataset_pattern.lower(),
        entry.profile_id.lower(),
        entry.title.lower(),
    }
    if query in exact_values:
        return 1.0
    if any(query in value or value in query for value in exact_values if value):
        return 0.82
    return 0.0


def _route_for_score(
    query: str,
    entry: DatasetCatalogEntry,
    semantic_score: float,
    lexical_score: float,
) -> Literal["lexical_exact", "semantic", "lexical_fallback", "hybrid"]:
    if _exact_match_score(query, entry) >= 1.0:
        return "lexical_exact"
    if semantic_score >= 0.28 and lexical_score >= 0.05:
        return "hybrid"
    if semantic_score >= lexical_score:
        return "semantic"
    return "lexical_fallback"


def _plan_route(
    candidates: tuple[DatasetDiscoveryCandidate, ...],
) -> Literal["none", "lexical_exact", "semantic", "lexical_fallback", "hybrid"]:
    if not candidates:
        return "none"
    return candidates[0].route


__all__ = [
    "DatasetCatalogEntry",
    "DatasetCatalogStalenessReport",
    "DatasetCatalogVectorMetadata",
    "DatasetDiscoveryBenchmarkPack",
    "DatasetDiscoveryCandidate",
    "DatasetDiscoveryEvalCase",
    "DatasetDiscoveryEvalOutcome",
    "DatasetDiscoveryEvalReport",
    "DatasetDiscoveryEvidence",
    "DatasetResolutionPlan",
    "SemanticDatasetCatalog",
    "build_semantic_dataset_catalog",
]
