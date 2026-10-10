"""Tests for DatasetCatalogStore (DuckDB read-only queries)."""

from __future__ import annotations

import sys
import tempfile
import types
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event

import duckdb
import numpy as np

from polisyos.data_forge.domains.catalog.batch.embedder import build_hnsw_index
from polisyos.data_forge.domains.catalog.batch.graph_builder import build_graph
from polisyos.data_forge.domains.catalog.knowledge.search import DatasetCatalogGraph, SearchFilters
from polisyos.data_forge.domains.catalog.knowledge.store import DatasetCatalogStore
from polisyos.data_forge.domains.catalog.knowledge.types import (
    DatasetCoverage,
    DatasetQuality,
    DatasetRecord,
    DistributionRecord,
)
from polisyos.scientist.agent.knowledge_tools import KnowledgeToolkit
from polisyos.scientist.agent.tools.knowledge_tools_adapter import build_knowledge_tool_registry


class _CatalogTokenizer:
    def get_vocab(self) -> dict[str, int]:
        return {"[UNK]": 0, "catalog": 1}


class _CatalogEncoder:
    def __init__(
        self,
        weight: tuple[float, float] = (1.0, 0.0),
        *,
        device: str = "cpu",
        output_dimension: int | None = None,
    ) -> None:
        self.weight = np.asarray(weight, dtype=np.float32)
        self.tokenizer = _CatalogTokenizer()
        self.config = {"hidden_size": 2}
        self.device = device
        self.output_dimension = output_dimension
        self.encode_calls = 0

    def state_dict(self) -> dict[str, np.ndarray]:
        return {"encoder.weight": self.weight.copy()}

    def modules(self) -> tuple[_CatalogEncoder, ...]:
        return (self,)

    def get_config_dict(self) -> dict[str, object]:
        return dict(self.config)

    def get_sentence_embedding_dimension(self) -> int:
        return self.output_dimension or int(self.weight.size)

    def encode(self, texts: list[str], **_kwargs: object) -> np.ndarray:
        self.encode_calls += 1
        return np.vstack([self.weight.copy() for _text in texts])


def _build_test_db(tmpdir: str) -> Path:
    db_path = Path(tmpdir) / "test_catalog.duckdb"
    records = [
        DatasetRecord(
            id="ds-gdp",
            title="GDP per capita by country",
            description="Annual GDP per capita, World Bank data",
            publisher="World Bank",
            themes=["economics"],
            keywords=["GDP", "per capita"],
            variables=["NY.GDP.PCAP.CD"],
            polisyos_metrics=["gdp", "avg_income"],
            spatial="WORLD",
            source_portal="worldbank",
            formats=["JSON"],
            distributions=[
                DistributionRecord(
                    id="dist-gdp-1",
                    url="https://api.worldbank.org/v2/data",
                    format="JSON",
                    connector_type="worldbank.wdi",
                    connector_params={"indicator_id": "NY.GDP.PCAP.CD"},
                    source_locator="NY.GDP.PCAP.CD",
                    parser_supported=True,
                    machine_readable=True,
                    profile_id="worldbank_wdi",
                    quality_score=0.9,
                ),
            ],
            source="worldbank",
            source_dataset_id="NY.GDP.PCAP.CD",
            execution_tier="fetchable",
            coverage=DatasetCoverage(
                countries=["UA", "PL"], time_start="2018", time_end="2024", granularity="annual"
            ),
            quality=DatasetQuality(execution_readiness_score=0.91),
            preferred_distribution_id="dist-gdp-1",
        ),
        DatasetRecord(
            id="ds-unemp",
            title="Unemployment rate, annual",
            description="Unemployment by country",
            publisher="ILO",
            variables=["SL.UEM.TOTL.ZS"],
            polisyos_metrics=["unemployment_rate"],
            source_portal="worldbank",
            formats=["CSV"],
            source="ilo",
            execution_tier="transport_ready",
            coverage=DatasetCoverage(
                countries=["DE"], time_start="2019", time_end="2023", granularity="annual"
            ),
            quality=DatasetQuality(execution_readiness_score=0.74),
            distributions=[],
        ),
    ]
    build_graph(records=iter(records), db_path=db_path)
    return db_path


def test_catalog_read_api_exports_shared_generation_currentness_helpers() -> None:
    from polisyos.data_forge.read_api import catalog

    expected = {
        "CatalogEmbeddingProfile",
        "CatalogQueryGenerationContext",
        "EmbeddingGenerationRef",
        "embedding_generation_matches_encoder",
        "generation_basis_matches_members",
        "resolve_embedding_generation",
    }
    assert expected <= set(catalog.__all__)
    assert callable(catalog.embedding_generation_matches_encoder)


