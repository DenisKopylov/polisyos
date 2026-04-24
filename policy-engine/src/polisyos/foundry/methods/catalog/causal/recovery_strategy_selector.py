"""Compile-time recovery strategy selection for missing-data estimands.

This module bridges the A-layer recoverability proof artifacts and the B-layer
estimator compiler.  It extracts a compact, typed profile from either:

- an ordered-recovery / full-law :class:`EstimandAST`,
- a recoverability certificate payload (full model dump or summary dict), or
- both together.

The resulting profile is then mapped to a recovery estimator family:

- complete-case
- inverse-probability weighting (IPW)
- augmentation / outcome regression
- doubly robust (AIPW / TMLE family)
- explicit refusal

The implementation intentionally prefers honest refusal for assumption-sensitive
MNAR-style certificates unless the caller explicitly opts into assumption
reliance.  This keeps the compiler aligned with PolicyOS's "honest degradation"
design.
"""

from __future__ import annotations

import dataclasses
from enum import Enum
from typing import Any

from pydantic import BaseModel

from polisyos.ir.analytics.estimand import EstimandAST, RatioNode, RecoveredDistNode


class RecoveryForm(str, Enum):
    """Structural form of the recoverability proof."""

    CONDITIONING = "conditioning"
    REWEIGHTING = "reweighting"
    AUGMENTATION = "augmentation"
    MIXED = "mixed"
    UNKNOWN = "unknown"


class RecoveryNuisance(str, Enum):
    """Nuisance object families exposed by the recoverability proof."""

    PROPENSITY = "propensity"
    OUTCOME_REGRESSION = "outcome_regression"
    DENSITY_RATIO = "density_ratio"
    ODDS_RATIO = "odds_ratio"


class RecoveryEstimatorFamily(str, Enum):
    """High-level estimator family for missing-data recovery."""

    COMPLETE_CASE = "complete_case"
    IPW = "ipw"
    AUGMENTATION = "augmentation"
    DOUBLY_ROBUST = "doubly_robust"
    REFUSE = "refuse"


@dataclasses.dataclass(frozen=True)
class RecoveryCompileProfile:
    """Typed proof-side profile consumed by the estimator compiler."""

    status: str
    recovery_form: RecoveryForm
    identified_nuisance: tuple[RecoveryNuisance, ...]
    required_side_conditions: tuple[str, ...]
    blocking_structures: tuple[str, ...]
    missingness_kinds: tuple[str, ...]
    can_complete_case: bool
    can_ipw: bool
    can_augmentation: bool
    can_doubly_robust: bool
    assumption_sensitive: bool
    notes: str = ""

    def to_summary_dict(self) -> dict[str, Any]:
        """Serialize the profile into JSON-friendly metadata."""
        return {
            "status": self.status,
            "recovery_form": self.recovery_form.value,
            "identified_nuisance": [item.value for item in self.identified_nuisance],
            "required_side_conditions": list(self.required_side_conditions),
            "blocking_structures": list(self.blocking_structures),
            "missingness_kinds": list(self.missingness_kinds),
            "can_complete_case": self.can_complete_case,
            "can_ipw": self.can_ipw,
            "can_augmentation": self.can_augmentation,
            "can_doubly_robust": self.can_doubly_robust,
            "assumption_sensitive": self.assumption_sensitive,
            "notes": self.notes,
        }


@dataclasses.dataclass(frozen=True)
class RecoveryReadinessProfile:
    """Normalized readiness payload consumed by strategy selection."""

    decision: str
    can_compile_estimation: bool | None
    can_run_estimation: bool | None
    passes_positivity: bool | None
    ess_fraction: float | None
    overlap_score: float | None
    blocking_reasons: tuple[str, ...]
    warnings: tuple[str, ...]


