from __future__ import annotations

import argparse
import importlib
import json
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import uvicorn

if TYPE_CHECKING:
    from collections.abc import Callable


def _load_fixture_builder() -> Callable[..., dict[str, object]]:
    policy_engine_root = Path(__file__).resolve().parents[3]
    import_roots = [
        policy_engine_root / "src",
        policy_engine_root,
        policy_engine_root / "tests",
    ]
    for root in import_roots:
        root_str = str(root)
        if root_str not in sys.path:
            sys.path.insert(0, root_str)

    module = importlib.import_module("_helpers.runtime_http")
    return module.build_runtime_api_env


def _ensure_policy_engine_import_roots() -> None:
    policy_engine_root = Path(__file__).resolve().parents[3]
    for root in (policy_engine_root / "src", policy_engine_root, policy_engine_root / "tests"):
        root_str = str(root)
        if root_str not in sys.path:
            sys.path.insert(0, root_str)


def _assert_dashboard_fixture_clean(payload: object) -> None:
    _ensure_policy_engine_import_roots()
    from tools.ops_runners.runtime.quality_benchmark_authority import (
        assert_no_benchmark_contamination,
    )

    assert_no_benchmark_contamination(payload, surface="dashboard_fixture")


def _install_bound_run_paper_fixture(env: dict[str, object]) -> str:
    """Create one real S2 run whose terminal manifest can back the report page."""
    _ensure_policy_engine_import_roots()
    from polisyos.core.security import tenant_scope
    from polisyos.pdc import Layer2S2DesignSearchInput
    from polisyos.runtime.quality.workspace.s2_design_search_operation import (
        S2_DESIGN_SEARCH_OPERATION_ID,
        execute_s2_design_search_operation,
    )

    policy_engine_root = Path(__file__).resolve().parents[3]
    proving_case = json.loads(
        (
            policy_engine_root
            / "architecture/policy_design_case/layer2_first_proving_case.json"
        ).read_text(encoding="utf-8")
    )
    manifest = json.loads(
        (
            policy_engine_root
            / "architecture/policy_design_case/layer2_s2_design_search_manifest.json"
        ).read_text(encoding="utf-8")
    )
    candidate_space = manifest["candidate_space"]
    search_input = Layer2S2DesignSearchInput(
        case_id=str(proving_case["case_id"]),
        intent_ref=(
            "repo://architecture/policy_design_case/layer2_first_proving_case.json"
        ),
        grammar_ref="repo://src/polisyos/policy_grammar",
        instrument_families=tuple(candidate_space["instrument_families"]),
        parameter_space={
            str(dimension): tuple(values)
            for dimension, values in candidate_space["parameter_space"].items()
        },
        actor_ref="actor://ua/ministry-of-economy",
        domain="ukrainian_msme_credit",
        objective_refs=tuple(
            f"objective://{item}" for item in proving_case["constructs"]
        ),
        construct_refs=tuple(
            f"construct://{item}" for item in proving_case["constructs"]
        ),
        authority_profile_ref="authority_profile.shadow",
        requested_posture="shadow",
        generated_at=datetime(2026, 5, 30, tzinfo=UTC),
    )

    app = env["app"]
    container = app.state.runtime_container
    context = container.runtime_api_context
    run_id = "R_run_paper_bound_001"
    with tenant_scope(
        None,
        tenant_id=str(env["tenant_a"]),
        cell_id=str(env["cell_a"]),
    ):
        execute_s2_design_search_operation(
            operation_id=S2_DESIGN_SEARCH_OPERATION_ID,
            search_input=search_input,
            store=context.store,
            core_runs_root=context.core_runs_root,
            run_id=run_id,
        )
    context.run_index.refresh(force=True)
    return run_id


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Serve fixture-backed runtime API for frontend e2e."
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--metadata-file", default=None)
    parser.add_argument("--include-run-paper-fixtures", action="store_true")
    args = parser.parse_args()

    build_runtime_api_env = _load_fixture_builder()
    tmp_root = Path(tempfile.mkdtemp(prefix="runtime-dashboard-e2e-"))
    env = build_runtime_api_env(
        tmp_root,
        include_run_paper_fixtures=args.include_run_paper_fixtures,
        include_test_client=False,
    )
    env["run_paper_bound_run_id"] = _install_bound_run_paper_fixture(env)
    app = env["app"]

    if args.metadata_file:
        metadata_path = Path(args.metadata_file)
        metadata_path.parent.mkdir(parents=True, exist_ok=True)
        metadata = {
            key: value
            for key, value in env.items()
            if key not in {"app", "client", "cas_root"}
        }
        _assert_dashboard_fixture_clean(metadata)
        metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