def test_missing_overlay_preserves_partial_legacy_catalog_reads() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "legacy-catalog.duckdb"
        con = duckdb.connect(str(db_path))
        try:
            con.execute(
                "CREATE TABLE ds_datasets (id VARCHAR, title VARCHAR, polisyos_metrics VARCHAR[])"
            )
            con.execute(
                "INSERT INTO ds_datasets VALUES ('legacy-ds', 'Legacy GDP', ['legacy_gdp'])"
            )
        finally:
            con.close()

        store = DatasetCatalogStore(
            db_path,
            Path(tmpdir),
            overlay_path=Path(tmpdir) / "missing-overlay.duckdb",
        )
        try:
            results = store.find_by_polisyos_metric("legacy_gdp")
            assert [result.id for result in results] == ["legacy-ds"]
        finally:
            store.close()


def test_search_by_text() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = _build_test_db(tmpdir)
        index_dir = Path(tmpdir)  # No HNSW for text-only test
        store = DatasetCatalogStore(db_path, index_dir)
        try:
            results = store.search_by_text("GDP", top_k=10)
            assert len(results) >= 1
            assert any("GDP" in r.title for r in results)
        finally:
            store.close()


def test_vector_index_rejects_same_id_with_changed_projected_content(
    monkeypatch, tmp_path: Path
) -> None:
    db_path = tmp_path / "currentness.duckdb"
    index_dir = tmp_path / "index"
    build_graph(
        records=iter(
            [
                DatasetRecord(
                    id="ds-currentness",
                    title="Original GDP series",
                    description="Original series description",
                    keywords=["gdp"],
                    variables=["gross domestic product"],
                )
            ]
        ),
        db_path=db_path,
    )
    assert (
        build_hnsw_index(
            db_path=db_path,
            index_dir=index_dir,
            embedding_dimension=2,
            encoder=_CatalogEncoder(),
        )
        == 1
    )
    selector_path = index_dir / "embedding_generation.json"
    selector_before = selector_path.read_bytes()

    store = DatasetCatalogStore(db_path, index_dir)
    try:
        assert store.has_vector_index()
        assert [
            result.id for result in store.search_by_vector(np.asarray([1.0, 0.0], dtype=np.float32))
        ] == ["ds-currentness"]
    finally:
        store.close()

    with duckdb.connect(str(db_path)) as con:
        con.execute(
            "UPDATE ds_datasets SET title = 'Changed population series', "
            "description = 'Population data', keywords = ['population'], "
            "variables = ['population'] "
            "WHERE id = 'ds-currentness'"
        )
        con.execute("CHECKPOINT")

    assert selector_path.read_bytes() == selector_before
    fresh_store = DatasetCatalogStore(db_path, index_dir)
    try:
        assert not fresh_store.has_vector_index()
        assert fresh_store.search_by_vector(np.asarray([1.0, 0.0], dtype=np.float32)) == []
        assert fresh_store.vector_index_refusal_reason == "catalog_material_basis_mismatch"
    finally:
        fresh_store.close()

    monkeypatch.setitem(
        sys.modules,
        "sentence_transformers",
        types.SimpleNamespace(SentenceTransformer=lambda *_args, **_kwargs: _CatalogEncoder()),
    )
    graph = DatasetCatalogGraph(db_path, index_dir)
    try:
        fallback_results = graph.search_datasets("original GDP series", top_k=1, explain=True)
        assert fallback_results
        assert all(
            result.search_explanation is not None
            and result.search_explanation["vector_score"] == 0
            and result.search_explanation["vector_search_refusal"]
            == "catalog_material_basis_mismatch"
            for result in fallback_results
        )
    finally:
        graph.close()


