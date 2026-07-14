"""Aggregate GY-N10 proof evidence from canonical PolicyOS owners.

This validator extends the existing N4, N8, N10a, composition, and recursive-cycle
validators.  It does not implement a second generation-cycle controller.  Task 12
intentionally emits only an in-memory ``proof_runs_pending`` payload; Task 13 will
attach the three owner-produced plain-language runs and register the frozen artifact.
"""

from __future__ import annotations

import contextlib
import copy
import functools
import hashlib
import io
import json
import subprocess
import sys
import time
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from tools.quality.validation.universality_preflight import assert_universality_preflight

REPO_ROOT = Path(__file__).resolve().parents[3]

# This is intentionally before argparse, artifact reads, caches, and PolicyOS owner imports.
try:
    assert_universality_preflight(REPO_ROOT)
except Exception as exc:  # pragma: no cover - exercised by a fresh child process
    error = str(exc)
    code = error.partition(":")[0] or type(exc).__name__
    sys.stderr.write(
        json.dumps(
            {"issues": [{"code": code, "error": error}], "status": "fail"},
            sort_keys=True,
        )
        + "\n"
    )
    raise SystemExit(1) from exc

import argparse  # noqa: E402

SCHEMA_VERSION = "policyos.policy_design_case.gy_n10.depth_n_universality.v1"
RULE_VERSION = "policyos.layer3.gy.n10.depth_n_universality.v1"
PRODUCER = (
    "tools.quality.validation.check_layer3_gy_depth_n_universality_contract"
)
OUTPUT_PATH = (
    "architecture/policy_design_case/layer3_gy_depth_n_universality_contract.json"
)

N4_PATH = "architecture/policy_design_case/layer3_gy_design_generation_contract.json"
FORK_B_PATH = (
    "architecture/policy_design_case/layer3_gy_n10_cg1_l2_relation_census.json"
)
N8_PATH = "architecture/policy_design_case/layer3_gy_value_gate_contract.json"
N10A_CENSUS_PATH = (
    "architecture/policy_design_case/layer3_gy_second_domain_census.json"
)
N10A_PACK_PATH = "architecture/policy_design_case/layer3_gy_second_domain_pack.json"
N10A_SMOKE_PATH = (
    "architecture/policy_design_case/layer3_gy_second_domain_smoke_design_problem.json"
)
N10A_TRACE_PATH = (
    "architecture/policy_design_case/layer3_gy_second_domain_cycle_entry_trace.json"
)
N10A_GAPS_PATH = (
    "architecture/policy_design_case/layer3_gy_second_domain_free_grow_gaps.json"
)
COMPOSITION_PATH = (
    "architecture/policy_design_case/layer3_gy_composition_certificates.json"
)

_UPSTREAM_PATHS = (
    N4_PATH,
    FORK_B_PATH,
    N8_PATH,
    "architecture/policy_design_case/layer3_gx_pinned_request.json",
    "architecture/policy_design_case/layer3_gy_data_state_substrate_contract.json",
    N10A_CENSUS_PATH,
    N10A_PACK_PATH,
    N10A_SMOKE_PATH,
    N10A_TRACE_PATH,
    N10A_GAPS_PATH,
    COMPOSITION_PATH,
    "architecture/generated_artifacts.toml",
)
_CONTENT_HASH_EXCLUDED_TOP_LEVEL = {"contract_content_hash", "runtime_metrics"}


class UniversalityContractError(RuntimeError):
    """Raised when a capstone payload cannot be derived honestly."""


def declared_outputs() -> list[str]:
    """Return the canonical artifact path reserved for the Task-13 proof."""

    return [OUTPUT_PATH]


