from __future__ import annotations

import asyncio
import json

import duckdb
from polisyos.data_forge.domains.academic.batch.config import AcademicBatchConfig
from polisyos.data_forge.domains.academic.batch.edge_synthesize import run_edge_synthesize
from polisyos.data_forge.domains.academic.batch.numeric_extract import run_numeric_extract
from polisyos.data_forge.domains.academic.batch.pipeline import _ensure_graph_inputs
from polisyos.data_forge.domains.academic.batch.resolve_extract import (
    GonkaMultiKeyPool,
    _ProviderClient,
    _resolve_provider_watchdog_seconds,
)
from polisyos.data_forge.domains.academic.batch.resolve_finalize import (
    _link_parameter_to_claims,
    run_resolve_finalize,
)
from polisyos.data_forge.domains.academic.knowledge.skg_store import (
    ensure_skg_schema,
    next_skg_version,
)
from polisyos.ir.analytics.context import ContextProfile
from polisyos.ir.analytics.literature import (
    ArticleExtractionResult,
    CausalClaim,
    ClaimExplicitness,
    ClaimType,
    ContextAttribute,
    DesignFamily,
    EvidenceParameter,
    EvidenceSpan,
    EvidenceStrength,
    ModerationEdge,
    ParameterType,
    SourceBasis,
)


def _write_jsonl(path, rows) -> None:  # type: ignore[no-untyped-def]
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def test_resolve_finalize_merges_attempts_and_builds_clean_outputs(tmp_path) -> None:
    config = AcademicBatchConfig(snapshot_root=tmp_path / "snap")
    _write_jsonl(
        config.selected_global_works_path,
        [
            {
                "work_id": "W1",
                "work": {
                    "id": "W1",
                    "title": "Tax reforms and growth",
                    "publication_year": 2021,
                    "language": "en",
                    "type": "article",
                    "has_fulltext": True,
                    "open_access": {"is_oa": True, "oa_url": "https://example.org/w1.pdf"},
                },
                "topic_ids": ["T1"],
                "topic_display_names": ["Tax policy"],
            }
        ],
    )

    attempt_one = ArticleExtractionResult(
        openalex_id="W1",
        title="Tax reforms and growth",
        year=2021,
        cited_by_count=12,
        source_basis=SourceBasis.FULLTEXT,
        causal_claims=[
            CausalClaim(
                claim_id="c1",
                cause_variable="tax_revenue",
                effect_variable="gdp_growth",
                claim_text="Higher tax revenue increases growth in stable states.",
                claim_type=ClaimType.CAUSAL_CLAIM,
                claim_explicitness=ClaimExplicitness.EXPLICIT,
                design_family_hint=DesignFamily.DID,
                evidence_strength=EvidenceStrength.QUASI_NATURAL,
                supporting_spans=[
                    EvidenceSpan(text="Higher tax revenue raised growth by 0.2 points.")
                ],
                method_spans=[EvidenceSpan(text="We estimate a difference-in-differences model.")],
                publish_to_graph=True,
                design_quality_tier=1,
                claim_extraction_confidence=0.81,
            )
        ],
        empirical_parameters=[
            EvidenceParameter(
                name="tax_revenue",
                parameter_type=ParameterType.QUANTITATIVE,
                value=0.2,
                unit="pp",
                evidence_strength=EvidenceStrength.QUASI_NATURAL,
            )
        ],
        context_attributes=[
            ContextAttribute(
                attribute_name="institutional quality",
                canonical_name="institutional_quality",
                value=0.8,
                country_codes=["UA"],
                confidence=0.8,
                evidence_spans=[EvidenceSpan(text="The institutional quality index is 0.8.")],
            )
        ],
        moderation_edges=[],
        boundary_conditions=[],
        extraction_model="model",
        extraction_timestamp="2026-03-12T00:00:00Z",
        extraction_confidence=0.8,
        token_count_prompt=100,
        token_count_completion=50,
    )
    attempt_two = attempt_one.model_copy(
        update={
            "causal_claims": [
                attempt_one.causal_claims[0].model_copy(
                    update={
                        "supporting_spans": [
                            EvidenceSpan(text="Growth rose more in high-capacity regions.")
                        ],
                        "method_spans": [
                            EvidenceSpan(text="Event-study estimates confirm the DiD timing.")
                        ],
                    }
                )
            ],
            "moderation_edges": [
                ModerationEdge(
                    base_cause="tax_revenue",
                    base_effect="gdp_growth",
                    moderator="institutional_quality",
                    base_claim_id="c1",
                    direction_of_moderation="amplifying",
                    confidence=0.72,
                )
            ],
            "llm_error_class": "provider_http_429",
            "token_count_prompt": 0,
            "token_count_completion": 0,
        }
    )
    _write_jsonl(
        config.resolve_extract_attempts_path,
        [
            attempt_one.model_dump(mode="json"),
            attempt_two.model_dump(mode="json"),
        ],
    )

    metrics = run_resolve_finalize(config)

    assert metrics["finalized"] == 1
    assert metrics["succeeded_nonempty"] == 1
    assert metrics["simulation_ready_numeric"] == 0
    final_results = (
        config.resolve_extract_final_results_path.read_text(encoding="utf-8").strip().splitlines()
    )
    assert len(final_results) == 1
    work_rows = [
        json.loads(line)
        for line in config.resolve_extract_final_works_path.read_text(encoding="utf-8").splitlines()
    ]
    assert work_rows[0]["metadata"]["resolve_finalize"] is True
    assert len(work_rows[0]["metadata"]["simulation_ready_numeric_estimates"]) == 0
    assert len(config.published_claims_final_path.read_text(encoding="utf-8").splitlines()) == 1
    assert len(config.context_attributes_clean_path.read_text(encoding="utf-8").splitlines()) == 1
    assert len(config.moderation_edges_clean_path.read_text(encoding="utf-8").splitlines()) == 1


