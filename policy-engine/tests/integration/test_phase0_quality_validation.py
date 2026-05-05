from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path

import duckdb
import pandas as pd
import pytest
from polisyos.data_forge.domains.academic.batch.article_extractor import run_article_extract
from polisyos.data_forge.domains.academic.batch.config import AcademicBatchConfig
from polisyos.data_forge.domains.academic.batch.fulltext_resolver import FullTextFetchResult
from polisyos.data_forge.domains.academic.batch.graph_builder import run_graph_load
from polisyos.data_forge.domains.academic.batch.resolve_extract import ProviderResponse
from polisyos.data_forge.domains.academic.knowledge.canonical_seed import CANONICAL_VARIABLES
from polisyos.data_forge.domains.academic.knowledge.runtime_canonical_registry import (
    runtime_canonical_names,
)
from polisyos.data_forge.domains.catalog.batch.config import DatasetBatchConfig
from polisyos.data_forge.domains.catalog.batch.core_sources_ingest import run_core_sources_ingest
from polisyos.data_forge.domains.catalog.knowledge.registry import DatasetRegistry
from polisyos.data_forge.domains.catalog.knowledge.variable_alignment import load_seed_alignments
from polisyos.data_forge.kernel.quality import evaluate_phase0_quality
from polisyos.fabric.connectors.sources.world_bank import WorldBankConnector
from polisyos.fabric.connectors.sources.wvs import WVSConnector
from polisyos.lex.api import evaluate_transport_constraints
from polisyos.lex.legal_evaluation.transport_constraints import is_transport_blocked

_CANONICAL_VAR_RE = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*){0,3}$")


class _DeterministicGonkaClient:
    def __init__(self, config):  # type: ignore[no-untyped-def]
        self._config = config

    async def __aenter__(self):  # type: ignore[no-untyped-def]
        return self

    async def __aexit__(self, *exc):  # type: ignore[no-untyped-def]
        return None

    async def chat_json(self, *, model, prompt, temperature):  # type: ignore[no-untyped-def]
        return ProviderResponse(
            parsed={
                "paper_relevance": True,
                "paper_relevance_reason": "policy causal",
                "empirical_parameters": [
                    {
                        "name": "institutional_quality",
                        "value": 0.62,
                        "parameter_type": "quantitative",
                        "evidence_strength": "observational",
                        "geographic_scope": "UA",
                    },
                    {
                        "name": "gdp_per_capita",
                        "value": 12500.0,
                        "parameter_type": "quantitative",
                        "evidence_strength": "observational",
                        "geographic_scope": "UA",
                    },
                ],
                "causal_claims": [
                    {
                        "claim_type": "causal_claim",
                        "cause_variable": "institutional_quality",
                        "effect_variable": "social_trust",
                        "direction": "positive",
                        "design_family_hint": "did",
                        "evidence_strength": "observational",
                        "supporting_span_ids": ["r_01"],
                        "method_span_ids": ["m_01"],
                    },
                    {
                        "claim_type": "causal_claim",
                        "cause_variable": "gdp_per_capita",
                        "effect_variable": "informal_economy_share",
                        "direction": "negative",
                        "design_family_hint": "did",
                        "evidence_strength": "observational",
                        "supporting_span_ids": ["r_01"],
                        "method_span_ids": ["m_01"],
                    },
                    {
                        "claim_type": "causal_claim",
                        "cause_variable": "corruption_level",
                        "effect_variable": "institutional_quality",
                        "direction": "negative",
                        "design_family_hint": "did",
                        "evidence_strength": "observational",
                        "supporting_span_ids": ["r_01"],
                        "method_span_ids": ["m_01"],
                    },
                    {
                        "claim_type": "causal_claim",
                        "cause_variable": "social_trust",
                        "effect_variable": "cultural_cluster",
                        "direction": "positive",
                        "design_family_hint": "did",
                        "evidence_strength": "observational",
                        "supporting_span_ids": ["r_01"],
                        "method_span_ids": ["m_01"],
                    },
                ],
                "boundary_conditions": [],
                "mechanisms": [],
                "methodology_summary": "did",
                "sample_size": 900,
                "citation_summary": "deterministic synthetic fixture",
                "extraction_confidence": 0.9,
            },
            usage={"prompt_tokens": 100, "completion_tokens": 50, "total_cost_usd": 0.01},
            http_status=200,
            finish_reason="stop",
            latency_ms=10.0,
            retry_count=0,
            limiter_wait_ms=0.0,
            backoff_sleep_ms=0.0,
            parse_status="ok",
            error_class="",
            raw_content="{}",
            truncated_output=False,
        )


