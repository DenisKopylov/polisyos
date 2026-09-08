"""Format only the added captured literal; preserve every decoded value and other source."""
# ruff: noqa: S101, S603, T201 - append-only research transformation witness
from __future__ import annotations

import ast
import io
import json
import subprocess
import sys
import tokenize
from pathlib import Path

owner = Path("src/polisyos/runtime/http/openapi_contract.py")
source = owner.read_text()
assignment = next(
    node for node in ast.parse(source).body
    if isinstance(node, ast.AnnAssign)
    and isinstance(node.target, ast.Name)
    and node.target.id == "_NORMATIVE_EVIDENCE_FIXTURE_RESPONSE"
)
before = ast.literal_eval(assignment.value)
snippet = "_NORMATIVE_EVIDENCE_FIXTURE_RESPONSE: dict[str, Any] = " + repr(before)
offsets = [0]
for line in snippet.splitlines(keepends=True):
    offsets.append(offsets[-1] + len(line))
edits = []
for token in tokenize.generate_tokens(io.StringIO(snippet).readline):
    if token.type != tokenize.STRING:
        continue
    value = ast.literal_eval(token.string)
    if not isinstance(value, str) or len(value) <= 48:
        continue
    start = offsets[token.start[0] - 1] + token.start[1]
    end = offsets[token.end[0] - 1] + token.end[1]
    chunks = [repr(value[index:index + 48]) for index in range(0, len(value), 48)]
    edits.append((start, end, "(\n" + "\n".join(chunks) + "\n)"))
for start, end, replacement in reversed(edits):
    snippet = snippet[:start] + replacement + snippet[end:]
command = [sys.executable, "-m", "ruff", "format", "--stdin-filename", str(owner), "-"]
formatted = subprocess.run(command, input=snippet, text=True, capture_output=True, check=False)
if formatted.returncode:
    print(formatted.stdout)
    print(formatted.stderr, file=sys.stderr)
    raise SystemExit(formatted.returncode)
updated = ast.parse(formatted.stdout).body[0]
assert isinstance(updated, ast.AnnAssign)
assert ast.literal_eval(updated.value) == before
lines = source.splitlines(keepends=True)
start = sum(map(len, lines[:assignment.lineno - 1]))
end = sum(map(len, lines[:assignment.end_lineno]))
owner.write_text(source[:start] + formatted.stdout + source[end:])
print(json.dumps({
    "formatter_argv": command,
    "formatter_returncode": formatted.returncode,
    "formatter_stderr": formatted.stderr,
    "source_outside_captured_literal_unchanged": True,
    "all_captured_values_unchanged": ast.literal_eval(updated.value) == before,
}, indent=2))
