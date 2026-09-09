"""Exercise surgical mutation, real child observation, and timeout restoration."""

# ruff: noqa: PT009 -- This standalone stdlib runner avoids runtime pytest imports.

from __future__ import annotations

import importlib
import json
import tempfile
import unittest
from pathlib import Path


class CorruptionHarnessTest(unittest.TestCase):
    """Keep the harness independent of expensive runtime owner imports."""

    def _exercise(self, *, timeout: bool = False, numeric: bool = False) -> dict:
        owner = importlib.import_module(
            "docs.superpowers.journals.corr-evidence.shared.report_artifact_corruption"
        )
        scratch = Path(".tmp/corr-report-corruption-probe")
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as temporary:
            root = Path(temporary).resolve()
            artifact = root / "artifact.json"
            original = b'{\n  "a/b": { "~flag": true, "spend": 1.25e1 }, "same": true\n}\n'
            artifact.write_bytes(original)
            (root / "checker.py").write_text(
                "import json, pathlib, sys, time\n"
                "print(pathlib.Path('artifact.json').read_text(), flush=True)\n"
                "print('child stderr retained', file=sys.stderr, flush=True)\n"
                + ("time.sleep(30)\n" if timeout else "raise SystemExit(1)\n"),
                encoding="utf-8",
            )
            evidence = owner.run_probe(
                artifact=Path("artifact.json"), checker_module="checker",
                pointer="/a~1b/spend" if numeric else "/a~1b/~0flag",
                replacement=13.5 if numeric else False, checker_args=["--check"],
                timeout_seconds=2 if timeout else 10, root=root,
            )
            self.assertEqual(artifact.read_bytes(), original)
            self.assertTrue(evidence["byte_identical_restoration"])
            self.assertTrue(evidence["only_selected_token_changed"])
            self.assertIn("child stderr retained", evidence["stderr"])
            observed = json.loads(evidence["stdout"])
            self.assertEqual(observed["a/b"]["spend"], 13.5 if numeric else 12.5)
            self.assertIs(observed["a/b"]["~flag"], numeric)
            self.assertIs(observed["same"], True)
            return evidence

    def test_real_child_observes_only_selected_boolean(self) -> None:
        evidence = self._exercise()
        self.assertEqual(evidence["returncode"], 1)
        self.assertFalse(evidence["timed_out"])

    def test_real_child_observes_only_selected_numeric_leaf(self) -> None:
        evidence = self._exercise(numeric=True)
        self.assertEqual(evidence["original_value"], 12.5)
        self.assertEqual(evidence["mutated_value"], 13.5)

    def test_timeout_restores_bytes_and_retains_partial_child_output(self) -> None:
        evidence = self._exercise(timeout=True)
        self.assertTrue(evidence["timed_out"])
        self.assertEqual(evidence["disposition"], "harness_nonreceipt")


if __name__ == "__main__":
    unittest.main()
