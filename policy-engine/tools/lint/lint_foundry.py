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

MIXED_BACKEND_DIRS = {
    "methods/backends",
    "methods/catalog",
}

NO_JAX_DIRS = {
    "methods/catalog/causal",
    "methods/catalog/causal/transport",
    "methods/catalog/causal/discovery",
    "methods/catalog/econometrics",
    "methods/catalog/optimization",
}

NO_JAX_FILE_ALLOWLIST = {
    "methods/catalog/causal/ci_backends.py",
}

MIXED_BACKEND_ALLOWED_IMPORTS = {
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

# Infrastructure directories exempt from data-plane purity checks.
# These contain orchestration, CLI, simulation dashboards, and test utilities
# that legitimately require I/O and system access.
INFRA_DIRS = {
    "plugins",
    "agent_sim",
    "runtime",
    "methods/testing",
    "methods/cli",        # CLI tooling — needs I/O and pathlib
}

INFRA_FILES = {
    "agents.py",
    "methods/base.py",
    "methods/discovery.py",
    "methods/_artifacts_fingerprint.py",
    # Infrastructure modules that legitimately require I/O / system access:
    "methods/cache.py",          # disk-backed result cache (sqlite3, pathlib)
    "methods/hot_reload.py",     # file-watcher for dev (os, pathlib)
    "methods/observability.py",  # metrics / tracing integration (os)
    "methods/compat_matrix.py",  # compat report generator (pandas)
    "methods/composer.py",       # chain orchestration (os for env vars)
    "methods/deprecation.py",    # CLI-facing deprecation warnings (print to stderr)
    "methods/backends/checkpointing.py",  # checkpoint I/O (pathlib)
    "methods/backends/ray_runner.py",     # Ray distributed runner (os)
}


@dataclass(frozen=True)
class Violation:
    path: Path
    lineno: int
    message: str


def _policy_for_file(py_file: Path, foundry_root: Path) -> str:
    try:
        rel = py_file.relative_to(foundry_root)
    except ValueError:
        return "standard"
    rel_str = str(rel).replace("\\", "/")

    for infra_dir in INFRA_DIRS:
        if rel_str.startswith(infra_dir + "/") or rel_str == infra_dir:
            return "infra"
    if rel_str in INFRA_FILES:
        return "infra"
    if rel_str in NO_JAX_FILE_ALLOWLIST:
        return "mixed"

    for no_jax_dir in NO_JAX_DIRS:
        if rel_str.startswith(no_jax_dir):
            return "no_jax"
    for mixed_dir in MIXED_BACKEND_DIRS:
        if rel_str.startswith(mixed_dir):
            return "mixed"
    return "standard"


def _banned_import_roots(policy: str) -> set[str]:
    if policy == "infra":
        return set()
    if policy == "mixed":
        return STANDARD_BANNED_IMPORT_ROOTS - MIXED_BACKEND_ALLOWED_IMPORTS
    if policy == "no_jax":
        return (STANDARD_BANNED_IMPORT_ROOTS - MIXED_BACKEND_ALLOWED_IMPORTS) | NO_JAX_BANNED_IMPORTS
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
