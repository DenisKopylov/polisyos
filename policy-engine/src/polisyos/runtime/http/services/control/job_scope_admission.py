"""ControlJobScopeAdmissionMixin implementation for durable control-job lifecycle facets."""

from __future__ import annotations

import uuid
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal, cast

from pydantic import BaseModel, ConfigDict

from polisyos.core import artifacts, registry, run
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.canon import content_hash as canonical_content_hash
from polisyos.core.canon import to_canonical_bytes
from polisyos.core.contracts.control import DecisionValidityEventRequest, PolicyFlags
from polisyos.core.security import clear_tenant_context, tenant_scope
from polisyos.runtime.http.execution_policy import RuntimePrincipal
from polisyos.runtime.http.services.adapters.core_run import (
    derive_core_run_dir,
    load_terminal_core_run_source,
)
from polisyos.runtime.http.services.control.artifacts import _make_artifact_ref
from polisyos.runtime.http.services.control.evaluation_safety import (
    EvaluationSafetyAttemptAuthorities,
    EvaluationSafetyPersistenceContext,
    EvaluationSafetyReplayMaterial,
    PersistedEvaluationSafetyAttempt,
    PersistedEvaluationSafetyProjection,
)
from polisyos.runtime.http.services.control.response_shapes import _decision_validity_dedupe_payload
from polisyos.runtime.http.services.control.workspace_loop_transition import (
    _WorkflowExecutionNonAuthorityError,
)
from polisyos.runtime.quality.authority import GovernanceMetadata, SameInputClosure
from polisyos.runtime.quality.evaluation_safety import (
    EvaluationAttemptIntake,
    EvaluationExecutionContext,
)

from .job_attempt_publication import (
    _EVALUATION_SAFETY_ATTEMPT_KEY,
    _EVALUATION_SAFETY_EXECUTION_CONTEXT_KEY,
)

if TYPE_CHECKING:
    from ..control_plane_store import (
        ControlJobExecutionAdmission,
        ControlJobExecutionScope,
        ControlJobRecord,
    )


def _strict_json_value_equal(actual: object, expected: object) -> bool:
    """Compare decoded JSON values without Python's bool/int equality coercion."""
    if type(actual) is not type(expected):
        return False
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            return False
        if any(type(key) is not str for key in expected) or any(
            type(key) is not str for key in actual
        ):
            return False
        return actual.keys() == expected.keys() and all(
            _strict_json_value_equal(actual[key], expected[key]) for key in expected
        )
    if isinstance(expected, list):
        if not isinstance(actual, list):
            return False
        return len(actual) == len(expected) and all(
            _strict_json_value_equal(actual_item, expected_item)
            for actual_item, expected_item in zip(actual, expected, strict=True)
        )
    if expected is None or type(expected) in {bool, int, float, str}:
        return actual == expected
    return False


