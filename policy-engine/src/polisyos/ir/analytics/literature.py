from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.ir.analytics.context import ContextProfile
from polisyos.ir.artifacts import ArtifactStore, InputRef, get_json_artifact, put_json_artifact


class ParameterType(str, Enum):
    QUANTITATIVE = "quantitative"
    QUALITATIVE = "qualitative"


class EvidenceStrength(str, Enum):
    RCT = "rct"
    QUASI_NATURAL = "quasi_natural"
    META_ANALYSIS = "meta_analysis"
    OBSERVATIONAL = "observational"
    THEORETICAL = "theoretical"
    UNKNOWN = "unknown"


class CausalDirection(str, Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NULL = "null"
    MIXED = "mixed"


class EvidenceParameter(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    value: float | None = None
    confidence_interval: tuple[float, float] | None = None
    std_error: float | None = None
    parameter_type: ParameterType = ParameterType.QUANTITATIVE
    evidence_strength: EvidenceStrength = EvidenceStrength.UNKNOWN
    geographic_scope: str = ""
    time_period: str = ""
    transferability: str = "unknown"
    transfer_conditions: list[str] = Field(default_factory=list)


class CausalClaim(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cause_variable: str
    effect_variable: str
    direction: CausalDirection = CausalDirection.MIXED
    effect_size: float | None = None
    evidence_strength: EvidenceStrength = EvidenceStrength.UNKNOWN
    scope_conditions: list[str] = Field(default_factory=list)
    counterevidence_notes: str = ""


class BoundaryCondition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    variable: str = ""
    operator: str = ""
    threshold_value: str = ""
    scope_text: str = ""
    confidence: float = 0.0


class ArticleExtractionResult(BaseModel):
    """Primary IR contract for literature extraction pipeline."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    openalex_id: str
    doi: str = ""
    title: str
    publication_year: int | None = None
    cited_by_count: int = 0

    methodology: str = ""
    methodology_enum: EvidenceStrength = EvidenceStrength.UNKNOWN
    sample_size: int | None = None

    empirical_parameters: list[EvidenceParameter] = Field(default_factory=list)
    causal_claims: list[CausalClaim] = Field(default_factory=list)
    boundary_conditions: list[BoundaryCondition] = Field(default_factory=list)

    extraction_model: str
    extraction_timestamp: str
    extraction_confidence: float

    source_context: ContextProfile | None = None

    screening_cost_usd: float = 0.0
    extraction_cost_usd: float = 0.0
    token_count_prompt: int = 0
    token_count_completion: int = 0

    @model_validator(mode="after")
    def _validate_confidence(self) -> "ArticleExtractionResult":
        if not (0.0 <= self.extraction_confidence <= 1.0):
            raise ValueError(f"extraction_confidence must be [0,1], got {self.extraction_confidence}")
        return self


_SCHEMA_NAME = "ir.article_extraction_result"
_SCHEMA_VERSION = "1.0"


def persist_article_extraction_result(
    store: ArtifactStore,
    result: ArticleExtractionResult,
    *,
    inputs: list[InputRef] | None = None,
) -> dict:
    return put_json_artifact(
        store,
        result.model_dump(mode="json"),
        kind=_SCHEMA_NAME,
        schema_name=_SCHEMA_NAME,
        schema_version=_SCHEMA_VERSION,
        inputs=inputs,
    )


def load_article_extraction_result(store: ArtifactStore, ref: object) -> ArticleExtractionResult:
    artifact_id = ref.artifact_id if hasattr(ref, "artifact_id") else ref
    payload = get_json_artifact(store, artifact_id)
    return ArticleExtractionResult.model_validate(payload)


__all__ = [
    "ParameterType",
    "EvidenceStrength",
    "CausalDirection",
    "EvidenceParameter",
    "CausalClaim",
    "BoundaryCondition",
    "ArticleExtractionResult",
    "persist_article_extraction_result",
    "load_article_extraction_result",
]
