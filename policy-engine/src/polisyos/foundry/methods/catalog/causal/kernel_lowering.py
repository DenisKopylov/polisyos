"""Kernel/RKHS lowering rules for proof-certified causal estimands."""

from __future__ import annotations

from typing import Any

from polisyos.ir.analytics.estimand import (
    DistributionDomain,
    DistributionLawNode,
    DistributionRef,
    EstimandAST,
    EventPredicate,
)
from polisyos.ir.analytics.kernel_causal import (
    KernelConsistencyClaim,
    KernelEstimatorSpec,
    KernelEstimatorTemplate,
    KernelLoweringDisposition,
    KernelNuisanceSpec,
    KernelRegularization,
    KernelRegularizationSelection,
    KernelSpec,
    KernelTargetRepresentation,
)
from polisyos.ir.canon import content_hash, to_canonical_bytes
from polisyos.ir.refs import EstimandASTRef, ProofBundleRef


def should_request_kernel_lowering(
    ast: EstimandAST,
    identification_metadata: dict[str, Any] | None = None,
) -> bool:
    """Return True when the caller explicitly asks for RKHS lowering."""

    metadata = dict(identification_metadata or {})
    if bool(metadata.get("kernel_lowering_requested")):
        return True
    estimator_family = str(metadata.get("estimator_family", "")).strip().lower()
    if estimator_family in {"kernel", "rkhs", "cme", "kiv"}:
        return True
    requested_template = str(metadata.get("kernel_template", "")).strip()
    if requested_template:
        return True
    id_method = ast.identification_method.lower()
    return any(token in id_method for token in ("kernel", "rkhs", "cme", "kiv"))


def build_default_output_kernel(*, distributional: bool) -> KernelSpec:
    """Project default output kernel for distributional or operator targets."""

    return KernelSpec(
        name="rbf",
        params={"bandwidth": "median_heuristic"},
        characteristic=distributional,
        weak_metrizing=distributional,
    )


def build_kernel_estimator_spec(
    ast: EstimandAST,
    *,
    shape: str,
    identification_metadata: dict[str, Any] | None = None,
) -> KernelEstimatorSpec:
    """Build a typed kernel lowering spec from an identified causal estimand."""

    metadata = dict(identification_metadata or {})
    proof_status = str(metadata.get("proof_status", "identified"))
    proof_bundle_ref = _maybe_model_ref(metadata.get("proof_bundle_ref"), ProofBundleRef)
    estimand_ref = _maybe_model_ref(metadata.get("estimand_ref"), EstimandASTRef)
    distributional = _is_distributional_ast(ast, metadata)
    target_representation = _select_target_representation(metadata, distributional=distributional)
    output_kernel = _select_output_kernel(metadata, distributional=distributional)
    template = _select_template(shape, metadata)
    operator_certificate = bool(metadata.get("operator_certificate_present"))
    blocking_reasons: list[str] = []
    disposition = KernelLoweringDisposition.READY
    variable_roles = _extract_variable_roles(ast, template, metadata)
    side_conditions = _extract_side_conditions(ast)

    if proof_status != "identified":
        disposition = KernelLoweringDisposition.PROOF_ONLY
        blocking_reasons.append(f"proof_status={proof_status}")
    elif template is None:
        disposition = KernelLoweringDisposition.UNSUPPORTED
        blocking_reasons.append(f"unsupported_shape={shape}")
    elif (
        template
        in {
            KernelEstimatorTemplate.KIV,
            KernelEstimatorTemplate.PROXIMAL_MINIMAX,
        }
        and not operator_certificate
    ):
        disposition = KernelLoweringDisposition.PROOF_ONLY
        blocking_reasons.append("operator_certificate_missing")
    elif (
        distributional
        and target_representation
        in {
            KernelTargetRepresentation.MEAN_EMBEDDING,
            KernelTargetRepresentation.DISTRIBUTION_DIFFERENCE,
        }
        and not output_kernel.characteristic
    ):
        disposition = KernelLoweringDisposition.REPRESENTATION_ONLY
        blocking_reasons.append("output_kernel_not_characteristic")

    if template is None:
        template = KernelEstimatorTemplate.BACKDOOR_CME

    lambda_value = _coerce_positive_float(metadata.get("kernel_lambda"), default=5.0e-2)
    regularization = KernelRegularization(
        selection=(
            KernelRegularizationSelection.STABILITY_GUARDED_CV
            if template
            not in {
                KernelEstimatorTemplate.KIV,
                KernelEstimatorTemplate.PROXIMAL_MINIMAX,
            }
            else KernelRegularizationSelection.CV
        ),
        lambda_value=lambda_value,
        lambda_schedule=_lambda_schedule(metadata, center=lambda_value),
        cross_fit_folds=(
            int(metadata["cross_fit_folds"])
            if metadata.get("cross_fit_folds") is not None
            else None
        ),
    )
    nuisance_plan = tuple(_nuisance_plan_for_template(template))
    diagnostics_plan = tuple(_diagnostics_for_template(template, distributional=distributional))
    consistency_claim = _consistency_claim_for_template(template, metadata)

    return KernelEstimatorSpec(
        estimand_hash=content_hash(to_canonical_bytes(ast.canonical_payload())),
        estimand_ref=estimand_ref,
        proof_bundle_ref=proof_bundle_ref,
        template=template,
        target_representation=target_representation,
        lowering_disposition=disposition,
        output_kernel=output_kernel,
        input_kernels=_default_input_kernels(template),
        regularization=regularization,
        variable_roles=variable_roles,
        required_side_conditions=side_conditions,
        nuisance_plan=nuisance_plan,
        diagnostics_plan=diagnostics_plan,
        consistency_claim=consistency_claim,
        blocking_reasons=tuple(blocking_reasons),
        metadata={
            "shape": shape,
            "distributional": distributional,
            "operator_certificate_present": operator_certificate,
            "weak_metrizing": output_kernel.weak_metrizing,
            "domain_roles": _extract_domain_roles(ast),
            "query_str": ast.query_str,
        },
    )


