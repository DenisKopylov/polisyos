"""Public cross-backend equivalence certificate API."""

from __future__ import annotations

from polisyos.foundry.methods.equivalence.bounds import (
    EquivalencePolicy,
    FieldCalibrationStats,
    derive_field_tolerance_spec,
    derive_pairwise_budget,
)
from polisyos.foundry.methods.equivalence.calibrate import (
    CalibrationBattery,
    CalibrationCase,
    CalibrationResult,
    calibrate_backend_pair,
    calibrate_backend_pair_detailed,
)
from polisyos.foundry.methods.equivalence.canonicalize import (
    canonicalize_method_result,
)
from polisyos.foundry.methods.equivalence.compare import compare_field_values
from polisyos.foundry.methods.equivalence.protocol import (
    EQUIVALENCE_CERTIFICATE_KIND,
    EQUIVALENCE_CERTIFICATE_SCHEMA,
    EQUIVALENCE_CERTIFICATE_SCHEMA_VERSION,
    EQUIVALENCE_COMPARATOR_VERSION,
    ComparatorKind,
    CrossBackendEquivalenceCertificate,
    EquivalenceRuntimeEnvelope,
    EquivalenceVerdict,
    EquivalenceVerificationReport,
    FieldComparison,
    FieldRequirement,
    FieldToleranceSpec,
)
from polisyos.foundry.methods.equivalence.resolver import (
    EquivalenceCertificateResolver,
    InMemoryEquivalenceCertificateRegistry,
    ResolvedEquivalenceCertificate,
    get_default_equivalence_resolver,
    reset_default_equivalence_resolver,
    set_default_equivalence_resolver,
)
from polisyos.foundry.methods.equivalence.store import (
    EQUIVALENCE_ATTESTATION_KIND,
    EQUIVALENCE_ATTESTATION_PREDICATE_TYPE,
    EQUIVALENCE_ATTESTATION_SCHEMA,
    EQUIVALENCE_ATTESTATION_SCHEMA_VERSION,
    PersistedEquivalenceArtifacts,
    load_equivalence_certificate,
    persist_attested_equivalence_certificate,
    persist_equivalence_certificate,
    verify_persisted_equivalence_certificate,
)
from polisyos.foundry.methods.equivalence.verify import (
    assess_certificate_applicability,
    attach_equivalence_ref,
    runtime_envelope_from_results,
    verify_backend_equivalence,
)

__all__ = [
    "EQUIVALENCE_ATTESTATION_KIND",
    "EQUIVALENCE_ATTESTATION_PREDICATE_TYPE",
    "EQUIVALENCE_ATTESTATION_SCHEMA",
    "EQUIVALENCE_ATTESTATION_SCHEMA_VERSION",
    "EQUIVALENCE_CERTIFICATE_KIND",
    "EQUIVALENCE_CERTIFICATE_SCHEMA",
    "EQUIVALENCE_CERTIFICATE_SCHEMA_VERSION",
    "EQUIVALENCE_COMPARATOR_VERSION",
    "CalibrationBattery",
    "CalibrationCase",
    "CalibrationResult",
    "ComparatorKind",
    "CrossBackendEquivalenceCertificate",
    "EquivalenceCertificateResolver",
    "EquivalencePolicy",
    "EquivalenceRuntimeEnvelope",
    "EquivalenceVerdict",
    "EquivalenceVerificationReport",
    "FieldCalibrationStats",
    "FieldComparison",
    "FieldRequirement",
    "FieldToleranceSpec",
    "InMemoryEquivalenceCertificateRegistry",
    "PersistedEquivalenceArtifacts",
    "ResolvedEquivalenceCertificate",
    "assess_certificate_applicability",
    "attach_equivalence_ref",
    "calibrate_backend_pair",
    "calibrate_backend_pair_detailed",
    "canonicalize_method_result",
    "compare_field_values",
    "derive_field_tolerance_spec",
    "derive_pairwise_budget",
    "get_default_equivalence_resolver",
    "load_equivalence_certificate",
    "persist_attested_equivalence_certificate",
    "persist_equivalence_certificate",
    "reset_default_equivalence_resolver",
    "runtime_envelope_from_results",
    "set_default_equivalence_resolver",
    "verify_backend_equivalence",
    "verify_persisted_equivalence_certificate",
]
