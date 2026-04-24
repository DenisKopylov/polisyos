"""Conservative proximal identification prover for PCI-Core graphs.

This module implements the v1 Stage 11.1 surface: a sound, intentionally
incomplete proximal bridge identifier that emits machine-checkable certificates
for canonical single-treatment/single-outcome proximal settings.
"""

from __future__ import annotations

from collections import deque
from itertools import combinations
from typing import TYPE_CHECKING, Any

from polisyos.foundry.methods.catalog.causal.admg_ops import c_components
from polisyos.ir.analytics.causal_graph import CausalGraphModel, EdgeMark, GraphType
from polisyos.ir.analytics.negative_certificate import (
    BlockingType,
    NegativeCertificate,
)
from polisyos.ir.analytics.proximal import (
    BridgeFunctionSpec,
    IdentifiedFunctional,
    ProximalAssumption,
    ProximalGraphCheck,
    ProximalIdentificationCertificate,
    ProximalQuerySpec,
    ProxyAnnotation,
)

if TYPE_CHECKING:
    from polisyos.ir.analytics.causal_queries import CausalQuery

PROXIMAL_V1_ALGORITHM = "proximal_id_v1_pci_core"
PROXIMAL_SPATIAL_V1_ALGORITHM = "proximal_spatial_id_v1"


