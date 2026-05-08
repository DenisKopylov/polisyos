"""id_engine — Shpitser-Pearl ID algorithm for causal identification.

Implements the complete recursive ID algorithm (Tian & Pearl 2002; Shpitser &
Pearl 2006) plus the IDC extension for conditional interventional distributions
and the TR (Transportability) wrapper from Bareinboim & Pearl (2012).

All internal data-types (HedgeCertificate, IdentificationResult) are frozen
dataclasses rather than Pydantic models — they are internal algorithm state that
never crosses a JSON serialisation boundary directly.  At the boundary (in
SymbolicIdentifyV2.pure_step) they are converted to the existing IR contracts
(TransportabilityResult, EstimandAST).

Key functions
-------------
id_algorithm(treatment, outcome, graph)
    → IdentificationResult (IDENTIFIED | HEDGE_FOUND | PAG_AMBIGUOUS | ORACLE_NEEDED)

idc_algorithm(treatment, outcome, conditions, graph)
    → IdentificationResult via IDC reduction to two ID calls

tr_algorithm(treatment, outcome, selection_diagram)
    → IdentificationResult for transportability (augments graph with S-nodes)

id_with_oracle_fallback(treatment, outcome, graph, oracle)
    → IdentificationResult, trying oracle backends when native ID returns ORACLE_NEEDED

References
----------
Tian, J., Pearl, J. (2002). "A General Identification Condition for Causal Effects."
    AAAI 2002.
Shpitser, I., Pearl, J. (2006). "Identification of Joint Interventional Distributions
    in Recursive Semi-Markovian Causal Models." AAAI 2006.
Bareinboim, E., Pearl, J. (2012). "Transportability of Causal Effects: Completeness
    Results." AAAI 2012.
"""

from __future__ import annotations

import dataclasses
import hashlib
from typing import Any, Literal

from polisyos.foundry.methods.catalog.causal._id_contracts import (
    CtfQuery,
    HedgeCertificate,
    IdentificationResult,
    IdentificationStatus,
    ProofStep,
    RequiredDataSpec,
    SourceDomain,
)
from polisyos.foundry.methods.catalog.causal.admg_ops import (
    ancestors,
    augment_with_s_nodes,
    c_components,
    descendants,
    do_operator,
    extract_bidirected_edges,
    extract_directed_edges,
    induced_subgraph,
    m_separation,
    resolve_s_node_by_adjustment,
    topological_order,
)
from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, EdgeMark, GraphType
from polisyos.ir.analytics.estimand import (
    ConditionalInterventionNode,
    CounterfactualNode,
    CrossWorldNode,
    DistributionDomain,
    DistributionRef,
    EstimandAST,
    ModifiedTreatmentPolicyNode,
    NestedCounterfactualNode,
    ProductNode,
    RatioNode,
    SideCondition,
    SideConditionKind,
    StochasticInterventionNode,
    StochasticPolicy,
    SumNode,
    make_frontdoor_estimand,
    make_z_transport_estimand,
)

# ---------------------------------------------------------------------------
# PAG-specific identification (Malinsky & Spirtes 2017)
# ---------------------------------------------------------------------------

from . import core as _core

globals().update({name: getattr(_core, name) for name in dir(_core) if not name.startswith("__")})


def z_id_algorithm(
    *,
    treatment: frozenset[str],
    outcome: frozenset[str],
    z_interventions: frozenset[str],
    graph: CausalGraphModel,
    available_domains: list[Any] | None = None,
    dataset_ref: str | None = None,
    _depth: int = 0,
    _trace: list[str] | None = None,
) -> IdentificationResult:
    """Bareinboim-Pearl 2013 IJCAI Z-transportability algorithm.

    Extends the ID algorithm to exploit experimental distributions P_z(·|·)
    available from z-interventional studies.

    Parameters
    ----------
    treatment:         X — intervention variables
    outcome:           Y — outcome variables
    z_interventions:   Z — variables for which experimental distributions are available
    graph:             causal graph G
    available_domains: optional list of SourceDomain objects (unused in base impl)
    dataset_ref:       tag for DistributionRef leaves
    """
    if _trace is None:
        _trace = []

    _trace.append(
        f"[depth={_depth}] z_id_algorithm(X={sorted(treatment)}, Y={sorted(outcome)}, "
        f"Z={sorted(z_interventions)})"
    )

    _steps: list[ProofStep] = []

    # Step 0: No z-interventions — fall back to standard ID
    if not z_interventions:
        _trace.append(
            f"[depth={_depth}] z_id: no Z-interventions → standard id_with_oracle_fallback"
        )
        return id_with_oracle_fallback(
            treatment=treatment,
            outcome=outcome,
            graph=graph,
            oracle="none",
            dataset_ref=dataset_ref,
        )

    # Step 1: Try direct Z-transport formula first (most informative, fewest assumptions)
    direct = _z_transport_direct_pass(
        treatment=treatment,
        outcome=outcome,
        z_interventions=z_interventions,
        graph=graph,
        dataset_ref=dataset_ref,
    )
    if direct is not None and direct.status is IdentificationStatus.IDENTIFIED:
        _trace.append(f"[depth={_depth}] z_id: direct Z-transport formula applies")
        _steps.append(
            ProofStep(
                rule_name="Z_TRANSPORT",
                antecedent_vars=tuple(sorted(z_interventions)),
                consequent_vars=tuple(sorted(outcome)),
                applied_to_graph_state=(
                    f"Direct Z-transport: Σ_Z P_z(Y|X,Z)·P*(Z) with Z={sorted(z_interventions)}"
                ),
                depth=_depth,
            )
        )
        return dataclasses.replace(
            direct,
            proof_steps=_steps + list(direct.proof_steps),
        )

    # Step 2: Try ID with EXPERIMENTAL domain (Z-interventions as experimental data)
    available_vars = frozenset(graph.nodes) - z_interventions
    if treatment <= available_vars or not (treatment & z_interventions):
        first_pass = id_algorithm(
            treatment=treatment,
            outcome=outcome,
            graph=graph,
            available_vars=frozenset(graph.nodes),
            dataset_ref=dataset_ref,
            domain=DistributionDomain.EXPERIMENTAL,
            _depth=_depth,
            _trace=_trace,
        )
        if first_pass.status is IdentificationStatus.IDENTIFIED:
            _trace.append(f"[depth={_depth}] z_id: first pass IDENTIFIED")
            return dataclasses.replace(
                first_pass,
                proof_steps=_steps + list(first_pass.proof_steps),
            )
    else:
        first_pass = IdentificationResult(
            status=IdentificationStatus.ORACLE_NEEDED,
            estimand_ast=None,
            hedge_certificate=None,
            trace=list(_trace),
            required_distributions=[],
        )

    _trace.append(
        f"[depth={_depth}] z_id: first pass status={first_pass.status}, trying idc fallback"
    )

    # Step 3: Try IDC with each Z-variable as instrument
    best: IdentificationResult = first_pass
    status_rank = {
        IdentificationStatus.IDENTIFIED: 3,
        IdentificationStatus.ORACLE_NEEDED: 2,
        IdentificationStatus.PAG_AMBIGUOUS: 1,
        IdentificationStatus.HEDGE_FOUND: 0,
        IdentificationStatus.NOT_RECOVERABLE: -1,
    }

    for z in sorted(z_interventions):
        z_set = frozenset({z})
        try:
            candidate = idc_algorithm(
                treatment=treatment,
                outcome=outcome,
                conditions=z_set,
                graph=graph,
                dataset_ref=dataset_ref,
                domain=DistributionDomain.EXPERIMENTAL,
            )
            if status_rank.get(candidate.status, 0) > status_rank.get(best.status, 0):
                best = candidate
                _steps.append(
                    ProofStep(
                        rule_name="Z_TRANSPORT",
                        antecedent_vars=(z,),
                        consequent_vars=tuple(sorted(outcome)),
                        applied_to_graph_state=(
                            f"IDC fallback for Z-transport: P(Y|do(X),{z}) / P({z}|do(X)) "
                            f"with domain=EXPERIMENTAL"
                        ),
                        depth=_depth,
                    )
                )
                if best.status is IdentificationStatus.IDENTIFIED:
                    break
        except Exception:
            pass

    return dataclasses.replace(best, proof_steps=_steps + list(best.proof_steps))


