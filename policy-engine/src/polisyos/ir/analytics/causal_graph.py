"""Public analytics causal graph module API."""

from __future__ import annotations

import hashlib
import importlib
import json
from collections.abc import Mapping
from copy import deepcopy
from enum import Enum
from functools import cached_property
from typing import Any, ClassVar, NoReturn, Protocol, Self, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.ir._internal.runtime_protocols import protocol_declared_callables_are_callable
from polisyos.ir.artifacts import ArtifactStore, InputRef, get_json_artifact, put_json_artifact
from polisyos.ir.model_layer.canon import CanonSpec
from polisyos.ir.registry.refs import CausalGraphModelRef


@runtime_checkable
class _RustworkxDirectedGraph(Protocol):
    """Small runtime-checked surface used by the optional rustworkx export."""

    def add_node(self, node: str, /) -> int: ...

    def add_edge(self, source: int, target: int, data: object, /) -> object: ...


class GraphType(str, Enum):
    """Graph type public type."""

    DAG = "dag"
    CPDAG = "cpdag"
    PAG = "pag"
    MGRAPH = "mgraph"  # M-graph: includes R_X indicator and X_star proxy nodes
    ADMG = "admg"  # Acyclic Directed Mixed Graph (bidirected edges only, no R-nodes)


class PAGIdentificationPolicy(str, Enum):
    """PAG identification policy data model."""

    CONSERVATIVE = "conservative"
    OPTIMISTIC = "optimistic"
    PROBABILISTIC = "probabilistic"


class EdgeMark(str, Enum):
    """Edge mark public type."""

    TAIL = "tail"
    ARROW = "arrow"
    CIRCLE = "circle"


class UnsupportedGraphProjectionError(ValueError):
    """Typed refusal when a source graph cannot support one admitted DAG projection."""

    def __init__(self, reason_code: str) -> None:
        self.reason_code = reason_code
        super().__init__(
            "cannot project unresolved partial orientation or unsupported source "
            f"profile: {reason_code}; retain the original graph for a partial-graph "
            "consumer"
        )


class GraphProjectionStatus(str, Enum):
    """Describe whether a source graph has an admitted DAG projection."""

    IDENTITY = "identity"
    PROJECTED = "projected"
    UNAVAILABLE = "unavailable"
    UNSUPPORTED = "unsupported"