def test_graph_rejects_query_encoder_assets_mismatched_with_selected_generation(
    monkeypatch, tmp_path: Path
) -> None:
    db_path = tmp_path / "encoder-currentness.duckdb"
    index_dir = tmp_path / "index"
    build_graph(
        records=iter(
            [
                DatasetRecord(
                    id="ds-encoder-currentness",
                    title="Original GDP series",
                    description="Original series description",
                    keywords=["gdp"],
                    variables=["gross domestic product"],
                )
            ]
        ),
        db_path=db_path,
    )
    producer_encoder = _CatalogEncoder()
    assert (
        build_hnsw_index(
            db_path=db_path,
            index_dir=index_dir,
            embedding_dimension=2,
            encoder=producer_encoder,
        )
        == 1
    )
    selector_path = index_dir / "embedding_generation.json"
    selector_before = selector_path.read_bytes()

    matching_encoder = _CatalogEncoder()
    monkeypatch.setitem(
        sys.modules,
        "sentence_transformers",
        types.SimpleNamespace(
            SentenceTransformer=lambda *_args, **_kwargs: matching_encoder,
        ),
    )
    matching_graph = DatasetCatalogGraph(db_path, index_dir)
    try:
        matching_results = matching_graph.search_datasets("gdp series", top_k=1, explain=True)
        assert matching_results
        assert matching_results[0].search_explanation is not None
        assert matching_results[0].search_explanation["vector_score"] > 0
        matching_encoder.weight[:] = np.asarray([0.0, 1.0], dtype=np.float32)
        calls_before_mutation = matching_encoder.encode_calls
        cached_fallback = matching_graph.search_datasets("gdp series", top_k=1, explain=True)
        assert cached_fallback
        assert matching_encoder.encode_calls == calls_before_mutation
        assert matching_graph.last_query_metrics is not None
        assert (
            matching_graph.last_query_metrics.vector_search_refusal
            == "query_encoder_generation_intent_mismatch"
        )
        assert cached_fallback[0].search_explanation is not None
        assert cached_fallback[0].search_explanation["vector_search_refusal"] == (
            "query_encoder_generation_intent_mismatch"
        )
    finally:
        matching_graph.close()

    incompatible_encoder = _CatalogEncoder(weight=(0.0, 1.0))
    monkeypatch.setitem(
        sys.modules,
        "sentence_transformers",
        types.SimpleNamespace(
            SentenceTransformer=lambda *_args, **_kwargs: incompatible_encoder,
        ),
    )
    incompatible_graph = DatasetCatalogGraph(db_path, index_dir)
    try:
        fallback_results = incompatible_graph.search_datasets("gdp series", top_k=1, explain=True)
        assert fallback_results
        assert incompatible_encoder.encode_calls == 0
        assert incompatible_graph.last_query_metrics is not None
        assert (
            incompatible_graph.last_query_metrics.vector_search_refusal
            == "query_encoder_generation_intent_mismatch"
        )
        assert fallback_results[0].search_explanation is not None
        assert fallback_results[0].search_explanation["vector_search_refusal"] == (
            "query_encoder_generation_intent_mismatch"
        )
    finally:
        incompatible_graph.close()

    assert selector_path.read_bytes() == selector_before


