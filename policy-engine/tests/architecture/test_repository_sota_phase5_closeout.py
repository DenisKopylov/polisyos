from __future__ import annotations

import datetime as dt
import subprocess
import tomllib
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKSPACE_ROOT = REPO_ROOT.parent


def test_phase5_repository_sota_closeout_command_is_registered() -> None:
    from tools.registry import TOOL_SPECS_BY_KEY

    spec = TOOL_SPECS_BY_KEY[("workspace", "repository-sota-closeout")]

    assert spec.module == "tools.devx.workspace.repository_sota_closeout"
    assert spec.callable_name == "main"
    assert spec.status.value == "active"


def test_phase5_gate_registry_is_fail_closed_and_evidence_backed() -> None:
    contract = _read_toml("architecture/repository_sota_gates.toml")
    header = contract["repository_sota_gates"]
    gates = {gate["id"]: gate for gate in contract["gate"]}

    assert header["status"] == "fail_closed"
    assert _contract_path_exists(header["closeout_report"])
    assert header["gate_command"] == "uv run polisyos-tools workspace repository-sota-closeout"

    assert {
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
    } <= set(gates)

    for gate in gates.values():
        assert gate["mode"] == "fail_closed", gate["id"]
        assert gate["owner"], gate["id"]
        assert gate["command"], gate["id"]
        assert _contract_path_exists(gate["evidence"]), gate["id"]
        if gate.get("exceptions"):
            assert _contract_path_exists(gate["exceptions"]), gate["id"]
    assert (
        gates["docs-freshness"]["command"]
        == "uv run polisyos-tools workspace repository-sota-closeout --skip-generated-checks"
    )


def test_phase5_remaining_exceptions_are_owner_approved_and_time_bounded() -> None:
    today = dt.date.today()

    imports = _read_toml("architecture/imports/exceptions.toml")["exception"]
    for exception in imports:
        assert exception["id"]
        assert exception["owner"]
        assert exception["reason"]
        assert exception["source_glob"]
        assert _date(exception["expires"]) >= today

    complexity = _read_toml("architecture/complexity_exceptions.toml")
    assert complexity["complexity_exceptions"]["status"] == "active"
    for exception in complexity["exception"]:
        path = exception["path"]
        assert "*" not in path and "?" not in path and "[" not in path
        assert (REPO_ROOT / path).exists(), path
        assert exception["owner"]
        assert exception["reason"]
        assert exception["remediation"]
        assert _date(exception["expires"]) >= today

    shims = _read_toml("architecture/shims.toml")["shim"]
    for shim in shims:
        assert shim["id"]
        assert shim["owner"]
        assert shim["reason"]
        assert shim["target_path"]
        assert shim["issue"]
        assert _date(shim["sunset_date"]) >= today
        assert _contract_path_exists(shim["target_path"]), shim["id"]
        if shim["type"] == "wrapper_only":
            assert _contract_path_exists(shim["source_path"]), shim["id"]


def test_phase5_ops_security_release_and_observability_modes_are_fail_closed() -> None:
    ops = _read_toml("architecture/ops_baselines.toml")
    for baseline in ops["baseline"]:
        assert baseline["mode"] == "fail_closed", baseline["id"]

    assert "mode: fail_closed" in (REPO_ROOT / "ops/observability/otel/baseline.yaml").read_text(
        encoding="utf-8"
    )
    for path, table in {
        "ops/security/secrets-baseline.toml": "secrets_baseline",
        "ops/release/commit-policy.toml": "commit_policy",
        "ops/release/release-fragment-policy.toml": "release_fragments",
        "ops/runtime/runtime-contracts.toml": "runtime_contracts",
        "ops/migrations/migration-contracts.toml": "migration_contracts",
    }.items():
        assert _read_toml(path)[table]["mode"] == "fail_closed"

    secrets = _read_toml("ops/security/secrets-baseline.toml")["secrets_baseline"]
    for config_path in secrets["config_paths"]:
        assert _contract_path_exists(config_path)
    assert secrets["baseline_commands"]

    sbom = _read_toml("ops/security/sbom.toml")["sbom"]
    for input_path in sbom["inputs"]:
        assert _contract_path_exists(input_path), input_path

    security_readme = (REPO_ROOT / "ops/security/README.md").read_text(encoding="utf-8")
    assert "report-only" not in security_readme
    commit_policy = _read_toml("ops/release/commit-policy.toml")["commit_policy"]
    assert "report-only" not in commit_policy["evidence_policy"]


def test_phase5_ci_precommit_docs_and_command_registry_are_wired() -> None:
    for path in (
        REPO_ROOT / ".pre-commit-config.yaml",
        WORKSPACE_ROOT / ".github/workflows/abi.yml",
        REPO_ROOT / "ops/ci/templates/workflows/arch.yml",
    ):
        assert "repository-sota-closeout" in path.read_text(encoding="utf-8")

    closeout = REPO_ROOT / "docs/plans/accepted/REPOSITORY_SOTA_PHASE_5_CLOSEOUT.md"
    assert closeout.exists()
    assert "repository-sota-closeout" in closeout.read_text(encoding="utf-8")

    for path in (
        "docs/plans/accepted/REPOSITORY_SOTA_PLAN.md",
        "docs/reference/repository-topology.md",
        "docs/reference/quality-gates.md",
        "docs/reference/repository-hygiene.md",
        "docs/reference/contributor-start-here.md",
        "docs/adr/README.md",
        "docs/plans/README.md",
        "docs/reference/tools.md",
    ):
        assert "repository-sota-closeout" in (REPO_ROOT / path).read_text(encoding="utf-8")

    mkdocs = (REPO_ROOT / "mkdocs.yml").read_text(encoding="utf-8")
    for nav_path in (
        "reference/frontend/workspace-contract.md",
        "reference/data-lake-policy.md",
        "reference/local-runtime-state.md",
        "reference/operations/ops-baselines.md",
    ):
        assert nav_path in mkdocs


def test_phase5_contract_only_closeout_gate_passes() -> None:
    subprocess.run(
        [
            "uv",
            "run",
            "polisyos-tools",
            "workspace",
            "repository-sota-closeout",
            "--contract-only",
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )


def _read_toml(path: str) -> dict[str, Any]:
    return tomllib.loads((REPO_ROOT / path).read_text(encoding="utf-8"))


def _contract_path_exists(path: str) -> bool:
    if any(char in path for char in "*?["):
        return bool(list(REPO_ROOT.glob(path)))
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate.exists()
    return (REPO_ROOT / candidate).exists()


def _date(value: str) -> dt.date:
    return dt.date.fromisoformat(value)
