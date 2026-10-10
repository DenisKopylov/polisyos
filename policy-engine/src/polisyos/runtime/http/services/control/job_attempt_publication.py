"""ControlJobAttemptPublicationMixin implementation for durable control-job lifecycle facets."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field

from polisyos.core import artifacts, registry, run
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.canon import content_hash as canonical_content_hash
from polisyos.core.canon import to_canonical_bytes
from polisyos.core.contracts.control import NaturalLanguageRunRequest
from polisyos.runtime.http.services.adapters.core_run import (
    derive_control_job_core_run_id,
    derive_core_run_dir,
    load_completed_control_job_core_run_source,
    load_terminal_core_run_source,
)
from polisyos.runtime.http.services.control.workspace_loop_transition import (
    _WorkflowExecutionNonAuthorityError,
)
from polisyos.runtime.quality.evaluation_modes import (
    EvaluationMode,
    resolve_evaluation_mode,
    resolve_execution_intent_band,
)
from polisyos.runtime.quality.evaluation_safety import EvaluationAttemptIntake

from ..control_plane_store import (
    ControlJobExecutionAdmission,
    ControlJobExecutionScope,
    ControlJobLeaseLostError,
    ControlJobRecord,
)

if TYPE_CHECKING:
    from polisyos.common.logger import _CompatLogger
    from polisyos.runtime.quality.agent_action_authority import AgentActionPermissionSnapshot
import hashlib
import json

_EXECUTION_INTENT_BINDING_SCHEMA = "polisyos.runtime.control_execution_intent.v2"
_NL_AUTHORIZATION_RECEIPT_KEY = "nl_authorization_receipt"
_NL_REQUEST_SNAPSHOT_KEY = "nl_request_snapshot"
_NL_REQUEST_SNAPSHOT_SCHEMA = "polisyos.runtime.control_nl_request_snapshot.v1"
_NL_REQUEST_SNAPSHOT_DIGEST_PROFILE = (
    "polisyos.runtime.authorization.nl_request_snapshot.canonical_json.v1"
)

_EVALUATION_SAFETY_ATTEMPT_KEY = "evaluation_safety_attempt"

_EVALUATION_SAFETY_EXECUTION_CONTEXT_KEY = "_polisyos_eval_safety_execution_context"

_EXECUTION_INTENT_BINDING_KEY = "execution_intent_binding"

_NL_ROUTE_ID = "POST /api/v1/control/runs/nl"

_NL_ROUTE_ACTION = "control.launch_nl_run"


def _nl_request_body_bytes(request: NaturalLanguageRunRequest) -> bytes:
    """Serialize a typed request deterministically for non-HTTP owner tests."""
    return json.dumps(
        request.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _validate_nl_request_json_values(request: NaturalLanguageRunRequest) -> None:
    """Reject values the runtime's canonical JSON owner cannot represent."""
    from polisyos.runtime.http.resource_binding import _digest_payload

    _digest_payload(request.model_dump(mode="python"))


def _nl_request_snapshot_content_hash(snapshot: Mapping[str, Any]) -> str:
    """Hash the pinned JSON request snapshot profile, including finite numbers."""
    if (
        snapshot.get("schema_version") != _NL_REQUEST_SNAPSHOT_SCHEMA
        or snapshot.get("digest_profile") != _NL_REQUEST_SNAPSHOT_DIGEST_PROFILE
    ):
        raise ValueError("nl_authorized_request_snapshot_digest_profile_invalid")
    from polisyos.runtime.http.resource_binding import _digest_payload

    return _digest_payload(dict(snapshot))


