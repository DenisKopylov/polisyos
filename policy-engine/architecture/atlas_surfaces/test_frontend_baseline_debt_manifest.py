"""Behavioral tests for the Atlas frontend baseline-debt lifecycle."""

from __future__ import annotations

import copy
import hashlib
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


def _always_null_c07_scalar_bytes() -> bytes:
    path = REPO_ROOT / "apps/runtime-dashboard/src/shared/charts/quantityChartSemantics.tsx"
    source = path.read_bytes()
    start = source.index(b"export function chartQuantityScalarPoint")
    end = source.index(b"\nexport function chartQuantityInterval", start)
    replacement = b"""export function chartQuantityScalarPoint(
  input: ChartQuantityInput | null | undefined,
): number | null {
  // Retained semantic marker strings: chartQuantityMembers, finitePoint,
  // members.length, members[0]?.point, and input == null.
  return null;
}
"""
    corrupted = source[:start] + replacement + source[end:]
    for marker in (
        b"chartQuantityMembers",
        b"finitePoint",
        b"members.length",
        b"members[0]?.point",
        b"input == null",
    ):
        if marker not in corrupted:
            raise AssertionError(f"corruption lost marker: {marker!r}")
    return corrupted


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


def _reactivate_resolution(lint: dict[str, object], resolution: dict[str, object]) -> None:
    origin = resolution["origin_identity"]
    diagnostic = {key: value for key, value in origin.items() if key != "source_content_sha256"}
    lint.update(
        {
            "disposition": "rebind_pending",
            "exit_code": 1,
            "error_count": 1,
            "source_file_count": 1,
            "files": [
                {
                    "path": origin["path"],
                    "content_sha256": origin["source_content_sha256"],
                    "diagnostic_count": 1,
                    "rule_counts": [{"rule_id": origin["rule_id"], "count": 1}],
                    "diagnostics": [diagnostic],
                }
            ],
            "identity_set_sha256": checker._canonical_sha256([origin]),
        }
    )
    lint["diagnostic_set"]["sha256"] = checker._canonical_sha256([diagnostic])


