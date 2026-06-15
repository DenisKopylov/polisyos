from __future__ import annotations

import json
from importlib import import_module
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]


def _validator() -> Any:
    return import_module("tools.quality.validation.check_policy_design_case_layer3_gx_hardening")


def _codes(report: dict[str, Any]) -> set[str]:
    return {str(issue["code"]) for issue in report.get("issues", [])}


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def test_gx_validator_reports_no_current_expected_red_overclaims() -> None:
    validator = _validator()

    report = validator.validate_layer3_gx_hardening(REPO_ROOT)

    assert report["status"] == "pass"
    assert report["issues"] == []
    assert "layer3_gx_readiness_manifest_overrides_reducer_output" not in _codes(report)
    assert not any("legacy" in code for code in _codes(report))
    literal_lint = report["artifacts"]["layer3_gx_runtime_literal_lint"]
    assert literal_lint["status"] == "pass"
    assert literal_lint["issues"] == []
    expected_red = report["artifacts"]["layer3_gx_expected_red_checks"]
    assert expected_red["status"] == "empty"
    assert expected_red["final_task12_complete"] is True
    assert expected_red["checks"] == []
    assert expected_red["covered_issue_fingerprints"] == []
    assert report["summary"]["positive_status_count"] == 0
    assert report["summary"]["expected_red_check_count"] == 0
    assert {
        "layer3_gx_pinned_request",
        "layer3_gx_concept_alias_seed_rows",
        "layer3_gx_scope_seed_rows",
        "layer3_gx_demand_pull_request",
        "layer3_gx_data_mutation_free_growth_test_report",
        "layer3_gx_final_pinned_route_outcome_report",
        "layer3_gx_final_blocker_audit_record",
    } <= set(report["artifacts"])
    producers = {
        row["producer_ref"]: row
        for row in report["artifacts"]["layer3_gx_producer_registry"]["producers"]
    }
    assert producers[
        "external-request://layer3-gx/pinned-request/ua-msme-affordable-loans-2022"
    ]["producer_type"] == "external_request"
    assert producers[
        "external-request://layer3-gx/scope/ua-msme-affordable-loans-2022"
    ]["producer_type"] == "external_request"
    assert producers[
        "external-request://layer3-gx/demand-pull/ua-msme-affordable-loans-2022"
    ]["producer_type"] == "external_request"


def test_task6_gx_data_mutation_free_growth_report_covers_required_slices() -> None:
    validator = _validator()

    report = validator.build_data_mutation_free_growth_test_report(REPO_ROOT)
    rows = {row["requirement_id"]: row for row in report["coverage_rows"]}

    assert report["status"] == "pass"
    assert set(report["required_requirement_ids"]) <= set(rows)
    assert report["missing_requirement_ids"] == []
    assert all(row["test_refs"] for row in rows.values())
    assert rows["g1_dcat_metric_binding_insertion"]["production_readiness_status"] == (
        "bounded_surrogate"
    )
    assert rows["g1_canonical_overlay_injection"]["authority_boundary"] == {
        "can_create_source_contract": False,
        "can_create_admission": False,
        "can_create_promotion": False,
        "can_create_conversion": False,
    }
    assert rows["canonical_corpus_pinned_request_search_health"][
        "requires_corpus_snapshot_hash"
    ] is True


def test_gx_producer_registry_wires_g1_measurement_replay_contracts() -> None:
    validator = _validator()

    registry = validator.build_producer_registry(REPO_ROOT)
    producers = {
        row["producer_ref"]: row
        for row in registry["producers"]
        if row.get("producer_ref")
    }

    assert {
        "measurement://layer3-g1/l1-dcat-search-recall",
        "measurement://layer3-g1/l1-dcat-search-ledgers",
    } <= set(producers)
    for producer_ref in (
        "measurement://layer3-g1/l1-dcat-search-recall",
        "measurement://layer3-g1/l1-dcat-search-ledgers",
    ):
        producer = producers[producer_ref]
        assert producer["producer_type"] == "measurement"
        assert all(
            producer.get(key)
            for key in validator.MEASUREMENT_REPLAY_REQUIRED_KEYS
        )

    replay = validator.build_measurement_replay_report(
        REPO_ROOT,
        producer_registry=registry,
    )

    assert replay["status"] == "pass"
    assert replay["measurement_root_count"] >= 2
    assert "layer3_gx_measurement_replay_not_measured" not in _codes(replay)
    assert all(row["replayable"] for row in replay["records"])


