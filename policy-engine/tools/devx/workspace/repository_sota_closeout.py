#!/usr/bin/env python3
"""Enforce the Repository SOTA Phase 5 closeout gate."""

from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import hashlib
import io
import re
import shlex
import subprocess
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Any
from unittest.mock import patch

import yaml
from yaml.nodes import MappingNode

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

from tools.lib.docs_freshness import (
    evaluate_docs_freshness_observation,
    extract_docs_freshness_violation_count,
    validate_docs_freshness_baseline,
)
from tools.lib.fs import (
    active_secure_output_root,
    atomic_write_bytes,
    atomic_write_json,
    scoped_report_path,
)
from tools.lib.imports import repo_root_from
from tools.lib.runner import run_command

REPO_ROOT = repo_root_from(__file__)
WORKSPACE_ROOT = REPO_ROOT.parent
MAX_ARCHITECTURE_EXCEPTION_DAYS = 90
MAX_COMPLEXITY_EXCEPTION_DAYS = 120
FORBIDDEN_PRODUCT_ROOTS = {".github", "cloud_deploy", "deploy", "docker", "gcp", "scripts"}
FORBIDDEN_TOOL_ROOTS = {
    "benchmarks",
    "calibration",
    "cloud",
    "data",
    "diagnostics",
    "lint",
    "release",
    "runtime",
    "testing",
    "ukraine_data",
    "validation",
    "workspace",
}
SCHEMA_PURITY_SNIPPET = """
from pathlib import Path
from tools.lib.fs import scoped_report_path, write_scoped_report_text

root = Path("schemas")
output = scoped_report_path(
    "schema-purity", Path("_build/.tmp/last-mile/schemas-python-residue.txt")
)
matches = []
if root.exists():
    for path in sorted(root.rglob("*")):
        if path.name == "__pycache__" or path.suffix == ".py":
            matches.append(path.as_posix())
write_scoped_report_text(
    output, "\\n".join(matches) + ("\\n" if matches else ""), atomic=False
)
if matches:
    print("\\n".join(matches))
    raise SystemExit(1)
"""


@dataclass(frozen=True)
class LastMileGateOwnership:
    """Bind a gate to the command its declared owner actually dispatches."""

    id: str
    owner: str
    source_path: str
    argv: tuple[str, ...]
    owner_script_attribute: str | None = None


LAST_MILE_GATE_OWNERSHIP: tuple[LastMileGateOwnership, ...] = (
    LastMileGateOwnership(
        "repository-structure",
        "repository-sota-closeout",
        "tools/devx/workspace/repository_sota_closeout.py",
        (
            "uv",
            "run",
            "python",
            "tools/quality/validation/repository_structure_phase0.py",
            "gate",
            "--gate",
            "all",
            "--mode",
            "fail-closed",
            "--json",
        ),
    ),
    LastMileGateOwnership(
        "repository-last-mile-inventory",
        "workspace verify",
        "tools/devx/workspace/verify.py",
        (
            "uv",
            "run",
            "python",
            "tools/quality/validation/repository_last_mile_inventory.py",
            "--json-output",
            "_build/.tmp/last-mile/inventory.json",
            "--check",
        ),
    ),
    LastMileGateOwnership(
        "shell-package-closure",
        "workspace verify",
        "tools/devx/workspace/verify.py",
        (
            "uv",
            "run",
            "polisyos-tools",
            "validation",
            "check-package-import-gates",
            "--fail-closed",
            "--json-output",
            "_build/.tmp/last-mile/package-import-gates.json",
        ),
    ),
    LastMileGateOwnership(
        "cross-cutting-name-collision",
        "workspace verify",
        "tools/devx/workspace/verify.py",
        (
            "uv",
            "run",
            "python",
            "tools/quality/validation/repository_last_mile_inventory.py",
            "--json-output",
            "_build/.tmp/last-mile/inventory.json",
            "--check",
        ),
    ),
    LastMileGateOwnership(
        "schema-purity",
        "workspace verify",
        "tools/devx/workspace/verify.py",
        ("uv", "run", "python", "-c"),
        owner_script_attribute="SCHEMA_PURITY_SNIPPET",
    ),
    LastMileGateOwnership(
        "directory-health",
        "workspace ci-parity",
        "tools/devx/workspace/ci_parity.py",
        (
            "uv",
            "run",
            "python",
            "tools/quality/validation/directory_health.py",
            "--repo-root",
            ".",
            "--json-output",
            "_build/.tmp/last-mile/directory-health.json",
            "--markdown-output",
            "_build/.tmp/last-mile/directory-health.md",
            "--fail-on-regression",
        ),
    ),
    LastMileGateOwnership(
        "test-ratchets-helper-topology",
        "workspace ci-parity",
        "tools/devx/workspace/ci_parity.py",
        (
            "uv",
            "run",
            "python",
            "tools/quality/testing/report_test_ratchets.py",
            "--format",
            "json",
            "--output",
            "_build/.tmp/last-mile/test-ratchets.json",
            "--fail-on-regression",
        ),
    ),
    LastMileGateOwnership(
        "extension-examples",
        "workspace ci-parity",
        "tools/devx/workspace/ci_parity.py",
        ("uv", "run", "python", "tools/quality/validation/check_extension_examples.py"),
    ),
    LastMileGateOwnership(
        "adr-thematic-index",
        "workspace ci-parity",
        "tools/devx/workspace/ci_parity.py",
        (
            "uv",
            "run",
            "python",
            "tools/quality/validation/generate_adr_index.py",
            "--check",
        ),
    ),
    LastMileGateOwnership(
        "validator-module-size",
        "workspace ci-parity",
        "tools/devx/workspace/ci_parity.py",
        (
            "uv",
            "run",
            "python",
            "tools/quality/validation/architecture_report_only_contracts.py",
            "--report",
            "module-size",
            "--json-output",
            "_build/.tmp/last-mile/module-size.json",
            "--fail-on-contract-errors",
        ),
    ),
    LastMileGateOwnership(
        "dead-overrides",
        "repository-sota-closeout",
        "tools/devx/workspace/repository_sota_closeout.py",
        (
            "uv",
            "run",
            "python",
            "tools/ops_runners/reports/dead_overrides.py",
            "--json-output",
            "_build/.tmp/last-mile/dead-overrides.json",
        ),
    ),
    LastMileGateOwnership(
        "operability-release",
        "release workflow",
        "../.github/workflows/release.yml",
        (
            "uv",
            "run",
            "polisyos-tools",
            "release",
            "check-operability-release-gates",
            "--fragments-dir",
            "${{ needs.prepare-release.outputs.fragments_dir }}",
            "--fail-closed",
            "--json-output",
            "/tmp/release-operability-gates.json",  # noqa: S108 - matches the release workflow output path
        ),
    ),
    LastMileGateOwnership(
        "compatibility-release",
        "release workflow",
        "../.github/workflows/release.yml",
        (
            "uv",
            "run",
            "polisyos-tools",
            "release",
            "check-compatibility-release-gates",
            "--fragments-dir",
            "${{ needs.prepare-release.outputs.fragments_dir }}",
            "--fail-on-contract-errors",
            "--json-output",
            "/tmp/release-compatibility-gates.json",  # noqa: S108 - matches the release workflow output path
        ),
    ),
    LastMileGateOwnership(
        "acceptance-audit",
        "workspace acceptance-audit",
        "tools/devx/workspace/repository_sota_closeout.py",
        (
            "uv",
            "run",
            "polisyos-tools",
            "workspace",
            "acceptance-audit",
            "--json-output",
            "_build/.tmp/last-mile/platform-acceptance.json",
            "--summary",
            "_build/.tmp/last-mile/platform-acceptance.md",
        ),
    ),
)


@dataclass(frozen=True)
class Finding:
    gate: str
    message: str
    detail: str = ""

    def render(self) -> str:
        suffix = f" :: {self.detail}" if self.detail else ""
        return f"[{self.gate}] {self.message}{suffix}"


@dataclass(frozen=True)
class RequiredGateContract:
    """Pin one established gate's command and executable coverage routes."""

    command: str
    coverage: tuple[str, ...]
    skip_command: str | None = None