def test_resolve_finalize_infers_simulation_ready_strength_and_unit(tmp_path) -> None:
    config = AcademicBatchConfig(snapshot_root=tmp_path / "snap")
    _write_jsonl(
        config.selected_global_works_path,
        [
            {
                "work_id": "W2",
                "work": {
                    "id": "W2",
                    "title": "Savings commitment and household choices",
                    "publication_year": 2022,
                    "language": "en",
                    "type": "article",
                    "has_fulltext": True,
                    "open_access": {"is_oa": True, "oa_url": "https://example.org/w2.pdf"},
                },
                "topic_ids": ["T2"],
                "topic_display_names": ["Gender and household policy"],
            }
        ],
    )

    attempt = ArticleExtractionResult(
        openalex_id="W2",
        title="Savings commitment and household choices",
        year=2022,
        cited_by_count=20,
        source_basis=SourceBasis.FULLTEXT,
        methodology="Randomized encouragement design with household follow-up surveys.",
        methodology_enum=EvidenceStrength.RCT,
        causal_claims=[
            CausalClaim(
                claim_id="c2",
                cause_variable="access_to_commitment_savings",
                effect_variable="economic.household_consumption_pattern",
                claim_text="Access to commitment savings increased household consumption flexibility.",
                claim_type=ClaimType.CAUSAL_CLAIM,
                claim_explicitness=ClaimExplicitness.EXPLICIT,
                design_family_hint=DesignFamily.RCT,
                evidence_strength=EvidenceStrength.RCT,
                supporting_spans=[
                    EvidenceSpan(
                        text="Access to commitment savings increased consumption flexibility."
                    )
                ],
                method_spans=[
                    EvidenceSpan(text="We randomized access to commitment savings products.")
                ],
                publish_to_graph=True,
                design_quality_tier=1,
                claim_extraction_confidence=0.9,
            )
        ],
        empirical_parameters=[
            EvidenceParameter(
                name="access_to_commitment_savings",
                display_name="treatment effect on household consumption flexibility",
                parameter_type=ParameterType.QUANTITATIVE,
                value=0.25,
                confidence_interval=(0.10, 0.40),
                unit=None,
                evidence_strength=EvidenceStrength.UNKNOWN,
            )
        ],
        source_context=ContextProfile(context_id="KE", context_label="Kenya", countries=["KE"]),
        extraction_model="model",
        extraction_timestamp="2026-03-12T00:00:00Z",
        extraction_confidence=0.88,
        token_count_prompt=100,
        token_count_completion=50,
    )
    _write_jsonl(config.resolve_extract_attempts_path, [attempt.model_dump(mode="json")])

    metrics = run_resolve_finalize(config)

    assert metrics["simulation_ready_numeric"] == 1
    numeric_rows = [
        json.loads(line)
        for line in config.simulation_ready_numeric_path.read_text(encoding="utf-8").splitlines()
    ]
    assert numeric_rows[0]["unit"] == "unitless"
    assert numeric_rows[0]["evidence_strength"] == "rct"