class GraphProjectionDisposition(BaseModel):
    """Content-bound status for a graph identity or an explicit DAG projection."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: GraphProjectionStatus
    source_graph_type: GraphType
    source_graph_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    resolved_graph_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    reason_code: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def _validate_disposition(self) -> GraphProjectionDisposition:
        if self.status is GraphProjectionStatus.IDENTITY:
            if self.source_graph_type is not GraphType.DAG:
                raise ValueError("identity disposition requires a declared DAG source")
            if self.resolved_graph_sha256 not in (None, self.source_graph_sha256):
                raise ValueError("identity disposition cannot change the source graph content")
            if self.reason_code is not None:
                raise ValueError("identity disposition cannot carry a refusal reason")
        elif self.status is GraphProjectionStatus.PROJECTED:
            if self.source_graph_type not in {GraphType.PAG, GraphType.CPDAG, GraphType.ADMG}:
                raise ValueError("projected disposition requires an admitted source graph profile")
            if self.resolved_graph_sha256 is None or self.reason_code is not None:
                raise ValueError("projected disposition requires a resolved graph and no refusal")
        elif self.status is GraphProjectionStatus.UNAVAILABLE:
            if self.resolved_graph_sha256 is not None or self.reason_code is None:
                raise ValueError("unavailable disposition requires a reason and no DAG")
        elif self.reason_code is None:
            raise ValueError("unsupported disposition requires a reason")
        return self


def _declared_cached_property_names(model_type: type[BaseModel]) -> frozenset[str]:
    """Return cache names declared by the model class hierarchy."""
    return frozenset(
        name
        for base in reversed(model_type.__mro__)
        for name, descriptor in vars(base).items()
        if isinstance(descriptor, cached_property)
    )


def _snapshot_canonical_value(value: Any) -> Any:
    """Copy canonical container values without trusting caller-defined iterators."""
    if type(value) in (list, _FrozenList):
        return [_snapshot_canonical_value(item) for item in list.__iter__(value)]
    if type(value) in (dict, _FrozenDict):
        return {key: _snapshot_canonical_value(item) for key, item in dict.items(value)}
    if type(value) is tuple:
        return tuple(_snapshot_canonical_value(item) for item in value)
    if type(value) is set:
        return {_snapshot_canonical_value(item) for item in value}
    if type(value) is frozenset:
        return frozenset(_snapshot_canonical_value(item) for item in value)
    if isinstance(value, (list, dict, tuple, set, frozenset)):
        raise ValueError("canonical model contains a noncanonical container")
    return value


def _canonical_model_field_snapshot(
    instance: object,
    model_type: type[BaseModel],
) -> dict[str, Any]:
    """Read every declared model field and reject undeclared runtime storage."""
    if type(instance) is not model_type:
        raise ValueError(f"expected canonical {model_type.__name__} runtime type")
    try:
        stored_fields = object.__getattribute__(instance, "__dict__")
        extra_fields = object.__getattribute__(instance, "__pydantic_extra__")
    except AttributeError as exc:
        raise ValueError("canonical model storage is unavailable") from exc
    try:
        private_fields = object.__getattribute__(instance, "__pydantic_private__")
    except AttributeError as exc:
        if getattr(model_type, "__private_attributes__", {}):
            raise ValueError("canonical model private storage is unavailable") from exc
        # Pydantic's model_construct omits this internal slot when the schema
        # declares no private attributes. It carries no model data; the complete
        # declared fields below are still rebuilt and strictly revalidated.
        private_fields = None
    if type(stored_fields) is not dict:
        raise ValueError("canonical model field storage must be a plain dictionary")
    if extra_fields is not None:
        raise ValueError("canonical model cannot carry Pydantic extra fields")
    if private_fields is not None and (type(private_fields) is not dict or private_fields):
        raise ValueError("canonical model cannot carry undeclared private fields")

    declared_fields = set(model_type.model_fields)
    cached_properties = _declared_cached_property_names(model_type)
    stored_names = set(stored_fields)
    unknown_names = stored_names - declared_fields - cached_properties
    missing_names = declared_fields - stored_names
    if unknown_names:
        raise ValueError(
            "canonical model has undeclared stored fields: "
            + ", ".join(sorted(str(name) for name in unknown_names))
        )
    if missing_names:
        raise ValueError(
            "canonical model is missing stored fields: " + ", ".join(sorted(missing_names))
        )
    return {
        name: _snapshot_canonical_value(stored_fields[name]) for name in model_type.model_fields
    }


def _canonical_model(instance: object, model_type: type[BaseModel]) -> BaseModel:
    """Revalidate a model from its complete declared field set."""
    fields = _canonical_model_field_snapshot(instance, model_type)
    try:
        return model_type.model_validate(fields, strict=True)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"canonical {model_type.__name__} validation failed") from exc


def _canonical_causal_graph(graph: object) -> CausalGraphModel:
    """Rebuild a graph and every nested edge from the actual canonical fields."""
    fields = _canonical_model_field_snapshot(graph, CausalGraphModel)
    edges = fields.get("edges")
    if type(edges) is not list:
        raise ValueError("canonical graph edges must be a list")
    fields["edges"] = [_canonical_model(edge, CausalEdge) for edge in edges]
    try:
        return CausalGraphModel.model_validate(fields, strict=True)
    except (TypeError, ValueError) as exc:
        raise ValueError("canonical causal graph validation failed") from exc


def _canonical_graph_projection_disposition(
    disposition: object,
) -> GraphProjectionDisposition:
    """Revalidate the complete stored disposition before using its status."""
    canonical = _canonical_model(disposition, GraphProjectionDisposition)
    if type(canonical) is not GraphProjectionDisposition:
        raise ValueError("canonical graph disposition validation failed")
    return canonical


def _allows_legacy_graph_projection_adaptation(value: Mapping[str, Any]) -> bool:
    """Allow the adapter only for unversioned or exact schema-1.0 receipts."""
    return "schema_version" not in value or value["schema_version"] == "1.0"


def graph_content_sha256(graph: CausalGraphModel) -> str:
    """Hash complete, strictly revalidated model fields, excluding declared caches."""
    canonical = _canonical_causal_graph(graph)
    payload = canonical.model_dump(mode="json")
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def graph_projection_disposition(
    source_graph: CausalGraphModel,
    resolved_graph: CausalGraphModel | None,
    *,
    status: GraphProjectionStatus,
    reason_code: str | None = None,
) -> GraphProjectionDisposition:
    """Bind a projection status to the exact source and optional resolved graph."""
    source_graph = _canonical_causal_graph(source_graph)
    if resolved_graph is not None:
        resolved_graph = _canonical_causal_graph(resolved_graph)
    return GraphProjectionDisposition(
        status=status,
        source_graph_type=source_graph.graph_type,
        source_graph_sha256=graph_content_sha256(source_graph),
        resolved_graph_sha256=(
            graph_content_sha256(resolved_graph) if resolved_graph is not None else None
        ),
        reason_code=reason_code,
    )


def legacy_graph_projection_disposition(
    source_graph: CausalGraphModel,
    resolved_graph: CausalGraphModel | None,
) -> GraphProjectionDisposition:
    """Upgrade a historical graph receipt only when its projection replays exactly.

    A historical source graph without a recorded result remains an unsupported
    input for DAG-only consumers. A stored DAG is admitted only when the current
    canonical projector recreates the complete payload byte-for-byte by digest.
    The old candidate remains preserved on an unsupported receipt but cannot be
    consumed as an analysis graph.
    """
    source_graph = _canonical_causal_graph(source_graph)
    if resolved_graph is not None:
        resolved_graph = _canonical_causal_graph(resolved_graph)
    source_hash = graph_content_sha256(source_graph)
    resolved_hash = graph_content_sha256(resolved_graph) if resolved_graph is not None else None
    if source_graph.graph_type is GraphType.DAG:
        if resolved_hash in (None, source_hash):
            return GraphProjectionDisposition(
                status=GraphProjectionStatus.IDENTITY,
                source_graph_type=source_graph.graph_type,
                source_graph_sha256=source_hash,
                resolved_graph_sha256=resolved_hash,
            )
        return GraphProjectionDisposition(
            status=GraphProjectionStatus.UNSUPPORTED,
            source_graph_type=source_graph.graph_type,
            source_graph_sha256=source_hash,
            resolved_graph_sha256=resolved_hash,
            reason_code="historical_identity_projection_mismatch",
        )
    if resolved_graph is None:
        return GraphProjectionDisposition(
            status=GraphProjectionStatus.UNSUPPORTED,
            source_graph_type=source_graph.graph_type,
            source_graph_sha256=source_hash,
            reason_code="historical_projection_disposition_not_recorded",
        )
    try:
        expected, _ = project_graph_to_dag(source_graph)
    except ValueError:
        expected = None
    if expected is not None and graph_content_sha256(expected) == resolved_hash:
        return GraphProjectionDisposition(
            status=GraphProjectionStatus.PROJECTED,
            source_graph_type=source_graph.graph_type,
            source_graph_sha256=source_hash,
            resolved_graph_sha256=resolved_hash,
        )
    return GraphProjectionDisposition(
        status=GraphProjectionStatus.UNSUPPORTED,
        source_graph_type=source_graph.graph_type,
        source_graph_sha256=source_hash,
        resolved_graph_sha256=resolved_hash,
        reason_code="historical_projection_receipt_not_recomputed",
    )


def graph_for_analysis(
    source_graph: CausalGraphModel,
    resolved_graph: CausalGraphModel | None,
    disposition: GraphProjectionDisposition | None,
) -> CausalGraphModel | None:
    """Return only a fully revalidated source identity or canonical DAG projection."""
    source_graph = _canonical_causal_graph(source_graph)
    if resolved_graph is not None:
        resolved_graph = _canonical_causal_graph(resolved_graph)
    if disposition is None:
        if resolved_graph is not None:
            raise ValueError("resolved graph requires a typed projection disposition")
        return source_graph if source_graph.graph_type is GraphType.DAG else None

    disposition = _canonical_graph_projection_disposition(disposition)
    if (
        disposition.source_graph_type is not source_graph.graph_type
        or disposition.source_graph_sha256 != graph_content_sha256(source_graph)
    ):
        raise ValueError("graph projection disposition does not bind the current source graph")
    if disposition.status is GraphProjectionStatus.IDENTITY:
        if (
            resolved_graph is not None
            and graph_content_sha256(resolved_graph) != disposition.source_graph_sha256
        ):
            raise ValueError("identity projection differs from its source graph")
        return source_graph
    if disposition.status is GraphProjectionStatus.PROJECTED:
        if (
            resolved_graph is None
            or graph_content_sha256(resolved_graph) != disposition.resolved_graph_sha256
        ):
            raise ValueError("resolved graph does not match its projection disposition")
        expected, _ = project_graph_to_dag(source_graph)
        if graph_content_sha256(expected) != graph_content_sha256(resolved_graph):
            raise ValueError("resolved graph is not the canonical projection of its source")
        return resolved_graph
    if disposition.status is GraphProjectionStatus.UNAVAILABLE:
        if resolved_graph is not None:
            raise ValueError("unavailable source cannot carry a resolved DAG")
        return None
    if (
        resolved_graph is not None
        and graph_content_sha256(resolved_graph) != disposition.resolved_graph_sha256
    ):
        raise ValueError("unsupported candidate graph does not match its refusal disposition")
    if resolved_graph is None and disposition.resolved_graph_sha256 is not None:
        raise ValueError("unsupported refusal references a missing candidate graph")
    return None


class EdgeSource(str, Enum):
    """Edge source public type."""

    DATA = "data"
    LITERATURE = "literature"
    LLM_PRIOR = "llm_prior"
    EXPERT = "expert"
    SIMULATION = "simulation"


class _FrozenList(list[Any]):
    """List-compatible container that rejects in-place mutation."""

    __slots__ = ()

    def _immutable(self, *_args: Any, **_kwargs: Any) -> NoReturn:
        raise TypeError("published graph containers are immutable")

    __setitem__ = _immutable
    __delitem__ = _immutable
    __iadd__ = _immutable
    __imul__ = _immutable
    append = _immutable
    clear = _immutable
    extend = _immutable
    insert = _immutable
    pop = _immutable
    remove = _immutable
    reverse = _immutable
    sort = _immutable

    def __copy__(self) -> _FrozenList:
        return _FrozenList(self)

    def __deepcopy__(self, memo: dict[int, Any]) -> _FrozenList:
        existing = memo.get(id(self))
        if isinstance(existing, _FrozenList):
            return existing
        if existing is not None:
            raise TypeError("deepcopy memo contains an incompatible frozen-list copy")
        copied = _FrozenList()
        memo[id(self)] = copied
        list.extend(copied, (deepcopy(item, memo) for item in self))
        return copied


class _FrozenDict(dict[Any, Any]):
    """Dict-compatible container that rejects in-place mutation."""

    __slots__ = ()

    def _immutable(self, *_args: Any, **_kwargs: Any) -> NoReturn:
        raise TypeError("published graph containers are immutable")

    __delitem__ = _immutable
    __ior__ = _immutable
    __setitem__ = _immutable
    clear = _immutable
    pop = _immutable
    popitem = _immutable
    setdefault = _immutable
    update = _immutable

    def __copy__(self) -> _FrozenDict:
        return _FrozenDict(self)

    def __deepcopy__(self, memo: dict[int, Any]) -> _FrozenDict:
        existing = memo.get(id(self))
        if isinstance(existing, _FrozenDict):
            return existing
        if existing is not None:
            raise TypeError("deepcopy memo contains an incompatible frozen-dict copy")
        copied = _FrozenDict()
        memo[id(self)] = copied
        dict.update(
            copied,
            ((deepcopy(key, memo), deepcopy(value, memo)) for key, value in self.items()),
        )
        return copied


def _freeze_value(value: Any) -> Any:
    """Recursively freeze standard mutable containers while preserving wire shapes."""
    if isinstance(value, Mapping):
        return _FrozenDict((key, _freeze_value(item)) for key, item in value.items())
    if isinstance(value, list):
        return _FrozenList(_freeze_value(item) for item in value)
    if isinstance(value, tuple):
        return tuple(_freeze_value(item) for item in value)
    if isinstance(value, set):
        return frozenset(_freeze_value(item) for item in value)
    return value


class CausalEdge(BaseModel):
    """Causal edge public type."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    SOURCE_WEIGHTS: ClassVar[dict[EdgeSource, float]] = {
        EdgeSource.LITERATURE: 0.5,
        EdgeSource.DATA: 0.4,
        EdgeSource.EXPERT: 0.1,
        EdgeSource.LLM_PRIOR: 0.05,
        EdgeSource.SIMULATION: 0.1,
    }

    src: str = Field(min_length=1)
    dst: str = Field(min_length=1)
    mark_src: EdgeMark = EdgeMark.TAIL
    mark_dst: EdgeMark = EdgeMark.ARROW
    lag: int | None = Field(default=None, ge=0)

    sources: list[EdgeSource] = Field(default_factory=list)
    data_confidence: float | None = None
    literature_confidence: float | None = None
    llm_confidence: float | None = None
    expert_confidence: float | None = None
    simulation_confidence: float | None = None
    combined_confidence: float | None = None

    unsupported_by_evidence: bool = False

    evidence_refs: list[str] = Field(default_factory=list)
    p_value: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_fields(self) -> CausalEdge:
        for name in (
            "data_confidence",
            "literature_confidence",
            "llm_confidence",
            "expert_confidence",
            "simulation_confidence",
            "combined_confidence",
            "p_value",
        ):
            value = getattr(self, name)
            if value is None:
                continue
            if not (0.0 <= value <= 1.0):
                raise ValueError(f"{name} must be in [0,1], got {value}")
        return self

    def model_post_init(self, __context: Any) -> None:
        self._freeze_collections()

    def _freeze_collections(self) -> None:
        object.__setattr__(self, "sources", _freeze_value(self.sources))
        object.__setattr__(self, "evidence_refs", _freeze_value(self.evidence_refs))
        object.__setattr__(self, "metadata", _freeze_value(self.metadata))

    def model_copy(
        self,
        *,
        update: Mapping[str, Any] | None = None,
        deep: bool = False,
    ) -> Self:
        copied = super().model_copy(update=update, deep=deep)
        copied._freeze_collections()
        return copied

    @staticmethod
    def _clamp_probability(value: float | None) -> float:
        if value is None:
            return 0.0
        if value < 0.0:
            return 0.0
        if value > 1.0:
            return 1.0
        return float(value)

    def _confidence_for_source(self, source: EdgeSource) -> float:
        if source is EdgeSource.DATA:
            return self._clamp_probability(self.data_confidence)
        if source is EdgeSource.LITERATURE:
            return self._clamp_probability(self.literature_confidence)
        if source is EdgeSource.LLM_PRIOR:
            return self._clamp_probability(self.llm_confidence)
        if source is EdgeSource.EXPERT:
            return self._clamp_probability(self.expert_confidence)
        if source is EdgeSource.SIMULATION:
            return self._clamp_probability(self.simulation_confidence)
        return 0.0

    def compute_combined_confidence(self) -> float:
        product_of_failures = 1.0
        for source in self.sources:
            conf = self._confidence_for_source(source)
            weight = self.SOURCE_WEIGHTS.get(source, 0.05)
            product_of_failures *= (1.0 - conf) ** weight
        combined = 1.0 - product_of_failures
        return self._clamp_probability(combined)


