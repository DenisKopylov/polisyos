from __future__ import annotations

import math
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.ir.analytics.context import ContextProfile
from polisyos.ir.analytics.causal_graph import (
    CausalEdge,
    CausalGraphModel,
    EdgeSource,
    GraphType,
)
from polisyos.ir.canon import CanonSpec
from polisyos.ir.artifacts import ArtifactStore, InputRef, get_json_artifact, put_json_artifact
from polisyos.ir.artifacts.contracts import ArtifactID
from polisyos.ir.refs import LiteratureCausalPriorRef


class ParameterType(str, Enum):
    QUANTITATIVE = "quantitative"
    QUALITATIVE = "qualitative"
    ORDINAL = "ordinal"
    DISTRIBUTIONAL = "distributional"


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
    AMBIGUOUS = "ambiguous"
    NON_LINEAR = "non_linear"


class EvidenceParameter(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    display_name: str = ""
    parameter_type: ParameterType = ParameterType.QUANTITATIVE

    value: float | None = None
    value_range: tuple[float, float] | None = None
    value_qualitative: str | None = None
    confidence_interval: tuple[float, float] | None = None
    std_error: float | None = None
    unit: str | None = None

    evidence_strength: EvidenceStrength = EvidenceStrength.UNKNOWN
    geographic_scope: str = ""
    time_period: str = ""
    aggregation_level: str = ""

    transferability: str = "unknown"
    transfer_conditions: list[str] = Field(default_factory=list)
    heterogeneity_note: str | None = None
    subgroup_estimates: dict[str, float] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_value_present(self) -> "EvidenceParameter":
        if self.value is None and self.value_range is None and self.value_qualitative is None:
            raise ValueError("At least one of value, value_range, value_qualitative is required")
        if self.confidence_interval is not None:
            lo, hi = self.confidence_interval
            if not (math.isfinite(lo) and math.isfinite(hi) and lo <= hi):
                raise ValueError(f"Invalid confidence_interval: ({lo}, {hi})")
        return self


class CausalClaim(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cause_variable: str
    effect_variable: str
    direction: CausalDirection = CausalDirection.MIXED
    magnitude_qualitative: str | None = None
    effect_size: float | None = None
    evidence_strength: EvidenceStrength = EvidenceStrength.UNKNOWN
    scope_conditions: list[str] = Field(default_factory=list)
    counterevidence_notes: str = ""

    @model_validator(mode="before")
    @classmethod
    def _upgrade_legacy_claim(cls, data: object) -> object:
        if not isinstance(data, dict):
            return data
        payload = dict(data)
        if "cause_variable" not in payload and "cause" in payload:
            payload["cause_variable"] = payload.get("cause")
        if "effect_variable" not in payload and "effect" in payload:
            payload["effect_variable"] = payload.get("effect")
        payload.pop("cause", None)
        payload.pop("effect", None)
        direction = str(payload.get("direction") or "").strip().lower()
        if direction == "mixed":
            payload["direction"] = CausalDirection.MIXED.value
        return payload


class Mechanism(BaseModel):
    model_config = ConfigDict(extra="forbid")

    description: str
    mediating_variables: list[str] = Field(default_factory=list)
    evidence_type: str = ""
    theoretical_framework: str | None = None


class BoundaryCondition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    variable: str = ""
    condition_type: str = ""
    required_value: str | float | None = None
    violated_by: list[str] = Field(default_factory=list)
    consequence_if_violated: str = ""

    # legacy fields (v1.0)
    operator: str = ""
    threshold_value: str = ""
    scope_text: str = ""
    confidence: float = 0.0

    @model_validator(mode="before")
    @classmethod
    def _upgrade_legacy_boundary(cls, data: object) -> object:
        if not isinstance(data, dict):
            return data
        payload = dict(data)
        if not payload.get("condition_type"):
            payload["condition_type"] = "threshold" if payload.get("operator") else "categorical"
        if payload.get("required_value") is None:
            if payload.get("threshold_value") not in (None, ""):
                payload["required_value"] = str(payload.get("threshold_value"))
            elif payload.get("scope_text"):
                payload["required_value"] = str(payload.get("scope_text"))
        if not payload.get("consequence_if_violated"):
            payload["consequence_if_violated"] = "effect transportability may fail"
        return payload


class ArticleExtractionResult(BaseModel):
    """Primary IR contract for literature extraction pipeline."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.1"
    openalex_id: str
    doi: str = ""
    title: str

    # v1.1 canonical field
    year: int | None = None
    # v1.0 compatibility
    publication_year: int | None = None

    cited_by_count: int = 0

    methodology: str = ""
    methodology_enum: EvidenceStrength = EvidenceStrength.UNKNOWN
    sample_size: int | None = None

    empirical_parameters: list[EvidenceParameter] = Field(default_factory=list)
    causal_claims: list[CausalClaim] = Field(default_factory=list)
    mechanisms: list[Mechanism] = Field(default_factory=list)
    boundary_conditions: list[BoundaryCondition] = Field(default_factory=list)
    citation_summary: str = ""

    extraction_model: str
    extraction_timestamp: str
    extraction_confidence: float

    source_context: ContextProfile | None = None

    screening_cost_usd: float = 0.0
    extraction_cost_usd: float = 0.0
    token_count_prompt: int = 0
    token_count_completion: int = 0

    @model_validator(mode="before")
    @classmethod
    def _upgrade_legacy_payload(cls, data: object) -> object:
        if not isinstance(data, dict):
            return data
        payload = dict(data)
        if "year" not in payload and "publication_year" in payload:
            payload["year"] = payload.get("publication_year")
        if "publication_year" not in payload and "year" in payload:
            payload["publication_year"] = payload.get("year")
        if "schema_version" not in payload:
            payload["schema_version"] = (
                "1.0"
                if "publication_year" in payload and "year" not in payload
                else "1.1"
            )
        return payload

    @model_validator(mode="after")
    def _validate_confidence(self) -> "ArticleExtractionResult":
        if not (0.0 <= self.extraction_confidence <= 1.0):
            raise ValueError(f"extraction_confidence must be [0,1], got {self.extraction_confidence}")
        if self.year is None and self.publication_year is not None:
            self.year = self.publication_year
        if self.publication_year is None and self.year is not None:
            self.publication_year = self.year
        return self


class LiteratureEdgePrior(BaseModel):
    model_config = ConfigDict(extra="forbid")

    src: str
    dst: str
    confidence: float = Field(ge=0.0, le=1.0)
    n_articles: int = Field(default=0, ge=0)
    evidence_strength: EvidenceStrength = EvidenceStrength.UNKNOWN
    article_refs: list[str] = Field(default_factory=list)
    scope_conditions: list[str] = Field(default_factory=list)
    direction: CausalDirection = CausalDirection.MIXED
    meta_effect_size: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ReconciliationDiagnostics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cyclic_inconsistency_norm: float = Field(default=0.0, ge=0.0)
    irreducible_conflict_norm: float = Field(default=0.0, ge=0.0)
    gradient_norm: float = Field(default=0.0, ge=0.0)
    curl_norm: float = Field(default=0.0, ge=0.0)
    harmonic_norm: float = Field(default=0.0, ge=0.0)
    diagnostics_truncated: bool = False
    truncation_reason: str | None = None
    d0_shape: tuple[int, int] = (0, 0)
    d1_shape: tuple[int, int] = (0, 0)
    delta0_shape: tuple[int, int] = (0, 0)
    delta1_shape: tuple[int, int] = (0, 0)
    n_components: int = 0
    n_sources: int = 0
    n_edges: int = 0
    n_triangles: int = 0
    operators: dict[str, Any] = Field(default_factory=dict)


class LiteratureCausalPrior(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    edges: list[LiteratureEdgePrior] = Field(default_factory=list)
    skg_version_id: int | None = None
    skg_snapshot_ref: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    def to_causal_graph_model(
        self,
        *,
        nodes: list[str] | None = None,
        min_confidence: float = 0.0,
    ) -> CausalGraphModel:
        node_set: set[str] = set(nodes or [])
        graph_edges: list[CausalEdge] = []
        for edge in self.edges:
            if edge.confidence < min_confidence:
                continue
            node_set.add(edge.src)
            node_set.add(edge.dst)
            edge_metadata = dict(edge.metadata)
            edge_metadata.setdefault("evidence_strength", edge.evidence_strength.value)
            edge_metadata.setdefault("scope_conditions", list(edge.scope_conditions))
            edge_metadata.setdefault("direction", edge.direction.value)
            if edge.meta_effect_size is not None:
                edge_metadata.setdefault("meta_effect_size", float(edge.meta_effect_size))
            graph_edges.append(
                CausalEdge(
                    src=edge.src,
                    dst=edge.dst,
                    sources=[EdgeSource.LITERATURE],
                    literature_confidence=edge.confidence,
                    combined_confidence=edge.confidence,
                    evidence_refs=list(edge.article_refs),
                    metadata=edge_metadata,
                )
            )

        return CausalGraphModel(
            graph_type=GraphType.CPDAG,
            nodes=sorted(node_set),
            edges=graph_edges,
            discovery_method="literature_prior",
            skg_version_id=self.skg_version_id,
            metadata={
                "skg_snapshot_ref": self.skg_snapshot_ref,
                "literature_prior_edge_count": len(graph_edges),
                **self.metadata,
            },
        )


_SCHEMA_NAME = "ir.article_extraction_result"
_SCHEMA_VERSION = "1.1"
_LITERATURE_PRIOR_SCHEMA_NAME = "ir.literature_causal_prior"
_LITERATURE_PRIOR_SCHEMA_VERSION = "1.0"


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
        canon_spec=CanonSpec(forbid_floats=False),
    )


def load_article_extraction_result(store: ArtifactStore, ref: object) -> ArticleExtractionResult:
    artifact_id = ref.artifact_id if hasattr(ref, "artifact_id") else ref
    artifact = artifact_id if isinstance(artifact_id, ArtifactID) else ArtifactID(str(artifact_id))
    payload = get_json_artifact(store, artifact)
    return ArticleExtractionResult.model_validate(payload)


def persist_literature_causal_prior(
    store: ArtifactStore,
    prior: LiteratureCausalPrior,
    *,
    inputs: list[InputRef] | None = None,
) -> LiteratureCausalPriorRef:
    ref = put_json_artifact(
        store,
        prior.model_dump(mode="json"),
        kind=_LITERATURE_PRIOR_SCHEMA_NAME,
        schema_name=_LITERATURE_PRIOR_SCHEMA_NAME,
        schema_version=_LITERATURE_PRIOR_SCHEMA_VERSION,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return LiteratureCausalPriorRef.model_validate(ref)


def load_literature_causal_prior(
    store: ArtifactStore,
    ref: LiteratureCausalPriorRef | object,
) -> LiteratureCausalPrior:
    artifact_id = ref.artifact_id if hasattr(ref, "artifact_id") else ref
    artifact = artifact_id if isinstance(artifact_id, ArtifactID) else ArtifactID(str(artifact_id))
    payload = get_json_artifact(store, artifact)
    return LiteratureCausalPrior.model_validate(payload)


__all__ = [
    "ParameterType",
    "EvidenceStrength",
    "CausalDirection",
    "EvidenceParameter",
    "CausalClaim",
    "Mechanism",
    "BoundaryCondition",
    "ArticleExtractionResult",
    "LiteratureEdgePrior",
    "ReconciliationDiagnostics",
    "LiteratureCausalPrior",
    "persist_article_extraction_result",
    "load_article_extraction_result",
    "persist_literature_causal_prior",
    "load_literature_causal_prior",
]