def test_pipeline_auto_prepares_graph_inputs_when_merge_missing(tmp_path) -> None:
    config = AcademicBatchConfig(snapshot_root=tmp_path / "snap")
    called: list[str] = []

    def _fake_merge(cfg):  # type: ignore[no-untyped-def]
        called.append(str(cfg.snapshot_root))
        cfg.merged_records_path.parent.mkdir(parents=True, exist_ok=True)
        cfg.merged_records_path.write_text("", encoding="utf-8")
        return {"works": 1}

    metrics = _ensure_graph_inputs(config, merge_and_dedup_fn=_fake_merge)

    assert metrics == {"works": 1}
    assert called == [str(config.snapshot_root)]
    assert config.merged_records_path.exists()


def test_resolve_finalize_filters_non_effect_stats_and_infers_score_units(tmp_path) -> None:
    config = AcademicBatchConfig(snapshot_root=tmp_path / "snap")
    _write_jsonl(
        config.selected_global_works_path,
        [
            {
                "work_id": "W3",
                "work": {
                    "id": "W3",
                    "title": "Online health education and prevention knowledge",
                    "publication_year": 2021,
                    "language": "en",
                    "type": "article",
                    "has_fulltext": True,
                    "open_access": {"is_oa": True, "oa_url": "https://example.org/w3.pdf"},
                },
                "topic_ids": ["T3"],
                "topic_display_names": ["Public health and nutrition"],
            }
        ],
    )

    attempt = ArticleExtractionResult(
        openalex_id="W3",
        title="Online health education and prevention knowledge",
        year=2021,
        cited_by_count=8,
        source_basis=SourceBasis.FULLTEXT,
        methodology="Non-randomized pretest-posttest score comparison.",
        methodology_enum=EvidenceStrength.QUASI_NATURAL,
        causal_claims=[
            CausalClaim(
                claim_id="c3",
                cause_variable="health.education.media.video",
                effect_variable="health.knowledge.covid19_prevention",
                claim_text="Online video education improved prevention knowledge scores.",
                claim_type=ClaimType.CAUSAL_CLAIM,
                claim_explicitness=ClaimExplicitness.EXPLICIT,
                design_family_hint=DesignFamily.QUASI_EXPERIMENTAL_OTHER,
                evidence_strength=EvidenceStrength.QUASI_NATURAL,
                supporting_spans=[EvidenceSpan(text="Knowledge scores increased after treatment.")],
                method_spans=[
                    EvidenceSpan(text="We compare pretest and posttest knowledge scores.")
                ],
                publish_to_graph=True,
                design_quality_tier=2,
                claim_extraction_confidence=0.86,
            )
        ],
        empirical_parameters=[
            EvidenceParameter(
                name="health.knowledge.covid19_prevention",
                display_name="health.knowledge.covid19_prevention",
                parameter_type=ParameterType.QUANTITATIVE,
                value=0.248,
                std_error=0.05,
                unit=None,
                evidence_strength=EvidenceStrength.UNKNOWN,
                heterogeneity_note="average posttest minus pretest knowledge score difference",
            ),
            EvidenceParameter(
                name="study.sample_size",
                display_name="study.sample_size",
                parameter_type=ParameterType.QUANTITATIVE,
                value=120.0,
                unit=None,
                evidence_strength=EvidenceStrength.UNKNOWN,
                heterogeneity_note="purposive sample from WhatsApp groups",
            ),
        ],
        source_context=ContextProfile(context_id="NG", context_label="Nigeria", countries=["NG"]),
        extraction_model="model",
        extraction_timestamp="2026-03-12T00:00:00Z",
        extraction_confidence=0.84,
        token_count_prompt=100,
        token_count_completion=50,
    )
    _write_jsonl(config.resolve_extract_attempts_path, [attempt.model_dump(mode="json")])

    metrics = run_resolve_finalize(config)

    assert metrics["simulation_ready_numeric"] == 1


