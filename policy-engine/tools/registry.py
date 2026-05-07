"""Unified metadata registry for ``polisyos-tools``."""

from __future__ import annotations

import ast
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from tools.lib.imports import repo_root_from
from tools.lib.runner import ToolSpec, ToolStatus

TOOLS_ROOT = Path(__file__).resolve().parent

ZONE_ORDER: tuple[str, ...] = ("devx", "quality", "ops", "research")
ZONE_IMPLEMENTATION_DIRS: dict[str, str] = {
    "ops": "ops_runners",
}

_SKIP_FILES = {"__init__.py", "_common.py"}


@dataclass(frozen=True)
class CategoryManifestEntry:
    """Stable public category metadata and canonical implementation location."""

    zone: str
    category: str
    implementation_package: str
    implementation_root: Path
    compatibility_package: str
    summary: str


_CATEGORY_SUMMARIES: dict[str, str] = {
    "workspace": "Contributor bootstrap, doctor and verification flows",
    "architecture": "Architecture guardrails, inventories and scaffolds",
    "connectors": "Connector contract checks and scaffolding",
    "foundry": "Foundry code generation and signature baselines",
    "lint": "Import/lint/debt rules and autofix-capable quality gates",
    "diagnostics": "Schema, ABI, provenance and environment diagnostics",
    "validation": "Repo validation, docs accuracy and ratchet checks",
    "testing": "Mutation and local integration testing helpers",
    "ci": "CI policy and freshness checks",
    "deploy": "Deployment orchestration and operational handoff helpers",
    "cloud": "Cloud deploy, shard, pipeline and preflight helpers",
    "release": "Release gating, notes and canary orchestration",
    "migrations": "Artifact and storage migration tooling",
    "runtime": "Runtime API OpenAPI/client and legacy run maintenance",
    "data": "Data prep, review bundles and fixture capture",
    "ukraine_data": "Ukraine public-data ingestion and Lex corpus prep",
    "calibration": "Shard comparison and calibration helpers",
    "ops-experiments": "Operational experiment suites and campaign runners",
    "benchmarks": "Benchmark executable/orchestration surface",
    "demos": "Research/demo runnable surfaces retained for manual use",
    "research-experiments": "Research experiment helpers and topic organization tools",
}

_ZONE_CATEGORIES: dict[str, tuple[str, ...]] = {
    "devx": ("workspace", "architecture", "connectors", "foundry"),
    "quality": ("lint", "diagnostics", "validation", "testing", "ci"),
    "ops": (
        "calibration",
        "cloud",
        "data",
        "deploy",
        "ops-experiments",
        "migrations",
        "release",
        "runtime",
        "ukraine_data",
    ),
    "research": ("benchmarks", "demos", "research-experiments"),
}

_CATEGORY_IMPLEMENTATION_DIRS: dict[tuple[str, str], str] = {
    ("ops", "ops-experiments"): "experiments",
    ("research", "research-experiments"): "experiments",
}

SOURCE_PHASE_MAP: tuple[tuple[str, str, str], ...] = (
    (
        "Phase 0",
        "SQL/shell injection, shell safety, destructive operation guardrails",
        "`tools.lib.runner`, `tools.lib.sql`, `tools.lib.fs`",
    ),
    (
        "Phase 1",
        "atomicity, rollback, resource/I/O validation, degraded mode, legacy quarantine",
        "`tools.lib.fs`, `tools.lib.http`, `tools.lib.preflight`, lifecycle status metadata",
    ),
    (
        "Phase 2",
        "unified CLI, shared runtime, packaging/import normalization, "
        "dependency graph, docs metadata",
        "`polisyos-tools`, `tools.registry`, `tools.cli`, compatibility package shims",
    ),
    (
        "Phase 3",
        "critical tool test program, structured CI output, timing telemetry",
        "`tests/repo_quality/tools/**`, `tools.lib.output`, `tools.lib.timing`, workspace gates",
    ),
    (
        "Phase 4",
        "cloud, benchmarks, scripts, and duplicate namespace consolidation",
        "`tools/ops_runners/**`, `tools/research/**`, final topology and retired wrapper evidence",
    ),
    (
        "Phase 5",
        "incremental execution, cache, autofix/rule registry, hot-path maintainability",
        "`tools.lib.cache`, `tools/quality/lint/**`, targeted `--fix` and changed-file modes",
    ),
)


