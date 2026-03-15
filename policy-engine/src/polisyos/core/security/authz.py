"""Authorization client for OPA sidecar with fail-closed semantics."""
from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

from polisyos.common.logger import get_logger
from polisyos.core.cache import TTLCache
from polisyos.core.canon import truncated_hash
from polisyos.core.observability import get_metrics
from polisyos.core.security.access_scope import AccessScope

if TYPE_CHECKING:
    import aiohttp

logger = get_logger("polisyos.security.authz")


class AuthzDecision(str, Enum):
    ALLOW = "allow"
    DENY = "deny"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class AuthzResult:
    decision: AuthzDecision
    policy: str
    reasons: tuple[str, ...] = ()
    latency_ms: float = 0.0
    cached: bool = False
    audit_entry: dict[str, Any] = field(default_factory=dict)

    @property
    def is_allowed(self) -> bool:
        return self.decision == AuthzDecision.ALLOW


@dataclass(frozen=True, slots=True)
class AuthzInput:
    request_method: str
    request_path: str
    request_headers: dict[str, str]

    identity_tenant_id: str
    identity_cell_id: str | None
    identity_principal_type: str
    identity_roles: frozenset[str]
    identity_mfa_verified: bool
    identity_sub: str = ""
    identity_spiffe_id: str = ""

    peer_spiffe_id: str = ""

    resource_tenant_id: str = ""
    resource_kind: str = ""
    resource_artifact_id: str = ""
    resource_pii_tier: str = "none"
    resource_metric_id: str = ""
    resource_columns: tuple[dict[str, str], ...] = ()
    resource_requires_anonymization: bool = False

    @classmethod
    def for_http_request(
        cls,
        *,
        request_method: str,
        request_path: str,
        request_headers: dict[str, str],
        scope: AccessScope,
        peer_spiffe_id: str = "",
        resource_tenant_id: str = "",
        resource_kind: str = "",
        resource_artifact_id: str = "",
        resource_pii_tier: str = "none",
        resource_metric_id: str = "",
        resource_columns: tuple[dict[str, str], ...] = (),
        resource_requires_anonymization: bool = False,
    ) -> "AuthzInput":
        return cls(
            request_method=request_method,
            request_path=request_path,
            request_headers=request_headers,
            identity_tenant_id=scope.tenant_id,
            identity_cell_id=scope.cell_id,
            identity_principal_type=scope.principal_type,
            identity_roles=frozenset(role.value for role in scope.roles),
            identity_mfa_verified=scope.mfa_verified,
            identity_sub=scope.user_sub,
            identity_spiffe_id=scope.spiffe_id,
            peer_spiffe_id=peer_spiffe_id,
            resource_tenant_id=resource_tenant_id,
            resource_kind=resource_kind,
            resource_artifact_id=resource_artifact_id,
            resource_pii_tier=resource_pii_tier,
            resource_metric_id=resource_metric_id,
            resource_columns=resource_columns,
            resource_requires_anonymization=resource_requires_anonymization,
        )

    @classmethod
    def for_cas_artifact(
        cls,
        *,
        request_method: str,
        request_path: str,
        request_headers: dict[str, str],
        scope: AccessScope,
        artifact_id: str,
        owner_tenant_id: str,
        peer_spiffe_id: str = "",
    ) -> "AuthzInput":
        return cls.for_http_request(
            request_method=request_method,
            request_path=request_path,
            request_headers=request_headers,
            scope=scope,
            peer_spiffe_id=peer_spiffe_id,
            resource_tenant_id=owner_tenant_id,
            resource_kind="cas_artifact",
            resource_artifact_id=artifact_id,
        )

    @classmethod
    def for_data_access(
        cls,
        *,
        request_method: str,
        request_path: str,
        request_headers: dict[str, str],
        scope: AccessScope,
        pii_tier: str,
        metric_id: str = "",
        columns: tuple[dict[str, str], ...] = (),
        requires_anonymization: bool = False,
        peer_spiffe_id: str = "",
    ) -> "AuthzInput":
        return cls.for_http_request(
            request_method=request_method,
            request_path=request_path,
            request_headers=request_headers,
            scope=scope,
            peer_spiffe_id=peer_spiffe_id,
            resource_tenant_id=scope.tenant_id,
            resource_kind="data_snapshot",
            resource_pii_tier=pii_tier,
            resource_metric_id=metric_id,
            resource_columns=columns,
            resource_requires_anonymization=requires_anonymization,
        )

    def to_opa_input(self) -> dict[str, Any]:
        return {
            "request": {
                "method": self.request_method,
                "path": self.request_path,
                "headers": self.request_headers,
            },
            "identity": {
                "tenant_id": self.identity_tenant_id,
                "cell_id": self.identity_cell_id,
                "principal_type": self.identity_principal_type,
                "roles": sorted(self.identity_roles),
                "mfa_verified": self.identity_mfa_verified,
                "sub": self.identity_sub,
                "spiffe_id": self.identity_spiffe_id,
            },
            "peer": {
                "spiffe_id": self.peer_spiffe_id,
            },
            "resource": {
                "tenant_id": self.resource_tenant_id,
                "kind": self.resource_kind,
                "artifact_id": self.resource_artifact_id,
                "pii_tier": self.resource_pii_tier,
                "metric_id": self.resource_metric_id,
                "columns": list(self.resource_columns),
                "requires_anonymization": self.resource_requires_anonymization,
            },
        }

    def cache_key(self) -> str:
        raw = json.dumps(self.to_opa_input(), sort_keys=True, separators=(",", ":"))
        return truncated_hash(raw, length=16)


