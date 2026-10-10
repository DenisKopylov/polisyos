from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from polisyos.core.security import tenant_scope
from polisyos.pdc import Layer2S2DesignSearchInput
from polisyos.runtime.quality.workspace.s2_design_search_operation import (
    S2_DESIGN_SEARCH_OPERATION_ID,
    execute_s2_design_search_operation,
)


def _proving_case_search_input() -> Layer2S2DesignSearchInput:
    policy_engine = Path(__file__).resolve().parents[5]
    proving_case = json.loads(
        (
            policy_engine / "architecture/policy_design_case/layer2_first_proving_case.json"
        ).read_text(encoding="utf-8")
    )
    manifest = json.loads(
        (
            policy_engine / "architecture/policy_design_case/layer2_s2_design_search_manifest.json"
        ).read_text(encoding="utf-8")
    )
    candidate_space = manifest["candidate_space"]
    return Layer2S2DesignSearchInput(
        case_id=str(proving_case["case_id"]),
        intent_ref="repo://architecture/policy_design_case/layer2_first_proving_case.json",
        grammar_ref="repo://src/polisyos/policy_grammar",
        instrument_families=tuple(candidate_space["instrument_families"]),
        parameter_space={
            str(dimension): tuple(values)
            for dimension, values in candidate_space["parameter_space"].items()
        },
        actor_ref="actor://ua/ministry-of-economy",
        domain="ukrainian_msme_credit",
        objective_refs=tuple(f"objective://{item}" for item in proving_case["constructs"]),
        construct_refs=tuple(f"construct://{item}" for item in proving_case["constructs"]),
        authority_profile_ref="authority_profile.shadow",
        requested_posture="shadow",
        generated_at=datetime(2026, 5, 30, tzinfo=UTC),
    )


def _produce_bound_run(runtime_api_env, *, run_id: str) -> None:
    context = runtime_api_env["app"].state.runtime_api_ctx
    with tenant_scope(
        None,
        tenant_id=runtime_api_env["tenant_a"],
        cell_id=runtime_api_env["cell_a"],
    ):
        execute_s2_design_search_operation(
            operation_id=S2_DESIGN_SEARCH_OPERATION_ID,
            search_input=_proving_case_search_input(),
            store=context.store,
            core_runs_root=context.core_runs_root,
            run_id=run_id,
        )
    context.run_index.refresh(force=True)


def test_case_inspection_rejects_a_sibling_runs_replay_tuple(runtime_api_env) -> None:
    client = runtime_api_env["client"]
    target_run_id = "R_case_inspection_primary"
    sibling_run_id = "R_case_inspection_sibling"
    _produce_bound_run(runtime_api_env, run_id=target_run_id)
    _produce_bound_run(runtime_api_env, run_id=sibling_run_id)
    target_url = f"/api/v1/runs/{target_run_id}/case-inspection"
    sibling_url = f"/api/v1/runs/{sibling_run_id}/case-inspection"

    target = client.get(target_url)
    sibling = client.get(sibling_url)

    assert target.status_code == 200, target.text
    assert sibling.status_code == 200, sibling.text
    target_pins = target.json()["replay_pins"]
    sibling_pins = sibling.json()["replay_pins"]
    assert target_pins["manifest_artifact_id"] != sibling_pins["manifest_artifact_id"]

    replay = client.get(target_url, params=sibling_pins)

    assert replay.status_code == 409, replay.text
    assert replay.json()["code"] == "case_inspection_replay_pin_mismatch"
