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

    from polisyos.core.artifacts import ArtifactRef, FileSystemCAS
    from polisyos.pdc import Layer2S2DesignSearchInput


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


def _build_run_paper_search_input(
    *,
    fixture_role: str | None = None,
) -> Layer2S2DesignSearchInput:
    """Build one deterministic S2 input, distinct for each governed fixture role."""
    _ensure_policy_engine_import_roots()
    from polisyos.pdc import Layer2S2DesignSearchInput

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
    base_case_id = str(proving_case["case_id"])
    case_id = (
        f"{base_case_id}__dashboard_{fixture_role}"
        if fixture_role is not None
        else base_case_id
    )
    return Layer2S2DesignSearchInput(
        case_id=case_id,
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


def _persist_run_paper_fixture_binding(
    *,
    store: FileSystemCAS,
    run_id: str,
    tenant_id: str,
    cell_id: str,
    fixture_role: str,
) -> tuple[ArtifactRef, ArtifactRef, ArtifactRef]:
    """Persist the verified S2 chain attached to one existing fixture run."""
    _ensure_policy_engine_import_roots()
    from polisyos.pdc import persist_s2_design_search_run, run_s2_shadow_design_loop

    search_run = run_s2_shadow_design_loop(
        _build_run_paper_search_input(fixture_role=fixture_role)
    )
    persisted = persist_s2_design_search_run(
        search_run,
        store=store,
        run_id=run_id,
        tenant_id=tenant_id,
        cell_id=cell_id,
    )
    return (
        persisted.design_record_ref,
        persisted.search_ledger_ref,
        persisted.binding_ref,
    )


def _install_bound_run_paper_fixture(env: dict[str, object]) -> str:
    """Create one real S2 run whose terminal manifest can back the report page."""
    _ensure_policy_engine_import_roots()
    from polisyos.core.security import tenant_scope
    from polisyos.runtime.quality.workspace.s2_design_search_operation import (
        S2_DESIGN_SEARCH_OPERATION_ID,
        execute_s2_design_search_operation,
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
            search_input=_build_run_paper_search_input(),
            store=context.store,
            core_runs_root=context.core_runs_root,
            run_id=run_id,
        )
    context.run_index.refresh(force=True)
    return run_id


def _build_dashboard_fixture_env(
    tmp_root: Path,
    *,
    include_run_paper_fixtures: bool,
    include_bound_run_paper_fixture: bool,
    include_test_client: bool,
) -> dict[str, object]:
    """Build dashboard fixtures with producer-bound paper runs when requested."""
    build_runtime_api_env = _load_fixture_builder()
    env = build_runtime_api_env(
        tmp_root,
        include_run_paper_fixtures=include_run_paper_fixtures,
        run_paper_binding_factory=(
            _persist_run_paper_fixture_binding
            if include_run_paper_fixtures
            else None
        ),
        include_test_client=include_test_client,
    )
    if include_bound_run_paper_fixture:
        env["run_paper_bound_run_id"] = _install_bound_run_paper_fixture(env)
    return env


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Serve fixture-backed runtime API for frontend e2e."
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--metadata-file", default=None)
    parser.add_argument("--include-run-paper-fixtures", action="store_true")
    parser.add_argument("--include-bound-run-paper-fixture", action="store_true")
    args = parser.parse_args()

    tmp_root = Path(tempfile.mkdtemp(prefix="runtime-dashboard-e2e-"))
    env = _build_dashboard_fixture_env(
        tmp_root,
        include_run_paper_fixtures=args.include_run_paper_fixtures,
        include_bound_run_paper_fixture=args.include_bound_run_paper_fixture,
        include_test_client=False,
    )
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
