"""Resolve execution profiles and control-plane posture from env vars and caller identity."""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, cast

from polisyos.core.contracts.control import ExecutionProfile, PolicyFlags
from polisyos.core.security.identity import PolicyOSRole, UserIdentityClaims

_PROFILE_ORDER: dict[str, int] = {
    "dev": 0,
    "research": 1,
    "governed": 2,
    "production": 3,
}
_SUPPORTED_PROFILES: tuple[ExecutionProfile, ...] = ("dev", "research", "governed", "production")
_PRIVILEGED_ROLES = frozenset({PolicyOSRole.ADMIN, PolicyOSRole.SERVICE, PolicyOSRole.SYSTEM})


def _env_flag(name: str) -> bool:
    value = os.getenv(name, "").strip().lower()
    return value in {"1", "true", "yes", "on"}


class ExecutionProfileError(ValueError):
    """Signal that a requested profile is invalid or weaker than deployment policy."""
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class PolicyFlagForbiddenError(PermissionError):
    """Signal that a non-privileged caller requested a restricted policy flag."""
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class RuntimeBootstrapError(RuntimeError):
    """Signal that deployment configuration cannot satisfy the selected execution profile."""
    pass


@dataclass(frozen=True)
class RuntimePrincipal:
    """Normalize caller identity for execution-policy checks."""
    subject: str = "anonymous"
    tenant_id: str | None = None
    roles: frozenset[str] = frozenset()
    authenticated: bool = False

    @property
    def is_privileged(self) -> bool:
        """Return whether the caller has an admin/service/system role."""
        return bool(self.roles & {role.value for role in _PRIVILEGED_ROLES})

    @classmethod
    def from_user_claims(cls, claims: UserIdentityClaims | None) -> "RuntimePrincipal":
        """Convert normalized JWT claims into the internal principal policy model."""
        if claims is None:
            return cls()
        return cls(
            subject=claims.sub,
            tenant_id=claims.tenant_id,
            roles=frozenset(role.value for role in claims.roles),
            authenticated=True,
        )


@dataclass(frozen=True)
class ResolvedExecutionPolicy:
    """Describe effective runtime posture after profile, flags, and principal checks."""
    default_profile: ExecutionProfile
    requested_profile: ExecutionProfile | None
    effective_profile: ExecutionProfile
    policy_flags: PolicyFlags
    worker_backend: str
    state_store_backend: str
    sqlite_path: str
    postgres_dsn: str | None
    security_required: bool
    external_worker_required: bool
    postgres_required: bool
    authz_shadow_allowed: bool
    mock_fallback_allowed: bool
    security_posture: dict[str, Any]
    fallback_rules: dict[str, Any]
    gateway_posture: dict[str, Any]
    actor: dict[str, Any]
    config_fingerprint: str