def test_toolkit_reports_selected_generation_refusal_without_explanation(
    monkeypatch, tmp_path: Path
) -> None:
    db_path = tmp_path / "toolkit-currentness.duckdb"
    index_dir = tmp_path / "index"
    build_graph(
        records=iter(
            [
                DatasetRecord(
                    id="ds-toolkit-currentness",
                    title="GDP series",
                    description="Annual GDP data",
                    keywords=["gdp"],
                    variables=["gross domestic product"],
                )
            ]
        ),
        db_path=db_path,
    )
    producer_encoder = _CatalogEncoder()
    assert (
        build_hnsw_index(
            db_path=db_path,
            index_dir=index_dir,
            embedding_dimension=2,
            encoder=producer_encoder,
        )
        == 1
    )
    selector_path = index_dir / "embedding_generation.json"
    selector_before = selector_path.read_bytes()

    compatible_encoder = _CatalogEncoder()
    monkeypatch.setitem(
        sys.modules,
        "sentence_transformers",
        types.SimpleNamespace(
            SentenceTransformer=lambda *_args, **_kwargs: compatible_encoder,
        ),
    )
    compatible_graph = DatasetCatalogGraph(db_path, index_dir)
    try:
        compatible_toolkit = KnowledgeToolkit(dataset_catalog=compatible_graph)
        compatible_results = compatible_toolkit.search_datasets("gdp series", top_k=1)
        assert compatible_results
        assert compatible_results[0].search_mode == "vector"
        assert compatible_results[0].vector_refusal_code is None
        selected_context = compatible_results[0].query_generation_context
        assert selected_context is not None
        assert selected_context.state == "selected"
        assert selected_context.selected_generation_id
        assert selected_context.selected_profile is not None
        assert selected_context.reader_profile is not None
        assert (
            selected_context.selected_profile.encoder_asset_identity
            == selected_context.reader_profile.encoder_asset_identity
        )
        actual_generation = compatible_graph._store._current_dataset_generation()
        assert actual_generation is not None
        assert selected_context.selected_generation_id == actual_generation.generation_id
    finally:
        compatible_graph.close()

    incompatible_encoder = _CatalogEncoder(weight=(0.0, 1.0))
    monkeypatch.setitem(
        sys.modules,
        "sentence_transformers",
        types.SimpleNamespace(
            SentenceTransformer=lambda *_args, **_kwargs: incompatible_encoder,
        ),
    )
    incompatible_graph = DatasetCatalogGraph(db_path, index_dir)
    try:
        toolkit = KnowledgeToolkit(dataset_catalog=incompatible_graph)
        results = toolkit.search_datasets("gdp series", top_k=1)

        assert results
        assert results[0].search_mode == "text"
        assert results[0].vector_refusal_code == "query_encoder_generation_intent_mismatch"
        assert results[0].search_explanation is None
        refused_context = results[0].query_generation_context
        assert refused_context is not None
        assert refused_context.state == "refused"
        assert refused_context.selected_generation_id
        assert refused_context.selected_profile is not None
        assert refused_context.reader_profile is not None
        assert (
            refused_context.selected_profile.encoder_asset_identity
            != refused_context.reader_profile.encoder_asset_identity
        )
        assert incompatible_encoder.encode_calls == 0
        context = toolkit.format_dataset_context(results)
        assert "query_encoder_generation_intent_mismatch" in context
        assert "remain candidates" in context
        assert incompatible_graph.last_query_metrics is not None
        assert incompatible_graph.last_query_metrics.search_mode == "text"

        tool_result = build_knowledge_tool_registry(toolkit).execute(
            "search_datasets",
            {"query": "gdp series", "top_k": 1},
        )
        assert tool_result.error is None
        assert tool_result.result["results"][0]["search_mode"] == "text"
        assert tool_result.result["results"][0]["vector_refusal_code"] == (
            "query_encoder_generation_intent_mismatch"
        )
        assert tool_result.result["search_mode"] == "text"
        assert tool_result.result["vector_refusal_code"] == (
            "query_encoder_generation_intent_mismatch"
        )
        assert tool_result.result["query_generation_context"]["state"] == "refused"
        assert tool_result.result["query_generation_context"]["selected_generation_id"]
    finally:
        incompatible_graph.close()

    wrong_profile_graph = DatasetCatalogGraph(
        db_path,
        index_dir,
        embedding_model="different-model",
    )
    try:
        wrong_profile_results = KnowledgeToolkit(
            dataset_catalog=wrong_profile_graph
        ).search_datasets("gdp series", top_k=1)
        assert wrong_profile_results
        assert wrong_profile_results[0].search_mode == "text"
        assert wrong_profile_results[0].vector_refusal_code == "query_embedding_model_mismatch"
        assert wrong_profile_results[0].search_explanation is None
        assert wrong_profile_results[0].query_generation_context is not None
        assert wrong_profile_results[0].query_generation_context.state == "refused"
    finally:
        wrong_profile_graph.close()

    assert selector_path.read_bytes() == selector_before