def check_provenance_stability(repo_root: Path) -> dict[str, Any]:
    """Validate and cross-bind every frozen owner on the Stage-4 entry graph.

    Args:
        repo_root: Policy Engine checkout root.

    Returns:
        A content-only stability report. ``status=stable`` means every owner
        validator passed and every cross-artifact identity resolved.
    """

    root = repo_root.resolve()
    dirty_paths = _dirty_upstream_paths(root)
    if dirty_paths:
        return {
            "status": "drifted",
            "issues": [
                {"code": "upstream_artifact_dirty", "paths": dirty_paths}
            ],
        }
    return copy.deepcopy(_cached_provenance_stability(root.as_posix()))


@functools.lru_cache(maxsize=2)
def _cached_provenance_stability(repo_root: str) -> dict[str, Any]:
    # Imported owners may emit informational registration diagnostics. The capstone
    # validator owns one machine-readable output document, so those non-contract
    # side effects are contained at the single owner-intake boundary.
    owner_stdout = io.StringIO()
    owner_stderr = io.StringIO()
    with contextlib.redirect_stdout(owner_stdout), contextlib.redirect_stderr(
        owner_stderr
    ):
        return _derive_provenance_stability(repo_root)


def _derive_provenance_stability(repo_root: str) -> dict[str, Any]:
    root = Path(repo_root)
    issues: list[dict[str, Any]] = []

    # Owner imports happen only after the module-level universality preflight.
    from polisyos.pdc import gy_content_hash
    from polisyos.runtime.quality.design_problem import DesignProblem
    from tools.quality.validation import (
        check_layer3_gy_composition_artifacts as composition_validator,
    )
    from tools.quality.validation import (
        check_layer3_gy_design_generation_contract as n4_validator,
    )
    from tools.quality.validation import (
        check_layer3_gy_n10_cg1_l2_relation_census as census_validator,
    )
    from tools.quality.validation import (
        check_layer3_gy_second_domain_pack as n10a_validator,
    )
    from tools.quality.validation import (
        check_layer3_gy_value_gate_contract as n8_validator,
    )

    n4 = _read_json(root / N4_PATH)
    census = _read_json(root / FORK_B_PATH)
    n8 = _read_json(root / N8_PATH)
    composition = _read_json(root / COMPOSITION_PATH)
    n10a_bundle = n10a_validator._load_frozen_bundle(root)

    with contextlib.chdir(root):
        n4_report = n4_validator.validate(root)
    _extend_owner_issues(issues, "n4", n4_report.get("issues"))
    try:
        census_validator._validate(census)
    except (KeyError, TypeError, ValueError) as exc:
        issues.append({"code": "fork_b_census_invalid", "error": str(exc)})
    _extend_owner_issues(issues, "n8", n8_validator.validate_payload(n8))
    _extend_owner_issues(
        issues,
        "n10a",
        n10a_validator.validate_bundle_payloads(n10a_bundle, root),
    )
    composition_report = composition_validator.validate(root)
    _extend_owner_issues(
        issues,
        "composition",
        composition_report.get("issues"),
    )

    n4_file_sha = _file_sha256(root / N4_PATH)
    census_input = _mapping(census.get("input_refs"))
    census_n4_sha = str(census_input.get("design_generation_artifact_sha256") or "")
    production = _mapping(n8.get("production_refusal"))
    if census_n4_sha != n4_file_sha:
        issues.append({"code": "n4_to_fork_b_artifact_binding_drift"})
    if str(production.get("n4_artifact_sha256") or "") != n4_file_sha:
        issues.append({"code": "n4_to_n8_artifact_binding_drift"})

    census_ref = {
        "artifact_ref": FORK_B_PATH,
        "content_hash": census.get("content_hash"),
        "raw_full_table_content_hash": census.get("raw_full_table_content_hash"),
        "n4_artifact_sha256": census_n4_sha,
    }
    n8_fork_b_ref = _mapping(n8.get("fork_b_census_receipt"))
    if census_ref["content_hash"] != n8_fork_b_ref.get("content_hash"):
        issues.append({"code": "fork_b_to_n8_content_binding_drift"})
    if census_ref["raw_full_table_content_hash"] != n8_fork_b_ref.get(
        "raw_full_table_content_hash"
    ):
        issues.append({"code": "fork_b_to_n8_raw_binding_drift"})

    n4_problem_refs = sorted(
        {
            str(item.get("design_problem_ref"))
            for item in _mappings(n4.get("generation_results"))
            if item.get("design_problem_ref")
        }
    )
    n8_problem_ref = str(production.get("design_problem_ref") or "")
    if n8_problem_ref not in n4_problem_refs:
        issues.append({"code": "n8_design_problem_not_in_n4_denominator"})

    frozen_comparator = _mapping(
        _mapping(n10a_bundle.get("census")).get("first_vertical_comparator")
    )
    live_comparator = n10a_validator._first_vertical_comparator(root)
    if frozen_comparator != live_comparator:
        issues.append({"code": "n10a_first_vertical_comparator_drift"})
    semantic_projection_hash = str(
        _mapping(live_comparator.get("source_hashes")).get(N8_PATH) or ""
    )
    n10a_comparator_hash = str(
        _mapping(frozen_comparator.get("source_hashes")).get(N8_PATH) or ""
    )
    if semantic_projection_hash != n10a_comparator_hash:
        issues.append({"code": "n8_to_n10a_semantic_projection_drift"})

    smoke = _mapping(n10a_bundle.get("smoke_problem"))
    problem = DesignProblem.model_validate(smoke.get("design_problem"))
    canonical_problem_ref = gy_content_hash(problem.model_dump(mode="json"))
    trace = _mapping(n10a_bundle.get("cycle_trace"))
    capture = _mapping(trace.get("n4_owner_capture"))
    capture_input = _mapping(capture.get("input_binding"))
    projection = _mapping(capture.get("owner_result_projection"))
    cycle_run = _mapping(trace.get("generation_cycle_run"))
    design_problem_refs = {
        "canonical": canonical_problem_ref,
        "capture_input": str(capture_input.get("design_problem_ref") or ""),
        "owner_projection": str(projection.get("design_problem_ref") or ""),
        "generation_cycle_run": str(cycle_run.get("design_problem_ref") or ""),
    }
    for index, cycle in enumerate(_mappings(cycle_run.get("cycles"))):
        design_problem_refs[f"cycle_{index}"] = str(
            cycle.get("design_problem_ref") or ""
        )
    if len(set(design_problem_refs.values())) != 1:
        issues.append({"code": "education_design_problem_binding_drift"})

    prompt_hashes = {
        "owner_projection": _strings(projection.get("exact_call_prompt_hashes")),
        "responses": [
            str(item.get("prompt_hash") or "")
            for item in _mappings(capture.get("responses"))
        ],
        "journal": [
            str(item.get("prompt_hash") or "")
            for item in _mappings(
                _mapping(capture.get("journal_receipt")).get("call_evidence_rows")
            )
        ],
    }
    if (
        not prompt_hashes["owner_projection"]
        or prompt_hashes["owner_projection"] != prompt_hashes["responses"]
        or prompt_hashes["owner_projection"] != prompt_hashes["journal"]
    ):
        issues.append({"code": "education_prompt_hash_binding_drift"})

    n10a_census_hash = str(
        _mapping(n10a_bundle.get("census")).get("census_content_hash") or ""
    )
    observed_composition_census_hashes = sorted(
        set(_values_for_key(composition, "census_content_hash"))
    )
    composition_status = (
        "bound"
        if composition_report.get("status") == "pass"
        and observed_composition_census_hashes == [n10a_census_hash]
        else "drifted"
    )
    if composition_status != "bound":
        issues.append({"code": "composition_to_n10a_census_binding_drift"})

    return {
        "status": "stable" if not issues else "drifted",
        "issues": issues,
        "source_refs": {
            "n4_artifact": N4_PATH,
            "n4_artifact_sha256": n4_file_sha,
            "fork_b_census": FORK_B_PATH,
            "n8_contract": N8_PATH,
            "n10a_census": N10A_CENSUS_PATH,
            "n10a_smoke_problem": N10A_SMOKE_PATH,
            "n10a_cycle_trace": N10A_TRACE_PATH,
            "composition_contract": COMPOSITION_PATH,
        },
        "census_ref": census_ref,
        "n8_fork_b_ref": {
            "content_hash": n8_fork_b_ref.get("content_hash"),
            "raw_full_table_content_hash": n8_fork_b_ref.get(
                "raw_full_table_content_hash"
            ),
            "usable_certified_relations": n8_fork_b_ref.get(
                "usable_certified_relations"
            ),
        },
        "first_vertical_refs": {
            "n8_design_problem_ref": n8_problem_ref,
            "n4_generation_design_problem_refs": n4_problem_refs,
            "semantic_projection_hash": semantic_projection_hash,
            "n10a_comparator_hash": n10a_comparator_hash,
        },
        "design_problem_refs": design_problem_refs,
        "prompt_hashes": prompt_hashes,
        "composition_ref": {
            "status": composition_status,
            "n10a_census_content_hash": n10a_census_hash,
            "observed_census_content_hashes": observed_composition_census_hashes,
        },
    }


