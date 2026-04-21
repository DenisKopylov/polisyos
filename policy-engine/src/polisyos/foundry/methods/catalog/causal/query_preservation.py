"""Audit whether graph abstractions preserve the target causal query."""
from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from functools import lru_cache
from itertools import combinations
from typing import Literal

from polisyos.foundry.methods.catalog.causal.admg_ops import (
    ancestors,
    d_separation,
    descendants,
    has_directed_cycle,
    induced_subgraph,
    m_separation,
    remove_outgoing_edges,
)
from polisyos.foundry.methods.catalog.causal.cyclic_id import sigma_separation
from polisyos.foundry.methods.catalog.causal.id_engine import (
    IdentificationStatus,
    id_algorithm,
    idc_algorithm,
)
from polisyos.ir.analytics.causal_graph import (
    CausalEdge,
    CausalGraphModel,
    EdgeMark,
    EdgeSource,
    GraphType,
)
from polisyos.ir.analytics.causal_queries import CausalQuery, QueryType
from polisyos.ir.analytics.cross_graph import (
    CompositionCertificate,
    InterfaceMapping,
    QueryPreservationCertificate,
    SCMFragment,
)
from polisyos.ir.analytics.negative_certificate import BlockingType, NegativeCertificate

QueryPreservationStatus = Literal["preserved", "broken", "unknown"]


@dataclass(frozen=True)
class _ResolvedVariable:
    composed_node: str | None
    local_nodes: dict[str, str]


@dataclass(frozen=True)
class _GraphicalObligation:
    kind: Literal["backdoor_adjustment"]
    treatment: str
    outcome: str
    conditioning: frozenset[str]


@dataclass(frozen=True)
class GraphicalObligationTrace:
    """Record which graphical obligations were checked while preserving a causal query."""
    kind: str
    treatment: str
    outcome: str
    conditioning: tuple[str, ...]
    criterion: str = ""
    holds_in_source: bool | None = None
    holds_in_composed: bool | None = None


@dataclass(frozen=True)
class QueryPreservationTrace:
    """Capture pass/fail status and obligation traces for an abstraction-preservation check."""
    fingerprint: str
    status: QueryPreservationStatus
    reason_code: str
    source_fragment_id: str | None = None
    query_semantics: str = ""
    obligations_checked: tuple[GraphicalObligationTrace, ...] = ()
    witness_fragment_ids: tuple[str, ...] = ()
    source_witness_kind: str = ""
    assumption_boundary: str | None = None
    theorem_family: str | None = None
    identification_status: str | None = None
    identification_method: str | None = None
    identification_trace: tuple[str, ...] = ()
    latent_projection_graph: CausalGraphModel | None = None
    latent_projection_signature: dict[str, object] | None = None
    identifying_estimand: dict[str, object] | None = None
    required_distributions: tuple[dict[str, object], ...] = ()
    positive_witness: dict[str, object] | None = None
    hedge_witness: dict[str, object] | None = None


@dataclass(frozen=True)
class _LatentProjectionContext:
    graph: CausalGraphModel
    hidden_nodes: frozenset[str]
    binding_to_node: Mapping[tuple[str, str], str]


def check_query_preservation(
    query: CausalQuery,
    *,
    composed_graph: CausalGraphModel,
    fragments: Sequence[SCMFragment] | None,
    fragment_graphs: Mapping[str, CausalGraphModel] | None,
    interface_mapping: InterfaceMapping,
    composition_certificate: CompositionCertificate,
) -> QueryPreservationStatus:
    """Return whether a composed graph still preserves the semantics of one causal query."""
    evaluation = _evaluate_query_preservation(
        query,
        composed_graph=composed_graph,
        fragments=fragments or (),
        fragment_graphs=fragment_graphs or {},
        interface_mapping=interface_mapping,
        composition_certificate=composition_certificate,
    )
    return evaluation.status


def check_query_preservation_batch(
    queries: Sequence[CausalQuery],
    *,
    composed_graph: CausalGraphModel,
    fragments: Sequence[SCMFragment] | None,
    fragment_graphs: Mapping[str, CausalGraphModel] | None,
    interface_mapping: InterfaceMapping,
    composition_certificate: CompositionCertificate,
) -> dict[str, QueryPreservationStatus]:
    """Evaluate preservation status for a batch of causal queries keyed by fingerprint."""
    evaluations = evaluate_query_preservation_batch(
        queries,
        composed_graph=composed_graph,
        fragments=fragments or (),
        fragment_graphs=fragment_graphs or {},
        interface_mapping=interface_mapping,
        composition_certificate=composition_certificate,
    )
    return {
        fingerprint: evaluation.status
        for fingerprint, evaluation in sorted(evaluations.items())
    }


def evaluate_query_preservation(
    query: CausalQuery,
    *,
    composed_graph: CausalGraphModel,
    fragments: Sequence[SCMFragment] | None,
    fragment_graphs: Mapping[str, CausalGraphModel] | None,
    interface_mapping: InterfaceMapping,
    composition_certificate: CompositionCertificate,
) -> QueryPreservationTrace:
    """Produce a full preservation trace explaining why a causal query passed or failed."""
    return _evaluate_query_preservation(
        query,
        composed_graph=composed_graph,
        fragments=fragments or (),
        fragment_graphs=fragment_graphs or {},
        interface_mapping=interface_mapping,
        composition_certificate=composition_certificate,
    )


def evaluate_query_preservation_batch(
    queries: Sequence[CausalQuery],
    *,
    composed_graph: CausalGraphModel,
    fragments: Sequence[SCMFragment] | None,
    fragment_graphs: Mapping[str, CausalGraphModel] | None,
    interface_mapping: InterfaceMapping,
    composition_certificate: CompositionCertificate,
) -> dict[str, QueryPreservationTrace]:
    """Produce preservation traces for many queries in one composed-graph audit."""
    evaluations = [
        _evaluate_query_preservation(
            query,
            composed_graph=composed_graph,
            fragments=fragments or (),
            fragment_graphs=fragment_graphs or {},
            interface_mapping=interface_mapping,
            composition_certificate=composition_certificate,
        )
        for query in queries
    ]
    return {evaluation.fingerprint: evaluation for evaluation in evaluations}


def update_query_preservation_cache(
    composition_certificate: CompositionCertificate,
    *,
    queries: Sequence[CausalQuery],
    composed_graph: CausalGraphModel,
    fragments: Sequence[SCMFragment] | None,
    fragment_graphs: Mapping[str, CausalGraphModel] | None,
    interface_mapping: InterfaceMapping,
) -> tuple[CompositionCertificate, dict[str, QueryPreservationStatus]]:
    """Persist fresh preservation statuses back onto a composition certificate cache."""
    checked = dict(composition_certificate.checked_queries)
    certificates = dict(composition_certificate.query_certificates)
    evaluations = list(
        evaluate_query_preservation_batch(
            queries,
            composed_graph=composed_graph,
            fragments=fragments or (),
            fragment_graphs=fragment_graphs or {},
            interface_mapping=interface_mapping,
            composition_certificate=composition_certificate,
        ).values()
    )
    for evaluation in evaluations:
        checked[evaluation.fingerprint] = evaluation.status
        existing_negative_ref = None
        existing_projection_ref = None
        existing_record = certificates.get(evaluation.fingerprint)
        if existing_record is not None:
            existing_negative_ref = existing_record.negative_certificate_ref
            existing_projection_ref = existing_record.latent_projection_ref
        certificates[evaluation.fingerprint] = _trace_to_query_certificate(
            evaluation,
            negative_certificate_ref=existing_negative_ref,
            latent_projection_ref=existing_projection_ref,
        )

    updated_certificate = composition_certificate.model_copy(
        update={
            "checked_queries": dict(sorted(checked.items())),
            "query_certificates": dict(sorted(certificates.items())),
        }
    )
    return (
        updated_certificate,
        {
            evaluation.fingerprint: evaluation.status
            for evaluation in sorted(evaluations, key=lambda item: item.fingerprint)
        },
    )


