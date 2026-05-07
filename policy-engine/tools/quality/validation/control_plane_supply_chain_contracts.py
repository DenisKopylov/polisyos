"""Validate the control-plane and supply-chain contract."""

from __future__ import annotations

import argparse
import json
import re
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tools.lib.imports import repo_root_from
from tools.quality.ci import check_workflow_policy

REPO_ROOT = repo_root_from(__file__)
WORKSPACE_ROOT = REPO_ROOT.parent
DEFAULT_CONTRACT = REPO_ROOT / "architecture" / "control_plane_supply_chain.toml"
DEFAULT_CODEOWNERS = WORKSPACE_ROOT / ".github" / "CODEOWNERS"
DEFAULT_RULESET = WORKSPACE_ROOT / ".github" / "repository-rulesets" / "main.yml"
DEFAULT_CROSSWALK_REPORT = REPO_ROOT / "docs/archive/reports/supply-chain-control-crosswalk.json"
REQUIRED_RULESET_TIERS = {
    "required-review",
    "code-owner-review",
    "fast-pr-checks",
    "release-gate-checks",
    "protected-branch-restrictions",
}
REQUIRED_CROSSWALK_CONTROLS = {
    "OpenSSF Scorecard",
    "SLSA provenance",
    "SBOM",
}
REQUIRED_GENERATED_ARTIFACT_FAMILIES = {
    "release-sbom",
    "supply-chain-control-crosswalk",
}
DEPENDENCY_LOCK_PATHS = {
    ".github/renovate.json",
    "policy-engine/uv.lock",
    "policy-engine/pnpm-lock.yaml",
}
RETIRED_RENOVATE_MATCH_FILE_NAMES = {
    "policy-engine/frontend/runtime-dashboard/package.json",
}
RELEASE_CANDIDATE_REQUIRED_CHECKS = {
    "release SBOM generation",
    "vulnerability scan and policy evaluation",
    "keyless signing",
    "build provenance attestation",
}
JOB_RE = re.compile(r"^  (?P<job>[A-Za-z0-9_-]+):\s*(?:#.*)?$")
JOB_PERMISSIONS_RE = re.compile(r"^    permissions:\s*(?P<inline>.*)$")
PERMISSION_ITEM_RE = re.compile(
    r"^      (?P<permission>[A-Za-z-]+):\s*(?P<level>read|write|none)\s*(?:#.*)?$"
)
INLINE_PERMISSION_RE = re.compile(r"(?P<permission>[A-Za-z-]+)\s*:\s*(?P<level>read|write|none)")

EXTERNAL_CONTROL_BASELINES: dict[str, dict[str, Any]] = {
    "OpenSSF Scorecard": {
        "external_standard": "OpenSSF Scorecard",
        "reference_urls": [
            "https://scorecard.dev/",
            "https://github.com/ossf/scorecard/blob/main/docs/checks.md",
        ],
        "external_control_refs": [
            "Branch-Protection",
            "Code-Review",
            "Dangerous-Workflow",
            "Dependency-Update-Tool",
            "Pinned-Dependencies",
            "Security-Policy",
            "Signed-Releases",
            "Token-Permissions",
            "Vulnerabilities",
        ],
    },
    "SLSA provenance": {
        "external_standard": "SLSA Build Track",
        "reference_urls": [
            "https://slsa.dev/spec/latest/",
            "https://slsa.dev/spec/v1.2/provenance",
        ],
        "external_control_refs": [
            "Build provenance exists for release subjects",
            "Provenance is distributed with release artifacts",
            "Release consumers can verify artifact provenance",
        ],
    },
    "SBOM": {
        "external_standard": "Release SBOM policy",
        "reference_urls": [
            "https://cyclonedx.org/specification/overview/",
            "https://scorecard.dev/",
        ],
        "external_control_refs": [
            "CycloneDX JSON SBOM generated for release candidates",
            "Dependency-lock changes refresh SBOM evidence",
            "Vulnerability report evaluated before release promotion",
        ],
    },
    "Signed artifacts": {
        "external_standard": "OpenSSF Scorecard / Sigstore release signing",
        "reference_urls": [
            "https://scorecard.dev/",
            "https://docs.sigstore.dev/",
        ],
        "external_control_refs": [
            "Signed-Releases",
            "Keyless release artifact signing",
            "Release certificates published with artifacts",
        ],
    },
}