def build_live_payload(repo_root: Path, *, lane: str = "lane0") -> dict[str, Any]:
    """Build the honest pre-proof Task-12 payload from frozen owner evidence.

    Args:
        repo_root: Policy Engine checkout root.
        lane: The cheap Stage-4 scaffold lane. Only ``lane0`` is admitted before
            Task 13 captures the proof runs.

    Returns:
        A content-bound payload explicitly marked ``proof_runs_pending``.

    Raises:
        UniversalityContractError: If the entry graph drifted or a proof lane
            is requested before its owner runs exist.
    """

    root = repo_root.resolve()
    if lane != "lane0":
        raise UniversalityContractError("proof_lane_unavailable_before_task13")
    stability = check_provenance_stability(root)
    if stability.get("status") != "stable":
        raise UniversalityContractError("provenance_stability_failed")

    n8 = _read_json(root / N8_PATH)
    census = _read_json(root / FORK_B_PATH)
    composition = _read_json(root / COMPOSITION_PATH)
    denominators = _mapping(n8.get("denominators"))
    families = _strings(denominators.get("native_contract_families"))
    education = _mapping(n8.get("education_refusal"))
    production = _mapping(n8.get("production_refusal"))
    recursive_run = _mappings(composition.get("recursive_runs"))[0]
    joint_receipts = _joint_simulation_receipts(recursive_run)

    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "rule_version": RULE_VERSION,
        "producer": PRODUCER,
        "proof_status": "proof_runs_pending",
        "capability_reality": {
            "producer": "producer_missing",
            "artifact": "artifact_missing",
            "semantic_test": "semantic_test_missing",
        },
        "content_hash_excluded_fields": ["runtime_metrics"],
        "source_refs": stability["source_refs"],
        "provenance_stability": stability,
        "domain_runs": {},
        "non_panel_evidence": {
            "fork": str(census.get("fork") or ""),
            "status": "acquisition_required",
            "native_contract_families": families,
            "supported_native_families": len(families),
            "fork_a_candidate_count": len(
                census.get("fork_a_evidence_candidate_refs") or []
            ),
            "census_content_hash": census.get("content_hash"),
            "raw_census_content_hash": census.get(
                "raw_full_table_content_hash"
            ),
            "first_vertical_terminal": {
                "status": production.get("status"),
                "authority_blockers": list(
                    production.get("authority_blockers") or []
                ),
                "decision_grade": production.get("decision_grade"),
                "acquisition_requirement": production.get(
                    "acquisition_requirement"
                ),
                "receipt_content_hash": production.get("content_hash"),
            },
        },
        "education_refusal": {
            "status": education.get("status"),
            "authority_blockers": list(education.get("authority_blockers") or []),
            "decision_grade": education.get("decision_grade"),
            "selected_method_fqn": education.get("selected_method_fqn"),
            "selection_receipt_content_hash": _mapping(
                education.get("method_selection_receipt")
            ).get("content_hash"),
            "receipt_content_hash": education.get("content_hash"),
        },
        "depth_evidence": {
            "authority_scope": recursive_run.get("authority_scope"),
            "controller_ref": recursive_run.get("controller_ref"),
            "observed_max_depth": recursive_run.get("observed_max_depth"),
            "recursive_run_content_hash": recursive_run.get("content_hash"),
            "recursive_graph_ref": recursive_run.get("recursive_graph_ref"),
            "recursive_graph_content_hash": recursive_run.get(
                "recursive_graph_content_hash"
            ),
            "joint_simulation_receipts": joint_receipts,
            "composition_receipts": [
                {
                    "receipt_id": item.get("receipt_id"),
                    "receipt_ref": item.get("receipt_ref"),
                }
                for item in _mappings(composition.get("composition_receipts"))
            ],
        },
        "gy_g_strangle_receipt": copy.deepcopy(
            _mapping(composition.get("depth_n_strangle_receipt"))
        ),
        "pattern_pass": {
            "P27": "canonical_owners_aggregated_no_parallel_cycle",
            "P29": "proof_runs_pending_not_self_attested",
            "P31": "single_validator_intake_for_capstone_evidence",
            "P32": "resolve_content_bind_and_validate_before_projection",
        },
        "runtime_metrics": {"lane": lane},
    }
    payload["contract_content_hash"] = _contract_content_hash(payload)
    return payload