def update_query_preservation_artifact_refs(
    composition_certificate: CompositionCertificate,
    *,
    latent_projection_refs: Mapping[str, str] | None = None,
    negative_certificate_refs: Mapping[str, str] | None = None,
) -> CompositionCertificate:
    """Attach persisted artifact refs to cached per-query preservation certificates."""
    if not composition_certificate.query_certificates:
        return composition_certificate

    projection_refs = dict(latent_projection_refs or {})
    negative_refs = dict(negative_certificate_refs or {})
    updated_records: dict[str, QueryPreservationCertificate] = {}
    changed = False
    for fingerprint, record in sorted(composition_certificate.query_certificates.items()):
        update_payload: dict[str, object] = {}
        projection_ref = projection_refs.get(fingerprint)
        negative_ref = negative_refs.get(fingerprint)
        if projection_ref is not None and record.latent_projection_ref != projection_ref:
            update_payload["latent_projection_ref"] = projection_ref
        if negative_ref is not None and record.negative_certificate_ref != negative_ref:
            update_payload["negative_certificate_ref"] = negative_ref
        updated_records[fingerprint] = (
            record.model_copy(update=update_payload) if update_payload else record
        )
        changed = changed or bool(update_payload)

    if not changed:
        return composition_certificate
    return composition_certificate.model_copy(update={"query_certificates": updated_records})


def _evaluate_query_preservation(
    query: CausalQuery,
    *,
    composed_graph: CausalGraphModel,
    fragments: Sequence[SCMFragment],
    fragment_graphs: Mapping[str, CausalGraphModel],
    interface_mapping: InterfaceMapping,
    composition_certificate: CompositionCertificate,
) -> QueryPreservationTrace:
    fragment_index = {fragment.fragment_id: fragment for fragment in fragments}
    composed_graph = _attach_cycle_contract_metadata(
        composed_graph,
        cycle_contracts=composition_certificate.metadata.get("cycle_contracts", []),
    )
    fingerprint = _query_fingerprint(
        query=query,
        composed_graph=composed_graph,
        fragments=fragments,
        fragment_graphs=fragment_graphs,
        interface_mapping=interface_mapping,
        composition_certificate=composition_certificate,
    )
    cached = composition_certificate.checked_queries.get(fingerprint)
    if cached is not None:
        cached_record = composition_certificate.query_certificates.get(fingerprint)
        if cached_record is not None:
            return _trace_from_query_certificate(
                fingerprint=fingerprint,
                certificate=cached_record,
            )
        return QueryPreservationTrace(
            fingerprint=fingerprint,
            status=cached,
            reason_code="cached",
            query_semantics=_query_semantics(query),
        )

    obligations = _graphical_obligations_for_query(query)
    if not obligations:
        return QueryPreservationTrace(
            fingerprint=fingerprint,
            status="unknown",
            reason_code="unsupported_query_type",
            query_semantics=_query_semantics(query),
        )

    query_variables = sorted(
        {
            obligation.treatment
            for obligation in obligations
        }
        | {
            obligation.outcome
            for obligation in obligations
        }
        | {
            variable
            for obligation in obligations
            for variable in obligation.conditioning
        }
    )

    if _has_latent_bridge_entries(interface_mapping):
        return _evaluate_latent_projection_preservation(
            query,
            fingerprint=fingerprint,
            query_semantics=_query_semantics(query),
            query_variables=query_variables,
            fragment_graphs=fragment_graphs,
            interface_mapping=interface_mapping,
        )

    resolutions = _build_variable_resolutions(
        query_variables=query_variables,
        composed_graph=composed_graph,
        fragment_graphs=fragment_graphs,
        interface_mapping=interface_mapping,
    )
    if set(query_variables) - set(resolutions):
        return QueryPreservationTrace(
            fingerprint=fingerprint,
            status="unknown",
            reason_code="unresolved_query_variable",
            query_semantics=_query_semantics(query),
        )

    composed_obligations = _resolve_composed_obligations(obligations, resolutions)
    if composed_obligations is None:
        return QueryPreservationTrace(
            fingerprint=fingerprint,
            status="unknown",
            reason_code="unresolved_composed_node",
            query_semantics=_query_semantics(query),
        )

    fragment_ids = sorted(fragment_graphs)
    topology = _fragment_topology(
        fragment_ids=fragment_ids,
        interface_mapping=interface_mapping,
        composition_certificate=composition_certificate,
    )

    obligation_traces: list[GraphicalObligationTrace] = []
    witness_sets: list[tuple[str, ...]] = []
    witness_kind = ""
    source_fragment_id: str | None = None

    for obligation, composed_obligation in zip(obligations, composed_obligations, strict=False):
        witness_candidates = _candidate_witness_fragment_sets(
            obligation=obligation,
            resolutions=resolutions,
            fragment_ids=fragment_ids,
            topology=topology,
        )
        if not witness_candidates:
            return QueryPreservationTrace(
                fingerprint=fingerprint,
                status="unknown",
                reason_code="missing_obligation_witness",
                query_semantics=_query_semantics(query),
                obligations_checked=tuple(obligation_traces),
                witness_fragment_ids=tuple(sorted({item for group in witness_sets for item in group})),
            )

        evaluated_candidates: list[tuple[tuple[str, ...], GraphicalObligationTrace, str | None]] = []
        for witness_fragment_ids in witness_candidates:
            witness_graph = _build_witness_graph(
                witness_fragment_ids=witness_fragment_ids,
                fragment_graphs=fragment_graphs,
                interface_mapping=interface_mapping,
                fragments=fragment_index,
            )
            if witness_graph is None:
                continue
            holds_in_source, source_criterion = _obligation_evaluation(
                witness_graph,
                composed_obligation,
            )
            holds_in_composed, composed_criterion = _obligation_evaluation(
                composed_graph,
                composed_obligation,
            )
            evaluated_candidates.append(
                (
                    witness_fragment_ids,
                    GraphicalObligationTrace(
                        kind=composed_obligation.kind,
                        treatment=composed_obligation.treatment,
                        outcome=composed_obligation.outcome,
                        conditioning=tuple(sorted(composed_obligation.conditioning)),
                        criterion=source_criterion or composed_criterion,
                        holds_in_source=holds_in_source,
                        holds_in_composed=holds_in_composed,
                    ),
                    _assumption_boundary_for_obligation(
                        obligation=composed_obligation,
                        witness_graph=witness_graph,
                        composed_graph=composed_graph,
                        interface_mapping=interface_mapping,
                    ),
                )
            )

        if not evaluated_candidates:
            return QueryPreservationTrace(
                fingerprint=fingerprint,
                status="unknown",
                reason_code="missing_obligation_witness",
                query_semantics=_query_semantics(query),
                obligations_checked=tuple(obligation_traces),
                witness_fragment_ids=tuple(sorted({item for group in witness_sets for item in group})),
            )

        supporting_candidates = [
            item for item in evaluated_candidates if item[1].holds_in_source is True
        ]
        if supporting_candidates:
            chosen_witness, obligation_trace, assumption_boundary = next(
                (
                    item
                    for item in supporting_candidates
                    if item[2] is None
                ),
                supporting_candidates[0],
            )
        else:
            chosen_witness, obligation_trace, assumption_boundary = evaluated_candidates[0]

        witness_fragment_ids = chosen_witness
        witness_sets.append(witness_fragment_ids)
        obligation_traces.append(obligation_trace)

        if obligation_trace.holds_in_source is not True:
            combined_witness = tuple(sorted({item for group in witness_sets for item in group}))
            return QueryPreservationTrace(
                fingerprint=fingerprint,
                status="unknown",
                reason_code="source_obligation_not_supported",
                source_fragment_id=witness_fragment_ids[0] if len(witness_fragment_ids) == 1 else None,
                query_semantics=_query_semantics(query),
                obligations_checked=tuple(obligation_traces),
                witness_fragment_ids=combined_witness,
                source_witness_kind=_witness_kind(combined_witness),
            )

        if assumption_boundary is not None:
            combined_witness = tuple(sorted({item for group in witness_sets for item in group}))
            reason_code = (
                _latent_bridge_boundary_reason(interface_mapping)
                if assumption_boundary == "latent_bridge"
                else "latent_bridge_research_boundary"
            )
            return QueryPreservationTrace(
                fingerprint=fingerprint,
                status="unknown",
                reason_code=reason_code,
                source_fragment_id=witness_fragment_ids[0] if len(witness_fragment_ids) == 1 else None,
                query_semantics=_query_semantics(query),
                obligations_checked=tuple(obligation_traces),
                witness_fragment_ids=combined_witness,
                source_witness_kind=_witness_kind(combined_witness),
                assumption_boundary=assumption_boundary,
            )

        if obligation_trace.holds_in_composed is not True:
            combined_witness = tuple(sorted({item for group in witness_sets for item in group}))
            return QueryPreservationTrace(
                fingerprint=fingerprint,
                status="broken",
                reason_code="obligation_broken_after_composition",
                source_fragment_id=witness_fragment_ids[0] if len(witness_fragment_ids) == 1 else None,
                query_semantics=_query_semantics(query),
                obligations_checked=tuple(obligation_traces),
                witness_fragment_ids=combined_witness,
                source_witness_kind=_witness_kind(combined_witness),
            )

        if not witness_kind:
            witness_kind = _witness_kind(witness_fragment_ids)
        if source_fragment_id is None and len(witness_fragment_ids) == 1:
            source_fragment_id = witness_fragment_ids[0]

    combined_witness = tuple(sorted({item for group in witness_sets for item in group}))
    return QueryPreservationTrace(
        fingerprint=fingerprint,
        status="preserved",
        reason_code="evaluated",
        source_fragment_id=source_fragment_id if len(combined_witness) == 1 else None,
        query_semantics=_query_semantics(query),
        obligations_checked=tuple(obligation_traces),
        witness_fragment_ids=combined_witness,
        source_witness_kind=_witness_kind(combined_witness),
    )


