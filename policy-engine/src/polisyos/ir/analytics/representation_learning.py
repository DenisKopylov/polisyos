"""Representation-learning and latent-confounder contracts."""
from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.ir._validation import ensure_finite_numeric, ensure_unique_ids


class RepresentationModelFamily(str, Enum):
    """Frontier representation-learning families carried as IR contracts."""

    CEVAE = "cevae"
    LATENT_SCM = "latent_scm"
    NEURAL_CAUSAL_MODEL = "neural_causal_model"
    CAUSAL_GENERATIVE_MODEL = "causal_generative_model"


class LatentTrustLevel(str, Enum):
    """Promotion level for latent/representation-learning outputs."""

    RESEARCH = "research"
    CONDITIONAL = "conditional"
    VALIDATED = "validated"


class LatentVariableSpec(BaseModel):
    """One latent variable family introduced by a representation model."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    latent_id: str = Field(min_length=1)
    dimension: int = Field(ge=1, le=4096)
    parents: tuple[str, ...] = ()
    observed_children: tuple[str, ...] = ()
    regularization_weight: float | None = Field(default=None, ge=0.0)

    @model_validator(mode="after")
    def validate_latent(self) -> "LatentVariableSpec":
        ensure_unique_ids(self.parents, key_fn=lambda item: item, label="latent parent")
        ensure_unique_ids(
            self.observed_children,
            key_fn=lambda item: item,
            label="latent observed_child",
        )
        if self.regularization_weight is not None:
            ensure_finite_numeric(
                self.regularization_weight,
                field_name=f"{self.latent_id}.regularization_weight",
            )
        return self


class RepresentationEncoderSpec(BaseModel):
    """Encoder metadata for a latent causal representation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    encoder_id: str = Field(min_length=1)
    input_fields: tuple[str, ...] = Field(..., min_length=1)
    architecture_hint: str = Field(min_length=1)
    latent_dimensions: dict[str, int] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_encoder(self) -> "RepresentationEncoderSpec":
        ensure_unique_ids(self.input_fields, key_fn=lambda item: item, label="encoder input_field")
        for latent_id, dimension in self.latent_dimensions.items():
            if not latent_id.strip():
                raise ValueError("latent_dimensions keys must be non-empty")
            if dimension <= 0:
                raise ValueError("latent_dimensions values must be positive")
        return self


class LatentConfounderContract(BaseModel):
    """Research-track contract for latent confounder / representation models."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    contract_id: str = Field(min_length=1)
    model_family: RepresentationModelFamily
    treatment_field: str = Field(min_length=1)
    outcome_field: str = Field(min_length=1)
    observed_covariates: tuple[str, ...] = ()
    latent_variables: list[LatentVariableSpec] = Field(default_factory=list)
    encoder: RepresentationEncoderSpec
    identifiability_assumptions: tuple[str, ...] = ()
    trust_level: LatentTrustLevel = LatentTrustLevel.RESEARCH
    research_gate_required: bool = True
    decision_support_allowed: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_contract(self) -> "LatentConfounderContract":
        ensure_unique_ids(
            self.observed_covariates,
            key_fn=lambda item: item,
            label="observed covariate",
        )
        ensure_unique_ids(
            self.latent_variables,
            key_fn=lambda item: item.latent_id,
            label="latent variable_id",
        )
        known_latents = {item.latent_id for item in self.latent_variables}
        if set(self.encoder.latent_dimensions) - known_latents:
            raise ValueError("encoder latent_dimensions must reference declared latent_variables")
        if self.decision_support_allowed and self.trust_level is LatentTrustLevel.RESEARCH:
            raise ValueError("research-track latent contracts cannot enable decision support")
        if self.decision_support_allowed and self.research_gate_required:
            raise ValueError(
                "decision-support latent contracts cannot keep research_gate_required=True"
            )
        return self


class RepresentationLearningResult(BaseModel):
    """Frozen result contract for latent/representation-learning runs."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    contract_id: str = Field(min_length=1)
    model_family: RepresentationModelFamily
    learned_latent_ids: tuple[str, ...] = ()
    trust_level: LatentTrustLevel = LatentTrustLevel.RESEARCH
    elbo: float | None = None
    reconstruction_loss: float | None = Field(default=None, ge=0.0)
    counterfactual_consistency_score: float | None = Field(default=None, ge=0.0, le=1.0)
    environment_invariance_score: float | None = Field(default=None, ge=0.0, le=1.0)
    warnings: tuple[str, ...] = ()
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_result(self) -> "RepresentationLearningResult":
        ensure_unique_ids(
            self.learned_latent_ids,
            key_fn=lambda item: item,
            label="learned latent_id",
        )
        for field_name in (
            "elbo",
            "reconstruction_loss",
            "counterfactual_consistency_score",
            "environment_invariance_score",
        ):
            value = getattr(self, field_name)
            if value is not None:
                ensure_finite_numeric(value, field_name=field_name)
        return self


__all__ = [
    "LatentConfounderContract",
    "LatentTrustLevel",
    "LatentVariableSpec",
    "RepresentationEncoderSpec",
    "RepresentationLearningResult",
    "RepresentationModelFamily",
]
