from __future__ import annotations

import glob
import json
import re
import tomllib
from pathlib import Path
from typing import Any

import pytest
import yaml
from opentelemetry import metrics as otel_metrics
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader

from polisyos.core.observability import _metrics_registry_base as metrics_registry_base
from polisyos.core.observability.config import (
    MetricsExporterType,
    OTelConfig,
    ResourceConfig,
)
from polisyos.core.observability.metrics_parts import MetricsRegistry

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
    assert set(components) >= PHASE_4_9_COMPONENTS

    for component in components.values():
        bundle_path = REPO_ROOT / component["bundle"]
        assert bundle_path.is_dir(), component["id"]
        bundle_files = {path.name for path in bundle_path.iterdir()}
        assert bundle_files >= REQUIRED_BUNDLE_FILES, component["id"]

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


def test_default_prometheus_loads_every_component_declared_rule_source() -> None:
    loaded_sources = _prometheus_rule_sources_loaded_by_default(REPO_ROOT)
    declared_sources = _component_prometheus_rule_sources(REPO_ROOT)

    assert declared_sources <= loaded_sources
    assert all(path.is_file() for path in loaded_sources)
    for source in loaded_sources:
        payload = yaml.safe_load(source.read_text(encoding="utf-8"))
        assert isinstance(payload, dict), source
        assert payload.get("groups"), source


@pytest.mark.parametrize(
    "removed_rule_source_case",
    [
        ("ops/observability/prometheus/rules/mtls-rules.yaml",),
        ("ops/observability/prometheus/rules/scientist-alerts.yml",),
    ],
)
def test_default_rule_source_gate_detects_config_removal_while_file_and_declaration_remain(
    tmp_path: Path,
    removed_rule_source_case: tuple[str],
) -> None:
    removed_rule_source = removed_rule_source_case[0]
    config_path = REPO_ROOT / "ops/observability/prometheus/prometheus.yml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    configured_path = (
        f"/etc/prometheus/{Path(removed_rule_source).relative_to('ops/observability/prometheus')}"
    )
    config["rule_files"] = [path for path in config["rule_files"] if path != configured_path]
    mutated_config = tmp_path / "prometheus.yml"
    mutated_config.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")

    expected_source = (REPO_ROOT / removed_rule_source).resolve()
    assert expected_source.is_file()
    assert expected_source in _component_prometheus_rule_sources(REPO_ROOT)
    loaded_sources = _prometheus_rule_sources_loaded_by_default(
        REPO_ROOT,
        config_path=mutated_config,
    )

    assert expected_source not in loaded_sources
    assert _component_prometheus_rule_sources(REPO_ROOT) - loaded_sources == {expected_source}


def test_core_tenant_boundary_sli_names_the_metric_emitted_by_its_native_producer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reader = InMemoryMetricReader()
    provider = MeterProvider(metric_readers=[reader])
    config = OTelConfig(enabled=True, metrics_exporter=MetricsExporterType.NONE)
    monkeypatch.setattr(metrics_registry_base, "get_default_config", lambda: config)
    monkeypatch.setattr(
        metrics_registry_base,
        "get_resource_config",
        lambda _: ResourceConfig(service_name="polisyos-test", service_version="test"),
    )
    monkeypatch.setattr(otel_metrics, "get_meter", provider.get_meter)
    monkeypatch.setattr(otel_metrics, "set_meter_provider", lambda _: None)
    monkeypatch.setattr(metrics_registry_base.MetricsRegistryBase, "_instance", None)
    monkeypatch.setattr(metrics_registry_base.MetricsRegistryBase, "_initialized", False)

    try:
        registry = MetricsRegistry()
        registry.record_tenant_boundary_violation(
            source_tenant="tenant-a",
            target_tenant="tenant-b",
            resource_type="artifact",
        )
        metric_names = {
            metric.name
            for resource in reader.get_metrics_data().resource_metrics
            for scope in resource.scope_metrics
            for metric in scope.metrics
        }

        for relative_path in (
            "ops/components/core/slo.yaml",
            "ops/observability/slo/core.yaml",
        ):
            slo = yaml.safe_load((REPO_ROOT / relative_path).read_text(encoding="utf-8"))
            objective = next(
                item
                for item in slo["objectives"]
                if item["name"] == "core_tenant_boundary_violations"
            )
            sli_metrics = set(re.findall(r"\bpolisyos_[A-Za-z0-9_]+", objective["sli"]))

            assert sli_metrics == {"polisyos_audit_tenant_boundary_violations_total"}
            assert sli_metrics <= metric_names
    finally:
        provider.shutdown()


def _component_prometheus_rule_sources(repo_root: Path) -> set[Path]:
    observability = tomllib.loads(
        (repo_root / "architecture/component_observability.toml").read_text(encoding="utf-8")
    )
    return {
        (repo_root / source).resolve()
        for component in observability["component_contract"]
        for source in component.get("prometheus_rules", [])
    }


def _prometheus_rule_sources_loaded_by_default(
    repo_root: Path,
    *,
    config_path: Path | None = None,
) -> set[Path]:
    config_path = config_path or repo_root / "ops/observability/prometheus/prometheus.yml"
    prometheus_config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    compose_path = repo_root / "ops/docker/observability.compose.yml"
    compose = yaml.safe_load(compose_path.read_text(encoding="utf-8"))
    mounts: list[tuple[Path, Path]] = []
    for volume in compose["services"]["prometheus"]["volumes"]:
        source, target, *_ = volume.split(":")
        mounts.append((Path(target), (compose_path.parent / source).resolve()))

    loaded: set[Path] = set()
    for configured_path in prometheus_config["rule_files"]:
        target = Path(configured_path)
        mount = next(
            (
                candidate
                for candidate in sorted(mounts, key=lambda item: len(item[0].parts), reverse=True)
                if target == candidate[0] or candidate[0] in target.parents
            ),
            None,
        )
        assert mount is not None, configured_path
        mount_target, mount_source = mount
        path_pattern = mount_source / target.relative_to(mount_target)
        resolved = {Path(path).resolve() for path in glob.glob(str(path_pattern))}
        assert resolved, configured_path
        loaded.update(resolved)
    return loaded


def _read_toml(path: str) -> dict[str, Any]:
    return tomllib.loads((REPO_ROOT / path).read_text(encoding="utf-8"))


def _path_exists(path: str) -> bool:
    return (REPO_ROOT / path).exists()


def _public_stable_components() -> set[str]:
    surface = _read_toml("architecture/public_surface/contract.toml")
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