def test_gx_producer_registry_refreshes_g1_measurement_rows_from_artifacts(
    tmp_path: Path,
) -> None:
    validator = _validator()
    _write_json(
        tmp_path / "architecture/policy_design_case/layer3_gx_producer_registry.json",
        {
            "producers": [
                {
                    "producer_ref": "measurement://layer3-g1/l1-dcat-search-recall",
                    "producer_type": "measurement",
                    "corpus_ref": "duckdb://stale#table",
                }
            ]
        },
    )
    _write_json(
        tmp_path / "architecture/policy_design_case/layer3_g1_search_recall_freshness.json",
        {
            "search_recall_freshness": {
                "canonical_corpus_path": "fresh/dataset_catalog.duckdb",
                "corpus_kind": "canonical",
                "corpus_ref": "duckdb://fresh/dataset_catalog.duckdb#ds_metric_bindings",
                "corpus_snapshot_hash": "sha256:" + "a" * 64,
                "measurement_provenance": "l1_dcat_query",
                "query_trace_refs": ["g1-query-trace:fresh"],
                "query_expansion_trace_refs": ["query-hash:fresh"],
                "replay_command": (
                    "uv run python "
                    "tools/quality/validation/check_policy_design_case_layer3_g1_readiness.py "
                    "--repo-root . --write"
                ),
                "replay_expected_output_hash": "sha256:" + "b" * 64,
            }
        },
    )

    registry = validator.build_producer_registry(tmp_path)
    producers = {
        row["producer_ref"]: row
        for row in registry["producers"]
        if row.get("producer_ref")
    }
    producer = producers["measurement://layer3-g1/l1-dcat-search-recall"]

    assert producer["corpus_ref"] == (
        "duckdb://fresh/dataset_catalog.duckdb#ds_metric_bindings"
    )
    assert producer["expected_output_hash"] == "sha256:" + "b" * 64
    assert producer["measurement_id"] == "layer3-g1-l1-dcat-search-recall"


def test_task9_gx_g4_g5_waist_court_report_is_registered_and_diagnostic() -> None:
    validator = _validator()

    report = validator.validate_layer3_gx_hardening(REPO_ROOT)
    artifact = report["artifacts"]["layer3_gx_g4_g5_dereference_waist_court_report"]

    assert report["status"] == "pass"
    assert report["summary"]["g4_g5_waist_court_status"] == "partial"
    assert artifact["schema_version"] == (
        "policyos.policy_design_case.layer3_gx_g4_g5_dereference_waist_court.v1"
    )
    assert artifact["status"] == "partial"
    assert artifact["scope"] == "gx_vertical_pinned_route_only"
    assert artifact["g4"]["reducer_id"] == "reduce_g4_promotion_state"
    assert artifact["g5"]["reducer_id"] == "reduce_g5_conversion_outcome"
    assert artifact["g4"]["input_ref_status"] in {"pass", "blocked"}
    assert artifact["g5"]["input_ref_status"] in {"pass", "blocked"}
    assert artifact["g5"]["demand_pull_artifact_metadata_status"] == "pass"
    assert "layer3_gx_task9_multi_family_pending" in artifact["issue_codes"]
    assert "conversion_authority" in artifact["may_not_use_for"]
    assert "promotion_authority" in artifact["may_not_use_for"]


def test_gx_correction_log_records_recomputed_clean_replacement(tmp_path: Path) -> None:
    validator = _validator()
    hardcode_delta = (
        tmp_path
        / "architecture/policy_design_case/layer3_g1_hardcode_strangle_delta.json"
    )
    _write_json(
        hardcode_delta,
        {
            "hardcode_strangle_delta": {
                "fallback_deletion_status": "deleted_or_disabled_no_fallback",
                "issue_codes": [],
            },
            "schema_version": "policyos.policy_design_case.layer3_g1_substrate_grounding.v1",
        },
    )

    report = validator.build_correction_retraction_log(
        tmp_path,
        runtime_literal_lint={"status": "pass", "issues": []},
    )

    assert report["status"] == "pass"
    assert report["issues"] == []
    assert report["records"][0]["corrected_false_artifact_ref"].endswith(
        "layer3_g1_hardcode_strangle_delta.json#fallback_deletion_status"
    )
    assert report["records"][0]["replacement_status"] == "recomputed_clean"
    assert (
        report["records"][0]["recomputed_replacement_status"]
        == "deleted_or_disabled_no_fallback"
    )


