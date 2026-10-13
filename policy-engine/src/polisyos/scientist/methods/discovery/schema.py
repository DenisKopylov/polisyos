"""Typed discovery contracts for graph-hypothesis search."""

from __future__ import annotations

from enum import Enum
from functools import lru_cache
from types import UnionType
from typing import Annotated, Any, Literal, Union, get_args, get_origin

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.core.artifacts.manifest import InputRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.core.contracts.scientist import GraphHypothesisRef
from polisyos.ir.analytics.causal_discovery import (
    AlgebraicConstraintReport,
    CausalDiscoveryReport,
    LatentDiscoveryBundle,
)
from polisyos.ir.analytics.causal_graph import (
    CausalEdge,
    CausalGraphModel,
    GraphProjectionDisposition,
    _allows_legacy_graph_projection_adaptation,
    _canonical_model_field_snapshot,
    graph_for_analysis,
    legacy_graph_projection_disposition,
)
from polisyos.ir.registry.refs import CausalDiscoveryReportRef
from polisyos.scientist.methods.discovery.artifact_refs import profile_bound_written_ref
from polisyos.scientist.methods.discovery.latent_producers import produce_latent_discovery_bundle

GRAPH_HYPOTHESIS_SCHEMA_NAME = "polisyos.scientist.methods.discovery.GraphHypothesis"
GRAPH_HYPOTHESIS_SCHEMA_VERSION: Literal["1.1"] = "1.1"


class DiscoveryAlgorithmFamily(str, Enum):
    """High-level causal-discovery families used by the portfolio runner."""

    CONSTRAINT_BASED = "constraint_based"
    SCORE_BASED = "score_based"
    FUNCTIONAL = "functional"
    TIME_SERIES = "time_series"


class DiscoveryMethod(str, Enum):
    """Concrete discovery methods supported by Phase C portfolio."""

    PC = "pc"
    FCI = "fci"
    GES = "ges"
    DAGMA = "dagma"
    ANM = "anm"
    PAIRWISE_HEURISTIC = "pairwise_heuristic"
    PCMCI_PLUS = "pcmci+"


class ComputeFootprint(BaseModel):
    """Minimal execution footprint for one graph hypothesis."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    runtime_seconds: float = Field(default=0.0, ge=0.0)
    timeout_seconds: float | None = Field(default=None, ge=0.0)
    n_samples: int | None = Field(default=None, ge=0)
    n_variables: int | None = Field(default=None, ge=0)
    n_bootstrap: int = Field(default=0, ge=0)
    random_seed: int | None = None
    backend: str | None = None
    method_params: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class GraphHypothesis(BaseModel):
    """Layer-C candidate schema reused across portfolio, stability, and judging."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.1"] = GRAPH_HYPOTHESIS_SCHEMA_VERSION
    hypothesis_id: str = Field(min_length=1)
    algorithm_family: DiscoveryAlgorithmFamily
    method: DiscoveryMethod
    graph: CausalGraphModel
    resolved_graph: CausalGraphModel | None = None
    projection_disposition: GraphProjectionDisposition
    edge_confidence: dict[str, float] = Field(default_factory=dict)
    assumptions: list[str] = Field(default_factory=list)
    compute_footprint: ComputeFootprint = Field(default_factory=ComputeFootprint)
    failure_reasons: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    algebraic_constraints: AlgebraicConstraintReport | None = None
    latent_discovery: LatentDiscoveryBundle | None = None
    source_discovery_report_ref: CausalDiscoveryReportRef | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _adapt_historical_graph_projection(cls, value: Any) -> Any:
        if not isinstance(value, dict) or "projection_disposition" in value:
            return value
        if (
            "graph" not in value
            or not _allows_legacy_graph_projection_adaptation(value)
        ):
            return value
        data = dict(value)
        source_graph = CausalGraphModel.model_validate(data["graph"])
        resolved_value = data.get("resolved_graph")
        resolved_graph = (
            CausalGraphModel.model_validate(resolved_value)
            if resolved_value is not None
            else None
        )
        data["projection_disposition"] = legacy_graph_projection_disposition(
            source_graph,
            resolved_graph,
        )
        if data.get("schema_version") in (None, "1.0"):
            data["schema_version"] = GRAPH_HYPOTHESIS_SCHEMA_VERSION
        return data

    @model_validator(mode="after")
    def _validate_edge_confidence(self) -> GraphHypothesis:
        if self.projection_disposition is None:
            raise ValueError("graph hypotheses require a typed graph disposition")
        graph_for_analysis(self.graph, self.resolved_graph, self.projection_disposition)
        for key, value in self.edge_confidence.items():
            if not key:
                raise ValueError("edge_confidence keys must be non-empty")
            if not (0.0 <= float(value) <= 1.0):
                raise ValueError(f"edge_confidence[{key!r}] must be in [0,1], got {value}")
        return self

    def graph_for_analysis(self) -> CausalGraphModel | None:
        """Return only a content-bound DAG accepted by this hypothesis."""
        return graph_for_analysis(
            self.graph, self.resolved_graph, self.projection_disposition
        )


