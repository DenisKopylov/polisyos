"""Foundry-specific lint rules registered for ``lint_foundry``."""

from __future__ import annotations

import ast

from . import RuleContext, RuleDefinition, RuleFix, RuleViolation, register_rule


def _check_banned_imports(context: RuleContext) -> list[RuleViolation]:
    banned_roots = set(context.data.get("banned_roots") or ())
    violations: list[RuleViolation] = []
    for node in ast.walk(context.tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root in banned_roots:
                    violations.append(
                        RuleViolation(
                            rule_id="foundry.banned-import-root",
                            path=context.path,
                            lineno=node.lineno,
                            message=f"banned import ({context.policy}): {alias.name}",
                        )
                    )
        elif isinstance(node, ast.ImportFrom):
            if not node.module:
                continue
            root = node.module.split(".")[0]
            if root in banned_roots:
                violations.append(
                    RuleViolation(
                        rule_id="foundry.banned-import-root",
                        path=context.path,
                        lineno=node.lineno,
                        message=f"banned import ({context.policy}): {node.module}",
                    )
                )
    return violations


def _check_banned_builtins(context: RuleContext) -> list[RuleViolation]:
    banned_builtins = set(context.data.get("banned_builtins") or ())
    violations: list[RuleViolation] = []
    for node in ast.walk(context.tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Name):
            continue
        if node.func.id not in banned_builtins:
            continue
        parent = getattr(node, "_parent", None)
        standalone_expr = isinstance(parent, ast.Expr)
        violations.append(
            RuleViolation(
                rule_id="foundry.banned-builtin-call",
                path=context.path,
                lineno=node.lineno,
                message=f"banned builtin call: {node.func.id}()",
                fixable=node.func.id == "print" and standalone_expr,
                start_lineno=node.lineno,
                end_lineno=getattr(parent, "end_lineno", node.lineno) if standalone_expr else None,
            )
        )
    return violations


def _fix_banned_builtins(
    context: RuleContext,
    violations: tuple[RuleViolation, ...] | list[RuleViolation],
) -> RuleFix | None:
    removable_ranges = sorted(
        {
            (
                violation.start_lineno or violation.lineno,
                violation.end_lineno or violation.lineno,
            )
            for violation in violations
            if violation.fixable
        }
    )
    if not removable_ranges:
        return None

    def _should_remove(line_number: int) -> bool:
        return any(start <= line_number <= end for start, end in removable_ranges)

    lines = context.source.splitlines(keepends=True)
    rendered = "".join(
        line for line_number, line in enumerate(lines, start=1) if not _should_remove(line_number)
    )
    if rendered == context.source:
        return None
    return RuleFix(
        rule_id="foundry.banned-builtin-call",
        path=context.path,
        description="removed standalone print() debug calls",
        rendered_source=rendered,
    )


register_rule(
    RuleDefinition(
        rule_id="foundry.banned-import-root",
        description="Disallow banned import roots in foundry purity zones.",
        check=_check_banned_imports,
    )
)

register_rule(
    RuleDefinition(
        rule_id="foundry.banned-builtin-call",
        description="Disallow banned builtin calls in foundry purity zones.",
        check=_check_banned_builtins,
        fix=_fix_banned_builtins,
    )
)
