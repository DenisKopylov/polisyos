"""Behavioral coverage for the runtime Lex search facade bridge."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

import polisyos.lex as lex_facade
from polisyos.core.contracts.control import (
    LegalQueryGenerationIntentV1,
    LexSearchRequest,
)
from polisyos.lex.knowledge import LegalFactResult
from polisyos.runtime.http.app import create_runtime_api_app
from polisyos.runtime.http.container import RuntimeContainerOverrides
from polisyos.runtime.http.services.control.lex_pipeline import LexPipelineMixin
from tests._helpers.runtime_api.legal_search_profile_fixture import (
    build_legal_search_profile_fixture,
)


def _owner_result(*, suffix: str, similarity: float) -> LegalFactResult:
    return LegalFactResult(
        fact_id=f"fact-{suffix}",
        subject_name=f"Subject {suffix}",
        predicate=f"predicate-{suffix}",
        object_name=f"Object {suffix}",
        fact_text=f"Fact text {suffix}",
        confidence=0.91,
        norm_type="right",
        action_canon=f"action-{suffix}",
        norm_type_canon="entitlement",
        condition_text_uk=f"condition-{suffix}",
        exception_text_uk=f"exception-{suffix}",
        procedure_text_uk=f"procedure-{suffix}",
        thresholds_json='[{"operator":">=","value":1}]',
        source_quote_uk=f"quote-{suffix}",
        trust_tier="normative_fact",
        grounding_status="exact_quote",
        canonical_status="canonicalized",
        reference_resolution_status="resolved",
        structure_quality="complete",
        constraint_type_canon="eligibility",
        legal_unit_subtype="normative_rule",
        route_class="direct_norm",
        empty_spo_retry_eligible=True,
        audit_miss_prone=True,
        reference_bearing=True,
        threshold_bearing=True,
        fused_confidence=0.88,
        confidence_breakdown_json='{"source":0.9}',
        consistency_score=0.97,
        hallucination_flags_json='["reviewed"]',
        quality_band="high",
        doc_id=f"doc-{suffix}",
        doc_family_id=f"family-{suffix}",
        version_id=f"version-{suffix}",
        jurisdiction="UA",
        top_domain="labor",
        effective_from="2026-01-01",
        effective_to="2026-12-31",
        temporal_state="effective",
        temporal_resolution_status="resolved",
        temporal_source_scope="provision",
        temporal_source_kind="official_registry",
        temporal_confidence=0.99,
        temporal_provenance_json='{"source":"official_registry"}',
        doc_name=f"Document {suffix}",
        doc_reestr_code=f"code-{suffix}",
        provision_anchor=f"article-{suffix}",
        provision_citation=f"Article {suffix}",
        similarity=similarity,
    )


def _request(tmp_path: Path) -> LexSearchRequest:
    output_dir = tmp_path / "lex-search"
    output_dir.mkdir()
    (output_dir / "lex_knowledge_graph.duckdb").touch()
    return LexSearchRequest(query="worker leave", top_k=7, output_dir=str(output_dir))


class _LegacyStoreTrap:
    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise AssertionError("runtime imported internal LegalKnowledgeStore")


def _trap_legacy_store(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "polisyos.lex.knowledge.store.LegalKnowledgeStore",
        _LegacyStoreTrap,
    )


def test_runtime_container_rejects_untyped_legal_query_encoder_provider(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError, match="legal_query_encoder_provider_invalid"):
        create_runtime_api_app(
            cas_root=tmp_path / ".polisyos" / "cas",
            container_overrides=RuntimeContainerOverrides(
                legal_query_encoder_provider=lambda: object(),  # type: ignore[arg-type]
            ),
        )


def test_search_lex_graph_uses_public_graph_and_preserves_owner_results(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = _request(tmp_path)
    owner_results = [
        _owner_result(suffix="z", similarity=0.41),
        _owner_result(suffix="a", similarity=0.93),
    ]
    instances: list[Any] = []

    class _RecordingGraph:
        def __init__(
            self,
            *,
            db_path: Path,
            index_dir: Path,
            query_encoder: object | None = None,
            query_profile: tuple[object, ...] | None = None,
        ) -> None:
            self.db_path = db_path
            self.index_dir = index_dir
            self.query_encoder = query_encoder
            self.query_profile = query_profile
            self.search_calls: list[tuple[str, dict[str, object]]] = []
            self.close_count = 0
            self.query_profile_error = None
            instances.append(self)

        def text_search(self, query: str, **kwargs: object) -> list[LegalFactResult]:
            self.search_calls.append((query, kwargs))
            return owner_results

        def close(self) -> None:
            self.close_count += 1

    monkeypatch.setattr(lex_facade, "LegalKnowledgeGraph", _RecordingGraph)
    _trap_legacy_store(monkeypatch)

    response = LexPipelineMixin().search_lex_graph(request, request_id="req-lex-facade")

    assert len(instances) == 1
    graph = instances[0]
    assert graph.db_path == Path(request.output_dir) / "lex_knowledge_graph.duckdb"
    assert graph.index_dir == Path(request.output_dir)
    assert graph.search_calls == [
        (
            "worker leave",
            {
                "top_k": 7,
                "trust_tier": None,
                "include_candidates": False,
            },
        )
    ]
    assert response.query == "worker leave"
    assert response.total == 2
    assert [item.model_dump(mode="python") for item in response.results] == [
        result.model_dump(mode="python") for result in owner_results
    ]
    assert graph.close_count == 1
    assert graph.query_profile is None
    assert response.search_mode == "text"
    assert response.vector_refusal_code == "query_profile_unavailable"


def test_search_lex_graph_preserves_valid_intent_and_typed_provider_refusal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = _request(tmp_path).model_copy(
        update={
            "query_generation_intent": (
                LegalQueryGenerationIntentV1(
                    basis_kind="legal_lex_facts_embedding",
                    generation_id="a" * 32,
                    inventory_json=json.dumps(
                        {"basis": {"basis_kind": "legal_lex_facts_embedding"}},
                        sort_keys=True,
                        separators=(",", ":"),
                    ),
                ),
            )
        }
    )
    owner_results = [_owner_result(suffix="typed", similarity=0.8)]
    instances: list[Any] = []

    class _ProfilelessGraph:
        def __init__(
            self,
            *,
            db_path: Path,
            index_dir: Path,
            query_encoder: object | None = None,
            query_profile: tuple[object, ...] | None = None,
        ) -> None:
            self.query_encoder = query_encoder
            self.query_profile = query_profile
            self.close_count = 0
            self.query_profile_error = type(
                "Refusal", (), {"code": "query_encoder_assets_unavailable"}
            )()
            self.hybrid_calls: list[tuple[str, dict[str, object]]] = []
            instances.append(self)

        def hybrid_search(self, query: str, **kwargs: object) -> list[LegalFactResult]:
            self.hybrid_calls.append((query, kwargs))
            return owner_results

        def close(self) -> None:
            self.close_count += 1

    monkeypatch.setattr(lex_facade, "LegalKnowledgeGraph", _ProfilelessGraph)
    _trap_legacy_store(monkeypatch)

    response = LexPipelineMixin().search_lex_graph(request, request_id="req-typed-refusal")

    assert len(instances) == 1
    graph = instances[0]
    assert graph.query_profile is not None
    assert len(graph.query_profile) == 1
    assert graph.query_profile[0].basis_kind == "legal_lex_facts_embedding"
    assert graph.hybrid_calls == [
        (
            "worker leave",
            {"top_k": 7, "trust_tier": None, "include_candidates": False},
        )
    ]
    assert response.search_mode == "text"
    assert response.vector_refusal_code == "query_encoder_assets_unavailable"
    assert [item.fact_id for item in response.results] == ["fact-typed"]
    assert graph.close_count == 1


def test_get_lex_search_profile_reads_the_selected_fact_generation_snapshot(
    tmp_path: Path,
) -> None:
    fixture = build_legal_search_profile_fixture(tmp_path / "legal-profile")

    response = LexPipelineMixin().get_lex_search_profile(
        str(fixture.output_dir),
        request_id="req-selected-legal-profile",
    )

    assert response.status == "available"
    assert response.output_dir == str(fixture.output_dir)
    assert len(response.query_generation_intent) == 1
    intent = response.query_generation_intent[0]
    assert intent.basis_kind == "legal_lex_facts_embedding"
    assert len(intent.generation_id) == 32
    inventory = json.loads(intent.inventory_json)
    assert inventory["generation_id"] == intent.generation_id
    assert inventory["basis"]["basis_kind"] == intent.basis_kind


def test_get_lex_search_profile_returns_typed_refusal_without_a_selected_generation(
    tmp_path: Path,
) -> None:
    response = LexPipelineMixin().get_lex_search_profile(
        str(tmp_path / "missing-legal-profile"),
        request_id="req-missing-legal-profile",
    )

    assert response.status == "refused"
    assert response.refusal_code == "selected_generation_unavailable"


def test_search_lex_graph_rejects_malformed_intent_and_keeps_text_results(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = _request(tmp_path).model_copy(
        update={
            "query_generation_intent": (
                LegalQueryGenerationIntentV1(
                    basis_kind="legal_lex_facts_embedding",
                    generation_id="a" * 32,
                    inventory_json="{not-json",
                ),
            )
        }
    )
    owner_results = [_owner_result(suffix="text", similarity=0.7)]

    class _TextGraph:
        def __init__(
            self,
            *,
            db_path: Path,
            index_dir: Path,
            query_encoder: object | None = None,
            query_profile: tuple[object, ...] | None = None,
        ) -> None:
            self.query_encoder = query_encoder
            self.query_profile = query_profile
            self.close_count = 0
            self.text_calls: list[tuple[str, dict[str, object]]] = []

        def text_search(self, query: str, **kwargs: object) -> list[LegalFactResult]:
            self.text_calls.append((query, kwargs))
            return owner_results

        def close(self) -> None:
            self.close_count += 1

    graph: _TextGraph | None = None

    def _graph_factory(**kwargs: object) -> _TextGraph:
        nonlocal graph
        graph = _TextGraph(**kwargs)  # type: ignore[arg-type]
        return graph

    monkeypatch.setattr(lex_facade, "LegalKnowledgeGraph", _graph_factory)
    _trap_legacy_store(monkeypatch)

    response = LexPipelineMixin().search_lex_graph(request, request_id="req-malformed-intent")

    assert graph is not None
    assert graph.query_profile is None
    assert graph.text_calls == [
        (
            "worker leave",
            {"top_k": 7, "trust_tier": None, "include_candidates": False},
        )
    ]
    assert response.search_mode == "text"
    assert response.vector_refusal_code == "query_profile_malformed"
    assert [item.fact_id for item in response.results] == ["fact-text"]
    assert graph.close_count == 1


def test_search_lex_graph_treats_empty_present_intent_as_malformed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = _request(tmp_path).model_copy(update={"query_generation_intent": ()})
    owner_results = [_owner_result(suffix="empty-intent", similarity=0.6)]

    class _TextGraph:
        def __init__(
            self,
            *,
            db_path: Path,
            index_dir: Path,
            query_encoder: object | None = None,
            query_profile: tuple[object, ...] | None = None,
        ) -> None:
            self.query_profile = query_profile
            self.close_count = 0

        def text_search(self, query: str, **kwargs: object) -> list[LegalFactResult]:
            del query, kwargs
            return owner_results

        def close(self) -> None:
            self.close_count += 1

    graph: _TextGraph | None = None

    def _graph_factory(**kwargs: object) -> _TextGraph:
        nonlocal graph
        graph = _TextGraph(**kwargs)  # type: ignore[arg-type]
        return graph

    monkeypatch.setattr(lex_facade, "LegalKnowledgeGraph", _graph_factory)
    _trap_legacy_store(monkeypatch)

    response = LexPipelineMixin().search_lex_graph(request, request_id="req-empty-intent")

    assert graph is not None
    assert graph.query_profile is None
    assert graph.close_count == 1
    assert response.search_mode == "text"
    assert response.vector_refusal_code == "query_profile_malformed"
    assert [item.fact_id for item in response.results] == ["fact-empty-intent"]


def test_search_lex_graph_reports_malformed_present_intent_without_database(
    tmp_path: Path,
) -> None:
    request = LexSearchRequest(
        query="worker leave",
        top_k=7,
        output_dir=str(tmp_path),
        query_generation_intent=(),
    )

    response = LexPipelineMixin().search_lex_graph(request, request_id="req-empty-no-db")

    assert response.search_mode == "text"
    assert response.vector_refusal_code == "query_profile_malformed"
    assert response.results == []


def test_search_lex_graph_degrades_known_error_and_closes_graph(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = _request(tmp_path)
    instances: list[Any] = []

    class _FailingGraph:
        def __init__(
            self,
            *,
            db_path: Path,
            index_dir: Path,
            query_encoder: object | None = None,
            query_profile: tuple[object, ...] | None = None,
        ) -> None:
            self.query_encoder = query_encoder
            self.close_count = 0
            instances.append(self)

        def text_search(self, query: str, **kwargs: object) -> list[LegalFactResult]:
            raise RuntimeError("owner search unavailable")

        def close(self) -> None:
            self.close_count += 1

    monkeypatch.setattr(lex_facade, "LegalKnowledgeGraph", _FailingGraph)
    _trap_legacy_store(monkeypatch)

    response = LexPipelineMixin().search_lex_graph(request, request_id="req-known-error")

    assert response.query == "worker leave"
    assert response.results == []
    assert response.total == 0
    assert response.search_mode == "text"
    assert response.vector_refusal_code == "lex_search_failed"
    assert len(instances) == 1
    assert instances[0].close_count == 1


def test_search_lex_graph_propagates_unknown_error_and_closes_graph_in_finally(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _SentinelSearchError(Exception):
        pass

    request = _request(tmp_path)
    instances: list[Any] = []

    class _FailingGraph:
        def __init__(
            self,
            *,
            db_path: Path,
            index_dir: Path,
            query_encoder: object | None = None,
            query_profile: tuple[object, ...] | None = None,
        ) -> None:
            self.query_encoder = query_encoder
            self.close_count = 0
            instances.append(self)

        def text_search(self, query: str, **kwargs: object) -> list[LegalFactResult]:
            raise _SentinelSearchError("unknown owner failure")

        def close(self) -> None:
            self.close_count += 1

    monkeypatch.setattr(lex_facade, "LegalKnowledgeGraph", _FailingGraph)
    _trap_legacy_store(monkeypatch)

    with pytest.raises(_SentinelSearchError, match="unknown owner failure"):
        LexPipelineMixin().search_lex_graph(request, request_id="req-unknown-error")

    assert len(instances) == 1
    assert instances[0].close_count == 1