def _manifest_entry(zone: str, category: str) -> CategoryManifestEntry:
    implementation_zone = ZONE_IMPLEMENTATION_DIRS.get(zone, zone)
    implementation_dir = _CATEGORY_IMPLEMENTATION_DIRS.get((zone, category), category)
    implementation_package = f"tools.{implementation_zone}.{implementation_dir}"
    return CategoryManifestEntry(
        zone=zone,
        category=category,
        implementation_package=implementation_package,
        implementation_root=TOOLS_ROOT / implementation_zone / implementation_dir,
        compatibility_package=f"tools.{category}",
        summary=_CATEGORY_SUMMARIES[category],
    )


CATEGORY_MANIFEST: dict[str, CategoryManifestEntry] = {
    category: _manifest_entry(zone, category)
    for zone in ZONE_ORDER
    for category in _ZONE_CATEGORIES[zone]
}

_OVERRIDES: dict[tuple[str, str], dict[str, Any]] = {
    ("cloud", "deploy-to-server"): {
        "external_dependencies": ("ssh", "scp", "rsync"),
        "dependencies": ("cloud.prepare-shards", "cloud.setup-server"),
    },
    ("cloud", "check-progress"): {
        "external_dependencies": ("ssh",),
    },
    ("cloud", "run-pipeline"): {
        "external_dependencies": ("bash",),
    },
    ("cloud", "run-diagnostic"): {
        "dependencies": ("cloud.run-pipeline",),
    },
    ("cloud", "run-datasets-validation"): {
        "dependencies": ("cloud.run-pipeline",),
    },
    ("cloud", "run-remaining-stages"): {
        "status": ToolStatus.DEPRECATED,
        "replacement": "cloud run-pipeline --resume --snapshot-root ...",
        "reason": (
            "remaining-stage execution is now a compatibility bridge to the reviewed "
            "resume workflow"
        ),
        "dependencies": ("cloud.run-pipeline",),
    },
    ("diagnostics", "check-udf-perf"): {
        "status": ToolStatus.QUARANTINED,
        "required_imports": ("polisyos.fabric.udf.engine", "polisyos.fabric.io.graph_store"),
        "replacement": "diagnostics check-setup",
        "reason": "legacy UDF stack depends on modules that are not present in the current package",
    },
    ("demos", "run-udf-query-demo"): {
        "status": ToolStatus.QUARANTINED,
        "required_imports": ("polisyos.fabric.udf.engine",),
        "replacement": "diagnostics check-setup",
        "reason": "legacy UDF demo depends on the removed fabric.udf module family",
    },
    ("demos", "run-udf-hybrid-demo"): {
        "status": ToolStatus.QUARANTINED,
        "required_imports": ("polisyos.fabric.udf.engine", "polisyos.fabric.io.graph_store"),
        "replacement": "diagnostics check-setup",
        "reason": "legacy hybrid UDF demo depends on removed UDF/graph-store APIs",
    },
    ("demos", "run-export-demo"): {
        "status": ToolStatus.DEPRECATED,
        "replacement": "runtime export-runtime-openapi",
        "reason": (
            "demo uses historical Foundry import paths and is retained only as reference material"
        ),
    },
    ("demos", "run-mechanism-design"): {
        "status": ToolStatus.DEPRECATED,
        "replacement": "benchmarks bench-domain",
        "reason": "manual research demo predates the current Foundry method registry",
    },
    ("testing", "mutation"): {
        "external_dependencies": ("mutmut",),
    },
    ("foundry", "generate-stubs"): {
        "required_imports": ("mypy.stubgen",),
    },
    ("migrations", "migrate"): {
        "required_extras": ("pyyaml",),
        "reason": "YAML input/output requires PyYAML; JSON artifacts work without it",
    },
    ("runtime", "generate-runtime-client"): {
        "dependencies": ("runtime.export-runtime-openapi",),
    },
    ("diagnostics", "abi-diff"): {
        "dependencies": ("diagnostics.gen-schema",),
    },
    ("cloud", "run-lex-from-manifest"): {
        "dependencies": ("cloud.gcp-preflight",),
    },
    ("cloud", "merge-shards"): {
        "dependencies": ("cloud.run-lex-from-manifest",),
    },
    ("workspace", "bootstrap"): {
        "dependencies": ("workspace.doctor",),
    },
    ("workspace", "docs-style"): {
        "dependencies": (),
    },
    ("workspace", "ci-parity"): {},
    ("workspace", "format-check"): {
        "dependencies": (),
    },
    ("workspace", "lint-fast"): {
        "dependencies": (),
    },
    ("workspace", "lint-full"): {
        "dependencies": (
            "workspace.lint-fast",
            "workspace.format-check",
            "workspace.python-base-mypy",
            "workspace.python-base-basedpyright",
        ),
    },
    ("workspace", "core-runtime-closeout"): {},
    ("workspace", "acceptance-audit"): {},
    ("workspace", "remote-acceptance"): {},
    ("workspace", "doctor"): {},
    ("workspace", "verify"): {
        "dependencies": ("workspace.doctor",),
    },
    ("release", "stage-release-snapshot"): {
        "dependencies": ("release.check-release-version", "runtime.export-runtime-openapi"),
    },
}

