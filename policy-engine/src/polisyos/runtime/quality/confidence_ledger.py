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
import contextvars
import dataclasses as _dataclasses
import dis
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
from importlib.machinery import SourceFileLoader
from pathlib import Path
from typing import Any, Literal, Self, cast

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
type _FacadeRuntimeBindingReference = tuple[
    str,
    str,
    types.ModuleType,
    str,
    types.ModuleType,
    str,
    object,
    str,
    str,
    types.ModuleType,
    str,
    str,
    object,
    types.FunctionType | None,
    str | None,
    object,
]
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


class _CodeNormalizationCache:
    """Memoize immutable code-object normalization for one integrity pass."""

    def __init__(self) -> None:
        self._normalized_by_identity: dict[int, tuple[types.CodeType, dict[str, object]]] = {}

    def get(self, code: types.CodeType) -> dict[str, object] | None:
        """Return a normalized value only when the retained object is identical."""
        entry = self._normalized_by_identity.get(id(code))
        if entry is None or entry[0] is not code:
            return None
        return entry[1]

    def put(self, code: types.CodeType, value: dict[str, object]) -> None:
        """Retain the immutable code object beside its derived value."""
        self._normalized_by_identity[id(code)] = (code, value)


class _IntegrityAnalysisContext:
    """Hold source and code derivations for exactly one integrity pass."""

    def __init__(self) -> None:
        self.code_cache = _CodeNormalizationCache()
        self._source_bytes_by_path: dict[Path, bytes] = {}
        self._source_trees_by_bytes: dict[tuple[bytes, bool], ast.Module] = {}

    def remember_source(self, source_path: Path, source_bytes: bytes) -> bytes:
        """Bind exact source bytes to a resolved path for this pass."""
        resolved = source_path.resolve()
        previous = self._source_bytes_by_path.get(resolved)
        if previous is not None and previous != source_bytes:
            raise ConfidenceLedgerError(
                "canonical_loaded_runtime_mismatch",
                f"repository source changed during integrity analysis: {resolved.name}",
            )
        self._source_bytes_by_path[resolved] = source_bytes
        return source_bytes

    def source_bytes(self, source_path: Path) -> bytes:
        """Read a source file once and retain its exact bytes for final comparison."""
        resolved = source_path.resolve()
        previous = self._source_bytes_by_path.get(resolved)
        if previous is not None:
            return previous
        try:
            source_bytes = resolved.read_bytes()
        except OSError as exc:
            raise ConfidenceLedgerError(
                "canonical_loaded_runtime_mismatch",
                f"loaded repository source unavailable: {resolved.name}",
            ) from exc
        return self.remember_source(resolved, source_bytes)

    def source_tree(self, source_path: Path) -> ast.Module:
        """Return the AST derived from the exact bytes observed in this pass."""
        return self.tree_for_bytes(
            self.source_bytes(source_path),
            filename=str(source_path),
            decode_utf8=True,
        )

    def tree_for_bytes(
        self,
        source_bytes: bytes,
        *,
        filename: str,
        decode_utf8: bool = False,
    ) -> ast.Module:
        """Parse each distinct exact source byte string once in this pass."""
        key = (source_bytes, decode_utf8)
        tree = self._source_trees_by_bytes.get(key)
        if tree is None:
            source: str | bytes = source_bytes.decode("utf-8") if decode_utf8 else source_bytes
            tree = ast.parse(source, filename=filename)
            self._source_trees_by_bytes[key] = tree
        return tree

    def assert_sources_unchanged(self) -> None:
        """Reject source drift between derivation and the end of this pass."""
        for source_path, expected_bytes in sorted(
            self._source_bytes_by_path.items(), key=lambda item: item[0].as_posix()
        ):
            try:
                current_bytes = source_path.read_bytes()
            except OSError as exc:
                raise ConfidenceLedgerError(
                    "canonical_loaded_runtime_mismatch",
                    "loaded repository source unavailable at end of integrity analysis: "
                    f"{source_path.name}",
                ) from exc
            if current_bytes != expected_bytes:
                raise ConfidenceLedgerError(
                    "canonical_loaded_runtime_mismatch",
                    f"repository source changed during integrity analysis: {source_path.name}",
                )


_ACTIVE_INTEGRITY_ANALYSIS: contextvars.ContextVar[_IntegrityAnalysisContext | None] = (
    contextvars.ContextVar("polisyos_confidence_ledger_integrity_analysis", default=None)
)


def _active_integrity_analysis() -> _IntegrityAnalysisContext | None:
    """Return this context's currently active integrity-pass derivations."""
    return _ACTIVE_INTEGRITY_ANALYSIS.get()


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
        if authority_provenance == "canonical_repo":
            _require_import_time_identity_snapshot()
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

        _require_import_time_identity_snapshot()
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
            and _IMPORT_TIME_LOADED_CODE_CONSISTENT is True
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

        if self._authority_provenance == "canonical_repo":
            root = self._authority_repo_root
            observed: str | None = None
            if root is not None and root == _loaded_policy_engine_root():
                try:
                    quick_fence = _deployment_quick_fence(root)
                except ConfidenceLedgerError:
                    quick_fence = None
                if quick_fence != self._deployment_quick_fence:
                    try:
                        deployment_baseline, stable_fence = _stable_deployment_snapshot(root)
                        observed = _deployment_identity_from_baseline(deployment_baseline)
                    except ConfidenceLedgerError:
                        observed = None
                    if observed == self._deployment_identity:
                        self._deployment_quick_fence = stable_fence
                    else:
                        # Unavailable bytes fail this operation closed, but do not
                        # become a durable claim that deployment identity changed.
                        if observed is not None and self._journal_path.exists():
                            self._persist_deployment_drift_poison_locked(observed)
                        raise ConfidenceLedgerError("canonical_deployment_identity_invalid")
        _assert_ledger_artifact_contracts_current()

    def _read_pinned_cas_json_for_drift_poison_locked(
        self,
        artifact_ref: str,
        *,
        contract_id: str,
    ) -> object:
        """Read a poison prerequisite against import-pinned CAS contracts only."""

        from polisyos.core.artifacts import load_core_json_artifact

        contract = _IMPORT_TIME_LEDGER_ARTIFACT_CONTRACTS.get(contract_id)
        if contract is None:
            raise ConfidenceLedgerError("ledger_cas_manifest_invalid")
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

    def _journaled_put_drift_poison_locked(self, payload: dict[str, Any]) -> None:
        """Persist only the fail-closed poison record using its pinned contract."""

        contract = _IMPORT_TIME_LEDGER_ARTIFACT_CONTRACTS.get("deployment_drift_poison")
        if contract is None:
            raise ConfidenceLedgerError("deployment_drift_poison_invalid")
        artifact_ref = _cas_json_artifact_ref(payload)
        self._append_scope_journal_intent(
            artifact_kind="deployment_drift_poison",
            artifact_ref=artifact_ref,
            payload=payload,
        )
        ref = self._artifact_store.put_json(
            _jsonable(payload),
            artifacts.PutOptions(
                kind=contract.kind,
                media_type=contract.media_type,
                schema=contract.schema,
                producer=contract.producer,
            ),
            canon_spec=_IMPORT_TIME_LEDGER_CANON_SPEC,
        )
        if str(ref.artifact_id) != artifact_ref:
            raise ConfidenceLedgerError("ledger_scope_journal_invalid")
        stored_payload = self._read_pinned_cas_json_for_drift_poison_locked(
            artifact_ref,
            contract_id="deployment_drift_poison",
        )
        if stored_payload != payload:
            raise ConfidenceLedgerError("ledger_scope_journal_invalid")
        self._append_scope_journal_commit(
            artifact_kind="deployment_drift_poison",
            artifact_ref=artifact_ref,
        )

    def _persist_deployment_drift_poison_locked(self, observed: str) -> None:
        """Persist an irreversible denial before reporting canonical source drift."""

        if not isinstance(observed, str) or observed == self._deployment_identity:
            raise ConfidenceLedgerError("deployment_drift_poison_invalid")
        registry_ref = _cas_json_artifact_ref(self._registry.source_payload())
        root = self._expected_root_binding(registry_ref)
        root_ref = _cas_json_artifact_ref(root)
        try:
            stored_root = ConfidenceLedgerRoot.model_validate(
                self._read_pinned_cas_json_for_drift_poison_locked(
                    root_ref,
                    contract_id="root",
                )
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
            "observed_deployment_identity": observed,
            "reason": "canonical_deployment_identity_changed",
        }
        payload["poison_id"] = _identity(
            "confidence-deployment-drift-poison",
            payload,
        )
        self._journaled_put_drift_poison_locked(payload)

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
    analysis = _active_integrity_analysis()
    tree = (
        analysis.tree_for_bytes(
            source_bytes,
            filename="confidence_ledger.py",
            decode_utf8=False,
        )
        if analysis is not None
        else ast.parse(source_bytes, filename="confidence_ledger.py")
    )
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
            "facade_runtime_projection": _IMPORT_TIME_FACADE_RUNTIME_PROJECTION,
            "loaded_code_manifest": _IMPORT_TIME_LOADED_CODE_MANIFEST,
        },
    )


