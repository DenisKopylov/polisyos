"""Run one named correspondence evidence gate and retain its actual exit code.

Usage: .venv/bin/python docs/superpowers/journals/correspondence/runner.py GATE
This is a lane evidence recorder, not a runtime acceptance authority. Native
owners and tests remain unchanged. Every test file and function is named below.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
BASE = "cc74d65813d7bb1259a0f82f6c3cc8b131661a97"
BRANCH = "codex/correspondence-consumers"
RAW = HERE / "raw"
LIVE = RAW / "fresh-defensive-2026-09-11"

LEGAL_RUNTIME = "tests/unit/runtime/quality/test_intervention_substrate.py"
LEGAL_FOUNDRY = "tests/unit/foundry/validation/test_legal_correspondence.py"
CAUSAL_FRAME = "tests/unit/runtime/quality/test_grounding_calibration.py"
CAUSAL_BIND = "tests/unit/runtime/quality/test_grounding_bind.py"
CAUSAL_SOURCE = "tests/unit/runtime/quality/test_production_grounding_calibration.py"
GY_J = "tests/unit/runtime/quality/workspace/test_production_case_admission.py"

TEST_NODES = {
    "legal-tests": [
        f"{LEGAL_RUNTIME}::test_phase5_real_unrelated_law_target_cannot_authorize_a_knob",
        f"{LEGAL_RUNTIME}::test_subject_comparison_removal_turns_real_transposition_gate_red",
        f"{LEGAL_RUNTIME}::test_subject_forwarding_removal_turns_real_positive_gate_red",
        f"{LEGAL_RUNTIME}::test_missing_legal_subject_is_ambiguous_before_numeric_units",
        f"{LEGAL_RUNTIME}::test_frozen_subject_producer_is_invariant_to_the_proposed_law_mapping",
        f"{LEGAL_RUNTIME}::test_synthetic_recognition_does_not_authorize_credal_or_atom_consumers",
        f"{LEGAL_RUNTIME}::test_current_law_resolution_rejects_rehashed_recognition_splices",
        f"{LEGAL_FOUNDRY}::test_persisted_source_distinguishes_correspondence_and_transposition",
        f"{LEGAL_FOUNDRY}::test_source_bindings_and_time_are_decisive",
        f"{LEGAL_FOUNDRY}::test_source_marker_or_unresolved_authority_ref_cannot_grant_governed_authority",
        f"{LEGAL_FOUNDRY}::test_persisted_comparison_must_be_recomputed_from_the_actual_source",
        f"{LEGAL_FOUNDRY}::test_subject_scope_and_unique_membership_are_decisive",
        f"{LEGAL_FOUNDRY}::test_common_source_ancestry_is_circular_even_with_different_producer_labels",
    ],
    "causal-tests": [
        f"{CAUSAL_FRAME}::test_frame_tier_is_blind_to_binding_outcomes_and_shared_sources_cluster",
        f"{CAUSAL_FRAME}::test_frame_scope_stales_on_each_epoch_component_and_never_grants_synthetic_authority",
        f"{CAUSAL_FRAME}::test_source_clusters_follow_transitive_support_not_row_identity",
        f"{CAUSAL_FRAME}::test_refusal_suite_predeclared_complete_and_refusal_reason_is_structural",
        f"{CAUSAL_FRAME}::test_suite_refuses_execution_before_declaration_and_keeps_novel_input_ambiguous",
        f"{CAUSAL_FRAME}::test_refusal_report_rejects_fallback_when_binder_structural_guard_is_removed",
        f"{CAUSAL_FRAME}::test_frame_intakes_recompute_mutable_nested_content[declaration]",
        f"{CAUSAL_FRAME}::test_frame_intakes_recompute_mutable_nested_content[execution]",
        f"{CAUSAL_BIND}::test_cold_start_exact_freezes_bind",
        f"{CAUSAL_BIND}::test_fabricated_caller_calibration_is_rejected_and_freezes_bind",
        f"{CAUSAL_BIND}::test_spoofed_caller_calibration_still_freezes_bind",
        f"{CAUSAL_SOURCE}::test_source_matches_persist_and_replay_without_becoming_relation_calibration",
        f"{CAUSAL_SOURCE}::test_valid_new_cas_cannot_launder_candidate_or_publication_data[publication]",
        f"{CAUSAL_SOURCE}::test_valid_new_cas_cannot_launder_candidate_or_publication_data[grade]",
        f"{CAUSAL_SOURCE}::test_missing_source_and_exact_context_are_persisted_refusals",
    ],
    "gy-j-tests": [
        f"{GY_J}::test_production_attempts_original_requirements_through_s1_before_terminal",
        f"{GY_J}::test_production_refusal_does_not_fabricate_fixture_recall",
        f"{GY_J}::test_production_never_calls_fixture_benchmark_or_estimate",
        f"{GY_J}::test_production_receipt_consumer_recomputes_substance",
        f"{GY_J}::test_production_current_source_change_revokes_receipt",
        f"{GY_J}::test_original_source_markers_do_not_admit_changed_demand",
        f"{GY_J}::test_production_p28_witness_rejects_retained_decisions_without_actual_s1",
    ],
}

SOURCE_FILES = [
    "src/polisyos/foundry/validation/legal_correspondence.py",
    "src/polisyos/runtime/quality/intervention_substrate.py",
    "src/polisyos/runtime/quality/credal_reference.py",
    "src/polisyos/runtime/quality/grounding_calibration.py",
    "src/polisyos/runtime/quality/grounding_bind.py",
    "src/polisyos/runtime/quality/production_grounding_calibration.py",
    "src/polisyos/runtime/quality/acquisition_planner.py",
    "src/polisyos/runtime/http/services/control/workspace_loop_transition.py",
    "src/polisyos/runtime/quality/workspace/loop.py",
    "src/polisyos/runtime/quality/graded_outcomes.py",
    "tools/quality/validation/check_layer3_gy_loop_artifacts.py",
    "tools/quality/validation/check_grounding_refusal_sensitivity.py",
    "tools/quality/validation/check_layer3_gy_intervention_substrate_contract.py",
]


def _emit(value: object) -> None:
    sys.stdout.write(json.dumps(value, indent=2) + "\n")
    sys.stdout.flush()


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise ValueError(reason)


def _digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _native_nodes(gate: str) -> list[str]:
    nodes = TEST_NODES[gate]
    for node in nodes:
        file, function = node.split("::")
        tree = ast.parse((ROOT / file).read_text())
        names = {
            item.name
            for item in ast.walk(tree)
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        if function.split("[")[0] not in names:
            raise ValueError(f"native_definition_not_found:{node}")
    return nodes


def _declare_live() -> int:
    """Declare a fresh defensive frame through existing owners before any decisions."""
    from polisyos.core import artifacts
    from polisyos.runtime.quality.data_state_substrate import (
        build_production_data_state_world_model_record,
    )
    from polisyos.runtime.quality.grounding_calibration import (
        GroundingEpochScope,
        build_owner_frame_inputs,
        build_refusal_reference_scaffold,
        declare_calibration_frame,
        declare_refusal_suite,
        difficulty_tier,
        produce_grounding_proof_world_input,
        source_clusters,
    )
    from polisyos.runtime.quality.intervention_substrate import (
        _COMPOSED_WMR_REQUIRED_SUBSTRATE_FAMILIES,
    )

    _require(not (LIVE / "frame.json").exists(), "fresh_frame_already_declared")
    cas = LIVE / "world-cas"
    result = build_production_data_state_world_model_record(
        artifacts.FileSystemCAS(cas),
        repo_root=ROOT,
        workspace_dir=LIVE / "world-workspace",
        agent_limit=16,
        required_substrate_families=_COMPOSED_WMR_REQUIRED_SUBSTRATE_FAMILIES,
    )
    world, ref = result.world_model.record, result.world_model.record_ref
    proof = produce_grounding_proof_world_input(
        ROOT,
        world_cas=cas,
        world_ref=str(ref.artifact_id),
    )
    inputs, sources = build_owner_frame_inputs(ROOT, world, domain=world.policy_domain)
    reference = build_refusal_reference_scaffold(ROOT, world)
    declared = json.loads((HERE / "frame-manifest.json").read_text())["causal"]
    selected = tuple(declared["selected_stratum"])
    tiers = {row.input_id: difficulty_tier(row) for row in inputs}
    # This lane retained a specific held-input cell, before measuring outcomes.
    # Fail on changed input difficulty instead of selecting another successful cell.
    _require(
        bool(inputs) and set(tiers.values()) == {"cross_modal"},
        "held_input_difficulty_changed_redeclaration_required",
    )
    now = datetime.now(UTC)
    epoch = {**declared["epoch_scope"], "reference_epoch": reference.reference_epoch}
    frame = declare_calibration_frame(
        inputs,
        source_refs=sources,
        epoch_scope=GroundingEpochScope(**epoch),
        selected_stratum=selected,
        declared_at=now,
    )
    suite = declare_refusal_suite(frame, reference, declared_at=now)
    LIVE.mkdir(parents=True, exist_ok=True)
    for name, artifact in (("frame", frame), ("suite", suite), ("proof-input", proof)):
        (LIVE / f"{name}.json").write_text(artifact.model_dump_json(indent=2) + "\n")
    context = {
        "declared_at": now.isoformat(),
        "stage": "declared_not_executed",
        "world_cas": str(cas.relative_to(ROOT)),
        "world_ref": str(ref.artifact_id),
        "world_content_hash": world.content_hash,
        "world_created_at": str(world.created_at),
        "epoch_scope": epoch,
        "previous_epoch_scope": declared["epoch_scope"],
        "selected_stratum": list(frame.selected_stratum),
        "input_only_tiers": tiers,
        "complete_input_ids": [row.input_id for row in inputs],
        "complete_mismatch_ids": [case.case_id for case in suite.mismatches],
        "ambiguous_inputs": list(suite.ambiguous_inputs),
        "source_clusters": len(source_clusters(inputs)),
        "calibration_denominator_ids": [],
        "correctness_bound": None,
        "adjudication_budget_spent": False,
        "files": {
            str((LIVE / f"{name}.json").relative_to(ROOT)): _digest(LIVE / f"{name}.json")
            for name in ("frame", "suite", "proof-input")
        },
    }
    (LIVE / "context.json").write_text(json.dumps(context, indent=2) + "\n")
    _emit(context)
    return 0


def _live_command(gate: str, python: str) -> list[str]:
    context = json.loads((LIVE / "context.json").read_text())
    manifest = json.loads((HERE / "frame-manifest.json").read_text())
    _require(
        manifest.get("fresh_defensive_redeclaration", {}).get("files") == context["files"],
        "fresh_frame_not_bound_in_lane_manifest",
    )
    committed = subprocess.check_output(
        [
            "/usr/bin/git",
            "show",
            "HEAD:policy-engine/docs/superpowers/journals/correspondence/frame-manifest.json",
        ],
        cwd=ROOT,
        text=True,
    )
    _require(json.loads(committed) == manifest, "fresh_manifest_not_committed")
    for path, digest in context["files"].items():
        _require(_digest(ROOT / path) == digest, f"fresh_declaration_drift:{path}")
    report = LIVE / "report.json"
    if gate == "causal-live-drift":
        corrupt = json.loads(report.read_text())
        corrupt["binder_refused"] += 1
        report = LIVE / "corrupt-report.json"
        report.write_text(json.dumps(corrupt, indent=2) + "\n")
    return [
        python,
        "-m",
        "tools.quality.validation.check_grounding_refusal_sensitivity",
        "--write" if gate == "causal-live-write" else "--check",
        "--repo-root",
        ".",
        "--world-cas",
        context["world_cas"],
        "--world-ref",
        context["world_ref"],
        "--declarations",
        str(LIVE),
        "--report",
        str(report),
    ]


def _json_pointer_differences(left: object, right: object, path: str = "") -> list[str]:
    """Walk both entire JSON values and report differing pointers without copying payloads."""
    if type(left) is not type(right):
        return [path or "/"]
    if isinstance(left, dict) and isinstance(right, dict):
        differences = []
        for key in sorted(left.keys() | right.keys()):
            pointer = path + "/" + str(key).replace("~", "~0").replace("/", "~1")
            if key not in left or key not in right:
                differences.append(pointer)
            else:
                differences.extend(_json_pointer_differences(left[key], right[key], pointer))
        return differences
    if isinstance(left, list) and isinstance(right, list):
        if len(left) != len(right):
            return [path or "/"]
        return [
            pointer
            for index, (a, b) in enumerate(zip(left, right, strict=True))
            for pointer in _json_pointer_differences(a, b, path + "/" + str(index))
        ]
    return [] if left == right else [path or "/"]


def _legal_fresh_drift() -> int:
    """Recompute a fresh expected artifact before crediting a corrupted-artifact refusal."""
    from unittest.mock import patch

    from tools.quality.validation import check_layer3_gy_intervention_substrate_contract as owner

    path = ROOT / owner.OUTPUT_PATH
    fresh_path = RAW / "legal-fresh-expected.json"
    fresh = owner.build_live_payload(ROOT)
    fresh_path.write_text(json.dumps(fresh, indent=2) + "\n")
    original = Path.read_text
    _emit(
        {
            "stage": "fresh_produced",
            "canonical_path": owner.OUTPUT_PATH,
            "canonical_sha256": _digest(path),
            "fresh_path": str(fresh_path.relative_to(ROOT)),
            "fresh_sha256": _digest(fresh_path),
            "complete_two_JSON_difference_pointers": _json_pointer_differences(
                json.loads(original(path)), fresh
            ),
        }
    )

    def read_fresh(self: Path, *args: object, **kwargs: object) -> str:
        if self.resolve() == path.resolve():
            return original(fresh_path)
        return original(self, *args, **kwargs)

    # The builder stays untouched: validate executes the actual producer again.
    with patch.object(Path, "read_text", read_fresh):
        baseline = owner.validate(ROOT)
    _emit({"stage": "fresh_expected_independent_recomputation", "report": baseline})
    if baseline["status"] != "pass":
        _emit({"corruption_sensitivity": "not_established_without_green_control"})
        return 2
    corrupt = json.loads(original(fresh_path))
    corrupt["behavior_report"]["coverage"]["law_trace"]["traced"] += 1
    corrupt_path = RAW / "legal-corrupt-expected.json"
    corrupt_path.write_text(json.dumps(corrupt, indent=2) + "\n")

    def read_corrupt(self: Path, *args: object, **kwargs: object) -> str:
        if self.resolve() == path.resolve():
            return original(corrupt_path)
        return original(self, *args, **kwargs)

    with patch.object(Path, "read_text", read_corrupt):
        report = owner.validate(ROOT)
    _emit(
        {
            "stage": "corrupt_expected_independent_recomputation",
            "report": report,
            "corrupt_sha256": _digest(corrupt_path),
            "canonical_sha256_after": _digest(path),
        }
    )
    return 1 if report["status"] == "fail" else 0


def _openapi_probe() -> int:
    """Observe the native isolated output probe without altering its source-copy boundary."""
    import shutil
    from unittest.mock import patch

    from tools.devx.architecture import guardrails as owner

    family = next(
        row
        for row in owner._parse_generated_artifacts(owner.DEFAULT_GENERATED_MANIFEST)
        if row.family_id == "runtime-openapi-snapshot"
    )
    candidate = RAW / (
        "openapi-candidate-" + datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ") + ".json"
    )
    original_run = subprocess.run

    def observe_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        result = original_run(*args, **kwargs)  # Native owner's unchanged argv.
        command = args[0] if args else kwargs.get("args", ())
        if (
            isinstance(command, (list, tuple))
            and result.returncode == 0
            and "tools/ops_runners/runtime/export_runtime_openapi.py" in command
        ):
            emitted = Path(command[command.index("--output") + 1])
            shutil.copy2(emitted, candidate)
        return result

    try:
        # Keep the native temporary directory, source copier, environment and argv.
        # Observe only after the actual generator exits, before native cleanup.
        with patch.object(owner.subprocess, "run", observe_run):
            violations = owner._measure_required_generated_artifacts(
                [family],
                expected_root=ROOT,
                violations=[],
            )
    except owner.GeneratedArtifactCheckUnrunError as error:
        _emit({"status": "UNRUN", "diagnostic": str(error)})
        return 2
    if not candidate.exists():
        _emit({"status": "UNRUN", "diagnostic": "native_generator_candidate_not_captured"})
        return 2
    expected = ROOT / "schemas/runtime_api_v1.openapi.json"
    _emit(
        {
            "complete_verdict": [str(item) for item in violations],
            "expected_path": str(expected.relative_to(ROOT)),
            "expected_sha256": _digest(expected),
            "candidate_path": str(candidate.relative_to(ROOT)),
            "candidate_sha256": _digest(candidate),
            "complete_two_JSON_difference_pointers": _json_pointer_differences(
                json.loads(expected.read_text()), json.loads(candidate.read_text())
            ),
        }
    )
    return 1 if violations else 0


def _operation(name: str) -> int:
    """Execute a single removal control or source/predicate inspection."""
    if name == "live-declare":
        return _declare_live()
    if name == "solver-witness":
        from importlib.metadata import version

        from ortools.sat.python import cp_model

        model = cp_model.CpModel()
        witness = model.new_bool_var("correspondence_station_witness")
        model.add(witness == 1)
        solver = cp_model.CpSolver()
        status = solver.solve(model)
        _require(
            status == cp_model.OPTIMAL and solver.value(witness) == 1,
            "station_solver_not_established",
        )
        _emit(
            {
                "solver_status": solver.status_name(status),
                "witness": solver.value(witness),
                "packages": {
                    name: version(name)
                    for name in (
                        "ortools",
                        "numpy",
                        "pandas",
                        "protobuf",
                        "absl-py",
                        "immutabledict",
                        "typing-extensions",
                        "pytest",
                        "pydantic",
                        "jaxlib",
                    )
                },
            }
        )
        return 0
    if name == "legal-owner-drift":
        return _legal_fresh_drift()
    if name == "openapi-probe":
        return _openapi_probe()
    if name in {"legal-red", "causal-red"}:
        import pytest

        if name == "legal-red":
            from polisyos.foundry.validation import legal_correspondence

            legal_correspondence._same_subject = lambda _lever, _norm: True
            node = f"{LEGAL_RUNTIME}::test_phase5_real_unrelated_law_target_cannot_authorize_a_knob"
        else:
            from polisyos.runtime.quality import grounding_bind

            grounding_bind._has_selected_critical_veto = lambda _certificate: False
            node = (
                f"{CAUSAL_FRAME}::"
                "test_refusal_suite_predeclared_complete_and_refusal_reason_is_structural"
            )
        _emit({"removed_property": name, "unchanged_test": node})
        return int(pytest.main(["-q", "-o", "addopts=", node]))
    if name == "gy-j-population":
        relative = "architecture/policy_design_case/layer3_gy_graded_outcome_routing_report_v2.json"
        report = json.loads((ROOT / relative).read_text())
        population = report["population"]
        groups = [
            report[key]
            for key in ("graded_outcomes", "honest_non_value_outcomes", "unmeasurable_outcomes")
        ]
        members = population["members"]
        positions = [item["population_position"] for group in groups for item in group]
        _require(sorted(positions) == list(range(len(members))), "population_partition_drift")
        _require(population["member_count"] == len(members), "population_count_drift")
        _require(
            population["definition"] == "canonical_producer_production_observations",
            "population_definition_drift",
        )
        _require(population["period"] == "report_generation", "population_period_drift")
        rate = None if groups[2] or not members else round(len(groups[0]) / len(members), 4)
        _require(report["summary"]["useful_design_rate"] == rate, "population_rate_drift")
        _emit(
            {
                "finding": "CC-J2",
                "evidence_kind": "persisted_report_arithmetic_not_new_live_run",
                "source": relative,
                "source_sha256": _digest(ROOT / relative),
                "complete_denominator": (
                    "one JSON file: /population/members and all three partitions"
                ),
                "population": population,
                "graded_count": len(groups[0]),
                "non_value_count": len(groups[1]),
                "unmeasurable_count": len(groups[2]),
                "recomputed_rate": rate,
                "admission_states": [row.get("admission_state") for row in groups[1]],
            }
        )
        return 0
    if name == "source-audit":
        findings = []
        terms = (
            "correspondence",
            "production_case",
            "graded",
            "calibration",
            "refusal",
            "capture_skg",
            "iter_l6_edges",
            "same_subject",
        )
        for relative in SOURCE_FILES:
            path = ROOT / relative
            tree = ast.parse(path.read_text())
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and any(
                    term in node.name.lower() for term in terms
                ):
                    findings.append(
                        {
                            "path": relative,
                            "definition": node.name,
                            "line": node.lineno,
                            "calls": [
                                {"line": call.lineno, "expression": ast.unparse(call.func)}
                                for call in ast.walk(node)
                                if isinstance(call, ast.Call)
                            ],
                        }
                    )
        _emit(
            {
                "kind": "AST_navigation_not_semantic_availability_verdict",
                "complete_file_denominator": SOURCE_FILES,
                "definitions": findings,
            }
        )
        return 0
    raise ValueError(f"unknown_operation:{name}")


def _command(gate: str) -> list[str]:
    python = str(ROOT / ".venv/bin/python")
    if gate in TEST_NODES:
        return [
            python,
            "-m",
            "pytest",
            "-q",
            "-o",
            "addopts=",
            f"--junitxml={RAW / (gate + '.xml')}",
            *_native_nodes(gate),
        ]
    if gate in {
        "legal-red",
        "causal-red",
        "gy-j-population",
        "source-audit",
        "live-declare",
        "solver-witness",
        "legal-owner-drift",
        "openapi-probe",
    }:
        return [python, str(Path(__file__).resolve()), "--operation", gate]
    if gate in {"causal-live-write", "causal-live-check", "causal-live-drift"}:
        return _live_command(gate, python)
    if gate == "legal-owner":
        return [
            python,
            "-m",
            "tools.quality.validation.check_layer3_gy_intervention_substrate_contract",
            "--repo-root",
            ".",
            "--check",
            "--output-format",
            "json",
        ]
    if gate == "guardrails":
        return [python, "-m", "tools.cli", "architecture", "guardrails", "check"]
    if gate == "ruff":
        return [python, "-m", "ruff", "check", str(Path(__file__).relative_to(ROOT))]
    raise ValueError(f"unknown_gate:{gate}")


def main() -> int:
    """Record one invocation, preserving failure/UNRUN codes rather than laundering them."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("gate", nargs="?")
    parser.add_argument("--operation")
    parser.add_argument("--timeout", type=float, default=900)
    args = parser.parse_args()
    if args.operation:
        return _operation(args.operation)
    if not args.gate:
        parser.error("name one gate")
    branch = subprocess.check_output(
        ["/usr/bin/git", "symbolic-ref", "--short", "HEAD"], cwd=ROOT, text=True
    ).strip()
    if branch != BRANCH:
        raise RuntimeError(f"unexpected_branch:{branch}")
    manifest = json.loads((HERE / "frame-manifest.json").read_text())
    if datetime.fromisoformat(manifest["declared_at"]) >= datetime.now(UTC):
        raise RuntimeError("frame_not_declared_before_execution")
    for path, digest in manifest["source_files"].items():
        if _digest(ROOT / path) != digest:
            raise RuntimeError(f"declared_source_drift:{path}")
    RAW.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    receipt = RAW / f"{stamp}-{args.gate}.json"
    command = _command(args.gate)
    environment = dict(os.environ)
    environment["PATH"] = str(ROOT / ".venv/bin") + os.pathsep + environment.get("PATH", "")
    environment["PYTHONPATH"] = os.pathsep.join((str(ROOT / "src"), str(ROOT)))
    frozen = {
        "head": subprocess.check_output(
            ["/usr/bin/git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "runner_sha256": _digest(Path(__file__)),
        "frame_sha256": _digest(HERE / "frame-manifest.json"),
        "source_files": {path: _digest(ROOT / path) for path in SOURCE_FILES},
        "test_files": {
            path: _digest(ROOT / path)
            for path in sorted(
                {node.split("::")[0] for nodes in TEST_NODES.values() for node in nodes}
            )
        },
    }
    started = time.monotonic()
    try:
        result = subprocess.run(  # noqa: S603 -- fixed local gate argv, shell=False
            command,
            cwd=ROOT,
            env=environment,
            text=True,
            capture_output=True,
            timeout=args.timeout,
            check=False,
        )
        code, stdout, stderr = result.returncode, result.stdout, result.stderr
        timed_out = False
    except subprocess.TimeoutExpired as exc:
        code, timed_out = 2, True
        stdout = exc.stdout or b""
        stderr = exc.stderr or b""
        stdout = stdout.decode(errors="replace") if isinstance(stdout, bytes) else stdout
        stderr = stderr.decode(errors="replace") if isinstance(stderr, bytes) else stderr
    record = {
        "gate": args.gate,
        "argv": command,
        "cwd": str(ROOT),
        "branch": branch,
        **frozen,
        "lane_merge_base": BASE,
        "started_at": stamp,
        "elapsed_seconds": time.monotonic() - started,
        "timeout_seconds": args.timeout,
        "timed_out": timed_out,
        "returncode": code,
        "stdout": stdout,
        "stderr": stderr,
    }
    receipt.write_text(json.dumps(record, indent=2) + "\n")
    _emit(
        {
            "gate": args.gate,
            "returncode": code,
            "timed_out": timed_out,
            "elapsed_seconds": record["elapsed_seconds"],
            "receipt": str(receipt.relative_to(ROOT)),
            "sha256": _digest(receipt),
            "stdout_tail": stdout[-3500:],
            "stderr_tail": stderr[-1800:],
        }
    )
    return code


if __name__ == "__main__":
    raise SystemExit(main())
