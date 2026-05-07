from __future__ import annotations

import re
import tomllib
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_phase1_6_runtime_state_layout_defines_schema_cas_and_migration_slots() -> None:
    local = _read_toml("architecture/local_runtime_state.toml")
    layout = _read_toml("architecture/runtime_state_layout.toml")

    assert local["local_runtime_state"]["layout_contract"] == "architecture/runtime_state_layout.toml"
    assert layout["runtime_state_layout"]["schema_document"] == ".polisyos/SCHEMA.md"
    assert layout["runtime_state_layout"]["status"] in {"contract_only", "active"}

    schema = layout["schema_md_contract"]
    for required in (
        "Purpose",
        "Owner And Contact",
        "Allowed Directory Layout",
        "File Naming",
        "Formats",
        "Retention",
        "Backup Policy",
        "Safe Cleanup",
        "Promotion Rules",
        "Migration Slots",
    ):
        assert required in schema["required_sections"]

    cas = layout["cas_normalization"]
    assert cas["canonical_path"] == ".polisyos/cas"
    assert cas["cache_path"] == ".polisyos/cas/_cache"
    assert cas["validation_path"] == ".polisyos/cas/_readme_check"
    assert ".polisyos/artifacts" in cas["legacy_cache_paths"]

    slots = {slot["id"]: slot for slot in layout["state_slot"]}
    assert {
        "runs",
        "reports",
        "audits",
        "cas",
        "cas_cache",
        "cas_readme_check",
        "provider_verification",
        "idempotency",
        "decision_validity",
        "search_registry",
        "production_data",
        "persisted_local_state",
    } <= set(slots)

    for slot in slots.values():
        for field in (
            "paths",
            "owner",
            "purpose",
            "naming",
            "formats",
            "retention_class",
            "default_retention_days",
            "backup_policy",
            "safe_cleanup_command",
            "promotion_rule",
            "migration_class",
            "migration_slot",
        ):
            assert slot[field], (slot["id"], field)

    migration_slots = {slot["id"]: slot for slot in layout["migration_slot"]}
    assert {
        "audit",
        "idempotency",
        "decision_validity",
        "search_registry",
        "provider_verification",
        "persisted_local_state",
    } <= set(migration_slots)
    assert {slot["class"] for slot in migration_slots.values()} == {"runtime_state"}


def test_phase1_6_runbook_coverage_maps_all_current_alerts() -> None:
    contract = _read_toml("architecture/runbook_coverage.toml")

    header = contract["runbook_coverage"]
    assert header["ops_organization_decision"] == "invert_to_ops_components"
    assert header["component_bundle_root"] == "ops/components"

    components = {item["component"]: item for item in contract["component_contract"]}
    assert {
        "core",
        "runtime",
        "scientist",
        "foundry",
        "fabric",
        "data_forge",
        "lex",
        "scholar",
        "security",
        "calibration",
    } <= set(components)

    for component in components.values():
        for field in ("owner", "runbooks", "alerts", "dashboards", "escalation"):
            assert field in component, (component["component"], field)
        for runbook in component["runbooks"]:
            assert _path_exists(runbook), (component["component"], runbook)

    mappings = {item["alert"]: item for item in contract["alert_mapping"]}
    alert_names = _prometheus_alert_names()
    assert alert_names <= set(mappings)

    for alert in alert_names:
        mapping = mappings[alert]
        assert mapping["component"] in components, alert
        assert mapping.get("runbooks") or mapping.get("exception_reason"), alert
        for runbook in mapping.get("runbooks", []):
            assert _path_exists(runbook), (alert, runbook)


def test_phase1_6_component_observability_records_slo_expectations() -> None:
    contract = _read_toml("architecture/component_observability.toml")
    components = {item["component"]: item for item in contract["component_contract"]}

    required_public_stable = {"core", "ir", "foundry", "lex", "scholar"}
    explicit_exceptions = {"berl", "ddm", "calibration"}
    assert required_public_stable <= set(components)
    assert explicit_exceptions <= set(components)

    for component in components.values():
        for field in (
            "owner",
            "slo_file",
            "slo_status",
            "prometheus_rules",
            "grafana_dashboard",
            "trace_context_keys",
            "log_context_keys",
            "release_gate",
        ):
            assert field in component, (component["component"], field)
        assert component["slo_status"] in {"present", "required_missing", "exception"}
        if component["slo_status"] == "present":
            assert _path_exists(component["slo_file"]), component["component"]
        if component["slo_status"] == "exception":
            assert component["exception_reason"], component["component"]
            assert component["exception_expires"], component["component"]
        for rule in component["prometheus_rules"]:
            assert _path_exists(rule), (component["component"], rule)
        if component["grafana_dashboard"]:
            assert _path_exists(component["grafana_dashboard"]), component["component"]


def test_phase1_6_migration_classes_and_release_gates_are_declared() -> None:
    migrations = _read_toml("ops/migrations/migration-contracts.toml")
    classes = {item["id"]: item for item in migrations["migration_class"]}

    assert {"db", "runtime_state", "api_schemas", "ir"} == set(classes)
    assert migrations["migration_contracts"]["target_roots"] == [
        "ops/migrations/db",
        "ops/migrations/runtime_state",
        "ops/migrations/api_schemas",
        "ops/migrations/ir",
    ]

    topology = _read_toml("ops/release/deployment-topology.toml")
    units = {item["id"]: item for item in topology["deployment_unit"]}
    assert {"control_plane", "runtime_api", "data_plane", "frontend", "python_packages"} <= set(
        units
    )

    gates = _read_toml("ops/release/promotion-gates.toml")
    gate_ids = {item["id"] for item in gates["gate"]}
    assert {
        "runtime_api_contract",
        "api_schema_compatibility",
        "db_migration_review",
        "runtime_state_migration_review",
        "ir_migration_review",
        "component_observability_coverage",
        "runbook_alert_coverage",
        "security_sbom_provenance",
    } <= gate_ids


def _read_toml(path: str) -> dict[str, Any]:
    return tomllib.loads((REPO_ROOT / path).read_text(encoding="utf-8"))


def _path_exists(path: str) -> bool:
    return (REPO_ROOT / path).exists()


def _prometheus_alert_names() -> set[str]:
    names: set[str] = set()
    for path in (REPO_ROOT / "ops/observability/prometheus").rglob("*.yml"):
        names.update(_alerts_in_text(path.read_text(encoding="utf-8")))
    for path in (REPO_ROOT / "ops/observability/prometheus").rglob("*.yaml"):
        names.update(_alerts_in_text(path.read_text(encoding="utf-8")))
    return names


def _alerts_in_text(text: str) -> set[str]:
    return set(re.findall(r"^\s*-\s+alert:\s+([A-Za-z0-9_]+)\s*$", text, re.MULTILINE))