# This independent baseline prevents deleting a TOML row from shrinking the
# closeout denominator. Additional well-formed rows remain generically routed.
_REQUIRED_GATE_CONTRACTS: dict[str, RequiredGateContract] = {
    "topology-loose-files": RequiredGateContract(
        "uv run pytest tests/repo_quality/architecture/test_repository_sota_phase3_topology_cleanup.py -q",
        ("subprocess",),
    ),
    "import-linter": RequiredGateContract(
        "uv run python tools/quality/lint/lint_imports.py --policy architecture/imports/policy.toml --exceptions architecture/imports/exceptions.toml",
        ("subprocess",),
    ),
    "public-surface": RequiredGateContract(
        "uv run polisyos-tools architecture guardrails check",
        ("subprocess",),
    ),
    "generated-drift": RequiredGateContract(
        "uv run polisyos-tools architecture guardrails check --all-generated-checks",
        ("subprocess",),
        "uv run polisyos-tools architecture guardrails check --skip-generated-checks",
    ),
    "docs-freshness": RequiredGateContract(
        "uv run polisyos-tools validation check-docs-accuracy --repo-root .",
        ("preflight:docs-freshness-contract", "conditional:docs-freshness-runtime"),
    ),
    "public-polish": RequiredGateContract(
        "uv run pytest tests/repo_quality/architecture/test_repository_public_polish.py -q",
        ("subprocess",),
    ),
    "shim-audit": RequiredGateContract(
        "uv run polisyos-tools workspace repository-sota-closeout --contract-only",
        ("preflight:migration-shim-contract",),
    ),
    "complexity-exceptions": RequiredGateContract(
        "uv run polisyos-tools workspace repository-sota-closeout --contract-only",
        ("preflight:complexity-exception-contract",),
    ),
    "security-baselines": RequiredGateContract(
        "uv run polisyos-tools workspace repository-sota-closeout --contract-only",
        ("preflight:ops-modes",),
    ),
    "dependency-baselines": RequiredGateContract(
        "uv run polisyos-tools workspace repository-sota-closeout --contract-only",
        ("preflight:ops-modes",),
    ),
    "sbom-baseline": RequiredGateContract(
        "uv run polisyos-tools workspace repository-sota-closeout --contract-only",
        ("preflight:ops-modes",),
    ),
    "commit-policy": RequiredGateContract(
        "uv run polisyos-tools workspace repository-sota-closeout --contract-only",
        ("preflight:ops-modes",),
    ),
    "command-registry": RequiredGateContract(
        "uv run polisyos-tools docs --output docs/reference/tools.md --check",
        ("subprocess",),
    ),
}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the fail-closed Repository SOTA Phase 5 closeout gate."
    )
    parser.add_argument(
        "--contract-only",
        action="store_true",
        help="Validate machine-readable contracts without running subprocess drift checks.",
    )
    parser.add_argument(
        "--skip-generated-checks",
        action="store_true",
        help="Run architecture guardrails without the slower generated-artifact drift commands.",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        help="Optional JSON report path.",
    )
    parser.add_argument(
        "--subprocess-receipt-dir",
        type=Path,
        help=(
            "Optional directory for complete stdout/stderr and command receipts from each "
            "subprocess gate."
        ),
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    findings: list[Finding] = []
    preflight_findings: list[Finding] = []

    for _check_id, check in _preflight_checks():
        preflight_findings.extend(check())
    findings.extend(preflight_findings)

    registry_valid = not any(finding.gate == "gate-registry" for finding in preflight_findings)
    if not args.contract_only and registry_valid:
        findings.extend(_run_fail_closed_subprocess_gates(args))

    payload = {
        "status": "failed" if findings else "passed",
        "finding_count": len(findings),
        "findings": [
            {
                "gate": finding.gate,
                "message": finding.message,
                "detail": finding.detail,
            }
            for finding in findings
        ],
    }
    if args.output_json is not None:
        output_json = scoped_report_path("repository-sota-closeout", args.output_json)
        atomic_write_json(output_json, payload)

    if findings:
        print("Repository SOTA Phase 5 closeout gate FAILED:")
        for finding in findings:
            print(f"- {finding.render()}")
        return 1

    print("Repository SOTA Phase 5 closeout gate passed.")
    return 0


def _read_toml(relative_path: str) -> dict[str, Any]:
    return tomllib.loads((REPO_ROOT / relative_path).read_text(encoding="utf-8"))


def _resolve(relative_path: str) -> Path:
    return (REPO_ROOT / relative_path).resolve()


def _parse_date(
    value: object, *, gate: str, subject: str, field: str
) -> tuple[dt.date | None, Finding | None]:
    raw = str(value or "").strip()
    if not raw:
        return None, Finding(gate, f"{subject} missing `{field}`")
    try:
        return dt.date.fromisoformat(raw), None
    except ValueError:
        return None, Finding(gate, f"{subject} has invalid `{field}`", raw)


def _has_issue_or_adr(item: dict[str, Any]) -> bool:
    return any(str(item.get(field, "")).strip() for field in ("issue", "adr", "adr_reference"))


def _has_renewal_owner_and_adr(item: dict[str, Any]) -> bool:
    owner = str(item.get("renewal_owner", "")).strip()
    adr = str(item.get("adr") or item.get("adr_reference") or "").strip()
    return bool(owner and adr)


def _require_issue_or_adr(
    findings: list[Finding], gate: str, subject: str, item: dict[str, Any]
) -> None:
    if not _has_issue_or_adr(item):
        findings.append(Finding(gate, f"{subject} missing issue/ADR reference"))


def _check_required_fields(
    findings: list[Finding],
    *,
    gate: str,
    subject: str,
    item: dict[str, Any],
    fields: Sequence[str],
) -> None:
    for field in fields:
        if item.get(field) in (None, "", [], {}):
            findings.append(Finding(gate, f"{subject} missing `{field}`"))


def _check_future_date_field(
    findings: list[Finding],
    *,
    gate: str,
    subject: str,
    item: dict[str, Any],
    field: str,
) -> None:
    date_value, error = _parse_date(item.get(field), gate=gate, subject=subject, field=field)
    if error is not None:
        findings.append(error)
    elif date_value is not None and date_value < dt.date.today():
        findings.append(Finding(gate, f"{subject} expired", date_value.isoformat()))


def _gate_registry_rows(data: dict[str, Any] | None = None) -> list[object]:
    registry = data if data is not None else _read_toml("architecture/gates/repository_sota.toml")
    if not isinstance(registry, dict):
        return []
    rows = registry.get("gate")
    return rows if isinstance(rows, list) else []


def _parse_gate_command(value: object) -> list[str] | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        command = shlex.split(value)
    except ValueError:
        return None
    return command or None


def _check_gate_registry() -> list[Finding]:
    findings: list[Finding] = []
    loaded = _read_toml("architecture/gates/repository_sota.toml")
    if not isinstance(loaded, dict):
        findings.append(Finding("gate-registry", "registry document must be a table"))
        loaded = {}
    data = loaded
    header = data.get("repository_sota_gates", {})
    if not isinstance(header, dict):
        header = {}
    if header.get("status") != "fail_closed":
        findings.append(
            Finding(
                "gate-registry",
                "repository_sota_gates.status must be fail_closed",
                str(header.get("status")),
            )
        )
    closeout_report = header.get("closeout_report")
    if not isinstance(closeout_report, str) or not closeout_report.strip():
        findings.append(Finding("gate-registry", "closeout report is missing"))
    elif not _resolve(closeout_report).exists():
        findings.append(Finding("gate-registry", "closeout report is missing", closeout_report))

    raw_rows = data.get("gate")
    if not isinstance(raw_rows, list):
        findings.append(Finding("gate-registry", "gate registry `gate` field must be a list"))
        rows: list[object] = []
    else:
        rows = _gate_registry_rows(data)
        if not rows:
            findings.append(Finding("gate-registry", "no gate rows are registered"))
    known_preflights = {check_id for check_id, _check in _preflight_checks()}
    known_conditionals = set(_conditional_gate_handlers())
    seen_ids: dict[str, int] = {}
    conditional_owners: dict[str, str] = {}
    for index, item in enumerate(rows, start=1):
        if not isinstance(item, dict):
            findings.append(Finding("gate-registry", "gate row must be a table", f"gate[{index}]"))
            continue
        gate_id = item.get("id")
        if not isinstance(gate_id, str) or not gate_id.strip():
            gate_id = f"gate[{index}]"
            findings.append(Finding("gate-registry", "gate row missing string `id`", gate_id))
        else:
            original_gate_id = gate_id
            gate_id = gate_id.strip()
            if original_gate_id != gate_id:
                findings.append(
                    Finding(
                        "gate-registry",
                        "gate id has surrounding whitespace",
                        repr(original_gate_id),
                    )
                )
            if gate_id in seen_ids:
                findings.append(
                    Finding(
                        "gate-registry",
                        "duplicate gate id",
                        f"{gate_id}: rows {seen_ids[gate_id]} and {index}",
                    )
                )
            else:
                seen_ids[gate_id] = index

        if item.get("mode") != "fail_closed":
            findings.append(Finding("gate-registry", f"{gate_id} is not fail_closed"))
        for field in ("owner", "command", "evidence"):
            value = item.get(field)
            if not isinstance(value, str) or not value.strip():
                findings.append(Finding("gate-registry", f"{gate_id} missing string `{field}`"))
        required = _REQUIRED_GATE_CONTRACTS.get(gate_id)
        if required is not None:
            if item.get("command") != required.command:
                findings.append(
                    Finding(
                        "gate-registry",
                        f"{gate_id} required command mismatch",
                        str(item.get("command")),
                    )
                )
            if item.get("coverage") != list(required.coverage):
                findings.append(
                    Finding(
                        "gate-registry",
                        f"{gate_id} required coverage routes mismatch",
                        repr(item.get("coverage")),
                    )
                )
            if item.get("skip_command") != required.skip_command:
                findings.append(
                    Finding(
                        "gate-registry",
                        f"{gate_id} required skip command mismatch",
                        str(item.get("skip_command")),
                    )
                )
        if _parse_gate_command(item.get("command")) is None:
            findings.append(
                Finding("gate-registry", f"{gate_id} command is not a valid argument string")
            )
        if gate_id != "generated-drift" and "skip_command" in item:
            findings.append(
                Finding(
                    "gate-registry",
                    f"{gate_id} skip_command is only permitted for generated-drift",
                )
            )
        if "skip_command" in item and _parse_gate_command(item.get("skip_command")) is None:
            findings.append(
                Finding("gate-registry", f"{gate_id} skip_command is not a valid argument string")
            )

        evidence = item.get("evidence")
        if isinstance(evidence, str) and evidence.strip() and not _resolve(evidence).exists():
            findings.append(Finding("gate-registry", f"{gate_id} evidence path missing", evidence))
        exceptions = item.get("exceptions")
        if exceptions is not None:
            if not isinstance(exceptions, str) or not exceptions.strip():
                findings.append(Finding("gate-registry", f"{gate_id} exceptions must be a path"))
            elif not _resolve(exceptions).exists():
                findings.append(
                    Finding("gate-registry", f"{gate_id} exception path missing", exceptions)
                )

        coverage = item.get("coverage")
        if not isinstance(coverage, list) or not coverage:
            findings.append(Finding("gate-registry", f"{gate_id} must declare coverage routes"))
            continue
        seen_routes: set[str] = set()
        for route in coverage:
            if not isinstance(route, str) or not route.strip():
                findings.append(Finding("gate-registry", f"{gate_id} has malformed coverage route"))
                continue
            if route in seen_routes:
                findings.append(
                    Finding("gate-registry", f"{gate_id} duplicates coverage route", route)
                )
                continue
            seen_routes.add(route)
            if route == "subprocess":
                continue
            kind, separator, target = route.partition(":")
            if not separator or not target:
                findings.append(
                    Finding("gate-registry", f"{gate_id} has unknown coverage route", route)
                )
            elif kind == "preflight":
                if target == "gate-registry" or target not in known_preflights:
                    findings.append(
                        Finding(
                            "gate-registry", f"{gate_id} preflight route is not executable", target
                        )
                    )
            elif kind == "conditional":
                if target not in known_conditionals:
                    findings.append(
                        Finding(
                            "gate-registry", f"{gate_id} conditional route has no handler", target
                        )
                    )
                elif target in conditional_owners and conditional_owners[target] != gate_id:
                    findings.append(
                        Finding(
                            "gate-registry",
                            "conditional route is owned by multiple gate rows",
                            f"{target}: {conditional_owners[target]}, {gate_id}",
                        )
                    )
                else:
                    conditional_owners[target] = gate_id
            else:
                findings.append(
                    Finding("gate-registry", f"{gate_id} has unknown coverage route", route)
                )

    for gate_id in _REQUIRED_GATE_CONTRACTS:
        if gate_id not in seen_ids:
            findings.append(Finding("gate-registry", "missing required gate", gate_id))

    return findings


def _check_final_topology_contract() -> list[Finding]:
    findings: list[Finding] = []
    topology = _read_toml("architecture/topology.toml")
    if topology.get("topology", {}).get("status") != "final":
        findings.append(
            Finding(
                "topology",
                "architecture/topology.toml must be final after Repository SOTA closeout",
                str(topology.get("topology", {}).get("status")),
            )
        )
    product_paths = {
        str(item.get("path", ""))
        for item in topology.get("path", [])
        if item.get("scope") == "product_root"
    }
    for path_name in sorted(FORBIDDEN_PRODUCT_ROOTS):
        if path_name in product_paths or _resolve(path_name).exists():
            findings.append(Finding("topology", "retired product-root surface remains", path_name))
    for path_name in sorted(FORBIDDEN_TOOL_ROOTS):
        if _resolve(f"tools/{path_name}").exists():
            findings.append(
                Finding("topology", "retired tools namespace remains", f"tools/{path_name}")
            )
    return findings


def _check_ops_modes() -> list[Finding]:
    findings: list[Finding] = []
    ops = _read_toml("architecture/baselines/ops.toml")
    for baseline in ops.get("baseline", []):
        baseline_id = str(baseline.get("id", "unknown"))
        if baseline.get("mode") != "fail_closed":
            findings.append(Finding("ops-baselines", f"{baseline_id} is not fail_closed"))
        for path in baseline.get("paths", []):
            if not _path_pattern_exists(str(path)):
                findings.append(Finding("ops-baselines", f"{baseline_id} path missing", str(path)))

    mode_files = {
        "ops/security/secrets-baseline.toml": "secrets_baseline",
        "ops/release/commit-policy.toml": "commit_policy",
        "ops/release/release-fragment-policy.toml": "release_fragments",
        "ops/runtime/runtime-contracts.toml": "runtime_contracts",
        "ops/migrations/migration-contracts.toml": "migration_contracts",
    }
    for relative_path, table in mode_files.items():
        payload = _read_toml(relative_path)
        if payload[table].get("mode") != "fail_closed":
            findings.append(Finding("ops-baselines", f"{relative_path} is not fail_closed"))
    findings.extend(_check_security_dependency_sbom_contracts())
    otel = _resolve("ops/observability/otel/baseline.yaml").read_text(encoding="utf-8")
    if "mode: fail_closed" not in otel:
        findings.append(
            Finding("ops-baselines", "ops/observability/otel/baseline.yaml is not fail_closed")
        )
    security_readme = _resolve("ops/security/README.md").read_text(encoding="utf-8")
    if "report-only" in security_readme:
        findings.append(
            Finding("ops-baselines", "ops/security/README.md still describes report-only gates")
        )
    commit_policy = _read_toml("ops/release/commit-policy.toml")["commit_policy"]
    if "report-only" in str(commit_policy.get("evidence_policy", "")):
        findings.append(
            Finding("ops-baselines", "commit policy still points at report-only evidence")
        )
    return findings


def _check_security_dependency_sbom_contracts() -> list[Finding]:
    findings: list[Finding] = []
    secrets = _read_toml("ops/security/secrets-baseline.toml")["secrets_baseline"]
    for path in secrets.get("config_paths", []):
        if not _resolve(str(path)).exists():
            findings.append(
                Finding("security-baselines", "secrets scanner config missing", str(path))
            )
    if not secrets.get("baseline_commands"):
        findings.append(Finding("security-baselines", "secrets baseline has no commands"))

    osv = _read_toml("ops/security/osv-scanner.toml")["osv"]
    for lockfile in osv.get("lockfiles", []):
        path = str(lockfile.get("path", "")).strip()
        if path and not lockfile.get("optional", False) and not _resolve(path).exists():
            findings.append(Finding("dependency-baselines", "required lockfile missing", path))

    sbom = _read_toml("ops/security/sbom.toml")["sbom"]
    for path in sbom.get("inputs", []):
        if not _resolve(str(path)).exists():
            findings.append(Finding("sbom-baseline", "SBOM input missing", str(path)))
    if not str(sbom.get("output_dir", "")).strip():
        findings.append(Finding("sbom-baseline", "SBOM output_dir missing"))
    return findings


def _path_pattern_exists(path: str) -> bool:
    if any(char in path for char in "*?["):
        return bool(list(REPO_ROOT.glob(path)))
    resolved = _resolve(path)
    return resolved.exists()


def _check_docs_freshness_contract() -> list[Finding]:
    baseline = _read_toml("architecture/exceptions/docs_freshness.toml")[
        "docs_freshness_exceptions"
    ]
    findings, _, _ = _docs_freshness_contract_findings(baseline)
    return findings


def _docs_freshness_contract_findings(
    baseline: dict[str, Any],
) -> tuple[list[Finding], int | None, str]:
    contract = validate_docs_freshness_baseline(baseline)
    findings = [Finding("docs-freshness", message) for message in contract.findings]
    return findings, contract.expected_violation_count, contract.baseline_sha256


def _check_time_bounded_import_exceptions() -> list[Finding]:
    findings: list[Finding] = []
    today = dt.date.today()
    max_expiry = today + dt.timedelta(days=MAX_ARCHITECTURE_EXCEPTION_DAYS)
    payload = _read_toml("architecture/imports/exceptions.toml")
    seen: set[str] = set()
    for idx, exception in enumerate(payload.get("exception", []), start=1):
        exception_id = str(exception.get("id", "")).strip()
        subject = exception_id or f"exception[{idx}]"
        if not exception_id:
            findings.append(Finding("import-exceptions", f"{subject} missing id"))
        elif exception_id in seen:
            findings.append(Finding("import-exceptions", f"duplicate id {exception_id}"))
        seen.add(exception_id)
        for field in ("owner", "reason", "source_glob"):
            if not str(exception.get(field, "")).strip():
                findings.append(Finding("import-exceptions", f"{subject} missing `{field}`"))
        _require_issue_or_adr(findings, "import-exceptions", subject, exception)
        expires, error = _parse_date(
            exception.get("expires"), gate="import-exceptions", subject=subject, field="expires"
        )
        if error is not None:
            findings.append(error)
            continue
        assert expires is not None
        if expires < today:
            findings.append(Finding("import-exceptions", f"{subject} expired", expires.isoformat()))
        if expires > max_expiry:
            findings.append(
                Finding(
                    "import-exceptions",
                    f"{subject} exceeds {MAX_ARCHITECTURE_EXCEPTION_DAYS} day window",
                    expires.isoformat(),
                )
            )
    return findings


def _check_complexity_exceptions() -> list[Finding]:
    findings: list[Finding] = []
    today = dt.date.today()
    max_expiry = today + dt.timedelta(days=MAX_COMPLEXITY_EXCEPTION_DAYS)
    payload = _read_toml("architecture/exceptions/complexity.toml")
    if payload.get("complexity_exceptions", {}).get("status") != "active":
        findings.append(Finding("complexity", "complexity exceptions registry must be active"))
    for idx, exception in enumerate(payload.get("exception", []), start=1):
        path = str(exception.get("path", "")).strip()
        subject = path or f"exception[{idx}]"
        if not path:
            findings.append(Finding("complexity", f"{subject} missing path"))
        if any(marker in path for marker in ("*", "?", "[")):
            findings.append(Finding("complexity", f"{subject} uses a wildcard path"))
        elif path and not _resolve(path).exists():
            findings.append(Finding("complexity", f"{subject} path does not exist"))
        for field in ("owner", "reason", "remediation"):
            if not str(exception.get(field, "")).strip():
                findings.append(Finding("complexity", f"{subject} missing `{field}`"))
        _require_issue_or_adr(findings, "complexity", subject, exception)
        expires, error = _parse_date(
            exception.get("expires"), gate="complexity", subject=subject, field="expires"
        )
        if error is not None:
            findings.append(error)
            continue
        assert expires is not None
        if expires < today:
            findings.append(Finding("complexity", f"{subject} expired", expires.isoformat()))
        if expires > max_expiry:
            findings.append(
                Finding(
                    "complexity",
                    f"{subject} exceeds {MAX_COMPLEXITY_EXCEPTION_DAYS} day window",
                    expires.isoformat(),
                )
            )
    return findings


def _check_migration_shims() -> list[Finding]:
    findings: list[Finding] = []
    today = dt.date.today()
    payload = _read_toml("architecture/shims.toml")
    seen: set[str] = set()
    for idx, shim in enumerate(payload.get("shim", []), start=1):
        shim_id = str(shim.get("id", "")).strip()
        subject = shim_id or f"shim[{idx}]"
        if not shim_id:
            findings.append(Finding("shims", f"{subject} missing id"))
        elif shim_id in seen:
            findings.append(Finding("shims", f"duplicate id {shim_id}"))
        seen.add(shim_id)
        for field in ("source_path", "target_path", "type", "reason", "owner", "issue"):
            if not str(shim.get(field, "")).strip():
                findings.append(Finding("shims", f"{subject} missing `{field}`"))
        sunset, error = _parse_date(
            shim.get("sunset_date"), gate="shims", subject=subject, field="sunset_date"
        )
        if error is not None:
            findings.append(error)
        elif sunset is not None and sunset < today and not _has_renewal_owner_and_adr(shim):
            findings.append(Finding("shims", f"{subject} expired", sunset.isoformat()))

        target = str(shim.get("target_path", "")).strip()
        if target and not _resolve(target).exists():
            findings.append(Finding("shims", f"{subject} target path missing", target))
        source = str(shim.get("source_path", "")).strip()
        if shim.get("type") == "wrapper_only" and source and not _resolve(source).exists():
            findings.append(Finding("shims", f"{subject} wrapper source missing", source))
    return findings


def _check_phase65_exception_cleanup() -> list[Finding]:
    findings: list[Finding] = []
    findings.extend(_check_import_exception_docs_registry())
    findings.extend(_check_dynamic_import_exception_metadata())
    findings.extend(_check_structure_remediation_exception_metadata())
    findings.extend(_check_package_contract_exception_metadata())
    findings.extend(_check_test_topology_exception_metadata())
    findings.extend(_check_test_ratchet_exception_metadata())
    findings.extend(_check_static_override_exception_metadata())
    findings.extend(_check_module_size_budget_exception_metadata())
    findings.extend(_check_slo_runbook_exception_metadata())
    findings.extend(_check_directory_contract_exception_policy())
    findings.extend(_check_generated_artifact_exception_policy())
    findings.extend(_check_control_plane_exception_metadata())
    findings.extend(_check_guardrail_exception_metadata())
    findings.extend(_check_public_surface_compatibility_sunsets())
    findings.extend(_check_package_boundary_shim_refs())
    findings.extend(_check_non_expired_named_sunsets())
    return findings


def _check_import_exception_docs_registry() -> list[Finding]:
    findings: list[Finding] = []
    gate = "phase6.5-exceptions"
    exceptions = _read_toml("architecture/imports/exceptions.toml").get("exception", [])
    toml_ids = {str(item.get("id", "")).strip() for item in exceptions if item.get("id")}
    md_path = _resolve("architecture/imports/exceptions.md")
    md_text = md_path.read_text(encoding="utf-8")
    md_ids = set(re.findall(r"`(E-\d{4}-\d{2}-[A-Z0-9-]+)`", md_text))

    extra = sorted(md_ids - toml_ids)
    missing = sorted(toml_ids - md_ids)
    if extra:
        findings.append(
            Finding(
                gate,
                "import exception Markdown registry has retired ids",
                ", ".join(extra),
            )
        )
    if missing:
        findings.append(
            Finding(
                gate,
                "import exception Markdown registry is missing active ids",
                ", ".join(missing),
            )
        )
    if "issue/ADR" not in md_text and "issue or ADR" not in md_text:
        findings.append(Finding(gate, "import exception Markdown registry omits issue/ADR policy"))
    return findings


def _check_structure_remediation_exception_metadata() -> list[Finding]:
    findings: list[Finding] = []
    gate = "phase6.5-exceptions"
    payload = _read_toml("architecture/exceptions/structure_remediation.toml")
    for idx, exception in enumerate(payload.get("exception", []), start=1):
        subject = str(exception.get("id", "")).strip() or f"structure_exception[{idx}]"
        _check_required_fields(
            findings,
            gate=gate,
            subject=subject,
            item=exception,
            fields=("id", "gate", "owner", "reason", "sunset", "match"),
        )
        _require_issue_or_adr(findings, gate, subject, exception)
        _check_future_date_field(
            findings, gate=gate, subject=subject, item=exception, field="sunset"
        )
    return findings


def _check_dynamic_import_exception_metadata() -> list[Finding]:
    findings: list[Finding] = []
    gate = "phase6.5-exceptions"
    payload = _read_toml("architecture/imports/dynamic.toml")
    header = payload.get("dynamic_imports", {})
    _check_required_fields(
        findings,
        gate=gate,
        subject="dynamic_imports",
        item=header,
        fields=(
            "owner",
            "status",
            "extension_points",
            "review_owner",
            "reviewed_at",
            "review_expires",
            "exception_policy",
        ),
    )
    _require_issue_or_adr(findings, gate, "dynamic_imports", header)
    _check_future_date_field(
        findings,
        gate=gate,
        subject="dynamic_imports",
        item=header,
        field="review_expires",
    )
    reviewed_at, error = _parse_date(
        header.get("reviewed_at"),
        gate=gate,
        subject="dynamic_imports",
        field="reviewed_at",
    )
    if error is not None:
        findings.append(error)
    elif reviewed_at is not None and reviewed_at > dt.date.today():
        findings.append(Finding(gate, "dynamic_imports review date is in the future"))

    extension_points = str(header.get("extension_points", "")).strip()
    if extension_points and not _resolve(extension_points).exists():
        findings.append(Finding(gate, "dynamic_imports extension point contract missing"))

    seen: set[str] = set()
    for idx, pattern in enumerate(payload.get("pattern", []), start=1):
        subject = str(pattern.get("id", "")).strip() or f"dynamic_import[{idx}]"
        if subject in seen:
            findings.append(Finding(gate, f"duplicate dynamic import id {subject}"))
        seen.add(subject)
        _check_required_fields(
            findings,
            gate=gate,
            subject=subject,
            item=pattern,
            fields=("id", "pattern", "source_file", "line", "call", "owner", "verifier", "notes"),
        )
        if not pattern.get("target") and not pattern.get("allowed_targets"):
            findings.append(Finding(gate, f"{subject} missing target or allowed_targets"))
        source_file = str(pattern.get("source_file", "")).strip()
        if source_file and not _resolve(source_file).exists():
            findings.append(Finding(gate, f"{subject} source_file missing", source_file))
        if any(word in str(pattern.get("notes", "")).lower() for word in ("temporary", "shim")):
            _require_issue_or_adr(findings, gate, subject, pattern)
            _check_future_date_field(
                findings, gate=gate, subject=subject, item=pattern, field="sunset"
            )
    return findings


def _check_package_contract_exception_metadata() -> list[Finding]:
    findings: list[Finding] = []
    gate = "phase6.5-exceptions"
    for path in sorted(_resolve("architecture/packages").glob("*.toml")):
        if path.stem in {"boundaries", "layout"}:
            continue
        payload = _read_toml(str(path.relative_to(REPO_ROOT)))
        package_header = payload.get("package", {})
        package_name = (
            str(package_header.get("name", path.stem))
            if isinstance(package_header, dict)
            else path.stem
        )
        for idx, exception in enumerate(payload.get("exception", []), start=1):
            subject = str(exception.get("id", "")).strip() or f"{package_name}.exception[{idx}]"
            _check_required_fields(
                findings,
                gate=gate,
                subject=subject,
                item=exception,
                fields=("id", "owner", "kind", "reason", "sunset", "registry"),
            )
            _require_issue_or_adr(findings, gate, subject, exception)
            _check_future_date_field(
                findings, gate=gate, subject=subject, item=exception, field="sunset"
            )
            registry = str(exception.get("registry", "")).strip()
            if registry and not _resolve(registry).exists():
                findings.append(Finding(gate, f"{subject} registry path missing", registry))
        for idx, sunset in enumerate(payload.get("sunset", []), start=1):
            subject = str(sunset.get("id", "")).strip() or f"{package_name}.sunset[{idx}]"
            _check_required_fields(
                findings,
                gate=gate,
                subject=subject,
                item=sunset,
                fields=("id", "owner", "date", "condition"),
            )
            _require_issue_or_adr(findings, gate, subject, sunset)
            _check_future_date_field(
                findings, gate=gate, subject=subject, item=sunset, field="date"
            )
    return findings


def _check_test_ratchet_exception_metadata() -> list[Finding]:
    findings: list[Finding] = []
    gate = "phase6.5-exceptions"
    payload = _read_toml("architecture/tests/ratchets.toml")
    for idx, exception in enumerate(payload.get("pytest_universe_exception", []), start=1):
        subject = str(exception.get("id", "")).strip() or f"pytest_universe_exception[{idx}]"
        _check_required_fields(
            findings,
            gate=gate,
            subject=subject,
            item=exception,
            fields=("id", "owner", "reason", "expires"),
        )
        _require_issue_or_adr(findings, gate, subject, exception)
        _check_future_date_field(
            findings, gate=gate, subject=subject, item=exception, field="expires"
        )

    for idx, exception in enumerate(payload.get("package_exception", []), start=1):
        subject = str(exception.get("id", "")).strip() or f"package_exception[{idx}]"
        _check_required_fields(
            findings,
            gate=gate,
            subject=subject,
            item=exception,
            fields=("id", "owner", "reason", "sunset_date"),
        )
        _require_issue_or_adr(findings, gate, subject, exception)
        _check_future_date_field(
            findings, gate=gate, subject=subject, item=exception, field="sunset_date"
        )

    for idx, ratchet in enumerate(payload.get("package_ratchet", []), start=1):
        subject = str(ratchet.get("name", "")).strip() or f"package_ratchet[{idx}]"
        if ratchet.get("package_mode") == "explicit_exception":
            _check_required_fields(
                findings,
                gate=gate,
                subject=subject,
                item=ratchet,
                fields=("exception_reason", "exception_expires", "exception_issue"),
            )
            _check_future_date_field(
                findings, gate=gate, subject=subject, item=ratchet, field="exception_expires"
            )
        for prefix in ("mirror_regression_exception", "strict_mirror_regression_exception"):
            if ratchet.get(prefix):
                _check_required_fields(
                    findings,
                    gate=gate,
                    subject=f"{subject}.{prefix}",
                    item=ratchet,
                    fields=(
                        f"{prefix}_owner",
                        f"{prefix}_reason",
                        f"{prefix}_expires",
                        f"{prefix}_issue",
                    ),
                )
                _check_future_date_field(
                    findings,
                    gate=gate,
                    subject=f"{subject}.{prefix}",
                    item=ratchet,
                    field=f"{prefix}_expires",
                )
    return findings


def _check_test_topology_exception_metadata() -> list[Finding]:
    findings: list[Finding] = []
    gate = "phase6.5-exceptions"
    payload = _read_toml("architecture/tests/topology.toml")
    for idx, exception in enumerate(payload.get("source_package_exception", []), start=1):
        subject = str(exception.get("name", "")).strip() or f"source_package_exception[{idx}]"
        _check_required_fields(
            findings,
            gate=gate,
            subject=subject,
            item=exception,
            fields=("name", "source_path", "classification", "owner", "reason", "sunset"),
        )
        _require_issue_or_adr(findings, gate, subject, exception)
        _check_future_date_field(
            findings, gate=gate, subject=subject, item=exception, field="sunset"
        )
        source_path = str(exception.get("source_path", "")).strip()
        if source_path and not _resolve(source_path).exists():
            findings.append(Finding(gate, f"{subject} source_path missing", source_path))
    return findings


def _check_static_override_exception_metadata() -> list[Finding]:
    findings: list[Finding] = []
    gate = "phase6.5-exceptions"
    payload = _read_toml("architecture/tooling/static_analysis_overrides.toml")
    for idx, override in enumerate(payload.get("override_scope", []), start=1):
        subject = str(override.get("id", "")).strip() or f"override_scope[{idx}]"
        _check_required_fields(
            findings,
            gate=gate,
            subject=subject,
            item=override,
            fields=("id", "owner", "expectation", "sunset"),
        )
        _require_issue_or_adr(findings, gate, subject, override)
        _check_future_date_field(
            findings, gate=gate, subject=subject, item=override, field="sunset"
        )
    return findings


def _check_module_size_budget_exception_metadata() -> list[Finding]:
    findings: list[Finding] = []
    gate = "phase6.5-exceptions"
    payload = _read_toml("architecture/module_size_budget.toml")
    for idx, budget in enumerate(payload.get("budget", []), start=1):
        subject = str(budget.get("path", "")).strip() or f"module_size_budget[{idx}]"
        _check_required_fields(
            findings,
            gate=gate,
            subject=subject,
            item=budget,
            fields=("path", "owner", "strategy", "shrink_plan", "sunset"),
        )
        _require_issue_or_adr(findings, gate, subject, budget)
        _check_future_date_field(findings, gate=gate, subject=subject, item=budget, field="sunset")
    return findings


def _check_slo_runbook_exception_metadata() -> list[Finding]:
    findings: list[Finding] = []
    gate = "phase6.5-exceptions"
    for relative_path, table_name in (
        ("architecture/component_observability.toml", "component_contract"),
        ("ops/components/index.toml", "component"),
    ):
        payload = _read_toml(relative_path)
        for idx, component in enumerate(payload.get(table_name, []), start=1):
            if component.get("slo_status") != "exception":
                continue
            subject = str(
                component.get("component") or component.get("id") or f"{table_name}[{idx}]"
            )
            _check_required_fields(
                findings,
                gate=gate,
                subject=subject,
                item=component,
                fields=("owner", "exception_reason", "exception_expires", "exception_issue"),
            )
            _check_future_date_field(
                findings,
                gate=gate,
                subject=subject,
                item=component,
                field="exception_expires",
            )

    runbook = _read_toml("architecture/runbook_coverage.toml")
    for idx, component in enumerate(runbook.get("component_contract", []), start=1):
        if not component.get("slo_exception"):
            continue
        subject = str(component.get("component") or f"runbook_component[{idx}]")
        _check_required_fields(
            findings,
            gate=gate,
            subject=subject,
            item=component,
            fields=(
                "owner",
                "slo_exception_reason",
                "slo_exception_expires",
                "slo_exception_issue",
            ),
        )
        _check_future_date_field(
            findings,
            gate=gate,
            subject=subject,
            item=component,
            field="slo_exception_expires",
        )
        exception_path = str(component.get("slo_exception", "")).strip()
        if exception_path and not _resolve(exception_path).exists():
            findings.append(Finding(gate, f"{subject} SLO exception path missing", exception_path))
    return findings


def _check_directory_contract_exception_policy() -> list[Finding]:
    findings: list[Finding] = []
    gate = "phase6.5-exceptions"
    payload = _read_toml("architecture/policies/directory_contracts.toml")
    header = payload.get("directory_contracts", {})
    local_docs = payload.get("local_documentation_requirement", {})
    if not str(header.get("exception_policy_issue", "")).strip():
        findings.append(Finding(gate, "directory contracts missing exception policy issue"))
    required_fields = set(local_docs.get("accepted_exception_fields", []))
    expected = {"owner", "reason", "sunset", "promotion_or_cleanup_target", "issue_or_adr"}
    missing = sorted(expected - required_fields)
    if missing:
        findings.append(
            Finding(
                gate,
                "directory contracts accepted exception fields are incomplete",
                ", ".join(missing),
            )
        )
    if local_docs.get("require_owner") is not True:
        findings.append(Finding(gate, "directory contracts do not require exception owner"))
    if local_docs.get("require_sunset_for_exceptions") is not True:
        findings.append(Finding(gate, "directory contracts do not require exception sunset"))
    return findings


def _check_generated_artifact_exception_policy() -> list[Finding]:
    findings: list[Finding] = []
    gate = "phase6.5-exceptions"
    payload = _read_toml("architecture/generated_artifacts.toml")
    header = payload.get("generated_artifacts", {})
    if not str(header.get("exception_policy", "")).strip():
        findings.append(Finding(gate, "generated artifact contract missing exception policy"))
    if not str(header.get("exception_policy_issue", "")).strip():
        findings.append(Finding(gate, "generated artifact contract missing exception policy issue"))

    for idx, family in enumerate(payload.get("family", []), start=1):
        subject = str(family.get("id", "")).strip() or f"generated_artifact_family[{idx}]"
        _check_required_fields(
            findings,
            gate=gate,
            subject=subject,
            item=family,
            fields=(
                "id",
                "owner",
                "approval_owner",
                "source_of_truth",
                "freshness_rule",
                "regenerate_commands",
                "stale_output_behavior",
                "promotion_target",
            ),
        )
        if any(field in family for field in ("exception_reason", "exception_expires", "sunset")):
            _require_issue_or_adr(findings, gate, subject, family)
            date_field = "exception_expires" if "exception_expires" in family else "sunset"
            _check_future_date_field(
                findings, gate=gate, subject=subject, item=family, field=date_field
            )
    return findings


def _check_control_plane_exception_metadata() -> list[Finding]:
    findings: list[Finding] = []
    gate = "phase6.5-exceptions"
    payload = _read_toml("architecture/control_plane_supply_chain.toml")
    codeowners_gate = payload.get("codeowners_gate", {})
    if codeowners_gate.get("personal_repo_exception"):
        _check_required_fields(
            findings,
            gate=gate,
            subject="codeowners_gate.personal_repo_exception",
            item=codeowners_gate,
            fields=(
                "personal_repo_exception_reason",
                "personal_repo_exception_expires",
                "personal_repo_exception_issue",
            ),
        )
        _check_future_date_field(
            findings,
            gate=gate,
            subject="codeowners_gate.personal_repo_exception",
            item=codeowners_gate,
            field="personal_repo_exception_expires",
        )

    for idx, mapping in enumerate(payload.get("owner_mapping", []), start=1):
        if not mapping.get("personal_repo_exception"):
            continue
        subject = str(mapping.get("owner", "")).strip() or f"owner_mapping[{idx}]"
        _check_required_fields(
            findings,
            gate=gate,
            subject=f"{subject}.personal_repo_exception",
            item=mapping,
            fields=(
                "owner",
                "personal_repo_exception_reason",
                "personal_repo_exception_expires",
                "personal_repo_exception_issue",
            ),
        )
        _check_future_date_field(
            findings,
            gate=gate,
            subject=f"{subject}.personal_repo_exception",
            item=mapping,
            field="personal_repo_exception_expires",
        )
    return findings


def _check_guardrail_exception_metadata() -> list[Finding]:
    findings: list[Finding] = []
    gate = "phase6.5-exceptions"
    payload = _read_toml("architecture/exceptions/guardrails.toml")
    for idx, exception in enumerate(payload.get("exception", []), start=1):
        subject = str(exception.get("id", "")).strip() or f"guardrail_exception[{idx}]"
        _check_required_fields(
            findings,
            gate=gate,
            subject=subject,
            item=exception,
            fields=("id", "check", "owner", "reason", "expires"),
        )
        _require_issue_or_adr(findings, gate, subject, exception)
        _check_future_date_field(
            findings, gate=gate, subject=subject, item=exception, field="expires"
        )
    return findings


def _check_public_surface_compatibility_sunsets() -> list[Finding]:
    findings: list[Finding] = []
    gate = "phase6.5-exceptions"
    payload = _read_toml("architecture/public_surface/contract.toml")
    for package in payload.get("package", []):
        if package.get("classification") != "compatibility":
            continue
        subject = str(package.get("module", "compatibility-package"))
        _check_required_fields(
            findings,
            gate=gate,
            subject=subject,
            item=package,
            fields=("owner", "notes", "supported_entrypoints"),
        )
        note_dates = re.findall(r"\b20\d{2}-\d{2}-\d{2}\b", str(package.get("notes", "")))
        if not note_dates:
            findings.append(Finding(gate, f"{subject} compatibility row missing sunset date"))
            continue
        sunset = max(dt.date.fromisoformat(raw) for raw in note_dates)
        if sunset < dt.date.today():
            findings.append(
                Finding(gate, f"{subject} compatibility row expired", sunset.isoformat())
            )
    return findings


def _check_package_boundary_shim_refs() -> list[Finding]:
    findings: list[Finding] = []
    gate = "phase6.5-exceptions"
    shims = {
        str(shim.get("id", "")).strip()
        for shim in _read_toml("architecture/shims.toml").get("shim", [])
        if shim.get("id")
    }
    for package in _read_toml("architecture/packages/boundaries.toml").get("package", []):
        if not package.get("compatibility_shim"):
            continue
        subject = str(package.get("module", "compatibility-shim"))
        shim_id = str(package.get("shim_id", "")).strip()
        if not shim_id:
            findings.append(Finding(gate, f"{subject} missing shim_id"))
        elif shim_id not in shims:
            findings.append(Finding(gate, f"{subject} references unknown shim", shim_id))
    return findings


def _check_non_expired_named_sunsets() -> list[Finding]:
    findings: list[Finding] = []
    gate = "phase6.5-exceptions"
    for relative_path, section_name, subject_field in (
        ("architecture/name_registry.toml", "shared_name", "name"),
        ("architecture/name_registry.toml", "rename_backlog", "name"),
        ("architecture/policies/cross_cutting_concerns.toml", "concern", "name"),
    ):
        payload = _read_toml(relative_path)
        for idx, item in enumerate(payload.get(section_name, []), start=1):
            subject = str(item.get(subject_field, "")).strip() or f"{section_name}[{idx}]"
            _check_non_expired_sunset_value(findings, gate, subject, item.get("sunset"))
            for nested_section in ("allowed_adapters", "unresolved_collisions"):
                for nested_idx, nested in enumerate(item.get(nested_section, []), start=1):
                    nested_subject = f"{subject}.{nested_section}[{nested_idx}]"
                    _check_non_expired_sunset_value(
                        findings, gate, nested_subject, nested.get("sunset")
                    )
    return findings


def _check_non_expired_sunset_value(
    findings: list[Finding], gate: str, subject: str, value: object
) -> None:
    raw = str(value or "").strip()
    if not raw or raw == "none":
        return
    try:
        sunset = dt.date.fromisoformat(raw)
    except ValueError:
        findings.append(Finding(gate, f"{subject} has invalid sunset", raw))
        return
    if sunset < dt.date.today():
        findings.append(Finding(gate, f"{subject} sunset expired", raw))


@dataclass(frozen=True)
class _ShellCommand:
    """One supported simple command in a restricted shell program."""

    argv: tuple[str, ...]
    nested: _ShellProgram | None = None
    may_succeed: bool = True
    terminates: bool = False
    enables_errexit: bool = False


@dataclass(frozen=True)
class _ShellProgram:
    """Simple commands grouped by &&; semicolons separate independent lists."""

    groups: tuple[tuple[_ShellCommand, ...], ...]


_SHELL_UNSUPPORTED_CONTROL_TOKENS = frozenset({"||", "|", "&", "<", ">", "(", ")", "{", "}"})
_SHELL_UNSUPPORTED_KEYWORDS = frozenset(
    {
        "!",
        "[",
        "[[",
        "case",
        "do",
        "done",
        "elif",
        "else",
        "esac",
        "fi",
        "for",
        "function",
        "if",
        "then",
        "until",
        "while",
    }
)
_SHELL_STATE_MUTATING_BUILTINS = frozenset(
    {
        ".",
        "alias",
        "builtin",
        "command",
        "declare",
        "eval",
        "export",
        "hash",
        "local",
        "readonly",
        "set",
        "source",
        "test",
        "trap",
        "typeset",
        "unalias",
        "unset",
    }
)


def _parse_shell_command(parts: list[str]) -> _ShellCommand | None:
    if not parts or re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", parts[0]):
        return None
    executable = Path(parts[0]).name
    if executable == "set":
        if parts[1:] in (["-e"], ["-eo", "pipefail"], ["-euo", "pipefail"]):
            return _ShellCommand(tuple(parts), enables_errexit=True)
        return None
    if executable in _SHELL_UNSUPPORTED_KEYWORDS or executable in _SHELL_STATE_MUTATING_BUILTINS:
        return None
    if executable in {"bash", "sh"}:
        if len(parts) != 3 or parts[1] not in {"-c", "-lc", "-cl"}:
            return None
        nested = _parse_shell_program(parts[2])
        if nested is None:
            return None
        return _ShellCommand(tuple(parts), nested, _shell_program_may_succeed(nested))
    if executable == "false":
        return _ShellCommand(tuple(parts), may_succeed=False)
    if executable in {"true", ":"}:
        return _ShellCommand(tuple(parts))
    if executable == "exit":
        status = parts[1] if len(parts) > 1 else None
        may_succeed = status is None or (status.isdecimal() and int(status) % 256 == 0)
        return _ShellCommand(tuple(parts), may_succeed=may_succeed, terminates=True)
    if executable == "exec":
        return _ShellCommand(tuple(parts), terminates=True)
    if executable == "return":
        return None
    return _ShellCommand(tuple(parts))


def _parse_shell_program(script: str) -> _ShellProgram | None:
    """Parse a restricted shell grammar; unsupported syntax fails closed."""
    normalized = re.sub(r"\\\r?\n[ \t]*", " ", script)
    try:
        lexer = shlex.shlex(normalized, posix=True, punctuation_chars=";&|<>(){}\n")
        lexer.whitespace = " \t\r"
        lexer.whitespace_split = True
        lexer.commenters = "#"
        tokens = list(lexer)
    except (TypeError, ValueError):
        return None

    groups: list[tuple[_ShellCommand, ...]] = []
    current_group: list[_ShellCommand] = []
    current_command: list[str] = []
    for lexeme in tokens:
        if lexeme in {";", "\n"}:
            if current_command:
                command = _parse_shell_command(current_command)
                if command is None:
                    return None
                current_group.append(command)
                current_command = []
            elif current_group:
                return None
            if current_group:
                groups.append(tuple(current_group))
                current_group = []
            continue
        if lexeme == "&&":
            if not current_command:
                return None
            command = _parse_shell_command(current_command)
            if command is None:
                return None
            current_group.append(command)
            current_command = []
            continue
        if lexeme in _SHELL_UNSUPPORTED_CONTROL_TOKENS or "\n" in lexeme:
            return None
        current_command.append(lexeme)

    if current_command:
        command = _parse_shell_command(current_command)
        if command is None:
            return None
        current_group.append(command)
    elif current_group:
        return None
    if current_group:
        groups.append(tuple(current_group))
    return _ShellProgram(tuple(groups))


def _shell_program_may_succeed(program: _ShellProgram) -> bool:
    if not program.groups:
        return True
    for group_index, group in enumerate(program.groups):
        group_may_succeed = True
        for command in group:
            if command.terminates:
                return command.may_succeed
            if not command.may_succeed:
                group_may_succeed = False
                break
        if group_index == len(program.groups) - 1:
            return group_may_succeed
    return True


def _shell_fail_closed_commands(program: _ShellProgram) -> list[tuple[str, ...]]:
    """Return reachable invocations whose failure reaches the script's exit status."""
    commands: list[tuple[str, ...]] = []
    final_group_index = len(program.groups) - 1
    for group_index, group in enumerate(program.groups):
        reachable = True
        for command in group:
            if not reachable:
                break
            if group_index == final_group_index:
                if command.nested is not None:
                    commands.extend(_shell_fail_closed_commands(command.nested))
                else:
                    commands.append(command.argv)
            if command.terminates:
                return commands
            if not command.may_succeed:
                reachable = False
    return commands


def _shell_command_sequences(script: str) -> list[tuple[str, ...]]:
    """Return direct invocations proven reachable and failure-propagating.

    The supported subset is simple argv commands, semicolon-separated lists,
    && lists, and nested bash/sh -c wrappers. Pipelines, OR lists, background
    jobs, redirections, control-flow forms, shell-state mutation, and dynamic
    shell evaluation are rejected instead of flattened.
    """
    program = _parse_shell_program(script)
    return [] if program is None else _shell_fail_closed_commands(program)


def _workflow_condition_is_unconditional(condition: object) -> bool:
    if condition is None or condition is True:
        return True
    if not isinstance(condition, str):
        return False
    normalized = re.sub(r"\s+", "", condition).lower()
    return normalized in {"true", "${{true}}"}


def _active_workflow_run_scripts(payload: object) -> list[str]:
    if not isinstance(payload, dict):
        return []
    jobs = payload.get("jobs")
    if not isinstance(jobs, dict):
        return []
    scripts: list[str] = []
    for job in jobs.values():
        if not isinstance(job, dict) or not _workflow_condition_is_unconditional(job.get("if")):
            continue
        steps = job.get("steps")
        if not isinstance(steps, list):
            continue
        for step in steps:
            if not isinstance(step, dict) or not _workflow_condition_is_unconditional(
                step.get("if")
            ):
                continue
            script = step.get("run")
            if isinstance(script, str):
                scripts.append(script)
    return scripts


@dataclass(frozen=True, slots=True)
class _ShellInvocation:
    """A source-parsed command and the execution facts that govern its result."""

    argv: tuple[str, ...]
    working_directory: PurePosixPath | None
    status_propagates: bool


@dataclass(frozen=True, slots=True)
class _RouteObservation:
    invocation: _ShellInvocation
    context_errors: tuple[str, ...] = ()
    source_checkout_root: PurePosixPath | None = None


class _UniqueKeySafeLoader(yaml.SafeLoader):
    """PyYAML safe loader that refuses ambiguous explicit mapping keys."""

    def construct_mapping(self, node: MappingNode, deep: bool = False) -> dict[Any, Any]:
        if isinstance(node, MappingNode):
            seen: set[Any] = set()
            for key_node, _value_node in node.value:
                if key_node.tag == "tag:yaml.org,2002:merge":
                    raise yaml.constructor.ConstructorError(
                        "while constructing a mapping",
                        node.start_mark,
                        "YAML merge keys are outside the admitted route profile",
                        key_node.start_mark,
                    )
                key = self.construct_object(key_node, deep=deep)
                try:
                    duplicate = key in seen
                except TypeError as exc:
                    raise yaml.constructor.ConstructorError(
                        "while constructing a mapping",
                        node.start_mark,
                        "unhashable mapping key",
                        key_node.start_mark,
                    ) from exc
                if duplicate:
                    raise yaml.constructor.ConstructorError(
                        "while constructing a mapping",
                        node.start_mark,
                        f"duplicate mapping key {key!r}",
                        key_node.start_mark,
                    )
                seen.add(key)
        return super().construct_mapping(node, deep=deep)


def _load_unique_yaml(path: Path) -> object:
    # The custom loader inherits SafeLoader and rejects duplicate/merge keys.
    return yaml.load(
        path.read_text(encoding="utf-8"),
        Loader=_UniqueKeySafeLoader,  # noqa: S506
    )


# This finite source profile is derived from actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683
# action.yml: only the path input relocates the checkout and fetch-depth is used by the authored
# architecture template. The other declared inputs and every future/unknown key fail closed.
_ACTIONS_CHECKOUT_PROFILE_INPUTS = frozenset({"fetch-depth", "path"})


def _normalize_checkout_inputs(
    value: object,
) -> tuple[dict[str, object] | None, tuple[str, ...]]:
    """Normalize the finite checkout-input profile, rejecting every other key or value."""
    if not isinstance(value, dict):
        return None, ("source checkout inputs are not a static mapping",)

    normalized: dict[str, object] = {}
    seen: dict[str, str] = {}
    errors: list[str] = []
    for key, input_value in value.items():
        if not isinstance(key, str):
            errors.append("source checkout input key is not a string")
            continue
        canonical = key.casefold()
        previous = seen.get(canonical)
        if previous is not None:
            errors.append(
                "source checkout input keys collide after case-insensitive normalization: "
                f"{previous!r} and {key!r}"
            )
            continue
        seen[canonical] = key
        if canonical not in _ACTIONS_CHECKOUT_PROFILE_INPUTS:
            errors.append(f"source checkout input {key!r} is outside the admitted input profile")
            continue
        if canonical == "path":
            if (
                not isinstance(input_value, str)
                or not input_value
                or input_value != input_value.strip()
            ):
                errors.append("source checkout path input is not a non-empty literal string")
                continue
            normalized[canonical] = input_value
            continue

        if type(input_value) is int:
            depth = input_value
        elif isinstance(input_value, str) and re.fullmatch(r"[0-9]+", input_value):
            try:
                depth = int(input_value)
            except ValueError:
                errors.append(
                    "source checkout fetch-depth input is not a supported integer literal"
                )
                continue
        else:
            errors.append("source checkout fetch-depth input is not a non-negative integer literal")
            continue
        if depth < 0:
            errors.append("source checkout fetch-depth input is not a non-negative integer literal")
            continue
        normalized[canonical] = depth

    if errors:
        return None, tuple(errors)
    return normalized, ()


def _normalize_checkout_path(base: PurePosixPath | None, value: object) -> PurePosixPath | None:
    """Normalize a literal relative checkout path without leaving its root."""
    if base is None or not isinstance(value, str) or not value or value != value.strip():
        return None
    if value.startswith(("/", "~")) or any(
        token in value for token in ("$", "`", "*", "?", "[", "]", "{", "}", "\\")
    ):
        return None

    parts = list(base.parts)
    for part in PurePosixPath(value).parts:
        if part in {"", "."}:
            continue
        if part == "..":
            if not parts:
                return None
            parts.pop()
        else:
            parts.append(part)
    return PurePosixPath(*parts) if parts else PurePosixPath(".")


def _shell_route_invocations(
    program: _ShellProgram,
    working_directory: PurePosixPath | None,
    *,
    parent_status_propagates: bool = True,
    errexit: bool = False,
) -> list[_ShellInvocation]:
    """Walk the supported shell AST, carrying cwd and exit-status reachability."""
    invocations: list[_ShellInvocation] = []
    if not program.groups:
        return invocations

    final_group_index = len(program.groups) - 1
    current_directory = working_directory
    current_errexit = errexit
    for group_index, group in enumerate(program.groups):
        reachable = True
        for command_index, command in enumerate(group):
            if not reachable:
                break
            executable = Path(command.argv[0]).name if command.argv else ""
            if executable == "cd":
                if len(command.argv) != 2:
                    current_directory = None
                else:
                    changed = _normalize_checkout_path(current_directory, command.argv[1])
                    if command_index == len(group) - 1 and group_index < final_group_index:
                        current_directory = None
                    else:
                        current_directory = changed
            elif command.nested is not None:
                invocations.extend(
                    _shell_route_invocations(
                        command.nested,
                        current_directory,
                        parent_status_propagates=(
                            parent_status_propagates
                            and (group_index == final_group_index or current_errexit)
                        ),
                        errexit=False,
                    )
                )
            else:
                invocations.append(
                    _ShellInvocation(
                        command.argv,
                        current_directory,
                        parent_status_propagates
                        and (group_index == final_group_index or current_errexit),
                    )
                )

            if command.enables_errexit:
                current_errexit = True
            if command.terminates:
                return invocations
            if not command.may_succeed:
                reachable = False
                if current_errexit:
                    return invocations
    return invocations


def _condition_is_statically_true(scope: Mapping[str, Any]) -> bool:
    if "if" not in scope:
        return True
    condition = scope["if"]
    if condition is True:
        return True
    if not isinstance(condition, str):
        return False
    normalized = re.sub(r"\s+", "", condition).lower()
    return normalized in {"true", "${{true}}"}


def _run_defaults(scope: Mapping[str, Any]) -> tuple[dict[str, Any], tuple[str, ...]]:
    errors: list[str] = []
    defaults = scope.get("defaults", {})
    if not isinstance(defaults, dict):
        return {}, ("defaults must be a static mapping",)
    if set(defaults) - {"run"}:
        errors.append("unsupported defaults keys")
    run_defaults = defaults.get("run", {})
    if not isinstance(run_defaults, dict):
        errors.append("defaults.run must be a static mapping")
        return {}, tuple(errors)
    if set(run_defaults) - {"shell", "working-directory"}:
        errors.append("unsupported defaults.run keys")
    return run_defaults, tuple(errors)


def _effective_run_setting(
    workflow_run: Mapping[str, Any],
    job_run: Mapping[str, Any],
    step: Mapping[str, Any],
    key: str,
) -> object:
    for scope in (step, job_run, workflow_run):
        if key in scope:
            return scope[key]
    return _MISSING


_MISSING = object()


def _workflow_route_context_errors(
    workflow: Mapping[str, Any],
    job: Mapping[str, Any],
    step: Mapping[str, Any],
    *,
    allow_needs: bool = False,
) -> tuple[str, ...]:
    errors: list[str] = []
    if not _condition_is_statically_true(job) or not _condition_is_statically_true(step):
        errors.append("job/step condition is not statically unconditional")
    for scope, label in ((job, "job"), (step, "step")):
        if scope.get("continue-on-error", False) is not False:
            errors.append(f"{label} continue-on-error is not literal false/absent")
    if "needs" in job and job["needs"] not in ([], ()):
        needs = job["needs"]
        if isinstance(needs, str):
            dependency_names = [needs]
        elif isinstance(needs, list):
            dependency_names = needs
        else:
            dependency_names = []
        jobs = workflow.get("jobs", {})
        valid_needs = (
            allow_needs
            and bool(dependency_names)
            and isinstance(jobs, dict)
            and all(
                isinstance(name, str)
                and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]*", name) is not None
                and isinstance(jobs.get(name), dict)
                and _condition_is_statically_true(jobs[name])
                and jobs[name].get("continue-on-error", False) is False
                and jobs[name].get("needs", []) in ([], ())
                and "strategy" not in jobs[name]
                for name in dependency_names
            )
        )
        if not valid_needs:
            errors.append("job has unsupported or status-promoting dependencies")
    if "strategy" in job:
        errors.append("job strategy is outside the admitted static runner profile")
    if "container" in job:
        errors.append("job container changes the shell execution profile")
    if "environment" in job:
        errors.append("job environment has an unmodeled approval gate")
    runner = job.get("runs-on")
    if runner != "ubuntu-latest":
        errors.append("job runner selector is outside the admitted ubuntu-latest profile")

    for scope, label in ((workflow, "workflow"), (job, "job"), (step, "step")):
        if "env" in scope and scope["env"] != {}:
            errors.append(f"{label} environment can alter shell or command context")

    workflow_run, workflow_errors = _run_defaults(workflow)
    job_run, job_errors = _run_defaults(job)
    errors.extend(workflow_errors)
    errors.extend(job_errors)
    if "shell" in step:
        effective_shell = step["shell"]
    elif "shell" in job_run:
        effective_shell = job_run["shell"]
    else:
        effective_shell = workflow_run.get("shell", _MISSING)
    if effective_shell is not _MISSING and (
        not isinstance(effective_shell, str) or effective_shell not in {"bash", "sh"}
    ):
        errors.append("effective run shell is not a built-in bash/sh profile")
    if "background" in step and step["background"] is not False:
        errors.append("background step has deferred status semantics")
    if any(key in step for key in ("wait", "wait-all", "parallel", "cancel")):
        errors.append("step uses unsupported asynchronous workflow semantics")
    return tuple(errors)


