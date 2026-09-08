"""Check compact collection reconciliation against an actual independent JUnit run."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from xml.etree import ElementTree

CAPTURE = "docs.superpowers.journals.gy-phase5-evidence.shared.capture"
RECONCILE = "docs.superpowers.journals.gy-phase5-evidence.shared.reconcile_pytest"
with tempfile.TemporaryDirectory(dir=Path.cwd() / ".tmp", prefix="corr-reconcile-") as scratch:
    root = Path(scratch)
    test = root / "test_synthetic_reconcile.py"
    test.write_text(
        "synthetic = True\ndef test_capture_identity():\n    assert synthetic is True\n"
    )
    receipt = root / "execution.json"
    subprocess.run(  # noqa: S603 - fixed local probe argv
        [sys.executable, "-m", CAPTURE, str(receipt), sys.executable, "-m", "pytest",
         str(test), "-q", f"--junitxml={root / 'execution.xml'}"],
        check=True, capture_output=True, text=True,
    )
    result = subprocess.run(  # noqa: S603 - fixed local probe argv
        [sys.executable, "-m", RECONCILE, str(receipt), "--compact"],
        check=False, capture_output=True, text=True,
    )
    text = result.stdout
    record = json.loads(text[text.index('{\n  "denominator"'):])
    sys.stdout.write(json.dumps({"returncode": result.returncode, "record": record}) + "\n")
    if "collected_identities" in record or "executed_identities" in record:
        raise AssertionError("compact_reconciliation_repeats_derived_identity_sets")
    if result.returncode or record["collected_identity_hash"] != record["executed_identity_hash"]:
        raise AssertionError("independent_reconciliation_did_not_match")
    if record["collected_count"] != 1 or record["executed_count"] != 1:
        raise AssertionError("complete_probe_denominator_changed")
    tree = ElementTree.parse(root / "execution.xml")  # noqa: S314 - own local JUnit
    suite = tree.find(".//testsuite")
    case = suite.find("testcase")
    suite.remove(case)
    tree.write(root / "execution.xml")
    missing = subprocess.run(  # noqa: S603 - fixed local probe argv
        [sys.executable, "-m", RECONCILE, str(receipt), "--compact"],
        check=False, capture_output=True, text=True,
    )
    missing_record = json.loads(missing.stdout[missing.stdout.index('{\n  "denominator"'):])
    sys.stdout.write(json.dumps({"removal_returncode": missing.returncode,
                                "record": missing_record}) + "\n")
    if missing.returncode != 1 or len(missing_record["missing_executions"]) != 1:
        raise AssertionError("missing_execution_did_not_fail_identity_reconciliation")
