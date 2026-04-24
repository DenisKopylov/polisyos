"""QualityScoreAggregator — composite quality scoring for causal analysis runs.

Combines three orthogonal quality dimensions into a single CausalQualityReport:

    data_quality   = f(ESS fraction, overlap score, data provenance quality)
    method_quality = f(fidelity tier, determinism tier)
    robustness     = f(sensitivity analysis, falsification tests)

    composite = w_data * data_q + w_method * method_q + w_robustness * robustness_q
               (defaults: 0.35, 0.35, 0.30)

Called from CausalEngine.audit() to attach a CausalQualityReport to EvidenceBundle.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from polisyos.ir.analytics.evidence_bundle import DataProvenance, EstimationStep
from polisyos.ir.analytics.quality_report import (
    CausalQualityReport,
    QualityDimension,
    _score_to_grade,
)

# ---------------------------------------------------------------------------
# FidelityLevel → quality score mapping
# ---------------------------------------------------------------------------

_FIDELITY_SCORES: dict[str, float] = {
    "high": 1.0,
    "HIGH": 1.0,
    "medium": 0.65,
    "MEDIUM": 0.65,
    "low": 0.35,
    "LOW": 0.35,
}

# DeterminismTier → quality contribution
_DETERMINISM_SCORES: dict[str, float] = {
    "strict_cpu": 1.0,
    "library_deterministic": 0.90,
    "statistical": 0.70,
    "best_effort_gpu": 0.60,
    "nondeterministic": 0.30,
}


class QualityScoreAggregator:
    """Aggregates quality scores across data, method, and robustness dimensions.

    Parameters
    ----------
    weights:
        Override the default dimension weights
        ``{"data": 0.35, "method": 0.35, "robustness": 0.30}``.
    """

    DEFAULT_WEIGHTS: dict[str, float] = {
        "data": 0.35,
        "method": 0.35,
        "robustness": 0.30,
    }

    def __init__(self, weights: dict[str, float] | None = None) -> None:
        self._weights = weights or dict(self.DEFAULT_WEIGHTS)

    # ------------------------------------------------------------------
    # Data quality
    # ------------------------------------------------------------------

    def compute_data_quality(
        self,
        data_provenance: tuple[DataProvenance, ...],
        node_outputs: dict[str, Any] | None = None,
    ) -> QualityDimension:
        """Score the data quality dimension.

        Components (all normalised to [0, 1]):
        - ``provenance_quality``: mean of DataProvenance.quality_score values (weight 0.30)
        - ``ess_fraction``:       effective sample size fraction from PositivityDiagnostic (0.40)
        - ``overlap_score``:      overlap score from PositivityDiagnostic (0.30)

        When no diagnostics are available the ESS and overlap sub-scores default to 1.0
        (neutral — not penalised for not running the diagnostic).
        """
        components: dict[str, float] = {}
        warnings: list[str] = []

        # Provenance quality: mean quality_score across all data sources
        if data_provenance:
            prov_scores = [p.quality_score for p in data_provenance]
            components["provenance_quality"] = sum(prov_scores) / len(prov_scores)
            unavailable = [
                p.dataset_ref
                for p in data_provenance
                if p.availability_status not in ("available",)
            ]
            if unavailable:
                warnings.append(f"Data sources with limited availability: {', '.join(unavailable)}")
        else:
            components["provenance_quality"] = 1.0

        # ESS fraction and overlap from node outputs
        ess_frac = 1.0
        overlap = 1.0
        if node_outputs:
            for out in node_outputs.values():
                if not isinstance(out, dict):
                    continue
                result = out.get("result", {})
                if isinstance(result, dict) and "ess_fraction" in result:
                    ess_frac = min(float(result["ess_fraction"]), 1.0)
                    overlap = min(float(result.get("overlap_score", 1.0)), 1.0)
                    break
                # Also check top-level keys (some nodes put scores there directly)
                if "ess_fraction" in out:
                    ess_frac = min(float(out["ess_fraction"]), 1.0)
                    overlap = min(float(out.get("overlap_score", 1.0)), 1.0)
                    break

        components["ess_fraction"] = ess_frac
        components["overlap_score"] = overlap

        if ess_frac < 0.3:
            warnings.append(
                f"Low effective sample size fraction ({ess_frac:.2f}). "
                "Estimates may be highly variable."
            )
        if overlap < 0.5:
            warnings.append(f"Low overlap score ({overlap:.2f}). Positivity may be violated.")

        # Weighted average
        score = (
            0.30 * components["provenance_quality"]
            + 0.40 * components["ess_fraction"]
            + 0.30 * components["overlap_score"]
        )
        score = max(0.0, min(1.0, score))
        return QualityDimension(
            score=round(score, 4),
            grade=_score_to_grade(score),
            components=components,
            warnings=tuple(warnings),
            is_blocking=score < 0.30,
        )

    # ------------------------------------------------------------------
    # Method quality
    # ------------------------------------------------------------------

    def compute_method_quality(
        self,
        estimation_steps: tuple[EstimationStep, ...],
    ) -> QualityDimension:
        """Score the method quality dimension.

        Components:
        - ``fidelity_tier``:     not directly available per-step; defaults to 1.0
        - ``determinism_tier``:  mean DeterminismTier score across all non-nuisance steps
        - ``has_primary_method``: 1.0 when at least one non-nuisance step executed
        """
        components: dict[str, float] = {}
        warnings: list[str] = []

        if not estimation_steps:
            # No estimation was performed (identify-only run)
            components["has_primary_method"] = 0.5
            components["determinism_tier"] = 1.0
            warnings.append("No estimation steps recorded — estimation may not have run.")
            score = 0.5
            return QualityDimension(
                score=round(score, 4),
                grade=_score_to_grade(score),
                components=components,
                warnings=tuple(warnings),
                is_blocking=False,
            )

        primary_steps = [s for s in estimation_steps if not s.is_nuisance]
        components["has_primary_method"] = 1.0 if primary_steps else 0.3

        # Determinism tier score
        det_scores: list[float] = []
        for step in estimation_steps:
            tier = step.determinism_tier or ""
            det_scores.append(_DETERMINISM_SCORES.get(tier, 0.70))

        components["determinism_tier"] = sum(det_scores) / len(det_scores) if det_scores else 1.0

        # Warn on nondeterministic primary steps
        nondeterministic = [
            s.method_fqn for s in primary_steps if s.determinism_tier == "nondeterministic"
        ]
        if nondeterministic:
            warnings.append(
                f"Nondeterministic primary method(s): {', '.join(nondeterministic)}. "
                "Results may not be reproducible."
            )

        score = 0.40 * components["has_primary_method"] + 0.60 * components["determinism_tier"]
        score = max(0.0, min(1.0, score))
        return QualityDimension(
            score=round(score, 4),
            grade=_score_to_grade(score),
            components=components,
            warnings=tuple(warnings),
            is_blocking=score < 0.30,
        )

    # ------------------------------------------------------------------
    # Robustness
    # ------------------------------------------------------------------

    def compute_robustness(
        self,
        node_outputs: dict[str, Any] | None = None,
    ) -> QualityDimension:
        """Score the robustness dimension.

        Components:
        - ``sensitivity_robust``:    1.0 if SensitivityResult.is_robust, else 0.3
        - ``falsification_passed``:  n_passed / n_total from FalsificationReport
        - ``no_critical_failures``:  1.0 if no critical falsification failures

        When no robustness checks were run, all components default to 0.7
        (modest neutral — we don't reward or penalise for skipping).
        """
        components: dict[str, float] = {}
        warnings: list[str] = []
        outputs = node_outputs or {}

        # Sensitivity
        is_robust: bool | None = None
        for out in outputs.values():
            if not isinstance(out, dict):
                continue
            sr = out.get("sensitivity_result")
            if sr is not None:
                is_robust = bool(
                    getattr(sr, "is_robust", None)
                    or (isinstance(sr, dict) and sr.get("is_robust", False))
                )
                e_val = getattr(sr, "e_value", None) or (isinstance(sr, dict) and sr.get("e_value"))
                if e_val is not None:
                    components["e_value_signal"] = min(float(e_val) / 3.0, 1.0)
                break

        if is_robust is None:
            # No sensitivity check was run
            components["sensitivity_robust"] = 0.7
        elif is_robust:
            components["sensitivity_robust"] = 1.0
        else:
            components["sensitivity_robust"] = 0.3
            warnings.append("Sensitivity analysis indicates the estimate is not robust.")

        # Falsification
        n_total = 0
        n_passed_fals = 0
        has_critical_failure = False
        for out in outputs.values():
            if not isinstance(out, dict):
                continue
            refute = out.get("refutation_result")
            if isinstance(refute, dict):
                n_total += 1
                if refute.get("passed", True):
                    n_passed_fals += 1
                elif refute.get("is_critical", False):
                    has_critical_failure = True
                    warnings.append(
                        f"Critical falsification failure: {refute.get('test_name', 'unknown')}"
                    )

        if n_total == 0:
            components["falsification_passed"] = 0.7
            components["no_critical_failures"] = 1.0
        else:
            components["falsification_passed"] = n_passed_fals / n_total
            components["no_critical_failures"] = 0.0 if has_critical_failure else 1.0
            if n_passed_fals < n_total:
                warnings.append(
                    f"{n_total - n_passed_fals}/{n_total} falsification test(s) failed."
                )

        score = (
            0.50 * components["sensitivity_robust"]
            + 0.30 * components.get("falsification_passed", 0.7)
            + 0.20 * components.get("no_critical_failures", 1.0)
        )
        score = max(0.0, min(1.0, score))
        return QualityDimension(
            score=round(score, 4),
            grade=_score_to_grade(score),
            components=components,
            warnings=tuple(warnings),
            is_blocking=has_critical_failure,
        )

    # ------------------------------------------------------------------
    # Aggregate
    # ------------------------------------------------------------------

    def aggregate(
        self,
        data_q: QualityDimension,
        method_q: QualityDimension,
        robustness_q: QualityDimension,
        *,
        run_id: str,
        query_str: str = "",
    ) -> CausalQualityReport:
        """Combine three QualityDimension objects into a CausalQualityReport."""
        w = self._weights
        composite = (
            w["data"] * data_q.score
            + w["method"] * method_q.score
            + w["robustness"] * robustness_q.score
        )
        composite = max(0.0, min(1.0, composite))

        # A blocking dimension forces the composite to F (< 0.40)
        any_blocking = data_q.is_blocking or method_q.is_blocking or robustness_q.is_blocking
        if any_blocking:
            composite = min(composite, 0.39)

        grade = _score_to_grade(composite)
        pub_ready = composite >= 0.70 and not any_blocking

        # Collect caveats from all dimension warnings
        caveats: list[str] = []
        for dim in (data_q, method_q, robustness_q):
            caveats.extend(dim.warnings)

        return CausalQualityReport(
            run_id=run_id,
            query_str=query_str,
            data_quality=data_q,
            method_quality=method_q,
            robustness=robustness_q,
            composite_score=round(composite, 4),
            composite_grade=grade,
            is_publication_ready=pub_ready,
            caveats=tuple(caveats),
            weights=dict(w),
            created_at=datetime.now(UTC).isoformat(),
        )

    # ------------------------------------------------------------------
    # Convenience: compute all + aggregate in one call
    # ------------------------------------------------------------------

    def score(
        self,
        *,
        run_id: str,
        query_str: str = "",
        data_provenance: tuple[DataProvenance, ...] = (),
        estimation_steps: tuple[EstimationStep, ...] = (),
        node_outputs: dict[str, Any] | None = None,
    ) -> CausalQualityReport:
        """Compute all quality dimensions and return an aggregated CausalQualityReport."""
        data_q = self.compute_data_quality(data_provenance, node_outputs=node_outputs)
        method_q = self.compute_method_quality(estimation_steps)
        robustness_q = self.compute_robustness(node_outputs=node_outputs)
        return self.aggregate(data_q, method_q, robustness_q, run_id=run_id, query_str=query_str)


__all__ = ["QualityScoreAggregator"]