def _evaluate_latent_projection_preservation(
    query: CausalQuery,
    *,
    fingerprint: str,
    query_semantics: str,
    query_variables: Sequence[str],
    fragment_graphs: Mapping[str, CausalGraphModel],
    interface_mapping: InterfaceMapping,
) -> QueryPreservationTrace:
    if query.query_type is QueryType.SOFT_INTERVENTION:
        return QueryPreservationTrace(
            fingerprint=fingerprint,
            status="unknown",
            reason_code="latent_projection_soft_intervention_out_of_scope",
            query_semantics=query_semantics,
            assumption_boundary="latent_bridge",
        )
    if query.query_type is not QueryType.INTERVENTIONAL:
        return QueryPreservationTrace(
            fingerprint=fingerprint,
            status="unknown",
            reason_code="unsupported_query_type",
            query_semantics=query_semantics,
            assumption_boundary="latent_bridge",
        )
    if query.intervention_spec is not None:
        return QueryPreservationTrace(
            fingerprint=fingerprint,
            status="unknown",
            reason_code="latent_projection_non_atomic_intervention_out_of_scope",
            query_semantics=query_semantics,
            assumption_boundary="latent_bridge",
        )

    projection = _build_composed_latent_projection(
        fragment_graphs=fragment_graphs,
        interface_mapping=interface_mapping,
    )
    if projection is None:
        return QueryPreservationTrace(
            fingerprint=fingerprint,
            status="unknown",
            reason_code="latent_projection_out_of_scope",
            query_semantics=query_semantics,
            assumption_boundary="latent_bridge",
        )
    if isinstance(projection, str):
        return QueryPreservationTrace(
            fingerprint=fingerprint,
            status="unknown",
            reason_code=projection,
            query_semantics=query_semantics,
            assumption_boundary="latent_bridge",
        )

    resolutions = _build_latent_projection_resolutions(
        query_variables=query_variables,
        projection=projection,
        fragment_graphs=fragment_graphs,
        interface_mapping=interface_mapping,
    )
    if set(query_variables) - set(resolutions):
        return QueryPreservationTrace(
            fingerprint=fingerprint,
            status="unknown",
            reason_code="latent_projection_unresolved_query_variable",
            query_semantics=query_semantics,
            assumption_boundary="latent_bridge",
            latent_projection_graph=projection.graph,
            latent_projection_signature=_graph_signature(projection.graph),
        )

    treatment = resolutions[query.treatment_variable].composed_node
    outcome = resolutions[query.outcome_variable].composed_node
    condition_nodes = {
        resolutions[variable].composed_node
        for variable in query.condition
    }
    if treatment is None or outcome is None or None in condition_nodes:
        return QueryPreservationTrace(
            fingerprint=fingerprint,
            status="unknown",
            reason_code="latent_projection_unresolved_query_variable",
            query_semantics=query_semantics,
            assumption_boundary="latent_bridge",
            latent_projection_graph=projection.graph,
            latent_projection_signature=_graph_signature(projection.graph),
        )

    involved_fragments = tuple(
        sorted(
            {
                fragment_id
                for resolution in resolutions.values()
                for fragment_id in resolution.local_nodes
            }
        )
    )
    witness_kind = _witness_kind(involved_fragments) if involved_fragments else ""
    latent_projection_signature = _graph_signature(projection.graph)
    try:
        if condition_nodes:
            result = idc_algorithm(
                treatment=frozenset({treatment}),
                outcome=frozenset({outcome}),
                conditions=frozenset(str(node) for node in condition_nodes if node),
                graph=projection.graph,
            )
        else:
            result = id_algorithm(
                treatment=frozenset({treatment}),
                outcome=frozenset({outcome}),
                graph=projection.graph,
            )
    except Exception:
        return QueryPreservationTrace(
            fingerprint=fingerprint,
            status="unknown",
            reason_code="latent_projection_execution_failed",
            query_semantics=query_semantics,
            witness_fragment_ids=involved_fragments,
            source_witness_kind=witness_kind,
            assumption_boundary="latent_bridge",
            latent_projection_graph=projection.graph,
            latent_projection_signature=latent_projection_signature,
        )

    identification_method = (
        result.estimand_ast.identification_method
        if result.estimand_ast is not None
        else None
    )
    source_fragment_id = involved_fragments[0] if len(involved_fragments) == 1 else None
    identifying_estimand = (
        result.estimand_ast.model_dump(mode="json")
        if result.estimand_ast is not None and hasattr(result.estimand_ast, "model_dump")
        else None
    )
    required_distributions = _serialize_required_distributions(result)
    positive_witness = _positive_witness_for_identified_result(result)
    adjustment_witness = _find_adjustment_witness(
        projection.graph,
        treatment=treatment,
        outcome=outcome,
        required_conditioning=frozenset(str(node) for node in condition_nodes if node),
    )
    if (
        result.status is IdentificationStatus.IDENTIFIED
        and adjustment_witness is not None
        and not str(identification_method or "").strip().lower().startswith("frontdoor")
    ):
        positive_witness = {"adjustment_set": [_pretty_query_node(item) for item in adjustment_witness]}
        if str(identification_method or "").strip().lower() not in {"backdoor", "idc"}:
            identification_method = "backdoor"
    theorem_family = _theorem_family_for_identification_method(identification_method)

    if result.status is IdentificationStatus.IDENTIFIED:
        return QueryPreservationTrace(
            fingerprint=fingerprint,
            status="preserved",
            reason_code="latent_projection_exact_identified",
            source_fragment_id=source_fragment_id,
            query_semantics=query_semantics,
            witness_fragment_ids=involved_fragments,
            source_witness_kind=witness_kind,
            theorem_family=theorem_family,
            identification_status=result.status.value,
            identification_method=identification_method,
            identification_trace=tuple(result.trace),
            latent_projection_graph=projection.graph,
            latent_projection_signature=latent_projection_signature,
            identifying_estimand=identifying_estimand,
            required_distributions=required_distributions,
            positive_witness=positive_witness,
        )

    if result.status is IdentificationStatus.HEDGE_FOUND and result.hedge_certificate is not None:
        cert = result.hedge_certificate
        return QueryPreservationTrace(
            fingerprint=fingerprint,
            status="broken",
            reason_code="latent_projection_hedge_found",
            source_fragment_id=source_fragment_id,
            query_semantics=query_semantics,
            witness_fragment_ids=involved_fragments,
            source_witness_kind=witness_kind,
            theorem_family=theorem_family,
            identification_status=result.status.value,
            identification_method=identification_method,
            identification_trace=tuple(result.trace),
            latent_projection_graph=projection.graph,
            latent_projection_signature=latent_projection_signature,
            identifying_estimand=identifying_estimand,
            required_distributions=required_distributions,
            hedge_witness={
                "treatment": tuple(sorted(cert.treatment)),
                "outcome": tuple(sorted(cert.outcome)),
                "hedge_forest": tuple(sorted(cert.hedge_forest)),
                "hedge_root": tuple(sorted(cert.hedge_root)),
                "c_component_witness": tuple(sorted(cert.c_component_witness)),
            },
        )

    return QueryPreservationTrace(
        fingerprint=fingerprint,
        status="unknown",
        reason_code=f"latent_projection_{result.status.value}",
        source_fragment_id=source_fragment_id,
        query_semantics=query_semantics,
        witness_fragment_ids=involved_fragments,
        source_witness_kind=witness_kind,
        assumption_boundary="latent_bridge",
        theorem_family=theorem_family,
        identification_status=result.status.value,
        identification_method=identification_method,
        identification_trace=tuple(result.trace),
        latent_projection_graph=projection.graph,
        latent_projection_signature=latent_projection_signature,
        identifying_estimand=identifying_estimand,
        required_distributions=required_distributions,
    )


