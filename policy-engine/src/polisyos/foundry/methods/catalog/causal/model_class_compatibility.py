"""Finite-sample model-class compatibility checks for tractable SCM families.

Stage 8.3 starts with the binary instrumental-variable (IV) class because its
observed-data feasibility region is a tractable polytope whose facets are the
instrumental inequalities.  This module turns those inequalities into a
machine-checkable compatibility report and, when violated, a blocking
``NegativeCertificate``.
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from itertools import product
from typing import Any, Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field
from scipy.stats import fisher_exact

from polisyos.ir.analytics.negative_certificate import (
    BlockingType,
    ModelClassCompatibilityReport,
    ModelClassConstraintResult,
    ModelClassFiniteSampleTest,
    NegativeCertificate,
)

_SUPPORTED_BINARY_IV_MODEL_CLASSES = frozenset(
    {
        "iv.binary.unconditional",
        "iv.binary.conditional_on_v",
        "iv.binary.response_polytope",
    }
)


class CompatibilityVerdict(BaseModel):
    """Typed verdict returned by ``check_model_class_compatibility``."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal["compatible", "incompatible", "unsupported"]
    report: ModelClassCompatibilityReport
    negative_certificate: NegativeCertificate | None = None


@dataclass(frozen=True)
class _FamilyTestDecision:
    family_id: str
    raw_p_value: float
    adjusted_p_value: float
    rejected: bool
    witness_constraint_id: str | None