def _prune_source_domains(
    outcome: frozenset[str],
    graph: CausalGraphModel,
    source_domains: list[SourceDomain],
) -> list[SourceDomain]:
    """Remove source domains that cannot contribute to identifying *outcome*.

    A domain contributes if its z_interventions or s_nodes intersect with any
    c-component that overlaps with the ancestral closure of the outcome.
    Domains with no special information (bare standard-ID fallbacks) are kept
    only if no other domain is available.

    The pruning is greedy (first-fit coverage) and preserves ordering.
    """
    all_comps = c_components(graph)
    relevant_vars = ancestors(graph, outcome)
    relevant_comps = [c for c in all_comps if c & relevant_vars]

    useful: list[SourceDomain] = []
    covered: set[frozenset[str]] = set()
    bare: list[SourceDomain] = []  # domains with no s/z info

    for domain in source_domains:
        domain_vars = domain.z_interventions | domain.s_nodes
        if not domain_vars:
            bare.append(domain)
            continue
        domain_comps = {c for c in relevant_comps if c & domain_vars}
        new_coverage = domain_comps - covered
        if new_coverage:
            useful.append(domain)
            covered |= new_coverage

    if not useful:
        # Fall back to all domains if pruning removes everything
        return source_domains
    # Append one bare domain as a last-resort standard-ID fallback
    if bare:
        useful.append(bare[0])
    return useful


def _mz_factorize_by_c_component(
    *,
    treatment: frozenset[str],
    outcome: frozenset[str],
    source_domains: list[SourceDomain],
    graph: CausalGraphModel,
    dataset_ref: str | None,
    _steps: list[ProofStep],
    _trace: list[str],
) -> IdentificationResult | None:
    """Formal mz-ID factorisation by c-component (Bareinboim & Pearl 2014, Theorem 2).

    Restricts to the ancestral subgraph G[An(Y)], computes c-components of that
    subgraph, and for each c-component that intersects the outcome set tries all
    source domains until one identifies the component.  Combines the per-component
    estimands via a ProductNode.

    Validity condition (Theorem 2):
        For every c-component Si ⊆ C(G[An(Y)]) with Si ∩ Y ≠ ∅:
            ∃ domain d such that id_algorithm on G[Si] identifies Y ∩ Si.
        Combined result: ∏_i Q[Si] covers all of Y.

    Returns None if factorisation fails (some component cannot be identified).
    """
    # Restrict to ancestral subgraph G[An(Y)] per Theorem 2
    an_y = ancestors(graph, outcome)
    ancestral_graph = induced_subgraph(graph, an_y)

    all_comps = c_components(ancestral_graph)
    if len(all_comps) <= 1:
        return None  # No factorisation benefit if there is only one c-component

    comp_results: list[tuple[IdentificationResult, str]] = []  # (result, domain_id)
    all_dists: list[DistributionRef] = []
    factor_nodes: list[Any] = []
    covered_outcomes: set[str] = set()

    for comp in all_comps:
        comp_outcome = outcome & comp
        if not comp_outcome:
            continue  # this component does not intersect Y

        comp_treatment = treatment & comp
        comp_graph = induced_subgraph(ancestral_graph, comp)

        # Try each domain for this component
        best_comp: IdentificationResult | None = None
        best_domain_id: str = ""
        for domain in source_domains:
            # Route through domain-appropriate algorithm
            has_z = bool(domain.z_interventions & comp)
            has_s = bool(domain.s_nodes & comp)
            eff_dataset = dataset_ref or domain.dataset_ref

            try:
                if has_s and has_z:
                    aug_comp = augment_with_s_nodes(comp_graph, domain.s_nodes & comp)
                    comp_result = z_id_algorithm(
                        treatment=comp_treatment
                        if comp_treatment
                        else treatment & frozenset(comp_graph.nodes),
                        outcome=comp_outcome,
                        z_interventions=domain.z_interventions & comp,
                        graph=aug_comp,
                        dataset_ref=eff_dataset,
                    )
                elif has_z:
                    comp_result = z_id_algorithm(
                        treatment=comp_treatment
                        if comp_treatment
                        else treatment & frozenset(comp_graph.nodes),
                        outcome=comp_outcome,
                        z_interventions=domain.z_interventions & comp,
                        graph=comp_graph,
                        dataset_ref=eff_dataset,
                    )
                else:
                    comp_result = id_with_oracle_fallback(
                        treatment=comp_treatment
                        if comp_treatment
                        else treatment & frozenset(comp_graph.nodes),
                        outcome=comp_outcome,
                        graph=comp_graph,
                        oracle="none",
                        dataset_ref=eff_dataset,
                    )
            except Exception:
                continue

            if comp_result.status is IdentificationStatus.IDENTIFIED:
                best_comp = comp_result
                best_domain_id = domain.domain_id
                break  # First domain that works is sufficient

        if best_comp is None:
            _trace.append(f"mz_factorize: c-component {sorted(comp)} not identified by any domain")
            return None  # Factorisation fails

        # Record domain selection for this component
        _steps.append(
            ProofStep(
                rule_name="S_DOMAIN_SELECT",
                antecedent_vars=tuple(sorted(comp)),
                consequent_vars=tuple(sorted(comp_outcome)),
                applied_to_graph_state=(
                    f"Domain {best_domain_id!r} selected for c-component "
                    f"{sorted(comp)} → identifies {sorted(comp_outcome)}"
                ),
                depth=0,
            )
        )
        comp_results.append((best_comp, best_domain_id))
        assert best_comp.estimand_ast is not None
        factor_nodes.append(best_comp.estimand_ast.root)
        all_dists.extend(best_comp.required_distributions)
        covered_outcomes.update(comp_outcome)

    if not factor_nodes:
        return None

    # Completeness check: every outcome variable must be covered
    if not (outcome <= covered_outcomes):
        _trace.append(
            f"mz_factorize: incomplete — covered={sorted(covered_outcomes)}, "
            f"needed={sorted(outcome)}"
        )
        return None

    # Build combined estimand
    combined_root = (
        factor_nodes[0] if len(factor_nodes) == 1 else ProductNode(factors=tuple(factor_nodes))
    )
    combined_ast = EstimandAST(
        query_str=f"P({sorted(outcome)}|do({sorted(treatment)}))",
        root=combined_root,
        treatment=(
            next(iter(sorted(treatment))) if len(treatment) == 1 else str(sorted(treatment))
        ),
        outcome=(next(iter(sorted(outcome))) if len(outcome) == 1 else str(sorted(outcome))),
        all_variables=tuple(sorted(treatment | outcome)),
        identification_method="mz_id_factorization",
    )

    # Emit MZ_FACTORIZE ProofStep
    _steps.append(
        ProofStep(
            rule_name="MZ_FACTORIZE",
            antecedent_vars=tuple(sorted(treatment | outcome)),
            consequent_vars=tuple(sorted(outcome)),
            applied_to_graph_state=(
                f"mz-ID factorisation over {len(factor_nodes)} c-component(s) of G[An(Y)] succeeded"
            ),
            depth=0,
        )
    )
    _trace.append(f"mz_factorize: factorisation succeeded over {len(factor_nodes)} c-component(s)")

    return IdentificationResult(
        status=IdentificationStatus.IDENTIFIED,
        estimand_ast=combined_ast,
        hedge_certificate=None,
        trace=_trace,
        required_distributions=all_dists,
        proof_steps=list(_steps),
    )


