#!/usr/bin/env python3
"""Run the Phase D6 path-aware documentation drift gate.

This checker turns the D6 documentation rules into one callable gate:

* detect which docs-sensitive surfaces changed relative to git;
* require the matching evidence/docs updates for those surfaces;
* dispatch the existing canonical generators and validators only when needed.
"""

from __future__ import annotations

import argparse
import fnmatch
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from tools._lib.imports import repo_root_from

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

REPO_ROOT = repo_root_from(__file__)
IMPACT_NOTE = "docs/reference/documentation-inventory.md"

TOOLS_REFERENCE_PATTERNS = ("tools/**",)
DOCS_OR_README_PATTERNS = (
    "docs/**",
    "mkdocs.yml",
    "README.md",
    "frontend/**/README.md",
    "src/polisyos/**/README.md",
    "tools/**/README.md",
)
FACADE_PATTERNS = (
    "src/polisyos/**/__init__.py",
    "architecture/public_surface.toml",
    "architecture/generated_artifacts.toml",
)
IR_OR_SCHEMA_PATTERNS = (
    "src/polisyos/ir/**",
    "schemas/**",
)
RUNTIME_HTTP_PATTERNS = ("src/polisyos/runtime/http/**",)
SEMANTIC_DOCSTRING_PATTERNS = (
    "src/polisyos/**/__init__.py",
    "src/polisyos/runtime/http/*.py",
    "src/polisyos/runtime/http/**/*.py",
)
FRONTEND_API_PATTERNS = (
    "frontend/runtime-api-client/**",
    "frontend/runtime-dashboard/src/api/**",
    "frontend/runtime-dashboard/src/test/contracts/**",
    "frontend/runtime-reference-shell/**",
)
RUNTIME_EVIDENCE_PATTERNS = (
    "schemas/runtime_api_v1.openapi.json",
    "docs/reference/api/**",
    "docs/how-to/deploy-runtime.md",
    "docs/how-to/use-control-plane.md",
    "docs/runbooks/runtime-api-outage.md",
    "frontend/README.md",
    "frontend/runtime-api-client/README.md",
    "frontend/runtime-dashboard/README.md",
    IMPACT_NOTE,
)
FABRIC_CONNECTOR_PATTERNS = ("src/polisyos/fabric/connectors/**",)
FABRIC_EVIDENCE_PATTERNS = (
    "docs/reference/fabric/**",
    "docs/connectors/CONTRIBUTING.md",
    "docs/how-to/add-data-source.md",
    "docs/how-to/manage-generated-artifacts.md",
    IMPACT_NOTE,
)
SCIENTIST_EVIDENCE_PATTERNS = (
    "docs/reference/scientist/**",
    IMPACT_NOTE,
)
FOUNDRY_EVIDENCE_PATTERNS = (
    "docs/reference/foundry/**",
    "docs/benchmarks/**",
    "docs/explanation/causal-engine.md",
    IMPACT_NOTE,
)
FRONTEND_EVIDENCE_PATTERNS = (
    "frontend/README.md",
    "frontend/runtime-api-client/README.md",
    "frontend/runtime-dashboard/README.md",
    "frontend/runtime-reference-shell/README.md",
    "docs/how-to/onboarding/frontend-engineer.md",
    "docs/runbooks/broken-contract-generation.md",
    "docs/reference/generated-artifacts.md",
    IMPACT_NOTE,
)
SECURITY_DOC_PATTERNS = (
    "docs/reference/security-compliance.md",
    "docs/explanation/security-model.md",
    IMPACT_NOTE,
)
SECURITY_RUNBOOK_PATTERNS = (
    "docs/runbooks/**",
    "docs/reference/operations/platform-acceptance-audit.md",
    "docs/archive/reports/platform-acceptance.manual.toml",
    IMPACT_NOTE,
)


@dataclass(frozen=True)
class GateCommand:
    """Describe one canonical command dispatched by the docs gate."""

    key: str
    label: str
    argv: tuple[str, ...]


@dataclass(frozen=True)
class GateFinding:
    """Describe one missing-evidence or missing-docs finding."""

    rule_id: str
    message: str


@dataclass(frozen=True)
class GatePlan:
    """Bundle the commands and findings required for one change set."""

    commands: tuple[GateCommand, ...]
    findings: tuple[GateFinding, ...]


