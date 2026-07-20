"""Distinct step-up declarations for high-stakes runtime mutations."""

from __future__ import annotations

import json
import time
from copy import deepcopy
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Protocol, cast

from polisyos.runtime.http.access_audit import (
    RuntimeAuthorizationAuditError,
    RuntimeAuthorizationOutcome,
    emit_runtime_authorization_audit,
)
from polisyos.runtime.http.authorization import (
    ActionPermissionDependency,
    BoundActionPermissionVerification,
    MatchedAuthorizationRoute,
    get_route_action_permission_dependency,
    iter_route_dependency_calls,
)
from polisyos.runtime.http.container import resolve_control_service
from polisyos.runtime.http.dependencies import RuntimeAccessScope as AccessScope
from polisyos.runtime.http.errors import RuntimeHTTPError, forbidden, service_unavailable
from polisyos.runtime.http.permissions import RuntimePermission
from polisyos.runtime.http.resource_binding import BoundAuthorizationResource

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

    from fastapi import Request
    from fastapi.routing import APIRoute as _ImportedAPIRoute

    _APIRoute: type[_ImportedAPIRoute] | None

    class _DependencyNode(Protocol):
        call: object
        dependencies: Sequence[_DependencyNode]

    class _Route(Protocol):
        dependant: _DependencyNode
        methods: set[str]
        path: str
else:
    try:  # pragma: no cover - optional runtime dependency
        from fastapi import Request
        from fastapi.routing import APIRoute as _ImportedAPIRoute
    except ModuleNotFoundError:  # pragma: no cover
        Request = cast("Any", object)
        _APIRoute: Any | None = None
    else:  # pragma: no cover - import wiring only
        _APIRoute = _ImportedAPIRoute

    Mapping = Any
    _Route = Any


class StepUpClass(StrEnum):
    """Closed human-assurance classes required by high-stakes actions."""

    PROMOTION = "promotion"
    PRODUCTION_APPROVAL = "production_approval"
    PUBLICATION = "publication"
    REVOCATION = "revocation"
    ACQUISITION_APPROVAL = "acquisition_approval"