class FrontendBaselineDebtLifecycleTests(unittest.TestCase):
    """Prove debt can shrink without erasing its immutable origin."""

    def test_lint_origin_active_and_resolved_form_an_exact_partition(self) -> None:
        manifest = _manifest()
        lint = manifest["lint"]

        self.assertIn("immutable_origin", lint)
        self.assertEqual(lint["immutable_origin"]["error_count"], 75)
        self.assertEqual(lint["immutable_origin"]["source_file_count"], 22)
        self.assertEqual(lint["error_count"], 0)
        self.assertEqual(lint["source_file_count"], 0)
        self.assertEqual(len(lint["resolutions"]), 75)
        self.assertEqual(checker.validate_baseline_manifest(manifest), [])

    def test_lint_partition_rejects_a_missing_resolution(self) -> None:
        mutation = copy.deepcopy(_manifest())
        mutation["lint"]["resolutions"].pop()

        errors = checker.validate_baseline_manifest(mutation)

        self.assertIn("lint_partition_missing_identity", errors)

    def test_lint_partition_rejects_an_active_and_resolved_duplicate(self) -> None:
        mutation = copy.deepcopy(_manifest())
        _reactivate_resolution(
            mutation["lint"],
            mutation["lint"]["resolutions"][0],
        )

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

    def test_c07_chart_resolution_classifications_are_exact_and_content_bound(self) -> None:
        manifest = _manifest()
        resolutions = [
            row
            for row in manifest["lint"]["resolutions"]
            if row["cluster_id"] == "C07"
        ]

        self.assertEqual(
            {
                "layout_geometry": 33,
                "quantity_semantics": 4,
            },
            dict(checker.Counter(row["classification"] for row in resolutions)),
        )
        self.assertTrue(
            all(
                row["semantic_kind"]
                == (
                    "decision_bearing"
                    if row["classification"] == "quantity_semantics"
                    else "non_authority_control"
                )
                for row in resolutions
            )
        )
        self.assertTrue(
            all(
                row["closure_test_ref"]
                == "apps/runtime-dashboard/src/shared/charts/quantityChartSemantics.test.tsx"
                for row in resolutions
            )
        )

    def test_c07_chart_resolution_rejects_semantic_kind_laundering(self) -> None:
        mutation = copy.deepcopy(_manifest())
        resolution = next(
            row
            for row in mutation["lint"]["resolutions"]
            if row["cluster_id"] == "C07"
            and row["classification"] == "quantity_semantics"
        )
        resolution["semantic_kind"] = "non_authority_control"

        errors = checker.validate_baseline_manifest(mutation)

        self.assertIn("lint_c07_semantic_kind_drift", errors)

    def test_c08_non_authority_classifications_are_exact_and_content_bound(
        self,
    ) -> None:
        manifest = _manifest()
        resolutions = [row for row in manifest["lint"]["resolutions"] if row["cluster_id"] == "C08"]

        self.assertEqual(
            {
                "interaction_control": 3,
                "layout_geometry": 5,
                "motion_geometry": 9,
                "operational_request_control": 1,
            },
            dict(checker.Counter(row["classification"] for row in resolutions)),
        )
        self.assertTrue(all(row["semantic_kind"] == "non_authority_control" for row in resolutions))
        self.assertTrue(
            all(
                row["closure_test_ref"]
                == "apps/runtime-dashboard/eslint-plugin-local/rules/quantity-must-be-wrapped.test.cjs"
                for row in resolutions
            )
        )

    def test_c08_rejects_classification_laundering(self) -> None:
        mutation = copy.deepcopy(_manifest())
        resolution = next(
            row for row in mutation["lint"]["resolutions"] if row["cluster_id"] == "C08"
        )
        resolution["classification"] = "motion_geometry"

        errors = checker.validate_baseline_manifest(mutation)

        self.assertIn("lint_c08_resolution_classification_drift", errors)

    def test_c08_rejects_semantic_kind_laundering(self) -> None:
        mutation = copy.deepcopy(_manifest())
        resolution = next(
            row for row in mutation["lint"]["resolutions"] if row["cluster_id"] == "C08"
        )
        resolution["semantic_kind"] = "decision_bearing"

        errors = checker.validate_baseline_manifest(mutation)

        self.assertIn("lint_c08_semantic_kind_drift", errors)

    def test_c08_rejects_a_marker_only_closure(self) -> None:
        mutation = copy.deepcopy(_manifest())
        resolution = next(
            row for row in mutation["lint"]["resolutions"] if row["cluster_id"] == "C08"
        )
        resolution["closure_test_ref"] = (
            "apps/runtime-dashboard/src/shared/lib/domain/nonAuthorityNumeric.test.ts"
        )

        errors = checker.validate_baseline_manifest(mutation)

        self.assertIn(
            "lint_c08_semantic_closure_drift:" + resolution["origin_identity_sha256"],
            errors,
        )

    def test_c08_requires_the_canonical_numeric_adapter(self) -> None:
        mutation = copy.deepcopy(_manifest())
        resolution = next(
            row for row in mutation["lint"]["resolutions"] if row["cluster_id"] == "C08"
        )
        resolution["implementation_refs"] = [
            ref
            for ref in resolution["implementation_refs"]
            if ref != "apps/runtime-dashboard/src/shared/lib/domain/nonAuthorityNumeric.ts"
        ]

        errors = checker.validate_baseline_manifest(mutation)

        self.assertIn(
            "lint_c08_semantic_adapter_drift:" + resolution["origin_identity_sha256"],
            errors,
        )

    def test_resolution_content_bindings_cover_exact_derived_roles_and_live_bytes(
        self,
    ) -> None:
        manifest = _manifest()

        errors = checker.validate_baseline_manifest(manifest)

        self.assertEqual(errors, [])
        c07_closure = next(
            row
            for row in manifest["lint"]["resolution_content_bindings"]
            if row["cluster_id"] == "C07"
            and row["path"]
            == "apps/runtime-dashboard/src/shared/charts/quantityChartSemantics.test.tsx"
        )
        self.assertEqual(c07_closure["roles"], ["closure_test", "consumer"])

    def test_resolution_content_bindings_reject_a_removed_binding(self) -> None:
        mutation = _manifest()
        removed = mutation["lint"]["resolution_content_bindings"].pop()

        errors = checker.validate_baseline_manifest(mutation)

        self.assertIn(
            "lint_resolution_content_binding_missing:"
            f"{removed['cluster_id']}:{removed['path']}",
            errors,
        )

    def test_resolution_content_bindings_reject_role_laundering(self) -> None:
        mutation = _manifest()
        binding = next(
            row
            for row in mutation["lint"]["resolution_content_bindings"]
            if row["cluster_id"] == "C07" and len(row["roles"]) > 1
        )
        binding["roles"] = binding["roles"][:-1]

        errors = checker.validate_baseline_manifest(mutation)

        self.assertIn(
            "lint_resolution_content_binding_role_drift:"
            f"{binding['cluster_id']}:{binding['path']}",
            errors,
        )

    def test_resolution_content_bindings_reject_duplicate_cluster_path(self) -> None:
        mutation = _manifest()
        duplicate = copy.deepcopy(mutation["lint"]["resolution_content_bindings"][0])
        duplicate["sha256"] = "0" * 64
        mutation["lint"]["resolution_content_bindings"].append(duplicate)

        errors = checker.validate_baseline_manifest(mutation)

        self.assertIn(
            "lint_resolution_content_binding_duplicate:"
            f"{duplicate['cluster_id']}:{duplicate['path']}",
            errors,
        )

    def test_resolution_content_bindings_reject_an_extra_cluster_path(self) -> None:
        mutation = _manifest()
        path = "architecture/atlas_surfaces/frontend-baseline-debt.schema.json"
        mutation["lint"]["resolution_content_bindings"].append(
            {
                "cluster_id": "C07",
                "path": path,
                "roles": ["consumer"],
                "sha256": hashlib.sha256((REPO_ROOT / path).read_bytes()).hexdigest(),
            }
        )

        errors = checker.validate_baseline_manifest(mutation)

        self.assertIn(
            f"lint_resolution_content_binding_extra:C07:{path}",
            errors,
        )

    def test_resolution_content_binding_detects_marker_preserving_scalar_corruption(
        self,
    ) -> None:
        manifest = _manifest()
        path = "apps/runtime-dashboard/src/shared/charts/quantityChartSemantics.tsx"

        errors = checker.validate_baseline_manifest(
            manifest,
            source_bytes_override={path: _always_null_c07_scalar_bytes()},
        )

        self.assertIn(
            f"lint_resolution_content_hash_drift:C07:{path}",
            errors,
        )

    def test_lint_comparator_requires_the_exact_active_set(self) -> None:
        manifest = _manifest()
        exact_path = _write_json(_eslint_results(manifest["lint"]))
        origin = manifest["lint"]["resolutions"][0]["origin_identity"]
        fabricated_path = _write_json(
            [
                {
                    "filePath": str(REPO_ROOT / origin["path"]),
                    "messages": [
                        {
                            "ruleId": origin["rule_id"],
                            "severity": origin["severity"],
                            "line": origin["line"],
                            "column": origin["column"],
                            "endLine": origin["end_line"],
                            "endColumn": origin["end_column"],
                            "messageId": origin["message_id"],
                            "message": origin["message"],
                        }
                    ],
                    "suppressedMessages": [],
                }
            ]
        )
        self.addCleanup(exact_path.unlink)
        self.addCleanup(fabricated_path.unlink)

        self.assertEqual(checker.compare_lint_results(manifest, exact_path), [])
        errors = checker.compare_lint_results(manifest, fabricated_path)
        self.assertTrue(
            any(error.startswith("lint_new_diagnostic:") for error in errors),
            errors,
        )

    def test_architecture_origin_active_and_resolved_form_an_exact_partition(self) -> None:
        manifest = _manifest()
        architecture = manifest["architecture"]

        self.assertEqual(architecture["immutable_origin"]["violation_count"], 36)
        self.assertEqual(architecture["violation_count"], 6)
        self.assertEqual(architecture["source_file_count"], 5)
        self.assertEqual(len(architecture["resolutions"]), 30)
        self.assertEqual(
            sum(
                resolution["cluster_id"] == "C09"
                for resolution in architecture["resolutions"]
            ),
            7,
        )
        c10_resolutions = [
            resolution
            for resolution in architecture["resolutions"]
            if resolution["cluster_id"] == "C10"
        ]
        self.assertEqual(len(c10_resolutions), 1)
        self.assertEqual(
            c10_resolutions[0]["origin_identity"]["source_path"],
            "apps/runtime-dashboard/src/shared/ui/authored-text/AuthoredText.tsx",
        )
        self.assertEqual(
            c10_resolutions[0]["closure_test_ref"],
            "apps/runtime-dashboard/src/shared/ui/authored-text/authoredTextArchitecture.test.ts",
        )
        c11_resolutions = [
            resolution
            for resolution in architecture["resolutions"]
            if resolution["cluster_id"] == "C11"
        ]
        self.assertEqual(len(c11_resolutions), 9)
        self.assertEqual(
            {
                "apps/runtime-dashboard/src/shared/charts/UncertaintyDisplay.tsx",
                "apps/runtime-dashboard/src/shared/charts/uncertainty-rendering.ts",
                "apps/runtime-dashboard/src/shared/ui/trust-view/HashChip.tsx",
                "apps/runtime-dashboard/src/shared/ui/trust-view/TrustInspector.test.tsx",
                "apps/runtime-dashboard/src/shared/ui/trust-view/TrustInspector.tsx",
                "apps/runtime-dashboard/src/shared/ui/trust-view/TrustMetadata.tsx",
                "apps/runtime-dashboard/src/shared/ui/trust-view/TrustViewToggle.test.tsx",
                "apps/runtime-dashboard/src/shared/ui/trust-view/TrustViewToggle.tsx",
            },
            {
                resolution["origin_identity"]["source_path"]
                for resolution in c11_resolutions
            },
        )
        self.assertTrue(
            all(
                resolution["classification"] == "shared_dependency_inverted"
                and resolution["closure_test_ref"]
                == "apps/runtime-dashboard/src/shared/ui/trust-view/trustViewArchitecture.test.ts"
                for resolution in c11_resolutions
            )
        )
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

    def test_lifecycle_corruption_probes_exercise_marker_preserving_property_removal(
        self,
    ) -> None:
        manifest = _manifest()
        path = "apps/runtime-dashboard/src/shared/charts/quantityChartSemantics.tsx"
        binding = next(
            row
            for row in manifest["lint"]["resolution_content_bindings"]
            if row["cluster_id"] == "C07" and row["path"] == path
        )
        binding["sha256"] = hashlib.sha256(
            _always_null_c07_scalar_bytes()
        ).hexdigest()

        escaped = checker._baseline_corruption_probes(manifest)

        self.assertIn(
            "lint-c07-scalar-property-removed-markers-retained",
            escaped,
        )


if __name__ == "__main__":
    unittest.main()
