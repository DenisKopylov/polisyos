from __future__ import annotations

import json

import duckdb

from polisyos.academic.knowledge.parameter_selector import ParameterSelector
from polisyos.academic.knowledge.skg_query import SKGQuery
from polisyos.ir.analytics.causal_graph import CausalGraphModel, GraphType
from polisyos.ir.analytics.context import ContextProfile, IncomeLevel
from polisyos.ir.analytics.transportability import TransportabilityStatus


def _seed_params(db_path, rows: list[tuple[str, str, str]]) -> None:
    con = duckdb.connect(str(db_path))
    try:
        con.execute(
            """
            CREATE TABLE ac_skg_parameters (
                param_id VARCHAR,
                canonical_name VARCHAR,
                openalex_id VARCHAR,
                parameter_json VARCHAR,
                context_json VARCHAR
            )
            """
        )
        con.executemany(
            "INSERT INTO ac_skg_parameters VALUES (?, ?, ?, ?, ?)",
            rows,
        )
    finally:
        con.close()


def test_select_for_context_uses_max_confidence_times_evidence_weight(tmp_path) -> None:
    db_path = tmp_path / "skg.duckdb"
    _seed_params(
        db_path,
        [
            (
                "p_cee",
                "fiscal_multiplier",
                "W_CEE",
                json.dumps(
                    {
                        "name": "fiscal_multiplier",
                        "value": 1.3,
                        "parameter_type": "quantitative",
                        "evidence_strength": "observational",
                    }
                ),
                json.dumps(
                    {
                        "context_id": "PL",
                        "income_level": "lower_middle",
                        "institutional_quality": 0.45,
                        "post_communist": True,
                    }
                ),
            ),
            (
                "p_far",
                "fiscal_multiplier",
                "W_FAR",
                json.dumps(
                    {
                        "name": "fiscal_multiplier",
                        "value": 2.1,
                        "parameter_type": "quantitative",
                        "evidence_strength": "theoretical",
                    }
                ),
                json.dumps(
                    {
                        "context_id": "US",
                        "income_level": "high",
                        "institutional_quality": 0.9,
                        "post_communist": False,
                    }
                ),
            ),
        ],
    )
    query = SKGQuery(db_path=db_path, index_dir=tmp_path / "idx")
    selector = ParameterSelector(query)
    target_context = ContextProfile(
        context_id="UA",
        income_level=IncomeLevel.LOWER_MIDDLE,
        institutional_quality=0.4,
        post_communist=True,
    )
    graph = CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["fiscal_multiplier"],
        edges=[],
    )

    try:
        best_param, applicability = selector.select_for_context(
            parameter_name="fiscal_multiplier",
            target_context=target_context,
            causal_graph=graph,
        )
    finally:
        query.close()

    assert best_param is not None
    assert best_param.value == 1.3
    assert applicability.is_applicable is True
    assert applicability.transport_status in {
        TransportabilityStatus.DIRECT,
        TransportabilityStatus.TRANSPORTABLE,
    }


def test_select_for_context_low_confidence_fallback_and_multiplier(
    tmp_path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "skg.duckdb"
    _seed_params(
        db_path,
        [
            (
                "p1",
                "fiscal_multiplier",
                "W1",
                json.dumps(
                    {
                        "name": "fiscal_multiplier",
                        "value": 0.5,
                        "parameter_type": "quantitative",
                        "evidence_strength": "unknown",
                    }
                ),
                json.dumps({"context_id": "SRC", "income_level": "high"}),
            )
        ],
    )

    # Force confidence = 0.5 via distance path for deterministic multiplier check.
    monkeypatch.setattr(
        "polisyos.ir.analytics.context.ContextProfile.distance_to",
        lambda self, other: 1.0,
    )

    query = SKGQuery(db_path=db_path, index_dir=tmp_path / "idx")
    selector = ParameterSelector(query)
    target_context = ContextProfile(context_id="UA", income_level=IncomeLevel.LOWER_MIDDLE)
    graph = CausalGraphModel(graph_type=GraphType.DAG, nodes=["fiscal_multiplier"], edges=[])

    try:
        param, applicability = selector.select_for_context(
            parameter_name="fiscal_multiplier",
            target_context=target_context,
            causal_graph=graph,
        )
        fallback_param, fallback_applicability = selector.select_for_context(
            parameter_name="fiscal_multiplier",
            target_context=target_context,
            causal_graph=graph,
            min_transport_confidence=0.8,
        )
    finally:
        query.close()

    assert param is not None
    assert applicability.transport_confidence == 0.5
    assert applicability.uncertainty_multiplier == 2.0

    assert fallback_param is None
    assert fallback_applicability.is_applicable is False
    assert fallback_applicability.transport_confidence == 0.5
