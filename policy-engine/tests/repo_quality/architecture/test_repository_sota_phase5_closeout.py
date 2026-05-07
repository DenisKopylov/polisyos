from __future__ import annotations

import datetime as dt
import re
import subprocess
import tomllib
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
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
        assert _has_issue_or_adr(exception)
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
        assert _has_issue_or_adr(exception)
        assert _date(exception["expires"]) >= today

    docs = _read_toml("architecture/docs_freshness_exceptions.toml")["docs_freshness_exceptions"]
    assert docs["owner"]
    assert docs["reason"]
    assert docs["issue"]
    assert _date(docs["expires"]) >= today

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


def test_phase6_5_exception_cleanup_registries_are_reviewable() -> None:
    today = dt.date.today()
    import_ids = {
        exception["id"]
        for exception in _read_toml("architecture/imports/exceptions.toml")["exception"]
    }
    import_docs = (REPO_ROOT / "architecture/imports/exceptions.md").read_text(encoding="utf-8")
    documented_ids = set(re.findall(r"`(E-\d{4}-\d{2}-[A-Z0-9-]+)`", import_docs))
    assert documented_ids == import_ids
    assert "issue/ADR" in import_docs

    dynamic_imports = _read_toml("architecture/dynamic_imports.toml")
    dynamic_header = dynamic_imports["dynamic_imports"]
    _assert_fields(
        dynamic_header,
        ("review_owner", "reviewed_at", "review_expires", "issue", "adr", "exception_policy"),
    )
    assert _date(dynamic_header["review_expires"]) >= today
    for pattern in dynamic_imports["pattern"]:
        _assert_fields(pattern, ("id", "owner", "source_file", "call", "verifier", "notes"))
        assert pattern.get("target") or pattern.get("allowed_targets"), pattern["id"]
        assert _contract_path_exists(pattern["source_file"]), pattern["id"]

    for package_contract in sorted((REPO_ROOT / "architecture/packages").glob("*.toml")):
        payload = tomllib.loads(package_contract.read_text(encoding="utf-8"))
        for exception in payload.get("exception", []):
            _assert_fields(exception, ("id", "owner", "kind", "reason", "sunset", "registry"))
            assert _has_issue_or_adr(exception), exception["id"]
            assert _date(exception["sunset"]) >= today
            assert _contract_path_exists(exception["registry"]), exception["id"]
        for sunset in payload.get("sunset", []):
            _assert_fields(sunset, ("id", "owner", "date", "condition"))
            assert _has_issue_or_adr(sunset), sunset["id"]
            assert _date(sunset["date"]) >= today

    test_topology = _read_toml("architecture/test_topology.toml")
    for exception in test_topology.get("source_package_exception", []):
        _assert_fields(
            exception, ("name", "source_path", "classification", "owner", "reason", "sunset")
        )
        assert _has_issue_or_adr(exception), exception["name"]
        assert _date(exception["sunset"]) >= today
        assert _contract_path_exists(exception["source_path"]), exception["name"]

    for override in _read_toml("architecture/static_analysis_overrides.toml")["override_scope"]:
        _assert_fields(override, ("id", "owner", "expectation", "sunset", "issue"))
        assert _date(override["sunset"]) >= today

    for budget in _read_toml("architecture/module_size_budget.toml")["budget"]:
        _assert_fields(budget, ("path", "owner", "strategy", "shrink_plan", "sunset"))
        assert _has_issue_or_adr(budget), budget["path"]
        assert _date(budget["sunset"]) >= today

    ratchets = _read_toml("architecture/test_ratchets.toml")
    for exception in ratchets.get("pytest_universe_exception", []):
        _assert_fields(exception, ("id", "owner", "reason", "expires", "issue"))
        assert _date(exception["expires"]) >= today
    for exception in ratchets.get("package_exception", []):
        _assert_fields(exception, ("id", "owner", "reason", "sunset_date", "issue"))
        assert _date(exception["sunset_date"]) >= today

    for component in _read_toml("architecture/component_observability.toml")["component_contract"]:
        if component.get("slo_status") == "exception":
            _assert_fields(
                component,
                ("owner", "exception_reason", "exception_expires", "exception_issue"),
            )
            assert _date(component["exception_expires"]) >= today

    for component in _read_toml("architecture/runbook_coverage.toml")["component_contract"]:
        if component.get("slo_exception"):
            _assert_fields(
                component,
                ("owner", "slo_exception_reason", "slo_exception_expires", "slo_exception_issue"),
            )
            assert _date(component["slo_exception_expires"]) >= today
            assert _contract_path_exists(component["slo_exception"]), component["component"]

    directory_contracts = _read_toml("architecture/directory_contracts.toml")
    assert directory_contracts["directory_contracts"]["exception_policy_issue"]
    accepted_fields = set(
        directory_contracts["local_documentation_requirement"]["accepted_exception_fields"]
    )
    assert {
        "owner",
        "reason",
        "sunset",
        "promotion_or_cleanup_target",
        "issue_or_adr",
    } <= accepted_fields

    generated_artifacts = _read_toml("architecture/generated_artifacts.toml")
    assert generated_artifacts["generated_artifacts"]["exception_policy"]
    assert generated_artifacts["generated_artifacts"]["exception_policy_issue"]
    for family in generated_artifacts["family"]:
        _assert_fields(
            family,
            (
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

    control_plane = _read_toml("architecture/control_plane_supply_chain.toml")
    for item in [control_plane["codeowners_gate"], *control_plane["owner_mapping"]]:
        if item.get("personal_repo_exception"):
            _assert_fields(
                item,
                (
                    "personal_repo_exception_reason",
                    "personal_repo_exception_expires",
                    "personal_repo_exception_issue",
                ),
            )
            assert _date(item["personal_repo_exception_expires"]) >= today


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

    mkdocs = (REPO_ROOT / "architecture/tooling/mkdocs/generated.yml").read_text(encoding="utf-8")
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


def _assert_fields(item: dict[str, Any], fields: tuple[str, ...]) -> None:
    for field in fields:
        assert item.get(field) not in (None, "", [], {}), field


def _has_issue_or_adr(item: dict[str, Any]) -> bool:
    return any(str(item.get(field, "")).strip() for field in ("issue", "adr", "adr_reference"))