GATE_COMMANDS: dict[str, GateCommand] = {
    "tools_reference": GateCommand(
        key="tools_reference",
        label="verify generated tools reference",
        argv=(
            "uv",
            "run",
            "polisyos-tools",
            "docs",
            "--check",
            "--output",
            "docs/reference/tools.md",
        ),
    ),
    "public_surface": GateCommand(
        key="public_surface",
        label="verify public-surface and README freshness guardrails",
        argv=("uv", "run", "polisyos-tools", "architecture", "guardrails", "check"),
    ),
    "schema_docs": GateCommand(
        key="schema_docs",
        label="verify schema snapshots and IR reference docs",
        argv=("uv", "run", "--extra", "ml", "python", "tools/diagnostics/gen_schema.py", "--check"),
    ),
    "runtime_api": GateCommand(
        key="runtime_api",
        label="verify Runtime API OpenAPI and generated client drift",
        argv=(
            "uv",
            "run",
            "--extra",
            "runtime",
            "--extra",
            "ml",
            "python",
            "tools/runtime/check_runtime_api_contract.py",
        ),
    ),
    "docs_accuracy": GateCommand(
        key="docs_accuracy",
        label="verify docs accuracy",
        argv=(
            "uv",
            "run",
            "polisyos-tools",
            "validation",
            "check-docs-accuracy",
            "--repo-root",
            ".",
        ),
    ),
    "semantic_docstrings": GateCommand(
        key="semantic_docstrings",
        label="verify semantic public-surface docstrings",
        argv=(),
    ),
    "strict_docs_build": GateCommand(
        key="strict_docs_build",
        label="build documentation site in strict mode",
        argv=("uv", "run", "--extra", "docs", "python", "-m", "mkdocs", "build", "--strict"),
    ),
}


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the path-aware Phase D6 documentation drift gate."
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=REPO_ROOT,
        help="Repository root containing docs/, src/, tools/, and mkdocs.yml.",
    )
    parser.add_argument(
        "--base-ref",
        default=None,
        help=(
            "Git ref/SHA used to compute the change set. "
            "When omitted, compare the current worktree against HEAD."
        ),
    )
    parser.add_argument(
        "--head-ref",
        default="HEAD",
        help="Git ref/SHA to diff against the resolved base. Defaults to HEAD.",
    )
    parser.add_argument(
        "--changed-path",
        action="append",
        default=[],
        help=(
            "Explicit repo-relative changed path override. Repeat to bypass git diff "
            "and evaluate only the listed paths."
        ),
    )
    return parser.parse_args(argv)