def _graphical_obligations_for_query(query: CausalQuery) -> tuple[_GraphicalObligation, ...]:
    if query.query_type not in {QueryType.INTERVENTIONAL, QueryType.SOFT_INTERVENTION}:
        return ()
    treatment = str(query.treatment_variable).strip()
    outcome = str(query.outcome_variable).strip()
    conditioning = frozenset(
        str(variable).strip()
        for variable in query.condition
        if str(variable).strip()
    )
    if not treatment or not outcome or treatment == outcome:
        return ()
    return (
        _GraphicalObligation(
            kind="backdoor_adjustment",
            treatment=treatment,
            outcome=outcome,
            conditioning=conditioning,
        ),
    )


def _query_semantics(query: CausalQuery) -> str:
    if query.intervention_spec is not None:
        return f"{query.query_type.value}:{query.intervention_spec.type.value}"
    return query.query_type.value


def _fragment_cycle_contract_summary(fragment: SCMFragment) -> dict[str, object]:
    return {
        "fragment_id": fragment.fragment_id,
        "cycle_type": fragment.cycle_type.value,
        "cycle_scope": fragment.cycle_scope.value,
        "composition_policy": fragment.composition_policy.value,
        "graph_audit_guarantee": fragment.graph_audit_guarantee.value,
        "allowed_alignment_types": list(fragment.allowed_alignment_types),
        "witnesses": [
            {
                "scc_id": witness.scc_id,
                "solver_kind": witness.solver_kind.value,
                "uniqueness_scope": witness.uniqueness_scope.value,
                "interventional_closure": witness.interventional_closure.value,
                "markov_semantics": witness.markov_semantics.value,
                "initial_condition_dependent": witness.initial_condition_dependent,
            }
            for witness in fragment.cycle_witnesses
        ],
    }


def _cycle_semantics_mode_from_contracts(
    cycle_contracts: Sequence[Mapping[str, object]],
) -> str:
    non_acyclic = [
        contract
        for contract in cycle_contracts
        if str(contract.get("cycle_type", "")).strip() not in {"", "acyclic"}
    ]
    if not non_acyclic:
        return "none"
    if all(
        str(witness.get("markov_semantics", "")).strip() == "sigma_separation"
        for contract in non_acyclic
        for witness in contract.get("witnesses", [])
        if isinstance(witness, Mapping)
    ):
        return "sigma_separation"
    return "none"


def _attach_cycle_contract_metadata(
    graph: CausalGraphModel,
    *,
    cycle_contracts: Sequence[Mapping[str, object]],
) -> CausalGraphModel:
    contracts = [dict(contract) for contract in cycle_contracts if isinstance(contract, Mapping)]
    if not contracts:
        return graph
    metadata = dict(graph.metadata)
    if not metadata.get("cycle_contracts"):
        metadata["cycle_contracts"] = contracts
    metadata.setdefault(
        "supported_cycle_fragment_ids",
        sorted(
            str(contract.get("fragment_id", "")).strip()
            for contract in contracts
            if str(contract.get("cycle_type", "")).strip() not in {"", "acyclic"}
        ),
    )
    metadata.setdefault(
        "cycle_semantics_mode",
        _cycle_semantics_mode_from_contracts(contracts),
    )
    return graph.model_copy(update={"metadata": metadata})


def negative_certificate_from_query_preservation_trace(
    query: CausalQuery,
    trace: QueryPreservationTrace,
) -> NegativeCertificate | None:
    """Convert an exact latent-interface failure into a typed impossibility artifact."""
    if trace.status != "broken":
        return None
    if trace.reason_code != "latent_projection_hedge_found":
        return None

    treatment = str(query.treatment_variable).strip()
    outcome = str(query.outcome_variable).strip()
    expression = _query_expression(query)
    witness = trace.hedge_witness or {}
    hedge_forest = tuple(str(item) for item in witness.get("hedge_forest", ()))
    hedge_root = tuple(str(item) for item in witness.get("hedge_root", ()))
    c_component = tuple(str(item) for item in witness.get("c_component_witness", ()))
    technical_detail = ""
    if hedge_forest or hedge_root:
        technical_detail = f"Hedge: F={list(hedge_forest)}, F'={list(hedge_root)}"

    suggested = NegativeCertificate.auto_suggest_experiments(
        BlockingType.HEDGE_STRUCTURE,
        missing_vars=tuple(sorted({treatment} - {""})),
    )
    return NegativeCertificate(
        blocking_type=BlockingType.HEDGE_STRUCTURE,
        blocking_description=(
            "Latent-interface composition breaks exact identifiability for "
            f"{expression}. The composed latent projection contains a hedge witness."
        ),
        technical_detail=technical_detail,
        required_distributions=tuple(trace.required_distributions),
        suggested_experiments=suggested,
        quantitative_diagnostics={
            "identification_status": trace.identification_status,
            "algorithm_version": trace.theorem_family or "latent_projection_exact",
            "proof_trace": list(trace.identification_trace),
            "query_preservation_reason": trace.reason_code,
            "hedge_forest_size": len(hedge_forest),
            "hedge_root_size": len(hedge_root),
            "c_component_size": len(c_component),
            "witness_fragment_count": len(trace.witness_fragment_ids),
        },
        constructive_message=(
            "Re-identify the query on the composed latent projection, or break the latent "
            "confounding path with a valid experiment, instrument, front-door mediator, "
            "or stronger proxy/proximal assumptions."
        ),
    )


def _query_expression(query: CausalQuery) -> str:
    treatment = str(query.treatment_variable).strip()
    outcome = str(query.outcome_variable).strip()
    if query.condition:
        conditions = ", ".join(sorted(str(item).strip() for item in query.condition))
        return f"P({outcome} | do({treatment}), {conditions})"
    return f"P({outcome} | do({treatment}))"


def _trace_to_query_certificate(
    trace: QueryPreservationTrace,
    *,
    negative_certificate_ref: str | None = None,
    latent_projection_ref: str | None = None,
) -> QueryPreservationCertificate:
    return QueryPreservationCertificate(
        status=trace.status,
        reason_code=trace.reason_code,
        query_semantics=trace.query_semantics,
        source_fragment_id=trace.source_fragment_id,
        witness_fragment_ids=list(trace.witness_fragment_ids),
        source_witness_kind=trace.source_witness_kind,
        assumption_boundary=trace.assumption_boundary,
        theorem_family=trace.theorem_family,
        identification_status=trace.identification_status,
        identification_method=trace.identification_method,
        identification_trace=list(trace.identification_trace),
        obligations_checked=[
            {
                "kind": obligation.kind,
                "treatment": obligation.treatment,
                "outcome": obligation.outcome,
                "conditioning": list(obligation.conditioning),
                "criterion": obligation.criterion,
                "holds_in_source": obligation.holds_in_source,
                "holds_in_composed": obligation.holds_in_composed,
            }
            for obligation in trace.obligations_checked
        ],
        latent_projection_signature=(
            trace.latent_projection_signature
            if trace.latent_projection_signature is not None
            else _graph_signature(trace.latent_projection_graph)
            if trace.latent_projection_graph is not None
            else None
        ),
        latent_projection_ref=latent_projection_ref,
        identifying_estimand=trace.identifying_estimand,
        required_distributions=[dict(item) for item in trace.required_distributions],
        positive_witness=trace.positive_witness,
        hedge_witness=trace.hedge_witness,
        negative_certificate_ref=negative_certificate_ref,
        metadata={"fingerprint": trace.fingerprint},
    )


