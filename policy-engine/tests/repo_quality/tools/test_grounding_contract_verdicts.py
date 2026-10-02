"""Stdlib CLI witnesses for typed CG1/CG2 checker verdicts."""

from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from tools.quality.validation import check_grounding_bind_contract as cg2
from tools.quality.validation import check_grounding_relation_contract as cg1


class GroundingContractVerdictTests(unittest.TestCase):
    """Check CLI status and disclosure without invoking product runtimes."""

    def test_unexpected_read_error_is_redacted_unrun_for_both_checkers(self) -> None:
        for checker in (cg1, cg2):
            with self.subTest(checker=checker.__name__):
                output = io.StringIO()

                def unreadable_input(_repo_root):
                    raise OSError("synthetic read secret must not be rendered")

                with (
                    patch.object(checker, "validate", side_effect=unreadable_input),
                    redirect_stdout(output),
                ):
                    exit_code = checker.main(["--check", "--output-format", "json"])

                rendered = output.getvalue()
                report = json.loads(rendered)
                assert exit_code == 2
                assert report["status"] == "UNRUN"
                assert report["issues"] == [{"code": "inspection_unrun"}]
                failure = report["inspection_failure"]
                assert failure["error_type"] == "OSError"
                assert set(failure["source_frame"]) == {"path", "line", "function"}
                assert "synthetic read secret" not in rendered
                assert report["measurement"]["declared_inputs"]["source_modules"]
                assert report["measurement"]["unresolved_by_construction"]

    def test_completed_checks_keep_pass_and_fail_exit_codes(self) -> None:
        for checker in (cg1, cg2):
            with self.subTest(checker=checker.__name__, status="pass"):
                output = io.StringIO()
                with (
                    patch.object(
                        checker,
                        "validate",
                        return_value={"status": "pass", "issues": []},
                    ),
                    redirect_stdout(output),
                ):
                    exit_code = checker.main(["--check", "--output-format", "json"])
                assert exit_code == 0
                assert json.loads(output.getvalue())["status"] == "pass"

            with self.subTest(checker=checker.__name__, status="fail"):
                output = io.StringIO()
                with (
                    patch.object(
                        checker,
                        "validate",
                        return_value={
                            "status": "fail",
                            "issues": [{"code": "synthetic_semantic_failure"}],
                        },
                    ),
                    redirect_stdout(output),
                ):
                    exit_code = checker.main(["--check", "--output-format", "json"])
                report = json.loads(output.getvalue())
                assert exit_code == 1
                assert report["status"] == "fail"
                assert report["issues"] == [{"code": "synthetic_semantic_failure"}]


if __name__ == "__main__":
    unittest.main()
