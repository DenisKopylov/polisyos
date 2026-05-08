#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import datetime as dt
import difflib
import fnmatch
import json
import os
import re
import shlex
import subprocess
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tools.lib.imports import repo_root_from

REPO_ROOT = repo_root_from(__file__)
SRC_ROOT = REPO_ROOT / "src"
DEFAULT_PUBLIC_MANIFEST = REPO_ROOT / "architecture" / "public_surface" / "contract.toml"
DEFAULT_PUBLIC_JSON = REPO_ROOT / "architecture" / "public_surface" / "inventory.json"
DEFAULT_PUBLIC_MD = REPO_ROOT / "docs" / "reference" / "public-surface.md"
DEFAULT_GENERATED_MANIFEST = REPO_ROOT / "architecture" / "generated_artifacts.toml"
DEFAULT_GENERATED_MD = REPO_ROOT / "docs" / "reference" / "generated-artifacts.md"
DEFAULT_DEEP_IMPORT_BASELINE = REPO_ROOT / "architecture" / "baselines" / "imports" / "deep_import.json"
DEFAULT_EXCEPTION_FILE = REPO_ROOT / "architecture" / "exceptions" / "guardrails.toml"
DEFAULT_EXCEPTION_REGISTRY = REPO_ROOT / "architecture" / "guardrail_exceptions_registry.md"
DEFAULT_MODULE_SIZE_BUDGET = REPO_ROOT / "architecture" / "module_size_budget.toml"
DEFAULT_MAX_EXPIRY_DAYS = 90
FRESHNESS_PATTERNS = (
    re.compile(r"^- Last updated:\s+\d{4}-\d{2}-\d{2}$", flags=re.MULTILINE),
    re.compile(r"^- Последнее обновление:\s+\d{4}-\d{2}-\d{2}$", flags=re.MULTILINE),
)
WHERE_TO_START_PATTERNS = (
    "## Where to Start",
    "## Где начать",
)
WORKFLOW_BASELINE_REQUIREMENTS: dict[str, tuple[tuple[str, str, str], ...]] = {
    "ops/ci/templates/workflows/arch.yml": (
        (
            "python_baseline",
            'python-version: "3.14"',
            "Architecture workflow must use the Python 3.14 contributor baseline.",
        ),
        (
            "node_baseline",
            'node-version: "22"',
            "Architecture workflow must use the Node 22 contributor baseline.",
        ),
        (
            "uv_sync",
            "uv sync --frozen --extra lint --extra test --extra runtime --extra causal-discovery",
            "Architecture workflow must install Python dependencies via the canonical `uv sync` baseline.",
        ),
        (
            "pnpm_install",
            "corepack pnpm install --frozen-lockfile",
            "Architecture workflow must use the canonical `corepack pnpm` frontend install.",
        ),
        (
            "uv_guardrails",
            "uv run polisyos-tools architecture guardrails check",
            "Architecture workflow must run the architecture guardrails inside the synced `uv` environment.",
        ),
    ),
}
WORKFLOW_BASELINE_FORBIDDEN: dict[str, tuple[tuple[str, str, str], ...]] = {
    "ops/ci/templates/workflows/arch.yml": (
        (
            "legacy_pip_install",
            'pip install -e ".[dev,test,causal-discovery]"',
            "Architecture workflow must not bootstrap repo dependencies with `pip install -e`; use `uv sync` instead.",
        ),
        (
            "legacy_npm_ci",
            "run: npm ci",
            "Architecture workflow must not use `npm ci`; use `corepack pnpm install --frozen-lockfile` instead.",
        ),
        (
            "legacy_npm_install",
            "run: npm install",
            "Architecture workflow must not use `npm install`; use `corepack pnpm install --frozen-lockfile` instead.",
        ),
    ),
}


@dataclass(frozen=True)
class PackagePolicy:
    module: str
    classification: str
    facade_mode: str
    owner: str
    readme: Path
    reference_doc: Path
    supported_entrypoints: tuple[str, ...]
    major_subsystem: bool
    notes: str


@dataclass(frozen=True)
class PackageInventory:
    module: str
    classification: str
    facade_mode_expected: str
    facade_mode_observed: str
    owner: str
    readme: str
    reference_doc: str
    supported_entrypoints: tuple[str, ...]
    major_subsystem: bool
    export_count: int
    exports: tuple[str, ...]
    has___getattr__: bool
    has___dir__: bool
    source_file: str
    summary: str
    notes: str


@dataclass(frozen=True)
class DeepImportEdge:
    source_module: str
    source_root: str
    source_file: str
    target_module: str
    target_root: str

    @property
    def key(self) -> str:
        return f"{self.source_module}->{self.target_module}"


@dataclass(frozen=True)
class GuardrailException:
    exception_id: str
    check: str
    owner: str
    reason: str
    expires: dt.date
    subject_glob: str
    detail_glob: str
    source_module_glob: str
    target_module_glob: str


@dataclass(frozen=True)
class GuardrailViolation:
    check: str
    subject: str
    message: str
    detail: str = ""
    source_module: str = ""
    target_module: str = ""


@dataclass(frozen=True)
class ReadmeGateSubject:
    module: str
    readme: str
    major_subsystem: bool
    reason: str
    detail: str = ""


