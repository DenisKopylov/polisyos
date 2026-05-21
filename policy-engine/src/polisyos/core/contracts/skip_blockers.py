"""Typed skip/blocker contracts for optional analytic nodes."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from collections.abc import Mapping

SKIP_BLOCKER_REQUIRED_FIELDS = (
    "reason",
    "missing_input",
    "owner",
    "phase",
    "downstream_impact",
    "allowed_profile",
    "closeout_blocking_policy",
    "scorecard_blocking_policy",
    "approval_blocking_policy",
    "public_export_blocking_policy",
)
SERIOUS_SKIP_BLOCKER_PROFILES = frozenset(
    {"research", "governed", "production", "serious_runtime"}
)
SKIP_BLOCKER_SURFACES = frozenset(
    {"closeout", "scorecard", "approval", "public_export"}
)
OPTIONAL_ANALYTIC_NODE_KINDS = frozenset(
    {
        "causal",
        "transportability",
        "normative_arbitration",
        "governance",
        "evaluator",
        "decision_packet",
    }
)


class SkipBlockerContractError(ValueError):
    """Raised when a skipped analytic node has no valid blocker contract."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        field: str | None = None,
    ) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.field = field


class SkippedNodeBlocker(BaseModel):
    """Machine-actionable blocker persisted for one skipped analytic node."""

    model_config = ConfigDict(frozen=True, extra="allow")

    node_id: str = Field(min_length=1)
    alias: str | None = None
    node_kind: str = Field(min_length=1)
    status: str = Field(default="skipped", pattern="^skipped$")
    reason: str = Field(min_length=1)
    missing_input: str = Field(min_length=1)
    owner: str = Field(min_length=1)
    phase: str = Field(min_length=1)
    downstream_impact: str = Field(min_length=1)
    allowed_profile: str = Field(min_length=1)
    closeout_blocking_policy: str = Field(min_length=1)
    scorecard_blocking_policy: str = Field(min_length=1)
    approval_blocking_policy: str = Field(min_length=1)
    public_export_blocking_policy: str = Field(min_length=1)
    blocker_code: str = "skipped_analytic_node_blocks_scorecard"
    severity: str = "high"
    next_action: str | None = None
    generated_at: datetime | None = None


@dataclass(frozen=True)
class SkipBlockerPolicyDecision:
    """Result of applying a skipped-node blocker to a downstream surface."""

    allowed: bool
    blocking: bool
    code: str | None
    reason: str
    record: SkippedNodeBlocker | None = None
    surface: str = "scorecard"


def deserialize_skip_blocker_record(payload: Mapping[str, object]) -> SkippedNodeBlocker:
    """Validate a raw skipped-node blocker payload."""

    for field in SKIP_BLOCKER_REQUIRED_FIELDS:
        if field not in payload:
            raise SkipBlockerContractError(
                "skip_blocker_required_field_missing",
                f"Skipped node blocker is missing required field: {field}.",
                field=field,
            )
    return SkippedNodeBlocker.model_validate(dict(payload))


def serialize_skip_blocker_record(record: SkippedNodeBlocker) -> dict[str, object]:
    """Return a JSON-safe skipped-node blocker payload."""

    return record.model_dump(mode="json")


def build_skip_blocker_record(
    *,
    node_id: str,
    reason: str,
    missing_input: str,
    owner: str,
    phase: str,
    downstream_impact: str,
    allowed_profile: str,
    closeout_blocking_policy: str,
    scorecard_blocking_policy: str,
    approval_blocking_policy: str,
    public_export_blocking_policy: str,
    alias: str | None = None,
    node_kind: str | None = None,
    blocker_code: str = "skipped_analytic_node_blocks_scorecard",
    severity: str = "high",
    next_action: str | None = None,
    generated_at: datetime | None = None,
) -> SkippedNodeBlocker:
    """Build a normalized skip blocker from node skip context."""

    inferred_kind = node_kind or classify_optional_analytic_node(alias=alias, node_id=node_id)
    return SkippedNodeBlocker(
        node_id=_required_text(node_id, "node_id"),
        alias=_optional_text(alias),
        node_kind=inferred_kind or "other_optional_analytic",
        reason=_required_text(reason, "reason"),
        missing_input=_required_text(missing_input, "missing_input"),
        owner=_required_text(owner, "owner"),
        phase=_required_text(phase, "phase"),
        downstream_impact=_required_text(downstream_impact, "downstream_impact"),
        allowed_profile=_normalize_profile(allowed_profile) or "dev",
        closeout_blocking_policy=_required_text(
            closeout_blocking_policy,
            "closeout_blocking_policy",
        ),
        scorecard_blocking_policy=_required_text(
            scorecard_blocking_policy,
            "scorecard_blocking_policy",
        ),
        approval_blocking_policy=_required_text(
            approval_blocking_policy,
            "approval_blocking_policy",
        ),
        public_export_blocking_policy=_required_text(
            public_export_blocking_policy,
            "public_export_blocking_policy",
        ),
        blocker_code=_required_text(blocker_code, "blocker_code"),
        severity=_required_text(severity, "severity"),
        next_action=_optional_text(next_action)
        or "Provide the missing input or explicitly downgrade the execution profile.",
        generated_at=generated_at or datetime.now(UTC).replace(microsecond=0),
    )


