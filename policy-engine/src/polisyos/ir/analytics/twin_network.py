"""Twin-network IR types for Pearl counterfactual queries.

A twin network duplicates the SCM graph into two parallel worlds that share
the same exogenous noise (U) variables.  This enables computing the joint
distribution P(Y(x₀), Y(x₁)) and per-unit Individual Treatment Effects (ITE).

Pearl's three-step Abduction–Action–Prediction algorithm:
  1. Abduction  – infer U from factual observation (X=x₀, Y=y₀, …)
  2. Action     – apply counterfactual intervention do(X=x₁)
  3. Prediction – forward-simulate using the abducted U to get Y(x₁)

The factual and counterfactual worlds share the *same* U realisation,
which is what creates the individual-level correlation between Y(x₀) and Y(x₁).
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from polisyos.ir._internal.validation import coerce_float
from polisyos.ir.analytics.causal_queries import (
    CausalEstimatorInterval,
    CausalResultKind,
    _causal_distribution_envelope,
)
from polisyos.ir.artifacts import ArtifactStore, InputRef  # noqa: TC001
from polisyos.ir.artifacts.contracts import ArtifactOwnerDeclaration, CanonInfo
from polisyos.ir.artifacts.io import _get_owned_json_artifact, _put_owned_json_artifact
from polisyos.ir.migrations.base import (
    CompatibilityMode,
    IRRepresentationKey,
    IRRepresentationRegistration,
    ResolvedSchemaAdmission,
    register_ir_representation,
    register_schema_version,
)
from polisyos.ir.model_layer.canon import CanonSpec
from polisyos.ir.registry.refs import TwinNetworkResultRef

if TYPE_CHECKING:
    from polisyos.ir.analytics.causal_queries import InterventionSpec
    from polisyos.ir.analytics.uncertainty import UncertaintyEnvelope
else:
    from polisyos.ir.analytics.causal_queries import InterventionSpec


class TwinWorldSample(BaseModel):
    """One realisation of the factual + counterfactual world sharing the same U."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    factual_values: dict[str, float]
    """Node values in the factual world (do(X=x₀) with abducted noise)."""

    counterfactual_values: dict[str, float]
    """Node values in the counterfactual world (do(X=x₁) with the same noise)."""

    individual_treatment_effect: float
    """ITE = counterfactual_outcome − factual_outcome for the designated outcome."""

    @field_validator("individual_treatment_effect", mode="before")
    @classmethod
    def _coerce_ite(cls, value: object) -> float:
        casted = coerce_float(value)
        if not math.isfinite(casted):
            raise ValueError("individual_treatment_effect must be finite")
        return casted


