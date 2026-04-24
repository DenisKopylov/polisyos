from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import duckdb
import numpy as np

from polisyos.academic.batch import best_snapshot, cli
from polisyos.academic.batch.benchmark import BenchmarkOutcome
from polisyos.academic.knowledge.search import ScholarKnowledgeGraph
from polisyos.academic.knowledge.skg_query import SKGQuery
from polisyos.academic.knowledge.skg_store import ensure_skg_schema
from polisyos.batch_common.manifest import write_publish_manifest, write_stage_manifest


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def _default_benchmark_scenarios() -> list[dict]:
    return [
        {
            "scenario_id": "education_human_capital",
            "title": "Teacher coaching and learning outcomes",
            "policy_domain": "education",
            "causal_edges": [
                {"cause": "education.teacher_coaching", "effect": "education.learning_outcomes"}
            ],
            "parameters": ["education.learning_outcomes"],
            "scholar_queries": [
                {
                    "cause": "education.teacher_coaching",
                    "effect": "education.learning_outcomes",
                    "support_mode": "hybrid",
                    "min_results": 1,
                }
            ],
        },
        {
            "scenario_id": "social_protection_consumption",
            "title": "Cash transfers and consumption smoothing",
            "policy_domain": "social_policy",
            "causal_edges": [
                {
                    "cause": "social.cash_transfer_program",
                    "effect": "economic.household_consumption",
                }
            ],
            "parameters": ["economic.household_consumption"],
            "scholar_queries": [
                {
                    "cause": "social.cash_transfer_program",
                    "effect": "economic.household_consumption",
                    "support_mode": "hybrid",
                    "min_results": 1,
                }
            ],
        },
    ]


def _default_benchmark_report_scenarios() -> list[dict]:
    return [
        {
            "scenario_id": "education_human_capital",
            "causal_edges": [{"status": "supported"}],
            "scholar_queries": [{"supported": True}],
        },
        {
            "scenario_id": "social_protection_consumption",
            "causal_edges": [{"status": "mixed"}],
            "scholar_queries": [{"supported": True}],
        },
    ]