class _ControlExecutionIntentBinding(BaseModel):
    """Strict durable binding between an NL request, its route, and its owner."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["polisyos.runtime.control_execution_intent.v2"]
    intent_band: Literal[
        "candidate_only",
        "simulate_only_attempt",
        "data_trust_required",
        "eval_safety_required",
        "not_established",
    ]
    admission_status: Literal["established", "not_established"]
    canonical_mode: EvaluationMode | None
    mode_token_hash: str | None
    attempt_id: str | None
    attempt_content_hash: str | None
    route_id: Literal["POST /api/v1/control/runs/nl"]
    route_action: Literal["control.launch_nl_run"]
    actor_subject: str = Field(min_length=1)
    actor_authenticated: bool
    actor_roles: tuple[str, ...]
    authorization_receipt: dict[str, Any] | None
    admission_surface: Literal["served_route"]
    tenant_id: str | None
    cell_id: str | None
    job_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    intent_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


def _build_nl_authorization_receipt(
    bound_permission: object,
    *,
    request_id: str | None,
    request: NaturalLanguageRunRequest,
    request_body_bytes: bytes,
    request_query_bytes: bytes,
    normalized_llm_models: list[str],
) -> dict[str, Any]:
    """Project the sealed route proof into a replayable owner-derived receipt."""
    from polisyos.runtime.http.authorization import (
        ActionPermissionVerification,
        BoundActionPermissionVerification,
        ResourceBindingSource,
    )
    from polisyos.runtime.http.permissions import RuntimePermission
    from polisyos.runtime.http.resource_binding import (
        BindingAuthority,
        BoundAuthorizationResource,
        _canonical_json,
        _digest_payload,
        _parse_json_object,
    )
    from polisyos.runtime.quality.agent_action_authority import (
        AgentActionPermissionSnapshot,
        agent_action_content_hash,
        agent_action_permission_hash,
    )

    if type(bound_permission) is not BoundActionPermissionVerification:
        raise ValueError("nl_route_authorization_proof_not_established")
    verification = bound_permission.verification
    resource = bound_permission.bound_resource
    requirement = verification.requirement
    spec = requirement.resource_binding
    if (
        type(verification) is not ActionPermissionVerification
        or type(resource) is not BoundAuthorizationResource
        or resource.requirement is not requirement
        or requirement.permission is not RuntimePermission.RUNS_LAUNCH
        or spec.source is not ResourceBindingSource.TENANT_COLLECTION
        or spec.resource_kind != "runtime.run_collection.nl"
        or any(
            getattr(spec, field_name) not in (None, (), False)
            for field_name in (
                "path_parameter",
                "path_selector_parameters",
                "query_selector_parameters",
                "body_field",
                "parent_field",
                "selector_fields",
                "required_selector_fields",
                "required_selector_alternatives",
                "parent_required",
                "allow_empty_body",
            )
        )
        or resource.authority is not BindingAuthority.TENANT_COLLECTION
        or resource.tenant_id != verification.tenant_id
        or not verification.tenant_id.strip()
        or requirement.permission not in verification.granted_permissions
        or resource.resolved_context is not None
        or resource.canonical_selectors != (("tenant_id", _canonical_json(verification.tenant_id)),)
    ):
        raise ValueError("nl_route_authorization_proof_binding_mismatch")

    expected_resource_digest = _digest_payload(
        {
            "binding_version": "runtime.authorization.resource.v1",
            "permission": requirement.permission.value,
            "resource_kind": spec.resource_kind,
            "authority": resource.authority.value,
            "tenant_id": resource.tenant_id,
            "body_sha256": resource.body_sha256,
            "query_sha256": resource.query_sha256,
            "selectors": resource.canonical_selectors,
            "resolved_context_sha256": None,
        }
    )
    if (
        resource.resource_digest != expected_resource_digest
        or resource.body_sha256 != "sha256:" + hashlib.sha256(request_body_bytes).hexdigest()
        or resource.query_sha256 != "sha256:" + hashlib.sha256(request_query_bytes).hexdigest()
    ):
        raise ValueError("nl_route_authorization_resource_digest_mismatch")
    _parse_json_object(request_body_bytes)
    try:
        parsed_request = NaturalLanguageRunRequest.model_validate_json(request_body_bytes)
    except (TypeError, ValueError) as exc:
        raise ValueError("nl_route_authorization_request_body_invalid") from exc
    if parsed_request.model_dump(mode="json") != request.model_dump(mode="json"):
        raise ValueError("nl_route_authorization_request_body_mismatch")
    request_snapshot = {
        "schema_version": _NL_REQUEST_SNAPSHOT_SCHEMA,
        "digest_profile": _NL_REQUEST_SNAPSHOT_DIGEST_PROFILE,
        "request": request.model_dump(mode="json"),
        "normalized_llm_models": list(normalized_llm_models),
    }
    snapshot = AgentActionPermissionSnapshot(
        subject=verification.subject,
        tenant_id=verification.tenant_id,
        jwt_id=verification.jwt_id,
        roles=tuple(sorted(role.value for role in verification.roles)),
        authorization_source=verification.authorization_source,
        required_permission=requirement.permission.value,
        granted_permissions=tuple(
            sorted(permission.value for permission in verification.granted_permissions)
        ),
        resource_digest=resource.resource_digest,
        resource_kind=resource.resource_kind,
        resource_authority=resource.authority.value,
        body_sha256=resource.body_sha256,
        query_sha256=resource.query_sha256,
    )
    permission_hash = agent_action_permission_hash(bound_permission)
    if agent_action_content_hash(snapshot) != permission_hash:
        raise ValueError("nl_route_authorization_snapshot_mismatch")
    receipt_payload: dict[str, Any] = {
        "schema_version": "polisyos.runtime.nl_route_authorization_receipt.v1",
        "route_id": _NL_ROUTE_ID,
        "request_id": request_id,
        "permission_snapshot": snapshot.model_dump(mode="json"),
        "permission_proof_hash": permission_hash,
        "request_content_hash": _nl_request_snapshot_content_hash(request_snapshot),
        "resource": {
            "resource_id": resource.resource_id,
            "resource_digest": resource.resource_digest,
            "resource_kind": resource.resource_kind,
            "authority": resource.authority.value,
            "tenant_id": resource.tenant_id,
            "body_sha256": resource.body_sha256,
            "query_sha256": resource.query_sha256,
            "selectors": [list(pair) for pair in resource.canonical_selectors],
        },
    }
    receipt_payload["receipt_digest"] = canonical_content_hash(
        to_canonical_bytes(receipt_payload),
        prefix=True,
    )
    return receipt_payload


def _build_control_execution_intent_binding(
    payload: Mapping[str, Any],
    *,
    job_id: str,
    run_id: str,
    actor: Mapping[str, Any],
) -> dict[str, Any]:
    """Build a replayable, typed binding for the served NL launch intent."""
    raw_context = payload.get("context")
    context_is_valid = raw_context is None or isinstance(raw_context, Mapping)
    context = raw_context if isinstance(raw_context, Mapping) else {}
    has_attempt = not context_is_valid or _EVALUATION_SAFETY_ATTEMPT_KEY in context
    raw_attempt = context.get(_EVALUATION_SAFETY_ATTEMPT_KEY) if context_is_valid else raw_context
    raw_mode = (
        raw_attempt.get("requested_mode_token")
        if isinstance(raw_attempt, Mapping)
        and isinstance(raw_attempt.get("requested_mode_token"), str)
        else None
    )
    mode_resolution = resolve_evaluation_mode(raw_mode)
    canonical_mode = mode_resolution.canonical_mode
    intent_band = resolve_execution_intent_band(
        attempt_present=has_attempt,
        mode_resolution=mode_resolution,
    ).value
    raw_authorization_receipt = payload.get(_NL_AUTHORIZATION_RECEIPT_KEY)
    authorization_receipt = (
        _validate_nl_authorization_receipt(raw_authorization_receipt)
        if raw_authorization_receipt is not None
        else None
    )
    _validate_nl_request_snapshot(
        payload,
        authorization_receipt if isinstance(authorization_receipt, Mapping) else None,
    )
    admission_status = (
        "established" if isinstance(authorization_receipt, Mapping) else "not_established"
    )

    attempt_content_hash = (
        canonical_content_hash(to_canonical_bytes(raw_attempt), prefix=True)
        if has_attempt
        else None
    )
    attempt_id = (
        raw_attempt.get("attempt_id")
        if isinstance(raw_attempt, Mapping) and isinstance(raw_attempt.get("attempt_id"), str)
        else None
    )
    if has_attempt:
        # The caller's derived resolution is not an authority source. Recompute it
        # from the exact requested token, then require the full typed intake shape.
        if not isinstance(raw_attempt, Mapping) or mode_resolution.status != "accepted":
            admission_status = "not_established"
        else:
            intake_payload = dict(raw_attempt)
            intake_payload["mode_resolution"] = mode_resolution.model_dump(mode="json")
            try:
                parsed_attempt = EvaluationAttemptIntake.model_validate(intake_payload)
            except Exception:
                admission_status = "not_established"
            else:
                attempt_id = parsed_attempt.attempt_id
                if (
                    not bool(actor.get("authenticated"))
                    or not isinstance(actor.get("subject"), str)
                    or not str(actor.get("subject")).strip()
                    or not isinstance(actor.get("tenant_id"), str)
                    or not str(actor.get("tenant_id")).strip()
                    or not isinstance(actor.get("cell_id"), str)
                    or not str(actor.get("cell_id")).strip()
                ):
                    admission_status = "not_established"
                if not isinstance(authorization_receipt, Mapping):
                    admission_status = "not_established"

    actor_roles = actor.get("roles")
    normalized_roles = tuple(
        sorted(role for role in actor_roles if isinstance(role, str))
        if isinstance(actor_roles, (list, tuple, set, frozenset))
        else ()
    )
    digest_payload: dict[str, Any] = {
        "schema_version": _EXECUTION_INTENT_BINDING_SCHEMA,
        "intent_band": intent_band,
        "admission_status": admission_status,
        "canonical_mode": canonical_mode,
        "mode_token_hash": mode_resolution.source_token_hash if has_attempt else None,
        "attempt_id": attempt_id,
        "attempt_content_hash": attempt_content_hash,
        "route_id": _NL_ROUTE_ID,
        "route_action": _NL_ROUTE_ACTION,
        "actor_subject": str(actor.get("subject") or "anonymous"),
        "actor_authenticated": bool(actor.get("authenticated")),
        "actor_roles": normalized_roles,
        "tenant_id": (
            actor.get("tenant_id")
            if isinstance(actor.get("tenant_id"), str)
            and actor["tenant_id"].strip()
            and actor["tenant_id"].casefold() != "tenant-unknown"
            else None
        ),
        "cell_id": (
            actor.get("cell_id")
            if isinstance(actor.get("cell_id"), str)
            and actor["cell_id"].strip()
            and actor["cell_id"].casefold() != "cell-unknown"
            else None
        ),
        "job_id": job_id,
        "run_id": run_id,
        "authorization_receipt": (
            dict(authorization_receipt) if isinstance(authorization_receipt, Mapping) else None
        ),
        "admission_surface": "served_route",
    }
    digest = canonical_content_hash(to_canonical_bytes(digest_payload), prefix=True)
    return _ControlExecutionIntentBinding(
        **digest_payload,
        intent_digest=digest,
    ).model_dump(mode="json")


def _validate_nl_authorization_resource(
    resource: object, snapshot: AgentActionPermissionSnapshot
) -> None:
    from polisyos.runtime.http.permissions import RuntimePermission
    from polisyos.runtime.http.resource_binding import _canonical_json, _digest_payload

    if not isinstance(resource, Mapping):
        raise ValueError("nl_route_authorization_resource_missing")
    if set(resource) != {
        "resource_id",
        "resource_digest",
        "resource_kind",
        "authority",
        "tenant_id",
        "body_sha256",
        "query_sha256",
        "selectors",
    }:
        raise ValueError("nl_route_authorization_resource_shape_invalid")
    expected_selectors = [["tenant_id", _canonical_json(snapshot.tenant_id)]]
    resource_id = resource.get("resource_id")
    if (
        snapshot.required_permission != RuntimePermission.RUNS_LAUNCH.value
        or RuntimePermission.RUNS_LAUNCH.value not in snapshot.granted_permissions
        or snapshot.resource_kind != "runtime.run_collection.nl.tenant_collection"
        or snapshot.resource_authority != "tenant_collection"
        or resource.get("resource_kind") != snapshot.resource_kind
        or resource.get("authority") != snapshot.resource_authority
        or resource.get("tenant_id") != snapshot.tenant_id
        or resource.get("body_sha256") != snapshot.body_sha256
        or resource.get("query_sha256") != snapshot.query_sha256
        or resource.get("selectors") != expected_selectors
        or not isinstance(resource_id, str)
        or not resource_id.startswith("urn:polisyos:runtime-authorization-resource:v1:")
    ):
        raise ValueError("nl_route_authorization_resource_binding_mismatch")
    resource_digest = _digest_payload(
        {
            "binding_version": "runtime.authorization.resource.v1",
            "permission": RuntimePermission.RUNS_LAUNCH.value,
            "resource_kind": "runtime.run_collection.nl",
            "authority": "tenant_collection",
            "tenant_id": snapshot.tenant_id,
            "body_sha256": snapshot.body_sha256,
            "query_sha256": snapshot.query_sha256,
            "selectors": (tuple(expected_selectors[0]),),
            "resolved_context_sha256": None,
        }
    )
    if (
        resource.get("resource_digest") != resource_digest
        or not resource_id.endswith(resource_digest)
        or snapshot.resource_digest != resource_digest
    ):
        raise ValueError("nl_route_authorization_resource_digest_mismatch")


def _validate_nl_authorization_receipt(receipt: object) -> dict[str, Any]:
    """Recompute the NL route's permission snapshot and tenant binding receipt."""
    from polisyos.runtime.quality.agent_action_authority import (
        AgentActionPermissionSnapshot,
        agent_action_content_hash,
    )

    if not isinstance(receipt, Mapping):
        raise ValueError("nl_route_authorization_receipt_missing")
    try:
        receipt_data = dict(receipt)
        if (
            set(receipt_data)
            != {
                "schema_version",
                "route_id",
                "request_id",
                "permission_snapshot",
                "permission_proof_hash",
                "request_content_hash",
                "resource",
                "receipt_digest",
            }
            or receipt_data.get("schema_version")
            != "polisyos.runtime.nl_route_authorization_receipt.v1"
            or receipt_data.get("route_id") != _NL_ROUTE_ID
            or not isinstance(receipt_data.get("request_id"), str)
            or not str(receipt_data["request_id"]).strip()
        ):
            raise ValueError("nl_route_authorization_receipt_identity_mismatch")
        snapshot = AgentActionPermissionSnapshot.model_validate(
            receipt_data.get("permission_snapshot")
        )
        request_content_hash = receipt_data.get("request_content_hash")
        if (
            not isinstance(request_content_hash, str)
            or len(request_content_hash) != 71
            or not request_content_hash.startswith("sha256:")
            or any(char not in "0123456789abcdef" for char in request_content_hash[7:])
        ):
            raise ValueError("nl_route_authorization_request_hash_invalid")
        _validate_nl_authorization_resource(receipt_data.get("resource"), snapshot)
        permission_hash = agent_action_content_hash(snapshot)
        if receipt_data.get("permission_proof_hash") != permission_hash:
            raise ValueError("nl_route_authorization_permission_hash_mismatch")
        digest_payload = {
            key: value for key, value in receipt_data.items() if key != "receipt_digest"
        }
        expected_receipt_digest = canonical_content_hash(
            to_canonical_bytes(digest_payload),
            prefix=True,
        )
        if receipt_data.get("receipt_digest") != expected_receipt_digest:
            raise ValueError("nl_route_authorization_receipt_digest_mismatch")
        return receipt_data
    except (TypeError, ValueError, KeyError) as exc:
        if isinstance(exc, ValueError) and str(exc).startswith("nl_route_authorization_"):
            raise
        raise ValueError("nl_route_authorization_receipt_invalid") from exc


