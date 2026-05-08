# ruff: noqa: S101, S603, S607

from __future__ import annotations

import json
import subprocess
import tomllib
from pathlib import Path

from tools.quality.validation import control_plane_supply_chain_contracts as contracts

REPO_ROOT = Path(__file__).resolve().parents[3]
WORKSPACE_ROOT = REPO_ROOT.parent
CONTRACT_PATH = REPO_ROOT / "architecture" / "control_plane_supply_chain.toml"
CROSSWALK_REPORT_PATH = REPO_ROOT / "docs/archive/reports/supply-chain-control-crosswalk.json"
CODEOWNERS_PATH = WORKSPACE_ROOT / ".github" / "CODEOWNERS"
RETIRED_CODEOWNERS_PATTERNS = {
    "/README.md",
    "/SECURITY.md",
    "/SUPPORT.md",
    "/CODE_OF_CONDUCT.md",
    "/lefthook.yml",
    "/design/**",
    "/policy-engine/baseline/**",
    "/policy-engine/packs/**",
}


def test_phase28_control_plane_contract_passes_after_path_prefix_cleanup() -> None:
    findings = contracts.validate_contract(contract_path=CONTRACT_PATH)

    assert contracts.blockers(findings) == []
    assert findings == []


def test_phase28_current_codeowners_matches_active_owner_projection() -> None:
    data = _read_contract()
    patterns = _read_codeowners_patterns()
    target_patterns = {
        pattern
        for mapping in data["owner_mapping"]
        for pattern in mapping.get("target_codeowners_patterns", [])
    }

    assert data["codeowners_gate"]["mode"] == "fail_closed"
    assert "codeowners_cleanup_target" not in data
    assert RETIRED_CODEOWNERS_PATTERNS.isdisjoint(patterns)
    assert target_patterns <= patterns


def test_phase28_owner_mappings_cover_package_owners_and_public_stable_modules() -> None:
    data = _read_contract()
    mappings = {item["owner"]: item for item in data["owner_mapping"]}

    package_boundaries = _read_toml(REPO_ROOT / "architecture/packages/boundaries.toml")
    package_owners = {item["owner"] for item in package_boundaries["package"]}
    assert package_owners <= set(mappings)

    public_surface = _read_toml(REPO_ROOT / "architecture/public_surface/contract.toml")
    stable_modules = {
        item["module"]
        for item in public_surface["package"]
        if item["classification"] == "public_stable"
    }
    covered_modules = {
        module for mapping in mappings.values() for module in mapping.get("covers_modules", [])
    }
    assert stable_modules <= covered_modules
    assert (
        "/policy-engine/src/polisyos/common/**"
        in mappings["team-core"]["target_codeowners_patterns"]
    )
    assert (
        "/policy-engine/src/polisyos/scholar/**"
        in mappings["team-scholar"]["target_codeowners_patterns"]
    )


def test_phase28_ruleset_and_ci_identity_targets_are_explicit() -> None:
    data = _read_contract()
    tiers = {item["id"]: item for item in data["ruleset_tier"]}
    assert {
        "required-review",
        "code-owner-review",
        "fast-pr-checks",
        "release-gate-checks",
        "protected-branch-restrictions",
    } <= set(tiers)
    assert tiers["fast-pr-checks"]["required_status_checks"] == [
        "Fast PR / Gate",
        "Standard PR / Gate",
    ]
    assert "force-push" in "\n".join(tiers["protected-branch-restrictions"]["requirements"])
    assert "branch deletion" in "\n".join(tiers["protected-branch-restrictions"]["requirements"])

    oidc_jobs = {(item["workflow"], item["job"]) for item in data["oidc_job"]}
    assert (
        ".github/workflows/release.yml",
        "sign-artifacts",
    ) in oidc_jobs
    assert (
        ".github/workflows/release.yml",
        "attest-artifacts",
    ) in oidc_jobs
    assert (".github/workflows/docs-pages.yml", "deploy") in oidc_jobs


def test_phase59_workflow_write_permissions_are_exact_job_scope() -> None:
    data = _read_contract()
    expected_writes = contracts._contracted_write_permissions(data)
    actual_writes = contracts._workflow_write_permissions()

    assert actual_writes == expected_writes
    assert {
        workflow_job
        for workflow_job, permissions in actual_writes.items()
        if "id-token: write" in permissions
    } == {
        (".github/workflows/docs-pages.yml", "deploy"),
        (".github/workflows/release.yml", "sign-artifacts"),
        (".github/workflows/release.yml", "attest-artifacts"),
    }