def test_gx_runtime_literal_lint_flags_new_builder_literal(tmp_path: Path) -> None:
    validator = _validator()
    source = tmp_path / "src/polisyos/runtime/quality/new_builder.py"
    source.parent.mkdir(parents=True)
    source.write_text(
        """
def build_layer3_probe():
    return {"status": "grounded_or_uncertain", "promotion_state": "governed_promoted"}
""".lstrip(),
        encoding="utf-8",
    )

    report = validator.build_runtime_literal_lint(
        tmp_path,
        scan_roots=(Path("src/polisyos/runtime"),),
    )

    assert report["status"] == "fail"
    assert "layer3_gx_runtime_literal_forbidden" in _codes(report)
    assert any(
        issue["literal"] == "grounded_or_uncertain" and issue["path"].endswith("new_builder.py")
        for issue in report["issues"]
    )


def test_gx_runtime_literal_lint_flags_forbidden_domain_identifier(
    tmp_path: Path,
) -> None:
    validator = _validator()
    source = tmp_path / "src/polisyos/runtime/quality/probe.py"
    source.parent.mkdir(parents=True)
    source.write_text(
        """
def probe_firm_survival_source_contract_v2_groundability():
    return None
""".lstrip(),
        encoding="utf-8",
    )

    report = validator.build_runtime_literal_lint(
        tmp_path,
        scan_roots=(Path("src/polisyos/runtime"),),
    )

    assert report["status"] == "fail"
    assert any(
        issue["literal"] == "firm_survival"
        and issue["path"].endswith("probe.py")
        and issue["identifier"] == "probe_firm_survival_source_contract_v2_groundability"
        for issue in report["issues"]
    )


def test_gx_task1_runtime_core_has_no_forbidden_domain_identifiers() -> None:
    validator = _validator()

    report = validator.build_runtime_literal_lint(
        REPO_ROOT,
        scan_roots=(Path("src/polisyos/runtime"), Path("src/polisyos/core")),
    )

    forbidden_identifier_issues = [
        issue
        for issue in report["issues"]
        if issue["code"] == "layer3_gx_runtime_literal_forbidden"
        and issue.get("identifier")
    ]
    assert forbidden_identifier_issues == []


def test_gx_runtime_literal_lint_allows_non_status_pass_text(tmp_path: Path) -> None:
    validator = _validator()
    source = tmp_path / "src/polisyos/runtime/quality/general_status.py"
    source.parent.mkdir(parents=True)
    source.write_text(
        """
HELP_TEXT = "run this pass after setup"
""".lstrip(),
        encoding="utf-8",
    )

    report = validator.build_runtime_literal_lint(
        tmp_path,
        scan_roots=(Path("src/polisyos/runtime"),),
    )

    assert report["status"] == "pass"


def test_gx_digest_lint_rejects_repeated_and_non_hex_sha256(tmp_path: Path) -> None:
    validator = _validator()
    source = tmp_path / "src/polisyos/runtime/quality/digests.py"
    source.parent.mkdir(parents=True)
    source.write_text(
        """
REPEATED = "sha256:1111111111111111111111111111111111111111111111111111111111111111"
NON_HEX = "sha256:g5-g1"
""".lstrip(),
        encoding="utf-8",
    )

    report = validator.build_runtime_literal_lint(
        tmp_path,
        scan_roots=(Path("src/polisyos/runtime"),),
    )

    assert "layer3_gx_placeholder_digest_forbidden" in _codes(report)
    assert "layer3_gx_malformed_sha256_forbidden" in _codes(report)


def test_gx_digest_lint_allows_runtime_hash_prefix_builders(tmp_path: Path) -> None:
    validator = _validator()
    source = tmp_path / "src/polisyos/runtime/quality/digests.py"
    source.parent.mkdir(parents=True)
    source.write_text(
        """
import hashlib


def ref(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()
""".lstrip(),
        encoding="utf-8",
    )

    report = validator.build_runtime_literal_lint(
        tmp_path,
        scan_roots=(Path("src/polisyos/runtime"),),
    )

    assert report["status"] == "pass"


def test_gx_positive_status_without_reducer_provenance_fails(tmp_path: Path) -> None:
    validator = _validator()
    artifact = tmp_path / "architecture/policy_design_case/layer3_probe.json"
    _write_json(
        artifact,
        {
            "record_id": "probe-positive",
            "promotion_state": "governed_promoted",
            "producer_ref": "producer://probe/derivation",
        },
    )

    report = validator.build_positive_status_provenance(
        tmp_path,
        artifact_paths=(Path("architecture/policy_design_case/layer3_probe.json"),),
    )

    assert report["status"] == "fail"
    assert "layer3_gx_reducer_provenance_missing" in _codes(report)
    assert report["positive_status_count"] == 1


