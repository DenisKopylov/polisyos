#!/usr/bin/env python3
"""Enforce the Repository SOTA Phase 5 closeout gate."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import re
import subprocess
import sys
import tomllib
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tools.lib.fs import atomic_write_json
from tools.lib.imports import repo_root_from

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

root = Path("schemas")
output = Path("_build/.tmp/last-mile/schemas-python-residue.txt")
output.parent.mkdir(parents=True, exist_ok=True)
matches = []
if root.exists():
    for path in sorted(root.rglob("*")):
        if path.name == "__pycache__" or path.suffix == ".py":
            matches.append(path.as_posix())
output.write_text("\\n".join(matches) + ("\\n" if matches else ""), encoding="utf-8")
if matches:
    print("\\n".join(matches))
    raise SystemExit(1)
"""
LAST_MILE_GATE_OWNERSHIP: tuple[dict[str, str], ...] = (
    {
        "id": "repository-structure",
        "owner": "repository-sota-closeout",
        "source_path": "tools/devx/workspace/repository_sota_closeout.py",
        "needle": "repository_structure_phase0.py",
    },
    {
        "id": "repository-last-mile-inventory",
        "owner": "workspace verify",
        "source_path": "tools/devx/workspace/verify.py",
        "needle": "repository_last_mile_inventory.py",
    },
    {
        "id": "shell-package-closure",
        "owner": "workspace verify",
        "source_path": "tools/devx/workspace/verify.py",
        "needle": "check-package-import-gates",
    },
    {
        "id": "cross-cutting-name-collision",
        "owner": "workspace verify",
        "source_path": "tools/devx/workspace/verify.py",
        "needle": "repository_last_mile_inventory.py",
    },
    {
        "id": "schema-purity",
        "owner": "workspace verify",
        "source_path": "tools/devx/workspace/verify.py",
        "needle": "schemas-python-residue.txt",
    },
    {
        "id": "directory-health",
        "owner": "workspace ci-parity",
        "source_path": "tools/devx/workspace/ci_parity.py",
        "needle": "directory_health.py",
    },
    {
        "id": "test-ratchets-helper-topology",
        "owner": "workspace ci-parity",
        "source_path": "tools/devx/workspace/ci_parity.py",
        "needle": "report_test_ratchets.py",
    },
    {
        "id": "extension-examples",
        "owner": "workspace ci-parity",
        "source_path": "tools/devx/workspace/ci_parity.py",
        "needle": "check_extension_examples.py",
    },
    {
        "id": "adr-thematic-index",
        "owner": "workspace ci-parity",
        "source_path": "tools/devx/workspace/ci_parity.py",
        "needle": "generate_adr_index.py",
    },
    {
        "id": "validator-module-size",
        "owner": "workspace ci-parity",
        "source_path": "tools/devx/workspace/ci_parity.py",
        "needle": "module-size",
    },
    {
        "id": "dead-overrides",
        "owner": "repository-sota-closeout",
        "source_path": "tools/devx/workspace/repository_sota_closeout.py",
        "needle": "dead_overrides.py",
    },
    {
        "id": "operability-release",
        "owner": "release workflow",
        "source_path": "../.github/workflows/release.yml",
        "needle": "check-operability-release-gates",
    },
    {
        "id": "compatibility-release",
        "owner": "release workflow",
        "source_path": "../.github/workflows/release.yml",
        "needle": "check-compatibility-release-gates",
    },
    {
        "id": "acceptance-audit",
        "owner": "workspace acceptance-audit",
        "source_path": "tools/devx/workspace/repository_sota_closeout.py",
        "needle": "acceptance-audit",
    },
)


@dataclass(frozen=True)
class Finding:
    gate: str
    message: str
    detail: str = ""

    def render(self) -> str:
        suffix = f" :: {self.detail}" if self.detail else ""
        return f"[{self.gate}] {self.message}{suffix}"


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
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    findings: list[Finding] = []

    findings.extend(_check_gate_registry())
    findings.extend(_check_final_topology_contract())
    findings.extend(_check_ops_modes())
    findings.extend(_check_docs_freshness_contract())
    findings.extend(_check_time_bounded_import_exceptions())
    findings.extend(_check_complexity_exceptions())
    findings.extend(_check_migration_shims())
    findings.extend(_check_phase65_exception_cleanup())
    findings.extend(_check_wiring())
    findings.extend(_check_closeout_docs())
    findings.extend(_check_public_polish_contract())

    if not args.contract_only:
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
        atomic_write_json(args.output_json, payload)

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


