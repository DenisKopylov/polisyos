"""R1 removal probe for partial V2's uncomposed-parent terminal fold."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

_PLUGIN_PATH = Path(__file__).resolve()
_POLICY_ENGINE = _PLUGIN_PATH.parents[3]
_REPO_ROOT = _POLICY_ENGINE.parent
_TARGET_NODEID = (
    "tests/integration/runtime_quality/test_e02_recursive_budget_frontier.py::"
    "test_partial_v2_rejects_self_asserted_internal_parent_terminal"
)
_OUTPUT_ENV = "POLISYOS_PARTIAL_V2_REMOVAL_EVIDENCE_PATH"
_CALLS: list[dict[str, Any]] = []
_REPORTS: list[dict[str, Any]] = []


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


def _terminal_fields(terminal: object) -> dict[str, Any]:
    kind = getattr(terminal, "kind", None)
    return {
        "kind": getattr(kind, "value", str(kind) if kind is not None else None),
        "blocking_obligations": list(getattr(terminal, "blocking_obligations", ())),
        "budget_kind": getattr(terminal, "budget_kind", None),
        "costed_plan_present": getattr(terminal, "costed_plan", None) is not None,
        "data_need_spec_present": getattr(terminal, "data_need_spec", None) is not None,
    }


def _return_terminal_unchanged(terminal: object) -> object:
    """Remove the owner-derived fold check while preserving the typed input."""
    fields = _terminal_fields(terminal)
    _CALLS.append(
        {
            "argument_type": _qualified_type(terminal),
            "input": fields,
            "returned_same_object": True,
            "output": fields,
        }
    )
    # Intentionally do not synthesize, alter, or validate the terminal here.
    return terminal


def pytest_configure(config: pytest.Config) -> None:
    from polisyos.runtime.quality import recursive_generation_cycle

    recursive_generation_cycle._fold_uncomposed_partial_parent_terminal = (  # noqa: SLF001
        _return_terminal_unchanged
    )


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
    source_path = _POLICY_ENGINE / "src/polisyos/runtime/quality/recursive_generation_cycle.py"
    source_sha = hashlib.sha256(source_path.read_bytes()).hexdigest()
    plugin_sha = hashlib.sha256(_PLUGIN_PATH.read_bytes()).hexdigest()
    call_phase = next(
        (report for report in _REPORTS if report["when"] == "call"), None
    )
    longrepr = (call_phase or {}).get("longrepr") or ""
    expected_falsifier_report = bool(
        call_phase is not None
        and call_phase["outcome"] == "failed"
        and "DID NOT RAISE" in longrepr
        and "ValidationError" in longrepr
    )
    canonical_positive = bool(
        len(_CALLS) >= 1
        and _CALLS[0]["input"]["kind"] == "recursive_blocked"
        and _CALLS[0]["input"]["blocking_obligations"]
        and _CALLS[0]["input"]["budget_kind"] is None
        and not _CALLS[0]["input"]["costed_plan_present"]
        and not _CALLS[0]["input"]["data_need_spec_present"]
        and _CALLS[0]["returned_same_object"]
    )
    forged_grounded_abstention = bool(
        len(_CALLS) >= 2
        and _CALLS[1]["input"]["kind"] == "grounded_abstention"
        and _CALLS[1]["input"]["kind"] != "recursive_blocked"
        and _CALLS[1]["returned_same_object"]
    )
    intended_witness = bool(
        len(_CALLS) == 2
        and canonical_positive
        and forged_grounded_abstention
        and expected_falsifier_report
    )
    output_env = os.environ.get(_OUTPUT_ENV)
    output_path = Path(output_env).expanduser() if output_env else _PLUGIN_PATH.with_name(
        "r1_evidence.json"
    )
    evidence = {
        "schema": "policyos.e02.partial_v2_parent_terminal_removal_r1.v1",
        "purpose": "source-property-removal witness; never a product PASS",
        "created_at_utc": datetime.now(UTC).isoformat(),
        "target_nodeid": _TARGET_NODEID,
        "pytest_exitstatus": int(exitstatus),
        "head": _git("rev-parse", "HEAD"),
        "head_tree": _git("rev-parse", "HEAD^{tree}"),
        "source_path": str(source_path),
        "source_sha256": source_sha,
        "source_git_blob": _git(
            "rev-parse", "HEAD:policy-engine/src/polisyos/runtime/quality/recursive_generation_cycle.py"
        ),
        "plugin_path": str(_PLUGIN_PATH),
        "plugin_sha256": plugin_sha,
        "output_path_env": _OUTPUT_ENV,
        "output_path_was_explicit": bool(output_env),
        "target_reports": _REPORTS,
        "helper_calls": _CALLS,
        "canonical_positive_constructed_with_markers": canonical_positive,
        "forged_grounded_abstention_reached_helper": forged_grounded_abstention,
        "expected_did_not_raise_failure_observed": expected_falsifier_report,
        "verdict": "EXPECTED_FALSIFIER" if intended_witness else "HARNESS_ERROR_OR_UNEXPECTED_RESULT",
        "interpretation": (
            "The plugin returns each typed terminal unchanged after removing only the uncomposed "
            "parent fold. EXPECTED_FALSIFIER requires the canonical blocked parent to pass first, "
            "then a grounded-abstention parent with valid recomputed payload hash/schema/topology "
            "to reach the first pytest.raises and produce DID NOT RAISE. Other errors are not "
            "classified as the intended witness. This removal result is not a product PASS."
        ),
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
