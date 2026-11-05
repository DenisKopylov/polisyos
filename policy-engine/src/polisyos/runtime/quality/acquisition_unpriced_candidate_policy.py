"""Server-selected limits for candidate research with unestablished USD cost.

This record binds an exact pre-route source to an existing one-call Fabric
authorization and an existing run-bound N5 invocation quota. It does not
admit data, grant a lease, reserve dollars, or authorize publication. The
route owner must independently replay the selected planner and candidate cycle.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.core import artifacts, canon
from polisyos.fabric import data_plane
from polisyos.runtime.quality.agent_action_authority import (
    agent_action_content_hash,
    write_runtime_authority_artifact,
)
from polisyos.runtime.quality.authority import GovernanceMetadata
from polisyos.runtime.quality.authority_reconciliation import reconcile_authority_ref
from polisyos.scientist.orchestration.engine import BudgetLedgerInvocationProfile

if TYPE_CHECKING:
    from polisyos.core.artifacts import ArtifactRef, CoreJSONArtifactStore
    from polisyos.runtime.http.services.control.run_lifecycle import (
        ControlPlaneService,
        OriginalRunBudgetScopeEvidence,
    )
    from polisyos.runtime.quality.acquisition_route_loop import (
        VerifiedCandidateExperimentOrigin,
    )
    from polisyos.runtime.quality.event_log import RuntimeDiagnosticEventLog
    from polisyos.scientist.orchestration.engine import (
        BudgetInvocationCapacityObservation,
        BudgetState,
        ProducerBudgetObservation,
        ProducerBudgetObserver,
    )

_HASH = r"^sha256:[0-9a-f]{64}$"
POLICY_KIND = "runtime_quality.candidate_unpriced_acquisition_policy"
POLICY_SCHEMA = "polisyos.runtime.CandidateUnpricedAcquisitionPolicy"
POLICY_PRODUCER = "polisyos.runtime.acquisition_candidate_unpriced_policy"
POLICY_EVENT = "polisyos.runtime.acquisition.candidate_unpriced_policy.v1"
_REQUIRED_LIMITATIONS = frozenset(
    {
        "acquisition_monetary_cost_not_established",
        "n5_monetary_cost_not_established",
        "per_call_usd_reservation_not_established",
        "candidate_only_no_publication_authority",
    }
)
_POLICY_V1 = "polisyos.runtime.candidate_unpriced_acquisition_policy.v1"
_POLICY_V2 = "polisyos.runtime.candidate_unpriced_acquisition_policy.v2"
_EXPERIMENT_FIELDS = frozenset(
    {
        "experiment_intent",
        "information_value",
        "source_payload_ref",
        "request_content_hash",
        "original_metered_budget_usd",
        "configured_template",
    }
)


def _selected_ref(ref: object, kind: str) -> bool:
    return (
        isinstance(ref, artifacts.ArtifactRef)
        and set(type(ref).model_fields) == set(artifacts.ArtifactRef.model_fields)
        and set(vars(ref)) == set(artifacts.ArtifactRef.model_fields)
        and not ref.__pydantic_extra__
        and ref.kind == kind
        and ref.media_type == "application/json"
        and ref.manifest_profile_sha256 is not None
    )


class CandidateUnpricedPolicyScope(BaseModel):
    """The exact selected source occurrence, before its route ID exists."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    tenant_id: str = Field(min_length=1)
    cell_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    source_job_id: str = Field(min_length=1)
    design_problem_ref: str = Field(pattern=_HASH)
    design_problem_basis_ref: str = Field(pattern=_HASH)
    source_cycle_index: int = Field(ge=0)
    candidate_id: str = Field(min_length=1)
    candidate_content_hash: str = Field(pattern=_HASH)
    requirement_id: str = Field(min_length=1)
    compiled_requirement_ref: str = Field(min_length=1)
    candidate_digest: str = Field(pattern=_HASH)
    planner_report_hash: str = Field(pattern=_HASH)
    compiled_ref: artifacts.ArtifactRef
    planner_report_ref: artifacts.ArtifactRef
    compiler_report_ref: artifacts.ArtifactRef
    configured_port_source_ref: artifacts.ArtifactRef

    @model_validator(mode="after")
    def _require_selected_sources(self) -> CandidateUnpricedPolicyScope:
        refs = (
            (self.compiled_ref, "runtime.compiled_recursive_generation_cycle"),
            (self.planner_report_ref, "runtime.acquisition_planner_report"),
            (self.compiler_report_ref, "runtime.data_requirement_compilation_report"),
            (
                self.configured_port_source_ref,
                "runtime.quality.n7_configured_candidate_port_source",
            ),
        )
        if any(not _selected_ref(ref, kind) for ref, kind in refs):
            raise ValueError("candidate_unpriced_policy_selected_source_invalid")
        return self


