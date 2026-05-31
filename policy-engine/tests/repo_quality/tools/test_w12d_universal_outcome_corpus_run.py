from __future__ import annotations

# ruff: noqa: S101
import json
from pathlib import Path

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
    assert case["corpus_stub"]["max_authority_posture"] == "governed-pilot"
    assert "production_closeout_authority" in case["corpus_stub"]["may_not_use_for"]


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
    assert s2["status"] == "shadow_ready"
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
    assert case["s2_design_search"]["status"] == "shadow_ready"
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