def test_phase28_release_artifacts_tie_to_sbom_provenance_and_generated_contracts() -> None:
    data = _read_contract()
    artifacts = {item["artifact_type"]: item for item in data["release_artifact_contract"]}
    assert {
        "python-wheel",
        "python-sdist",
        "runtime-dashboard-bundle",
        "checksum-manifest",
    } <= set(artifacts)

    generated = _read_toml(REPO_ROOT / "architecture/generated_artifacts.toml")
    generated_families = {item["id"] for item in generated["family"]}
    assert "release-sbom" in generated_families
    assert "supply-chain-control-crosswalk" in generated_families
    for artifact in artifacts.values():
        assert artifact["sbom_required"] is True
        assert artifact["generated_artifact_family"] == "release-sbom"
        assert artifact["provenance_target"]
        assert artifact["signing_target"]

    phases = {item["phase"]: item for item in data["release_phase_gate"]}
    assert phases["dependency_lock_change"]["sbom_required"] is True
    assert phases["release_candidate"]["provenance_required"] is True
    assert phases["release_candidate"]["signed_artifacts_required"] is True
    assert {
        ".github/renovate.json",
        "policy-engine/uv.lock",
        "policy-engine/pnpm-lock.yaml",
    } <= set(phases["dependency_lock_change"]["trigger_paths"])


def test_phase59_supply_chain_crosswalk_report_matches_contract() -> None:
    data = _read_contract()
    report = json.loads(CROSSWALK_REPORT_PATH.read_text(encoding="utf-8"))
    generated_report = contracts.build_crosswalk_report(data)

    assert report == generated_report
    assert report["status"] == "policy_defined"
    assert {item["control"] for item in report["controls"]} >= {
        "OpenSSF Scorecard",
        "SLSA provenance",
        "SBOM",
        "Signed artifacts",
    }
    assert all(item["external_control_refs"] for item in report["controls"])
    assert any(
        item["control"] == "OpenSSF Scorecard"
        and item["reporting_artifact"] == "nightly-scorecard"
        for item in report["controls"]
    )


def test_phase28_renovate_placement_follows_split_root_decision() -> None:
    data = _read_contract()
    renovate = data["renovate"]

    assert renovate["current_path"] == ".github/renovate.json"
    assert (WORKSPACE_ROOT / renovate["current_path"]).exists()
    assert renovate["target_path"] == ".github/renovate.json"
    assert renovate["preferred_target"] == ".github/renovate.json"
    assert "archived" in renovate["fallback_policy"]
    assert not (WORKSPACE_ROOT / "renovate.json").exists()


def test_phase7_renovate_match_file_names_resolve_to_current_manifests() -> None:
    data = _read_contract()
    renovate_path = WORKSPACE_ROOT / data["renovate"]["current_path"]
    renovate = json.loads(renovate_path.read_text(encoding="utf-8"))
    match_file_names = {
        name
        for rule in renovate.get("packageRules", [])
        for name in rule.get("matchFileNames", [])
    }

    retired_dashboard_manifest = "/".join(
        ("policy-engine", "frontend", "runtime-dashboard", "package.json")
    )

    assert retired_dashboard_manifest not in match_file_names
    assert {
        "policy-engine/apps/runtime-dashboard/package.json",
        "policy-engine/apps/runtime-reference-shell/package.json",
        "policy-engine/packages/cli/package.json",
        "policy-engine/packages/runtime-api-client/package.json",
    } <= match_file_names
    assert all((WORKSPACE_ROOT / name).exists() for name in match_file_names)


def test_phase28_validation_cli_exits_zero_without_findings(tmp_path: Path) -> None:
    crosswalk_report = tmp_path / "supply-chain-control-crosswalk.json"
    result = subprocess.run(
        [
            "uv",
            "run",
            "python",
            "tools/quality/validation/control_plane_supply_chain_contracts.py",
            "--crosswalk-json",
            str(crosswalk_report),
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    assert "Control-plane and supply-chain contract passed." in result.stdout
    assert crosswalk_report.exists()


def _read_contract() -> dict:
    return _read_toml(CONTRACT_PATH)


def _read_codeowners_patterns() -> set[str]:
    patterns: set[str] = set()
    for line in CODEOWNERS_PATH.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            patterns.add(stripped.split()[0])
    return patterns


def _read_toml(path: Path) -> dict:
    return tomllib.loads(path.read_text(encoding="utf-8"))
