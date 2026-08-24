"""Mandate-bounded, persisted authority decisions before agent effects."""

from __future__ import annotations

import re
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib import import_module
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Literal, Protocol, cast, final

from pydantic import AwareDatetime, BaseModel, Field, model_validator

from polisyos.core import artifacts, canon
from polisyos.pdc import (
    AuthorityBoundary,
    Layer2ReadinessModel,
    OperationContract,
    OperationInvocationRecord,
)
from polisyos.runtime.http.mutation_policy import RuntimeIdempotencyStore
from polisyos.runtime.http.permissions import RuntimePermission
from polisyos.runtime.http.security import PolicyOSRole
from polisyos.runtime.quality.authority import GovernanceMetadata
from polisyos.runtime.quality.authority_reconciliation import reconcile_authority_ref
from polisyos.runtime.quality.candidate_firewall import (
    CandidateFirewallError,
    assert_no_candidate_authority_laundering,
)
from polisyos.runtime.quality.design_axes.mandate_bounded_delegation import (
    HUMAN_DECISION_RECORD_V2,
    LAYER2_S7_AGENT_ACTION_DELEGATION_SCHEMA_VERSION,
    LAYER2_S7_DELEGATION_SCHEMA_VERSION,
    DecisionOption,
    DelegatedActionEnvelope,
    DelegationContract,
    DraftActionScope,
    FiveRightsRequirement,
    HumanDecisionFiveRightsBinding,
    HumanDecisionRecord,
    HumanDecisionRequest,
    build_human_decision_request,
)
from polisyos.runtime.quality.event_log import RuntimeDiagnosticEventLog
from polisyos.runtime.quality.memory_influence import memory_influence_claim_evidence_issues
from polisyos.runtime.quality.prompt_tool_ledger import ModelAssistedStepLedger

if TYPE_CHECKING:
    from polisyos.runtime.http.authorization import BoundActionPermissionVerification
    from polisyos.runtime.http.resource_binding import BoundAuthorizationResource
    from polisyos.runtime.http.services.human_decision_contracts import (
        HumanDecisionPA2GatewayAdapterInput,
    )

    class _CasRef(Protocol):
        @property
        def artifact_id(self) -> object: ...

    class _AuthorityArtifactWriteResult(Protocol):
        @property
        def cas_ref(self) -> _CasRef: ...

        @property
        def payload_sha256(self) -> str: ...


def write_runtime_authority_artifact(
    store: object,
    event_log: object,
    payload: object,
    options: artifacts.ArtifactWriteOptions,
    **authority_fields: object,
) -> _AuthorityArtifactWriteResult:
    """Load the namespace-package writer while retaining the testable seam."""

    authority_artifacts = cast(
        "Any", import_module("polisyos.runtime.http.services.control.artifacts")
    )
    return cast(
        "_AuthorityArtifactWriteResult",
        authority_artifacts.write_runtime_authority_artifact(
            store,
            event_log,
            payload,
            options,
            **authority_fields,
        ),
    )


class _HumanDecisionServiceProtocol(Protocol):
    """Structural annotation for the exact-type checked runtime resolver."""

    def resolve_gateway_adapter(
        self,
        adapter: HumanDecisionPA2GatewayAdapterInput,
        *,
        evaluated_at: datetime,
        operation: object,
        invocation: object,
        intent: object,
        bound_permission: object,
        resolved_contract: object,
        admission: object,
        admission_ref: str,
        selected_envelope: object,
        effect_binding: object,
    ) -> object: ...


AGENT_ACTION_AUTHORITY_SCHEMA_VERSION: Literal["policyos.runtime.agent_action_authority.v1"] = (
    "policyos.runtime.agent_action_authority.v1"
)
AGENT_ACTION_ADMISSION_SCHEMA_VERSION: Literal["policyos.runtime.agent_action_admission.v1"] = (
    "policyos.runtime.agent_action_admission.v1"
)
AGENT_ACTION_AUTHORITY_RULE_VERSION = "policyos.gy.pa2.agent-action-authority.v1"

DELEGATION_CONTRACT_ARTIFACT_KIND = "runtime_quality.agent_action_delegation_contract"
AGENT_ACTION_ADMISSION_ARTIFACT_KIND = "runtime_quality.agent_action_admission"
HUMAN_DECISION_ARTIFACT_KIND = "runtime_quality.agent_action_human_decision"
AGENT_ACTION_DECISION_ARTIFACT_KIND = "runtime_quality.agent_action_authority_decision"

AgentActionOutcome = Literal["allowed", "refused"]
PredicateName = Literal[
    "verified_identity",
    "explicit_permission",
    "mandate_bounded_delegation",
    "operation_in_envelope",
    "live_accountability",
]
PredicateProvenance = Literal["recomputed", "independently_reconciled"]

_PREDICATE_NAMES: tuple[PredicateName, ...] = (
    "verified_identity",
    "explicit_permission",
    "mandate_bounded_delegation",
    "operation_in_envelope",
    "live_accountability",
)
_ACTION_KIND_PATTERN = re.compile(r"^[a-z][a-z0-9_.:-]*$")
_SHA256_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
_AUTHORITY_SCOPE_KEY_PARTS = frozenset(
    {"authority_scope", "delegation_scope", "mandate_scope", "scope", "scope_selector"}
)
_AUTHORITY_SCOPE_VALUE_MARKERS = (
    "action_envelope",
    "delegation-envelope:",
    "delegation_contract",
    "delegation-contract",
    "/delegation-contract",
    "mandate_scope",
)
_DECISION_MAY_NOT_USE_FOR = [
    "claim_evidence",
    "publication_authority",
    "promotion_authority",
    "legal_authority",
    "data_authority",
    "permission_vocabulary",
]


class AgentActionIntent(Layer2ReadinessModel):
    """Invocation intent whose authority comes only from owner-controlled inputs."""

    action_kind: str = Field(..., pattern=r"^[a-z][a-z0-9_.:-]*$", max_length=120)
    draft_scope: DraftActionScope | None = None
    tool_name: str | None = Field(default=None, min_length=1, max_length=200)

    @model_validator(mode="after")
    def _validate_typed_surfaces(self) -> AgentActionIntent:
        if self.action_kind == "draft" and self.draft_scope is None:
            raise ValueError("draft action requires audience and externality")
        if self.action_kind != "draft" and self.draft_scope is not None:
            raise ValueError("draft scope is valid only for the draft action kind")
        if self.action_kind == "tool_call" and self.tool_name is None:
            raise ValueError("tool_call action requires a tool name")
        return self


class AgentActionAdmissionBundle(Layer2ReadinessModel):
    """Signed admission of all memory, input, and tool influence for one invocation."""

    schema_version: Literal["policyos.runtime.agent_action_admission.v1"] = (
        AGENT_ACTION_ADMISSION_SCHEMA_VERSION
    )
    bundle_id: str = Field(..., min_length=1, max_length=180)
    bundle_ref: str = Field(..., min_length=1, max_length=300)
    invocation_content_hash: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")
    operation_content_hash: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")
    intent_content_hash: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")
    permission_proof_hash: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")
    bound_resource_digest: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")
    delegation_contract_ref: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")
    effect_binding_digest: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")
    memory_claim_payload: dict[str, object] = Field(default_factory=dict)
    authority_input_payload: dict[str, object] = Field(default_factory=dict)
    tool_ledger: ModelAssistedStepLedger | None = None
    hypothesis_ledger: dict[str, object] | None = None
    authority_boundary: AuthorityBoundary
    rule_version_ref: str = Field(..., min_length=1, max_length=300)
    admitted_at: AwareDatetime

    @model_validator(mode="after")
    def _validate_admission_authority(self) -> AgentActionAdmissionBundle:
        boundary = self.authority_boundary
        if (
            boundary.source_authority != "deterministic_producer"
            or boundary.posture not in {"governed", "production"}
            or "agent_action_input_admission" not in boundary.authoritative_for
        ):
            raise ValueError("agent action admission requires governed producer authority")
        return self


@dataclass(frozen=True, slots=True)
class AgentActionEffectBinding:
    """Composition-root-owned binding from an action tuple to one effect adapter."""

    binding_id: str
    action_kind: str
    operation_id: str
    operation_version: str
    implementation_ref: str
    handler: Callable[[OperationInvocationRecord], object]
    tool_name: str | None = None

    def __post_init__(self) -> None:
        for field_name in (
            "binding_id",
            "action_kind",
            "operation_id",
            "operation_version",
            "implementation_ref",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"effect binding {field_name} must be non-empty")
        if not _ACTION_KIND_PATTERN.fullmatch(self.action_kind):
            raise ValueError("effect binding action kind is invalid")
        if not callable(self.handler):
            raise TypeError("effect binding handler must be callable")
        if self.action_kind == "tool_call" and not self.tool_name:
            raise ValueError("tool-call effect binding requires a tool name")
        if self.action_kind != "tool_call" and self.tool_name is not None:
            raise ValueError("tool name is valid only for a tool-call effect binding")

    @property
    def key(self) -> tuple[str, str, str]:
        """Return the exact owner-registry lookup key."""

        return self.action_kind, self.operation_id, self.operation_version

    @property
    def binding_digest(self) -> str:
        """Return a content binding for the declared adapter identity and action tuple."""

        return _exact_hash(
            {
                "binding_id": self.binding_id,
                "action_kind": self.action_kind,
                "operation_id": self.operation_id,
                "operation_version": self.operation_version,
                "implementation_ref": self.implementation_ref,
                "tool_name": self.tool_name,
            }
        )