def test_gx_diagnostic_pass_without_producer_is_not_production_positive(
    tmp_path: Path,
) -> None:
    validator = _validator()
    artifact_path = Path("architecture/policy_design_case/layer3_probe.json")
    _write_json(
        tmp_path / artifact_path,
        {
            "conformance_report": {
                "report_id": "probe-diagnostic",
                "status": "pass",
                "issue_codes": [],
            }
        },
    )

    provenance = validator.build_positive_status_provenance(
        tmp_path,
        artifact_paths=(artifact_path,),
    )
    root_chain = validator.build_producer_root_chain_report(
        tmp_path,
        artifact_paths=(artifact_path,),
    )
    recompute = validator.build_persisted_status_recompute_drift(
        tmp_path,
        artifact_paths=(artifact_path,),
    )

    assert provenance["status"] == "pass"
    assert provenance["candidate_positive_status_count"] == 1
    assert provenance["positive_status_count"] == 0
    assert provenance["excluded_candidate_count"] == 1
    assert provenance["excluded_candidate_records"][0]["classification"] == (
        "diagnostic_positive_not_authority"
    )
    assert root_chain["status"] == "pass"
    assert root_chain["records"] == []
    assert recompute["status"] == "pass"
    assert recompute["issues"] == []


def test_gx_external_request_input_status_is_not_reducer_produced_authority(
    tmp_path: Path,
) -> None:
    validator = _validator()
    artifact_path = Path("architecture/policy_design_case/layer3_demand_input.json")
    _write_json(
        tmp_path / artifact_path,
        {
            "status": "pass",
            "producer_ref": "external-request://probe/demand",
            "producer_type": "external_request",
            "authority_purpose": "demand_pull_input_only",
            "may_not_use_for": ["conversion_authority", "production_authority"],
        },
    )

    provenance = validator.build_positive_status_provenance(
        tmp_path,
        artifact_paths=(artifact_path,),
    )
    recompute = validator.build_persisted_status_recompute_drift(
        tmp_path,
        artifact_paths=(artifact_path,),
    )

    assert provenance["status"] == "pass"
    assert provenance["candidate_positive_status_count"] == 1
    assert provenance["positive_status_count"] == 0
    assert provenance["excluded_candidate_records"][0]["classification"] == (
        "external_request_input_positive_not_reducer_output"
    )
    assert recompute["status"] == "pass"
    assert recompute["issues"] == []


def test_gx_hand_edited_positive_status_recompute_guard_fails(tmp_path: Path) -> None:
    validator = _validator()
    artifact = tmp_path / "architecture/policy_design_case/layer3_probe.json"
    _write_json(
        artifact,
        {
            "record_id": "probe-positive",
            "conversion_outcome": "grounded_limited",
            "producer_ref": "producer://probe/measurement",
            "produced_by": {
                "reducer_id": "reduce_probe",
                "reducer_version": "v1",
                "rule_version": "policyos.test",
                "input_hashes": {"input": "sha256:" + "2" * 64},
                "output_hash": "sha256:" + "3" * 64,
            },
        },
    )

    report = validator.build_persisted_status_recompute_drift(
        tmp_path,
        artifact_paths=(Path("architecture/policy_design_case/layer3_probe.json"),),
    )

    assert report["status"] == "fail"
    assert "layer3_gx_recompute_output_hash_mismatch" in _codes(report)


def test_gx_derivation_only_producer_chain_fails(tmp_path: Path) -> None:
    validator = _validator()
    artifact = tmp_path / "architecture/policy_design_case/layer3_probe.json"
    _write_json(
        artifact,
        {
            "record_id": "probe-positive",
            "grounding_closure_outcome": "grounded_or_uncertain",
            "producer_ref": "producer://probe/derivation",
            "produced_by": {
                "reducer_id": "reduce_probe",
                "reducer_version": "v1",
                "rule_version": "policyos.test",
                "input_hashes": {"input": "sha256:" + "4" * 64},
                "output_hash": "sha256:" + "5" * 64,
            },
        },
    )
    _write_json(
        tmp_path / "architecture/policy_design_case/layer3_gx_producer_registry.json",
        {
            "producers": [
                {
                    "producer_ref": "producer://probe/derivation",
                    "producer_type": "derivation",
                    "root_refs": [],
                }
            ]
        },
    )

    report = validator.build_producer_root_chain_report(
        tmp_path,
        artifact_paths=(Path("architecture/policy_design_case/layer3_probe.json"),),
    )

    assert report["status"] == "fail"
    assert "layer3_gx_producer_root_invalid" in _codes(report)


