# ruff: noqa: S101

from __future__ import annotations

import copy
import tomllib
from pathlib import Path
from typing import Any

from polisyos.runtime.quality.invariants import (
    DEFAULT_REGISTRY_RELATIVE_PATH,
    build_production_invariant_registry_report,
    validate_invariant_registry_payload,
)
from tools.quality.validation import check_production_invariant_registry

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_every_production_invariant_declares_implementation_ownership() -> None:
    report = build_production_invariant_registry_report(repo_root=REPO_ROOT)

    assert report["status"] == "pass", report["issues"]
    assert report["source"]["registry_path"] == DEFAULT_REGISTRY_RELATIVE_PATH.as_posix()
    assert report["summary"]["invariant_count"] >= 1
    assert report["summary"]["issue_count"] == 0


def test_production_invariant_registry_rejects_empty_or_wrong_shaped_rows() -> None:
    row = _valid_row()
    row["invariant_id"] = ""
    row["producer_owners"] = []
    row["dependencies"] = "not-a-list"

    result = validate_invariant_registry_payload({"invariants": [row]}, repo_root=REPO_ROOT)

    assert result.status == "fail"
    assert _issue_codes(result.as_dict()) >= {
        "invariant_field_invalid",
        "invariant_list_field_empty",
        "invariant_list_field_invalid",
    }


def test_registry_rejects_missing_final_owner() -> None:
    row = _valid_row()
    row.pop("final_owner")

    result = validate_invariant_registry_payload({"invariants": [row]}, repo_root=REPO_ROOT)

    assert result.status == "fail"
    assert "invariant_final_owner_missing" in _issue_codes(result.as_dict())


def test_registry_rejects_multi_owner_final_authority() -> None:
    row = _valid_row()
    row["final_owner"] = ["runtime.quality.closeout", "runtime.dashboard"]

    result = validate_invariant_registry_payload({"invariants": [row]}, repo_root=REPO_ROOT)

    assert result.status == "fail"
    assert "invariant_final_owner_count_invalid" in _issue_codes(result.as_dict())


def test_registry_rejects_missing_override_policy() -> None:
    row = _valid_row()
    row.pop("override_policy")

    result = validate_invariant_registry_payload({"invariants": [row]}, repo_root=REPO_ROOT)

    assert result.status == "fail"
    assert "invariant_override_policy_missing" in _issue_codes(result.as_dict())


def test_registry_rejects_missing_projection_policy() -> None:
    row = _valid_row()
    row.pop("dashboard_projection_policy")

    result = validate_invariant_registry_payload({"invariants": [row]}, repo_root=REPO_ROOT)

    assert result.status == "fail"
    assert "invariant_dashboard_projection_policy_missing" in _issue_codes(
        result.as_dict()
    )


def test_registry_rejects_missing_failure_code() -> None:
    row = _valid_row()
    row.pop("failure_code")

    result = validate_invariant_registry_payload({"invariants": [row]}, repo_root=REPO_ROOT)

    assert result.status == "fail"
    assert "invariant_failure_code_missing" in _issue_codes(result.as_dict())


def test_registry_rejects_unreferenced_minimum_closeout_gate_rows() -> None:
    row = _valid_row()
    row["minimum_closeout_gate"] = "not_a_minimum_closeout_gate"

    result = validate_invariant_registry_payload({"invariants": [row]}, repo_root=REPO_ROOT)

    assert result.status == "fail"
    assert "invariant_minimum_closeout_gate_unknown" in _issue_codes(result.as_dict())


def test_registry_rejects_missing_known_minimum_closeout_gate() -> None:
    payload = _actual_registry_payload()
    payload["invariants"] = [
        row
        for row in payload["invariants"]
        if row["minimum_closeout_gate"] != "closeout_matrix_dashboard_api_smoke"
    ]

    result = validate_invariant_registry_payload(payload, repo_root=REPO_ROOT)

    assert result.status == "fail"
    assert "invariant_minimum_closeout_gate_unregistered" in _issue_codes(
        result.as_dict()
    )


def test_registry_rejects_duplicate_minimum_closeout_gate_without_policy() -> None:
    payload = _actual_registry_payload()
    duplicate = copy.deepcopy(payload["invariants"][0])
    duplicate["invariant_id"] = "HDS-MCG-DUPLICATE"
    payload["invariants"].append(duplicate)

    result = validate_invariant_registry_payload(payload, repo_root=REPO_ROOT)

    assert result.status == "fail"
    assert "invariant_minimum_closeout_gate_duplicate" in _issue_codes(result.as_dict())