def _check_gate_registry() -> list[Finding]:
    findings: list[Finding] = []
    data = _read_toml("architecture/gates/repository_sota.toml")
    header = data.get("repository_sota_gates", {})
    if header.get("status") != "fail_closed":
        findings.append(
            Finding(
                "gate-registry",
                "repository_sota_gates.status must be fail_closed",
                str(header.get("status")),
            )
        )
    closeout_report = str(header.get("closeout_report", "")).strip()
    if not closeout_report or not _resolve(closeout_report).exists():
        findings.append(Finding("gate-registry", "closeout report is missing", closeout_report))

    expected = {
        "topology-loose-files",
        "import-linter",
        "public-surface",
        "generated-drift",
        "docs-freshness",
        "public-polish",
        "shim-audit",
        "complexity-exceptions",
        "security-baselines",
        "dependency-baselines",
        "sbom-baseline",
        "commit-policy",
        "command-registry",
    }
    gates = {str(item.get("id", "")): item for item in data.get("gate", [])}
    missing = sorted(expected - set(gates))
    if missing:
        findings.append(Finding("gate-registry", "missing required gates", ", ".join(missing)))

    expected_commands = {
        "docs-freshness": (
            "uv run polisyos-tools workspace repository-sota-closeout --skip-generated-checks"
        ),
        "public-polish": (
            "uv run pytest tests/repo_quality/architecture/test_repository_public_polish.py -q"
        ),
    }
    for gate_id, gate in gates.items():
        if gate.get("mode") != "fail_closed":
            findings.append(Finding("gate-registry", f"{gate_id} is not fail_closed"))
        for field in ("owner", "command", "evidence"):
            value = str(gate.get(field, "")).strip()
            if not value:
                findings.append(Finding("gate-registry", f"{gate_id} missing `{field}`"))
        expected_command = expected_commands.get(gate_id)
        observed_command = str(gate.get("command", "")).strip()
        if expected_command is not None and observed_command != expected_command:
            findings.append(
                Finding(
                    "gate-registry",
                    f"{gate_id} command is not the fail-closed closeout command",
                    observed_command,
                )
            )
        evidence = str(gate.get("evidence", "")).strip()
        if evidence and not _resolve(evidence).exists():
            findings.append(Finding("gate-registry", f"{gate_id} evidence path missing", evidence))
        exceptions = str(gate.get("exceptions", "")).strip()
        if exceptions and not _resolve(exceptions).exists():
            findings.append(
                Finding("gate-registry", f"{gate_id} exception path missing", exceptions)
            )
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
    findings: list[Finding] = []
    baseline = _read_toml("architecture/exceptions/docs_freshness.toml")[
        "docs_freshness_exceptions"
    ]
    if baseline.get("mode") != "fail_closed_baseline":
        findings.append(
            Finding("docs-freshness", "docs freshness mode is not fail_closed_baseline")
        )
    for field in ("owner", "reason", "command", "issue"):
        if not str(baseline.get(field, "")).strip():
            findings.append(Finding("docs-freshness", f"docs freshness baseline missing `{field}`"))

    expires, error = _parse_date(
        baseline.get("expires"),
        gate="docs-freshness",
        subject="docs_freshness_exceptions",
        field="expires",
    )
    if error is not None:
        findings.append(error)
    elif expires is not None and expires < dt.date.today():
        findings.append(Finding("docs-freshness", "docs freshness exception baseline expired"))

    try:
        expected_count = int(baseline.get("expected_violation_count", -1))
    except (TypeError, ValueError):
        expected_count = -1
    if expected_count < 0:
        findings.append(Finding("docs-freshness", "expected_violation_count must be non-negative"))

    digest = str(baseline.get("baseline_sha256", "")).strip()
    if expected_count > 0 and (not digest or digest == "pending"):
        findings.append(Finding("docs-freshness", "docs freshness baseline hash is pending"))
    elif digest and digest != "pending" and not re.fullmatch(r"[0-9a-f]{64}", digest):
        findings.append(Finding("docs-freshness", "docs freshness baseline hash is not sha256"))
    return findings


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


def _check_wiring() -> list[Finding]:
    findings: list[Finding] = []
    checks = {
        ".pre-commit-config.yaml": "repository-sota-closeout",
        "../.github/workflows/abi.yml": "repository-sota-closeout",
        "ops/ci/templates/workflows/arch.yml": "repository-sota-closeout",
    }
    for relative_path, needle in checks.items():
        path = _resolve(relative_path)
        if not path.exists():
            findings.append(Finding("wiring", "wiring file missing", relative_path))
            continue
        if needle not in path.read_text(encoding="utf-8"):
            findings.append(Finding("wiring", f"{relative_path} does not invoke {needle}"))
    findings.extend(_check_last_mile_gate_ownership())
    return findings


