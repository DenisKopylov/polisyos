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

import ast
import builtins as _builtins
import functools
import hashlib
import importlib
import importlib.util
import inspect as _inspect
import json
import os
import sys
import sysconfig
import threading
import tomllib
import types
import typing
from collections.abc import Callable, Iterable, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from enum import Enum
from fractions import Fraction
from pathlib import Path
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.common import serialization
from polisyos.core import artifacts, canon
from polisyos.core.artifacts.backends.config import ArtifactStoreConfig, build_artifact_store
from polisyos.fabric import atomic_write_json
from polisyos.pdc import PromotionObligationClass

_LEDGER_MODULE_SOURCE_PATH = Path(__file__).resolve()

CONFIDENCE_LEDGER_REGISTRY_SCHEMA_VERSION = "policyos.runtime.confidence_ledger.registry.v1"
CONFIDENCE_LEDGER_SCHEMA_VERSION = "policyos.runtime.confidence_ledger.v1"
DEPLOYMENT_IDENTITY_OBSERVATION_SCHEMA_VERSION = (
    "policyos.runtime.confidence_ledger.loaded_deployment_identity.v1"
)
N9_PROMOTION_SEMANTIC_PROJECTION_RULE_VERSION = (
    "policyos.runtime.quality.confidence_ledger.n9_promotion_semantic_projection.v1"
)
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
        "n8_calibration_receipt_recompute_v1",
        "n8_data_trust_recompute_v1",
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
type _DeploymentFileFence = tuple[str, int, int, int, int, int]
type _DeploymentQuickFence = tuple[tuple[_DeploymentFileFence, ...], str]
_LRU_CACHE_WRAPPER_TYPE = type(functools.lru_cache(maxsize=1)(lambda: None))


@dataclass(frozen=True)
class _LoaderOwnedCallableSlot:
    """One source-declared callable binding owned by a module or local class."""

    owner_path: tuple[str, ...]
    binding_name: str
    descriptor_kind: str
    property_accessors: tuple[str, ...]
    decorators: tuple[str, ...]
    source_firstlinenos: tuple[tuple[str, int], ...]
    lru_cache_parameters: tuple[tuple[str, int, int | None, bool], ...]

    @property
    def qualname(self) -> str:
        """Return the loader qualname for the declared binding."""

        return ".".join((*self.owner_path, self.binding_name))


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
_LEDGER_ARTIFACT_MEDIA_TYPE = "application/json"
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