def _workflow_source_checkout_root(
    steps: Sequence[object], before_index: int
) -> tuple[PurePosixPath | None, tuple[str, ...]]:
    """Resolve the source checkout prefix before a workflow run step."""
    errors: list[str] = []
    prior_steps = steps[:before_index]
    if any(not isinstance(step, dict) for step in prior_steps):
        errors.append("a prior workflow step is not a static mapping")
    checkouts = [
        step
        for step in prior_steps
        if isinstance(step, dict)
        and isinstance(step.get("uses"), str)
        and step["uses"].split("@", 1)[0] == "actions/checkout"
    ]
    if not checkouts:
        return None, (*errors, "no preceding actions/checkout source declaration")
    if len(checkouts) != 1:
        return None, (*errors, "multiple preceding actions/checkout declarations are ambiguous")

    checkout = checkouts[0]
    uses = checkout.get("uses")
    if (
        not isinstance(uses, str)
        or re.fullmatch(r"actions/checkout@[A-Za-z0-9._/-]+", uses) is None
    ):
        errors.append("source checkout action reference is not a literal actions/checkout ref")
    if not _condition_is_statically_true(checkout):
        errors.append("source checkout step condition is not statically unconditional")
    if checkout.get("continue-on-error", False) is not False:
        errors.append("source checkout step continue-on-error is not literal false/absent")
    if "run" in checkout:
        errors.append("source checkout step also declares a run command")

    with_inputs = checkout.get("with", {})
    normalized_inputs, input_errors = _normalize_checkout_inputs(with_inputs)
    errors.extend(input_errors)
    if normalized_inputs is None:
        return None, tuple(errors)
    source_root = _normalize_checkout_path(PurePosixPath("."), normalized_inputs.get("path", "."))
    if source_root is None:
        errors.append("source checkout path is not a literal workspace-relative path")
    return source_root, tuple(errors)