class OPAClient:
    """Async OPA client with in-memory TTL cache and fail-closed behavior."""

    def __init__(
        self,
        *,
        opa_url: str = "http://localhost:8181",
        policy_path: str = "polisyos/authz/decision",
        cache_max_size: int = 1000,
        cache_ttl_seconds: float = 30.0,
        timeout_seconds: float = 2.0,
    ) -> None:
        self._opa_url = opa_url.rstrip("/")
        self._policy_path = policy_path.strip("/")
        self._cache_max_size = max(cache_max_size, 1)
        self._cache_ttl = max(cache_ttl_seconds, 0.0)
        self._timeout = max(timeout_seconds, 0.1)

        self._cache = TTLCache[str, AuthzResult](
            ttl_seconds=self._cache_ttl,
            max_size=self._cache_max_size,
            time_fn=time.monotonic,
        )
        self._session: aiohttp.ClientSession | None = None
        self._lock = asyncio.Lock()

    async def _ensure_session(self) -> None:
        if self._session is None or self._session.closed:
            import aiohttp

            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self._timeout)
            )

    async def check(self, authz_input: AuthzInput) -> AuthzResult:
        cache_key = authz_input.cache_key()
        cached = self._cache.get(cache_key)
        if cached is not None:
            result = cached
            get_metrics().record_authz_cache_hit(policy=self._policy_path)
            return AuthzResult(
                decision=result.decision,
                policy=result.policy,
                reasons=result.reasons,
                latency_ms=0.0,
                cached=True,
                audit_entry=result.audit_entry,
            )

        started = time.monotonic()
        try:
            payload = await self._query_opa(authz_input)
        except (AttributeError, KeyError, OSError, RuntimeError, TimeoutError, TypeError, ValueError) as exc:
            latency_ms = (time.monotonic() - started) * 1000.0
            logger.error("OPA authorization query failed, deny-by-default: %s", exc)
            get_metrics().record_authz_error(policy=self._policy_path, reason="opa_unreachable")
            get_metrics().record_authz_latency(self._policy_path, latency_ms / 1000.0)
            deny_result = AuthzResult(
                decision=AuthzDecision.DENY,
                policy=self._policy_path,
                reasons=("OPA_UNREACHABLE",),
                latency_ms=latency_ms,
            )
            get_metrics().record_authz_decision(
                policy=self._policy_path,
                decision=deny_result.decision.value,
                cached=False,
            )
            return deny_result

        latency_ms = (time.monotonic() - started) * 1000.0
        get_metrics().record_authz_latency(self._policy_path, latency_ms / 1000.0)

        decision = AuthzDecision.ALLOW if bool(payload.get("allow", False)) else AuthzDecision.DENY
        audit_entry = payload.get("audit_entry", {})
        if not isinstance(audit_entry, dict):
            audit_entry = {}
        allowed_columns = payload.get("allowed_columns")
        if allowed_columns is not None and "allowed_columns" not in audit_entry:
            audit_entry = dict(audit_entry)
            if isinstance(allowed_columns, (list, tuple, set)):
                audit_entry["allowed_columns"] = [str(item) for item in allowed_columns]
            else:
                audit_entry["allowed_columns"] = allowed_columns
        result = AuthzResult(
            decision=decision,
            policy=self._policy_path,
            reasons=tuple(str(reason) for reason in payload.get("deny_reasons", [])),
            latency_ms=latency_ms,
            cached=False,
            audit_entry=audit_entry,
        )
        get_metrics().record_authz_decision(
            policy=self._policy_path,
            decision=result.decision.value,
            cached=False,
        )

        await self._cache_put(cache_key, result)
        return result

    async def _cache_put(self, key: str, value: AuthzResult) -> None:
        if self._cache_ttl <= 0.0:
            return
        async with self._lock:
            self._cache.set(key, value)

    async def _query_opa(self, authz_input: AuthzInput) -> dict[str, Any]:
        await self._ensure_session()
        assert self._session is not None

        url = f"{self._opa_url}/v1/data/{self._policy_path}"
        body = {"input": authz_input.to_opa_input()}

        async with self._session.post(url, json=body) as response:
            if response.status != 200:
                text = await response.text()
                raise RuntimeError(f"OPA returned {response.status}: {text}")
            payload = await response.json()
            result = payload.get("result")
            if not isinstance(result, dict):
                raise RuntimeError("OPA response missing object result")
            return result

    async def close(self) -> None:
        if self._session is not None and not self._session.closed:
            await self._session.close()


__all__ = ["AuthzDecision", "AuthzInput", "AuthzResult", "OPAClient"]