def check_model_class_compatibility(
    *,
    model_class_id: str,
    data: np.ndarray,
    variable_names: Sequence[str],
    observed_variables: Sequence[str],
    alpha: float = 0.05,
    multiple_testing: Literal["holm", "bonferroni", "none"] = "holm",
) -> CompatibilityVerdict:
    """Check whether ``data`` is compatible with a supported SCM model class.

    Currently supported:

    - ``iv.binary.unconditional`` with ``observed_variables=[Z, D, Y]``
    - ``iv.binary.conditional_on_v`` with ``observed_variables=[Z, D, Y, *V]``
    - ``iv.binary.response_polytope`` as an alias for the same tractable family
    """

    requested_model_class_id = _normalize_requested_model_class_id(model_class_id)
    if requested_model_class_id not in _SUPPORTED_BINARY_IV_MODEL_CLASSES:
        report = ModelClassCompatibilityReport(
            compatibility_status="unsupported",
            model_class_id=requested_model_class_id,
            observed_variables=tuple(str(item) for item in observed_variables),
            constraint_family_name="unsupported_model_class",
            finite_sample_test=ModelClassFiniteSampleTest(
                test_name="unsupported",
                alpha=alpha,
                multiple_testing=multiple_testing,
            ),
            evidence_summary={"reason": "unsupported_model_class"},
            warnings=[f"model_class_unsupported:{requested_model_class_id}"],
        )
        return CompatibilityVerdict(status="unsupported", report=report)

    if len(observed_variables) < 3:
        raise ValueError("observed_variables must include at least Z, D, and Y")

    z_name, d_name, y_name = [str(item) for item in observed_variables[:3]]
    conditioning_variables = tuple(str(item) for item in observed_variables[3:])
    column_lookup = {str(name): index for index, name in enumerate(variable_names)}
    missing = [
        name for name in (z_name, d_name, y_name, *conditioning_variables) if name not in column_lookup
    ]
    if missing:
        raise ValueError(f"data is missing required observed variables: {missing}")

    selected_columns = [column_lookup[name] for name in (z_name, d_name, y_name, *conditioning_variables)]
    subset = np.asarray(data[:, selected_columns], dtype=object)
    if subset.ndim != 2:
        raise ValueError("data must be a 2D array")

    complete_mask = np.ones(subset.shape[0], dtype=bool)
    for index in range(subset.shape[1]):
        column = np.asarray(subset[:, index], dtype=object)
        column_mask = np.array([not _is_missing(value) for value in column], dtype=bool)
        complete_mask &= column_mask
    subset = subset[complete_mask]

    warnings: list[str] = []
    complete_n = int(subset.shape[0])
    if complete_n == 0:
        report = ModelClassCompatibilityReport(
            compatibility_status="unsupported",
            model_class_id=requested_model_class_id,
            observed_variables=(z_name, d_name, y_name, *conditioning_variables),
            constraint_family_name="instrumental_inequalities_wang_robins_richardson_2017",
            finite_sample_test=ModelClassFiniteSampleTest(
                test_name="fisher_exact_one_sided",
                alpha=alpha,
                multiple_testing=multiple_testing,
            ),
            evidence_summary={
                "n": 0,
                "complete_case_n": 0,
                "reason": "no_complete_cases",
            },
            warnings=["binary_iv_no_complete_cases"],
        )
        return CompatibilityVerdict(status="unsupported", report=report)

    z = _coerce_binary_column(subset[:, 0], name=z_name)
    d = _coerce_binary_column(subset[:, 1], name=d_name)
    y = _coerce_binary_column(subset[:, 2], name=y_name)

    if conditioning_variables:
        strata_keys = [
            tuple(_jsonable_scalar(value) for value in row)
            for row in np.asarray(subset[:, 3:], dtype=object)
        ]
    else:
        strata_keys = [("__all__",)] * complete_n

    grouped_indices: dict[tuple[Any, ...], list[int]] = defaultdict(list)
    for index, key in enumerate(strata_keys):
        grouped_indices[key].append(index)

    raw_results: list[dict[str, Any]] = []
    supported_constraint_count = 0
    skipped_constraint_count = 0
    max_violation_margin = float("-inf")
    worst_constraint_id: str | None = None

    for stratum_key, indices in grouped_indices.items():
        indices_array = np.asarray(indices, dtype=int)
        z_slice = z[indices_array]
        d_slice = d[indices_array]
        y_slice = y[indices_array]
        n_z1 = int(np.sum(z_slice == 1))
        n_z0 = int(np.sum(z_slice == 0))
        scope = _scope_from_key(conditioning_variables, stratum_key)

        if n_z1 == 0 or n_z0 == 0:
            skipped_constraint_count += 4
            warnings.append(
                "binary_iv_empty_instrument_arm:"
                f"{_scope_token(scope)}:n_z1={n_z1}:n_z0={n_z0}"
            )
            continue

        for d_value, y_value in product((0, 1), repeat=2):
            family_id = _binary_iv_family_id(d_value=d_value, y_value=y_value)
            constraint_id = _binary_iv_constraint_id(
                d_value=d_value,
                y_value=y_value,
                scope=scope,
            )
            expression_ast = _binary_iv_expression(
                z_name=z_name,
                d_name=d_name,
                y_name=y_name,
                d_value=d_value,
                y_value=y_value,
            )
            lhs_z1 = float(np.mean((z_slice == 1) & (d_slice == d_value) & (y_slice == y_value))) / (
                float(np.mean(z_slice == 1)) or 1.0
            )
            lhs_z0_term = float(
                np.mean((z_slice == 0) & (d_slice == d_value) & (y_slice == (1 - y_value)))
            ) / (float(np.mean(z_slice == 0)) or 1.0)
            violation_margin = float(lhs_z1 + lhs_z0_term - 1.0)
            q_success_z1 = int(np.sum((z_slice == 1) & (d_slice == d_value) & (y_slice == y_value)))
            q_fail_z1 = int(n_z1 - q_success_z1)
            q_success_z0 = int(
                np.sum((z_slice == 0) & ~((d_slice == d_value) & (y_slice == (1 - y_value))))
            )
            q_fail_z0 = int(n_z0 - q_success_z0)
            table = np.asarray(
                [
                    [q_success_z1, q_fail_z1],
                    [q_success_z0, q_fail_z0],
                ],
                dtype=int,
            )
            p_value = float(fisher_exact(table, alternative="greater").pvalue)
            supported_constraint_count += 1
            if violation_margin > max_violation_margin:
                max_violation_margin = violation_margin
                worst_constraint_id = constraint_id
            raw_results.append(
                {
                    "constraint_id": constraint_id,
                    "family_id": family_id,
                    "expression_ast": expression_ast,
                    "scope": scope,
                    "lhs_estimate": float(lhs_z1 + lhs_z0_term),
                    "violation_margin": violation_margin,
                    "p_value": p_value,
                    "table": table.tolist(),
                    "n_z1": n_z1,
                    "n_z0": n_z0,
                    "d_value": d_value,
                    "y_value": y_value,
                    "success_rate_z1": float(q_success_z1 / n_z1),
                    "success_rate_z0": float(q_success_z0 / n_z0),
                    "z_name": z_name,
                    "d_name": d_name,
                    "y_name": y_name,
                    "linear_form": _binary_iv_linear_form(
                        z_name=z_name,
                        d_name=d_name,
                        y_name=y_name,
                        d_value=d_value,
                        y_value=y_value,
                    ),
                }
            )

    if supported_constraint_count == 0:
        report = ModelClassCompatibilityReport(
            compatibility_status="unsupported",
            model_class_id=_normalized_model_class_id(conditioning_variables),
            observed_variables=(z_name, d_name, y_name, *conditioning_variables),
            constraint_family_name="instrumental_inequalities_wang_robins_richardson_2017",
            finite_sample_test=ModelClassFiniteSampleTest(
                test_name="fisher_exact_one_sided",
                alpha=alpha,
                multiple_testing=multiple_testing,
            ),
            evidence_summary={
                "n": int(data.shape[0]),
                "complete_case_n": complete_n,
                "tested_constraint_count": 0,
                "skipped_constraint_count": skipped_constraint_count,
                "reason": "no_supported_constraints",
            },
            warnings=_dedupe(warnings or ["binary_iv_no_supported_constraints"]),
        )
        return CompatibilityVerdict(status="unsupported", report=report)

    family_decisions, overall_test_name, family_test_name = _binary_iv_family_decisions(
        raw_results=raw_results,
        alpha=float(alpha),
        multiple_testing=multiple_testing,
        conditional=bool(conditioning_variables),
    )
    constraints: list[ModelClassConstraintResult] = []
    rejection_set: list[str] = []
    family_rejection_set: list[str] = []
    compatibility_status: Literal["compatible", "incompatible", "unsupported"] = "compatible"

    for family_id, decision in family_decisions.items():
        if decision.rejected and decision.witness_constraint_id is not None:
            compatibility_status = "incompatible"
            rejection_set.append(str(decision.witness_constraint_id))
            family_rejection_set.append(str(family_id))

    for entry in raw_results:
        decision = family_decisions[str(entry["family_id"])]
        witness_for_rejected_family = bool(
            decision.rejected and decision.witness_constraint_id == str(entry["constraint_id"])
        )
        constraints.append(
            ModelClassConstraintResult(
                constraint_id=str(entry["constraint_id"]),
                expression_ast=str(entry["expression_ast"]),
                family_id=str(entry["family_id"]),
                scope=dict(entry["scope"]),
                lhs_estimate=float(entry["lhs_estimate"]),
                violation_margin=float(entry["violation_margin"]),
                p_value=float(entry["p_value"]),
                adjusted_p_value=float(decision.adjusted_p_value),
                family_raw_p_value=float(decision.raw_p_value),
                family_adjusted_p_value=float(decision.adjusted_p_value),
                rejected=witness_for_rejected_family,
                witness_for_rejected_family=witness_for_rejected_family,
                metadata={
                    "table": list(entry["table"]),
                    "n_z1": int(entry["n_z1"]),
                    "n_z0": int(entry["n_z0"]),
                    "d_value": int(entry["d_value"]),
                    "y_value": int(entry["y_value"]),
                    "success_rate_z1": float(entry["success_rate_z1"]),
                    "success_rate_z0": float(entry["success_rate_z0"]),
                    "linear_form": dict(entry["linear_form"]),
                    "local_test_name": "fisher_exact_one_sided",
                    "family_test_name": family_test_name,
                },
            )
        )

    normalized_model_class_id = _normalized_model_class_id(conditioning_variables)
    finite_sample_test = ModelClassFiniteSampleTest(
        test_name=overall_test_name,
        alpha=float(alpha),
        multiple_testing=multiple_testing,
        local_test_name="fisher_exact_one_sided",
        family_test_name=family_test_name,
        rejection_set=tuple(rejection_set),
        p_values_by_constraint={
            constraint.constraint_id: float(constraint.p_value or 1.0) for constraint in constraints
        },
        adjusted_p_values_by_constraint={
            constraint.constraint_id: float(constraint.adjusted_p_value or 1.0)
            for constraint in constraints
        },
        family_p_values={
            family_id: float(decision.raw_p_value)
            for family_id, decision in family_decisions.items()
        },
        family_adjusted_p_values={
            family_id: float(decision.adjusted_p_value)
            for family_id, decision in family_decisions.items()
        },
        family_rejection_set=tuple(family_rejection_set),
    )
    summary = {
        "n": int(data.shape[0]),
        "complete_case_n": complete_n,
        "tested_constraint_count": supported_constraint_count,
        "tested_family_count": len(family_decisions),
        "skipped_constraint_count": skipped_constraint_count,
        "family_rejection_count": len(family_rejection_set),
        "max_violation_margin": float(max_violation_margin),
        "worst_constraint_id": worst_constraint_id,
        "conditioning_strata_count": len(grouped_indices),
        "requested_model_class_id": requested_model_class_id,
    }
    report = ModelClassCompatibilityReport(
        compatibility_status=compatibility_status,
        model_class_id=normalized_model_class_id,
        observed_variables=(z_name, d_name, y_name, *conditioning_variables),
        constraint_family_name="instrumental_inequalities_wang_robins_richardson_2017",
        constraint_type="linear_inequality",
        constraints=tuple(constraints),
        finite_sample_test=finite_sample_test,
        evidence_summary=summary,
        warnings=_dedupe(warnings),
    )
    certificate = (
        _negative_certificate_from_compatibility_report(report)
        if compatibility_status == "incompatible"
        else None
    )
    return CompatibilityVerdict(
        status=compatibility_status,
        report=report,
        negative_certificate=certificate,
    )


