# ruff: noqa: S101

from __future__ import annotations

import json
from pathlib import Path

from tools.quality.validation import check_can_i_closeout


def _write_bundle(
    root: Path,
    *,
    include_revisions: bool = True,
    include_schema_verification: bool = True,
    live: bool = False,
) -> Path:
    quality_dir = root / "quality_evidence"
    quality_dir.mkdir(parents=True)
    bundle = {
        "schema_version": "policyos.canary_evidence.v1",
        "canary_kind": "research",
        "quality_status": "pass",
        "command": {
            "matrix_lane_id": (
                "profile-research__provider-live_gonka_proxy"
                "__data-canonical_production__scenario-public_golden__ui-api_only"
                if live
                else "profile-research__provider-simulated__data-canonical_production"
                "__scenario-public_golden__ui-api_only"
            )
        },
    }
    if include_revisions:
        bundle["git_sha"] = "abc123"
        bundle["code_revision"] = {"git_sha": "abc123", "source": "git"}
    (root / "bundle.json").write_text(json.dumps(bundle), encoding="utf-8")
    (quality_dir / "quality_scorecard.json").write_text(
        json.dumps(
            {
                "schema_version": "policyos.quality_scorecard.v1",
                "quality_status": "pass",
                "quality_gates": [
                    {
                        "name": "normative_evidence_present",
                        "status": "pass",
                        "reader_gate_version": (
                            "runtime.scorecard.normative_evidence_present.v2"
                        ),
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    report = {
        "schema_version": "policyos.lex.normative_applicability_report.v1",
        "status": "pass",
    }
    if include_schema_verification:
        report["schema_compatibility"] = {
            "decision": "compatible",
            "validation_ref": "sha256:" + "a" * 64,
            "reader_gate": "normative_evidence_present",
            "reader_gate_version": "runtime.scorecard.normative_evidence_present.v2",
        }
    (quality_dir / "normative_evidence.json").write_text(
        json.dumps(report),
        encoding="utf-8",
    )
    return root


def _write_w4_closeout_records(bundle: Path) -> None:
    quality_dir = bundle / "quality_evidence"
    records = {
        "policy_design_case_i4_graph.json": (
            "policyos.runtime.policy_design_case.wave4_i4_graph.v1"
        ),
        "policy_design_portfolio_effective_support.json": (
            "policyos.runtime.policy_design_case.portfolio_effective_support.v1"
        ),
        "lifecycle_reissue_report.json": (
            "policyos.runtime.policy_design_case.lifecycle_reissue_report.v1"
        ),
        "policy_design_case_projection_contract_fixture.json": (
            "policyos.runtime.policy_design_case.projection_contract_fixture.v1"
        ),
        "formal_invariants.json": "policyos.runtime.formal_invariants.v1",
        "source_truth.json": "policyos.runtime.source_truth.v1",
        "conflict_materialization_closeout.json": (
            "policyos.scientist.cross_graph.conflict_materialization.closeout.v1"
        ),
        "attestation.json": "policyos.runtime.attestation.v1",
        "semantic_binding_ledger.json": "policyos.runtime.semantic_binding.v1",
        "claim_registry.json": "policyos.runtime.claim_registry.v1",
        "policy_design_case.json": "policyos.policy_design_case.record_family_coverage.v1",
        "projection_publication_state.json": (
            "policyos.runtime.policy_design_case.projection_publication_state.v1"
        ),
        "run_cost_proportionality.json": "policyos.runtime.run_cost_proportionality.v1",
        "audit_verifier.json": "policyos.runtime.audit_verifier.v1",
    }
    for filename, schema_version in records.items():
        (quality_dir / filename).write_text(
            json.dumps(
                {
                    "schema_version": schema_version,
                    "status": "pass",
                    "authority_role": "runtime_reader",
                    "provenance_kind": "runtime_emitted",
                    "producer": f"fixture.{Path(filename).stem}",
                    "runtime_event_ref": f"event://w4d/{Path(filename).stem}",
                    "cas_ref": "sha256:" + "b" * 64,
                    "issues": [],
                }
            ),
            encoding="utf-8",
        )


def test_cli_writes_pass_record_for_verified_bundle(tmp_path: Path) -> None:
    bundle = _write_bundle(tmp_path / "bundle")
    output = tmp_path / "can_i_closeout.json"

    exit_code = check_can_i_closeout.main(
        [
            "--repo-root",
            str(Path.cwd()),
            "--bundle-dir",
            str(bundle),
            "--json-output",
            str(output),
        ]
    )
    payload = json.loads(output.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert payload["status"] == "pass"
    assert payload["producer_reader_matrix"][0]["status"] == "pass"


def test_cli_fails_live_bundle_without_revision(tmp_path: Path) -> None:
    bundle = _write_bundle(tmp_path / "bundle", include_revisions=False, live=True)
    output = tmp_path / "can_i_closeout.json"

    exit_code = check_can_i_closeout.main(
        [
            "--repo-root",
            str(Path.cwd()),
            "--bundle-dir",
            str(bundle),
            "--json-output",
            str(output),
        ]
    )
    payload = json.loads(output.read_text(encoding="utf-8"))

    assert exit_code == 2
    assert {issue["code"] for issue in payload["issues"]} >= {
        "closeout_git_sha_missing",
        "closeout_code_revision_missing",
    }


def test_cli_can_emit_fail_closed_closeout_reader_skeleton(tmp_path: Path) -> None:
    bundle = _write_bundle(tmp_path / "bundle")
    output = tmp_path / "can_i_closeout_reader.json"

    exit_code = check_can_i_closeout.main(
        [
            "--repo-root",
            str(Path.cwd()),
            "--bundle-dir",
            str(bundle),
            "--json-output",
            str(output),
            "--reader-skeleton",
        ]
    )
    payload = json.loads(output.read_text(encoding="utf-8"))

    assert exit_code == 2
    assert payload["schema_version"] == "policyos.runtime.can_i_closeout.reader_skeleton.v1"
    assert payload["status"] == "incomplete"
    assert payload["can_closeout"] is False
    assert payload["compatibility_record"]["status"] == "pass"
    assert payload["authority_envelope"]["authoritative_for"] == ["closeout_verdict"]
    assert "closeout_module_reader_stubbed" in {
        issue["code"] for issue in payload["issues"]
    }


def test_cli_can_emit_w4_closeout_integration_verdict_from_bundle(tmp_path: Path) -> None:
    bundle = _write_bundle(tmp_path / "bundle")
    _write_w4_closeout_records(bundle)
    output = tmp_path / "can_i_closeout_w4.json"

    exit_code = check_can_i_closeout.main(
        [
            "--repo-root",
            str(Path.cwd()),
            "--bundle-dir",
            str(bundle),
            "--json-output",
            str(output),
            "--reader-integration",
        ]
    )
    payload = json.loads(output.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert payload["schema_version"] == "policyos.runtime.can_i_closeout.integration.v1"
    assert payload["status"] == "closed"
    assert payload["can_closeout"] is True
    assert payload["summary"]["module_reader_count"] >= 10
    assert payload["compatibility_record"]["status"] == "pass"
    assert {
        row["module_id"]: row["status"] for row in payload["module_reader_results"]
    }["source_truth"] == "pass"


def test_w4_closeout_integration_requires_real_i4_wave4_records(tmp_path: Path) -> None:
    bundle = _write_bundle(tmp_path / "bundle")
    quality_dir = bundle / "quality_evidence"
    records = {
        "formal_invariants.json": "policyos.runtime.formal_invariants.v1",
        "source_truth.json": "policyos.runtime.source_truth.v1",
        "attestation.json": "policyos.runtime.attestation.v1",
        "semantic_binding_ledger.json": "policyos.runtime.semantic_binding.v1",
        "claim_registry.json": "policyos.runtime.claim_registry.v1",
        "policy_design_case.json": "policyos.policy_design_case.record_family_coverage.v1",
        "projection_publication_state.json": (
            "policyos.runtime.policy_design_case.projection_publication_state.v1"
        ),
        "run_cost_proportionality.json": "policyos.runtime.run_cost_proportionality.v1",
        "audit_verifier.json": "policyos.runtime.audit_verifier.v1",
    }
    for filename, schema_version in records.items():
        (quality_dir / filename).write_text(
            json.dumps(
                {
                    "schema_version": schema_version,
                    "status": "pass",
                    "authority_role": "runtime_reader",
                    "provenance_kind": "runtime_emitted",
                    "producer": f"fixture.{Path(filename).stem}",
                    "runtime_event_ref": f"event://w4d/{Path(filename).stem}",
                    "cas_ref": "sha256:" + "c" * 64,
                    "issues": [],
                }
            ),
            encoding="utf-8",
        )
    output = tmp_path / "can_i_closeout_w4_missing_i4.json"

    exit_code = check_can_i_closeout.main(
        [
            "--repo-root",
            str(Path.cwd()),
            "--bundle-dir",
            str(bundle),
            "--json-output",
            str(output),
            "--reader-integration",
        ]
    )
    payload = json.loads(output.read_text(encoding="utf-8"))

    assert exit_code == 2
    assert payload["schema_version"] == "policyos.runtime.can_i_closeout.integration.v1"
    assert payload["status"] == "incomplete"
    missing_modules = {
        row["module_id"]
        for row in payload["module_reader_results"]
        if row["status"] == "missing"
    }
    assert missing_modules >= {
        "i4_policy_design_case_graph",
        "portfolio_effective_support",
        "lifecycle_reissue",
        "projection_consumer_contract",
    }


def test_reader_skeleton_mode_preserves_shape_for_missing_bundle(tmp_path: Path) -> None:
    output = tmp_path / "missing_reader.json"

    exit_code = check_can_i_closeout.main(
        [
            "--repo-root",
            str(Path.cwd()),
            "--bundle-dir",
            str(tmp_path / "missing-bundle"),
            "--json-output",
            str(output),
            "--reader-skeleton",
        ]
    )
    payload = json.loads(output.read_text(encoding="utf-8"))

    assert exit_code == 3
    assert payload["schema_version"] == "policyos.runtime.can_i_closeout.reader_skeleton.v1"
    assert payload["status"] == "blocked"
    assert payload["can_closeout"] is False
    assert payload["compatibility_record"]["issues"][0]["code"] == "closeout_bundle_dir_missing"