def mz_id_algorithm(
    *,
    treatment: frozenset[str],
    outcome: frozenset[str],
    source_domains: list[SourceDomain],
    graph: CausalGraphModel,
    dataset_ref: str | None = None,
) -> IdentificationResult:
    """Pearl-Bareinboim 2014 AAAI meta-transportability algorithm.

    Combines evidence from multiple source domains (each potentially having
    s-node selections and/or z-interventions) to identify a causal effect
    in the target domain.

    Enhancements:
    - Uses :func:`augment_with_s_nodes` from admg_ops for domain S-node augmentation
    - Fixed :class:`SNode` instantiation (was missing required fields)
    - Formal c-component factorisation via :func:`_mz_factorize_by_c_component`
      (restricted to ancestral subgraph per Bareinboim & Pearl 2014 Theorem 2)
    - ProofStep emission for MZ_FACTORIZE and S_DOMAIN_SELECT

    Parameters
    ----------
    treatment:      X — intervention variables
    outcome:        Y — outcome variables
    source_domains: list of SourceDomain descriptors
    graph:          target-domain causal graph G
    dataset_ref:    tag for DistributionRef leaves
    """
    _trace: list[str] = [
        f"mz_id_algorithm(X={sorted(treatment)}, Y={sorted(outcome)}, "
        f"domains={[d.domain_id for d in source_domains]})"
    ]

    # No source domains — fall back to standard ID
    if not source_domains:
        return id_with_oracle_fallback(
            treatment=treatment,
            outcome=outcome,
            graph=graph,
            oracle="none",
            dataset_ref=dataset_ref,
        )

    # Prune source domains that cannot contribute to identifying outcome
    pruned = _prune_source_domains(outcome, graph, source_domains)
    if len(pruned) < len(source_domains):
        _trace.append(f"mz_id: pruned {len(source_domains) - len(pruned)} irrelevant domain(s)")
        source_domains = pruned

    identified_results: list[tuple[int, IdentificationResult]] = []  # (domain_idx, result)
    last_result: IdentificationResult | None = None

    for domain_idx, domain in enumerate(source_domains):
        has_s = bool(domain.s_nodes)
        has_z = bool(domain.z_interventions)

        if has_s and has_z:
            # Domain has both S-nodes and Z-interventions: use z_id on S-augmented graph
            augmented = augment_with_s_nodes(graph, domain.s_nodes)
            result = z_id_algorithm(
                treatment=treatment,
                outcome=outcome,
                z_interventions=domain.z_interventions,
                graph=augmented,
                dataset_ref=dataset_ref or domain.dataset_ref,
            )
        elif has_s:
            # Domain has only S-nodes: use tr_algorithm with a minimal SelectionDiagram
            try:
                from polisyos.ir.analytics.context import ContextProfile
                from polisyos.ir.analytics.transportability import (
                    SelectionDiagram,
                    SNode,
                )

                s_node_list = [
                    SNode(
                        target_variable=sv,
                        context_dimension="programmatic",
                        source_value=0.0,
                        target_value=1.0,
                        delta=1.0,
                        severity="medium",
                    )
                    for sv in sorted(domain.s_nodes)
                ]
                ctx = ContextProfile()
                sd_obj = SelectionDiagram(
                    base_graph=graph,
                    s_nodes=s_node_list,
                    source_context=ctx,
                    target_context=ctx,
                )
                result = tr_algorithm(
                    treatment=treatment,
                    outcome=outcome,
                    selection_diagram=sd_obj,
                    dataset_ref=dataset_ref or domain.dataset_ref,
                )
            except Exception:
                result = id_with_oracle_fallback(
                    treatment=treatment,
                    outcome=outcome,
                    graph=graph,
                    oracle="none",
                    dataset_ref=dataset_ref or domain.dataset_ref,
                )
        elif has_z:
            # Domain has only Z-interventions
            result = z_id_algorithm(
                treatment=treatment,
                outcome=outcome,
                z_interventions=domain.z_interventions,
                graph=graph,
                dataset_ref=dataset_ref or domain.dataset_ref,
            )
        else:
            # No special information — standard ID
            result = id_with_oracle_fallback(
                treatment=treatment,
                outcome=outcome,
                graph=graph,
                oracle="none",
                dataset_ref=dataset_ref or domain.dataset_ref,
            )

        last_result = result
        if result.status is IdentificationStatus.IDENTIFIED:
            identified_results.append((domain_idx, result))

    # Return best IDENTIFIED result — prefer the domain with more z_interventions
    # (more experimental information → more reliable estimand).
    if identified_results:

        def _z_count_for_pair(pair: tuple[int, IdentificationResult]) -> int:
            d_idx, _ = pair
            return len(source_domains[d_idx].z_interventions)

        identified_results.sort(key=_z_count_for_pair, reverse=True)
        return identified_results[0][1]

    # Formal cross-domain factorisation (Bareinboim & Pearl 2014, Theorem 2)
    if len(source_domains) > 1:
        factorize_steps: list[ProofStep] = []
        fact_result = _mz_factorize_by_c_component(
            treatment=treatment,
            outcome=outcome,
            source_domains=source_domains,
            graph=graph,
            dataset_ref=dataset_ref,
            _steps=factorize_steps,
            _trace=_trace,
        )
        if fact_result is not None:
            return fact_result

    # Nothing worked — return the last result (ORACLE_NEEDED or HEDGE_FOUND)
    if last_result is not None:
        return last_result
    return id_with_oracle_fallback(
        treatment=treatment,
        outcome=outcome,
        graph=graph,
        oracle="none",
        dataset_ref=dataset_ref,
    )


# ===========================================================================
# PHASE 5: Extended Identification Theory
# ===========================================================================

# ---------------------------------------------------------------------------
# 5.1  Stochastic, Conditional, and Dynamic Interventions
# ---------------------------------------------------------------------------

