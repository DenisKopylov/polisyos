# ruff: noqa: S101

from __future__ import annotations

import copy
import tomllib
from pathlib import Path

from polisyos.runtime.quality.formal_invariants import (
    FORMAL_INVARIANT_REGISTRY_RELATIVE_PATH,
    REQUIRED_CLOSEOUT_INVARIANT_IDS,
    build_formal_invariant_spec_report,
    model_check_formal_invariant_specs,
    validate_formal_invariant_specs_payload,
)

REPO_ROOT = Path(__file__).resolve().parents[4]


def _actual_payload() -> dict[str, object]:
    with (REPO_ROOT / FORMAL_INVARIANT_REGISTRY_RELATIVE_PATH).open("rb") as handle:
        return tomllib.load(handle)


def test_phase_29_4_closeout_invariants_are_model_checked() -> None:
    report = build_formal_invariant_spec_report(repo_root=REPO_ROOT)

    assert report["status"] == "pass", report["issues"]
    assert (
        report["source"]["registry_path"]
        == FORMAL_INVARIANT_REGISTRY_RELATIVE_PATH.as_posix()
    )
    assert report["summary"]["required_coverage_pct"] == 100.0
    assert set(report["required_closeout_invariants"]) == REQUIRED_CLOSEOUT_INVARIANT_IDS

    model_checks = report["model_checks"]
    assert model_checks["status"] == "pass", model_checks["checks"]
    assert {check["spec_id"] for check in model_checks["checks"]} >= {
        "authority_ordering",
        "phase_barriers",
        "same_input_closure",
        "cas_event_reconciliation",
        "terminal_readiness",
    }
    assert all(check["counterexamples"] == [] for check in model_checks["checks"])


def test_formal_invariant_registry_rejects_missing_required_closeout_spec() -> None:
    payload = _actual_payload()
    mutated = copy.deepcopy(payload)
    mutated["specs"] = [
        row for row in mutated["specs"] if row["spec_id"] != "terminal_readiness"
    ]

    validation = validate_formal_invariant_specs_payload(mutated, repo_root=REPO_ROOT)

    assert validation.status == "fail"
    assert "formal_invariant_required_spec_missing" in {
        issue.code for issue in validation.issues
    }


def test_substrate_critical_invariants_cannot_be_unit_test_only() -> None:
    payload = _actual_payload()
    mutated = copy.deepcopy(payload)
    mutated["specs"][0]["accepted_check_type"] = "unit_test_only"
    mutated["specs"][0]["model_property"] = None

    validation = validate_formal_invariant_specs_payload(mutated, repo_root=REPO_ROOT)

    assert validation.status == "fail"
    assert "formal_invariant_check_type_insufficient" in {
        issue.code for issue in validation.issues
    }


def test_model_checker_reports_unknown_model_property_as_counterexample() -> None:
    payload = _actual_payload()
    mutated = copy.deepcopy(payload)
    mutated["specs"][0]["model_property"] = "authority_ordering_all_roles_are_valid"

    result = model_check_formal_invariant_specs(mutated["specs"])

    assert result["status"] == "fail"
    assert result["checks"][0]["status"] == "fail"
    assert result["checks"][0]["counterexamples"] == [
        {"code": "formal_invariant_model_property_unknown"}
    ]