@dataclass(frozen=True)
class GeneratedArtifactFamily:
    family_id: str
    label: str
    owner: str
    approval_owner: str
    lifecycle: str
    generator: str
    verifier: str
    promotion_target: str
    stale_output_behavior: str
    source_of_truth: str
    outputs: tuple[Path, ...]
    regenerate_commands: tuple[str, ...]
    commit_policy: str
    freshness_rule: str
    drift_gate: str
    workflow: Path | None
    check_cwd: Path | None
    check_command: tuple[str, ...] | None
    check_git_diff_paths: tuple[Path, ...]
    retention_days: int | None


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render and validate architecture guardrail inventories."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    sync = subparsers.add_parser("sync", help="Render inventories and baseline files.")
    _add_common_args(sync)
    sync.add_argument(
        "--skip-deep-import-baseline",
        action="store_true",
        help="Do not rewrite the deep-import baseline JSON.",
    )

    check = subparsers.add_parser("check", help="Validate manifests, inventories, and baselines.")
    _add_common_args(check)
    check.add_argument(
        "--run-generated-checks",
        action="store_true",
        help="Run automated generated-artifact freshness checks declared in the manifest.",
    )
    check.add_argument(
        "--max-expiry-days",
        type=int,
        default=DEFAULT_MAX_EXPIRY_DAYS,
        help="Maximum allowed exception lifetime in days.",
    )

    return parser.parse_args()


def _add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--public-manifest", type=Path, default=DEFAULT_PUBLIC_MANIFEST)
    parser.add_argument("--public-json", type=Path, default=DEFAULT_PUBLIC_JSON)
    parser.add_argument("--public-md", type=Path, default=DEFAULT_PUBLIC_MD)
    parser.add_argument("--generated-manifest", type=Path, default=DEFAULT_GENERATED_MANIFEST)
    parser.add_argument("--generated-md", type=Path, default=DEFAULT_GENERATED_MD)
    parser.add_argument("--deep-import-baseline", type=Path, default=DEFAULT_DEEP_IMPORT_BASELINE)
    parser.add_argument("--exceptions", type=Path, default=DEFAULT_EXCEPTION_FILE)
    parser.add_argument("--exceptions-registry", type=Path, default=DEFAULT_EXCEPTION_REGISTRY)


def _read_toml(path: Path) -> dict[str, Any]:
    return tomllib.loads(path.read_text(encoding="utf-8"))


def _ensure_relative(path_str: str) -> Path:
    path = Path(path_str)
    return path if path.is_absolute() else REPO_ROOT / path


def _parse_check_command(value: Any) -> tuple[str, ...] | None:
    if value is None:
        return None
    if isinstance(value, str):
        return tuple(shlex.split(value))
    return tuple(str(part) for part in value)


def _parse_public_surface(path: Path) -> list[PackagePolicy]:
    data = _read_toml(path)
    packages = data.get("package", [])
    results: list[PackagePolicy] = []
    for item in packages:
        module = str(item["module"])
        results.append(
            PackagePolicy(
                module=module,
                classification=str(item["classification"]),
                facade_mode=str(item["facade_mode"]),
                owner=str(item["owner"]),
                readme=_ensure_relative(str(item["readme"])),
                reference_doc=_ensure_relative(str(item["reference_doc"])),
                supported_entrypoints=tuple(item.get("supported_entrypoints", [])),
                major_subsystem=bool(item.get("major_subsystem", False)),
                notes=str(item.get("notes", "")),
            )
        )
    return results


def _parse_generated_artifacts(path: Path) -> list[GeneratedArtifactFamily]:
    data = _read_toml(path)
    families = data.get("family", [])
    results: list[GeneratedArtifactFamily] = []
    for item in families:
        workflow_raw = item.get("workflow")
        check_cwd_raw = item.get("check_cwd")
        check_command_raw = item.get("check_command")
        results.append(
            GeneratedArtifactFamily(
                family_id=str(item["id"]),
                label=str(item["label"]),
                owner=str(item["owner"]),
                approval_owner=str(item["approval_owner"]),
                lifecycle=str(item.get("lifecycle", "")),
                generator=str(item.get("generator", "")),
                verifier=str(item.get("verifier", "")),
                promotion_target=str(item.get("promotion_target", "")),
                stale_output_behavior=str(item.get("stale_output_behavior", "")),
                source_of_truth=str(item["source_of_truth"]),
                outputs=tuple(_ensure_relative(output) for output in item.get("outputs", [])),
                regenerate_commands=tuple(
                    str(command) for command in item.get("regenerate_commands", [])
                ),
                commit_policy=str(item["commit_policy"]),
                freshness_rule=str(item["freshness_rule"]),
                drift_gate=str(item["drift_gate"]),
                workflow=_ensure_relative(str(workflow_raw)) if workflow_raw else None,
                check_cwd=_ensure_relative(str(check_cwd_raw)) if check_cwd_raw else None,
                check_command=_parse_check_command(check_command_raw),
                check_git_diff_paths=tuple(
                    Path(part) for part in item.get("check_git_diff_paths", [])
                ),
                retention_days=(
                    int(item["retention_days"]) if item.get("retention_days") is not None else None
                ),
            )
        )
    return results


def _parse_guardrail_exceptions(path: Path) -> list[GuardrailException]:
    if not path.exists():
        return []
    data = _read_toml(path)
    entries = data.get("exception", [])
    results: list[GuardrailException] = []
    for item in entries:
        results.append(
            GuardrailException(
                exception_id=str(item["id"]),
                check=str(item["check"]),
                owner=str(item["owner"]),
                reason=str(item["reason"]),
                expires=dt.date.fromisoformat(str(item["expires"])),
                subject_glob=str(item.get("subject_glob", "*")),
                detail_glob=str(item.get("detail_glob", "*")),
                source_module_glob=str(item.get("source_module_glob", "*")),
                target_module_glob=str(item.get("target_module_glob", "*")),
            )
        )
    return results


