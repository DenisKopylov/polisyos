"""Typed contracts for synthetic worlds, truth manifests, and evaluation runs."""

from __future__ import annotations

import json
from collections.abc import Mapping
from enum import Enum
from pathlib import Path
from typing import Any

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, field_serializer

from polisyos.ir.model_layer.canon import CanonSpec, content_hash, to_canonical_bytes


class WorldFamily(str, Enum):
    """Supported synthetic-world families."""

    CROSS_SECTIONAL = "cross_sectional"
    PANEL_DYNAMIC = "panel_dynamic"
    SPATIO_TEMPORAL = "spatio_temporal"
    SURVEY_REPEATED_CROSS_SECTION = "survey_repeated_cross_section"


class MissingnessMechanism(str, Enum):
    """Canonical missingness operators."""

    NONE = "none"
    MCAR = "mcar"
    MAR = "mar"
    MNAR = "mnar"


class MeasurementErrorKind(str, Enum):
    """Measurement-error operators."""

    NONE = "none"
    CLASSICAL_ADDITIVE = "classical_additive"
    BERKSON = "berkson"
    MISCLASSIFICATION = "misclassification"
    HEAPING = "heaping"
    TOP_CODING = "top_coding"


class SamplingDesignKind(str, Enum):
    """Sampling design operators for observed datasets."""

    CENSUS = "census"
    BERNOULLI = "bernoulli"
    STRATIFIED = "stratified"
    CLUSTERED = "clustered"


class InterventionStyle(str, Enum):
    """How interventions are assigned in the latent world."""

    STATIC = "static"
    DYNAMIC = "dynamic"
    SPATIAL = "spatial"
    SURVEY_WAVE = "survey_wave"


class TruthComputationMode(str, Enum):
    """How Bayesian/posterior ground truth is produced."""

    EXACT_POSTERIOR = "exact_posterior"
    REFERENCE_POSTERIOR = "reference_posterior"


def json_safe(value: Any) -> Any:
    """Convert arrays, numpy scalars, and nested payloads into JSON-safe values."""
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, BaseModel):
        return json_safe(value.model_dump(mode="python"))
    if isinstance(value, Mapping):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [json_safe(item) for item in value]
    return value


class MissingnessSpec(BaseModel):
    """Parameterize missingness as a standalone observation operator."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    mechanism: MissingnessMechanism = MissingnessMechanism.NONE
    rate: float = Field(default=0.0, ge=0.0, le=0.95)
    strength: float = Field(default=1.0, ge=0.0, le=10.0)
    targets: tuple[str, ...] = ()


class MeasurementErrorSpec(BaseModel):
    """Parameterize measurement error independently from the latent process."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: MeasurementErrorKind = MeasurementErrorKind.NONE
    scale: float = Field(default=0.0, ge=0.0, le=10.0)
    misclassification_probability: float = Field(default=0.0, ge=0.0, le=0.5)
    heaping_base: float = Field(default=10.0, gt=0.0)
    top_code_quantile: float = Field(default=0.98, ge=0.5, le=0.999)
    targets: tuple[str, ...] = ()


class SamplingDesignSpec(BaseModel):
    """Parameterize the observed-sample design."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: SamplingDesignKind = SamplingDesignKind.CENSUS
    inclusion_rate: float = Field(default=1.0, gt=0.0, le=1.0)
    response_rate: float = Field(default=1.0, gt=0.0, le=1.0)
    n_strata: int = Field(default=4, ge=1)
    n_clusters: int = Field(default=8, ge=1)
    calibrate_weights: bool = True


class InterventionSpec(BaseModel):
    """Declare how interventions are routed through the world."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    style: InterventionStyle = InterventionStyle.STATIC
    treatment_share: float = Field(default=0.5, ge=0.0, le=1.0)
    treatment_start_period: int | None = Field(default=None, ge=0)
    instrument_strength: float = Field(default=0.5, ge=0.0, le=10.0)
    mediation_strength: float = Field(default=0.25, ge=0.0, le=10.0)


class TruthSpec(BaseModel):
    """Configure which truth families a world should materialize."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    posterior_mode: TruthComputationMode = TruthComputationMode.REFERENCE_POSTERIOR
    include_bayesian: bool = True
    include_ml: bool = True
    include_forecasting: bool = True
    include_econometrics: bool = True
    include_survey: bool = True
    include_distributional: bool = True
    include_causal: bool = True
    extra_targets: tuple[str, ...] = ()


class EvaluationSpec(BaseModel):
    """Default evaluation policy for truth-centric benchmarks."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    default_metric_set: str = "default"
    default_hooks: tuple[str, ...] = ("coverage", "calibration", "wasserstein", "pehe")
    calibration_bins: int = Field(default=10, ge=4, le=50)
    interval_level: float = Field(default=0.9, gt=0.0, lt=1.0)