class PromotionCertificateOffer(_StrictModel):
    """Owner candidate resolved through registry data before N9 can use it."""

    request_key: str = Field(min_length=1)
    certificate_class: str = Field(min_length=1)
    certificate_ref: str = Field(min_length=1)
    owner_projection_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    claim: PredictableClaimSpec

    @model_validator(mode="after")
    def _is_a_promotion_candidate_only(self) -> Self:
        if (
            self.claim.certificate_role != "promotion"
            or self.claim.claim_polarity != "false_accept"
        ):
            raise ValueError("n9_certificate_offer_role_invalid")
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
    ledger_root_id: str = Field(pattern=r"^confidence-ledger-root:sha256:[0-9a-f]{64}$")
    ledger_root_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    authority_provenance: Literal["canonical_repo"]
    expected_deployment_identity: str = Field(
        pattern=r"^policy-engine-deployment:sha256:[0-9a-f]{64}$"
    )
    observed_deployment_identity: str = Field(
        pattern=r"^policy-engine-deployment:sha256:[0-9a-f]{64}$"
    )
    reason: Literal["canonical_deployment_identity_changed"]
    poison_id: str = Field(pattern=r"^confidence-deployment-drift-poison:sha256:[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _requires_actual_drift(self) -> Self:
        if self.expected_deployment_identity == self.observed_deployment_identity:
            raise ValueError("deployment_drift_poison_identity_equal")
        return self


class LoadedDeploymentIdentityObservation(_StrictModel):
    """Typed import-time identity supplied by the confidence-ledger owner.

    The identity commits to the owner's canonical deployment baseline (including
    ``uv.lock``) and its loaded-code manifest. It is a capture of the process's
    loaded deployment, not a claim that mutable source files remain current.
    The canonical ledger session performs that separate currentness check when
    authority is requested.
    """

    schema_version: Literal[DEPLOYMENT_IDENTITY_OBSERVATION_SCHEMA_VERSION] = (
        DEPLOYMENT_IDENTITY_OBSERVATION_SCHEMA_VERSION
    )
    status: Literal["established", "not_established"]
    deployment_identity: str | None = Field(
        default=None,
        pattern=r"^policy-engine-deployment:sha256:[0-9a-f]{64}$",
    )
    reason_code: (
        Literal[
            "canonical_loaded_runtime_mismatch",
            "canonical_deployment_identity_invalid",
            "packaged_deployment_identity_issuer_unavailable",
        ]
        | None
    ) = None

    @model_validator(mode="after")
    def _bind_status_to_identity(self) -> Self:
        if self.status == "established":
            if self.deployment_identity is None or self.reason_code is not None:
                raise ValueError("loaded_deployment_identity_observation_invalid")
        elif self.deployment_identity is not None or self.reason_code is None:
            raise ValueError("loaded_deployment_identity_observation_invalid")
        return self


class N6DeploymentCurrentnessObservation(_StrictModel):
    """Identity-bound N6 currentness observation owned by the confidence ledger.

    This observation compares a persisted run's canonical deployment identity
    with the identity captured when the current process loaded. It deliberately
    does not turn source presence, a matching identity, or a source census into
    authority: that requires the separately appointed N6 census and deployment
    identity issuers.
    """

    schema_version: Literal["policyos.runtime.confidence_ledger.n6_currentness_observation.v2"] = (
        "policyos.runtime.confidence_ledger.n6_currentness_observation.v2"
    )
    status: Literal["current", "stale", "not_established"]
    census_verdict: Literal["PASS", "FAIL", "UNRUN"]
    recorded_identity_status: Literal["established", "not_established"] | None = None
    recorded_deployment_identity: str | None = Field(
        default=None,
        pattern=r"^policy-engine-deployment:sha256:[0-9a-f]{64}$",
    )
    loaded_identity_status: Literal["established", "not_established"]
    loaded_deployment_identity: str | None = Field(
        default=None,
        pattern=r"^policy-engine-deployment:sha256:[0-9a-f]{64}$",
    )
    loaded_identity_reason_code: (
        Literal[
            "canonical_loaded_runtime_mismatch",
            "canonical_deployment_identity_invalid",
            "packaged_deployment_identity_issuer_unavailable",
        ]
        | None
    ) = None
    reason_code: Literal[
        "historical_deployment_identity_not_recorded",
        "loaded_deployment_identity_not_established",
        "generation_cycle_deployment_identity_mismatch",
        "n6_census_issuer_not_appointed",
        "n6_census_not_established",
        "n6_currentness_established",
    ]
    unresolved_by_construction: tuple[str, ...]

    @model_validator(mode="after")
    def _bind_observation(self) -> Self:
        if self.loaded_identity_status == "established":
            if (
                self.loaded_deployment_identity is None
                or self.loaded_identity_reason_code is not None
            ):
                raise ValueError("n6_currentness_loaded_identity_missing")
        elif (
            self.loaded_deployment_identity is not None or self.loaded_identity_reason_code is None
        ):
            raise ValueError("n6_currentness_loaded_identity_unexpected")
        if self.status == "current" and (
            self.census_verdict != "PASS"
            or self.loaded_identity_status != "established"
            or self.recorded_identity_status != "established"
            or self.recorded_deployment_identity != self.loaded_deployment_identity
        ):
            raise ValueError("n6_currentness_current_not_reconciled")
        if self.status == "stale" and (
            self.recorded_identity_status != "established"
            or self.loaded_identity_status != "established"
            or self.recorded_deployment_identity == self.loaded_deployment_identity
        ):
            raise ValueError("n6_currentness_stale_not_reconciled")
        if self.status == "not_established" and self.census_verdict != "UNRUN":
            raise ValueError("n6_currentness_unestablished_requires_unrun_census")
        return self


class PackagedDeploymentIdentityReadiness(_StrictModel):
    """Three-valued installed-package identity readiness from the ledger owner.

    This inspection does not mint a deployment identity or authority receipt.
    It states which installed-package inputs are absent and keeps the N6
    strangle census separate from historical replay.
    """

    schema_version: Literal["policyos.runtime.confidence_ledger.packaged_identity_readiness.v1"] = (
        "policyos.runtime.confidence_ledger.packaged_identity_readiness.v1"
    )
    verdict: Literal["PASS", "FAIL", "UNRUN"]
    inputs: dict[str, str | bool]
    unresolved_by_construction: tuple[
        Literal[
            "packaged_build_identity_issuer_not_appointed",
            "n6_strangle_census_not_established",
            "deployment_authority_issuer_not_appointed",
        ],
        ...,
    ]


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


@dataclass(frozen=True)
class _LedgerArtifactContract:
    """Typed producer, payload-model, and CAS identity for one ledger artifact."""

    kind: str
    schema: artifacts.SchemaInfo
    producer: artifacts.ProducerInfo
    media_type: str
    scope_bound: bool
    payload_model: type[BaseModel] | None


_LEDGER_ARTIFACT_CONTRACTS: Mapping[str, _LedgerArtifactContract] = types.MappingProxyType(
    {
        "scope_anchor": _LedgerArtifactContract(
            kind="runtime.quality.confidence_ledger.scope_anchor",
            schema=_SCOPE_ANCHOR_SCHEMA,
            producer=_LEDGER_PRODUCER,
            media_type=_LEDGER_ARTIFACT_MEDIA_TYPE,
            scope_bound=True,
            payload_model=None,
        ),
        "registry": _LedgerArtifactContract(
            kind="runtime.quality.confidence_ledger.registry",
            schema=_REGISTRY_SCHEMA,
            producer=_LEDGER_PRODUCER,
            media_type=_LEDGER_ARTIFACT_MEDIA_TYPE,
            scope_bound=False,
            payload_model=ConfidenceLedgerRegistry,
        ),
        "root": _LedgerArtifactContract(
            kind="runtime.quality.confidence_ledger.root",
            schema=_ROOT_SCHEMA,
            producer=_LEDGER_PRODUCER,
            media_type=_LEDGER_ARTIFACT_MEDIA_TYPE,
            scope_bound=True,
            payload_model=ConfidenceLedgerRoot,
        ),
        "event": _LedgerArtifactContract(
            kind="runtime.quality.confidence_ledger.event",
            schema=_EVENT_SCHEMA,
            producer=_LEDGER_PRODUCER,
            media_type=_LEDGER_ARTIFACT_MEDIA_TYPE,
            scope_bound=True,
            payload_model=_StoredLedgerEvent,
        ),
        "receipt": _LedgerArtifactContract(
            kind="runtime.quality.confidence_ledger.receipt",
            schema=_RECEIPT_SCHEMA,
            producer=_LEDGER_PRODUCER,
            media_type=_LEDGER_ARTIFACT_MEDIA_TYPE,
            scope_bound=True,
            payload_model=ConfidenceLedgerReceipt,
        ),
        "deployment_drift_poison": _LedgerArtifactContract(
            kind="runtime.quality.confidence_ledger.deployment_drift_poison",
            schema=_DEPLOYMENT_DRIFT_POISON_SCHEMA,
            producer=_LEDGER_PRODUCER,
            media_type=_LEDGER_ARTIFACT_MEDIA_TYPE,
            scope_bound=True,
            payload_model=_DeploymentDriftPoison,
        ),
    }
)


class ConfidenceLedgerSemanticOwnerBinding(_StrictModel):
    """Stable owner/verifier identity from a fully verified live binding."""

    certificate_ref: str = Field(min_length=1)
    certificate_class: str = Field(min_length=1)
    certificate_route_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    owner_ref: str = Field(min_length=1)
    owner_projection_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    verifier_ref: str = Field(min_length=1)
    verifier_kernel_id: str = Field(min_length=1)
    binding_projection_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class ConfidenceLedgerSemanticCheck(_StrictModel):
    """Operational-identity-free projection of one ledger check."""

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
    certificate_route_hash: str | None = Field(
        default=None,
        pattern=r"^sha256:[0-9a-f]{64}$",
    )
    certificate_role: CertificateRole
    claim_polarity: ClaimPolarity
    claim_ref: str = Field(min_length=1)
    null_ref: str = Field(min_length=1)
    claim_scope_ref: str = Field(min_length=1)
    data_window_ref: str = Field(min_length=1)
    filtration_projection_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    registry_content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    instrument_definition_hash: str | None = Field(
        default=None,
        pattern=r"^sha256:[0-9a-f]{64}$",
    )
    proof_profile_hash: str | None = Field(default=None, pattern=r"^sha256:[0-9a-f]{64}$")
    execution_status: ExecutionStatus
    outcome: CompletionOutcome
    execution_ordinal: int | None = Field(default=None, ge=0)
    schedule_query_index: int | None = Field(default=None, ge=0)
    execution_id: str | None = Field(
        default=None,
        pattern=r"^confidence-execution:sha256:[0-9a-f]{64}$",
    )
    deterministic_proof: bool
    anytime_valid: bool
    spend: RationalSpec
    spend_decimal: str = Field(pattern=r"^(0|[0-9]+(?:\.[0-9]+)?)$")
    supports_obligation: bool
    eligible_for_promotion: bool
    refusal_code: str | None = Field(default=None, min_length=1)
    proof_detail: str = Field(min_length=1)
    owner_invocation_claim_projection_hash: str | None = Field(
        default=None,
        pattern=r"^sha256:[0-9a-f]{64}$",
    )
    good_event_id: str | None = Field(
        default=None,
        pattern=r"^confidence-good-event:sha256:[0-9a-f]{64}$",
    )
    owner_binding: ConfidenceLedgerSemanticOwnerBinding | None
    claim_execution_projection_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    check_projection_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class ConfidenceLedgerSemanticEvent(_StrictModel):
    """Stable semantic append transition with an explicit parent hash."""

    event_type: Literal["prepared", "started", "completed"]
    revision: int = Field(gt=0)
    parent_event_projection_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    check: ConfidenceLedgerSemanticCheck
    event_projection_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class ConfidenceLedgerSemanticReceiptProjection(_StrictModel):
    """Stable semantic lineage projected from a verified live receipt."""

    schema_version: Literal[CONFIDENCE_LEDGER_SCHEMA_VERSION]
    projection_scope: Literal[
        "n11_real_accounting_append_lineage",
        "n11_conformance_append_lineage",
    ]
    authority_provenance: SessionAuthorityProvenance
    deployment_identity: str = Field(pattern=r"^policy-engine-deployment:sha256:[0-9a-f]{64}$")
    risk_scope: ConfidenceRiskBudgetScope
    scope_id: str = Field(pattern=r"^confidence-risk-scope:sha256:[0-9a-f]{64}$")
    scope_anchor_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    registry_content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    schedule_profile_id: str = Field(min_length=1)
    schedule_profile_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    schedule_projection_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    budget_delta: RationalSpec
    budget_delta_decimal: str
    root_projection_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    events: tuple[ConfidenceLedgerSemanticEvent, ...]
    checks: tuple[ConfidenceLedgerSemanticCheck, ...]
    head_event_projection_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    total_spend: RationalSpec
    total_spend_decimal: str
    within_budget: bool
    good_event_clause: Literal[GOOD_EVENT_CLAUSE]
    conditionality_clause: Literal[CONDITIONAL_VALIDITY_CLAUSE]
    maintained_assumptions: tuple[Literal["obligation_completeness", "validator_soundness"], ...]
    projection_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class N9PromotionSemanticLedgerProjection(_StrictModel):
    """Stable promotion lineage emitted from a fully verified live ledger.

    The raw N9 certificate remains the byte-complete custody record.  This
    projection is the producer-owned comparison identity for its semantic
    event history; it deliberately omits deployment- and CAS-local locators.
    """

    schema_version: Literal[CONFIDENCE_LEDGER_SCHEMA_VERSION]
    projection_rule_version: Literal[N9_PROMOTION_SEMANTIC_PROJECTION_RULE_VERSION]
    projection_scope: Literal["n9_promotion_semantic_receipt"]
    authority_provenance: SessionAuthorityProvenance
    risk_scope: ConfidenceRiskBudgetScope
    scope_id: str = Field(pattern=r"^confidence-risk-scope:sha256:[0-9a-f]{64}$")
    registry_content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    schedule_profile_id: str = Field(min_length=1)
    schedule_profile_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    schedule_projection_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    budget_delta: RationalSpec
    budget_delta_decimal: str
    root_projection_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    events: tuple[ConfidenceLedgerSemanticEvent, ...]
    checks: tuple[ConfidenceLedgerSemanticCheck, ...]
    head_event_projection_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    total_spend: RationalSpec
    total_spend_decimal: str
    within_budget: bool
    good_event_clause: Literal[GOOD_EVENT_CLAUSE]
    conditionality_clause: Literal[CONDITIONAL_VALIDITY_CLAUSE]
    maintained_assumptions: tuple[Literal["obligation_completeness", "validator_soundness"], ...]
    projection_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _semantic_lineage_is_content_bound(self) -> N9PromotionSemanticLedgerProjection:
        if self.scope_id != self.risk_scope.scope_id:
            raise ValueError("n9_semantic_projection_scope_binding_invalid")
        root_values = _n9_semantic_ledger_root_values(
            receipt=self,
            risk_scope=self.risk_scope,
        )
        if self.root_projection_hash != _content_hash(root_values):
            raise ValueError("n9_semantic_projection_root_hash_drift")
        head_projection_hash = self.root_projection_hash
        current_checks: dict[str, ConfidenceLedgerSemanticCheck] = {}
        filtration_by_request: dict[str, str] = {}
        for event in self.events:
            request_key = event.check.request_key
            if event.event_type == "prepared" or (
                request_key not in filtration_by_request
                and event.check.outcome == "preflight_refusal"
            ):
                if request_key in filtration_by_request:
                    raise ValueError("n9_semantic_projection_duplicate_preparation")
                filtration_by_request[request_key] = head_projection_hash
            if request_key not in filtration_by_request:
                raise ValueError("n9_semantic_projection_missing_preparation")
            if event.check.filtration_projection_hash != filtration_by_request[request_key]:
                raise ValueError("n9_semantic_projection_filtration_drift")
            expected_claim_hash = _semantic_claim_execution_projection_hash_from_projection(
                event.check
            )
            if event.check.claim_execution_projection_hash != expected_claim_hash:
                raise ValueError("n9_semantic_claim_execution_projection_hash_drift")
            expected_check_hash = _content_hash(
                event.check.model_dump(mode="json", exclude={"check_projection_hash"})
            )
            if event.check.check_projection_hash != expected_check_hash:
                raise ValueError("n9_semantic_check_projection_hash_drift")
            event_values = event.model_dump(mode="json", exclude={"event_projection_hash"})
            if event.parent_event_projection_hash != head_projection_hash:
                raise ValueError("n9_semantic_event_parent_drift")
            if event.event_projection_hash != _content_hash(event_values):
                raise ValueError("n9_semantic_event_projection_hash_drift")
            current_checks[request_key] = event.check
            head_projection_hash = event.event_projection_hash
        checks = tuple(current_checks[key] for key in sorted(current_checks))
        if self.checks != checks:
            raise ValueError("n9_semantic_projection_current_check_drift")
        if self.head_event_projection_hash != head_projection_hash:
            raise ValueError("n9_semantic_projection_head_hash_drift")
        if self.total_spend != _rational_spec(
            sum((check.spend.fraction for check in self.checks), Fraction())
        ):
            raise ValueError("n9_semantic_projection_total_spend_drift")
        if self.total_spend_decimal != _fraction_display(self.total_spend.fraction):
            raise ValueError("n9_semantic_projection_total_spend_decimal_drift")
        if self.within_budget is not (self.total_spend.fraction <= self.budget_delta.fraction):
            raise ValueError("n9_semantic_projection_budget_outcome_drift")
        expected_projection_hash = _content_hash(
            self.model_dump(mode="json", exclude={"projection_hash"})
        )
        if self.projection_hash != expected_projection_hash:
            raise ValueError("n9_semantic_projection_hash_drift")
        return self


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
    scope_anchor_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
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

    @model_validator(mode="after")
    def _projection_hash_is_content_bound(self) -> N9PromotionCertificateProjection:
        expected = _content_hash(self.model_dump(mode="json", exclude={"projection_hash"}))
        if self.projection_hash != expected:
            raise ValueError("n9_promotion_projection_hash_drift")
        return self


class N12EpochReferenceProjection(_StrictModel):
    """Future N12 locator projection without implementing epochs."""

    schema_version: Literal[CONFIDENCE_LEDGER_SCHEMA_VERSION]
    projection_scope: Literal["n12_epoch_reference"]
    authority_provenance: SessionAuthorityProvenance
    deployment_identity: str = Field(pattern=r"^policy-engine-deployment:sha256:[0-9a-f]{64}$")
    risk_scope: ConfidenceRiskBudgetScope
    scope_id: str
    scope_anchor_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
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
        "_deployment_quick_fence",
        "_execution_claims",
        "_execution_claims_lock",
        "_head_path",
        "_journal_offset",
        "_journal_path",
        "_journal_prefix_hash",
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
        artifact_store: artifacts.ArtifactStore,
        state_root: Path,
        certificate_resolver: CertificateResolver | None,
        certificate_verifier: CertificateVerifier | None,
    ) -> None:
        loaded_root = _loaded_policy_engine_root()
        _baseline, _quick_fence, deployment_identity = _admit_loaded_runtime(loaded_root)
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
            deployment_identity=deployment_identity,
            deployment_quick_fence=None,
        )

    def _initialize(
        self,
        *,
        registry: ConfidenceLedgerRegistry,
        risk_scope: ConfidenceRiskBudgetScope,
        schedule_profile_id: str | None,
        artifact_store: artifacts.ArtifactStore,
        state_root: Path,
        certificate_resolver: CertificateResolver | None,
        certificate_verifier: CertificateVerifier | None,
        authority_provenance: SessionAuthorityProvenance,
        authority_repo_root: Path | None,
        deployment_identity: str,
        deployment_quick_fence: _DeploymentQuickFence | None,
    ) -> None:
        _assert_ledger_artifact_contracts_current()
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
        self._deployment_quick_fence = deployment_quick_fence
        self._cas_reconciled = False
        self._execution_claims: set[str] = set()
        self._execution_claims_lock = threading.Lock()
        self._state_root.mkdir(parents=True, exist_ok=True)
        scope_hex = risk_scope.scope_id.rsplit(":", 1)[-1]
        self._head_path = self._state_root / f"{scope_hex}.head.json"
        self._lock_path = self._state_root / f"{scope_hex}.lock"
        self._journal_path = self._state_root / f"{scope_hex}.append.wal"
        self._journal_offset = 0
        self._journal_prefix_hash = hashlib.sha256(b"").digest()
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
        (
            _deployment_baseline_value,
            deployment_quick_fence,
            deployment_identity,
        ) = _admit_loaded_runtime(
            root,
        )
        registry = load_confidence_ledger_registry(root / DEFAULT_REGISTRY_RELATIVE_PATH)
        session = object.__new__(cls)
        session._initialize(
            registry=registry,
            risk_scope=risk_scope,
            schedule_profile_id=schedule_profile_id,
            artifact_store=build_artifact_store(
                ArtifactStoreConfig(
                    backend="filesystem",
                    root=str(root / ".polisyos/cas"),
                ),
            ),
            state_root=root / ".polisyos/runtime/confidence_ledger",
            certificate_resolver=None,
            certificate_verifier=None,
            authority_provenance="canonical_repo",
            authority_repo_root=root,
            deployment_identity=deployment_identity,
            deployment_quick_fence=deployment_quick_fence,
        )
        return session

    @classmethod
    def _for_verification(
        cls,
        repo_root: str | Path,
        *,
        risk_scope: ConfidenceRiskBudgetScope,
        artifact_store: artifacts.ArtifactStore,
        state_root: str | Path,
        certificate_resolver: CertificateResolver | None = None,
        certificate_verifier: CertificateVerifier | None = None,
        schedule_profile_id: str | None = None,
        registry_source: object | None = None,
    ) -> ConfidenceLedgerSession:
        """Open an isolated non-authority session for tests and frozen recomputation."""

        root = Path(repo_root).resolve()
        if root != _loaded_policy_engine_root():
            raise ConfidenceLedgerError("canonical_deployment_identity_invalid")
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
            and self._deployment_quick_fence == _deployment_quick_fence(root)
        )

    @property
    def deployment_identity(self) -> str:
        """Return the immutable canonical deployment identity this session admitted."""

        return self._deployment_identity

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

    def prepare_offer(
        self,
        *,
        history_token: ConfidenceLedgerHistoryToken,
        offer: PromotionCertificateOffer,
    ) -> ConfidenceLedgerCheck:
        """Resolve a typed owner offer through registry data, then bind its check."""

        route = self._registry.resolve_certificate_route(offer.certificate_class)
        if (
            route.certificate_role != offer.claim.certificate_role
            or route.claim_polarity != offer.claim.claim_polarity
        ):
            raise ConfidenceLedgerError("certificate_class_route_mismatch")
        return self.prepare_check(
            history_token=history_token,
            request_key=offer.request_key,
            obligation_class=route.obligation_class,
            instrument_id=route.instrument_id,
            certificate_ref=offer.certificate_ref,
            certificate_class=offer.certificate_class,
            claim=offer.claim,
        )

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
            anchor_ref = self._put_ledger_json(anchor_payload, contract_id="scope_anchor")
            if str(anchor_ref.artifact_id) != expected_anchor_ref:
                raise ConfidenceLedgerError("ledger_scope_anchor_identity_invalid")
            registry_ref = self._put_ledger_json(
                self._registry.source_payload(),
                contract_id="registry",
            )
            if str(registry_ref.artifact_id) != expected_registry_ref:
                raise ConfidenceLedgerError("registry_artifact_identity_invalid")
            root = self._expected_root_binding(str(registry_ref.artifact_id))
            if self._artifact_store.has(expected_root_ref):
                raise ConfidenceLedgerError("ledger_head_reset_detected")
            root_ref = self._put_ledger_json(
                root.model_dump(mode="json"),
                contract_id="root",
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
        from polisyos.core.artifacts import load_core_json_artifact

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
            if manifest.kind == _ledger_artifact_contract("root").kind:
                root_contract = _ledger_artifact_contract("root")
                if (
                    manifest.producer == root_contract.producer
                    and manifest.artifact_schema == root_contract.schema
                ):
                    payload = self._read_cas_json(artifact_ref, root_contract.schema)
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
                payload = load_core_json_artifact(self._artifact_store, artifact_id)
            except (OSError, ValueError, TypeError) as exc:
                raise ConfidenceLedgerError("ledger_cas_payload_invalid", str(exc)) from exc
            if not isinstance(payload, Mapping) or payload.get("scope_id") != root.scope_id:
                continue
            artifact_contract = _ledger_artifact_contract(artifact_kind)
            if (
                manifest.producer != artifact_contract.producer
                or manifest.artifact_schema != artifact_contract.schema
                or manifest.media_type != artifact_contract.media_type
            ):
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

    def _validate_ledger_artifact_payload(
        self,
        *,
        contract_id: str,
        artifact_ref: str,
        payload: object | None,
        require_cas: bool,
        expected_scope_id: str | None = None,
    ) -> tuple[dict[str, Any], str | None]:
        """Resolve one source-owned CAS contract and recompute its domain semantics."""
        try:
            from polisyos.core.artifacts import load_core_json_artifact

            contract = _ledger_artifact_contract(contract_id)
            manifest = self._artifact_store.get_manifest(artifact_ref) if require_cas else None
            if require_cas:
                if (
                    manifest is None
                    or manifest.kind != contract.kind
                    or manifest.artifact_schema != contract.schema
                    or manifest.producer != contract.producer
                    or manifest.media_type != contract.media_type
                ):
                    raise ValueError("ledger_artifact_manifest_kind_schema_or_media_mismatch")
                stored_payload = load_core_json_artifact(self._artifact_store, artifact_ref)
                if payload is not None and stored_payload != payload:
                    raise ValueError("ledger_artifact_payload_mismatch")
                payload = stored_payload
            if not isinstance(payload, Mapping):
                raise ValueError("ledger_artifact_payload_not_mapping")
            payload_dict = dict(payload)
            if _cas_json_artifact_ref(payload_dict) != artifact_ref:
                raise ValueError("ledger_artifact_content_reference_mismatch")

            scope_id: str | None
            if contract_id == "scope_anchor":
                expected_keys = {
                    "schema_version",
                    "scope_id",
                    "scope_owner_ref",
                    "authority_purpose",
                    "owner_scope_key",
                    "epoch_ref",
                }
                if set(payload_dict) != expected_keys:
                    raise ValueError("ledger_scope_anchor_shape_invalid")
                if payload_dict.get("schema_version") != CONFIDENCE_LEDGER_SCHEMA_VERSION:
                    raise ValueError("ledger_scope_anchor_schema_invalid")
                owner_ref = payload_dict.get("scope_owner_ref")
                purpose = payload_dict.get("authority_purpose")
                owner_key = payload_dict.get("owner_scope_key")
                epoch_ref = payload_dict.get("epoch_ref")
                if not all(
                    isinstance(value, str) and value for value in (owner_ref, purpose, owner_key)
                ):
                    raise ValueError("ledger_scope_anchor_identity_invalid")
                if epoch_ref is not None and not isinstance(epoch_ref, str):
                    raise ValueError("ledger_scope_anchor_epoch_invalid")
                scope_id = _identity(
                    "confidence-risk-scope",
                    {
                        "scope_owner_ref": owner_ref,
                        "authority_purpose": purpose,
                        "owner_scope_key": owner_key,
                        "epoch_ref": epoch_ref,
                    },
                )
                if payload_dict.get("scope_id") != scope_id:
                    raise ValueError("ledger_scope_anchor_scope_mismatch")
            elif contract_id == "registry":
                registry = _ledger_payload_model(contract_id).model_validate(payload_dict)
                if registry.model_dump(mode="json") != payload_dict:
                    raise ValueError("ledger_registry_payload_not_canonical")
                scope_id = None
            elif contract_id == "root":
                root = _ledger_payload_model(contract_id).model_validate(payload_dict)
                if root.model_dump(mode="json") != payload_dict:
                    raise ValueError("ledger_root_payload_not_canonical")
                if (
                    root.scope_id != root.risk_scope.scope_id
                    or root.scope_anchor_ref
                    != _cas_json_artifact_ref(_confidence_scope_anchor_payload(root.risk_scope))
                    or root.ledger_root_id
                    != _identity(
                        "confidence-ledger-root",
                        root.model_dump(mode="json", exclude={"ledger_root_id"}),
                    )
                ):
                    raise ValueError("ledger_root_scope_or_identity_invalid")
                if not self._artifact_store.has(root.registry_artifact_ref):
                    raise ValueError("ledger_root_registry_reference_unresolved")
                registry_payload, _ = self._validate_ledger_artifact_payload(
                    contract_id="registry",
                    artifact_ref=root.registry_artifact_ref,
                    payload=None,
                    require_cas=True,
                )
                registry = _ledger_payload_model("registry").model_validate(registry_payload)
                if root.registry_content_hash != registry.content_hash:
                    raise ValueError("ledger_root_registry_binding_invalid")
                scope_id = root.scope_id
            elif contract_id == "event":
                event = _ledger_payload_model(contract_id).model_validate(payload_dict)
                if (
                    event.model_dump(mode="json") != payload_dict
                    or event.scope_id != event.check.scope_id
                    or event.event_id != _recompute_event_id(event)
                    or event.check.event_id != event.event_id
                    or event.check.check_id != _recompute_check_id(event.check)
                ):
                    raise ValueError("ledger_event_scope_or_identity_invalid")
                _validate_check_registry_binding(event.check, registry=self._registry)
                _validate_request_fingerprint(event.check)
                _validate_claim_execution_binding(event.check)
                scope_id = event.scope_id
            elif contract_id == "receipt":
                _ledger_payload_model(contract_id).model_validate(payload_dict)
                receipt = validate_confidence_ledger_receipt_structure(
                    payload_dict,
                    registry=self._registry,
                )
                if receipt.model_dump(mode="json") != payload_dict:
                    raise ValueError("ledger_receipt_payload_not_canonical")
                scope_id = receipt.scope_id
            elif contract_id == "deployment_drift_poison":
                poison = _ledger_payload_model(contract_id).model_validate(payload_dict)
                if (
                    poison.model_dump(mode="json") != payload_dict
                    or poison.poison_id
                    != _identity(
                        "confidence-deployment-drift-poison",
                        poison.model_dump(mode="json", exclude={"poison_id"}),
                    )
                    or not self._artifact_store.has(poison.ledger_root_ref)
                ):
                    raise ValueError("ledger_poison_scope_or_identity_invalid")
                root_payload, root_scope_id = self._validate_ledger_artifact_payload(
                    contract_id="root",
                    artifact_ref=poison.ledger_root_ref,
                    payload=None,
                    require_cas=True,
                )
                root = _ledger_payload_model("root").model_validate(root_payload)
                if (
                    root_scope_id != poison.scope_id
                    or root.scope_id != poison.scope_id
                    or root.ledger_root_id != poison.ledger_root_id
                    or root.authority_provenance != "canonical_repo"
                    or root.deployment_identity != poison.expected_deployment_identity
                ):
                    raise ValueError("ledger_poison_root_binding_invalid")
                scope_id = poison.scope_id
            else:  # pragma: no cover - closed by the source contract registry.
                raise ValueError("unknown_ledger_artifact_contract")

            if contract.scope_bound and scope_id is None:
                raise ValueError("ledger_artifact_scope_not_established")
            if expected_scope_id is not None and scope_id != expected_scope_id:
                raise ValueError("ledger_artifact_scope_mismatch")
            return payload_dict, scope_id
        except (ConfidenceLedgerError, OSError, TypeError, ValueError) as exc:
            raise ValueError(f"{contract_id}:{exc}") from exc

    def _resolve_scope_journal_artifact(
        self,
        *,
        artifact_kind: Literal["event", "receipt", "deployment_drift_poison"],
        artifact_ref: str,
        payload: object,
        require_cas: bool,
    ) -> dict[str, Any]:
        """Resolve one WAL claim through the shared typed CAS artifact boundary."""
        try:
            validated, _scope_id = self._validate_ledger_artifact_payload(
                contract_id=artifact_kind,
                artifact_ref=artifact_ref,
                payload=payload,
                require_cas=require_cas,
                expected_scope_id=self._risk_scope.scope_id,
            )
        except (ConfidenceLedgerError, OSError, TypeError, ValueError) as exc:
            raise ConfidenceLedgerError("ledger_scope_journal_invalid", str(exc)) from exc
        return validated

    def _replay_scope_journal_locked(self) -> dict[str, set[str]]:
        """Complete only source-valid, scope-bound WAL intents."""

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
            present = self._artifact_store.has(artifact_ref)
            if not present and artifact_ref in commits:
                code = (
                    "ledger_receipt_witness_invalid"
                    if intent.artifact_kind == "event"
                    else "ledger_scope_journal_invalid"
                )
                raise ConfidenceLedgerError(code)
            payload = self._resolve_scope_journal_artifact(
                artifact_kind=intent.artifact_kind,
                artifact_ref=artifact_ref,
                payload=payload,
                require_cas=present,
            )
            if not present:
                ref = self._put_ledger_json(payload, contract_id=intent.artifact_kind)
                if str(ref.artifact_id) != artifact_ref:
                    raise ConfidenceLedgerError("ledger_scope_journal_invalid")
                self._resolve_scope_journal_artifact(
                    artifact_kind=intent.artifact_kind,
                    artifact_ref=artifact_ref,
                    payload=payload,
                    require_cas=True,
                )
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
        try:
            root = ConfidenceLedgerRoot.model_validate(
                self._read_cas_json(poison.ledger_root_ref, _ROOT_SCHEMA)
            )
        except (ConfidenceLedgerError, ValueError) as exc:
            raise ConfidenceLedgerError("deployment_drift_poison_invalid", str(exc)) from exc
        expected_root_id = _identity(
            "confidence-ledger-root",
            root.model_dump(mode="json", exclude={"ledger_root_id"}),
        )
        if (
            poison.scope_id != self._risk_scope.scope_id
            or poison.poison_id != expected_id
            or poison.ledger_root_id != root.ledger_root_id
            or root.ledger_root_id != expected_root_id
            or poison.ledger_root_ref != _cas_json_artifact_ref(root)
            or root.scope_id != poison.scope_id
            or root.authority_provenance != "canonical_repo"
            or root.deployment_identity != poison.expected_deployment_identity
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

        return _confidence_scope_anchor_payload(self._risk_scope)

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
        """Validate the WAL and repair only an incomplete final record suffix."""

        identity = self._journal_identity()
        flags = os.O_RDWR
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        try:
            fd = os.open(self._journal_path, flags)
        except OSError as exc:
            raise ConfidenceLedgerError("ledger_scope_journal_invalid", str(exc)) from exc
        try:
            held = os.fstat(fd)
            if (held.st_dev, held.st_ino) != (
                identity["device"],
                identity["inode"],
            ):
                raise ConfidenceLedgerError("ledger_scope_journal_invalid")
            if held.st_size < self._journal_offset:
                raise ConfidenceLedgerError("ledger_scope_journal_rollback_detected")
            chunks: list[bytes] = []
            while True:
                chunk = os.read(fd, 1024 * 1024)
                if not chunk:
                    break
                chunks.append(chunk)
            journal_bytes = b"".join(chunks)
            if len(journal_bytes) != held.st_size:
                raise ConfidenceLedgerError("ledger_scope_journal_invalid")
            if (
                self._journal_offset
                and hashlib.sha256(journal_bytes[: self._journal_offset]).digest()
                != self._journal_prefix_hash
            ):
                raise ConfidenceLedgerError("ledger_scope_journal_rollback_detected")

            last_newline = journal_bytes.rfind(b"\n")
            verified_size = last_newline + 1
            verified_bytes = journal_bytes[:verified_size]
            torn_suffix = journal_bytes[verified_size:]
            records: list[_ScopeJournalRecord] = []
            previous_hash = _scope_journal_genesis_hash(self._risk_scope.scope_id)
            for raw_line in verified_bytes.splitlines():
                try:
                    record = _ScopeJournalRecord.model_validate_json(raw_line)
                except ValueError as exc:
                    raise ConfidenceLedgerError("ledger_scope_journal_invalid", str(exc)) from exc
                expected_hash = _scope_journal_record_hash(record)
                if (
                    record.scope_id != self._risk_scope.scope_id
                    or record.revision != len(records) + 1
                    or record.previous_record_hash != previous_hash
                    or record.record_hash != expected_hash
                    or (record.record_type == "intent") != (record.payload is not None)
                ):
                    raise ConfidenceLedgerError("ledger_scope_journal_invalid")
                records.append(record)
                previous_hash = record.record_hash

            if self._journal_identity() != identity:
                raise ConfidenceLedgerError("ledger_scope_journal_invalid")
            if torn_suffix:
                os.ftruncate(fd, verified_size)
                os.fsync(fd)
                _fsync_directory(self._journal_path.parent)
                if self._journal_identity() != identity:
                    raise ConfidenceLedgerError("ledger_scope_journal_invalid")
            self._journal_records = records
            self._journal_offset = verified_size
            self._journal_prefix_hash = hashlib.sha256(verified_bytes).digest()
        except OSError as exc:
            raise ConfidenceLedgerError("ledger_scope_journal_invalid", str(exc)) from exc
        finally:
            os.close(fd)
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
        self._read_new_scope_journal_records_locked()

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

        _, schema = _journal_artifact_contract(artifact_kind)
        artifact_ref = _cas_json_artifact_ref(payload)
        self._append_scope_journal_intent(
            artifact_kind=artifact_kind,
            artifact_ref=artifact_ref,
            payload=payload,
        )
        ref = self._put_ledger_json(payload, contract_id=artifact_kind)
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

    def _prior_scope_artifact_payloads(
        self,
    ) -> tuple[tuple[str, artifacts.ArtifactID, Mapping[str, Any]], ...]:
        """Read all typed, content-bound artifacts that can evidence ledger history."""
        _assert_ledger_artifact_contracts_current()
        contracts_by_kind = {
            contract.kind: (contract_id, contract)
            for contract_id, contract in _IMPORT_TIME_LEDGER_ARTIFACT_CONTRACTS.items()
        }
        try:
            # Materialize while guarded: a lazy inventory failure after partial
            # iteration is still unknown membership, never a negative result.
            artifact_ids = tuple(self._artifact_store.iter_artifact_ids())
        except (OSError, TypeError, ValueError) as exc:
            raise ConfidenceLedgerError(
                "prior_scope_membership_not_established",
                str(exc),
            ) from exc

        payloads: list[tuple[str, artifacts.ArtifactID, Mapping[str, Any]]] = []
        for artifact_id in artifact_ids:
            try:
                manifest = self._artifact_store.get_manifest(artifact_id)
                contract_row = contracts_by_kind.get(manifest.kind)
                if contract_row is None:
                    if manifest.kind.startswith("runtime.quality.confidence_ledger."):
                        raise ValueError(
                            f"unrecognized confidence-ledger artifact kind: {manifest.kind}"
                        )
                    continue
                contract_id, contract = contract_row
                if (
                    manifest.artifact_schema != contract.schema
                    or manifest.producer != contract.producer
                    or manifest.media_type != contract.media_type
                ):
                    raise ValueError(f"unverified {manifest.kind} metadata")
                payload, scope_id = self._validate_ledger_artifact_payload(
                    contract_id=contract_id,
                    artifact_ref=str(artifact_id),
                    payload=None,
                    require_cas=True,
                )
                if contract.scope_bound:
                    if scope_id is None:
                        raise ValueError(f"missing typed scope for {manifest.kind}")
                    payloads.append((manifest.kind, artifact_id, payload))
            except (ConfidenceLedgerError, OSError, TypeError, ValueError) as exc:
                cause = exc
                while cause.__cause__ is not None:
                    cause = cause.__cause__
                raise ConfidenceLedgerError(
                    "prior_scope_membership_not_established",
                    str(exc),
                ) from cause
        return tuple(payloads)

    def _prior_scope_artifact_exists(self) -> bool:
        """Find prior scope use through one typed boundary for WAL and CAS evidence."""
        try:
            journal_refs = self._replay_scope_journal_locked()
        except ConfidenceLedgerError as exc:
            if exc.code == "prior_scope_membership_not_established":
                raise
            raise ConfidenceLedgerError(
                "prior_scope_membership_not_established",
                exc.code,
            ) from exc
        if any(journal_refs.values()):
            return True

        return any(
            payload["scope_id"] == self._risk_scope.scope_id
            for _kind, _artifact_id, payload in self._prior_scope_artifact_payloads()
        )

    def _scope_root_artifact_exists(self) -> bool:
        """Return whether a fully validated immutable root exists for this scope."""
        return any(
            kind == "runtime.quality.confidence_ledger.root"
            and payload["scope_id"] == self._risk_scope.scope_id
            for kind, _artifact_id, payload in self._prior_scope_artifact_payloads()
        )

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
        evidence_hash = recompute_confidence_owner_evidence_hash(evidence)
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
            owner_projection_hash=recompute_confidence_owner_projection_hash(
                evidence.owner_projection
            ),
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

    def _put_ledger_json(self, payload: object, *, contract_id: str) -> artifacts.ArtifactRef:
        """Persist a source-owned ledger artifact using its registered contract."""
        return self._put_json(payload, contract_id=contract_id)

    def _read_cas_json(self, artifact_ref: str, schema: artifacts.SchemaInfo) -> object:
        from polisyos.core.artifacts import load_core_json_artifact

        _assert_ledger_artifact_contracts_current()
        matching = tuple(
            contract
            for contract in _IMPORT_TIME_LEDGER_ARTIFACT_CONTRACTS.values()
            if contract.schema == schema
        )
        if len(matching) != 1:
            raise ConfidenceLedgerError("ledger_cas_manifest_invalid")
        contract = matching[0]
        report = self._artifact_store.verify(artifact_ref)
        if not report.ok:
            raise ConfidenceLedgerError("ledger_cas_integrity_invalid", report.error)
        manifest = self._artifact_store.get_manifest(artifact_ref)
        if (
            manifest.kind != contract.kind
            or manifest.artifact_schema != contract.schema
            or manifest.producer != contract.producer
            or manifest.media_type != contract.media_type
        ):
            raise ConfidenceLedgerError("ledger_cas_manifest_invalid")
        try:
            return load_core_json_artifact(self._artifact_store, artifact_ref)
        except (OSError, ValueError, TypeError) as exc:
            raise ConfidenceLedgerError("ledger_cas_payload_invalid", str(exc)) from exc

    def _put_json(self, payload: object, *, contract_id: str) -> artifacts.ArtifactRef:
        contract = _ledger_artifact_contract(contract_id)
        _assert_ledger_artifact_contracts_current()
        return self._artifact_store.put_json(
            _jsonable(payload),
            artifacts.PutOptions(
                kind=contract.kind,
                media_type=contract.media_type,
                schema=contract.schema,
                producer=contract.producer,
            ),
            canon_spec=_IMPORT_TIME_LEDGER_CANON_SPEC,
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
        """Fence runtime contracts and canonical source against in-session drift."""

        _assert_ledger_artifact_contracts_current()
        if self._authority_provenance != "canonical_repo":
            return
        root = self._authority_repo_root
        observed: str | None = None
        if root is not None and root == _loaded_policy_engine_root():
            try:
                quick_fence = _deployment_quick_fence(root)
            except ConfidenceLedgerError:
                quick_fence = None
            if quick_fence == self._deployment_quick_fence:
                return
            try:
                deployment_baseline, stable_fence = _stable_deployment_snapshot(root)
                observed = _deployment_identity_from_baseline(deployment_baseline)
            except ConfidenceLedgerError:
                observed = None
            if observed == self._deployment_identity:
                self._deployment_quick_fence = stable_fence
                return
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
        if observed_identity == self._deployment_identity:
            raise ConfidenceLedgerError("deployment_drift_poison_invalid")
        registry_ref = _cas_json_artifact_ref(self._registry.source_payload())
        root = self._expected_root_binding(registry_ref)
        root_ref = _cas_json_artifact_ref(root)
        try:
            stored_root = ConfidenceLedgerRoot.model_validate(
                self._read_cas_json(root_ref, _ROOT_SCHEMA)
            )
        except (ConfidenceLedgerError, ValueError) as exc:
            raise ConfidenceLedgerError("deployment_drift_poison_invalid", str(exc)) from exc
        if stored_root != root:
            raise ConfidenceLedgerError("deployment_drift_poison_invalid")
        payload: dict[str, Any] = {
            "schema_version": CONFIDENCE_LEDGER_SCHEMA_VERSION,
            "scope_id": self._risk_scope.scope_id,
            "ledger_root_id": root.ledger_root_id,
            "ledger_root_ref": root_ref,
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


def recompute_confidence_owner_projection_hash(owner_projection: object) -> str:
    """Hash an owner projection with the ledger's sole canonical serializer."""

    return _content_hash(owner_projection)


def recompute_confidence_owner_evidence_hash(
    evidence: OwnerCertificateEvidence,
) -> str:
    """Hash resolved owner evidence exactly as the ledger verifier intake does."""

    return _content_hash(evidence)


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


def _semantic_owner_binding(
    check: ConfidenceLedgerCheck,
) -> ConfidenceLedgerSemanticOwnerBinding | None:
    """Project a verified owner binding without invocation-local proof hashes."""

    binding = check.owner_binding
    if binding is None:
        return None
    values: dict[str, Any] = {
        "certificate_ref": binding.certificate_ref,
        "certificate_class": binding.certificate_class,
        "certificate_route_hash": binding.certificate_route_hash,
        "owner_ref": binding.owner_ref,
        "owner_projection_hash": binding.owner_projection_hash,
        "verifier_ref": binding.verifier_ref,
        "verifier_kernel_id": binding.verifier_kernel_id,
    }
    values["binding_projection_hash"] = _content_hash(values)
    return ConfidenceLedgerSemanticOwnerBinding.model_validate(values)


def _semantic_claim_execution_projection_hash(
    check: ConfidenceLedgerCheck,
    *,
    filtration_projection_hash: str,
) -> str:
    """Bind a draw to predictable semantic history without physical CAS identity."""

    return _content_hash(
        {
            "scope_id": check.scope_id,
            "request_fingerprint": check.request_fingerprint,
            "claim_ref": check.claim_ref,
            "null_ref": check.null_ref,
            "claim_scope_ref": check.claim_scope_ref,
            "data_window_ref": check.data_window_ref,
            "filtration_projection_hash": filtration_projection_hash,
            "certificate_role": check.certificate_role,
            "claim_polarity": check.claim_polarity,
            "execution_id": check.execution_id,
            "execution_ordinal": check.execution_ordinal,
            "schedule_query_index": check.schedule_query_index,
            "reserved_alpha": check.spend,
            "registry_content_hash": check.registry_content_hash,
            "instrument_definition_hash": check.instrument_definition_hash,
            "proof_profile_hash": check.proof_profile_hash,
        }
    )


def _semantic_claim_execution_projection_hash_from_projection(
    check: ConfidenceLedgerSemanticCheck,
) -> str:
    """Recompute a semantic claim binding from its persisted full preimage."""

    return _content_hash(
        {
            "scope_id": check.scope_id,
            "request_fingerprint": check.request_fingerprint,
            "claim_ref": check.claim_ref,
            "null_ref": check.null_ref,
            "claim_scope_ref": check.claim_scope_ref,
            "data_window_ref": check.data_window_ref,
            "filtration_projection_hash": check.filtration_projection_hash,
            "certificate_role": check.certificate_role,
            "claim_polarity": check.claim_polarity,
            "execution_id": check.execution_id,
            "execution_ordinal": check.execution_ordinal,
            "schedule_query_index": check.schedule_query_index,
            "reserved_alpha": check.spend,
            "registry_content_hash": check.registry_content_hash,
            "instrument_definition_hash": check.instrument_definition_hash,
            "proof_profile_hash": check.proof_profile_hash,
        }
    )


def _semantic_check_projection(
    check: ConfidenceLedgerCheck,
    *,
    filtration_projection_hash: str,
) -> ConfidenceLedgerSemanticCheck:
    """Project one verified live check onto stable semantic identities."""

    values: dict[str, Any] = {
        "schema_version": check.schema_version,
        "scope_id": check.scope_id,
        "request_key": check.request_key,
        "request_fingerprint": check.request_fingerprint,
        "obligation_class": check.obligation_class,
        "instrument_id": check.instrument_id,
        "instrument_family": check.instrument_family,
        "proof_profile_id": check.proof_profile_id,
        "certificate_ref": check.certificate_ref,
        "certificate_class": check.certificate_class,
        "certificate_route_hash": check.certificate_route_hash,
        "certificate_role": check.certificate_role,
        "claim_polarity": check.claim_polarity,
        "claim_ref": check.claim_ref,
        "null_ref": check.null_ref,
        "claim_scope_ref": check.claim_scope_ref,
        "data_window_ref": check.data_window_ref,
        "filtration_projection_hash": filtration_projection_hash,
        "registry_content_hash": check.registry_content_hash,
        "instrument_definition_hash": check.instrument_definition_hash,
        "proof_profile_hash": check.proof_profile_hash,
        "execution_status": check.execution_status,
        "outcome": check.outcome,
        "execution_ordinal": check.execution_ordinal,
        "schedule_query_index": check.schedule_query_index,
        "execution_id": check.execution_id,
        "deterministic_proof": check.deterministic_proof,
        "anytime_valid": check.anytime_valid,
        "spend": check.spend,
        "spend_decimal": check.spend_decimal,
        "supports_obligation": check.supports_obligation,
        "eligible_for_promotion": check.eligible_for_promotion,
        "refusal_code": check.refusal_code,
        "proof_detail": check.proof_detail,
        "owner_invocation_claim_projection_hash": (
            _content_hash(
                {
                    "scope_id": check.scope_id,
                    "request_fingerprint": check.request_fingerprint,
                    "execution_id": check.execution_id,
                    "execution_ordinal": check.execution_ordinal,
                    "schedule_query_index": check.schedule_query_index,
                    "owner_invocation_claimed": True,
                }
            )
            if check.owner_invocation_claim_id is not None
            else None
        ),
        "good_event_id": check.good_event_id,
        "owner_binding": _semantic_owner_binding(check),
        "claim_execution_projection_hash": _semantic_claim_execution_projection_hash(
            check,
            filtration_projection_hash=filtration_projection_hash,
        ),
    }
    values["check_projection_hash"] = _content_hash(values)
    return ConfidenceLedgerSemanticCheck.model_validate(values)


def _semantic_ledger_root_values(
    *,
    receipt: ConfidenceLedgerReceipt,
    risk_scope: ConfidenceRiskBudgetScope,
    projection_scope: str,
) -> dict[str, Any]:
    """Return the stable semantic root payload for a verified receipt."""

    return {
        "schema_version": receipt.schema_version,
        "projection_scope": projection_scope,
        "authority_provenance": receipt.authority_provenance,
        "deployment_identity": receipt.deployment_identity,
        "risk_scope": risk_scope,
        "scope_id": receipt.scope_id,
        "scope_anchor_ref": receipt.scope_anchor_ref,
        "registry_content_hash": receipt.registry_content_hash,
        "schedule_profile_id": receipt.schedule_profile_id,
        "schedule_profile_hash": receipt.schedule_profile_hash,
        "schedule_projection_hash": receipt.schedule_projection_hash,
        "budget_delta": receipt.budget_delta,
        "budget_delta_decimal": receipt.budget_delta_decimal,
        "conditionality_clause": receipt.conditionality_clause,
        "maintained_assumptions": receipt.maintained_assumptions,
    }


def _n9_semantic_ledger_root_values(
    *,
    receipt: ConfidenceLedgerReceipt | N9PromotionSemanticLedgerProjection,
    risk_scope: ConfidenceRiskBudgetScope,
) -> dict[str, Any]:
    """Return the stable N9 ledger root without physical deployment locators."""

    return {
        "schema_version": receipt.schema_version,
        "projection_rule_version": N9_PROMOTION_SEMANTIC_PROJECTION_RULE_VERSION,
        "projection_scope": "n9_promotion_semantic_receipt",
        "authority_provenance": receipt.authority_provenance,
        "risk_scope": risk_scope,
        "scope_id": receipt.scope_id,
        "registry_content_hash": receipt.registry_content_hash,
        "schedule_profile_id": receipt.schedule_profile_id,
        "schedule_profile_hash": receipt.schedule_profile_hash,
        "schedule_projection_hash": receipt.schedule_projection_hash,
        "budget_delta": receipt.budget_delta,
        "budget_delta_decimal": receipt.budget_delta_decimal,
        "conditionality_clause": receipt.conditionality_clause,
        "maintained_assumptions": receipt.maintained_assumptions,
    }


def _project_semantic_event_lineage(
    receipt: ConfidenceLedgerReceipt,
    *,
    root_projection_hash: str,
    error_prefix: str,
) -> tuple[
    tuple[ConfidenceLedgerSemanticEvent, ...],
    tuple[ConfidenceLedgerSemanticCheck, ...],
    str,
]:
    """Project one validated physical event chain onto stable semantic lineage."""

    head_projection_hash = root_projection_hash
    filtration_by_request: dict[str, str] = {}
    current_checks: dict[str, ConfidenceLedgerSemanticCheck] = {}
    projected_events: list[ConfidenceLedgerSemanticEvent] = []
    for event in receipt.events:
        request_key = event.check.request_key
        if event.event_type == "prepared" or (
            request_key not in filtration_by_request and event.check.outcome == "preflight_refusal"
        ):
            if request_key in filtration_by_request:
                raise ConfidenceLedgerError(f"{error_prefix}_duplicate_preparation")
            filtration_by_request[request_key] = head_projection_hash
        try:
            filtration_projection_hash = filtration_by_request[request_key]
        except KeyError as exc:  # pragma: no cover - live receipt validation owns this guard.
            raise ConfidenceLedgerError(f"{error_prefix}_missing_preparation") from exc
        projected_check = _semantic_check_projection(
            event.check,
            filtration_projection_hash=filtration_projection_hash,
        )
        event_values: dict[str, Any] = {
            "event_type": event.event_type,
            "revision": event.revision,
            "parent_event_projection_hash": head_projection_hash,
            "check": projected_check,
        }
        event_values["event_projection_hash"] = _content_hash(event_values)
        projected_event = ConfidenceLedgerSemanticEvent.model_validate(event_values)
        projected_events.append(projected_event)
        current_checks[request_key] = projected_check
        head_projection_hash = projected_event.event_projection_hash
    live_current = {check.request_key: check for check in receipt.checks}
    if set(live_current) != set(current_checks):  # pragma: no cover - receipt validation guard.
        raise ConfidenceLedgerError(f"{error_prefix}_current_check_denominator_drift")
    for request_key, live_check in live_current.items():
        expected = _semantic_check_projection(
            live_check,
            filtration_projection_hash=filtration_by_request[request_key],
        )
        if expected != current_checks[request_key]:  # pragma: no cover - validation guard.
            raise ConfidenceLedgerError(f"{error_prefix}_current_check_drift")
    checks = tuple(current_checks[key] for key in sorted(current_checks))
    return tuple(projected_events), checks, head_projection_hash


def project_confidence_ledger_semantic_receipt(
    receipt: ConfidenceLedgerReceipt | Mapping[str, object],
    *,
    session: ConfidenceLedgerSession,
    projection_scope: Literal[
        "n11_real_accounting_append_lineage",
        "n11_conformance_append_lineage",
    ],
) -> ConfidenceLedgerSemanticReceiptProjection:
    """Project a fully verified live receipt onto stable append semantics."""

    validated = validate_confidence_ledger_receipt(receipt, session=session)
    risk_scope = session.risk_scope
    expected_authority_purpose = {
        "n11_real_accounting_append_lineage": "n11_real_n10_n13b_accounting",
        "n11_conformance_append_lineage": "n11_probabilistic_conformance",
    }[projection_scope]
    if risk_scope.authority_purpose != expected_authority_purpose:
        raise ConfidenceLedgerError("semantic_projection_scope_authority_mismatch")
    if (
        validated.scope_id != risk_scope.scope_id
        or validated.scope_anchor_ref != recompute_confidence_scope_anchor_ref(risk_scope)
    ):
        raise ConfidenceLedgerError("semantic_projection_scope_binding_invalid")
    root_values = _semantic_ledger_root_values(
        receipt=validated,
        risk_scope=risk_scope,
        projection_scope=projection_scope,
    )
    root_projection_hash = _content_hash(root_values)
    projected_events, checks, head_projection_hash = _project_semantic_event_lineage(
        validated,
        root_projection_hash=root_projection_hash,
        error_prefix="semantic_projection",
    )
    values: dict[str, Any] = {
        **root_values,
        "root_projection_hash": root_projection_hash,
        "events": projected_events,
        "checks": checks,
        "head_event_projection_hash": head_projection_hash,
        "total_spend": validated.total_spend,
        "total_spend_decimal": validated.total_spend_decimal,
        "within_budget": validated.within_budget,
        "good_event_clause": validated.good_event_clause,
    }
    values["projection_hash"] = _content_hash(values)
    return ConfidenceLedgerSemanticReceiptProjection.model_validate(values)


def project_n9_promotion_semantic_ledger(
    receipt: ConfidenceLedgerReceipt | Mapping[str, object],
    *,
    session: ConfidenceLedgerSession,
) -> N9PromotionSemanticLedgerProjection:
    """Project a verified N9 ledger onto stable claim and filtration semantics."""

    validated = validate_confidence_ledger_receipt(receipt, session=session)
    risk_scope = session.risk_scope
    if risk_scope.authority_purpose != "n9_promotion":
        raise ConfidenceLedgerError("n9_semantic_projection_scope_authority_mismatch")
    if validated.scope_id != risk_scope.scope_id:
        raise ConfidenceLedgerError("n9_semantic_projection_scope_binding_invalid")
    root_values = _n9_semantic_ledger_root_values(
        receipt=validated,
        risk_scope=risk_scope,
    )
    root_projection_hash = _content_hash(root_values)
    events, checks, head_projection_hash = _project_semantic_event_lineage(
        validated,
        root_projection_hash=root_projection_hash,
        error_prefix="n9_semantic_projection",
    )
    values: dict[str, Any] = {
        **root_values,
        "root_projection_hash": root_projection_hash,
        "events": events,
        "checks": checks,
        "head_event_projection_hash": head_projection_hash,
        "total_spend": validated.total_spend,
        "total_spend_decimal": validated.total_spend_decimal,
        "within_budget": validated.within_budget,
        "good_event_clause": validated.good_event_clause,
    }
    values["projection_hash"] = _content_hash(values)
    return N9PromotionSemanticLedgerProjection.model_validate(values)


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
        "scope_anchor_ref": validated.scope_anchor_ref,
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
        "risk_scope": scope,
        "scope_id": validated.scope_id,
        "scope_anchor_ref": validated.scope_anchor_ref,
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


def recompute_confidence_scope_anchor_ref(risk_scope: ConfidenceRiskBudgetScope) -> str:
    """Recompute the immutable CAS anchor for one declared risk scope."""

    return _cas_json_artifact_ref(_confidence_scope_anchor_payload(risk_scope))


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
    return _content_hash(serialization.artifact_self_identity_projection(record))


def _fsync_directory(path: Path) -> None:
    """Durably persist a directory entry update."""

    flags = os.O_RDONLY
    if hasattr(os, "O_DIRECTORY"):
        flags |= os.O_DIRECTORY
    fd = os.open(path, flags)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _ledger_artifact_contract(contract_id: str) -> _LedgerArtifactContract:
    """Return the import-pinned, source-checked CAS contract."""
    try:
        return _IMPORT_TIME_LEDGER_ARTIFACT_CONTRACTS[contract_id]
    except KeyError as exc:
        raise ConfidenceLedgerError("unknown_ledger_artifact_contract", contract_id) from exc


def _ledger_payload_model(contract_id: str) -> type[BaseModel]:
    """Resolve the payload model bound to a registered artifact contract."""
    model = _ledger_artifact_contract(contract_id).payload_model
    if model is None:
        raise ConfidenceLedgerError("ledger_artifact_payload_model_unavailable", contract_id)
    return model


def _journal_artifact_contract(
    artifact_kind: Literal["event", "receipt", "deployment_drift_poison"],
) -> tuple[str, artifacts.SchemaInfo]:
    contract = _ledger_artifact_contract(artifact_kind)
    return contract.kind, contract.schema


def _source_module_bindings(tree: ast.Module) -> dict[str, ast.AST]:
    """Index unique top-level source bindings without evaluating source code."""
    bindings: dict[str, ast.AST] = {}
    for node in tree.body:
        targets: tuple[ast.expr, ...] = ()
        value: ast.AST | None = None
        if isinstance(node, ast.Assign):
            targets = tuple(node.targets)
            value = node.value
        elif isinstance(node, ast.AnnAssign):
            targets = (node.target,)
            value = node.value
        if value is None:
            continue
        for target in targets:
            if isinstance(target, ast.Name):
                if target.id in bindings:
                    raise ValueError(f"duplicate source binding: {target.id}")
                bindings[target.id] = value
    return bindings


def _source_keyword_values(call: ast.Call) -> dict[str, ast.AST]:
    """Return explicit keyword values, rejecting dynamic expansion."""
    if any(keyword.arg is None for keyword in call.keywords):
        raise ValueError("dynamic source keyword expansion")
    result = {str(keyword.arg): keyword.value for keyword in call.keywords}
    if len(result) != len(call.keywords):
        raise ValueError("duplicate source keyword")
    return result


def _source_string(node: ast.AST) -> str:
    """Read a literal string from an AST node."""
    value = _source_literal(node, expected_type=str)
    if not isinstance(value, str):
        raise ValueError("source value is not a string")
    return value


def _source_schema_projection(bindings: Mapping[str, ast.AST], name: str) -> dict[str, str]:
    """Read a source-declared SchemaInfo pair from literal constructor arguments."""
    expression = bindings.get(name)
    if not isinstance(expression, ast.Call) or not (
        isinstance(expression.func, ast.Attribute)
        and isinstance(expression.func.value, ast.Name)
        and expression.func.value.id == "artifacts"
        and expression.func.attr == "SchemaInfo"
    ):
        raise ValueError(f"source schema binding is not SchemaInfo: {name}")
    values = _source_keyword_values(expression)
    if set(values) != {"name", "version"}:
        raise ValueError(f"source schema fields differ: {name}")
    schema_name = _source_string(values["name"])
    version = _source_string(values["version"])
    return {"name": schema_name, "version": version}


def _source_producer_projection(bindings: Mapping[str, ast.AST]) -> dict[str, object]:
    """Read the source-owned producer identity using literal constructor values."""
    expression = bindings.get("_LEDGER_PRODUCER")
    if not isinstance(expression, ast.Call) or not (
        isinstance(expression.func, ast.Attribute)
        and isinstance(expression.func.value, ast.Name)
        and expression.func.value.id == "artifacts"
        and expression.func.attr == "ProducerInfo"
    ):
        raise ValueError("source producer binding is not ProducerInfo")
    values = _source_keyword_values(expression)
    if set(values) != {"component", "version"}:
        raise ValueError("source producer fields differ")
    return {
        "component": _source_literal(values["component"], expected_type=str),
        "version": _source_literal(values["version"], expected_type=str),
        "git": None,
    }


def _source_ledger_contract_projection(source_bytes: bytes) -> str:
    """Derive the complete ledger artifact table from source-owned literals."""
    tree = ast.parse(source_bytes, filename="confidence_ledger.py")
    bindings = _source_module_bindings(tree)
    table_expression = bindings.get("_LEDGER_ARTIFACT_CONTRACTS")
    if not isinstance(table_expression, ast.Call) or not (
        isinstance(table_expression.func, ast.Attribute)
        and isinstance(table_expression.func.value, ast.Name)
        and table_expression.func.value.id == "types"
        and table_expression.func.attr == "MappingProxyType"
        and not table_expression.keywords
        and len(table_expression.args) == 1
        and isinstance(table_expression.args[0], ast.Dict)
    ):
        raise ValueError("ledger contract table is not a source-owned immutable mapping")
    table_literal = table_expression.args[0]
    producer = _source_producer_projection(bindings)
    media_expression = bindings.get("_LEDGER_ARTIFACT_MEDIA_TYPE")
    media_type = _source_literal(media_expression, expected_type=str) if media_expression else None
    if not isinstance(media_type, str) or not media_type:
        raise ValueError("source media type is missing")
    schema_names: set[str] = set()
    model_names: set[str] = set()
    contract_rows: dict[str, dict[str, object]] = {}
    for key_node, value_node in zip(table_literal.keys, table_literal.values, strict=True):
        if (
            key_node is None
            or not isinstance(value_node, ast.Call)
            or not (
                isinstance(value_node.func, ast.Name)
                and value_node.func.id == "_LedgerArtifactContract"
            )
        ):
            raise ValueError("source ledger contract row is not a literal contract")
        contract_id = _source_literal(key_node, expected_type=str)
        values = _source_keyword_values(value_node)
        if set(values) != {
            "kind",
            "schema",
            "producer",
            "media_type",
            "scope_bound",
            "payload_model",
        }:
            raise ValueError(f"source ledger contract fields differ: {contract_id}")
        kind = _source_literal(values["kind"], expected_type=str)
        schema_node = values["schema"]
        producer_node = values["producer"]
        media_node = values["media_type"]
        scope_bound = _source_literal(values["scope_bound"], expected_type=bool)
        if not isinstance(schema_node, ast.Name) or schema_node.id not in bindings:
            raise ValueError(f"source schema reference is invalid: {contract_id}")
        if not isinstance(producer_node, ast.Name) or producer_node.id != "_LEDGER_PRODUCER":
            raise ValueError(f"source producer reference is invalid: {contract_id}")
        if not isinstance(media_node, ast.Name) or media_node.id != "_LEDGER_ARTIFACT_MEDIA_TYPE":
            raise ValueError(f"source media reference is invalid: {contract_id}")
        model_node = values["payload_model"]
        if isinstance(model_node, ast.Constant) and model_node.value is None:
            model_name: str | None = None
        elif isinstance(model_node, ast.Name):
            model_name = model_node.id
            model_names.add(model_name)
        else:
            raise ValueError(f"source payload model reference is invalid: {contract_id}")
        if contract_id in contract_rows:
            raise ValueError(f"duplicate source contract id: {contract_id}")
        schema_name = schema_node.id
        schema_names.add(schema_name)
        schema = _source_schema_projection(bindings, schema_name)
        contract_rows[contract_id] = {
            "kind": kind,
            "schema_binding": schema_name,
            "schema": schema,
            "producer_binding": "_LEDGER_PRODUCER",
            "producer": producer,
            "media_type_binding": "_LEDGER_ARTIFACT_MEDIA_TYPE",
            "media_type": media_type,
            "scope_bound": scope_bound,
            "payload_model": model_name,
        }
    class_names = {node.name for node in tree.body if isinstance(node, ast.ClassDef)}
    if not model_names.issubset(class_names):
        raise ValueError("source contract names an absent payload model")
    schema_bindings = {
        name: _source_schema_projection(bindings, name) for name in sorted(schema_names)
    }
    version_bindings = {}
    for name in (
        "CONFIDENCE_LEDGER_SCHEMA_VERSION",
        "CONFIDENCE_LEDGER_REGISTRY_SCHEMA_VERSION",
    ):
        value = bindings.get(name)
        if value is None:
            raise ValueError(f"source semantic version is missing: {name}")
        version_bindings[name] = _source_literal(value, expected_type=str)
    return _canonical_json(
        {
            "contracts": contract_rows,
            "producer_binding": producer,
            "schema_bindings": schema_bindings,
            "media_type_binding": media_type,
            "version_bindings": version_bindings,
        }
    )


def _runtime_producer_projection(value: object) -> dict[str, object]:
    """Normalize the producer fields that determine a persisted manifest claim."""
    if type(value) is not artifacts.ProducerInfo:
        raise ValueError("ledger producer runtime type changed")
    producer_value = typing.cast("artifacts.ProducerInfo", value)
    git = producer_value.git
    git_projection = None
    if git is not None:
        git_projection = {"commit": git.commit, "dirty": git.dirty}
    component = str(producer_value.component)
    if not component or not isinstance(producer_value.version, str) or not producer_value.version:
        raise ValueError("ledger producer runtime value is invalid")
    return {
        "component": component,
        "version": producer_value.version,
        "git": git_projection,
    }


def _runtime_schema_projection(value: object) -> dict[str, str]:
    """Normalize the schema name/version fields that identify a CAS payload."""
    if type(value) is not artifacts.SchemaInfo:
        raise ValueError("ledger schema runtime type changed")
    schema_value = typing.cast("artifacts.SchemaInfo", value)
    if not isinstance(schema_value.name, str) or not schema_value.name:
        raise ValueError("ledger schema name is invalid")
    if not isinstance(schema_value.version, str) or not schema_value.version:
        raise ValueError("ledger schema version is invalid")
    return {"name": schema_value.name, "version": schema_value.version}


def _runtime_ledger_contract_projection() -> str:
    """Capture every effective table/global value used by CAS admission and replay."""
    table = _LEDGER_ARTIFACT_CONTRACTS
    if type(table) is not types.MappingProxyType:
        raise ValueError("ledger contract registry is no longer immutable")
    producer = _runtime_producer_projection(_LEDGER_PRODUCER)
    media_type = _LEDGER_ARTIFACT_MEDIA_TYPE
    if not isinstance(media_type, str) or not media_type:
        raise ValueError("ledger media type is invalid")
    schema_bindings: dict[str, dict[str, str]] = {}
    contracts: dict[str, dict[str, object]] = {}
    for contract_id, contract in sorted(table.items()):
        if not isinstance(contract_id, str) or not contract_id:
            raise ValueError("ledger contract id is invalid")
        if type(contract) is not _LedgerArtifactContract:
            raise ValueError(f"ledger contract runtime model changed: {contract_id}")
        schema = _runtime_schema_projection(contract.schema)
        row_producer = _runtime_producer_projection(contract.producer)
        row_media_type = contract.media_type
        if not isinstance(row_media_type, str) or not row_media_type:
            raise ValueError(f"ledger contract media type is invalid: {contract_id}")
        if type(contract.scope_bound) is not bool:
            raise ValueError(f"ledger contract scope binding is invalid: {contract_id}")
        if contract.payload_model is not None and not (
            isinstance(contract.payload_model, type)
            and issubclass(contract.payload_model, BaseModel)
        ):
            raise ValueError(f"ledger contract payload model is invalid: {contract_id}")
        schema_name = next(
            (
                name
                for name, candidate in globals().items()
                if name.endswith("_SCHEMA") and candidate is contract.schema
            ),
            None,
        )
        if not isinstance(schema_name, str):
            raise ValueError(f"ledger schema has no source-owned binding: {contract_id}")
        schema_bindings[schema_name] = schema
        model_name = contract.payload_model.__name__ if contract.payload_model is not None else None
        if model_name is not None and globals().get(model_name) is not contract.payload_model:
            raise ValueError(f"ledger payload model binding changed: {contract_id}")
        if contract.kind != contract.kind.strip() or not contract.kind:
            raise ValueError(f"ledger artifact kind is invalid: {contract_id}")
        contracts[contract_id] = {
            "kind": contract.kind,
            "schema_binding": schema_name,
            "schema": schema,
            "producer_binding": "_LEDGER_PRODUCER",
            "producer": row_producer,
            "media_type_binding": "_LEDGER_ARTIFACT_MEDIA_TYPE",
            "media_type": row_media_type,
            "scope_bound": contract.scope_bound,
            "payload_model": model_name,
        }
    if not contracts:
        raise ValueError("ledger contract registry is empty")
    for contract_id, contract in table.items():
        if contract.producer != _LEDGER_PRODUCER or contract.media_type != media_type:
            raise ValueError(f"ledger contract global binding changed: {contract_id}")
    versions = {
        "CONFIDENCE_LEDGER_SCHEMA_VERSION": CONFIDENCE_LEDGER_SCHEMA_VERSION,
        "CONFIDENCE_LEDGER_REGISTRY_SCHEMA_VERSION": CONFIDENCE_LEDGER_REGISTRY_SCHEMA_VERSION,
    }
    if any(not isinstance(value, str) or not value for value in versions.values()):
        raise ValueError("ledger semantic version binding is invalid")
    return _canonical_json(
        {
            "contracts": contracts,
            "producer_binding": producer,
            "schema_bindings": dict(sorted(schema_bindings.items())),
            "media_type_binding": media_type,
            "version_bindings": versions,
        }
    )


def _snapshot_ledger_contracts(
    contracts: Mapping[str, _LedgerArtifactContract],
) -> Mapping[str, _LedgerArtifactContract]:
    """Copy mutable Pydantic metadata into a private immutable import-time table."""
    snapshot: dict[str, _LedgerArtifactContract] = {}
    for contract_id, contract in contracts.items():
        if contract.producer.git is not None:
            raise ConfidenceLedgerError("canonical_loaded_runtime_mismatch")
        snapshot[contract_id] = _LedgerArtifactContract(
            kind=contract.kind,
            schema=artifacts.SchemaInfo(
                name=contract.schema.name,
                version=contract.schema.version,
            ),
            producer=artifacts.ProducerInfo(
                component=str(contract.producer.component),
                version=contract.producer.version,
            ),
            media_type=contract.media_type,
            scope_bound=contract.scope_bound,
            payload_model=contract.payload_model,
        )
    return types.MappingProxyType(snapshot)


def _ledger_model_dependencies(
    contracts: Mapping[str, _LedgerArtifactContract],
) -> tuple[type[BaseModel], ...]:
    """Derive the full transitive payload model set from registered contracts."""
    pending = [
        contract.payload_model
        for contract in contracts.values()
        if contract.payload_model is not None
    ]
    discovered: dict[str, type[BaseModel]] = {}
    while pending:
        model = pending.pop()
        if not isinstance(model, type) or not issubclass(model, BaseModel):
            raise ValueError("ledger payload model is not a Pydantic model")
        identity = _runtime_type_ref(model)
        if identity in discovered:
            continue
        if globals().get(model.__name__) is not model:
            raise ValueError(f"ledger payload model global changed: {identity}")
        discovered[identity] = model
        fields = getattr(model, "model_fields", None)
        if not isinstance(fields, dict):
            raise ValueError(f"ledger payload model fields are unavailable: {identity}")
        for field in fields.values():
            pending.extend(
                candidate
                for candidate in _annotation_model_types(field.annotation)
                if candidate not in discovered.values()
            )
    return tuple(discovered[name] for name in sorted(discovered))


def _annotation_model_types(annotation: object) -> tuple[type[BaseModel], ...]:
    """Collect model classes nested in a resolved Pydantic field annotation."""
    found: dict[str, type[BaseModel]] = {}
    pending = [annotation]
    while pending:
        current = pending.pop()
        if isinstance(current, type) and issubclass(current, BaseModel):
            found[_runtime_type_ref(current)] = current
            continue
        pending.extend(typing.get_args(current))
    return tuple(found[name] for name in sorted(found))


def _ledger_model_projection(
    contracts: Mapping[str, _LedgerArtifactContract],
) -> str:
    """Bind runtime field state for every registered payload model and dependency."""
    result: dict[str, object] = {}
    for model in _ledger_model_dependencies(contracts):
        identity = _runtime_type_ref(model)
        fields = model.model_fields
        rows: dict[str, object] = {}
        for field_name, field in sorted(fields.items()):
            if not isinstance(field_name, str) or not field_name:
                raise ValueError(f"ledger model field name is invalid: {identity}")
            annotation = field.annotation
            annotation_name = (
                _runtime_type_ref(annotation) if isinstance(annotation, type) else str(annotation)
            )
            field_binding: dict[str, object] = {}
            field_state = getattr(field, "__dict__", None)
            if isinstance(field_state, dict):
                field_binding["dict"] = _normalize_runtime_binding_value(field_state, seen=set())
            for owner in type(field).__mro__:
                slots = getattr(owner, "__slots__", ())
                if isinstance(slots, str):
                    slots = (slots,)
                for slot in slots:
                    if (
                        not isinstance(slot, str)
                        or slot in field_binding
                        or not hasattr(field, slot)
                    ):
                        continue
                    field_binding[slot] = _normalize_runtime_binding_value(
                        getattr(field, slot),
                        seen=set(),
                    )
            if not field_binding:
                raise ValueError(
                    f"ledger model field state is unavailable: {identity}.{field_name}"
                )
            rows[field_name] = {
                "annotation": annotation_name,
                "required": field.is_required(),
                "field_binding": field_binding,
            }
        model_config = getattr(model, "model_config", None)
        if type(model_config) is not dict:
            raise ValueError(f"ledger model config is unavailable: {identity}")
        decorators = getattr(model, "__pydantic_decorators__", None)
        result[identity] = {
            "model_config": _normalize_runtime_binding_value(model_config, seen=set()),
            "decorators": _normalize_runtime_binding_value(decorators, seen=set()),
            "fields": rows,
        }
    return _canonical_json(result)


def _runtime_ledger_snapshot_projection(
    contracts: Mapping[str, _LedgerArtifactContract],
) -> str:
    """Bind every effective field in the pinned import-time contract snapshot."""
    if type(contracts) is not types.MappingProxyType:
        raise ValueError("pinned ledger contract snapshot is no longer immutable")
    rows: dict[str, dict[str, object]] = {}
    for contract_id, contract in sorted(contracts.items()):
        if not isinstance(contract_id, str) or not contract_id:
            raise ValueError("pinned ledger contract id is invalid")
        if type(contract) is not _LedgerArtifactContract:
            raise ValueError(f"pinned ledger contract model changed: {contract_id}")
        schema = _runtime_schema_projection(contract.schema)
        producer = _runtime_producer_projection(contract.producer)
        if not isinstance(contract.media_type, str) or not contract.media_type:
            raise ValueError(f"pinned ledger media type is invalid: {contract_id}")
        if type(contract.scope_bound) is not bool:
            raise ValueError(f"pinned ledger scope binding is invalid: {contract_id}")
        model = contract.payload_model
        model_name = model.__name__ if model is not None else None
        if model is not None and (
            not isinstance(model, type)
            or not issubclass(model, BaseModel)
            or globals().get(model_name) is not model
        ):
            raise ValueError(f"pinned ledger payload model changed: {contract_id}")
        if not isinstance(contract.kind, str) or not contract.kind:
            raise ValueError(f"pinned ledger artifact kind is invalid: {contract_id}")
        rows[contract_id] = {
            "kind": contract.kind,
            "schema": schema,
            "producer": producer,
            "media_type": contract.media_type,
            "scope_bound": contract.scope_bound,
            "payload_model": model_name,
        }
    if not rows:
        raise ValueError("pinned ledger contract snapshot is empty")
    return _canonical_json(rows)


def _capture_import_ledger_contract_state(
    source_path: Path = _LEDGER_MODULE_SOURCE_PATH,
) -> tuple[str, str, str, str]:
    """Reconcile source declarations, then freeze effective table/model dependencies."""
    try:
        source_bytes = source_path.read_bytes()
        declared = _source_ledger_contract_projection(source_bytes)
        effective = _runtime_ledger_contract_projection()
        models = _ledger_model_projection(_LEDGER_ARTIFACT_CONTRACTS)
        canon = _canonical_json(_normalize_runtime_binding_value(_CAS_CANON_SPEC, seen=set()))
        if declared != effective:
            raise ValueError("source ledger declarations differ from the loaded contract table")
        return _bytes_hash(source_bytes), effective, models, canon
    except (OSError, TypeError, ValueError, AttributeError) as exc:
        raise ConfidenceLedgerError("canonical_loaded_runtime_mismatch", str(exc)) from exc


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
    """Return the source checkout or installed package root for this module."""

    module_path = Path(__file__).resolve()
    checkout_root = module_path.parents[4]
    if (checkout_root / "src" / "polisyos").is_dir():
        return checkout_root
    installed_root = module_path.parents[3]
    if (installed_root / "polisyos").is_dir():
        return installed_root
    return checkout_root


def capture_loaded_deployment_identity() -> LoadedDeploymentIdentityObservation:
    """Capture the current process identity from the canonical owner snapshot.

    The snapshot is made once when this owner loads. It binds the loaded-code
    manifest and canonical deployment files, including the lock file, without
    rescanning the source tree on each N6 run. A later canonical ledger session
    revalidates currentness before it can admit N9 authority.
    """

    if not _IMPORT_TIME_LOADED_CODE_CONSISTENT:
        return LoadedDeploymentIdentityObservation(
            status="not_established",
            reason_code=_IMPORT_TIME_DEPLOYMENT_IDENTITY_REASON,
        )
    try:
        identity = _deployment_identity_from_baseline(_IMPORT_TIME_DEPLOYMENT_BASELINE)
    except (NameError, ConfidenceLedgerError):
        return LoadedDeploymentIdentityObservation(
            status="not_established",
            reason_code="canonical_deployment_identity_invalid",
        )
    return LoadedDeploymentIdentityObservation(
        status="established",
        deployment_identity=identity,
    )


def inspect_packaged_deployment_identity() -> PackagedDeploymentIdentityReadiness:
    """Report installed identity inputs without trusting a self-issued manifest."""

    root = _loaded_policy_engine_root()
    package_root = root / "polisyos"
    manifest_path = package_root / "runtime" / "quality" / "_packaged_deployment_identity.json"
    source_checkout = bool(
        (root / "pyproject.toml").is_file()
        and (root / "uv.lock").is_file()
        and (root / "src" / "polisyos").is_dir()
    )
    return PackagedDeploymentIdentityReadiness(
        verdict="UNRUN",
        inputs={
            "canonical_identity_owner": "polisyos.runtime.quality.confidence_ledger",
            "installed_package_root": package_root.as_posix(),
            "source_checkout_inputs_present": source_checkout,
            "package_manifest_present": manifest_path.is_file(),
            "lockfile_present_at_runtime": (root / "uv.lock").is_file(),
            "n6_census_verdict": "UNRUN",
        },
        unresolved_by_construction=(
            "packaged_build_identity_issuer_not_appointed",
            "n6_strangle_census_not_established",
            "deployment_authority_issuer_not_appointed",
        ),
    )


def observe_n6_deployment_currentness(
    *,
    recorded_identity_status: Literal["established", "not_established"] | None,
    recorded_deployment_identity: str | None,
) -> N6DeploymentCurrentnessObservation:
    """Compare a run with canonical loaded identity without reading source files.

    A recorded identity mismatch is typed stale. Historical runs without an
    identity remain replayable but cannot be called current. Matching identity
    remains UNRUN while the package-owned N6 census issuer is not appointed.
    """

    loaded = capture_loaded_deployment_identity()
    readiness = inspect_packaged_deployment_identity()
    unresolved = tuple(readiness.unresolved_by_construction)
    common = {
        "census_verdict": readiness.verdict,
        "recorded_identity_status": recorded_identity_status,
        "recorded_deployment_identity": recorded_deployment_identity,
        "loaded_identity_status": loaded.status,
        "loaded_deployment_identity": loaded.deployment_identity,
        "loaded_identity_reason_code": loaded.reason_code,
        "unresolved_by_construction": unresolved,
    }
    if recorded_identity_status is None:
        return N6DeploymentCurrentnessObservation(
            status="not_established",
            reason_code=(
                "n6_census_issuer_not_appointed"
                if loaded.status == "established"
                else "loaded_deployment_identity_not_established"
            ),
            **common,
        )
    if recorded_identity_status != "established" or recorded_deployment_identity is None:
        return N6DeploymentCurrentnessObservation(
            status="not_established",
            reason_code="historical_deployment_identity_not_recorded",
            **common,
        )
    if loaded.status != "established" or loaded.deployment_identity is None:
        return N6DeploymentCurrentnessObservation(
            status="not_established",
            reason_code="loaded_deployment_identity_not_established",
            **common,
        )
    if recorded_deployment_identity != loaded.deployment_identity:
        return N6DeploymentCurrentnessObservation(
            status="stale",
            reason_code="generation_cycle_deployment_identity_mismatch",
            **common,
        )
    if readiness.verdict != "PASS" or unresolved:
        reason_code = (
            "n6_census_issuer_not_appointed"
            if "n6_strangle_census_not_established" in unresolved
            else "n6_census_not_established"
        )
        return N6DeploymentCurrentnessObservation(
            status="not_established",
            reason_code=reason_code,
            **common,
        )
    return N6DeploymentCurrentnessObservation(
        status="current",
        census_verdict="PASS",
        recorded_identity_status=recorded_identity_status,
        recorded_deployment_identity=recorded_deployment_identity,
        loaded_identity_status=loaded.status,
        loaded_deployment_identity=loaded.deployment_identity,
        loaded_identity_reason_code=loaded.reason_code,
        reason_code="n6_currentness_established",
        unresolved_by_construction=(),
    )


def _policy_engine_deployment_identity(repo_root: Path) -> str:
    """Bind authority to disk bytes, runtime ABI, and actually loaded code."""

    return _deployment_identity_from_baseline(_deployment_baseline(repo_root))


def _deployment_identity_from_baseline(deployment_baseline: str) -> str:
    """Compose the authority identity from a content-complete baseline."""

    return _identity(
        "policy-engine-deployment",
        {
            "current_deployment": deployment_baseline,
            "authority_import_closure": _IMPORT_TIME_AUTHORITY_IMPORT_CLOSURE,
            "loaded_code_manifest": _IMPORT_TIME_LOADED_CODE_MANIFEST,
        },
    )


def _assert_loaded_runtime_matches_import_baseline(
    repo_root: Path,
    *,
    deployment_baseline: str | None = None,
) -> None:
    """Reject authority if disk or runtime differs from the importing process."""

    _assert_ledger_artifact_contracts_current()
    loaded_code_manifest, loaded_code_consistent = _loaded_code_manifest(
        repo_root,
        _derived_authority_import_closure(repo_root),
    )
    if (
        deployment_baseline or _deployment_baseline(repo_root)
    ) != _IMPORT_TIME_DEPLOYMENT_BASELINE or not (
        _IMPORT_TIME_LOADED_CODE_CONSISTENT
        and loaded_code_consistent
        and _loaded_code_evidence_projection(loaded_code_manifest)
        == _loaded_code_evidence_projection(_IMPORT_TIME_LOADED_CODE_MANIFEST)
    ):
        raise ConfidenceLedgerError("canonical_loaded_runtime_mismatch")


def _admit_loaded_runtime(
    repo_root: Path,
) -> tuple[str, _DeploymentQuickFence, str]:
    """Freeze and admit one complete runtime deployment identity."""

    deployment_baseline, deployment_quick_fence = _stable_deployment_snapshot(repo_root)
    _assert_loaded_runtime_matches_import_baseline(
        repo_root,
        deployment_baseline=deployment_baseline,
    )
    return (
        deployment_baseline,
        deployment_quick_fence,
        _deployment_identity_from_baseline(deployment_baseline),
    )


def _deployment_baseline(repo_root: Path) -> str:
    """Return a path-normalized full source, lock, project, and ABI baseline."""

    files: dict[str, str] = {}
    for relative in _deployment_relative_paths(repo_root):
        path = repo_root / relative
        try:
            content = path.read_bytes()
        except OSError as exc:
            raise ConfidenceLedgerError(
                "canonical_deployment_identity_invalid", relative.as_posix()
            ) from exc
        files[relative.as_posix()] = f"sha256:{hashlib.sha256(content).hexdigest()}"
    return _canonical_json(
        {
            "files": files,
            "python_runtime": _python_runtime_manifest(),
        }
    )


def _stable_deployment_snapshot(repo_root: Path) -> tuple[str, _DeploymentQuickFence]:
    """Capture content only when the cheap file/runtime fence remains stable."""

    before = _deployment_quick_fence(repo_root)
    baseline = _deployment_baseline(repo_root)
    after = _deployment_quick_fence(repo_root)
    if before != after:
        raise ConfidenceLedgerError("canonical_deployment_identity_invalid")
    return baseline, after


def _deployment_quick_fence(repo_root: Path) -> _DeploymentQuickFence:
    """Return a cheap path/inode/size/time fence for authority deployment files."""

    entries: list[_DeploymentFileFence] = []
    for relative in _deployment_relative_paths_from_closure(_IMPORT_TIME_AUTHORITY_IMPORT_CLOSURE):
        path = repo_root / relative
        try:
            stat = path.stat()
        except OSError as exc:
            raise ConfidenceLedgerError(
                "canonical_deployment_identity_invalid", relative.as_posix()
            ) from exc
        entries.append(
            (
                relative.as_posix(),
                stat.st_dev,
                stat.st_ino,
                stat.st_size,
                stat.st_mtime_ns,
                stat.st_ctime_ns,
            )
        )
    return tuple(entries), _canonical_json(_python_runtime_manifest())


def _deployment_relative_paths(repo_root: Path) -> tuple[Path, ...]:
    """Return the deployment files derived from the authority import closure."""

    return _deployment_relative_paths_from_closure(_derived_authority_import_closure(repo_root))


def _deployment_relative_paths_from_closure(
    closure: tuple[tuple[str, str], ...],
) -> tuple[Path, ...]:
    """Return deployment paths from one already admitted derived closure."""

    source_paths = tuple(Path(relative_path) for _module_name, relative_path in closure)
    if not source_paths:
        raise ConfidenceLedgerError("canonical_deployment_identity_invalid")
    return (Path("pyproject.toml"), Path("uv.lock"), *source_paths)


@dataclass(frozen=True, slots=True)
class _LiteralModuleGetattrProviderIndex:
    """Index literal PEP 562 providers found in one parsed source module."""

    providers_by_export: Mapping[str, frozenset[str]]
    invalid_exports: frozenset[str]


@dataclass(slots=True)
class _AuthorityImportClosureSourceIndex:
    """Cache source parses and PEP 562 indexes for one closure computation."""

    parsed_by_content: dict[bytes, ast.Module]
    providers_by_content: dict[bytes, _LiteralModuleGetattrProviderIndex]

    def parse(self, content: bytes, *, filename: str) -> ast.Module:
        """Parse exact source bytes once within the current closure computation."""

        tree = self.parsed_by_content.get(content)
        if tree is None:
            tree = ast.parse(content, filename=filename)
            self.parsed_by_content[content] = tree
        return tree


def _resolve_authority_import_closure(
    repo_root: Path,
    entry_module: str | Iterable[str],
    *,
    include_tools: bool = False,
) -> tuple[tuple[str, str], ...]:
    """Resolve one complete repository-local declared import closure.

    Runtime mode follows repository-local static imports outside typing-only
    arms plus source-declared PEP 562 re-exports. Literal dynamic targets are
    source-owner inputs, not runtime modules, unless reached through a static
    edge; owner/tool mode additionally sees literal dynamic imports and tools.
    Both modes exclude typing-only arms.
    """

    resolved: dict[str, Path] = {}
    pending = {entry_module} if isinstance(entry_module, str) else set(entry_module)
    allowed_roots = {"polisyos", *(("tools",) if include_tools else ())}
    directory_entries: dict[Path, frozenset[str]] = {}
    source_index = _AuthorityImportClosureSourceIndex({}, {})

    @functools.cache
    def resolve_source(module_name: str) -> Path | None:
        return _repository_module_source(
            repo_root,
            module_name,
            directory_entries=directory_entries,
        )

    while pending:
        module_name = min(pending)
        pending.remove(module_name)
        if module_name in resolved:
            continue
        relative = resolve_source(module_name)
        if relative is None:
            raise ConfidenceLedgerError(
                "canonical_loaded_runtime_mismatch",
                f"unresolved repository import: {module_name}",
            )
        resolved[module_name] = relative
        package = module_name if relative.name == "__init__.py" else module_name.rpartition(".")[0]
        try:
            source_bytes = (repo_root / relative).read_bytes()
            tree = source_index.parse(source_bytes, filename=relative.as_posix())
        except (OSError, SyntaxError) as exc:
            raise ConfidenceLedgerError(
                "canonical_loaded_runtime_mismatch",
                relative.as_posix(),
            ) from exc
        discovered: set[str] = set()
        nodes = _runtime_ast_nodes(tree)
        for node in nodes:
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if _repository_module_root(alias.name) in allowed_roots:
                        if resolve_source(alias.name) is None:
                            raise ConfidenceLedgerError(
                                "canonical_loaded_runtime_mismatch",
                                f"unresolved repository import: {alias.name}",
                            )
                        discovered.add(alias.name)
            elif isinstance(node, ast.ImportFrom):
                base = _resolve_import_from_base(node, package)
                if base is None or _repository_module_root(base) not in allowed_roots:
                    continue
                if resolve_source(base) is None:
                    raise ConfidenceLedgerError(
                        "canonical_loaded_runtime_mismatch",
                        f"unresolved repository import: {base}",
                    )
                discovered.add(base)
                for alias in node.names:
                    if alias.name == "*":
                        continue
                    candidate = f"{base}.{alias.name}"
                    if resolve_source(candidate) is not None:
                        discovered.add(candidate)
                        continue
                    provider = _literal_module_getattr_provider(
                        repo_root,
                        base,
                        alias.name,
                        directory_entries=directory_entries,
                        source_index=source_index,
                    )
                    if provider is not None and _repository_module_root(provider) in allowed_roots:
                        if resolve_source(provider) is None:
                            raise ConfidenceLedgerError(
                                "canonical_loaded_runtime_mismatch",
                                f"unresolved repository import: {provider}",
                            )
                        discovered.add(provider)
            elif isinstance(node, ast.Call):
                dynamic_ref = _literal_dynamic_import_ref(node)
                if (
                    include_tools
                    and dynamic_ref is not None
                    and _repository_module_root(dynamic_ref) in allowed_roots
                ):
                    if resolve_source(dynamic_ref) is None:
                        raise ConfidenceLedgerError(
                            "canonical_loaded_runtime_mismatch",
                            f"unresolved repository import: {dynamic_ref}",
                        )
                    discovered.add(dynamic_ref)
        for discovered_module in tuple(discovered):
            parts = discovered_module.split(".")
            for length in range(1, len(parts)):
                parent = ".".join(parts[:length])
                if resolve_source(parent) is not None:
                    discovered.add(parent)
        pending.update(discovered - resolved.keys())
    return tuple(
        (module_name, resolved[module_name].as_posix()) for module_name in sorted(resolved)
    )


def _derived_authority_import_closure(repo_root: Path) -> tuple[tuple[str, str], ...]:
    """Recompute and admit only the import-time authority closure."""

    resolved = _resolve_authority_import_closure(repo_root, __name__)
    if resolved != _IMPORT_TIME_AUTHORITY_IMPORT_CLOSURE:
        raise ConfidenceLedgerError(
            "canonical_loaded_runtime_mismatch",
            "authority import closure differs from source",
        )
    return resolved


def _literal_module_getattr_provider(
    repo_root: Path,
    module_name: str,
    export_name: str,
    *,
    directory_entries: dict[Path, frozenset[str]],
    source_index: _AuthorityImportClosureSourceIndex | None = None,
) -> str | None:
    """Resolve one literal PEP 562 re-export provider without importing it."""

    relative = _repository_module_source(
        repo_root,
        module_name,
        directory_entries=directory_entries,
    )
    if relative is None:
        return None
    if source_index is None:
        source_index = _AuthorityImportClosureSourceIndex({}, {})
    try:
        source_bytes = (repo_root / relative).read_bytes()
        tree = source_index.parse(source_bytes, filename=relative.as_posix())
    except (OSError, SyntaxError) as exc:
        raise ConfidenceLedgerError(
            "canonical_loaded_runtime_mismatch",
            relative.as_posix(),
        ) from exc
    provider_index = source_index.providers_by_content.get(source_bytes)
    if provider_index is None:
        provider_index = _literal_module_getattr_provider_index(tree)
        source_index.providers_by_content[source_bytes] = provider_index
    if export_name in provider_index.invalid_exports or "*" in provider_index.invalid_exports:
        raise ConfidenceLedgerError(
            "canonical_loaded_runtime_mismatch",
            f"non-literal repository re-export: {module_name}.{export_name}",
        )
    providers = provider_index.providers_by_export.get(export_name, frozenset())
    if len(providers) > 1:
        raise ConfidenceLedgerError(
            "canonical_loaded_runtime_mismatch",
            f"ambiguous repository re-export: {module_name}.{export_name}",
        )
    provider = next(iter(providers), None)
    if provider is not None and provider.startswith("."):
        try:
            provider = importlib.util.resolve_name(provider, module_name)
        except (ImportError, TypeError, ValueError) as exc:
            raise ConfidenceLedgerError(
                "canonical_loaded_runtime_mismatch",
                f"ambiguous relative repository re-export: {module_name}.{export_name}",
            ) from exc
    return provider


def _source_scope_nodes(
    nodes: Iterable[ast.AST], *, descend_into_ifs: bool = True
) -> Iterable[ast.AST]:
    """Walk one executable scope while excluding nested declarations."""

    pending = list(reversed(tuple(nodes)))
    while pending:
        node = pending.pop()
        yield node
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            continue
        if isinstance(node, ast.If) and _is_type_checking_test(node.test):
            children = node.orelse
        elif isinstance(node, ast.If) and not descend_into_ifs:
            children = ()
        else:
            children = tuple(ast.iter_child_nodes(node))
        pending.extend(reversed(children))


def _source_scope_bound_names(nodes: Iterable[ast.AST]) -> frozenset[str]:
    """Return names bound in a source scope, excluding nested definition bodies."""

    bound: set[str] = set()
    for node in _source_scope_nodes(nodes):
        if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            bound.add(node.id)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            bound.add(node.name)
        elif isinstance(node, ast.Import):
            bound.update(alias.asname or alias.name.partition(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            bound.update(alias.asname or alias.name for alias in node.names if alias.name != "*")
        elif isinstance(node, (ast.Global, ast.Nonlocal)):
            bound.update(node.names)
    return frozenset(bound)


def _literal_builtin_name_unshadowed(
    tree: ast.Module,
    function: ast.FunctionDef | ast.AsyncFunctionDef,
    name: str,
) -> bool:
    """Prove a name still denotes its builtin in both module and function scope."""

    parameters = {
        arg.arg
        for arg in (
            *function.args.posonlyargs,
            *function.args.args,
            *function.args.kwonlyargs,
        )
    }
    if function.args.vararg is not None:
        parameters.add(function.args.vararg.arg)
    if function.args.kwarg is not None:
        parameters.add(function.args.kwarg.arg)
    return bool(
        name not in _source_scope_bound_names(tree.body)
        and name not in _source_scope_bound_names(function.body)
        and name not in parameters
    )


def _literal_getattr_dispatch_names(test: ast.expr, parameter_name: str) -> frozenset[str]:
    """Return names selected by a literal equality or membership guard."""

    if not isinstance(test, ast.Compare) or len(test.ops) != 1 or len(test.comparators) != 1:
        return frozenset()
    left, right, operator = test.left, test.comparators[0], test.ops[0]
    if isinstance(operator, ast.Eq):
        if (
            isinstance(left, ast.Name)
            and left.id == parameter_name
            and isinstance(right, ast.Constant)
            and isinstance(right.value, str)
        ):
            return frozenset({right.value})
        if (
            isinstance(right, ast.Name)
            and right.id == parameter_name
            and isinstance(left, ast.Constant)
            and isinstance(left.value, str)
        ):
            return frozenset({left.value})
        return frozenset()
    if (
        isinstance(operator, ast.In)
        and isinstance(left, ast.Name)
        and left.id == parameter_name
        and isinstance(right, (ast.List, ast.Set, ast.Tuple))
        and all(
            isinstance(item, ast.Constant) and isinstance(item.value, str) for item in right.elts
        )
    ):
        return frozenset(item.value for item in right.elts)
    return frozenset()


def _literal_import_helper_bindings(
    tree: ast.Module,
    function: ast.FunctionDef | ast.AsyncFunctionDef,
) -> tuple[frozenset[str], frozenset[str]]:
    """Find unconditional module-scope importlib aliases without local shadows."""

    functions: set[str] = set()
    modules: set[str] = set()
    module_import_counts: dict[str, int] = {}
    for node in _source_scope_nodes(tree.body):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                bound_name = alias.asname or alias.name
                module_import_counts[bound_name] = module_import_counts.get(bound_name, 0) + 1
        elif isinstance(node, ast.Import):
            for alias in node.names:
                bound_name = alias.asname or alias.name.partition(".")[0]
                module_import_counts[bound_name] = module_import_counts.get(bound_name, 0) + 1

    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module == "importlib":
            functions.update(
                alias.asname or alias.name for alias in node.names if alias.name == "import_module"
            )
        elif isinstance(node, ast.Import):
            modules.update(
                alias.asname or "importlib" for alias in node.names if alias.name == "importlib"
            )

    module_stores = {
        node.id
        for node in _source_scope_nodes(tree.body)
        if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del))
    }
    local_stores = {
        node.id
        for node in _source_scope_nodes(function.body)
        if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del))
    }
    local_imports: set[str] = set()
    for node in _source_scope_nodes(function.body):
        if isinstance(node, ast.Import):
            local_imports.update(
                alias.asname or alias.name.partition(".")[0] for alias in node.names
            )
        elif isinstance(node, ast.ImportFrom):
            local_imports.update(
                alias.asname or alias.name for alias in node.names if alias.name != "*"
            )
    parameters = {
        arg.arg
        for arg in (
            *function.args.posonlyargs,
            *function.args.args,
            *function.args.kwonlyargs,
        )
    }
    if function.args.vararg is not None:
        parameters.add(function.args.vararg.arg)
    if function.args.kwarg is not None:
        parameters.add(function.args.kwarg.arg)
    shadows = module_stores | local_stores | local_imports | parameters
    for alias in functions | modules:
        if module_import_counts.get(alias) != 1 or alias in shadows:
            functions.discard(alias)
            modules.discard(alias)
    return frozenset(functions), frozenset(modules)


def _literal_source_module_target(
    call: ast.Call,
    imported_functions: frozenset[str],
    imported_modules: frozenset[str],
    *,
    builtin_import_unshadowed: bool,
) -> tuple[bool, str | None]:
    """Resolve a declared literal importlib or absolute __import__ target."""

    function = call.func
    imported_function = isinstance(function, ast.Name) and function.id in imported_functions
    imported_module_function = (
        isinstance(function, ast.Attribute)
        and function.attr == "import_module"
        and isinstance(function.value, ast.Name)
        and function.value.id in imported_modules
    )
    builtin_import = (
        builtin_import_unshadowed and isinstance(function, ast.Name) and function.id == "__import__"
    )
    if not (imported_function or imported_module_function or builtin_import):
        return False, None
    if not call.args or not isinstance(call.args[0], ast.Constant):
        return True, None
    target = call.args[0].value
    if not isinstance(target, str):
        return True, None
    if target.startswith("."):
        package = call.args[1] if len(call.args) > 1 else None
        valid_package = isinstance(package, ast.Name) and package.id in {"__name__", "__package__"}
        if not (imported_function or imported_module_function) or not valid_package:
            return True, None
    return True, target


def _simple_assignment(node: ast.AST) -> tuple[str, ast.expr] | None:
    """Return one simple assignment binding, excluding destructuring."""

    if (
        isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
    ):
        return node.targets[0].id, node.value
    if (
        isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
        and node.value is not None
    ):
        return node.target.id, node.value
    return None


def _dynamic_getattr_name(node: ast.AST, parameter_name: str) -> bool:
    """Return whether getattr reads the PEP 562 name argument."""

    return bool(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "getattr"
        and len(node.args) >= 2
        and isinstance(node.args[1], ast.Name)
        and node.args[1].id == parameter_name
    )


def _literal_module_getattr_provider_index(tree: ast.Module) -> _LiteralModuleGetattrProviderIndex:
    """Index literal dictionaries and guarded source-declared lazy providers."""

    mapping_names: set[str] = set()
    functions: list[ast.FunctionDef | ast.AsyncFunctionDef] = []
    for statement in tree.body:
        if (
            isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef))
            and statement.name == "__getattr__"
            and statement.args.args
        ):
            functions.append(statement)
            parameter = statement.args.args[0].arg
            mapping_names.update(
                node.value.id
                for node in ast.walk(statement)
                if isinstance(node, ast.Subscript)
                and isinstance(node.value, ast.Name)
                and isinstance(node.slice, ast.Name)
                and node.slice.id == parameter
            )

    providers: dict[str, set[str]] = {}
    invalid: set[str] = set()
    for statement in tree.body:
        if isinstance(statement, ast.Assign) and len(statement.targets) == 1:
            target, value = statement.targets[0], statement.value
        elif isinstance(statement, ast.AnnAssign):
            target, value = statement.target, statement.value
        else:
            continue
        if not (
            isinstance(target, ast.Name)
            and target.id in mapping_names
            and isinstance(value, ast.Dict)
        ):
            continue
        for key, row in zip(value.keys, value.values, strict=True):
            if not (
                isinstance(key, ast.Constant)
                and isinstance(key.value, str)
                and isinstance(row, (ast.Tuple, ast.List))
                and row.elts
            ):
                continue
            module = row.elts[0]
            if isinstance(module, ast.Constant) and isinstance(module.value, str):
                providers.setdefault(key.value, set()).add(module.value)
            else:
                invalid.add(key.value)

    for function in functions:
        parameter = function.args.args[0].arg
        imported_functions, imported_modules = _literal_import_helper_bindings(tree, function)
        builtin_getattr_unshadowed = _literal_builtin_name_unshadowed(tree, function, "getattr")
        builtin_import_unshadowed = _literal_builtin_name_unshadowed(tree, function, "__import__")
        nodes = tuple(_source_scope_nodes(function.body))
        lookups = tuple(node for node in nodes if _dynamic_getattr_name(node, parameter))
        calls_getattr = any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "getattr"
            for node in nodes
        )
        calls_import = any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "__import__"
            for node in nodes
        )
        if mapping_names and (
            (calls_getattr and not builtin_getattr_unshadowed)
            or (calls_import and not builtin_import_unshadowed)
        ):
            invalid.add("*")
        if (calls_getattr and not builtin_getattr_unshadowed) or (
            calls_import and not builtin_import_unshadowed
        ):
            invalid.add("*")
        if lookups and not builtin_getattr_unshadowed:
            invalid.add("*")
            continue
        handled: set[int] = set()
        for branch in nodes:
            if not isinstance(branch, ast.If):
                continue
            branch_lookups = tuple(
                node
                for node in _source_scope_nodes(branch.body, descend_into_ifs=False)
                if _dynamic_getattr_name(node, parameter)
            )
            if not branch_lookups:
                continue
            handled.update(id(node) for node in branch_lookups)
            names = _literal_getattr_dispatch_names(branch.test, parameter)
            if not names:
                invalid.add("*")
                continue
            module_vars = {
                call.args[0].id for call in branch_lookups if isinstance(call.args[0], ast.Name)
            }
            by_var: dict[str, set[str]] = {}
            invalid_vars: set[str] = set()
            for node in branch.body:
                binding = _simple_assignment(node)
                if binding is None or binding[0] not in module_vars:
                    continue
                variable, value = binding
                if not isinstance(value, ast.Call):
                    invalid_vars.add(variable)
                    continue
                recognized, module = _literal_source_module_target(
                    value,
                    imported_functions,
                    imported_modules,
                    builtin_import_unshadowed=builtin_import_unshadowed,
                )
                if not recognized or module is None:
                    invalid_vars.add(variable)
                    continue
                by_var.setdefault(variable, set()).add(module)
            for call in branch_lookups:
                expr = call.args[0]
                module = None
                if isinstance(expr, ast.Name):
                    possible = by_var.get(expr.id, set())
                    if expr.id not in invalid_vars and len(possible) == 1:
                        module = next(iter(possible))
                elif isinstance(expr, ast.Call):
                    recognized, module = _literal_source_module_target(
                        expr,
                        imported_functions,
                        imported_modules,
                        builtin_import_unshadowed=builtin_import_unshadowed,
                    )
                    if not recognized:
                        module = None
                if module is None:
                    invalid.update(names)
                else:
                    for name in names:
                        providers.setdefault(name, set()).add(module)
        if any(id(call) not in handled for call in lookups):
            invalid.add("*")
    return _LiteralModuleGetattrProviderIndex(
        providers_by_export=types.MappingProxyType(
            {name: frozenset(modules) for name, modules in providers.items()}
        ),
        invalid_exports=frozenset(invalid),
    )