# Proof-step rule name constants for Phase-5 steps
_SID_POLICY_WRAP = "SID_POLICY_WRAP"
_SID_SHIFT = "SID_SHIFT"
_SID_CONDITIONAL = "SID_CONDITIONAL"
_SID_DAG_POLICY = "SID_DAG_POLICY"
_SID_SIGMA_FALLBACK = "SID_SIGMA_FALLBACK"
_DYNAMIC_GFORMULA = "DYNAMIC_GFORMULA"
_JOINT_FACTOR_DECOMPOSE = "JOINT_FACTOR_DECOMPOSE"
_MULTI_OUTCOME_SHARED_CCOMP = "MULTI_OUTCOME_SHARED_CCOMP"


def _policy_side_conditions(
    *,
    treatment: frozenset[str],
    policy: StochasticPolicy,
) -> tuple[SideCondition, ...]:
    """Return the core side-conditions required for policy identification."""
    treatment_vars = tuple(sorted(treatment))
    support_vars = tuple(sorted(treatment | frozenset(policy.conditioning_vars)))
    positivity_description = (
        "Shift positivity required: the shifted treatment support must remain inside "
        "the observed treatment mechanism support, i.e. f(A-delta|L) > 0 wherever "
        "the policy is evaluated."
        if policy.policy_type == "shift"
        else "Policy support / positivity required: the stochastic policy may only "
        "assign treatment values with non-zero observed support under the natural "
        "assignment mechanism."
    )
    return (
        SideCondition(
            kind=SideConditionKind.CONSISTENCY,
            variables=treatment_vars,
            description=(
                "Consistency for policy interventions: the observed outcome equals the "
                "counterfactual policy outcome whenever the realized treatment follows "
                "the policy-assigned regime."
            ),
        ),
        SideCondition(
            kind=SideConditionKind.POSITIVITY,
            variables=support_vars,
            description=positivity_description,
        ),
    )


def _policy_metadata(policy: StochasticPolicy) -> dict[str, Any]:
    return {
        "policy_type": policy.policy_type,
        "policy_conditioning_vars": list(policy.conditioning_vars),
        "policy_expr": policy.policy_expr,
        "shift_delta": policy.shift_delta,
    }


def _resolve_selection_targets(raw_s_nodes: Any) -> frozenset[str]:
    """Resolve selection-node targets to substantive variable names."""
    if raw_s_nodes is None:
        return frozenset()
    resolved: set[str] = set()
    for node in raw_s_nodes or ():
        target = getattr(node, "target_variable", None)
        if target:
            resolved.add(str(target))
        elif isinstance(node, str) and node.startswith("S_") and len(node) > 2:
            resolved.add(node[2:])
        elif isinstance(node, str):
            resolved.add(node)
    return frozenset(resolved)


def _make_policy_estimand_ast(
    *,
    treatment: frozenset[str],
    outcome: frozenset[str],
    policy: StochasticPolicy,
    inner_do_node: object,
    domain: DistributionDomain,
    dataset_ref: str | None,
    identification_method: str,
    side_conditions: tuple[SideCondition, ...],
) -> EstimandAST:
    """Build the policy estimand AST for a stochastic or shift intervention."""
    t_str = next(iter(sorted(treatment))) if len(treatment) == 1 else str(sorted(treatment))
    y_str = next(iter(sorted(outcome))) if len(outcome) == 1 else str(sorted(outcome))
    all_variables = tuple(sorted(treatment | outcome | frozenset(policy.conditioning_vars)))

    if policy.policy_type == "shift":
        policy_expr = policy.policy_expr or (
            f"{t_str}+{policy.shift_delta}" if policy.shift_delta is not None else f"shift({t_str})"
        )
        root_node = ModifiedTreatmentPolicyNode(
            treatment_var=t_str,
            policy_expr=policy_expr,
            natural_treatment_var=t_str,
            covariates=tuple(policy.conditioning_vars),
            inner_node=inner_do_node,  # type: ignore[arg-type]
            domain=domain,
            dataset_ref=dataset_ref,
        )
        query_str = f"E_d[{y_str}|mtp({t_str})]"
    else:
        integration_var = t_str if len(treatment) == 1 else sorted(treatment)[0]
        root_node = StochasticInterventionNode(
            treatment_var=t_str,
            policy=policy,
            inner_do_node=inner_do_node,  # type: ignore[arg-type]
            integration_var=integration_var,
            domain=domain,
        )
        query_str = f"E_π[{y_str}|do({t_str})]"

    return EstimandAST(
        query_str=query_str,
        root=root_node,  # type: ignore[arg-type]
        treatment=t_str,
        outcome=y_str,
        all_variables=all_variables,
        side_conditions=side_conditions,
        identification_method=identification_method,
    )


def _attempt_sigma_policy_identification(
    *,
    treatment: frozenset[str],
    outcome: frozenset[str],
    graph: CausalGraphModel,
    policy: StochasticPolicy,
    dataset_ref: str | None,
    domain: DistributionDomain,
    selection_targets: frozenset[str],
    trace: list[str],
) -> IdentificationResult | None:
    """Attempt a conservative sigma-calculus fallback for soft policies."""
    from polisyos.foundry.methods.catalog.causal.sigma_calculus import sigma_identify

    if policy.policy_type != "soft":
        return None

    selection_vars = selection_targets or frozenset(treatment)
    atomic_ast = _wrap_root(
        DistributionRef(
            domain=domain,
            variables=tuple(sorted(outcome)),
            intervention_set=tuple(sorted(treatment)),
            dataset_ref=dataset_ref,
        ),
        treatment=treatment,
        outcome=outcome,
        method="sid_sigma_seed",
    )
    sigma_ast, sigma_steps = sigma_identify(
        atomic_ast,
        graph,
        selection_vars=selection_vars,
    )
    sigma_refs = sigma_ast.collect_distribution_refs()
    if not sigma_refs:
        trace.append("[SID] sigma fallback produced no observable distribution leaves")
        return None
    if any(frozenset(ref.intervention_set) & treatment for ref in sigma_refs):
        trace.append(
            "[SID] sigma fallback left treatment interventions in observable leaves "
            f"for selection vars={sorted(selection_vars)}"
        )
        return None

    trace.append(
        "[SID] sigma fallback identified the atomic policy kernel via "
        f"selection vars={sorted(selection_vars)}"
    )
    ast = _make_policy_estimand_ast(
        treatment=treatment,
        outcome=outcome,
        policy=policy,
        inner_do_node=sigma_ast.root,
        domain=domain,
        dataset_ref=dataset_ref,
        identification_method="sid_sigma_soft",
        side_conditions=_policy_side_conditions(treatment=treatment, policy=policy),
    )
    return IdentificationResult(
        status=IdentificationStatus.IDENTIFIED,
        estimand_ast=ast,
        hedge_certificate=None,
        trace=list(trace),
        required_distributions=sigma_refs,
        algorithm_version="sid_sigma_v2",
        proof_steps=[
            ProofStep(
                rule_name=_SID_SIGMA_FALLBACK,
                antecedent_vars=tuple(sorted(treatment)),
                consequent_vars=tuple(sorted(outcome)),
                applied_to_graph_state=(
                    f"sigma-calculus fallback succeeded under selection vars="
                    f"{sorted(selection_vars)}"
                ),
                depth=0,
            ),
            *sigma_steps,
        ],
        metadata={
            **_policy_metadata(policy),
            "sigma_selection_vars": sorted(selection_vars),
            "policy_semantics": "sigma_calculus",
        },
    )


