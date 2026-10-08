"""Unapplied A/G call excerpt using existing Legal owner types and consumer.

This function accepts an independently saved request snapshot. It never reads a
current generation selector to manufacture the expected request intent. The
nine executed generic cases call the same Graph constructor/search_facts path
with min_similarity=0.0/include_candidates=True; current served text-search
filters use trust_tier=None/include_candidates=False.

Imports name the existing defining modules because current G has no typed
profile export. The companion extends the existing declared knowledge facade;
this file creates no DTO, new producer, HTTP schema or response status.
"""

from pathlib import Path

from polisyos.lex.knowledge.search import LegalKnowledgeGraph
from polisyos.lex.knowledge.store import LegalQueryProfile, LegalQueryProfileError
from polisyos.lex.knowledge.types import LegalFactResult


def consume_saved_fact_request(
    *,
    db_path: Path,
    index_dir: Path,
    query: str,
    top_k: int,
    request_intent: tuple[LegalQueryProfile, ...],
    query_encoder: object,
    min_similarity: float = 0.3,
    include_candidates: bool = False,
) -> list[LegalFactResult]:
    """Read typed facts or preserve the actual owner refusal for A/G to serve."""
    graph = LegalKnowledgeGraph(
        db_path,
        index_dir,
        query_encoder=query_encoder,
        query_profile=request_intent,
    )
    try:
        results = graph.search_facts(
            query,
            top_k=top_k,
            min_similarity=min_similarity,
            trust_tier=None,
            include_candidates=include_candidates,
        )
        if graph.query_profile_error is not None:
            raise LegalQueryProfileError(graph.query_profile_error.code)
        return results
    finally:
        graph.close()