def test_registered_search_tool_keeps_refusal_for_empty_query_results(
    monkeypatch, tmp_path: Path
) -> None:
    db_path = tmp_path / "empty-query-status.duckdb"
    index_dir = tmp_path / "index"
    build_graph(
        records=iter(
            [
                DatasetRecord(
                    id="ds-empty-query-status",
                    title="GDP series",
                    description="Annual GDP data",
                    keywords=["gdp"],
                    variables=["gross domestic product"],
                )
            ]
        ),
        db_path=db_path,
    )
    assert (
        build_hnsw_index(
            db_path=db_path,
            index_dir=index_dir,
            embedding_dimension=2,
            encoder=_CatalogEncoder(),
        )
        == 1
    )
    selector_path = index_dir / "embedding_generation.json"
    selector_before = selector_path.read_bytes()
    query = "unmatched planetary query"

    absent_graph = DatasetCatalogGraph(db_path, tmp_path / "no-selected-generation")
    try:
        absent_tool_result = build_knowledge_tool_registry(
            KnowledgeToolkit(dataset_catalog=absent_graph)
        ).execute("search_datasets", {"query": query, "top_k": 1})
        assert absent_tool_result.error is None
        assert absent_tool_result.result["results"] == []
        assert absent_tool_result.result["search_mode"] == "text"
        assert absent_tool_result.result["vector_refusal_code"] == (
            "selected_generation_unavailable"
        )
        assert absent_tool_result.result["query_generation_context"] == {"state": "absent"}
    finally:
        absent_graph.close()

    refusing_encoder = _CatalogEncoder(weight=(0.0, 1.0))
    monkeypatch.setitem(
        sys.modules,
        "sentence_transformers",
        types.SimpleNamespace(SentenceTransformer=lambda *_args, **_kwargs: refusing_encoder),
    )
    refusing_graph = DatasetCatalogGraph(db_path, index_dir)
    try:
        toolkit = KnowledgeToolkit(dataset_catalog=refusing_graph)
        assert toolkit.search_datasets(query, top_k=1) == []

        tool_result = build_knowledge_tool_registry(toolkit).execute(
            "search_datasets",
            {"query": query, "top_k": 1},
        )
        assert tool_result.error is None
        assert tool_result.result["results"] == []
        assert tool_result.result["search_mode"] == "text"
        assert tool_result.result["vector_refusal_code"] == (
            "query_encoder_generation_intent_mismatch"
        )
        assert tool_result.result["query_generation_context"]["state"] == "refused"
        assert tool_result.result["query_generation_context"]["selected_generation_id"]
        refused_context = tool_result.result["query_generation_context"]
        assert (
            refused_context["selected_profile"]["encoder_asset_identity"]
            != (refused_context["reader_profile"]["encoder_asset_identity"])
        )
        assert refusing_encoder.encode_calls == 0
    finally:
        refusing_graph.close()

    compatible_encoder = _CatalogEncoder()
    monkeypatch.setitem(
        sys.modules,
        "sentence_transformers",
        types.SimpleNamespace(SentenceTransformer=lambda *_args, **_kwargs: compatible_encoder),
    )
    compatible_graph = DatasetCatalogGraph(db_path, index_dir)
    try:
        compatible_tool_result = build_knowledge_tool_registry(
            KnowledgeToolkit(dataset_catalog=compatible_graph)
        ).execute(
            "search_datasets",
            {"query": query, "top_k": 1, "domain": "no-such-theme"},
        )
        assert compatible_tool_result.error is None
        assert compatible_tool_result.result["results"] == []
        assert compatible_tool_result.result["search_mode"] == "vector"
        assert "vector_refusal_code" not in compatible_tool_result.result
        assert compatible_tool_result.result["query_generation_context"]["state"] == "selected"
        assert compatible_tool_result.result["query_generation_context"]["selected_generation_id"]
        compatible_context = compatible_tool_result.result["query_generation_context"]
        assert (
            compatible_context["selected_profile"]["encoder_asset_identity"]
            == (compatible_context["reader_profile"]["encoder_asset_identity"])
        )
        assert compatible_encoder.encode_calls > 0
    finally:
        compatible_graph.close()

    assert selector_path.read_bytes() == selector_before


def test_legacy_empty_search_remains_limited_with_unknown_generation_context() -> None:
    class LegacyCatalog:
        def search_datasets(
            self,
            _query: str,
            *,
            domain_filter: str | None = None,
            top_k: int = 10,
        ) -> list[object]:
            del domain_filter, top_k
            return []

    toolkit = KnowledgeToolkit(dataset_catalog=LegacyCatalog())  # type: ignore[arg-type]
    response = toolkit.search_datasets_with_status("empty legacy response")

    assert response.results == []
    assert response.search_mode is None
    assert response.vector_refusal_code is None
    assert response.limitation_code == "query_status_unavailable"
    assert response.query_generation_context.state == "unknown"


def test_overlapping_queries_keep_their_own_encoder_status(monkeypatch, tmp_path: Path) -> None:
    class ConcurrentCatalogEncoder(_CatalogEncoder):
        def __init__(self) -> None:
            super().__init__()
            self.normal_query_started = Event()
            self.release_normal_query = Event()

        def encode(self, texts: list[str], **kwargs: object) -> np.ndarray:
            if texts == ["normal concurrent query"]:
                self.normal_query_started.set()
                if not self.release_normal_query.wait(timeout=5):
                    raise TimeoutError("normal query test gate timed out")
            if texts == ["failing concurrent query"]:
                raise RuntimeError("controlled query encoder failure")
            return super().encode(texts, **kwargs)

    db_path = tmp_path / "concurrent-query-status.duckdb"
    index_dir = tmp_path / "index"
    build_graph(
        records=iter(
            [
                DatasetRecord(
                    id="ds-concurrent-query-status",
                    title="GDP series",
                    description="Annual GDP data",
                    keywords=["gdp"],
                    variables=["gross domestic product"],
                )
            ]
        ),
        db_path=db_path,
    )
    encoder = ConcurrentCatalogEncoder()
    assert (
        build_hnsw_index(
            db_path=db_path,
            index_dir=index_dir,
            embedding_dimension=2,
            encoder=encoder,
        )
        == 1
    )
    monkeypatch.setitem(
        sys.modules,
        "sentence_transformers",
        types.SimpleNamespace(SentenceTransformer=lambda *_args, **_kwargs: encoder),
    )
    graph = DatasetCatalogGraph(db_path, index_dir)
    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            normal_call = executor.submit(
                graph.search_datasets_with_status, "normal concurrent query"
            )
            assert encoder.normal_query_started.wait(timeout=5)

            failing_call_started = Event()

            def _run_failing_query():
                failing_call_started.set()
                return graph.search_datasets_with_status("failing concurrent query")

            failing_call = executor.submit(_run_failing_query)
            assert failing_call_started.wait(timeout=5)
            encoder.release_normal_query.set()
            normal_response = normal_call.result(timeout=5)
            failing_response = failing_call.result(timeout=5)

        assert normal_response.search_mode == "vector"
        assert normal_response.vector_refusal_code is None
        assert failing_response.search_mode == "text"
        assert failing_response.vector_refusal_code == "query_encoder_execution_failed"
    finally:
        encoder.release_normal_query.set()
        graph.close()