def _select_template(
    shape: str,
    metadata: dict[str, Any],
) -> KernelEstimatorTemplate | None:
    explicit = str(metadata.get("kernel_template", "")).strip().lower()
    if explicit:
        try:
            return KernelEstimatorTemplate(explicit)
        except ValueError:
            return None
    if shape in {"backdoor", "dml_compatible", "conditional_do", "stochastic_intervention"}:
        binary_treatment = bool(metadata.get("binary_treatment"))
        if binary_treatment and bool(metadata.get("kernel_dr_allowed", True)):
            return KernelEstimatorTemplate.DR_CME
        return KernelEstimatorTemplate.BACKDOOR_CME
    if shape == "frontdoor":
        return KernelEstimatorTemplate.FRONTDOOR_CME
    if shape == "transport_reweight":
        return KernelEstimatorTemplate.TRANSPORT_CME
    if shape == "iv":
        return KernelEstimatorTemplate.KIV
    if shape in {"measurement_error_proxy", "proximal_mediation"}:
        return KernelEstimatorTemplate.PROXIMAL_MINIMAX
    return None


def _select_target_representation(
    metadata: dict[str, Any],
    *,
    distributional: bool,
) -> KernelTargetRepresentation:
    explicit = str(metadata.get("kernel_target_representation", "")).strip().lower()
    if explicit:
        return KernelTargetRepresentation(explicit)
    if distributional:
        return KernelTargetRepresentation.MEAN_EMBEDDING
    return KernelTargetRepresentation.EFFECT_OPERATOR


def _select_output_kernel(
    metadata: dict[str, Any],
    *,
    distributional: bool,
) -> KernelSpec:
    payload = metadata.get("output_kernel")
    if isinstance(payload, KernelSpec):
        return payload
    if isinstance(payload, dict):
        return KernelSpec.model_validate(payload)
    return build_default_output_kernel(distributional=distributional)


def _default_input_kernels(template: KernelEstimatorTemplate) -> dict[str, KernelSpec]:
    shared = KernelSpec(name="rbf", params={"bandwidth": "median_heuristic"})
    if template is KernelEstimatorTemplate.FRONTDOOR_CME:
        return {
            "treatment": shared,
            "mediator": shared,
            "outcome": shared,
        }
    if template is KernelEstimatorTemplate.TRANSPORT_CME:
        return {
            "covariates": shared,
            "target": shared,
        }
    if template is KernelEstimatorTemplate.KIV:
        return {
            "instrument": shared,
            "treatment": shared,
        }
    return {"covariates": shared}


