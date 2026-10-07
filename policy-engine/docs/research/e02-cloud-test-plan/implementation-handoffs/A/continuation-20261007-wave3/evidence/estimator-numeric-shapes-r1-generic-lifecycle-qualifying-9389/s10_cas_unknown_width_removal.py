"""R1 removal probe for S10 diagnostic-only unknown-versus-zero width semantics."""
from __future__ import annotations

import hashlib
import inspect
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
    "tests/unit/runtime/quality/test_e02_estimator_numeric_shapes.py::"
    "test_s10_cas_readback_preserves_unknown_vs_zero_diagnostics_and_limitation"
)
_OUTPUT_ENV = "POLISYOS_S10_CAS_UNKNOWN_WIDTH_REMOVAL_EVIDENCE_PATH"
_CALLS: list[dict[str, Any]] = []
_REPORTS: list[dict[str, Any]] = []
_FAILURE_LOCALS: dict[str, Any] | None = None
_FAILURE_TRACEBACK: list[dict[str, Any]] = []
_FAILURE_CAPTURE_ERROR: str | None = None
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


def _shape(evidence: dict[str, Any]) -> dict[str, Any]:
    value = evidence.get("estimator_shape_diagnostics")
    return dict(value) if isinstance(value, dict) else {}


def _evidence_markers(evidence: dict[str, Any]) -> dict[str, Any]:
    shape = _shape(evidence)
    return {
        "forecast_tier": evidence.get("forecast_tier"),
        "calibration_status": evidence.get("calibration_status"),
        "denominator": evidence.get("denominator"),
        "numerator": evidence.get("numerator"),
        "pass_rate": evidence.get("pass_rate"),
        "interval_coverage_metric": evidence.get("interval_coverage_metric"),
        "calibration_error_metric": evidence.get("calibration_error_metric"),
        "counterfactual_credibility": evidence.get("counterfactual_credibility"),
        "false_clear_counts": evidence.get("false_clear_counts"),
        "finite_point": shape.get("finite_point"),
        "point_value_status": shape.get("point_value_status"),
        "finite_interval": shape.get("finite_interval"),
        "relative_interval_width": shape.get("relative_interval_width"),
        "ci_width": evidence.get("ci_width"),
    }


def _point_value(report: object) -> Any:
    if isinstance(report, dict):
        return report.get("point_estimate")
    return getattr(report, "point_estimate", None)


def _path_value(root: object, *path: str) -> Any:
    value = root
    for key in path:
        if isinstance(value, dict):
            value = value.get(key)
        else:
            value = getattr(value, key, None)
        if value is None:
            break
    return value


def _as_text(value: object | None) -> str | None:
    """Serialize typed artifact identifiers without losing their exact display value."""
    return None if value is None else str(value)


def _caller_snapshot(report: object) -> dict[str, Any]:
    frame = inspect.currentframe()
    caller = frame.f_back if frame is not None else None
    caller = caller.f_back if caller is not None else None
    if caller is None:
        return {"available": False}
    local = caller.f_locals
    line = caller.f_lineno
    snapshot: dict[str, Any] = {
        "available": True,
        "function": caller.f_code.co_name,
        "line": line,
        "report_type": type(report).__name__,
        "label": local.get("label"),
        "point_estimate": _point_value(report),
    }
    if line == 240:  # Fresh report reconstructed only after CAS verify/get.
        ref = local.get("ref")
        loaded = local.get("loaded")
        snapshot["phase"] = "fresh_cas_readback"
        snapshot["storage_ref_id"] = _as_text(getattr(ref, "artifact_id", None))
        snapshot["storage_ref_content_hash"] = _as_text(
            getattr(ref, "content_hash", None)
        )
        snapshot["loaded_bytes_length"] = len(local.get("loaded_bytes", b""))
        if isinstance(loaded, dict):
            snapshot["stored_relative_interval_width"] = _path_value(
                loaded,
                "estimator_calibration_evidence",
                "estimator_shape_diagnostics",
                "relative_interval_width",
            )
            snapshot["stored_point_value_status"] = _path_value(
                loaded,
                "estimator_calibration_evidence",
                "estimator_shape_diagnostics",
                "point_value_status",
            )
    elif line == 202:
        snapshot["phase"] = "pre_persist"
    else:
        snapshot["phase"] = "other_callsite"
    return snapshot


