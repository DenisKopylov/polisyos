from __future__ import annotations

# ruff: noqa: S101
import json
from pathlib import Path

import pytest

from tools.quality.validation import build_policy_evidence_capability_index as builder
from tools.quality.validation import run_universal_outcome_corpus as w12d

REPO_ROOT = Path(__file__).resolve().parents[3]
MANIFEST_PATH = (
    REPO_ROOT
    / "architecture/policy_design_case/"
    "wave12d_universal_outcome_corpus_run_manifest.json"
)
SINGLE_CASE_PATH = (
    REPO_ROOT
    / "tests/fixtures/universal-corpus/cases/ua-msme-affordable-loans-2022.json"
)
G1_FIXTURE_DIR = REPO_ROOT / "tests/fixtures/layer3/g1"


@pytest.fixture(scope="module")
def w12d_s9_report(tmp_path_factory: pytest.TempPathFactory) -> dict[str, object]:
    tmp_path = tmp_path_factory.mktemp("w12d-s9-corpus")
    return w12d.run_w12d_universal_outcome_corpus(
        repo_root=REPO_ROOT,
        corpus_path=REPO_ROOT / "tests/fixtures/universal-corpus",
        graph_output_dir=tmp_path / "graphs",
        hypothesis_ledger_output_dir=tmp_path / "ledgers",
        mode="real_producer",
    )


def _s9_blocks(report: dict[str, object]) -> list[dict[str, object]]:
    return [dict(case["s9_projection_lowering"]) for case in report["cases"]]


def _s10_blocks(report: dict[str, object]) -> list[dict[str, object]]:
    return [dict(case["s10_outcome_prediction"]) for case in report["cases"]]


def _s11_blocks(report: dict[str, object]) -> list[dict[str, object]]:
    return [dict(case["s11_predictive_knowledge"]) for case in report["cases"]]


def _s12_blocks(report: dict[str, object]) -> list[dict[str, object]]:
    return [dict(case["s12_resource_economics"]) for case in report["cases"]]


def _s13_blocks(report: dict[str, object]) -> list[dict[str, object]]:
    return [dict(case["s13_post_deploy_accountability"]) for case in report["cases"]]


def _s14_blocks(report: dict[str, object]) -> list[dict[str, object]]:
    return [dict(case["s14_universality_assurance"]) for case in report["cases"]]


def _g0_blocks(report: dict[str, object]) -> list[dict[str, object]]:
    return [dict(case["layer3_g0_grounding_gate"]) for case in report["cases"]]


def _g1_fixture(name: str) -> dict[str, object]:
    return json.loads((G1_FIXTURE_DIR / name).read_text(encoding="utf-8"))


