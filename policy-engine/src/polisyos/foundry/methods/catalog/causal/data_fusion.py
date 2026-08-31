"""data_fusion — Multi-source causal data fusion (Phase 9).

Implements the data-fusion framework of Bareinboim & Pearl (2016), which
formalises the problem of combining K heterogeneous datasets — each with
potentially different selection biases and experimental distributions — to
identify a target causal query in the policy population.

Four exported algorithm functions (plus one foundry wrapper class):

``fuse_experimental_observational``
    Combine one observational + one RCT dataset via Z-transport
    (Bareinboim & Pearl 2013).  Delegates to ``z_id_algorithm``.

``multi_study_fusion``
    Combine K studies with arbitrary selection biases and experimental
    distributions via the mZ-ID algorithm (Bareinboim & Pearl 2016).
    Delegates to ``mz_id_algorithm``.

``optimal_data_combination``
    Given per-dataset EIF variances, compute inverse-variance-weighted
    combination for minimum asymptotic variance.

``design_external_validity``
    Assess whether a source-population causal effect is transportable to
    a target population via the TR algorithm (Bareinboim & Pearl 2012).

``counterfactual_fusion``
    Fuse multi-domain datasets for Layer-3 counterfactual queries via
    counterfactual transportability.

Foundry method: ``causal.fusion.data_fusion@1.0.0``

References
----------
Bareinboim, E. & Pearl, J. (2016). Causal inference and the data-fusion
    problem. *PNAS*, 113(27), 7345–7352.
Bareinboim, E. & Pearl, J. (2013). A general algorithm for deciding
    transportability of experimental results. *JAIR*, 46, 505–538.
Bareinboim, E. & Pearl, J. (2012). Transportability of causal effects:
    Completeness results. *AAAI*.
"""

from __future__ import annotations

import dataclasses
import logging
from collections.abc import Mapping, Sequence
from typing import Any, ClassVar

from polisyos.core.observability import DeterminismTier
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
from polisyos.ir.analytics.causal_graph import CausalGraphModel
from polisyos.ir.analytics.context import ContextProfile
from polisyos.ir.analytics.data_fusion import (
    DataCombinationPlan,
    FusionDataset,
    FusionResult,
    ValidityReport,
)
from polisyos.ir.analytics.transportability import SelectionDiagram, SNode

_logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Algorithm functions
# ---------------------------------------------------------------------------


def fuse_experimental_observational(
    *,
    graph: CausalGraphModel,
    treatment: str,
    outcome: str,
    exp_interventions: Sequence[str],
    obs_data_ref: str = "obs",
    exp_data_ref: str = "rct",
) -> FusionResult:
    """Fuse one observational dataset with one RCT via Z-transport.

    Implements the Z-ID algorithm (Bareinboim & Pearl 2013): given an
    observational distribution P(V) and experimental distributions
    P(V | do(Z_i)) for Z_i ∈ ``exp_interventions``, identifies
    P*(Y | do(X)) in the target population.

    Parameters
    ----------
    graph:
        Causal DAG (no S-nodes required; only the base causal structure).
    treatment:
        Treatment variable X.
    outcome:
        Outcome variable Y.
    exp_interventions:
        Variables Z for which P(V|do(Z)) is available from the RCT.
    obs_data_ref:
        Reference key for the observational dataset.
    exp_data_ref:
        Reference key for the experimental (RCT) dataset.

    Returns
    -------
    FusionResult
        ``is_identified=True`` when Z-transport succeeds.
    """
    from polisyos.foundry.methods.catalog.causal.id_engine import (
        IdentificationStatus,
        z_id_algorithm,
    )

    z_set = frozenset(exp_interventions)
    result = z_id_algorithm(
        treatment=frozenset({treatment}),
        outcome=frozenset({outcome}),
        z_interventions=z_set,
        graph=graph,
        dataset_ref=obs_data_ref,
    )

    identified = result.status == IdentificationStatus.IDENTIFIED
    latex = None
    if identified and result.estimand_ast is not None:
        try:
            latex = result.estimand_ast.to_latex()
        except Exception:  # pragma: no cover
            pass

    warnings: list[str] = []
    if not identified:
        warnings.append(
            f"Z-transport failed (status={result.status.value}). "
            "Check that the experimental interventions are sufficient to "
            "identify the target query."
        )

    return FusionResult(
        query=f"P*({outcome}|do({treatment}))",
        is_identified=identified,
        fusion_formula_latex=latex,
        required_datasets=(obs_data_ref, exp_data_ref),
        required_interventions=tuple(sorted(z_set)),
        identification_algorithm="z-id",
        proof_steps=tuple(ps.rule_name for ps in result.proof_steps),
        warnings=tuple(warnings),
    )