def validate_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Validate Task-12 honesty and content integrity.

    Args:
        payload: Universality contract payload.

    Returns:
        Structured validation status and issues.
    """

    issues: list[dict[str, Any]] = []
    if payload.get("schema_version") != SCHEMA_VERSION:
        issues.append({"code": "schema_version_mismatch"})
    if payload.get("rule_version") != RULE_VERSION:
        issues.append({"code": "rule_version_mismatch"})
    if payload.get("contract_content_hash") != _contract_content_hash(payload):
        issues.append({"code": "contract_content_hash_mismatch"})

    proof_status = payload.get("proof_status")
    domain_runs = payload.get("domain_runs")
    if proof_status == "proof_runs_pending":
        if domain_runs != {}:
            issues.append({"code": "pending_proof_contains_domain_runs"})
        expected_reality = {
            "producer": "producer_missing",
            "artifact": "artifact_missing",
            "semantic_test": "semantic_test_missing",
        }
        if payload.get("capability_reality") != expected_reality:
            issues.append({"code": "pending_capability_reality_drift"})
    elif proof_status == "complete":
        if set(domain_runs or {}) != {"first_vertical", "education", "unseen"}:
            issues.append({"code": "complete_proof_domain_denominator_missing"})
    else:
        issues.append({"code": "proof_status_invalid"})

    stability = _mapping(payload.get("provenance_stability"))
    if stability.get("status") != "stable" or stability.get("issues") != []:
        issues.append({"code": "provenance_stability_not_green"})
    non_panel = _mapping(payload.get("non_panel_evidence"))
    families = _strings(non_panel.get("native_contract_families"))
    if (
        non_panel.get("fork") != "B"
        or non_panel.get("status") != "acquisition_required"
        or int(non_panel.get("fork_a_candidate_count") or 0) != 0
        or non_panel.get("supported_native_families") != len(families)
        or not families
    ):
        issues.append({"code": "fork_b_evidence_invalid"})
    education = _mapping(payload.get("education_refusal"))
    if (
        education.get("status") != "value_blocked"
        or education.get("authority_blockers")
        != ["method_estimand_binding_mismatch"]
    ):
        issues.append({"code": "education_refusal_invalid"})
    depth = _mapping(payload.get("depth_evidence"))
    if int(depth.get("observed_max_depth") or 0) <= 2:
        issues.append({"code": "depth_n_evidence_missing"})
    strangle = _mapping(payload.get("gy_g_strangle_receipt"))
    if (
        strangle.get("status") != "strangled"
        or strangle.get("production_fixture_callers") != []
    ):
        issues.append({"code": "gy_g_strangle_receipt_invalid"})
    for path in _volatile_content_paths(payload):
        issues.append({"code": "volatile_content_field", "path": path})

    return {
        "status": "pass" if not issues else "fail",
        "issues": issues,
        "outputs": declared_outputs(),
    }


def write_payload(repo_root: Path, output_path: Path) -> bytes:
    """Write a byte-stable Task-12 payload to a noncanonical test path.

    Args:
        repo_root: Policy Engine checkout root.
        output_path: Explicit destination. The canonical Task-13 path is fenced
            while proof runs are pending.

    Returns:
        Exact bytes written.

    Raises:
        UniversalityContractError: If asked to freeze the incomplete payload as
            the canonical proof artifact.
    """

    root = repo_root.resolve()
    if output_path.resolve() == (root / OUTPUT_PATH).resolve():
        raise UniversalityContractError("proof_runs_pending")
    payload = build_live_payload(root, lane="lane0")
    data = (_canonical_json(payload) + "\n").encode("utf-8")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(data)
    return data


def corrupt_field_drift_check(repo_root: Path) -> dict[str, Any]:
    """Corrupt one semantic field and require the hash verifier to reject it."""

    payload = build_live_payload(repo_root, lane="lane0")
    payload["proof_status"] = "complete"
    report = validate_payload(payload)
    detected = any(
        issue.get("code") == "contract_content_hash_mismatch"
        for issue in report["issues"]
    )
    return {
        "status": "fail" if detected else "pass",
        "issues": report["issues"] if detected else [
            {"code": "corrupt_field_drift_not_detected"}
        ],
        "expected_exit": 1,
    }


def _check_canonical(repo_root: Path) -> dict[str, Any]:
    stability = check_provenance_stability(repo_root)
    if stability.get("status") != "stable":
        return {"status": "fail", "issues": stability.get("issues", [])}
    path = repo_root / OUTPUT_PATH
    if not path.is_file():
        return {
            "status": "fail",
            "issues": [{"code": "universality_contract_artifact_missing"}],
        }
    payload = _read_json(path)
    report = validate_payload(payload)
    if payload.get("proof_status") != "complete":
        report["issues"].append({"code": "proof_runs_pending"})
        report["status"] = "fail"
    return report


def _rederive_audit(repo_root: Path) -> dict[str, Any]:
    stability = check_provenance_stability(repo_root)
    if stability.get("status") != "stable":
        return {"status": "fail", "issues": stability.get("issues", [])}
    path = repo_root / OUTPUT_PATH
    if not path.is_file():
        return {
            "status": "fail",
            "issues": [{"code": "universality_contract_artifact_missing"}],
        }
    live = build_live_payload(repo_root, lane="lane0")
    committed = _read_json(path)
    issues = list(validate_payload(committed)["issues"])
    if committed != live:
        issues.append({"code": "universality_contract_rederive_drift"})
    return {"status": "pass" if not issues else "fail", "issues": issues}


def _main_report(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    if args.corrupt_field_drift_check:
        report = corrupt_field_drift_check(REPO_ROOT)
        return report, 1 if report["status"] == "fail" else 0
    if args.source_flip_mutations:
        return {
            "status": "fail",
            "issues": [{"code": "source_flip_mutations_pending"}],
        }, 1
    if args.rederive_audit:
        report = _rederive_audit(REPO_ROOT)
        return report, 0 if report["status"] == "pass" else 1
    if args.write:
        stability = check_provenance_stability(REPO_ROOT)
        if stability.get("status") != "stable":
            return {"status": "fail", "issues": stability.get("issues", [])}, 1
        return {
            "status": "fail",
            "issues": [{"code": "proof_runs_pending"}],
        }, 1
    report = _check_canonical(REPO_ROOT)
    return report, 0 if report["status"] == "pass" else 1


def main(argv: Sequence[str] | None = None) -> int:
    """Run one universality validator mode after the mandatory preflight."""

    started = time.monotonic()
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--check", action="store_true")
    modes.add_argument("--corrupt-field-drift-check", action="store_true")
    modes.add_argument("--rederive-audit", action="store_true")
    modes.add_argument("--source-flip-mutations", action="store_true")
    modes.add_argument("--write", action="store_true")
    parser.add_argument("--output-format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)
    report, exit_code = _main_report(args)
    report["wall_time_seconds"] = round(max(0.0, time.monotonic() - started), 6)
    if args.output_format == "json":
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(json.dumps(report, sort_keys=True))
    return exit_code


def _dirty_upstream_paths(repo_root: Path) -> list[str]:
    result = subprocess.run(
        ["git", "status", "--porcelain=v1", "--", *_UPSTREAM_PATHS],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise UniversalityContractError(
            "upstream_dirty_census_failed:" + result.stderr.strip()
        )
    return sorted(
        line[3:].strip()
        for line in result.stdout.splitlines()
        if line.strip()
    )


def _extend_owner_issues(
    target: list[dict[str, Any]],
    owner: str,
    owner_issues: object,
) -> None:
    for issue in owner_issues or ():
        if isinstance(issue, Mapping):
            target.append(
                {
                    "code": f"{owner}_owner_validation_failed",
                    "owner_issue": dict(issue),
                }
            )
        else:
            target.append(
                {"code": f"{owner}_owner_validation_failed", "owner_issue": issue}
            )


def _joint_simulation_receipts(recursive_run: Mapping[str, Any]) -> list[dict[str, Any]]:
    receipts: list[dict[str, Any]] = []
    for node in _mappings(recursive_run.get("nodes")):
        simulation = _mapping(node.get("joint_simulation"))
        receipt = _mapping(simulation.get("receipt"))
        if not receipt:
            continue
        receipts.append(
            {
                "node_ref": node.get("node_ref"),
                "receipt_id": receipt.get("receipt_id"),
                "payload_hash": receipt.get("payload_hash"),
                "uncertainty_kind": receipt.get("uncertainty_kind"),
                "interaction_term_count": len(
                    simulation.get("interaction_terms") or []
                ),
            }
        )
    return receipts


def _contract_content_hash(payload: Mapping[str, Any]) -> str:
    stable = {
        key: value
        for key, value in payload.items()
        if key not in _CONTENT_HASH_EXCLUDED_TOP_LEVEL
    }
    return "sha256:" + hashlib.sha256(
        _canonical_json(stable).encode("utf-8")
    ).hexdigest()


def _volatile_content_paths(value: object, path: str = "$") -> list[str]:
    paths: list[str] = []
    if isinstance(value, Mapping):
        for key, item in value.items():
            child_path = f"{path}.{key}"
            if path == "$" and key == "runtime_metrics":
                continue
            lowered = str(key).lower()
            if any(
                token in lowered
                for token in ("timestamp", "wall_time", "elapsed", "generated_at")
            ):
                paths.append(child_path)
            paths.extend(_volatile_content_paths(item, child_path))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            paths.extend(_volatile_content_paths(item, f"{path}[{index}]"))
    return paths


def _values_for_key(value: object, target_key: str) -> list[str]:
    values: list[str] = []
    if isinstance(value, Mapping):
        for key, item in value.items():
            if key == target_key and isinstance(item, str):
                values.append(item)
            values.extend(_values_for_key(item, target_key))
    elif isinstance(value, list):
        for item in value:
            values.extend(_values_for_key(item, target_key))
    return values


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise UniversalityContractError(f"json_object_required:{path.name}")
    return payload


def _file_sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True)


def _mapping(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _mappings(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, Mapping)]


def _strings(value: object) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    return [str(item) for item in value]


if __name__ == "__main__":
    raise SystemExit(main())