def _runtime_ast_nodes(node: ast.AST) -> Iterable[ast.AST]:
    """Walk declarations that can execute, excluding typing-only import arms."""

    yield node
    if isinstance(node, ast.If) and _is_type_checking_test(node.test):
        for child in node.orelse:
            yield from _runtime_ast_nodes(child)
        return
    for child in ast.iter_child_nodes(node):
        yield from _runtime_ast_nodes(child)


def _is_type_checking_test(node: ast.expr) -> bool:
    """Return whether an ``if`` test is the conventional TYPE_CHECKING guard."""

    return bool(
        (isinstance(node, ast.Name) and node.id == "TYPE_CHECKING")
        or (
            isinstance(node, ast.Attribute)
            and node.attr == "TYPE_CHECKING"
            and isinstance(node.value, ast.Name)
            and node.value.id in {"typing", "typing_extensions"}
        )
    )


def _repository_module_root(module_name: str) -> str:
    """Return the leading module component for one dotted import name."""

    return module_name.partition(".")[0]


def _literal_dynamic_import_ref(node: ast.Call) -> str | None:
    """Return a literal ``import_module``/``__import__`` target when declared."""

    target = node.func
    is_import_module = bool(
        isinstance(target, ast.Attribute)
        and target.attr == "import_module"
        and isinstance(target.value, ast.Name)
        and target.value.id == "importlib"
    )
    is_dunder_import = isinstance(target, ast.Name) and target.id == "__import__"
    if not (is_import_module or is_dunder_import) or not node.args:
        return None
    value = node.args[0]
    return value.value if isinstance(value, ast.Constant) and isinstance(value.value, str) else None


