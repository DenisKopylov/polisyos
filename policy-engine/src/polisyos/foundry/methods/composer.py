"""
Method Composer - builds execution DAG using graphlib.

This module provides the builder-pattern API for composing multiple
Foundry methods into a validated, topologically-sorted execution chain.

Architecture laws:
- Law G: No NetworkX - uses Python's built-in graphlib.TopologicalSorter
- Law H: Deterministic ordering for reproducible builds
- Law I: Static vs Dynamic parameter separation
"""

from __future__ import annotations

import graphlib
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from polisyos.foundry.methods.base import MethodSignature, _stable_digest
from polisyos.foundry.methods.exceptions import CyclicDependencyError, MissingRequirementError
from polisyos.foundry.methods.linker import LinkResult, SlotBinding, SlotLinker
from polisyos.foundry.methods.registry import MethodRegistry

if TYPE_CHECKING:
    from polisyos.foundry.methods.backends.chain_executor import ExecutorMode, FxRateProvider

__all__ = [
    "CompiledMethodChain",
    "CompositionDAG",
    "MethodComposer",
    "MethodNode",
    "SemanticValidationLevel",
]


class SemanticValidationLevel(Enum):
    """Controls how strictly the composer validates semantic constraints."""

    OFF = "off"
    WARN = "warn"
    STRICT = "strict"


# =============================================================================
# Data Structures
# =============================================================================


@dataclass(frozen=True, slots=True, order=True)
class NodeKey:
    """
    Stable identifier for a node instance within a composition.

    This key is stable across runs for identical method FQNs and static
    parameters, and can be used for canonical ordering and cache keys.
    """

    method_fqn: str
    static_params_digest: str


def _stable_params_digest(params: Mapping[str, Any]) -> str:
    try:
        return _stable_digest(dict(params))
    except TypeError as exc:
        raise TypeError(f"Static parameters must be stable-serializable: {exc}") from exc


@dataclass(frozen=True, slots=True)
class MethodNode:
    """
    A node in the composition DAG representing a method instance.

    Each node is uniquely identified by its UUID. Multiple nodes can
    reference the same method FQN with different parameter values.
    """

    id: UUID
    method_fqn: str
    params: Mapping[str, Any]
    static_params: Mapping[str, Any]
    node_key: NodeKey | None = None
    instance_index: int = 0
    commutes_with: frozenset[str] = frozenset()

    # Track insertion order for deterministic sorting
    _insertion_order: int = field(default=0, compare=False, hash=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "params", MappingProxyType(dict(self.params)))
        object.__setattr__(self, "static_params", MappingProxyType(dict(self.static_params)))
        if self.node_key is None:
            digest = _stable_params_digest(self.static_params)
            object.__setattr__(self, "node_key", NodeKey(self.method_fqn, digest))
        if not isinstance(self.commutes_with, frozenset):
            object.__setattr__(self, "commutes_with", frozenset(self.commutes_with))

    def __hash__(self) -> int:
        return hash(self.id)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, MethodNode):
            return NotImplemented
        return self.id == other.id

    def __repr__(self) -> str:
        return f"MethodNode({self.method_fqn}, id={str(self.id)[:8]}...)"


