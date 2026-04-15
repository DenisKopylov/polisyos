"""Lightweight repo policy checks for GitHub Actions workflows.

This script complements actionlint with PolicyOS-specific supply-chain and
workflow-governance assertions that are easier to express as text-level checks
than as generic YAML lint rules.
"""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path

from tools._lib.runner import ToolStatus
from tools.registry import LEGACY_ENTRYPOINTS, TOOL_SPECS


TOP_LEVEL_JOBS_RE = re.compile(r"(?m)^jobs:\s*$")
USES_RE = re.compile(r"(?m)^\s*uses:\s*(?P<target>[^\s#]+)")
RUN_BLOCK_RE = re.compile(r"^(?P<indent>\s*)run:\s*(?P<inline>.*)$")
SHA_PIN_RE = re.compile(r"^[0-9a-f]{40}$")
UNTRUSTED_EXPR_RE = re.compile(
    r"\$\{\{\s*(github\.event\.(pull_request|issue)|github\.head_ref)"
)
LEGACY_CI_PATHS: dict[str, str] = {
    **LEGACY_ENTRYPOINTS,
    "cloud_deploy/": "use `tools/cloud/deploy/` assets and `polisyos-tools cloud deploy-to-server` instead",
}


@dataclass(slots=True)
class Finding:
    path: Path
    message: str


def _iter_policy_files(repo_root: Path) -> list[Path]:
    paths = sorted((repo_root / ".github" / "workflows").glob("*.y*ml"))
    paths.extend(sorted((repo_root / ".github" / "actions").glob("**/action.y*ml")))
    return [path for path in paths if path.is_file()]


def _top_level_prefix(text: str) -> str:
    match = TOP_LEVEL_JOBS_RE.search(text)
    if match is None:
        return text
    return text[: match.start()]


def _check_top_level_permissions(path: Path, text: str) -> list[Finding]:
    findings: list[Finding] = []
    prefix = _top_level_prefix(text)
    if not re.search(r"(?m)^permissions:\s*(\{.*\})?\s*$", prefix):
        findings.append(Finding(path, "top-level permissions block is required"))
        return findings

    if re.search(r"(?m)^permissions:\s*write-all\s*$", prefix):
        findings.append(Finding(path, "top-level permissions must not use write-all"))

    for line in prefix.splitlines():
        stripped = line.strip()
        if stripped.endswith(": write") or stripped == "write-all":
            findings.append(
                Finding(
                    path,
                    f"top-level permission escalation must move to job scope: `{stripped}`",
                )
            )
    return findings


def _check_pinned_actions(path: Path, text: str) -> list[Finding]:
    findings: list[Finding] = []
    for match in USES_RE.finditer(text):
        target = match.group("target")
        if target.startswith("./") or target.startswith("docker://"):
            continue
        if "@" not in target:
            findings.append(Finding(path, f"`uses:` target is missing a ref: `{target}`"))
            continue
        _, ref = target.rsplit("@", 1)
        if not SHA_PIN_RE.fullmatch(ref):
            findings.append(Finding(path, f"third-party action is not pinned to a full SHA: `{target}`"))
    return findings


def _check_events_and_runners(path: Path, text: str) -> list[Finding]:
    findings: list[Finding] = []
    if re.search(r"(?m)^\s*pull_request_target:\s*$", text):
        findings.append(Finding(path, "`pull_request_target` is forbidden in repo policy"))
    if re.search(r"(?m)^\s*runs-on:\s*self-hosted\b", text):
        findings.append(Finding(path, "self-hosted runners require an owner/isolation review before use"))
    return findings


def _check_untrusted_run_interpolation(path: Path, text: str) -> list[Finding]:
    findings: list[Finding] = []
    lines = text.splitlines()
    in_run_block = False
    run_indent = 0

    for line in lines:
        run_match = RUN_BLOCK_RE.match(line)
        if run_match:
            in_run_block = True
            run_indent = len(run_match.group("indent"))
            inline = run_match.group("inline")
            if inline and UNTRUSTED_EXPR_RE.search(inline):
                findings.append(
                    Finding(
                        path,
                        "untrusted GitHub context must not be interpolated directly inside `run:` commands",
                    )
                )
            continue

        if in_run_block:
            indent = len(line) - len(line.lstrip(" "))
            if line.strip() and indent <= run_indent:
                in_run_block = False
            elif UNTRUSTED_EXPR_RE.search(line):
                findings.append(
                    Finding(
                        path,
                        "untrusted GitHub context must not be interpolated directly inside `run:` blocks",
                    )
                )
    return findings


def _check_deprecated_tool_surfaces(path: Path, text: str) -> list[Finding]:
    findings: list[Finding] = []
    for spec in TOOL_SPECS:
        if spec.status == ToolStatus.ACTIVE:
            continue
        patterns = [
            f"polisyos-tools {spec.category} {spec.name}",
            f"python tools/{spec.category}/{spec.module.rsplit('.', 1)[-1]}.py",
            f"python3 tools/{spec.category}/{spec.module.rsplit('.', 1)[-1]}.py",
        ]
        patterns.extend(spec.aliases)
        for pattern in patterns:
            if pattern and pattern in text:
                replacement = f"; use {spec.replacement}" if spec.replacement else ""
                findings.append(
                    Finding(
                        path,
                        f"deprecated/quarantined tool surface referenced in CI: `{pattern}`{replacement}",
                    )
                )
                break
    for legacy_path, replacement in LEGACY_CI_PATHS.items():
        if legacy_path in text:
            findings.append(
                Finding(
                    path,
                    f"legacy repository surface referenced in CI: `{legacy_path}`; {replacement}",
                )
            )
    return findings


def collect_findings(repo_root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for path in _iter_policy_files(repo_root):
        text = path.read_text(encoding="utf-8")
        is_workflow = ".github/workflows" in str(path)
        if is_workflow:
            findings.extend(_check_top_level_permissions(path, text))
            findings.extend(_check_events_and_runners(path, text))
            findings.extend(_check_untrusted_run_interpolation(path, text))
            findings.extend(_check_deprecated_tool_surfaces(path, text))
        findings.extend(_check_pinned_actions(path, text))
    return findings


def write_summary(findings: list[Finding], summary_path: Path, repo_root: Path) -> None:
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# Workflow Policy Summary", ""]
    if not findings:
        lines.extend(
            [
                "Status: pass",
                "",
                "- Top-level permissions are present.",
                "- External actions are pinned to full SHAs.",
                "- No forbidden runner/event patterns were detected.",
            ]
        )
    else:
        lines.extend(["Status: fail", "", "| File | Finding |", "|---|---|"])
        for finding in findings:
            rel = finding.path.relative_to(repo_root)
            lines.append(f"| `{rel}` | {finding.message} |")
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check GitHub Actions workflow policy invariants")
    parser.add_argument("--repo-root", default=".", help="Repository root")
    parser.add_argument("--summary", help="Optional markdown summary output path")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    findings = collect_findings(repo_root)
    if args.summary:
        write_summary(findings, Path(args.summary).resolve(), repo_root)
    if findings:
        for finding in findings:
            rel = finding.path.relative_to(repo_root)
            print(f"{rel}: {finding.message}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
