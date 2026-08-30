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