def _check_last_mile_gate_ownership() -> list[Finding]:
    findings: list[Finding] = []
    for gate in LAST_MILE_GATE_OWNERSHIP:
        gate_id = gate["id"]
        owner = gate["owner"]
        relative_path = gate["source_path"]
        needle = gate["needle"]
        path = _resolve(relative_path)
        if not path.exists():
            findings.append(
                Finding("last-mile-wiring", f"{gate_id} owner file missing", relative_path)
            )
            continue
        if needle not in path.read_text(encoding="utf-8"):
            findings.append(
                Finding(
                    "last-mile-wiring",
                    f"{gate_id} is not wired through {owner}",
                    f"{relative_path} missing {needle}",
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


def _run_fail_closed_subprocess_gates(args: argparse.Namespace) -> list[Finding]:
    findings: list[Finding] = []
    guardrail_command = [
        "uv",
        "run",
        "polisyos-tools",
        "architecture",
        "guardrails",
        "check",
    ]
    if not args.skip_generated_checks:
        guardrail_command.append("--run-generated-checks")

    commands = [
        ("generated-drift", guardrail_command),
        (
            "import-linter",
            [
                "uv",
                "run",
                "python",
                "tools/quality/lint/lint_imports.py",
                "--policy",
                "architecture/imports/policy.toml",
                "--exceptions",
                "architecture/imports/exceptions.toml",
            ],
        ),
        (
            "command-registry",
            [
                "uv",
                "run",
                "polisyos-tools",
                "docs",
                "--output",
                "docs/reference/tools.md",
                "--check",
            ],
        ),
        (
            "public-polish",
            [
                "uv",
                "run",
                "pytest",
                "tests/repo_quality/architecture/test_repository_public_polish.py",
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
            [
                "uv",
                "run",
                "python",
                "tools/quality/validation/check_extension_examples.py",
            ],
        ),
        (
            "adr-thematic-index",
            [
                "uv",
                "run",
                "python",
                "tools/quality/validation/generate_adr_index.py",
                "--check",
            ],
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
            [
                "uv",
                "run",
                "python",
                "-c",
                SCHEMA_PURITY_SNIPPET.strip(),
            ],
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
    for gate, command in commands:
        completed = subprocess.run(
            command,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode != 0:
            findings.append(Finding(gate, "subprocess gate failed", _compact_output(completed)))

    findings.extend(_run_docs_freshness_gate())
    return findings


def _compact_output(completed: subprocess.CompletedProcess[str], *, limit: int = 4000) -> str:
    output = ((completed.stdout or "") + (completed.stderr or "")).strip()
    if len(output) <= limit:
        return output
    return output[:limit] + "\n...[truncated]..."


def _run_docs_freshness_gate() -> list[Finding]:
    findings: list[Finding] = []
    baseline = _read_toml("architecture/exceptions/docs_freshness.toml")[
        "docs_freshness_exceptions"
    ]
    expires, error = _parse_date(
        baseline.get("expires"),
        gate="docs-freshness",
        subject="docs_freshness_exceptions",
        field="expires",
    )
    if error is not None:
        return [error]
    assert expires is not None
    if expires < dt.date.today():
        return [Finding("docs-freshness", "docs freshness exception baseline expired")]

    command = [
        "uv",
        "run",
        "polisyos-tools",
        "validation",
        "check-docs-accuracy",
        "--repo-root",
        ".",
    ]
    completed = subprocess.run(
        command,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    output = (completed.stdout or "") + (completed.stderr or "")
    digest = hashlib.sha256(output.encode("utf-8")).hexdigest()
    observed_count = _extract_docs_violation_count(output)
    expected_count = int(baseline.get("expected_violation_count", -1))
    expected_digest = str(baseline.get("baseline_sha256", "")).strip()

    if completed.returncode == 0:
        if expected_count not in {0, observed_count}:
            findings.append(
                Finding(
                    "docs-freshness",
                    "docs accuracy is clean but baseline still expects violations",
                    str(expected_count),
                )
            )
        return findings

    if not expected_digest or expected_digest == "pending":
        findings.append(Finding("docs-freshness", "docs freshness baseline hash is pending"))
    if observed_count != expected_count:
        findings.append(
            Finding(
                "docs-freshness",
                "docs freshness violation count changed",
                f"expected {expected_count}, observed {observed_count}",
            )
        )
    if digest != expected_digest:
        findings.append(
            Finding(
                "docs-freshness",
                "docs freshness baseline hash changed",
                f"expected {expected_digest}, observed {digest}",
            )
        )
    return findings


def _extract_docs_violation_count(output: str) -> int:
    match = re.search(r"^- violations:\s+(\d+)$", output, flags=re.MULTILINE)
    if match is None:
        return -1
    return int(match.group(1))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
