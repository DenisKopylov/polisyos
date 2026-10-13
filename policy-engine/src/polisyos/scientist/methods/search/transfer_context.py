"""Shared transfer-scope contracts for cross-run search reuse."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from polisyos.core.security import (
    get_current_access_scope_or_none,
    get_current_tenant_id_or_none,
)

_SLUG_RE = re.compile(r"[^a-z0-9_.-]+")


class TransferTenantScopeStatus(str, Enum):
    """Tenant identity quality carried across candidate transfer boundaries."""

    UNKNOWN = "unknown"
    AUTHENTICATED = "authenticated"
    DECLARED_UNSCOPED = "declared_unscoped"


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
    source_tenant_scope_status: TransferTenantScopeStatus = TransferTenantScopeStatus.UNKNOWN
    target_tenant_scope_status: TransferTenantScopeStatus = TransferTenantScopeStatus.UNKNOWN
    transferred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    provenance_weight: float = Field(default=1.0, ge=0.0, le=1.0)


class TransferContext(BaseModel):
    """Scope of a lesson/frontier publication or transfer target."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    task_family: str = Field(default="policy", min_length=1)
    domain: str = Field(default="isolated", min_length=1)
    run_id: str = Field(default="unknown", min_length=1)
    tenant_hash: str | None = None
    tenant_scope_status: TransferTenantScopeStatus = TransferTenantScopeStatus.UNKNOWN
    cross_tenant_opt_in: bool = False
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @model_validator(mode="after")
    def _validate_tenant_scope(self) -> TransferContext:
        if self.tenant_hash is not None and not self.tenant_hash.strip():
            raise ValueError("tenant hash must be a non-empty identity")
        if (
            self.tenant_scope_status is TransferTenantScopeStatus.AUTHENTICATED
            and self.tenant_hash is None
        ):
            raise ValueError("authenticated transfer scope requires a tenant hash")
        if (
            self.tenant_scope_status is TransferTenantScopeStatus.DECLARED_UNSCOPED
            and self.tenant_hash is not None
        ):
            raise ValueError("declared unscoped transfer scope cannot carry a tenant hash")
        return self

    @property
    def tenant_partition(self) -> str:
        return tenant_partition(self.tenant_hash)

    @property
    def task_family_slug(self) -> str:
        return _slug(self.task_family)

    @property
    def domain_slug(self) -> str:
        return _slug(self.domain)


class TransferSourceScope(BaseModel):
    """Producer-owned source identity and its scope-quality limitation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["2.0"] = "2.0"
    task_family: str = Field(min_length=1)
    domain: str = Field(min_length=1)
    tenant_kind: Literal["unscoped", "tenant"]
    tenant_hash: str | None = Field(...)
    tenant_scope_status: TransferTenantScopeStatus

    @model_validator(mode="after")
    def _validate_scope_binding(self) -> TransferSourceScope:
        if self.tenant_hash is not None and not self.tenant_hash.strip():
            raise ValueError("tenant source scope requires a non-empty identity")
        if self.tenant_kind == "unscoped" and self.tenant_hash is not None:
            raise ValueError("unscoped source scope cannot carry a tenant hash")
        if self.tenant_kind == "tenant" and self.tenant_hash is None:
            raise ValueError("tenant source scope requires an explicit tenant hash")
        if (
            self.tenant_scope_status is TransferTenantScopeStatus.AUTHENTICATED
            and self.tenant_hash is None
        ):
            raise ValueError("authenticated source scope requires a tenant hash")
        if (
            self.tenant_scope_status is TransferTenantScopeStatus.DECLARED_UNSCOPED
            and self.tenant_hash is not None
        ):
            raise ValueError("declared unscoped source scope cannot carry a tenant hash")
        if (self.tenant_kind == "unscoped") != (self.tenant_hash is None):
            raise ValueError("tenant kind must match the nullable tenant hash")
        return self

    @classmethod
    def from_context(cls, context: TransferContext) -> TransferSourceScope:
        return cls(
            schema_version="2.0",
            task_family=context.task_family,
            domain=context.domain,
            tenant_kind="unscoped" if context.tenant_hash is None else "tenant",
            tenant_hash=context.tenant_hash,
            tenant_scope_status=context.tenant_scope_status,
        )

    def context(self, *, run_id: str = "namespace_scan") -> TransferContext:
        return TransferContext(
            task_family=self.task_family,
            domain=self.domain,
            tenant_hash=self.tenant_hash,
            tenant_scope_status=self.tenant_scope_status,
            run_id=run_id,
        )


class TransferPathBinding(BaseModel):
    """A versioned locator commitment; source identity comes from its body."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal["bound", "legacy_unbound", "malformed"]
    scope_digest: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _validate_locator_state(self) -> TransferPathBinding:
        if (self.status == "bound") != (self.scope_digest is not None):
            raise ValueError("only a valid versioned locator carries a scope digest")
        return self


