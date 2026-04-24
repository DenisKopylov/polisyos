"""Replay checks for proof traces after causal-fragment composition.

The Stage 2.2 contract is deliberately conservative: this module never claims
that a changed graph preserves a proof by analogy. It only marks a trace
``reusable`` when every recorded graphical witness has the same local support
projection and the same optional ancestor/district signatures. When a witness
changes but a local graphical obligation can still be checked, the certificate
is downgraded to ``revalidate``; when a critical witness is falsified, it is
``rederive``.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from itertools import combinations
from typing import TYPE_CHECKING, Any

from polisyos.foundry.methods.catalog.causal.admg_ops import (
    ancestors,
    c_components,
    induced_subgraph,
    m_separation,
    remove_incoming_edges,
    remove_outgoing_edges,
)
from polisyos.ir.analytics.causal_graph import CausalGraphModel, EdgeMark, GraphType
from polisyos.ir.analytics.proof_composability import (
    ProofComposabilityCertificate,
    ProofComposabilityStatus,
    ProofGraphWitness,
    ProofObligationKind,
    ProofReplayStepStatus,
    ProofWitnessIndex,
    build_proof_composability_certificate,
)

if TYPE_CHECKING:
    from polisyos.ir.analytics.evidence_bundle import ProofStep
    from polisyos.ir.refs import EvidenceBundleRef, ProofWitnessIndexRef


_MUTILATION_RE = re.compile(r"(?P<op>remove_in|remove_out|do)\s*\((?P<vars>[^)]*)\)")


@dataclass(frozen=True)
class WitnessReplayResult:
    """Internal replay result for one graphical witness."""

    witness_id: str
    step_status: ProofReplayStepStatus
    projection_preserved: bool | None
    current_projection_hash: str | None = None
    current_ancestor_signature: tuple[str, ...] = ()
    current_district_signature: tuple[tuple[str, ...], ...] = ()
    new_ancestors: tuple[str, ...] = ()
    new_district_links: tuple[tuple[str, str], ...] = ()
    reason: str = ""

    @property
    def is_preserved(self) -> bool:
        return (
            self.step_status is ProofReplayStepStatus.VALID
            and self.projection_preserved is True
            and not self.new_ancestors
            and not self.new_district_links
        )


def proof_support_projection_hash(
    graph: CausalGraphModel,
    *,
    support_vars: tuple[str, ...] | list[str] | set[str],
    mutilation: str = "",
) -> str:
    """Hash the witness support projection after applying a recorded mutilation.

    The hash is intentionally local and deterministic. It is based on the
    induced support subgraph after the same operation recorded in the witness;
    separate ancestor and district signatures should be stored when a step uses
    those objects.
    """

    support = frozenset(str(var) for var in support_vars)
    mutilated = apply_witness_mutilation(graph, mutilation)
    support_graph = induced_subgraph(mutilated, support)
    payload = {
        "graph_type": getattr(support_graph.graph_type, "value", str(support_graph.graph_type)),
        "nodes": sorted(support_graph.nodes),
        "directed_edges": sorted(
            (edge.src, edge.dst)
            for edge in support_graph.edges
            if edge.mark_src is EdgeMark.TAIL and edge.mark_dst is EdgeMark.ARROW
        ),
        "bidirected_edges": sorted(
            tuple(sorted((edge.src, edge.dst)))
            for edge in support_graph.edges
            if edge.mark_src is EdgeMark.ARROW and edge.mark_dst is EdgeMark.ARROW
        ),
        "circle_edges": sorted(
            (edge.src, edge.dst, edge.mark_src.value, edge.mark_dst.value)
            for edge in support_graph.edges
            if edge.mark_src is EdgeMark.CIRCLE or edge.mark_dst is EdgeMark.CIRCLE
        ),
        "mutilation": _normalize_mutilation(mutilation),
    }
    return _hash_payload(payload)


def proof_ancestor_signature(
    graph: CausalGraphModel,
    *,
    support_vars: tuple[str, ...] | list[str] | set[str],
    mutilation: str = "",
) -> tuple[str, ...]:
    """Return the sorted ancestor closure for a witness support set."""

    support = frozenset(str(var) for var in support_vars)
    mutilated = apply_witness_mutilation(graph, mutilation)
    return tuple(sorted(ancestors(mutilated, support)))


def proof_district_signature(
    graph: CausalGraphModel,
    *,
    support_vars: tuple[str, ...] | list[str] | set[str],
    mutilation: str = "",
) -> tuple[tuple[str, ...], ...]:
    """Return the support-local district signature after recorded mutilation."""

    support = frozenset(str(var) for var in support_vars)
    mutilated = apply_witness_mutilation(graph, mutilation)
    support_graph = induced_subgraph(mutilated, support)
    return _district_signature_from_components(c_components(support_graph))


def apply_witness_mutilation(graph: CausalGraphModel, mutilation: str) -> CausalGraphModel:
    """Apply the subset of do-calculus mutilations supported by Stage 2.2."""

    current = graph
    normalized = _normalize_mutilation(mutilation)
    if not normalized or normalized in {"none", "identity"}:
        return current
    for match in _MUTILATION_RE.finditer(normalized):
        op = match.group("op")
        nodes = frozenset(_parse_var_list(match.group("vars")))
        if not nodes:
            continue
        if op in {"remove_in", "do"}:
            current = remove_incoming_edges(current, nodes)
        elif op == "remove_out":
            current = remove_outgoing_edges(current, nodes)
    return current


def replay_graph_witness(
    witness: ProofGraphWitness,
    composed_graph: CausalGraphModel,
) -> WitnessReplayResult:
    """Replay one graphical witness against a composed graph."""

    if _unsupported_graph(composed_graph):
        return WitnessReplayResult(
            witness_id=witness.witness_id,
            step_status=ProofReplayStepStatus.UNKNOWN,
            projection_preserved=None,
            reason="unsupported_graph_for_replay",
        )
    if not witness.support_vars:
        return WitnessReplayResult(
            witness_id=witness.witness_id,
            step_status=ProofReplayStepStatus.UNKNOWN,
            projection_preserved=None,
            reason="missing_support_vars",
        )
    missing = sorted(set(witness.support_vars) - set(composed_graph.nodes))
    if missing:
        return WitnessReplayResult(
            witness_id=witness.witness_id,
            step_status=ProofReplayStepStatus.INVALID,
            projection_preserved=False,
            reason=f"support_vars_missing:{','.join(missing)}",
        )

    current_hash = proof_support_projection_hash(
        composed_graph,
        support_vars=witness.support_vars,
        mutilation=witness.mutilation,
    )
    current_ancestors = proof_ancestor_signature(
        composed_graph,
        support_vars=witness.support_vars,
        mutilation=witness.mutilation,
    )
    current_districts = proof_district_signature(
        composed_graph,
        support_vars=witness.support_vars,
        mutilation=witness.mutilation,
    )
    projection_preserved = (
        current_hash == witness.projection_hash if witness.projection_hash else None
    )
    expected_ancestors = tuple(witness.ancestor_signature)
    expected_districts = tuple(witness.district_signature)
    new_ancestors = tuple(sorted(set(current_ancestors) - set(expected_ancestors)))
    new_district_links = _new_district_links(expected_districts, current_districts)

    if (
        projection_preserved is True
        and (not expected_ancestors or current_ancestors == expected_ancestors)
        and (not expected_districts or current_districts == expected_districts)
    ):
        return WitnessReplayResult(
            witness_id=witness.witness_id,
            step_status=ProofReplayStepStatus.VALID,
            projection_preserved=True,
            current_projection_hash=current_hash,
            current_ancestor_signature=current_ancestors,
            current_district_signature=current_districts,
        )

    obligation_result = _recheck_obligation(witness, composed_graph)
    if obligation_result is False:
        return WitnessReplayResult(
            witness_id=witness.witness_id,
            step_status=ProofReplayStepStatus.INVALID,
            projection_preserved=projection_preserved,
            current_projection_hash=current_hash,
            current_ancestor_signature=current_ancestors,
            current_district_signature=current_districts,
            new_ancestors=new_ancestors if expected_ancestors else (),
            new_district_links=new_district_links if expected_districts else (),
            reason="obligation_broken_after_composition",
        )
    if obligation_result is True:
        return WitnessReplayResult(
            witness_id=witness.witness_id,
            step_status=ProofReplayStepStatus.VALID,
            projection_preserved=False if projection_preserved is False else projection_preserved,
            current_projection_hash=current_hash,
            current_ancestor_signature=current_ancestors,
            current_district_signature=current_districts,
            new_ancestors=new_ancestors if expected_ancestors else (),
            new_district_links=new_district_links if expected_districts else (),
            reason="obligation_revalidated_on_composed_graph",
        )

    if witness.obligation_kind in {
        ProofObligationKind.ANCESTRAL_RESTRICTION,
        ProofObligationKind.DISTRICT_FACTORIZATION,
        ProofObligationKind.HEDGE_WITNESS,
    } and (
        (expected_ancestors and current_ancestors != expected_ancestors)
        or (expected_districts and current_districts != expected_districts)
        or projection_preserved is False
    ):
        return WitnessReplayResult(
            witness_id=witness.witness_id,
            step_status=ProofReplayStepStatus.INVALID,
            projection_preserved=projection_preserved,
            current_projection_hash=current_hash,
            current_ancestor_signature=current_ancestors,
            current_district_signature=current_districts,
            new_ancestors=new_ancestors if expected_ancestors else (),
            new_district_links=new_district_links if expected_districts else (),
            reason="critical_witness_signature_changed",
        )

    return WitnessReplayResult(
        witness_id=witness.witness_id,
        step_status=ProofReplayStepStatus.UNKNOWN,
        projection_preserved=projection_preserved,
        current_projection_hash=current_hash,
        current_ancestor_signature=current_ancestors,
        current_district_signature=current_districts,
        new_ancestors=new_ancestors if expected_ancestors else (),
        new_district_links=new_district_links if expected_districts else (),
        reason="witness_needs_revalidation",
    )


def check_proof_trace_composability(
    *,
    witness_index: ProofWitnessIndex,
    composed_graph: CausalGraphModel,
    source_fragment_id: str,
    checked_query: str,
    composed_graph_ref: str | None = None,
    proof_trace_ref: EvidenceBundleRef | None = None,
    witness_index_ref: ProofWitnessIndexRef | None = None,
    interface_vars: tuple[str, ...] | list[str] | set[str] = (),
    invalidated_by_graph_hashes: tuple[str, ...] | list[str] | set[str] = (),
    metadata: dict[str, Any] | None = None,
) -> ProofComposabilityCertificate:
    """Build a Stage 2.2 composability certificate for a stored witness index."""

    replay = [replay_graph_witness(witness, composed_graph) for witness in witness_index.witnesses]
    replay_by_id = {item.witness_id: item for item in replay}

    step_statuses: dict[str, ProofReplayStepStatus] = {}
    for step_id, witness_ids in sorted(witness_index.step_to_witness_ids.items()):
        linked = [
            replay_by_id[witness_id] for witness_id in witness_ids if witness_id in replay_by_id
        ]
        if not linked:
            step_statuses[step_id] = ProofReplayStepStatus.UNKNOWN
        elif any(item.step_status is ProofReplayStepStatus.INVALID for item in linked):
            step_statuses[step_id] = ProofReplayStepStatus.INVALID
        elif all(item.is_preserved for item in linked):
            step_statuses[step_id] = ProofReplayStepStatus.VALID
        elif any(item.step_status is ProofReplayStepStatus.UNKNOWN for item in linked):
            step_statuses[step_id] = ProofReplayStepStatus.UNKNOWN
        else:
            step_statuses[step_id] = ProofReplayStepStatus.VALID

    preserved_witness_ids = tuple(sorted(item.witness_id for item in replay if item.is_preserved))
    broken_witness_ids = tuple(
        sorted(
            item.witness_id for item in replay if item.step_status is ProofReplayStepStatus.INVALID
        )
    )
    invalidation_reasons = tuple(
        sorted(
            {
                f"{item.witness_id}:{item.reason}"
                for item in replay
                if item.reason
                and item.step_status
                in {
                    ProofReplayStepStatus.INVALID,
                    ProofReplayStepStatus.UNKNOWN,
                }
            }
        )
    )
    new_ancestors = tuple(sorted({ancestor for item in replay for ancestor in item.new_ancestors}))
    new_district_links = tuple(
        sorted({link for item in replay for link in item.new_district_links})
    )
    projection_values = [
        item.projection_preserved for item in replay if item.projection_preserved is not None
    ]
    projection_preservation_passed = all(projection_values) if projection_values else None

    status = _resolve_composability_status(
        step_statuses=step_statuses,
        broken_witness_ids=broken_witness_ids,
        projection_preservation_passed=projection_preservation_passed,
        replay=replay,
    )
    payload_metadata = dict(metadata or {})
    payload_metadata["witness_replay"] = [
        {
            "witness_id": item.witness_id,
            "step_status": item.step_status.value,
            "projection_preserved": item.projection_preserved,
            "current_projection_hash": item.current_projection_hash,
            "reason": item.reason,
        }
        for item in replay
    ]
    payload_metadata["cache_key"] = proof_composability_cache_key(
        query=checked_query,
        theorem_family=str(payload_metadata.get("theorem_family", "")),
        proof_trace_hash=str(payload_metadata.get("proof_trace_hash", "")),
        witness_projection_hashes=tuple(
            witness.projection_hash
            for witness in witness_index.witnesses
            if witness.projection_hash
        ),
        interface_signature=tuple(interface_vars),
    )

    return build_proof_composability_certificate(
        status=status,
        source_fragment_id=source_fragment_id,
        composed_graph_ref=composed_graph_ref,
        checked_query=checked_query,
        proof_trace_ref=proof_trace_ref,
        witness_index_ref=witness_index_ref,
        preserved_witness_ids=preserved_witness_ids,
        broken_witness_ids=broken_witness_ids,
        step_statuses=step_statuses,
        invalidation_reasons=invalidation_reasons,
        interface_vars=tuple(interface_vars),
        new_ancestors=new_ancestors,
        new_district_links=new_district_links,
        projection_preservation_passed=projection_preservation_passed,
        proof_support_projection_hash=witness_index.proof_support_projection_hash,
        invalidated_by_graph_hashes=tuple(invalidated_by_graph_hashes),
        metadata=payload_metadata,
    )


def build_witness_index_from_proof_steps(
    proof_steps: tuple[ProofStep, ...] | list[ProofStep],
    *,
    graph: CausalGraphModel,
    theorem_family: str = "",
    default_mutilation: str = "",
) -> ProofWitnessIndex:
    """Create a conservative witness index for existing IR proof steps."""

    witnesses: list[ProofGraphWitness] = []
    step_to_witness_ids: dict[str, tuple[str, ...]] = {}
    support_hashes: list[str] = []
    for index, step in enumerate(proof_steps):
        step_id = step.step_id or _stable_step_id(step, index=index)
        support_vars = tuple(sorted(set(step.variables_affected)))
        if not support_vars:
            continue
        obligation_kind = _obligation_kind_for_rule(step.rule_name)
        projection_hash = proof_support_projection_hash(
            graph,
            support_vars=support_vars,
            mutilation=default_mutilation,
        )
        support_hashes.append(projection_hash)
        witness_id = f"{step_id}:graph"
        witnesses.append(
            ProofGraphWitness(
                witness_id=witness_id,
                obligation_kind=obligation_kind,
                support_vars=support_vars,
                mutilation=default_mutilation,
                projection_hash=projection_hash,
                ancestor_signature=proof_ancestor_signature(
                    graph,
                    support_vars=support_vars,
                    mutilation=default_mutilation,
                ),
                district_signature=proof_district_signature(
                    graph,
                    support_vars=support_vars,
                    mutilation=default_mutilation,
                ),
                metadata={
                    "rule_name": step.rule_name,
                    "theorem_family": step.theorem_family or theorem_family,
                    "source": "build_witness_index_from_proof_steps",
                },
            )
        )
        step_to_witness_ids[step_id] = (witness_id,)

    return ProofWitnessIndex(
        witnesses=tuple(witnesses),
        step_to_witness_ids=step_to_witness_ids,
        proof_support_projection_hash=_hash_payload(support_hashes),
        metadata={"theorem_family": theorem_family},
    )


def proof_composability_cache_key(
    *,
    query: str,
    theorem_family: str,
    proof_trace_hash: str,
    witness_projection_hashes: tuple[str, ...] | list[str],
    interface_signature: tuple[str, ...] | list[str] | set[str],
) -> str:
    """Return the Stage 2.2 cache key prescribed by the research plan."""

    return "proof-replay:" + _hash_payload(
        {
            "query": query,
            "theorem_family": theorem_family,
            "proof_trace_hash": proof_trace_hash,
            "witness_projection_hashes": sorted(witness_projection_hashes),
            "interface_signature": sorted(interface_signature),
        }
    )


def _resolve_composability_status(
    *,
    step_statuses: dict[str, ProofReplayStepStatus],
    broken_witness_ids: tuple[str, ...],
    projection_preservation_passed: bool | None,
    replay: list[WitnessReplayResult],
) -> ProofComposabilityStatus:
    if broken_witness_ids or any(
        status is ProofReplayStepStatus.INVALID for status in step_statuses.values()
    ):
        return ProofComposabilityStatus.REDERIVE
    if any(item.reason == "unsupported_graph_for_replay" for item in replay):
        return ProofComposabilityStatus.UNKNOWN
    if (
        step_statuses
        and all(status is ProofReplayStepStatus.VALID for status in step_statuses.values())
        and projection_preservation_passed is True
        and all(item.is_preserved for item in replay)
    ):
        return ProofComposabilityStatus.REUSABLE
    if replay:
        return ProofComposabilityStatus.REVALIDATE
    return ProofComposabilityStatus.UNKNOWN


def _recheck_obligation(
    witness: ProofGraphWitness,
    graph: CausalGraphModel,
) -> bool | None:
    if witness.obligation_kind is not ProofObligationKind.M_SEPARATION:
        return None
    statement = _m_separation_statement(witness)
    if statement is None:
        return None
    x_set, y_set, z_set = statement
    mutilated = apply_witness_mutilation(graph, witness.mutilation)
    return m_separation(mutilated, x_set, y_set, z_set)


def _m_separation_statement(
    witness: ProofGraphWitness,
) -> tuple[frozenset[str], frozenset[str], frozenset[str]] | None:
    metadata = dict(witness.metadata or {})
    if {"x_set", "y_set"}.issubset(metadata):
        return (
            frozenset(_coerce_var_tuple(metadata.get("x_set"))),
            frozenset(_coerce_var_tuple(metadata.get("y_set"))),
            frozenset(_coerce_var_tuple(metadata.get("z_set", ()))),
        )
    if not witness.separation_statement:
        return None
    parsed = re.match(
        r"\s*(?P<x>[A-Za-z0-9_, ]+)\s*(?:_|⊥|perp)+\s*(?P<y>[A-Za-z0-9_, ]+)"
        r"(?:\s*\|\s*(?P<z>[A-Za-z0-9_, ]+))?",
        witness.separation_statement,
    )
    if parsed is None:
        return None
    return (
        frozenset(_parse_var_list(parsed.group("x"))),
        frozenset(_parse_var_list(parsed.group("y"))),
        frozenset(_parse_var_list(parsed.group("z") or "")),
    )


def _obligation_kind_for_rule(rule_name: str) -> ProofObligationKind:
    upper = rule_name.upper()
    if upper in {"RULE1", "RULE2", "RULE3", "SIGMA_R1", "SIGMA_R2", "SIGMA_R3"}:
        return ProofObligationKind.M_SEPARATION
    if upper in {"ANCESTRAL_COLLAPSE"}:
        return ProofObligationKind.ANCESTRAL_RESTRICTION
    if "COMPONENT" in upper or "FACTOR" in upper:
        return ProofObligationKind.DISTRICT_FACTORIZATION
    if "HEDGE" in upper:
        return ProofObligationKind.HEDGE_WITNESS
    if "FRONTDOOR" in upper:
        return ProofObligationKind.FRONTDOOR
    if "G_FORMULA" in upper:
        return ProofObligationKind.G_FORMULA
    return ProofObligationKind.ORACLE


def _unsupported_graph(graph: CausalGraphModel) -> bool:
    if graph.graph_type not in {GraphType.DAG, GraphType.ADMG, GraphType.PAG, GraphType.CPDAG}:
        return True
    return any(
        edge.mark_src is EdgeMark.CIRCLE or edge.mark_dst is EdgeMark.CIRCLE for edge in graph.edges
    )


def _new_district_links(
    expected: tuple[tuple[str, ...], ...],
    current: tuple[tuple[str, ...], ...],
) -> tuple[tuple[str, str], ...]:
    expected_pairs = _district_pairs(expected)
    current_pairs = _district_pairs(current)
    return tuple(sorted(current_pairs - expected_pairs))


def _district_pairs(signature: tuple[tuple[str, ...], ...]) -> set[tuple[str, str]]:
    pairs: set[tuple[str, str]] = set()
    for district in signature:
        for left, right in combinations(sorted(district), 2):
            pairs.add((left, right))
    return pairs


def _district_signature_from_components(
    components: list[frozenset[str]],
) -> tuple[tuple[str, ...], ...]:
    return tuple(sorted(tuple(sorted(component)) for component in components if component))


def _normalize_mutilation(value: str) -> str:
    return (
        str(value or "")
        .strip()
        .lower()
        .replace("remove_incoming_edges", "remove_in")
        .replace("remove_outgoing_edges", "remove_out")
        .replace("remove_incoming", "remove_in")
        .replace("remove_outgoing", "remove_out")
    )


def _parse_var_list(value: str) -> tuple[str, ...]:
    return tuple(
        item.strip()
        for item in str(value or "").replace("{", "").replace("}", "").split(",")
        if item.strip()
    )


def _coerce_var_tuple(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return _parse_var_list(value)
    if isinstance(value, (list, tuple, set, frozenset)):
        return tuple(str(item).strip() for item in value if str(item).strip())
    return (str(value).strip(),) if str(value).strip() else ()


def _stable_step_id(step: ProofStep, *, index: int) -> str:
    digest = _hash_payload(
        {
            "index": index,
            "rule_name": step.rule_name,
            "variables_affected": step.variables_affected,
            "graph_state_before": step.graph_state_before,
            "graph_state_after": step.graph_state_after,
        }
    )[:12]
    return f"step_{index:04d}_{digest}"


def _hash_payload(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


__all__ = [
    "WitnessReplayResult",
    "apply_witness_mutilation",
    "build_witness_index_from_proof_steps",
    "check_proof_trace_composability",
    "proof_ancestor_signature",
    "proof_composability_cache_key",
    "proof_district_signature",
    "proof_support_projection_hash",
    "replay_graph_witness",
]