class TwinNetworkResult(BaseModel):
    """Output of a twin-network joint counterfactual query."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.1", pattern=r"^\d+\.\d+$")
    outcome_variable: str
    result_kind: CausalResultKind = CausalResultKind.ITE_DISTRIBUTION
    interval_level: float = Field(default=0.95, gt=0.0, lt=1.0)
    estimator_interval: CausalEstimatorInterval | None = None

    @model_validator(mode="before")
    @classmethod
    def _normalize_historical_result(cls, value: object) -> object:
        if isinstance(value, dict):
            version = value.get("schema_version", "1.1")
            if version not in {"1.0", "1.1"}:
                raise ValueError("unsupported twin result schema version")
            if version == "1.0":
                return {
                    **value,
                    "schema_version": "1.1",
                    "result_kind": "ite_distribution",
                    "estimator_interval": None,
                }
        return value

    factual_intervention: InterventionSpec
    """The intervention applied in the factual world (x₀)."""

    counterfactual_intervention: InterventionSpec
    """The intervention applied in the counterfactual world (x₁)."""

    # ── Potential outcome marginals ────────────────────────────────────────────
    po_factual_mean: float
    """E[Y(x₀)] — marginal mean of the factual potential outcome."""

    po_factual_std: float = Field(ge=0.0)
    """Std dev of Y(x₀)."""

    po_counter_mean: float
    """E[Y(x₁)] — marginal mean of the counterfactual potential outcome."""

    po_counter_std: float = Field(ge=0.0)
    """Std dev of Y(x₁)."""

    # ── Individual Treatment Effect ────────────────────────────────────────────
    ite_mean: float
    """E[Y(x₁) − Y(x₀)] = E[ITE].  Equals the ATE under the abduction condition."""

    ite_std: float = Field(ge=0.0)
    """Std dev of the ITE distribution — non-zero when individual responses vary."""

    ite_ci: tuple[float, float]
    """Central quantile span of the ITE distribution, not an estimator CI."""

    # ── Dependence between potential outcomes ──────────────────────────────────
    po_correlation: float = Field(ge=-1.0, le=1.0)
    """Corr(Y(x₀), Y(x₁)).

    Key twin-network quantity: positive when shared noise drives both potential
    outcomes in the same direction.  Values near 1 indicate near-deterministic
    individual responses (small ITE variance); values near 0 indicate that the
    treatment effect is highly heterogeneous across units.
    """

    # ── Optional full distributions (omit to save memory) ─────────────────────
    ite_distribution: list[float] | None = None
    po_factual_distribution: list[float] | None = None
    po_counter_distribution: list[float] | None = None

    # ── Diagnostics ───────────────────────────────────────────────────────────
    computation_time_seconds: float = Field(default=0.0, ge=0.0)
    abduction_warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    # ── Validators ────────────────────────────────────────────────────────────

    @field_validator(
        "po_factual_mean",
        "po_factual_std",
        "po_counter_mean",
        "po_counter_std",
        "ite_mean",
        "ite_std",
        "computation_time_seconds",
        mode="before",
    )
    @classmethod
    def _coerce_scalar(cls, value: object) -> float:
        casted = coerce_float(value)
        if not math.isfinite(casted):
            raise ValueError("numeric fields must be finite")
        return casted

    @field_validator("ite_ci", mode="before")
    @classmethod
    def _coerce_ci(cls, value: object) -> tuple[float, float]:
        if not isinstance(value, (tuple, list)) or len(value) != 2:
            raise ValueError("ite_ci must be a 2-element tuple/list")
        lo = coerce_float(value[0])
        hi = coerce_float(value[1])
        if not math.isfinite(lo) or not math.isfinite(hi):
            raise ValueError("ite_ci bounds must be finite")
        return (lo, hi)

    @field_validator("po_correlation", mode="before")
    @classmethod
    def _coerce_correlation(cls, value: object) -> float:
        casted = coerce_float(value)
        if not math.isfinite(casted):
            raise ValueError("po_correlation must be finite")
        return float(max(-1.0, min(1.0, casted)))

    @field_validator(
        "ite_distribution", "po_factual_distribution", "po_counter_distribution", mode="before"
    )
    @classmethod
    def _coerce_distribution(cls, value: object) -> list[float] | None:
        if value is None:
            return None
        if not isinstance(value, list):
            raise ValueError("distribution fields must be lists of floats")
        normalized: list[float] = []
        for item in value:
            casted = coerce_float(item)
            if not math.isfinite(casted):
                raise ValueError("distribution values must be finite")
            normalized.append(casted)
        return normalized

    @model_validator(mode="after")
    def _validate_result(self) -> TwinNetworkResult:
        lo, hi = self.ite_ci
        if lo > hi:
            raise ValueError("ite_ci lower cannot exceed upper")
        if not math.isfinite(self.po_correlation):
            raise ValueError("po_correlation must be finite")
        return self

    # ── Integration with uncertainty system ───────────────────────────────────

    def to_uncertainty_envelope(self) -> UncertaintyEnvelope:
        """Convert ITE summary to a standard UncertaintyEnvelope."""
        return _causal_distribution_envelope(
            kind=self.result_kind,
            point=self.ite_mean,
            bounds=self.ite_ci,
            level=self.interval_level,
            n_samples=len(self.ite_distribution) if self.ite_distribution else None,
            metadata={
                "query_type": "twin_network",
                "outcome_variable": self.outcome_variable,
                "ite_std": self.ite_std,
                "po_correlation": self.po_correlation,
                **dict(self.metadata),
            },
        )

    def to_estimator_uncertainty_envelope(self) -> UncertaintyEnvelope | None:
        """Return a separate CI over refitted replicate effect estimators."""
        return (
            self.estimator_interval.to_uncertainty_envelope() if self.estimator_interval else None
        )


# ── Persistence helpers ────────────────────────────────────────────────────────


def _family_payload_version(value: object) -> str | None:
    """Return a strict embedded version, distinguishing absence from malformed null."""
    if not isinstance(value, Mapping):
        raise ValueError("owned family payload must be an object")
    if "schema_version" not in value:
        return None
    version = value["schema_version"]
    if type(version) is not str or not version.strip():
        raise ValueError("owned family payload schema_version must be a nonempty string")
    return version


def _family_source_mapping(value: object, admission: ResolvedSchemaAdmission) -> dict[str, Any]:
    """Bind payload bytes to the exact tuple already selected from the owner snapshot."""
    if not isinstance(value, Mapping):
        raise ValueError("owned family payload must be an object")
    if _family_payload_version(value) != admission.source_registration.payload_version:
        raise ValueError("payload version differs from exact registered tuple")
    return dict(value)


def _family_profile(profile: CanonInfo, row: IRRepresentationRegistration) -> bool:
    """Require the producer's actual canonicalization profile and no profile alias."""
    return (
        profile == CanonInfo.from_spec(CanonSpec(forbid_floats=False)) and row.profile_ref is None
    )