def multi_study_fusion(
    *,
    datasets: Sequence[FusionDataset],
    graph: CausalGraphModel,
    treatment: str,
    outcome: str,
) -> FusionResult:
    """Fuse K studies with heterogeneous selection biases via mZ-ID.

    Implements Bareinboim & Pearl (2016) Theorem 1: generalised
    meta-transportability combining observational and experimental
    distributions across K domains with different S-node structures.

    Each ``FusionDataset`` maps directly to a ``SourceDomain`` in the
    mZ-ID algorithm:
    - ``selection_bias_vars`` → S-nodes (mechanism shifts)
    - ``available_interventions`` → Z-interventional distributions

    Parameters
    ----------
    datasets:
        Sequence of FusionDataset descriptors for each source domain.
    graph:
        Base causal DAG shared by all domains (structural assumptions).
    treatment:
        Treatment variable X in the target query.
    outcome:
        Outcome variable Y in the target query.

    Returns
    -------
    FusionResult
        ``is_identified=True`` when mZ-ID succeeds across the K domains.
    """
    from polisyos.foundry.methods.catalog.causal.id_engine import (
        IdentificationStatus,
        SourceDomain,
        mz_id_algorithm,
    )

    source_domains = [
        SourceDomain(
            domain_id=ds.domain_id,
            s_nodes=frozenset(ds.selection_bias_vars),
            z_interventions=frozenset(ds.available_interventions),
            dataset_ref=ds.dataset_ref,
        )
        for ds in datasets
    ]

    result = mz_id_algorithm(
        treatment=frozenset({treatment}),
        outcome=frozenset({outcome}),
        source_domains=source_domains,
        graph=graph,
    )

    identified = result.status == IdentificationStatus.IDENTIFIED
    latex = None
    if identified and result.estimand_ast is not None:
        try:
            latex = result.estimand_ast.to_latex()
        except Exception:  # pragma: no cover
            pass

    required_refs = tuple(ds.dataset_ref for ds in datasets if ds.dataset_ref)
    required_ivs = tuple(iv for ds in datasets for iv in ds.available_interventions)

    warnings: list[str] = []
    if not identified:
        warnings.append(
            f"mZ-ID failed (status={result.status.value}). "
            "Additional experimental data or fewer selection biases may be needed."
        )

    return FusionResult(
        query=f"P*({outcome}|do({treatment}))",
        is_identified=identified,
        fusion_formula_latex=latex,
        required_datasets=required_refs,
        required_interventions=required_ivs,
        identification_algorithm="mz-id",
        proof_steps=tuple(ps.rule_name for ps in result.proof_steps),
        warnings=tuple(warnings),
    )


def optimal_data_combination(
    *,
    eif_variances: dict[str, float],
    query: str,
    required_datasets: Sequence[str] = (),
) -> DataCombinationPlan:
    """Compute inverse-variance-optimal weights for combining dataset estimates.

    Given per-dataset EIF (Efficient Influence Function) variances, computes
    the minimum-variance convex combination weights:

        w_k = (1/V_k) / Σ_j (1/V_j)
        V_combined = 1 / Σ_k (1/V_k)

    This is the semiparametrically efficient combination when the EIF
    variances are known (or consistently estimated).

    Parameters
    ----------
    eif_variances:
        Mapping domain_id → EIF variance estimate V_k > 0.
    query:
        Target causal query string.
    required_datasets:
        Dataset references included in the combination.

    Returns
    -------
    DataCombinationPlan
        Optimal weights and combined asymptotic variance.
    """
    # Guard against zero / negative variances
    valid = {k: v for k, v in eif_variances.items() if v > 1e-12}
    if not valid:
        _logger.warning(
            "optimal_data_combination: all EIF variances are zero or invalid; "
            "returning uniform weights."
        )
        n = max(len(eif_variances), 1)
        weights = dict.fromkeys(eif_variances, 1.0 / n)
        return DataCombinationPlan(
            query=query,
            source_weights=weights,
            combination_method="uniform_fallback",
            expected_variance=None,
            required_datasets=tuple(required_datasets),
        )

    inv_vars = {k: 1.0 / v for k, v in valid.items()}
    total_inv = sum(inv_vars.values())
    weights = {k: v / total_inv for k, v in inv_vars.items()}
    combined_var = 1.0 / total_inv

    return DataCombinationPlan(
        query=query,
        source_weights=weights,
        combination_method="inverse_variance_weighted",
        expected_variance=combined_var,
        required_datasets=tuple(required_datasets),
    )