def _assert_loaded_runtime_matches_import_baseline(
    repo_root: Path,
    *,
    deployment_baseline: str | None = None,
) -> None:
    """Reject authority if disk or runtime differs from the importing process."""

    _require_import_time_identity_snapshot()
    _assert_ledger_artifact_contracts_current()
    observed_binding_references: list[_FacadeRuntimeBindingReference] = []
    facade_projection, supplemental_closure = _source_facade_runtime_projection(
        repo_root,
        _derived_authority_import_closure(repo_root),
        runtime_binding_references=observed_binding_references,
    )
    if not _runtime_binding_references_match(
        observed_binding_references,
        _IMPORT_TIME_FACADE_RUNTIME_BINDING_REFERENCES,
    ):
        raise ConfidenceLedgerError("canonical_loaded_runtime_mismatch")
    runtime_closure = _combined_runtime_code_closure(
        _IMPORT_TIME_AUTHORITY_IMPORT_CLOSURE,
        supplemental_closure,
    )
    if (
        facade_projection != _IMPORT_TIME_FACADE_RUNTIME_PROJECTION
        or runtime_closure != _IMPORT_TIME_RUNTIME_CODE_CLOSURE
    ):
        raise ConfidenceLedgerError("canonical_loaded_runtime_mismatch")
    loaded_code_manifest, loaded_code_consistent = _loaded_code_manifest(
        repo_root,
        runtime_closure,
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

    _require_import_time_identity_snapshot()
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


def _require_import_time_identity_snapshot() -> None:
    """Refuse authority when import-time identity was not captured successfully."""

    if not _IMPORT_TIME_LOADED_CODE_CONSISTENT:
        failure = _IMPORT_TIME_DEPLOYMENT_IDENTITY_FAILURE
        detail = (
            f"{failure[0]}: {failure[1]}"
            if failure is not None
            else "import-time identity snapshot is unavailable"
        )
        raise ConfidenceLedgerError(_IMPORT_TIME_DEPLOYMENT_IDENTITY_REASON, detail)


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


def _combined_runtime_code_closure(
    closure: tuple[tuple[str, str], ...],
    supplemental: tuple[tuple[str, str], ...],
) -> tuple[tuple[str, str], ...]:
    """Combine source-selected modules and source-bound cached-export owners."""

    combined = dict(closure)
    for module_name, relative_path in supplemental:
        existing = combined.get(module_name)
        if existing is not None and existing != relative_path:
            raise ConfidenceLedgerError("canonical_loaded_runtime_mismatch")
        combined[module_name] = relative_path
    return tuple(sorted(combined.items()))


@dataclass(frozen=True, slots=True)
class _LiteralModuleGetattrProviderIndex:
    """Index literal PEP 562 providers found in one parsed source module."""

    providers_by_export: Mapping[str, frozenset[str]]
    invalid_exports: frozenset[str]
    provider_symbols_by_export: Mapping[str, frozenset[str]] | None = None
    generated_mapping_dispatch: bool = False
    mapping_names: frozenset[str] = frozenset()
    module_providers_by_export: Mapping[str, frozenset[str]] | None = None


@dataclass(slots=True)
class _AuthorityImportClosureSourceIndex:
    """Cache source parses and PEP 562 indexes for one closure computation."""

    parsed_by_content: dict[bytes, ast.Module]
    providers_by_content: dict[bytes, _LiteralModuleGetattrProviderIndex]
    diagnostic_unqualified_direct_bindings: set[tuple[str, str]] | None = None

    def parse(self, content: bytes, *, filename: str) -> ast.Module:
        """Parse exact source bytes once within the current closure computation."""

        tree = self.parsed_by_content.get(content)
        if tree is None:
            tree = ast.parse(content, filename=filename)
            self.parsed_by_content[content] = tree
        return tree


@dataclass(frozen=True, slots=True)
class _DiagnosticAuthoritySourceCandidates:
    """Source-only candidates and bindings which remain unqualified."""

    entry_modules: tuple[str, ...]
    source_candidates: tuple[tuple[str, str], ...]
    unqualified_direct_bindings: tuple[tuple[str, str], ...]
    unresolved_by_construction: tuple[str, ...]


def _diagnose_unqualified_authority_import_candidates(
    repo_root: Path,
    entry_module: str | Iterable[str],
) -> _DiagnosticAuthoritySourceCandidates:
    """Collect unqualified source candidates without executing or admitting them."""

    entries = (entry_module,) if isinstance(entry_module, str) else tuple(sorted(set(entry_module)))
    if not entries:
        raise ValueError("diagnostic_authority_entry_missing")
    unqualified: set[tuple[str, str]] = set()
    candidates = _resolve_authority_import_closure(
        repo_root,
        entries,
        _diagnostic_unqualified_direct_bindings=unqualified,
    )
    return _DiagnosticAuthoritySourceCandidates(
        entry_modules=entries,
        source_candidates=candidates,
        unqualified_direct_bindings=tuple(sorted(unqualified)),
        unresolved_by_construction=(
            "source_readset_and_complete_denominator_not_instrumented",
            "actual_source_execution_and_selected_provider",
            "direct_binding_construction_and_consumer_holdings",
            "dynamic_imports_outside_static_source_candidates",
            "material_state_and_protected_use",
        ),
    )


_NO_EXECUTION_BINDING = object()


def _passive_capture_lookup(mapping: object, name: str) -> object:
    if type(mapping) not in (dict, types.MappingProxyType):
        return _NO_EXECUTION_BINDING
    try:
        for key, value in cast("Mapping[object, object]", mapping).items():
            if type(key) is str and key == name:
                return value
    except RuntimeError:
        return _NO_EXECUTION_BINDING
    return _NO_EXECUTION_BINDING


def _code_tree_contains(root: object, target: object) -> bool:
    """Compare code identities within a retained compiler output tree."""

    if type(root) is not types.CodeType or type(target) is not types.CodeType:
        return False
    pending = [root]
    while pending:
        code = pending.pop()
        if code is target:
            return True
        pending.extend(item for item in code.co_consts if type(item) is types.CodeType)
    return False


def _recorder_function_hold_matches(row: object) -> bool:
    """Inspect one held function without calling it or its defaults."""

    if type(row) is not tuple or len(row) != 7:
        return False
    function, code, defaults, kwdefaults, kwitems, closure, cells = row
    if (
        type(function) is not types.FunctionType
        or type(code) is not types.CodeType
        or function.__code__ is not code
        or function.__defaults__ is not defaults
        or function.__kwdefaults__ is not kwdefaults
        or function.__closure__ is not closure
        or type(kwitems) is not tuple
        or type(cells) is not tuple
    ):
        return False
    if kwdefaults is None:
        if kwitems:
            return False
    elif (
        type(kwdefaults) is not dict
        or len(kwdefaults) != len(kwitems)
        or any(type(key) is not str for key in kwdefaults)
        or any(
            type(item) is not tuple
            or len(item) != 2
            or type(item[0]) is not str
            or _passive_capture_lookup(kwdefaults, item[0]) is not item[1]
            for item in kwitems
        )
    ):
        return False
    if closure is None:
        return not cells
    if type(closure) is not tuple or len(closure) != len(cells):
        return False
    for cell, held in zip(closure, cells, strict=True):
        if (
            type(cell) is not types.CellType
            or type(held) is not tuple
            or len(held) != 3
            or held[0] is not cell
            or type(held[1]) is not bool
        ):
            return False
        try:
            content = cell.cell_contents
        except ValueError:
            if held[1]:
                return False
        else:
            if not held[1] or content is not held[2]:
                return False
    return True


def _recorder_class_hold_matches(row: object) -> bool:
    """Inspect retained class bindings and bases without invoking descriptors."""

    if type(row) is not tuple or len(row) != 3:
        return False
    cls, bases, fields = row
    if type(cls) is not type or type(bases) is not tuple or type(fields) is not tuple:
        return False
    namespace = type.__getattribute__(cls, "__dict__")
    current_bases = type.__getattribute__(cls, "__bases__")
    if (
        len(current_bases) != len(bases)
        or any(actual is not held for actual, held in zip(current_bases, bases, strict=True))
        or len(namespace) != len(fields)
    ):
        return False
    return not any(
        type(item) is not tuple
        or len(item) != 2
        or type(item[0]) is not str
        or _passive_capture_lookup(namespace, item[0]) is not item[1]
        for item in fields
    )


def _host_recorder_anchor_matches(recorder: object, capture: object) -> bool:
    """Passively reconcile the early host's retained recorder execution surface.

    This is a prerequisite for diagnostics, not an appointment, a complete
    provider/state proof, or an authority grant. The appointed host and Python
    runtime remain the bounded root of trust for the process.
    """

    host = _passive_capture_lookup(sys.modules, "_polisyos_early_host")
    session = _passive_capture_lookup(sys.__dict__, "_polisyos_loaded_host_v1")
    if (
        type(host) is not types.ModuleType
        or type(recorder) is not types.ModuleType
        or type(session) is not dict
        or _passive_capture_lookup(sys.modules, "_polisyos_loaded_source_capture") is not recorder
        or _passive_capture_lookup(host.__dict__, "_HOST_SESSION") is not session
        or _passive_capture_lookup(session, "recorder") is not recorder
        or _passive_capture_lookup(session, "capture") is not capture
        or _passive_capture_lookup(sys.__dict__, "_polisyos_loaded_execution_owner_v1")
        is not capture
    ):
        return False
    process_id = _passive_capture_lookup(session, "pid")
    if type(process_id) is not int or process_id != os.getpid():
        return False
    host_code = _passive_capture_lookup(session, "host_code")
    recorder_code = _passive_capture_lookup(session, "recorder_code")
    handoff = _passive_capture_lookup(host.__dict__, "handoff_if_ready")
    capture_type = _passive_capture_lookup(session, "recorder_type")
    descriptors = _passive_capture_lookup(session, "recorder_descriptors")
    retained_globals = _passive_capture_lookup(session, "recorder_globals")
    function_holds = _passive_capture_lookup(session, "recorder_functions")
    class_holds = _passive_capture_lookup(session, "recorder_classes")
    if (
        type(host_code) is not types.CodeType
        or host_code is not _passive_capture_lookup(host.__dict__, "_HOST_EXECUTION_CODE")
        or type(recorder_code) is not types.CodeType
        or type(handoff) is not types.FunctionType
        or handoff is not _passive_capture_lookup(session, "handoff")
        or handoff.__globals__ is not host.__dict__
        or not _code_tree_contains(host_code, handoff.__code__)
        or type(capture_type) is not type
        or type(capture) is not capture_type
        or _passive_capture_lookup(recorder.__dict__, "SourceExecutionCapture") is not capture_type
        or type(descriptors) is not tuple
        or type(retained_globals) is not tuple
        or type(function_holds) is not tuple
        or type(class_holds) is not tuple
    ):
        return False
    if not all(_recorder_function_hold_matches(row) for row in function_holds) or not all(
        _recorder_class_hold_matches(row) for row in class_holds
    ):
        return False
    held_functions = {id(row[0]) for row in function_holds}
    held_classes = {id(row[0]) for row in class_holds}
    if (
        len(held_functions) != len(function_holds)
        or len(held_classes) != len(class_holds)
        or id(capture_type) not in held_classes
    ):
        return False
    class_namespace = type.__getattribute__(capture_type, "__dict__")
    if type(_passive_capture_lookup(class_namespace, "__dict__")) is not types.GetSetDescriptorType:
        return False
    instance_namespace = object.__getattribute__(capture, "__dict__")
    if type(instance_namespace) is not dict:
        return False
    descriptor_types = (types.FunctionType, property, classmethod, staticmethod)
    actual_names = {
        name
        for name, value in class_namespace.items()
        if type(name) is str and type(value) in descriptor_types
    }
    retained_names: set[str] = set()
    referenced_names: set[str] = set()
    for row in descriptors:
        if type(row) is not tuple or len(row) != 2 or type(row[0]) is not str:
            return False
        name, value = row
        if (
            name in retained_names
            or _passive_capture_lookup(class_namespace, name) is not value
            or _passive_capture_lookup(instance_namespace, name) is not _NO_EXECUTION_BINDING
        ):
            return False
        retained_names.add(name)
        functions: tuple[types.FunctionType, ...]
        if type(value) is types.FunctionType:
            functions = (value,)
        elif type(value) is property:
            functions = cast(
                "tuple[types.FunctionType, ...]",
                tuple(
                    function
                    for function in (value.fget, value.fset, value.fdel)
                    if function is not None
                ),
            )
        elif type(value) in (classmethod, staticmethod):
            functions = (value.__func__,)
        else:
            return False
        for function in functions:
            if (
                type(function) is not types.FunctionType
                or id(function) not in held_functions
                or function.__globals__ is not recorder.__dict__
                or not _code_tree_contains(recorder_code, function.__code__)
            ):
                return False
    for row in class_holds:
        for _, value in row[2]:
            if type(value) is types.FunctionType:
                functions = (value,)
            elif type(value) is property:
                functions = cast(
                    "tuple[types.FunctionType, ...]",
                    tuple(
                        function
                        for function in (value.fget, value.fset, value.fdel)
                        if function is not None
                    ),
                )
            elif type(value) in (classmethod, staticmethod):
                functions = (value.__func__,)
            else:
                continue
            if any(
                type(function) is not types.FunctionType or id(function) not in held_functions
                for function in functions
            ):
                return False
    for row in function_holds:
        function = row[0]
        if function.__globals__ is recorder.__dict__:
            pending = [function.__code__]
            while pending:
                code = pending.pop()
                referenced_names.update(code.co_names)
                pending.extend(item for item in code.co_consts if type(item) is types.CodeType)
    if retained_names != actual_names:
        return False
    actual_global_names = {
        name
        for name in referenced_names
        if _passive_capture_lookup(recorder.__dict__, name) is not _NO_EXECUTION_BINDING
    }
    retained_global_names: set[str] = set()
    for row in retained_globals:
        if type(row) is not tuple or len(row) != 2 or type(row[0]) is not str:
            return False
        name, value = row
        if (
            name in retained_global_names
            or _passive_capture_lookup(recorder.__dict__, name) is not value
            or (
                type(value) is types.FunctionType
                and value.__globals__ is recorder.__dict__
                and id(value) not in held_functions
            )
            or (
                type(value) is type
                and type.__getattribute__(value, "__module__") == recorder.__name__
                and id(value) not in held_classes
            )
        ):
            return False
        retained_global_names.add(name)
    if retained_global_names != actual_global_names:
        return False
    root = _loaded_policy_engine_root()
    try:
        for module, code, expected_path, expected_hash in (
            (host, host_code, root / "tools/authority_bootstrap.py", "host_sha256"),
            (
                recorder,
                recorder_code,
                root / "tools/loaded_execution_capture.py",
                "recorder_sha256",
            ),
        ):
            filename = _passive_capture_lookup(module.__dict__, "__file__")
            selected_hash = _passive_capture_lookup(session, expected_hash)
            if type(filename) is not str or type(selected_hash) is not str:
                return False
            path = Path(filename)
            source = path.read_bytes()
            if (
                path.resolve() != expected_path.resolve()
                or hashlib.sha256(source).hexdigest() != selected_hash
            ):
                return False
            compiled = compile(
                source, str(path), "exec", dont_inherit=True, optimize=sys.flags.optimize
            )
            if _normalize_code_object(compiled) != _normalize_code_object(code):
                return False
    except (OSError, SyntaxError, TypeError, ValueError):
        return False
    return True


# Boundary rationale: these private diagnostics accept opaque host-owned
# producer objects; importing tooling types into the product would invert the
# dependency boundary, and their values are never treated as authority.
def _source_import_aliases_for_event(
    repo_root: Path,
    capture: Any,  # noqa: ANN401
    event: Any,  # noqa: ANN401
    symbol: str,
    *,
    parsed_sources: dict[str, ast.Module] | None = None,
    imports_by_line: dict[str, dict[int, list[ast.ImportFrom]]] | None = None,
) -> tuple[str, ...]:
    """Resolve import aliases from the actual caller's retained source line."""

    if event.route != "builtin_import" or type(event.caller_line) is not int:
        return ()
    importer = capture.completed(event.importer_name)
    tree = None if parsed_sources is None else parsed_sources.get(event.importer_name)
    if tree is None:
        capture.assert_retained(frozenset({event.importer_name}))
        source = repo_root / importer.relative_path
        content = source.read_bytes()
        if hashlib.sha256(content).hexdigest() != importer.source_sha256:
            raise ValueError("importer_source_observation_mismatch")
        tree = ast.parse(content, filename=str(source))
        if parsed_sources is not None:
            parsed_sources[event.importer_name] = tree
    if imports_by_line is None:
        nodes: Iterable[ast.AST] = ast.walk(tree)
    else:
        indexed = imports_by_line.get(event.importer_name)
        if indexed is None:
            indexed = {}
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    for line in range(node.lineno, (node.end_lineno or node.lineno) + 1):
                        indexed.setdefault(line, []).append(node)
            imports_by_line[event.importer_name] = indexed
        nodes = indexed.get(event.caller_line, ())
    aliases: set[str] = set()
    for node in nodes:
        if not isinstance(node, ast.ImportFrom) or not (
            node.lineno <= event.caller_line <= (node.end_lineno or node.lineno)
        ):
            continue
        if node.level:
            package = importer.package
            if not package or node.level > len(package.split(".")):
                continue
            parent = package.rsplit(".", node.level - 1)[0]
            provider = f"{parent}.{node.module}" if node.module else parent
        else:
            provider = node.module or ""
        if provider != event.provider_name:
            continue
        aliases.update(alias.asname or symbol for alias in node.names if alias.name == symbol)
    return tuple(sorted(aliases))


def _observed_source_bindings(
    repo_root: Path,
    capture: Any,  # noqa: ANN401
    graph: Any,  # noqa: ANN401
) -> tuple[
    tuple[tuple[str, str, str, tuple[tuple[str, str], ...]], ...],
    tuple[tuple[str, str, str, str], ...],
]:
    """Reconcile actual module-initializer import bindings for diagnostics.

    A disagreement is reported without deciding whether an incidental rebinding
    matters to authority. The protected operation still needs its independently
    derived readset and the existing recorder guard for every required binding.
    """

    reached = frozenset(graph.reached_sources)
    parsed_sources: dict[str, ast.Module] = {}
    imports_by_line: dict[str, dict[int, list[ast.ImportFrom]]] = {}
    namespaces: dict[str, Mapping[str, object]] = {}
    provider_digests: dict[str, str] = {}
    matched: dict[tuple[str, str, str], set[tuple[str, str]]] = {}
    disagreements: set[tuple[str, str, str, str]] = set()
    for event in capture.import_events():
        if (
            event.route != "builtin_import"
            or event.importer_name not in reached
            or event.provider_name not in reached
        ):
            continue
        try:
            importer = capture.completed(event.importer_name)
            provider = capture.completed(event.provider_name)
        except ImportError:
            if capture.failed:
                raise
            continue
        if event.caller_code is not importer.code:
            # Function-local imports are not module-global binding claims.
            continue
        if event.importer is not importer.module or event.provider is not provider.module:
            raise ValueError("imported_module_observation_mismatch")
        for symbol in event.requested_exports:
            if type(symbol) is not str or not symbol.isidentifier():
                continue
            retained = _passive_capture_lookup(provider.watched_exports, symbol)
            event_value = _passive_capture_lookup(event.retained_exports, symbol)
            if retained is _NO_EXECUTION_BINDING or event_value is _NO_EXECUTION_BINDING:
                continue
            aliases = _source_import_aliases_for_event(
                repo_root,
                capture,
                event,
                symbol,
                parsed_sources=parsed_sources,
                imports_by_line=imports_by_line,
            )
            for alias in aliases:
                provider_namespace = namespaces.get(event.provider_name)
                if provider_namespace is None:
                    provider_namespace = capture.retained_module_namespace(event.provider_name)
                    namespaces[event.provider_name] = provider_namespace
                importer_namespace = namespaces.get(event.importer_name)
                if importer_namespace is None:
                    importer_namespace = capture.retained_module_namespace(event.importer_name)
                    namespaces[event.importer_name] = importer_namespace
                current_provider = _passive_capture_lookup(provider_namespace, symbol)
                current_consumer = _passive_capture_lookup(importer_namespace, alias)
                if (
                    event_value is not retained
                    or current_provider is not retained
                    or current_consumer is not retained
                ):
                    disagreements.add((event.provider_name, symbol, event.importer_name, alias))
                    continue
                digest = provider_digests.get(event.provider_name)
                if digest is None:
                    source = repo_root / provider.relative_path
                    digest = hashlib.sha256(source.read_bytes()).hexdigest()
                    if (
                        digest != provider.source_sha256
                        or source.resolve() != Path(provider.origin).resolve()
                        or type(provider.code) is not types.CodeType
                    ):
                        raise ValueError("executed_source_observation_mismatch")
                    provider_digests[event.provider_name] = digest
                capture.assert_import_binding(
                    event, importer_attribute=alias, provider_export=symbol
                )
                matched.setdefault((event.provider_name, symbol, digest), set()).add(
                    (event.importer_name, alias)
                )
    bindings = tuple(
        (module, symbol, digest, tuple(sorted(consumers)))
        for (module, symbol, digest), consumers in sorted(matched.items())
    )
    return bindings, tuple(sorted(disagreements))


def _observe_unsealed_host_capture(
    recorder_module: object,
    capture: Any,  # noqa: ANN401
) -> dict[str, object]:
    """Reconcile live source candidates for diagnostics without admitting identity.

    The early host supplies its retained recorder and capture. This result is not
    an appointment, complete dependency graph, state proof, or authority token.
    Actual observed module-level imports and their held bindings are examined
    generically; no particular protocol or provider is privileged.
    """

    report: dict[str, object] = {
        "status": "not_established",
        "phase": "collecting",
        "proof_schema": "policyos.runtime.confidence_ledger.loaded_execution_capture.v1",
        "identity_rule": "canonical-source-execution/1",
        "runtime_profile_id": None,
        "capture_time_role": "in_progress_or_unavailable",
        "currentness_time_role": "not_evaluated",
        "executed_direct_bindings": [],
        "unresolved": (
            "trusted_host_appointment",
            "complete_relevant_bindings",
            "runtime_dependency_and_native_profile",
            "material_state",
            "owner_sealing_and_currentness",
            "protected_through_use",
        ),
    }
    identity = capture_loaded_deployment_identity()
    report["legacy_identity_status"] = identity.status
    report["legacy_identity_reason"] = identity.reason_code
    report["protected_loaded_execution_status"] = "not_established"
    if not _host_recorder_anchor_matches(recorder_module, capture):
        report["failure"] = "host_execution_anchor_unavailable"
        return report
    try:
        capture_diagnostic = capture.diagnostic()
        report["phase"] = capture_diagnostic.phase
        report["failed_premise"] = capture_diagnostic.failed_premise
        report["capture_failure"] = capture_diagnostic.failure_code
        root = _loaded_policy_engine_root()
        capture.assert_retained(frozenset({__name__}))
        execution = capture.completed(__name__)
        if execution.module is not _passive_capture_lookup(sys.modules, __name__):
            raise ValueError("ledger_execution_binding_changed")
        graph = capture.relevant_graph(frozenset({__name__}))
        matched, disagreements = _observed_source_bindings(root, capture, graph)
        report["executed_direct_bindings"] = matched
        report["observed_binding_disagreements"] = disagreements
        report["observed_source_modules"] = len(graph.reached_sources)
        report["external_provider_count"] = len(graph.external_providers)
        report["failed_reachable_imports"] = graph.failed_imports
        report["failed_reachable_modules"] = graph.failed_modules
        report["unresolved_importers"] = graph.unresolved_importers
        report["pending_modules"] = graph.pending_modules
        report["event_graph_scope"] = (
            "observed module-initializer import bindings reachable from the ledger; "
            "not a complete runtime closure or authority readset"
        )
        report["candidate_only"] = True
    except (
        OSError,
        ImportError,
        AttributeError,
        TypeError,
        ValueError,
        ConfidenceLedgerError,
    ) as exc:
        if type(exc) is ConfidenceLedgerError:
            report["failure"] = exc.code
            report["failure_detail"] = exc.detail
        elif (
            (
                type(exc) is _passive_capture_lookup(recorder_module.__dict__, "CaptureError")
                or type(exc) is ValueError
            )
            and len(exc.args) == 1
            and type(exc.args[0]) is str
        ):
            report["failure"] = exc.args[0]
        else:
            report["failure"] = type(exc).__name__
    return report


def _resolve_authority_import_closure(
    repo_root: Path,
    entry_module: str | Iterable[str],
    *,
    include_tools: bool = False,
    _diagnostic_unqualified_direct_bindings: set[tuple[str, str]] | None = None,
) -> tuple[tuple[str, str], ...]:
    """Discover a repository-local source import closure candidate.

    This source-only set is not an authority admission. Runtime authority callers
    must reconcile it against loaded modules, selected facade/provider/importer
    objects, code, profile, and the shared source-integrity snapshot before use.
    Runtime mode follows repository-local static imports outside typing-only arms
    plus source-declared PEP 562 candidates. Literal dynamic targets are source
    inputs, not runtime modules, unless reached through a static edge; owner/tool
    mode additionally sees literal dynamic imports and tools. Both modes exclude
    typing-only arms. The private diagnostic collector permits unqualified local
    source bindings as candidates and records every such binding. That mode is
    not evidence of the selected provider, execution, or an admissible closure.
    """

    resolved: dict[str, Path] = {}
    pending = {entry_module} if isinstance(entry_module, str) else set(entry_module)
    allowed_roots = {"polisyos", *(("tools",) if include_tools else ())}
    directory_entries: dict[Path, frozenset[str]] = {}
    source_index = _AuthorityImportClosureSourceIndex(
        {}, {}, _diagnostic_unqualified_direct_bindings
    )

    @functools.cache
    def resolve_source(module_name: str) -> Path | None:
        return _repository_module_source(
            repo_root,
            module_name,
            directory_entries=directory_entries,
        )

    def candidate_route_for_closure(
        base: str,
        export_name: str,
        *,
        visited: frozenset[tuple[str, str]] = frozenset(),
    ) -> tuple[str, str, str | None] | None:
        candidate = _source_module_import_route_candidate(
            repo_root,
            base,
            export_name,
            directory_entries=directory_entries,
            source_index=source_index,
            visited=visited,
        )
        if candidate.package_initializer_effect_unknown and candidate.route is None:
            raise ConfidenceLedgerError(
                "canonical_loaded_runtime_mismatch",
                f"unqualified package initializer route: {base}.{export_name}",
            )
        # Discovery records a source candidate, not an authority admission.
        # The later runtime projection binds the facade, provider, importer, and
        # selected consumer object before this candidate can support a claim.
        return candidate.route

    def discover_route_chain(
        base: str,
        export_name: str,
        route: tuple[str, str, str | None],
        discovered: set[str],
    ) -> None:
        """Include every finite symbol owner reached by nested lazy maps."""

        route_kind, target_module, target_symbol = route
        if route_kind == "symbol" and (target_module, target_symbol) == (base, export_name):
            discovered.add(target_module)
            return
        visited_routes: frozenset[tuple[str, str]] = frozenset({(base, export_name)})
        while (
            route_kind in {"module", "symbol"}
            and _repository_module_root(target_module) in allowed_roots
        ):
            if resolve_source(target_module) is None:
                raise ConfidenceLedgerError(
                    "canonical_loaded_runtime_mismatch",
                    f"unresolved repository import: {target_module}",
                )
            discovered.add(target_module)
            if route_kind != "symbol" or target_symbol is None:
                return
            current = (target_module, target_symbol)
            if current in visited_routes:
                raise ConfidenceLedgerError(
                    "canonical_loaded_runtime_mismatch",
                    f"cyclic source import route: {target_module}.{target_symbol}",
                )
            next_route = candidate_route_for_closure(
                target_module,
                target_symbol,
                visited=visited_routes,
            )
            if next_route is None:
                raise ConfidenceLedgerError(
                    "canonical_loaded_runtime_mismatch",
                    f"unresolved source symbol route: {target_module}.{target_symbol}",
                )
            visited_routes = visited_routes | {current}
            if next_route == ("symbol", target_module, target_symbol):
                return
            route_kind, target_module, target_symbol = next_route

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
            analysis = _active_integrity_analysis()
            source_path = repo_root / relative
            source_bytes = (
                analysis.source_bytes(source_path)
                if analysis is not None
                else source_path.read_bytes()
            )
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
                    route = candidate_route_for_closure(base, alias.name)
                    if route is None:
                        continue
                    discover_route_chain(base, alias.name, route, discovered)
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


def _package_bound_module_provider_target(
    target: str,
    *,
    module_name: str,
    module_source: Path,
    export_name: str,
) -> str:
    """Resolve one source-owned relative module target against its package."""

    if not target.startswith("."):
        return target
    if Path(module_source).name != "__init__.py":
        raise ConfidenceLedgerError(
            "canonical_loaded_runtime_mismatch",
            f"relative repository module target is not package-bound: {module_name}.{export_name}",
        )
    try:
        return importlib.util.resolve_name(target, module_name)
    except (ImportError, TypeError, ValueError) as exc:
        raise ConfidenceLedgerError(
            "canonical_loaded_runtime_mismatch",
            f"ambiguous relative repository module target: {module_name}.{export_name}",
        ) from exc


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
    provider_index = _source_module_provider_index(
        repo_root,
        module_name,
        tree,
        directory_entries=directory_entries,
        source_index=source_index,
    )

    mapped_targets: set[tuple[str, str]] = set()
    mapped_module_targets: set[str] = set()
    if provider_index.mapping_names:
        external_mappings, _invalid_imports = _source_imported_facade_mappings(
            repo_root,
            module_name,
            tree,
            provider_index.mapping_names,
            directory_entries=directory_entries,
            source_index=source_index,
        )
        source_maps, invalid_maps, _namespace_effect_unknown = (
            _source_declared_facade_mapping_values(
                tree,
                provider_index.mapping_names,
                external_mappings=external_mappings,
            )
        )
        if invalid_maps:
            raise ConfidenceLedgerError(
                "canonical_loaded_runtime_mismatch",
                f"unsupported source facade map: {module_name}",
            )
        module_exports = provider_index.module_providers_by_export or {}
        for source_map in source_maps.values():
            raw_target = source_map.get(export_name, _STATIC_FACADE_UNKNOWN)
            if raw_target is _STATIC_FACADE_UNKNOWN:
                continue
            if export_name in module_exports:
                if type(raw_target) is not str or not raw_target:
                    raise ConfidenceLedgerError(
                        "canonical_loaded_runtime_mismatch",
                        f"invalid module-valued source facade target: {module_name}.{export_name}",
                    )
                mapped_module_targets.add(raw_target)
                continue
            target = _literal_facade_provider_target(export_name, raw_target)
            if target is None:
                raise ConfidenceLedgerError(
                    "canonical_loaded_runtime_mismatch",
                    f"invalid source facade target: {module_name}.{export_name}",
                )
            target_module, target_symbol = target
            if target_module.startswith("."):
                if Path(relative).name != "__init__.py":
                    raise ConfidenceLedgerError(
                        "canonical_loaded_runtime_mismatch",
                        f"relative repository re-export is not package-bound: "
                        f"{module_name}.{export_name}",
                    )
                try:
                    target_module = importlib.util.resolve_name(target_module, module_name)
                except (ImportError, TypeError, ValueError) as exc:
                    raise ConfidenceLedgerError(
                        "canonical_loaded_runtime_mismatch",
                        f"ambiguous relative repository re-export: {module_name}.{export_name}",
                    ) from exc
            mapped_targets.add((target_module, target_symbol))

    mapped_symbol: str | None = None
    module_providers = provider_index.module_providers_by_export or {}

    resolved_module_providers = frozenset(
        _package_bound_module_provider_target(
            target,
            module_name=module_name,
            module_source=relative,
            export_name=export_name,
        )
        for target in module_providers.get(export_name, frozenset())
    )
    resolved_mapped_module_targets = {
        _package_bound_module_provider_target(
            target,
            module_name=module_name,
            module_source=relative,
            export_name=export_name,
        )
        for target in mapped_module_targets
    }
    provider: str | None = None
    if resolved_mapped_module_targets:
        if len(resolved_mapped_module_targets) != 1:
            raise ConfidenceLedgerError(
                "canonical_loaded_runtime_mismatch",
                f"ambiguous module facade map target: {module_name}.{export_name}",
            )
        provider = next(iter(resolved_mapped_module_targets))
        indexed = resolved_module_providers
        if len(indexed) != 1 or provider not in indexed:
            raise ConfidenceLedgerError(
                "canonical_loaded_runtime_mismatch",
                f"source facade map differs from getter: {module_name}.{export_name}",
            )
        mapped_symbol = None
    elif mapped_targets:
        if len(mapped_targets) != 1:
            raise ConfidenceLedgerError(
                "canonical_loaded_runtime_mismatch",
                f"ambiguous source facade map target: {module_name}.{export_name}",
            )
        provider, mapped_symbol = next(iter(mapped_targets))
        indexed_providers = provider_index.providers_by_export.get(export_name, frozenset())
        if provider_index.generated_mapping_dispatch and not indexed_providers:
            raise ConfidenceLedgerError(
                "canonical_loaded_runtime_mismatch",
                f"missing repository re-export binding: {module_name}.{export_name}",
            )
        if indexed_providers:
            normalized_providers: set[str] = set()
            for indexed_provider in indexed_providers:
                if indexed_provider.startswith("."):
                    try:
                        indexed_provider = importlib.util.resolve_name(
                            indexed_provider,
                            module_name,
                        )
                    except (ImportError, TypeError, ValueError) as exc:
                        raise ConfidenceLedgerError(
                            "canonical_loaded_runtime_mismatch",
                            f"ambiguous repository re-export: {module_name}.{export_name}",
                        ) from exc
                normalized_providers.add(indexed_provider)
            indexed_symbols = (provider_index.provider_symbols_by_export or {}).get(
                export_name, frozenset({export_name})
            )
            if provider not in normalized_providers or mapped_symbol not in indexed_symbols:
                raise ConfidenceLedgerError(
                    "canonical_loaded_runtime_mismatch",
                    f"source facade map differs from getter: {module_name}.{export_name}",
                )
    else:
        if export_name in provider_index.invalid_exports or "*" in provider_index.invalid_exports:
            raise ConfidenceLedgerError(
                "canonical_loaded_runtime_mismatch",
                f"non-literal repository re-export: {module_name}.{export_name}",
            )
        direct_module_providers = resolved_module_providers
        if len(direct_module_providers) > 1:
            raise ConfidenceLedgerError(
                "canonical_loaded_runtime_mismatch",
                f"ambiguous module repository re-export: {module_name}.{export_name}",
            )
        if direct_module_providers:
            provider = next(iter(direct_module_providers))
            mapped_symbol = None
        providers = provider_index.providers_by_export.get(export_name, frozenset())
        if provider is None and len(providers) > 1:
            raise ConfidenceLedgerError(
                "canonical_loaded_runtime_mismatch",
                f"ambiguous repository re-export: {module_name}.{export_name}",
            )
        if provider is None:
            provider = next(iter(providers), None)
        if provider is None and provider_index.generated_mapping_dispatch:
            raise ConfidenceLedgerError(
                "canonical_loaded_runtime_mismatch",
                f"missing repository re-export binding: {module_name}.{export_name}",
            )
    if provider is not None and provider.startswith("."):
        if Path(relative).name != "__init__.py":
            raise ConfidenceLedgerError(
                "canonical_loaded_runtime_mismatch",
                f"relative repository re-export is not package-bound: {module_name}.{export_name}",
            )
        try:
            provider = importlib.util.resolve_name(provider, module_name)
        except (ImportError, TypeError, ValueError) as exc:
            raise ConfidenceLedgerError(
                "canonical_loaded_runtime_mismatch",
                f"ambiguous relative repository re-export: {module_name}.{export_name}",
            ) from exc
    if (
        provider is not None
        and provider not in resolved_module_providers
        and _repository_module_root(provider) in {"polisyos", "tools"}
    ):
        provider_symbols = provider_index.provider_symbols_by_export or {}
        symbols = (
            frozenset({mapped_symbol})
            if mapped_symbol is not None
            else provider_symbols.get(export_name, frozenset({export_name}))
        )
        if len(symbols) != 1:
            raise ConfidenceLedgerError(
                "canonical_loaded_runtime_mismatch",
                f"ambiguous repository re-export binding: {module_name}.{export_name}",
            )
        provider_symbol = next(iter(symbols))
        if not _repository_module_exports_symbol(
            repo_root,
            provider,
            provider_symbol,
            directory_entries=directory_entries,
            source_index=source_index,
        ):
            raise ConfidenceLedgerError(
                "canonical_loaded_runtime_mismatch",
                f"repository re-export target does not bind: {provider}.{provider_symbol}",
            )
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


def _source_scope_bound_names(
    nodes: Iterable[ast.AST],
    *,
    include_imports: bool = True,
) -> frozenset[str]:
    """Return names bound in one source scope, excluding nested definition bodies."""

    bound: set[str] = set()
    for node in _source_scope_nodes(nodes):
        if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            bound.add(node.id)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            bound.add(node.name)
        elif isinstance(node, ast.Import) and include_imports:
            bound.update(alias.asname or alias.name.partition(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and include_imports:
            bound.update(alias.asname or alias.name for alias in node.names if alias.name != "*")
        elif isinstance(node, (ast.ExceptHandler, ast.MatchAs, ast.MatchStar)):
            if node.name is not None:
                bound.add(node.name)
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


def _literal_package_child_import_template(node: ast.AST, parameter_name: str) -> bool:
    """Recognize only ``f"{__name__}.{parameter_name}"`` source routes."""

    if not isinstance(node, ast.JoinedStr) or len(node.values) != 3:
        return False
    package_name, separator, export_name = node.values
    return bool(
        isinstance(package_name, ast.FormattedValue)
        and isinstance(package_name.value, ast.Name)
        and package_name.value.id == "__name__"
        and package_name.conversion == -1
        and package_name.format_spec is None
        and isinstance(separator, ast.Constant)
        and separator.value == "."
        and isinstance(export_name, ast.FormattedValue)
        and isinstance(export_name.value, ast.Name)
        and export_name.value.id == parameter_name
        and export_name.conversion == -1
        and export_name.format_spec is None
    )


def _literal_absolute_package_child_import_template(
    node: ast.AST,
    parameter_name: str,
    package_module_name: str | None,
) -> bool:
    """Recognize a source-qualified ``<package>.<selected_name>`` child route."""

    if package_module_name is None or not isinstance(node, ast.JoinedStr) or len(node.values) != 2:
        return False
    prefix, export_name = node.values
    return bool(
        isinstance(prefix, ast.Constant)
        and prefix.value == f"{package_module_name}."
        and isinstance(export_name, ast.FormattedValue)
        and isinstance(export_name.value, ast.Name)
        and export_name.value.id == parameter_name
        and export_name.conversion == -1
        and export_name.format_spec is None
    )


def _literal_getattr_dispatch_collection_names(
    test: ast.expr, parameter_name: str
) -> frozenset[str]:
    """Return source names used by a direct finite membership guard."""

    if not isinstance(test, ast.Compare) or len(test.ops) != 1 or len(test.comparators) != 1:
        return frozenset()
    left, right, operator = test.left, test.comparators[0], test.ops[0]
    if (
        isinstance(operator, (ast.In, ast.NotIn))
        and isinstance(left, ast.Name)
        and left.id == parameter_name
        and isinstance(right, ast.Name)
    ):
        return frozenset({right.id})
    return frozenset()


def _literal_collection_is_source_stable(tree: ast.Module, name: str) -> bool:
    """Reject source-level mutation or aliasing of a literal dispatch collection."""

    mutating_methods = {
        "add",
        "append",
        "clear",
        "discard",
        "extend",
        "insert",
        "pop",
        "remove",
        "reverse",
        "sort",
        "update",
    }
    copied_read_builtins = {"frozenset", "list", "set", "sorted", "tuple"}
    module_bound_names = _source_scope_bound_names(tree.body)

    def target_root_names(target: ast.AST) -> tuple[str, ...]:
        if isinstance(target, ast.Name):
            return (target.id,)
        if isinstance(target, (ast.Attribute, ast.Subscript)):
            return target_root_names(target.value)
        if isinstance(target, (ast.Tuple, ast.List)):
            return tuple(root for item in target.elts for root in target_root_names(item))
        return ()

    module_binding_targets = {
        id(target)
        for statement in _source_scope_nodes(tree.body)
        if isinstance(statement, (ast.Assign, ast.AnnAssign))
        for target in (
            statement.targets if isinstance(statement, ast.Assign) else [statement.target]
        )
        if isinstance(target, ast.Name) and target.id == name
    }

    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == name
            and node.func.attr in mutating_methods
        ):
            return False
        if isinstance(node, ast.AugAssign) and name in target_root_names(node.target):
            return False
        if isinstance(node, ast.Delete) and any(
            name in target_root_names(target) for target in node.targets
        ):
            return False
        if (
            isinstance(node, ast.Call)
            and any(isinstance(value, ast.Name) and value.id == name for value in ast.walk(node))
            and (
                not isinstance(node.func, ast.Name)
                or node.func.id not in copied_read_builtins
                or node.func.id in module_bound_names
                or node.keywords
                or len(node.args) != 1
            )
        ):
            # A known unshadowed builtin can read/consume this literal without
            # receiving an alias to its mutable storage. Arbitrary calls remain
            # an escape and therefore keep the collection unknown.
            return False
        if isinstance(node, ast.Assign):
            if any(
                isinstance(value, ast.Name) and value.id == name for value in ast.walk(node.value)
            ):
                return False
            if any(
                name in target_root_names(target)
                and not (isinstance(target, ast.Name) and id(target) in module_binding_targets)
                for target in node.targets
            ):
                return False
        if isinstance(node, ast.AnnAssign):
            if node.value is not None and any(
                isinstance(value, ast.Name) and value.id == name for value in ast.walk(node.value)
            ):
                return False
            if name in target_root_names(node.target) and not (
                isinstance(node.target, ast.Name) and id(node.target) in module_binding_targets
            ):
                return False
    return True


def _literal_import_helper_bindings(
    tree: ast.Module,
    function: ast.FunctionDef | ast.AsyncFunctionDef,
) -> tuple[frozenset[str], frozenset[str]]:
    """Find direct importlib aliases without possible scope rebinding."""

    functions: set[str] = set()
    modules: set[str] = set()
    imported_bindings: dict[str, set[str]] = {}
    module_scope = tuple(_source_scope_nodes(tree.body))
    if any(
        isinstance(node, ast.ImportFrom) and any(alias.name == "*" for alias in node.names)
        for node in module_scope
    ):
        return frozenset(), frozenset()
    for node in module_scope:
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                bound_name = alias.asname or alias.name
                imported_bindings.setdefault(bound_name, set()).add(
                    f"{node.module}.{alias.name}" if node.module else alias.name
                )
        elif isinstance(node, ast.Import):
            for alias in node.names:
                bound_name = alias.asname or alias.name.partition(".")[0]
                imported_bindings.setdefault(bound_name, set()).add(
                    alias.name if alias.asname else alias.name.partition(".")[0]
                )

    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module == "importlib":
            functions.update(
                alias.asname or alias.name for alias in node.names if alias.name == "import_module"
            )
        elif isinstance(node, ast.Import):
            modules.update(
                alias.asname or "importlib"
                for alias in node.names
                if alias.name == "importlib" or alias.name.startswith("importlib.")
                if not alias.asname or alias.name == "importlib"
            )

    # Imports are inventoried separately above; every other binding form in
    # this executable scope can replace the imported helper at runtime.
    module_stores = _source_scope_bound_names(tree.body, include_imports=False)
    local_stores = _source_scope_bound_names(function.body, include_imports=False)
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
        expected_binding = "importlib.import_module" if alias in functions else "importlib"
        if imported_bindings.get(alias) != {expected_binding} or alias in shadows:
            functions.discard(alias)
            modules.discard(alias)
    return frozenset(functions), frozenset(modules)


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


_UNKNOWN_SOURCE_LITERAL = object()
_STATIC_FACADE_UNKNOWN = _UNKNOWN_SOURCE_LITERAL


def _literal_facade_mapping_names(tree: ast.Module) -> frozenset[str]:
    """Return map names from the canonical bounded provider analysis."""

    return _literal_module_getattr_provider_index(tree).mapping_names


def _literal_facade_mapping_values(
    tree: ast.Module,
    mapping_names: frozenset[str],
) -> tuple[dict[str, dict[str, object]], bool]:
    """Compatibility facade over the canonical source-map effect transfer."""

    maps, invalid = _static_facade_mapping_values(tree, mapping_names)
    return maps, not invalid and len(maps) == len(mapping_names)


def _literal_facade_provider_target(key: str, value: object) -> tuple[str, str] | None:
    """Decode the supported module or ``(module, symbol)`` source-map value."""

    if type(value) is str:
        return value, key
    if (
        type(value) in {tuple, list}
        and len(value) == 2
        and all(type(item) is str for item in value)
    ):
        return value[0], value[1]
    return None


def _literal_source_expression(
    node: ast.AST,
    values: Mapping[str, object],
    *,
    depth: int = 0,
) -> object:
    """Evaluate the inert expression fragment used to construct facade maps."""

    if depth > 80:
        return _UNKNOWN_SOURCE_LITERAL
    if not any(isinstance(child, ast.Dict) for child in ast.walk(node)):
        try:
            return ast.literal_eval(node)
        except (ValueError, TypeError, SyntaxError, MemoryError):
            pass
    if isinstance(node, ast.Name):
        return values.get(node.id, _UNKNOWN_SOURCE_LITERAL)
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        items: list[object] = []
        for element in node.elts:
            value_node = element.value if isinstance(element, ast.Starred) else element
            value = _literal_source_expression(value_node, values, depth=depth + 1)
            if value is _UNKNOWN_SOURCE_LITERAL:
                return _UNKNOWN_SOURCE_LITERAL
            if isinstance(element, ast.Starred):
                if type(value) not in {list, tuple, set, frozenset} or len(value) > 10000:
                    return _UNKNOWN_SOURCE_LITERAL
                items.extend(value)
            else:
                items.append(value)
        if len(items) > 10000:
            return _UNKNOWN_SOURCE_LITERAL
        if isinstance(node, ast.List):
            return items
        if isinstance(node, ast.Tuple):
            return tuple(items)
        try:
            return set(items)
        except (TypeError, ValueError):
            return _UNKNOWN_SOURCE_LITERAL
    if isinstance(node, ast.Dict):
        result: dict[object, object] = {}
        for key_node, value_node in zip(node.keys, node.values, strict=True):
            value = _literal_source_expression(value_node, values, depth=depth + 1)
            if value is _UNKNOWN_SOURCE_LITERAL:
                return _UNKNOWN_SOURCE_LITERAL
            if key_node is None:
                if (
                    type(value) is not dict
                    or len(result) + len(value) > 10000
                    or any(key in result for key in value)
                ):
                    return _UNKNOWN_SOURCE_LITERAL
                result.update(value)
                continue
            key = _literal_source_expression(key_node, values, depth=depth + 1)
            if key is _UNKNOWN_SOURCE_LITERAL:
                return _UNKNOWN_SOURCE_LITERAL
            try:
                if key in result:
                    return _UNKNOWN_SOURCE_LITERAL
                result[key] = value
            except (TypeError, ValueError):
                return _UNKNOWN_SOURCE_LITERAL
            if len(result) > 10000:
                return _UNKNOWN_SOURCE_LITERAL
        return result
    if isinstance(node, ast.JoinedStr):
        parts: list[str] = []
        for value in node.values:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                parts.append(value.value)
                continue
            if not (
                isinstance(value, ast.FormattedValue)
                and value.conversion == -1
                and value.format_spec is None
            ):
                return _UNKNOWN_SOURCE_LITERAL
            formatted = _literal_source_expression(
                value.value,
                values,
                depth=depth + 1,
            )
            if type(formatted) not in {str, int, float, bool}:
                return _UNKNOWN_SOURCE_LITERAL
            parts.append(str(formatted))
        return "".join(parts)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = _literal_source_expression(node.left, values, depth=depth + 1)
        right = _literal_source_expression(node.right, values, depth=depth + 1)
        if isinstance(left, str) and isinstance(right, str):
            return left + right
        if isinstance(left, tuple) and isinstance(right, tuple):
            return (*left, *right)
        if isinstance(left, list) and isinstance(right, list):
            return [*left, *right]
    if isinstance(node, ast.Subscript):
        value = _literal_source_expression(node.value, values, depth=depth + 1)
        key = _literal_source_expression(node.slice, values, depth=depth + 1)
        if isinstance(value, dict) and key is not _UNKNOWN_SOURCE_LITERAL:
            return value.get(key, _UNKNOWN_SOURCE_LITERAL)
        if isinstance(value, (tuple, list)) and isinstance(key, int):
            try:
                return value[key]
            except IndexError:
                return _UNKNOWN_SOURCE_LITERAL
    if isinstance(node, ast.IfExp):
        condition = _literal_source_expression(node.test, values, depth=depth + 1)
        if type(condition) is bool:
            return _literal_source_expression(
                node.body if condition else node.orelse,
                values,
                depth=depth + 1,
            )
        return _UNKNOWN_SOURCE_LITERAL
    if isinstance(node, ast.Compare) and len(node.ops) == 1 and len(node.comparators) == 1:
        left = _literal_source_expression(node.left, values, depth=depth + 1)
        right = _literal_source_expression(node.comparators[0], values, depth=depth + 1)
        if left is _UNKNOWN_SOURCE_LITERAL or right is _UNKNOWN_SOURCE_LITERAL:
            return _UNKNOWN_SOURCE_LITERAL
        try:
            if isinstance(node.ops[0], ast.Eq):
                return left == right
            if isinstance(node.ops[0], ast.In):
                return left in right
            if isinstance(node.ops[0], ast.NotIn):
                return left not in right
        except (TypeError, ValueError):
            return _UNKNOWN_SOURCE_LITERAL
    if isinstance(node, ast.DictComp):
        result: dict[object, object] = {}

        def bind_target(target: ast.AST, value: object, local: dict[str, object]) -> bool:
            if isinstance(target, ast.Name):
                local[target.id] = value
                return True
            if (
                isinstance(target, (ast.Tuple, ast.List))
                and isinstance(value, (tuple, list))
                and len(target.elts) == len(value)
            ):
                return all(
                    bind_target(item_target, item_value, local)
                    for item_target, item_value in zip(target.elts, value, strict=True)
                )
            return False

        remaining_steps = [10000]

        def visit(index: int, local: dict[str, object]) -> bool:
            if depth + index > 80 or index > len(node.generators):
                return False
            if index == len(node.generators):
                remaining_steps[0] -= 1
                if remaining_steps[0] < 0:
                    return False
                key = _literal_source_expression(node.key, local, depth=depth + 1)
                value = _literal_source_expression(node.value, local, depth=depth + 1)
                if key is _UNKNOWN_SOURCE_LITERAL or value is _UNKNOWN_SOURCE_LITERAL:
                    return False
                try:
                    result[key] = value
                except (TypeError, ValueError):
                    return False
                return len(result) <= 10000
            generator = node.generators[index]
            iterable = _literal_source_expression(generator.iter, local, depth=depth + 1)
            if type(iterable) not in {tuple, list, dict} or len(iterable) > 10000:
                return False
            for item in iterable:
                remaining_steps[0] -= 1
                if remaining_steps[0] < 0:
                    return False
                nested = dict(local)
                if not bind_target(generator.target, item, nested):
                    return False
                accepted = True
                for condition in generator.ifs:
                    condition_value = _literal_source_expression(
                        condition,
                        nested,
                        depth=depth + 1,
                    )
                    if type(condition_value) is not bool:
                        return False
                    if not condition_value:
                        accepted = False
                        break
                if accepted and not visit(index + 1, nested):
                    return False
            return True

        if not node.generators or len(node.generators) > 80 or not visit(0, dict(values)):
            return _UNKNOWN_SOURCE_LITERAL
        return result
    return _UNKNOWN_SOURCE_LITERAL


def _literal_source_iteration(
    node: ast.AST, values: Mapping[str, object]
) -> tuple[object, ...] | None:
    """Return a finite ordered literal iteration source without executing code."""

    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "items"
        and not node.args
        and not node.keywords
    ):
        source = _literal_source_expression(node.func.value, values)
        if isinstance(source, dict) and len(source) <= 10000:
            return tuple(source.items())
        return None
    source = _literal_source_expression(node, values)
    if isinstance(source, (tuple, list)) and len(source) <= 10000:
        return tuple(source)
    return None


def _source_target_names(target: ast.AST) -> tuple[str, ...]:
    """Return names bound by one assignment target."""

    if isinstance(target, ast.Name):
        return (target.id,)
    if isinstance(target, (ast.Tuple, ast.List)):
        return tuple(name for item in target.elts for name in _source_target_names(item))
    return ()


def _static_facade_mapping_values(
    tree: ast.Module,
    mapping_names: frozenset[str],
    *,
    external_mappings: Mapping[str, dict[str, object]] | None = None,
    scan_deferred_mapping_effects: bool = True,
    separate_namespace_effects: bool = False,
) -> tuple[dict[str, dict[str, object]], frozenset[str]]:
    """Recompute bounded module-scope literal maps with expression-effect transfer.

    ``scan_deferred_mapping_effects`` keeps the full function-body escape scan for
    provider maps. Source-owner projection can keep unknown module effects separate
    from an exact selected map, provided the runtime consumer later reconciles the
    live map and selected object references to this source projection.
    """

    values: dict[str, object] = {}
    invalid: set[str] = set()
    supported_mapping_stores: set[int] = set()
    type_checking_names: set[str] = set()
    typing_module_names: set[str] = set()
    future_annotations = any(
        isinstance(statement, ast.ImportFrom)
        and statement.module == "__future__"
        and any(alias.name == "annotations" for alias in statement.names)
        for statement in tree.body
    )
    lazy_annotations = future_annotations or sys.version_info[:2] == (3, 14)
    module_bound_names = _source_scope_bound_names(tree.body)

    def target_root_names(target: ast.AST) -> tuple[str, ...]:
        if isinstance(target, ast.Name):
            return (target.id,)
        if isinstance(target, (ast.Tuple, ast.List)):
            return tuple(name for item in target.elts for name in target_root_names(item))
        if isinstance(target, (ast.Subscript, ast.Attribute)):
            return target_root_names(target.value)
        return ()

    def clear_import_identity(name: str) -> None:
        type_checking_names.discard(name)
        typing_module_names.discard(name)

    def assign_target(target: ast.AST, value: object) -> bool:
        if isinstance(target, ast.Name):
            clear_import_identity(target.id)
            values[target.id] = value
            if target.id in mapping_names:
                supported_mapping_stores.add(id(target))
                if type(value) is not dict:
                    invalid.add(target.id)
            return True
        if isinstance(target, ast.Subscript) and isinstance(target.value, ast.Name):
            mapping_name = target.value.id
            current = values.get(mapping_name, _UNKNOWN_SOURCE_LITERAL)
            key = _literal_source_expression(target.slice, values)
            if (
                type(current) is dict
                and key is not _UNKNOWN_SOURCE_LITERAL
                and value is not _UNKNOWN_SOURCE_LITERAL
            ):
                try:
                    current[key] = value
                except (TypeError, ValueError):
                    invalid.add(mapping_name)
                    return False
                if mapping_name in mapping_names:
                    supported_mapping_stores.add(id(target))
                return True
            if isinstance(current, (dict, list, set)):
                # Nested mutable containers are outside the finite map-builder grammar;
                # a stored map may be reachable through them.
                invalid.update(mapping_names)
            poison_name(mapping_name)
            return False
        if isinstance(target, ast.Subscript):
            names = target_root_names(target.value)
            for name in names:
                poison_name(name)
            invalid.update(mapping_names)
            return False
        if isinstance(target, (ast.Tuple, ast.List)) and isinstance(value, (tuple, list)):
            if len(target.elts) != len(value):
                return False
            return all(
                assign_target(item, part) for item, part in zip(target.elts, value, strict=True)
            )
        invalid.update(mapping_names)
        return False

    def written_names(node: ast.AST) -> set[str]:
        """Return names whose current values may change in one bounded statement."""

        names: set[str] = set()
        for child in _source_scope_nodes((node,)):
            if isinstance(child, ast.Name) and isinstance(child.ctx, (ast.Store, ast.Del)):
                names.add(child.id)
            elif isinstance(child, ast.Subscript) and isinstance(child.ctx, (ast.Store, ast.Del)):
                names.update(target_root_names(child.value))
            elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                names.add(child.name)
            elif isinstance(child, ast.Import):
                names.update(alias.asname or alias.name.partition(".")[0] for alias in child.names)
            elif isinstance(child, ast.ImportFrom):
                names.update(
                    alias.asname or alias.name for alias in child.names if alias.name != "*"
                )
            elif (
                isinstance(child, ast.Call)
                and isinstance(child.func, ast.Attribute)
                and child.func.attr not in {"items", "keys", "values", "get", "copy"}
                and isinstance(child.func.value, ast.Name)
            ):
                # Unknown receiver methods may mutate the receiver; only the small
                # mapping-read surface used by the literal grammar is treated as pure.
                names.add(child.func.value.id)
        return names

    def poison_name(name: str) -> None:
        """Invalidate a written name and aliases to its mutable literal value."""

        clear_import_identity(name)
        value = values.get(name, _UNKNOWN_SOURCE_LITERAL)
        affected = {name}
        if isinstance(value, (dict, list, set)):
            affected.update(alias for alias, candidate in values.items() if candidate is value)
        for affected_name in affected:
            values[affected_name] = _UNKNOWN_SOURCE_LITERAL
            if affected_name in mapping_names:
                invalid.add(affected_name)

    def poison_all_maps() -> None:
        """Track unknown module effects separately from a selected source map."""

        namespace_guard = "__polisyos_static_namespace_effect_guard__"
        if separate_namespace_effects and namespace_guard in mapping_names:
            invalid.add(namespace_guard)
        else:
            invalid.update(mapping_names)

    def map_reaches_object(value: object, seen: set[int] | None = None) -> bool:
        """Return whether a mutable object is reachable from a tracked provider map."""

        if seen is None:
            seen = set()
        if id(value) in seen:
            return False
        seen.add(id(value))
        if any(values.get(name) is value for name in mapping_names):
            return True
        if type(value) is dict:
            return any(
                map_reaches_object(key, seen) or map_reaches_object(item, seen)
                for key, item in value.items()
            )
        if type(value) in {list, tuple, set, frozenset}:
            return any(map_reaches_object(item, seen) for item in value)
        return False

    def transfer_exact_call(call: ast.Call) -> bool:
        """Apply one call only when callee/receiver identity and arguments are proven."""

        function = call.func
        if (
            isinstance(function, ast.Name)
            and function.id == "frozenset"
            and "frozenset" not in module_bound_names
            and len(call.args) == 1
            and not call.keywords
        ):
            source = _literal_source_expression(call.args[0], values)
            return type(source) in {set, frozenset, tuple, list} and len(source) <= 10000

        if not isinstance(function, ast.Attribute) or not isinstance(function.value, ast.Name):
            return False
        receiver_name = function.value.id
        receiver = values.get(receiver_name, _UNKNOWN_SOURCE_LITERAL)
        if receiver is _UNKNOWN_SOURCE_LITERAL:
            return False

        if (
            function.attr == "items"
            and type(receiver) is dict
            and not call.args
            and not call.keywords
        ):
            return True

        if (
            function.attr == "update"
            and type(receiver) is dict
            and len(call.args) == 1
            and not call.keywords
        ):
            update = _literal_source_expression(call.args[0], values)
            if type(update) is not dict or len(update) > 10000:
                return False
            if any(name in invalid and values.get(name) is receiver for name in mapping_names):
                return False
            receiver.update(update)
            for name in mapping_names:
                if values.get(name) is receiver:
                    supported_mapping_stores.add(id(call))
            return True

        if (
            function.attr == "extend"
            and type(receiver) is list
            and len(call.args) == 1
            and not call.keywords
            and not map_reaches_object(receiver)
        ):
            extension = _literal_source_expression(call.args[0], values)
            if type(extension) not in {list, tuple} or len(extension) > 10000:
                return False
            receiver.extend(extension)
            return True
        return False

    def inspect_runtime_expression(node: ast.AST) -> None:
        """Transfer effects of expressions evaluated by module initialization."""

        if isinstance(node, ast.Lambda):
            for default in (*node.args.defaults, *node.args.kw_defaults):
                if default is not None:
                    inspect_runtime_expression(default)
            return
        if isinstance(node, ast.DictComp):
            # A pure finite dict comprehension is admitted only when the exact
            # literal evaluator resolves every iterable, filter, key, and value.
            if type(_literal_source_expression(node, values)) is not dict:
                poison_all_maps()
            return
        if isinstance(node, (ast.ListComp, ast.SetComp, ast.GeneratorExp)):
            # These comprehension forms remain outside the finite map grammar.
            poison_all_maps()
            return
        if isinstance(node, ast.NamedExpr):
            inspect_runtime_expression(node.value)
            poison_name(node.target.id) if isinstance(node.target, ast.Name) else None
            poison_all_maps()
            return
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute):
                inspect_runtime_expression(node.func.value)
            else:
                inspect_runtime_expression(node.func)
            for argument in node.args:
                inspect_runtime_expression(argument)
            for keyword in node.keywords:
                inspect_runtime_expression(keyword.value)
            if not transfer_exact_call(node):
                poison_unsupported_effect(node)
            return
        if isinstance(node, ast.Attribute):
            inspect_runtime_expression(node.value)
            # A free attribute read can invoke module/object lookup behavior. The
            # bounded grammar only permits attributes as part of a proven exact call.
            poison_all_maps()
            return
        if isinstance(node, ast.Subscript):
            inspect_runtime_expression(node.value)
            inspect_runtime_expression(node.slice)
            if _literal_source_expression(node, values) is _UNKNOWN_SOURCE_LITERAL:
                poison_all_maps()
            return
        if isinstance(node, (ast.BinOp, ast.UnaryOp, ast.Compare, ast.BoolOp, ast.IfExp)):
            for child in ast.iter_child_nodes(node):
                if isinstance(child, ast.expr):
                    inspect_runtime_expression(child)
            if _literal_source_expression(node, values) is _UNKNOWN_SOURCE_LITERAL:
                poison_all_maps()
            return
        if isinstance(node, ast.Dict):
            for key, value in zip(node.keys, node.values, strict=True):
                if key is None:
                    poison_all_maps()
                else:
                    inspect_runtime_expression(key)
                inspect_runtime_expression(value)
            return
        if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
            for item in node.elts:
                inspect_runtime_expression(item)
            if (
                isinstance(node, ast.Set)
                and _literal_source_expression(node, values) is _UNKNOWN_SOURCE_LITERAL
            ):
                poison_all_maps()
            return
        if isinstance(node, ast.JoinedStr):
            for item in node.values:
                if isinstance(item, ast.FormattedValue):
                    inspect_runtime_expression(item.value)
                    if item.format_spec is not None:
                        inspect_runtime_expression(item.format_spec)
                else:
                    inspect_runtime_expression(item)
            if _literal_source_expression(node, values) is _UNKNOWN_SOURCE_LITERAL:
                poison_all_maps()
            return
        if isinstance(node, ast.FormattedValue):
            inspect_runtime_expression(node.value)
            if node.format_spec is not None:
                inspect_runtime_expression(node.format_spec)
            if _literal_source_expression(node, values) is _UNKNOWN_SOURCE_LITERAL:
                poison_all_maps()
            return
        if isinstance(node, ast.Starred):
            inspect_runtime_expression(node.value)
            value = _literal_source_expression(node.value, values)
            if type(value) not in {tuple, list, set, frozenset}:
                poison_all_maps()
            return
        if isinstance(node, ast.expr):
            if isinstance(node, (ast.Constant, ast.Name)):
                return
            poison_all_maps()

    def inspect_target_effects(target: ast.AST) -> None:
        """Inspect Python-evaluated receiver/index expressions in a store target."""

        if isinstance(target, (ast.Tuple, ast.List)):
            for item in target.elts:
                inspect_target_effects(item)
        elif isinstance(target, ast.Subscript):
            inspect_runtime_expression(target.value)
            inspect_runtime_expression(target.slice)
        elif isinstance(target, ast.Attribute):
            inspect_runtime_expression(target.value)
            poison_all_maps()

    def definition_time_expressions(node: ast.AST) -> tuple[ast.expr, ...]:
        """Return decorator/default expressions executed while a definition is made."""

        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            arguments = node.args
            eager = [*node.decorator_list, *arguments.defaults]
            eager.extend(default for default in arguments.kw_defaults if default is not None)
            if not lazy_annotations:
                eager.extend(
                    annotation
                    for argument in (
                        *arguments.posonlyargs,
                        *arguments.args,
                        *arguments.kwonlyargs,
                    )
                    if (annotation := argument.annotation) is not None
                )
                if arguments.vararg is not None and arguments.vararg.annotation is not None:
                    eager.append(arguments.vararg.annotation)
                if arguments.kwarg is not None and arguments.kwarg.annotation is not None:
                    eager.append(arguments.kwarg.annotation)
                if node.returns is not None:
                    eager.append(node.returns)
            return tuple(eager)
        if isinstance(node, ast.Lambda):
            return tuple(
                expression
                for expression in (*node.args.defaults, *node.args.kw_defaults)
                if expression is not None
            )
        return ()

    def poison_unsupported_effect(node: ast.AST) -> None:
        """Fail closed when unmodeled execution can affect module-level map state."""

        scoped_nodes = tuple(_source_scope_nodes((node,)))
        for name in written_names(node):
            poison_name(name)
        for child in scoped_nodes:
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                for expression in definition_time_expressions(child):
                    inspect_runtime_expression(expression)
            elif isinstance(child, ast.ClassDef):
                # Class bodies execute immediately; no class-scope transfer is modeled.
                poison_all_maps()
        # An unknown branch may create an alias to any mutable literal read by an
        # assignment, then mutate that alias later. Poison the source object too so a
        # stale original name cannot still feed a provider map.
        for child in scoped_nodes:
            if (
                isinstance(child, (ast.Assign, ast.AnnAssign, ast.NamedExpr))
                and child.value is not None
            ):
                for value_node in _source_scope_nodes((child.value,)):
                    if (
                        isinstance(value_node, ast.Name)
                        and isinstance(value_node.ctx, ast.Load)
                        and isinstance(values.get(value_node.id), (dict, list, set))
                    ):
                        poison_name(value_node.id)
        if any(
            isinstance(child, ast.Subscript)
            and isinstance(child.ctx, (ast.Store, ast.Del))
            and not isinstance(child.value, ast.Name)
            for child in scoped_nodes
        ) or any(
            isinstance(child, ast.Attribute) and isinstance(child.ctx, (ast.Store, ast.Del))
            for child in scoped_nodes
        ):
            poison_all_maps()
        if any(isinstance(child, ast.Call) for child in scoped_nodes):
            # An opaque import-time call may mutate globals or a mutable input through an
            # alias. The finite evaluator cannot prove that effect absent, so no derived
            # provider map from this module remains authoritative.
            poison_all_maps()

    def bind_import(statement: ast.Import | ast.ImportFrom) -> None:
        if isinstance(statement, ast.Import):
            for alias in statement.names:
                bound = alias.asname or alias.name.partition(".")[0]
                clear_import_identity(bound)
                values[bound] = _UNKNOWN_SOURCE_LITERAL
                imported = alias.name if alias.asname else alias.name.partition(".")[0]
                if imported == "typing":
                    typing_module_names.add(bound)
        else:
            for alias in statement.names:
                bound = alias.asname or alias.name
                clear_import_identity(bound)
                if alias.name == "*":
                    poison_all_maps()
                    continue
                if (
                    statement.module in {"typing", "typing_extensions"}
                    and alias.name == "TYPE_CHECKING"
                ):
                    type_checking_names.add(bound)
                    values[bound] = False
                else:
                    imported_mapping = (external_mappings or {}).get(bound)
                    values[bound] = (
                        dict(imported_mapping)
                        if isinstance(statement, ast.ImportFrom)
                        and type(imported_mapping) is dict
                        and alias.name != "*"
                        else _UNKNOWN_SOURCE_LITERAL
                    )

    def execute(statements: Iterable[ast.stmt]) -> None:
        for statement in statements:
            if isinstance(statement, ast.Assign):
                inspect_runtime_expression(statement.value)
                value = _literal_source_expression(statement.value, values)
                for target in statement.targets:
                    inspect_target_effects(target)
                    if not assign_target(target, value):
                        for name in _source_target_names(target):
                            poison_name(name)
            elif isinstance(statement, ast.AnnAssign):
                if not lazy_annotations:
                    inspect_runtime_expression(statement.annotation)
                if statement.value is not None:
                    inspect_runtime_expression(statement.value)
                value = (
                    _literal_source_expression(statement.value, values)
                    if statement.value is not None
                    else _UNKNOWN_SOURCE_LITERAL
                )
                inspect_target_effects(statement.target)
                if not assign_target(statement.target, value):
                    for name in _source_target_names(statement.target):
                        poison_name(name)
            elif isinstance(statement, ast.For):
                inspect_runtime_expression(statement.iter)
                members = _literal_source_iteration(statement.iter, values)
                if members is None:
                    poison_unsupported_effect(statement)
                    poison_all_maps()
                    continue
                for member in members:
                    inspect_target_effects(statement.target)
                    assign_target(statement.target, member)
                    execute(statement.body)
                execute(statement.orelse)
            elif isinstance(statement, ast.Expr):
                inspect_runtime_expression(statement.value)
            elif isinstance(statement, ast.If):
                if (
                    isinstance(statement.test, ast.Name)
                    and statement.test.id in type_checking_names
                ) or (
                    isinstance(statement.test, ast.Attribute)
                    and statement.test.attr == "TYPE_CHECKING"
                    and isinstance(statement.test.value, ast.Name)
                    and statement.test.value.id in typing_module_names
                ):
                    condition: object = False
                else:
                    inspect_runtime_expression(statement.test)
                    condition = _literal_source_expression(statement.test, values)
                if type(condition) is bool:
                    execute(statement.body if condition else statement.orelse)
                else:
                    # An unknown truth test may execute user-defined __bool__, and an
                    # unknown branch may mutate any map or one of its aliases.
                    poison_unsupported_effect(statement)
                    poison_all_maps()
            elif isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if statement.decorator_list:
                    # Applying a decorator invokes arbitrary code after evaluating it.
                    for decorator in statement.decorator_list:
                        inspect_runtime_expression(decorator)
                    poison_all_maps()
                decorator_ids = {id(expression) for expression in statement.decorator_list}
                for expression in definition_time_expressions(statement):
                    if id(expression) not in decorator_ids:
                        inspect_runtime_expression(expression)
                values[statement.name] = _UNKNOWN_SOURCE_LITERAL
                clear_import_identity(statement.name)
                if statement.name in mapping_names:
                    invalid.add(statement.name)
            elif isinstance(statement, ast.ClassDef):
                for expression in (*statement.decorator_list, *statement.bases):
                    inspect_runtime_expression(expression)
                for keyword in statement.keywords:
                    inspect_runtime_expression(keyword.value)
                # Class body execution and metaclass hooks are outside this finite transfer.
                poison_all_maps()
                values[statement.name] = _UNKNOWN_SOURCE_LITERAL
                clear_import_identity(statement.name)
                if statement.name in mapping_names:
                    invalid.add(statement.name)
            elif isinstance(statement, (ast.Import, ast.ImportFrom)):
                bind_import(statement)
            elif isinstance(statement, ast.Delete):
                for target in statement.targets:
                    inspect_target_effects(target)
                    if isinstance(target, ast.Name):
                        poison_name(target.id)
                        if target.id in mapping_names:
                            invalid.add(target.id)
                    else:
                        poison_unsupported_effect(statement)
                        poison_all_maps()
            elif isinstance(statement, ast.AugAssign):
                inspect_target_effects(statement.target)
                inspect_runtime_expression(statement.value)
                poison_unsupported_effect(statement)
                poison_all_maps()
            else:
                poison_unsupported_effect(statement)
                poison_all_maps()

    execute(tree.body)

    if scan_deferred_mapping_effects:
        # A function can mutate a provider table after its initializer ran. Only
        # stores executed by the bounded module-scope interpreter count as proof.
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Name)
                and node.id in mapping_names
                and isinstance(node.ctx, (ast.Store, ast.Del))
            ):
                if id(node) not in supported_mapping_stores:
                    invalid.add(node.id)
            elif (
                isinstance(node, ast.Subscript)
                and isinstance(node.ctx, (ast.Store, ast.Del))
                and isinstance(node.value, ast.Name)
                and node.value.id in mapping_names
                and id(node) not in supported_mapping_stores
            ):
                invalid.add(node.value.id)
            elif isinstance(node, (ast.Assign, ast.AnnAssign)):
                value = node.value
                if isinstance(value, ast.Name) and value.id in mapping_names:
                    invalid.add(value.id)
            elif isinstance(node, ast.Call):
                for argument in (*node.args, *(keyword.value for keyword in node.keywords)):
                    if isinstance(argument, ast.Name) and argument.id in mapping_names:
                        invalid.add(argument.id)
                if (
                    isinstance(node.func, ast.Attribute)
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id in mapping_names
                    and (
                        node.func.attr not in {"items", "keys", "get", "update"}
                        or (node.func.attr == "update" and id(node) not in supported_mapping_stores)
                    )
                ):
                    invalid.add(node.func.value.id)

    result = {name: values[name] for name in mapping_names if type(values.get(name)) is dict}
    return result, frozenset(invalid)


