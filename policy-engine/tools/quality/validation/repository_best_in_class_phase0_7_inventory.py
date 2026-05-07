#!/usr/bin/env python3
"""Read-only Phase 0.7 inventory for repository best-in-class remediation."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python < 3.11 fallback.
    import tomli as tomllib  # type: ignore[no-redef]


SCHEMA_VERSION = 1
PHASE = "0.7"
SNAPSHOT_DATE = "2026-05-05"
REPORT_PATH = Path("docs/archive/reports/REPOSITORY_BEST_IN_CLASS_PHASE_0_7_DECISION_BRIEF.md")
MASTER_PLAN = Path(
    "docs/plans/archive/2026-05-07-repository-best-in-class-remediation-master-plan.md"
)

ADR_REQUIRED_MACHINE_FIELDS = (
    "status",
    "topic",
    "package",
    "supersedes",
    "superseded_by",
    "related",
)

SKIP_DIR_NAMES = {
    ".git",
    ".hg",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".hypothesis",
    ".benchmarks",
    ".basedpyright",
    ".cache",
    ".uv-cache",
    ".venv",
    ".venv_codex",
    ".tmp_c7_venv",
    "__pycache__",
    "node_modules",
    ".next",
    ".turbo",
    "_build",
    "_cache",
}

VENDOR_SKIP_DIR_NAMES = {
    ".git",
    ".hg",
    ".venv",
    ".venv_codex",
    ".tmp_c7_venv",
    "node_modules",
    ".next",
    ".turbo",
}

HIGH_VOLUME_SUBTREES = (
    "docs/adr",
    "schemas/snapshots/ir",
    "src/polisyos/foundry/methods/catalog/causal",
    "src/polisyos/ir/analytics",
    "src/polisyos/foundry/methods",
    "src/polisyos/data_forge/domains/legal/batch",
    "src/polisyos/data_forge/domains/catalog/batch",
    "src/polisyos/scientist/agent",
    "src/polisyos/scientist/search",
    "src/polisyos/scientist/orchestration/engine",
    "src/polisyos/runtime/http/services",
    "src/polisyos/fabric/connectors/sources",
    "apps/runtime-dashboard/src/shared/ui",
    "apps/runtime-dashboard/src/api",
    "apps/runtime-dashboard/src/features",
    "apps/runtime-dashboard/src/test",
    "tests/unit/foundry/methods/catalog/causal",
    "tests/unit/data_forge",
    "tests/unit/scientist/nodes",
    "tests/_data",
    "tests/_golden",
    "tests/_helpers",
    "docs/archive/reports",
)

NON_PRODUCT_PYTHON_ROOTS = (
    "benchmarks",
    "tools",
    "tests/_helpers",
    "tests/repo_quality/architecture",
    "tests/contract",
    "tests/integration",
    "tests/repo_quality/lint",
    "tests/property",
    "tests/repo_quality",
    "tests/repo_quality/tools",
    "tests/unit",
    "schemas/__init__.py",
)

LOCAL_RESIDUE_NAMES = {
    ".DS_Store",
    "__pycache__",
}

DATA_SUFFIXES = {
    ".csv",
    ".json",
    ".jsonl",
    ".parquet",
    ".pkl",
    ".toml",
    ".tsv",
    ".txt",
    ".yaml",
    ".yml",
}


def _default_repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _git_root(path: Path) -> Path:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=path,
            check=True,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return path
    return Path(completed.stdout.strip()).resolve()


def _git_lines(cwd: Path, *args: str) -> list[str]:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return []
    return [line for line in completed.stdout.splitlines() if line.strip()]


def _check_ignored(git_root: Path, path: Path) -> bool:
    try:
        rel = path.resolve().relative_to(git_root.resolve()).as_posix()
    except ValueError:
        rel = path.as_posix()
    result = subprocess.run(
        ["git", "check-ignore", "-q", "--", rel],
        cwd=git_root,
        check=False,
    )
    return result.returncode == 0


def _ignored_file_count(git_root: Path, path: Path) -> int:
    return len(
        _git_lines(
            git_root,
            "ls-files",
            "-o",
            "-i",
            "--exclude-standard",
            "--",
            path.as_posix(),
        )
    )


def _tracked_count(git_root: Path, path: Path) -> int:
    return len(_git_lines(git_root, "ls-files", "--", path.as_posix()))


def _status_count(git_root: Path, path: Path) -> int:
    return len(_git_lines(git_root, "status", "--short", "--", path.as_posix()))


def _walk_files(root: Path, *, skip_dir_names: set[str] | None = None) -> list[Path]:
    if not root.exists():
        return []
    skip = skip_dir_names or SKIP_DIR_NAMES
    files: list[Path] = []
    for current, dirnames, filenames in os.walk(root):
        dirnames[:] = [name for name in dirnames if name not in skip]
        for filename in filenames:
            files.append(Path(current) / filename)
    return sorted(files)


def _walk_dirs(root: Path, *, skip_dir_names: set[str] | None = None) -> list[Path]:
    if not root.exists():
        return []
    skip = skip_dir_names or SKIP_DIR_NAMES
    dirs: list[Path] = []
    for current, dirnames, _filenames in os.walk(root):
        dirnames[:] = [name for name in dirnames if name not in skip]
        dirs.append(Path(current))
    return sorted(dirs)


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def _load_pyproject(repo_root: Path) -> dict[str, Any]:
    path = repo_root / "pyproject.toml"
    if not path.exists():
        return {}
    with path.open("rb") as stream:
        return tomllib.load(stream)


def _line_count(path: Path) -> int:
    text = _read_text(path)
    return len(text.splitlines()) if text else 0


def _summary_by_suffix(files: list[Path]) -> dict[str, int]:
    counts = Counter(path.suffix.lower() or "<none>" for path in files)
    return dict(sorted(counts.items()))


def _markdown_table(headers: tuple[str, ...], rows: list[tuple[Any, ...]]) -> list[str]:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        values = [str(value).replace("\n", " ").replace("|", "\\|") for value in row]
        lines.append("| " + " | ".join(values) + " |")
    return lines


def _link(path: str) -> str:
    return f"`{path}`"


def _doc_tags(rel: str) -> list[str]:
    tags: list[str] = []
    name = Path(rel).name.lower()
    if "release" in name and ("note" in name or "notes" in name):
        tags.append("release-note")
    if rel.startswith("docs/brand/") or rel.startswith("design/"):
        tags.append("design")
    if rel.startswith("docs/migration/"):
        tags.append("migration")
    if rel.startswith("docs/adr/"):
        tags.append("adr")
    if rel.startswith("docs/runbooks/"):
        tags.append("runbook")
    if rel.startswith("docs/explanation/") or rel.startswith("architecture/"):
        tags.append("architecture-prose")
    if rel.startswith("docs/contracts/"):
        tags.append("contract-prose")
    if not tags:
        tags.append("docs-prose")
    return tags


def _doc_lifecycle(rel: str) -> str:
    if rel.startswith("docs/plans/active/"):
        return "active-plan"
    if rel.startswith("docs/plans/accepted/"):
        return "accepted-plan"
    if rel.startswith("docs/archive/"):
        return "archived"
    if rel.startswith("docs/adr/"):
        return "adr"
    if rel.startswith("docs/runbooks/"):
        return "runbook"
    if rel.startswith("docs/migration/"):
        return "migration"
    if rel.startswith("docs/brand/") or rel.startswith("design/"):
        return "design"
    if rel.startswith("docs/explanation/") or rel.startswith("architecture/"):
        return "architecture-prose"
    return "durable-doc"


def _collect_docs(repo_root: Path) -> dict[str, Any]:
    doc_roots = [repo_root / "docs", repo_root / "architecture", repo_root / "design"]
    docs: list[dict[str, Any]] = []
    for root in doc_roots:
        for path in _walk_files(root):
            if path.suffix.lower() not in {".md", ".rst", ".html"}:
                continue
            rel = _rel(path, repo_root)
            if rel == REPORT_PATH.as_posix():
                continue
            docs.append(
                {
                    "path": rel,
                    "lifecycle": _doc_lifecycle(rel),
                    "tags": _doc_tags(rel),
                    "lines": _line_count(path),
                    "future_phase": _doc_future_phase(rel),
                }
            )

    lifecycle_counts = Counter(row["lifecycle"] for row in docs)
    tag_counts: Counter[str] = Counter()
    for row in docs:
        tag_counts.update(row["tags"])
    return {
        "documents": sorted(docs, key=lambda row: row["path"]),
        "lifecycle_counts": dict(sorted(lifecycle_counts.items())),
        "tag_counts": dict(sorted(tag_counts.items())),
    }


def _doc_future_phase(rel: str) -> str:
    if rel.startswith("docs/adr/"):
        return "2.6, 6.4"
    if rel.startswith("docs/plans/"):
        return "2.6, 6.4"
    if rel.startswith("docs/runbooks/"):
        return "4.9, 5.7"
    if rel.startswith("docs/archive/"):
        return "2.6, 2.9, 6.4"
    if rel.startswith("docs/brand/") or rel.startswith("design/"):
        return "4.10, 6.4"
    if rel.startswith("docs/migration/"):
        return "2.6, 5.6"
    return "4.10, 5.7, 6.4"


def _front_matter_fields(text: str) -> dict[str, str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    fields: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        fields[key.strip().lower()] = value.strip()
    return fields


def _heading_title(text: str, fallback: str) -> str:
    for line in text.splitlines():
        if line.startswith("# "):
            return line.removeprefix("# ").strip()
    return fallback


def _body_status(text: str) -> str:
    lines = text.splitlines()
    for index, line in enumerate(lines):
        lowered = line.strip().lower()
        if lowered in {"## status", "### status"}:
            for candidate in lines[index + 1 :]:
                stripped = candidate.strip()
                if stripped:
                    return stripped.strip("`* ")
        match = re.match(r"[-*]\s+\*\*(status|статус)\*\*\s*:\s*(.+)", line, flags=re.I)
        if match:
            return match.group(2).strip()
    return ""


def _body_related_present(text: str) -> bool:
    lowered = text.lower()
    return "related decisions" in lowered or "related:" in lowered or "extends:" in lowered


def _adr_id_from_path(path: Path) -> str:
    name = path.stem
    patterns = (
        r"^(\d{4})",
        r"^adr-(\d+)",
        r"^repository-structure-(\d+)",
    )
    for pattern in patterns:
        match = re.search(pattern, name, flags=re.I)
        if match:
            return match.group(1)
    return name


def _collect_adr_metadata(repo_root: Path) -> dict[str, Any]:
    adr_root = repo_root / "docs" / "adr"
    support_names = {"README.md", "index.md", "_template.md", "template.md"}
    rows: list[dict[str, Any]] = []
    for path in sorted(adr_root.glob("*.md")):
        if path.name in support_names:
            continue
        text = _read_text(path)
        front_matter = _front_matter_fields(text)
        missing = [field for field in ADR_REQUIRED_MACHINE_FIELDS if not front_matter.get(field)]
        rows.append(
            {
                "id": _adr_id_from_path(path),
                "path": _rel(path, repo_root),
                "title": _heading_title(text, path.stem),
                "machine_status": front_matter.get("status", ""),
                "body_status": _body_status(text),
                "body_related_present": _body_related_present(text),
                "missing_machine_fields": missing,
                "missing_machine_count": len(missing),
                "future_phase": "2.6, 6.4",
            }
        )

    missing_field_counts = Counter()
    for row in rows:
        missing_field_counts.update(row["missing_machine_fields"])
    status_counts = Counter(
        (row["machine_status"] or row["body_status"] or "missing") for row in rows
    )
    return {
        "rows": rows,
        "missing_field_counts": dict(sorted(missing_field_counts.items())),
        "status_counts": dict(sorted(status_counts.items())),
        "total": len(rows),
        "all_fields_present": sum(1 for row in rows if not row["missing_machine_fields"]),
    }


def _py_modules(path: Path, repo_root: Path, *, recursive: bool = False) -> list[str]:
    if not path.exists():
        return []
    globber = path.rglob("*.py") if recursive else path.glob("*.py")
    modules = []
    for item in sorted(globber):
        if item.name == "__init__.py" or "__pycache__" in item.parts:
            continue
        modules.append(_rel(item, repo_root))
    return modules


def _child_dirs(path: Path, repo_root: Path) -> list[str]:
    if not path.exists():
        return []
    return [
        _rel(child, repo_root)
        for child in sorted(path.iterdir())
        if child.is_dir() and child.name not in SKIP_DIR_NAMES
    ]


def _collect_extension_points(repo_root: Path) -> dict[str, Any]:
    pyproject = _load_pyproject(repo_root)
    entry_points = pyproject.get("project", {}).get("entry-points", {})
    extension_contract_path = repo_root / "architecture/extension_points.toml"
    extension_contract = (
        tomllib.loads(extension_contract_path.read_text(encoding="utf-8"))
        if extension_contract_path.exists()
        else {}
    )
    contract_by_name = {
        row.get("name"): row for row in extension_contract.get("extension_point", [])
    }

    def _group_for(name: str) -> str:
        row = contract_by_name.get(name, {})
        return str(row.get("entry_point_group", name))

    def _registered_for(name: str) -> list[str]:
        group = _group_for(name)
        group_entries = entry_points.get(group, {})
        if isinstance(group_entries, dict):
            return sorted(group_entries)
        return []

    foundry_catalog = repo_root / "src/polisyos/foundry/methods/catalog"
    scientist_builtins = repo_root / "src/polisyos/scientist/nodes/builtins"
    data_forge_domains = repo_root / "src/polisyos/data_forge/domains"
    runtime_http = repo_root / "src/polisyos/runtime/http"
    lex_normpack = repo_root / "src/polisyos/lex/normpack"

    runtime_middlewares = []
    for path in sorted(runtime_http.glob("*middleware*.py")):
        runtime_middlewares.append(_rel(path, repo_root))
    for path in sorted(runtime_http.rglob("*.py")):
        if path in {repo_root / item for item in runtime_middlewares}:
            continue
        text = _read_text(path)
        if re.search(r"class\s+\w*Middleware\b", text):
            runtime_middlewares.append(_rel(path, repo_root))

    surfaces = [
        {
            "surface": "Fabric connectors",
            "path": "src/polisyos/fabric/connectors/sources",
            "entry_point_group": _group_for("polisyos.fabric_connectors"),
            "entry_points": _registered_for("polisyos.fabric_connectors"),
            "candidates": _py_modules(
                repo_root / "src/polisyos/fabric/connectors/sources",
                repo_root,
            ),
            "decision": "Version and compatibility metadata already start in pyproject entry points; source modules need contract coverage and installable examples.",
            "future_phase": "1.5, 5.10, 6.4",
        },
        {
            "surface": "Scientist governance passes",
            "path": "src/polisyos/scientist/governance/passes",
            "entry_point_group": _group_for("polisyos.scientist_governance_passes"),
            "entry_points": _registered_for("polisyos.scientist_governance_passes"),
            "candidates": _py_modules(
                repo_root / "src/polisyos/scientist/governance/passes",
                repo_root,
            ),
            "decision": "Entry points exist; pass ABI/version policy and external authoring docs remain Wave 1/Wave 6 work.",
            "future_phase": "1.5, 5.2, 6.4",
        },
        {
            "surface": "Foundry methods",
            "path": "src/polisyos/foundry/methods/catalog",
            "entry_point_group": _group_for("polisyos.foundry_methods"),
            "entry_points": _registered_for("polisyos.foundry_methods"),
            "candidates": _child_dirs(foundry_catalog, repo_root),
            "decision": "Catalog directories and registry boot modules are extension-like but not exposed through a project entry-point group yet.",
            "future_phase": "1.5, 4.2, 5.1, 6.4",
        },
        {
            "surface": "Scientist nodes",
            "path": "src/polisyos/scientist/nodes/builtins",
            "entry_point_group": _group_for("polisyos.scientist_nodes"),
            "entry_points": _registered_for("polisyos.scientist_nodes"),
            "candidates": _child_dirs(scientist_builtins, repo_root),
            "decision": "Builtin node domains are registry-backed extension candidates; external node ABI waits for Scientist API integration.",
            "future_phase": "1.5, 5.2, 6.4",
        },
        {
            "surface": "Data Forge domains",
            "path": "src/polisyos/data_forge/domains",
            "entry_point_group": _group_for("polisyos.data_forge_domains"),
            "entry_points": _registered_for("polisyos.data_forge_domains"),
            "candidates": _child_dirs(data_forge_domains, repo_root),
            "decision": "Domain packages behave like pluggable data products; directory/data placement contract is required before cleanup.",
            "future_phase": "1.5, 1.8, 2.9, 5.10, 6.2",
        },
        {
            "surface": "Lex norm packs",
            "path": "src/polisyos/lex/normpack",
            "entry_point_group": _group_for("polisyos.lex_normpacks"),
            "entry_points": _registered_for("polisyos.lex_normpacks"),
            "candidates": _py_modules(lex_normpack, repo_root, recursive=True)
            + ["src/polisyos/ir/norm_pack.py"],
            "decision": "NormPack code is present but lacks extension packaging and installable verification examples.",
            "future_phase": "1.5, 5.10, 6.4",
        },
        {
            "surface": "Runtime middlewares",
            "path": "src/polisyos/runtime/http",
            "entry_point_group": _group_for("polisyos.runtime_middlewares"),
            "entry_points": _registered_for("polisyos.runtime_middlewares"),
            "candidates": sorted(set(runtime_middlewares)),
            "decision": "Middleware classes are internal extension candidates; registration and deprecation policy should be explicit before externalizing.",
            "future_phase": "1.5, 5.10, 6.4",
        },
    ]
    return {"surfaces": surfaces}


def _collect_examples(repo_root: Path) -> dict[str, Any]:
    examples_root = repo_root / "examples"
    examples: list[dict[str, Any]] = []
    for path in _walk_files(examples_root):
        rel = _rel(path, repo_root)
        text = _read_text(path) if path.suffix in {".py", ".md", ".toml", ".yaml", ".yml"} else ""
        installable = path.suffix == ".py" and "polisyos" in text
        examples.append(
            {
                "path": rel,
                "suffix": path.suffix or "<none>",
                "installable_verification_candidate": installable,
                "decision": (
                    "promote to installable smoke/example asset"
                    if installable
                    else "keep as supporting example asset until Phase 6.4 discovery rules"
                ),
                "future_phase": "1.5, 4.10, 6.4",
            }
        )
    return {
        "rows": examples,
        "installable_candidates": [
            row for row in examples if row["installable_verification_candidate"]
        ],
    }


def _directory_file_counts(path: Path) -> dict[str, int]:
    files = _walk_files(path, skip_dir_names=VENDOR_SKIP_DIR_NAMES)
    counts = Counter()
    for file_path in files:
        parts = set(file_path.parts)
        if "__pycache__" in parts:
            counts["pycache_files"] += 1
            continue
        if file_path.name == ".DS_Store":
            counts["ds_store_files"] += 1
            continue
        counts["files"] += 1
        if file_path.suffix == ".py":
            counts["python_files"] += 1
        elif file_path.suffix in {".md", ".rst"}:
            counts["docs_files"] += 1
        elif file_path.suffix.lower() in DATA_SUFFIXES:
            counts["data_files"] += 1
        elif file_path.suffix in {".ts", ".tsx", ".js", ".jsx"}:
            counts["frontend_files"] += 1
    return dict(counts)


def _needs_for_subtree(path: Path) -> list[str]:
    needs: list[str] = []
    if path.is_dir() and not (path / "README.md").exists():
        needs.append("README")
    if path.is_dir() and not (path / "AUTHORING.md").exists():
        needs.append("AUTHORING")
    files = _walk_files(path, skip_dir_names=VENDOR_SKIP_DIR_NAMES)
    product_files = [
        file_path
        for file_path in files
        if "__pycache__" not in file_path.parts and file_path.name != ".DS_Store"
    ]
    if len(product_files) >= 50 and not (path / "index.md").exists():
        needs.append("generated-index")
    return needs


def _collect_high_volume_subtrees(repo_root: Path) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for rel in HIGH_VOLUME_SUBTREES:
        path = repo_root / rel
        exists = path.exists()
        counts = _directory_file_counts(path) if exists else {}
        needs = _needs_for_subtree(path) if exists and path.is_dir() else ["missing-path"]
        rows.append(
            {
                "path": rel,
                "exists": exists,
                "counts": counts,
                "has_readme": (path / "README.md").exists() if path.is_dir() else False,
                "has_authoring": (path / "AUTHORING.md").exists() if path.is_dir() else False,
                "has_index": (path / "index.md").exists() if path.is_dir() else False,
                "needs": needs,
                "future_phase": "1.8, 4.10, 5.7, 6.2, 6.4",
            }
        )
    return {"rows": rows}


def _top_level_role(name: str) -> str:
    roles = {
        ".claude": "local/editor-agent-metadata",
        ".cursor": "local/editor-agent-metadata",
        ".git": "git-control-state",
        ".github": "github-control-plane",
        "src": "product-source",
        "tests": "tests",
        "docs": "docs",
        "architecture": "architecture-contracts",
        "schemas": "schemas",
        "tools": "tooling",
        "benchmarks": "benchmarks",
        "frontend": "frontend-workspace",
        "examples": "examples",
        "ops": "ops",
        "data": "data",
        "design": "design",
        "release": "release-control",
        "release-fragments": "release-control",
        "packages": "workspace-packages",
        "_build": "local/generated-output",
        "_cache": "local/cache",
        ".polisyos": "local/runtime-state",
        "tmp": "local/scratch",
        "logs": "local/logs",
        "benchmark-results": "local/benchmark-output",
    }
    if name in roles:
        return roles[name]
    if name.startswith("."):
        return "local-or-control-metadata"
    return roles.get(name, "unclassified")


def _is_outer_local_only_root(name: str) -> bool:
    return name in {".claude", ".cursor", ".git", "_cache", "tmp"}


def _collect_top_level_dirs(repo_root: Path) -> dict[str, Any]:
    git_root = _git_root(repo_root)
    product_rows: list[dict[str, Any]] = []
    for child in sorted(repo_root.iterdir()):
        if not child.is_dir():
            continue
        rel = _rel(child, git_root)
        tracked = _tracked_count(git_root, child)
        ignored_file_count = _ignored_file_count(git_root, child)
        ignored = _check_ignored(git_root, child)
        product_rows.append(
            {
                "path": _rel(child, repo_root),
                "role": _top_level_role(child.name),
                "tracked_files": tracked,
                "status_paths": _status_count(git_root, child),
                "ignored": ignored,
                "local_only": tracked == 0 and ignored,
                "ignored_file_count": ignored_file_count,
                "git_relative": rel,
                "future_phase": "1.8, 2.9, 6.2",
            }
        )

    outer_rows: list[dict[str, Any]] = []
    if git_root != repo_root:
        for child in sorted(git_root.iterdir()):
            if child == repo_root:
                continue
            if not child.is_dir():
                continue
            tracked = _tracked_count(git_root, child)
            ignored_file_count = _ignored_file_count(git_root, child)
            ignored = (
                _check_ignored(git_root, child)
                or ignored_file_count > 0
                or child.name in {".claude", ".cursor", "_cache", "tmp"}
            )
            outer_rows.append(
                {
                    "path": _rel(child, git_root),
                    "role": _top_level_role(child.name),
                    "tracked_files": tracked,
                    "status_paths": _status_count(git_root, child),
                    "ignored": ignored,
                    "local_only": tracked == 0
                    and (ignored or _is_outer_local_only_root(child.name)),
                    "ignored_file_count": ignored_file_count,
                    "future_phase": "0.2, 1.1, 2.9, 6.2",
                }
            )
    return {"product_root": product_rows, "workspace_root": outer_rows}


def _collect_non_product_python_roots(repo_root: Path) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for rel in NON_PRODUCT_PYTHON_ROOTS:
        path = repo_root / rel
        if path.is_file():
            python_files = 1 if path.suffix == ".py" else 0
            package_markers = 1 if path.name == "__init__.py" else 0
            pycache_dirs = 0
        else:
            python_files = len(_py_modules(path, repo_root, recursive=True)) if path.exists() else 0
            package_markers = len(list(path.rglob("__init__.py"))) if path.exists() else 0
            pycache_dirs = len(
                [
                    item
                    for item in _walk_dirs(path, skip_dir_names=VENDOR_SKIP_DIR_NAMES)
                    if item.name == "__pycache__"
                ]
            )
        rows.append(
            {
                "path": rel,
                "exists": path.exists(),
                "python_files": python_files,
                "package_markers": package_markers,
                "pycache_dirs": pycache_dirs,
                "decision": "non-product import root; keep out of product package contracts",
                "future_phase": "1.4, 1.8, 2.4, 6.2",
            }
        )
    return {"rows": rows}


def _is_asset_path(path: Path) -> bool:
    parts = {part.lower() for part in path.parts}
    if parts & {"assets", "fixtures", "resources", "seeds", "seed_data"}:
        return True
    lowered = path.name.lower()
    return any(token in lowered for token in ("seed", "fixture", "golden", "snapshot"))


def _collect_assets(repo_root: Path) -> dict[str, Any]:
    all_files = _walk_files(repo_root, skip_dir_names=VENDOR_SKIP_DIR_NAMES)
    product_assets: list[str] = []
    test_fixtures: list[str] = []
    golden_snapshots: list[str] = []
    example_assets: list[str] = []
    frontend_test_fixtures: list[str] = []
    local_audit_reports: list[str] = []
    benchmark_reports: list[str] = []
    ds_store: list[str] = []
    pycache_dirs: list[str] = []
    egg_info: list[str] = []

    for path in all_files:
        rel = _rel(path, repo_root)
        is_residue = (
            path.name == ".DS_Store"
            or "__pycache__" in path.parts
            or any(part.endswith(".egg-info") for part in path.parts)
        )
        if path.name == ".DS_Store":
            ds_store.append(rel)
        if path.suffix in {".egg-info"} or path.name.endswith(".egg-info"):
            egg_info.append(rel)
        if is_residue:
            continue
        if rel.startswith("src/polisyos/") and _is_asset_path(path):
            product_assets.append(rel)
        if rel.startswith("tests/_data/") or ("/fixtures/" in rel and rel.startswith("tests/")):
            test_fixtures.append(rel)
        if (
            rel.startswith("tests/_golden/")
            or "golden" in rel.lower()
            or rel.startswith("schemas/snapshots/")
        ):
            golden_snapshots.append(rel)
        if rel.startswith("examples/"):
            example_assets.append(rel)
        if rel.startswith("apps/runtime-dashboard/src/test/") and "/fixtures/" in rel:
            frontend_test_fixtures.append(rel)
        if (
            "/_reports/" in rel
            or rel.startswith(".polisyos/reports/")
            or rel.startswith(".polisyos/audits/")
            or rel.startswith("docs/archive/reports/_logs")
        ):
            local_audit_reports.append(rel)
        if (
            rel.startswith("benchmark-results/")
            or rel.startswith("_build/benchmark-results/")
            or rel.startswith("benchmarks/_reports/")
            or rel.startswith(".benchmarks/")
        ):
            benchmark_reports.append(rel)

    for directory in _walk_dirs(repo_root, skip_dir_names=VENDOR_SKIP_DIR_NAMES):
        rel = _rel(directory, repo_root)
        if directory.name == "__pycache__":
            pycache_dirs.append(rel)
        if directory.name.endswith(".egg-info"):
            egg_info.append(rel)

    empty_dirs = [
        _rel(directory, repo_root)
        for directory in _walk_dirs(repo_root, skip_dir_names=VENDOR_SKIP_DIR_NAMES)
        if directory.is_dir() and not any(directory.iterdir())
    ]

    categories = {
        "product_seed_assets": sorted(set(product_assets)),
        "test_fixtures": sorted(set(test_fixtures)),
        "golden_records_snapshots": sorted(set(golden_snapshots)),
        "example_assets": sorted(set(example_assets)),
        "frontend_test_fixtures": sorted(set(frontend_test_fixtures)),
        "empty_directories": sorted(set(empty_dirs)),
        "ds_store": sorted(set(ds_store)),
        "pycache_dirs": sorted(set(pycache_dirs)),
        "egg_info_residue": sorted(set(egg_info)),
        "local_audit_reports": sorted(set(local_audit_reports)),
        "benchmark_reports": sorted(set(benchmark_reports)),
    }
    return {
        "categories": categories,
        "counts": {name: len(paths) for name, paths in sorted(categories.items())},
        "future_phase": "1.8, 2.4, 2.9, 6.2",
    }


def _collect_git_snapshot(repo_root: Path) -> dict[str, Any]:
    git_root = _git_root(repo_root)
    branch_lines = _git_lines(git_root, "branch", "--show-current")
    head_lines = _git_lines(git_root, "rev-parse", "--short", "HEAD")
    status_lines = _git_lines(git_root, "status", "--short")
    status_counts = Counter(line[:2] for line in status_lines)
    return {
        "git_root": _rel(git_root, repo_root),
        "branch": branch_lines[0] if branch_lines else "",
        "head": head_lines[0] if head_lines else "",
        "dirty_paths": len(status_lines),
        "status_counts": dict(sorted(status_counts.items())),
    }


def _decision_queue(inventory: dict[str, Any]) -> list[dict[str, str]]:
    return [
        {
            "finding": "Docs lifecycle surfaces exist across active, accepted, archive, migration, runbook, ADR, design, and architecture prose buckets.",
            "decision": "Create lifecycle/index contracts before moving documents or nav entries.",
            "future_phase": "2.6, 6.4",
        },
        {
            "finding": "ADR files mostly lack machine-readable status/topic/package/supersession metadata.",
            "decision": "Add ADR index TOML and generated topic/status pages.",
            "future_phase": "2.6, 6.4",
        },
        {
            "finding": "Extension candidates exceed the two current pyproject entry-point groups.",
            "decision": "Define versioned extension ABI contracts before externalizing Foundry, Scientist node, Lex, Data Forge, or Runtime middleware surfaces.",
            "future_phase": "1.5, 5.1, 5.2, 5.10, 6.4",
        },
        {
            "finding": "Examples are sparse and not packaged as verification assets.",
            "decision": "Promote installable examples only after extension contracts and directory contracts exist.",
            "future_phase": "1.5, 4.10, 6.4",
        },
        {
            "finding": "High-volume source, schema, docs, test, and frontend subtrees have uneven README/AUTHORING/index coverage.",
            "decision": "Draft directory contracts first; add README/AUTHORING/index files in documentation-only phases.",
            "future_phase": "1.8, 4.10, 5.7, 6.4",
        },
        {
            "finding": "Product assets, test fixtures, snapshots, benchmark reports, and local residue share ambiguous path conventions.",
            "decision": "Split product seed assets, test data, golden records, examples, and local reports through dedicated hygiene phases.",
            "future_phase": "1.8, 2.4, 2.9, 6.2",
        },
    ]


def collect_inventory(repo_root: Path) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    inventory: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "snapshot_date": SNAPSHOT_DATE,
        "master_plan": MASTER_PLAN.as_posix(),
        "git": _collect_git_snapshot(repo_root),
        "documentation": _collect_docs(repo_root),
        "adr_metadata": _collect_adr_metadata(repo_root),
        "extension_points": _collect_extension_points(repo_root),
        "examples": _collect_examples(repo_root),
        "top_level_directories": _collect_top_level_dirs(repo_root),
        "high_volume_subtrees": _collect_high_volume_subtrees(repo_root),
        "non_product_python_roots": _collect_non_product_python_roots(repo_root),
        "assets": _collect_assets(repo_root),
    }
    inventory["decision_queue"] = _decision_queue(inventory)
    return inventory


def validate_inventory(inventory: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    required_sections = (
        "documentation",
        "adr_metadata",
        "extension_points",
        "examples",
        "top_level_directories",
        "high_volume_subtrees",
        "non_product_python_roots",
        "assets",
        "decision_queue",
    )
    for section in required_sections:
        if section not in inventory:
            errors.append(f"missing section: {section}")
    if len(inventory.get("high_volume_subtrees", {}).get("rows", [])) != len(HIGH_VOLUME_SUBTREES):
        errors.append("high-volume subtree inventory is incomplete")
    if len(inventory.get("extension_points", {}).get("surfaces", [])) != 7:
        errors.append("extension-point surface inventory is incomplete")
    if not inventory.get("decision_queue"):
        errors.append("decision queue is empty")
    return errors


def dump_json(inventory: dict[str, Any]) -> str:
    return json.dumps(inventory, indent=2, sort_keys=True) + "\n"


def render_markdown(inventory: dict[str, Any]) -> str:
    lines: list[str] = [
        "---",
        "title: Repository Best-In-Class Phase 0.7 Decision Brief",
        "status: report",
        "owner: team-docs",
        f"created: {inventory['snapshot_date']}",
        f"last_verified: {inventory['snapshot_date']}",
        "stability: snapshot",
        "---",
        "",
        "# Repository Best-In-Class Phase 0.7 Decision Brief",
        "",
        "Generated by `tools/quality/validation/repository_best_in_class_phase0_7_inventory.py`.",
        "",
        "This read-only inventory implements Phase 0.7 of",
        f"`{inventory['master_plan']}`. It records documentation lifecycle, ADR",
        "metadata, extension-point candidates, examples, directory-contract",
        "inputs, non-product Python roots, assets, fixtures, snapshots, and local",
        "residue. It does not move docs, add docs navigation, promote examples,",
        "generate indexes, or clean directories.",
        "",
        "## Snapshot",
        "",
    ]

    git = inventory["git"]
    lines.extend(
        _markdown_table(
            ("Field", "Value"),
            [
                ("Date", inventory["snapshot_date"]),
                ("Branch", f"`{git['branch']}`" if git["branch"] else "`<unknown>`"),
                ("HEAD", f"`{git['head']}`" if git["head"] else "`<unknown>`"),
                ("Dirty paths", git["dirty_paths"]),
                ("Structural moves performed", "None"),
            ],
        )
    )
    lines.extend(["", "## Acceptance Coverage", ""])
    lines.extend(
        _markdown_table(
            ("Acceptance item", "Status", "Evidence"),
            [
                (
                    "Complete directory-closure, documentation, extension, and asset decision brief",
                    "complete",
                    "This report plus generated inventory sections below",
                ),
                (
                    "No docs lifecycle moves",
                    "preserved",
                    "Inventory only; no files are moved between docs buckets",
                ),
                (
                    "No examples promotion",
                    "preserved",
                    "Examples are classified as candidates only",
                ),
                (
                    "No directory cleanup",
                    "preserved",
                    "Residue and local-only roots are recorded only",
                ),
            ],
        )
    )

    lines.extend(["", "## Decision Queue", ""])
    lines.extend(
        _markdown_table(
            ("Finding", "Decision needed", "Future phase"),
            [
                (row["finding"], row["decision"], row["future_phase"])
                for row in inventory["decision_queue"]
            ],
        )
    )

    documentation = inventory["documentation"]
    lines.extend(["", "## Documentation Inventory", ""])
    lines.append("Lifecycle counts:")
    lines.extend(
        _markdown_table(
            ("Lifecycle", "Documents"),
            [(key, value) for key, value in documentation["lifecycle_counts"].items()],
        )
    )
    lines.extend(["", "Functional tag counts:"])
    lines.extend(
        _markdown_table(
            ("Tag", "Documents"),
            [(key, value) for key, value in documentation["tag_counts"].items()],
        )
    )
    lines.extend(["", "Lifecycle document map:"])
    lines.extend(
        _markdown_table(
            ("Path", "Lifecycle", "Tags", "Future phase"),
            [
                (
                    _link(row["path"]),
                    row["lifecycle"],
                    ", ".join(row["tags"]),
                    row["future_phase"],
                )
                for row in documentation["documents"]
            ],
        )
    )

    adr = inventory["adr_metadata"]
    lines.extend(["", "## ADR Metadata Inventory", ""])
    lines.extend(
        _markdown_table(
            ("Metric", "Value"),
            [
                ("ADR decision files", adr["total"]),
                ("ADRs with all required machine fields", adr["all_fields_present"]),
                ("Required machine fields", ", ".join(ADR_REQUIRED_MACHINE_FIELDS)),
            ],
        )
    )
    lines.extend(["", "Missing machine-readable field counts:"])
    lines.extend(
        _markdown_table(
            ("Field", "Missing ADRs"),
            [(key, value) for key, value in adr["missing_field_counts"].items()],
        )
    )
    lines.extend(["", "ADR machine-readable gap map:"])
    lines.extend(
        _markdown_table(
            ("ADR", "Body status", "Body related", "Missing machine fields", "Future phase"),
            [
                (
                    _link(row["path"]),
                    row["machine_status"] or row["body_status"] or "missing",
                    "yes" if row["body_related_present"] else "no",
                    ", ".join(row["missing_machine_fields"]) or "none",
                    row["future_phase"],
                )
                for row in adr["rows"]
            ],
        )
    )

    lines.extend(["", "## Extension-Point Inventory", ""])
    lines.extend(
        _markdown_table(
            (
                "Surface",
                "Path",
                "Entry points",
                "Candidates",
                "Decision",
                "Future phase",
            ),
            [
                (
                    row["surface"],
                    _link(row["path"]),
                    len(row["entry_points"]),
                    len(row["candidates"]),
                    row["decision"],
                    row["future_phase"],
                )
                for row in inventory["extension_points"]["surfaces"]
            ],
        )
    )
    for row in inventory["extension_points"]["surfaces"]:
        lines.extend(["", f"### {row['surface']}"])
        if row["entry_points"]:
            lines.append("")
            lines.append("Registered entry points:")
            for item in row["entry_points"]:
                lines.append(f"- `{item}`")
        if row["candidates"]:
            lines.append("")
            lines.append("Candidate paths:")
            for item in row["candidates"][:80]:
                lines.append(f"- `{item}`")
            if len(row["candidates"]) > 80:
                lines.append(f"- ... {len(row['candidates']) - 80} additional candidates omitted")

    examples = inventory["examples"]
    lines.extend(["", "## Examples Inventory", ""])
    lines.extend(
        _markdown_table(
            ("Path", "Installable verification candidate", "Decision", "Future phase"),
            [
                (
                    _link(row["path"]),
                    "yes" if row["installable_verification_candidate"] else "no",
                    row["decision"],
                    row["future_phase"],
                )
                for row in examples["rows"]
            ]
            or [("`examples/`", "no", "directory missing or empty", "1.5, 4.10, 6.4")],
        )
    )

    lines.extend(["", "## Directory Contract Inventory", ""])
    lines.append("Product-root top-level directories:")
    lines.extend(
        _markdown_table(
            (
                "Path",
                "Role",
                "Tracked files",
                "Status paths",
                "Ignored files",
                "Ignored",
                "Local-only",
                "Future phase",
            ),
            [
                (
                    _link(row["path"]),
                    row["role"],
                    row["tracked_files"],
                    row["status_paths"],
                    row["ignored_file_count"],
                    "yes" if row["ignored"] else "no",
                    "yes" if row["local_only"] else "no",
                    row["future_phase"],
                )
                for row in inventory["top_level_directories"]["product_root"]
            ],
        )
    )
    workspace_rows = inventory["top_level_directories"]["workspace_root"]
    if workspace_rows:
        lines.extend(["", "Workspace-root local-only directory candidates:"])
        lines.extend(
            _markdown_table(
                (
                    "Path",
                    "Role",
                    "Tracked files",
                    "Status paths",
                    "Ignored files",
                    "Ignored",
                    "Local-only",
                    "Future phase",
                ),
                [
                    (
                        _link(row["path"]),
                        row["role"],
                        row["tracked_files"],
                        row["status_paths"],
                        row["ignored_file_count"],
                        "yes" if row["ignored"] else "no",
                        "yes" if row["local_only"] else "no",
                        row["future_phase"],
                    )
                    for row in workspace_rows
                ],
            )
        )

    lines.extend(["", "High-volume subtree README/AUTHORING/index coverage:"])
    lines.extend(
        _markdown_table(
            (
                "Path",
                "Exists",
                "Files",
                "Python",
                "Docs",
                "Data",
                "README",
                "AUTHORING",
                "Index",
                "Needs",
                "Future phase",
            ),
            [
                (
                    _link(row["path"]),
                    "yes" if row["exists"] else "no",
                    row["counts"].get("files", 0),
                    row["counts"].get("python_files", 0),
                    row["counts"].get("docs_files", 0),
                    row["counts"].get("data_files", 0),
                    "yes" if row["has_readme"] else "no",
                    "yes" if row["has_authoring"] else "no",
                    "yes" if row["has_index"] else "no",
                    ", ".join(row["needs"]) or "none",
                    row["future_phase"],
                )
                for row in inventory["high_volume_subtrees"]["rows"]
            ],
        )
    )

    lines.extend(["", "Non-product Python roots outside `src/polisyos`:"])
    lines.extend(
        _markdown_table(
            (
                "Path",
                "Exists",
                "Python files",
                "Package markers",
                "Pycache dirs",
                "Decision",
                "Future phase",
            ),
            [
                (
                    _link(row["path"]),
                    "yes" if row["exists"] else "no",
                    row["python_files"],
                    row["package_markers"],
                    row["pycache_dirs"],
                    row["decision"],
                    row["future_phase"],
                )
                for row in inventory["non_product_python_roots"]["rows"]
            ],
        )
    )

    assets = inventory["assets"]
    lines.extend(["", "## Asset And Residue Inventory", ""])
    lines.extend(
        _markdown_table(
            ("Category", "Count", "Future phase"),
            [
                (category, count, assets["future_phase"])
                for category, count in assets["counts"].items()
            ],
        )
    )
    for category, paths in assets["categories"].items():
        lines.extend(["", f"### {category}"])
        if not paths:
            lines.append("")
            lines.append("None found.")
            continue
        lines.append("")
        for path in paths[:120]:
            lines.append(f"- `{path}`")
        if len(paths) > 120:
            lines.append(f"- ... {len(paths) - 120} additional paths omitted")

    lines.extend(
        [
            "",
            "## Verification",
            "",
            "Recommended refresh command:",
            "",
            "```bash",
            "uv run python tools/quality/validation/repository_best_in_class_phase0_7_inventory.py --check",
            "```",
            "",
            "Report-only regeneration command:",
            "",
            "```bash",
            "uv run python tools/quality/validation/repository_best_in_class_phase0_7_inventory.py --markdown-output docs/archive/reports/REPOSITORY_BEST_IN_CLASS_PHASE_0_7_DECISION_BRIEF.md",
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def check_artifacts(repo_root: Path, report_path: Path) -> list[str]:
    inventory = collect_inventory(repo_root)
    expected = render_markdown(inventory)
    if not report_path.exists():
        return [f"missing report: {report_path}"]
    actual = report_path.read_text(encoding="utf-8")
    if actual != expected:
        return [f"report out of date: {report_path}"]
    return validate_inventory(inventory)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=_default_repo_root())
    parser.add_argument("--json-output", type=Path, default=None)
    parser.add_argument("--markdown-output", type=Path, default=None)
    parser.add_argument("--check", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    repo_root = args.repo_root.resolve()
    report_path = repo_root / REPORT_PATH
    if args.check:
        errors = check_artifacts(repo_root, report_path)
        if errors:
            for error in errors:
                print(error)
            return 1
        print("Phase 0.7 inventory report is current.")
        return 0

    inventory = collect_inventory(repo_root)
    errors = validate_inventory(inventory)
    if errors:
        for error in errors:
            print(error)
        return 1
    if args.json_output is not None:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(dump_json(inventory), encoding="utf-8")
    markdown = render_markdown(inventory)
    if args.markdown_output is not None:
        args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
        args.markdown_output.write_text(markdown, encoding="utf-8")
    else:
        print(markdown)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
