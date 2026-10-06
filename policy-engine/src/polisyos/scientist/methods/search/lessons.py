"""CAS-backed lesson registry for funnel failures and transfer-aware reuse."""

from __future__ import annotations

import hashlib
import os
import re
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from enum import Enum
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from polisyos.core.artifacts.manifest import ArtifactRef, InputRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.ir import FailureSeverity, TypedFailureCard
from polisyos.scientist.methods.autotune.models import default_search_registry_root
from polisyos.scientist.methods.search.transfer_context import (
    TransferAuditHop,
    TransferContext,
    TransferPolicy,
    build_transfer_hop,
    compute_provenance_weight,
    resolve_transfer_context,
)

_LESSON_CARD_KIND = "scientist.search.lesson_card"
_LESSON_INDEX_KIND = "scientist.search.lesson_index"
_LESSON_CARD_SCHEMA = SchemaInfo(name="polisyos.scientist.search.LessonCard", version="1.0")
_LESSON_INDEX_SCHEMA = SchemaInfo(
    name="polisyos.scientist.search.LessonIndexSnapshot",
    version="1.0",
)
_WHITESPACE_RE = re.compile(r"\s+")


class LessonKind(str, Enum):
    """Lesson kind public type."""

    FAILURE = "failure"
    SUCCESS = "success"
    OPPORTUNITY = "opportunity"


class LessonTrustLevel(str, Enum):
    """Lesson trust level public type."""

    LOCAL = "local"
    TRANSFERRED = "transferred"
    LOW_CONFIDENCE = "low_confidence"


class LessonCard(BaseModel):
    """Immutable lesson card stored in CAS."""

    model_config = ConfigDict(extra="forbid")

    lesson_id: str = Field(default_factory=lambda: uuid4().hex)
    schema_version: str = Field(default="1.0", pattern=r"^\d+\.\d+$")
    kind: LessonKind
    summary: str = Field(min_length=1)
    failure_type: str = Field(min_length=1)
    stage_name: str = Field(min_length=1)
    fidelity_level: int = Field(ge=0)
    candidate_hash: str = Field(min_length=1)
    source_run_id: str = Field(min_length=1)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    trust_level: LessonTrustLevel = LessonTrustLevel.LOCAL
    task_family: str = Field(default="policy", min_length=1)
    domain: str = Field(default="general", min_length=1)
    provenance_weight: float = Field(default=1.0, ge=0.0, le=1.0)
    last_accessed_at: datetime | None = None
    transfer_chain: list[TransferAuditHop] = Field(default_factory=list)
    origin_run_id: str | None = None
    origin_domain: str | None = None
    origin_tenant_hash: str | None = None
    tags: list[str] = Field(default_factory=list)
    remediation_hint: str | None = None
    mutation_hints: list[str] = Field(default_factory=list)
    anti_patterns: list[str] = Field(default_factory=list)
    failure_card_refs: list[ArtifactRef] = Field(default_factory=list)
    trace_refs: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class LessonQuery(BaseModel):
    """Query filters for lesson retrieval."""

    model_config = ConfigDict(extra="forbid")

    failure_type: str | None = None
    stage_name: str | None = None
    fidelity_level: int | None = Field(default=None, ge=0)
    tags: list[str] = Field(default_factory=list)
    candidate_hash: str | None = None
    source_run_id: str | None = None
    task_family: str | None = None
    domain: str | None = None
    tenant_hash: str | None = None
    trust_levels: list[LessonTrustLevel] = Field(default_factory=list)
    min_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    min_tag_overlap: int = Field(default=1, ge=0, le=50)
    limit: int = Field(default=10, ge=1, le=100)
    as_of: datetime | None = None


class LessonIndexEntry(BaseModel):
    """Mutable registry index entry for deduped lessons."""

    model_config = ConfigDict(extra="forbid")

    lesson_id: str
    artifact_ref: ArtifactRef
    normalized_signature: str
    occurrence_count: int = Field(default=1, ge=1)
    first_seen: datetime
    last_seen: datetime
    last_accessed_at: datetime | None = None
    invalidated: bool = False
    invalidation_reason: str | None = None
    tags: list[str] = Field(default_factory=list)
    card_refs: list[ArtifactRef] = Field(default_factory=list)
    kind: LessonKind
    summary: str
    failure_type: str
    stage_name: str
    fidelity_level: int = Field(ge=0)
    candidate_hash: str
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    trust_level: LessonTrustLevel = LessonTrustLevel.LOCAL
    task_family: str = Field(default="policy", min_length=1)
    domain: str = Field(default="general", min_length=1)
    provenance_weight: float = Field(default=1.0, ge=0.0, le=1.0)
    transfer_chain: list[TransferAuditHop] = Field(default_factory=list)
    origin_run_id: str | None = None
    origin_domain: str | None = None
    origin_tenant_hash: str | None = None
    remediation_hint: str | None = None