def _validate_nl_request_snapshot(
    payload: Mapping[str, Any],
    authorization_receipt: Mapping[str, Any] | None,
) -> None:
    """Reconcile the authorized typed request snapshot with the executable payload."""
    raw_snapshot = payload.get(_NL_REQUEST_SNAPSHOT_KEY)
    if not isinstance(raw_snapshot, Mapping) or set(raw_snapshot) != {
        "schema_version",
        "digest_profile",
        "request",
        "normalized_llm_models",
    }:
        raise ValueError("nl_authorized_request_snapshot_missing")
    if raw_snapshot.get("schema_version") != _NL_REQUEST_SNAPSHOT_SCHEMA:
        raise ValueError("nl_authorized_request_snapshot_schema_invalid")
    if raw_snapshot.get("digest_profile") != _NL_REQUEST_SNAPSHOT_DIGEST_PROFILE:
        raise ValueError("nl_authorized_request_snapshot_digest_profile_invalid")
    raw_request = raw_snapshot.get("request")
    normalized_models = raw_snapshot.get("normalized_llm_models")
    if (
        not isinstance(raw_request, Mapping)
        or not isinstance(normalized_models, list)
        or not normalized_models
        or any(not isinstance(model, str) or not model.strip() for model in normalized_models)
    ):
        raise ValueError("nl_authorized_request_snapshot_shape_invalid")
    try:
        request = NaturalLanguageRunRequest.model_validate(dict(raw_request))
    except (TypeError, ValueError) as exc:
        raise ValueError("nl_authorized_request_snapshot_invalid") from exc
    request_values = request.model_dump(mode="json")
    snapshot = {
        "schema_version": _NL_REQUEST_SNAPSHOT_SCHEMA,
        "digest_profile": _NL_REQUEST_SNAPSHOT_DIGEST_PROFILE,
        "request": request_values,
        "normalized_llm_models": list(normalized_models),
    }
    if request_values != dict(raw_request):
        raise ValueError("nl_authorized_request_snapshot_not_canonical")
    if authorization_receipt is not None and authorization_receipt.get(
        "request_content_hash"
    ) != _nl_request_snapshot_content_hash(snapshot):
        raise ValueError("nl_authorized_request_snapshot_receipt_mismatch")
    expected_payload = {
        "request": request.request,
        "context": dict(request.context),
        "domain_hint": request.domain_hint,
        "data_source": (
            request.data_source.model_dump(mode="json") if request.data_source is not None else None
        ),
        "target_world_scope_profile_id": request.target_world_scope_profile_id,
        "max_iterations": request.max_iterations,
        "llm_models": list(normalized_models),
        "max_parallel_models": request.max_parallel_models,
        "run_budget_usd": request.run_budget_usd,
        "per_model_budget_usd": request.per_model_budget_usd,
        "checkpoint_policy": request.checkpoint_policy,
        "execution_plan_ref": request.execution_plan_ref,
        "execution_plan": request.execution_plan,
        "stop_criteria": request.stop_criteria,
        "governance_constraints": request.governance_constraints,
        "expected_outputs": request.expected_outputs,
    }
    _validate_nl_snapshot_payload_fields(payload, expected_payload)


