"""Read-only bounded census; incomplete selected inputs never certify absence."""

from __future__ import annotations

import ast
import hashlib
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
OUT = Path(__file__).resolve().parent / "raw"
OUTPUT_NAME = "census-with-read-boundaries.json"


class ResearchReads:
    """Record actual byte reads and failures for these internal research callers."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.successful: list[dict[str, object]] = []
        self.failed: list[dict[str, str]] = []
        self.git_operations: list[dict[str, object]] = []

    def fail(self, path: str, operation: str, exc: Exception) -> None:
        self.failed.append({"path": path, "operation": operation, "error": repr(exc)})

    def text(self, relative: str) -> str | None:
        try:
            data = (self.root / relative).read_bytes()
        except Exception as exc:
            self.fail(relative, "read_bytes", exc)
            return None
        self.successful.append(
            {"path": relative, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
        )
        try:
            return data.decode("utf-8")
        except UnicodeDecodeError as exc:
            self.fail(relative, "decode_utf8", exc)
            return None

    def git(self, arguments: list[str]) -> str | None:
        command = ["git", *arguments]
        try:
            # Internal callers supply only fixed read-only Git queries, never user command text.
            result = subprocess.run(  # noqa: S603
                command, cwd=self.root, capture_output=True, check=False
            )
            self.git_operations.append(
                {
                    "command": command,
                    "cwd": str(self.root),
                    "returncode": result.returncode,
                    "stdout_bytes": len(result.stdout),
                    "stdout_sha256": hashlib.sha256(result.stdout).hexdigest(),
                    "stderr": result.stderr.decode("utf-8", errors="replace"),
                }
            )
            if result.returncode:
                raise RuntimeError(f"Git input command exited {result.returncode}")
            return result.stdout.decode("utf-8")
        except Exception as exc:
            self.fail(".git", " ".join(command), exc)
            return None

    def fields(self) -> dict[str, object]:
        return {
            "status": "UNRUN" if self.failed else "COMPLETE",
            "coverage": "partial" if self.failed else "complete_selected_inputs",
            "successful_reads": self.successful,
            "failed_attempts": self.failed,
            "ambiguous": self.failed,
            "git_operations": self.git_operations,
        }


def emit_result(result: dict[str, object], path: Path | None = None) -> int:
    """Emit the same complete receipt to stdout and, when selected, one local file."""

    result["unresolved_by_construction"].append(
        "instrument interpreter and import dependency reads are outside the explicit input receipt"
    )
    rendered = json.dumps(result, indent=2) + "\n"
    if path is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(rendered)
    sys.stdout.write(rendered)
    return 1 if result["status"] == "UNRUN" else 0


def main() -> int:
    selectors = ["src", "tools", "tests"]
    measured = ResearchReads(ROOT)
    tracked = measured.git(["ls-files", "-z", "--", *selectors])
    tree = measured.git(["ls-tree", "-rz", "--name-only", "HEAD", "--", *selectors])
    source_set = {p for p in (tracked or "").split("\0") if p.endswith(".py")}
    tree_set = {p for p in (tree or "").split("\0") if p.endswith(".py")}
    names = {
        "plan_evidence_acquisition",
        "plan_requirement_gap_acquisition",
        "derive_growth_backlog",
        "plan_from_required_data",
    }
    calls, defs, token_hits = [], [], []
    pattern = re.compile(
        r"\b(?:evsi|evpi|expected_value|expected_cost|value_of_information)\b", re.I
    )
    for relative in sorted(source_set):
        source = measured.text(relative)
        if source is None:
            continue
        try:
            parsed = ast.parse(source, filename=relative)
        except Exception as exc:
            measured.fail(relative, "ast.parse", exc)
            continue
        aliases = {}
        for node in ast.walk(parsed):
            if isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    aliases[alias.asname or alias.name] = alias.name
        for node in ast.walk(parsed):
            if (
                isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and node.name.casefold() in names
            ):
                defs.append({"path": relative, "line": node.lineno, "name": node.name})
            if isinstance(node, ast.Call):
                name = (
                    node.func.id
                    if isinstance(node.func, ast.Name)
                    else node.func.attr
                    if isinstance(node.func, ast.Attribute)
                    else ""
                )
                resolved = aliases.get(name, name)
                if resolved.casefold() in names:
                    calls.append(
                        {
                            "path": relative,
                            "line": node.lineno,
                            "name": resolved,
                            "call": ast.unparse(node),
                        }
                    )
        if pattern.search(source):
            token_hits.append(relative)
    artifact = "architecture/policy_design_case/layer3_gy_n13a_acquisition_census.json"
    artifact_text = measured.text(artifact)
    rows = None
    if artifact_text is not None:
        try:
            data = json.loads(artifact_text)
            backlog = data["growth_backlog"]
            keys = sorted({key for row in backlog for key in row})
            independent_ids = [row["variable_id"] for row in data["reverse_demand_residuals"]]
            absent_keys = [
                "voi_ranking_ref",
                "decision_owner_ref",
                "decision_ref",
                "ranking_ref",
                "owner_decision",
                "expected_value",
                "expected_cost",
                "cost_basis",
            ]
            rows = {
                "artifact": next(item for item in measured.successful if item["path"] == artifact),
                "row_denominator": len(backlog),
                "row_ids": [row["variable_id"] for row in backlog],
                "keys": keys,
                "independent_reverse_residual_ids": independent_ids,
                "residual_symmetric_difference": sorted(
                    set(independent_ids) ^ {row["variable_id"] for row in backlog}
                ),
                "distributions": {
                    key: dict(Counter(str(row.get(key)) for row in backlog))
                    for key in [
                        "voi_owner_fit",
                        "authority_boundary",
                        "ranking_method",
                        "binding_confidence",
                        "ranking_score",
                        "voi_owner_ref",
                    ]
                },
                "key_occurrences_case_insensitive": {
                    key: sum(any(k.casefold() == key for k in row) for row in backlog)
                    for key in absent_keys
                },
            }
        except Exception as exc:
            measured.fail(artifact, "JSON row interpretation", exc)
    head = measured.git(["rev-parse", "HEAD"])
    result = {
        "counterexample_before_search": "A later or aliased producer may already bind metric "
        "residuals to real VOI inputs; use AST calls and case-insensitive semantic tokens.",
        "head": head.strip() if head else None,
        "selector": selectors,
        "file_type_denominator": {".py": len(source_set), ".json": 1},
        "exclusions": [
            "untracked files",
            "non-Python files in source roots",
            "Python paths outside selected roots",
            "all other artifacts",
        ],
        "independent_tree_difference": sorted(source_set ^ tree_set),
        "definitions": defs,
        "calls": calls,
        "case_insensitive_semantic_token_files": token_hits,
        "numeric_rows": rows,
        "unresolved_by_construction": [
            "dynamic Python dispatch",
            "non-Python producers",
            "external artifact stores",
            "semantic meaning not established by token matching",
            "unselected authority documents",
            "unselected Python paths outside src/tools/tests",
            "untracked implementations",
            "lexical receiver and alias equivalence not established",
            "historical education native/Git input closure",
            "Git internal reads are subprocess-scoped",
        ],
        **measured.fields(),
    }
    return emit_result(result, OUT / OUTPUT_NAME)


if __name__ == "__main__":
    raise SystemExit(main())
