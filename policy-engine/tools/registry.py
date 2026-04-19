"""Unified metadata registry for ``polisyos-tools``."""

from __future__ import annotations

import ast
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from tools._lib.imports import repo_root_from
from tools._lib.runner import ToolSpec, ToolStatus

TOOLS_ROOT = Path(__file__).resolve().parent

ZONE_ORDER: tuple[str, ...] = ("devx", "quality", "ops", "research")

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
    "cloud": "Cloud deploy, shard, pipeline and preflight helpers",
    "release": "Release gating, notes and canary orchestration",
    "migrations": "Artifact and storage migration tooling",
    "runtime": "Runtime API OpenAPI/client and legacy run maintenance",
    "data": "Data prep, review bundles and fixture capture",
    "ukraine_data": "Ukraine public-data ingestion and Lex corpus prep",
    "calibration": "Shard comparison and calibration helpers",
    "benchmarks": "Benchmark executable/orchestration surface",
    "demos": "Research/demo runnable surfaces retained for manual use",
}

_ZONE_CATEGORIES: dict[str, tuple[str, ...]] = {
    "devx": ("workspace", "architecture", "connectors", "foundry"),
    "quality": ("lint", "diagnostics", "validation", "testing", "ci"),
    "ops": ("cloud", "release", "migrations", "runtime", "data", "ukraine_data", "calibration"),
    "research": ("benchmarks", "demos"),
}

SOURCE_PHASE_MAP: tuple[tuple[str, str, str], ...] = (
    (
        "Phase 0",
        "SQL/shell injection, shell safety, destructive operation guardrails",
        "`tools._lib.runner`, `tools._lib.sql`, `tools._lib.fs`",
    ),
    (
        "Phase 1",
        "atomicity, rollback, resource/I/O validation, degraded mode, legacy quarantine",
        "`tools._lib.fs`, `tools._lib.http`, `tools._lib.preflight`, lifecycle status metadata",
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
        "`tests/tools/**`, `tools._lib.output`, `tools._lib.timing`, workspace gates",
    ),
    (
        "Phase 4",
        "cloud/scripts/benchmarks consolidation and deprecated cleanup",
        "`tools/ops/**`, `tools/research/**`, compatibility wrappers and deprecation metadata",
    ),
    (
        "Phase 5",
        "incremental execution, cache, autofix/rule registry, hot-path maintainability",
        "`tools._lib.cache`, `tools/quality/lint/**`, targeted `--fix` and changed-file modes",
    ),
)


def _manifest_entry(zone: str, category: str) -> CategoryManifestEntry:
    implementation_package = f"tools.{zone}.{category}"
    return CategoryManifestEntry(
        zone=zone,
        category=category,
        implementation_package=implementation_package,
        implementation_root=TOOLS_ROOT / zone / category,
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
        "aliases": (
            "./scripts/generate_stubs.py",
            "python scripts/generate_stubs.py",
            "python3 scripts/generate_stubs.py",
        ),
    },
    ("foundry", "update-signature-baseline"): {
        "aliases": (
            "./scripts/update_signature_baseline.py",
            "python scripts/update_signature_baseline.py",
            "python3 scripts/update_signature_baseline.py",
        ),
    },
    ("data", "build-academic-gold-candidates"): {
        "aliases": ("./scripts/build_academic_gold_candidates.py",),
    },
    ("data", "build-expert-review-bundle"): {
        "aliases": ("./scripts/build_expert_review_bundle.py",),
    },
    ("data", "generate-wvs-registry"): {
        "aliases": ("./scripts/generate_wvs_registry.py",),
    },
    ("data", "record-fixtures"): {
        "aliases": ("./scripts/record_fixtures.py",),
    },
    ("benchmarks", "benchmark-lex-llm-steady-state"): {
        "aliases": ("./scripts/benchmark_lex_llm_steady_state.py",),
    },
    ("benchmarks", "benchmark-lex-llm-sweep"): {
        "aliases": ("./scripts/benchmark_lex_llm_sweep.py",),
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
        "aliases": ("./scripts/bootstrap",),
    },
    ("workspace", "ci-parity"): {
        "aliases": ("./scripts/ci-parity",),
    },
    ("workspace", "core-runtime-closeout"): {
        "aliases": ("./scripts/core-runtime-closeout",),
    },
    ("workspace", "acceptance-audit"): {
        "aliases": ("./scripts/acceptance-audit",),
    },
    ("workspace", "remote-acceptance"): {
        "aliases": ("./scripts/remote-acceptance",),
    },
    ("workspace", "doctor"): {
        "aliases": ("./scripts/doctor",),
    },
    ("workspace", "verify"): {
        "dependencies": ("workspace.doctor",),
        "aliases": ("./scripts/verify",),
    },
    ("release", "stage-release-snapshot"): {
        "dependencies": ("release.check-release-version", "runtime.export-runtime-openapi"),
    },
}