def sid_algorithm(
    *,
    treatment: frozenset[str],
    outcome: frozenset[str],
    graph: CausalGraphModel,
    policy: StochasticPolicy,
    available_vars: frozenset[str] | None = None,
    dataset_ref: str | None = None,
    domain: DistributionDomain = DistributionDomain.SOURCE,
    s_nodes: Any = None,
) -> IdentificationResult:
    """Stochastic intervention identification (Correa & Bareinboim 2020).

    Identifies E_π[Y] = ∫ P(Y|do(X=x)) π(x|Z) dx for a policy π by:

    1. Running the standard ID algorithm to obtain P(Y|do(X=x)).
    2. If identified, wrapping the result in a :class:`StochasticInterventionNode`
       that encodes the policy integration.
    3. For ``shift`` policies (Díaz & van der Laan 2012), a modified-treatment-policy
       wrapper is produced instead of a hard do() node.
    4. For ``conditional`` policies (do(X|Z=z)), delegating to
       :func:`conditional_intervention_id`.

    Parameters
    ----------
    treatment:
        X — the treatment variable(s) being intervened on stochastically.
    outcome:
        Y — the target outcome variable(s).
    graph:
        Causal DAG or PAG.
    policy:
        The stochastic policy π specification.
    available_vars, dataset_ref, domain, s_nodes:
        Forwarded to the inner :func:`id_algorithm` call.

    References
    ----------
    Correa, J. & Bareinboim, E. (2020). "A Calculus for Stochastic
        Interventions: Causal Effect Identification and Surrogate
        Experiments." NeurIPS 2020.
    Díaz, I. & van der Laan, M.J. (2012). "Population Intervention Causal
        Effects Based on Stochastic Interventions." Biometrics 68(2).
    """
    _trace: list[str] = []
    _steps: list[ProofStep] = []

    t_str = next(iter(sorted(treatment))) if len(treatment) == 1 else str(sorted(treatment))
    y_str = next(iter(sorted(outcome))) if len(outcome) == 1 else str(sorted(outcome))

    _trace.append(
        f"[SID] sid_algorithm(X={sorted(treatment)}, Y={sorted(outcome)}, "
        f"policy_type={policy.policy_type})"
    )

    # Delegate conditional-type policy to conditional_intervention_id
    if policy.policy_type == "conditional":
        if not policy.conditioning_vars:
            _trace.append("[SID] conditional policy has empty conditioning_vars → standard ID")
        else:
            cond_result = conditional_intervention_id(
                treatment=treatment,
                outcome=outcome,
                condition_vars=frozenset(policy.conditioning_vars),
                graph=graph,
                available_vars=available_vars,
                dataset_ref=dataset_ref,
                domain=domain,
            )
            _steps.append(
                ProofStep(
                    rule_name=_SID_CONDITIONAL,
                    antecedent_vars=tuple(sorted(treatment)),
                    consequent_vars=tuple(sorted(outcome)),
                    applied_to_graph_state=(
                        f"Conditional policy do(X|Z={sorted(policy.conditioning_vars)}) "
                        f"→ conditional_intervention_id; inner status={cond_result.status.value}"
                    ),
                    depth=0,
                )
            )
            return dataclasses.replace(
                cond_result,
                proof_steps=_steps + list(cond_result.proof_steps),
                algorithm_version="sid_conditional_v1",
                metadata={
                    **dict(getattr(cond_result, "metadata", {}) or {}),
                    **_policy_metadata(policy),
                },
            )

    available = available_vars if available_vars is not None else frozenset(graph.nodes)

    # Unconfounded DAG fast path: directly use the policy g-formula/truncated
    # factorization instead of routing through the full recursive ID kernel.
    if graph.graph_type is GraphType.DAG:
        dag_trace = list(_trace)
        base_result = _dag_g_formula(
            treatment=treatment,
            outcome=outcome,
            graph=graph,
            available_vars=available,
            dataset_ref=dataset_ref,
            domain=domain,
            depth=0,
            trace=dag_trace,
        )
        _trace = list(base_result.trace)
        if base_result.status is IdentificationStatus.IDENTIFIED:
            _steps.append(
                ProofStep(
                    rule_name=_SID_DAG_POLICY,
                    antecedent_vars=tuple(sorted(treatment)),
                    consequent_vars=tuple(sorted(outcome)),
                    applied_to_graph_state=(
                        "Policy g-formula fast path: replaced the treatment mechanism "
                        "with the policy factor inside the DAG truncated factorization."
                    ),
                    depth=0,
                )
            )
    else:
        # General fallback: use the recursive ID kernel for P(Y|do(X=x)).
        base_result = id_algorithm(
            treatment=treatment,
            outcome=outcome,
            graph=graph,
            dataset_ref=dataset_ref,
            domain=domain,
            available_vars=available_vars,
        )
        _trace.extend(base_result.trace)

    if base_result.status is not IdentificationStatus.IDENTIFIED:
        sigma_result = _attempt_sigma_policy_identification(
            treatment=treatment,
            outcome=outcome,
            graph=graph,
            policy=policy,
            dataset_ref=dataset_ref,
            domain=domain,
            selection_targets=_resolve_selection_targets(s_nodes),
            trace=_trace,
        )
        if sigma_result is not None:
            return sigma_result

        _trace.append(
            f"[SID] Base ID returned {base_result.status.value} — "
            "stochastic ID inherits non-identifiability"
        )
        return dataclasses.replace(
            base_result,
            trace=_trace,
            algorithm_version="sid_v2",
            metadata={
                **dict(getattr(base_result, "metadata", {}) or {}),
                **_policy_metadata(policy),
            },
        )

    # Base ID succeeded — wrap the inner estimand in a stochastic node
    inner_do_node = base_result.estimand_ast.root  # type: ignore[union-attr]

    rule = _SID_SHIFT if policy.policy_type == "shift" else _SID_POLICY_WRAP
    _steps.append(
        ProofStep(
            rule_name=rule,
            antecedent_vars=tuple(sorted(treatment)),
            consequent_vars=tuple(sorted(outcome)),
            applied_to_graph_state=(
                f"policy_type={policy.policy_type}; "
                f"wrapped P({y_str}|do({t_str})) in StochasticInterventionNode"
            ),
            depth=0,
        )
    )
    wrapper_kind = (
        "ModifiedTreatmentPolicyNode"
        if policy.policy_type == "shift"
        else "StochasticInterventionNode"
    )
    _trace.append(
        f"[SID] IDENTIFIED — wrapped base estimand in {wrapper_kind} "
        f"(policy_type={policy.policy_type})"
    )

    identification_method = (
        "sid_shift" if policy.policy_type == "shift" else f"sid_{policy.policy_type}"
    )
    base_side_conditions = (
        tuple(base_result.estimand_ast.side_conditions)
        if base_result.estimand_ast is not None
        else ()
    )
    ast = _make_policy_estimand_ast(
        treatment=treatment,
        outcome=outcome,
        policy=policy,
        inner_do_node=inner_do_node,
        domain=domain,
        dataset_ref=dataset_ref,
        identification_method=identification_method,
        side_conditions=base_side_conditions
        + _policy_side_conditions(
            treatment=treatment,
            policy=policy,
        ),
    )
    return IdentificationResult(
        status=IdentificationStatus.IDENTIFIED,
        estimand_ast=ast,
        hedge_certificate=None,
        trace=_trace,
        required_distributions=base_result.required_distributions,
        algorithm_version="sid_v2",
        proof_steps=_steps + list(base_result.proof_steps),
        metadata={
            **dict(getattr(base_result, "metadata", {}) or {}),
            **_policy_metadata(policy),
        },
    )


