"""Balanced success, failure, and opportunity memory contracts."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import TYPE_CHECKING, Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from polisyos.scientist.methods.search.lessons import LessonCard, LessonKind
from polisyos.scientist.orchestration.memory.contracts import MemoryVisibility

if TYPE_CHECKING:
    from collections.abc import Iterable

    from polisyos.scientist.orchestration.memory.applicability import (
        MemoryApplicabilityContext,
    )

BALANCED_MEMORY_SCHEMA_VERSION = "policyos.scientist.balanced_memory_record.v1"
BALANCED_MEMORY_ADR_REF = "ADR-0172"
BALANCED_MEMORY_METADATA_KEY = "balanced_memory_record"
BALANCED_MEMORY_LESSON_SCHEMA_VERSION = "1.1"

MEMORY_FORBIDDEN_CURRENT_USES: tuple[str, ...] = (
    "current_claim_evidence",
    "current_claim_closure",
    "claim_support",
    "claim_refutation",
    "legal_authority",
    "data_authority",
    "method_authority",
    "closeout_verdict",
    "producer_evidence_replacement",
    "claim_registry_ref_replacement",
)
MEMORY_FUTURE_AUTHORITY_USES: tuple[str, ...] = (
    "future_search",
    "future_review",
    "future_routing",
    "future_acquisition_suggestion",
    "memory_lifecycle",
)
_LLM_SOURCE_KINDS = frozenset({"llm_candidate", "llm_critic", "llm_drafter"})


class BalancedMemoryKind(str, Enum):
    """Balanced memory kind.

    Failure memories preserve known anti-patterns. Success memories preserve
    useful search or review paths. Opportunity memories preserve promising
    unresolved follow-up paths.
    """

    FAILURE = "failure"
    SUCCESS = "success"
    OPPORTUNITY = "opportunity"


class MemoryInfluenceMode(str, Enum):
    """Allowed future influence modes for balanced memory."""

    WARNING_ANTI_PATTERN = "warning_anti_pattern"
    GUIDE_SEARCH = "guide_search"
    GUIDE_REVIEW = "guide_review"
    SUGGEST_ACQUISITION = "suggest_acquisition"


class MemorySourceKind(str, Enum):
    """Source classification for memory authority and P15 boundaries."""

    DETERMINISTIC_PRODUCER = "deterministic_producer"
    RUNTIME_QUALITY = "runtime_quality"
    HUMAN_REVIEW = "human_review"
    LLM_CANDIDATE = "llm_candidate"
    LLM_CRITIC = "llm_critic"
    LLM_DRAFTER = "llm_drafter"


class MemorySourceStatus(str, Enum):
    """Authority status of the source material captured as memory."""

    VERIFIED = "verified"
    CANDIDATE_UNVERIFIED = "candidate_unverified"
    REJECTED_SPECULATION = "rejected_speculation"


class BalancedMemoryDecayPolicy(BaseModel):
    """Governed TTL and decay configuration for reusable balanced memory."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["policyos.scientist.memory_decay_policy.v1"] = (
        "policyos.scientist.memory_decay_policy.v1"
    )
    default_ttl_days: int = Field(default=180, ge=1)
    half_life_days: int = Field(default=45, ge=1)
    minimum_influence_weight: float = Field(default=0.05, ge=0.0, le=1.0)
    governed_config_ref: str = Field(
        default="governed-config:scientist-memory-decay/default-v1",
        min_length=1,
    )


