"""High-level hybrid search API for the academic knowledge graph."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from polisyos.common.logger import get_logger
from polisyos.data_forge.domains.academic.knowledge.skg_query import SKGQuery
from polisyos.data_forge.domains.academic.knowledge.skg_store import EVIDENCE_WEIGHTS
from polisyos.data_forge.domains.academic.knowledge.store import ScholarKnowledgeStore
from polisyos.data_forge.domains.academic.knowledge.types import (
    BoundaryConditionResult,
    CausalClaimResult,
    ParameterPrior,
    WorkSearchResult,
)

logger = get_logger(__name__)


class ScholarKnowledgeGraph:
    """Read-only access to the academic knowledge graph with hybrid search."""

    def __init__(
        self,
        db_path: Path,
        index_dir: Path,
        *,
        embedding_model: str | None = None,
    ) -> None:
        self._db_path = Path(db_path)
        self._index_dir = Path(index_dir)
        self._store = ScholarKnowledgeStore(db_path, index_dir)
        self._embedding_model_name = embedding_model or self._discover_embedding_model()
        self._embedder = None

    def _discover_embedding_model(self) -> str:
        for manifest_path in (
            self._index_dir / "manifests" / "embed.json",
            self._index_dir.parent / "manifests" / "embed.json",
        ):
            if not manifest_path.exists():
                continue
            try:
                payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            metrics = payload.get("metrics")
            if not isinstance(metrics, dict):
                continue
            embedding_model = str(metrics.get("embedding_model") or "").strip()
            if embedding_model:
                return embedding_model
        return ""

    def _get_query_embedding(self, query: str) -> np.ndarray | None:
        try:
            if not self._embedding_model_name:
                return None
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

    def find_relevant_works(
        self,
        query: str,
        *,
        domain: str | None = None,
        top_k: int = 20,
        vector_weight: float = 0.7,
        text_weight: float = 0.3,
    ) -> list[WorkSearchResult]:
        del domain
        text_results = self._store.text_search_works(query, top_k=top_k * 2)

        vec = self._get_query_embedding(query)
        if vec is None:
            return text_results[:top_k]

        try:
            vector_results = self._store.search_works_by_vector(
                vec,
                top_k=top_k * 2,
                min_similarity=0.2,
            )
        except Exception as exc:
            logger.warning(
                "Vector work search failed; falling back to text-only retrieval: %s", exc
            )
            return text_results[:top_k]

        scores: dict[str, float] = {}
        result_map: dict[str, WorkSearchResult] = {}

        for result in vector_results:
            scores[result.id] = scores.get(result.id, 0.0) + result.similarity * vector_weight
            result_map[result.id] = result

        for result in text_results:
            scores[result.id] = scores.get(result.id, 0.0) + text_weight
            if result.id not in result_map:
                result_map[result.id] = result

        ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
        results: list[WorkSearchResult] = []
        for work_id, score in ranked:
            if work_id not in result_map:
                continue
            base = result_map[work_id]
            results.append(WorkSearchResult(**{**base.model_dump(), "similarity": score}))
            if len(results) >= top_k:
                break
        return results

    def get_parameter_prior(
        self,
        variable: str,
        domain: str | None = None,
        country: str | None = None,
        *,
        prefer_simulation_ready: bool = True,
    ) -> ParameterPrior | None:
        if prefer_simulation_ready:
            query = SKGQuery(db_path=self._db_path, index_dir=self._index_dir)
            try:
                candidates = query.query_parameters(
                    variable,
                    layer="auto",
                    require_simulation_ready=True,
                )
            finally:
                query.close()
            if candidates:
                usable_candidates = [
                    candidate for candidate in candidates if candidate.parameter.value is not None
                ]
                values = np.array(
                    [float(candidate.parameter.value) for candidate in usable_candidates]
                )
                if len(values) > 0:
                    weights = np.array(
                        [
                            EVIDENCE_WEIGHTS.get(
                                candidate.parameter.evidence_strength.value,
                                EVIDENCE_WEIGHTS["unknown"],
                            )
                            for candidate in usable_candidates
                        ]
                    )
                    if weights.sum() == 0:
                        weights = np.ones_like(weights)
                    weights = weights / weights.sum()
                    weighted_mean = float(np.average(values, weights=weights))
                    weighted_std = float(
                        np.sqrt(np.average((values - weighted_mean) ** 2, weights=weights))
                    )
                    weighted_std = max(weighted_std, 0.01)
                    return ParameterPrior(
                        variable=variable,
                        prior_mean=weighted_mean,
                        prior_std=weighted_std,
                        prior_low=float(np.percentile(values, 10)),
                        prior_high=float(np.percentile(values, 90)),
                        n_studies=len(usable_candidates),
                        best_design=str(usable_candidates[0].parameter.evidence_strength.value),
                        as_calibration_prior={
                            "distribution": "normal",
                            "mean": weighted_mean,
                            "std": weighted_std,
                        },
                    )

        estimates = self._store.get_parameter_estimates(variable, domain, country)
        if not estimates:
            return None

        values = np.array([estimate.estimate for estimate in estimates])
        weights = np.array([estimate.trust_score for estimate in estimates])
        if weights.sum() == 0:
            weights = np.ones_like(weights)
        weights = weights / weights.sum()

        weighted_mean = float(np.average(values, weights=weights))
        weighted_std = float(np.sqrt(np.average((values - weighted_mean) ** 2, weights=weights)))
        weighted_std = max(weighted_std, 0.01)
        best_design = ""
        if estimates:
            sorted_by_trust = sorted(
                estimates, key=lambda estimate: estimate.trust_score, reverse=True
            )
            best_design = sorted_by_trust[0].study_design

        return ParameterPrior(
            variable=variable,
            prior_mean=weighted_mean,
            prior_std=weighted_std,
            prior_low=float(np.percentile(values, 10)),
            prior_high=float(np.percentile(values, 90)),
            n_studies=len(estimates),
            best_design=best_design,
            as_calibration_prior={
                "distribution": "normal",
                "mean": weighted_mean,
                "std": weighted_std,
            },
        )

    def find_causal_evidence(
        self,
        cause: str,
        effect: str,
        *,
        min_trust: float = 0.5,
        support_mode: str = "exact",
    ) -> list[CausalClaimResult]:
        if str(support_mode or "exact").strip().lower() == "exact":
            return self._store.get_causal_claims(cause, effect, min_trust=min_trust)
        query = SKGQuery(db_path=self._db_path, index_dir=self._index_dir)
        try:
            return query.query_claims(
                cause=cause,
                effect=effect,
                min_trust=min_trust,
                support_mode=support_mode,
            )
        finally:
            query.close()

    def get_mechanism_evidence(
        self,
        mechanism_name: str,
        *,
        top_k: int = 20,
        min_trust: float = 0.3,
    ) -> list[CausalClaimResult]:
        return self._store.search_causal_claims(
            mechanism_name,
            top_k=top_k,
            min_trust=min_trust,
        )

    def find_works_for_topic(
        self,
        topic_id: str,
        *,
        run_id: str | None = None,
        pass_name: str | None = None,
        top_k: int = 20,
    ) -> list[WorkSearchResult]:
        return self._store.search_works_by_topic(
            topic_id,
            run_id=run_id,
            pass_name=pass_name,
            top_k=top_k,
        )

    def get_boundary_conditions_for_work(self, work_id: str) -> list[BoundaryConditionResult]:
        return self._store.get_boundary_conditions_for_work(work_id)

    def close(self) -> None:
        self._store.close()
