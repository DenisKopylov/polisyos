"""Recoverability IR certificates for missing-data proof kernel decisions.

These contracts make M-graph recoverability a first-class proof artifact rather
than a string-only diagnostic attached to a generic negative certificate.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from polisyos.ir.analytics.negative_certificate import NegativeCertificate  # noqa: TC001
from polisyos.ir.artifacts import ArtifactStore, InputRef, get_json_artifact, put_json_artifact
from polisyos.ir.canon import CanonSpec, content_hash, to_canonical_bytes
from polisyos.ir.refs import JointDecisionCertificateRef, RecoverabilityCertificateRef


class RecoverabilityCertificateStatus(str, Enum):
    """Recoverability status of a target functional under an M-graph."""

    RECOVERABLE = "recoverable"
    RECOVERABLE_UNDER_ASSUMPTIONS = "recoverable_under_assumptions"
    NOT_RECOVERABLE = "not_recoverable"


class RecoveryScope(str, Enum):
    """Which functional the certificate is about."""

    FULL_LAW = "full_law"
    CAUSAL_QUERY = "causal_query"
    OBSERVATIONAL_QUERY = "observational_query"
    REQUIRED_FACTORS = "required_factors"
    UNKNOWN = "unknown"


class RecoverabilityEstimatorFamily(str, Enum):
    """Estimator family suggested by a recoverability strategy."""

    COMPLETE_CASE = "complete_case"
    IPW = "ipw"
    AIPW = "aipw"
    G_FORMULA_REWEIGHT = "g_formula_reweight"


class RepairSetType(str, Enum):
    """Type of repair that can unlock recoverability."""

    ASSUMPTION = "assumption"
    DATA = "data"


class RepairSetTestability(str, Enum):
    """Whether a repair assumption is testable from the observed data."""

    TESTABLE = "testable"
    NOT_TESTABLE = "not_testable"
    UNKNOWN = "unknown"


class RecoveryStep(BaseModel):
    """Single certified missingness-recovery proof step."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    rule_name: str
    rule_formal_name: str = ""
    applicable_theorem: str = ""
    description: str = ""
    variables_affected: tuple[str, ...] = ()
    depth: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)


class MinimalRepairSet(BaseModel):
    """Minimal data or assumption change that would make recovery possible."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    repair_type: RepairSetType
    items: tuple[str, ...]
    testability: RepairSetTestability = RepairSetTestability.UNKNOWN
    notes: str = ""


class RecoverabilityCertificate(BaseModel):
    """Typed certificate for missing-data recoverability in an M-graph."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    target_query: str
    mgraph_fingerprint: str
    status: RecoverabilityCertificateStatus
    recovery_scope: RecoveryScope = RecoveryScope.UNKNOWN
    recovery_expression_ast: dict[str, Any] | None = None
    recovery_steps: tuple[RecoveryStep, ...] = ()
    blocking_r_nodes: tuple[str, ...] = ()
    blocking_explanation: str = ""
    minimal_repair_sets: tuple[MinimalRepairSet, ...] = ()
    recommended_estimator_family: RecoverabilityEstimatorFamily | None = None
    computable_functionals: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    completeness_regime: Literal["complete", "sound_incomplete", "heuristic_backed"] = (
        "sound_incomplete"
    )
    theorem_family: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def is_recoverable(self) -> bool:
        return self.status is RecoverabilityCertificateStatus.RECOVERABLE

    def to_summary_dict(self) -> dict[str, Any]:
        """Return the compact JSON shape embedded in proof/readiness metadata."""
        return {
            "schema_version": self.schema_version,
            "target_query": self.target_query,
            "mgraph_fingerprint": self.mgraph_fingerprint,
            "status": self.status.value,
            "recovery_scope": self.recovery_scope.value,
            "blocking_r_nodes": list(self.blocking_r_nodes),
            "blocking_r_nodes_count": len(self.blocking_r_nodes),
            "minimal_repair_sets": [
                repair.model_dump(mode="json") for repair in self.minimal_repair_sets
            ],
            "minimal_repair_set_count": len(self.minimal_repair_sets),
            "recommended_estimator_family": (
                self.recommended_estimator_family.value
                if self.recommended_estimator_family is not None
                else None
            ),
            "computable_functionals": list(self.computable_functionals),
            "warnings": list(self.warnings),
            "completeness_regime": self.completeness_regime,
            "theorem_family": self.theorem_family,
        }