def _create_original_db(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with duckdb.connect(str(path)) as con:
        ensure_skg_schema(con)
        con.execute(
            """
            CREATE TABLE ac_works (
                id VARCHAR PRIMARY KEY,
                title VARCHAR,
                doi VARCHAR,
                abstract VARCHAR,
                year INTEGER,
                publication_date VARCHAR,
                language VARCHAR,
                work_type VARCHAR,
                is_retracted BOOLEAN,
                cited_by_count INTEGER,
                fwci DOUBLE,
                citation_percentile DOUBLE,
                citation_top_1 BOOLEAN,
                citation_top_10 BOOLEAN,
                journal VARCHAR,
                source_id VARCHAR,
                is_oa BOOLEAN,
                has_fulltext BOOLEAN,
                full_text_url VARCHAR,
                trust_score DOUBLE,
                study_design VARCHAR
            )
            """
        )
        con.execute(
            """
            INSERT INTO ac_works VALUES (
                'W1',
                'Teacher coaching and student learning',
                '10.1/example',
                'Teacher coaching programs improve student learning outcomes.',
                2022,
                '2022-01-01',
                'en',
                'article',
                FALSE,
                12,
                1.2,
                0.95,
                FALSE,
                TRUE,
                'Journal of Policy Trials',
                'S1',
                TRUE,
                TRUE,
                'https://example.org/fulltext',
                0.87,
                'rct'
            )
            """
        )
        con.execute(
            "CREATE TABLE ac_work_concepts (work_id VARCHAR, concept_name VARCHAR, score DOUBLE)"
        )
        con.execute("INSERT INTO ac_work_concepts VALUES ('W1', 'teacher coaching', 0.91)")
        con.execute(
            """
            CREATE TABLE ac_parameter_estimates (
                id VARCHAR,
                work_id VARCHAR,
                variable_name VARCHAR,
                estimate DOUBLE,
                ci_low DOUBLE,
                ci_high DOUBLE,
                std_error DOUBLE,
                unit VARCHAR,
                domain VARCHAR,
                study_design VARCHAR,
                sample_size INTEGER,
                country VARCHAR,
                period_start INTEGER,
                period_end INTEGER,
                trust_score DOUBLE,
                raw_context VARCHAR
            )
            """
        )
        con.execute(
            """
            INSERT INTO ac_parameter_estimates VALUES (
                'pe1', 'W1', 'teacher_coaching_program', 0.25, 0.1, 0.4, 0.05,
                'standard_deviations', 'education', 'rct', 500, 'KE', 2020, 2022, 0.92, '{}'
            )
            """
        )
        con.execute(
            "CREATE TABLE ac_causal_claims_raw (id VARCHAR, work_id VARCHAR, cause VARCHAR, effect VARCHAR)"
        )
        con.execute(
            "INSERT INTO ac_causal_claims_raw VALUES ('raw1', 'W1', 'teacher_coaching_program', 'student_learning')"
        )
        con.execute(
            """
            CREATE TABLE ac_claim_adjudications (
                claim_id VARCHAR,
                publishable_edge BOOLEAN,
                design_quality_tier INTEGER
            )
            """
        )
        con.execute("INSERT INTO ac_claim_adjudications VALUES ('claim1', TRUE, 1)")
        con.execute(
            """
            CREATE TABLE ac_causal_claims (
                id VARCHAR,
                work_id VARCHAR,
                cause VARCHAR,
                effect VARCHAR,
                direction VARCHAR,
                strength VARCHAR,
                mechanism VARCHAR,
                domain VARCHAR,
                trust_score DOUBLE
            )
            """
        )
        con.execute(
            """
            INSERT INTO ac_causal_claims VALUES (
                'claim1', 'W1', 'teacher_coaching_program', 'student_learning',
                'positive', 'rct', 'instructional_quality', 'education', 0.93
            )
            """
        )
        con.execute("CREATE TABLE ac_runs (run_id VARCHAR)")
        con.execute("INSERT INTO ac_runs VALUES ('run_original')")
        con.execute("CREATE TABLE ac_topics (topic_id VARCHAR, title VARCHAR)")
        con.execute("INSERT INTO ac_topics VALUES ('education_topic', 'Education')")
        con.execute(
            "CREATE TABLE ac_topic_selections (work_id VARCHAR, topic_id VARCHAR, run_id VARCHAR, pass_name VARCHAR)"
        )
        con.execute(
            "INSERT INTO ac_topic_selections VALUES ('W1', 'education_topic', 'run_original', 'pass1')"
        )
        con.execute("CREATE TABLE ac_article_extractions (openalex_id VARCHAR, payload VARCHAR)")
        con.execute("INSERT INTO ac_article_extractions VALUES ('W1', '{}')")
        con.execute("CREATE TABLE ac_boundary_conditions (work_id VARCHAR, condition_text VARCHAR)")
        con.execute("INSERT INTO ac_boundary_conditions VALUES ('W1', 'rural schools')")
        con.execute("CREATE TABLE ac_ingest_errors (error_id VARCHAR, message VARCHAR)")
        con.execute("INSERT INTO ac_ingest_errors VALUES ('err1', 'none')")
        con.execute(
            """
            INSERT INTO ac_skg_versions(version_id, created_ts, n_articles, n_edges, n_variables, description)
            VALUES (7, '2026-04-01T00:00:00+00:00', 1, 1, 0, 'original')
            """
        )
        con.execute(
            """
            INSERT INTO ac_skg_articles(
                openalex_id, doi, title, year, cited_by_count, extraction_json, context_json, retracted, skg_version
            ) VALUES (
                'W1', '10.1/example', 'Teacher coaching and student learning', 2022, 12, '{}', '{}', FALSE, 7
            )
            """
        )
        con.execute(
            """
            INSERT INTO ac_skg_edges(
                edge_id, src, dst, direction, n_articles, article_refs, evidence_strength,
                confidence, scope_conditions, quality_signals_json
            ) VALUES (
                'e_exact', 'teacher_coaching_program', 'student_learning', 'positive', 1, '["W1"]',
                'rct', 0.91, '[]', '{}'
            )
            """
        )
        con.execute(
            """
            INSERT INTO ac_skg_edge_evidence(
                edge_id, claim_id, openalex_id, src, dst, direction, evidence_strength, confidence,
                design_family, design_quality_tier, skg_version
            ) VALUES (
                'e_exact', 'claim1', 'W1', 'teacher_coaching_program', 'student_learning',
                'positive', 'rct', 0.91, 'experiment', 1, 7
            )
            """
        )
        con.execute(
            """
            INSERT INTO ac_skg_edges(
                edge_id, src, dst, direction, n_articles, article_refs, evidence_strength,
                confidence, scope_conditions, quality_signals_json
            ) VALUES (
                'e_cash', 'fiscal.cash_transfer', 'economic.consumption', 'positive', 1, '["W1"]',
                'rct', 0.89, '[]', '{}'
            )
            """
        )
        con.execute(
            """
            INSERT INTO ac_skg_edge_evidence(
                edge_id, claim_id, openalex_id, src, dst, direction, evidence_strength, confidence,
                design_family, design_quality_tier, skg_version
            ) VALUES (
                'e_cash', 'claim_cash', 'W1', 'fiscal.cash_transfer', 'economic.consumption',
                'positive', 'rct', 0.89, 'experiment', 1, 7
            )
            """
        )
        con.execute(
            """
            INSERT INTO ac_skg_context_attributes(
                attr_id, openalex_id, canonical_name, attribute_value, value_qualitative, unit,
                country_code, time_period, measurement_method, confidence, evidence_span_count, skg_version
            ) VALUES (
                'ctx1', 'W1', 'school.resources', 1.0, NULL, 'index', 'KE', '2020-2022',
                'survey', 0.8, 2, 7
            )
            """
        )
        con.execute(
            """
            INSERT INTO ac_skg_moderation_edges(
                moderation_id, base_cause, base_effect, moderator, base_claim_id, direction_of_mod,
                interaction_coeff, interaction_pvalue, evidence_count, confidence, match_quality,
                alignment_source, source_refs, skg_version
            ) VALUES (
                'mod1', 'teacher_coaching_program', 'student_learning', 'school.resources', 'claim1',
                'positive', 0.2, 0.03, 1, 0.7, 'exact_claim_ref', 'manual', '["W1"]', 7
            )
            """
        )
        con.execute(
            """
            INSERT INTO ac_skg_variables(
                canonical_name, normalized_name, display_name, parent_name, approved_canonical_name,
                approved_parent_name, is_approved_canonical, resolution_method, resolution_confidence, mention_count
            ) VALUES
            ('teacher_coaching_program', 'teacher_coaching_program', 'Teacher coaching program', NULL,
             'education.teacher_coaching', NULL, FALSE, 'manual', 0.95, 10),
            ('student_learning', 'student_learning', 'Student learning', NULL,
             'education.learning_outcomes', NULL, FALSE, 'manual', 0.95, 12),
            ('fiscal.cash_transfer', 'fiscal.cash_transfer', 'Cash transfer', 'social',
             'social.cash_transfer_program', NULL, FALSE, 'manual', 0.98, 8),
            ('economic.consumption', 'economic.consumption', 'Consumption', 'economic',
             'economic.household_consumption', NULL, FALSE, 'manual', 0.98, 9),
            ('economic.consumption_index', 'economic.consumption_index', 'Consumption index', 'economic',
             'economic.household_consumption', NULL, FALSE, 'manual', 0.90, 4),
            ('governance.procurement_compliance', 'governance.procurement_compliance', 'Procurement compliance', 'governance',
             'governance.procurement_integrity', NULL, FALSE, 'manual', 0.88, 3)
            """
        )
        con.execute(
            """
            INSERT INTO ac_skg_canonization_cache(raw_name, canonical_name, approved)
            VALUES
            ('cash transfer', 'fiscal.cash_transfer', TRUE),
            ('teacher coaching', 'teacher_coaching_program', TRUE)
            """
        )
        con.execute(
            """
            INSERT INTO ac_skg_variable_synonyms(synonym, canonical_name, method, confidence, approved)
            VALUES
            ('cash transfer programme', 'social.cash_transfer_program', 'manual', 1.0, TRUE),
            ('teacher coaching programme', 'education.teacher_coaching', 'manual', 1.0, TRUE)
            """
        )


def _create_remap_db(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with duckdb.connect(str(path)) as con:
        ensure_skg_schema(con)
        con.execute(
            """
            INSERT INTO ac_skg_versions(version_id, created_ts, n_articles, n_edges, n_variables, description)
            VALUES (11, '2026-04-02T00:00:00+00:00', 1, 2, 12, 'remap')
            """
        )
        con.execute(
            """
            INSERT INTO ac_skg_variables(
                canonical_name, normalized_name, display_name, parent_name, approved_canonical_name,
                approved_parent_name, is_approved_canonical, resolution_method, resolution_confidence, mention_count
            ) VALUES
            ('education.teacher_coaching', 'education.teacher_coaching', 'Teacher coaching', 'education',
             'education.teacher_coaching', NULL, TRUE, 'manual', 1.0, 20),
            ('teacher_coaching_program', 'teacher_coaching_program', 'Teacher coaching program', NULL,
             'teacher_coaching_program', NULL, TRUE, 'manual', 1.0, 10),
            ('education.learning_outcomes', 'education.learning_outcomes', 'Learning outcomes', 'education',
             'education.learning_outcomes', NULL, TRUE, 'manual', 1.0, 22),
            ('student_learning', 'student_learning', 'Student learning', NULL,
             'student_learning', NULL, TRUE, 'manual', 1.0, 12),
            ('social.cash_transfer_program', 'social.cash_transfer_program', 'Cash transfer program', 'social',
             'social.cash_transfer_program', NULL, TRUE, 'manual', 1.0, 14),
            ('fiscal.cash_transfer', 'fiscal.cash_transfer', 'Cash transfer', 'fiscal',
             'fiscal.cash_transfer', NULL, TRUE, 'manual', 1.0, 9),
            ('economic.household_consumption', 'economic.household_consumption', 'Household consumption', 'economic',
             'economic.household_consumption', NULL, TRUE, 'manual', 1.0, 15),
            ('economic.consumption', 'economic.consumption', 'Consumption', 'economic',
             'economic.consumption', NULL, TRUE, 'manual', 1.0, 9),
            ('governance.public_procurement_compliance', 'governance.public_procurement_compliance', 'Public procurement compliance', 'governance',
             'governance.public_procurement_compliance', NULL, TRUE, 'manual', 1.0, 6),
            ('governance.procurement_integrity', 'governance.procurement_integrity', 'Procurement integrity', 'governance',
             'governance.procurement_integrity', NULL, TRUE, 'manual', 1.0, 5),
            ('governance.procurement_compliance', 'governance.procurement_compliance', 'Procurement compliance', 'governance',
             'governance.public_procurement_compliance', NULL, FALSE, 'manual', 0.97, 7)
            """
        )
        con.execute(
            """
            INSERT INTO ac_skg_family_edges(
                family_edge_id, src_family, dst_family, direction, n_articles, n_claims, article_refs, claim_refs,
                evidence_strength, confidence, direction_histogram_json, design_tier_histogram_json,
                design_family_histogram_json, candidate_layer, quality_signals_json
            ) VALUES (
                'fe1', 'teacher_coaching_program', 'student_learning', 'positive', 1, 1, '["W1"]', '["claim1"]',
                'rct', 0.95, '{"positive": 1}', '{"1": 1}', '{"experiment": 1}', 'family', '{}'
            )
            """
        )
        con.execute(
            """
            INSERT INTO ac_skg_contested_edges(
                contested_edge_id, src_family, dst_family, n_articles, n_claims, article_refs, claim_refs,
                dominant_direction, resolution_status, runtime_support, evidence_strength, confidence,
                positive_weight, negative_weight, mixed_weight, dominant_direction_agreement,
                strongest_dissent_strength, strongest_dissent_year, direction_histogram_json, quality_signals_json
            ) VALUES (
                'ce1', 'teacher_coaching_program', 'student_learning', 1, 1, '["W1"]', '["claim1"]',
                'positive', 'resolved', 'SUPPORTED', 'rct', 0.8, 1.0, 0.0, 0.0, 1.0, '', NULL,
                '{"positive": 1}', '{}'
            )
            """
        )
        con.execute(
            """
            INSERT INTO ac_skg_parameters(param_id, canonical_name, openalex_id, parameter_json, context_json)
            VALUES ('param1', 'teacher_coaching_program', 'W1', '{"estimate": 0.25}', '{}')
            """
        )
        con.execute(
            """
            INSERT INTO ac_skg_simulation_parameters(
                numeric_id, openalex_id, canonical_name, estimate_type, point_estimate, estimate_sign, unit,
                evidence_strength, confidence_interval_json, std_error, linked_claim_ids_json, linked_edges_json,
                context_json, source_layer, uncertainty_source, quality_flags_json
            ) VALUES (
                'num1', 'W1', 'teacher_coaching_program', 'average_treatment_effect', 0.25, 'positive',
                'standard_deviations', 'rct', '[0.1, 0.4]', 0.05, '["claim1"]', '["e_exact"]',
                '{"context_id":"KE","countries":["KE"]}', 'simulation_ready', 'std_error', '[]'
            )
            """
        )
        con.execute(
            """
            INSERT INTO ac_skg_canonization_cache(raw_name, canonical_name, approved)
            VALUES
            ('teacher coaching program', 'teacher_coaching_program', TRUE),
            ('cash transfer', 'social.cash_transfer_program', TRUE)
            """
        )
        con.execute(
            """
            INSERT INTO ac_skg_variable_synonyms(synonym, canonical_name, method, confidence, approved)
            VALUES
            ('teacher coaching', 'teacher_coaching_program', 'manual', 1.0, TRUE),
            ('cash transfers', 'social.cash_transfer_program', 'manual', 1.0, TRUE)
            """
        )


def _create_source_snapshot(
    root: Path,
    *,
    benchmark_metrics: dict[str, float],
    qc_metrics: dict[str, float],
    benchmark_scenarios: list[dict] | None = None,
    suite_scenarios: list[dict] | None = None,
) -> None:
    academic = root / "academic"
    (academic / "graph").mkdir(parents=True, exist_ok=True)
    (academic / "manifests").mkdir(parents=True, exist_ok=True)
    (academic / "publish").mkdir(parents=True, exist_ok=True)

    for rel in best_snapshot._ORIGINAL_COPY_FILES:
        suffix = Path(rel).suffix
        if suffix == ".jsonl":
            _write_jsonl(academic / rel, [{"artifact": rel, "source": root.name}])
        elif suffix == ".json":
            _write_json(academic / rel, {"artifact": rel, "source": root.name})
        else:
            (academic / rel).write_text(f"{root.name}:{rel}\n", encoding="utf-8")

    _write_json(
        academic / "benchmark_suite.json",
        {
            "suite_id": "best_snapshot_suite",
            "scenarios": suite_scenarios or _default_benchmark_scenarios(),
        },
    )
    _write_json(
        academic / "benchmark_report.json",
        {
            "metrics": benchmark_metrics,
            "readiness": {"passed": False},
            "scenarios": benchmark_scenarios or _default_benchmark_report_scenarios(),
        },
    )
    _write_json(academic / "qc_report.json", {"metrics": qc_metrics, "passed": False})
    _write_json(
        academic / "publish" / "academic_pipeline_readiness.json",
        {"readiness": {"consumer_ready": False}, "metrics": benchmark_metrics},
    )
    _write_jsonl(academic / "canonical_review_queue.jsonl", [{"item": "var1"}])
    _write_json(
        academic / "edge_synthesis_report.json",
        {"family_edges": int(qc_metrics.get("family_edge_count", 0))},
    )
    _write_jsonl(academic / "runtime_demand_backlog.jsonl", [{"need_id": "need1"}])
    _write_jsonl(academic / "fulltext_fetch_log.jsonl", [{"work_id": "W1", "status": "ok"}])
    _write_jsonl(academic / "llm_request_log.jsonl", [{"request_id": "req1", "status": "ok"}])
    _write_jsonl(academic / "resolve_extract_errors.jsonl", [{"work_id": "W1", "error": "none"}])
    _write_json(academic / "resolve_extract_progress.json", {"processed": 1, "completed": 1})
    _write_json((root / "pipeline.log"), {"status": "ok", "source": root.name})
    _write_json((root / "pipeline_remaining.log"), {"status": "ok", "source": root.name})
    _write_json((root / "auto_approve.log"), {"status": "ok", "source": root.name})
    _write_json(
        academic / "manifests" / "graph_load.json", {"stage": "graph_load", "source": root.name}
    )
    _write_json(
        academic / "manifests" / "benchmark.json", {"stage": "benchmark", "source": root.name}
    )
    write_publish_manifest(
        manifest_path=academic / "publish" / "manifest.json",
        pipeline="academic",
        artifacts=[academic / "benchmark_report.json", academic / "qc_report.json"],
        qc_report_path=academic / "qc_report.json",
        extra={"snapshot_root": str(root)},
    )


def _create_backup_snapshot(root: Path) -> None:
    academic = root / "academic"
    (academic / "graph").mkdir(parents=True, exist_ok=True)
    (academic / "publish").mkdir(parents=True, exist_ok=True)
    (academic / "manifests").mkdir(parents=True, exist_ok=True)
    (academic / "graph" / "scholar_knowledge.duckdb").write_text("backup-db", encoding="utf-8")
    _write_json(
        academic / "benchmark_report.json",
        {"metrics": {"scholar_query_coverage_ratio": 0.2, "parameter_supported_ratio": 0.1}},
    )
    _write_json(
        academic / "qc_report.json", {"metrics": {"global_canonical_resolution_rate_pct": 80.0}}
    )
    _write_json(
        academic / "publish" / "academic_pipeline_readiness.json",
        {"readiness": {"consumer_ready": True}},
    )
    write_publish_manifest(
        manifest_path=academic / "publish" / "manifest.json",
        pipeline="academic",
        artifacts=[academic / "benchmark_report.json", academic / "qc_report.json"],
        qc_report_path=academic / "qc_report.json",
        extra={"snapshot_root": str(root)},
    )
    _write_json(academic / "manifests" / "publish.json", {"stage": "publish"})


def _install_stage_fakes(
    monkeypatch,
    *,
    benchmark_metrics: dict[str, float],
    qc_metrics: dict[str, float],
    benchmark_scenarios: list[dict] | None = None,
) -> None:
    def fake_graph_index(config):  # type: ignore[no-untyped-def]
        write_stage_manifest(
            manifest_path=config.manifests_dir / "graph_index.json",
            stage="graph_index",
            status="ok",
            metrics={},
            artifacts=[config.db_path],
        )

    def fake_transport_score(config):  # type: ignore[no-untyped-def]
        _write_jsonl(
            config.transport_scores_path,
            [{"edge_id": "e_exact", "transport_confidence": 0.82, "target_context_id": "UA"}],
        )
        write_stage_manifest(
            manifest_path=config.manifests_dir / "transport_score.json",
            stage="transport_score",
            status="ok",
            metrics={"edges_scored": 1, "profiles_built": 1, "transport_scores_written": 1},
            artifacts=[config.db_path, config.transport_scores_path],
        )
        return {"edges_scored": 1, "profiles_built": 1, "transport_scores_written": 1}

    def fake_embed(config, *, thermal=False):  # type: ignore[no-untyped-def]
        del thermal
        (config.index_dir / "ac_work_embeddings.npz").write_bytes(b"npz")
        (config.index_dir / "ac_work_index.hnsw").write_bytes(b"hnsw")
        write_stage_manifest(
            manifest_path=config.manifests_dir / "embed.json",
            stage="embed",
            status="ok",
            metrics={
                "embedded": 1,
                "embedding_model": config.embedding_model,
                "embedding_dimension": config.embedding_dimension,
            },
            artifacts=[
                config.index_dir / "ac_work_embeddings.npz",
                config.index_dir / "ac_work_index.hnsw",
            ],
        )
        return 1

    def fake_benchmark(config):  # type: ignore[no-untyped-def]
        _write_jsonl(config.runtime_demand_backlog_path, [{"need_id": "need-runtime"}])
        _write_json(
            config.benchmark_report_path,
            {
                "snapshot_root": str(config.snapshot_root),
                "component_dir": str(config.component_dir),
                "metrics": benchmark_metrics,
                "runtime_demand_backlog": {
                    "path": str(config.runtime_demand_backlog_path),
                    "items": 1,
                },
                "readiness": {"passed": True, "failed_checks": []},
                "scenarios": benchmark_scenarios or _default_benchmark_report_scenarios(),
            },
        )
        write_stage_manifest(
            manifest_path=config.manifests_dir / "benchmark.json",
            stage="benchmark",
            status="ok",
            metrics=benchmark_metrics,
            artifacts=[
                config.benchmark_suite_path,
                config.benchmark_report_path,
                config.runtime_demand_backlog_path,
            ],
        )
        return BenchmarkOutcome(
            report_path=config.benchmark_report_path,
            metrics=benchmark_metrics,
            passed=True,
            failed_checks=(),
        )

    def fake_qc(config, *, fail_fast=False):  # type: ignore[no-untyped-def]
        del fail_fast
        _write_json(config.qc_report_path, {"metrics": qc_metrics, "passed": True, "checks": []})
        write_stage_manifest(
            manifest_path=config.manifests_dir / "qc.json",
            stage="qc",
            status="ok",
            metrics=qc_metrics,
            artifacts=[config.qc_report_path],
        )
        return SimpleNamespace(passed=True)

    def fake_publish(config):  # type: ignore[no-untyped-def]
        readiness = {
            "consumer_ready": True,
            "canonical_runtime_ready": True,
            "parameter_utility_ready": True,
            "causal_prior_utility_ready": True,
            "cross_graph_utility_ready": True,
            "transport_utility_ready": True,
            "scholar_retrieval_ready": True,
            "operational_stability_ready": True,
        }
        _write_json(
            config.readiness_report_path,
            {
                "kind": "academic_pipeline_readiness",
                "snapshot_root": str(config.snapshot_root),
                "component_dir": str(config.component_dir),
                "readiness": readiness,
                "artifacts": {
                    "benchmark_report": str(config.benchmark_report_path),
                    "qc_report": str(config.qc_report_path),
                    "runtime_demand_backlog": str(config.runtime_demand_backlog_path),
                },
            },
        )
        manifest = write_publish_manifest(
            manifest_path=config.publish_manifest_path,
            pipeline="academic",
            artifacts=[
                config.db_path,
                config.index_dir / "ac_work_embeddings.npz",
                config.index_dir / "ac_work_index.hnsw",
                config.benchmark_suite_path,
                config.benchmark_report_path,
                config.runtime_demand_backlog_path,
                config.qc_report_path,
                config.edge_synthesis_report_path,
                config.canonical_review_queue_path,
                config.transport_scores_path,
                config.readiness_report_path,
                config.manifests_dir / "graph_index.json",
                config.manifests_dir / "transport_score.json",
                config.manifests_dir / "embed.json",
                config.manifests_dir / "benchmark.json",
                config.manifests_dir / "qc.json",
            ],
            qc_report_path=config.qc_report_path,
            extra={
                "snapshot_root": str(config.snapshot_root),
                "component_dir": str(config.component_dir),
                "readiness_report": str(config.readiness_report_path),
                "readiness": readiness,
            },
        )
        write_stage_manifest(
            manifest_path=config.manifests_dir / "publish.json",
            stage="publish",
            status="ok",
            metrics={"artifacts": 16},
            artifacts=[manifest],
        )
        return manifest

    monkeypatch.setattr(best_snapshot, "run_graph_index", fake_graph_index)
    monkeypatch.setattr(best_snapshot, "run_transport_score", fake_transport_score)
    monkeypatch.setattr(best_snapshot, "run_embed", fake_embed)
    monkeypatch.setattr(best_snapshot, "run_benchmark", fake_benchmark)
    monkeypatch.setattr(best_snapshot, "run_qc", fake_qc)
    monkeypatch.setattr(best_snapshot, "run_publish", fake_publish)
    monkeypatch.setattr(
        best_snapshot.ScholarKnowledgeGraph,
        "_get_query_embedding",
        lambda self, query: None,
    )


def _prepare_snapshot_sources(tmp_path: Path) -> tuple[Path, Path, Path]:
    original_root = tmp_path / "original"
    remap_root = tmp_path / "remap"
    backup_root = tmp_path / "backup"

    _create_source_snapshot(
        original_root,
        benchmark_metrics={
            "scholar_query_coverage_ratio": 0.30,
            "parameter_supported_ratio": 0.20,
            "causal_supported_plus_mixed_ratio": 0.30,
            "non_default_transport_evidence_ratio": 0.20,
            "runtime_demanded_canonical_resolution_rate_pct": 80.0,
        },
        qc_metrics={
            "runtime_demanded_canonical_resolution_rate_pct": 80.0,
            "global_canonical_resolution_rate_pct": 20.0,
            "family_edge_count": 1,
        },
    )
    _create_remap_db(remap_root / "academic" / "graph" / "scholar_knowledge.duckdb")
    _write_jsonl(
        remap_root / "academic" / "canonical_review_queue.jsonl", [{"canonical_name": "leftover"}]
    )
    _write_json(remap_root / "academic" / "edge_synthesis_report.json", {"family_edges": 5})
    _write_json(
        remap_root / "academic" / "manifests" / "edge_synthesize.json", {"stage": "edge_synthesize"}
    )
    _write_json(remap_root / "publish" / "manifest.json", {"unused": True})

    _create_original_db(original_root / "academic" / "graph" / "scholar_knowledge.duckdb")
    _create_backup_snapshot(backup_root)

    return original_root, remap_root, backup_root


def test_build_runtime_first_snapshot_promotes_and_rewrites_paths(tmp_path, monkeypatch) -> None:
    original_root, remap_root, backup_root = _prepare_snapshot_sources(tmp_path)
    _install_stage_fakes(
        monkeypatch,
        benchmark_metrics={
            "scholar_query_coverage_ratio": 0.90,
            "parameter_supported_ratio": 0.80,
            "causal_supported_plus_mixed_ratio": 0.90,
            "non_default_transport_evidence_ratio": 0.80,
            "runtime_demanded_canonical_resolution_rate_pct": 100.0,
        },
        qc_metrics={
            "runtime_demanded_canonical_resolution_rate_pct": 100.0,
            "global_canonical_resolution_rate_pct": 98.7,
            "family_edge_count": 16000,
        },
    )

    result = best_snapshot.build_runtime_first_snapshot(
        original_root=original_root,
        remap_root=remap_root,
        backup_root=backup_root,
        output_root=tmp_path / "assembled",
        timestamp="20260410T120000Z",
    )

    assert result.promoted is True
    assert result.best_root == result.final_root
    assert not result.candidate_root.exists()
    assert result.final_root.exists()
    assert (result.final_root / "academic" / "graph" / "scholar_knowledge.duckdb").exists()

    with duckdb.connect(
        str(result.final_root / "academic" / "graph" / "scholar_knowledge.duckdb"), read_only=True
    ) as con:
        version_rows = con.execute(
            "SELECT version_id, n_articles, n_edges, n_variables FROM ac_skg_versions"
        ).fetchall()
        assert version_rows == [(1, 1, 2, 12)]
        assert con.execute("SELECT COUNT(*) FROM ac_works").fetchone()[0] == 1
        assert con.execute("SELECT COUNT(*) FROM ac_skg_variables").fetchone()[0] == 12
        assert con.execute("SELECT DISTINCT skg_version FROM ac_skg_articles").fetchall() == [(1,)]
        assert con.execute("SELECT DISTINCT skg_version FROM ac_skg_edge_evidence").fetchall() == [
            (1,)
        ]
        assert con.execute(
            "SELECT DISTINCT skg_version FROM ac_skg_context_attributes"
        ).fetchall() == [(1,)]
        assert con.execute(
            "SELECT DISTINCT skg_version FROM ac_skg_moderation_edges"
        ).fetchall() == [(1,)]
        assert (
            con.execute(
                "SELECT approved_canonical_name FROM ac_skg_variables WHERE canonical_name = 'fiscal.cash_transfer'"
            ).fetchone()[0]
            == "social.cash_transfer_program"
        )
        assert (
            con.execute(
                "SELECT approved_canonical_name FROM ac_skg_variables WHERE canonical_name = 'governance.procurement_compliance'"
            ).fetchone()[0]
            == "governance.public_procurement_compliance"
        )
        assert (
            con.execute(
                "SELECT COUNT(*) FROM ac_skg_variables WHERE canonical_name = 'economic.consumption_index'"
            ).fetchone()[0]
            == 1
        )
        assert (
            con.execute(
                """
                SELECT COUNT(*)
                FROM ac_skg_variable_synonyms
                WHERE synonym = 'cash transfer programme'
                  AND canonical_name = 'social.cash_transfer_program'
                """
            ).fetchone()[0]
            == 1
        )
        assert (
            con.execute(
                """
                SELECT canonical_name
                FROM ac_skg_canonization_cache
                WHERE raw_name = 'cash transfer'
                """
            ).fetchone()[0]
            == "fiscal.cash_transfer"
        )
        assert (
            con.execute(
                """
                SELECT canonical_name
                FROM ac_skg_canonization_cache
                WHERE raw_name = 'cash transfer programme'
                """
            ).fetchone()[0]
            == "social.cash_transfer_program"
        )

    graph_index_manifest = json.loads(
        (result.final_root / "academic" / "manifests" / "graph_index.json").read_text(
            encoding="utf-8"
        )
    )
    assert str(result.final_root) in graph_index_manifest["artifacts"][0]["path"]

    runtime_sources = json.loads(result.runtime_evidence_sources_path.read_text(encoding="utf-8"))
    assert runtime_sources["academic_db_path"] == str(
        result.final_root / "academic" / "graph" / "scholar_knowledge.duckdb"
    )
    assert runtime_sources["skg_snapshot_ref"].endswith("#v1")

    promotion_report = json.loads(result.promotion_report_path.read_text(encoding="utf-8"))
    assert promotion_report["promoted"] is True
    assert promotion_report["manifest_consistency"]["passed"] is True
    assert promotion_report["functional_checks"]["passed"] is True
    assert promotion_report["gates"]["scenario_runtime_no_regression"] is True
    assert promotion_report["gates"]["gain_floor__family_edge_count"] is True

    assert (
        result.final_root / "meta" / "source_manifests" / "original" / "publish_manifest.json"
    ).exists()
    assert (result.final_root / "diagnostics" / "fulltext_fetch_log.jsonl").exists()


def test_build_runtime_first_snapshot_keeps_candidate_when_gates_fail(
    tmp_path, monkeypatch
) -> None:
    original_root, remap_root, backup_root = _prepare_snapshot_sources(tmp_path)
    _install_stage_fakes(
        monkeypatch,
        benchmark_metrics={
            "scholar_query_coverage_ratio": 0.10,
            "parameter_supported_ratio": 0.80,
            "causal_supported_plus_mixed_ratio": 0.90,
            "non_default_transport_evidence_ratio": 0.80,
            "runtime_demanded_canonical_resolution_rate_pct": 100.0,
        },
        qc_metrics={
            "runtime_demanded_canonical_resolution_rate_pct": 100.0,
            "global_canonical_resolution_rate_pct": 98.7,
            "family_edge_count": 16000,
        },
    )

    result = best_snapshot.build_runtime_first_snapshot(
        original_root=original_root,
        remap_root=remap_root,
        backup_root=backup_root,
        output_root=tmp_path / "assembled",
        timestamp="20260410T130000Z",
    )

    assert result.promoted is False
    assert result.final_root == result.candidate_root
    assert result.best_root is None
    assert result.candidate_root.exists()
    assert not (tmp_path / "assembled" / "policyos_academic_best_20260410T130000Z").exists()

    promotion_report = json.loads(result.promotion_report_path.read_text(encoding="utf-8"))
    assert "scholar_query_coverage_no_regression" in promotion_report["failed_gates"]


def test_build_runtime_first_snapshot_restores_runtime_alias_bridges(tmp_path, monkeypatch) -> None:
    original_root, remap_root, backup_root = _prepare_snapshot_sources(tmp_path)
    _install_stage_fakes(
        monkeypatch,
        benchmark_metrics={
            "scholar_query_coverage_ratio": 0.90,
            "parameter_supported_ratio": 0.80,
            "causal_supported_plus_mixed_ratio": 0.90,
            "non_default_transport_evidence_ratio": 0.80,
            "runtime_demanded_canonical_resolution_rate_pct": 100.0,
        },
        qc_metrics={
            "runtime_demanded_canonical_resolution_rate_pct": 100.0,
            "global_canonical_resolution_rate_pct": 98.7,
            "family_edge_count": 16000,
        },
    )

    result = best_snapshot.build_runtime_first_snapshot(
        original_root=original_root,
        remap_root=remap_root,
        backup_root=backup_root,
        output_root=tmp_path / "assembled",
        timestamp="20260410T150000Z",
        embedding_model="intfloat/multilingual-e5-small",
        embedding_dimension=384,
    )

    query = SKGQuery(
        db_path=result.final_root / "academic" / "graph" / "scholar_knowledge.duckdb",
        index_dir=result.final_root / "academic",
    )
    try:
        social_support = query.query_edge_support(
            cause="social.cash_transfer_program",
            effect="economic.household_consumption",
            support_mode="hybrid",
        )
        education_support = query.query_edge_support(
            cause="education.teacher_coaching",
            effect="education.learning_outcomes",
            support_mode="hybrid",
        )
    finally:
        query.close()

    assert [row.edge_id for row in social_support] == ["e_cash"]
    assert [row.edge_id for row in education_support] == ["e_exact"]

    graph = ScholarKnowledgeGraph(
        db_path=result.final_root / "academic" / "graph" / "scholar_knowledge.duckdb",
        index_dir=result.final_root / "academic",
    )
    try:
        assert graph._embedding_model_name == "intfloat/multilingual-e5-small"
        assert graph.find_causal_evidence(
            "social.cash_transfer_program",
            "economic.household_consumption",
            support_mode="hybrid",
            min_trust=0.0,
        )
        assert graph.find_causal_evidence(
            "education.teacher_coaching",
            "education.learning_outcomes",
            support_mode="hybrid",
            min_trust=0.0,
        )

        graph._get_query_embedding = lambda query_text: np.ones(384, dtype=np.float32)  # type: ignore[method-assign]
        original_vector_search = graph._store.search_works_by_vector
        graph._store.search_works_by_vector = lambda *args, **kwargs: (_ for _ in ()).throw(
            RuntimeError("dim mismatch")
        )  # type: ignore[method-assign]
        try:
            assert graph.find_relevant_works("Teacher coaching", top_k=3)
        finally:
            graph._store.search_works_by_vector = original_vector_search  # type: ignore[method-assign]
    finally:
        graph.close()


def test_build_runtime_first_snapshot_records_scenario_level_regressions(
    tmp_path, monkeypatch
) -> None:
    original_root, remap_root, backup_root = _prepare_snapshot_sources(tmp_path)
    _install_stage_fakes(
        monkeypatch,
        benchmark_metrics={
            "scholar_query_coverage_ratio": 0.90,
            "parameter_supported_ratio": 0.80,
            "causal_supported_plus_mixed_ratio": 0.90,
            "non_default_transport_evidence_ratio": 0.80,
            "runtime_demanded_canonical_resolution_rate_pct": 100.0,
        },
        qc_metrics={
            "runtime_demanded_canonical_resolution_rate_pct": 100.0,
            "global_canonical_resolution_rate_pct": 98.7,
            "family_edge_count": 16000,
        },
        benchmark_scenarios=[
            {
                "scenario_id": "education_human_capital",
                "causal_edges": [{"status": "supported"}],
                "scholar_queries": [{"supported": True}],
            },
            {
                "scenario_id": "social_protection_consumption",
                "causal_edges": [{"status": "unsupported"}],
                "scholar_queries": [{"supported": False}],
            },
        ],
    )

    result = best_snapshot.build_runtime_first_snapshot(
        original_root=original_root,
        remap_root=remap_root,
        backup_root=backup_root,
        output_root=tmp_path / "assembled",
        timestamp="20260410T160000Z",
    )

    assert result.promoted is False
    promotion_report = json.loads(result.promotion_report_path.read_text(encoding="utf-8"))
    assert "scenario_runtime_no_regression" in promotion_report["failed_gates"]
    assert promotion_report["scenario_regressions"] == [
        {
            "scenario_id": "social_protection_consumption",
            "surface": "causal",
            "original_status": "mixed",
            "candidate_status": "unsupported",
        },
        {
            "scenario_id": "social_protection_consumption",
            "surface": "scholar",
            "original_status": "supported",
            "candidate_status": "unsupported",
        },
    ]


def test_build_best_command_dispatches(tmp_path, monkeypatch, capsys) -> None:
    parser = cli._build_parser()
    args = parser.parse_args(
        [
            "build-best",
            "--original-root",
            str(tmp_path / "original"),
            "--remap-root",
            str(tmp_path / "remap"),
            "--backup-root",
            str(tmp_path / "backup"),
            "--output-root",
            str(tmp_path / "out"),
            "--timestamp",
            "20260410T140000Z",
        ]
    )

    def fake_build_runtime_first_snapshot(**kwargs):  # type: ignore[no-untyped-def]
        assert kwargs["timestamp"] == "20260410T140000Z"
        return best_snapshot.RuntimeFirstSnapshotResult(
            timestamp="20260410T140000Z",
            candidate_root=tmp_path / "out" / "policyos_academic_candidate_20260410T140000Z",
            final_root=tmp_path / "out" / "policyos_academic_best_20260410T140000Z",
            best_root=tmp_path / "out" / "policyos_academic_best_20260410T140000Z",
            promoted=True,
            snapshot_version_id=1,
            promotion_report_path=tmp_path / "out" / "promotion_report.json",
            runtime_evidence_sources_path=tmp_path / "out" / "runtime_evidence_sources.json",
        )

    monkeypatch.setattr(
        "polisyos.academic.batch.best_snapshot.build_runtime_first_snapshot",
        fake_build_runtime_first_snapshot,
    )

    cli._cmd_build_best(args)
    out = capsys.readouterr().out
    assert '"promoted": true' in out.lower()
    assert "policyos_academic_best_20260410T140000Z" in out