@dataclasses.dataclass(frozen=True)
class RecoveryStrategyPlan:
    """Compiler-ready strategy choice for a recoverability certificate."""

    family: RecoveryEstimatorFamily
    preferred_strategy: str
    required_nuisance: tuple[str, ...]
    safety_guards: tuple[str, ...]
    compiler_lowering_hooks: tuple[str, ...]
    confidence: float
    reason: str
    profile: RecoveryCompileProfile

    def to_summary_dict(self) -> dict[str, Any]:
        """Serialize the strategy plan into JSON-friendly metadata."""
        return {
            "family": self.family.value,
            "preferred_strategy": self.preferred_strategy,
            "required_nuisance": list(self.required_nuisance),
            "safety_guards": list(self.safety_guards),
            "compiler_lowering_hooks": list(self.compiler_lowering_hooks),
            "confidence": self.confidence,
            "reason": self.reason,
            "profile": self.profile.to_summary_dict(),
        }


def has_recovery_context(
    ast: EstimandAST,
    recoverability_certificate: Any | None = None,
) -> bool:
    """Return ``True`` when either the AST or the certificate indicates recovery."""
    if collect_recovered_dist_nodes(ast):
        return True
    id_method = (ast.identification_method or "").lower()
    if "ordered_recovery" in id_method or "full_law" in id_method:
        return True
    payload = _coerce_payload(recoverability_certificate)
    return payload is not None


def collect_recovered_dist_nodes(ast: EstimandAST | Any) -> list[RecoveredDistNode]:
    """Collect all ``RecoveredDistNode`` instances reachable from *ast*."""
    root = ast.root if isinstance(ast, EstimandAST) else ast
    return [node for node in _iter_pydantic_nodes(root) if isinstance(node, RecoveredDistNode)]


def infer_recovery_compile_profile(
    ast: EstimandAST | None = None,
    *,
    recoverability_certificate: Any | None = None,
) -> RecoveryCompileProfile:
    """Build a typed compile-time profile from AST/certificate evidence."""
    payload = _coerce_payload(recoverability_certificate)
    compile_time_payload = _extract_compile_time_payload(payload)
    if compile_time_payload is not None:
        return _profile_from_payload(compile_time_payload, payload=payload)

    status = _extract_status(payload)
    blocking = _extract_blocking(payload)
    recovered_nodes = collect_recovered_dist_nodes(ast) if ast is not None else []

    if not recovered_nodes:
        assumption_sensitive = status == "recoverable_under_assumptions" or bool(blocking)
        return RecoveryCompileProfile(
            status=status,
            recovery_form=RecoveryForm.UNKNOWN,
            identified_nuisance=(),
            required_side_conditions=(),
            blocking_structures=blocking,
            missingness_kinds=(),
            can_complete_case=False,
            can_ipw=False,
            can_augmentation=False,
            can_doubly_robust=False,
            assumption_sensitive=assumption_sensitive,
            notes="Recovery context present, but no typed recovered factors were available.",
        )

    missingness_kinds = tuple(
        sorted({str(node.missingness_kind or "unknown") for node in recovered_nodes})
    )
    recovery_form = RecoveryForm.CONDITIONING
    if ast is not None and any(
        isinstance(node, RatioNode) for node in _iter_pydantic_nodes(ast.root)
    ):
        recovery_form = RecoveryForm.MIXED

    identified_nuisance = {RecoveryNuisance.OUTCOME_REGRESSION}
    required_side_conditions: set[str] = set()
    blocking_structures = set(blocking)

    fully_observed_or_mar = set(missingness_kinds).issubset({"fully_observed", "mcar", "mar"})
    if fully_observed_or_mar:
        identified_nuisance.add(RecoveryNuisance.PROPENSITY)
        required_side_conditions.add("positivity")
    if recovery_form is RecoveryForm.MIXED:
        identified_nuisance.add(RecoveryNuisance.DENSITY_RATIO)
        required_side_conditions.add("positivity")

    can_complete_case = True
    can_ipw = (
        RecoveryNuisance.PROPENSITY in identified_nuisance
        or RecoveryNuisance.DENSITY_RATIO in identified_nuisance
    )
    can_augmentation = True
    can_doubly_robust = can_ipw and can_augmentation

    assumption_sensitive = (
        status == "recoverable_under_assumptions"
        or bool(blocking_structures)
        or any(kind == "mnar" for kind in missingness_kinds)
    )
    if any(kind == "mnar" for kind in missingness_kinds):
        required_side_conditions.add("missingness_assumption_review")

    notes = (
        "Ordered-recovery factors detected: conditioning-based recovery "
        f"over missingness kinds {', '.join(missingness_kinds)}."
    )
    return RecoveryCompileProfile(
        status=status,
        recovery_form=recovery_form,
        identified_nuisance=tuple(sorted(identified_nuisance, key=lambda item: item.value)),
        required_side_conditions=tuple(sorted(required_side_conditions)),
        blocking_structures=tuple(sorted(blocking_structures)),
        missingness_kinds=missingness_kinds,
        can_complete_case=can_complete_case,
        can_ipw=can_ipw,
        can_augmentation=can_augmentation,
        can_doubly_robust=can_doubly_robust,
        assumption_sensitive=assumption_sensitive,
        notes=notes,
    )