def test_gx_reducer_decision_report_enumerates_required_task4_reducers(
    tmp_path: Path,
) -> None:
    validator = _validator()

    report = validator.build_layer3_gx_reducer_decision_report(tmp_path)

    reducer_ids = {row["reducer_id"] for row in report["decisions"]}
    assert {
        "reduce_g1_source_grounding_closure",
        "reduce_g2_forecast_admission",
        "reduce_g3_proof_authority",
        "reduce_gl_legal_authority",
        "reduce_g4_promotion_state",
        "reduce_g5_conversion_outcome",
        "reduce_g7_region_closure",
        "reduce_g8_domain_vs_search_ceiling",
    } <= reducer_ids
    assert all(row["produced_by"]["output_hash"].startswith("sha256:") for row in report["decisions"])


def test_gx_vertical_pinned_route_uses_data_home_measured_search_and_reducers() -> None:
    validator = _validator()

    report = validator.build_layer3_gx_vertical_pinned_route_report(REPO_ROOT)

    assert report["case_id"] == "ua-msme-affordable-loans-2022"
    assert report["status"] == "blocked"
    assert report["final_outcome"] == "unchanged_blocker"
    assert report["data_home_status"] == "ready"
    assert report["g1_search_measurement_status"] == "blocked"

    decisions = {row["reducer_id"]: row for row in report["decisions"]}
    assert set(decisions) == {
        "reduce_g1_source_grounding_closure",
        "reduce_g4_promotion_state",
        "reduce_g5_conversion_outcome",
    }
    for decision in decisions.values():
        assert decision["produced_by"]["output_hash"].startswith("sha256:")
        assert "layer3_gx_inline_input_forbidden" not in decision["issue_codes"]
        assert "layer3_gx_required_input_ref_missing" not in decision["issue_codes"]

    assert (
        "repo://architecture/policy_design_case/layer3_gx_pinned_request.json"
        in decisions["reduce_g4_promotion_state"]["input_refs"]
    )
    assert (
        "repo://architecture/policy_design_case/layer3_gx_demand_pull_request.json"
        in decisions["reduce_g5_conversion_outcome"]["input_refs"]
    )
    assert "layer3_g1_search_health_not_measured_or_failed" in report["next_blocker_refs"]
    assert "layer3_g5_abstention_candidate_missing" in report["next_blocker_refs"]
    assert report["route_replay_key"].startswith("layer3-gx-vertical-pinned-route:")


def test_gx_provisional_task12_pinned_route_outcome_is_reducer_authored() -> None:
    validator = _validator()

    report = validator.build_layer3_gx_provisional_pinned_route_outcome_report(REPO_ROOT)

    assert (
        report["schema_version"]
        == "policyos.policy_design_case.layer3_gx_provisional_pinned_route_outcome.v1"
    )
    assert report["run_phase"] == "provisional_task12"
    assert report["status"] == "blocked"
    assert report["outcome_kind"] == "typed_blocker"
    assert report["outcome_source"] == "reduce_g5_conversion_outcome"
    assert report["g5_conversion_outcome"] == "unchanged_blocker"
    assert report["useful_design_credit"] is False
    assert report["route_replay_key"].startswith("layer3-gx-vertical-pinned-route:")
    assert report["provisional_run_hash"].startswith("sha256:")
    assert {
        "repo://architecture/policy_design_case/layer3_gx_vertical_pinned_route_report.json",
        "repo://architecture/policy_design_case/layer3_gx_provisional_blocker_audit_record.json",
    } <= set(report["persisted_artifact_refs"])

    reducer_calls = {row["reducer_id"]: row for row in report["reducer_calls"]}
    assert set(reducer_calls) == {
        "reduce_g1_source_grounding_closure",
        "reduce_g4_promotion_state",
        "reduce_g5_conversion_outcome",
    }
    for call in reducer_calls.values():
        assert call["rule_version"] == "policyos.layer3.gx.reducer_only_status.v1"
        assert call["input_hashes"]
        assert call["output_hash"].startswith("sha256:")

    assert "layer3_g5_grounded_evidence_ref_missing" in report["next_missing_refs"]
    assert "layer3_g1_search_health_not_measured_or_failed" in report["next_missing_refs"]
    assert "production_authority" in report["may_not_use_for"]
    assert "useful_design_credit" in report["may_not_use_for"]


