from __future__ import annotations

import json

import duckdb

from polisyos.academic.batch.benchmark import run_benchmark
from polisyos.academic.batch.config import AcademicBatchConfig
from polisyos.academic.knowledge.skg_store import ensure_skg_schema


def test_benchmark_reports_runtime_readiness_metrics(tmp_path) -> None:
    config = AcademicBatchConfig(
        snapshot_root=tmp_path / "snap",
        transport_target_context_id="UA",
    )
    with duckdb.connect(str(config.db_path)) as con:
        ensure_skg_schema(con)
        con.execute(
            """
            INSERT INTO ac_skg_edges(edge_id, src, dst, direction, n_articles, article_refs, evidence_strength, confidence, scope_conditions, quality_signals_json)
            VALUES ('e1', 'tax_revenue', 'economic.gdp_growth', 'positive', 2, '["W1","W2"]', 'quasi_natural', 0.82, '[]', '{}')
            """
        )
        con.execute(
            """
            INSERT INTO ac_skg_family_edges(
                family_edge_id, src_family, dst_family, direction, n_articles, n_claims,
                article_refs, claim_refs, evidence_strength, confidence,
                direction_histogram_json, design_tier_histogram_json, design_family_histogram_json,
                candidate_layer, quality_signals_json
            )
            VALUES (
                'fe1', 'tax_revenue', 'economic.gdp_growth', 'positive', 4, 3,
                '["W1","W2","W3","W4"]', '["c1","c2","c3"]', 'meta_analysis', 0.9,
                '{"positive": 4}', '{"1": 2}', '{"rct": 2}', 'family', '{"conflict_flag": false}'
            )
            """
        )
        con.execute(
            """
            INSERT INTO ac_skg_contested_edges(
                contested_edge_id, src_family, dst_family, n_articles, n_claims, article_refs,
                claim_refs, dominant_direction, resolution_status, runtime_support,
                evidence_strength, confidence, direction_histogram_json, quality_signals_json
            )
            VALUES (
                'ce1', 'tax_revenue', 'economic.gdp_growth', 4, 3, '["W1","W2","W3","W4"]',
                '["c1","c2","c3"]', 'mixed', 'contested', 'MIXED',
                'meta_analysis', 0.76, '{"positive": 2, "negative": 2}', '{"conflict_flag": true}'
            )
            """
        )
        con.execute(
            """
            INSERT INTO ac_skg_simulation_parameters(
                numeric_id, openalex_id, canonical_name, estimate_type, point_estimate, estimate_sign, unit,
                evidence_strength, confidence_interval_json, std_error, linked_claim_ids_json, linked_edges_json,
                context_json, source_layer, uncertainty_source, quality_flags_json
            )
            VALUES (
                'n1', 'W1', 'tax_revenue', 'average_treatment_effect', 0.2, 'positive', 'percentage_points',
                'quasi_natural', '[0.1, 0.3]', 0.05, '["c1"]', '["e1"]',
                '{"context_id":"KE","context_label":"Kenya","countries":["KE"]}', 'simulation_ready', 'std_error', '[]'
            )
            """
        )
        con.execute(
            """
            INSERT INTO ac_skg_transport_scores(
                transport_id, edge_id, target_context_id, base_confidence, generic_penalty, context_match_reward,
                transport_confidence, match_mode, matched_moderators_json, skg_version
            )
            VALUES ('t1', 'e1', 'UA', 0.82, 0.0, 0.1, 0.77, 'moderator_match', '["institutional_quality"]', 1)
            """
        )

    config.benchmark_suite_path.write_text(
        json.dumps(
            {
                "suite_id": "test_suite",
                "scenarios": [
                    {
                        "scenario_id": "s1",
                        "title": "Tax and growth",
                        "policy_domain": "fiscal",
                        "causal_edges": [{"cause": "tax_revenue", "effect": "economic.gdp_growth"}],
                        "parameters": ["tax_revenue"],
                        "scholar_queries": [
                            {
                                "cause": "tax_revenue",
                                "effect": "economic.gdp_growth",
                                "support_mode": "hybrid",
                                "min_results": 1,
                            }
                        ],
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    outcome = run_benchmark(config)

    assert outcome.metrics["causal_supported_ratio"] == 1.0
    assert outcome.metrics["parameter_supported_ratio"] == 1.0
    assert outcome.metrics["scholar_query_coverage_ratio"] == 1.0
    assert outcome.metrics["non_default_transport_evidence_ratio"] == 1.0
    assert outcome.metrics["family_edge_coverage_ratio"] == 1.0
    assert outcome.metrics["contested_edge_coverage_ratio"] == 1.0
    report = json.loads(config.benchmark_report_path.read_text(encoding="utf-8"))
    assert report["readiness"]["passed"] is True
    assert report["scenarios"][0]["causal_edges"][0]["family_matches"]
    assert report["scenarios"][0]["causal_edges"][0]["contested_matches"]


def test_benchmark_applies_scenario_specific_credibility_policy(tmp_path) -> None:
    config = AcademicBatchConfig(snapshot_root=tmp_path / "snap")
    with duckdb.connect(str(config.db_path)) as con:
        ensure_skg_schema(con)
        con.execute(
            """
            INSERT INTO ac_skg_articles(openalex_id, title, year, extraction_json, context_json, retracted, skg_version)
            VALUES ('W_old_1', 'Old evidence 1', 2005, '{}', '{}', FALSE, 1),
                   ('W_old_2', 'Old evidence 2', 2006, '{}', '{}', FALSE, 1)
            """
        )
        con.execute(
            """
            INSERT INTO ac_skg_edges(edge_id, src, dst, direction, n_articles, article_refs, evidence_strength, confidence, scope_conditions, quality_signals_json)
            VALUES ('e_old', 'digital.infrastructure_quality', 'economic.firm_productivity', 'positive', 2, '["W_old_1","W_old_2"]', 'quasi_natural', 0.85, '[]', '{}')
            """
        )

    config.benchmark_suite_path.write_text(
        json.dumps(
            {
                "suite_id": "policy_suite",
                "scenarios": [
                    {
                        "scenario_id": "digital_recent_only",
                        "title": "Digital productivity needs recent evidence",
                        "policy_domain": "digital",
                        "credibility_policy": {
                            "min_confidence": 0.8,
                            "min_unique_works": 2,
                            "require_conflict_free": True,
                            "max_evidence_age_years": 10,
                        },
                        "causal_edges": [
                            {
                                "cause": "digital.infrastructure_quality",
                                "effect": "economic.firm_productivity",
                            }
                        ],
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    outcome = run_benchmark(config)

    assert outcome.metrics["causal_supported_ratio"] == 0.0
    report = json.loads(config.benchmark_report_path.read_text(encoding="utf-8"))
    edge_report = report["scenarios"][0]["causal_edges"][0]
    assert edge_report["status"] == "mixed"
    assert edge_report["policy_checks"][0]["passed"] is False
    assert "evidence_too_old" in edge_report["policy_checks"][0]["reasons"]


def test_benchmark_writes_runtime_demand_backlog_and_canonical_metrics(tmp_path) -> None:
    config = AcademicBatchConfig(snapshot_root=tmp_path / "snap")
    with duckdb.connect(str(config.db_path)) as con:
        ensure_skg_schema(con)

    config.benchmark_suite_path.write_text(
        json.dumps(
            {
                "suite_id": "runtime_suite",
                "scenarios": [
                    {
                        "scenario_id": "education_runtime",
                        "title": "Teacher coaching runtime need",
                        "policy_domain": "education",
                        "causal_edges": [
                            {
                                "cause": "teacher_coaching_program",
                                "effect": "student_learning",
                            }
                        ],
                        "parameters": ["teacher_coaching_program"],
                        "scholar_queries": [
                            {
                                "cause": "teacher_coaching_program",
                                "effect": "student_learning",
                                "support_mode": "hybrid",
                                "min_results": 1,
                            }
                        ],
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    outcome = run_benchmark(config)

    assert outcome.metrics["runtime_demanded_canonical_resolution_rate_pct"] == 100.0
    assert config.runtime_demand_backlog_path.exists()
    backlog_rows = [
        json.loads(line)
        for line in config.runtime_demand_backlog_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert backlog_rows
    assert any(item["need_type"] == "causal_edge" for item in backlog_rows)
    assert any("harvest_literature_for_causal_pair" in item["recommended_actions"] for item in backlog_rows)
    report = json.loads(config.benchmark_report_path.read_text(encoding="utf-8"))
    assert report["runtime_demand_backlog"]["items"] == len(backlog_rows)