def _run_git(repo_root: Path, args: Sequence[str]) -> str:
    completed = subprocess.run(  # noqa: S603
        ["git", *args],  # noqa: S607
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _try_git(repo_root: Path, args: Sequence[str]) -> str | None:
    try:
        return _run_git(repo_root, args)
    except subprocess.CalledProcessError:
        return None


def _resolve_diff_base(repo_root: Path, *, base_ref: str | None, head_ref: str) -> str | None:
    if not base_ref:
        return None
    merge_base = _try_git(repo_root, ("merge-base", head_ref, base_ref))
    if merge_base:
        return merge_base
    return base_ref


def _untracked_paths(repo_root: Path) -> set[str]:
    result = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard", "--", "."],  # noqa: S607
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return set()
    return {line.strip() for line in result.stdout.splitlines() if line.strip()}


def _repo_prefix_from_git_root(repo_root: Path) -> str:
    git_root = _try_git(repo_root, ("rev-parse", "--show-toplevel"))
    if not git_root:
        return ""
    try:
        return repo_root.resolve().relative_to(Path(git_root).resolve()).as_posix()
    except ValueError:
        return ""


def normalize_changed_paths(repo_root: Path, paths: Iterable[str]) -> tuple[str, ...]:
    """Normalize git paths to be relative to ``repo_root``.

    ``policy-engine`` lives inside a larger git checkout, so tracked files can
    arrive as ``policy-engine/src/...`` while untracked files arrive as
    ``src/...``. D6 rules operate on product-root-relative paths.
    """

    prefix = _repo_prefix_from_git_root(repo_root)
    normalized: set[str] = set()
    for raw_path in paths:
        path = raw_path.strip().replace("\\", "/")
        if not path:
            continue
        if prefix and path == prefix:
            continue
        if prefix and path.startswith(f"{prefix}/"):
            path = path[len(prefix) + 1 :]
        normalized.add(path)
    return tuple(sorted(normalized))


def load_changed_paths(repo_root: Path, *, base_ref: str | None, head_ref: str) -> tuple[str, ...]:
    """Return repo-relative changed paths for the requested diff window."""

    baseline = _resolve_diff_base(repo_root, base_ref=base_ref, head_ref=head_ref)
    if baseline is None:
        diff_args = ("diff", "--name-only", "--diff-filter=ACMRD", "HEAD", "--", ".")
    else:
        diff_args = ("diff", "--name-only", "--diff-filter=ACMRD", baseline, head_ref, "--", ".")
    diff_output = _try_git(repo_root, diff_args) or ""
    changed = {line.strip() for line in diff_output.splitlines() if line.strip()}
    if head_ref == "HEAD":
        changed.update(_untracked_paths(repo_root))
    return normalize_changed_paths(repo_root, changed)


def _matches(path: str, patterns: Iterable[str]) -> bool:
    return any(fnmatch.fnmatch(path, pattern) for pattern in patterns)


def _has_changed(paths: Sequence[str], patterns: Iterable[str]) -> bool:
    return any(_matches(path, patterns) for path in paths)


def _has_keyword_match(paths: Sequence[str], *, prefix: str, keywords: Iterable[str]) -> bool:
    return any(
        path.startswith(prefix) and any(keyword in path for keyword in keywords) for path in paths
    )


def _matching_paths(paths: Sequence[str], patterns: Iterable[str]) -> tuple[str, ...]:
    return tuple(path for path in paths if _matches(path, patterns))


def _format_paths(paths: Sequence[str]) -> str:
    if not paths:
        return "(none)"
    if len(paths) <= 4:
        return ", ".join(f"`{path}`" for path in paths)
    head = ", ".join(f"`{path}`" for path in paths[:4])
    return f"{head}, and {len(paths) - 4} more"


def _format_patterns(patterns: Sequence[str]) -> str:
    return ", ".join(f"`{pattern}`" for pattern in patterns)


def _facade_readmes(paths: Sequence[str]) -> tuple[str, ...]:
    readmes: set[str] = set()
    for path in paths:
        candidate = Path(path)
        if candidate.name != "__init__.py":
            continue
        if candidate.parts[:2] != ("src", "polisyos"):
            continue
        readmes.add((candidate.parent / "README.md").as_posix())
    return tuple(sorted(readmes))


def _module_prefixes(paths: Sequence[str]) -> tuple[str, ...]:
    prefixes: set[str] = set()
    for path in paths:
        candidate = Path(path)
        if candidate.suffix != ".py":
            continue
        if candidate.parts[:2] != ("src", "polisyos"):
            continue
        parts = list(candidate.parts[1:])
        if parts[-1] == "__init__.py":
            module_parts = parts[:-1]
        else:
            parts[-1] = parts[-1].removesuffix(".py")
            module_parts = parts
        prefixes.add(".".join(module_parts))
    return tuple(sorted(prefixes))


def _build_semantic_docstrings_command(changed_paths: Sequence[str]) -> GateCommand:
    prefixes = _module_prefixes(changed_paths)
    argv = [
        "uv",
        "run",
        "polisyos-tools",
        "validation",
        "check-docstring-quality",
        "--repo-root",
        ".",
        "--allowlist",
        "tools/validation/docstring_quality_allowlist.txt",
        "--coverage-scope",
        "public-surface",
        "--minimum-coverage",
        "85",
    ]
    for prefix in prefixes:
        argv.extend(["--module-prefix", prefix])
    return GateCommand(
        key="semantic_docstrings",
        label="verify semantic public-surface docstrings for changed modules",
        argv=tuple(argv),
    )


def _is_scientist_docs_sensitive(path: str) -> bool:
    if not path.startswith("src/polisyos/scientist/"):
        return False
    return any(keyword in path for keyword in ("workflow", "govern", "causal"))


def _is_foundry_docs_sensitive(path: str) -> bool:
    if not path.startswith("src/polisyos/foundry/"):
        return False
    return any(keyword in path for keyword in ("compile", "execute", "methods", "calibration"))


def _is_security_sensitive(path: str) -> bool:
    if path.startswith("src/polisyos/core/security/"):
        return True
    if path.startswith("src/polisyos/runtime/http/"):
        return any(
            keyword in path for keyword in ("auth", "tenant", "audit", "sign", "csrf", "jwt")
        )
    if not path.startswith(("src/polisyos/", "tools/")):
        return False
    return any(keyword in path for keyword in ("auth", "tenant", "audit", "sign", "compliance"))


def build_gate_plan(changed_paths: Sequence[str]) -> GatePlan:
    """Return the D6 docs-gate plan for the given repo-relative paths."""

    command_keys: list[str] = []
    dynamic_commands: dict[str, GateCommand] = {}
    findings: list[GateFinding] = []
    semantic_docstring_paths = _matching_paths(changed_paths, SEMANTIC_DOCSTRING_PATTERNS)

    def add_command(key: str) -> None:
        if key not in command_keys:
            if key == "semantic_docstrings":
                dynamic_commands[key] = _build_semantic_docstrings_command(semantic_docstring_paths)
            command_keys.append(key)

    if _has_changed(changed_paths, TOOLS_REFERENCE_PATTERNS):
        add_command("tools_reference")

    docs_or_readme_changed = _has_changed(changed_paths, DOCS_OR_README_PATTERNS)
    facade_changed = _has_changed(changed_paths, FACADE_PATTERNS)
    runtime_http_changed = _has_changed(changed_paths, RUNTIME_HTTP_PATTERNS)
    ir_or_schema_changed = _has_changed(changed_paths, IR_OR_SCHEMA_PATTERNS)
    frontend_api_changed = _has_changed(changed_paths, FRONTEND_API_PATTERNS)
    fabric_connector_changed = _has_changed(changed_paths, FABRIC_CONNECTOR_PATTERNS)
    scientist_changed = any(_is_scientist_docs_sensitive(path) for path in changed_paths)
    foundry_changed = any(_is_foundry_docs_sensitive(path) for path in changed_paths)
    security_changed = any(_is_security_sensitive(path) for path in changed_paths)

    if facade_changed:
        add_command("public_surface")
    if ir_or_schema_changed:
        add_command("schema_docs")
    if runtime_http_changed or frontend_api_changed:
        add_command("runtime_api")
    if docs_or_readme_changed:
        add_command("docs_accuracy")
        add_command("strict_docs_build")
    if semantic_docstring_paths and (facade_changed or runtime_http_changed):
        add_command("semantic_docstrings")

    if runtime_http_changed and not _has_changed(changed_paths, RUNTIME_EVIDENCE_PATTERNS):
        touched = _format_paths(_matching_paths(changed_paths, RUNTIME_HTTP_PATTERNS))
        findings.append(
            GateFinding(
                rule_id="runtime_api_evidence",
                message=(
                    "Runtime HTTP changes require Runtime API docs or OpenAPI evidence updates. "
                    f"Touched: {touched}. "
                    f"Expected one of: {_format_patterns(RUNTIME_EVIDENCE_PATTERNS)}."
                ),
            )
        )

    if fabric_connector_changed and not _has_changed(changed_paths, FABRIC_EVIDENCE_PATTERNS):
        touched = _format_paths(_matching_paths(changed_paths, FABRIC_CONNECTOR_PATTERNS))
        findings.append(
            GateFinding(
                rule_id="fabric_connector_docs",
                message=(
                    "Fabric connector changes require connector docs or an impact note. "
                    f"Touched: {touched}. "
                    f"Expected one of: {_format_patterns(FABRIC_EVIDENCE_PATTERNS)}."
                ),
            )
        )

    if scientist_changed and not _has_changed(changed_paths, SCIENTIST_EVIDENCE_PATTERNS):
        touched = tuple(path for path in changed_paths if _is_scientist_docs_sensitive(path))
        findings.append(
            GateFinding(
                rule_id="scientist_docs",
                message=(
                    "Scientist workflow/governance/causal changes require Scientist reference "
                    f"docs or an impact note. Touched: {_format_paths(touched)}. "
                    f"Expected one of: {_format_patterns(SCIENTIST_EVIDENCE_PATTERNS)}."
                ),
            )
        )

    if foundry_changed and not _has_changed(changed_paths, FOUNDRY_EVIDENCE_PATTERNS):
        touched = tuple(path for path in changed_paths if _is_foundry_docs_sensitive(path))
        findings.append(
            GateFinding(
                rule_id="foundry_docs",
                message=(
                    "Foundry compile/execute/method/calibration changes require Foundry reference, "
                    f"benchmark docs, or an impact note. Touched: {_format_paths(touched)}. "
                    f"Expected one of: {_format_patterns(FOUNDRY_EVIDENCE_PATTERNS)}."
                ),
            )
        )

    if frontend_api_changed and not _has_changed(changed_paths, FRONTEND_EVIDENCE_PATTERNS):
        touched = _format_paths(_matching_paths(changed_paths, FRONTEND_API_PATTERNS))
        findings.append(
            GateFinding(
                rule_id="frontend_docs",
                message=(
                    "Frontend API client/dashboard API changes require frontend docs coverage "
                    f"or an impact note. Touched: {touched}. "
                    f"Expected one of: {_format_patterns(FRONTEND_EVIDENCE_PATTERNS)}."
                ),
            )
        )

    if security_changed:
        touched = tuple(path for path in changed_paths if _is_security_sensitive(path))
        if not _has_changed(changed_paths, SECURITY_DOC_PATTERNS):
            findings.append(
                GateFinding(
                    rule_id="security_docs",
                    message=(
                        "Security/auth/tenant/signing/audit/compliance changes require "
                        "security/compliance docs coverage. "
                        f"Touched: {_format_paths(touched)}. "
                        f"Expected one of: {_format_patterns(SECURITY_DOC_PATTERNS)}."
                    ),
                )
            )
        if not _has_changed(changed_paths, SECURITY_RUNBOOK_PATTERNS):
            findings.append(
                GateFinding(
                    rule_id="security_runbooks",
                    message=(
                        "Security/auth/tenant/signing/audit/compliance changes require runbook "
                        "or rehearsal-ledger evidence. "
                        f"Touched: {_format_paths(touched)}. "
                        f"Expected one of: {_format_patterns(SECURITY_RUNBOOK_PATTERNS)}."
                    ),
                )
            )

    if facade_changed:
        expected_readmes = _facade_readmes(changed_paths)
        if expected_readmes and not _has_changed(changed_paths, (*expected_readmes, IMPACT_NOTE)):
            findings.append(
                GateFinding(
                    rule_id="readme_freshness",
                    message=(
                        "Public package-facade changes require the matching package README to "
                        "stay fresh or an impact note to be recorded. "
                        f"Expected one of: {_format_patterns((*expected_readmes, IMPACT_NOTE))}."
                    ),
                )
            )

    return GatePlan(
        commands=tuple(dynamic_commands.get(key, GATE_COMMANDS[key]) for key in command_keys),
        findings=tuple(findings),
    )


def _run_gate_commands(repo_root: Path, commands: Sequence[GateCommand]) -> list[str]:
    errors: list[str] = []
    for command in commands:
        printable = shlex.join(command.argv)
        print(f"[docs-gate] {command.label}")
        print(f"[docs-gate] $ {printable}")
        completed = subprocess.run(command.argv, cwd=repo_root, check=False)  # noqa: S603
        if completed.returncode != 0:
            errors.append(
                f"{command.label} failed with exit code {completed.returncode}: {printable}"
            )
            break
    return errors


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    repo_root = args.repo_root.resolve()
    changed_paths = (
        normalize_changed_paths(repo_root, args.changed_path)
        if args.changed_path
        else load_changed_paths(repo_root, base_ref=args.base_ref, head_ref=args.head_ref)
    )
    plan = build_gate_plan(changed_paths)

    print("Docs drift gate")
    print(f"- changed files: {len(changed_paths)}")
    if changed_paths:
        print(f"- change window: {_format_paths(changed_paths)}")

    if not plan.commands and not plan.findings:
        print("- no docs-sensitive D6 rules were triggered")
        return 0

    errors = _run_gate_commands(repo_root, plan.commands)
    all_findings = list(plan.findings)
    all_findings.extend(GateFinding(rule_id="command_failure", message=error) for error in errors)

    if all_findings:
        print("Docs drift gate FAILED:")
        for finding in all_findings:
            print(f"- [{finding.rule_id}] {finding.message}")
        return 1

    print("Docs drift gate passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