def proximal_identify_v1(
    graph: CausalGraphModel,
    query: CausalQuery,
    proxies: ProxyAnnotation | dict[str, Any],
) -> ProximalIdentificationCertificate | NegativeCertificate:
    """Identify a canonical proximal ATE query or explain the failed condition.

    The covered PCI-Core class is conservative: DAG/ADMG inputs, one treatment,
    one outcome, non-empty Z/W proxy sets, no A-to-W directed path, no
    Z-to-Y directed path avoiding A, and bidirected district relevance for
    A/Y and the declared proxies.
    """

    proxy_annotation = (
        proxies if isinstance(proxies, ProxyAnnotation) else ProxyAnnotation.model_validate(proxies)
    )
    treatment = query.treatment_variable
    outcome = query.outcome_variable
    covariates = proxy_annotation.covariates
    trace = [
        "Started PCI-Core proximal v1 identification.",
        f"Query target={proxy_annotation.estimand} treatment={treatment} outcome={outcome}.",
    ]

    query_type = str(getattr(query.query_type, "value", query.query_type) or "")
    if query_type != "interventional":
        return _negative(
            check="query_type_supported",
            blocking_type=BlockingType.OUT_OF_SCOPE_FOR_PROXIMAL_V1,
            description="Proximal v1 only supports interventional mean-effect queries.",
            detail=f"Received query_type={query_type or 'unknown'}.",
            trace=trace,
            witness={"query_type": query_type or "unknown"},
        )

    if graph.graph_type not in {GraphType.ADMG, GraphType.DAG}:
        return _negative(
            check="graph_type_supported",
            blocking_type=BlockingType.OUT_OF_SCOPE_FOR_PROXIMAL_V1,
            description=(
                "Proximal v1 only supports DAG/ADMG graphs with directed and bidirected edges."
            ),
            detail=f"Received graph_type={graph.graph_type.value}.",
            trace=trace,
            witness={"graph_type": graph.graph_type.value},
        )

    node_set = set(graph.nodes)
    referenced = {
        treatment,
        outcome,
        *proxy_annotation.treatment_inducing,
        *proxy_annotation.outcome_inducing,
        *covariates,
    }
    missing = tuple(sorted(referenced - node_set))
    if missing:
        return _negative(
            check="variables_present",
            blocking_type=BlockingType.PROXIMAL_CONDITION_FAILED,
            description="The proximal query references variables that are absent from the graph.",
            detail=f"Missing variables: {list(missing)}.",
            trace=trace,
            witness={"missing_variables": list(missing)},
            missing_vars=missing,
        )

    if not proxy_annotation.treatment_inducing or not proxy_annotation.outcome_inducing:
        return _negative(
            check="proxy_sets_non_empty",
            blocking_type=BlockingType.PROXIMAL_CONDITION_FAILED,
            description="Proximal v1 requires non-empty treatment- and outcome-proxy sets.",
            detail=(
                "Both treatment_inducing (Z) and outcome_inducing (W) proxy "
                "annotations are required."
            ),
            trace=trace,
            witness={
                "treatment_inducing": list(proxy_annotation.treatment_inducing),
                "outcome_inducing": list(proxy_annotation.outcome_inducing),
            },
        )

    disjoint_failure = _first_overlap(
        {
            "treatment": {treatment},
            "outcome": {outcome},
            "treatment_inducing": set(proxy_annotation.treatment_inducing),
            "outcome_inducing": set(proxy_annotation.outcome_inducing),
            "covariates": set(covariates),
        }
    )
    if disjoint_failure is not None:
        left, right, overlap = disjoint_failure
        return _negative(
            check="proxy_annotation_disjoint",
            blocking_type=BlockingType.PROXIMAL_CONDITION_FAILED,
            description=(
                "Proximal v1 requires treatment, outcome, proxies, and covariates to be disjoint."
            ),
            detail=f"{left} and {right} overlap on {sorted(overlap)}.",
            trace=trace,
            witness={"left": left, "right": right, "overlap": sorted(overlap)},
            missing_vars=tuple(sorted(overlap)),
        )

    graph_checks = [
        ProximalGraphCheck(
            check="proxy_annotation_disjoint",
            status="pass",
            requirements=(
                "A, Y, treatment-inducing proxies, outcome-inducing proxies, "
                "and X are pairwise disjoint",
            ),
        )
    ]

    for w_proxy in proxy_annotation.outcome_inducing:
        path = _directed_path(graph, treatment, w_proxy)
        if path:
            return _negative(
                check="no_directed_path_A_to_W",
                blocking_type=BlockingType.PROXIMAL_CONDITION_FAILED,
                description="An outcome-inducing proxy has a directed causal path from treatment.",
                detail=f"Found directed path from {treatment} to {w_proxy}: {' -> '.join(path)}.",
                trace=trace,
                witness={
                    "violation_code": "DIRECTED_PATH_FOUND",
                    "from": treatment,
                    "to": w_proxy,
                    "path": path,
                },
                missing_vars=(w_proxy,),
            )
    graph_checks.append(
        ProximalGraphCheck(
            check="no_directed_path_A_to_W",
            status="pass",
            source=treatment,
            target_set=proxy_annotation.outcome_inducing,
            detail="No directed path from treatment to any W-proxy was found.",
        )
    )

    for z_proxy in proxy_annotation.treatment_inducing:
        path = _directed_path(graph, z_proxy, outcome, forbidden_nodes={treatment})
        if path:
            return _negative(
                check="no_directed_path_Z_to_Y_without_A",
                blocking_type=BlockingType.PROXIMAL_CONDITION_FAILED,
                description=(
                    "A treatment-inducing proxy has a directed path to outcome "
                    "that avoids treatment."
                ),
                detail=(
                    f"Found directed path from {z_proxy} to {outcome} avoiding "
                    f"{treatment}: {' -> '.join(path)}."
                ),
                trace=trace,
                witness={
                    "violation_code": "DIRECTED_PATH_FOUND_WITHOUT_A",
                    "from": z_proxy,
                    "to": outcome,
                    "forbidden_node": treatment,
                    "path": path,
                },
                missing_vars=(z_proxy,),
            )
    graph_checks.append(
        ProximalGraphCheck(
            check="no_directed_path_Z_to_Y_without_A",
            status="pass",
            source_set=proxy_annotation.treatment_inducing,
            target=outcome,
            detail=(
                "No directed path from any Z-proxy to outcome was found after removing treatment."
            ),
        )
    )

    district_check = _check_district_relevance(
        graph=graph,
        treatment=treatment,
        outcome=outcome,
        proxies=proxy_annotation,
    )
    if district_check.status == "fail":
        return _negative(
            check="district_relevance",
            blocking_type=BlockingType.PROXIMAL_CONDITION_FAILED,
            description="The declared proxies are not in the required bidirected districts.",
            detail=district_check.detail,
            trace=trace,
            witness=district_check.witness,
            missing_vars=(
                *proxy_annotation.treatment_inducing,
                *proxy_annotation.outcome_inducing,
            ),
        )
    graph_checks.append(district_check)

    cert = ProximalIdentificationCertificate(
        query=ProximalQuerySpec(
            estimand=proxy_annotation.estimand,
            treatment=(treatment,),
            outcome=(outcome,),
            covariates=covariates,
        ),
        proxies=proxy_annotation,
        graph_checks=tuple(graph_checks),
        bridge_functions=_bridge_specs(
            treatment=treatment,
            outcome=outcome,
            proxies=proxy_annotation,
        ),
        identified_functionals=_identified_functionals(
            proxies=proxy_annotation,
        ),
        assumptions=(
            "consistency",
            "positivity",
            "proxy_independence",
            "bridge_existence",
            "completeness",
        ),
        proof_trace=(
            *trace,
            "Matched PCI-Core graphical pattern.",
            "Declared proximal bridge equation(s).",
            "Applied proximal bridge identification functional.",
        ),
        metadata={
            "algorithm": PROXIMAL_V1_ALGORITHM,
            "method": "proximal_bridge",
            "theorem_family": "proximal_id",
            "soundness_scope": (
                "Sound under checked PCI-Core graph conditions plus explicit "
                "bridge existence, positivity, consistency, proxy independence, "
                "and completeness assumptions."
            ),
        },
    )
    return cert