def test_gx_provisional_task12_blocker_audit_record_cites_specific_evidence() -> None:
    validator = _validator()

    audit = validator.build_layer3_gx_provisional_blocker_audit_record(REPO_ROOT)

    assert (
        audit["schema_version"]
        == "policyos.policy_design_case.layer3_gx_provisional_blocker_audit.v1"
    )
    assert audit["audit_phase"] == "provisional_task12"
    assert audit["status"] == "blocked"
    assert audit["answer_status"] == "blocked_not_currently_publishable"
    assert audit["g8_open_question_surface_status"] == "not_required_until_task11"
    assert audit["blocker_specific_search_status"] == "not_measured"
    assert audit["g1_search_measurement_status"] == "blocked"
    assert audit["audit_record_hash"].startswith("sha256:")
    assert {
        "repo://architecture/policy_design_case/layer3_gx_vertical_pinned_route_report.json",
        "repo://architecture/policy_design_case/layer3_g1_search_recall_freshness.json",
        "repo://architecture/policy_design_case/layer3_g1_substrate_search_ledgers.json",
    } <= set(audit["cited_artifact_refs"])
    assert "layer3_g5_abstention_candidate_missing" in audit["next_blocker_refs"]
    assert "layer3_g1_search_health_not_measured_or_failed" in audit["next_blocker_refs"]
    assert "layer3_g4_missing_g1_grounded_source_contract" in audit["next_blocker_refs"]
    assert "production_authority" in audit["may_not_use_for"]
    assert "domain_ceiling_authority_without_gate" in audit["may_not_use_for"]


def test_gx_final_task12_pinned_route_outcome_uses_g8_audit_surface() -> None:
    validator = _validator()

    report = validator.build_layer3_gx_final_pinned_route_outcome_report(REPO_ROOT)

    assert (
        report["schema_version"]
        == "policyos.policy_design_case.layer3_gx_final_pinned_route_outcome.v1"
    )
    assert report["run_phase"] == "final_task12"
    assert report["status"] == "blocked"
    assert report["outcome_kind"] == "search_ceiling_repair_required"
    assert report["outcome_source"] == (
        "reduce_g5_conversion_outcome+reduce_g8_domain_vs_search_ceiling"
    )
    assert report["g5_conversion_outcome"] == "unchanged_blocker"
    assert report["g8_domain_vs_search_ceiling_status"] == "search_ceiling_repair_required"
    assert report["g8_open_question_answer_status"] == "blocked"
    assert report["g8_search_health_classification"]["current_blocker_status"] == "unmeasured"
    assert report["useful_design_credit"] is False
    assert report["final_run_hash"].startswith("sha256:")
    assert report["final_run_hash_basis"] == "report_without_final_run_hash"

    reducer_calls = {row["reducer_id"]: row for row in report["reducer_calls"]}
    assert set(reducer_calls) == {
        "reduce_g1_source_grounding_closure",
        "reduce_g4_promotion_state",
        "reduce_g5_conversion_outcome",
        "reduce_g8_domain_vs_search_ceiling",
    }
    g8_call = reducer_calls["reduce_g8_domain_vs_search_ceiling"]
    assert g8_call["status"] == "search_ceiling_repair_required"
    assert g8_call["rule_version"] == "policyos.layer3.gx.reducer_only_status.v1"
    assert g8_call["input_hashes"]
    assert g8_call["output_hash"].startswith("sha256:")
    assert g8_call["persisted_status_ref"].endswith("#g8_domain_vs_search_ceiling")

    assert {
        "repo://architecture/policy_design_case/layer3_gx_vertical_pinned_route_report.json",
        "repo://architecture/policy_design_case/layer3_gx_provisional_pinned_route_outcome_report.json",
        "repo://architecture/policy_design_case/layer3_gx_final_blocker_audit_record.json",
        "repo://architecture/policy_design_case/layer3_g8_readiness_manifest.json",
        "repo://architecture/policy_design_case/layer3_g8_domain_vs_search_ceiling_gate.json",
        "repo://architecture/policy_design_case/layer3_g8_open_question_answer_ledger.json",
        "repo://architecture/policy_design_case/layer3_g8_metric_governance_audit_surface.json",
        "repo://architecture/policy_design_case/layer3_g8_closeout_signal_consumer_gate.json",
    } <= set(report["persisted_artifact_refs"])
    assert "layer3_g8_blocker_specific_search_diagnostic_missing" in report["issue_codes"]
    assert "layer3_g8_blocker_specific_search_diagnostic_missing" in report["next_missing_refs"]
    assert "production_authority" in report["may_not_use_for"]
    assert "closeout_authority" in report["may_not_use_for"]
    assert "runtime_closeout_authority" in report["may_not_use_for"]
    assert "useful_design_credit" in report["may_not_use_for"]

    comparison = report["provisional_comparison"]
    assert comparison["provisional_run_hash"].startswith("sha256:")
    assert comparison["final_run_hash"] == report["final_run_hash"]
    assert {
        ("outcome_kind", "typed_blocker", "search_ceiling_repair_required"),
        ("g8_open_question_surface_status", "not_required_until_task11", "blocked"),
    } <= {
        (row["field"], row["provisional"], row["final"])
        for row in comparison["changed_statuses"]
    }
    assert any(
        row["reducer_id"] == "reduce_g8_domain_vs_search_ceiling"
        and row["change"] == "added_in_final_task12"
        for row in comparison["changed_reducer_inputs"]
    )
    assert any(
        row["producer_root_ref"]
        == "repo://architecture/policy_design_case/layer3_g8_domain_vs_search_ceiling_gate.json"
        and row["change"] == "added_in_final_task12"
        for row in comparison["changed_producer_roots"]
    )