def _import_authority_closure_modules(
    closure: tuple[tuple[str, str], ...],
) -> None:
    """Load every declared authority module before live-code capture."""

    for module_name, _relative_path in closure:
        try:
            module = importlib.import_module(module_name)
        except Exception as exc:
            raise ConfidenceLedgerError(
                "canonical_loaded_runtime_mismatch",
                f"authority closure import failed: {module_name}",
            ) from exc
        if sys.modules.get(module_name) is not module:
            raise ConfidenceLedgerError(
                "canonical_loaded_runtime_mismatch",
                f"authority closure module not loaded: {module_name}",
            )


def _resolve_import_from_base(node: ast.ImportFrom, package: str) -> str | None:
    """Resolve one absolute or relative ``from`` import base."""

    if node.level == 0:
        return node.module
    relative_name = "." * node.level + (node.module or "")
    try:
        return importlib.util.resolve_name(relative_name, package)
    except (ImportError, ValueError) as exc:
        raise ConfidenceLedgerError(
            "canonical_loaded_runtime_mismatch",
            f"ambiguous relative import: {relative_name}",
        ) from exc


def _repository_module_source(
    repo_root: Path,
    module_name: str,
    *,
    directory_entries: dict[Path, frozenset[str]] | None = None,
) -> Path | None:
    """Resolve one repository Python module without importing it."""

    module_root = _repository_module_root(module_name)
    if module_root not in {"polisyos", "tools"}:
        return None
    module_parts = module_name.split(".")
    if module_root == "polisyos":
        base = Path("src") if (repo_root / "src" / "polisyos").is_dir() else Path()
    else:
        base = Path()
    package_path = base.joinpath(*module_parts, "__init__.py")
    module_path = base.joinpath(*module_parts).with_suffix(".py")
    # FileFinder resolves a package directory before a same-named module file.
    # Mirror that rule so the declared closure binds the source Python loads.
    if _repository_file_exists_exactly(
        repo_root,
        package_path,
        directory_entries=directory_entries,
    ):
        return package_path
    return (
        module_path
        if _repository_file_exists_exactly(
            repo_root,
            module_path,
            directory_entries=directory_entries,
        )
        else None
    )