class JointDecisionStatus(str, Enum):
    """Four-way joint identification and recoverability verdict."""

    IDENTIFIED_AND_RECOVERABLE = "IdentifiedAndRecoverable"
    IDENTIFIED_BUT_NOT_RECOVERABLE = "IdentifiedButNotRecoverable"
    NOT_IDENTIFIED = "NotIdentified"
    RECOVERABLE_BUT_NOT_IDENTIFIED = "RecoverableButNotIdentified"


class JointDecisionCertificate(BaseModel):
    """Top-level proof-kernel decision joining ID and recoverability."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    verdict: JointDecisionStatus
    target_query: str
    id_status: str
    recoverability: RecoverabilityCertificate
    identification_result: dict[str, Any] | None = None
    negative_certificate: NegativeCertificate | None = None
    computable_functionals: tuple[str, ...] = ()
    recommended_estimator_family: RecoverabilityEstimatorFamily | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    def to_summary_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "verdict": self.verdict.value,
            "target_query": self.target_query,
            "id_status": self.id_status,
            "recoverability": self.recoverability.to_summary_dict(),
            "computable_functionals": list(self.computable_functionals),
            "recommended_estimator_family": (
                self.recommended_estimator_family.value
                if self.recommended_estimator_family is not None
                else None
            ),
        }


def mgraph_fingerprint(payload: object) -> str:
    """Return a stable sha256 fingerprint for an M-graph-like payload."""
    if hasattr(payload, "model_dump"):
        payload = payload.model_dump(mode="json")
    canonical = to_canonical_bytes(payload, spec=CanonSpec(forbid_floats=False))
    return content_hash(canonical, prefix=True)


def persist_recoverability_certificate(
    store: ArtifactStore,
    certificate: RecoverabilityCertificate,
    *,
    inputs: list[InputRef] | None = None,
    schema_name: str = "ir.recoverability_certificate",
    schema_version: str = "1.0",
) -> RecoverabilityCertificateRef:
    """Persist a recoverability certificate and return its typed artifact ref."""

    ref = put_json_artifact(
        store,
        certificate.model_dump(mode="json"),
        kind="ir.recoverability_certificate",
        schema_name=schema_name,
        schema_version=schema_version,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return RecoverabilityCertificateRef.model_validate(ref)


def load_recoverability_certificate(
    store: ArtifactStore,
    ref: RecoverabilityCertificateRef,
) -> RecoverabilityCertificate:
    """Load a persisted recoverability certificate."""

    payload = get_json_artifact(store, ref.artifact_id)
    return RecoverabilityCertificate.model_validate(payload)


def persist_joint_decision_certificate(
    store: ArtifactStore,
    certificate: JointDecisionCertificate,
    *,
    inputs: list[InputRef] | None = None,
    schema_name: str = "ir.joint_decision_certificate",
    schema_version: str = "1.0",
) -> JointDecisionCertificateRef:
    """Persist a joint identification-recoverability decision and return its typed artifact ref."""

    ref = put_json_artifact(
        store,
        certificate.model_dump(mode="json"),
        kind="ir.joint_decision_certificate",
        schema_name=schema_name,
        schema_version=schema_version,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return JointDecisionCertificateRef.model_validate(ref)


def load_joint_decision_certificate(
    store: ArtifactStore,
    ref: JointDecisionCertificateRef,
) -> JointDecisionCertificate:
    """Load a persisted joint identification-recoverability decision."""

    payload = get_json_artifact(store, ref.artifact_id)
    return JointDecisionCertificate.model_validate(payload)


__all__ = [
    "JointDecisionCertificate",
    "JointDecisionCertificateRef",
    "JointDecisionStatus",
    "load_joint_decision_certificate",
    "load_recoverability_certificate",
    "MinimalRepairSet",
    "persist_joint_decision_certificate",
    "persist_recoverability_certificate",
    "RecoverabilityCertificate",
    "RecoverabilityCertificateRef",
    "RecoverabilityCertificateStatus",
    "RecoverabilityEstimatorFamily",
    "RecoveryScope",
    "RecoveryStep",
    "RepairSetTestability",
    "RepairSetType",
    "mgraph_fingerprint",
]
