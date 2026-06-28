#!/usr/bin/env python3
"""Validate committed Layer 3 GY loop artifacts and lifecycle registration."""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import sys
import tempfile
import tomllib
import uuid
from collections.abc import Iterator
from contextlib import ExitStack
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import patch

FAMILY_ID = "policy-design-case-layer3-gy-loop-artifacts"
SOURCE_FAMILY_ID = "policy-design-case-layer3-gy-loop-source-artifacts"
MANIFEST_PATH = "architecture/policy_design_case/layer3_gy_slice0_fixture_manifest.json"
PROOFS_PATH = "architecture/policy_design_case/layer3_gy_production_loop_run_proofs.json"
GRADED_OUTCOME_PATH = (
    "architecture/policy_design_case/layer3_gy_graded_outcome_routing_report.json"
)
OUTCOME_RUN_PATH = "architecture/policy_design_case/layer3_gy_outcome_run.json"
OUTCOME_REPLAY_PATH = (
    "architecture/policy_design_case/layer3_gy_outcome_replay_proof.json"
)
BENCHMARK_PATH = "architecture/policy_design_case/layer3_gy_semantic_benchmark.json"


def declared_outputs() -> list[str]:
    """Return the generated artifacts this validator writes in --write mode."""

    return [
        PROOFS_PATH,
        GRADED_OUTCOME_PATH,
        OUTCOME_RUN_PATH,
        OUTCOME_REPLAY_PATH,
    ]


