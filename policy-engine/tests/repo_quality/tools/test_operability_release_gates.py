from __future__ import annotations

import datetime as dt
import tomllib
from pathlib import Path
from typing import Any

from tools.ops_runners.release import check_operability_release_gates as gates

REPO_ROOT = Path(__file__).resolve().parents[3]

REQUIRED_BUNDLE_FILES = {
    "README.md",
    "alerts.yml",
    "dashboard.json",
    "retention-policy.toml",
    "runbooks.md",
    "runtime-contract.toml",
    "slo.yaml",
}
PLAN_COMPLETION_TARGET = dt.date(2026, 5, 31)
MIN_EXCEPTION_EXPIRATION = PLAN_COMPLETION_TARGET + dt.timedelta(days=90)


def test_phase6_6_public_stable_bundles_are_complete_or_actioned() -> None:
    index = _read_toml(REPO_ROOT / "ops/components/index.toml")
    runbooks = _read_toml(REPO_ROOT / "architecture/runbook_coverage.toml")
    observability = _read_toml(REPO_ROOT / "architecture/component_observability.toml")
    header = index["component_bundles"]

    assert header["phase_6_6_completeness_gate"] == "fail_closed"
    assert header["phase_6_6_plan_completion_target"] == PLAN_COMPLETION_TARGET.isoformat()
    assert set(header["required_public_stable_bundle_files"]) == REQUIRED_BUNDLE_FILES

    components = {item["id"]: item for item in index["component"]}
    public_stable = {
        component_id
        for component_id, component in components.items()
        if component["classification"] == "public_stable"
    }
    assert {"common", "core", "fabric", "foundry", "ir", "lex", "runtime", "scientist"} <= (
        public_stable
    )

    for component_id in public_stable:
        bundle_path = REPO_ROOT / components[component_id]["bundle"]
        assert {path.name for path in bundle_path.iterdir()} >= REQUIRED_BUNDLE_FILES, component_id

    _assert_exception_registry_is_actioned(index["component"])
    _assert_exception_registry_is_actioned(observability["component_contract"])
    _assert_slo_exception_registry_is_actioned(runbooks["component_contract"])


def test_phase6_6_gate_fails_public_stable_missing_required_bundle_file(
    tmp_path: Path,
) -> None:
    repo_root = _write_minimal_operability_repo(
        tmp_path, slo_status="present", omit_bundle_file="dashboard.json"
    )

    _, findings = gates._check_operability(
        repo_root, current_date=dt.date(2026, 5, 8)
    )

    assert _finding(
        findings,
        check="operability-bundle-completeness",
        subject="core",
        detail="dashboard.json",
    )


def test_phase6_6_gate_fails_expired_slo_exception(tmp_path: Path) -> None:
    repo_root = _write_minimal_operability_repo(
        tmp_path,
        slo_status="exception",
        exception_expires="2026-05-01",
        exception_action_plan="Promote core to a standalone SLO bundle.",
        exception_action_due="2026-05-31",
    )

    _, findings = gates._check_operability(
        repo_root, current_date=dt.date(2026, 5, 8)
    )

    assert _finding(
        findings,
        check="operability-exception-policy",
        subject="core",
        message="exception expired",
    )


def test_phase6_6_gate_requires_action_plan_for_short_slo_exception(
    tmp_path: Path,
) -> None:
    repo_root = _write_minimal_operability_repo(
        tmp_path,
        slo_status="exception",
        exception_expires="2026-08-01",
        exception_action_plan="",
        exception_action_due="",
    )

    _, findings = gates._check_operability(
        repo_root, current_date=dt.date(2026, 5, 8)
    )

    assert _finding(
        findings,
        check="operability-exception-policy",
        subject="core",
        message="short exception must have an action plan due inside the plan window",
    )


def _assert_exception_registry_is_actioned(items: list[dict[str, Any]]) -> None:
    exceptions = [item for item in items if item.get("slo_status") == "exception"]
    assert exceptions
    for item in exceptions:
        subject = item.get("id", item.get("component"))
        for field in (
            "exception_owner",
            "exception_reason",
            "exception_expires",
            "exception_action_plan",
            "exception_action_due",
        ):
            assert item.get(field), (subject, field)
        expires = _date(str(item["exception_expires"]))
        action_due = _date(str(item["exception_action_due"]))
        assert expires >= MIN_EXCEPTION_EXPIRATION or action_due <= PLAN_COMPLETION_TARGET, subject


def _assert_slo_exception_registry_is_actioned(items: list[dict[str, Any]]) -> None:
    exceptions = [item for item in items if item.get("slo_exception")]
    assert exceptions
    for item in exceptions:
        for field in (
            "slo_exception_owner",
            "slo_exception_reason",
            "slo_exception_expires",
            "slo_exception_action_plan",
            "slo_exception_action_due",
        ):
            assert item.get(field), (item["component"], field)
        expires = _date(str(item["slo_exception_expires"]))
        action_due = _date(str(item["slo_exception_action_due"]))
        assert expires >= MIN_EXCEPTION_EXPIRATION or action_due <= PLAN_COMPLETION_TARGET, (
            item["component"]
        )


