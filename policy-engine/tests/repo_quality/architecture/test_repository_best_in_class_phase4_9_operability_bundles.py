from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]

REQUIRED_BUNDLE_FILES = {
    "README.md",
    "slo.yaml",
    "alerts.yml",
    "dashboard.json",
    "runbooks.md",
    "runtime-contract.toml",
    "retention-policy.toml",
}

PHASE_4_9_COMPONENTS = {
    "core",
    "ir",
    "foundry",
    "lex",
    "scholar",
    "berl",
    "ddm",
    "calibration",
}


def test_phase4_9_component_bundles_cover_public_stable_and_required_components() -> None:
    index = _read_toml("ops/components/index.toml")
    header = index["component_bundles"]

    assert header["status"] == "active_draft"
    assert header["ops_organization_decision"] == "invert_to_ops_components"
    assert header["component_bundle_root"] == "ops/components"

    components = {item["id"]: item for item in index["component"]}
    public_stable = _public_stable_components()

    assert public_stable <= set(components)
    assert PHASE_4_9_COMPONENTS <= set(components)

    for component in components.values():
        bundle_path = REPO_ROOT / component["bundle"]
        assert bundle_path.is_dir(), component["id"]
        assert REQUIRED_BUNDLE_FILES <= {path.name for path in bundle_path.iterdir()}, component["id"]

        assert component["runbooks"], component["id"]
        for runbook in component["runbooks"]:
            assert _path_exists(runbook), (component["id"], runbook)

        assert component["slo_status"] in {"present", "exception"}, component["id"]
        assert _path_exists(component["slo_file"]), (component["id"], component["slo_file"])
        slo_text = (REPO_ROOT / component["slo_file"]).read_text(encoding="utf-8")
        if component["slo_status"] == "present":
            assert "objectives:" in slo_text, component["id"]
            assert "- name:" in slo_text, component["id"]
            assert "runbook:" in slo_text, component["id"]
        else:
            assert "status: exception" in slo_text, component["id"]
            assert component["exception_reason"], component["id"]
            assert component["exception_expires"], component["id"]

        for dashboard in component["dashboards"]:
            assert _path_exists(dashboard), (component["id"], dashboard)
        for contract in component["runtime_contracts"]:
            assert _path_exists(contract), (component["id"], contract)

        json.loads((bundle_path / "dashboard.json").read_text(encoding="utf-8"))
        _read_toml(str(Path(component["bundle"]) / "runtime-contract.toml"))
        _read_toml(str(Path(component["bundle"]) / "retention-policy.toml"))


def test_phase4_9_component_alert_bundles_map_every_prometheus_alert_to_a_runbook() -> None:
    mappings: dict[str, str] = {}

    for path in (REPO_ROOT / "ops/components").glob("*/alerts.yml"):
        current_alert: str | None = None
        for line in path.read_text(encoding="utf-8").splitlines():
            name_match = re.match(r"^\s*-\s+name:\s+([A-Za-z0-9_]+)\s*$", line)
            if name_match:
                current_alert = name_match.group(1)
                mappings[current_alert] = ""
                continue
            runbook_match = re.match(r"^\s+runbook:\s+(.+)\s*$", line)
            if current_alert and runbook_match:
                mappings[current_alert] = runbook_match.group(1).strip()

    alert_names = _prometheus_alert_names()
    assert alert_names <= set(mappings)

    for alert in alert_names:
        runbook = mappings[alert]
        assert runbook, alert
        assert _path_exists(runbook), (alert, runbook)


def test_phase4_9_observability_contract_has_no_missing_required_slos() -> None:
    contract = _read_toml("architecture/component_observability.toml")

    missing = [
        component["component"]
        for component in contract["component_contract"]
        if component["slo_status"] == "required_missing"
    ]

    assert missing == []


def _read_toml(path: str) -> dict[str, Any]:
    return tomllib.loads((REPO_ROOT / path).read_text(encoding="utf-8"))


def _path_exists(path: str) -> bool:
    return (REPO_ROOT / path).exists()


def _public_stable_components() -> set[str]:
    surface = _read_toml("architecture/public_surface.toml")
    components: set[str] = set()
    for package in surface["package"]:
        if package["classification"] == "public_stable":
            components.add(package["module"].removeprefix("polisyos."))
    return components


def _prometheus_alert_names() -> set[str]:
    names: set[str] = set()
    for path in (REPO_ROOT / "ops/observability/prometheus").rglob("*.yml"):
        names.update(_alerts_in_text(path.read_text(encoding="utf-8")))
    for path in (REPO_ROOT / "ops/observability/prometheus").rglob("*.yaml"):
        names.update(_alerts_in_text(path.read_text(encoding="utf-8")))
    return names


def _alerts_in_text(text: str) -> set[str]:
    return set(re.findall(r"^\s*-\s+alert:\s+([A-Za-z0-9_]+)\s*$", text, re.MULTILINE))