def _workflow_route_observations(
    relative_path: str, *, allow_needs: bool = False
) -> tuple[list[_RouteObservation], str | None]:
    path = _resolve(relative_path)
    if not path.exists():
        return [], f"{relative_path} is missing"
    try:
        payload = _load_unique_yaml(path)
    except (OSError, yaml.YAMLError) as exc:
        return [], f"{relative_path} cannot be parsed as unique-key YAML: {exc}"
    if not isinstance(payload, dict) or not isinstance(payload.get("jobs"), dict):
        return [], f"{relative_path} has no parsed jobs mapping"

    observations: list[_RouteObservation] = []
    workflow_run, workflow_errors = _run_defaults(payload)
    for job in payload["jobs"].values():
        if not isinstance(job, dict) or not isinstance(job.get("steps"), list):
            continue
        steps = job["steps"]
        job_run, _job_default_errors = _run_defaults(job)
        for step_index, step in enumerate(steps):
            if not isinstance(step, dict) or not isinstance(step.get("run"), str):
                continue
            source_checkout_root, checkout_errors = _workflow_source_checkout_root(
                steps, step_index
            )
            context_errors = list(
                _workflow_route_context_errors(payload, job, step, allow_needs=allow_needs)
            )
            context_errors.extend(workflow_errors)
            context_errors.extend(_job_default_errors)
            context_errors.extend(checkout_errors)
            effective_directory = _effective_run_setting(
                workflow_run, job_run, step, "working-directory"
            )
            if effective_directory is _MISSING:
                # GitHub Actions starts each run step from GITHUB_WORKSPACE,
                # independent of where actions/checkout placed repository bytes.
                working_directory = PurePosixPath(".")
            else:
                working_directory = _normalize_checkout_path(
                    PurePosixPath("."), effective_directory
                )
                if working_directory is None:
                    context_errors.append(
                        "effective working-directory is not a literal workspace-relative path"
                    )
            effective_shell = _effective_run_setting(workflow_run, job_run, step, "shell")
            if effective_shell is not _MISSING and (
                not isinstance(effective_shell, str) or effective_shell not in {"bash", "sh"}
            ):
                context_errors.append("effective run shell is not a built-in bash/sh profile")
            program = _parse_shell_program(step["run"])
            if program is None:
                continue
            for invocation in _shell_route_invocations(program, working_directory, errexit=True):
                observations.append(
                    _RouteObservation(
                        invocation=invocation,
                        context_errors=tuple(dict.fromkeys(context_errors)),
                        source_checkout_root=source_checkout_root,
                    )
                )
    return observations, None


