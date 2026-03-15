"""High-level hybrid search API for the legal knowledge graph.

Combines vector similarity search with text matching and optional
graph traversal. This is the main entry point for the rest of the system.

Usage::

from polisyos.common.logger import get_logger
    from polisyos.lex.knowledge.search import LegalKnowledgeGraph

    kg = LegalKnowledgeGraph(
        db_path=Path("data/lex_knowledge/lex_knowledge_graph.duckdb"),
        index_dir=Path("data/lex_knowledge"),
    )
    results = kg.hybrid_search("бюджетний дефіцит", top_k=20)
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from polisyos.common.logger import get_logger
from polisyos.lex.knowledge.store import LegalKnowledgeStore
from polisyos.lex.knowledge.types import (
    LegalFactResult,
    LegalProvisionResult,
    LegalSearchResult,
)

logger = get_logger(__name__)


class LegalKnowledgeGraph:
    """Read-only access to the legal knowledge graph with hybrid search."""

    def __init__(
        self,
        db_path: Path,
        index_dir: Path,
        *,
        openai_api_key: str | None = None,
        embedding_model: str = "text-embedding-3-large",
    ) -> None:
        self._store = LegalKnowledgeStore(db_path, index_dir)
        self._openai_api_key = openai_api_key
        self._embedding_model = embedding_model
        self._embedding_client = None
        self._embedding_dim: int | None = None

    # ------------------------------------------------------------------
    # Embedding helper
    # ------------------------------------------------------------------

    def _get_query_embedding(self, query: str) -> np.ndarray | None:
        """Embed a query string using OpenAI API (sync)."""
        if not self._openai_api_key:
            return None

        try:
            import openai

            if self._embedding_client is None:
                self._embedding_client = openai.OpenAI(api_key=self._openai_api_key)

            resp = self._embedding_client.embeddings.create(
                model=self._embedding_model,
                input=[query],
            )
            vec = np.array(resp.data[0].embedding, dtype=np.float32)
            # L2 normalize
            norm = np.linalg.norm(vec)
            if norm > 0:
                vec = vec / norm
            return vec
        except Exception as exc:
            logger.warning("Failed to embed query: %s", exc)
            return None

    # ------------------------------------------------------------------
    # Search methods
    # ------------------------------------------------------------------

    def search_entities(
        self,
        query: str,
        *,
        top_k: int = 10,
        min_similarity: float = 0.3,
    ) -> list[LegalSearchResult]:
        """Vector similarity search on entities."""
        vec = self._get_query_embedding(query)
        if vec is None:
            return []
        return self._store.search_entities_by_vector(
            vec, top_k=top_k, min_similarity=min_similarity,
        )

    def search_facts(
        self,
        query: str,
        *,
        top_k: int = 20,
        min_similarity: float = 0.3,
        trust_tier: str | None = "grounded_fact",
        jurisdiction: str | None = None,
        domain: str | None = None,
        as_of: str | None = None,
        legal_unit_subtype: str | None = None,
        route_class: str | None = None,
        include_candidates: bool = False,
    ) -> list[LegalFactResult]:
        """Vector similarity search on facts."""
        vec = self._get_query_embedding(query)
        if vec is None:
            return []
        return self._store.search_facts_by_vector(
            vec,
            top_k=top_k,
            min_similarity=min_similarity,
            trust_tier=trust_tier,
            jurisdiction=jurisdiction,
            domain=domain,
            as_of=as_of,
            legal_unit_subtype=legal_unit_subtype,
            route_class=route_class,
            include_candidates=include_candidates,
        )

    def search_provisions(
        self,
        query: str,
        *,
        top_k: int = 10,
        min_similarity: float = 0.3,
        legal_unit_subtype: str | None = None,
        route_class: str | None = None,
    ) -> list[LegalProvisionResult]:
        """Vector similarity search on provisions."""
        vec = self._get_query_embedding(query)
        if vec is None:
            return []
        return self._store.search_provisions_by_vector(
            vec,
            top_k=top_k,
            min_similarity=min_similarity,
            legal_unit_subtype=legal_unit_subtype,
            route_class=route_class,
        )

    def text_search(
        self,
        query: str,
        *,
        top_k: int = 20,
        trust_tier: str | None = "grounded_fact",
        jurisdiction: str | None = None,
        domain: str | None = None,
        as_of: str | None = None,
        legal_unit_subtype: str | None = None,
        route_class: str | None = None,
        include_candidates: bool = False,
    ) -> list[LegalFactResult]:
        """Full-text search on fact_text using DuckDB ILIKE."""
        return self._store.text_search_facts(
            query,
            top_k=top_k,
            trust_tier=trust_tier,
            jurisdiction=jurisdiction,
            domain=domain,
            as_of=as_of,
            legal_unit_subtype=legal_unit_subtype,
            route_class=route_class,
            include_candidates=include_candidates,
        )

    def search_facts_by_action(
        self,
        action_canon: str,
        *,
        top_k: int = 50,
        trust_tier: str | None = "normative_fact",
        jurisdiction: str | None = None,
        domain: str | None = None,
        as_of: str | None = None,
        legal_unit_subtype: str | None = None,
        route_class: str | None = None,
        include_candidates: bool = False,
    ) -> list[LegalFactResult]:
        """Structured retrieval by canonical action."""
        return self._store.search_facts_by_action(
            action_canon,
            top_k=top_k,
            trust_tier=trust_tier,
            jurisdiction=jurisdiction,
            domain=domain,
            as_of=as_of,
            legal_unit_subtype=legal_unit_subtype,
            route_class=route_class,
            include_candidates=include_candidates,
        )

    def search_facts_with_threshold(
        self,
        metric: str,
        *,
        top_k: int = 50,
        trust_tier: str | None = "normative_fact",
        jurisdiction: str | None = None,
        domain: str | None = None,
        as_of: str | None = None,
        legal_unit_subtype: str | None = None,
        route_class: str | None = None,
        include_candidates: bool = False,
    ) -> list[LegalFactResult]:
        """Structured retrieval by threshold metric."""
        return self._store.search_facts_with_threshold(
            metric,
            top_k=top_k,
            trust_tier=trust_tier,
            jurisdiction=jurisdiction,
            domain=domain,
            as_of=as_of,
            legal_unit_subtype=legal_unit_subtype,
            route_class=route_class,
            include_candidates=include_candidates,
        )

    def find_legal_constraints(
        self,
        *,
        query: str | None = None,
        top_k: int = 50,
        jurisdiction: str | None = None,
        domain: str | None = None,
        as_of: str | None = None,
        legal_unit_subtype: str | None = None,
        route_class: str | None = None,
    ) -> list[LegalFactResult]:
        """Retrieve high-trust legal constraints for governance and foundry."""
        return self._store.find_constraints(
            query=query,
            top_k=top_k,
            jurisdiction=jurisdiction,
            domain=domain,
            as_of=as_of,
            legal_unit_subtype=legal_unit_subtype,
            route_class=route_class,
        )

    def get_applicable_norms(
        self,
        *,
        domain: str | None = None,
        jurisdiction: str | None = None,
        as_of: str | None = None,
        top_k: int = 100,
        legal_unit_subtype: str | None = None,
        route_class: str | None = None,
    ) -> list[LegalFactResult]:
        """Retrieve high-trust norms filtered by domain/jurisdiction/time."""
        return self._store.get_applicable_norms(
            domain=domain,
            jurisdiction=jurisdiction,
            as_of=as_of,
            top_k=top_k,
            legal_unit_subtype=legal_unit_subtype,
            route_class=route_class,
        )

    def hybrid_search(
        self,
        query: str,
        *,
        top_k: int = 20,
        vector_weight: float = 0.7,
        text_weight: float = 0.3,
        trust_tier: str | None = "grounded_fact",
        jurisdiction: str | None = None,
        domain: str | None = None,
        as_of: str | None = None,
        legal_unit_subtype: str | None = None,
        route_class: str | None = None,
        include_candidates: bool = False,
    ) -> list[LegalFactResult]:
        """Combined vector + text search with score fusion.

        If no OpenAI API key is configured, falls back to text-only search.
        """
        text_results = self._store.text_search_facts(
            query,
            top_k=top_k * 2,
            trust_tier=trust_tier,
            jurisdiction=jurisdiction,
            domain=domain,
            as_of=as_of,
            legal_unit_subtype=legal_unit_subtype,
            route_class=route_class,
            include_candidates=include_candidates,
        )

        vec = self._get_query_embedding(query)
        if vec is None:
            # No embeddings available — return text results only
            return text_results[:top_k]

        vector_results = self._store.search_facts_by_vector(
            vec,
            top_k=top_k * 2,
            min_similarity=0.2,
            trust_tier=trust_tier,
            jurisdiction=jurisdiction,
            domain=domain,
            as_of=as_of,
            legal_unit_subtype=legal_unit_subtype,
            route_class=route_class,
            include_candidates=include_candidates,
        )

        # Score fusion: merge by fact_id
        scores: dict[str, float] = {}
        fact_map: dict[str, LegalFactResult] = {}

        for r in vector_results:
            scores[r.fact_id] = scores.get(r.fact_id, 0.0) + r.similarity * vector_weight
            fact_map[r.fact_id] = r

        for r in text_results:
            scores[r.fact_id] = scores.get(r.fact_id, 0.0) + text_weight
            if r.fact_id not in fact_map:
                fact_map[r.fact_id] = r

        # Sort by fused score
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]

        return [
            LegalFactResult(
                fact_id=fid,
                subject_name=fact_map[fid].subject_name,
                predicate=fact_map[fid].predicate,
                object_name=fact_map[fid].object_name,
                fact_text=fact_map[fid].fact_text,
                confidence=fact_map[fid].confidence,
                norm_type=fact_map[fid].norm_type,
                action_canon=fact_map[fid].action_canon,
                norm_type_canon=fact_map[fid].norm_type_canon,
                condition_text_uk=fact_map[fid].condition_text_uk,
                exception_text_uk=fact_map[fid].exception_text_uk,
                procedure_text_uk=fact_map[fid].procedure_text_uk,
                thresholds_json=fact_map[fid].thresholds_json,
                source_quote_uk=fact_map[fid].source_quote_uk,
                trust_tier=fact_map[fid].trust_tier,
                grounding_status=fact_map[fid].grounding_status,
                canonical_status=fact_map[fid].canonical_status,
                reference_resolution_status=fact_map[fid].reference_resolution_status,
                structure_quality=fact_map[fid].structure_quality,
                constraint_type_canon=fact_map[fid].constraint_type_canon,
                jurisdiction=fact_map[fid].jurisdiction,
                top_domain=fact_map[fid].top_domain,
                effective_from=fact_map[fid].effective_from,
                effective_to=fact_map[fid].effective_to,
                doc_name=fact_map[fid].doc_name,
                doc_reestr_code=fact_map[fid].doc_reestr_code,
                provision_citation=fact_map[fid].provision_citation,
                similarity=score,
            )
            for fid, score in ranked
            if fid in fact_map
        ]

    # ------------------------------------------------------------------
    # Graph methods (delegated)
    # ------------------------------------------------------------------

    def get_norms_for_entity(
        self,
        entity_id: str,
        *,
        trust_tier: str | None = "grounded_fact",
        jurisdiction: str | None = None,
        domain: str | None = None,
        as_of: str | None = None,
        include_candidates: bool = False,
    ) -> list[LegalFactResult]:
        """All facts where entity is subject or object."""
        return self._store.get_facts_for_entity(
            entity_id,
            trust_tier=trust_tier,
            jurisdiction=jurisdiction,
            domain=domain,
            as_of=as_of,
            include_candidates=include_candidates,
        )

    def find_related_entities(
        self,
        entity_id: str,
        *,
        max_hops: int = 2,
        max_results: int = 50,
        trust_tier: str | None = "grounded_fact",
        include_candidates: bool = False,
    ) -> list[tuple[LegalSearchResult, str, int]]:
        """Graph traversal: find entities connected via facts."""
        return self._store.find_related_entities(
            entity_id,
            max_hops=max_hops,
            max_results=max_results,
            trust_tier=trust_tier,
            include_candidates=include_candidates,
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        self._store.close()
