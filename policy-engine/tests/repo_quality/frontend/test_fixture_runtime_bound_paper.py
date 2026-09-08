"""Semantic fixture contract for dashboard run-paper routes."""

from __future__ import annotations

import importlib
import importlib.util
from pathlib import Path
from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURE_SERVER = (
    REPO_ROOT / "apps/runtime-dashboard/scripts/serve_fixture_runtime_api.py"
)
BOUND_ARTIFACT_KINDS = {
    "policyos.layer2_s2.design_record_v0",
    "policyos.layer2_s2.search_ledger",
    "policyos.pdc.run_bound_design_record_binding",
}


def _load_fixture_server() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "ds11_fixture_runtime_api", FIXTURE_SERVER
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_dashboard_fixture_publishes_one_content_bound_s2_run_paper(
    tmp_path: Path,
) -> None:
    """Require a real bound S2 record and preserve its authority abstention."""
    server = _load_fixture_server()
    builder = server._load_fixture_builder()
    env = builder(tmp_path, include_test_client=True)
    try:
        run_id = server._install_bound_run_paper_fixture(env)
        response = env["client"].get(f"/api/v1/runs/{run_id}/paper")
    finally:
        runtime_helper = importlib.import_module("_helpers.runtime_http")
        runtime_helper.close_runtime_api_env(env)

    assert response.status_code == 200, response.text
    packet = response.json()
    case = packet["case_record"]
    binding = case["design_record_binding"]
    assert run_id == "R_run_paper_bound_001"
    assert case["availability"] == "record_available_authority_abstaining"
    assert case["authority_projection"] == "abstained"
    assert binding["run_id"] == run_id == packet["run"]["run_id"]
    assert binding["tenant_id"] == env["tenant_a"] == packet["run"]["tenant_id"]
    assert binding["cell_id"] == env["cell_a"]
    linked_kinds = [
        link["artifact_ref"]["kind"] for link in packet["artifact_links"]
    ]
    assert {kind for kind in linked_kinds if kind in BOUND_ARTIFACT_KINDS} == (
        BOUND_ARTIFACT_KINDS
    )
    assert all(linked_kinds.count(kind) == 1 for kind in BOUND_ARTIFACT_KINDS)


def test_bound_run_paper_fixture_is_opt_in_and_preserves_default_run_population(
    tmp_path: Path,
) -> None:
    """Keep the S2 report witness out of unrelated Playwright and visual suites."""
    server = _load_fixture_server()
    runtime_helper = importlib.import_module("_helpers.runtime_http")
    default_env = server._build_dashboard_fixture_env(
        tmp_path / "default",
        include_run_paper_fixtures=False,
        include_bound_run_paper_fixture=False,
        include_test_client=True,
    )
    bound_env = server._build_dashboard_fixture_env(
        tmp_path / "bound",
        include_run_paper_fixtures=False,
        include_bound_run_paper_fixture=True,
        include_test_client=True,
    )
    try:
        default_runs = default_env["client"].get("/api/v1/runs?limit=100").json()[
            "runs"
        ]
        bound_runs = bound_env["client"].get("/api/v1/runs?limit=100").json()[
            "runs"
        ]
    finally:
        runtime_helper.close_runtime_api_env(default_env)
        runtime_helper.close_runtime_api_env(bound_env)

    bound_run_id = "R_run_paper_bound_001"
    assert "run_paper_bound_run_id" not in default_env
    assert all(row["run_id"] != bound_run_id for row in default_runs)
    assert bound_env["run_paper_bound_run_id"] == bound_run_id
    assert [row["run_id"] for row in bound_runs].count(bound_run_id) == 1
    assert len(bound_runs) == len(default_runs) + 1


def test_visual_run_paper_fixtures_bind_three_distinct_s2_records(
    tmp_path: Path,
) -> None:
    """Make each governed visual case reach the authority-abstaining arm."""
    server = _load_fixture_server()
    runtime_helper = importlib.import_module("_helpers.runtime_http")
    env = server._build_dashboard_fixture_env(
        tmp_path,
        include_run_paper_fixtures=True,
        include_bound_run_paper_fixture=False,
        include_test_client=True,
    )
    try:
        run_ids = [
            env["run_paper_bound_run_id"],
            env["run_paper_empty_run_id"],
            env["run_paper_growth_run_id"],
        ]
        responses = [
            env["client"].get(f"/api/v1/runs/{run_id}/paper")
            for run_id in run_ids
        ]
    finally:
        runtime_helper.close_runtime_api_env(env)

    assert all(response.status_code == 200 for response in responses), [
        response.text for response in responses
    ]
    packets = [response.json() for response in responses]
    cases = [packet["case_record"] for packet in packets]
    assert [packet["run"]["run_id"] for packet in packets] == run_ids
    assert all(
        case["availability"] == "record_available_authority_abstaining"
        for case in cases
    )
    assert all(case["authority_projection"] == "abstained" for case in cases)
    assert [case["design_record_binding"]["run_id"] for case in cases] == run_ids
    assert len(
        {
            case["design_record_binding"]["design_record_content_digest"]
            for case in cases
        }
    ) == 3
    for packet in packets:
        linked_kinds = [
            link["artifact_ref"]["kind"] for link in packet["artifact_links"]
        ]
        assert all(linked_kinds.count(kind) == 1 for kind in BOUND_ARTIFACT_KINDS)
    growth_kinds = [
        link["artifact_ref"]["kind"] for link in packets[2]["artifact_links"]
    ]
    assert growth_kinds.count("test.run_paper_growth_output") == 64
    assert len(packets[2]["artifact_links"]) == len(packets[1]["artifact_links"]) + 64