def _prepare_lex_db(db_path: Path) -> None:
    con = duckdb.connect(str(db_path))
    try:
        con.execute(
            """
            CREATE TABLE lex_facts (
                fact_id VARCHAR,
                fact_text VARCHAR,
                condition_text_uk VARCHAR,
                procedure_text_uk VARCHAR,
                doc_id VARCHAR,
                doc_name VARCHAR,
                doc_reestr_code VARCHAR,
                provision_citation VARCHAR
            )
            """
        )
        con.execute(
            """
            CREATE TABLE lex_doc_domains (
                doc_id VARCHAR,
                domain VARCHAR
            )
            """
        )
        con.execute(
            """
            INSERT INTO lex_facts VALUES (
                'fact_0d_1',
                'Tax code prohibits retroactive tax changes.',
                '',
                '',
                'doc_0d_1',
                'Tax Code',
                'UA-TAX',
                'Art. 58'
            )
            """
        )
        con.execute("INSERT INTO lex_doc_domains VALUES ('doc_0d_1', 'tax_policy')")
        con.execute("CHECKPOINT")
    finally:
        con.close()


def _canonical_namespace() -> set[str]:
    namespace: set[str] = set()
    for root, children in CANONICAL_VARIABLES.items():
        namespace.add(root)
        for child in children:
            if child == "_root":
                continue
            namespace.add(f"{root}.{child}")
    namespace.update(runtime_canonical_names())
    return namespace


def _alignment_seed_parity_pct() -> float:
    path = (
        Path(__file__).resolve().parents[2]
        / "data"
        / "dataset_catalog"
        / "seed_variable_alignments.yaml"
    )
    alignments = load_seed_alignments(path)
    if not alignments:
        return 100.0
    namespace = _canonical_namespace()
    covered = sum(1 for item in alignments if item.canonical_var in namespace)
    return (covered / len(alignments)) * 100.0


def _dataset_resolution_quality(
    *,
    claim_vars: set[str],
    registry: DatasetRegistry,
    country_code: str,
    year: int,
) -> tuple[float, float, float]:
    if not claim_vars:
        return 100.0, 0.0, 0.0

    covered = 0
    proxy = 0
    extrapolated = 0
    for variable in claim_vars:
        matches = registry.find_datasets_for_variable(variable, country_code, (year, year))
        if not matches:
            continue
        best = matches[0]
        if best.coverage_match != "none":
            covered += 1
        if best.is_proxy:
            proxy += 1
        if best.temporal_match == "extrapolation":
            extrapolated += 1
    denominator = len(claim_vars)
    return (
        (covered / denominator) * 100.0,
        (proxy / denominator) * 100.0,
        (extrapolated / denominator) * 100.0,
    )