_SOURCE_FACADE_NAMESPACE_EFFECT_GUARD = "__polisyos_static_namespace_effect_guard__"


def _source_declared_facade_mapping_values(
    tree: ast.Module,
    mapping_names: frozenset[str],
    *,
    external_mappings: Mapping[str, dict[str, object]] | None = None,
) -> tuple[dict[str, dict[str, object]], frozenset[str], bool]:
    """Project selected map values from source while separating unrelated init effects.

    These maps are declarations parsed from exact source bytes, not runtime evidence.
    Consumers must reconcile the loaded map and selected provider/importer references
    to this projection before accepting a source-owned binding.
    """

    watched_names = mapping_names | {
        _SOURCE_FACADE_NAMESPACE_EFFECT_GUARD,
        "__name__",
        "__package__",
    }
    maps, invalid = _static_facade_mapping_values(
        tree,
        watched_names,
        external_mappings=external_mappings,
        separate_namespace_effects=True,
    )
    selected_maps = {name: maps[name] for name in mapping_names if name in maps}
    invalid_maps = invalid & mapping_names
    namespace_effect_unknown = bool(
        invalid
        & {
            _SOURCE_FACADE_NAMESPACE_EFFECT_GUARD,
            "__name__",
            "__package__",
        }
    )
    return selected_maps, frozenset(invalid_maps), namespace_effect_unknown


def _source_imported_facade_mappings(
    repo_root: Path,
    module_name: str,
    tree: ast.Module,
    mapping_names: frozenset[str],
    *,
    directory_entries: dict[Path, frozenset[str]],
    source_index: _AuthorityImportClosureSourceIndex,
) -> tuple[dict[str, dict[str, object]], frozenset[str]]:
    """Resolve only unique direct imports of finite maps owned by repository source."""

    relative = _repository_module_source(
        repo_root, module_name, directory_entries=directory_entries
    )
    if relative is None:
        return {}, frozenset(mapping_names)
    package = module_name if relative.name == "__init__.py" else module_name.rpartition(".")[0]
    imported: dict[str, dict[str, object]] = {}
    invalid: set[str] = set()
    for local_name in mapping_names:
        sites = _module_scope_direct_binding_sites(tree, local_name)
        if not sites:
            continue
        if len(sites) != 1:
            invalid.add(local_name)
            continue
        binding_kind, statement, alias = sites[0]
        if (
            binding_kind != "import_from"
            or not isinstance(statement, ast.ImportFrom)
            or alias is None
            or alias.name == "*"
        ):
            continue
        base = _resolve_import_from_base(statement, package)
        if base is None:
            invalid.add(local_name)
            continue
        provider_path = _repository_module_source(
            repo_root, base, directory_entries=directory_entries
        )
        if provider_path is None:
            invalid.add(local_name)
            continue
        try:
            analysis = _active_integrity_analysis()
            provider_bytes = (
                analysis.source_bytes(repo_root / provider_path)
                if analysis is not None
                else (repo_root / provider_path).read_bytes()
            )
            provider_tree = source_index.parse(provider_bytes, filename=provider_path.as_posix())
        except (OSError, SyntaxError, ValueError):
            invalid.add(local_name)
            continue
        provider_sites = _module_scope_direct_binding_sites(provider_tree, alias.name)
        if len(provider_sites) != 1 or provider_sites[0][0] != "assignment":
            invalid.add(local_name)
            continue
        maps, invalid_maps, _namespace_effect_unknown = _source_declared_facade_mapping_values(
            provider_tree,
            frozenset({alias.name}),
        )
        provider_map = maps.get(alias.name)
        if alias.name in invalid_maps or type(provider_map) is not dict:
            invalid.add(local_name)
            continue
        try:
            _literal_facade_value_projection(provider_map)
        except (ConfidenceLedgerError, TypeError, ValueError):
            invalid.add(local_name)
            continue
        imported[local_name] = provider_map
    return imported, frozenset(invalid)


def _literal_module_getattr_mapping_names(tree: ast.Module) -> frozenset[str]:
    """Return module tables indexed by a top-level literal ``__getattr__`` hook."""

    names: set[str] = set()
    for statement in tree.body:
        if not (
            isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef))
            and statement.name == "__getattr__"
        ):
            continue
        for node in _source_scope_nodes(statement.body):
            if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name):
                names.add(node.value.id)
    return frozenset(names)


def _source_module_provider_index(
    repo_root: Path,
    module_name: str,
    tree: ast.Module,
    *,
    directory_entries: dict[Path, frozenset[str]],
    source_index: _AuthorityImportClosureSourceIndex,
) -> _LiteralModuleGetattrProviderIndex:
    """Index a facade using exact source-owned finite maps, including direct imports."""

    relative = _repository_module_source(
        repo_root,
        module_name,
        directory_entries=directory_entries,
    )
    mapping_names = _literal_module_getattr_mapping_names(tree)
    external_mappings: dict[str, dict[str, object]] = {}
    if mapping_names:
        external_mappings, _invalid_imports = _source_imported_facade_mappings(
            repo_root,
            module_name,
            tree,
            mapping_names,
            directory_entries=directory_entries,
            source_index=source_index,
        )
    return _literal_module_getattr_provider_index(
        tree,
        external_mappings=external_mappings,
        package_module_name=(
            module_name if relative is not None and relative.name == "__init__.py" else None
        ),
    )


def _literal_mapping_import_call(
    call: ast.Call,
    mapping_names: frozenset[str],
    imported_functions: frozenset[str],
    imported_modules: frozenset[str],
) -> str | None:
    """Return the table name used by a trusted importlib map lookup."""

    function = call.func
    imported_function = isinstance(function, ast.Name) and function.id in imported_functions
    imported_module_function = (
        isinstance(function, ast.Attribute)
        and function.attr == "import_module"
        and isinstance(function.value, ast.Name)
        and function.value.id in imported_modules
    )
    if not (imported_function or imported_module_function) or not call.args:
        return None
    target = call.args[0]
    referenced_maps = {
        child.value.id
        for child in ast.walk(target)
        if isinstance(child, ast.Subscript)
        and isinstance(child.value, ast.Name)
        and child.value.id in mapping_names
    }
    if len(referenced_maps) == 1:
        return next(iter(referenced_maps))
    if referenced_maps:
        return "*"
    return None


def _literal_module_getattr_mapping_providers(
    tree: ast.Module,
    function: ast.FunctionDef | ast.AsyncFunctionDef,
    parameter_name: str,
    mapping_names: frozenset[str],
    imported_functions: frozenset[str],
    imported_modules: frozenset[str],
    external_mappings: Mapping[str, dict[str, object]] | None = None,
    package_module_name: str | None = None,
) -> tuple[dict[str, set[str]], dict[str, set[str]], dict[str, set[str]], set[str], set[int]]:
    """Bind source-map exports through bounded, provenance-preserving getter flow."""

    scope = tuple(_source_scope_nodes(function.body))
    function_bound_names = _source_scope_bound_names(function.body)
    module_bound_names = _source_scope_bound_names(tree.body)
    builtin_getattr_unshadowed = _literal_builtin_name_unshadowed(tree, function, "getattr")
    builtin_globals_unshadowed = _literal_builtin_name_unshadowed(tree, function, "globals")

    def is_import_call(node: ast.AST) -> bool:
        if not isinstance(node, ast.Call):
            return False
        callee = node.func
        if isinstance(callee, ast.Name):
            return callee.id in imported_functions and callee.id not in function_bound_names
        return bool(
            isinstance(callee, ast.Attribute)
            and callee.attr == "import_module"
            and isinstance(callee.value, ast.Name)
            and callee.value.id in imported_modules
            and callee.value.id not in function_bound_names
        )

    referenced_maps = frozenset(
        node.value.id
        for node in scope
        if isinstance(node, ast.Subscript)
        and isinstance(node.value, ast.Name)
        and node.value.id in mapping_names
    )
    # Reuse the module-initializer effect transfer for both map-backed and
    # direct getters. The sentinel is watched by the same monotone transfer so
    # an opaque executed initializer cannot silently rebind import aliases or
    # the implicit package namespace used by a relative import.
    values_by_map, invalid_maps, namespace_effect_unknown = _source_declared_facade_mapping_values(
        tree,
        mapping_names,
        external_mappings=external_mappings,
    )
    tables: dict[str, dict[str, object]] = {}
    invalid: set[str] = set()
    # Unknown package effects do not poison every selected export. Routes that
    # actually depend on implicit package context remain guarded below.
    for mapping_name in referenced_maps:
        table = values_by_map.get(mapping_name)
        if (
            mapping_name in function_bound_names
            or mapping_name in invalid_maps
            or not isinstance(table, dict)
        ):
            invalid.add("*")
        else:
            tables[mapping_name] = table

    # Only unique, immutable source-owned string collections are used to decide
    # name-domain branches. Mutable or multiply-bound values stay unknown.
    module_constants: dict[str, frozenset[str]] = {}
    module_scope = tuple(_source_scope_nodes(tree.body))
    candidate_constants: dict[str, frozenset[str]] = {}
    mutable_candidate_constants: set[str] = set()
    for statement in tree.body:
        if isinstance(statement, ast.Assign) and len(statement.targets) == 1:
            target, expression = statement.targets[0], statement.value
        elif isinstance(statement, ast.AnnAssign):
            target, expression = statement.target, statement.value
        else:
            continue
        if not isinstance(target, ast.Name) or expression is None:
            continue
        values: object = _UNKNOWN_SOURCE_LITERAL
        try:
            literal = ast.literal_eval(expression)
        except (ValueError, TypeError, SyntaxError, MemoryError):
            literal = _UNKNOWN_SOURCE_LITERAL
        if type(literal) in {tuple, list, frozenset} and all(type(item) is str for item in literal):
            values = frozenset(literal)
        elif (
            isinstance(expression, ast.Call)
            and isinstance(expression.func, ast.Name)
            and expression.func.id == "frozenset"
            and expression.func.id not in module_bound_names
            and len(expression.args) == 1
            and not expression.keywords
        ):
            try:
                frozen_input = ast.literal_eval(expression.args[0])
            except (ValueError, TypeError, SyntaxError, MemoryError):
                frozen_input = _UNKNOWN_SOURCE_LITERAL
            if isinstance(frozen_input, (tuple, list, set, frozenset)) and all(
                type(item) is str for item in frozen_input
            ):
                values = frozenset(frozen_input)
        if isinstance(values, frozenset):
            candidate_constants[target.id] = values
            if type(literal) is list:
                mutable_candidate_constants.add(target.id)
            else:
                mutable_candidate_constants.discard(target.id)
    for name, values in candidate_constants.items():
        stores = tuple(
            node
            for node in module_scope
            if isinstance(node, ast.Name)
            and node.id == name
            and isinstance(node.ctx, (ast.Store, ast.Del))
        )
        if len(stores) == 1 and (
            name not in mutable_candidate_constants
            or _literal_collection_is_source_stable(tree, name)
        ):
            module_constants[name] = values

    map_collection_tag = object()
    map_value_tag = object()
    map_component_tag = object()
    module_tag = object()
    attribute_tag = object()
    relative_child_tag = object()
    absolute_child_tag = object()
    providers: dict[str, set[str]] = {}
    members: dict[str, set[str]] = {}
    module_providers: dict[str, set[str]] = {}
    handled_getattrs: set[int] = set()
    handled_imports: set[int] = set()

    def is_tagged(value: object, tag: object, length: int) -> bool:
        return isinstance(value, tuple) and len(value) == length and value[0] is tag

    def module_import_result(
        node: ast.Call,
        selected_map: str | None,
        selected_export: object,
        module_name: object,
        symbol_name: str,
        export_name: str,
    ) -> object:
        """Bind one exact absolute or explicitly package-relative import target."""

        if (
            type(module_name) is not str
            or not module_name
            or selected_export != export_name
            or (selected_map is not None and type(selected_map) is not str)
        ):
            return _UNKNOWN_SOURCE_LITERAL
        if module_name.startswith("."):
            if not (
                len(node.args) == 2
                and isinstance(node.args[1], ast.Name)
                and node.args[1].id == "__name__"
                and "__name__" not in module_bound_names
                and "__package__" not in module_bound_names
                and "__name__" not in function_bound_names
                and "__package__" not in function_bound_names
                and not namespace_effect_unknown
            ):
                return _UNKNOWN_SOURCE_LITERAL
        elif len(node.args) != 1:
            return _UNKNOWN_SOURCE_LITERAL
        handled_imports.add(id(node))
        return (module_tag, selected_map, selected_export, module_name, symbol_name)

    def mapped_import_target(
        node: ast.AST,
        environment: Mapping[str, object],
        export_name: str,
    ) -> object:
        """Resolve one map-backed or explicit literal import in this flow state."""

        if not isinstance(node, ast.Call) or not is_import_call(node) or node.keywords:
            return _UNKNOWN_SOURCE_LITERAL
        if len(node.args) not in {1, 2}:
            return _UNKNOWN_SOURCE_LITERAL
        selected = evaluate_expression(node.args[0], environment, export_name)
        raw_target: object
        selected_map: object
        selected_export: object
        if is_tagged(selected, map_value_tag, 4):
            selected_map, selected_export, raw_target = selected[1], selected[2], selected[3]
        elif is_tagged(selected, map_component_tag, 6):
            _tag, selected_map, selected_export, parent, index, _component = selected
            if type(index) is not int or index != 0 or type(parent) not in {tuple, list}:
                return _UNKNOWN_SOURCE_LITERAL
            raw_target = parent
        elif type(selected) is str and not selected.startswith("."):
            # An absolute source literal does not depend on package __name__ or
            # __package__. The loaded map and consumer identity are reconciled later.
            return module_import_result(
                node,
                None,
                export_name,
                selected,
                export_name,
                export_name,
            )
        elif (
            is_tagged(selected, relative_child_tag, 2)
            and selected[1] == export_name
            and len(node.args) == 1
            and not namespace_effect_unknown
            and "__name__" not in module_bound_names
            and "__name__" not in function_bound_names
        ):
            # A source-checked package-child template remains relative until the
            # owner resolver binds it to this package initializer.
            handled_imports.add(id(node))
            return (module_tag, None, export_name, f".{export_name}", export_name)
        elif (
            is_tagged(selected, absolute_child_tag, 3)
            and selected[2] == export_name
            and len(node.args) == 1
        ):
            package_name = selected[1]
            if type(package_name) is not str or not package_name:
                return _UNKNOWN_SOURCE_LITERAL
            handled_imports.add(id(node))
            return (
                module_tag,
                None,
                export_name,
                f"{package_name}.{export_name}",
                export_name,
            )
        elif type(selected) is str and selected.startswith("."):
            # The package binding is shared by direct literals and imported map
            # values, so both routes require the same stable explicit package.
            return module_import_result(
                node,
                None,
                export_name,
                selected,
                export_name,
                export_name,
            )
        else:
            return _UNKNOWN_SOURCE_LITERAL
        if type(raw_target) is str:
            module_name, symbol_name = raw_target, export_name
        elif (
            type(raw_target) in {tuple, list}
            and len(raw_target) == 2
            and all(type(item) is str for item in raw_target)
        ):
            module_name, symbol_name = raw_target
        else:
            return _UNKNOWN_SOURCE_LITERAL
        if type(selected_map) is not str:
            return _UNKNOWN_SOURCE_LITERAL
        return module_import_result(
            node,
            selected_map,
            selected_export,
            module_name,
            symbol_name,
            export_name,
        )

    def evaluate_expression(
        node: ast.AST,
        environment: Mapping[str, object],
        export_name: str,
    ) -> object:
        if isinstance(node, ast.Name):
            if node.id in environment:
                return environment[node.id]
            if node.id in values_by_map:
                return (map_collection_tag, node.id, values_by_map[node.id])
            if node.id in module_constants and node.id not in function_bound_names:
                return module_constants[node.id]
            return _UNKNOWN_SOURCE_LITERAL
        if isinstance(node, ast.JoinedStr):
            if (
                _literal_package_child_import_template(node, parameter_name)
                and "__name__" not in module_bound_names
                and "__name__" not in function_bound_names
                and not namespace_effect_unknown
            ):
                return (relative_child_tag, export_name)
            if _literal_absolute_package_child_import_template(
                node,
                parameter_name,
                package_module_name,
            ):
                return (absolute_child_tag, package_module_name, export_name)
            return _UNKNOWN_SOURCE_LITERAL
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
            values: list[object] = []
            for item in node.elts:
                value = evaluate_expression(item, environment, export_name)
                if value is _UNKNOWN_SOURCE_LITERAL:
                    return _UNKNOWN_SOURCE_LITERAL
                values.append(value)
            if isinstance(node, ast.Tuple):
                return tuple(values)
            if isinstance(node, ast.Set):
                try:
                    return set(values)
                except TypeError:
                    return _UNKNOWN_SOURCE_LITERAL
            return values
        if isinstance(node, ast.Subscript):
            container = evaluate_expression(node.value, environment, export_name)
            key = evaluate_expression(node.slice, environment, export_name)
            if is_tagged(container, map_collection_tag, 3):
                table = container[2]
                if type(key) is str and isinstance(table, dict) and key in table:
                    return (map_value_tag, container[1], key, table[key])
                return _UNKNOWN_SOURCE_LITERAL
            if is_tagged(container, map_value_tag, 4):
                target = container[3]
                if (
                    type(key) is int
                    and type(target) in {tuple, list}
                    and -len(target) <= key < len(target)
                ):
                    index = key if key >= 0 else len(target) + key
                    return (
                        map_component_tag,
                        container[1],
                        container[2],
                        target,
                        index,
                        target[index],
                    )
                return _UNKNOWN_SOURCE_LITERAL
            return _UNKNOWN_SOURCE_LITERAL
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            value = evaluate_expression(node.operand, environment, export_name)
            return not value if type(value) is bool else _UNKNOWN_SOURCE_LITERAL
        if isinstance(node, ast.BoolOp):
            values = [evaluate_expression(value, environment, export_name) for value in node.values]
            booleans = [value if type(value) is bool else None for value in values]
            if isinstance(node.op, ast.And):
                if False in booleans:
                    return False
                return True if all(value is True for value in booleans) else _UNKNOWN_SOURCE_LITERAL
            if isinstance(node.op, ast.Or):
                if True in booleans:
                    return True
                return (
                    False if all(value is False for value in booleans) else _UNKNOWN_SOURCE_LITERAL
                )
            return _UNKNOWN_SOURCE_LITERAL
        if isinstance(node, ast.Compare) and len(node.ops) == 1 and len(node.comparators) == 1:
            left = evaluate_expression(node.left, environment, export_name)
            right = evaluate_expression(node.comparators[0], environment, export_name)
            if left is _UNKNOWN_SOURCE_LITERAL or right is _UNKNOWN_SOURCE_LITERAL:
                return _UNKNOWN_SOURCE_LITERAL
            if is_tagged(right, map_collection_tag, 3):
                right = right[2]
            try:
                if isinstance(node.ops[0], ast.Eq):
                    return left == right
                if isinstance(node.ops[0], ast.NotEq):
                    return left != right
                if isinstance(node.ops[0], ast.In):
                    return left in right
                if isinstance(node.ops[0], ast.NotIn):
                    return left not in right
            except (TypeError, ValueError):
                return _UNKNOWN_SOURCE_LITERAL
            return _UNKNOWN_SOURCE_LITERAL
        if isinstance(node, ast.Call):
            module = mapped_import_target(node, environment, export_name)
            if is_tagged(module, module_tag, 5):
                return module
            if (
                builtin_getattr_unshadowed
                and isinstance(node.func, ast.Name)
                and node.func.id == "getattr"
                and node.func.id not in function_bound_names
                and len(node.args) == 2
                and not node.keywords
            ):
                owner = evaluate_expression(node.args[0], environment, export_name)
                selected_name = evaluate_expression(node.args[1], environment, export_name)
                if is_tagged(owner, module_tag, 5):
                    map_name, selected_export, module_name, symbol_name = owner[1:]
                    if (
                        is_tagged(selected_name, map_component_tag, 6)
                        and selected_name[1] == map_name
                        and selected_name[2] == selected_export
                        and selected_name[4] == 1
                        and selected_name[5] == symbol_name
                    ) or selected_name == symbol_name:
                        handled_getattrs.add(id(node))
                        return (attribute_tag, map_name, selected_export, module_name, symbol_name)
            return _UNKNOWN_SOURCE_LITERAL
        return _UNKNOWN_SOURCE_LITERAL

    def expression_has_unmodeled_effect(
        node: ast.AST,
        environment: Mapping[str, object],
        export_name: str,
    ) -> bool:
        """Refuse executed getter expressions outside the finite pure/call grammar."""

        if isinstance(node, ast.Lambda):
            return any(
                expression_has_unmodeled_effect(default, environment, export_name)
                for default in (*node.args.defaults, *node.args.kw_defaults)
                if default is not None
            )
        if isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
            return True
        if isinstance(node, ast.Call):
            if id(node) not in handled_imports and id(node) not in handled_getattrs:
                return True
            return any(
                expression_has_unmodeled_effect(argument, environment, export_name)
                for argument in node.args
            ) or any(
                expression_has_unmodeled_effect(keyword.value, environment, export_name)
                for keyword in node.keywords
            )
        if isinstance(node, ast.Attribute):
            # Attribute access can run a descriptor or module __getattr__; the
            # only admitted callable attribute is covered by its recognized Call.
            return True
        if isinstance(node, ast.Subscript):
            if evaluate_expression(node, environment, export_name) is _UNKNOWN_SOURCE_LITERAL:
                return True
            return expression_has_unmodeled_effect(
                node.value, environment, export_name
            ) or expression_has_unmodeled_effect(node.slice, environment, export_name)
        if isinstance(node, ast.JoinedStr):
            return evaluate_expression(node, environment, export_name) is _UNKNOWN_SOURCE_LITERAL
        if isinstance(node, ast.IfExp):
            if expression_has_unmodeled_effect(node.test, environment, export_name):
                return True
            condition = evaluate_expression(node.test, environment, export_name)
            if type(condition) is bool:
                selected = node.body if condition else node.orelse
                return expression_has_unmodeled_effect(selected, environment, export_name)
            return expression_has_unmodeled_effect(
                node.body, environment, export_name
            ) or expression_has_unmodeled_effect(node.orelse, environment, export_name)
        if isinstance(node, ast.BoolOp):
            for value_node in node.values:
                if expression_has_unmodeled_effect(value_node, environment, export_name):
                    return True
                value = evaluate_expression(value_node, environment, export_name)
                if type(value) is bool and (
                    (isinstance(node.op, ast.And) and not value)
                    or (isinstance(node.op, ast.Or) and value)
                ):
                    break
            return False
        if isinstance(node, (ast.BinOp, ast.UnaryOp, ast.Compare)):
            if evaluate_expression(node, environment, export_name) is _UNKNOWN_SOURCE_LITERAL:
                return True
            return any(
                expression_has_unmodeled_effect(child, environment, export_name)
                for child in ast.iter_child_nodes(node)
                if isinstance(child, ast.expr)
            )
        if isinstance(node, (ast.Constant, ast.Name)):
            return False
        if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
            value = evaluate_expression(node, environment, export_name)
            if value is _UNKNOWN_SOURCE_LITERAL:
                return True
            return any(
                expression_has_unmodeled_effect(child, environment, export_name)
                for child in node.elts
            )
        if isinstance(node, ast.Dict):
            # Dict construction is outside the getter value grammar; an unknown
            # mapping expansion can execute user-defined iteration and hashing.
            return True
        return True

    def is_name_global_write(target: ast.AST) -> bool:
        return bool(
            builtin_globals_unshadowed
            and isinstance(target, ast.Subscript)
            and isinstance(target.ctx, ast.Store)
            and isinstance(target.slice, ast.Name)
            and target.slice.id == parameter_name
            and isinstance(target.value, ast.Call)
            and isinstance(target.value.func, ast.Name)
            and target.value.func.id == "globals"
            and not target.value.args
            and not target.value.keywords
        )

    def bind_target(target: ast.AST, value: object, environment: dict[str, object]) -> bool:
        if isinstance(target, ast.Name):
            environment[target.id] = value
            return True
        if not isinstance(target, (ast.Tuple, ast.List)):
            return False
        if is_tagged(value, map_value_tag, 4):
            raw = value[3]
            if type(raw) not in {tuple, list} or len(raw) != len(target.elts):
                return False
            parts = tuple(
                (map_component_tag, value[1], value[2], raw, index, item)
                for index, item in enumerate(raw)
            )
        elif type(value) in {tuple, list} and len(value) == len(target.elts):
            parts = value
        else:
            return False
        return all(
            bind_target(child, part, environment)
            for child, part in zip(target.elts, parts, strict=True)
        )

    def execute_block(
        statements: Iterable[ast.stmt],
        states: list[tuple[dict[str, object], str, object]],
        export_name: str,
    ) -> list[tuple[dict[str, object], str, object]]:
        current = states
        for statement in statements:
            next_states: list[tuple[dict[str, object], str, object]] = []
            for environment, terminal, result in current:
                if terminal:
                    next_states.append((environment, terminal, result))
                    continue
                if isinstance(statement, ast.If):
                    if expression_has_unmodeled_effect(statement.test, environment, export_name):
                        next_states.append((environment, "unsupported", _UNKNOWN_SOURCE_LITERAL))
                        continue
                    condition = evaluate_expression(statement.test, environment, export_name)
                    if type(condition) is bool:
                        selected = statement.body if condition else statement.orelse
                        next_states.extend(
                            execute_block(
                                selected,
                                [(dict(environment), "", _UNKNOWN_SOURCE_LITERAL)],
                                export_name,
                            )
                        )
                    else:
                        next_states.extend(
                            execute_block(
                                statement.body,
                                [(dict(environment), "", _UNKNOWN_SOURCE_LITERAL)],
                                export_name,
                            )
                        )
                        if statement.orelse:
                            next_states.extend(
                                execute_block(
                                    statement.orelse,
                                    [(dict(environment), "", _UNKNOWN_SOURCE_LITERAL)],
                                    export_name,
                                )
                            )
                        else:
                            next_states.append((dict(environment), "", _UNKNOWN_SOURCE_LITERAL))
                    continue
                if isinstance(statement, ast.Return):
                    value = (
                        None
                        if statement.value is None
                        else evaluate_expression(statement.value, environment, export_name)
                    )
                    if statement.value is not None and expression_has_unmodeled_effect(
                        statement.value, environment, export_name
                    ):
                        next_states.append((environment, "unsupported", _UNKNOWN_SOURCE_LITERAL))
                        continue
                    next_states.append((environment, "return", value))
                    continue
                if isinstance(statement, ast.Raise):
                    next_states.append((environment, "raise", _UNKNOWN_SOURCE_LITERAL))
                    continue
                if isinstance(statement, ast.Pass):
                    next_states.append((environment, "", _UNKNOWN_SOURCE_LITERAL))
                    continue
                if (
                    isinstance(statement, ast.Expr)
                    and isinstance(statement.value, ast.Constant)
                    and type(statement.value.value) is str
                ):
                    next_states.append((environment, "", _UNKNOWN_SOURCE_LITERAL))
                    continue
                if isinstance(statement, (ast.Assign, ast.AnnAssign)):
                    if isinstance(statement, ast.AnnAssign) and statement.value is None:
                        next_states.append((environment, "", _UNKNOWN_SOURCE_LITERAL))
                        continue
                    value_node = statement.value
                    value = evaluate_expression(value_node, environment, export_name)
                    if expression_has_unmodeled_effect(value_node, environment, export_name):
                        next_states.append((environment, "unsupported", _UNKNOWN_SOURCE_LITERAL))
                        continue
                    targets = (
                        statement.targets
                        if isinstance(statement, ast.Assign)
                        else [statement.target]
                    )
                    if len(targets) != 1:
                        next_states.append((environment, "unsupported", _UNKNOWN_SOURCE_LITERAL))
                        continue
                    updated = dict(environment)
                    target = targets[0]
                    if bind_target(target, value, updated):
                        next_states.append((updated, "", _UNKNOWN_SOURCE_LITERAL))
                    elif is_name_global_write(target):
                        if not (
                            (is_tagged(value, attribute_tag, 5) or is_tagged(value, module_tag, 5))
                            and value[2] == export_name
                        ):
                            next_states.append(
                                (environment, "unsupported", _UNKNOWN_SOURCE_LITERAL)
                            )
                        else:
                            next_states.append((environment, "", _UNKNOWN_SOURCE_LITERAL))
                    else:
                        next_states.append((environment, "unsupported", _UNKNOWN_SOURCE_LITERAL))
                    continue
                next_states.append((environment, "unsupported", _UNKNOWN_SOURCE_LITERAL))
            current = next_states
            if len(current) > 256:
                return [({}, "unsupported", _UNKNOWN_SOURCE_LITERAL)]
        return current

    candidate_exports: set[str] = set()
    for _mapping_name, table in tables.items():
        for export_name in table:
            if type(export_name) is not str:
                invalid.add("*")
            else:
                candidate_exports.add(export_name)
    for statement in scope:
        if isinstance(statement, ast.If):
            candidate_exports.update(
                _literal_getattr_dispatch_names(statement.test, parameter_name)
            )
            for collection_name in _literal_getattr_dispatch_collection_names(
                statement.test, parameter_name
            ):
                candidate_exports.update(module_constants.get(collection_name, frozenset()))
    if not tables and not candidate_exports:
        return {}, {}, {}, invalid, set()
    if invalid:
        # Keep valid rows available for diagnostics, but a malformed candidate
        # map blocks the facade projection as a whole through the wildcard.
        pass

    for export_name in candidate_exports:
        states = execute_block(
            function.body,
            [({parameter_name: export_name}, "", _UNKNOWN_SOURCE_LITERAL)],
            export_name,
        )
        targets: set[tuple[str, str]] = set()
        module_targets: set[str] = set()
        accepted_return = False
        unsupported = False
        for _environment, terminal, result in states:
            if terminal == "raise":
                continue
            if terminal != "return":
                unsupported = True
                continue
            if (
                is_tagged(result, module_tag, 5)
                and result[2] == export_name
                and (result[1] is None or result[1] in tables)
                and type(result[3]) is str
                and bool(result[3])
            ):
                accepted_return = True
                module_targets.add(result[3])
            elif (
                is_tagged(result, attribute_tag, 5)
                and result[2] == export_name
                and (result[1] is None or result[1] in tables)
                and type(result[3]) is str
                and type(result[4]) is str
            ):
                accepted_return = True
                targets.add((result[3], result[4]))
            else:
                unsupported = True
        if (not accepted_return or unsupported) or (bool(targets) == bool(module_targets)):
            invalid.add(export_name)
            continue
        if module_targets:
            if len(module_targets) != 1:
                invalid.add(export_name)
                continue
            module_providers.setdefault(export_name, set()).update(module_targets)
            continue
        if len(targets) != 1:
            invalid.add(export_name)
            continue
        provider_name, symbol_name = next(iter(targets))
        providers.setdefault(export_name, set()).add(provider_name)
        members.setdefault(export_name, set()).add(symbol_name)

    if not builtin_getattr_unshadowed:
        invalid.add("*")

    return providers, members, module_providers, invalid, handled_getattrs