LEGACY_ENTRYPOINTS: dict[str, str] = {
    "scripts/acceptance-audit": "polisyos-tools workspace acceptance-audit",
    "scripts/bootstrap": "polisyos-tools workspace bootstrap",
    "scripts/build_academic_gold_candidates.py": (
        "polisyos-tools data build-academic-gold-candidates"
    ),
    "scripts/build_expert_review_bundle.py": "polisyos-tools data build-expert-review-bundle",
    "scripts/ci-parity": "polisyos-tools workspace ci-parity",
    "scripts/core-runtime-closeout": "polisyos-tools workspace core-runtime-closeout",
    "scripts/doctor": "polisyos-tools workspace doctor",
    "scripts/generate_stubs.py": "polisyos-tools foundry generate-stubs",
    "scripts/generate_wvs_registry.py": "polisyos-tools data generate-wvs-registry",
    "scripts/record_fixtures.py": "polisyos-tools data record-fixtures",
    "scripts/remote-acceptance": "polisyos-tools workspace remote-acceptance",
    "scripts/update_signature_baseline.py": "polisyos-tools foundry update-signature-baseline",
    "scripts/verify": "polisyos-tools workspace verify",
    "scripts/benchmark_lex_llm_steady_state.py": (
        "polisyos-tools benchmarks benchmark-lex-llm-steady-state"
    ),
    "scripts/benchmark_lex_llm_sweep.py": "polisyos-tools benchmarks benchmark-lex-llm-sweep",
    "scripts/mutation_test.sh": "polisyos-tools testing mutation --suite foundry --target <target>",
    "scripts/mutation_test_scientist.sh": (
        "polisyos-tools testing mutation --suite scientist --target <target>"
    ),
    "benchmarks/run_all_benchmarks.sh": "polisyos-tools benchmarks run-all",
    "benchmarks/run_local_sota_profile.sh": "polisyos-tools benchmarks run-local-sota-profile",
    "benchmarks/build_release_summary.py": "polisyos-tools benchmarks build-release-summary",
    "benchmarks/prepare_real_benchmark_data.py": (
        "polisyos-tools benchmarks prepare-real-benchmark-data"
    ),
    "benchmarks/run_parallel.py": "polisyos-tools benchmarks run-parallel",
}


def _command_name(path: Path) -> str:
    return path.stem.replace("_", "-")


def _module_name(entry: CategoryManifestEntry, path: Path) -> str:
    return f"{entry.implementation_package}.{path.stem}"


def _extract_module_metadata(path: Path) -> tuple[str, str | None]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    summary = (ast.get_docstring(tree) or "").strip().splitlines()
    callable_name: str | None = None
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in {"main", "check"}:
            callable_name = node.name
            if node.name == "main":
                break
    return (summary[0] if summary else "", callable_name)


def _discover_specs() -> tuple[ToolSpec, ...]:
    specs: list[ToolSpec] = []
    for zone in ZONE_ORDER:
        for category in _ZONE_CATEGORIES[zone]:
            entry = CATEGORY_MANIFEST[category]
            for path in sorted(entry.implementation_root.glob("*.py")):
                if path.name in _SKIP_FILES or path.name.startswith("."):
                    continue
                summary, callable_name = _extract_module_metadata(path)
                if callable_name is None:
                    continue
                command = _command_name(path)
                spec = ToolSpec(
                    name=command,
                    zone=entry.zone,
                    category=entry.category,
                    module=_module_name(entry, path),
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
        "|---|---|---|",
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
            "|---|---|---|---|",
            "| Generated command reference | `docs/reference/tools.md` | `tools.registry` command metadata, dependency graph edges, lifecycle status metadata | `uv run polisyos-tools docs --output docs/reference/tools.md` |",
            "| Tooling READMEs | `tools/README.md`, `tools/validation/README.md`, `tools/devx/workspace/README.md`, `tools/devx/architecture/README.md` | canonical CLI behavior, workspace gates, validation helpers, architecture guardrails | `uv run polisyos-tools workspace ci-parity --skip-browser` |",
            "| Shared D1-L5 how-to/reference pages | `docs/how-to/operate-ci-cd-platform.md`, `docs/how-to/manage-generated-artifacts.md`, `docs/how-to/release-policy.md`, `docs/reference/quality-gates.md`, `docs/reference/dependency-platform.md`, `docs/reference/merge-governance.md`, `docs/reference/ratchet-policy.md` | repo workflows, generated-artifact guardrails, release tooling, ratchet policy docs | `uv run polisyos-tools architecture guardrails check` |",
            "",
            "## Backlog",
            "",
            "| Gap | Priority | Tracking note |",
            "|---|---|---|",
            "| No missing required D1-L5 output pages | - | All required D1-L5 files listed in `docs/DOCUMENTATION_SOTA_PLAN.md` are present. |",
            "| Additional per-category README expansion outside the D1 scope | P3 | Further category-local docs can land in D2 without blocking the D1 closure criteria. |",
            "",
            "## Zones",
            "",
            "| Zone | Categories |",
            "|---|---|",
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
                "|---|---|---|---|---|---|---|---|",
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
            "## Compatibility Wrappers",
            "",
            "| Legacy Path | Canonical Command |",
            "|---|---|",
        ]
    )
    for legacy_path, replacement in sorted(LEGACY_ENTRYPOINTS.items()):
        lines.append(f"| `{legacy_path}` | `{replacement}` |")
    lifecycle_specs = tuple(spec for spec in TOOL_SPECS if spec.status != ToolStatus.ACTIVE)
    lines.extend(
        [
            "",
            "## Deprecated And Quarantined Commands",
            "",
            "| Category | Command | Status | Replacement | Reason |",
            "|---|---|---|---|---|",
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
            "- `scripts/` and root `benchmarks/*` executables are compatibility "
            "wrappers for one deprecation window.",
            "- New tools must be added to the zone/category manifest before "
            "creating any new top-level `tools/<category>` package.",
            "- `tools/benchmarks` is the executable surface; root `benchmarks/` "
            "is benchmark-domain support code.",
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
