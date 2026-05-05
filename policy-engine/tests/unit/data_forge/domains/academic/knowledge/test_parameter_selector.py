from __future__ import annotations

import json

import duckdb
import pytest
from polisyos.data_forge.domains.academic.knowledge.parameter_selector import ParameterSelector
from polisyos.data_forge.domains.academic.knowledge.skg_query import SKGQuery
from polisyos.ir.analytics.causal_graph import CausalGraphModel, GraphType
from polisyos.ir.analytics.context import ContextProfile, IncomeLevel
from polisyos.ir.analytics.transportability import TransportabilityStatus, TransportMode


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


def _seed_transport_support(
    db_path,
    *,
    profiles: list[tuple[str, str]] | None = None,
    moderation_edges: list[str] | None = None,
    transport_targets: list[str] | None = None,
) -> None:
    con = duckdb.connect(str(db_path))
    try:
        con.execute(
            """
            CREATE TABLE ac_skg_context_profiles (
                profile_id VARCHAR,
                context_id VARCHAR
            )
            """
        )
        con.execute(
            """
            CREATE TABLE ac_skg_moderation_edges (
                moderation_id VARCHAR,
                moderator VARCHAR
            )
            """
        )
        con.execute(
            """
            CREATE TABLE ac_skg_transport_scores (
                transport_id VARCHAR,
                target_context_id VARCHAR
            )
            """
        )
        if profiles:
            con.executemany("INSERT INTO ac_skg_context_profiles VALUES (?, ?)", profiles)
        if moderation_edges:
            con.executemany(
                "INSERT INTO ac_skg_moderation_edges VALUES (?, ?)",
                [(f"m{idx}", moderator) for idx, moderator in enumerate(moderation_edges, start=1)],
            )
        if transport_targets:
            con.executemany(
                "INSERT INTO ac_skg_transport_scores VALUES (?, ?)",
                [(f"t{idx}", target) for idx, target in enumerate(transport_targets, start=1)],
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
    assert applicability.transport_status is TransportabilityStatus.IDENTIFIED
    assert applicability.transport_mode in {
        TransportMode.DIRECT,
        TransportMode.TRANSPORT_FORMULA,
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
    _seed_transport_support(
        db_path,
        profiles=[("profile_src", "SRC"), ("profile_ua", "UA")],
        transport_targets=["UA"],
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
    assert applicability.transport_confidence == 0.375
    assert applicability.uncertainty_multiplier == pytest.approx(2.5)

    assert fallback_param is None
    assert fallback_applicability.is_applicable is False
    assert fallback_applicability.transport_confidence == 0.375


def test_select_for_context_applies_transport_penalty_notes_and_uncertainty(tmp_path) -> None:
    db_path = tmp_path / "skg.duckdb"
    _seed_params(
        db_path,
        [
            (
                "p_transport",
                "fiscal_multiplier",
                "W_transport",
                json.dumps(
                    {
                        "name": "fiscal_multiplier",
                        "value": 1.2,
                        "parameter_type": "quantitative",
                        "evidence_strength": "rct",
                    }
                ),
                json.dumps(
                    {
                        "context_id": "PL",
                        "income_level": "lower_middle",
                        "institutional_quality": 0.41,
                        "post_communist": True,
                    }
                ),
            )
        ],
    )
    _seed_transport_support(
        db_path,
        profiles=[("profile_pl", "PL"), ("profile_ua", "UA")],
        moderation_edges=["fiscal_multiplier"],
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
    assert applicability.is_applicable is True
    assert applicability.transport_confidence < 0.95
    assert applicability.uncertainty_multiplier > 1.0
    assert "moderation_edges:1" in applicability.transport_notes
    assert "transport_score_unavailable" in applicability.transport_notes


def test_select_for_context_marks_context_mismatch_and_no_uncertainty(tmp_path) -> None:
    db_path = tmp_path / "skg.duckdb"
    _seed_params(
        db_path,
        [
            (
                "p_far_context",
                "fiscal_multiplier",
                "W_far",
                json.dumps(
                    {
                        "name": "fiscal_multiplier",
                        "value": 0.9,
                        "parameter_type": "quantitative",
                        "evidence_strength": "quasi_natural",
                    }
                ),
                json.dumps(
                    {
                        "context_id": "US",
                        "income_level": "high",
                        "institutional_quality": 0.95,
                        "post_communist": False,
                    }
                ),
            )
        ],
    )
    _seed_transport_support(
        db_path,
        profiles=[("profile_us", "US"), ("profile_ua", "UA")],
    )

    query = SKGQuery(db_path=db_path, index_dir=tmp_path / "idx")
    selector = ParameterSelector(query)
    target_context = ContextProfile(
        context_id="UA",
        income_level=IncomeLevel.LOWER_MIDDLE,
        institutional_quality=0.35,
        post_communist=True,
    )
    graph = CausalGraphModel(graph_type=GraphType.DAG, nodes=["fiscal_multiplier"], edges=[])

    try:
        _, applicability = selector.select_for_context(
            parameter_name="fiscal_multiplier",
            target_context=target_context,
            causal_graph=graph,
            min_transport_confidence=0.0,
        )
    finally:
        query.close()

    assert "context_mismatch" in applicability.transport_notes
    assert "no_uncertainty" in applicability.transport_notes
    assert applicability.uncertainty_multiplier > 1.5
