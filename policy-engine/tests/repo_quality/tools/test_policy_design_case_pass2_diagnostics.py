from __future__ import annotations

# ruff: noqa: S101
import json
from pathlib import Path

from tools.quality.validation import build_policy_design_case_pass2_diagnostics as diag
from tools.quality.validation import check_policy_design_case_wave34_pass2 as wave34_check
from tools.quality.validation import run_policy_design_case_pass2_phase34_3 as diag34_3
from tools.quality.validation import run_policy_design_case_pass2_phase34_4 as diag34_4
from tools.quality.validation import run_policy_design_case_pass2_phase34_5 as diag34_5
from tools.quality.validation import run_policy_design_case_pass2_phase34_6 as diag34_6

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_phase34_1_payload_records_missing_cross_domain_runtime_bundles(
    tmp_path: Path,
) -> None:
    wave33_dir = _write_minimal_wave33(tmp_path)

    payload = diag.build_phase34_1_payload(
        repo_root=REPO_ROOT,
        wave33_dir=wave33_dir,
    )

    pdd37 = payload["pdds"]["PDD-037"]

    assert payload["status"] == "diagnosed"
    assert payload["observed_wave33_case"]["observed_scenario_ids"] == [
        "ukraine_msme_wartime_credit_support"
    ]
    assert pdd37["acceptance_gate_status"] == "failed"
    assert pdd37["summary"]["missing_runtime_domain_count"] == len(
        diag.PHASE56_CROSS_DOMAIN_SCENARIO_IDS
    )
    assert {
        finding["code"] for finding in pdd37["findings"]
    } == {"pass2_wave33_cross_domain_bundle_missing"}


def test_phase34_1_payload_records_metamorphic_and_multilingual_gaps(
    tmp_path: Path,
) -> None:
    wave33_dir = _write_minimal_wave33(tmp_path)

    payload = diag.build_phase34_1_payload(
        repo_root=REPO_ROOT,
        wave33_dir=wave33_dir,
    )

    pdd55 = payload["pdds"]["PDD-055"]
    pdd56 = payload["pdds"]["PDD-056"]

    assert pdd55["acceptance_gate_status"] == "failed"
    assert pdd55["summary"]["total_variant_count"] > 0
    assert pdd55["summary"]["missing_runtime_variant_count"] == pdd55["summary"][
        "total_variant_count"
    ]
    assert {
        "pass2_wave33_metamorphic_variant_bundle_missing",
        "pass2_wave33_metamorphic_data_removal_probe_missing",
    } <= {finding["code"] for finding in pdd55["findings"]}

    assert pdd56["acceptance_gate_status"] == "failed"
    assert pdd56["summary"]["runtime_multilingual_pair_count"] == 0
    assert pdd56["summary"]["transliteration_variant_count"] == 0
    assert pdd56["summary"]["mixed_language_variant_count"] == 0
    assert {
        "pass2_wave33_multilingual_runtime_pair_missing",
        "pass2_transliteration_variant_contract_missing",
        "pass2_mixed_language_variant_contract_missing",
        "pass2_wave33_hardcoded_language_path_audit_missing",
    } <= {finding["code"] for finding in pdd56["findings"]}


def test_phase34_1_payload_fails_closed_when_wave33_artifacts_are_missing(
    tmp_path: Path,
) -> None:
    wave33_dir = tmp_path / "wave-33"
    wave33_dir.mkdir()

    payload = diag.build_phase34_1_payload(
        repo_root=REPO_ROOT,
        wave33_dir=wave33_dir,
    )

    assert payload["status"] == "blocked"
    assert payload["summary"]["input_issue_count"] == len(diag.REQUIRED_WAVE33_ARTIFACTS)
    assert {
        issue["code"] for issue in payload["input_evidence"]["issues"]
    } == {"pass2_wave33_required_artifact_missing"}
    assert {
        report["acceptance_gate_status"] for report in payload["pdds"].values()
    } == {"blocked"}