def _nuisance_plan_for_template(
    template: KernelEstimatorTemplate,
) -> list[KernelNuisanceSpec]:
    if template is KernelEstimatorTemplate.BACKDOOR_CME:
        return [
            KernelNuisanceSpec(
                role="cme_y_given_xz",
                method_hint="causal.kernel.nuisance.fit_cme_y_given_xz",
                diagnostics=("kernel_semantics", "regularization_stability"),
            ),
        ]
    if template is KernelEstimatorTemplate.FRONTDOOR_CME:
        return [
            KernelNuisanceSpec(
                role="cme_m_given_x",
                method_hint="causal.kernel.nuisance.fit_cme_m_given_x",
            ),
            KernelNuisanceSpec(
                role="cme_y_given_mx",
                method_hint="causal.kernel.nuisance.fit_cme_y_given_mx",
            ),
        ]
    if template is KernelEstimatorTemplate.TRANSPORT_CME:
        return [
            KernelNuisanceSpec(
                role="cme_y_given_xz",
                method_hint="causal.kernel.nuisance.fit_cme_y_given_xz",
            ),
            KernelNuisanceSpec(
                role="density_ratio",
                method_hint="causal.kernel.nuisance.fit_density_ratio",
                diagnostics=("overlap",),
            ),
        ]
    if template is KernelEstimatorTemplate.DR_CME:
        return [
            KernelNuisanceSpec(
                role="cme_y_given_xz",
                method_hint="causal.kernel.nuisance.fit_cme_y_given_xz",
            ),
            KernelNuisanceSpec(
                role="propensity",
                method_hint="causal.kernel.nuisance.fit_propensity",
                diagnostics=("overlap",),
            ),
        ]
    if template is KernelEstimatorTemplate.KIV:
        return [
            KernelNuisanceSpec(
                role="kiv_first_stage",
                method_hint="causal.kernel.nuisance.fit_kiv_first_stage",
                diagnostics=("operator_injectivity", "regularization_stability"),
            ),
            KernelNuisanceSpec(
                role="kiv_second_stage",
                method_hint="causal.kernel.nuisance.fit_kiv_second_stage",
                diagnostics=("operator_injectivity",),
            ),
        ]
    return [
        KernelNuisanceSpec(
            role="proximal_bridge",
            method_hint="causal.kernel.nuisance.solve_proximal_bridge",
            diagnostics=("operator_injectivity", "regularization_stability"),
        ),
    ]


def _diagnostics_for_template(
    template: KernelEstimatorTemplate,
    *,
    distributional: bool,
) -> list[str]:
    diagnostics = [
        "kernel_semantics",
        "regularization_stability",
        "causal_side_conditions",
    ]
    if template in {
        KernelEstimatorTemplate.TRANSPORT_CME,
        KernelEstimatorTemplate.DR_CME,
    }:
        diagnostics.append("overlap")
    if template in {
        KernelEstimatorTemplate.KIV,
        KernelEstimatorTemplate.PROXIMAL_MINIMAX,
    }:
        diagnostics.append("operator_injectivity")
    if distributional:
        diagnostics.append("weak_metrization")
    if distributional:
        diagnostics.append("distributional_effect_test")
    return diagnostics


def _consistency_claim_for_template(
    template: KernelEstimatorTemplate,
    metadata: dict[str, Any],
) -> KernelConsistencyClaim:
    explicit = str(metadata.get("kernel_consistency_claim", "")).strip().lower()
    if explicit:
        return KernelConsistencyClaim(explicit)
    if template in {
        KernelEstimatorTemplate.FRONTDOOR_CME,
        KernelEstimatorTemplate.DR_CME,
    }:
        return KernelConsistencyClaim.UNIFORM
    if template in {
        KernelEstimatorTemplate.KIV,
        KernelEstimatorTemplate.PROXIMAL_MINIMAX,
    }:
        return KernelConsistencyClaim.NONE
    return KernelConsistencyClaim.RKHS_NORM


def _is_distributional_ast(
    ast: EstimandAST,
    metadata: dict[str, Any],
) -> bool:
    if str(metadata.get("query_kind", "")).strip().lower() == "distribution_law":
        return True
    if str(metadata.get("distributional_query_kind", "")).strip():
        return True
    if isinstance(ast.root, DistributionLawNode):
        return True
    return _node_has_event(ast.root)


def _node_has_event(node: Any) -> bool:
    if isinstance(node, DistributionRef):
        return isinstance(node.event, EventPredicate)
    if hasattr(node, "operand"):
        return _node_has_event(node.operand)
    if hasattr(node, "factors"):
        return any(_node_has_event(child) for child in node.factors)
    if hasattr(node, "numerator") or hasattr(node, "denominator"):
        return _node_has_event(getattr(node, "numerator", None)) or _node_has_event(
            getattr(node, "denominator", None)
        )
    if hasattr(node, "inner_do_node"):
        return _node_has_event(node.inner_do_node)
    if hasattr(node, "inner_node"):
        inner = node.inner_node
        return False if inner is None else _node_has_event(inner)
    return False


def _maybe_model_ref(payload: Any, ref_type: type[Any]) -> Any | None:
    if payload is None:
        return None
    if isinstance(payload, ref_type):
        return payload
    if isinstance(payload, dict):
        try:
            return ref_type.model_validate(payload)
        except Exception:
            return None
    return None