def _repository_file_exists_exactly(
    repo_root: Path,
    relative: Path,
    *,
    directory_entries: dict[Path, frozenset[str]] | None = None,
) -> bool:
    """Resolve repository paths without case-folding filesystem aliases."""

    current = repo_root
    try:
        for part in relative.parts:
            if directory_entries is None:
                names = frozenset(entry.name for entry in current.iterdir())
            else:
                names = directory_entries.get(current)
                if names is None:
                    names = frozenset(entry.name for entry in current.iterdir())
                    directory_entries[current] = names
            if part not in names:
                return False
            current /= part
    except OSError:
        return False
    return current.is_file()


def _decorator_expression_name(node: ast.expr) -> str:
    """Return one stable source-level decorator name."""

    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return f"{_decorator_expression_name(node.value)}.{node.attr}"
    if isinstance(node, ast.Call):
        return f"{_decorator_expression_name(node.func)}()"
    return type(node).__name__


def _literal_lru_cache_parameters(
    node: ast.expr,
    *,
    source_path: Path,
) -> tuple[int | None, bool] | None:
    """Return one source-declared ``lru_cache`` policy or fail closed."""

    target = node.func if isinstance(node, ast.Call) else node
    decorator_name = _decorator_expression_name(target)
    if decorator_name != "lru_cache" and not decorator_name.endswith(".lru_cache"):
        return None
    maxsize: object = 128
    typed: object = False
    assigned: set[str] = set()
    if isinstance(node, ast.Call):
        if len(node.args) > 2:
            raise ConfidenceLedgerError(
                "canonical_loaded_runtime_mismatch",
                f"authority lru_cache policy invalid: {source_path.name}",
            )
        for index, argument in enumerate(node.args):
            name = ("maxsize", "typed")[index]
            try:
                value = ast.literal_eval(argument)
            except (ValueError, TypeError, SyntaxError, MemoryError) as exc:
                raise ConfidenceLedgerError(
                    "canonical_loaded_runtime_mismatch",
                    f"authority lru_cache policy not literal: {source_path.name}",
                ) from exc
            if name == "maxsize":
                maxsize = value
            else:
                typed = value
            assigned.add(name)
        for keyword in node.keywords:
            if keyword.arg not in {"maxsize", "typed"} or keyword.arg in assigned:
                raise ConfidenceLedgerError(
                    "canonical_loaded_runtime_mismatch",
                    f"authority lru_cache policy invalid: {source_path.name}",
                )
            try:
                value = ast.literal_eval(keyword.value)
            except (ValueError, TypeError, SyntaxError, MemoryError) as exc:
                raise ConfidenceLedgerError(
                    "canonical_loaded_runtime_mismatch",
                    f"authority lru_cache policy not literal: {source_path.name}",
                ) from exc
            if keyword.arg == "maxsize":
                maxsize = value
            else:
                typed = value
            assigned.add(keyword.arg)
    if not ((maxsize is None or (type(maxsize) is int and maxsize >= 0)) and type(typed) is bool):
        raise ConfidenceLedgerError(
            "canonical_loaded_runtime_mismatch",
            f"authority lru_cache policy invalid: {source_path.name}",
        )
    return maxsize, typed


def _loader_owned_callable_slots(source_path: Path) -> tuple[_LoaderOwnedCallableSlot, ...]:
    """Enumerate direct module and loader-local class callable slots."""

    try:
        tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    except (OSError, SyntaxError, UnicodeError) as exc:
        raise ConfidenceLedgerError(
            "canonical_loaded_runtime_mismatch",
            f"authority module source invalid: {source_path.name}",
        ) from exc
    declarations: dict[tuple[tuple[str, ...], str], _LoaderOwnedCallableSlot] = {}

    def add_function(
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        owner_path: tuple[str, ...],
    ) -> None:
        key = (owner_path, node.name)
        decorators = tuple(_decorator_expression_name(item) for item in node.decorator_list)
        firstlineno = min((node.lineno, *(item.lineno for item in node.decorator_list)))
        accessor_roles: set[str] = set()
        for decorator in decorators:
            if decorator.endswith(".setter"):
                accessor_roles.add("fset")
            elif decorator.endswith(".deleter"):
                accessor_roles.add("fdel")
            elif (
                decorator.endswith(".getter")
                or decorator == "property"
                or decorator.startswith("computed_field")
            ):
                accessor_roles.add("fget")
        if len(accessor_roles) > 1:
            raise ConfidenceLedgerError(
                "canonical_loaded_runtime_mismatch",
                f"authority property declaration ambiguous: {source_path.name}:{node.lineno}",
            )
        role = next(iter(accessor_roles), "function")
        lru_cache_parameters = tuple(
            parameters
            for decorator in node.decorator_list
            if (
                parameters := _literal_lru_cache_parameters(
                    decorator,
                    source_path=source_path,
                )
            )
            is not None
        )
        if len(lru_cache_parameters) > 1:
            raise ConfidenceLedgerError(
                "canonical_loaded_runtime_mismatch",
                f"authority lru_cache declaration ambiguous: {source_path.name}:{node.lineno}",
            )
        previous = declarations.get(key)
        extends_property = role in {"fset", "fdel"} and previous is not None
        source_firstlinenos = dict(previous.source_firstlinenos) if extends_property else {}
        source_firstlinenos[role] = firstlineno
        cache_policies = {
            item_role: (item_line, maxsize, typed)
            for item_role, item_line, maxsize, typed in (
                previous.lru_cache_parameters if extends_property else ()
            )
        }
        if lru_cache_parameters:
            maxsize, typed = lru_cache_parameters[0]
            cache_policies[role] = (firstlineno, maxsize, typed)
        else:
            cache_policies.pop(role, None)
        merged_decorators = (
            {*previous.decorators, *decorators} if extends_property else set(decorators)
        )
        property_accessors = tuple(
            sorted(item_role for item_role in source_firstlinenos if item_role != "function")
        )
        if property_accessors:
            descriptor_kind = "property"
        elif owner_path and node.name == "__new__":
            descriptor_kind = "staticmethod"
        elif (owner_path and node.name in {"__class_getitem__", "__init_subclass__"}) or any(
            item == "classmethod" or item.endswith(".classmethod") for item in decorators
        ):
            descriptor_kind = "classmethod"
        elif any(item == "staticmethod" or item.endswith(".staticmethod") for item in decorators):
            descriptor_kind = "staticmethod"
        elif lru_cache_parameters:
            descriptor_kind = "lru_cache"
        else:
            descriptor_kind = "function"
        declarations[key] = _LoaderOwnedCallableSlot(
            owner_path=owner_path,
            binding_name=node.name,
            descriptor_kind=(
                previous.descriptor_kind
                if extends_property and previous is not None
                else descriptor_kind
            ),
            property_accessors=property_accessors,
            decorators=tuple(sorted(merged_decorators)),
            source_firstlinenos=tuple(sorted(source_firstlinenos.items())),
            lru_cache_parameters=tuple(
                sorted(
                    (item_role, item_line, maxsize, typed)
                    for item_role, (item_line, maxsize, typed) in cache_policies.items()
                )
            ),
        )

    def add_class(node: ast.ClassDef, owner_path: tuple[str, ...]) -> None:
        class_path = (*owner_path, node.name)
        for child in node.body:
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                add_function(child, class_path)
            elif isinstance(child, ast.ClassDef):
                add_class(child, class_path)

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            add_function(node, ())
        elif isinstance(node, ast.ClassDef):
            add_class(node, ())
    return tuple(declarations[key] for key in sorted(declarations))


def _loader_owned_slot_owner(
    module: object,
    module_name: str,
    owner_path: tuple[str, ...],
) -> object | None:
    """Resolve an exact loader-local class path without inherited lookup."""

    owner = module
    for index, name in enumerate(owner_path):
        namespace = getattr(owner, "__dict__", {})
        if not isinstance(namespace, Mapping):
            return None
        owner = namespace.get(name)
        expected_qualname = ".".join(owner_path[: index + 1])
        if not (
            isinstance(owner, type)
            and owner.__module__ == module_name
            and owner.__qualname__ == expected_qualname
        ):
            return None
    return owner


def _unwrapped_function_chain(
    function: types.FunctionType,
) -> tuple[types.FunctionType, tuple[types.FunctionType, ...]]:
    """Return one function's terminal ``__wrapped__`` target and outer chain."""

    chain: list[types.FunctionType] = []
    seen: set[int] = set()
    current = function
    while id(current) not in seen:
        seen.add(id(current))
        chain.append(current)
        wrapped = getattr(current, "__wrapped__", None)
        if not isinstance(wrapped, types.FunctionType):
            break
        current = wrapped
    return chain[-1], tuple(chain)