def test_phase34_1_main_writes_detailed_reports_and_backlog_fragments(
    tmp_path: Path,
) -> None:
    wave33_dir = _write_minimal_wave33(tmp_path)
    output_dir = tmp_path / "diagnostics"
    fragment_dir = output_dir / "pass2" / "backlog_fragments"

    exit_code = diag.main(
        [
            "--repo-root",
            str(REPO_ROOT),
            "--wave33-dir",
            str(wave33_dir),
            "--output-dir",
            str(output_dir),
            "--fragment-dir",
            str(fragment_dir),
        ]
    )

    phase_payload = json.loads(
        (output_dir / "pass2" / "phase34_1_cross_domain_metamorphic_diagnostics.json")
        .read_text(encoding="utf-8")
    )

    assert exit_code == 0
    assert phase_payload["status"] == "diagnosed"
    for pdd_id, slug in diag.PDD_ARTIFACTS.items():
        pdd_dir = output_dir / pdd_id.lower()
        assert (pdd_dir / f"{slug}.json").exists()
        assert (pdd_dir / f"{slug}.md").exists()
        assert (pdd_dir / "summary.md").exists()
        assert (fragment_dir / f"{pdd_id.lower()}.md").exists()
        assert f"{pdd_id}:fragment" in phase_payload["output"]


def test_phase34_2_payload_records_adversarial_fail_closed_gaps(
    tmp_path: Path,
) -> None:
    wave33_dir = _write_phase34_2_wave33(tmp_path)

    payload = diag.build_phase34_2_payload(
        repo_root=REPO_ROOT,
        wave33_dir=wave33_dir,
    )

    pdd38 = payload["pdds"]["PDD-038"]

    assert payload["status"] == "diagnosed"
    assert payload["summary"]["fail_closed_baseline"]["status"] == "confirmed"
    assert pdd38["acceptance_gate_status"] == "failed"
    assert pdd38["summary"]["required_scenario_count"] == len(
        diag.PDD038_ADVERSARIAL_SCENARIOS
    )
    assert pdd38["summary"]["not_run_scenario_count"] >= 4
    assert {
        "pass2_wave33_baseline_fails_closed",
        "pass2_pdd038_adversarial_scenario_evidence_missing",
        "pass2_pdd038_security_prompt_injection_probes_missing",
    } <= {finding["code"] for finding in pdd38["findings"]}


def test_phase34_2_payload_records_cache_error_and_strategic_gaps(
    tmp_path: Path,
) -> None:
    wave33_dir = _write_phase34_2_wave33(tmp_path)

    payload = diag.build_phase34_2_payload(
        repo_root=REPO_ROOT,
        wave33_dir=wave33_dir,
    )

    pdd64 = payload["pdds"]["PDD-064"]
    pdd65 = payload["pdds"]["PDD-065"]
    pdd98 = payload["pdds"]["PDD-098"]

    assert pdd64["acceptance_gate_status"] == "failed"
    assert pdd64["summary"]["cache_event_count"] == 1
    assert pdd64["summary"]["scorecard_snapshot_source_blocker_count"] == 3
    assert {
        "pass2_pdd064_index_cache_fingerprint_ledger_missing",
        "pass2_pdd064_snapshot_source_gaps_fail_closed",
        "pass2_pdd064_poisoning_negative_tests_missing",
    } <= {finding["code"] for finding in pdd64["findings"]}

    assert pdd65["acceptance_gate_status"] == "failed"
    assert pdd65["summary"]["root_cause_preserving_surface_count"] == 3
    assert pdd65["summary"]["collapsed_summary_surface_count"] == 1
    assert pdd65["summary"]["taxonomy_artifact_present"] is False
    assert {
        "pass2_pdd065_detailed_surfaces_preserve_root_cause",
        "pass2_pdd065_readiness_summary_collapses_failure_semantics",
        "pass2_pdd065_error_taxonomy_artifact_missing",
    } <= {finding["code"] for finding in pdd65["findings"]}

    assert pdd98["acceptance_gate_status"] == "failed"
    assert pdd98["summary"]["strategic_ledger_present"] is False
    assert pdd98["summary"]["missing_requirement_count"] == 4
    assert {
        "pass2_pdd098_strategic_behavior_ledger_missing",
        "pass2_pdd098_monitoring_text_generic_not_mechanism_bound",
        "pass2_pdd098_closeout_failure_indirect_not_strategic_gate",
    } <= {finding["code"] for finding in pdd98["findings"]}