def _binary_iv_family_decisions(
    *,
    raw_results: Sequence[dict[str, Any]],
    alpha: float,
    multiple_testing: Literal["holm", "bonferroni", "none"],
    conditional: bool,
) -> tuple[dict[str, _FamilyTestDecision], str, str]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for entry in raw_results:
        grouped[str(entry["family_id"])].append(dict(entry))

    ordered_family_ids = sorted(grouped)
    family_raw_p_values: list[float] = []
    witness_candidates: dict[str, str | None] = {}
    family_has_positive_margin: dict[str, bool] = {}

    for family_id in ordered_family_ids:
        entries = grouped[family_id]
        local_p_values = [float(entry["p_value"]) for entry in entries]
        family_raw_p_values.append(_family_raw_p_value(local_p_values))
        family_has_positive_margin[family_id] = any(
            float(entry["violation_margin"]) > 0.0 for entry in entries
        )
        witness = _select_family_witness(entries)
        witness_candidates[family_id] = (
            str(witness["constraint_id"]) if witness is not None else None
        )

    family_adjusted = _adjust_p_values(family_raw_p_values, method=multiple_testing)
    family_decisions: dict[str, _FamilyTestDecision] = {}
    for family_id, raw_p_value, adjusted_p_value in zip(
        ordered_family_ids,
        family_raw_p_values,
        family_adjusted,
        strict=False,
    ):
        rejected = bool(
            family_has_positive_margin[family_id]
            and witness_candidates[family_id] is not None
            and float(adjusted_p_value) < alpha
        )
        family_decisions[family_id] = _FamilyTestDecision(
            family_id=family_id,
            raw_p_value=float(raw_p_value),
            adjusted_p_value=float(adjusted_p_value),
            rejected=rejected,
            witness_constraint_id=witness_candidates[family_id],
        )

    if conditional:
        return (
            family_decisions,
            "gail_simon_style_fisher_union_intersection",
            "gail_simon_style_fisher_union_intersection",
        )
    return (
        family_decisions,
        "fisher_exact_one_sided",
        "constraint_level_identity",
    )


