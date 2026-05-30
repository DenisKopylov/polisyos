from __future__ import annotations

import json
from pathlib import Path

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.canon import from_canonical_bytes
from polisyos.runtime.http.services.control_plane_store import ControlPlaneStore
from polisyos.runtime.quality.event_log import RuntimeDiagnosticEventLog
from tools.quality.testing import runtime_resilience_matrix

REQUIRED_SLO_PHASES = {
    "control.job_lease",
    "control.job_heartbeat",
    "fabric.materialization",
    "cas.put",
    "cas.get",
    "runtime.run_index_refresh",
    "runtime.run_index_list",
    "runtime.timeline_build",
    "runtime.lineage_build",
    "provider.preflight",
    "evidence.bundle_assembly",
    "api.job_detail",
    "dashboard.first_meaningful_route_render",
}

REQUIRED_PHASE_5_5_READINESS_LANES = {
    "load",
    "soak",
    "retry_storm",
    "provider_brownout",
    "cas_pressure",
    "queue_saturation",
    "dashboard_degradation",
}

REQUIRED_PHASE_5_5_SLO_METRICS = {
    "trace_continuity",
    "event_loss",
    "payload_mismatch",
    "latency",
    "retry_amplification",
    "stale_evidence",
    "operator_root_cause_fields",
}

REQUIRED_OPERATOR_ROOT_CAUSE_FIELDS = {
    "owner",
    "phase",
    "cause",
    "missing_input",
    "downstream_impact",
    "refs",
    "next_command",
}


def test_deterministic_matrix_declares_phase_5_6_scenarios_and_slo_budgets() -> None:
    payload = runtime_resilience_matrix.build_matrix_payload(deterministic=True)

    scenario_ids = {scenario["scenario_id"] for scenario in payload["scenarios"]}
    budget_phases = {budget["phase"] for budget in payload["slo_budgets"]}

    assert payload["schema_version"] == "policyos.runtime_resilience_matrix.v1"
    assert payload["mode"] == "deterministic"
    assert payload["resilience_report_ref"]["schema_version"] == payload["schema_version"]
    assert set(payload["resilience_report_ref"]["source_scenarios"]) == scenario_ids
    assert {
        "load_overload",
        "soak_incomplete_evidence",
        "retry_storm",
        "provider_brownout_live",
        "cas_pressure",
        "queue_saturation",
        "run_index_pressure",
        "dashboard_degraded_rendering",
    } <= scenario_ids
    assert budget_phases >= REQUIRED_SLO_PHASES
    assert all(budget["budget_ms"] > 0 for budget in payload["slo_budgets"])
    assert all(budget["next_action"] for budget in payload["slo_budgets"])


def test_phase_5_5_report_only_readiness_lanes_do_not_claim_runtime_authority() -> None:
    payload = runtime_resilience_matrix.build_matrix_payload(deterministic=True)

    lanes = {
        scenario["readiness_lane"]["lane_id"]: scenario
        for scenario in payload["scenarios"]
        if scenario.get("readiness_lane")
    }

    assert set(lanes) >= REQUIRED_PHASE_5_5_READINESS_LANES
    for lane_id in REQUIRED_PHASE_5_5_READINESS_LANES:
        scenario = lanes[lane_id]
        evidence = scenario["runtime_owned_evidence"]

        assert scenario["readiness_lane"]["status"] == scenario["status"]
        assert evidence["runtime_owned"] is False
        assert evidence["emission_mode"] == "report_only"
        assert evidence["artifact_kind"] == "runtime.resilience_lane_evidence"
        assert evidence["evidence_ref"].startswith(
            "quality_evidence/resilience_lanes/"
        )
        assert evidence["diagnostic_event"]["emitted"] is False


def test_phase_5_5_emits_runtime_owned_cas_and_durable_events(tmp_path: Path) -> None:
    artifact_store = FileSystemCAS(tmp_path / "cas").for_tenant(
        "tenant-wave5",
        cell_id="cell-wave5",
    )
    control_store = ControlPlaneStore(
        backend="sqlite",
        sqlite_path=tmp_path / "control-plane.sqlite3",
    )
    event_log = RuntimeDiagnosticEventLog(
        store=control_store,
        artifact_store=artifact_store,
    )

    emitted = runtime_resilience_matrix.emit_runtime_resilience_matrix(
        artifact_store=artifact_store,
        event_log=event_log,
        deterministic=True,
    )

    lanes = {
        scenario["readiness_lane"]["lane_id"]: scenario
        for scenario in emitted["scenarios"]
        if scenario.get("readiness_lane")
    }
    records = event_log.list_events(
        run_id="run-wave5-runtime-resilience",
        job_id="job-wave5-runtime-resilience",
        limit=1000,
    )
    event_types = {record.event.event_type for record in records}

    assert set(lanes) >= REQUIRED_PHASE_5_5_READINESS_LANES
    assert {
        "polisyos.runtime.resilience_lane.evidence_emitted.v1",
        "polisyos.runtime.resilience_lane.slo_evidence_emitted.v1",
    } <= event_types
    for lane_id in REQUIRED_PHASE_5_5_READINESS_LANES:
        scenario = lanes[lane_id]
        evidence = scenario["runtime_owned_evidence"]
        slo_evidence = scenario["diagnostic_slo_evidence"]

        assert evidence["runtime_owned"] is True
        assert evidence["emission_mode"] == "runtime_cas_event"
        assert evidence["evidence_ref"].startswith("sha256:")
        assert evidence["diagnostic_event"]["emitted"] is True
        assert evidence["diagnostic_event"]["artifact_ref"] == evidence["evidence_ref"]
        assert artifact_store.has(evidence["evidence_ref"])
        stored_lane = from_canonical_bytes(artifact_store.get_bytes(evidence["evidence_ref"]))
        assert stored_lane["readiness_lane_id"] == lane_id

        assert slo_evidence["runtime_owned"] is True
        assert slo_evidence["emission_mode"] == "runtime_cas_event"
        assert slo_evidence["slo_evidence_ref"].startswith("sha256:")
        assert artifact_store.has(slo_evidence["slo_evidence_ref"])
        assert all(metric["evidence_ref"] == evidence["evidence_ref"] for metric in slo_evidence["metrics"])


