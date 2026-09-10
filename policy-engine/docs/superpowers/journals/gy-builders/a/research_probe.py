"""Read-only complete source census and existing-owner execution for GY-AQ1."""

from __future__ import annotations

import ast
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path


def main() -> None:
    """Cross-check source sets and exercise canonical persistence primitives."""
    root = Path.cwd()
    source = root / "src"
    first = {str(path.relative_to(root)) for path in source.rglob("*.py")}
    tracked = subprocess.check_output(
        ["git", "ls-files", "-z", "src"], text=True
    ).split("\0")
    second = {path for path in tracked if path.endswith(".py")}
    assert first == second, (sorted(first - second), sorted(second - first))
    tokens = ("non_data_acquisition", "AuthorityCeiling", "GapShapeAssessment")
    matches = {token: [] for token in tokens}
    ambiguous = []
    for name in sorted(first):
        try:
            text = (root / name).read_text()
            ast.parse(text)
        except (UnicodeError, SyntaxError) as exc:
            ambiguous.append({"path": name, "error": str(exc)})
            continue
        for token in tokens:
            if token in text:
                matches[token].append(name)
    independent = {}
    for token in tokens:
        run = subprocess.run(
            ["rg", "-l", "--fixed-strings", "--glob", "*.py", token, "src"],
            text=True, capture_output=True, check=False,
        )
        assert run.returncode in (0, 1), run.stderr
        independent[token] = sorted(run.stdout.splitlines())
        assert matches[token] == independent[token]
    print(json.dumps({"denominator_path": "policy-engine/src/**/*.py",
                      "pathlib_python_files": len(first),
                      "git_python_files": len(second), "ambiguous": ambiguous,
                      "token_matching_files": matches,
                      "independent_rg_matching_files": independent}, indent=2))
    assert not ambiguous
    from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
    from polisyos.fabric.data_plane.evidence_journal import (
        append_fsync_jsonl,
        resolve_journal_event_ref,
    )
    from polisyos.runtime.quality.acquisition_planner import (
        AcquisitionGapType,
        AcquisitionStrategy,
    )

    scratch = root / "_build" / ".tmp"
    scratch.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=scratch, prefix="aq1-research-") as temporary:
        store = FileSystemCAS(Path(temporary) / "cas")
        blob = b'{"authority":"candidate_only","missing_object":"legal_mandate"}'
        ref = store.put_bytes(
            blob, opts=PutOptions(kind="research.non_data_candidate", media_type="application/json")
        )
        assert store.get_bytes(ref.artifact_id) == blob
        assert str(ref.artifact_id) == "sha256:" + hashlib.sha256(blob).hexdigest()
        event_ref = append_fsync_jsonl(
            Path(temporary) / "events.jsonl",
            {"sequence": 1, "event_kind": "research.non_data_candidate",
             "artifact_ref": str(ref.artifact_id), "authority": "candidate_only"},
        )
        assert resolve_journal_event_ref(event_ref)["artifact_ref"] == str(ref.artifact_id)
        print(json.dumps({"existing_cas_roundtrip": "pass",
                          "existing_journal_roundtrip": "pass",
                          "planner_gap_vocabulary": [item.value for item in AcquisitionGapType],
                          "planner_strategy_vocabulary": [item.value for item in AcquisitionStrategy]},
                         indent=2))


if __name__ == "__main__":
    main()