def proximal_spatial_identify_v1(
    graph: CausalGraphModel,
    query: CausalQuery,
    proxies: ProxyAnnotation | dict[str, Any],
) -> ProximalIdentificationCertificate | NegativeCertificate:
    """Certify a conservative spatial-proximal extension of PCI-Core.

    The spatial v1 surface layers buffered ring-lag checks on top of the
    existing PCI-Core certificate. It remains intentionally incomplete:
    point identification is only certified when the proxy metadata declares
    two spatial proxy families and excludes contemporaneous unbuffered
    outcome proxies that would violate proximal exclusion under spillovers.
    """

    proxy_annotation = (
        proxies if isinstance(proxies, ProxyAnnotation) else ProxyAnnotation.model_validate(proxies)
    )
    base_result = proximal_identify_v1(graph, query, proxy_annotation)
    if isinstance(base_result, NegativeCertificate):
        return base_result

    trace = [
        *base_result.proof_trace,
        "Started spatial proximal v1 extension checks.",
    ]
    spatial_specs = tuple(proxy_annotation.spatial_proxy_specs)
    if not spatial_specs:
        return _negative(
            check="spatial_proxy_specs_present",
            blocking_type=BlockingType.PROXIMAL_CONDITION_FAILED,
            description="Spatial proximal v1 requires declared spatial proxy construction metadata.",
            detail=(
                "Provide spatial_proxy_specs with ring-lag, buffer, time-mode, and "
                "spillover-radius claims for the declared proxies."
            ),
            trace=trace,
            witness={"required_fields": ["lag_orders", "buffer_radius", "time_mode"]},
            missing_vars=(
                *proxy_annotation.treatment_inducing,
                *proxy_annotation.outcome_inducing,
            ),
            algorithm_version=PROXIMAL_SPATIAL_V1_ALGORITHM,
        )

    graph_checks = list(base_result.graph_checks)
    graph_checks.append(
        ProximalGraphCheck(
            check="spatial_proxy_specs_present",
            status="pass",
            source_set=proxy_annotation.treatment_inducing,
            target_set=proxy_annotation.outcome_inducing,
            requirements=("Spatial proxy construction metadata declared for proximal proxies",),
            detail="Spatial proxy specifications were provided for the declared proxy sets.",
        )
    )

    roles_covered = {role for spec in spatial_specs for role in spec.allowed_roles}
    if not {"treatment_inducing", "outcome_inducing"} <= roles_covered:
        return _negative(
            check="spatial_proxy_roles_covered",
            blocking_type=BlockingType.PROXIMAL_CONDITION_FAILED,
            description="Spatial proximal v1 requires both treatment- and outcome-inducing proxy families.",
            detail=(
                "The declared spatial_proxy_specs must cover both treatment_inducing "
                "and outcome_inducing roles."
            ),
            trace=trace,
            witness={"roles_covered": sorted(roles_covered)},
            missing_vars=(
                *proxy_annotation.treatment_inducing,
                *proxy_annotation.outcome_inducing,
            ),
            algorithm_version=PROXIMAL_SPATIAL_V1_ALGORITHM,
        )
    graph_checks.append(
        ProximalGraphCheck(
            check="spatial_proxy_roles_covered",
            status="pass",
            requirements=(
                "At least one spatial proxy family covers treatment-inducing proxies",
                "At least one spatial proxy family covers outcome-inducing proxies",
            ),
            witness={"roles_covered": sorted(roles_covered)},
            detail="Spatial proxy role coverage is sufficient for proximal spatial v1.",
        )
    )

    z_ring_orders = sorted(
        {
            lag
            for spec in spatial_specs
            if "treatment_inducing" in spec.allowed_roles
            for lag in spec.lag_orders
        }
    )
    w_ring_orders = sorted(
        {
            lag
            for spec in spatial_specs
            if "outcome_inducing" in spec.allowed_roles
            for lag in spec.lag_orders
        }
    )
    if not z_ring_orders or not w_ring_orders or len(set(z_ring_orders + w_ring_orders)) < 2:
        return _negative(
            check="ring_specific_rank_support",
            blocking_type=BlockingType.PROXIMAL_CONDITION_FAILED,
            description=(
                "Spatial proximal v1 requires distinct ring-lag support across the two proxy families."
            ),
            detail=(
                "Declare at least one treatment-inducing ring and one outcome-inducing "
                "ring, with non-degenerate lag support across the two families."
            ),
            trace=trace,
            witness={
                "treatment_ring_orders": z_ring_orders,
                "outcome_ring_orders": w_ring_orders,
            },
            missing_vars=(
                *proxy_annotation.treatment_inducing,
                *proxy_annotation.outcome_inducing,
            ),
            algorithm_version=PROXIMAL_SPATIAL_V1_ALGORITHM,
        )
    graph_checks.append(
        ProximalGraphCheck(
            check="ring_specific_rank_support",
            status="pass",
            requirements=(
                "Treatment- and outcome-proxy families expose non-degenerate ring-lag support",
            ),
            witness={
                "treatment_ring_orders": z_ring_orders,
                "outcome_ring_orders": w_ring_orders,
            },
            detail="Distinct ring-lag families were declared for the spatial proxy sets.",
        )
    )

    for spec in spatial_specs:
        if "outcome_inducing" not in spec.allowed_roles or spec.time_mode != "contemporaneous":
            continue
        spillover_radius = (
            int(spec.spillover_radius_claim) if spec.spillover_radius_claim is not None else 1
        )
        buffer_radius = int(spec.buffer_radius or 0)
        min_lag = min(spec.lag_orders)
        has_safe_buffer = max(buffer_radius, min_lag) > spillover_radius
        if (
            spec.proxy_construction
            in {
                "ring_lag",
                "buffered_ring_lag",
            }
            and not has_safe_buffer
        ):
            return _negative(
                check="buffered_spatial_proxy_exclusion",
                blocking_type=BlockingType.PROXIMAL_CONDITION_FAILED,
                description=(
                    "An outcome-inducing spatial proxy is too close to satisfy buffered exclusion."
                ),
                detail=(
                    "Contemporaneous outcome proxies require either a pre-treatment / negative-control "
                    "construction or a ring/buffer that exceeds the declared spillover radius."
                ),
                trace=trace,
                witness={
                    "proxy_variables": list(spec.proxy_variables),
                    "proxy_construction": spec.proxy_construction,
                    "time_mode": spec.time_mode,
                    "lag_orders": list(spec.lag_orders),
                    "buffer_radius": buffer_radius,
                    "spillover_radius_claim": spillover_radius,
                },
                missing_vars=tuple(spec.proxy_variables),
                algorithm_version=PROXIMAL_SPATIAL_V1_ALGORITHM,
            )
    graph_checks.append(
        ProximalGraphCheck(
            check="buffered_spatial_proxy_exclusion",
            status="pass",
            requirements=(
                "Outcome-inducing spatial proxies avoid contemporaneous unbuffered spillover paths",
            ),
            witness={
                "spatial_proxy_specs": [spec.model_dump(mode="json") for spec in spatial_specs],
            },
            detail="Declared spatial proxy specifications satisfy buffered-exclusion claims.",
        )
    )

    graph_class = base_result.graph_class.model_copy(
        update={
            "name": "PCI-Core-Spatial",
            "notes": (
                "v1 spatial proximal extension: PCI-Core plus machine-checkable "
                "buffered ring-lag proxy declarations and conservative spillover exclusions."
            ),
        }
    )
    metadata = {
        **base_result.metadata,
        "algorithm": PROXIMAL_SPATIAL_V1_ALGORITHM,
        "method": "spatial_proximal_bridge",
        "theorem_family": "proximal_spatial_id_v1",
        "implementation_coverage": "spatial_proximal_bridge_v1",
        "completeness_regime": "sound_incomplete",
        "proof_stratum": "A1_extended",
        "spatial_proxy_specs": [spec.model_dump(mode="json") for spec in spatial_specs],
        "spatial_proxy_spec": [spec.model_dump(mode="json") for spec in spatial_specs],
        "proxy_ring_diagnostics": [
            check.model_dump(mode="json")
            for check in graph_checks
            if check.check in {"ring_specific_rank_support", "buffered_spatial_proxy_exclusion"}
        ],
        "spillover_radius_claim": sorted(
            {
                int(spec.spillover_radius_claim)
                for spec in spatial_specs
                if spec.spillover_radius_claim is not None
            }
        ),
        "impact_functionals_declared": ["tau", "ADE", "AIE", "ATE_total"],
        "weight_matrix_refs": [
            spec.weight_matrix_ref for spec in spatial_specs if spec.weight_matrix_ref is not None
        ],
    }
    return base_result.model_copy(
        update={
            "graph_class": graph_class,
            "graph_checks": tuple(graph_checks),
            "proof_trace": (
                *trace,
                "Validated spatial proxy family coverage and ring-lag support.",
                "Validated buffered exclusion for contemporaneous outcome proxies.",
            ),
            "metadata": metadata,
        }
    )