def test_registry_rejects_unknown_reader_and_enforcer_mappings() -> None:
    row = _valid_row()
    row["scorecard_gate_names"] = ["not_a_scorecard_gate"]
    row["readiness_check"] = "not_a_readiness_check"
    row["runtime_event_names"] = ["not_a_runtime_event"]

    result = validate_invariant_registry_payload({"invariants": [row]}, repo_root=REPO_ROOT)

    assert result.status == "fail"
    assert _issue_codes(result.as_dict()) >= {
        "invariant_scorecard_gate_unknown",
        "invariant_readiness_check_unknown",
        "invariant_runtime_event_unknown",
    }


def test_registry_cli_reports_diffs_and_fails_invalid_registry(tmp_path: Path) -> None:
    registry = tmp_path / "invariant_registry.toml"
    registry.write_text(
        "\n".join(
            [
                "[[invariants]]",
                'invariant_id = "HDS-MCG-999"',
                'minimum_closeout_gate = "not_a_minimum_closeout_gate"',
                'pql_id = "PQL-999"',
                'final_owner = "runtime.quality.closeout"',
                'producer_owners = ["runtime.nl_pipeline"]',
                'runtime_event_names = ["not_a_runtime_event"]',
                'required_artifact_kinds = ["quality_report"]',
                'required_ref_keys = ["quality_report_ref"]',
                'evidence_classes = ["authority_bearing"]',
                'allowed_provenance_kinds = ["runtime_emitted"]',
                'required_schema_contracts = ["runtime_quality.quality_report.v1"]',
                'scorecard_gate_names = ["not_a_scorecard_gate"]',
                'readiness_check = "not_a_readiness_check"',
                'approval_policy = "requires_verified_scorecard"',
                'override_policy = "not_overridable"',
                'non_overridable_blockers = ["authority_cas_missing"]',
                'dashboard_projection_policy = "projection_only"',
                'public_artifact_policy = "not_public_exportable"',
                'conflict_policy = "fail_closed"',
                'failure_code = "hds_unknown_gate"',
                'diagnostic_owner = "team-runtime"',
                "dependencies = []",
                'consumers = ["runtime.scorecard"]',
                (
                    'next_diagnostic_command = "uv run pytest '
                    'tests/unit/runtime/quality/test_scorecard.py -q"'
                ),
                (
                    'negative_tests = ["tests/unit/runtime/quality/test_scorecard.py::'
                    'test_runtime_quality_scorecard_fails_closed_for_serious_profiles_'
                    'missing_runtime_refs"]'
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    exit_code = check_production_invariant_registry.main(
        [
            "--repo-root",
            str(REPO_ROOT),
            "--registry",
            str(registry),
            "--output-format",
            "json",
        ]
    )

    assert exit_code == 1


def _valid_row() -> dict[str, Any]:
    return copy.deepcopy(
        {
            "invariant_id": "HDS-MCG-TEST",
            "minimum_closeout_gate": "serious_canary_runtime_refs",
            "pql_id": "PQL-001",
            "final_owner": "runtime.quality.closeout",
            "producer_owners": [
                "runtime.nl_pipeline",
                "lex.normative_applicability",
            ],
            "runtime_event_names": [
                "polisyos.runtime.evidence.normative_applicability_report.v1",
            ],
            "required_artifact_kinds": ["normative_applicability_report"],
            "required_ref_keys": ["normative_applicability_report_ref"],
            "evidence_classes": ["authority_bearing"],
            "allowed_provenance_kinds": ["runtime_emitted"],
            "required_schema_contracts": [
                "runtime_quality.normative_applicability_report.v1",
            ],
            "scorecard_gate_names": ["normative_evidence_present"],
            "readiness_check": "production_quality.runtime_required_refs",
            "approval_policy": "requires_verified_scorecard",
            "override_policy": "not_overridable",
            "non_overridable_blockers": ["authority_cas_missing"],
            "dashboard_projection_policy": "projection_only",
            "public_artifact_policy": "not_public_exportable",
            "conflict_policy": "fail_closed",
            "failure_code": "hds_runtime_refs_missing",
            "diagnostic_owner": "team-runtime",
            "dependencies": [],
            "consumers": ["runtime.scorecard"],
            "next_diagnostic_command": (
                "uv run pytest tests/unit/runtime/quality/test_scorecard.py -q"
            ),
            "negative_tests": [
                "tests/unit/runtime/quality/test_scorecard.py::test_runtime_quality_scorecard_fails_closed_for_serious_profiles_missing_runtime_refs",
            ],
        }
    )


def _actual_registry_payload() -> dict[str, Any]:
    with (REPO_ROOT / DEFAULT_REGISTRY_RELATIVE_PATH).open("rb") as handle:
        return tomllib.load(handle)


def _issue_codes(report: dict[str, Any]) -> set[str]:
    return {
        str(issue["code"])
        for issue in report.get("issues", [])
        if isinstance(issue, dict)
    }