@dataclass(slots=True)
class CompositionDAG:
    """
    A directed acyclic graph of method nodes.

    Uses adjacency list representation for O(V + E) operations.
    Edges represent data flow: source outputs -> target inputs.
    """

    nodes: dict[UUID, MethodNode] = field(default_factory=dict)
    successors: dict[UUID, set[UUID]] = field(default_factory=dict)
    predecessors: dict[UUID, set[UUID]] = field(default_factory=dict)
    edges: dict[tuple[UUID, UUID], LinkResult] = field(default_factory=dict)
    _insertion_counter: int = field(default=0, repr=False)

    def add_node(self, node: MethodNode) -> None:
        if node.id in self.nodes:
            raise ValueError(f"Node {node.id} already exists in DAG")

        self.nodes[node.id] = node
        if node.id not in self.successors:
            self.successors[node.id] = set()
        if node.id not in self.predecessors:
            self.predecessors[node.id] = set()

    def add_edge(self, source_id: UUID, target_id: UUID, link_result: LinkResult) -> None:
        if source_id not in self.nodes:
            raise KeyError(f"Source node {source_id} not in DAG")
        if target_id not in self.nodes:
            raise KeyError(f"Target node {target_id} not in DAG")

        self.successors[source_id].add(target_id)
        self.predecessors[target_id].add(source_id)
        self.edges[(source_id, target_id)] = link_result

    def _stable_key(self, node_id: UUID) -> tuple[NodeKey, int, int]:
        node = self.nodes[node_id]
        node_key = node.node_key or NodeKey(node.method_fqn, "")
        return (node_key, node.instance_index, node._insertion_order)

    def _sort_ready(self, ready: Sequence[UUID]) -> list[UUID]:
        if len(ready) <= 1:
            return list(ready)

        ready_set = set(ready)

        def mut_commutes(a: UUID, b: UUID) -> bool:
            node_a = self.nodes[a]
            node_b = self.nodes[b]
            return (
                node_b.method_fqn in node_a.commutes_with
                and node_a.method_fqn in node_b.commutes_with
            )

        def commutes_with_all(node_id: UUID) -> bool:
            for other in ready_set:
                if other == node_id:
                    continue
                if not mut_commutes(node_id, other):
                    return False
            return True

        order_sensitive: list[UUID] = []
        commuting: list[UUID] = []
        for node_id in ready:
            if commutes_with_all(node_id):
                commuting.append(node_id)
            else:
                order_sensitive.append(node_id)

        order_sensitive.sort(
            key=lambda nid: (self.nodes[nid]._insertion_order, self._stable_key(nid))
        )
        commuting.sort(key=self._stable_key)
        return order_sensitive + commuting

    def topological_order(
        self,
        extra_predecessors: Mapping[UUID, set[UUID]] | None = None,
    ) -> list[UUID]:
        graph: dict[UUID, set[UUID]] = {}
        for node_id in self.nodes:
            preds = set(self.predecessors.get(node_id, set()))
            if extra_predecessors and node_id in extra_predecessors:
                preds |= {p for p in extra_predecessors[node_id] if p in self.nodes}
            graph[node_id] = preds

        sorter = graphlib.TopologicalSorter(graph)
        try:
            sorter.prepare()
        except graphlib.CycleError as exc:
            cycle_nodes: list[UUID] = []
            for arg in exc.args:
                if isinstance(arg, (list, tuple)):
                    cycle_nodes = list(arg)
                    break
            cycle_fqns = [
                self.nodes[uid].method_fqn if uid in self.nodes else str(uid) for uid in cycle_nodes
            ]
            if not cycle_fqns:
                cycle_fqns = ["<cycle>"]
            raise CyclicDependencyError(cycle_fqns) from None

        order: list[UUID] = []
        ready = list(sorter.get_ready())
        while ready:
            batch = self._sort_ready(ready)
            order.extend(batch)
            for node_id in batch:
                sorter.done(node_id)
            ready = list(sorter.get_ready())
        return order

    def get_roots(self) -> list[UUID]:
        roots = [nid for nid, preds in self.predecessors.items() if not preds]
        roots.sort(key=lambda nid: (self.nodes[nid]._insertion_order, self._stable_key(nid)))
        return roots

    def get_leaves(self) -> list[UUID]:
        leaves = [nid for nid, succs in self.successors.items() if not succs]
        leaves.sort(key=lambda nid: (self.nodes[nid]._insertion_order, self._stable_key(nid)))
        return leaves

    def get_edge(self, source_id: UUID, target_id: UUID) -> LinkResult | None:
        return self.edges.get((source_id, target_id))

    def compute_parallel_levels(
        self,
        extra_predecessors: Mapping[UUID, set[UUID]] | None = None,
    ) -> list[list[UUID]]:
        """
        Partition the DAG into topological *levels*.

        All nodes within the same level are mutually independent and can
        execute concurrently.  Nodes in level *k+1* depend only on nodes
        in levels 0..k.

        Returns
        -------
        list[list[UUID]]
            Ordered list of levels; each level is a sorted list of node UUIDs.
            The sort order within each level follows the same stable key as
            ``topological_order()`` (insertion order first, then NodeKey).

        Raises
        ------
        CyclicDependencyError
            If the DAG contains a cycle.
        """
        # Build in-degree map respecting extra_predecessors
        in_degree: dict[UUID, int] = {}
        adj: dict[UUID, set[UUID]] = {nid: set() for nid in self.nodes}

        for node_id in self.nodes:
            preds = set(self.predecessors.get(node_id, set()))
            if extra_predecessors and node_id in extra_predecessors:
                preds |= {p for p in extra_predecessors[node_id] if p in self.nodes}
            in_degree[node_id] = len(preds)
            for pred_id in preds:
                if pred_id in adj:
                    adj[pred_id].add(node_id)

        levels: list[list[UUID]] = []
        ready: list[UUID] = [nid for nid, deg in in_degree.items() if deg == 0]

        processed = 0
        while ready:
            batch = self._sort_ready(ready)
            levels.append(batch)
            processed += len(batch)
            next_ready: list[UUID] = []
            for node_id in batch:
                for succ_id in adj.get(node_id, set()):
                    in_degree[succ_id] -= 1
                    if in_degree[succ_id] == 0:
                        next_ready.append(succ_id)
            ready = next_ready

        if processed != len(self.nodes):
            # Cycle detected
            remaining = [nid for nid, deg in in_degree.items() if deg > 0]
            cycle_fqns = [self.nodes[uid].method_fqn for uid in remaining[:5]]
            raise CyclicDependencyError(cycle_fqns)

        return levels

    def freeze(self) -> FrozenCompositionDAG:
        nodes = MappingProxyType(dict(self.nodes))
        successors = MappingProxyType(
            {nid: frozenset(succs) for nid, succs in self.successors.items()}
        )
        predecessors = MappingProxyType(
            {nid: frozenset(preds) for nid, preds in self.predecessors.items()}
        )
        edges = MappingProxyType(dict(self.edges))
        return FrozenCompositionDAG(
            nodes=nodes,
            successors=successors,
            predecessors=predecessors,
            edges=edges,
        )

    def __len__(self) -> int:
        return len(self.nodes)

    def __contains__(self, node_id: UUID) -> bool:
        return node_id in self.nodes


