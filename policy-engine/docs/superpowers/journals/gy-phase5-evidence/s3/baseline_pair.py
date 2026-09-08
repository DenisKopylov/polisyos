"""Execute the exact two education nodes from the registered immutable slice base."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parents[5]
    baseline = root.parents[1] / "gyphase5-lane-basecheck" / "policy-engine"
    command = [".venv/bin/python", "-m", "pytest",
        "tests/unit/runtime/quality/test_intervention_substrate.py::test_pack_lever_resolution_returns_typed_candidate_unbound",
        "tests/unit/runtime/quality/test_intervention_substrate.py::test_pack_context_fences_first_vertical_knob_fallback",
        "-q", "--tb=short"]
    environment = os.environ.copy()
    environment["PATH"] = str(baseline / ".venv/bin") + os.pathsep + environment["PATH"]
    environment["PYTHONPATH"] = ".:src"
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=baseline, text=True).strip()
    branch = subprocess.check_output(["git", "symbolic-ref", "--short", "HEAD"],
                                     cwd=baseline, text=True).strip()
    assert head == "3d572c146f9d021cb6daad64ebb7b093121ed124"
    assert branch == "codex/gyphase5-lane-basecheck"
    result = subprocess.run(command, cwd=baseline, env=environment, text=True, capture_output=True)
    print(json.dumps({"cwd": str(baseline), "command": command, "PATH": environment["PATH"],
                      "PYTHONPATH": environment["PYTHONPATH"], "head": head, "branch": branch,
                      "return_code": result.returncode, "stdout": result.stdout,
                      "stderr": result.stderr}, indent=2))
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