def _module_name_for_path(file_path: Path) -> tuple[str, bool] | None:
    relative = file_path.relative_to(SRC_ROOT)
    parts = list(relative.parts)
    if not parts or parts[0] != "polisyos":
        return None
    if parts[-1] == "__init__.py":
        return ".".join(parts[:-1]), True
    parts[-1] = parts[-1].removesuffix(".py")
    return ".".join(parts), False


def _iter_py_files() -> list[Path]:
    return sorted(path for path in SRC_ROOT.rglob("*.py") if "__pycache__" not in path.parts)


def _root_for_module(module: str) -> str | None:
    parts = module.split(".")
    if len(parts) < 2 or parts[0] != "polisyos":
        return None
    return parts[1]


def _resolve_import_module(
    current_module: str, is_package: bool, node: ast.ImportFrom
) -> str | None:
    if node.level == 0:
        return node.module
    package_parts = current_module.split(".")
    if not is_package:
        package_parts = package_parts[:-1]
    if node.level - 1 > len(package_parts):
        return None
    base_parts = package_parts[: len(package_parts) - (node.level - 1)]
    if node.module:
        base_parts += node.module.split(".")
    return ".".join(base_parts)


def _string_list_value(node: ast.AST) -> tuple[str, ...] | None:
    try:
        value = ast.literal_eval(node)
    except Exception:
        return None
    if isinstance(value, (list, tuple)) and all(isinstance(item, str) for item in value):
        return tuple(value)
    return None


def _extract_exports(tree: ast.Module) -> tuple[str, ...]:
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "__all__":
                    exports = _string_list_value(node.value)
                    if exports is not None:
                        return exports
        if isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name) and node.target.id == "__all__" and node.value:
                exports = _string_list_value(node.value)
                if exports is not None:
                    return exports
    return ()


def _observed_facade_mode(*, exports: tuple[str, ...], has_getattr: bool) -> str:
    if exports and has_getattr:
        return "lazy_facade"
    if exports:
        return "eager_exports"
    return "module_doc_only"


def _package_file_for(module: str) -> Path:
    relative = Path(*module.split("."))
    return SRC_ROOT / relative / "__init__.py"


def build_public_surface_inventory(policies: list[PackagePolicy]) -> list[PackageInventory]:
    inventory: list[PackageInventory] = []
    for policy in policies:
        source_file = _package_file_for(policy.module)
        if not source_file.exists():
            raise FileNotFoundError(f"Public surface module file not found: {source_file}")
        tree = ast.parse(source_file.read_text(encoding="utf-8"))
        exports = _extract_exports(tree)
        function_names = {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}
        summary = (ast.get_docstring(tree) or "").strip().splitlines()
        inventory.append(
            PackageInventory(
                module=policy.module,
                classification=policy.classification,
                facade_mode_expected=policy.facade_mode,
                facade_mode_observed=_observed_facade_mode(
                    exports=exports,
                    has_getattr="__getattr__" in function_names,
                ),
                owner=policy.owner,
                readme=str(policy.readme.relative_to(REPO_ROOT)),
                reference_doc=str(policy.reference_doc.relative_to(REPO_ROOT)),
                supported_entrypoints=policy.supported_entrypoints,
                major_subsystem=policy.major_subsystem,
                export_count=len(exports),
                exports=exports,
                has___getattr__="__getattr__" in function_names,
                has___dir__="__dir__" in function_names,
                source_file=str(source_file.relative_to(REPO_ROOT)),
                summary=summary[0] if summary else "",
                notes=policy.notes,
            )
        )
    return inventory


