"""Topic/run-aware SKG query helpers for SCM stages."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from polisyos.academic.knowledge.store import ScholarKnowledgeStore
from polisyos.academic.knowledge.types import BoundaryConditionResult, CausalClaimResult, ParameterEstimateResult, ParameterPrior


@dataclass(frozen=True)
class LiteraturePriorResult:
    variable: str
    prior: ParameterPrior | None
    estimates: list[ParameterEstimateResult]


class SKGQuery:
    """Read-only query API for SKG tables in academic DuckDB."""

    def __init__(self, db_path: Path, index_dir: Path) -> None:
        self._store = ScholarKnowledgeStore(db_path, index_dir)

    def query_prior(
        self,
        *,
        variable: str,
        domain: str | None = None,
        country: str | None = None,
    ) -> LiteraturePriorResult:
        estimates = self._store.get_parameter_estimates(variable, domain=domain, country=country)
        if not estimates:
            return LiteraturePriorResult(variable=variable, prior=None, estimates=[])

        values = np.array([e.estimate for e in estimates])
        weights = np.array([max(0.01, e.trust_score) for e in estimates])
        weights = weights / weights.sum()

        weighted_mean = float(np.average(values, weights=weights))
        weighted_std = float(np.sqrt(np.average((values - weighted_mean) ** 2, weights=weights)))
        weighted_std = max(weighted_std, 0.01)
        prior_low = float(np.percentile(values, 10))
        prior_high = float(np.percentile(values, 90))

        best_design = sorted(estimates, key=lambda e: e.trust_score, reverse=True)[0].study_design if estimates else ""
        prior = ParameterPrior(
            variable=variable,
            prior_mean=weighted_mean,
            prior_std=weighted_std,
            prior_low=prior_low,
            prior_high=prior_high,
            n_studies=len(estimates),
            best_design=best_design,
            as_calibration_prior={
                "distribution": "normal",
                "mean": weighted_mean,
                "std": weighted_std,
            },
        )
        return LiteraturePriorResult(variable=variable, prior=prior, estimates=estimates)

    def query_claims(
        self,
        *,
        cause: str,
        effect: str,
        min_trust: float = 0.5,
    ) -> list[CausalClaimResult]:
        return self._store.get_causal_claims(cause, effect, min_trust=min_trust)

    def query_boundary_conditions(self, *, work_id: str) -> list[BoundaryConditionResult]:
        return self._store.get_boundary_conditions_for_work(work_id)

    def close(self) -> None:
        self._store.close()


__all__ = ["SKGQuery", "LiteraturePriorResult"]
