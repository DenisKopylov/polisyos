"""Content-binding checks for append-only DS11 accessibility evidence."""

from __future__ import annotations

import copy
import hashlib
import json
import subprocess
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
RECEIPT_ROOT = (
    REPO_ROOT
    / "docs/plans/active/atlas-slices/receipts/ds11-page-a11y-current"
)
RECEIPT_PATH = RECEIPT_ROOT / "receipt.json"
SOURCE_DENOMINATOR = (
    "apps/runtime-dashboard",
    "package.json",
    "pnpm-lock.yaml",
    "pnpm-workspace.yaml",
)
EXPECTED_COMMAND = (
    "PLAYWRIGHT_JSON_OUTPUT_FILE=<receipt-relative-output> corepack pnpm --filter "
    "@polisyos/runtime-dashboard run test:a11y:pages --reporter=json --workers=1 "
    "--retries=0 --update-snapshots=none"
)
EXPECTED_LIMITATIONS = (
    "page_suite_conformance_not_human_behavior",
    "internal_receipt_not_external_countersignature",
    "rendered_presentation_not_source_language_authority",
)
EXPECTED_PAGE_A11Y_FILES = {
    "../src/test/a11y/color-blind-simulation.spec.ts",
    "../src/test/a11y/keyboard-journeys.spec.ts",
    "../src/test/a11y/screen-reader-snapshots.spec.ts",
    "a11y/routes.a11y.spec.ts",
}
EXPECTED_PAGE_A11Y_SCRIPT = (
    "PLAYWRIGHT_INCLUDE_BOUND_RUN_PAPER_FIXTURE=1 playwright test e2e/a11y "
    "--project=chromium"
)
RECEIPT_KEYS = {
    "schema_version",
    "authority_purpose",
    "status",
    "recorded_at_utc",
    "issuer",
    "evidence_grade",
    "command",
    "scope",
    "limitations",
    "human_behavior_status",
    "external_countersign_status",
    "source_language_authority",
    "source_binding",
    "raw_receipts",
    "replay_agreement",
    "toolchain",
    "payload_digest",
}


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict), f"JSON root must be an object: {path}"
    return payload