def _validate_nl_snapshot_payload_fields(
    payload: Mapping[str, Any], expected_payload: Mapping[str, Any]
) -> None:
    for field_name, expected_value in expected_payload.items():
        observed_value = payload.get(field_name)
        if field_name == "checkpoint_policy" and isinstance(observed_value, Mapping):
            observed_value = dict(observed_value)
        if observed_value != expected_value:
            raise ValueError("nl_authorized_request_payload_mismatch")


class ControlJobAttemptPublicationMixin:
    """Own one control-job lifecycle facet without changing service entrypoints."""

    def _require_current_generation_job_attempt(self, job: ControlJobRecord) -> None:
        """Require the same live control-job lease immediately before Core writes."""
        current = self._control_store.current_execution_job_record()
        if (
            current.job_id != job.job_id
            or current.run_id != job.run_id
            or current.state != "running"
            or current.attempt != job.attempt
            or current.lease_owner != job.lease_owner
            or not isinstance(current.lease_owner, str)
            or not current.lease_owner.strip()
        ):
            raise ControlJobLeaseLostError("control_job_core_run_attempt_lease_lost")

    def _start_generation_run_context(
        self,
        *,
        job: ControlJobRecord,
        execution_scope: ControlJobExecutionScope,
    ) -> tuple[str, run.RunContext]:
        """Start one Core trace for this admitted live lease before compute begins."""
        control_run_id = str(job.run_id or "")
        tenant_id = execution_scope.tenant_id
        cell_id = execution_scope.cell_id
        if (
            execution_scope.status != "established"
            or not control_run_id
            or not tenant_id
            or not cell_id
        ):
            raise ValueError("control_job_core_run_identity_unbound")
        self._require_current_generation_job_attempt(job)
        core_run_id = derive_control_job_core_run_id(
            job_id=job.job_id,
            control_run_id=control_run_id,
            attempt=job.attempt,
        )
        run_dir = derive_core_run_dir(self._core_runs_root, core_run_id)
        if run_dir.exists():
            # Never append another RUN_STARTED to a previous attempt's trace.
            raise ValueError("control_job_core_run_attempt_already_exists")
        registry_bundle = registry.build_default_registry_bundle(self._artifact_store).bundle_ref
        context = run.RunContext.start(
            self._artifact_store,
            registry_bundle,
            producer=artifacts.ProducerInfo(
                component="polisyos.runtime.http.control.candidate_generation",
                version="1.0.0",
            ),
            run_dir=run_dir,
            run_id=core_run_id,
            tenant_id=tenant_id,
            cell_id=cell_id,
            access_scope=None,
        )
        # This is the explicit stable-control-job -> attempt-Core join. Do not
        # encode the stable run as parent_run_id: it is not a Core parent run.
        context.run_manifest.control_job_id = job.job_id
        context.run_manifest.execution_profile = job.effective_execution_profile
        return core_run_id, context

    def _finish_generation_run_context(
        self,
        *,
        job: ControlJobRecord,
        execution_scope: ControlJobExecutionScope,
        core_run_id: str,
        context: run.RunContext,
        outputs: list[ArtifactRef],
        status: str,
        errors: list[dict[str, object]] | None = None,
    ) -> ArtifactRef:
        """Finalize and strictly read back a supplied, pre-started attempt context."""
        control_run_id = str(job.run_id or "")
        if (
            core_run_id
            != derive_control_job_core_run_id(
                job_id=job.job_id,
                control_run_id=control_run_id,
                attempt=job.attempt,
            )
            or context.run_manifest.run_id != core_run_id
            or context.run_manifest.control_job_id != job.job_id
            or context.tenant_id != execution_scope.tenant_id
            or context.cell_id != execution_scope.cell_id
            or context.run_manifest.finished_at is not None
        ):
            raise ValueError("control_job_core_run_context_binding_mismatch")
        self._require_current_generation_job_attempt(job)
        existing_outputs = list(context.run_manifest.outputs)
        if existing_outputs != outputs[: len(existing_outputs)]:
            raise ValueError("control_job_core_run_output_prefix_mismatch")
        for output in outputs[len(existing_outputs) :]:
            context.add_output(output)
        manifest_ref = context.finalize(status=status, errors=errors)
        terminal = load_terminal_core_run_source(
            store=self._artifact_store,
            core_runs_root=self._core_runs_root,
            run_id=core_run_id,
        )
        if (
            terminal.manifest_ref != manifest_ref
            or terminal.manifest.status != status
            or terminal.manifest.control_job_id != job.job_id
            or terminal.manifest.outputs != outputs
            or terminal.manifest.tenant_id != execution_scope.tenant_id
            or terminal.manifest.cell_id != execution_scope.cell_id
        ):
            raise ValueError("control_job_core_run_terminal_readback_failed")
        return terminal.manifest_ref

    @staticmethod
    def _core_run_progress_fields(
        *, job: ControlJobRecord, core_run_id: str, manifest_ref: ArtifactRef
    ) -> dict[str, object]:
        """Return the attempt pointer that the same lease-fenced job write owns."""
        return {
            "core_run_id": core_run_id,
            "core_run_attempt": job.attempt,
            "core_manifest_artifact_ref": manifest_ref.model_dump(mode="json"),
            "manifest_ref": str(manifest_ref.artifact_id),
        }

    def _publish_generation_run(
        self,
        *,
        job: ControlJobRecord,
        payload: Mapping[str, Any],
        execution_scope: ControlJobExecutionScope,
        core_run_id: str,
        run_context: run.RunContext | None,
        compiled_run_ref: ArtifactRef | None = None,
        normative_disposition_ref: ArtifactRef | None = None,
        proposal_ref: ArtifactRef | None = None,
    ) -> ArtifactRef:
        """Finalize a pre-started Core attempt or read back its owned terminal."""
        del payload  # Identity and ownership come from the admitted job record.
        if compiled_run_ref is not None and proposal_ref is not None:
            raise ValueError("control_job_core_run_output_shape_invalid")
        if normative_disposition_ref is not None and compiled_run_ref is None:
            raise ValueError("control_job_core_run_output_shape_invalid")
        outputs = (
            [compiled_run_ref, normative_disposition_ref]
            if compiled_run_ref is not None and normative_disposition_ref is not None
            else [compiled_run_ref]
            if compiled_run_ref is not None
            else [proposal_ref]
            if proposal_ref is not None
            else []
        )
        if not outputs or any(not isinstance(ref, ArtifactRef) for ref in outputs):
            raise ValueError("control_job_core_run_exact_outputs_not_established")
        exact_outputs = cast("list[ArtifactRef]", outputs)
        if run_context is not None:
            return self._finish_generation_run_context(
                job=job,
                execution_scope=execution_scope,
                core_run_id=core_run_id,
                context=run_context,
                outputs=exact_outputs,
                status="ok",
            )
        terminal = load_completed_control_job_core_run_source(
            store=self._artifact_store,
            core_runs_root=self._core_runs_root,
            job=job,
            expected_control_run_id=str(job.run_id or ""),
            tenant_id=str(execution_scope.tenant_id or ""),
            cell_id=str(execution_scope.cell_id or ""),
        )
        if terminal.run_id != core_run_id or terminal.manifest.outputs != exact_outputs:
            raise ValueError("normative_generation_terminal_source_mismatch")
        return terminal.manifest_ref

    def _require_nl_job_execution_intent_binding(
        self,
        *,
        job: ControlJobRecord,
        admission: ControlJobExecutionAdmission,
        execution_scope: ControlJobExecutionScope,
        payload: Mapping[str, Any],
        capability_manifest_ref: str,
        capability_manifest: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Reconcile route intent against immutable admission and current custody."""
        failure_code = "nl_job_execution_intent_not_established"
        try:
            if (
                execution_scope.status != "established"
                or not capability_manifest_ref
                or not job.payload_ref
                or not job.run_id
            ):
                raise ValueError(failure_code)
            event = self._control_store.get_job_created_event_payload(job.job_id)
            outbox = self._control_store.get_job_created_outbox_event(job.job_id)
            payload_binding = payload.get(_EXECUTION_INTENT_BINDING_KEY)
            event_binding = event.get(_EXECUTION_INTENT_BINDING_KEY)
            actor = capability_manifest.get("actor")
            if not isinstance(actor, Mapping):
                raise ValueError(failure_code)
            expected_binding = _build_control_execution_intent_binding(
                payload,
                job_id=job.job_id,
                run_id=job.run_id,
                actor=actor,
            )
            if not isinstance(payload_binding, Mapping):
                raise ValueError(failure_code)
            binding = _ControlExecutionIntentBinding.model_validate_json(
                json.dumps(payload_binding, sort_keys=True)
            )
            binding_payload = binding.model_dump(mode="json", exclude={"intent_digest"})
            recomputed_digest = canonical_content_hash(
                to_canonical_bytes(binding_payload),
                prefix=True,
            )
            payload_tenant_id = payload.get("tenant_id")
            payload_cell_id = payload.get("cell_id")
            expected_outbox_payload = {
                "job_id": job.job_id,
                "job_kind": job.kind,
                "run_id": job.run_id,
                "pipeline_id": job.pipeline_id,
                "effective_execution_profile": job.effective_execution_profile,
                **event,
            }
            manifest_actor_roles = actor.get("roles")
            normalized_manifest_roles = tuple(
                sorted(role for role in manifest_actor_roles if isinstance(role, str))
                if isinstance(manifest_actor_roles, (list, tuple, set, frozenset))
                else ()
            )
            authorization_receipt = binding.authorization_receipt
            authorization_snapshot = (
                authorization_receipt.get("permission_snapshot")
                if isinstance(authorization_receipt, Mapping)
                else None
            )
            if (
                outbox is None
                or outbox.topic != "control.job.created"
                or outbox.event_key != f"{job.job_id}:job_created"
                or outbox.job_id != job.job_id
                or outbox.run_id != job.run_id
                or outbox.state not in {"pending", "published"}
                or outbox.payload != expected_outbox_payload
                or not isinstance(event_binding, Mapping)
                or event.get("job_id") != job.job_id
                or event.get("run_id") != job.run_id
                or event.get("job_kind") != "natural_language_run"
                or event.get("payload_ref") != job.payload_ref
                or event.get("capability_manifest_ref")
                != admission.admission_capability_manifest_ref
                or event.get("execution_scope") != self._execution_scope_payload(execution_scope)
                or event.get("intent_digest") != binding.intent_digest
                or payload.get("run_id") != job.run_id
                or event_binding != dict(payload_binding)
                or dict(payload_binding) != expected_binding
                or binding.intent_digest != recomputed_digest
                or capability_manifest.get("job_id") != job.job_id
                or capability_manifest.get("run_id") != job.run_id
                or capability_manifest.get("pipeline_id") != job.pipeline_id
                or capability_manifest.get("payload_ref") != job.payload_ref
                or binding.actor_subject != job.submitted_by
                or binding.actor_subject != execution_scope.actor_subject
                or binding.actor_subject != actor.get("subject")
                or binding.actor_authenticated is not actor.get("authenticated")
                or binding.actor_authenticated is not execution_scope.actor_authenticated
                or binding.actor_roles != normalized_manifest_roles
                or binding.actor_roles != execution_scope.actor_roles
                or binding.tenant_id != actor.get("tenant_id")
                or binding.cell_id != actor.get("cell_id")
                or binding.tenant_id != execution_scope.tenant_id
                or binding.cell_id != execution_scope.cell_id
                or payload_tenant_id != execution_scope.tenant_id
                or payload_cell_id != execution_scope.cell_id
                or binding.route_id != _NL_ROUTE_ID
                or binding.route_action != _NL_ROUTE_ACTION
                or binding.admission_surface != "served_route"
                or (
                    isinstance(authorization_receipt, Mapping)
                    and (
                        not isinstance(authorization_snapshot, Mapping)
                        or authorization_snapshot.get("subject") != binding.actor_subject
                        or authorization_snapshot.get("tenant_id") != binding.tenant_id
                        or tuple(authorization_snapshot.get("roles", ())) != binding.actor_roles
                    )
                )
                or not isinstance(authorization_receipt, Mapping)
            ):
                raise ValueError(failure_code)
            replayed_binding = binding.model_dump(mode="json")
            if (
                binding.admission_status == "established"
                and binding.intent_band == "simulate_only_attempt"
                and binding.canonical_mode == "simulate_only"
                and binding.actor_authenticated is True
                and isinstance(binding.tenant_id, str)
                and binding.tenant_id.strip()
                and isinstance(binding.cell_id, str)
                and binding.cell_id.strip()
            ):
                from polisyos.runtime.quality.cycle_substrate import (
                    _VERIFIED_NL_EXECUTION_OWNER_ISSUER,
                    VerifiedNLJobScope,
                )

                current_job = self._control_store.current_execution_job_record()
                if (
                    current_job.job_id != job.job_id
                    or current_job.run_id != job.run_id
                    or current_job.state != "running"
                    or not isinstance(current_job.lease_owner, str)
                    or not current_job.lease_owner.strip()
                    or current_job.lease_owner != job.lease_owner
                    or current_job.attempt != job.attempt
                ):
                    raise ValueError(failure_code)
                verified_scope = VerifiedNLJobScope.model_validate(
                    {
                        "job_id": current_job.job_id,
                        "run_id": str(current_job.run_id),
                        "tenant_id": binding.tenant_id,
                        "cell_id": binding.cell_id,
                        "worker_id": current_job.lease_owner,
                        "attempt": current_job.attempt,
                        "admission_status": binding.admission_status,
                        "intent_band": binding.intent_band,
                        "canonical_mode": binding.canonical_mode,
                        "route_id": binding.route_id,
                        "route_action": binding.route_action,
                        "admission_surface": binding.admission_surface,
                        "actor_subject": binding.actor_subject,
                        "actor_authenticated": True,
                        "intent_digest": binding.intent_digest,
                    }
                )
                object.__setattr__(
                    verified_scope,
                    "_issuer",
                    _VERIFIED_NL_EXECUTION_OWNER_ISSUER,
                )
                replayed_binding["_verified_nl_job_scope"] = verified_scope
            return replayed_binding
        except Exception as exc:
            if isinstance(exc, RuntimeError) and str(exc) == failure_code:
                raise
            raise RuntimeError(failure_code) from exc

    def _fail_control_job_attempt(
        self,
        *,
        job: ControlJobRecord,
        execution_scope: ControlJobExecutionScope,
        payload: dict[str, Any],
        capability_manifest_ref: str | None,
        core_run_id: str | None,
        core_run_context: run.RunContext | None,
        exc: Exception,
        logger: _CompatLogger,
    ) -> None:
        """Finalize any open Core attempt and persist the job's failure state."""
        failure_core_progress: dict[str, object] = {}
        failure_core_progress: dict[str, object] = {}
        if (
            core_run_context is not None
            and core_run_id is not None
            and core_run_context.run_manifest.finished_at is None
        ):
            try:
                failure_manifest_ref = self._finish_generation_run_context(
                    job=job,
                    execution_scope=execution_scope,
                    core_run_id=core_run_id,
                    context=core_run_context,
                    outputs=list(core_run_context.run_manifest.outputs),
                    status="error",
                    errors=[{"code": "control_job_generation_attempt_failed"}],
                )
                failure_core_progress = self._core_run_progress_fields(
                    job=job,
                    core_run_id=core_run_id,
                    manifest_ref=failure_manifest_ref,
                )
            except Exception as finalize_exc:
                logger.debug(
                    "Could not finalize failed Core attempt %s: %s",
                    core_run_id,
                    finalize_exc,
                )
        progress = (
            dict(exc.progress) if isinstance(exc, _WorkflowExecutionNonAuthorityError) else None
        )
        if failure_core_progress:
            progress = dict(progress or {})
            progress.update(
                {
                    "core_terminal_status": "error",
                    **failure_core_progress,
                }
            )
        self._emit_runtime_diagnostic_event(
            execution_scope=execution_scope,
            job_id=job.job_id,
            run_id=job.run_id,
            execution_profile=job.effective_execution_profile,
            phase="job_execution",
            event_type="polisyos.runtime.diagnostic.blocker.v1",
            state_before=job.state,
            state_after="failed",
            payload=payload,
            event_payload={
                "job_kind": job.kind,
                "error": str(exc)[:500],
                "projection_authority": "runtime_event_only",
            },
            blocking_status="blocking",
        )
        self._control_store.fail_job(
            job_id=job.job_id,
            capability_manifest_ref=capability_manifest_ref,
            error_message=str(exc),
            progress=progress,
        )
