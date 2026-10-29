"""CAS-backed lesson registry for funnel failures and transfer-aware reuse."""

from __future__ import annotations

import math
import os
import re
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from enum import Enum
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Literal, cast
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from polisyos.core.artifacts.manifest import ArtifactRef, InputRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.ir import FailureSeverity, TypedFailureCard
from polisyos.scientist.methods.autotune.models import default_search_registry_root
from polisyos.scientist.methods.search.objective import ObjectiveScoreStatus
from polisyos.scientist.methods.search.transfer_context import (
    TransferAuditHop,
    TransferContext,
    TransferPathBinding,
    TransferPolicy,
    TransferScopeRefusal,
    TransferScopeRefusalReason,
    TransferScopeRefusedError,
    TransferSourceScope,
    TransferTenantScopeStatus,
    build_transfer_hop,
    compute_provenance_weight,
    decode_transfer_scope_path,
    make_transfer_scope_refusal,
    resolve_transfer_context,
    transfer_scope_path_parts,
    transfer_scope_refusal,
)

_LESSON_CARD_KIND = "scientist.search.lesson_card"
_LESSON_INDEX_KIND = "scientist.search.lesson_index"
_LESSON_CARD_SCHEMA = SchemaInfo(name="polisyos.scientist.search.LessonCard", version="2.0")
_LESSON_INDEX_SCHEMA = SchemaInfo(
    name="polisyos.scientist.search.LessonIndexSnapshot",
    version="3.0",
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
    schema_version: Literal["1.0", "2.0"] = "2.0"
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
    origin_tenant_scope_status: TransferTenantScopeStatus = TransferTenantScopeStatus.UNKNOWN
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
    origin_tenant_scope_status: TransferTenantScopeStatus = TransferTenantScopeStatus.UNKNOWN
    remediation_hint: str | None = None


class LessonIndexSnapshot(BaseModel):
    """Serializable snapshot of the lesson registry index."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0", "3.0"] = "3.0"
    snapshot_created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    task_family: str = Field(default="policy", min_length=1)
    domain: str = Field(default="general", min_length=1)
    source_scope: TransferSourceScope | None = None
    entries: list[LessonIndexEntry] = Field(default_factory=list)


class LessonTransferBundle(BaseModel):
    """Transfer candidates paired with source-scope refusals from the same scan."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    candidates: list[LessonCard] = Field(default_factory=list)
    scope_refusals: list[TransferScopeRefusal] = Field(default_factory=list)
    target_tenant_scope_status: TransferTenantScopeStatus = TransferTenantScopeStatus.UNKNOWN


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
    origin_tenant_scope_status: TransferTenantScopeStatus = TransferTenantScopeStatus.UNKNOWN
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


def _search_source_refusal(ref: ArtifactRef | str) -> TransferScopeRefusedError:
    """Build a typed refusal for a source artifact that fails schema admission."""
    return TransferScopeRefusedError(
        [
            make_transfer_scope_refusal(
                Path(str(ref)), TransferScopeRefusalReason.INVALID_SOURCE_BODY
            )
        ]
    )


def _load_profiled_search_artifact(
    store: FileSystemCAS,
    ref: ArtifactRef | str,
    *,
    kind: str,
    schema_name: str,
    supported_versions: frozenset[str],
    model_type: type[BaseModel],
) -> BaseModel:
    """Load one exact selected manifest and require its schema to match the body."""
    from polisyos.core.artifacts import (
        artifact_ref_for_manifest,
        load_core_json_artifact,
        read_core_manifest_profile,
    )

    try:
        manifest, _ = read_core_manifest_profile(store, ref)
        declared_schema = manifest.artifact_schema
        if (
            manifest.kind != kind
            or manifest.media_type != "application/json"
            or declared_schema is None
            or declared_schema.name != schema_name
            or declared_schema.version not in supported_versions
        ):
            raise ValueError("search_artifact_manifest_schema_mismatch")
        selected_ref = artifact_ref_for_manifest(manifest)
        model = model_type.model_validate(load_core_json_artifact(store, selected_ref))
        if getattr(model, "schema_version", None) != declared_schema.version:
            raise ValueError("search_artifact_payload_schema_mismatch")
    except (ValidationError, TypeError, ValueError):
        raise _search_source_refusal(ref) from None
    return model


def persist_lesson_card(
    store: FileSystemCAS,
    card: LessonCard,
    *,
    inputs: list[InputRef] | None = None,
) -> ArtifactRef:
    """Persist a reusable lesson card captured from failures, governance issues, or successful runs."""
    card_data = card.model_dump(mode="python")
    card_data["schema_version"] = "2.0"
    current_card = LessonCard.model_validate(card_data)
    return store.put_json(
        current_card,
        PutOptions(
            kind=_LESSON_CARD_KIND,
            media_type="application/json",
            schema=_LESSON_CARD_SCHEMA,
            inputs=list(inputs or []),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )


def load_lesson_card(store: FileSystemCAS, ref: ArtifactRef | str) -> LessonCard:
    """Load a lesson card only when its exact manifest and body schemas agree."""
    return cast(
        "LessonCard",
        _load_profiled_search_artifact(
            store,
            ref,
            kind=_LESSON_CARD_KIND,
            schema_name=_LESSON_CARD_SCHEMA.name,
            supported_versions=frozenset({"1.0", "2.0"}),
            model_type=LessonCard,
        ),
    )


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
    context = resolve_transfer_context(
        transfer_context=transfer_context, fallback_run_id=source_run_id
    )
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
    raw_value = getattr(final_result, "objective_value", None)
    score_status = getattr(final_result, "score_status", ObjectiveScoreStatus.NOT_ESTABLISHED)
    assessment = getattr(final_result, "score_assessment", None)
    assessed_value = getattr(assessment, "value", None)
    objective_value: float | None = None
    if (
        score_status is ObjectiveScoreStatus.AVAILABLE
        and getattr(assessment, "status", None) is ObjectiveScoreStatus.AVAILABLE
        and not isinstance(raw_value, bool)
        and isinstance(raw_value, (int, float))
        and math.isfinite(float(raw_value))
        and assessed_value is not None
        and float(raw_value) == float(assessed_value)
    ):
        objective_value = float(raw_value)
    final_action = str(getattr(outcome, "final_action", "complete"))
    candidate_hash = str(getattr(outcome, "candidate_hash", "unknown"))
    context = resolve_transfer_context(
        transfer_context=transfer_context, fallback_run_id=source_run_id
    )
    summary = f"Candidate reached {stage_name} with final action '{final_action}'."
    if objective_value is not None:
        summary = f"{summary[:-1]} and objective {objective_value:.4f}."
    return LessonCard(
        kind=LessonKind.SUCCESS,
        summary=summary,
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
        metadata={
            "final_action": final_action,
            "objective_score_status": (
                score_status.value
                if isinstance(score_status, ObjectiveScoreStatus)
                else ObjectiveScoreStatus.NOT_ESTABLISHED.value
            ),
        },
    )


def _legacy_tenant_partition(tenant_hash: str | None) -> str:
    """Reproduce the pre-v2 locator only to detect, never to trust, old data."""
    normalized = (tenant_hash or "global").strip().lower() or "unknown"
    return re.sub(r"[^a-z0-9_.-]+", "_", normalized)


def _scope_refusal(path: Path, reason: TransferScopeRefusalReason) -> TransferScopeRefusal:
    return make_transfer_scope_refusal(path, reason)


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
        target = resolve_transfer_context(
            transfer_context=context,
            task_family=(card.task_family if "task_family" in card.model_fields_set else None),
            domain=card.domain if "domain" in card.model_fields_set else None,
            # source_run_id describes the source card, not a declared target run.
            fallback_run_id=card.source_run_id if context is None else None,
        )
        normalized_card = self._normalize_card(card, resolved_context=target)
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
                    origin_tenant_scope_status=normalized_card.origin_tenant_scope_status,
                    remediation_hint=normalized_card.remediation_hint,
                )
            )
        else:
            existing.artifact_ref = card_ref
            existing.lesson_id = normalized_card.lesson_id
            existing.occurrence_count += 1
            existing.last_seen = max(existing.last_seen, now)
            existing.last_accessed_at = max(
                [
                    stamp
                    for stamp in (existing.last_accessed_at, normalized_card.last_accessed_at)
                    if stamp is not None
                ],
                default=existing.last_accessed_at,
            )
            existing.tags = sorted(set(existing.tags) | set(normalized_card.tags))
            existing.summary = normalized_card.summary or existing.summary
            existing.candidate_hash = normalized_card.candidate_hash or existing.candidate_hash
            existing.confidence = max(existing.confidence, normalized_card.confidence)
            existing.provenance_weight = max(
                existing.provenance_weight,
                normalized_card.provenance_weight,
            )
            existing.task_family = normalized_card.task_family or existing.task_family
            existing.domain = normalized_card.domain or existing.domain
            existing.origin_run_id = existing.origin_run_id or normalized_card.origin_run_id
            existing.origin_domain = existing.origin_domain or normalized_card.origin_domain
            existing.origin_tenant_hash = (
                existing.origin_tenant_hash
                if existing.origin_tenant_hash is not None
                else normalized_card.origin_tenant_hash
            )
            existing.origin_tenant_scope_status = normalized_card.origin_tenant_scope_status
            existing.transfer_chain = (
                list(existing.transfer_chain)
                if existing.transfer_chain
                else list(normalized_card.transfer_chain)
            )
            if existing.trust_level is not LessonTrustLevel.LOCAL:
                existing.trust_level = normalized_card.trust_level
            existing.remediation_hint = (
                normalized_card.remediation_hint or existing.remediation_hint
            )
            if card_ref not in existing.card_refs:
                existing.card_refs.append(card_ref)
                existing.card_refs = existing.card_refs[-20:]

        self._persist_index(snapshot, context=target)
        return card_ref

    def query(self, context: LessonQuery) -> list[LessonCard]:
        target = resolve_transfer_context(
            task_family=context.task_family,
            domain=context.domain,
            fallback_run_id=context.source_run_id or "unknown",
            tenant_hash=context.tenant_hash,
            tenant_hash_is_explicit="tenant_hash" in context.model_fields_set,
        )
        if self._should_aggregate_local_query(context):
            return self._query_local_aggregated(context, target_context=target)
        return self._query_local(context, target_context=target)

    def query_with_transfer(
        self,
        context: LessonQuery,
        *,
        target_context: TransferContext | None = None,
        policy: TransferPolicy | None = None,
    ) -> list[LessonCard]:
        if target_context is not None:
            # Query task/domain/run fields select source cards; target_context is
            # the target declaration. tenant_hash selects the namespace because
            # LessonQuery has no separate tenant-card predicate.
            active_target = resolve_transfer_context(
                transfer_context=target_context,
                tenant_hash=context.tenant_hash,
                tenant_hash_is_explicit="tenant_hash" in context.model_fields_set,
            )
        else:
            active_target = resolve_transfer_context(
                task_family=context.task_family,
                domain=context.domain,
                fallback_run_id="unknown",
                tenant_hash=context.tenant_hash,
                tenant_hash_is_explicit="tenant_hash" in context.model_fields_set,
            )
        if self._should_use_aggregated_local_transfer_lookup(context, active_target):
            results = self._query_local_aggregated(context, target_context=active_target)
            return results[: context.limit]

        results = self._query_local(context, target_context=active_target)
        if len(results) >= context.limit:
            return results[: context.limit]

        transfer_bundle = self._find_transfer_candidates(
            context,
            target_context=active_target,
            policy=policy,
            candidate_limit=None,
        )
        blocking_refusals = [
            refusal
            for refusal in transfer_bundle.scope_refusals
            if refusal.reason is not TransferScopeRefusalReason.CROSS_TENANT_NOT_AUTHORIZED
        ]
        if blocking_refusals:
            raise TransferScopeRefusedError(blocking_refusals)
        for candidate in transfer_bundle.candidates:
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
    ) -> LessonTransferBundle:
        """Return up to the requested number of ordered source candidates."""
        return self._find_transfer_candidates(
            context,
            target_context=target_context,
            policy=policy,
            candidate_limit=context.limit,
        )

    def _find_transfer_candidates(
        self,
        context: LessonQuery,
        *,
        target_context: TransferContext,
        policy: TransferPolicy | None = None,
        candidate_limit: int | None,
    ) -> LessonTransferBundle:
        """Select source candidates, optionally retaining the complete set.

        A final query defers its result quota until projected trust and
        confidence are recomputed. Direct candidate inspection remains bounded
        by the caller's query limit.
        """
        matches: list[tuple[float, datetime, LessonCard]] = []
        scope_refusals: list[TransferScopeRefusal] = []
        target_context = resolve_transfer_context(transfer_context=target_context)
        active_policy = policy or self._transfer_policy
        target_path = self._index_path_for_context(target_context)
        for path_binding, path in self._iter_index_paths():
            if path == target_path:
                continue
            if path_binding.status != "bound":
                reason = (
                    TransferScopeRefusalReason.LEGACY_PATH_UNBOUND
                    if path_binding.status == "legacy_unbound"
                    else TransferScopeRefusalReason.MALFORMED_PATH
                )
                scope_refusals.append(_scope_refusal(path, reason))
                continue
            try:
                snapshot = self._load_index_file(path)
            except (ValueError, ValidationError):
                scope_refusals.append(
                    _scope_refusal(path, TransferScopeRefusalReason.INVALID_SOURCE_BODY)
                )
                continue
            refusal = transfer_scope_refusal(path_binding, snapshot.source_scope, path)
            if refusal is not None:
                scope_refusals.append(refusal)
                continue
            source_scope = snapshot.source_scope
            assert source_scope is not None
            if any(
                entry.task_family != source_scope.task_family
                or entry.domain != source_scope.domain
                or entry.origin_tenant_hash != source_scope.tenant_hash
                or entry.origin_tenant_scope_status != source_scope.tenant_scope_status
                for entry in snapshot.entries
            ):
                scope_refusals.append(
                    _scope_refusal(path, TransferScopeRefusalReason.ENTRY_SCOPE_MISMATCH)
                )
                continue
            for entry in self._sorted_entries(snapshot):
                if entry.invalidated:
                    continue
                if not self._entry_matches(entry, context):
                    continue
                source_context = source_scope.context(run_id=entry.origin_run_id or entry.lesson_id)
                if source_context.tenant_scope_status is not target_context.tenant_scope_status:
                    reason = (
                        TransferScopeRefusalReason.TENANT_SCOPE_UNKNOWN
                        if TransferTenantScopeStatus.UNKNOWN
                        in {source_context.tenant_scope_status, target_context.tenant_scope_status}
                        else TransferScopeRefusalReason.TENANT_SCOPE_STATUS_MISMATCH
                    )
                    scope_refusals.append(_scope_refusal(path, reason))
                    continue
                cross_tenant_allowed = (
                    active_policy.allow_cross_tenant
                    and active_policy.allow_cross_domain
                    and target_context.cross_tenant_opt_in
                    and source_context.tenant_scope_status
                    is TransferTenantScopeStatus.AUTHENTICATED
                    and target_context.tenant_scope_status
                    is TransferTenantScopeStatus.AUTHENTICATED
                )
                if (
                    source_context.tenant_hash != target_context.tenant_hash
                    and not cross_tenant_allowed
                ):
                    scope_refusals.append(
                        _scope_refusal(
                            path,
                            TransferScopeRefusalReason.CROSS_TENANT_NOT_AUTHORIZED,
                        )
                    )
                    continue
                card = load_lesson_card(self._store, entry.artifact_ref)
                if (
                    card.task_family != source_scope.task_family
                    or card.domain != source_scope.domain
                    or card.origin_tenant_hash != source_scope.tenant_hash
                    or card.origin_tenant_scope_status != source_scope.tenant_scope_status
                ):
                    scope_refusals.append(
                        _scope_refusal(path, TransferScopeRefusalReason.ENTRY_SCOPE_MISMATCH)
                    )
                    continue
                weight = compute_provenance_weight(
                    source_context,
                    target_context,
                    created_at=self._evidence_anchor(entry, card),
                    policy=active_policy,
                )
                if weight <= 0.0:
                    continue
                if not self._revalidate_transfer(card, context, target_context=target_context):
                    continue
                normalized = self._normalize_card(
                    card.model_copy(update={"provenance_weight": weight}),
                    resolved_context=source_context,
                )
                matches.append((weight, entry.last_seen, normalized))

        matches.sort(key=lambda item: (item[0], item[1].timestamp()), reverse=True)
        blocking_refusals = [
            refusal
            for refusal in scope_refusals
            if refusal.reason is not TransferScopeRefusalReason.CROSS_TENANT_NOT_AUTHORIZED
        ]
        candidates = [card for _, _, card in matches]
        if candidate_limit is not None:
            candidates = candidates[:candidate_limit]
        return LessonTransferBundle(
            candidates=[] if blocking_refusals else candidates,
            scope_refusals=scope_refusals,
            target_tenant_scope_status=target_context.tenant_scope_status,
        )

    def materialize_transfer(
        self,
        card: LessonCard,
        *,
        target_context: TransferContext,
        query: LessonQuery | None = None,
        policy: TransferPolicy | None = None,
    ) -> LessonCard | None:
        # Source provenance is verified from the stored source record; it is not
        # an additional declaration of the destination TransferContext.
        target_context = resolve_transfer_context(transfer_context=target_context)
        active_policy = policy or self._transfer_policy
        source_binding = self._verified_source_binding_for_card(card)
        if source_binding is None:
            raise TransferScopeRefusedError(
                [
                    _scope_refusal(
                        Path(card.lesson_id), TransferScopeRefusalReason.SOURCE_BINDING_MISSING
                    )
                ]
            )
        source_scope, source_entry = source_binding
        source_context = source_scope.context(run_id=card.origin_run_id or card.source_run_id)
        effective_card = self._materialize_query_card(
            source_entry,
            now=datetime.now(UTC),
            source_context=source_context,
            ttl_days=active_policy.ttl_days,
        )
        # A caller may present an already-demoted candidate; never raise it.
        effective_card = effective_card.model_copy(
            update={
                "confidence": min(effective_card.confidence, card.confidence),
                "trust_level": (
                    LessonTrustLevel.LOW_CONFIDENCE
                    if card.trust_level is LessonTrustLevel.LOW_CONFIDENCE
                    else effective_card.trust_level
                ),
            }
        )
        weight = compute_provenance_weight(
            source_context,
            target_context,
            created_at=self._evidence_anchor(source_entry, effective_card),
            policy=active_policy,
        )
        if weight <= 0.0:
            return None
        if query is not None and not self._revalidate_transfer(
            effective_card,
            query,
            target_context=target_context,
        ):
            return None

        transfer_hop = build_transfer_hop(
            source_context,
            target_context,
            provenance_weight=weight,
        )
        materialized = self._normalize_card(
            effective_card.model_copy(
                update={
                    "lesson_id": uuid4().hex,
                    "task_family": target_context.task_family,
                    "domain": target_context.domain,
                    "trust_level": (
                        LessonTrustLevel.TRANSFERRED
                        if weight >= 0.5
                        and effective_card.trust_level is not LessonTrustLevel.LOW_CONFIDENCE
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
            resolved_context=target_context,
        )
        if query is not None and not self._matches_materialized_transfer(materialized, query):
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
                    origin_tenant_scope_status=entry.origin_tenant_scope_status,
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
        for path_binding, path in self._iter_index_paths():
            snapshot = self._load_scoped_index(path_binding, path)
            for entry in snapshot.entries:
                if entry.lesson_id != lesson_id:
                    continue
                entry.invalidated = True
                entry.invalidation_reason = reason
                matched = True
                scope = snapshot.source_scope
                assert scope is not None
                self._persist_index(snapshot, context=scope.context(), path=path)
                break
            if matched:
                break
        return matched

    def garbage_collect(self, ttl_days: int | None = None) -> int:
        active_ttl = max(1, int(ttl_days or self._transfer_policy.ttl_days))
        archive_cutoff = datetime.now(UTC) - timedelta(days=active_ttl * 2)
        removed = 0
        for path_binding, path in self._iter_index_paths():
            snapshot = self._load_scoped_index(path_binding, path)
            namespace_context = snapshot.source_scope.context() if snapshot.source_scope else None
            if namespace_context is None:
                raise TransferScopeRefusedError(
                    [_scope_refusal(path, TransferScopeRefusalReason.LEGACY_PATH_UNBOUND)]
                )
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
            active_context = resolve_transfer_context()
            return self._aggregate_local_snapshot(target_context=active_context)
        active_context = resolve_transfer_context(transfer_context=context)
        path = self._index_path_for_context(active_context)
        legacy_path = self._legacy_index_path_for_context(active_context)
        if legacy_path.exists():
            raise TransferScopeRefusedError(
                [_scope_refusal(legacy_path, TransferScopeRefusalReason.LEGACY_PATH_UNBOUND)]
            )
        expected_scope = TransferSourceScope.from_context(active_context)
        if not path.exists():
            return LessonIndexSnapshot(
                schema_version="3.0",
                task_family=active_context.task_family,
                domain=active_context.domain,
                source_scope=expected_scope,
            )
        try:
            snapshot = self._load_index_file(path)
        except (ValueError, ValidationError):
            raise TransferScopeRefusedError(
                [_scope_refusal(path, TransferScopeRefusalReason.INVALID_SOURCE_BODY)]
            ) from None
        binding = decode_transfer_scope_path(path.relative_to(self._root).parts[:-1])
        refusal = transfer_scope_refusal(binding, snapshot.source_scope, path)
        if refusal is not None:
            raise TransferScopeRefusedError([refusal])
        if snapshot.source_scope != expected_scope:
            raise TransferScopeRefusedError(
                [_scope_refusal(path, TransferScopeRefusalReason.PATH_BODY_MISMATCH)]
            )
        if (
            snapshot.task_family != expected_scope.task_family
            or snapshot.domain != expected_scope.domain
        ):
            raise TransferScopeRefusedError(
                [_scope_refusal(path, TransferScopeRefusalReason.PATH_BODY_MISMATCH)]
            )
        return snapshot

    def _query_local(
        self,
        query: LessonQuery,
        *,
        target_context: TransferContext,
    ) -> list[LessonCard]:
        snapshot = self.index_snapshot(context=target_context)
        results: list[LessonCard] = []
        now = datetime.now(UTC)
        mutated = False
        for entry in self._sorted_entries(snapshot):
            if entry.invalidated:
                continue
            if not self._entry_matches(entry, query):
                continue
            card = self._materialize_query_card(entry, now=now, source_context=target_context)
            if not self._matches_query(card, query):
                continue
            results.append(card)
            entry.last_accessed_at = now
            mutated = True
            if len(results) >= query.limit:
                break
        if mutated:
            self._persist_index(snapshot, context=target_context)
        return results

    def _query_local_aggregated(
        self,
        query: LessonQuery,
        *,
        target_context: TransferContext,
    ) -> list[LessonCard]:
        now = datetime.now(UTC)
        candidates: list[
            tuple[
                tuple[bool, float, int, float],
                LessonIndexEntry,
                LessonIndexSnapshot,
                TransferContext,
            ]
        ] = []
        for path_binding, path in self._iter_index_paths():
            snapshot = self._load_scoped_index(path_binding, path)
            namespace_context = snapshot.source_scope.context() if snapshot.source_scope else None
            if namespace_context is None:
                raise TransferScopeRefusedError(
                    [_scope_refusal(path, TransferScopeRefusalReason.LEGACY_PATH_UNBOUND)]
                )
            scope = snapshot.source_scope
            assert scope is not None
            if (
                scope.tenant_hash != target_context.tenant_hash
                or scope.tenant_scope_status is not target_context.tenant_scope_status
            ):
                continue
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
        mutated_snapshots: dict[
            tuple[str, str, str], tuple[LessonIndexSnapshot, TransferContext]
        ] = {}
        for _, entry, snapshot, namespace_context in sorted(candidates, key=lambda item: item[0]):
            card = self._materialize_query_card(entry, now=now, source_context=namespace_context)
            if not self._matches_query(card, query):
                continue
            results.append(card)
            entry.last_accessed_at = now
            mutated_snapshots[
                (
                    namespace_context.tenant_partition,
                    namespace_context.task_family,
                    namespace_context.domain,
                )
            ] = (snapshot, namespace_context)
            if len(results) >= query.limit:
                break

        for snapshot, namespace_context in mutated_snapshots.values():
            self._persist_index(snapshot, context=namespace_context)
        return results

    def _aggregate_local_snapshot(
        self,
        *,
        target_context: TransferContext,
    ) -> LessonIndexSnapshot:
        snapshots: list[LessonIndexSnapshot] = []
        for binding, path in self._iter_index_paths():
            snapshot = self._load_scoped_index(binding, path)
            scope = snapshot.source_scope
            assert scope is not None
            if (
                scope.tenant_hash == target_context.tenant_hash
                and scope.tenant_scope_status is target_context.tenant_scope_status
            ):
                snapshots.append(snapshot)
        if not snapshots:
            return LessonIndexSnapshot(
                schema_version="3.0",
                task_family=target_context.task_family,
                domain=target_context.domain,
            )
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
                "tenant_hash" in query.model_fields_set,
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
    def _matches_materialized_transfer(
        record: LessonCard,
        query: LessonQuery,
    ) -> bool:
        """Apply effective result filters after source selection.

        Source identity and content selectors are checked against the
        original card before projection. The materialized result can
        change trust; these predicates govern its effective quality.
        """
        if query.trust_levels and record.trust_level not in set(query.trust_levels):
            return False
        return float(record.confidence) >= float(query.min_confidence)

    @staticmethod
    def _matches_query(
        record: LessonCard | LessonIndexEntry,
        query: LessonQuery,
        *,
        include_trust: bool = True,
    ) -> bool:
        """Apply query predicates to the record at the current pipeline stage.

        Index entries skip source-run and trust checks because the index does
        not own the effective card status and transfer may change trust. The
        domain predicate follows the record being evaluated: a source record
        before projection, or a persisted target record on a local read.
        origin_domain remains provenance and never replaces the record domain.
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
        source_context: TransferContext,
        ttl_days: int | None = None,
    ) -> LessonCard:
        card = load_lesson_card(self._store, entry.artifact_ref)
        if (
            entry.task_family != source_context.task_family
            or entry.domain != source_context.domain
            or entry.origin_tenant_hash != source_context.tenant_hash
            or entry.origin_tenant_scope_status is not source_context.tenant_scope_status
            or card.task_family != entry.task_family
            or card.domain != entry.domain
            or card.origin_tenant_hash != entry.origin_tenant_hash
            or card.origin_tenant_scope_status is not entry.origin_tenant_scope_status
        ):
            raise TransferScopeRefusedError(
                [
                    _scope_refusal(
                        Path(str(entry.artifact_ref)),
                        TransferScopeRefusalReason.ENTRY_SCOPE_MISMATCH,
                    )
                ]
            )
        normalized = self._normalize_card(card, resolved_context=source_context)
        evidence_anchor = self._evidence_anchor(entry, normalized)
        age = max(timedelta(), now - evidence_anchor)
        trust_level = normalized.trust_level
        confidence = normalized.confidence
        if age > timedelta(days=self._transfer_policy.ttl_days if ttl_days is None else ttl_days):
            trust_level = LessonTrustLevel.LOW_CONFIDENCE
            confidence = min(confidence, 0.5)
        return normalized.model_copy(
            update={
                "trust_level": trust_level,
                "confidence": confidence,
                "last_accessed_at": now,
                "provenance_weight": entry.provenance_weight,
            }
        )

    def _verified_source_binding_for_card(
        self,
        candidate: LessonCard,
    ) -> tuple[TransferSourceScope, LessonIndexEntry] | None:
        """Resolve a candidate to one unambiguous persisted source binding."""

        candidate_payload = candidate.model_dump(mode="json")
        for derived_field in ("provenance_weight", "last_accessed_at", "trust_level", "confidence"):
            candidate_payload.pop(derived_field, None)
        matches: list[tuple[TransferSourceScope, LessonIndexEntry]] = []
        for binding, path in self._iter_index_paths():
            if binding.status != "bound":
                continue
            snapshot = self._load_scoped_index(binding, path)
            scope = snapshot.source_scope
            if scope is None:
                continue
            for entry in snapshot.entries:
                if entry.invalidated or entry.lesson_id != candidate.lesson_id:
                    continue
                if (
                    entry.task_family != candidate.task_family
                    or entry.domain != candidate.domain
                    or entry.origin_run_id != candidate.origin_run_id
                    or entry.origin_domain != candidate.origin_domain
                    or entry.origin_tenant_hash != candidate.origin_tenant_hash
                    or entry.origin_tenant_scope_status is not candidate.origin_tenant_scope_status
                ):
                    continue
                stored = load_lesson_card(self._store, entry.artifact_ref)
                stored_payload = stored.model_dump(mode="json")
                for derived_field in (
                    "provenance_weight",
                    "last_accessed_at",
                    "trust_level",
                    "confidence",
                ):
                    stored_payload.pop(derived_field, None)
                if stored_payload != candidate_payload:
                    continue
                if candidate.trust_level == stored.trust_level:
                    if candidate.confidence > stored.confidence:
                        continue
                elif (
                    candidate.trust_level is not LessonTrustLevel.LOW_CONFIDENCE
                    or candidate.confidence > min(stored.confidence, 0.5)
                ):
                    continue
                if (
                    stored.task_family != scope.task_family
                    or stored.domain != scope.domain
                    or stored.origin_tenant_hash != scope.tenant_hash
                    or stored.origin_tenant_scope_status is not scope.tenant_scope_status
                ):
                    raise TransferScopeRefusedError(
                        [_scope_refusal(path, TransferScopeRefusalReason.ENTRY_SCOPE_MISMATCH)]
                    )
                matches.append((scope, entry))
        if not matches:
            return None
        binding = matches[0]
        return binding if all(item == binding for item in matches[1:]) else None

    def _normalize_card(
        self,
        card: LessonCard,
        *,
        resolved_context: TransferContext | None = None,
    ) -> LessonCard:
        if resolved_context is None:
            active_context = resolve_transfer_context(
                task_family=card.task_family,
                domain=card.domain,
                fallback_run_id=card.source_run_id,
                tenant_hash=card.origin_tenant_hash,
                tenant_hash_is_explicit=card.origin_tenant_hash is not None,
            )
        else:
            # Callers pass either a freshly resolved request context or a source
            # scope whose path, body, index rows, and CAS card were verified at intake.
            # Re-resolving a verified source against the live destination AccessScope
            # would conflate the two owners during an authorized cross-tenant transfer.
            active_context = resolved_context
        update: dict[str, Any] = {
            "task_family": (
                active_context.task_family
                if resolved_context is not None
                else (card.task_family or active_context.task_family)
            ),
            "domain": (
                active_context.domain
                if resolved_context is not None
                else (card.domain or active_context.domain)
            ),
            "origin_run_id": card.origin_run_id or card.source_run_id,
            "origin_domain": (
                card.origin_domain
                or (card.domain if resolved_context is None else active_context.domain)
                or active_context.domain
            ),
            "origin_tenant_hash": active_context.tenant_hash,
            "origin_tenant_scope_status": active_context.tenant_scope_status,
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
        return entry.last_accessed_at or entry.last_seen

    @staticmethod
    def _evidence_anchor(entry: LessonIndexEntry, card: LessonCard) -> datetime:
        """Return the newest producer/evidence timestamp, never an access time."""
        return max(entry.last_seen, card.created_at)

    def _index_path_for_context(self, context: TransferContext) -> Path:
        return self._root.joinpath(*transfer_scope_path_parts(context), "index.json")

    def _legacy_index_path_for_context(self, context: TransferContext) -> Path:
        return (
            self._root
            / _legacy_tenant_partition(context.tenant_hash)
            / context.task_family_slug
            / context.domain_slug
            / "index.json"
        )

    def _iter_index_paths(self) -> list[tuple[TransferPathBinding, Path]]:
        paths = sorted(self._root.rglob("index.json"))
        result: list[tuple[TransferPathBinding, Path]] = []
        for path in paths:
            result.append(
                (decode_transfer_scope_path(path.relative_to(self._root).parts[:-1]), path)
            )
        return result

    def _persist_index(
        self,
        snapshot: LessonIndexSnapshot,
        *,
        context: TransferContext | None = None,
        path: Path | None = None,
    ) -> None:
        active_context = context or (
            snapshot.source_scope.context()
            if snapshot.source_scope is not None
            else resolve_transfer_context(
                task_family=snapshot.task_family,
                domain=snapshot.domain,
            )
        )
        expected_scope = TransferSourceScope.from_context(active_context)
        if snapshot.source_scope is None and snapshot.entries:
            raise TransferScopeRefusedError(
                [
                    _scope_refusal(
                        path or self._index_path_for_context(active_context),
                        TransferScopeRefusalReason.SOURCE_BINDING_MISSING,
                    )
                ]
            )
        if snapshot.source_scope is not None and snapshot.source_scope != expected_scope:
            reason = (
                TransferScopeRefusalReason.CROSS_TENANT_NOT_AUTHORIZED
                if snapshot.source_scope.tenant_hash != expected_scope.tenant_hash
                else TransferScopeRefusalReason.PATH_BODY_MISMATCH
            )
            raise TransferScopeRefusedError(
                [_scope_refusal(path or self._index_path_for_context(active_context), reason)]
            )
        if snapshot.source_scope is not None and (
            snapshot.task_family != expected_scope.task_family
            or snapshot.domain != expected_scope.domain
        ):
            raise TransferScopeRefusedError(
                [
                    _scope_refusal(
                        path or self._index_path_for_context(active_context),
                        TransferScopeRefusalReason.PATH_BODY_MISMATCH,
                    )
                ]
            )
        snapshot.schema_version = "3.0"
        snapshot.source_scope = expected_scope
        snapshot.snapshot_created_at = datetime.now(UTC)
        snapshot.task_family = snapshot.task_family or active_context.task_family
        snapshot.domain = snapshot.domain or active_context.domain
        if any(
            entry.task_family != expected_scope.task_family
            or entry.domain != expected_scope.domain
            or entry.origin_tenant_hash != expected_scope.tenant_hash
            or entry.origin_tenant_scope_status != expected_scope.tenant_scope_status
            for entry in snapshot.entries
        ):
            raise TransferScopeRefusedError(
                [
                    _scope_refusal(
                        path or self._index_path_for_context(active_context),
                        TransferScopeRefusalReason.ENTRY_SCOPE_MISMATCH,
                    )
                ]
            )
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
        payload = snapshot.model_dump_json(indent=2).encode("utf-8")
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

    def _load_scoped_index(
        self, path_binding: TransferPathBinding, path: Path
    ) -> LessonIndexSnapshot:
        try:
            snapshot = self._load_index_file(path)
        except (ValueError, ValidationError):
            raise TransferScopeRefusedError(
                [_scope_refusal(path, TransferScopeRefusalReason.INVALID_SOURCE_BODY)]
            ) from None
        refusal = transfer_scope_refusal(path_binding, snapshot.source_scope, path)
        if refusal is not None:
            raise TransferScopeRefusedError([refusal])
        scope = snapshot.source_scope
        assert scope is not None
        if snapshot.task_family != scope.task_family or snapshot.domain != scope.domain:
            raise TransferScopeRefusedError(
                [_scope_refusal(path, TransferScopeRefusalReason.PATH_BODY_MISMATCH)]
            )
        if any(
            entry.task_family != scope.task_family
            or entry.domain != scope.domain
            or entry.origin_tenant_hash != scope.tenant_hash
            or entry.origin_tenant_scope_status != scope.tenant_scope_status
            for entry in snapshot.entries
        ):
            raise TransferScopeRefusedError(
                [_scope_refusal(path, TransferScopeRefusalReason.ENTRY_SCOPE_MISMATCH)]
            )
        return snapshot

    @staticmethod
    def _load_index_file(path: Path) -> LessonIndexSnapshot:
        return LessonIndexSnapshot.model_validate_json(path.read_text(encoding="utf-8"))

    @classmethod
    def load_snapshot(
        cls,
        store: FileSystemCAS,
        ref: ArtifactRef | str,
    ) -> LessonIndexSnapshot:
        snapshot = cast(
            "LessonIndexSnapshot",
            _load_profiled_search_artifact(
                store,
                ref,
                kind=_LESSON_INDEX_KIND,
                schema_name=_LESSON_INDEX_SCHEMA.name,
                supported_versions=frozenset({"1.0", "3.0"}),
                model_type=LessonIndexSnapshot,
            ),
        )
        scope = snapshot.source_scope
        if scope is None:
            raise TransferScopeRefusedError(
                [_scope_refusal(Path(str(ref)), TransferScopeRefusalReason.SOURCE_BINDING_MISSING)]
            )
        if snapshot.task_family != scope.task_family or snapshot.domain != scope.domain:
            raise TransferScopeRefusedError(
                [_scope_refusal(Path(str(ref)), TransferScopeRefusalReason.PATH_BODY_MISMATCH)]
            )
        if any(
            entry.task_family != scope.task_family
            or entry.domain != scope.domain
            or entry.origin_tenant_hash != scope.tenant_hash
            or entry.origin_tenant_scope_status != scope.tenant_scope_status
            for entry in snapshot.entries
        ):
            raise TransferScopeRefusedError(
                [_scope_refusal(Path(str(ref)), TransferScopeRefusalReason.ENTRY_SCOPE_MISMATCH)]
            )
        return snapshot

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
    "LessonTransferBundle",
    "lesson_from_failure_card",
    "load_lesson_card",
    "persist_lesson_card",
    "success_lesson_from_outcome",
]