@pytest.mark.integration
def test_phase0_quality_validation_deterministic_e2e(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "polisyos.data_forge.domains.academic.batch.resolve_extract.GonkaMultiKeyPool",
        _DeterministicGonkaClient,
    )

    async def _fake_fetch_full_text_result(work, **kwargs):  # type: ignore[no-untyped-def]
        return FullTextFetchResult(
            text="We use a difference-in-differences design. Institutional quality improves social trust.",
            source_kind="fulltext_html",
            source_url="https://example.org/synthetic",
            final_state="usable_fulltext",
        )

    monkeypatch.setattr(
        "polisyos.data_forge.domains.academic.batch.resolve_extract.fetch_full_text_result_for_work",
        _fake_fetch_full_text_result,
    )

    async def _fake_wb_fetch(self, _handle, request):
        filters = dict(request.filters or ())
        countries = filters.get("country") or ("UA",)
        country = str(countries[0])
        year = request.date_start.year if request.date_start is not None else 2020
        df = pd.DataFrame(
            [
                {
                    "country_code": country,
                    "year": year,
                    "value": 0.5 if request.dataset_id.startswith(("R", "C", "G")) else 15000.0,
                }
            ]
        )
        return type("WBResult", (), {"data": df})()

    async def _fake_wvs_fetch(self, _handle, request):
        filters = dict(request.filters or ())
        countries = filters.get("country") or ("UA",)
        years = filters.get("survey_year") or ("2020",)
        country = str(countries[0])
        survey_year = int(years[0])
        df = pd.DataFrame(
            [
                {
                    "country_code": country,
                    "survey_year": survey_year,
                    "wave": 7,
                    "value": 0.6,
                }
            ]
        )
        return type("WVSResult", (), {"data": df})()

    monkeypatch.setattr(WorldBankConnector, "fetch", _fake_wb_fetch)
    monkeypatch.setattr(WVSConnector, "fetch", _fake_wvs_fetch)

    academic_config = AcademicBatchConfig(snapshot_root=tmp_path / "snap")
    academic_config.gonka_api_key = "fake"
    academic_config.selected_global_works_path.parent.mkdir(parents=True, exist_ok=True)

    with open(academic_config.selected_global_works_path, "w", encoding="utf-8") as fh:
        for index in range(1, 51):
            work_id = f"https://openalex.org/W{index:04d}"
            row = {
                "work_id": work_id,
                "topic_ids": ["T_POLICY"],
                "topic_display_names": ["Economic policy"],
                "work": {
                    "id": work_id,
                    "title": f"Synthetic Policy Study {index}",
                    "publication_year": 2022,
                    "cited_by_count": 100 + index,
                    "topics": [{"display_name": "Economic policy"}],
                    "abstract_inverted_index": {"policy": [0], "evaluation": [1], "effects": [2]},
                    "authorships": [{"institutions": [{"country_code": "UA"}]}],
                    "open_access": {"is_oa": False},
                },
            }
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    article_metrics = asyncio.run(run_article_extract(academic_config))
    assert int(article_metrics["successful_llm_extractions_per_topic"]) == 50

    extracted_records_path = academic_config.extracted_dir / "resolve_extract.jsonl"
    academic_config.merged_records_path.parent.mkdir(parents=True, exist_ok=True)
    academic_config.merged_records_path.write_text(
        extracted_records_path.read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    run_graph_load(academic_config)

    dataset_config = DatasetBatchConfig(snapshot_root=tmp_path / "snap")
    core_stats = run_core_sources_ingest(dataset_config)
    assert core_stats.observations > 0

    lex_db_path = tmp_path / "lex_kg.duckdb"
    _prepare_lex_db(lex_db_path)
    constraints = evaluate_transport_constraints(
        jurisdiction="UA",
        policy_domain="tax_policy",
        policy_spec={"retroactive": True},
        legal_kg_db_path=lex_db_path,
    )
    assert constraints.hard_constraints

    with duckdb.connect(str(academic_config.db_path), read_only=True) as con:
        article_count = int(
            con.execute(
                "SELECT COUNT(DISTINCT work_id) FROM ac_article_extractions WHERE extraction_mode = 'resolve_extract'"
            ).fetchone()[0]
            or 0
        )
        claims_count = int(con.execute("SELECT COUNT(*) FROM ac_causal_claims").fetchone()[0] or 0)
        parameters_count = int(
            con.execute("SELECT COUNT(*) FROM ac_parameter_estimates").fetchone()[0] or 0
        )
        claim_rows = con.execute("SELECT cause, effect FROM ac_causal_claims").fetchall()

    canonical_tokens = 0
    claim_vars: set[str] = set()
    for row in claim_rows:
        cause = str(row[0] or "").strip()
        effect = str(row[1] or "").strip()
        claim_vars.update({cause, effect})
        if _CANONICAL_VAR_RE.match(cause):
            canonical_tokens += 1
        if _CANONICAL_VAR_RE.match(effect):
            canonical_tokens += 1
    canonical_claim_variable_pct = (
        (canonical_tokens / max(1, claims_count * 2)) * 100.0 if claims_count else 0.0
    )

    registry = DatasetRegistry(dataset_config.db_path)
    dataset_coverage_pct, proxy_share_pct, temporal_extrapolation_share_pct = (
        _dataset_resolution_quality(
            claim_vars=claim_vars,
            registry=registry,
            country_code="UA",
            year=2020,
        )
    )

    report = evaluate_phase0_quality(
        article_count=article_count,
        claims_count=claims_count,
        parameters_count=parameters_count,
        canonical_claim_variable_pct=canonical_claim_variable_pct,
        alignment_seed_parity_pct=_alignment_seed_parity_pct(),
        hard_constraints_present=bool(constraints.hard_constraints),
        hard_constraint_block_signal=is_transport_blocked(constraints),
        dataset_coverage_pct=dataset_coverage_pct,
        proxy_share_pct=proxy_share_pct,
        temporal_extrapolation_share_pct=temporal_extrapolation_share_pct,
    )

    assert report.passed is True
    assert all(check.passed for check in report.checks if check.severity == "critical")