def test_gonka_multi_key_pool_spreads_first_concurrent_acquires_across_keys(tmp_path) -> None:
    config = AcademicBatchConfig(snapshot_root=tmp_path / "snap")
    config.gonka_api_keys = ["k1", "k2", "k3", "k4", "k5"]
    pool = GonkaMultiKeyPool(config)

    async def _run() -> list[int]:
        acquired = [await pool._acquire() for _ in range(5)]
        try:
            return [client.client_index for client in acquired]
        finally:
            for client in acquired:
                pool._release(client)

    indexes = asyncio.run(_run())
    assert sorted(indexes) == [1, 2, 3, 4, 5]


def test_link_parameter_to_claims_uses_token_overlap() -> None:
    claim = CausalClaim(
        claim_id="c_overlap",
        cause_variable="use_of_grain_loaders",
        effect_variable="grain_damage_power_consumption",
        claim_text="Grain loaders damage caryopses by 4-6% and increase power consumption.",
        claim_type=ClaimType.CAUSAL_CLAIM,
        claim_explicitness=ClaimExplicitness.EXPLICIT,
        design_family_hint=DesignFamily.OLS,
        evidence_strength=EvidenceStrength.OBSERVATIONAL,
        supporting_spans=[EvidenceSpan(text="Grain loaders damage caryopses by 4-6%.")],
        method_spans=[EvidenceSpan(text="Controlled harvesting comparison.")],
    )
    parameter = EvidenceParameter(
        name="grain_damage_from_loaders",
        display_name="grain damage from loaders",
        parameter_type=ParameterType.QUANTITATIVE,
        value=0.04,
        unit="proportion",
        evidence_strength=EvidenceStrength.OBSERVATIONAL,
        heterogeneity_note="Grain loaders damage caryopses by 4-6%",
    )

    assert _link_parameter_to_claims(parameter, [claim]) == ["c_overlap"]