def edge_key_for_edge(edge: CausalEdge) -> str:
    """Return the normalized edge key used by scientist discovery."""
    return _cached_edge_key(edge.src, edge.dst, _normalized_lag(edge.lag))


def orientation_key_for_edge(edge: CausalEdge) -> str:
    """Return a mark-aware edge descriptor for orientation-frequency accounting."""
    return _cached_orientation_key(
        edge.src,
        edge.dst,
        getattr(edge.mark_src, "value", str(edge.mark_src)),
        getattr(edge.mark_dst, "value", str(edge.mark_dst)),
        _normalized_lag(edge.lag),
    )


def skeleton_key_for_edge(edge: CausalEdge) -> str:
    """Return the skeleton key, ignoring orientation but preserving lag."""
    return _cached_skeleton_key(edge.src, edge.dst, _normalized_lag(edge.lag))


def _normalized_lag(lag: int | None) -> int:
    return 0 if lag in (None, 0) else int(lag)


@lru_cache(maxsize=16384)
def _cached_edge_key(src: str, dst: str, lag: int) -> str:
    key = f"{src}->{dst}"
    if lag:
        return f"{key}@lag={lag}"
    return key


@lru_cache(maxsize=16384)
def _cached_orientation_key(
    src: str,
    dst: str,
    mark_src: str,
    mark_dst: str,
    lag: int,
) -> str:
    base = f"{src}|{mark_src}>{mark_dst}|{dst}"
    if lag:
        return f"{base}@lag={lag}"
    return base


@lru_cache(maxsize=16384)
def _cached_skeleton_key(src: str, dst: str, lag: int) -> str:
    left, right = sorted((src, dst))
    base = f"{left}--{right}"
    if lag:
        return f"{base}@lag={lag}"
    return base


def infer_algorithm_family(method: DiscoveryMethod | str) -> DiscoveryAlgorithmFamily:
    """Map a concrete method to its portfolio family."""

    normalized = DiscoveryMethod(method)
    if normalized in {DiscoveryMethod.PC, DiscoveryMethod.FCI}:
        return DiscoveryAlgorithmFamily.CONSTRAINT_BASED
    if normalized in {DiscoveryMethod.GES, DiscoveryMethod.DAGMA}:
        return DiscoveryAlgorithmFamily.SCORE_BASED
    if normalized in {DiscoveryMethod.ANM, DiscoveryMethod.PAIRWISE_HEURISTIC}:
        return DiscoveryAlgorithmFamily.FUNCTIONAL
    return DiscoveryAlgorithmFamily.TIME_SERIES