def collect_deep_import_edges(policies: list[PackagePolicy]) -> list[DeepImportEdge]:
    allowed_entrypoints: dict[str, set[str]] = {}
    for policy in policies:
        root = _root_for_module(policy.module)
        if root is None:
            continue
        allowed_entrypoints.setdefault(root, set()).update(policy.supported_entrypoints)

    edges: dict[str, DeepImportEdge] = {}
    for file_path in _iter_py_files():
        module_info = _module_name_for_path(file_path)
        if module_info is None:
            continue
        source_module, is_package = module_info
        source_root = _root_for_module(source_module)
        if source_root is None:
            continue
        tree = ast.parse(file_path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            target_module: str | None = None
            if isinstance(node, ast.Import):
                for alias in node.names:
                    target_module = alias.name
                    _maybe_add_deep_import(
                        edges=edges,
                        allowed_entrypoints=allowed_entrypoints,
                        source_module=source_module,
                        source_root=source_root,
                        source_file=file_path,
                        target_module=target_module,
                    )
            elif isinstance(node, ast.ImportFrom):
                target_module = _resolve_import_module(source_module, is_package, node)
                if target_module:
                    _maybe_add_deep_import(
                        edges=edges,
                        allowed_entrypoints=allowed_entrypoints,
                        source_module=source_module,
                        source_root=source_root,
                        source_file=file_path,
                        target_module=target_module,
                    )
    return sorted(edges.values(), key=lambda edge: (edge.source_module, edge.target_module))


def _maybe_add_deep_import(
    *,
    edges: dict[str, DeepImportEdge],
    allowed_entrypoints: dict[str, set[str]],
    source_module: str,
    source_root: str,
    source_file: Path,
    target_module: str,
) -> None:
    if target_module == "polisyos" or not target_module.startswith("polisyos."):
        return
    target_root = _root_for_module(target_module)
    if target_root is None or target_root == source_root:
        return
    if target_module == f"polisyos.{target_root}":
        return
    if target_module in allowed_entrypoints.get(target_root, set()):
        return
    edge = DeepImportEdge(
        source_module=source_module,
        source_root=source_root,
        source_file=str(source_file.relative_to(REPO_ROOT)),
        target_module=target_module,
        target_root=target_root,
    )
    edges[edge.key] = edge


def _parse_registry_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    ids: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if "|" not in line:
            continue
        parts = [part.strip() for part in line.split("|")]
        if len(parts) < 3:
            continue
        first = parts[1].strip().strip("`")
        if not first or first in {"id", "---", "_no-active-exceptions_", "-"}:
            continue
        ids.add(first)
    return ids


def render_public_surface_json(inventory: list[PackageInventory]) -> str:
    payload = {
        "version": 1,
        "internal_rule": "Any polisyos module path not listed here is internal by default.",
        "packages": [
            {
                "module": item.module,
                "classification": item.classification,
                "facade_mode_expected": item.facade_mode_expected,
                "facade_mode_observed": item.facade_mode_observed,
                "owner": item.owner,
                "readme": item.readme,
                "reference_doc": item.reference_doc,
                "supported_entrypoints": list(item.supported_entrypoints),
                "major_subsystem": item.major_subsystem,
                "export_count": item.export_count,
                "exports": list(item.exports),
                "has___getattr__": item.has___getattr__,
                "has___dir__": item.has___dir__,
                "source_file": item.source_file,
                "summary": item.summary,
                "notes": item.notes,
            }
            for item in inventory
        ],
    }
    return json.dumps(payload, indent=2, ensure_ascii=True) + "\n"


def render_public_surface_markdown(inventory: list[PackageInventory]) -> str:
    lines = [
        "# Public Surface",
        "",
        "> Generated from `architecture/public_surface/contract.toml` and package facades under `src/polisyos/**/__init__.py`.",
        "",
        "Canonical regeneration command:",
        "",
        "```bash",
        "uv run python tools/devx/architecture/guardrails.py sync --skip-deep-import-baseline",
        "```",
        "",
        "Supported entrypoints are intentionally explicit. Any `polisyos.*` path not listed on this page is **internal** and may change without compatibility guarantees.",
        "",
        "Classification policy:",
        "",
        "- `public_stable`: supported entrypoint with normal compatibility, release-note, and migration expectations.",
        "- `public_experimental`: documented entrypoint that should stay visible in docs and release notes when touched, but it does not promise long-term compatibility.",
        "- `internal`: any `polisyos.*` path not listed here; keep it out of public docs and release notes unless operators must care.",
        "",
        "| Package | Classification | Facade | Exports | Owner | README |",
        "| --- | --- | --- | ---: | --- | --- |",
    ]
    for item in inventory:
        readme_rel = item.readme
        lines.append(
            f"| `{item.module}` | `{item.classification}` | `{item.facade_mode_observed}` | {item.export_count} | `{item.owner}` | `{readme_rel}` |"
        )

    for item in inventory:
        lines.extend(
            [
                "",
                f"## `{item.module}`",
                "",
                f"- Classification: `{item.classification}`",
                f"- Supported entrypoints: {', '.join(f'`{entry}`' for entry in item.supported_entrypoints)}",
                f"- Facade policy: expected `{item.facade_mode_expected}`, observed `{item.facade_mode_observed}`",
                f"- Owner: `{item.owner}`",
                f"- README: `{item.readme}`",
                f"- Reference doc: `{item.reference_doc}`",
                f"- Notes: {item.notes}",
            ]
        )
        if item.summary:
            lines.append(f"- Summary: {item.summary}")
        if item.export_count:
            lines.extend(
                [
                    "",
                    f"<details><summary>Supported exports ({item.export_count})</summary>",
                    "",
                    "```text",
                    *item.exports,
                    "```",
                    "",
                    "</details>",
                ]
            )
        else:
            lines.extend(
                [
                    "",
                    "This package does not expose a package-level `__all__` facade. Treat the module root itself as the only documented entrypoint.",
                ]
            )
    lines.append("")
    return "\n".join(lines)


def render_deep_import_baseline_json(edges: list[DeepImportEdge]) -> str:
    payload = {
        "version": 1,
        "rule": "Cross-package imports should prefer documented supported entrypoints. This baseline freezes existing deep-import edges so new creep fails review.",
        "edges": [
            {
                "source_module": edge.source_module,
                "source_root": edge.source_root,
                "source_file": edge.source_file,
                "target_module": edge.target_module,
                "target_root": edge.target_root,
            }
            for edge in edges
        ],
    }
    return json.dumps(payload, indent=2, ensure_ascii=True) + "\n"


def render_generated_artifacts_markdown(families: list[GeneratedArtifactFamily]) -> str:
    lines = [
        "# Generated Artifacts",
        "",
        "> Generated from `architecture/generated_artifacts.toml`.",
        "> Regenerate this page with `uv run polisyos-tools architecture guardrails sync`.",
        "> Validate drift with `uv run polisyos-tools architecture guardrails check`.",
        "",
        "Every committed generated artifact family must have a source of truth, a regeneration command, a freshness rule, and an approval owner.",
        "",
        "| Family | Lifecycle | Commit policy | Drift gate | Owner | Outputs |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for family in families:
        outputs = "<br/>".join(f"`{_repo_display_path(path)}`" for path in family.outputs)
        lines.append(
            f"| `{family.label}` | `{family.lifecycle}` | `{family.commit_policy}` | `{family.drift_gate}` | `{family.owner}` | {outputs} |"
        )

    for family in families:
        lines.extend(
            [
                "",
                f"## `{family.label}`",
                "",
                f"- Family id: `{family.family_id}`",
                f"- Lifecycle: `{family.lifecycle}`",
                f"- Source of truth: {family.source_of_truth}",
                f"- Generator: {family.generator}",
                f"- Verifier: {family.verifier}",
                f"- Promotion target: {family.promotion_target}",
                f"- Commit policy: `{family.commit_policy}`",
                f"- Freshness rule: {family.freshness_rule}",
                f"- Stale output behavior: `{family.stale_output_behavior}`",
                f"- Drift gate: `{family.drift_gate}`",
                f"- Owner: `{family.owner}`",
                f"- Approval owner: `{family.approval_owner}`",
            ]
        )
        if family.retention_days is not None:
            lines.append(f"- Retention: `{family.retention_days}` days")
        if family.workflow is not None:
            lines.append(f"- Related workflow/config: `{_repo_display_path(family.workflow)}`")
        lines.extend(
            [
                "- Outputs:",
                *[f"  - `{_repo_display_path(output)}`" for output in family.outputs],
                "",
                "Canonical regeneration commands:",
                "",
                "```bash",
                *family.regenerate_commands,
                "```",
            ]
        )
    lines.append("")
    return "\n".join(lines)


def _repo_display_path(path: Path) -> str:
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return os.path.relpath(path, REPO_ROOT)


def _write_if_changed(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return
    path.write_text(content, encoding="utf-8")


def _diff(label: str, expected: str, current: str) -> str:
    lines = difflib.unified_diff(
        current.splitlines(),
        expected.splitlines(),
        fromfile=f"{label} (current)",
        tofile=f"{label} (expected)",
        lineterm="",
    )
    return "\n".join(lines)


def _readme_gate_subjects(inventory: list[PackageInventory]) -> list[ReadmeGateSubject]:
    subjects: dict[tuple[str, str], ReadmeGateSubject] = {}
    for item in inventory:
        subjects[(item.module, item.readme)] = ReadmeGateSubject(
            module=item.module,
            readme=item.readme,
            major_subsystem=item.major_subsystem,
            reason=f"public_surface:{item.classification}",
        )

    if DEFAULT_MODULE_SIZE_BUDGET.exists():
        budget = _read_toml(DEFAULT_MODULE_SIZE_BUDGET)
        for item in budget.get("budget", []):
            path = Path(str(item.get("path", "")))
            if len(path.parts) < 3 or path.parts[:2] != ("src", "polisyos"):
                continue
            module = f"polisyos.{path.parts[2]}"
            readme = f"src/polisyos/{path.parts[2]}/README.md"
            key = (module, readme)
            existing = subjects.get(key)
            reason = "high_complexity"
            if existing is not None:
                reason = f"{existing.reason},high_complexity"
            subjects[key] = ReadmeGateSubject(
                module=module,
                readme=readme,
                major_subsystem=existing.major_subsystem if existing else False,
                reason=reason,
                detail=path.as_posix(),
            )

    return sorted(subjects.values(), key=lambda subject: (subject.readme, subject.module))


def _check_readmes(inventory: list[PackageInventory]) -> list[GuardrailViolation]:
    violations: list[GuardrailViolation] = []
    for item in _readme_gate_subjects(inventory):
        readme_path = REPO_ROOT / item.readme
        if not readme_path.exists():
            violations.append(
                GuardrailViolation(
                    check="readme_policy",
                    subject=item.readme,
                    detail=item.reason,
                    message=(
                        f"Missing package README for {item.module}: {item.readme} "
                        f"({item.reason})"
                    ),
                )
            )
            continue
        text = readme_path.read_text(encoding="utf-8")
        if not any(pattern.search(text) for pattern in FRESHNESS_PATTERNS):
            violations.append(
                GuardrailViolation(
                    check="readme_policy",
                    subject=item.readme,
                    detail=f"freshness_marker:{item.reason}",
                    message=(
                        f"{item.readme} is missing a README freshness marker "
                        f"(`Last updated` / `Последнее обновление`) for {item.reason}."
                    ),
                )
            )
        if item.major_subsystem and not any(marker in text for marker in WHERE_TO_START_PATTERNS):
            violations.append(
                GuardrailViolation(
                    check="readme_policy",
                    subject=item.readme,
                    detail=f"where_to_start:{item.reason}",
                    message=f"{item.readme} must include a `Where to Start` section.",
                )
            )
    return violations


def _check_public_surface_contracts(inventory: list[PackageInventory]) -> list[GuardrailViolation]:
    violations: list[GuardrailViolation] = []
    for item in inventory:
        if item.facade_mode_expected != item.facade_mode_observed:
            violations.append(
                GuardrailViolation(
                    check="public_surface",
                    subject=item.module,
                    detail="facade_mode",
                    message=(
                        f"{item.module} facade drift: expected `{item.facade_mode_expected}`, "
                        f"observed `{item.facade_mode_observed}`."
                    ),
                )
            )
        if item.facade_mode_expected == "lazy_facade" and not item.has___getattr__:
            violations.append(
                GuardrailViolation(
                    check="public_surface",
                    subject=item.module,
                    detail="lazy_facade_getattr",
                    message=f"{item.module} is expected to be lazy but has no `__getattr__` facade.",
                )
            )
        if item.facade_mode_expected in {"lazy_facade", "eager_exports"} and item.export_count == 0:
            violations.append(
                GuardrailViolation(
                    check="public_surface",
                    subject=item.module,
                    detail="missing_exports",
                    message=f"{item.module} must expose a non-empty `__all__` surface.",
                )
            )
        if not (REPO_ROOT / item.reference_doc).exists():
            violations.append(
                GuardrailViolation(
                    check="public_surface",
                    subject=item.module,
                    detail="reference_doc",
                    message=f"Reference doc missing for {item.module}: {item.reference_doc}",
                )
            )
    return violations


def _check_generated_artifact_manifest(
    families: list[GeneratedArtifactFamily],
) -> list[GuardrailViolation]:
    violations: list[GuardrailViolation] = []
    seen_ids: set[str] = set()
    allowed_lifecycles = {
        "source_committed",
        "generated_committed",
        "generated_ignored",
        "runtime_ignored",
        "scratch_ignored",
    }
    allowed_stale_behaviors = {
        "fail",
        "warn",
        "cleanup_eligible",
        "ignored_by_policy",
        "block_release",
    }
    for family in families:
        if family.family_id in seen_ids:
            violations.append(
                GuardrailViolation(
                    check="generated_artifact",
                    subject=family.family_id,
                    detail="duplicate_family_id",
                    message=f"Duplicate generated artifact family id: {family.family_id}",
                )
            )
        seen_ids.add(family.family_id)
        for field, value in (
            ("lifecycle", family.lifecycle),
            ("generator", family.generator),
            ("verifier", family.verifier),
            ("promotion_target", family.promotion_target),
            ("stale_output_behavior", family.stale_output_behavior),
        ):
            if not value.strip():
                violations.append(
                    GuardrailViolation(
                        check="generated_artifact",
                        subject=family.family_id,
                        detail=f"missing_{field}",
                        message=f"{family.family_id} must declare `{field}`.",
                    )
                )
        if family.lifecycle and family.lifecycle not in allowed_lifecycles:
            violations.append(
                GuardrailViolation(
                    check="generated_artifact",
                    subject=family.family_id,
                    detail="invalid_lifecycle",
                    message=f"{family.family_id} has invalid lifecycle `{family.lifecycle}`.",
                )
            )
        if (
            family.stale_output_behavior
            and family.stale_output_behavior not in allowed_stale_behaviors
        ):
            violations.append(
                GuardrailViolation(
                    check="generated_artifact",
                    subject=family.family_id,
                    detail="invalid_stale_output_behavior",
                    message=(
                        f"{family.family_id} has invalid stale_output_behavior "
                        f"`{family.stale_output_behavior}`."
                    ),
                )
            )
        if family.commit_policy == "local_ignored" and family.lifecycle == "generated_committed":
            violations.append(
                GuardrailViolation(
                    check="generated_artifact",
                    subject=family.family_id,
                    detail="commit_policy_lifecycle_mismatch",
                    message=(
                        f"{family.family_id} cannot be local_ignored with "
                        "generated_committed lifecycle."
                    ),
                )
            )
        if family.commit_policy == "committed" and family.lifecycle in {
            "generated_ignored",
            "runtime_ignored",
            "scratch_ignored",
        }:
            violations.append(
                GuardrailViolation(
                    check="generated_artifact",
                    subject=family.family_id,
                    detail="commit_policy_lifecycle_mismatch",
                    message=(
                        f"{family.family_id} committed family must not use ignored lifecycle "
                        f"`{family.lifecycle}`."
                    ),
                )
            )
        if family.workflow is not None and not family.workflow.exists():
            violations.append(
                GuardrailViolation(
                    check="workflow_config",
                    subject=_repo_display_path(family.workflow),
                    detail=family.family_id,
                    message=(
                        f"Workflow/config drift: missing file {_repo_display_path(family.workflow)}"
                    ),
                )
            )
        if not family.regenerate_commands:
            violations.append(
                GuardrailViolation(
                    check="generated_artifact",
                    subject=family.family_id,
                    detail="missing_regeneration_command",
                    message=f"{family.family_id} must declare at least one regeneration command.",
                )
            )
        if family.commit_policy == "committed":
            for output in family.outputs:
                if not output.exists():
                    violations.append(
                        GuardrailViolation(
                            check="generated_artifact",
                            subject=family.family_id,
                            detail=_repo_display_path(output),
                            message=(
                                f"{family.family_id} declares committed output "
                                f"{_repo_display_path(output)} but the path is missing."
                            ),
                        )
                    )
    return violations


def _run_generated_artifact_checks(
    families: list[GeneratedArtifactFamily],
) -> list[GuardrailViolation]:
    violations: list[GuardrailViolation] = []
    for family in families:
        if family.check_command is None:
            continue
        cwd = family.check_cwd or REPO_ROOT
        before_outputs: dict[Path, bytes | None] = {}
        for path in family.check_git_diff_paths:
            absolute = cwd / path
            before_outputs[path] = absolute.read_bytes() if absolute.exists() else None
        result = subprocess.run(
            list(family.check_command),
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            output = (result.stdout or "") + (result.stderr or "")
            violations.append(
                GuardrailViolation(
                    check="generated_artifact",
                    subject=family.family_id,
                    detail="automated_drift_check",
                    message=f"{family.family_id} automated drift check failed:\n{output.strip()}",
                )
            )
            continue
        if family.check_git_diff_paths:
            changed_paths: list[str] = []
            for path in family.check_git_diff_paths:
                absolute = cwd / path
                before = before_outputs.get(path)
                after = absolute.read_bytes() if absolute.exists() else None
                if before != after:
                    changed_paths.append(str(path))
            if changed_paths:
                violations.append(
                    GuardrailViolation(
                        check="generated_artifact",
                        subject=family.family_id,
                        detail="git_diff_drift",
                        message=(
                            f"{family.family_id} regeneration changed "
                            f"{', '.join(changed_paths)}. Re-run the canonical generation command and commit the refreshed outputs."
                        ),
                    )
                )
    return violations


def _check_workflow_toolchain_guardrails() -> list[GuardrailViolation]:
    violations: list[GuardrailViolation] = []
    for workflow_rel, rules in WORKFLOW_BASELINE_REQUIREMENTS.items():
        workflow_path = REPO_ROOT / workflow_rel
        if not workflow_path.exists():
            violations.append(
                GuardrailViolation(
                    check="workflow_config",
                    subject=workflow_rel,
                    detail="missing_workflow",
                    message=f"Workflow/config drift: missing file {workflow_rel}",
                )
            )
            continue
        text = workflow_path.read_text(encoding="utf-8")
        for detail, snippet, message in rules:
            if snippet not in text:
                violations.append(
                    GuardrailViolation(
                        check="workflow_config",
                        subject=workflow_rel,
                        detail=detail,
                        message=f"{message} Expected snippet: `{snippet}`",
                    )
                )
    for workflow_rel, rules in WORKFLOW_BASELINE_FORBIDDEN.items():
        workflow_path = REPO_ROOT / workflow_rel
        if not workflow_path.exists():
            continue
        text = workflow_path.read_text(encoding="utf-8")
        for detail, snippet, message in rules:
            if snippet in text:
                violations.append(
                    GuardrailViolation(
                        check="workflow_config",
                        subject=workflow_rel,
                        detail=detail,
                        message=f"{message} Found forbidden snippet: `{snippet}`",
                    )
                )
    return violations


def _validate_guardrail_exceptions(
    exceptions_path: Path,
    registry_path: Path,
    *,
    max_expiry_days: int,
) -> list[str]:
    violations: list[str] = []
    try:
        registry_label = str(registry_path.relative_to(REPO_ROOT))
    except ValueError:
        registry_label = str(registry_path)
    try:
        exceptions_label = str(exceptions_path.relative_to(REPO_ROOT))
    except ValueError:
        exceptions_label = str(exceptions_path)
    if not exceptions_path.exists():
        violations.append(f"Guardrail exceptions file not found: {exceptions_label}")
        return violations
    registry_ids = _parse_registry_ids(registry_path)
    today = dt.date.today()
    max_expiry = today + dt.timedelta(days=max_expiry_days)
    seen_ids: set[str] = set()
    for exception in _parse_guardrail_exceptions(exceptions_path):
        if exception.exception_id in seen_ids:
            violations.append(f"Duplicate guardrail exception id: {exception.exception_id}")
        seen_ids.add(exception.exception_id)
        if exception.expires < today:
            violations.append(f"Guardrail exception `{exception.exception_id}` is expired.")
        if exception.expires > max_expiry:
            violations.append(
                f"Guardrail exception `{exception.exception_id}` exceeds {max_expiry_days}-day max expiry window."
            )
        if exception.exception_id not in registry_ids:
            violations.append(
                f"Guardrail exception `{exception.exception_id}` is missing from {registry_label}."
            )
    return violations


def _load_deep_import_baseline(path: Path) -> dict[str, DeepImportEdge]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    results: dict[str, DeepImportEdge] = {}
    for item in payload.get("edges", []):
        edge = DeepImportEdge(
            source_module=str(item["source_module"]),
            source_root=str(item["source_root"]),
            source_file=str(item["source_file"]),
            target_module=str(item["target_module"]),
            target_root=str(item["target_root"]),
        )
        results[edge.key] = edge
    return results


def _exception_matches_violation(
    exception: GuardrailException,
    violation: GuardrailViolation,
) -> bool:
    if exception.check != violation.check:
        return False
    if violation.check == "deep_import":
        return fnmatch.fnmatch(
            violation.source_module, exception.source_module_glob
        ) and fnmatch.fnmatch(violation.target_module, exception.target_module_glob)
    return fnmatch.fnmatch(violation.subject, exception.subject_glob) and fnmatch.fnmatch(
        violation.detail or "", exception.detail_glob
    )


def _apply_guardrail_exceptions(
    violations: list[GuardrailViolation],
    exceptions: list[GuardrailException],
) -> list[str]:
    emitted: list[str] = []
    for violation in violations:
        if any(_exception_matches_violation(exception, violation) for exception in exceptions):
            continue
        emitted.append(violation.message)
    return emitted


def _check_deep_import_creep(
    *,
    baseline_path: Path,
    current_edges: list[DeepImportEdge],
) -> list[GuardrailViolation]:
    violations: list[GuardrailViolation] = []
    if not baseline_path.exists():
        return [
            GuardrailViolation(
                check="deep_import",
                subject=str(baseline_path.relative_to(REPO_ROOT)),
                detail="missing_baseline",
                message=f"Deep-import baseline file not found: {baseline_path.relative_to(REPO_ROOT)}",
            )
        ]
    baseline_edges = _load_deep_import_baseline(baseline_path)
    current_by_key = {edge.key: edge for edge in current_edges}

    for key, edge in sorted(current_by_key.items()):
        if key in baseline_edges:
            continue
        violations.append(
            GuardrailViolation(
                check="deep_import",
                subject=edge.source_module,
                detail=edge.target_module,
                source_module=edge.source_module,
                target_module=edge.target_module,
                message=(
                    "New deep-import creep detected: "
                    f"{edge.source_module} -> {edge.target_module} "
                    f"({edge.source_file}). Add a stable facade, update the baseline intentionally, "
                    "or register a temporary exception."
                ),
            )
        )
    return violations


def run_sync(args: argparse.Namespace) -> int:
    public_policies = _parse_public_surface(args.public_manifest)
    public_inventory = build_public_surface_inventory(public_policies)
    families = _parse_generated_artifacts(args.generated_manifest)
    deep_import_edges = collect_deep_import_edges(public_policies)

    _write_if_changed(args.public_json, render_public_surface_json(public_inventory))
    _write_if_changed(args.public_md, render_public_surface_markdown(public_inventory))
    if not args.skip_deep_import_baseline:
        _write_if_changed(
            args.deep_import_baseline,
            render_deep_import_baseline_json(deep_import_edges),
        )
    _write_if_changed(args.generated_md, render_generated_artifacts_markdown(families))
    print("Architecture guardrail inventories updated.")
    return 0


def run_check(args: argparse.Namespace) -> int:
    violations: list[str] = []

    public_policies = _parse_public_surface(args.public_manifest)
    public_inventory = build_public_surface_inventory(public_policies)
    expected_public_json = render_public_surface_json(public_inventory)
    expected_public_md = render_public_surface_markdown(public_inventory)
    expected_deep_import_baseline = render_deep_import_baseline_json(
        collect_deep_import_edges(public_policies)
    )
    families = _parse_generated_artifacts(args.generated_manifest)
    expected_generated_md = render_generated_artifacts_markdown(families)
    guardrail_exceptions = _parse_guardrail_exceptions(args.exceptions)

    if not args.public_json.exists():
        violations.append(
            f"Missing public surface inventory JSON: {args.public_json.relative_to(REPO_ROOT)}"
        )
    elif args.public_json.read_text(encoding="utf-8") != expected_public_json:
        violations.append(
            "Public surface inventory JSON drift detected.\n"
            + _diff(
                str(args.public_json.relative_to(REPO_ROOT)),
                expected_public_json,
                args.public_json.read_text(encoding="utf-8"),
            )
        )

    if not args.public_md.exists():
        violations.append(
            f"Missing public surface reference doc: {args.public_md.relative_to(REPO_ROOT)}"
        )
    elif args.public_md.read_text(encoding="utf-8") != expected_public_md:
        violations.append(
            "Public surface reference doc drift detected.\n"
            + _diff(
                str(args.public_md.relative_to(REPO_ROOT)),
                expected_public_md,
                args.public_md.read_text(encoding="utf-8"),
            )
        )

    if not args.generated_md.exists():
        violations.append(
            f"Missing generated-artifacts reference doc: {args.generated_md.relative_to(REPO_ROOT)}"
        )
    elif args.generated_md.read_text(encoding="utf-8") != expected_generated_md:
        violations.append(
            "Generated-artifacts reference doc drift detected.\n"
            + _diff(
                str(args.generated_md.relative_to(REPO_ROOT)),
                expected_generated_md,
                args.generated_md.read_text(encoding="utf-8"),
            )
        )

    if not args.deep_import_baseline.exists():
        violations.append(
            f"Missing deep-import baseline: {args.deep_import_baseline.relative_to(REPO_ROOT)}"
        )
    elif args.deep_import_baseline.read_text(encoding="utf-8") != expected_deep_import_baseline:
        violations.append(
            "Deep-import baseline drift detected. Re-run "
            "`uv run polisyos-tools architecture guardrails sync` only when intentionally "
            "accepting the new baseline.\n"
            + _diff(
                str(args.deep_import_baseline.relative_to(REPO_ROOT)),
                expected_deep_import_baseline,
                args.deep_import_baseline.read_text(encoding="utf-8"),
            )
        )

    violations.extend(
        _apply_guardrail_exceptions(
            _check_public_surface_contracts(public_inventory),
            guardrail_exceptions,
        )
    )
    violations.extend(
        _apply_guardrail_exceptions(
            _check_readmes(public_inventory),
            guardrail_exceptions,
        )
    )
    violations.extend(
        _validate_guardrail_exceptions(
            args.exceptions, args.exceptions_registry, max_expiry_days=args.max_expiry_days
        )
    )
    violations.extend(
        _apply_guardrail_exceptions(
            _check_deep_import_creep(
                baseline_path=args.deep_import_baseline,
                current_edges=collect_deep_import_edges(public_policies),
            ),
            guardrail_exceptions,
        )
    )
    violations.extend(
        _apply_guardrail_exceptions(
            _check_generated_artifact_manifest(families),
            guardrail_exceptions,
        )
    )
    violations.extend(
        _apply_guardrail_exceptions(
            _check_workflow_toolchain_guardrails(),
            guardrail_exceptions,
        )
    )

    if args.run_generated_checks:
        violations.extend(
            _apply_guardrail_exceptions(
                _run_generated_artifact_checks(families),
                guardrail_exceptions,
            )
        )

    if violations:
        print("Architecture guardrail check FAILED:")
        for violation in violations:
            print(f"- {violation}")
        return 1

    print("Architecture guardrail check passed.")
    return 0


def main() -> int:
    args = _parse_args()
    if args.command == "sync":
        return run_sync(args)
    return run_check(args)


if __name__ == "__main__":
    raise SystemExit(main())
