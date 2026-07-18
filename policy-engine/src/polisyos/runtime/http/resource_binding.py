"""Resolve immutable, pre-policy resources for mutating Runtime HTTP routes.

The action-permission preflight runs before this module is called.  This
binder then resolves only facts supported by installed runtime services.  In
particular, an authenticated tenant never becomes ownership evidence for an
unscoped selector merely because it made the request.
"""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Any, cast

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.canon import CanonSpec, from_canonical_bytes, to_canonical_bytes
from polisyos.core.security.access_scope import AccessScope
from polisyos.runtime.http.authorization import (
    ActionPermissionVerification,
    ResourceBindingSource,
    ResourceBindingSpec,
    RouteAuthorizationRequirement,
    principal_from_access_scope,
)
from polisyos.runtime.http.container import (
    resolve_control_service,
    resolve_runtime_api_context,
)
from polisyos.runtime.http.errors import (
    bad_request,
    forbidden,
    service_unavailable,
    unauthorized,
)
from polisyos.runtime.http.production_approval_binding import (
    production_approval_context_kind,
    resolve_production_approval_scorecard,
)
from polisyos.runtime.http.services.scenarios import (
    resolve_scenario_target_id,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from fastapi import Request

    from polisyos.runtime.http.dependencies import RuntimeApiContext
    from polisyos.runtime.http.services.run_index import IndexedRunRecord
else:
    try:  # pragma: no cover - optional runtime dependency
        from fastapi import Request
    except ModuleNotFoundError:  # pragma: no cover
        Request = cast("Any", object)


_DEFAULT_MAX_BODY_BYTES = 1024 * 1024
_MAX_BATCH_ITEMS = 100
_ABSENT_SELECTOR = '{"present":false}'
_RESOLVED_CONTEXT_CANON = CanonSpec(forbid_floats=False)
_SCENARIO_TARGET_CONTEXT_KIND = "runtime.scenario.target.v1"


class _ResolverKind(StrEnum):
    """Closed server-side resolvers registered for binding specs."""

    RUN = "run"
    ARTIFACT = "artifact"
    PROMOTION = "promotion"
    LINEAGE = "lineage"


_OWNED_PATH_RESOLVERS = {
    ("runtime.run.feedback_evaluation", "run_id"): _ResolverKind.RUN,
    ("runtime.run.reissue", "run_id"): _ResolverKind.RUN,
    ("runtime.run.production_approval", "run_id"): _ResolverKind.RUN,
    ("runtime.artifact.bureaucratic_render", "packet_id"): _ResolverKind.ARTIFACT,
}
_OWNED_BATCH_RESOLVERS = {
    ("runtime.artifact.batch", "artifact_ids"): _ResolverKind.ARTIFACT,
    ("runtime.run.batch", "run_ids"): _ResolverKind.RUN,
}
_RESOLVED_SELECTOR_RESOLVERS = {
    ("runtime.evidence.promotion.approve", "promotion_id"): _ResolverKind.PROMOTION,
    ("runtime.evidence.promotion.reject", "promotion_id"): _ResolverKind.PROMOTION,
}
_RESOLVED_BATCH_RESOLVERS = {
    ("runtime.lineage.batch", "lineage_ids"): _ResolverKind.LINEAGE,
}


class BindingAuthority(StrEnum):
    """Closed authority labels carried into OPA and the audit trail."""

    OWNERSHIP_VERIFIED = "ownership_verified"
    CONTENT_RESOLVED_UNSCOPED = "content_resolved_unscoped"
    CANDIDATE = "candidate"
    REQUEST_BOUND = "request_bound"
    TENANT_COLLECTION = "tenant_collection"


@dataclass(frozen=True, slots=True)
class BoundAuthorizationResource:
    """Frozen result of resolving one route's exact binding requirement.

    ``tenant_id`` is present only when ownership was verified or the resource
    is an authenticated tenant collection/candidate below a verified parent.
    ``resource_kind`` includes the authority label so an older OPA input shape
    cannot silently discard the distinction.  Selector values are canonical
    JSON text, including the ``"auto"`` sentinel for an unnamed scenario.
    """

    requirement: RouteAuthorizationRequirement
    tenant_id: str | None
    resource_kind: str
    resource_id: str
    resource_digest: str
    authority: BindingAuthority
    body_sha256: str
    query_sha256: str
    canonical_selectors: tuple[tuple[str, str], ...]
    resolved_context_kind: str | None = None
    resolved_context: bytes | None = None

    def __post_init__(self) -> None:
        if type(self.requirement) is not RouteAuthorizationRequirement:
            raise TypeError("requirement must be a RouteAuthorizationRequirement")
        if not isinstance(self.authority, BindingAuthority):
            raise TypeError("authority must be a BindingAuthority")
        expected_kind = _resource_kind(
            self.requirement.resource_binding,
            self.authority,
        )
        if self.resource_kind != expected_kind:
            raise ValueError("resource_kind must retain the exact binding authority")
        if self.tenant_id is not None:
            _validate_identifier(self.tenant_id, field_name="tenant_id")
        _validate_identifier(self.resource_id, field_name="resource_id")
        _validate_sha256(self.resource_digest, field_name="resource_digest")
        _validate_sha256(self.body_sha256, field_name="body_sha256")
        _validate_sha256(self.query_sha256, field_name="query_sha256")
        if self.resource_id != _binding_resource_urn(self.resource_digest):
            raise ValueError("resource_id must be the versioned binding-digest URN")
        tenant_required = {
            BindingAuthority.OWNERSHIP_VERIFIED,
            BindingAuthority.TENANT_COLLECTION,
        }
        tenant_forbidden = {
            BindingAuthority.CONTENT_RESOLVED_UNSCOPED,
            BindingAuthority.REQUEST_BOUND,
        }
        if self.authority in tenant_required and self.tenant_id is None:
            raise ValueError("binding authority requires a verified tenant")
        if self.authority in tenant_forbidden and self.tenant_id is not None:
            raise ValueError("unscoped binding authority cannot carry a tenant")
        if not isinstance(self.canonical_selectors, tuple):
            raise TypeError("canonical_selectors must be an immutable tuple")
        if tuple(sorted(self.canonical_selectors)) != self.canonical_selectors:
            raise ValueError("canonical_selectors must be in canonical order")
        selector_names = [name for name, _value in self.canonical_selectors]
        if len(selector_names) != len(set(selector_names)):
            raise ValueError("canonical_selectors must not contain duplicate names")
        for name, value in self.canonical_selectors:
            _validate_identifier(name, field_name="canonical selector name")
            _validate_identifier(value, field_name="canonical selector value")
        if (self.resolved_context_kind is None) != (self.resolved_context is None):
            raise ValueError(
                "resolved_context_kind and resolved_context must be present together"
            )
        if self.resolved_context_kind is not None:
            _validate_identifier(
                self.resolved_context_kind,
                field_name="resolved_context_kind",
            )
        if self.resolved_context is not None and not isinstance(
            self.resolved_context,
            bytes,
        ):
            raise TypeError("resolved_context must be immutable bytes")

    @property
    def canonical_resource_id(self) -> str:
        """Return the canonical identifier passed to policy evaluation."""
        return self.resource_id

    def to_opa_resource(self) -> dict[str, object]:
        """Project this frozen binding into the existing OPA resource shape.

        An explicit empty tenant is deliberate: the legacy OPA adapter falls
        back to the caller tenant only when the key is absent.  Unscoped
        bindings must therefore carry the key without inventing ownership.
        """
        return {
            "tenant_id": self.tenant_id or "",
            "kind": self.resource_kind,
            "artifact_id": self.resource_id,
            "binding_authority": self.authority.value,
            "resource_digest": self.resource_digest,
            "body_sha256": self.body_sha256,
            "query_sha256": self.query_sha256,
            "selectors": dict(self.canonical_selectors),
        }


def get_bound_resource_context(
    request: Request,
    *,
    expected_kind: str,
) -> Mapping[str, Any]:
    """Return an immutable resource's decoded context or fail closed."""
    bound = getattr(getattr(request, "state", object()), "authz_bound_resource", None)
    if (
        type(bound) is not BoundAuthorizationResource
        or bound.resolved_context_kind != expected_kind
        or not isinstance(bound.resolved_context, bytes)
    ):
        raise forbidden(
            "The route did not consume its exact resolved authorization context",
            code="authorization_binding_context_missing",
        )
    try:
        payload = from_canonical_bytes(bound.resolved_context)
    except (TypeError, ValueError) as exc:
        raise forbidden(
            "The resolved authorization context is invalid",
            code="authorization_binding_context_invalid",
        ) from exc
    if not isinstance(payload, Mapping):
        raise forbidden(
            "The resolved authorization context must be an object",
            code="authorization_binding_context_invalid",
        )
    return payload


def scenario_target_from_bound_request(
    request: Request,
    *,
    run: IndexedRunRecord,
    requested_id: str | None,
) -> tuple[str, int]:
    """Consume the exact pre-policy scenario target and revision snapshot."""
    context = get_bound_resource_context(
        request,
        expected_kind=_SCENARIO_TARGET_CONTEXT_KIND,
    )
    bound_run_id = context.get("run_id")
    scenario_id = context.get("scenario_id")
    expected_revision = context.get("expected_revision")
    if bound_run_id != run.run_id or not isinstance(scenario_id, str):
        raise forbidden(
            "The scenario target is not bound to this baseline run",
            code="authorization_binding_scenario_parent_mismatch",
        )
    try:
        _validate_identifier(scenario_id, field_name="scenario_id")
    except ValueError as exc:
        raise forbidden(
            "The bound scenario target is invalid",
            code="authorization_binding_context_invalid",
        ) from exc
    if type(expected_revision) is not int or expected_revision < 0:
        raise forbidden(
            "The bound scenario revision is invalid",
            code="authorization_binding_context_invalid",
        )
    if (
        requested_id is not None
        and resolve_scenario_target_id(run, requested_id) != scenario_id
    ):
        raise forbidden(
            "The request scenario target changed after authorization binding",
            code="authorization_binding_scenario_target_changed",
        )
    return scenario_id, expected_revision


def production_approval_scorecard_from_bound_request(
    request: Request,
    *,
    run_id: str,
) -> dict[str, Any]:
    """Consume the exact scorecard snapshot already admitted before OPA."""
    context = get_bound_resource_context(
        request,
        expected_kind=production_approval_context_kind(),
    )
    context_run_id = context.get("run_id")
    scorecard = context.get("scorecard")
    if context_run_id != run_id or not isinstance(scorecard, Mapping):
        raise forbidden(
            "The production-approval scorecard is not bound to this run",
            code="authorization_binding_scorecard_run_mismatch",
        )
    return dict(scorecard)


def bind_authorization_resource(
    request: Request,
    requirement: RouteAuthorizationRequirement,
    body_bytes: bytes,
    *,
    max_body_bytes: int | None = None,
) -> BoundAuthorizationResource:
    """Resolve the exact resource for a permission-preflighted unsafe request.

    Args:
        request: Matched HTTP request with path parameters and verified access
            scope installed by authentication middleware.
        requirement: The exact typed requirement declared on the matched route.
        body_bytes: Exact request bytes captured for later byte-identical replay.
        max_body_bytes: Optional test/deployment override for the body ceiling.

    Returns:
        An immutable binding suitable for OPA projection and later dependency
        identity checks.

    Raises:
        RuntimeHTTPError: If the body, identity, resource, ownership, or
            supporting service cannot be resolved without assumption.
    """
    if type(requirement) is not RouteAuthorizationRequirement:
        raise TypeError("requirement must be a RouteAuthorizationRequirement")
    if not isinstance(body_bytes, bytes):
        raise TypeError("body_bytes must be exact bytes")

    verification = getattr(
        getattr(request, "state", object()),
        "action_permission_verification",
        None,
    )
    if type(verification) is not ActionPermissionVerification:
        raise forbidden(
            "Exact action-permission preflight is required before resource binding",
            code="authorization_binding_preflight_required",
        )
    if verification.requirement is not requirement:
        raise forbidden(
            "Action-permission preflight does not match the route binding",
            code="authorization_binding_preflight_mismatch",
        )
    scope = _require_access_scope(request)
    scope_subject, scope_tenant_id, scope_identity_id, scope_roles = principal_from_access_scope(
        scope
    )
    if (
        verification.tenant_id != scope_tenant_id
        or verification.subject != scope_subject
        or verification.roles != scope_roles
        or verification.jwt_id != scope_identity_id
    ):
        raise forbidden(
            "Action-permission preflight and access scope do not identify the same principal",
            code="authorization_binding_identity_mismatch",
        )

    ceiling = _resolve_body_ceiling(max_body_bytes)
    if len(body_bytes) > ceiling:
        raise bad_request(
            "Authorization request body exceeds the configured limit",
            code="authorization_binding_body_too_large",
        )
    spec = requirement.resource_binding
    body = {} if not body_bytes and spec.allow_empty_body else _parse_json_object(body_bytes)
    _validate_required_binding_fields(body, spec)
    body_sha256 = _sha256(body_bytes)

    if spec.source is ResourceBindingSource.OWNED_EXISTING_PATH:
        return _bind_owned_existing_path(
            request,
            requirement=requirement,
            spec=spec,
            scope=scope,
            body=body,
            body_sha256=body_sha256,
        )
    if spec.source is ResourceBindingSource.OWNED_EXISTING_BATCH:
        return _bind_owned_existing_batch(
            request,
            requirement=requirement,
            spec=spec,
            scope=scope,
            body=body,
            body_sha256=body_sha256,
        )
    if spec.source is ResourceBindingSource.RESOLVED_SELECTOR:
        return _bind_resolved_selector(
            request,
            requirement=requirement,
            spec=spec,
            body_sha256=body_sha256,
        )
    if spec.source is ResourceBindingSource.RESOLVED_SELECTOR_BATCH:
        return _bind_resolved_selector_batch(
            request,
            requirement=requirement,
            spec=spec,
            scope=scope,
            body=body,
            body_sha256=body_sha256,
        )
    if spec.source is ResourceBindingSource.CANDIDATE_TARGET_SLOT:
        return _bind_candidate_target(
            request,
            requirement=requirement,
            spec=spec,
            scope=scope,
            body=body,
            body_sha256=body_sha256,
        )
    if spec.source is ResourceBindingSource.OWNED_PARENT_OR_REQUEST_COMPOSITE:
        return _bind_owned_parent_or_composite(
            request,
            requirement=requirement,
            spec=spec,
            scope=scope,
            body=body,
            body_sha256=body_sha256,
        )
    if spec.source is ResourceBindingSource.REQUEST_COMPOSITE:
        selectors = _selectors_from_body(body, spec.selector_fields)
        return _build_bound_resource(
            request=request,
            requirement=requirement,
            tenant_id=None,
            authority=BindingAuthority.REQUEST_BOUND,
            body_sha256=body_sha256,
            selectors=selectors,
        )
    if spec.source is ResourceBindingSource.TENANT_COLLECTION:
        selectors = (("tenant_id", _canonical_json(scope.tenant_id)),)
        return _build_bound_resource(
            request=request,
            requirement=requirement,
            tenant_id=scope.tenant_id,
            authority=BindingAuthority.TENANT_COLLECTION,
            body_sha256=body_sha256,
            selectors=selectors,
        )
    raise forbidden(
        "The route declares an unsupported resource-binding source",
        code="authorization_binding_source_unsupported",
    )


def _bind_owned_existing_path(
    request: Request,
    *,
    requirement: RouteAuthorizationRequirement,
    spec: ResourceBindingSpec,
    scope: AccessScope,
    body: Mapping[str, Any],
    body_sha256: str,
) -> BoundAuthorizationResource:
    parameter = cast("str", spec.path_parameter)
    value = _path_identifier(request, parameter)
    ctx = _require_runtime_context(request)
    resolver_kind = _OWNED_PATH_RESOLVERS.get((spec.resource_kind, parameter))
    if resolver_kind is _ResolverKind.ARTIFACT:
        resource_id, tenant_id = _resolve_owned_artifact(ctx, scope, value)
        selector_name = "artifact_id"
    elif resolver_kind is _ResolverKind.RUN:
        resource_id, tenant_id = _resolve_owned_run(ctx, scope, value)
        selector_name = "run_id"
    else:
        raise forbidden(
            "Owned path binding has no registered resolver",
            code="authorization_binding_path_unsupported",
        )
    selectors: tuple[tuple[str, str], ...] = (
        (selector_name, _canonical_json(resource_id)),
    )
    resolved_context_kind: str | None = None
    resolved_context: bytes | None = None
    if spec.resource_kind == "runtime.run.production_approval":
        _validate_production_approval_override_authority(body, scope=scope)
        resolved = resolve_production_approval_scorecard(
            body=body,
            control_service=resolve_control_service(request),
            run_id=resource_id,
            store=ctx.store,
        )
        selectors = (
            *selectors,
            ("quality_scorecard_ref", _canonical_json(resolved.reference)),
            ("scorecard_sha256", _canonical_json(resolved.payload_sha256)),
        )
        resolved_context_kind = production_approval_context_kind()
        resolved_context = resolved.context_bytes
    return _build_bound_resource(
        request=request,
        requirement=requirement,
        tenant_id=tenant_id,
        authority=BindingAuthority.OWNERSHIP_VERIFIED,
        body_sha256=body_sha256,
        selectors=selectors,
        resolved_context_kind=resolved_context_kind,
        resolved_context=resolved_context,
    )


def _validate_production_approval_override_authority(
    body: Mapping[str, Any],
    *,
    scope: AccessScope,
) -> None:
    """Reject client-authored override identity or signature before OPA."""
    raw_override = body.get("override")
    if raw_override is None:
        return
    if not isinstance(raw_override, Mapping):
        raise bad_request(
            "Production approval override must be an object",
            code="production_approval_override_invalid",
        )
    reviewer_identity = raw_override.get("reviewer_identity")
    if reviewer_identity != scope.user_sub:
        raise forbidden(
            "Override reviewer identity must equal the verified effective subject",
            code="production_approval_override_identity_mismatch",
        )
    if raw_override.get("signature") is not None:
        raise forbidden(
            "Client-asserted approval signatures are not authority",
            code="production_approval_client_signature_forbidden",
        )


def _bind_owned_existing_batch(
    request: Request,
    *,
    requirement: RouteAuthorizationRequirement,
    spec: ResourceBindingSpec,
    scope: AccessScope,
    body: Mapping[str, Any],
    body_sha256: str,
) -> BoundAuthorizationResource:
    field_name = cast("str", spec.body_field)
    values = _string_batch(body, field_name=field_name)
    ctx = _require_runtime_context(request)
    resolved: list[str] = []
    tenants: set[str] = set()
    resolver_kind = _OWNED_BATCH_RESOLVERS.get((spec.resource_kind, field_name))
    if resolver_kind is _ResolverKind.ARTIFACT:
        for value in values:
            artifact_id, tenant_id = _resolve_owned_artifact(ctx, scope, value)
            resolved.append(artifact_id)
            tenants.add(tenant_id)
    elif resolver_kind is _ResolverKind.RUN:
        for value in values:
            run_id, tenant_id = _resolve_owned_run(ctx, scope, value)
            resolved.append(run_id)
            tenants.add(tenant_id)
    else:
        raise forbidden(
            "Owned batch binding does not support the declared identifier field",
            code="authorization_binding_batch_unsupported",
        )
    canonical_values = tuple(sorted(resolved))
    if len(tenants) != 1:
        raise forbidden(
            "Authorization batch does not resolve to one verified tenant",
            code="authorization_binding_batch_tenant_mismatch",
        )
    selectors = ((field_name, _canonical_json(canonical_values)),)
    return _build_bound_resource(
        request=request,
        requirement=requirement,
        tenant_id=next(iter(tenants)),
        authority=BindingAuthority.OWNERSHIP_VERIFIED,
        body_sha256=body_sha256,
        selectors=selectors,
        include_body_in_digest=False,
    )


def _bind_resolved_selector(
    request: Request,
    *,
    requirement: RouteAuthorizationRequirement,
    spec: ResourceBindingSpec,
    body_sha256: str,
) -> BoundAuthorizationResource:
    parameter = cast("str", spec.path_parameter)
    resolver_kind = _RESOLVED_SELECTOR_RESOLVERS.get((spec.resource_kind, parameter))
    if resolver_kind is not _ResolverKind.PROMOTION:
        raise forbidden(
            "Resolved selector binding has no registered resolver",
            code="authorization_binding_selector_unsupported",
        )
    selector = _path_identifier(request, parameter)
    control = resolve_control_service(request)
    if control is None:
        raise service_unavailable(
            "Promotion resource resolver is unavailable",
            code="authorization_binding_resolver_unavailable",
        )
    try:
        candidates = control.list_promotion_candidates().candidates
    except Exception as exc:
        raise service_unavailable(
            "Promotion resource resolution failed",
            code="authorization_binding_resolver_failed",
        ) from exc
    matches = [candidate for candidate in candidates if candidate.promotion_id == selector]
    if len(matches) != 1:
        raise forbidden(
            "Promotion selector did not resolve to exactly one candidate",
            code="authorization_binding_selector_unresolved",
        )
    candidate_payload = matches[0].model_dump(mode="json")
    content_digest = _digest_payload(candidate_payload)
    selectors = (
        (parameter, _canonical_json(selector)),
        ("resolved_content_digest", _canonical_json(content_digest)),
    )
    return _build_bound_resource(
        request=request,
        requirement=requirement,
        tenant_id=None,
        authority=BindingAuthority.CONTENT_RESOLVED_UNSCOPED,
        body_sha256=body_sha256,
        selectors=selectors,
    )


def _bind_resolved_selector_batch(
    request: Request,
    *,
    requirement: RouteAuthorizationRequirement,
    spec: ResourceBindingSpec,
    scope: AccessScope,
    body: Mapping[str, Any],
    body_sha256: str,
) -> BoundAuthorizationResource:
    field_name = cast("str", spec.body_field)
    values = _string_batch(body, field_name=field_name)
    resolver_kind = _RESOLVED_BATCH_RESOLVERS.get((spec.resource_kind, field_name))
    if resolver_kind is not _ResolverKind.LINEAGE:
        raise forbidden(
            "Resolved batch binding does not support the declared selector field",
            code="authorization_binding_batch_unsupported",
        )
    ctx = _require_runtime_context(request)
    resolved = [_resolve_lineage_selector(ctx, scope, lineage_id) for lineage_id in values]
    tenants = {tenant_id for _canonical_id, tenant_id, _digest in resolved}
    if len(tenants) != 1:
        raise forbidden(
            "Lineage batch does not resolve to one verified tenant",
            code="authorization_binding_batch_tenant_mismatch",
        )
    canonical_entries = tuple(
        sorted(
            [
                {
                    "lineage_id": canonical_id,
                    "content_digest": digest,
                }
                for canonical_id, _tenant_id, digest in resolved
            ],
            key=lambda item: (item["lineage_id"], item["content_digest"]),
        )
    )
    selectors = ((field_name, _canonical_json(canonical_entries)),)
    return _build_bound_resource(
        request=request,
        requirement=requirement,
        tenant_id=next(iter(tenants)),
        authority=BindingAuthority.OWNERSHIP_VERIFIED,
        body_sha256=body_sha256,
        selectors=selectors,
        include_body_in_digest=False,
    )


def _bind_candidate_target(
    request: Request,
    *,
    requirement: RouteAuthorizationRequirement,
    spec: ResourceBindingSpec,
    scope: AccessScope,
    body: Mapping[str, Any],
    body_sha256: str,
) -> BoundAuthorizationResource:
    tenant_id: str | None = None
    selectors: list[tuple[str, str]] = []
    if spec.path_parameter is not None:
        if spec.path_parameter != "run_id":
            raise forbidden(
                "Candidate parent binding has no registered ownership resolver",
                code="authorization_binding_candidate_parent_unsupported",
            )
        parent_id = _path_identifier(request, spec.path_parameter)
        ctx = _require_runtime_context(request)
        canonical_parent, tenant_id = _resolve_owned_run(ctx, scope, parent_id)
        selectors.append((spec.path_parameter, _canonical_json(canonical_parent)))
        if spec.resource_kind == "runtime.run.scenario.candidate":
            try:
                run = ctx.run_index.get_run(canonical_parent)
            except (KeyError, TypeError, ValueError) as exc:
                raise forbidden(
                    "Scenario parent changed during authorization binding",
                    code="authorization_binding_run_unresolved",
                ) from exc
            requested_id = body.get("id")
            if requested_id is not None and not isinstance(requested_id, str):
                raise bad_request(
                    "Authorization scenario id must be a string",
                    code="authorization_binding_identifier_invalid",
                )
            scenario_id = resolve_scenario_target_id(run, requested_id)
            head = ctx.scenarios.get_persisted_head_or_none(scenario_id)
            if head is not None and head.baseline_run_id != canonical_parent:
                raise forbidden(
                    "Scenario target belongs to a different baseline run",
                    code="authorization_binding_scenario_parent_mismatch",
                )
            existing = (
                ctx.scenarios.get_persisted_manifest_for_head(head)
                if head is not None
                else None
            )
            expected_revision = existing.revision if existing is not None else 0
            selectors.extend(
                (
                    ("scenario_id", _canonical_json(scenario_id)),
                    ("expected_revision", _canonical_json(expected_revision)),
                )
            )
            if existing is not None:
                selectors.append(
                    (
                        "existing_manifest_digest",
                        _canonical_json(
                            _digest_payload(existing.model_dump(mode="json"))
                        ),
                    )
                )
            if head is not None:
                selectors.extend(
                    (
                        ("head_artifact_ref", _canonical_json(head.artifact_ref)),
                        ("head_manifest_hash", _canonical_json(head.manifest_hash)),
                    )
                )
            context = to_canonical_bytes(
                {
                    "context_version": _SCENARIO_TARGET_CONTEXT_KIND,
                    "run_id": canonical_parent,
                    "scenario_id": scenario_id,
                    "expected_revision": expected_revision,
                },
                spec=_RESOLVED_CONTEXT_CANON,
            )
            return _build_bound_resource(
                request=request,
                requirement=requirement,
                tenant_id=tenant_id,
                authority=(
                    BindingAuthority.OWNERSHIP_VERIFIED
                    if existing is not None
                    else BindingAuthority.CANDIDATE
                ),
                body_sha256=body_sha256,
                selectors=tuple(selectors),
                resolved_context_kind=_SCENARIO_TARGET_CONTEXT_KIND,
                resolved_context=context,
            )
    selectors.extend(_selectors_from_body(body, spec.selector_fields))
    if not selectors:
        raise bad_request(
            "Candidate binding has no resolvable target selectors",
            code="authorization_binding_candidate_empty",
        )
    return _build_bound_resource(
        request=request,
        requirement=requirement,
        tenant_id=tenant_id,
        authority=BindingAuthority.CANDIDATE,
        body_sha256=body_sha256,
        selectors=tuple(selectors),
    )


def _bind_owned_parent_or_composite(
    request: Request,
    *,
    requirement: RouteAuthorizationRequirement,
    spec: ResourceBindingSpec,
    scope: AccessScope,
    body: Mapping[str, Any],
    body_sha256: str,
) -> BoundAuthorizationResource:
    parent_field = cast("str", spec.parent_field)
    if parent_field != "run_id":
        raise forbidden(
            "Composite parent binding has no registered ownership resolver",
            code="authorization_binding_parent_unsupported",
        )
    parent = body.get(parent_field)
    selectors = list(_selectors_from_body(body, spec.selector_fields))
    tenant_id: str | None = None
    authority = BindingAuthority.REQUEST_BOUND
    if parent is not None:
        parent_id = _required_string(parent, field_name=parent_field)
        ctx = _require_runtime_context(request)
        canonical_parent, tenant_id = _resolve_owned_run(ctx, scope, parent_id)
        selectors.append((parent_field, _canonical_json(canonical_parent)))
        selectors.append(("parent_binding_authority", _canonical_json("ownership_verified")))
        authority = BindingAuthority.OWNERSHIP_VERIFIED
    selectors.sort()
    return _build_bound_resource(
        request=request,
        requirement=requirement,
        tenant_id=tenant_id,
        authority=authority,
        body_sha256=body_sha256,
        selectors=tuple(selectors),
    )


def _resolve_lineage_selector(
    ctx: RuntimeApiContext,
    scope: AccessScope,
    lineage_id: str,
) -> tuple[str, str, str]:
    artifact_candidate = lineage_id.removeprefix("artifact:")
    try:
        artifact_id = ArtifactID.model_validate(artifact_candidate)
    except (TypeError, ValueError):
        artifact_id = None
    if artifact_id is not None:
        canonical_id, tenant_id = _resolve_owned_artifact(ctx, scope, str(artifact_id))
        canonical_lineage_id = f"artifact:{canonical_id}"
        return canonical_lineage_id, tenant_id, canonical_id

    if lineage_id.startswith("scenario:"):
        remainder = lineage_id.removeprefix("scenario:")
        if ":" not in remainder:
            raise forbidden(
                "Scenario lineage selector has an unsupported form",
                code="authorization_binding_lineage_unsupported",
            )
        scenario_id, lineage_kind = remainder.rsplit(":", 1)
        scenario_id = _required_string(scenario_id, field_name="scenario_id")
        lineage_kind = _required_string(lineage_kind, field_name="lineage kind")
        try:
            manifest = ctx.scenarios.get_manifest(scenario_id)
        except Exception as exc:
            raise forbidden(
                "Scenario lineage selector could not be resolved",
                code="authorization_binding_lineage_unresolved",
            ) from exc
        _canonical_run_id, tenant_id = _resolve_owned_run(
            ctx,
            scope,
            manifest.baseline_run_id,
        )
        canonical_id = f"scenario:{manifest.id}:{lineage_kind}"
        content_digest = _digest_payload(
            {
                "lineage_id": canonical_id,
                "manifest": manifest.model_dump(mode="json"),
            }
        )
        return canonical_id, tenant_id, content_digest

    raise forbidden(
        "Lineage selector has an unsupported or unresolved form",
        code="authorization_binding_lineage_unsupported",
    )


def _resolve_owned_run(
    ctx: RuntimeApiContext,
    scope: AccessScope,
    value: str,
) -> tuple[str, str]:
    run_id = _required_string(value, field_name="run_id")
    try:
        run = ctx.run_index.get_run(run_id)
    except (KeyError, TypeError, ValueError) as exc:
        raise forbidden(
            "Run resource could not be resolved",
            code="authorization_binding_run_unresolved",
        ) from exc
    tenant_id = run.details.tenant_id
    if not isinstance(tenant_id, str) or not tenant_id:
        raise forbidden(
            "Run resource has no verified tenant ownership",
            code="authorization_binding_run_unscoped",
        )
    if tenant_id != scope.tenant_id:
        raise forbidden(
            "Run resource belongs to a different tenant",
            code="authorization_binding_run_tenant_mismatch",
        )
    return run.run_id, tenant_id


def _resolve_owned_artifact(
    ctx: RuntimeApiContext,
    scope: AccessScope,
    value: str,
) -> tuple[str, str]:
    raw = _required_string(value, field_name="artifact_id")
    try:
        artifact_id = ArtifactID.model_validate(raw)
    except (TypeError, ValueError) as exc:
        raise bad_request(
            "Artifact resource identifier is invalid",
            code="authorization_binding_artifact_invalid",
        ) from exc
    try:
        exists = ctx.store.has(artifact_id)
        tenant_id = ctx.run_index.get_artifact_tenant(str(artifact_id))
    except Exception as exc:
        raise service_unavailable(
            "Artifact ownership resolver failed",
            code="authorization_binding_resolver_failed",
        ) from exc
    if not exists:
        raise forbidden(
            "Artifact resource could not be resolved",
            code="authorization_binding_artifact_unresolved",
        )
    if not isinstance(tenant_id, str) or not tenant_id:
        raise forbidden(
            "Artifact resource has no verified tenant ownership",
            code="authorization_binding_artifact_unscoped",
        )
    if tenant_id != scope.tenant_id:
        raise forbidden(
            "Artifact resource belongs to a different tenant",
            code="authorization_binding_artifact_tenant_mismatch",
        )
    return str(artifact_id), tenant_id


def _require_runtime_context(request: Request) -> RuntimeApiContext:
    ctx = resolve_runtime_api_context(request)
    if ctx is None:
        raise service_unavailable(
            "Runtime resource resolver is unavailable",
            code="authorization_binding_resolver_unavailable",
        )
    return ctx


def _require_access_scope(request: Request) -> AccessScope:
    state = getattr(request, "state", object())
    scope = getattr(state, "authz_effective_scope", None)
    if not isinstance(scope, AccessScope):
        scope = getattr(state, "access_scope", None)
    if not isinstance(scope, AccessScope):
        raise unauthorized(
            "A verified access scope is required to bind this resource",
            code="authorization_binding_identity_required",
        )
    try:
        _validate_identifier(scope.tenant_id, field_name="access-scope tenant_id")
    except ValueError as exc:
        raise unauthorized(
            "The verified access scope has no valid tenant binding",
            code="authorization_binding_identity_invalid",
        ) from exc
    return scope


def _path_identifier(request: Request, name: str) -> str:
    path_params = getattr(request, "path_params", None)
    value = path_params.get(name) if isinstance(path_params, Mapping) else None
    return _required_string(value, field_name=f"path parameter {name}")


def _string_batch(body: Mapping[str, Any], *, field_name: str) -> tuple[str, ...]:
    value = body.get(field_name)
    if not isinstance(value, list) or not value:
        raise bad_request(
            "Authorization batch must contain a non-empty identifier list",
            code="authorization_binding_batch_empty",
        )
    if len(value) > _MAX_BATCH_ITEMS:
        raise bad_request(
            "Authorization batch exceeds the supported item limit",
            code="authorization_binding_batch_too_large",
        )
    values = tuple(_required_string(item, field_name=field_name) for item in value)
    return values


def _selectors_from_body(
    body: Mapping[str, Any],
    field_names: Sequence[str],
) -> tuple[tuple[str, str], ...]:
    selectors: list[tuple[str, str]] = []
    for field_name in field_names:
        if field_name not in body or body[field_name] is None:
            value = _ABSENT_SELECTOR
        else:
            value = _canonical_json(body[field_name])
        selectors.append((field_name, value))
    return tuple(sorted(selectors))


def _validate_required_binding_fields(
    body: Mapping[str, Any],
    spec: ResourceBindingSpec,
) -> None:
    for field_name in spec.required_selector_fields:
        value = body.get(field_name)
        if value is None or _is_empty_selector(value):
            raise bad_request(
                "Authorization request is missing a required resource selector",
                code="authorization_binding_selector_required",
            )
    if spec.required_selector_alternatives and not any(
        all(
            (value := body.get(field_name)) is not None and not _is_empty_selector(value)
            for field_name in alternative
        )
        for alternative in spec.required_selector_alternatives
    ):
        raise bad_request(
            "Authorization request does not satisfy a required resource-selector alternative",
            code="authorization_binding_selector_alternative_required",
        )
    if spec.parent_required:
        parent_field = cast("str", spec.parent_field)
        parent = body.get(parent_field)
        if parent is None or _is_empty_selector(parent):
            raise bad_request(
                "Authorization request is missing its required owned parent",
                code="authorization_binding_parent_required",
            )


def _is_empty_selector(value: object) -> bool:
    return isinstance(value, (str, list, tuple, dict)) and len(value) == 0


def _build_bound_resource(
    *,
    request: Request,
    requirement: RouteAuthorizationRequirement,
    tenant_id: str | None,
    authority: BindingAuthority,
    body_sha256: str,
    selectors: tuple[tuple[str, str], ...],
    include_body_in_digest: bool = True,
    resolved_context_kind: str | None = None,
    resolved_context: bytes | None = None,
) -> BoundAuthorizationResource:
    canonical_selectors = tuple(sorted(selectors))
    query_sha256 = _query_sha256(request)
    digest_payload = {
        "binding_version": "runtime.authorization.resource.v1",
        "permission": requirement.permission.value,
        "resource_kind": requirement.resource_binding.resource_kind,
        "authority": authority.value,
        "tenant_id": tenant_id,
        "body_sha256": body_sha256 if include_body_in_digest else None,
        "query_sha256": query_sha256,
        "selectors": canonical_selectors,
        "resolved_context_sha256": (
            _sha256(resolved_context) if resolved_context is not None else None
        ),
    }
    resource_digest = _digest_payload(digest_payload)
    return BoundAuthorizationResource(
        requirement=requirement,
        tenant_id=tenant_id,
        resource_kind=_resource_kind(requirement.resource_binding, authority),
        resource_id=_binding_resource_urn(resource_digest),
        resource_digest=resource_digest,
        authority=authority,
        body_sha256=body_sha256,
        query_sha256=query_sha256,
        canonical_selectors=canonical_selectors,
        resolved_context_kind=resolved_context_kind,
        resolved_context=resolved_context,
    )


def _query_sha256(request: Request) -> str:
    scope = getattr(request, "scope", None)
    raw_query = scope.get("query_string", b"") if isinstance(scope, Mapping) else b""
    if not isinstance(raw_query, bytes):
        raise forbidden(
            "The request query could not be bound exactly",
            code="authorization_binding_query_invalid",
        )
    return _sha256(raw_query)


def _resource_kind(spec: ResourceBindingSpec, authority: BindingAuthority) -> str:
    return f"{spec.resource_kind}.{authority.value}"


def _binding_resource_urn(resource_digest: str) -> str:
    return f"urn:polisyos:runtime-authorization-resource:v1:{resource_digest}"


def _parse_json_object(body_bytes: bytes) -> Mapping[str, Any]:
    if not body_bytes:
        raise bad_request(
            "Authorization request body must be a JSON object",
            code="authorization_binding_body_missing",
        )
    try:
        decoded = body_bytes.decode("utf-8")
        parsed = json.loads(
            decoded,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_non_finite_number,
        )
    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
        ValueError,
        RecursionError,
        OverflowError,
    ) as exc:
        raise bad_request(
            "Authorization request body is not valid canonicalizable JSON",
            code="authorization_binding_body_invalid",
        ) from exc
    if not isinstance(parsed, dict):
        raise bad_request(
            "Authorization request body must be a JSON object",
            code="authorization_binding_body_invalid",
        )
    return parsed


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON object key")
        result[key] = value
    return result