def _extract_variable_roles(
    ast: EstimandAST,
    template: KernelEstimatorTemplate | None,
    metadata: dict[str, Any],
) -> dict[str, tuple[str, ...]]:
    explicit = metadata.get("variable_roles")
    roles: dict[str, tuple[str, ...]] = {}
    if isinstance(explicit, dict):
        for key, value in explicit.items():
            if isinstance(value, str):
                roles[str(key)] = (value,)
            elif isinstance(value, (list, tuple, set, frozenset)):
                normalized = tuple(str(item) for item in value if str(item).strip())
                if normalized:
                    roles[str(key)] = normalized

    roles.setdefault("treatment", (ast.treatment,))
    roles.setdefault("outcome", (ast.outcome,))

    dist_refs = ast.collect_distribution_refs()
    if isinstance(ast.root, DistributionLawNode):
        covariates = tuple(
            value for value in ast.root.conditioning if value not in {ast.treatment, ast.outcome}
        )
        if covariates:
            roles.setdefault("covariates", covariates)
    else:
        covariate_candidates = sorted(
            {
                variable
                for ref in dist_refs
                for variable in ref.conditioning
                if variable not in {ast.treatment, ast.outcome}
            }
        )
        if covariate_candidates:
            roles.setdefault("covariates", tuple(covariate_candidates))

    if template is KernelEstimatorTemplate.FRONTDOOR_CME:
        mediator = _guess_frontdoor_mediator(ast)
        if mediator is not None:
            roles.setdefault("mediator", (mediator,))

    if template is KernelEstimatorTemplate.KIV:
        roles.setdefault("instrument", tuple(metadata.get("instrument_names", ("instrument",))))
    if template is KernelEstimatorTemplate.PROXIMAL_MINIMAX:
        roles.setdefault(
            "treatment_proxy",
            tuple(metadata.get("treatment_proxy_names", ("treatment_proxy",))),
        )
        roles.setdefault(
            "outcome_proxy",
            tuple(metadata.get("outcome_proxy_names", ("outcome_proxy",))),
        )

    return dict(sorted(roles.items()))


def _guess_frontdoor_mediator(ast: EstimandAST) -> str | None:
    dist_refs = ast.collect_distribution_refs()
    mediator_candidates = sorted(
        {
            variable
            for ref in dist_refs
            if ast.treatment in ref.conditioning
            for variable in ref.variables
            if variable not in {ast.treatment, ast.outcome}
        }
    )
    if not mediator_candidates:
        return None
    outcome_conditioning = {
        variable
        for ref in dist_refs
        if ast.outcome in ref.variables
        for variable in ref.conditioning
    }
    for candidate in mediator_candidates:
        if candidate in outcome_conditioning:
            return candidate
    return mediator_candidates[0]


def _extract_side_conditions(ast: EstimandAST) -> tuple[str, ...]:
    observed: set[str] = {condition.kind.value for condition in ast.side_conditions}
    for ref in ast.collect_distribution_refs():
        observed.update(condition.kind.value for condition in ref.side_conditions)
    return tuple(sorted(observed))


def _extract_domain_roles(ast: EstimandAST) -> dict[str, tuple[str, ...]]:
    domain_roles: dict[str, list[str]] = {
        DistributionDomain.SOURCE.value: [],
        DistributionDomain.TARGET.value: [],
        DistributionDomain.EXPERIMENTAL.value: [],
    }
    for ref in ast.collect_distribution_refs():
        if ref.dataset_ref is not None:
            domain_roles[ref.domain.value].append(ref.dataset_ref)
    if isinstance(ast.root, DistributionLawNode) and ast.root.dataset_ref is not None:
        domain_roles[ast.root.domain.value].append(ast.root.dataset_ref)
    return {
        domain: tuple(sorted(dict.fromkeys(values)))
        for domain, values in domain_roles.items()
        if values
    }


def _lambda_schedule(metadata: dict[str, Any], *, center: float) -> tuple[float, ...]:
    explicit = metadata.get("kernel_lambda_schedule")
    if isinstance(explicit, (list, tuple)):
        schedule = tuple(
            float(value)
            for value in explicit
            if _coerce_positive_float(value, default=None) is not None
        )
        if schedule:
            return schedule
    return (center / 10.0, center, center * 10.0)


def _coerce_positive_float(value: Any, *, default: float | None) -> float | None:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return default
    if numeric <= 0.0:
        return default
    return numeric


__all__ = [
    "build_default_output_kernel",
    "build_kernel_estimator_spec",
    "should_request_kernel_lowering",
]