def test_phase34_2_main_writes_detailed_reports_and_backlog_fragments(
    tmp_path: Path,
) -> None:
    wave33_dir = _write_phase34_2_wave33(tmp_path)
    output_dir = tmp_path / "diagnostics"
    fragment_dir = output_dir / "pass2" / "backlog_fragments"

    exit_code = diag.main(
        [
            "--repo-root",
            str(REPO_ROOT),
            "--wave33-dir",
            str(wave33_dir),
            "--output-dir",
            str(output_dir),
            "--fragment-dir",
            str(fragment_dir),
            "--phase",
            "34.2",
        ]
    )

    phase_payload = json.loads(
        (
            output_dir
            / "pass2"
            / "phase34_2_adversarial_fail_closed_diagnostics.json"
        ).read_text(encoding="utf-8")
    )

    assert exit_code == 0
    assert phase_payload["status"] == "diagnosed"
    for pdd_id, slug in diag.PDD_ARTIFACTS_PHASE34_2.items():
        pdd_dir = output_dir / pdd_id.lower()
        assert (pdd_dir / f"{slug}.json").exists()
        assert (pdd_dir / f"{slug}.md").exists()
        assert (pdd_dir / "summary.md").exists()
        assert (fragment_dir / f"{pdd_id.lower()}.md").exists()
        assert f"{pdd_id}:fragment" in phase_payload["output"]


def test_phase34_4_main_writes_canonical_extraction_measurement_reports(
    tmp_path: Path,
) -> None:
    output_root = tmp_path / "diagnostics"

    exit_code = diag34_4.main(
        [
            "--repo-root",
            str(REPO_ROOT),
            "--wave33-dir",
            str(_actual_wave33_dir()),
            "--output-root",
            str(output_root),
        ]
    )

    phase_payload = json.loads(
        (
            output_root
            / "pass2"
            / "phase_34_4_extraction_measurement_diagnostics.json"
        ).read_text(encoding="utf-8")
    )

    assert exit_code == 0
    assert phase_payload["wave"] == "34"
    assert phase_payload["phase"] == "34.4"
    assert phase_payload["status"] == "diagnosed"
    assert phase_payload["runtime_acceptance_status"] == "failed"

    for pdd_id, spec in diag34_4.PDD_SPECS.items():
        detail = json.loads(
            (output_root / pdd_id.lower() / f"{spec['slug']}.json").read_text(
                encoding="utf-8"
            )
        )
        _assert_canonical_wave34_detail(
            detail,
            pdd_id=pdd_id,
            phase="34.4",
            expected_gate_prefix="failed",
        )
        assert (output_root / pdd_id.lower() / f"{spec['slug']}.md").exists()
        assert (output_root / pdd_id.lower() / "summary.md").exists()
        assert (
            output_root / "pass2" / "backlog_fragments" / f"{pdd_id.lower()}.md"
        ).exists()