def design_external_validity(
    *,
    graph: CausalGraphModel,
    s_nodes: Sequence[SNode],
    source_population: str,
    target_population: str,
    treatment: str,
    outcome: str,
) -> ValidityReport:
    """Assess external validity via the TR algorithm (Bareinboim & Pearl 2012).

    Constructs a selection diagram from the provided S-nodes (representing
    mechanism differences between source and target populations) and runs
    ``tr_algorithm`` to determine whether P*(Y|do(X)) is transportable.

    Parameters
    ----------
    graph:
        Base causal DAG (structural assumptions shared across populations).
    s_nodes:
        S-node specifications encoding mechanism shifts between populations.
    source_population:
        Identifier of the source (study) population.
    target_population:
        Identifier of the target (policy) population.
    treatment:
        Treatment variable X.
    outcome:
        Outcome variable Y.

    Returns
    -------
    ValidityReport
        ``overall_transportability=True`` iff TR algorithm succeeds.
    """
    from polisyos.foundry.methods.catalog.causal.id_engine import (
        IdentificationStatus,
        tr_algorithm,
    )

    source_ctx = ContextProfile(context_id=source_population, context_label=source_population)
    target_ctx = ContextProfile(context_id=target_population, context_label=target_population)

    diagram = SelectionDiagram(
        base_graph=graph,
        s_nodes=list(s_nodes),
        source_context=source_ctx,
        target_context=target_ctx,
    )

    result = tr_algorithm(
        treatment=frozenset({treatment}),
        outcome=frozenset({outcome}),
        selection_diagram=diagram,
    )

    identified = result.status == IdentificationStatus.IDENTIFIED
    latex = None
    if identified and result.estimand_ast is not None:
        try:
            latex = result.estimand_ast.to_latex()
        except Exception:  # pragma: no cover
            pass

    # Infer which S-node variables block transportability from the trace
    all_s_vars = tuple(sn.target_variable for sn in s_nodes)
    if identified:
        non_transportable: tuple[str, ...] = ()
        transportable = all_s_vars
    else:
        # Heuristic: variables mentioned in the trace as blocking
        blocking = frozenset(
            v
            for line in result.trace
            for v in all_s_vars
            if v in line and ("BLOCK" in line.upper() or "HEDGE" in line.upper())
        )
        non_transportable = tuple(v for v in all_s_vars if v in blocking)
        transportable = tuple(v for v in all_s_vars if v not in blocking)

    return ValidityReport(
        source_population=source_population,
        target_population=target_population,
        transportable_variables=transportable,
        non_transportable_variables=non_transportable,
        recommended_adjustments=all_s_vars,
        transport_formula_latex=latex,
        overall_transportability=identified,
    )


def _coerce_ctf_query(raw_query: Any) -> Any:
    from polisyos.foundry.methods.catalog.causal.id_engine import CtfQuery

    if isinstance(raw_query, CtfQuery):
        return raw_query
    if dataclasses.is_dataclass(raw_query):
        return CtfQuery(**dataclasses.asdict(raw_query))
    if hasattr(raw_query, "model_dump"):
        return CtfQuery(**raw_query.model_dump(mode="python"))
    if isinstance(raw_query, Mapping):
        return CtfQuery(**dict(raw_query))
    raise TypeError("counterfactual_query must be a CtfQuery or mapping-compatible object.")


