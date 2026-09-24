"""Bounded tracked-product census with one complete JSON output mode.

Internal research CLI; run from the repository root with product source/tools on
PYTHONPATH. A token census cannot establish semantic task allocation or runtime
invocation. Missing/unreadable selected members leave the run UNRUN and partial.
"""

from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from tools.lib.fs import measure_file_reads, measured_read_bytes

_PATTERNS = {
    "exact_task": r"DS15-MANDATE-INTAKE",
    "signature_scope": r"mandate|delegat|acquisition.admission|admission.bundle",
    "factory": (
        r"AgentActionAuthorityGateway|AcquisitionAuthorityGateway|"
        r"AcquisitionAdmissionBundleProducer|build_production_admission_bundle_producer|"
        r"AcquisitionAdmissionAuthorityConfig|mandate_evidence_provider|"
        r"agent_action_admission_bundle_provider"
    ),
}
_SKIP = {
    ".git",
    ".venv",
    "node_modules",
    "production_data",
    "__pycache__",
    "raw",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "dist",
    "build",
    ".next",
}
_AST_NAMES = re.compile(r"mandate|delegat|admission.?bundle|authority.?gateway", re.I)


def census(root: Path) -> dict[str, Any]:
    """Read every tracked product member and disclose unselected/interpreted boundaries."""
    failures: list[dict[str, str]] = []
    try:
        git_executable = shutil.which("git")
        if git_executable is None:
            raise FileNotFoundError("Git executable unavailable")
        listed = subprocess.run(  # noqa: S603 - fixed Git argv, no caller-supplied command
            [git_executable, "ls-files", "-z", "--", "policy-engine"],
            cwd=root,
            capture_output=True,
            check=False,
        )
        listing = {
            "operation": "git ls-files -z -- policy-engine",
            "returncode": listed.returncode,
            "stdout_sha256": hashlib.sha256(listed.stdout).hexdigest(),
            "stderr": listed.stderr.decode("utf-8", errors="replace"),
        }
        if listed.returncode:
            failures.append({"path": "Git index", "error": "enumeration_failed"})
        tracked = sorted(Path(os.fsdecode(item)) for item in listed.stdout.split(b"\0") if item)
    except OSError as error:
        listing = {"operation": "git ls-files", "error": type(error).__name__}
        tracked = []
        failures.append({"path": "Git index", "error": type(error).__name__})
    walked: set[Path] = set()
    walk_errors: list[str] = []
    for directory, dirs, files in os.walk(
        root / "policy-engine", onerror=lambda e: walk_errors.append(str(e))
    ):
        dirs[:] = [name for name in dirs if name not in _SKIP]
        walked.update((Path(directory) / name).relative_to(root) for name in files)
    failures.extend({"path": "filesystem reconciliation", "error": error} for error in walk_errors)
    results: dict[str, list[Any]] = {name: [] for name in _PATTERNS}
    parsed: list[str] = []
    syntax_failures: list[dict[str, str]] = []
    binary: list[str] = []
    decoded: list[dict[str, str]] = []
    events: list[dict[str, Any]] = []
    with measure_file_reads(root) as reads:
        for relative in tracked:
            try:
                raw = measured_read_bytes(root / relative)
            except OSError as error:
                failures.append({"path": str(relative), "error": type(error).__name__})
                continue
            try:
                content = raw.decode("utf-8")
            except UnicodeError:
                binary.append(str(relative))
                continue
            decoded.append({"path": str(relative), "suffix": relative.suffix})
            lines: list[str] | None = None
            for name, pattern in _PATTERNS.items():
                if not re.search(pattern, content, re.I):
                    continue
                lines = content.splitlines() if lines is None else lines
                for number, line in enumerate(lines, 1):
                    if re.search(pattern, line, re.I):
                        results[name].append(
                            {
                                "path": str(relative),
                                "line": number,
                                "text": line,
                                "case_sensitive": bool(re.search(pattern, line)),
                            }
                        )
            if relative.suffix != ".py":
                continue
            try:
                tree = ast.parse(content, filename=str(relative))
            except (SyntaxError, ValueError) as error:
                syntax_failures.append({"path": str(relative), "error": str(error)})
                continue
            parsed.append(str(relative))
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    if _AST_NAMES.search(node.name):
                        events.append(
                            {
                                "path": str(relative),
                                "line": node.lineno,
                                "kind": type(node).__name__,
                                "name": node.name,
                            }
                        )
                elif isinstance(node, ast.Call):
                    function = node.func
                    name = (
                        function.id
                        if isinstance(function, ast.Name)
                        else (function.attr if isinstance(function, ast.Attribute) else "")
                    )
                    if _AST_NAMES.search(name):
                        events.append(
                            {
                                "path": str(relative),
                                "line": node.lineno,
                                "kind": "Call",
                                "name": name,
                            }
                        )
        complete = not failures and not syntax_failures
        measurement = reads.snapshot(complete_verdict=complete)
    return {
        "status": "COMPLETE" if complete else "UNRUN",
        "coverage": "complete_over_selected_inputs" if complete else "partial",
        "selector": {
            "root": "policy-engine",
            "paths": "Git index; current working-tree bytes",
            "file_types": "all tracked bytes; UTF-8 token interpretation; .py AST only",
            "filesystem_walk_exclusions": sorted(_SKIP),
            "patterns": _PATTERNS,
        },
        "counterexamples": [
            "Outside-selector task evidence leaves semantic allocation undecided.",
            "Unreadable tracked members are ambiguous, not zero evidence.",
            "Case-insensitive tokens and AST definitions differ from runtime callers.",
        ],
        "enumeration": listing,
        "selected_paths": [str(path) for path in tracked],
        "tracked_count": len(tracked),
        "reads_count": len(decoded),
        "text_types": dict(Counter(row["suffix"] for row in decoded)),
        "measurement": measurement,
        "failed": failures,
        "undecodable": binary,
        "ast_parsed_paths": parsed,
        "ast_failed": syntax_failures,
        "ast": events,
        "independent_walk": {
            "tracked_missing_from_walk": sorted(str(path) for path in set(tracked) - walked),
            "untracked_walk_count": len(walked - set(tracked)),
            "untracked_candidate_authority": sorted(
                str(path)
                for path in walked - set(tracked)
                if path.suffix in {".md", ".toml", ".json", ".yaml", ".yml", ".py"}
                and "docs/superpowers/journals/acquisition-movement/" not in str(path)
            ),
        },
        "results": results,
        "unresolved_by_construction": [
            *measurement["unresolved_by_construction"],
            "Untracked/ignored files and semantic task aliases are not authority inputs.",
            "Undecodable binary content is read but not interpreted as authority text.",
            "Dynamic runtime dispatch and external institutional authority remain undecided.",
            "AST syntax failures and unreadable selected members prevent a complete verdict.",
        ],
    }


def main() -> int:
    """Print one full receipt-bearing JSON output; partial runs fail explicitly."""
    result = census(Path.cwd())
    sys.stdout.write(json.dumps(result, indent=2) + "\n")
    return 0 if result["status"] == "COMPLETE" else 2


if __name__ == "__main__":
    raise SystemExit(main())