class _ControlJobExecutionScopeLimitation(BaseModel):
    """Candidate-only output limitation when a worker has no admitted owner."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["polisyos.runtime.control_execution_scope_limitation.v1"] = (
        "polisyos.runtime.control_execution_scope_limitation.v1"
    )
    status: Literal["not_established"] = "not_established"
    code: Literal["control_job_execution_scope_not_established"] = (
        "control_job_execution_scope_not_established"
    )
    candidate_work: Literal["unclaimed_only"] = "unclaimed_only"
    authority: Literal["withheld"] = "withheld"


_NL_JOB_OWNER_CONTEXT_KEYS = frozenset(
    {"tenant_id", "cell_id", "job_id", "run_id", "runtime_identity"}
)


@dataclass(frozen=True, slots=True)
class _ControlEvaluationSafetyResult:
    """One container-owned attempt result before any evaluator can run."""

    persisted: PersistedEvaluationSafetyAttempt
    projection: PersistedEvaluationSafetyProjection
    execution_context: EvaluationExecutionContext | None

    @property
    def blocked(self) -> bool:
        return self.persisted.decision.safety.status == "blocked"


def _limit_authority_boundary(limited: dict[str, Any]) -> None:
    boundary = limited.get("authority_boundary")
    if not isinstance(boundary, Mapping):
        return
    candidate_boundary = dict(boundary)
    candidate_boundary["decision_grade"] = "unsupported"
    known_limits = candidate_boundary.get("known_limits")
    known_limits = list(known_limits) if isinstance(known_limits, list) else []
    if "control_job_execution_scope_not_established" not in known_limits:
        known_limits.append("control_job_execution_scope_not_established")
    candidate_boundary["known_limits"] = known_limits
    limited["authority_boundary"] = candidate_boundary


def _limit_authority_surface_packet(limited: dict[str, Any]) -> None:
    boundary = limited.get("authority_boundary")
    packet = limited.get("authority_surface_packet")
    if not isinstance(boundary, Mapping) or not isinstance(packet, Mapping):
        return
    candidate_packet = dict(packet)
    candidate_packet["authority_result"] = "candidate_only"
    candidate_packet["boundary"] = boundary
    surfaces = packet.get("surfaces")
    if isinstance(surfaces, Mapping):
        candidate_surfaces = {name: _limit_surface(surface) for name, surface in surfaces.items()}
        candidate_packet["surfaces"] = candidate_surfaces
        limited["surface_authority"] = candidate_surfaces
        limited["public_packet"] = {
            "authority_boundary": boundary,
            "projection": candidate_surfaces.get("public_packet"),
        }
        for progress_key, surface_key in (
            ("artifact_projection", "artifact"),
            ("lineage_projection", "lineage"),
            ("export_projection", "export"),
        ):
            if surface_key in candidate_surfaces:
                limited[progress_key] = candidate_surfaces[surface_key]
    limited["authority_surface_packet"] = candidate_packet


def _limit_surface(surface: object) -> object:
    if not isinstance(surface, Mapping):
        return surface
    return {
        **dict(surface),
        "status": "candidate_only",
        "authority_result": "candidate_only",
        "decision_grade": "unsupported",
        "reason": "control_job_execution_scope_not_established",
    }


def _limit_quality_scorecard(limited: dict[str, Any], limitation: dict[str, Any]) -> None:
    scorecard = limited.get("quality_scorecard")
    if not isinstance(scorecard, Mapping):
        return
    limited_scorecard = dict(scorecard)
    limited_scorecard["approval_ready"] = False
    limited_scorecard["approval_state"] = "candidate_only"
    limited_scorecard["execution_scope_limitation"] = limitation
    for field_name in ("authority_boundary", "authority_surface_packet"):
        value = limited.get(field_name)
        if isinstance(value, Mapping):
            limited_scorecard[field_name] = value
    limited["quality_scorecard"] = limited_scorecard


class ControlJobScopeAdmissionMixin:
    """Own one control-job lifecycle facet without changing service entrypoints."""

    @staticmethod
    def _derive_decision_validity_dedupe_key(
        request: DecisionValidityEventRequest,
        *,
        dependency_keys: list[str],
    ) -> str:
        return uuid.uuid5(
            uuid.NAMESPACE_URL,
            _decision_validity_dedupe_payload(request, dependency_keys=dependency_keys),
        ).hex

    def _load_payload_ref(self, payload_ref: str, *, kind: str) -> dict[str, Any]:
        from polisyos.core.artifacts import artifact_manifest_profile_sha256
        from polisyos.core.artifacts.manifest import ArtifactRef
        from polisyos.core.canon import from_canonical_bytes

        declared_ref = _make_artifact_ref(payload_ref, kind=kind)
        manifest = self._artifact_store.get_manifest(declared_ref)
        if manifest.kind != kind or manifest.media_type != "application/json":
            raise RuntimeError("Control job payload manifest does not match its owner kind")
        selected_ref = ArtifactRef(
            artifact_id=declared_ref.artifact_id,
            kind=manifest.kind,
            media_type=manifest.media_type,
            manifest_profile_sha256=artifact_manifest_profile_sha256(manifest),
        )
        verification = self._artifact_store.verify(selected_ref)
        if not verification.ok:
            raise RuntimeError("Control job payload failed selected-profile verification")
        payload = from_canonical_bytes(self._artifact_store.get_bytes(selected_ref))
        if not isinstance(payload, dict):
            raise RuntimeError("Control job payload must decode to a JSON object")
        return dict(payload)

    def _refresh_capability_manifest(
        self,
        *,
        job: ControlJobRecord,
        execution_scope: ControlJobExecutionScope,
        observed_fallbacks: list[str] | None = None,
    ) -> str:
        """Refresh the current manifest from persisted worker admission only."""
        if execution_scope.status == "established":
            tenant_id = execution_scope.tenant_id
            cell_id = execution_scope.cell_id
            subject = execution_scope.actor_subject
            authenticated = execution_scope.actor_authenticated
            roles = frozenset(execution_scope.actor_roles)
            if (
                not tenant_id
                or not cell_id
                or not subject
                or not authenticated
                or subject != job.submitted_by
            ):
                raise RuntimeError("control_job_execution_scope_incomplete")
            principal = RuntimePrincipal(
                subject=subject,
                tenant_id=tenant_id,
                cell_id=cell_id,
                roles=roles,
                authenticated=True,
            )
        else:
            # Unknown legacy scope may still execute unclaimed candidate work. A
            # refresh must not promote payload or manifest identity into a principal.
            principal = RuntimePrincipal()

        policy = self._policy_resolver.resolve(
            requested_profile=job.requested_execution_profile,
            policy_flags=PolicyFlags.model_validate(job.policy_flags),
            principal=principal,
        )
        if (
            policy.effective_profile != job.effective_execution_profile
            or policy.requested_profile != job.requested_execution_profile
            or policy.policy_flags.model_dump(mode="json") != job.policy_flags
        ):
            raise RuntimeError("control_job_capability_manifest_policy_mismatch")
        manifest_ref = self._persist_capability_manifest(
            policy=policy,
            job_id=job.job_id,
            run_id=job.run_id,
            pipeline_id=job.pipeline_id,
            payload_ref=job.payload_ref,
            observed_fallbacks=observed_fallbacks,
        )
        self._control_store.update_manifest_ref(
            job_id=job.job_id,
            capability_manifest_ref=manifest_ref,
        )
        return manifest_ref

    def _validate_capability_manifest_for_scope(
        self,
        *,
        manifest_ref: str,
        job: ControlJobRecord,
        execution_scope: ControlJobExecutionScope,
    ) -> dict[str, Any]:
        """Bind manifest bytes to the canonical leased row and admitted actor."""
        manifest = self._load_payload_ref(
            manifest_ref,
            kind="runtime.capability_manifest",
        )
        expected_binding: dict[str, Any] = {
            "job_id": job.job_id,
            "run_id": job.run_id,
            "pipeline_id": job.pipeline_id,
            "payload_ref": job.payload_ref,
            "requested_execution_profile": job.requested_execution_profile,
            "effective_execution_profile": job.effective_execution_profile,
            "policy_flags": job.policy_flags,
        }
        if not isinstance(manifest, Mapping) or any(
            key not in manifest for key in expected_binding
        ):
            raise RuntimeError("control_job_capability_manifest_binding_mismatch")
        actor = manifest.get("actor")
        observed_binding = {key: manifest[key] for key in expected_binding}
        if not _strict_json_value_equal(observed_binding, expected_binding):
            raise RuntimeError("control_job_capability_manifest_binding_mismatch")
        if execution_scope.status == "established":
            expected_actor = {
                "subject": execution_scope.actor_subject,
                "tenant_id": execution_scope.tenant_id,
                "cell_id": execution_scope.cell_id,
                "roles": list(execution_scope.actor_roles),
                "authenticated": True,
            }
            if not _strict_json_value_equal(actor, expected_actor):
                raise RuntimeError("control_job_capability_manifest_actor_mismatch")
        else:
            anonymous_actor = {
                "subject": "anonymous",
                "tenant_id": None,
                "cell_id": None,
                "roles": [],
                "authenticated": False,
            }
            if not _strict_json_value_equal(actor, anonymous_actor):
                raise RuntimeError("control_job_unknown_scope_manifest_not_anonymous")
        return dict(manifest)

    def _resolve_capability_manifest_for_execution(
        self,
        *,
        job: ControlJobRecord,
        admission: ControlJobExecutionAdmission,
        execution_scope: ControlJobExecutionScope,
    ) -> tuple[str, dict[str, Any]]:
        """Resolve a current manifest without treating its mutable pointer as identity."""
        if execution_scope.status == "established" and job.capability_manifest_ref:
            manifest_ref = job.capability_manifest_ref
        else:
            manifest_ref = self._refresh_capability_manifest(
                job=job,
                execution_scope=execution_scope,
            )
        manifest = self._validate_capability_manifest_for_scope(
            manifest_ref=manifest_ref,
            job=job,
            execution_scope=execution_scope,
        )
        # The event pointer is a historical admission snapshot. It is checked by
        # the NL binding consumer but never forced to equal a fenced current pointer.
        _ = admission.manifest_pointer_state
        return manifest_ref, manifest

    @staticmethod
    def _limit_workflow_progress_for_execution_scope(
        progress: dict[str, Any],
        execution_scope: ControlJobExecutionScope,
    ) -> dict[str, Any]:
        """Carry unknown owner scope through the served result as a candidate limit."""
        if execution_scope.status == "established":
            return progress

        limitation = _ControlJobExecutionScopeLimitation().model_dump(mode="json")
        limited = dict(progress)
        limited["execution_scope_status"] = "not_established"
        limited["execution_scope_limitation"] = limitation
        if limited.get("authority_result") == "verifier_stamped":
            limited["authority_result"] = "candidate_only"
        if limited.get("authority_result") is not None:
            limited["execution_band"] = "candidate"

        _limit_authority_boundary(limited)
        _limit_authority_surface_packet(limited)
        _limit_quality_scorecard(limited, limitation)

        approval_projection = limited.get("approval_projection")
        reasons = (
            list(approval_projection.get("reasons") or [])
            if isinstance(approval_projection, Mapping)
            else []
        )
        if "control_job_execution_scope_not_established" not in reasons:
            reasons.append("control_job_execution_scope_not_established")
        limited["approval_projection"] = {
            "state": "candidate_only",
            "eligible": False,
            "reasons": reasons,
        }
        return limited

    @contextmanager
    def _install_execution_scope(self, execution_scope: ControlJobExecutionScope) -> Iterator[None]:
        """Clear request identity, then install only persisted tenant/cell custody."""
        with clear_tenant_context():
            if execution_scope.status == "established":
                if not execution_scope.tenant_id or not execution_scope.cell_id:
                    raise RuntimeError("control_job_execution_scope_incomplete")
                with tenant_scope(
                    None,
                    tenant_id=execution_scope.tenant_id,
                    cell_id=execution_scope.cell_id,
                ):
                    yield
                return
            yield

    @staticmethod
    def _payload_for_execution_scope(
        payload: Mapping[str, Any],
        *,
        job: ControlJobRecord,
        execution_scope: ControlJobExecutionScope,
    ) -> dict[str, Any]:
        """Reject stable mismatches and strip caller owner claims from candidate inputs."""
        result = dict(payload)
        if result.get("run_id") is not None and result.get("run_id") != job.run_id:
            raise RuntimeError("control_job_payload_run_id_mismatch")
        result["job_id"] = job.job_id
        result["run_id"] = job.run_id
        result.pop("runtime_identity", None)
        if execution_scope.status == "established":
            if (
                result.get("tenant_id") != execution_scope.tenant_id
                or result.get("cell_id") != execution_scope.cell_id
            ):
                raise RuntimeError("control_job_payload_owner_scope_mismatch")
            result["tenant_id"] = execution_scope.tenant_id
            result["cell_id"] = execution_scope.cell_id
        else:
            result.pop("tenant_id", None)
            result.pop("cell_id", None)

        raw_state_payload = result.get("state_payload")
        if isinstance(raw_state_payload, Mapping):
            state_payload = dict(raw_state_payload)
            for key in _NL_JOB_OWNER_CONTEXT_KEYS:
                state_payload.pop(key, None)
            raw_params = state_payload.get("params")
            if isinstance(raw_params, Mapping):
                state_payload["params"] = {
                    key: value
                    for key, value in raw_params.items()
                    if key not in _NL_JOB_OWNER_CONTEXT_KEYS
                }
            state_payload["job_id"] = job.job_id
            state_payload["run_id"] = job.run_id
            if execution_scope.status == "established":
                state_payload["tenant_id"] = execution_scope.tenant_id
                state_payload["cell_id"] = execution_scope.cell_id
            result["state_payload"] = state_payload
        return result

    def _hydrate_state_payload(
        self,
        payload: dict[str, Any],
        *,
        job: ControlJobRecord,
        capability_manifest_ref: str,
    ) -> dict[str, Any]:
        state_payload = dict(payload)
        state_payload["control_job_id"] = job.job_id
        state_payload["execution_profile"] = job.effective_execution_profile
        state_payload["capability_manifest_ref"] = _make_artifact_ref(
            capability_manifest_ref,
            kind="runtime.capability_manifest",
        )
        return state_payload

    def _evaluation_safety_persistence_context(
        self,
        *,
        intake: EvaluationAttemptIntake,
        job: ControlJobRecord,
        payload: Mapping[str, Any],
        execution_scope: ControlJobExecutionScope,
    ) -> EvaluationSafetyPersistenceContext:
        trace = self._job_trace_context(job_id=job.job_id, payload=payload)
        tenant_id = execution_scope.tenant_id
        cell_id = execution_scope.cell_id
        if execution_scope.status != "established" or tenant_id is None or cell_id is None:
            code = "evaluation_safety_tenant_scope_not_established"
            raise _WorkflowExecutionNonAuthorityError(
                code,
                progress={
                    "state": "failed",
                    "runtime_state": "blocked",
                    "phase": "evaluation_safety",
                    "status": "not_established",
                    "execution_band": "authority",
                    "limitation_code": code,
                    "authority_path": "evaluation_safety",
                    "authority_result": "blocked",
                    "eval_safety_blocker_codes": [code],
                    "runtime_diagnostic_event_status": "not_established",
                    "runtime_diagnostic_event_limitation_code": (
                        "diagnostic_event_owner_scope_not_established"
                    ),
                },
            )
        run_id = str(job.run_id or "run-unknown")
        input_refs = tuple(ref.artifact_id for ref in intake.evaluation_input_refs)
        closure_payload = {
            "attempt_id": intake.attempt_id,
            "run_id": run_id,
            "job_id": job.job_id,
            "tenant_id": tenant_id,
            "cell_id": cell_id,
            "evidence_input_refs": input_refs,
        }
        mode_ref = canonical_content_hash(
            to_canonical_bytes(intake.mode_resolution.model_dump(mode="json")),
            prefix=True,
        )
        return EvaluationSafetyPersistenceContext(
            tenant_id=tenant_id,
            cell_id=cell_id,
            run_id=run_id,
            job_id=job.job_id,
            trace_id=str(trace["trace_id"]),
            span_id=str(trace["span_id"]),
            parent_span_id=(str(trace["parent_span_id"]) if trace.get("parent_span_id") else None),
            requested_execution_profile=(
                job.requested_execution_profile or job.effective_execution_profile
            ),
            effective_execution_profile=job.effective_execution_profile,
            phase="evaluation_safety",
            generated_at=intake.requested_at,
            as_of_time=intake.requested_at,
            same_input_closure=SameInputClosure(
                closure_id=f"eval-safety:{intake.attempt_id}",
                status="closed",
                run_id=run_id,
                job_id=job.job_id,
                tenant_id=tenant_id,
                cell_id=cell_id,
                effective_mode_ref=mode_ref,
                evidence_input_refs=input_refs,
                closure_sha256=canonical_content_hash(to_canonical_bytes(closure_payload)),
            ),
            effective_mode_ref=mode_ref,
            governance=GovernanceMetadata(
                classification="internal",
                authority_boundary="runtime",
                pii="none",
                retention_policy="runtime-quality-90d",
                review_status="runtime_verified",
                override_policy="no_override",
                approval_policy="runtime_owner_required",
            ),
        )

    def _admit_evaluation_safety_attempt(
        self,
        *,
        extension_payload: Mapping[str, Any],
        job: ControlJobRecord,
        payload: Mapping[str, Any],
        execution_scope: ControlJobExecutionScope,
    ) -> _ControlEvaluationSafetyResult | None:
        if _EVALUATION_SAFETY_ATTEMPT_KEY not in extension_payload:
            return None
        intake = EvaluationAttemptIntake.model_validate(
            extension_payload[_EVALUATION_SAFETY_ATTEMPT_KEY]
        )
        persistence_context = self._evaluation_safety_persistence_context(
            intake=intake,
            job=job,
            payload=payload,
            execution_scope=execution_scope,
        )
        authorities = EvaluationSafetyAttemptAuthorities(
            mode_basis_ref=None,
            mode_basis=None,
            pack_ref=None,
            pack=None,
            semantic_facet_denominator_receipt_ref=None,
            facet_registry=None,
            facet_denominator=None,
            authority_resolver=self._evaluation_safety_authority_resolver,
            appointment_resolver=self._evaluation_safety_appointment_resolver,
            verifier_registry=self._evaluation_safety_verifier_registry,
            evidence=(),
            classification_offer=None,
            classification=None,
            certificate_issue_cause_ref=None,
        )
        persisted = self._evaluation_safety_persistence_service.compose_and_persist_attempt(
            intake=intake,
            authorities=authorities,
            context=persistence_context,
            evaluated_at=intake.requested_at,
            promotion_sources=self._evaluation_safety_promotion_sources,
        )
        if persisted.promotion_source_resolution_ref is not None:
            self._emit_runtime_diagnostic_event(
                job_id=job.job_id,
                run_id=job.run_id,
                execution_profile=job.effective_execution_profile,
                phase="evaluation_safety",
                event_type="polisyos.runtime.diagnostic.producer_execution.v1",
                payload=payload,
                execution_scope=execution_scope,
                event_payload={
                    "producer": "promotion_classification_source_resolution",
                    "source_resolution_ref": persisted.promotion_source_resolution_ref,
                    "projection_authority": "informational_projection_only",
                },
                artifact_refs=[persisted.promotion_source_resolution_ref],
            )
        evidence_key = (
            persisted.owner_evidence.decision_ref.artifact_id,
            persisted.owner_evidence.decision_ref.content_hash,
        )
        self._evaluation_safety_decision_evidence[evidence_key] = persisted.owner_evidence
        reduction = self._evaluation_safety_persistence_service.reduce_decisions(
            evidence=tuple(self._evaluation_safety_decision_evidence.values())
        )
        projection = self._evaluation_safety_persistence_service.persist_metrics_projection(
            reduction=reduction,
            context=persistence_context,
            generated_at=intake.requested_at,
        )
        safety = persisted.decision.safety
        execution_context: EvaluationExecutionContext | None = None
        if safety.status == "passed" and safety.evaluation_mode is not None:
            revision_head = (
                persisted.revision_nodes[-1].revision_ref if persisted.revision_nodes else None
            )
            execution_context = EvaluationExecutionContext(
                intake_ref=persisted.intake_ref,
                evaluator_owner_id=intake.evaluator_owner_id,
                design_problem_ref=intake.design_problem_ref,
                evaluation_mode=safety.evaluation_mode,
                candidate_ref=intake.candidate_ref,
                world_model_record_ref=intake.world_model_record_ref,
                target_population_scope_ref=intake.target_population_scope_ref,
                rule_version=(
                    intake.requested_rule_version or "policyos.runtime.eval-safety.simulate-only.v1"
                ),
                intended_start_at=intake.intended_start_at,
                evaluation_input_refs=intake.evaluation_input_refs,
                evaluation_input_provenance=intake.evaluation_input_provenance,
                eval_safety_certificate_ref=persisted.certificate_ref,
                eval_safety_revision_head_ref=revision_head,
            )
            replay_material = EvaluationSafetyReplayMaterial(
                intake_ref=persisted.intake_ref,
                request_ref=persisted.request_ref,
                mode_basis_ref=None,
                mode_basis=None,
                pack_ref=None,
                pack=None,
                facet_registry=None,
                facet_denominator=None,
                authority_resolver=self._evaluation_safety_authority_resolver,
                appointment_resolver=self._evaluation_safety_appointment_resolver,
                verifier_registry=self._evaluation_safety_verifier_registry,
                evidence=(),
                classification=None,
                decision_ref=persisted.decision_ref,
                certificate_ref=persisted.certificate_ref,
                revision_nodes=persisted.revision_nodes,
                decision_evaluated_at=safety.evaluated_at,
                revalidated_at=safety.evaluated_at,
            )
            self._evaluation_safety_state_resolver.register(
                context=execution_context,
                material=replay_material,
            )
        return _ControlEvaluationSafetyResult(
            persisted=persisted,
            projection=projection,
            execution_context=execution_context,
        )

    def _blocked_evaluation_safety_progress(
        self,
        *,
        result: _ControlEvaluationSafetyResult,
        job: ControlJobRecord,
        payload: Mapping[str, Any],
        execution_scope: ControlJobExecutionScope,
        core_run_id: str | None = None,
        core_run_context: run.RunContext | None = None,
    ) -> dict[str, Any]:
        run_id = str(job.run_id or "run-unknown")
        run_dir = derive_core_run_dir(self._core_runs_root, run_id)
        projection_ref = ArtifactRef(
            artifact_id=artifacts.ArtifactID.model_validate(
                result.projection.projection_ref.artifact_id
            ),
            kind=result.projection.projection_ref.artifact_type,
            media_type="application/json",
        )
        blocker_codes = list(result.persisted.decision.safety.blocker_codes)
        core_progress: dict[str, object] = {}
        if core_run_context is not None:
            if core_run_id is None:
                raise ValueError("evaluation_safety_core_attempt_identity_missing")
            manifest_artifact_ref = self._finish_generation_run_context(
                job=job,
                execution_scope=execution_scope,
                core_run_id=core_run_id,
                context=core_run_context,
                outputs=[projection_ref],
                status="error",
                errors=[
                    {
                        "code": "evaluation_safety_attempt_blocked",
                        "blocker_codes": blocker_codes,
                    }
                ],
            )
            manifest_ref = manifest_artifact_ref
            core_progress = self._core_run_progress_fields(
                job=job,
                core_run_id=core_run_id,
                manifest_ref=manifest_artifact_ref,
            )
        elif run_dir.exists():
            terminal_source = load_terminal_core_run_source(
                store=self._artifact_store,
                core_runs_root=self._core_runs_root,
                run_id=run_id,
            )
            if terminal_source.manifest.status != "error" or terminal_source.manifest.outputs != [
                projection_ref
            ]:
                raise ValueError("evaluation_safety_terminal_manifest_mismatch")
            manifest_ref = terminal_source.manifest_ref
        else:
            registry_bundle = registry.build_default_registry_bundle(
                self._artifact_store
            ).bundle_ref
            run_context = run.RunContext.start(
                self._artifact_store,
                registry_bundle,
                producer=artifacts.ProducerInfo(
                    component="polisyos.runtime.http.control.evaluation_safety",
                    version="1.0.0",
                ),
                run_dir=run_dir,
                run_id=run_id,
                tenant_id=execution_scope.tenant_id,
                cell_id=execution_scope.cell_id,
                access_scope=None,
            )
            run_context.add_output(projection_ref)
            manifest_ref = run_context.finalize(
                status="error",
                errors=[
                    {
                        "code": "evaluation_safety_attempt_blocked",
                        "blocker_codes": blocker_codes,
                    }
                ],
            )
        projection = result.projection.projection
        progress = dict(job.progress)
        artifacts_index = progress.get("artifacts_index")
        artifacts_index = dict(artifacts_index) if isinstance(artifacts_index, Mapping) else {}
        artifacts_index.update(
            {
                "eval_safety_projection_ref": result.projection.projection_ref.artifact_id,
                "eval_safety_promotion_source_resolution_ref": (
                    result.persisted.promotion_source_resolution_ref
                ),
                "manifest_ref": str(manifest_ref.artifact_id),
            }
        )
        progress.update(
            {
                "state": "failed",
                "runtime_state": "blocked",
                "phase": "evaluation_safety",
                "run_id": run_id,
                "authority_path": "evaluation_safety",
                "authority_result": "blocked",
                "eval_safety_projection_ref": (result.projection.projection_ref.artifact_id),
                "eval_safety_disposition": result.persisted.decision.safety.status,
                "eval_safety_promotion_source_resolution_ref": (
                    result.persisted.promotion_source_resolution_ref
                ),
                "eval_safety_blocker_codes": blocker_codes,
                "eval_safety_counters": {
                    "unsafe_attempt_blocked_count": (projection.unsafe_attempt_blocked_count),
                    "near_miss_count": projection.near_miss_count,
                    "near_miss_classification_status": (projection.near_miss_classification_status),
                    "reconciliation_status": projection.reconciliation_status,
                },
                "manifest_ref": str(manifest_ref.artifact_id),
                **core_progress,
                "artifacts_index": artifacts_index,
            }
        )
        return progress

    def _finish_blocked_evaluation_safety_attempt(
        self,
        *,
        result: _ControlEvaluationSafetyResult,
        job: ControlJobRecord,
        payload: Mapping[str, Any],
        execution_scope: ControlJobExecutionScope,
        capability_manifest_ref: str,
        core_run_id: str | None = None,
        core_run_context: run.RunContext | None = None,
    ) -> None:
        progress = self._blocked_evaluation_safety_progress(
            result=result,
            job=job,
            payload=payload,
            execution_scope=execution_scope,
            core_run_id=core_run_id,
            core_run_context=core_run_context,
        )
        self._control_store.fail_job(
            job_id=job.job_id,
            error_message="evaluation_safety_attempt_blocked",
            capability_manifest_ref=capability_manifest_ref,
            progress=progress,
        )
        self._emit_runtime_diagnostic_event(
            job_id=job.job_id,
            run_id=job.run_id,
            execution_profile=job.effective_execution_profile,
            phase="evaluation_safety",
            event_type="polisyos.runtime.diagnostic.blocker.v1",
            state_before="running",
            state_after="failed",
            payload=payload,
            execution_scope=execution_scope,
            event_payload={
                "job_kind": job.kind,
                "blocker_codes": progress["eval_safety_blocker_codes"],
                "projection_authority": "informational_projection_only",
            },
            artifact_refs=[
                progress["eval_safety_projection_ref"],
                progress["manifest_ref"],
            ],
            blocking_status="blocking",
        )

    def _process_workflow_control_job(
        self,
        *,
        job: ControlJobRecord,
        payload: dict[str, Any],
        execution_scope: ControlJobExecutionScope,
        capability_manifest_ref: str,
    ) -> None:
        """Run, scope-limit, and complete one admitted workflow job."""
        state_payload = self._hydrate_state_payload(
            payload["state_payload"],
            job=job,
            capability_manifest_ref=capability_manifest_ref,
        )
        evaluation_safety = self._admit_evaluation_safety_attempt(
            extension_payload=cast("Mapping[str, Any]", state_payload.get("params") or {}),
            job=job,
            payload=payload,
            execution_scope=execution_scope,
        )
        if evaluation_safety is not None and evaluation_safety.blocked:
            self._finish_blocked_evaluation_safety_attempt(
                result=evaluation_safety,
                job=job,
                payload=payload,
                execution_scope=execution_scope,
                capability_manifest_ref=capability_manifest_ref,
            )
            return
        if evaluation_safety is not None and evaluation_safety.execution_context is not None:
            state_payload[_EVALUATION_SAFETY_EXECUTION_CONTEXT_KEY] = (
                evaluation_safety.execution_context.model_dump(mode="json")
            )
        progress = self._execute_workflow_control_transition(
            state_payload,
            payload["checkpoint_policy"],
            job=job,
            endpoint="/api/v1/control/runs",
            execution_scope_status=execution_scope.status,
            http_request_id=str(
                (payload.get("_telemetry") or {}).get("request_id") or f"control-job:{job.job_id}"
            ),
        )
        progress = self._limit_workflow_progress_for_execution_scope(
            progress,
            execution_scope,
        )
        self._control_store.complete_job(
            job_id=job.job_id,
            run_id=job.run_id,
            capability_manifest_ref=capability_manifest_ref,
            progress=progress,
        )
        terminal_record = self._control_store.get_job(job.job_id)
        terminal_state = terminal_record.state if terminal_record is not None else "completed"
        if terminal_state == "completed":
            self._finalize_workspace_loop_run_proof(
                job_id=job.job_id,
                endpoint="/api/v1/control/runs",
            )
        self._emit_runtime_diagnostic_event(
            execution_scope=execution_scope,
            job_id=job.job_id,
            run_id=job.run_id,
            execution_profile=job.effective_execution_profile,
            phase="job_execution",
            event_type="polisyos.runtime.diagnostic.phase_transition.v1",
            state_before="running",
            state_after=terminal_state,
            payload=payload,
            event_payload={"job_kind": job.kind},
            blocking_status="blocking" if terminal_state == "failed" else None,
        )
        return

    @staticmethod
    def _require_control_job_payload_ref(job: ControlJobRecord) -> str:
        """Return the durable payload pointer or preserve its established error."""
        if not job.payload_ref:
            raise RuntimeError("control job payload ref is missing")
        return job.payload_ref

    def _bind_control_job_execution_intent(
        self,
        *,
        job: ControlJobRecord,
        admission: ControlJobExecutionAdmission,
        execution_scope: ControlJobExecutionScope,
        payload: dict[str, Any],
        capability_manifest_ref: str,
        capability_manifest: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Validate NL execution intent only for the NL job kind."""
        if job.kind != "natural_language_run":
            return None
        binding = self._require_nl_job_execution_intent_binding(
            job=job,
            admission=admission,
            execution_scope=execution_scope,
            payload=payload,
            capability_manifest_ref=capability_manifest_ref,
            capability_manifest=capability_manifest,
        )
        if (
            binding["admission_status"] != "established"
            or binding["intent_band"] == "not_established"
        ):
            raise RuntimeError("nl_job_execution_intent_not_established")
        return binding