def counterfactual_fusion(
    *,
    datasets: Sequence[FusionDataset],
    graph: CausalGraphModel,
    counterfactual_query: Any,
) -> FusionResult:
    """Fuse source domains for a Layer-3 counterfactual query."""
    from polisyos.foundry.methods.catalog.causal.ctf_transport import (
        build_ctf_selection_diagram,
        ctf_transportability,
    )
    from polisyos.foundry.methods.catalog.causal.id_engine import (
        IdentificationStatus,
        SourceDomain,
    )
    from polisyos.ir.analytics.negative_certificate import NegativeCertificate

    ctf_query = _coerce_ctf_query(counterfactual_query)
    source_domains = [
        SourceDomain(
            domain_id=ds.domain_id,
            s_nodes=frozenset(ds.selection_bias_vars),
            z_interventions=frozenset(ds.available_interventions),
            dataset_ref=ds.dataset_ref,
        )
        for ds in datasets
    ]
    selection_diagram = build_ctf_selection_diagram(
        graph=graph,
        source_domains=source_domains,
    )
    result = ctf_transportability(
        ctf_query,
        selection_diagram,
        source_domains=source_domains,
    )

    required_refs = tuple(ds.dataset_ref for ds in datasets if ds.dataset_ref)
    required_ivs = tuple(iv for ds in datasets for iv in ds.available_interventions)
    query_str = getattr(result, "query_str", "") or f"CTF[{ctf_query.kind}:{ctf_query.outcome}]"

    if isinstance(result, NegativeCertificate):
        return FusionResult(
            query=query_str,
            is_identified=False,
            fusion_formula_latex=None,
            required_datasets=required_refs,
            required_interventions=required_ivs,
            identification_algorithm="ctf_transport",
            proof_steps=(),
            warnings=(result.to_summary(),),
        )

    identified = result.status == IdentificationStatus.IDENTIFIED
    latex = None
    if identified and result.estimand_ast is not None:
        try:
            latex = result.estimand_ast.to_latex()
        except Exception:  # pragma: no cover
            pass

    warnings: list[str] = []
    if not identified:
        warnings.append(
            f"Counterfactual transport failed (status={result.status.value}). "
            "Additional target-domain data or transport-resolving experiments may be needed."
        )

    return FusionResult(
        query=query_str,
        is_identified=identified,
        fusion_formula_latex=latex,
        required_datasets=required_refs,
        required_interventions=required_ivs,
        identification_algorithm="ctf_transport",
        proof_steps=tuple(ps.rule_name for ps in result.proof_steps),
        warnings=tuple(warnings),
    )


# ---------------------------------------------------------------------------
# Foundry wrapper
# ---------------------------------------------------------------------------