def _family_raw_p_value(local_p_values: Sequence[float]) -> float:
    if not local_p_values:
        return 1.0
    minimum = min(float(value) for value in local_p_values)
    return float(min(1.0, minimum * max(1, len(local_p_values))))


def _select_family_witness(
    entries: Sequence[dict[str, Any]],
) -> dict[str, Any] | None:
    positive_entries = [entry for entry in entries if float(entry["violation_margin"]) > 0.0]
    if not positive_entries:
        return None
    return min(
        positive_entries,
        key=lambda entry: (
            float(entry["p_value"]),
            -float(entry["violation_margin"]),
            str(entry["constraint_id"]),
        ),
    )


def _negative_certificate_from_compatibility_report(
    report: ModelClassCompatibilityReport,
) -> NegativeCertificate:
    rejected = [constraint for constraint in report.constraints if constraint.rejected]
    if not rejected:
        rejected = [
            constraint
            for constraint in report.constraints
            if constraint.witness_for_rejected_family
        ]
    worst = max(rejected, key=lambda item: item.violation_margin or float("-inf"))
    model_label = report.model_class_id.replace("_", " ")
    family_p = float(worst.family_adjusted_p_value or worst.adjusted_p_value or 1.0)
    return NegativeCertificate(
        blocking_type=BlockingType.MODEL_CLASS_INCOMPATIBLE,
        blocking_description=(
            "Observed data are incompatible with the declared SCM class "
            f"`{model_label}`."
        ),
        technical_detail=(
            f"Rejected semialgebraic constraint {worst.constraint_id}: "
            f"{worst.expression_ast} with adjusted_p={family_p:.6g} "
            f"and violation_margin={float(worst.violation_margin or 0.0):.6g}."
        ),
        constructive_message=(
            "Do not continue IV-style estimation under this SCM class on the current data. "
            "Revisit exclusion/independence assumptions, add measured confounders, or switch "
            "to a different identification/bounds strategy."
        ),
        quantitative_diagnostics={
            "model_class_id": report.model_class_id,
            "tested_constraint_count": report.evidence_summary.get("tested_constraint_count"),
            "tested_family_count": report.evidence_summary.get("tested_family_count"),
            "max_violation_margin": report.evidence_summary.get("max_violation_margin"),
            "worst_constraint_id": report.evidence_summary.get("worst_constraint_id"),
            "family_rejection_set": list(report.finite_sample_test.family_rejection_set),
        },
        model_class_compatibility=report,
        suggested_experiments=NegativeCertificate.auto_suggest_experiments(
            BlockingType.MODEL_CLASS_INCOMPATIBLE,
            missing_vars=tuple(report.observed_variables),
        ),
    )


