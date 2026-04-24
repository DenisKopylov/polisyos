from __future__ import annotations

from dataclasses import dataclass

import pytest

from polisyos.datasets.knowledge.proxy_resolver import (
    compose_confidence_chain,
    compose_confidence_harmonic,
    resolve_proxy,
    validate_proxy,
)


@dataclass(frozen=True)
class _DatasetMatch:
    dataset_id: str
    raw_variable: str
    canonical_variable: str
    is_proxy: bool
    mapping_confidence: float
    proxy_penalty: float = 0.0


class _DatasetRegistry:
    def __init__(self, matches: list[_DatasetMatch]) -> None:
        self._matches = matches

    def find_datasets_for_variable(
        self,
        canonical_var: str,
        country_code: str,
        year_range: tuple[int, int] | None = None,
    ) -> list[_DatasetMatch]:
        del canonical_var, country_code, year_range
        return list(self._matches)


class _SKGWithContextAdjust:
    def __init__(self, table: dict[tuple[str, str, str], float]) -> None:
        self._table = table

    def get_proxy_context_adjustment(
        self,
        *,
        proxy_variable: str,
        target_variable: str,
        target_context: str,
    ) -> float | None:
        return self._table.get((proxy_variable, target_variable, target_context))


def test_resolve_proxy_uses_context_dependent_adjustment() -> None:
    matches = [
        _DatasetMatch(
            dataset_id="TI_CPI",
            raw_variable="cpi_score",
            canonical_variable="cpi_score",
            is_proxy=True,
            mapping_confidence=0.78,
            proxy_penalty=0.22,
        ),
    ]
    registry = _DatasetRegistry(matches)
    skg = _SKGWithContextAdjust(
        table={
            ("cpi_score", "institutional_quality", "DE"): 0.92,
            ("cpi_score", "institutional_quality", "UA"): 0.70,
        }
    )

    de_chain = resolve_proxy("institutional_quality", "DE", registry, skg)
    ua_chain = resolve_proxy("institutional_quality", "UA", registry, skg)

    assert de_chain.proxies
    assert ua_chain.proxies
    assert de_chain.proxies[0].context_adjustment > ua_chain.proxies[0].context_adjustment
    assert de_chain.proxies[0].effective_confidence > ua_chain.proxies[0].effective_confidence


def test_resolve_proxy_fallback_to_conservative_adjustment_without_evidence() -> None:
    matches = [
        _DatasetMatch(
            dataset_id="WB_WDI",
            raw_variable="SL.TLF.TOTL.IN.ZS",
            canonical_variable="informal_employment",
            is_proxy=True,
            mapping_confidence=0.65,
            proxy_penalty=0.35,
        ),
    ]
    registry = _DatasetRegistry(matches)

    chain = resolve_proxy("informal_economy_share", "UA", registry, object())

    assert len(chain.proxies) == 1
    assert chain.proxies[0].context_adjustment == 0.8
    assert chain.proxies[0].source == "seed_table"


def test_resolve_proxy_returns_empty_proxies_when_direct_match_exists() -> None:
    matches = [
        _DatasetMatch(
            dataset_id="WB_WGI",
            raw_variable="rl_est",
            canonical_variable="institutional_quality",
            is_proxy=False,
            mapping_confidence=0.91,
        ),
        _DatasetMatch(
            dataset_id="TI_CPI",
            raw_variable="cpi_score",
            canonical_variable="cpi_score",
            is_proxy=True,
            mapping_confidence=0.80,
        ),
    ]
    registry = _DatasetRegistry(matches)

    chain = resolve_proxy("institutional_quality", "UA", registry, object())

    assert chain.proxies == []
    assert chain.best_single_confidence == 0.91


def test_resolve_proxy_sorts_candidates_by_effective_confidence() -> None:
    matches = [
        _DatasetMatch(
            dataset_id="A",
            raw_variable="a_raw",
            canonical_variable="proxy_a",
            is_proxy=True,
            mapping_confidence=0.70,
        ),
        _DatasetMatch(
            dataset_id="B",
            raw_variable="b_raw",
            canonical_variable="proxy_b",
            is_proxy=True,
            mapping_confidence=0.82,
        ),
        _DatasetMatch(
            dataset_id="C",
            raw_variable="c_raw",
            canonical_variable="proxy_c",
            is_proxy=True,
            mapping_confidence=0.62,
        ),
    ]
    registry = _DatasetRegistry(matches)
    skg = _SKGWithContextAdjust(
        table={
            ("proxy_a", "target_var", "UA"): 0.95,
            ("proxy_b", "target_var", "UA"): 0.70,
            ("proxy_c", "target_var", "UA"): 0.60,
        }
    )

    chain = resolve_proxy("target_var", "UA", registry, skg)

    ordered = [candidate.proxy_dataset_id for candidate in chain.proxies]
    assert ordered == ["A", "B", "C"]
    assert chain.best_single_confidence == chain.proxies[0].effective_confidence


# --- compose_confidence_harmonic tests ---


def test_harmonic_identity() -> None:
    assert compose_confidence_harmonic(1.0, 1.0) == pytest.approx(1.0)