def conditional_intervention_id(
    *,
    treatment: frozenset[str],
    outcome: frozenset[str],
    condition_vars: frozenset[str],
    graph: CausalGraphModel,
    available_vars: frozenset[str] | None = None,
    dataset_ref: str | None = None,
    domain: DistributionDomain = DistributionDomain.SOURCE,
) -> IdentificationResult:
    """Identify P(Y | do(X | Z=z)) — conditional intervention (Pearl 2009, §4.2).

    A conditional intervention do(X|Z=z) applies the treatment only within the
    subpopulation where Z=z.  Formally this equals the standard ID estimand
    P(Y|do(X)) evaluated within that stratum.

    Algorithm
    ---------
    1. Run id_algorithm(X, Y, graph) to get P(Y|do(X)).
    2. If identified, wrap the inner estimand in a :class:`ConditionalInterventionNode`
       recording the conditioning variables Z.
    3. Estimation delegates to an AIPW/TMLE restricted to the Z=z stratum.

    Parameters
    ----------
    treatment:
        X — treatment variable(s).
    outcome:
        Y — outcome variable(s).
    condition_vars:
        Z — variables defining the conditioning subpopulation.
    graph, available_vars, dataset_ref, domain:
        Standard ID algorithm inputs.

    References
    ----------
    Pearl, J. (2009). *Causality*, 2nd ed., §4.2. Cambridge University Press.
    """
    _trace: list[str] = []
    _steps: list[ProofStep] = []

    t_str = next(iter(sorted(treatment))) if len(treatment) == 1 else str(sorted(treatment))
    y_str = next(iter(sorted(outcome))) if len(outcome) == 1 else str(sorted(outcome))
    z_sorted = sorted(condition_vars)

    _trace.append(
        f"[COND-DO] conditional_intervention_id("
        f"X={sorted(treatment)}, Y={sorted(outcome)}, Z={z_sorted})"
    )

    # Step 1: standard ID on the full graph
    base_result = id_algorithm(
        treatment=treatment,
        outcome=outcome,
        graph=graph,
        dataset_ref=dataset_ref,
        domain=domain,
        available_vars=available_vars,
    )
    _trace.extend(base_result.trace)

    if base_result.status is not IdentificationStatus.IDENTIFIED:
        _trace.append(
            f"[COND-DO] Base ID returned {base_result.status.value} — "
            "conditional ID inherits non-identifiability"
        )
        return dataclasses.replace(
            base_result,
            trace=_trace,
            algorithm_version="cond_do_v1",
        )

    # Step 2: wrap in ConditionalInterventionNode
    cond_node = ConditionalInterventionNode(
        treatment=t_str,
        outcome=y_str,
        condition_vars=tuple(z_sorted),
        inner_do_node=base_result.estimand_ast.root,  # type: ignore[union-attr]
        domain=domain,
        dataset_ref=dataset_ref,
    )
    _steps.append(
        ProofStep(
            rule_name=_SID_CONDITIONAL,
            antecedent_vars=tuple(sorted(treatment)),
            consequent_vars=tuple(sorted(outcome)),
            applied_to_graph_state=(
                f"do(X|Z={z_sorted}): standard ID succeeded; "
                f"wrapped in ConditionalInterventionNode(condition_vars={z_sorted})"
            ),
            depth=0,
        )
    )
    _trace.append(f"[COND-DO] IDENTIFIED — wrapped in ConditionalInterventionNode(Z={z_sorted})")

    ast = EstimandAST(
        query_str=f"P({y_str}|do({t_str}|Z={z_sorted}))",
        root=cond_node,
        treatment=t_str,
        outcome=y_str,
        all_variables=tuple(sorted(treatment | outcome | condition_vars)),
        identification_method="conditional_do",
    )
    return IdentificationResult(
        status=IdentificationStatus.IDENTIFIED,
        estimand_ast=ast,
        hedge_certificate=None,
        trace=_trace,
        required_distributions=base_result.required_distributions,
        algorithm_version="cond_do_v1",
        proof_steps=_steps + list(base_result.proof_steps),
    )