def test_gx_final_task12_blocker_audit_consumes_task11_g8_surface() -> None:
    validator = _validator()

    audit = validator.build_layer3_gx_final_blocker_audit_record(REPO_ROOT)

    assert (
        audit["schema_version"]
        == "policyos.policy_design_case.layer3_gx_final_blocker_audit.v1"
    )
    assert audit["audit_phase"] == "final_task12"
    assert audit["status"] == "blocked"
    assert audit["answer_status"] == "blocked_not_currently_publishable"
    assert audit["g8_open_question_surface_status"] == "blocked"
    assert audit["blocker_specific_search_status"] == "unmeasured"
    assert audit["g8_domain_vs_search_ceiling_status"] == "search_ceiling_repair_required"
    assert audit["g8_domain_ceiling_claim_allowed"] is False
    assert audit["audit_record_hash"].startswith("sha256:")
    assert {
        "repo://architecture/policy_design_case/layer3_gx_vertical_pinned_route_report.json",
        "repo://architecture/policy_design_case/layer3_gx_provisional_blocker_audit_record.json",
        "repo://architecture/policy_design_case/layer3_g8_readiness_manifest.json",
        "repo://architecture/policy_design_case/layer3_g8_cross_metric_diagnosis.json",
        "repo://architecture/policy_design_case/layer3_g8_domain_vs_search_ceiling_gate.json",
        "repo://architecture/policy_design_case/layer3_g8_open_question_answer_ledger.json",
        "repo://architecture/policy_design_case/layer3_g8_metric_governance_audit_surface.json",
        "repo://architecture/policy_design_case/layer3_g8_closeout_signal_consumer_gate.json",
    } <= set(audit["cited_artifact_refs"])
    assert audit["audit_basis"]["task11_g8_surface_consumed"] is True
    assert audit["audit_basis"]["domain_ceiling_claim_allowed"] is False
    assert "layer3_g8_blocker_specific_search_diagnostic_missing" in audit["issue_codes"]
    assert "layer3_g8_blocker_specific_search_diagnostic_missing" in audit["next_blocker_refs"]
    assert "production_authority" in audit["may_not_use_for"]
    assert "closeout_authority" in audit["may_not_use_for"]
    assert "runtime_closeout_authority" in audit["may_not_use_for"]
    assert "domain_ceiling_authority_without_gate" in audit["may_not_use_for"]


def test_gx_readiness_manifest_cannot_override_reducer_blocker(
    tmp_path: Path,
) -> None:
    validator = _validator()
    manifest = tmp_path / "architecture/policy_design_case/layer3_g5_readiness_manifest.json"
    _write_json(
        manifest,
        {
            "status": "pass",
            "g5_conversion_outcome": "unchanged_blocker",
            "summary": {
                "g5_dependency_readiness_status": "fail",
                "g5_g4_dependency_status": "fail",
                "g5_upstream_scope_join_status": "fail",
            },
            "issue_codes": [],
        },
    )

    report = validator.build_layer3_gx_reducer_decision_report(tmp_path)

    assert report["status"] == "fail"
    assert "layer3_gx_readiness_manifest_overrides_reducer_output" in _codes(report)
    g5 = next(
        row
        for row in report["decisions"]
        if row["reducer_id"] == "reduce_g5_conversion_outcome"
    )
    assert g5["status"] == "unchanged_blocker"
    assert g5["readiness_status"] == "fail"


