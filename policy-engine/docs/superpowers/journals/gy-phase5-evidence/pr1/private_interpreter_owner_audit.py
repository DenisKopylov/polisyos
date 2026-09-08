"""Record the bounded canonical Python environment-owner set without creating environments."""

# ruff: noqa: S101, S603, T201 - read-only Git/stdlib audit and complete evidence output

import ast
import inspect
import json
import re
import subprocess
import sys
import venv
from pathlib import Path

root = Path.cwd()
records = []


def git(*args: str) -> str:
    """Retain a read-only Git command with both complete streams and its real status."""
    argv = ["git", *args]
    result = subprocess.run(argv, cwd=root, capture_output=True, text=True, check=False)
    records.append(
        {
            "argv": argv,
            "cwd": str(root),
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
    )
    assert result.returncode == 0
    return result.stdout


indexed = {
    name for name in git("ls-files", "-z", "--", "src", "tools").split("\0") if name.endswith(".py")
}
committed = {
    name.removeprefix("policy-engine/")
    for name in git("ls-tree", "-r", "--name-only", "-z", "HEAD", "--", "src", "tools").split("\0")
    if name.endswith(".py")
}
assert indexed == committed
ambiguous = []
tokens = []
builders = []
needle = re.compile(r"venv|virtualenv|EnvBuilder|_base_executable|DYLD_|libpython|pyvenv\.cfg")
for relative in sorted(indexed):
    try:
        text = (root / relative).read_text()
        tree = ast.parse(text)
    except (OSError, UnicodeError, SyntaxError) as exc:
        ambiguous.append({"path": relative, "error": repr(exc)})
        continue
    for number, line in enumerate(text.splitlines(), 1):
        if needle.search(line):
            tokens.append({"path": relative, "line": number, "source": line})
    aliases = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            aliases.update({alias.asname or alias.name: alias.name for alias in node.names})
        if isinstance(node, ast.ImportFrom) and node.module:
            aliases.update(
                {alias.asname or alias.name: node.module + "." + alias.name for alias in node.names}
            )
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        rendered = ast.unparse(node.func)
        head, _, rest = rendered.partition(".")
        resolved = aliases.get(head, head) + ("." + rest if rest else "")
        if resolved in {"venv.EnvBuilder", "venv.create", "virtualenv.cli_run", "virtualenv.run"}:
            builders.append(
                {
                    "path": relative,
                    "line": node.lineno,
                    "resolved_owner": resolved,
                    "actual_call": ast.unparse(node),
                }
            )
git(
    "show",
    "6fa919b744c945f686a42ab746bbb3f5dbaa9b79",
    "--",
    "tools/devx/architecture/guardrails.py",
)
registry = root / "docs/plans/active/DEBT-REGISTER.md"
row = [
    line
    for line in registry.read_text().splitlines()
    if line.startswith("| `generated-freshness-probe-rebinds-caller-venv` |")
]
assert len(row) == 1
packet = {
    "denominator": (
        "All tracked production src/**/*.py and tools/**/*.py; independent index/HEAD path sets; "
        "complete AST call and environment-token walks. Non-Python launchers and external "
        "installed tools are outside this owner census."
    ),
    "index_python_identities": sorted(indexed),
    "head_python_identities": sorted(committed),
    "ambiguous": ambiguous,
    "environment_token_findings": tokens,
    "direct_environment_constructor_calls": builders,
    "actual_stdlib_venv_file": venv.__file__,
    "actual_interpreter": sys.executable,
    "actual_base_executable": sys._base_executable,
    "actual_stdlib_setup_python_source": inspect.getsource(venv.EnvBuilder.setup_python),
    "actual_stdlib_ensure_directories_source": inspect.getsource(
        venv.EnvBuilder.ensure_directories
    ),
    "closed_row_verbatim": row,
    "git_commands": records,
}
output = (
    root
    / "docs/superpowers/journals/gy-phase5-evidence/pr1/private-interpreter-owner-complete.json"
)
output.write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n")
print(
    json.dumps(
        {
            "output": str(output),
            "ambiguous": ambiguous,
            "direct_environment_constructor_calls": builders,
            "actual_base_executable": sys._base_executable,
        },
        indent=2,
    )
)
raise SystemExit(bool(ambiguous))