def _precommit_route_observations(
    relative_path: str, checkout_root: PurePosixPath
) -> tuple[list[_RouteObservation], str | None]:
    path = _resolve(relative_path)
    if not path.exists():
        return [], f"{relative_path} is missing"
    try:
        payload = _load_unique_yaml(path)
    except (OSError, yaml.YAMLError) as exc:
        return [], f"{relative_path} cannot be parsed as unique-key YAML: {exc}"
    if not isinstance(payload, dict) or not isinstance(payload.get("repos"), list):
        return [], f"{relative_path} has no parsed pre-commit repositories"

    observations: list[_RouteObservation] = []
    for repository in payload["repos"]:
        if not isinstance(repository, dict) or repository.get("repo") != "local":
            continue
        hooks = repository.get("hooks")
        if not isinstance(hooks, list):
            continue
        for hook in hooks:
            if not isinstance(hook, dict) or hook.get("id") != "repository-sota-closeout":
                continue
            errors: list[str] = []
            if hook.get("language") != "system":
                errors.append("pre-commit hook language is not system")
            if hook.get("always_run") is not True:
                errors.append("pre-commit hook is not always_run")
            if hook.get("pass_filenames") is not False:
                errors.append("pre-commit hook may receive unmatched filenames")
            if hook.get("args", []) not in ([], None):
                errors.append("pre-commit hook args are outside the admitted profile")
            entry = hook.get("entry")
            if isinstance(entry, str):
                try:
                    argv = shlex.split(entry, posix=True)
                except ValueError:
                    continue
            elif isinstance(entry, list) and all(isinstance(item, str) for item in entry):
                argv = list(entry)
            else:
                continue
            command = _parse_shell_command(argv)
            if command is None:
                continue
            if command.nested is None:
                invocations = [_ShellInvocation(tuple(argv), checkout_root, True)]
            else:
                invocations = _shell_route_invocations(command.nested, checkout_root, errexit=False)
            observations.extend(
                _RouteObservation(
                    invocation,
                    tuple(errors),
                    source_checkout_root=PurePosixPath("."),
                )
                for invocation in invocations
            )
    return observations, None