def _trace_from_query_certificate(
    *,
    fingerprint: str,
    certificate: QueryPreservationCertificate,
) -> QueryPreservationTrace:
    return QueryPreservationTrace(
        fingerprint=fingerprint,
        status=certificate.status,
        reason_code=certificate.reason_code,
        source_fragment_id=certificate.source_fragment_id,
        query_semantics=certificate.query_semantics,
        obligations_checked=tuple(
            GraphicalObligationTrace(
                kind=str(item.get("kind", "")),
                treatment=str(item.get("treatment", "")),
                outcome=str(item.get("outcome", "")),
                conditioning=tuple(str(token) for token in item.get("conditioning", [])),
                criterion=str(item.get("criterion", "")),
                holds_in_source=(
                    bool(item["holds_in_source"])
                    if item.get("holds_in_source") is not None
                    else None
                ),
                holds_in_composed=(
                    bool(item["holds_in_composed"])
                    if item.get("holds_in_composed") is not None
                    else None
                ),
            )
            for item in certificate.obligations_checked
        ),
        witness_fragment_ids=tuple(certificate.witness_fragment_ids),
        source_witness_kind=certificate.source_witness_kind,
        assumption_boundary=certificate.assumption_boundary,
        theorem_family=certificate.theorem_family,
        identification_status=certificate.identification_status,
        identification_method=certificate.identification_method,
        identification_trace=tuple(certificate.identification_trace),
        latent_projection_signature=(
            dict(certificate.latent_projection_signature)
            if certificate.latent_projection_signature is not None
            else None
        ),
        identifying_estimand=(
            dict(certificate.identifying_estimand)
            if certificate.identifying_estimand is not None
            else None
        ),
        required_distributions=tuple(dict(item) for item in certificate.required_distributions),
        positive_witness=(
            dict(certificate.positive_witness)
            if certificate.positive_witness is not None
            else None
        ),
        hedge_witness=(
            dict(certificate.hedge_witness)
            if certificate.hedge_witness is not None
            else None
        ),
    )


def _serialize_required_distributions(result: object) -> tuple[dict[str, object], ...]:
    raw_items = getattr(result, "required_distributions", []) or []
    serialized: list[dict[str, object]] = []
    for item in raw_items:
        if hasattr(item, "model_dump"):
            serialized.append(item.model_dump(mode="json"))
        elif isinstance(item, dict):
            serialized.append(dict(item))
    return tuple(serialized)


def _positive_witness_for_identified_result(result: object) -> dict[str, object] | None:
    estimand_ast = getattr(result, "estimand_ast", None)
    identification_method = (
        str(getattr(estimand_ast, "identification_method", "") or "").strip().lower()
    )
    treatment = str(getattr(estimand_ast, "treatment", "") or "").strip()
    outcome = str(getattr(estimand_ast, "outcome", "") or "").strip()
    all_variables = tuple(str(item) for item in (getattr(estimand_ast, "all_variables", ()) or ()))

    if identification_method == "frontdoor":
        mediators = sorted(
            {
                _pretty_query_node(item)
                for item in all_variables
                if item not in {treatment, outcome}
            }
        )
        return {"mediators": mediators}
    if identification_method == "backdoor":
        adjustment_set = sorted(
            {
                _pretty_query_node(item)
                for item in all_variables
                if item not in {treatment, outcome}
            }
        )
        return {"adjustment_set": adjustment_set}
    if identification_method == "proxy_adjustment":
        proxy_variables = sorted(
            {
                _pretty_query_node(item)
                for item in all_variables
                if item not in {treatment, outcome}
            }
        )
        return {"proxy_variables": proxy_variables}
    if identification_method == "idc":
        return {"conditional_query": True}
    return None


def _pretty_query_node(node: str) -> str:
    token = str(node).strip()
    if token.startswith("stitched::"):
        parts = token.split("::")
        if len(parts) >= 2 and parts[1]:
            return parts[1]
    if "::" in token:
        _, local_name = token.split("::", 1)
        if local_name:
            return local_name
    return token


def _find_adjustment_witness(
    graph: CausalGraphModel,
    *,
    treatment: str,
    outcome: str,
    required_conditioning: frozenset[str] = frozenset(),
) -> tuple[str, ...] | None:
    if graph.graph_type not in {GraphType.DAG, GraphType.ADMG}:
        return None
    graph_nodes = set(graph.nodes)
    if not {treatment, outcome}.issubset(graph_nodes):
        return None
    if not required_conditioning.issubset(graph_nodes):
        return None

    forbidden = descendants(graph, frozenset({treatment}), include_self=False)
    candidate_pool = sorted(graph_nodes - {treatment, outcome} - forbidden)
    required = tuple(sorted(required_conditioning))
    optional = [node for node in candidate_pool if node not in required_conditioning]
    if len(optional) > 12:
        return None

    common_ancestors = tuple(
        sorted(
            (
                ancestors(graph, frozenset({treatment}), include_self=False)
                & ancestors(graph, frozenset({outcome}), include_self=False)
                & set(candidate_pool)
            )
        )
    )
    if common_ancestors:
        preferred_conditioning = frozenset({*required, *common_ancestors})
        if _obligation_holds(
            graph,
            _GraphicalObligation(
                kind="backdoor_adjustment",
                treatment=treatment,
                outcome=outcome,
                conditioning=preferred_conditioning,
            ),
        ):
            return tuple(sorted(preferred_conditioning))

    for size in range(len(optional) + 1):
        for subset in combinations(optional, size):
            conditioning = frozenset({*required, *subset})
            if _obligation_holds(
                graph,
                _GraphicalObligation(
                    kind="backdoor_adjustment",
                    treatment=treatment,
                    outcome=outcome,
                    conditioning=conditioning,
                ),
            ):
                return tuple(sorted(conditioning))
    return None


def _theorem_family_for_identification_method(identification_method: str | None) -> str | None:
    token = str(identification_method or "").strip().lower()
    if not token:
        return "id_exact"
    if token == "backdoor":
        return "adjustment_exact"
    if token.startswith("frontdoor"):
        return "frontdoor_exact"
    if token.startswith("proxy"):
        return "proxy_exact"
    if token.startswith("proximal"):
        return "proximal_exact"
    if token == "idc":
        return "idc_exact"
    return "id_exact"


def _resolve_composed_obligations(
    obligations: Sequence[_GraphicalObligation],
    resolutions: Mapping[str, _ResolvedVariable],
) -> tuple[_GraphicalObligation, ...] | None:
    resolved: list[_GraphicalObligation] = []
    for obligation in obligations:
        treatment = resolutions[obligation.treatment].composed_node
        outcome = resolutions[obligation.outcome].composed_node
        conditioning = {
            resolutions[variable].composed_node
            for variable in obligation.conditioning
        }
        if treatment is None or outcome is None or None in conditioning:
            return None
        resolved.append(
            _GraphicalObligation(
                kind=obligation.kind,
                treatment=treatment,
                outcome=outcome,
                conditioning=frozenset(str(variable) for variable in conditioning if variable),
            )
        )
    return tuple(resolved)


def _build_variable_resolutions(
    *,
    query_variables: Sequence[str],
    composed_graph: CausalGraphModel,
    fragment_graphs: Mapping[str, CausalGraphModel],
    interface_mapping: InterfaceMapping,
) -> dict[str, _ResolvedVariable]:
    binding_keys = {
        (binding.fragment_id, binding.variable_name)
        for entry in interface_mapping.entries
        for binding in entry.bindings
    }
    interface_by_canonical = {
        entry.canonical_node_id: entry for entry in interface_mapping.entries
    }
    interface_by_variable_name: dict[str, list[tuple[str, str, str]]] = {}
    for entry in interface_mapping.entries:
        for binding in entry.bindings:
            interface_by_variable_name.setdefault(binding.variable_name, []).append(
                (entry.canonical_node_id, binding.fragment_id, binding.variable_name)
            )

    non_interface_nodes: dict[str, list[tuple[str, str, str]]] = {}
    for fragment_id, graph in fragment_graphs.items():
        for node in graph.nodes:
            if (fragment_id, node) in binding_keys:
                continue
            non_interface_nodes.setdefault(node, []).append(
                (f"{fragment_id}::{node}", fragment_id, node)
            )

    resolutions: dict[str, _ResolvedVariable] = {}
    composed_nodes = set(composed_graph.nodes)
    for variable in query_variables:
        token = str(variable).strip()
        if not token:
            continue
        entry = interface_by_canonical.get(token)
        if entry is not None:
            resolutions[token] = _ResolvedVariable(
                composed_node=entry.canonical_node_id,
                local_nodes={binding.fragment_id: binding.variable_name for binding in entry.bindings},
            )
            continue

        if token in composed_nodes and "::" in token:
            fragment_id, local_name = token.split("::", 1)
            if fragment_id in fragment_graphs and local_name in fragment_graphs[fragment_id].nodes:
                resolutions[token] = _ResolvedVariable(
                    composed_node=token,
                    local_nodes={fragment_id: local_name},
                )
                continue

        interface_candidates = interface_by_variable_name.get(token, [])
        unique_interface_nodes = {item[0] for item in interface_candidates}
        if len(unique_interface_nodes) == 1:
            canonical_node = next(iter(unique_interface_nodes))
            local_nodes = {
                fragment_id: variable_name
                for _, fragment_id, variable_name in interface_candidates
            }
            resolutions[token] = _ResolvedVariable(
                composed_node=canonical_node,
                local_nodes=local_nodes,
            )
            continue

        non_interface_candidates = non_interface_nodes.get(token, [])
        if len(non_interface_candidates) == 1:
            composed_node, fragment_id, local_name = non_interface_candidates[0]
            resolutions[token] = _ResolvedVariable(
                composed_node=composed_node,
                local_nodes={fragment_id: local_name},
            )

    return resolutions