class BalancedMemoryBiasPolicy(BaseModel):
    """Governed thresholds for conservative-bias memory posture metrics."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["policyos.scientist.memory_bias_policy.v1"] = (
        "policyos.scientist.memory_bias_policy.v1"
    )
    risk_overprediction_threshold: float = Field(default=0.70, ge=0.0, le=1.0)
    opportunity_suppression_threshold: float = Field(default=0.60, ge=0.0, le=1.0)
    excessive_blocker_threshold: float = Field(default=0.70, ge=0.0, le=1.0)
    minimum_sample_count: int = Field(default=1, ge=1)
    governed_config_ref: str = Field(
        default="governed-config:scientist-memory-bias/default-v1",
        min_length=1,
    )


class BalancedMemoryBiasMetrics(BaseModel):
    """Metrics that surface conservative skew in retrieved memory influence."""

    model_config = ConfigDict(extra="forbid")

    risk_overprediction_rate: float = Field(ge=0.0, le=1.0)
    opportunity_suppression_rate: float = Field(ge=0.0, le=1.0)
    excessive_blocker_rate: float = Field(ge=0.0, le=1.0)
    warnings: tuple[str, ...] = Field(default=())
    retrieved_kind_counts: dict[str, int] = Field(default_factory=dict)
    rejected_kind_counts: dict[str, int] = Field(default_factory=dict)


class MemoryScopeRevocationTrigger(BaseModel):
    """Rule-change trigger that revokes only memories in the affected scope."""

    model_config = ConfigDict(extra="forbid")

    trigger_id: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    changed_rule_ref: str = Field(min_length=1)
    previous_rule_version: str = Field(min_length=1)
    new_rule_version: str = Field(min_length=1)
    scope: BalancedMemoryScope
    affected_pattern_types: tuple[str, ...] = Field(default=())
    affected_memory_ids: tuple[str, ...] = Field(default=())
    changed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("affected_pattern_types", "affected_memory_ids", mode="before")
    @classmethod
    def _coerce_trigger_tuple(cls, value: Iterable[str] | None) -> tuple[str, ...]:
        if value is None:
            return ()
        return tuple(str(item) for item in value if str(item))

    @field_validator("changed_at")
    @classmethod
    def _normalize_changed_at(cls, value: datetime) -> datetime:
        return value.astimezone(UTC)


class BalancedMemoryScope(BaseModel):
    """Scope and expiry controls for reusable balanced memory."""

    model_config = ConfigDict(extra="forbid")

    visibility: MemoryVisibility = MemoryVisibility.DOMAIN
    tenant_hash: str | None = None
    domain: str = Field(default="general", min_length=1)
    workflow_id: str | None = None
    method_family: str | None = None
    task_family: str = Field(default="policy", min_length=1)
    expires_at: datetime | None = None

    @field_validator("expires_at")
    @classmethod
    def _normalize_expiry(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        return value.astimezone(UTC)

    def to_legacy_scope(self) -> dict[str, str]:
        """Return the existing lesson metadata scope shape."""

        scope = {
            "visibility": self.visibility.value,
            "domain": self.domain,
            "task_family": self.task_family,
        }
        if self.tenant_hash:
            scope["tenant_hash"] = self.tenant_hash
        if self.workflow_id:
            scope["workflow_id"] = self.workflow_id
        if self.method_family:
            scope["method_family"] = self.method_family
        if self.expires_at is not None:
            scope["expires_at"] = self.expires_at.isoformat()
        return scope


class BalancedMemoryAuthorityBoundary(BaseModel):
    """Authority boundary that keeps memory influence out of evidence slots."""

    model_config = ConfigDict(extra="forbid")

    adr_ref: Literal["ADR-0172"] = BALANCED_MEMORY_ADR_REF
    source_kind: MemorySourceKind
    source_status: MemorySourceStatus = MemorySourceStatus.VERIFIED
    authoritative_for: tuple[str, ...] = MEMORY_FUTURE_AUTHORITY_USES
    may_not_use_for: tuple[str, ...] = MEMORY_FORBIDDEN_CURRENT_USES
    producer_verification_ref: str | None = None

    @model_validator(mode="after")
    def _validate_boundary(self) -> BalancedMemoryAuthorityBoundary:
        missing = set(MEMORY_FORBIDDEN_CURRENT_USES) - set(self.may_not_use_for)
        if missing:
            raise ValueError(
                "balanced memory boundary missing forbidden uses: "
                + ",".join(sorted(missing))
            )
        if (
            self.source_kind.value in _LLM_SOURCE_KINDS
            and self.source_status is MemorySourceStatus.VERIFIED
        ):
            raise ValueError("LLM-originated memory cannot be verified by its own source")
        return self


class BalancedMemoryRecord(BaseModel):
    """Persistable balanced memory record stored through the lesson registry."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["policyos.scientist.balanced_memory_record.v1"] = (
        BALANCED_MEMORY_SCHEMA_VERSION
    )
    memory_id: str = Field(default_factory=lambda: f"memory-{uuid4().hex}", min_length=1)
    kind: BalancedMemoryKind
    summary: str = Field(min_length=1)
    pattern_type: str = Field(min_length=1)
    stage_name: str = Field(min_length=1)
    source_run_id: str = Field(min_length=1)
    candidate_hash: str = Field(min_length=1)
    scope: BalancedMemoryScope = Field(default_factory=BalancedMemoryScope)
    authority_boundary: BalancedMemoryAuthorityBoundary
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    influence_modes: tuple[MemoryInfluenceMode, ...] = Field(default=())
    tags: tuple[str, ...] = Field(default=())
    anti_patterns: tuple[str, ...] = Field(default=())
    guidance: str | None = None
    revoked_at: datetime | None = None
    revocation_reason: str | None = None
    contamination_checked: bool = False
    contamination_findings: tuple[str, ...] = Field(default=())
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("created_at", "revoked_at")
    @classmethod
    def _normalize_datetimes(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        return value.astimezone(UTC)

    @field_validator("tags", "anti_patterns", mode="before")
    @classmethod
    def _coerce_tuple(cls, value: Iterable[str] | None) -> tuple[str, ...]:
        if value is None:
            return ()
        return tuple(str(item) for item in value if str(item))

    @model_validator(mode="after")
    def _validate_memory_record(self) -> BalancedMemoryRecord:
        if self.scope.expires_at is not None and self.scope.expires_at <= self.created_at:
            raise ValueError("balanced memory expiry must be after creation")
        if self.revoked_at is not None and not self.revocation_reason:
            raise ValueError("revoked balanced memory requires revocation_reason")
        if self.revocation_reason and self.revoked_at is None:
            raise ValueError("revocation_reason requires revoked_at")
        if self.authority_boundary.source_kind.value in _LLM_SOURCE_KINDS and self.influence_modes:
            raise ValueError("LLM-originated memory cannot carry active influence modes")
        if (
            not self.influence_modes
            and self.authority_boundary.source_kind.value not in _LLM_SOURCE_KINDS
        ):
            self.influence_modes = default_influence_modes_for_kind(self.kind)
        return self

    @property
    def revoked(self) -> bool:
        """Return whether this memory record has been revoked."""

        return self.revoked_at is not None


class BalancedMemoryApplicability(BaseModel):
    """Applicability decision for a balanced memory record."""

    model_config = ConfigDict(extra="forbid")

    memory_id: str = Field(min_length=1)
    memory_kind: BalancedMemoryKind
    applies: bool
    reasons: tuple[str, ...] = Field(min_length=1)
    scope: dict[str, str] = Field(default_factory=dict)
    expires_at: datetime | None = None
    influence_weight: float = Field(default=1.0, ge=0.0, le=1.0)
    decay_status: Literal[
        "active",
        "decayed",
        "expired_scope",
        "expired_ttl",
        "revoked",
        "blocked",
    ] = "active"
    influence_modes: tuple[MemoryInfluenceMode, ...] = Field(default=())

    @model_validator(mode="after")
    def _validate_applicability(self) -> BalancedMemoryApplicability:
        if not self.reasons:
            raise ValueError("BalancedMemoryApplicability must include reasons")
        if not self.applies and self.influence_modes:
            raise ValueError("non-applicable balanced memory cannot carry influence modes")
        return self


def default_influence_modes_for_kind(
    kind: BalancedMemoryKind,
) -> tuple[MemoryInfluenceMode, ...]:
    """Return ADR-0172 default future influence modes for a memory kind."""

    if kind is BalancedMemoryKind.FAILURE:
        return (MemoryInfluenceMode.WARNING_ANTI_PATTERN, MemoryInfluenceMode.GUIDE_REVIEW)
    if kind is BalancedMemoryKind.SUCCESS:
        return (MemoryInfluenceMode.GUIDE_SEARCH, MemoryInfluenceMode.GUIDE_REVIEW)
    return (MemoryInfluenceMode.SUGGEST_ACQUISITION, MemoryInfluenceMode.GUIDE_REVIEW)


def build_balanced_memory_record(
    *,
    kind: BalancedMemoryKind,
    summary: str,
    pattern_type: str,
    stage_name: str,
    source_run_id: str,
    candidate_hash: str,
    scope: BalancedMemoryScope | None = None,
    source_kind: MemorySourceKind = MemorySourceKind.RUNTIME_QUALITY,
    source_status: MemorySourceStatus | None = None,
    confidence: float = 1.0,
    created_at: datetime | None = None,
    tags: Iterable[str] = (),
    anti_patterns: Iterable[str] = (),
    guidance: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> BalancedMemoryRecord:
    """Build a validated balanced memory record."""

    if source_status is None:
        source_status = (
            MemorySourceStatus.CANDIDATE_UNVERIFIED
            if source_kind.value in _LLM_SOURCE_KINDS
            else MemorySourceStatus.VERIFIED
        )
    influence_modes: tuple[MemoryInfluenceMode, ...] = (
        ()
        if source_kind.value in _LLM_SOURCE_KINDS
        else default_influence_modes_for_kind(kind)
    )
    active_scope = scope or BalancedMemoryScope()
    return BalancedMemoryRecord(
        kind=kind,
        summary=summary,
        pattern_type=pattern_type,
        stage_name=stage_name,
        source_run_id=source_run_id,
        candidate_hash=candidate_hash,
        scope=active_scope,
        authority_boundary=BalancedMemoryAuthorityBoundary(
            source_kind=source_kind,
            source_status=source_status,
        ),
        created_at=created_at or datetime.now(UTC),
        confidence=confidence,
        influence_modes=influence_modes,
        tags=tuple(tags),
        anti_patterns=tuple(anti_patterns),
        guidance=guidance,
        metadata=metadata or {},
    )


def balanced_memory_to_lesson_card(memory: BalancedMemoryRecord) -> LessonCard:
    """Convert a balanced memory record into the existing persisted lesson shape."""

    metadata = {
        **memory.metadata,
        BALANCED_MEMORY_METADATA_KEY: memory.model_dump(mode="json"),
        "balanced_memory": True,
        "memory_kind": memory.kind.value,
        "memory_scope": memory.scope.to_legacy_scope(),
        "memory_visibility": memory.scope.visibility.value,
        "memory_authority_boundary": memory.authority_boundary.model_dump(mode="json"),
        "reusable_memory": True,
    }
    return LessonCard(
        lesson_id=memory.memory_id,
        schema_version=BALANCED_MEMORY_LESSON_SCHEMA_VERSION,
        kind=LessonKind(memory.kind.value),
        summary=memory.summary,
        failure_type=memory.pattern_type,
        stage_name=memory.stage_name,
        fidelity_level=0,
        candidate_hash=memory.candidate_hash,
        source_run_id=memory.source_run_id,
        created_at=memory.created_at,
        confidence=memory.confidence,
        task_family=memory.scope.task_family,
        domain=memory.scope.domain,
        origin_run_id=memory.source_run_id,
        origin_domain=memory.scope.domain,
        origin_tenant_hash=memory.scope.tenant_hash,
        tags=list(memory.tags),
        remediation_hint=memory.guidance,
        anti_patterns=list(memory.anti_patterns),
        metadata=metadata,
    )


def balanced_memory_from_lesson_card(lesson: LessonCard) -> BalancedMemoryRecord:
    """Read a balanced memory record from a lesson card."""

    payload = lesson.metadata.get(BALANCED_MEMORY_METADATA_KEY)
    if isinstance(payload, dict):
        return BalancedMemoryRecord.model_validate(payload)
    scope = _scope_from_legacy_metadata(lesson)
    return build_balanced_memory_record(
        kind=BalancedMemoryKind(lesson.kind.value),
        summary=lesson.summary,
        pattern_type=lesson.failure_type,
        stage_name=lesson.stage_name,
        source_run_id=lesson.source_run_id,
        candidate_hash=lesson.candidate_hash,
        scope=scope,
        source_kind=MemorySourceKind.RUNTIME_QUALITY,
        confidence=lesson.confidence,
        tags=lesson.tags,
        anti_patterns=lesson.anti_patterns,
        guidance=lesson.remediation_hint,
        metadata={
            key: value
            for key, value in lesson.metadata.items()
            if key not in {BALANCED_MEMORY_METADATA_KEY, "memory_scope"}
        },
    )


def revoke_balanced_memory_record(
    memory: BalancedMemoryRecord,
    *,
    reason: str,
    revoked_at: datetime | None = None,
) -> BalancedMemoryRecord:
    """Return a revoked copy of a balanced memory record."""

    return memory.model_copy(
        update={
            "revoked_at": (revoked_at or datetime.now(UTC)).astimezone(UTC),
            "revocation_reason": reason,
        }
    )


def evaluate_balanced_memory_applicability(
    memory: BalancedMemoryRecord,
    context: MemoryApplicabilityContext,
    *,
    revoked_memory_ids: Iterable[str] = (),
    decay_policy: BalancedMemoryDecayPolicy | None = None,
) -> BalancedMemoryApplicability:
    """Evaluate whether balanced memory may influence a future run."""

    active_decay_policy = decay_policy or BalancedMemoryDecayPolicy()
    reasons: list[str] = [f"{memory.kind.value}_memory"]
    blocked: list[str] = []
    revoked = set(revoked_memory_ids)
    scope = memory.scope.to_legacy_scope()
    now = context.now.astimezone(UTC)
    explicit_expiry = memory.scope.expires_at
    ttl_expiry = memory.created_at + timedelta(days=active_decay_policy.default_ttl_days)
    effective_expiry = _earliest_expiry(explicit_expiry, ttl_expiry)
    influence_weight = calculate_balanced_memory_influence_weight(
        memory,
        now=now,
        decay_policy=active_decay_policy,
    )
    decay_status: Literal[
        "active",
        "decayed",
        "expired_scope",
        "expired_ttl",
        "revoked",
        "blocked",
    ] = "active"

    if memory.memory_id in revoked or memory.revoked:
        blocked.append("revoked")
        decay_status = "revoked"
    if explicit_expiry is not None and now > explicit_expiry:
        blocked.append("expired")
        decay_status = "expired_scope"
    elif now > ttl_expiry:
        blocked.append("expired_ttl")
        decay_status = "expired_ttl"
    elif influence_weight < active_decay_policy.minimum_influence_weight:
        blocked.append("decayed_below_threshold")
        decay_status = "decayed"
    else:
        reasons.append("not_expired")
        reasons.append("decay_weight_active")
    if memory.scope.task_family and memory.scope.task_family != context.task_family:
        blocked.append("task_family_mismatch")
    else:
        reasons.append("task_family_match")

    _check_visibility(
        memory=memory,
        context=context,
        reasons=reasons,
        blocked=blocked,
    )
    _check_optional_scope(
        expected=memory.scope.workflow_id,
        context_value=context.workflow_id,
        label="workflow_id",
        reasons=reasons,
        blocked=blocked,
    )
    _check_optional_scope(
        expected=memory.scope.method_family,
        context_value=context.method_family,
        label="method_family",
        reasons=reasons,
        blocked=blocked,
    )
    if memory.authority_boundary.source_kind.value in _LLM_SOURCE_KINDS:
        if memory.authority_boundary.source_status is MemorySourceStatus.REJECTED_SPECULATION:
            blocked.append("llm_rejected_speculation")
        else:
            blocked.append("llm_candidate_unverified")
        decay_status = "blocked" if decay_status == "active" else decay_status

    applies = not blocked
    return BalancedMemoryApplicability(
        memory_id=memory.memory_id,
        memory_kind=memory.kind,
        applies=applies,
        reasons=tuple(_dedupe([*reasons, *blocked])),
        scope=scope,
        expires_at=effective_expiry,
        influence_weight=influence_weight,
        decay_status=decay_status,
        influence_modes=memory.influence_modes if applies else (),
    )


def assert_balanced_memory_can_influence(
    applicability: BalancedMemoryApplicability,
) -> BalancedMemoryApplicability:
    """Raise when balanced memory cannot influence a target run."""

    if not applicability.applies:
        raise ValueError("balanced memory cannot influence run: " + ",".join(applicability.reasons))
    return applicability


def calculate_balanced_memory_influence_weight(
    memory: BalancedMemoryRecord,
    *,
    now: datetime,
    decay_policy: BalancedMemoryDecayPolicy | None = None,
) -> float:
    """Return the decayed future-influence weight for a balanced memory record."""

    active_decay_policy = decay_policy or BalancedMemoryDecayPolicy()
    age = max(timedelta(), now.astimezone(UTC) - memory.created_at)
    age_days = age.total_seconds() / 86_400
    half_life_factor = 0.5 ** (age_days / active_decay_policy.half_life_days)
    return round(max(0.0, min(1.0, float(memory.confidence) * half_life_factor)), 12)


def memory_matches_scope_revocation_trigger(
    memory: BalancedMemoryRecord,
    trigger: MemoryScopeRevocationTrigger,
) -> bool:
    """Return whether a rule-change trigger affects this memory record."""

    if trigger.affected_memory_ids and memory.memory_id in set(trigger.affected_memory_ids):
        return True
    if trigger.affected_pattern_types and memory.pattern_type not in set(
        trigger.affected_pattern_types
    ):
        return False
    return _scope_matches_trigger(memory.scope, trigger.scope)


def revoke_balanced_memories_for_scope_change(
    memories: Iterable[BalancedMemoryRecord],
    trigger: MemoryScopeRevocationTrigger,
    *,
    revoked_at: datetime | None = None,
) -> tuple[BalancedMemoryRecord, ...]:
    """Return copies with matching memories revoked for a scoped rule change."""

    active_revoked_at = (revoked_at or trigger.changed_at).astimezone(UTC)
    output: list[BalancedMemoryRecord] = []
    for memory in memories:
        if not memory_matches_scope_revocation_trigger(memory, trigger):
            output.append(memory)
            continue
        output.append(
            revoke_balanced_memory_record(
                memory.model_copy(
                    update={
                        "metadata": {
                            **memory.metadata,
                            "scope_revocation_trigger": trigger.model_dump(mode="json"),
                        }
                    }
                ),
                reason=f"scope_revoked_rule_change:{trigger.changed_rule_ref}:{trigger.reason}",
                revoked_at=active_revoked_at,
            )
        )
    return tuple(output)


def calculate_conservative_bias_metrics(
    *,
    retrieved_memories: Iterable[BalancedMemoryRecord],
    rejected_memories: Iterable[BalancedMemoryApplicability],
    bias_policy: BalancedMemoryBiasPolicy | None = None,
) -> BalancedMemoryBiasMetrics:
    """Calculate conservative-bias metrics over one memory retrieval result."""

    active_policy = bias_policy or BalancedMemoryBiasPolicy()
    retrieved_counts = _balanced_kind_counts_record(memory.kind for memory in retrieved_memories)
    rejected_counts = _balanced_kind_counts_record(
        applicability.memory_kind for applicability in rejected_memories
    )
    retrieved_total = sum(retrieved_counts.values())
    failure_count = retrieved_counts.get(BalancedMemoryKind.FAILURE.value, 0)
    success_count = retrieved_counts.get(BalancedMemoryKind.SUCCESS.value, 0)
    opportunity_retrieved = retrieved_counts.get(BalancedMemoryKind.OPPORTUNITY.value, 0)
    opportunity_rejected = rejected_counts.get(BalancedMemoryKind.OPPORTUNITY.value, 0)

    risk_denominator = failure_count + success_count
    risk_overprediction_rate = _safe_rate(failure_count, risk_denominator)
    opportunity_suppression_rate = _safe_rate(
        opportunity_rejected,
        opportunity_retrieved + opportunity_rejected,
    )
    excessive_blocker_rate = _safe_rate(failure_count, retrieved_total)

    warnings: list[str] = []
    sample_count = retrieved_total + sum(rejected_counts.values())
    if sample_count >= active_policy.minimum_sample_count:
        if risk_overprediction_rate > active_policy.risk_overprediction_threshold:
            warnings.append("risk_overprediction")
        if opportunity_suppression_rate > active_policy.opportunity_suppression_threshold:
            warnings.append("opportunity_suppression")
        if excessive_blocker_rate > active_policy.excessive_blocker_threshold:
            warnings.append("excessive_blocker_rate")

    return BalancedMemoryBiasMetrics(
        risk_overprediction_rate=risk_overprediction_rate,
        opportunity_suppression_rate=opportunity_suppression_rate,
        excessive_blocker_rate=excessive_blocker_rate,
        warnings=tuple(warnings),
        retrieved_kind_counts=retrieved_counts,
        rejected_kind_counts=rejected_counts,
    )


def _scope_from_legacy_metadata(lesson: LessonCard) -> BalancedMemoryScope:
    raw_scope = lesson.metadata.get("memory_scope")
    if not isinstance(raw_scope, dict):
        raw_scope = {}
    visibility = _coerce_visibility(raw_scope.get("visibility"))
    expires_at = _parse_expiry(raw_scope.get("expires_at"))
    return BalancedMemoryScope(
        visibility=visibility,
        tenant_hash=_optional_text(raw_scope.get("tenant_hash") or lesson.origin_tenant_hash),
        domain=_optional_text(raw_scope.get("domain") or lesson.domain) or "general",
        workflow_id=_optional_text(raw_scope.get("workflow_id")),
        method_family=_optional_text(raw_scope.get("method_family")),
        task_family=_optional_text(raw_scope.get("task_family") or lesson.task_family) or "policy",
        expires_at=expires_at,
    )


def _earliest_expiry(left: datetime | None, right: datetime | None) -> datetime | None:
    if left is None:
        return right
    if right is None:
        return left
    return min(left, right)


def _scope_matches_trigger(
    memory_scope: BalancedMemoryScope,
    trigger_scope: BalancedMemoryScope,
) -> bool:
    if trigger_scope.task_family and memory_scope.task_family != trigger_scope.task_family:
        return False
    if trigger_scope.domain and memory_scope.domain != trigger_scope.domain:
        return False
    if trigger_scope.tenant_hash and memory_scope.tenant_hash != trigger_scope.tenant_hash:
        return False
    if trigger_scope.workflow_id and memory_scope.workflow_id != trigger_scope.workflow_id:
        return False
    return not (
        trigger_scope.method_family
        and memory_scope.method_family != trigger_scope.method_family
    )


def _balanced_kind_counts_record(kinds: Iterable[BalancedMemoryKind]) -> dict[str, int]:
    counts = {kind.value: 0 for kind in BalancedMemoryKind}
    for kind in kinds:
        counts[kind.value] += 1
    return {kind: count for kind, count in counts.items() if count}


def _safe_rate(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(max(0.0, min(1.0, numerator / denominator)), 12)


def _check_visibility(
    *,
    memory: BalancedMemoryRecord,
    context: MemoryApplicabilityContext,
    reasons: list[str],
    blocked: list[str],
) -> None:
    visibility = memory.scope.visibility
    if visibility is MemoryVisibility.LOCAL_RUN:
        if memory.source_run_id != context.run_id:
            blocked.append("run_scope_mismatch")
        else:
            reasons.append("run_scope_match")
        return
    if visibility is MemoryVisibility.TENANT:
        if not memory.scope.tenant_hash or memory.scope.tenant_hash != context.tenant_hash:
            blocked.append("tenant_scope_mismatch")
        else:
            reasons.append("tenant_scope_match")
        return
    if visibility is MemoryVisibility.DOMAIN:
        if memory.scope.domain != context.domain:
            blocked.append("domain_scope_mismatch")
        else:
            reasons.append("domain_scope_match")
        return
    reasons.append("global_public_scope")


def _check_optional_scope(
    *,
    expected: str | None,
    context_value: str | None,
    label: str,
    reasons: list[str],
    blocked: list[str],
) -> None:
    if expected is None:
        return
    if context_value != expected:
        blocked.append(f"{label}_mismatch")
        return
    reasons.append(f"{label}_match")


def _coerce_visibility(value: object) -> MemoryVisibility:
    try:
        return MemoryVisibility(str(value or MemoryVisibility.DOMAIN.value))
    except ValueError:
        return MemoryVisibility.DOMAIN


def _parse_expiry(value: object) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.astimezone(UTC)
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(UTC)


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _dedupe(values: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


__all__ = [
    "BALANCED_MEMORY_ADR_REF",
    "BALANCED_MEMORY_LESSON_SCHEMA_VERSION",
    "BALANCED_MEMORY_METADATA_KEY",
    "BALANCED_MEMORY_SCHEMA_VERSION",
    "MEMORY_FORBIDDEN_CURRENT_USES",
    "MEMORY_FUTURE_AUTHORITY_USES",
    "BalancedMemoryApplicability",
    "BalancedMemoryAuthorityBoundary",
    "BalancedMemoryBiasMetrics",
    "BalancedMemoryBiasPolicy",
    "BalancedMemoryDecayPolicy",
    "BalancedMemoryKind",
    "BalancedMemoryRecord",
    "BalancedMemoryScope",
    "MemoryInfluenceMode",
    "MemoryScopeRevocationTrigger",
    "MemorySourceKind",
    "MemorySourceStatus",
    "assert_balanced_memory_can_influence",
    "balanced_memory_from_lesson_card",
    "balanced_memory_to_lesson_card",
    "build_balanced_memory_record",
    "calculate_balanced_memory_influence_weight",
    "calculate_conservative_bias_metrics",
    "default_influence_modes_for_kind",
    "evaluate_balanced_memory_applicability",
    "memory_matches_scope_revocation_trigger",
    "revoke_balanced_memories_for_scope_change",
    "revoke_balanced_memory_record",
]
