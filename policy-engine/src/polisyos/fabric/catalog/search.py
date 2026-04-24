"""
Metric search engine with explainable semantic fallback.

Resolves fuzzy user queries into validated MetricBinding objects while exposing
the ranked search plan that led to each candidate.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from polisyos.common.logger import logger

from .binding import MetricBinding
from .contract import DataContract
from .semantic import SemanticCatalogIndex
from .source_bindings import SourceBinding


@dataclass
class SearchResult:
    """
    Result of a metric search with confidence scoring.

    Attributes:
        binding: The MetricBinding for this result
        contract: The underlying DataContract
        confidence: Match confidence (0.0 to 1.0)
        matched_alias: The alias that matched the query
        is_deprecated: Whether this metric is deprecated
        route: semantic / lexical search route used for this result
        explanations: Human-readable reasons supporting the ranking
        score_breakdown: Per-route score components
        vector_metadata: Embedding metadata for semantic matches
    """

    binding: MetricBinding
    contract: DataContract
    confidence: float
    matched_alias: str | None = None
    is_deprecated: bool = False
    route: str = "lexical"
    explanations: tuple[str, ...] = ()
    score_breakdown: dict[str, float] = field(default_factory=dict)
    vector_metadata: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Set deprecated flag from contract."""

        self.is_deprecated = self.contract.deprecated


@dataclass
class SearchResponse:
    """
    Complete response from a metric search.

    Attributes:
        results: List of search results, sorted by confidence (descending)
        needs_disambiguation: True if human clarification is needed
        query: The original query string
        total_candidates: Total metrics considered
        plan_steps: Explainable ordered search-plan steps
    """

    results: list[SearchResult]
    needs_disambiguation: bool
    query: str
    total_candidates: int = 0
    plan_steps: list[dict[str, object]] = field(default_factory=list)

    @property
    def best_match(self) -> SearchResult | None:
        """Return the highest-confidence result, if any."""

        return self.results[0] if self.results else None

    @property
    def is_ambiguous(self) -> bool:
        """True if there are multiple high-confidence matches."""

        if len(self.results) < 2:
            return False
        return (self.results[0].confidence - self.results[1].confidence) < 0.1


