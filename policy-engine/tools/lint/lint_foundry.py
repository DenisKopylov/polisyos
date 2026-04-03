#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
from dataclasses import dataclass
from pathlib import Path

STANDARD_BANNED_IMPORT_ROOTS = {
    "duckdb",
    "kuzu",
    "pandas",
    "polars",
    "pyarrow",
    "random",
    "requests",
    "httpx",
    "sqlite3",
    "sqlalchemy",
    "subprocess",
    "os",
    "pathlib",
    "shutil",
    "glob",
    "tempfile",
    "dagma",
    "y0",
}

MIXED_ALLOWED_IMPORTS = {
    "numpy",
    "scipy",
    "statsmodels",
    "linearmodels",
    "pandas",
    "dowhy",
    "econml",
    "ortools",
    "pulp",
    "sklearn",
    "causallearn",
    "rustworkx",
    "kuzu",
    "dagma",
    "y0",
}

NO_JAX_BANNED_IMPORTS = {"jax", "jaxlib", "equinox", "optax"}

BANNED_BUILTINS = {"print", "open"}

# ---------------------------------------------------------------------------
# Zone map: declarative path-prefix → zone assignment.
# Evaluated longest-prefix-first so specific paths override broader directories.
# Zones: "infra" (no restrictions), "mixed" (scientific Python allowed),
#         "no_jax" (mixed minus JAX family), "standard" (strict purity).
# ---------------------------------------------------------------------------
ZONE_MAP: dict[str, str] = {
    # infra — orchestration, CLI, simulation, test utilities (no restrictions)
    "plugins/":                          "infra",
    "agent_sim/":                        "infra",
    "runtime/":                          "infra",
    "methods/testing/":                  "infra",
    "methods/cli/":                      "infra",
    "agents.py":                         "infra",
    "methods/base.py":                   "infra",
    "methods/discovery.py":              "infra",
    "methods/_artifacts_fingerprint.py": "infra",
    "methods/cache.py":                  "infra",   # disk-backed result cache
    "methods/hot_reload.py":             "infra",   # file-watcher for dev
    "methods/observability.py":          "infra",   # metrics / tracing
    "methods/compat_matrix.py":          "infra",   # compat report generator
    "methods/composer.py":               "infra",   # chain orchestration
    "methods/deprecation.py":            "infra",   # deprecation warnings
    "methods/backends/checkpointing.py": "infra",   # checkpoint I/O
    "methods/backends/ray_runner.py":    "infra",   # Ray distributed runner
    "_executor_snapshots.py":            "infra",   # state snapshot persistence
    "methods/selection_history.py":      "infra",   # execution history I/O
    # no_jax — causal/econometrics/optimization (mixed minus JAX family)
    "methods/catalog/causal/ci_backends.py": "mixed",  # allowlist override
    "methods/catalog/causal/":           "no_jax",
    "methods/catalog/causal/transport/": "no_jax",
    "methods/catalog/causal/discovery/": "no_jax",
    "methods/catalog/econometrics/":     "no_jax",
    "methods/catalog/optimization/":     "no_jax",
    # mixed — scientific Python allowed
    "methods/backends/":                 "mixed",
    "methods/catalog/":                  "mixed",
}
DEFAULT_ZONE = "standard"

_SORTED_ZONE_ENTRIES: list[tuple[str, str]] | None = None


def _sorted_zone_entries() -> list[tuple[str, str]]:
    global _SORTED_ZONE_ENTRIES
    if _SORTED_ZONE_ENTRIES is None:
        _SORTED_ZONE_ENTRIES = sorted(ZONE_MAP.items(), key=lambda kv: -len(kv[0]))
    return _SORTED_ZONE_ENTRIES


@dataclass(frozen=True)
class Violation:
    path: Path
    lineno: int
    message: str


def _policy_for_file(py_file: Path, foundry_root: Path) -> str:
    try:
        rel = py_file.relative_to(foundry_root)
    except ValueError:
        return DEFAULT_ZONE
    rel_str = str(rel).replace("\\", "/")

    for prefix, zone in _sorted_zone_entries():
        if prefix.endswith("/"):
            if rel_str.startswith(prefix) or rel_str + "/" == prefix:
                return zone
        else:
            if rel_str == prefix:
                return zone
    return DEFAULT_ZONE


def _banned_import_roots(policy: str) -> set[str]:
    if policy == "infra":
        return set()
    if policy == "mixed":
        return STANDARD_BANNED_IMPORT_ROOTS - MIXED_ALLOWED_IMPORTS
    if policy == "no_jax":
        return (STANDARD_BANNED_IMPORT_ROOTS - MIXED_ALLOWED_IMPORTS) | NO_JAX_BANNED_IMPORTS
    return set(STANDARD_BANNED_IMPORT_ROOTS)


def _banned_builtins(policy: str) -> set[str]:
    if policy == "infra":
        return set()
    return BANNED_BUILTINS


class FoundryVisitor(ast.NodeVisitor):
    def __init__(self, path: Path, policy: str) -> None:
        self.path = path
        self.policy = policy
        self.violations: list[Violation] = []
        self._banned_roots = _banned_import_roots(policy)
        self._banned_builtins = _banned_builtins(policy)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            root = alias.name.split(".")[0]
            if root in self._banned_roots:
                self.violations.append(
                    Violation(
                        path=self.path,
                        lineno=node.lineno,
                        message=f"banned import ({self.policy}): {alias.name}",
                    )
                )

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if not node.module:
            return
        root = node.module.split(".")[0]
        if root in self._banned_roots:
            self.violations.append(
                Violation(
                    path=self.path,
                    lineno=node.lineno,
                    message=f"banned import ({self.policy}): {node.module}",
                )
            )

    def visit_Call(self, node: ast.Call) -> None:
        if isinstance(node.func, ast.Name) and node.func.id in self._banned_builtins:
            self.violations.append(
                Violation(
                    path=self.path,
                    lineno=node.lineno,
                    message=f"banned builtin call: {node.func.id}()",
                )
            )
        self.generic_visit(node)


def find_foundry_roots(repo_root: Path) -> list[Path]:
    candidates = [
        repo_root / "src" / "foundry",
        repo_root / "src" / "polisyos" / "foundry",
    ]
    return [path for path in candidates if path.exists()]


def iter_py_files(root: Path) -> list[Path]:
    return [path for path in root.rglob("*.py") if "__pycache__" not in path.parts]


def format_path(root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Lint foundry for banned imports and I/O.")
    parser.add_argument("--repo-root", type=Path, default=Path("."), help="Repository root")
    args = parser.parse_args()

    repo_root = args.repo_root.resolve()
    roots = find_foundry_roots(repo_root)
    if not roots:
        print("No foundry roots found.")
        return 2

    violations: list[Violation] = []
    for root in roots:
        for path in iter_py_files(root):
            policy = _policy_for_file(path, root)
            tree = ast.parse(path.read_text(encoding="utf-8"))
            visitor = FoundryVisitor(path, policy)
            visitor.visit(tree)
            violations.extend(visitor.violations)

    if violations:
        print("Foundry ban list violations:")
        for violation in violations:
            print(f"- {format_path(repo_root, violation.path)}:{violation.lineno} {violation.message}")
        return 1

    print("Foundry ban list: clean")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