def _literal_module_getattr_direct_providers(
    tree: ast.Module,
    function: ast.FunctionDef | ast.AsyncFunctionDef,
    parameter_name: str,
    *,
    package_module_name: str | None,
) -> dict[str, tuple[str, str]] | None:
    """Resolve a complete finite-name ``import_module``/``getattr`` dispatch.

    This grammar admits only top-level branches whose literal name domain loads
    one source module and returns the attribute with the same selected name.
    Any other executable statement, rebinding, dynamic target, or branch shape
    leaves the whole dispatcher outside this source-only index.
    """

    if function.decorator_list:
        return None
    parameters = (
        *function.args.posonlyargs,
        *function.args.args,
        *function.args.kwonlyargs,
        *((function.args.vararg,) if function.args.vararg is not None else ()),
        *((function.args.kwarg,) if function.args.kwarg is not None else ()),
    )
    if not parameters or parameters[0].arg != parameter_name:
        return None
    if any(
        isinstance(node, ast.Name)
        and node.id == parameter_name
        and isinstance(node.ctx, (ast.Store, ast.Del))
        for node in _source_scope_nodes(function.body)
    ):
        return None
    imported_functions, imported_modules = _literal_import_helper_bindings(tree, function)
    if not imported_functions and not imported_modules:
        return None
    if not _literal_builtin_name_unshadowed(tree, function, "getattr"):
        return None

    statements = list(function.body)
    if (
        statements
        and isinstance(statements[0], ast.Expr)
        and isinstance(statements[0].value, ast.Constant)
        and type(statements[0].value.value) is str
    ):
        statements.pop(0)
    providers: dict[str, tuple[str, str]] = {}
    for statement in statements:
        if isinstance(statement, ast.Raise):
            exception = statement.exc
            if not (
                isinstance(exception, ast.Call)
                and isinstance(exception.func, ast.Name)
                and exception.func.id == "AttributeError"
                and _literal_builtin_name_unshadowed(tree, function, "AttributeError")
            ):
                return None
            continue
        if not isinstance(statement, ast.If) or statement.orelse:
            return None
        names = _literal_getattr_dispatch_names(statement.test, parameter_name)
        if not names or providers.keys() & names:
            return None
        branch = statement.body
        if len(branch) != 2:
            return None
        assignment, returned = branch
        if not (
            isinstance(assignment, ast.Assign)
            and len(assignment.targets) == 1
            and isinstance(assignment.targets[0], ast.Name)
            and isinstance(assignment.value, ast.Call)
            and not assignment.value.keywords
            and isinstance(returned, ast.Return)
            and isinstance(returned.value, ast.Call)
            and isinstance(returned.value.func, ast.Name)
            and returned.value.func.id == "getattr"
            and len(returned.value.args) == 2
            and not returned.value.keywords
            and isinstance(returned.value.args[0], ast.Name)
            and returned.value.args[0].id == assignment.targets[0].id
            and isinstance(returned.value.args[1], ast.Name)
            and returned.value.args[1].id == parameter_name
        ):
            return None
        load_call = assignment.value
        callee = load_call.func
        uses_import_module = bool(
            (isinstance(callee, ast.Name) and callee.id in imported_functions)
            or (
                isinstance(callee, ast.Attribute)
                and callee.attr == "import_module"
                and isinstance(callee.value, ast.Name)
                and callee.value.id in imported_modules
            )
        )
        if not uses_import_module or not load_call.args:
            return None
        try:
            target_module = ast.literal_eval(load_call.args[0])
        except (ValueError, TypeError, SyntaxError, MemoryError):
            return None
        if type(target_module) is not str or not target_module:
            return None
        if target_module.startswith("."):
            if (
                len(load_call.args) != 2
                or not isinstance(load_call.args[1], ast.Name)
                or load_call.args[1].id != "__name__"
                or package_module_name is None
            ):
                return None
            try:
                target_module = importlib.util.resolve_name(target_module, package_module_name)
            except (ImportError, TypeError, ValueError):
                return None
        elif len(load_call.args) != 1:
            return None
        for name in names:
            providers[name] = (target_module, name)
    return providers or None


def _literal_module_getattr_provider_index(
    tree: ast.Module,
    *,
    external_mappings: Mapping[str, dict[str, object]] | None = None,
    package_module_name: str | None = None,
) -> _LiteralModuleGetattrProviderIndex:
    """Index PEP 562 providers through one bounded source-value transfer."""

    mapping_names: set[str] = set()
    functions: list[ast.FunctionDef | ast.AsyncFunctionDef] = []
    for statement in tree.body:
        if (
            isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef))
            and statement.name == "__getattr__"
            and (statement.args.posonlyargs or statement.args.args)
        ):
            functions.append(statement)
    for function in functions:
        for node in _source_scope_nodes(function.body):
            if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name):
                mapping_names.add(node.value.id)

    providers: dict[str, set[str]] = {}
    provider_symbols: dict[str, set[str]] = {}
    module_providers: dict[str, set[str]] = {}
    invalid: set[str] = set()
    handled_getattrs: set[int] = set()
    # A PEP 562 function is a dispatch surface even when it has no source map.
    # Map rows, literal branches, and direct imports all flow through the same
    # stateful evaluator below; absence of a map never selects an alternate
    # scanner with a weaker namespace/effect model.
    generated_mapping_dispatch = any(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "__getattr__"
        for node in tree.body
    )
    if len(functions) > 1:
        invalid.add("*")

    for function in functions:
        parameters = (*function.args.posonlyargs, *function.args.args)
        if not parameters:
            invalid.add("*")
            continue
        parameter = parameters[0].arg
        imported_functions, imported_modules = _literal_import_helper_bindings(tree, function)
        direct_providers = _literal_module_getattr_direct_providers(
            tree,
            function,
            parameter,
            package_module_name=package_module_name,
        )
        if direct_providers is not None:
            for export_name, (provider_module, provider_symbol) in direct_providers.items():
                providers.setdefault(export_name, set()).add(provider_module)
                provider_symbols.setdefault(export_name, set()).add(provider_symbol)
            handled_getattrs.update(
                id(node)
                for node in _source_scope_nodes(function.body)
                if _dynamic_getattr_name(node, parameter)
            )
            continue
        mapped_providers, mapped_symbols, mapped_modules, mapped_invalid, mapped_getattrs = (
            _literal_module_getattr_mapping_providers(
                tree,
                function,
                parameter,
                frozenset(mapping_names),
                imported_functions,
                imported_modules,
                external_mappings,
                package_module_name,
            )
        )
        for export_name, modules in mapped_providers.items():
            providers.setdefault(export_name, set()).update(modules)
        for export_name, symbols in mapped_symbols.items():
            provider_symbols.setdefault(export_name, set()).update(symbols)
        for export_name, modules in mapped_modules.items():
            module_providers.setdefault(export_name, set()).update(modules)
        invalid.update(mapped_invalid)
        handled_getattrs.update(mapped_getattrs)

        dynamic_lookups = tuple(
            node
            for node in _source_scope_nodes(function.body)
            if _dynamic_getattr_name(node, parameter)
        )
        if any(id(node) not in handled_getattrs for node in dynamic_lookups):
            invalid.add("*")

    return _LiteralModuleGetattrProviderIndex(
        providers_by_export=types.MappingProxyType(
            {name: frozenset(modules) for name, modules in providers.items()}
        ),
        invalid_exports=frozenset(invalid),
        provider_symbols_by_export=types.MappingProxyType(
            {name: frozenset(symbols) for name, symbols in provider_symbols.items()}
        ),
        generated_mapping_dispatch=generated_mapping_dispatch,
        mapping_names=frozenset(mapping_names),
        module_providers_by_export=types.MappingProxyType(
            {name: frozenset(modules) for name, modules in module_providers.items()}
        ),
    )


def _literal_facade_value_matches(expected: object, observed: object) -> bool:
    """Compare source literals without Python's cross-type numeric equality."""

    if type(expected) is not type(observed):
        return False
    if type(expected) is dict:
        return bool(
            set(expected) == set(observed)
            and all(
                type(key) is str and _literal_facade_value_matches(expected[key], observed[key])
                for key in expected
            )
        )
    if type(expected) in {tuple, list}:
        return bool(
            len(expected) == len(observed)
            and all(
                _literal_facade_value_matches(left, right)
                for left, right in zip(expected, observed, strict=True)
            )
        )
    return expected == observed


def _literal_facade_value_projection(value: object) -> object:
    """Encode supported map values with their concrete container types."""

    if type(value) is dict:
        return {
            "$dict": {key: _literal_facade_value_projection(value[key]) for key in sorted(value)}
        }
    if type(value) is tuple:
        return {"$tuple": [_literal_facade_value_projection(item) for item in value]}
    if type(value) is list:
        return {"$list": [_literal_facade_value_projection(item) for item in value]}
    if value is None or type(value) in {str, int, float, bool}:
        return {"type": type(value).__name__, "value": value}
    raise ConfidenceLedgerError("canonical_loaded_runtime_mismatch")


def _source_facade_runtime_projection(
    repo_root: Path,
    closure: tuple[tuple[str, str], ...],
    *,
    runtime_binding_references: list[_FacadeRuntimeBindingReference] | None = None,
) -> tuple[str, tuple[tuple[str, str], ...]]:
    """Reconcile loaded lazy facade maps and selected exports to source owners.

    Source maps determine expected targets. The live mapping can only match that
    projection; it never contributes a closure edge. Cached and source-selected
    exports must be the exact object owned by the loaded, path-bound provider.
    """

    analysis = _active_integrity_analysis()
    owns_analysis = analysis is None
    token = None
    if analysis is None:
        analysis = _IntegrityAnalysisContext()
        token = _ACTIVE_INTEGRITY_ANALYSIS.set(analysis)
    try:
        closure_by_name = dict(closure)
        directory_entries: dict[Path, frozenset[str]] = {}
        source_index = _AuthorityImportClosureSourceIndex({}, {})
        source_rows: dict[
            str, tuple[ast.Module, _LiteralModuleGetattrProviderIndex, dict[str, dict[str, object]]]
        ] = {}
        runtime_scopes: dict[
            str,
            tuple[
                dict[int, tuple[str, str]],
                dict[str, ast.FunctionDef | ast.AsyncFunctionDef],
                dict[str, types.CodeType | None],
            ],
        ] = {}
        facade_rows: list[dict[str, object]] = []
        supplemental_modules: dict[str, str] = {}

        def resolve_source_target(
            facade_name: str,
            export_name: str,
            raw_target: object,
        ) -> tuple[str, str]:
            target = _literal_facade_provider_target(export_name, raw_target)
            if target is None:
                raise ConfidenceLedgerError(
                    "canonical_loaded_runtime_mismatch",
                    f"source facade owner is ambiguous: {facade_name}.{export_name}",
                )
            provider_name, attribute = target
            if provider_name.startswith("."):
                try:
                    provider_name = importlib.util.resolve_name(provider_name, facade_name)
                except (ImportError, TypeError, ValueError) as exc:
                    raise ConfidenceLedgerError(
                        "canonical_loaded_runtime_mismatch",
                        f"source facade owner is ambiguous: {facade_name}.{export_name}",
                    ) from exc
            return provider_name, attribute

        def qualified_projection_route(
            repo_root: Path,
            facade_name: str,
            export_name: str,
            *,
            directory_entries: dict[Path, frozenset[str]],
            source_index: _AuthorityImportClosureSourceIndex,
        ) -> tuple[str, str, str | None] | None:
            candidate = _source_module_import_route_candidate(
                repo_root,
                facade_name,
                export_name,
                directory_entries=directory_entries,
                source_index=source_index,
            )
            if not candidate.package_initializer_effect_unknown:
                return candidate.route
            if candidate.route is None:
                raise ConfidenceLedgerError(
                    "canonical_loaded_runtime_mismatch",
                    f"unreconciled package initializer effect: {facade_name}.{export_name}",
                )
            if candidate.binding_basis == "direct":
                route_kind, provider_name, _provider_symbol = candidate.route
                if route_kind in {"module", "symbol"} and provider_name != facade_name:
                    # A direct import from a separately source-owned provider is still
                    # only a candidate here; runtime identity checks below must bind the
                    # facade export and every selected importer to that exact provider.
                    return candidate.route
                raise ConfidenceLedgerError(
                    "canonical_loaded_runtime_mismatch",
                    f"unreconciled package initializer effect: {facade_name}.{export_name}",
                )
            if candidate.binding_basis != "literal_getattr":
                raise ConfidenceLedgerError(
                    "canonical_loaded_runtime_mismatch",
                    f"unreconciled package initializer effect: {facade_name}.{export_name}",
                )
            base_row = source_rows.get(facade_name)
            if base_row is None:
                raise ConfidenceLedgerError("canonical_loaded_runtime_mismatch")
            _base_tree, base_index, base_maps = base_row
            qualified_targets: set[tuple[str, str, str | None]] = set()
            module_exports = base_index.module_providers_by_export or {}
            for source_map in base_maps.values():
                if export_name not in source_map:
                    continue
                raw_target = source_map[export_name]
                if export_name in module_exports:
                    if type(raw_target) is not str:
                        raise ConfidenceLedgerError("canonical_loaded_runtime_mismatch")
                    target_module = _package_bound_module_provider_target(
                        raw_target,
                        module_name=facade_name,
                        module_source=Path(closure_by_name[facade_name]),
                        export_name=export_name,
                    )
                    qualified_targets.add(("module", target_module, None))
                else:
                    target_module, target_symbol = resolve_source_target(
                        facade_name,
                        export_name,
                        raw_target,
                    )
                    qualified_targets.add(("symbol", target_module, target_symbol))
            if qualified_targets != {candidate.route}:
                raise ConfidenceLedgerError(
                    "canonical_loaded_runtime_mismatch",
                    f"literal source map does not uniquely bind route: {facade_name}.{export_name}",
                )
            return candidate.route

        for module_name, relative_path in closure:
            source_path = (repo_root / relative_path).resolve()
            try:
                source_bytes = analysis.source_bytes(source_path)
                tree = source_index.parse(source_bytes, filename=relative_path)
            except (OSError, SyntaxError, ValueError) as exc:
                raise ConfidenceLedgerError(
                    "canonical_loaded_runtime_mismatch",
                    relative_path,
                ) from exc
            provider_index = _source_module_provider_index(
                repo_root,
                module_name,
                tree,
                directory_entries=directory_entries,
                source_index=source_index,
            )
            mapping_names = provider_index.mapping_names
            maps: dict[str, dict[str, object]] = {}
            if mapping_names:
                external_mappings, _invalid_imports = _source_imported_facade_mappings(
                    repo_root,
                    module_name,
                    tree,
                    mapping_names,
                    directory_entries=directory_entries,
                    source_index=source_index,
                )
                maps, invalid_maps, _namespace_effect_unknown = (
                    _source_declared_facade_mapping_values(
                        tree,
                        mapping_names,
                        external_mappings=external_mappings,
                    )
                )
                if invalid_maps or len(maps) != len(mapping_names):
                    raise ConfidenceLedgerError(
                        "canonical_loaded_runtime_mismatch",
                        f"unsupported source facade map: {module_name}",
                    )
                try:
                    for source_map in maps.values():
                        _literal_facade_value_projection(source_map)
                except (ConfidenceLedgerError, TypeError, ValueError) as exc:
                    raise ConfidenceLedgerError(
                        "canonical_loaded_runtime_mismatch",
                        f"unsupported source facade map: {module_name}",
                    ) from exc
                map_owners: list[dict[str, object]] = []
                provider_symbols = provider_index.provider_symbols_by_export or {}
                for mapping_name, source_map in sorted(maps.items()):
                    if type(source_map) is not dict:
                        raise ConfidenceLedgerError(
                            "canonical_loaded_runtime_mismatch",
                            f"unsupported source facade map: {module_name}.{mapping_name}",
                        )
                    for export, raw_target in sorted(source_map.items()):
                        if type(export) is not str:
                            raise ConfidenceLedgerError(
                                "canonical_loaded_runtime_mismatch",
                                f"unsupported source facade export: {module_name}",
                            )
                        target_module, target_symbol = resolve_source_target(
                            module_name,
                            export,
                            raw_target,
                        )
                        module_exports = provider_index.module_providers_by_export or {}
                        if export in module_exports:
                            if type(raw_target) is not str:
                                raise ConfidenceLedgerError(
                                    "canonical_loaded_runtime_mismatch",
                                    f"invalid module facade target: {module_name}.{export}",
                                )
                            target_module = _package_bound_module_provider_target(
                                raw_target,
                                module_name=module_name,
                                module_source=Path(relative_path),
                                export_name=export,
                            )
                            target_symbol = None
                            indexed_module_targets = frozenset(
                                _package_bound_module_provider_target(
                                    indexed_target,
                                    module_name=module_name,
                                    module_source=Path(relative_path),
                                    export_name=export,
                                )
                                for indexed_target in module_exports[export]
                            )
                            if (
                                len(indexed_module_targets) != 1
                                or target_module not in indexed_module_targets
                            ):
                                raise ConfidenceLedgerError(
                                    "canonical_loaded_runtime_mismatch",
                                    f"source facade module owner differs from getter: "
                                    f"{module_name}.{export}",
                                )
                        providers = provider_index.providers_by_export.get(
                            export,
                            frozenset(),
                        )
                        symbols = provider_symbols.get(export, frozenset())
                        if providers:
                            normalized_providers: set[str] = set()
                            for indexed_module in providers:
                                if indexed_module.startswith("."):
                                    try:
                                        indexed_module = importlib.util.resolve_name(
                                            indexed_module,
                                            module_name,
                                        )
                                    except (ImportError, TypeError, ValueError) as exc:
                                        raise ConfidenceLedgerError(
                                            "canonical_loaded_runtime_mismatch",
                                            f"source facade owner is ambiguous: "
                                            f"{module_name}.{export}",
                                        ) from exc
                                normalized_providers.add(indexed_module)
                            if target_module not in normalized_providers:
                                raise ConfidenceLedgerError(
                                    "canonical_loaded_runtime_mismatch",
                                    f"source facade owner differs from map: {module_name}.{export}",
                                )
                        if symbols and target_symbol not in symbols:
                            raise ConfidenceLedgerError(
                                "canonical_loaded_runtime_mismatch",
                                f"source facade member differs from map: {module_name}.{export}",
                            )
                        provider_path = _repository_module_source(
                            repo_root,
                            target_module,
                            directory_entries=directory_entries,
                        )
                        owner_verified = bool(
                            provider_path is not None
                            and (
                                target_symbol is None
                                or _repository_module_exports_symbol(
                                    repo_root,
                                    target_module,
                                    target_symbol,
                                    directory_entries=directory_entries,
                                    source_index=source_index,
                                )
                            )
                        )
                        map_owners.append(
                            {
                                "export": export,
                                "mapping": mapping_name,
                                "provider": target_module,
                                "provider_path": (
                                    provider_path.as_posix() if provider_path is not None else None
                                ),
                                "source_owner_status": (
                                    "recomputed" if owner_verified else "not_established"
                                ),
                                "symbol": target_symbol,
                            }
                        )
                facade_module = sys.modules.get(module_name)
                if facade_module is None:
                    raise ConfidenceLedgerError(
                        "canonical_loaded_runtime_mismatch",
                        f"authority facade module not loaded: {module_name}",
                    )
                namespace = vars(facade_module)
                live_maps: dict[str, object] = {}
                for mapping_name, expected_map in maps.items():
                    observed = namespace.get(mapping_name, _STATIC_FACADE_UNKNOWN)
                    if type(observed) is not dict or not _literal_facade_value_matches(
                        expected_map,
                        observed,
                    ):
                        raise ConfidenceLedgerError(
                            "canonical_loaded_runtime_mismatch",
                            f"loaded facade map differs from source: {module_name}.{mapping_name}",
                        )
                    live_maps[mapping_name] = _literal_facade_value_projection(expected_map)
                facade_rows.append(
                    {
                        "module": module_name,
                        "relative_path": relative_path,
                        "maps": live_maps,
                        "map_owners": map_owners,
                        "map_transfer_status": {
                            name: ("recomputed" if name not in invalid_maps else "not_established")
                            for name in sorted(maps)
                        },
                    }
                )
            source_rows[module_name] = (tree, provider_index, maps)
            runtime_scopes[module_name] = _runtime_import_scope_index(
                tree,
                filename=relative_path,
            )

        read_api_surface_projection = _read_api_surface_runtime_identity_projection(
            repo_root,
            closure_by_name,
            source_rows,
            runtime_binding_references=runtime_binding_references,
        )
        bindings_to_check: dict[tuple[str, str], tuple[str, str, bool]] = {}
        selected_importers: dict[tuple[str, str], set[tuple[str, str, str, str, str]]] = {}
        function_import_routes: dict[
            tuple[str, str], list[tuple[str, ast.ImportFrom, str, str, str, str]]
        ] = {}
        for module_name, (_tree, provider_index, maps) in source_rows.items():
            if not maps:
                continue
            facade_module = sys.modules.get(module_name)
            if facade_module is None:
                raise ConfidenceLedgerError("canonical_loaded_runtime_mismatch")
            namespace = vars(facade_module)
            for mapping in maps.values():
                for export, raw_target in mapping.items():
                    module_targets = (provider_index.module_providers_by_export or {}).get(
                        export, frozenset()
                    )
                    if export not in namespace:
                        continue
                    if module_targets:
                        relative_path = closure_by_name[module_name]
                        resolved_module_targets = frozenset(
                            _package_bound_module_provider_target(
                                target,
                                module_name=module_name,
                                module_source=Path(relative_path),
                                export_name=export,
                            )
                            for target in module_targets
                        )
                        if len(resolved_module_targets) != 1 or type(raw_target) is not str:
                            raise ConfidenceLedgerError(
                                "canonical_loaded_runtime_mismatch",
                                f"ambiguous cached module facade binding: {module_name}.{export}",
                            )
                        target_module = next(iter(resolved_module_targets))
                        resolved_raw_target = _package_bound_module_provider_target(
                            raw_target,
                            module_name=module_name,
                            module_source=Path(relative_path),
                            export_name=export,
                        )
                        target_path = _repository_module_source(
                            repo_root,
                            target_module,
                            directory_entries=directory_entries,
                        )
                        loaded_target = sys.modules.get(target_module)
                        if (
                            target_path is None
                            or resolved_raw_target != target_module
                            or loaded_target is None
                            or namespace.get(export) is not loaded_target
                        ):
                            raise ConfidenceLedgerError(
                                "canonical_loaded_runtime_mismatch",
                                f"cached module facade binding differs: {module_name}.{export}",
                            )
                        continue
                    target = resolve_source_target(module_name, export, raw_target)
                    bindings_to_check[(module_name, export)] = (*target, False)

        module_value_bindings: list[tuple[str, str, str, str, tuple[tuple[str, str], ...]]] = []
        module_source_route_owners: dict[tuple[str, str], set[tuple[str, str]]] = {}
        for module_name, (tree, _provider_index, _maps) in source_rows.items():
            package = (
                module_name
                if Path(closure_by_name[module_name]).name == "__init__.py"
                else module_name.rpartition(".")[0]
            )
            scope_index, function_nodes, function_codes = runtime_scopes[module_name]
            for node in _runtime_ast_nodes(tree):
                if not isinstance(node, (ast.Import, ast.ImportFrom)):
                    continue
                scope_kind, scope_owner = scope_index.get(
                    id(node), ("unsupported_scope", "<unknown>")
                )
                if isinstance(node, ast.Import):
                    if scope_kind not in {"module", "function_local"}:
                        if any(
                            _repository_module_source(
                                repo_root,
                                alias.name,
                                directory_entries=directory_entries,
                            )
                            is not None
                            for alias in node.names
                        ):
                            raise ConfidenceLedgerError(
                                "canonical_loaded_runtime_mismatch",
                                f"unsupported source-module import scope: {module_name}",
                            )
                        continue
                    for alias in node.names:
                        if alias.asname is None:
                            continue
                        candidate = alias.name
                        candidate_path = _repository_module_source(
                            repo_root,
                            candidate,
                            directory_entries=directory_entries,
                        )
                        if candidate_path is None:
                            continue
                        if scope_kind == "function_local":
                            owner = function_nodes.get(scope_owner)
                            if owner is None or not _source_function_import_binding_is_unique(
                                owner,
                                owner_code=function_codes.get(scope_owner),
                                local_name=alias.asname,
                                import_node=node,
                            ):
                                raise ConfidenceLedgerError(
                                    "canonical_loaded_runtime_mismatch",
                                    "unsupported local source-module binding: "
                                    f"{module_name}.{alias.asname}",
                                )
                            supplemental_modules[candidate] = candidate_path.as_posix()
                    continue

                base = _resolve_import_from_base(node, package)
                if base is None or base not in source_rows:
                    continue
                _base_tree, _base_index, base_maps = source_rows[base]
                if any(alias.name == "*" for alias in node.names) and base_maps:
                    raise ConfidenceLedgerError(
                        "canonical_loaded_runtime_mismatch",
                        f"wildcard lazy facade import is not source-selected: {base}",
                    )
                for alias in node.names:
                    if alias.name == "*":
                        continue
                    local_name = alias.asname or alias.name
                    route = qualified_projection_route(
                        repo_root,
                        base,
                        alias.name,
                        directory_entries=directory_entries,
                        source_index=source_index,
                    )
                    if route is None:
                        continue
                    route_kind, target_module, target_symbol = route
                    if route_kind == "external":
                        raise ConfidenceLedgerError(
                            "canonical_loaded_runtime_mismatch",
                            f"source facade provider is outside repository: {base}.{alias.name}",
                        )
                    if route_kind == "module":
                        if scope_kind not in {"module", "function_local"}:
                            raise ConfidenceLedgerError(
                                "canonical_loaded_runtime_mismatch",
                                "unsupported source-module import scope: "
                                f"{module_name}.{local_name}",
                            )
                        prior_binding = bindings_to_check.get((base, alias.name))
                        bindings_to_check[(base, alias.name)] = (
                            target_module,
                            "<module>",
                            scope_kind == "function_local"
                            or (prior_binding[2] if prior_binding is not None else False),
                        )
                        if scope_kind == "function_local":
                            selected_importers.setdefault((base, alias.name), set()).add(
                                (
                                    module_name,
                                    local_name,
                                    scope_kind,
                                    scope_owner,
                                    str(node.lineno),
                                )
                            )
                        if scope_kind == "function_local":
                            owner = function_nodes.get(scope_owner)
                            if owner is None or not _source_function_import_binding_is_unique(
                                owner,
                                owner_code=function_codes.get(scope_owner),
                                local_name=local_name,
                                import_node=node,
                            ):
                                raise ConfidenceLedgerError(
                                    "canonical_loaded_runtime_mismatch",
                                    "unsupported local source-module binding: "
                                    f"{module_name}.{local_name}",
                                )
                            target_path = _repository_module_source(
                                repo_root,
                                target_module,
                                directory_entries=directory_entries,
                            )
                            if target_path is None:
                                raise ConfidenceLedgerError("canonical_loaded_runtime_mismatch")
                            supplemental_modules[target_module] = target_path.as_posix()
                            function_import_routes.setdefault(
                                (module_name, scope_owner), []
                            ).append(
                                (
                                    local_name,
                                    node,
                                    base,
                                    alias.name,
                                    target_module,
                                    None,
                                )
                            )
                        continue
                    if target_symbol is None:
                        raise ConfidenceLedgerError("canonical_loaded_runtime_mismatch")
                    map_targets = {
                        resolve_source_target(base, alias.name, source_map[alias.name])
                        for source_map in base_maps.values()
                        if alias.name in source_map
                    }
                    if map_targets and map_targets != {(target_module, target_symbol)}:
                        raise ConfidenceLedgerError(
                            "canonical_loaded_runtime_mismatch",
                            f"source facade map differs from binding: {base}.{alias.name}",
                        )
                    if scope_kind not in {"module", "function_local"}:
                        raise ConfidenceLedgerError(
                            "canonical_loaded_runtime_mismatch",
                            f"unsupported selected import scope: {module_name}.{local_name}",
                        )
                    prior_binding = bindings_to_check.get((base, alias.name))
                    bindings_to_check[(base, alias.name)] = (
                        target_module,
                        target_symbol,
                        scope_kind == "function_local"
                        or (prior_binding[2] if prior_binding is not None else False),
                    )
                    if scope_kind == "function_local":
                        selected_importers.setdefault((base, alias.name), set()).add(
                            (
                                module_name,
                                local_name,
                                scope_kind,
                                scope_owner,
                                str(node.lineno),
                            )
                        )
                    if scope_kind == "function_local":
                        owner = function_nodes.get(scope_owner)
                        if owner is None or not _source_function_import_binding_is_unique(
                            owner,
                            owner_code=function_codes.get(scope_owner),
                            local_name=local_name,
                            import_node=node,
                        ):
                            raise ConfidenceLedgerError(
                                "canonical_loaded_runtime_mismatch",
                                f"unsupported local facade binding: {module_name}.{local_name}",
                            )
                        function_import_routes.setdefault((module_name, scope_owner), []).append(
                            (
                                local_name,
                                node,
                                base,
                                alias.name,
                                target_module,
                                target_symbol,
                            )
                        )

        # Reconcile final module-level aliases from actual source transfer. A
        # temporary package alias may be deleted after its selected member has
        # been bound; only the final consumer binding is authoritative.
        for module_name, (tree, _provider_index, _maps) in source_rows.items():
            package = (
                module_name
                if Path(closure_by_name[module_name]).name == "__init__.py"
                else module_name.rpartition(".")[0]
            )
            scope_index, function_nodes, function_codes = runtime_scopes[module_name]
            state: dict[str, tuple[str, str, str | None, str]] = {}
            state_owners: dict[str, set[tuple[str, str]]] = {}
            callable_state: dict[str, ast.FunctionDef | ast.AsyncFunctionDef] = {}
            invalid_state: set[str] = set()
            deferred_global_reads: set[str] = set()
            for statement in tree.body:
                if isinstance(statement, (ast.Import, ast.ImportFrom)):
                    if scope_index.get(id(statement), ("", ""))[0] != "module":
                        continue
                    if isinstance(statement, ast.Import):
                        for alias in statement.names:
                            if alias.asname is None:
                                continue
                            callable_state.pop(alias.asname, None)
                            target_path = _repository_module_source(
                                repo_root,
                                alias.name,
                                directory_entries=directory_entries,
                            )
                            state_owners.pop(alias.asname, None)
                            if target_path is not None:
                                state[alias.asname] = (
                                    "module",
                                    alias.name,
                                    None,
                                    str(statement.lineno),
                                )
                                invalid_state.discard(alias.asname)
                            else:
                                state.pop(alias.asname, None)
                                invalid_state.add(alias.asname)
                        continue
                    for alias in statement.names:
                        if alias.name != "*":
                            callable_state.pop(alias.asname or alias.name, None)
                    base = _resolve_import_from_base(statement, package)
                    if base is None or base not in source_rows:
                        continue
                    _base_tree, _base_index, base_maps = source_rows[base]
                    for alias in statement.names:
                        if alias.name == "*":
                            continue
                        local_name = alias.asname or alias.name
                        route = qualified_projection_route(
                            repo_root,
                            base,
                            alias.name,
                            directory_entries=directory_entries,
                            source_index=source_index,
                        )
                        if route is None:
                            state_owners.pop(local_name, None)
                            if local_name in state:
                                state.pop(local_name, None)
                                invalid_state.add(local_name)
                            continue
                        route_kind, target_module, target_symbol = route
                        state_owners[local_name] = {(base, alias.name)}
                        if route_kind == "external":
                            raise ConfidenceLedgerError("canonical_loaded_runtime_mismatch")
                        if route_kind == "module":
                            state[local_name] = (
                                "module",
                                target_module,
                                None,
                                str(statement.lineno),
                            )
                            invalid_state.discard(local_name)
                            continue
                        if target_symbol is None:
                            raise ConfidenceLedgerError("canonical_loaded_runtime_mismatch")
                        state[local_name] = (
                            "symbol",
                            target_module,
                            target_symbol,
                            str(statement.lineno),
                        )
                        invalid_state.discard(local_name)
                    continue
                if isinstance(statement, (ast.Assign, ast.AnnAssign)):
                    value = statement.value
                    targets = (
                        statement.targets
                        if isinstance(statement, ast.Assign)
                        else [statement.target]
                    )
                    if len(targets) == 1 and isinstance(targets[0], ast.Name):
                        local_name = targets[0].id
                        resolved: tuple[str, str, str | None, str] | None = None
                        resolved_owners: set[tuple[str, str]] = set()
                        selected_calls = (
                            {
                                child.func.id
                                for child in ast.walk(value)
                                if isinstance(child, ast.Call)
                                and isinstance(child.func, ast.Name)
                                and function_import_routes.get((module_name, child.func.id))
                            }
                            if value is not None
                            else set()
                        )
                        if isinstance(value, ast.Name):
                            resolved = state.get(value.id)
                            resolved_owners = set(state_owners.get(value.id, set()))
                        elif (
                            isinstance(value, ast.Attribute)
                            and isinstance(value.value, ast.Name)
                            and (module_state := state.get(value.value.id)) is not None
                            and module_state[0] == "module"
                        ):
                            resolved = (
                                "symbol",
                                module_state[1],
                                value.attr,
                                str(statement.lineno),
                            )
                            resolved_owners = set(state_owners.get(value.value.id, set()))
                        elif isinstance(value, ast.Call) and isinstance(value.func, ast.Name):
                            route_rows = function_import_routes.get(
                                (module_name, value.func.id),
                                [],
                            )
                            source_owner = callable_state.get(value.func.id)
                            if route_rows:
                                proven_rows = [
                                    row
                                    for row in route_rows
                                    if source_owner is not None
                                    and _source_function_returns_imported_binding(
                                        source_owner,
                                        local_name=row[0],
                                        import_node=row[1],
                                    )
                                ]
                                if not value.args and not value.keywords and len(proven_rows) == 1:
                                    _local, _import_node, base, export, provider, symbol = (
                                        proven_rows[0]
                                    )
                                    resolved = (
                                        "module" if symbol is None else "symbol",
                                        provider,
                                        symbol,
                                        str(statement.lineno),
                                    )
                                    resolved_owners = {(base, export)}
                                else:
                                    raise ConfidenceLedgerError(
                                        "canonical_loaded_runtime_mismatch",
                                        "unsupported selected consumer call result: "
                                        f"{module_name}.{local_name}",
                                    )
                        elif selected_calls:
                            raise ConfidenceLedgerError(
                                "canonical_loaded_runtime_mismatch",
                                "unsupported selected consumer value flow: "
                                f"{module_name}.{local_name}",
                            )
                        callable_state.pop(local_name, None)
                        if resolved is not None:
                            state[local_name] = resolved
                            state_owners[local_name] = resolved_owners
                            invalid_state.discard(local_name)
                            continue
                        state_owners.pop(local_name, None)
                        if local_name in state:
                            state.pop(local_name, None)
                            invalid_state.add(local_name)
                        continue
                    selected_calls = (
                        {
                            child.func.id
                            for child in ast.walk(value)
                            if isinstance(child, ast.Call)
                            and isinstance(child.func, ast.Name)
                            and function_import_routes.get((module_name, child.func.id))
                        }
                        if value is not None
                        else set()
                    )
                    if selected_calls:
                        raise ConfidenceLedgerError(
                            "canonical_loaded_runtime_mismatch",
                            f"unsupported selected consumer assignment: {module_name}",
                        )
                    if any(
                        isinstance(child, ast.Name) and child.id in state
                        for child in ast.walk(statement)
                    ):
                        raise ConfidenceLedgerError(
                            "canonical_loaded_runtime_mismatch",
                            f"unsupported module alias assignment: {module_name}",
                        )
                    continue
                if isinstance(statement, ast.Delete):
                    for target in statement.targets:
                        if isinstance(target, ast.Name):
                            state.pop(target.id, None)
                            state_owners.pop(target.id, None)
                            callable_state.pop(target.id, None)
                            invalid_state.discard(target.id)
                            if target.id in deferred_global_reads:
                                raise ConfidenceLedgerError("canonical_loaded_runtime_mismatch")
                        elif any(
                            isinstance(child, ast.Name) and child.id in state
                            for child in ast.walk(target)
                        ):
                            raise ConfidenceLedgerError("canonical_loaded_runtime_mismatch")
                    continue
                if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    for child in ast.walk(statement):
                        if (
                            isinstance(child, ast.Name)
                            and child.id in state
                            and isinstance(child.ctx, ast.Load)
                        ):
                            deferred_global_reads.add(child.id)
                    callable_state.pop(statement.name, None)
                    if (
                        isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef))
                        and not statement.decorator_list
                        and function_nodes.get(statement.name) is statement
                        and function_codes.get(statement.name) is not None
                    ):
                        callable_state[statement.name] = statement
                    if statement.name in state:
                        state.pop(statement.name, None)
                        state_owners.pop(statement.name, None)
                        invalid_state.add(statement.name)
                    continue
                if isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Constant):
                    continue
                if any(
                    isinstance(child, ast.Name) and child.id in state
                    for child in ast.walk(statement)
                ):
                    raise ConfidenceLedgerError(
                        "canonical_loaded_runtime_mismatch",
                        f"unsupported module alias use: {module_name}",
                    )
            if invalid_state & deferred_global_reads:
                raise ConfidenceLedgerError(
                    "canonical_loaded_runtime_mismatch",
                    f"deferred module alias binding is unresolved: {module_name}",
                )
            if invalid_state:
                module_module = sys.modules.get(module_name)
                namespace = vars(module_module) if module_module is not None else {}
                if any(name in namespace for name in invalid_state):
                    raise ConfidenceLedgerError(
                        "canonical_loaded_runtime_mismatch",
                        f"module alias binding is unresolved: {module_name}",
                    )
            for local_name, binding in state.items():
                final_owners = state_owners.get(local_name, set())
                for facade_name, export_name in final_owners:
                    route_binding = bindings_to_check.get((facade_name, export_name))
                    if route_binding is None:
                        continue
                    route_provider, route_attribute, _route_selected = route_binding
                    direct_consumer = route_provider == binding[1] and (
                        (binding[0] == "module" and route_attribute == "<module>")
                        or (binding[0] == "symbol" and binding[2] == route_attribute)
                    )
                    if direct_consumer:
                        bindings_to_check[(facade_name, export_name)] = (
                            route_provider,
                            route_attribute,
                            True,
                        )
                        selected_importers.setdefault((facade_name, export_name), set()).add(
                            (
                                module_name,
                                local_name,
                                "module",
                                "<module>",
                                binding[3],
                            )
                        )
                if binding[0] == "module":
                    module_value_bindings.append(
                        (
                            module_name,
                            local_name,
                            binding[1],
                            "<module>",
                            tuple(sorted(final_owners)),
                        )
                    )
                elif binding[0] == "symbol" and binding[2] is not None:
                    provider_path = _repository_module_source(
                        repo_root,
                        binding[1],
                        directory_entries=directory_entries,
                    )
                    if provider_path is None:
                        raise ConfidenceLedgerError("canonical_loaded_runtime_mismatch")
                    if binding[1] not in closure_by_name:
                        supplemental_modules[binding[1]] = provider_path.as_posix()
                    bindings_to_check[(module_name, local_name)] = (
                        binding[1],
                        binding[2],
                        True,
                    )
                    module_source_route_owners[(module_name, local_name)] = set(final_owners)
                    selected_importers.setdefault((module_name, local_name), set()).add(
                        (module_name, local_name, "module_value", "<module>", binding[3])
                    )

        checked_bindings: list[dict[str, object]] = []
        for (facade_name, export), (provider_name, attribute, selected) in sorted(
            bindings_to_check.items()
        ):
            provider_path = _repository_module_source(
                repo_root,
                provider_name,
                directory_entries=directory_entries,
            )
            if provider_path is None:
                raise ConfidenceLedgerError(
                    "canonical_loaded_runtime_mismatch",
                    f"source facade provider unavailable: {provider_name}",
                )
            if selected and closure_by_name.get(provider_name) != provider_path.as_posix():
                raise ConfidenceLedgerError(
                    "canonical_loaded_runtime_mismatch",
                    f"selected source facade provider is outside closure: {provider_name}",
                )
            if selected and not _repository_module_exports_symbol(
                repo_root,
                provider_name,
                attribute,
                directory_entries=directory_entries,
                source_index=source_index,
            ):
                raise ConfidenceLedgerError(
                    "canonical_loaded_runtime_mismatch",
                    f"selected source facade provider does not bind: {provider_name}.{attribute}",
                )
            provider_module = sys.modules.get(provider_name)
            facade_module = sys.modules.get(facade_name)
            if provider_module is None or facade_module is None:
                raise ConfidenceLedgerError(
                    "canonical_loaded_runtime_mismatch",
                    f"source facade binding is not loaded: {facade_name}.{export}",
                )
            provider_spec = getattr(provider_module, "__spec__", None)
            provider_origin = getattr(provider_spec, "origin", None)
            try:
                loaded_provider_path = (
                    Path(provider_origin).resolve().relative_to(repo_root.resolve())
                )
            except (OSError, TypeError, ValueError) as exc:
                raise ConfidenceLedgerError(
                    "canonical_loaded_runtime_mismatch",
                    f"source facade provider origin invalid: {provider_name}",
                ) from exc
            if loaded_provider_path.as_posix() != provider_path.as_posix():
                raise ConfidenceLedgerError(
                    "canonical_loaded_runtime_mismatch",
                    f"source facade provider origin differs: {provider_name}",
                )
            provider_namespace = vars(provider_module)
            facade_namespace = vars(facade_module)
            module_binding = attribute == "<module>"
            provider_value = (
                provider_module
                if module_binding
                else provider_namespace.get(attribute, _STATIC_FACADE_UNKNOWN)
            )
            if provider_value is _STATIC_FACADE_UNKNOWN:
                raise ConfidenceLedgerError(
                    "canonical_loaded_runtime_mismatch",
                    f"source facade provider binding is missing: {provider_name}.{attribute}",
                )
            cached = facade_namespace.get(export, _STATIC_FACADE_UNKNOWN)
            if cached is not _STATIC_FACADE_UNKNOWN and cached is not provider_value:
                raise ConfidenceLedgerError(
                    "canonical_loaded_runtime_mismatch",
                    f"cached source facade binding differs: {facade_name}.{export}",
                )
            if selected:
                observed = facade_namespace.get(export, _STATIC_FACADE_UNKNOWN)
                if observed is _STATIC_FACADE_UNKNOWN and not module_binding:
                    try:
                        observed = getattr(facade_module, export)
                    except Exception as exc:
                        raise ConfidenceLedgerError(
                            "canonical_loaded_runtime_mismatch",
                            f"source facade lookup failed: {facade_name}.{export}",
                        ) from exc
                if observed is not provider_value:
                    raise ConfidenceLedgerError(
                        "canonical_loaded_runtime_mismatch",
                        f"source facade lookup owner differs: {facade_name}.{export}",
                    )
            if provider_name not in closure_by_name:
                supplemental_modules[provider_name] = provider_path.as_posix()
            selected_import_rows: list[dict[str, str]] = []
            if selected:
                importer_rows = sorted(selected_importers.get((facade_name, export), set()))
                if not importer_rows:
                    raise ConfidenceLedgerError(
                        "canonical_loaded_runtime_mismatch",
                        f"selected source facade import is not bound: {facade_name}.{export}",
                    )
                for (
                    importer_name,
                    local_name,
                    binding_scope,
                    scope_owner,
                    source_line,
                ) in importer_rows:
                    importer_module = sys.modules.get(importer_name)
                    if importer_module is None:
                        raise ConfidenceLedgerError(
                            "canonical_loaded_runtime_mismatch",
                            f"selected importer module is not loaded: {importer_name}",
                        )
                    owner_container: object = importer_module
                    owner_binding: object = importer_module
                    owner_callable: types.FunctionType | None = None
                    owner_code_hash: str | None = None
                    if binding_scope in {"module", "module_value"}:
                        if (
                            vars(importer_module).get(local_name, _STATIC_FACADE_UNKNOWN)
                            is not provider_value
                        ):
                            raise ConfidenceLedgerError(
                                "canonical_loaded_runtime_mismatch",
                                f"selected importer binding differs: {importer_name}.{local_name}",
                            )
                    elif binding_scope == "function_local":
                        importer_scope = runtime_scopes.get(importer_name)
                        expected_owner_code = (
                            importer_scope[2].get(scope_owner)
                            if importer_scope is not None
                            else None
                        )
                        owner_node = (
                            importer_scope[1].get(scope_owner)
                            if importer_scope is not None
                            else None
                        )
                        owner_binding = _source_live_scope_owner(
                            importer_module,
                            importer_name,
                            scope_owner,
                            expected_code=expected_owner_code,
                            source_node=owner_node,
                            source_path=repo_root / closure_by_name[importer_name],
                        )
                        if owner_binding is None:
                            raise ConfidenceLedgerError(
                                "canonical_loaded_runtime_mismatch",
                                f"selected importer owner differs from pinned source: "
                                f"{importer_name}.{scope_owner}",
                            )
                        (
                            owner_container,
                            owner_binding,
                            owner_callable,
                            owner_code_hash,
                        ) = owner_binding
                    elif binding_scope != "function_local":
                        raise ConfidenceLedgerError("canonical_loaded_runtime_mismatch")
                    selected_import_rows.append(
                        {
                            "module": importer_name,
                            "name": local_name,
                            "scope": binding_scope,
                            "owner": scope_owner,
                            "line": source_line,
                        }
                    )
                    if runtime_binding_references is not None:
                        runtime_binding_references.append(
                            (
                                facade_name,
                                export,
                                facade_module,
                                provider_name,
                                provider_module,
                                attribute,
                                provider_value,
                                importer_name,
                                local_name,
                                importer_module,
                                binding_scope,
                                scope_owner,
                                owner_container,
                                owner_callable,
                                owner_code_hash,
                                owner_binding,
                            )
                        )
            binding_row: dict[str, object] = {
                "attribute": attribute,
                "facade": facade_name,
                "export": export,
                "provider": provider_name,
                "provider_path": provider_path.as_posix(),
                "selected": "true" if selected else "false",
                "importers": selected_import_rows,
            }
            source_routes = module_source_route_owners.get((facade_name, export), set())
            if source_routes:
                binding_row["source_routes"] = [
                    {"facade": source_facade, "export": source_export}
                    for source_facade, source_export in sorted(source_routes)
                ]
            checked_bindings.append(binding_row)

        for importer_name, local_name, target_name, scope_owner, source_routes in sorted(
            set(module_value_bindings)
        ):
            target_path = _repository_module_source(
                repo_root,
                target_name,
                directory_entries=directory_entries,
            )
            if target_path is None:
                raise ConfidenceLedgerError("canonical_loaded_runtime_mismatch")
            if target_name not in closure_by_name:
                supplemental_modules[target_name] = target_path.as_posix()
            importer_module = sys.modules.get(importer_name)
            provider_module = sys.modules.get(target_name)
            if importer_module is None or provider_module is None:
                raise ConfidenceLedgerError(
                    "canonical_loaded_runtime_mismatch",
                    f"source module alias is not loaded: {importer_name}.{local_name}",
                )
            try:
                loaded_module_path = Path(getattr(provider_module, "__file__", "")).resolve()
                loaded_module_path.relative_to(repo_root.resolve())
            except (OSError, TypeError, ValueError) as exc:
                raise ConfidenceLedgerError(
                    "canonical_loaded_runtime_mismatch",
                    f"source module origin is invalid: {target_name}",
                ) from exc
            if loaded_module_path != (repo_root / target_path).resolve():
                raise ConfidenceLedgerError(
                    "canonical_loaded_runtime_mismatch",
                    f"source module origin differs: {target_name}",
                )
            if vars(importer_module).get(local_name, _STATIC_FACADE_UNKNOWN) is not provider_module:
                raise ConfidenceLedgerError(
                    "canonical_loaded_runtime_mismatch",
                    f"source module binding differs: {importer_name}.{local_name}",
                )
            checked_bindings.append(
                {
                    "facade": importer_name,
                    "export": local_name,
                    "provider": target_name,
                    "provider_path": target_path.as_posix(),
                    "selected": "true",
                    "module_binding": "true",
                    "source_routes": [
                        {"facade": source_facade, "export": source_export}
                        for source_facade, source_export in source_routes
                    ],
                    "importers": [
                        {
                            "module": importer_name,
                            "name": local_name,
                            "scope": "module_value",
                            "owner": scope_owner,
                            "line": "source-transfer",
                        }
                    ],
                }
            )
            if runtime_binding_references is not None:
                runtime_binding_references.append(
                    (
                        importer_name,
                        local_name,
                        importer_module,
                        target_name,
                        provider_module,
                        "<module>",
                        provider_module,
                        importer_name,
                        local_name,
                        importer_module,
                        "module_value",
                        scope_owner,
                        importer_module,
                        None,
                        None,
                        importer_module,
                    )
                )

        for row in facade_rows:
            module = sys.modules.get(str(row["module"]))
            if module is None:
                raise ConfidenceLedgerError("canonical_loaded_runtime_mismatch")
            _tree, _index, maps = source_rows[str(row["module"])]
            for mapping_name, expected_map in maps.items():
                observed = vars(module).get(mapping_name, _STATIC_FACADE_UNKNOWN)
                if type(observed) is not dict or not _literal_facade_value_matches(
                    expected_map,
                    observed,
                ):
                    raise ConfidenceLedgerError(
                        "canonical_loaded_runtime_mismatch",
                        "loaded facade map changed during reconciliation: "
                        f"{row['module']}.{mapping_name}",
                    )
        manifest = {
            "facades": facade_rows,
            "bindings": checked_bindings,
            "read_api_surfaces": read_api_surface_projection,
        }
        if owns_analysis:
            analysis.assert_sources_unchanged()
        return _canonical_json(manifest), tuple(sorted(supplemental_modules.items()))
    except (OSError, TypeError, ValueError, AttributeError, SyntaxError) as exc:
        if isinstance(exc, ConfidenceLedgerError):
            raise
        raise ConfidenceLedgerError("canonical_loaded_runtime_mismatch", str(exc)) from exc
    finally:
        if token is not None:
            _ACTIVE_INTEGRITY_ANALYSIS.reset(token)