class CandidateUnpricedExperimentPolicyTemplate(BaseModel):
    """Server-selected limits for one independently authorized source attempt.

    The template is not a source-rights decision or an action permit. Its
    registry and provision identities must be reopened through the real
    authority, and the selected N5 allocation remains a separate owner.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["polisyos.runtime.candidate_unpriced_policy_template.v1"] = (
        "polisyos.runtime.candidate_unpriced_policy_template.v1"
    )
    tenant_id: str = Field(min_length=1)
    cell_id: str = Field(min_length=1)
    authority_entry_id: str = Field(min_length=1)
    authority_registry_sha256: str = Field(pattern=_HASH)
    authority_provision_sha256: str = Field(pattern=_HASH)
    attempt_id: str = Field(min_length=1)
    max_http_response_bytes: int = Field(gt=0, strict=True)
    max_http_decompressed_bytes: int = Field(gt=0, strict=True)
    max_http_timeout_seconds: float = Field(ge=1, allow_inf_nan=False)
    max_standard_n5_invocations: int = Field(gt=0, strict=True)
    max_metered_reentry_usd: Decimal = Field(gt=0, allow_inf_nan=False)

    @model_validator(mode="after")
    def _require_exact_identifiers(self) -> CandidateUnpricedExperimentPolicyTemplate:
        if any(
            value != value.strip()
            for value in (self.tenant_id, self.cell_id, self.authority_entry_id, self.attempt_id)
        ):
            raise ValueError("candidate_unpriced_template_scope_invalid")
        return self


class CandidateUnpricedAcquisitionPolicy(BaseModel):
    """One explicit server-configurable candidate-only research policy.

    The embedded authorization is the source owner's exact pretransport
    result, not a price or source-rights decision. Its writer-selected policy
    view must also be selected by the control composition root at current use.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[
        "polisyos.runtime.candidate_unpriced_acquisition_policy.v1",
        "polisyos.runtime.candidate_unpriced_acquisition_policy.v2",
    ] = _POLICY_V1
    purpose: Literal["bounded_candidate_research", "bounded_candidate_experiment_voi_unknown"] = (
        "bounded_candidate_research"
    )
    scope: CandidateUnpricedPolicyScope
    live_authorization: data_plane.LiveExecutionAuthorization
    n5_quota_profile: BudgetLedgerInvocationProfile
    monetary_cost: Literal["not_established"] = "not_established"
    hard_usd_reservation: Literal[False] = False
    observed_admission: Literal[False] = False
    publication_authority: Literal[False] = False
    limitations: tuple[str, ...] = Field(min_length=1)
    experiment_intent: Literal["bounded_experiment_voi_unknown"] | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    information_value: Literal["not_established"] | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    source_payload_ref: str | None = Field(
        default=None, pattern=_HASH, exclude_if=lambda value: value is None
    )
    request_content_hash: str | None = Field(
        default=None, pattern=_HASH, exclude_if=lambda value: value is None
    )
    original_metered_budget_usd: Decimal | None = Field(
        default=None, ge=0, allow_inf_nan=False, exclude_if=lambda value: value is None
    )
    configured_template: CandidateUnpricedExperimentPolicyTemplate | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    content_hash: str = Field(pattern=_HASH)

    @model_validator(mode="after")
    def _bind_policy(self) -> CandidateUnpricedAcquisitionPolicy:
        if self.schema_version == _POLICY_V1:
            if self.purpose != "bounded_candidate_research" or (
                _EXPERIMENT_FIELDS & self.model_fields_set
            ):
                raise ValueError("candidate_unpriced_policy_version_mismatch")
        elif (
            self.purpose != "bounded_candidate_experiment_voi_unknown"
            or self.experiment_intent != "bounded_experiment_voi_unknown"
            or self.information_value != "not_established"
            or self.source_payload_ref is None
            or self.request_content_hash is None
            or self.original_metered_budget_usd is None
            or "candidate_experiment_voi_not_established" not in self.limitations
        ):
            raise ValueError("candidate_unpriced_experiment_policy_incomplete")
        if self.configured_template is not None:
            template = self.configured_template
            budget = self.live_authorization.budget
            if (
                self.schema_version != _POLICY_V2
                or (template.tenant_id, template.cell_id)
                != (self.scope.tenant_id, self.scope.cell_id)
                or template.attempt_id != self.live_authorization.attempt_id
                or budget.max_response_bytes > template.max_http_response_bytes
                or budget.max_decompressed_bytes > template.max_http_decompressed_bytes
                or budget.timeout_seconds > template.max_http_timeout_seconds
                or self.n5_quota_profile.total_units - self.n5_quota_profile.protected_units
                > template.max_standard_n5_invocations
            ):
                raise ValueError("candidate_unpriced_template_policy_mismatch")
        binding = self.n5_quota_profile.run_binding
        if (
            not self.live_authorization.authorized
            or self.live_authorization.budget.call_budget != 1
            or self.live_authorization.budget.variable_budget != 1
            or self.n5_quota_profile.total_units <= self.n5_quota_profile.protected_units
            or (binding.tenant_id, binding.cell_id, binding.run_id, binding.control_job_id)
            != (
                self.scope.tenant_id,
                self.scope.cell_id,
                self.scope.run_id,
                self.scope.source_job_id,
            )
            or not _REQUIRED_LIMITATIONS.issubset(self.limitations)
            or len(set(self.limitations)) != len(self.limitations)
            or any(not item.strip() for item in self.limitations)
        ):
            raise ValueError("candidate_unpriced_policy_limits_invalid")
        expected = _content_hash(self.model_dump(mode="json", exclude={"content_hash"}))
        if self.content_hash != expected:
            raise ValueError("candidate_unpriced_policy_content_mismatch")
        return self