_TWIN_LEGACY_POLICY = ("twin-network-legacy-json", "1")
_TWIN_CURRENT_POLICY = ("twin-network-current-json", "1")
_TWIN_OWNER = ArtifactOwnerDeclaration(
    contract_id="polisyos.ir.analytics.twin_network.TwinNetworkResult",
    dto_fqn="polisyos.ir.analytics.twin_network.TwinNetworkResult",
    abi_key="twin_network_result",
    registry_key="twin_network_result",
    kind="ir.twin_network_result",
    media_type="application/json",
    purpose="twin_network_result",
    policy_revision="1",
    accepted_wire_policies=(_TWIN_LEGACY_POLICY, _TWIN_CURRENT_POLICY),
    payload_version_of=_family_payload_version,
    validate_source=_family_source_mapping,
    project_for_consumer=lambda value, admission: _project_twin_result(value, admission),
    validate_profile=_family_profile,
)


def _project_twin_result(
    value: dict[str, Any], admission: ResolvedSchemaAdmission
) -> TwinNetworkResult:
    """Apply the established legacy tuple adapter; keep current-law versions generic."""
    payload = dict(value)
    row = admission.source_registration
    if (row.wire_policy_ref, row.wire_policy_revision) == _TWIN_LEGACY_POLICY:
        payload.update(
            schema_version="1.1", result_kind="ite_distribution", estimator_interval=None
        )
        payload["metadata"] = {
            **payload.get("metadata", {}),
            "source_schema_version": row.schema_version,
        }
    return TwinNetworkResult.model_validate(payload)


def _register_twin_owner() -> None:
    """Register only current writer 1.1 and parser-established persisted source 1.0."""
    for version, mode in (("1.0", CompatibilityMode.NONE), ("1.1", CompatibilityMode.BACKWARD)):
        register_schema_version(
            "twin_network_result",
            version,
            compatibility=mode,
            notes=("TwinNetworkResult exact source tuples are owner-admitted.",),
        )
    old = IRRepresentationKey("ir.twin_network_result", "1.0", "1.0")
    register_ir_representation(
        registry_key="twin_network_result",
        owner_ref=_TWIN_OWNER.contract_id,
        dto_abi=_TWIN_OWNER.dto_fqn,
        wire_policy_ref=_TWIN_LEGACY_POLICY[0],
        wire_policy_revision=_TWIN_LEGACY_POLICY[1],
        schema_name="ir.twin_network_result",
        schema_version="1.0",
        payload_version="1.0",
    )
    register_ir_representation(
        registry_key="twin_network_result",
        owner_ref=_TWIN_OWNER.contract_id,
        dto_abi=_TWIN_OWNER.dto_fqn,
        wire_policy_ref=_TWIN_CURRENT_POLICY[0],
        wire_policy_revision=_TWIN_CURRENT_POLICY[1],
        schema_name="ir.twin_network_result",
        schema_version="1.1",
        payload_version="1.1",
        writable=True,
        current=True,
        default_write=True,
        readable_from=(old,),
    )


_register_twin_owner()


def persist_twin_network_result(
    store: ArtifactStore,
    result: TwinNetworkResult,
    *,
    inputs: list[InputRef] | None = None,
    schema_name: str = "ir.twin_network_result",
    schema_version: str | None = None,
) -> TwinNetworkResultRef:
    """Persist a Twin result through the exact registered current owner row."""
    resolved_version = result.schema_version if schema_version is None else schema_version
    if resolved_version != result.schema_version:
        raise ValueError("new twin results require matching payload/CAS schema")
    ref = _put_owned_json_artifact(
        store,
        result.model_dump(mode="json"),
        owner=_TWIN_OWNER,
        schema_name=schema_name,
        schema_version=resolved_version,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return TwinNetworkResultRef.from_selected_write(ref)


def load_twin_network_result(
    store: ArtifactStore,
    ref: TwinNetworkResultRef,
) -> TwinNetworkResult:
    """Load through exact owner tuple and current reader route."""
    return _get_owned_json_artifact(store, ref, owner=_TWIN_OWNER)


__all__ = [
    "TwinNetworkResult",
    "TwinWorldSample",
    "load_twin_network_result",
    "persist_twin_network_result",
]
