"""BERL explanation orchestration service."""

from __future__ import annotations

import struct
import uuid
from dataclasses import dataclass, field, fields
from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING, Literal, cast

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
    RawExplanation,
    ScalarModel,
    UnavailableAdapter,
)
from polisyos.berl.adapters.shap_kernel import (
    SUPPORTED_KERNEL_SHAP_FEATURE_DEPENDENCE_POLICIES,
)
from polisyos.berl.adapters.shap_tree import TREE_SHAP_FALLBACK_REASON
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
from polisyos.berl.metrics.disagreement import AttributionVector, compare_attribution_vectors
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


MethodScope = Literal["local", "global", "local_bin", "diagnostic"]
_CACHE_IDENTITY_UNSUPPORTED = object()
_BUILTIN_EFFECTIVE_METHODS: dict[type[object], str] = {
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
        self._adapters = dict(adapters or default_adapters())
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
                    effective_method_id=effective_method_id,
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
                    effective_method_id=effective_method_id,
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


def default_adapters() -> dict[str, ExplanationAdapter]:
    """Return the built-in BERL adapter registry."""

    return {
        "kernel_shap": cast("ExplanationAdapter", KernelSHAPAdapter()),
        "kernel_shap_conditional": cast(
            "ExplanationAdapter",
            UnavailableAdapter(
                method_id="kernel_shap_conditional",
                diagnostic=_CONDITIONAL_KERNEL_SHAP_UNAVAILABLE,
            ),
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
    adapters: Mapping[str, ExplanationAdapter],
) -> ExplanationAdapter | None:
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


def _effective_method_id(adapter: ExplanationAdapter) -> str:
    builtin_profile = _BUILTIN_EFFECTIVE_METHODS.get(type(adapter))
    if builtin_profile is not None:
        return builtin_profile
    candidate = getattr(adapter, "effective_method_id", None)
    if isinstance(candidate, str) and candidate:
        return candidate
    return adapter.method_id


def _effective_request_key(
    *,
    model: ScalarModel,
    request: ExplanationRequest,
    context: ExplanationContext,
    adapter: ExplanationAdapter,
    effective_method_id: str,
) -> tuple[object, ...] | None:
    """Return a complete request key only for known built-ins and typed inputs.

    Custom adapters remain executable, but are not automatically reused because
    the protocol has no source-owned cache-identity contract for their state.
    """

    adapter_identity = _adapter_cache_identity(adapter, effective_method_id)
    if adapter_identity is None:
        return None
    request_values = (
        _freeze(request.x),
        _freeze(request.feature_names),
        _freeze(request.background_rows),
        _freeze(request.adapter_params),
        _freeze(request.constraints),
    )
    if any(value is _CACHE_IDENTITY_UNSUPPORTED for value in request_values):
        return None
    return (
        "berl-effective-request-v3",
        adapter_identity,
        id(model),
        request.model_id,
        request.model_hash,
        request.model_class,
        request.training_data_hash,
        request.calibration_ref,
        *request_values,
        context.output_scale,
        context.perturbation_distribution,
        context.feature_dependence_policy,
        context.confidence,
        context.random_seed,
        request.n_eval_perturbations,
        request.perturbation_radius,
        request.residual_cap,
        request.include_redundancy,
    )


def _adapter_cache_identity(
    adapter: ExplanationAdapter,
    effective_method_id: str,
) -> tuple[object, ...] | None:
    """Return identity for an exact, source-owned immutable built-in adapter.

    Custom adapters, dataclass or otherwise, execute every selected route until
    the adapter protocol supplies an admitted cache-configuration contract.
    """

    builtin_profile = _BUILTIN_EFFECTIVE_METHODS.get(type(adapter))
    if builtin_profile is None or effective_method_id != builtin_profile:
        return None

    adapter_method_id = object.__getattribute__(adapter, "method_id")
    shared_kernel_profile = (
        type(adapter) is KernelSHAPAdapter
        and adapter_method_id in {"kernel_shap", "kernel_shap_marginal"}
        and builtin_profile == "kernel_shap"
    )
    shared_tree_fallback = (
        type(adapter) is TreeSHAPAdapter
        and adapter_method_id == "tree_shap"
        and builtin_profile == "kernel_shap"
    )
    identity_type = (
        KernelSHAPAdapter if shared_kernel_profile or shared_tree_fallback else type(adapter)
    )
    configuration: list[tuple[str, object]] = []
    for item in fields(adapter):
        if (shared_kernel_profile or shared_tree_fallback) and item.name == "method_id":
            continue
        frozen_value = _freeze_immutable_configuration(object.__getattribute__(adapter, item.name))
        if frozen_value is _CACHE_IDENTITY_UNSUPPORTED:
            return None
        configuration.append((item.name, frozen_value))
    return (
        identity_type.__module__,
        identity_type.__qualname__,
        builtin_profile,
        tuple(configuration),
    )


def _freeze_scalar(value: object) -> object:
    """Encode supported scalar values with their exact primitive type."""

    if value is None:
        return ("none",)
    if type(value) is bool:
        return ("bool", value)
    if type(value) is int:
        return ("int", value)
    if type(value) is float:
        return ("float64", struct.pack(">d", value).hex())
    if type(value) is str:
        return ("str", value)
    return _CACHE_IDENTITY_UNSUPPORTED


def _freeze_immutable_configuration(value: object) -> object:
    """Freeze typed immutable values for source-owned built-in configuration."""

    if isinstance(value, Enum):
        frozen_value = _freeze_immutable_configuration(value.value)
        if frozen_value is _CACHE_IDENTITY_UNSUPPORTED:
            return _CACHE_IDENTITY_UNSUPPORTED
        return ("enum", type(value).__module__, type(value).__qualname__, frozen_value)
    scalar = _freeze_scalar(value)
    if scalar is not _CACHE_IDENTITY_UNSUPPORTED:
        return scalar
    if type(value) is dict:
        items = []
        for key, item in value.items():
            frozen_key = _freeze_immutable_configuration(key)
            frozen_item = _freeze_immutable_configuration(item)
            if (
                frozen_key is _CACHE_IDENTITY_UNSUPPORTED
                or frozen_item is _CACHE_IDENTITY_UNSUPPORTED
            ):
                return _CACHE_IDENTITY_UNSUPPORTED
            items.append((frozen_key, frozen_item))
        return ("dict", tuple(sorted(items, key=lambda pair: repr(pair[0]))))
    if type(value) is tuple or type(value) is frozenset:
        frozen_items = tuple(_freeze_immutable_configuration(item) for item in value)
        if any(item is _CACHE_IDENTITY_UNSUPPORTED for item in frozen_items):
            return _CACHE_IDENTITY_UNSUPPORTED
        if type(value) is frozenset:
            frozen_items = tuple(sorted(frozen_items, key=repr))
        return (type(value).__name__, frozen_items)
    if type(value) is FeatureConstraint:
        lower = _freeze_immutable_configuration(object.__getattribute__(value, "lower"))
        upper = _freeze_immutable_configuration(object.__getattribute__(value, "upper"))
        if lower is _CACHE_IDENTITY_UNSUPPORTED or upper is _CACHE_IDENTITY_UNSUPPORTED:
            return _CACHE_IDENTITY_UNSUPPORTED
        return ("feature_constraint", lower, upper)
    return _CACHE_IDENTITY_UNSUPPORTED


def _freeze(value: object) -> object:
    """Freeze canonical request values; opaque values disable cross-route reuse."""

    if isinstance(value, Enum):
        frozen_value = _freeze(value.value)
        if frozen_value is _CACHE_IDENTITY_UNSUPPORTED:
            return _CACHE_IDENTITY_UNSUPPORTED
        return ("enum", type(value).__module__, type(value).__qualname__, frozen_value)
    scalar = _freeze_scalar(value)
    if scalar is not _CACHE_IDENTITY_UNSUPPORTED:
        return scalar
    if type(value) is dict:
        items = []
        for key, item in value.items():
            frozen_key = _freeze(key)
            frozen_item = _freeze(item)
            if (
                frozen_key is _CACHE_IDENTITY_UNSUPPORTED
                or frozen_item is _CACHE_IDENTITY_UNSUPPORTED
            ):
                return _CACHE_IDENTITY_UNSUPPORTED
            items.append((frozen_key, frozen_item))
        return ("dict", tuple(sorted(items, key=lambda pair: repr(pair[0]))))
    if type(value) in {tuple, list, set, frozenset}:
        frozen_items = tuple(_freeze(item) for item in value)
        if any(item is _CACHE_IDENTITY_UNSUPPORTED for item in frozen_items):
            return _CACHE_IDENTITY_UNSUPPORTED
        if type(value) in {set, frozenset}:
            frozen_items = tuple(sorted(frozen_items, key=repr))
        return (type(value).__name__, frozen_items)
    if type(value) is FeatureConstraint:
        lower = _freeze(object.__getattribute__(value, "lower"))
        upper = _freeze(object.__getattribute__(value, "upper"))
        if lower is _CACHE_IDENTITY_UNSUPPORTED or upper is _CACHE_IDENTITY_UNSUPPORTED:
            return _CACHE_IDENTITY_UNSUPPORTED
        return ("feature_constraint", lower, upper)
    return _CACHE_IDENTITY_UNSUPPORTED


def _string_param(params: Mapping[str, object], name: str) -> str | None:
    value = params.get(name)
    return value if isinstance(value, str) else None


def _reidentify_method(
    method: MethodExplanation,
    *,
    adapter: ExplanationAdapter,
    requested_method_id: str,
    effective_method_id: str,
) -> MethodExplanation:
    params = dict(method.params)
    assumptions = dict(method.assumptions)
    fallback = method.fallback
    fallback_reason = method.fallback_reason
    params["requested_method_id"] = requested_method_id
    params["effective_method_id"] = effective_method_id

    if type(adapter) is TreeSHAPAdapter and adapter.method_id == "tree_shap":
        fallback = True
        fallback_reason = TREE_SHAP_FALLBACK_REASON
        params["fallback"] = True
        params["fallback_reason"] = fallback_reason
        assumptions["tree_exactness_claimed"] = False
        assumptions["fallback_reason"] = fallback_reason
    elif type(adapter) is KernelSHAPAdapter and adapter.method_id in {
        "kernel_shap",
        "kernel_shap_marginal",
    }:
        fallback = False
        fallback_reason = None
        params["fallback"] = False
        params.pop("fallback_reason", None)
        assumptions.pop("tree_exactness_claimed", None)
        assumptions.pop("fallback_reason", None)

    return method.model_copy(
        update={
            "method_id": requested_method_id,
            "requested_method_id": requested_method_id,
            "effective_method_id": effective_method_id,
            "fallback": fallback,
            "fallback_reason": fallback_reason,
            "params": params,
            "assumptions": assumptions,
        }
    )


def _diagnostic_method(
    method_id: str,
    reason: str,
    *,
    effective_method_id: str | None = None,
) -> MethodExplanation:
    effective = effective_method_id or method_id
    return MethodExplanation(
        method_id=method_id,
        requested_method_id=method_id,
        effective_method_id=effective,
        library="polisyos.berl",
        scope="diagnostic",
        params={
            "diagnostic": reason,
            "requested_method_id": method_id,
            "effective_method_id": effective,
        },
        assumptions={"faithfulness_claim": "unbounded", "display_policy": "diagnostic_only"},
    )


def _scope_from_raw(raw: RawExplanation) -> MethodScope:
    scope = raw.assumptions.get("scope")
    if scope == "local_bin_effect_evidence":
        return "local_bin"
    if scope == "global_comparison_evidence":
        return "global"
    return "local"


def _top_feature_from_vectors(vectors: Sequence[AttributionVector]) -> str | None:
    values: dict[str, float] = {}
    for vector in vectors:
        for feature, value in vector.values.items():
            if abs(value) > abs(values.get(feature, 0.0)):
                values[feature] = value
    if not values:
        return None
    return max(values.items(), key=lambda item: abs(item[1]))[0]


def _feature_in_redundancy_cluster(
    feature: str,
    background_rows: Sequence[Mapping[str, float]],
) -> bool:
    if not background_rows:
        return False
    return any(
        feature in cluster.features for cluster in detect_redundancy_clusters(background_rows)
    )