def select_recovery_strategy(
    ast: EstimandAST | None = None,
    *,
    recoverability_certificate: Any | None = None,
    data_readiness: Any | None = None,
    n_obs: int | None = None,
    covariate_dim: int | None = None,
    allow_assumption_reliance: bool = False,
) -> RecoveryStrategyPlan:
    """Map a recoverability certificate/profile to an estimator family."""
    profile = infer_recovery_compile_profile(
        ast,
        recoverability_certificate=recoverability_certificate,
    )
    readiness = _coerce_readiness_profile(data_readiness)
    guards = _default_safety_guards(profile, readiness)

    if profile.status == "not_recoverable":
        return RecoveryStrategyPlan(
            family=RecoveryEstimatorFamily.REFUSE,
            preferred_strategy="refuse",
            required_nuisance=(),
            safety_guards=guards,
            compiler_lowering_hooks=_lowering_hooks(
                RecoveryEstimatorFamily.REFUSE,
                preferred_strategy="refuse",
            ),
            confidence=0.95,
            reason="Recoverability certificate is not positive; estimation must refuse.",
            profile=profile,
        )

    if _readiness_requires_refusal(readiness):
        blocking = ", ".join(readiness.blocking_reasons) if readiness is not None else ""
        reason = (
            "Data readiness gate blocks missing-data recovery compilation."
            if not blocking
            else f"Data readiness gate blocks missing-data recovery compilation: {blocking}."
        )
        return RecoveryStrategyPlan(
            family=RecoveryEstimatorFamily.REFUSE,
            preferred_strategy="refuse",
            required_nuisance=(),
            safety_guards=guards,
            compiler_lowering_hooks=_lowering_hooks(
                RecoveryEstimatorFamily.REFUSE,
                preferred_strategy="refuse",
            ),
            confidence=0.92,
            reason=reason,
            profile=profile,
        )

    if profile.assumption_sensitive and not allow_assumption_reliance:
        return RecoveryStrategyPlan(
            family=RecoveryEstimatorFamily.REFUSE,
            preferred_strategy="refuse",
            required_nuisance=(),
            safety_guards=guards + ("require_human_assumption_acceptance",),
            compiler_lowering_hooks=_lowering_hooks(
                RecoveryEstimatorFamily.REFUSE,
                preferred_strategy="refuse",
            ),
            confidence=0.9,
            reason=(
                "Recovery depends on unresolved missingness assumptions or blocking "
                "structures; automatic compilation refuses until assumptions are accepted."
            ),
            profile=profile,
        )

    if profile.can_doubly_robust:
        prefer_tmle = n_obs is not None and n_obs < 500
        if _readiness_suggests_weight_instability(readiness):
            prefer_tmle = True
        if covariate_dim is not None and covariate_dim > 5:
            prefer_tmle = False
        preferred = "tmle" if prefer_tmle else "aipw"
        return RecoveryStrategyPlan(
            family=RecoveryEstimatorFamily.DOUBLY_ROBUST,
            preferred_strategy=preferred,
            required_nuisance=("propensity", "outcome_regression"),
            safety_guards=guards,
            compiler_lowering_hooks=_lowering_hooks(
                RecoveryEstimatorFamily.DOUBLY_ROBUST,
                preferred_strategy=preferred,
            ),
            confidence=0.88,
            reason=(
                "Certificate identifies both missingness and outcome nuisances; "
                "compile to a doubly robust recovery estimator."
            ),
            profile=profile,
        )

    if profile.can_ipw:
        return RecoveryStrategyPlan(
            family=RecoveryEstimatorFamily.IPW,
            preferred_strategy="ipw",
            required_nuisance=("propensity",),
            safety_guards=guards,
            compiler_lowering_hooks=_lowering_hooks(
                RecoveryEstimatorFamily.IPW,
                preferred_strategy="ipw",
            ),
            confidence=0.8,
            reason="Certificate exposes an estimable observation propensity / reweighting path.",
            profile=profile,
        )

    if profile.can_augmentation:
        return RecoveryStrategyPlan(
            family=RecoveryEstimatorFamily.AUGMENTATION,
            preferred_strategy="augmentation",
            required_nuisance=("outcome_regression",),
            safety_guards=guards,
            compiler_lowering_hooks=_lowering_hooks(
                RecoveryEstimatorFamily.AUGMENTATION,
                preferred_strategy="augmentation",
            ),
            confidence=0.75,
            reason="Certificate supports conditioning-based recovery via augmentation.",
            profile=profile,
        )

    if profile.can_complete_case:
        return RecoveryStrategyPlan(
            family=RecoveryEstimatorFamily.COMPLETE_CASE,
            preferred_strategy="complete_case",
            required_nuisance=(),
            safety_guards=guards,
            compiler_lowering_hooks=_lowering_hooks(
                RecoveryEstimatorFamily.COMPLETE_CASE,
                preferred_strategy="complete_case",
            ),
            confidence=0.55,
            reason="Only complete-case recovery remains admissible from the proof structure.",
            profile=profile,
        )

    return RecoveryStrategyPlan(
        family=RecoveryEstimatorFamily.REFUSE,
        preferred_strategy="refuse",
        required_nuisance=(),
        safety_guards=guards,
        compiler_lowering_hooks=_lowering_hooks(
            RecoveryEstimatorFamily.REFUSE,
            preferred_strategy="refuse",
        ),
        confidence=0.7,
        reason="No valid recovery estimator family could be derived from the certificate.",
        profile=profile,
    )


