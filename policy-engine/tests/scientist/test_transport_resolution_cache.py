from __future__ import annotations

import pytest

from polisyos.datasets.knowledge.types import PStarZResult
from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, GraphType
from polisyos.ir.analytics.context import ContextProfile, IncomeLevel
from polisyos.lex.legal_evaluation.transport_constraints import LegalConstraintSet
from polisyos.scientist.nodes.builtins.causal.resolve_transport import (
    TransportabilityResolutionLoop,
)


class _CountingDatasetRegistry:
    def __init__(self) -> None:
        self.find_calls = 0
        self.compute_calls = 0

    def find_datasets_for_variable(
        self,
        canonical_var: str,
        country_code: str,
        year_range: tuple[int, int] | None = None,
    ) -> list[object]:
        del canonical_var, country_code, year_range
        self.find_calls += 1
        return [object()]

    def compute_p_star_z(
        self,
        canonical_var: str,
        country_code: str,
        year: int,
        *,
        condition_on: dict[str, float] | None = None,
    ) -> PStarZResult:
        del country_code, year
        self.compute_calls += 1
        return PStarZResult(
            canonical_variable=canonical_var,
            value=0.42,
            dataset_id="WGI",
            raw_variable=canonical_var,
            is_proxy=False,
            confidence=0.9,
            penalty_breakdown={},
            is_conditional=bool(condition_on),
            condition_on=condition_on or {},
        )


def _graph() -> CausalGraphModel:
    return CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["tax_rate", "tax_compliance", "gdp_growth"],
        edges=[
            CausalEdge(src="tax_rate", dst="tax_compliance"),
            CausalEdge(src="tax_compliance", dst="gdp_growth"),
        ],
    )


def _source_target() -> tuple[ContextProfile, ContextProfile]:
    source = ContextProfile(
        context_id="DE",
        income_level=IncomeLevel.HIGH,
        institutional_quality=0.9,
    )
    target = ContextProfile(
        context_id="UA",
        income_level=IncomeLevel.LOWER_MIDDLE,
        institutional_quality=0.25,
        time_period="2020-2024",
    )
    return source, target


def _no_constraints(**kwargs) -> LegalConstraintSet:
    del kwargs
    return LegalConstraintSet(
        jurisdiction="UA",
        policy_domain="tax",
        hard_constraints=[],
        soft_constraints=[],
        data_license_constraints=[],
        legal_dag_mappings=[],
    )


def test_transport_resolution_cache_hits_within_single_run(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "polisyos.scientist.nodes.builtins.causal.resolve_transport.evaluate_transport_constraints",
        _no_constraints,
    )
    registry = _CountingDatasetRegistry()
    loop = TransportabilityResolutionLoop(
        dataset_registry=registry,
        legal_kg_db_path=None,
        skg_query=object(),
        max_rounds=3,
    )
    source, target = _source_target()

    result = loop.resolve(
        source_context=source,
        target_context=target,
        causal_graph=_graph(),
        query_treatment="tax_rate",
        query_outcome="gdp_growth",
        solver_mode="simplified",
    )

    assert result.resolution_rounds >= 2
    assert registry.compute_calls == 1
    assert registry.find_calls == 1


def test_transport_resolution_cache_isolation_between_runs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "polisyos.scientist.nodes.builtins.causal.resolve_transport.evaluate_transport_constraints",
        _no_constraints,
    )
    registry = _CountingDatasetRegistry()
    loop = TransportabilityResolutionLoop(
        dataset_registry=registry,
        legal_kg_db_path=None,
        skg_query=object(),
        max_rounds=3,
    )
    source, target = _source_target()

    loop.resolve(
        source_context=source,
        target_context=target,
        causal_graph=_graph(),
        query_treatment="tax_rate",
        query_outcome="gdp_growth",
        solver_mode="simplified",
    )
    loop.resolve(
        source_context=source,
        target_context=target,
        causal_graph=_graph(),
        query_treatment="tax_rate",
        query_outcome="gdp_growth",
        solver_mode="simplified",
    )

    assert registry.compute_calls == 2
    assert registry.find_calls == 2


def test_transport_resolution_condition_key_normalization() -> None:
    registry = _CountingDatasetRegistry()
    loop = TransportabilityResolutionLoop(
        dataset_registry=registry,
        legal_kg_db_path=None,
        skg_query=object(),
    )
    loop._cache_clear()
    loop._cached_compute_p_star_z(
        canonical_var="tax_compliance",
        country_code="UA",
        year=2022,
        condition_on={"dose": 1.0, "a": 0.5},
    )
    loop._cached_compute_p_star_z(
        canonical_var="tax_compliance",
        country_code="UA",
        year=2022,
        condition_on={"a": 0.5, "dose": 1.0},
    )

    assert registry.compute_calls == 1