LEGACY_ENTRYPOINTS: dict[str, str] = {}


def _command_name(path: Path) -> str:
    return path.stem.replace("_", "-")


def _iter_category_modules(entry: CategoryManifestEntry) -> tuple[tuple[Path, str], ...]:
    modules: list[tuple[Path, str]] = [
        (path, entry.implementation_package)
        for path in sorted(entry.implementation_root.glob("*.py"))
        if path.name not in _SKIP_FILES and not path.name.startswith(".")
    ]
    if entry.category == "ci":
        canonical_names = {path.name for path, _module_package in modules}
        modules.extend(
            (path, "tools.ci")
            for path in sorted((TOOLS_ROOT / "ci").glob("*.py"))
            if path.name not in _SKIP_FILES
            and not path.name.startswith(".")
            and path.name not in canonical_names
        )
    return tuple(modules)


def _module_name(module_package: str, path: Path) -> str:
    return f"{module_package}.{path.stem}"


def _extract_module_metadata(path: Path) -> tuple[str, str | None]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    summary = (ast.get_docstring(tree) or "").strip().splitlines()
    callable_name: str | None = None
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in {"main", "check"}:
            callable_name = node.name
            if node.name == "main":
                break
        if isinstance(node, ast.ImportFrom):
            imported_callables = {
                alias.asname or alias.name
                for alias in node.names
                if alias.name in {"main", "check"}
            }
            if "main" in imported_callables:
                callable_name = "main"
                break
            if "check" in imported_callables:
                callable_name = "check"
    return (summary[0] if summary else "", callable_name)


def _discover_specs() -> tuple[ToolSpec, ...]:
    specs: list[ToolSpec] = []
    for zone in ZONE_ORDER:
        for category in _ZONE_CATEGORIES[zone]:
            entry = CATEGORY_MANIFEST[category]
            for path, module_package in _iter_category_modules(entry):
                summary, callable_name = _extract_module_metadata(path)
                if callable_name is None:
                    continue
                command = _command_name(path)
                spec = ToolSpec(
                    name=command,
                    zone=entry.zone,
                    category=entry.category,
                    module=_module_name(module_package, path),
                    callable_name=callable_name,
                    summary=summary or f"{entry.category}/{path.stem}",
                )
                overrides = _OVERRIDES.get((category, command))
                if overrides:
                    spec = replace(spec, **overrides)
                specs.append(spec)
    return tuple(specs)


TOOL_SPECS: tuple[ToolSpec, ...] = _discover_specs()
TOOL_SPECS_BY_KEY: dict[tuple[str, str], ToolSpec] = {
    (spec.category, spec.name): spec for spec in TOOL_SPECS
}
TOOL_SPECS_BY_QUALIFIED_NAME: dict[str, ToolSpec] = {
    spec.qualified_name: spec for spec in TOOL_SPECS
}