def default_method_assumptions(method: DiscoveryMethod | str) -> list[str]:
    """Return conservative, method-specific assumptions for surfaced provenance."""

    normalized = DiscoveryMethod(method)
    assumptions: dict[DiscoveryMethod, list[str]] = {
        DiscoveryMethod.PC: [
            "causal_sufficiency unless contradicted by later discovery evidence",
            "faithfulness / Markov assumptions for conditional-independence testing",
        ],
        DiscoveryMethod.FCI: [
            "faithfulness / Markov assumptions for conditional-independence testing",
            "latent confounders may exist; output preserves partial ancestral uncertainty",
        ],
        DiscoveryMethod.GES: [
            "score-equivalent DAG search with no latent-confounder handling in the base search",
            "faithfulness / score consistency assumptions",
        ],
        DiscoveryMethod.DAGMA: [
            "continuous optimization over DAG structure with acyclicity constraint",
            "no latent-confounder handling in the base score-based search",
        ],
        DiscoveryMethod.ANM: [
            "pairwise additive-noise orientation is used as a heuristic structural signal",
            "orientation quality depends on non-Gaussianity / nonlinear asymmetry being informative",
        ],
        DiscoveryMethod.PAIRWISE_HEURISTIC: [
            "pairwise orientation is heuristic and intended as a low-cost functional baseline",
            "edge orientation quality depends on directional asymmetry surviving the chosen residual proxy",
        ],
        DiscoveryMethod.PCMCI_PLUS: [
            "lag-limited time-series discovery under the configured maximum lag",
            "stationarity / stable temporal mechanism assumptions of the chosen conditional-independence test",
        ],
    }
    return list(assumptions[normalized])


def bootstrap_confidence_for_edge(
    report: CausalDiscoveryReport,
    edge: CausalEdge,
) -> float | None:
    """Resolve bootstrap stability for an edge across foundry report key variants."""

    stability = dict(report.bootstrap_stability)
    for key in (
        edge_key_for_edge(edge),
        orientation_key_for_edge(edge),
        f"{edge.src}->{edge.dst}@lag={edge.lag}",
    ):
        if key in stability:
            return float(stability[key])
    return None


def edge_confidence_for_edge(
    report: CausalDiscoveryReport,
    edge: CausalEdge,
    *,
    shared_bootstrap_stability: dict[str, float] | None = None,
) -> float:
    """Resolve edge confidence using the agreed fallback order."""

    normalized_key = edge_key_for_edge(edge)
    if shared_bootstrap_stability and normalized_key in shared_bootstrap_stability:
        return float(shared_bootstrap_stability[normalized_key])
    if edge.combined_confidence is not None:
        return float(edge.combined_confidence)
    if edge.data_confidence is not None:
        return float(edge.data_confidence)
    return 0.5


def graph_hypothesis_from_report(
    report: CausalDiscoveryReport,
    *,
    hypothesis_id: str,
    compute_footprint: ComputeFootprint | None = None,
    shared_bootstrap_stability: dict[str, float] | None = None,
    metadata: dict[str, Any] | None = None,
) -> GraphHypothesis:
    """Normalize a foundry discovery report into the scientist graph contract."""

    method = DiscoveryMethod(report.method)
    warnings = list(report.warnings)
    failure_markers = (
        "timeout",
        "failed",
        "modulenotfounderror",
        "unsupported",
        "executor_failed",
        "algorithm_failed",
    )
    failure_reasons = [
        warning
        for warning in warnings
        if any(marker in warning.lower() for marker in failure_markers)
    ]
    edge_confidence = {
        edge_key_for_edge(edge): edge_confidence_for_edge(
            report,
            edge,
            shared_bootstrap_stability=shared_bootstrap_stability,
        )
        for edge in report.graph.edges
    }
    return GraphHypothesis(
        hypothesis_id=hypothesis_id,
        algorithm_family=infer_algorithm_family(method),
        method=method,
        graph=report.graph,
        resolved_graph=report.resolved_graph,
        projection_disposition=report.projection_disposition,
        edge_confidence=edge_confidence,
        assumptions=default_method_assumptions(method),
        compute_footprint=compute_footprint or ComputeFootprint(),
        failure_reasons=failure_reasons,
        warnings=warnings,
        algebraic_constraints=report.algebraic_constraints,
        latent_discovery=produce_latent_discovery_bundle(
            report,
            graph=report.graph_for_analysis(),
        ),
        metadata={
            "discovery_report_metadata": dict(report.metadata),
            **(metadata or {}),
        },
    )