class StepUpAssertionVerificationError(ValueError):
    """Signal that a signed assertion failed one fail-closed verifier rule."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class StepUpVerificationContext:
    """Exact request, principal, action, and resource bound into an assertion."""

    subject: str
    tenant_id: str
    method: str
    route_path: str
    permission: str
    resource_id: str
    resource_digest: str
    resource_kind: str
    binding_authority: str
    body_sha256: str
    step_up_class: StepUpClass
    scorecard_ref: str | None
    scorecard_sha256: str | None

    def __post_init__(self) -> None:
        required = {
            "subject": self.subject,
            "tenant_id": self.tenant_id,
            "method": self.method,
            "route_path": self.route_path,
            "permission": self.permission,
            "resource_id": self.resource_id,
            "resource_digest": self.resource_digest,
            "resource_kind": self.resource_kind,
            "binding_authority": self.binding_authority,
            "body_sha256": self.body_sha256,
        }
        if any(not isinstance(value, str) or not value.strip() for value in required.values()):
            raise TypeError("step-up verification context fields must be non-empty strings")
        if self.method not in {"POST", "PUT", "PATCH", "DELETE"}:
            raise ValueError("step-up verification context requires an unsafe HTTP method")
        if not isinstance(self.step_up_class, StepUpClass):
            raise TypeError("step_up_class must be a StepUpClass")
        for field_name, value in (
            ("scorecard_ref", self.scorecard_ref),
            ("scorecard_sha256", self.scorecard_sha256),
        ):
            if value is not None and (
                not isinstance(value, str) or not value.strip()
            ):
                raise TypeError(f"{field_name} must be None or a non-empty string")
        scorecard_values = (self.scorecard_ref, self.scorecard_sha256)
        if self.step_up_class is StepUpClass.PRODUCTION_APPROVAL:
            if any(value is None for value in scorecard_values):
                raise ValueError("production approval step-up requires scorecard binding")
        elif any(value is not None for value in scorecard_values):
            raise ValueError("scorecard binding is exclusive to production approval")


@dataclass(frozen=True, slots=True)
class StepUpAssertionVerification:
    """Frozen proof returned only after signature and semantic verification."""

    context: StepUpVerificationContext
    assertion_id: str
    issuer: str
    audience: str
    issued_at: int
    expires_at: int
    assurance: str

    def __post_init__(self) -> None:
        if type(self.context) is not StepUpVerificationContext:
            raise TypeError("context must be a StepUpVerificationContext")
        for field_name, value in (
            ("assertion_id", self.assertion_id),
            ("issuer", self.issuer),
            ("audience", self.audience),
            ("assurance", self.assurance),
        ):
            if not isinstance(value, str) or not value.strip():
                raise TypeError(f"{field_name} must be a non-empty string")
        if type(self.issued_at) is not int or type(self.expires_at) is not int:
            raise TypeError("step-up assertion timestamps must be integers")
        if self.expires_at <= self.issued_at:
            raise ValueError("step-up assertion expiration must follow issuance")


class StepUpAssertionVerifier(Protocol):
    """Verify one external assertion against an immutable request context."""

    def verify(
        self,
        token: str,
        context: StepUpVerificationContext,
    ) -> StepUpAssertionVerification:
        """Return a proof or raise :class:`StepUpAssertionVerificationError`."""
        ...


class _JWTModule(Protocol):
    def get_unverified_header(self, jwt: str | bytes) -> dict[str, Any]: ...


class StepUpReplayStore(Protocol):
    """Atomically consume unique assertion identifiers until expiration."""

    def consume_step_up_assertion(
        self,
        *,
        assertion_id: str,
        expires_at: int,
    ) -> bool:
        """Return true only for the first durable consumption."""
        ...


class JWTStepUpAssertionVerifier:
    """Validate signed JWT step-up assertions with exact semantic binding."""

    def __init__(
        self,
        *,
        issuer: str,
        audience: str,
        algorithms: tuple[str, ...],
        maximum_age_seconds: int,
        clock_skew_seconds: int = 30,
        verification_key: object | None = None,
        jwks_uri: str | None = None,
        allowed_key_ids: frozenset[str] = frozenset(),
        revoked_key_ids: frozenset[str] = frozenset(),
        clock: Callable[[], float] = time.time,
    ) -> None:
        if not issuer.strip() or not audience.strip():
            raise ValueError("step-up issuer and audience must be non-empty")
        if not algorithms or any(
            not algorithm.strip() or algorithm.lower() == "none"
            for algorithm in algorithms
        ):
            raise ValueError("step-up algorithms must be an explicit trusted set")
        if type(maximum_age_seconds) is not int or maximum_age_seconds <= 0:
            raise ValueError("maximum_age_seconds must be a positive integer")
        if type(clock_skew_seconds) is not int or clock_skew_seconds < 0:
            raise ValueError("clock_skew_seconds must be a non-negative integer")
        if (verification_key is None) == (jwks_uri is None):
            raise ValueError("configure exactly one step-up verification key source")
        if allowed_key_ids & revoked_key_ids:
            raise ValueError("a step-up key id cannot be both allowed and revoked")
        self._issuer = issuer.rstrip("/")
        self._audience = audience
        self._algorithms = algorithms
        self._maximum_age_seconds = maximum_age_seconds
        self._clock_skew_seconds = clock_skew_seconds
        self._verification_key = verification_key
        self._jwks_uri = jwks_uri
        self._allowed_key_ids = allowed_key_ids
        self._revoked_key_ids = revoked_key_ids
        self._clock = clock
        self._jwks_client: Any | None = None

    def verify(
        self,
        token: str,
        context: StepUpVerificationContext,
    ) -> StepUpAssertionVerification:
        """Verify signature, time, assurance, and every request binding claim."""
        if not isinstance(token, str) or not token.strip():
            raise StepUpAssertionVerificationError(
                "step_up_invalid",
                "Step-up assertion is empty",
            )
        if type(context) is not StepUpVerificationContext:
            raise TypeError("context must be a StepUpVerificationContext")
        try:
            import jwt as pyjwt
        except ModuleNotFoundError as exc:  # pragma: no cover - packaging guard
            raise StepUpAssertionVerificationError(
                "step_up_verifier_unavailable",
                "PyJWT is unavailable for step-up verification",
            ) from exc

        key_id, algorithm = self._validated_header(pyjwt, token)
        key = self._verification_key
        if key is None:
            try:
                client = self._jwks_client
                if client is None:
                    client = pyjwt.PyJWKClient(cast("str", self._jwks_uri))
                    self._jwks_client = client
                key = client.get_signing_key_from_jwt(token).key
            except Exception as exc:
                raise StepUpAssertionVerificationError(
                    "step_up_signature_invalid",
                    "Step-up assertion signing key could not be verified",
                ) from exc
        try:
            payload = pyjwt.decode(
                token,
                cast("Any", key),
                algorithms=list(self._algorithms),
                audience=self._audience,
                issuer=self._issuer,
                options={
                    "require": [
                        "exp",
                        "iat",
                        "iss",
                        "aud",
                        "sub",
                        "tenant_id",
                        "jti",
                    ],
                    "verify_exp": False,
                    "verify_iat": False,
                    "verify_nbf": False,
                },
            )
        except pyjwt.InvalidTokenError as exc:
            raise StepUpAssertionVerificationError(
                "step_up_signature_invalid",
                "Step-up assertion signature, issuer, or audience is invalid",
            ) from exc
        if type(payload.get("aud")) is not str or payload.get("aud") != self._audience:
            raise StepUpAssertionVerificationError(
                "step_up_signature_invalid",
                "Step-up assertion audience must be an exact singleton match",
            )

        now = int(self._clock())
        issued_at = _required_int_claim(payload, "iat")
        expires_at = _required_int_claim(payload, "exp")
        not_before = _optional_int_claim(payload, "nbf")
        if issued_at > now + self._clock_skew_seconds:
            raise StepUpAssertionVerificationError(
                "step_up_future",
                "Step-up assertion was issued in the future",
            )
        if not_before is not None and not_before > now + self._clock_skew_seconds:
            raise StepUpAssertionVerificationError(
                "step_up_not_yet_valid",
                "Step-up assertion is not yet valid",
            )
        if now - issued_at > self._maximum_age_seconds:
            raise StepUpAssertionVerificationError(
                "step_up_stale",
                "Step-up assertion is stale",
            )
        if (
            expires_at <= now - self._clock_skew_seconds
            or expires_at <= issued_at
            or (not_before is not None and expires_at <= not_before)
        ):
            raise StepUpAssertionVerificationError(
                "step_up_expired",
                "Step-up assertion has expired or has an invalid time window",
            )
        if payload.get("mfa_verified") is not True:
            raise StepUpAssertionVerificationError(
                "step_up_assurance_required",
                "Step-up assertion lacks verified MFA assurance",
            )
        assurance = payload.get("assurance")
        if not isinstance(assurance, str) or not assurance.strip():
            raise StepUpAssertionVerificationError(
                "step_up_assurance_required",
                "Step-up assertion lacks an assurance method",
            )

        expected_bindings: dict[str, object] = {
            "sub": context.subject,
            "tenant_id": context.tenant_id,
            "method": context.method,
            "route": context.route_path,
            "permission": context.permission,
            "resource_id": context.resource_id,
            "resource_digest": context.resource_digest,
            "resource_kind": context.resource_kind,
            "binding_authority": context.binding_authority,
            "body_sha256": context.body_sha256,
            "step_up_class": context.step_up_class.value,
            "scorecard_ref": context.scorecard_ref,
            "scorecard_sha256": context.scorecard_sha256,
        }
        mismatched = tuple(
            name
            for name, expected in expected_bindings.items()
            if payload.get(name) != expected
        )
        if mismatched:
            raise StepUpAssertionVerificationError(
                "step_up_binding_mismatch",
                "Step-up assertion binding does not match the request: "
                + ", ".join(mismatched),
            )
        assertion_id = payload.get("jti")
        if not isinstance(assertion_id, str) or not assertion_id.strip():
            raise StepUpAssertionVerificationError(
                "step_up_invalid",
                "Step-up assertion lacks a unique identifier",
            )
        del key_id, algorithm
        return StepUpAssertionVerification(
            context=context,
            assertion_id=assertion_id,
            issuer=self._issuer,
            audience=self._audience,
            issued_at=issued_at,
            expires_at=expires_at,
            assurance=assurance,
        )

    def _validated_header(self, pyjwt: _JWTModule, token: str) -> tuple[str, str]:
        try:
            header = pyjwt.get_unverified_header(token)
        except Exception as exc:
            raise StepUpAssertionVerificationError(
                "step_up_invalid",
                "Step-up assertion header is invalid",
            ) from exc
        key_id = header.get("kid")
        algorithm = header.get("alg")
        if not isinstance(key_id, str) or not key_id.strip():
            raise StepUpAssertionVerificationError(
                "step_up_key_untrusted",
                "Step-up assertion lacks a trusted key identifier",
            )
        if key_id in self._revoked_key_ids:
            raise StepUpAssertionVerificationError(
                "step_up_key_untrusted",
                "Step-up assertion key has been revoked",
            )
        if self._allowed_key_ids and key_id not in self._allowed_key_ids:
            raise StepUpAssertionVerificationError(
                "step_up_key_untrusted",
                "Step-up assertion key is not in the active trust set",
            )
        if not isinstance(algorithm, str) or algorithm not in self._algorithms:
            raise StepUpAssertionVerificationError(
                "step_up_algorithm_untrusted",
                "Step-up assertion algorithm is not trusted",
            )
        return key_id, algorithm


def _required_int_claim(payload: object, claim: str) -> int:
    if not isinstance(payload, dict):
        raise StepUpAssertionVerificationError(
            "step_up_invalid",
            "Step-up assertion payload is invalid",
        )
    value = payload.get(claim)
    if type(value) is not int:
        raise StepUpAssertionVerificationError(
            "step_up_invalid",
            f"Step-up assertion claim {claim!r} must be an integer",
        )
    return value


def _optional_int_claim(payload: object, claim: str) -> int | None:
    if not isinstance(payload, dict):
        raise StepUpAssertionVerificationError(
            "step_up_invalid",
            "Step-up assertion payload is invalid",
        )
    if claim not in payload:
        return None
    value = payload[claim]
    if type(value) is not int:
        raise StepUpAssertionVerificationError(
            "step_up_invalid",
            f"Step-up assertion claim {claim!r} must be an integer",
        )
    return value


HIGH_STAKES_PERMISSION_CLASSES: Mapping[RuntimePermission, StepUpClass] = (
    MappingProxyType(
        {
            RuntimePermission.EVIDENCE_ACQUIRE: StepUpClass.ACQUISITION_APPROVAL,
            RuntimePermission.EVIDENCE_PROMOTIONS_APPROVE: StepUpClass.PROMOTION,
            RuntimePermission.EVIDENCE_PROMOTIONS_REJECT: StepUpClass.PROMOTION,
            RuntimePermission.DECISIONS_VALIDITY_PUBLISH: StepUpClass.PUBLICATION,
            RuntimePermission.RUNS_REISSUE: StepUpClass.REVOCATION,
            RuntimePermission.RUNS_PRODUCTION_APPROVAL_CREATE: (
                StepUpClass.PRODUCTION_APPROVAL
            ),
        }
    )
)


@dataclass(frozen=True, slots=True)
class StepUpRequirement:
    """Declare the fresh-assurance class required by one route."""

    step_up_class: StepUpClass

    def __post_init__(self) -> None:
        if not isinstance(self.step_up_class, StepUpClass):
            raise TypeError("step_up_class must be a StepUpClass")


@dataclass(frozen=True, slots=True)
class StepUpDependency:
    """Executable and structurally inspectable high-stakes dependency."""

    requirement: StepUpRequirement
    __polisyos_step_up__: StepUpRequirement = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if type(self.requirement) is not StepUpRequirement:
            raise TypeError("requirement must be a StepUpRequirement")
        object.__setattr__(self, "__polisyos_step_up__", self.requirement)

    def __call__(self, request: Request) -> StepUpAssertionVerification:
        """Verify, consume, and audit one assertion before handler execution."""
        try:
            verification = self._authorize(request)
        except RuntimeHTTPError as exc:
            emit_runtime_authorization_audit(
                request,
                outcome=RuntimeAuthorizationOutcome.DENY,
                denial_reason=exc.code or exc.error,
                step_up_outcome="denied",
                raise_on_failure=False,
            )
            raise
        try:
            emit_runtime_authorization_audit(
                request,
                outcome=RuntimeAuthorizationOutcome.ALLOW,
                step_up_outcome="verified",
                raise_on_failure=True,
            )
        except RuntimeAuthorizationAuditError as exc:
            raise service_unavailable(
                "Authorization audit is unavailable; mutation denied",
                code="authorization_audit_unavailable",
            ) from exc
        return verification

    def _authorize(self, request: Request) -> StepUpAssertionVerification:
        """Require a distinct assertion after the action consumed its binding."""
        state = getattr(request, "state", object())
        action_verification = getattr(
            state,
            "action_permission_verification",
            None,
        )
        if type(action_verification) is not BoundActionPermissionVerification:
            raise forbidden(
                "Step-up requires the exact bound action-permission proof",
                code="step_up_action_unbound",
            )
        bound_resource = action_verification.bound_resource
        if (
            type(bound_resource) is not BoundAuthorizationResource
            or getattr(state, "authz_bound_resource", None) is not bound_resource
            or getattr(state, "authz_action_bound_resource", None) is not bound_resource
            or getattr(state, "authz_resource_frozen", False) is not True
        ):
            raise forbidden(
                "Step-up requires the exact frozen authorization resource",
                code="step_up_resource_unbound",
            )
        effective_scope = getattr(state, "authz_effective_scope", None)
        if (
            not isinstance(effective_scope, AccessScope)
            or effective_scope.principal_type != "user"
            or not effective_scope.user_sub
        ):
            raise forbidden(
                "This step-up class requires a verified human principal",
                code="step_up_human_principal_required",
            )
        if effective_scope.mfa_verified is not True:
            raise forbidden(
                "This step-up class requires an MFA-verified base identity",
                code="step_up_base_mfa_required",
            )
        context = _build_step_up_context(
            request,
            action_verification=action_verification,
            requirement=self.requirement,
            effective_scope=effective_scope,
        )
        existing = getattr(state, "step_up_verification", None)
        if existing is not None:
            if (
                type(existing) is StepUpAssertionVerification
                and existing.context == context
                and existing.expires_at > int(time.time())
            ):
                return existing
            raise forbidden(
                "A different or expired step-up proof is already bound",
                code="step_up_context_mismatch",
            )
        token = request.headers.get("X-PolicyOS-Step-Up", "").strip()
        if not token:
            raise forbidden(
                "A fresh one-use step-up assertion is required",
                code="step_up_required",
            )
        if len(token) > 16 * 1024:
            raise forbidden(
                "The step-up assertion exceeds the accepted size",
                code="step_up_invalid",
            )
        security = getattr(getattr(request, "app", object()), "state", object())
        security_config = getattr(security, "runtime_security", None)
        verifier = getattr(security_config, "step_up_verifier", None)
        from polisyos.runtime.http.deployment_security_attestation import (
            require_attested_deployment_component,
            require_installed_deployment_security,
        )

        if verifier is not None:
            verifier = cast(
                "StepUpAssertionVerifier",
                require_attested_deployment_component(
                    request,
                    component_name="step_up_verifier",
                    candidate=verifier,
                ),
            )
        verify = getattr(verifier, "verify", None)
        if not callable(verify):
            raise service_unavailable(
                "The step-up assertion verifier is unavailable",
                code="step_up_verifier_unavailable",
            )
        try:
            verification = verify(token, context)
        except StepUpAssertionVerificationError as exc:
            if exc.code == "step_up_verifier_unavailable":
                raise service_unavailable(str(exc), code=exc.code) from exc
            raise forbidden(str(exc), code=exc.code) from exc
        except Exception as exc:
            raise service_unavailable(
                "The step-up assertion verifier failed closed",
                code="step_up_verifier_failed",
            ) from exc
        if (
            type(verification) is not StepUpAssertionVerification
            or verification.context != context
        ):
            raise service_unavailable(
                "The step-up verifier returned an invalid bound proof",
                code="step_up_verifier_contract_invalid",
            )
        if verification.expires_at <= int(time.time()):
            raise forbidden(
                "The verified step-up assertion is no longer fresh",
                code="step_up_expired",
            )
        if verifier is not None:
            require_installed_deployment_security(request)
        replay_store = getattr(security_config, "step_up_replay_store", None)
        if replay_store is None:
            control_service = resolve_control_service(request)
            replay_store = getattr(control_service, "step_up_replay_store", None)
        consume = getattr(replay_store, "consume_step_up_assertion", None)
        if not callable(consume):
            raise service_unavailable(
                "The durable step-up replay store is unavailable",
                code="step_up_replay_store_unavailable",
            )
        try:
            consumed = consume(
                assertion_id=verification.assertion_id,
                expires_at=verification.expires_at,
            )
        except Exception as exc:
            raise service_unavailable(
                "The durable step-up replay store failed closed",
                code="step_up_replay_store_failed",
            ) from exc
        if consumed is not True:
            raise forbidden(
                "The step-up assertion has already been consumed",
                code="step_up_replayed",
            )
        cast("Any", state).step_up_verification = verification
        return verification


def step_up_verification_matches_request(
    request: Request,
    *,
    action_verification: BoundActionPermissionVerification,
) -> bool:
    """Return whether state contains the exact live proof for this bound request."""
    state = request.state
    requirement = getattr(state, "authz_step_up_requirement", None)
    effective_scope = getattr(state, "authz_effective_scope", None)
    verification = getattr(state, "step_up_verification", None)
    if (
        type(requirement) is not StepUpRequirement
        or not isinstance(effective_scope, AccessScope)
        or type(verification) is not StepUpAssertionVerification
        or verification.expires_at <= int(time.time())
    ):
        return False
    try:
        expected_context = _build_step_up_context(
            request,
            action_verification=action_verification,
            requirement=requirement,
            effective_scope=effective_scope,
        )
    except RuntimeHTTPError:
        return False
    return verification.context == expected_context


def _build_step_up_context(
    request: Request,
    *,
    action_verification: BoundActionPermissionVerification,
    requirement: StepUpRequirement,
    effective_scope: AccessScope,
) -> StepUpVerificationContext:
    state = request.state
    matched_route = getattr(state, "authz_matched_route", None)
    bound_resource = action_verification.bound_resource
    proof = action_verification.verification
    if type(matched_route) is not MatchedAuthorizationRoute:
        raise forbidden(
            "Step-up requires the exact matched route identity",
            code="step_up_route_unbound",
        )
    if (
        type(bound_resource) is not BoundAuthorizationResource
        or bound_resource.requirement is not proof.requirement
        or proof.subject != effective_scope.user_sub
        or proof.tenant_id != effective_scope.tenant_id
        or matched_route.method != request.method.upper()
        or getattr(state, "authz_body_sha256", None) != bound_resource.body_sha256
    ):
        raise forbidden(
            "Step-up request authority is not exactly bound",
            code="step_up_context_mismatch",
        )
    expected_class = HIGH_STAKES_PERMISSION_CLASSES.get(proof.requirement.permission)
    if expected_class is not requirement.step_up_class:
        raise forbidden(
            "Step-up class does not match the action permission",
            code="step_up_class_mismatch",
        )
    selectors = dict(bound_resource.canonical_selectors)
    scorecard_ref: str | None = None
    scorecard_sha256: str | None = None
    if requirement.step_up_class is StepUpClass.PRODUCTION_APPROVAL:
        scorecard_ref = _decoded_selector(selectors, "quality_scorecard_ref")
        scorecard_sha256 = _decoded_selector(selectors, "scorecard_sha256")
        if scorecard_ref is None or scorecard_sha256 is None:
            raise forbidden(
                "Production approval step-up lacks a persisted scorecard binding",
                code="step_up_scorecard_unbound",
            )
    return StepUpVerificationContext(
        subject=proof.subject,
        tenant_id=proof.tenant_id,
        method=matched_route.method,
        route_path=matched_route.path_template,
        permission=proof.requirement.permission.value,
        resource_id=bound_resource.resource_id,
        resource_digest=bound_resource.resource_digest,
        resource_kind=bound_resource.resource_kind,
        binding_authority=bound_resource.authority.value,
        body_sha256=bound_resource.body_sha256,
        step_up_class=requirement.step_up_class,
        scorecard_ref=scorecard_ref,
        scorecard_sha256=scorecard_sha256,
    )


def _decoded_selector(selectors: dict[str, str], name: str) -> str | None:
    raw = selectors.get(name)
    if raw is None:
        return None
    try:
        value = json.loads(raw)
    except (TypeError, ValueError):
        return None
    return value if isinstance(value, str) and value.strip() else None


def require_step_up(step_up_class: StepUpClass) -> StepUpDependency:
    """Build one typed high-stakes step-up dependency."""
    if not isinstance(step_up_class, StepUpClass):
        raise TypeError("step_up_class must be a StepUpClass")
    return StepUpDependency(StepUpRequirement(step_up_class=step_up_class))


def get_route_step_up_dependency(
    route: _Route,
    *,
    action_dependency: ActionPermissionDependency | None = None,
) -> StepUpDependency | None:
    """Return the exact direct step-up declaration or reject route drift."""
    action = action_dependency or get_route_action_permission_dependency(
        cast("Any", route)
    )
    expected_class = HIGH_STAKES_PERMISSION_CLASSES.get(action.requirement.permission)
    dependency_calls = tuple(iter_route_dependency_calls(cast("Any", route)))
    impostors = tuple(
        dependency
        for dependency in dependency_calls
        if getattr(dependency, "__polisyos_step_up__", None) is not None
        and type(dependency) is not StepUpDependency
    )
    dependencies = tuple(
        dependency
        for dependency in dependency_calls
        if type(dependency) is StepUpDependency
    )
    direct_calls = tuple(child.call for child in route.dependant.dependencies)
    direct_dependencies = tuple(
        dependency
        for dependency in direct_calls
        if type(dependency) is StepUpDependency
    )
    unsafe_methods = set(route.methods) & {"POST", "PUT", "PATCH", "DELETE"}
    label = f"{','.join(sorted(unsafe_methods))} {route.path}"
    if expected_class is None:
        if dependencies or impostors:
            raise RuntimeError(f"{label} declares an unexpected step-up dependency")
        return None
    if impostors:
        raise RuntimeError(f"{label} has a marker-only step-up dependency")
    if len(dependencies) != 1 or len(direct_dependencies) != 1:
        raise RuntimeError(
            f"{label} requires one direct step-up dependency; "
            f"found={len(dependencies)} direct={len(direct_dependencies)}"
        )
    dependency = dependencies[0]
    marker = dependency.__polisyos_step_up__
    if marker is not dependency.requirement or marker.step_up_class is not expected_class:
        raise RuntimeError(
            f"{label} has mismatched step-up class; "
            f"expected={expected_class.value} actual={marker.step_up_class.value}"
        )
    action_index = next(
        (index for index, call in enumerate(direct_calls) if call is action),
        -1,
    )
    step_up_index = next(
        (index for index, call in enumerate(direct_calls) if call is dependency),
        -1,
    )
    if action_index < 0 or step_up_index <= action_index:
        raise RuntimeError(f"{label} must declare action before step-up")
    return dependency


def assert_high_stakes_step_up_contract(app: object) -> None:
    """Validate the high-stakes step-up declarations installed on ``app``."""
    if _APIRoute is None:
        raise RuntimeError("step-up route inspection requires FastAPI")
    routes = tuple(getattr(getattr(app, "router", app), "routes", ()))
    violations: list[str] = []
    for candidate in routes:
        if not isinstance(candidate, _APIRoute):
            continue
        methods = set(candidate.methods) & {"POST", "PUT", "PATCH", "DELETE"}
        if not methods:
            continue
        try:
            action = get_route_action_permission_dependency(cast("Any", candidate))
        except RuntimeError:
            continue
        try:
            get_route_step_up_dependency(
                cast("Any", candidate),
                action_dependency=action,
            )
        except RuntimeError as exc:
            violations.append(str(exc))

    if violations:
        details = "\n".join(f"- {violation}" for violation in violations)
        raise RuntimeError("high-stakes step-up contract failed:\n" + details)


def install_step_up_openapi_contract(app: object) -> None:
    """Project each distinct high-stakes assurance class into OpenAPI."""
    application = cast("Any", app)
    original_openapi = application.openapi
    cached: dict[str, Any] | None = None

    def _custom_openapi() -> dict[str, Any]:
        nonlocal cached
        if cached is not None:
            return cached
        schema = deepcopy(original_openapi())
        for candidate in application.routes:
            if _APIRoute is None or not isinstance(candidate, _APIRoute):
                continue
            methods = set(candidate.methods) & {"POST", "PUT", "PATCH", "DELETE"}
            if not methods:
                continue
            dependency = get_route_step_up_dependency(cast("Any", candidate))
            if dependency is None:
                continue
            for method in methods:
                operation = schema["paths"][candidate.path][method.lower()]
                operation["x-polisyos-step-up-class"] = (
                    dependency.requirement.step_up_class.value
                )
        cached = schema
        return schema

    application.openapi = _custom_openapi


__all__ = [
    "HIGH_STAKES_PERMISSION_CLASSES",
    "JWTStepUpAssertionVerifier",
    "StepUpAssertionVerification",
    "StepUpAssertionVerificationError",
    "StepUpAssertionVerifier",
    "StepUpClass",
    "StepUpDependency",
    "StepUpReplayStore",
    "StepUpRequirement",
    "StepUpVerificationContext",
    "assert_high_stakes_step_up_contract",
    "get_route_step_up_dependency",
    "install_step_up_openapi_contract",
    "require_step_up",
    "step_up_verification_matches_request",
]