def _build_latent_projection_resolutions(
    *,
    query_variables: Sequence[str],
    projection: _LatentProjectionContext,
    fragment_graphs: Mapping[str, CausalGraphModel],
    interface_mapping: InterfaceMapping,
) -> dict[str, _ResolvedVariable]:
    interface_by_canonical = {
        entry.canonical_node_id: entry
        for entry in interface_mapping.entries
        if entry.alignment_type != "latent_bridge"
    }
    interface_by_variable_name: dict[str, list[tuple[str, str, str]]] = {}
    binding_keys = {
        (binding.fragment_id, binding.variable_name)
        for entry in interface_mapping.entries
        for binding in entry.bindings
    }
    for entry in interface_mapping.entries:
        if entry.alignment_type == "latent_bridge":
            continue
        for binding in entry.bindings:
            interface_by_variable_name.setdefault(binding.variable_name, []).append(
                (entry.canonical_node_id, binding.fragment_id, binding.variable_name)
            )

    non_interface_nodes: dict[str, list[tuple[str, str, str]]] = {}
    for fragment_id, graph in fragment_graphs.items():
        for node in graph.nodes:
            if (fragment_id, node) in binding_keys:
                continue
            token = f"{fragment_id}::{node}"
            if token not in set(projection.graph.nodes):
                continue
            non_interface_nodes.setdefault(node, []).append((token, fragment_id, node))

    projected_nodes = set(projection.graph.nodes)
    resolutions: dict[str, _ResolvedVariable] = {}
    for variable in query_variables:
        token = str(variable).strip()
        if not token:
            continue
        entry = interface_by_canonical.get(token)
        if entry is not None and token in projected_nodes:
            resolutions[token] = _ResolvedVariable(
                composed_node=entry.canonical_node_id,
                local_nodes={binding.fragment_id: binding.variable_name for binding in entry.bindings},
            )
            continue

        if token in projected_nodes and "::" in token:
            fragment_id, local_name = token.split("::", 1)
            if fragment_id in fragment_graphs and local_name in fragment_graphs[fragment_id].nodes:
                resolutions[token] = _ResolvedVariable(
                    composed_node=token,
                    local_nodes={fragment_id: local_name},
                )
                continue

        interface_candidates = interface_by_variable_name.get(token, [])
        unique_interface_nodes = {item[0] for item in interface_candidates if item[0] in projected_nodes}
        if len(unique_interface_nodes) == 1:
            canonical_node = next(iter(unique_interface_nodes))
            local_nodes = {
                fragment_id: variable_name
                for _, fragment_id, variable_name in interface_candidates
            }
            resolutions[token] = _ResolvedVariable(
                composed_node=canonical_node,
                local_nodes=local_nodes,
            )
            continue

        non_interface_candidates = non_interface_nodes.get(token, [])
        if len(non_interface_candidates) == 1:
            composed_node, fragment_id, local_name = non_interface_candidates[0]
            resolutions[token] = _ResolvedVariable(
                composed_node=composed_node,
                local_nodes={fragment_id: local_name},
            )

    return resolutions


def _has_latent_bridge_entries(interface_mapping: InterfaceMapping) -> bool:
    return any(entry.alignment_type == "latent_bridge" for entry in interface_mapping.entries)


def _latent_bridge_boundary_reason(interface_mapping: InterfaceMapping) -> str:
    blockers: set[str] = set()
    for entry in interface_mapping.entries:
        if entry.alignment_type != "latent_bridge":
            continue
        payload = entry.metadata.get("latent_artifact_blockers")
        if not isinstance(payload, list):
            continue
        blockers.update(str(item).strip() for item in payload if str(item).strip())
    if "latent_artifact_proof_only" in blockers:
        return "latent_artifact_proof_only"
    if "latent_promotion_denied" in blockers:
        return "latent_promotion_denied"
    if "latent_promotion_evidence_missing" in blockers:
        return "latent_promotion_evidence_missing"
    return "latent_bridge_research_boundary"


def _build_composed_latent_projection(
    *,
    fragment_graphs: Mapping[str, CausalGraphModel],
    interface_mapping: InterfaceMapping,
) -> _LatentProjectionContext | str | None:
    if not fragment_graphs:
        return None
    if any(graph.graph_type is not GraphType.DAG for graph in fragment_graphs.values()):
        return "latent_projection_requires_dag_fragments"

    binding_to_node: dict[tuple[str, str], str] = {}
    hidden_nodes: set[str] = set()
    node_set: set[str] = set()
    merged_edges: dict[tuple[str, str], CausalEdge] = {}

    for entry in interface_mapping.entries:
        node_id = entry.canonical_node_id
        if entry.alignment_type == "latent_bridge":
            hidden_nodes.add(node_id)
        node_set.add(node_id)
        for binding in entry.bindings:
            binding_to_node[(binding.fragment_id, binding.variable_name)] = node_id

    for fragment_id, graph in sorted(fragment_graphs.items()):
        for edge in graph.edges:
            if edge.mark_src is not EdgeMark.TAIL or edge.mark_dst is not EdgeMark.ARROW:
                return "latent_projection_requires_unmixed_dag_fragments"
            if edge.lag not in (None, 0):
                return "latent_projection_requires_unlagged_dag_fragments"
            src = binding_to_node.get((fragment_id, edge.src), f"{fragment_id}::{edge.src}")
            dst = binding_to_node.get((fragment_id, edge.dst), f"{fragment_id}::{edge.dst}")
            node_set.add(src)
            node_set.add(dst)
            if src == dst:
                continue
            merged_edges[(src, dst)] = _merge_witness_edge(
                merged_edges.get((src, dst)),
                edge.model_copy(update={"src": src, "dst": dst}),
            )

    base_edges = [merged_edges[key] for key in sorted(merged_edges)]
    if _directed_cycle_edges(base_edges):
        return "latent_projection_directed_cycle"

    adjacency: dict[str, set[str]] = {node: set() for node in node_set}
    for edge in base_edges:
        adjacency.setdefault(edge.src, set()).add(edge.dst)
        adjacency.setdefault(edge.dst, set())

    observed_nodes = set(node_set) - hidden_nodes

    @lru_cache(maxsize=None)
    def observed_descendants_from_hidden(node: str) -> frozenset[str]:
        descendants_set: set[str] = set()
        for child in sorted(adjacency.get(node, set())):
            if child in hidden_nodes:
                descendants_set.update(observed_descendants_from_hidden(child))
            elif child in observed_nodes:
                descendants_set.add(child)
        return frozenset(descendants_set)

    projected_edges: dict[tuple[str, str, str, str, int], CausalEdge] = {}
    for src in sorted(observed_nodes):
        reachable: set[str] = set()
        for child in sorted(adjacency.get(src, set())):
            if child in hidden_nodes:
                reachable.update(observed_descendants_from_hidden(child))
            elif child in observed_nodes:
                reachable.add(child)
        for dst in sorted(reachable):
            if src == dst:
                continue
            edge = CausalEdge(
                src=src,
                dst=dst,
                mark_src=EdgeMark.TAIL,
                mark_dst=EdgeMark.ARROW,
                sources=[EdgeSource.EXPERT],
                combined_confidence=1.0,
                metadata={"latent_projection": "directed_closure"},
            )
            key = _witness_edge_key(edge)
            projected_edges[key] = _merge_witness_edge(projected_edges.get(key), edge)

    for hidden in sorted(hidden_nodes):
        descendants_set = sorted(observed_descendants_from_hidden(hidden))
        for left, right in combinations(descendants_set, 2):
            edge = CausalEdge(
                src=left,
                dst=right,
                mark_src=EdgeMark.ARROW,
                mark_dst=EdgeMark.ARROW,
                sources=[EdgeSource.EXPERT],
                combined_confidence=1.0,
                metadata={
                    "latent_projection": "bidirected_common_hidden_ancestor",
                    "hidden_node": hidden,
                },
            )
            key = _witness_edge_key(edge)
            projected_edges[key] = _merge_witness_edge(projected_edges.get(key), edge)

    projected_edge_list = [projected_edges[key] for key in sorted(projected_edges)]
    if _directed_cycle_edges(projected_edge_list):
        return "latent_projection_directed_cycle"
    graph_type = (
        GraphType.ADMG
        if any(edge.mark_src is EdgeMark.ARROW and edge.mark_dst is EdgeMark.ARROW for edge in projected_edge_list)
        else GraphType.DAG
    )
    return _LatentProjectionContext(
        graph=CausalGraphModel(
            graph_type=graph_type,
            nodes=sorted(observed_nodes),
            edges=projected_edge_list,
            discovery_method="latent_projection_query_preservation",
            metadata={
                "hidden_interface_nodes": sorted(hidden_nodes),
                "interface_mapping_entry_ids": [
                    entry.interface_id for entry in interface_mapping.entries if entry.alignment_type == "latent_bridge"
                ],
            },
        ),
        hidden_nodes=frozenset(hidden_nodes),
        binding_to_node=binding_to_node,
    )


