"""Public observation causal readiness module API."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import Field, model_validator

from polisyos.ir.artifacts import ArtifactStore, InputRef, get_json_artifact, put_json_artifact
from polisyos.ir.canon import CanonSpec
from polisyos.ir.kernel.base import KernelModel
from polisyos.ir.observation.contracts import ObservationFamily, StrategicResponseChannel
from polisyos.ir.refs import ArtifactRefModel, CausalReadinessBundleRef

SCHEMA_VERSION_PATTERN = r"^\d+\.\d+$"
_CAUSAL_READINESS_SCHEMA_NAME = "ir.causal_readiness_bundle"
_CAUSAL_READINESS_SCHEMA_VERSION = "1.0"


class ProxyIdentificationEntry(KernelModel):
    """Readiness result for a proxy-identification pathway."""

    family: ObservationFamily
    proxy_variable: str = Field(..., min_length=1, max_length=120)
    latent_variable: str = Field(..., min_length=1, max_length=120)
    status: Literal["identified", "oracle_needed"]
    verification_method: str = Field(default="identify_with_proxy", min_length=1, max_length=120)
    measurement_model: str = Field(default="unknown", min_length=1, max_length=32)
    estimand_ast: dict[str, Any] | None = None
    proof_steps: list[dict[str, Any]] = Field(default_factory=list)
    trace: list[str] = Field(default_factory=list)
    normalized_reason: str | None = Field(default=None, max_length=255)
    metadata: dict[str, Any] = Field(default_factory=dict)


class TransportabilityCheckEntry(KernelModel):
    """Readiness result for one transportability check."""

    check_id: str = Field(..., min_length=1, max_length=120)
    family: ObservationFamily | None = None
    status: Literal["identified", "partially_identified", "blocked"]
    cross_regime: bool = False
    result_ref: ArtifactRefModel | None = None
    blocking_s_nodes: list[str] = Field(default_factory=list)
    identification_engine: str = Field(default="", max_length=120)
    normalized_reason: str | None = Field(default=None, max_length=255)
    trace: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class StrategicResponseEntry(KernelModel):
    """Readiness result for a strategic-response channel or intervention kind."""

    channel: StrategicResponseChannel
    intervention_kind: str | None = Field(default=None, max_length=120)
    status: Literal["ready", "blocked"]
    fallback_mode: str = Field(default="", max_length=120)
    strategic_scm_ref: ArtifactRefModel | None = None
    strategic_response_bundle_ref: ArtifactRefModel | None = None
    performative_shift: float | None = None
    warnings: list[str] = Field(default_factory=list)
    blocked_reason: str | None = Field(default=None, max_length=255)
    summary: dict[str, Any] = Field(default_factory=dict)


class CounterfactualCheckEntry(KernelModel):
    """Readiness result for a counterfactual query request."""

    query_id: str = Field(..., min_length=1, max_length=120)
    family: ObservationFamily | None = None
    status: str = Field(..., min_length=1, max_length=64)
    query_kind: str = Field(default="generic", min_length=1, max_length=120)
    algorithm_version: str = Field(default="", max_length=120)
    normalized_query: str = Field(default="", max_length=500)
    estimand_ast: dict[str, Any] | None = None
    hedge_certificate: dict[str, Any] | None = None
    trace: list[str] = Field(default_factory=list)
    normalized_reason: str | None = Field(default=None, max_length=255)
    metadata: dict[str, Any] = Field(default_factory=dict)


class InterferenceReadinessEntry(KernelModel):
    """Readiness descriptor for an interference-aware loss target."""

    spec_id: str = Field(..., min_length=1, max_length=120)
    family: ObservationFamily
    predicted_metric_path: str = Field(..., min_length=1, max_length=255)
    ready: bool = True
    notes: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class CausalReadinessBundle(KernelModel):
    """Persistable bundle of causal-readiness checks.

    Collects the proxy, transportability, strategic-response, counterfactual,
    and interference checks that must pass before Scientist launches a full
    causal execution run.
    """

    schema_version: str = Field("1.0", pattern=SCHEMA_VERSION_PATTERN)
    proxy_results: list[ProxyIdentificationEntry] = Field(default_factory=list)
    transport_results: list[TransportabilityCheckEntry] = Field(default_factory=list)
    strategic_results: list[StrategicResponseEntry] = Field(default_factory=list)
    counterfactual_results: list[CounterfactualCheckEntry] = Field(default_factory=list)
    interference_specs: list[InterferenceReadinessEntry] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_unique_ids(self) -> "CausalReadinessBundle":
        def _ensure_unique(values: list[str], *, label: str) -> None:
            if len(set(values)) != len(values):
                raise ValueError(f"{label} must be unique")

        _ensure_unique([item.check_id for item in self.transport_results], label="transport_results.check_id")
        _ensure_unique([item.query_id for item in self.counterfactual_results], label="counterfactual_results.query_id")
        _ensure_unique([item.spec_id for item in self.interference_specs], label="interference_specs.spec_id")
        return self


def persist_causal_readiness_bundle(
    store: ArtifactStore,
    bundle: CausalReadinessBundle,
    *,
    inputs: list[InputRef] | None = None,
    schema_name: str = _CAUSAL_READINESS_SCHEMA_NAME,
    schema_version: str = _CAUSAL_READINESS_SCHEMA_VERSION,
) -> CausalReadinessBundleRef:
    """Persist a causal-readiness bundle to the artifact store."""

    ref = put_json_artifact(
        store,
        bundle.model_dump(mode="json"),
        kind="ir.causal_readiness_bundle",
        schema_name=schema_name,
        schema_version=schema_version,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return CausalReadinessBundleRef.model_validate(ref)


def load_causal_readiness_bundle(
    store: ArtifactStore,
    ref: CausalReadinessBundleRef,
) -> CausalReadinessBundle:
    """Load a persisted causal-readiness bundle from the artifact store."""

    payload = get_json_artifact(store, ref.artifact_id)
    return CausalReadinessBundle.model_validate(payload)


__all__ = [
    "CausalReadinessBundle",
    "CounterfactualCheckEntry",
    "InterferenceReadinessEntry",
    "ProxyIdentificationEntry",
    "StrategicResponseEntry",
    "TransportabilityCheckEntry",
    "load_causal_readiness_bundle",
    "persist_causal_readiness_bundle",
]