class AgentActionAuthorityWriteContext(Layer2ReadinessModel):
    """Runtime-owned identity used by the existing authority artifact writer."""

    tenant_id: str = Field(..., min_length=1, max_length=200)
    cell_id: str | None = Field(default=None, min_length=1, max_length=200)
    run_id: str = Field(..., min_length=1, max_length=200)
    job_id: str = Field(..., min_length=1, max_length=200)
    trace_id: str = Field(..., min_length=1, max_length=200)
    span_id: str = Field(..., min_length=1, max_length=200)
    parent_span_id: str | None = Field(default=None, min_length=1, max_length=200)
    owner: str = Field(..., min_length=1, max_length=200)
    requested_execution_profile: str = Field(..., min_length=1, max_length=80)
    effective_execution_profile: str = Field(..., min_length=1, max_length=80)
    effective_mode_ref: str = Field(..., min_length=1, max_length=300)
    degradation_ledger_ref: str | None = Field(default=None, min_length=1, max_length=300)


class ResolvedDelegationContract(Layer2ReadinessModel):
    """CAS/event/signature-resolved mandate artifact returned only by the owner gateway."""

    contract: DelegationContract
    contract_cas_ref: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")
    contract_payload_hash: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")
    resolved_for_resource_digest: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")
    signer_identity: str = Field(..., min_length=1, max_length=300)
    reconciliation_event_id: str = Field(..., min_length=1, max_length=300)
    predicate_provenance: Literal["independently_reconciled"] = "independently_reconciled"


class AgentActionPermissionSnapshot(Layer2ReadinessModel):
    """Serializable snapshot of the exact DS20 proof consumed by the gate."""

    subject: str
    tenant_id: str
    jwt_id: str
    roles: tuple[str, ...]
    authorization_source: str
    required_permission: str
    granted_permissions: tuple[str, ...]
    resource_digest: str
    resource_kind: str
    resource_authority: str
    body_sha256: str
    query_sha256: str


class AgentActionPredicateCheck(Layer2ReadinessModel):
    """One recomputed conjunct in the pre-action authority decision."""

    predicate: PredicateName
    satisfied: bool
    provenance: PredicateProvenance
    reason: str = Field(..., min_length=1, max_length=500)


class AgentActionAuthorityDecision(Layer2ReadinessModel):
    """Persisted allow or refusal with one replay-linked governed shape."""

    schema_version: Literal["policyos.runtime.agent_action_authority.v1"] = (
        AGENT_ACTION_AUTHORITY_SCHEMA_VERSION
    )
    decision_id: str = Field(..., min_length=1, max_length=220)
    decision_ref: str = Field(..., min_length=1, max_length=300)
    outcome: AgentActionOutcome
    refusal_reasons: tuple[str, ...]
    action_kind: str = Field(..., min_length=1, max_length=120)
    draft_scope: DraftActionScope | None
    case_id: str = Field(..., min_length=1, max_length=200)
    operation_id: str = Field(..., min_length=1, max_length=200)
    operation_version: str = Field(..., min_length=1, max_length=80)
    operation_content_hash: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")
    invocation_id: str = Field(..., min_length=1, max_length=240)
    invocation_content_hash: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")
    intent_content_hash: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")
    bound_resource_digest: str | None = Field(default=None, pattern=r"^sha256:[0-9a-f]{64}$")
    contract_ref: str | None = Field(default=None, pattern=r"^sha256:[0-9a-f]{64}$")
    contract_content_hash: str | None = Field(default=None, pattern=r"^sha256:[0-9a-f]{64}$")
    admission_bundle_ref: str | None = Field(default=None, pattern=r"^sha256:[0-9a-f]{64}$")
    envelope_id: str | None = None
    envelope_ref: str | None = None
    envelope_predicate_provenance: PredicateProvenance
    effect_binding_id: str | None = None
    effect_binding_digest: str | None = Field(default=None, pattern=r"^sha256:[0-9a-f]{64}$")
    effect_implementation_ref: str | None = None
    permission_snapshot: AgentActionPermissionSnapshot | None
    predicate_checks: tuple[AgentActionPredicateCheck, ...]
    human_decision_request: HumanDecisionRequest | None
    human_decision_record_ref: str | None = Field(
        default=None,
        pattern=r"^sha256:[0-9a-f]{64}$",
    )
    replay_input_refs: tuple[str, ...] = Field(..., min_length=1)
    authority_boundary: AuthorityBoundary
    rule_version_ref: str = Field(..., min_length=1, max_length=300)
    decided_at: AwareDatetime

    @model_validator(mode="after")
    def _validate_decision_shape(self) -> AgentActionAuthorityDecision:
        names = tuple(check.predicate for check in self.predicate_checks)
        if names != _PREDICATE_NAMES:
            raise ValueError("agent action decision requires the five ordered conjuncts")
        if self.outcome == "allowed":
            if self.refusal_reasons:
                raise ValueError("allowed decision cannot carry refusal reasons")
            if not all(check.satisfied for check in self.predicate_checks):
                raise ValueError("allowed decision requires all five conjuncts")
            if not self.effect_binding_id or not self.effect_binding_digest:
                raise ValueError("allowed decision requires an exact effect binding")
            if self.contract_ref is None or self.admission_bundle_ref is None:
                raise ValueError(
                    "allowed decision requires persisted owner and admission artifacts"
                )
        else:
            if not self.refusal_reasons:
                raise ValueError("refused decision requires a refusal reason")
            if self.human_decision_request is None:
                raise ValueError("refused decision requires a human decision request")
            if all(check.satisfied for check in self.predicate_checks):
                raise ValueError("refused decision requires a failed conjunct")
        return self


@dataclass(frozen=True, slots=True)
class PersistedAgentActionDecision:
    """Content-bound persistence receipt for one authority decision."""

    decision: AgentActionAuthorityDecision
    write_result: _AuthorityArtifactWriteResult
    durable_event_id: str


class AgentActionAuthorityRefused(ValueError):  # noqa: N818 - governed outcome, then raise
    """Raised after a governed refusal decision has been durably recorded."""

    def __init__(self, persisted: PersistedAgentActionDecision) -> None:
        self.decision = persisted.decision
        self.persistence_receipt = persisted.write_result
        self.durable_event_id = persisted.durable_event_id
        super().__init__(";".join(self.decision.refusal_reasons))


class AgentActionAuthorityRecordingError(RuntimeError):
    """Raised when a decision cannot be content-bound before an external effect."""