@dataclass(frozen=True)
class Finding:
    severity: str
    check: str
    message: str
    detail: str = ""

    def render(self) -> str:
        suffix = f" :: {self.detail}" if self.detail else ""
        return f"[{self.severity}] {self.check}: {self.message}{suffix}"


def load_contract(path: Path = DEFAULT_CONTRACT) -> dict[str, Any]:
    return tomllib.loads(path.read_text(encoding="utf-8"))


def build_crosswalk_report(contract: dict[str, Any]) -> dict[str, Any]:
    phases = [dict(item) for item in contract.get("release_phase_gate", [])]
    artifacts = [dict(item) for item in contract.get("release_artifact_contract", [])]
    controls: list[dict[str, Any]] = []

    for item in contract.get("control_crosswalk", []):
        control = str(item.get("control", ""))
        baseline = EXTERNAL_CONTROL_BASELINES.get(control, {})
        controls.append(
            {
                "control": control,
                "owner": item.get("owner", ""),
                "external_standard": baseline.get("external_standard", ""),
                "reference_urls": baseline.get("reference_urls", []),
                "external_control_refs": baseline.get("external_control_refs", []),
                "release_phase": item.get("release_phase", ""),
                "reporting_artifact": item.get("reporting_artifact", ""),
                "evidence": item.get("evidence", ""),
                "mapped_phase_gates": _mapped_phase_gates(
                    str(item.get("release_phase", "")),
                    phases,
                ),
            }
        )

    return {
        "schema_version": 1,
        "status": "policy_defined",
        "source_contract": "architecture/control_plane_supply_chain.toml",
        "generated_by": (
            "uv run python tools/quality/validation/"
            "control_plane_supply_chain_contracts.py --crosswalk-json "
            "docs/archive/reports/supply-chain-control-crosswalk.json"
        ),
        "external_reference_baseline": {
            control: {
                "external_standard": data["external_standard"],
                "reference_urls": data["reference_urls"],
            }
            for control, data in EXTERNAL_CONTROL_BASELINES.items()
        },
        "release_phase_gates": phases,
        "release_artifact_contracts": artifacts,
        "controls": controls,
    }


def validate_contract(
    *,
    contract_path: Path = DEFAULT_CONTRACT,
    strict_current_codeowners: bool = False,
) -> list[Finding]:
    contract = load_contract(contract_path)
    findings: list[Finding] = []

    findings.extend(_check_header(contract))
    findings.extend(_check_root_sources(contract))
    findings.extend(_check_owner_mappings(contract, strict_current_codeowners))
    findings.extend(_check_ruleset_targets(contract))
    findings.extend(_check_workflow_permissions(contract))
    findings.extend(_check_release_contract(contract))
    findings.extend(_check_renovate_policy(contract))
    return findings


def blockers(findings: list[Finding]) -> list[Finding]:
    return [finding for finding in findings if finding.severity == "blocker"]