def build_compile_time_recovery_summary(
    ast: EstimandAST | None = None,
    *,
    recoverability_certificate: Any | None = None,
    data_readiness: Any | None = None,
    n_obs: int | None = None,
    covariate_dim: int | None = None,
    allow_assumption_reliance: bool = False,
) -> dict[str, Any]:
    """Return the JSON-friendly compile-time strategy summary."""
    plan = select_recovery_strategy(
        ast,
        recoverability_certificate=recoverability_certificate,
        data_readiness=data_readiness,
        n_obs=n_obs,
        covariate_dim=covariate_dim,
        allow_assumption_reliance=allow_assumption_reliance,
    )
    return plan.to_summary_dict()


def _default_safety_guards(
    profile: RecoveryCompileProfile,
    readiness: RecoveryReadinessProfile | None = None,
) -> tuple[str, ...]:
    guards: list[str] = ["recoverability_certificate_check"]
    if "positivity" in profile.required_side_conditions:
        guards.append("positivity_check")
    if profile.can_ipw or profile.can_doubly_robust:
        guards.extend(["weight_truncation", "minimum_effective_sample_size"])
    if profile.assumption_sensitive:
        guards.append("assumption_sensitivity_reporting")
    if readiness is not None:
        guards.append("data_readiness_gate")
        if readiness.decision == "warn":
            guards.append("readiness_warning_reporting")
        if _readiness_suggests_weight_instability(readiness):
            guards.extend(["weight_stability_diagnostics", "stabilized_weight_review"])
    return tuple(dict.fromkeys(guards))


