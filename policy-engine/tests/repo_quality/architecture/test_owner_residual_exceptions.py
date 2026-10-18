"""Exercise the retained exception boundary without weakening its failure modes."""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest

from tools.quality.validation import repository_structure_phase0 as structure

PRODUCT = Path(__file__).resolve().parents[3]


def _common_residual_case() -> tuple[dict, dict]:
    tracked = structure._tracked_entries(structure._git_root(PRODUCT))
    inventory = structure.collect_inventory(PRODUCT, tracked_paths=tracked)
    exception = next(
        entry
        for entry in structure._load_structure_exceptions(PRODUCT, tracked)
        if entry["id"] == "loose-root-common-shared-utilities"
    )
    finding = next(
        item
        for item in structure.gate_loose_files(PRODUCT, inventory, tracked)
        if structure._finding_matches_exception(item, exception)
    )
    return finding, copy.deepcopy(exception)


def test_expired_exception_preserves_real_finding_and_refusal(tmp_path: Path) -> None:
    finding, exception = _common_residual_case()
    exception["sunset"] = "2026-01-02"
    result = structure._apply_structure_exceptions([finding], [exception])
    receipt = tmp_path / "expired-exception.json"
    receipt.write_text(json.dumps(result), encoding="utf-8")
    reopened = json.loads(receipt.read_text(encoding="utf-8"))
    assert finding in reopened, "expired exception suppressed the real Common finding"
    assert any(
        item.get("id") == exception["id"]
        and item["message"] == "Structure remediation exception is expired."
        for item in reopened
    ), "expiry did not produce its own refusal"


def test_absent_and_wrong_scope_exceptions_do_not_suppress_real_finding(tmp_path: Path) -> None:
    finding, exception = _common_residual_case()
    exception["sunset"] = "2099-01-01"
    assert structure._apply_structure_exceptions([finding], [exception]) == []
    exception["match"]["package"] = "scholar"
    results = {
        "absent": structure._apply_structure_exceptions([finding], []),
        "wrong_scope": structure._apply_structure_exceptions([finding], [exception]),
    }
    receipt = tmp_path / "scope-refusals.json"
    receipt.write_text(json.dumps(results), encoding="utf-8")
    reopened = json.loads(receipt.read_text(encoding="utf-8"))
    assert reopened["absent"] == [finding]
    assert finding in reopened["wrong_scope"]
    assert any(
        item.get("id") == exception["id"]
        and item["message"] == "Structure remediation exception matches no current gate finding."
        for item in reopened["wrong_scope"]
    ), "unmatched exception target did not produce a registry refusal"