def _sha256(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _canonical_digest(payload: object) -> str:
    return _sha256(
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    )


def _assert_exact_keys(
    payload: dict[str, Any], expected: set[str], *, context: str
) -> None:
    assert set(payload) == expected, (
        f"{context} keys mismatch: "
        f"missing={sorted(expected - set(payload))}, "
        f"unexpected={sorted(set(payload) - expected)}"
    )


def _parse_utc(value: object, *, context: str) -> datetime:
    assert isinstance(value, str) and value.endswith("Z"), f"{context} must be UTC"
    parsed = datetime.fromisoformat(value.removesuffix("Z") + "+00:00")
    assert parsed.tzinfo == UTC, f"{context} must be timezone-aware UTC"
    return parsed


def _command_stdout(argv: list[str]) -> str:
    completed = subprocess.run(  # noqa: S603 - fixed version-only command.
        argv,
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    return completed.stdout.strip()


def _tracked_source_rows() -> tuple[tuple[str, str], ...]:
    completed = subprocess.run(  # noqa: S603 - fixed read-only git census.
        ["git", "ls-files", "-z", "--", *SOURCE_DENOMINATOR],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
    )
    assert completed.returncode == 0, completed.stderr.decode("utf-8")
    paths = tuple(
        sorted(
            path
            for path in completed.stdout.decode("utf-8").split("\0")
            if path
        )
    )
    return tuple((path, _sha256((REPO_ROOT / path).read_bytes())) for path in paths)


def _collected_identity_rows(report: dict[str, Any]) -> tuple[str, ...]:
    identities: list[str] = []

    def visit(suites: object, parents: tuple[str, ...] = ()) -> None:
        assert isinstance(suites, list), "Playwright suites must be a list"
        for suite in suites:
            assert isinstance(suite, dict), "Playwright suite must be an object"
            title = suite.get("title")
            lineage = parents + ((str(title),) if title else ())
            specs = suite.get("specs", [])
            assert isinstance(specs, list), "Playwright specs must be a list"
            for spec in specs:
                assert isinstance(spec, dict), "Playwright spec must be an object"
                assert spec.get("ok") is True, f"non-green spec: {spec.get('title')}"
                tests = spec.get("tests")
                assert isinstance(tests, list) and tests, "spec has no project result"
                for test in tests:
                    assert isinstance(test, dict), "project result must be an object"
                    assert test.get("expectedStatus") == "passed"
                    assert test.get("status") == "expected"
                    results = test.get("results")
                    assert isinstance(results, list) and len(results) == 1
                    result = results[0]
                    assert isinstance(result, dict)
                    assert result.get("status") == "passed"
                    assert result.get("retry") == 0
                    assert result.get("errors") == []
                    identity = (
                        str(spec.get("file")),
                        *lineage,
                        str(spec.get("title")),
                        str(test.get("projectName")),
                    )
                    identities.append("::".join(identity))
            visit(suite.get("suites", []), lineage)

    visit(report.get("suites"))
    return tuple(identities)


def _executed_scope(report: dict[str, Any]) -> tuple[set[str], set[str]]:
    files: set[str] = set()
    projects: set[str] = set()

    def visit(suites: object) -> None:
        assert isinstance(suites, list), "Playwright suites must be a list"
        for suite in suites:
            assert isinstance(suite, dict), "Playwright suite must be an object"
            specs = suite.get("specs", [])
            assert isinstance(specs, list), "Playwright specs must be a list"
            for spec in specs:
                assert isinstance(spec, dict), "Playwright spec must be an object"
                files.add(str(spec.get("file")))
                tests = spec.get("tests")
                assert isinstance(tests, list) and tests
                for test in tests:
                    assert isinstance(test, dict)
                    projects.add(str(test.get("projectName")))
            visit(suite.get("suites", []))

    visit(report.get("suites"))
    return files, projects


def _resign(receipt: dict[str, Any]) -> None:
    digest_payload = {key: value for key, value in receipt.items() if key != "payload_digest"}
    receipt["payload_digest"] = _canonical_digest(digest_payload)


def _validate_receipt(receipt: dict[str, Any]) -> None:
    _assert_exact_keys(receipt, RECEIPT_KEYS, context="receipt")
    assert receipt["schema_version"] == "policyos.ds11.page_a11y_current_receipt.v1"
    assert receipt["authority_purpose"] == "current_scoped_page_conformance"
    assert receipt["status"] == "passed"
    assert receipt["issuer"] == "policyos.repository_test_harness"
    assert receipt["evidence_grade"] == "internal_recomputed"
    assert receipt["command"] == EXPECTED_COMMAND
    assert tuple(receipt["limitations"]) == EXPECTED_LIMITATIONS
    assert receipt["human_behavior_status"] == "not_established"
    assert receipt["external_countersign_status"] == "not_established"
    assert receipt["source_language_authority"] == "not_conferred"
    recorded_at = _parse_utc(receipt["recorded_at_utc"], context="recorded_at_utc")

    scope = receipt["scope"]
    assert isinstance(scope, dict)
    _assert_exact_keys(
        scope,
        {"package", "script", "browser_project", "source_denominator"},
        context="scope",
    )
    assert scope == {
        "package": "@polisyos/runtime-dashboard",
        "script": "test:a11y:pages",
        "browser_project": "chromium",
        "source_denominator": list(SOURCE_DENOMINATOR),
    }

    source_binding = receipt["source_binding"]
    assert isinstance(source_binding, dict)
    _assert_exact_keys(
        source_binding,
        {
            "predicate_class",
            "path_count",
            "source_set_digest",
            "dashboard_source_commit",
        },
        context="source binding",
    )
    assert source_binding["predicate_class"] == "recomputed"
    source_rows = _tracked_source_rows()
    assert source_binding["path_count"] == len(source_rows)
    assert source_binding["source_set_digest"] == _canonical_digest(source_rows)
    source_commit = source_binding["dashboard_source_commit"]
    commit_check = subprocess.run(  # noqa: S603 - fixed read-only git probe.
        ["git", "cat-file", "-e", f"{source_commit}^{{commit}}"],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
    )
    assert commit_check.returncode == 0, "dashboard source commit is not resolvable"
    source_diff = subprocess.run(  # noqa: S603 - fixed read-only git probe.
        ["git", "diff", "--quiet", source_commit, "--", *SOURCE_DENOMINATOR],
        cwd=REPO_ROOT,
        check=False,
    )
    assert source_diff.returncode == 0, "dashboard source changed after receipt execution"

    toolchain = receipt["toolchain"]
    assert isinstance(toolchain, dict)
    _assert_exact_keys(toolchain, {"node", "pnpm", "playwright"}, context="toolchain")
    root_package = _load_json(REPO_ROOT / "package.json")
    dashboard_package = _load_json(
        REPO_ROOT / "apps/runtime-dashboard/package.json"
    )
    assert dashboard_package["scripts"]["test:a11y:pages"] == EXPECTED_PAGE_A11Y_SCRIPT
    assert root_package["packageManager"] == f"pnpm@{toolchain['pnpm']}"
    assert dashboard_package["devDependencies"]["playwright"] == toolchain["playwright"]
    assert toolchain["node"] == _command_stdout(["node", "--version"])
    assert toolchain["pnpm"] == _command_stdout(["corepack", "pnpm", "--version"])

    raw_receipts = receipt["raw_receipts"]
    assert isinstance(raw_receipts, list) and len(raw_receipts) == 2
    identity_runs: list[tuple[str, ...]] = []
    result_digests: set[str] = set()
    previous_finish: datetime | None = None
    for expected_run, raw in enumerate(raw_receipts, start=1):
        assert isinstance(raw, dict)
        _assert_exact_keys(
            raw,
            {
                "run",
                "started_at_utc",
                "results_path",
                "last_run_path",
                "results_sha256",
                "last_run_sha256",
                "summary",
            },
            context=f"run {expected_run}",
        )
        assert raw["run"] == expected_run
        assert raw["results_path"] == f"run-{expected_run}/results.json"
        assert raw["last_run_path"] == f"run-{expected_run}/last-run.json"
        results_path = RECEIPT_ROOT / raw["results_path"]
        last_run_path = RECEIPT_ROOT / raw["last_run_path"]
        assert raw["results_sha256"] == _sha256(results_path.read_bytes()), (
            "raw result digest mismatch"
        )
        assert raw["last_run_sha256"] == _sha256(last_run_path.read_bytes()), (
            "last-run digest mismatch"
        )
        report = _load_json(results_path)
        last_run = _load_json(last_run_path)
        _assert_exact_keys(
            report, {"config", "suites", "errors", "stats"}, context="raw report"
        )
        _assert_exact_keys(
            last_run, {"status", "failedTests"}, context="last-run report"
        )
        config = report["config"]
        assert isinstance(config, dict)
        assert config["version"] == toolchain["playwright"]
        assert config["workers"] == 1
        assert config["reporter"] == [["json"]]
        assert config["updateSnapshots"] == "none"
        projects = config["projects"]
        assert isinstance(projects, list)
        chromium_projects = [
            project
            for project in projects
            if isinstance(project, dict) and project.get("id") == "chromium"
        ]
        assert len(chromium_projects) == 1
        chromium_project = chromium_projects[0]
        assert chromium_project["name"] == "chromium"
        assert chromium_project["retries"] == 0
        assert chromium_project["repeatEach"] == 1
        assert chromium_project["metadata"]["actualWorkers"] == 1
        identities = _collected_identity_rows(report)
        assert len(identities) == len(set(identities)) == 25
        files, executed_projects = _executed_scope(report)
        assert files == EXPECTED_PAGE_A11Y_FILES
        assert executed_projects == {"chromium"}
        stats = report.get("stats")
        assert isinstance(stats, dict)
        _assert_exact_keys(
            stats,
            {"startTime", "duration", "expected", "skipped", "unexpected", "flaky"},
            context="raw stats",
        )
        started_at = _parse_utc(raw["started_at_utc"], context="run started_at_utc")
        assert raw["started_at_utc"] == stats["startTime"]
        duration_ms = stats["duration"]
        assert isinstance(duration_ms, int | float) and duration_ms > 0
        finished_at = started_at + timedelta(milliseconds=duration_ms)
        if previous_finish is not None:
            assert started_at > previous_finish, "runs were not independent sequential invocations"
        previous_finish = finished_at
        observed_summary = {
            "collected": len(identities),
            "expected": stats.get("expected"),
            "skipped": stats.get("skipped"),
            "unexpected": stats.get("unexpected"),
            "flaky": stats.get("flaky"),
            "exit_code": 0,
        }
        assert raw["summary"] == observed_summary
        assert report.get("errors") == []
        assert last_run == {"status": "passed", "failedTests": []}
        identity_runs.append(identities)
        result_digests.add(raw["results_sha256"])

    assert len(result_digests) == 2, "run result digests must be distinct"
    assert previous_finish is not None and recorded_at >= previous_finish
    assert identity_runs[0] == identity_runs[1]
    replay = receipt["replay_agreement"]
    assert isinstance(replay, dict)
    _assert_exact_keys(
        replay,
        {
            "completed_replays",
            "predicate_class",
            "identity_count",
            "identity_digest",
        },
        context="replay agreement",
    )
    assert replay["completed_replays"] == 2
    assert replay["predicate_class"] == "independently_reconciled"
    assert replay["identity_count"] == len(identity_runs[0]) == 25
    assert replay["identity_digest"] == _canonical_digest(identity_runs[0])

    expected_payload_digest = receipt["payload_digest"]
    _resign(receipt)
    assert receipt["payload_digest"] == expected_payload_digest


def test_current_page_conformance_receipt_is_fresh_scope_exact_and_content_bound() -> None:
    """Recompute two green runs and all tracked dashboard source bytes."""
    _validate_receipt(_load_json(RECEIPT_PATH))


def test_current_page_conformance_receipt_rejects_raw_result_digest_drift() -> None:
    """A shaped receipt cannot stay green when one carried result changes."""
    receipt = copy.deepcopy(_load_json(RECEIPT_PATH))
    receipt["raw_receipts"][0]["results_sha256"] = "sha256:" + "0" * 64

    with pytest.raises(AssertionError, match="raw result digest mismatch"):
        _validate_receipt(receipt)


def _claim_external_authority(receipt: dict[str, Any]) -> None:
    receipt["issuer"] = "external_auditor"


def _inflate_evidence_grade(receipt: dict[str, Any]) -> None:
    receipt["evidence_grade"] = "externally_certified"


def _add_unverified_certification(receipt: dict[str, Any]) -> None:
    receipt["external_certification"] = "granted"


def _substitute_scope(receipt: dict[str, Any]) -> None:
    receipt["scope"] = {
        "package": "@other/app",
        "script": "test:unrelated",
        "browser_project": "webkit",
        "source_denominator": ["apps/other"],
    }


def _substitute_toolchain(receipt: dict[str, Any]) -> None:
    receipt["toolchain"] = {
        "node": "v0.0.0",
        "pnpm": "0.0.0",
        "playwright": "0.0.0",
    }


@pytest.mark.parametrize(
    "mutation",
    [
        _claim_external_authority,
        _inflate_evidence_grade,
        _add_unverified_certification,
        _substitute_scope,
        _substitute_toolchain,
    ],
    ids=(
        "external-issuer",
        "external-grade",
        "extra-certification",
        "wrong-scope",
        "wrong-toolchain",
    ),
)
def test_current_page_conformance_receipt_rejects_authority_or_scope_inflation(
    mutation: Callable[[dict[str, Any]], None],
) -> None:
    """Re-signing cannot turn a bounded internal receipt into stronger evidence."""
    receipt = copy.deepcopy(_load_json(RECEIPT_PATH))
    mutation(receipt)
    _resign(receipt)

    with pytest.raises(AssertionError):
        _validate_receipt(receipt)


def test_current_page_conformance_receipt_rejects_duplicate_run_substitution() -> None:
    """One invocation cannot occupy both independently reconciled run slots."""
    receipt = copy.deepcopy(_load_json(RECEIPT_PATH))
    receipt["raw_receipts"][1] = copy.deepcopy(receipt["raw_receipts"][0])
    receipt["raw_receipts"][1]["run"] = 2
    _resign(receipt)

    with pytest.raises(AssertionError):
        _validate_receipt(receipt)
