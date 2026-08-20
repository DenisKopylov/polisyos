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
from unittest import mock


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


def _expect_equal(expected: object, actual: object) -> None:
    if expected != actual:
        raise AssertionError(f"expected {expected!r}, received {actual!r}")


def _expect_true(value: object, message: str) -> None:
    if not value:
        raise AssertionError(message)


def _c16_resolved_manifest() -> dict[str, object]:
    manifest = copy.deepcopy(_manifest())
    manifest["vitest"].update(
        {
            "disposition": "resolved",
            "command": (
                "/usr/bin/time -p corepack pnpm exec vitest run --reporter=json "
                "--outputFile=../../_build/apps/runtime-dashboard/"
                "ds6-c16-vitest-final.json"
            ),
            "wall_duration_seconds": 515.40,
            "vitest_duration_seconds": 512.9371760253906,
            "exit_code": 0,
            "test_files": {"total": 317, "passed": 317, "failed": 0},
            "tests": {"total": 983, "passed": 983, "failed": 0},
            "failure_set": {
                "hash_algorithm": "sha256",
                "serialization": "RFC8785_JCS",
                "payload": "flat_sorted_failures",
                "sort_key": [
                    "test_file",
                    "test_name",
                    "assertion_line",
                    "assertion_anchor",
                ],
                "sha256": (
                    "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945"
                ),
            },
            "debt_classes": [],
            "receipt_provenance": {
                "receipt_kind": "whole_suite_vitest_json",
                "producer_revision": (
                    "97d0c620836a3e6d33c347a1f7f563aaa9177d0c"
                ),
                "entry_revision": "41a2020d5c2097c30c94807737ba6d3a80323d2e",
                "source_delta_sha256": (
                    "800225190d7a47f68b585db206d6b634bd1c7787ab27bb9c5b8e8e1f5fc2bf8a"
                ),
                "raw_receipt_sha256": (
                    "0621a29ad48454fa57c232206f2eec26267e82ad5285879dacc02bf29ebe79ec"
                ),
                "raw_receipt_bytes": 368353,
                "predicate_provenance": "recomputed",
                "authority_purpose": "c16_landed_whole_suite_release",
                "raw_receipt_availability": "not_persisted_in_repository",
                "source_refs": [
                    {
                        "path": (
                            "docs/plans/active/atlas-slices/"
                            "DS6-evidence-workflow.md"
                        ),
                        "content_sha256": (
                            "8339ef3b2a4c12220e0e205cb66fd5626fe1e81eebdf9cec3aafb7861c34cdad"
                        ),
                    },
                    {
                        "path": (
                            "docs/plans/active/atlas-slices/"
                            "DS6-evidence-workflow-journal.md"
                        ),
                        "content_sha256": (
                            "70bd0986b2b1c1d78e2e9e7e507d5f3f592ede12ccf15b27705d0da24a472eae"
                        ),
                    },
                ],
            },
        }
    )
    return manifest


