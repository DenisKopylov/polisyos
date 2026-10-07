"""R1 pytest plugin removing only N8 candidate/problem binding at the real helper."""
from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

_PLUGIN_PATH = Path(__file__).resolve()
_POLICY_ENGINE = _PLUGIN_PATH.parents[3]
_REPO_ROOT = _POLICY_ENGINE.parent
_TARGET_NODEID = (
    "tests/unit/runtime/quality/test_value_gate.py::"
    "test_foundry_value_port_recomputes_actual_n5_outcome_and_atom_bindings"
)
_CALLS: list[dict[str, Any]] = []
_REPORTS: list[dict[str, Any]] = []
_ORIGINAL: Any = None


def _git(*args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=_REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return result.stdout.strip()


def _qualified_type(value: object) -> str:
    cls = type(value)
    return f"{cls.__module__}.{cls.__qualname__}"


def _problem_target(problem: object | None) -> str | None:
    if problem is None:
        return None
    outcome = getattr(problem, "outcome_of_interest", None)
    target = getattr(outcome, "target_variable", None)
    return str(target) if target is not None else None


def _artifact_ref_fields(value: object) -> dict[str, Any]:
    fields = ("artifact_id", "artifact_type", "content_hash", "schema_ref", "uri", "version")
    return {name: getattr(value, name, None) for name in fields}


def _without_candidate_problem_binding(
    simulation: object,
    *,
    artifact_store: object | None = None,
    candidate: object | None = None,
    problem: object | None = None,
) -> object | None:
    """Call the real resolver while omitting only its candidate/problem arguments."""
    record: dict[str, Any] = {
        "candidate_supplied": candidate is not None,
        "candidate_type": _qualified_type(candidate) if candidate is not None else None,
        "problem_supplied": problem is not None,
        "problem_target_variable": _problem_target(problem),
        "artifact_store_supplied": artifact_store is not None,
        "artifact_store_type": (
            _qualified_type(artifact_store) if artifact_store is not None else None
        ),
        "simulation_type": _qualified_type(simulation),
    }
    _CALLS.append(record)
    try:
        # Keep the real simulation, artifact store, CAS read, and validation path.
        # The property removal is exactly omission of candidate/problem binding.
        result = _ORIGINAL(simulation, artifact_store=artifact_store)
    except BaseException as exc:
        record["raised"] = {"type": _qualified_type(exc), "message": str(exc)}
        raise
    record["result_type"] = _qualified_type(result) if result is not None else None
    record["result_is_none"] = result is None
    if result is not None:
        record["artifact_ref"] = _artifact_ref_fields(result)
    return result


def pytest_configure(config: pytest.Config) -> None:
    global _ORIGINAL
    from polisyos.runtime.quality import generation_cycle

    _ORIGINAL = generation_cycle.simulation_evaluation_input_ref
    generation_cycle.simulation_evaluation_input_ref = _without_candidate_problem_binding


def pytest_runtest_logreport(report: pytest.TestReport) -> None:
    if report.nodeid != _TARGET_NODEID:
        return
    _REPORTS.append(
        {
            "nodeid": report.nodeid,
            "when": report.when,
            "outcome": report.outcome,
            "longrepr": str(report.longrepr) if report.longrepr is not None else None,
        }
    )


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    plugin_hash = hashlib.sha256(_PLUGIN_PATH.read_bytes()).hexdigest()
    source_path = _POLICY_ENGINE / "src/polisyos/runtime/quality/generation_cycle.py"
    source_sha = hashlib.sha256(source_path.read_bytes()).hexdigest()
    call_phase = next(
        (report for report in _REPORTS if report["when"] == "call"), None
    )
    longrepr = (call_phase or {}).get("longrepr") or ""
    # The intended falsifier is the first real assertion that expects the wrong
    # outcome to resolve to None. A setup/import/fixture failure is not a witness.
    expected_assertion = (
        call_phase is not None
        and call_phase["outcome"] == "failed"
        and "simulation_evaluation_input_ref" in longrepr
        and "is None" in longrepr
        and "wrong_outcome_problem" in longrepr
    )
    def is_real_ref_call(record: dict[str, Any], expected_target: str) -> bool:
        return bool(
            record.get("candidate_supplied") is True
            and record.get("problem_supplied") is True
            and record.get("problem_target_variable") == expected_target
            and record.get("artifact_store_supplied") is True
            and record.get("raised") is None
            and record.get("result_is_none") is False
            and record.get("artifact_ref", {}).get("content_hash")
        )

    # The fixture first builds the normal avg_income context through the same
    # helper. The target call is second and changes only the requested outcome.
    real_ref = bool(
        len(_CALLS) == 2
        and is_real_ref_call(_CALLS[0], "avg_income")
        and is_real_ref_call(_CALLS[1], "firm_survival")
    )
    evidence = {
        "schema": "policyos.e02.n8_binding_removal_r1.v1",
        "purpose": "source-property-removal witness; never a product PASS",
        "created_at_utc": datetime.now(UTC).isoformat(),
        "target_nodeid": _TARGET_NODEID,
        "pytest_exitstatus": int(exitstatus),
        "head": _git("rev-parse", "HEAD"),
        "head_tree": _git("rev-parse", "HEAD^{tree}"),
        "generation_cycle_path": str(source_path),
        "generation_cycle_sha256": source_sha,
        "generation_cycle_git_blob": _git(
            "rev-parse", "HEAD:policy-engine/src/polisyos/runtime/quality/generation_cycle.py"
        ),
        "plugin_path": str(_PLUGIN_PATH),
        "plugin_sha256": plugin_hash,
        "target_reports": _REPORTS,
        "real_helper_calls": _CALLS,
        "intended_assertion_failure_observed": expected_assertion,
        "real_artifact_ref_returned_under_removed_binding": real_ref,
        "verdict": (
            "EXPECTED_FALSIFIER"
            if expected_assertion and real_ref
            else "HARNESS_ERROR_OR_UNEXPECTED_RESULT"
        ),
        "interpretation": (
            "A failure at the consumer's wrong-outcome-is-None assertion, after the real helper "
            "returns a CAS-backed ArtifactRef with candidate/problem binding omitted, witnesses "
            "that the removed binding is behaviorally required. This is a removal probe, not "
            "evidence that the unmodified product passes."
        ),
    }
    output = _PLUGIN_PATH.with_name("r1_evidence.json")
    output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