def test_resolve_finalize_rejects_ambiguous_small_number_bundles(tmp_path) -> None:
    config = AcademicBatchConfig(snapshot_root=tmp_path / "snap")
    _write_jsonl(
        config.selected_global_works_path,
        [
            {
                "work_id": "W4",
                "work": {
                    "id": "W4",
                    "title": "Online health education and prevention knowledge",
                    "publication_year": 2021,
                    "language": "en",
                    "type": "article",
                    "has_fulltext": True,
                    "open_access": {"is_oa": True, "oa_url": "https://example.org/w4.pdf"},
                },
                "topic_ids": ["T4"],
                "topic_display_names": ["Public health and nutrition"],
            }
        ],
    )

    attempt = ArticleExtractionResult(
        openalex_id="W4",
        title="Online health education and prevention knowledge",
        year=2021,
        cited_by_count=8,
        source_basis=SourceBasis.FULLTEXT,
        methodology="Non-randomized pretest-posttest score comparison.",
        methodology_enum=EvidenceStrength.QUASI_NATURAL,
        causal_claims=[
            CausalClaim(
                claim_id="c4",
                cause_variable="health.education.media.video",
                effect_variable="health.knowledge.covid19_prevention",
                claim_text="Online video education improved prevention knowledge scores.",
                claim_type=ClaimType.CAUSAL_CLAIM,
                claim_explicitness=ClaimExplicitness.EXPLICIT,
                design_family_hint=DesignFamily.QUASI_EXPERIMENTAL_OTHER,
                evidence_strength=EvidenceStrength.QUASI_NATURAL,
                supporting_spans=[EvidenceSpan(text="Knowledge scores increased after treatment.")],
                method_spans=[
                    EvidenceSpan(text="We compare pretest and posttest knowledge scores.")
                ],
                publish_to_graph=True,
                design_quality_tier=2,
                claim_extraction_confidence=0.86,
            )
        ],
        empirical_parameters=[
            EvidenceParameter(
                name="health.knowledge.covid19_prevention",
                display_name="health.knowledge.covid19_prevention",
                parameter_type=ParameterType.QUANTITATIVE,
                value=0.001,
                unit=None,
                evidence_strength=EvidenceStrength.UNKNOWN,
                heterogeneity_note="comparison of pretest and posttest knowledge scores",
            ),
            EvidenceParameter(
                name="health.knowledge.covid19_prevention",
                display_name="health.knowledge.covid19_prevention",
                parameter_type=ParameterType.QUANTITATIVE,
                value=0.045,
                unit=None,
                evidence_strength=EvidenceStrength.UNKNOWN,
                heterogeneity_note="comparison of pretest and posttest knowledge scores",
            ),
            EvidenceParameter(
                name="health.knowledge.covid19_prevention",
                display_name="health.knowledge.covid19_prevention",
                parameter_type=ParameterType.QUANTITATIVE,
                value=0.248,
                unit=None,
                evidence_strength=EvidenceStrength.UNKNOWN,
                heterogeneity_note="comparison of pretest and posttest knowledge scores",
            ),
        ],
        extraction_model="model",
        extraction_timestamp="2026-03-12T00:00:00Z",
        extraction_confidence=0.84,
        token_count_prompt=100,
        token_count_completion=50,
    )
    _write_jsonl(config.resolve_extract_attempts_path, [attempt.model_dump(mode="json")])

    metrics = run_resolve_finalize(config)

    assert metrics["simulation_ready_numeric"] == 0
    assert config.simulation_ready_numeric_path.read_text(encoding="utf-8").strip() == ""


def test_numeric_extract_materializes_raw_curated_and_simulation_ready_layers(tmp_path) -> None:
    config = AcademicBatchConfig(snapshot_root=tmp_path / "snap")
    result = ArticleExtractionResult(
        openalex_id="W5",
        title="Tax salience and compliance",
        year=2024,
        cited_by_count=10,
        source_basis=SourceBasis.FULLTEXT,
        methodology="Randomized disclosure intervention with tax notices.",
        methodology_enum=EvidenceStrength.RCT,
        causal_claims=[
            CausalClaim(
                claim_id="c5",
                cause_variable="fiscal.tax_notice_salience",
                effect_variable="fiscal.tax_compliance_rate",
                claim_text="Salient tax notices increased compliance.",
                claim_type=ClaimType.CAUSAL_CLAIM,
                claim_explicitness=ClaimExplicitness.EXPLICIT,
                design_family_hint=DesignFamily.RCT,
                evidence_strength=EvidenceStrength.RCT,
                supporting_spans=[
                    EvidenceSpan(text="Tax notices increased compliance by 4 percentage points.")
                ],
                method_spans=[EvidenceSpan(text="We randomized reminder notice framing.")],
                publish_to_graph=True,
                design_quality_tier=1,
                claim_extraction_confidence=0.91,
            )
        ],
        empirical_parameters=[
            EvidenceParameter(
                name="fiscal.tax_compliance_rate",
                parameter_type=ParameterType.QUANTITATIVE,
                value=4.0,
                unit="percentage_points",
                confidence_interval=(2.1, 5.9),
                evidence_strength=EvidenceStrength.RCT,
            )
        ],
        extraction_model="model",
        extraction_timestamp="2026-03-13T00:00:00Z",
        extraction_confidence=0.9,
        token_count_prompt=100,
        token_count_completion=50,
    )
    _write_jsonl(config.resolve_extract_final_results_path, [result.model_dump(mode="json")])
    _write_jsonl(
        config.resolve_extract_final_works_path,
        [
            {
                "id": "W5",
                "title": "Tax salience and compliance",
                "context_profile": {"context_id": "UA", "income_level": "upper_middle"},
            }
        ],
    )

    metrics = run_numeric_extract(config)

    assert metrics == {
        "works_seen": 1,
        "raw_numeric": 1,
        "curated_numeric": 1,
        "simulation_ready": 1,
    }
    simulation_rows = [
        json.loads(line)
        for line in config.simulation_ready_numeric_path.read_text(encoding="utf-8").splitlines()
    ]
    assert simulation_rows[0]["canonical_name"] == "fiscal.tax_compliance_rate"
    assert simulation_rows[0]["uncertainty_source"] == "confidence_interval"
    assert simulation_rows[0]["source_layer"] == "simulation_ready"
    assert simulation_rows[0]["source_context"]["context_id"] == "UA"
    assert simulation_rows[0]["linked_claim_ids"] == ["c5"]
    assert simulation_rows[0]["linked_edge_ids"] != []