def _lowering_hooks(
    family: RecoveryEstimatorFamily,
    *,
    preferred_strategy: str,
) -> tuple[str, ...]:
    if family is RecoveryEstimatorFamily.DOUBLY_ROBUST:
        return (
            f"missing_data.{preferred_strategy}",
            "recovered_dist.dr",
        )
    if family is RecoveryEstimatorFamily.IPW:
        return ("missing_data.ipw", "recovered_dist.ipw")
    if family is RecoveryEstimatorFamily.AUGMENTATION:
        return ("missing_data.augmentation", "recovered_dist.augmentation")
    if family is RecoveryEstimatorFamily.COMPLETE_CASE:
        return ("missing_data.complete_case", "recovered_dist.complete_case")
    return ("missing_data.refusal",)


def _coerce_payload(recoverability_certificate: Any | None) -> dict[str, Any] | None:
    if recoverability_certificate is None:
        return None
    if isinstance(recoverability_certificate, dict):
        return dict(recoverability_certificate)
    if hasattr(recoverability_certificate, "model_dump"):
        return recoverability_certificate.model_dump(mode="json")
    return None


def _coerce_readiness_profile(data_readiness: Any | None) -> RecoveryReadinessProfile | None:
    if data_readiness is None:
        return None
    if isinstance(data_readiness, dict):
        payload = dict(data_readiness)
    elif hasattr(data_readiness, "model_dump"):
        payload = data_readiness.model_dump(mode="json")
    else:
        return None
    positivity = payload.get("positivity")
    positivity_payload = positivity if isinstance(positivity, dict) else {}
    return RecoveryReadinessProfile(
        decision=str(payload.get("decision", "unknown") or "unknown"),
        can_compile_estimation=_coerce_optional_bool(payload.get("can_compile_estimation")),
        can_run_estimation=_coerce_optional_bool(payload.get("can_run_estimation")),
        passes_positivity=_coerce_optional_bool(positivity_payload.get("passes_positivity")),
        ess_fraction=_coerce_optional_float(
            positivity_payload.get("ess_fraction", payload.get("metrics", {}).get("ess_fraction"))
            if isinstance(payload.get("metrics"), dict)
            else positivity_payload.get("ess_fraction")
        ),
        overlap_score=_coerce_optional_float(
            positivity_payload.get("overlap_score", payload.get("metrics", {}).get("overlap_score"))
            if isinstance(payload.get("metrics"), dict)
            else positivity_payload.get("overlap_score")
        ),
        blocking_reasons=_coerce_str_tuple(payload.get("blocking_reasons")),
        warnings=_coerce_str_tuple(payload.get("warnings")),
    )


def _coerce_optional_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    return None


def _coerce_optional_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _coerce_str_tuple(value: Any) -> tuple[str, ...]:
    if isinstance(value, (list, tuple)):
        return tuple(str(item) for item in value)
    return ()


def _readiness_requires_refusal(readiness: RecoveryReadinessProfile | None) -> bool:
    if readiness is None:
        return False
    if readiness.decision == "block":
        return True
    if readiness.can_compile_estimation is False or readiness.can_run_estimation is False:
        return True
    if readiness.passes_positivity is False:
        return True
    return False


def _readiness_suggests_weight_instability(readiness: RecoveryReadinessProfile | None) -> bool:
    if readiness is None:
        return False
    if readiness.decision == "warn":
        return True
    if readiness.ess_fraction is not None and readiness.ess_fraction < 0.50:
        return True
    if readiness.overlap_score is not None and readiness.overlap_score < 0.70:
        return True
    return False