def _wiring_route_is_safe(
    relative_path: str,
    expected_argv: tuple[str, ...],
    expected_directory: PurePosixPath,
    *,
    precommit: bool,
) -> tuple[bool, str | None]:
    if precommit:
        observations, error = _precommit_route_observations(relative_path, PurePosixPath("."))
    else:
        observations, error = _workflow_route_observations(relative_path)
    if error is not None:
        return False, error
    matches = [
        observation for observation in observations if observation.invocation.argv == expected_argv
    ]
    if not matches:
        return False, "no parsed executable invocation has the required argv and mode"
    for observation in matches:
        if observation.context_errors:
            return False, "; ".join(observation.context_errors)
        if not observation.invocation.status_propagates:
            return False, "the command is not in a status-propagating shell position"
        if observation.source_checkout_root is None:
            return False, "the source checkout location is not statically established"
        expected_source_directory = _normalize_checkout_path(
            observation.source_checkout_root, expected_directory.as_posix()
        )
        if observation.invocation.working_directory != expected_source_directory:
            return (
                False,
                "the effective command working directory is not the source-relative expected root",
            )
    return True, None


def _check_wiring() -> list[Finding]:
    findings: list[Finding] = []
    contract_only = (
        "uv",
        "run",
        "polisyos-tools",
        "workspace",
        "repository-sota-closeout",
        "--contract-only",
    )
    full_closeout = contract_only[:-1]
    routes = (
        (".pre-commit-config.yaml", contract_only, PurePosixPath("policy-engine"), True),
        (
            "../.github/workflows/abi.yml",
            contract_only,
            PurePosixPath("policy-engine"),
            False,
        ),
        (
            "ops/ci/templates/workflows/arch.yml",
            full_closeout,
            PurePosixPath("."),
            False,
        ),
    )
    for relative_path, expected, expected_directory, is_precommit in routes:
        path = _resolve(relative_path)
        if not path.exists():
            findings.append(Finding("wiring", "wiring file missing", relative_path))
            continue
        safe, reason = _wiring_route_is_safe(
            relative_path, expected, expected_directory, precommit=is_precommit
        )
        if not safe:
            if reason is not None and "cannot be parsed" in reason:
                findings.append(
                    Finding(
                        "wiring",
                        f"wiring source could not be inspected: {reason}",
                        relative_path,
                    )
                )
            else:
                findings.append(
                    Finding(
                        "wiring",
                        f"{relative_path} has no fail-closed executable closeout route: {reason}",
                        relative_path,
                    )
                )
    findings.extend(_check_last_mile_gate_ownership())
    return findings