def test_numeric_extract_keeps_rows_curated_when_uncertainty_missing(tmp_path) -> None:
    config = AcademicBatchConfig(snapshot_root=tmp_path / "snap")
    result = ArticleExtractionResult(
        openalex_id="W6",
        title="Savings prompts and budgeting",
        year=2024,
        cited_by_count=10,
        source_basis=SourceBasis.FULLTEXT,
        methodology="Quasi-experimental rollout with district controls.",
        methodology_enum=EvidenceStrength.QUASI_NATURAL,
        causal_claims=[
            CausalClaim(
                claim_id="c6",
                cause_variable="access_to_commitment_savings",
                effect_variable="economic.household_savings_rate",
                claim_text="Savings prompts increased household savings.",
                claim_type=ClaimType.CAUSAL_CLAIM,
                claim_explicitness=ClaimExplicitness.EXPLICIT,
                design_family_hint=DesignFamily.QUASI_EXPERIMENTAL_OTHER,
                evidence_strength=EvidenceStrength.QUASI_NATURAL,
                supporting_spans=[EvidenceSpan(text="Savings rose after prompt exposure.")],
                method_spans=[EvidenceSpan(text="District-level rollout timing is quasi-random.")],
                publish_to_graph=True,
                design_quality_tier=2,
                claim_extraction_confidence=0.82,
            )
        ],
        empirical_parameters=[
            EvidenceParameter(
                name="economic.household_savings_rate",
                parameter_type=ParameterType.QUANTITATIVE,
                value=0.18,
                unit="unitless",
                evidence_strength=EvidenceStrength.QUASI_NATURAL,
            )
        ],
        extraction_model="model",
        extraction_timestamp="2026-03-13T00:00:00Z",
        extraction_confidence=0.82,
        token_count_prompt=100,
        token_count_completion=50,
    )
    _write_jsonl(config.resolve_extract_final_results_path, [result.model_dump(mode="json")])
    _write_jsonl(
        config.resolve_extract_final_works_path,
        [
            {
                "id": "W6",
                "title": "Savings prompts and budgeting",
                "context_profile": {"context_id": "UA"},
            }
        ],
    )

    metrics = run_numeric_extract(config)

    assert metrics["raw_numeric"] == 1
    assert metrics["curated_numeric"] == 1
    assert metrics["simulation_ready"] == 0