def test_gx_allows_g7_local_blocker_as_reducer_blocked_diagnostic(
    tmp_path: Path,
) -> None:
    validator = _validator()
    manifest = tmp_path / "architecture/policy_design_case/layer3_g7_readiness_manifest.json"
    _write_json(
        manifest,
        {
            "status": "pass",
            "status_authority_boundary": (
                "artifact_family_integrity_only_not_region_closure_authority"
            ),
            "region_closure_authority_status": "blocked",
            "g7_region_value_closure_status": "blocked_by_current_g5_unchanged_blocker",
            "summary": {
                "g7_region_value_closure_status": (
                    "blocked_by_current_g5_unchanged_blocker"
                ),
                "g7_current_g5_unchanged_blocker_status": "blocked",
            },
        },
    )
    valid = validator.Layer3ReducerInputRef(
        ref="repo://fixture/g7.json",
        content_hash="sha256:" + "1" * 64,
        producer_ref="fixture://g7",
        fixture_input=True,
    )
    decision = validator.reduce_g7_region_closure(
        validator.G7RegionClosureInputs(
            gx_migration_state="blocked_by_gx_migration",
            g5_conversion_outcome="grounded_limited",
            regional_breadth_status="pass",
            input_refs=(valid,),
        )
    )

    issues = validator._reducer_manifest_override_issues(tmp_path, (decision,))

    assert issues == []


def test_g7_readiness_manifest_declares_status_boundary() -> None:
    validator = import_module("tools.quality.validation.check_policy_design_case_layer3_g7_readiness")

    manifest = validator._readiness_manifest(
        REPO_ROOT,
        validator._build_runtime_bundle(REPO_ROOT),
        drift_keys=(),
        registration_statuses=validator._registration_statuses(REPO_ROOT),
    )

    assert (
        manifest["status_authority_boundary"]
        == "artifact_family_integrity_only_not_region_closure_authority"
    )
    assert manifest["region_closure_authority_status"] == "blocked"
    assert manifest["g7_region_value_closure_status"] == (
        "blocked_by_current_g5_unchanged_blocker"
    )


def test_gx_reducer_integrity_requires_valid_producer_root_chain() -> None:
    validator = _validator()
    positive_status_provenance = {
        "positive_status_count": 1,
        "records": [
            {
                "artifact_path": "architecture/policy_design_case/layer3_probe.json",
                "json_pointer": "$",
                "field": "promotion_state",
                "value": "governed_promoted",
                "producer_ref": "measurement://probe",
                "produced_by_present": True,
                "missing_produced_by_keys": [],
            }
        ],
    }
    producer_root_chain = {
        "status": "fail",
        "records": [
            {
                "artifact_path": "architecture/policy_design_case/layer3_probe.json",
                "json_pointer": "$",
                "producer_ref": "measurement://probe",
                "producer_type": "derivation",
                "valid_root_chain": False,
            }
        ],
    }

    report = validator.build_reducer_integrity_report(
        positive_status_provenance,
        producer_root_chain=producer_root_chain,
    )

    assert report["status"] == "fail"
    assert "layer3_gx_reducer_producer_root_chain_invalid" in _codes(report)


def test_gx_measurement_without_replay_contract_fails(tmp_path: Path) -> None:
    validator = _validator()
    _write_json(
        tmp_path / "architecture/policy_design_case/layer3_gx_producer_registry.json",
        {
            "producers": [
                {
                    "producer_ref": "producer://probe/measurement",
                    "producer_type": "measurement",
                    "corpus_ref": "corpus://probe",
                    "corpus_snapshot_hash": "sha256:" + "6" * 64,
                }
            ]
        },
    )

    report = validator.build_measurement_replay_report(tmp_path)

    assert report["status"] == "fail"
    assert "layer3_gx_measurement_replay_contract_missing" in _codes(report)


def test_gx_validation_authority_boundary_denies_legacy_green_g5() -> None:
    validator = _validator()

    boundary = validator.build_validation_authority_boundary(REPO_ROOT)
    rows = {row["slice_id"]: row for row in boundary["slices"]}

    assert rows["G5"]["old_validator_status"] == "pass"
    assert rows["G5"]["readiness_authority"] == "legacy_diagnostic_only"
    assert rows["G5"]["may_count_for_gx_closeout"] is False
    assert rows["G5"]["issue_codes"] == []
    assert "layer3_gx_legacy_green_not_authoritative" in rows["G5"][
        "legacy_diagnostic_codes"
    ]
    assert rows["G5"]["expected_red_eligible"] is False


def test_gx_validation_authority_boundary_is_enforced_not_expected_red() -> None:
    validator = _validator()

    boundary = validator.build_validation_authority_boundary(REPO_ROOT)

    assert boundary["status"] == "authority_boundary_enforced"
    assert boundary["issues"] == []
    assert boundary["legacy_diagnostic_count"] > 0
    assert all(row["may_count_for_gx_closeout"] is False for row in boundary["slices"])