def _capture_command_specs(module_name: str, argv: list[str]) -> list[tuple[str, ...]]:
    from importlib import import_module

    module = import_module(module_name)
    commands: list[tuple[str, ...]] = []

    def capture(command: object) -> None:
        actual = getattr(command, "argv", None)
        if isinstance(actual, (tuple, list)):
            commands.append(tuple(str(token) for token in actual))

    with (
        patch.object(module, "run_command", side_effect=capture),
        contextlib.redirect_stdout(io.StringIO()),
    ):
        module.main(argv)
    return commands


def _capture_closeout_subprocess_commands() -> dict[str, list[tuple[str, ...]]]:
    captured: dict[str, list[tuple[str, ...]]] = {}

    def capture(
        gate: str, command: Sequence[str], *, receipt_dir: Path | None
    ) -> subprocess.CompletedProcess[str]:
        del receipt_dir
        captured.setdefault(gate, []).append(tuple(str(token) for token in command))
        return subprocess.CompletedProcess(list(command), 0, stdout="", stderr="")

    with (
        patch.object(sys.modules[__name__], "_run_subprocess_with_receipt", side_effect=capture),
        patch.object(sys.modules[__name__], "_run_conditional_registered_gates", return_value=[]),
    ):
        _run_fail_closed_subprocess_gates(
            argparse.Namespace(skip_generated_checks=False, subprocess_receipt_dir=None)
        )
    return captured


def _workflow_commands(relative_path: str) -> tuple[list[tuple[str, ...]], str | None]:
    """Read executable product-root commands from safe release-workflow contexts."""
    observations, error = _workflow_route_observations(relative_path, allow_needs=True)
    if error is not None:
        return [], error
    return [
        observation.invocation.argv
        for observation in observations
        if not observation.context_errors
        and observation.source_checkout_root is not None
        and observation.invocation.status_propagates
        and observation.invocation.working_directory
        == _normalize_checkout_path(observation.source_checkout_root, "policy-engine")
    ], None


def _last_mile_owner_command_inventory() -> tuple[dict[str, list[tuple[str, ...]]], dict[str, Any]]:
    from importlib import import_module

    verify = import_module("tools.devx.workspace.verify")
    ci_parity = import_module("tools.devx.workspace.ci_parity")
    sota_commands = _capture_closeout_subprocess_commands()
    inventory: dict[str, list[tuple[str, ...]]] = {
        "repository-sota-closeout": [
            command for commands in sota_commands.values() for command in commands
        ],
        "workspace acceptance-audit": [
            command for commands in sota_commands.values() for command in commands
        ],
        "workspace verify": _capture_command_specs(
            "tools.devx.workspace.verify", ["--backend-only", "--skip-doctor"]
        ),
        "workspace ci-parity": _capture_command_specs(
            "tools.devx.workspace.ci_parity",
            ["--backend-only", "--skip-doctor", "--skip-runtime-http"],
        ),
    }
    release_commands, error = _workflow_commands("../.github/workflows/release.yml")
    if error is None:
        inventory["release workflow"] = release_commands
    else:
        inventory["release workflow"] = []
    return inventory, {
        "workspace verify": verify,
        "workspace ci-parity": ci_parity,
        "release workflow error": error,
    }


def _executable_argv_matches(expected: tuple[str, ...], actual: tuple[str, ...]) -> bool:
    if len(expected) != len(actual):
        return False
    if expected and expected[0] == "uv":
        return Path(actual[0]).name == "uv" and actual[1:] == expected[1:]
    return actual == expected


def _check_last_mile_gate_ownership() -> list[Finding]:
    findings: list[Finding] = []
    inventory, owner_modules = _last_mile_owner_command_inventory()
    release_error = owner_modules["release workflow error"]
    for gate in LAST_MILE_GATE_OWNERSHIP:
        commands = inventory.get(gate.owner, [])
        expected = gate.argv
        if gate.owner_script_attribute is not None:
            module = owner_modules.get(gate.owner)
            script = getattr(module, gate.owner_script_attribute, None)
            if not isinstance(script, str):
                script = None
            if script is not None:
                expected = (*expected, script.strip())
        if gate.owner == "release workflow" and release_error is not None:
            findings.append(
                Finding(
                    "last-mile-wiring",
                    f"{gate.id} owner workflow could not be inspected",
                    str(release_error),
                )
            )
            continue
        if not any(_executable_argv_matches(expected, command) for command in commands):
            findings.append(
                Finding(
                    "last-mile-wiring",
                    f"{gate.id} is not dispatched through {gate.owner}",
                    f"{gate.source_path} is missing executable argv: {shlex.join(expected)}",
                )
            )
    return findings


def _check_closeout_docs() -> list[Finding]:
    findings: list[Finding] = []
    required_paths = (
        "docs/plans/accepted/REPOSITORY_SOTA_PHASE_5_CLOSEOUT.md",
        "docs/reference/repository-topology.md",
        "docs/reference/quality-gates.md",
        "docs/reference/repository-hygiene.md",
        "docs/reference/contributor-start-here.md",
        "docs/adr/README.md",
        "docs/plans/README.md",
    )
    for relative_path in required_paths:
        if not _resolve(relative_path).exists():
            findings.append(Finding("docs", "required closeout doc missing", relative_path))
    plan = _resolve("docs/plans/accepted/REPOSITORY_SOTA_PLAN.md")
    if "REPOSITORY_SOTA_PHASE_5_CLOSEOUT.md" not in plan.read_text(encoding="utf-8"):
        findings.append(Finding("docs", "main plan does not link Phase 5 closeout report"))
    return findings


def _check_public_polish_contract() -> list[Finding]:
    findings: list[Finding] = []
    active_sota = sorted(_resolve("docs/plans/active").glob("REPOSITORY_SOTA*.md"))
    if active_sota:
        findings.append(
            Finding(
                "public-polish",
                "Repository SOTA evidence remains in active lifecycle",
                ", ".join(path.name for path in active_sota),
            )
        )

    required_links = {
        "docs/index.md": "reference/repository-topology.md",
        "docs/reference/index.md": "repository-topology.md",
        "docs/reference/operations/index.md": "../repository-topology.md",
        "architecture/tooling/mkdocs/generated.yml": "reference/repository-topology.md",
        "mkdocs.yml": "architecture/tooling/mkdocs/generated.yml",
    }
    for relative_path, needle in required_links.items():
        text = _resolve(relative_path).read_text(encoding="utf-8")
        if needle not in text:
            findings.append(
                Finding(
                    "public-polish",
                    f"{relative_path} does not link topology reference",
                    needle,
                )
            )

    public_roots = (
        "docs/reference",
        "docs/how-to",
        "docs/runbooks",
        "docs/tutorials",
        "docs/brand",
    )
    excluded_link = re.compile(
        r"\]\([^)]*(?:plans/active|archive/(?:plans|reports))/[^)]*\.md[^)]*\)"
    )
    stale_current_topology = (
        "Product-root GitHub Actions workflows are not active platform files today",
        "legacy root-level `cloud_deploy/`",
        "`policy-engine/.github`",
        "`policy-engine/cloud_deploy`",
        "`policy-engine/deploy`",
        "`policy-engine/docker`",
        "`policy-engine/gcp`",
    )
    for root in public_roots:
        for path in _resolve(root).rglob("*.md"):
            text = path.read_text(encoding="utf-8")
            for line_number, line in enumerate(text.splitlines(), start=1):
                if excluded_link.search(line):
                    findings.append(
                        Finding(
                            "public-polish",
                            "published doc links to excluded plan evidence",
                            f"{path.relative_to(REPO_ROOT)}:{line_number}",
                        )
                    )
                for phrase in stale_current_topology:
                    if phrase in line:
                        findings.append(
                            Finding(
                                "public-polish",
                                "published doc describes retired topology as current",
                                f"{path.relative_to(REPO_ROOT)}:{line_number}:{phrase}",
                            )
                        )
    return findings


