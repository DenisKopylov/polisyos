"""Durable anytime-valid confidence accounting for the N9 promotion gate.

The ledger is deliberately narrower than a statistics library.  It binds a
data-registered instrument to a code-owned mathematical kernel, allocates risk
from a predictable schedule before an owner is called, and persists every
transition as an immutable CAS event.  A single locked head pointer is the only
mutable state.  Deterministic owner proofs are independently recomputed and
spend zero risk; statistical families without a repository-owned theorem
verifier fail closed.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import sysconfig
import threading
import tomllib
from collections.abc import Callable, Iterable, Mapping
from contextlib import contextmanager
from fractions import Fraction
from pathlib import Path
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.core import artifacts, canon
from polisyos.fabric.io.atomic import atomic_write_json
from polisyos.pdc import PromotionObligationClass

CONFIDENCE_LEDGER_REGISTRY_SCHEMA_VERSION = "policyos.runtime.confidence_ledger.registry.v1"
CONFIDENCE_LEDGER_SCHEMA_VERSION = "policyos.runtime.confidence_ledger.v1"
CONDITIONAL_VALIDITY_CLAUSE = (
    "P(false promotion | maintained assumptions) <= delta is conditional on obligation "
    "completeness + validator soundness (the spec's A4 = our open P29)."
)
GOOD_EVENT_CLAUSE = (
    "Omega_delta is the intersection of the good events for executed probabilistic "
    "checks; the union bound is used without an independence claim."
)
DEFAULT_REGISTRY_RELATIVE_PATH = Path("architecture/production_quality/confidence_ledger.toml")

_MAINTAINED_ASSUMPTIONS = ("obligation_completeness", "validator_soundness")
_DISPLAY_DECIMAL_PLACES = 48
# 355/113 is a certified upper bound for pi.  This is therefore a conservative
# exact rational lower bound for 6/pi^2.  Decimal strings are display-only.
_BASEL_COEFFICIENT_LOWER = Fraction(6 * 113 * 113, 355 * 355)
_SUPPORTED_SCHEDULE_KERNELS = frozenset({"basel_square_v1"})
_SUPPORTED_PROOF_KERNELS = frozenset(
    {
        "closed_constant_unit_e_process_v1",
        "deterministic_owner_v1",
        "ineligible_v1",
        "owner_theorem_unavailable_v1",
    }
)
_SUPPORTED_OWNER_VERIFIER_KERNELS = frozenset(
    {
        "n10_route_projection_recompute_v1",
        "n13b_passport_revalidate_v1",
    }
)

type ClaimPolarity = Literal[
    "false_accept",
    "confident_wrong_refusal",
    "confident_wrong_admission",
    "conformance_only",
]
type CertificateRole = Literal[
    "promotion",
    "promotion_conformance",
    "refusal",
    "acquisition",
    "admission",
]
type SessionAuthorityProvenance = Literal["canonical_repo", "verification"]
type ExecutionStatus = Literal["prepared", "started", "executed", "refused", "unexecuted"]
type CompletionOutcome = Literal[
    "prepared",
    "started",
    "supported",
    "not_supported",
    "preflight_refusal",
    "cancelled",
    "owner_refused",
    "owner_error",
    "recovered_crash",
    "refused",
]

_ROLE_POLARITY: dict[str, ClaimPolarity] = {
    "promotion": "false_accept",
    "promotion_conformance": "conformance_only",
    "refusal": "confident_wrong_refusal",
    "acquisition": "confident_wrong_refusal",
    "admission": "confident_wrong_admission",
}
_CAS_CANON_SPEC = canon.CanonSpec(exclude_none=False)
_LEDGER_PRODUCER = artifacts.ProducerInfo(
    component="polisyos.runtime.quality.confidence_ledger",
    version="1.0.0",
)
_REGISTRY_SCHEMA = artifacts.SchemaInfo(
    name="polisyos.runtime.confidence-ledger-registry", version="1.0.0"
)
_SCOPE_ANCHOR_SCHEMA = artifacts.SchemaInfo(
    name="polisyos.runtime.confidence-ledger-scope-anchor", version="1.0.0"
)
_ROOT_SCHEMA = artifacts.SchemaInfo(name="polisyos.runtime.confidence-ledger-root", version="1.0.0")
_EVENT_SCHEMA = artifacts.SchemaInfo(
    name="polisyos.runtime.confidence-ledger-event", version="1.0.0"
)
_RECEIPT_SCHEMA = artifacts.SchemaInfo(
    name="polisyos.runtime.confidence-ledger-receipt", version="1.0.0"
)
_DEPLOYMENT_DRIFT_POISON_SCHEMA = artifacts.SchemaInfo(
    name="polisyos.runtime.confidence-ledger-deployment-drift-poison",
    version="1.0.0",
)

try:  # pragma: no cover - POSIX is the authority-bearing backend.
    import fcntl as _fcntl
except ImportError:  # pragma: no cover
    _fcntl = None

_LOCKS_GUARD = threading.Lock()
_PATH_LOCKS: dict[Path, threading.RLock] = {}
_INVOCATION_LOCKS_GUARD = threading.Lock()
_INVOCATION_LOCKS: dict[Path, threading.Lock] = {}


class _StrictModel(BaseModel):
    """Strict immutable base for public confidence-ledger contracts."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class ConfidenceLedgerError(ValueError):
    """Typed fail-closed confidence-ledger error."""

    def __init__(self, code: str, detail: str | None = None) -> None:
        self.code = code
        self.detail = detail or code
        super().__init__(f"{code}: {self.detail}")


class RationalSpec(_StrictModel):
    """Exact non-negative rational value."""

    numerator: int = Field(ge=0)
    denominator: int = Field(gt=0)

    @property
    def fraction(self) -> Fraction:
        """Return the exact represented fraction."""

        return Fraction(self.numerator, self.denominator)


class ConfidenceRiskBudgetScope(_StrictModel):
    """Stable owner scope for one non-resettable risk budget."""

    scope_owner_ref: str = Field(min_length=1)
    authority_purpose: str = Field(min_length=1)
    owner_scope_key: str = Field(min_length=1)
    owner_projection_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    epoch_ref: str | None
    model_ref: str | None
    rule_ref: str | None
    schema_ref: str | None

    @property
    def scope_id(self) -> str:
        """Return the stable key; mutable owner content is a root binding."""

        return _identity(
            "confidence-risk-scope",
            {
                "scope_owner_ref": self.scope_owner_ref,
                "authority_purpose": self.authority_purpose,
                "owner_scope_key": self.owner_scope_key,
                "epoch_ref": self.epoch_ref,
            },
        )


class PredictableClaimSpec(_StrictModel):
    """Claim facts fixed before the check outcome is observed."""

    claim_ref: str = Field(min_length=1)
    null_ref: str = Field(min_length=1)
    claim_scope_ref: str = Field(min_length=1)
    data_window_ref: str = Field(min_length=1)
    certificate_role: CertificateRole
    claim_polarity: ClaimPolarity

    @model_validator(mode="after")
    def _role_matches_protected_error(self) -> Self:
        if _ROLE_POLARITY[self.certificate_role] != self.claim_polarity:
            raise ValueError("certificate_role_polarity_mismatch")
        return self


class ConfidenceLedgerHistoryToken(_StrictModel):
    """Canonical F_(t-1) token used for predictable preparation."""

    scope_id: str = Field(pattern=r"^confidence-risk-scope:sha256:[0-9a-f]{64}$")
    ledger_root_id: str = Field(pattern=r"^confidence-ledger-root:sha256:[0-9a-f]{64}$")
    ledger_root_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    head_event_id: str = Field(
        pattern=r"^(?:confidence-event|confidence-ledger-root):sha256:[0-9a-f]{64}$"
    )
    head_event_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    revision: int = Field(ge=0)
    next_execution_ordinal: int = Field(ge=0)
    filtration_ref: str = Field(min_length=1)
    precheck_history_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class ConfidenceLedgerPolicy(_StrictModel):
    """Top-level delta policy and exact conditionality statement."""

    delta: RationalSpec
    default_schedule_profile_id: str = Field(min_length=1)
    conditionality_clause: str = Field(min_length=1)

    @model_validator(mode="after")
    def _is_safe(self) -> Self:
        if self.conditionality_clause != CONDITIONAL_VALIDITY_CLAUSE:
            raise ValueError("conditionality_clause_missing")
        if self.delta.fraction > 1:
            raise ValueError("delta_must_not_exceed_one")
        return self


class PredictableScheduleProfile(_StrictModel):
    """Data-selected schedule backed by a known symbolic kernel."""

    profile_id: str = Field(min_length=1)
    proof_kernel_id: str = Field(min_length=1)
    mass: RationalSpec

    @model_validator(mode="after")
    def _mass_is_safe(self) -> Self:
        if self.mass.fraction > 1:
            raise ValueError("schedule_total_mass_above_one")
        return self


class ObligationBudgetPool(_StrictModel):
    """Exact delta pool over the N9 obligation taxonomy."""

    pool_id: str = Field(min_length=1)
    weight: RationalSpec
    obligation_classes: tuple[PromotionObligationClass, ...] = Field(min_length=1)


class InstrumentProofProfile(_StrictModel):
    """Registered selection of a code-owned proof kernel."""

    profile_id: str = Field(min_length=1)
    proof_kernel_id: str = Field(min_length=1)
    guarantee_kind: str = Field(min_length=1)
    deterministic: bool
    anytime_valid: bool
    permits_obligation_satisfaction: bool
    refusal_code: str | None = Field(default=None, min_length=1)