def test_graph_names_model_device_and_dimension_generation_refusals(
    monkeypatch, tmp_path: Path
) -> None:
    db_path = tmp_path / "intent-currentness.duckdb"
    index_dir = tmp_path / "index"
    build_graph(
        records=iter(
            [
                DatasetRecord(
                    id="ds-intent-currentness",
                    title="GDP series",
                    description="Annual GDP data",
                    keywords=["gdp"],
                    variables=["gross domestic product"],
                )
            ]
        ),
        db_path=db_path,
    )
    assert (
        build_hnsw_index(
            db_path=db_path,
            index_dir=index_dir,
            embedding_dimension=2,
            encoder=_CatalogEncoder(),
        )
        == 1
    )

    cases = (
        (
            _CatalogEncoder(device="mps"),
            "intfloat/multilingual-e5-large",
            "query_encoder_generation_intent_mismatch",
        ),
        (
            _CatalogEncoder(output_dimension=3),
            "intfloat/multilingual-e5-large",
            "query_encoder_generation_intent_mismatch",
        ),
        (_CatalogEncoder(), "different-model", "query_embedding_model_mismatch"),
    )
    for encoder, model, expected_refusal in cases:
        monkeypatch.setitem(
            sys.modules,
            "sentence_transformers",
            types.SimpleNamespace(
                SentenceTransformer=lambda *_args, _encoder=encoder, **_kwargs: _encoder,
            ),
        )
        graph = DatasetCatalogGraph(db_path, index_dir, embedding_model=model)
        try:
            fallback_results = graph.search_datasets("gdp series", top_k=1, explain=True)
            assert fallback_results
            assert encoder.encode_calls == 0
            assert graph.last_query_metrics is not None
            assert graph.last_query_metrics.vector_search_refusal == expected_refusal
            assert fallback_results[0].search_explanation is not None
            assert fallback_results[0].search_explanation["vector_search_refusal"] == (
                expected_refusal
            )
        finally:
            graph.close()