def test_phase34_5_main_writes_canonical_operational_recovery_reports(
    tmp_path: Path,
) -> None:
    output_root = tmp_path / "diagnostics"

    exit_code = diag34_5.main(
        [
            "--repo-root",
            str(REPO_ROOT),
            "--wave33-dir",
            str(_actual_wave33_dir()),
            "--output-root",
            str(output_root),
        ]
    )

    phase_payload = json.loads(
        (
            output_root
            / "pass2"
            / "phase_34_5_operational_recovery_diagnostics.json"
        ).read_text(encoding="utf-8")
    )

    assert exit_code == 0
    assert phase_payload["wave"] == "34"
    assert phase_payload["phase"] == "34.5"
    assert phase_payload["status"] == "diagnosed"
    assert phase_payload["runtime_acceptance_status"] == "failed"

    for pdd_id, spec in diag34_5.PDD_SPECS.items():
        detail = json.loads(
            (output_root / pdd_id.lower() / f"{spec['slug']}.json").read_text(
                encoding="utf-8"
            )
        )
        _assert_canonical_wave34_detail(
            detail,
            pdd_id=pdd_id,
            phase="34.5",
            expected_gate_prefix="failed",
        )
        assert (output_root / pdd_id.lower() / f"{spec['slug']}.md").exists()
        assert (output_root / pdd_id.lower() / "summary.md").exists()
        assert (
            output_root / "pass2" / "backlog_fragments" / f"{pdd_id.lower()}.md"
        ).exists()


def test_phase34_6_main_reproduces_canonical_human_facing_packet(
    tmp_path: Path,
) -> None:
    output_root = tmp_path / "diagnostics"

    exit_code = diag34_6.main(
        [
            "--repo-root",
            str(REPO_ROOT),
            "--wave33-dir",
            str(_actual_wave33_dir()),
            "--output-root",
            str(output_root),
        ]
    )

    phase_payload = json.loads(
        (
            output_root
            / "pass2"
            / "phase_34_6_human_facing_legitimacy_memory_diagnostics.json"
        ).read_text(encoding="utf-8")
    )

    assert exit_code == 0
    assert phase_payload["wave"] == "34"
    assert phase_payload["phase"] == "34.6"
    assert phase_payload["status"] == "diagnosed"
    assert phase_payload["runtime_acceptance_status"] == "failed"

    for pdd_id, spec in diag34_6.PDD_SPECS.items():
        detail = json.loads(
            (output_root / pdd_id.lower() / f"{spec['slug']}.json").read_text(
                encoding="utf-8"
            )
        )
        _assert_canonical_wave34_detail(
            detail,
            pdd_id=pdd_id,
            phase="34.6",
            expected_gate_prefix="failed",
        )
        assert "recommended_remediation_id" in detail
        assert "promoted_remediation" not in detail


def test_wave34_exit_fence_validator_rejects_wrong_wave_metadata(
    tmp_path: Path,
) -> None:
    output_root = tmp_path / "diagnostics"
    _write_complete_wave34_packet(output_root)

    assert (
        wave34_check.main(
            [
                "--repo-root",
                str(REPO_ROOT),
                "--diagnostics-root",
                str(output_root),
            ]
        )
        == 0
    )

    pdd100_path = (
        output_root / "pdd-100" / "document_extraction_authority_audit.json"
    )
    payload = json.loads(pdd100_path.read_text(encoding="utf-8"))
    payload["wave"] = "33"
    pdd100_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    assert (
        wave34_check.main(
            [
                "--repo-root",
                str(REPO_ROOT),
                "--diagnostics-root",
                str(output_root),
            ]
        )
        == 1
    )


