"""CYC02 exact configured NCM bytes survive producer exit and fresh consumption."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest


def _child(mode: str, root: Path, handoff: dict[str, Any] | None = None) -> dict[str, Any]:
    product = Path(__file__).resolve().parents[3]
    environment = dict(os.environ)
    environment["PYTHONPATH"] = os.pathsep.join(
        (str(product / "src"), str(product), str(product / "tests"))
    )
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    for name in (
        "OMP_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "MKL_NUM_THREADS",
        "POLARS_MAX_THREADS",
    ):
        environment[name] = "1"
    command = [
        sys.executable,
        "-B",
        "-m",
        "tests._helpers.cyc02_fresh_configured_ncm",
        mode,
        str(root),
    ]
    logs = root / "child-output"
    logs.mkdir(exist_ok=True)
    stdout_path = logs / f"{mode}.stdout.txt"
    stderr_path = logs / f"{mode}.stderr.txt"
    (logs / f"{mode}.command.json").write_text(
        json.dumps({"argv": command, "state": "started"}, indent=2) + "\n"
    )
    # Direct files preserve partial output if the outer resource supervisor
    # terminates the process tree before subprocess.run can return.
    with stdout_path.open("w") as stdout, stderr_path.open("w") as stderr:
        completed = subprocess.run(
            command,
            cwd=product,
            env=environment,
            input=json.dumps(handoff) if handoff is not None else None,
            stdout=stdout,
            stderr=stderr,
            text=True,
            check=False,
        )
    captured_stdout = stdout_path.read_text()
    captured_stderr = stderr_path.read_text()
    (logs / f"{mode}.command.json").write_text(
        json.dumps({"argv": command, "returncode": completed.returncode}, indent=2) + "\n"
    )
    assert completed.returncode == 0, (
        f"{mode} child exited {completed.returncode}; full output: {logs}; "
        f"stderr tail:\n{captured_stderr[-6000:]}\nstdout tail:\n{captured_stdout[-3000:]}"
    )
    lines = [line for line in captured_stdout.splitlines() if line.strip()]
    assert lines
    return json.loads(lines[-1])


@pytest.mark.integration
def test_configured_procurement_n5_survives_exit_and_reaches_fresh_api_and_conditional_reader(
    tmp_path: Path,
) -> None:
    """A separate reader preserves useful numbers, exact views and all authority limits."""
    produced = _child("produce", tmp_path)
    consumed = _child("consume", tmp_path, produced)
    _assert_fresh_projection(produced, consumed)
    semantic = _child("semantic_controls", tmp_path, produced)
    _assert_semantic_controls(semantic)


def _assert_fresh_projection(produced: dict[str, Any], consumed: dict[str, Any]) -> None:
    """Check the selected public projection and conditional limits independently."""
    from polisyos.core.artifacts import ArtifactRef, artifact_ref_identity_key

    assert produced["producer_pid"] != consumed["consumer_pid"] != os.getpid()
    assert produced["witness"] == consumed["witness"]
    assert produced["producer_n8_status"] == "value_pending_n8"
    witness = consumed["witness"]
    assert witness["expected_effect"] == 0.5
    assert witness["absolute_error_bound"] < 1e-12
    assert {seed for seed, _ in witness["sample_effects"]} == {11, 12}
    value = consumed["conditional_value"]
    assert value["status"] == "value_conditional"
    assert value["evaluation_mode"] == "simulate_only"
    assert value["decision_grade"] == "low"
    assert value["value_ref"] == witness["result_ref"]["artifact_id"]
    assert value["value_receipt"] is value["method_selection_receipt"] is None
    assert set(witness["persisted_blockers"]).issubset(value["authority_blockers"])
    assert "simulation_only_k_sim_not_world_evidence" in value["authority_blockers"]
    projection = consumed["projection"]
    assert projection["publication_authority"] is False
    assert projection["authority_purpose"] == "candidate_observation_only"
    (observation,) = [
        item for item in projection["n5_observations"] if item["status"] == "joint_simulated"
    ]
    for outer, original in (
        ("simulation_result_ref", "result_ref"),
        ("n5_input_ref", "input_ref"),
        ("n4_source_ref", "n4_ref"),
        ("context_job_ref", "context_ref"),
    ):
        assert artifact_ref_identity_key(ArtifactRef.model_validate(observation[outer])) == (
            artifact_ref_identity_key(ArtifactRef.model_validate(witness[original]))
        )
    assert observation["currentness_status"] == "not_established"
    assert observation["result_body_status"] == "resolved"
    body = observation["result_body"]
    assert body["atom_ids"] == witness["atom_ids"]
    assert body["selected_outcomes"] == witness["selected_outcomes"]
    assert body["world_model_record_content_hash"] == witness["world_model_record_hash"]
    assert body["horizon"] == witness["horizon"]
    assert body["trajectories"] == [
        {
            "run_level": trajectory["run_level"],
            "atom_ids": trajectory["atom_ids"],
            "points": [
                {"step": point["step"], "outcomes": point["outcomes"], "effects": point["effect"]}
                for point in trajectory["points"]
            ],
        }
        for trajectory in witness["trajectories"]
    ]
    assert body["unit_provenance"] == "declared_candidate_model"
    assert body["outcome_units"] == {witness["outcome"]: witness["outcome_unit"]}
    assert artifact_ref_identity_key(ArtifactRef.model_validate(body["model_declaration_ref"])) == (
        artifact_ref_identity_key(ArtifactRef.model_validate(witness["model_declaration_ref"]))
    )
    assert body["publication_authority"] is False
    controls = consumed["controls"]
    assert controls["foreign_tenant"] == "refused"
    assert controls["restored"] == "resolved"
    assert controls["wrong_world"]["authority_blockers"] == ["joint_simulation_result_wmr_mismatch"]
    assert controls["corrupt_blob"]["authority_blockers"] == [
        "joint_simulation_result_integrity_invalid"
    ]
    assert controls["missing_selected_manifest"]["authority_blockers"] == [
        "joint_simulation_result_unavailable"
    ]
    assert all(
        controls[name]["status"] == "value_blocked" and controls[name]["value_ref"] is None
        for name in ("wrong_world", "corrupt_blob", "missing_selected_manifest")
    )


def _assert_semantic_controls(semantic: dict[str, Any]) -> None:
    """The retained candidate remains useful while divergent meanings refuse."""
    assert semantic["no_new_n5"] is True
    assert semantic["original_selected_result_unchanged"] is True
    assert semantic["original_request_selected_verifier"] == "accepted"
    for name in ("wrong_model", "wrong_baseline", "wrong_trajectory"):
        assert semantic[name] == "selected_plan_execution_binding_missing"
    assert semantic["independent_numeric_oracle_rejected_drift"] is True
    unknown = semantic["unknown_blocker"]
    assert unknown["status"] == "value_blocked"
    assert unknown["authority_blockers"] == ["n8_persisted_blocker_not_candidate_allowlisted"]
    assert unknown["value_ref"] is unknown["value_receipt"] is None
    empirical = semantic["empirical_no_treatment"]
    assert empirical["context_status"] == "refused"
    assert empirical["code"] == "eval_safety_simulation_input_unresolved"
    assert empirical["value_port_status"] == "not_run"
    assert semantic["empirical_owner_assignment_status"] == "owner_assignment_unresolved"
    assert semantic["empirical_treatment_gate"].startswith("not_reached:")
    assert empirical["value_receipt"] is None
    restored = semantic["original_conditional_restored"]
    assert restored["status"] == "value_conditional"
    assert restored["evaluation_mode"] == "simulate_only"
    assert restored["decision_grade"] == "low"
    assert restored["value_receipt"] is restored["method_selection_receipt"] is None
