"""Owner for extracted DS11 trust-claim posture logic."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from polisyos.scientist.evidence.claims.posture import (
    AccessibilityEvidenceKind,
    AccessibilityPurpose,
    AdmittedSourceMember,
    ClaimPostureRow,
    ClaimPostureState,
    ClaimSourceBinding,
    EstablishmentClass,
    PageA11yFailureBinding,
    PageA11yReceiptBinding,
    SourceResolution,
)


@dataclass(frozen=True, slots=True)
class AccessibilityDependencies:
    """Bind this owner to the active facade collaborators."""

    admitted_is_dir: Callable[..., Any]
    admitted_is_file: Callable[..., Any]
    admitted_read_bytes: Callable[..., Any]
    reject_owner_predicate: Callable[..., Any]
    require_contained_path: Callable[..., Any]
    page_receipt_path: Path


from tools.quality.validation.trust_claim_posture_contracts import (
    AccessibilityEvaluation,
    ScopeEvaluation,
)


def _parse_accessibility_source_date(
    value: str, *, dependencies: AccessibilityDependencies
) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError:
        dependencies.reject_owner_predicate(
            "DS11-ACCESSIBILITY-CONTRACT",
            "accessibility_source_as_of_date",
            "accessibility source_as_of binding is not an ISO date",
        )


def derive_page_a11y_receipt(
    repo_root: Path, *, dependencies: AccessibilityDependencies
) -> PageA11yReceiptBinding:
    """Recompute the historical page-a11y receipt from its five admitted JSON files."""
    root = repo_root.resolve()
    receipt_root = (root / dependencies.page_receipt_path).resolve()
    expected = (
        Path("environment-after.json"),
        Path("environment-before.json"),
        Path("receipt.json"),
        Path("run-1/.last-run.json"),
        Path("run-1/results.json"),
    )
    dependencies.require_contained_path(
        receipt_root,
        root,
        code="DS11-PAGE-A11Y-RECEIPT-CONTRACT",
        stage="page_a11y_root_containment",
        label="page-a11y receipt source",
    )
    if not dependencies.admitted_is_dir(
        receipt_root,
        root,
        code="DS11-PAGE-A11Y-RECEIPT-CONTRACT",
        stage="page_a11y_root_presence",
        label="page-a11y receipt source",
    ):
        raise ValueError("page-a11y receipt source is missing")
    files = tuple((receipt_root / item).resolve() for item in expected)
    for item in files:
        dependencies.require_contained_path(
            item,
            receipt_root,
            code="DS11-PAGE-A11Y-RECEIPT-CONTRACT",
            stage="page_a11y_member_containment",
            label="page-a11y receipt member",
        )
    if any(
        not dependencies.admitted_is_file(
            item,
            receipt_root,
            code="DS11-PAGE-A11Y-RECEIPT-CONTRACT",
            stage="page_a11y_member_presence",
            label="page-a11y receipt member",
        )
        for item in files
    ):
        dependencies.reject_owner_predicate(
            "DS11-PAGE-A11Y-RECEIPT-CONTRACT",
            "page_a11y_member_completeness",
            "page-a11y receipt must contain all five admitted files",
        )
    raw_by_name = {
        name.as_posix(): dependencies.admitted_read_bytes(
            path,
            receipt_root,
            code="DS11-PAGE-A11Y-RECEIPT-CONTRACT",
            stage="page_a11y_member_read",
            label="page-a11y receipt member",
        )
        for name, path in zip(expected, files, strict=True)
    }
    admitted = tuple(
        AdmittedSourceMember(
            path=(dependencies.page_receipt_path / name).as_posix(),
            content_digest="sha256:" + hashlib.sha256(raw_by_name[name.as_posix()]).hexdigest(),
        )
        for name in expected
    )
    normalized = json.loads(raw_by_name["receipt.json"])
    if not isinstance(normalized, dict):
        dependencies.reject_owner_predicate(
            "DS11-PAGE-A11Y-RECEIPT-CONTRACT",
            "page_a11y_receipt_shape",
            "page-a11y receipt must be a JSON object",
        )
    expected_authority_metadata = {
        "schema_version": "policyos.ds11.page_a11y_base_receipt.v1",
        "authority_purpose": "historical_currentness_limitation",
        "status": "blocked",
        "execution_entry_commit": "8e5832bbdb0f206b6221112f4a1502b45981bd40",
        "policy_source_base_commit": "f935e0c2e9359bc1202ce5d36ea706de58f7aaab",
        "command": "PLAYWRIGHT_JSON_OUTPUT_FILE=<receipt-relative-output> corepack pnpm "
        "--filter @polisyos/runtime-dashboard exec playwright test e2e/a11y "
        "--project=chromium --reporter=json",
    }
    if {
        key: normalized.get(key) for key in expected_authority_metadata
    } != expected_authority_metadata:
        dependencies.reject_owner_predicate(
            "DS11-PAGE-A11Y-RECEIPT-CONTRACT",
            "page_a11y_authority_basis",
            "page-a11y authority/base/command metadata differs from the admitted basis",
        )
    results = json.loads(raw_by_name["run-1/results.json"])
    last_run = json.loads(raw_by_name["run-1/.last-run.json"])
    if not isinstance(results, dict) or not isinstance(last_run, dict):
        dependencies.reject_owner_predicate(
            "DS11-PAGE-A11Y-RECEIPT-CONTRACT",
            "page_a11y_result_shape",
            "page-a11y result files must be JSON objects",
        )
    for name in ("environment-before.json", "environment-after.json"):
        environment = json.loads(raw_by_name[name])
        if not isinstance(environment, dict) or not {
            "captured_at",
            "node",
            "platform",
            "arch",
            "cwd",
        } <= set(environment):
            dependencies.reject_owner_predicate(
                "DS11-PAGE-A11Y-RECEIPT-CONTRACT",
                "page_a11y_environment_shape",
                "page-a11y environment receipt is malformed",
            )
    suites = results.get("suites")
    stats = results.get("stats")
    if not isinstance(suites, list) or not isinstance(stats, dict):
        dependencies.reject_owner_predicate(
            "DS11-PAGE-A11Y-RECEIPT-CONTRACT",
            "page_a11y_results_shape",
            "page-a11y results require a suite list and stats object",
        )
    identities, failures = _derive_page_result_rows(suites, dependencies=dependencies)
    observed = {
        "collected": len(identities),
        "passed": sum(item[1] == "passed" for item in identities),
        "failed": sum(item[1] == "failed" for item in identities),
        "skipped": sum(item[1] == "skipped" for item in identities),
        "duration_ms": stats.get("duration"),
        "exit_code": 1 if failures else 0,
    }
    raw_authored_identities = normalized.get("collected_identities")
    raw_authored_failures = normalized.get("inherited_failure_identities")
    if (
        not isinstance(raw_authored_identities, list)
        or not isinstance(raw_authored_failures, list)
        or any(
            not isinstance(item, dict)
            or not isinstance(item.get("identity"), str)
            or not isinstance(item.get("status"), str)
            for item in (*raw_authored_identities, *raw_authored_failures)
        )
    ):
        dependencies.reject_owner_predicate(
            "DS11-PAGE-A11Y-RECEIPT-CONTRACT",
            "page_a11y_recorded_identity_shape",
            "page-a11y receipt identity rows are malformed",
        )
    authored_identities = tuple(
        (item["identity"], item["status"]) for item in raw_authored_identities
    )
    authored_failures = tuple((item["identity"], item["status"]) for item in raw_authored_failures)
    if normalized.get("result") != observed or authored_identities != identities:
        dependencies.reject_owner_predicate(
            "DS11-PAGE-A11Y-RECEIPT-CONTRACT",
            "page_a11y_result_identity",
            "page-a11y receipt result/identity differs from recomputation",
        )
    if authored_failures != tuple((item.identity, "failed") for item in failures):
        dependencies.reject_owner_predicate(
            "DS11-PAGE-A11Y-RECEIPT-CONTRACT",
            "page_a11y_failure_identities",
            "page-a11y receipt failure identities differ from recomputation",
        )
    raw_receipts = normalized.get("raw_receipts")
    replay = normalized.get("replay_agreement")
    if not isinstance(raw_receipts, dict) or not isinstance(replay, dict):
        dependencies.reject_owner_predicate(
            "DS11-PAGE-A11Y-RECEIPT-CONTRACT",
            "page_a11y_receipt_shape",
            "page-a11y receipt raw_receipts and replay_agreement must be objects",
        )
    if (
        raw_receipts.get("results_sha256")
        != hashlib.sha256(raw_by_name["run-1/results.json"]).hexdigest()
    ):
        dependencies.reject_owner_predicate(
            "DS11-PAGE-A11Y-RECEIPT-CONTRACT",
            "page_a11y_results_digest",
            "page-a11y results receipt digest differs",
        )
    if (
        raw_receipts.get("last_run_sha256")
        != hashlib.sha256(raw_by_name["run-1/.last-run.json"]).hexdigest()
    ):
        dependencies.reject_owner_predicate(
            "DS11-PAGE-A11Y-RECEIPT-CONTRACT",
            "page_a11y_last_run_digest",
            "page-a11y last-run receipt digest differs",
        )
    failure_ids = {item.test_id for item in failures}
    failed_tests = last_run.get("failedTests")
    if not isinstance(failed_tests, list) or not all(
        isinstance(item, str) for item in failed_tests
    ):
        dependencies.reject_owner_predicate(
            "DS11-PAGE-A11Y-RECEIPT-CONTRACT",
            "page_a11y_last_run_shape",
            "page-a11y last-run failedTests must be a string list",
        )
    if last_run.get("status") != "failed" or set(failed_tests) != failure_ids:
        dependencies.reject_owner_predicate(
            "DS11-PAGE-A11Y-RECEIPT-CONTRACT",
            "page_a11y_last_run_failures",
            "page-a11y last-run failures differ from results",
        )
    if replay.get("admissibility") != "not_established" or replay.get("committed_raw_runs") != 1:
        dependencies.reject_owner_predicate(
            "DS11-PAGE-A11Y-RECEIPT-CONTRACT",
            "page_a11y_replay_establishment",
            "page-a11y replay receipt overstates establishment",
        )
    try:
        source_as_of = date.fromisoformat(str(stats["startTime"])[:10])
        duration_ms = float(stats["duration"])
    except KeyError, TypeError, ValueError:
        dependencies.reject_owner_predicate(
            "DS11-PAGE-A11Y-RECEIPT-CONTRACT",
            "page_a11y_statistics",
            "page-a11y results statistics are incomplete or invalid",
        )
    try:
        return PageA11yReceiptBinding(
            **expected_authority_metadata,
            path=dependencies.page_receipt_path.as_posix(),
            source_contents={
                (dependencies.page_receipt_path / Path(name)).as_posix(): raw.decode("utf-8")
                for name, raw in raw_by_name.items()
            },
            content_digest="sha256:" + hashlib.sha256(raw_by_name["receipt.json"]).hexdigest(),
            admitted_sources=admitted,
            source_as_of=source_as_of,
            collected=observed["collected"],
            passed=observed["passed"],
            failed=observed["failed"],
            skipped=observed["skipped"],
            duration_ms=duration_ms,
            exit_code=observed["exit_code"],
            failures=failures,
            replay_establishment=EstablishmentClass.NOT_ESTABLISHED,
            limitation_refs=(str(replay.get("limitation")),),
        )
    except ValidationError:
        dependencies.reject_owner_predicate(
            "DS11-PAGE-A11Y-RECEIPT-CONTRACT",
            "page_a11y_typed_artifact",
            "page-a11y receipt violates its typed artifact schema",
        )


def _derive_page_result_rows(
    suites: Sequence[Mapping[str, object]], *, dependencies: AccessibilityDependencies
) -> tuple[tuple[tuple[str, str], ...], tuple[PageA11yFailureBinding, ...]]:
    identities: list[tuple[str, str]] = []
    failures: list[PageA11yFailureBinding] = []
    for suite in suites:
        if not isinstance(suite, dict):
            dependencies.reject_owner_predicate(
                "DS11-PAGE-A11Y-RECEIPT-CONTRACT",
                "page_a11y_suite_shape",
                "page-a11y suite rows must be objects",
            )
        specs = suite.get("specs", [])
        if not isinstance(specs, list):
            dependencies.reject_owner_predicate(
                "DS11-PAGE-A11Y-RECEIPT-CONTRACT",
                "page_a11y_specs_shape",
                "page-a11y suite specs must be a list",
            )
        for spec in specs:
            if not isinstance(spec, dict):
                dependencies.reject_owner_predicate(
                    "DS11-PAGE-A11Y-RECEIPT-CONTRACT",
                    "page_a11y_spec_shape",
                    "page-a11y spec rows must be objects",
                )
            identity = f"{spec.get('file')}::{spec.get('title')}"
            tests = spec.get("tests", [])
            if not isinstance(tests, list):
                dependencies.reject_owner_predicate(
                    "DS11-PAGE-A11Y-RECEIPT-CONTRACT",
                    "page_a11y_tests_shape",
                    "page-a11y spec tests must be a list",
                )
            for test in tests:
                if not isinstance(test, dict):
                    dependencies.reject_owner_predicate(
                        "DS11-PAGE-A11Y-RECEIPT-CONTRACT",
                        "page_a11y_test_shape",
                        "page-a11y test rows must be objects",
                    )
                raw_results = test.get("results", [])
                if not isinstance(raw_results, list) or any(
                    not isinstance(result, dict) for result in raw_results
                ):
                    dependencies.reject_owner_predicate(
                        "DS11-PAGE-A11Y-RECEIPT-CONTRACT",
                        "page_a11y_test_results_shape",
                        "page-a11y test results must be an object list",
                    )
                if not isinstance(spec.get("file"), str) or not isinstance(spec.get("title"), str):
                    dependencies.reject_owner_predicate(
                        "DS11-PAGE-A11Y-RECEIPT-CONTRACT",
                        "page_a11y_spec_identity",
                        "page-a11y spec identity requires file and title strings",
                    )
                if not isinstance(test.get("status"), str):
                    dependencies.reject_owner_predicate(
                        "DS11-PAGE-A11Y-RECEIPT-CONTRACT",
                        "page_a11y_test_status",
                        "page-a11y test status must be a string",
                    )
                raw_status = str(test["status"])
                status = (
                    "passed"
                    if raw_status == "expected"
                    else "skipped"
                    if raw_status == "skipped"
                    else "failed"
                )
                identities.append((identity, status))
                if status == "failed":
                    if not isinstance(spec.get("id"), str):
                        dependencies.reject_owner_predicate(
                            "DS11-PAGE-A11Y-RECEIPT-CONTRACT",
                            "page_a11y_spec_id",
                            "page-a11y failed-test spec requires an id string",
                        )
                    error_objects = [result.get("error", {}) for result in raw_results]
                    if any(not isinstance(error, dict) for error in error_objects):
                        dependencies.reject_owner_predicate(
                            "DS11-PAGE-A11Y-RECEIPT-CONTRACT",
                            "page_a11y_test_error_shape",
                            "page-a11y test error details must be objects",
                        )
                    message = " ".join(str(error.get("message", "")) for error in error_objects)
                    failures.append(
                        PageA11yFailureBinding(
                            identity=identity,
                            test_id=str(spec.get("id")),
                            issue_signature=_page_issue_signature(
                                message, dependencies=dependencies
                            ),
                        )
                    )
        nested = suite.get("suites", [])
        if not isinstance(nested, list):
            dependencies.reject_owner_predicate(
                "DS11-PAGE-A11Y-RECEIPT-CONTRACT",
                "page_a11y_nested_suites_shape",
                "page-a11y nested suites must be a list",
            )
        nested_identities, nested_failures = _derive_page_result_rows(
            nested, dependencies=dependencies
        )
        identities.extend(nested_identities)
        failures.extend(nested_failures)
    return tuple(identities), tuple(failures)


def _page_issue_signature(message: str, *, dependencies: AccessibilityDependencies) -> str:
    plain = re.sub(r"\x1b\[[0-9;]*m", "", message)
    axe = re.search(r'"id"\s*:\s*"([^"]+)"', plain)
    if axe:
        return f"axe:{axe.group(1)}"
    expected = re.search(r'Expected substring:\s*"(?:link|button) \\"([^"\\]+)\\""', plain)
    if expected:
        return f"accessible_name:{expected.group(1)}"
    dependencies.reject_owner_predicate(
        "DS11-PAGE-A11Y-RECEIPT-CONTRACT",
        "page_a11y_issue_signature",
        "page-a11y failure has no admitted semantic issue signature",
    )


def validate_claim_copy(
    copy: str,
    *,
    source_row: object | None,
    admitted_sources: Sequence[AdmittedSourceMember] = (),
    requested_purpose: str = "capability_claim",
    dependencies: AccessibilityDependencies,
) -> tuple[str, ...]:
    """Require copy to bind a strict, supported, admitted posture object."""
    del copy
    if not isinstance(source_row, (ClaimPostureRow, ClaimSourceBinding)):
        return ("DS11-IDENTITY-COPY-UNBOUND",)
    admitted = {item.path: item.content_digest for item in admitted_sources}
    bindings = (
        source_row.source_bindings if isinstance(source_row, ClaimPostureRow) else (source_row,)
    )
    state = (
        source_row.effective_state
        if isinstance(source_row, ClaimPostureRow)
        else source_row.source_state
    )
    if state != ClaimPostureState.SUPPORTED and state != "supported":
        return ("DS11-IDENTITY-COPY-UNBOUND",)
    if not bindings or any(
        binding.resolution != SourceResolution.RESOLVED
        or admitted.get(binding.coordinate.path) != binding.content_digest
        or requested_purpose not in binding.authoritative_for
        or requested_purpose in binding.may_not_use_for
        for binding in bindings
    ):
        return ("DS11-IDENTITY-COPY-UNBOUND",)
    return ()


def evaluate_accessibility_evidence(
    *,
    evidence_kind: str,
    requested_purpose: str,
    source_as_of: date,
    countersign_ref: str | None,
    register_as_of: date = date(2026, 8, 26),
    dependencies: AccessibilityDependencies,
) -> AccessibilityEvaluation:
    """Prevent internal historical evidence from minting current certification."""
    issues: set[str] = set()
    try:
        kind = AccessibilityEvidenceKind(evidence_kind)
    except ValueError:
        kind = None
        issues.add("DS11-A11Y-EVIDENCE-KIND-UNKNOWN")
    try:
        purpose = AccessibilityPurpose(requested_purpose)
    except ValueError:
        purpose = None
        issues.add("DS11-A11Y-PURPOSE-UNKNOWN")
    if source_as_of > register_as_of or register_as_of - source_as_of > timedelta(days=365):
        issues.add("DS11-A11Y-EVIDENCE-STALE")
    external = purpose in {
        AccessibilityPurpose.EXTERNAL_CERTIFICATION,
        AccessibilityPurpose.CURRENT_CONFORMANCE,
    }
    if external and (
        kind != AccessibilityEvidenceKind.EXTERNAL_COUNTERSIGNED_AUDIT or not countersign_ref
    ):
        issues.add("DS11-A11Y-CERTIFICATION-NOT-EARNED")
    if purpose == AccessibilityPurpose.HISTORICAL_INTERNAL_PRE_AUDIT and kind not in {
        AccessibilityEvidenceKind.INTERNAL_PRE_AUDIT,
        AccessibilityEvidenceKind.EXTERNAL_COUNTERSIGNED_AUDIT,
    }:
        issues.add("DS11-A11Y-EVIDENCE-NOT-ADMITTED")
    return AccessibilityEvaluation(
        state=ClaimPostureState.BLOCKED if issues else ClaimPostureState.SUPPORTED,
        issue_codes=tuple(sorted(issues)),
    )


def evaluate_scope_assumption(
    *, scope_assumption: str, adjudication_ref: str | None, dependencies: AccessibilityDependencies
) -> ScopeEvaluation:
    """Freeze a declared, unadjudicated scope as a visible limitation."""
    if not adjudication_ref:
        return ScopeEvaluation(
            state=ClaimPostureState.BLOCKED,
            establishment_class=EstablishmentClass.NOT_ESTABLISHED,
            limitations=(f"Declared scope assumption: {scope_assumption}",),
        )
    return ScopeEvaluation(
        state=ClaimPostureState.BLOCKED,
        establishment_class=EstablishmentClass.INSTITUTIONALLY_SUPPLIED,
        limitations=(f"Institutionally supplied scope: {scope_assumption}",),
    )
