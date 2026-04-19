"""Proximal causal identification certificate IR.

The objects in this module are intentionally estimator-agnostic. They record
the machine-checked graph obligations, the bridge equations that must be solved
by an estimator, and the non-graphical assumptions that make the proximal
identification argument sound.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.ir.artifacts import ArtifactStore, InputRef, get_json_artifact, put_json_artifact
from polisyos.ir.canon import CanonSpec
from polisyos.ir.refs import ProximalIdentificationCertificateRef


class ProxyAnnotation(BaseModel):
    """User/developer supplied proximal proxy annotation.

    ``treatment_inducing`` corresponds to Z-proxies and ``outcome_inducing`` to
    W-proxies in the proximal causal inference literature.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    treatment_inducing: tuple[str, ...] = Field(default_factory=tuple)
    outcome_inducing: tuple[str, ...] = Field(default_factory=tuple)
    covariates: tuple[str, ...] = Field(default_factory=tuple)
    estimand: Literal["ATE", "ATT", "MEAN_EFFECT"] = "ATE"
    include_treatment_bridge: bool = True

    @model_validator(mode="after")
    def _normalize_sets(self) -> ProxyAnnotation:
        for field_name in ("treatment_inducing", "outcome_inducing", "covariates"):
            values = tuple(str(item).strip() for item in getattr(self, field_name))
            if any(not item for item in values):
                raise ValueError(f"{field_name} must not contain empty variable names")
            if len(set(values)) != len(values):
                raise ValueError(f"{field_name} must not contain duplicate variables")
            object.__setattr__(self, field_name, tuple(sorted(values)))
        return self


class ProximalQuerySpec(BaseModel):
    """Machine-readable target query for a proximal certificate."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    estimand: Literal["ATE", "ATT", "MEAN_EFFECT"] = "ATE"
    treatment: tuple[str, ...]
    outcome: tuple[str, ...]
    covariates: tuple[str, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def _validate_query_scope(self) -> ProximalQuerySpec:
        if len(self.treatment) != 1:
            raise ValueError("proximal v1 supports exactly one treatment")
        if len(self.outcome) != 1:
            raise ValueError("proximal v1 supports exactly one outcome")
        for field_name in ("treatment", "outcome", "covariates"):
            values = tuple(str(item).strip() for item in getattr(self, field_name))
            if any(not item for item in values):
                raise ValueError(f"{field_name} must not contain empty variable names")
            if len(set(values)) != len(values):
                raise ValueError(f"{field_name} must not contain duplicate variables")
            object.__setattr__(self, field_name, tuple(sorted(values)))
        return self


class ProximalGraphClass(BaseModel):
    """Declared graph class covered by a proximal certificate."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = "PCI-Core"
    graph_type_required: tuple[Literal["admg", "dag"], ...] = ("admg", "dag")
    notes: str = (
        "v1: single treatment, single outcome; conservative sufficient "
        "graphical checks for proximal bridge identification."
    )


class ProximalGraphCheck(BaseModel):
    """One machine-checkable graph obligation and optional witness data."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    check: str
    status: Literal["pass", "fail"]
    source: str | None = None
    target: str | None = None
    source_set: tuple[str, ...] = Field(default_factory=tuple)
    target_set: tuple[str, ...] = Field(default_factory=tuple)
    requirements: tuple[str, ...] = Field(default_factory=tuple)
    witness: dict[str, Any] = Field(default_factory=dict)
    detail: str = ""


class ProximalAssumption(BaseModel):
    """Explicit graphical or non-graphical assumption in the certificate."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    type: str
    statement: str
    source: str = "proximal_causal_inference"
    machine_checkable: bool = False


class BridgeFunctionSpec(BaseModel):
    """A confounding bridge equation emitted by the proximal identifier."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    role: Literal["outcome_bridge", "treatment_bridge"]
    domain: tuple[str, ...]
    equation_type: Literal["conditional_expectation", "integral_equation"]
    equation: str
    assumptions: tuple[ProximalAssumption, ...] = Field(default_factory=tuple)
    optional: bool = False


class IdentifiedFunctional(BaseModel):
    """Final identified functional certified by the proximal proof."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    target: Literal["ATE", "ATT", "MEAN_EFFECT"]
    expression: str
    preferred: bool = False
    bridge_role: Literal["outcome_bridge", "treatment_bridge", "doubly_robust"] | None = None


class ProximalIdentificationCertificate(BaseModel):
    """Constructive proximal identification proof artifact."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    query: ProximalQuerySpec
    proxies: ProxyAnnotation
    graph_class: ProximalGraphClass = Field(default_factory=ProximalGraphClass)
    graph_checks: tuple[ProximalGraphCheck, ...] = Field(default_factory=tuple)
    bridge_functions: tuple[BridgeFunctionSpec, ...] = Field(default_factory=tuple)
    identified_functionals: tuple[IdentifiedFunctional, ...] = Field(default_factory=tuple)
    assumptions: tuple[str, ...] = Field(default_factory=tuple)
    proof_trace: tuple[str, ...] = Field(default_factory=tuple)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_certificate(self) -> ProximalIdentificationCertificate:
        if not self.bridge_functions:
            raise ValueError("a proximal certificate must declare at least one bridge function")
        if not self.identified_functionals:
            raise ValueError("a proximal certificate must declare an identified functional")
        failed_checks = [item.check for item in self.graph_checks if item.status == "fail"]
        if failed_checks:
            raise ValueError(f"proximal certificate cannot include failed checks: {failed_checks}")
        return self


def persist_proximal_identification_certificate(
    store: ArtifactStore,
    certificate: ProximalIdentificationCertificate,
    *,
    inputs: list[InputRef] | None = None,
    schema_name: str = "ir.proximal_identification_certificate",
    schema_version: str = "1.0",
) -> ProximalIdentificationCertificateRef:
    """Persist a proximal identification certificate and return its typed artifact ref."""

    ref = put_json_artifact(
        store,
        certificate.model_dump(mode="json"),
        kind="ir.proximal_identification_certificate",
        schema_name=schema_name,
        schema_version=schema_version,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return ProximalIdentificationCertificateRef.model_validate(ref)


def load_proximal_identification_certificate(
    store: ArtifactStore,
    ref: ProximalIdentificationCertificateRef,
) -> ProximalIdentificationCertificate:
    """Load a persisted proximal identification certificate."""

    payload = get_json_artifact(store, ref.artifact_id)
    return ProximalIdentificationCertificate.model_validate(payload)


__all__ = [
    "BridgeFunctionSpec",
    "IdentifiedFunctional",
    "load_proximal_identification_certificate",
    "ProximalAssumption",
    "ProximalGraphCheck",
    "ProximalGraphClass",
    "ProximalIdentificationCertificate",
    "ProximalQuerySpec",
    "ProxyAnnotation",
    "persist_proximal_identification_certificate",
]