def dynamic_intervention_id(
    *,
    treatment_sequence: list[str],
    outcome: str,
    graph: CausalGraphModel,
    time_points: list[int],
    covariate_sequence: list[str] | None = None,
    dataset_ref: str | None = None,
    domain: DistributionDomain = DistributionDomain.SOURCE,
) -> IdentificationResult:
    """Identify P(Y^ā) for a sequential / dynamic treatment regime ā = (A_0,...,A_T).

    The identification reduces to the *g-computation formula* (Robins 1986):

        P(Y^ā) = Σ_{l̄} ∏_t P(L_t | ā_{t-1}, l̄_{t-1}) × E[Y | ā, l̄]

    Sequential ignorability is checked graphically: for each time point t,
    we require L_t ⊥ A_t | (ā_{t-1}, l̄_{t-1}) in G_{do(A_1,...,A_{t-1})}.

    Parameters
    ----------
    treatment_sequence:
        Ordered list of treatment variables [A_0, A_1, ..., A_T].
    outcome:
        Terminal outcome variable Y.
    graph:
        Causal DAG encoding the longitudinal data-generating process.
    time_points:
        Integer time indices corresponding to each treatment in the sequence.
    covariate_sequence:
        Optional ordered list of time-varying covariate variables [L_0, ..., L_T].
        Defaults to all non-treatment, non-outcome graph nodes.
    dataset_ref, domain:
        Standard estimand metadata.

    References
    ----------
    Robins, J.M. (1986). "A New Approach to Causal Inference in Mortality
        Studies with a Sustained Exposure Period." Math Modelling, 7, 1393–1512.
    Hernán, M.A. & Robins, J.M. (2020). *Causal Inference: What If.*
        Chapman & Hall.
    """
    _trace: list[str] = []
    _steps: list[ProofStep] = []

    T = len(treatment_sequence)
    all_nodes = set(graph.nodes)

    if covariate_sequence is None:
        reserved = set(treatment_sequence) | {outcome}
        covariate_sequence = [v for v in sorted(all_nodes - reserved)]

    _trace.append(f"[DYN-ID] dynamic_intervention_id(A={treatment_sequence}, Y={outcome}, T={T})")

    # --- Sequential ignorability check (graphical) ---
    si_satisfied = True
    si_warnings: list[str] = []
    for t_idx, at in enumerate(treatment_sequence):
        prev_treatments = frozenset(treatment_sequence[:t_idx])
        # Check A_t ⊥ Y | prev_treatments, covariates in the mutilated graph
        mutilated = do_operator(graph, prev_treatments) if prev_treatments else graph
        y_ancestors = ancestors(mutilated, frozenset({outcome}))
        # A_t should not be an ancestor of Y through a back-door path
        # Simplified check: no unblocked paths from A_t back-doors after mutilation
        at_node_set = frozenset({at})
        # m-separation: A_t independent of time-lagged confounders given history
        remaining_confounders = y_ancestors - frozenset(treatment_sequence) - frozenset({outcome})
        if remaining_confounders:
            sep_ok = m_separation(
                mutilated,
                x_set=at_node_set,
                y_set=frozenset({outcome}),
                z_set=prev_treatments | frozenset(covariate_sequence),
            )
            if not sep_ok:
                si_satisfied = False
                si_warnings.append(
                    f"Sequential ignorability potentially violated at t={t_idx}: "
                    f"A_{t_idx}={at} not m-separated from Y given history"
                )

    if not si_satisfied:
        warning_str = "; ".join(si_warnings)
        _trace.append(f"[DYN-ID] Sequential ignorability check: WARNINGS — {warning_str}")
        _steps.append(
            ProofStep(
                rule_name=_DYNAMIC_GFORMULA,
                antecedent_vars=tuple(treatment_sequence),
                consequent_vars=(outcome,),
                applied_to_graph_state=f"Sequential ignorability warnings: {warning_str}",
                depth=0,
            )
        )
        # Still emit the g-formula estimand with a side-condition warning
        # (the estimand is correct *if* the user asserts SI holds)

    # Build g-formula estimand as a ProductNode of sequential conditional factors
    # P(Y^ā) = Σ_{l̄} ∏_t P(L_t|Ā_{t-1},L̄_{t-1}) · E[Y|Ā,L̄]
    factors = []

    # Time-varying covariate densities P(L_t | history)
    for t_idx, lt in enumerate(covariate_sequence):
        history_treatments = tuple(treatment_sequence[:t_idx])
        history_covariates = tuple(covariate_sequence[:t_idx])
        cond_set = history_treatments + history_covariates
        factors.append(
            DistributionRef(
                domain=domain,
                variables=(lt,),
                conditioning=cond_set,
                dataset_ref=dataset_ref,
                intervention_set=(),
            )
        )

    # Outcome model E[Y | full treatment + covariate history]
    outcome_factor = DistributionRef(
        domain=domain,
        variables=(outcome,),
        conditioning=tuple(treatment_sequence) + tuple(covariate_sequence),
        dataset_ref=dataset_ref,
        intervention_set=tuple(treatment_sequence),
    )
    factors.append(outcome_factor)

    all_covariate_vars = tuple(covariate_sequence)
    if factors:
        if len(factors) == 1:
            inner_node = factors[0]
        else:
            inner_node = ProductNode(factors=tuple(factors))
    else:
        inner_node = outcome_factor

    root = (
        SumNode(
            summation_vars=all_covariate_vars,
            operand=inner_node,
        )
        if all_covariate_vars
        else inner_node
    )

    si_note = (
        "sequential_ignorability_assumed" if si_satisfied else "sequential_ignorability_warnings"
    )
    _steps.append(
        ProofStep(
            rule_name=_DYNAMIC_GFORMULA,
            antecedent_vars=tuple(treatment_sequence),
            consequent_vars=(outcome,),
            applied_to_graph_state=(
                f"g-formula T={T}: {len(covariate_sequence)} time-varying covariates; {si_note}"
            ),
            depth=0,
        )
    )
    _trace.append(f"[DYN-ID] IDENTIFIED via g-formula (T={T}, {si_note})")

    t_label = str(treatment_sequence)
    ast = EstimandAST(
        query_str=f"P({outcome}^ā; ā={treatment_sequence})",
        root=root,
        treatment=treatment_sequence[0] if treatment_sequence else "",
        outcome=outcome,
        all_variables=tuple(sorted(set(treatment_sequence) | set(covariate_sequence) | {outcome})),
        identification_method="dynamic_g_formula",
    )
    all_dist_refs = [
        DistributionRef(
            domain=domain,
            variables=(v,),
            dataset_ref=dataset_ref,
        )
        for v in sorted(set(treatment_sequence) | set(covariate_sequence) | {outcome})
    ]
    return IdentificationResult(
        status=IdentificationStatus.IDENTIFIED,
        estimand_ast=ast,
        hedge_certificate=None,
        trace=_trace,
        required_distributions=all_dist_refs,
        algorithm_version="dynamic_g_formula_v1",
        proof_steps=_steps,
    )


# ---------------------------------------------------------------------------
# 5.2  Multi-Outcome and Joint Interventions
# ---------------------------------------------------------------------------