@dataclass(frozen=True, slots=True)
class FrozenCompositionDAG:
    """
    Immutable snapshot of a composition DAG.

    Provides read-only access to nodes, edges, and adjacency lists.
    """

    nodes: Mapping[UUID, MethodNode]
    successors: Mapping[UUID, frozenset[UUID]]
    predecessors: Mapping[UUID, frozenset[UUID]]
    edges: Mapping[tuple[UUID, UUID], LinkResult]

    def get_edge(self, source_id: UUID, target_id: UUID) -> LinkResult | None:
        return self.edges.get((source_id, target_id))

    def get_roots(self) -> list[UUID]:
        roots = [nid for nid, preds in self.predecessors.items() if not preds]
        roots.sort(
            key=lambda nid: (
                self.nodes[nid]._insertion_order,
                self.nodes[nid].node_key,
                self.nodes[nid].instance_index,
            )
        )
        return roots

    def get_leaves(self) -> list[UUID]:
        leaves = [nid for nid, succs in self.successors.items() if not succs]
        leaves.sort(
            key=lambda nid: (
                self.nodes[nid]._insertion_order,
                self.nodes[nid].node_key,
                self.nodes[nid].instance_index,
            )
        )
        return leaves

    def __len__(self) -> int:
        return len(self.nodes)

    def __contains__(self, node_id: UUID) -> bool:
        return node_id in self.nodes


# =============================================================================
# Method Composer
# =============================================================================