def _c03_open_manifest() -> dict[str, object]:
    manifest = copy.deepcopy(_manifest())
    manifest["vitest"] = {
        "owner_slice": "DS4",
        "disposition": "rebind_pending",
        "command": (
            "corepack pnpm exec vitest run --reporter=json "
            "--outputFile=../../_build/apps/runtime-dashboard/"
            "ds4-c12-vitest-v2.json"
        ),
        "wall_duration_seconds": 315.06,
        "vitest_duration_seconds": 315.06,
        "exit_code": 1,
        "test_files": {"total": 263, "passed": 262, "failed": 1},
        "tests": {"total": 766, "passed": 763, "failed": 3},
        "failure_set": {
            "hash_algorithm": "sha256",
            "serialization": "RFC8785_JCS",
            "payload": "flat_sorted_failures",
            "sort_key": [
                "test_file",
                "test_name",
                "assertion_line",
                "assertion_anchor",
            ],
            "sha256": (
                "533b0f74d085c34acb3b3dbbffd8a8fa056b023e1b96f93a464902682a9b94dd"
            ),
        },
        "debt_classes": [
            {
                "class_id": "i18n-count-message-parity",
                "owner_slice": "DS6",
                "disposition": "rebind_pending",
                "rationale": (
                    "Three unchanged locale parity cases expose the same "
                    "count-sensitive message without ICU plural syntax or an "
                    "explicit allowlist entry; Ruling 2 assigns this class to DS6."
                ),
                "failure_count": 3,
                "failures": [
                    {
                        "test_file": (
                            "apps/runtime-dashboard/src/shared/i18n/parity.test.ts"
                        ),
                        "test_name": (
                            "locale catalogs > marks all count-sensitive "
                            f"{locale} messages with ICU plural syntax or an "
                            "explicit allowlist entry"
                        ),
                        "assertion_line": 88,
                        "assertion_anchor": (
                            "panels.agentPipeline.overBudget must use ICU plural "
                            "syntax or be justified in COUNT_MESSAGE_ALLOWLIST: "
                            "expected false to be true"
                        ),
                    }
                    for locale in ("en", "uk", "ru")
                ],
            }
        ],
        "parent_reproduction": {
            "revision": "0ef16da1b1a3efe1bce0345cf85163fe4971baaa",
            "command": (
                "corepack pnpm exec vitest run src/shared/i18n/parity.test.ts "
                "src/shared/ui/A11yCoverage.a11y.test.tsx "
                "src/app/providers/TemporalCursorProvider.test.tsx"
            ),
            "wall_duration_seconds": 2.43,
            "exit_code": 1,
            "test_files": {"total": 3, "passed": 1, "failed": 2},
            "tests": {"total": 8, "passed": 4, "failed": 4},
            "matches_full_run_failure_set": True,
        },
    }
    return manifest


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

    def test_vitest_accepts_the_exact_open_or_c16_resolved_lifecycle(self) -> None:
        _expect_equal([], checker.validate_baseline_manifest(_c03_open_manifest()))
        _expect_equal([], checker.validate_baseline_manifest(_c16_resolved_manifest()))

    def test_c03_c16_receipt_is_recomputed_from_landed_content(self) -> None:
        receipt_loader = getattr(checker, "_c03_c16_receipt", None)
        receipt_parser = getattr(checker, "_c03_c16_receipt_from_sources", None)
        _expect_true(callable(receipt_loader), "C16 receipt loader is missing")
        _expect_true(callable(receipt_parser), "C16 receipt parser is missing")
        if not callable(receipt_loader) or not callable(receipt_parser):
            return

        receipt = receipt_loader()
        expected = _c16_resolved_manifest()["vitest"]
        for field in (
            "command",
            "wall_duration_seconds",
            "vitest_duration_seconds",
            "exit_code",
            "test_files",
            "tests",
            "failure_set",
            "debt_classes",
            "receipt_provenance",
        ):
            with self.subTest(field=field):
                _expect_equal(expected[field], receipt[field])

        source_revision = "97d0c620836a3e6d33c347a1f7f563aaa9177d0c"
        sources = {}
        for label, source_ref in {
            "plan": "policy-engine/docs/plans/active/atlas-slices/DS6-evidence-workflow.md",
            "journal": (
                "policy-engine/docs/plans/active/atlas-slices/"
                "DS6-evidence-workflow-journal.md"
            ),
        }.items():
            result = subprocess.run(  # noqa: S603 - fixed test fixture revision
                [  # noqa: S607 - repository tool resolved by the test environment
                    "git",
                    "show",
                    f"{source_revision}:{source_ref}",
                ],
                cwd=REPO_ROOT.parent,
                check=True,
                capture_output=True,
                text=True,
            )
            sources[label] = result.stdout
        _expect_equal(receipt, receipt_parser(sources["plan"], sources["journal"]))

        for label, plan_text, journal_text in (
            (
                "changed_plan_hash",
                sources["plan"].replace(
                    "0621a29ad48454fa57c232206f2eec26267e82ad5285879dacc02bf29ebe79ec",
                    "0" * 64,
                    1,
                ),
                sources["journal"],
            ),
            (
                "changed_journal_count",
                sources["plan"],
                sources["journal"].replace("317/317 files", "316/317 files", 1),
            ),
        ):
            with self.subTest(label=label):
                try:
                    receipt_parser(plan_text, journal_text)
                except ValueError:
                    continue
                raise AssertionError(f"C16 source corruption escaped: {label}")

    def test_c03_c16_git_provenance_is_recomputed_not_self_attested(self) -> None:
        validator = getattr(checker, "_c03_verify_c16_git_provenance", None)
        _expect_true(callable(validator), "C16 Git provenance verifier is missing")
        if not callable(validator):
            return

        provenance = copy.deepcopy(
            _c16_resolved_manifest()["vitest"]["receipt_provenance"]
        )
        validator(provenance)
        for field in ("entry_revision", "source_delta_sha256"):
            with self.subTest(field=field):
                mutation = copy.deepcopy(provenance)
                mutation[field] = "0" * len(str(mutation[field]))
                try:
                    validator(mutation)
                except ValueError:
                    continue
                raise AssertionError(f"C16 Git provenance drift escaped: {field}")

    def test_vitest_resolved_lifecycle_rejects_mixed_or_unmeasured_receipts(self) -> None:
        corruptions = {
            "open_disposition": lambda vitest: vitest.__setitem__(
                "disposition", "rebind_pending"
            ),
            "nonzero_exit": lambda vitest: vitest.__setitem__("exit_code", 1),
            "nonempty_debt": lambda vitest: vitest.__setitem__(
                "debt_classes",
                copy.deepcopy(_c03_open_manifest()["vitest"]["debt_classes"]),
            ),
            "changed_command": lambda vitest: vitest.__setitem__(
                "command", "corepack pnpm exec vitest run --reporter=json"
            ),
            "changed_wall_duration": lambda vitest: vitest.__setitem__(
                "wall_duration_seconds", 515.41
            ),
            "changed_vitest_duration": lambda vitest: vitest.__setitem__(
                "vitest_duration_seconds", 512.0
            ),
            "changed_file_total": lambda vitest: vitest["test_files"].__setitem__(
                "total", 318
            ),
            "changed_test_total": lambda vitest: vitest["tests"].__setitem__(
                "total", 984
            ),
            "nonempty_failure_hash": lambda vitest: vitest["failure_set"].__setitem__(
                "sha256", "0" * 64
            ),
        }
        for label, corrupt in corruptions.items():
            with self.subTest(label=label):
                mutation = _c16_resolved_manifest()
                corrupt(mutation["vitest"])
                _expect_true(
                    checker.validate_baseline_manifest(mutation),
                    f"resolved corruption escaped: {label}",
                )

    def test_vitest_schema_rejects_a_changed_open_signature(self) -> None:
        mutation = _c03_open_manifest()
        mutation["vitest"]["debt_classes"][0]["failures"][0][
            "assertion_anchor"
        ] = "fabricated anchor"
        _expect_true(
            checker._schema_errors(mutation, checker.BASELINE_SCHEMA_PATH),
            "standalone baseline schema admitted a changed C03 anchor",
        )

    def test_resolved_comparator_rejects_empty_or_focused_receipts(self) -> None:
        for label, raw in {
            "empty": {"testResults": []},
            "focused": {
                "testResults": [
                    {
                        "name": "src/shared/i18n/parity.test.ts",
                        "assertionResults": [{"status": "passed"}],
                    }
                ]
            },
        }.items():
            with self.subTest(label=label):
                receipt_path = _write_json(raw)
                _expect_true(
                    checker.compare_vitest_results(
                        _c16_resolved_manifest(), receipt_path
                    ),
                    f"resolved comparator admitted {label} receipt",
                )

    def test_supplemental_producer_rejects_a_mixed_c03_lifecycle(self) -> None:
        mutation = _c16_resolved_manifest()
        mutation["vitest"]["disposition"] = "rebind_pending"
        original_load = checker._load_json

        def load_mixed_baseline(path: Path) -> dict[str, object]:
            if path == checker.BASELINE_PATH:
                return copy.deepcopy(mutation)
            return original_load(path)

        with mock.patch.object(checker, "_load_json", side_effect=load_mixed_baseline):
            try:
                checker._supplemental_findings()
            except ValueError:
                return
        raise AssertionError("supplemental producer admitted mixed C03 lifecycle")

    def test_c03_producer_transitions_only_the_exact_open_receipt(self) -> None:
        producer = getattr(checker, "_c03_resolved_baseline_manifest", None)
        _expect_true(callable(producer), "C03 baseline producer is missing")
        if not callable(producer):
            return

        expected = _c16_resolved_manifest()
        _expect_equal(expected, producer(_c03_open_manifest()))
        _expect_equal(expected, producer(expected))

        for label, mutate in {
            "fourth_identity": lambda manifest: manifest["vitest"]["debt_classes"][0][
                "failures"
            ].append(
                {
                    "test_file": "apps/runtime-dashboard/src/changed.test.ts",
                    "test_name": "changed",
                    "assertion_line": 1,
                    "assertion_anchor": "changed",
                }
            ),
            "changed_signature": lambda manifest: manifest["vitest"]["debt_classes"][
                0
            ]["failures"][0].__setitem__("assertion_anchor", "changed"),
        }.items():
            with self.subTest(label=label):
                mutation = _c03_open_manifest()
                mutate(mutation)
                try:
                    producer(mutation)
                except ValueError:
                    continue
                raise AssertionError(f"C03 admitted corrupted receipt: {label}")

    def test_c03_text_producer_rewrites_only_the_vitest_member(self) -> None:
        producer = getattr(checker, "_c03_resolved_baseline_manifest_text", None)
        _expect_true(callable(producer), "C03 text producer is missing")
        if not callable(producer):
            return

        source = MANIFEST_PATH.read_text(encoding="utf-8")
        member = '\n  "vitest": {'
        next_member = ',\n  "architecture":'
        source_start = source.index(member) + 1
        source_suffix = source.index(next_member, source_start)
        open_lines = json.dumps(
            _c03_open_manifest()["vitest"], indent=2, ensure_ascii=False
        ).splitlines()
        open_member = open_lines[0] + "\n" + "\n".join(
            "  " + line for line in open_lines[1:]
        )
        open_source = (
            source[:source_start]
            + '  "vitest": '
            + open_member
            + source[source_suffix:]
        )

        candidate = producer(open_source)
        _expect_equal(_c16_resolved_manifest(), json.loads(candidate))
        _expect_equal(candidate, producer(candidate))

        source_start = open_source.index(member) + 1
        candidate_start = candidate.index(member) + 1
        source_suffix = open_source.index(next_member, source_start)
        candidate_suffix = candidate.index(next_member, candidate_start)
        _expect_equal(open_source[:source_start], candidate[:candidate_start])
        _expect_equal(open_source[source_suffix:], candidate[candidate_suffix:])

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

    def test_c06_removed_authority_guess_requires_its_behavioral_negative(self) -> None:
        mutation = copy.deepcopy(_manifest())
        resolution = next(
            row
            for row in mutation["lint"]["resolutions"]
            if row["cluster_id"] == "C06"
            and row["classification"] == "authority_guess_removed"
            and row["origin_identity"]["path"]
            == "apps/runtime-dashboard/src/features/runs/domain/publicationPacket.ts"
        )
        resolution["closure_test_ref"] = (
            "apps/runtime-dashboard/src/shared/ui/quantity/quantityDecisionProducers.test.tsx"
        )

        errors = checker.validate_baseline_manifest(mutation)

        self.assertIn(
            "lint_c06_semantic_closure_drift:"
            + resolution["origin_identity_sha256"],
            errors,
        )

    def test_c06_reclassifies_the_removed_readiness_fallbacks(self) -> None:
        manifest = _manifest()
        resolutions = [
            row
            for row in manifest["lint"]["resolutions"]
            if row["cluster_id"] == "C06"
        ]

        self.assertEqual(
            {"quantity_enveloped": 8, "authority_guess_removed": 9, "collection_control": 2, "parser_control": 1},
            dict(checker.Counter(row["classification"] for row in resolutions)),
        )
        by_origin = {row["origin_identity_sha256"]: row for row in resolutions}
        for origin_id in (
            "4159737e7aac6623c40d68894cff3363d4532f1378c48141c463396799d768a9",
            "4b9c4586ac6aa14f97e0b28129e18894fd948ff2f8239740a24a4648b8df690b",
        ):
            self.assertEqual(by_origin[origin_id]["classification"], "authority_guess_removed")

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
        self.assertEqual(architecture["disposition"], "resolved")
        self.assertEqual(architecture["exit_code"], 0)
        self.assertEqual(architecture["violation_count"], 0)
        self.assertEqual(architecture["source_file_count"], 0)
        self.assertEqual(
            architecture["identity_set_sha256"], checker._canonical_sha256([])
        )
        self.assertEqual(architecture["violations"], [])
        self.assertEqual(len(architecture["resolutions"]), 36)
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
        c18_resolution = next(
            resolution
            for resolution in architecture["resolutions"]
            if resolution["cluster_id"] == "C18"
        )
        self.assertEqual(c18_resolution["classification"], "feature_public_barrel")
        self.assertEqual(
            c18_resolution["origin_identity"],
            {
                "source_path": "apps/runtime-dashboard/src/app/workspaces.ts",
                "source_content_sha256": (
                    "df8e3785d0baa2e30af4cf68567c2fe33dc736adfc0babd64d268241e1bfc4b3"
                ),
                "line": 9,
                "specifier": "@/features/runs/api/useRunsSample",
                "resolved_target_path": (
                    "apps/runtime-dashboard/src/features/runs/api/useRunsSample.ts"
                ),
                "rule_id": "app-no-feature-internals",
                "message": (
                    "app layer can import features only through their public index.ts barrel."
                ),
                "display": (
                    "src/app/workspaces.ts:9 -> @/features/runs/api/useRunsSample :: "
                    "app layer can import features only through their public index.ts barrel."
                ),
            },
        )
        self.assertEqual(checker.validate_baseline_manifest(manifest), [])

    def test_architecture_partition_rejects_a_missing_resolution(self) -> None:
        mutation = copy.deepcopy(_manifest())
        mutation["architecture"]["resolutions"].pop()

        errors = checker.validate_baseline_manifest(mutation)

        self.assertIn("architecture_partition_missing_identity", errors)

    def test_architecture_origin_rejects_rewritten_producer_provenance(
        self,
    ) -> None:
        mutation = copy.deepcopy(_manifest())
        mutation["architecture"]["immutable_origin"]["producer_sha256"] = "0" * 64

        errors = checker.validate_baseline_manifest(mutation)

        self.assertIn("architecture_immutable_origin_anchor_drift", errors)

    def test_architecture_comparator_rejects_the_revived_c18_edge_from_zero(
        self,
    ) -> None:
        manifest = _manifest()
        c18_resolution = next(
            resolution
            for resolution in manifest["architecture"]["resolutions"]
            if resolution["cluster_id"] == "C18"
        )
        empty_path = _write_json({"violations": []})
        revived_path = _write_json(
            {"violations": [c18_resolution["origin_identity"]]}
        )
        self.addCleanup(empty_path.unlink)
        self.addCleanup(revived_path.unlink)

        self.assertEqual(
            checker.compare_architecture_results(manifest, empty_path),
            [],
        )
        errors = checker.compare_architecture_results(manifest, revived_path)
        self.assertTrue(
            any(error.startswith("architecture_new_violation:") for error in errors),
            errors,
        )

    def test_architecture_c18_rejects_shared_dependency_classification(
        self,
    ) -> None:
        mutation = copy.deepcopy(_manifest())
        resolution = next(
            row
            for row in mutation["architecture"]["resolutions"]
            if row["cluster_id"] == "C18"
        )
        resolution["classification"] = "shared_dependency_inverted"

        errors = checker.validate_baseline_manifest(mutation)

        self.assertTrue(
            any("feature_public_barrel" in error for error in errors),
            errors,
        )

    def test_architecture_non_c18_rejects_feature_public_barrel_classification(
        self,
    ) -> None:
        for cluster_id in ("C09", "C10", "C11"):
            with self.subTest(cluster_id=cluster_id):
                mutation = copy.deepcopy(_manifest())
                resolution = next(
                    row
                    for row in mutation["architecture"]["resolutions"]
                    if row["cluster_id"] == cluster_id
                )
                resolution["classification"] = "feature_public_barrel"

                errors = checker.validate_baseline_manifest(mutation)

                self.assertTrue(
                    any("shared_dependency_inverted" in error for error in errors),
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

    def test_lifecycle_corruption_probes_still_reject_marker_preserving_property_removal_when_the_hash_is_laundered(
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

        self.assertNotIn(
            "lint-c07-scalar-property-removed-markers-retained",
            escaped,
        )


if __name__ == "__main__":
    unittest.main()