def test_phase_5_5_each_readiness_lane_emits_diagnostic_slo_evidence() -> None:
    payload = runtime_resilience_matrix.build_matrix_payload(deterministic=True)

    lanes = {
        scenario["readiness_lane"]["lane_id"]: scenario
        for scenario in payload["scenarios"]
        if scenario.get("readiness_lane")
    }

    for lane_id in REQUIRED_PHASE_5_5_READINESS_LANES:
        slo_evidence = lanes[lane_id]["diagnostic_slo_evidence"]
        metric_ids = {metric["metric_id"] for metric in slo_evidence["metrics"]}
        root_cause = next(
            metric
            for metric in slo_evidence["metrics"]
            if metric["metric_id"] == "operator_root_cause_fields"
        )

        assert slo_evidence["schema_version"] == "policyos.runtime.lane_diagnostic_slos.v1"
        assert slo_evidence["runtime_owned"] is False
        assert slo_evidence["emission_mode"] == "report_only"
        assert metric_ids >= REQUIRED_PHASE_5_5_SLO_METRICS
        assert all(metric["evidence_ref"] for metric in slo_evidence["metrics"])
        assert all(metric["observed_at"] for metric in slo_evidence["metrics"])
        assert set(root_cause["fields"]) >= REQUIRED_OPERATOR_ROOT_CAUSE_FIELDS


def test_live_provider_brownout_is_quarantined_until_explicitly_enabled() -> None:
    payload = runtime_resilience_matrix.build_matrix_payload(deterministic=True)
    live_lane = _scenario(payload, "provider_brownout_live")

    assert live_lane["status"] == "quarantined"
    assert live_lane["ci_safe"] is False
    assert live_lane["quarantine"]["requires_flag"] == "--include-live-provider-brownout"
    assert live_lane["runner"]["live_provider"] is True

    enabled_payload = runtime_resilience_matrix.build_matrix_payload(
        deterministic=True,
        include_live_provider_brownout=True,
    )
    enabled_live_lane = _scenario(enabled_payload, "provider_brownout_live")

    assert enabled_live_lane["status"] == "manual_ready"
    assert enabled_live_lane["ci_safe"] is False
    assert enabled_live_lane["runner"]["requires_explicit_flag"] is True


def test_matrix_distinguishes_performance_operational_and_quality_failures() -> None:
    payload = runtime_resilience_matrix.build_matrix_payload(deterministic=True)

    assert _scenario(payload, "load_overload")["classification"] == "performance_warning"
    assert _scenario(payload, "queue_saturation")["classification"] == "operational_failure"
    assert _scenario(payload, "soak_incomplete_evidence")["classification"] == "quality_failure"

    incomplete = _scenario(payload, "soak_incomplete_evidence")
    assert incomplete["evidence"]["complete"] is False
    assert incomplete["evidence"]["missing"] == ["quality_evidence/policy_grounding_matrix.json"]
    assert incomplete["approval"]["approval_blocking"] is True
    assert incomplete["approval"]["fail_closed"] is True
    assert incomplete["approval"]["quality_status"] == "fail"


def test_operator_findings_expose_bottleneck_layer_phase_value_budget_and_action() -> None:
    payload = runtime_resilience_matrix.build_matrix_payload(deterministic=True)

    required_keys = {
        "scenario_id",
        "classification",
        "layer",
        "phase",
        "observed_value_ms",
        "budget_ms",
        "status",
        "next_action",
    }
    assert payload["operator_findings"]
    assert all(required_keys <= set(finding) for finding in payload["operator_findings"])
    assert any(
        finding["scenario_id"] == "dashboard_degraded_rendering"
        and finding["layer"] == "dashboard"
        and finding["phase"] == "dashboard.first_meaningful_route_render"
        and finding["observed_value_ms"] > finding["budget_ms"]
        for finding in payload["operator_findings"]
    )


def test_runtime_resilience_matrix_cli_writes_stable_json(tmp_path: Path) -> None:
    output = tmp_path / "resilience_matrix.json"

    assert (
        runtime_resilience_matrix.main(
            ["--deterministic", "--json-output", str(output)]
        )
        == 0
    )

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload == runtime_resilience_matrix.build_matrix_payload(
        deterministic=True,
        json_output=output,
    )
    assert payload["summary"]["quarantined"] == 1
    assert payload["summary"]["performance_warnings"] >= 1
    assert payload["summary"]["operational_failures"] >= 1
    assert payload["summary"]["quality_failures"] >= 1
    assert payload["summary"]["approval_blocking"] >= 1


def _scenario(payload: dict[str, object], scenario_id: str) -> dict[str, object]:
    scenarios = payload["scenarios"]
    assert isinstance(scenarios, list)
    for scenario in scenarios:
        assert isinstance(scenario, dict)
        if scenario["scenario_id"] == scenario_id:
            return scenario
    raise AssertionError(f"missing scenario {scenario_id}")
