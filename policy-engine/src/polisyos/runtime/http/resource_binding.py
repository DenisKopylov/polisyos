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
from dataclasses import dataclass, replace
from enum import StrEnum
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, cast

from polisyos.common.canonical_profile import CanonicalProfileRefusalError
from polisyos.core import artifacts, canon
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
from polisyos.runtime.http.dependencies import RuntimeAccessScope as AccessScope
from polisyos.runtime.http.errors import (
    bad_request,
    conflict,
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
    from polisyos.runtime.http.services.scenario_heads import ScenarioHeadRecord
else:
    try:  # pragma: no cover - optional runtime dependency
        from fastapi import Request
    except ModuleNotFoundError:  # pragma: no cover
        Request = cast("Any", object)


_DEFAULT_MAX_BODY_BYTES = 1024 * 1024
_MAX_BATCH_ITEMS = 100
_ABSENT_SELECTOR = '{"present":false}'
_RESOLVED_CONTEXT_CANON = canon.CanonSpec(forbid_floats=False)
_SCENARIO_TARGET_CONTEXT_KIND = "runtime.scenario.target.v1"
_LINEAGE_BATCH_CONTEXT_KIND = "runtime.lineage.batch.v1"
_HUMAN_DECISION_CREATE_CONTEXT_KIND = "runtime.human_decision.create.v1"
_CONTROL_JOB_CANCELLATION_CONTEXT_KIND = "runtime.control_job.cancellation.v1"


class _ResolverKind(StrEnum):
    """Closed server-side resolvers registered for binding specs."""

    RUN = "run"
    JOB = "job"
    ARTIFACT = "artifact"
    PROMOTION = "promotion"
    LINEAGE = "lineage"


_OWNED_PATH_RESOLVERS = {
    ("runtime.control_job.cancel", "job_id"): _ResolverKind.JOB,
    ("runtime.run.normative_evidence", "run_id"): _ResolverKind.RUN,
    ("runtime.run.epoch_staleness", "run_id"): _ResolverKind.RUN,
    ("runtime.run.feedback_evaluation", "run_id"): _ResolverKind.RUN,
    ("runtime.run.predictive_calibration", "run_id"): _ResolverKind.RUN,
    ("runtime.run.method_execution_selection", "run_id"): _ResolverKind.RUN,
    ("runtime.run.method_metrics", "run_id"): _ResolverKind.RUN,
    ("runtime.run.reissue", "run_id"): _ResolverKind.RUN,
    ("runtime.run.production_approval", "run_id"): _ResolverKind.RUN,
    ("runtime.run.public_verification_record", "run_id"): _ResolverKind.RUN,
    ("runtime.run.human_decision", "run_id"): _ResolverKind.RUN,
    ("runtime.run.human_decision_gate", "run_id"): _ResolverKind.RUN,
    ("runtime.run.human_decision_record", "run_id"): _ResolverKind.RUN,
    ("runtime.run.human_decision_evidence", "run_id"): _ResolverKind.RUN,
    (
        "runtime.run.human_decision_review_effectiveness",
        "run_id",
    ): _ResolverKind.RUN,
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
            raise ValueError("resolved_context_kind and resolved_context must be present together")
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


@dataclass(frozen=True, slots=True)
class _ResolvedLineageSelector:
    """Carry one pre-policy lineage resolution into the frozen batch context."""

    requested_id: str
    canonical_id: str
    tenant_id: str
    content_digest: str
    scenario_head: Mapping[str, object] | None = None
    scenario_manifest: Mapping[str, Any] | None = None


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
        payload = canon.from_canonical_bytes(bound.resolved_context)
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


def _human_decision_create_selectors(
    *,
    body: Mapping[str, Any],
    exposure_session_ref: str,
    selectors: tuple[tuple[str, str], ...],
) -> tuple[tuple[str, str], ...]:
    """Derive the human-mutation selector quantity at its sole binding owner."""
    binding_fields = (
        "source_kind",
        "source_ref",
        "decision_request_ref",
        "decision_request_digest",
        "basis_ref",
        "basis_digest",
        "principal_binding_ref",
        "reviewer_separation_ref",
        "presentation_contract_ref",
        "action_kind",
        "action",
        "decision_action",
        "decision_mode",
    )
    canonical_selectors = tuple(
        sorted(
            (
                *selectors,
                *(
                    (
                        field_name,
                        _canonical_json(body.get(field_name))
                        if field_name in body
                        else _ABSENT_SELECTOR,
                    )
                    for field_name in binding_fields
                ),
                (
                    "exposure_token_sha256",
                    _canonical_json(
                        "sha256:" + hashlib.sha256(exposure_session_ref.encode("utf-8")).hexdigest()
                    ),
                ),
            )
        )
    )
    return canonical_selectors


def human_decision_create_from_bound_resource(
    bound: BoundAuthorizationResource,
    *,
    run_id: str,
) -> Mapping[str, Any]:
    """Resolve and recompute the full sealed mutation selectors and header context."""
    if (
        type(bound) is not BoundAuthorizationResource
        or bound.resolved_context_kind != _HUMAN_DECISION_CREATE_CONTEXT_KIND
        or not isinstance(bound.resolved_context, bytes)
    ):
        raise forbidden(
            "The human-decision authorization context is absent",
            code="authorization_binding_context_missing",
        )
    try:
        context = canon.from_canonical_bytes(bound.resolved_context)
    except (TypeError, ValueError) as exc:
        raise forbidden(
            "The human-decision authorization context is invalid",
            code="authorization_binding_context_invalid",
        ) from exc
    if (
        not isinstance(context, Mapping)
        or context.get("context_version") != _HUMAN_DECISION_CREATE_CONTEXT_KIND
    ):
        raise forbidden(
            "The human-decision authorization context has an unsupported version",
            code="authorization_binding_context_invalid",
        )
    body = context.get("body")
    exposure_session_ref = context.get("exposure_session_ref")
    if not isinstance(body, Mapping) or not isinstance(exposure_session_ref, str):
        raise forbidden(
            "The human-decision authorization context is incomplete",
            code="authorization_binding_context_invalid",
        )
    expected = _human_decision_create_selectors(
        body=body,
        exposure_session_ref=exposure_session_ref,
        selectors=(("run_id", _canonical_json(run_id)),),
    )
    if bound.canonical_selectors != expected:
        raise forbidden(
            "The human-decision selectors differ from the sealed mutation context",
            code="authorization_binding_context_mismatch",
        )
    return context


def human_decision_create_from_bound_request(request: Request) -> Mapping[str, Any]:
    """Return the exact pre-OPA human-decision request/header snapshot."""
    bound = getattr(getattr(request, "state", object()), "authz_bound_resource", None)
    return human_decision_create_from_bound_resource(
        bound, run_id=_path_identifier(request, "run_id")
    )


def lineage_batch_from_bound_request(
    request: Request,
    *,
    ctx: RuntimeApiContext,
    requested_lineage_ids: Sequence[str],
    requested_selected_artifact_refs: Sequence[artifacts.ArtifactRef | None] | None = None,
    requested_run_id: str | None = None,
) -> tuple[
    tuple[str, ...],
    Mapping[str, Mapping[str, Any]],
    tuple[artifacts.ArtifactRef | None, ...] | None,
    tuple[str | None, ...] | None,
    str | None,
    tuple[str | None, ...],
]:
    """Consume and revalidate the exact pre-policy lineage batch snapshot.

    Scenario manifests are returned from the immutable authorization context,
    never re-resolved after OPA. The current durable head must still equal the
    authorized head; a concurrent change therefore fails before route effects.
    """
    context = get_bound_resource_context(
        request,
        expected_kind=_LINEAGE_BATCH_CONTEXT_KIND,
    )
    if context.get("context_version") != _LINEAGE_BATCH_CONTEXT_KIND:
        raise forbidden(
            "The lineage authorization context has an unsupported version",
            code="authorization_binding_context_invalid",
        )
    raw_entries = context.get("entries")
    if not isinstance(raw_entries, list):
        raise forbidden(
            "The lineage authorization context has no resolved entries",
            code="authorization_binding_context_invalid",
        )

    entries: list[Mapping[str, Any]] = []
    for raw_entry in raw_entries:
        if not isinstance(raw_entry, Mapping):
            raise forbidden(
                "The lineage authorization context contains an invalid entry",
                code="authorization_binding_context_invalid",
            )
        requested_id = raw_entry.get("requested_lineage_id")
        canonical_id = raw_entry.get("lineage_id")
        content_digest = raw_entry.get("content_digest")
        values = (requested_id, canonical_id, content_digest)
        if any(
            not isinstance(value, str) or not value or value != value.strip() for value in values
        ):
            raise forbidden(
                "The lineage authorization context contains an invalid identifier",
                code="authorization_binding_context_invalid",
            )
        try:
            _validate_sha256(cast("str", content_digest), field_name="content_digest")
        except ValueError as exc:
            raise forbidden(
                "The lineage authorization context contains an invalid digest",
                code="authorization_binding_context_invalid",
            ) from exc
        entries.append(raw_entry)

    entries.sort(key=lambda entry: int(entry.get("request_index", -1)))
    if [entry.get("request_index") for entry in entries] != list(range(len(entries))):
        raise forbidden(
            "The lineage authorization context has invalid request positions",
            code="authorization_binding_context_invalid",
        )
    if [entry.get("requested_lineage_id") for entry in entries] != list(requested_lineage_ids):
        raise forbidden(
            "The request lineage batch differs from its authorized context",
            code="authorization_binding_context_mismatch",
        )

    selected_refs_present = context.get("selected_artifact_refs_present") is True
    context_run_id = context.get("run_id")
    if context_run_id != requested_run_id:
        raise forbidden(
            "The lineage run binding differs from its authorized context",
            code="authorization_binding_context_mismatch",
        )
    if selected_refs_present != (requested_selected_artifact_refs is not None):
        raise forbidden(
            "The selected artifact profile list differs from its authorized context",
            code="authorization_binding_context_mismatch",
        )
    if requested_selected_artifact_refs is not None:
        if len(requested_selected_artifact_refs) != len(entries):
            raise forbidden(
                "Selected artifact profiles do not align with lineage selectors",
                code="authorization_binding_context_mismatch",
            )
        for index, (requested_ref, entry) in enumerate(
            zip(requested_selected_artifact_refs, entries, strict=True)
        ):
            raw_ref = entry.get("selected_artifact_ref")
            canonical_ref = (
                requested_ref.model_dump(mode="json") if requested_ref is not None else None
            )
            if entry.get("request_index") != index or raw_ref != canonical_ref:
                raise forbidden(
                    "A selected artifact profile differs from its pre-policy binding",
                    code="authorization_binding_context_mismatch",
                )

    canonical_ids: list[str] = []
    scenario_manifests: dict[str, Mapping[str, Any]] = {}
    authorized_refs: list[artifacts.ArtifactRef | None] = []
    artifact_ref_provenances: list[str | None] = []
    source_run_ids: list[str | None] = []
    for entry in entries:
        requested_id = cast("str", entry["requested_lineage_id"])
        canonical_id = cast("str", entry["lineage_id"])
        content_digest = cast("str", entry["content_digest"])
        canonical_ids.append(canonical_id)
        raw_ref = entry.get("selected_artifact_ref")
        authorized_ref = (
            artifacts.ArtifactRef.model_validate(raw_ref) if isinstance(raw_ref, Mapping) else None
        )
        if authorized_ref is not None:
            try:
                ctx.lineage.verify_selected_artifact_ref(authorized_ref)
            except CanonicalProfileRefusalError as exc:
                raise conflict(
                    "Selected artifact profile changed after authorization",
                    code=exc.code,
                ) from exc
            except (TypeError, ValueError) as exc:
                raise conflict(
                    "Selected artifact profile changed after authorization",
                    code="authorization_binding_profile_mismatch",
                ) from exc
        expected_binding_status = (
            "verified"
            if authorized_ref is not None
            else ("not_established" if selected_refs_present else None)
        )
        if entry.get("profile_binding_status") != expected_binding_status:
            raise forbidden(
                "The selected profile status differs from its pre-policy binding",
                code="authorization_binding_context_invalid",
            )
        expected_source_run_id = context_run_id if authorized_ref is not None else None
        if entry.get("source_run_id") != expected_source_run_id:
            raise forbidden(
                "The selected profile run differs from its pre-policy binding",
                code="authorization_binding_context_invalid",
            )
        authorized_refs.append(authorized_ref)
        artifact_ref_provenances.append(cast("str | None", entry.get("artifact_ref_provenance")))
        source_run_ids.append(expected_source_run_id)

        scenario_head = entry.get("scenario_head")
        scenario_manifest = entry.get("scenario_manifest")
        if not canonical_id.startswith("scenario:"):
            if scenario_head is not None or scenario_manifest is not None:
                raise forbidden(
                    "A non-scenario lineage entry carries scenario authority",
                    code="authorization_binding_context_invalid",
                )
            continue
        if not isinstance(scenario_head, Mapping) or not isinstance(
            scenario_manifest,
            Mapping,
        ):
            raise forbidden(
                "A scenario lineage entry has no frozen head and manifest",
                code="authorization_binding_context_invalid",
            )
        remainder = canonical_id.removeprefix("scenario:")
        if ":" not in remainder:
            raise forbidden(
                "A scenario lineage entry has an invalid canonical identifier",
                code="authorization_binding_context_invalid",
            )
        scenario_id, _lineage_kind = remainder.rsplit(":", 1)
        if (
            scenario_manifest.get("id") != scenario_id
            or scenario_manifest.get("baseline_run_id") != scenario_head.get("baseline_run_id")
            or scenario_manifest.get("revision") != scenario_head.get("revision")
            or scenario_manifest.get("manifest_hash") != scenario_head.get("manifest_hash")
            or scenario_head.get("scenario_id") != scenario_id
            or _digest_payload(
                {
                    "lineage_id": canonical_id,
                    "manifest": dict(scenario_manifest),
                }
            )
            != content_digest
        ):
            raise forbidden(
                "A scenario lineage entry is not content-bound to its head",
                code="authorization_binding_context_invalid",
            )

        current_head = ctx.scenarios.get_persisted_head_or_none(scenario_id)
        if current_head is None or _scenario_head_context(current_head) != dict(scenario_head):
            raise conflict(
                "Scenario changed after authorization binding",
                code="scenario_authorization_binding_changed",
            )
        prior_manifest = scenario_manifests.get(canonical_id)
        if prior_manifest is not None and dict(prior_manifest) != dict(scenario_manifest):
            raise forbidden(
                "Duplicate scenario lineage entries disagree on authorized content",
                code="authorization_binding_context_invalid",
            )
        scenario_manifests[canonical_id] = MappingProxyType(dict(scenario_manifest))

    if context_run_id is not None and any(ref is not None for ref in authorized_refs):
        try:
            run = ctx.run_index.get_run(context_run_id)
            current_run_packet = ctx.lineage.selected_decision_packet_ref_for_run(run)
        except CanonicalProfileRefusalError as exc:
            raise conflict(
                "The run selected profile changed after authorization",
                code=exc.code,
            ) from exc
        except (KeyError, TypeError, ValueError) as exc:
            raise conflict(
                "The bound run changed after authorization",
                code="authorization_binding_run_unresolved",
            ) from exc
        for _entry, ref, provenance in zip(
            entries, authorized_refs, artifact_ref_provenances, strict=True
        ):
            if ref is None:
                continue
            if current_run_packet is None:
                raise conflict(
                    "The run selected profile changed after authorization",
                    code="authorization_binding_run_profile_unresolved",
                )
            expected_ref, expected_provenance = current_run_packet
            if (
                artifacts.artifact_ref_identity_key(ref)
                != artifacts.artifact_ref_identity_key(expected_ref)
                or provenance != expected_provenance
            ):
                raise conflict(
                    "The run selected profile changed after authorization",
                    code="authorization_binding_profile_context_changed",
                )
    return (
        tuple(canonical_ids),
        MappingProxyType(scenario_manifests),
        tuple(authorized_refs) if selected_refs_present else None,
        tuple(artifact_ref_provenances) if selected_refs_present else None,
        cast("str | None", context_run_id),
        tuple(source_run_ids),
    )


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
    if requested_id is not None and resolve_scenario_target_id(run, requested_id) != scenario_id:
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


def production_approval_inputs_from_bound_request(
    request: Request,
    *,
    run_id: str,
) -> tuple[dict[str, Any], str]:
    """Return the scorecard plus its exact immutable pre-OPA digest."""

    context = get_bound_resource_context(
        request,
        expected_kind=production_approval_context_kind(),
    )
    context_run_id = context.get("run_id")
    scorecard = context.get("scorecard")
    scorecard_digest = context.get("scorecard_sha256")
    if (
        context_run_id != run_id
        or not isinstance(scorecard, Mapping)
        or not isinstance(scorecard_digest, str)
        or not scorecard_digest.startswith("sha256:")
    ):
        raise forbidden(
            "The production-approval inputs are not bound to this run",
            code="authorization_binding_scorecard_run_mismatch",
        )
    return dict(scorecard), scorecard_digest


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
        if spec.resource_kind == "runtime.run.method_execution_selection":
            indexed_run = _resolve_method_execution_indexed_run(ctx, request, scope, value)
            resource_id = indexed_run.run_id
            tenant_id = indexed_run.details.tenant_id
        else:
            resource_id, tenant_id = _resolve_owned_run(ctx, scope, value)
        selector_name = "run_id"
    elif resolver_kind is _ResolverKind.JOB:
        control = resolve_control_service(request)
        if control is None:
            raise service_unavailable(
                "Control job resolver is unavailable",
                code="authorization_binding_resolver_unavailable",
            )
        try:
            record = control._control_store.get_job(value)
            if record is None:
                raise KeyError(value)
            creation_scope, _event = (
                control._control_store._reconcile_control_job_creation_envelope(record)
            )
        except Exception as exc:
            raise forbidden(
                "Control job resource could not be resolved",
                code="authorization_binding_job_unresolved",
            ) from exc
        if (
            creation_scope.status != "established"
            or creation_scope.tenant_id != scope.tenant_id
            or not scope.cell_id
            or creation_scope.cell_id != scope.cell_id
        ):
            raise forbidden(
                "Control job ownership is not established for this tenant and cell",
                code="authorization_binding_job_scope_mismatch",
            )
        resource_id, tenant_id, selector_name = record.job_id, creation_scope.tenant_id, "job_id"
    else:
        raise forbidden(
            "Owned path binding has no registered resolver",
            code="authorization_binding_path_unsupported",
        )
    selectors: tuple[tuple[str, str], ...] = tuple(
        sorted(
            (
                (selector_name, _canonical_json(resource_id)),
                *(
                    (
                        path_selector,
                        _canonical_json(_path_identifier(request, path_selector)),
                    )
                    for path_selector in spec.path_selector_parameters
                ),
                *(
                    (
                        query_selector,
                        _canonical_json(_query_identifier(request, query_selector)),
                    )
                    for query_selector in spec.query_selector_parameters
                ),
            )
        )
    )
    if resolver_kind is _ResolverKind.JOB:
        selectors = tuple(sorted((*selectors, ("cell_id", _canonical_json(scope.cell_id)))))
    resolved_context_kind: str | None = None
    resolved_context: bytes | None = None
    if resolver_kind is _ResolverKind.JOB:
        from polisyos.core.contracts.control import ControlJobCancellationRequest

        try:
            cancellation = ControlJobCancellationRequest.model_validate(body)
        except (TypeError, ValueError) as exc:
            raise bad_request(
                "Control job cancellation request is invalid",
                code="authorization_binding_job_cancellation_invalid",
            ) from exc
        resolved_context_kind = _CONTROL_JOB_CANCELLATION_CONTEXT_KIND
        resolved_context = canon.to_canonical_bytes(
            cancellation.model_dump(mode="json"), _RESOLVED_CONTEXT_CANON
        )
    elif spec.resource_kind == "runtime.run.production_approval":
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
            (
                "production_basis_ref",
                _canonical_json(body.get("production_basis_ref")),
            ),
            (
                "production_basis_sha256",
                _canonical_json(body.get("production_basis_digest")),
            ),
            (
                "human_decision_record_ref",
                _canonical_json(body.get("human_decision_record_ref")),
            ),
            (
                "human_decision_record_sha256",
                _canonical_json(body.get("human_decision_record_digest")),
            ),
        )
        resolved_context_kind = production_approval_context_kind()
        resolved_context = resolved.context_bytes
    elif spec.resource_kind == "runtime.run.human_decision":
        exposure_session_ref = request.headers.get(
            "X-PolicyOS-Human-Decision-Exposure",
            "",
        ).strip()
        if not exposure_session_ref:
            raise bad_request(
                "Human-decision mutation requires an exposure-session header",
                code="human_decision_exposure_session_required",
            )
        forbidden_authority_fields = {
            "actor_ref",
            "actor_key_id",
            "canonical_actor",
            "custody_key_id",
            "custody_signer_identity",
            "decided_at",
            "recorded_at",
            "reservation_id",
            "reservation_version",
            "rights_checks",
            "signature",
            "signer_identity",
            "status",
            "verifier_epoch",
        }
        present_forbidden = sorted(forbidden_authority_fields & set(body))
        if present_forbidden:
            raise bad_request(
                "Caller-authored human-decision authority fields are forbidden",
                code="human_decision_authority_fields_forbidden",
            )
        selectors = _human_decision_create_selectors(
            body=body, exposure_session_ref=exposure_session_ref, selectors=selectors
        )
        resolved_context_kind = _HUMAN_DECISION_CREATE_CONTEXT_KIND
        resolved_context = canon.to_canonical_bytes(
            {
                "context_version": _HUMAN_DECISION_CREATE_CONTEXT_KIND,
                "body": dict(body),
                "exposure_session_ref": exposure_session_ref,
            },
            _RESOLVED_CONTEXT_CANON,
        )
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
    selected_refs = _artifact_ref_batch(
        body, field_name="selected_artifact_refs", expected_count=len(values)
    )
    raw_run_id = body.get("run_id")
    if raw_run_id is not None and not isinstance(raw_run_id, str):
        raise bad_request(
            "Lineage batch run_id must be a string", code="authorization_binding_identifier_invalid"
        )
    canonical_run_id: str | None = None
    run_packet: tuple[artifacts.ArtifactRef, str] | None = None
    if raw_run_id is not None:
        canonical_run_id, run_tenant = _resolve_owned_run(ctx, scope, raw_run_id)
        tenants_for_run = {item.tenant_id for item in resolved}
        if tenants_for_run != {run_tenant}:
            raise forbidden(
                "Lineage batch selectors do not share the bound run tenant",
                code="authorization_binding_batch_tenant_mismatch",
            )
        if selected_refs is None:
            raise bad_request(
                "A run-bound lineage batch requires aligned selected_artifact_refs",
                code="authorization_binding_profile_list_required",
            )
        run = ctx.run_index.get_run(canonical_run_id)
        if selected_refs is not None and any(ref is not None for ref in selected_refs):
            try:
                run_packet = ctx.lineage.selected_decision_packet_ref_for_run(run)
            except CanonicalProfileRefusalError as exc:
                raise conflict(
                    "The run decision packet has no admissible selected profile",
                    code=exc.code,
                ) from exc
    if selected_refs is not None and len(selected_refs) != len(resolved):
        raise bad_request(
            "selected_artifact_refs must align with lineage_ids",
            code="authorization_binding_profile_list_mismatch",
        )

    tenants = {item.tenant_id for item in resolved}
    tenants.update(
        _resolve_owned_artifact(ctx, scope, str(ref.artifact_id))[1]
        for ref in (selected_refs or ())
        if ref is not None
    )
    if canonical_run_id is not None:
        tenants.add(_resolve_owned_run(ctx, scope, canonical_run_id)[1])
    if len(tenants) != 1:
        raise forbidden(
            "Lineage batch does not resolve to one verified tenant",
            code="authorization_binding_batch_tenant_mismatch",
        )

    context_entries: list[dict[str, Any]] = []
    canonical_entries_list: list[dict[str, Any]] = []
    artifact_ref_provenances: list[str | None] = []
    for index, (item, selected_ref) in enumerate(
        zip(resolved, selected_refs or [None] * len(resolved), strict=True)
    ):
        provenance: str | None = None
        if selected_ref is not None:
            if item.canonical_id != f"artifact:{selected_ref.artifact_id}":
                raise forbidden(
                    "Selected artifact profile does not identify the requested lineage",
                    code="authorization_binding_profile_lineage_mismatch",
                )
            try:
                ctx.lineage.verify_selected_artifact_ref(selected_ref)
            except CanonicalProfileRefusalError as exc:
                raise conflict(
                    "Selected artifact profile is not verified by the canonical reader",
                    code=exc.code,
                ) from exc
            except (TypeError, ValueError) as exc:
                raise conflict(
                    "Selected artifact profile does not match its stored manifest",
                    code="authorization_binding_profile_mismatch",
                ) from exc
            if canonical_run_id is not None:
                if run_packet is None:
                    raise forbidden(
                        "The bound run has no selected decision packet profile",
                        code="authorization_binding_run_profile_unresolved",
                    )
                expected_ref, expected_provenance = run_packet
                if artifacts.artifact_ref_identity_key(
                    selected_ref
                ) != artifacts.artifact_ref_identity_key(expected_ref):
                    raise forbidden(
                        "Selected artifact profile differs from the bound run output",
                        code="authorization_binding_profile_context_mismatch",
                    )
                provenance = expected_provenance
            else:
                provenance = "reader_materialized"
        artifact_ref_provenances.append(provenance)
        context_entry: dict[str, Any] = {
            "request_index": index,
            "requested_lineage_id": item.requested_id,
            "lineage_id": item.canonical_id,
            "content_digest": item.content_digest,
            "selected_artifact_ref": selected_ref.model_dump(mode="json")
            if selected_ref is not None
            else None,
            "artifact_ref_provenance": provenance,
            "profile_binding_status": "verified"
            if selected_ref is not None
            else ("not_established" if selected_refs is not None else None),
            "source_run_id": canonical_run_id if selected_ref is not None else None,
        }
        if item.scenario_head is not None and item.scenario_manifest is not None:
            context_entry["scenario_head"] = dict(item.scenario_head)
            context_entry["scenario_manifest"] = dict(item.scenario_manifest)
        context_entries.append(context_entry)
        canonical_entry = {
            "lineage_id": item.canonical_id,
            "content_digest": item.content_digest,
            "selected_artifact_ref": selected_ref.model_dump(mode="json")
            if selected_ref is not None
            else None,
        }
        canonical_entries_list.append(canonical_entry)
    canonical_entries = tuple(
        sorted(
            canonical_entries_list,
            key=lambda item: (
                item["lineage_id"],
                item["content_digest"],
                _canonical_json(item["selected_artifact_ref"]),
            ),
        )
    )
    context_entries.sort(key=lambda item: item["request_index"])
    context = canon.to_canonical_bytes(
        {
            "context_version": _LINEAGE_BATCH_CONTEXT_KIND,
            "entries": context_entries,
            "selected_artifact_refs_present": selected_refs is not None,
            "run_id": canonical_run_id,
        },
        spec=_RESOLVED_CONTEXT_CANON,
    )
    selectors_list = [(field_name, _canonical_json(canonical_entries))]
    if selected_refs is not None:
        selectors_list.append(
            (
                "selected_artifact_refs",
                _canonical_json(
                    [
                        ref.model_dump(mode="json") if ref is not None else None
                        for ref in selected_refs
                    ]
                ),
            )
        )
    if canonical_run_id is not None:
        selectors_list.append(("run_id", _canonical_json(canonical_run_id)))
    selectors = tuple(sorted(selectors_list))
    return _build_bound_resource(
        request=request,
        requirement=requirement,
        tenant_id=next(iter(tenants)),
        authority=BindingAuthority.OWNERSHIP_VERIFIED,
        body_sha256=body_sha256,
        selectors=selectors,
        include_body_in_digest=False,
        resolved_context_kind=_LINEAGE_BATCH_CONTEXT_KIND,
        resolved_context=context,
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
                ctx.scenarios.get_persisted_manifest_for_head(head) if head is not None else None
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
                        _canonical_json(_digest_payload(existing.model_dump(mode="json"))),
                    )
                )
            if head is not None:
                selectors.extend(
                    (
                        ("head_artifact_ref", _canonical_json(head.artifact_ref)),
                        ("head_manifest_hash", _canonical_json(head.manifest_hash)),
                    )
                )
            context = canon.to_canonical_bytes(
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
) -> _ResolvedLineageSelector:
    artifact_candidate = lineage_id.removeprefix("artifact:")
    try:
        artifact_id = artifacts.ArtifactID.model_validate(artifact_candidate)
    except TypeError, ValueError:
        artifact_id = None
    if artifact_id is not None:
        canonical_id, tenant_id = _resolve_owned_artifact(ctx, scope, str(artifact_id))
        canonical_lineage_id = f"artifact:{canonical_id}"
        return _ResolvedLineageSelector(
            requested_id=lineage_id,
            canonical_id=canonical_lineage_id,
            tenant_id=tenant_id,
            content_digest=canonical_id,
        )

    if lineage_id.startswith("run:"):
        remainder = lineage_id.removeprefix("run:")
        if ":" not in remainder:
            raise forbidden(
                "Run lineage selector has an unsupported form",
                code="authorization_binding_lineage_unsupported",
            )
        run_id, lineage_kind = remainder.rsplit(":", 1)
        run_id = _required_string(run_id, field_name="run_id")
        lineage_kind = _required_string(lineage_kind, field_name="lineage kind")
        if lineage_kind != "telemetry":
            raise forbidden(
                "Run lineage selector has an unsupported kind",
                code="authorization_binding_lineage_unsupported",
            )
        canonical_run_id, tenant_id = _resolve_owned_run(ctx, scope, run_id)
        canonical_id = f"run:{canonical_run_id}:telemetry"
        return _ResolvedLineageSelector(
            requested_id=lineage_id,
            canonical_id=canonical_id,
            tenant_id=tenant_id,
            content_digest=_digest_payload(
                {
                    "lineage_id": canonical_id,
                    "run_id": canonical_run_id,
                }
            ),
        )

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
        head = ctx.scenarios.get_persisted_head_or_none(scenario_id)
        if head is None:
            raise forbidden(
                "Scenario lineage selector could not be resolved",
                code="authorization_binding_lineage_unresolved",
            )
        manifest = ctx.scenarios.get_persisted_manifest_for_head(head)
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
        return _ResolvedLineageSelector(
            requested_id=lineage_id,
            canonical_id=canonical_id,
            tenant_id=tenant_id,
            content_digest=content_digest,
            scenario_head=_scenario_head_context(head),
            scenario_manifest=manifest.model_dump(mode="json"),
        )

    raise forbidden(
        "Lineage selector has an unsupported or unresolved form",
        code="authorization_binding_lineage_unsupported",
    )