class MethodComposer:
    """
    Builder-pattern class for composing methods into an execution DAG.

    Provides a fluent API for:
    1. Adding method instances with specific parameters
    2. Connecting methods (validating data flow compatibility)
    3. Validating the composition (cycles, conflicts, requirements)
    4. Building the final execution chain

    Note:
        requires declarations are treated as dependency-only edges for
        ordering, even when no data-flow edge exists.
    """

    def __init__(
        self,
        registry: MethodRegistry | None = None,
        linker: SlotLinker | None = None,
    ) -> None:
        self._registry = registry or MethodRegistry.get_instance()
        self._linker = linker or SlotLinker()
        self._dag = CompositionDAG()

        self._signatures: dict[UUID, MethodSignature] = {}
        self._insertion_counter = 0
        self._instance_counters: dict[NodeKey, int] = {}

    @property
    def dag(self) -> CompositionDAG:
        return self._dag

    def add(self, method_name: str, **params: Any) -> MethodNode:
        """Add a method instance to the composition."""
        method_class = self._registry.get(method_name)
        sig = method_class.signature

        static_params: dict[str, Any] = {}
        dynamic_params: dict[str, Any] = {}

        for param_spec in sig.parameters:
            value = params.get(param_spec.name, param_spec.default)
            if param_spec.is_static:
                static_params[param_spec.name] = value
            else:
                dynamic_params[param_spec.name] = value

        known_params = {p.name for p in sig.parameters}
        unknown = set(params.keys()) - known_params
        if unknown:
            raise ValueError(
                f"Unknown parameters for {sig.fqn}: {sorted(unknown)}. "
                f"Valid parameters: {sorted(known_params)}"
            )

        static_digest = _stable_params_digest(static_params)
        node_key = NodeKey(sig.fqn, static_digest)
        instance_index = self._instance_counters.get(node_key, 0)
        self._instance_counters[node_key] = instance_index + 1

        node = MethodNode(
            id=uuid4(),
            method_fqn=sig.fqn,
            params=dynamic_params,
            static_params=static_params,
            node_key=node_key,
            instance_index=instance_index,
            commutes_with=sig.commutes_with,
            _insertion_order=self._insertion_counter,
        )
        self._insertion_counter += 1
        self._dag._insertion_counter = self._insertion_counter

        self._dag.add_node(node)
        self._signatures[node.id] = sig

        return node

    def connect(
        self,
        source: MethodNode,
        target: MethodNode,
        slot_mapping: Mapping[str, str] | None = None,
    ) -> LinkResult:
        """Connect source outputs to target inputs (data flow)."""
        if source.id not in self._dag.nodes:
            raise KeyError(f"Source node {source.id} not in composition")
        if target.id not in self._dag.nodes:
            raise KeyError(f"Target node {target.id} not in composition")

        source_sig = self._signatures[source.id]
        target_sig = self._signatures[target.id]

        link_result = self._linker.link(
            source_sig,
            target_sig,
            explicit_mapping=slot_mapping,
        )

        link_result = link_result.with_node_ids(source.id, target.id)
        self._dag.add_edge(source.id, target.id, link_result)

        return link_result

    def _requirement_edges(
        self,
        level: SemanticValidationLevel = SemanticValidationLevel.WARN,
    ) -> tuple[dict[UUID, set[UUID]], list[str]]:
        warnings: list[str] = []
        predecessors: dict[UUID, set[UUID]] = {}
        fqn_to_ids: dict[str, list[UUID]] = {}

        for node_id, sig in self._signatures.items():
            fqn_to_ids.setdefault(sig.fqn, []).append(node_id)

        for node_id, sig in self._signatures.items():
            required_ids: set[UUID] = set()
            for required_fqn in sig.requires:
                ids = fqn_to_ids.get(required_fqn)
                if not ids:
                    if level == SemanticValidationLevel.STRICT:
                        raise MissingRequirementError(sig.fqn, required_fqn)
                    elif level == SemanticValidationLevel.WARN:
                        warnings.append(
                            f"MISSING REQUIREMENT: {sig.fqn} requires {required_fqn}, "
                            "which is not in composition"
                        )
                    # OFF → silent continue
                    continue
                required_ids.update(ids)

            if required_ids:
                predecessors[node_id] = required_ids

        return predecessors, warnings

    def validate(
        self,
        level: SemanticValidationLevel = SemanticValidationLevel.WARN,
    ) -> list[str]:
        """Validate the composition; returns warnings without raising."""
        warnings: list[str] = []

        req_predecessors, req_warnings = self._requirement_edges(level=level)
        warnings.extend(req_warnings)

        try:
            self._dag.topological_order(extra_predecessors=req_predecessors)
        except CyclicDependencyError as exc:
            warnings.append(f"CRITICAL: {exc}")

        all_fqns = {self._signatures[nid].fqn for nid in self._dag.nodes}
        for node_id in self._dag.nodes:
            sig = self._signatures[node_id]
            for conflict_fqn in sig.conflicts_with:
                if conflict_fqn in all_fqns:
                    warnings.append(
                        f"CONFLICT: {sig.fqn} declares conflict with {conflict_fqn}, "
                        "but both are present in composition"
                    )

        for link_result in self._dag.edges.values():
            warnings.extend(link_result.warnings)
            if link_result.unconnected_inputs:
                target_label = link_result.target_fqn
                if link_result.target_id is not None:
                    target_label = f"{target_label} ({str(link_result.target_id)[:8]})"
                warnings.append(
                    f"Unconnected inputs in {target_label}: {list(link_result.unconnected_inputs)}"
                )

        return warnings

    def build(
        self,
        *,
        validate_semantics: SemanticValidationLevel | bool = SemanticValidationLevel.WARN,
    ) -> CompiledMethodChain:
        """Build the compiled chain; raises on cyclic dependencies.

        Parameters
        ----------
        validate_semantics:
            Controls semantic validation level:
            - ``SemanticValidationLevel.OFF`` — no semantic checks
            - ``SemanticValidationLevel.WARN`` (default) — append warnings
            - ``SemanticValidationLevel.STRICT`` — raise on errors

            For backward compatibility, ``bool`` values are accepted:
            ``True`` maps to ``STRICT``, ``False`` maps to ``OFF``.
        """
        # Backward compat: accept bool
        if isinstance(validate_semantics, bool):
            validate_semantics = (
                SemanticValidationLevel.STRICT
                if validate_semantics
                else SemanticValidationLevel.OFF
            )

        warnings = self.validate(level=validate_semantics)
        req_predecessors, _req_warnings = self._requirement_edges(level=validate_semantics)
        order = self._dag.topological_order(extra_predecessors=req_predecessors)

        all_bindings: list[SlotBinding] = []
        for link_result in self._dag.edges.values():
            all_bindings.extend(link_result.bindings)
        all_bindings.sort(
            key=lambda b: (
                str(b.target_node_id) if b.target_node_id is not None else b.target_method,
                b.target_slot,
                str(b.source_node_id) if b.source_node_id is not None else b.source_method,
                b.source_slot,
            )
        )

        # Compute composition-aware cache keys (includes upstream context)
        frozen_dag = self._dag.freeze()
        cache_keys = self._compute_composition_cache_keys(
            frozen_dag,
            req_predecessors,
        )

        chain = CompiledMethodChain(
            dag=frozen_dag,
            signatures=MappingProxyType(dict(self._signatures)),
            execution_order=tuple(order),
            bindings=tuple(all_bindings),
            warnings=tuple(w for w in warnings if not w.startswith("CRITICAL:")),
            cache_keys=cache_keys,
        )

        if validate_semantics != SemanticValidationLevel.OFF:
            from polisyos.foundry.methods.semantic_validator import CrossMethodValidator

            strict = validate_semantics == SemanticValidationLevel.STRICT
            validator = CrossMethodValidator(strict=strict)
            report = validator.validate_chain(chain)

            if report.errors and strict:
                raise ValueError(f"Chain failed semantic validation:\n{report.summary()}")

            if report.warnings or (report.errors and not strict):
                all_issues = list(report.warnings) + (list(report.errors) if not strict else [])
                semantic_warnings = tuple(f"[semantic] {issue.message}" for issue in all_issues)
                from dataclasses import replace as _replace

                chain = _replace(chain, warnings=chain.warnings + semantic_warnings)

        return chain

    def _compute_composition_cache_keys(
        self,
        frozen_dag: FrozenCompositionDAG,
        req_predecessors: dict[UUID, set[UUID]],
    ) -> MappingProxyType[UUID, str]:
        """Compute cache keys that incorporate upstream context and backend."""
        cache_keys: dict[UUID, str] = {}
        for node_id in frozen_dag.nodes:
            node = frozen_dag.nodes[node_id]
            sig = self._signatures[node_id]
            # Gather all predecessors: both data-flow and requirement edges
            upstream_ids: set[UUID] = set(frozen_dag.predecessors.get(node_id, frozenset()))
            if node_id in req_predecessors:
                upstream_ids |= {
                    uid for uid in req_predecessors[node_id] if uid in frozen_dag.nodes
                }
            upstream_digests = sorted(
                frozen_dag.nodes[uid].node_key.static_params_digest
                for uid in upstream_ids
                if frozen_dag.nodes[uid].node_key is not None
            )
            combined = {
                "static_params": dict(node.static_params),
                "upstream_digests": upstream_digests,
                "backend": sig.backend.value if sig.backend else None,
            }
            cache_keys[node_id] = _stable_digest(combined)
        return MappingProxyType(cache_keys)

    def __len__(self) -> int:
        return len(self._dag)

    def __repr__(self) -> str:
        n_nodes = len(self._dag.nodes)
        n_edges = len(self._dag.edges)
        return f"<MethodComposer nodes={n_nodes} edges={n_edges}>"


