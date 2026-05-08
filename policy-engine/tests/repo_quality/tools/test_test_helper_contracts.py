# ruff: noqa: S101

from __future__ import annotations

import importlib.util
import json
import sys
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
RATCHETS = REPO_ROOT / "architecture" / "tests" / "ratchets.toml"
BASELINE = (
    REPO_ROOT
    / "architecture"
    / "baselines"
    / "repository_best_in_class_last_mile"
    / "test_helper_topology.json"
)
REPORTER = REPO_ROOT / "tools" / "quality" / "testing" / "report_test_ratchets.py"


def _load_toml(path: Path) -> dict:
    return tomllib.loads(path.read_text(encoding="utf-8"))


def _load_reporter() -> object:
    spec = importlib.util.spec_from_file_location("report_test_ratchets", REPORTER)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_phase_5_5_helper_topology_contract_is_declared() -> None:
    ratchets = _load_toml(RATCHETS)

    contract = ratchets["test_helper_topology"]

    assert contract["status"] == "active_contract"
    assert contract["owner"] == "team-quality"
    assert contract["baseline"] == (
        "architecture/baselines/repository_best_in_class_last_mile/"
        "test_helper_topology.json"
    )
    assert contract["shared_helper_root"] == "tests/_helpers"
    assert contract["layer_local_conftest_glob"] == "tests/**/conftest.py"
    assert contract["shared_helper_allowed_imports"] == [
        "product_code",
        "standard_library",
        "standard_test_libraries",
    ]
    assert contract["shared_helper_forbidden_test_layers"] == [
        "tests/unit",
        "tests/integration",
        "tests/property",
        "tests/contract",
        "tests/repo_quality",
    ]
    assert contract["growth_policy"] == "ratchet_update_required"


def test_phase_5_5_helper_topology_baseline_matches_live_inventory() -> None:
    reporter = _load_reporter()
    ratchets = _load_toml(RATCHETS)
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))

    report = reporter._build_test_helper_topology_report(ratchets)
    summary = report["summary"]

    assert baseline["schema_version"] == 1
    assert baseline["owner"] == "team-quality"
    assert baseline["status"] == "active_baseline"
    assert summary["shared_helper_files"] == baseline["summary"]["shared_helper_files"]
    assert summary["layer_local_conftest_files"] == baseline["summary"][
        "layer_local_conftest_files"
    ]
    assert summary["duplicated_fixture_factories"] == baseline["summary"][
        "duplicated_fixture_factories"
    ]
    assert summary["unused_helpers"] == baseline["summary"]["unused_helpers"]
    assert summary["forbidden_reverse_imports"] == baseline["summary"][
        "forbidden_reverse_imports"
    ]
    assert report["status"] == "ok"


def test_phase_5_5_reporter_payload_exposes_helper_gate_status() -> None:
    reporter = _load_reporter()

    payload = reporter._build_payload(RATCHETS)
    helper_gate = payload["test_helper_topology"]

    assert payload["summary"]["test_helper_topology_status"] == "ok"
    assert helper_gate["status"] == "ok"
    assert helper_gate["summary"]["forbidden_reverse_imports"] == 0
    assert helper_gate["summary"]["duplicated_fixture_factories"] == len(
        helper_gate["registered_duplicate_fixture_factories"]
    )
    assert "unused_helpers" in helper_gate
    assert "forbidden_reverse_imports" in helper_gate