class LessonIndexSnapshot(BaseModel):
    """Serializable snapshot of the lesson registry index."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(default="1.0", pattern=r"^\d+\.\d+$")
    snapshot_created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    task_family: str = Field(default="policy", min_length=1)
    domain: str = Field(default="general", min_length=1)
    entries: list[LessonIndexEntry] = Field(default_factory=list)


class LessonPattern(BaseModel):
    """Compact lesson pattern used by reports and heuristics."""

    model_config = ConfigDict(extra="forbid")

    lesson_id: str
    artifact_ref: ArtifactRef
    occurrence_count: int = Field(ge=1)
    kind: LessonKind
    summary: str
    failure_type: str
    stage_name: str
    fidelity_level: int = Field(ge=0)
    confidence: float = Field(ge=0.0, le=1.0)
    trust_level: LessonTrustLevel
    task_family: str = Field(default="policy", min_length=1)
    domain: str = Field(default="general", min_length=1)
    provenance_weight: float = Field(default=1.0, ge=0.0, le=1.0)
    tags: list[str] = Field(default_factory=list)
    remediation_hint: str | None = None
    last_seen: datetime
    last_accessed_at: datetime | None = None


def _normalize_text(value: str) -> str:
    return _WHITESPACE_RE.sub(" ", value.strip().lower())[:500]


def _normalized_signature(card: LessonCard) -> str:
    tags = sorted({tag.strip().lower() for tag in card.tags if tag.strip()})
    material = "|".join(
        [
            card.kind.value,
            card.failure_type.strip().lower(),
            card.stage_name.strip().lower(),
            card.task_family.strip().lower(),
            card.domain.strip().lower(),
            _normalize_text(card.summary),
            _normalize_text(card.remediation_hint or ""),
            ",".join(tags),
        ]
    )
    return material[:1024]


def persist_lesson_card(
    store: FileSystemCAS,
    card: LessonCard,
    *,
    inputs: list[InputRef] | None = None,
) -> ArtifactRef:
    """Persist a reusable lesson card captured from failures, governance issues, or successful runs."""
    return store.put_json(
        card,
        PutOptions(
            kind=_LESSON_CARD_KIND,
            media_type="application/json",
            schema=_LESSON_CARD_SCHEMA,
            inputs=list(inputs or []),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )


def load_lesson_card(store: FileSystemCAS, ref: ArtifactRef | str) -> LessonCard:
    """Load lesson card."""
    return LessonCard.model_validate(from_canonical_bytes(store.get_bytes(ref)))


def lesson_from_failure_card(
    failure_card: TypedFailureCard,
    *,
    candidate_hash: str,
    stage_name: str,
    fidelity_level: int,
    source_run_id: str,
    tags: Iterable[str] | None = None,
    trace_refs: Iterable[str] | None = None,
    transfer_context: TransferContext | None = None,
) -> LessonCard:
    """Translate a typed failure card into a reusable lesson card."""

    severity = (
        failure_card.severity.value
        if isinstance(failure_card.severity, FailureSeverity)
        else str(failure_card.severity)
    )
    metadata = {"judge_name": failure_card.judge_name, "severity": severity}
    metadata.update(failure_card.metadata)
    anti_patterns = [failure_card.failure_type]
    context = transfer_context or resolve_transfer_context(run_id=source_run_id)
    return LessonCard(
        kind=LessonKind.FAILURE,
        summary=failure_card.description,
        failure_type=failure_card.failure_type,
        stage_name=stage_name,
        fidelity_level=fidelity_level,
        candidate_hash=candidate_hash,
        source_run_id=source_run_id,
        confidence=1.0 if severity == FailureSeverity.BLOCKER.value else 0.75,
        trust_level=LessonTrustLevel.LOCAL,
        task_family=context.task_family,
        domain=context.domain,
        provenance_weight=1.0,
        origin_run_id=source_run_id,
        origin_domain=context.domain,
        origin_tenant_hash=context.tenant_hash,
        tags=list(tags or []),
        remediation_hint=failure_card.remediation_hint,
        anti_patterns=anti_patterns,
        failure_card_refs=(
            [ArtifactRef.model_validate(failure_card.evidence_ref.model_dump(mode="json"))]
            if failure_card.evidence_ref is not None
            else []
        ),
        trace_refs=list(trace_refs or []),
        metadata=metadata,
    )


def success_lesson_from_outcome(
    outcome: Any,
    *,
    source_run_id: str,
    tags: Iterable[str] | None = None,
    trace_refs: Iterable[str] | None = None,
    transfer_context: TransferContext | None = None,
) -> LessonCard:
    """Build a reusable success-pattern lesson from a funnel outcome."""

    final_result = getattr(outcome, "final_result", None)
    stage_name = getattr(final_result, "stage_name", "funnel")
    fidelity_level = int(getattr(final_result, "fidelity_level", 0) or 0)
    objective_value = float(getattr(final_result, "objective_value", 0.0) or 0.0)
    final_action = str(getattr(outcome, "final_action", "complete"))
    candidate_hash = str(getattr(outcome, "candidate_hash", "unknown"))
    context = transfer_context or resolve_transfer_context(run_id=source_run_id)
    return LessonCard(
        kind=LessonKind.SUCCESS,
        summary=(
            f"Candidate reached {stage_name} with final action '{final_action}' "
            f"and objective {objective_value:.4f}."
        ),
        failure_type="success_pattern",
        stage_name=stage_name,
        fidelity_level=fidelity_level,
        candidate_hash=candidate_hash,
        source_run_id=source_run_id,
        confidence=0.8,
        trust_level=LessonTrustLevel.LOCAL,
        task_family=context.task_family,
        domain=context.domain,
        provenance_weight=1.0,
        origin_run_id=source_run_id,
        origin_domain=context.domain,
        origin_tenant_hash=context.tenant_hash,
        tags=list(tags or []),
        mutation_hints=["Preserve the intervention structure and causal assumptions."],
        trace_refs=list(trace_refs or []),
        metadata={"final_action": final_action},
    )


class LessonRegistry:
    """CAS-backed lesson registry with atomic namespaced indexes."""

    def __init__(
        self,
        root: Path | None = None,
        *,
        store: FileSystemCAS,
        transfer_policy: TransferPolicy | None = None,
    ) -> None:
        base_root = (root or (default_search_registry_root() / "lessons")).resolve()
        self._root = base_root
        self._store = store
        self._transfer_policy = transfer_policy or TransferPolicy()
        self._root.mkdir(parents=True, exist_ok=True)
        self._last_snapshot_ref: ArtifactRef | None = None

    def record(self, card: LessonCard) -> ArtifactRef:
        return self.record_local(card)

    def record_local(
        self,
        card: LessonCard,
        *,
        context: TransferContext | None = None,
    ) -> ArtifactRef:
        target = context or resolve_transfer_context(
            task_family=card.task_family,
            domain=card.domain,
            run_id=card.source_run_id,
            tenant_hash=card.origin_tenant_hash,
        )
        normalized_card = self._normalize_card(card, target_context=target)
        card_ref = persist_lesson_card(self._store, normalized_card)
        snapshot = self.index_snapshot(context=target)
        signature = _normalized_signature(normalized_card)
        now = normalized_card.created_at

        existing = next(
            (
                entry
                for entry in snapshot.entries
                if entry.normalized_signature == signature and not entry.invalidated
            ),
            None,
        )
        if existing is None:
            snapshot.entries.append(
                LessonIndexEntry(
                    lesson_id=normalized_card.lesson_id,
                    artifact_ref=card_ref,
                    normalized_signature=signature,
                    first_seen=now,
                    last_seen=now,
                    last_accessed_at=normalized_card.last_accessed_at,
                    tags=sorted(set(normalized_card.tags)),
                    card_refs=[card_ref],
                    kind=normalized_card.kind,
                    summary=normalized_card.summary,
                    failure_type=normalized_card.failure_type,
                    stage_name=normalized_card.stage_name,
                    fidelity_level=normalized_card.fidelity_level,
                    candidate_hash=normalized_card.candidate_hash,
                    confidence=normalized_card.confidence,
                    trust_level=normalized_card.trust_level,
                    task_family=normalized_card.task_family,
                    domain=normalized_card.domain,
                    provenance_weight=normalized_card.provenance_weight,
                    transfer_chain=list(normalized_card.transfer_chain),
                    origin_run_id=normalized_card.origin_run_id,
                    origin_domain=normalized_card.origin_domain,
                    origin_tenant_hash=normalized_card.origin_tenant_hash,
                    remediation_hint=normalized_card.remediation_hint,
                )
            )
        else:
            existing.occurrence_count += 1
            if now >= existing.last_seen:
                existing.artifact_ref = card_ref
                existing.last_seen = now
                for field in (
                    "summary",
                    "candidate_hash",
                    "confidence",
                    "provenance_weight",
                    "task_family",
                    "domain",
                    "origin_run_id",
                    "origin_domain",
                    "origin_tenant_hash",
                    "transfer_chain",
                    "trust_level",
                    "remediation_hint",
                    "tags",
                    "fidelity_level",
                    "stage_name",
                ):
                    setattr(existing, field, getattr(normalized_card, field))
            existing.last_accessed_at = max(
                [
                    stamp
                    for stamp in (existing.last_accessed_at, normalized_card.last_accessed_at)
                    if stamp is not None
                ],
                default=existing.last_accessed_at,
            )
            if card_ref not in existing.card_refs:
                existing.card_refs.append(card_ref)
                existing.card_refs = existing.card_refs[-20:]

        self._persist_index(snapshot, context=target)
        return card_ref

    def query(self, context: LessonQuery) -> list[LessonCard]:
        now = self._query_time(context)
        if self._should_aggregate_local_query(context):
            return self._query_local_aggregated(context, now=now)
        target = resolve_transfer_context(
            task_family=context.task_family,
            domain=context.domain,
            run_id=context.source_run_id or "unknown",
            tenant_hash=context.tenant_hash,
        ).model_copy(update={"timestamp": now})
        return self._query_local(context, target_context=target)

    def query_with_transfer(
        self,
        context: LessonQuery,
        *,
        target_context: TransferContext | None = None,
        policy: TransferPolicy | None = None,
    ) -> list[LessonCard]:
        active_target = target_context or resolve_transfer_context(
            task_family=context.task_family,
            domain=context.domain,
            run_id=context.source_run_id or "unknown",
        )
        now = self._query_time(context, target_context=target_context)
        active_target = active_target.model_copy(update={"timestamp": now})
        if self._should_use_aggregated_local_transfer_lookup(context, active_target):
            results = self._query_local_aggregated(context, now=now, policy=policy)
            return results[: context.limit]

        results = self._query_local(context, target_context=active_target, policy=policy)
        if len(results) >= context.limit:
            return results[: context.limit]

        for candidate in self.find_transfer_candidates(
            context,
            target_context=active_target,
            policy=policy,
        ):
            materialized = self.materialize_transfer(
                candidate,
                target_context=active_target,
                query=context,
                policy=policy,
            )
            if materialized is None:
                continue
            results.append(materialized)
            if len(results) >= context.limit:
                break
        return results[: context.limit]

    def find_transfer_candidates(
        self,
        context: LessonQuery,
        *,
        target_context: TransferContext,
        policy: TransferPolicy | None = None,
    ) -> list[LessonCard]:
        matches: list[tuple[float, datetime, LessonCard]] = []
        self._query_time(context, target_context=target_context)
        active_policy = policy or self._transfer_policy
        target_path = self._index_path_for_context(target_context)
        for namespace_context, path in self._iter_index_paths():
            if path == target_path:
                continue
            snapshot = self._load_index_file(path)
            for entry in self._sorted_entries(snapshot):
                if entry.invalidated:
                    continue
                source_context = TransferContext(
                    task_family=entry.task_family,
                    domain=entry.domain,
                    run_id=entry.origin_run_id or entry.lesson_id,
                    tenant_hash=namespace_context.tenant_hash,
                )
                card = load_lesson_card(self._store, entry.artifact_ref)
                normalized = self._aged_card(
                    card,
                    evidence_anchor=self._evidence_anchor(entry, card),
                    now=target_context.timestamp,
                    policy=active_policy,
                )
                if normalized is None:
                    continue
                weight = compute_provenance_weight(
                    source_context,
                    target_context,
                    created_at=self._evidence_anchor(entry, card),
                    policy=active_policy,
                )
                if weight <= 0.0:
                    continue
                if card.task_family != target_context.task_family:
                    continue
                projected = self._project_transfer(
                    normalized, target_context=target_context, weight=weight
                )
                if not self._matches_query(projected, context):
                    continue
                matches.append((weight, entry.last_seen, normalized))

        matches.sort(key=lambda item: (item[0], item[1].timestamp()), reverse=True)
        return [card for _, _, card in matches[: context.limit]]

    def materialize_transfer(
        self,
        card: LessonCard,
        *,
        target_context: TransferContext,
        query: LessonQuery | None = None,
        policy: TransferPolicy | None = None,
    ) -> LessonCard | None:
        active_policy = policy or self._transfer_policy
        if query is not None:
            self._query_time(query, target_context=target_context)
        card = self._aged_card(
            card,
            evidence_anchor=card.created_at,
            now=target_context.timestamp,
            policy=active_policy,
        )
        if card is None:
            return None
        source_context = TransferContext(
            task_family=card.task_family,
            domain=card.domain,
            run_id=card.origin_run_id or card.source_run_id,
            tenant_hash=card.origin_tenant_hash,
        )
        weight = compute_provenance_weight(
            source_context,
            target_context,
            created_at=card.created_at,
            policy=active_policy,
        )
        if weight <= 0.0:
            return None
        if card.task_family != target_context.task_family:
            return None
        projected = self._project_transfer(card, target_context=target_context, weight=weight)
        if query is not None and not self._matches_query(projected, query):
            return None

        transfer_hop = build_transfer_hop(
            source_context,
            target_context,
            provenance_weight=weight,
        )
        materialized = self._normalize_card(
            card.model_copy(
                update={
                    "lesson_id": uuid4().hex,
                    "task_family": target_context.task_family,
                    "domain": target_context.domain,
                    "trust_level": (
                        LessonTrustLevel.TRANSFERRED
                        if projected.trust_level is LessonTrustLevel.TRANSFERRED
                        else LessonTrustLevel.LOW_CONFIDENCE
                    ),
                    "provenance_weight": weight,
                    "last_accessed_at": target_context.timestamp,
                    "transfer_chain": [*card.transfer_chain, transfer_hop],
                    "metadata": {
                        **card.metadata,
                        "materialized_transfer": True,
                    },
                }
            ),
            target_context=target_context,
        )
        if query is not None and not self._matches_query(materialized, query):
            return None
        self.record_local(materialized, context=target_context)
        return materialized

    def top_patterns(
        self,
        limit: int = 5,
        *,
        context: TransferContext | None = None,
    ) -> list[LessonPattern]:
        snapshot = self.index_snapshot(context=context)
        patterns: list[LessonPattern] = []
        for entry in self._sorted_entries(snapshot):
            if entry.invalidated:
                continue
            patterns.append(
                LessonPattern(
                    lesson_id=entry.lesson_id,
                    artifact_ref=entry.artifact_ref,
                    occurrence_count=entry.occurrence_count,
                    kind=entry.kind,
                    summary=entry.summary,
                    failure_type=entry.failure_type,
                    stage_name=entry.stage_name,
                    fidelity_level=entry.fidelity_level,
                    confidence=entry.confidence,
                    trust_level=entry.trust_level,
                    task_family=entry.task_family,
                    domain=entry.domain,
                    provenance_weight=entry.provenance_weight,
                    tags=list(entry.tags),
                    remediation_hint=entry.remediation_hint,
                    last_seen=entry.last_seen,
                    last_accessed_at=entry.last_accessed_at,
                )
            )
            if len(patterns) >= limit:
                break
        return patterns

    def invalidate(self, lesson_id: str, reason: str) -> bool:
        matched = False
        for _, path in self._iter_index_paths():
            snapshot = self._load_index_file(path)
            for entry in snapshot.entries:
                if entry.lesson_id != lesson_id:
                    continue
                entry.invalidated = True
                entry.invalidation_reason = reason
                matched = True
                self._persist_index(snapshot, path=path)
                break
            if matched:
                break
        return matched

    def garbage_collect(self, ttl_days: int | None = None) -> int:
        active_ttl = max(1, int(ttl_days or self._transfer_policy.ttl_days))
        archive_cutoff = datetime.now(UTC) - timedelta(days=active_ttl * 2)
        removed = 0
        for namespace_context, path in self._iter_index_paths():
            snapshot = self._load_index_file(path)
            before = len(snapshot.entries)
            snapshot.entries = [
                self._demoted_entry(entry, ttl_days=active_ttl)
                for entry in snapshot.entries
                if not entry.invalidated and self._activity_anchor(entry) >= archive_cutoff
            ]
            delta = before - len(snapshot.entries)
            if delta:
                removed += delta
                self._persist_index(snapshot, context=namespace_context, path=path)
        return removed

    def snapshot_ref(self) -> ArtifactRef | None:
        return self._last_snapshot_ref

    def index_snapshot(
        self,
        *,
        context: TransferContext | None = None,
    ) -> LessonIndexSnapshot:
        if context is None:
            return self._aggregate_local_snapshot()
        active_context = context or resolve_transfer_context()
        path = self._index_path_for_context(active_context)
        if not path.exists():
            return LessonIndexSnapshot(
                task_family=active_context.task_family,
                domain=active_context.domain,
            )
        return self._load_index_file(path)

    def _query_local(
        self,
        query: LessonQuery,
        *,
        target_context: TransferContext,
        policy: TransferPolicy | None = None,
    ) -> list[LessonCard]:
        snapshot = self.index_snapshot(context=target_context)
        results: list[LessonCard] = []
        now = self._query_time(query, target_context=target_context)
        for entry in self._sorted_entries(snapshot):
            if entry.invalidated:
                continue
            if not self._entry_matches(entry, query):
                continue
            card = self._materialize_query_card(entry, now=now, policy=policy)
            if card is None or not self._matches_query(card, query):
                continue
            results.append(card)
            self._touch_access(entry, now=now, context=target_context)
            if len(results) >= query.limit:
                break
        return results

    def _query_local_aggregated(
        self, query: LessonQuery, *, now: datetime, policy: TransferPolicy | None = None
    ) -> list[LessonCard]:
        candidates: list[
            tuple[
                tuple[bool, float, int, float],
                LessonIndexEntry,
                LessonIndexSnapshot,
                TransferContext,
            ]
        ] = []
        for namespace_context, path in self._iter_index_paths():
            snapshot = self._load_index_file(path)
            for entry in snapshot.entries:
                if entry.invalidated:
                    continue
                if not self._entry_matches(entry, query):
                    continue
                candidates.append(
                    (
                        (
                            entry.invalidated,
                            -float(entry.provenance_weight),
                            -int(entry.occurrence_count),
                            -float(entry.last_seen.timestamp()),
                        ),
                        entry,
                        snapshot,
                        namespace_context,
                    )
                )

        results: list[LessonCard] = []
        for _, entry, snapshot, namespace_context in sorted(candidates, key=lambda item: item[0]):
            card = self._materialize_query_card(entry, now=now, policy=policy)
            if card is None or not self._matches_query(card, query):
                continue
            results.append(card)
            self._touch_access(entry, now=now, context=namespace_context)
            if len(results) >= query.limit:
                break

        return results

    def _aggregate_local_snapshot(self) -> LessonIndexSnapshot:
        snapshots = [self._load_index_file(path) for _, path in self._iter_index_paths()]
        if not snapshots:
            return LessonIndexSnapshot()
        task_families = {snapshot.task_family for snapshot in snapshots if snapshot.task_family}
        domains = {snapshot.domain for snapshot in snapshots if snapshot.domain}
        latest_created_at = max(snapshot.snapshot_created_at for snapshot in snapshots)
        return LessonIndexSnapshot(
            snapshot_created_at=latest_created_at,
            task_family=task_families.pop() if len(task_families) == 1 else "aggregated",
            domain=domains.pop() if len(domains) == 1 else "aggregated_local",
            entries=[entry for snapshot in snapshots for entry in snapshot.entries],
        )

    @staticmethod
    def _should_aggregate_local_query(query: LessonQuery) -> bool:
        return not any(
            (
                query.domain,
                query.source_run_id,
                query.tenant_hash,
            )
        )

    @classmethod
    def _should_use_aggregated_local_transfer_lookup(
        cls,
        query: LessonQuery,
        target_context: TransferContext,
    ) -> bool:
        return cls._should_aggregate_local_query(query) and (
            target_context.tenant_hash is None and target_context.domain.startswith("isolated::")
        )

    def _entry_matches(
        self,
        entry: LessonIndexEntry,
        query: LessonQuery,
    ) -> bool:
        return self._matches_query(
            entry,
            query,
            include_trust=False,
        )

    @staticmethod
    def _matches_query(
        record: LessonCard | LessonIndexEntry,
        query: LessonQuery,
        *,
        include_trust: bool = True,
    ) -> bool:
        """Apply one query predicate to an index entry or effective lesson card.

        Index entries skip source-run and trust checks because the index does
        not own the effective card status and transfer may change trust. The
        same predicate is then applied to the effective card before it is
        persisted or returned.
        """

        if query.failure_type and record.failure_type != query.failure_type:
            return False
        if query.stage_name and record.stage_name != query.stage_name:
            return False
        if query.fidelity_level is not None and record.fidelity_level != query.fidelity_level:
            return False
        if query.candidate_hash and record.candidate_hash != query.candidate_hash:
            return False
        if query.task_family and record.task_family != query.task_family:
            return False
        if query.domain and record.domain != query.domain:
            return False
        if query.source_run_id and isinstance(record, LessonCard):
            if record.source_run_id != query.source_run_id:
                return False
        if (
            include_trust
            and query.trust_levels
            and record.trust_level not in set(query.trust_levels)
        ):
            return False
        if float(record.confidence) < float(query.min_confidence):
            return False
        tag_filter = {tag for tag in query.tags if tag}
        if tag_filter:
            overlap = len(set(record.tags) & tag_filter)
            if overlap < query.min_tag_overlap:
                return False
        return True

    def _materialize_query_card(
        self,
        entry: LessonIndexEntry,
        *,
        now: datetime,
        policy: TransferPolicy | None = None,
    ) -> LessonCard | None:
        card = load_lesson_card(self._store, entry.artifact_ref)
        normalized = self._normalize_card(card)
        evidence_anchor = self._evidence_anchor(entry, normalized)
        effective = self._aged_card(
            normalized,
            evidence_anchor=evidence_anchor,
            now=now,
            policy=policy or self._transfer_policy,
        )
        if effective is None:
            return None
        return effective.model_copy(
            update={"last_accessed_at": now, "provenance_weight": entry.provenance_weight}
        )

    @staticmethod
    def _aged_card(
        card: LessonCard, *, evidence_anchor: datetime, now: datetime, policy: TransferPolicy
    ) -> LessonCard | None:
        # A persisted version cannot supply evidence before its occurrence.
        # Retention access clocks are deliberately absent from this predicate.
        if any(stamp.tzinfo is None for stamp in (card.created_at, evidence_anchor, now)):
            return None
        if card.created_at > now or evidence_anchor > now:
            return None
        if now - evidence_anchor > timedelta(days=policy.ttl_days):
            return card.model_copy(
                update={
                    "trust_level": LessonTrustLevel.LOW_CONFIDENCE,
                    "confidence": min(card.confidence, 0.5),
                }
            )
        return card

    @staticmethod
    def _query_time(
        query: LessonQuery, *, target_context: TransferContext | None = None
    ) -> datetime:
        """Bind one explicit as-of time across local and transfer routes."""
        if (
            target_context is not None
            and query.as_of is not None
            and query.as_of != target_context.timestamp
        ):
            raise ValueError("Lesson query as-of conflicts with the target context timestamp")
        now = (
            target_context.timestamp
            if target_context is not None
            else query.as_of or datetime.now(UTC)
        )
        if now.tzinfo is None:
            raise ValueError("Lesson query as-of must include a timezone")
        return now

    @staticmethod
    def _project_transfer(
        card: LessonCard, *, target_context: TransferContext, weight: float
    ) -> LessonCard:
        return card.model_copy(
            update={
                "task_family": target_context.task_family,
                "domain": target_context.domain,
                "trust_level": LessonTrustLevel.TRANSFERRED
                if weight >= 0.5 and card.trust_level is not LessonTrustLevel.LOW_CONFIDENCE
                else LessonTrustLevel.LOW_CONFIDENCE,
                "provenance_weight": weight,
            }
        )

    def _touch_access(
        self, entry: LessonIndexEntry, *, now: datetime, context: TransferContext
    ) -> None:
        """Persist tiny retention metadata at most once per UTC day, outside CAS."""
        if entry.last_accessed_at is not None and entry.last_accessed_at.date() >= now.date():
            return
        path = self._access_path(self._index_path_for_context(context), entry.lesson_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile(
            mode="w", delete=False, dir=path.parent, prefix=".access.", suffix=".tmp"
        ) as stream:
            stream.write(now.isoformat())
            stream.flush()
            os.fsync(stream.fileno())
            temporary = Path(stream.name)
        os.replace(temporary, path)
        entry.last_accessed_at = now

    @staticmethod
    def _access_path(index_path: Path, lesson_id: str) -> Path:
        name = hashlib.sha256(lesson_id.encode("utf-8")).hexdigest()
        return index_path.parent / "access" / (name + ".txt")

    def _normalize_card(
        self,
        card: LessonCard,
        *,
        target_context: TransferContext | None = None,
    ) -> LessonCard:
        active_context = target_context or resolve_transfer_context(
            task_family=card.task_family,
            domain=card.domain,
            run_id=card.source_run_id,
            tenant_hash=card.origin_tenant_hash,
        )
        update: dict[str, Any] = {
            "task_family": (
                active_context.task_family
                if target_context is not None
                else (card.task_family or active_context.task_family)
            ),
            "domain": (
                active_context.domain
                if target_context is not None
                else (card.domain or active_context.domain)
            ),
            "origin_run_id": card.origin_run_id or card.source_run_id,
            "origin_domain": (
                card.origin_domain
                or (card.domain if target_context is None else active_context.domain)
                or active_context.domain
            ),
            "origin_tenant_hash": card.origin_tenant_hash or active_context.tenant_hash,
            "provenance_weight": float(card.provenance_weight or 1.0),
        }
        if card.trust_level is LessonTrustLevel.LOCAL:
            update["provenance_weight"] = 1.0
        return card.model_copy(update=update)

    def _revalidate_transfer(
        self,
        card: LessonCard,
        query: LessonQuery,
        *,
        target_context: TransferContext,
    ) -> bool:
        if card.task_family != target_context.task_family:
            return False
        return self._matches_query(card, query, include_trust=False)

    def _demoted_entry(
        self,
        entry: LessonIndexEntry,
        *,
        ttl_days: int,
    ) -> LessonIndexEntry:
        age = max(timedelta(), datetime.now(UTC) - self._activity_anchor(entry))
        if age > timedelta(days=ttl_days):
            return entry.model_copy(update={"trust_level": LessonTrustLevel.LOW_CONFIDENCE})
        return entry

    @staticmethod
    def _activity_anchor(entry: LessonIndexEntry) -> datetime:
        """Return the usage clock used only for retention and garbage collection."""
        return max(entry.last_seen, entry.last_accessed_at or entry.last_seen)

    @staticmethod
    def _evidence_anchor(entry: LessonIndexEntry, card: LessonCard) -> datetime:
        """Return the newest producer/evidence timestamp, never an access time."""
        return max(entry.last_seen, card.created_at)

    def _index_path_for_context(self, context: TransferContext) -> Path:
        return (
            self._root
            / context.tenant_partition
            / context.task_family_slug
            / context.domain_slug
            / "index.json"
        )

    def _iter_index_paths(self) -> list[tuple[TransferContext, Path]]:
        paths = sorted(self._root.glob("*/*/*/index.json"))
        contexts: list[tuple[TransferContext, Path]] = []
        for path in paths:
            try:
                tenant_partition, task_family, domain = path.parts[-4:-1]
            except ValueError:
                continue
            contexts.append(
                (
                    TransferContext(
                        task_family=task_family,
                        domain=domain,
                        run_id="namespace_scan",
                        tenant_hash=tenant_partition,
                    ),
                    path,
                )
            )
        return contexts

    def _persist_index(
        self,
        snapshot: LessonIndexSnapshot,
        *,
        context: TransferContext | None = None,
        path: Path | None = None,
    ) -> None:
        active_context = context or resolve_transfer_context(
            task_family=snapshot.task_family,
            domain=snapshot.domain,
        )
        snapshot.snapshot_created_at = datetime.now(UTC)
        snapshot.task_family = snapshot.task_family or active_context.task_family
        snapshot.domain = snapshot.domain or active_context.domain
        self._write_index_file(snapshot, path=path or self._index_path_for_context(active_context))
        self._last_snapshot_ref = self._store.put_json(
            snapshot,
            PutOptions(
                kind=_LESSON_INDEX_KIND,
                media_type="application/json",
                schema=_LESSON_INDEX_SCHEMA,
            ),
            canon_spec=CanonSpec(forbid_floats=False),
        )

    @staticmethod
    def _write_index_file(snapshot: LessonIndexSnapshot, *, path: Path) -> None:
        payload = snapshot.model_dump_json(indent=2, exclude_none=True).encode("utf-8")
        path.parent.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile(
            mode="wb",
            delete=False,
            dir=str(path.parent),
            prefix=".lessons.",
            suffix=".tmp",
        ) as tmp:
            tmp.write(payload)
            tmp.flush()
            os.fsync(tmp.fileno())
            tmp_path = Path(tmp.name)
        os.replace(tmp_path, path)

    def _load_index_file(self, path: Path) -> LessonIndexSnapshot:
        snapshot = LessonIndexSnapshot.model_validate_json(path.read_text(encoding="utf-8"))
        for entry in snapshot.entries:
            access = self._access_path(path, entry.lesson_id)
            if access.exists():
                try:
                    stamp = datetime.fromisoformat(access.read_text(encoding="utf-8"))
                    if stamp.tzinfo is not None and (
                        entry.last_accessed_at is None or stamp > entry.last_accessed_at
                    ):
                        entry.last_accessed_at = stamp
                except ValueError:
                    pass  # Corrupt retention hints cannot create producer evidence.
        return snapshot

    @classmethod
    def load_snapshot(
        cls,
        store: FileSystemCAS,
        ref: ArtifactRef | str,
    ) -> LessonIndexSnapshot:
        return LessonIndexSnapshot.model_validate(from_canonical_bytes(store.get_bytes(ref)))

    @staticmethod
    def _sorted_entries(snapshot: LessonIndexSnapshot) -> list[LessonIndexEntry]:
        return sorted(
            snapshot.entries,
            key=lambda item: (
                item.invalidated,
                -item.provenance_weight,
                -item.occurrence_count,
                -item.last_seen.timestamp(),
            ),
        )


__all__ = [
    "LessonCard",
    "LessonIndexEntry",
    "LessonIndexSnapshot",
    "LessonKind",
    "LessonPattern",
    "LessonQuery",
    "LessonRegistry",
    "LessonTrustLevel",
    "lesson_from_failure_card",
    "load_lesson_card",
    "persist_lesson_card",
    "success_lesson_from_outcome",
]