def _snapshot_untyped_graph_hypothesis_value(value: Any) -> Any:
    """Copy values under Any without trusting model serializers or iterators."""
    if isinstance(value, BaseModel):
        model_type = type(value)
        fields = _canonical_model_field_snapshot(value, model_type)
        return {
            name: _snapshot_untyped_graph_hypothesis_value(fields[name])
            for name in model_type.model_fields
        }
    if type(value) is dict:
        return {
            key: _snapshot_untyped_graph_hypothesis_value(item)
            for key, item in dict.items(value)
        }
    if type(value) is list:
        return [
            _snapshot_untyped_graph_hypothesis_value(item)
            for item in list.__iter__(value)
        ]
    if type(value) is tuple:
        return tuple(_snapshot_untyped_graph_hypothesis_value(item) for item in value)
    if type(value) is set:
        return {_snapshot_untyped_graph_hypothesis_value(item) for item in value}
    if type(value) is frozenset:
        return frozenset(_snapshot_untyped_graph_hypothesis_value(item) for item in value)
    if isinstance(value, (list, dict, tuple, set, frozenset)):
        raise ValueError("graph hypothesis contains a noncanonical nested container")
    return value


def _annotation_matches_value(value: Any, annotation: Any) -> bool:
    """Select a union branch using the stored runtime value, not serialization."""
    origin = get_origin(annotation)
    if origin is Annotated:
        return _annotation_matches_value(value, get_args(annotation)[0])
    if origin in (Union, UnionType):
        return any(_annotation_matches_value(value, item) for item in get_args(annotation))
    if annotation is Any:
        return True
    if annotation is type(None):
        return value is None
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return isinstance(value, annotation)
    if origin is list:
        return isinstance(value, list)
    if origin is dict:
        return isinstance(value, dict)
    if origin is tuple:
        return isinstance(value, tuple)
    if origin is set:
        return isinstance(value, set)
    if origin is frozenset:
        return isinstance(value, frozenset)
    if isinstance(annotation, type):
        return isinstance(value, annotation)
    return True