def _reject_non_finite_number(value: str) -> None:
    raise ValueError(f"non-finite JSON number is not supported: {value}")


def _canonical_json(value: object) -> str:
    try:
        return json.dumps(
            value,
            ensure_ascii=True,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    except (TypeError, ValueError, RecursionError, OverflowError) as exc:
        raise bad_request(
            "Authorization selector is not canonicalizable JSON",
            code="authorization_binding_selector_invalid",
        ) from exc


def _digest_payload(value: object) -> str:
    try:
        canonical_bytes = _canonical_json(value).encode("utf-8")
    except UnicodeEncodeError as exc:  # defensive if canonical encoding changes
        raise bad_request(
            "Authorization selector is not UTF-8 canonicalizable",
            code="authorization_binding_selector_invalid",
        ) from exc
    return _sha256(canonical_bytes)


def _sha256(value: bytes) -> str:
    return f"sha256:{hashlib.sha256(value).hexdigest()}"


def _validate_sha256(value: str, *, field_name: str) -> None:
    try:
        _ = ArtifactID.model_validate(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be a canonical SHA-256 digest") from exc


def _required_string(value: object, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise bad_request(
            f"Authorization {field_name} must be a string",
            code="authorization_binding_identifier_invalid",
        )
    try:
        _validate_identifier(value, field_name=field_name)
    except ValueError as exc:
        raise bad_request(
            f"Authorization {field_name} must be a non-empty trimmed string",
            code="authorization_binding_identifier_invalid",
        ) from exc
    return value


def _validate_identifier(value: str, *, field_name: str) -> None:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError(f"{field_name} must be a non-empty trimmed string")


def _resolve_body_ceiling(configured: int | None) -> int:
    if configured is not None:
        if configured <= 0:
            raise ValueError("max_body_bytes must be positive")
        return configured
    raw = os.getenv("POLISYOS_RUNTIME_AUTHZ_MAX_BODY_BYTES")
    if raw is None:
        return _DEFAULT_MAX_BODY_BYTES
    try:
        parsed = int(raw)
    except ValueError as exc:
        raise service_unavailable(
            "Authorization body limit is misconfigured",
            code="authorization_binding_configuration_invalid",
        ) from exc
    if parsed <= 0:
        raise service_unavailable(
            "Authorization body limit is misconfigured",
            code="authorization_binding_configuration_invalid",
        )
    return parsed


__all__ = [
    "BindingAuthority",
    "BoundAuthorizationResource",
    "bind_authorization_resource",
    "get_bound_resource_context",
    "production_approval_scorecard_from_bound_request",
    "scenario_target_from_bound_request",
]