def _extract_compile_time_payload(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    if payload is None:
        return None
    nested = payload.get("compile_time_recovery")
    if isinstance(nested, dict):
        return nested
    metadata = payload.get("metadata")
    if isinstance(metadata, dict):
        nested = metadata.get("compile_time_recovery")
        if isinstance(nested, dict):
            return nested
    return None


def _extract_status(payload: dict[str, Any] | None) -> str:
    if payload is None:
        return "recoverable"
    raw = str(payload.get("status", "recoverable") or "recoverable").strip().lower()
    if raw in {"recoverable", "recoverable_under_assumptions", "not_recoverable"}:
        return raw
    return "recoverable"


def _extract_blocking(payload: dict[str, Any] | None) -> tuple[str, ...]:
    if payload is None:
        return ()
    raw = payload.get("blocking_r_nodes", ())
    if isinstance(raw, (list, tuple)):
        return tuple(sorted(str(item) for item in raw))
    return ()


def _profile_from_payload(
    compile_time_payload: dict[str, Any],
    *,
    payload: dict[str, Any] | None = None,
) -> RecoveryCompileProfile:
    profile_payload = compile_time_payload.get("profile")
    source_payload = (
        dict(profile_payload) if isinstance(profile_payload, dict) else dict(compile_time_payload)
    )

    def _bool(name: str, default: bool = False) -> bool:
        return bool(source_payload.get(name, default))

    def _tuple(name: str) -> tuple[str, ...]:
        raw = source_payload.get(name, ())
        if isinstance(raw, (list, tuple)):
            return tuple(str(item) for item in raw)
        return ()

    nuisances: list[RecoveryNuisance] = []
    for item in _tuple("identified_nuisance"):
        try:
            nuisances.append(RecoveryNuisance(item))
        except ValueError:
            continue

    try:
        recovery_form = RecoveryForm(str(source_payload.get("recovery_form", "unknown")))
    except ValueError:
        recovery_form = RecoveryForm.UNKNOWN

    status = (
        _extract_status(payload)
        if payload is not None
        else str(source_payload.get("status", "recoverable"))
    )
    blocking_structures = _tuple("blocking_structures")
    if payload is not None:
        payload_blocking = _extract_blocking(payload)
        if payload_blocking:
            blocking_structures = tuple(sorted(set(blocking_structures) | set(payload_blocking)))
    assumption_sensitive = _bool("assumption_sensitive")
    if status == "recoverable_under_assumptions" or blocking_structures:
        assumption_sensitive = True

    return RecoveryCompileProfile(
        status=status,
        recovery_form=recovery_form,
        identified_nuisance=tuple(sorted(nuisances, key=lambda item: item.value)),
        required_side_conditions=_tuple("required_side_conditions"),
        blocking_structures=blocking_structures,
        missingness_kinds=_tuple("missingness_kinds"),
        can_complete_case=_bool("can_complete_case"),
        can_ipw=_bool("can_ipw"),
        can_augmentation=_bool("can_augmentation"),
        can_doubly_robust=_bool("can_doubly_robust"),
        assumption_sensitive=assumption_sensitive,
        notes=str(source_payload.get("notes", "") or ""),
    )


def _iter_pydantic_nodes(value: Any):
    if isinstance(value, BaseModel):
        yield value
        for field_name in value.__class__.model_fields:
            yield from _iter_pydantic_nodes(getattr(value, field_name))
        return
    if isinstance(value, (list, tuple)):
        for item in value:
            yield from _iter_pydantic_nodes(item)


__all__ = [
    "RecoveryCompileProfile",
    "RecoveryEstimatorFamily",
    "RecoveryForm",
    "RecoveryNuisance",
    "RecoveryStrategyPlan",
    "build_compile_time_recovery_summary",
    "collect_recovered_dist_nodes",
    "has_recovery_context",
    "infer_recovery_compile_profile",
    "select_recovery_strategy",
]
