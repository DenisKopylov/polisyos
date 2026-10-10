from __future__ import annotations

import ast
import shutil
import subprocess
import sys
from pathlib import Path

script = Path(__file__).resolve()
repo = next(parent for parent in script.parents if (parent / "src/polisyos").is_dir())
source_root = repo / "src/polisyos"
python_files = sorted(
    path for path in source_root.rglob("*.py") if path.is_file() and not path.is_symlink()
)
tracked = set(
    subprocess.check_output(  # noqa: S603 -- fixed `git ls-files` command, no user input
        [
            shutil.which("git") or "git",
            "ls-files",
            "--",
            "src/polisyos/**/*.py",
            "src/polisyos/*.py",
        ],
        cwd=repo,
        text=True,
    ).splitlines()
)
tracked_python = sorted(path for path in tracked if path.endswith(".py"))
lexical_hits: list[tuple[Path, list[int]]] = []
ast_hits: list[tuple[Path, list[int]]] = []
for path in python_files:
    text = path.read_text(encoding="utf-8")
    lines = [
        index
        for index, line in enumerate(text.splitlines(), start=1)
        if "uncertainty_envelopes" in line or "propagation_report_ref" in line
    ]
    if lines:
        lexical_hits.append((path, lines))
    try:
        tree = ast.parse(text, filename=str(path))
    except SyntaxError:
        continue
    direct_reads = [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute) and node.attr == "uncertainty_envelopes"
    ]
    if direct_reads:
        ast_hits.append((path, sorted(direct_reads)))

output = [
    f"actual Python files under src/polisyos: {len(python_files)}",
    f"tracked Python files under src/polisyos: {len(tracked_python)}",
    f"untracked Python files under src/polisyos: {len(python_files) - len(tracked_python)}",
    f"lexical-hit Python files: {len(lexical_hits)}",
]
for path, lines in lexical_hits:
    output.append(f"LEX {path.relative_to(repo)}")
    content = path.read_text(encoding="utf-8").splitlines()
    for line in lines:
        output.append(f"  {line}: {content[line - 1].strip()}")
output.append(f"AST direct .uncertainty_envelopes reads: {len(ast_hits)} files")
for path, lines in ast_hits:
    output.append(f"AST {path.relative_to(repo)}: {lines}")
sys.stdout.write("\n".join(output) + "\n")