def _patch_unknown_width(report: object) -> dict[str, object]:
    original = _ORIGINAL(report)
    original_evidence = dict(original)
    output: dict[str, object] = original_evidence
    point = _point_value(report)
    original_shape = _shape(original_evidence)
    changed_paths: list[str] = []
    if point is None and original_shape.get("finite_interval") is True:
        updated_shape = dict(original_shape)
        updated_shape["relative_interval_width"] = 0.5
        output = dict(original_evidence)
        output["estimator_shape_diagnostics"] = updated_shape
        changed_paths.append("estimator_shape_diagnostics.relative_interval_width")
    output_shape = _shape(output)
    restored_shape = dict(output_shape)
    restored_shape["relative_interval_width"] = original_shape.get("relative_interval_width")
    restored = dict(output)
    restored["estimator_shape_diagnostics"] = restored_shape
    markers_unchanged = restored == original_evidence
    caller = _caller_snapshot(report)
    _CALLS.append(
        {
            "index": len(_CALLS),
            "point_estimate": point,
            "point_estimate_type": type(point).__name__ if point is not None else "NoneType",
            "original_helper_called_once": True,
            "original_markers": _evidence_markers(original_evidence),
            "returned_markers": _evidence_markers(output),
            "changed_paths": changed_paths,
            "all_other_evidence_markers_unchanged": markers_unchanged,
            "caller": caller,
        }
    )
    return output