def _source_scope_returned_function_names(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> tuple[str | None, ...]:
    """Return direct-scope return names without descending into nested scopes."""

    returned: list[str | None] = []
    pending = list(reversed(node.body))
    while pending:
        current = pending.pop()
        if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            continue
        if isinstance(current, ast.Return):
            returned.append(current.value.id if isinstance(current.value, ast.Name) else None)
            continue
        pending.extend(reversed(list(ast.iter_child_nodes(current))))
    return tuple(returned)


def _returned_local_wrapper_path(
    factory_node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> tuple[str, ...] | None:
    """Resolve a simple, unique nested-function return path for a decorator."""

    path: list[str] = []
    current = factory_node
    while True:
        nested = [
            child
            for child in current.body
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        if not nested:
            return tuple(path) if path else None
        returned = _source_scope_returned_function_names(current)
        if len(nested) != 1 or not returned or any(name != nested[0].name for name in returned):
            return None
        path.append(nested[0].name)
        current = nested[0]


def _exact_literal_equal(actual: object, expected: object) -> bool:
    """Compare only immutable source-literal values with exact runtime types."""

    if type(actual) is not type(expected):
        return False
    if type(actual) is tuple:
        return len(actual) == len(expected) and all(
            _exact_literal_equal(left, right) for left, right in zip(actual, expected, strict=True)
        )
    if type(actual) in {str, int, bool, float, bytes, type(None)}:
        return actual == expected
    return False


_UNSUPPORTED_SOURCE_LITERAL = object()


def _source_literal(
    node: ast.AST,
    *,
    expected_type: type[object] | None = None,
) -> object:
    """Read a supported literal, optionally requiring an exact constant type."""

    if expected_type is not None:
        if not isinstance(node, ast.Constant) or type(node.value) is not expected_type:
            raise ValueError("source value is not the required literal")
        return node.value
    try:
        value = ast.literal_eval(node)
    except (ValueError, TypeError, SyntaxError, MemoryError):
        return _UNSUPPORTED_SOURCE_LITERAL
    if type(value) in {str, int, bool, float, bytes, type(None)}:
        return value
    if type(value) is tuple and all(
        type(item) in {str, int, bool, float, bytes, type(None)} for item in value
    ):
        return value
    return _UNSUPPORTED_SOURCE_LITERAL


def _source_function_defaults_match(
    function: types.FunctionType,
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> bool:
    """Require live positional and keyword-only defaults to match source literals."""

    positional_defaults = tuple(_source_literal(item) for item in node.args.defaults)
    if any(value is _UNSUPPORTED_SOURCE_LITERAL for value in positional_defaults):
        return False
    actual_positional_defaults = function.__defaults__ or ()
    if len(actual_positional_defaults) != len(positional_defaults) or any(
        not _exact_literal_equal(actual, expected)
        for actual, expected in zip(actual_positional_defaults, positional_defaults, strict=True)
    ):
        return False

    expected_keyword_defaults: dict[str, object] = {}
    if len(node.args.kwonlyargs) != len(node.args.kw_defaults):
        return False
    for argument, default in zip(node.args.kwonlyargs, node.args.kw_defaults, strict=True):
        if default is None:
            continue
        value = _source_literal(default)
        if value is _UNSUPPORTED_SOURCE_LITERAL:
            return False
        expected_keyword_defaults[argument.arg] = value
    actual_keyword_defaults = function.__kwdefaults__
    if actual_keyword_defaults is None:
        actual_keyword_defaults = {}
    if type(actual_keyword_defaults) is not dict or set(actual_keyword_defaults) != set(
        expected_keyword_defaults
    ):
        return False
    return all(
        _exact_literal_equal(actual_keyword_defaults[name], expected)
        for name, expected in expected_keyword_defaults.items()
    )


def _source_decorator_factory_captures(
    factory_node: ast.FunctionDef | ast.AsyncFunctionDef,
    decorator_node: ast.expr,
    *,
    terminal: types.FunctionType,
) -> dict[str, object] | None:
    """Bind a literal decorator call against its complete non-variadic source signature."""

    if factory_node.args.vararg is not None or factory_node.args.kwarg is not None:
        return None
    positional_parameters = (
        *factory_node.args.posonlyargs,
        *factory_node.args.args,
    )
    keyword_only_parameters = tuple(factory_node.args.kwonlyargs)
    parameter_names = tuple(
        argument.arg for argument in (*positional_parameters, *keyword_only_parameters)
    )
    if len(set(parameter_names)) != len(parameter_names):
        return None

    values: dict[str, object] = {}
    default_start = len(positional_parameters) - len(factory_node.args.defaults)
    for index, default in enumerate(factory_node.args.defaults, start=default_start):
        value = _source_literal(default)
        if value is _UNSUPPORTED_SOURCE_LITERAL:
            return None
        values[positional_parameters[index].arg] = value
    if len(keyword_only_parameters) != len(factory_node.args.kw_defaults):
        return None
    for argument, default in zip(
        keyword_only_parameters, factory_node.args.kw_defaults, strict=True
    ):
        if default is None:
            continue
        value = _source_literal(default)
        if value is _UNSUPPORTED_SOURCE_LITERAL:
            return None
        values[argument.arg] = value

    explicit_bindings: set[str] = set()
    if isinstance(decorator_node, ast.Call):
        if len(decorator_node.args) > len(positional_parameters):
            return None
        for index, argument in enumerate(decorator_node.args):
            name = positional_parameters[index].arg
            value = _source_literal(argument)
            if value is _UNSUPPORTED_SOURCE_LITERAL:
                return None
            values[name] = value
            explicit_bindings.add(name)

        positional_only_names = {argument.arg for argument in factory_node.args.posonlyargs}
        keywordable_names = {argument.arg for argument in factory_node.args.args} | {
            argument.arg for argument in keyword_only_parameters
        }
        for keyword in decorator_node.keywords:
            if (
                keyword.arg is None
                or keyword.arg in positional_only_names
                or keyword.arg not in keywordable_names
                or keyword.arg in explicit_bindings
            ):
                return None
            value = _source_literal(keyword.value)
            if value is _UNSUPPORTED_SOURCE_LITERAL:
                return None
            values[keyword.arg] = value
            explicit_bindings.add(keyword.arg)
    else:
        if not positional_parameters:
            return None
        values[positional_parameters[0].arg] = terminal

    if set(parameter_names) - set(values):
        return None
    return values


def _source_slot_function_node(
    tree: ast.Module,
    slot: _LoaderOwnedCallableSlot,
) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    """Resolve one source-declared function slot without evaluating imports."""

    body: list[ast.stmt] = tree.body
    for class_name in slot.owner_path:
        owner = next(
            (
                statement
                for statement in body
                if isinstance(statement, ast.ClassDef) and statement.name == class_name
            ),
            None,
        )
        if owner is None:
            return None
        body = owner.body
    declaration = next(
        (
            statement
            for statement in body
            if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef))
            and statement.name == slot.binding_name
        ),
        None,
    )
    return declaration


@dataclass(frozen=True)
class _SourceDecoratorParameter:
    """One parameter reconstructed only from a loader-matched source function."""

    name: str
    kind_name: str
    has_default: bool
    default: object
    has_annotation: bool
    annotation: str | None


@dataclass(frozen=True)
class _SourceDecoratorParameterMap:
    """Ordered source-derived parameters exposed by ``Signature.parameters``."""

    parameters: tuple[_SourceDecoratorParameter, ...]


@dataclass(frozen=True)
class _SourceDecoratorSignature:
    """A signature projection derived from one source AST declaration."""

    parameters: tuple[_SourceDecoratorParameter, ...]
    has_return_annotation: bool
    return_annotation: str | None


@dataclass(frozen=True)
class _SourceResolvedAnnotation:
    """Supported union members resolved through source-declared imports."""

    members: tuple[object, ...]


@dataclass(frozen=True)
class _SourceResolvedAnnotationMap:
    """The selector annotation exposed by source-derived ``get_type_hints``."""

    selector_name: str
    selector_annotation: _SourceResolvedAnnotation | None


@dataclass(frozen=True)
class _SourceBoundOperation:
    """A method operation accepted by the bounded source expression evaluator."""

    name: str
    receiver: object


_SOURCE_DERIVATION_FAILED = object()


def _source_decorator_truth(value: object) -> object:
    """Resolve truthiness only for exact immutable scalar values in the source subset."""

    if value is _SOURCE_DERIVATION_FAILED:
        return _SOURCE_DERIVATION_FAILED
    if value is None:
        return False
    if type(value) in {bool, int, float, str, bytes, tuple}:
        return bool(value)
    return _SOURCE_DERIVATION_FAILED


def _source_import_binding(
    name: str,
    *,
    tree: ast.Module,
    module: object,
    module_name: str,
) -> object:
    """Resolve one source import and require the live module binding to retain it."""

    namespace = getattr(module, "__dict__", None)
    if type(namespace) is not dict:
        return _SOURCE_DERIVATION_FAILED
    imported: list[tuple[str, str]] = []
    for statement in tree.body:
        if isinstance(statement, ast.ImportFrom):
            for alias in statement.names:
                if alias.name == "*":
                    continue
                local_name = alias.asname or alias.name
                if local_name == name:
                    if statement.level:
                        package = module_name.rpartition(".")[0]
                        try:
                            imported_module = importlib.util.resolve_name(
                                "." * statement.level + (statement.module or ""),
                                package,
                            )
                        except (ImportError, ValueError):
                            return _SOURCE_DERIVATION_FAILED
                    else:
                        imported_module = statement.module
                    if not imported_module:
                        return _SOURCE_DERIVATION_FAILED
                    imported.append((imported_module, alias.name))
        elif isinstance(statement, ast.Import):
            for alias in statement.names:
                local_name = alias.asname or alias.name.split(".", 1)[0]
                if local_name == name:
                    imported.append((alias.name if alias.asname else local_name, ""))
    if len(imported) > 1:
        return _SOURCE_DERIVATION_FAILED
    if not imported:
        if name in namespace:
            return _SOURCE_DERIVATION_FAILED
        builtin_namespace = namespace.get("__builtins__", _builtins)
        if builtin_namespace is _builtins:
            builtin_namespace = vars(_builtins)
        if type(builtin_namespace) is not dict:
            return _SOURCE_DERIVATION_FAILED
        expected_builtin = vars(_builtins).get(name, _SOURCE_DERIVATION_FAILED)
        if (
            expected_builtin is _SOURCE_DERIVATION_FAILED
            or builtin_namespace.get(name) is not expected_builtin
        ):
            return _SOURCE_DERIVATION_FAILED
        return expected_builtin

    target_module_name, imported_name = imported[0]
    target_module = sys.modules.get(target_module_name)
    target_namespace = getattr(target_module, "__dict__", None)
    if type(target_namespace) is not dict:
        return _SOURCE_DERIVATION_FAILED
    expected = (
        target_module
        if not imported_name
        else target_namespace.get(imported_name, _SOURCE_DERIVATION_FAILED)
    )
    if expected is _SOURCE_DERIVATION_FAILED or namespace.get(name) is not expected:
        return _SOURCE_DERIVATION_FAILED
    return expected


def _source_future_annotations_enabled(tree: ast.Module) -> bool:
    """Return whether this module's signatures use postponed annotations."""

    return any(
        isinstance(statement, ast.ImportFrom)
        and statement.module == "__future__"
        and any(alias.name == "annotations" for alias in statement.names)
        for statement in tree.body
    )


def _source_parameter_nodes(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> tuple[tuple[ast.arg, str, ast.expr | None], ...] | None:
    """Enumerate Python parameters and defaults in canonical signature order."""

    arguments = node.args
    positional = [*arguments.posonlyargs, *arguments.args]
    if len(arguments.defaults) > len(positional):
        return None
    default_start = len(positional) - len(arguments.defaults)
    defaults: dict[str, ast.expr] = {
        argument.arg: default
        for argument, default in zip(positional[default_start:], arguments.defaults, strict=True)
    }
    rows: list[tuple[ast.arg, str, ast.expr | None]] = []
    for argument in arguments.posonlyargs:
        rows.append((argument, "POSITIONAL_ONLY", defaults.get(argument.arg)))
    for argument in arguments.args:
        rows.append((argument, "POSITIONAL_OR_KEYWORD", defaults.get(argument.arg)))
    if arguments.vararg is not None:
        rows.append((arguments.vararg, "VAR_POSITIONAL", None))
    if len(arguments.kwonlyargs) != len(arguments.kw_defaults):
        return None
    for argument, default in zip(arguments.kwonlyargs, arguments.kw_defaults, strict=True):
        rows.append((argument, "KEYWORD_ONLY", default))
    if arguments.kwarg is not None:
        rows.append((arguments.kwarg, "VAR_KEYWORD", None))
    if len({argument.arg for argument, _kind, _default in rows}) != len(rows):
        return None
    return tuple(rows)


def _source_function_annotation_strings(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> dict[str, str] | None:
    """Stringify every postponed annotation in one source function declaration."""

    expected: dict[str, str] = {}
    parameter_nodes = _source_parameter_nodes(node)
    if parameter_nodes is None:
        return None
    for argument, _kind, _default in parameter_nodes:
        if argument.annotation is not None:
            expected[argument.arg] = ast.unparse(argument.annotation)
    if node.returns is not None:
        expected["return"] = ast.unparse(node.returns)
    return expected


def _source_function_annotations_match(
    function: types.FunctionType,
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> bool:
    """Require runtime annotation strings to match the exact source declaration."""

    expected = _source_function_annotation_strings(node)
    actual = function.__annotations__
    return bool(
        expected is not None
        and type(actual) is dict
        and set(actual) == set(expected)
        and all(
            type(actual[name]) is str and actual[name] == value for name, value in expected.items()
        )
    )


def _source_function_signature(
    function: types.FunctionType,
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    *,
    tree: ast.Module,
) -> _SourceDecoratorSignature | None:
    """Build a bounded signature from AST, defaults, and annotation source."""

    if not _source_future_annotations_enabled(tree):
        return None
    if not _source_function_defaults_match(function, node):
        return None
    if not _source_function_annotations_match(function, node):
        return None
    function_namespace = function.__dict__
    if type(function_namespace) is not dict or any(
        name in function_namespace
        for name in ("__signature__", "__wrapped__", "__text_signature__")
    ):
        return None
    parameter_nodes = _source_parameter_nodes(node)
    if parameter_nodes is None:
        return None
    parameters: list[_SourceDecoratorParameter] = []
    for argument, kind_name, default_node in parameter_nodes:
        if default_node is None:
            has_default = False
            default: object = None
        else:
            default = _source_literal(default_node)
            if default is _UNSUPPORTED_SOURCE_LITERAL:
                return None
            has_default = True
        annotation = ast.unparse(argument.annotation) if argument.annotation is not None else None
        parameters.append(
            _SourceDecoratorParameter(
                name=argument.arg,
                kind_name=kind_name,
                has_default=has_default,
                default=default,
                has_annotation=argument.annotation is not None,
                annotation=annotation,
            )
        )
    return_annotation = ast.unparse(node.returns) if node.returns is not None else None
    return _SourceDecoratorSignature(
        parameters=tuple(parameters),
        has_return_annotation=node.returns is not None,
        return_annotation=return_annotation,
    )


def _source_annotation_members(
    node: ast.expr,
    *,
    tree: ast.Module,
    module: object,
    module_name: str,
) -> tuple[object, ...] | None:
    """Resolve only names and ``|`` unions whose bindings are source imports."""

    if isinstance(node, ast.Name):
        value = _source_import_binding(
            node.id,
            tree=tree,
            module=module,
            module_name=module_name,
        )
        return (value,) if isinstance(value, type) else None
    if isinstance(node, ast.Constant) and node.value is None:
        return (type(None),)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        left = _source_annotation_members(
            node.left, tree=tree, module=module, module_name=module_name
        )
        right = _source_annotation_members(
            node.right, tree=tree, module=module, module_name=module_name
        )
        if left is None or right is None:
            return None
        result = list(left)
        for value in right:
            if not any(value is existing for existing in result):
                result.append(value)
        return tuple(result)
    return None


def _source_imported_names(tree: ast.Module) -> frozenset[str]:
    """Return direct module import bindings without inferring runtime names."""

    names: set[str] = set()
    for statement in tree.body:
        if isinstance(statement, ast.ImportFrom):
            names.update(
                alias.asname or alias.name for alias in statement.names if alias.name != "*"
            )
        elif isinstance(statement, ast.Import):
            names.update(alias.asname or alias.name.split(".", 1)[0] for alias in statement.names)
    return frozenset(names)


def _source_reference_annotation_identity(
    *,
    tree: ast.Module,
    module: object,
    module_name: str,
    source_path: Path,
    loader_code_hashes: Mapping[str, tuple[str, ...]],
) -> object:
    """Find the source helper's direct reference type guard and validate its function."""

    helper_node = next(
        (
            statement
            for statement in tree.body
            if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef))
            and statement.name == "_selector_annotation_accepts_full_reference"
        ),
        None,
    )
    namespace = getattr(module, "__dict__", None)
    helper = (
        namespace.get("_selector_annotation_accepts_full_reference")
        if type(namespace) is dict
        else None
    )
    if not isinstance(helper_node, ast.FunctionDef) or not isinstance(helper, types.FunctionType):
        return _SOURCE_DERIVATION_FAILED
    imported_names = _source_imported_names(tree)
    for expression in ast.walk(helper_node):
        if (
            isinstance(expression, ast.Name)
            and isinstance(expression.ctx, ast.Load)
            and expression.id in imported_names
            and _source_import_binding(
                expression.id, tree=tree, module=module, module_name=module_name
            )
            is _SOURCE_DERIVATION_FAILED
        ):
            return _SOURCE_DERIVATION_FAILED
    if not (
        helper.__globals__ is namespace
        and helper.__qualname__ == helper_node.name
        and Path(helper.__code__.co_filename).resolve() == source_path
        and _content_hash(_normalize_code_object(helper.__code__))
        in loader_code_hashes.get(helper.__qualname__, ())
        and _source_function_defaults_match(helper, helper_node)
    ):
        return _SOURCE_DERIVATION_FAILED

    guarded_names: list[str] = []
    for statement in helper_node.body:
        if not isinstance(statement, ast.If) or not isinstance(statement.test, ast.Compare):
            continue
        test = statement.test
        if not (
            isinstance(test.left, ast.Name)
            and test.left.id == "annotation"
            and len(test.ops) == 1
            and isinstance(test.ops[0], ast.Is)
            and len(test.comparators) == 1
            and isinstance(test.comparators[0], ast.Name)
            and any(
                isinstance(child, ast.Return)
                and isinstance(child.value, ast.Constant)
                and child.value.value is True
                for child in statement.body
            )
        ):
            continue
        guarded_names.append(test.comparators[0].id)
    if len(guarded_names) != 1:
        return _SOURCE_DERIVATION_FAILED
    value = _source_import_binding(
        guarded_names[0], tree=tree, module=module, module_name=module_name
    )
    return value if isinstance(value, type) else _SOURCE_DERIVATION_FAILED


def _source_signature_value_matches(
    actual: object,
    expected: _SourceDecoratorSignature,
) -> bool:
    """Compare inspect values structurally to the independently derived signature."""

    if type(actual) is not _inspect.Signature:
        return False
    actual_parameters = actual.parameters
    if not isinstance(actual_parameters, Mapping):
        return False
    if tuple(actual_parameters) != tuple(parameter.name for parameter in expected.parameters):
        return False
    for parameter in expected.parameters:
        if not _source_parameter_value_matches(actual_parameters.get(parameter.name), parameter):
            return False
    if expected.has_return_annotation:
        return (
            type(actual.return_annotation) is str
            and actual.return_annotation == expected.return_annotation
        )
    return actual.return_annotation is _inspect.Signature.empty


def _source_parameter_value_matches(
    actual: object,
    expected: _SourceDecoratorParameter,
) -> bool:
    """Compare one inspect parameter's kind, default, and annotation to source."""

    if type(actual) is not _inspect.Parameter:
        return False
    expected_kind = getattr(_inspect.Parameter, expected.kind_name, None)
    if actual.kind is not expected_kind:
        return False
    if expected.has_default:
        if not _exact_literal_equal(actual.default, expected.default):
            return False
    elif actual.default is not _inspect.Parameter.empty:
        return False
    if expected.has_annotation:
        if type(actual.annotation) is not str or actual.annotation != expected.annotation:
            return False
    elif actual.annotation is not _inspect.Parameter.empty:
        return False
    return actual.name == expected.name


def _source_parameter_default_value(
    parameter: _SourceDecoratorParameter,
) -> object:
    """Expose the default in the same shape as ``inspect.Parameter.default``."""

    return parameter.default if parameter.has_default else _inspect.Parameter.empty


def _source_eval_decorator_expression(
    node: ast.expr,
    environment: Mapping[str, object],
    *,
    terminal: types.FunctionType,
    terminal_node: ast.FunctionDef | ast.AsyncFunctionDef,
    source_tree: ast.Module,
    module: object,
    module_name: str,
    source_path: Path,
    loader_code_hashes: Mapping[str, tuple[str, ...]],
) -> object:
    """Evaluate the small, side-effect-free expression subset used by the factory."""

    if isinstance(node, ast.Constant) and type(node.value) in {
        str,
        int,
        bool,
        float,
        bytes,
        type(None),
    }:
        return node.value
    if isinstance(node, ast.Name):
        return environment.get(node.id, _SOURCE_DERIVATION_FAILED)
    if isinstance(node, ast.Attribute):
        receiver = _source_eval_decorator_expression(
            node.value,
            environment,
            terminal=terminal,
            terminal_node=terminal_node,
            source_tree=source_tree,
            module=module,
            module_name=module_name,
            source_path=source_path,
            loader_code_hashes=loader_code_hashes,
        )
        if isinstance(receiver, _SourceDecoratorSignature) and node.attr == "parameters":
            return _SourceDecoratorParameterMap(receiver.parameters)
        if isinstance(receiver, _SourceDecoratorParameterMap) and node.attr == "values":
            return _SourceBoundOperation("values", receiver)
        if isinstance(receiver, _SourceDecoratorParameter):
            if node.attr == "name":
                return receiver.name
            if node.attr == "default":
                return _source_parameter_default_value(receiver)
        if isinstance(receiver, _SourceResolvedAnnotationMap) and node.attr == "get":
            return _SourceBoundOperation("get", receiver)
        return _SOURCE_DERIVATION_FAILED
    if isinstance(node, ast.Call):
        if node.keywords:
            return _SOURCE_DERIVATION_FAILED
        if isinstance(node.func, ast.Name):
            name = node.func.id
            if name == "signature" and len(node.args) == 1:
                if (
                    _source_import_binding(
                        name, tree=source_tree, module=module, module_name=module_name
                    )
                    is _SOURCE_DERIVATION_FAILED
                ):
                    return _SOURCE_DERIVATION_FAILED
                argument = _source_eval_decorator_expression(
                    node.args[0],
                    environment,
                    terminal=terminal,
                    terminal_node=terminal_node,
                    source_tree=source_tree,
                    module=module,
                    module_name=module_name,
                    source_path=source_path,
                    loader_code_hashes=loader_code_hashes,
                )
                if argument is not terminal:
                    return _SOURCE_DERIVATION_FAILED
                return (
                    _source_function_signature(terminal, terminal_node, tree=source_tree)
                    or _SOURCE_DERIVATION_FAILED
                )
            if name == "get_type_hints" and len(node.args) == 1:
                if (
                    _source_import_binding(
                        name, tree=source_tree, module=module, module_name=module_name
                    )
                    is _SOURCE_DERIVATION_FAILED
                ):
                    return _SOURCE_DERIVATION_FAILED
                argument = _source_eval_decorator_expression(
                    node.args[0],
                    environment,
                    terminal=terminal,
                    terminal_node=terminal_node,
                    source_tree=source_tree,
                    module=module,
                    module_name=module_name,
                    source_path=source_path,
                    loader_code_hashes=loader_code_hashes,
                )
                if argument is not terminal:
                    return _SOURCE_DERIVATION_FAILED
                parameter_nodes = _source_parameter_nodes(terminal_node)
                if parameter_nodes is None or len(parameter_nodes) < 2:
                    return _SOURCE_DERIVATION_FAILED
                selector_node = parameter_nodes[1][0]
                selector_name = selector_node.arg
                if selector_node.annotation is None:
                    return _SourceResolvedAnnotationMap(selector_name, None)
                members = _source_annotation_members(
                    selector_node.annotation,
                    tree=source_tree,
                    module=module,
                    module_name=module_name,
                )
                if members is None:
                    return _SOURCE_DERIVATION_FAILED
                return _SourceResolvedAnnotationMap(
                    selector_name, _SourceResolvedAnnotation(members)
                )
            if name == "_selector_annotation_accepts_full_reference" and len(node.args) == 1:
                helper_identity = _source_reference_annotation_identity(
                    tree=source_tree,
                    module=module,
                    module_name=module_name,
                    source_path=source_path,
                    loader_code_hashes=loader_code_hashes,
                )
                if helper_identity is _SOURCE_DERIVATION_FAILED:
                    return _SOURCE_DERIVATION_FAILED
                argument = _source_eval_decorator_expression(
                    node.args[0],
                    environment,
                    terminal=terminal,
                    terminal_node=terminal_node,
                    source_tree=source_tree,
                    module=module,
                    module_name=module_name,
                    source_path=source_path,
                    loader_code_hashes=loader_code_hashes,
                )
                if argument is None:
                    return False
                if not isinstance(argument, _SourceResolvedAnnotation):
                    return _SOURCE_DERIVATION_FAILED
                return any(member is helper_identity for member in argument.members)
            if name == "tuple" and len(node.args) == 1:
                argument = _source_eval_decorator_expression(
                    node.args[0],
                    environment,
                    terminal=terminal,
                    terminal_node=terminal_node,
                    source_tree=source_tree,
                    module=module,
                    module_name=module_name,
                    source_path=source_path,
                    loader_code_hashes=loader_code_hashes,
                )
                if isinstance(argument, tuple):
                    return argument
                return _SOURCE_DERIVATION_FAILED
            if name == "len" and len(node.args) == 1:
                argument = _source_eval_decorator_expression(
                    node.args[0],
                    environment,
                    terminal=terminal,
                    terminal_node=terminal_node,
                    source_tree=source_tree,
                    module=module,
                    module_name=module_name,
                    source_path=source_path,
                    loader_code_hashes=loader_code_hashes,
                )
                if isinstance(argument, (tuple, _SourceDecoratorParameterMap)):
                    return len(argument if isinstance(argument, tuple) else argument.parameters)
                return _SOURCE_DERIVATION_FAILED
            return _SOURCE_DERIVATION_FAILED
        if isinstance(node.func, ast.Attribute):
            operation = _source_eval_decorator_expression(
                node.func,
                environment,
                terminal=terminal,
                terminal_node=terminal_node,
                source_tree=source_tree,
                module=module,
                module_name=module_name,
                source_path=source_path,
                loader_code_hashes=loader_code_hashes,
            )
            if not isinstance(operation, _SourceBoundOperation):
                return _SOURCE_DERIVATION_FAILED
            if (
                operation.name == "values"
                and not node.args
                and isinstance(operation.receiver, _SourceDecoratorParameterMap)
            ):
                return operation.receiver.parameters
            if operation.name == "get" and len(node.args) == 1:
                key = _source_eval_decorator_expression(
                    node.args[0],
                    environment,
                    terminal=terminal,
                    terminal_node=terminal_node,
                    source_tree=source_tree,
                    module=module,
                    module_name=module_name,
                    source_path=source_path,
                    loader_code_hashes=loader_code_hashes,
                )
                if (
                    isinstance(operation.receiver, _SourceResolvedAnnotationMap)
                    and key == operation.receiver.selector_name
                ):
                    return operation.receiver.selector_annotation
            return _SOURCE_DERIVATION_FAILED
        return _SOURCE_DERIVATION_FAILED
    if isinstance(node, ast.Subscript):
        receiver = _source_eval_decorator_expression(
            node.value,
            environment,
            terminal=terminal,
            terminal_node=terminal_node,
            source_tree=source_tree,
            module=module,
            module_name=module_name,
            source_path=source_path,
            loader_code_hashes=loader_code_hashes,
        )
        index = _source_eval_decorator_expression(
            node.slice,
            environment,
            terminal=terminal,
            terminal_node=terminal_node,
            source_tree=source_tree,
            module=module,
            module_name=module_name,
            source_path=source_path,
            loader_code_hashes=loader_code_hashes,
        )
        if (
            isinstance(receiver, tuple)
            and type(index) is int
            and -len(receiver) <= index < len(receiver)
        ):
            return receiver[index]
        return _SOURCE_DERIVATION_FAILED
    if isinstance(node, ast.IfExp):
        condition = _source_eval_decorator_expression(
            node.test,
            environment,
            terminal=terminal,
            terminal_node=terminal_node,
            source_tree=source_tree,
            module=module,
            module_name=module_name,
            source_path=source_path,
            loader_code_hashes=loader_code_hashes,
        )
        if type(condition) is not bool:
            return _SOURCE_DERIVATION_FAILED
        return _source_eval_decorator_expression(
            node.body if condition else node.orelse,
            environment,
            terminal=terminal,
            terminal_node=terminal_node,
            source_tree=source_tree,
            module=module,
            module_name=module_name,
            source_path=source_path,
            loader_code_hashes=loader_code_hashes,
        )
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = _source_eval_decorator_expression(
            node.left,
            environment,
            terminal=terminal,
            terminal_node=terminal_node,
            source_tree=source_tree,
            module=module,
            module_name=module_name,
            source_path=source_path,
            loader_code_hashes=loader_code_hashes,
        )
        right = _source_eval_decorator_expression(
            node.right,
            environment,
            terminal=terminal,
            terminal_node=terminal_node,
            source_tree=source_tree,
            module=module,
            module_name=module_name,
            source_path=source_path,
            loader_code_hashes=loader_code_hashes,
        )
        if type(left) is int and type(right) is int:
            return left + right
        return _SOURCE_DERIVATION_FAILED
    if isinstance(node, ast.BoolOp) and node.values:
        if isinstance(node.op, ast.And):
            for child in node.values:
                value = _source_eval_decorator_expression(
                    child,
                    environment,
                    terminal=terminal,
                    terminal_node=terminal_node,
                    source_tree=source_tree,
                    module=module,
                    module_name=module_name,
                    source_path=source_path,
                    loader_code_hashes=loader_code_hashes,
                )
                truth = _source_decorator_truth(value)
                if truth is _SOURCE_DERIVATION_FAILED:
                    return _SOURCE_DERIVATION_FAILED
                if not truth:
                    return value
            return value
        if isinstance(node.op, ast.Or):
            for child in node.values:
                value = _source_eval_decorator_expression(
                    child,
                    environment,
                    terminal=terminal,
                    terminal_node=terminal_node,
                    source_tree=source_tree,
                    module=module,
                    module_name=module_name,
                    source_path=source_path,
                    loader_code_hashes=loader_code_hashes,
                )
                truth = _source_decorator_truth(value)
                if truth is _SOURCE_DERIVATION_FAILED:
                    return _SOURCE_DERIVATION_FAILED
                if truth:
                    return value
            return value
        return _SOURCE_DERIVATION_FAILED
    if isinstance(node, ast.Compare) and len(node.ops) == 1 and len(node.comparators) == 1:
        left = _source_eval_decorator_expression(
            node.left,
            environment,
            terminal=terminal,
            terminal_node=terminal_node,
            source_tree=source_tree,
            module=module,
            module_name=module_name,
            source_path=source_path,
            loader_code_hashes=loader_code_hashes,
        )
        right = _source_eval_decorator_expression(
            node.comparators[0],
            environment,
            terminal=terminal,
            terminal_node=terminal_node,
            source_tree=source_tree,
            module=module,
            module_name=module_name,
            source_path=source_path,
            loader_code_hashes=loader_code_hashes,
        )
        operator = node.ops[0]
        if isinstance(operator, ast.Is):
            return left is right
        if isinstance(operator, ast.IsNot):
            return left is not right
        if isinstance(operator, ast.GtE) and type(left) is int and type(right) is int:
            return left >= right
        if isinstance(operator, ast.Lt) and type(left) is int and type(right) is int:
            return left < right
        return _SOURCE_DERIVATION_FAILED
    return _SOURCE_DERIVATION_FAILED


def _source_execute_decorator_statement(
    statement: ast.stmt,
    environment: dict[str, object],
    *,
    terminal: types.FunctionType,
    terminal_node: ast.FunctionDef | ast.AsyncFunctionDef,
    source_tree: ast.Module,
    module: object,
    module_name: str,
    source_path: Path,
    loader_code_hashes: Mapping[str, tuple[str, ...]],
) -> bool:
    """Execute one assignment/control node in the bounded decorator evaluator."""

    if isinstance(statement, ast.Assign):
        if len(statement.targets) != 1 or not isinstance(statement.targets[0], ast.Name):
            return False
        value = _source_eval_decorator_expression(
            statement.value,
            environment,
            terminal=terminal,
            terminal_node=terminal_node,
            source_tree=source_tree,
            module=module,
            module_name=module_name,
            source_path=source_path,
            loader_code_hashes=loader_code_hashes,
        )
        if value is _SOURCE_DERIVATION_FAILED:
            return False
        environment[statement.targets[0].id] = value
        return True
    if isinstance(statement, ast.AnnAssign):
        if statement.value is None or not isinstance(statement.target, ast.Name):
            return False
        value = _source_eval_decorator_expression(
            statement.value,
            environment,
            terminal=terminal,
            terminal_node=terminal_node,
            source_tree=source_tree,
            module=module,
            module_name=module_name,
            source_path=source_path,
            loader_code_hashes=loader_code_hashes,
        )
        if value is _SOURCE_DERIVATION_FAILED:
            return False
        environment[statement.target.id] = value
        return True
    if isinstance(statement, ast.If):
        condition = _source_eval_decorator_expression(
            statement.test,
            environment,
            terminal=terminal,
            terminal_node=terminal_node,
            source_tree=source_tree,
            module=module,
            module_name=module_name,
            source_path=source_path,
            loader_code_hashes=loader_code_hashes,
        )
        if type(condition) is not bool:
            return False
        selected = statement.body if condition else statement.orelse
        for child in selected:
            if isinstance(child, ast.Raise) or not _source_execute_decorator_statement(
                child,
                environment,
                terminal=terminal,
                terminal_node=terminal_node,
                source_tree=source_tree,
                module=module,
                module_name=module_name,
                source_path=source_path,
                loader_code_hashes=loader_code_hashes,
            ):
                return False
        return True
    if isinstance(statement, ast.Try):
        if statement.orelse or statement.finalbody:
            return False
        for child in statement.body:
            if not _source_execute_decorator_statement(
                child,
                environment,
                terminal=terminal,
                terminal_node=terminal_node,
                source_tree=source_tree,
                module=module,
                module_name=module_name,
                source_path=source_path,
                loader_code_hashes=loader_code_hashes,
            ):
                return False
        return True
    return False


def _source_derived_decorator_environment(
    factory_node: ast.FunctionDef | ast.AsyncFunctionDef,
    decorator_node: ast.expr,
    wrapper_path: tuple[str, ...],
    terminal: types.FunctionType,
    terminal_node: ast.FunctionDef | ast.AsyncFunctionDef,
    *,
    source_tree: ast.Module,
    module: object,
    module_name: str,
    source_path: Path,
    loader_code_hashes: Mapping[str, tuple[str, ...]],
) -> dict[str, object] | None:
    """Derive each closure cell by interpreting supported source AST only."""

    if len(wrapper_path) < 2:
        return None
    captures = _source_decorator_factory_captures(factory_node, decorator_node, terminal=terminal)
    if captures is None:
        return None
    parent: ast.FunctionDef | ast.AsyncFunctionDef = factory_node
    for nested_name in wrapper_path[:-1]:
        nested = [
            child
            for child in parent.body
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
            and child.name == nested_name
        ]
        if len(nested) != 1:
            return None
        parent = nested[0]
    wrapper = [
        child
        for child in parent.body
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
        and child.name == wrapper_path[-1]
    ]
    positional_parameters = [*parent.args.posonlyargs, *parent.args.args]
    if (
        len(wrapper) != 1
        or len(positional_parameters) != 1
        or parent.args.vararg is not None
        or parent.args.kwarg is not None
        or parent.args.kwonlyargs
        or parent.args.defaults
        or positional_parameters[0].arg in captures
    ):
        return None
    environment = dict(captures)
    environment[positional_parameters[0].arg] = terminal
    reached_wrapper = False
    for statement in parent.body:
        if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if statement is wrapper[0]:
                reached_wrapper = True
                break
            return None
        if not _source_execute_decorator_statement(
            statement,
            environment,
            terminal=terminal,
            terminal_node=terminal_node,
            source_tree=source_tree,
            module=module,
            module_name=module_name,
            source_path=source_path,
            loader_code_hashes=loader_code_hashes,
        ):
            return None
    return environment if reached_wrapper else None


def _source_capture_value_matches(
    actual: object,
    expected: object,
    *,
    terminal: types.FunctionType,
) -> bool:
    """Compare a runtime cell against its source-derived value without replay."""

    if expected is terminal:
        return actual is terminal
    if isinstance(expected, _SourceDecoratorSignature):
        return _source_signature_value_matches(actual, expected)
    if isinstance(expected, _SourceDecoratorParameter):
        return _source_parameter_value_matches(actual, expected)
    return _exact_literal_equal(actual, expected)


def _source_local_decorator_names(
    slot: _LoaderOwnedCallableSlot,
    module: object,
    module_name: str,
) -> tuple[str, ...]:
    """Find local function decorators whose wrapper must be source-reconciled."""

    namespace = getattr(module, "__dict__", {})
    if not isinstance(namespace, Mapping):
        return ()
    names: list[str] = []
    for decorator in slot.decorators:
        name = decorator[:-2] if decorator.endswith("()") else decorator
        factory = namespace.get(name)
        if isinstance(factory, types.FunctionType) and factory.__module__ == module_name:
            names.append(name)
    return tuple(names)


def _local_decorator_wrapper_matches(
    function: types.FunctionType,
    *,
    terminal: types.FunctionType,
    chain: tuple[types.FunctionType, ...],
    slot: _LoaderOwnedCallableSlot,
    module: object,
    module_name: str,
    source_path: Path,
    loader_code_hashes: Mapping[str, tuple[str, ...]],
) -> bool:
    """Authenticate a local decorator wrapper by its source path and closure."""

    if slot.descriptor_kind != "function" or len(chain) != 2:
        return False
    local_names = _source_local_decorator_names(slot, module, module_name)
    if len(local_names) != 1 or getattr(function, "__wrapped__", None) is not terminal:
        return False
    factory_name = local_names[0]
    namespace = getattr(module, "__dict__", {})
    factory = namespace.get(factory_name) if isinstance(namespace, Mapping) else None
    if not isinstance(factory, types.FunctionType):
        return False
    if not (
        factory.__module__ == module_name
        and factory.__globals__ is namespace
        and factory.__qualname__ == factory_name
        and Path(factory.__code__.co_filename).resolve() == source_path
        and _content_hash(_normalize_code_object(factory.__code__))
        in loader_code_hashes.get(factory.__qualname__, ())
    ):
        return False
    try:
        tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    except (OSError, SyntaxError, UnicodeError):
        return False
    factory_node = next(
        (
            statement
            for statement in tree.body
            if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef))
            and statement.name == factory_name
        ),
        None,
    )
    slot_node = _source_slot_function_node(tree, slot)
    if factory_node is None or slot_node is None or len(slot_node.decorator_list) != 1:
        return False
    decorator_node = slot_node.decorator_list[0]
    decorator_target = (
        decorator_node.func if isinstance(decorator_node, ast.Call) else decorator_node
    )
    if not isinstance(decorator_target, ast.Name) or decorator_target.id != factory_name:
        return False
    wrapper_path = _returned_local_wrapper_path(factory_node)
    if wrapper_path is None:
        return False
    expected_wrapper_qualname = factory_name + ".<locals>." + ".<locals>.".join(wrapper_path)
    if not (
        function.__module__ == module_name
        and function.__globals__ is namespace
        and function.__qualname__ == slot.qualname
        and function.__code__.co_qualname == expected_wrapper_qualname
        and Path(function.__code__.co_filename).resolve() == source_path
        and _content_hash(_normalize_code_object(function.__code__))
        in loader_code_hashes.get(expected_wrapper_qualname, ())
    ):
        return False

    wrapper_node = factory_node
    for nested_name in wrapper_path:
        wrapper_node = next(
            (
                child
                for child in wrapper_node.body
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
                and child.name == nested_name
            ),
            None,
        )
        if wrapper_node is None:
            return False
    if not _source_function_defaults_match(function, wrapper_node):
        return False
    if not _source_function_defaults_match(factory, factory_node):
        return False
    if not _source_function_defaults_match(terminal, slot_node):
        return False
    if not _source_function_annotations_match(terminal, slot_node):
        return False
    expected_environment = _source_derived_decorator_environment(
        factory_node,
        decorator_node,
        wrapper_path,
        terminal,
        slot_node,
        source_tree=tree,
        module=module,
        module_name=module_name,
        source_path=source_path,
        loader_code_hashes=loader_code_hashes,
    )
    if expected_environment is None:
        return False

    closure = function.__closure__ or ()
    if len(closure) != len(function.__code__.co_freevars):
        return False
    target_bindings = 0
    for name, cell in zip(function.__code__.co_freevars, closure, strict=True):
        try:
            value = cell.cell_contents
        except ValueError:
            return False
        expected = expected_environment.get(name, _SOURCE_DERIVATION_FAILED)
        if expected is _SOURCE_DERIVATION_FAILED:
            return False
        if value is terminal:
            target_bindings += 1
        if not _source_capture_value_matches(value, expected, terminal=terminal):
            return False
    return target_bindings == 1


def _loader_owned_slot_function_matches(
    function: types.FunctionType,
    *,
    slot: _LoaderOwnedCallableSlot,
    module_name: str,
    source_path: Path,
    expected_hashes: tuple[str, ...],
    expected_firstlinenos: tuple[int, ...],
    module: object,
    loader_code_hashes: Mapping[str, tuple[str, ...]],
) -> tuple[dict[str, object], bool]:
    """Reconcile one live function or declared wrapper to its loader slot."""

    terminal, chain = _unwrapped_function_chain(function)
    terminal_hash = _content_hash(_normalize_code_object(terminal.__code__))
    terminal_matches = bool(
        expected_hashes
        and terminal.__code__.co_firstlineno in expected_firstlinenos
        and terminal.__module__ == module_name
        and terminal.__globals__ is getattr(module, "__dict__", None)
        and terminal.__qualname__ == slot.qualname
        and Path(terminal.__code__.co_filename).resolve() == source_path
        and terminal_hash in expected_hashes
    )
    expects_contextmanager = any(
        decorator == "contextmanager" or decorator.endswith(".contextmanager")
        for decorator in slot.decorators
    )
    local_decorator_names = _source_local_decorator_names(slot, module, module_name)
    wrapper_matches = len(chain) == 1 and not expects_contextmanager and not local_decorator_names
    if len(chain) > 1 and expects_contextmanager:
        expected_wrapper = contextmanager(terminal)
        wrapper_matches = _content_hash(_normalize_function_binding(function)) == _content_hash(
            _normalize_function_binding(expected_wrapper)
        )
    elif len(chain) > 1 and local_decorator_names:
        wrapper_matches = _local_decorator_wrapper_matches(
            function,
            terminal=terminal,
            chain=chain,
            slot=slot,
            module=module,
            module_name=module_name,
            source_path=source_path,
            loader_code_hashes=loader_code_hashes,
        )
    return (
        {
            "chain_normalized_code_hashes": [
                _content_hash(_normalize_code_object(item.__code__)) for item in chain
            ],
            "terminal_declared_module": terminal.__module__,
            "terminal_firstlineno": terminal.__code__.co_firstlineno,
            "terminal_qualname": terminal.__qualname__,
            "terminal_source": Path(terminal.__code__.co_filename).resolve().as_posix(),
            "expected_firstlinenos": list(expected_firstlinenos),
            "wrapper_matches_declared_decorator": wrapper_matches,
        },
        terminal_matches and wrapper_matches,
    )


def _loader_owned_slot_binding(
    module: object,
    module_name: str,
    source_path: Path,
    slot: _LoaderOwnedCallableSlot,
    expected_hashes: tuple[str, ...],
    loader_code_hashes: Mapping[str, tuple[str, ...]],
) -> tuple[dict[str, object], bool]:
    """Resolve and reconcile one exact source-declared callable binding."""

    owner = _loader_owned_slot_owner(module, module_name, slot.owner_path)
    namespace = getattr(owner, "__dict__", {}) if owner is not None else {}
    raw = namespace.get(slot.binding_name) if isinstance(namespace, Mapping) else None
    functions: list[tuple[str, types.FunctionType]] = []
    source_firstlinenos = dict(slot.source_firstlinenos)
    expected_cache_policies = {
        role: {"maxsize": maxsize, "typed": typed}
        for role, _firstlineno, maxsize, typed in slot.lru_cache_parameters
    }
    cache_policy_rows: list[dict[str, object]] = []
    wrapper_shape_matches = True

    def append_function(role: str, value: object) -> None:
        nonlocal wrapper_shape_matches
        expected_policy = expected_cache_policies.get(role)
        if isinstance(value, _LRU_CACHE_WRAPPER_TYPE):
            actual_policy = value.cache_parameters()
            cache_policy_matches = bool(
                expected_policy is not None
                and type(actual_policy) is dict
                and set(actual_policy) == {"maxsize", "typed"}
                and (
                    actual_policy["maxsize"] is None
                    or (type(actual_policy["maxsize"]) is int and actual_policy["maxsize"] >= 0)
                )
                and type(actual_policy["typed"]) is bool
                and actual_policy == expected_policy
            )
            cache_policy_rows.append(
                {
                    "role": role,
                    "actual": actual_policy,
                    "expected": expected_policy,
                    "matches_declared_policy": cache_policy_matches,
                }
            )
            wrapped = getattr(value, "__wrapped__", None)
            if cache_policy_matches and isinstance(wrapped, types.FunctionType):
                functions.append((role, wrapped))
            else:
                wrapper_shape_matches = False
            return
        if expected_policy is not None:
            cache_policy_rows.append(
                {
                    "role": role,
                    "actual": None,
                    "expected": expected_policy,
                    "matches_declared_policy": False,
                }
            )
            wrapper_shape_matches = False
        if isinstance(value, types.FunctionType):
            functions.append((role, value))
        else:
            wrapper_shape_matches = False

    if isinstance(raw, property):
        descriptor_kind = "property"
    elif isinstance(raw, classmethod):
        descriptor_kind = "classmethod"
    elif isinstance(raw, staticmethod):
        descriptor_kind = "staticmethod"
    elif isinstance(raw, _LRU_CACHE_WRAPPER_TYPE):
        descriptor_kind = "lru_cache"
    elif isinstance(raw, types.FunctionType):
        descriptor_kind = "function"
    else:
        descriptor_kind = f"{type(raw).__module__}.{type(raw).__qualname__}"
    descriptor_kind_matches = descriptor_kind == slot.descriptor_kind
    if isinstance(raw, property):
        actual_accessors = tuple(
            accessor for accessor in ("fget", "fset", "fdel") if getattr(raw, accessor) is not None
        )
        wrapper_shape_matches = actual_accessors == slot.property_accessors
        for accessor in slot.property_accessors:
            append_function(accessor, getattr(raw, accessor))
    elif isinstance(raw, (classmethod, staticmethod)):
        append_function("function", raw.__func__)
    elif isinstance(raw, (_LRU_CACHE_WRAPPER_TYPE, types.FunctionType)):
        append_function("function", raw)
    else:
        wrapper_shape_matches = False
    function_rows: list[dict[str, object]] = []
    functions_match = bool(functions)
    for accessor, function in functions:
        expected_firstlinenos = (
            (source_firstlinenos[accessor],) if accessor in source_firstlinenos else ()
        )
        row, matches = _loader_owned_slot_function_matches(
            function,
            slot=slot,
            module_name=module_name,
            source_path=source_path,
            expected_hashes=expected_hashes,
            expected_firstlinenos=expected_firstlinenos,
            module=module,
            loader_code_hashes=loader_code_hashes,
        )
        function_rows.append({"accessor": accessor, **row, "matches_loader_slot": matches})
        functions_match = functions_match and matches
    matches_slot = bool(
        owner is not None and descriptor_kind_matches and wrapper_shape_matches and functions_match
    )
    return (
        {
            "binding_type": f"{type(raw).__module__}.{type(raw).__qualname__}",
            "cache_policies": cache_policy_rows,
            "decorators": list(slot.decorators),
            "descriptor_kind": descriptor_kind,
            "descriptor_kind_matches": descriptor_kind_matches,
            "expected_descriptor_kind": slot.descriptor_kind,
            "expected_property_accessors": list(slot.property_accessors),
            "expected_source_firstlinenos": [list(item) for item in slot.source_firstlinenos],
            "functions": function_rows,
            "loader_normalized_code_hashes": list(expected_hashes),
            "matches_loader_slot": matches_slot,
            "owner_path": list(slot.owner_path),
        },
        matches_slot,
    )


def _loaded_code_manifest(
    repo_root: Path,
    closure: tuple[tuple[str, str], ...],
) -> tuple[str, bool]:
    """Capture normalized code objects for the complete declared closure."""

    manifest: dict[str, object] = {}
    all_consistent = True
    for module_name, relative_path in closure:
        module = sys.modules.get(module_name)
        if module is None:
            raise ConfidenceLedgerError(
                "canonical_loaded_runtime_mismatch",
                f"authority closure module not loaded: {module_name}",
            )
        spec = getattr(module, "__spec__", None)
        loader = getattr(spec, "loader", None)
        get_code = getattr(loader, "get_code", None)
        origin = getattr(spec, "origin", None)
        if not callable(get_code) or not isinstance(origin, str):
            raise ConfidenceLedgerError(
                "canonical_loaded_runtime_mismatch",
                f"loaded repository module has no code provenance: {module_name}",
            )
        try:
            origin_relative = Path(origin).resolve().relative_to(repo_root).as_posix()
            code = get_code(module_name)
        except (ImportError, OSError, ValueError) as exc:
            raise ConfidenceLedgerError(
                "canonical_loaded_runtime_mismatch",
                f"loaded repository module provenance invalid: {module_name}",
            ) from exc
        if origin_relative != relative_path or not isinstance(code, types.CodeType):
            raise ConfidenceLedgerError(
                "canonical_loaded_runtime_mismatch",
                f"loaded repository module provenance invalid: {module_name}",
            )
        source_path = (repo_root / relative_path).resolve()
        live_defined_code = _live_defined_code_manifest(
            module,
            module_name,
            source_path=source_path,
        )
        loader_code_hashes = _loader_code_hashes_by_qualname(code)
        live_loader_bindings: dict[str, object] = {}
        module_consistent = True
        for label, live_code in live_defined_code.items():
            code_qualname = str(live_code["code_qualname"])
            live_hash = str(live_code["normalized_code_hash"])
            defined_locally = bool(live_code["defined_locally"])
            loader_hashes = loader_code_hashes.get(code_qualname, ()) if defined_locally else ()
            matches_loader = (
                live_hash in loader_hashes and bool(live_code["globals_match_module"])
                if defined_locally
                else None
            )
            if defined_locally:
                module_consistent = module_consistent and bool(matches_loader)
            live_loader_bindings[label] = {
                **live_code,
                "loader_normalized_code_hashes": list(loader_hashes),
                "matches_loader": matches_loader,
            }
        loader_owned_slots: dict[str, object] = {}
        for slot in _loader_owned_callable_slots(source_path):
            expected_hashes = loader_code_hashes.get(slot.qualname, ())
            row, matches_slot = _loader_owned_slot_binding(
                module,
                module_name,
                source_path,
                slot,
                expected_hashes,
                loader_code_hashes,
            )
            module_consistent = module_consistent and matches_slot
            loader_owned_slots[slot.qualname] = row
        for binding_label, binding in live_loader_bindings.items():
            if not binding["defined_locally"]:
                continue
            code_qualname = str(binding["code_qualname"])
            declared_qualname = str(binding["qualname"])
            if code_qualname == declared_qualname:
                continue
            slot_qualname = binding_label
            for accessor in (".fget", ".fset", ".fdel"):
                if slot_qualname.endswith(accessor):
                    slot_qualname = slot_qualname.removesuffix(accessor)
                    break
            slot_row = loader_owned_slots.get(slot_qualname)
            slot_proves_wrapper = (
                type(slot_row) is dict and slot_row.get("matches_loader_slot") is True
            )
            binding_matches = bool(
                binding["matches_loader"]
                and declared_qualname == slot_qualname
                and slot_proves_wrapper
            )
            binding["matches_loader"] = binding_matches
            module_consistent = module_consistent and binding_matches
        all_consistent = all_consistent and module_consistent
        try:
            source_hash = _bytes_hash((repo_root / relative_path).read_bytes())
        except OSError as exc:
            raise ConfidenceLedgerError(
                "canonical_loaded_runtime_mismatch",
                f"loaded repository source unavailable: {module_name}",
            ) from exc
        manifest[module_name] = {
            "relative_path": relative_path,
            "source_hash": source_hash,
            "loader_module_code_hash": _content_hash(_normalize_code_object(code)),
            "live_defined_code": live_loader_bindings,
            "loader_owned_callable_slots": loader_owned_slots,
            "live_loader_consistent": module_consistent,
        }
    return _canonical_json(manifest), all_consistent


def _loaded_code_evidence_projection(manifest: str) -> str:
    """Remove process-late non-local exports from stable runtime evidence."""

    try:
        payload = json.loads(manifest)
    except (json.JSONDecodeError, TypeError) as exc:
        raise ConfidenceLedgerError("canonical_loaded_runtime_mismatch") from exc
    if type(payload) is not dict:
        raise ConfidenceLedgerError("canonical_loaded_runtime_mismatch")
    projection: dict[str, object] = {}
    for module_name, module_row in payload.items():
        if not (isinstance(module_name, str) and type(module_row) is dict):
            raise ConfidenceLedgerError("canonical_loaded_runtime_mismatch")
        live_bindings = module_row.get("live_defined_code")
        if type(live_bindings) is not dict:
            raise ConfidenceLedgerError("canonical_loaded_runtime_mismatch")
        local_bindings: dict[str, object] = {}
        for label, binding in live_bindings.items():
            if not (
                isinstance(label, str)
                and type(binding) is dict
                and type(binding.get("defined_locally")) is bool
            ):
                raise ConfidenceLedgerError("canonical_loaded_runtime_mismatch")
            if binding["defined_locally"]:
                local_bindings[label] = binding
        projection[module_name] = {
            **module_row,
            "live_defined_code": local_bindings,
        }
    return _canonical_json(projection)


def _live_defined_code_manifest(
    module: object,
    module_name: str,
    *,
    source_path: Path,
) -> dict[str, dict[str, object]]:
    """Capture every live function bound into one authority module namespace."""

    found: dict[str, tuple[types.FunctionType, bool, bool]] = {}
    seen_classes: set[int] = set()
    module_namespace = getattr(module, "__dict__", {})
    if not isinstance(module_namespace, dict):
        raise ConfidenceLedgerError(
            "canonical_loaded_runtime_mismatch",
            f"loaded repository module namespace invalid: {module_name}",
        )

    def add_function(label: str, function: types.FunctionType) -> None:
        defined_locally = bool(
            function.__module__ == module_name
            and Path(function.__code__.co_filename).resolve() == source_path
        )
        found[label] = (
            function,
            defined_locally,
            function.__globals__ is module_namespace,
        )

    def walk_class(label: str, cls: type[object]) -> None:
        if id(cls) in seen_classes or cls.__module__ != module_name:
            return
        seen_classes.add(id(cls))
        for name, value in sorted(vars(cls).items()):
            member_label = f"{label}.{name}"
            if isinstance(value, types.FunctionType):
                add_function(member_label, value)
            elif isinstance(value, (classmethod, staticmethod)):
                add_function(member_label, value.__func__)
            elif isinstance(value, property):
                for accessor_name in ("fget", "fset", "fdel"):
                    accessor = getattr(value, accessor_name)
                    if isinstance(accessor, types.FunctionType):
                        add_function(f"{member_label}.{accessor_name}", accessor)
            elif isinstance(value, type):
                walk_class(member_label, value)

    namespace = module_namespace
    for name, value in sorted(namespace.items()):
        if isinstance(value, types.FunctionType):
            add_function(name, value)
        elif isinstance(value, type):
            walk_class(name, value)
    return {
        label: {
            "qualname": function.__qualname__,
            "code_qualname": function.__code__.co_qualname,
            "declared_module": function.__module__,
            "defined_locally": defined_locally,
            "globals_match_module": globals_match,
            "normalized_code_hash": _content_hash(_normalize_code_object(function.__code__)),
            "normalized_binding_hash": _content_hash(_normalize_function_binding(function)),
        }
        for label, (function, defined_locally, globals_match) in sorted(found.items())
    }


def _normalize_function_binding(
    function: types.FunctionType,
    *,
    seen: set[int] | None = None,
) -> dict[str, object]:
    """Bind executable code together with defaults and closed-over state."""

    active = set() if seen is None else set(seen)
    active.add(id(function))
    closure: list[object] = []
    for cell in function.__closure__ or ():
        try:
            value = cell.cell_contents
        except ValueError:
            closure.append({"empty_cell": True})
        else:
            closure.append(_normalize_runtime_binding_value(value, seen=active))
    return {
        "declared_module": function.__module__,
        "qualname": function.__qualname__,
        "code": _normalize_code_object(function.__code__),
        "defaults": _normalize_runtime_binding_value(
            function.__defaults__,
            seen=active,
        ),
        "kwdefaults": _normalize_runtime_binding_value(
            function.__kwdefaults__,
            seen=active,
        ),
        "closure": closure,
    }


def _normalize_runtime_binding_value(value: object, *, seen: set[int]) -> object:
    """Return a deterministic, path-safe representation of bound runtime state."""

    if isinstance(value, (str, int, bool)) or value is None:
        return value
    if isinstance(value, float):
        return {"float_hex": value.hex()}
    if isinstance(value, complex):
        return {"complex": [value.real.hex(), value.imag.hex()]}
    if isinstance(value, bytes):
        return {"bytes_hash": _bytes_hash(value)}
    if value is Ellipsis:
        return {"singleton": "ellipsis"}
    if isinstance(value, Fraction):
        return {"fraction": [value.numerator, value.denominator]}
    if isinstance(value, Path):
        rendered = value.as_posix()
        return {
            "path_kind": "absolute_hash" if value.is_absolute() else "relative",
            "value": _bytes_hash(rendered.encode()) if value.is_absolute() else rendered,
        }
    if isinstance(value, Enum):
        return {
            "enum_type": _runtime_type_ref(type(value)),
            "name": value.name,
            "value": _normalize_runtime_binding_value(value.value, seen=seen),
        }
    object_id = id(value)
    if object_id in seen:
        return {"cycle": _runtime_type_ref(type(value))}
    nested_seen = {*seen, object_id}
    if isinstance(value, tuple):
        return {
            "tuple": [_normalize_runtime_binding_value(item, seen=nested_seen) for item in value]
        }
    if isinstance(value, list):
        return {
            "list": [_normalize_runtime_binding_value(item, seen=nested_seen) for item in value]
        }
    if isinstance(value, (set, frozenset)):
        items = [_normalize_runtime_binding_value(item, seen=nested_seen) for item in value]
        return {
            "set" if isinstance(value, set) else "frozenset": sorted(
                items,
                key=_canonical_json,
            )
        }
    if isinstance(value, Mapping):
        items = [
            [
                _normalize_runtime_binding_value(key, seen=nested_seen),
                _normalize_runtime_binding_value(item, seen=nested_seen),
            ]
            for key, item in value.items()
        ]
        return {"mapping": sorted(items, key=_canonical_json)}
    if isinstance(value, types.FunctionType):
        return {
            "function": _normalize_function_binding(value, seen=nested_seen),
        }
    if isinstance(value, type):
        return {"type": _runtime_type_ref(value)}
    state = getattr(value, "__dict__", None)
    if isinstance(state, dict) and state:
        return {
            "object_type": _runtime_type_ref(type(value)),
            "state": _normalize_runtime_binding_value(state, seen=nested_seen),
        }
    return {"singleton_type": _runtime_type_ref(type(value))}


def _runtime_type_ref(value: type[object]) -> str:
    """Return a stable type name without a filesystem path or memory address."""

    return f"{value.__module__}.{value.__qualname__}"


def _loader_code_hashes_by_qualname(code: types.CodeType) -> dict[str, tuple[str, ...]]:
    """Index compiled source code by stable qualified name."""

    hashes: dict[str, set[str]] = {}

    def walk(current: types.CodeType) -> None:
        hashes.setdefault(current.co_qualname, set()).add(
            _content_hash(_normalize_code_object(current))
        )
        for constant in current.co_consts:
            if isinstance(constant, types.CodeType):
                walk(constant)

    walk(code)
    return {qualname: tuple(sorted(values)) for qualname, values in sorted(hashes.items())}


def _normalize_code_object(code: types.CodeType) -> dict[str, object]:
    """Normalize executable code while excluding machine-local filenames."""

    return {
        "argcount": code.co_argcount,
        "posonlyargcount": code.co_posonlyargcount,
        "kwonlyargcount": code.co_kwonlyargcount,
        "nlocals": code.co_nlocals,
        "stacksize": code.co_stacksize,
        "flags": code.co_flags,
        "code_hash": _bytes_hash(code.co_code),
        "consts": [_normalize_code_constant(value) for value in code.co_consts],
        "names": list(code.co_names),
        "varnames": list(code.co_varnames),
        "freevars": list(code.co_freevars),
        "cellvars": list(code.co_cellvars),
        "name": code.co_name,
        "qualname": code.co_qualname,
        "firstlineno": code.co_firstlineno,
        "linetable_hash": _bytes_hash(code.co_linetable),
        "exceptiontable_hash": _bytes_hash(code.co_exceptiontable),
    }


def _normalize_code_constant(value: object) -> object:
    """Return a canonical representation of a code-object constant."""

    if isinstance(value, types.CodeType):
        return {"code": _normalize_code_object(value)}
    if isinstance(value, bytes):
        return {"bytes_hash": _bytes_hash(value)}
    if isinstance(value, tuple):
        return {"tuple": [_normalize_code_constant(item) for item in value]}
    if isinstance(value, slice):
        return {
            "slice": [
                _normalize_code_constant(value.start),
                _normalize_code_constant(value.stop),
                _normalize_code_constant(value.step),
            ]
        }
    if isinstance(value, frozenset):
        items = [_normalize_code_constant(item) for item in value]
        return {"frozenset": sorted(items, key=_canonical_json)}
    if isinstance(value, float):
        return {"float_hex": value.hex()}
    if isinstance(value, complex):
        return {"complex": [value.real.hex(), value.imag.hex()]}
    if value is Ellipsis:
        return {"singleton": "ellipsis"}
    if isinstance(value, (str, int, bool)) or value is None:
        return value
    raise ConfidenceLedgerError(
        "canonical_loaded_runtime_mismatch",
        f"unsupported code constant: {type(value).__name__}",
    )


def _bytes_hash(value: bytes) -> str:
    return f"sha256:{hashlib.sha256(value).hexdigest()}"


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


def _confidence_scope_anchor_payload(
    risk_scope: ConfidenceRiskBudgetScope,
) -> dict[str, Any]:
    """Return the sole canonical scope-anchor payload."""

    return {
        "schema_version": CONFIDENCE_LEDGER_SCHEMA_VERSION,
        "scope_id": risk_scope.scope_id,
        "scope_owner_ref": risk_scope.scope_owner_ref,
        "authority_purpose": risk_scope.authority_purpose,
        "owner_scope_key": risk_scope.owner_scope_key,
        "epoch_ref": risk_scope.epoch_ref,
    }


def _content_hash(payload: object) -> str:
    return "sha256:" + hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _cas_json_artifact_ref(payload: object) -> str:
    data = canon.to_canonical_bytes(_jsonable(payload), _IMPORT_TIME_LEDGER_CANON_SPEC)
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
    "ConfidenceLedgerSemanticCheck",
    "ConfidenceLedgerSemanticEvent",
    "ConfidenceLedgerSemanticOwnerBinding",
    "ConfidenceLedgerSemanticReceiptProjection",
    "ConfidenceLedgerSession",
    "ConfidenceRiskBudgetScope",
    "LoadedDeploymentIdentityObservation",
    "N6DeploymentCurrentnessObservation",
    "N9PromotionCertificateProjection",
    "N9PromotionLedgerRow",
    "N9PromotionSemanticLedgerProjection",
    "N12EpochReferenceProjection",
    "OwnerCertificateBinding",
    "OwnerCertificateEvidence",
    "OwnerCertificateVerification",
    "PackagedDeploymentIdentityReadiness",
    "PredictableClaimSpec",
    "PromotionCertificateOffer",
    "RationalSpec",
    "capture_loaded_deployment_identity",
    "inspect_packaged_deployment_identity",
    "load_confidence_ledger_registry",
    "observe_n6_deployment_currentness",
    "project_confidence_ledger_semantic_receipt",
    "project_n9_promotion_certificate",
    "project_n9_promotion_semantic_ledger",
    "project_n12_epoch_reference",
    "recompute_confidence_owner_evidence_hash",
    "recompute_confidence_owner_projection_hash",
    "recompute_confidence_schedule_projection_hash",
    "recompute_confidence_scope_anchor_ref",
    "validate_confidence_ledger_receipt",
    "validate_confidence_ledger_receipt_structure",
]