class CandidateUnpricedPolicyBinding(BaseModel):
    """Server-only selection of one exact policy view for one exact scope."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    scope: CandidateUnpricedPolicyScope
    policy_ref: artifacts.ArtifactRef

    @model_validator(mode="after")
    def _require_selected_policy(self) -> CandidateUnpricedPolicyBinding:
        if not _selected_ref(self.policy_ref, POLICY_KIND):
            raise ValueError("candidate_unpriced_policy_binding_invalid")
        return self


@dataclass(frozen=True, slots=True)
class CandidateUnpricedLiveContext:
    """Concrete owners carried to the existing live executor, not a permit."""

    control_service: ControlPlaneService
    scope: CandidateUnpricedPolicyScope
    policy_ref: ArtifactRef
    action_phase_ref: str
    budget_observer: ProducerBudgetObserver
    budget_state: BudgetState
    experiment_origin: VerifiedCandidateExperimentOrigin | None = None


def _content_hash(payload: object) -> str:
    return (
        "sha256:"
        + hashlib.sha256(
            canon.to_canonical_bytes(payload, canon.CanonSpec(forbid_floats=False))
        ).hexdigest()
    )


def issue_candidate_unpriced_policy(
    *,
    scope: CandidateUnpricedPolicyScope,
    live_authorization: data_plane.LiveExecutionAuthorization,
    n5_quota_profile: BudgetLedgerInvocationProfile,
    limitations: tuple[str, ...],
) -> CandidateUnpricedAcquisitionPolicy:
    """Construct policy bytes without selecting a server owner or permitting work.

    The composition root must select the persisted view and the live executor
    must rederive its Fabric authorization and quota from their actual owners.
    """
    if (
        type(scope) is not CandidateUnpricedPolicyScope
        or type(live_authorization) is not data_plane.LiveExecutionAuthorization
        or type(n5_quota_profile) is not BudgetLedgerInvocationProfile
    ):
        raise TypeError("candidate_unpriced_policy_inputs_untyped")
    draft = CandidateUnpricedAcquisitionPolicy.model_construct(
        scope=scope,
        live_authorization=live_authorization,
        n5_quota_profile=n5_quota_profile,
        limitations=limitations,
        content_hash="sha256:" + "0" * 64,
    )
    payload = draft.model_dump(mode="json", exclude={"content_hash"})
    return CandidateUnpricedAcquisitionPolicy.model_validate(
        {**payload, "content_hash": _content_hash(payload)}
    )


def issue_candidate_unpriced_experiment_policy(
    *,
    scope: CandidateUnpricedPolicyScope,
    live_authorization: data_plane.LiveExecutionAuthorization,
    n5_quota_profile: BudgetLedgerInvocationProfile,
    source_payload_ref: str,
    request_content_hash: str,
    original_metered_budget_usd: Decimal,
    limitations: tuple[str, ...],
    configured_template: CandidateUnpricedExperimentPolicyTemplate | None = None,
) -> CandidateUnpricedAcquisitionPolicy:
    """Declare one bounded experiment; live owners must verify its request.

    The source payload and request hash are content bindings, not standalone
    proof of the user's intent. Current and historical consumers must reopen
    the signed source through Control and independently verify the route,
    physical quota and Fabric authorization before any effect.
    """
    if (
        type(scope) is not CandidateUnpricedPolicyScope
        or type(live_authorization) is not data_plane.LiveExecutionAuthorization
        or type(n5_quota_profile) is not BudgetLedgerInvocationProfile
        or type(original_metered_budget_usd) is not Decimal
    ):
        raise TypeError("candidate_unpriced_policy_inputs_untyped")
    draft = CandidateUnpricedAcquisitionPolicy.model_construct(
        schema_version=_POLICY_V2,
        purpose="bounded_candidate_experiment_voi_unknown",
        scope=scope,
        live_authorization=live_authorization,
        n5_quota_profile=n5_quota_profile,
        limitations=limitations,
        experiment_intent="bounded_experiment_voi_unknown",
        information_value="not_established",
        source_payload_ref=source_payload_ref,
        request_content_hash=request_content_hash,
        original_metered_budget_usd=original_metered_budget_usd,
        configured_template=configured_template,
        content_hash="sha256:" + "0" * 64,
    )
    payload = draft.model_dump(mode="json", exclude={"content_hash"})
    return CandidateUnpricedAcquisitionPolicy.model_validate(
        {**payload, "content_hash": _content_hash(payload)}
    )


def _policy_schema_version(policy: CandidateUnpricedAcquisitionPolicy) -> str:
    if policy.schema_version == _POLICY_V1:
        return "1.0"
    if policy.schema_version == _POLICY_V2:
        return "2.0"
    raise ValueError("candidate_unpriced_policy_version_unsupported")


def _policy_inputs(policy: CandidateUnpricedAcquisitionPolicy) -> tuple[artifacts.InputRef, ...]:
    scope = policy.scope
    return tuple(
        artifacts.input_ref_from_artifact_ref(ref, role=role)
        for role, ref in (
            ("compiled_run", scope.compiled_ref),
            ("planner_report", scope.planner_report_ref),
            ("compiler_report", scope.compiler_report_ref),
            ("configured_port_source", scope.configured_port_source_ref),
        )
    )


def _require_policy_sources(
    store: CoreJSONArtifactStore, policy: CandidateUnpricedAcquisitionPolicy
) -> None:
    scope = policy.scope
    for ref in (
        scope.compiled_ref,
        scope.planner_report_ref,
        scope.compiler_report_ref,
        scope.configured_port_source_ref,
    ):
        manifest = store.get_manifest(ref)
        if (
            artifacts.artifact_ref_identity_key(artifacts.artifact_ref_for_manifest(manifest))
            != artifacts.artifact_ref_identity_key(ref)
            or not store.verify(ref).ok
        ):
            raise ValueError("candidate_unpriced_policy_source_unverified")
    if policy.schema_version == _POLICY_V1:
        # Preserve the historical V1 reader's raw-value hash law.
        report = artifacts.load_core_json_artifact(store, scope.planner_report_ref)
        actual_hash = agent_action_content_hash(report) if isinstance(report, dict) else None
    else:
        from polisyos.runtime.quality.acquisition_evaluation import _candidate_ref_same
        from polisyos.runtime.quality.acquisition_planner import (
            _N7_CONFIGURED_REPORT_SCHEMA,
            _validate_persisted_planner_report,
            load_acquisition_planner_report,
        )

        # The route hash binds the typed report's JSON projection. Decoded CAS
        # values contain a datetime object, whose raw canonical hash is the
        # artifact identity rather than this semantic route hash.
        report = load_acquisition_planner_report(store, scope.planner_report_ref)
        basis = report.requirement_basis_binding
        lineage = report.candidate_lineage
        if (
            report.schema_version != _N7_CONFIGURED_REPORT_SCHEMA
            or basis is None
            or lineage is None
            or not _candidate_ref_same(basis.compiler_report_ref, scope.compiler_report_ref)
            or not _candidate_ref_same(lineage.port_source_ref, scope.configured_port_source_ref)
            or len(
                tuple(
                    record
                    for record in report.acquisition_records
                    if record.compiled_requirement_ref == scope.compiled_requirement_ref
                )
            )
            != 1
            or _validate_persisted_planner_report(
                store=store, ref=scope.planner_report_ref, report=report
            )
        ):
            raise ValueError("candidate_unpriced_policy_planner_owner_not_established")
        actual_hash = agent_action_content_hash(report)
    if actual_hash != scope.planner_report_hash:
        raise ValueError("candidate_unpriced_policy_planner_hash_mismatch")


def persist_candidate_unpriced_policy(
    *,
    store: CoreJSONArtifactStore,
    event_log: RuntimeDiagnosticEventLog,
    policy: CandidateUnpricedAcquisitionPolicy,
) -> ArtifactRef:
    """Persist a non-template candidate policy as a selected owner artifact.

    Persistence alone does not select the policy in the server configuration.
    """
    if type(policy) is not CandidateUnpricedAcquisitionPolicy:
        raise TypeError("candidate_unpriced_policy_untyped")
    policy = CandidateUnpricedAcquisitionPolicy.model_validate(policy.model_dump(mode="json"))
    if policy.configured_template is not None:
        raise ValueError("candidate_unpriced_template_issuer_not_established")
    return _persist_owned_candidate_unpriced_policy(
        store=store,
        event_log=event_log,
        policy=policy,
    )


def _read_existing_owned_candidate_unpriced_policy(
    *,
    store: CoreJSONArtifactStore,
    event_log: RuntimeDiagnosticEventLog,
    policy: CandidateUnpricedAcquisitionPolicy,
) -> ArtifactRef | None:
    """Resolve one idempotent prior write from its event and complete CAS view."""
    event_id = "evt_candidate_unpriced_policy_" + policy.content_hash.removeprefix("sha256:")
    rows = event_log.list_events(event_id=event_id, limit=2)
    if not rows:
        return None
    if len(rows) != 1:
        raise ValueError("candidate_unpriced_policy_event_identity_ambiguous")
    event = rows[0].event
    if event.event_id != event_id or not event.payload_ref:
        raise ValueError("candidate_unpriced_policy_event_mismatch")

    inventory = getattr(store, "inventory_snapshot", None)
    if not callable(inventory):
        raise ValueError("candidate_unpriced_policy_inventory_unavailable")
    snapshot = inventory(artifact_id=artifacts.ArtifactID.model_validate(event.payload_ref))
    if getattr(snapshot, "verdict", None) != "pass":
        raise ValueError("candidate_unpriced_policy_inventory_unverified")
    matches: dict[tuple[str, str, str, str | None], ArtifactRef] = {}
    for entry in snapshot.entries:
        manifest = entry.manifest
        if manifest.kind != POLICY_KIND:
            continue
        if (
            manifest.media_type != "application/json"
            or manifest.artifact_schema
            != artifacts.SchemaInfo(name=POLICY_SCHEMA, version=_policy_schema_version(policy))
            or manifest.producer != artifacts.ProducerInfo(component=POLICY_PRODUCER, version="1.0")
            or manifest.artifact_id != artifacts.ArtifactID.model_validate(event.payload_ref)
        ):
            raise ValueError("candidate_unpriced_policy_inventory_identity_mismatch")
        ref = artifacts.artifact_ref_for_manifest(manifest)
        if not _selected_ref(ref, POLICY_KIND):
            raise ValueError("candidate_unpriced_policy_inventory_ref_untyped")
        entry_ref = entry.artifact_ref
        entry_artifact_id = (
            entry_ref.artifact_id if isinstance(entry_ref, artifacts.ArtifactRef) else entry_ref
        )
        if entry_artifact_id != ref.artifact_id:
            raise ValueError("candidate_unpriced_policy_inventory_identity_mismatch")
        identity = artifacts.artifact_ref_identity_key(ref)
        matches[identity] = ref
    if len(matches) != 1:
        raise ValueError("candidate_unpriced_policy_inventory_not_unique")
    selected = next(iter(matches.values()))
    existing = read_candidate_unpriced_policy(store=store, event_log=event_log, ref=selected)
    if existing != policy:
        raise ValueError("candidate_unpriced_policy_existing_content_mismatch")
    return selected


def _persist_owned_candidate_unpriced_policy(
    *,
    store: CoreJSONArtifactStore,
    event_log: RuntimeDiagnosticEventLog,
    policy: CandidateUnpricedAcquisitionPolicy,
) -> ArtifactRef:
    """Persist a policy after its actual owners have selected it.

    Template policies may use this private seam only after the composition root
    has derived their source, quota, and Fabric authorization from current owners.
    """
    if type(policy) is not CandidateUnpricedAcquisitionPolicy:
        raise TypeError("candidate_unpriced_policy_untyped")
    policy = CandidateUnpricedAcquisitionPolicy.model_validate(policy.model_dump(mode="json"))
    _require_policy_sources(store, policy)
    existing = _read_existing_owned_candidate_unpriced_policy(
        store=store,
        event_log=event_log,
        policy=policy,
    )
    if existing is not None:
        return existing
    inputs = _policy_inputs(policy)
    refs = tuple(sorted({str(item.artifact_id) for item in inputs}))
    generated_at = datetime.now(UTC).isoformat()
    scope = policy.scope
    from polisyos.runtime.quality.diagnostic_events import DiagnosticEventContractError

    try:
        result = write_runtime_authority_artifact(
            store,
            event_log,
            policy.model_dump(mode="json"),
            artifacts.ArtifactWriteOptions(
                kind=POLICY_KIND,
                media_type="application/json",
                schema=artifacts.SchemaInfo(
                    name=POLICY_SCHEMA, version=_policy_schema_version(policy)
                ),
                producer=artifacts.ProducerInfo(component=POLICY_PRODUCER, version="1.0"),
                inputs=list(inputs),
            ),
            evidence_id=policy.content_hash.removeprefix("sha256:"),
            evidence_class="authority_bearing",
            authority_role="producer_authority",
            provenance_kind="runtime_emitted",
            owner="team-runtime-quality",
            reader_contract=POLICY_KIND + ".reader",
            reader_contract_version=_policy_schema_version(policy),
            tenant_id=scope.tenant_id,
            cell_id=scope.cell_id,
            run_id=scope.run_id,
            job_id=scope.source_job_id,
            trace_id="trace-" + scope.source_job_id,
            span_id="span-candidate-unpriced-policy",
            parent_span_id=None,
            requested_execution_profile="governed",
            effective_execution_profile="governed",
            phase="candidate_unpriced_policy",
            generated_at=generated_at,
            as_of_time=generated_at,
            same_input_closure={
                "closure_id": "candidate-unpriced-policy:" + policy.content_hash,
                "status": "closed",
                "run_id": scope.run_id,
                "job_id": scope.source_job_id,
                "tenant_id": scope.tenant_id,
                "cell_id": scope.cell_id,
                "evidence_input_refs": refs,
                "closure_sha256": scope.design_problem_ref,
            },
            input_refs=refs,
            effective_mode_ref=policy.purpose,
            degradation_ledger_ref=None,
            semantic_binding_ref=policy.content_hash,
            validation_status="pass",
            blocking_status="non_blocking",
            governance=GovernanceMetadata(
                classification="internal",
                authority_boundary=POLICY_PRODUCER,
                pii="none",
                retention_policy="runtime-quality-90d",
                review_status="runtime_verified",
                override_policy="no_override",
                approval_policy="pa2_ds9_decision_required",
            ),
            event_id="evt_candidate_unpriced_policy_" + policy.content_hash.removeprefix("sha256:"),
            event_source=POLICY_PRODUCER,
            event_type=POLICY_EVENT,
            event_subject="run/" + scope.run_id + "/candidate/" + scope.candidate_id,
            state_before=None,
            state_after="configured_candidate_only",
            canon_spec=canon.CanonSpec(forbid_floats=False),
        )
    except DiagnosticEventContractError as exc:
        if exc.code != "authority_event_collision":
            raise
        existing = _read_existing_owned_candidate_unpriced_policy(
            store=store,
            event_log=event_log,
            policy=policy,
        )
        if existing is None:
            raise
        return existing
    loaded = read_candidate_unpriced_policy(store=store, event_log=event_log, ref=result.cas_ref)
    if loaded != policy:
        raise RuntimeError("candidate_unpriced_policy_readback_mismatch")
    return result.cas_ref


def read_candidate_unpriced_policy(
    *,
    store: CoreJSONArtifactStore,
    event_log: RuntimeDiagnosticEventLog,
    ref: ArtifactRef,
) -> CandidateUnpricedAcquisitionPolicy:
    """Reopen an exact historical selected policy without consulting current config."""
    if not _selected_ref(ref, POLICY_KIND):
        raise ValueError("candidate_unpriced_policy_profile_missing")
    manifest = store.get_manifest(ref)
    if (
        artifacts.artifact_ref_identity_key(artifacts.artifact_ref_for_manifest(manifest))
        != artifacts.artifact_ref_identity_key(ref)
        or not store.verify(ref).ok
        or manifest.artifact_schema
        not in (
            artifacts.SchemaInfo(name=POLICY_SCHEMA, version="1.0"),
            artifacts.SchemaInfo(name=POLICY_SCHEMA, version="2.0"),
        )
        or manifest.producer != artifacts.ProducerInfo(component=POLICY_PRODUCER, version="1.0")
    ):
        raise ValueError("candidate_unpriced_policy_owner_mismatch")
    policy = CandidateUnpricedAcquisitionPolicy.model_validate(
        artifacts.load_core_json_artifact(store, ref)
    )
    if manifest.artifact_schema.version != _policy_schema_version(policy):
        raise ValueError("candidate_unpriced_policy_version_mismatch")
    _require_policy_sources(store, policy)
    expected = sorted(
        (str(item.artifact_id), item.role, item.manifest_profile_sha256)
        for item in _policy_inputs(policy)
    )
    actual = sorted(
        (str(item.artifact_id), item.role, item.manifest_profile_sha256) for item in manifest.inputs
    )
    if actual != expected:
        raise ValueError("candidate_unpriced_policy_lineage_mismatch")
    scope = policy.scope
    report = reconcile_authority_ref(
        artifact_store=store,
        event_log=event_log,
        cas_ref=ref,
        expected_tenant_id=scope.tenant_id,
        expected_cell_id=scope.cell_id,
        expected_run_id=scope.run_id,
        expected_job_id=scope.source_job_id,
    )
    event_id = "evt_candidate_unpriced_policy_" + policy.content_hash.removeprefix("sha256:")
    rows = event_log.list_events(event_id=event_id, limit=2)
    if report.durable_event_id != event_id or len(rows) != 1:
        raise ValueError("candidate_unpriced_policy_event_missing")
    event = rows[0].event
    if (
        event.event_type != POLICY_EVENT
        or event.event_source != POLICY_PRODUCER
        or event.producer_component != POLICY_PRODUCER
        or event.producer_version != "1.0"
        or event.phase != "candidate_unpriced_policy"
        or event.payload_ref != str(ref.artifact_id)
        or tuple(event.artifact_refs) != (str(ref.artifact_id),)
        or event.tenant_id != scope.tenant_id
        or event.cell_id != scope.cell_id
        or event.run_id != scope.run_id
        or event.job_id != scope.source_job_id
    ):
        raise ValueError("candidate_unpriced_policy_event_mismatch")
    return policy


def list_current_candidate_unpriced_policy_bindings(
    *,
    control_service: ControlPlaneService,
    tenant_id: str,
    cell_id: str,
    run_id: str,
    source_job_id: str,
    candidate_id: str,
) -> tuple[CandidateUnpricedPolicyBinding, ...]:
    """Reopen configured views and uniquely selected issued template policies.

    This is a read-only selection, not source permission or an action permit.
    Template-issued entries are accepted only while their complete embedded
    server configuration remains selected; every effect still replays its owners.
    """
    from polisyos.runtime.http.services.control.run_lifecycle import ControlPlaneService
    from polisyos.runtime.http.services.control_registry_providers import ControlRegistryProviders

    if type(control_service) is not ControlPlaneService or any(
        not isinstance(value, str) or not value.strip()
        for value in (tenant_id, cell_id, run_id, source_job_id, candidate_id)
    ):
        raise ValueError("candidate_unpriced_policy_control_owner_missing")
    providers = control_service._registry_providers
    if type(providers) is not ControlRegistryProviders:
        raise ValueError("candidate_unpriced_policy_control_owner_missing")
    scope_key = (tenant_id, cell_id, run_id, source_job_id, candidate_id)
    selected = [
        item
        for item in providers.candidate_unpriced_policy_bindings
        if (
            item.scope.tenant_id,
            item.scope.cell_id,
            item.scope.run_id,
            item.scope.source_job_id,
            item.scope.candidate_id,
        )
        == scope_key
    ]
    templates = providers.candidate_unpriced_policy_templates
    if not templates:
        return tuple(selected)
    event_log = control_service._diagnostic_event_log
    store = control_service._artifact_store
    inventory = getattr(store, "inventory_snapshot", None)
    if not callable(inventory):
        raise ValueError("candidate_unpriced_policy_inventory_unavailable")
    limit = 500
    rows = event_log.list_events(run_id=run_id, job_id=source_job_id, limit=limit)
    if len(rows) >= limit:
        raise ValueError("candidate_unpriced_policy_event_inventory_incomplete")
    seen = {artifacts.artifact_ref_identity_key(item.policy_ref) for item in selected}
    for row in rows:
        event = row.event
        if (
            event.event_type != POLICY_EVENT
            or event.event_source != POLICY_PRODUCER
            or event.producer_component != POLICY_PRODUCER
            or event.event_subject != f"run/{run_id}/candidate/{candidate_id}"
            or (event.tenant_id, event.cell_id, event.run_id, event.job_id)
            != (tenant_id, cell_id, run_id, source_job_id)
        ):
            continue
        if not event.payload_ref:
            raise ValueError("candidate_unpriced_policy_event_payload_missing")
        artifact_id = artifacts.ArtifactID.model_validate(event.payload_ref)
        payload_ref = str(artifact_id)
        raw_payload_accessible = True
        try:
            raw_payload = store.get_bytes(artifact_id)
        except artifacts.ArtifactOwnershipError:
            # The bare-ID default view may be outside this tenant's readable
            # ownership while an exact selected manifest view remains owned.
            # Do not widen scope or retry the payload through another selector;
            # let the existing inventory and selected-ref reader decide.
            raw_payload_accessible = False
        if raw_payload_accessible:
            if type(raw_payload) is not bytes or payload_ref != event.payload_ref:
                raise ValueError("candidate_unpriced_policy_event_payload_identity_mismatch")
            if "sha256:" + hashlib.sha256(raw_payload).hexdigest() != payload_ref:
                raise ValueError("candidate_unpriced_policy_event_payload_identity_mismatch")
            policy_payload = CandidateUnpricedAcquisitionPolicy.model_validate(
                canon.from_canonical_bytes(
                    raw_payload,
                    version=canon.CanonSpec(forbid_floats=False).version,
                )
            )
            if (
                policy_payload.configured_template is None
                or policy_payload.configured_template not in templates
            ):
                # Keep the negative shortcut inside Core's existing selected
                # profile boundary. Raw decoding above is useful for cheaply
                # recognizing an inactive template, but it cannot bypass a
                # declared-profile refusal that the prior full reader would make.
                # If the default manifest/profile path cannot establish the same
                # typed policy, fall through to the unchanged full inventory and
                # reader path so that path remains authoritative.
                try:
                    selected_manifest = store.get_manifest(artifact_id)
                    selected_ref = artifacts.artifact_ref_for_manifest(selected_manifest)
                    selected_payload = artifacts.load_core_json_artifact(
                        store, selected_ref, raw_payload_bytes=raw_payload
                    )
                    selected_policy = CandidateUnpricedAcquisitionPolicy.model_validate(
                        selected_payload
                    )
                except artifacts.ArtifactOwnershipError:
                    pass
                except (OSError, TypeError, ValueError):
                    pass
                else:
                    if selected_policy == policy_payload:
                        continue
        snapshot = inventory(artifact_id=artifact_id)
        if snapshot.verdict != "pass":
            raise ValueError("candidate_unpriced_policy_inventory_unverified")
        candidates: dict[tuple[str, str, str, str | None], CandidateUnpricedPolicyBinding] = {}
        for entry in snapshot.entries:
            manifest = entry.manifest
            if (
                manifest.kind != POLICY_KIND
                or manifest.media_type != "application/json"
                or manifest.producer
                != artifacts.ProducerInfo(component=POLICY_PRODUCER, version="1.0")
            ):
                continue
            ref = artifacts.artifact_ref_for_manifest(manifest)
            identity = artifacts.artifact_ref_identity_key(ref)
            if identity in candidates:
                continue
            policy = read_candidate_unpriced_policy(store=store, event_log=event_log, ref=ref)
            if policy.configured_template is None:
                continue
            if policy.configured_template not in templates:
                continue
            if (
                policy.scope.tenant_id,
                policy.scope.cell_id,
                policy.scope.run_id,
                policy.scope.source_job_id,
                policy.scope.candidate_id,
            ) != scope_key:
                raise ValueError("candidate_unpriced_policy_event_scope_mismatch")
            candidates[identity] = CandidateUnpricedPolicyBinding(
                scope=policy.scope, policy_ref=ref
            )
        if len(candidates) > 1:
            raise ValueError("candidate_unpriced_policy_profile_not_unique")
        for identity, binding in candidates.items():
            if identity not in seen:
                selected.append(binding)
                seen.add(identity)
    after = event_log.list_events(run_id=run_id, job_id=source_job_id, limit=limit)
    if len(after) >= limit or after != rows or control_service._registry_providers is not providers:
        raise ValueError("candidate_unpriced_policy_selection_changed")
    return tuple(selected)


def resolve_current_candidate_unpriced_policy(
    *,
    control_service: ControlPlaneService,
    scope: CandidateUnpricedPolicyScope,
) -> tuple[ArtifactRef, CandidateUnpricedAcquisitionPolicy]:
    """Resolve one exact server-selected view; this is not a fetch permit."""
    from polisyos.runtime.http.services.control.run_lifecycle import ControlPlaneService
    from polisyos.runtime.http.services.control_registry_providers import ControlRegistryProviders
    from polisyos.runtime.quality.acquisition_evaluation import _candidate_model_values_same

    if type(control_service) is not ControlPlaneService or type(scope) is not (
        CandidateUnpricedPolicyScope
    ):
        raise ValueError("candidate_unpriced_policy_control_owner_missing")
    providers = control_service._registry_providers
    if type(providers) is not ControlRegistryProviders:
        raise ValueError("candidate_unpriced_policy_control_owner_missing")
    bindings = list_current_candidate_unpriced_policy_bindings(
        control_service=control_service,
        tenant_id=scope.tenant_id,
        cell_id=scope.cell_id,
        run_id=scope.run_id,
        source_job_id=scope.source_job_id,
        candidate_id=scope.candidate_id,
    )
    matches = tuple(
        binding for binding in bindings if _candidate_model_values_same(binding.scope, scope)
    )
    if len(matches) != 1:
        raise ValueError("candidate_unpriced_policy_not_selected")
    ref = matches[0].policy_ref
    policy = read_candidate_unpriced_policy(
        store=control_service._artifact_store,
        event_log=control_service._diagnostic_event_log,
        ref=ref,
    )
    if not _candidate_model_values_same(policy.scope, scope):
        raise ValueError("candidate_unpriced_policy_scope_mismatch")
    return ref, policy


def verify_candidate_unpriced_experiment_policy_intent(
    *,
    control_service: ControlPlaneService,
    closure: object,
    scope: CandidateUnpricedPolicyScope,
    policy_ref: ArtifactRef,
) -> OriginalRunBudgetScopeEvidence:
    """Reopen the exact signed request and configured experiment declaration.

    This is only the original-intent join. The caller must independently
    reconcile the selected source cycle, action, lease, Fabric authorization,
    journal and physical quota before taking an effect.
    """
    from polisyos.runtime.http.services.control.run_lifecycle import (
        ControlPlaneService,
        OriginalRunBudgetScopeEvidence,
    )

    if type(control_service) is not ControlPlaneService or type(scope) is not (
        CandidateUnpricedPolicyScope
    ):
        raise ValueError("candidate_experiment_policy_owner_not_established")
    selected, policy = resolve_current_candidate_unpriced_policy(
        control_service=control_service, scope=scope
    )
    if (
        not _selected_ref(policy_ref, POLICY_KIND)
        or artifacts.artifact_ref_identity_key(selected)
        != artifacts.artifact_ref_identity_key(policy_ref)
        or policy.schema_version != _POLICY_V2
        or any(
            getattr(closure, name, None) != getattr(scope, name)
            for name in ("tenant_id", "cell_id", "run_id", "source_job_id")
        )
    ):
        raise ValueError("candidate_experiment_policy_intent_not_established")
    evidence = ControlPlaneService.verify_candidate_experiment_intent(
        control_service, closure=closure
    )
    if (
        type(evidence) is not OriginalRunBudgetScopeEvidence
        or (
            evidence.tenant_id,
            evidence.cell_id,
            evidence.run_id,
            evidence.source_job_id,
        )
        != (scope.tenant_id, scope.cell_id, scope.run_id, scope.source_job_id)
        or not evidence.scope_explicit
        or evidence.run_budget_scope != "metered_paid_producers_and_bounded_candidate"
        or not evidence.candidate_acquisition_intent_present
        or evidence.candidate_acquisition_intent != policy.experiment_intent
        or evidence.request_snapshot_schema != "polisyos.runtime.control_nl_request_snapshot.v5"
        or evidence.source_payload_ref != policy.source_payload_ref
        or evidence.request_content_hash != policy.request_content_hash
        or evidence.run_budget_usd != policy.original_metered_budget_usd
    ):
        raise ValueError("candidate_experiment_policy_intent_not_established")
    selected_again, _ = resolve_current_candidate_unpriced_policy(
        control_service=control_service, scope=scope
    )
    if artifacts.artifact_ref_identity_key(selected_again) != artifacts.artifact_ref_identity_key(
        selected
    ):
        raise ValueError("candidate_experiment_policy_selection_changed")
    return evidence


def reconcile_candidate_unpriced_work(
    *,
    control_service: ControlPlaneService,
    scope: CandidateUnpricedPolicyScope,
    policy_ref: ArtifactRef,
    action_phase_ref: str,
    live_authorization: data_plane.LiveExecutionAuthorization,
    budget_observer: ProducerBudgetObserver,
    budget_state: BudgetState,
    experiment_source_closure: object | None = None,
    experiment_origin: VerifiedCandidateExperimentOrigin | None = None,
) -> tuple[ProducerBudgetObservation, BudgetInvocationCapacityObservation]:
    """Reconcile actual owners before a candidate call; reserve no USD or N5 unit.

    The live executor must supply the authorization it independently derived
    from its source/harness and enforce its own journal permit. The numerical
    producer must still reserve each physical invocation through its owner.
    """
    from polisyos.runtime.quality.acquisition_route_loop import (
        AcquisitionCandidateExperimentPhaseReceipt,
        AcquisitionRoutePhaseReceipt,
        VerifiedCandidateExperimentOrigin,
    )
    from polisyos.scientist.orchestration.engine import (
        BudgetInvocationQuotaPolicy,
        BudgetState,
        ProducerBudgetObserver,
    )

    selected_ref, policy = resolve_current_candidate_unpriced_policy(
        control_service=control_service, scope=scope
    )
    experiment_evidence = None
    if policy.schema_version == _POLICY_V2:
        if (
            type(experiment_origin) is not VerifiedCandidateExperimentOrigin
            or experiment_source_closure is not None
            or experiment_origin.policy_scope != scope
            or experiment_origin.policy_ref != policy_ref
        ):
            raise ValueError("candidate_experiment_policy_intent_not_established")
        experiment_evidence = verify_candidate_unpriced_experiment_policy_intent(
            control_service=control_service,
            closure=experiment_origin,
            scope=scope,
            policy_ref=policy_ref,
        )
    elif experiment_source_closure is not None or experiment_origin is not None:
        raise ValueError("candidate_experiment_policy_version_not_established")
    if (
        not _selected_ref(policy_ref, POLICY_KIND)
        or artifacts.artifact_ref_identity_key(selected_ref)
        != artifacts.artifact_ref_identity_key(policy_ref)
        or type(live_authorization) is not data_plane.LiveExecutionAuthorization
        or live_authorization != policy.live_authorization
        or type(budget_observer) is not ProducerBudgetObserver
        or type(budget_state) is not BudgetState
        or any(
            name in vars(budget_observer)
            for name in ("admit", "observe", "observe_standard_invocation_capacity")
        )
    ):
        raise ValueError("candidate_unpriced_policy_live_owner_mismatch")
    admission = control_service._control_store.current_execution_job_admission()
    if (
        admission.job.kind != "acquisition"
        or admission.job.state != "running"
        or admission.job.run_id != scope.run_id
        or admission.scope.status != "established"
        or admission.scope.actor_authenticated is not True
        or not admission.scope.actor_subject
        or admission.scope.tenant_id != scope.tenant_id
        or admission.scope.cell_id != scope.cell_id
    ):
        raise ValueError("candidate_unpriced_policy_live_job_not_admitted")
    sink = control_service.acquisition_route_sink
    experiment_snapshot: tuple[object, object, object] | None = None
    if experiment_origin is not None:
        handler = getattr(control_service, "_acquisition_job_handler", None)
        action_service = getattr(handler, "__self__", None)
        production_port = getattr(action_service, "_production_execution_port", None)
        bridge = getattr(production_port, "_world_growth_bridge", None)
        try:
            from polisyos.runtime.quality.candidate_acquisition_action import (
                _current_candidate_experiment_action,
                _select_current_candidate_experiment_outcome,
            )

            selected, phase, live_admission = _current_candidate_experiment_action(
                bridge, experiment_origin, action_phase_ref
            )
        except (OSError, RuntimeError, TypeError, ValueError) as exc:
            raise ValueError("candidate_experiment_action_not_current") from exc
        if (
            type(phase) is not AcquisitionCandidateExperimentPhaseReceipt
            or phase.receipt_phase != "executing"
            or phase.policy_scope != scope
            or phase.policy_ref != policy_ref
            or phase.request_content_hash != experiment_origin.request_content_hash
            or phase.compiled_ref != str(scope.compiled_ref.artifact_id)
            or phase.planner_report_hash != scope.planner_report_hash
            or live_admission != admission
        ):
            raise ValueError("candidate_experiment_action_scope_mismatch")
        experiment_outcomes = sink.experiment_action_outcomes(
            tenant_id=scope.tenant_id,
            cell_id=scope.cell_id,
            run_id=scope.run_id,
            source_job_id=scope.source_job_id,
            route_id=phase.route_id,
            verified_origin=experiment_origin,
        )
        action = _select_current_candidate_experiment_outcome(
            experiment_outcomes,
            origin=experiment_origin,
            action_job_id=admission.job.job_id,
            action_generation=phase.action_generation,
            receipt_ref=action_phase_ref,
            required_phase="executing",
        )
        if action.latest_receipt != phase:
            raise ValueError("candidate_experiment_action_not_current")
        experiment_snapshot = (selected, phase, live_admission)
    else:
        phase = sink._read_verified_action_phase(action_phase_ref).receipt
        if (
            type(phase) is not AcquisitionRoutePhaseReceipt
            or phase.receipt_phase != "executing"
            or phase.tenant_id != scope.tenant_id
            or phase.cell_id != scope.cell_id
            or phase.run_id != scope.run_id
            or phase.source_job_id != scope.source_job_id
            or phase.job_id != admission.job.job_id
            or phase.compiled_ref != str(scope.compiled_ref.artifact_id)
            or phase.planner_report_hash != scope.planner_report_hash
        ):
            raise ValueError("candidate_unpriced_policy_action_scope_mismatch")
        action = sink.current_action_outcome(
            tenant_id=scope.tenant_id,
            cell_id=scope.cell_id,
            run_id=scope.run_id,
            source_job_id=scope.source_job_id,
            route_id=phase.route_id,
        )
        if (
            action is None
            or action.head.receipt_ref != action_phase_ref
            or action.head.job_id != admission.job.job_id
            or action.latest_receipt != phase
        ):
            raise ValueError("candidate_unpriced_policy_action_not_current")
    selected_quota_profile = policy.n5_quota_profile
    if type(selected_quota_profile) is not BudgetLedgerInvocationProfile:
        raise ValueError("candidate_unpriced_policy_live_owner_mismatch")
    bound_quota_profile = budget_observer.invocation_quota_profile
    if (
        bound_quota_profile is not None and bound_quota_profile != selected_quota_profile
    ) or budget_observer.invocation_purpose != "standard":
        raise ValueError("candidate_unpriced_policy_live_owner_mismatch")
    ProducerBudgetObserver.require_bound_state(budget_observer, budget_state)
    budget = ProducerBudgetObserver.admit(budget_observer)
    if budget.predicate_basis != "independently_reconciled" or budget.remaining_usd <= Decimal(0):
        raise ValueError("candidate_unpriced_policy_n5_capacity_not_established")
    if budget.run_binding != selected_quota_profile.run_binding:
        raise ValueError("candidate_unpriced_policy_live_owner_mismatch")
    try:
        selected_quota = ProducerBudgetObserver.bind_invocation_policy_from_selected_owner(
            budget_observer,
            BudgetInvocationQuotaPolicy.model_validate(
                selected_quota_profile.model_dump(mode="python", exclude={"run_binding"}),
                strict=True,
            ),
            purpose="standard",
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("candidate_unpriced_policy_live_owner_mismatch") from exc
    if (
        type(selected_quota) is not BudgetLedgerInvocationProfile
        or selected_quota != selected_quota_profile
        or budget_observer.invocation_quota_profile != selected_quota_profile
        or budget_observer.invocation_purpose != "standard"
    ):
        raise ValueError("candidate_unpriced_policy_live_owner_mismatch")
    capacity = ProducerBudgetObserver.observe_standard_invocation_capacity(budget_observer)
    if (
        capacity.status != "available"
        or capacity.profile_digest != selected_quota_profile.profile_digest
    ):
        raise ValueError("candidate_unpriced_policy_n5_capacity_not_established")
    selected_again, _ = resolve_current_candidate_unpriced_policy(
        control_service=control_service, scope=scope
    )
    if artifacts.artifact_ref_identity_key(selected_again) != artifacts.artifact_ref_identity_key(
        selected_ref
    ):
        raise ValueError("candidate_unpriced_policy_selection_changed")
    if control_service._control_store.current_execution_job_admission() != admission:
        raise ValueError("candidate_unpriced_policy_live_job_changed")
    if experiment_origin is None:
        if (
            sink.current_action_outcome(
                tenant_id=scope.tenant_id,
                cell_id=scope.cell_id,
                run_id=scope.run_id,
                source_job_id=scope.source_job_id,
                route_id=phase.route_id,
            )
            != action
        ):
            raise ValueError("candidate_unpriced_policy_action_changed")
    else:
        current_outcomes = sink.experiment_action_outcomes(
            tenant_id=scope.tenant_id,
            cell_id=scope.cell_id,
            run_id=scope.run_id,
            source_job_id=scope.source_job_id,
            route_id=phase.route_id,
            verified_origin=experiment_origin,
        )
        current_action = _select_current_candidate_experiment_outcome(
            current_outcomes,
            origin=experiment_origin,
            action_job_id=admission.job.job_id,
            action_generation=phase.action_generation,
            receipt_ref=action_phase_ref,
            required_phase="executing",
        )
        if current_action != action or current_outcomes != experiment_outcomes:
            raise ValueError("candidate_experiment_action_changed")
    if (
        experiment_evidence is not None
        and verify_candidate_unpriced_experiment_policy_intent(
            control_service=control_service,
            closure=experiment_origin,
            scope=scope,
            policy_ref=policy_ref,
        )
        != experiment_evidence
    ):
        raise ValueError("candidate_experiment_policy_intent_changed")
    if experiment_origin is not None:
        try:
            selected_after, phase_after, admission_after = _current_candidate_experiment_action(
                bridge, experiment_origin, action_phase_ref
            )
        except (OSError, RuntimeError, TypeError, ValueError) as exc:
            raise ValueError("candidate_experiment_action_changed") from exc
        if (selected_after, phase_after, admission_after) != experiment_snapshot:
            raise ValueError("candidate_experiment_action_changed")
    return budget, capacity