class RuntimeExecutionPolicyResolver:
    """Validate requested execution profiles against deployment and caller constraints."""
    def __init__(
        self,
        *,
        default_profile: ExecutionProfile,
        worker_backend: str,
        state_store_backend: str,
        sqlite_path: str,
        postgres_dsn: str | None,
    ) -> None:
        self._default_profile = self._coerce_profile(default_profile)
        self._worker_backend = worker_backend.strip().lower()
        self._state_store_backend = state_store_backend.strip().lower()
        self._sqlite_path = sqlite_path
        self._postgres_dsn = postgres_dsn

    @classmethod
    def from_env(cls) -> "RuntimeExecutionPolicyResolver":
        """Resolve deployment defaults from `POLISYOS_EXECUTION_PROFILE` and control-plane env vars."""
        default_profile = cls._coerce_profile(
            os.getenv("POLISYOS_EXECUTION_PROFILE", "dev").strip().lower() or "dev"
        )
        default_worker_backend = (
            "external" if default_profile in {"research", "governed", "production"} else "embedded"
        )
        default_state_store = (
            "postgres" if default_profile in {"research", "governed", "production"} else "sqlite"
        )
        return cls(
            default_profile=default_profile,
            worker_backend=os.getenv("POLISYOS_CONTROL_WORKER_BACKEND", default_worker_backend),
            state_store_backend=os.getenv("POLISYOS_CONTROL_STATE_STORE_BACKEND", default_state_store),
            sqlite_path=os.getenv(
                "POLISYOS_CONTROL_SQLITE_PATH",
                ".polisyos/control_plane.sqlite3",
            ),
            postgres_dsn=(os.getenv("POLISYOS_CONTROL_POSTGRES_DSN", "").strip() or None),
        )

    @property
    def default_profile(self) -> ExecutionProfile:
        """Return the deployment baseline execution profile."""
        return self._default_profile

    @property
    def worker_backend(self) -> str:
        """Return the configured control-worker backend (`embedded` or `external`)."""
        return self._worker_backend

    @property
    def state_store_backend(self) -> str:
        """Return the configured state-store backend (`sqlite` or `postgres`)."""
        return self._state_store_backend

    @property
    def sqlite_path(self) -> str:
        """Return the SQLite state-store path used when `state_store_backend=sqlite`."""
        return self._sqlite_path

    @property
    def postgres_dsn(self) -> str | None:
        """Return the PostgreSQL DSN used when durable control-plane state is required."""
        return self._postgres_dsn

    @staticmethod
    def supported_profiles() -> tuple[ExecutionProfile, ...]:
        """Return the ordered set of accepted execution profiles."""
        return _SUPPORTED_PROFILES

    @classmethod
    def _coerce_profile(cls, value: str | ExecutionProfile) -> ExecutionProfile:
        normalized = str(value or "").strip().lower()
        if normalized not in _PROFILE_ORDER:
            raise ExecutionProfileError(
                "invalid_execution_profile",
                f"Unsupported execution profile: {value!r}",
            )
        return cast(ExecutionProfile, normalized)

    @classmethod
    def _profile_rank(cls, value: str | ExecutionProfile) -> int:
        profile = cls._coerce_profile(value)
        return _PROFILE_ORDER[profile]

    def resolve(
        self,
        *,
        requested_profile: ExecutionProfile | None,
        policy_flags: PolicyFlags | None = None,
        principal: RuntimePrincipal | None = None,
    ) -> ResolvedExecutionPolicy:
        """Resolve requested/default profile, enforce no-downgrade policy, and derive runtime posture.

        Raises:
            ExecutionProfileError: If the requested profile is invalid or weaker
                than the deployment default.
            PolicyFlagForbiddenError: If a non-privileged caller requests
                `allow_mock_fallback`.
        """
        flags = policy_flags or PolicyFlags()
        actor = principal or RuntimePrincipal()
        requested = self._coerce_profile(requested_profile) if requested_profile else None
        if requested is not None and self._profile_rank(requested) < self._profile_rank(self._default_profile):
            raise ExecutionProfileError(
                "execution_profile_downgrade_forbidden",
                (
                    f"Requested execution profile {requested!r} is less strict than "
                    f"deployment default {self._default_profile!r}."
                ),
            )

        effective = requested or self._default_profile
        if self._profile_rank(effective) < self._profile_rank(self._default_profile):
            effective = self._default_profile

        if flags.allow_mock_fallback and not actor.is_privileged:
            raise PolicyFlagForbiddenError(
                "policy_flag_forbidden",
                "allow_mock_fallback requires a privileged principal.",
            )

        research_local_control_waiver = effective == "research" and _env_flag(
            "POLISYOS_RESEARCH_ALLOW_LOCAL_CONTROL_PLANE"
        )
        security_required = effective in {"governed", "production"}
        durable_control_required = effective in {"research", "governed", "production"}
        external_worker_required = durable_control_required and not research_local_control_waiver
        postgres_required = durable_control_required and not research_local_control_waiver
        mock_fallback_allowed = effective == "dev" or bool(flags.allow_mock_fallback)
        authz_shadow_allowed = effective != "production"
        gateway_posture = {
            "configured": bool(os.getenv("POLISYOS_LLM_GATEWAY_BASE_URL", "").strip()),
            "provider": (os.getenv("POLISYOS_LLM_GATEWAY_PROVIDER", "").strip() or "gateway"),
        }
        security_posture = {
            "required": security_required,
            "authz_shadow_allowed": authz_shadow_allowed,
            "middleware_required": security_required,
        }
        fallback_rules = {
            "mock_fallback_allowed": mock_fallback_allowed,
            "policy_flag_required_for_mock_fallback": effective != "dev",
            "durable_control_required": durable_control_required,
            "local_control_plane_waiver_active": research_local_control_waiver,
            "local_control_plane_waiver_allowed": effective == "research",
        }
        fingerprint_payload = {
            "default_profile": self._default_profile,
            "effective_profile": effective,
            "worker_backend": self._worker_backend,
            "state_store_backend": self._state_store_backend,
            "security_required": security_required,
            "durable_control_required": durable_control_required,
            "local_control_plane_waiver_active": research_local_control_waiver,
            "allow_mock_fallback": mock_fallback_allowed,
            "gateway_configured": gateway_posture["configured"],
        }
        config_fingerprint = hashlib.sha256(
            json.dumps(fingerprint_payload, sort_keys=True).encode("utf-8")
        ).hexdigest()
        return ResolvedExecutionPolicy(
            default_profile=self._default_profile,
            requested_profile=requested,
            effective_profile=effective,
            policy_flags=flags,
            worker_backend=self._worker_backend,
            state_store_backend=self._state_store_backend,
            sqlite_path=self._sqlite_path,
            postgres_dsn=self._postgres_dsn,
            security_required=security_required,
            external_worker_required=external_worker_required,
            postgres_required=postgres_required,
            authz_shadow_allowed=authz_shadow_allowed,
            mock_fallback_allowed=mock_fallback_allowed,
            security_posture=security_posture,
            fallback_rules=fallback_rules,
            gateway_posture=gateway_posture,
            actor={
                "subject": actor.subject,
                "tenant_id": actor.tenant_id,
                "roles": sorted(actor.roles),
                "authenticated": actor.authenticated,
            },
            config_fingerprint=config_fingerprint,
        )

    def validate_bootstrap(
        self,
        *,
        authz_shadow_mode: bool,
        security_chain_available: bool,
    ) -> ResolvedExecutionPolicy:
        """Validate deployment bootstrap state against the resolved execution profile.

        Raises:
            RuntimeBootstrapError: If required authz/security middleware, external
                worker backend, or PostgreSQL state-store configuration is missing.
        """
        policy = self.resolve(requested_profile=None, policy_flags=PolicyFlags(), principal=None)
        if policy.postgres_required and self._state_store_backend != "postgres":
            raise RuntimeBootstrapError(
                "Execution profile requires PostgreSQL-backed control-plane state store."
            )
        if policy.postgres_required and not self._postgres_dsn:
            raise RuntimeBootstrapError(
                "Execution profile requires POLISYOS_CONTROL_POSTGRES_DSN."
            )
        if policy.external_worker_required and self._worker_backend != "external":
            raise RuntimeBootstrapError(
                "Execution profile requires POLISYOS_CONTROL_WORKER_BACKEND=external."
            )
        if policy.security_required and not security_chain_available:
            raise RuntimeBootstrapError(
                "Execution profile requires runtime security middlewares and providers."
            )
        if not policy.authz_shadow_allowed and authz_shadow_mode:
            raise RuntimeBootstrapError(
                "Execution profile 'production' forbids authz shadow mode."
            )
        return policy