def _directed_cycle_edges(edges: Sequence[CausalEdge]) -> bool:
    adjacency: dict[str, set[str]] = {}
    for edge in edges:
        if edge.mark_src is not EdgeMark.TAIL or edge.mark_dst is not EdgeMark.ARROW:
            continue
        adjacency.setdefault(edge.src, set()).add(edge.dst)
        adjacency.setdefault(edge.dst, set())

    visited: set[str] = set()
    active: set[str] = set()

    def visit(node: str) -> bool:
        if node in active:
            return True
        if node in visited:
            return False
        visited.add(node)
        active.add(node)
        for nxt in sorted(adjacency.get(node, set())):
            if visit(nxt):
                return True
        active.remove(node)
        return False

    for node in sorted(adjacency):
        if visit(node):
            return True
    return False


def _fragment_topology(
    *,
    fragment_ids: Sequence[str],
    interface_mapping: InterfaceMapping,
    composition_certificate: CompositionCertificate,
) -> dict[str, set[str]]:
    adjacency = {fragment_id: set() for fragment_id in fragment_ids}

    for raw_pair in composition_certificate.metadata.get("selected_stitch_pairs", []):
        if not isinstance(raw_pair, (list, tuple)) or len(raw_pair) != 2:
            continue
        left = str(raw_pair[0]).strip()
        right = str(raw_pair[1]).strip()
        if left in adjacency and right in adjacency and left != right:
            adjacency[left].add(right)
            adjacency[right].add(left)

    if any(adjacency.values()):
        return adjacency

    for entry in interface_mapping.entries:
        fragment_group = sorted({binding.fragment_id for binding in entry.bindings})
        for left, right in combinations(fragment_group, 2):
            adjacency.setdefault(left, set()).add(right)
            adjacency.setdefault(right, set()).add(left)
    return adjacency


def _candidate_witness_fragment_sets(
    *,
    obligation: _GraphicalObligation,
    resolutions: Mapping[str, _ResolvedVariable],
    fragment_ids: Sequence[str],
    topology: Mapping[str, set[str]],
) -> list[tuple[str, ...]]:
    variables = [obligation.treatment, obligation.outcome, *sorted(obligation.conditioning)]
    candidate_sets = {
        variable: set(resolutions[variable].local_nodes)
        for variable in variables
    }
    candidates: list[tuple[str, ...]] = []
    for size in range(1, len(fragment_ids) + 1):
        for subset in combinations(fragment_ids, size):
            subset_set = set(subset)
            if not all(candidate_sets[variable] & subset_set for variable in variables):
                continue
            if _subset_connected(subset_set, topology):
                candidates.append(tuple(subset))
        if candidates:
            return candidates
    return []


def _subset_connected(
    subset: set[str],
    topology: Mapping[str, set[str]],
) -> bool:
    if not subset:
        return False
    if len(subset) == 1:
        return True
    start = next(iter(sorted(subset)))
    visited = {start}
    frontier = [start]
    while frontier:
        current = frontier.pop()
        for neighbor in sorted(topology.get(current, set()) & subset):
            if neighbor in visited:
                continue
            visited.add(neighbor)
            frontier.append(neighbor)
    return visited == subset


def _build_witness_graph(
    *,
    witness_fragment_ids: Sequence[str],
    fragment_graphs: Mapping[str, CausalGraphModel],
    interface_mapping: InterfaceMapping,
    fragments: Mapping[str, SCMFragment],
) -> CausalGraphModel | None:
    if not witness_fragment_ids:
        return None
    if any(fragment_id not in fragment_graphs for fragment_id in witness_fragment_ids):
        return None

    binding_to_node = {
        (binding.fragment_id, binding.variable_name): entry.canonical_node_id
        for entry in interface_mapping.entries
        for binding in entry.bindings
    }
    graph_type = (
        GraphType.ADMG
        if any(fragment_graphs[fragment_id].graph_type is GraphType.ADMG for fragment_id in witness_fragment_ids)
        else GraphType.DAG
    )
    node_set: set[str] = set()
    merged_edges: dict[tuple[str, str, str, str, int], CausalEdge] = {}

    for fragment_id in sorted(witness_fragment_ids):
        graph = fragment_graphs[fragment_id]
        node_map = {
            node: binding_to_node.get((fragment_id, node), f"{fragment_id}::{node}")
            for node in graph.nodes
        }
        node_set.update(node_map.values())
        for edge in graph.edges:
            edge_metadata = dict(edge.metadata)
            edge_metadata["contributing_fragment_ids"] = sorted(
                {
                    fragment_id,
                    *(
                        str(item)
                        for item in edge_metadata.get("contributing_fragment_ids", [])
                        if str(item).strip()
                    ),
                }
            )
            remapped = edge.model_copy(
                update={
                    "src": node_map[edge.src],
                    "dst": node_map[edge.dst],
                    "metadata": edge_metadata,
                }
            )
            if remapped.src == remapped.dst:
                continue
            edge_key = _witness_edge_key(remapped)
            merged_edges[edge_key] = _merge_witness_edge(merged_edges.get(edge_key), remapped)

    witness_graph = CausalGraphModel(
        graph_type=graph_type,
        nodes=sorted(node_set),
        edges=[merged_edges[key] for key in sorted(merged_edges)],
        discovery_method="query_preservation_witness",
        metadata={
            "witness_fragment_ids": list(sorted(witness_fragment_ids)),
            "cycle_contracts": [
                _fragment_cycle_contract_summary(fragments[fragment_id])
                for fragment_id in sorted(witness_fragment_ids)
                if fragment_id in fragments
            ],
        },
    )
    return _attach_cycle_contract_metadata(
        witness_graph,
        cycle_contracts=witness_graph.metadata.get("cycle_contracts", []),
    )


def _witness_edge_key(edge: CausalEdge) -> tuple[str, str, str, str, int]:
    return (
        edge.src,
        edge.dst,
        edge.mark_src.value,
        edge.mark_dst.value,
        int(edge.lag or 0),
    )