def validate(
    repo_root: Path,
    *,
    write: bool = False,
    corrupt_field_drift_check: bool = False,
) -> dict[str, Any]:
    issues: list[dict[str, str]] = []
    _ensure_src_path(repo_root)
    generated = tomllib.loads(
        (repo_root / "architecture/generated_artifacts.toml").read_text(encoding="utf-8")
    )
    families = {family.get("id"): family for family in generated.get("family", [])}
    family = families.get(FAMILY_ID)
    if not family:
        issues.append({"code": "layer3_gy_generated_artifacts_family_missing"})
    else:
        outputs = set(family.get("outputs") or [])
        expected_outputs = {
            PROOFS_PATH,
            GRADED_OUTCOME_PATH,
            OUTCOME_RUN_PATH,
            OUTCOME_REPLAY_PATH,
        }
        if outputs != expected_outputs:
            issues.append(
                {
                    "code": "layer3_gy_generated_output_scope_drift",
                    "expected": ",".join(sorted(expected_outputs)),
                    "actual": ",".join(sorted(outputs)),
                }
            )
        if family.get("stale_output_behavior") != "fail":
            issues.append({"code": "layer3_gy_stale_output_not_fail_closed"})
        if "--check" not in list(family.get("check_command") or []):
            issues.append({"code": "layer3_gy_check_command_missing_check_mode"})
        regenerate_commands = " ".join(family.get("regenerate_commands") or [])
        if "--write" not in regenerate_commands:
            issues.append({"code": "layer3_gy_regenerate_command_missing_write_mode"})
    source_family = families.get(SOURCE_FAMILY_ID)
    if not source_family:
        issues.append({"code": "layer3_gy_loop_source_family_missing"})
    else:
        source_outputs = set(source_family.get("outputs") or [])
        if source_outputs != {MANIFEST_PATH, BENCHMARK_PATH}:
            issues.append(
                {
                    "code": "layer3_gy_loop_source_output_scope_drift",
                    "expected": ",".join(sorted((MANIFEST_PATH, BENCHMARK_PATH))),
                    "actual": ",".join(sorted(source_outputs)),
                }
            )
        if source_family.get("lifecycle") != "source_committed":
            issues.append({"code": "layer3_gy_loop_source_family_lifecycle_drift"})
        _validate_source_artifact_integrity(repo_root, source_family, issues)

    manifest = _read_json(repo_root / MANIFEST_PATH, issues)
    if manifest:
        fixture_ids = {
            fixture.get("fixture_id")
            for fixture in manifest.get("fixtures", [])
            if isinstance(fixture, dict)
        }
        required = {
            "ua_msme_credit_worldbank_measurement",
            "tourism_local_development_ceiling_probe",
        }
        missing = sorted(required - fixture_ids)
        if missing:
            issues.append({"code": "layer3_gy_slice0_fixture_missing", "missing": ",".join(missing)})
        for fixture in manifest.get("fixtures", []):
            if not isinstance(fixture, dict):
                issues.append({"code": "layer3_gy_fixture_not_object"})
                continue
            for field in (
                "construct_scope_query",
                "expected_terminal",
                "forbidden_terminals",
                "expected_producer_root_kind",
            ):
                if not fixture.get(field):
                    issues.append(
                        {
                            "code": "layer3_gy_fixture_field_missing",
                            "fixture_id": str(fixture.get("fixture_id")),
                            "field": field,
                        }
                    )

    proofs = {} if write else _read_json(repo_root / PROOFS_PATH, issues)
    if proofs and not write:
        proof_items = proofs.get("proofs")
        if not isinstance(proof_items, list):
            issues.append({"code": "layer3_gy_proofs_not_list"})
        elif not proof_items:
            issues.append({"code": "layer3_gy_proofs_empty"})
        else:
            if len(proof_items) < 2:
                issues.append({"code": "layer3_gy_proofs_missing_two_slice0_paths"})
            for index, proof in enumerate(proof_items):
                if not isinstance(proof, dict):
                    issues.append(
                        {"code": "layer3_gy_proof_not_object", "index": str(index)}
                    )
                    continue
                _validate_production_loop_proof(index, proof, issues)
    graded_report = {} if write else _read_json(repo_root / GRADED_OUTCOME_PATH, issues)
    if graded_report and not write:
        _validate_graded_outcome_report(graded_report, issues)
    outcome_run = {} if write else _read_json(repo_root / OUTCOME_RUN_PATH, issues)
    outcome_replay = {} if write else _read_json(repo_root / OUTCOME_REPLAY_PATH, issues)
    if outcome_run and outcome_replay and not write:
        validate_outcome_run(outcome_run, outcome_replay, issues)
    benchmark = _read_json(repo_root / BENCHMARK_PATH, issues)
    if benchmark:
        for field in ("label_owner", "expert_author", "reviewer", "provenance", "thresholds"):
            if not benchmark.get(field):
                issues.append({"code": "layer3_gy_benchmark_field_missing", "field": field})
        thresholds = benchmark.get("thresholds") or {}
        pre_decision = thresholds.get("pre_decision") if isinstance(thresholds, dict) else None
        for field in ("precision_at_5", "recall_at_known_seeds"):
            if not isinstance(pre_decision, dict) or field not in pre_decision:
                issues.append(
                    {"code": "layer3_gy_benchmark_threshold_missing", "field": field}
                )
        labels = benchmark.get("labels")
        if not isinstance(labels, list) or not labels:
            issues.append({"code": "layer3_gy_benchmark_labels_missing"})
        else:
            for label in labels:
                if not isinstance(label, dict):
                    issues.append({"code": "layer3_gy_benchmark_label_not_object"})
                    continue
                for field in (
                    "owner_expert",
                    "reviewer",
                    "known_admissible_dataset_ids",
                    "negative_control_dataset_ids",
                ):
                    if field not in label:
                        issues.append(
                            {
                                "code": "layer3_gy_benchmark_label_field_missing",
                                "fixture_id": str(label.get("fixture_id")),
                                "field": field,
                            }
                        )

    if any(
        issue.get("code")
        in {
            "layer3_gy_source_output_integrity_drift",
            "layer3_gy_source_output_missing",
            "layer3_gy_source_integrity_digest_missing",
            "layer3_gy_source_integrity_manifest_missing",
        }
        for issue in issues
    ):
        return {
            "status": "fail",
            "issues": issues,
            "checked_artifacts": [
                MANIFEST_PATH,
                PROOFS_PATH,
                GRADED_OUTCOME_PATH,
                OUTCOME_RUN_PATH,
                OUTCOME_REPLAY_PATH,
                BENCHMARK_PATH,
            ],
            "family_id": FAMILY_ID,
            "source_family_id": SOURCE_FAMILY_ID,
            "write": write,
        }

    live_payloads = build_live_loop_artifacts(repo_root)
    live_proofs = live_payloads[PROOFS_PATH]
    live_graded_report = live_payloads[GRADED_OUTCOME_PATH]
    live_outcome_run = live_payloads[OUTCOME_RUN_PATH]
    live_outcome_replay = live_payloads[OUTCOME_REPLAY_PATH]
    live_proof_items = live_proofs.get("proofs")
    if isinstance(live_proof_items, list):
        for index, proof in enumerate(live_proof_items):
            if isinstance(proof, dict):
                _validate_production_loop_proof(index, proof, issues)
            else:
                issues.append({"code": "layer3_gy_live_proof_not_object", "index": str(index)})
    else:
        issues.append({"code": "layer3_gy_live_proofs_not_list"})
    _validate_graded_outcome_report(live_graded_report, issues)
    validate_outcome_run(live_outcome_run, live_outcome_replay, issues)
    if corrupt_field_drift_check:
        corrupt_issues: list[dict[str, str]] = []
        corrupted = json.loads(json.dumps(live_outcome_run))
        corrupted["search_exit_contract"]["terminal_state"]["reason"] = (
            "corrupt-field-drift-check"
        )
        validate_outcome_run(corrupted, live_outcome_replay, corrupt_issues)
        if any(
            issue.get("code") == "layer3_gy_outcome_replay_output_drift"
            for issue in corrupt_issues
        ):
            issues.append({"code": "layer3_gy_graded_outcome_corrupt_field_drift_detected"})
        else:
            issues.append({"code": "layer3_gy_graded_outcome_corrupt_field_drift_not_detected"})
    if write:
        for relative_path, payload in live_payloads.items():
            output_path = repo_root / relative_path
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(
                json.dumps(payload, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
    elif proofs and proofs != live_proofs:
        issues.append({"code": "layer3_gy_production_proof_drift", "path": PROOFS_PATH})
    elif graded_report and graded_report != live_graded_report:
        issues.append(
            {"code": "layer3_gy_graded_outcome_report_drift", "path": GRADED_OUTCOME_PATH}
        )
    elif outcome_run and outcome_run != live_outcome_run:
        issues.append({"code": "layer3_gy_outcome_run_drift", "path": OUTCOME_RUN_PATH})
    elif outcome_replay and outcome_replay != live_outcome_replay:
        issues.append(
            {"code": "layer3_gy_outcome_replay_drift", "path": OUTCOME_REPLAY_PATH}
        )

    from tools.quality.validation import check_layer3_gy_generated_public_lifecycle_audit

    lifecycle_report = (
        check_layer3_gy_generated_public_lifecycle_audit.validate_gy_lifecycle_registry(
            repo_root
        )
    )
    issues.extend(lifecycle_report["issues"])

    return {
        "status": "pass" if not issues else "fail",
        "issues": issues,
        "checked_artifacts": [
            MANIFEST_PATH,
            PROOFS_PATH,
            GRADED_OUTCOME_PATH,
            OUTCOME_RUN_PATH,
            OUTCOME_REPLAY_PATH,
            BENCHMARK_PATH,
        ],
        "family_id": FAMILY_ID,
        "source_family_id": SOURCE_FAMILY_ID,
        "write": write,
    }


def build_live_loop_artifacts(repo_root: Path) -> dict[str, dict[str, Any]]:
    """Recompute proof artifacts from the durable control-plane worker path."""

    _ensure_src_path(repo_root)
    slice0_observations = [
        _run_durable_workspace_loop_observation(
            fixture_id="ua_msme_credit_worldbank_measurement",
            repo_root=repo_root,
            catalog_mode="slice0_fixture",
        ),
        _run_durable_workspace_loop_observation(
            fixture_id="tourism_local_development_ceiling_probe",
            repo_root=repo_root,
            catalog_mode="slice0_fixture",
        ),
    ]
    outcome_observation = _run_durable_workspace_loop_observation(
        fixture_id="ua_msme_credit_worldbank_measurement",
        repo_root=repo_root,
        catalog_mode="production",
    )
    proofs = [observation["proof"] for observation in slice0_observations]
    outcome_run = _build_outcome_run(outcome_observation)
    outcome_replay = {
        "schema_version": "policyos.policy_design_case.layer3_gy.outcome_replay_artifact.v1",
        "owner": "team-runtime-quality",
        "proof_source": "production_http_route_recomputed",
        "case_id": "ua-msme-affordable-loans-2022",
        "replay_proof": outcome_observation["outcome_replay_proof"],
    }
    return {
        PROOFS_PATH: {
            "schema_version": "policyos.policy_design_case.layer3_gy.production_loop_run_proofs.v1",
            "owner": "team-runtime-quality",
            "proof_source": "durable_worker_recomputed",
            "proofs": proofs,
        },
        GRADED_OUTCOME_PATH: _build_graded_outcome_report([outcome_observation]),
        OUTCOME_RUN_PATH: outcome_run,
        OUTCOME_REPLAY_PATH: outcome_replay,
    }


def _build_outcome_run(observation: dict[str, Any]) -> dict[str, Any]:
    contract = dict(observation["search_exit_contract"])
    proof = dict(observation["proof"])
    replay = dict(observation["outcome_replay_proof"])
    terminal = dict(contract.get("terminal_state") or {})
    return {
        "schema_version": "policyos.policy_design_case.layer3_gy.outcome_run.v1",
        "rule_version": "policyos.layer3.gy.outcome_run.v1",
        "owner": "team-runtime-quality",
        "case_id": "ua-msme-affordable-loans-2022",
        "fixture_id": str(observation["fixture_id"]),
        "proof_source": "production_http_route_recomputed",
        "trigger_kind": str(observation["trigger_kind"]),
        "http_receipts": dict(observation["http_receipts"]),
        "gx_validator_status": str(observation["gx_validator_status"]),
        "gx_case_outcome": dict(observation["gx_case_outcome"]),
        "terminal_outcome": str(terminal.get("kind") or ""),
        "useful_design_credit": terminal.get("kind") == "grounded_partial_admissible",
        "evidence_kind": contract.get("evidence_kind"),
        "decision_grade": contract.get("decision_grade"),
        "evidence_ladder_rung": contract.get("evidence_ladder_rung"),
        "producer_roots": list(replay.get("producer_roots") or []),
        "incompleteness": dict(contract.get("incompleteness_record") or {}),
        "input_hashes": dict(replay.get("input_hashes") or {}),
        "output_hash": str(replay.get("output_hash") or ""),
        "search_exit_contract_ref": str(proof["output_search_exit_contract_ref"]),
        "production_loop_run_proof_ref": str(observation["proof_ref"]),
        "outcome_replay_proof_ref": str(proof["output_replay_proof_ref"]),
        "cas_resolution_checks": list(observation["cas_resolution_checks"]),
        "artifacts_index": dict(observation["artifacts_index"]),
        "production_loop_run_proof": proof,
        "search_exit_contract": contract,
    }


def _validate_source_artifact_integrity(
    repo_root: Path,
    family: dict[str, Any],
    issues: list[dict[str, str]],
) -> None:
    integrity = family.get("source_integrity_sha256")
    if not isinstance(integrity, dict):
        issues.append({"code": "layer3_gy_source_integrity_manifest_missing"})
        return
    for output in (MANIFEST_PATH, BENCHMARK_PATH):
        expected = str(integrity.get(output) or "")
        if not expected:
            issues.append({"code": "layer3_gy_source_integrity_digest_missing", "path": output})
            continue
        path = repo_root / output
        if not path.is_file():
            issues.append({"code": "layer3_gy_source_output_missing", "path": output})
            continue
        actual = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != expected:
            issues.append(
                {
                    "code": "layer3_gy_source_output_integrity_drift",
                    "path": output,
                    "expected": expected,
                    "actual": actual,
                }
            )


def _build_graded_outcome_report(
    observations: list[dict[str, Any]],
) -> dict[str, Any]:
    outcomes: list[dict[str, Any]] = []
    non_value_outcomes: list[dict[str, Any]] = []
    for observation in observations:
        proof = dict(observation["proof"])
        contract = dict(observation.get("search_exit_contract") or {})
        terminal = contract.get("terminal_state")
        authority = contract.get("authority_boundary")
        if not isinstance(terminal, dict):
            continue
        if terminal.get("kind") != "grounded_partial_admissible":
            non_value_outcomes.append(
                {
                    "fixture_id": str(observation["fixture_id"]),
                    "run_id": str(proof.get("run_id") or ""),
                    "job_id": str(proof.get("job_id") or ""),
                    "terminal_state": str(terminal.get("kind") or ""),
                    "decision_grade": str(contract.get("decision_grade") or "unsupported"),
                    "evidence_kind": contract.get("evidence_kind"),
                    "evidence_ladder_rung": str(
                        contract.get("evidence_ladder_rung") or "none"
                    ),
                    "incompleteness_recorded": bool(
                        contract.get("incompleteness_record")
                    ),
                    "useful_design_credit": False,
                }
            )
            continue
        if not isinstance(authority, dict):
            continue
        outcomes.append(
            {
                "fixture_id": str(observation["fixture_id"]),
                "run_id": str(proof.get("run_id") or ""),
                "job_id": str(proof.get("job_id") or ""),
                "output_search_exit_contract_ref": str(
                    proof.get("output_search_exit_contract_ref") or ""
                ),
                "terminal_state": str(terminal.get("kind") or ""),
                "conversion_outcome": "publish-with-limitation",
                "authority_boundary_ref": str(authority.get("boundary_id") or ""),
                "decision_grade": str(authority.get("decision_grade") or ""),
                "evidence_kind": str(authority.get("evidence_kind") or ""),
                "limitation_refs": list(authority.get("known_limits") or []),
                "may_not_use_for": list(authority.get("may_not_use_for") or []),
                "useful_design_credit_route": "genuine_graded_outcome_only",
                "floor_relaxation_used": False,
            }
        )
    capped_count = sum(
        1
        for outcome in outcomes
        if outcome.get("decision_grade") in {"descriptive_only", "advisory_admissible"}
    )
    return {
        "schema_version": (
            "policyos.policy_design_case.layer3_gy.graded_outcome_routing_report.v1"
        ),
        "rule_version": "policyos.layer3.gy.graded_outcome_routing.v1",
        "owner": "team-runtime-quality",
        "proof_source": "durable_worker_recomputed",
        "graded_outcomes": outcomes,
        "honest_non_value_outcomes": non_value_outcomes,
        "summary": {
            "grounded_partial_admissible_count": len(outcomes),
            "capped_decision_grade_count": capped_count,
            "floor_relaxation_used_count": sum(
                1 for outcome in outcomes if outcome.get("floor_relaxation_used") is True
            ),
            "useful_design_rate": (
                round(len(outcomes) / len(observations), 4) if observations else 0.0
            ),
        },
    }


def _validate_graded_outcome_report(
    report: dict[str, Any],
    issues: list[dict[str, str]],
) -> None:
    if report.get("schema_version") != (
        "policyos.policy_design_case.layer3_gy.graded_outcome_routing_report.v1"
    ):
        issues.append({"code": "layer3_gy_graded_outcome_schema_version_invalid"})
    outcomes = report.get("graded_outcomes")
    if not isinstance(outcomes, list):
        issues.append({"code": "layer3_gy_graded_outcomes_missing"})
        return
    for index, outcome in enumerate(outcomes):
        if not isinstance(outcome, dict):
            issues.append(
                {"code": "layer3_gy_graded_outcome_not_object", "index": str(index)}
            )
            continue
        if outcome.get("terminal_state") != "grounded_partial_admissible":
            issues.append(
                {
                    "code": "layer3_gy_graded_outcome_terminal_invalid",
                    "index": str(index),
                }
            )
        if outcome.get("conversion_outcome") != "publish-with-limitation":
            issues.append(
                {
                    "code": "layer3_gy_graded_outcome_conversion_invalid",
                    "index": str(index),
                }
            )
        if outcome.get("decision_grade") not in {
            "descriptive_only",
            "advisory_admissible",
        }:
            issues.append(
                {
                    "code": "layer3_gy_graded_outcome_decision_grade_uncapped",
                    "index": str(index),
                }
            )
        if not outcome.get("limitation_refs"):
            issues.append(
                {
                    "code": "layer3_gy_graded_outcome_limitation_missing",
                    "index": str(index),
                }
            )
        may_not_use_for = set(outcome.get("may_not_use_for") or [])
        if not may_not_use_for or "production_decision" not in may_not_use_for:
            issues.append(
                {
                    "code": "layer3_gy_graded_outcome_deny_list_missing",
                    "index": str(index),
                }
            )
        if outcome.get("floor_relaxation_used") is not False:
            issues.append(
                {
                    "code": "layer3_gy_graded_outcome_floor_relaxation_used",
                    "index": str(index),
                }
            )
        ref = str(outcome.get("output_search_exit_contract_ref") or "")
        if not _looks_like_sha256_ref(ref):
            issues.append(
                {
                    "code": "layer3_gy_graded_outcome_contract_ref_invalid",
                    "index": str(index),
                }
            )
    non_value = report.get("honest_non_value_outcomes")
    if not isinstance(non_value, list):
        issues.append({"code": "layer3_gy_honest_non_value_outcomes_missing"})
        return
    for index, outcome in enumerate(non_value):
        if not isinstance(outcome, dict):
            issues.append(
                {"code": "layer3_gy_honest_non_value_outcome_not_object", "index": str(index)}
            )
            continue
        if outcome.get("terminal_state") not in {
            "grounded_abstention",
            "search_ceiling_repair_required",
            "acquisition_required",
            "a_spec_gap",
            "tool_failure",
            "composition_invalid",
            "recursive_blocked",
            "budget_exhausted",
            "human_decision_required",
        }:
            issues.append(
                {"code": "layer3_gy_honest_non_value_terminal_invalid", "index": str(index)}
            )
        if outcome.get("useful_design_credit") is not False:
            issues.append(
                {"code": "layer3_gy_honest_non_value_forced_useful", "index": str(index)}
            )
        if outcome.get("incompleteness_recorded") is not True:
            issues.append(
                {"code": "layer3_gy_honest_non_value_incompleteness_missing", "index": str(index)}
            )
    summary = report.get("summary")
    if isinstance(summary, dict):
        expected_rate = (
            round(len(outcomes) / (len(outcomes) + len(non_value)), 4)
            if outcomes or non_value
            else 0.0
        )
        if summary.get("useful_design_rate") != expected_rate:
            issues.append({"code": "layer3_gy_useful_design_rate_drift"})


def validate_outcome_run(
    outcome: dict[str, Any],
    replay_artifact: dict[str, Any],
    issues: list[dict[str, str]],
) -> None:
    """Recompute the GY-L outcome claims from the production run payloads."""

    from pydantic import ValidationError

    from polisyos.core.canon import CanonSpec, to_canonical_bytes
    from polisyos.runtime.quality.authority import (
        OutcomeReplayProof,
        ProductionLoopRunProof,
    )
    from tools.quality.validation.gy_evidence_canon import canonical_evidence_hash

    if outcome.get("trigger_kind") != "http_control_route":
        issues.append({"code": "layer3_gy_outcome_direct_helper_rejected"})
    if outcome.get("proof_source") != "production_http_route_recomputed":
        issues.append({"code": "layer3_gy_outcome_hand_authored_proof_rejected"})
    proof_payload = outcome.get("production_loop_run_proof")
    contract = outcome.get("search_exit_contract")
    replay_payload = replay_artifact.get("replay_proof")
    if not isinstance(proof_payload, dict):
        issues.append({"code": "layer3_gy_outcome_production_proof_missing"})
        return
    if not isinstance(contract, dict):
        issues.append({"code": "layer3_gy_outcome_search_exit_contract_missing"})
        return
    if not isinstance(replay_payload, dict):
        issues.append({"code": "layer3_gy_outcome_replay_proof_missing"})
        return
    try:
        proof = ProductionLoopRunProof.model_validate(proof_payload)
        replay = OutcomeReplayProof.model_validate(replay_payload)
    except ValidationError:
        issues.append({"code": "layer3_gy_outcome_typed_proof_invalid"})
        return

    receipts = outcome.get("http_receipts")
    launch = receipts.get("launch") if isinstance(receipts, dict) else None
    readback = receipts.get("readback") if isinstance(receipts, dict) else None
    if not isinstance(launch, dict) or (
        launch.get("method") != "POST"
        or launch.get("surface") != "/api/v1/control/runs"
        or launch.get("status_code") != 200
        or launch.get("job_id") != proof.job_id
        or launch.get("run_id") != proof.run_id
    ):
        issues.append({"code": "layer3_gy_outcome_http_launch_receipt_invalid"})
    if not isinstance(readback, dict) or (
        readback.get("method") != "GET"
        or readback.get("status_code") != 200
        or readback.get("observed_state") != "completed"
        or proof.job_id not in str(readback.get("surface") or "")
    ):
        issues.append({"code": "layer3_gy_outcome_http_readback_receipt_invalid"})

    terminal = contract.get("terminal_state")
    terminal_kind = terminal.get("kind") if isinstance(terminal, dict) else None
    accepted_terminals = {
        "grounded_partial_admissible",
        "grounded_abstention",
        "search_ceiling_repair_required",
        "acquisition_required",
        "a_spec_gap",
        "tool_failure",
        "composition_invalid",
        "recursive_blocked",
        "budget_exhausted",
        "human_decision_required",
    }
    if terminal_kind not in accepted_terminals:
        issues.append({"code": "layer3_gy_outcome_terminal_invalid"})
    if terminal_kind != outcome.get("terminal_outcome"):
        issues.append({"code": "layer3_gy_outcome_terminal_projection_drift"})
    if outcome.get("case_id") == "ua-msme-affordable-loans-2022" and (
        terminal_kind == "grounded_partial_admissible"
        or outcome.get("useful_design_credit") is not False
    ):
        issues.append({"code": "layer3_gy_outcome_ua_msme_forced_value_rejected"})
    gx_case_outcome = outcome.get("gx_case_outcome")
    if not isinstance(gx_case_outcome, dict) or (
        gx_case_outcome.get("case_id") != outcome.get("case_id")
        or gx_case_outcome.get("outcome_kind") != terminal_kind
        or gx_case_outcome.get("useful_design_credit")
        is not outcome.get("useful_design_credit")
        or not _looks_like_sha256_ref(
            str(gx_case_outcome.get("final_run_hash") or "")
        )
        or gx_case_outcome.get("input_artifact_ref") not in replay.input_hashes
    ):
        issues.append({"code": "layer3_gy_outcome_gx_terminal_drift"})
    if not contract.get("incompleteness_record") or not outcome.get("incompleteness"):
        issues.append({"code": "layer3_gy_outcome_incompleteness_missing"})
    boundary = contract.get("authority_boundary")
    expected_evidence_kind = (
        boundary.get("evidence_kind") if isinstance(boundary, dict) else None
    )
    expected_decision_grade = (
        boundary.get("decision_grade") if isinstance(boundary, dict) else "unsupported"
    ) or "unsupported"
    if contract.get("evidence_kind") != expected_evidence_kind:
        issues.append({"code": "layer3_gy_outcome_evidence_kind_drift"})
    if contract.get("decision_grade") != expected_decision_grade:
        issues.append({"code": "layer3_gy_outcome_decision_grade_drift"})
    if contract.get("evidence_ladder_rung") != (expected_evidence_kind or "none"):
        issues.append({"code": "layer3_gy_outcome_ladder_rung_drift"})

    recomputed_output_hash = canonical_evidence_hash(contract)
    if replay.output_hash != recomputed_output_hash or outcome.get(
        "output_hash"
    ) != recomputed_output_hash:
        issues.append({"code": "layer3_gy_outcome_replay_output_drift"})
    if replay.replay_levels != ["A", "B", "C"] or any(
        level.status != "verified" for level in replay.level_proofs
    ):
        issues.append({"code": "layer3_gy_outcome_replay_levels_invalid"})
    if not replay.input_hashes or replay.input_hashes != outcome.get("input_hashes"):
        issues.append({"code": "layer3_gy_outcome_input_hash_drift"})
    if not replay.producer_roots or replay.producer_roots != outcome.get("producer_roots"):
        issues.append({"code": "layer3_gy_outcome_producer_roots_missing"})

    cas_checks = outcome.get("cas_resolution_checks")
    resolved_refs = {
        str(item.get("artifact_ref"))
        for item in cas_checks or []
        if isinstance(item, dict) and item.get("resolved") is True
    }
    if any(
        item.get("payload_sha256") != item.get("artifact_ref")
        for item in cas_checks or []
        if isinstance(item, dict) and item.get("resolved") is True
    ):
        issues.append({"code": "layer3_gy_outcome_cas_content_hash_drift"})
    if not set(proof.output_cas_refs) <= resolved_refs:
        issues.append({"code": "layer3_gy_outcome_cas_resolution_missing"})
    proof_ref = str(outcome.get("production_loop_run_proof_ref") or "")
    recomputed_proof_ref = "sha256:" + hashlib.sha256(
        to_canonical_bytes(proof_payload, CanonSpec(forbid_floats=False))
    ).hexdigest()
    if proof_ref not in resolved_refs or proof_ref != recomputed_proof_ref:
        issues.append({"code": "layer3_gy_outcome_production_proof_content_drift"})
    artifacts_index = outcome.get("artifacts_index")
    if not isinstance(artifacts_index, dict) or any(
        key not in artifacts_index for key in proof.artifacts_index_refs
    ):
        issues.append({"code": "layer3_gy_outcome_artifacts_index_resolution_missing"})
    if proof.output_replay_proof_ref != outcome.get("outcome_replay_proof_ref"):
        issues.append({"code": "layer3_gy_outcome_replay_ref_drift"})
    if proof.control_store_state_transitions != ["pending", "running", "completed"]:
        issues.append({"code": "layer3_gy_outcome_store_transitions_invalid"})
    if "runs_readback" not in proof.surface_reads_checked or not proof.surface_readbacks:
        issues.append({"code": "layer3_gy_outcome_runs_readback_missing"})


def _run_durable_workspace_loop_proof(
    *,
    fixture_id: str,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    """Return only the proof payload for compatibility with older tests."""

    return _run_durable_workspace_loop_observation(
        fixture_id=fixture_id,
        repo_root=(repo_root or Path.cwd()).resolve(),
        catalog_mode="slice0_fixture",
    )["proof"]


def _run_durable_workspace_loop_observation(
    *,
    fixture_id: str,
    repo_root: Path,
    catalog_mode: str,
) -> dict[str, Any]:
    from polisyos.core.artifacts.manifest import SchemaInfo
    from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
    from polisyos.core.canon import CanonSpec
    from polisyos.data_forge.read_api.catalog import build_slice0_fixture_catalog_graph
    from polisyos.runtime.http.app import create_runtime_api_app
    from polisyos.runtime.http.container import RuntimeContainerOverrides
    from polisyos.runtime.http.execution_policy import RuntimeExecutionPolicyResolver
    from polisyos.runtime.http.services.control.run_lifecycle import ControlPlaneService
    from polisyos.runtime.http.services.control_registry_providers import (
        resolve_control_registry_providers,
    )
    from polisyos.runtime.http.services.control_worker import ControlWorker
    from polisyos.runtime.quality.authority import (
        OutcomeReplayProof,
        ProductionLoopRunProof,
    )

    try:
        from fastapi.testclient import TestClient
    except ModuleNotFoundError as exc:  # pragma: no cover - runtime dependency gate
        raise RuntimeError("FastAPI TestClient is required for production-route proof") from exc

    fixed_now = datetime(2026, 6, 15, 12, 0, 0, tzinfo=UTC)
    uuid_iter = _deterministic_uuid_sequence(
        f"gy-loop-proof:{catalog_mode}:{fixture_id}"
    )
    if catalog_mode == "production":
        catalog_root = (
            repo_root
            / "production_data/datasets_full_phase3full_20260327_183054"
        )
        catalog_path = catalog_root / "dataset_catalog.duckdb"
        if not catalog_path.is_file():
            raise RuntimeError(
                "GY-L production catalog prerequisite missing: " + str(catalog_path)
            )
        from polisyos.data_forge.domains.catalog.knowledge.search import DatasetCatalogGraph

        catalog_graph = DatasetCatalogGraph(catalog_path, catalog_root)
        gx_input_path = (
            repo_root
            / "architecture/policy_design_case/layer3_gx_reports/"
            "ua-msme-affordable-loans-2022/"
            "layer3_gx_final_pinned_route_outcome_report.json"
        )
        root_payload = json.loads(gx_input_path.read_text(encoding="utf-8"))
        from tools.quality.validation import (
            check_policy_design_case_layer3_gx_hardening,
        )

        gx_report = check_policy_design_case_layer3_gx_hardening.validate_layer3_gx_hardening(
            repo_root,
            case="ua-msme",
        )
        gx_validator_status = str(gx_report.get("status") or "fail")
    elif catalog_mode == "slice0_fixture":
        catalog_graph = None
        root_payload = {"fixture_id": fixture_id, "root": True}
        gx_validator_status = "not_applicable_slice0_fixture"
    else:
        raise ValueError(f"unsupported catalog_mode: {catalog_mode}")

    with tempfile.TemporaryDirectory(prefix=f"polisyos-gy-loop-proof-{fixture_id}-") as tmp:
        root = Path(tmp)
        cas_root = root / ".polisyos"
        store = FileSystemCAS(cas_root)
        root_ref = store.put_json(
            root_payload,
            PutOptions(
                kind="gy.loop.proof.root",
                media_type="application/json",
                schema=SchemaInfo(name="polisyos.gy.loop.proof.root", version="1.0"),
            ),
            canon_spec=CanonSpec(forbid_floats=False),
        )
        if catalog_graph is None:
            catalog_graph = build_slice0_fixture_catalog_graph(root / "catalog")
        providers = resolve_control_registry_providers(
            gy_catalog_graph=catalog_graph
        )
        with ExitStack() as stack:
            stack.enter_context(
                patch(
                    "polisyos.core.run.context.new_run_id",
                    return_value=f"run-gy-loop-proof-{fixture_id}",
                )
            )
            for target in (
                "polisyos.runtime.http.services.control.run_lifecycle.uuid.uuid4",
                "polisyos.runtime.http.services.control.workspace_loop_transition.uuid.uuid4",
                "polisyos.runtime.http.services.control_worker.uuid.uuid4",
            ):
                stack.enter_context(patch(target, side_effect=lambda: next(uuid_iter)))
            stack.enter_context(
                patch(
                    "polisyos.runtime.http.services.control_plane_store._utc_now",
                    return_value=fixed_now,
                )
            )
            stack.enter_context(
                patch(
                    "polisyos.runtime.quality.acquisition_planner._utc",
                    return_value=fixed_now,
                )
            )
            stack.enter_context(
                patch(
                    "polisyos.runtime.quality.workspace.loop._utc_now",
                    return_value=fixed_now,
                )
            )
            service = ControlPlaneService(
                cas_root=cas_root,
                core_runs_root=cas_root / "runs",
                artifact_store=store,
                registry_providers=providers,
                policy_resolver=RuntimeExecutionPolicyResolver(
                    default_profile="dev",
                    worker_backend="external",
                    state_store_backend="sqlite",
                    sqlite_path=str(root / "control_plane.sqlite3"),
                    postgres_dsn=None,
                ),
            )
            service._worker = ControlWorker(
                store=service._control_store,
                handler=service._process_control_job,
                worker_id=(
                    f"control-worker-gy-loop-proof-{catalog_mode}-{_slug(fixture_id)}"
                ),
            )
            app = create_runtime_api_app(
                cas_root=cas_root,
                core_runs_root=cas_root / "runs",
                enable_security_middlewares=False,
                allow_fixture_identity=True,
                container_overrides=RuntimeContainerOverrides(control_service=service),
            )
            try:
                with TestClient(app) as client:
                    launch_response = client.post(
                        "/api/v1/control/runs",
                        json={
                            "data_source": {
                                "data_snapshot_ref": str(root_ref.artifact_id),
                            },
                            "params": {"slice0_fixture_id": fixture_id},
                        },
                        headers={"X-Request-ID": f"gy-loop-{catalog_mode}-{_slug(fixture_id)}"},
                    )
                    if launch_response.status_code != 200:
                        raise RuntimeError(
                            "Production control route rejected GY loop run: "
                            f"{launch_response.status_code} {launch_response.text}"
                        )
                    launch = launch_response.json()
                    if service._worker is None:
                        raise RuntimeError("ControlWorker was not initialized")
                    service._worker.dispatch_once()
                    readback_response = client.get(
                        f"/api/v1/control/jobs/{launch['job_id']}",
                        headers={
                            "X-Request-ID": (
                                f"gy-loop-readback-{catalog_mode}-{_slug(fixture_id)}"
                            )
                        },
                    )
                response_payload = readback_response.json()
                if response_payload.get("state") != "completed":
                    raise RuntimeError(
                        f"Durable proof job for {fixture_id} did not complete: "
                        f"{response_payload.get('state')}"
                    )
                progress = dict(response_payload["progress"])
                proof_payload = progress.get("production_loop_run_proof")
                proof = ProductionLoopRunProof.model_validate(proof_payload)
                contract_payload = progress.get("search_exit_contract")
                replay_payload = progress.get("outcome_replay_proof")
                replay = OutcomeReplayProof.model_validate(replay_payload)
                cas_checks = []
                proof_ref = str(progress["production_loop_run_proof_ref"])
                for artifact_ref in [*proof.output_cas_refs, proof_ref]:
                    payload_bytes = store.get_bytes(artifact_ref)
                    cas_checks.append(
                        {
                            "artifact_ref": artifact_ref,
                            "resolved": True,
                            "payload_sha256": "sha256:"
                            + hashlib.sha256(payload_bytes).hexdigest(),
                        }
                    )
                return {
                    "fixture_id": fixture_id,
                    "proof": proof.model_dump(mode="json", by_alias=True),
                    "proof_ref": proof_ref,
                    "outcome_replay_proof": replay.model_dump(mode="json"),
                    "search_exit_contract": (
                        contract_payload if isinstance(contract_payload, dict) else {}
                    ),
                    "artifacts_index": dict(progress.get("artifacts_index") or {}),
                    "cas_resolution_checks": cas_checks,
                    "trigger_kind": "http_control_route",
                    "gx_validator_status": gx_validator_status,
                    "gx_case_outcome": {
                        "case_id": str(root_payload.get("case_id") or ""),
                        "status": str(root_payload.get("status") or ""),
                        "outcome_kind": str(root_payload.get("outcome_kind") or ""),
                        "useful_design_credit": root_payload.get("useful_design_credit"),
                        "final_run_hash": str(root_payload.get("final_run_hash") or ""),
                        "input_artifact_ref": str(root_ref.artifact_id),
                    },
                    "http_receipts": {
                        "launch": {
                            "method": "POST",
                            "surface": "/api/v1/control/runs",
                            "status_code": launch_response.status_code,
                            "run_id": launch["run_id"],
                            "job_id": launch["job_id"],
                        },
                        "readback": {
                            "method": "GET",
                            "surface": f"/api/v1/control/jobs/{launch['job_id']}",
                            "status_code": readback_response.status_code,
                            "observed_state": response_payload["state"],
                        },
                    },
                }
            finally:
                service.close()


def _deterministic_uuid_sequence(seed: str) -> Iterator[uuid.UUID]:
    index = 0
    while True:
        yield uuid.uuid5(uuid.NAMESPACE_URL, f"{seed}:{index}")
        index += 1


def _slug(value: str) -> str:
    normalized = "".join(char.lower() if char.isalnum() else "-" for char in value)
    compact = "-".join(part for part in normalized.split("-") if part)
    return compact or "item"


def _ensure_src_path(repo_root: Path) -> None:
    src_path = repo_root / "src"
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))


def _read_json(path: Path, issues: list[dict[str, str]]) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        issues.append({"code": "layer3_gy_artifact_missing", "path": str(path)})
        return {}
    except json.JSONDecodeError as exc:
        issues.append({"code": "layer3_gy_artifact_invalid_json", "path": str(path), "error": str(exc)})
        return {}
    if not isinstance(payload, dict):
        issues.append({"code": "layer3_gy_artifact_not_object", "path": str(path)})
        return {}
    return payload


def _validate_production_loop_proof(
    index: int,
    proof: dict[str, Any],
    issues: list[dict[str, str]],
) -> None:
    required_fields = (
        "run_id",
        "job_id",
        "endpoint",
        "http_request_id",
        "job_kind",
        "worker_lease_id",
        "worker_id",
        "_execute_workflow_invocation_id",
        "workspace_loop_invocation_id",
        "control_store_state_transitions",
        "input_artifacts",
        "output_search_exit_contract_ref",
        "output_replay_proof_ref",
        "output_cas_refs",
        "artifacts_index_refs",
        "surface_reads_checked",
        "legacy_path_disposition",
    )
    for field in required_fields:
        if not proof.get(field):
            issues.append(
                {
                    "code": "layer3_gy_proof_field_missing",
                    "index": str(index),
                    "field": field,
                }
            )
    if proof.get("endpoint") != "/api/v1/control/runs":
        issues.append({"code": "layer3_gy_proof_endpoint_not_runs", "index": str(index)})
    if proof.get("job_kind") != "workflow_run":
        issues.append({"code": "layer3_gy_proof_job_kind_not_workflow", "index": str(index)})
    if proof.get("legacy_path_disposition") != "routed_to_workspace_loop":
        issues.append(
            {"code": "layer3_gy_proof_not_workspace_loop_authority_path", "index": str(index)}
        )
    if proof.get("control_store_state_transitions") != ["pending", "running", "completed"]:
        issues.append({"code": "layer3_gy_proof_state_sequence_invalid", "index": str(index)})
    if "runs_readback" not in set(proof.get("surface_reads_checked") or []):
        issues.append({"code": "layer3_gy_proof_runs_readback_missing", "index": str(index)})
    readbacks = proof.get("surface_readbacks")
    if not isinstance(readbacks, list) or not readbacks:
        issues.append(
            {"code": "layer3_gy_proof_runs_readback_observation_missing", "index": str(index)}
        )
    else:
        observed_results = set()
        for readback_index, readback in enumerate(readbacks):
            if not isinstance(readback, dict):
                issues.append(
                    {
                        "code": "layer3_gy_proof_readback_not_object",
                        "index": str(index),
                        "readback_index": str(readback_index),
                    }
                )
                continue
            observed_results.add(str(readback.get("observed_authority_result") or ""))
            if readback.get("surface") != "/api/v1/control/runs":
                issues.append(
                    {
                        "code": "layer3_gy_proof_readback_surface_invalid",
                        "index": str(index),
                        "readback_index": str(readback_index),
                    }
                )
            if readback.get("observed_job_state") != "completed":
                issues.append(
                    {
                        "code": "layer3_gy_proof_readback_not_completed",
                        "index": str(index),
                        "readback_index": str(readback_index),
                    }
                )
            if readback.get("observed_search_exit_contract_ref") != proof.get(
                "output_search_exit_contract_ref"
            ):
                issues.append(
                    {
                        "code": "layer3_gy_proof_readback_contract_ref_mismatch",
                        "index": str(index),
                        "readback_index": str(readback_index),
                    }
                )
            if readback.get("matched_search_exit_contract_ref") is not True:
                issues.append(
                    {
                        "code": "layer3_gy_proof_readback_match_not_true",
                        "index": str(index),
                        "readback_index": str(readback_index),
                    }
                )
        if "verifier_stamped" in observed_results and (
            "authority_derivation_trace_refs"
            not in set(proof.get("artifacts_index_refs") or [])
        ):
            issues.append(
                {"code": "layer3_gy_proof_authority_trace_ref_missing", "index": str(index)}
            )
        if "acquisition_required" in observed_results and (
            "authority_derivation_trace_refs"
            in set(proof.get("artifacts_index_refs") or [])
        ):
            issues.append(
                {
                    "code": "layer3_gy_proof_acquisition_must_not_claim_authority_trace",
                    "index": str(index),
                }
            )
    if not str(proof.get("worker_lease_id") or "").startswith("control-worker"):
        issues.append({"code": "layer3_gy_proof_worker_lease_missing", "index": str(index)})
    if proof.get("worker_lease_id") != proof.get("worker_id"):
        issues.append({"code": "layer3_gy_proof_worker_lease_mismatch", "index": str(index)})
    refs = [
        str(proof.get("output_search_exit_contract_ref") or ""),
        str(proof.get("output_replay_proof_ref") or ""),
        *[str(ref) for ref in proof.get("output_cas_refs") or []],
    ]
    for ref in refs:
        if not _looks_like_sha256_ref(ref):
            issues.append(
                {
                    "code": "layer3_gy_proof_ref_not_content_addressed",
                    "index": str(index),
                    "ref": ref,
                }
            )
        elif len(set(ref.removeprefix("sha256:"))) == 1:
            issues.append(
                {
                    "code": "layer3_gy_proof_placeholder_ref",
                    "index": str(index),
                    "ref": ref,
                }
            )


def _looks_like_sha256_ref(value: str) -> bool:
    prefix = "sha256:"
    return (
        value.startswith(prefix)
        and len(value) == len(prefix) + 64
        and all(char in "0123456789abcdef" for char in value[len(prefix) :])
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--output-format", choices=("json", "text"), default="text")
    parser.add_argument("--check", action="store_true", help="Validate committed artifacts.")
    parser.add_argument("--write", action="store_true", help="Regenerate committed proof artifacts.")
    parser.add_argument(
        "--corrupt-field-drift-check",
        action="store_true",
        help="Mutate a recomputed graded-outcome field and require validation to fail.",
    )
    args = parser.parse_args(argv)
    if args.check and args.write:
        parser.error("--check and --write are mutually exclusive")

    with contextlib.redirect_stdout(sys.stderr):
        report = validate(
            Path(args.repo_root).resolve(),
            write=args.write,
            corrupt_field_drift_check=args.corrupt_field_drift_check,
        )
    if args.output_format == "json":
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"Layer 3 GY loop artifacts: {report['status']}")
        for issue in report["issues"]:
            print(f"- {issue['code']}: {issue}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
