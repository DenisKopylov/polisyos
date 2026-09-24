"""Exercise the research census through its real JSON command and read boundary."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

PRODUCT = Path(__file__).resolve().parents[3]
SCRIPT = Path(
    os.environ.get(
        "VOCAB_CENSUS_SCRIPT",
        PRODUCT / "docs/research/policy-operations/correspondence-vocabularies/source_census.py",
    )
)
RAW = Path(
    os.environ.get(
        "VOCAB_CENSUS_RAW",
        PRODUCT / "docs/superpowers/journals/correspondence/vocabularies/raw/census-probes",
    )
)


class SourceCensusTests(unittest.TestCase):
    """Verify lexical presence, ambiguous reads and exclusions without owner inference."""

    def setUp(self) -> None:
        """Create an isolated tracked corpus under ignored repository scratch."""
        RAW.mkdir(parents=True, exist_ok=True)
        self.directory = tempfile.TemporaryDirectory(dir=RAW)
        self.addCleanup(self.directory.cleanup)
        self.repo = Path(self.directory.name)
        self.git("init", "-q")
        self.write("policy-engine/src/polisyos/ir/a.py", b"class NormativeAuditStatus: pass\n")
        self.write("policy-engine/src/polisyos/foundry/b.py", b"estimand = 1\n")
        self.write("policy-engine/src/polisyos/ir/skip.ts", b"assurance_level")
        self.write("docs/demand.py", b"assurance_level")
        self.git("add", ".")
        self.git(
            "-c",
            "user.name=Census fixture",
            "-c",
            "user.email=fixture@example.invalid",
            "-c",
            "commit.gpgsign=false",
            "commit",
            "-qm",
            "Fixture corpus",
        )

    def git(self, *args: str) -> None:
        """Run a Git fixture operation, failing on incomplete setup."""
        subprocess.run(["git", "-C", str(self.repo), *args], check=True, capture_output=True)

    def write(self, name: str, data: bytes) -> None:
        """Write exact fixture bytes."""
        path = self.repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def run_census(self, suffix: str = "") -> tuple[int, dict[str, Any]]:
        """Call the actual research command and retain its complete deciding output."""
        process = subprocess.run(
            [sys.executable, str(SCRIPT), "--repo", str(self.repo)],
            capture_output=True,
            check=False,
        )
        name = self.id().split(".")[-1] + suffix
        (RAW / f"{name}.stdout.json").write_bytes(process.stdout)
        (RAW / f"{name}.stderr.txt").write_bytes(process.stderr)
        (RAW / f"{name}.exit.json").write_text(json.dumps({"exit_code": process.returncode}))
        return process.returncode, json.loads(process.stdout)

    def test_capitalised_counterexample_is_found(self) -> None:
        code, receipt = self.run_census()
        assert code == 0
        assert receipt["enumerated_denominator"] == 2
        assert receipt["independent_tree_denominator"] == 2
        term = receipt["terms"]["normative"]
        assert term["case_sensitive"]["observed_matching_files"] == 0
        assert term["case_insensitive"]["matching_paths"] == ["policy-engine/src/polisyos/ir/a.py"]

    def test_outside_only_evidence_stays_unresolved(self) -> None:
        code, receipt = self.run_census()
        assert code == 0
        assert (
            receipt["terms"]["assurance_level"]["case_insensitive"]["observed_matching_files"] == 0
        )
        assert (
            "unselected_authority_documents_and_other_roots_or_suffixes"
            in receipt["unresolved_by_construction"]
        )
        read_paths = {entry["path"] for entry in receipt["file_reads"]}
        assert "docs/demand.py" not in read_paths
        assert "policy-engine/src/polisyos/ir/skip.ts" not in read_paths

    def test_missing_tracked_input_is_ambiguous(self) -> None:
        (self.repo / "policy-engine/src/polisyos/ir/a.py").unlink()
        code, receipt = self.run_census()
        assert code == 2
        assert receipt["status"] == "UNRUN"
        assert receipt["enumerated_denominator"] == 2
        assert receipt["successful_read_denominator"] == 1
        assert any(entry["status"] == "ambiguous" for entry in receipt["file_reads"])

    def test_unreadable_utf8_input_is_ambiguous(self) -> None:
        self.write("policy-engine/src/polisyos/ir/a.py", b"\xff")
        code, receipt = self.run_census()
        assert code == 2
        assert receipt["status"] == "UNRUN"
        assert any(
            "UnicodeDecodeError" in entry.get("error", "") for entry in receipt["file_reads"]
        )

    def test_changed_bytes_change_result_and_receipt(self) -> None:
        _, before = self.run_census("-before")
        self.write("policy-engine/src/polisyos/ir/a.py", b"class Estimand: pass\n")
        code, after = self.run_census("-after")
        assert code == 0
        assert before["file_reads"] != after["file_reads"]
        assert after["terms"]["estimand"]["case_insensitive"]["observed_matching_files"] == 2
        assert after["working_tree_delta_from_head"]

    def test_untracked_python_is_not_silently_admitted(self) -> None:
        self.write("policy-engine/src/polisyos/ir/new.py", b"assurance_level")
        code, receipt = self.run_census()
        assert code == 0
        assert receipt["enumerated_denominator"] == 2
        assert "untracked_files_and_other_revisions" in receipt["unresolved_by_construction"]


if __name__ == "__main__":
    unittest.main()
