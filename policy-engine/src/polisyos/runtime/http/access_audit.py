"""Append-only audit logging for runtime reads and authorization decisions."""

from __future__ import annotations

import logging
import os
import threading
import time
import uuid
from enum import StrEnum
from functools import partial
from typing import TYPE_CHECKING, Any, Literal

from anyio import to_thread
from pydantic import BaseModel, ConfigDict

from polisyos.common.serialization import fast_json_dumps

if TYPE_CHECKING:
    from pathlib import Path

    from fastapi import Request

logger = logging.getLogger("polisyos.runtime.authorization_audit")


class RuntimeAuthorizationAuditError(RuntimeError):
    """Signal that a mutation decision could not reach the authority audit."""


class RuntimeAuthorizationOutcome(StrEnum):
    """Closed terminal authorization outcomes."""

    ALLOW = "allow"
    DENY = "deny"


class RuntimeAuthorizationAuditEvent(BaseModel):
    """Strict terminal event appended to the existing runtime access audit."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["polisyos.runtime.authorization_audit.v1"] = (
        "polisyos.runtime.authorization_audit.v1"
    )
    event_type: Literal["runtime.authorization.decision"] = (
        "runtime.authorization.decision"
    )
    timestamp: float
    request_id: str
    outcome: RuntimeAuthorizationOutcome
    denial_reason: str
    method: str
    route_path: str
    permission: str
    resource_id: str
    resource_digest: str
    resource_kind: str
    binding_authority: str
    step_up_class: str
    step_up_outcome: Literal["not_required", "verified", "denied", "unresolved"]
    subject: str
    tenant_id: str
    principal_type: str
    opa_policy: str
    opa_reasons: list[str]


class RuntimeDataAccessAuditTrail:
    """Persist data-access audit events for compliance review."""

    def __init__(self, *, path: Path) -> None:
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def append(self, entry: dict[str, Any]) -> None:
        line = fast_json_dumps(entry, sort_keys=False) + "\n"
        with self._lock, self._path.open("a", encoding="utf-8") as handle:
            handle.write(line)
            handle.flush()
            os.fsync(handle.fileno())


def emit_runtime_authorization_audit(
    request: Request,
    *,
    outcome: RuntimeAuthorizationOutcome,
    denial_reason: str = "",
    step_up_outcome: Literal["verified", "denied", "unresolved"] | None = None,
    raise_on_failure: bool,
) -> bool:
    """Append one idempotent terminal authorization admission to ``access.jsonl``.

    The request body and all bearer/step-up assertion material are deliberately
    absent from this contract. An allow-path append failure raises so a handler
    cannot execute without its authorization receipt. The allow outcome records
    admission under the immutable bound context; it is not a handler-success
    assertion.
    """
    if not isinstance(outcome, RuntimeAuthorizationOutcome):
        raise TypeError("outcome must be a RuntimeAuthorizationOutcome")
    state = request.state
    if getattr(state, "runtime_authorization_audit_terminal", False):
        return bool(getattr(state, "runtime_authorization_audit_emitted", False))

    requirement = getattr(state, "authz_route_requirement", None)
    permission_value = getattr(getattr(requirement, "permission", None), "value", "")
    matched_route = getattr(state, "authz_matched_route", None)
    route_path = getattr(matched_route, "path_template", None) or str(request.url.path)
    bound_resource = (
        getattr(state, "authz_bound_resource", None)
        if getattr(state, "authz_resource_frozen", False) is True
        else None
    )
    effective_scope = getattr(state, "authz_effective_scope", None)
    access_scope = effective_scope or getattr(state, "access_scope", None)
    claims = getattr(state, "user_claims", None)
    subject = (
        getattr(access_scope, "user_sub", None)
        or getattr(access_scope, "spiffe_id", None)
        or getattr(claims, "sub", None)
        or "anonymous"
    )
    tenant_id = (
        getattr(access_scope, "tenant_id", None)
        or getattr(claims, "tenant_id", None)
        or ""
    )
    principal_type = getattr(access_scope, "principal_type", None) or (
        "user" if claims is not None else "anonymous"
    )
    step_requirement = getattr(state, "authz_step_up_requirement", None)
    step_class = getattr(getattr(step_requirement, "step_up_class", None), "value", "")
    if step_requirement is None:
        resolved_step_outcome = "not_required"
    elif step_up_outcome is not None:
        resolved_step_outcome = step_up_outcome
    elif getattr(state, "step_up_verification", None) is not None:
        resolved_step_outcome = "verified"
    else:
        resolved_step_outcome = "unresolved"
    request_id = getattr(state, "request_id", None)
    if not isinstance(request_id, str) or not request_id:
        request_id = request.headers.get("X-Request-ID", "").strip() or str(uuid.uuid4())
        state.request_id = request_id
    event = RuntimeAuthorizationAuditEvent(
        timestamp=time.time(),
        request_id=request_id,
        outcome=outcome,
        denial_reason=(denial_reason if outcome is RuntimeAuthorizationOutcome.DENY else ""),
        method=request.method.upper(),
        route_path=route_path,
        permission=str(permission_value),
        resource_id=str(getattr(bound_resource, "resource_id", "")),
        resource_digest=str(getattr(bound_resource, "resource_digest", "")),
        resource_kind=str(getattr(bound_resource, "resource_kind", "")),
        binding_authority=str(
            getattr(getattr(bound_resource, "authority", None), "value", "")
        ),
        step_up_class=str(step_class),
        step_up_outcome=resolved_step_outcome,
        subject=str(subject),
        tenant_id=str(tenant_id),
        principal_type=str(principal_type),
        opa_policy=str(getattr(state, "authz_policy", "") or ""),
        opa_reasons=[str(reason) for reason in getattr(state, "authz_reasons", ())],
    )
    app_state = getattr(getattr(request, "app", object()), "state", object())
    container = getattr(app_state, "runtime_container", None)
    audit_trail = getattr(container, "runtime_access_audit", None)
    if audit_trail is None:
        audit_trail = getattr(app_state, "runtime_access_audit", None)
    append = getattr(audit_trail, "append", None)
    try:
        if not callable(append):
            raise RuntimeAuthorizationAuditError(
                "Runtime authorization access-audit trail is unavailable"
            )
        append(event.model_dump(mode="json"))
    except Exception as exc:
        state.runtime_authorization_audit_terminal = True
        state.runtime_authorization_audit_emitted = False
        if raise_on_failure:
            if isinstance(exc, RuntimeAuthorizationAuditError):
                raise
            raise RuntimeAuthorizationAuditError(
                "Runtime authorization access-audit append failed"
            ) from exc
        logger.exception("Authorization denial audit append failed")
        return False
    state.runtime_authorization_audit_terminal = True
    state.runtime_authorization_audit_emitted = True
    return True


async def emit_runtime_authorization_audit_async(
    request: Request,
    *,
    outcome: RuntimeAuthorizationOutcome,
    denial_reason: str = "",
    step_up_outcome: Literal["verified", "denied", "unresolved"] | None = None,
    raise_on_failure: bool,
) -> bool:
    """Append one decision without running durable audit I/O on the ASGI loop."""
    return await to_thread.run_sync(
        partial(
            emit_runtime_authorization_audit,
            request,
            outcome=outcome,
            denial_reason=denial_reason,
            step_up_outcome=step_up_outcome,
            raise_on_failure=raise_on_failure,
        )
    )


__all__ = [
    "RuntimeAuthorizationAuditError",
    "RuntimeAuthorizationAuditEvent",
    "RuntimeAuthorizationOutcome",
    "RuntimeDataAccessAuditTrail",
    "emit_runtime_authorization_audit",
    "emit_runtime_authorization_audit_async",
]
