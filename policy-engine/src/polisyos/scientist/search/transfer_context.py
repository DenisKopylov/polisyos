"""Shared transfer-scope contracts for cross-run search reuse."""

from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime, timedelta
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from polisyos.core.security.tenant_context import get_current_tenant_id_or_none

_SLUG_RE = re.compile(r"[^a-z0-9_.-]+")


class TransferPolicy(BaseModel):
    """Deterministic policy controlling cross-run reuse."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    allow_cross_domain: bool = True
    allow_cross_tenant: bool = False
    ttl_days: int = Field(default=90, ge=1)


class TransferAuditHop(BaseModel):
    """One hop in a transfer chain."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    from_task_family: str = Field(min_length=1)
    from_domain: str = Field(min_length=1)
    to_task_family: str = Field(min_length=1)
    to_domain: str = Field(min_length=1)
    source_run_id: str = Field(min_length=1)
    source_tenant_hash: str | None = None
    target_tenant_hash: str | None = None
    transferred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    provenance_weight: float = Field(default=1.0, ge=0.0, le=1.0)


class TransferContext(BaseModel):
    """Scope of a lesson/frontier publication or transfer target."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    task_family: str = Field(default="policy", min_length=1)
    domain: str = Field(default="isolated", min_length=1)
    run_id: str = Field(default="unknown", min_length=1)
    tenant_hash: str | None = None
    cross_tenant_opt_in: bool = False
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @property
    def tenant_partition(self) -> str:
        return tenant_partition(self.tenant_hash)

    @property
    def task_family_slug(self) -> str:
        return _slug(self.task_family)

    @property
    def domain_slug(self) -> str:
        return _slug(self.domain)


def anonymize_tenant_id(tenant_id: str | None) -> str | None:
    """Convert a raw tenant id to a stable non-reversible hash prefix."""

    raw = str(tenant_id or "").strip()
    if not raw:
        return None
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def tenant_partition(tenant_hash: str | None) -> str:
    """Tenant partition helper."""
    return _slug(tenant_hash or "global")


def build_transfer_hop(
    source: TransferContext,
    target: TransferContext,
    *,
    provenance_weight: float,
) -> TransferAuditHop:
    """Build transfer hop."""
    return TransferAuditHop(
        from_task_family=source.task_family,
        from_domain=source.domain,
        to_task_family=target.task_family,
        to_domain=target.domain,
        source_run_id=source.run_id,
        source_tenant_hash=source.tenant_hash,
        target_tenant_hash=target.tenant_hash,
        provenance_weight=provenance_weight,
    )


def compute_provenance_weight(
    source: TransferContext,
    target: TransferContext,
    *,
    created_at: datetime | None = None,
    policy: TransferPolicy | None = None,
) -> float:
    """Weight transferred knowledge by scope distance and age."""

    active_policy = policy or TransferPolicy()
    if source.task_family != target.task_family:
        return 0.0

    same_tenant = source.tenant_hash == target.tenant_hash
    same_domain = source.domain == target.domain

    if same_tenant and same_domain:
        base = 1.0
    elif same_tenant and active_policy.allow_cross_domain:
        base = 0.65
    elif (
        active_policy.allow_cross_tenant
        and active_policy.allow_cross_domain
        and target.cross_tenant_opt_in
    ):
        base = 0.35
    else:
        return 0.0

    if created_at is None:
        return base

    age = max(timedelta(), target.timestamp - created_at)
    if age > timedelta(days=active_policy.ttl_days * 2):
        return 0.0
    if age > timedelta(days=active_policy.ttl_days):
        return base * 0.5
    return base


def resolve_transfer_context(
    *,
    candidate: Any | None = None,
    context: dict[str, Any] | None = None,
    task_family: str | None = None,
    domain: str | None = None,
    run_id: str | None = None,
    cross_tenant_opt_in: bool | None = None,
    tenant_hash: str | None = None,
) -> TransferContext:
    """Best-effort context derivation shared by lessons and pareto reuse."""

    payload = dict(context or {})
    existing = payload.get("transfer_context")
    if isinstance(existing, TransferContext):
        base = existing
    elif isinstance(existing, dict):
        try:
            base = TransferContext.model_validate(existing)
        except Exception:
            base = None
    else:
        base = None

    resolved_task_family = (
        task_family
        or _string_or_none(payload.get("task_family"))
        or _nested_string(payload, "policy_search_context", "task_family")
        or _candidate_metadata(candidate, "task_family")
        or ("discovery" if _looks_like_discovery_candidate(candidate) else "policy")
    )
    resolved_domain = (
        domain
        or _string_or_none(payload.get("policy_request_domain"))
        or _string_or_none(payload.get("domain"))
        or _candidate_domain(candidate)
        or _candidate_metadata(candidate, "domain")
        or None
    )
    resolved_run_id = (
        run_id
        or _string_or_none(payload.get("source_run_id"))
        or _string_or_none(payload.get("run_id"))
        or (base.run_id if base is not None else None)
        or "unknown"
    )
    resolved_tenant_hash = (
        tenant_hash
        or _string_or_none(payload.get("tenant_hash"))
        or anonymize_tenant_id(get_current_tenant_id_or_none())
        or (base.tenant_hash if base is not None else None)
    )
    return TransferContext(
        task_family=resolved_task_family or (base.task_family if base is not None else "policy"),
        domain=resolved_domain or _isolated_domain(resolved_run_id),
        run_id=resolved_run_id,
        tenant_hash=resolved_tenant_hash,
        cross_tenant_opt_in=(
            bool(cross_tenant_opt_in)
            if cross_tenant_opt_in is not None
            else bool(
                payload.get("cross_tenant_opt_in")
                if "cross_tenant_opt_in" in payload
                else (base.cross_tenant_opt_in if base is not None else False)
            )
        ),
        timestamp=base.timestamp if base is not None else datetime.now(UTC),
    )


def lesson_hint_payload(card: Any) -> dict[str, Any]:
    """Compact transfer-aware payload for prompt/generation contexts."""

    return {
        "summary": str(getattr(card, "summary", "") or ""),
        "failure_type": str(getattr(card, "failure_type", "") or ""),
        "remediation_hint": getattr(card, "remediation_hint", None),
        "trust_level": str(
            getattr(getattr(card, "trust_level", None), "value", getattr(card, "trust_level", ""))
        ),
        "provenance_weight": float(getattr(card, "provenance_weight", 1.0) or 0.0),
        "domain": str(getattr(card, "domain", "isolated") or "isolated"),
        "task_family": str(getattr(card, "task_family", "policy") or "policy"),
    }


def _isolated_domain(run_id: str | None) -> str:
    normalized = _slug(str(run_id or "unknown").strip() or "unknown")
    return f"isolated::{normalized}"


def _candidate_domain(candidate: Any | None) -> str | None:
    if candidate is None:
        return None
    if isinstance(candidate, dict):
        trinity_bundle = candidate.get("trinity_bundle") or {}
        problem_frame = trinity_bundle.get("problem_frame") or {}
        raw_domain = problem_frame.get("domain")
        if isinstance(raw_domain, dict):
            raw_domain = raw_domain.get("value")
        if raw_domain is not None:
            return str(getattr(raw_domain, "value", raw_domain)).strip() or None
        metadata = candidate.get("metadata")
        if isinstance(metadata, dict):
            raw_domain = metadata.get("domain")
            if raw_domain is not None:
                return str(raw_domain).strip() or None
        return None
    bundle = getattr(candidate, "trinity_bundle", None)
    if bundle is not None:
        problem_frame = getattr(bundle, "problem_frame", None)
        raw_domain = getattr(problem_frame, "domain", None)
        if raw_domain is not None:
            return str(getattr(raw_domain, "value", raw_domain)).strip() or None
    return _candidate_metadata(candidate, "domain")


def _candidate_metadata(candidate: Any | None, key: str) -> str | None:
    metadata = getattr(candidate, "metadata", None)
    if isinstance(candidate, dict):
        metadata = candidate.get("metadata", metadata)
    if isinstance(metadata, dict):
        value = metadata.get(key)
        if value is not None:
            return str(value).strip() or None
    return None


def _looks_like_discovery_candidate(candidate: Any | None) -> bool:
    if candidate is None:
        return False
    if isinstance(candidate, dict):
        return "graph" in candidate or "hypothesis_id" in candidate
    return hasattr(candidate, "graph") or hasattr(candidate, "hypothesis_id")


def _nested_string(payload: dict[str, Any], key: str, nested_key: str) -> str | None:
    nested = payload.get(key)
    if isinstance(nested, dict):
        return _string_or_none(nested.get(nested_key))
    return None


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _slug(value: str) -> str:
    normalized = value.strip().lower() or "unknown"
    return _SLUG_RE.sub("_", normalized)


__all__ = [
    "TransferAuditHop",
    "TransferContext",
    "TransferPolicy",
    "anonymize_tenant_id",
    "build_transfer_hop",
    "compute_provenance_weight",
    "lesson_hint_payload",
    "resolve_transfer_context",
    "tenant_partition",
]