def zones() -> tuple[str, ...]:
    return ZONE_ORDER


def categories() -> tuple[str, ...]:
    return tuple(category for zone in ZONE_ORDER for category in _ZONE_CATEGORIES[zone])


def categories_for_zone(zone: str) -> tuple[str, ...]:
    return _ZONE_CATEGORIES[zone]


def specs_for_zone(zone: str) -> tuple[ToolSpec, ...]:
    allowed = set(_ZONE_CATEGORIES[zone])
    return tuple(spec for spec in TOOL_SPECS if spec.category in allowed)


def specs_for_category(category: str) -> tuple[ToolSpec, ...]:
    return tuple(spec for spec in TOOL_SPECS if spec.category == category)


def category_zone(category: str) -> str:
    return CATEGORY_MANIFEST[category].zone


def get_spec(category: str, name: str) -> ToolSpec:
    try:
        return TOOL_SPECS_BY_KEY[(category, name)]
    except KeyError as exc:
        raise KeyError(f"unknown tool command: {category} {name}") from exc


def dependency_edges() -> tuple[tuple[str, str], ...]:
    edges: list[tuple[str, str]] = []
    for spec in TOOL_SPECS:
        for dependency in spec.dependencies:
            edges.append((dependency, spec.qualified_name))
    return tuple(sorted(edges))


def render_graph(format: str = "mermaid") -> str:
    edges = dependency_edges()
    if format == "json":
        import json

        return json.dumps({"edges": edges}, indent=2, sort_keys=True) + "\n"
    if format == "dot":
        lines = ["digraph polisyos_tools {"]
        for source, target in edges:
            lines.append(f'  "{source}" -> "{target}";')
        lines.append("}")
        return "\n".join(lines) + "\n"
    if format != "mermaid":
        raise ValueError(f"unsupported graph format: {format}")
    lines = ["graph TD"]
    if not edges:
        lines.append('  empty["No declared tool dependencies"]')
    for source, target in edges:
        lines.append(f'  "{source}" --> "{target}"')
    return "\n".join(lines) + "\n"


def _canonical_command(spec: ToolSpec) -> str:
    return f"polisyos-tools {spec.category} {spec.name}"