def test_edge_synthesize_builds_family_edges_and_review_queue(tmp_path) -> None:
    config = AcademicBatchConfig(snapshot_root=tmp_path / "snap")
    con = duckdb.connect(str(config.db_path))
    try:
        ensure_skg_schema(con)
        version_id = next_skg_version(con, description="test")
        con.execute(
            """
            INSERT INTO ac_skg_edge_evidence(
                edge_id, claim_id, openalex_id, src, dst, direction,
                evidence_strength, confidence, design_family, design_quality_tier, skg_version
            ) VALUES
                ('e1', 'c1', 'W1', 'institutional_quality.rule_of_law', 'gdp_growth.real', 'positive', 'quasi_natural', 0.82, 'did', 1, ?),
                ('e2', 'c2', 'W2', 'institutional_quality.government_effectiveness', 'gdp_growth.nominal', 'positive', 'panel_fe', 0.66, 'panel_fe', 2, ?)
            """,
            [version_id, version_id],
        )
        con.execute(
            """
            INSERT INTO ac_skg_canonization_cache(raw_name, canonical_name, approved)
            VALUES ('govt effectiveness', 'institutional_quality.government_effectiveness', FALSE)
            """
        )
        con.execute("CHECKPOINT")
    finally:
        con.close()

    metrics = run_edge_synthesize(config)

    assert metrics["family_edges"] == 1
    assert metrics["review_queue"] == 1
    con = duckdb.connect(str(config.db_path), read_only=True)
    try:
        row = con.execute(
            "SELECT src_family, dst_family, n_articles, n_claims FROM ac_skg_family_edges"
        ).fetchone()
    finally:
        con.close()
    assert row == ("institutional_quality", "gdp_growth", 2, 2)


def test_edge_synthesize_materializes_contested_edges(tmp_path) -> None:
    config = AcademicBatchConfig(snapshot_root=tmp_path / "snap")
    con = duckdb.connect(str(config.db_path))
    try:
        ensure_skg_schema(con)
        version_id = next_skg_version(con, description="test")
        con.execute(
            """
            INSERT INTO ac_skg_edge_evidence(
                edge_id, claim_id, openalex_id, src, dst, direction,
                evidence_strength, confidence, design_family, design_quality_tier, skg_version
            ) VALUES
                ('e1', 'c1', 'W1', 'macro.tax', 'macro.employment', 'positive', 'quasi_natural', 0.82, 'did', 1, ?),
                ('e2', 'c2', 'W2', 'macro.tax', 'macro.employment', 'negative', 'panel_fe', 0.66, 'panel_fe', 2, ?)
            """,
            [version_id, version_id],
        )
        con.execute(
            """
            INSERT INTO ac_skg_canonization_cache(raw_name, canonical_name, approved)
            VALUES
                ('macro tax', 'macro.tax', TRUE),
                ('macro employment', 'macro.employment', TRUE)
            """
        )
        con.execute("CHECKPOINT")
    finally:
        con.close()

    metrics = run_edge_synthesize(config)

    assert metrics["contested_edges"] == 1
    con = duckdb.connect(str(config.db_path), read_only=True)
    try:
        row = con.execute(
            "SELECT src_family, dst_family, resolution_status, runtime_support FROM ac_skg_contested_edges"
        ).fetchone()
    finally:
        con.close()
    assert row == ("macro.tax", "macro.employment", "contested", "MIXED")


def test_provider_client_supports_fractional_rps() -> None:
    client = _ProviderClient(
        client_index=1,
        api_key="test-key",
        base_url="https://example.test/v1",
        rate_limit_rps=0.04,
        circuit_failures=5,
        circuit_reset_seconds=60,
        connect_timeout_seconds=5,
        read_timeout_seconds=5,
        total_timeout_seconds=10,
    )

    assert client.limiter._max == 1
    assert client.limiter._window == 25.0
    assert client.rate_limit_rps == 0.04


def test_provider_watchdog_override_modes(tmp_path) -> None:
    config = AcademicBatchConfig(snapshot_root=tmp_path / "snap")
    config.article_total_timeout_seconds = 150

    config.article_provider_watchdog_seconds = 0
    assert _resolve_provider_watchdog_seconds(config) == 300.0

    config.article_provider_watchdog_seconds = 420
    assert _resolve_provider_watchdog_seconds(config) == 420.0

    config.article_provider_watchdog_seconds = -1
    assert _resolve_provider_watchdog_seconds(config) is None
