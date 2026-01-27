"""
Metric search engine with disambiguation.

Resolves fuzzy user queries into validated MetricBinding objects.
If confidence is low, signals that human disambiguation is required.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List

from polisyos.common.logger import logger

from .binding import MetricBinding
from .contract import DataContract


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
    """

    binding: MetricBinding
    contract: DataContract
    confidence: float
    matched_alias: str | None = None
    is_deprecated: bool = False

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
    """

    results: List[SearchResult]
    needs_disambiguation: bool
    query: str
    total_candidates: int = 0

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
    Searches for metrics with disambiguation logic.

    If confidence is below threshold, returns needs_disambiguation=True
    rather than making a potentially incorrect guess.
    """

    def __init__(
        self,
        contracts: List[DataContract],
        threshold: float = 0.7,
        max_results: int = 5,
    ) -> None:
        """
        Initialize the searcher with contracts.

        Args:
            contracts: List of DataContract to search
            threshold: Minimum confidence to avoid disambiguation
            max_results: Maximum results to return
        """

        self._contracts: dict[str, DataContract] = {c.metric_id: c for c in contracts}
        self._threshold = threshold
        self._max_results = max_results

        # Build reverse index: alias -> [metric_id, ...]
        self._alias_index: dict[str, List[str]] = {}
        self._build_alias_index(contracts)

        logger.debug(
            "MetricSearcher initialized with %s contracts, %s unique aliases",
            len(contracts),
            len(self._alias_index),
        )

    def _build_alias_index(self, contracts: List[DataContract]) -> None:
        """Build reverse alias -> metric_id mapping."""

        for contract in contracts:
            searchable = [
                contract.metric_id,
                contract.display_name.lower(),
            ] + contract.aliases

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
        Search for metrics matching query.

        Args:
            query: User's search query (e.g., "unemployment", "GDP growth")

        Returns:
            SearchResponse with results and disambiguation flag
        """

        query_lower = query.lower().strip()

        if not query_lower:
            return SearchResponse(
                results=[],
                needs_disambiguation=True,
                query=query,
                total_candidates=len(self._contracts),
            )

        results: List[SearchResult] = []

        # Phase 1: Exact alias match
        if query_lower in self._alias_index:
            metric_ids = self._alias_index[query_lower]
            for metric_id in metric_ids:
                contract = self._contracts[metric_id]
                results.append(
                    SearchResult(
                        binding=MetricBinding.from_contract(contract),
                        contract=contract,
                        confidence=1.0,
                        matched_alias=query_lower,
                    )
                )

        if len(results) == 1 and results[0].confidence == 1.0:
            return SearchResponse(
                results=results,
                needs_disambiguation=False,
                query=query,
                total_candidates=len(self._contracts),
            )

        # Phase 2: Fuzzy matching
        if not results:
            seen_ids: set[str] = set()

            for alias, metric_ids in self._alias_index.items():
                similarity = self._compute_similarity(query_lower, alias)

                if similarity > 0.3:
                    for metric_id in metric_ids:
                        if metric_id in seen_ids:
                            continue
                        seen_ids.add(metric_id)

                        contract = self._contracts[metric_id]
                        results.append(
                            SearchResult(
                                binding=MetricBinding.from_contract(contract),
                                contract=contract,
                                confidence=similarity,
                                matched_alias=alias,
                            )
                        )

        results.sort(key=lambda r: (-r.confidence, r.binding.metric_id))
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
        )

    def _needs_disambiguation(self, results: List[SearchResult]) -> bool:
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
            if (best.confidence - second.confidence) < 0.15 and second.confidence > 0.5:
                return True

        return False

    def _compute_similarity(self, query: str, candidate: str) -> float:
        """
        Compute similarity between query and candidate.

        Uses Jaccard similarity on word tokens.
        Future: Replace with embedding-based similarity.
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

    def _tokenize(self, text: str) -> List[str]:
        """
        Tokenize text into words.

        Handles underscores and dots as separators.
        """

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

        return response.best_match.binding