def _normalize_requested_model_class_id(model_class_id: str) -> str:
    return str(model_class_id).strip().lower()


def _normalized_model_class_id(conditioning_variables: Sequence[str]) -> str:
    return "iv.binary.conditional_on_v" if conditioning_variables else "iv.binary.unconditional"


def _binary_iv_expression(
    *,
    z_name: str,
    d_name: str,
    y_name: str,
    d_value: int,
    y_value: int,
) -> str:
    return (
        f"P({d_name}={d_value},{y_name}={y_value}|{z_name}=1) + "
        f"P({d_name}={d_value},{y_name}={1 - y_value}|{z_name}=0) <= 1"
    )


def _binary_iv_constraint_id(
    *,
    d_value: int,
    y_value: int,
    scope: dict[str, Any],
) -> str:
    suffix = ""
    if scope:
        scope_bits = ",".join(f"{key}={value}" for key, value in sorted(scope.items()))
        suffix = f":{scope_bits}"
    return f"iv_binary:d{d_value}:y{y_value}{suffix}"


def _binary_iv_family_id(*, d_value: int, y_value: int) -> str:
    return f"iv_binary_family:d{d_value}:y{y_value}"


def _binary_iv_linear_form(
    *,
    z_name: str,
    d_name: str,
    y_name: str,
    d_value: int,
    y_value: int,
) -> dict[str, Any]:
    return {
        "lhs_terms": [
            {
                "coefficient": 1.0,
                "probability": f"P({d_name}={d_value},{y_name}={y_value}|{z_name}=1)",
                "z_value": 1,
                "d_value": d_value,
                "y_value": y_value,
            },
            {
                "coefficient": 1.0,
                "probability": f"P({d_name}={d_value},{y_name}={1 - y_value}|{z_name}=0)",
                "z_value": 0,
                "d_value": d_value,
                "y_value": 1 - y_value,
            },
        ],
        "rhs": 1.0,
    }