def _write_minimal_wave33(
    tmp_path: Path,
    *,
    scenario_id: str = "ukraine_msme_wartime_credit_support",
) -> Path:
    wave33_dir = tmp_path / "wave-33"
    wave33_dir.mkdir()
    _write_json(
        wave33_dir / "real_domain_baseline.json",
        {
            "wave": 33,
            "status": "baseline_recorded",
            "exit_fence": {"status": "pass"},
            "research_profile_case": {
                "run_id": "R_test",
                "job_id": "job-test",
                "case_id": "pdc-R_test",
                "bundle_path": ".polisyos/test-bundle",
                "authority_profile": {"effective_execution_profile": "research"},
                "stage_evidence": {"readiness": {"status": "fail"}},
            },
        },
    )
    _write_json(
        wave33_dir / "research_real_domain_matrix.json",
        {
            "lanes": [
                {
                    "scenario": "public_golden",
                    "command": [
                        "python3",
                        "-m",
                        "tools.ops_runners.runtime.local_production_canary",
                        f"--quality-scenario={scenario_id}",
                    ],
                }
            ]
        },
    )
    _write_json(
        wave33_dir / "policy_design_case_sample.json",
        {
            "case_id": "pdc-R_test",
            "run_id": "R_test",
            "job_id": "job-test",
            "authority_profile": {"effective_execution_profile": "research"},
            "intent_envelope": {
                "jurisdiction": "UA",
                "policy_time": "2026-05-15",
                "data_time": "2024-2026",
                "policy_problem": "Wartime MSMEs face liquidity constraints.",
                "desired_outcome": "msme_survival_rate",
                "proposed_intervention": "wartime_credit_support",
                "target_population": "Ukrainian wartime MSMEs",
            },
        },
    )
    _write_json(
        wave33_dir / "quality_scorecard.json",
        {
            "quality_status": "fail",
            "approval_state": "quality_failed",
            "quality_gates": [
                {
                    "name": "normative_evidence_present",
                    "code": "legal_retrieval_trace_missing",
                    "stage": "lex",
                    "status": "fail",
                    "blocking": True,
                    "evidence_ref": "quality_evidence/normative_evidence.json",
                }
            ],
        },
    )
    _write_json(
        wave33_dir / "readiness.json",
        {
            "status": "fail",
            "passes_required": False,
            "minimum_closeout_gate_failures": ["policy_design_concept_unresolved"],
        },
    )
    _write_json(
        wave33_dir / "production_data_evidence.json",
        {
            "context": {"bundles": {"curated": {"readiness": "ready"}}},
            "materialization_refs": {"production_data_quality": "sha256:test"},
        },
    )
    _write_json(
        wave33_dir / "claim_argument.json",
        {
            "claim": {"status": "blocked"},
            "subclaims": [],
        },
    )
    _write_json(wave33_dir / "policy_grounding_matrix.json", {"status": "pass"})
    return wave33_dir


