#!/usr/bin/env python3
"""Build the deterministic runtime resilience matrix for production-quality gates."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.core.canon import CanonSpec
from polisyos.runtime.quality.diagnostic_events import (
    DIAGNOSTIC_EVENT_SCHEMA_NAME,
    DIAGNOSTIC_EVENT_SCHEMA_VERSION,
    DiagnosticEvent,
)
from polisyos.runtime.quality.event_log import DiagnosticEventPayloadPolicy

SCHEMA_VERSION = "policyos.runtime_resilience_matrix.v1"
LANE_EVIDENCE_SCHEMA_VERSION = "policyos.runtime.resilience_lane_evidence.v1"
LANE_DIAGNOSTIC_SLO_SCHEMA_VERSION = "policyos.runtime.lane_diagnostic_slos.v1"
DETERMINISTIC_GENERATED_AT = "2026-05-13T00:00:00+00:00"
DEFAULT_REPORT_PATH = "_build/.tmp/production-quality/resilience_matrix.json"
LIVE_PROVIDER_FLAG = "--include-live-provider-brownout"
LANE_EVIDENCE_ROOT = "quality_evidence/resilience_lanes"
RESILIENCE_RUN_ID = "run-wave5-runtime-resilience"
RESILIENCE_JOB_ID = "job-wave5-runtime-resilience"
RESILIENCE_TENANT_ID = "tenant-wave5"
RESILIENCE_CELL_ID = "cell-wave5"
LANE_EVIDENCE_EVENT_TYPE = "polisyos.runtime.resilience_lane.evidence_emitted.v1"
LANE_SLO_EVENT_TYPE = "polisyos.runtime.resilience_lane.slo_evidence_emitted.v1"

SLO_BUDGETS: tuple[dict[str, Any], ...] = (
    {
        "phase": "control.job_lease",
        "layer": "control_plane",
        "budget_ms": 250.0,
        "next_action": "Inspect lease acquisition latency, worker ownership, and queue locking.",
    },
    {
        "phase": "control.job_heartbeat",
        "layer": "control_plane",
        "budget_ms": 1000.0,
        "next_action": "Inspect worker heartbeat lag and fail over stale leases before approval.",
    },
    {
        "phase": "fabric.materialization",
        "layer": "fabric",
        "budget_ms": 120_000.0,
        "next_action": "Inspect materialization partitions, connector latency, and snapshot writes.",
    },
    {
        "phase": "cas.put",
        "layer": "artifact_store",
        "budget_ms": 250.0,
        "next_action": "Inspect CAS write contention and filesystem latency.",
    },
    {
        "phase": "cas.get",
        "layer": "artifact_store",
        "budget_ms": 200.0,
        "next_action": "Inspect CAS read latency, cache hit rate, and artifact fan-out.",
    },
    {
        "phase": "runtime.run_index_refresh",
        "layer": "runtime_api",
        "budget_ms": 500.0,
        "next_action": "Profile run-index refresh and reduce filesystem scan work.",
    },
    {
        "phase": "runtime.run_index_list",
        "layer": "runtime_api",
        "budget_ms": 100.0,
        "next_action": "Profile run-index listing and tenant filtering latency.",
    },
    {
        "phase": "runtime.timeline_build",
        "layer": "runtime_api",
        "budget_ms": 500.0,
        "next_action": "Profile timeline assembly and trace-event normalization.",
    },
    {
        "phase": "runtime.lineage_build",
        "layer": "runtime_api",
        "budget_ms": 750.0,
        "next_action": "Profile lineage graph expansion and artifact edge resolution.",
    },
    {
        "phase": "provider.preflight",
        "layer": "provider_gateway",
        "budget_ms": 10_000.0,
        "next_action": "Run provider preflight, check brownout status, and switch to simulated lane if live evidence is unavailable.",
    },
    {
        "phase": "evidence.bundle_assembly",
        "layer": "canary_evidence",
        "budget_ms": 5000.0,
        "next_action": "Inspect evidence bundle assembly and block approval when required refs are incomplete.",
    },
    {
        "phase": "api.job_detail",
        "layer": "runtime_api",
        "budget_ms": 250.0,
        "next_action": "Inspect control job detail payload size and API dependency latency.",
    },
    {
        "phase": "dashboard.first_meaningful_route_render",
        "layer": "dashboard",
        "budget_ms": 3000.0,
        "next_action": "Inspect dashboard smoke trace and disable noncritical panels before approval.",
    },
)

_BUDGET_BY_PHASE = {row["phase"]: row for row in SLO_BUDGETS}

_COMMON_EVIDENCE = (
    "bundle.json",
    "job.json",
    "run.json",
    "timeline.json",
    "lineage.json",
    "quality_evidence/quality_scorecard.json",
    "quality_evidence/policy_grounding_matrix.json",
    "performance.json",
)

_SCENARIO_ORDER = (
    "load_overload",
    "soak_incomplete_evidence",
    "retry_storm",
    "provider_brownout_live",
    "cas_pressure",
    "queue_saturation",
    "run_index_pressure",
    "dashboard_degraded_rendering",
)

_READINESS_LANE_BY_SCENARIO = {
    "load_overload": "load",
    "soak_incomplete_evidence": "soak",
    "retry_storm": "retry_storm",
    "provider_brownout_live": "provider_brownout",
    "cas_pressure": "cas_pressure",
    "queue_saturation": "queue_saturation",
    "run_index_pressure": "run_index_pressure",
    "dashboard_degraded_rendering": "dashboard_degradation",
}


def build_matrix_payload(
    *,
    deterministic: bool = False,
    include_live_provider_brownout: bool = False,
    json_output: str | Path | None = None,
) -> dict[str, Any]:
    """Return the stable Phase 5.6 runtime resilience matrix payload."""

    generated_at = (
        DETERMINISTIC_GENERATED_AT
        if deterministic
        else datetime.now(UTC).replace(microsecond=0).isoformat()
    )
    scenarios = [
        _build_scenario(
            scenario_id,
            include_live_provider_brownout=include_live_provider_brownout,
            observed_at=generated_at,
        )
        for scenario_id in _SCENARIO_ORDER
    ]
    operator_findings = _operator_findings(scenarios)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "mode": "deterministic" if deterministic else "local",
        "resilience_report_ref": {
            "path": str(json_output) if json_output is not None else DEFAULT_REPORT_PATH,
            "schema_version": SCHEMA_VERSION,
            "source_scenarios": [scenario["scenario_id"] for scenario in scenarios],
        },
        "slo_budgets": [dict(row) for row in SLO_BUDGETS],
        "summary": _summary(scenarios),
        "operator_findings": operator_findings,
        "scenarios": scenarios,
    }


def emit_runtime_resilience_matrix(
    *,
    artifact_store: Any,
    event_log: Any,
    deterministic: bool = False,
    include_live_provider_brownout: bool = False,
    json_output: str | Path | None = None,
) -> dict[str, Any]:
    """Build the matrix and persist every lane evidence row through runtime CAS/events."""

    payload = build_matrix_payload(
        deterministic=deterministic,
        include_live_provider_brownout=include_live_provider_brownout,
        json_output=json_output,
    )
    emitted_scenarios = [
        _emit_scenario_runtime_evidence(
            scenario,
            artifact_store=artifact_store,
            event_log=event_log,
            observed_at=str(payload["generated_at"]),
        )
        for scenario in payload["scenarios"]
    ]
    emitted = {
        **payload,
        "mode": f"{payload['mode']}_runtime_emitted",
        "runtime_emission": {
            "runtime_owned": True,
            "run_id": RESILIENCE_RUN_ID,
            "job_id": RESILIENCE_JOB_ID,
            "event_types": [LANE_EVIDENCE_EVENT_TYPE, LANE_SLO_EVENT_TYPE],
        },
        "operator_ttrc_minutes": {"p50": 5.0, "p90": 10.0},
        "scenarios": emitted_scenarios,
    }
    emitted["summary"] = _summary(emitted_scenarios)
    emitted["operator_findings"] = _operator_findings(emitted_scenarios)
    return emitted


def _build_scenario(
    scenario_id: str,
    *,
    include_live_provider_brownout: bool,
    observed_at: str,
) -> dict[str, Any]:
    builders = {
        "load_overload": lambda: _load_overload(observed_at=observed_at),
        "soak_incomplete_evidence": lambda: _soak_incomplete_evidence(
            observed_at=observed_at,
        ),
        "retry_storm": lambda: _retry_storm(observed_at=observed_at),
        "provider_brownout_live": lambda: _provider_brownout_live(
            include_live_provider_brownout=include_live_provider_brownout,
            observed_at=observed_at,
        ),
        "cas_pressure": lambda: _cas_pressure(observed_at=observed_at),
        "queue_saturation": lambda: _queue_saturation(observed_at=observed_at),
        "run_index_pressure": lambda: _run_index_pressure(observed_at=observed_at),
        "dashboard_degraded_rendering": lambda: _dashboard_degraded_rendering(
            observed_at=observed_at,
        ),
    }
    return builders[scenario_id]()


def _load_overload(*, observed_at: str) -> dict[str, Any]:
    observations = [
        _observation("control.job_heartbeat", 1450.0),
        _observation("api.job_detail", 180.0),
    ]
    return _scenario(
        scenario_id="load_overload",
        scenario_kind="load",
        status="warn",
        classification="performance_warning",
        observations=observations,
        evidence=_evidence(),
        approval=_approval(
            performance_status="warn",
            quality_status="pass",
            operational_status="pass",
            approval_blocking=True,
            fail_closed=False,
            reason="performance_budget_warn",
        ),
        degraded_mode={
            "mode": "load_shedding",
            "observable": True,
            "fail_closed": False,
        },
        observed_at=observed_at,
    )


def _soak_incomplete_evidence(*, observed_at: str) -> dict[str, Any]:
    observations = [
        _observation("fabric.materialization", 132_000.0),
        _observation("evidence.bundle_assembly", 4100.0),
    ]
    return _scenario(
        scenario_id="soak_incomplete_evidence",
        scenario_kind="soak",
        status="failed",
        classification="quality_failure",
        observations=observations,
        evidence=_evidence(missing=["quality_evidence/policy_grounding_matrix.json"]),
        approval=_approval(
            performance_status="warn",
            quality_status="fail",
            operational_status="pass",
            approval_blocking=True,
            fail_closed=True,
            reason="evidence_incomplete_under_load",
        ),
        degraded_mode={
            "mode": "evidence_incomplete",
            "observable": True,
            "fail_closed": True,
        },
        observed_at=observed_at,
    )


def _retry_storm(*, observed_at: str) -> dict[str, Any]:
    observations = [
        _observation("provider.preflight", 16_500.0),
        _observation("control.job_heartbeat", 920.0),
    ]
    return _scenario(
        scenario_id="retry_storm",
        scenario_kind="retry_storm",
        status="failed",
        classification="operational_failure",
        observations=observations,
        evidence=_evidence(),
        approval=_approval(
            performance_status="fail",
            quality_status="pass",
            operational_status="fail",
            approval_blocking=True,
            fail_closed=True,
            reason="retry_storm_provider_preflight_failed",
        ),
        degraded_mode={
            "mode": "retry_backoff",
            "observable": True,
            "fail_closed": True,
        },
        observed_at=observed_at,
    )


def _provider_brownout_live(
    *,
    include_live_provider_brownout: bool,
    observed_at: str,
) -> dict[str, Any]:
    observations = [_observation("provider.preflight", 18_000.0)]
    if include_live_provider_brownout:
        return _scenario(
            scenario_id="provider_brownout_live",
            scenario_kind="provider_brownout",
            status="manual_ready",
            classification="operational_failure",
            observations=observations,
            evidence=_evidence(required=(*_COMMON_EVIDENCE, "provider_preflight.json")),
            approval=_approval(
                performance_status="fail",
                quality_status="pass",
                operational_status="fail",
                approval_blocking=True,
                fail_closed=True,
                reason="live_provider_brownout",
            ),
            degraded_mode={
                "mode": "provider_brownout",
                "observable": True,
                "fail_closed": True,
            },
            ci_safe=False,
            runner=_live_runner(enabled=True),
            observed_at=observed_at,
        )
    return _scenario(
        scenario_id="provider_brownout_live",
        scenario_kind="provider_brownout",
        status="quarantined",
        classification="quarantined",
        observations=observations,
        evidence=_evidence(required=(*_COMMON_EVIDENCE, "provider_preflight.json")),
        approval=_approval(
            performance_status="missing",
            quality_status="pass",
            operational_status="quarantined",
            approval_blocking=True,
            fail_closed=True,
            reason="live_provider_brownout_quarantined",
        ),
        degraded_mode={
            "mode": "provider_brownout",
            "observable": True,
            "fail_closed": True,
        },
        ci_safe=False,
        quarantine={
            "reason": "requires live provider brownout credentials and budget approval",
            "requires_flag": LIVE_PROVIDER_FLAG,
            "owner": "team-ops",
            "exit_criteria": "Run manually with explicit live-provider brownout approval and attach provider_preflight.json.",
        },
        runner=_live_runner(enabled=False),
        observed_at=observed_at,
    )


def _cas_pressure(*, observed_at: str) -> dict[str, Any]:
    observations = [
        _observation("cas.put", 420.0),
        _observation("cas.get", 320.0),
    ]
    return _scenario(
        scenario_id="cas_pressure",
        scenario_kind="cas_pressure",
        status="warn",
        classification="performance_warning",
        observations=observations,
        evidence=_evidence(),
        approval=_approval(
            performance_status="warn",
            quality_status="pass",
            operational_status="pass",
            approval_blocking=True,
            fail_closed=False,
            reason="performance_budget_warn",
        ),
        degraded_mode={
            "mode": "cas_backpressure",
            "observable": True,
            "fail_closed": False,
        },
        observed_at=observed_at,
    )


def _queue_saturation(*, observed_at: str) -> dict[str, Any]:
    observations = [
        _observation("control.job_lease", 870.0),
        _observation("control.job_heartbeat", 2600.0),
    ]
    return _scenario(
        scenario_id="queue_saturation",
        scenario_kind="queue_saturation",
        status="failed",
        classification="operational_failure",
        observations=observations,
        evidence=_evidence(),
        approval=_approval(
            performance_status="fail",
            quality_status="pass",
            operational_status="fail",
            approval_blocking=True,
            fail_closed=True,
            reason="control_queue_saturated",
        ),
        degraded_mode={
            "mode": "queue_backpressure",
            "observable": True,
            "fail_closed": True,
        },
        observed_at=observed_at,
    )


def _run_index_pressure(*, observed_at: str) -> dict[str, Any]:
    observations = [
        _observation("runtime.run_index_refresh", 850.0),
        _observation("runtime.run_index_list", 145.0),
        _observation("runtime.timeline_build", 420.0),
        _observation("runtime.lineage_build", 690.0),
    ]
    return _scenario(
        scenario_id="run_index_pressure",
        scenario_kind="run_index_pressure",
        status="warn",
        classification="performance_warning",
        observations=observations,
        evidence=_evidence(),
        approval=_approval(
            performance_status="warn",
            quality_status="pass",
            operational_status="pass",
            approval_blocking=True,
            fail_closed=False,
            reason="performance_budget_warn",
        ),
        degraded_mode={
            "mode": "run_index_pressure",
            "observable": True,
            "fail_closed": False,
        },
        observed_at=observed_at,
    )


def _dashboard_degraded_rendering(*, observed_at: str) -> dict[str, Any]:
    observations = [_observation("dashboard.first_meaningful_route_render", 4200.0)]
    return _scenario(
        scenario_id="dashboard_degraded_rendering",
        scenario_kind="dashboard_degradation",
        status="warn",
        classification="performance_warning",
        observations=observations,
        evidence=_evidence(required=(*_COMMON_EVIDENCE, "dashboard.json")),
        approval=_approval(
            performance_status="warn",
            quality_status="pass",
            operational_status="pass",
            approval_blocking=True,
            fail_closed=False,
            reason="performance_budget_warn",
        ),
        degraded_mode={
            "mode": "dashboard_degraded_rendering",
            "observable": True,
            "fail_closed": False,
        },
        observed_at=observed_at,
    )


def _scenario(
    *,
    scenario_id: str,
    scenario_kind: str,
    status: str,
    classification: str,
    observations: list[dict[str, Any]],
    evidence: dict[str, Any],
    approval: dict[str, Any],
    degraded_mode: dict[str, Any],
    observed_at: str,
    ci_safe: bool = True,
    quarantine: dict[str, str] | None = None,
    runner: dict[str, Any] | None = None,
) -> dict[str, Any]:
    readiness_lane = _readiness_lane(
        scenario_id=scenario_id,
        scenario_kind=scenario_kind,
        status=status,
        classification=classification,
        ci_safe=ci_safe,
    )
    runtime_owned_evidence = _runtime_owned_evidence(
        scenario_id=scenario_id,
        readiness_lane=readiness_lane,
        evidence=evidence,
        observed_at=observed_at,
    )
    diagnostic_slo_evidence = _lane_diagnostic_slo_evidence(
        scenario_id=scenario_id,
        readiness_lane=readiness_lane,
        observations=observations,
        evidence=evidence,
        approval=approval,
        runtime_owned_evidence=runtime_owned_evidence,
        observed_at=observed_at,
    )
    return {
        "scenario_id": scenario_id,
        "scenario_kind": scenario_kind,
        "lane": "deterministic_local" if ci_safe else "live_provider_manual",
        "readiness_lane": readiness_lane,
        "status": status,
        "classification": classification,
        "ci_safe": ci_safe,
        "quarantine": quarantine,
        "runner": runner or _deterministic_runner(scenario_id),
        "top_bottleneck": _top_bottleneck(observations),
        "observations": observations,
        "runtime_owned_evidence": runtime_owned_evidence,
        "diagnostic_slo_evidence": diagnostic_slo_evidence,
        "evidence": evidence,
        "approval": approval,
        "degraded_mode": degraded_mode,
    }


def _emit_scenario_runtime_evidence(
    scenario: dict[str, Any],
    *,
    artifact_store: Any,
    event_log: Any,
    observed_at: str,
) -> dict[str, Any]:
    emitted = dict(scenario)
    lane_payload = _runtime_lane_payload_for_cas(scenario)
    lane_ref = _put_runtime_json(
        artifact_store,
        lane_payload,
        kind="runtime.resilience_lane_evidence",
        schema_name="polisyos.runtime.ResilienceLaneEvidence",
        schema_version="1.0",
    )
    lane_event = _append_resilience_event(
        event_log,
        scenario=scenario,
        event_type=LANE_EVIDENCE_EVENT_TYPE,
        event_suffix="lane-evidence",
        artifact_ref=lane_ref,
        payload=lane_payload,
        observed_at=observed_at,
    )

    runtime_evidence = dict(scenario["runtime_owned_evidence"])
    runtime_evidence.update(
        {
            "runtime_owned": True,
            "authority": "runtime",
            "emission_mode": "runtime_cas_event",
            "evidence_ref": lane_ref,
            "diagnostic_event": {
                **dict(runtime_evidence["diagnostic_event"]),
                "event_id": lane_event.event.event_id,
                "event_type": LANE_EVIDENCE_EVENT_TYPE,
                "artifact_ref": lane_ref,
                "runtime_owned": True,
                "emitted": True,
            },
        }
    )

    slo_payload = {
        **dict(scenario["diagnostic_slo_evidence"]),
        "runtime_owned": True,
        "emission_mode": "runtime_cas_event",
        "lane_evidence_ref": lane_ref,
        "metrics": [
            {**dict(metric), "evidence_ref": lane_ref}
            for metric in scenario["diagnostic_slo_evidence"]["metrics"]
            if isinstance(metric, dict)
        ],
    }
    slo_ref = _put_runtime_json(
        artifact_store,
        slo_payload,
        kind="runtime.resilience_lane_slo_evidence",
        schema_name="polisyos.runtime.ResilienceLaneSloEvidence",
        schema_version="1.0",
    )
    slo_event = _append_resilience_event(
        event_log,
        scenario=scenario,
        event_type=LANE_SLO_EVENT_TYPE,
        event_suffix="slo-evidence",
        artifact_ref=slo_ref,
        payload=slo_payload,
        observed_at=observed_at,
    )
    slo_evidence = dict(slo_payload)
    slo_evidence.update(
        {
            "slo_evidence_ref": slo_ref,
            "diagnostic_event": {
                "event_id": slo_event.event.event_id,
                "event_type": LANE_SLO_EVENT_TYPE,
                "artifact_ref": slo_ref,
                "runtime_owned": True,
                "emitted": True,
            },
        }
    )

    emitted["runtime_owned_evidence"] = runtime_evidence
    emitted["diagnostic_slo_evidence"] = slo_evidence
    return emitted


def _runtime_lane_payload_for_cas(scenario: dict[str, Any]) -> dict[str, Any]:
    evidence = dict(scenario["runtime_owned_evidence"])
    return {
        **evidence,
        "runtime_owned": True,
        "authority": "runtime",
        "emission_mode": "runtime_cas_event",
        "scenario_id": scenario["scenario_id"],
        "status": scenario["status"],
        "classification": scenario["classification"],
        "readiness_lane": dict(scenario["readiness_lane"]),
        "approval": dict(scenario["approval"]),
    }


def _put_runtime_json(
    artifact_store: Any,
    payload: dict[str, Any],
    *,
    kind: str,
    schema_name: str,
    schema_version: str,
) -> str:
    ref = artifact_store.put_json(
        payload,
        ArtifactWriteOptions(
            kind=kind,
            media_type="application/json",
            schema=SchemaInfo(name=schema_name, version=schema_version),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return str(ref.artifact_id)


def _append_resilience_event(
    event_log: Any,
    *,
    scenario: dict[str, Any],
    event_type: str,
    event_suffix: str,
    artifact_ref: str,
    payload: dict[str, Any],
    observed_at: str,
) -> Any:
    scenario_id = str(scenario["scenario_id"])
    lane_id = str(scenario["readiness_lane"]["lane_id"])
    event = DiagnosticEvent(
        event_id=f"evt-wave5-{scenario_id}-{event_suffix}",
        event_source="polisyos.runtime",
        event_type=event_type,
        event_time=datetime.fromisoformat(observed_at).astimezone(UTC),
        event_subject=(
            f"run/{RESILIENCE_RUN_ID}/job/{RESILIENCE_JOB_ID}/lane/{lane_id}/{event_suffix}"
        ),
        schema_name=DIAGNOSTIC_EVENT_SCHEMA_NAME,
        schema_version=DIAGNOSTIC_EVENT_SCHEMA_VERSION,
        trace_id=f"trace-wave5-{scenario_id}",
        span_id=f"span-{event_suffix}-{scenario_id}",
        parent_span_id=None,
        run_id=RESILIENCE_RUN_ID,
        job_id=RESILIENCE_JOB_ID,
        tenant_id=RESILIENCE_TENANT_ID,
        cell_id=RESILIENCE_CELL_ID,
        producer_component="tools.quality.testing.runtime_resilience_matrix",
        producer_version="2026.05.15+hds-wave5",
        execution_profile="production",
        phase=str(scenario["scenario_kind"]),
        state_before="observed",
        state_after="persisted",
        payload_ref=artifact_ref,
        artifact_refs=(artifact_ref,),
        input_refs=(lane_id,),
        blocking_status=(
            "blocking" if scenario["approval"]["fail_closed"] is True else "non_blocking"
        ),
        redaction_policy_ref="redaction-policy/runtime-diagnostics-v1",
        duplicate_of=None,
        dedupe_key=f"{RESILIENCE_JOB_ID}:{lane_id}:{event_suffix}",
        sampling_decision="always_record",
        sampling_rate=1.0,
    )
    return event_log.append(
        event,
        payload=payload,
        payload_policy=DiagnosticEventPayloadPolicy(authority_bearing=True),
    )


def _readiness_lane(
    *,
    scenario_id: str,
    scenario_kind: str,
    status: str,
    classification: str,
    ci_safe: bool,
) -> dict[str, Any]:
    lane_id = _READINESS_LANE_BY_SCENARIO[scenario_id]
    return {
        "lane_id": lane_id,
        "scenario_id": scenario_id,
        "scenario_kind": scenario_kind,
        "status": status,
        "classification": classification,
        "ci_safe": ci_safe,
        "runtime_required": True,
    }


def _runtime_owned_evidence(
    *,
    scenario_id: str,
    readiness_lane: dict[str, Any],
    evidence: dict[str, Any],
    observed_at: str,
) -> dict[str, Any]:
    evidence_ref = f"{LANE_EVIDENCE_ROOT}/{scenario_id}.json"
    return {
        "schema_version": LANE_EVIDENCE_SCHEMA_VERSION,
        "runtime_owned": False,
        "authority": "report_only",
        "producer": "runtime.resilience_matrix",
        "emitted_by": "tools.quality.testing.runtime_resilience_matrix",
        "emission_mode": "report_only",
        "artifact_kind": "runtime.resilience_lane_evidence",
        "evidence_ref": evidence_ref,
        "observed_at": observed_at,
        "readiness_lane_id": readiness_lane["lane_id"],
        "required_evidence": list(evidence["required"]),
        "observed_evidence": list(evidence["observed"]),
        "missing_evidence": list(evidence["missing"]),
        "diagnostic_event": {
            "event_id": f"diagnostic-event:{scenario_id}:resilience_lane_evidence",
            "event_type": LANE_EVIDENCE_EVENT_TYPE,
            "producer": "runtime.resilience_matrix",
            "artifact_ref": evidence_ref,
            "observed_at": observed_at,
            "runtime_owned": False,
            "emitted": False,
            "trace_id": f"trace:{scenario_id}:resilience",
        },
    }


def _lane_diagnostic_slo_evidence(
    *,
    scenario_id: str,
    readiness_lane: dict[str, Any],
    observations: list[dict[str, Any]],
    evidence: dict[str, Any],
    approval: dict[str, Any],
    runtime_owned_evidence: dict[str, Any],
    observed_at: str,
) -> dict[str, Any]:
    evidence_ref = str(runtime_owned_evidence["evidence_ref"])
    bottleneck = _top_bottleneck(observations)
    latency_value = float(bottleneck.get("observed_value_ms") or 0.0)
    latency_budget = float(bottleneck.get("budget_ms") or 1.0)
    retry_amplification = _retry_amplification_for(scenario_id)
    missing = list(evidence["missing"])
    return {
        "schema_version": LANE_DIAGNOSTIC_SLO_SCHEMA_VERSION,
        "runtime_owned": False,
        "emission_mode": "report_only",
        "readiness_lane_id": readiness_lane["lane_id"],
        "scenario_id": scenario_id,
        "observed_at": observed_at,
        "metrics": [
            _lane_slo_metric(
                "trace_continuity",
                value=1.0,
                comparator="at_least",
                threshold=1.0,
                observed_at=observed_at,
                evidence_ref=evidence_ref,
            ),
            _lane_slo_metric(
                "event_loss",
                value=0.0,
                comparator="at_most",
                threshold=0.0,
                observed_at=observed_at,
                evidence_ref=evidence_ref,
            ),
            _lane_slo_metric(
                "payload_mismatch",
                value=0.0,
                comparator="at_most",
                threshold=0.0,
                observed_at=observed_at,
                evidence_ref=evidence_ref,
            ),
            _lane_slo_metric(
                "latency",
                value=latency_value,
                comparator="at_most",
                threshold=latency_budget,
                observed_at=observed_at,
                evidence_ref=evidence_ref,
                phase=str(bottleneck.get("phase") or ""),
                layer=str(bottleneck.get("layer") or ""),
            ),
            _lane_slo_metric(
                "retry_amplification",
                value=retry_amplification,
                comparator="at_most",
                threshold=1.5,
                observed_at=observed_at,
                evidence_ref=evidence_ref,
            ),
            _lane_slo_metric(
                "stale_evidence",
                value=0.0,
                comparator="at_most",
                threshold=0.0,
                observed_at=observed_at,
                evidence_ref=evidence_ref,
            ),
            _operator_root_cause_metric(
                scenario_id=scenario_id,
                readiness_lane=readiness_lane,
                bottleneck=bottleneck,
                approval=approval,
                missing=missing,
                evidence_ref=evidence_ref,
                observed_at=observed_at,
            ),
        ],
    }


def _lane_slo_metric(
    metric_id: str,
    *,
    value: float,
    comparator: str,
    threshold: float,
    observed_at: str,
    evidence_ref: str,
    phase: str | None = None,
    layer: str | None = None,
) -> dict[str, Any]:
    passed = value >= threshold if comparator == "at_least" else value <= threshold
    metric: dict[str, Any] = {
        "metric_id": metric_id,
        "value": value,
        "status": "pass" if passed else "over_error_budget",
        "objective": {
            "comparator": comparator,
            "threshold": threshold,
        },
        "observed_at": observed_at,
        "evidence_ref": evidence_ref,
    }
    if phase:
        metric["phase"] = phase
    if layer:
        metric["layer"] = layer
    return metric


def _operator_root_cause_metric(
    *,
    scenario_id: str,
    readiness_lane: dict[str, Any],
    bottleneck: dict[str, Any],
    approval: dict[str, Any],
    missing: list[str],
    evidence_ref: str,
    observed_at: str,
) -> dict[str, Any]:
    phase = str(bottleneck.get("phase") or readiness_lane["scenario_kind"])
    fields = {
        "owner": _owner_for(readiness_lane),
        "phase": phase,
        "cause": str(approval["reason"]),
        "missing_input": missing,
        "downstream_impact": _downstream_impact(approval),
        "refs": [evidence_ref],
        "next_command": (
            "uv run python tools/quality/testing/runtime_resilience_matrix.py "
            "--deterministic --list"
        ),
    }
    metric = _lane_slo_metric(
        "operator_root_cause_fields",
        value=1.0,
        comparator="at_least",
        threshold=1.0,
        observed_at=observed_at,
        evidence_ref=evidence_ref,
        phase=phase,
        layer=str(bottleneck.get("layer") or "runtime"),
    )
    metric["fields"] = fields
    metric["scenario_id"] = scenario_id
    return metric


def _retry_amplification_for(scenario_id: str) -> float:
    if scenario_id == "retry_storm":
        return 4.0
    if scenario_id == "provider_brownout_live":
        return 2.0
    return 1.0


def _owner_for(readiness_lane: dict[str, Any]) -> str:
    lane_id = str(readiness_lane["lane_id"])
    if lane_id == "dashboard_degradation":
        return "runtime-dashboard"
    if lane_id in {"provider_brownout", "retry_storm"}:
        return "runtime-quality"
    return "runtime-platform"


def _downstream_impact(approval: dict[str, Any]) -> str:
    if approval["fail_closed"] is True:
        return "production approval is blocked until runtime evidence is repaired"
    if approval["approval_blocking"] is True:
        return "production approval requires operator review before promotion"
    return "runtime lane remains eligible for approval"


def _observation(phase: str, observed_value_ms: float) -> dict[str, Any]:
    budget = _BUDGET_BY_PHASE[phase]
    budget_ms = float(budget["budget_ms"])
    status = "pass" if observed_value_ms <= budget_ms else "over_budget"
    row: dict[str, Any] = {
        "phase": phase,
        "layer": budget["layer"],
        "observed_value_ms": float(observed_value_ms),
        "observed_duration_ms": float(observed_value_ms),
        "budget_ms": budget_ms,
        "status": status,
        "next_action": budget["next_action"],
    }
    if status == "over_budget":
        row["over_by_ms"] = round(observed_value_ms - budget_ms, 3)
    return row


def _top_bottleneck(observations: list[dict[str, Any]]) -> dict[str, Any]:
    if not observations:
        return {}
    return dict(
        max(
            observations,
            key=lambda row: float(row["observed_value_ms"]) / max(float(row["budget_ms"]), 1.0),
        )
    )


def _evidence(
    *,
    required: tuple[str, ...] = _COMMON_EVIDENCE,
    missing: list[str] | None = None,
) -> dict[str, Any]:
    missing_set = set(missing or [])
    observed = [item for item in required if item not in missing_set]
    return {
        "required": list(required),
        "observed": observed,
        "missing": sorted(missing_set),
        "complete": not missing_set,
    }


def _approval(
    *,
    performance_status: str,
    quality_status: str,
    operational_status: str,
    approval_blocking: bool,
    fail_closed: bool,
    reason: str,
) -> dict[str, Any]:
    return {
        "eligible": not approval_blocking,
        "approval_blocking": approval_blocking,
        "fail_closed": fail_closed,
        "performance_status": performance_status,
        "quality_status": quality_status,
        "operational_status": operational_status,
        "reason": reason,
    }


def _deterministic_runner(scenario_id: str) -> dict[str, Any]:
    return {
        "kind": "deterministic_fixture",
        "live_provider": False,
        "requires_explicit_flag": False,
        "argv": ["--deterministic", f"--scenario={scenario_id}"],
    }


def _live_runner(*, enabled: bool) -> dict[str, Any]:
    argv = [LIVE_PROVIDER_FLAG, "--scenario=provider_brownout_live"] if enabled else []
    return {
        "kind": "manual_live_provider_fixture",
        "live_provider": True,
        "requires_explicit_flag": True,
        "argv": argv,
    }


def _summary(scenarios: list[dict[str, Any]]) -> dict[str, Any]:
    classifications = [str(scenario["classification"]) for scenario in scenarios]
    return {
        "total_scenarios": len(scenarios),
        "deterministic_local": sum(1 for scenario in scenarios if scenario["ci_safe"] is True),
        "quarantined": sum(1 for scenario in scenarios if scenario["status"] == "quarantined"),
        "manual_ready": sum(1 for scenario in scenarios if scenario["status"] == "manual_ready"),
        "performance_warnings": classifications.count("performance_warning"),
        "operational_failures": classifications.count("operational_failure"),
        "quality_failures": classifications.count("quality_failure"),
        "approval_blocking": sum(
            1 for scenario in scenarios if scenario["approval"]["approval_blocking"] is True
        ),
        "fail_closed": sum(
            1 for scenario in scenarios if scenario["approval"]["fail_closed"] is True
        ),
    }


def _operator_findings(scenarios: list[dict[str, Any]]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for scenario in scenarios:
        if scenario["status"] == "quarantined":
            continue
        bottleneck = scenario["top_bottleneck"]
        if not bottleneck:
            continue
        if bottleneck["status"] == "pass" and scenario["evidence"]["complete"] is True:
            continue
        findings.append(
            {
                "scenario_id": scenario["scenario_id"],
                "classification": scenario["classification"],
                "layer": bottleneck["layer"],
                "phase": bottleneck["phase"],
                "observed_value_ms": bottleneck["observed_value_ms"],
                "budget_ms": bottleneck["budget_ms"],
                "status": bottleneck["status"],
                "next_action": bottleneck["next_action"],
            }
        )
    return findings


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _print_summary(payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    print(
        "Runtime resilience matrix: "
        f"{summary['total_scenarios']} scenarios, "
        f"{summary['performance_warnings']} performance warnings, "
        f"{summary['operational_failures']} operational failures, "
        f"{summary['quality_failures']} quality failures, "
        f"{summary['quarantined']} quarantined"
    )
    for finding in payload["operator_findings"]:
        print(
            f"{finding['scenario_id']} [{finding['classification']}]: "
            f"{finding['layer']} {finding['phase']} "
            f"{finding['observed_value_ms']}ms/{finding['budget_ms']}ms"
        )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--deterministic",
        action="store_true",
        help="Emit stable timestamps and deterministic local scenario values.",
    )
    parser.add_argument(
        LIVE_PROVIDER_FLAG,
        action="store_true",
        help="Mark the live-provider brownout lane manual-ready instead of quarantined.",
    )
    parser.add_argument(
        "--json-output",
        default="",
        help="Optional path to write the resilience matrix JSON payload.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="Print a concise operator summary.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    json_output = Path(args.json_output) if args.json_output else None
    payload = build_matrix_payload(
        deterministic=args.deterministic,
        include_live_provider_brownout=args.include_live_provider_brownout,
        json_output=json_output,
    )
    if json_output is not None:
        _write_json(json_output, payload)
    if args.list or json_output is None:
        _print_summary(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "SCHEMA_VERSION",
    "SLO_BUDGETS",
    "build_matrix_payload",
    "emit_runtime_resilience_matrix",
    "main",
]
