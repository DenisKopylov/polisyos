"""High-level hybrid search API for the academic knowledge graph.

Provides parameter priors from literature, causal evidence search,
and work discovery with pre-extracted estimates.

Usage::

    from polisyos.academic.knowledge.search import ScholarKnowledgeGraph

    graph = ScholarKnowledgeGraph(
        db_path=Path("data/scholar_knowledge/scholar_knowledge.duckdb"),
        index_dir=Path("data/scholar_knowledge"),
    )
    prior = graph.get_parameter_prior("min_wage_employment_elasticity", domain="labor")
    evidence = graph.find_causal_evidence("minimum wage", "employment")
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np

from polisyos.academic.knowledge.store import ScholarKnowledgeStore
from polisyos.academic.knowledge.types import (
    BoundaryConditionResult,
    CausalClaimResult,
    ParameterPrior,
    WorkSearchResult,
)

logger = logging.getLogger(__name__)


class ScholarKnowledgeGraph:
    """Read-only access to the academic knowledge graph with hybrid search."""

    def __init__(
        self,
        db_path: Path,
        index_dir: Path,
        *,
        embedding_model: str = "intfloat/multilingual-e5-large",
    ) -> None:
        self._store = ScholarKnowledgeStore(db_path, index_dir)
        self._embedding_model_name = embedding_model
        self._embedder = None

    # ------------------------------------------------------------------
    # Embedding helper (local sentence-transformers)
    # ------------------------------------------------------------------

    def _get_query_embedding(self, query: str) -> np.ndarray | None:
        try:
            if self._embedder is None:
                from sentence_transformers import SentenceTransformer

                self._embedder = SentenceTransformer(self._embedding_model_name)
            vec = self._embedder.encode([query])[0].astype(np.float32)
            norm = np.linalg.norm(vec)
            if norm > 0:
                vec = vec / norm
            return vec
        except Exception as exc:
            logger.warning("Failed to embed query: %s", exc)
            return None

    # ------------------------------------------------------------------
    # Work search
    # ------------------------------------------------------------------

    def find_relevant_works(
        self,
        query: str,
        *,
        domain: str | None = None,
        top_k: int = 20,
        vector_weight: float = 0.7,
        text_weight: float = 0.3,
    ) -> list[WorkSearchResult]:
        """Hybrid vector + text search for academic works."""
        text_results = self._store.text_search_works(query, top_k=top_k * 2)

        vec = self._get_query_embedding(query)
        if vec is None:
            return text_results[:top_k]

        vector_results = self._store.search_works_by_vector(
            vec, top_k=top_k * 2, min_similarity=0.2,
        )

        # Score fusion
        scores: dict[str, float] = {}
        result_map: dict[str, WorkSearchResult] = {}

        for r in vector_results:
            scores[r.id] = scores.get(r.id, 0.0) + r.similarity * vector_weight
            result_map[r.id] = r

        for r in text_results:
            scores[r.id] = scores.get(r.id, 0.0) + text_weight
            if r.id not in result_map:
                result_map[r.id] = r

        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        results: list[WorkSearchResult] = []
        for wid, score in ranked:
            if wid not in result_map:
                continue
            r = result_map[wid]
            results.append(WorkSearchResult(
                **{**r.model_dump(), "similarity": score},
            ))
            if len(results) >= top_k:
                break
        return results

    # ------------------------------------------------------------------
    # Parameter priors
    # ------------------------------------------------------------------

    def get_parameter_prior(
        self,
        variable: str,
        domain: str | None = None,
        country: str | None = None,
    ) -> ParameterPrior | None:
        """Aggregate parameter estimates from literature into a prior distribution.

        Returns a ParameterPrior with prior_mean/prior_std compatible with
        foundry/calibration/ TrainableHandle.
        """
        estimates = self._store.get_parameter_estimates(variable, domain, country)
        if not estimates:
            return None

        values = np.array([e.estimate for e in estimates])
        weights = np.array([e.trust_score for e in estimates])

        # Avoid zero weights
        if weights.sum() == 0:
            weights = np.ones_like(weights)
        weights = weights / weights.sum()

        weighted_mean = float(np.average(values, weights=weights))
        weighted_std = float(np.sqrt(np.average((values - weighted_mean) ** 2, weights=weights)))
        weighted_std = max(weighted_std, 0.01)  # floor to avoid degenerate prior

        prior_low = float(np.percentile(values, 10))
        prior_high = float(np.percentile(values, 90))

        # Best study design among top estimates
        best_design = ""
        if estimates:
            sorted_by_trust = sorted(estimates, key=lambda e: e.trust_score, reverse=True)
            best_design = sorted_by_trust[0].study_design

        return ParameterPrior(
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

    # ------------------------------------------------------------------
    # Causal evidence
    # ------------------------------------------------------------------

    def find_causal_evidence(
        self,
        cause: str,
        effect: str,
        *,
        min_trust: float = 0.5,
    ) -> list[CausalClaimResult]:
        """Find causal claims: is there evidence that cause → effect?"""
        return self._store.get_causal_claims(cause, effect, min_trust=min_trust)

    def get_mechanism_evidence(
        self,
        mechanism_name: str,
        *,
        top_k: int = 20,
        min_trust: float = 0.3,
    ) -> list[CausalClaimResult]:
        """Find evidence for a specific causal mechanism."""
        return self._store.search_causal_claims(
            mechanism_name, top_k=top_k, min_trust=min_trust,
        )

    def find_works_for_topic(
        self,
        topic_id: str,
        *,
        run_id: str | None = None,
        pass_name: str | None = None,
        top_k: int = 20,
    ) -> list[WorkSearchResult]:
        """Topic-aware lookup for selected works in a specific run/pass."""
        return self._store.search_works_by_topic(
            topic_id,
            run_id=run_id,
            pass_name=pass_name,
            top_k=top_k,
        )

    def get_boundary_conditions_for_work(self, work_id: str) -> list[BoundaryConditionResult]:
        """Load extracted boundary conditions for a work id."""
        return self._store.get_boundary_conditions_for_work(work_id)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        self._store.close()
