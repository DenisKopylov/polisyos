"""Contracts for proof-carrying incentive-compatibility verification."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.contracts.scientist import ScientistArtifactRef

ICProperty = Literal[
    "dominant_strategy_ic",
    "bayesian_ic",
    "ex_post_ir",
    "ex_interim_ir",
]
ICVerificationMode = Literal["strict_proof", "counterexample_search"]
ICBackendHint = Literal[
    "auto",
    "finite_exact",
    "envelope_1d",
    "cycmon_lp",
    "smt_lra_proof",
]
ICVerdict = Literal[
    "positive",
    "negative",
    "semantic_validation_failure",
    "unsupported_fragment",
    "inconclusive",
]
ICCertificateScope = Literal["semantic", "runtime"]
ICConformanceVerdict = Literal[
    "conformant",
    "mismatch",
    "unsupported_fragment",
    "semantic_validation_failure",
]


class ICVerificationCertificateRef(ScientistArtifactRef):
    """Reference to a positive IC certificate stored in CAS."""

    kind: str = "scientist.ic_certificate"
    media_type: str = "application/json"


class ICNegativeCertificateRef(ScientistArtifactRef):
    """Reference to a negative IC witness stored in CAS."""

    kind: str = "scientist.ic_negative_certificate"
    media_type: str = "application/json"


class ICVerificationReportRef(ScientistArtifactRef):
    """Reference to a verification report stored in CAS."""

    kind: str = "scientist.ic_report"
    media_type: str = "application/json"


class ICProofAttachmentRef(ScientistArtifactRef):
    """Reference to auxiliary proof material emitted by advanced backends."""

    kind: str = "scientist.ic_proof_attachment"
    media_type: str = "application/json"


class ICImplementationConformanceReportRef(ScientistArtifactRef):
    """Reference to an implementation-conformance report stored in CAS."""

    kind: str = "scientist.ic_conformance_report"
    media_type: str = "application/json"


class ICVerificationRequest(BaseModel):
    """Request one machine-checkable verification run over one mechanism claim."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    property: ICProperty
    mode: ICVerificationMode = "strict_proof"
    backend_hint: ICBackendHint = "auto"
    input_ref: ArtifactRef
    semantics_ref: ArtifactRef | None = None
    allow_payment_synthesis: bool = True
    exact_number_format: Literal["rational_string", "decimal_string"] = "rational_string"


class IncentiveCompatibilityCertificate(BaseModel):
    """Positive proof object for an IC claim over a declared semantic fragment."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    certificate_kind: Literal["positive"] = "positive"
    property: ICProperty
    backend: str
    input_digest: str
    arithmetic: str
    scope: ICCertificateScope = "semantic"
    witness: dict[str, Any] = Field(default_factory=dict)
    derived_payment_rule_ref: ArtifactRef | None = None
    implementation_conformance_ref: ArtifactRef | None = None
    proof_artifacts: list[ArtifactRef] = Field(default_factory=list)


class ICNegativeCertificate(BaseModel):
    """Negative proof object carrying a constructive witness against the claim."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    certificate_kind: Literal["negative"] = "negative"
    property: ICProperty
    backend: str
    input_digest: str
    arithmetic: str
    scope: ICCertificateScope = "semantic"
    witness: dict[str, Any] = Field(default_factory=dict)
    implementation_conformance_ref: ArtifactRef | None = None
    proof_artifacts: list[ArtifactRef] = Field(default_factory=list)


class ICVerificationReport(BaseModel):
    """Compact auditable summary of one verification attempt."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    property: ICProperty
    mode: ICVerificationMode
    backend: str
    verdict: ICVerdict
    input_digest: str
    players_checked: tuple[str, ...] = ()
    deviations_checked: int = Field(default=0, ge=0)
    notes: tuple[str, ...] = ()


class ICVerificationResult(BaseModel):
    """Return contract for verification services used by governance."""

    model_config = ConfigDict(extra="forbid")

    ok: bool
    verdict: ICVerdict
    certificate_ref: ICVerificationCertificateRef | ICNegativeCertificateRef | None = None
    report_ref: ICVerificationReportRef | None = None
    notes: list[str] = Field(default_factory=list)


class ICImplementationConformanceRequest(BaseModel):
    """Request an exact authored-semantics vs implementation-snapshot comparison."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    authored_semantics_ref: ArtifactRef
    implementation_semantics_ref: ArtifactRef
    backend_hint: Literal["auto", "finite_exact", "envelope_1d", "cycmon_lp"] = "auto"


class ICImplementationConformanceReport(BaseModel):
    """Auditable equality report between authored and implementation semantics."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    backend: str
    verdict: ICConformanceVerdict
    authored_digest: str
    implementation_digest: str
    mismatch_witness: dict[str, Any] = Field(default_factory=dict)
    notes: tuple[str, ...] = ()


class ICImplementationConformanceResult(BaseModel):
    """Return contract for implementation-conformance verification services."""

    model_config = ConfigDict(extra="forbid")

    ok: bool
    verdict: ICConformanceVerdict
    report_ref: ICImplementationConformanceReportRef | None = None
    notes: list[str] = Field(default_factory=list)


__all__ = [
    "ICBackendHint",
    "ICCertificateScope",
    "ICConformanceVerdict",
    "ICImplementationConformanceReport",
    "ICImplementationConformanceReportRef",
    "ICImplementationConformanceRequest",
    "ICImplementationConformanceResult",
    "ICNegativeCertificate",
    "ICNegativeCertificateRef",
    "ICProofAttachmentRef",
    "ICProperty",
    "ICVerdict",
    "ICVerificationCertificateRef",
    "ICVerificationMode",
    "ICVerificationReport",
    "ICVerificationReportRef",
    "ICVerificationRequest",
    "ICVerificationResult",
    "IncentiveCompatibilityCertificate",
]