# =============================================================================
# Compiled Chain Output
# =============================================================================


@dataclass(frozen=True, slots=True)
class CompiledMethodChain:
    """
    An immutable, validated method chain ready for execution.

    Contains a frozen DAG snapshot, execution order, slot bindings, and warnings.
    """

    dag: FrozenCompositionDAG
    signatures: Mapping[UUID, MethodSignature]
    execution_order: tuple[UUID, ...]
    bindings: tuple[SlotBinding, ...]
    warnings: tuple[str, ...]
    cache_keys: Mapping[UUID, str] = field(default_factory=lambda: MappingProxyType({}))

    def __len__(self) -> int:
        return len(self.execution_order)

    def methods_in_order(self) -> Iterator[tuple[UUID, MethodSignature]]:
        for node_id in self.execution_order:
            yield node_id, self.signatures[node_id]

    def get_node(self, node_id: UUID) -> MethodNode:
        return self.dag.nodes[node_id]

    def get_signature(self, node_id: UUID) -> MethodSignature:
        return self.signatures[node_id]

    def get_bindings_for_target(self, target_id: UUID) -> list[SlotBinding]:
        target_fqn = self.signatures[target_id].fqn
        result: list[SlotBinding] = []
        for binding in self.bindings:
            if binding.target_node_id == target_id or (
                binding.target_node_id is None and binding.target_method == target_fqn
            ):
                result.append(binding)
        return result

    @property
    def has_warnings(self) -> bool:
        return len(self.warnings) > 0

    @property
    def fqn_order(self) -> list[str]:
        return [self.signatures[nid].fqn for nid in self.execution_order]

    def __repr__(self) -> str:
        return (
            f"CompiledMethodChain(methods={len(self)}, "
            f"bindings={len(self.bindings)}, warnings={len(self.warnings)})"
        )

    def execute_heterogeneous(
        self,
        *,
        state: Any,
        params_per_node: Mapping[UUID, Mapping[str, Any]] | None = None,
        seed: int = 0,
        registry: MethodRegistry | None = None,
        executor_mode: ExecutorMode = "sequential",
        async_node_timeout_sec: float | None = None,
        fx_rate_provider: FxRateProvider | None = None,
    ) -> Any:
        from polisyos.foundry.methods.backends.chain_executor import (
            execute_heterogeneous_chain,
        )

        return execute_heterogeneous_chain(
            self,
            state=state,
            params_per_node=params_per_node,
            seed=seed,
            registry=registry,
            executor_mode=executor_mode,
            async_node_timeout_sec=async_node_timeout_sec,
            fx_rate_provider=fx_rate_provider,
        )