def _first_overlap(groups: dict[str, set[str]]) -> tuple[str, str, set[str]] | None:
    for left, right in combinations(groups, 2):
        overlap = groups[left] & groups[right]
        if overlap:
            return left, right, overlap
    return None


def _directed_path(
    graph: CausalGraphModel,
    src: str,
    dst: str,
    *,
    forbidden_nodes: set[str] | frozenset[str] | None = None,
) -> list[str]:
    if src == dst:
        return []
    forbidden = set(forbidden_nodes or ())
    if src in forbidden or dst in forbidden:
        return []
    adjacency: dict[str, list[str]] = {node: [] for node in graph.nodes}
    for edge in graph.edges:
        if edge.mark_src is EdgeMark.TAIL and edge.mark_dst is EdgeMark.ARROW:
            if edge.lag not in (None, 0):
                continue
            if edge.src in forbidden or edge.dst in forbidden:
                continue
            adjacency.setdefault(edge.src, []).append(edge.dst)

    parents: dict[str, str | None] = {src: None}
    queue: deque[str] = deque([src])
    while queue:
        node = queue.popleft()
        for child in adjacency.get(node, []):
            if child in parents:
                continue
            parents[child] = node
            if child == dst:
                return _reconstruct_path(parents, dst)
            queue.append(child)
    return []