def _source_live_scope_owner(
    module: types.ModuleType,
    module_name: str,
    scope_owner: str,
    *,
    expected_code: types.CodeType | None,
    source_node: ast.FunctionDef | ast.AsyncFunctionDef | None,
    source_path: Path,
) -> tuple[object, object, types.FunctionType, str] | None:
    """Bind a local-import scope to its actual module or class callable owner."""

    if expected_code is None or source_node is None:
        return None
    module_namespace = vars(module)
    if type(module_namespace) is not dict:
        return None
    owner_parts = tuple(scope_owner.split("."))
    if not owner_parts or any(not part for part in owner_parts):
        return None
    owner_container: object = module
    if len(owner_parts) == 1:
        if source_node.decorator_list:
            return None
        raw_callable = module_namespace.get(owner_parts[0])
    elif len(owner_parts) == 2:
        class_name, member_name = owner_parts
        owner_container = module_namespace.get(class_name)
        if type(owner_container) is not type:
            return None
        class_namespace = type.__getattribute__(owner_container, "__dict__")
        if not isinstance(class_namespace, Mapping):
            return None
        if not (
            type.__getattribute__(owner_container, "__module__") == module_name
            and type.__getattribute__(owner_container, "__qualname__") == class_name
        ):
            return None
        raw_callable = class_namespace.get(member_name)
        decorator_names = tuple(
            _decorator_expression_name(item) for item in source_node.decorator_list
        )
        expected_descriptor: type[object] | None
        if not decorator_names:
            expected_descriptor = types.FunctionType
        elif decorator_names == ("classmethod",):
            expected_descriptor = classmethod
        elif decorator_names == ("staticmethod",):
            expected_descriptor = staticmethod
        else:
            return None
        if type(raw_callable) is not expected_descriptor:
            return None
        if type(raw_callable) in {classmethod, staticmethod}:
            raw_callable = raw_callable.__func__
    else:
        return None
    if not isinstance(raw_callable, types.FunctionType):
        return None
    actual_code = raw_callable.__code__
    expected_code_hash = _content_hash(_normalize_code_object(expected_code))
    actual_code_hash = _content_hash(_normalize_code_object(actual_code))
    if not (
        raw_callable.__globals__ is module_namespace
        and raw_callable.__qualname__ == scope_owner
        and actual_code.co_qualname == scope_owner
        and expected_code.co_qualname == scope_owner
        and Path(actual_code.co_filename).resolve() == source_path.resolve()
        and actual_code_hash == expected_code_hash
    ):
        return None
    return (
        owner_container,
        module_namespace.get(owner_parts[-1])
        if len(owner_parts) == 1
        else (type.__getattribute__(owner_container, "__dict__").get(owner_parts[-1])),
        raw_callable,
        actual_code_hash,
    )


def _runtime_binding_references_match(
    observed: Iterable[_FacadeRuntimeBindingReference],
    expected: tuple[_FacadeRuntimeBindingReference, ...],
) -> bool:
    """Require the selected facade/importer/provider objects to remain identical."""

    key_indexes = (0, 1, 3, 5, 7, 8, 14)
    object_indexes = (2, 4, 6, 9, 12, 13, 15)
    observed_rows = tuple(sorted(observed, key=lambda item: (item[0], item[1], item[7], item[8])))
    expected_rows = tuple(sorted(expected, key=lambda item: (item[0], item[1], item[7], item[8])))
    if len(observed_rows) != len(expected_rows):
        return False
    for current, pinned in zip(observed_rows, expected_rows, strict=True):
        if any(current[index] != pinned[index] for index in key_indexes):
            return False
        if any(current[index] is not pinned[index] for index in object_indexes):
            return False
    return True


def _runtime_import_scope_index(
    tree: ast.Module,
    *,
    filename: str = "<pinned-source>",
) -> tuple[
    dict[int, tuple[str, str]],
    dict[str, ast.FunctionDef | ast.AsyncFunctionDef],
    dict[str, types.CodeType | None],
]:
    """Index runtime imports by lexical owner and compiler-derived closure scope.

    Only module imports and direct function or method locals have a binding
    model here. Conditional imports, class-body imports, and nested callable
    imports remain explicit unsupported scopes. The code-object index comes
    from compiling the pinned AST; source is never executed.
    """

    import_scopes: dict[int, tuple[str, str]] = {}
    functions: dict[str, ast.FunctionDef | ast.AsyncFunctionDef] = {}
    function_codes: dict[str, types.CodeType | None] = {}

    module_code = compile(tree, filename, "exec", dont_inherit=True)

    def add_code(code: types.CodeType) -> None:
        if code.co_name != "<module>":
            owner_name = code.co_qualname.replace(".<locals>.", ".")
            if owner_name in function_codes:
                function_codes[owner_name] = None
            else:
                function_codes[owner_name] = code
        for value in code.co_consts:
            if isinstance(value, types.CodeType):
                add_code(value)

    add_code(module_code)

    def walk(
        node: ast.AST,
        *,
        scope_kind: str,
        owner: tuple[str, ...],
        controlled: bool = False,
    ) -> None:
        if isinstance(node, ast.If) and _is_type_checking_test(node.test):
            for statement in node.orelse:
                walk(statement, scope_kind=scope_kind, owner=owner, controlled=controlled)
            return
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for expression in (*node.decorator_list, *node.args.defaults, *node.args.kw_defaults):
                if expression is not None:
                    walk(expression, scope_kind=scope_kind, owner=owner, controlled=controlled)
            if node.returns is not None:
                walk(node.returns, scope_kind=scope_kind, owner=owner, controlled=controlled)
            function_owner = (*owner, node.name)
            functions[".".join(function_owner)] = node
            if scope_kind in {"module", "class_local"} and not controlled:
                body_scope = "function_local"
            elif scope_kind in {"module", "class_local"}:
                body_scope = "function_controlled"
            else:
                body_scope = "nested_callable"
            for statement in node.body:
                walk(statement, scope_kind=body_scope, owner=function_owner)
            return
        if isinstance(node, ast.ClassDef):
            for expression in (*node.decorator_list, *node.bases, *node.keywords):
                walk(expression, scope_kind=scope_kind, owner=owner, controlled=controlled)
            class_owner = (*owner, node.name)
            body_scope = (
                "class_local" if scope_kind == "module" and not controlled else "nested_class"
            )
            for statement in node.body:
                walk(statement, scope_kind=body_scope, owner=class_owner)
            return
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            indexed_scope = (
                f"{scope_kind}_controlled"
                if controlled and scope_kind in {"module", "function_local"}
                else scope_kind
            )
            import_scopes[id(node)] = (indexed_scope, ".".join(owner) if owner else "<module>")
            return
        controls = (
            ast.If,
            ast.For,
            ast.AsyncFor,
            ast.While,
            ast.With,
            ast.AsyncWith,
            ast.Try,
            ast.TryStar,
            ast.Match,
        )
        if isinstance(node, controls):
            next_controlled = controlled or scope_kind in {"module", "function_local"}
            for child in ast.iter_child_nodes(node):
                walk(child, scope_kind=scope_kind, owner=owner, controlled=next_controlled)
            return
        for child in ast.iter_child_nodes(node):
            walk(child, scope_kind=scope_kind, owner=owner, controlled=controlled)

    walk(tree, scope_kind="module", owner=())
    return import_scopes, functions, function_codes


def _source_function_returns_imported_binding(
    owner: ast.FunctionDef | ast.AsyncFunctionDef,
    *,
    local_name: str,
    import_node: ast.Import | ast.ImportFrom,
) -> bool:
    """Prove one bounded source-local value flow from import to function result.

    Accepted bodies are a direct import followed by ``return local`` or one
    undecorated, argument-only identity helper followed by ``return helper(local)``.
    The analyzer never executes source functions; all other flow remains unknown.
    """

    if owner.decorator_list:
        return False
    body = list(owner.body)
    if (
        body
        and isinstance(body[0], ast.Expr)
        and isinstance(body[0].value, ast.Constant)
        and (type(body[0].value.value) is str)
    ):
        body.pop(0)
    if not body or body[0] is not import_node:
        return False
    if len(body) == 2 and isinstance(body[1], ast.Return):
        result = body[1].value
        return bool(isinstance(result, ast.Name) and result.id == local_name)
    if len(body) != 3 or not isinstance(body[1], (ast.FunctionDef, ast.AsyncFunctionDef)):
        return False
    helper = body[1]
    result = body[2]
    if not (
        isinstance(result, ast.Return)
        and isinstance(result.value, ast.Call)
        and isinstance(result.value.func, ast.Name)
        and result.value.func.id == helper.name
        and len(result.value.args) == 1
        and not result.value.keywords
        and isinstance(result.value.args[0], ast.Name)
        and result.value.args[0].id == local_name
        and not helper.decorator_list
        and not helper.args.defaults
        and not helper.args.kw_defaults
        and not helper.args.kwonlyargs
        and helper.args.vararg is None
        and helper.args.kwarg is None
        and len((*helper.args.posonlyargs, *helper.args.args)) == 1
        and not getattr(helper, "type_params", ())
        and all(
            argument.annotation is None
            for argument in (*helper.args.posonlyargs, *helper.args.args)
        )
        and helper.returns is None
    ):
        return False
    helper_body = list(helper.body)
    if (
        helper_body
        and isinstance(helper_body[0], ast.Expr)
        and isinstance(helper_body[0].value, ast.Constant)
        and type(helper_body[0].value.value) is str
    ):
        helper_body.pop(0)
    if len(helper_body) != 1 or not isinstance(helper_body[0], ast.Return):
        return False
    parameter = (*helper.args.posonlyargs, *helper.args.args)[0].arg
    helper_result = helper_body[0].value
    return bool(isinstance(helper_result, ast.Name) and helper_result.id == parameter)


def _source_function_import_binding_is_unique(
    owner: ast.FunctionDef | ast.AsyncFunctionDef,
    *,
    owner_code: types.CodeType | None,
    local_name: str,
    import_node: ast.Import | ast.ImportFrom,
) -> bool:
    """Require one uncaptured local import binding in the compiled source function."""

    if (
        owner_code is None
        or owner_code.co_name != owner.name
        or local_name not in owner_code.co_varnames
        or local_name in owner_code.co_cellvars
    ):
        return False

    arguments = (
        *owner.args.posonlyargs,
        *owner.args.args,
        *owner.args.kwonlyargs,
        *((owner.args.vararg,) if owner.args.vararg is not None else ()),
        *((owner.args.kwarg,) if owner.args.kwarg is not None else ()),
    )
    if any(argument.arg == local_name for argument in arguments):
        return False

    writes: list[tuple[str, int, int, int]] = []
    unsupported_scope_declaration = False

    def write(name: str, node: ast.AST, ordinal: int = 0) -> None:
        writes.append((name, getattr(node, "lineno", -1), getattr(node, "col_offset", -1), ordinal))

    def walk(node: ast.AST, *, root: bool = False) -> None:
        nonlocal unsupported_scope_declaration
        if not root and isinstance(
            node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)
        ):
            if (
                isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                and node.name == local_name
            ):
                write(local_name, node)
            return
        if isinstance(node, (ast.Global, ast.Nonlocal)) and local_name in node.names:
            unsupported_scope_declaration = True
        elif (
            isinstance(node, ast.Name)
            and node.id == local_name
            and isinstance(node.ctx, (ast.Store, ast.Del))
        ):
            write(local_name, node)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for ordinal, alias in enumerate(node.names):
                bound = alias.asname or (
                    alias.name.split(".", 1)[0] if isinstance(node, ast.Import) else alias.name
                )
                if bound == local_name:
                    write(local_name, node, ordinal)
        elif (
            (isinstance(node, ast.ExceptHandler) and node.name == local_name)
            or (isinstance(node, ast.MatchAs) and node.name == local_name)
            or (isinstance(node, ast.MatchStar) and node.name == local_name)
            or (isinstance(node, ast.MatchMapping) and node.rest == local_name)
        ):
            write(local_name, node)
        for child in ast.iter_child_nodes(node):
            walk(child)

    for statement in owner.body:
        walk(statement)
    import_alias_ordinal = next(
        (
            ordinal
            for ordinal, alias in enumerate(import_node.names)
            if (
                alias.asname
                or (
                    alias.name.split(".", 1)[0]
                    if isinstance(import_node, ast.Import)
                    else alias.name
                )
            )
            == local_name
        ),
        -1,
    )
    expected = (
        local_name,
        getattr(import_node, "lineno", -1),
        getattr(import_node, "col_offset", -1),
        import_alias_ordinal,
    )
    return (
        not unsupported_scope_declaration
        and writes.count(expected) == 1
        and sum(row[0] == local_name for row in writes) == 1
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


def _module_scope_definite_bindings(tree: ast.Module) -> frozenset[str]:
    """Return names definitely bound by supported module-scope statements."""

    names: set[str] = set()

    def visit(statements: Iterable[ast.stmt]) -> None:
        for statement in statements:
            if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                names.add(statement.name)
            elif isinstance(statement, (ast.Assign, ast.AnnAssign)):
                if isinstance(statement, ast.AnnAssign) and statement.value is None:
                    continue
                targets = (
                    statement.targets if isinstance(statement, ast.Assign) else (statement.target,)
                )
                for target in targets:
                    names.update(_source_target_names(target))
            elif isinstance(statement, ast.TypeAlias):
                names.update(_source_target_names(statement.name))
            elif isinstance(statement, ast.Import):
                names.update(
                    alias.asname or alias.name.partition(".")[0] for alias in statement.names
                )
            elif isinstance(statement, ast.ImportFrom):
                names.update(
                    alias.asname or alias.name for alias in statement.names if alias.name != "*"
                )
            elif isinstance(statement, ast.If):
                if _is_type_checking_test(statement.test):
                    visit(statement.orelse)
                else:
                    try:
                        condition = ast.literal_eval(statement.test)
                    except (ValueError, TypeError, SyntaxError, MemoryError):
                        continue
                    if type(condition) is bool:
                        visit(statement.body if condition else statement.orelse)

    visit(tree.body)
    return frozenset(names)


def _module_scope_statement_binding_names(statement: ast.stmt) -> frozenset[str]:
    """Return module-scope names bound by one statement, without entering callables."""

    if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return frozenset({statement.name})
    if isinstance(statement, ast.Import):
        return frozenset(alias.asname or alias.name.partition(".")[0] for alias in statement.names)
    if isinstance(statement, ast.ImportFrom):
        names = {alias.asname or alias.name for alias in statement.names if alias.name != "*"}
        if any(alias.name == "*" for alias in statement.names):
            names.add("*")
        return frozenset(names)
    if isinstance(statement, ast.Assign):
        return frozenset(
            name for target in statement.targets for name in _source_target_names(target)
        )
    if isinstance(statement, ast.AnnAssign):
        if statement.value is None:
            return frozenset()
        return frozenset(_source_target_names(statement.target))
    if isinstance(statement, ast.AugAssign):
        return frozenset(_source_target_names(statement.target))
    if isinstance(statement, ast.TypeAlias):
        return frozenset(_source_target_names(statement.name))
    if isinstance(statement, ast.Delete):
        return frozenset(
            name for target in statement.targets for name in _source_target_names(target)
        )
    if isinstance(statement, ast.If):
        return frozenset(
            name
            for child in (*statement.body, *statement.orelse)
            for name in _module_scope_statement_binding_names(child)
        )
    if isinstance(statement, (ast.For, ast.AsyncFor)):
        names = set(_source_target_names(statement.target))
        for child in (*statement.body, *statement.orelse):
            names.update(_module_scope_statement_binding_names(child))
        return frozenset(names)
    if isinstance(statement, ast.While):
        return frozenset(
            name
            for child in (*statement.body, *statement.orelse)
            for name in _module_scope_statement_binding_names(child)
        )
    if isinstance(statement, (ast.With, ast.AsyncWith)):
        names = {
            name
            for item in statement.items
            if item.optional_vars is not None
            for name in _source_target_names(item.optional_vars)
        }
        for child in statement.body:
            names.update(_module_scope_statement_binding_names(child))
        return frozenset(names)
    if isinstance(statement, (ast.Try, getattr(ast, "TryStar", ast.Try))):
        names: set[str] = set()
        for child in (*statement.body, *statement.orelse, *statement.finalbody):
            names.update(_module_scope_statement_binding_names(child))
        for handler in statement.handlers:
            if handler.name is not None:
                names.add(handler.name)
            for child in handler.body:
                names.update(_module_scope_statement_binding_names(child))
        return frozenset(names)
    if isinstance(statement, ast.Match):
        names: set[str] = set()
        for case in statement.cases:
            for pattern_node in ast.walk(case.pattern):
                if (
                    isinstance(pattern_node, (ast.MatchAs, ast.MatchStar))
                    and pattern_node.name is not None
                ):
                    names.add(pattern_node.name)
                elif isinstance(pattern_node, ast.MatchMapping) and pattern_node.rest is not None:
                    names.add(pattern_node.rest)
            for child in case.body:
                names.update(_module_scope_statement_binding_names(child))
        return frozenset(names)
    if isinstance(statement, ast.Expr):
        names = {
            name
            for node in ast.walk(statement.value)
            if isinstance(node, ast.NamedExpr)
            for name in _source_target_names(node.target)
        }
        return frozenset(names)
    return frozenset()


def _module_scope_direct_binding_sites(
    tree: ast.Module,
    export_name: str,
) -> tuple[tuple[str, ast.stmt, ast.alias | None], ...]:
    """Find one unconditional runtime binding or refuse uncertain package flow."""

    sites: list[tuple[str, ast.stmt, ast.alias | None]] = []

    def visit(statements: Iterable[ast.stmt]) -> None:
        for statement in statements:
            if isinstance(statement, ast.If):
                if _is_type_checking_test(statement.test):
                    visit(statement.orelse)
                    continue
                try:
                    condition = ast.literal_eval(statement.test)
                except (ValueError, TypeError, SyntaxError, MemoryError):
                    condition = None
                if type(condition) is bool:
                    visit(statement.body if condition else statement.orelse)
                    continue
                branch_names = {
                    name
                    for child in (*statement.body, *statement.orelse)
                    for name in _module_scope_statement_binding_names(child)
                }
                if export_name in branch_names or "*" in branch_names:
                    raise ConfidenceLedgerError(
                        "canonical_loaded_runtime_mismatch",
                        f"conditional source binding is unresolved: {export_name}",
                    )
                continue
            statement_names = _module_scope_statement_binding_names(statement)
            if "*" in statement_names:
                raise ConfidenceLedgerError(
                    "canonical_loaded_runtime_mismatch",
                    f"wildcard source binding is unresolved: {export_name}",
                )
            if export_name not in statement_names:
                continue
            if isinstance(statement, ast.ImportFrom):
                matching = tuple(
                    alias
                    for alias in statement.names
                    if alias.name != "*" and (alias.asname or alias.name) == export_name
                )
                if len(matching) != 1:
                    raise ConfidenceLedgerError(
                        "canonical_loaded_runtime_mismatch",
                        f"ambiguous source import binding: {export_name}",
                    )
                sites.append(("import_from", statement, matching[0]))
            elif isinstance(statement, ast.Import):
                matching = tuple(
                    alias
                    for alias in statement.names
                    if (alias.asname or alias.name.partition(".")[0]) == export_name
                )
                if len(matching) != 1:
                    raise ConfidenceLedgerError(
                        "canonical_loaded_runtime_mismatch",
                        f"ambiguous source module binding: {export_name}",
                    )
                sites.append(("import", statement, matching[0]))
            elif isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                sites.append(("local", statement, None))
            elif isinstance(statement, (ast.Assign, ast.AnnAssign)):
                if isinstance(statement, ast.AnnAssign) and statement.value is None:
                    continue
                sites.append(("assignment", statement, None))
            else:
                sites.append(("unsupported", statement, None))

    visit(tree.body)
    return tuple(sites)


def _source_package_initializer_effect_is_unknown(tree: ast.Module) -> bool:
    """Return whether bounded transfer cannot establish package namespace stability.

    Only a top-level class with no bases, decorators, keywords, type parameters, or
    executable body beyond a docstring and ``pass`` is omitted from the effect view.
    The direct-binding resolver still reads the original tree. This preserves that
    narrow inert-class case without treating class bodies or metaclass hooks as safe.
    """

    def inert_class(statement: ast.stmt) -> bool:
        return bool(
            isinstance(statement, ast.ClassDef)
            and statement.name
            not in {
                "__name__",
                "__package__",
                "__path__",
                "__spec__",
                "__loader__",
                "__file__",
                "__cached__",
                "__builtins__",
                "__build_class__",
                "__getattr__",
                "__dir__",
                "__all__",
                "__polisyos_static_namespace_effect_guard__",
            }
            and not statement.decorator_list
            and not statement.bases
            and not statement.keywords
            and not getattr(statement, "type_params", ())
            and all(
                isinstance(child, ast.Pass)
                or (
                    isinstance(child, ast.Expr)
                    and isinstance(child.value, ast.Constant)
                    and type(child.value.value) is str
                )
                for child in statement.body
            )
        )

    watched_names = frozenset(
        {
            "__name__",
            "__package__",
            "__path__",
            "__spec__",
            "__loader__",
            "__file__",
            "__cached__",
            "__builtins__",
            "__build_class__",
            "__polisyos_static_namespace_effect_guard__",
        }
    )
    effect_tree = ast.Module(
        body=[statement for statement in tree.body if not inert_class(statement)],
        type_ignores=tree.type_ignores,
    )
    values, invalid = _static_facade_mapping_values(
        effect_tree,
        watched_names,
        scan_deferred_mapping_effects=False,
    )
    # The helper models tracked literal dicts as valid map inputs. These reserved
    # names are sentinels, not maps: any explicit binding of one is itself unknown.
    return bool(invalid & watched_names) or bool(values.keys() & watched_names)


def _source_package_getattr_binding_is_unresolved(tree: ast.Module) -> bool:
    """Detect module-level ``__getattr__`` bindings outside the literal hook index.

    The scope-bound-name census includes import aliases, assignment and deletion targets,
    definitions under module control flow, and other module-scope binding forms. Only one
    unshadowed top-level function definition is delegated to the existing literal PEP 562
    provider index; its per-export logic still refuses unsupported dispatch bodies.
    """

    if "__getattr__" not in _source_scope_bound_names(tree.body):
        return False
    definitions = tuple(
        statement
        for statement in tree.body
        if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef))
        and statement.name == "__getattr__"
    )
    if len(definitions) != 1:
        return True
    definition = definitions[0]
    other_statements = tuple(statement for statement in tree.body if statement is not definition)
    return "__getattr__" in _source_scope_bound_names(other_statements)


