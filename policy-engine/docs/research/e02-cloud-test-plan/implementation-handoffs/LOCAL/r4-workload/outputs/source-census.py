import re
import sys
from pathlib import Path

roots = [Path("policy-engine/src/polisyos"), Path("policy-engine/tests")]
patterns = {
    "LocalWorkerPool constructor": re.compile(r"\bLocalWorkerPool\s*\("),
    "LocalWorkerPool symbol": re.compile(r"\bLocalWorkerPool\b"),
    "build_workflow_runner call": re.compile(r"\bbuild_workflow_runner\s*\("),
}


def _emit(value: object) -> None:
    sys.stdout.write(f"{value}\n")


for root in roots:
    files = sorted(root.rglob("*.py"))
    _emit(f"ROOT {root}; denominator={len(files)} files of type .py")
    for name, pattern in patterns.items():
        hits = []
        for path in files:
            try:
                lines = path.read_text(encoding="utf-8").splitlines()
            except UnicodeDecodeError:
                continue
            for number, line in enumerate(lines, 1):
                if pattern.search(line):
                    hits.append((path, number, line.strip()))
        _emit(f"  {name}: {len(hits)} matching lines")
        for path, number, line in hits:
            _emit(f"    {path}:{number}: {line}")