def _write_phase34_2_wave33(tmp_path: Path) -> Path:
    wave33_dir = tmp_path / "wave-33"
    wave33_dir.mkdir()
    bundle_dir = tmp_path / "bundle"
    quality_dir = bundle_dir / "quality_evidence"
    quality_dir.mkdir(parents=True)
    blocker_codes = [
        "policy_design_jurisdiction_unresolved_competence_blocker",
        "selected_source_missing_source_rights",
        "semantic_fabric_source_facet_incomplete",
        "method_identification_requirements_missing",
        "data_forge_snapshot_binding_missing",
    ]
    blockers = [
        {
            "code": code,
            "message": f"{code} blocks closeout.",
            "layer": "test",
            "phase": "test_phase",
            "evidence_ref": "quality_evidence/test.json",
            "next_action": "Provide missing evidence.",
        }
        for code in blocker_codes
    ]
    _write_json(
        wave33_dir / "real_domain_baseline.json",
        {
            "wave": 33,
            "status": "baseline_recorded",
            "exit_fence": {"status": "pass"},
            "research_profile_case": {
                "matrix_status": "failed",
                "failure_code": "canary_scorecard_failed",
                "scorecard_status": "fail",
                "run_id": "R_phase34_2",
                "job_id": "job-phase34-2",
                "case_id": "pdc-phase34-2",
                "bundle_path": str(bundle_dir),
                "authority_profile": {"effective_execution_profile": "research"},
                "stage_evidence": {"readiness": {"status": "fail"}},
            },
        },
    )
    _write_json(
        wave33_dir / "research_real_domain_matrix.json",
        {
            "lanes": [
                {
                    "scenario": "public_golden",
                    "command": [
                        "python3",
                        "-m",
                        "tools.ops_runners.runtime.local_production_canary",
                        "--quality-scenario=ukraine_msme_wartime_credit_support",
                    ],
                }
            ]
        },
    )
    _write_json(
        wave33_dir / "policy_design_case_sample.json",
        {
            "case_id": "pdc-phase34-2",
            "run_id": "R_phase34_2",
            "job_id": "job-phase34-2",
            "authority_profile": {"effective_execution_profile": "research"},
            "intent_envelope": {
                "jurisdiction": "UA",
                "policy_time": "2026-05-15",
                "data_time": "2024-2026",
                "policy_problem": "Wartime MSMEs face liquidity constraints.",
                "desired_outcome": "msme_survival_rate",
                "proposed_intervention": "wartime_credit_support",
                "target_population": "Ukrainian wartime MSMEs",
            },
            "jurisdiction_spine": {
                "status": "blocked",
                "blockers": [
                    {
                        "code": "policy_design_jurisdiction_unresolved_competence_blocker",
                        "missing_input": "competence evidence for UA",
                    }
                ],
            },
        },
    )
    _write_json(
        wave33_dir / "quality_scorecard.json",
        {
            "quality_status": "fail",
            "approval_state": "quality_failed",
            "blocking_quality_failures": blockers,
            "quality_gates": [
                {
                    "name": code,
                    "code": code,
                    "stage": "test",
                    "status": "fail",
                    "blocking": True,
                    "evidence_ref": "quality_evidence/test.json",
                }
                for code in blocker_codes
            ],
        },
    )
    _write_json(
        wave33_dir / "readiness.json",
        {
            "status": "fail",
            "passes_all": False,
            "passes_required": False,
            "minimum_closeout_gate_failures": [
                {
                    "code": "selected_source_missing_source_rights",
                    "status": "fail",
                    "next_action": "Record source rights.",
                },
                {
                    "code": "method_identification_requirements_missing",
                    "status": "fail",
                    "next_action": "Emit method identification.",
                },
            ],
            "summary": {
                "status_counts": {"fail": 0, "pass": 2, "warn": 0},
                "failure_class_counts": {
                    "quality_failure": {"fail": 0, "pass": 2, "warn": 0, "total": 2}
                },
            },
            "component_failures": [],
            "component_results": {
                "readiness_aggregator": {"status": "pass"},
            },
        },
    )
    _write_json(
        wave33_dir / "production_data_evidence.json",
        {
            "context": {"bundles": {"curated": {"readiness": "ready"}}},
            "materialization_refs": {"production_data_quality": "sha256:test"},
        },
    )
    _write_json(
        wave33_dir / "claim_argument.json",
        {
            "claim": {"status": "blocked"},
            "blockers": blockers[:3],
            "subclaims": [],
        },
    )
    _write_json(
        wave33_dir / "policy_grounding_matrix.json",
        {
            "status": "pass",
            "claims": [
                {
                    "claim_id": "deterministic_recommendation_1",
                    "implementation_risks": [
                        "Monitor take-up, leakage, and delivery capacity."
                    ],
                    "monitoring_plan": [
                        "Track outcome, treatment, subgroup, and budget indicators."
                    ],
                    "withdrawal_reissue_triggers": [
                        "Withdraw or reissue if monitoring violates guardrails."
                    ],
                }
            ],
        },
    )
    _write_json(quality_dir / "security_assurance_report.json", {"status": "pass"})
    _write_json(
        quality_dir / "prompt_tool_ledger.json",
        {
            "summary": {"status": "pass", "step_count": 3},
            "steps": [{"prompt_fingerprint": "sha256:test"}],
        },
    )
    _write_json(quality_dir / "conflict_check.json", {"status": "pass"})
    _write_json(
        quality_dir / "fabric_retrieval_trace.json",
        {
            "status": "fail",
            "manifest_ref": "cas-manifest://sha256:test",
            "issues": [
                {"code": "selected_source_missing_source_rights"},
                {"code": "selected_source_missing_schema_ref"},
            ],
        },
    )
    _write_json(
        quality_dir / "production_data_quality.json",
        {
            "status": "pass",
            "authority_envelope": {
                "same_input_closure": {
                    "production_data_manifest_ref": "production-data-manifest:sha256:test"
                }
            },
        },
    )
    _write_json(
        quality_dir / "foundry_method_report.json",
        {
            "status": "fail",
            "issues": [{"code": "method_identification_requirements_missing"}],
        },
    )
    _write_json(
        quality_dir / "decision_artifact_quality.json",
        {
            "status": "fail",
            "issues": [{"code": "claim_compiler_runtime_registry_missing"}],
        },
    )
    _write_json(
        bundle_dir / "timeline.json",
        {
            "events": [
                {
                    "phase": "scientist.node.build_data_snapshot",
                    "event": "NODE_CACHE_STORE",
                    "metrics": {"cache_store": 1},
                    "refs": {
                        "outputs": [
                            {
                                "kind": "scientist.node_cache_entry",
                                "artifact_id": "sha256:test",
                            }
                        ]
                    },
                }
            ]
        },
    )
    return wave33_dir


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _actual_wave33_dir() -> Path:
    return REPO_ROOT / "_build" / "policy-design-case" / "rebaseline" / "wave-33"