def _merge_witness_edge(existing: CausalEdge | None, incoming: CausalEdge) -> CausalEdge:
    if existing is None:
        combined = incoming.compute_combined_confidence() if incoming.sources else incoming.combined_confidence
        return incoming.model_copy(update={"combined_confidence": combined})

    merged = CausalEdge(
        src=existing.src,
        dst=existing.dst,
        mark_src=existing.mark_src,
        mark_dst=existing.mark_dst,
        lag=existing.lag,
        sources=sorted(set(existing.sources) | set(incoming.sources), key=lambda item: item.value),
        data_confidence=max(
            value for value in (existing.data_confidence, incoming.data_confidence) if value is not None
        )
        if any(value is not None for value in (existing.data_confidence, incoming.data_confidence))
        else None,
        literature_confidence=max(
            value
            for value in (existing.literature_confidence, incoming.literature_confidence)
            if value is not None
        )
        if any(
            value is not None
            for value in (existing.literature_confidence, incoming.literature_confidence)
        )
        else None,
        llm_confidence=max(
            value for value in (existing.llm_confidence, incoming.llm_confidence) if value is not None
        )
        if any(value is not None for value in (existing.llm_confidence, incoming.llm_confidence))
        else None,
        expert_confidence=max(
            value for value in (existing.expert_confidence, incoming.expert_confidence) if value is not None
        )
        if any(value is not None for value in (existing.expert_confidence, incoming.expert_confidence))
        else None,
        simulation_confidence=max(
            value
            for value in (existing.simulation_confidence, incoming.simulation_confidence)
            if value is not None
        )
        if any(
            value is not None
            for value in (existing.simulation_confidence, incoming.simulation_confidence)
        )
        else None,
        unsupported_by_evidence=existing.unsupported_by_evidence and incoming.unsupported_by_evidence,
        evidence_refs=sorted(set(existing.evidence_refs) | set(incoming.evidence_refs)),
        metadata={**existing.metadata, **incoming.metadata},
    )
    combined_confidence = (
        merged.compute_combined_confidence()
        if merged.sources
        else max(
            value
            for value in (existing.combined_confidence, incoming.combined_confidence)
            if value is not None
        )
        if any(value is not None for value in (existing.combined_confidence, incoming.combined_confidence))
        else None
    )
    return merged.model_copy(update={"combined_confidence": combined_confidence})


def _assumption_boundary_for_obligation(
    *,
    obligation: _GraphicalObligation,
    witness_graph: CausalGraphModel,
    composed_graph: CausalGraphModel,
    interface_mapping: InterfaceMapping,
) -> str | None:
    latent_nodes = {
        entry.canonical_node_id
        for entry in interface_mapping.entries
        if entry.alignment_type == "latent_bridge"
    }
    if not latent_nodes:
        return None
    witness_nodes = _obligation_relevant_nodes(witness_graph, obligation)
    composed_nodes = _obligation_relevant_nodes(composed_graph, obligation)
    if latent_nodes & witness_nodes:
        return "latent_bridge"
    if latent_nodes & composed_nodes:
        return "latent_bridge"
    return None


def _obligation_holds(
    graph: CausalGraphModel,
    obligation: _GraphicalObligation,
) -> bool:
    return _obligation_evaluation(graph, obligation)[0]


def _obligation_evaluation(
    graph: CausalGraphModel,
    obligation: _GraphicalObligation,
) -> tuple[bool, str]:
    if obligation.kind != "backdoor_adjustment":
        return False, ""
    seed = frozenset(
        {obligation.treatment, obligation.outcome, *obligation.conditioning}
    )
    if not seed.issubset(set(graph.nodes)):
        return False, ""
    forbidden_adjustment = descendants(
        graph,
        frozenset({obligation.treatment}),
        include_self=False,
    )
    if obligation.conditioning & forbidden_adjustment:
        return False, ""

    mutilated = remove_outgoing_edges(graph, frozenset({obligation.treatment}))
    relevant_nodes = ancestors(mutilated, seed) | seed
    relevant_graph = induced_subgraph(mutilated, relevant_nodes)
    return _separation_holds(
        relevant_graph,
        treatment=obligation.treatment,
        outcome=obligation.outcome,
        conditioning=obligation.conditioning,
    )


def _obligation_relevant_nodes(
    graph: CausalGraphModel,
    obligation: _GraphicalObligation,
) -> frozenset[str]:
    seed = frozenset({obligation.treatment, obligation.outcome, *obligation.conditioning})
    if not seed.issubset(set(graph.nodes)):
        return frozenset()
    mutilated = remove_outgoing_edges(graph, frozenset({obligation.treatment}))
    return frozenset(ancestors(mutilated, seed) | seed)


def _separation_holds(
    graph: CausalGraphModel,
    *,
    treatment: str,
    outcome: str,
    conditioning: frozenset[str],
) -> tuple[bool, str]:
    if not {treatment, outcome, *conditioning}.issubset(set(graph.nodes)):
        return False, ""
    if _should_use_sigma_separation(graph):
        return (
            sigma_separation(
                graph,
                frozenset({treatment}),
                frozenset({outcome}),
                conditioning,
            ),
            "sigma_separation",
        )
    if graph.graph_type is GraphType.DAG:
        return (
            d_separation(
                graph,
                frozenset({treatment}),
                frozenset({outcome}),
                conditioning,
            ),
            "d_separation",
        )
    if graph.graph_type is GraphType.ADMG:
        return (
            m_separation(
                graph,
                frozenset({treatment}),
                frozenset({outcome}),
                conditioning,
            ),
            "m_separation",
        )
    raise ValueError(f"unsupported graph type for query preservation: {graph.graph_type}")


def _should_use_sigma_separation(graph: CausalGraphModel) -> bool:
    cycle_mode = str(graph.metadata.get("cycle_semantics_mode", "")).strip().lower()
    if cycle_mode == "sigma_separation":
        return True
    cycle_contracts = graph.metadata.get("cycle_contracts", [])
    if (
        isinstance(cycle_contracts, list)
        and _cycle_semantics_mode_from_contracts(cycle_contracts) == "sigma_separation"
    ):
        return True
    return graph.graph_type is GraphType.ADMG and has_directed_cycle(graph)


def _witness_kind(witness_fragment_ids: Sequence[str]) -> str:
    return "single_fragment" if len(witness_fragment_ids) == 1 else "stitched_subgraph"


def _query_fingerprint(
    *,
    query: CausalQuery,
    composed_graph: CausalGraphModel,
    fragments: Sequence[SCMFragment],
    fragment_graphs: Mapping[str, CausalGraphModel],
    interface_mapping: InterfaceMapping,
    composition_certificate: CompositionCertificate,
) -> str:
    payload = {
        "query": query.model_dump(mode="json"),
        "composition": {
            "composed_graph": _graph_signature(composed_graph),
            "source_fragment_ids": sorted(composition_certificate.source_fragment_refs),
            "source_fragment_graph_ids": sorted(composition_certificate.source_fragment_graph_refs),
            "fragments": [
                {
                    "fragment_id": fragment.fragment_id,
                    "cycle_type": fragment.cycle_type.value,
                    "cycle_scope": fragment.cycle_scope.value,
                    "composition_policy": fragment.composition_policy.value,
                    "cycle_witnesses": [
                        {
                            "scc_id": witness.scc_id,
                            "solver_kind": witness.solver_kind.value,
                            "uniqueness_scope": witness.uniqueness_scope.value,
                            "interventional_closure": witness.interventional_closure.value,
                            "markov_semantics": witness.markov_semantics.value,
                            "initial_condition_dependent": witness.initial_condition_dependent,
                        }
                        for witness in fragment.cycle_witnesses
                    ],
                    "fragment_graph": _graph_signature(fragment_graphs[fragment.fragment_id]),
                }
                for fragment in sorted(fragments, key=lambda item: item.fragment_id)
                if fragment.fragment_id in fragment_graphs
            ],
            "fragment_graphs": {
                fragment_id: _graph_signature(graph)
                for fragment_id, graph in sorted(fragment_graphs.items())
            },
            "interface_mapping": interface_mapping.model_dump(mode="json"),
            "cycle_contracts": list(composition_certificate.metadata.get("cycle_contracts", [])),
        },
    }
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _graph_signature(graph: CausalGraphModel) -> dict[str, object]:
    return {
        "graph_type": graph.graph_type.value,
        "nodes": list(graph.nodes),
        "edges": [
            _edge_signature(edge)
            for edge in sorted(
                graph.edges,
                key=lambda item: (
                    item.src,
                    item.dst,
                    item.mark_src.value,
                    item.mark_dst.value,
                    int(item.lag or 0),
                ),
            )
        ],
    }


def _edge_signature(edge: CausalEdge) -> dict[str, object]:
    return {
        "src": edge.src,
        "dst": edge.dst,
        "mark_src": edge.mark_src.value,
        "mark_dst": edge.mark_dst.value,
        "lag": int(edge.lag or 0),
    }


__all__ = [
    "GraphicalObligationTrace",
    "QueryPreservationTrace",
    "QueryPreservationStatus",
    "evaluate_query_preservation",
    "evaluate_query_preservation_batch",
    "check_query_preservation",
    "check_query_preservation_batch",
    "negative_certificate_from_query_preservation_trace",
    "update_query_preservation_cache",
    "update_query_preservation_artifact_refs",
]