def pytest_configure(config: pytest.Config) -> None:
    global _ORIGINAL
    from polisyos.runtime.quality import generation_cycle

    _ORIGINAL = generation_cycle._s10_calibration_evidence_from_report  # noqa: SLF001
    generation_cycle._s10_calibration_evidence_from_report = _patch_unknown_width  # noqa: SLF001


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


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo[Any]):
    global _FAILURE_CAPTURE_ERROR, _FAILURE_LOCALS
    outcome = yield
    report = outcome.get_result()
    if item.nodeid != _TARGET_NODEID or call.when != "call" or call.excinfo is None:
        return
    for entry in call.excinfo.traceback:
        try:
            frame = entry.frame
            frame_name = getattr(getattr(frame, "code", None), "name", None)
            if frame_name is None:
                raw_frame = getattr(frame, "raw", None)
                frame_name = getattr(getattr(raw_frame, "f_code", None), "co_name", None)
            if frame_name != "test_s10_cas_readback_preserves_unknown_vs_zero_diagnostics_and_limitation":
                continue
            local = frame.f_locals
            cases = local.get("cases")
            if not isinstance(cases, dict):
                continue
            snapshots: dict[str, Any] = {}
            for label in ("unknown", "zero"):
                case = cases.get(label)
                if not isinstance(case, dict):
                    continue
                stored = case.get("stored_evidence")
                evidence = case.get("evidence")
                stored = stored if isinstance(stored, dict) else {}
                evidence = evidence if isinstance(evidence, dict) else {}
                support = case.get("support")
                receipt = case.get("receipt")
                snapshots[label] = {
                    "stored_markers": _evidence_markers(stored),
                    "recomputed_markers": _evidence_markers(evidence),
                    "forecast_tier": _as_text(getattr(support, "forecast_tier", None)),
                    "limitation_refs": [
                        _as_text(value)
                        for value in getattr(support, "s6_limitation_refs", ())
                    ],
                    "calibration_is_none": case.get("calibration") is None,
                    "receipt_status": _as_text(getattr(receipt, "status", None)),
                    "artifact_refs_present_in_case": [
                        key for key in case if "ref" in key.lower()
                    ],
                }
            unknown = snapshots.get("unknown", {})
            zero = snapshots.get("zero", {})
            _FAILURE_LOCALS = {
                "case_snapshots": snapshots,
                "store_root": str(local.get("store_root")) if local.get("store_root") is not None else None,
                "store_type": type(local.get("store")).__name__ if local.get("store") is not None else None,
                "read_store_type": type(local.get("read_store")).__name__ if local.get("read_store") is not None else None,
                "last_loop_storage_ref_id": _as_text(
                    getattr(local.get("ref"), "artifact_id", None)
                ),
                "unknown_and_zero_cases_present": set(snapshots) == {"unknown", "zero"},
                "both_receipts_blocked": (
                    unknown.get("receipt_status") == "blocked"
                    and zero.get("receipt_status") == "blocked"
                ),
                "both_forecasts_blocked": (
                    unknown.get("forecast_tier") == "blocked"
                    and zero.get("forecast_tier") == "blocked"
                ),
                "both_calibration_records_absent": (
                    unknown.get("calibration_is_none") is True
                    and zero.get("calibration_is_none") is True
                ),
                "both_s10_limitation_refs_present": all(
                    "s10://calibration/fail-closed/insufficient-history"
                    in snapshots.get(label, {}).get("limitation_refs", ())
                    for label in ("unknown", "zero")
                ),
            }
            _FAILURE_TRACEBACK.append(
                {
                    "test_frame_line_1based": entry.lineno + 1,
                    "statement": str(getattr(entry, "statement", "")),
                }
            )
            return
        except Exception as exc:  # Preserve the test report; make capture failure explicit.
            _FAILURE_CAPTURE_ERROR = f"{type(exc).__name__}: {exc}"
            return


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    source_path = _POLICY_ENGINE / "src/polisyos/runtime/quality/generation_cycle.py"
    source_sha = hashlib.sha256(source_path.read_bytes()).hexdigest()
    plugin_sha = hashlib.sha256(_PLUGIN_PATH.read_bytes()).hexdigest()
    call_phase = next(
        (report for report in _REPORTS if report["when"] == "call"), None
    )
    longrepr = (call_phase or {}).get("longrepr") or ""
    unknown = (_FAILURE_LOCALS or {}).get("case_snapshots", {}).get("unknown", {})
    zero = (_FAILURE_LOCALS or {}).get("case_snapshots", {}).get("zero", {})
    unknown_calls = [
        row for row in _CALLS
        if row["point_estimate"] is None
        and row["original_markers"].get("finite_interval") is True
    ]
    zero_calls = [
        row for row in _CALLS
        if row["point_estimate_type"] == "float"
        and row["point_estimate"] == 0.0
        and row["original_markers"].get("finite_interval") is True
    ]
    all_calls_are_target_shapes = bool(
        _CALLS
        and all(
            row["original_markers"].get("finite_interval") is True
            and (
                row["point_estimate"] is None
                or (
                    row["point_estimate_type"] == "float"
                    and row["point_estimate"] == 0.0
                )
            )
            for row in _CALLS
        )
    )
    lifecycle_coverage = {
        f"{label}_{phase}": any(
            row["caller"].get("label") == label
            and row["caller"].get("phase") == phase
            and row["point_estimate"] == expected_point
            and row["original_markers"].get("finite_interval") is True
            for row in _CALLS
        )
        for label, expected_point in (("unknown", None), ("zero", 0.0))
        for phase in ("pre_persist", "fresh_cas_readback")
    }
    lifecycle_coverage_valid = all(lifecycle_coverage.values())
    readback_refs = [
        row["caller"] for row in _CALLS
        if row["caller"].get("phase") == "fresh_cas_readback"
    ]
    readback_by_label = {
        label: next((row for row in readback_refs if row.get("label") == label), None)
        for label in ("unknown", "zero")
    }
    distinct_readback_refs = [
        readback_by_label[label] for label in ("unknown", "zero")
        if readback_by_label[label] is not None
    ]
    actual_readbacks_valid = bool(
        lifecycle_coverage_valid
        and len(distinct_readback_refs) == 2
        and all(row.get("storage_ref_id") for row in distinct_readback_refs)
        and len({row.get("storage_ref_id") for row in distinct_readback_refs}) == 2
        and all(row.get("loaded_bytes_length", 0) > 0 for row in distinct_readback_refs)
        and all(row.get("stored_relative_interval_width") == 0.5 for row in distinct_readback_refs)
        and all(
            row.get("stored_point_value_status")
            == ("missing" if label == "unknown" else "known")
            for label, row in readback_by_label.items()
            if row is not None
        )
    )
    original_unknown_none_at_all_stages = bool(
        len(unknown_calls) >= 2
        and lifecycle_coverage_valid
        and all(
            row["original_markers"]["relative_interval_width"] is None
            and row["returned_markers"]["relative_interval_width"] == 0.5
            and row["original_markers"]["finite_point"] is False
            and row["returned_markers"]["finite_point"] is False
            and row["returned_markers"]["point_value_status"] == "missing"
            and row["all_other_evidence_markers_unchanged"] is True
            for row in unknown_calls
        )
    )
    explicit_zero_unchanged_at_all_stages = bool(
        len(zero_calls) >= 2
        and lifecycle_coverage_valid
        and all(
            row["original_markers"]["relative_interval_width"] == 0.5
            and row["returned_markers"]["relative_interval_width"] == 0.5
            and row["all_other_evidence_markers_unchanged"] is True
            and row["changed_paths"] == []
            for row in zero_calls
        )
    )
    expected_assertion_failure = bool(
        call_phase is not None
        and call_phase["outcome"] == "failed"
        and "is None" in longrepr
        and "relative_interval_width" in longrepr
        and "0.5" in longrepr
        and _FAILURE_TRACEBACK
        and 257 <= _FAILURE_TRACEBACK[-1]["test_frame_line_1based"] <= 259
    )
    cas_readback_and_blocked_consumer = bool(
        all_calls_are_target_shapes
        and lifecycle_coverage_valid
        and all(
            row.get("storage_ref_id") and row.get("loaded_bytes_length", 0) > 0
            for row in distinct_readback_refs
        )
        and (_FAILURE_LOCALS or {}).get("unknown_and_zero_cases_present") is True
        and (_FAILURE_LOCALS or {}).get("both_receipts_blocked") is True
        and (_FAILURE_LOCALS or {}).get("both_forecasts_blocked") is True
        and (_FAILURE_LOCALS or {}).get("both_calibration_records_absent") is True
        and (_FAILURE_LOCALS or {}).get("both_s10_limitation_refs_present") is True
        and actual_readbacks_valid
        and unknown.get("stored_markers", {}).get("relative_interval_width") == 0.5
        and zero.get("stored_markers", {}).get("relative_interval_width") == 0.5
    )
    intended_witness = bool(
        all_calls_are_target_shapes
        and lifecycle_coverage_valid
        and original_unknown_none_at_all_stages
        and explicit_zero_unchanged_at_all_stages
        and expected_assertion_failure
        and cas_readback_and_blocked_consumer
    )
    output_env = os.environ.get(_OUTPUT_ENV)
    output_path = Path(output_env).expanduser() if output_env else _PLUGIN_PATH.with_name(
        "r1_evidence.json"
    )
    evidence = {
        "schema": "policyos.e02.s10_cas_unknown_width_removal_r1.v1",
        "purpose": "diagnostic property-removal witness; never a product PASS",
        "created_at_utc": datetime.now(UTC).isoformat(),
        "target_nodeid": _TARGET_NODEID,
        "pytest_exitstatus": int(exitstatus),
        "head": _git("rev-parse", "HEAD"),
        "head_tree": _git("rev-parse", "HEAD^{tree}"),
        "source_path": str(source_path),
        "source_sha256": source_sha,
        "source_git_blob": _git(
            "rev-parse", "HEAD:policy-engine/src/polisyos/runtime/quality/generation_cycle.py"
        ),
        "plugin_path": str(_PLUGIN_PATH),
        "plugin_sha256": plugin_sha,
        "output_path_env": _OUTPUT_ENV,
        "output_path_was_explicit": bool(output_env),
        "target_reports": _REPORTS,
        "helper_calls": _CALLS,
        "failure_traceback": _FAILURE_TRACEBACK,
        "failure_locals": _FAILURE_LOCALS,
        "failure_capture_error": _FAILURE_CAPTURE_ERROR,
        "call_count": len(_CALLS),
        "call_counts_by_input": {
            "unknown_missing_point_finite_interval": len(unknown_calls),
            "explicit_zero_finite_interval": len(zero_calls),
        },
        "all_calls_are_target_shapes": all_calls_are_target_shapes,
        "lifecycle_coverage": lifecycle_coverage,
        "lifecycle_coverage_valid": lifecycle_coverage_valid,
        "actual_distinct_cas_readbacks_valid": actual_readbacks_valid,
        "original_unknown_width_none_before_and_after_cas": original_unknown_none_at_all_stages,
        "explicit_zero_width_unchanged_before_and_after_cas": explicit_zero_unchanged_at_all_stages,
        "cas_readback_and_blocked_consumer_observed": cas_readback_and_blocked_consumer,
        "expected_unknown_stored_width_assertion_failure": expected_assertion_failure,
        "verdict": "EXPECTED_FALSIFIER" if intended_witness else "HARNESS_ERROR_OR_UNEXPECTED_RESULT",
        "interpretation": (
            "The probe changes only diagnostic relative_interval_width for missing point estimate "
            "with finite CI, reproducing the old proxy value 0.5. It keeps finite_point=false, "
            "point_value_status=missing, blocked forecast, absent empirical coverage/calibration, "
            "and the S10 limitation. EXPECTED_FALSIFIER requires the real CAS persist/verify/get "
            "and blocked consumers for unknown and explicit zero, followed by failure at the stored "
            "unknown-width-is-None assertion. This does not establish S10 or B18/B31 closure."
        ),
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
