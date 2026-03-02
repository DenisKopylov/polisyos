"""Proxy resolution for transportability when direct data is unavailable."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

ProxySource = Literal["meta_analysis", "seed_table", "skg_correlation"]


class ProxyCandidate(BaseModel):
    """Single proxy variable candidate for a missing target variable."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    proxy_variable: str
    proxy_dataset_id: str
    proxy_raw_name: str
    base_correlation: float
    context_adjustment: float
    effective_confidence: float
    source: ProxySource


class ProxyChain(BaseModel):
    """Ranked proxy chain for one unresolved target variable."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    target_variable: str
    proxies: list[ProxyCandidate] = Field(default_factory=list)
    composite_method: str | None = None
    composite_confidence: float | None = None
    best_single_confidence: float = 0.0
    chain_length_warning: str | None = None


@runtime_checkable
class DatasetRegistryLike(Protocol):
    """Minimal contract expected by proxy resolver."""

    def find_datasets_for_variable(
        self,
        canonical_var: str,
        country_code: str,
        year_range: tuple[int, int] | None = None,
    ) -> Sequence[Any]:
        """Resolve datasets for one canonical variable."""


@runtime_checkable
class SKGQueryLike(Protocol):
    """Optional SKG query contract used for context-aware adjustments."""

    def query_claims(
        self,
        *,
        cause: str,
        effect: str,
        min_trust: float = 0.0,
    ) -> Sequence[Any]:
        """Query causal claims between two variables."""


MAX_SAFE_CHAIN_LENGTH = 5


def compose_confidence_harmonic(c1: float, c2: float) -> float:
    """Harmonic mean: chain confidence <= min(c1, c2). Weakest-link property."""
    if c1 <= 0 or c2 <= 0:
        return 0.0
    return 2.0 * c1 * c2 / (c1 + c2)


def compose_confidence_chain(scores: Sequence[float]) -> float:
    """Iterative harmonic composition for N-length proxy chains."""
    if not scores:
        return 0.0
    result = float(scores[0])
    for s in scores[1:]:
        result = compose_confidence_harmonic(result, s)
    return result


def resolve_proxy(
    target_var: str,
    target_context: str,
    dataset_registry: DatasetRegistryLike,
    skg_query: SKGQueryLike | Any,
) -> ProxyChain:
    """Resolve ranked proxy candidates with context-aware confidence penalties."""
    matches = list(
        dataset_registry.find_datasets_for_variable(
            canonical_var=target_var,
            country_code=target_context,
            year_range=None,
        )
    )

    direct_confidence = _best_direct_confidence(matches)
    if direct_confidence > 0.0:
        return ProxyChain(
            target_variable=target_var,
            proxies=[],
            composite_method=None,
            composite_confidence=None,
            best_single_confidence=_clamp01(direct_confidence),
        )

    candidates: list[ProxyCandidate] = []
    for match in matches:
        if not _is_proxy_match(match):
            continue

        proxy_var = _row_text(match, "canonical_variable", "canonical_var", default=target_var)
        proxy_raw = _row_text(match, "raw_variable", "raw_name", "dataset_var", default=proxy_var)
        dataset_id = _row_text(match, "dataset_id", "id", default="")

        base_correlation = _derive_base_correlation(match)
        context_adjustment, source = _derive_context_adjustment(
            skg_query=skg_query,
            proxy_variable=proxy_var,
            target_variable=target_var,
            target_context=target_context,
        )

        candidates.append(
            ProxyCandidate(
                proxy_variable=proxy_var,
                proxy_dataset_id=dataset_id,
                proxy_raw_name=proxy_raw,
                base_correlation=base_correlation,
                context_adjustment=context_adjustment,
                effective_confidence=_clamp01(
                    compose_confidence_harmonic(base_correlation, context_adjustment)
                ),
                source=source,
            )
        )

    candidates.sort(key=lambda row: row.effective_confidence, reverse=True)
    best = candidates[0].effective_confidence if candidates else 0.0

    chain_warning: str | None = None
    if len(candidates) > MAX_SAFE_CHAIN_LENGTH:
        chain_warning = (
            f"Proxy chain length {len(candidates)} exceeds recommended "
            f"maximum {MAX_SAFE_CHAIN_LENGTH}; confidence degradation likely."
        )

    composite_conf: float | None = None
    if len(candidates) >= 2:
        composite_conf = compose_confidence_chain(
            [c.effective_confidence for c in candidates]
        )

    return ProxyChain(
        target_variable=target_var,
        proxies=candidates,
        composite_method="harmonic" if composite_conf is not None else None,
        composite_confidence=composite_conf,
        best_single_confidence=best,
        chain_length_warning=chain_warning,
    )


def _best_direct_confidence(matches: Iterable[Any]) -> float:
    best = 0.0
    for row in matches:
        if _is_proxy_match(row):
            continue
        conf = _row_float(row, "mapping_confidence", "confidence", "similarity")
        if conf is None:
            penalty = _row_float(row, "proxy_penalty")
            if penalty is not None:
                conf = 1.0 - penalty
        if conf is not None:
            best = max(best, _clamp01(conf))
    return best


def _derive_base_correlation(row: Any) -> float:
    confidence = _row_float(row, "mapping_confidence", "confidence", "similarity")
    if confidence is not None:
        return _clamp01(confidence)
    proxy_penalty = _row_float(row, "proxy_penalty")
    if proxy_penalty is not None:
        return _clamp01(1.0 - proxy_penalty)
    return 0.5


def _derive_context_adjustment(
    *,
    skg_query: SKGQueryLike | Any,
    proxy_variable: str,
    target_variable: str,
    target_context: str,
) -> tuple[float, ProxySource]:
    explicit = _resolve_explicit_context_adjustment(
        skg_query=skg_query,
        proxy_variable=proxy_variable,
        target_variable=target_variable,
        target_context=target_context,
    )
    if explicit is not None:
        return explicit

    inferred = _estimate_adjustment_from_skg(
        skg_query=skg_query,
        proxy_variable=proxy_variable,
        target_variable=target_variable,
        target_context=target_context,
    )
    if inferred is not None:
        return inferred, "skg_correlation"
    return 0.8, "seed_table"


def _resolve_explicit_context_adjustment(
    *,
    skg_query: Any,
    proxy_variable: str,
    target_variable: str,
    target_context: str,
) -> tuple[float, ProxySource] | None:
    resolver = getattr(skg_query, "get_proxy_context_adjustment", None)
    if callable(resolver):
        raw = resolver(
            proxy_variable=proxy_variable,
            target_variable=target_variable,
            target_context=target_context,
        )
        if isinstance(raw, tuple) and len(raw) == 2:
            value = _coerce_float(raw[0])
            source = _coerce_source(raw[1])
            if value is not None and source is not None:
                return _clamp01(value), source
        value = _coerce_float(raw)
        if value is not None:
            return _clamp01(value), "meta_analysis"

    resolver = getattr(skg_query, "query_proxy_correlation", None)
    if callable(resolver):
        raw = resolver(
            proxy_variable=proxy_variable,
            target_variable=target_variable,
            target_context=target_context,
        )
        if isinstance(raw, dict):
            corr = _coerce_float(raw.get("correlation"))
            if corr is not None:
                # Transform |corr| in [0,1] into conservative confidence multiplier.
                return _clamp01(0.6 + 0.4 * abs(corr)), "meta_analysis"
        corr = _coerce_float(raw)
        if corr is not None:
            return _clamp01(0.6 + 0.4 * abs(corr)), "meta_analysis"
    return None


def _estimate_adjustment_from_skg(
    *,
    skg_query: Any,
    proxy_variable: str,
    target_variable: str,
    target_context: str,
) -> float | None:
    scores: list[float] = []

    query_claims = getattr(skg_query, "query_claims", None)
    if callable(query_claims):
        for cause, effect in (
            (proxy_variable, target_variable),
            (target_variable, proxy_variable),
        ):
            try:
                claims = query_claims(cause=cause, effect=effect, min_trust=0.0)
            except TypeError:
                claims = query_claims(cause=cause, effect=effect)
            for claim in claims:
                trust = _row_float(claim, "trust_score")
                if trust is not None:
                    scores.append(_clamp01(0.65 + 0.35 * trust))

    store = getattr(skg_query, "_store", None)
    get_estimates = getattr(store, "get_parameter_estimates", None)
    if callable(get_estimates):
        proxy_estimates = get_estimates(proxy_variable, country=target_context)
        target_estimates = get_estimates(target_variable, country=target_context)
        if proxy_estimates and target_estimates:
            ratio = min(len(proxy_estimates), len(target_estimates)) / max(
                len(proxy_estimates), len(target_estimates)
            )
            scores.append(_clamp01(0.75 + 0.25 * ratio))
        elif proxy_estimates or target_estimates:
            scores.append(0.72)

    if not scores:
        return None
    return _clamp01(sum(scores) / len(scores))


def _is_proxy_match(row: Any) -> bool:
    raw = _row_value(row, "is_proxy")
    return bool(raw) if raw is not None else False


def _row_text(row: Any, *keys: str, default: str = "") -> str:
    for key in keys:
        value = _row_value(row, key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return default


def _row_float(row: Any, *keys: str) -> float | None:
    for key in keys:
        value = _row_value(row, key)
        if value is None:
            continue
        cast = _coerce_float(value)
        if cast is not None:
            return cast
    return None


def _row_value(row: Any, key: str) -> Any:
    if isinstance(row, dict):
        return row.get(key)
    return getattr(row, key, None)


def _coerce_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _coerce_source(value: Any) -> ProxySource | None:
    if not isinstance(value, str):
        return None
    lowered = value.strip().lower()
    if lowered in {"meta_analysis", "seed_table", "skg_correlation"}:
        return lowered
    return None


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


class ProxyValidityChecklist(BaseModel):
    """Full 4-condition proxy validity check result."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    proxy: str
    target: str
    outcome: str
    relevance_check: bool
    exclusion_check: bool
    non_collider_check: bool
    completeness_check: bool
    overall_valid: bool
    violations: list[str] = Field(default_factory=list)
    requires_expert_review: bool = False