def _registered_subprocess_gates(*, skip_generated_checks: bool) -> list[tuple[str, list[str]]]:
    commands: list[tuple[str, list[str]]] = []
    for item in _gate_registry_rows():
        if not isinstance(item, dict):
            continue
        coverage = item.get("coverage")
        if not isinstance(coverage, list) or "subprocess" not in coverage:
            continue
        gate_id = item.get("id")
        if not isinstance(gate_id, str) or not gate_id.strip():
            continue
        command_text = item.get("command")
        skip_command = item.get("skip_command")
        if skip_generated_checks and gate_id == "generated-drift":
            required = _REQUIRED_GATE_CONTRACTS.get(gate_id)
            if required is not None and skip_command == required.skip_command:
                command_text = skip_command
        command = _parse_gate_command(command_text)
        if command is not None:
            commands.append((gate_id, command))
    return commands


def _supporting_subprocess_gates() -> list[tuple[str, list[str]]]:
    return [
        (
            "repository-sota-registry-contract",
            [
                "uv",
                "run",
                "pytest",
                "tests/repo_quality/architecture/test_repository_sota_phase5_closeout.py",
                "-q",
            ],
        ),
        (
            "repository-structure",
            [
                "uv",
                "run",
                "python",
                "tools/quality/validation/repository_structure_phase0.py",
                "gate",
                "--gate",
                "all",
                "--mode",
                "fail-closed",
                "--json",
            ],
        ),
        (
            "last-mile-inventory",
            [
                "uv",
                "run",
                "python",
                "tools/quality/validation/repository_last_mile_inventory.py",
                "--json-output",
                "_build/.tmp/last-mile/inventory.json",
                "--check",
            ],
        ),
        (
            "package-import-gates",
            [
                "uv",
                "run",
                "python",
                "tools/quality/validation/check_package_import_gates.py",
                "--fail-closed",
                "--json-output",
                "_build/.tmp/last-mile/package-import-gates.json",
            ],
        ),
        (
            "directory-health",
            [
                "uv",
                "run",
                "python",
                "tools/quality/validation/directory_health.py",
                "--repo-root",
                ".",
                "--json-output",
                "_build/.tmp/last-mile/directory-health.json",
                "--markdown-output",
                "_build/.tmp/last-mile/directory-health.md",
                "--fail-on-regression",
            ],
        ),
        (
            "test-ratchets-helper-topology",
            [
                "uv",
                "run",
                "python",
                "tools/quality/testing/report_test_ratchets.py",
                "--format",
                "json",
                "--output",
                "_build/.tmp/last-mile/test-ratchets.json",
                "--fail-on-regression",
            ],
        ),
        (
            "dead-overrides",
            [
                "uv",
                "run",
                "python",
                "tools/ops_runners/reports/dead_overrides.py",
                "--json-output",
                "_build/.tmp/last-mile/dead-overrides.json",
            ],
        ),
        (
            "extension-examples",
            ["uv", "run", "python", "tools/quality/validation/check_extension_examples.py"],
        ),
        (
            "adr-thematic-index",
            ["uv", "run", "python", "tools/quality/validation/generate_adr_index.py", "--check"],
        ),
        (
            "validator-module-size",
            [
                "uv",
                "run",
                "python",
                "tools/quality/validation/architecture_report_only_contracts.py",
                "--report",
                "module-size",
                "--json-output",
                "_build/.tmp/last-mile/module-size.json",
                "--fail-on-contract-errors",
            ],
        ),
        (
            "schema-purity",
            ["uv", "run", "python", "-c", SCHEMA_PURITY_SNIPPET.strip()],
        ),
        (
            "operability-release",
            [
                "uv",
                "run",
                "python",
                "tools/ops_runners/release/check_operability_release_gates.py",
                "--json-output",
                "_build/.tmp/last-mile/operability-release-gates.json",
                "--fail-closed",
            ],
        ),
        (
            "compatibility-release",
            [
                "uv",
                "run",
                "python",
                "tools/ops_runners/release/check_compatibility_release_gates.py",
                "--json-output",
                "_build/.tmp/last-mile/compatibility-release-gates.json",
                "--fail-on-contract-errors",
            ],
        ),
        (
            "acceptance-audit",
            [
                "uv",
                "run",
                "polisyos-tools",
                "workspace",
                "acceptance-audit",
                "--json-output",
                "_build/.tmp/last-mile/platform-acceptance.json",
                "--summary",
                "_build/.tmp/last-mile/platform-acceptance.md",
            ],
        ),
    ]


def _conditional_gate_handlers() -> dict[str, Callable[..., list[Finding]]]:
    return {"docs-freshness-runtime": _run_docs_freshness_gate}


def _run_conditional_registered_gates(*, receipt_dir: Path | None) -> list[Finding]:
    findings: list[Finding] = []
    handlers = _conditional_gate_handlers()
    for item in _gate_registry_rows():
        if not isinstance(item, dict):
            continue
        coverage = item.get("coverage")
        if not isinstance(coverage, list):
            continue
        for route in coverage:
            if not isinstance(route, str) or not route.startswith("conditional:"):
                continue
            handler = handlers.get(route.partition(":")[2])
            if handler is not None:
                findings.extend(handler(gate=item, receipt_dir=receipt_dir))
    return findings


def _preflight_checks() -> tuple[tuple[str, Callable[[], list[Finding]]], ...]:
    return (
        ("gate-registry", _check_gate_registry),
        ("final-topology-contract", _check_final_topology_contract),
        ("ops-modes", _check_ops_modes),
        ("docs-freshness-contract", _check_docs_freshness_contract),
        ("time-bounded-import-exceptions", _check_time_bounded_import_exceptions),
        ("complexity-exception-contract", _check_complexity_exceptions),
        ("migration-shim-contract", _check_migration_shims),
        ("phase65-exception-cleanup", _check_phase65_exception_cleanup),
        ("wiring", _check_wiring),
        ("closeout-docs", _check_closeout_docs),
        ("public-polish-contract", _check_public_polish_contract),
    )


def _run_fail_closed_subprocess_gates(args: argparse.Namespace) -> list[Finding]:
    findings: list[Finding] = []
    receipt_dir = getattr(args, "subprocess_receipt_dir", None)
    commands = _registered_subprocess_gates(skip_generated_checks=args.skip_generated_checks)
    commands.extend(_supporting_subprocess_gates())
    for gate, command in commands:
        completed = _run_subprocess_with_receipt(
            gate,
            command,
            receipt_dir=receipt_dir,
        )
        if completed.returncode != 0:
            findings.append(Finding(gate, "subprocess gate failed", _compact_output(completed)))

    findings.extend(_run_conditional_registered_gates(receipt_dir=receipt_dir))
    return findings


_CHILD_REPORT_OUTPUT_OPTIONS = frozenset(
    {"--json-output", "--markdown-output", "--output", "--summary"}
)


def _route_native_child_report_outputs(gate: str, command: Sequence[str]) -> tuple[str, ...]:
    """Route every declared child report flag beneath its gate's owned directory.

    Only an explicit secure-output scope changes argv. The command-registry
    ``--output ... --check`` option is a comparison input, not a write sink.
    """
    if active_secure_output_root() is None:
        return tuple(command)
    routed = [str(part) for part in command]
    for index, token in enumerate(tuple(routed)):
        option, separator, value = token.partition("=")
        if option not in _CHILD_REPORT_OUTPUT_OPTIONS:
            continue
        if option == "--output" and "--check" in routed:
            continue
        value_index = index + 1 if not separator else None
        if value_index is not None:
            if value_index >= len(routed):
                raise ValueError(f"{gate}: {option} requires a report path")
            requested = Path(routed[value_index])
        else:
            requested = Path(value)
        if not requested.name or requested.name in {".", ".."}:
            raise ValueError(f"{gate}: {option} requires one report leaf name")
        output_path = scoped_report_path(gate, requested)
        if value_index is None:
            routed[index] = f"{option}={output_path}"
        else:
            routed[value_index] = str(output_path)
    return tuple(routed)


def _run_subprocess_with_receipt(
    gate: str,
    command: Sequence[str],
    *,
    receipt_dir: Path | None,
) -> subprocess.CompletedProcess[str]:
    """Run one child with its report outputs and captured receipts in the active scope."""
    routed_command = _route_native_child_report_outputs(gate, command)
    if receipt_dir is None:
        return run_command(
            routed_command,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

    raw_completed = run_command(
        routed_command,
        cwd=REPO_ROOT,
        capture_output=True,
        check=False,
    )
    _write_subprocess_receipt(
        receipt_dir,
        gate=gate,
        command=routed_command,
        completed=raw_completed,
    )
    return subprocess.CompletedProcess(
        raw_completed.args,
        raw_completed.returncode,
        stdout=_decode_subprocess_output(raw_completed.stdout or b""),
        stderr=_decode_subprocess_output(raw_completed.stderr or b""),
    )


def _decode_subprocess_output(output: bytes) -> str:
    """Decode retained child output for existing gate summaries and comparisons."""
    return (
        output.decode("utf-8", errors="backslashreplace").replace("\r\n", "\n").replace("\r", "\n")
    )


def _write_subprocess_receipt(
    receipt_dir: Path,
    *,
    gate: str,
    command: Sequence[str],
    completed: subprocess.CompletedProcess[bytes],
) -> None:
    """Atomically retain one child gate's raw output and command/exit/hash manifest."""
    stdout = completed.stdout or b""
    stderr = completed.stderr or b""
    output_dir = receipt_dir / gate
    atomic_write_bytes(output_dir / "stdout.bin", stdout)
    atomic_write_bytes(output_dir / "stderr.bin", stderr)
    atomic_write_json(
        output_dir / "receipt.json",
        {
            "schema_version": 1,
            "gate": gate,
            "command": list(command),
            "cwd": str(REPO_ROOT),
            "exit_code": completed.returncode,
            "gate_output_decoding": {
                "encoding": "utf-8",
                "errors": "backslashreplace",
                "newline_normalization": "universal",
            },
            "stdout": {
                "file": "stdout.bin",
                "byte_length": len(stdout),
                "sha256": hashlib.sha256(stdout).hexdigest(),
            },
            "stderr": {
                "file": "stderr.bin",
                "byte_length": len(stderr),
                "sha256": hashlib.sha256(stderr).hexdigest(),
            },
        },
    )


def _compact_output(completed: subprocess.CompletedProcess[str], *, limit: int = 4000) -> str:
    output = ((completed.stdout or "") + (completed.stderr or "")).strip()
    if len(output) <= limit:
        return output
    return output[:limit] + "\n...[truncated]..."


def _run_docs_freshness_gate(
    *, gate: dict[str, Any] | None = None, receipt_dir: Path | None = None
) -> list[Finding]:
    if gate is None:
        matching = [
            item
            for item in _gate_registry_rows()
            if isinstance(item, dict) and item.get("id") == "docs-freshness"
        ]
        if len(matching) != 1:
            return [Finding("docs-freshness", "registry row is missing or ambiguous")]
        gate = matching[0]
    baseline = _read_toml("architecture/exceptions/docs_freshness.toml")[
        "docs_freshness_exceptions"
    ]
    findings, expected_count, expected_digest = _docs_freshness_contract_findings(baseline)
    if expected_count is None:
        return findings
    if expected_count > 0 and findings:
        return findings

    command = _parse_gate_command(gate.get("command"))
    if command is None:
        return [*findings, Finding("docs-freshness", "registered command is malformed")]
    completed = _run_subprocess_with_receipt(
        "docs-freshness",
        command,
        receipt_dir=receipt_dir,
    )
    output = (completed.stdout or "") + (completed.stderr or "")
    observed_count = _extract_docs_violation_count(output)
    findings.extend(
        Finding("docs-freshness", message, str(observed_count))
        for message in evaluate_docs_freshness_observation(
            expected_count=expected_count,
            expected_digest=expected_digest,
            returncode=completed.returncode,
            output=output,
        )
    )
    return findings


def _extract_docs_violation_count(output: str) -> int | None:
    return extract_docs_freshness_violation_count(output)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