def build_capability_manifest_payload(
    *,
    policy: ResolvedExecutionPolicy,
    job_id: str,
    run_id: str | None,
    pipeline_id: str | None,
    payload_ref: str | None,
    observed_fallbacks: list[str] | None = None,
) -> dict[str, Any]:
    """Build the durable capability-manifest payload persisted alongside control jobs."""
    return {
        "schema_version": "1.0",
        "created_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "job_id": job_id,
        "run_id": run_id,
        "pipeline_id": pipeline_id,
        "payload_ref": payload_ref,
        "requested_execution_profile": policy.requested_profile,
        "default_execution_profile": policy.default_profile,
        "effective_execution_profile": policy.effective_profile,
        "worker_backend": policy.worker_backend,
        "state_store_backend": policy.state_store_backend,
        "security_posture": dict(policy.security_posture),
        "fallback_rules": dict(policy.fallback_rules),
        "gateway_posture": dict(policy.gateway_posture),
        "policy_flags": policy.policy_flags.model_dump(mode="json"),
        "observed_fallbacks": list(observed_fallbacks or []),
        "actor": dict(policy.actor),
        "config_fingerprint": policy.config_fingerprint,
    }


__all__ = [
    "ExecutionProfileError",
    "PolicyFlagForbiddenError",
    "ResolvedExecutionPolicy",
    "RuntimeBootstrapError",
    "RuntimeExecutionPolicyResolver",
    "RuntimePrincipal",
    "build_capability_manifest_payload",
]