class InstrumentDefinition(_StrictModel):
    """Data-registered instrument definition; IDs are not engine enums."""

    instrument_id: str = Field(min_length=1)
    instrument_family: str = Field(min_length=1)
    proof_profile_id: str = Field(min_length=1)
    certificate_roles: tuple[CertificateRole, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _roles_are_unique(self) -> Self:
        if len(self.certificate_roles) != len(set(self.certificate_roles)):
            raise ValueError("duplicate_certificate_role")
        return self


class CertificateClassRoute(_StrictModel):
    """Data-only evidence-class route to code-owned owner verification."""

    certificate_class: str = Field(min_length=1)
    instrument_id: str = Field(min_length=1)
    obligation_class: PromotionObligationClass
    certificate_role: CertificateRole
    claim_polarity: ClaimPolarity
    owner_ref: str = Field(min_length=1)
    verifier_kernel_id: str = Field(min_length=1)
    verifier_ref: str = Field(min_length=1)

    @model_validator(mode="after")
    def _is_semantically_bound(self) -> Self:
        if _ROLE_POLARITY[self.certificate_role] != self.claim_polarity:
            raise ValueError("certificate_role_polarity_mismatch")
        if self.owner_ref == self.verifier_ref:
            raise ValueError("owner_and_verifier_must_be_distinct")
        return self


class ConfidenceLedgerRegistry(_StrictModel):
    """Strict registry and complete N9 delta partition."""

    schema_version: Literal[CONFIDENCE_LEDGER_REGISTRY_SCHEMA_VERSION]
    policy: ConfidenceLedgerPolicy
    schedule_profiles: tuple[PredictableScheduleProfile, ...] = Field(min_length=1)
    obligation_pools: tuple[ObligationBudgetPool, ...] = Field(min_length=1)
    proof_profiles: tuple[InstrumentProofProfile, ...] = Field(min_length=1)
    instruments: tuple[InstrumentDefinition, ...] = Field(min_length=1)
    certificate_class_routes: tuple[CertificateClassRoute, ...] = ()

    @model_validator(mode="after")
    def _is_total_and_resolvable(self) -> Self:
        _require_unique(
            (item.profile_id for item in self.schedule_profiles),
            "duplicate_schedule_profile",
        )
        schedules = {item.profile_id: item for item in self.schedule_profiles}
        if self.policy.default_schedule_profile_id not in schedules:
            raise ValueError("default_schedule_profile_missing")
        if any(
            item.proof_kernel_id not in _SUPPORTED_SCHEDULE_KERNELS
            for item in self.schedule_profiles
        ):
            raise ValueError("unknown_schedule_proof_kernel")
        _require_unique((item.pool_id for item in self.obligation_pools), "duplicate_pool")
        members = [item for pool in self.obligation_pools for item in pool.obligation_classes]
        if len(members) != len(set(members)):
            raise ValueError("duplicate_obligation_class")
        if set(members) != set(PromotionObligationClass):
            raise ValueError("obligation_partition_not_total")
        if sum((pool.weight.fraction for pool in self.obligation_pools), Fraction()) != 1:
            raise ValueError("obligation_pool_weights_do_not_sum_to_one")
        _require_unique(
            (item.profile_id for item in self.proof_profiles),
            "duplicate_proof_profile",
        )
        profiles = {item.profile_id: item for item in self.proof_profiles}
        if any(
            item.proof_kernel_id not in _SUPPORTED_PROOF_KERNELS for item in self.proof_profiles
        ):
            raise ValueError("unknown_instrument_proof_kernel")
        for profile in self.proof_profiles:
            _validate_proof_profile_contract(profile)
        _require_unique((item.instrument_id for item in self.instruments), "duplicate_instrument")
        if any(item.proof_profile_id not in profiles for item in self.instruments):
            raise ValueError("instrument_proof_profile_missing")
        _require_unique(
            (item.certificate_class for item in self.certificate_class_routes),
            "duplicate_certificate_class_route",
        )
        instrument_ids = {item.instrument_id for item in self.instruments}
        if any(item.instrument_id not in instrument_ids for item in self.certificate_class_routes):
            raise ValueError("certificate_class_instrument_missing")
        instrument_by_id = {item.instrument_id: item for item in self.instruments}
        if any(
            item.certificate_role not in instrument_by_id[item.instrument_id].certificate_roles
            for item in self.certificate_class_routes
        ):
            raise ValueError("certificate_class_role_not_permitted")
        if any(
            item.verifier_kernel_id not in _SUPPORTED_OWNER_VERIFIER_KERNELS
            for item in self.certificate_class_routes
        ):
            raise ValueError("unknown_owner_verifier_kernel")
        return self

    @property
    def content_hash(self) -> str:
        """Return the content identity of all registry data."""

        return _content_hash(self.source_payload())

    @property
    def obligation_weights(self) -> dict[PromotionObligationClass, Fraction]:
        """Expand the seven configured pools over N9's typed denominator."""

        result: dict[PromotionObligationClass, Fraction] = {}
        for pool in self.obligation_pools:
            weight = pool.weight.fraction / len(pool.obligation_classes)
            result.update(dict.fromkeys(pool.obligation_classes, weight))
        return result

    def source_payload(self) -> dict[str, Any]:
        """Return canonical source-shaped registry data."""

        return self.model_dump(mode="json")

    def resolve_schedule(self, profile_id: str | None = None) -> PredictableScheduleProfile:
        """Resolve exactly one schedule profile."""

        selected = profile_id or self.policy.default_schedule_profile_id
        matches = [item for item in self.schedule_profiles if item.profile_id == selected]
        if len(matches) != 1:
            raise ConfidenceLedgerError("schedule_profile_missing", selected)
        return matches[0]

    def resolve_instrument(self, instrument_id: str) -> InstrumentDefinition:
        """Resolve an instrument or fail closed."""

        matches = [item for item in self.instruments if item.instrument_id == instrument_id]
        if len(matches) != 1:
            raise ConfidenceLedgerError("unknown_instrument", instrument_id)
        return matches[0]

    def resolve_proof_profile(self, profile_id: str) -> InstrumentProofProfile:
        """Resolve one profile referenced by an instrument."""

        matches = [item for item in self.proof_profiles if item.profile_id == profile_id]
        if len(matches) != 1:
            raise ConfidenceLedgerError("registry_binding_invalid", profile_id)
        return matches[0]

    def resolve_certificate_route(self, certificate_class: str) -> CertificateClassRoute:
        """Resolve the complete registered route for a real evidence class."""

        matches = [
            item
            for item in self.certificate_class_routes
            if item.certificate_class == certificate_class
        ]
        if len(matches) != 1:
            raise ConfidenceLedgerError("certificate_class_route_missing", certificate_class)
        return matches[0]


class OwnerCertificateEvidence(_StrictModel):
    """Narrow owner projection resolved afresh by certificate reference."""

    certificate_ref: str = Field(min_length=1)
    instrument_id: str = Field(min_length=1)
    obligation_class: PromotionObligationClass
    certificate_role: CertificateRole
    claim_polarity: ClaimPolarity
    owner_ref: str = Field(min_length=1)
    owner_projection: dict[str, Any]
    certificate_class: str | None = Field(default=None, min_length=1)
    claim_execution_binding_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _is_structural(self) -> Self:
        if _ROLE_POLARITY[self.certificate_role] != self.claim_polarity:
            raise ValueError("certificate_role_polarity_mismatch")
        _canonical_json(self.owner_projection)
        return self


class OwnerCertificateVerification(_StrictModel):
    """Independent structural-verifier result."""

    verifier_ref: str = Field(min_length=1)
    verifier_projection: dict[str, Any]
    certificate_evidence_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    claim_execution_binding_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    supports_obligation: bool

    @model_validator(mode="after")
    def _projection_is_canonical(self) -> Self:
        _canonical_json(self.verifier_projection)
        return self


class OwnerCertificateBinding(_StrictModel):
    """Content binding to independently recomputed owner/verifier projections."""

    certificate_ref: str = Field(min_length=1)
    certificate_class: str = Field(min_length=1)
    certificate_route_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    owner_ref: str = Field(min_length=1)
    owner_projection_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    verifier_ref: str = Field(min_length=1)
    verifier_kernel_id: str = Field(min_length=1)
    verifier_projection_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    certificate_evidence_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    verification_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class OwnerInvocationLockIdentity(_StrictModel):
    """Stable process/OS lock identity for exactly one owner execution."""

    nonce: str = Field(pattern=r"^confidence-owner-invocation-lock:sha256:[0-9a-f]{64}$")
    device: int = Field(ge=0)
    inode: int = Field(gt=0)


class ConfidenceLedgerRoot(_StrictModel):
    """Immutable CAS root binding a scope to exactly one risk policy."""

    schema_version: Literal[CONFIDENCE_LEDGER_SCHEMA_VERSION]
    risk_scope: ConfidenceRiskBudgetScope
    scope_id: str = Field(pattern=r"^confidence-risk-scope:sha256:[0-9a-f]{64}$")
    scope_anchor_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    authority_provenance: SessionAuthorityProvenance
    deployment_identity: str = Field(pattern=r"^policy-engine-deployment:sha256:[0-9a-f]{64}$")
    registry_artifact_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    registry_content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    schedule_profile_id: str = Field(min_length=1)
    schedule_profile_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    schedule_projection_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    obligation_split_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    budget_delta: RationalSpec
    conditionality_clause: Literal[CONDITIONAL_VALIDITY_CLAUSE]
    maintained_assumptions: tuple[Literal["obligation_completeness", "validator_soundness"], ...]
    ledger_root_id: str = Field(pattern=r"^confidence-ledger-root:sha256:[0-9a-f]{64}$")


class ConfidenceLedgerCheck(_StrictModel):
    """Current state of one immutable request binding."""

    schema_version: Literal[CONFIDENCE_LEDGER_SCHEMA_VERSION]
    scope_id: str = Field(pattern=r"^confidence-risk-scope:sha256:[0-9a-f]{64}$")
    request_key: str = Field(min_length=1)
    request_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    obligation_class: PromotionObligationClass
    instrument_id: str = Field(min_length=1)
    instrument_family: str = Field(min_length=1)
    proof_profile_id: str = Field(min_length=1)
    certificate_ref: str = Field(min_length=1)
    certificate_class: str | None = Field(default=None, min_length=1)
    certificate_route_hash: str | None = Field(default=None, pattern=r"^sha256:[0-9a-f]{64}$")
    certificate_role: CertificateRole
    claim_polarity: ClaimPolarity
    claim_ref: str = Field(min_length=1)
    null_ref: str = Field(min_length=1)
    claim_scope_ref: str = Field(min_length=1)
    data_window_ref: str = Field(min_length=1)
    filtration_ref: str = Field(min_length=1)
    precheck_history_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    registry_content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    instrument_definition_hash: str | None = Field(default=None, pattern=r"^sha256:[0-9a-f]{64}$")
    proof_profile_hash: str | None = Field(default=None, pattern=r"^sha256:[0-9a-f]{64}$")
    prepared_event_id: str = Field(pattern=r"^confidence-event:sha256:[0-9a-f]{64}$")
    started_event_id: str | None = Field(
        default=None, pattern=r"^confidence-event:sha256:[0-9a-f]{64}$"
    )
    event_id: str = Field(pattern=r"^confidence-event:sha256:[0-9a-f]{64}$")
    check_id: str = Field(pattern=r"^confidence-check:sha256:[0-9a-f]{64}$")
    execution_status: ExecutionStatus
    outcome: CompletionOutcome
    execution_ordinal: int | None = Field(default=None, ge=0)
    schedule_query_index: int | None = Field(default=None, ge=0)
    execution_id: str | None = Field(
        default=None, pattern=r"^confidence-execution:sha256:[0-9a-f]{64}$"
    )
    owner_invocation_claim_id: str | None = Field(
        default=None,
        pattern=r"^confidence-owner-invocation:sha256:[0-9a-f]{64}$",
    )
    owner_invocation_lock_identity: OwnerInvocationLockIdentity | None = None
    deterministic_proof: bool
    anytime_valid: bool
    spend: RationalSpec
    spend_decimal: str = Field(pattern=r"^(0|[0-9]+(?:\.[0-9]+)?)$")
    supports_obligation: bool
    eligible_for_promotion: bool
    refusal_code: str | None = Field(default=None, min_length=1)
    proof_detail: str = Field(min_length=1)
    good_event_id: str | None = Field(
        default=None, pattern=r"^confidence-good-event:sha256:[0-9a-f]{64}$"
    )
    owner_binding: OwnerCertificateBinding | None
    claim_execution_binding_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _state_is_coherent(self) -> Self:
        if _ROLE_POLARITY[self.certificate_role] != self.claim_polarity:
            raise ValueError("certificate_role_polarity_mismatch")
        paired = (self.execution_ordinal is None, self.execution_id is None)
        if paired[0] != paired[1]:
            raise ValueError("execution_identity_incomplete")
        if self.started_event_id is None and self.execution_ordinal is not None:
            raise ValueError("unstarted_execution_identity")
        if self.owner_invocation_claim_id is not None and self.execution_id is None:
            raise ValueError("owner_invocation_claim_without_execution")
        if (self.execution_id is None) != (self.owner_invocation_lock_identity is None):
            raise ValueError("owner_invocation_lock_identity_incomplete")
        if (
            self.outcome
            in {
                "supported",
                "not_supported",
                "owner_refused",
                "owner_error",
                "refused",
            }
            and self.owner_invocation_claim_id is None
        ):
            raise ValueError("owner_invocation_claim_missing")
        if self.execution_status in {"prepared", "refused", "unexecuted"} and (
            self.started_event_id is None and self.spend.fraction != 0
        ):
            raise ValueError("spend_for_unexecuted_check")
        if self.deterministic_proof and self.spend.fraction != 0:
            raise ValueError("deterministic_proof_nonzero_spend")
        if self.eligible_for_promotion and not (
            self.execution_status == "executed"
            and self.outcome == "supported"
            and self.anytime_valid
            and self.supports_obligation
            and self.certificate_role == "promotion"
            and self.claim_polarity == "false_accept"
        ):
            raise ValueError("ineligible_check_marked_promotable")
        return self


class ConfidenceLedgerEvent(_StrictModel):
    """One immutable event-chain transition exposed in a receipt."""

    schema_version: Literal[CONFIDENCE_LEDGER_SCHEMA_VERSION]
    event_type: Literal["prepared", "started", "completed"]
    scope_id: str
    ledger_root_id: str
    revision: int = Field(gt=0)
    parent_event_id: str
    parent_event_ref: str
    event_id: str = Field(pattern=r"^confidence-event:sha256:[0-9a-f]{64}$")
    event_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    check: ConfidenceLedgerCheck


class _StoredLedgerEvent(_StrictModel):
    """CAS payload; its artifact reference is supplied by the manifest."""

    schema_version: Literal[CONFIDENCE_LEDGER_SCHEMA_VERSION]
    event_type: Literal["prepared", "started", "completed"]
    scope_id: str
    ledger_root_id: str
    revision: int = Field(gt=0)
    parent_event_id: str
    parent_event_ref: str
    event_id: str = Field(pattern=r"^confidence-event:sha256:[0-9a-f]{64}$")
    check: ConfidenceLedgerCheck


class _LedgerHead(_StrictModel):
    """The one atomically replaced mutable pointer for a scope."""

    schema_version: Literal[CONFIDENCE_LEDGER_SCHEMA_VERSION]
    scope_id: str
    scope_anchor_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    authority_provenance: SessionAuthorityProvenance
    ledger_root_id: str
    ledger_root_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    head_event_id: str
    head_event_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    revision: int = Field(ge=0)


class _ScopeJournalRecord(_StrictModel):
    """One hash-chained WAL record for a scope-local CAS artifact."""

    schema_version: Literal[CONFIDENCE_LEDGER_SCHEMA_VERSION]
    scope_id: str = Field(pattern=r"^confidence-risk-scope:sha256:[0-9a-f]{64}$")
    revision: int = Field(gt=0)
    previous_record_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    record_type: Literal["intent", "commit"]
    artifact_kind: Literal["event", "receipt", "deployment_drift_poison"]
    artifact_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    payload: dict[str, Any] | None
    record_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class _DeploymentDriftPoison(_StrictModel):
    """Irreversible same-scope denial after canonical deployment drift."""

    schema_version: Literal[CONFIDENCE_LEDGER_SCHEMA_VERSION]
    scope_id: str = Field(pattern=r"^confidence-risk-scope:sha256:[0-9a-f]{64}$")
    authority_provenance: Literal["canonical_repo"]
    expected_deployment_identity: str = Field(
        pattern=r"^policy-engine-deployment:sha256:[0-9a-f]{64}$"
    )
    observed_deployment_identity: str = Field(
        pattern=r"^policy-engine-deployment:sha256:[0-9a-f]{64}$"
    )
    reason: Literal["canonical_deployment_identity_changed"]
    poison_id: str = Field(pattern=r"^confidence-deployment-drift-poison:sha256:[0-9a-f]{64}$")


class ConfidenceLedgerReceipt(_StrictModel):
    """Canonical recomputation of the current durable event-chain head."""

    schema_version: Literal[CONFIDENCE_LEDGER_SCHEMA_VERSION]
    scope_id: str = Field(pattern=r"^confidence-risk-scope:sha256:[0-9a-f]{64}$")
    scope_anchor_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    authority_provenance: SessionAuthorityProvenance
    deployment_identity: str = Field(pattern=r"^policy-engine-deployment:sha256:[0-9a-f]{64}$")
    ledger_root_id: str = Field(pattern=r"^confidence-ledger-root:sha256:[0-9a-f]{64}$")
    ledger_root_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    head_event_id: str
    head_event_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    registry_artifact_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    registry_content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    schedule_profile_id: str = Field(min_length=1)
    schedule_profile_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    schedule_projection_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    budget_delta: RationalSpec
    budget_delta_decimal: str
    events: tuple[ConfidenceLedgerEvent, ...]
    checks: tuple[ConfidenceLedgerCheck, ...]
    total_spend: RationalSpec
    total_spend_decimal: str
    within_budget: bool
    good_event_clause: Literal[GOOD_EVENT_CLAUSE]
    conditionality_clause: Literal[CONDITIONAL_VALIDITY_CLAUSE]
    maintained_assumptions: tuple[Literal["obligation_completeness", "validator_soundness"], ...]
    receipt_id: str = Field(pattern=r"^confidence-ledger:sha256:[0-9a-f]{64}$")


class N9PromotionLedgerRow(_StrictModel):
    """Typed promotion-claim row; other certificate roles are not projected."""

    obligation_class: PromotionObligationClass
    instrument_id: str
    instrument_family: str
    certificate_ref: str
    certificate_role: Literal["promotion"]
    claim_polarity: Literal["false_accept"]
    check_id: str
    execution_status: ExecutionStatus
    outcome: CompletionOutcome
    execution_ordinal: int | None
    execution_id: str | None
    spend: RationalSpec
    spend_decimal: str
    anytime_valid: bool
    supports_obligation: bool
    eligible_for_promotion: bool
    claim_execution_binding_hash: str


class N9PromotionCertificateProjection(_StrictModel):
    """Narrow current-head projection consumed by N9."""

    schema_version: Literal[CONFIDENCE_LEDGER_SCHEMA_VERSION]
    projection_scope: Literal["n9_promotion_certificate"]
    authority_provenance: SessionAuthorityProvenance
    deployment_identity: str = Field(pattern=r"^policy-engine-deployment:sha256:[0-9a-f]{64}$")
    risk_scope: ConfidenceRiskBudgetScope
    scope_id: str
    ledger_root_id: str
    ledger_root_ref: str
    head_event_id: str
    head_event_ref: str
    ledger_receipt_id: str
    ledger_receipt_ref: str
    registry_content_hash: str
    schedule_projection_hash: str
    promotion_rows: tuple[N9PromotionLedgerRow, ...]
    total_spend: RationalSpec
    total_spend_decimal: str
    budget_delta: RationalSpec
    budget_delta_decimal: str
    within_budget: bool
    good_event_clause: Literal[GOOD_EVENT_CLAUSE]
    conditionality_clause: Literal[CONDITIONAL_VALIDITY_CLAUSE]
    maintained_assumptions: tuple[Literal["obligation_completeness", "validator_soundness"], ...]
    projection_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class N12EpochReferenceProjection(_StrictModel):
    """Future N12 locator projection without implementing epochs."""

    schema_version: Literal[CONFIDENCE_LEDGER_SCHEMA_VERSION]
    projection_scope: Literal["n12_epoch_reference"]
    authority_provenance: SessionAuthorityProvenance
    deployment_identity: str = Field(pattern=r"^policy-engine-deployment:sha256:[0-9a-f]{64}$")
    scope_id: str
    ledger_root_id: str
    ledger_root_ref: str
    head_event_id: str
    head_event_ref: str
    ledger_receipt_id: str
    ledger_receipt_ref: str
    epoch_ref: str | None
    model_ref: str | None
    rule_ref: str | None
    schema_ref: str | None
    validity: Literal["epoch_not_implemented"]
    conditionality_clause: Literal[CONDITIONAL_VALIDITY_CLAUSE]
    maintained_assumptions: tuple[Literal["obligation_completeness", "validator_soundness"], ...]
    projection_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


CertificateResolver = Callable[[ConfidenceLedgerCheck], OwnerCertificateEvidence]
CertificateVerifier = Callable[[OwnerCertificateEvidence], OwnerCertificateVerification]


class ConfidenceLedgerSession:
    """Durable resolve-bind-verify session for one risk-budget scope."""

    __slots__ = (
        "_artifact_store",
        "_authority_provenance",
        "_authority_repo_root",
        "_cas_reconciled",
        "_certificate_resolver",
        "_certificate_verifier",
        "_deployment_identity",
        "_execution_claims",
        "_execution_claims_lock",
        "_head_path",
        "_journal_offset",
        "_journal_path",
        "_journal_records",
        "_lock_path",
        "_registry",
        "_risk_scope",
        "_schedule",
        "_scope_tombstone_path",
        "_session_sealed",
        "_state_root",
    )
    _IMMUTABLE_PROVENANCE_FIELDS = frozenset(
        {
            "_registry",
            "_risk_scope",
            "_schedule",
            "_artifact_store",
            "_state_root",
            "_certificate_resolver",
            "_certificate_verifier",
            "_authority_provenance",
            "_authority_repo_root",
            "_deployment_identity",
            "_head_path",
            "_journal_path",
            "_lock_path",
            "_scope_tombstone_path",
            "_is_authority_session",
        }
    )

    def __init_subclass__(cls, **kwargs: object) -> None:
        del kwargs
        raise TypeError("confidence_ledger_session_is_final")

    def __setattr__(self, name: str, value: object) -> None:
        if getattr(self, "_session_sealed", False) and (name in self._IMMUTABLE_PROVENANCE_FIELDS):
            raise AttributeError("session_authority_provenance_immutable")
        object.__setattr__(self, name, value)

    def __init__(
        self,
        *,
        registry: ConfidenceLedgerRegistry,
        risk_scope: ConfidenceRiskBudgetScope,
        schedule_profile_id: str | None,
        artifact_store: artifacts.FileSystemCAS,
        state_root: Path,
        certificate_resolver: CertificateResolver | None,
        certificate_verifier: CertificateVerifier | None,
    ) -> None:
        self._initialize(
            registry=registry,
            risk_scope=risk_scope,
            schedule_profile_id=schedule_profile_id,
            artifact_store=artifact_store,
            state_root=state_root,
            certificate_resolver=certificate_resolver,
            certificate_verifier=certificate_verifier,
            authority_provenance="verification",
            authority_repo_root=None,
            deployment_identity=_policy_engine_deployment_identity(_loaded_policy_engine_root()),
        )

    def _initialize(
        self,
        *,
        registry: ConfidenceLedgerRegistry,
        risk_scope: ConfidenceRiskBudgetScope,
        schedule_profile_id: str | None,
        artifact_store: artifacts.FileSystemCAS,
        state_root: Path,
        certificate_resolver: CertificateResolver | None,
        certificate_verifier: CertificateVerifier | None,
        authority_provenance: SessionAuthorityProvenance,
        authority_repo_root: Path | None,
        deployment_identity: str,
    ) -> None:
        object.__setattr__(self, "_session_sealed", False)
        self._registry = registry
        self._risk_scope = risk_scope
        self._schedule = registry.resolve_schedule(schedule_profile_id)
        self._artifact_store = artifact_store
        self._state_root = Path(state_root).resolve()
        self._certificate_resolver = certificate_resolver
        self._certificate_verifier = certificate_verifier
        self._authority_provenance = authority_provenance
        self._authority_repo_root = authority_repo_root
        self._deployment_identity = deployment_identity
        self._cas_reconciled = False
        self._execution_claims: set[str] = set()
        self._execution_claims_lock = threading.Lock()
        self._state_root.mkdir(parents=True, exist_ok=True)
        scope_hex = risk_scope.scope_id.rsplit(":", 1)[-1]
        self._head_path = self._state_root / f"{scope_hex}.head.json"
        self._lock_path = self._state_root / f"{scope_hex}.lock"
        self._journal_path = self._state_root / f"{scope_hex}.append.wal"
        self._journal_offset = 0
        self._journal_records: list[_ScopeJournalRecord] = []
        self._scope_tombstone_path = self._state_root / f"{scope_hex}.scope.json"
        self._initialize_or_validate_root()
        object.__setattr__(self, "_session_sealed", True)

    @classmethod
    def from_repo(
        cls,
        repo_root: str | Path,
        *,
        risk_scope: ConfidenceRiskBudgetScope,
        schedule_profile_id: str | None = None,
    ) -> ConfidenceLedgerSession:
        """Open the sole authority-bearing durable session for ``risk_scope``."""

        root = Path(repo_root).resolve()
        loaded_root = _loaded_policy_engine_root()
        if root != loaded_root:
            raise ConfidenceLedgerError("canonical_deployment_identity_invalid")
        deployment_identity = _policy_engine_deployment_identity(root)
        registry = load_confidence_ledger_registry(root / DEFAULT_REGISTRY_RELATIVE_PATH)
        session = object.__new__(cls)
        session._initialize(
            registry=registry,
            risk_scope=risk_scope,
            schedule_profile_id=schedule_profile_id,
            artifact_store=artifacts.FileSystemCAS(root / ".polisyos/cas"),
            state_root=root / ".polisyos/runtime/confidence_ledger",
            certificate_resolver=None,
            certificate_verifier=None,
            authority_provenance="canonical_repo",
            authority_repo_root=root,
            deployment_identity=deployment_identity,
        )
        return session

    @classmethod
    def _for_verification(
        cls,
        repo_root: str | Path,
        *,
        risk_scope: ConfidenceRiskBudgetScope,
        artifact_store: artifacts.FileSystemCAS,
        state_root: str | Path,
        certificate_resolver: CertificateResolver | None = None,
        certificate_verifier: CertificateVerifier | None = None,
        schedule_profile_id: str | None = None,
        registry_source: object | None = None,
    ) -> ConfidenceLedgerSession:
        """Open an isolated non-authority session for tests and frozen recomputation."""

        root = Path(repo_root).resolve()
        source = (
            root / DEFAULT_REGISTRY_RELATIVE_PATH if registry_source is None else registry_source
        )
        return cls(
            registry=load_confidence_ledger_registry(source),
            risk_scope=risk_scope,
            schedule_profile_id=schedule_profile_id,
            artifact_store=artifact_store,
            state_root=Path(state_root),
            certificate_resolver=certificate_resolver,
            certificate_verifier=certificate_verifier,
        )

    @property
    def risk_scope(self) -> ConfidenceRiskBudgetScope:
        """Return the bound owner risk scope."""

        return self._risk_scope

    @property
    def registry(self) -> ConfidenceLedgerRegistry:
        """Return the content-bound registry."""

        return self._registry

    @property
    def is_authority_session(self) -> bool:
        """Return whether this session owns the canonical promotion-risk namespace."""

        root = self._authority_repo_root
        return bool(
            type(self) is ConfidenceLedgerSession
            and self._authority_provenance == "canonical_repo"
            and root is not None
            and self._certificate_resolver is None
            and self._certificate_verifier is None
            and self._state_root == root / ".polisyos/runtime/confidence_ledger"
            and self._artifact_store.root == root / ".polisyos/cas"
            and root == _loaded_policy_engine_root()
            and self._deployment_identity == _policy_engine_deployment_identity(root)
        )

    @property
    def authority_provenance(self) -> SessionAuthorityProvenance:
        """Return the immutable origin of this ledger namespace."""

        return self._authority_provenance

    def observe_history(self) -> ConfidenceLedgerHistoryToken:
        """Observe the canonical head used for the next predictable claim."""

        with self._exclusive_lock():
            head, root, events = self._load_state_locked()
            return self._history_token(head, root, events)

    def prepare_check(
        self,
        *,
        history_token: ConfidenceLedgerHistoryToken,
        request_key: str,
        obligation_class: PromotionObligationClass,
        instrument_id: str,
        certificate_ref: str,
        certificate_class: str | None = None,
        claim: PredictableClaimSpec,
    ) -> ConfidenceLedgerCheck:
        """Bind a check before its outcome; preflight refusals spend zero."""

        try:
            obligation = PromotionObligationClass(obligation_class)
        except ValueError as exc:
            raise ConfidenceLedgerError("unknown_obligation_class", str(obligation_class)) from exc
        request_payload = {
            "request_key": request_key,
            "obligation_class": obligation,
            "instrument_id": instrument_id,
            "certificate_ref": certificate_ref,
            "certificate_class": certificate_class,
            "claim": claim,
        }
        fingerprint = _content_hash(request_payload)
        with self._exclusive_lock():
            head, root, events = self._load_state_locked()
            current_token = self._history_token(head, root, events)
            if history_token != current_token:
                raise ConfidenceLedgerError("ledger_head_conflict")
            current = _current_checks(events)
            if request_key in current:
                existing = current[request_key]
                if existing.request_fingerprint != fingerprint:
                    raise ConfidenceLedgerError("idempotency_binding_mismatch", request_key)
                return existing
            instrument: InstrumentDefinition | None = None
            profile: InstrumentProofProfile | None = None
            route: CertificateClassRoute | None = None
            refusal: str | None = None
            try:
                instrument = self._registry.resolve_instrument(instrument_id)
                profile = self._registry.resolve_proof_profile(instrument.proof_profile_id)
                refusal = _instrument_preflight_refusal(
                    instrument=instrument,
                    profile=profile,
                    certificate_role=claim.certificate_role,
                )
                if refusal is None and (profile.deterministic or certificate_class is not None):
                    if certificate_class is None:
                        raise ConfidenceLedgerError("certificate_class_route_missing")
                    route = self._registry.resolve_certificate_route(certificate_class)
                    if (
                        route.instrument_id != instrument_id
                        or route.obligation_class != obligation
                        or route.certificate_role != claim.certificate_role
                        or route.claim_polarity != claim.claim_polarity
                    ):
                        raise ConfidenceLedgerError("certificate_class_route_mismatch")
            except ConfidenceLedgerError as exc:
                refusal = exc.code
            event_type: Literal["prepared", "completed"] = (
                "completed" if refusal is not None else "prepared"
            )
            check = self._base_check(
                head=head,
                history_token=history_token,
                request_key=request_key,
                fingerprint=fingerprint,
                obligation=obligation,
                instrument_id=instrument_id,
                certificate_ref=certificate_ref,
                certificate_class=certificate_class,
                certificate_route_hash=_content_hash(route) if route else None,
                claim=claim,
                instrument=instrument,
                profile=profile,
                execution_status="refused" if refusal else "prepared",
                outcome="preflight_refusal" if refusal else "prepared",
                refusal_code=refusal,
                proof_detail=(
                    f"preflight refused: {refusal}"
                    if refusal
                    else "claim and instrument bound before outcome"
                ),
            )
            appended = self._append_event_locked(
                head=head,
                root=root,
                event_type=event_type,
                check=check,
            )
            if refusal is not None:
                raise ConfidenceLedgerError(refusal, instrument_id)
            return appended.check

    def start_check(self, prepared: ConfidenceLedgerCheck) -> ConfidenceLedgerCheck:
        """Atomically assign an ordinal and burn risk before calling an owner."""

        with self._exclusive_lock():
            head, root, events = self._load_state_locked()
            current = _current_checks(events).get(prepared.request_key)
            if current is None or current.request_fingerprint != prepared.request_fingerprint:
                raise ConfidenceLedgerError("prepared_check_not_canonical")
            if current.outcome not in {"prepared", "started"}:
                return current
            if current.outcome == "started":
                raise ConfidenceLedgerError("duplicate_execution_conflict")
            if (
                head.head_event_id != current.prepared_event_id
                or current.event_id != current.prepared_event_id
            ):
                raise ConfidenceLedgerError("ledger_head_conflict")
            ordinals = [
                item.execution_ordinal
                for item in _current_checks(events).values()
                if item.execution_ordinal is not None
            ]
            ordinal = max(ordinals, default=-1) + 1
            schedule_index = ordinal
            profile = self._registry.resolve_proof_profile(current.proof_profile_id)
            spend = Fraction()
            if not profile.deterministic:
                spend = _schedule_alpha(
                    delta=self._registry.policy.delta.fraction,
                    obligation_weight=self._registry.obligation_weights[current.obligation_class],
                    query_index=schedule_index,
                    schedule=self._schedule,
                )
            prior_spend = sum(
                (item.spend.fraction for item in _current_checks(events).values()),
                Fraction(),
            )
            if prior_spend + spend > self._registry.policy.delta.fraction:
                raise ConfidenceLedgerError("over_spend")
            execution_id = _identity(
                "confidence-execution",
                {
                    "scope_id": root.scope_id,
                    "ordinal": ordinal,
                    "request_fingerprint": current.request_fingerprint,
                    "schedule_query_index": schedule_index,
                },
            )
            binding_hash = _claim_execution_binding_hash(
                check=current,
                execution_id=execution_id,
                execution_ordinal=ordinal,
                schedule_query_index=schedule_index,
                spend=spend,
            )
            invocation_lock_identity = self._create_owner_invocation_lock_locked(
                execution_id=execution_id,
                request_fingerprint=current.request_fingerprint,
            )
            started = current.model_copy(
                update={
                    "execution_status": "started",
                    "outcome": "started",
                    "execution_ordinal": ordinal,
                    "schedule_query_index": schedule_index,
                    "execution_id": execution_id,
                    "owner_invocation_lock_identity": invocation_lock_identity,
                    "spend": _rational_spec(spend),
                    "spend_decimal": _fraction_display(spend),
                    "claim_execution_binding_hash": binding_hash,
                    "proof_detail": "risk burned before owner execution",
                }
            )
            appended = self._append_event_locked(
                head=head, root=root, event_type="started", check=started
            )
            if appended.check.execution_id is None:  # pragma: no cover - strict model invariant.
                raise ConfidenceLedgerError("execution_identity_missing")
            with self._execution_claims_lock:
                self._execution_claims.add(appended.check.execution_id)
            return appended.check

    def execute_check(self, offered: ConfidenceLedgerCheck) -> ConfidenceLedgerCheck:
        """Execute a prepared check through its code-owned proof kernel."""

        if offered.outcome not in {"prepared", "started"}:
            return offered
        started = offered if offered.outcome == "started" else self.start_check(offered)
        if started.outcome != "started":
            return started
        with self._owner_invocation_lock(started, blocking=True):
            claimed = self._claim_owner_invocation(started)
            return self._execute_claimed_check(claimed)

    def _execute_claimed_check(self, claimed: ConfidenceLedgerCheck) -> ConfidenceLedgerCheck:
        """Run a proof kernel while the caller holds the invocation locks."""

        if claimed.outcome != "started":
            return claimed
        profile = self._registry.resolve_proof_profile(claimed.proof_profile_id)
        if profile.proof_kernel_id == "closed_constant_unit_e_process_v1":
            return self._complete(
                claimed,
                outcome="not_supported",
                supports_obligation=False,
                eligible_for_promotion=False,
                proof_detail=("closed e-process E_t=1 is anytime-valid but cannot reject any null"),
            )
        if profile.proof_kernel_id == "deterministic_owner_v1":
            try:
                binding, supports = self._resolve_bind_verify_owner(claimed)
            except ConfidenceLedgerError as exc:
                return self._complete(
                    claimed,
                    outcome="refused",
                    supports_obligation=False,
                    eligible_for_promotion=False,
                    refusal_code=exc.code,
                    proof_detail="deterministic owner evidence did not reverify",
                )
            except (ValueError, TypeError, KeyError):
                return self._complete(
                    claimed,
                    outcome="refused",
                    supports_obligation=False,
                    eligible_for_promotion=False,
                    refusal_code="owner_reverification_failed",
                    proof_detail="deterministic owner evidence did not reverify",
                )
            eligible = bool(
                supports
                and claimed.certificate_role == "promotion"
                and claimed.claim_polarity == "false_accept"
            )
            return self._complete(
                claimed,
                outcome="supported" if supports else "not_supported",
                supports_obligation=supports,
                eligible_for_promotion=eligible,
                proof_detail="deterministic owner projection independently recomputed",
                owner_binding=binding,
            )
        return self._complete(
            claimed,
            outcome="refused",
            supports_obligation=False,
            eligible_for_promotion=False,
            refusal_code="unknown_proof_theorem",
            proof_detail="no code-owned proof kernel can authorize this instrument",
        )

    def cancel_prepared(
        self, prepared: ConfidenceLedgerCheck, *, detail: str = "cancelled before start"
    ) -> ConfidenceLedgerCheck:
        """Cancel an unstarted check without an ordinal or spend."""

        return self._complete_unstarted(
            prepared,
            outcome="cancelled",
            proof_detail=detail,
        )

    def record_owner_failure(
        self,
        started: ConfidenceLedgerCheck,
        *,
        outcome: Literal["owner_refused", "owner_error"],
        code: str,
        detail: str,
    ) -> ConfidenceLedgerCheck:
        """Record an owner failure without refunding an already burned slot."""

        with self._owner_invocation_lock(started, blocking=True):
            claimed = self._claim_owner_invocation(started)
            return self._complete(
                claimed,
                outcome=outcome,
                supports_obligation=False,
                eligible_for_promotion=False,
                refusal_code=code,
                proof_detail=detail,
            )

    def recover_started(self, started: ConfidenceLedgerCheck) -> ConfidenceLedgerCheck:
        """Close a crash-open start without re-executing or refunding it."""

        with self._owner_invocation_lock(started, blocking=False), self._exclusive_lock():
            head, root, events = self._load_state_locked()
            current = _current_checks(events).get(started.request_key)
            if current is None or current.request_fingerprint != started.request_fingerprint:
                raise ConfidenceLedgerError("started_check_not_canonical")
            if current.outcome != "started":
                return current
            return self._complete_locked(
                head=head,
                root=root,
                events=events,
                current=current,
                outcome="recovered_crash",
                supports_obligation=False,
                eligible_for_promotion=False,
                refusal_code="started_check_recovered_without_reexecution",
                proof_detail="crash-open execution retained its full burn",
            )

    def _claim_owner_invocation(
        self,
        offered: ConfidenceLedgerCheck,
    ) -> ConfidenceLedgerCheck:
        """Durably elect the only process permitted to invoke one started owner."""

        with self._exclusive_lock():
            head, root, events = self._load_state_locked()
            current = _current_checks(events).get(offered.request_key)
            if current is None or current.request_fingerprint != offered.request_fingerprint:
                raise ConfidenceLedgerError("started_check_not_canonical")
            if current.outcome != "started":
                return current
            if current.owner_invocation_claim_id is not None:
                raise ConfidenceLedgerError("duplicate_execution_conflict")
            if current.execution_id is None:
                raise ConfidenceLedgerError("execution_identity_missing")
            with self._execution_claims_lock:
                if current.execution_id not in self._execution_claims:
                    raise ConfidenceLedgerError("duplicate_execution_conflict")
            claim_id = _identity(
                "confidence-owner-invocation",
                {
                    "scope_id": current.scope_id,
                    "execution_id": current.execution_id,
                    "request_fingerprint": current.request_fingerprint,
                    "lock_identity": current.owner_invocation_lock_identity,
                },
            )
            claimed = current.model_copy(
                update={
                    "owner_invocation_claim_id": claim_id,
                    "proof_detail": "owner invocation durably claimed",
                }
            )
            claimed_event = self._append_event_locked(
                head=head,
                root=root,
                event_type="started",
                check=claimed,
            ).check
            with self._execution_claims_lock:
                self._execution_claims.discard(current.execution_id)
            return claimed_event

    def receipt(self) -> ConfidenceLedgerReceipt:
        """Recompute the canonical receipt from the current immutable chain."""

        with self._exclusive_lock():
            head, root, events = self._load_state_locked()
            return self._build_receipt(head, root, events)

    def persist_receipt(self, receipt: ConfidenceLedgerReceipt) -> str:
        """Persist a validated receipt and return its CAS locator."""

        validated = validate_confidence_ledger_receipt(receipt, session=self)
        with self._exclusive_lock():
            head, root, events = self._load_state_locked()
            if validated != self._build_receipt(head, root, events):
                raise ConfidenceLedgerError("receipt_not_canonical_head")
            ref = self._journaled_put_json_locked(
                validated.model_dump(mode="json"),
                artifact_kind="receipt",
            )
            return str(ref.artifact_id)

    def _initialize_or_validate_root(self) -> None:
        with self._exclusive_lock():
            self._ensure_scope_journal_locked()
            anchor_payload = self._scope_anchor_payload()
            expected_anchor_ref = _cas_json_artifact_ref(anchor_payload)
            expected_registry_ref = _cas_json_artifact_ref(self._registry.source_payload())
            expected_root = self._expected_root_binding(expected_registry_ref)
            expected_root_ref = _cas_json_artifact_ref(expected_root)
            obvious_scope = (
                self._head_path.exists()
                or self._scope_tombstone_path.exists()
                or self._artifact_store.has(expected_anchor_ref)
                or self._artifact_store.has(expected_root_ref)
            )
            prior_scope_exists = False if obvious_scope else self._prior_scope_artifact_exists()
            existing_scope = obvious_scope or prior_scope_exists
            if existing_scope:
                if not self._scope_tombstone_path.exists() or not self._artifact_store.has(
                    expected_anchor_ref
                ):
                    raise ConfidenceLedgerError("ledger_head_reset_detected")
                if (
                    not self._artifact_store.has(expected_root_ref)
                    and self._scope_root_artifact_exists()
                ):
                    raise ConfidenceLedgerError("ledger_scope_binding_mismatch")
                if not self._artifact_store.has(expected_root_ref):
                    raise ConfidenceLedgerError("ledger_head_reset_detected")
                self._load_state_locked()
                return
            anchor_ref = self._put_json(
                anchor_payload,
                kind="runtime.quality.confidence_ledger.scope_anchor",
                schema=_SCOPE_ANCHOR_SCHEMA,
            )
            if str(anchor_ref.artifact_id) != expected_anchor_ref:
                raise ConfidenceLedgerError("ledger_scope_anchor_identity_invalid")
            registry_ref = self._put_json(
                self._registry.source_payload(),
                kind="runtime.quality.confidence_ledger.registry",
                schema=_REGISTRY_SCHEMA,
            )
            if str(registry_ref.artifact_id) != expected_registry_ref:
                raise ConfidenceLedgerError("registry_artifact_identity_invalid")
            root = self._expected_root_binding(str(registry_ref.artifact_id))
            if self._artifact_store.has(expected_root_ref):
                raise ConfidenceLedgerError("ledger_head_reset_detected")
            root_ref = self._put_json(
                root.model_dump(mode="json"),
                kind="runtime.quality.confidence_ledger.root",
                schema=_ROOT_SCHEMA,
            )
            if str(root_ref.artifact_id) != expected_root_ref:
                raise ConfidenceLedgerError("ledger_root_artifact_identity_invalid")
            atomic_write_json(
                self._scope_tombstone_path,
                self._scope_tombstone_payload(expected_anchor_ref),
            )
            head = _LedgerHead(
                schema_version=CONFIDENCE_LEDGER_SCHEMA_VERSION,
                scope_id=root.scope_id,
                scope_anchor_ref=expected_anchor_ref,
                authority_provenance=self._authority_provenance,
                ledger_root_id=root.ledger_root_id,
                ledger_root_ref=str(root_ref.artifact_id),
                head_event_id=root.ledger_root_id,
                head_event_ref=str(root_ref.artifact_id),
                revision=0,
            )
            atomic_write_json(self._head_path, head.model_dump(mode="json"))
            self._cas_reconciled = True

    def _load_state_locked(
        self,
    ) -> tuple[_LedgerHead, ConfidenceLedgerRoot, tuple[ConfidenceLedgerEvent, ...]]:
        anchor_payload = self._scope_anchor_payload()
        anchor_ref = _cas_json_artifact_ref(anchor_payload)
        if self._read_cas_json(anchor_ref, _SCOPE_ANCHOR_SCHEMA) != anchor_payload:
            raise ConfidenceLedgerError("ledger_scope_anchor_invalid")
        try:
            tombstone = json.loads(self._scope_tombstone_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ConfidenceLedgerError("ledger_scope_tombstone_invalid", str(exc)) from exc
        if tombstone != self._scope_tombstone_payload(anchor_ref):
            raise ConfidenceLedgerError("ledger_scope_tombstone_invalid")
        registry_ref = _cas_json_artifact_ref(self._registry.source_payload())
        expected_root = self._expected_root_binding(registry_ref)
        root_ref = _cas_json_artifact_ref(expected_root)
        root = ConfidenceLedgerRoot.model_validate(self._read_cas_json(root_ref, _ROOT_SCHEMA))
        expected_root_id = _identity(
            "confidence-ledger-root",
            root.model_dump(mode="json", exclude={"ledger_root_id"}),
        )
        if root.ledger_root_id != expected_root_id:
            raise ConfidenceLedgerError("ledger_root_identity_invalid")
        if (
            root != expected_root
            or root.scope_anchor_ref != anchor_ref
            or root.authority_provenance != self._authority_provenance
            or root.deployment_identity != self._deployment_identity
        ):
            raise ConfidenceLedgerError("ledger_scope_binding_mismatch")
        registry_payload = self._read_cas_json(root.registry_artifact_ref, _REGISTRY_SCHEMA)
        if registry_payload != self._registry.source_payload():
            raise ConfidenceLedgerError("registry_binding_invalid")
        artifact_refs = self._scope_artifact_refs_locked(root, root_ref=root_ref)
        if artifact_refs["deployment_drift_poison"]:
            for poison_ref in artifact_refs["deployment_drift_poison"]:
                self._validate_deployment_drift_poison_ref(poison_ref)
            raise ConfidenceLedgerError("deployment_drift_poisoned")
        events = self._reconstruct_event_lineage_locked(
            root,
            root_ref=root_ref,
            event_refs=artifact_refs["event"],
        )
        _validate_chain_semantics(
            events,
            scope_id=root.scope_id,
            ledger_root_id=root.ledger_root_id,
            ledger_root_ref=root_ref,
            registry=self._registry,
        )
        self._validate_persisted_receipt_witnesses_locked(
            root=root,
            root_ref=root_ref,
            events=events,
            receipt_refs=artifact_refs["receipt"],
        )
        tail = events[-1] if events else None
        derived_head = _LedgerHead(
            schema_version=CONFIDENCE_LEDGER_SCHEMA_VERSION,
            scope_id=root.scope_id,
            scope_anchor_ref=root.scope_anchor_ref,
            authority_provenance=root.authority_provenance,
            ledger_root_id=root.ledger_root_id,
            ledger_root_ref=root_ref,
            head_event_id=tail.event_id if tail is not None else root.ledger_root_id,
            head_event_ref=tail.event_ref if tail is not None else root_ref,
            revision=len(events),
        )
        cached_head: _LedgerHead | None = None
        if self._head_path.exists():
            try:
                cached_head = _LedgerHead.model_validate_json(self._head_path.read_bytes())
            except (OSError, ValueError):
                cached_head = None
        if cached_head != derived_head:
            atomic_write_json(self._head_path, derived_head.model_dump(mode="json"))
        return derived_head, root, events

    def _scope_artifact_refs_locked(
        self,
        root: ConfidenceLedgerRoot,
        *,
        root_ref: str,
    ) -> dict[str, set[str]]:
        """Replay the scope WAL and reconcile shared CAS once per session."""

        refs = self._replay_scope_journal_locked()
        if self._cas_reconciled:
            return refs
        artifact_kinds = {
            "runtime.quality.confidence_ledger.event": "event",
            "runtime.quality.confidence_ledger.receipt": "receipt",
            "runtime.quality.confidence_ledger.deployment_drift_poison": (
                "deployment_drift_poison"
            ),
        }
        for artifact_id in self._artifact_store.iter_artifact_ids():
            try:
                manifest = self._artifact_store.get_manifest(artifact_id)
            except (OSError, ValueError):
                continue
            artifact_ref = str(artifact_id)
            if manifest.kind == "runtime.quality.confidence_ledger.root":
                if (
                    manifest.producer == _LEDGER_PRODUCER
                    and manifest.artifact_schema == _ROOT_SCHEMA
                ):
                    payload = self._read_cas_json(artifact_ref, _ROOT_SCHEMA)
                    if (
                        isinstance(payload, Mapping)
                        and payload.get("scope_id") == root.scope_id
                        and artifact_ref != root_ref
                    ):
                        raise ConfidenceLedgerError("ledger_scope_binding_mismatch")
                continue
            artifact_kind = artifact_kinds.get(manifest.kind)
            if artifact_kind is None:
                continue
            report = self._artifact_store.verify(artifact_id)
            if not report.ok:
                raise ConfidenceLedgerError("ledger_cas_integrity_invalid", report.error)
            try:
                payload = canon.from_canonical_bytes(self._artifact_store.get_bytes(artifact_id))
            except (OSError, ValueError, TypeError) as exc:
                raise ConfidenceLedgerError("ledger_cas_payload_invalid", str(exc)) from exc
            if not isinstance(payload, Mapping) or payload.get("scope_id") != root.scope_id:
                continue
            _, expected_schema = _journal_artifact_contract(artifact_kind)
            if manifest.producer != _LEDGER_PRODUCER or manifest.artifact_schema != expected_schema:
                code = (
                    "ledger_receipt_witness_invalid"
                    if artifact_kind == "receipt"
                    else "ledger_scope_journal_invalid"
                )
                raise ConfidenceLedgerError(code)
            payload_dict = dict(payload)
            if artifact_ref not in refs[artifact_kind]:
                self._append_scope_journal_intent(
                    artifact_kind=artifact_kind,
                    artifact_ref=artifact_ref,
                    payload=payload_dict,
                )
                self._append_scope_journal_commit(
                    artifact_kind=artifact_kind,
                    artifact_ref=artifact_ref,
                )
                refs[artifact_kind].add(artifact_ref)
        self._cas_reconciled = True
        return refs

    def _replay_scope_journal_locked(self) -> dict[str, set[str]]:
        """Complete WAL intents and return committed scope artifact refs."""

        records = self._read_new_scope_journal_records_locked()
        intents: dict[str, _ScopeJournalRecord] = {}
        commits: set[str] = set()
        refs: dict[str, set[str]] = {
            "event": set(),
            "receipt": set(),
            "deployment_drift_poison": set(),
        }
        for record in records:
            if record.record_type == "intent":
                existing = intents.get(record.artifact_ref)
                if existing is not None and (
                    existing.artifact_kind != record.artifact_kind
                    or existing.payload != record.payload
                ):
                    raise ConfidenceLedgerError("ledger_scope_journal_invalid")
                intents[record.artifact_ref] = record
            else:
                intent = intents.get(record.artifact_ref)
                if intent is None or intent.artifact_kind != record.artifact_kind:
                    raise ConfidenceLedgerError("ledger_scope_journal_invalid")
                commits.add(record.artifact_ref)
        for artifact_ref, intent in intents.items():
            payload = intent.payload
            if payload is None:
                raise ConfidenceLedgerError("ledger_scope_journal_invalid")
            if _cas_json_artifact_ref(payload) != artifact_ref:
                raise ConfidenceLedgerError("ledger_scope_journal_invalid")
            kind, schema = _journal_artifact_contract(intent.artifact_kind)
            if self._artifact_store.has(artifact_ref):
                if self._read_cas_json(artifact_ref, schema) != payload:
                    raise ConfidenceLedgerError("ledger_scope_journal_invalid")
            elif artifact_ref in commits:
                code = (
                    "ledger_receipt_witness_invalid"
                    if intent.artifact_kind == "event"
                    else "ledger_scope_journal_invalid"
                )
                raise ConfidenceLedgerError(code)
            else:
                ref = self._put_json(payload, kind=kind, schema=schema)
                if str(ref.artifact_id) != artifact_ref:
                    raise ConfidenceLedgerError("ledger_scope_journal_invalid")
            if artifact_ref not in commits:
                self._append_scope_journal_commit(
                    artifact_kind=intent.artifact_kind,
                    artifact_ref=artifact_ref,
                )
            refs[intent.artifact_kind].add(artifact_ref)
        return refs

    def _validate_deployment_drift_poison_ref(self, artifact_ref: str) -> None:
        """Validate one terminal same-scope canonical deployment denial."""

        payload = self._read_cas_json(
            artifact_ref,
            _DEPLOYMENT_DRIFT_POISON_SCHEMA,
        )
        try:
            poison = _DeploymentDriftPoison.model_validate(payload)
        except ValueError as exc:
            raise ConfidenceLedgerError("deployment_drift_poison_invalid", str(exc)) from exc
        expected_id = _identity(
            "confidence-deployment-drift-poison",
            poison.model_dump(mode="json", exclude={"poison_id"}),
        )
        if (
            poison.scope_id != self._risk_scope.scope_id
            or poison.expected_deployment_identity != self._deployment_identity
            or poison.poison_id != expected_id
        ):
            raise ConfidenceLedgerError("deployment_drift_poison_invalid")

    def _reconstruct_event_lineage_locked(
        self,
        root: ConfidenceLedgerRoot,
        *,
        root_ref: str,
        event_refs: set[str],
    ) -> tuple[ConfidenceLedgerEvent, ...]:
        """Rebuild the unique maximal same-scope/root event chain from immutable CAS."""

        children: dict[tuple[str, str], list[ConfidenceLedgerEvent]] = {}
        all_event_ids: set[str] = set()
        for artifact_ref in sorted(event_refs):
            payload = self._read_cas_json(artifact_ref, _EVENT_SCHEMA)
            try:
                stored = _StoredLedgerEvent.model_validate(payload)
            except ValueError as exc:
                raise ConfidenceLedgerError("ledger_event_chain_invalid", str(exc)) from exc
            if stored.ledger_root_id != root.ledger_root_id:
                raise ConfidenceLedgerError("ledger_scope_binding_mismatch")
            if (
                stored.event_id != _recompute_event_id(stored)
                or stored.check.event_id != stored.event_id
                or stored.check.check_id != _recompute_check_id(stored.check)
            ):
                raise ConfidenceLedgerError("ledger_event_chain_invalid")
            event = ConfidenceLedgerEvent(
                **stored.model_dump(mode="python"), event_ref=artifact_ref
            )
            children.setdefault((stored.parent_event_id, stored.parent_event_ref), []).append(event)
            if event.event_id in all_event_ids:
                raise ConfidenceLedgerError("ledger_event_fork_detected")
            all_event_ids.add(event.event_id)
        lineage: list[ConfidenceLedgerEvent] = []
        parent = (root.ledger_root_id, root_ref)
        while True:
            next_events = children.get(parent, [])
            if len(next_events) > 1:
                raise ConfidenceLedgerError("ledger_event_fork_detected")
            if not next_events:
                break
            event = next_events[0]
            lineage.append(event)
            parent = (event.event_id, event.event_ref)
        if {event.event_id for event in lineage} != all_event_ids:
            raise ConfidenceLedgerError("ledger_event_unreachable")
        return tuple(lineage)

    def _validate_persisted_receipt_witnesses_locked(
        self,
        *,
        root: ConfidenceLedgerRoot,
        root_ref: str,
        events: tuple[ConfidenceLedgerEvent, ...],
        receipt_refs: set[str],
    ) -> None:
        """Require every same-scope receipt to witness an exact CAS prefix."""

        for artifact_ref in sorted(receipt_refs):
            payload = self._read_cas_json(artifact_ref, _RECEIPT_SCHEMA)
            try:
                receipt = validate_confidence_ledger_receipt_structure(
                    payload,
                    registry=self._registry,
                )
                prefix = events[: len(receipt.events)]
                if receipt.events != prefix or len(prefix) != len(receipt.events):
                    raise ConfidenceLedgerError("ledger_receipt_witness_invalid")
                for witnessed in receipt.events:
                    stored_payload = self._read_cas_json(
                        witnessed.event_ref,
                        _EVENT_SCHEMA,
                    )
                    stored = _StoredLedgerEvent.model_validate(stored_payload)
                    materialized = ConfidenceLedgerEvent(
                        **stored.model_dump(mode="python"),
                        event_ref=witnessed.event_ref,
                    )
                    if materialized != witnessed:
                        raise ConfidenceLedgerError("ledger_receipt_witness_invalid")
                tail = receipt.events[-1] if receipt.events else None
                prefix_head = _LedgerHead(
                    schema_version=CONFIDENCE_LEDGER_SCHEMA_VERSION,
                    scope_id=root.scope_id,
                    scope_anchor_ref=root.scope_anchor_ref,
                    authority_provenance=root.authority_provenance,
                    ledger_root_id=root.ledger_root_id,
                    ledger_root_ref=root_ref,
                    head_event_id=(tail.event_id if tail is not None else root.ledger_root_id),
                    head_event_ref=tail.event_ref if tail is not None else root_ref,
                    revision=len(receipt.events),
                )
                expected = self._build_receipt(prefix_head, root, receipt.events)
                if receipt != expected:
                    raise ConfidenceLedgerError("ledger_receipt_witness_invalid")
            except (ConfidenceLedgerError, ValueError) as exc:
                if (
                    isinstance(exc, ConfidenceLedgerError)
                    and exc.code == "ledger_receipt_witness_invalid"
                ):
                    raise
                raise ConfidenceLedgerError("ledger_receipt_witness_invalid", str(exc)) from exc

    def _scope_anchor_payload(self) -> dict[str, Any]:
        """Return the immutable scope identity independent of mutable root bindings."""

        return {
            "schema_version": CONFIDENCE_LEDGER_SCHEMA_VERSION,
            "scope_id": self._risk_scope.scope_id,
            "scope_owner_ref": self._risk_scope.scope_owner_ref,
            "authority_purpose": self._risk_scope.authority_purpose,
            "owner_scope_key": self._risk_scope.owner_scope_key,
            "epoch_ref": self._risk_scope.epoch_ref,
        }

    def _scope_tombstone_payload(self, anchor_ref: str) -> dict[str, Any]:
        """Return the stable local scope index independent of root revisions."""

        return {
            **self._scope_anchor_payload(),
            "scope_anchor_ref": anchor_ref,
            "lock_identity": self._lock_identity(),
            "journal_identity": self._journal_identity(),
        }

    def _lock_identity(self) -> dict[str, int]:
        """Return the stable local lock inode bound at first scope creation."""

        try:
            stat = self._lock_path.stat()
        except OSError as exc:
            raise ConfidenceLedgerError("ledger_lock_identity_invalid", str(exc)) from exc
        return {"device": stat.st_dev, "inode": stat.st_ino}

    def _ensure_scope_journal_locked(self) -> None:
        """Create the WAL once, refusing replacement of an established journal."""

        if self._journal_path.exists():
            return
        if self._head_path.exists() or self._scope_tombstone_path.exists():
            raise ConfidenceLedgerError("ledger_scope_journal_invalid")
        flags = os.O_RDWR | os.O_CREAT | os.O_EXCL
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        try:
            fd = os.open(self._journal_path, flags, 0o600)
        except OSError as exc:
            raise ConfidenceLedgerError("ledger_scope_journal_invalid", str(exc)) from exc
        try:
            os.fsync(fd)
        finally:
            os.close(fd)

    def _journal_identity(self) -> dict[str, int]:
        """Return the inode identity of the scope-bound append WAL."""

        try:
            stat = self._journal_path.lstat()
        except OSError as exc:
            raise ConfidenceLedgerError("ledger_scope_journal_invalid", str(exc)) from exc
        return {"device": stat.st_dev, "inode": stat.st_ino}

    def _read_new_scope_journal_records_locked(
        self,
    ) -> tuple[_ScopeJournalRecord, ...]:
        """Incrementally validate records appended by this or another process."""

        identity = self._journal_identity()
        try:
            size = self._journal_path.stat().st_size
        except OSError as exc:
            raise ConfidenceLedgerError("ledger_scope_journal_invalid", str(exc)) from exc
        if size < self._journal_offset:
            raise ConfidenceLedgerError("ledger_scope_journal_rollback_detected")
        if size == self._journal_offset:
            return tuple(self._journal_records)
        try:
            with self._journal_path.open("rb") as handle:
                handle.seek(self._journal_offset)
                appended = handle.read()
        except OSError as exc:
            raise ConfidenceLedgerError("ledger_scope_journal_invalid", str(exc)) from exc
        if not appended.endswith(b"\n"):
            raise ConfidenceLedgerError("ledger_scope_journal_invalid")
        previous_hash = (
            self._journal_records[-1].record_hash
            if self._journal_records
            else _scope_journal_genesis_hash(self._risk_scope.scope_id)
        )
        revision = len(self._journal_records)
        for raw_line in appended.splitlines():
            try:
                record = _ScopeJournalRecord.model_validate_json(raw_line)
            except ValueError as exc:
                raise ConfidenceLedgerError("ledger_scope_journal_invalid", str(exc)) from exc
            expected_hash = _scope_journal_record_hash(record)
            if (
                record.scope_id != self._risk_scope.scope_id
                or record.revision != revision + 1
                or record.previous_record_hash != previous_hash
                or record.record_hash != expected_hash
                or (record.record_type == "intent") != (record.payload is not None)
            ):
                raise ConfidenceLedgerError("ledger_scope_journal_invalid")
            self._journal_records.append(record)
            revision += 1
            previous_hash = record.record_hash
        self._journal_offset = size
        if self._journal_identity() != identity:
            raise ConfidenceLedgerError("ledger_scope_journal_invalid")
        return tuple(self._journal_records)

    def _append_scope_journal_record_locked(
        self,
        *,
        record_type: Literal["intent", "commit"],
        artifact_kind: Literal["event", "receipt", "deployment_drift_poison"],
        artifact_ref: str,
        payload: dict[str, Any] | None,
    ) -> None:
        """Append and fsync one hash-chained WAL record."""

        self._read_new_scope_journal_records_locked()
        previous_hash = (
            self._journal_records[-1].record_hash
            if self._journal_records
            else _scope_journal_genesis_hash(self._risk_scope.scope_id)
        )
        values: dict[str, Any] = {
            "schema_version": CONFIDENCE_LEDGER_SCHEMA_VERSION,
            "scope_id": self._risk_scope.scope_id,
            "revision": len(self._journal_records) + 1,
            "previous_record_hash": previous_hash,
            "record_type": record_type,
            "artifact_kind": artifact_kind,
            "artifact_ref": artifact_ref,
            "payload": payload,
        }
        values["record_hash"] = _content_hash(values)
        record = _ScopeJournalRecord.model_validate(values)
        encoded = f"{_canonical_json(record)}\n".encode()
        flags = os.O_WRONLY | os.O_APPEND
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        expected_identity = self._journal_identity()
        try:
            fd = os.open(self._journal_path, flags)
        except OSError as exc:
            raise ConfidenceLedgerError("ledger_scope_journal_invalid", str(exc)) from exc
        try:
            held = os.fstat(fd)
            if (held.st_dev, held.st_ino) != (
                expected_identity["device"],
                expected_identity["inode"],
            ):
                raise ConfidenceLedgerError("ledger_scope_journal_invalid")
            written = 0
            while written < len(encoded):
                written += os.write(fd, encoded[written:])
            os.fsync(fd)
        finally:
            os.close(fd)
        self._journal_records.append(record)
        self._journal_offset += len(encoded)

    def _append_scope_journal_intent(
        self,
        *,
        artifact_kind: Literal["event", "receipt", "deployment_drift_poison"],
        artifact_ref: str,
        payload: dict[str, Any],
    ) -> None:
        """Durably record reconstructible bytes before their CAS write."""

        records = self._read_new_scope_journal_records_locked()
        existing = [
            record
            for record in records
            if record.record_type == "intent" and record.artifact_ref == artifact_ref
        ]
        if existing:
            if any(
                record.artifact_kind != artifact_kind or record.payload != payload
                for record in existing
            ):
                raise ConfidenceLedgerError("ledger_scope_journal_invalid")
            return
        self._append_scope_journal_record_locked(
            record_type="intent",
            artifact_kind=artifact_kind,
            artifact_ref=artifact_ref,
            payload=payload,
        )

    def _append_scope_journal_commit(
        self,
        *,
        artifact_kind: Literal["event", "receipt", "deployment_drift_poison"],
        artifact_ref: str,
    ) -> None:
        """Commit one WAL intent after its CAS artifact verifies."""

        if artifact_kind not in {"event", "receipt", "deployment_drift_poison"}:
            raise ConfidenceLedgerError("ledger_scope_journal_invalid")
        records = self._read_new_scope_journal_records_locked()
        if any(
            record.record_type == "commit" and record.artifact_ref == artifact_ref
            for record in records
        ):
            return
        if not any(
            record.record_type == "intent"
            and record.artifact_ref == artifact_ref
            and record.artifact_kind == artifact_kind
            for record in records
        ):
            raise ConfidenceLedgerError("ledger_scope_journal_invalid")
        self._append_scope_journal_record_locked(
            record_type="commit",
            artifact_kind=artifact_kind,
            artifact_ref=artifact_ref,
            payload=None,
        )

    def _journaled_put_json_locked(
        self,
        payload: dict[str, Any],
        *,
        artifact_kind: Literal["event", "receipt", "deployment_drift_poison"],
    ) -> artifacts.ArtifactRef:
        """Write one artifact through WAL intent, CAS verification, and commit."""

        kind, schema = _journal_artifact_contract(artifact_kind)
        artifact_ref = _cas_json_artifact_ref(payload)
        self._append_scope_journal_intent(
            artifact_kind=artifact_kind,
            artifact_ref=artifact_ref,
            payload=payload,
        )
        ref = self._put_json(payload, kind=kind, schema=schema)
        if str(ref.artifact_id) != artifact_ref:
            raise ConfidenceLedgerError("ledger_scope_journal_invalid")
        self._read_cas_json(artifact_ref, schema)
        self._append_scope_journal_commit(
            artifact_kind=artifact_kind,
            artifact_ref=artifact_ref,
        )
        return ref

    def _owner_invocation_lock_path(self, execution_id: str) -> Path:
        """Return the stable local lock path for one execution identity."""

        execution_hex = execution_id.rsplit(":", 1)[-1]
        return self._state_root / "owner_invocations" / f"{execution_hex}.lock"

    def _create_owner_invocation_lock_locked(
        self,
        *,
        execution_id: str,
        request_fingerprint: str,
    ) -> OwnerInvocationLockIdentity:
        """Create the stable invocation lock before publishing a started event."""

        path = self._owner_invocation_lock_path(execution_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        nonce = _identity(
            "confidence-owner-invocation-lock",
            {
                "scope_id": self._risk_scope.scope_id,
                "execution_id": execution_id,
                "request_fingerprint": request_fingerprint,
            },
        )
        flags = os.O_RDWR | os.O_CREAT | os.O_EXCL
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        try:
            fd = os.open(path, flags, 0o600)
        except FileExistsError:
            return self._adopt_unpublished_owner_invocation_lock(
                path=path,
                nonce=nonce,
            )
        except OSError as exc:
            raise ConfidenceLedgerError("owner_invocation_lock_invalid", str(exc)) from exc
        try:
            os.write(fd, f"{nonce}\n".encode())
            os.fsync(fd)
            held = os.fstat(fd)
            linked = path.lstat()
            if (held.st_dev, held.st_ino) != (linked.st_dev, linked.st_ino):
                raise ConfidenceLedgerError("owner_invocation_lock_invalid")
            return OwnerInvocationLockIdentity(
                nonce=nonce,
                device=held.st_dev,
                inode=held.st_ino,
            )
        finally:
            os.close(fd)

    def _adopt_unpublished_owner_invocation_lock(
        self,
        *,
        path: Path,
        nonce: str,
    ) -> OwnerInvocationLockIdentity:
        """Adopt an exact crash-orphan lock only after proving it is not live."""

        thread_lock = _path_invocation_thread_lock(path)
        if not thread_lock.acquire(blocking=False):
            raise ConfidenceLedgerError("owner_invocation_still_live")
        fd: int | None = None
        filesystem_locked = False
        try:
            flags = os.O_RDWR
            if hasattr(os, "O_NOFOLLOW"):
                flags |= os.O_NOFOLLOW
            try:
                fd = os.open(path, flags)
                held = os.fstat(fd)
                linked = path.lstat()
            except OSError as exc:
                raise ConfidenceLedgerError("owner_invocation_lock_invalid", str(exc)) from exc
            if (held.st_dev, held.st_ino) != (linked.st_dev, linked.st_ino):
                raise ConfidenceLedgerError("owner_invocation_lock_invalid")
            os.lseek(fd, 0, os.SEEK_SET)
            if os.read(fd, 512) != f"{nonce}\n".encode():
                raise ConfidenceLedgerError("owner_invocation_lock_invalid")
            try:
                _fcntl.flock(fd, _fcntl.LOCK_EX | _fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise ConfidenceLedgerError("owner_invocation_still_live") from exc
            filesystem_locked = True
            return OwnerInvocationLockIdentity(
                nonce=nonce,
                device=held.st_dev,
                inode=held.st_ino,
            )
        finally:
            if fd is not None:
                if filesystem_locked:
                    _fcntl.flock(fd, _fcntl.LOCK_UN)
                os.close(fd)
            thread_lock.release()

    @contextmanager
    def _owner_invocation_lock(
        self,
        check: ConfidenceLedgerCheck,
        *,
        blocking: bool,
    ) -> Iterable[None]:
        """Hold the process and filesystem locks for one owner invocation."""

        execution_id = check.execution_id
        identity = check.owner_invocation_lock_identity
        if execution_id is None or identity is None:
            raise ConfidenceLedgerError("owner_invocation_lock_invalid")
        path = self._owner_invocation_lock_path(execution_id)
        thread_lock = _path_invocation_thread_lock(path)
        if not thread_lock.acquire(blocking=blocking):
            raise ConfidenceLedgerError("owner_invocation_still_live")
        fd: int | None = None
        filesystem_locked = False
        try:
            flags = os.O_RDWR
            if hasattr(os, "O_NOFOLLOW"):
                flags |= os.O_NOFOLLOW
            try:
                fd = os.open(path, flags)
                held = os.fstat(fd)
                linked = path.lstat()
            except OSError as exc:
                raise ConfidenceLedgerError("owner_invocation_lock_invalid", str(exc)) from exc
            if (held.st_dev, held.st_ino) != (identity.device, identity.inode) or (
                linked.st_dev,
                linked.st_ino,
            ) != (identity.device, identity.inode):
                raise ConfidenceLedgerError("owner_invocation_lock_invalid")
            os.lseek(fd, 0, os.SEEK_SET)
            if os.read(fd, 512) != f"{identity.nonce}\n".encode():
                raise ConfidenceLedgerError("owner_invocation_lock_invalid")
            lock_flags = _fcntl.LOCK_EX | (0 if blocking else _fcntl.LOCK_NB)
            try:
                _fcntl.flock(fd, lock_flags)
            except BlockingIOError as exc:
                raise ConfidenceLedgerError("owner_invocation_still_live") from exc
            filesystem_locked = True
            held = os.fstat(fd)
            try:
                linked = path.lstat()
            except OSError as exc:
                raise ConfidenceLedgerError("owner_invocation_lock_invalid", str(exc)) from exc
            if (held.st_dev, held.st_ino) != (identity.device, identity.inode) or (
                linked.st_dev,
                linked.st_ino,
            ) != (identity.device, identity.inode):
                raise ConfidenceLedgerError("owner_invocation_lock_invalid")
            yield
        finally:
            if fd is not None:
                if filesystem_locked:
                    _fcntl.flock(fd, _fcntl.LOCK_UN)
                os.close(fd)
            thread_lock.release()

    def _prior_scope_artifact_exists(self) -> bool:
        """Find an older chain even when mutable pointers and anchors were removed."""

        for artifact_id in self._artifact_store.iter_artifact_ids():
            try:
                manifest = self._artifact_store.get_manifest(artifact_id)
            except (OSError, ValueError):
                continue
            recognized = {
                "runtime.quality.confidence_ledger.root": _ROOT_SCHEMA,
                "runtime.quality.confidence_ledger.event": _EVENT_SCHEMA,
                "runtime.quality.confidence_ledger.receipt": _RECEIPT_SCHEMA,
            }
            expected_schema = recognized.get(manifest.kind)
            if (
                expected_schema is None
                or manifest.artifact_schema != expected_schema
                or manifest.producer != _LEDGER_PRODUCER
            ):
                continue
            try:
                payload = canon.from_canonical_bytes(self._artifact_store.get_bytes(artifact_id))
            except (OSError, ValueError, TypeError):
                continue
            if isinstance(payload, Mapping) and payload.get("scope_id") == (
                self._risk_scope.scope_id
            ):
                return True
        return False

    def _scope_root_artifact_exists(self) -> bool:
        """Return whether immutable CAS contains any root for this scope."""

        for artifact_id in self._artifact_store.iter_artifact_ids():
            try:
                manifest = self._artifact_store.get_manifest(artifact_id)
            except (OSError, ValueError):
                continue
            if (
                manifest.kind != "runtime.quality.confidence_ledger.root"
                or manifest.artifact_schema != _ROOT_SCHEMA
                or manifest.producer != _LEDGER_PRODUCER
            ):
                continue
            try:
                payload = canon.from_canonical_bytes(self._artifact_store.get_bytes(artifact_id))
            except (OSError, ValueError, TypeError):
                continue
            if (
                isinstance(payload, Mapping)
                and payload.get("scope_id") == self._risk_scope.scope_id
            ):
                return True
        return False

    def _expected_root_binding(self, registry_ref: str) -> ConfidenceLedgerRoot:
        payload: dict[str, Any] = {
            "schema_version": CONFIDENCE_LEDGER_SCHEMA_VERSION,
            "risk_scope": self._risk_scope,
            "scope_id": self._risk_scope.scope_id,
            "scope_anchor_ref": _cas_json_artifact_ref(self._scope_anchor_payload()),
            "authority_provenance": self._authority_provenance,
            "deployment_identity": self._deployment_identity,
            "registry_artifact_ref": registry_ref,
            "registry_content_hash": self._registry.content_hash,
            "schedule_profile_id": self._schedule.profile_id,
            "schedule_profile_hash": _content_hash(self._schedule),
            "schedule_projection_hash": _schedule_projection_hash(self._registry, self._schedule),
            "obligation_split_hash": _content_hash(
                {
                    item.value: _rational_spec(weight)
                    for item, weight in self._registry.obligation_weights.items()
                }
            ),
            "budget_delta": self._registry.policy.delta,
            "conditionality_clause": CONDITIONAL_VALIDITY_CLAUSE,
            "maintained_assumptions": _MAINTAINED_ASSUMPTIONS,
        }
        payload["ledger_root_id"] = _identity("confidence-ledger-root", payload)
        return ConfidenceLedgerRoot.model_validate(payload)

    def _history_token(
        self,
        head: _LedgerHead,
        root: ConfidenceLedgerRoot,
        events: tuple[ConfidenceLedgerEvent, ...],
    ) -> ConfidenceLedgerHistoryToken:
        ordinals = [
            item.execution_ordinal
            for item in _current_checks(events).values()
            if item.execution_ordinal is not None
        ]
        base = {
            "scope_id": root.scope_id,
            "ledger_root_id": root.ledger_root_id,
            "ledger_root_ref": head.ledger_root_ref,
            "head_event_id": head.head_event_id,
            "head_event_ref": head.head_event_ref,
            "revision": head.revision,
            "next_execution_ordinal": max(ordinals, default=-1) + 1,
            "filtration_ref": f"confidence-ledger://{root.scope_id}/revision/{head.revision}",
        }
        return ConfidenceLedgerHistoryToken(**base, precheck_history_hash=_content_hash(base))

    def _base_check(
        self,
        *,
        head: _LedgerHead,
        history_token: ConfidenceLedgerHistoryToken,
        request_key: str,
        fingerprint: str,
        obligation: PromotionObligationClass,
        instrument_id: str,
        certificate_ref: str,
        certificate_class: str | None,
        certificate_route_hash: str | None,
        claim: PredictableClaimSpec,
        instrument: InstrumentDefinition | None,
        profile: InstrumentProofProfile | None,
        execution_status: ExecutionStatus,
        outcome: CompletionOutcome,
        refusal_code: str | None,
        proof_detail: str,
    ) -> ConfidenceLedgerCheck:
        family = instrument.instrument_family if instrument else "unknown_instrument"
        profile_id = instrument.proof_profile_id if instrument else "unknown_profile"
        event_id = _identity(
            "confidence-event",
            {
                "scope_id": self._risk_scope.scope_id,
                "revision": head.revision + 1,
                "parent_event_id": head.head_event_id,
                "request_fingerprint": fingerprint,
                "outcome": outcome,
            },
        )
        values: dict[str, Any] = {
            "schema_version": CONFIDENCE_LEDGER_SCHEMA_VERSION,
            "scope_id": self._risk_scope.scope_id,
            "request_key": request_key,
            "request_fingerprint": fingerprint,
            "obligation_class": obligation,
            "instrument_id": instrument_id,
            "instrument_family": family,
            "proof_profile_id": profile_id,
            "certificate_ref": certificate_ref,
            "certificate_class": certificate_class,
            "certificate_route_hash": certificate_route_hash,
            "certificate_role": claim.certificate_role,
            "claim_polarity": claim.claim_polarity,
            "claim_ref": claim.claim_ref,
            "null_ref": claim.null_ref,
            "claim_scope_ref": claim.claim_scope_ref,
            "data_window_ref": claim.data_window_ref,
            "filtration_ref": history_token.filtration_ref,
            "precheck_history_hash": history_token.precheck_history_hash,
            "registry_content_hash": self._registry.content_hash,
            "instrument_definition_hash": (_content_hash(instrument) if instrument else None),
            "proof_profile_hash": _content_hash(profile) if profile else None,
            "prepared_event_id": event_id,
            "started_event_id": None,
            "event_id": event_id,
            "execution_status": execution_status,
            "outcome": outcome,
            "execution_ordinal": None,
            "schedule_query_index": None,
            "execution_id": None,
            "owner_invocation_claim_id": None,
            "owner_invocation_lock_identity": None,
            "deterministic_proof": bool(profile and profile.deterministic),
            "anytime_valid": bool(profile and profile.anytime_valid),
            "spend": _rational_spec(Fraction()),
            "spend_decimal": "0",
            "supports_obligation": False,
            "eligible_for_promotion": False,
            "refusal_code": refusal_code,
            "proof_detail": proof_detail,
            "good_event_id": None,
            "owner_binding": None,
            "claim_execution_binding_hash": _content_hash(
                {
                    "request_fingerprint": fingerprint,
                    "history": history_token.precheck_history_hash,
                    "execution": None,
                    "spend": _rational_spec(Fraction()),
                }
            ),
        }
        values["check_id"] = _identity("confidence-check", values)
        return ConfidenceLedgerCheck.model_validate(values)

    def _append_event_locked(
        self,
        *,
        head: _LedgerHead,
        root: ConfidenceLedgerRoot,
        event_type: Literal["prepared", "started", "completed"],
        check: ConfidenceLedgerCheck,
    ) -> ConfidenceLedgerEvent:
        self._assert_deployment_identity_locked()
        revision = head.revision + 1
        event_core = {
            "event_type": event_type,
            "scope_id": root.scope_id,
            "ledger_root_id": root.ledger_root_id,
            "revision": revision,
            "parent_event_id": head.head_event_id,
            "parent_event_ref": head.head_event_ref,
            "check": check,
        }
        event_id = _identity("confidence-event", _event_identity_payload(event_core))
        updates: dict[str, Any] = {"event_id": event_id}
        if event_type == "prepared" or (
            check.outcome == "preflight_refusal" and check.started_event_id is None
        ):
            updates["prepared_event_id"] = event_id
        if event_type == "started" and check.started_event_id is None:
            updates["started_event_id"] = event_id
        revised = check.model_copy(update=updates)
        revised = revised.model_copy(update={"check_id": _recompute_check_id(revised)})
        stored = _StoredLedgerEvent(
            schema_version=CONFIDENCE_LEDGER_SCHEMA_VERSION,
            event_type=event_type,
            scope_id=root.scope_id,
            ledger_root_id=root.ledger_root_id,
            revision=revision,
            parent_event_id=head.head_event_id,
            parent_event_ref=head.head_event_ref,
            event_id=event_id,
            check=revised,
        )
        if _recompute_event_id(stored) != event_id:
            raise ConfidenceLedgerError("ledger_event_identity_invalid")
        ref = self._journaled_put_json_locked(
            stored.model_dump(mode="json"),
            artifact_kind="event",
        )
        event = ConfidenceLedgerEvent(
            **stored.model_dump(mode="python"), event_ref=str(ref.artifact_id)
        )
        next_head = _LedgerHead(
            schema_version=CONFIDENCE_LEDGER_SCHEMA_VERSION,
            scope_id=root.scope_id,
            scope_anchor_ref=root.scope_anchor_ref,
            authority_provenance=root.authority_provenance,
            ledger_root_id=root.ledger_root_id,
            ledger_root_ref=head.ledger_root_ref,
            head_event_id=event_id,
            head_event_ref=str(ref.artifact_id),
            revision=revision,
        )
        atomic_write_json(self._head_path, next_head.model_dump(mode="json"))
        self._assert_deployment_identity_locked()
        return event

    def _complete_unstarted(
        self,
        offered: ConfidenceLedgerCheck,
        *,
        outcome: Literal["cancelled"],
        proof_detail: str,
    ) -> ConfidenceLedgerCheck:
        with self._exclusive_lock():
            head, root, events = self._load_state_locked()
            current = _current_checks(events).get(offered.request_key)
            if current is None or current.request_fingerprint != offered.request_fingerprint:
                raise ConfidenceLedgerError("prepared_check_not_canonical")
            if current.outcome != "prepared":
                return current
            completed = current.model_copy(
                update={
                    "execution_status": "unexecuted",
                    "outcome": outcome,
                    "proof_detail": proof_detail,
                }
            )
            return self._append_event_locked(
                head=head, root=root, event_type="completed", check=completed
            ).check

    def _complete(
        self,
        offered: ConfidenceLedgerCheck,
        *,
        outcome: CompletionOutcome,
        supports_obligation: bool,
        eligible_for_promotion: bool,
        proof_detail: str,
        refusal_code: str | None = None,
        owner_binding: OwnerCertificateBinding | None = None,
    ) -> ConfidenceLedgerCheck:
        with self._exclusive_lock():
            head, root, events = self._load_state_locked()
            current = _current_checks(events).get(offered.request_key)
            if current is None or current.request_fingerprint != offered.request_fingerprint:
                raise ConfidenceLedgerError("started_check_not_canonical")
            if current.outcome != "started":
                return current
            return self._complete_locked(
                head=head,
                root=root,
                events=events,
                current=current,
                outcome=outcome,
                supports_obligation=supports_obligation,
                eligible_for_promotion=eligible_for_promotion,
                proof_detail=proof_detail,
                refusal_code=refusal_code,
                owner_binding=owner_binding,
            )

    def _complete_locked(
        self,
        *,
        head: _LedgerHead,
        root: ConfidenceLedgerRoot,
        events: tuple[ConfidenceLedgerEvent, ...],
        current: ConfidenceLedgerCheck,
        outcome: CompletionOutcome,
        supports_obligation: bool,
        eligible_for_promotion: bool,
        proof_detail: str,
        refusal_code: str | None = None,
        owner_binding: OwnerCertificateBinding | None = None,
    ) -> ConfidenceLedgerCheck:
        """Append one completion while the caller holds the scope lock."""

        del events
        if current.outcome != "started":
            return current
        if outcome != "recovered_crash" and current.owner_invocation_claim_id is None:
            raise ConfidenceLedgerError("owner_invocation_claim_missing")
        status: ExecutionStatus = "executed"
        if outcome in {"owner_refused", "owner_error", "recovered_crash", "refused"}:
            status = "refused"
        good_event_id = None
        if not current.deterministic_proof and current.execution_ordinal is not None:
            good_event_id = _identity(
                "confidence-good-event",
                {
                    "execution_id": current.execution_id,
                    "spend": current.spend,
                    "protected_error": current.claim_polarity,
                },
            )
        completed = current.model_copy(
            update={
                "execution_status": status,
                "outcome": outcome,
                "supports_obligation": supports_obligation,
                "eligible_for_promotion": eligible_for_promotion,
                "refusal_code": refusal_code,
                "proof_detail": proof_detail,
                "owner_binding": owner_binding,
                "good_event_id": good_event_id,
            }
        )
        return self._append_event_locked(
            head=head, root=root, event_type="completed", check=completed
        ).check

    def _resolve_bind_verify_owner(
        self, check: ConfidenceLedgerCheck
    ) -> tuple[OwnerCertificateBinding, bool]:
        if self._certificate_resolver is None or self._certificate_verifier is None:
            raise ConfidenceLedgerError("owner_reverification_failed")
        if check.certificate_class is None or check.certificate_route_hash is None:
            raise ConfidenceLedgerError("certificate_class_route_missing")
        route = self._registry.resolve_certificate_route(check.certificate_class)
        if (
            check.certificate_route_hash != _content_hash(route)
            or route.instrument_id != check.instrument_id
            or route.obligation_class != check.obligation_class
            or route.certificate_role != check.certificate_role
            or route.claim_polarity != check.claim_polarity
        ):
            raise ConfidenceLedgerError("certificate_class_route_mismatch")
        evidence = self._certificate_resolver(check)
        if (
            evidence.certificate_ref != check.certificate_ref
            or evidence.instrument_id != check.instrument_id
            or evidence.obligation_class != check.obligation_class
            or evidence.certificate_role != check.certificate_role
            or evidence.claim_polarity != check.claim_polarity
            or evidence.certificate_class != check.certificate_class
        ):
            raise ConfidenceLedgerError("owner_certificate_binding_invalid")
        if evidence.claim_execution_binding_hash != check.claim_execution_binding_hash:
            raise ConfidenceLedgerError("claim_execution_binding_invalid")
        if evidence.owner_ref != route.owner_ref:
            raise ConfidenceLedgerError("owner_verifier_provenance_mismatch")
        verification = self._certificate_verifier(evidence)
        if evidence.owner_ref == verification.verifier_ref:
            raise ConfidenceLedgerError("owner_and_verifier_must_be_distinct")
        if verification.verifier_ref != route.verifier_ref:
            raise ConfidenceLedgerError("owner_verifier_provenance_mismatch")
        evidence_hash = _content_hash(evidence)
        if (
            verification.certificate_evidence_hash != evidence_hash
            or verification.claim_execution_binding_hash != check.claim_execution_binding_hash
        ):
            raise ConfidenceLedgerError("owner_verifier_binding_invalid")
        binding = OwnerCertificateBinding(
            certificate_ref=evidence.certificate_ref,
            certificate_class=check.certificate_class,
            certificate_route_hash=check.certificate_route_hash,
            owner_ref=evidence.owner_ref,
            owner_projection_hash=_content_hash(evidence.owner_projection),
            verifier_ref=verification.verifier_ref,
            verifier_kernel_id=route.verifier_kernel_id,
            verifier_projection_hash=_content_hash(verification.verifier_projection),
            certificate_evidence_hash=evidence_hash,
            verification_hash=_content_hash(verification),
        )
        return binding, verification.supports_obligation

    def _build_receipt(
        self,
        head: _LedgerHead,
        root: ConfidenceLedgerRoot,
        events: tuple[ConfidenceLedgerEvent, ...],
    ) -> ConfidenceLedgerReceipt:
        checks = tuple(sorted(_current_checks(events).values(), key=lambda item: item.request_key))
        total = sum((item.spend.fraction for item in checks), Fraction())
        payload: dict[str, Any] = {
            "schema_version": CONFIDENCE_LEDGER_SCHEMA_VERSION,
            "scope_id": root.scope_id,
            "scope_anchor_ref": root.scope_anchor_ref,
            "authority_provenance": root.authority_provenance,
            "deployment_identity": root.deployment_identity,
            "ledger_root_id": root.ledger_root_id,
            "ledger_root_ref": head.ledger_root_ref,
            "head_event_id": head.head_event_id,
            "head_event_ref": head.head_event_ref,
            "registry_artifact_ref": root.registry_artifact_ref,
            "registry_content_hash": root.registry_content_hash,
            "schedule_profile_id": root.schedule_profile_id,
            "schedule_profile_hash": root.schedule_profile_hash,
            "schedule_projection_hash": root.schedule_projection_hash,
            "budget_delta": root.budget_delta,
            "budget_delta_decimal": _fraction_display(root.budget_delta.fraction),
            "events": events,
            "checks": checks,
            "total_spend": _rational_spec(total),
            "total_spend_decimal": _fraction_display(total),
            "within_budget": total <= root.budget_delta.fraction,
            "good_event_clause": GOOD_EVENT_CLAUSE,
            "conditionality_clause": CONDITIONAL_VALIDITY_CLAUSE,
            "maintained_assumptions": _MAINTAINED_ASSUMPTIONS,
        }
        payload["receipt_id"] = _identity("confidence-ledger", payload)
        return ConfidenceLedgerReceipt.model_validate(payload)

    def _read_cas_json(self, artifact_ref: str, schema: artifacts.SchemaInfo) -> object:
        report = self._artifact_store.verify(artifact_ref)
        if not report.ok:
            raise ConfidenceLedgerError("ledger_cas_integrity_invalid", report.error)
        manifest = self._artifact_store.get_manifest(artifact_ref)
        if manifest.artifact_schema != schema or manifest.producer != _LEDGER_PRODUCER:
            raise ConfidenceLedgerError("ledger_cas_manifest_invalid")
        try:
            return canon.from_canonical_bytes(self._artifact_store.get_bytes(artifact_ref))
        except (OSError, ValueError, TypeError) as exc:
            raise ConfidenceLedgerError("ledger_cas_payload_invalid", str(exc)) from exc

    def _put_json(
        self, payload: object, *, kind: str, schema: artifacts.SchemaInfo
    ) -> artifacts.ArtifactRef:
        return self._artifact_store.put_json(
            _jsonable(payload),
            artifacts.PutOptions(
                kind=kind,
                media_type="application/json",
                schema=schema,
                producer=_LEDGER_PRODUCER,
            ),
            canon_spec=_CAS_CANON_SPEC,
        )

    @contextmanager
    def _exclusive_lock(self) -> Iterable[None]:
        if _fcntl is None:  # pragma: no cover
            raise ConfidenceLedgerError("ledger_lock_backend_unavailable")
        lock = _path_thread_lock(self._lock_path)
        with lock:
            self._lock_path.parent.mkdir(parents=True, exist_ok=True)
            existing_scope = self._head_path.exists() or self._scope_tombstone_path.exists()
            if existing_scope and not self._lock_path.exists():
                raise ConfidenceLedgerError("ledger_lock_identity_invalid")
            try:
                fd = os.open(self._lock_path, os.O_RDWR | os.O_CREAT | os.O_EXCL, 0o600)
            except FileExistsError:
                try:
                    fd = os.open(self._lock_path, os.O_RDWR)
                except OSError as exc:
                    raise ConfidenceLedgerError("ledger_lock_identity_invalid", str(exc)) from exc
            try:
                _fcntl.flock(fd, _fcntl.LOCK_EX)
                held = os.fstat(fd)
                try:
                    linked = self._lock_path.stat()
                except OSError as exc:
                    raise ConfidenceLedgerError("ledger_lock_identity_invalid", str(exc)) from exc
                if (held.st_dev, held.st_ino) != (linked.st_dev, linked.st_ino):
                    raise ConfidenceLedgerError("ledger_lock_identity_invalid")
                self._assert_deployment_identity_locked()
                if self._journal_path.exists():
                    self._assert_no_deployment_drift_poison_locked()
                try:
                    yield
                finally:
                    self._assert_deployment_identity_locked()
            finally:
                _fcntl.flock(fd, _fcntl.LOCK_UN)
                os.close(fd)

    def _assert_deployment_identity_locked(self) -> None:
        """Fence canonical authority against a checkout change during a session."""

        if self._authority_provenance != "canonical_repo":
            return
        root = self._authority_repo_root
        observed: str | None = None
        if root is not None and root == _loaded_policy_engine_root():
            try:
                observed = _policy_engine_deployment_identity(root)
            except ConfidenceLedgerError:
                observed = None
        if observed != self._deployment_identity:
            if self._journal_path.exists():
                self._persist_deployment_drift_poison_locked(observed)
            raise ConfidenceLedgerError("canonical_deployment_identity_invalid")

    def _persist_deployment_drift_poison_locked(self, observed: str | None) -> None:
        """Persist an irreversible denial before reporting canonical source drift."""

        observed_identity = observed or _identity(
            "policy-engine-deployment",
            {"status": "unavailable"},
        )
        payload: dict[str, Any] = {
            "schema_version": CONFIDENCE_LEDGER_SCHEMA_VERSION,
            "scope_id": self._risk_scope.scope_id,
            "authority_provenance": "canonical_repo",
            "expected_deployment_identity": self._deployment_identity,
            "observed_deployment_identity": observed_identity,
            "reason": "canonical_deployment_identity_changed",
        }
        payload["poison_id"] = _identity(
            "confidence-deployment-drift-poison",
            payload,
        )
        self._journaled_put_json_locked(
            payload,
            artifact_kind="deployment_drift_poison",
        )

    def _assert_no_deployment_drift_poison_locked(self) -> None:
        """Treat every valid same-scope deployment poison as terminal."""

        refs = self._replay_scope_journal_locked()["deployment_drift_poison"]
        for artifact_ref in refs:
            self._validate_deployment_drift_poison_ref(artifact_ref)
        if refs:
            raise ConfidenceLedgerError("deployment_drift_poisoned")


def load_confidence_ledger_registry(
    source: str | Path | Mapping[str, object],
) -> ConfidenceLedgerRegistry:
    """Load and validate the data registry from TOML or an explicit payload."""

    if isinstance(source, Mapping):
        payload: object = dict(source)
    else:
        with Path(source).open("rb") as handle:
            payload = tomllib.load(handle)
    return ConfidenceLedgerRegistry.model_validate(payload)


def recompute_confidence_schedule_projection_hash(
    registry: ConfidenceLedgerRegistry,
    *,
    schedule_profile_id: str | None = None,
) -> str:
    """Recompute the code-owned proof projection for one registered schedule."""

    schedule = registry.resolve_schedule(schedule_profile_id)
    return _schedule_projection_hash(registry, schedule)


def validate_confidence_ledger_receipt_structure(
    receipt: ConfidenceLedgerReceipt | Mapping[str, object],
    *,
    registry: ConfidenceLedgerRegistry,
) -> ConfidenceLedgerReceipt:
    """Purely recompute a receipt's registry, lineage, and spend semantics.

    This validator is independent of the mutable head, CAS availability, and
    certificate owners.  Authority-bearing callers must additionally use
    :func:`validate_confidence_ledger_receipt` for current-head and owner
    re-verification.
    """

    try:
        parsed = (
            receipt
            if isinstance(receipt, ConfidenceLedgerReceipt)
            else ConfidenceLedgerReceipt.model_validate(receipt)
        )
    except ValueError as exc:
        message = str(exc)
        if "conditionality_clause" in message:
            raise ConfidenceLedgerError("conditionality_clause_missing") from exc
        raise ConfidenceLedgerError("receipt_schema_invalid", message) from exc
    if parsed.conditionality_clause != CONDITIONAL_VALIDITY_CLAUSE:
        raise ConfidenceLedgerError("conditionality_clause_missing")
    if parsed.maintained_assumptions != _MAINTAINED_ASSUMPTIONS:
        raise ConfidenceLedgerError("maintained_assumptions_missing")
    if parsed.registry_content_hash != registry.content_hash:
        raise ConfidenceLedgerError("registry_binding_invalid")
    schedule = registry.resolve_schedule(parsed.schedule_profile_id)
    if (
        parsed.schedule_profile_hash != _content_hash(schedule)
        or parsed.schedule_projection_hash
        != recompute_confidence_schedule_projection_hash(
            registry,
            schedule_profile_id=parsed.schedule_profile_id,
        )
        or parsed.budget_delta != registry.policy.delta
        or parsed.budget_delta_decimal != _fraction_display(registry.policy.delta.fraction)
    ):
        raise ConfidenceLedgerError("schedule_projection_binding_invalid")
    _validate_receipt_event_lineage(parsed, registry=registry)
    for check in parsed.checks:
        _validate_check_registry_binding(check, registry=registry)
        _validate_request_fingerprint(check)
    _validate_receipt_spend(parsed, registry=registry, schedule=schedule)
    for check in parsed.checks:
        _validate_claim_execution_binding(check)
    expected_checks = tuple(
        sorted(
            _current_checks(parsed.events).values(),
            key=lambda item: item.request_key,
        )
    )
    if parsed.checks != expected_checks:
        raise ConfidenceLedgerError("receipt_check_projection_invalid")
    identity_payload = parsed.model_dump(mode="json", exclude={"receipt_id"})
    if parsed.receipt_id != _identity("confidence-ledger", identity_payload):
        raise ConfidenceLedgerError("receipt_identity_invalid")
    return parsed


def validate_confidence_ledger_receipt(
    receipt: ConfidenceLedgerReceipt | Mapping[str, object],
    *,
    session: ConfidenceLedgerSession,
) -> ConfidenceLedgerReceipt:
    """Structurally recompute a receipt from owners and the canonical head."""

    parsed = validate_confidence_ledger_receipt_structure(
        receipt,
        registry=session.registry,
    )
    canonical = session.receipt()
    if (
        parsed.scope_id != canonical.scope_id
        or parsed.head_event_id != canonical.head_event_id
        or parsed.head_event_ref != canonical.head_event_ref
    ):
        raise ConfidenceLedgerError("receipt_not_canonical_head")
    if parsed != canonical:
        raise ConfidenceLedgerError("receipt_recomputation_mismatch")
    for check in canonical.checks:
        if check.deterministic_proof and check.outcome in {"supported", "not_supported"}:
            if check.owner_binding is None:  # pragma: no cover - structural guard above.
                raise ConfidenceLedgerError("owner_binding_missing")
            binding, supports = session._resolve_bind_verify_owner(check)
            if binding != check.owner_binding or supports != check.supports_obligation:
                raise ConfidenceLedgerError("owner_reverification_failed")
    return canonical


def project_n9_promotion_certificate(
    receipt: ConfidenceLedgerReceipt | Mapping[str, object],
    *,
    session: ConfidenceLedgerSession,
) -> N9PromotionCertificateProjection:
    """Project only promotion-role rows and current-head provenance for N9."""

    validated = validate_confidence_ledger_receipt(receipt, session=session)
    receipt_ref = session.persist_receipt(validated)
    rows = tuple(
        N9PromotionLedgerRow(
            obligation_class=check.obligation_class,
            instrument_id=check.instrument_id,
            instrument_family=check.instrument_family,
            certificate_ref=check.certificate_ref,
            certificate_role="promotion",
            claim_polarity="false_accept",
            check_id=check.check_id,
            execution_status=check.execution_status,
            outcome=check.outcome,
            execution_ordinal=check.execution_ordinal,
            execution_id=check.execution_id,
            spend=check.spend,
            spend_decimal=check.spend_decimal,
            anytime_valid=check.anytime_valid,
            supports_obligation=check.supports_obligation,
            eligible_for_promotion=check.eligible_for_promotion,
            claim_execution_binding_hash=check.claim_execution_binding_hash,
        )
        for check in validated.checks
        if check.certificate_role == "promotion" and check.claim_polarity == "false_accept"
    )
    payload: dict[str, Any] = {
        "schema_version": CONFIDENCE_LEDGER_SCHEMA_VERSION,
        "projection_scope": "n9_promotion_certificate",
        "authority_provenance": validated.authority_provenance,
        "deployment_identity": validated.deployment_identity,
        "risk_scope": session.risk_scope,
        "scope_id": validated.scope_id,
        "ledger_root_id": validated.ledger_root_id,
        "ledger_root_ref": validated.ledger_root_ref,
        "head_event_id": validated.head_event_id,
        "head_event_ref": validated.head_event_ref,
        "ledger_receipt_id": validated.receipt_id,
        "ledger_receipt_ref": receipt_ref,
        "registry_content_hash": validated.registry_content_hash,
        "schedule_projection_hash": validated.schedule_projection_hash,
        "promotion_rows": rows,
        "total_spend": validated.total_spend,
        "total_spend_decimal": validated.total_spend_decimal,
        "budget_delta": validated.budget_delta,
        "budget_delta_decimal": validated.budget_delta_decimal,
        "within_budget": validated.within_budget,
        "good_event_clause": GOOD_EVENT_CLAUSE,
        "conditionality_clause": CONDITIONAL_VALIDITY_CLAUSE,
        "maintained_assumptions": _MAINTAINED_ASSUMPTIONS,
    }
    payload["projection_hash"] = _content_hash(payload)
    return N9PromotionCertificateProjection.model_validate(payload)


def project_n12_epoch_reference(
    receipt: ConfidenceLedgerReceipt | Mapping[str, object],
    *,
    session: ConfidenceLedgerSession,
) -> N12EpochReferenceProjection:
    """Project future epoch locators without implementing N12 epochs."""

    validated = validate_confidence_ledger_receipt(receipt, session=session)
    receipt_ref = session.persist_receipt(validated)
    scope = session.risk_scope
    payload: dict[str, Any] = {
        "schema_version": CONFIDENCE_LEDGER_SCHEMA_VERSION,
        "projection_scope": "n12_epoch_reference",
        "authority_provenance": validated.authority_provenance,
        "deployment_identity": validated.deployment_identity,
        "scope_id": validated.scope_id,
        "ledger_root_id": validated.ledger_root_id,
        "ledger_root_ref": validated.ledger_root_ref,
        "head_event_id": validated.head_event_id,
        "head_event_ref": validated.head_event_ref,
        "ledger_receipt_id": validated.receipt_id,
        "ledger_receipt_ref": receipt_ref,
        "epoch_ref": scope.epoch_ref,
        "model_ref": scope.model_ref,
        "rule_ref": scope.rule_ref,
        "schema_ref": scope.schema_ref,
        "validity": "epoch_not_implemented",
        "conditionality_clause": CONDITIONAL_VALIDITY_CLAUSE,
        "maintained_assumptions": _MAINTAINED_ASSUMPTIONS,
    }
    payload["projection_hash"] = _content_hash(payload)
    return N12EpochReferenceProjection.model_validate(payload)


def _validate_receipt_event_lineage(
    receipt: ConfidenceLedgerReceipt,
    *,
    registry: ConfidenceLedgerRegistry,
) -> None:
    events = receipt.events
    if events:
        tail = events[-1]
        if (
            receipt.head_event_id != tail.event_id
            or receipt.head_event_ref != tail.event_ref
            or tail.revision != len(events)
        ):
            raise ConfidenceLedgerError("ledger_event_chain_invalid")
    elif (
        receipt.head_event_id != receipt.ledger_root_id
        or receipt.head_event_ref != receipt.ledger_root_ref
    ):
        raise ConfidenceLedgerError("ledger_event_chain_invalid")
    for event in events:
        stored = _StoredLedgerEvent.model_validate(
            event.model_dump(mode="json", exclude={"event_ref"})
        )
        if (
            event.scope_id != receipt.scope_id
            or event.ledger_root_id != receipt.ledger_root_id
            or event.check.scope_id != receipt.scope_id
            or event.event_id != _recompute_event_id(stored)
            or event.check.event_id != event.event_id
            or event.check.check_id != _recompute_check_id(event.check)
        ):
            raise ConfidenceLedgerError("ledger_event_chain_invalid")
    _validate_chain_semantics(
        events,
        scope_id=receipt.scope_id,
        ledger_root_id=receipt.ledger_root_id,
        ledger_root_ref=receipt.ledger_root_ref,
        registry=registry,
    )


def _validate_chain_semantics(
    events: tuple[ConfidenceLedgerEvent, ...],
    *,
    scope_id: str,
    ledger_root_id: str,
    ledger_root_ref: str,
    registry: ConfidenceLedgerRegistry,
) -> None:
    parent_id = ledger_root_id
    parent_ref = ledger_root_ref
    requests: dict[str, ConfidenceLedgerCheck] = {}
    ordinals: set[int] = set()
    for index, event in enumerate(events, start=1):
        check = event.check
        if (
            event.revision != index
            or event.scope_id != scope_id
            or event.ledger_root_id != ledger_root_id
            or event.parent_event_id != parent_id
            or event.parent_event_ref != parent_ref
        ):
            raise ConfidenceLedgerError("ledger_event_chain_invalid")
        expected_event_type = (
            "prepared"
            if check.outcome == "prepared"
            else "started"
            if check.outcome == "started"
            else "completed"
        )
        if event.event_type != expected_event_type:
            raise ConfidenceLedgerError("ledger_transition_invalid")
        _validate_check_registry_binding(check, registry=registry)
        _validate_request_fingerprint(check)
        _validate_claim_execution_binding(check)
        previous = requests.get(check.request_key)
        if previous is None and event.event_type not in {"prepared", "completed"}:
            raise ConfidenceLedgerError("started_without_preparation")
        if previous is None:
            if check.outcome not in {"prepared", "preflight_refusal"}:
                raise ConfidenceLedgerError("started_without_preparation")
            if check.prepared_event_id != event.event_id:
                raise ConfidenceLedgerError("prepared_event_binding_invalid")
            _validate_precheck_history(
                check,
                scope_id=scope_id,
                ledger_root_id=ledger_root_id,
                ledger_root_ref=ledger_root_ref,
                parent_event_id=event.parent_event_id,
                parent_event_ref=event.parent_event_ref,
                prior_revision=index - 1,
                current_checks=requests,
            )
        if previous is not None:
            if previous.request_fingerprint != event.check.request_fingerprint:
                raise ConfidenceLedgerError("idempotency_binding_mismatch")
            _validate_prepared_binding_unchanged(previous, check)
            allowed = {
                ("prepared", "started"),
                ("prepared", "cancelled"),
                ("started", "started"),
                ("started", "supported"),
                ("started", "not_supported"),
                ("started", "owner_refused"),
                ("started", "owner_error"),
                ("started", "recovered_crash"),
                ("started", "refused"),
            }
            if (previous.outcome, event.check.outcome) not in allowed:
                raise ConfidenceLedgerError("ledger_transition_invalid")
            if (
                check.outcome == "started"
                and check.started_event_id != event.event_id
                and previous.outcome != "started"
            ):
                raise ConfidenceLedgerError("started_event_binding_invalid")
            if previous.outcome == "started":
                _validate_started_binding_unchanged(previous, check)
                if check.outcome == "started":
                    expected_claim = _identity(
                        "confidence-owner-invocation",
                        {
                            "scope_id": check.scope_id,
                            "execution_id": check.execution_id,
                            "request_fingerprint": check.request_fingerprint,
                            "lock_identity": check.owner_invocation_lock_identity,
                        },
                    )
                    if (
                        previous.owner_invocation_claim_id is not None
                        or check.owner_invocation_claim_id != expected_claim
                    ):
                        raise ConfidenceLedgerError("owner_invocation_claim_invalid")
                elif (
                    check.outcome != "recovered_crash"
                    and previous.owner_invocation_claim_id is None
                ):
                    raise ConfidenceLedgerError("owner_invocation_claim_missing")
                elif check.owner_invocation_claim_id != previous.owner_invocation_claim_id:
                    raise ConfidenceLedgerError("owner_invocation_claim_changed")
            elif check.outcome == "started" and check.owner_invocation_claim_id is not None:
                raise ConfidenceLedgerError("owner_invocation_claim_before_start")
        if check.execution_ordinal is not None and (
            previous is None or previous.execution_ordinal is None
        ):
            if check.execution_ordinal in ordinals:
                raise ConfidenceLedgerError("duplicate_schedule_slot")
            if check.execution_ordinal != len(ordinals):
                raise ConfidenceLedgerError("schedule_slot_missing")
            ordinals.add(check.execution_ordinal)
        requests[check.request_key] = check
        parent_id = event.event_id
        parent_ref = event.event_ref


def _validate_precheck_history(
    check: ConfidenceLedgerCheck,
    *,
    scope_id: str,
    ledger_root_id: str,
    ledger_root_ref: str,
    parent_event_id: str,
    parent_event_ref: str,
    prior_revision: int,
    current_checks: Mapping[str, ConfidenceLedgerCheck],
) -> None:
    ordinals = [
        item.execution_ordinal
        for item in current_checks.values()
        if item.execution_ordinal is not None
    ]
    base = {
        "scope_id": scope_id,
        "ledger_root_id": ledger_root_id,
        "ledger_root_ref": ledger_root_ref,
        "head_event_id": parent_event_id,
        "head_event_ref": parent_event_ref,
        "revision": prior_revision,
        "next_execution_ordinal": max(ordinals, default=-1) + 1,
        "filtration_ref": f"confidence-ledger://{scope_id}/revision/{prior_revision}",
    }
    if check.filtration_ref != base[
        "filtration_ref"
    ] or check.precheck_history_hash != _content_hash(base):
        raise ConfidenceLedgerError("precheck_history_binding_invalid")


def _validate_request_fingerprint(check: ConfidenceLedgerCheck) -> None:
    claim = PredictableClaimSpec(
        claim_ref=check.claim_ref,
        null_ref=check.null_ref,
        claim_scope_ref=check.claim_scope_ref,
        data_window_ref=check.data_window_ref,
        certificate_role=check.certificate_role,
        claim_polarity=check.claim_polarity,
    )
    expected = _content_hash(
        {
            "request_key": check.request_key,
            "obligation_class": check.obligation_class,
            "instrument_id": check.instrument_id,
            "certificate_ref": check.certificate_ref,
            "certificate_class": check.certificate_class,
            "claim": claim,
        }
    )
    if check.request_fingerprint != expected:
        raise ConfidenceLedgerError("request_fingerprint_invalid")


def _validate_claim_execution_binding(check: ConfidenceLedgerCheck) -> None:
    if check.execution_id is None:
        expected = _content_hash(
            {
                "request_fingerprint": check.request_fingerprint,
                "history": check.precheck_history_hash,
                "execution": None,
                "spend": _rational_spec(Fraction()),
            }
        )
    else:
        if check.execution_ordinal is None or check.schedule_query_index is None:
            raise ConfidenceLedgerError("execution_identity_incomplete")
        expected = _claim_execution_binding_hash(
            check=check,
            execution_id=check.execution_id,
            execution_ordinal=check.execution_ordinal,
            schedule_query_index=check.schedule_query_index,
            spend=check.spend.fraction,
        )
    if check.claim_execution_binding_hash != expected:
        raise ConfidenceLedgerError("claim_execution_binding_invalid")


def _validate_prepared_binding_unchanged(
    previous: ConfidenceLedgerCheck,
    current: ConfidenceLedgerCheck,
) -> None:
    fields = (
        "request_key",
        "request_fingerprint",
        "obligation_class",
        "instrument_id",
        "instrument_family",
        "proof_profile_id",
        "certificate_ref",
        "certificate_class",
        "certificate_route_hash",
        "certificate_role",
        "claim_polarity",
        "claim_ref",
        "null_ref",
        "claim_scope_ref",
        "data_window_ref",
        "filtration_ref",
        "precheck_history_hash",
        "registry_content_hash",
        "instrument_definition_hash",
        "proof_profile_hash",
        "prepared_event_id",
        "deterministic_proof",
        "anytime_valid",
    )
    if any(getattr(previous, field) != getattr(current, field) for field in fields):
        raise ConfidenceLedgerError("prepared_check_binding_changed")


def _validate_started_binding_unchanged(
    previous: ConfidenceLedgerCheck,
    current: ConfidenceLedgerCheck,
) -> None:
    fields = (
        "started_event_id",
        "execution_ordinal",
        "schedule_query_index",
        "execution_id",
        "owner_invocation_lock_identity",
        "spend",
        "spend_decimal",
        "claim_execution_binding_hash",
    )
    if any(getattr(previous, field) != getattr(current, field) for field in fields):
        raise ConfidenceLedgerError("started_check_binding_changed")


def _instrument_preflight_refusal(
    *,
    instrument: InstrumentDefinition,
    profile: InstrumentProofProfile,
    certificate_role: CertificateRole,
) -> str | None:
    if certificate_role not in instrument.certificate_roles:
        return "certificate_role_not_permitted"
    if profile.proof_kernel_id == "ineligible_v1":
        return profile.refusal_code or "non_anytime_valid"
    if profile.proof_kernel_id == "owner_theorem_unavailable_v1":
        return profile.refusal_code or "owner_theorem_unavailable"
    if not profile.deterministic and not profile.anytime_valid:
        return "non_anytime_valid"
    return None


def _validate_check_registry_binding(
    check: ConfidenceLedgerCheck,
    *,
    registry: ConfidenceLedgerRegistry,
) -> None:
    if check.registry_content_hash != registry.content_hash:
        raise ConfidenceLedgerError("registry_binding_invalid")
    try:
        instrument = registry.resolve_instrument(check.instrument_id)
    except ConfidenceLedgerError as exc:
        if exc.code != "unknown_instrument":
            raise
        unknown_binding = (
            check.instrument_family == "unknown_instrument"
            and check.proof_profile_id == "unknown_profile"
            and check.instrument_definition_hash is None
            and check.proof_profile_hash is None
            and not check.deterministic_proof
            and not check.anytime_valid
            and check.execution_status == "refused"
            and check.outcome == "preflight_refusal"
            and check.refusal_code == "unknown_instrument"
            and check.execution_id is None
            and check.spend.fraction == 0
            and not check.supports_obligation
            and not check.eligible_for_promotion
        )
        if not unknown_binding:
            raise ConfidenceLedgerError("instrument_registry_binding_invalid") from exc
        return
    profile = registry.resolve_proof_profile(instrument.proof_profile_id)
    if (
        check.instrument_family != instrument.instrument_family
        or check.proof_profile_id != instrument.proof_profile_id
        or check.instrument_definition_hash != _content_hash(instrument)
        or check.proof_profile_hash != _content_hash(profile)
        or check.deterministic_proof is not profile.deterministic
        or check.anytime_valid is not profile.anytime_valid
    ):
        raise ConfidenceLedgerError("instrument_registry_binding_invalid")
    preflight_refusal = _instrument_preflight_refusal(
        instrument=instrument,
        profile=profile,
        certificate_role=check.certificate_role,
    )
    route: CertificateClassRoute | None = None
    if preflight_refusal is None and (profile.deterministic or check.certificate_class is not None):
        if check.certificate_class is None:
            preflight_refusal = "certificate_class_route_missing"
        else:
            try:
                route = registry.resolve_certificate_route(check.certificate_class)
            except ConfidenceLedgerError as exc:
                preflight_refusal = exc.code
            else:
                if (
                    route.instrument_id != check.instrument_id
                    or route.obligation_class != check.obligation_class
                    or route.certificate_role != check.certificate_role
                    or route.claim_polarity != check.claim_polarity
                ):
                    preflight_refusal = "certificate_class_route_mismatch"
    expected_route_hash = _content_hash(route) if route is not None else None
    if check.certificate_route_hash != expected_route_hash:
        raise ConfidenceLedgerError("certificate_class_route_mismatch")
    if preflight_refusal is not None:
        if not (
            check.execution_status == "refused"
            and check.outcome == "preflight_refusal"
            and check.refusal_code == preflight_refusal
            and check.execution_id is None
            and check.spend.fraction == 0
            and not check.supports_obligation
            and not check.eligible_for_promotion
        ):
            raise ConfidenceLedgerError("instrument_registry_binding_invalid")
    elif check.outcome == "preflight_refusal":
        raise ConfidenceLedgerError("instrument_registry_binding_invalid")
    if (
        check.supports_obligation or check.eligible_for_promotion
    ) and not profile.permits_obligation_satisfaction:
        raise ConfidenceLedgerError("instrument_registry_binding_invalid")
    if profile.deterministic and check.outcome in {"supported", "not_supported"}:
        if check.owner_binding is None:
            raise ConfidenceLedgerError("owner_binding_missing")
        if route is None:
            raise ConfidenceLedgerError("certificate_class_route_missing")
        binding = check.owner_binding
        if (
            binding.certificate_ref != check.certificate_ref
            or binding.certificate_class != route.certificate_class
            or binding.certificate_route_hash != _content_hash(route)
            or binding.owner_ref != route.owner_ref
            or binding.verifier_kernel_id != route.verifier_kernel_id
            or binding.verifier_ref != route.verifier_ref
        ):
            raise ConfidenceLedgerError("owner_verifier_provenance_mismatch")


def _validate_receipt_spend(
    receipt: ConfidenceLedgerReceipt,
    *,
    registry: ConfidenceLedgerRegistry,
    schedule: PredictableScheduleProfile,
) -> None:
    budget = registry.policy.delta.fraction
    recorded_total = receipt.total_spend.fraction
    if recorded_total > budget or not receipt.within_budget:
        raise ConfidenceLedgerError("over_spend")
    recomputed_total = Fraction()
    for check in receipt.checks:
        if check.deterministic_proof and check.spend.fraction:
            raise ConfidenceLedgerError("deterministic_proof_nonzero_spend")
        if check.started_event_id is None and check.spend.fraction:
            raise ConfidenceLedgerError("spend_for_unexecuted_check")
        recomputed_total += check.spend.fraction
    executed = sorted(
        (check for check in receipt.checks if check.execution_ordinal is not None),
        key=lambda check: int(check.execution_ordinal or 0),
    )
    ordinals = tuple(check.execution_ordinal for check in executed)
    if len(set(ordinals)) != len(ordinals):
        raise ConfidenceLedgerError("duplicate_schedule_slot")
    if ordinals != tuple(range(len(executed))):
        raise ConfidenceLedgerError("schedule_slot_missing")
    for check in executed:
        if check.execution_ordinal is None:  # pragma: no cover - filtered above.
            raise ConfidenceLedgerError("schedule_slot_missing")
        expected_index = check.execution_ordinal
        if check.schedule_query_index != expected_index:
            raise ConfidenceLedgerError("schedule_slot_missing")
        instrument = registry.resolve_instrument(check.instrument_id)
        profile = registry.resolve_proof_profile(instrument.proof_profile_id)
        expected_spend = Fraction()
        if not profile.deterministic:
            expected_spend = _schedule_alpha(
                delta=budget,
                obligation_weight=registry.obligation_weights[check.obligation_class],
                query_index=expected_index,
                schedule=schedule,
            )
        if check.spend.fraction != expected_spend:
            raise ConfidenceLedgerError("forged_spend_row")
    if recomputed_total != recorded_total:
        raise ConfidenceLedgerError("forged_spend_row")
    if any(
        check.spend_decimal != _fraction_display(check.spend.fraction) for check in receipt.checks
    ):
        raise ConfidenceLedgerError("spend_decimal_drift")
    if receipt.total_spend_decimal != _fraction_display(recorded_total):
        raise ConfidenceLedgerError("spend_decimal_drift")
    if receipt.within_budget is not (recorded_total <= budget):
        raise ConfidenceLedgerError("forged_spend_row")


def _current_checks(events: tuple[ConfidenceLedgerEvent, ...]) -> dict[str, ConfidenceLedgerCheck]:
    result: dict[str, ConfidenceLedgerCheck] = {}
    for event in events:
        result[event.check.request_key] = event.check
    return result


def _claim_execution_binding_hash(
    *,
    check: ConfidenceLedgerCheck,
    execution_id: str,
    execution_ordinal: int,
    schedule_query_index: int,
    spend: Fraction,
) -> str:
    return _content_hash(
        {
            "scope_id": check.scope_id,
            "request_fingerprint": check.request_fingerprint,
            "claim_ref": check.claim_ref,
            "null_ref": check.null_ref,
            "claim_scope_ref": check.claim_scope_ref,
            "data_window_ref": check.data_window_ref,
            "filtration_ref": check.filtration_ref,
            "precheck_history_hash": check.precheck_history_hash,
            "certificate_role": check.certificate_role,
            "claim_polarity": check.claim_polarity,
            "execution_id": execution_id,
            "execution_ordinal": execution_ordinal,
            "schedule_query_index": schedule_query_index,
            "reserved_alpha": _rational_spec(spend),
            "registry_content_hash": check.registry_content_hash,
            "instrument_definition_hash": check.instrument_definition_hash,
            "proof_profile_hash": check.proof_profile_hash,
        }
    )


def _event_identity_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    check = payload["check"]
    if isinstance(check, ConfidenceLedgerCheck):
        check_payload = check.model_dump(mode="json")
    else:
        check_payload = dict(check)
    for key in ("event_id", "check_id", "prepared_event_id", "started_event_id"):
        check_payload.pop(key, None)
    return {
        "event_type": payload["event_type"],
        "scope_id": payload["scope_id"],
        "ledger_root_id": payload["ledger_root_id"],
        "revision": payload["revision"],
        "parent_event_id": payload["parent_event_id"],
        "parent_event_ref": payload["parent_event_ref"],
        "check": check_payload,
    }


def _recompute_event_id(event: _StoredLedgerEvent) -> str:
    return _identity(
        "confidence-event",
        _event_identity_payload(event.model_dump(mode="python")),
    )


def _recompute_check_id(check: ConfidenceLedgerCheck) -> str:
    return _identity(
        "confidence-check",
        check.model_dump(mode="json", exclude={"check_id"}),
    )


def _schedule_alpha(
    *,
    delta: Fraction,
    obligation_weight: Fraction,
    query_index: int,
    schedule: PredictableScheduleProfile,
) -> Fraction:
    if schedule.proof_kernel_id != "basel_square_v1":
        raise ConfidenceLedgerError("unknown_schedule_proof_kernel")
    return (
        delta
        * obligation_weight
        * schedule.mass.fraction
        * _BASEL_COEFFICIENT_LOWER
        / ((query_index + 1) ** 2)
    )


def _schedule_projection_hash(
    registry: ConfidenceLedgerRegistry, schedule: PredictableScheduleProfile
) -> str:
    return _content_hash(
        {
            "schedule": schedule,
            "kernel": "6/(pi^2*(t+1)^2)",
            "certified_rational_coefficient": _rational_spec(_BASEL_COEFFICIENT_LOWER),
            "delta": registry.policy.delta,
            "obligation_weights": {
                item.value: _rational_spec(weight)
                for item, weight in registry.obligation_weights.items()
            },
        }
    )


def _validate_proof_profile_contract(profile: InstrumentProofProfile) -> None:
    expected: dict[str, tuple[bool, bool, bool]] = {
        "closed_constant_unit_e_process_v1": (False, True, False),
        "deterministic_owner_v1": (True, True, True),
        "ineligible_v1": (False, False, False),
        "owner_theorem_unavailable_v1": (False, False, False),
    }
    if (
        profile.deterministic,
        profile.anytime_valid,
        profile.permits_obligation_satisfaction,
    ) != expected[profile.proof_kernel_id]:
        raise ValueError("proof_profile_kernel_contract_mismatch")
    if profile.proof_kernel_id in {"ineligible_v1", "owner_theorem_unavailable_v1"}:
        if profile.refusal_code is None:
            raise ValueError("ineligible_profile_refusal_missing")
    elif profile.refusal_code is not None:
        raise ValueError("eligible_profile_refusal_forbidden")


def _path_thread_lock(path: Path) -> threading.RLock:
    with _LOCKS_GUARD:
        return _PATH_LOCKS.setdefault(path, threading.RLock())


def _path_invocation_thread_lock(path: Path) -> threading.Lock:
    with _INVOCATION_LOCKS_GUARD:
        return _INVOCATION_LOCKS.setdefault(path, threading.Lock())


def _scope_journal_genesis_hash(scope_id: str) -> str:
    return _content_hash({"scope_id": scope_id, "journal": "genesis"})


def _scope_journal_record_hash(record: _ScopeJournalRecord) -> str:
    return _content_hash(record.model_dump(mode="json", exclude={"record_hash"}))


def _journal_artifact_contract(
    artifact_kind: Literal["event", "receipt", "deployment_drift_poison"],
) -> tuple[str, artifacts.SchemaInfo]:
    return {
        "event": ("runtime.quality.confidence_ledger.event", _EVENT_SCHEMA),
        "receipt": ("runtime.quality.confidence_ledger.receipt", _RECEIPT_SCHEMA),
        "deployment_drift_poison": (
            "runtime.quality.confidence_ledger.deployment_drift_poison",
            _DEPLOYMENT_DRIFT_POISON_SCHEMA,
        ),
    }[artifact_kind]


def _rational_spec(value: Fraction) -> RationalSpec:
    return RationalSpec(numerator=value.numerator, denominator=value.denominator)


def _fraction_display(value: Fraction) -> str:
    if value == 0:
        return "0"
    scale = 10**_DISPLAY_DECIMAL_PLACES
    scaled = value.numerator * scale // value.denominator
    whole, remainder = divmod(scaled, scale)
    if remainder == 0:
        return str(whole)
    decimals = f"{remainder:0{_DISPLAY_DECIMAL_PLACES}d}".rstrip("0")
    return f"{whole}.{decimals}"


def _loaded_policy_engine_root() -> Path:
    """Return the checkout that supplied the currently imported runtime module."""

    return Path(__file__).resolve().parents[4]


def _policy_engine_deployment_identity(repo_root: Path) -> str:
    """Bind authority to loaded deployment bytes without persisting absolute paths."""

    relative_paths = [Path("pyproject.toml"), Path("uv.lock")]
    source_root = repo_root / "src/polisyos"
    try:
        relative_paths.extend(
            sorted(
                (path.relative_to(repo_root) for path in source_root.rglob("*.py")),
                key=lambda path: path.as_posix(),
            )
        )
    except OSError as exc:
        raise ConfidenceLedgerError("canonical_deployment_identity_invalid") from exc
    if len(relative_paths) == 2:
        raise ConfidenceLedgerError("canonical_deployment_identity_invalid")
    files: dict[str, str] = {}
    for relative in relative_paths:
        path = repo_root / relative
        try:
            content = path.read_bytes()
        except OSError as exc:
            raise ConfidenceLedgerError(
                "canonical_deployment_identity_invalid", relative.as_posix()
            ) from exc
        files[relative.as_posix()] = f"sha256:{hashlib.sha256(content).hexdigest()}"
    return _identity(
        "policy-engine-deployment",
        {
            "files": files,
            "python_runtime": _python_runtime_manifest(),
        },
    )


def _python_runtime_manifest() -> dict[str, object]:
    """Return ABI-relevant interpreter identity without machine-local paths."""

    version = sys.version_info
    return {
        "implementation": sys.implementation.name,
        "version": {
            "major": version.major,
            "minor": version.minor,
            "micro": version.micro,
            "releaselevel": version.releaselevel,
            "serial": version.serial,
        },
        "cache_tag": sys.implementation.cache_tag,
        "hexversion": sys.hexversion,
        "abiflags": getattr(sys, "abiflags", ""),
        "byteorder": sys.byteorder,
        "soabi": sysconfig.get_config_var("SOABI"),
        "multiarch": sysconfig.get_config_var("MULTIARCH"),
        "py_debug": sysconfig.get_config_var("Py_DEBUG"),
        "gil_disabled": sysconfig.get_config_var("Py_GIL_DISABLED"),
    }


def _require_unique(values: Iterable[str], code: str) -> None:
    materialized = tuple(values)
    if len(materialized) != len(set(materialized)):
        raise ValueError(code)


def _identity(prefix: str, payload: object) -> str:
    return f"{prefix}:{_content_hash(payload)}"


def _content_hash(payload: object) -> str:
    return "sha256:" + hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _cas_json_artifact_ref(payload: object) -> str:
    data = canon.to_canonical_bytes(_jsonable(payload), _CAS_CANON_SPEC)
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _canonical_json(payload: object) -> str:
    return json.dumps(
        _jsonable(payload),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def _jsonable(payload: object) -> object:
    if isinstance(payload, BaseModel):
        return payload.model_dump(mode="json")
    if isinstance(payload, Mapping):
        return {str(key): _jsonable(value) for key, value in payload.items()}
    if isinstance(payload, (tuple, list)):
        return [_jsonable(value) for value in payload]
    if isinstance(payload, PromotionObligationClass):
        return payload.value
    if isinstance(payload, Path):
        return payload.as_posix()
    if isinstance(payload, (str, int, bool)) or payload is None:
        return payload
    raise TypeError(f"non-canonical confidence-ledger value: {type(payload).__name__}")


__all__ = [
    "CONDITIONAL_VALIDITY_CLAUSE",
    "GOOD_EVENT_CLAUSE",
    "ConfidenceLedgerCheck",
    "ConfidenceLedgerError",
    "ConfidenceLedgerEvent",
    "ConfidenceLedgerHistoryToken",
    "ConfidenceLedgerReceipt",
    "ConfidenceLedgerRegistry",
    "ConfidenceLedgerSession",
    "ConfidenceRiskBudgetScope",
    "N9PromotionCertificateProjection",
    "N9PromotionLedgerRow",
    "N12EpochReferenceProjection",
    "OwnerCertificateBinding",
    "OwnerCertificateEvidence",
    "OwnerCertificateVerification",
    "PredictableClaimSpec",
    "RationalSpec",
    "load_confidence_ledger_registry",
    "project_n9_promotion_certificate",
    "project_n12_epoch_reference",
    "recompute_confidence_schedule_projection_hash",
    "validate_confidence_ledger_receipt",
    "validate_confidence_ledger_receipt_structure",
]
