"""Behavioral tests for the Atlas frontend baseline-debt lifecycle."""

from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path


ATLAS_DIR = Path(__file__).resolve().parent
REPO_ROOT = ATLAS_DIR.parents[1]
CHECKER_PATH = ATLAS_DIR / "check_frontend_disposition_register.py"
MANIFEST_PATH = ATLAS_DIR / "frontend-baseline-debt-manifest.json"
ARCHITECTURE_SCRIPT = (
    REPO_ROOT / "apps/runtime-dashboard/scripts/check-architecture.mjs"
)

_SPEC = importlib.util.spec_from_file_location("frontend_debt_checker", CHECKER_PATH)
if _SPEC is None or _SPEC.loader is None:  # pragma: no cover - import bootstrap guard
    raise RuntimeError(f"Unable to import debt checker from {CHECKER_PATH}")
checker = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(checker)


def _manifest() -> dict[str, object]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def _write_json(value: object) -> Path:
    handle = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
    with handle:
        json.dump(value, handle)
    return Path(handle.name)


def _eslint_results(lint: dict[str, object]) -> list[dict[str, object]]:
    return [
        {
            "filePath": str(REPO_ROOT / file_entry["path"]),
            "messages": [
                {
                    "ruleId": row["rule_id"],
                    "severity": row["severity"],
                    "line": row["line"],
                    "column": row["column"],
                    "endLine": row["end_line"],
                    "endColumn": row["end_column"],
                    "messageId": row["message_id"],
                    "message": row["message"],
                }
                for row in file_entry["diagnostics"]
            ],
            "suppressedMessages": [],
        }
        for file_entry in lint["files"]
    ]


class FrontendBaselineDebtLifecycleTests(unittest.TestCase):
    """Prove debt can shrink without erasing its immutable origin."""

    def test_lint_origin_active_and_resolved_form_an_exact_partition(self) -> None:
        manifest = _manifest()
        lint = manifest["lint"]

        self.assertIn("immutable_origin", lint)
        self.assertEqual(lint["immutable_origin"]["error_count"], 75)
        self.assertEqual(lint["immutable_origin"]["source_file_count"], 22)
        self.assertEqual(lint["error_count"], 55)
        self.assertEqual(lint["source_file_count"], 15)
        self.assertEqual(len(lint["resolutions"]), 20)
        self.assertEqual(checker.validate_baseline_manifest(manifest), [])

    def test_lint_partition_rejects_a_missing_resolution(self) -> None:
        mutation = copy.deepcopy(_manifest())
        mutation["lint"]["resolutions"].pop()

        errors = checker.validate_baseline_manifest(mutation)

        self.assertIn("lint_partition_missing_identity", errors)

    def test_lint_partition_rejects_an_active_and_resolved_duplicate(self) -> None:
        mutation = copy.deepcopy(_manifest())
        active_identity = checker._lint_identity_rows(mutation["lint"])[0][0]
        mutation["lint"]["resolutions"][0]["origin_identity_sha256"] = active_identity

        errors = checker.validate_baseline_manifest(mutation)

        self.assertIn("lint_partition_overlap", errors)

    def test_lint_origin_rejects_a_moved_identity_even_when_counts_hold(self) -> None:
        mutation = copy.deepcopy(_manifest())
        mutation["lint"]["resolutions"][0]["origin_identity"]["line"] += 1

        errors = checker.validate_baseline_manifest(mutation)

        self.assertIn("lint_origin_identity_set_hash_drift", errors)

    def test_lint_resolution_rejects_a_fabricated_reference(self) -> None:
        mutation = copy.deepcopy(_manifest())
        mutation["lint"]["resolutions"][0]["implementation_refs"][0] = (
            "apps/runtime-dashboard/src/not-a-real-successor.ts"
        )

        errors = checker.validate_baseline_manifest(mutation)

        self.assertTrue(
            any(error.startswith("lint_resolution_reference_path_missing:") for error in errors),
            errors,
        )

    def test_c06_quantity_resolution_rejects_an_unrelated_existing_test(self) -> None:
        mutation = copy.deepcopy(_manifest())
        resolution = next(
            row
            for row in mutation["lint"]["resolutions"]
            if row["cluster_id"] == "C06"
            and row["classification"] == "quantity_enveloped"
        )
        resolution["closure_test_ref"] = (
            "apps/runtime-dashboard/src/shared/ui/quantity/Quantity.test.tsx"
        )

        errors = checker.validate_baseline_manifest(mutation)

        self.assertIn(
            "lint_c06_semantic_closure_drift:"
            + resolution["origin_identity_sha256"],
            errors,
        )

    def test_lint_comparator_requires_the_exact_active_set(self) -> None:
        manifest = _manifest()
        exact_path = _write_json(_eslint_results(manifest["lint"]))
        missing_results = _eslint_results(manifest["lint"])
        missing_results[0]["messages"].pop()
        missing_path = _write_json(missing_results)
        self.addCleanup(exact_path.unlink)
        self.addCleanup(missing_path.unlink)

        self.assertEqual(checker.compare_lint_results(manifest, exact_path), [])
        errors = checker.compare_lint_results(manifest, missing_path)
        self.assertTrue(
            any(error.startswith("lint_expected_diagnostic_missing:") for error in errors),
            errors,
        )

    def test_architecture_origin_active_and_resolved_form_an_exact_partition(self) -> None:
        manifest = _manifest()
        architecture = manifest["architecture"]

        self.assertEqual(architecture["immutable_origin"]["violation_count"], 36)
        self.assertEqual(architecture["violation_count"], 23)
        self.assertEqual(len(architecture["resolutions"]), 13)
        self.assertEqual(checker.validate_baseline_manifest(manifest), [])

    def test_architecture_partition_rejects_a_missing_resolution(self) -> None:
        mutation = copy.deepcopy(_manifest())
        mutation["architecture"]["resolutions"].pop()

        errors = checker.validate_baseline_manifest(mutation)

        self.assertIn("architecture_partition_missing_identity", errors)

    def test_architecture_comparator_requires_the_exact_active_set(self) -> None:
        manifest = _manifest()
        exact = {"violations": manifest["architecture"]["violations"]}
        exact_path = _write_json(exact)
        missing_path = _write_json({"violations": exact["violations"][1:]})
        self.addCleanup(exact_path.unlink)
        self.addCleanup(missing_path.unlink)

        self.assertEqual(
            checker.compare_architecture_results(manifest, exact_path),
            [],
        )
        errors = checker.compare_architecture_results(manifest, missing_path)
        self.assertTrue(
            any(error.startswith("architecture_expected_violation_missing:") for error in errors),
            errors,
        )

    def test_architecture_json_and_human_modes_share_one_producer(self) -> None:
        json_run = subprocess.run(
            ["node", str(ARCHITECTURE_SCRIPT), "--format=json"],
            cwd=REPO_ROOT / "apps/runtime-dashboard",
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertTrue(json_run.stdout.strip())
        payload = json.loads(json_run.stdout)
        violations = payload["violations"]
        self.assertEqual(json_run.returncode, 0 if not violations else 1)

        human_run = subprocess.run(
            ["node", str(ARCHITECTURE_SCRIPT)],
            cwd=REPO_ROOT / "apps/runtime-dashboard",
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(human_run.returncode, json_run.returncode)
        for violation in violations:
            self.assertIn(f"- {violation['display']}", human_run.stderr)

    def test_lifecycle_corruption_probes_all_fail_closed(self) -> None:
        manifest = _manifest()

        self.assertEqual(checker._baseline_corruption_probes(manifest), [])


if __name__ == "__main__":
    unittest.main()
