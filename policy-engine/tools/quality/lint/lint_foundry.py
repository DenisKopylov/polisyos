#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from tools._lib.fs import atomic_write_text
from tools._lib.output import OUTPUT_FORMATS, ToolMessage, ToolResult, format_tool_result

from .rules import RuleContext, RuleFix, RuleViolation, iter_rules

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

ZONE_MAP: dict[str, str] = {
    "plugins/": "infra",
    "agent_sim/": "infra",
    "runtime/": "infra",
    "methods/testing/": "infra",
    "methods/cli/": "infra",
    "agents.py": "infra",
    "quickstart.py": "infra",
    "methods/base.py": "infra",
    "methods/discovery.py": "infra",
    "methods/_artifacts_fingerprint.py": "infra",
    "methods/cache.py": "infra",
    "methods/hot_reload.py": "infra",
    "methods/observability.py": "infra",
    "methods/compat_matrix.py": "infra",
    "methods/composer.py": "infra",
    "methods/deprecation.py": "infra",
    "methods/backends/checkpointing.py": "infra",
    "methods/backends/ray_runner.py": "infra",
    "_executor_snapshots.py": "infra",
    "methods/selection_history.py": "infra",
    "release_acceptance.py": "infra",
    "methods/catalog/causal/ci_backends.py": "mixed",
    "methods/catalog/causal/": "no_jax",
    "methods/catalog/causal/transport/": "no_jax",
    "methods/catalog/causal/discovery/": "no_jax",
    "methods/catalog/econometrics/": "no_jax",
    "methods/catalog/optimization/": "no_jax",
    "methods/backends/": "mixed",
    "methods/catalog/": "mixed",
}
DEFAULT_ZONE = "standard"
_SORTED_ZONE_ENTRIES: list[tuple[str, str]] | None = None


@dataclass(frozen=True)
class ScanOutcome:
    violations: tuple[RuleViolation, ...]
    fixes: tuple[RuleFix, ...]


def _sorted_zone_entries() -> list[tuple[str, str]]:
    global _SORTED_ZONE_ENTRIES
    if _SORTED_ZONE_ENTRIES is None:
        _SORTED_ZONE_ENTRIES = sorted(ZONE_MAP.items(), key=lambda kv: -len(kv[0]))
    return _SORTED_ZONE_ENTRIES


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


def find_foundry_roots(repo_root: Path) -> list[Path]:
    candidates = [
        repo_root / "src" / "foundry",
        repo_root / "src" / "polisyos" / "foundry",
    ]
    return [path for path in candidates if path.exists()]