def _reconstruct_path(parents: dict[str, str | None], dst: str) -> list[str]:
    path = [dst]
    current = dst
    while parents[current] is not None:
        current = parents[current] or ""
        path.append(current)
    return list(reversed(path))


def _check_district_relevance(
    *,
    graph: CausalGraphModel,
    treatment: str,
    outcome: str,
    proxies: ProxyAnnotation,
) -> ProximalGraphCheck:
    components = c_components(graph)
    district_by_node = {node: component for component in components for node in component}
    treatment_district = district_by_node.get(treatment, frozenset({treatment}))
    outcome_district = district_by_node.get(outcome, frozenset({outcome}))
    witness = {
        "districts": [sorted(component) for component in components],
        "treatment_district": sorted(treatment_district),
        "outcome_district": sorted(outcome_district),
    }

    if outcome not in treatment_district:
        return ProximalGraphCheck(
            check="district_relevance",
            status="fail",
            source=treatment,
            target=outcome,
            requirements=("A and Y must lie in the same bidirected district",),
            witness={
                **witness,
                "violation_code": "DISTRICT_DISCONNECTED",
                "node": outcome,
                "required_district_of": treatment,
            },
            detail="Treatment and outcome are not in the same bidirected district.",
        )

    for z_proxy in proxies.treatment_inducing:
        if z_proxy not in treatment_district:
            return ProximalGraphCheck(
                check="district_relevance",
                status="fail",
                source=z_proxy,
                target=treatment,
                requirements=("Each Z-proxy must lie in district(A)",),
                witness={
                    **witness,
                    "violation_code": "DISTRICT_DISCONNECTED",
                    "node": z_proxy,
                    "required_district_of": treatment,
                },
                detail=f"Z-proxy {z_proxy} is not in the bidirected district of {treatment}.",
            )

    for w_proxy in proxies.outcome_inducing:
        if w_proxy not in outcome_district:
            return ProximalGraphCheck(
                check="district_relevance",
                status="fail",
                source=w_proxy,
                target=outcome,
                requirements=("Each W-proxy must lie in district(Y)",),
                witness={
                    **witness,
                    "violation_code": "DISTRICT_DISCONNECTED",
                    "node": w_proxy,
                    "required_district_of": outcome,
                },
                detail=f"W-proxy {w_proxy} is not in the bidirected district of {outcome}.",
            )

    return ProximalGraphCheck(
        check="district_relevance",
        status="pass",
        source=treatment,
        target=outcome,
        requirements=(
            "A and Y are in the same bidirected district",
            "Each Z-proxy is in district(A)",
            "Each W-proxy is in district(Y)",
        ),
        witness=witness,
        detail="All PCI-Core bidirected district relevance checks passed.",
    )