class AgentActionAuthorityOwnerResolutionError(ValueError):
    """Typed fail-closed error raised by the composition-root authority gateway."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@final
class AgentActionAuthorityGateway:
    """Server-owned artifact, replay, and effect boundary for agent actions."""

    def __init__(
        self,
        *,
        artifact_store: artifacts.FileSystemCAS,
        event_log: RuntimeDiagnosticEventLog,
        idempotency_store: RuntimeIdempotencyStore,
        artifact_verifier: artifacts.Ed25519Verifier,
        bound_permission: BoundActionPermissionVerification,
        admission_producer_identity: str,
        write_context: AgentActionAuthorityWriteContext,
        contract_refs_by_resource_digest: Mapping[str, str],
        admission_refs_by_invocation_hash: Mapping[str, str],
        effect_bindings: tuple[AgentActionEffectBinding, ...],
        human_decision_refs_by_request_ref: Mapping[str, str] | None = None,
        human_decision_service: _HumanDecisionServiceProtocol | None = None,
        human_decision_adapters_by_request_ref: Mapping[str, HumanDecisionPA2GatewayAdapterInput]
        | None = None,
    ) -> None:
        if type(artifact_store) is not artifacts.FileSystemCAS:
            raise TypeError("agent action authority requires the concrete server CAS")
        if type(event_log) is not RuntimeDiagnosticEventLog:
            raise TypeError("agent action authority requires the durable runtime event log")
        if type(idempotency_store) is not RuntimeIdempotencyStore:
            raise TypeError("agent action authority requires the server idempotency owner")
        if type(artifact_verifier) is not artifacts.Ed25519Verifier:
            raise TypeError("agent action authority requires the trusted signature verifier")
        try:
            bound_permission_hash = agent_action_permission_hash(bound_permission)
        except (TypeError, ValueError) as exc:
            raise TypeError(
                "agent action authority requires the exact DS20 request-state proof"
            ) from exc
        if not admission_producer_identity.strip():
            raise ValueError("admission producer identity must be non-empty")
        self._artifact_store = artifact_store
        self._event_log = event_log
        self._idempotency_store = idempotency_store
        self._artifact_verifier = artifact_verifier
        self._bound_permission = bound_permission
        self._bound_permission_hash = bound_permission_hash
        self._admission_producer_identity = admission_producer_identity
        self._write_context = write_context
        self._contract_refs = _frozen_ref_mapping(contract_refs_by_resource_digest)
        self._admission_refs = _frozen_ref_mapping(admission_refs_by_invocation_hash)
        self._human_decision_refs = _frozen_ref_mapping(human_decision_refs_by_request_ref or {})
        adapter_rows = dict(human_decision_adapters_by_request_ref or {})
        if adapter_rows:
            from polisyos.runtime.http.services.human_decision_contracts import (
                HumanDecisionPA2GatewayAdapterInput,
            )
            from polisyos.runtime.http.services.human_decisions import HumanDecisionService

            if type(human_decision_service) is not HumanDecisionService:
                raise TypeError("v2 human decisions require the concrete deployment resolver")
            for request_ref, adapter in adapter_rows.items():
                if (
                    type(request_ref) is not str
                    or not request_ref
                    or type(adapter) is not HumanDecisionPA2GatewayAdapterInput
                    or adapter.decision_request_ref != request_ref
                ):
                    raise TypeError("human-decision adapter mapping is not exact")
                if request_ref in self._human_decision_refs:
                    raise ValueError("human-decision request has ambiguous v1/v2 sources")
        elif human_decision_service is not None:
            from polisyos.runtime.http.services.human_decisions import HumanDecisionService

            if type(human_decision_service) is not HumanDecisionService:
                raise TypeError("human-decision service must be the concrete runtime type")
        self._human_decision_service = human_decision_service
        self._human_decision_adapters = MappingProxyType(adapter_rows)
        binding_map: dict[tuple[str, str, str], AgentActionEffectBinding] = {}
        for binding in effect_bindings:
            if type(binding) is not AgentActionEffectBinding:
                raise TypeError("effect bindings must use AgentActionEffectBinding")
            if binding.key in binding_map:
                raise ValueError(f"duplicate agent action effect binding: {binding.key!r}")
            binding_map[binding.key] = binding
        self._effect_bindings = MappingProxyType(binding_map)

    @property
    def write_context(self) -> AgentActionAuthorityWriteContext:
        """Return the immutable runtime write identity."""

        return self._write_context

    @property
    def bound_permission(self) -> BoundActionPermissionVerification:
        """Return the exact request-scoped DS20 proof installed by the composition root."""

        return self._bound_permission

    def owns_bound_permission(self, candidate: object) -> bool:
        """Check identity and frozen content against the request-scoped DS20 intake."""

        if candidate is not self._bound_permission:
            return False
        try:
            return agent_action_permission_hash(candidate) == self._bound_permission_hash
        except (TypeError, ValueError):
            return False

    def resolve_effect_binding(
        self,
        *,
        intent: AgentActionIntent,
        operation: OperationContract,
    ) -> AgentActionEffectBinding:
        """Resolve only the composition-root binding for the exact action tuple."""

        binding = self._effect_bindings.get(
            (intent.action_kind, operation.operation_id, operation.operation_version)
        )
        if binding is None or (
            intent.action_kind == "tool_call" and binding.tool_name != intent.tool_name
        ):
            raise AgentActionAuthorityOwnerResolutionError("effect_binding_missing")
        return binding

    def resolve_delegation_contract(
        self,
        resource_digest: str,
    ) -> ResolvedDelegationContract:
        """Resolve the owner-selected signed contract for one bound resource."""

        ref = self._contract_refs.get(resource_digest)
        if ref is None:
            raise AgentActionAuthorityOwnerResolutionError("delegation_contract_not_persisted")
        payload, signer_identity, event_id = self._read_signed_artifact(
            ref=ref,
            expected_kind=DELEGATION_CONTRACT_ARTIFACT_KIND,
            expected_schema_name="polisyos.runtime.DelegationContract",
            expected_schema_version=LAYER2_S7_AGENT_ACTION_DELEGATION_SCHEMA_VERSION,
            failure_prefix="delegation_contract",
            expected_signer_identity=None,
            expect_current_run=False,
        )
        try:
            contract = DelegationContract.model_validate(payload)
        except (TypeError, ValueError) as exc:
            raise AgentActionAuthorityOwnerResolutionError("delegation_contract_invalid") from exc
        if contract.mandate_owner_ref is None or signer_identity != contract.mandate_owner_ref:
            raise AgentActionAuthorityOwnerResolutionError(
                "delegation_contract_owner_signature_mismatch"
            )
        return ResolvedDelegationContract(
            contract=contract,
            contract_cas_ref=ref,
            contract_payload_hash=ref,
            resolved_for_resource_digest=resource_digest,
            signer_identity=signer_identity,
            reconciliation_event_id=event_id,
        )

    def resolve_admission_bundle(
        self,
        invocation_content_hash: str,
    ) -> tuple[AgentActionAdmissionBundle, str]:
        """Resolve one independently signed influence-admission artifact."""

        ref = self._admission_refs.get(invocation_content_hash)
        if ref is None:
            raise AgentActionAuthorityOwnerResolutionError("governed_admission_bundle_missing")
        payload, _, _ = self._read_signed_artifact(
            ref=ref,
            expected_kind=AGENT_ACTION_ADMISSION_ARTIFACT_KIND,
            expected_schema_name="polisyos.runtime.AgentActionAdmissionBundle",
            expected_schema_version=AGENT_ACTION_ADMISSION_SCHEMA_VERSION,
            failure_prefix="governed_admission_bundle",
            expected_signer_identity=self._admission_producer_identity,
            expect_current_run=True,
        )
        try:
            bundle = AgentActionAdmissionBundle.model_validate(payload)
        except (TypeError, ValueError) as exc:
            raise AgentActionAuthorityOwnerResolutionError(
                "governed_admission_bundle_invalid"
            ) from exc
        return bundle, ref

    def resolve_human_decision(
        self,
        request: HumanDecisionRequest,
        *,
        evaluated_at: datetime,
        operation: OperationContract,
        invocation: OperationInvocationRecord,
        intent: AgentActionIntent,
        bound_permission: BoundActionPermissionVerification,
        resolved_contract: ResolvedDelegationContract,
        admission: AgentActionAdmissionBundle,
        admission_ref: str,
        selected_envelope: DelegatedActionEnvelope,
        effect_binding: AgentActionEffectBinding,
    ) -> tuple[HumanDecisionRecord, str, HumanDecisionRequest] | None:
        """Resolve a signed human decision selected by the exact request binding."""

        adapter = self._human_decision_adapters.get(request.request_ref)
        if adapter is not None:
            from polisyos.runtime.http.services.human_decisions import (
                HumanDecisionOperationalResolutionError,
                _ResolvedPA2OperationalAuthority,
            )

            service = self._human_decision_service
            if service is None:  # pragma: no cover - constructor invariant
                raise AgentActionAuthorityOwnerResolutionError("DS9-DECISION-PRODUCER-MISSING")
            try:
                resolution = service.resolve_gateway_adapter(
                    adapter,
                    evaluated_at=evaluated_at,
                    operation=operation,
                    invocation=invocation,
                    intent=intent,
                    bound_permission=bound_permission,
                    resolved_contract=resolved_contract,
                    admission=admission,
                    admission_ref=admission_ref,
                    selected_envelope=selected_envelope,
                    effect_binding=effect_binding,
                )
            except HumanDecisionOperationalResolutionError as exc:
                raise AgentActionAuthorityOwnerResolutionError(exc.code) from exc
            if type(resolution) is not _ResolvedPA2OperationalAuthority:
                raise AgentActionAuthorityOwnerResolutionError("DS9-DECISION-PRODUCER-MISSING")
            return resolution.record, adapter.record_ref, resolution.request

        ref = self._human_decision_refs.get(request.request_ref)
        if ref is None:
            return None
        payload, signer_identity, _ = self._read_signed_artifact(
            ref=ref,
            expected_kind=HUMAN_DECISION_ARTIFACT_KIND,
            expected_schema_name="polisyos.runtime.HumanDecisionRecord",
            expected_schema_version=LAYER2_S7_DELEGATION_SCHEMA_VERSION,
            failure_prefix="human_decision",
            expected_signer_identity=None,
            expect_current_run=True,
        )
        try:
            record = HumanDecisionRecord.model_validate(payload)
        except (TypeError, ValueError) as exc:
            raise AgentActionAuthorityOwnerResolutionError("human_decision_record_invalid") from exc
        if record.actor_ref != signer_identity:
            raise AgentActionAuthorityOwnerResolutionError(
                "human_decision_actor_signature_mismatch"
            )
        return record, ref, request

    def begin_dispatch(self, dispatch_binding_hash: str) -> str:
        """Reserve the invocation through the existing durable idempotency owner."""

        state, _ = self._idempotency_store.begin(
            tenant_id=self._write_context.tenant_id,
            method="AGENT",
            path="/runtime/agent-action",
            idempotency_key=dispatch_binding_hash,
            request_hash=dispatch_binding_hash,
        )
        return state

    def release_dispatch(self, dispatch_binding_hash: str) -> None:
        """Release a non-effecting reservation after its refusal is persisted."""

        self._idempotency_store.fail(
            tenant_id=self._write_context.tenant_id,
            method="AGENT",
            path="/runtime/agent-action",
            idempotency_key=dispatch_binding_hash,
        )

    def complete_dispatch(
        self,
        dispatch_binding_hash: str,
        persisted: PersistedAgentActionDecision,
    ) -> None:
        """Durably consume an allowed invocation before the adapter can run."""

        self._idempotency_store.complete(
            tenant_id=self._write_context.tenant_id,
            method="AGENT",
            path="/runtime/agent-action",
            idempotency_key=dispatch_binding_hash,
            request_hash=dispatch_binding_hash,
            status_code=200,
            media_type="application/json",
            body={
                "decision_cas_ref": str(persisted.write_result.cas_ref.artifact_id),
                "decision_payload_sha256": persisted.write_result.payload_sha256,
                "effect_binding_digest": persisted.decision.effect_binding_digest,
            },
        )

    def persist_decision(
        self,
        decision: AgentActionAuthorityDecision,
    ) -> PersistedAgentActionDecision:
        """Persist and independently reconcile the exact decision bytes."""

        payload = decision.model_dump(mode="json")
        canon_spec = canon.CanonSpec()
        expected_sha = canon.content_hash(canon.to_canonical_bytes(payload, canon_spec))
        expected_ref = f"sha256:{expected_sha}"
        input_refs = tuple(
            ref
            for ref in decision.replay_input_refs
            if _is_sha256(ref) and self._artifact_store.has(ref)
        )
        try:
            result = write_runtime_authority_artifact(
                self._artifact_store,
                self._event_log,
                payload,
                _decision_write_options(input_refs),
                **self._decision_authority_fields(
                    decision=decision,
                    input_refs=input_refs,
                    canon_spec=canon_spec,
                ),
            )
            if result.payload_sha256 != expected_sha:
                raise ValueError("decision payload digest mismatch")
            if str(result.cas_ref.artifact_id) != expected_ref:
                raise ValueError("decision CAS reference mismatch")
            report = reconcile_authority_ref(
                artifact_store=self._artifact_store,
                event_log=self._event_log,
                cas_ref=expected_ref,
                expected_tenant_id=self._write_context.tenant_id,
                expected_cell_id=self._write_context.cell_id,
                expected_run_id=self._write_context.run_id,
                expected_job_id=self._write_context.job_id,
            )
            loaded = AgentActionAuthorityDecision.model_validate(
                canon.from_canonical_bytes(self._artifact_store.get_bytes(expected_ref))
            )
            if loaded != decision:
                raise ValueError("persisted decision content mismatch")
            manifest = self._artifact_store.get_manifest(expected_ref)
            schema = manifest.artifact_schema
            if (
                manifest.kind != AGENT_ACTION_DECISION_ARTIFACT_KIND
                or schema is None
                or schema.name != "polisyos.runtime.AgentActionAuthorityDecision"
                or schema.version != AGENT_ACTION_AUTHORITY_SCHEMA_VERSION
            ):
                raise ValueError("persisted decision manifest mismatch")
            if report.durable_event_id is None:
                raise ValueError("persisted decision durable event missing")
        except Exception as exc:
            raise AgentActionAuthorityRecordingError(
                "agent action authority decision was not content-bound; effect refused"
            ) from exc
        return PersistedAgentActionDecision(
            decision=decision,
            write_result=result,
            durable_event_id=report.durable_event_id,
        )

    def execute_bound_effect(
        self,
        *,
        operation: OperationContract,
        invocation: OperationInvocationRecord,
        intent: AgentActionIntent,
        persisted: PersistedAgentActionDecision,
    ) -> object:
        """Revalidate owner inputs and execute only the sealed, exact adapter binding."""

        decision = self._revalidate_persisted_decision(persisted)
        if decision.outcome != "allowed":
            raise AgentActionAuthorityRecordingError("a refusal cannot execute an effect")
        binding = self.resolve_effect_binding(intent=intent, operation=operation)
        if (
            binding.binding_id != decision.effect_binding_id
            or binding.binding_digest != decision.effect_binding_digest
            or binding.implementation_ref != decision.effect_implementation_ref
            or _exact_hash(operation) != decision.operation_content_hash
            or _exact_hash(invocation) != decision.invocation_content_hash
            or _exact_hash(intent) != decision.intent_content_hash
        ):
            raise AgentActionAuthorityRecordingError(
                "agent action effect binding changed after decision; effect refused"
            )
        if decision.bound_resource_digest is None or decision.contract_ref is None:
            raise AgentActionAuthorityRecordingError("allowed decision lost owner binding")
        resolved = self.resolve_delegation_contract(decision.bound_resource_digest)
        if resolved.contract_cas_ref != decision.contract_ref:
            raise AgentActionAuthorityRecordingError("delegation contract head changed")
        envelope = next(
            (
                row
                for row in resolved.contract.action_envelopes
                if row.envelope_id == decision.envelope_id
            ),
            None,
        )
        instant = _utcnow()
        if (
            envelope is None
            or envelope.status != "active"
            or instant < envelope.valid_from
            or instant >= envelope.valid_until
        ):
            raise AgentActionAuthorityRecordingError(
                "delegation envelope is no longer live; effect refused"
            )
        return binding.handler(invocation)

    def _revalidate_persisted_decision(
        self,
        persisted: PersistedAgentActionDecision,
    ) -> AgentActionAuthorityDecision:
        """Reload and content-bind the exact authority artifact before any effect."""

        try:
            decision_ref = str(persisted.write_result.cas_ref.artifact_id)
            payload = persisted.decision.model_dump(mode="json")
            expected_sha = canon.content_hash(canon.to_canonical_bytes(payload, canon.CanonSpec()))
            expected_ref = f"sha256:{expected_sha}"
            if (
                decision_ref != expected_ref
                or persisted.write_result.payload_sha256 != expected_sha
            ):
                raise ValueError("decision receipt is not bound to the supplied decision")
            artifact_id = artifacts.ArtifactID.model_validate(decision_ref)
            loaded = AgentActionAuthorityDecision.model_validate(
                canon.from_canonical_bytes(self._artifact_store.get_bytes(artifact_id))
            )
            if loaded != persisted.decision:
                raise ValueError("persisted decision bytes differ from the supplied decision")
            manifest = self._artifact_store.get_manifest(artifact_id)
            schema = manifest.artifact_schema
            if (
                manifest.kind != AGENT_ACTION_DECISION_ARTIFACT_KIND
                or schema is None
                or schema.name != "polisyos.runtime.AgentActionAuthorityDecision"
                or schema.version != AGENT_ACTION_AUTHORITY_SCHEMA_VERSION
                or manifest.authority is None
                or manifest.authority.payload_sha256 != expected_sha
            ):
                raise ValueError("persisted decision manifest is not authority-bound")
            report = reconcile_authority_ref(
                artifact_store=self._artifact_store,
                event_log=self._event_log,
                cas_ref=decision_ref,
                expected_tenant_id=self._write_context.tenant_id,
                expected_cell_id=self._write_context.cell_id,
                expected_run_id=self._write_context.run_id,
                expected_job_id=self._write_context.job_id,
            )
            if report.durable_event_id != persisted.durable_event_id:
                raise ValueError("decision receipt durable event changed")
        except Exception as exc:
            raise AgentActionAuthorityRecordingError(
                "agent action effect requires the exact persisted decision"
            ) from exc
        return loaded

    def _read_signed_artifact(
        self,
        *,
        ref: str,
        expected_kind: str,
        expected_schema_name: str,
        expected_schema_version: str,
        failure_prefix: str,
        expected_signer_identity: str | None,
        expect_current_run: bool,
    ) -> tuple[object, str, str]:
        try:
            artifact_id = artifacts.ArtifactID.model_validate(ref)
            report = reconcile_authority_ref(
                artifact_store=self._artifact_store,
                event_log=self._event_log,
                cas_ref=ref,
                expected_tenant_id=self._write_context.tenant_id,
                expected_cell_id=self._write_context.cell_id,
                expected_run_id=self._write_context.run_id if expect_current_run else None,
                expected_job_id=self._write_context.job_id if expect_current_run else None,
            )
            manifest = self._artifact_store.get_manifest(artifact_id)
            schema = manifest.artifact_schema
            if (
                manifest.kind != expected_kind
                or schema is None
                or schema.name != expected_schema_name
                or schema.version != expected_schema_version
            ):
                raise ValueError("artifact manifest kind or schema mismatch")
            signature = self._artifact_store.verify_signature(
                artifact_id,
                self._artifact_verifier,
                strict_identity=True,
            )
            if (
                signature.status is not artifacts.SignatureVerificationStatus.VALID
                or signature.signer_identity is None
            ):
                raise ValueError("artifact signature is not trusted")
            if (
                expected_signer_identity is not None
                and signature.signer_identity != expected_signer_identity
            ):
                raise ValueError("artifact signer identity mismatch")
            if report.durable_event_id is None:
                raise ValueError("artifact has no durable event")
            payload = canon.from_canonical_bytes(self._artifact_store.get_bytes(artifact_id))
        except Exception as exc:
            raise AgentActionAuthorityOwnerResolutionError(
                f"{failure_prefix}_authority_unverified"
            ) from exc
        return payload, signature.signer_identity, report.durable_event_id

    def _decision_authority_fields(
        self,
        *,
        decision: AgentActionAuthorityDecision,
        input_refs: tuple[str, ...],
        canon_spec: canon.CanonSpec,
    ) -> dict[str, object]:
        context = self._write_context
        closure_hash = _exact_hash(
            {
                "run_id": context.run_id,
                "job_id": context.job_id,
                "tenant_id": context.tenant_id,
                "cell_id": context.cell_id,
                "input_refs": input_refs,
            }
        )
        generated_at = decision.decided_at.isoformat()
        return {
            "evidence_id": decision.decision_id,
            "evidence_class": "authority_bearing",
            "authority_role": "producer_authority",
            "provenance_kind": "runtime_emitted",
            "owner": context.owner,
            "reader_contract": "runtime_quality.agent_action_authority.reader",
            "reader_contract_version": "1.0",
            "tenant_id": context.tenant_id,
            "cell_id": context.cell_id,
            "run_id": context.run_id,
            "job_id": context.job_id,
            "trace_id": context.trace_id,
            "span_id": context.span_id,
            "parent_span_id": context.parent_span_id,
            "requested_execution_profile": context.requested_execution_profile,
            "effective_execution_profile": context.effective_execution_profile,
            "phase": "agent_action_authority",
            "generated_at": generated_at,
            "as_of_time": generated_at,
            "same_input_closure": {
                "closure_id": f"agent-action-authority.{closure_hash[7:31]}",
                "status": "closed",
                "run_id": context.run_id,
                "job_id": context.job_id,
                "tenant_id": context.tenant_id,
                "cell_id": context.cell_id,
                "effective_mode_ref": context.effective_mode_ref,
                "degradation_ledger_ref": context.degradation_ledger_ref,
                "evidence_input_refs": input_refs,
                "closure_sha256": closure_hash,
            },
            "input_refs": input_refs,
            "effective_mode_ref": context.effective_mode_ref,
            "degradation_ledger_ref": context.degradation_ledger_ref,
            "semantic_binding_ref": decision.effect_binding_digest,
            "validation_status": "pass" if decision.outcome == "allowed" else "blocked",
            "blocking_status": "non_blocking" if decision.outcome == "allowed" else "blocking",
            "governance": GovernanceMetadata(
                classification="internal",
                authority_boundary="runtime.agent_action_dispatch",
                pii="none",
                retention_policy="runtime-quality-90d",
                review_status="runtime_verified",
                override_policy="five_rights_signed_mandate_owner_only",
                approval_policy="mandate_owner_contract_required",
            ),
            "event_id": f"evt_agent_action_{_exact_hash(decision)[7:31]}",
            "event_source": "polisyos.runtime.quality.agent_action_authority",
            "event_type": "polisyos.runtime.diagnostic.cas_write.v1",
            "event_subject": f"run/{context.run_id}/job/{context.job_id}/agent-action",
            "state_after": decision.outcome,
            "canon_spec": canon_spec,
        }


_ACTIVE_GATEWAY: ContextVar[AgentActionAuthorityGateway | None] = ContextVar(
    "polisyos_agent_action_authority_gateway",
    default=None,
)


@contextmanager
def agent_action_authority_scope(
    gateway: AgentActionAuthorityGateway,
) -> Iterator[None]:
    """Install one request-scoped server gateway as the sole owner intake."""

    if type(gateway) is not AgentActionAuthorityGateway:
        raise TypeError("agent action authority scope requires the exact server gateway")
    token = _ACTIVE_GATEWAY.set(gateway)
    try:
        yield
    finally:
        _ACTIVE_GATEWAY.reset(token)


def produce_agent_action_authority_decision(
    *,
    bound_permission: BoundActionPermissionVerification,
    operation: OperationContract,
    invocation: OperationInvocationRecord,
    intent: AgentActionIntent,
) -> AgentActionAuthorityDecision:
    """Recompute the five conjuncts from the active owner gateway without an effect."""

    gateway = _active_gateway()
    return _produce_decision(
        gateway=gateway,
        bound_permission=bound_permission,
        operation=operation,
        invocation=invocation,
        intent=intent,
        reservation_issue=None,
    )


def agent_action_content_hash(value: object) -> str:
    """Return the exact canonical hash used to bind operation, invocation, and intent."""

    return _exact_hash(value)


def agent_action_permission_hash(bound_permission: object) -> str:
    """Hash one structurally valid exact DS20 proof for owner/admission binding."""

    reasons: list[str] = []
    snapshot, _, identity_ok, permission_ok = _consume_ds20_floor(
        bound_permission,
        reasons,
    )
    if snapshot is None or not identity_ok or not permission_ok or reasons:
        raise ValueError("DS20 permission proof is not valid and granted")
    return _exact_hash(snapshot)


def dispatch_agent_external_action(
    *,
    bound_permission: BoundActionPermissionVerification,
    operation: OperationContract,
    invocation: OperationInvocationRecord,
    intent: AgentActionIntent,
) -> object:
    """Persist one decision, durably consume an allow, then run its sealed adapter."""

    gateway = _active_gateway()
    dispatch_hash = _dispatch_binding_hash(operation, invocation, intent)
    reservation_state = gateway.begin_dispatch(dispatch_hash)
    reservation_issue = (
        None if reservation_state == "started" else "agent_action_invocation_already_consumed"
    )
    completed = False
    try:
        decision = _produce_decision(
            gateway=gateway,
            bound_permission=bound_permission,
            operation=operation,
            invocation=invocation,
            intent=intent,
            reservation_issue=reservation_issue,
        )
        persisted = gateway.persist_decision(decision)
        if decision.outcome == "refused":
            if reservation_state == "started":
                gateway.release_dispatch(dispatch_hash)
            raise AgentActionAuthorityRefused(persisted)
        gateway.complete_dispatch(dispatch_hash, persisted)
        completed = True
        return gateway.execute_bound_effect(
            operation=operation,
            invocation=invocation,
            intent=intent,
            persisted=persisted,
        )
    except AgentActionAuthorityRefused:
        raise
    except Exception:
        if reservation_state == "started" and not completed:
            gateway.release_dispatch(dispatch_hash)
        raise


def _produce_decision(
    *,
    gateway: AgentActionAuthorityGateway,
    bound_permission: object,
    operation: OperationContract,
    invocation: OperationInvocationRecord,
    intent: AgentActionIntent,
    reservation_issue: str | None,
) -> AgentActionAuthorityDecision:
    instant = _utcnow()
    operation_hash = _exact_hash(operation)
    invocation_hash = _exact_hash(invocation)
    intent_hash = _exact_hash(intent)
    reasons: list[str] = []
    satisfied: dict[PredicateName, bool] = dict.fromkeys(_PREDICATE_NAMES, False)
    proof_snapshot, bound_resource, identity_ok, permission_ok = _consume_ds20_floor(
        bound_permission,
        reasons,
    )
    if not gateway.owns_bound_permission(bound_permission):
        reasons.append("verified_identity_proof_not_owner_bound")
        identity_ok = False
        permission_ok = False
    satisfied["verified_identity"] = identity_ok
    satisfied["explicit_permission"] = permission_ok
    if reservation_issue is not None:
        reasons.append(reservation_issue)
    if proof_snapshot is not None and proof_snapshot.tenant_id != gateway.write_context.tenant_id:
        reasons.append("authority_gateway_tenant_mismatch")

    validated_operation, validated_invocation, validated_intent = _validate_action_inputs(
        operation,
        invocation,
        intent,
        reasons,
    )
    operation_matches_invocation = (
        validated_invocation.operation_id == validated_operation.operation_id
        and validated_invocation.operation_version == validated_operation.operation_version
    )
    if not operation_matches_invocation:
        reasons.append("operation_invocation_mismatch")

    binding: AgentActionEffectBinding | None = None
    try:
        binding = gateway.resolve_effect_binding(
            intent=validated_intent,
            operation=validated_operation,
        )
    except AgentActionAuthorityOwnerResolutionError as exc:
        reasons.append(exc.code)

    resolved: ResolvedDelegationContract | None = None
    contract: DelegationContract | None = None
    if bound_resource is not None:
        try:
            resolved = gateway.resolve_delegation_contract(bound_resource.resource_digest)
            contract = resolved.contract
        except AgentActionAuthorityOwnerResolutionError as exc:
            reasons.append(exc.code)
    else:
        reasons.append("delegation_contract_unavailable")

    admission: AgentActionAdmissionBundle | None = None
    admission_ref: str | None = None
    try:
        admission, admission_ref = gateway.resolve_admission_bundle(invocation_hash)
    except AgentActionAuthorityOwnerResolutionError as exc:
        reasons.append(exc.code)

    if admission is not None:
        try:
            permission_proof_hash = agent_action_permission_hash(bound_permission)
        except (TypeError, ValueError):
            permission_proof_hash = None
        admission_mismatches = {
            "admission_invocation_mismatch": admission.invocation_content_hash != invocation_hash,
            "admission_operation_mismatch": admission.operation_content_hash != operation_hash,
            "admission_intent_mismatch": admission.intent_content_hash != intent_hash,
            "admission_permission_proof_mismatch": (
                permission_proof_hash is None
                or admission.permission_proof_hash != permission_proof_hash
            ),
            "admission_resource_mismatch": (
                bound_resource is None
                or admission.bound_resource_digest != bound_resource.resource_digest
            ),
            "admission_contract_mismatch": (
                resolved is None or admission.delegation_contract_ref != resolved.contract_cas_ref
            ),
            "admission_effect_binding_mismatch": (
                binding is None or admission.effect_binding_digest != binding.binding_digest
            ),
        }
        reasons.extend(code for code, failed in admission_mismatches.items() if failed)
        if memory_influence_claim_evidence_issues(admission.memory_claim_payload):
            reasons.append("memory_not_admissible_as_policy_fact")
        try:
            assert_no_candidate_authority_laundering(
                admission.authority_input_payload,
                hypothesis_ledger=admission.hypothesis_ledger,
                surface="agent_action_authority_input",
            )
        except CandidateFirewallError:
            reasons.append("input_candidate_not_admitted")
        if validated_intent.tool_name is not None and not _tool_is_admitted(
            validated_intent.tool_name,
            admission.tool_ledger,
        ):
            reasons.append("tool_admission_missing")

    caller_scope_path = _caller_controlled_scope_path(validated_invocation)
    if caller_scope_path is not None:
        reasons.append("envelope_provenance_caller_controlled")

    selected: DelegatedActionEnvelope | None = None
    if contract is not None:
        kind_rows = tuple(
            row
            for row in contract.action_envelopes
            if row.action_kind == validated_intent.action_kind
        )
        if not kind_rows:
            reasons.append("unknown_action_kind")
        else:
            operation_rows = tuple(
                row
                for row in kind_rows
                if row.operation_id == validated_operation.operation_id
                and row.operation_version == validated_operation.operation_version
            )
            if not operation_rows:
                reasons.append("operation_out_of_envelope")
                selected = next(iter(kind_rows))
            elif len(operation_rows) > 1:
                reasons.append("delegation_envelope_ambiguous")
            else:
                selected = next(iter(operation_rows))

    if selected is not None and proof_snapshot is not None and bound_resource is not None:
        if selected.required_permission.value != proof_snapshot.required_permission:
            reasons.append("explicit_permission_mismatch")
            satisfied["explicit_permission"] = False
        if selected.authorized_subject != proof_snapshot.subject:
            reasons.append("delegation_subject_mismatch")
        if selected.required_tenant_id != proof_snapshot.tenant_id:
            reasons.append("delegation_tenant_mismatch")
        if selected.required_resource_digest != bound_resource.resource_digest:
            reasons.append("delegation_resource_mismatch")
        if selected.draft_scope != validated_intent.draft_scope:
            reasons.append("draft_scope_out_of_envelope")

    mandate_blockers = {
        "delegation_contract_unavailable",
        "delegation_contract_not_persisted",
        "delegation_contract_authority_unverified",
        "delegation_contract_invalid",
        "delegation_contract_owner_signature_mismatch",
        "authority_gateway_tenant_mismatch",
        "verified_identity_proof_not_owner_bound",
        "governed_admission_bundle_missing",
        "governed_admission_bundle_authority_unverified",
        "governed_admission_bundle_invalid",
        "admission_invocation_mismatch",
        "admission_operation_mismatch",
        "admission_intent_mismatch",
        "admission_permission_proof_mismatch",
        "admission_resource_mismatch",
        "admission_contract_mismatch",
        "admission_effect_binding_mismatch",
        "effect_binding_missing",
        "envelope_provenance_caller_controlled",
        "memory_not_admissible_as_policy_fact",
        "input_candidate_not_admitted",
        "tool_admission_missing",
        "unknown_action_kind",
        "delegation_envelope_ambiguous",
        "delegation_subject_mismatch",
        "delegation_tenant_mismatch",
        "delegation_resource_mismatch",
        "draft_scope_out_of_envelope",
        "agent_action_invocation_already_consumed",
        "operation_contract_invalid",
        "operation_invocation_invalid",
        "agent_action_intent_invalid",
    }
    satisfied["mandate_bounded_delegation"] = (
        contract is not None
        and selected is not None
        and admission is not None
        and binding is not None
        and not mandate_blockers.intersection(reasons)
    )
    satisfied["operation_in_envelope"] = (
        operation_matches_invocation
        and selected is not None
        and selected.operation_id == validated_operation.operation_id
        and selected.operation_version == validated_operation.operation_version
        and "delegation_envelope_ambiguous" not in reasons
    )

    if selected is not None and proof_snapshot is not None:
        if selected.status != "active":
            reasons.append("delegation_envelope_revoked")
        if instant < selected.valid_from:
            reasons.append("delegation_envelope_not_yet_valid")
        if instant >= selected.valid_until:
            reasons.append("delegation_envelope_expired")
        if not set(proof_snapshot.roles).intersection(
            role.value for role in selected.authorized_runtime_roles
        ):
            reasons.append("delegation_runtime_role_mismatch")
        satisfied["live_accountability"] = not {
            "delegation_envelope_revoked",
            "delegation_envelope_not_yet_valid",
            "delegation_envelope_expired",
            "delegation_runtime_role_mismatch",
        }.intersection(reasons)

    request = _human_decision_request(
        contract=contract,
        invocation=validated_invocation,
        invocation_hash=invocation_hash,
        operation_hash=operation_hash,
        intent_hash=intent_hash,
        action_kind=validated_intent.action_kind,
        now=instant,
        selected_envelope=selected,
        contract_ref=resolved.contract_cas_ref if resolved is not None else None,
        resource_digest=(bound_resource.resource_digest if bound_resource is not None else None),
        effect_binding_digest=(binding.binding_digest if binding is not None else None),
    )
    decision_record_ref: str | None = None
    if (
        contract is not None
        and selected is not None
        and resolved is not None
        and admission is not None
        and admission_ref is not None
        and binding is not None
        and proof_snapshot is not None
        and "operation_out_of_envelope" in reasons
        and not (set(reasons) - {"operation_out_of_envelope"})
    ):
        try:
            human_resolution = gateway.resolve_human_decision(
                request,
                evaluated_at=instant,
                operation=validated_operation,
                invocation=validated_invocation,
                intent=validated_intent,
                bound_permission=cast(
                    "BoundActionPermissionVerification",
                    bound_permission,
                ),
                resolved_contract=resolved,
                admission=admission,
                admission_ref=admission_ref,
                selected_envelope=selected,
                effect_binding=binding,
            )
        except AgentActionAuthorityOwnerResolutionError as exc:
            reasons.append(exc.code)
        else:
            human_record = human_resolution[0] if human_resolution is not None else None
            signed_request = human_resolution[2] if human_resolution is not None else request
            human_issue = _human_override_issue(
                contract=contract,
                request=signed_request,
                record=human_record,
                now=instant,
                envelope=selected,
            )
            if human_issue is None and human_resolution is not None:
                reasons.remove("operation_out_of_envelope")
                satisfied["operation_in_envelope"] = True
                decision_record_ref = human_resolution[1]
                request = signed_request
            elif human_issue is not None and human_resolution is not None:
                reasons.append(human_issue)

    reasons = list(dict.fromkeys(reasons))
    allowed = all(satisfied.values()) and not reasons
    outcome: AgentActionOutcome = "allowed" if allowed else "refused"
    checks = _predicate_checks(satisfied, resolved)
    replay_refs = _replay_refs(
        operation_hash=operation_hash,
        invocation_hash=invocation_hash,
        intent_hash=intent_hash,
        resolved=resolved,
        admission_ref=admission_ref,
        selected=selected,
        human_decision_record_ref=decision_record_ref,
    )
    case_id = contract.case_id if contract is not None else validated_invocation.workspace_id
    decision_binding = _exact_hash(
        {
            "operation_hash": operation_hash,
            "invocation_hash": invocation_hash,
            "intent_hash": intent_hash,
            "contract_ref": resolved.contract_cas_ref if resolved is not None else None,
            "admission_ref": admission_ref,
            "effect_binding_digest": binding.binding_digest if binding is not None else None,
            "outcome": outcome,
            "reasons": reasons,
        }
    )
    return AgentActionAuthorityDecision(
        decision_id=f"agent-action-authority.{decision_binding[7:39]}",
        decision_ref=f"runtime://agent-action-authority/{decision_binding[7:]}",
        outcome=outcome,
        refusal_reasons=tuple(reasons),
        action_kind=validated_intent.action_kind,
        draft_scope=validated_intent.draft_scope,
        case_id=case_id,
        operation_id=validated_operation.operation_id,
        operation_version=validated_operation.operation_version,
        operation_content_hash=operation_hash,
        invocation_id=validated_invocation.invocation_id,
        invocation_content_hash=invocation_hash,
        intent_content_hash=intent_hash,
        bound_resource_digest=(
            bound_resource.resource_digest if bound_resource is not None else None
        ),
        contract_ref=resolved.contract_cas_ref if resolved is not None else None,
        contract_content_hash=(resolved.contract_payload_hash if resolved is not None else None),
        admission_bundle_ref=admission_ref,
        envelope_id=selected.envelope_id if selected is not None else None,
        envelope_ref=selected.envelope_ref if selected is not None else None,
        envelope_predicate_provenance="recomputed",
        effect_binding_id=binding.binding_id if binding is not None else None,
        effect_binding_digest=binding.binding_digest if binding is not None else None,
        effect_implementation_ref=binding.implementation_ref if binding is not None else None,
        permission_snapshot=proof_snapshot,
        predicate_checks=checks,
        human_decision_request=(
            request if not allowed or decision_record_ref is not None else None
        ),
        human_decision_record_ref=decision_record_ref,
        replay_input_refs=replay_refs,
        authority_boundary=_decision_authority_boundary(),
        rule_version_ref=AGENT_ACTION_AUTHORITY_RULE_VERSION,
        decided_at=instant,
    )


def _active_gateway() -> AgentActionAuthorityGateway:
    gateway = _ACTIVE_GATEWAY.get()
    if type(gateway) is not AgentActionAuthorityGateway:
        raise AgentActionAuthorityRecordingError(
            "agent action authority gateway is not installed; effect refused"
        )
    return gateway


def _consume_ds20_floor(
    bound_permission: object,
    reasons: list[str],
) -> tuple[
    AgentActionPermissionSnapshot | None,
    BoundAuthorizationResource | None,
    bool,
    bool,
]:
    from polisyos.runtime.http.authorization import (
        ActionPermissionVerification,
        BoundActionPermissionVerification,
        RouteAuthorizationRequirement,
    )
    from polisyos.runtime.http.resource_binding import (
        BindingAuthority,
        BoundAuthorizationResource,
    )

    if type(bound_permission) is not BoundActionPermissionVerification:
        reasons.append("verified_identity_proof_missing")
        return None, None, False, False
    verification = bound_permission.verification
    raw_resource = bound_permission.bound_resource
    if type(raw_resource) is not BoundAuthorizationResource:
        reasons.append("verified_identity_proof_invalid")
        return None, None, False, False
    resource = raw_resource
    try:
        shape_valid = (
            type(verification) is ActionPermissionVerification
            and type(verification.requirement) is RouteAuthorizationRequirement
            and resource.requirement == verification.requirement
            and isinstance(verification.requirement.permission, RuntimePermission)
            and isinstance(resource.authority, BindingAuthority)
            and isinstance(verification.subject, str)
            and bool(verification.subject.strip())
            and isinstance(verification.tenant_id, str)
            and bool(verification.tenant_id.strip())
            and isinstance(verification.jwt_id, str)
            and bool(verification.jwt_id.strip())
            and isinstance(verification.authorization_source, str)
            and bool(verification.authorization_source.strip())
            and type(verification.roles) is frozenset
            and bool(verification.roles)
            and all(isinstance(role, PolicyOSRole) for role in verification.roles)
            and type(verification.granted_permissions) is tuple
            and all(
                isinstance(permission, RuntimePermission)
                for permission in verification.granted_permissions
            )
            and isinstance(resource.resource_digest, str)
            and _is_sha256(resource.resource_digest)
            and isinstance(resource.body_sha256, str)
            and _is_sha256(resource.body_sha256)
            and isinstance(resource.query_sha256, str)
            and _is_sha256(resource.query_sha256)
        )
    except Exception:
        shape_valid = False
    if not shape_valid:
        reasons.append("verified_identity_proof_invalid")
        return None, None, False, False
    if resource.tenant_id is not None and resource.tenant_id != verification.tenant_id:
        reasons.append("bound_resource_tenant_mismatch")
        return None, resource, False, False
    required_permission = verification.requirement.permission
    permission_ok = required_permission in verification.granted_permissions
    if not permission_ok:
        reasons.append("explicit_permission_missing")
    snapshot = AgentActionPermissionSnapshot(
        subject=verification.subject,
        tenant_id=verification.tenant_id,
        jwt_id=verification.jwt_id,
        roles=tuple(sorted(role.value for role in verification.roles)),
        authorization_source=verification.authorization_source,
        required_permission=required_permission.value,
        granted_permissions=tuple(
            sorted(permission.value for permission in verification.granted_permissions)
        ),
        resource_digest=resource.resource_digest,
        resource_kind=resource.resource_kind,
        resource_authority=resource.authority.value,
        body_sha256=resource.body_sha256,
        query_sha256=resource.query_sha256,
    )
    return snapshot, resource, True, permission_ok


def _validate_action_inputs(
    operation: OperationContract,
    invocation: OperationInvocationRecord,
    intent: AgentActionIntent,
    reasons: list[str],
) -> tuple[OperationContract, OperationInvocationRecord, AgentActionIntent]:
    try:
        validated_operation = OperationContract.model_validate(operation.model_dump(mode="python"))
    except (AttributeError, TypeError, ValueError):
        reasons.append("operation_contract_invalid")
        validated_operation = operation
    try:
        validated_invocation = OperationInvocationRecord.model_validate(
            invocation.model_dump(mode="python")
        )
    except (AttributeError, TypeError, ValueError):
        reasons.append("operation_invocation_invalid")
        validated_invocation = invocation
    try:
        validated_intent = AgentActionIntent.model_validate(intent.model_dump(mode="python"))
    except (AttributeError, TypeError, ValueError):
        reasons.append("agent_action_intent_invalid")
        validated_intent = intent
    return validated_operation, validated_invocation, validated_intent


def _caller_controlled_scope_path(invocation: OperationInvocationRecord) -> str | None:
    for root, payload in (
        ("parameters", invocation.parameters),
        ("selected_by", invocation.selected_by),
        ("internal_trace", invocation.internal_trace),
    ):
        path = _scope_path(payload, root)
        if path is not None:
            return path
    return None


def _scope_path(value: object, path: str) -> str | None:
    if isinstance(value, Mapping):
        for raw_key, nested in value.items():
            key = str(raw_key).strip().casefold().replace("-", "_")
            nested_path = f"{path}.{raw_key}"
            if "envelope" in key or key in _AUTHORITY_SCOPE_KEY_PARTS or key.endswith("_scope"):
                return nested_path
            found = _scope_path(nested, nested_path)
            if found is not None:
                return found
        return None
    if isinstance(value, list | tuple | set):
        for index, nested in enumerate(value):
            found = _scope_path(nested, f"{path}[{index}]")
            if found is not None:
                return found
        return None
    if isinstance(value, str):
        normalized = value.casefold().replace("-", "_")
        if any(marker.replace("-", "_") in normalized for marker in _AUTHORITY_SCOPE_VALUE_MARKERS):
            return path
    return None


def _tool_is_admitted(tool_name: str, ledger: object) -> bool:
    if type(ledger) is not ModelAssistedStepLedger:
        return False
    if tool_name not in ledger.tool_allowlist:
        return False
    calls = [call for call in ledger.tool_call_refs if call.tool_name == tool_name]
    return bool(calls) and all(call.status == "pass" for call in calls)


def _human_decision_request(
    *,
    contract: DelegationContract | None,
    invocation: OperationInvocationRecord,
    invocation_hash: str,
    operation_hash: str,
    intent_hash: str,
    action_kind: str,
    now: datetime,
    selected_envelope: DelegatedActionEnvelope | None,
    contract_ref: str | None,
    resource_digest: str | None,
    effect_binding_digest: str | None,
) -> HumanDecisionRequest:
    binding_hash = _exact_hash(
        {
            "invocation_hash": invocation_hash,
            "operation_hash": operation_hash,
            "intent_hash": intent_hash,
            "contract_ref": contract_ref,
            "resource_digest": resource_digest,
            "envelope_ref": selected_envelope.envelope_ref if selected_envelope else None,
            "valid_from": selected_envelope.valid_from if selected_envelope else None,
            "valid_until": selected_envelope.valid_until if selected_envelope else None,
            "effect_binding_digest": effect_binding_digest,
        }
    )
    request_id = f"agent-action.{action_kind}.{binding_hash[7:31]}"[:120]
    request_ref = f"runtime://agent-action-authority/requests/{binding_hash[7:]}"
    decidable_until = (
        selected_envelope.valid_until
        if selected_envelope is not None and selected_envelope.valid_until > now
        else now
    )
    provenance = [
        invocation_hash,
        operation_hash,
        intent_hash,
        *(
            [contract_ref, resource_digest, effect_binding_digest]
            if contract_ref and resource_digest and effect_binding_digest
            else []
        ),
    ]
    if contract is not None:
        base = build_human_decision_request(
            case_id=contract.case_id,
            contract=contract,
            decision_class_id="mandate_boundary",
            need_reasons=["out_of_envelope"],
            voi_rank=1,
            s6_mandate_record_ref=contract.s6_mandate_record_ref,
            s6_mandate_firewall_disposition=contract.s6_mandate_firewall_disposition,
            rule_version_ref=contract.rule_version_ref,
        )
        return base.model_copy(
            update={
                "request_id": request_id,
                "request_ref": request_ref,
                "requested_at": now,
                "decision_due_at": decidable_until,
                "decidable_until": decidable_until,
                "provenance_refs": list(dict.fromkeys(provenance)),
            }
        )
    return HumanDecisionRequest(
        request_id=request_id,
        request_ref=request_ref,
        case_id=invocation.workspace_id,
        delegation_contract_ref="runtime://delegation-contract/unresolved",
        decision_rights_matrix_ref="runtime://decision-rights/unresolved",
        decision_class_id="mandate_boundary",
        required_role="mandate_owner",
        interaction_mode="request_driven",
        disposition="request_human_decision",
        need_reasons=["out_of_envelope"],
        requested_at=now,
        decision_due_at=now,
        decidable_until=now,
        decision_options=[
            DecisionOption(
                option_id="escalate",
                action="escalate",
                label="Escalate",
                consequence="No action occurs until mandate authority is resolved.",
            )
        ],
        provenance_refs=list(dict.fromkeys(provenance)),
        material_limitations=["Delegation contract could not be resolved."],
        value_stakes_impact="An external agent action is blocked pending accountable review.",
        what_changes_under_each_choice=["Escalation preserves zero external effects."],
        five_rights_requirements=FiveRightsRequirement(
            right_decision=f"Decide whether to authorize {action_kind}.",
            right_person="mandate_owner",
            right_information="Identity, permission, operation, envelope, and refusal reasons.",
            right_format_channel="governed_review",
            right_time="Before any external effect.",
        ),
        five_rights_binding=HumanDecisionFiveRightsBinding(
            decision_class_id="mandate_boundary",
            decision_rights_matrix_ref="runtime://decision-rights/unresolved",
            required_role="mandate_owner",
            required_information_refs=(),
            required_channel="governed_review",
            required_representation="full",
            time_rule="intersection_of_signed_validity_intervals_pre_action",
        ),
        available_actions=["escalate"],
        attention_cost_rank=1,
        voi_rank=1,
        s6_mandate_record_ref="runtime://mandate/unresolved",
        s6_mandate_firewall_disposition="block",
        authority_boundary=AuthorityBoundary(
            authoritative_for=["human_decision_routing"],
            may_not_use_for=_DECISION_MAY_NOT_USE_FOR,
            source_authority="deterministic_producer",
            posture="shadow",
            rule_version_refs=[AGENT_ACTION_AUTHORITY_RULE_VERSION],
        ),
        rule_version_ref=AGENT_ACTION_AUTHORITY_RULE_VERSION,
    )


def _human_override_issue(
    *,
    contract: DelegationContract,
    request: HumanDecisionRequest,
    record: HumanDecisionRecord | None,
    now: datetime,
    envelope: DelegatedActionEnvelope,
) -> str | None:
    if record is None:
        return "human_decision_record_missing"
    if record.human_decision_request_ref != request.request_ref:
        return "human_decision_request_mismatch"
    if record.case_id != contract.case_id:
        return "human_decision_case_mismatch"
    if record.actor_ref != contract.mandate_owner_ref or record.actor_role != request.required_role:
        return "human_decision_wrong_role"
    if record.decision_action_exercised != "approve" or not record.active_choice:
        return "human_decision_not_approved"
    if not record.five_rights_check.all_pass():
        return "human_decision_five_rights_failed"
    if record.responsibility_integrity.status != "pass":
        return "human_decision_integrity_failed"
    if record.schema_version != HUMAN_DECISION_RECORD_V2:
        return "DS9-DECISION-V1-REVALIDATION"
    if record.rule_version_ref != contract.rule_version_ref:
        return "human_decision_rule_version_mismatch"
    if record.mandate_record_ref != contract.s6_mandate_record_ref:
        return "human_decision_mandate_mismatch"
    boundary = record.authority_boundary
    if (
        boundary.source_authority != "human_governance"
        or boundary.posture not in {"governed", "production"}
        or "human_decision_act" not in boundary.authoritative_for
    ):
        return "human_decision_authority_boundary_invalid"
    if request.request_ref not in record.provenance_refs:
        return "human_decision_request_provenance_missing"
    if (
        record.decided_at < envelope.valid_from
        or record.decided_at < request.requested_at
        or record.decided_at > now
        or record.decided_at > envelope.valid_until
    ):
        return "human_decision_outside_ttl"
    if request.decidable_until is None or record.decided_at > request.decidable_until:
        return "human_decision_outside_ttl"
    return None


def _predicate_checks(
    satisfied: Mapping[PredicateName, bool],
    resolved: ResolvedDelegationContract | None,
) -> tuple[AgentActionPredicateCheck, ...]:
    reasons = {
        "verified_identity": "Exact DS20 bound identity proof is structurally valid.",
        "explicit_permission": "The exact DS20 permission equals the owner envelope permission.",
        "mandate_bounded_delegation": "Signed owner and admission artifacts bound the action.",
        "operation_in_envelope": (
            "Operation and invocation match one owner envelope or exact override."
        ),
        "live_accountability": "The envelope is active, in TTL, and role-accountable.",
    }
    return tuple(
        AgentActionPredicateCheck(
            predicate=name,
            satisfied=satisfied[name],
            provenance=(
                resolved.predicate_provenance
                if name == "mandate_bounded_delegation" and resolved is not None
                else "recomputed"
            ),
            reason=reasons[name],
        )
        for name in _PREDICATE_NAMES
    )


def _replay_refs(
    *,
    operation_hash: str,
    invocation_hash: str,
    intent_hash: str,
    resolved: ResolvedDelegationContract | None,
    admission_ref: str | None,
    selected: DelegatedActionEnvelope | None,
    human_decision_record_ref: str | None,
) -> tuple[str, ...]:
    refs = [operation_hash, invocation_hash, intent_hash]
    if resolved is not None:
        refs.extend((resolved.contract_cas_ref, resolved.reconciliation_event_id))
    if admission_ref is not None:
        refs.append(admission_ref)
    if selected is not None:
        refs.extend((selected.envelope_ref, selected.issuance_decision_ref))
    if human_decision_record_ref is not None:
        refs.append(human_decision_record_ref)
    return tuple(dict.fromkeys(refs))


def _decision_authority_boundary() -> AuthorityBoundary:
    return AuthorityBoundary(
        authoritative_for=["agent_action_dispatch_decision"],
        may_not_use_for=_DECISION_MAY_NOT_USE_FOR,
        source_authority="deterministic_producer",
        posture="governed",
        rule_version_refs=[AGENT_ACTION_AUTHORITY_RULE_VERSION],
    )


def _decision_write_options(
    input_refs: tuple[str, ...],
) -> artifacts.ArtifactWriteOptions:
    return artifacts.ArtifactWriteOptions(
        kind=AGENT_ACTION_DECISION_ARTIFACT_KIND,
        media_type="application/json",
        schema=artifacts.SchemaInfo(
            name="polisyos.runtime.AgentActionAuthorityDecision",
            version=AGENT_ACTION_AUTHORITY_SCHEMA_VERSION,
        ),
        producer=artifacts.ProducerInfo(
            component="polisyos.runtime.quality.agent_action_authority",
            version="2026.08.19+gy-pa2",
        ),
        governance=artifacts.ArtifactGovernanceInfo(classification="internal"),
        inputs=[
            artifacts.InputRef(
                artifact_id=artifacts.ArtifactID.model_validate(ref),
                role="authority_input",
            )
            for ref in input_refs
        ],
    )


def _frozen_ref_mapping(values: Mapping[str, str]) -> Mapping[str, str]:
    copied: dict[str, str] = {}
    for key, ref in values.items():
        if not isinstance(key, str) or not key.strip():
            raise ValueError("authority gateway mapping keys must be non-empty")
        if not isinstance(ref, str) or not _is_sha256(ref):
            raise ValueError("authority gateway mappings require CAS refs")
        copied[key] = ref
    return MappingProxyType(copied)


def _dispatch_binding_hash(
    operation: OperationContract,
    invocation: OperationInvocationRecord,
    intent: AgentActionIntent,
) -> str:
    return _exact_hash(
        {
            "operation": _exact_hash(operation),
            "invocation": _exact_hash(invocation),
            "intent": _exact_hash(intent),
        }
    )


def _exact_hash(value: object) -> str:
    payload = value.model_dump(mode="json") if isinstance(value, BaseModel) else value
    canonical = canon.to_canonical_bytes(
        payload,
        canon.CanonSpec(forbid_floats=False),
    )
    return f"sha256:{canon.content_hash(canonical)}"


def _is_sha256(value: str) -> bool:
    return bool(_SHA256_PATTERN.fullmatch(value))


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("agent action authority decision time must be timezone-aware")
    return value.astimezone(UTC)


def _utcnow() -> datetime:
    """Read the producer-owned live clock for protected action decisions."""

    return datetime.now(UTC)


__all__ = [
    "AGENT_ACTION_ADMISSION_ARTIFACT_KIND",
    "AGENT_ACTION_ADMISSION_SCHEMA_VERSION",
    "AGENT_ACTION_AUTHORITY_RULE_VERSION",
    "AGENT_ACTION_AUTHORITY_SCHEMA_VERSION",
    "AGENT_ACTION_DECISION_ARTIFACT_KIND",
    "DELEGATION_CONTRACT_ARTIFACT_KIND",
    "HUMAN_DECISION_ARTIFACT_KIND",
    "AgentActionAdmissionBundle",
    "AgentActionAuthorityDecision",
    "AgentActionAuthorityGateway",
    "AgentActionAuthorityRecordingError",
    "AgentActionAuthorityRefused",
    "AgentActionAuthorityWriteContext",
    "AgentActionEffectBinding",
    "AgentActionIntent",
    "AgentActionPermissionSnapshot",
    "AgentActionPredicateCheck",
    "DraftActionScope",
    "PersistedAgentActionDecision",
    "ResolvedDelegationContract",
    "agent_action_authority_scope",
    "agent_action_content_hash",
    "agent_action_permission_hash",
    "dispatch_agent_external_action",
    "produce_agent_action_authority_decision",
]