def validate_proxy(
    proxy: str,
    target: str,
    outcome: str,
    adjacency: dict[str, set[str]],
    correlation_matrix: dict[tuple[str, str], float] | None = None,
    invertibility_threshold: float = 0.3,
) -> ProxyValidityChecklist:
    """Full 4-condition proxy validity check against causal graph adjacency.

    Conditions:
    1. relevance: proxy connected to target (direct edge or path)
    2. exclusion: no direct edge proxy->outcome bypassing target
    3. non_collider: proxy is not a collider on the path treatment->outcome
    4. completeness: Corr(proxy, target) > invertibility_threshold
    """
    violations: list[str] = []
    requires_expert = False

    # 1. Relevance: proxy must be adjacent to or ancestor of target
    proxy_neighbors = adjacency.get(proxy, set())
    target_neighbors = adjacency.get(target, set())
    relevance = target in proxy_neighbors or proxy in target_neighbors
    if not relevance:
        # Check indirect path
        relevance = _bfs_path_exists(adjacency, proxy, target)
    if not relevance:
        violations.append(f"proxy '{proxy}' has no path to target '{target}'")

    # 2. Exclusion: proxy should not directly cause outcome (bypassing target)
    exclusion = outcome not in proxy_neighbors
    if not exclusion:
        if target in proxy_neighbors:
            requires_expert = True
            violations.append(
                f"proxy '{proxy}' has direct edge to outcome '{outcome}'; "
                "expert review recommended"
            )
        else:
            violations.append(
                f"proxy '{proxy}' directly affects outcome '{outcome}' without target path"
            )

    # 3. Non-collider: proxy should not be a node receiving edges from both sides
    incoming_to_proxy = {node for node, children in adjacency.items() if proxy in children}
    non_collider = True
    for node_a in incoming_to_proxy:
        for node_b in incoming_to_proxy:
            if node_a != node_b and node_a != proxy and node_b != proxy:
                if _bfs_path_exists(adjacency, node_a, outcome) and _bfs_path_exists(
                    adjacency, node_b, outcome
                ):
                    non_collider = False
                    break
        if not non_collider:
            break
    if not non_collider:
        violations.append(f"proxy '{proxy}' appears as a collider; conditioning may bias")

    # 4. Completeness: correlation above invertibility threshold
    completeness = True
    if correlation_matrix is not None:
        corr = correlation_matrix.get((proxy, target)) or correlation_matrix.get(
            (target, proxy)
        )
        if corr is not None:
            completeness = abs(corr) > invertibility_threshold
            if not completeness:
                violations.append(
                    f"Corr({proxy},{target})={corr:.3f} below "
                    f"invertibility threshold {invertibility_threshold}"
                )
        else:
            requires_expert = True
    else:
        requires_expert = True

    overall = relevance and exclusion and non_collider and completeness
    return ProxyValidityChecklist(
        proxy=proxy,
        target=target,
        outcome=outcome,
        relevance_check=relevance,
        exclusion_check=exclusion,
        non_collider_check=non_collider,
        completeness_check=completeness,
        overall_valid=overall,
        violations=violations,
        requires_expert_review=requires_expert,
    )


def _bfs_path_exists(adjacency: dict[str, set[str]], start: str, goal: str) -> bool:
    if start == goal:
        return True
    visited: set[str] = {start}
    queue: list[str] = [start]
    while queue:
        node = queue.pop(0)
        for nxt in adjacency.get(node, set()):
            if nxt == goal:
                return True
            if nxt not in visited:
                visited.add(nxt)
                queue.append(nxt)
    return False


__all__ = [
    "DatasetRegistryLike",
    "MAX_SAFE_CHAIN_LENGTH",
    "ProxyCandidate",
    "ProxyChain",
    "ProxyValidityChecklist",
    "SKGQueryLike",
    "compose_confidence_chain",
    "compose_confidence_harmonic",
    "resolve_proxy",
    "validate_proxy",
]