def _bridge_specs(
    *,
    treatment: str,
    outcome: str,
    proxies: ProxyAnnotation,
) -> tuple[BridgeFunctionSpec, ...]:
    z_vars = proxies.treatment_inducing
    w_vars = proxies.outcome_inducing
    x_vars = proxies.covariates
    z_a_x = _format_vars((*z_vars, treatment, *x_vars))
    w_a_x = _format_vars((*w_vars, treatment, *x_vars))
    w_x = _format_vars((*w_vars, *x_vars))
    z_x = _format_vars((*z_vars, *x_vars))

    outcome_assumption = ProximalAssumption(
        type="completeness",
        statement=(
            "If E[v(U) | Z,A,X] = 0 almost surely, then v(U) = 0 almost surely "
            "over the declared outcome-bridge function class."
        ),
        source="Miao-Shi-Tchetgen-Tchetgen; Shpitser-Wood-Doughty-Tchetgen-Tchetgen",
        machine_checkable=False,
    )
    treatment_assumption = ProximalAssumption(
        type="completeness",
        statement=(
            "If E[v(U) | W,A,X] = 0 almost surely, then v(U) = 0 almost surely "
            "over the declared treatment-bridge function class."
        ),
        source="proximal semiparametric theory",
        machine_checkable=False,
    )

    specs = [
        BridgeFunctionSpec(
            name="h",
            role="outcome_bridge",
            domain=(*w_vars, treatment, *x_vars),
            equation_type="conditional_expectation",
            equation=f"E[{outcome} | {z_a_x}] = E[h({w_a_x}) | {z_a_x}]",
            assumptions=(outcome_assumption,),
        )
    ]
    if proxies.include_treatment_bridge:
        specs.append(
            BridgeFunctionSpec(
                name="q",
                role="treatment_bridge",
                domain=(*z_vars, treatment, *x_vars),
                equation_type="integral_equation",
                equation=(
                    f"1 / f({treatment}=a | {w_x}) = integral q({z_x}, a) "
                    f"dF({z_x} | {w_x}, {treatment}=a)"
                ),
                assumptions=(treatment_assumption,),
                optional=True,
            )
        )
    return tuple(specs)