def _check_header(contract: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []
    header = contract.get("control_plane_supply_chain", {})
    if header.get("status") != "active_contract":
        findings.append(
            Finding(
                "blocker",
                "header",
                "control_plane_supply_chain.status must be active_contract",
                str(header.get("status")),
            )
        )
    if not header.get("phase"):
        findings.append(Finding("blocker", "header", "contract must identify remediation scope"))
    if not str(header.get("validation_command", "")).strip():
        findings.append(Finding("blocker", "header", "validation_command is required"))
    return findings


def _check_root_sources(contract: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []
    topology = contract.get("root_topology", {})
    if topology.get("product_root") != "policy-engine":
        findings.append(
            Finding(
                "blocker",
                "root-topology",
                "product_root must remain policy-engine for the current split-root contract",
                str(topology.get("product_root")),
            )
        )
    for label, path in {
        "codeowners_source": DEFAULT_CODEOWNERS,
        "ruleset_source": DEFAULT_RULESET,
    }.items():
        if not path.exists():
            findings.append(Finding("blocker", "root-topology", f"{label} is missing", str(path)))
    if topology.get("wave2_cleanup_phase") != "2.8":
        findings.append(
            Finding(
                "blocker",
                "root-topology",
                "CODEOWNERS/ruleset path cleanup must point at Phase 2.8",
                str(topology.get("wave2_cleanup_phase")),
            )
        )
    return findings


def _check_owner_mappings(
    contract: dict[str, Any], strict_current_codeowners: bool
) -> list[Finding]:
    findings: list[Finding] = []
    mappings = {str(item.get("owner", "")): item for item in contract.get("owner_mapping", [])}
    codeowners_gate = contract.get("codeowners_gate", {})
    fail_closed_codeowners = codeowners_gate.get("mode") == "fail_closed"
    strict_current_codeowners = strict_current_codeowners or fail_closed_codeowners
    cleanup_targets = {
        str(item.get("pattern", "")): item for item in contract.get("codeowners_cleanup_target", [])
    }
    codeowners_patterns = _codeowners_patterns()

    if fail_closed_codeowners and cleanup_targets:
        findings.append(
            Finding(
                "blocker",
                "codeowners-cleanup",
                "Phase 2.8 cleanup targets must not remain in the active contract",
                ", ".join(sorted(cleanup_targets)),
            )
        )

    for owner, mapping in sorted(mappings.items()):
        if not owner:
            findings.append(Finding("blocker", "owner-mapping", "owner_mapping missing owner"))
            continue
        if not mapping.get("target_codeowners_patterns"):
            findings.append(
                Finding("blocker", "owner-mapping", "owner mapping has no target patterns", owner)
            )
        if not mapping.get("current_reviewers") and not mapping.get("personal_repo_exception"):
            findings.append(
                Finding(
                    "blocker",
                    "owner-mapping",
                    "owner mapping needs current reviewers or a personal-repo exception",
                    owner,
                )
            )

    for record in _package_owner_records():
        owner = record["owner"]
        if owner not in mappings:
            findings.append(
                Finding(
                    "blocker",
                    "owner-coverage",
                    "architecture package owner has no owner_mapping",
                    f"{owner} from {record['source']}:{record['module']}",
                )
            )

    stable_modules = _public_stable_modules()
    boundary_owner_by_module = {
        record["module"]: record["owner"]
        for record in _package_owner_records()
        if record["source"] == "architecture/package_boundaries.toml"
    }
    for module in stable_modules:
        owner = boundary_owner_by_module.get(module) or _public_surface_owner(module)
        mapping = mappings.get(owner, {})
        if module not in set(mapping.get("covers_modules", [])):
            findings.append(
                Finding(
                    "blocker",
                    "public-stable-coverage",
                    "public_stable package is not listed in its target owner mapping",
                    f"{module} -> {owner}",
                )
            )
            continue
        expected_pattern = _module_codeowners_pattern(module)
        if expected_pattern and not _pattern_list_covers(
            mapping.get("target_codeowners_patterns", []), expected_pattern
        ):
            findings.append(
                Finding(
                    "blocker",
                    "public-stable-coverage",
                    "public_stable package lacks target CODEOWNERS pattern",
                    f"{module} expects {expected_pattern}",
                )
            )

    missing_cleanup_targets = sorted(
        pattern
        for pattern in _missing_or_retired_codeowners_patterns(codeowners_patterns)
        if pattern not in cleanup_targets
    )
    for pattern in missing_cleanup_targets:
        findings.append(
            Finding(
                "blocker" if fail_closed_codeowners else "advisory",
                "codeowners-cleanup",
                "current CODEOWNERS pattern resolves to a missing path and is not "
                "listed as a cleanup target",
                pattern,
            )
        )

    for pattern in sorted(set(codeowners_patterns) & set(cleanup_targets)):
        findings.append(
            Finding(
                "blocker" if fail_closed_codeowners else "advisory",
                "codeowners-cleanup",
                "current CODEOWNERS still contains a Phase 2.8 cleanup target",
                pattern,
            )
        )

    if strict_current_codeowners:
        for owner, mapping in sorted(mappings.items()):
            for pattern in mapping.get("target_codeowners_patterns", []):
                if pattern not in codeowners_patterns:
                    findings.append(
                        Finding(
                            "blocker",
                            "current-codeowners",
                            "target pattern is not present in current CODEOWNERS",
                            f"{owner}: {pattern}",
                        )
                    )
    return findings


def _check_ruleset_targets(contract: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []
    tiers = {str(item.get("id", "")): item for item in contract.get("ruleset_tier", [])}
    missing = sorted(REQUIRED_RULESET_TIERS - set(tiers))
    if missing:
        findings.append(
            Finding(
                "blocker", "ruleset-tiers", "missing required ruleset tiers", ", ".join(missing)
            )
        )
    text = DEFAULT_RULESET.read_text(encoding="utf-8") if DEFAULT_RULESET.exists() else ""
    for needle in (
        "require_pull_request: true",
        "require_code_owner_review: true",
        "Fast PR / Gate",
        "Standard PR / Gate",
    ):
        if needle not in text:
            findings.append(
                Finding("blocker", "ruleset-current-evidence", "ruleset evidence missing", needle)
            )
    protected = tiers.get("protected-branch-restrictions", {})
    requirements = "\n".join(protected.get("requirements", []))
    if "force-push" not in requirements or "branch deletion" not in requirements:
        findings.append(
            Finding(
                "blocker",
                "ruleset-tiers",
                "protected-branch-restrictions must target force-push and delete controls",
            )
        )
    return findings


def _check_workflow_permissions(contract: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []
    policy = contract.get("ci_permissions", {})
    if policy.get("default_top_level_permissions") != "contents: read":
        findings.append(
            Finding(
                "blocker",
                "ci-permissions",
                "default_top_level_permissions must be contents: read",
                str(policy.get("default_top_level_permissions")),
            )
        )
    if not policy.get("top_level_write_permissions_forbidden"):
        findings.append(
            Finding("blocker", "ci-permissions", "top-level write permissions must be forbidden")
        )

    workflow_findings = check_workflow_policy.collect_findings(WORKSPACE_ROOT)
    for finding in workflow_findings:
        findings.append(
            Finding(
                "blocker",
                "workflow-policy",
                finding.message,
                str(finding.path.relative_to(WORKSPACE_ROOT)),
            )
        )

    actual_write_permissions = _workflow_write_permissions()
    contracted_write_permissions = _contracted_write_permissions(contract)
    for workflow_job, permissions in sorted(actual_write_permissions.items()):
        contracted = contracted_write_permissions.get(workflow_job, set())
        missing = sorted(permissions - contracted)
        if missing:
            findings.append(
                Finding(
                    "blocker",
                    "workflow-permissions",
                    "job-level write permission is not covered by workflow_write_permission",
                    f"{workflow_job[0]}:{workflow_job[1]} -> {', '.join(missing)}",
                )
            )

    for workflow_job, permissions in sorted(contracted_write_permissions.items()):
        actual = actual_write_permissions.get(workflow_job, set())
        stale = sorted(permissions - actual)
        if stale:
            findings.append(
                Finding(
                    "blocker",
                    "workflow-permissions",
                    "workflow_write_permission contract does not match current workflow",
                    f"{workflow_job[0]}:{workflow_job[1]} -> {', '.join(stale)}",
                )
            )

    jobs_with_id_token = {
        workflow_job
        for workflow_job, permissions in actual_write_permissions.items()
        if "id-token: write" in permissions
    }
    contracted_oidc_jobs = {
        (str(item.get("workflow", "")), str(item.get("job", "")))
        for item in contract.get("oidc_job", [])
    }
    for workflow_job in sorted(jobs_with_id_token - contracted_oidc_jobs):
        findings.append(
            Finding(
                "blocker",
                "oidc",
                "job uses id-token: write but has no exact oidc_job contract",
                f"{workflow_job[0]}:{workflow_job[1]}",
            )
        )
    for workflow_job in sorted(contracted_oidc_jobs - jobs_with_id_token):
        findings.append(
            Finding(
                "blocker",
                "oidc",
                "oidc_job contract does not match a current id-token: write job",
                f"{workflow_job[0]}:{workflow_job[1]}",
            )
        )
    return findings


def _check_release_contract(contract: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []
    generated_families = _generated_artifact_families()
    missing_families = sorted(REQUIRED_GENERATED_ARTIFACT_FAMILIES - generated_families)
    if missing_families:
        findings.append(
            Finding(
                "blocker",
                "generated-artifact-families",
                "missing required supply-chain generated artifact families",
                ", ".join(missing_families),
            )
        )
    release_phases = {
        str(item.get("phase", "")): item for item in contract.get("release_phase_gate", [])
    }
    for phase in ("dependency_lock_change", "release_candidate"):
        gate = release_phases.get(phase)
        if not gate:
            findings.append(
                Finding("blocker", "release-phases", "missing release phase gate", phase)
            )
            continue
        if not gate.get("sbom_required"):
            findings.append(Finding("blocker", "release-phases", "SBOM must be required", phase))
        family = str(gate.get("generated_artifact_family", ""))
        if family not in generated_families:
            findings.append(
                Finding(
                    "blocker",
                    "release-phases",
                    "release phase references unknown generated artifact family",
                    f"{phase}: {family}",
                )
            )
        if phase == "dependency_lock_change":
            missing_paths = sorted(DEPENDENCY_LOCK_PATHS - set(gate.get("trigger_paths", [])))
            if missing_paths:
                findings.append(
                    Finding(
                        "blocker",
                        "release-phases",
                        "dependency-lock gate must name lock/config trigger paths",
                        ", ".join(missing_paths),
                    )
                )
        if phase == "release_candidate":
            checks = set(gate.get("checks", []))
            missing_checks = sorted(RELEASE_CANDIDATE_REQUIRED_CHECKS - checks)
            if missing_checks:
                findings.append(
                    Finding(
                        "blocker",
                        "release-phases",
                        "release-candidate gate is missing required supply-chain checks",
                        ", ".join(missing_checks),
                    )
                )

    for artifact in contract.get("release_artifact_contract", []):
        artifact_type = str(artifact.get("artifact_type", "unknown"))
        for field in ("patterns", "owner", "provenance_target", "signing_target"):
            if not artifact.get(field):
                findings.append(
                    Finding(
                        "blocker",
                        "release-artifacts",
                        f"release artifact contract missing {field}",
                        artifact_type,
                    )
                )
        if not artifact.get("sbom_required"):
            findings.append(
                Finding("blocker", "release-artifacts", "artifact must require SBOM", artifact_type)
            )
        family = str(artifact.get("generated_artifact_family", ""))
        if family not in generated_families:
            findings.append(
                Finding(
                    "blocker",
                    "release-artifacts",
                    "artifact references unknown generated artifact family",
                    f"{artifact_type}: {family}",
                )
            )

    controls = {str(item.get("control", "")) for item in contract.get("control_crosswalk", [])}
    missing_controls = sorted(REQUIRED_CROSSWALK_CONTROLS - controls)
    if missing_controls:
        findings.append(
            Finding(
                "blocker",
                "control-crosswalk",
                "missing required Scorecard/SLSA-style crosswalk controls",
                ", ".join(missing_controls),
            )
        )
    for item in contract.get("control_crosswalk", []):
        control = str(item.get("control", ""))
        if control not in EXTERNAL_CONTROL_BASELINES:
            findings.append(
                Finding(
                    "blocker",
                    "control-crosswalk",
                    "control crosswalk is missing external baseline mapping",
                    control,
                )
            )
        if not str(item.get("reporting_artifact", "")).strip():
            findings.append(
                Finding(
                    "blocker",
                    "control-crosswalk",
                    "control crosswalk entry needs a reporting artifact",
                    control,
                )
            )
    if not build_crosswalk_report(contract)["controls"]:
        findings.append(Finding("blocker", "control-crosswalk", "crosswalk report is empty"))
    return findings


def _check_renovate_policy(contract: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []
    renovate = contract.get("renovate", {})
    current = str(renovate.get("current_path", ""))
    target = str(renovate.get("target_path", ""))
    if not current or not (WORKSPACE_ROOT / current).exists():
        findings.append(
            Finding("blocker", "renovate", "current Renovate config is missing", current)
        )
    if target != ".github/renovate.json":
        findings.append(
            Finding(
                "blocker",
                "renovate",
                "target Renovate placement must be .github/renovate.json",
                target,
            )
        )
    if current != target:
        findings.append(
            Finding(
                "blocker",
                "renovate",
                "current Renovate placement must match the canonical target",
                f"{current} != {target}",
            )
        )
    if (WORKSPACE_ROOT / "renovate.json").exists():
        findings.append(
            Finding(
                "blocker",
                "renovate",
                "outer-root renovate.json is retired; use .github/renovate.json",
            )
        )
    if not str(renovate.get("fallback_policy", "")).strip():
        findings.append(Finding("blocker", "renovate", "fallback_policy is required"))
    if current:
        findings.extend(_check_renovate_match_file_names(WORKSPACE_ROOT / current))
    return findings


def _check_renovate_match_file_names(path: Path) -> list[Finding]:
    if not path.exists():
        return []
    findings: list[Finding] = []
    try:
        renovate = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [
            Finding(
                "blocker",
                "renovate",
                "Renovate config must be valid JSON",
                f"{path}: {exc}",
            )
        ]

    match_file_names = {
        str(name)
        for rule in renovate.get("packageRules", [])
        for name in rule.get("matchFileNames", [])
    }
    retired = sorted(RETIRED_RENOVATE_MATCH_FILE_NAMES & match_file_names)
    if retired:
        findings.append(
            Finding(
                "blocker",
                "renovate",
                "Renovate matchFileNames references retired workspace paths",
                ", ".join(retired),
            )
        )
    for name in sorted(match_file_names):
        if not (WORKSPACE_ROOT / name).exists():
            findings.append(
                Finding(
                    "blocker",
                    "renovate",
                    "Renovate matchFileNames path does not exist",
                    name,
                )
            )
    return findings


def _codeowners_patterns() -> set[str]:
    patterns: set[str] = set()
    if not DEFAULT_CODEOWNERS.exists():
        return patterns
    for line in DEFAULT_CODEOWNERS.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        patterns.add(stripped.split()[0])
    return patterns


def _missing_or_retired_codeowners_patterns(patterns: set[str]) -> set[str]:
    missing: set[str] = set()
    for pattern in patterns:
        if _pattern_exists(pattern):
            continue
        missing.add(pattern)
    return missing


def _pattern_exists(pattern: str) -> bool:
    normalized = pattern.lstrip("/")
    if normalized.endswith("/**"):
        normalized = normalized[:-3]
    elif normalized.endswith("*"):
        normalized = normalized[:-1]
    if not normalized:
        return True
    return (WORKSPACE_ROOT / normalized).exists()


def _package_owner_records() -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    package_dir = REPO_ROOT / "architecture" / "packages"
    for path in sorted(package_dir.glob("*.toml")):
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        entries = data.get("package", [])
        if isinstance(entries, dict):
            entries = [entries]
        for item in entries:
            module = str(item.get("module") or item.get("name") or "").strip()
            owner = str(item.get("owner") or "").strip()
            if module and owner:
                records.append(
                    {"module": module, "owner": owner, "source": str(path.relative_to(REPO_ROOT))}
                )

    boundaries = tomllib.loads((REPO_ROOT / "architecture/package_boundaries.toml").read_text())
    for item in boundaries.get("package", []):
        records.append(
            {
                "module": str(item.get("module", "")),
                "owner": str(item.get("owner", "")),
                "source": "architecture/package_boundaries.toml",
            }
        )

    layout = tomllib.loads((REPO_ROOT / "architecture/package_layout.toml").read_text())
    for item in layout.get("package", []):
        if item.get("current_status") == "removed":
            continue
        name = str(item.get("name", ""))
        records.append(
            {
                "module": name if name.startswith("polisyos.") else f"polisyos.{name}",
                "owner": str(item.get("owner", "")),
                "source": "architecture/package_layout.toml",
            }
        )

    public_surface = tomllib.loads((REPO_ROOT / "architecture/public_surface.toml").read_text())
    for item in public_surface.get("package", []):
        records.append(
            {
                "module": str(item.get("module", "")),
                "owner": str(item.get("owner", "")),
                "source": "architecture/public_surface.toml",
            }
        )
    return [record for record in records if record["module"] and record["owner"]]


def _public_stable_modules() -> set[str]:
    public_surface = tomllib.loads((REPO_ROOT / "architecture/public_surface.toml").read_text())
    return {
        str(item.get("module", ""))
        for item in public_surface.get("package", [])
        if item.get("classification") == "public_stable"
    }


def _public_surface_owner(module: str) -> str:
    public_surface = tomllib.loads((REPO_ROOT / "architecture/public_surface.toml").read_text())
    for item in public_surface.get("package", []):
        if item.get("module") == module:
            return str(item.get("owner", ""))
    return ""


def _module_codeowners_pattern(module: str) -> str:
    if not module.startswith("polisyos."):
        return ""
    suffix = "/".join(module.split(".")[1:])
    return f"/policy-engine/src/polisyos/{suffix}/**"


def _pattern_list_covers(patterns: list[str], expected: str) -> bool:
    expected_path = expected.removesuffix("**")
    for pattern in patterns:
        if pattern == expected:
            return True
        if pattern.endswith("/**") and expected_path.startswith(pattern.removesuffix("**")):
            return True
    return False


def _generated_artifact_families() -> set[str]:
    data = tomllib.loads((REPO_ROOT / "architecture/generated_artifacts.toml").read_text())
    return {str(item.get("id", "")) for item in data.get("family", [])}


def _mapped_phase_gates(release_phase: str, phases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for phase in phases:
        name = str(phase.get("phase", ""))
        if name and name in release_phase:
            selected.append(
                {
                    "phase": name,
                    "checks": phase.get("checks", []),
                    "sbom_required": bool(phase.get("sbom_required", False)),
                    "provenance_required": bool(phase.get("provenance_required", False)),
                    "signed_artifacts_required": bool(
                        phase.get("signed_artifacts_required", False)
                    ),
                    "generated_artifact_family": phase.get("generated_artifact_family", ""),
                }
            )
    return selected


def _workflow_write_permissions() -> dict[tuple[str, str], set[str]]:
    write_permissions: dict[tuple[str, str], set[str]] = {}
    for path in sorted((WORKSPACE_ROOT / ".github" / "workflows").glob("*.yml")):
        rel = str(path.relative_to(WORKSPACE_ROOT))
        for job, permissions in _job_permissions(path).items():
            writes = {
                f"{permission}: write"
                for permission, level in permissions.items()
                if level == "write"
            }
            if writes:
                write_permissions[(rel, job)] = writes
    return write_permissions


def _contracted_write_permissions(contract: dict[str, Any]) -> dict[tuple[str, str], set[str]]:
    permissions: dict[tuple[str, str], set[str]] = {}
    for item in contract.get("workflow_write_permission", []):
        workflow_job = (str(item.get("workflow", "")), str(item.get("job", "")))
        permissions[workflow_job] = {
            str(permission)
            for permission in item.get("permissions", [])
            if str(permission).endswith(": write")
        }
    return permissions


def _job_permissions(path: Path) -> dict[str, dict[str, str]]:
    text = path.read_text(encoding="utf-8")
    jobs: dict[str, dict[str, str]] = {}
    current_job = ""
    in_jobs = False
    collecting_permissions = False

    for line in text.splitlines():
        if line == "jobs:":
            in_jobs = True
            current_job = ""
            collecting_permissions = False
            continue
        if not in_jobs:
            continue

        job_match = JOB_RE.match(line)
        if job_match:
            current_job = job_match.group("job")
            jobs.setdefault(current_job, {})
            collecting_permissions = False
            continue

        if not current_job:
            continue

        permissions_match = JOB_PERMISSIONS_RE.match(line)
        if permissions_match:
            inline = permissions_match.group("inline")
            jobs[current_job] = _parse_inline_permissions(inline)
            collecting_permissions = not inline.strip()
            continue

        if collecting_permissions:
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            indent = len(line) - len(line.lstrip(" "))
            if indent <= 4:
                collecting_permissions = False
                continue
            permission_match = PERMISSION_ITEM_RE.match(line)
            if permission_match:
                jobs[current_job][permission_match.group("permission")] = (
                    permission_match.group("level")
                )
    return jobs


def _parse_inline_permissions(inline: str) -> dict[str, str]:
    normalized = inline.split("#", 1)[0].strip()
    if not normalized:
        return {}
    if normalized in {"read-all", "write-all"}:
        return {"*": normalized.removesuffix("-all")}
    if normalized == "{}":
        return {}
    if normalized.startswith("{") and normalized.endswith("}"):
        return {
            match.group("permission"): match.group("level")
            for match in INLINE_PERMISSION_RE.finditer(normalized[1:-1])
        }
    return {}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate control-plane and supply-chain contracts."
    )
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument(
        "--strict-current-codeowners",
        action="store_true",
        help="Fail if target CODEOWNERS patterns are not already present in current CODEOWNERS.",
    )
    parser.add_argument("--output-json", type=Path)
    parser.add_argument(
        "--crosswalk-json",
        type=Path,
        help=(
            "Write the external Scorecard/SLSA-style supply-chain control "
            "crosswalk report."
        ),
    )
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    findings = validate_contract(
        contract_path=args.contract.resolve(),
        strict_current_codeowners=args.strict_current_codeowners,
    )
    payload = {
        "status": "failed" if blockers(findings) else "passed",
        "blocker_count": len(blockers(findings)),
        "finding_count": len(findings),
        "findings": [finding.__dict__ for finding in findings],
    }
    if args.output_json is not None:
        _write_json(args.output_json, payload)
    if args.crosswalk_json is not None:
        _write_json(args.crosswalk_json, build_crosswalk_report(load_contract(args.contract)))

    if findings:
        for finding in findings:
            sys.stdout.write(f"{finding.render()}\n")
    if blockers(findings):
        return 1
    sys.stdout.write("Control-plane and supply-chain contract passed.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
