"""BERL explanation orchestration service."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, cast

from polisyos.berl.adapters import (
    ALEAdapter,
    EBMComponentAdapter,
    FiniteDifferenceGradientAdapter,
    KernelSHAPAdapter,
    LIMEAdapter,
    PermutationImportanceAdapter,
    TreeSHAPAdapter,
)
from polisyos.berl.adapters.protocol import (
    AdapterUnavailableError,
    ExplanationAdapter,
    ExplanationContext,
    ScalarModel,
    UnavailableAdapter,
)
from polisyos.berl.adapters.shap_kernel import (
    SUPPORTED_KERNEL_SHAP_FEATURE_DEPENDENCE_POLICIES,
)
from polisyos.berl.contracts.explanation_bundle import (
    AuditReport,
    BackgroundData,
    DisagreementReport,
    ExplanationAssumptions,
    ExplanationBundle,
    FeatureAttribution,
    FeatureContext,
    FeatureDependencePolicy,
    GroupAttribution,
    InfidelityReport,
    MethodExplanation,
    ModelContext,
    PerturbationDistribution,
    PredictionContext,
    RedundancyClusterModel,
    RedundancyContext,
    RedundancyEvidenceModel,
    SupportCheck,
    ValidityReport,
)
from polisyos.berl.contracts.validation_rules import (
    ValidationThresholds,
    validate_explanation_bundle,
)
from polisyos.berl.metrics.disagreement import (
    AttributionVector,
    compare_attribution_vectors,
)
from polisyos.berl.metrics.empirical_bounds import adjust_confidence_for_union
from polisyos.berl.metrics.infidelity import estimate_local_infidelity
from polisyos.berl.metrics.redundancy import (
    RedundancyCluster,
    RedundancyEvidence,
    detect_redundancy_clusters,
    group_attributions,
)
from polisyos.berl.perturbations import (
    FeatureConstraint,
    PerturbedPoint,
    build_heldout_records,
    perturbation_support_rates,
    sample_local_perturbations,
)

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from polisyos.core.artifacts import ArtifactStore as CoreArtifactStore
    from polisyos.ir import ArtifactStore as IRArtifactStore
    from polisyos.ir import ExplanationBundleRef

from polisyos.berl.service.cache_identity import (
    _adapter_cache_identity as _adapter_cache_identity,
)
from polisyos.berl.service.cache_identity import (
    _effective_method_id,
    _effective_request_key,
    _string_param,
)
from polisyos.berl.service.cache_identity import (
    _freeze as _freeze,
)
from polisyos.berl.service.cache_identity import (
    _freeze_immutable_configuration as _freeze_immutable_configuration,
)
from polisyos.berl.service.cache_identity import (
    _freeze_scalar as _freeze_scalar,
)
from polisyos.berl.service.cache_identity import (
    _is_builtin_adapter as _is_builtin_adapter,
)
from polisyos.berl.service.results import (
    _diagnostic_method,
    _feature_in_redundancy_cluster,
    _reidentify_method,
    _scope_from_raw,
    _top_feature_from_vectors,
)

type _AdapterRoute = ExplanationAdapter | UnavailableAdapter
type _BuiltinAdapter = (
    ALEAdapter
    | EBMComponentAdapter
    | FiniteDifferenceGradientAdapter
    | KernelSHAPAdapter
    | LIMEAdapter
    | PermutationImportanceAdapter
    | TreeSHAPAdapter
)
_BUILTIN_EFFECTIVE_METHODS: dict[type[_BuiltinAdapter], str] = {
    ALEAdapter: "ale_local_bin",
    EBMComponentAdapter: "ebm_components",
    FiniteDifferenceGradientAdapter: "finite_difference_gradient",
    KernelSHAPAdapter: "kernel_shap",
    LIMEAdapter: "lime",
    PermutationImportanceAdapter: "permutation_importance",
    TreeSHAPAdapter: "kernel_shap",
}


@dataclass(frozen=True, slots=True)
class ExplanationRequest:
    """Request shape corresponding to POST /explanations semantics."""

    prediction_id: str
    row_id: str
    x: Mapping[str, float]
    feature_names: tuple[str, ...]
    methods: tuple[str, ...] = (
        "kernel_shap",
        "lime",
        "ale_local_bin",
    )
    output_name: str = "model_output"
    output_scale: str = "score"
    confidence: float = 0.95
    perturbation_policy: str = "conditional_empirical_local"
    feature_dependence_policy: str = "conditional_observational"
    model_id: str = "model"
    model_hash: str = "sha256:unknown"
    model_class: str = "black_box"
    training_data_hash: str | None = None
    calibration_ref: str | None = None
    feature_values_ref: str = "inline://features"
    feature_schema_version: str = "unknown"
    constraints_ref: str | None = None
    missingness_policy: str = "model_native"
    background_rows: Sequence[Mapping[str, float]] = field(default_factory=tuple)
    n_eval_perturbations: int = 512
    perturbation_radius: float = 0.25
    residual_cap: float = 4.0
    random_seed: int | None = 1234
    include_disagreement: bool = True
    include_redundancy: bool = True
    constraints: Mapping[str, FeatureConstraint] = field(default_factory=dict)
    adapter_params: Mapping[str, object] = field(default_factory=dict)
    artifact_refs: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class _CachedAdapterRun:
    """One effective adapter run reusable by compatible requested aliases."""

    method: MethodExplanation
    vector: AttributionVector | None


class ExplanationOrchestrator:
    """Run method adapters, held-out infidelity checks, and bundle validation."""

    def __init__(
        self,
        adapters: Mapping[str, ExplanationAdapter] | None = None,
        *,
        thresholds: ValidationThresholds | None = None,
    ) -> None:
        self._adapters: dict[str, _AdapterRoute] = dict(adapters or default_adapters())
        self._thresholds = thresholds or ValidationThresholds()

    def explain(self, model: ScalarModel, request: ExplanationRequest) -> ExplanationBundle:
        """Return an audited ExplanationBundle for one scalar prediction."""

        context = ExplanationContext(
            feature_names=request.feature_names,
            output_scale=request.output_scale,
            perturbation_distribution=request.perturbation_policy,
            feature_dependence_policy=request.feature_dependence_policy,
            confidence=adjust_confidence_for_union(
                global_confidence=request.confidence,
                claim_count=max(1, len(request.methods)),
            ),
            random_seed=request.random_seed,
            params={
                **dict(request.adapter_params),
                "background_rows": tuple(request.background_rows),
                "lime_radius": request.perturbation_radius,
            },
        )
        effective_cache: dict[tuple[object, ...], _CachedAdapterRun] = {}
        redundancy = self._build_redundancy(request)
        perturbations = sample_local_perturbations(
            x=request.x,
            feature_names=request.feature_names,
            n=request.n_eval_perturbations,
            radius=request.perturbation_radius,
            random_seed=request.random_seed,
            constraints=request.constraints,
        )
        methods: list[MethodExplanation] = []
        attribution_vectors: list[AttributionVector] = []
        compared_method_ids: set[str] = set()
        for method_id in request.methods:
            adapter = _adapter_for_request(
                method_id,
                request.feature_dependence_policy,
                self._adapters,
            )
            if adapter is None:
                methods.append(_diagnostic_method(method_id, "adapter_not_registered"))
                continue
            if isinstance(adapter, UnavailableAdapter):
                methods.append(_diagnostic_method(method_id, adapter.diagnostic))
                continue
            effective_method_id = _effective_method_id(adapter)
            cache_key = _effective_request_key(
                model=model,
                request=request,
                context=context,
                adapter=adapter,
                effective_method_id=effective_method_id,
            )
            cached = effective_cache.get(cache_key) if cache_key is not None else None
            if cached is None:
                method, vector = self._run_adapter(
                    model=model,
                    request=request,
                    context=context,
                    adapter=adapter,
                    requested_method_id=method_id,
                    effective_method_id=effective_method_id,
                    redundancy=redundancy,
                    perturbations=perturbations,
                )
                cached = _CachedAdapterRun(method=method, vector=vector)
                if cache_key is not None:
                    effective_cache[cache_key] = cached
            else:
                method = _reidentify_method(
                    cached.method,
                    adapter=adapter,
                    requested_method_id=method_id,
                    # A cached result proves execution only when its vector exists.
                    effective_method_id=(
                        cached.vector.method_id if cached.vector is not None else None
                    ),
                )
                vector = None
            methods.append(method)
            if vector is not None and vector.method_id not in compared_method_ids:
                attribution_vectors.append(vector)
                compared_method_ids.add(vector.method_id)

        ood_rate, constraint_violation_rate = perturbation_support_rates(perturbations)
        bundle = ExplanationBundle(
            bundle_id=str(uuid.uuid4()),
            created_at=datetime.now(UTC),
            model=ModelContext(
                model_id=request.model_id,
                model_hash=request.model_hash,
                model_class=request.model_class,
                training_data_hash=request.training_data_hash,
                calibration_ref=request.calibration_ref,
            ),
            prediction=PredictionContext(
                prediction_id=request.prediction_id,
                row_id=request.row_id,
                output_name=request.output_name,
                output_scale=request.output_scale,
                raw_score=float(model(request.x)),
            ),
            feature_context=FeatureContext(
                feature_values_ref=request.feature_values_ref,
                feature_schema_version=request.feature_schema_version,
                constraints_ref=request.constraints_ref,
                missingness_policy=request.missingness_policy,
            ),
            assumptions=ExplanationAssumptions(
                perturbation_distribution=PerturbationDistribution(
                    name=request.perturbation_policy,
                    radius=request.perturbation_radius,
                    continuous_policy="uniform_numeric_ball",
                    support_constraints=request.constraints_ref,
                ),
                feature_dependence_policy=FeatureDependencePolicy(
                    primary=request.feature_dependence_policy,
                    causal_claim_made=False,
                ),
                background_data=BackgroundData(
                    dataset_ref="inline://background_rows" if request.background_rows else None,
                    n=len(request.background_rows),
                    sampling_policy="request_supplied",
                ),
            ),
            redundancy=redundancy,
            methods=methods,
            disagreement=self._build_disagreement(attribution_vectors, request),
            validity=ValidityReport(
                support_check=SupportCheck(
                    ood_rate_eval_perturbations=ood_rate,
                    constraint_violation_rate=constraint_violation_rate,
                ),
                use_restrictions=[
                    "Explanation is local to the declared perturbation distribution.",
                    "No causal claim is made without explicit intervention semantics.",
                ],
            ),
            audit=AuditReport(
                code_version="polisyos.berl@1.0.0",
                random_seeds=[] if request.random_seed is None else [request.random_seed],
                artifact_refs=list(request.artifact_refs),
            ),
        )
        validation = validate_explanation_bundle(bundle, thresholds=self._thresholds)
        return bundle.model_copy(
            update={
                "faithfulness_claim": validation.faithfulness_claim,
                "display_policy": validation.display_policy,
                "analyst_warning": "; ".join(validation.violations) or None,
            }
        )

    def _run_adapter(
        self,
        *,
        model: ScalarModel,
        request: ExplanationRequest,
        context: ExplanationContext,
        adapter: ExplanationAdapter,
        requested_method_id: str,
        effective_method_id: str,
        redundancy: RedundancyContext,
        perturbations: Sequence[PerturbedPoint],
    ) -> tuple[MethodExplanation, AttributionVector | None]:
        try:
            raw = adapter.explain(model, request.x, context)
            records = build_heldout_records(
                model=model,
                x=request.x,
                explanation=raw,
                adapter=adapter,
                perturbations=perturbations,
            )
            bound = estimate_local_infidelity(
                records,
                confidence=context.confidence,
                residual_cap=request.residual_cap,
            )
        except (AdapterUnavailableError, TypeError, ValueError, RuntimeError) as exc:
            return (
                _diagnostic_method(
                    requested_method_id,
                    str(exc),
                ),
                None,
            )

        uncertainty = adapter.estimator_uncertainty(raw)
        # The selected adapter is the execution binding. A result payload may
        # describe the run, but it cannot relabel which implementation was called.
        raw_fallback = raw.fallback or raw.params.get("fallback") is True
        raw_fallback_reason = raw.fallback_reason or _string_param(
            raw.params,
            "fallback_reason",
        )
        params = dict(raw.params)
        params["requested_method_id"] = requested_method_id
        params["effective_method_id"] = effective_method_id
        if raw_fallback:
            params["fallback"] = True
        if raw_fallback_reason is not None:
            params["fallback_reason"] = raw_fallback_reason
        feature_attributions = [
            FeatureAttribution(
                feature=feature,
                value=value,
                standard_error=uncertainty.standard_errors.get(feature),
                confidence_interval=uncertainty.confidence_intervals.get(feature),
            )
            for feature, value in raw.attributions.items()
        ]
        group_values = group_attributions(
            raw.attributions,
            list(detect_redundancy_clusters_from_bundle(redundancy)),
        )
        method = MethodExplanation(
            method_id=requested_method_id,
            requested_method_id=requested_method_id,
            effective_method_id=effective_method_id,
            fallback=raw_fallback,
            fallback_reason=raw_fallback_reason,
            library="polisyos.berl",
            library_version="1.0.0",
            scope=_scope_from_raw(raw),
            params=params,
            assumptions=dict(raw.assumptions),
            attributions=feature_attributions,
            group_attributions=[
                GroupAttribution(cluster_id=cluster_id, value=value)
                for cluster_id, value in group_values.items()
            ],
            infidelity=InfidelityReport(
                point_estimate=bound.point_estimate,
                upper_bound=bound.upper_bound,
                confidence=bound.confidence,
                n_eval_perturbations=bound.n,
                residual_cap=bound.residual_cap,
                bound_type=f"{bound.bound_type}_heldout",
            ),
        )
        return (
            method,
            AttributionVector(
                effective_method_id,
                raw.attributions,
                uncertainty.confidence_intervals,
            ),
        )

    def _build_redundancy(self, request: ExplanationRequest) -> RedundancyContext:
        if not request.include_redundancy or not request.background_rows:
            return RedundancyContext()
        clusters = detect_redundancy_clusters(request.background_rows)
        return RedundancyContext(
            clusters=[
                RedundancyClusterModel(
                    cluster_id=cluster.cluster_id,
                    features=list(cluster.features),
                    evidence=RedundancyEvidenceModel(
                        max_abs_corr=cluster.evidence.max_abs_corr,
                        max_predictability_r2=cluster.evidence.max_predictability_r2,
                        domain_rule=cluster.evidence.domain_rule,
                    ),
                    reporting_policy=cluster.reporting_policy,
                )
                for cluster in clusters
            ]
        )

    def _build_disagreement(
        self,
        vectors: Sequence[AttributionVector],
        request: ExplanationRequest,
    ) -> DisagreementReport | None:
        if not request.include_disagreement or len(vectors) < 2:
            return None
        summary = compare_attribution_vectors(vectors, top_k=min(5, len(request.feature_names)))
        flags = list(summary.flags)
        redundancy_adjusted_conflicts = [
            feature
            for feature in summary.sign_conflict_features
            if not _feature_in_redundancy_cluster(feature, request.background_rows)
        ]
        top_feature = _top_feature_from_vectors(vectors)
        if top_feature is not None and _feature_in_redundancy_cluster(
            top_feature,
            request.background_rows,
        ):
            flags.append("feature_level_non_identifiable")
        return DisagreementReport(
            methods_compared=list(summary.methods_compared),
            top_k=summary.top_k,
            top_k_jaccard_median=summary.top_k_jaccard_median,
            kendall_tau_median=summary.kendall_tau_median,
            magnitude_l1_median=summary.magnitude_l1_median,
            sign_conflict_features=list(summary.sign_conflict_features),
            redundancy_adjusted_conflicts=redundancy_adjusted_conflicts,
            flags=list(dict.fromkeys(flags)),
        )


def explain_and_persist(
    model: ScalarModel,
    request: ExplanationRequest,
    store: CoreArtifactStore | IRArtifactStore,
    *,
    orchestrator: ExplanationOrchestrator | None = None,
) -> ExplanationBundleRef:
    """Produce an explanation bundle and persist its exact selected CAS view.

    Args:
        model: Scalar model to explain.
        request: Request describing the prediction and explanation methods.
        store: Existing Core or IR artifact store receiving the produced bundle.
        orchestrator: Configured BERL producer; defaults to the standard registry.

    Returns:
        ExplanationBundleRef: Exact selected-view ref returned by the CAS write.

    Raises:
        ValueError: If the produced bundle or selected ref violates the BERL contract.
        NotImplementedError: If the store cannot return the profile selected by its write.
        OSError: If the store reports an operating-system write failure.
    """
    from polisyos.berl.persistence import persist_explanation_bundle

    producer = orchestrator if orchestrator is not None else ExplanationOrchestrator()
    bundle = producer.explain(model, request)
    return persist_explanation_bundle(store, bundle)


def default_adapters() -> dict[str, _AdapterRoute]:
    """Return the built-in BERL adapter registry."""

    return {
        "kernel_shap": cast("ExplanationAdapter", KernelSHAPAdapter()),
        "kernel_shap_conditional": UnavailableAdapter(
            method_id="kernel_shap_conditional",
            diagnostic=_CONDITIONAL_KERNEL_SHAP_UNAVAILABLE,
        ),
        "kernel_shap_marginal": cast(
            "ExplanationAdapter",
            KernelSHAPAdapter(method_id="kernel_shap_marginal"),
        ),
        "lime": cast("ExplanationAdapter", LIMEAdapter()),
        "ale_local_bin": cast("ExplanationAdapter", ALEAdapter()),
        "tree_shap": cast("ExplanationAdapter", TreeSHAPAdapter()),
        "gradient": cast("ExplanationAdapter", FiniteDifferenceGradientAdapter()),
        "finite_difference_gradient": cast(
            "ExplanationAdapter",
            FiniteDifferenceGradientAdapter(),
        ),
        "permutation_importance": cast("ExplanationAdapter", PermutationImportanceAdapter()),
        "ebm_components": cast("ExplanationAdapter", EBMComponentAdapter()),
    }


_CONDITIONAL_KERNEL_SHAP_UNAVAILABLE = (
    "no verified conditional law over observed features is available for KernelSHAP; "
    "no attribution was produced"
)


def _adapter_for_request(
    method_id: str,
    feature_dependence_policy: str,
    adapters: Mapping[str, _AdapterRoute],
) -> _AdapterRoute | None:
    """Refuse KernelSHAP requests whose declared feature law is not implemented."""

    if method_id == "kernel_shap_conditional":
        return UnavailableAdapter(
            method_id=method_id,
            diagnostic=_CONDITIONAL_KERNEL_SHAP_UNAVAILABLE,
        )
    if method_id in {"kernel_shap", "kernel_shap_marginal"} and (
        feature_dependence_policy not in SUPPORTED_KERNEL_SHAP_FEATURE_DEPENDENCE_POLICIES
    ):
        return UnavailableAdapter(
            method_id=method_id,
            diagnostic=(
                "empirical replacement KernelSHAP has no verified conditional law; "
                f"feature-dependence policy {feature_dependence_policy!r} is unsupported"
            ),
        )
    return adapters.get(method_id)


def detect_redundancy_clusters_from_bundle(
    redundancy: RedundancyContext,
) -> tuple[RedundancyCluster, ...]:
    """Convert bundle redundancy models back to metric clusters."""

    return tuple(
        RedundancyCluster(
            cluster_id=cluster.cluster_id,
            features=tuple(cluster.features),
            evidence=RedundancyEvidence(
                max_abs_corr=cluster.evidence.max_abs_corr or 0.0,
                max_predictability_r2=cluster.evidence.max_predictability_r2 or 0.0,
                domain_rule=cluster.evidence.domain_rule,
            ),
            reporting_policy=cluster.reporting_policy,
        )
        for cluster in redundancy.clusters
    )