@dataclass(frozen=True, slots=True)
class _SourceModuleImportRouteCandidate:
    """One source-discovered route that has not necessarily earned runtime authority."""

    route: tuple[str, str, str | None] | None
    binding_basis: Literal[
        "direct",
        "literal_getattr",
        "child",
        "unresolved",
        "absent",
    ]
    package_initializer_effect_unknown: bool


def _source_module_import_route(
    repo_root: Path,
    module_name: str,
    export_name: str,
    *,
    directory_entries: dict[Path, frozenset[str]],
    source_index: _AuthorityImportClosureSourceIndex,
    visited: frozenset[tuple[str, str]] = frozenset(),
    skip_direct_binding: bool = False,
) -> tuple[str, str, str | None] | None:
    """Resolve a statically supported import route only when package effects are known."""

    candidate = _source_module_import_route_candidate(
        repo_root,
        module_name,
        export_name,
        directory_entries=directory_entries,
        source_index=source_index,
        visited=visited,
        skip_direct_binding=skip_direct_binding,
    )
    if candidate.package_initializer_effect_unknown:
        raise ConfidenceLedgerError(
            "canonical_loaded_runtime_mismatch",
            f"package initializer namespace effect is unresolved: {module_name}.{export_name}",
        )
    return candidate.route


def _source_module_import_route_candidate(
    repo_root: Path,
    module_name: str,
    export_name: str,
    *,
    directory_entries: dict[Path, frozenset[str]],
    source_index: _AuthorityImportClosureSourceIndex,
    visited: frozenset[tuple[str, str]] = frozenset(),
    skip_direct_binding: bool = False,
) -> _SourceModuleImportRouteCandidate:
    """Discover a source route candidate without asserting its loaded binding is authoritative.

    Callers that admit an authority route must separately reconcile the complete
    source/runtime/code projection. An unknown package initializer neither qualifies
    nor excludes a candidate by itself: the selected source provider and every live
    facade/importer binding must be independently reconciled before admission.
    """

    key = (module_name, export_name)
    if key in visited and not skip_direct_binding:
        raise ConfidenceLedgerError(
            "canonical_loaded_runtime_mismatch",
            f"cyclic source import route: {module_name}.{export_name}",
        )
    next_visited = visited if skip_direct_binding else visited | {key}
    module_source = _repository_module_source(
        repo_root,
        module_name,
        directory_entries=directory_entries,
    )
    initializer_tree: ast.Module | None = None
    if module_source is not None and module_source.name == "__init__.py":
        try:
            analysis = _active_integrity_analysis()
            source_path = repo_root / module_source
            source_bytes = (
                analysis.source_bytes(source_path)
                if analysis is not None
                else source_path.read_bytes()
            )
            initializer_tree = source_index.parse(source_bytes, filename=module_source.as_posix())
        except (OSError, SyntaxError) as exc:
            raise ConfidenceLedgerError(
                "canonical_loaded_runtime_mismatch",
                module_source.as_posix(),
            ) from exc
    initializer_effect_unknown = bool(
        initializer_tree is not None
        and _source_package_initializer_effect_is_unknown(initializer_tree)
    )
    direct = (
        None
        if skip_direct_binding
        else _source_module_direct_binding_route(
            repo_root,
            module_name,
            export_name,
            directory_entries=directory_entries,
            source_index=source_index,
            visited=next_visited,
        )
    )
    if direct is not None:
        return _SourceModuleImportRouteCandidate(
            route=direct,
            binding_basis="direct",
            package_initializer_effect_unknown=initializer_effect_unknown,
        )

    if initializer_tree is not None and _source_package_getattr_binding_is_unresolved(
        initializer_tree
    ):
        return _SourceModuleImportRouteCandidate(
            route=None,
            binding_basis="unresolved",
            package_initializer_effect_unknown=True,
        )

    provider = _literal_module_getattr_provider(
        repo_root,
        module_name,
        export_name,
        directory_entries=directory_entries,
        source_index=source_index,
    )
    if provider is not None:
        relative = _repository_module_source(
            repo_root,
            module_name,
            directory_entries=directory_entries,
        )
        if relative is None:
            raise ConfidenceLedgerError("canonical_loaded_runtime_mismatch")
        try:
            analysis = _active_integrity_analysis()
            source_path = repo_root / relative
            source_bytes = (
                analysis.source_bytes(source_path)
                if analysis is not None
                else source_path.read_bytes()
            )
            tree = source_index.parse(source_bytes, filename=relative.as_posix())
        except (OSError, SyntaxError) as exc:
            raise ConfidenceLedgerError(
                "canonical_loaded_runtime_mismatch",
                relative.as_posix(),
            ) from exc
        provider_index = _source_module_provider_index(
            repo_root,
            module_name,
            tree,
            directory_entries=directory_entries,
            source_index=source_index,
        )
        module_providers = provider_index.module_providers_by_export or {}
        module_targets = frozenset(
            _package_bound_module_provider_target(
                target,
                module_name=module_name,
                module_source=relative,
                export_name=export_name,
            )
            for target in module_providers.get(export_name, frozenset())
        )
        if module_targets:
            if len(module_targets) != 1 or next(iter(module_targets)) != provider:
                raise ConfidenceLedgerError(
                    "canonical_loaded_runtime_mismatch",
                    f"ambiguous module facade binding: {module_name}.{export_name}",
                )
            route = ("module", provider, None)
        else:
            symbols = (provider_index.provider_symbols_by_export or {}).get(
                export_name,
                frozenset({export_name}),
            )
            if len(symbols) != 1:
                raise ConfidenceLedgerError(
                    "canonical_loaded_runtime_mismatch",
                    f"ambiguous source facade binding: {module_name}.{export_name}",
                )
            route_kind = (
                "symbol"
                if _repository_module_source(
                    repo_root,
                    provider,
                    directory_entries=directory_entries,
                )
                is not None
                else "external"
            )
            route = route_kind, provider, next(iter(symbols))
        return _SourceModuleImportRouteCandidate(
            route=route,
            binding_basis="literal_getattr",
            package_initializer_effect_unknown=initializer_effect_unknown,
        )

    if initializer_effect_unknown:
        return _SourceModuleImportRouteCandidate(
            route=None,
            binding_basis="unresolved",
            package_initializer_effect_unknown=True,
        )

    child_module = f"{module_name}.{export_name}"
    if (
        module_source is not None
        and module_source.name == "__init__.py"
        and _repository_module_source(
            repo_root,
            child_module,
            directory_entries=directory_entries,
        )
        is not None
    ):
        return _SourceModuleImportRouteCandidate(
            route=("module", child_module, None),
            binding_basis="child",
            package_initializer_effect_unknown=False,
        )
    return _SourceModuleImportRouteCandidate(
        route=None,
        binding_basis="absent",
        package_initializer_effect_unknown=False,
    )


_READ_API_SURFACES_MODULE = "polisyos.data_forge.read_api.surfaces"
_READ_API_SURFACE_ROUTES_MODULE = "polisyos.data_forge.read_api.surface_routes"
_READ_API_PACKAGE_MODULE = "polisyos.data_forge.read_api"
_READ_API_SURFACE_FIELDS = ("name", "module", "summary")


def _source_ast_name_is(node: ast.AST, expected: str) -> bool:
    return isinstance(node, ast.Name) and node.id == expected


def _read_api_surface_source_declaration_supported(tree: ast.Module) -> bool:
    """Recognize only the current source-owned surface record constructor."""

    def import_binding_is(name: str, module: str, level: int) -> bool:
        sites = _module_scope_direct_binding_sites(tree, name)
        return bool(
            len(sites) == 1
            and sites[0][0] == "import_from"
            and isinstance(sites[0][1], ast.ImportFrom)
            and sites[0][1].module == module
            and sites[0][1].level == level
            and sites[0][2] is not None
            and sites[0][2].name == name
            and sites[0][2].asname is None
        )

    class_sites = _module_scope_direct_binding_sites(tree, "ReadApiSurface")
    tuple_sites = _module_scope_direct_binding_sites(tree, "READ_API_SURFACES")
    if not (
        import_binding_is("dataclass", "dataclasses", 0)
        and import_binding_is("READ_API_SURFACE_MODULES", "surface_routes", 1)
        and import_binding_is("READ_API_SURFACE_SUMMARIES", "surface_routes", 1)
        and len(class_sites) == 1
        and class_sites[0][0] == "local"
        and isinstance(class_sites[0][1], ast.ClassDef)
        and len(tuple_sites) == 1
        and tuple_sites[0][0] == "assignment"
        and isinstance(tuple_sites[0][1], ast.AnnAssign)
        and tuple_sites[0][1].value is not None
    ):
        return False

    record_class = class_sites[0][1]
    if not isinstance(record_class, ast.ClassDef):
        return False
    if not (
        not record_class.bases
        and not record_class.keywords
        and not getattr(record_class, "type_params", ())
        and len(record_class.decorator_list) == 1
    ):
        return False
    decorator = record_class.decorator_list[0]
    if not (
        isinstance(decorator, ast.Call)
        and _source_ast_name_is(decorator.func, "dataclass")
        and not decorator.args
        and len(decorator.keywords) == 2
        and decorator.keywords[0].arg == "frozen"
        and isinstance(decorator.keywords[0].value, ast.Constant)
        and decorator.keywords[0].value.value is True
        and decorator.keywords[1].arg == "slots"
        and isinstance(decorator.keywords[1].value, ast.Constant)
        and decorator.keywords[1].value.value is True
    ):
        return False
    body = [
        statement
        for statement in record_class.body
        if not (
            isinstance(statement, ast.Expr)
            and isinstance(statement.value, ast.Constant)
            and type(statement.value.value) is str
        )
    ]
    if len(body) != len(_READ_API_SURFACE_FIELDS):
        return False
    for statement, field_name in zip(body, _READ_API_SURFACE_FIELDS, strict=True):
        if not (
            isinstance(statement, ast.AnnAssign)
            and isinstance(statement.target, ast.Name)
            and statement.target.id == field_name
            and _source_ast_name_is(statement.annotation, "str")
            and statement.value is None
        ):
            return False

    tuple_declaration = tuple_sites[0][1]
    if not isinstance(tuple_declaration, ast.AnnAssign):
        return False
    annotation = tuple_declaration.annotation
    if not (
        isinstance(annotation, ast.Subscript)
        and _source_ast_name_is(annotation.value, "tuple")
        and isinstance(annotation.slice, ast.Tuple)
        and len(annotation.slice.elts) == 2
        and _source_ast_name_is(annotation.slice.elts[0], "ReadApiSurface")
        and isinstance(annotation.slice.elts[1], ast.Constant)
        and annotation.slice.elts[1].value is Ellipsis
    ):
        return False
    value = tuple_declaration.value
    if not (
        isinstance(value, ast.Call)
        and _source_ast_name_is(value.func, "tuple")
        and len(value.args) == 1
        and not value.keywords
        and isinstance(value.args[0], ast.GeneratorExp)
    ):
        return False
    generator = value.args[0]
    record_call = generator.elt
    if not (
        isinstance(record_call, ast.Call)
        and _source_ast_name_is(record_call.func, "ReadApiSurface")
        and not record_call.args
        and len(record_call.keywords) == 3
        and record_call.keywords[0].arg == "name"
        and _source_ast_name_is(record_call.keywords[0].value, "name")
        and record_call.keywords[1].arg == "module"
        and _source_ast_name_is(record_call.keywords[1].value, "module")
        and record_call.keywords[2].arg == "summary"
        and isinstance(record_call.keywords[2].value, ast.Subscript)
        and _source_ast_name_is(record_call.keywords[2].value.value, "READ_API_SURFACE_SUMMARIES")
        and _source_ast_name_is(record_call.keywords[2].value.slice, "name")
        and len(generator.generators) == 1
    ):
        return False
    clause = generator.generators[0]
    return bool(
        isinstance(clause.target, ast.Tuple)
        and len(clause.target.elts) == 2
        and all(isinstance(item, ast.Name) for item in clause.target.elts)
        and tuple(item.id for item in clause.target.elts) == ("name", "module")
        and isinstance(clause.iter, ast.Call)
        and isinstance(clause.iter.func, ast.Attribute)
        and _source_ast_name_is(clause.iter.func.value, "READ_API_SURFACE_MODULES")
        and clause.iter.func.attr == "items"
        and not clause.iter.args
        and not clause.iter.keywords
        and not clause.ifs
        and clause.is_async == 0
    )


def _read_api_surface_source_binding_supported(
    module_name: str,
    export_name: str,
    tree: ast.Module,
) -> bool:
    """Admit only the pinned route-record source declaration shape."""

    return bool(
        module_name == _READ_API_SURFACES_MODULE
        and export_name in {"ReadApiSurface", "READ_API_SURFACES"}
        and _read_api_surface_source_declaration_supported(tree)
    )


def _read_api_surface_literal_map(tree: ast.Module, name: str) -> dict[str, str]:
    """Read one unique direct literal map from exact parsed source bytes."""

    sites = _module_scope_direct_binding_sites(tree, name)
    if (
        len(sites) != 1
        or sites[0][0] != "assignment"
        or not isinstance(sites[0][1], (ast.Assign, ast.AnnAssign))
    ):
        raise ConfidenceLedgerError("canonical_loaded_runtime_mismatch")
    statement = sites[0][1]
    value = statement.value
    if not isinstance(value, ast.Dict):
        raise ConfidenceLedgerError("canonical_loaded_runtime_mismatch")
    parsed = _literal_source_expression(value, {})
    if (
        type(parsed) is not dict
        or not parsed
        or any(type(key) is not str or type(item) is not str for key, item in parsed.items())
        or len(parsed) != len(value.keys)
    ):
        raise ConfidenceLedgerError("canonical_loaded_runtime_mismatch")
    return parsed


def _append_source_identity_reference(
    references: list[_FacadeRuntimeBindingReference] | None,
    *,
    binding_module_name: str,
    symbol: str,
    binding_module: types.ModuleType,
    provider_module_name: str,
    provider_module: types.ModuleType,
    provider_value: object,
    importer_module_name: str,
    importer_module: types.ModuleType,
) -> None:
    if references is None:
        return
    references.append(
        (
            binding_module_name,
            symbol,
            binding_module,
            provider_module_name,
            provider_module,
            symbol,
            provider_value,
            importer_module_name,
            symbol,
            importer_module,
            "module_value",
            "<module>",
            importer_module,
            None,
            None,
            importer_module,
        )
    )


def _read_api_surface_runtime_identity_projection(
    repo_root: Path,
    closure_by_name: Mapping[str, str],
    source_rows: Mapping[
        str,
        tuple[ast.Module, _LiteralModuleGetattrProviderIndex, dict[str, dict[str, object]]],
    ],
    *,
    runtime_binding_references: list[_FacadeRuntimeBindingReference] | None,
) -> dict[str, object] | None:
    """Compare the loaded read_api route records to independent literal source values."""

    if _READ_API_SURFACES_MODULE not in closure_by_name:
        return None
    required_modules = (
        _READ_API_SURFACES_MODULE,
        _READ_API_SURFACE_ROUTES_MODULE,
        _READ_API_PACKAGE_MODULE,
    )
    if any(name not in closure_by_name or name not in source_rows for name in required_modules):
        raise ConfidenceLedgerError("canonical_loaded_runtime_mismatch")
    surfaces_tree = source_rows[_READ_API_SURFACES_MODULE][0]
    routes_tree = source_rows[_READ_API_SURFACE_ROUTES_MODULE][0]
    if not _read_api_surface_source_declaration_supported(surfaces_tree):
        raise ConfidenceLedgerError(
            "canonical_loaded_runtime_mismatch",
            "unsupported source-owned read_api surface declaration",
        )
    expected_modules = _read_api_surface_literal_map(routes_tree, "READ_API_SURFACE_MODULES")
    expected_summaries = _read_api_surface_literal_map(routes_tree, "READ_API_SURFACE_SUMMARIES")
    if tuple(expected_modules) != tuple(expected_summaries):
        raise ConfidenceLedgerError("canonical_loaded_runtime_mismatch")
    loaded_modules = {name: sys.modules.get(name) for name in required_modules}
    if any(type(module) is not types.ModuleType for module in loaded_modules.values()):
        raise ConfidenceLedgerError("canonical_loaded_runtime_mismatch")
    routes_module = loaded_modules[_READ_API_SURFACE_ROUTES_MODULE]
    surfaces_module = loaded_modules[_READ_API_SURFACES_MODULE]
    package_module = loaded_modules[_READ_API_PACKAGE_MODULE]
    if not all(
        isinstance(module, types.ModuleType)
        for module in (routes_module, surfaces_module, package_module)
    ):
        raise ConfidenceLedgerError("canonical_loaded_runtime_mismatch")

    for module_name in required_modules:
        loaded_module = loaded_modules[module_name]
        if not isinstance(loaded_module, types.ModuleType):
            raise ConfidenceLedgerError("canonical_loaded_runtime_mismatch")
        expected_path = (repo_root / closure_by_name[module_name]).resolve()
        try:
            loaded_path = Path(loaded_module.__file__).resolve()
        except (AttributeError, OSError, TypeError, ValueError) as exc:
            raise ConfidenceLedgerError(
                "canonical_loaded_runtime_mismatch",
                f"read_api source origin is invalid: {module_name}",
            ) from exc
        if loaded_path != expected_path:
            raise ConfidenceLedgerError(
                "canonical_loaded_runtime_mismatch",
                f"read_api source origin differs: {module_name}",
            )

    route_namespace = vars(routes_module)
    source_namespace = vars(surfaces_module)
    package_namespace = vars(package_module)
    observed_modules = route_namespace.get("READ_API_SURFACE_MODULES")
    observed_summaries = route_namespace.get("READ_API_SURFACE_SUMMARIES")
    if not (
        type(observed_modules) is dict
        and tuple(observed_modules.items()) == tuple(expected_modules.items())
        and type(observed_summaries) is dict
        and tuple(observed_summaries.items()) == tuple(expected_summaries.items())
        and source_namespace.get("READ_API_SURFACE_MODULES") is observed_modules
        and source_namespace.get("READ_API_SURFACE_SUMMARIES") is observed_summaries
        and package_namespace.get("_READ_API_SURFACE_MODULES") is observed_modules
    ):
        raise ConfidenceLedgerError("canonical_loaded_runtime_mismatch")

    surface_class = source_namespace.get("ReadApiSurface")
    surface_rows = source_namespace.get("READ_API_SURFACES")
    if not (
        type(surface_class) is type
        and type(surface_rows) is tuple
        and type(source_namespace.get("dataclass")) is type(dataclass)
        and source_namespace.get("dataclass") is dataclass
        and _dataclasses.is_dataclass(surface_class)
        and type.__getattribute__(surface_class, "__module__") == _READ_API_SURFACES_MODULE
        and type.__getattribute__(surface_class, "__qualname__") == "ReadApiSurface"
        and type.__getattribute__(surface_class, "__slots__") == _READ_API_SURFACE_FIELDS
    ):
        raise ConfidenceLedgerError("canonical_loaded_runtime_mismatch")
    parameters = type.__getattribute__(surface_class, "__dict__").get("__dataclass_params__")
    if parameters is None or getattr(parameters, "frozen", None) is not True:
        raise ConfidenceLedgerError("canonical_loaded_runtime_mismatch")
    dataclass_fields = _dataclasses.fields(surface_class)
    if tuple(field.name for field in dataclass_fields) != _READ_API_SURFACE_FIELDS:
        raise ConfidenceLedgerError("canonical_loaded_runtime_mismatch")
    for field in dataclass_fields:
        if not (field.type is str or (type(field.type) is str and field.type == "str")) or not (
            field.default is _dataclasses.MISSING
            and field.default_factory is _dataclasses.MISSING
            and field.init
            and field.repr
            and field.compare
        ):
            raise ConfidenceLedgerError("canonical_loaded_runtime_mismatch")

    expected_rows = tuple(
        (name, expected_modules[name], expected_summaries[name]) for name in expected_modules
    )
    observed_rows: list[tuple[str, str, str]] = []
    if len(surface_rows) != len(expected_rows):
        raise ConfidenceLedgerError("canonical_loaded_runtime_mismatch")
    for row in surface_rows:
        if type(row) is not surface_class:
            raise ConfidenceLedgerError("canonical_loaded_runtime_mismatch")
        values = tuple(object.__getattribute__(row, name) for name in _READ_API_SURFACE_FIELDS)
        if any(type(value) is not str for value in values):
            raise ConfidenceLedgerError("canonical_loaded_runtime_mismatch")
        observed_rows.append(values)
    if tuple(observed_rows) != expected_rows:
        raise ConfidenceLedgerError("canonical_loaded_runtime_mismatch")

    for name, expected_value in (
        ("ReadApiSurface", surface_class),
        ("READ_API_SURFACES", surface_rows),
    ):
        if package_namespace.get(name) is not expected_value:
            raise ConfidenceLedgerError("canonical_loaded_runtime_mismatch")
        _append_source_identity_reference(
            runtime_binding_references,
            binding_module_name=_READ_API_SURFACES_MODULE,
            symbol=name,
            binding_module=surfaces_module,
            provider_module_name=_READ_API_SURFACES_MODULE,
            provider_module=surfaces_module,
            provider_value=expected_value,
            importer_module_name=_READ_API_SURFACES_MODULE,
            importer_module=surfaces_module,
        )
        _append_source_identity_reference(
            runtime_binding_references,
            binding_module_name=_READ_API_PACKAGE_MODULE,
            symbol=name,
            binding_module=package_module,
            provider_module_name=_READ_API_SURFACES_MODULE,
            provider_module=surfaces_module,
            provider_value=expected_value,
            importer_module_name=_READ_API_PACKAGE_MODULE,
            importer_module=package_module,
        )
    return {
        "routes": [
            {"name": name, "module": module, "summary": expected_summaries[name]}
            for name, module in expected_modules.items()
        ],
        "surface_count": len(expected_rows),
        "source_owner_status": "recomputed",
    }


class _ProviderSourceGraphReconciliation:
    """Track identity bindings and completed comparisons for one provider graph."""

    __slots__ = ("active_pairs", "expected_to_live", "verified_pairs")

    def __init__(self) -> None:
        self.expected_to_live: dict[int, object] = {}
        self.active_pairs: set[tuple[int, int]] = set()
        self.verified_pairs: set[tuple[int, int]] = set()

    @staticmethod
    def _is_primitive(value: object) -> bool:
        return type(value) in {str, int, bool, float, bytes, type(None)}

    def bind(self, expected: object, actual: object) -> bool:
        if self._is_primitive(expected):
            return True
        previous = self.expected_to_live.get(id(expected), _SOURCE_DERIVATION_FAILED)
        if previous is not _SOURCE_DERIVATION_FAILED:
            return previous is actual
        self.expected_to_live[id(expected)] = actual
        return True

    def enter(self, expected: object, actual: object) -> bool | None:
        """Return false for alias conflicts, true for active/verified pairs, else None."""
        if not self.bind(expected, actual):
            return False
        pair = (id(actual), id(expected))
        if pair in self.verified_pairs or pair in self.active_pairs:
            return True
        self.active_pairs.add(pair)
        return None

    def finish(self, expected: object, actual: object, matched: bool) -> None:
        """Close one active pair and memoize it only after a complete match."""
        pair = (id(actual), id(expected))
        self.active_pairs.discard(pair)
        if matched:
            self.verified_pairs.add(pair)


_PYTHON_DATACLASS_TRANSFORM_KEY = "python.stdlib.dataclasses.dataclass"


def _python_dataclass_transform_source_projection() -> dict[str, object]:
    """Reconcile consumed stdlib dataclass bindings to an isolated source execution."""

    provider = sys.modules.get("dataclasses")
    if type(provider) is not types.ModuleType or provider is not _dataclasses:
        raise ConfidenceLedgerError("canonical_loaded_runtime_mismatch")
    provider_namespace = vars(provider)
    provider_path_value = getattr(provider, "__file__", None)
    if type(provider_path_value) is not str:
        raise ConfidenceLedgerError("canonical_loaded_runtime_mismatch")
    try:
        provider_path = Path(provider_path_value).resolve()
        stdlib_root = Path(sysconfig.get_path("stdlib")).resolve()
        relative_provider_path = provider_path.relative_to(stdlib_root)
    except (OSError, TypeError, ValueError) as exc:
        raise ConfidenceLedgerError("canonical_loaded_runtime_mismatch") from exc
    if relative_provider_path.as_posix() != "dataclasses.py":
        raise ConfidenceLedgerError("canonical_loaded_runtime_mismatch")
    if types.MappingProxyType is not type(type.__dict__):
        raise ConfidenceLedgerError("canonical_loaded_runtime_mismatch")
    analysis = _active_integrity_analysis()
    try:
        source_bytes = (
            analysis.source_bytes(provider_path)
            if analysis is not None
            else provider_path.read_bytes()
        )
        provider_tree = ast.parse(source_bytes, filename=relative_provider_path.as_posix())
        provider_code = compile(
            source_bytes,
            str(provider_path),
            "exec",
            dont_inherit=True,
            optimize=sys.flags.optimize,
        )
    except (OSError, SyntaxError, TypeError, ValueError) as exc:
        raise ConfidenceLedgerError("canonical_loaded_runtime_mismatch") from exc
    if not isinstance(provider_code, types.CodeType):
        raise ConfidenceLedgerError("canonical_loaded_runtime_mismatch")

    live_dataclasses_binding = sys.modules.get("dataclasses")
    isolated_provider = types.ModuleType("dataclasses")
    isolated_namespace = vars(isolated_provider)
    isolated_namespace.update(
        {
            "__name__": "dataclasses",
            "__package__": "",
            "__file__": str(provider_path),
            "__cached__": None,
            "__loader__": getattr(provider, "__loader__", None),
            "__spec__": getattr(provider, "__spec__", None),
        }
    )
    isolated_modules = dict(sys.modules)
    isolated_modules["dataclasses"] = isolated_provider
    isolated_sys = types.ModuleType("sys")
    isolated_sys.__dict__.update(vars(sys))
    isolated_sys.modules = isolated_modules
    real_import = _builtins.__import__

    def isolated_import(
        name: str,
        globals: dict[str, object] | None = None,
        locals: dict[str, object] | None = None,
        fromlist: tuple[str, ...] = (),
        level: int = 0,
    ) -> object:
        if level == 0 and name == "sys":
            return isolated_sys
        return real_import(name, globals, locals, fromlist, level)

    isolated_builtins = dict(vars(_builtins))
    isolated_builtins["__import__"] = isolated_import
    isolated_namespace["__builtins__"] = isolated_builtins
    try:
        exec(provider_code, isolated_namespace)  # noqa: S102
    except Exception as exc:
        raise ConfidenceLedgerError("canonical_loaded_runtime_mismatch") from exc
    if (
        sys.modules.get("dataclasses") is not live_dataclasses_binding
        or live_dataclasses_binding is not provider
        or isolated_namespace.get("sys") is not isolated_sys
        or isolated_namespace.get("types") is not types
    ):
        raise ConfidenceLedgerError("canonical_loaded_runtime_mismatch")

    source_code_hashes = _loader_code_hashes_by_qualname(provider_code)
    source_function_names = {
        statement.name
        for statement in provider_tree.body
        if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    source_class_names = {
        statement.name for statement in provider_tree.body if isinstance(statement, ast.ClassDef)
    }
    source_functions = {name: isolated_namespace.get(name) for name in ("dataclass", "field")}
    if any(type(function) is not types.FunctionType for function in source_functions.values()):
        raise ConfidenceLedgerError("canonical_loaded_runtime_mismatch")

    consumed_global_names: set[str] = set()
    consumed_load_global_names: set[str] = set()
    consumed_builtin_names: set[str] = set()
    consumed_class_names: set[str] = set()
    consumed_class_bindings: set[str] = set()
    helper_bindings: dict[str, dict[str, str]] = {}
    global_bindings: dict[str, object] = {}
    source_graph = _ProviderSourceGraphReconciliation()

    def code_load_global_names(code: types.CodeType) -> tuple[str, ...] | None:
        names: set[str] = set()
        pending = [code]
        visited_code: set[int] = set()
        while pending:
            current = pending.pop()
            if id(current) in visited_code:
                continue
            visited_code.add(id(current))
            try:
                instructions = dis.get_instructions(current)
            except (TypeError, ValueError):
                return None
            for instruction in instructions:
                if instruction.opname == "LOAD_GLOBAL":
                    if type(instruction.argval) is not str:
                        return None
                    names.add(instruction.argval)
                elif instruction.opname in {
                    "LOAD_NAME",
                    "LOAD_CLASSDEREF",
                    "LOAD_FROM_DICT_OR_GLOBALS",
                }:
                    return None
            pending.extend(
                constant for constant in current.co_consts if type(constant) is types.CodeType
            )
        return tuple(sorted(names))

    def bind_expected(expected: object, actual: object) -> bool:
        return source_graph.bind(expected, actual)

    def provider_value_matches(actual: object, expected: object, *, depth: int = 0) -> bool:
        if depth > 40:
            return False
        if type(expected) in {str, int, bool, float, bytes, type(None)}:
            return _provider_value_matches_contents(actual, expected, depth=depth)
        if type(expected) is types.FunctionType and (
            expected.__module__ == "dataclasses" and expected.__globals__ is isolated_namespace
        ):
            return visit_function(f"binding:{expected.__qualname__}", actual, expected)
        if (
            type(expected) is type
            and expected.__module__ == "dataclasses"
            and expected.__qualname__ in source_code_hashes
        ):
            return visit_class(expected.__qualname__, actual, expected)
        state = source_graph.enter(expected, actual)
        if state is not None:
            return state
        matched = False
        try:
            matched = _provider_value_matches_contents(actual, expected, depth=depth)
        except Exception:
            matched = False
        finally:
            source_graph.finish(expected, actual, matched)
        return matched

    def _provider_value_matches_contents(actual: object, expected: object, *, depth: int) -> bool:
        if actual is expected:
            return True
        if type(expected) is types.ModuleType:
            if expected is not isolated_sys:
                return actual is expected
            if actual is not sys:
                return False
            actual_namespace = vars(sys)
            expected_namespace = vars(isolated_sys)
            if set(actual_namespace) != set(expected_namespace) or any(
                actual_namespace[name] is not expected_namespace[name]
                for name in expected_namespace
                if name != "modules"
            ):
                return False
            actual_modules = actual_namespace.get("modules")
            expected_modules = expected_namespace.get("modules")
            if (
                type(actual_modules) is not dict
                or type(expected_modules) is not dict
                or set(actual_modules) != set(expected_modules)
            ):
                return False
            for name, expected_module in expected_modules.items():
                actual_module = actual_modules[name]
                if name == "dataclasses":
                    if expected_module is not isolated_provider or actual_module is not provider:
                        return False
                elif actual_module is not expected_module:
                    return False
            return True
        if type(expected) is types.FunctionType:
            if expected.__module__ == "dataclasses" and expected.__globals__ is isolated_namespace:
                return visit_function(
                    f"binding:{expected.__qualname__}",
                    actual,
                    expected,
                )
            if (
                type(actual) is not types.FunctionType
                or actual.__globals__ is not expected.__globals__
            ):
                return False
            if (
                _normalize_code_object(actual.__code__) != _normalize_code_object(expected.__code__)
                or actual.__module__ != expected.__module__
                or actual.__name__ != expected.__name__
                or actual.__qualname__ != expected.__qualname__
                or actual.__doc__ != expected.__doc__
                or actual.__code__.co_freevars != expected.__code__.co_freevars
                or not bind_expected(expected, actual)
            ):
                return False
            actual_closure = actual.__closure__ or ()
            expected_closure = expected.__closure__ or ()
            if len(actual_closure) != len(expected_closure) or not all(
                provider_value_matches(left.cell_contents, right.cell_contents, depth=depth + 1)
                for left, right in zip(actual_closure, expected_closure, strict=True)
            ):
                return False
            return all(
                provider_value_matches(
                    getattr(actual, attribute, None),
                    getattr(expected, attribute, None),
                    depth=depth + 1,
                )
                for attribute in ("__defaults__", "__kwdefaults__", "__annotations__", "__dict__")
            )
        if type(expected) is type:
            if type(actual) is not type:
                return False
            if expected.__module__ == "dataclasses" and expected.__qualname__ in source_code_hashes:
                return visit_class(expected.__qualname__, actual, expected)
            return actual is expected
        if type(expected) in {types.MemberDescriptorType, types.GetSetDescriptorType}:
            if type(actual) is not type(expected):
                return False
            return actual.__name__ == expected.__name__ and provider_value_matches(
                actual.__objclass__,
                expected.__objclass__,
                depth=depth + 1,
            )
        if type(expected) in {classmethod, staticmethod}:
            return type(actual) is type(expected) and provider_value_matches(
                actual.__func__,
                expected.__func__,
                depth=depth + 1,
            )
        if type(expected) is property:
            if type(actual) is not property:
                return False
            return all(
                provider_value_matches(
                    getattr(actual, attribute, _SOURCE_DERIVATION_FAILED),
                    getattr(expected, attribute, _SOURCE_DERIVATION_FAILED),
                    depth=depth + 1,
                )
                for attribute in ("fget", "fset", "fdel", "__doc__")
            )
        if type(expected).__module__ == "re" and type(expected).__name__ == "Pattern":
            return (
                type(actual) is type(expected)
                and actual.pattern == expected.pattern
                and actual.flags == expected.flags
                and actual.groups == expected.groups
                and dict(actual.groupindex) == dict(expected.groupindex)
            )
        if type(expected) in {str, int, bool, bytes, type(None)}:
            return type(actual) is type(expected) and actual == expected
        if type(expected) is float:
            return type(actual) is float and actual.hex() == expected.hex()
        if type(expected) in {tuple, list}:
            return (
                type(actual) is type(expected)
                and len(actual) == len(expected)
                and all(
                    provider_value_matches(left, right, depth=depth + 1)
                    for left, right in zip(actual, expected, strict=True)
                )
            )
        if type(expected) is dict:
            return (
                type(actual) is dict
                and len(actual) == len(expected)
                and all(
                    key in actual and provider_value_matches(actual[key], value, depth=depth + 1)
                    for key, value in expected.items()
                )
            )
        if type(expected) is type(type.__dict__):
            if type(actual) is not type(expected) or len(actual) != len(expected):
                return False
            return all(
                key in actual and provider_value_matches(actual[key], value, depth=depth + 1)
                for key, value in expected.items()
            )
        if type(expected) in {set, frozenset}:
            return type(actual) is type(expected) and _normalize_runtime_binding_value(
                actual, seen=set()
            ) == _normalize_runtime_binding_value(expected, seen=set())
        expected_type = type(expected)
        if expected_type.__module__ == "dataclasses":
            if not provider_value_matches(type(actual), expected_type, depth=depth + 1):
                return False
            if not bind_expected(expected, actual):
                return False
            try:
                actual_state = object.__getattribute__(actual, "__dict__")
                expected_state = object.__getattribute__(expected, "__dict__")
            except AttributeError:
                try:
                    return repr(actual) == repr(expected)
                except Exception:
                    return False
            return (
                type(actual_state) is dict
                and type(expected_state) is dict
                and provider_value_matches(actual_state, expected_state, depth=depth + 1)
            )
        return actual is expected

    def visit_function(label: str, actual: object, expected: object) -> bool:
        state = source_graph.enter(expected, actual)
        if state is not None:
            return state
        matched = False
        try:
            matched = _visit_function_contents(label, actual, expected)
        finally:
            source_graph.finish(expected, actual, matched)
        return matched

    def _visit_function_contents(label: str, actual: object, expected: object) -> bool:
        if type(actual) is not types.FunctionType or type(expected) is not types.FunctionType:
            return False
        if (
            expected.__module__ != "dataclasses"
            or expected.__globals__ is not isolated_namespace
            or actual.__module__ != "dataclasses"
            or actual.__globals__ is not provider_namespace
            or actual.__qualname__ != expected.__qualname__
            or actual.__name__ != expected.__name__
            or actual.__doc__ != expected.__doc__
            or actual.__code__.co_qualname != expected.__code__.co_qualname
        ):
            return False
        code_hash = _content_hash(_normalize_code_object(expected.__code__))
        expected_hashes = source_code_hashes.get(expected.__code__.co_qualname, ())
        if (
            code_hash not in expected_hashes
            or _content_hash(_normalize_code_object(actual.__code__)) != code_hash
        ):
            return False
        if not bind_expected(expected, actual):
            return False
        helper_bindings[label] = {
            "code_sha256": code_hash,
            "binding_sha256": _content_hash(_normalize_function_binding(actual)),
        }
        if actual.__code__.co_freevars != expected.__code__.co_freevars:
            return False
        actual_closure = actual.__closure__ or ()
        expected_closure = expected.__closure__ or ()
        if len(actual_closure) != len(expected_closure):
            return False
        if not all(
            provider_value_matches(left.cell_contents, right.cell_contents)
            for left, right in zip(actual_closure, expected_closure, strict=True)
        ):
            return False
        for attribute in ("__defaults__", "__kwdefaults__", "__annotations__", "__dict__"):
            if not provider_value_matches(
                getattr(actual, attribute, None),
                getattr(expected, attribute, None),
            ):
                return False
        global_names = code_load_global_names(expected.__code__)
        expected_builtins = expected.__builtins__
        actual_builtins = actual.__builtins__
        if (
            global_names is None
            or type(expected_builtins) is not dict
            or type(actual_builtins) is not dict
        ):
            return False
        for name in global_names:
            consumed_load_global_names.add(name)
            if name in isolated_namespace:
                consumed_global_names.add(name)
                if not visit_binding(name):
                    return False
                continue
            if name in provider_namespace:
                return False
            if name not in expected_builtins or name not in actual_builtins:
                return False
            if not provider_value_matches(actual_builtins[name], expected_builtins[name]):
                return False
            consumed_builtin_names.add(name)
        return True

    def visit_class(label: str, actual: object, expected: object) -> bool:
        state = source_graph.enter(expected, actual)
        if state is not None:
            return state
        matched = False
        try:
            matched = _visit_class_contents(label, actual, expected)
        finally:
            source_graph.finish(expected, actual, matched)
        return matched

    def _visit_class_contents(label: str, actual: object, expected: object) -> bool:
        if type(actual) is not type or type(expected) is not type:
            return False
        if (
            type.__getattribute__(expected, "__module__") != "dataclasses"
            or type.__getattribute__(actual, "__module__") != "dataclasses"
            or type.__getattribute__(actual, "__qualname__")
            != type.__getattribute__(expected, "__qualname__")
            or type.__getattribute__(actual, "__name__")
            != type.__getattribute__(expected, "__name__")
        ):
            return False
        if not bind_expected(expected, actual):
            return False
        consumed_class_names.add(label)
        actual_bases = type.__getattribute__(actual, "__bases__")
        expected_bases = type.__getattribute__(expected, "__bases__")
        if len(actual_bases) != len(expected_bases) or not all(
            provider_value_matches(left, right)
            for left, right in zip(actual_bases, expected_bases, strict=True)
        ):
            return False
        actual_namespace = type.__getattribute__(actual, "__dict__")
        expected_namespace = type.__getattribute__(expected, "__dict__")
        if set(actual_namespace) != set(expected_namespace):
            return False
        for name, expected_value in expected_namespace.items():
            actual_value = actual_namespace[name]
            if type(expected_value) is types.FunctionType and (
                expected_value.__module__ == "dataclasses"
                and expected_value.__globals__ is isolated_namespace
            ):
                if not visit_function(
                    f"{label}.{name}",
                    actual_value,
                    expected_value,
                ):
                    return False
            elif (
                type(expected_value) is type
                and expected_value.__module__ == "dataclasses"
                and expected_value.__qualname__ in source_code_hashes
            ):
                if not visit_class(
                    f"{label}.{name}",
                    actual_value,
                    expected_value,
                ):
                    return False
            elif not provider_value_matches(actual_value, expected_value):
                return False
        return True

    def visit_binding(name: str) -> bool:
        if name not in isolated_namespace:
            return True
        if name not in provider_namespace:
            return False
        expected = isolated_namespace[name]
        actual = provider_namespace[name]
        if type(expected) is types.FunctionType and (
            expected.__module__ == "dataclasses" and expected.__globals__ is isolated_namespace
        ):
            return visit_function(name, actual, expected)
        if (
            type(expected) is type
            and expected.__module__ == "dataclasses"
            and expected.__qualname__ in source_code_hashes
        ):
            consumed_class_bindings.add(name)
            return visit_class(name, actual, expected)
        if not bind_expected(expected, actual):
            return False
        if type(expected) is types.FunctionType and type(actual) is not types.FunctionType:
            return False
        if type(expected) is type and type(actual) is not type:
            return False
        if type(expected) is types.ModuleType and type(actual) is not types.ModuleType:
            return False
        if type(actual) is types.ModuleType:
            rendered: object = {"module": actual.__name__}
        elif type(actual) is types.FunctionType:
            rendered = {
                "function_module": actual.__module__,
                "function_qualname": actual.__qualname__,
                "function_code_sha256": _content_hash(_normalize_code_object(actual.__code__)),
                "function_binding_sha256": _content_hash(_normalize_function_binding(actual)),
            }
        elif type(actual) is type:
            rendered = {"type": _runtime_type_ref(actual)}
        else:
            rendered = _normalize_runtime_binding_value(actual, seen={id(provider)})
        global_bindings[name] = rendered
        return provider_value_matches(actual, expected)

    for symbol, function in source_functions.items():
        if (
            type(function) is not types.FunctionType
            or function.__module__ != "dataclasses"
            or function.__qualname__ != symbol
            or function.__globals__ is not isolated_namespace
        ):
            raise ConfidenceLedgerError("canonical_loaded_runtime_mismatch")
        actual_function = provider_namespace.get(symbol)
        if not visit_function(symbol, actual_function, function):
            raise ConfidenceLedgerError("canonical_loaded_runtime_mismatch")
    for class_name in sorted(source_class_names):
        if not visit_class(
            class_name,
            provider_namespace.get(class_name),
            isolated_namespace.get(class_name),
        ):
            raise ConfidenceLedgerError("canonical_loaded_runtime_mismatch")
    if not source_functions.keys() <= {
        name for name in helper_bindings if name in source_function_names
    }:
        raise ConfidenceLedgerError("canonical_loaded_runtime_mismatch")
    if sys.modules.get("dataclasses") is not provider:
        raise ConfidenceLedgerError("canonical_loaded_runtime_mismatch")
    return {
        "provider_module": "dataclasses",
        "provider_symbol": "dataclass",
        "provider_symbols": ("dataclass", "field"),
        "provider_relative_path": relative_provider_path.as_posix(),
        "provider_source_sha256": _bytes_hash(source_bytes),
        "provider_code_sha256": helper_bindings["dataclass"]["code_sha256"],
        "field_code_sha256": helper_bindings["field"]["code_sha256"],
        "helper_bindings": helper_bindings,
        "global_bindings": global_bindings,
        "consumed_global_names": tuple(sorted(consumed_global_names)),
        "consumed_class_binding_names": tuple(sorted(consumed_class_bindings)),
        "provider_source_class_names": tuple(sorted(source_class_names)),
        "consumed_source_class_labels": tuple(sorted(consumed_class_names)),
        "consumed_load_global_names": tuple(sorted(consumed_load_global_names)),
        "consumed_builtin_names": tuple(sorted(consumed_builtin_names)),
        "provider_load_global_binding_count": len(consumed_load_global_names),
        "provider_builtin_binding_count": len(consumed_builtin_names),
        "provider_global_binding_count": len(global_bindings) + len(consumed_class_bindings),
        "provider_class_binding_count": len(source_class_names),
    }


def _source_dataclass_transform_options(
    tree: ast.Module,
    statement: ast.ClassDef,
) -> tuple[str, dict[str, bool]] | None:
    """Resolve one direct stdlib dataclass import and a literal option set."""

    if len(statement.decorator_list) != 1:
        return None
    decorator = statement.decorator_list[0]
    if isinstance(decorator, ast.Name):
        decorator_name = decorator.id
        options: dict[str, bool] = {}
    elif isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Name):
        decorator_name = decorator.func.id
        if decorator.args:
            return None
        options = {}
        supported_options = {
            "init",
            "repr",
            "eq",
            "order",
            "unsafe_hash",
            "frozen",
            "match_args",
            "kw_only",
            "slots",
            "weakref_slot",
        }
        for keyword in decorator.keywords:
            if (
                keyword.arg is None
                or keyword.arg not in supported_options
                or keyword.arg in options
                or not isinstance(keyword.value, ast.Constant)
                or type(keyword.value.value) is not bool
            ):
                return None
            options[keyword.arg] = keyword.value.value
    else:
        return None
    sites = _module_scope_direct_binding_sites(tree, decorator_name)
    if not (
        len(sites) == 1
        and sites[0][0] == "import_from"
        and isinstance(sites[0][1], ast.ImportFrom)
        and sites[0][1].module == "dataclasses"
        and sites[0][1].level == 0
        and sites[0][2] is not None
        and sites[0][2].name == "dataclass"
        and sites[0][2].asname in {None, decorator_name}
    ):
        return None
    return decorator_name, options