class MetricSearcher:
    """
    Searches for metrics with semantic ranking and lexical fallback.

    If confidence is below threshold, returns needs_disambiguation=True
    rather than making a potentially incorrect guess.
    """

    def __init__(
        self,
        contracts: list[DataContract],
        *,
        bindings: Sequence[SourceBinding] | None = None,
        threshold: float = 0.7,
        max_results: int = 5,
    ) -> None:
        self._contracts: dict[str, DataContract] = {c.metric_id: c for c in contracts}
        self._threshold = threshold
        self._max_results = max_results
        self._bindings: list[SourceBinding] = list(bindings or [])

        self._alias_index: dict[str, list[str]] = {}
        self._build_alias_index(contracts)
        self._semantic_index = SemanticCatalogIndex(contracts, self._bindings)

        logger.debug(
            "MetricSearcher initialized with %s contracts, %s unique aliases",
            len(contracts),
            len(self._alias_index),
        )

    @property
    def semantic_index(self) -> SemanticCatalogIndex:
        return self._semantic_index

    def refresh_semantic_index(
        self,
        contracts: Sequence[DataContract],
        *,
        bindings: Sequence[SourceBinding] | None = None,
    ) -> list[str]:
        """Refresh lexical + semantic indices and return changed metric ids."""

        next_contracts = list(contracts)
        self._contracts = {contract.metric_id: contract for contract in next_contracts}
        self._bindings = list(bindings or self._bindings)
        self._alias_index = {}
        self._build_alias_index(next_contracts)
        return self._semantic_index.refresh(next_contracts, self._bindings)

    def _build_alias_index(self, contracts: Sequence[DataContract]) -> None:
        """Build reverse alias -> metric_id mapping."""

        for contract in contracts:
            searchable = [contract.metric_id, contract.display_name.lower(), *contract.aliases]

            last_segment = contract.metric_id.split(".")[-1]
            searchable.append(last_segment)
            searchable.extend(tag.lower() for tag in contract.tags)

            for alias in set(searchable):
                alias_lower = alias.lower().strip()
                if not alias_lower:
                    continue
                if alias_lower not in self._alias_index:
                    self._alias_index[alias_lower] = []
                if contract.metric_id not in self._alias_index[alias_lower]:
                    self._alias_index[alias_lower].append(contract.metric_id)

    def search(self, query: str) -> SearchResponse:
        """
        Search for metrics matching query using an explainable plan.

        Search plan:
        1. Exact lexical alias match
        2. Semantic vector ranking across enriched metric documents
        3. Deterministic lexical fuzzy fallback
        """

        query_lower = query.lower().strip()
        plan_steps: list[dict[str, object]] = []

        if not query_lower:
            return SearchResponse(
                results=[],
                needs_disambiguation=True,
                query=query,
                total_candidates=len(self._contracts),
                plan_steps=[
                    {
                        "step": "validate_query",
                        "route": "none",
                        "status": "empty_query",
                        "candidate_count": 0,
                    }
                ],
            )

        exact_results = self._search_exact_alias(query_lower)
        plan_steps.append(
            {
                "step": "lexical_exact",
                "route": "lexical",
                "status": "matched" if exact_results else "no_match",
                "candidate_count": len(exact_results),
            }
        )
        if len(exact_results) == 1 and exact_results[0].confidence == 1.0:
            return SearchResponse(
                results=exact_results,
                needs_disambiguation=False,
                query=query,
                total_candidates=len(self._contracts),
                plan_steps=plan_steps,
            )

        semantic_matches = self._semantic_index.search(
            query_lower,
            limit=self._max_results * 3,
            min_score=0.28,
        )
        plan_steps.append(
            {
                "step": "semantic_rank",
                "route": "semantic",
                "status": "matched" if semantic_matches else "no_match",
                "candidate_count": len(semantic_matches),
                "embedding_model": self._semantic_index.embedding_model,
            }
        )

        lexical_matches = self._search_fuzzy(query_lower)
        plan_steps.append(
            {
                "step": "lexical_fallback",
                "route": "lexical",
                "status": "matched" if lexical_matches else "no_match",
                "candidate_count": len(lexical_matches),
            }
        )

        semantic_top = semantic_matches[0].score if semantic_matches else 0.0
        lexical_top = lexical_matches[0].confidence if lexical_matches else 0.0
        query_token_count = len(self._tokenize(query_lower))
        semantic_best_metric = semantic_matches[0].metric_id if semantic_matches else None
        lexical_best_metric = lexical_matches[0].contract.metric_id if lexical_matches else None
        prefer_semantic = semantic_top >= 0.33 and (
            semantic_top >= (lexical_top + 0.05)
            or (
                query_token_count >= 4
                and semantic_top >= 0.45
                and semantic_best_metric is not None
                and (
                    semantic_best_metric != lexical_best_metric
                    or semantic_top >= max(lexical_top - 0.02, 0.45)
                )
            )
        )

        if exact_results:
            results = exact_results
        elif prefer_semantic:
            results = self._build_semantic_results(query_lower, semantic_matches, lexical_matches)
        else:
            results = lexical_matches

        results.sort(key=lambda item: (-item.confidence, item.binding.metric_id))
        results = results[: self._max_results]
        needs_disambiguation = self._needs_disambiguation(results)

        for result in results:
            if result.is_deprecated:
                logger.warning(
                    "Metric '%s' is deprecated. Consider using '%s' instead.",
                    result.contract.metric_id,
                    result.contract.superseded_by,
                )

        return SearchResponse(
            results=results,
            needs_disambiguation=needs_disambiguation,
            query=query,
            total_candidates=len(self._contracts),
            plan_steps=plan_steps,
        )

    def _search_exact_alias(self, query_lower: str) -> list[SearchResult]:
        results: list[SearchResult] = []
        if query_lower not in self._alias_index:
            return results
        for metric_id in self._alias_index[query_lower]:
            contract = self._contracts[metric_id]
            results.append(
                SearchResult(
                    binding=MetricBinding.from_contract(contract),
                    contract=contract,
                    confidence=1.0,
                    matched_alias=query_lower,
                    route="lexical",
                    explanations=(
                        f"Exact alias match for '{query_lower}'.",
                        "Semantic search skipped because deterministic lexical match succeeded.",
                    ),
                    score_breakdown={"lexical": 1.0, "semantic": 0.0},
                )
            )
        return results

    def _search_fuzzy(self, query_lower: str) -> list[SearchResult]:
        best_matches: dict[str, tuple[float, str]] = {}
        for alias, metric_ids in self._alias_index.items():
            similarity = self._compute_similarity(query_lower, alias)
            if similarity <= 0.3:
                continue
            for metric_id in metric_ids:
                current = best_matches.get(metric_id)
                if current is None or similarity > current[0]:
                    best_matches[metric_id] = (similarity, alias)
                    continue
                if similarity == current[0] and alias < current[1]:
                    best_matches[metric_id] = (similarity, alias)

        results: list[SearchResult] = []
        for metric_id, (similarity, alias) in best_matches.items():
            contract = self._contracts[metric_id]
            results.append(
                SearchResult(
                    binding=MetricBinding.from_contract(contract),
                    contract=contract,
                    confidence=similarity,
                    matched_alias=alias,
                    route="lexical",
                    explanations=(
                        f"Lexical fallback matched alias '{alias}' with similarity {similarity:.2f}.",
                    ),
                    score_breakdown={"lexical": similarity, "semantic": 0.0},
                )
            )
        results.sort(key=lambda item: (-item.confidence, item.binding.metric_id))
        return results

    def _build_semantic_results(
        self,
        query_lower: str,
        semantic_matches,
        lexical_matches: Sequence[SearchResult],
    ) -> list[SearchResult]:
        lexical_by_metric = {item.contract.metric_id: item for item in lexical_matches}
        query_terms = set(self._tokenize(query_lower))
        results: list[SearchResult] = []
        for match in semantic_matches:
            contract = self._contracts.get(match.metric_id)
            if contract is None:
                continue
            lexical = lexical_by_metric.get(match.metric_id)
            lexical_score = lexical.confidence if lexical is not None else 0.0
            coverage = len(set(match.supporting_tokens)) / max(1, len(query_terms))
            combined_score = min(1.0, match.score * 0.70 + coverage * 0.25 + lexical_score * 0.05)
            explanations = [
                f"Semantic rank {match.score:.2f} from enriched catalog metadata.",
                f"Query coverage {coverage:.2f}.",
            ]
            if match.supporting_tokens:
                explanations.append("Supporting tokens: " + ", ".join(match.supporting_tokens))
            if lexical is not None and lexical.matched_alias:
                explanations.append(f"Lexical hint preserved from alias '{lexical.matched_alias}'.")
            vector_metadata = {
                "source": match.vector_metadata.source,
                "schema_version": match.vector_metadata.schema_version,
                "embedding_model": match.vector_metadata.embedding_model,
                "timestamp": match.vector_metadata.timestamp,
                "invalidation_policy": match.vector_metadata.invalidation_policy,
                "fingerprint": match.vector_metadata.fingerprint,
            }
            results.append(
                SearchResult(
                    binding=MetricBinding.from_contract(contract),
                    contract=contract,
                    confidence=combined_score,
                    matched_alias=lexical.matched_alias if lexical is not None else None,
                    route="semantic",
                    explanations=tuple(explanations),
                    score_breakdown={
                        "semantic": match.score,
                        "coverage": coverage,
                        "lexical": lexical_score,
                    },
                    vector_metadata=vector_metadata,
                )
            )
        return results

    def _needs_disambiguation(self, results: list[SearchResult]) -> bool:
        """
        Determine if disambiguation is required.

        Returns True if:
        - No results found
        - Best result confidence < threshold
        - Multiple results with similar confidence (ambiguous)
        """

        if not results:
            return True

        best = results[0]
        if best.confidence < self._threshold:
            return True

        if len(results) >= 2:
            second = results[1]
            if (best.confidence - second.confidence) < 0.2 and second.confidence > 0.5:
                return True

        return False

    def _compute_similarity(self, query: str, candidate: str) -> float:
        """
        Compute lexical similarity between query and candidate.

        Uses Jaccard similarity on word tokens with simple prefix/substring boosts.
        """

        query_tokens = set(self._tokenize(query))
        candidate_tokens = set(self._tokenize(candidate))

        if not query_tokens or not candidate_tokens:
            return 0.0

        intersection = len(query_tokens & candidate_tokens)
        union = len(query_tokens | candidate_tokens)

        jaccard = intersection / union if union > 0 else 0.0

        substring_boost = 0.0
        if query in candidate or candidate in query:
            substring_boost = 0.3

        prefix_boost = 0.0
        if candidate.startswith(query) or query.startswith(candidate):
            prefix_boost = 0.2

        return min(1.0, jaccard + substring_boost + prefix_boost)

    def _tokenize(self, text: str) -> list[str]:
        """Tokenize text into normalized words."""

        normalized = text.replace("_", " ").replace(".", " ").replace("-", " ")
        return [token for token in normalized.split() if token]

    def resolve(self, query: str) -> MetricBinding:
        """
        Resolve a query to a single binding.

        Convenience method that raises if disambiguation is needed.
        """

        response = self.search(query)

        if response.needs_disambiguation:
            if not response.results:
                raise ValueError(
                    f"No metrics found matching '{query}'. "
                    f"Available metrics: {list(self._contracts.keys())[:5]}..."
                )
            options = [
                f"  - {r.contract.display_name} ({r.contract.metric_id}): {r.confidence:.0%}"
                for r in response.results
            ]
            raise ValueError(
                f"Ambiguous query '{query}'. Please specify one of:\n" + "\n".join(options)
            )

        if response.best_match is None:
            raise ValueError(f"No best match available for '{query}'.")
        return response.best_match.binding