(
    _IMPORT_TIME_LEDGER_CONTRACT_SOURCE_HASH,
    _IMPORT_TIME_LEDGER_CONTRACT_PROJECTION,
    _IMPORT_TIME_LEDGER_MODEL_PROJECTION,
    _IMPORT_TIME_LEDGER_CANON_PROJECTION,
) = _capture_import_ledger_contract_state()
_IMPORT_TIME_LEDGER_ARTIFACT_CONTRACTS: Mapping[str, _LedgerArtifactContract] = (
    _snapshot_ledger_contracts(_LEDGER_ARTIFACT_CONTRACTS)
)
_IMPORT_TIME_LEDGER_CANON_SPEC = _CAS_CANON_SPEC
_IMPORT_TIME_LEDGER_SNAPSHOT_PROJECTION = _runtime_ledger_snapshot_projection(
    _IMPORT_TIME_LEDGER_ARTIFACT_CONTRACTS
)


def _assert_ledger_artifact_contracts_current(
    source_path: Path = _LEDGER_MODULE_SOURCE_PATH,
    expected_source_hash: str = _IMPORT_TIME_LEDGER_CONTRACT_SOURCE_HASH,
    expected_contract_projection: str = _IMPORT_TIME_LEDGER_CONTRACT_PROJECTION,
    expected_model_projection: str = _IMPORT_TIME_LEDGER_MODEL_PROJECTION,
    expected_canon_projection: str = _IMPORT_TIME_LEDGER_CANON_PROJECTION,
    expected_contracts: Mapping[str, _LedgerArtifactContract] = (
        _IMPORT_TIME_LEDGER_ARTIFACT_CONTRACTS
    ),
    expected_snapshot_projection: str = _IMPORT_TIME_LEDGER_SNAPSHOT_PROJECTION,
    expected_canon_spec: canon.CanonSpec = _IMPORT_TIME_LEDGER_CANON_SPEC,
    loaded_code_manifest_fn: Callable[
        [Path, tuple[tuple[str, str], ...]], tuple[str, bool]
    ] = _loaded_code_manifest,
    loaded_code_evidence_projection_fn: Callable[[str], str] = _loaded_code_evidence_projection,
) -> None:
    """Fail closed when source, contracts, snapshots, or loaded code drift."""
    try:
        runtime = globals()
        expected_strings = {
            "_IMPORT_TIME_LEDGER_CONTRACT_SOURCE_HASH": expected_source_hash,
            "_IMPORT_TIME_LEDGER_CONTRACT_PROJECTION": expected_contract_projection,
            "_IMPORT_TIME_LEDGER_MODEL_PROJECTION": expected_model_projection,
            "_IMPORT_TIME_LEDGER_CANON_PROJECTION": expected_canon_projection,
            "_IMPORT_TIME_LEDGER_SNAPSHOT_PROJECTION": expected_snapshot_projection,
        }
        if any(runtime.get(name) != value for name, value in expected_strings.items()):
            raise ValueError("pinned ledger identity binding was rebound")
        if runtime.get("_IMPORT_TIME_LEDGER_ARTIFACT_CONTRACTS") is not expected_contracts:
            raise ValueError("pinned ledger contract snapshot was rebound")
        if runtime.get("_IMPORT_TIME_LEDGER_CANON_SPEC") is not expected_canon_spec:
            raise ValueError("pinned ledger canonical specification was rebound")
        source_hash = _bytes_hash(source_path.read_bytes())
        contract_projection = _runtime_ledger_contract_projection()
        model_projection = _ledger_model_projection(_LEDGER_ARTIFACT_CONTRACTS)
        snapshot_projection = _runtime_ledger_snapshot_projection(
            _IMPORT_TIME_LEDGER_ARTIFACT_CONTRACTS
        )
        canon_projection = _canonical_json(
            _normalize_runtime_binding_value(_CAS_CANON_SPEC, seen=set())
        )
        pinned_canon_projection = _canonical_json(
            _normalize_runtime_binding_value(_IMPORT_TIME_LEDGER_CANON_SPEC, seen=set())
        )
        if (
            source_hash != expected_source_hash
            or contract_projection != expected_contract_projection
            or model_projection != expected_model_projection
            or snapshot_projection != expected_snapshot_projection
            or canon_projection != expected_canon_projection
            or pinned_canon_projection != expected_canon_projection
        ):
            raise ValueError("runtime ledger contract differs from its import-time source")
        if _IMPORT_TIME_LOADED_CODE_MANIFEST:
            if _IMPORT_TIME_LOADED_CODE_CONSISTENT is not True:
                raise ValueError("loaded authority code was not consistent at import")
            loaded_code_manifest, loaded_code_consistent = loaded_code_manifest_fn(
                _IMPORT_TIME_OWNER_ROOT,
                _IMPORT_TIME_AUTHORITY_IMPORT_CLOSURE,
            )
            if not loaded_code_consistent or loaded_code_evidence_projection_fn(
                loaded_code_manifest
            ) != loaded_code_evidence_projection_fn(_IMPORT_TIME_LOADED_CODE_MANIFEST):
                raise ValueError("loaded authority code differs from its import-time identity")
        elif (
            _IMPORT_TIME_AUTHORITY_IMPORT_CLOSURE
            or _IMPORT_TIME_LOADED_CODE_CONSISTENT is not False
        ):
            raise ValueError("loaded authority identity snapshot is incomplete")
    except (OSError, TypeError, ValueError, AttributeError) as exc:
        if isinstance(exc, ConfidenceLedgerError):
            raise
        raise ConfidenceLedgerError("canonical_loaded_runtime_mismatch", str(exc)) from exc