def test_graph_exposes_legacy_flat_generation_text_fallback(monkeypatch, tmp_path: Path) -> None:
    db_path = tmp_path / "legacy-currentness.duckdb"
    index_dir = tmp_path / "index"
    build_graph(
        records=iter(
            [
                DatasetRecord(
                    id="ds-legacy-currentness",
                    title="GDP series",
                    description="Annual GDP data",
                    keywords=["gdp"],
                    variables=["gross domestic product"],
                )
            ]
        ),
        db_path=db_path,
    )
    assert (
        build_hnsw_index(
            db_path=db_path,
            index_dir=index_dir,
            embedding_dimension=2,
            encoder=_CatalogEncoder(),
        )
        == 1
    )
    (index_dir / "embedding_generation.json").unlink()
    assert (index_dir / "ds_dataset_embeddings.npz").is_file()
    assert (index_dir / "ds_dataset_index.hnsw").is_file()

    def reject_encoder_load(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("legacy flat vectors must not load a query encoder")

    monkeypatch.setitem(
        sys.modules,
        "sentence_transformers",
        types.SimpleNamespace(SentenceTransformer=reject_encoder_load),
    )
    graph = DatasetCatalogGraph(db_path, index_dir)
    try:
        results = graph.search_datasets("gdp series", top_k=1, explain=True)
        assert results
        assert results[0].id == "ds-legacy-currentness"
        assert graph.last_query_metrics is not None
        assert (
            graph.last_query_metrics.vector_search_refusal
            == "legacy_generation_requires_selected_complete_basis"
        )
        assert results[0].search_explanation is not None
        assert results[0].search_explanation["vector_search_refusal"] == (
            "legacy_generation_requires_selected_complete_basis"
        )
    finally:
        graph.close()


def test_find_by_polisyos_metric() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = _build_test_db(tmpdir)
        index_dir = Path(tmpdir)
        store = DatasetCatalogStore(db_path, index_dir)
        try:
            results = store.find_by_polisyos_metric("gdp")
            assert len(results) >= 1
            assert "gdp" in results[0].polisyos_metrics
        finally:
            store.close()


def test_resolve_metric_bindings() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = _build_test_db(tmpdir)
        index_dir = Path(tmpdir)
        store = DatasetCatalogStore(db_path, index_dir)
        try:
            bindings = store.resolve_metric_bindings("gdp")
            assert len(bindings) == 1
            assert bindings[0].request_dataset_id == "NY.GDP.PCAP.CD"
            assert bindings[0].connector_id == "worldbank.wdi"
        finally:
            store.close()


def test_resolve_metric_bindings_prefers_transport_ready_and_schema_ready() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = _build_test_db(tmpdir)
        index_dir = Path(tmpdir)
        con = duckdb.connect(str(db_path))
        try:
            con.execute(
                "INSERT INTO ds_datasets (id, source, title, execution_tier, preferred_distribution_id) "
                "VALUES ('ds-gdp-alt', 'oecd', 'GDP alt', 'transport_ready', 'dist-gdp-alt')"
            )
            con.execute(
                "INSERT INTO ds_distributions (id, dataset_id, connector_type, source_locator, profile_id, parser_supported, machine_readable, quality_score) "
                "VALUES ('dist-gdp-alt', 'ds-gdp-alt', 'sdmx.source', 'GDP_ALT', 'oecd_sdmx', TRUE, TRUE, 0.9)"
            )
            con.execute("DELETE FROM ds_metric_bindings WHERE metric_id = 'gdp'")
            con.executemany(
                "INSERT INTO ds_metric_bindings "
                "(metric_id, dataset_id, distribution_id, connector_id, profile_id, request_dataset_id, confidence, default_filters, execution_tier, source) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    (
                        "gdp",
                        "ds-gdp",
                        "dist-gdp-1",
                        "worldbank.wdi",
                        "worldbank_wdi",
                        "NY.GDP.PCAP.CD",
                        0.99,
                        "{}",
                        "fetchable",
                        "worldbank",
                    ),
                    (
                        "gdp",
                        "ds-gdp-alt",
                        "dist-gdp-alt",
                        "sdmx.source",
                        "oecd_sdmx",
                        "GDP_ALT",
                        0.70,
                        "{}",
                        "transport_ready",
                        "oecd",
                    ),
                ],
            )
            con.execute(
                "INSERT INTO ds_schema_profiles "
                "(distribution_id, dataset_id, columns_json, inferred_time_column, inferred_geography_column, inferred_value_columns, sample_row_count, preview_sample_hash, inference_mode, parser_mode, format_notes_json) "
                "VALUES ('dist-gdp-alt', 'ds-gdp-alt', '[]', 'year', 'country_code', ['value'], 10, 'hash', 'preview', 'preview', '{}')"
            )
            con.execute("CHECKPOINT")
        finally:
            con.close()

        store = DatasetCatalogStore(db_path, index_dir)
        try:
            bindings = store.resolve_metric_bindings("gdp")
            assert len(bindings) >= 2
            assert bindings[0].catalog_dataset_id == "ds-gdp-alt"
            assert bindings[0].execution_tier == "transport_ready"
        finally:
            store.close()


def test_find_by_variables() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = _build_test_db(tmpdir)
        index_dir = Path(tmpdir)
        store = DatasetCatalogStore(db_path, index_dir)
        try:
            results = store.find_by_variables(["NY.GDP.PCAP.CD"])
            assert len(results) >= 1
        finally:
            store.close()


def test_find_by_variables_empty() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = _build_test_db(tmpdir)
        index_dir = Path(tmpdir)
        store = DatasetCatalogStore(db_path, index_dir)
        try:
            results = store.find_by_variables([])
            assert results == []
        finally:
            store.close()


def test_get_connector_params() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = _build_test_db(tmpdir)
        index_dir = Path(tmpdir)
        store = DatasetCatalogStore(db_path, index_dir)
        try:
            connector = store.get_connector_params("ds-gdp")
            assert connector is not None
            assert connector["type"] == "worldbank.wdi"
            assert connector["dataset_id"] == "NY.GDP.PCAP.CD"
        finally:
            store.close()


def test_get_connector_params_missing() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = _build_test_db(tmpdir)
        index_dir = Path(tmpdir)
        store = DatasetCatalogStore(db_path, index_dir)
        try:
            connector = store.get_connector_params("nonexistent-id")
            assert connector is None
        finally:
            store.close()


