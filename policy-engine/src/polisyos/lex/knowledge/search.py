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

from typing import TYPE_CHECKING

from polisyos.common.logger import get_logger
from polisyos.lex.knowledge.store import (
    LegalKnowledgeStore,
    LegalQueryInput,
    LegalQueryProfileError,
)
from polisyos.lex.knowledge.types import (
    LegalDocVersionResult,
    LegalFactResult,
    LegalProvisionResult,
    LegalReferenceEdgeResult,
    LegalSearchResult,
    LegalSourceAnchor,
    LegalSourceBundle,
)

if TYPE_CHECKING:
    from pathlib import Path

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
        query_encoder: object | None = None,
    ) -> None:
        """Open a read-only graph with an optional content-bound local query encoder.

        Args:
            db_path: Legal knowledge DuckDB path.
            index_dir: Directory containing selected Legal embedding generations.
            openai_api_key: Deprecated compatibility argument; it does not authorize vectors.
            embedding_model: Deprecated label retained for constructor compatibility.
            query_encoder: Live local encoder whose weights and tokenizer must match each
                selected generation before vector search is allowed.
        """
        self._store = LegalKnowledgeStore(db_path, index_dir)
        self._embedding_model = embedding_model
        self._query_encoder = query_encoder
        self._query_profile_error = (
            None
            if query_encoder is not None
            else LegalQueryProfileError("query_encoder_assets_unavailable")
        )
        if openai_api_key is not None and query_encoder is None:
            logger.warning(
                "legal_query_profile_unsupported: OpenAI query embeddings lack inspectable local "
                "encoder assets; vector search will use text fallback"
            )

    @property
    def query_profile_error(self) -> LegalQueryProfileError | None:
        """Return the typed reason vector search is unsupported, if one is known."""
        return self._query_profile_error

    # ------------------------------------------------------------------
    # Embedding helper
    # ------------------------------------------------------------------

    def _get_query_input(self, query: str) -> LegalQueryInput | None:
        """Bind query text to the configured live local encoder, without a caller vector."""
        if self._query_encoder is None:
            self._query_profile_error = LegalQueryProfileError("query_encoder_assets_unavailable")
            return None
        self._query_profile_error = None
        return LegalQueryInput(text=query, encoder=self._query_encoder)

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
        query_input = self._get_query_input(query)
        if query_input is None:
            return []
        try:
            return self._store.search_entities_by_vector(
                query_input,
                top_k=top_k,
                min_similarity=min_similarity,
            )
        except LegalQueryProfileError as exc:
            self._query_profile_error = exc
            raise

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
        min_fused_confidence: float | None = None,
        quality_band: str | None = None,
    ) -> list[LegalFactResult]:
        """Vector similarity search on facts."""
        query_input = self._get_query_input(query)
        if query_input is None:
            return []
        try:
            return self._store.search_facts_by_vector(
                query_input,
                top_k=top_k,
                min_similarity=min_similarity,
                trust_tier=trust_tier,
                jurisdiction=jurisdiction,
                domain=domain,
                as_of=as_of,
                legal_unit_subtype=legal_unit_subtype,
                route_class=route_class,
                include_candidates=include_candidates,
                min_fused_confidence=min_fused_confidence,
                quality_band=quality_band,
            )
        except LegalQueryProfileError as exc:
            self._query_profile_error = exc
            raise

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
        query_input = self._get_query_input(query)
        if query_input is None:
            return []
        try:
            return self._store.search_provisions_by_vector(
                query_input,
                top_k=top_k,
                min_similarity=min_similarity,
                legal_unit_subtype=legal_unit_subtype,
                route_class=route_class,
            )
        except LegalQueryProfileError as exc:
            self._query_profile_error = exc
            raise

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
        min_fused_confidence: float | None = None,
        quality_band: str | None = None,
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
            min_fused_confidence=min_fused_confidence,
            quality_band=quality_band,
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
        min_fused_confidence: float | None = None,
        quality_band: str | None = None,
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
            min_fused_confidence=min_fused_confidence,
            quality_band=quality_band,
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
        min_fused_confidence: float | None = None,
        quality_band: str | None = None,
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
            min_fused_confidence=min_fused_confidence,
            quality_band=quality_band,
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
        min_fused_confidence: float | None = None,
        quality_band: str | None = None,
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
            min_fused_confidence=min_fused_confidence,
            quality_band=quality_band,
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
        min_fused_confidence: float | None = None,
        quality_band: str | None = None,
    ) -> list[LegalFactResult]:
        """Retrieve high-trust norms filtered by domain/jurisdiction/time."""
        return self._store.get_applicable_norms(
            domain=domain,
            jurisdiction=jurisdiction,
            as_of=as_of,
            top_k=top_k,
            legal_unit_subtype=legal_unit_subtype,
            route_class=route_class,
            min_fused_confidence=min_fused_confidence,
            quality_band=quality_band,
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
        min_fused_confidence: float | None = None,
        quality_band: str | None = None,
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
            min_fused_confidence=min_fused_confidence,
            quality_band=quality_band,
        )

        query_input = self._get_query_input(query)
        if query_input is None:
            # No embeddings available — return text results only
            return text_results[:top_k]

        try:
            vector_results = self._store.search_facts_by_vector(
                query_input,
                top_k=top_k * 2,
                min_similarity=0.2,
                trust_tier=trust_tier,
                jurisdiction=jurisdiction,
                domain=domain,
                as_of=as_of,
                legal_unit_subtype=legal_unit_subtype,
                route_class=route_class,
                include_candidates=include_candidates,
                min_fused_confidence=min_fused_confidence,
                quality_band=quality_band,
            )
        except LegalQueryProfileError as exc:
            self._query_profile_error = exc
            logger.warning("Legal vector profile unsupported; using text results: {}", exc.code)
            return text_results[:top_k]

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
                legal_unit_subtype=fact_map[fid].legal_unit_subtype,
                route_class=fact_map[fid].route_class,
                empty_spo_retry_eligible=fact_map[fid].empty_spo_retry_eligible,
                audit_miss_prone=fact_map[fid].audit_miss_prone,
                reference_bearing=fact_map[fid].reference_bearing,
                threshold_bearing=fact_map[fid].threshold_bearing,
                fused_confidence=fact_map[fid].fused_confidence,
                confidence_breakdown_json=fact_map[fid].confidence_breakdown_json,
                consistency_score=fact_map[fid].consistency_score,
                hallucination_flags_json=fact_map[fid].hallucination_flags_json,
                quality_band=fact_map[fid].quality_band,
                doc_id=fact_map[fid].doc_id,
                doc_family_id=fact_map[fid].doc_family_id,
                version_id=fact_map[fid].version_id,
                jurisdiction=fact_map[fid].jurisdiction,
                top_domain=fact_map[fid].top_domain,
                effective_from=fact_map[fid].effective_from,
                effective_to=fact_map[fid].effective_to,
                temporal_state=fact_map[fid].temporal_state,
                temporal_resolution_status=fact_map[fid].temporal_resolution_status,
                temporal_source_scope=fact_map[fid].temporal_source_scope,
                temporal_source_kind=fact_map[fid].temporal_source_kind,
                temporal_confidence=fact_map[fid].temporal_confidence,
                temporal_provenance_json=fact_map[fid].temporal_provenance_json,
                doc_name=fact_map[fid].doc_name,
                doc_reestr_code=fact_map[fid].doc_reestr_code,
                provision_anchor=fact_map[fid].provision_anchor,
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

    def load_provisions_by_anchor(
        self,
        doc_id: str,
        anchors: list[str],
    ) -> list[LegalSourceAnchor]:
        return self._store.load_provisions_by_anchor(doc_id, anchors)

    def load_doc_version_chain(
        self,
        *,
        doc_id: str | None = None,
        doc_family_id: str | None = None,
    ) -> list[LegalDocVersionResult]:
        return self._store.load_doc_version_chain(doc_id=doc_id, doc_family_id=doc_family_id)

    def load_appendix_context(
        self,
        doc_id: str,
        anchor: str,
        *,
        max_depth: int = 4,
    ) -> list[str]:
        return self._store.load_appendix_context(doc_id, anchor, max_depth=max_depth)

    def expand_reference_neighborhood(
        self,
        *,
        doc_id: str,
        anchors: list[str],
        max_hops: int = 2,
    ) -> list[LegalReferenceEdgeResult]:
        return self._store.expand_reference_neighborhood(
            doc_id=doc_id,
            anchors=anchors,
            max_hops=max_hops,
        )

    def load_source_bundle(
        self,
        *,
        doc_id: str,
        anchors: list[str],
        version_id: str | None = None,
        max_reference_hops: int = 2,
        candidate_fact_ids: list[str] | None = None,
        candidate_provision_ids: list[str] | None = None,
    ) -> LegalSourceBundle | None:
        return self._store.load_source_bundle(
            doc_id=doc_id,
            anchors=anchors,
            version_id=version_id,
            max_reference_hops=max_reference_hops,
            candidate_fact_ids=candidate_fact_ids,
            candidate_provision_ids=candidate_provision_ids,
        )

    def get_versioned_source_refs(
        self,
        *,
        doc_id: str | None = None,
        doc_family_id: str | None = None,
    ) -> list[LegalDocVersionResult]:
        return self.load_doc_version_chain(doc_id=doc_id, doc_family_id=doc_family_id)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        self._store.close()
