"""Counterfactual transportability (Phase 4).

Extends Layer-3 counterfactual identification with selection-diagram based
transportability. The implementation deliberately reuses the existing:

- ``id_star_algorithm`` / ``idc_star_algorithm`` for Layer-3 seed queries
- ``rewrite_ctf_estimand`` for counterfactual-calculus reduction
- ``rewrite_estimand_with_selection`` for σ-calculus under selection
- ``SelectionDiagram`` / ``SourceDomain`` / ``NegativeCertificate`` contracts

The main entrypoint is ``ctf_transportability()`` which returns either an
``IdentificationResult`` (exact symbolic transport formula found) or a
``NegativeCertificate`` with partial bounds when the transport path stalls.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Iterable
from typing import Any

from polisyos.foundry.methods.catalog.causal.admg_ops import augment_with_s_nodes
from polisyos.foundry.methods.catalog.causal.ctf_calculus import (
    ast_contains_counterfactual,
    rewrite_ctf_estimand,
)
from polisyos.foundry.methods.catalog.causal.id_engine import (
    CtfQuery,
    IdentificationResult,
    IdentificationStatus,
    ProofStep,
    SourceDomain,
    _counterfactual_ast,
    _normalize_counterfactual_query,
    id_star_algorithm,
    idc_star_algorithm,
    mz_id_algorithm,
    tr_algorithm,
    z_id_algorithm,
)
from polisyos.foundry.methods.catalog.causal.sigma_calculus import (
    rewrite_estimand_with_selection,
)
from polisyos.ir.analytics.context import ContextProfile
from polisyos.ir.analytics.estimand import (
    CounterfactualNode,
    CrossWorldNode,
    CtfInterventionNode,
    DistributionDomain,
    DistributionRef,
    EstimandAST,
    IntegralNode,
    NestedCounterfactualNode,
    ProductNode,
    RatioNode,
    SumNode,
)
from polisyos.ir.analytics.negative_certificate import (
    BlockingType,
    NegativeCertificate,
)
from polisyos.ir.analytics.partial_identification import (
    BoundMethod,
    PartialIdentificationResult,
)
from polisyos.ir.analytics.transportability import SelectionDiagram, SNode


def _normalize_source_domains(
    source_domains: list[Any] | None,
    *,
    dataset_ref: str | None = None,
) -> list[SourceDomain]:
    normalized: list[SourceDomain] = []
    for idx, domain in enumerate(source_domains or []):
        if isinstance(domain, SourceDomain):
            normalized.append(domain)
            continue
        normalized.append(
            SourceDomain(
                domain_id=str(getattr(domain, "domain_id", f"source_{idx + 1}")),
                s_nodes=frozenset(getattr(domain, "s_nodes", ()) or ()),
                z_interventions=frozenset(getattr(domain, "z_interventions", ()) or ()),
                dataset_ref=getattr(domain, "dataset_ref", dataset_ref),
            )
        )
    return normalized


def _materialize_s_nodes(
    graph: Any,
    *,
    s_nodes: Iterable[Any] | None = None,
    source_domains: list[SourceDomain] | None = None,
) -> list[SNode]:
    materialized: dict[str, SNode] = {}

    def _coerce(entry: Any) -> SNode:
        if isinstance(entry, SNode):
            return entry
        return SNode(
            target_variable=str(getattr(entry, "target_variable", entry)),
            context_dimension=str(getattr(entry, "context_dimension", "programmatic")),
            source_value=getattr(entry, "source_value", 0.0),
            target_value=getattr(entry, "target_value", 1.0),
            delta=float(getattr(entry, "delta", 1.0)),
            severity=str(getattr(entry, "severity", "medium")),
        )

    for node in s_nodes or ():
        snode = _coerce(node)
        materialized.setdefault(snode.target_variable, snode)

    for domain in source_domains or ():
        for variable in sorted(domain.s_nodes):
            materialized.setdefault(
                variable,
                SNode(
                    target_variable=variable,
                    context_dimension="source_domain",
                    source_value=0.0,
                    target_value=1.0,
                    delta=1.0,
                    severity="medium",
                ),
            )

    return list(materialized.values())


def build_ctf_selection_diagram(
    *,
    graph: Any,
    s_nodes: Iterable[Any] | None = None,
    source_domains: list[Any] | None = None,
) -> SelectionDiagram:
    """Build a SelectionDiagram for Layer-3 transport routing.

    Explicit ``s_nodes`` win, but domain-local S-nodes are also folded in so
    multi-domain ctf-fusion can use the same routing path.
    """
    normalized_domains = _normalize_source_domains(source_domains)
    snode_list = _materialize_s_nodes(
        graph,
        s_nodes=s_nodes,
        source_domains=normalized_domains,
    )
    source_ctx = ContextProfile(context_id="source", context_label="source")
    target_ctx = ContextProfile(context_id="target", context_label="target")
    return SelectionDiagram(
        base_graph=graph,
        s_nodes=snode_list,
        source_context=source_ctx,
        target_context=target_ctx,
        context_distance=source_ctx.distance_to(target_ctx),
    )


def _effective_selection_vars(
    selection_diagram: SelectionDiagram,
    source_domains: list[SourceDomain],
) -> frozenset[str]:
    selection_vars = {s.target_variable for s in selection_diagram.s_nodes}
    for domain in source_domains:
        selection_vars.update(domain.s_nodes)
    return frozenset(selection_vars)


def _pick_matching_source_domain(
    ref: DistributionRef,
    source_domains: list[SourceDomain],
) -> SourceDomain | None:
    if not source_domains:
        return None

    intervention_set = frozenset(ref.intervention_set)
    if intervention_set:
        exact = [
            domain for domain in source_domains
            if intervention_set <= domain.z_interventions
        ]
        if exact:
            return exact[0]
        partial = [
            domain for domain in source_domains
            if intervention_set & domain.z_interventions
        ]
        if partial:
            partial.sort(key=lambda domain: len(intervention_set & domain.z_interventions), reverse=True)
            return partial[0]

    leaf_scope = frozenset(ref.variables) | frozenset(ref.conditioning)
    structural = [
        domain for domain in source_domains
        if leaf_scope & domain.s_nodes
    ]
    if structural:
        return structural[0]
    return source_domains[0]


def _rewrite_transport_node(
    node: Any,
    *,
    selection_vars: frozenset[str],
    source_domains: list[SourceDomain],
    dataset_ref: str | None,
) -> Any:
    if isinstance(node, DistributionRef):
        leaf_scope = frozenset(node.variables) | frozenset(node.conditioning)
        matched_domain = _pick_matching_source_domain(node, source_domains)
        if node.intervention_set:
            domain_kind = (
                DistributionDomain.EXPERIMENTAL
                if matched_domain is not None and matched_domain.z_interventions
                else DistributionDomain.EXPERIMENTAL
            )
        elif selection_vars and leaf_scope & selection_vars:
            domain_kind = DistributionDomain.TARGET
        elif source_domains:
            domain_kind = DistributionDomain.SOURCE
        else:
            domain_kind = DistributionDomain.TARGET if selection_vars else node.domain
        resolved_dataset_ref = node.dataset_ref or dataset_ref
        if matched_domain is not None and matched_domain.dataset_ref:
            resolved_dataset_ref = matched_domain.dataset_ref
        return node.model_copy(
            update={
                "domain": domain_kind,
                "dataset_ref": resolved_dataset_ref,
            }
        )

    if isinstance(node, SumNode):
        operand = _rewrite_transport_node(
            node.operand,
            selection_vars=selection_vars,
            source_domains=source_domains,
            dataset_ref=dataset_ref,
        )
        return node if operand is node.operand else node.model_copy(update={"operand": operand})

    if isinstance(node, IntegralNode):
        operand = _rewrite_transport_node(
            node.operand,
            selection_vars=selection_vars,
            source_domains=source_domains,
            dataset_ref=dataset_ref,
        )
        return node if operand is node.operand else node.model_copy(update={"operand": operand})

    if isinstance(node, ProductNode):
        factors = tuple(
            _rewrite_transport_node(
                factor,
                selection_vars=selection_vars,
                source_domains=source_domains,
                dataset_ref=dataset_ref,
            )
            for factor in node.factors
        )
        return node if factors == node.factors else node.model_copy(update={"factors": factors})

    if isinstance(node, RatioNode):
        numerator = _rewrite_transport_node(
            node.numerator,
            selection_vars=selection_vars,
            source_domains=source_domains,
            dataset_ref=dataset_ref,
        )
        denominator = _rewrite_transport_node(
            node.denominator,
            selection_vars=selection_vars,
            source_domains=source_domains,
            dataset_ref=dataset_ref,
        )
        if numerator is node.numerator and denominator is node.denominator:
            return node
        return node.model_copy(update={"numerator": numerator, "denominator": denominator})

    if isinstance(node, NestedCounterfactualNode):
        inner = _rewrite_transport_node(
            node.inner_counterfactual,
            selection_vars=selection_vars,
            source_domains=source_domains,
            dataset_ref=dataset_ref,
        )
        return node if inner is node.inner_counterfactual else node.model_copy(update={"inner_counterfactual": inner})

    if isinstance(node, CrossWorldNode):
        worlds = tuple(
            _rewrite_transport_node(
                world,
                selection_vars=selection_vars,
                source_domains=source_domains,
                dataset_ref=dataset_ref,
            )
            for world in node.worlds
        )
        return node if worlds == node.worlds else node.model_copy(update={"worlds": worlds})

    if isinstance(node, CtfInterventionNode):
        context = _rewrite_transport_node(
            node.ctf_context,
            selection_vars=selection_vars,
            source_domains=source_domains,
            dataset_ref=dataset_ref,
        )
        return node if context is node.ctf_context else node.model_copy(update={"ctf_context": context})

    if isinstance(node, CounterfactualNode):
        return node
    return node


def _annotate_transport_ast(
    ast: EstimandAST,
    *,
    selection_vars: frozenset[str],
    source_domains: list[SourceDomain],
    dataset_ref: str | None,
) -> EstimandAST:
    rewritten_root = _rewrite_transport_node(
        ast.root,
        selection_vars=selection_vars,
        source_domains=source_domains,
        dataset_ref=dataset_ref,
    )
    if rewritten_root is ast.root:
        return ast
    return ast.model_copy(update={"root": rewritten_root})


def _single_distribution_leaf(ast: EstimandAST) -> DistributionRef | None:
    return ast.root if isinstance(ast.root, DistributionRef) else None


def _delegate_layer2_transport(
    leaf: DistributionRef,
    *,
    selection_diagram: SelectionDiagram,
    source_domains: list[SourceDomain],
    dataset_ref: str | None,
) -> IdentificationResult | None:
    treatment = frozenset(leaf.intervention_set)
    outcome = frozenset(leaf.variables)
    if not treatment or not outcome:
        return None

    has_selection = bool(_effective_selection_vars(selection_diagram, source_domains))
    has_multi_domain = len(source_domains) > 1
    has_experiments = any(domain.z_interventions for domain in source_domains)

    if has_multi_domain or (has_selection and has_experiments):
        return mz_id_algorithm(
            treatment=treatment,
            outcome=outcome,
            source_domains=source_domains,
            graph=selection_diagram.base_graph,
            dataset_ref=dataset_ref,
        )
    if has_selection:
        return tr_algorithm(
            treatment=treatment,
            outcome=outcome,
            selection_diagram=selection_diagram,
            dataset_ref=dataset_ref,
        )
    if has_experiments:
        z_interventions = frozenset().union(*(domain.z_interventions for domain in source_domains))
        return z_id_algorithm(
            treatment=treatment,
            outcome=outcome,
            z_interventions=z_interventions,
            graph=selection_diagram.base_graph,
            dataset_ref=dataset_ref,
        )
    return None


def ctf_transport_bounds(
    ctf_query: CtfQuery,
    selection_diagram: SelectionDiagram,
    source_domains: list[SourceDomain] | None = None,
) -> PartialIdentificationResult:
    """Worst-case partial-ID bounds for counterfactual transport failure."""
    selection_vars = _effective_selection_vars(
        selection_diagram,
        source_domains or [],
    )
    width_penalty = min(1.0, 0.15 * len(selection_vars))
    lower = 0.0
    upper = 1.0
    return PartialIdentificationResult(
        method=BoundMethod.TRANSPORT_BOUNDS,
        lower_bound=lower,
        upper_bound=upper,
        confidence=max(0.0, 0.25 - width_penalty),
        assumptions_used=[
            "counterfactual_transport_relaxation",
            "worst_case_counterfactual_transport",
            f"selection_vars={sorted(selection_vars)}",
            f"query_kind={ctf_query.kind}",
        ],
        bounds_type="relaxed_polynomial",
        relaxation_gap=1.0,
        display_label="Counterfactual transport worst-case bounds",
    )


def _ctf_transport_failure_certificate(
    *,
    ctf_query: CtfQuery,
    selection_diagram: SelectionDiagram,
    source_domains: list[SourceDomain],
    fallback_result: IdentificationResult | None,
) -> NegativeCertificate:
    treatment = frozenset(name for name, _ in ctf_query.intervention)
    outcome = frozenset({ctf_query.outcome})
    selection_vars = _effective_selection_vars(selection_diagram, source_domains)
    bounds = ctf_transport_bounds(
        ctf_query,
        selection_diagram,
        source_domains,
    )
    domain_ids = [domain.domain_id for domain in source_domains] or ["target"]
    if selection_vars:
        return NegativeCertificate.from_mz_id_failure(
            treatment=treatment,
            outcome=outcome,
            unresolved_s_nodes=selection_vars,
            available_domains=domain_ids,
            hedge_certificate=getattr(fallback_result, "hedge_certificate", None),
            partial_bounds=bounds,
        )
    return NegativeCertificate(
        blocking_type=BlockingType.HEDGE_STRUCTURE,
        blocking_description=(
            f"Counterfactual transportability failed for {ctf_query.kind}:{ctf_query.outcome}. "
            "No exact Layer-3 transport reduction was found."
        ),
        technical_detail="Fallback ID* on the selection-augmented graph did not identify the query.",
        partial_bounds=bounds,
        suggested_experiments=NegativeCertificate.auto_suggest_experiments(
            BlockingType.HEDGE_STRUCTURE,
            missing_vars=tuple(sorted(treatment or outcome)),
        ),
        constructive_message=(
            "Collect target-domain data for the shifted mechanisms or add source-domain "
            "experiments that intervene on the transport-critical variables."
        ),
    )


def ctf_transportability(
    ctf_query: CtfQuery,
    selection_diagram: SelectionDiagram,
    source_domains: list[SourceDomain] | None = None,
    *,
    dataset_ref: str | None = None,
) -> IdentificationResult | NegativeCertificate:
    """Identify a Layer-3 counterfactual query under transport/fusion."""
    normalized_domains = _normalize_source_domains(source_domains, dataset_ref=dataset_ref)
    selection_vars = _effective_selection_vars(selection_diagram, normalized_domains)
    graph = selection_diagram.base_graph
    trace = [
        f"ctf_transportability(kind={ctf_query.kind}, outcome={ctf_query.outcome})",
        f"selection_vars={sorted(selection_vars)}",
        f"domains={[domain.domain_id for domain in normalized_domains]}",
    ]
    proof_steps: list[Any] = [
        ProofStep(
            rule_name="CTF_TRANSPORT_START",
            antecedent_vars=tuple(sorted(name for name, _ in ctf_query.intervention)),
            consequent_vars=(ctf_query.outcome,),
            applied_to_graph_state=(
                f"Start Layer-3 transportability on selection vars={sorted(selection_vars)} "
                f"and domains={[domain.domain_id for domain in normalized_domains]}"
            ),
        )
    ]

    if selection_vars:
        proof_steps.append(
            ProofStep(
                rule_name="CTF_TRANSPORT_AUGMENT",
                antecedent_vars=tuple(sorted(selection_vars)),
                consequent_vars=(ctf_query.outcome,),
                applied_to_graph_state=(
                    "Augmented the counterfactual transport problem with selection variables "
                    f"{sorted(selection_vars)}"
                ),
            )
        )

    seed_result = (
        idc_star_algorithm(ctf_query, graph)
        if ctf_query.evidence
        else id_star_algorithm(ctf_query, graph)
    )
    seed_ast = seed_result.estimand_ast
    if seed_ast is None:
        normalized_query = _normalize_counterfactual_query(ctf_query)
        seed_ast = _counterfactual_ast(
            query=ctf_query,
            normalized_query=normalized_query,
            identification_method="ctf_transport_seed",
        )
        trace.append("ctf_transportability: built raw Layer-3 AST because base ID* did not identify")
    else:
        trace.append("ctf_transportability: seeded Layer-3 AST from ID*/IDC*")

    augmented_graph = (
        augment_with_s_nodes(graph, selection_vars)
        if selection_vars
        else graph
    )
    ctf_ast, ctf_steps = rewrite_ctf_estimand(seed_ast, augmented_graph)
    sigma_ast, sigma_steps = rewrite_estimand_with_selection(
        ctf_ast,
        graph,
        selection_vars,
        ctf_postpass=lambda rewritten_ast, _rewritten_graph: (rewritten_ast, []),
    )
    rewritten_ast = _annotate_transport_ast(
        sigma_ast,
        selection_vars=selection_vars,
        source_domains=normalized_domains,
        dataset_ref=dataset_ref,
    )
    proof_steps.extend(ctf_steps)
    proof_steps.extend(sigma_steps)

    if not ast_contains_counterfactual(rewritten_ast.root):
        reduced_leaf = _single_distribution_leaf(rewritten_ast)
        delegated = None
        if reduced_leaf is not None:
            delegated = _delegate_layer2_transport(
                reduced_leaf,
                selection_diagram=selection_diagram,
                source_domains=normalized_domains,
                dataset_ref=dataset_ref,
            )
        if delegated is not None:
            delegated_ast = delegated.estimand_ast
            if delegated.status is not IdentificationStatus.IDENTIFIED or delegated_ast is None:
                trace.append("ctf_transportability: Layer-2 delegate failed after ctf reduction")
                return _ctf_transport_failure_certificate(
                    ctf_query=ctf_query,
                    selection_diagram=selection_diagram,
                    source_domains=normalized_domains,
                    fallback_result=delegated,
                )
            rewritten_ast = _annotate_transport_ast(
                delegated_ast,
                selection_vars=selection_vars,
                source_domains=normalized_domains,
                dataset_ref=dataset_ref,
            )
            trace.append("ctf_transportability: reduced to Layer-2 and delegated to transport backend")
            proof_steps.extend(getattr(delegated, "proof_steps", []))

        if len(normalized_domains) > 1:
            proof_steps.append(
                ProofStep(
                    rule_name="CTF_TRANSPORT_MZ",
                    antecedent_vars=tuple(sorted(selection_vars)),
                    consequent_vars=(ctf_query.outcome,),
                    applied_to_graph_state=(
                        f"Assigned reduced Layer-2 leaves across source domains "
                        f"{[domain.domain_id for domain in normalized_domains]}"
                    ),
                )
            )
        proof_steps.append(
            ProofStep(
                rule_name="CTF_TRANSPORT_EXACT",
                antecedent_vars=tuple(sorted(selection_vars)),
                consequent_vars=(ctf_query.outcome,),
                applied_to_graph_state=(
                    "Counterfactual query reduced to a transport-identifiable symbolic formula."
                ),
            )
        )
        trace.append("ctf_transportability: exact symbolic Layer-3 transport formula identified")
        return IdentificationResult(
            status=IdentificationStatus.IDENTIFIED,
            estimand_ast=rewritten_ast,
            hedge_certificate=None,
            trace=trace + list(getattr(seed_result, "trace", [])),
            required_distributions=rewritten_ast.collect_distribution_refs(),
            algorithm_version="ctf_transport_v1",
            proof_steps=proof_steps + list(getattr(seed_result, "proof_steps", [])),
            query_str=rewritten_ast.query_str,
        )

    proof_steps.append(
        ProofStep(
            rule_name="CTF_TRANSPORT_FALLBACK",
            antecedent_vars=tuple(sorted(selection_vars)),
            consequent_vars=(ctf_query.outcome,),
            applied_to_graph_state=(
                "Counterfactual nodes remain after σ/ctf reduction; falling back to ID* on the "
                "selection-augmented graph."
            ),
        )
    )
    fallback_result = (
        idc_star_algorithm(ctf_query, augmented_graph)
        if ctf_query.evidence
        else id_star_algorithm(ctf_query, augmented_graph)
    )
    if fallback_result.status is IdentificationStatus.IDENTIFIED and fallback_result.estimand_ast is not None:
        fallback_ast = _annotate_transport_ast(
            fallback_result.estimand_ast,
            selection_vars=selection_vars,
            source_domains=normalized_domains,
            dataset_ref=dataset_ref,
        )
        trace.append("ctf_transportability: fallback ID* on selection-augmented graph succeeded")
        return dataclasses.replace(
            fallback_result,
            estimand_ast=fallback_ast,
            trace=trace + list(fallback_result.trace),
            required_distributions=fallback_ast.collect_distribution_refs(),
            algorithm_version="ctf_transport_v1",
            proof_steps=proof_steps + list(fallback_result.proof_steps),
            query_str=fallback_ast.query_str,
        )

    trace.append("ctf_transportability: exact transport failed; returning constructive negative certificate")
    return _ctf_transport_failure_certificate(
        ctf_query=ctf_query,
        selection_diagram=selection_diagram,
        source_domains=normalized_domains,
        fallback_result=fallback_result,
    )


__all__ = [
    "build_ctf_selection_diagram",
    "ctf_transport_bounds",
    "ctf_transportability",
]