class SyntheticWorldDGP(BaseModel):
    """Versioned DGP specification for a synthetic world."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    world_id: str
    family: WorldFamily
    seed: int = 0

    world_spec_version: str = Field(default="1.0.0", pattern=r"^\d+\.\d+\.\d+$")
    truth_schema_version: str = Field(default="1.0.0", pattern=r"^\d+\.\d+\.\d+$")
    artifact_schema_version: str = Field(default="1.0.0", pattern=r"^\d+\.\d+\.\d+$")

    n_units: int = Field(default=128, ge=8)
    n_features: int = Field(default=4, ge=1)
    n_periods: int = Field(default=10, ge=3)
    n_regions: int = Field(default=8, ge=3)
    n_waves: int = Field(default=4, ge=2)
    n_strata: int = Field(default=4, ge=1)
    n_clusters: int = Field(default=8, ge=1)

    noise_scale: float = Field(default=0.4, gt=0.0)
    treatment_effect: float = Field(default=1.0, ge=-10.0, le=10.0)
    heterogeneity_scale: float = Field(default=0.3, ge=0.0, le=10.0)
    confounding_strength: float = Field(default=0.7, ge=0.0, le=10.0)
    autoregressive_scale: float = Field(default=0.65, ge=0.0, lt=0.999)
    spatial_scale: float = Field(default=0.2, ge=0.0, lt=0.999)
    classification_temperature: float = Field(default=1.0, gt=0.05, le=10.0)

    intervention: InterventionSpec = Field(default_factory=InterventionSpec)
    truth: TruthSpec = Field(default_factory=TruthSpec)
    evaluation: EvaluationSpec = Field(default_factory=EvaluationSpec)
    missingness: MissingnessSpec = Field(default_factory=MissingnessSpec)
    measurement: MeasurementErrorSpec = Field(default_factory=MeasurementErrorSpec)
    sampling: SamplingDesignSpec = Field(default_factory=SamplingDesignSpec)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def config_hash(self) -> str:
        """Stable hash over the configuration excluding the runtime seed."""
        payload = self.model_dump(mode="python", exclude={"seed"})
        canonical = to_canonical_bytes(payload, spec=CanonSpec(forbid_floats=False))
        return content_hash(canonical, prefix=True)

    @classmethod
    def from_path(cls, path: str | Path, *, seed: int | None = None) -> SyntheticWorldDGP:
        """Load a JSON/YAML world spec from disk."""
        file_path = Path(path)
        text = file_path.read_text(encoding="utf-8")
        if file_path.suffix.lower() in {".yaml", ".yml"}:
            import yaml

            payload = yaml.safe_load(text) or {}
        elif file_path.suffix.lower() == ".json":
            payload = json.loads(text)
        else:
            try:
                payload = json.loads(text)
            except json.JSONDecodeError:
                import yaml

                payload = yaml.safe_load(text) or {}
        if seed is not None:
            payload = {**payload, "seed": seed}
        return cls.model_validate(payload)


class WorldSpec(SyntheticWorldDGP):
    """Named public alias for the canonical synthetic-world spec."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class TruthQuery(BaseModel):
    """Declarative request for truth targets."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    targets: tuple[str, ...] = ()
    prefixes: tuple[str, ...] = ()
    subset: dict[str, Any] = Field(default_factory=dict)


class TruthManifest(BaseModel):
    """Ground-truth manifest emitted by a synthetic world."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    world_id: str
    family: WorldFamily
    world_spec_version: str
    truth_schema_version: str
    seed: int
    config_hash: str
    truth_policy: dict[str, Any] = Field(default_factory=dict)
    available_targets: tuple[str, ...]
    target_families: tuple[str, ...]
    targets: dict[str, dict[str, Any]]

    @field_serializer("truth_policy", "targets", when_used="json")
    def _serialize_targets(self, value: Any) -> Any:
        return json_safe(value)


class WorldArtifact(BaseModel):
    """Materialized world lineage for replay and benchmark wiring."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    world_id: str
    family: WorldFamily
    world_spec_version: str
    truth_schema_version: str
    artifact_schema_version: str
    seed: int
    config_hash: str
    split: str
    row_count: int = Field(ge=0)
    observed_columns: tuple[str, ...]
    available_targets: tuple[str, ...]
    latent_hash: str | None = None
    observed_hash: str | None = None
    truth_hash: str | None = None
    replay_key: str | None = None
    latent_artifact_ref: str | None = None
    observed_artifact_ref: str | None = None
    truth_artifact_ref: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_serializer("metadata", when_used="json")
    def _serialize_metadata(self, value: dict[str, Any]) -> dict[str, Any]:
        return json_safe(value)


class SyntheticWorldSample(BaseModel):
    """Observed or latent slice emitted by ``SyntheticWorld.sample``."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    world_id: str
    family: WorldFamily
    split: str
    seed: int
    config_hash: str
    row_count: int = Field(ge=0)
    format: str = "python"
    columns: dict[str, Any]
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_serializer("columns", "metadata", when_used="json")
    def _serialize_payload(self, value: Any) -> Any:
        return json_safe(value)


class EvaluationRun(BaseModel):
    """Truth-centric evaluation run shared by benchmarks and reports."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    world_id: str
    queried_targets: tuple[str, ...]
    metric_set: str = "default"
    metrics: dict[str, float]
    evaluation_policy: dict[str, Any] = Field(default_factory=dict)
    diagnostics: dict[str, Any] = Field(default_factory=dict)
    hooks: tuple[str, ...] = ()
    plots: dict[str, Any] = Field(default_factory=dict)

    @field_serializer("evaluation_policy", "diagnostics", "plots", when_used="json")
    def _serialize_payload(self, value: dict[str, Any]) -> dict[str, Any]:
        return json_safe(value)


class BenchmarkSuiteBinding(BaseModel):
    """Declare how one or more worlds land in the benchmark harness."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    suite_id: str
    benchmark_family: str
    case_ids: tuple[str, ...]
    world_ids: tuple[str, ...]