def joint_id_algorithm(
    *,
    treatments: frozenset[str],
    outcomes: frozenset[str],
    graph: CausalGraphModel,
    available_vars: frozenset[str] | None = None,
    dataset_ref: str | None = None,
    domain: DistributionDomain = DistributionDomain.SOURCE,
) -> IdentificationResult:
    """Identify P(Y₁,...,Yₖ | do(X₁,...,Xₘ)) via c-component factorisation.

    Implements Tian (2002): factor the joint interventional distribution via
    c-components of G \\ X, then identify each factor independently.  A single
    c-component decomposition is computed and shared across all outcome factors,
    making this more efficient than K independent ID calls.

    Algorithm
    ---------
    1. Compute c-components {S_1,...,S_k} of G[V \\ X].
    2. Partition outcomes Y into groups Y_i = Y ∩ S_i.
    3. For each non-empty Y_i run id_algorithm(X, Y_i, G[S_i ∪ X]).
    4. If all factors are identified, combine via ProductNode over all estimands.

    Parameters
    ----------
    treatments:
        X — set of treatment variable(s) being fixed.
    outcomes:
        Y — set of all target outcome variable(s).
    graph, available_vars, dataset_ref, domain:
        Standard ID algorithm inputs.

    References
    ----------
    Tian, J. (2002). "Studies in Causal Reasoning and Learning." PhD thesis,
        UCLA.  (Joint identification via c-component factorisation.)
    Tian, J. & Pearl, J. (2002). "A General Identification Condition for
        Causal Effects." AAAI 2002.
    """
    _trace: list[str] = []
    _steps: list[ProofStep] = []

    if available_vars is None:
        available_vars = frozenset(graph.nodes)

    t_str = str(sorted(treatments)) if len(treatments) != 1 else next(iter(sorted(treatments)))
    y_str = str(sorted(outcomes)) if len(outcomes) != 1 else next(iter(sorted(outcomes)))

    _trace.append(f"[JOINT-ID] joint_id_algorithm(X={sorted(treatments)}, Y={sorted(outcomes)})")

    # Degenerate case: single treatment, single outcome → standard ID
    if len(outcomes) == 1 and len(treatments) == 1:
        return id_algorithm(
            treatment=treatments,
            outcome=outcomes,
            graph=graph,
            dataset_ref=dataset_ref,
            domain=domain,
            available_vars=available_vars,
        )

    # Step 1: Compute c-components of G \ X
    g_minus_x = induced_subgraph(graph, available_vars - treatments)
    comps = c_components(g_minus_x)  # list[frozenset[str]]

    _trace.append(f"[JOINT-ID] c-components of G\\X: {[sorted(c) for c in comps]}")
    _steps.append(
        ProofStep(
            rule_name=_JOINT_FACTOR_DECOMPOSE,
            antecedent_vars=tuple(sorted(treatments)),
            consequent_vars=tuple(sorted(outcomes)),
            applied_to_graph_state=(
                f"c-components of G\\X computed once: {[sorted(c) for c in comps]}"
            ),
            depth=0,
        )
    )

    # Step 2: group outcomes by c-component
    comp_outcome_groups: list[tuple[frozenset[str], frozenset[str]]] = []
    unassigned = set(outcomes)
    for comp in comps:
        y_in_comp = outcomes & comp
        if y_in_comp:
            comp_outcome_groups.append((comp, y_in_comp))
            unassigned -= y_in_comp

    if unassigned:
        # Outcomes not in any c-component of G\X → they may be in X or unreachable
        _trace.append(
            f"[JOINT-ID] Unassigned outcomes {sorted(unassigned)} — "
            "not in any c-component of G\\X; treating as trivially identified"
        )
        # Add them as trivial factors
        for v in sorted(unassigned):
            comp_outcome_groups.append((frozenset({v}), frozenset({v})))

    # Step 3: identify each factor
    all_identified = True
    factor_estimands: list[Any] = []
    all_required: list[DistributionRef] = []
    last_failed_result: IdentificationResult | None = None

    for comp, y_group in comp_outcome_groups:
        sub_vars = (comp | treatments) & available_vars
        sub_graph = induced_subgraph(graph, sub_vars)
        factor_result = id_algorithm(
            treatment=treatments,
            outcome=y_group,
            graph=sub_graph,
            dataset_ref=dataset_ref,
            domain=domain,
            available_vars=sub_vars,
        )
        _trace.extend(factor_result.trace)
        all_required.extend(factor_result.required_distributions)

        if factor_result.status is not IdentificationStatus.IDENTIFIED:
            _trace.append(
                f"[JOINT-ID] Factor for Y_group={sorted(y_group)} "
                f"FAILED: {factor_result.status.value}"
            )
            all_identified = False
            last_failed_result = factor_result
            break

        factor_estimands.append(factor_result.estimand_ast.root)  # type: ignore[union-attr]
        _trace.append(f"[JOINT-ID] Factor for Y_group={sorted(y_group)} IDENTIFIED")

    if not all_identified:
        _trace.append("[JOINT-ID] Joint identification FAILED — returning last failed result")
        return dataclasses.replace(
            last_failed_result,  # type: ignore[arg-type]
            trace=_trace,
            proof_steps=_steps + list(last_failed_result.proof_steps),  # type: ignore[union-attr]
            algorithm_version="joint_id_v1",
        )

    # Step 4: combine factors into joint ProductNode
    if len(factor_estimands) == 1:
        joint_root = factor_estimands[0]
    else:
        joint_root = ProductNode(factors=tuple(factor_estimands))

    _steps.append(
        ProofStep(
            rule_name=_JOINT_FACTOR_DECOMPOSE,
            antecedent_vars=tuple(sorted(treatments)),
            consequent_vars=tuple(sorted(outcomes)),
            applied_to_graph_state=(
                f"Joint identification SUCCEEDED: "
                f"{len(factor_estimands)} factors combined into ProductNode"
            ),
            depth=0,
        )
    )
    _trace.append(f"[JOINT-ID] IDENTIFIED — {len(factor_estimands)} factor(s) as ProductNode")

    ast = EstimandAST(
        query_str=f"P({y_str}|do({t_str}))",
        root=joint_root,
        treatment=t_str,
        outcome=y_str,
        all_variables=tuple(sorted(treatments | outcomes)),
        identification_method="joint_id_c_component",
    )
    return IdentificationResult(
        status=IdentificationStatus.IDENTIFIED,
        estimand_ast=ast,
        hedge_certificate=None,
        trace=_trace,
        required_distributions=list(dict.fromkeys((str(d), d) for d in all_required).values())
        if all_required
        else [],
        algorithm_version="joint_id_v1",
        proof_steps=_steps,
    )


def multi_outcome_id(
    *,
    treatment: frozenset[str],
    outcomes: list[str],
    graph: CausalGraphModel,
    available_vars: frozenset[str] | None = None,
    dataset_ref: str | None = None,
    domain: DistributionDomain = DistributionDomain.SOURCE,
) -> dict[str, IdentificationResult]:
    """Identify P(Yᵢ|do(X)) for each Yᵢ, sharing one c-component decomposition.

    More efficient than K independent :func:`id_algorithm` calls when all
    outcomes share the same treatment and graph.  The c-components of G \\ X are
    computed once, then each outcome Y_i is resolved within its component.

    Parameters
    ----------
    treatment:
        X — treatment variable(s).
    outcomes:
        List of outcome variable names to identify simultaneously.
    graph, available_vars, dataset_ref, domain:
        Standard ID algorithm inputs.

    Returns
    -------
    dict[str, IdentificationResult]
        Keyed by outcome variable name.  Each value is a standard
        :class:`IdentificationResult` (IDENTIFIED or failure).
    """
    if available_vars is None:
        available_vars = frozenset(graph.nodes)

    _trace: list[str] = []
    _trace.append(f"[MULTI-ID] multi_outcome_id(X={sorted(treatment)}, Y_list={outcomes})")

    # Shared c-component decomposition
    g_minus_x = induced_subgraph(graph, available_vars - treatment)
    comps = c_components(g_minus_x)

    _trace.append(f"[MULTI-ID] Shared c-components of G\\X: {[sorted(c) for c in comps]}")

    # Map each outcome to its c-component for efficient sub-graph selection
    outcome_to_comp: dict[str, frozenset[str]] = {}
    for y_var in outcomes:
        for comp in comps:
            if y_var in comp:
                outcome_to_comp[y_var] = comp
                break
        if y_var not in outcome_to_comp:
            # Not in any c-component — treat as singleton
            outcome_to_comp[y_var] = frozenset({y_var})

    results: dict[str, IdentificationResult] = {}
    shared_step = ProofStep(
        rule_name=_MULTI_OUTCOME_SHARED_CCOMP,
        antecedent_vars=tuple(sorted(treatment)),
        consequent_vars=tuple(outcomes),
        applied_to_graph_state=(
            f"Shared c-component decomposition for {len(outcomes)} outcomes: "
            f"{[sorted(c) for c in comps]}"
        ),
        depth=0,
    )

    for y_var in outcomes:
        comp = outcome_to_comp[y_var]
        sub_vars = (comp | treatment) & available_vars
        sub_graph = induced_subgraph(graph, sub_vars)
        result = id_algorithm(
            treatment=treatment,
            outcome=frozenset({y_var}),
            graph=sub_graph,
            dataset_ref=dataset_ref,
            domain=domain,
            available_vars=sub_vars,
        )
        # Prepend the shared c-component step to each result's proof steps
        results[y_var] = dataclasses.replace(
            result,
            proof_steps=[shared_step] + list(result.proof_steps),
            algorithm_version="multi_outcome_id_v1",
        )
        _trace.append(f"[MULTI-ID] Y={y_var} → {result.status.value}")

    return results


__all__ = [name for name in globals() if not name.startswith("__")]