def _snapshot_graph_hypothesis_value(value: Any, annotation: Any) -> Any:
    """Rebuild a declared value recursively from its actual stored fields."""
    origin = get_origin(annotation)
    if origin is Annotated:
        return _snapshot_graph_hypothesis_value(value, get_args(annotation)[0])
    if origin in (Union, UnionType):
        candidates = [item for item in get_args(annotation) if item is not type(None)]
        if value is None and len(candidates) != len(get_args(annotation)):
            return None
        for candidate in candidates:
            if _annotation_matches_value(value, candidate):
                return _snapshot_graph_hypothesis_value(value, candidate)
        return value
    if annotation is Any or annotation in (list, dict, tuple, set, frozenset):
        return _snapshot_untyped_graph_hypothesis_value(value)
    if (
        isinstance(annotation, type)
        and issubclass(annotation, BaseModel)
        and getattr(annotation, "__pydantic_root_model__", False)
    ):
        root_field = annotation.model_fields.get("root")
        if root_field is None:
            raise ValueError(f"root model {annotation.__name__} has no declared root field")
        if isinstance(value, BaseModel):
            if type(value) is not annotation:
                raise ValueError(
                    f"graph hypothesis root model requires exact {annotation.__name__} runtime type"
                )
            root_fields = _canonical_model_field_snapshot(value, annotation)
            if set(root_fields) != {"root"}:
                raise ValueError(f"root model {annotation.__name__} has invalid stored fields")
            root_value = _snapshot_graph_hypothesis_value(
                root_fields["root"], root_field.annotation
            )
        else:
            root_value = _snapshot_graph_hypothesis_value(value, root_field.annotation)
        return annotation.model_validate(root_value, strict=True)
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        if isinstance(value, BaseModel):
            if not isinstance(value, annotation):
                raise ValueError(
                    f"graph hypothesis nested model does not match {annotation.__name__}"
                )
            if annotation in {CausalGraphModel, CausalEdge, GraphProjectionDisposition} and type(value) is not annotation:
                raise ValueError(
                    f"graph hypothesis requires exact {annotation.__name__} runtime type"
                )
            actual_fields = _canonical_model_field_snapshot(value, type(value))
            if type(value) is not annotation:
                extra_fields = set(actual_fields) - set(annotation.model_fields)
                if extra_fields:
                    raise ValueError(
                        f"graph hypothesis nested {annotation.__name__} has undeclared fields"
                    )
            fields = {
                name: _snapshot_graph_hypothesis_value(
                    actual_fields[name], field.annotation
                )
                for name, field in annotation.model_fields.items()
                if name in actual_fields
            }
            missing_fields = set(annotation.model_fields) - set(fields)
            if missing_fields:
                raise ValueError(
                    f"graph hypothesis nested {annotation.__name__} is missing declared fields"
                )
            return annotation.model_validate(fields, strict=True)
        if type(value) is dict:
            fields = {}
            for name, item in dict.items(value):
                field = annotation.model_fields.get(name)
                fields[name] = (
                    _snapshot_graph_hypothesis_value(item, field.annotation)
                    if field is not None
                    else _snapshot_untyped_graph_hypothesis_value(item)
                )
            return annotation.model_validate(fields, strict=True)
        return value
    if origin is list:
        if type(value) is not list:
            return value
        item_annotation = get_args(annotation)[0]
        return [
            _snapshot_graph_hypothesis_value(item, item_annotation)
            for item in list.__iter__(value)
        ]
    if origin is dict:
        if type(value) is not dict:
            return value
        key_annotation, item_annotation = get_args(annotation)
        return {
            _snapshot_graph_hypothesis_value(key, key_annotation):
            _snapshot_graph_hypothesis_value(item, item_annotation)
            for key, item in dict.items(value)
        }
    if origin is tuple:
        if type(value) is not tuple:
            return value
        item_annotations = get_args(annotation)
        if len(item_annotations) == 2 and item_annotations[1] is Ellipsis:
            return tuple(
                _snapshot_graph_hypothesis_value(item, item_annotations[0])
                for item in value
            )
        if len(value) != len(item_annotations):
            return value
        return tuple(
            _snapshot_graph_hypothesis_value(item, item_annotation)
            for item, item_annotation in zip(value, item_annotations, strict=True)
        )
    if origin in (set, frozenset):
        if type(value) is not origin:
            return value
        item_annotation = get_args(annotation)[0]
        items = (
            _snapshot_graph_hypothesis_value(item, item_annotation)
            for item in value
        )
        return origin(items)
    return value


def _revalidate_current_graph_hypothesis(hypothesis: GraphHypothesis) -> GraphHypothesis:
    """Rebuild every declared field before a current-version artifact write."""
    if type(hypothesis) is not GraphHypothesis:
        raise ValueError("graph hypothesis persistence requires the canonical model type")
    try:
        fields = _canonical_model_field_snapshot(hypothesis, GraphHypothesis)
        snapshot = {
            name: _snapshot_graph_hypothesis_value(
                fields[name], field.annotation
            )
            for name, field in GraphHypothesis.model_fields.items()
        }
        return GraphHypothesis.model_validate(snapshot, strict=True)
    except RecursionError as exc:
        raise ValueError("graph hypothesis contains cyclic nested values") from exc