def _scenario_head_context(head: ScenarioHeadRecord) -> dict[str, object]:
    return {
        "scenario_id": head.scenario_id,
        "baseline_run_id": head.baseline_run_id,
        "revision": head.revision,
        "artifact_ref": head.artifact_ref,
        "manifest_hash": head.manifest_hash,
        "updated_at": head.updated_at.isoformat(),
    }


def _resolve_method_execution_indexed_run(
    ctx: RuntimeApiContext,
    request: Request,
    scope: AccessScope,
    value: str,
) -> IndexedRunRecord:
    """Resolve the selected-method path to its actual Core trace under current ownership."""
    run_id = _required_string(value, field_name="run_id")
    used_control_alias = False
    try:
        indexed_run = ctx.run_index.get_run(run_id)
    except KeyError, TypeError, ValueError:
        control = resolve_control_service(request)
        resolve_binding = getattr(control, "_resolve_observational_method_core_run_binding", None)
        if not callable(resolve_binding):
            raise forbidden(
                "Run resource could not be resolved",
                code="authorization_binding_run_unresolved",
            ) from None
        try:
            binding = resolve_binding(
                control_run_id=run_id,
                tenant_id=scope.tenant_id,
                cell_id=scope.cell_id,
            )
        except (KeyError, RuntimeError, TypeError, ValueError) as exc:
            raise forbidden(
                "Run resource could not be resolved",
                code="authorization_binding_run_unresolved",
            ) from exc
        if (
            type(binding) is not tuple
            or len(binding) != 2
            or type(binding[0]) is not str
            or not binding[0]
            or type(binding[1]) is not str
            or not binding[1]
        ):
            raise forbidden(
                "Run resource could not be resolved",
                code="authorization_binding_run_unresolved",
            ) from None
        core_run_id, control_job_id = binding
        try:
            ctx.run_index.refresh(force=True)
            indexed_run = ctx.run_index.get_run(core_run_id)
            confirmed_binding = resolve_binding(
                control_run_id=run_id,
                tenant_id=scope.tenant_id,
                cell_id=scope.cell_id,
            )
        except (KeyError, RuntimeError, TypeError, ValueError) as exc:
            raise forbidden(
                "Run resource could not be resolved",
                code="authorization_binding_run_unresolved",
            ) from exc
        if confirmed_binding != binding:
            raise forbidden(
                "Run resource ownership changed during resolution",
                code="authorization_binding_run_unresolved",
            ) from None
        if (
            indexed_run.source_kind != "core_run"
            or indexed_run.run_id != core_run_id
            or indexed_run.details.run_id != core_run_id
            or indexed_run.summary.run_id != core_run_id
            or indexed_run.details.source_kind != "core_run"
            or indexed_run.summary.source_kind != "core_run"
            or indexed_run.summary.tenant_id != scope.tenant_id
            or indexed_run.summary.cell_id != scope.cell_id
        ):
            raise forbidden(
                "Run resource is not the actual Core attempt selected by the owner",
                code="authorization_binding_run_unresolved",
            ) from None
        details = indexed_run.details
        summary = indexed_run.summary
        if details.control_job_id == control_job_id and summary.control_job_id == control_job_id:
            pass
        elif (
            details.control_job_id is None
            and summary.control_job_id is None
            and details.status == "unknown"
            and summary.status == "unknown"
            and details.manifest_ref is None
            and details.execution_profile == summary.execution_profile
            and details.started_at == summary.started_at
            and summary.finished_at is None
            and details.finished_at is None
            and details.has_trace
            and summary.has_trace
            and summary.run_terminality.value == "non_terminal"
            and details.tenant_id == scope.tenant_id
            and summary.tenant_id == scope.tenant_id
            and details.cell_id == scope.cell_id
            and summary.cell_id == scope.cell_id
        ):
            # An active Core trace has no terminal manifest yet, so Core cannot
            # claim the job ID. The current scoped control-owner binding above is
            # the provenance for this projection association; preserve the actual
            # Core run ID and source kind rather than relabelling the artifact.
            indexed_run = replace(
                indexed_run,
                details=details.model_copy(update={"control_job_id": control_job_id}),
                summary=summary.model_copy(update={"control_job_id": control_job_id}),
            )
        else:
            raise forbidden(
                "Run resource is not the selected control-job attempt",
                code="authorization_binding_run_unresolved",
            ) from None
        used_control_alias = True

    tenant_id = indexed_run.details.tenant_id
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
    if used_control_alias and (
        not scope.cell_id
        or not indexed_run.details.cell_id
        or indexed_run.details.cell_id != scope.cell_id
    ):
        raise forbidden(
            "Run resource belongs to a different or unestablished cell",
            code="authorization_binding_run_cell_mismatch",
        )
    if (
        indexed_run.source_kind != "core_run"
        or indexed_run.run_id != indexed_run.details.run_id
        or not indexed_run.details.has_trace
    ):
        raise forbidden(
            "Run resource has no verified Core trace identity",
            code="authorization_binding_run_unresolved",
        )
    return indexed_run


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
        artifact_id = artifacts.ArtifactID.model_validate(raw)
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