class CausalGraphModel(BaseModel):
    """DAG / CPDAG / PAG / MGRAPH / ADMG causal graph IR contract."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0"
    graph_type: GraphType
    nodes: list[str]
    edges: list[CausalEdge]
    discovery_method: str = ""
    skg_version_id: int | None = None
    pag_identification_policy: PAGIdentificationPolicy = PAGIdentificationPolicy.CONSERVATIVE
    id_confidence_under_pag: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    def dag_projection_refusal_code(self) -> str | None:
        """Return why this fully revalidated graph cannot be admitted as one DAG."""
        try:
            graph = _canonical_causal_graph(self)
        except (TypeError, ValueError):
            return "causal_graph_profile_invalid"
        return _dag_projection_refusal_code_from_canonical(graph)

    @model_validator(mode="after")
    def _validate_graph(self) -> CausalGraphModel:
        if not self.nodes:
            raise ValueError("nodes must be non-empty")
        if any(not node for node in self.nodes):
            raise ValueError("nodes must not contain empty names")
        if len(set(self.nodes)) != len(self.nodes):
            raise ValueError("nodes must be unique")

        node_set = set(self.nodes)
        for edge in self.edges:
            if edge.src not in node_set:
                raise ValueError(f"Edge src '{edge.src}' not in nodes")
            if edge.dst not in node_set:
                raise ValueError(f"Edge dst '{edge.dst}' not in nodes")
            if edge.src == edge.dst:
                if not (
                    edge.lag is not None
                    and edge.lag > 0
                    and edge.mark_src is EdgeMark.TAIL
                    and edge.mark_dst is EdgeMark.ARROW
                ):
                    raise ValueError(
                        "zero-lag self-loop is not allowed; self-loops require a "
                        "positive lagged directed edge"
                    )

        if self.graph_type is GraphType.PAG:
            self._ensure_pag_unique_adjacencies()

        if self.graph_type is GraphType.DAG:
            for edge in self.edges:
                if edge.mark_src is not EdgeMark.TAIL or edge.mark_dst is not EdgeMark.ARROW:
                    raise ValueError(
                        "DAG requires oriented edges with mark_src=tail, mark_dst=arrow"
                    )
            # Time-unrolled DAGs (e.g., PCMCI) may contain lagged reciprocal edges
            # that are acyclic in time. Cycle check is applied to contemporaneous edges.
            if _has_directed_cycle(nodes=self.nodes, edges=self.edges, include_lagged=False):
                raise ValueError("DAG must be acyclic")
        elif self.graph_type is GraphType.CPDAG:
            for edge in self.edges:
                if edge.mark_src is EdgeMark.CIRCLE or edge.mark_dst is EdgeMark.CIRCLE:
                    raise ValueError("CPDAG does not allow circle endpoints")
        elif self.graph_type is GraphType.MGRAPH:
            _validate_mgraph_structure(self.nodes, self.edges)

        if self.id_confidence_under_pag is not None:
            if not (0.0 <= self.id_confidence_under_pag <= 1.0):
                raise ValueError("id_confidence_under_pag must be in [0,1]")
            if self.pag_identification_policy is not PAGIdentificationPolicy.PROBABILISTIC:
                raise ValueError(
                    "id_confidence_under_pag is only allowed when "
                    "pag_identification_policy=probabilistic"
                )
        return self

    def _pag_duplicate_adjacencies(self) -> tuple[tuple[str, str], ...]:
        """Return unordered endpoint pairs represented by multiple PAG edge rows."""
        seen: set[tuple[str, str]] = set()
        duplicates: set[tuple[str, str]] = set()
        for edge in self.edges:
            first, second = edge.src, edge.dst
            pair = (first, second) if first <= second else (second, first)
            if pair in seen:
                duplicates.add(pair)
            seen.add(pair)
        return tuple(sorted(duplicates))

    def _ensure_pag_unique_adjacencies(self) -> None:
        """Refuse PAG edge rows that collapse to the same endpoint-keyed adjacency."""
        duplicates = self._pag_duplicate_adjacencies()
        if duplicates:
            src, dst = duplicates[0]
            raise ValueError(
                "PAG requires at most one edge per unordered node pair; "
                f"duplicate adjacency ({src!r}, {dst!r})"
            )

    def model_post_init(self, __context: Any) -> None:
        self._freeze_collections()

    def _freeze_collections(self) -> None:
        object.__setattr__(self, "nodes", _freeze_value(self.nodes))
        object.__setattr__(self, "edges", _freeze_value(self.edges))
        object.__setattr__(self, "metadata", _freeze_value(self.metadata))
        for edge in self.edges:
            if isinstance(edge, CausalEdge):
                edge._freeze_collections()

    def model_copy(
        self,
        *,
        update: Mapping[str, Any] | None = None,
        deep: bool = False,
    ) -> Self:
        copied = super().model_copy(update=update, deep=deep)
        if copied.graph_type == GraphType.PAG:
            copied._ensure_pag_unique_adjacencies()
        copied._freeze_collections()
        copied.__dict__.pop("kuzu_node_rows", None)
        copied.__dict__.pop("kuzu_edge_rows", None)
        copied.__dict__.pop("_kuzu_node_rows_json", None)
        copied.__dict__.pop("_kuzu_edge_rows_json", None)
        return copied

    @staticmethod
    def _dot_escape(value: str) -> str:
        return value.replace("\\", "\\\\").replace('"', '\\"')

    def to_dot(self) -> str:
        """
        Convert graph to DOT digraph for DoWhy.

        Requires a fully oriented DAG (tail->arrow edges only).
        """
        if self.graph_type is not GraphType.DAG:
            raise ValueError("to_dot() is only supported for DAG graphs")
        lines: list[str] = ["digraph {"]
        for node in self.nodes:
            lines.append(f'  "{self._dot_escape(node)}";')
        for edge in self.edges:
            if edge.mark_src is not EdgeMark.TAIL or edge.mark_dst is not EdgeMark.ARROW:
                raise ValueError("to_dot() requires fully oriented edges (tail->arrow)")
            src = self._dot_escape(edge.src)
            dst = self._dot_escape(edge.dst)
            if edge.lag is None:
                lines.append(f'  "{src}" -> "{dst}";')
            else:
                # Keep compact temporal edges distinguishable in the serialized
                # representation. Static consumers must reject these edges before
                # handing the DOT text to a backend that ignores attributes.
                lines.append(f'  "{src}" -> "{dst}" [lag="{edge.lag}", temporal="true"];')
        lines.append("}")
        return "\n".join(lines)

    def to_rustworkx(self) -> tuple[Any, dict[str, int]]:
        rx_module = importlib.import_module("rustworkx")
        graph_factory = getattr(rx_module, "PyDiGraph", None)
        if not callable(graph_factory):
            raise AttributeError("rustworkx does not expose PyDiGraph")
        graph_candidate: object = graph_factory()
        if not isinstance(graph_candidate, _RustworkxDirectedGraph) or not (
            protocol_declared_callables_are_callable(
                graph_candidate,
                _RustworkxDirectedGraph,
            )
        ):
            raise TypeError("rustworkx PyDiGraph does not expose the required graph methods")
        graph = graph_candidate

        node_map: dict[str, int] = {}
        for node in self.nodes:
            idx = graph.add_node(node)
            node_map[node] = idx
        for edge in self.edges:
            graph.add_edge(
                node_map[edge.src],
                node_map[edge.dst],
                edge.model_dump(mode="json", exclude={"src", "dst"}),
            )
        return graph, node_map

    def to_networkx(self) -> Any:
        import networkx as nx

        graph: nx.MultiDiGraph[str, dict[str, object], dict[str, object]] = nx.MultiDiGraph()
        graph.add_nodes_from(self.nodes)
        grouped_edges: dict[
            tuple[str, str, str, str, int | None],
            list[tuple[str, dict[str, Any]]],
        ] = {}
        for edge in self.edges:
            edge_payload = edge.model_dump(mode="json", exclude={"src", "dst"})
            relation = (
                edge.src,
                edge.dst,
                edge.mark_src.value,
                edge.mark_dst.value,
                edge.lag,
            )
            payload_identity = json.dumps(
                edge_payload,
                sort_keys=True,
                separators=(",", ":"),
            )
            grouped_edges.setdefault(relation, []).append((payload_identity, edge_payload))

        for relation, edges in grouped_edges.items():
            src, dst, mark_src, mark_dst, lag = relation
            for ordinal, (_, edge_payload) in enumerate(sorted(edges, key=lambda item: item[0])):
                # NetworkX keys are scoped to (src, dst). Typed marks and lag
                # identify the relation class; payload ordinals separate distinct
                # payloads and exact duplicates without hash collisions.
                relation_key = (mark_src, mark_dst, lag, ordinal)
                graph.add_edge(
                    src,
                    dst,
                    key=relation_key,
                    **edge_payload,
                )
        return graph

    @cached_property
    def _kuzu_node_rows_json(self) -> tuple[str, ...]:
        """Cache immutable serialized node rows for this graph version."""
        return tuple(json.dumps({"name": node}) for node in self.nodes)

    @property
    def kuzu_node_rows(self) -> tuple[dict[str, str], ...]:
        """Return detached node rows backed by an immutable preparation cache."""
        return tuple(json.loads(row) for row in self._kuzu_node_rows_json)

    @cached_property
    def _kuzu_edge_rows_json(self) -> tuple[str, ...]:
        """Cache immutable serialized edge rows for this graph version."""
        graph_type = self.graph_type.value
        return tuple(
            json.dumps(_serialize_kuzu_edge_row(edge, graph_type=graph_type)) for edge in self.edges
        )

    @property
    def kuzu_edge_rows(self) -> tuple[dict[str, Any], ...]:
        """Return detached edge rows backed by an immutable preparation cache."""
        return tuple(json.loads(row) for row in self._kuzu_edge_rows_json)

    def to_kuzu(self, kuzu_conn: Any) -> None:
        for row in self.kuzu_node_rows:
            kuzu_conn.execute("MERGE (v:CausalVar {name: $name})", row)

        for row in self.kuzu_edge_rows:
            kuzu_conn.execute(
                (
                    "MATCH (s:CausalVar {name: $src}), (d:CausalVar {name: $dst}) "
                    "MERGE (s)-[r:CausalEdge]->(d) "
                    "SET r.mark_src = $mark_src, "
                    "r.mark_dst = $mark_dst, "
                    "r.lag = $lag, "
                    "r.combined_confidence = $combined_confidence, "
                    "r.graph_type = $graph_type, "
                    "r.sources = $sources, "
                    "r.evidence_refs = $evidence_refs, "
                    "r.metadata_json = $metadata_json"
                ),
                row,
            )


def _serialize_kuzu_edge_row(edge: CausalEdge, *, graph_type: str) -> dict[str, Any]:
    return {
        "src": edge.src,
        "dst": edge.dst,
        "mark_src": edge.mark_src.value,
        "mark_dst": edge.mark_dst.value,
        "lag": edge.lag,
        "combined_confidence": edge.combined_confidence,
        "graph_type": graph_type,
        "sources": json.dumps([source.value for source in edge.sources]),
        "evidence_refs": json.dumps(edge.evidence_refs),
        "metadata_json": json.dumps(edge.metadata, sort_keys=True),
    }


def _validate_mgraph_structure(nodes: list[str], edges: list[CausalEdge]) -> None:
    """Validate the naming contract for an M-graph.

    For every node named "R_X" in nodes:
      - The substantive variable "X" must also be in nodes.
      - The proxy variable "X_star" must also be in nodes.
    For every node named "X_star" in nodes:
      - An edge R_X → X_star (TAIL→ARROW) must exist.
    Raises ValueError with a descriptive message on violation.
    """
    node_set = set(nodes)
    directed = {
        (e.src, e.dst) for e in edges if e.mark_src.value == "tail" and e.mark_dst.value == "arrow"
    }

    for node in nodes:
        if node.startswith("R_"):
            target = node[2:]  # "R_X" → "X"
            if target not in node_set:
                raise ValueError(
                    f"M-graph node '{node}' has no corresponding substantive variable '{target}'"
                )
            proxy = f"{target}_star"
            if proxy not in node_set:
                raise ValueError(
                    f"M-graph node '{node}' has no corresponding proxy variable '{proxy}'"
                )
        elif node.endswith("_star"):
            target = node[:-5]  # "X_star" → "X"
            r_node = f"R_{target}"
            if r_node not in node_set:
                raise ValueError(f"M-graph proxy '{node}' has no corresponding R-node '{r_node}'")
            # Edge R_X → X_star must exist
            if (r_node, node) not in directed:
                raise ValueError(f"M-graph requires directed edge '{r_node}' → '{node}'")


def _has_directed_cycle(
    *,
    nodes: list[str],
    edges: list[CausalEdge],
    include_lagged: bool = True,
) -> bool:
    indegree: dict[str, int] = dict.fromkeys(nodes, 0)
    adjacency: dict[str, list[str]] = {node: [] for node in nodes}
    for edge in edges:
        if not include_lagged and edge.lag not in (None, 0):
            continue
        adjacency[edge.src].append(edge.dst)
        indegree[edge.dst] += 1

    queue = [node for node, deg in indegree.items() if deg == 0]
    visited = 0
    while queue:
        node = queue.pop()
        visited += 1
        for nxt in adjacency[node]:
            indegree[nxt] -= 1
            if indegree[nxt] == 0:
                queue.append(nxt)
    return visited != len(nodes)


def persist_causal_graph_model(
    store: ArtifactStore,
    graph: CausalGraphModel,
    *,
    inputs: list[InputRef] | None = None,
    schema_name: str = "ir.causal_graph_model",
    schema_version: str = "1.0",
    return_selected_profile: bool = False,
) -> CausalGraphModelRef:
    """Persist a graph and optionally return the exact profile selected by this write."""
    ref = put_json_artifact(
        store,
        graph.model_dump(mode="json"),
        kind="ir.causal_graph_model",
        schema_name=schema_name,
        schema_version=schema_version,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=return_selected_profile,
    )
    return CausalGraphModelRef.model_validate(ref)


def load_causal_graph_model(
    store: ArtifactStore,
    ref: CausalGraphModelRef,
) -> CausalGraphModel:
    """Load causal graph model."""
    payload = get_json_artifact(store, ref)
    return CausalGraphModel.model_validate(payload)


def _dag_projection_refusal_code_from_canonical(
    graph: CausalGraphModel,
) -> str | None:
    """Apply the projection profile only to an already canonical graph snapshot."""
    if graph.graph_type is GraphType.DAG:
        return None
    if graph.graph_type not in {GraphType.PAG, GraphType.CPDAG, GraphType.ADMG}:
        return "graph_type_not_admitted_for_dag_projection"
    if any(edge.lag not in (None, 0) for edge in graph.edges):
        return "temporal_graph_projection_not_admitted"
    for edge in graph.edges:
        pair = (edge.mark_src, edge.mark_dst)
        if pair in {
            (EdgeMark.TAIL, EdgeMark.ARROW),
            (EdgeMark.ARROW, EdgeMark.TAIL),
        }:
            continue
        if graph.graph_type is GraphType.ADMG and pair == (
            EdgeMark.ARROW,
            EdgeMark.ARROW,
        ):
            continue
        return "partial_graph_endpoint_profile_not_admitted"
    return None


def project_graph_to_dag(graph: CausalGraphModel) -> tuple[CausalGraphModel, list[str]]:
    """Build the unique admitted DAG representation for a supported source profile.

    DAG inputs preserve their graph content in a detached canonical snapshot.
    Directed-only PAG/CPDAG sources preserve their known orientations. Static
    ADMG bidirected edges receive explicit latent parents. Other profiles retain
    their source graph and are refused.
    """
    try:
        graph = _canonical_causal_graph(graph)
    except (TypeError, ValueError) as exc:
        raise UnsupportedGraphProjectionError("causal_graph_profile_invalid") from exc
    refusal = _dag_projection_refusal_code_from_canonical(graph)
    if refusal is not None:
        raise UnsupportedGraphProjectionError(refusal)
    if graph.graph_type is GraphType.DAG:
        return graph, []

    new_edges: list[CausalEdge] = []
    latent_vars: list[str] = []
    used_nodes = set(graph.nodes)
    projection_stats = {"bidirected_replaced": 0, "reversed_normalized": 0}

    def next_latent_name() -> str:
        index = 0
        while True:
            candidate = f"U_{index}"
            index += 1
            if candidate not in used_nodes:
                used_nodes.add(candidate)
                return candidate

    for edge in graph.edges:
        if edge.mark_src is EdgeMark.ARROW and edge.mark_dst is EdgeMark.ARROW:
            latent_name = next_latent_name()
            latent_vars.append(latent_name)
            projection_stats["bidirected_replaced"] += 1
            edge_label = f"{edge.src}<->{edge.dst}"
            base_meta = dict(edge.metadata)
            for endpoint in (edge.src, edge.dst):
                new_edges.append(
                    edge.model_copy(
                        update={
                            "src": latent_name,
                            "dst": endpoint,
                            "mark_src": EdgeMark.TAIL,
                            "mark_dst": EdgeMark.ARROW,
                            "metadata": {
                                **base_meta,
                                "latent_proxy": True,
                                "original_bidirected": edge_label,
                            },
                        }
                    )
                )
            continue
        if edge.mark_src is EdgeMark.ARROW and edge.mark_dst is EdgeMark.TAIL:
            projection_stats["reversed_normalized"] += 1
            new_edges.append(
                edge.model_copy(
                    update={
                        "src": edge.dst,
                        "dst": edge.src,
                        "mark_src": EdgeMark.TAIL,
                        "mark_dst": EdgeMark.ARROW,
                        "metadata": {
                            **dict(edge.metadata),
                            "orientation_normalized": True,
                            "original_src": edge.src,
                            "original_dst": edge.dst,
                            "original_marks": [
                                edge.mark_src.value,
                                edge.mark_dst.value,
                            ],
                        },
                    }
                )
            )
            continue
        if edge.mark_src is EdgeMark.TAIL and edge.mark_dst is EdgeMark.ARROW:
            new_edges.append(edge)
            continue
        raise ValueError(
            "cannot project unresolved partial orientation: "
            f"{edge.src!r} {edge.mark_src.value}-{edge.mark_dst.value} {edge.dst!r}"
        )

    metadata = {
        **dict(graph.metadata),
        "pag_projection": {
            "performed": True,
            "latent_vars": list(latent_vars),
            **projection_stats,
        },
    }
    projected = CausalGraphModel(
        schema_version=graph.schema_version,
        graph_type=GraphType.DAG,
        nodes=list(graph.nodes) + latent_vars,
        edges=new_edges,
        discovery_method=graph.discovery_method,
        skg_version_id=graph.skg_version_id,
        pag_identification_policy=graph.pag_identification_policy,
        id_confidence_under_pag=None,
        metadata=metadata,
    )
    return projected, latent_vars


__all__ = [
    "CausalEdge",
    "CausalGraphModel",
    "EdgeMark",
    "EdgeSource",
    "GraphProjectionDisposition",
    "GraphProjectionStatus",
    "GraphType",
    "PAGIdentificationPolicy",
    "UnsupportedGraphProjectionError",
    "graph_content_sha256",
    "graph_for_analysis",
    "graph_projection_disposition",
    "legacy_graph_projection_disposition",
    "load_causal_graph_model",
    "persist_causal_graph_model",
    "project_graph_to_dag",
]
