"""Behavioral input receipts for the registered Atlas enforcement caller."""

from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from typing import Any
from unittest.mock import patch

from architecture.atlas_surfaces.test_atlas_enforcement import (
    checker,
    scope_obligation_manifest,
    write_slice_plan,
)


class ScopeMeasurementTests(unittest.TestCase):
    """Prove input selection cannot turn unparsed ownership into measured absence."""

    def test_scope_measurement_keeps_master_ownership_outside_acknowledgement(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            master = Path(temp_dir) / "master.md"
            master.write_text("# Master\nDebt rows this slice must close: DS12 owns this.\n")
            receipt: dict[str, Any] = {}
            errors = checker.validate_slice_scope_obligations(
                manifest=scope_obligation_manifest(),
                plan_paths=[master],
                measurement=receipt,
            )
            assert errors == []
            assert receipt["selected_plans"] == []
            assert receipt["excluded_plans"][0]["path"] == str(master)
            assert any(
                row["path"] == str(master) and row["status"] == "read" for row in receipt["inputs"]
            )
            assert any(
                "master-plan ownership acts" in value
                for value in receipt["unresolved_by_construction"]
            )

    def test_scope_measurement_preserves_invalid_and_unreadable_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            invalid = Path(temp_dir) / "invalid.md"
            invalid.write_text("---\ntype: [\n---\n")
            missing = Path(temp_dir) / "missing.md"
            receipt: dict[str, Any] = {}
            errors = checker.validate_slice_scope_obligations(
                manifest=scope_obligation_manifest(),
                plan_paths=[invalid, missing],
                measurement=receipt,
            )
            assert errors == []  # Admitted acknowledgements only; no allocation verdict.
            assert receipt["plan_selection_complete"] is False
            assert {row["path"] for row in receipt["unresolved_inputs"]} == {
                str(invalid),
                str(missing),
            }
            assert receipt["excluded_plans"] == []
            assert all(
                row["class"] == "unresolved_by_construction" for row in receipt["unresolved_inputs"]
            )

    def test_scope_measurement_is_printed_even_when_original_obligation_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest = scope_obligation_manifest()
            target = write_slice_plan(
                Path(temp_dir) / "target.md",
                {
                    "type": "slice-plan",
                    "slice": manifest["target_slices"][0],
                },
            )
            receipt: dict[str, Any] = {}
            errors = checker.validate_slice_scope_obligations(
                manifest=manifest,
                plan_paths=[target],
                measurement=receipt,
            )
            assert any(
                error.startswith("slice_scope_obligation_inputs_missing:") for error in errors
            )
            output = StringIO()
            with (
                patch.object(
                    checker,
                    "validate_enforcement",
                    return_value=(errors, {"sliceScopeMeasurement": receipt}),
                ),
                patch.object(checker, "_architecture_recurrence_errors", return_value=([], {})),
                redirect_stdout(output),
                redirect_stderr(StringIO()),
            ):
                assert checker.main(["--check"]) == 1
            printed = json.loads(
                next(
                    line.removeprefix("slice_scope_measurement=")
                    for line in output.getvalue().splitlines()
                    if line.startswith("slice_scope_measurement=")
                )
            )
            assert printed == receipt

    def test_scope_unreadable_manifest_makes_cli_unrun_with_partial_reads(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            missing = Path(temp_dir) / "manifest.json"

            def scope_only() -> object:
                checker.validate_slice_scope_obligations(plan_paths=[])
                raise AssertionError("unreadable manifest must abort")

            output = StringIO()
            with (
                patch.object(checker, "SLICE_SCOPE_OBLIGATIONS_PATH", missing),
                patch.object(checker, "validate_enforcement", side_effect=scope_only),
                redirect_stdout(output),
            ):
                assert checker.main(["--check"]) == 2
            receipt = json.loads(
                next(
                    line.removeprefix("slice_scope_measurement=")
                    for line in output.getvalue().splitlines()
                    if line.startswith("slice_scope_measurement=")
                )
            )
            assert receipt["complete_verdict"] is False
            assert any(
                row["path"] == str(missing) and row["status"] == "unreadable"
                for row in receipt["inputs"]
            )
            assert "UNRUN" in output.getvalue()

    def test_failed_git_enumeration_is_unrun_with_retained_manifest_read(self) -> None:
        def scope_only() -> object:
            checker.validate_slice_scope_obligations()
            raise AssertionError("failed enumeration must abort")
        output = StringIO()
        with (patch.object(checker, "validate_enforcement", side_effect=scope_only),
              patch.object(checker.subprocess, "run", return_value=__import__("subprocess").CompletedProcess(
                  ["git", "ls-files"], 1, "", "enumeration failed")),
              redirect_stdout(output)):
            assert checker.main(["--check"]) == 2
        receipt = json.loads(next(line.removeprefix("slice_scope_measurement=")
                                 for line in output.getvalue().splitlines()
                                 if line.startswith("slice_scope_measurement=")))
        assert receipt["complete_verdict"] is False
        assert any(item["path"].endswith(checker.SLICE_SCOPE_OBLIGATIONS_PATH.name) and item["status"] == "read"
                   for item in receipt["inputs"])
        assert "slice_scope_obligation_plan_enumeration_failed" in output.getvalue()