def render_reference_docs() -> str:
    repo_root = repo_root_from(__file__)
    lines = [
        "# Polisyos Tools Reference",
        "",
        "Generated from `tools.registry` command metadata.",
        "",
        "## D1-L5 Source Phase Map",
        "",
        "| Source phase | Focus | Current evidence |",
        "| ------------ | ----- | ---------------- |",
    ]
    for phase, focus, evidence in SOURCE_PHASE_MAP:
        lines.append(f"| {phase} | {focus} | {evidence} |")
    lines.extend(
        [
            "",
            "## Validation Contract",
            "",
            "- Regenerate this page with "
            "`uv run polisyos-tools docs --output docs/reference/tools.md`.",
            "- `polisyos-tools workspace ci-parity` includes docs accuracy, "
            "strict MkDocs build, and semantic docstring checks unless "
            "`--skip-docs` is set.",
            "- Deprecated and quarantined commands must keep `status`, "
            "`replacement`, and `reason` metadata in `tools.registry`.",
            "",
            "## Documentation Impact",
            "",
            "| Output cluster | Exact files | Source of truth | Validation |",
            "| -------------- | ----------- | --------------- | ---------- |",
            "| Generated command reference | `docs/reference/tools.md` | `tools.registry` command metadata, dependency graph edges, lifecycle status metadata | `uv run polisyos-tools docs --output docs/reference/tools.md` |",
            "| Tooling READMEs | `tools/README.md`, `tools/quality/validation/README.md`, `tools/devx/workspace/README.md`, `tools/devx/architecture/README.md` | canonical CLI behavior, workspace gates, validation helpers, architecture guardrails | `uv run polisyos-tools workspace ci-parity --skip-browser` |",
            "| Shared D1-L5 how-to/reference pages | `docs/how-to/operate-ci-cd-platform.md`, `docs/how-to/manage-generated-artifacts.md`, `docs/how-to/release-policy.md`, `docs/reference/quality-gates.md`, `docs/reference/dependency-platform.md`, `docs/reference/merge-governance.md`, `docs/reference/ratchet-policy.md` | repo workflows, generated-artifact guardrails, release tooling, ratchet policy docs | `uv run polisyos-tools architecture guardrails check` |",
            "",
            "## Backlog",
            "",
            "| Gap | Priority | Tracking note |",
            "| --- | -------- | ------------- |",
            "| No missing required D1-L5 output pages | - | All required D1-L5 files listed in `docs/plans/active/DOCUMENTATION_SOTA_PLAN.md` are present. |",
            "| Additional per-category README expansion outside the D1 scope | P3 | Further category-local docs can land in D2 without blocking the D1 closure criteria. |",
            "",
            "## Zones",
            "",
            "| Zone | Categories |",
            "| ---- | ---------- |",
        ]
    )
    for zone in zones():
        categories_csv = ", ".join(f"`{category}`" for category in categories_for_zone(zone))
        lines.append(f"| `{zone}` | {categories_csv} |")
    lines.extend(["", "## Commands", ""])
    for zone in zones():
        lines.extend([f"### `{zone}`", ""])
        lines.extend(
            [
                "| Category | Command | Status | Canonical | Summary | Replacement | "
                "Aliases | Dependencies |",
                "| -------- | ------- | ------ | --------- | ------- | ----------- | "
                "------- | ------------ |",
            ]
        )
        for category in categories_for_zone(zone):
            for spec in specs_for_category(category):
                deps = ", ".join(f"`{dep}`" for dep in spec.dependencies) or "-"
                aliases = ", ".join(f"`{alias}`" for alias in spec.aliases) or "-"
                replacement = spec.replacement or "-"
                lines.append(
                    f"| `{spec.category}` | `{spec.name}` | `{spec.status.value}` | "
                    f"`{_canonical_command(spec)}` | {spec.summary or '-'} | "
                    f"{replacement} | {aliases} | {deps} |"
                )
        lines.append("")
    lines.extend(
        [
            "## Retired Compatibility Wrappers",
            "",
            "Legacy path-based wrappers are retained only for the Phase 1D migration window.",
            "All wrappers emit a deprecation warning and sunset on 2026-09-01.",
            "",
            "| Legacy path | Replacement |",
            "| ----------- | ----------- |",
        ]
    )
    for legacy_path, replacement in sorted(LEGACY_ENTRYPOINTS.items()):
        lines.append(f"| `{legacy_path}` | {replacement} |")
    lifecycle_specs = tuple(spec for spec in TOOL_SPECS if spec.status != ToolStatus.ACTIVE)
    lines.extend(
        [
            "",
            "## Deprecated And Quarantined Commands",
            "",
            "| Category | Command | Status | Replacement | Reason |",
            "| -------- | ------- | ------ | ----------- | ------ |",
        ]
    )
    if lifecycle_specs:
        for spec in lifecycle_specs:
            replacement = spec.replacement or "-"
            reason = spec.reason or "-"
            lines.append(
                f"| `{spec.category}` | `{spec.name}` | `{spec.status.value}` | "
                f"{replacement} | {reason} |"
            )
    else:
        lines.append("| - | - | - | - | - |")
    lines.extend(
        [
            "",
            "## Policy",
            "",
            "- `tools/` is the only canonical executable surface.",
            "- The former product-root script tree is retired; use `polisyos-tools` commands directly.",
            "- New tools must be added to the zone/category manifest before "
            "creating any new top-level `tools/<category>` package.",
            "- Benchmark commands live under `tools/research/benchmarks`; root "
            "`benchmarks/` is benchmark-domain support code.",
            "",
            "## Dependency Graph",
            "",
            "```mermaid",
            render_graph("mermaid").rstrip(),
            "```",
            "",
            f"_Repo root: `{repo_root}`_",
            "",
        ]
    )
    return "\n".join(lines)