def iter_py_files(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*.py") if "__pycache__" not in path.parts)


def format_path(root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _annotate_parents(tree: ast.AST) -> None:
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            child._parent = parent


def _build_context(path: Path, *, repo_root: Path, policy: str) -> RuleContext:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    _annotate_parents(tree)
    return RuleContext(
        path=path,
        repo_root=repo_root,
        source=source,
        tree=tree,
        policy=policy,
        data={
            "banned_roots": sorted(_banned_import_roots(policy)),
            "banned_builtins": sorted(_banned_builtins(policy)),
        },
    )


def _run_rules(context: RuleContext) -> list[RuleViolation]:
    violations: list[RuleViolation] = []
    for rule in iter_rules("foundry."):
        violations.extend(rule.check(context))
    return sorted(
        violations, key=lambda item: (str(item.path), item.lineno, item.rule_id, item.message)
    )


def _apply_fixes(
    context: RuleContext, violations: list[RuleViolation]
) -> tuple[RuleContext, tuple[RuleFix, ...]]:
    fixes: list[RuleFix] = []
    working_context = context

    for rule in iter_rules("foundry."):
        if rule.fix is None:
            continue
        rule_violations = [
            violation
            for violation in violations
            if violation.rule_id == rule.rule_id and violation.fixable
        ]
        if not rule_violations:
            continue
        fix = rule.fix(working_context, rule_violations)
        if fix is None:
            continue
        atomic_write_text(fix.path, fix.rendered_source, encoding="utf-8")
        fixes.append(fix)
        working_context = _build_context(
            fix.path, repo_root=context.repo_root, policy=context.policy
        )

    return working_context, tuple(fixes)


def _scan_file(
    path: Path,
    *,
    repo_root: Path,
    policy: str,
    apply_fix: bool,
) -> ScanOutcome:
    context = _build_context(path, repo_root=repo_root, policy=policy)
    violations = _run_rules(context)
    fixes: tuple[RuleFix, ...] = ()
    if apply_fix and violations:
        context, fixes = _apply_fixes(context, violations)
        violations = _run_rules(context)
    return ScanOutcome(violations=tuple(violations), fixes=fixes)


def _emit_output(content: str, *, output: Path | None) -> None:
    if output is not None:
        atomic_write_text(output, content, encoding="utf-8")
        return
    print(content, end="")


def _render_text_report(
    *,
    repo_root: Path,
    violations: list[RuleViolation],
    fixes: list[RuleFix],
) -> str:
    lines: list[str] = []
    if fixes:
        lines.append("Foundry autofix actions:")
        for fix in fixes:
            lines.append(f"- {format_path(repo_root, fix.path)} {fix.description}")
        lines.append("")

    if violations:
        lines.append("Foundry ban list violations:")
        for violation in violations:
            lines.append(
                f"- {format_path(repo_root, violation.path)}:{violation.lineno} {violation.message}"
            )
        return "\n".join(lines) + "\n"

    if fixes:
        lines.append("Foundry ban list: fixed")
        return "\n".join(lines) + "\n"
    return "Foundry ban list: clean\n"


def _structured_result(
    *,
    repo_root: Path,
    violations: list[RuleViolation],
    fixes: list[RuleFix],
    roots: list[Path],
) -> ToolResult:
    status = "failed" if violations else "ok"
    summary = (
        "foundry ban list failed"
        if violations
        else ("foundry ban list fixed" if fixes else "foundry ban list clean")
    )
    messages = [
        ToolMessage(
            level="error",
            message=violation.message,
            path=format_path(repo_root, violation.path),
            line=violation.lineno,
            rule_id=violation.rule_id,
        )
        for violation in violations
    ]
    return ToolResult(
        tool="lint.lint-foundry",
        status=status,
        summary=summary,
        exit_code=1 if violations else 0,
        messages=tuple(messages),
        data={
            "root_count": len(roots),
            "violation_count": len(violations),
            "applied_fix_count": len(fixes),
            "applied_fixes": [
                {
                    "path": format_path(repo_root, fix.path),
                    "rule_id": fix.rule_id,
                    "description": fix.description,
                }
                for fix in fixes
            ],
        },
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Lint foundry for banned imports and I/O.")
    parser.add_argument("--repo-root", type=Path, default=Path("."), help="Repository root.")
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Apply safe mechanical fixes for supported foundry rules.",
    )
    parser.add_argument(
        "--output-format",
        choices=list(OUTPUT_FORMATS),
        default="text",
        help="Render the final lint result as text/json/sarif/junit.",
    )
    parser.add_argument("--output", type=Path, help="Optional output file.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    repo_root = args.repo_root.resolve()
    roots = find_foundry_roots(repo_root)
    if not roots:
        result = ToolResult.failed(
            "lint.lint-foundry",
            "No foundry roots found.",
            exit_code=2,
        )
        _emit_output(
            format_tool_result(result, output_format=args.output_format), output=args.output
        )
        return 2

    violations: list[RuleViolation] = []
    fixes: list[RuleFix] = []
    for root in roots:
        for path in iter_py_files(root):
            policy = _policy_for_file(path, root)
            outcome = _scan_file(
                path,
                repo_root=repo_root,
                policy=policy,
                apply_fix=args.fix,
            )
            violations.extend(outcome.violations)
            fixes.extend(outcome.fixes)

    if args.output_format == "text":
        _emit_output(
            _render_text_report(repo_root=repo_root, violations=violations, fixes=fixes),
            output=args.output,
        )
    else:
        _emit_output(
            format_tool_result(
                _structured_result(
                    repo_root=repo_root,
                    violations=violations,
                    fixes=fixes,
                    roots=roots,
                ),
                output_format=args.output_format,
            ),
            output=args.output,
        )

    return 1 if violations else 0


if __name__ == "__main__":
    raise SystemExit(main())