def test_w12d_construct_lookup_reads_governed_rows_without_legacy_fallback(
    tmp_path: Path,
) -> None:
    pdc_dir = tmp_path / "architecture/policy_design_case"
    pdc_dir.mkdir(parents=True)
    (pdc_dir / "layer2_s3_governed_capability_rows.json").write_text(
        json.dumps(
            {
                "scenario_family_construct_rows": [
                    {
                        "scenario_family": "solar_credit_panel",
                        "construct": "solar_credit_access",
                        "producer_ref": "producer://test/solar-credit-panel",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    assert (
        w12d._first_construct_ref(
            {"required_data_families": ["solar-credit-panel"]},
            repo_root=tmp_path,
        )
        == "solar_credit_access"
    )
    assert (
        w12d._first_construct_ref(
            {"required_data_families": ["unknown-family"]},
            repo_root=tmp_path,
        )
        is None
    )


def test_w12d_manifest_is_deterministic_and_runs_real_corpus() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    assert manifest == w12d.build_w12d_manifest()
    assert manifest["schema_version"] == w12d.MANIFEST_SCHEMA_VERSION
    assert manifest["phase_id"] == "W12.D"
    assert manifest["command_contract"]["synthetic_fixture_substitution_allowed"] is False
    assert "--corpus tests/fixtures/universal-corpus" in manifest["command_contract"]["command"]
    assert (
        "--capability-index "
        "_build/.tmp/production-quality/capability-index/capability_index_v1.duckdb"
        in manifest["command_contract"]["command"]
    )
    assert manifest["metric_policy"]["useful_design_outcomes"] == [
        "pass",
        "publish-with-limitation",
    ]
    assert manifest["metric_policy"]["typed_blockers_count_as_useful_design"] is False
    assert (
        manifest["metric_policy"]["layer3_g0_pre_adapter_blocks_count_as_useful_design"]
        is False
    )
    assert (
        manifest["metric_policy"][
            "no_hit_domain_ceiling_requires_g1_search_adapter"
        ]
        is True
    )
    assert manifest["layer3_g0_pre_adapter_readiness"] == {
        "readiness_gate_ref": (
            "repo://architecture/policy_design_case/layer3_g0_readiness_manifest.json"
        ),
        "schema_version": "policyos.policy_design_case.layer3_g0_discovery_search.v2",
        "rule_version": "policyos.layer3.g0.discovery_search_free_growth.v2",
        "not_grounded_conversion_slice": True,
        "no_hit_domain_ceiling_summary_allowed_before_g1": False,
        "g1_search_adapter_required_for_no_hit_domain_ceiling": True,
    }
    assert manifest["w6_w7_w8_chain"] == {
        "universal_compilation_kernel": "W6",
        "producer_pipeline": "W7",
        "runtime_pdc_graph": "W8.A",
    }


def test_w12d_report_keeps_typed_blockers_out_of_useful_design() -> None:
    report = w12d.build_w12d_universal_outcome_corpus_report(
        case_results=[
            _case_result(
                case_id="useful-case",
                domain="housing",
                authority_level="production",
                outcome="publish-with-limitation",
                expert_label="limitation_required",
                runtime_pdc_graph_status="pass",
            ),
            _case_result(
                case_id="blocked-case",
                domain="tax",
                authority_level="production",
                outcome="typed_blocker",
                expert_label="false_pass",
                runtime_pdc_graph_status="blocked",
            ),
        ],
        repo_root=REPO_ROOT,
        corpus_ref="repo://tests/fixtures/universal-corpus",
    )

    assert report["status"] == "pass"
    assert report["summary"]["case_count"] == 2
    assert report["summary"]["outcome_counts"] == {
        "accepted_deficit": 0,
        "pass": 0,
        "publish-with-limitation": 1,
        "typed_blocker": 1,
    }
    assert report["summary"]["useful_design_rate"] == 0.5
    assert report["summary"]["closeout_honesty_rate"] == 1.0
    assert report["summary"]["expected_negative_control_count"] == 1
    assert report["summary"]["unexpected_typed_blocker_count"] == 0
    assert report["summary"]["rollout_blocker_count"] == 0
    assert report["rollout_blockers"] == []
    production = report["authority_level_metric_stratification"]["production"]
    assert production["case_count"] == 2
    assert production["useful_design_count"] == 1
    assert production["typed_blocker_count"] == 1
    assert production["useful_design_rate"] == 0.5

    blocker = report["typed_blockers"][0]
    assert blocker["case_id"] == "blocked-case"
    assert blocker["code"] == "w12d_runtime_pdc_graph_blocked"
    assert blocker["counts_as_useful_design"] is False
    assert blocker["counts_as_closeout_honesty_failure"] is False
    assert blocker["blocks_rollout_posture"] is False
    assert blocker["expected_negative_control"] is True


def test_w12d_runs_single_real_case_through_w6_w7_w8(tmp_path: Path) -> None:
    report = w12d.run_w12d_universal_outcome_corpus(
        repo_root=REPO_ROOT,
        corpus_path=SINGLE_CASE_PATH,
        graph_output_dir=tmp_path / "graphs",
    )

    assert report["schema_version"] == w12d.SCHEMA_VERSION
    assert report["summary"]["case_count"] == 1
    case = report["cases"][0]
    assert case["case_id"] == "ua-msme-affordable-loans-2022"
    assert case["universal_compilation"]["status"] == "pass"
    assert case["producer_pipeline"]["status"] == "blocked"
    assert case["runtime_pdc_graph"]["status"] == "pass"
    assert case["runtime_pdc_graph"]["graph_ref"].startswith("sha256:")
    assert case["evidence_bound_pdc_graph"]["artifact_ref"].startswith("repo://")
    assert case["outcome"] == "typed_blocker"
    assert case["counts_toward_useful_design"] is False
    assert "w12d_producer_pipeline_blocked" in {
        blocker["code"] for blocker in case["typed_blockers"]
    }
    assert case["expert_adjudication_delta"]["expert_label"] == "limitation_required"
    assert case["expert_adjudication_delta"]["expected_outcome"] == (
        "publish-with-limitation"
    )
    assert case["expert_adjudication_delta"]["status"] == "delta"


def test_w12d_corpus_stub_mode_can_produce_useful_design_without_production_authority(
    tmp_path: Path,
) -> None:
    stub_dir = tmp_path / "producer-stubs"
    stub_dir.mkdir()
    (stub_dir / "ua-msme-affordable-loans-2022.producer_stubs.json").write_text(
        json.dumps(
            {
                "case_id": "ua-msme-affordable-loans-2022",
                "mode": "corpus_stub",
                "max_authority_posture": "governed-pilot",
                "fabric": {"*": "selected"},
                "lex": {"*": "selected"},
                "foundry": {"*": "selected"},
                "scholar": {"*": "selected"},
                "participation": {"*": "limited"},
            }
        ),
        encoding="utf-8",
    )
    index_dir = tmp_path / "capability-index"
    assert builder.main(["--mode", "fixture", "--output-dir", str(index_dir)]) == 0

    report = w12d.run_w12d_universal_outcome_corpus(
        repo_root=REPO_ROOT,
        corpus_path=SINGLE_CASE_PATH,
        graph_output_dir=tmp_path / "graphs",
        hypothesis_ledger_output_dir=tmp_path / "ledgers",
        mode="corpus_stub",
        producer_stub_dir=stub_dir,
        capability_index_path=index_dir / "capability_index_v1.duckdb",
    )

    assert report["mode"] == "corpus_stub"
    assert report["summary"]["runtime_useful_design_rate"] == 1.0
    assert report["summary"]["useful_design_alignment_rate"] == 1.0
    assert report["summary"]["closeout_honesty_rate"] == 1.0
    case = report["cases"][0]
    assert case["producer_pipeline"]["status"] == "pass"
    assert case["outcome"] == "publish-with-limitation"
    assert case["conversion_outcome"] == "not_attempted_g0_pre_adapter"
    assert case["layer3_g0_grounding_gate"]["counts_as_useful_design"] is False
    assert report["summary"]["grounded_conversion_count"] == 0
    assert case["corpus_stub"]["max_authority_posture"] == "governed-pilot"
    assert "production_closeout_authority" in case["corpus_stub"]["may_not_use_for"]


def test_w12d_layer3_g0_blocks_all_corpus_conversion_without_useful_design_credit(
    tmp_path: Path,
) -> None:
    report = _run_full_corpus_report(tmp_path)
    gates = _g0_blocks(report)

    assert report["summary"]["case_count"] == 13
    assert report["summary"]["grounded_conversion_count"] == 0
    assert report["summary"]["layer3_g0_pre_adapter_block_count"] == 13
    assert report["summary"]["first_vertical_corpus_case_id"] == (
        "ua-msme-affordable-loans-2022"
    )
    assert report["summary"]["first_vertical_construct_bundle_id"] == (
        "ukrainian_msme_credit_constructs"
    )
    assert len(gates) == 13
    assert all(gate["status"] == "blocked_pre_adapter" for gate in gates)
    assert all(
        gate["conversion_outcome"] == "not_attempted_g0_pre_adapter"
        for gate in gates
    )
    assert all(gate["admitted_adapter_count"] == 0 for gate in gates)
    assert all(gate["grounded_conversion_count"] == 0 for gate in gates)
    assert all(gate["counts_as_useful_design"] is False for gate in gates)
    assert all(
        gate["first_vertical_corpus_case_id"] == "ua-msme-affordable-loans-2022"
        for gate in gates
    )
    assert all(
        gate["first_vertical_construct_bundle_id"]
        == "ukrainian_msme_credit_constructs"
        for gate in gates
    )
    assert all(
        case["conversion_outcome"] == "not_attempted_g0_pre_adapter"
        for case in report["cases"]
    )
    assert all(
        blocker["counts_as_useful_design"] is False
        for blocker in report["typed_blockers"]
    )
    assert report["summary"]["runtime_useful_design_count"] == report["summary"][
        "useful_design_count"
    ]


def test_w12d_layer3_g0_readiness_blocks_no_hit_domain_ceiling_summaries() -> None:
    report = w12d.build_w12d_universal_outcome_corpus_report(
        case_results=[
            _case_result(
                case_id="blocked-case",
                domain="housing",
                authority_level="production",
                outcome="typed_blocker",
                expert_label="false_pass",
                runtime_pdc_graph_status="blocked",
            )
        ],
        repo_root=REPO_ROOT,
        corpus_ref="repo://tests/fixtures/universal-corpus",
    )

    readiness = report["layer3_g0_pre_adapter_readiness"]
    gate = report["cases"][0]["layer3_g0_grounding_gate"]

    assert readiness["not_grounded_conversion_slice"] is True
    assert readiness["search_recall_seed_status"] == "pass"
    assert readiness["index_freshness_status"] == "pass"
    assert readiness["free_growth_fixture_status"] == "pass"
    assert readiness["mechanism_generality_fixture_status"] == "pass"
    assert readiness["no_hit_domain_ceiling_summary_allowed_before_g1"] is False
    assert readiness["g1_search_adapter_required_for_no_hit_domain_ceiling"] is True
    assert report["summary"]["no_hit_domain_ceiling_summary_allowed"] is False
    assert report["summary"]["g1_search_adapter_required_for_no_hit_domain_ceiling"] is True
    assert gate["no_hit_domain_ceiling_summary_allowed"] is False
    assert gate["search_ceiling_blocks_domain_ceiling"] is True
    assert "domain_ceiling" in gate["authority_boundary"]["may_not_use_for"]


def test_w12d_layer3_g1_records_first_vertical_grounding_without_claim_authority() -> None:
    report = w12d.build_w12d_universal_outcome_corpus_report(
        case_results=[
            _case_result(
                case_id="ua-msme-affordable-loans-2022",
                domain="fiscal_support",
                authority_level="production",
                outcome="typed_blocker",
                expert_label="limitation_required",
                runtime_pdc_graph_status="blocked",
            )
        ],
        repo_root=REPO_ROOT,
        corpus_ref="repo://tests/fixtures/universal-corpus",
    )

    case = report["cases"][0]
    gate = case["layer3_g1_grounding_gate"]

    assert gate["schema_version"] == "policyos.policy_design_case.layer3_g1_grounding_gate.v1"
    assert gate["case_id"] == "ua-msme-affordable-loans-2022"
    assert gate["construct_bundle_id"] == "ukrainian_msme_credit_constructs"
    assert gate["counts_as_useful_design"] is False
    assert gate["production_claim_authority_count"] == 0
    assert gate["useful_design_credit_count"] == 0
    assert "claim_authority" in gate["may_not_use_for"]
    assert "search_hit_as_authority" in gate["may_not_use_for"]
    assert report["summary"]["layer3_g1_useful_design_credit_count"] == 0
    assert report["summary"]["layer3_g1_claim_authority_leak_count"] == 0


def test_w12d_layer3_g1_raw_fixture_binding_does_not_count_as_grounded() -> None:
    case = _case_result(
        case_id="ua-msme-affordable-loans-2022",
        domain="fiscal_support",
        authority_level="production",
        outcome="typed_blocker",
        expert_label="limitation_required",
        runtime_pdc_graph_status="blocked",
    )
    case["layer3_g1_candidate_fixture"] = _g1_fixture(
        "raw_data_forge_output_without_adapter.json"
    )["payload"]

    report = w12d.build_w12d_universal_outcome_corpus_report(
        case_results=[case],
        repo_root=REPO_ROOT,
        corpus_ref="repo://tests/fixtures/universal-corpus",
    )

    gate = report["cases"][0]["layer3_g1_grounding_gate"]

    assert gate["grounded_construct_refs"] == []
    assert gate["grounded_or_uncertain_construct_count"] == 0
    assert gate["counts_as_useful_design"] is False
    assert "layer3_g1_raw_output_without_adapter" in gate["issue_codes"]
    assert report["summary"]["layer3_g1_grounded_or_uncertain_construct_count"] == 0


def test_w12d_layer3_g1_gate_is_inserted_before_summary_without_overwriting_g0_conversion_outcome() -> None:
    report = w12d.build_w12d_universal_outcome_corpus_report(
        case_results=[
            _case_result(
                case_id="ua-msme-affordable-loans-2022",
                domain="fiscal_support",
                authority_level="production",
                outcome="typed_blocker",
                expert_label="limitation_required",
                runtime_pdc_graph_status="blocked",
            )
        ],
        repo_root=REPO_ROOT,
        corpus_ref="repo://tests/fixtures/universal-corpus",
    )

    case = report["cases"][0]
    gate = case["layer3_g1_grounding_gate"]

    assert case["conversion_outcome"] == "not_attempted_g0_pre_adapter"
    assert case["layer3_g0_grounding_gate"]["conversion_outcome"] == (
        "not_attempted_g0_pre_adapter"
    )
    assert gate["layer3_g1_grounding_outcome"] == report["summary"][
        "layer3_g1_grounding_closure_outcome"
    ]
    assert report["summary"]["layer3_g1_w12d_conversion_outcome_overwrite_count"] == 0
    assert report["summary"]["layer3_g1_w12d_gate_injection_order"] == (
        "after_g0_before_summary"
    )


def test_w12d_layer3_g2_forecast_gate_consumes_posture_after_g1_without_authority() -> None:
    report = w12d.build_w12d_universal_outcome_corpus_report(
        case_results=[
            _case_result(
                case_id="ua-msme-affordable-loans-2022",
                domain="fiscal_support",
                authority_level="production",
                outcome="typed_blocker",
                expert_label="limitation_required",
                runtime_pdc_graph_status="blocked",
            ),
            _case_result(
                case_id="housing-affordability-2024",
                domain="housing",
                authority_level="research",
                outcome="typed_blocker",
                expert_label="limitation_required",
                runtime_pdc_graph_status="blocked",
            ),
        ],
        repo_root=REPO_ROOT,
        corpus_ref="repo://tests/fixtures/universal-corpus",
    )

    first_case = report["cases"][0]
    lightweight_case = report["cases"][1]
    gate = first_case["layer3_g2_forecast_gate"]

    assert list(first_case).index("layer3_g2_forecast_gate") > list(first_case).index(
        "layer3_g1_grounding_gate"
    )
    assert gate["schema_version"] == "policyos.policy_design_case.layer3_g2_forecast_gate.v1"
    assert gate["status"] == "pass"
    assert gate["posture_consumed"] is True
    assert gate["forecast_tiers"] == ["observable_calibrated"]
    assert gate["forecast_support_refs"]
    assert gate["forecast_calibration_record_refs"]
    assert gate["source_contract_refs"]
    assert gate["method_validity_refs"]
    assert gate["uncertainty_interval_refs"]
    assert gate["full_s2_consumer_case_count"] == 1
    assert gate["lightweight_forecast_posture_ref_count"] == 1
    assert gate["useful_design_delta_count"] == 0
    assert gate["closeout_claimed"] is False
    assert gate["recommendation_authority_claimed"] is False
    assert gate["claim_authority_claimed"] is False
    assert "claim_authority" in gate["may_not_use_for"]
    assert first_case["conversion_outcome"] == first_case["layer3_g0_grounding_gate"][
        "conversion_outcome"
    ]
    assert lightweight_case["layer3_g2_forecast_gate"]["status"] == "pass"
    assert lightweight_case["layer3_g2_forecast_gate"]["posture_consumed"] is False
    assert lightweight_case["layer3_g2_forecast_gate"]["lightweight_posture_ref"]
    assert report["summary"]["layer3_g2_w12d_gate_injection_order"] == (
        "after_g1_before_summary"
    )
    assert report["summary"]["layer3_g2_full_s2_consumer_case_count"] == 1
    assert report["summary"]["layer3_g2_useful_design_delta_count"] == 0


def test_w12d_layer3_g2_domain_ceiling_still_routes_after_g1_without_consumption() -> None:
    case = _case_result(
        case_id="ua-msme-affordable-loans-2022",
        domain="fiscal_support",
        authority_level="production",
        outcome="typed_blocker",
        expert_label="limitation_required",
        runtime_pdc_graph_status="blocked",
    )
    case["layer3_g2_domain_ceiling_status"] = "causal_forecast_domain_ceiling"

    report = w12d.build_w12d_universal_outcome_corpus_report(
        case_results=[case],
        repo_root=REPO_ROOT,
        corpus_ref="repo://tests/fixtures/universal-corpus",
    )

    gate = report["cases"][0]["layer3_g2_forecast_gate"]

    assert "layer3_g1_grounding_gate" in report["cases"][0]
    assert gate["status"] == "pass"
    assert gate["posture_consumed"] is False
    assert gate["domain_ceiling_status"] == "causal_forecast_domain_ceiling"
    assert gate["layer3_g2_gate_injection_order"] == "after_g1_before_summary"
    assert report["summary"]["layer3_g2_domain_ceiling_gate_count"] == 1
    assert report["summary"]["layer3_g2_w12d_not_routed_count"] == 0


def test_w12d_layer3_g1_search_ceiling_does_not_count_as_domain_ceiling() -> None:
    case = _case_result(
        case_id="ua-msme-affordable-loans-2022",
        domain="fiscal_support",
        authority_level="production",
        outcome="typed_blocker",
        expert_label="limitation_required",
        runtime_pdc_graph_status="blocked",
    )
    case["layer3_g1_candidate_fixture"] = _g1_fixture(
        "search_recall_seed_miss_domain_ceiling.json"
    )["payload"]

    report = w12d.build_w12d_universal_outcome_corpus_report(
        case_results=[case],
        repo_root=REPO_ROOT,
        corpus_ref="repo://tests/fixtures/universal-corpus",
    )

    gate = report["cases"][0]["layer3_g1_grounding_gate"]

    assert gate["layer3_g1_grounding_outcome"] == "search_ceiling_repair_required"
    assert gate["grounded_abstention_domain_ceiling_refs"] == []
    assert gate["counts_as_useful_design"] is False
    assert report["summary"]["layer3_g1_grounded_abstention_domain_ceiling_count"] == 0
    assert report["summary"]["layer3_g1_search_ceiling_repair_required_count"] == 1


def test_w12d_canonical_outcome_consumes_s1_governed_closeout_downgrade(
    tmp_path: Path,
) -> None:
    stub_dir = tmp_path / "producer-stubs"
    stub_dir.mkdir()
    (stub_dir / "ua-msme-affordable-loans-2022.producer_stubs.json").write_text(
        json.dumps(
            {
                "case_id": "ua-msme-affordable-loans-2022",
                "mode": "corpus_stub",
                "max_authority_posture": "governed-pilot",
                "fabric": {"*": "selected"},
                "lex": {"*": "selected"},
                "foundry": {"*": "selected"},
                "scholar": {"*": "selected"},
                "participation": {"*": "limited"},
            }
        ),
        encoding="utf-8",
    )
    index_dir = tmp_path / "capability-index"
    assert builder.main(["--mode", "fixture", "--output-dir", str(index_dir)]) == 0

    report = w12d.run_w12d_universal_outcome_corpus(
        repo_root=REPO_ROOT,
        corpus_path=SINGLE_CASE_PATH,
        graph_output_dir=tmp_path / "graphs",
        hypothesis_ledger_output_dir=tmp_path / "ledgers",
        mode="corpus_stub",
        producer_stub_dir=stub_dir,
        capability_index_path=index_dir / "capability_index_v1.duckdb",
    )

    case = report["cases"][0]
    assert case["s1_graded_outcome"]["outcome"] == "publish_with_limitation"
    assert case["s1_graded_outcome"]["closeout_status"] == "closed_with_limitations"
    assert case["s1_graded_outcome"]["decision_owner_ref"]
    assert case["s1_graded_outcome"]["authority_profile_ref"]
    assert case["s1_graded_outcome"]["review_refs"]
    assert case["outcome"] == "publish-with-limitation"
    assert case["expert_adjudication_delta"]["canonical_runtime_outcome"] == (
        "publish-with-limitation"
    )


def test_w12d_corpus_route_emits_s2_shadow_design_search_for_first_proving_case(
    tmp_path: Path,
) -> None:
    report = w12d.run_w12d_universal_outcome_corpus(
        repo_root=REPO_ROOT,
        corpus_path=SINGLE_CASE_PATH,
        graph_output_dir=tmp_path / "graphs",
        hypothesis_ledger_output_dir=tmp_path / "ledgers",
        mode="corpus_stub",
        producer_stub_dir=REPO_ROOT / "tests/fixtures/universal-corpus/producer_stubs",
    )

    case = report["cases"][0]
    s2 = case["s2_design_search"]
    assert s2["status"] in {
        "shadow_ready",
        "acquisition_required",
        "governance_required",
        "blocked",
    }
    assert s2["search_ledger"]["counterexample_conversion_rate"] == 1.0
    assert s2["search_ledger"]["grammar_diversity_minimum"] == 3
    assert set(s2["search_ledger"]["counterexample_class_vocabulary"]) == {
        "real_design_blocker",
        "substrate_gap",
        "a_spec_gap",
        "abstraction_gap",
        "value_gap",
        "budget_gap",
    }
    assert s2["search_ledger"]["acquisition_branch_state"] == "bridge_missing"
    assert s2["design_record"]["projection_status"] == "shadow"
    assert "production_recommendation" in s2["design_record"]["authority_boundary"][
        "may_not_use_for"
    ]


def test_w12d_s2_shadow_search_does_not_change_canonical_closeout_outcome(
    tmp_path: Path,
) -> None:
    report = w12d.run_w12d_universal_outcome_corpus(
        repo_root=REPO_ROOT,
        corpus_path=SINGLE_CASE_PATH,
        graph_output_dir=tmp_path / "graphs",
        hypothesis_ledger_output_dir=tmp_path / "ledgers",
        mode="corpus_stub",
        producer_stub_dir=REPO_ROOT / "tests/fixtures/universal-corpus/producer_stubs",
    )

    case = report["cases"][0]
    assert case["s2_design_search"]["status"] in {
        "shadow_ready",
        "acquisition_required",
        "governance_required",
        "blocked",
    }
    assert case["s2_design_search"]["canonical_outcome_effect"] == "none_shadow_only"
    assert case["outcome"] in {"accepted_deficit", "publish-with-limitation", "typed_blocker"}


def test_w12d_s1_route_does_not_override_production_or_hard_blockers(
    tmp_path: Path,
) -> None:
    index_dir = tmp_path / "capability-index"
    assert builder.main(["--mode", "fixture", "--output-dir", str(index_dir)]) == 0

    governed_report = w12d.run_w12d_universal_outcome_corpus(
        repo_root=REPO_ROOT,
        corpus_path=SINGLE_CASE_PATH,
        graph_output_dir=tmp_path / "governed-graphs",
        hypothesis_ledger_output_dir=tmp_path / "governed-ledgers",
        mode="corpus_stub",
        producer_stub_dir=REPO_ROOT / "tests/fixtures/universal-corpus/producer_stubs",
        capability_index_path=index_dir / "capability_index_v1.duckdb",
    )
    governed_case = governed_report["cases"][0]
    assert governed_case["authority_outcomes"]["governed"]["outcome"] == (
        "publish-with-limitation"
    )
    assert governed_case["authority_outcomes"]["production"]["outcome"] == "typed_blocker"

    blocked_report = w12d.run_w12d_universal_outcome_corpus(
        repo_root=REPO_ROOT,
        corpus_path=SINGLE_CASE_PATH,
        graph_output_dir=tmp_path / "blocked-graphs",
        hypothesis_ledger_output_dir=tmp_path / "blocked-ledgers",
        mode="real_producer",
        capability_index_path=index_dir / "capability_index_v1.duckdb",
    )
    blocked_case = blocked_report["cases"][0]
    assert blocked_case["outcome"] == "typed_blocker"
    assert blocked_case["s1_graded_outcome"]["blocked_by"] in {
        "hard_closeout_blocker",
        "non_overridable_gate",
        "review_required",
        "reissue_required",
    }


def test_w12d_corpus_stub_consumes_capability_index_and_emits_claim_binding_refs(
    tmp_path: Path,
) -> None:
    index_dir = tmp_path / "capability-index"
    assert builder.main(["--mode", "fixture", "--output-dir", str(index_dir)]) == 0

    report = w12d.run_w12d_universal_outcome_corpus(
        repo_root=REPO_ROOT,
        corpus_path=SINGLE_CASE_PATH,
        graph_output_dir=tmp_path / "graphs",
        hypothesis_ledger_output_dir=tmp_path / "ledgers",
        mode="corpus_stub",
        producer_stub_dir=REPO_ROOT / "tests/fixtures/universal-corpus/producer_stubs",
        capability_index_path=index_dir / "capability_index_v1.duckdb",
    )

    case = report["cases"][0]
    trace = case["capability_graph_trace"]
    assert trace["capability_index_loaded"] is True
    assert trace["construct_registry_loaded"] is True
    assert trace["resolver_executed"] is True
    assert trace["producer_binding_emitted"] is True
    assert trace["binding_count"] >= 1
    assert trace["w8e_conflict_signals"]["visible"] is True
    assert trace["w8f_independence_signals"]["visible"] is True
    assert trace["w8f_independence_signals"]["factor_count"] >= trace["binding_count"]

    claim_bindings = case["producer_pipeline"]["claim_bindings"]
    assert claim_bindings
    assert all(binding["capability_ref"] for binding in claim_bindings)
    assert all(binding["construct_ref"] for binding in claim_bindings)
    assert all(binding["capability_refs"] for binding in claim_bindings)
    assert all(binding["construct_refs"] for binding in claim_bindings)


def test_w12d_real_producer_converts_capability_graph_blockers_to_actionable_evidence(
    tmp_path: Path,
) -> None:
    index_dir = tmp_path / "capability-index"
    assert builder.main(["--mode", "fixture", "--output-dir", str(index_dir)]) == 0

    report = w12d.run_w12d_universal_outcome_corpus(
        repo_root=REPO_ROOT,
        corpus_path=SINGLE_CASE_PATH,
        graph_output_dir=tmp_path / "graphs",
        hypothesis_ledger_output_dir=tmp_path / "ledgers",
        mode="real_producer",
        capability_index_path=index_dir / "capability_index_v1.duckdb",
    )

    assert report["status"] == "pass"
    case = report["cases"][0]
    assert case["capability_graph_trace"]["status"] == "pass"
    assert case["producer_pipeline"]["status"] == "blocked"
    assert set(case["producer_pipeline"]["diagnostic_codes"]) & {
        "missing_binding_producers",
        "producer_pipeline_blocked_without_issue_codes",
    }
    blocker_codes = {blocker["code"] for blocker in case["typed_blockers"]}
    assert "w12d_producer_pipeline_blocked" not in blocker_codes
    assert blocker_codes & {
        "blocked_acquisition_required",
        "blocked_construct_validity_below_floor",
        "blocked_sample_size_below_floor",
        "blocked_rights_boundary",
        "blocked_authority_boundary",
    }
    assert all(not blocker["blocks_rollout_posture"] for blocker in report["typed_blockers"])


def test_w12d_real_producer_consumes_s3_closed_acquisition_binding(
    tmp_path: Path,
) -> None:
    index_dir = tmp_path / "capability-index"
    assert builder.main(["--mode", "fixture", "--output-dir", str(index_dir)]) == 0

    report = w12d.run_w12d_universal_outcome_corpus(
        repo_root=REPO_ROOT,
        corpus_path=SINGLE_CASE_PATH,
        graph_output_dir=tmp_path / "graphs",
        hypothesis_ledger_output_dir=tmp_path / "ledgers",
        mode="real_producer",
        capability_index_path=index_dir / "capability_index_v1.duckdb",
    )

    case = report["cases"][0]
    trace = case["capability_graph_trace"]
    s3 = trace["s3_acquisition"]
    assert s3["terminal"] == "closed_as_binding"
    assert s3["construct_status_before_after"] == {
        "before": "blocked_acquisition_required",
        "after": "selected_exact",
    }
    assert s3["frozen"]["capability_index_ref"].startswith(
        "capability-index:layer2-s3-delta:credit_program_enrollment:"
    )

    grounded_rows = [
        binding
        for binding in trace["capability_bindings"]
        if binding.get("construct_ref") == "construct:credit_program_enrollment"
    ]
    assert grounded_rows
    assert {row["status"] for row in grounded_rows} == {"selected_exact"}
    assert all(
        row["capability_index_ref"] == s3["frozen"]["capability_index_ref"]
        for row in grounded_rows
    )
    assert all(
        "production_claim_authority" in row["may_not_use_for"]
        for row in grounded_rows
    )
    assert case["authority_outcomes"]["production"]["outcome"] == "typed_blocker"


def test_w12d_emits_s4_regime_for_13_cases(tmp_path: Path) -> None:
    report = w12d.run_w12d_universal_outcome_corpus(
        repo_root=REPO_ROOT,
        corpus_path=REPO_ROOT / "tests/fixtures/universal-corpus",
        graph_output_dir=tmp_path / "graphs",
        hypothesis_ledger_output_dir=tmp_path / "ledgers",
        mode="real_producer",
    )

    assert report["summary"]["case_count"] == 13
    s4_blocks = [case["s4_epistemic_regime"] for case in report["cases"]]
    assert len(s4_blocks) == 13
    assert {block["classifier_owner"] for block in s4_blocks} == {"A_gate"}
    assert all(block["evidence_basis"]["measurability_present"] is False for block in s4_blocks)
    assert all(block["evidence_basis"]["calibration_present"] is False for block in s4_blocks)
    assert all(block["evidence_basis"]["value_provenance_present"] is False for block in s4_blocks)
    assert all(block["predicted_regime"] != "risk" for block in s4_blocks)
    assert all(block["regime_claim_ref"].startswith("pdc://layer2/s4/") for block in s4_blocks)
    assert all(
        block["commitment_profile_ref"].startswith("pdc://layer2/s4/")
        for block in s4_blocks
    )
    assert all(
        block["axis_projection"]["position"]["cell_ref"] == "KNOWLEDGE.epistemic_regime"
        for block in s4_blocks
    )


def test_w12d_s4_records_w12_hypothesis(tmp_path: Path) -> None:
    report = w12d.run_w12d_universal_outcome_corpus(
        repo_root=REPO_ROOT,
        corpus_path=REPO_ROOT / "tests/fixtures/universal-corpus",
        graph_output_dir=tmp_path / "graphs",
        hypothesis_ledger_output_dir=tmp_path / "ledgers",
        mode="real_producer",
    )

    summary = report["s4_regime_summary"]
    assert summary["case_count"] == 13
    assert "regime_accuracy" in summary
    assert "penalized_score" in summary
    assert 0.0 <= summary["commitment_profile_adequacy"] <= 1.0
    assert summary["w12_overblocking_hypothesis"] in {"confirmed", "revised"}
    assert summary["limitation_required_case_count"] == 9
    assert sum(summary["limitation_required_non_risk_breakdown"].values()) == (
        summary["limitation_required_non_risk_count"]
    )
    assert summary["limitation_required_non_risk_count"] == 9
    assert summary["w12_overblocking_hypothesis"] == "confirmed"
    assert len(summary["per_case_regime_table"]) == 13
    assert all(row["expert_regime"] for row in summary["per_case_regime_table"])


def test_w12d_s4_does_not_change_canonical_closeout_outcome(tmp_path: Path) -> None:
    index_dir = tmp_path / "capability-index"
    assert builder.main(["--mode", "fixture", "--output-dir", str(index_dir)]) == 0

    report = w12d.run_w12d_universal_outcome_corpus(
        repo_root=REPO_ROOT,
        corpus_path=SINGLE_CASE_PATH,
        graph_output_dir=tmp_path / "graphs",
        hypothesis_ledger_output_dir=tmp_path / "ledgers",
        mode="corpus_stub",
        producer_stub_dir=REPO_ROOT / "tests/fixtures/universal-corpus/producer_stubs",
        capability_index_path=index_dir / "capability_index_v1.duckdb",
    )

    case = report["cases"][0]
    assert case["s4_epistemic_regime"]["canonical_outcome_effect"] == "none_shadow_only"
    assert case["outcome"] == "publish-with-limitation"
    assert report["summary"]["closeout_honesty_rate"] == 1.0


def test_w12d_emits_s5_coupling_for_13_cases(tmp_path: Path) -> None:
    report = w12d.run_w12d_universal_outcome_corpus(
        repo_root=REPO_ROOT,
        corpus_path=REPO_ROOT / "tests/fixtures/universal-corpus",
        graph_output_dir=tmp_path / "graphs",
        hypothesis_ledger_output_dir=tmp_path / "ledgers",
        mode="real_producer",
    )

    assert report["summary"]["case_count"] == 13
    s5_blocks = [case["s5_coupling_composition"] for case in report["cases"]]
    assert len(s5_blocks) == 13
    assert {block["classifier_owner"] for block in s5_blocks} == {"A_gate"}
    assert all(block["coupling_graph_ref"].startswith("pdc://layer2/s5/") for block in s5_blocks)
    assert all(
        block["module_discovery_ref"].startswith("pdc://layer2/s5/") for block in s5_blocks
    )
    assert all(
        block["decomposition_result_ref"].startswith("pdc://layer2/s5/") for block in s5_blocks
    )
    assert all(
        block["composition_receipt_ref"].startswith("pdc://layer2/s5/") for block in s5_blocks
    )
    assert all(
        block["tractability_budget_ref"].startswith("pdc://layer2/s5/") for block in s5_blocks
    )
    assert all(block["boundary_coupling_table"] for block in s5_blocks)
    assert all(
        block["predicted_feedback_intensity"] == block["expected_feedback_intensity"]
        for block in s5_blocks
    )
    assert all(
        block["predicted_coupling_regime"] != "modular"
        or block["composition_disposition"] == "compose"
        for block in s5_blocks
    )


def test_w12d_s5_prediction_inputs_do_not_contain_gold_labels() -> None:
    signals = json.loads(
        (
            REPO_ROOT / "tests/fixtures/layer2/s5/s5_coupling_case_signals.json"
        ).read_text(encoding="utf-8")
    )
    forbidden = {
        "expert_coupling_regime",
        "expected_composition_disposition",
        "coupling_matches_gold",
        "composition_matches_gold",
    }

    for entry in signals["cases"].values():
        assert forbidden.isdisjoint(entry)
        for boundary in entry["observed_boundaries"]:
            assert forbidden.isdisjoint(boundary)


def test_w12d_s5_records_coupling_accuracy_and_false_modular_penalty(
    tmp_path: Path,
) -> None:
    report = w12d.run_w12d_universal_outcome_corpus(
        repo_root=REPO_ROOT,
        corpus_path=REPO_ROOT / "tests/fixtures/universal-corpus",
        graph_output_dir=tmp_path / "graphs",
        hypothesis_ledger_output_dir=tmp_path / "ledgers",
        mode="real_producer",
    )

    summary = report["s5_coupling_summary"]
    assert summary["case_count"] == 13
    assert summary["coupling_accuracy"] >= 0.9
    assert summary["penalized_score"] >= 0.9
    assert summary["false_modular_count"] == 0
    assert summary["false_entangled_count"] >= 0
    assert summary["system_evidence_required_count"] >= 1
    assert set(summary["coupling_regime_counts"]) >= {
        "modular",
        "near_decomposable",
        "hierarchically_coupled",
        "entangled",
    }
    assert set(summary["boundary_regime_counts"]) >= {
        "modular",
        "near_decomposable",
        "hierarchically_coupled",
        "entangled",
    }
    assert "simulation_only_system_effect" in summary["system_effect_support_labels"]
    assert len(summary["per_case_coupling_table"]) == 13


def test_w12d_s5_does_not_change_canonical_closeout_outcome(tmp_path: Path) -> None:
    index_dir = tmp_path / "capability-index"
    assert builder.main(["--mode", "fixture", "--output-dir", str(index_dir)]) == 0

    report = w12d.run_w12d_universal_outcome_corpus(
        repo_root=REPO_ROOT,
        corpus_path=SINGLE_CASE_PATH,
        graph_output_dir=tmp_path / "graphs",
        hypothesis_ledger_output_dir=tmp_path / "ledgers",
        mode="corpus_stub",
        producer_stub_dir=REPO_ROOT / "tests/fixtures/universal-corpus/producer_stubs",
        capability_index_path=index_dir / "capability_index_v1.duckdb",
    )

    case = report["cases"][0]
    assert case["s5_coupling_composition"]["canonical_outcome_effect"] == "none_shadow_only"
    assert case["outcome"] == "publish-with-limitation"
    assert report["summary"]["closeout_honesty_rate"] == 1.0


def test_w12d_persists_runtime_critic_report_refs_for_w12c(
    tmp_path: Path,
) -> None:
    stub_dir = tmp_path / "producer-stubs"
    stub_dir.mkdir()
    (stub_dir / "ua-msme-affordable-loans-2022.producer_stubs.json").write_text(
        json.dumps(
            {
                "case_id": "ua-msme-affordable-loans-2022",
                "mode": "corpus_stub",
                "max_authority_posture": "governed-pilot",
                "fabric": {"*": "selected"},
                "lex": {"*": "selected"},
                "foundry": {"*": "selected"},
                "scholar": {"*": "selected"},
                "participation": {"*": "limited"},
            }
        ),
        encoding="utf-8",
    )

    report = w12d.run_w12d_universal_outcome_corpus(
        repo_root=REPO_ROOT,
        corpus_path=SINGLE_CASE_PATH,
        graph_output_dir=tmp_path / "graphs",
        hypothesis_ledger_output_dir=tmp_path / "ledgers",
        critic_report_output_dir=tmp_path / "critic-reports",
        mode="corpus_stub",
        producer_stub_dir=stub_dir,
    )

    case = report["cases"][0]
    critic_ref = case["llm_universal_compilation"]["critic_ensemble_report_ref"]
    assert critic_ref.startswith("repo://")
    critic_path = REPO_ROOT / critic_ref.removeprefix("repo://")
    assert critic_path.exists()
    critic_payload = json.loads(critic_path.read_text(encoding="utf-8"))
    assert critic_payload["case_id"] == "ua-msme-affordable-loans-2022"
    assert len(critic_payload["verdicts"]) > 0


def test_w12d_case_loader_ignores_producer_stub_fixtures() -> None:
    cases, issues = w12d._load_cases(REPO_ROOT / "tests/fixtures/universal-corpus")

    assert issues == []
    assert len(cases) == 13
    assert not any(str(case.get("_source_path")).endswith(".producer_stubs.json") for case in cases)


def test_w12d_cli_writes_report_for_existing_single_case(
    tmp_path: Path,
    monkeypatch,
) -> None:
    output_report = tmp_path / "w12d.json"
    index_dir = tmp_path / "capability-index"
    assert builder.main(["--mode", "fixture", "--output-dir", str(index_dir)]) == 0
    monkeypatch.setattr(
        w12d,
        "DEFAULT_CAPABILITY_INDEX",
        index_dir / "capability_index_v1.duckdb",
    )

    exit_code = w12d.main(
        [
            "--repo-root",
            str(REPO_ROOT),
            "--corpus",
            str(SINGLE_CASE_PATH),
            "--graph-output-dir",
            str(tmp_path / "graphs"),
            "--output",
            str(output_report),
            "--allow-typed-blockers",
        ]
    )

    assert exit_code == 0
    payload = json.loads(output_report.read_text(encoding="utf-8"))
    assert payload["phase_id"] == "W12.D"
    assert payload["summary"]["case_count"] == 1
    assert payload["cases"][0]["runtime_pdc_graph"]["status"] == "pass"
    assert payload["status"] == "pass"
    assert payload["summary"]["runtime_useful_design_rate"] == 0.0
    assert payload["cases"][0]["capability_graph_trace"]["s3_acquisition"][
        "terminal"
    ] == "closed_as_binding"
    assert "w12d_producer_pipeline_blocked" not in {
        blocker["code"] for blocker in payload["typed_blockers"]
    }


def test_w12d_emits_s6_blind_spot_firewalls_for_13_cases(tmp_path: Path) -> None:
    report = _run_full_corpus_report(tmp_path)

    assert report["summary"]["case_count"] == 13
    assert report["s6_blind_spot_summary"]["case_count"] == 13
    s6_blocks = [case["s6_blind_spot_firewalls"] for case in report["cases"]]
    assert len(s6_blocks) == 13
    assert all(block["maturity"] == "fail_closed" for block in s6_blocks)
    assert all(len(block["axis_firewall_table"]) == 5 for block in s6_blocks)
    assert all(block["matches_gold"] is True for block in s6_blocks)
    assert all(block["canonical_outcome_effect"] == "none_shadow_only" for block in s6_blocks)
    assert all(
        block["measurability_record_ref"].startswith("pdc://layer2/s6/")
        for block in s6_blocks
    )
    assert all(
        block["strategic_response_record_ref"].startswith("pdc://layer2/s6/")
        for block in s6_blocks
    )


def test_w12d_s6_records_per_axis_fail_closed_coverage(tmp_path: Path) -> None:
    report = _run_full_corpus_report(tmp_path)

    summary = report["s6_blind_spot_summary"]
    assert summary["axis_coverage_count"] == 5
    assert summary["all_five_axes_covered"] is True
    assert summary["per_axis_fail_closed_negative_control_pass_rate"] == 1.0
    assert summary["false_clear_count"] == 0
    assert set(summary["per_axis_disposition_counts"]) == _S6_AXIS_CELLS
    assert all(
        counts.get("block", 0) + counts.get("limit", 0) >= 1
        for counts in summary["per_axis_disposition_counts"].values()
    )
    assert len(summary["per_case_axis_table"]) == 13


def test_w12d_s6_gold_labels_cover_all_13_cases_and_five_axes() -> None:
    signals = json.loads(
        (
            REPO_ROOT / "tests/fixtures/layer2/s6/s6_blind_spot_case_signals.json"
        ).read_text(encoding="utf-8")
    )
    labels = json.loads(
        (
            REPO_ROOT / "tests/fixtures/layer2/s6/s6_blind_spot_expert_labels.json"
        ).read_text(encoding="utf-8")
    )
    expected_cases = {
        path.stem
        for path in (REPO_ROOT / "tests/fixtures/universal-corpus/cases").glob("*.json")
    }

    assert set(labels["cases"]) == expected_cases
    assert set(signals["cases"]) == expected_cases
    label_fields = {
        "expected_measurability_disposition",
        "expected_aggregation_disposition",
        "expected_capacity_disposition",
        "expected_mandate_disposition",
        "expected_strategic_response_disposition",
        "expected_overall_posture",
        "expected_blocking_axis_refs",
        "expected_limiting_axis_refs",
        "expected_bridge_consumer_refs",
        "expected_c3_authority_dimensions",
    }
    for case_id, row in labels["cases"].items():
        assert label_fields <= set(row), case_id
        assert set(row["expected_bridge_consumer_refs"]) >= _S6_BRIDGE_CONSUMERS
        assert set(row["expected_c3_authority_dimensions"]) == _S6_C3_DIMENSIONS

    forbidden_gold_fields = {
        "expected_measurability_disposition",
        "expected_aggregation_disposition",
        "expected_capacity_disposition",
        "expected_mandate_disposition",
        "expected_strategic_response_disposition",
        "expected_overall_posture",
        "expected_blocking_axis_refs",
        "expected_limiting_axis_refs",
        "matches_gold",
    }
    for row in signals["cases"].values():
        assert forbidden_gold_fields.isdisjoint(row)


def test_w12d_s6_pinned_case_injects_posture_into_s2(tmp_path: Path) -> None:
    index_dir = tmp_path / "capability-index"
    assert builder.main(["--mode", "fixture", "--output-dir", str(index_dir)]) == 0

    report = w12d.run_w12d_universal_outcome_corpus(
        repo_root=REPO_ROOT,
        corpus_path=SINGLE_CASE_PATH,
        graph_output_dir=tmp_path / "graphs",
        hypothesis_ledger_output_dir=tmp_path / "ledgers",
        mode="corpus_stub",
        producer_stub_dir=REPO_ROOT / "tests/fixtures/universal-corpus/producer_stubs",
        capability_index_path=index_dir / "capability_index_v1.duckdb",
    )

    case = report["cases"][0]
    s2 = case["s2_design_search"]
    s6 = case["s6_blind_spot_firewalls"]
    assert s2["status"] in {
        "shadow_ready",
        "acquisition_required",
        "governance_required",
        "blocked",
    }
    assert s2["constraint_store"]["constraint_records"]
    assert {
        row["cell_ref"] for row in s2["constraint_store"]["constraint_records"]
    } >= _S6_AXIS_CELLS
    assert set(
        s2["design_record"]["envelope"]["cluster_authority_dimension_refs"]
    ) == set(s6["cluster_authority_dimension_refs"])
    assert set(s2["design_record"]["ledger_refs"]) >= {
        s6["measurability_record_ref"],
        s6["aggregation_validity_record_ref"],
        s6["capacity_feasibility_record_ref"],
        s6["mandate_legitimacy_record_ref"],
        s6["strategic_response_record_ref"],
    }


def test_w12d_s6_reflexive_other_agents_flow_updates_system_dgp(tmp_path: Path) -> None:
    report = _run_full_corpus_report(tmp_path)

    strategic_blocks = [
        case["s6_blind_spot_firewalls"]
        for case in report["cases"]
        if case["s6_blind_spot_firewalls"]["strategic_response_record"][
            "firewall_disposition"
        ]
        == "block"
    ]
    assert strategic_blocks
    assert all(block["post_intervention_dgp_update_ref"] for block in strategic_blocks)
    assert all(block["system_dynamics_handoff_required"] is True for block in strategic_blocks)
    assert report["s6_blind_spot_summary"]["system_dynamics_handoff_count"] >= len(
        strategic_blocks
    )


def test_w12d_s6_bridge_consumer_table_covers_cluster_map_consumers(
    tmp_path: Path,
) -> None:
    report = _run_full_corpus_report(tmp_path)

    summary = report["s6_blind_spot_summary"]
    assert set(summary["bridge_consumer_coverage"]) >= _S6_BRIDGE_CONSUMERS
    assert all(summary["bridge_consumer_coverage"][ref] is True for ref in _S6_BRIDGE_CONSUMERS)
    for case in report["cases"]:
        rows = case["s6_blind_spot_firewalls"]["bridge_consumer_table"]
        assert {row["consumer_ref"] for row in rows} >= _S6_BRIDGE_CONSUMERS
        assert any(row["pending_consumer"] for row in rows)


def test_w12d_s6_c3_authority_dimension_table_uses_canonical_dimensions(
    tmp_path: Path,
) -> None:
    report = _run_full_corpus_report(tmp_path)

    coverage = report["s6_blind_spot_summary"]["c3_authority_dimension_coverage"]
    assert set(coverage) == _S6_C3_DIMENSIONS
    assert coverage["strategic_robustness"] is True
    assert coverage["response_model_validity"] is True
    for case in report["cases"]:
        rows = case["s6_blind_spot_firewalls"]["c3_authority_dimension_table"]
        assert {row["authority_dimension"] for row in rows} == _S6_C3_DIMENSIONS
        assert all(row["maturity"] == "fail_closed" for row in rows)


def test_w12d_s6_canonical_outcome_effect_remains_shadow_only(tmp_path: Path) -> None:
    index_dir = tmp_path / "capability-index"
    assert builder.main(["--mode", "fixture", "--output-dir", str(index_dir)]) == 0

    report = w12d.run_w12d_universal_outcome_corpus(
        repo_root=REPO_ROOT,
        corpus_path=SINGLE_CASE_PATH,
        graph_output_dir=tmp_path / "graphs",
        hypothesis_ledger_output_dir=tmp_path / "ledgers",
        mode="corpus_stub",
        producer_stub_dir=REPO_ROOT / "tests/fixtures/universal-corpus/producer_stubs",
        capability_index_path=index_dir / "capability_index_v1.duckdb",
    )

    case = report["cases"][0]
    assert case["s6_blind_spot_firewalls"]["canonical_outcome_effect"] == "none_shadow_only"
    assert case["s2_design_search"]["canonical_outcome_effect"] == "none_shadow_only"
    assert case["outcome"] == "publish-with-limitation"
    assert report["summary"]["closeout_honesty_rate"] == 1.0


def test_w12d_emits_s7_delegation_for_13_cases(tmp_path: Path) -> None:
    report = _run_full_corpus_report(tmp_path)

    assert report["summary"]["case_count"] == 13
    assert report["s7_delegation_summary"]["case_count"] == 13
    s7_blocks = [case["s7_delegation"] for case in report["cases"]]
    assert len(s7_blocks) == 13
    assert all(
        block["schema_version"] == "policyos.policy_design_case.layer2_s7_delegation.v1"
        for block in s7_blocks
    )
    assert all(
        block["delegation_contract_ref"].startswith("pdc://layer2/s7/") for block in s7_blocks
    )
    assert all(
        block["decision_rights_matrix_ref"].startswith("pdc://layer2/s7/") for block in s7_blocks
    )
    assert all(
        block["canonical_outcome_effect"] == "none_shadow_or_governed_pilot_only"
        for block in s7_blocks
    )
    assert all(
        "production_claim_authority" in block["authority_boundary"]["may_not_use_for"]
        for block in s7_blocks
    )


def test_w12d_s7_records_precision_recall_and_responsibility_integrity(
    tmp_path: Path,
) -> None:
    report = _run_full_corpus_report(tmp_path)

    summary = report["s7_delegation_summary"]
    assert summary["case_count"] == 13
    assert summary["delegation_precision"] == 1.0
    assert summary["delegation_recall"] == 1.0
    assert summary["responsibility_integrity_pass_rate"] == 1.0
    assert summary["oversight_theater_false_clear_count"] == 0
    assert summary["wrong_role_false_clear_count"] == 0
    assert summary["workflow_only_summary_false_clear_count"] == 0
    assert len(summary["per_case_delegation_table"]) == 13
    assert summary["request_emitted_count"] >= 7
    assert summary["no_interrupt_count"] >= 3
    assert summary["valid_human_decision_record_count"] >= 6


def test_w12d_s7_gold_labels_cover_all_13_cases_and_decision_need_reasons() -> None:
    signals = json.loads(
        (REPO_ROOT / "tests/fixtures/layer2/s7/s7_delegation_case_signals.json").read_text(
            encoding="utf-8"
        )
    )
    labels = json.loads(
        (REPO_ROOT / "tests/fixtures/layer2/s7/s7_delegation_expert_labels.json").read_text(
            encoding="utf-8"
        )
    )
    expected_cases = {
        path.stem for path in (REPO_ROOT / "tests/fixtures/universal-corpus/cases").glob("*.json")
    }

    assert set(labels["cases"]) == expected_cases
    assert set(signals["cases"]) == expected_cases
    label_fields = {
        "expected_need_reasons",
        "expected_interaction_mode",
        "expected_disposition",
        "expected_required_role",
        "expected_request_emitted",
        "expected_record_valid",
        "expected_governed_pilot_eligible",
    }
    observed_reasons = set()
    for case_id, row in labels["cases"].items():
        assert label_fields <= set(row), case_id
        observed_reasons.update(row["expected_need_reasons"])
        assert row["expected_interaction_mode"] != "ai_first"

    assert observed_reasons >= {
        "high_stakes",
        "value_laden",
        "out_of_envelope",
        "mandate_limited",
        "budget_required",
        "acquisition_required",
        "final_choice",
        "low_voi_no_interrupt",
        "routine_in_envelope",
    }
    assert (
        sum(
            1
            for row in labels["cases"].values()
            if row["expected_disposition"] == "blocked_mandate_missing"
        )
        >= 2
    )
    assert any(row["expected_governed_pilot_eligible"] for row in labels["cases"].values())

    forbidden_gold_fields = {
        "expected_need_reasons",
        "expected_interaction_mode",
        "expected_disposition",
        "expected_required_role",
        "expected_request_emitted",
        "expected_record_valid",
        "expected_governed_pilot_eligible",
        "matches_gold",
    }
    for row in signals["cases"].values():
        assert forbidden_gold_fields.isdisjoint(row)


def test_w12d_s7_pinned_case_injects_delegation_posture_into_s2(
    tmp_path: Path,
) -> None:
    index_dir = tmp_path / "capability-index"
    assert builder.main(["--mode", "fixture", "--output-dir", str(index_dir)]) == 0

    report = w12d.run_w12d_universal_outcome_corpus(
        repo_root=REPO_ROOT,
        corpus_path=SINGLE_CASE_PATH,
        graph_output_dir=tmp_path / "graphs",
        hypothesis_ledger_output_dir=tmp_path / "ledgers",
        mode="corpus_stub",
        producer_stub_dir=REPO_ROOT / "tests/fixtures/universal-corpus/producer_stubs",
        capability_index_path=index_dir / "capability_index_v1.duckdb",
    )

    case = report["cases"][0]
    s2 = case["s2_design_search"]
    s7 = case["s7_delegation"]
    assert (
        s2["delegation_posture"]["human_decision_request_ref"] == (s7["human_decision_request_ref"])
    )
    assert any(
        row["cell_ref"] == "CROSS_CUTTING.scientist_orchestration"
        for row in s2["constraint_store"]["constraint_records"]
    )
    assert s7["human_decision_request_ref"] in s2["search_ledger"]["delegation_request_refs"]
    if s7["human_decision_record_ref"] is not None:
        assert s7["human_decision_record_ref"] in s2["search_ledger"]["delegation_record_refs"]
    assert s7["human_decision_request_ref"] in s2["design_record"]["ledger_refs"]


def test_w12d_s7_decision_refs_are_closeout_visible_without_production_authority(
    tmp_path: Path,
) -> None:
    index_dir = tmp_path / "capability-index"
    assert builder.main(["--mode", "fixture", "--output-dir", str(index_dir)]) == 0

    report = w12d.run_w12d_universal_outcome_corpus(
        repo_root=REPO_ROOT,
        corpus_path=SINGLE_CASE_PATH,
        graph_output_dir=tmp_path / "graphs",
        hypothesis_ledger_output_dir=tmp_path / "ledgers",
        mode="corpus_stub",
        producer_stub_dir=REPO_ROOT / "tests/fixtures/universal-corpus/producer_stubs",
        capability_index_path=index_dir / "capability_index_v1.duckdb",
    )

    case = report["cases"][0]
    s7 = case["s7_delegation"]
    closeout = case["closeout_visible_refs"]
    assert s7["human_decision_request_ref"] in closeout["delegation_refs"]
    assert s7["canonical_outcome_effect"] == "none_shadow_or_governed_pilot_only"
    assert case["s2_design_search"]["canonical_outcome_effect"] == "none_shadow_only"
    assert "production_claim_authority" in s7["authority_boundary"]["may_not_use_for"]
    assert case["outcome"] == "publish-with-limitation"


def test_w12d_s7_negative_controls_fail_closed(tmp_path: Path) -> None:
    report = _run_full_corpus_report(tmp_path)

    summary = report["s7_delegation_summary"]
    assert summary["oversight_theater_false_clear_count"] == 0
    assert summary["wrong_role_false_clear_count"] == 0
    assert summary["ai_first_high_stakes_false_clear_count"] == 0
    assert summary["mandate_absent_delegation_false_clear_count"] == 0
    assert set(summary["negative_control_results"]) >= {
        "oversight_theater_probe",
        "wrong_role_approval_probe",
        "ai_first_high_stakes_probe",
        "mandate_absent_delegation_probe",
    }


def test_w12d_s7_workflow_only_summary_probe_fails_p12(tmp_path: Path) -> None:
    probe = json.loads(
        (
            REPO_ROOT / "tests/fixtures/layer2/s7/workflow_only_delegation_summary_probe.json"
        ).read_text(encoding="utf-8")
    )
    report = _run_full_corpus_report(tmp_path)

    assert probe["expected_failure_pattern"] == "P12"
    assert probe["typed_producer_artifact_refs"] == []
    assert probe["cluster_handoff_records"] == []
    assert report["s7_delegation_summary"]["workflow_only_summary_false_clear_count"] == 0
    assert (
        report["s7_delegation_summary"]["negative_control_results"][
            "workflow_only_delegation_summary_probe"
        ]["failure_pattern"]
        == "P12"
    )


def test_w12d_emits_s8_value_choice_blocks_for_13_cases(tmp_path: Path) -> None:
    report = _run_full_corpus_report(tmp_path)

    assert report["summary"]["case_count"] == 13
    assert report["s8_value_choice_summary"]["case_count"] == 13
    s8_blocks = [case["s8_value_choice"] for case in report["cases"]]
    assert len(s8_blocks) == 13
    assert all(
        block["schema_version"] == "policyos.policy_design_case.layer2_s8_value_choice.v1"
        for block in s8_blocks
    )
    assert all(
        block["value_choice_provenance_ref"].startswith("pdc://layer2/s8/")
        for block in s8_blocks
    )
    assert all(
        "production_recommendation" in block["may_not_use_for"] for block in s8_blocks
    )
    assert all(
        block["canonical_outcome_effect"]
        == "none_shadow_or_governed_pilot_value_context_only"
        for block in s8_blocks
    )


def test_w12d_s8_negative_controls_have_zero_false_clears(tmp_path: Path) -> None:
    report = _run_full_corpus_report(tmp_path)

    summary = report["s8_value_choice_summary"]
    assert summary["llm_weight_false_clear_count"] == 0
    assert summary["corpus_weight_false_clear_count"] == 0
    assert summary["blocked_mandate_value_choice_false_clear_count"] == 0
    assert summary["pareto_ranking_without_value_source_false_clear_count"] == 0
    assert summary["multi_principal_silent_average_false_clear_count"] == 0
    assert summary["s7_decision_substitution_false_clear_count"] == 0
    assert summary["shadow_scenario_authority_false_clear_count"] == 0
    assert summary["missing_arrow_disclosure_false_clear_count"] == 0
    assert set(summary["negative_control_results"]) >= {
        "llm_social_weight_probe",
        "blocked_mandate_value_choice_probe",
        "pareto_ranking_without_value_source_probe",
        "multi_principal_conflict_probe",
        "s7_human_decision_substitution_probe",
        "shadow_scenario_authority_spoof_probe",
        "missing_arrow_disclosure_probe",
    }


def test_w12d_s8_ranked_recommendations_require_authorized_value_source(
    tmp_path: Path,
) -> None:
    report = _run_full_corpus_report(tmp_path)

    for case in report["cases"]:
        block = case["s8_value_choice"]
        if block["ranking_mode"] == "ranked_with_authorized_values":
            assert block["authorized_value_schedule_ref"]
            assert block["disposition"] == "authorized"
            assert block["p20_firewall_status"] == "pass"
            assert block["p22_firewall_status"] == "pass"
        if block["ranking_mode"] == "ranking_blocked":
            assert block["p20_firewall_status"] in {"limit", "block"}
            assert block["authorized_value_schedule_ref"] is None


def test_w12d_s8_pinned_s2_case_injects_value_posture(tmp_path: Path) -> None:
    index_dir = tmp_path / "capability-index"
    assert builder.main(["--mode", "fixture", "--output-dir", str(index_dir)]) == 0

    report = w12d.run_w12d_universal_outcome_corpus(
        repo_root=REPO_ROOT,
        corpus_path=SINGLE_CASE_PATH,
        graph_output_dir=tmp_path / "graphs",
        hypothesis_ledger_output_dir=tmp_path / "ledgers",
        mode="corpus_stub",
        producer_stub_dir=REPO_ROOT / "tests/fixtures/universal-corpus/producer_stubs",
        capability_index_path=index_dir / "capability_index_v1.duckdb",
    )

    case = report["cases"][0]
    s2 = case["s2_design_search"]
    s8 = case["s8_value_choice"]
    assert (
        s2["value_posture"]["value_choice_provenance_ref"]
        == s8["value_choice_provenance_ref"]
    )
    assert s8["pareto_archive_ref"] in s2["search_ledger"]["pareto_archive_refs"]
    assert (
        s8["value_choice_provenance_ref"]
        in s2["search_ledger"]["value_choice_provenance_refs"]
    )
    assert s8["value_choice_provenance_ref"] in s2["design_record"]["ledger_refs"]


def test_w12d_s8_preserves_s2_shadow_only_outcome_effects(tmp_path: Path) -> None:
    report = _run_full_corpus_report(tmp_path)

    for case in report["cases"]:
        s8 = case["s8_value_choice"]
        assert (
            s8["canonical_outcome_effect"]
            == "none_shadow_or_governed_pilot_value_context_only"
        )
        if case["case_id"] == "ua-msme-affordable-loans-2022":
            assert case["s2_design_search"]["canonical_outcome_effect"] == "none_shadow_only"
    assert report["s8_value_choice_summary"]["s2_value_posture_injection_count"] == 1


_S6_AXIS_CELLS = {
    "SYSTEM.measurability",
    "SYSTEM.subject_granularity",
    "ACTOR.state_capacity_feasibility",
    "ACTOR.mandate_legitimacy",
    "OTHER_AGENTS.strategic_response",
}
_S6_BRIDGE_CONSUMERS = {
    "KNOWLEDGE.epistemic_regime",
    "ACTOR.value_choice_provenance",
    "INTERVENTION.targeting",
    "INTERVENTION.feasibility",
    "DESIGNER_ITSELF.envelope_membership",
    "PUBLIC.legitimacy_disclosure",
    "INTERVENTION.design_candidate",
    "SYSTEM.post_intervention_dgp",
    "SYSTEM.dynamics_feedback",
    "INTERVENTION.robustness",
}
_S6_C3_DIMENSIONS = {
    "measurability_adequacy",
    "aggregation_validity",
    "capacity_feasibility",
    "mandate_legitimacy",
    "strategic_robustness",
    "response_model_validity",
}


def _run_full_corpus_report(tmp_path: Path) -> dict[str, object]:
    return w12d.run_w12d_universal_outcome_corpus(
        repo_root=REPO_ROOT,
        corpus_path=REPO_ROOT / "tests/fixtures/universal-corpus",
        graph_output_dir=tmp_path / "graphs",
        hypothesis_ledger_output_dir=tmp_path / "ledgers",
        mode="real_producer",
    )


def _case_result(
    *,
    case_id: str,
    domain: str,
    authority_level: str,
    outcome: str,
    expert_label: str,
    runtime_pdc_graph_status: str,
) -> dict[str, object]:
    return {
        "case_id": case_id,
        "source_path": f"fixture://{case_id}",
        "domain": domain,
        "authority_level": authority_level,
        "outcome": outcome,
        "counts_toward_useful_design": outcome in {"pass", "publish-with-limitation"},
        "universal_compilation": {
            "status": "pass",
            "grammar_ref": f"grammar:{case_id}",
            "obligation_graph_ref": f"obligation-graph-{case_id}",
            "claim_decomposition_ref": f"claim-ledger:{case_id}",
        },
        "producer_pipeline": {
            "status": "pass" if runtime_pdc_graph_status == "pass" else "blocked",
            "producer_pipeline_ref": f"producer-pipeline:{case_id}",
        },
        "runtime_pdc_graph": {
            "status": runtime_pdc_graph_status,
            "graph_ref": f"sha256:{case_id}",
            "capability_reality_label": (
                "implemented" if runtime_pdc_graph_status == "pass" else "bridge_missing"
            ),
            "blockers": (
                []
                if runtime_pdc_graph_status == "pass"
                else [
                    {
                        "code": "w12d_runtime_pdc_graph_blocked",
                        "message": "Runtime PDC graph blocked.",
                    }
                ]
            ),
        },
        "evidence_bound_pdc_graph": {
            "artifact_ref": f"repo://_build/.tmp/pdc-graphs/{case_id}.json",
            "authority_boundary": {
                "authoritative_for": ["pdc_graph_structure"],
                "may_not_use_for": ["projection_authority", "claim_authority"],
            },
        },
        "expert_adjudication_delta": {
            "expert_label": expert_label,
            "expected_outcome": outcome,
            "runtime_structural_outcome": outcome,
            "canonical_runtime_outcome": outcome,
            "status": "aligned",
            "delta_codes": [],
        },
        "authority_outcomes": {
            authority_level: {
                "outcome": outcome,
                "counts_toward_useful_design": outcome
                in {"pass", "publish-with-limitation"},
            }
        },
        "typed_blockers": (
            []
            if runtime_pdc_graph_status == "pass"
            else [
                {
                    "code": "w12d_runtime_pdc_graph_blocked",
                    "case_id": case_id,
                    "domain": domain,
                    "authority_level": authority_level,
                }
            ]
        ),
        "issues": [],
    }


def test_w12d_emits_s9_projection_lowering_blocks_for_13_cases(
    w12d_s9_report: dict[str, object],
) -> None:
    summary = dict(w12d_s9_report["s9_projection_lowering_summary"])
    blocks = _s9_blocks(w12d_s9_report)

    assert summary["case_count"] == 13
    assert len(blocks) == 13
    assert summary["projection_faithfulness_denominator"] >= 52
    for block in blocks:
        assert block["schema_version"] == (
            "policyos.policy_design_case.layer2_s9_projection_lowering.v1"
        )
        assert block["canonical_design_record_ref"]
        assert len(block["projection_render_refs"]) >= 4
        assert len(block["projection_faithfulness_refs"]) >= 4


def test_w12d_s9_negative_controls_have_zero_false_clears(
    w12d_s9_report: dict[str, object],
) -> None:
    summary = dict(w12d_s9_report["s9_projection_lowering_summary"])

    assert summary["negative_control_false_clear_count"] == 0
    assert summary["false_clear_counts"]["added_prose_claim"] == 0
    assert summary["false_clear_counts"]["tradeoff_inversion"] == 0
    assert summary["false_clear_counts"]["shadow_candidate_approval"] == 0
    assert summary["false_clear_counts"]["universal_self_claim_without_s14"] == 0


def test_w12d_s9_public_projection_faithfulness_preserves_load_bearing_limits(
    w12d_s9_report: dict[str, object],
) -> None:
    blocks = _s9_blocks(w12d_s9_report)

    for block in blocks:
        assert block["faithfulness_status"] == "pass"
        assert block["load_bearing_limitation_refs"]
        assert block["public_projection_omission_manifest"]
        assert not block["public_projection_hidden_limitation_refs"]


def test_w12d_s9_lowering_blocks_deeper_output_without_grounding(
    w12d_s9_report: dict[str, object],
) -> None:
    blocks = _s9_blocks(w12d_s9_report)
    blocked = [
        block
        for block in blocks
        if block["lowering_gate_status"] == "lowering_blocked_missing_grounding"
    ]

    assert blocked
    for block in blocked:
        assert block["faithfulness_status"] == "pass"
        assert block["lowering_append_receipt_refs"] == []
        assert "production_recommendation" in block["may_not_use_for"]


def test_w12d_s9_preserves_s2_shadow_only_and_s8_value_context_boundaries(
    w12d_s9_report: dict[str, object],
) -> None:
    for case in w12d_s9_report["cases"]:
        case = dict(case)
        s2 = dict(case["s2_design_search"])
        s8 = dict(case["s8_value_choice"])
        s9 = dict(case["s9_projection_lowering"])

        assert s2["canonical_outcome_effect"] == "none_shadow_only"
        assert s9["canonical_outcome_effect"] == "none_projection_only_or_reissue_required"
        assert s9["s2_projection_status"] == s2["design_record"]["projection_status"] == "shadow"
        assert s9["s8_value_choice_provenance_ref"] == s8["value_choice_provenance_ref"]
        assert s9["s8_value_tradeoff_disclosure_ref"] == s8["value_tradeoff_disclosure_ref"]
        assert "preference_learning_authority" in s9["may_not_use_for"]


def test_w12d_emits_s10_outcome_prediction_blocks_for_13_cases(
    w12d_s9_report: dict[str, object],
) -> None:
    assert all("s10_outcome_prediction" in case for case in w12d_s9_report["cases"])
    summary = dict(w12d_s9_report["s10_outcome_prediction_summary"])
    blocks = _s10_blocks(w12d_s9_report)

    assert summary["case_count"] == 13
    assert len(blocks) == 13
    assert {block["schema_version"] for block in blocks} == {
        "policyos.policy_design_case.layer2_s10_outcome_prediction.v1"
    }
    assert any(block["forecast_tier"] == "observable_calibrated" for block in blocks)
    assert any(block["forecast_tier"] == "simulation_only_advisory" for block in blocks)
    assert any(block["forecast_tier"] == "equilibrium_contested_blocked" for block in blocks)


def test_w12d_s10_blocks_consume_s5_s6_s8_without_rerunning_them(
    w12d_s9_report: dict[str, object],
) -> None:
    for case in w12d_s9_report["cases"]:
        case = dict(case)
        s5 = dict(case["s5_coupling_composition"])
        s6 = dict(case["s6_blind_spot_firewalls"])
        s8 = dict(case["s8_value_choice"])
        s10 = dict(case["s10_outcome_prediction"])

        assert s10["s5_forecast_support_ref"] == s5["forecast_support_ref"]
        assert set(s10["s6_firewall_status_refs"]) >= {
            s6["measurability_record_ref"],
            s6["strategic_response_record_ref"],
        }
        assert s10["s8_value_choice_provenance_ref"] == s8["value_choice_provenance_ref"]
        assert s10["s8_value_tradeoff_disclosure_ref"] == (
            s8["value_tradeoff_disclosure_ref"]
        )
        assert s10["canonical_outcome_effect"] == (
            "forecast_support_only_not_outcome_authority"
        )


def test_w12d_s10_injects_first_case_s2_posture_without_full_search_for_all_cases(
    w12d_s9_report: dict[str, object],
) -> None:
    first_case_count = 0
    lightweight_case_count = 0

    for case in w12d_s9_report["cases"]:
        case = dict(case)
        s2 = dict(case["s2_design_search"])
        s10 = dict(case["s10_outcome_prediction"])
        if case["case_id"] == "ua-msme-affordable-loans-2022":
            first_case_count += 1
            assert s2["forecast_posture"]["forecast_support_ref"] == (
                s10["forecast_support_ref"]
            )
            assert s10["forecast_support_ref"] in s2["search_ledger"]["forecast_support_refs"]
        else:
            lightweight_case_count += 1
            assert s2["status"] == "not_applicable"
            assert s2["forecast_posture_ref"] == s10["forecast_support_ref"]
            assert "search_ledger" not in s2

    assert first_case_count == 1
    assert lightweight_case_count == 12


def test_w12d_s10_summary_records_calibration_and_negative_controls(
    w12d_s9_report: dict[str, object],
) -> None:
    summary = dict(w12d_s9_report["s10_outcome_prediction_summary"])

    assert summary["case_count"] == 13
    assert summary["observable_subset_calibration_denominator"] >= 4
    assert summary["observable_subset_calibration_numerator"] == (
        summary["observable_subset_calibration_denominator"]
    )
    assert summary["observable_subset_calibration_status"] == "pass"
    assert summary["observable_subset_calibration_floor_passed"] is True
    assert summary["non_observable_downgrade_count"] >= 1
    assert summary["equilibrium_contested_single_forecast_false_clear_count"] == 0
    assert summary["simulation_only_evidence_laundering_false_clear_count"] == 0


def test_w12d_emits_s11_predictive_knowledge_blocks_for_13_cases(
    w12d_s9_report: dict[str, object],
) -> None:
    assert all("s11_predictive_knowledge" in case for case in w12d_s9_report["cases"])
    summary = dict(w12d_s9_report["s11_predictive_knowledge_summary"])
    blocks = _s11_blocks(w12d_s9_report)

    assert summary["case_count"] == 13
    assert summary["axis_count"] == 52
    assert len(blocks) == 13
    assert {block["schema_version"] for block in blocks} == {
        "policyos.policy_design_case.layer2_s11_predictive_knowledge.v1"
    }
    axis_rows = [row for block in blocks for row in block["axis_upgrade_rows"]]
    assert len(axis_rows) == 52
    assert any(row["effective_maturity"] == "predictive" for row in axis_rows)
    assert any(row["effective_maturity"] == "fail_closed" for row in axis_rows)


def test_w12d_s11_blocks_consume_s6_s10_and_ir_without_rerunning_them(
    w12d_s9_report: dict[str, object],
) -> None:
    for case in w12d_s9_report["cases"]:
        case = dict(case)
        s6 = dict(case["s6_blind_spot_firewalls"])
        s10 = dict(case["s10_outcome_prediction"])
        s11 = dict(case["s11_predictive_knowledge"])

        assert set(s11["s6_floor_status_refs"]) >= {
            s6["measurability_record_ref"],
            s6["strategic_response_record_ref"],
        }
        assert s11["s10_forecast_support_ref"] == s10["forecast_support_ref"]
        assert s11["s10_forecast_tier"] == s10["forecast_tier"]
        assert s11["ir_analytics_bridge_ref"]
        assert s11["proof_carrying_analytics_ref"]
        assert s11["canonical_outcome_effect"] == (
            "predictive_relaxation_only_not_production_authority"
        )


def test_w12d_s11_injects_first_case_s2_posture_without_full_search_for_all_cases(
    w12d_s9_report: dict[str, object],
) -> None:
    first_case_count = 0
    lightweight_case_count = 0

    for case in w12d_s9_report["cases"]:
        case = dict(case)
        s2 = dict(case["s2_design_search"])
        s11 = dict(case["s11_predictive_knowledge"])
        if case["case_id"] == "ua-msme-affordable-loans-2022":
            first_case_count += 1
            assert s2["predictive_posture"]["predictive_knowledge_ref"] == (
                s11["predictive_knowledge_ref"]
            )
            assert s11["predictive_knowledge_ref"] in (
                s2["search_ledger"]["predictive_knowledge_refs"]
            )
        else:
            lightweight_case_count += 1
            assert s2["status"] == "not_applicable"
            assert s2["predictive_posture_ref"] == s11["predictive_knowledge_ref"]
            assert "search_ledger" not in s2

    assert first_case_count == 1
    assert lightweight_case_count == 12


def test_w12d_layer3_g3_consumes_resolved_first_case_proof_in_s11_s2_route(
    w12d_s9_report: dict[str, object],
) -> None:
    summary = dict(w12d_s9_report["layer3_g3_analytics_search_summary"])
    first = next(
        dict(case)
        for case in w12d_s9_report["cases"]
        if case["case_id"] == "ua-msme-affordable-loans-2022"
    )
    gate = dict(first["layer3_g3_analytics_search_gate"])
    s11 = dict(first["s11_predictive_knowledge"])
    s2 = dict(first["s2_design_search"])
    search_ledger = dict(s2["search_ledger"])
    design_record = dict(s2["design_record"])
    s11_constraints = [
        dict(row)
        for row in s2["constraint_store"]["constraint_records"]
        if str(row["constraint_id"]).startswith("layer2.s11.")
    ]
    axis_positions = [
        dict(row)
        for row in design_record["axis_positions"]
        if row["axis"] == "predictive_knowledge_relaxation"
    ]
    firewall_statuses = [
        dict(row)
        for row in design_record["firewall_status"]
        if row["cell_ref"] == "KNOWLEDGE.predictive_knowledge_relaxation"
    ]

    assert summary["g3_consumer_gate_count"] == 13
    assert summary["full_consumer_case_count"] == 1
    assert summary["lightweight_posture_ref_count"] == 12
    assert summary["fixture_certificate_closure_count"] == 0
    assert summary["useful_design_delta_count"] == 0
    assert gate["status"] == "pass"
    assert gate["route_kind"] == "full_s11_s2_consumer"
    assert gate["g3_closure_count"] == 1
    assert gate["g3_proof_carrying_analytics_ref"].startswith("pdc://layer3/g3/")
    assert s11["proof_carrying_analytics_ref"] == gate["g3_proof_carrying_analytics_ref"]
    assert s11["predictive_knowledge_ref"] in search_ledger["predictive_knowledge_refs"]
    assert gate["g3_proof_carrying_analytics_ref"] in (
        search_ledger["proof_carrying_analytics_refs"]
    )
    assert s11_constraints
    assert all(
        gate["g3_proof_carrying_analytics_ref"] in row["evidence_refs"]
        for row in s11_constraints
    )
    assert axis_positions
    assert gate["g3_proof_carrying_analytics_ref"] in axis_positions[0]["evidence_refs"]
    assert firewall_statuses and firewall_statuses[0]["status"] in {"limit", "block"}
    assert set(design_record["projection_audiences"]) == {
        "PUBLIC",
        "REVIEWER",
        "EXPERT",
        "MACHINE",
    }
    assert gate["consumer_assertions"] == {
        "search_ledger_predictive_knowledge_ref_consumed": True,
        "search_ledger_g3_proof_ref_consumed": True,
        "s11_constraint_store_entries_consumed": True,
        "refinement_status_consumed": True,
        "axis_position_declared": True,
        "firewall_status_consumed": True,
        "projection_fields_present": True,
    }


def test_w12d_layer3_g3_fixture_s11_refs_are_regression_context_not_closure(
    w12d_s9_report: dict[str, object],
) -> None:
    summary = dict(w12d_s9_report["layer3_g3_analytics_search_summary"])
    lightweight_gates = [
        dict(case["layer3_g3_analytics_search_gate"])
        for case in w12d_s9_report["cases"]
        if case["case_id"] != "ua-msme-affordable-loans-2022"
    ]

    assert len(lightweight_gates) == 12
    assert summary["fixture_certificate_closure_count"] == 0
    assert all(gate["route_kind"] == "lightweight_s11_posture_ref" for gate in lightweight_gates)
    assert all(gate["g3_closure_count"] == 0 for gate in lightweight_gates)
    assert all(gate["fixture_s11_regression_context_ref"] for gate in lightweight_gates)


def test_w12d_layer3_g3_gate_does_not_overwrite_g0_g1_g2_or_useful_design(
    w12d_s9_report: dict[str, object],
) -> None:
    summary = dict(w12d_s9_report["layer3_g3_analytics_search_summary"])

    assert summary["useful_design_delta_count"] == 0
    assert summary["g0_conversion_outcome_overwrite_count"] == 0
    assert summary["g1_conversion_outcome_overwrite_count"] == 0
    assert summary["g2_conversion_outcome_overwrite_count"] == 0
    assert all(
        case["counts_toward_useful_design"]
        == (case["outcome"] in w12d.USEFUL_DESIGN_OUTCOMES)
        for case in w12d_s9_report["cases"]
    )


def test_w12d_layer3_g5_red_baseline_missing_hook_keeps_pre_g5_grounded_count(
    w12d_s9_report: dict[str, object],
) -> None:
    """P01/P02/P04 red baseline: G5 is absent until W12.D consumes the overlay."""

    pinned = next(
        dict(case)
        for case in w12d_s9_report["cases"]
        if case["case_id"] == "ua-msme-affordable-loans-2022"
    )

    assert w12d_s9_report["summary"]["grounded_conversion_count"] == 0
    assert "layer3_g5_conversion_gate" in pinned


def test_w12d_layer3_g5_gate_is_inserted_after_g3_before_summary(
    w12d_s9_report: dict[str, object],
) -> None:
    pinned = next(
        dict(case)
        for case in w12d_s9_report["cases"]
        if case["case_id"] == "ua-msme-affordable-loans-2022"
    )
    summary = dict(w12d_s9_report["summary"])

    assert "layer3_g3_analytics_search_gate" in pinned
    assert "layer3_g5_conversion_gate" in pinned
    assert summary["layer3_g5_gate_injection_order"] == "after_g3_before_summary"
    assert summary["layer3_g5_gate_count"] == 1


def test_w12d_layer3_g5_handles_g3_summary_top_level_not_inside_summary(
    w12d_s9_report: dict[str, object],
) -> None:
    summary = dict(w12d_s9_report["summary"])

    assert "layer3_g3_analytics_search_summary" in w12d_s9_report
    assert "layer3_g3_analytics_search_summary" not in summary
    assert summary["layer3_g5_g3_summary_location"] == "top_level_report_field"


def test_w12d_layer3_g5_emits_pinned_case_conversion_classification(
    w12d_s9_report: dict[str, object],
) -> None:
    pinned = next(
        dict(case)
        for case in w12d_s9_report["cases"]
        if case["case_id"] == "ua-msme-affordable-loans-2022"
    )
    gate = dict(pinned["layer3_g5_conversion_gate"])

    assert gate["case_id"] == "ua-msme-affordable-loans-2022"
    assert gate["status"] == "not_routed"
    assert gate["conversion_classification"] == "unchanged_blocker"
    assert "layer3_g5_w12d_consumer_gate_missing" in gate["issue_codes"]


def test_w12d_layer3_g5_grounded_conversion_count_is_g5_owned(
    w12d_s9_report: dict[str, object],
) -> None:
    summary = dict(w12d_s9_report["summary"])

    assert summary["layer3_g0_grounded_conversion_count"] == 0
    assert summary["layer3_g5_grounded_conversion_count"] == 0
    assert summary["grounded_conversion_count"] == summary["layer3_g5_grounded_conversion_count"]
    assert summary["grounded_conversion_count_source"] == "layer3_g5_conversion_gate"


def test_w12d_layer3_g5_does_not_overwrite_g0_g1_g2_g3_histories(
    w12d_s9_report: dict[str, object],
) -> None:
    pinned = next(
        dict(case)
        for case in w12d_s9_report["cases"]
        if case["case_id"] == "ua-msme-affordable-loans-2022"
    )
    summary = dict(w12d_s9_report["summary"])

    assert all(
        key in pinned
        for key in (
            "layer3_g0_grounding_gate",
            "layer3_g1_grounding_gate",
            "layer3_g2_forecast_gate",
            "layer3_g3_analytics_search_gate",
            "layer3_g5_conversion_gate",
        )
    )
    assert summary["layer3_g5_g0_g1_g2_g3_history_overwrite_count"] == 0


def test_w12d_layer3_g5_preserves_pre_g5_closed_case_replay(
    w12d_s9_report: dict[str, object],
) -> None:
    pinned = next(
        dict(case)
        for case in w12d_s9_report["cases"]
        if case["case_id"] == "ua-msme-affordable-loans-2022"
    )
    gate = dict(pinned["layer3_g5_conversion_gate"])

    assert pinned["outcome"] == gate["pre_g5_outcome"]
    assert pinned["conversion_outcome"] == gate["pre_g5_conversion_outcome"]
    assert gate["pre_g5_replay_mutated"] is False


def test_w12d_layer3_g5_grounded_abstention_does_not_count_as_useful_design() -> None:
    summary = w12d._layer3_g5_summary(  # noqa: SLF001
        [
            {
                "layer3_g5_conversion_gate": {
                    "status": "pass",
                    "conversion_classification": "typed_blocker -> grounded_abstention",
                    "counts_toward_useful_design": False,
                    "grounded_conversion_count": 1,
                    "useful_design_credit_count": 0,
                }
            }
        ]
    )

    assert summary["layer3_g5_grounded_abstention_count"] == 1
    assert summary["layer3_g5_grounded_conversion_count"] == 1
    assert summary["layer3_g5_runtime_useful_design_credit_count"] == 0


def test_w12d_layer3_g5_grounded_limited_counts_only_with_status_composition() -> None:
    summary = w12d._layer3_g5_summary(  # noqa: SLF001
        [
            {
                "layer3_g5_conversion_gate": {
                    "status": "pass",
                    "conversion_classification": "typed_blocker -> grounded_limited",
                    "counts_toward_useful_design": True,
                    "grounded_conversion_count": 1,
                    "useful_design_credit_count": 1,
                    "status_composition_status": "pass",
                }
            },
            {
                "layer3_g5_conversion_gate": {
                    "status": "pass",
                    "conversion_classification": "typed_blocker -> grounded_limited",
                    "counts_toward_useful_design": True,
                    "grounded_conversion_count": 1,
                    "useful_design_credit_count": 1,
                    "status_composition_status": "missing",
                }
            },
        ]
    )

    assert summary["layer3_g5_grounded_limited_count"] == 2
    assert summary["layer3_g5_grounded_limited_status_composed_count"] == 1
    assert summary["layer3_g5_runtime_useful_design_credit_count"] == 1


def test_w12d_layer3_g5_preserves_runtime_vs_expert_useful_design_metrics(
    w12d_s9_report: dict[str, object],
) -> None:
    summary = dict(w12d_s9_report["summary"])

    assert summary["runtime_useful_design_count"] == summary["useful_design_count"]
    assert summary["expert_useful_design_ceiling_count"] >= summary["runtime_useful_design_count"]
    assert summary["layer3_g5_runtime_useful_design_credit_count"] == 0
    assert "layer3_g5_expert_useful_design_ceiling_count" not in summary


def test_w12d_s11_summary_records_per_axis_calibration_floor_and_negative_controls(
    w12d_s9_report: dict[str, object],
) -> None:
    summary = dict(w12d_s9_report["s11_predictive_knowledge_summary"])

    assert summary["case_count"] == 13
    assert summary["axis_count"] == 52
    assert summary["per_axis_predictive_calibration_denominator"] == (
        summary["axis_count"]
    )
    assert summary["per_axis_predictive_calibration_numerator"] <= (
        summary["per_axis_predictive_calibration_denominator"]
    )
    assert summary["predictive_axis_count"] + summary[
        "reverted_fail_closed_axis_count"
    ] == summary["axis_count"]
    assert summary["per_axis_predictive_calibration_threshold_ref"]
    for false_clear_field in w12d.S11_FALSE_CLEAR_FIELDS:
        flat_field = f"{false_clear_field}_false_clear_count"
        assert summary[flat_field] == 0
        assert summary["false_clear_counts"][false_clear_field] == 0


def test_w12d_s11_keeps_mandate_legitimacy_at_s6_floor(
    w12d_s9_report: dict[str, object],
) -> None:
    for case in w12d_s9_report["cases"]:
        s6 = dict(case["s6_blind_spot_firewalls"])
        s11 = dict(case["s11_predictive_knowledge"])
        axis_cells = {row["cell_ref"] for row in s11["axis_upgrade_rows"]}

        assert "ACTOR.mandate_legitimacy" not in axis_cells
        assert s6["mandate_legitimacy_record_ref"] in s11["s6_floor_status_refs"]
        assert "mandate_legitimacy_predictive_upgrade" in s11["may_not_use_for"]


def test_w12d_emits_s12_resource_economics_blocks_for_13_cases(
    w12d_s9_report: dict[str, object],
) -> None:
    assert all("s12_resource_economics" in case for case in w12d_s9_report["cases"])
    summary = dict(w12d_s9_report["s12_resource_economics_summary"])
    blocks = _s12_blocks(w12d_s9_report)

    assert summary["case_count"] == 13
    assert summary["voi_site_count"] >= 3
    assert summary["typed_budget_count"] == 5
    assert summary["override_rate_trend"] in {"improving", "flat"}
    assert summary["reuse_rate_trend"] in {"improving", "flat"}
    assert summary["growth_without_envelope_delta_count"] == 0
    assert summary["held_out_status"] == "pending_s14"
    assert all(value == 0 for value in summary["false_clear_counts"].values())
    assert len(summary["per_case_resource_table"]) == 13
    assert len(blocks) == 13
    assert {block["schema_version"] for block in blocks} == {
        "policyos.policy_design_case.layer2_s12_resource_economics.v1"
    }


def test_w12d_s12_voi_allocation_covers_at_least_three_sites(
    w12d_s9_report: dict[str, object],
) -> None:
    summary = dict(w12d_s9_report["s12_resource_economics_summary"])
    blocks = _s12_blocks(w12d_s9_report)

    assert summary["voi_site_count"] >= 3
    assert summary["typed_budget_count"] == 5
    for block in blocks:
        assert block["voi_site_count"] >= 3
        assert len(block["voi_allocation_refs"]) >= 3
        assert len(block["typed_budget_refs"]) == 5
        assert block["pareto_archive_ref"]
        assert block["canonical_outcome_effect"] == (
            "resource_allocation_only_not_production_authority"
        )


def test_w12d_s12_growth_entries_cite_envelope_delta(
    w12d_s9_report: dict[str, object],
) -> None:
    for block in _s12_blocks(w12d_s9_report):
        assert block["envelope_growth_ledger_ref"]
        assert block["growth_entries"]
        for entry in block["growth_entries"]:
            assert entry.get("certified_envelope_delta_ref") or entry.get(
                "pending_envelope_delta_ref"
            )
            assert entry["growth_counting_disposition"] != "blocked_no_envelope_delta"


def test_w12d_s12_negative_controls_have_zero_false_clears(
    w12d_s9_report: dict[str, object],
) -> None:
    summary = dict(w12d_s9_report["s12_resource_economics_summary"])

    assert summary["growth_without_envelope_delta_count"] == 0
    assert all(value == 0 for value in summary["false_clear_counts"].values())
    assert set(summary["negative_control_results"]) >= {
        "bespoke_one_off_growth_probe",
        "allocation_gaming_internal_metrics_probe",
        "floor_lowering_for_useful_design_rate_probe",
        "b_faster_than_a_growth_probe",
        "meta_regress_past_principal_probe",
        "interchangeable_budget_probe",
        "growth_without_envelope_delta_probe",
    }
    for result in summary["negative_control_results"].values():
        assert result["false_clear_count"] == 0
        assert result["observed_disposition"] == result["expected_disposition"]


def test_w12d_s12_preserves_s2_shadow_only_outcome_effects(
    w12d_s9_report: dict[str, object],
) -> None:
    for case in w12d_s9_report["cases"]:
        case = dict(case)
        s2 = dict(case["s2_design_search"])
        s12 = dict(case["s12_resource_economics"])

        assert s12["canonical_outcome_effect"] == (
            "resource_allocation_only_not_production_authority"
        )
        if case["case_id"] == "ua-msme-affordable-loans-2022":
            assert s2["resource_posture"]["resource_allocation_policy_ref"] == (
                s12["resource_allocation_policy_ref"]
            )
            assert s2["canonical_outcome_effect"] == "none_shadow_only"
        else:
            assert s2["status"] == "not_applicable"
            assert s2["resource_posture_ref"] == s12["resource_allocation_policy_ref"]


def test_w12d_emits_s13_post_deploy_blocks_for_13_cases(
    w12d_s9_report: dict[str, object],
) -> None:
    assert all("s13_post_deploy_accountability" in case for case in w12d_s9_report["cases"])
    summary = dict(w12d_s9_report["s13_post_deploy_accountability_summary"])
    blocks = _s13_blocks(w12d_s9_report)

    assert summary["case_count"] == 13
    assert summary["monitorability_rate"] == 1.0
    assert summary["mape_k_trace_completeness_rate"] == 1.0
    assert len(blocks) == 13
    assert {block["schema_version"] for block in blocks} == {
        "policyos.policy_design_case.layer2_s13_post_deploy_accountability.v1"
    }
    assert all(block["deployment_dossier_ref"] for block in blocks)
    assert all(block["public_accountability_note_ref"] for block in blocks)


def test_w12d_s13_monitorability_floor_and_attribution_gate_pass(
    w12d_s9_report: dict[str, object],
) -> None:
    summary = dict(w12d_s9_report["s13_post_deploy_accountability_summary"])

    assert summary["monitorability_rate"] == 1.0
    assert summary["a_before_b_ratio"] == 1.0
    assert summary["attribution_resolution_rate"] == 1.0
    assert summary["learning_without_attribution_count"] == 0
    for block in _s13_blocks(w12d_s9_report):
        assert block["monitorability_floor_passed"] is True
        if block["attribution_status"] in {"pending", "unattributable"}:
            assert block["learning_allowed"] is False


def test_w12d_s13_envelope_revision_includes_shrink_and_expand(
    w12d_s9_report: dict[str, object],
) -> None:
    summary = dict(w12d_s9_report["s13_post_deploy_accountability_summary"])
    directions = {block["envelope_revision_direction"] for block in _s13_blocks(w12d_s9_report)}

    assert summary["envelope_shrink_count"] >= 1
    assert summary["envelope_expansion_count"] >= 1
    assert "shrink" in directions or "split" in directions
    assert "expand" in directions


def test_w12d_s13_envelope_shrink_latency_is_recorded_for_seeded_disconfirmation(
    w12d_s9_report: dict[str, object],
) -> None:
    summary = dict(w12d_s9_report["s13_post_deploy_accountability_summary"])
    disconfirmation_blocks = [
        block for block in _s13_blocks(w12d_s9_report) if block["seeded_disconfirmation"]
    ]

    assert summary["envelope_shrink_latency_recorded_count"] >= 1
    assert disconfirmation_blocks
    assert any(block["shrink_latency_days"] for block in disconfirmation_blocks)
    assert all(
        block["assurance_case_delta_ref"]
        for block in disconfirmation_blocks
        if block["envelope_revision_direction"] in {"shrink", "split"}
    )


def test_w12d_s13_negative_controls_have_zero_false_clears(
    w12d_s9_report: dict[str, object],
) -> None:
    summary = dict(w12d_s9_report["s13_post_deploy_accountability_summary"])

    assert all(value == 0 for value in summary["false_clear_counts"].values())
    assert set(summary["negative_control_results"]) >= {
        "post_policy_data_as_pre_policy_evidence_probe",
        "learned_prior_in_current_evidence_slot_probe",
        "unattributable_updates_model_probe",
        "silent_closed_case_rewrite_probe",
        "learning_without_attribution_probe",
        "envelope_shrink_without_assurance_delta_probe",
        "b_update_before_a_firewall_probe",
        "implementation_failure_as_theory_refutation_probe",
        "outcome_learning_without_counterfactual_probe",
        "s13_as_production_or_recommendation_authority_probe",
    }
    for result in summary["negative_control_results"].values():
        assert result["false_clear_count"] == 0
        assert result["observed_disposition"] == result["expected_disposition"]


def test_w12d_s13_preserves_s2_shadow_only_outcome_effects(
    w12d_s9_report: dict[str, object],
) -> None:
    for case in w12d_s9_report["cases"]:
        case = dict(case)
        s2 = dict(case["s2_design_search"])
        s13 = dict(case["s13_post_deploy_accountability"])

        assert s13["canonical_outcome_effect"] == (
            "post_deploy_accountability_only_not_production_authority"
        )
        if case["case_id"] == "ua-msme-affordable-loans-2022":
            assert s2["accountability_posture"]["phase"] == "design_time_gate"
            assert s2["canonical_outcome_effect"] == "none_shadow_only"
        else:
            assert s2["status"] == "not_applicable"


def test_w12d_s13_design_time_gate_posture_does_not_inject_post_deploy_learning_refs(
    w12d_s9_report: dict[str, object],
) -> None:
    case = next(
        case
        for case in w12d_s9_report["cases"]
        if case["case_id"] == "ua-msme-affordable-loans-2022"
    )
    posture = case["s2_design_search"]["accountability_posture"]

    assert posture["phase"] == "design_time_gate"
    assert posture["divergence_record_refs"] == []
    assert posture["learning_update_proposal_refs"] == []
    assert posture["envelope_revision_ref"] is None
    assert posture["a_before_b_status"] is None


def test_w12d_s13_gold_labels_cover_all_13_cases_without_leaking_gold_into_signals() -> None:
    labels = json.loads(
        (
            REPO_ROOT / "tests/fixtures/layer2/s13/s13_post_deploy_expert_labels.json"
        ).read_text(encoding="utf-8")
    )
    signals = json.loads(
        (
            REPO_ROOT / "tests/fixtures/layer2/s13/s13_post_deploy_case_signals.json"
        ).read_text(encoding="utf-8")
    )
    expected_cases = {
        path.stem for path in (REPO_ROOT / "tests/fixtures/universal-corpus/cases").glob("*.json")
    }

    assert set(labels["cases"]) == expected_cases
    assert set(signals["cases"]) == expected_cases
    assert any(
        row["expected_envelope_revision_direction"] in {"shrink", "split"}
        for row in labels["cases"].values()
    )
    assert any(
        row["expected_envelope_revision_direction"] == "expand"
        for row in labels["cases"].values()
    )

    forbidden_gold_fields = {
        "expected_attribution_class",
        "expected_attribution_status",
        "expected_envelope_revision_direction",
        "expected_learning_allowed",
        "expected_public_accountability_note",
        "matches_gold",
    }
    for row in signals["cases"].values():
        assert forbidden_gold_fields.isdisjoint(row)


def test_w12d_emits_s14_dev_assurance_blocks_for_13_cases_without_sealed_access(
    w12d_s9_report: dict[str, object],
) -> None:
    assert all("s14_universality_assurance" in case for case in w12d_s9_report["cases"])
    summary = dict(w12d_s9_report["s14_universality_assurance_summary"])
    blocks = _s14_blocks(w12d_s9_report)

    assert summary["case_count"] == 13
    assert summary["sealed_battery_status"] == "not_accessed_in_dev"
    assert summary["sealed_battery_access_attempted"] is False
    assert summary["dev_sealed_battery_access_count"] == 0
    assert summary["universal_claim_gate_status"] != "pass"
    assert len(blocks) == 13
    assert all(block["sealed_battery_status"] == "not_accessed_in_dev" for block in blocks)
    assert all(block["sealed_battery_access_attempted"] is False for block in blocks)


def test_w12d_s14_dev_route_preserves_s2_s9_s13_authority_boundaries(
    w12d_s9_report: dict[str, object],
) -> None:
    for case in w12d_s9_report["cases"]:
        case = dict(case)
        s2 = dict(case["s2_design_search"])
        s9 = dict(case["s9_projection_lowering"])
        s13 = dict(case["s13_post_deploy_accountability"])
        s14 = dict(case["s14_universality_assurance"])

        assert s14["canonical_outcome_effect"] == (
            "universality_assurance_dev_shadow_only_not_claim_authority"
        )
        assert s14["authority_role"] == "projection_only"
        assert "production_recommendation" in s14["may_not_use_for"]
        assert "claim_authority" in s14["may_not_use_for"]
        assert s9["authority_role"] == "projection_only"
        assert s13["canonical_outcome_effect"] == (
            "post_deploy_accountability_only_not_production_authority"
        )
        if case["case_id"] == "ua-msme-affordable-loans-2022":
            assert s2["canonical_outcome_effect"] == "none_shadow_only"


def test_w12d_s14_bare_universal_claim_negative_control_has_zero_false_clears(
    w12d_s9_report: dict[str, object],
) -> None:
    summary = dict(w12d_s9_report["s14_universality_assurance_summary"])

    assert summary["bare_universal_claim_block_count"] >= 1
    assert summary["aggregate_universal_number_block_count"] >= 1
    assert summary["untested_axis_out_of_envelope_count"] >= 1
    assert all(value == 0 for value in summary["false_clear_counts"].values())
    assert set(summary["false_clear_counts"]) >= {
        "bare_universal_claim_without_battery",
        "sealed_battery_dev_access",
        "aggregate_universal_number_laundering",
        "gold_label_leak_into_dev_signal",
    }
    assert (
        summary["negative_control_results"]["bare_universal_claim_without_battery_probe"][
            "false_clear_count"
        ]
        == 0
    )


def test_w12d_s14_scorecard_refs_are_pending_sealed_not_passed_in_dev(
    w12d_s9_report: dict[str, object],
) -> None:
    summary = dict(w12d_s9_report["s14_universality_assurance_summary"])

    assert summary["sealed_battery_status"] == "not_accessed_in_dev"
    assert summary["universal_claim_gate_status"] != "pass"
    for block in _s14_blocks(w12d_s9_report):
        assert block["scorecard_status"] in {"pending_sealed", "not_tested", "limited"}
        assert block["sealed_battery_ref"].startswith("partition://")
        assert block["sealed_battery_status"] == "not_accessed_in_dev"
        assert block["universal_claim_gate_status"] != "pass"


def test_w12d_s14_gold_labels_cover_13_cases_without_leaking_into_signals() -> None:
    labels = json.loads(
        (
            REPO_ROOT / "tests/fixtures/layer2/s14/s14_universality_expert_labels.json"
        ).read_text(encoding="utf-8")
    )
    signals = json.loads(
        (
            REPO_ROOT / "tests/fixtures/layer2/s14/s14_universality_dev_signals.json"
        ).read_text(encoding="utf-8")
    )
    expected_cases = {
        path.stem for path in (REPO_ROOT / "tests/fixtures/universal-corpus/cases").glob("*.json")
    }

    assert set(labels["cases"]) == expected_cases
    assert set(signals["cases"]) == expected_cases
    assert any(
        row["expected_declared_posture"] == "out_of_envelope"
        for row in labels["cases"].values()
    )

    forbidden_gold_fields = {
        "expected_declared_posture",
        "expected_battery_status",
        "expected_gate_disposition",
        "expected_grounded_authority_status",
        "expected_held_out_status",
        "matches_gold",
        "gold_label",
        "answer_key",
        "hidden_case_payload",
        "sealed_fixture_contents",
    }
    for row in signals["cases"].values():
        assert forbidden_gold_fields.isdisjoint(row)


def test_w12d_s14_dev_route_emits_d4_status_composition_without_claim_authority(
    w12d_s9_report: dict[str, object],
) -> None:
    summary = dict(w12d_s9_report["s14_universality_assurance_summary"])

    assert summary["d4_corpus_track_count"] == 19
    assert summary["expert_oracle_layer_count"] == 4
    assert summary["breadth_floor_status"] in {"pass", "limited", "blocked"}
    assert summary["grounded_authority_coverage_status"] in {
        "pass",
        "limited",
        "blocked",
    }
    assert summary["baseline_comparison_status"] in {"pass", "limited", "blocked"}
    assert summary["evaluation_status_composition_status"] == "pass"
    assert summary["envelope_revision_dynamics_status"] in {"pass", "limited", "blocked"}
    for block in _s14_blocks(w12d_s9_report):
        assert block["d4_corpus_track_coverage_ref"]
        assert block["evaluation_status_composition_ref"]
        assert block["authority_role"] == "projection_only"
        assert "claim_authority" in block["may_not_use_for"]
