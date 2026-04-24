"""Cross-backend numerical equivalence certificate contracts."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from polisyos.core.observability.determinism import (
    DeterminismTier,
    parse_determinism_tier,
)
from polisyos.foundry.methods.base import ComputeBackend

EQUIVALENCE_COMPARATOR_VERSION = "polisyos.xbeq/0.1.0"
EQUIVALENCE_CERTIFICATE_SCHEMA = "polisyos.foundry.cross_backend_equivalence_certificate"
EQUIVALENCE_CERTIFICATE_SCHEMA_VERSION = "0.1.0"
EQUIVALENCE_CERTIFICATE_KIND = "foundry.cross_backend_equivalence_certificate"


class ComparatorKind(str, Enum):
    """Numeric/structural comparator used for one canonicalized field."""

    EXACT = "exact"
    ABS_REL = "abs_rel"
    ULP = "ulp"
    NORM = "norm"
    DISTRIBUTIONAL = "distributional"


class FieldRequirement(str, Enum):
    """How strongly one field influences the aggregate certificate verdict."""

    REQUIRED = "required"
    ADVISORY = "advisory"
    DIAGNOSTIC_ONLY = "diagnostic_only"

    @property
    def affects_verdict(self) -> bool:
        return self is FieldRequirement.REQUIRED


class EquivalenceVerdict(str, Enum):
    """Aggregate result of applying one equivalence certificate."""

    PASS_STRICT = "pass_strict"
    PASS_RELAXED = "pass_relaxed"
    FAIL = "fail"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class EquivalenceRuntimeEnvelope:
    """Pinned runtime posture that a certificate is allowed to cover."""

    source_backend: ComputeBackend
    target_backend: ComputeBackend
    source_runtime_fingerprint: str | None = None
    target_runtime_fingerprint: str | None = None
    source_execution_device: str | None = None
    target_execution_device: str | None = None
    source_determinism_tier: DeterminismTier | None = None
    target_determinism_tier: DeterminismTier | None = None
    source_library_versions: Mapping[str, str] = field(default_factory=dict)
    target_library_versions: Mapping[str, str] = field(default_factory=dict)
    source_route_key: Mapping[str, Any] = field(default_factory=dict)
    target_route_key: Mapping[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "source_backend": self.source_backend.value,
            "target_backend": self.target_backend.value,
            "source_runtime_fingerprint": self.source_runtime_fingerprint,
            "target_runtime_fingerprint": self.target_runtime_fingerprint,
            "source_execution_device": self.source_execution_device,
            "target_execution_device": self.target_execution_device,
            "source_determinism_tier": (
                None if self.source_determinism_tier is None else self.source_determinism_tier.value
            ),
            "target_determinism_tier": (
                None if self.target_determinism_tier is None else self.target_determinism_tier.value
            ),
            "source_library_versions": dict(self.source_library_versions),
            "target_library_versions": dict(self.target_library_versions),
            "source_route_key": dict(self.source_route_key),
            "target_route_key": dict(self.target_route_key),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> EquivalenceRuntimeEnvelope:
        return cls(
            source_backend=ComputeBackend(str(data["source_backend"])),
            target_backend=ComputeBackend(str(data["target_backend"])),
            source_runtime_fingerprint=_optional_string(data.get("source_runtime_fingerprint")),
            target_runtime_fingerprint=_optional_string(data.get("target_runtime_fingerprint")),
            source_execution_device=_optional_string(data.get("source_execution_device")),
            target_execution_device=_optional_string(data.get("target_execution_device")),
            source_determinism_tier=parse_determinism_tier(
                _optional_string(data.get("source_determinism_tier"))
            ),
            target_determinism_tier=parse_determinism_tier(
                _optional_string(data.get("target_determinism_tier"))
            ),
            source_library_versions=_coerce_string_mapping(data.get("source_library_versions")),
            target_library_versions=_coerce_string_mapping(data.get("target_library_versions")),
            source_route_key=_coerce_mapping(data.get("source_route_key")),
            target_route_key=_coerce_mapping(data.get("target_route_key")),
        )


@dataclass(frozen=True, slots=True)
class FieldToleranceSpec:
    """Per-field equivalence tolerance budget."""

    path: str
    comparator: ComparatorKind
    requirement: FieldRequirement = FieldRequirement.REQUIRED
    strict_atol: float = 0.0
    strict_rtol: float = 0.0
    relaxed_atol: float | None = None
    relaxed_rtol: float | None = None
    scale_floor: float = 0.0
    equal_nan: bool = False
    ulp_tol: int | None = None
    relaxed_ulp_tol: int | None = None
    norm_order: str | float | None = None
    strict_norm_tol: float | None = None
    relaxed_norm_tol: float | None = None
    distribution_metric: str | None = None
    strict_distribution_tol: float | None = None
    relaxed_distribution_tol: float | None = None
    confidence: float | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.path:
            raise ValueError("FieldToleranceSpec.path must be non-empty")
        if self.strict_atol < 0 or self.strict_rtol < 0:
            raise ValueError("strict tolerances must be non-negative")
        if self.scale_floor < 0:
            raise ValueError("scale_floor must be non-negative")
        if self.relaxed_atol is not None and self.relaxed_atol < 0:
            raise ValueError("relaxed_atol must be non-negative")
        if self.relaxed_rtol is not None and self.relaxed_rtol < 0:
            raise ValueError("relaxed_rtol must be non-negative")
        if self.ulp_tol is not None and self.ulp_tol < 0:
            raise ValueError("ulp_tol must be non-negative")
        if self.relaxed_ulp_tol is not None and self.relaxed_ulp_tol < 0:
            raise ValueError("relaxed_ulp_tol must be non-negative")
        if self.strict_norm_tol is not None and self.strict_norm_tol < 0:
            raise ValueError("strict_norm_tol must be non-negative")
        if self.relaxed_norm_tol is not None and self.relaxed_norm_tol < 0:
            raise ValueError("relaxed_norm_tol must be non-negative")
        if self.strict_distribution_tol is not None and self.strict_distribution_tol < 0:
            raise ValueError("strict_distribution_tol must be non-negative")
        if self.relaxed_distribution_tol is not None and self.relaxed_distribution_tol < 0:
            raise ValueError("relaxed_distribution_tol must be non-negative")
        if self.confidence is not None and not (0.0 < self.confidence <= 1.0):
            raise ValueError("confidence must be in (0, 1]")
        object.__setattr__(
            self,
            "relaxed_atol",
            self.strict_atol if self.relaxed_atol is None else self.relaxed_atol,
        )
        object.__setattr__(
            self,
            "relaxed_rtol",
            self.strict_rtol if self.relaxed_rtol is None else self.relaxed_rtol,
        )
        object.__setattr__(
            self,
            "relaxed_ulp_tol",
            self.ulp_tol if self.relaxed_ulp_tol is None else self.relaxed_ulp_tol,
        )
        object.__setattr__(
            self,
            "relaxed_norm_tol",
            (self.strict_norm_tol if self.relaxed_norm_tol is None else self.relaxed_norm_tol),
        )
        object.__setattr__(
            self,
            "relaxed_distribution_tol",
            (
                self.strict_distribution_tol
                if self.relaxed_distribution_tol is None
                else self.relaxed_distribution_tol
            ),
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "comparator": self.comparator.value,
            "requirement": self.requirement.value,
            "strict_atol": self.strict_atol,
            "strict_rtol": self.strict_rtol,
            "relaxed_atol": self.relaxed_atol,
            "relaxed_rtol": self.relaxed_rtol,
            "scale_floor": self.scale_floor,
            "equal_nan": self.equal_nan,
            "ulp_tol": self.ulp_tol,
            "relaxed_ulp_tol": self.relaxed_ulp_tol,
            "norm_order": self.norm_order,
            "strict_norm_tol": self.strict_norm_tol,
            "relaxed_norm_tol": self.relaxed_norm_tol,
            "distribution_metric": self.distribution_metric,
            "strict_distribution_tol": self.strict_distribution_tol,
            "relaxed_distribution_tol": self.relaxed_distribution_tol,
            "confidence": self.confidence,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> FieldToleranceSpec:
        return cls(
            path=str(data["path"]),
            comparator=ComparatorKind(str(data["comparator"])),
            requirement=FieldRequirement(str(data.get("requirement", "required"))),
            strict_atol=float(data.get("strict_atol", 0.0)),
            strict_rtol=float(data.get("strict_rtol", 0.0)),
            relaxed_atol=_optional_float(data.get("relaxed_atol")),
            relaxed_rtol=_optional_float(data.get("relaxed_rtol")),
            scale_floor=float(data.get("scale_floor", 0.0)),
            equal_nan=bool(data.get("equal_nan", False)),
            ulp_tol=_optional_int(data.get("ulp_tol")),
            relaxed_ulp_tol=_optional_int(data.get("relaxed_ulp_tol")),
            norm_order=data.get("norm_order"),
            strict_norm_tol=_optional_float(data.get("strict_norm_tol")),
            relaxed_norm_tol=_optional_float(data.get("relaxed_norm_tol")),
            distribution_metric=_optional_string(data.get("distribution_metric")),
            strict_distribution_tol=_optional_float(data.get("strict_distribution_tol")),
            relaxed_distribution_tol=_optional_float(data.get("relaxed_distribution_tol")),
            confidence=_optional_float(data.get("confidence")),
            metadata=_coerce_mapping(data.get("metadata")),
        )


@dataclass(frozen=True, slots=True)
class FieldComparison:
    """Observed comparison outcome for one field path."""

    path: str
    comparator: ComparatorKind
    requirement: FieldRequirement
    strict_ok: bool
    relaxed_ok: bool
    missing: bool = False
    message: str = ""
    lhs_shape: tuple[int, ...] | None = None
    rhs_shape: tuple[int, ...] | None = None
    max_abs_error: float | None = None
    max_rel_error: float | None = None
    max_ulp_error: int | None = None
    norm_error: float | None = None
    distribution_error: float | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "comparator": self.comparator.value,
            "requirement": self.requirement.value,
            "strict_ok": self.strict_ok,
            "relaxed_ok": self.relaxed_ok,
            "missing": self.missing,
            "message": self.message,
            "lhs_shape": None if self.lhs_shape is None else list(self.lhs_shape),
            "rhs_shape": None if self.rhs_shape is None else list(self.rhs_shape),
            "max_abs_error": self.max_abs_error,
            "max_rel_error": self.max_rel_error,
            "max_ulp_error": self.max_ulp_error,
            "norm_error": self.norm_error,
            "distribution_error": self.distribution_error,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class EquivalenceVerificationReport:
    """Machine-readable verification outcome for one result pair."""

    certificate_id: str
    verdict: EquivalenceVerdict
    applicable: bool
    field_reports: tuple[FieldComparison, ...] = ()
    runtime_budget_validation: Mapping[str, Any] = field(default_factory=dict)
    notes: tuple[str, ...] = ()

    @property
    def failed_required_paths(self) -> tuple[str, ...]:
        return tuple(
            report.path
            for report in self.field_reports
            if report.requirement.affects_verdict and not report.relaxed_ok
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "certificate_id": self.certificate_id,
            "verdict": self.verdict.value,
            "applicable": self.applicable,
            "field_reports": [report.as_dict() for report in self.field_reports],
            "runtime_budget_validation": dict(self.runtime_budget_validation),
            "notes": list(self.notes),
            "failed_required_paths": list(self.failed_required_paths),
        }


@dataclass(frozen=True, slots=True)
class CrossBackendEquivalenceCertificate:
    """Persisted certificate describing one backend-pair tolerance budget."""

    certificate_id: str
    method_fqn: str
    runtime_envelope: EquivalenceRuntimeEnvelope
    field_specs: tuple[FieldToleranceSpec, ...]
    comparator_version: str = EQUIVALENCE_COMPARATOR_VERSION
    confidence: float | None = None
    global_verdict: EquivalenceVerdict | None = None
    provenance: Mapping[str, Any] = field(default_factory=dict)
    test_vectors: Mapping[str, Any] = field(default_factory=dict)
    created_at: str | None = None
    expires_at: str | None = None
    signer: Mapping[str, Any] = field(default_factory=dict)
    signature: Mapping[str, Any] = field(default_factory=dict)
    notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.certificate_id:
            raise ValueError("certificate_id must be non-empty")
        if not self.method_fqn:
            raise ValueError("method_fqn must be non-empty")
        if not self.field_specs:
            raise ValueError("field_specs must be non-empty")
        if self.confidence is not None and not (0.0 < self.confidence <= 1.0):
            raise ValueError("confidence must be in (0, 1]")

    def as_dict(self) -> dict[str, Any]:
        return {
            "certificate_id": self.certificate_id,
            "method_fqn": self.method_fqn,
            "runtime_envelope": self.runtime_envelope.as_dict(),
            "field_specs": [spec.as_dict() for spec in self.field_specs],
            "comparator_version": self.comparator_version,
            "confidence": self.confidence,
            "global_verdict": (None if self.global_verdict is None else self.global_verdict.value),
            "provenance": dict(self.provenance),
            "test_vectors": dict(self.test_vectors),
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "signer": dict(self.signer),
            "signature": dict(self.signature),
            "notes": list(self.notes),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> CrossBackendEquivalenceCertificate:
        return cls(
            certificate_id=str(data["certificate_id"]),
            method_fqn=str(data["method_fqn"]),
            runtime_envelope=EquivalenceRuntimeEnvelope.from_dict(
                _coerce_mapping(data["runtime_envelope"])
            ),
            field_specs=tuple(
                FieldToleranceSpec.from_dict(item)
                for item in _coerce_sequence_of_mappings(data["field_specs"])
            ),
            comparator_version=str(data.get("comparator_version", EQUIVALENCE_COMPARATOR_VERSION)),
            confidence=_optional_float(data.get("confidence")),
            global_verdict=(
                None
                if data.get("global_verdict") is None
                else EquivalenceVerdict(str(data["global_verdict"]))
            ),
            provenance=_coerce_mapping(data.get("provenance")),
            test_vectors=_coerce_mapping(data.get("test_vectors")),
            created_at=_optional_string(data.get("created_at")),
            expires_at=_optional_string(data.get("expires_at")),
            signer=_coerce_mapping(data.get("signer")),
            signature=_coerce_mapping(data.get("signature")),
            notes=tuple(str(item) for item in data.get("notes", ()) if str(item).strip()),
        )


def _coerce_mapping(value: Any) -> Mapping[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise TypeError("expected mapping payload")
    return {str(key): item for key, item in value.items()}


def _coerce_string_mapping(value: Any) -> Mapping[str, str]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise TypeError("expected mapping payload")
    return {str(key): str(item) for key, item in value.items()}


def _coerce_sequence_of_mappings(value: Any) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(value, (list, tuple)):
        raise TypeError("expected sequence of mappings")
    return tuple(_coerce_mapping(item) for item in value)


def _optional_float(value: Any) -> float | None:
    return None if value is None else float(value)


def _optional_int(value: Any) -> int | None:
    return None if value is None else int(value)


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text or None


__all__ = [
    "EQUIVALENCE_CERTIFICATE_KIND",
    "EQUIVALENCE_CERTIFICATE_SCHEMA",
    "EQUIVALENCE_CERTIFICATE_SCHEMA_VERSION",
    "EQUIVALENCE_COMPARATOR_VERSION",
    "ComparatorKind",
    "CrossBackendEquivalenceCertificate",
    "EquivalenceRuntimeEnvelope",
    "EquivalenceVerdict",
    "EquivalenceVerificationReport",
    "FieldComparison",
    "FieldRequirement",
    "FieldToleranceSpec",
]