def _source_dataclass_safe_literal(value: object, *, depth: int = 0) -> bool:
    """Accept only bounded inert values for source-replayed dataclass defaults."""

    if depth > 40:
        return False
    if type(value) in {str, int, bool, float, bytes, type(None)}:
        return True
    if type(value) in {tuple, list, set, frozenset}:
        return len(value) <= 10000 and all(
            _source_dataclass_safe_literal(item, depth=depth + 1) for item in value
        )
    if type(value) is dict:
        return len(value) <= 10000 and all(
            _source_dataclass_safe_literal(key, depth=depth + 1)
            and _source_dataclass_safe_literal(item, depth=depth + 1)
            for key, item in value.items()
        )
    return False


def _source_dataclass_enum_member(
    node: ast.Attribute,
    *,
    tree: ast.Module,
    module: types.ModuleType,
    module_name: str,
) -> object:
    """Resolve one member only from a simple source-owned string Enum declaration."""

    if not isinstance(node.value, ast.Name):
        return _SOURCE_DERIVATION_FAILED
    enum_name = node.value.id
    sites = _module_scope_direct_binding_sites(tree, enum_name)
    if not (len(sites) == 1 and sites[0][0] == "local" and isinstance(sites[0][1], ast.ClassDef)):
        return _SOURCE_DERIVATION_FAILED
    statement = sites[0][1]
    if not (
        not statement.decorator_list
        and len(statement.bases) == 2
        and all(isinstance(base, ast.Name) for base in statement.bases)
        and tuple(base.id for base in statement.bases) == ("str", "Enum")
        and not statement.keywords
        and not getattr(statement, "type_params", ())
        and _source_import_binding(
            "str",
            tree=tree,
            module=module,
            module_name=module_name,
        )
        is _builtins.str
        and _source_import_binding(
            "Enum",
            tree=tree,
            module=module,
            module_name=module_name,
        )
        is Enum
    ):
        return _SOURCE_DERIVATION_FAILED
    members: dict[str, str] = {}
    for member in statement.body:
        if (
            isinstance(member, ast.Expr)
            and isinstance(member.value, ast.Constant)
            and type(member.value.value) is str
        ):
            continue
        if isinstance(member, ast.Assign) and len(member.targets) == 1:
            target = member.targets[0]
        elif (
            isinstance(member, ast.AnnAssign)
            and isinstance(member.target, ast.Name)
            and member.value is not None
        ):
            target = member.target
        else:
            return _SOURCE_DERIVATION_FAILED
        if not isinstance(target, ast.Name) or target.id in members:
            return _SOURCE_DERIVATION_FAILED
        try:
            value = ast.literal_eval(member.value)
        except (ValueError, TypeError, SyntaxError, MemoryError):
            return _SOURCE_DERIVATION_FAILED
        if type(value) is not str:
            return _SOURCE_DERIVATION_FAILED
        members[target.id] = value
    actual_enum = vars(module).get(enum_name)
    if not (
        members
        and type(actual_enum) is type(Enum)
        and actual_enum.__module__ == module_name
        and actual_enum.__qualname__ == enum_name
        and str in actual_enum.__mro__
        and Enum in actual_enum.__mro__
    ):
        return _SOURCE_DERIVATION_FAILED
    actual_members = actual_enum.__members__
    if tuple(actual_members) != tuple(members):
        return _SOURCE_DERIVATION_FAILED
    for name, value in members.items():
        actual_member = actual_members.get(name)
        if (
            type(actual_member) is not actual_enum
            or actual_member.value != value
            or type(actual_member.value) is not str
        ):
            return _SOURCE_DERIVATION_FAILED
    return actual_members.get(node.attr, _SOURCE_DERIVATION_FAILED)


def _source_dataclass_value(
    node: ast.expr,
    *,
    tree: ast.Module,
    module: types.ModuleType,
    module_name: str,
    depth: int = 0,
) -> object:
    """Evaluate only source literals, exact builtins, Enum members, and dataclasses.field."""

    if depth > 40:
        return _SOURCE_DERIVATION_FAILED
    try:
        literal = ast.literal_eval(node)
    except (ValueError, TypeError, SyntaxError, MemoryError):
        literal = _SOURCE_DERIVATION_FAILED
    if literal is not _SOURCE_DERIVATION_FAILED:
        return literal if _source_dataclass_safe_literal(literal) else _SOURCE_DERIVATION_FAILED
    if isinstance(node, ast.Attribute):
        return _source_dataclass_enum_member(
            node,
            tree=tree,
            module=module,
            module_name=module_name,
        )
    if isinstance(node, ast.Name):
        value = _source_import_binding(
            node.id,
            tree=tree,
            module=module,
            module_name=module_name,
        )
        safe_callables = (
            _builtins.dict,
            _builtins.list,
            _builtins.set,
            _builtins.tuple,
            _builtins.frozenset,
        )
        return value if any(value is item for item in safe_callables) else _SOURCE_DERIVATION_FAILED
    if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
        return _SOURCE_DERIVATION_FAILED
    function_name = node.func.id
    function = _source_import_binding(
        function_name,
        tree=tree,
        module=module,
        module_name=module_name,
    )
    if function is _SOURCE_DERIVATION_FAILED:
        return _SOURCE_DERIVATION_FAILED
    if function is _dataclasses.field:
        if node.args:
            return _SOURCE_DERIVATION_FAILED
        options: dict[str, object] = {}
        allowed = {
            "default",
            "default_factory",
            "init",
            "repr",
            "hash",
            "compare",
            "metadata",
            "kw_only",
        }
        for keyword in node.keywords:
            if keyword.arg is None or keyword.arg not in allowed or keyword.arg in options:
                return _SOURCE_DERIVATION_FAILED
            value = _source_dataclass_value(
                keyword.value,
                tree=tree,
                module=module,
                module_name=module_name,
                depth=depth + 1,
            )
            if value is _SOURCE_DERIVATION_FAILED:
                return _SOURCE_DERIVATION_FAILED
            if keyword.arg in {"init", "repr", "compare", "kw_only"} and type(value) is not bool:
                return _SOURCE_DERIVATION_FAILED
            if keyword.arg == "hash" and value is not None and type(value) is not bool:
                return _SOURCE_DERIVATION_FAILED
            if keyword.arg == "default_factory" and value not in {
                _builtins.dict,
                _builtins.list,
                _builtins.set,
                _builtins.tuple,
                _builtins.frozenset,
            }:
                return _SOURCE_DERIVATION_FAILED
            if keyword.arg == "metadata" and type(value) is not dict:
                return _SOURCE_DERIVATION_FAILED
            options[keyword.arg] = value
        try:
            return _dataclasses.field(**options)
        except (TypeError, ValueError):
            return _SOURCE_DERIVATION_FAILED
    if (
        function
        in {
            _builtins.dict,
            _builtins.list,
            _builtins.set,
            _builtins.tuple,
            _builtins.frozenset,
        }
        and not node.args
        and not node.keywords
    ):
        return function()
    return _SOURCE_DERIVATION_FAILED


def _source_dataclass_values_equal(actual: object, expected: object, *, depth: int = 0) -> bool:
    """Compare supported source values without invoking arbitrary equality methods."""

    if actual is expected:
        return True
    if depth > 40 or type(actual) is not type(expected):
        return False
    if type(actual) in {str, int, bool, bytes, type(None)}:
        return actual == expected
    if type(actual) is float:
        return actual.hex() == expected.hex()
    if type(actual) in {tuple, list}:
        return len(actual) == len(expected) and all(
            _source_dataclass_values_equal(left, right, depth=depth + 1)
            for left, right in zip(actual, expected, strict=True)
        )
    if type(actual) in {set, frozenset}:
        return _normalize_runtime_binding_value(actual, seen=set()) == (
            _normalize_runtime_binding_value(expected, seen=set())
        )
    if type(actual) is dict:
        return len(actual) == len(expected) and all(
            key in expected
            and _source_dataclass_values_equal(value, expected[key], depth=depth + 1)
            for key, value in actual.items()
        )
    if isinstance(actual, Enum) and type(actual) is type(expected):
        return actual.name == expected.name and _source_dataclass_values_equal(
            actual.value, expected.value, depth=depth + 1
        )
    return False


def _source_dataclass_fields_match(
    actual_fields: tuple[object, ...],
    expected_fields: tuple[object, ...],
) -> bool:
    # Compare every field slot emitted by the selected dataclass provider.
    field_slots = _dataclasses.Field.__slots__
    if type(field_slots) is str:
        field_slots = (field_slots,)
    if type(field_slots) is not tuple or any(type(name) is not str for name in field_slots):
        return False
    if len(actual_fields) != len(expected_fields):
        return False
    for actual, expected in zip(actual_fields, expected_fields, strict=True):
        if type(actual) is not _dataclasses.Field or type(expected) is not _dataclasses.Field:
            return False
        for name in field_slots:
            actual_value = getattr(actual, name, _SOURCE_DERIVATION_FAILED)
            expected_value = getattr(expected, name, _SOURCE_DERIVATION_FAILED)
            if (
                actual_value is _SOURCE_DERIVATION_FAILED
                or expected_value is _SOURCE_DERIVATION_FAILED
            ):
                return False
            if name == "default_factory":
                if actual_value is not expected_value:
                    return False
            elif name == "metadata":
                if type(actual_value) is not type(expected_value):
                    return False
                if not _source_dataclass_values_equal(dict(actual_value), dict(expected_value)):
                    return False
            elif not _source_dataclass_values_equal(actual_value, expected_value):
                return False
    return True


def _source_dataclass_function_globals_match(
    actual: types.FunctionType,
    expected: types.FunctionType,
) -> bool:
    """Bind only names executed by a generated function, without recursive global traversal."""

    actual_globals = actual.__globals__
    expected_globals = expected.__globals__
    if type(actual_globals) is not dict or type(expected_globals) is not dict:
        return False
    actual_builtins = actual_globals.get("__builtins__", _SOURCE_DERIVATION_FAILED)
    expected_builtins = expected_globals.get("__builtins__", _SOURCE_DERIVATION_FAILED)
    if actual_builtins is _SOURCE_DERIVATION_FAILED or actual_builtins is not expected_builtins:
        return False
    if type(actual_builtins) is dict:
        actual_builtins_namespace = actual_builtins
        expected_builtins_namespace = expected_builtins
    elif type(actual_builtins) is types.ModuleType:
        actual_builtins_namespace = vars(actual_builtins)
        expected_builtins_namespace = vars(expected_builtins)
    else:
        return False

    referenced_names: set[str] = set()

    def add_referenced_names(code: types.CodeType) -> None:
        referenced_names.update(code.co_names)
        for constant in code.co_consts:
            if isinstance(constant, types.CodeType):
                add_referenced_names(constant)

    add_referenced_names(actual.__code__)
    for name in referenced_names:
        if name in actual_globals or name in expected_globals:
            if name not in actual_globals or name not in expected_globals:
                return False
            actual_binding = actual_globals[name]
            expected_binding = expected_globals[name]
        else:
            if name not in actual_builtins_namespace or name not in expected_builtins_namespace:
                if name in actual_builtins_namespace or name in expected_builtins_namespace:
                    return False
                continue
            actual_binding = actual_builtins_namespace[name]
            expected_binding = expected_builtins_namespace[name]
        if actual_binding is expected_binding:
            continue
        if (
            type(actual_binding) is type(expected_binding)
            and type(actual_binding) in {str, int, bool, bytes, float, type(None)}
            and _source_dataclass_values_equal(actual_binding, expected_binding)
        ):
            continue
        return False
    return True


def _source_dataclass_runtime_output_matches(
    actual: object,
    expected: object,
    *,
    actual_class: type[object],
    expected_class: type[object],
    depth: int = 0,
    class_pairs: dict[int, type[object]] | None = None,
    source_method_names: frozenset[str] = frozenset(),
    source_method_function_ids: frozenset[int] = frozenset(),
) -> bool:
    pairs = {} if class_pairs is None else class_pairs
    if expected is expected_class:
        return actual is actual_class
    if actual is expected:
        return True
    if depth > 40 or type(actual) is not type(expected):
        return False
    if type(actual) is type:
        known_actual = pairs.get(id(expected))
        if id(expected) in pairs:
            return actual is known_actual
        if type.__getattribute__(actual, "__module__") != type.__getattribute__(
            expected, "__module__"
        ) or type.__getattribute__(actual, "__qualname__") != type.__getattribute__(
            expected, "__qualname__"
        ):
            return False
        pairs[id(expected)] = actual
        actual_bases = type.__getattribute__(actual, "__bases__")
        expected_bases = type.__getattribute__(expected, "__bases__")
        actual_mro = type.__getattribute__(actual, "__mro__")
        expected_mro = type.__getattribute__(expected, "__mro__")
        for actual_sequence, expected_sequence in (
            (actual_bases, expected_bases),
            (actual_mro, expected_mro),
        ):
            if len(actual_sequence) != len(expected_sequence) or not all(
                _source_dataclass_runtime_output_matches(
                    actual_item,
                    expected_item,
                    actual_class=actual_class,
                    expected_class=expected_class,
                    depth=depth + 1,
                    class_pairs=pairs,
                    source_method_names=source_method_names,
                    source_method_function_ids=source_method_function_ids,
                )
                for actual_item, expected_item in zip(
                    actual_sequence,
                    expected_sequence,
                    strict=True,
                )
            ):
                return False
        actual_namespace = type.__getattribute__(actual, "__dict__")
        expected_namespace = type.__getattribute__(expected, "__dict__")
        if type(actual_namespace) is not type(expected_namespace):
            return False
        if set(actual_namespace) != set(expected_namespace):
            return False
        for name, actual_value in actual_namespace.items():
            if name in source_method_names or type(actual_value) is not types.FunctionType:
                continue
            if not _source_dataclass_runtime_output_matches(
                actual_value,
                expected_namespace[name],
                actual_class=actual_class,
                expected_class=expected_class,
                depth=depth + 1,
                class_pairs=pairs,
                source_method_names=source_method_names,
                source_method_function_ids=source_method_function_ids,
            ):
                return False
        for name, actual_value in actual_namespace.items():
            expected_value = expected_namespace[name]
            if name == "__dataclass_fields__":
                if type(actual_value) is not dict or type(expected_value) is not dict:
                    return False
                if tuple(actual_value) != tuple(
                    expected_value
                ) or not _source_dataclass_fields_match(
                    tuple(actual_value.values()),
                    tuple(expected_value.values()),
                ):
                    return False
                continue
            if name == "__dataclass_params__":
                if type(actual_value) is not type(expected_value):
                    return False
                parameter_slots = getattr(type(actual_value), "__slots__", ())
                if type(parameter_slots) is str:
                    parameter_slots = (parameter_slots,)
                if type(parameter_slots) is not tuple or any(
                    type(parameter_name) is not str for parameter_name in parameter_slots
                ):
                    return False
                if any(
                    not _source_dataclass_values_equal(
                        getattr(actual_value, parameter_name, _SOURCE_DERIVATION_FAILED),
                        getattr(expected_value, parameter_name, _SOURCE_DERIVATION_FAILED),
                    )
                    for parameter_name in parameter_slots
                ):
                    return False
                continue
            if not _source_dataclass_runtime_output_matches(
                actual_value,
                expected_value,
                actual_class=actual_class,
                expected_class=expected_class,
                depth=depth + 1,
                class_pairs=pairs,
                source_method_names=source_method_names,
                source_method_function_ids=source_method_function_ids,
            ):
                return False
        return True
    if type(actual) in {str, int, bool, bytes, float, type(None)}:
        return _source_dataclass_values_equal(actual, expected)
    if type(actual) in {tuple, list}:
        return len(actual) == len(expected) and all(
            _source_dataclass_runtime_output_matches(
                left,
                right,
                actual_class=actual_class,
                expected_class=expected_class,
                depth=depth + 1,
                class_pairs=pairs,
                source_method_names=source_method_names,
                source_method_function_ids=source_method_function_ids,
            )
            for left, right in zip(actual, expected, strict=True)
        )
    if type(actual) is dict:
        return len(actual) == len(expected) and all(
            key in expected
            and _source_dataclass_runtime_output_matches(
                value,
                expected[key],
                actual_class=actual_class,
                expected_class=expected_class,
                depth=depth + 1,
                class_pairs=pairs,
                source_method_names=source_method_names,
                source_method_function_ids=source_method_function_ids,
            )
            for key, value in actual.items()
        )
    if type(actual) in {set, frozenset}:
        return _source_dataclass_values_equal(actual, expected)
    if type(actual) in {types.MemberDescriptorType, types.GetSetDescriptorType}:
        return actual.__name__ == expected.__name__ and _source_dataclass_runtime_output_matches(
            actual.__objclass__,
            expected.__objclass__,
            actual_class=actual_class,
            expected_class=expected_class,
            depth=depth + 1,
            class_pairs=pairs,
            source_method_names=source_method_names,
            source_method_function_ids=source_method_function_ids,
        )
    if type(actual) is property:
        if type(expected) is not property:
            return False
        actual_getter = getattr(actual, "fget", _SOURCE_DERIVATION_FAILED)
        expected_getter = getattr(expected, "fget", _SOURCE_DERIVATION_FAILED)
        actual_setter = getattr(actual, "fset", _SOURCE_DERIVATION_FAILED)
        expected_setter = getattr(expected, "fset", _SOURCE_DERIVATION_FAILED)
        actual_deleter = getattr(actual, "fdel", _SOURCE_DERIVATION_FAILED)
        expected_deleter = getattr(expected, "fdel", _SOURCE_DERIVATION_FAILED)
        if any(
            value is _SOURCE_DERIVATION_FAILED
            for value in (
                actual_getter,
                expected_getter,
                actual_setter,
                expected_setter,
                actual_deleter,
                expected_deleter,
            )
        ):
            return False
        if actual_setter is not None or actual_deleter is not None:
            return False
        return all(
            _source_dataclass_runtime_output_matches(
                actual_value,
                expected_value,
                actual_class=actual_class,
                expected_class=expected_class,
                depth=depth + 1,
                class_pairs=pairs,
                source_method_names=source_method_names,
                source_method_function_ids=source_method_function_ids,
            )
            for actual_value, expected_value in (
                (actual_getter, expected_getter),
                (actual_setter, expected_setter),
                (actual_deleter, expected_deleter),
                (getattr(actual, "__doc__", None), getattr(expected, "__doc__", None)),
                (
                    getattr(actual, "__isabstractmethod__", False),
                    getattr(expected, "__isabstractmethod__", False),
                ),
            )
        )
    if type(actual) is types.FunctionType:
        if id(actual) not in source_method_function_ids and _normalize_code_object(
            actual.__code__
        ) != _normalize_code_object(expected.__code__):
            return False
        if not _source_dataclass_function_globals_match(actual, expected):
            return False
        if any(
            getattr(actual, name, _SOURCE_DERIVATION_FAILED)
            != getattr(expected, name, _SOURCE_DERIVATION_FAILED)
            for name in ("__module__", "__name__", "__qualname__", "__doc__")
        ):
            return False
        for name in ("__defaults__", "__kwdefaults__", "__annotations__", "__type_params__"):
            actual_value = getattr(actual, name, _SOURCE_DERIVATION_FAILED)
            expected_value = getattr(expected, name, _SOURCE_DERIVATION_FAILED)
            if not _source_dataclass_runtime_output_matches(
                actual_value,
                expected_value,
                actual_class=actual_class,
                expected_class=expected_class,
                depth=depth + 1,
                class_pairs=pairs,
                source_method_names=source_method_names,
                source_method_function_ids=source_method_function_ids,
            ):
                return False
        actual_closure = actual.__closure__ or ()
        expected_closure = expected.__closure__ or ()
        if len(actual_closure) != len(expected_closure):
            return False
        actual_freevars = actual.__code__.co_freevars
        expected_freevars = expected.__code__.co_freevars
        if actual_freevars != expected_freevars:
            return False
        for freevar_name, actual_cell, expected_cell in zip(
            actual_freevars,
            actual_closure,
            expected_closure,
            strict=True,
        ):
            try:
                actual_value = actual_cell.cell_contents
            except ValueError:
                actual_value = _SOURCE_DERIVATION_FAILED
            try:
                expected_value = expected_cell.cell_contents
            except ValueError:
                expected_value = _SOURCE_DERIVATION_FAILED
            if freevar_name == "__class__":
                if expected_value is expected_class:
                    if actual_value is not actual_class:
                        return False
                elif pairs.get(id(expected_value), _SOURCE_DERIVATION_FAILED) is not actual_value:
                    return False
                continue
            if not _source_dataclass_runtime_output_matches(
                actual_value,
                expected_value,
                actual_class=actual_class,
                expected_class=expected_class,
                depth=depth + 1,
                class_pairs=pairs,
                source_method_names=source_method_names,
                source_method_function_ids=source_method_function_ids,
            ):
                return False
        return _source_dataclass_runtime_output_matches(
            actual.__dict__,
            expected.__dict__,
            actual_class=actual_class,
            expected_class=expected_class,
            depth=depth + 1,
            class_pairs=pairs,
            source_method_names=source_method_names,
            source_method_function_ids=source_method_function_ids,
        )
    return _source_dataclass_values_equal(actual, expected)


def _source_python_dataclass_binding_supported(
    repo_root: Path,
    module_name: str,
    export_name: str,
    relative: Path,
    tree: ast.Module,
    statement: ast.ClassDef,
) -> bool:
    """Admit a dataclass only when its complete safe source projection matches runtime output."""

    if statement.bases or statement.keywords or getattr(statement, "type_params", ()):
        return False
    resolved = _source_dataclass_transform_options(tree, statement)
    if resolved is None:
        return False
    decorator_name, options = resolved
    source_module = sys.modules.get(module_name)
    if type(source_module) is not types.ModuleType:
        return False
    source_path = (repo_root / relative).resolve()
    module_file = getattr(source_module, "__file__", None)
    module_spec = getattr(source_module, "__spec__", None)
    module_origin = getattr(module_spec, "origin", None)
    if not (
        type(module_file) is str
        and type(module_origin) is str
        and Path(module_file).resolve() == source_path
        and Path(module_origin).resolve() == source_path
    ):
        return False
    namespace = vars(source_module)
    if (
        namespace.get(decorator_name) is not _dataclasses.dataclass
        or _source_import_binding(
            decorator_name,
            tree=tree,
            module=source_module,
            module_name=module_name,
        )
        is not _dataclasses.dataclass
    ):
        return False
    try:
        _python_dataclass_transform_source_projection()
    except ConfidenceLedgerError:
        return False
    transformed = namespace.get(export_name)
    if type(transformed) is not type:
        return False
    transformed_namespace = type.__getattribute__(transformed, "__dict__")
    if not (
        type.__getattribute__(transformed, "__module__") == module_name
        and type.__getattribute__(transformed, "__qualname__") == export_name
        and _dataclasses.is_dataclass(transformed)
    ):
        return False
    if not _source_future_annotations_enabled(tree):
        return False
    declared: list[tuple[str, ast.expr]] = []
    source_methods: list[ast.FunctionDef | ast.AsyncFunctionDef] = []
    source_properties: set[str] = set()
    source_defaults: dict[str, object] = {}
    for index, member in enumerate(statement.body):
        if (
            index == 0
            and isinstance(member, ast.Expr)
            and isinstance(member.value, ast.Constant)
            and type(member.value.value) is str
        ):
            continue
        if (
            isinstance(member, ast.Expr)
            and isinstance(member.value, ast.Constant)
            and type(member.value.value) is str
        ):
            continue
        if isinstance(member, ast.AnnAssign):
            if not (
                isinstance(member.target, ast.Name)
                and member.simple == 1
                and member.target.id not in source_defaults
            ):
                return False
            declared.append((member.target.id, member.annotation))
            if member.value is not None:
                value = _source_dataclass_value(
                    member.value,
                    tree=tree,
                    module=source_module,
                    module_name=module_name,
                )
                if value is _SOURCE_DERIVATION_FAILED:
                    return False
                source_defaults[member.target.id] = value
            continue
        if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if member.name in {item.name for item in source_methods}:
                return False
            if member.decorator_list:
                if not (
                    len(member.decorator_list) == 1
                    and isinstance(member.decorator_list[0], ast.Name)
                    and member.decorator_list[0].id == "property"
                    and _source_import_binding(
                        "property",
                        tree=tree,
                        module=source_module,
                        module_name=module_name,
                    )
                    is property
                ):
                    return False
                source_properties.add(member.name)
            source_methods.append(member)
            continue
        return False
    field_names = tuple(name for name, _annotation in declared)
    annotations = transformed_namespace.get("__annotations__")
    if (
        not field_names
        or len(field_names) != len(set(field_names))
        or type(annotations) is not dict
        or tuple(annotations) != field_names
    ):
        return False
    for name, annotation_node in declared:
        annotation = annotations.get(name)
        if type(annotation) is not str or annotation != ast.unparse(annotation_node):
            return False
    try:
        actual_fields = _dataclasses.fields(transformed)
    except (TypeError, AttributeError):
        return False
    if tuple(field.name for field in actual_fields) != field_names:
        return False
    for field_value in actual_fields:
        if field_value.type != annotations.get(field_value.name):
            return False
        expected_default = source_defaults.get(field_value.name, _dataclasses.MISSING)
        if isinstance(expected_default, _dataclasses.Field):
            source_field = expected_default
            if (
                field_value.default is not source_field.default
                and not _source_dataclass_values_equal(field_value.default, source_field.default)
            ):
                return False
            if field_value.default_factory is not source_field.default_factory:
                return False
            for option in ("init", "repr", "compare", "hash", "kw_only"):
                expected_option = getattr(source_field, option)
                if option == "kw_only" and expected_option is _dataclasses.MISSING:
                    expected_option = options.get("kw_only", False)
                if getattr(field_value, option) != expected_option:
                    return False
            if not _source_dataclass_values_equal(
                dict(field_value.metadata),
                dict(source_field.metadata),
            ):
                return False
        elif not _source_dataclass_values_equal(field_value.default, expected_default):
            return False
    parameters = transformed_namespace.get("__dataclass_params__")
    if parameters is None:
        return False
    for option in ("init", "repr", "eq", "order", "unsafe_hash", "frozen"):
        if option in options and getattr(parameters, option, None) is not options[option]:
            return False
    if options.get("weakref_slot") is True:
        return False
    slots_enabled = options.get("slots", False)
    expected_slots = field_names if slots_enabled else transformed_namespace.get("__slots__")
    if slots_enabled:
        if (
            type(transformed_namespace.get("__slots__")) is not tuple
            or tuple(transformed_namespace["__slots__"]) != expected_slots
        ):
            return False
    elif "__slots__" in transformed_namespace:
        return False
    source_path = (repo_root / relative).resolve()
    analysis = _active_integrity_analysis()
    try:
        source_bytes = (
            analysis.source_bytes(source_path) if analysis is not None else source_path.read_bytes()
        )
        module_code = compile(
            source_bytes,
            str(source_path),
            "exec",
            dont_inherit=True,
            optimize=sys.flags.optimize,
        )
    except (OSError, SyntaxError, TypeError, ValueError):
        return False
    if not isinstance(module_code, types.CodeType):
        return False
    source_code_hashes = _loader_code_hashes_by_qualname(module_code)
    source_method_names: set[str] = set()
    source_method_function_ids: set[int] = set()
    for member in source_methods:
        source_method_names.add(member.name)
        actual_member = transformed_namespace.get(member.name)
        if member.name in source_properties:
            if (
                type(actual_member) is not property
                or actual_member.fset is not None
                or actual_member.fdel is not None
                or type(actual_member.fget) is not types.FunctionType
            ):
                return False
            actual_method = actual_member.fget
        else:
            if type(actual_member) is not types.FunctionType:
                return False
            actual_method = actual_member
        if not (
            actual_method.__globals__ is namespace
            and actual_method.__module__ == module_name
            and actual_method.__qualname__ == f"{export_name}.{member.name}"
            and Path(actual_method.__code__.co_filename).resolve() == source_path
            and _content_hash(_normalize_code_object(actual_method.__code__))
            in source_code_hashes.get(f"{export_name}.{member.name}", ())
            and not actual_method.__dict__
            and _source_function_defaults_match(actual_method, member)
            and _source_function_annotations_match(actual_method, member)
        ):
            return False
        source_method_function_ids.add(id(actual_method))
    try:
        replay_future_imports = [
            candidate
            for candidate in tree.body
            if isinstance(candidate, ast.ImportFrom) and candidate.module == "__future__"
        ]
        if not replay_future_imports:
            return False
        replay_module = ast.Module(
            body=[*replay_future_imports, statement],
            type_ignores=[],
        )
        replay_code = compile(
            replay_module,
            str(source_path),
            "exec",
            optimize=sys.flags.optimize,
        )
        if not isinstance(replay_code, types.CodeType):
            return False
        replay_namespace = dict(namespace)
        # Execute only the source-validated single stdlib dataclass statement above.
        exec(replay_code, replay_namespace)  # noqa: S102
        expected_class = replay_namespace.get(export_name)
        if type(expected_class) is not type:
            return False
        expected_namespace = type.__getattribute__(expected_class, "__dict__")
        expected_fields = tuple(_dataclasses.fields(expected_class))
        actual_field_tuple = tuple(actual_fields)
    except (AttributeError, NameError, RuntimeError, SyntaxError, TypeError, ValueError):
        return False
    if not _source_dataclass_fields_match(actual_field_tuple, expected_fields):
        return False
    if set(transformed_namespace) != set(expected_namespace):
        return False
    if tuple(expected_namespace.get("__annotations__", {})) != field_names:
        return False
    if tuple(expected_namespace.get("__dataclass_fields__", {})) != field_names:
        return False
    for output_name, expected_value in expected_namespace.items():
        actual_value = transformed_namespace[output_name]
        if output_name == "__dataclass_fields__":
            actual_field_map = actual_value
            expected_field_map = expected_value
            if type(actual_field_map) is not dict or type(expected_field_map) is not dict:
                return False
            if tuple(actual_field_map) != tuple(expected_field_map):
                return False
            if not _source_dataclass_fields_match(
                tuple(actual_field_map.values()),
                tuple(expected_field_map.values()),
            ):
                return False
            continue
        if output_name == "__dataclass_params__":
            if type(actual_value) is not type(expected_value):
                return False
            parameter_slots = getattr(type(actual_value), "__slots__", ())
            if type(parameter_slots) is str:
                parameter_slots = (parameter_slots,)
            if type(parameter_slots) is not tuple or any(
                type(name) is not str for name in parameter_slots
            ):
                return False
            for parameter_name in parameter_slots:
                actual_parameter = getattr(actual_value, parameter_name, _SOURCE_DERIVATION_FAILED)
                expected_parameter = getattr(
                    expected_value, parameter_name, _SOURCE_DERIVATION_FAILED
                )
                if (
                    actual_parameter is _SOURCE_DERIVATION_FAILED
                    or expected_parameter is _SOURCE_DERIVATION_FAILED
                    or not _source_dataclass_values_equal(actual_parameter, expected_parameter)
                ):
                    return False
            continue
        if not _source_dataclass_runtime_output_matches(
            actual_value,
            expected_value,
            actual_class=transformed,
            expected_class=expected_class,
            source_method_names=frozenset(source_method_names),
            source_method_function_ids=frozenset(source_method_function_ids),
        ):
            return False
    return True