def evaluate_skip_blocker_policy(
    record: SkippedNodeBlocker,
    *,
    active_profile: str | None,
    surface: str = "scorecard",
) -> SkipBlockerPolicyDecision:
    """Fail closed for serious profiles when skipped analytics feed authority surfaces."""

    surface_name = _normalize_surface(surface)
    profile = _normalize_profile(active_profile)
    if profile not in SERIOUS_SKIP_BLOCKER_PROFILES:
        return SkipBlockerPolicyDecision(
            allowed=True,
            blocking=False,
            code=None,
            reason=f"Profile {profile or 'unknown'} is not a serious closeout profile.",
            record=record,
            surface=surface_name,
        )

    policy = _surface_policy(record, surface_name)
    allowed_profile = _normalize_profile(record.allowed_profile)
    if profile == allowed_profile and not _policy_blocks(policy):
        return SkipBlockerPolicyDecision(
            allowed=True,
            blocking=False,
            code=None,
            reason=f"Skipped node is explicitly allowed for profile {profile}.",
            record=record,
            surface=surface_name,
        )

    code = _surface_blocker_code(record, surface_name)
    if profile != allowed_profile:
        reason = (
            f"Skipped {record.node_kind} node {record.alias or record.node_id} is only "
            f"allowed for profile {record.allowed_profile}; active profile is {profile}."
        )
    else:
        reason = (
            f"Skipped {record.node_kind} node {record.alias or record.node_id} "
            f"blocks {surface_name}: {policy}."
        )
    return SkipBlockerPolicyDecision(
        allowed=False,
        blocking=True,
        code=code,
        reason=reason,
        record=record,
        surface=surface_name,
    )


def classify_optional_analytic_node(
    *,
    alias: str | None,
    node_id: str | None,
    phase: str | None = None,
    node_kind: str | None = None,
) -> str | None:
    """Classify optional analytic node families that require skip blockers."""

    explicit_kind = _normalize_token(node_kind)
    if explicit_kind in OPTIONAL_ANALYTIC_NODE_KINDS:
        return explicit_kind

    text = " ".join(
        item
        for item in (
            str(alias or ""),
            str(node_id or ""),
            str(phase or ""),
        )
        if item
    ).casefold()
    checks = (
        ("transportability", ("transportability", "transport")),
        (
            "normative_arbitration",
            ("normative_arbitration", "normative arbitration", "arbitration"),
        ),
        ("decision_packet", ("decision_packet", "decision packet")),
        ("evaluator", ("evaluator", "evaluation_report", "evaluator_report")),
        ("governance", ("governance", "legal_check", "privacy_check", "quality_gate")),
        ("causal", ("causal", "counterfactual", "distributional", "welfare")),
    )
    for kind, tokens in checks:
        if any(token in text for token in tokens):
            return kind
    return None


def _surface_blocker_code(record: SkippedNodeBlocker, surface: str) -> str:
    if surface == "scorecard":
        return record.blocker_code or "skipped_analytic_node_blocks_scorecard"
    return f"skipped_analytic_node_blocks_{surface}"


def _surface_policy(record: SkippedNodeBlocker, surface: str) -> str:
    return {
        "closeout": record.closeout_blocking_policy,
        "scorecard": record.scorecard_blocking_policy,
        "approval": record.approval_blocking_policy,
        "public_export": record.public_export_blocking_policy,
    }[surface]


def _policy_blocks(policy: str) -> bool:
    lowered = policy.casefold()
    return any(
        token in lowered
        for token in ("block", "fail", "deny", "not_allowed", "not_overridable")
    )


def _normalize_surface(surface: str) -> str:
    normalized = _normalize_token(surface)
    if normalized not in SKIP_BLOCKER_SURFACES:
        raise SkipBlockerContractError(
            "skip_blocker_unknown_surface",
            f"Unknown skip blocker surface: {surface}.",
            field="surface",
        )
    return normalized


def _normalize_profile(profile: str | None) -> str | None:
    return _normalize_token(profile)


def _normalize_token(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().casefold().replace("-", "_").replace(" ", "_")
    return normalized or None


def _required_text(value: object, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise SkipBlockerContractError(
            "skip_blocker_required_field_empty",
            f"Skipped node blocker field is empty: {field}.",
            field=field,
        )
    return text


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