def _assert_canonical_wave34_detail(
    payload: dict[str, object],
    *,
    pdd_id: str,
    phase: str,
    expected_gate_prefix: str,
) -> None:
    assert payload["schema_version"]
    assert payload["tool"]
    assert payload["generated_at"]
    assert payload["wave"] == "34"
    assert payload["phase"] == phase
    assert payload["pdd_id"] == pdd_id
    assert payload["title"]
    assert payload["question"]
    assert payload["diagnostic_status"] == "diagnosed"
    assert str(payload["acceptance_gate_status"]).startswith(expected_gate_prefix)
    assert payload["verdict"]
    assert payload["recommended_gate"]
    assert payload["backlog_summary"]
    assert isinstance(payload["findings"], list)
    assert isinstance(payload["wave33"], dict)
    assert payload["wave33"]["run_id"]
    assert payload["wave33"]["bundle_path"]
    assert isinstance(payload["source_artifacts"], dict)
    assert payload["source_artifacts"]["real_domain_baseline"]


def _write_complete_wave34_packet(output_root: Path) -> None:
    fragment_dir = output_root / "pass2" / "backlog_fragments"
    wave33_dir = _actual_wave33_dir()
    assert (
        diag.main(
            [
                "--repo-root",
                str(REPO_ROOT),
                "--wave33-dir",
                str(wave33_dir),
                "--output-dir",
                str(output_root),
                "--fragment-dir",
                str(fragment_dir),
            ]
        )
        == 0
    )
    assert (
        diag.main(
            [
                "--repo-root",
                str(REPO_ROOT),
                "--wave33-dir",
                str(wave33_dir),
                "--output-dir",
                str(output_root),
                "--fragment-dir",
                str(fragment_dir),
                "--phase",
                "34.2",
            ]
        )
        == 0
    )
    assert (
        diag34_3.main(
            [
                "--repo-root",
                str(REPO_ROOT),
                "--wave33-dir",
                str(wave33_dir),
                "--output-root",
                str(output_root),
            ]
        )
        == 0
    )
    assert (
        diag34_4.main(
            [
                "--repo-root",
                str(REPO_ROOT),
                "--wave33-dir",
                str(wave33_dir),
                "--output-root",
                str(output_root),
            ]
        )
        == 0
    )
    assert (
        diag34_5.main(
            [
                "--repo-root",
                str(REPO_ROOT),
                "--wave33-dir",
                str(wave33_dir),
                "--output-root",
                str(output_root),
            ]
        )
        == 0
    )
    assert (
        diag34_6.main(
            [
                "--repo-root",
                str(REPO_ROOT),
                "--wave33-dir",
                str(wave33_dir),
                "--output-root",
                str(output_root),
            ]
        )
        == 0
    )