@foundry_method(
    namespace="causal.fusion",
    version="1.0.0",
    tags={"causal", "fusion", "transport", "bareinboim_pearl", "mz_id", "cross-section"},
)
class DataFusionEngine:
    """Multi-source causal data fusion (Bareinboim & Pearl 2016).

    Dispatches to one of five fusion modes via the ``mode`` parameter:

    ``"rct_plus_obs"`` (default)
        Fuse one observational + one RCT dataset via Z-transport.
        Requires: ``graph``, ``treatment``, ``outcome``,
        ``exp_interventions`` (list of str).

    ``"multi_study"``
        Fuse K studies with heterogeneous selection biases via mZ-ID.
        Requires: ``graph``, ``treatment``, ``outcome``,
        ``datasets`` (list of dicts matching FusionDataset schema).

    ``"optimal_combine"``
        Compute inverse-variance-optimal combination weights.
        Requires: ``eif_variances`` (dict domain_id → float),
        ``query`` (str).

    ``"external_validity"``
        Assess transportability via TR algorithm.
        Requires: ``graph``, ``treatment``, ``outcome``,
        ``s_node_vars`` (list of str — variable names with mechanism shifts),
        ``source_population``, ``target_population``.

    ``"ctf_fusion"``
        Fuse multiple domains for a Layer-3 counterfactual query.
        Requires: ``graph``, ``datasets``, ``counterfactual_query``.
    """

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="data_fusion",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("graph_json", SlotType.SCALAR, Unit("graph", "json")),
            }
        ),
        output_slots=frozenset(
            {
                SlotSpec("fusion_result", SlotType.SCALAR, Unit("result", "json")),
            }
        ),
        parameters=(
            ParameterSpec(name="mode", default="multi_study"),
            ParameterSpec(name="treatment", default=""),
            ParameterSpec(name="outcome", default=""),
            ParameterSpec(name="exp_interventions", default=[]),
            ParameterSpec(name="obs_data_ref", default="obs"),
            ParameterSpec(name="exp_data_ref", default="rct"),
            ParameterSpec(name="datasets", default=[]),
            ParameterSpec(name="eif_variances", default={}),
            ParameterSpec(name="query", default=""),
            ParameterSpec(name="counterfactual_query", default=None),
            ParameterSpec(name="s_node_vars", default=[]),
            ParameterSpec(name="source_population", default="source"),
            ParameterSpec(name="target_population", default="target"),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description=(
            "Multi-source causal data fusion via mZ-ID (Bareinboim & Pearl 2016). "
            "Combines observational and experimental datasets with heterogeneous "
            "selection biases to identify causal queries in the target population."
        ),
        tags=frozenset(
            {
                "causal",
                "fusion",
                "transport",
                "selection_diagram",
                "mz_id",
                "z_id",
                "tr_algorithm",
                "ctf_transport",
                "bareinboim_pearl",
            }
        ),
        citations=(
            "Bareinboim, E. & Pearl, J. (2016). Causal inference and the "
            "data-fusion problem. PNAS, 113(27), 7345–7352.",
            "Bareinboim, E. & Pearl, J. (2013). A general algorithm for "
            "deciding transportability of experimental results. JAIR, 46, 505–538.",
        ),
        equations={
            "z_transport": "P*(Y|do(X)) = Σ_Z P_Z(Y|X,Z) · P*(Z)",
            "mz_id": "P*(Y|do(X)) = mZ-ID(X, Y, G, {π_k})",
            "inv_var_weights": "w_k = (1/V_k) / Σ_j(1/V_j)",
        },
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        when_to_use=(
            "Multiple datasets from different populations or studies; "
            "combining RCT data with observational data; "
            "assessing generalisability of causal effects."
        ),
        when_not_to_use=(
            "All data from the same population with no selection bias; "
            "identification is already clear from a single source."
        ),
        output_interpretation=(
            "FusionResult: is_identified indicates whether the target query "
            "is identifiable from the fused sources. fusion_formula_latex gives "
            "the identification formula. proof_steps traces the algorithm."
        ),
    )

    @staticmethod
    def pure_step(
        state: Mapping[str, Any],
        params: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Dispatch to the selected fusion mode."""
        mode: str = params.get("mode", "multi_study")
        graph: CausalGraphModel = state["graph"]
        treatment: str = params.get("treatment", "")
        outcome: str = params.get("outcome", "")

        if mode == "rct_plus_obs":
            result = fuse_experimental_observational(
                graph=graph,
                treatment=treatment,
                outcome=outcome,
                exp_interventions=params.get("exp_interventions", []),
                obs_data_ref=params.get("obs_data_ref", "obs"),
                exp_data_ref=params.get("exp_data_ref", "rct"),
            )
            return {"fusion_result": result.model_dump()}

        if mode == "multi_study":
            raw_datasets = params.get("datasets", [])
            datasets = [FusionDataset.model_validate(d) for d in raw_datasets]
            result = multi_study_fusion(
                datasets=datasets,
                graph=graph,
                treatment=treatment,
                outcome=outcome,
            )
            return {"fusion_result": result.model_dump()}

        if mode == "optimal_combine":
            plan = optimal_data_combination(
                eif_variances=dict(params.get("eif_variances", {})),
                query=params.get("query", ""),
                required_datasets=params.get("required_datasets", []),
            )
            return {"fusion_result": plan.model_dump()}

        if mode == "external_validity":
            s_node_vars: list[str] = params.get("s_node_vars", [])
            s_nodes = [
                SNode(
                    target_variable=v,
                    context_dimension="mechanism_shift",
                    source_value=0.0,
                    target_value=1.0,
                    delta=1.0,
                    severity="medium",
                )
                for v in s_node_vars
            ]
            report = design_external_validity(
                graph=graph,
                s_nodes=s_nodes,
                source_population=params.get("source_population", "source"),
                target_population=params.get("target_population", "target"),
                treatment=treatment,
                outcome=outcome,
            )
            return {"fusion_result": report.model_dump()}

        if mode == "ctf_fusion":
            raw_datasets = params.get("datasets", [])
            datasets = [FusionDataset.model_validate(d) for d in raw_datasets]
            if params.get("counterfactual_query") is None:
                raise ValueError("ctf_fusion mode requires counterfactual_query.")
            result = counterfactual_fusion(
                datasets=datasets,
                graph=graph,
                counterfactual_query=params.get("counterfactual_query"),
            )
            return {"fusion_result": result.model_dump()}

        raise ValueError(
            f"Unknown DataFusionEngine mode {mode!r}. "
            "Expected one of: 'rct_plus_obs', 'multi_study', "
            "'optimal_combine', 'external_validity', 'ctf_fusion'."
        )


__all__ = [
    "DataFusionEngine",
    "counterfactual_fusion",
    "design_external_validity",
    "fuse_experimental_observational",
    "multi_study_fusion",
    "optimal_data_combination",
]