def _write_minimal_operability_repo(
    tmp_path: Path,
    *,
    slo_status: str,
    omit_bundle_file: str | None = None,
    exception_expires: str = "2026-08-01",
    exception_action_plan: str = "Replace the exception with a present component SLO.",
    exception_action_due: str = "2026-05-31",
) -> Path:
    repo_root = tmp_path / "repo"
    _write(
        repo_root / "architecture/public_surface/contract.toml",
        """
[public_surface]
version = 1

[[package]]
module = "polisyos.core"
classification = "public_stable"
""",
    )
    _write(
        repo_root / "architecture/runbook_coverage.toml",
        """
[runbook_coverage]
version = 2
phase_6_6_completeness_gate = "fail_closed"
phase_6_6_plan_window_start = "2026-05-07"
phase_6_6_plan_completion_target = "2026-05-31"
required_public_stable_bundle_files = [
  "README.md",
  "alerts.yml",
  "dashboard.json",
  "retention-policy.toml",
  "runbooks.md",
  "runtime-contract.toml",
  "slo.yaml",
]

[[component_contract]]
component = "core"
owner = "team-core"
runbooks = ["docs/runbooks/core.md"]
alerts = []
dashboards = ["ops/observability/grafana/dashboards/slo-overview.json"]
escalation = "team-core primary"
""",
    )
    exception_fields = ""
    slo_text = """
objectives:
  - name: availability
    runbook: docs/runbooks/core.md
"""
    if slo_status == "exception":
        exception_fields = f"""
exception_owner = "team-core"
exception_reason = "Core SLO is temporarily covered by dependent components."
exception_expires = "{exception_expires}"
exception_action_plan = "{exception_action_plan}"
exception_action_due = "{exception_action_due}"
"""
        slo_text = "status: exception\nreason: covered by dependent components\n"

    _write(
        repo_root / "architecture/component_observability.toml",
        f"""
[component_observability]
version = 2
phase_6_6_completeness_gate = "fail_closed"
phase_6_6_plan_window_start = "2026-05-07"
phase_6_6_plan_completion_target = "2026-05-31"
required_public_stable_bundle_files = [
  "README.md",
  "alerts.yml",
  "dashboard.json",
  "retention-policy.toml",
  "runbooks.md",
  "runtime-contract.toml",
  "slo.yaml",
]

[[component_contract]]
component = "core"
owner = "team-core"
slo_file = "ops/components/core/slo.yaml"
slo_status = "{slo_status}"
prometheus_rules = []
grafana_dashboard = "ops/observability/grafana/dashboards/slo-overview.json"
trace_context_keys = ["service.name"]
log_context_keys = ["request_id"]
release_gate = "core SLO gate"
{exception_fields}
""",
    )
    _write(
        repo_root / "ops/components/index.toml",
        f"""
[component_bundles]
version = 1
phase_6_6_completeness_gate = "fail_closed"
phase_6_6_plan_window_start = "2026-05-07"
phase_6_6_plan_completion_target = "2026-05-31"
required_public_stable_bundle_files = [
  "README.md",
  "alerts.yml",
  "dashboard.json",
  "retention-policy.toml",
  "runbooks.md",
  "runtime-contract.toml",
  "slo.yaml",
]

[[component]]
id = "core"
classification = "public_stable"
owner = "team-core"
bundle = "ops/components/core"
slo_status = "{slo_status}"
slo_file = "ops/components/core/slo.yaml"
runbooks = ["docs/runbooks/core.md"]
alerts = []
dashboards = ["ops/observability/grafana/dashboards/slo-overview.json"]
runtime_contracts = ["ops/components/core/runtime-contract.toml"]
retention_policy = "ops/components/core/retention-policy.toml"
{exception_fields}
""",
    )
    _write(repo_root / "docs/runbooks/core.md", "# Core runbook\n")
    _write(repo_root / "ops/observability/grafana/dashboards/slo-overview.json", "{}\n")
    (repo_root / "ops/observability/prometheus").mkdir(parents=True, exist_ok=True)

    bundle_files = {
        "README.md": "# Core\n",
        "alerts.yml": "alerts: []\n",
        "dashboard.json": "{}\n",
        "retention-policy.toml": "[retention_policy]\nowner = \"team-core\"\n",
        "runbooks.md": "# Core runbooks\n",
        "runtime-contract.toml": "[runtime_contract]\nowner = \"team-core\"\n",
        "slo.yaml": slo_text,
    }
    for filename, content in bundle_files.items():
        if filename == omit_bundle_file:
            continue
        _write(repo_root / "ops/components/core" / filename, content)
    return repo_root


def _finding(
    findings: list[gates.Finding],
    *,
    check: str,
    subject: str,
    message: str | None = None,
    detail: str | None = None,
) -> bool:
    return any(
        finding.check == check
        and finding.subject == subject
        and (message is None or finding.message == message)
        and (detail is None or detail in finding.detail)
        for finding in findings
    )


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.lstrip(), encoding="utf-8")


def _read_toml(path: Path) -> dict[str, Any]:
    return tomllib.loads(path.read_text(encoding="utf-8"))


def _date(value: str) -> dt.date:
    return dt.date.fromisoformat(value)
