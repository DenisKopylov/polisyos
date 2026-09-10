"""Retain full child output for one real report-owner source replacement.

Run exclusively: the existing owner temporarily replaces source bytes and
restores them in its finally block before this wrapper returns.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


def main() -> int:
    from tools.quality.validation import check_layer3_gy_promotion_contract as owner

    parser = argparse.ArgumentParser()
    parser.add_argument("mutation_id")
    args = parser.parse_args()
    cases = {case.mutation_id: case for case in owner._source_flip_cases()}
    case = cases[args.mutation_id]
    root = Path.cwd()
    before = {item.relative_path: (root / item.relative_path).read_bytes()
              for item in case.replacements}
    completed_children = []
    actual_run = subprocess.run

    def retain(*values: object, **kwargs: object) -> subprocess.CompletedProcess:
        result = actual_run(*values, **kwargs)
        completed_children.append(result)
        return result

    with patch.object(owner, "subprocess", SimpleNamespace(run=retain)):
        report = owner._run_source_flip_case(root, case)
    restored = all((root / name).read_bytes() == raw for name, raw in before.items())
    sys.stdout.write(json.dumps({
        "mutation_id": case.mutation_id, "owner_report": report,
        "exact_source_restoration": restored,
        "children": [{
            "argv": child.args, "returncode": child.returncode,
            "stdout": child.stdout, "stderr": child.stderr,
        } for child in completed_children],
    }, indent=2) + "\n")
    if not restored or len(completed_children) != 1:
        return 2
    return completed_children[0].returncode


if __name__ == "__main__":
    raise SystemExit(main())
