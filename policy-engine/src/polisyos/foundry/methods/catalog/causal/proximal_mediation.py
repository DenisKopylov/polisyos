"""Proximal mediation proof-kernel template for a single observed mediator.

Stage 11.3 adds a single-mediator proximal mediation surface for the functional
psi = E[Y{a, M(a_ref)}] under hidden confounding and observed negative-control
proxies. The implementation is intentionally conservative: it certifies one
topology, records oracle-level completeness assumptions explicitly, and falls
back to bounds when those obligations are not accepted or the nested bridge
appears numerically unsafe.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np

from polisyos.foundry.methods.catalog.causal.admg_ops import has_directed_cycle
from polisyos.foundry.methods.base import (
    ComplexityClass,
    ComputeBackend,
    FidelityLevel,
    MethodMetadata,
    MethodSignature,
    ParameterSpec,
    SlotSpec,
    SlotType,
    Unit,
    foundry_method,
)
from polisyos.foundry.methods.catalog.causal._common import (
    build_failure_report,
    build_success_report,
    wrap_causal_output,
)
from polisyos.foundry.methods.catalog.causal.frontier import (
    _bootstrap_effect_interval,
    _bridge_diagnostic_tests,
    _build_bridge_plausibility_report,
    _weighted_least_squares,
)
from polisyos.foundry.methods.catalog.causal.proximal_identify import (
    _directed_path,
    _first_overlap,
)
from polisyos.ir.analytics.causal import CausalMethod, EstimationStatus
from polisyos.ir.analytics.causal_graph import CausalGraphModel, EdgeMark, GraphType
from polisyos.ir.analytics.negative_certificate import (
    BlockingType,
    NegativeCertificate,
    negative_certificate_from_bridge_plausibility_report,
)
from polisyos.ir.analytics.partial_identification import (
    BoundMethod,
    BoundsBundle,
    PartialIdentificationResult,
    annotate_bounds_bundle_for_proximal_bridge_failure,
    bounds_bundle_from_partial_identification_result,
)
from polisyos.ir.analytics.proximal import (
    BridgeFailureMode,
    BridgeFallbackDisposition,
    ProximalGraphCheck,
    ProximalMediationBridgeEquation,
    ProximalMediationCertificate,
    ProximalMediationCompletenessCondition,
    ProximalMediationQuerySpec,
    ProxyAnnotation,
)

PROXIMAL_MEDIATION_V1_THEOREM = "proximal_mediation_thm1_dukes_2023"


def _proximal_mediation_output_slots() -> frozenset[SlotSpec]:
    return frozenset(
        {
            SlotSpec("report", SlotType.SCALAR, Unit("report", "json")),
            SlotSpec("envelope", SlotType.SCALAR, Unit("uncertainty", "json")),
            SlotSpec("warnings", SlotType.SCALAR, Unit("warning", "list")),
            SlotSpec(
                "proximal_mediation_result",
                SlotType.SCALAR,
                Unit("result", "json"),
            ),
            SlotSpec(
                "bridge_plausibility_report",
                SlotType.SCALAR,
                Unit("bridge_plausibility", "json"),
            ),
            SlotSpec("bounds_bundle", SlotType.SCALAR, Unit("bounds", "json")),
            SlotSpec(
                "negative_certificate",
                SlotType.SCALAR,
                Unit("negative_certificate", "json"),
            ),
        }
    )


def _resolve_outcome_support(
    *,
    outcome: np.ndarray | None,
    explicit_support: tuple[float, float] | None = None,
) -> tuple[float, float]:
    if explicit_support is not None:
        lower = float(explicit_support[0])
        upper = float(explicit_support[1])
        if np.isfinite(lower) and np.isfinite(upper) and lower < upper:
            return lower, upper
    if outcome is not None:
        y = np.asarray(outcome, dtype=float).reshape(-1)
        finite = y[np.isfinite(y)]
        if finite.size > 0:
            lower = float(np.min(finite))
            upper = float(np.max(finite))
            if upper - lower > 1.0e-12:
                return lower, upper
    return -1.0, 1.0


def proximal_mediation_partial_bounds(
    *,
    outcome: np.ndarray | None,
    target_effect: str,
    outcome_support: tuple[float, float] | None = None,
    assumption_tag: str = "proximal_mediation_oracle_not_accepted",
) -> PartialIdentificationResult:
    """Return a conservative v1 bounds fallback for psi/NDE/NIE.

    The current v1 backend uses support-implied outer bounds. This is honest
    under the stated bounded-outcome assumption and is the minimum acceptable
    fallback when completeness/cross-world obligations are not accepted or when
    the nested bridge appears numerically unsafe.
    """

    lower_y, upper_y = _resolve_outcome_support(
        outcome=outcome,
        explicit_support=outcome_support,
    )
    target = str(target_effect or "psi").strip().lower()
    if target == "psi":
        lower, upper = lower_y, upper_y
        label = "Support-implied proximal mediation bounds"
    else:
        lower, upper = lower_y - upper_y, upper_y - lower_y
        label = f"Support-implied proximal {target.upper()} bounds"
    return PartialIdentificationResult(
        method=BoundMethod.MANSKI,
        lower_bound=float(lower),
        upper_bound=float(upper),
        confidence=1.0,
        assumptions_used=[
            f"bounded_outcome_support in [{lower_y}, {upper_y}]",
            assumption_tag,
        ],
        bounds_type="manski",
        display_label=label,
        solver_metadata={
            "target_effect": target,
            "theorem_family": PROXIMAL_MEDIATION_V1_THEOREM,
            "outcome_support": [float(lower_y), float(upper_y)],
        },
    )


def proximal_mediation_bounds_bundle(
    *,
    outcome: np.ndarray | None,
    target_effect: str,
    outcome_support: tuple[float, float] | None = None,
    assumption_tag: str = "proximal_mediation_oracle_not_accepted",
    metadata: dict[str, Any] | None = None,
    warnings: list[str] | None = None,
) -> BoundsBundle:
    partial = proximal_mediation_partial_bounds(
        outcome=outcome,
        target_effect=target_effect,
        outcome_support=outcome_support,
        assumption_tag=assumption_tag,
    )
    bundle = bounds_bundle_from_partial_identification_result(
        partial,
        estimand_type=(
            "proximal_mediation_psi" if str(target_effect).lower() == "psi" else "path_specific_effect"
        ),
        warnings=list(warnings or []),
        metadata={
            "source": "proximal_mediation_v1_fallback",
            "target_effect": str(target_effect).lower(),
            "theorem_family": PROXIMAL_MEDIATION_V1_THEOREM,
            **dict(metadata or {}),
        },
    )
    return bundle


def _coerce_vector(value: Any) -> np.ndarray | None:
    if value is None:
        return None
    try:
        arr = np.asarray(value, dtype=float)
    except Exception:
        return None
    if arr.ndim == 2 and arr.shape[1] == 1:
        arr = arr[:, 0]
    if arr.ndim != 1:
        return None
    return arr.reshape(-1)


def _coerce_matrix(value: Any, *, n_obs: int) -> np.ndarray | None:
    if value is None:
        return None
    try:
        arr = np.asarray(value, dtype=float)
    except Exception:
        return None
    if arr.ndim == 1:
        arr = arr.reshape(-1, 1)
    elif arr.ndim > 2:
        try:
            arr = arr.reshape(arr.shape[0], -1)
        except Exception:
            return None
    if arr.ndim != 2 or arr.shape[0] != n_obs:
        return None
    return arr


def _first_available_vector(
    state: Mapping[str, Any],
    candidates: tuple[str, ...],
    *,
    n_obs: int | None = None,
) -> np.ndarray | None:
    for key in candidates:
        if not key:
            continue
        arr = _coerce_vector(state.get(key))
        if arr is None:
            continue
        if n_obs is not None and arr.shape[0] != n_obs:
            continue
        return arr
    return None


def _normalize_execution_state(
    state: Mapping[str, Any],
    params: Mapping[str, Any],
) -> dict[str, np.ndarray]:
    treatment_name = str(params.get("treatment_name", "treatment") or "treatment")
    mediator_name = str(params.get("mediator_name", "mediator") or "mediator")
    outcome_name = str(params.get("outcome_name", "outcome") or "outcome")
    z_names = tuple(str(item) for item in (params.get("treatment_proxy_names") or ()) if str(item))
    w_names = tuple(str(item) for item in (params.get("outcome_proxy_names") or ()) if str(item))
    x_names = tuple(str(item) for item in (params.get("covariate_names") or ()) if str(item))

    outcome = _first_available_vector(state, ("outcome", outcome_name))
    treatment = _first_available_vector(state, ("treatment", treatment_name))
    mediator = _first_available_vector(state, ("mediator", mediator_name))
    if outcome is None or treatment is None or mediator is None:
        raise ValueError("outcome, treatment, and mediator vectors are required")
    n_obs = int(outcome.shape[0])
    if treatment.shape[0] != n_obs or mediator.shape[0] != n_obs:
        raise ValueError("outcome, treatment, and mediator must be aligned")

    treatment_proxy = _first_available_vector(
        state,
        ("treatment_proxy", *z_names),
        n_obs=n_obs,
    )
    outcome_proxy = _first_available_vector(
        state,
        ("outcome_proxy", *w_names),
        n_obs=n_obs,
    )
    if treatment_proxy is None or outcome_proxy is None:
        raise ValueError("treatment_proxy and outcome_proxy vectors are required")

    covariates = _coerce_matrix(state.get("covariates"), n_obs=n_obs)
    if covariates is None:
        covariate_columns: list[np.ndarray] = []
        for name in x_names:
            column = _coerce_vector(state.get(name))
            if column is None or column.shape[0] != n_obs:
                raise ValueError("covariate columns must be aligned when covariates matrix is absent")
            covariate_columns.append(column)
        covariates = (
            np.column_stack(covariate_columns)
            if covariate_columns
            else np.empty((n_obs, 0), dtype=float)
        )

    finite_mask = (
        np.isfinite(outcome)
        & np.isfinite(treatment)
        & np.isfinite(mediator)
        & np.isfinite(treatment_proxy)
        & np.isfinite(outcome_proxy)
        & np.isfinite(covariates).all(axis=1)
    )
    binary_mask = np.isclose(treatment, 0.0) | np.isclose(treatment, 1.0)
    mask = finite_mask & binary_mask
    if int(np.sum(mask)) < 60:
        raise ValueError("proximal mediation requires at least 60 aligned finite observations")
    return {
        "outcome": outcome[mask].astype(float),
        "treatment": treatment[mask].astype(float),
        "mediator": mediator[mask].astype(float),
        "covariates": covariates[mask].astype(float),
        "treatment_proxy": treatment_proxy[mask].astype(float),
        "outcome_proxy": outcome_proxy[mask].astype(float),
    }


def _estimate_proximal_potential_means(
    *,
    outcome: np.ndarray,
    treatment: np.ndarray,
    covariates: np.ndarray,
    treatment_proxy: np.ndarray,
    outcome_proxy: np.ndarray,
    ridge: float,
) -> tuple[float, float, np.ndarray, np.ndarray]:
    n_obs = int(outcome.shape[0])
    proxy_design = np.column_stack([np.ones(n_obs), treatment, covariates, treatment_proxy])
    proxy_coef = _weighted_least_squares(proxy_design, outcome_proxy, ridge=ridge)

    def _predicted_proxy(a_value: float, indices: np.ndarray | None = None) -> np.ndarray:
        sel = slice(None) if indices is None else indices
        x_sel = covariates[sel]
        z_sel = treatment_proxy[sel]
        a_vec = np.full(x_sel.shape[0], a_value, dtype=float)
        design = np.column_stack([np.ones(x_sel.shape[0]), a_vec, x_sel, z_sel])
        return design @ proxy_coef

    bridge_design = np.column_stack([np.ones(n_obs), treatment, covariates, outcome_proxy])
    bridge_coef = _weighted_least_squares(bridge_design, outcome, ridge=ridge)

    y1_proxy = _predicted_proxy(1.0)
    y0_proxy = _predicted_proxy(0.0)
    d1 = np.column_stack([np.ones(n_obs), np.ones(n_obs), covariates, y1_proxy])
    d0 = np.column_stack([np.ones(n_obs), np.zeros(n_obs), covariates, y0_proxy])
    mu1 = float(np.mean(d1 @ bridge_coef))
    mu0 = float(np.mean(d0 @ bridge_coef))
    return mu1, mu0, bridge_coef, proxy_coef


def _estimate_proximal_mediation_components(
    *,
    outcome: np.ndarray,
    treatment: np.ndarray,
    mediator: np.ndarray,
    covariates: np.ndarray,
    treatment_proxy: np.ndarray,
    outcome_proxy: np.ndarray,
    ridge: float,
) -> dict[str, Any]:
    mask_a1 = np.isclose(treatment, 1.0)
    mask_a0 = np.isclose(treatment, 0.0)
    if int(np.sum(mask_a1)) < 20 or int(np.sum(mask_a0)) < 20:
        raise ValueError("proximal mediation requires support in both treatment arms")

    x1 = covariates[mask_a1]
    m1 = mediator[mask_a1]
    z1 = treatment_proxy[mask_a1]
    w1 = outcome_proxy[mask_a1]
    y1 = outcome[mask_a1]
    stage1_design = np.column_stack([np.ones(x1.shape[0]), z1, m1, x1])
    stage1_coef = _weighted_least_squares(stage1_design, w1, ridge=ridge)
    w1_hat = stage1_design @ stage1_coef
    h1_design = np.column_stack([np.ones(x1.shape[0]), w1_hat, m1, x1])
    h1_coef = _weighted_least_squares(h1_design, y1, ridge=ridge)

    h1_all_design = np.column_stack([np.ones(outcome.shape[0]), outcome_proxy, mediator, covariates])
    h1_values = h1_all_design @ h1_coef

    x0 = covariates[mask_a0]
    z0 = treatment_proxy[mask_a0]
    w0 = outcome_proxy[mask_a0]
    h1_0 = h1_values[mask_a0]
    stage0_design = np.column_stack([np.ones(x0.shape[0]), z0, x0])
    stage0_coef = _weighted_least_squares(stage0_design, w0, ridge=ridge)
    w0_hat = stage0_design @ stage0_coef
    h0_design = np.column_stack([np.ones(x0.shape[0]), w0_hat, x0])
    h0_coef = _weighted_least_squares(h0_design, h1_0, ridge=ridge)

    h0_all_design = np.column_stack([np.ones(outcome.shape[0]), outcome_proxy, covariates])
    psi = float(np.mean(h0_all_design @ h0_coef))
    mu1, mu0, total_bridge_coef, total_proxy_coef = _estimate_proximal_potential_means(
        outcome=outcome,
        treatment=treatment,
        covariates=covariates,
        treatment_proxy=treatment_proxy,
        outcome_proxy=outcome_proxy,
        ridge=ridge,
    )
    nde = psi - mu0
    nie = mu1 - psi
    return {
        "psi": psi,
        "mu1": mu1,
        "mu0": mu0,
        "nde": float(nde),
        "nie": float(nie),
        "h1_coefficients": [float(value) for value in h1_coef.tolist()],
        "h0_coefficients": [float(value) for value in h0_coef.tolist()],
        "stage1_proxy_coefficients": [float(value) for value in stage1_coef.tolist()],
        "stage0_proxy_coefficients": [float(value) for value in stage0_coef.tolist()],
        "total_bridge_coefficients": [float(value) for value in total_bridge_coef.tolist()],
        "total_proxy_coefficients": [float(value) for value in total_proxy_coef.tolist()],
        "n_arm_1": int(np.sum(mask_a1)),
        "n_arm_0": int(np.sum(mask_a0)),
    }


def _target_point_estimate(target_effect: str, components: Mapping[str, Any]) -> float:
    target = str(target_effect or "psi").strip().lower()
    if target == "nde":
        return float(components["nde"])
    if target == "nie":
        return float(components["nie"])
    return float(components["psi"])


def proximal_mediation_identify_v1(
    graph: CausalGraphModel,
    *,
    treatment: str,
    mediator: str,
    outcome: str,
    proxies: ProxyAnnotation | dict[str, Any],
    active_treatment_value: float = 1.0,
    reference_treatment_value: float = 0.0,
    target_effect: str = "psi",
) -> ProximalMediationCertificate | NegativeCertificate:
    """Certify the single-mediator proximal mediation template or explain failure."""

    proxy_annotation = (
        proxies if isinstance(proxies, ProxyAnnotation) else ProxyAnnotation.model_validate(proxies)
    )
    trace = [
        "Started proximal mediation v1 identification.",
        (
            "Target functional is psi = E[Y{a, M(a_ref)}] for the "
            f"single-mediator topology ({treatment}, {mediator}, {outcome})."
        ),
    ]

    if graph.graph_type not in {GraphType.DAG, GraphType.ADMG}:
        return _negative(
            check="graph_type_supported",
            blocking_type=BlockingType.OUT_OF_SCOPE_FOR_PROXIMAL_V1,
            description=(
                "Proximal mediation v1 only supports DAG/ADMG graphs with directed and "
                "bidirected edges."
            ),
            detail=f"Received graph_type={graph.graph_type.value}.",
            trace=trace,
            witness={"graph_type": graph.graph_type.value},
        )

    if has_directed_cycle(graph):
        return _negative(
            check="acyclicity_of_observed_subgraph",
            blocking_type=BlockingType.OUT_OF_SCOPE_FOR_PROXIMAL_V1,
            description="Proximal mediation v1 requires an acyclic observed graph.",
            detail="Detected a directed cycle in the supplied graph.",
            trace=trace,
            witness={"graph_type": graph.graph_type.value},
        )

    node_set = set(graph.nodes)
    referenced = {
        treatment,
        mediator,
        outcome,
        *proxy_annotation.treatment_inducing,
        *proxy_annotation.outcome_inducing,
        *proxy_annotation.covariates,
    }
    missing = tuple(sorted(referenced - node_set))
    if missing:
        return _negative(
            check="variables_present",
            blocking_type=BlockingType.PROXIMAL_CONDITION_FAILED,
            description="The proximal mediation query references variables absent from the graph.",
            detail=f"Missing variables: {list(missing)}.",
            trace=trace,
            witness={"missing_variables": list(missing)},
            missing_vars=missing,
        )

    if not proxy_annotation.treatment_inducing or not proxy_annotation.outcome_inducing:
        return _negative(
            check="proxy_sets_non_empty",
            blocking_type=BlockingType.PROXIMAL_CONDITION_FAILED,
            description=(
                "Proximal mediation v1 requires non-empty treatment- and outcome-proxy sets."
            ),
            detail="Both Z- and W-proxy families must be annotated.",
            trace=trace,
            witness={
                "treatment_inducing": list(proxy_annotation.treatment_inducing),
                "outcome_inducing": list(proxy_annotation.outcome_inducing),
            },
        )

    overlap = _first_overlap(
        {
            "treatment": {treatment},
            "mediator": {mediator},
            "outcome": {outcome},
            "treatment_inducing": set(proxy_annotation.treatment_inducing),
            "outcome_inducing": set(proxy_annotation.outcome_inducing),
            "covariates": set(proxy_annotation.covariates),
        }
    )
    if overlap is not None:
        left, right, shared = overlap
        return _negative(
            check="role_partition",
            blocking_type=BlockingType.PROXIMAL_CONDITION_FAILED,
            description=(
                "Treatment, mediator, outcome, proxies, and covariates must form "
                "disjoint variable roles."
            ),
            detail=f"{left} and {right} overlap on {sorted(shared)}.",
            trace=trace,
            witness={"left": left, "right": right, "overlap": sorted(shared)},
            missing_vars=tuple(sorted(shared)),
        )

    graph_checks = [
        ProximalGraphCheck(
            check="role_partition",
            status="pass",
            requirements=(
                "A, M, Y, treatment proxies Z, outcome proxies W, and X covariates are disjoint",
            ),
        )
    ]

    if not _directed_path(graph, treatment, mediator):
        return _negative(
            check="treatment_reaches_mediator",
            blocking_type=BlockingType.PROXIMAL_CONDITION_FAILED,
            description="The declared mediator is not downstream of the treatment.",
            detail=f"No directed path from {treatment} to {mediator} was found.",
            trace=trace,
            witness={"from": treatment, "to": mediator},
            missing_vars=(mediator,),
        )
    if not _directed_path(graph, mediator, outcome):
        return _negative(
            check="mediator_reaches_outcome",
            blocking_type=BlockingType.PROXIMAL_CONDITION_FAILED,
            description="The declared mediator does not lie on a directed path into the outcome.",
            detail=f"No directed path from {mediator} to {outcome} was found.",
            trace=trace,
            witness={"from": mediator, "to": outcome},
            missing_vars=(mediator,),
        )
    graph_checks.extend(
        [
            ProximalGraphCheck(
                check="treatment_reaches_mediator",
                status="pass",
                source=treatment,
                target=mediator,
                detail=f"Found a directed path from {treatment} to {mediator}.",
            ),
            ProximalGraphCheck(
                check="mediator_reaches_outcome",
                status="pass",
                source=mediator,
                target=outcome,
                detail=f"Found a directed path from {mediator} to {outcome}.",
            ),
            ProximalGraphCheck(
                check="acyclicity_of_observed_subgraph",
                status="pass",
                detail="No directed cycle was found in the observed graph.",
            ),
        ]
    )

    for z_proxy in proxy_annotation.treatment_inducing:
        if _has_directed_edge(graph, z_proxy, mediator):
            return _negative(
                check="no_direct_edge_Z_to_M",
                blocking_type=BlockingType.PROXIMAL_CONDITION_FAILED,
                description="A Z-proxy directly influences the mediator, violating the v1 template.",
                detail=f"Found forbidden edge {z_proxy} -> {mediator}.",
                trace=trace,
                witness={"from": z_proxy, "to": mediator},
                missing_vars=(z_proxy, mediator),
            )
        if _has_directed_edge(graph, z_proxy, outcome):
            return _negative(
                check="no_direct_edge_Z_to_Y",
                blocking_type=BlockingType.PROXIMAL_CONDITION_FAILED,
                description="A Z-proxy directly influences the outcome, violating the v1 template.",
                detail=f"Found forbidden edge {z_proxy} -> {outcome}.",
                trace=trace,
                witness={"from": z_proxy, "to": outcome},
                missing_vars=(z_proxy, outcome),
            )

    graph_checks.extend(
        [
            ProximalGraphCheck(
                check="no_direct_edge_Z_to_M",
                status="pass",
                source_set=proxy_annotation.treatment_inducing,
                target=mediator,
                detail="No forbidden direct edge from any Z-proxy to the mediator was found.",
            ),
            ProximalGraphCheck(
                check="no_direct_edge_Z_to_Y",
                status="pass",
                source_set=proxy_annotation.treatment_inducing,
                target=outcome,
                detail="No forbidden direct edge from any Z-proxy to the outcome was found.",
            ),
        ]
    )

    for w_proxy in proxy_annotation.outcome_inducing:
        if _has_directed_edge(graph, treatment, w_proxy):
            return _negative(
                check="no_direct_edge_A_to_W",
                blocking_type=BlockingType.PROXIMAL_CONDITION_FAILED,
                description="Treatment directly influences a W-proxy, violating the v1 template.",
                detail=f"Found forbidden edge {treatment} -> {w_proxy}.",
                trace=trace,
                witness={"from": treatment, "to": w_proxy},
                missing_vars=(treatment, w_proxy),
            )
        if _has_directed_edge(graph, mediator, w_proxy):
            return _negative(
                check="no_direct_edge_M_to_W",
                blocking_type=BlockingType.PROXIMAL_CONDITION_FAILED,
                description="Mediator directly influences a W-proxy, violating the v1 template.",
                detail=f"Found forbidden edge {mediator} -> {w_proxy}.",
                trace=trace,
                witness={"from": mediator, "to": w_proxy},
                missing_vars=(mediator, w_proxy),
            )

    graph_checks.extend(
        [
            ProximalGraphCheck(
                check="no_direct_edge_A_to_W",
                status="pass",
                source=treatment,
                target_set=proxy_annotation.outcome_inducing,
                detail="No forbidden direct edge from treatment to any W-proxy was found.",
            ),
            ProximalGraphCheck(
                check="no_direct_edge_M_to_W",
                status="pass",
                source=mediator,
                target_set=proxy_annotation.outcome_inducing,
                detail="No forbidden direct edge from mediator to any W-proxy was found.",
            ),
        ]
    )

    target_label = target_effect if target_effect in {"psi", "nde", "nie"} else "psi"
    bridge_equations = (
        ProximalMediationBridgeEquation(
            name="outcome_bridge_h1",
            target=f"E({outcome} | Z, {treatment}=1, {mediator}, X)",
            unknown_function="h1(W, M, X)",
            operator=f"integrate_W over F(W | Z, {treatment}=1, {mediator}, X)",
        ),
        ProximalMediationBridgeEquation(
            name="nested_bridge_h0",
            target=f"E(h1(W, {mediator}, X) | Z, {treatment}=0, X)",
            unknown_function="h0(W, X)",
            operator=f"integrate_W over F(W | Z, {treatment}=0, X)",
        ),
    )
    completeness_conditions = (
        ProximalMediationCompletenessCondition(
            name="comp_A1_M_X",
            statement=f"E[g(U)|Z,{treatment}=1,{mediator},X]=0 => g(U)=0",
        ),
        ProximalMediationCompletenessCondition(
            name="comp_A0_X",
            statement=f"E[g(U)|Z,{treatment}=0,X]=0 => g(U)=0",
        ),
    )
    trace.extend(
        [
            "Matched the single-mediator proximal mediation topology.",
            "Verified proxy exclusion restrictions relative to the mediator.",
            "Recorded nested bridge equations h1(W,M,X) and h0(W,X).",
            "Marked completeness and latent cross-world assumptions as oracle-required.",
        ]
    )
    return ProximalMediationCertificate(
        query=ProximalMediationQuerySpec(
            treatment=treatment,
            mediator=mediator,
            outcome=outcome,
            active_treatment_value=active_treatment_value,
            reference_treatment_value=reference_treatment_value,
            target_effect=target_label,
        ),
        variable_roles={
            "X": proxy_annotation.covariates,
            "Z": proxy_annotation.treatment_inducing,
            "W": proxy_annotation.outcome_inducing,
        },
        theorem={
            "citation_key": "DukesShpitserTchetgen2023_Thm1",
            "identified_functional": "psi = ∬ h0(w,x) dF(w|x) dF(x)",
        },
        graph_checks=tuple(graph_checks),
        bridge_equations=bridge_equations,
        completeness_conditions=completeness_conditions,
        identified_functional="psi = ∬ h0(w,x) dF(w|x) dF(x)",
        assumptions={
            "consistency": True,
            "positivity": True,
            "latent_exchangeability_given_U_X": True,
            "latent_cross_world_given_U_X": True,
            "proxy_exclusion_and_independences": {
                "Z_no_effect_on_M_or_Y": True,
                "A_M_no_effect_on_W": True,
            },
        },
        diagnostics_and_gates={
            "graph_checks_passed": [check.check for check in graph_checks],
            "oracle_flags": ["completeness_unverifiable", "cross_world_unverifiable"],
            "data_requirements": [f"P({outcome},W,Z,{treatment},{mediator},X) observational"],
            "fallback_policy": {
                "if_graph_check_fails": "bounds_or_block",
                "if_completeness_not_accepted": "bounds",
            },
        },
        proof_trace=tuple(trace),
        metadata={
            "algorithm_version": PROXIMAL_MEDIATION_V1_THEOREM,
            "single_mediator_template": True,
        },
    )


def _has_directed_edge(graph: CausalGraphModel, src: str, dst: str) -> bool:
    for edge in graph.edges:
        if edge.src != src or edge.dst != dst:
            continue
        if edge.mark_src is EdgeMark.TAIL and edge.mark_dst is EdgeMark.ARROW:
            if edge.lag in (None, 0):
                return True
    return False


def _negative(
    *,
    check: str,
    blocking_type: BlockingType,
    description: str,
    detail: str,
    trace: list[str],
    witness: dict[str, Any] | None = None,
    missing_vars: tuple[str, ...] = (),
) -> NegativeCertificate:
    diagnostics = {
        "algorithm_version": PROXIMAL_MEDIATION_V1_THEOREM,
        "identification_status": "non_identified",
        "failed_check": check,
        "witness": witness or {},
        "proof_trace": [*trace, f"Failed proximal mediation check: {check}."],
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
            "Proximal mediation was not certified. Inspect the failed_check and witness "
            "fields, then revise proxy roles, mediator topology, or fall back to a "
            "bounds-oriented path-specific analysis."
        ),
    )


@foundry_method(
    namespace="causal.proximal",
    version="1.0.0",
    tags={"causal", "proximal", "mediation", "path_specific", "oracle_backed"},
)
class ProximalMediationEstimator:
    """Approximate v1 proximal mediation estimator with honest bounds fallback."""

    signature: MethodSignature = MethodSignature(
        name="proximal_mediation",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("outcome", SlotType.VECTOR, Unit("outcome", "value"), shape=("n_obs",)),
                SlotSpec("treatment", SlotType.VECTOR, Unit("treatment", "binary"), shape=("n_obs",)),
                SlotSpec("mediator", SlotType.VECTOR, Unit("mediator", "value"), shape=("n_obs",)),
                SlotSpec("covariates", SlotType.MATRIX, Unit("covariate", "value"), shape=("n_obs", "n_features")),
                SlotSpec("treatment_proxy", SlotType.VECTOR, Unit("proxy", "value"), shape=("n_obs",)),
                SlotSpec("outcome_proxy", SlotType.VECTOR, Unit("proxy", "value"), shape=("n_obs",)),
            }
        ),
        output_slots=frozenset(
            _proximal_mediation_output_slots()
        ),
        parameters=(
            ParameterSpec("theorem_family", default=PROXIMAL_MEDIATION_V1_THEOREM),
            ParameterSpec("oracle_gate", default="required"),
            ParameterSpec("target_effect", default="psi"),
            ParameterSpec("treatment_name", default="treatment"),
            ParameterSpec("mediator_name", default="mediator"),
            ParameterSpec("outcome_name", default="outcome"),
            ParameterSpec("treatment_proxy_names", default=()),
            ParameterSpec("outcome_proxy_names", default=()),
            ParameterSpec("covariate_names", default=()),
            ParameterSpec("y_lower", default=None),
            ParameterSpec("y_upper", default=None),
            ParameterSpec("ridge", default=1.0e-4),
            ParameterSpec("confidence_level", default=0.95),
            ParameterSpec("n_bootstrap", default=200),
            ParameterSpec("bridge_residual_splits", default=12),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: MethodMetadata = MethodMetadata(
        description=(
            "Approximate single-mediator proximal mediation estimator with linear "
            "nested bridge solvers and explicit bounds fallback when oracle-level "
            "assumptions are not accepted or bridge diagnostics fail."
        ),
        tags=frozenset({"causal", "proximal", "mediation", "oracle_backed"}),
        citations=(
            "Dukes, O., Shpitser, I. & Tchetgen Tchetgen, E. (2023). Proximal mediation analysis.",
        ),
        when_to_use=(
            "Use after the Stage 11.3 proof kernel certifies the single-mediator "
            "proximal topology and governance accepts the oracle-level bridge and "
            "completeness assumptions."
        ),
        when_not_to_use=(
            "Do not use for arbitrary path-specific graphs, unsupported proxy "
            "topologies, or when oracle assumptions are not accepted."
        ),
    )

    @staticmethod
    def pure_step(state: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
        target_effect = str(params.get("target_effect", "psi") or "psi").strip().lower()
        ridge = float(params.get("ridge", 1.0e-4) or 1.0e-4)
        seed = int(params.get("__seed__", 0) or 0)
        y_lower = params.get("y_lower")
        y_upper = params.get("y_upper")
        outcome_support = None
        if y_lower is not None and y_upper is not None:
            try:
                outcome_support = (float(y_lower), float(y_upper))
            except (TypeError, ValueError):
                outcome_support = None

        try:
            normalized = _normalize_execution_state(
                state if isinstance(state, Mapping) else dict(state),
                params,
            )
        except Exception as exc:
            report = build_failure_report(
                method=CausalMethod.PROXIMAL_BRIDGE,
                status=EstimationStatus.INPUT_INVALID,
                reason=str(exc),
                estimand=f"proximal_mediation_{target_effect}",
                sample_size=0,
                n_treated=0,
                n_control=0,
                pre_periods=0,
                post_periods=0,
                assumptions={
                    "oracle_gate": str(params.get("oracle_gate", "required")),
                    "theorem_family": str(
                        params.get("theorem_family", PROXIMAL_MEDIATION_V1_THEOREM)
                    ),
                },
            )
            return wrap_causal_output(
                report,
                warnings=[report.status_reason or "input invalid"],
                extras={
                    "proximal_mediation_result": None,
                    "bridge_plausibility_report": None,
                    "bounds_bundle": None,
                    "negative_certificate": None,
                },
            )

        outcome = normalized["outcome"]
        treatment = normalized["treatment"]
        mediator = normalized["mediator"]
        covariates = normalized["covariates"]
        treatment_proxy = normalized["treatment_proxy"]
        outcome_proxy = normalized["outcome_proxy"]
        n_obs = int(outcome.shape[0])
        assumptions = {
            "oracle_gate": str(params.get("oracle_gate", "required")),
            "theorem_family": str(params.get("theorem_family", PROXIMAL_MEDIATION_V1_THEOREM)),
            "target_effect": target_effect,
        }

        bridge_report = _build_bridge_plausibility_report(
            outcome=outcome,
            treatment=treatment,
            covariates=covariates,
            treatment_proxy=treatment_proxy,
            outcome_proxy=outcome_proxy,
            ridge=ridge,
            seed=seed,
            n_residual_splits=int(params.get("bridge_residual_splits", 12) or 12),
        )
        bridge_report_payload = bridge_report.model_dump(mode="json")
        bridge_diagnostics = _bridge_diagnostic_tests(bridge_report)

        oracle_gate = str(params.get("oracle_gate", "required") or "required").strip().lower()
        oracle_accepted = oracle_gate in {"accepted", "allow", "allowed", "assumed", "true", "yes"}

        if not oracle_accepted:
            bounds_bundle = proximal_mediation_bounds_bundle(
                outcome=outcome,
                target_effect=target_effect,
                outcome_support=outcome_support,
                assumption_tag="proximal_mediation_oracle_not_accepted",
                metadata={"oracle_gate": oracle_gate},
                warnings=[
                    "Point identification requires oracle acceptance of completeness and cross-world assumptions.",
                ],
            )
            negative_certificate = NegativeCertificate(
                blocking_type=BlockingType.COMPLETENESS_UNLIKELY,
                blocking_description=(
                    "The proximal mediation template was certified structurally, but "
                    "oracle-level completeness/cross-world assumptions were not accepted."
                ),
                technical_detail=(
                    "Execution downgraded to bounds because oracle_gate "
                    f"was '{oracle_gate}'."
                ),
                quantitative_diagnostics={
                    "oracle_gate": oracle_gate,
                    "target_effect": target_effect,
                    "theorem_family": str(
                        params.get("theorem_family", PROXIMAL_MEDIATION_V1_THEOREM)
                    ),
                    "bridge_plausibility_report": bridge_report_payload,
                },
                constructive_message=(
                    "Accept the oracle assumptions explicitly if a point estimate is "
                    "governance-permitted; otherwise rely on the returned bounds."
                ),
                bounds_bundle=bounds_bundle,
            )
            report = build_failure_report(
                method=CausalMethod.PROXIMAL_BRIDGE,
                status=EstimationStatus.ASSUMPTION_FAILED,
                reason="proximal_mediation_oracle_not_accepted",
                estimand=f"proximal_mediation_{target_effect}",
                sample_size=n_obs,
                n_treated=int(np.sum(np.isclose(treatment, 1.0))),
                n_control=int(np.sum(np.isclose(treatment, 0.0))),
                pre_periods=0,
                post_periods=0,
                assumptions=assumptions,
                diagnostics=bridge_diagnostics,
                metadata={
                    "bridge_plausibility_report": bridge_report_payload,
                    "bridge_plausibility_severity": bridge_report.severity.value,
                    "fallback_mode": "bounds",
                },
            )
            return wrap_causal_output(
                report,
                warnings=list(bounds_bundle.warnings),
                extras={
                    "proximal_mediation_result": None,
                    "bridge_plausibility_report": bridge_report_payload,
                    "bounds_bundle": bounds_bundle.model_dump(mode="json"),
                    "negative_certificate": negative_certificate.model_dump(mode="json"),
                },
            )

        fallback_disposition = bridge_report.fallback_disposition
        if fallback_disposition in {
            BridgeFallbackDisposition.BLOCK_POINT_ESTIMATE,
            BridgeFallbackDisposition.REQUIRE_BOUNDS,
        }:
            bounds_bundle = proximal_mediation_bounds_bundle(
                outcome=outcome,
                target_effect=target_effect,
                outcome_support=outcome_support,
                assumption_tag="proximal_mediation_bridge_unstable",
                metadata={"diagnostic_fallback_disposition": fallback_disposition.value},
            )
            bounds_bundle = annotate_bounds_bundle_for_proximal_bridge_failure(
                bounds_bundle,
                bridge_report,
            )
            negative_certificate = negative_certificate_from_bridge_plausibility_report(
                bridge_report,
                estimand_type=(
                    "proximal_mediation_psi"
                    if target_effect == "psi"
                    else "path_specific_effect"
                ),
                bounds_bundle=bounds_bundle,
                missing_vars=("additional_treatment_proxy", "additional_outcome_proxy"),
                constructive_message=(
                    "Nested bridge diagnostics do not support an unqualified point estimate; "
                    "use the returned proximal mediation bounds or collect richer proxies."
                ),
            )
            reason = (
                "proximal_mediation_bridge_infeasible"
                if bridge_report.suspected_failure_mode is BridgeFailureMode.INFEASIBLE_EQUATION
                else "proximal_mediation_bridge_requires_bounds"
            )
            report = build_failure_report(
                method=CausalMethod.PROXIMAL_BRIDGE,
                status=EstimationStatus.ASSUMPTION_FAILED,
                reason=reason,
                estimand=f"proximal_mediation_{target_effect}",
                sample_size=n_obs,
                n_treated=int(np.sum(np.isclose(treatment, 1.0))),
                n_control=int(np.sum(np.isclose(treatment, 0.0))),
                pre_periods=0,
                post_periods=0,
                assumptions=assumptions,
                diagnostics=bridge_diagnostics,
                metadata={
                    "bridge_plausibility_report": bridge_report_payload,
                    "bridge_plausibility_severity": bridge_report.severity.value,
                    "bridge_failure_mode": bridge_report.suspected_failure_mode.value,
                },
            )
            return wrap_causal_output(
                report,
                warnings=list(bounds_bundle.warnings),
                extras={
                    "proximal_mediation_result": None,
                    "bridge_plausibility_report": bridge_report_payload,
                    "bounds_bundle": bounds_bundle.model_dump(mode="json"),
                    "negative_certificate": negative_certificate.model_dump(mode="json"),
                },
            )

        try:
            components = _estimate_proximal_mediation_components(
                outcome=outcome,
                treatment=treatment,
                mediator=mediator,
                covariates=covariates,
                treatment_proxy=treatment_proxy,
                outcome_proxy=outcome_proxy,
                ridge=ridge,
            )
        except Exception as exc:
            bounds_bundle = proximal_mediation_bounds_bundle(
                outcome=outcome,
                target_effect=target_effect,
                outcome_support=outcome_support,
                assumption_tag="proximal_mediation_numeric_failure",
                metadata={"numeric_failure": str(exc)},
            )
            report = build_failure_report(
                method=CausalMethod.PROXIMAL_BRIDGE,
                status=EstimationStatus.NUMERICAL_FAILURE,
                reason=str(exc),
                estimand=f"proximal_mediation_{target_effect}",
                sample_size=n_obs,
                n_treated=int(np.sum(np.isclose(treatment, 1.0))),
                n_control=int(np.sum(np.isclose(treatment, 0.0))),
                pre_periods=0,
                post_periods=0,
                assumptions=assumptions,
                diagnostics=bridge_diagnostics,
                metadata={"bridge_plausibility_report": bridge_report_payload},
            )
            return wrap_causal_output(
                report,
                warnings=list(bounds_bundle.warnings),
                extras={
                    "proximal_mediation_result": None,
                    "bridge_plausibility_report": bridge_report_payload,
                    "bounds_bundle": bounds_bundle.model_dump(mode="json"),
                    "negative_certificate": None,
                },
            )

        point_estimate = _target_point_estimate(target_effect, components)

        def _bootstrap_target(indices: np.ndarray) -> float:
            try:
                sampled = _estimate_proximal_mediation_components(
                    outcome=outcome[indices],
                    treatment=treatment[indices],
                    mediator=mediator[indices],
                    covariates=covariates[indices],
                    treatment_proxy=treatment_proxy[indices],
                    outcome_proxy=outcome_proxy[indices],
                    ridge=ridge,
                )
                return _target_point_estimate(target_effect, sampled)
            except Exception:
                return float(point_estimate)

        confidence_interval = _bootstrap_effect_interval(
            _bootstrap_target,
            n_obs=n_obs,
            n_bootstrap=int(params.get("n_bootstrap", 200) or 200),
            seed=seed,
        )
        estimand_name = (
            "proximal_mediation_psi"
            if target_effect == "psi"
            else f"proximal_{target_effect}"
        )
        report = build_success_report(
            method=CausalMethod.PROXIMAL_BRIDGE,
            estimand=estimand_name,
            point_estimate=float(point_estimate),
            confidence_interval=confidence_interval,
            confidence_level=float(params.get("confidence_level", 0.95) or 0.95),
            inference_method="proximal_mediation_linear_bridge",
            sample_size=n_obs,
            n_treated=int(np.sum(np.isclose(treatment, 1.0))),
            n_control=int(np.sum(np.isclose(treatment, 0.0))),
            pre_periods=0,
            post_periods=0,
            assumptions=assumptions,
            diagnostics=bridge_diagnostics,
            metadata={
                "bridge_plausibility_report": bridge_report_payload,
                "bridge_plausibility_severity": bridge_report.severity.value,
                "bridge_failure_mode": bridge_report.suspected_failure_mode.value,
            },
        )
        mediation_result = {
            "target_effect": target_effect,
            "point_estimate": float(point_estimate),
            "confidence_interval": [float(confidence_interval[0]), float(confidence_interval[1])],
            "psi": float(components["psi"]),
            "mu1": float(components["mu1"]),
            "mu0": float(components["mu0"]),
            "nde": float(components["nde"]),
            "nie": float(components["nie"]),
            "bridge_plausibility_report": bridge_report_payload,
            "bridge_plausibility_severity": bridge_report.severity.value,
            "bridge_failure_mode": bridge_report.suspected_failure_mode.value,
            "bridge_fallback_disposition": (
                fallback_disposition.value if fallback_disposition is not None else None
            ),
            "n_arm_1": int(components["n_arm_1"]),
            "n_arm_0": int(components["n_arm_0"]),
            "h1_coefficients": list(components["h1_coefficients"]),
            "h0_coefficients": list(components["h0_coefficients"]),
            "stage1_proxy_coefficients": list(components["stage1_proxy_coefficients"]),
            "stage0_proxy_coefficients": list(components["stage0_proxy_coefficients"]),
            "total_bridge_coefficients": list(components["total_bridge_coefficients"]),
            "total_proxy_coefficients": list(components["total_proxy_coefficients"]),
        }
        warnings = (
            ["proximal_mediation_plausibility_warning"]
            if fallback_disposition is BridgeFallbackDisposition.PROCEED_WITH_WARNING
            else []
        )
        return wrap_causal_output(
            report,
            warnings=warnings,
            extras={
                "proximal_mediation_result": mediation_result,
                "bridge_plausibility_report": bridge_report_payload,
                "bounds_bundle": None,
                "negative_certificate": None,
            },
        )


__all__ = [
    "PROXIMAL_MEDIATION_V1_THEOREM",
    "ProximalMediationEstimator",
    "proximal_mediation_bounds_bundle",
    "proximal_mediation_identify_v1",
]