def test_harmonic_zero_propagates() -> None:
    assert compose_confidence_harmonic(0.0, 0.8) == 0.0
    assert compose_confidence_harmonic(0.9, 0.0) == 0.0


def test_harmonic_bounded_by_arithmetic_mean() -> None:
    """Harmonic mean ≤ arithmetic mean (always)."""
    result = compose_confidence_harmonic(0.9, 0.3)
    arithmetic = (0.9 + 0.3) / 2
    assert result <= arithmetic + 1e-9
    assert result >= min(0.9, 0.3) - 1e-9


def test_harmonic_monotonicity() -> None:
    low = compose_confidence_harmonic(0.5, 0.5)
    high = compose_confidence_harmonic(0.5, 0.8)
    assert high > low


def test_harmonic_symmetry() -> None:
    assert compose_confidence_harmonic(0.4, 0.7) == pytest.approx(
        compose_confidence_harmonic(0.7, 0.4)
    )


@pytest.mark.parametrize(
    ("scores", "expected_zero"),
    [
        ([], True),
        ([0.0, 0.8], True),
        ([0.8], False),
    ],
)
def test_chain_edge_cases(scores: list[float], expected_zero: bool) -> None:
    result = compose_confidence_chain(scores)
    if expected_zero:
        assert result == 0.0
    else:
        assert result > 0.0


def test_chain_single_element() -> None:
    assert compose_confidence_chain([0.75]) == pytest.approx(0.75)


def test_chain_degradation() -> None:
    """Mixing weaker links into a chain lowers overall confidence."""
    scores = [0.8, 0.6, 0.7]
    result = compose_confidence_chain(scores)
    assert result < max(scores)
    assert result > 0.0


def test_resolve_proxy_uses_harmonic_confidence() -> None:
    """Effective confidence uses harmonic mean, not multiplicative."""
    matches = [
        _DatasetMatch(
            dataset_id="X",
            raw_variable="x_raw",
            canonical_variable="proxy_x",
            is_proxy=True,
            mapping_confidence=0.8,
        ),
    ]
    registry = _DatasetRegistry(matches)
    skg = _SKGWithContextAdjust(table={("proxy_x", "target_y", "US"): 0.6})
    chain = resolve_proxy("target_y", "US", registry, skg)
    assert chain.proxies
    proxy = chain.proxies[0]
    # Harmonic mean of 0.8 and 0.6 = 2*0.8*0.6/(0.8+0.6) ≈ 0.6857
    expected = 2.0 * 0.8 * 0.6 / (0.8 + 0.6)
    assert proxy.effective_confidence == pytest.approx(expected, abs=0.01)


def test_resolve_proxy_chain_length_warning() -> None:
    """Long proxy chains get a warning."""
    matches = [
        _DatasetMatch(
            dataset_id=f"D{i}",
            raw_variable=f"raw_{i}",
            canonical_variable=f"proxy_{i}",
            is_proxy=True,
            mapping_confidence=0.7,
        )
        for i in range(7)
    ]
    registry = _DatasetRegistry(matches)
    chain = resolve_proxy("target_z", "GB", registry, object())
    assert chain.chain_length_warning is not None
    assert "exceeds" in chain.chain_length_warning


# --- validate_proxy tests ---


def _simple_graph() -> dict[str, set[str]]:
    """X -> M -> Y, Z -> Y, P -> M (proxy for M)."""
    return {
        "X": {"M"},
        "M": {"Y"},
        "Z": {"Y"},
        "P": {"M"},
        "Y": set(),
    }


def test_validate_proxy_valid_case() -> None:
    adj = _simple_graph()
    result = validate_proxy(
        proxy="P",
        target="M",
        outcome="Y",
        adjacency=adj,
        correlation_matrix={("P", "M"): 0.85},
    )
    assert result.relevance_check
    assert result.exclusion_check
    assert result.completeness_check
    assert result.overall_valid


def test_validate_proxy_no_path_to_target() -> None:
    adj = {"A": set(), "B": set(), "Y": set()}
    result = validate_proxy(
        proxy="A",
        target="B",
        outcome="Y",
        adjacency=adj,
    )
    assert not result.relevance_check
    assert not result.overall_valid


def test_validate_proxy_direct_edge_to_outcome() -> None:
    adj = {"P": {"M", "Y"}, "M": {"Y"}, "Y": set()}
    result = validate_proxy(
        proxy="P",
        target="M",
        outcome="Y",
        adjacency=adj,
        correlation_matrix={("P", "M"): 0.7},
    )
    assert not result.exclusion_check


def test_validate_proxy_low_correlation() -> None:
    adj = _simple_graph()
    result = validate_proxy(
        proxy="P",
        target="M",
        outcome="Y",
        adjacency=adj,
        correlation_matrix={("P", "M"): 0.1},
        invertibility_threshold=0.3,
    )
    assert not result.completeness_check
    assert not result.overall_valid


def test_validate_proxy_missing_correlation_flags_expert() -> None:
    adj = _simple_graph()
    result = validate_proxy(
        proxy="P",
        target="M",
        outcome="Y",
        adjacency=adj,
    )
    assert result.requires_expert_review