def _identified_functionals(
    *,
    proxies: ProxyAnnotation,
) -> tuple[IdentifiedFunctional, ...]:
    if proxies.estimand == "ATE":
        return (
            IdentifiedFunctional(
                target="ATE",
                expression=f"E[{_h_call(proxies, '1')} - {_h_call(proxies, '0')}]",
                preferred=True,
                bridge_role="outcome_bridge",
            ),
        )
    return (
        IdentifiedFunctional(
            target=proxies.estimand,
            expression=(
                "Bridge functional declared for v1 scope; downstream estimator "
                "must specialize ATT/mean-effect weighting."
            ),
            preferred=False,
            bridge_role="outcome_bridge",
        ),
    )


def _h_call(proxies: ProxyAnnotation, treatment_value: str) -> str:
    args = [*proxies.outcome_inducing, treatment_value, *proxies.covariates]
    return f"h({_format_vars(tuple(args))})"


def _format_vars(values: tuple[str, ...]) -> str:
    return ", ".join(values) if values else "1"


def _negative(
    *,
    check: str,
    blocking_type: BlockingType,
    description: str,
    detail: str,
    trace: list[str],
    witness: dict[str, Any] | None = None,
    missing_vars: tuple[str, ...] = (),
    algorithm_version: str = PROXIMAL_V1_ALGORITHM,
) -> NegativeCertificate:
    diagnostics = {
        "algorithm_version": algorithm_version,
        "identification_status": "non_identified",
        "failed_check": check,
        "witness": witness or {},
        "proof_trace": [*trace, f"Failed PCI-Core check: {check}."],
    }
    return NegativeCertificate(
        blocking_type=blocking_type,
        blocking_description=description,
        technical_detail=detail,
        suggested_experiments=NegativeCertificate.auto_suggest_experiments(
            blocking_type,
            missing_vars=tuple(sorted(set(missing_vars))),
        ),
        quantitative_diagnostics=diagnostics,
        constructive_message=(
            "Proximal identification was not certified. Inspect the failed_check "
            "and witness fields, then revise proxy annotations or route to a "
            "different identification strategy."
        ),
    )


__all__ = [
    "PROXIMAL_SPATIAL_V1_ALGORITHM",
    "PROXIMAL_V1_ALGORITHM",
    "proximal_identify_v1",
    "proximal_spatial_identify_v1",
]