def test_selected_gate_checks_exception_targets_against_all_gate_findings(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    exception = {
        "id": "cross-gate-live-target",
        "gate": "loose_files_gate",
        "owner": "team-core-runtime",
        "sunset": "2099-01-01",
        "reason": "The exception target is present in the complete gate set.",
        "match": {"package": "common"},
    }
    live_finding = {
        "gate": "loose_files_gate",
        "package": "common",
        "message": "Top-level package has too many root .py files.",
    }
    monkeypatch.setattr(structure, "_git_root", lambda _path: tmp_path)
    monkeypatch.setattr(structure, "_tracked_entries", lambda _root: set())
    monkeypatch.setattr(
        structure,
        "collect_inventory",
        lambda _root, *, tracked_paths=None: {},
    )
    monkeypatch.setattr(
        structure,
        "GATE_FUNCTIONS",
        {
            "empty_namespace": lambda _root, _inventory, _tracked: [],
            "loose_files": lambda _root, _inventory, _tracked: [live_finding],
        },
    )
    monkeypatch.setattr(
        structure,
        "_load_structure_exceptions",
        lambda _root, _tracked: [exception],
    )

    findings, inventory = structure._collect_gate_measurement(tmp_path, "empty_namespace")
    assert inventory == {}
    assert findings == [], "a live exception for another gate was misclassified as orphaned"

    exception["match"]["package"] = "scholar"
    findings, inventory = structure._collect_gate_measurement(tmp_path, "empty_namespace")
    assert inventory == {}
    assert len(findings) == 1
    assert findings[0]["gate"] == "structure_exception_registry"
    assert findings[0]["id"] == exception["id"]
    assert findings[0]["message"] == (
        "Structure remediation exception matches no current gate finding."
    )


@pytest.mark.parametrize(
    ("gate", "selector", "expected_local_messages"),
    [
        (
            "all",
            ["--package", "common"],
            ["common root finding", "common package-files finding"],
        ),
        (
            "all",
            ["--scope", "root"],
            ["common root finding", "scholar root finding"],
        ),
        (
            "all",
            ["--scope", "package-files"],
            ["common package-files finding", "scholar package-files finding"],
        ),
        ("empty_namespace", ["--scope", "root"], []),
    ],
)
def test_cli_keeps_global_registry_refusals_outside_local_projection(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    gate: str,
    selector: list[str],
    expected_local_messages: list[str],
) -> None:
    registry_payload = {
        "shared_name": [
            {"name": "global-bad", "allowed_in": ["common"]},
            {
                "name": "global-bad",
                "allowed_in": ["common"],
                "semantic_axis": "test-axis",
                "disambiguation": "test distinction",
                "owner": "team-core-runtime",
                "target_phase": "phase1c",
                "sunset": "2099-01-01",
            },
        ],
        "rename_backlog": [{"name": "legacy-name", "packages": ["common"]}],
    }
    exceptions = [
        {
            "id": "cannot-target-registry-error",
            "gate": "name_collision_gate",
            "owner": "team-core-runtime",
            "sunset": "2099-01-01",
            "reason": "An exception may target a current gate finding only.",
            "match": {"name": "global-bad"},
        }
    ]
    local_loose_findings = [
        {
            "gate": "loose_files_gate",
            "severity": "warning",
            "message": "common root finding",
            "package": "common",
            "root_py_count": 6,
            "non_allowed": ["src/polisyos/common/helper.py"],
        },
        {
            "gate": "loose_files_gate",
            "severity": "warning",
            "message": "scholar root finding",
            "package": "scholar",
            "root_py_count": 6,
            "non_allowed": ["src/polisyos/scholar/helper.py"],
        },
        {
            "gate": "loose_files_gate",
            "severity": "warning",
            "message": "common package-files finding",
            "package": "common",
            "top_level_entry_count": 251,
            "max_top_level_entries": 250,
        },
        {
            "gate": "loose_files_gate",
            "severity": "warning",
            "message": "scholar package-files finding",
            "package": "scholar",
            "top_level_entry_count": 251,
            "max_top_level_entries": 250,
        },
    ]
    inventory = {
        "pyproject": {"line_count": 0},
        "repeated_directory_names": [
            {
                "name": "unregistered-local-collision",
                "packages": [
                    {"package": "common"},
                    {"package": "scholar"},
                ],
            }
        ],
    }
    gate_functions = dict(structure.GATE_FUNCTIONS)
    gate_functions.update(
        {
            "empty_namespace": lambda _root, _inventory, _tracked: [],
            "loose_files": lambda _root, _inventory, _tracked: local_loose_findings,
            "pyproject_size": lambda _root, _inventory, _tracked: [],
            "cache_dir": lambda _root, _inventory, _tracked: [],
            "build_output": lambda _root, _inventory, _tracked: [],
        }
    )

    def load_toml(path: Path, _tracked: set[Path] | None = None) -> dict:
        if path.name == "name_registry.toml":
            return registry_payload
        return {}

    monkeypatch.setattr(structure, "_git_root", lambda _path: tmp_path)
    monkeypatch.setattr(structure, "_tracked_entries", lambda _root: set())
    monkeypatch.setattr(
        structure,
        "collect_inventory",
        lambda _root, *, tracked_paths=None: inventory,
    )
    monkeypatch.setattr(structure, "_load_toml", load_toml)
    monkeypatch.setattr(
        structure,
        "_load_structure_exceptions",
        lambda _root, _tracked: exceptions,
    )
    monkeypatch.setattr(structure, "GATE_FUNCTIONS", gate_functions)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "repository_structure_phase0.py",
            "--repo-root",
            str(tmp_path),
            "gate",
            "--gate",
            gate,
            "--json",
            *selector,
        ],
    )

    exit_code = structure.main()
    result = json.loads(capsys.readouterr().out)

    assert exit_code == 1, "global registry refusals must keep the fail-closed CLI red"
    assert result["status"] == "FAILED"
    assert result["complete_verdict"] is True
    assert result["finding_coverage"] == "complete"
    messages = [finding["message"] for finding in result["findings"]]
    expected_global_messages = [
        "Shared name registry entry is duplicated.",
        "Shared name registry entry is missing required Phase 1C metadata.",
        "Rename backlog entry is missing required Phase 1C metadata.",
        "Structure remediation exception matches no current gate finding.",
    ]
    assert sorted(messages) == sorted([*expected_global_messages, *expected_local_messages])