class TransferScopeRefusalReason(str, Enum):
    """Fail-closed outcomes for source-scope resolution."""

    LEGACY_PATH_UNBOUND = "legacy_path_unbound"
    MALFORMED_PATH = "malformed_versioned_path"
    SOURCE_BINDING_MISSING = "source_binding_missing"
    PATH_BODY_MISMATCH = "path_body_scope_mismatch"
    ENTRY_SCOPE_MISMATCH = "entry_scope_mismatch"
    CROSS_TENANT_NOT_AUTHORIZED = "cross_tenant_not_authorized"
    INVALID_SOURCE_BODY = "invalid_source_body"
    INVALID_REQUEST_SCOPE = "invalid_request_scope"
    AUTHENTICATED_SCOPE_MISMATCH = "authenticated_scope_mismatch"
    REQUEST_TENANT_CONTEXT_MISMATCH = "request_tenant_context_mismatch"
    UNSCOPED_SCOPE_MISMATCH = "unscoped_scope_mismatch"
    TENANT_SCOPE_STATUS_MISMATCH = "tenant_scope_status_mismatch"
    TENANT_SCOPE_UNKNOWN = "tenant_scope_unknown"


class TransferScopeRefusal(BaseModel):
    """Typed refusal without exposing the tenant-bearing filesystem path."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    reason: TransferScopeRefusalReason
    location_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class TransferScopeRefusedError(RuntimeError):
    """Raised when a consumer cannot bind a source path to its persisted owner."""

    def __init__(self, refusals: list[TransferScopeRefusal]) -> None:
        self.refusals = tuple(refusals)
        super().__init__("transfer source scope could not be established")


def _scope_digest(scope: TransferSourceScope) -> str:
    """Hash the complete typed source scope using canonical JSON."""
    encoded = json.dumps(
        scope.model_dump(mode="json", exclude_none=False),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def transfer_scope_path_parts(context: TransferContext) -> tuple[str, str]:
    """Return a short versioned locator bound to the complete scope body."""
    return ("v3", _scope_digest(TransferSourceScope.from_context(context)))


def decode_transfer_scope_path(parts: tuple[str, ...]) -> TransferPathBinding:
    """Recognize a versioned locator without treating it as source authority."""
    if len(parts) == 3 or (len(parts) == 2 and parts[0] == "v2"):
        return TransferPathBinding(status="legacy_unbound")
    if len(parts) == 2 and parts[0] == "v3" and re.fullmatch(r"[0-9a-f]{64}", parts[1]) is not None:
        return TransferPathBinding(status="bound", scope_digest=parts[1])
    return TransferPathBinding(status="malformed")


def transfer_scope_refusal(
    path_binding: TransferPathBinding,
    body_scope: TransferSourceScope | None,
    path: Path,
) -> TransferScopeRefusal | None:
    """Reconcile a path commitment and its complete persisted source body."""
    if path_binding.status == "legacy_unbound":
        reason = TransferScopeRefusalReason.LEGACY_PATH_UNBOUND
    elif path_binding.status == "malformed":
        reason = TransferScopeRefusalReason.MALFORMED_PATH
    elif body_scope is None:
        reason = TransferScopeRefusalReason.SOURCE_BINDING_MISSING
    elif path_binding.scope_digest != _scope_digest(body_scope):
        reason = TransferScopeRefusalReason.PATH_BODY_MISMATCH
    else:
        return None
    return TransferScopeRefusal(
        reason=reason,
        location_sha256=hashlib.sha256(str(path).encode("utf-8")).hexdigest(),
    )


def make_transfer_scope_refusal(
    path: Path, reason: TransferScopeRefusalReason
) -> TransferScopeRefusal:
    """Build a typed refusal whose locator does not disclose its raw path."""
    return TransferScopeRefusal(
        reason=reason,
        location_sha256=hashlib.sha256(str(path).encode("utf-8")).hexdigest(),
    )


def anonymize_tenant_id(tenant_id: str | None) -> str | None:
    """Convert a raw tenant id to a stable non-reversible hash prefix."""

    raw = str(tenant_id or "").strip()
    if not raw:
        return None
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def tenant_partition(tenant_hash: str | None) -> str:
    """Return the partition locator for a valid tenant hash or an unscoped input."""
    if tenant_hash is not None and (not isinstance(tenant_hash, str) or not tenant_hash.strip()):
        raise ValueError("tenant hash must be a non-empty identity")
    if tenant_hash is None:
        return "n"
    return "t" + hashlib.sha256(tenant_hash.encode("utf-8")).hexdigest()


def tenant_hash_from_partition(partition: str) -> str | None:
    """Refuse to infer source identity from a non-authoritative path locator."""
    raise ValueError("tenant locators do not encode identity; a verified source body is required")


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
        source_tenant_scope_status=source.tenant_scope_status,
        target_tenant_scope_status=target.tenant_scope_status,
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

    if source.tenant_scope_status is not target.tenant_scope_status:
        return 0.0
    same_scope = source.tenant_hash == target.tenant_hash
    same_domain = source.domain == target.domain

    if same_scope and same_domain:
        base = 1.0
    elif same_scope and active_policy.allow_cross_domain:
        base = 0.65
    elif (
        active_policy.allow_cross_tenant
        and active_policy.allow_cross_domain
        and target.cross_tenant_opt_in
        and source.tenant_scope_status is TransferTenantScopeStatus.AUTHENTICATED
        and target.tenant_scope_status is TransferTenantScopeStatus.AUTHENTICATED
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
    context: Mapping[str, Any] | TransferContext | None = None,
    transfer_context: TransferContext | None = None,
    task_family: str | None = None,
    domain: str | None = None,
    run_id: str | None = None,
    fallback_run_id: str | None = None,
    cross_tenant_opt_in: bool | None = None,
    tenant_hash: str | None = None,
    tenant_hash_is_explicit: bool = False,
) -> TransferContext:
    """Resolve scope after reconciling every supplied declaration.

    Defaults on typed contexts remain fallback values, not declarations: only
    model_fields_set participates in conflict detection. Mapping keys, explicit
    keyword values, and set fields on typed contexts are reconciled before a
    selected context or candidate fallback can influence the result. `fallback_run_id`
    supplies a run identity only when no declaration exists; it never competes with one.
    """

    def refuse(reason: TransferScopeRefusalReason) -> None:
        raise TransferScopeRefusedError(
            [make_transfer_scope_refusal(Path("current-request-scope"), reason)]
        )

    def validated_typed(value: object) -> TransferContext:
        if not isinstance(value, TransferContext):
            refuse(TransferScopeRefusalReason.INVALID_REQUEST_SCOPE)
        try:
            return TransferContext.model_validate(value.model_dump(mode="python"))
        except (ValidationError, TypeError, ValueError):
            refuse(TransferScopeRefusalReason.INVALID_REQUEST_SCOPE)

    def validated_nested_mapping(value: object) -> tuple[TransferContext, set[str]]:
        if not isinstance(value, Mapping) or any(not isinstance(key, str) for key in value):
            refuse(TransferScopeRefusalReason.INVALID_REQUEST_SCOPE)
        raw = dict(value)
        if not {"task_family", "domain", "run_id"} <= raw.keys():
            refuse(TransferScopeRefusalReason.INVALID_REQUEST_SCOPE)
        try:
            model = TransferContext.model_validate(raw)
        except (ValidationError, TypeError, ValueError):
            refuse(TransferScopeRefusalReason.INVALID_REQUEST_SCOPE)
        return model, set(raw)

    def parsed_value(field_name: str, value: object) -> object:
        if field_name in {"task_family", "domain", "run_id"}:
            if not isinstance(value, str) or not value.strip():
                refuse(TransferScopeRefusalReason.INVALID_REQUEST_SCOPE)
            return value
        if field_name == "tenant_hash":
            if value is not None and (not isinstance(value, str) or not value.strip()):
                refuse(TransferScopeRefusalReason.INVALID_REQUEST_SCOPE)
            return value
        if field_name == "tenant_scope_status":
            try:
                return TransferTenantScopeStatus(value)
            except (TypeError, ValueError):
                refuse(TransferScopeRefusalReason.INVALID_REQUEST_SCOPE)
        if field_name == "cross_tenant_opt_in":
            if type(value) is not bool:
                refuse(TransferScopeRefusalReason.INVALID_REQUEST_SCOPE)
            return value
        if field_name == "timestamp":
            try:
                return TransferContext.model_validate({"timestamp": value}).timestamp
            except (ValidationError, TypeError, ValueError):
                refuse(TransferScopeRefusalReason.INVALID_REQUEST_SCOPE)
        refuse(TransferScopeRefusalReason.INVALID_REQUEST_SCOPE)

    declarations: dict[str, list[object]] = {
        "task_family": [],
        "domain": [],
        "run_id": [],
        "tenant_hash": [],
        "tenant_scope_status": [],
        "cross_tenant_opt_in": [],
        "timestamp": [],
    }

    def declare(field_name: str, value: object) -> None:
        declarations[field_name].append(parsed_value(field_name, value))

    def declare_typed(model: TransferContext, fields_set: set[str]) -> None:
        for field_name in declarations:
            if field_name in fields_set:
                declare(field_name, getattr(model, field_name))

    def declare_outer_mapping(payload: Mapping[str, Any]) -> None:
        if any(not isinstance(key, str) for key in payload):
            refuse(TransferScopeRefusalReason.INVALID_REQUEST_SCOPE)
        aliases = {
            "task_family": ("task_family",),
            "domain": ("domain", "policy_request_domain"),
            "run_id": ("run_id", "source_run_id"),
            "tenant_hash": ("tenant_hash",),
            "tenant_scope_status": ("tenant_scope_status",),
            "cross_tenant_opt_in": ("cross_tenant_opt_in",),
            "timestamp": ("timestamp",),
        }
        for canonical, keys in aliases.items():
            for key in keys:
                if key in payload:
                    declare(canonical, payload[key])
        if "policy_search_context" in payload:
            nested = payload["policy_search_context"]
            if not isinstance(nested, Mapping) or any(not isinstance(key, str) for key in nested):
                refuse(TransferScopeRefusalReason.INVALID_REQUEST_SCOPE)
            for field_name in ("task_family", "domain"):
                if field_name in nested:
                    declare(field_name, nested[field_name])

    base: TransferContext | None = None
    if context is None:
        pass
    elif isinstance(context, TransferContext):
        base = validated_typed(context)
        declare_typed(base, set(context.model_fields_set))
    elif isinstance(context, Mapping):
        declare_outer_mapping(context)
        if "transfer_context" in context and context["transfer_context"] is not None:
            nested = context["transfer_context"]
            if isinstance(nested, TransferContext):
                base = validated_typed(nested)
                declare_typed(base, set(nested.model_fields_set))
            else:
                base, present_fields = validated_nested_mapping(nested)
                declare_typed(base, present_fields)
    else:
        refuse(TransferScopeRefusalReason.INVALID_REQUEST_SCOPE)

    if transfer_context is not None:
        selected_context = validated_typed(transfer_context)
        declare_typed(selected_context, set(transfer_context.model_fields_set))
        base = selected_context

    if type(tenant_hash_is_explicit) is not bool:
        refuse(TransferScopeRefusalReason.INVALID_REQUEST_SCOPE)
    if fallback_run_id is not None and (
        not isinstance(fallback_run_id, str) or not fallback_run_id.strip()
    ):
        refuse(TransferScopeRefusalReason.INVALID_REQUEST_SCOPE)
    for value, field_name in (
        (task_family, "task_family"),
        (domain, "domain"),
        (run_id, "run_id"),
    ):
        if value is not None:
            declare(field_name, value)
    if cross_tenant_opt_in is not None:
        declare("cross_tenant_opt_in", cross_tenant_opt_in)
    if tenant_hash_is_explicit or tenant_hash is not None:
        declare("tenant_hash", tenant_hash)

    access_scope = get_current_access_scope_or_none()
    routed_tenant_id = get_current_tenant_id_or_none()

    def reconciled(
        field_name: str,
        mismatch_reason: TransferScopeRefusalReason,
    ) -> tuple[bool, object | None]:
        values = declarations[field_name]
        if not values:
            return False, None
        first = values[0]
        if any(value != first for value in values[1:]):
            reason = mismatch_reason
            if field_name == "tenant_hash" and access_scope is not None:
                reason = TransferScopeRefusalReason.AUTHENTICATED_SCOPE_MISMATCH
            refuse(reason)
        return True, first

    has_task, declared_task = reconciled(
        "task_family", TransferScopeRefusalReason.INVALID_REQUEST_SCOPE
    )
    has_domain, declared_domain = reconciled(
        "domain", TransferScopeRefusalReason.INVALID_REQUEST_SCOPE
    )
    has_run, declared_run = reconciled("run_id", TransferScopeRefusalReason.INVALID_REQUEST_SCOPE)
    has_hash, declared_hash = reconciled(
        "tenant_hash", TransferScopeRefusalReason.REQUEST_TENANT_CONTEXT_MISMATCH
    )
    has_status, declared_status = reconciled(
        "tenant_scope_status", TransferScopeRefusalReason.TENANT_SCOPE_STATUS_MISMATCH
    )
    has_opt_in, declared_opt_in = reconciled(
        "cross_tenant_opt_in", TransferScopeRefusalReason.INVALID_REQUEST_SCOPE
    )
    has_timestamp, declared_timestamp = reconciled(
        "timestamp", TransferScopeRefusalReason.INVALID_REQUEST_SCOPE
    )

    resolved_task_family = (
        declared_task
        if has_task
        else (base.task_family if base is not None else None)
        or _candidate_metadata(candidate, "task_family")
        or ("discovery" if _looks_like_discovery_candidate(candidate) else "policy")
    )
    resolved_domain = (
        declared_domain
        if has_domain
        else (base.domain if base is not None else None)
        or _candidate_domain(candidate)
        or _candidate_metadata(candidate, "domain")
        or None
    )
    resolved_run_id = (
        declared_run
        if has_run
        else fallback_run_id or (base.run_id if base is not None else None) or "unknown"
    )
    supplied_hash = declared_hash if has_hash else (base.tenant_hash if base is not None else None)
    requested_status = (
        declared_status
        if has_status
        else (base.tenant_scope_status if base is not None else TransferTenantScopeStatus.UNKNOWN)
    )
    requested_status = TransferTenantScopeStatus(requested_status)
    requested_opt_in = (
        declared_opt_in if has_opt_in else (base.cross_tenant_opt_in if base is not None else False)
    )
    requested_timestamp = (
        declared_timestamp
        if has_timestamp
        else (base.timestamp if base is not None else datetime.now(UTC))
    )

    if access_scope is not None:
        if routed_tenant_id is not None and routed_tenant_id != access_scope.tenant_id:
            refuse(TransferScopeRefusalReason.REQUEST_TENANT_CONTEXT_MISMATCH)
        authenticated_hash = anonymize_tenant_id(access_scope.tenant_id)
        if requested_status is TransferTenantScopeStatus.DECLARED_UNSCOPED:
            refuse(TransferScopeRefusalReason.AUTHENTICATED_SCOPE_MISMATCH)
        if has_hash and supplied_hash is not None and supplied_hash != authenticated_hash:
            refuse(TransferScopeRefusalReason.AUTHENTICATED_SCOPE_MISMATCH)
        resolved_hash = authenticated_hash
        resolved_status = TransferTenantScopeStatus.AUTHENTICATED
    elif routed_tenant_id is not None:
        routed_hash = anonymize_tenant_id(routed_tenant_id)
        if requested_status is TransferTenantScopeStatus.DECLARED_UNSCOPED:
            refuse(TransferScopeRefusalReason.UNSCOPED_SCOPE_MISMATCH)
        if has_hash and supplied_hash is not None and supplied_hash != routed_hash:
            refuse(TransferScopeRefusalReason.REQUEST_TENANT_CONTEXT_MISMATCH)
        resolved_hash = supplied_hash if has_hash and supplied_hash is not None else routed_hash
        resolved_status = TransferTenantScopeStatus.UNKNOWN
    elif requested_status is TransferTenantScopeStatus.DECLARED_UNSCOPED:
        if supplied_hash is not None:
            refuse(TransferScopeRefusalReason.UNSCOPED_SCOPE_MISMATCH)
        resolved_hash = None
        resolved_status = TransferTenantScopeStatus.DECLARED_UNSCOPED
    else:
        if requested_status is TransferTenantScopeStatus.AUTHENTICATED and supplied_hash is None:
            refuse(TransferScopeRefusalReason.INVALID_REQUEST_SCOPE)
        resolved_hash = supplied_hash
        # Serialized or caller-supplied "authenticated" is never proof.
        resolved_status = TransferTenantScopeStatus.UNKNOWN

    return TransferContext(
        task_family=str(
            resolved_task_family or (base.task_family if base is not None else "policy")
        ),
        domain=str(resolved_domain or _isolated_domain(str(resolved_run_id))),
        run_id=str(resolved_run_id),
        tenant_hash=resolved_hash,
        tenant_scope_status=resolved_status,
        cross_tenant_opt_in=requested_opt_in,
        timestamp=requested_timestamp,
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
    "TransferPathBinding",
    "TransferPolicy",
    "TransferScopeRefusal",
    "TransferScopeRefusalReason",
    "TransferScopeRefusedError",
    "TransferSourceScope",
    "TransferTenantScopeStatus",
    "anonymize_tenant_id",
    "build_transfer_hop",
    "compute_provenance_weight",
    "decode_transfer_scope_path",
    "lesson_hint_payload",
    "resolve_transfer_context",
    "make_transfer_scope_refusal",
    "tenant_hash_from_partition",
    "transfer_scope_path_parts",
    "transfer_scope_refusal",
    "tenant_partition",
]