def test_get_distributions() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = _build_test_db(tmpdir)
        index_dir = Path(tmpdir)
        store = DatasetCatalogStore(db_path, index_dir)
        try:
            dists = store.get_distributions("ds-gdp")
            assert len(dists) == 1
            assert dists[0].connector_type == "worldbank.wdi"
            assert dists[0].parser_supported is True
        finally:
            store.close()


def test_resolve_fetch_target() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = _build_test_db(tmpdir)
        index_dir = Path(tmpdir)
        store = DatasetCatalogStore(db_path, index_dir)
        try:
            target = store.resolve_fetch_target("ds-gdp")
            assert target is not None
            assert target.connector_id == "worldbank.wdi"
            assert target.request_dataset_id == "NY.GDP.PCAP.CD"
            assert target.profile_id == "worldbank_wdi"
        finally:
            store.close()


def test_search_by_text_matches_metric_tokens() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = _build_test_db(tmpdir)
        index_dir = Path(tmpdir)
        store = DatasetCatalogStore(db_path, index_dir)
        try:
            results = store.search_by_text("avg_income", top_k=10)
            assert len(results) >= 1
            assert results[0].id == "ds-gdp"
        finally:
            store.close()


def test_graph_search_datasets_expands_ukrainian_query_tokens() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = _build_test_db(tmpdir)
        graph = DatasetCatalogGraph(db_path, Path(tmpdir))
        try:
            results = graph.search_datasets("ввп на душу населення", top_k=5)
            assert results
            assert results[0].id == "ds-gdp"
        finally:
            graph.close()


def test_graph_search_datasets_boosts_country_specific_sources() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_catalog.duckdb"
        build_graph(
            records=iter(
                [
                    DatasetRecord(
                        id="ds-ro-health",
                        title="CHELTUIELI PENTRU SANATATE",
                        description="Sanatate publica si spitale",
                        source="data_gov_ro",
                        source_portal="data_gov_ro",
                        dataset_id="ro-health-1",
                        formats=["XLSX"],
                        distributions=[],
                    ),
                    DatasetRecord(
                        id="ds-md-health",
                        title="Statistica gender: Sanatatea femeilor in Moldova",
                        description="Sanatate publica in Republica Moldova",
                        source="data_gov_md",
                        source_portal="data_gov_md",
                        dataset_id="md-health-1",
                        formats=["XLSX"],
                        distributions=[],
                    ),
                ]
            ),
            db_path=db_path,
        )
        graph = DatasetCatalogGraph(db_path, Path(tmpdir))
        try:
            results = graph.search_datasets("sanatate publica romania", top_k=5)
            assert results
            assert results[0].id == "ds-ro-health"
        finally:
            graph.close()


def test_graph_search_datasets_supports_filters_and_explain() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = _build_test_db(tmpdir)
        graph = DatasetCatalogGraph(db_path, Path(tmpdir))
        try:
            results = graph.search_datasets(
                "gdp per capita",
                top_k=5,
                filters=SearchFilters(
                    sources=("worldbank",),
                    countries=("UA",),
                    execution_tier="fetchable",
                    min_quality_score=0.8,
                ),
                explain=True,
            )
            assert results
            assert results[0].id == "ds-gdp"
            assert results[0].search_explanation is not None
            assert "final_score" in results[0].search_explanation
            assert graph.last_query_metrics is not None
            assert graph.last_query_metrics.returned >= 1
        finally:
            graph.close()


def test_graph_suggest_related_uses_metric_overlap() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = _build_test_db(tmpdir)
        graph = DatasetCatalogGraph(db_path, Path(tmpdir))
        try:
            results = graph.suggest_related("ds-gdp", top_k=5)
            assert all(result.id != "ds-gdp" for result in results)
        finally:
            graph.close()


def test_graph_search_datasets_skips_embedding_import_when_index_missing(monkeypatch) -> None:
    class _PoisonModule(types.ModuleType):
        def __getattr__(self, name: str) -> object:
            raise AssertionError(
                "sentence_transformers should not be imported when vector index is missing"
            )

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = _build_test_db(tmpdir)
        graph = DatasetCatalogGraph(db_path, Path(tmpdir))
        monkeypatch.setitem(
            sys.modules, "sentence_transformers", _PoisonModule("sentence_transformers")
        )
        try:
            results = graph.search_datasets("gdp per capita", top_k=5)
            assert results
            assert results[0].id == "ds-gdp"
            assert graph.last_query_metrics is not None
            assert graph.last_query_metrics.vector_search_ms == 0.0
        finally:
            graph.close()