def _validate_graph_hypothesis_artifact_binding(
    ref: GraphHypothesisRef,
    manifest: Any,
    payload: Any,
) -> str:
    """Bind a stored graph hypothesis payload to its manifest schema version."""
    if (
        manifest.artifact_id != ref.artifact_id
        or manifest.kind != ref.kind
        or manifest.kind != "scientist.graph_hypothesis"
        or manifest.media_type != ref.media_type
        or manifest.media_type != "application/json"
    ):
        raise ValueError("graph hypothesis manifest identity mismatch")
    schema = manifest.artifact_schema
    if schema is None or schema.name != GRAPH_HYPOTHESIS_SCHEMA_NAME:
        raise ValueError("graph hypothesis manifest schema name is missing or invalid")
    if type(payload) is not dict:
        raise ValueError("graph hypothesis payload must be a JSON object")

    payload_version = payload.get("schema_version")
    if schema.version == GRAPH_HYPOTHESIS_SCHEMA_VERSION:
        if (
            payload_version != GRAPH_HYPOTHESIS_SCHEMA_VERSION
            or "projection_disposition" not in payload
        ):
            raise ValueError("current graph hypothesis manifest/payload schema mismatch")
        return GRAPH_HYPOTHESIS_SCHEMA_VERSION
    if schema.version == "1.0":
        if (
            payload_version != "1.0"
            or "projection_disposition" in payload
            or not _allows_legacy_graph_projection_adaptation(payload)
        ):
            raise ValueError("graph hypothesis is not an exact historical schema 1.0 shape")
        return "1.0"
    raise ValueError("unsupported graph hypothesis manifest schema version")


def persist_graph_hypothesis(
    store: FileSystemCAS,
    hypothesis: GraphHypothesis,
    *,
    inputs: list[InputRef] | None = None,
) -> GraphHypothesisRef:
    """Persist only a revalidated current graph hypothesis and matching manifest."""
    current = _revalidate_current_graph_hypothesis(hypothesis)
    if current.schema_version != GRAPH_HYPOTHESIS_SCHEMA_VERSION:
        raise ValueError("graph hypothesis producer requires the current schema version")
    ref = store.put_json(
        current,
        PutOptions(
            kind="scientist.graph_hypothesis",
            media_type="application/json",
            schema=SchemaInfo(
                name=GRAPH_HYPOTHESIS_SCHEMA_NAME,
                version=GRAPH_HYPOTHESIS_SCHEMA_VERSION,
            ),
            inputs=list(inputs or []),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    typed_ref = GraphHypothesisRef.model_validate(ref.model_dump(mode="json"))
    return profile_bound_written_ref(store, typed_ref)


def load_graph_hypothesis(
    store: FileSystemCAS,
    ref: GraphHypothesisRef,
) -> GraphHypothesis:
    """Load a version-bound current hypothesis or an exact historical 1.0 candidate."""
    manifest = store.get_manifest(ref)
    from polisyos.core.artifacts import load_core_json_artifact
    payload = load_core_json_artifact(store, ref)
    stored_version = _validate_graph_hypothesis_artifact_binding(ref, manifest, payload)
    hypothesis = GraphHypothesis.model_validate(payload)
    if stored_version == GRAPH_HYPOTHESIS_SCHEMA_VERSION:
        if hypothesis.schema_version != GRAPH_HYPOTHESIS_SCHEMA_VERSION:
            raise ValueError("current graph hypothesis payload did not retain its schema version")
    elif hypothesis.schema_version != GRAPH_HYPOTHESIS_SCHEMA_VERSION:
        raise ValueError("historical graph hypothesis did not adapt to the current typed model")
    return hypothesis


__all__ = [
    "GRAPH_HYPOTHESIS_SCHEMA_NAME",
    "GRAPH_HYPOTHESIS_SCHEMA_VERSION",
    "ComputeFootprint",
    "DiscoveryAlgorithmFamily",
    "DiscoveryMethod",
    "GraphHypothesis",
    "bootstrap_confidence_for_edge",
    "default_method_assumptions",
    "edge_confidence_for_edge",
    "edge_key_for_edge",
    "graph_hypothesis_from_report",
    "infer_algorithm_family",
    "load_graph_hypothesis",
    "orientation_key_for_edge",
    "persist_graph_hypothesis",
    "skeleton_key_for_edge",
]
