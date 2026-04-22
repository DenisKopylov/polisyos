"""Persist pre-execution causal-readiness checks for observation-derived bundles.

Readiness bundles sit between compiled observation manifests and full Scientist
execution: they record proxy identification, transportability, strategic
response, counterfactual, and interference preflight outcomes so downstream
runners can block, downgrade, or proceed with a causal execution bundle.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field, model_validator

from polisyos.ir._validation import ensure_non_empty_dotted_path, ensure_unique_ids
from polisyos.ir.artifacts import ArtifactStore, InputRef, get_json_artifact, put_json_artifact
from polisyos.ir.canon import CanonSpec
from polisyos.ir.kernel.base import KernelModel
from polisyos.ir.observation.contracts import ObservationFamily, StrategicResponseChannel
from polisyos.ir.refs import ArtifactRefModel, CausalReadinessBundleRef

SCHEMA_VERSION_PATTERN = r"^\d+\.\d+$"
_CAUSAL_READINESS_SCHEMA_NAME = "ir.causal_readiness_bundle"
_CAUSAL_READINESS_SCHEMA_VERSION = "1.0"


class ProxyIdentificationEntry(KernelModel):
    """Record whether a proxy pathway is identified or requires oracle support.

    The ``status`` field is read by readiness orchestration before proxy-based
    estimators run; ``oracle_needed`` should trigger escalation or fallback to a
    bounds-only route.
    """

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
    """Store one transportability preflight result and its blocking S-nodes.

    Scientist readiness gates use ``status`` and ``result_ref`` to decide whether
    a transported estimand can proceed, must fall back to partial identification,
    or is blocked by unresolved selection shifts.
    """

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
    """Summarize whether a strategic-response channel is ready or blocked.

    ``status`` and ``fallback_mode`` are consumed by strategic-response runners
    and policy governance to decide whether naive evaluation is safe or whether
    a strategic SCM/bundle must be used instead.
    """

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
    """Store counterfactual query preflight metadata and identification status."""

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
    """Declare whether an interference-aware loss target can be materialized."""

    spec_id: str = Field(..., min_length=1, max_length=120)
    family: ObservationFamily
    predicted_metric_path: str = Field(..., min_length=1, max_length=255)
    ready: bool = True
    supports_areal_interference: bool = False
    interference_topology_ready: bool | None = None
    maup_scale_declared: bool | None = None
    zoning_sensitivity_ready: bool | None = None
    aggregation_rule_consistent: bool | None = None
    measurement_error_bounded: bool | None = None
    notes: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_entry(self) -> "InterferenceReadinessEntry":
        ensure_non_empty_dotted_path(
            self.predicted_metric_path,
            field_name="predicted_metric_path",
            max_depth=16,
        )
        if not self.supports_areal_interference:
            return self
        if self.maup_scale_declared is None:
            raise ValueError(
                "maup_scale_declared must be set when supports_areal_interference is true"
            )
        if self.interference_topology_ready is None:
            raise ValueError(
                "interference_topology_ready must be set when supports_areal_interference is true"
            )
        if self.zoning_sensitivity_ready is None:
            raise ValueError(
                "zoning_sensitivity_ready must be set when supports_areal_interference is true"
            )
        if self.aggregation_rule_consistent is None:
            raise ValueError(
                "aggregation_rule_consistent must be set when supports_areal_interference is true"
            )
        if self.measurement_error_bounded is None:
            raise ValueError(
                "measurement_error_bounded must be set when supports_areal_interference is true"
            )
        return self


class CausalReadinessBundle(KernelModel):
    """Persist the complete pre-execution readiness ledger for causal runners.

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
        ensure_unique_ids(
            self.proxy_results,
            key_fn=lambda item: (item.family.value, item.proxy_variable, item.latent_variable),
            label="proxy_results",
        )
        ensure_unique_ids(
            self.transport_results,
            key_fn=lambda item: item.check_id,
            label="transport_results.check_id",
        )
        ensure_unique_ids(
            self.strategic_results,
            key_fn=lambda item: (item.channel.value, item.intervention_kind or ""),
            label="strategic_results",
        )
        ensure_unique_ids(
            self.counterfactual_results,
            key_fn=lambda item: item.query_id,
            label="counterfactual_results.query_id",
        )
        ensure_unique_ids(
            self.interference_specs,
            key_fn=lambda item: item.spec_id,
            label="interference_specs.spec_id",
        )
        return self


def persist_causal_readiness_bundle(
    store: ArtifactStore,
    bundle: CausalReadinessBundle,
    *,
    inputs: list[InputRef] | None = None,
    schema_name: str = _CAUSAL_READINESS_SCHEMA_NAME,
    schema_version: str = _CAUSAL_READINESS_SCHEMA_VERSION,
) -> CausalReadinessBundleRef:
    """Persist readiness checks as a content-addressed IR artifact.

    Args:
        store: Artifact store that owns the JSON artifact payload.
        bundle: Readiness results to serialize.
        inputs: Optional upstream artifact refs for lineage.
        schema_name: Schema identifier written to artifact metadata.
        schema_version: Schema version written to artifact metadata.

    Returns:
        A typed artifact reference for the stored readiness bundle.
    """

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
    """Load and validate a persisted readiness bundle from artifact storage.

    Args:
        store: Artifact store containing the bundle payload.
        ref: Typed reference returned by ``persist_causal_readiness_bundle``.

    Returns:
        The validated readiness bundle.
    """

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