_IMPORT_TIME_DEPLOYMENT_IDENTITY_REASON = "canonical_loaded_runtime_mismatch"
_IMPORT_TIME_OWNER_ROOT = _loaded_policy_engine_root()
if (
    (_IMPORT_TIME_OWNER_ROOT / "pyproject.toml").is_file()
    and (_IMPORT_TIME_OWNER_ROOT / "uv.lock").is_file()
    and (_IMPORT_TIME_OWNER_ROOT / "src" / "polisyos").is_dir()
):
    _IMPORT_TIME_AUTHORITY_IMPORT_CLOSURE = _resolve_authority_import_closure(
        _IMPORT_TIME_OWNER_ROOT,
        __name__,
    )
    (
        _IMPORT_TIME_DEPLOYMENT_BASELINE,
        _IMPORT_TIME_DEPLOYMENT_QUICK_FENCE,
    ) = _stable_deployment_snapshot(_IMPORT_TIME_OWNER_ROOT)
    _import_authority_closure_modules(_IMPORT_TIME_AUTHORITY_IMPORT_CLOSURE)
    (
        _IMPORT_TIME_LOADED_CODE_MANIFEST,
        _IMPORT_TIME_LOADED_CODE_CONSISTENT,
    ) = _loaded_code_manifest(
        _IMPORT_TIME_OWNER_ROOT,
        _IMPORT_TIME_AUTHORITY_IMPORT_CLOSURE,
    )
    if _deployment_quick_fence(_IMPORT_TIME_OWNER_ROOT) != _IMPORT_TIME_DEPLOYMENT_QUICK_FENCE:
        raise ConfidenceLedgerError("canonical_loaded_runtime_mismatch")
else:
    # An installed package lacks the source checkout's canonical lock/build
    # inputs until the confidence-ledger build issuer is appointed and wired.
    # Do not synthesize currentness; history-only callers may still use the
    # dedicated replay path when their import graph permits it.
    _IMPORT_TIME_AUTHORITY_IMPORT_CLOSURE = ()
    _IMPORT_TIME_DEPLOYMENT_BASELINE = None
    _IMPORT_TIME_DEPLOYMENT_QUICK_FENCE = ()
    _IMPORT_TIME_LOADED_CODE_MANIFEST = ""
    _IMPORT_TIME_LOADED_CODE_CONSISTENT = False
    _IMPORT_TIME_DEPLOYMENT_IDENTITY_REASON = "packaged_deployment_identity_issuer_unavailable"