def _scope_from_key(
    variable_names: Sequence[str],
    stratum_key: tuple[Any, ...],
) -> dict[str, Any]:
    if not variable_names:
        return {}
    return {
        str(name): _jsonable_scalar(value)
        for name, value in zip(variable_names, stratum_key, strict=False)
    }


def _scope_token(scope: dict[str, Any]) -> str:
    if not scope:
        return "__all__"
    return ",".join(f"{key}={value}" for key, value in sorted(scope.items()))


def _coerce_binary_column(values: np.ndarray, *, name: str) -> np.ndarray:
    encoded: list[int] = []
    seen: set[int] = set()
    for raw in np.asarray(values, dtype=object).reshape(-1):
        if isinstance(raw, (np.bool_, bool)):
            value = int(bool(raw))
        elif isinstance(raw, (np.integer, int)):
            value = int(raw)
        elif isinstance(raw, (np.floating, float)):
            if not np.isfinite(float(raw)):
                raise ValueError(f"{name} contains missing values after complete-case filtering")
            rounded = round(float(raw))
            if not np.isclose(float(raw), float(rounded)):
                raise ValueError(f"{name} must be binary-coded with values in {{0, 1}}")
            value = int(rounded)
        else:
            raise ValueError(f"{name} must be binary-coded with values in {{0, 1}}")
        if value not in {0, 1}:
            raise ValueError(f"{name} must be binary-coded with values in {{0, 1}}")
        seen.add(value)
        encoded.append(value)
    if len(seen) < 2:
        raise ValueError(f"{name} must contain both 0 and 1 to test binary IV compatibility")
    return np.asarray(encoded, dtype=int)


def _adjust_p_values(
    p_values: list[float],
    *,
    method: Literal["holm", "bonferroni", "none"],
) -> list[float]:
    if method == "none":
        return [max(0.0, min(1.0, float(value))) for value in p_values]
    if method == "bonferroni":
        n = max(1, len(p_values))
        return [min(1.0, float(value) * n) for value in p_values]
    return _holm_adjust(p_values)


def _holm_adjust(p_values: list[float]) -> list[float]:
    if not p_values:
        return []
    n = len(p_values)
    order = np.argsort(np.asarray(p_values, dtype=float))
    adjusted = np.empty(n, dtype=float)
    running = 0.0
    for rank, idx in enumerate(order):
        raw = float(p_values[int(idx)])
        candidate = min(1.0, raw * float(n - rank))
        running = max(running, candidate)
        adjusted[int(idx)] = running
    return [float(value) for value in adjusted]


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, (float, np.floating)):
        return bool(np.isnan(float(value)))
    return False


def _jsonable_scalar(value: Any) -> Any:
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    return value


def _dedupe(values: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        text = str(value)
        if text in seen:
            continue
        seen.add(text)
        ordered.append(text)
    return ordered


__all__ = [
    "CompatibilityVerdict",
    "check_model_class_compatibility",
]