def _source_module_direct_binding_route(
    repo_root: Path,
    module_name: str,
    export_name: str,
    *,
    directory_entries: dict[Path, frozenset[str]],
    source_index: _AuthorityImportClosureSourceIndex,
    visited: frozenset[tuple[str, str]],
) -> tuple[str, str, str | None] | None:
    """Resolve one statically supported package binding, without child fallback."""

    relative = _repository_module_source(
        repo_root,
        module_name,
        directory_entries=directory_entries,
    )
    if relative is None:
        return None
    try:
        analysis = _active_integrity_analysis()
        source_path = repo_root / relative
        source_bytes = (
            analysis.source_bytes(source_path) if analysis is not None else source_path.read_bytes()
        )
        tree = source_index.parse(source_bytes, filename=relative.as_posix())
    except (OSError, SyntaxError) as exc:
        raise ConfidenceLedgerError(
            "canonical_loaded_runtime_mismatch",
            relative.as_posix(),
        ) from exc
    sites = _module_scope_direct_binding_sites(tree, export_name)
    diagnostic_bindings = source_index.diagnostic_unqualified_direct_bindings
    if diagnostic_bindings is not None and (
        sites or export_name in _module_scope_definite_bindings(tree)
    ):
        # This names only the source namespace which may bind the requested
        # export. It does not identify the constructed object or qualify the
        # provider; those require separately admitted execution and bindings.
        diagnostic_bindings.add((module_name, export_name))
        return "symbol", module_name, export_name
    if not sites:
        if export_name in _module_scope_definite_bindings(tree):
            raise ConfidenceLedgerError(
                "canonical_loaded_runtime_mismatch",
                f"unsupported direct source binding: {module_name}.{export_name}",
            )
        return None
    if len(sites) != 1:
        raise ConfidenceLedgerError(
            "canonical_loaded_runtime_mismatch",
            f"rebound direct source export: {module_name}.{export_name}",
        )
    binding_kind, statement, alias = sites[0]
    if (
        binding_kind == "import_from"
        and isinstance(statement, ast.ImportFrom)
        and alias is not None
    ):
        package = module_name if relative.name == "__init__.py" else module_name.rpartition(".")[0]
        base = _resolve_import_from_base(statement, package)
        if (
            base is None
            or _repository_module_source(
                repo_root,
                base,
                directory_entries=directory_entries,
            )
            is None
        ):
            raise ConfidenceLedgerError(
                "canonical_loaded_runtime_mismatch",
                f"direct source provider is unavailable: {module_name}.{export_name}",
            )
        if base == module_name and alias.name == export_name:
            child_module = f"{module_name}.{export_name}"
            getter_sites = _module_scope_direct_binding_sites(tree, "__getattr__")
            import_position = (statement.lineno, statement.col_offset)
            getter_precedes_import = any(
                (
                    getattr(getter_statement, "lineno", -1),
                    getattr(getter_statement, "col_offset", -1),
                )
                < import_position
                for _kind, getter_statement, _getter_alias in getter_sites
            )
            if not getter_precedes_import:
                # A package self-import runs before any later __getattr__ binding. Python
                # can then load only the actual child module; a missing child fails before
                # the later map-backed hook exists and cannot be repaired by that hook.
                if (
                    _repository_module_source(
                        repo_root, child_module, directory_entries=directory_entries
                    )
                    is not None
                ):
                    return "module", child_module, None
                if getter_sites:
                    raise ConfidenceLedgerError(
                        "canonical_loaded_runtime_mismatch",
                        f"self-import precedes __getattr__ without child: "
                        f"{module_name}.{export_name}",
                    )
        target = _source_module_import_route(
            repo_root,
            base,
            alias.name,
            directory_entries=directory_entries,
            source_index=source_index,
            visited=visited,
            skip_direct_binding=(base == module_name and alias.name == export_name),
        )
        if target is None:
            raise ConfidenceLedgerError(
                "canonical_loaded_runtime_mismatch",
                f"direct source provider does not bind: {base}.{alias.name}",
            )
        if target[0] == "external":
            raise ConfidenceLedgerError(
                "canonical_loaded_runtime_mismatch",
                f"direct source provider is outside repository: {base}.{alias.name}",
            )
        return target
    if binding_kind == "import" and isinstance(statement, ast.Import) and alias is not None:
        target_module = alias.name if alias.asname is not None else alias.name.partition(".")[0]
        route_kind = (
            "module"
            if _repository_module_source(
                repo_root,
                target_module,
                directory_entries=directory_entries,
            )
            is not None
            else "external"
        )
        return route_kind, target_module, None
    if binding_kind == "local" and isinstance(
        statement,
        (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef),
    ):
        if statement.decorator_list and not (
            _read_api_surface_source_binding_supported(
                module_name,
                export_name,
                tree,
            )
            or (
                isinstance(statement, ast.ClassDef)
                and _source_python_dataclass_binding_supported(
                    repo_root,
                    module_name,
                    export_name,
                    relative,
                    tree,
                    statement,
                )
            )
        ):
            raise ConfidenceLedgerError(
                "canonical_loaded_runtime_mismatch",
                f"decorated direct source binding is unresolved: {module_name}.{export_name}",
            )
        return "symbol", module_name, export_name
    if binding_kind == "assignment" and isinstance(statement, (ast.Assign, ast.AnnAssign)):
        value = statement.value
        try:
            if value is None:
                raise ValueError("annotation-only binding")
            ast.literal_eval(value)
        except (ValueError, TypeError, SyntaxError, MemoryError) as exc:
            if _read_api_surface_source_binding_supported(
                module_name,
                export_name,
                tree,
            ):
                return "symbol", module_name, export_name
            raise ConfidenceLedgerError(
                "canonical_loaded_runtime_mismatch",
                f"side-effecting direct source assignment is unresolved: "
                f"{module_name}.{export_name}",
            ) from exc
        return "symbol", module_name, export_name
    raise ConfidenceLedgerError(
        "canonical_loaded_runtime_mismatch",
        f"unsupported direct source binding: {module_name}.{export_name}",
    )


def _source_module_direct_export_target(
    repo_root: Path,
    module_name: str,
    export_name: str,
    *,
    directory_entries: dict[Path, frozenset[str]],
    source_index: _AuthorityImportClosureSourceIndex,
) -> tuple[str, str] | None:
    """Return the source owner of one symbol-valued direct or lazy export."""

    route = _source_module_import_route(
        repo_root,
        module_name,
        export_name,
        directory_entries=directory_entries,
        source_index=source_index,
    )
    if route is None or route[0] != "symbol" or route[2] is None:
        return None
    return route[1], route[2]


def _repository_module_exports_symbol(
    repo_root: Path,
    module_name: str,
    symbol: str,
    *,
    directory_entries: dict[Path, frozenset[str]],
    source_index: _AuthorityImportClosureSourceIndex,
    visited: frozenset[tuple[str, str]] = frozenset(),
) -> bool:
    """Prove one facade target binds its requested name from repository source."""

    key = (module_name, symbol)
    if key in visited:
        return False
    relative = _repository_module_source(
        repo_root,
        module_name,
        directory_entries=directory_entries,
    )
    if relative is None:
        return False
    try:
        analysis = _active_integrity_analysis()
        source_path = repo_root / relative
        source_bytes = (
            analysis.source_bytes(source_path) if analysis is not None else source_path.read_bytes()
        )
        tree = source_index.parse(source_bytes, filename=relative.as_posix())
    except (OSError, SyntaxError):
        return False
    if symbol in _module_scope_definite_bindings(tree):
        return True
    # Imported map identity depends on the importing package as well as this file's
    # bytes. Recompute through the shared source-owner resolver instead of the
    # content-only literal-index cache, which cannot distinguish relative-map owners.
    provider_index = _source_module_provider_index(
        repo_root,
        module_name,
        tree,
        directory_entries=directory_entries,
        source_index=source_index,
    )
    if symbol in provider_index.invalid_exports or "*" in provider_index.invalid_exports:
        return False
    providers = provider_index.providers_by_export.get(symbol, frozenset())
    provider_symbols = provider_index.provider_symbols_by_export or {}
    target_symbols = provider_symbols.get(symbol, frozenset({symbol}))
    if len(providers) != 1 or len(target_symbols) != 1:
        return False
    provider = next(iter(providers))
    if provider.startswith("."):
        if Path(relative).name != "__init__.py":
            return False
        try:
            provider = importlib.util.resolve_name(provider, module_name)
        except (ImportError, TypeError, ValueError):
            return False
    return _repository_module_exports_symbol(
        repo_root,
        provider,
        next(iter(target_symbols)),
        directory_entries=directory_entries,
        source_index=source_index,
        visited=visited | {key},
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
        analysis = _active_integrity_analysis()
        tree = (
            analysis.source_tree(source_path)
            if analysis is not None
            else ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
        )
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


def _source_resolved_annotation_matches(
    actual: object,
    expected: _SourceResolvedAnnotation,
) -> bool:
    """Match only source-resolved class identities and their supported union forms."""

    members = expected.members
    if type(members) is not tuple or not members:
        return False
    if any(not isinstance(member, type) for member in members):
        return False
    if any(member is prior for index, member in enumerate(members) for prior in members[:index]):
        return False
    if len(members) == 1:
        return actual is members[0]

    try:
        origin = typing.get_origin(actual)
        actual_members = typing.get_args(actual)
    except (AttributeError, TypeError, ValueError):
        return False
    if type(actual_members) is not tuple or len(actual_members) != len(members):
        return False
    if origin is typing.Union:
        union_alias = typing.Union
        if type(actual) is not type(union_alias[int, str]):
            return False
    elif origin is types.UnionType:
        if type(actual) is not types.UnionType:
            return False
    else:
        return False

    if any(
        actual_member is prior
        for index, actual_member in enumerate(actual_members)
        for prior in actual_members[:index]
    ):
        return False
    return all(
        any(actual_member is member for actual_member in actual_members) for member in members
    )


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
    if type(expected) is _SourceResolvedAnnotation:
        return _source_resolved_annotation_matches(actual, expected)
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
        analysis = _active_integrity_analysis()
        tree = (
            analysis.source_tree(source_path)
            if analysis is not None
            else ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
        )
    except (OSError, SyntaxError, UnicodeError, ConfidenceLedgerError):
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


def _loaded_code_manifest_body(
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
        origin = getattr(spec, "origin", None)
        module_file = getattr(module, "__file__", None)
        source_path = (repo_root / relative_path).resolve()
        if (
            not isinstance(loader, SourceFileLoader)
            or not isinstance(origin, str)
            or not isinstance(module_file, str)
        ):
            raise ConfidenceLedgerError(
                "canonical_loaded_runtime_mismatch",
                f"loaded repository module has no source provenance: {module_name}",
            )
        try:
            origin_path = Path(origin).resolve()
            file_path = Path(module_file).resolve()
            source_path.relative_to(repo_root.resolve())
        except (OSError, TypeError, ValueError) as exc:
            raise ConfidenceLedgerError(
                "canonical_loaded_runtime_mismatch",
                f"loaded repository module provenance invalid: {module_name}",
            ) from exc
        if origin_path != source_path or file_path != source_path:
            raise ConfidenceLedgerError(
                "canonical_loaded_runtime_mismatch",
                f"loaded repository module provenance invalid: {module_name}",
            )
        analysis = _active_integrity_analysis()
        if analysis is None:
            raise ConfidenceLedgerError("canonical_loaded_runtime_mismatch")
        source_bytes = analysis.source_bytes(source_path)
        try:
            code = compile(
                source_bytes,
                str(source_path),
                "exec",
                dont_inherit=True,
                optimize=sys.flags.optimize,
            )
        except (OverflowError, SyntaxError, TypeError, ValueError) as exc:
            raise ConfidenceLedgerError(
                "canonical_loaded_runtime_mismatch",
                f"loaded repository source cannot be compiled: {module_name}",
            ) from exc
        if not isinstance(code, types.CodeType):
            raise ConfidenceLedgerError(
                "canonical_loaded_runtime_mismatch",
                f"loaded repository source cannot be compiled: {module_name}",
            )
        live_defined_code = _live_defined_code_manifest(
            module,
            module_name,
            source_path=source_path,
        )
        source_code_hashes = _loader_code_hashes_by_qualname(code)
        live_loader_bindings: dict[str, object] = {}
        module_consistent = True
        for label, live_code in live_defined_code.items():
            code_qualname = str(live_code["code_qualname"])
            live_hash = str(live_code["normalized_code_hash"])
            defined_locally = bool(live_code["defined_locally"])
            source_hashes = source_code_hashes.get(code_qualname, ()) if defined_locally else ()
            matches_loader = (
                live_hash in source_hashes and bool(live_code["globals_match_module"])
                if defined_locally
                else None
            )
            if defined_locally:
                module_consistent = module_consistent and bool(matches_loader)
            live_loader_bindings[label] = {
                **live_code,
                "loader_normalized_code_hashes": list(source_hashes),
                "matches_loader": matches_loader,
            }
        loader_owned_slots: dict[str, object] = {}
        for slot in _loader_owned_callable_slots(source_path):
            expected_hashes = source_code_hashes.get(slot.qualname, ())
            row, matches_slot = _loader_owned_slot_binding(
                module,
                module_name,
                source_path,
                slot,
                expected_hashes,
                source_code_hashes,
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
        manifest[module_name] = {
            "relative_path": relative_path,
            "source_hash": _bytes_hash(source_bytes),
            "loader_module_code_hash": _content_hash(_normalize_code_object(code)),
            "live_defined_code": live_loader_bindings,
            "loader_owned_callable_slots": loader_owned_slots,
            "live_loader_consistent": module_consistent,
        }
    return _canonical_json(manifest), all_consistent


def _loaded_code_manifest(
    repo_root: Path,
    closure: tuple[tuple[str, str], ...],
) -> tuple[str, bool]:
    """Capture loaded code with fresh inputs and pass-local source derivations."""
    analysis = _active_integrity_analysis()
    owns_analysis = analysis is None
    token = None
    if analysis is None:
        analysis = _IntegrityAnalysisContext()
        token = _ACTIVE_INTEGRITY_ANALYSIS.set(analysis)
    try:
        result = _loaded_code_manifest_body(repo_root, closure)
        if owns_analysis:
            analysis.assert_sources_unchanged()
        return result
    finally:
        if token is not None:
            _ACTIVE_INTEGRITY_ANALYSIS.reset(token)


def _execution_loaded_slot_bindings(
    root: Path,
    paths: Mapping[str, str],
    executed_code: tuple[tuple[str, types.CodeType], ...],
    *,
    receiver_classes: tuple[type, ...] = (),
) -> dict[str, object]:
    """Reconcile the live SOURCE slots which own actually consumed code.

    The original C95 full-module authority census remains unchanged. This
    separate observation has a different denominator: real producer frames and
    its exact entry callables. A nested function/comprehension is owned by the
    nearest source-declared callable, rather than a caller-written helper list.
    Unexecuted N4/N9/LLM alternatives receive a source-byte binding only.
    """
    modules: dict[str, set[str]] = {}
    for module, code in executed_code:
        if module in paths:
            modules.setdefault(module, set()).add(code.co_qualname)
    class_paths: dict[str, set[tuple[str, ...]]] = {}
    for cls in receiver_classes:
        module_name = cls.__module__
        module = sys.modules.get(module_name)
        parts = tuple(cls.__qualname__.split("."))
        owner: object = module
        for part in parts:
            owner = vars(owner).get(part) if hasattr(owner, "__dict__") else None
        if module_name not in paths or owner is not cls or type(cls) is not type:
            raise ConfidenceLedgerError("n5_receiver_construction_not_established")
        class_paths.setdefault(module_name, set()).add(parts)
        modules.setdefault(module_name, set())
    result: dict[str, object] = {}
    for module_name, qualnames in sorted(modules.items()):
        relative = paths[module_name]
        source_path = (root / relative).resolve(strict=True)
        module = sys.modules.get(module_name)
        spec = getattr(module, "__spec__", None)
        if (
            module is None
            or not isinstance(getattr(spec, "loader", None), SourceFileLoader)
            or Path(str(getattr(spec, "origin", ""))).resolve() != source_path
            or Path(str(getattr(module, "__file__", ""))).resolve() != source_path
        ):
            raise ConfidenceLedgerError("n5_executed_code_origin_mismatch")
        source = source_path.read_bytes()
        compiled = compile(
            source, str(source_path), "exec", dont_inherit=True, optimize=sys.flags.optimize
        )
        hashes = _loader_code_hashes_by_qualname(compiled)
        declarations = _loader_owned_callable_slots(source_path)
        selected: dict[str, _LoaderOwnedCallableSlot] = {}
        for qualname in qualnames:
            matches = tuple(
                slot
                for slot in declarations
                if qualname == slot.qualname or qualname.startswith(slot.qualname + ".<locals>.")
            )
            if not matches:
                if qualname == "<module>":
                    # Import/module execution has no callable owner slot. Its
                    # complete code is reconciled below against compiled source.
                    continue
                raise ConfidenceLedgerError("n5_executed_owner_slot_not_established")
            slot = max(matches, key=lambda item: len(item.qualname))
            selected[slot.qualname] = slot
        for owner_path in class_paths.get(module_name, ()):
            class_slots = tuple(
                slot for slot in declarations if slot.owner_path[: len(owner_path)] == owner_path
            )
            if not class_slots or not any(slot.binding_name == "__init__" for slot in class_slots):
                raise ConfidenceLedgerError("n5_receiver_construction_not_established")
            selected.update((slot.qualname, slot) for slot in class_slots)
            prefix = ".".join(owner_path)
            actual: set[str] = set()

            def collect_labels(cls: type, label: str, labels: set[str], owner_module: str) -> None:
                for name, raw in vars(cls).items():
                    member = label + "." + name
                    if isinstance(raw, (types.FunctionType, classmethod, staticmethod)):
                        labels.add(member)
                    elif isinstance(raw, property):
                        labels.update(
                            member + "." + role
                            for role in ("fget", "fset", "fdel")
                            if getattr(raw, role) is not None
                        )
                    elif isinstance(raw, type) and raw.__module__ == owner_module:
                        collect_labels(raw, member, labels, owner_module)

            cls = _loader_owned_slot_owner(module, module_name, owner_path)
            if not isinstance(cls, type):
                raise ConfidenceLedgerError("n5_receiver_construction_not_established")
            collect_labels(cls, prefix, actual, module_name)
            expected = {
                slot.qualname + "." + role if slot.descriptor_kind == "property" else slot.qualname
                for slot in class_slots
                for role in (
                    slot.property_accessors if slot.descriptor_kind == "property" else ("function",)
                )
            }
            if actual != expected:
                raise ConfidenceLedgerError("n5_receiver_construction_not_established")
        # Constructors execute module-global/import lookup edges before the
        # numerical observer exists. Reuse the source import relation on every
        # direct imported dependency read by those actual constructor code
        # objects, not a hand-written name/alias list.
        tree = ast.parse(source, filename=str(source_path))
        imported_names = _source_imported_names(tree)
        constructor_imports: dict[str, tuple[str, ...]] = {}
        for owner_path in class_paths.get(module_name, ()):
            cls = _loader_owned_slot_owner(module, module_name, owner_path)
            raw = vars(cls).get("__init__") if isinstance(cls, type) else None
            if not isinstance(raw, types.FunctionType):
                raise ConfidenceLedgerError("n5_receiver_construction_not_established")
            consumed = set()
            for instruction in dis.get_instructions(raw.__code__):
                if instruction.opname not in {"LOAD_GLOBAL", "LOAD_NAME"}:
                    continue
                name = str(instruction.argval)
                if name in imported_names:
                    if (
                        _source_import_binding(
                            name, tree=tree, module=module, module_name=module_name
                        )
                        is _SOURCE_DERIVATION_FAILED
                    ):
                        raise ConfidenceLedgerError("n5_receiver_construction_not_established")
                    consumed.add(name)
            constructor_imports[".".join(owner_path)] = tuple(sorted(consumed))
        rows: dict[str, dict[str, object]] = {}
        for qualname, slot in sorted(selected.items()):
            row, matches = _loader_owned_slot_binding(
                module, module_name, source_path, slot, hashes.get(qualname, ()), hashes
            )
            if not matches:
                receiver_owned = any(
                    slot.owner_path[: len(path)] == path
                    for path in class_paths.get(module_name, ())
                )
                raise ConfidenceLedgerError(
                    "n5_receiver_construction_not_established"
                    if receiver_owned
                    else "n5_consumed_loaded_binding_mismatch"
                )
            rows[qualname] = {"slot": row}
        # Validate loader slots before normalizing arbitrary current closures.
        # A noncanonical constructor's environment is not traversed first.
        live = _live_defined_code_manifest(
            module,
            module_name,
            source_path=source_path,
            selected_qualnames=frozenset(selected),
        )
        for qualname in sorted(selected):
            # Existing C95 rows include code/wrapper/descriptor provenance;
            # this adds defaults/kwdefaults/closure from its existing generic
            # function-binding owner. Same code with changed defaults differs.
            actual_bindings = {
                label: binding
                for label, binding in live.items()
                if label == qualname or label.startswith(qualname + ".")
            }
            if not actual_bindings:
                raise ConfidenceLedgerError("n5_consumed_loaded_binding_missing")
            rows[qualname]["live_bindings"] = actual_bindings
        result[module_name] = {
            "relative_path": relative,
            "consumed_slots": rows,
            "constructor_import_lookup_relations": constructor_imports,
        }
    return result


def capture_execution_source_bindings(
    entry_modules: tuple[str, ...],
    executed_code: tuple[tuple[str, types.CodeType], ...],
    *,
    bound_entry_code: tuple[tuple[str, types.CodeType], ...] = (),
    receiver_classes: tuple[type, ...] = (),
) -> dict[str, object]:
    """Reconcile the complete source closure and actual consumed live slots.

    Actual producer frames/entry objects determine the loaded-binding set. The
    static closure still binds every alternative's source bytes, but an
    unrelated loaded function is not asserted to have supplied this N5 result.
    The original C95 full-module admission policy is not changed by this seam.
    """
    root = _loaded_policy_engine_root()
    closure = _resolve_authority_import_closure(root, entry_modules)
    source_rows = tuple(
        (module, relative, _bytes_hash((root / relative).read_bytes()))
        for module, relative in closure
    )
    paths = dict(closure)
    loaded_bindings = _execution_loaded_slot_bindings(
        root, paths, executed_code + bound_entry_code, receiver_classes=receiver_classes
    )
    executed_rows: list[tuple[str, str, str]] = []
    bound_rows: list[tuple[str, str, str]] = []
    for index, (module, code) in enumerate(executed_code + bound_entry_code):
        relative = paths.get(module)
        loaded_module = sys.modules.get(module)
        spec = getattr(loaded_module, "__spec__", None)
        loader = getattr(spec, "loader", None)
        origin = getattr(spec, "origin", None)
        if relative is not None:
            source_path = (root / relative).resolve()
            source = source_path.read_bytes()
            if Path(code.co_filename).resolve() != source_path:
                raise ConfidenceLedgerError("n5_executed_code_origin_mismatch")
            compiled = compile(
                source, str(source_path), "exec", dont_inherit=True, optimize=sys.flags.optimize
            )
        elif isinstance(loader, SourceFileLoader) and isinstance(origin, str):
            source_path = Path(origin).resolve(strict=True)
            if (
                loaded_module is None
                or Path(str(getattr(loaded_module, "__file__", ""))).resolve() != source_path
                or Path(code.co_filename).resolve() != source_path
            ):
                raise ConfidenceLedgerError("n5_executed_dependency_origin_mismatch")
            source = source_path.read_bytes()
            compiled = compile(
                source, str(source_path), "exec", dont_inherit=True, optimize=sys.flags.optimize
            )
        elif origin == "frozen" and hasattr(loader, "get_code"):
            compiled = loader.get_code(module)
            if not isinstance(compiled, types.CodeType):
                raise ConfidenceLedgerError("n5_executed_frozen_dependency_unverified")
        else:
            raise ConfidenceLedgerError("n5_executed_dependency_source_not_established")
        expected = _loader_code_hashes_by_qualname(compiled).get(code.co_qualname, ())
        digest = _content_hash(_normalize_code_object(code))
        if digest not in expected:
            raise ConfidenceLedgerError("n5_executed_code_source_mismatch")
        row = (module, code.co_qualname, digest)
        (executed_rows if index < len(executed_code) else bound_rows).append(row)
    return {
        "source_closure_hash": _content_hash(source_rows),
        "source_module_count": len(source_rows),
        "loaded_binding_hash": _content_hash(loaded_bindings),
        "loaded_module_count": len(loaded_bindings),
        "executed_code": tuple(sorted(set(executed_rows))),
        "bound_entry_code": tuple(sorted(set(bound_rows))),
    }


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
    selected_qualnames: frozenset[str] | None = None,
) -> dict[str, dict[str, object]]:
    """Capture all authority bindings, or exactly an execution's selected slots.

    None preserves the original C95 full-census contract. The execution-only
    selection is applied before normalization, so unconsumed code/defaults do
    not enter that separate observation's deciding denominator.
    """

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
        if selected_qualnames is None
        or any(
            label == qualname or label.startswith(qualname + ".") for qualname in selected_qualnames
        )
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


def _normalize_code_object(
    code: types.CodeType,
    *,
    code_cache: _CodeNormalizationCache | None = None,
) -> dict[str, object]:
    """Normalize executable code while excluding machine-local filenames."""
    analysis = _active_integrity_analysis()
    active_cache = (
        code_cache
        if code_cache is not None
        else (analysis.code_cache if analysis is not None else None)
    )
    if active_cache is not None:
        cached = active_cache.get(code)
        if cached is not None:
            return cached
    normalized = {
        "argcount": code.co_argcount,
        "posonlyargcount": code.co_posonlyargcount,
        "kwonlyargcount": code.co_kwonlyargcount,
        "nlocals": code.co_nlocals,
        "stacksize": code.co_stacksize,
        "flags": code.co_flags,
        "code_hash": _bytes_hash(code.co_code),
        "consts": [
            _normalize_code_constant(value, code_cache=active_cache) for value in code.co_consts
        ],
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
    if active_cache is not None:
        active_cache.put(code, normalized)
    return normalized


def _normalize_code_constant(
    value: object,
    *,
    code_cache: _CodeNormalizationCache | None = None,
) -> object:
    """Return a canonical representation of a code-object constant."""

    if isinstance(value, types.CodeType):
        return {"code": _normalize_code_object(value, code_cache=code_cache)}
    if isinstance(value, bytes):
        return {"bytes_hash": _bytes_hash(value)}
    if isinstance(value, tuple):
        return {"tuple": [_normalize_code_constant(item, code_cache=code_cache) for item in value]}
    if isinstance(value, slice):
        return {
            "slice": [
                _normalize_code_constant(value.start, code_cache=code_cache),
                _normalize_code_constant(value.stop, code_cache=code_cache),
                _normalize_code_constant(value.step, code_cache=code_cache),
            ]
        }
    if isinstance(value, frozenset):
        items = [_normalize_code_constant(item, code_cache=code_cache) for item in value]
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
    analysis = _IntegrityAnalysisContext()
    analysis_token = _ACTIVE_INTEGRITY_ANALYSIS.set(analysis)
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
        source_bytes = source_path.read_bytes()
        analysis.remember_source(source_path, source_bytes)
        source_hash = _bytes_hash(source_bytes)
        source_contract_projection = _source_ledger_contract_projection(source_bytes)
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
        if source_contract_projection != contract_projection:
            raise ValueError("runtime ledger contract differs from its source declaration")
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
            observed_binding_references: list[_FacadeRuntimeBindingReference] = []
            facade_projection, supplemental_closure = _source_facade_runtime_projection(
                _IMPORT_TIME_OWNER_ROOT,
                _derived_authority_import_closure(_IMPORT_TIME_OWNER_ROOT),
                runtime_binding_references=observed_binding_references,
            )
            if not _runtime_binding_references_match(
                observed_binding_references,
                _IMPORT_TIME_FACADE_RUNTIME_BINDING_REFERENCES,
            ):
                raise ValueError("selected facade/importer binding differs from import snapshot")
            runtime_closure = _combined_runtime_code_closure(
                _IMPORT_TIME_AUTHORITY_IMPORT_CLOSURE,
                supplemental_closure,
            )
            if (
                facade_projection != _IMPORT_TIME_FACADE_RUNTIME_PROJECTION
                or runtime_closure != _IMPORT_TIME_RUNTIME_CODE_CLOSURE
            ):
                raise ValueError("loaded facade map differs from its import-time source")
            loaded_code_manifest, loaded_code_consistent = loaded_code_manifest_fn(
                _IMPORT_TIME_OWNER_ROOT,
                runtime_closure,
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
        analysis.assert_sources_unchanged()
    except (OSError, TypeError, ValueError, AttributeError, SyntaxError) as exc:
        if isinstance(exc, ConfidenceLedgerError):
            raise
        raise ConfidenceLedgerError("canonical_loaded_runtime_mismatch", str(exc)) from exc
    finally:
        _ACTIVE_INTEGRITY_ANALYSIS.reset(analysis_token)


_IMPORT_TIME_DEPLOYMENT_IDENTITY_REASON = "canonical_loaded_runtime_mismatch"
_IMPORT_TIME_DEPLOYMENT_IDENTITY_FAILURE: tuple[str, str] | None = None
_IMPORT_TIME_AUTHORITY_IMPORT_CLOSURE: tuple[tuple[str, str], ...] = ()
_IMPORT_TIME_DEPLOYMENT_BASELINE: str | None = None
_IMPORT_TIME_DEPLOYMENT_QUICK_FENCE: _DeploymentQuickFence = ()
_IMPORT_TIME_FACADE_RUNTIME_PROJECTION = ""
_IMPORT_TIME_FACADE_RUNTIME_BINDING_REFERENCES: tuple[_FacadeRuntimeBindingReference, ...] = ()
_IMPORT_TIME_FACADE_SUPPLEMENTAL_CLOSURE: tuple[tuple[str, str], ...] = ()
_IMPORT_TIME_RUNTIME_CODE_CLOSURE: tuple[tuple[str, str], ...] = ()
_IMPORT_TIME_LOADED_CODE_MANIFEST = ""
_IMPORT_TIME_LOADED_CODE_CONSISTENT = False
_IMPORT_TIME_OWNER_ROOT = _loaded_policy_engine_root()


def _early_host_capture_is_collecting() -> bool:
    """Defer self-capture while a live early host is still collecting imports.

    This is only a reason to wait; these process-local slots do not appoint a
    profile or authorize a later capture on their own.
    """

    session = _passive_capture_lookup(sys.__dict__, "_polisyos_loaded_host_v1")
    capture = _passive_capture_lookup(sys.__dict__, "_polisyos_loaded_execution_owner_v1")
    if type(session) is not dict or capture is _NO_EXECUTION_BINDING:
        return False
    phase = _passive_capture_lookup(session, "phase")
    return bool(
        type(phase) is str
        and phase == "collecting"
        and _passive_capture_lookup(session, "capture") is capture
    )


_IMPORT_TIME_HOST_CAPTURE_DEFERRED = _early_host_capture_is_collecting()
if _IMPORT_TIME_HOST_CAPTURE_DEFERRED:
    # The owner cannot observe its final module while its initializer runs.
    # Keep authority unavailable until the early host's post-import handoff.
    pass
elif (
    (_IMPORT_TIME_OWNER_ROOT / "pyproject.toml").is_file()
    and (_IMPORT_TIME_OWNER_ROOT / "uv.lock").is_file()
    and (_IMPORT_TIME_OWNER_ROOT / "src" / "polisyos").is_dir()
):
    try:
        authority_import_closure = _resolve_authority_import_closure(
            _IMPORT_TIME_OWNER_ROOT,
            __name__,
        )
        deployment_baseline, deployment_quick_fence = _stable_deployment_snapshot(
            _IMPORT_TIME_OWNER_ROOT
        )
        _import_authority_closure_modules(authority_import_closure)
        facade_runtime_binding_references: list[_FacadeRuntimeBindingReference] = []
        facade_runtime_projection, facade_supplemental_closure = _source_facade_runtime_projection(
            _IMPORT_TIME_OWNER_ROOT,
            authority_import_closure,
            runtime_binding_references=facade_runtime_binding_references,
        )
        runtime_code_closure = _combined_runtime_code_closure(
            authority_import_closure,
            facade_supplemental_closure,
        )
        loaded_code_manifest, loaded_code_consistent = _loaded_code_manifest(
            _IMPORT_TIME_OWNER_ROOT,
            runtime_code_closure,
        )
        if not loaded_code_consistent:
            raise ConfidenceLedgerError(
                "canonical_loaded_runtime_mismatch",
                "loaded authority code does not match its import-time source",
            )
        if _deployment_quick_fence(_IMPORT_TIME_OWNER_ROOT) != deployment_quick_fence:
            raise ConfidenceLedgerError("canonical_loaded_runtime_mismatch")
    except ConfidenceLedgerError as exc:
        # A failed first capture is terminal for this process. Preserve its typed
        # cause for diagnostics, and leave every authority-bearing snapshot field
        # in the same unavailable state; later source changes cannot upgrade it.
        _IMPORT_TIME_DEPLOYMENT_IDENTITY_FAILURE = (exc.code, exc.detail)
    else:
        _IMPORT_TIME_AUTHORITY_IMPORT_CLOSURE = authority_import_closure
        _IMPORT_TIME_DEPLOYMENT_BASELINE = deployment_baseline
        _IMPORT_TIME_DEPLOYMENT_QUICK_FENCE = deployment_quick_fence
        _IMPORT_TIME_FACADE_RUNTIME_PROJECTION = facade_runtime_projection
        _IMPORT_TIME_FACADE_RUNTIME_BINDING_REFERENCES = tuple(
            sorted(
                facade_runtime_binding_references,
                key=lambda item: (item[0], item[1], item[7], item[8], item[10], item[11]),
            )
        )
        _IMPORT_TIME_FACADE_SUPPLEMENTAL_CLOSURE = facade_supplemental_closure
        _IMPORT_TIME_RUNTIME_CODE_CLOSURE = runtime_code_closure
        _IMPORT_TIME_LOADED_CODE_MANIFEST = loaded_code_manifest
        # Publish this admission predicate last so reentrant imports cannot see a
        # partially captured snapshot as established.
        _IMPORT_TIME_LOADED_CODE_CONSISTENT = loaded_code_consistent
else:
    # An installed package lacks the source checkout's canonical lock/build
    # inputs until the confidence-ledger build issuer is appointed and wired.
    # Do not synthesize currentness; history-only callers may still use the
    # dedicated replay path when their import graph permits it.
    _IMPORT_TIME_DEPLOYMENT_IDENTITY_REASON = "packaged_deployment_identity_issuer_unavailable"