def _artifact_ref_batch(
    body: Mapping[str, Any],
    *,
    field_name: str,
    expected_count: int,
) -> tuple[artifacts.ArtifactRef | None, ...] | None:
    if field_name not in body:
        return None
    value = body[field_name]
    if not isinstance(value, list) or len(value) != expected_count:
        raise bad_request(
            "Selected artifact profiles must align with lineage_ids",
            code="authorization_binding_profile_list_mismatch",
        )
    refs: list[artifacts.ArtifactRef | None] = []
    for item in value:
        if item is None:
            refs.append(None)
            continue
        if not isinstance(item, Mapping):
            raise bad_request(
                "Selected artifact profile must be a typed reference or null",
                code="authorization_binding_profile_invalid",
            )
        try:
            ref = artifacts.ArtifactRef.model_validate(item)
        except (TypeError, ValueError) as exc:
            raise bad_request(
                "Selected artifact profile is malformed",
                code="authorization_binding_profile_invalid",
            ) from exc
        if ref.manifest_profile_sha256 is None:
            raise bad_request(
                "Selected artifact profile must name a manifest profile",
                code="authorization_binding_profile_unqualified",
            )
        refs.append(ref)
    return tuple(refs)


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


def _query_identifier(request: Request, name: str) -> str:
    values = request.query_params.getlist(name)
    if len(values) != 1:
        raise bad_request(
            "Authorization query selector must occur exactly once",
            code="authorization_binding_query_selector_invalid",
        )
    return _required_string(values[0], field_name=name)


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
        _ = artifacts.ArtifactID.model_validate(value)
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
    "human_decision_create_from_bound_request",
    "human_decision_create_from_bound_resource",
    "lineage_batch_from_bound_request",
    "production_approval_inputs_from_bound_request",
    "production_approval_scorecard_from_bound_request",
    "scenario_target_from_bound_request",
]
