#!/usr/bin/env python3
"""Validate or regenerate Layer 3 time/source and authority-candidate proofs."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import tomllib
import uuid
from collections.abc import Iterator, Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import patch

from pydantic import ValidationError

FAMILY_ID = "policy-design-case-layer3-time-source-authority"
TIME_SOURCE_AUDIT_PATH = (
    "architecture/policy_design_case/layer3_gy_time_source_envelope_audit.json"
)
AUTHORITY_INVENTORY_PATH = (
    "architecture/policy_design_case/layer3_gy_authority_candidate_inventory.json"
)
TASK0_AUDIT_PATH = (
    "architecture/policy_design_case/layer3_gy_task0_audit/"
    "layer3_gy_p0_coverage_audit.json"
)
GX_PROVENANCE_PATH = "architecture/policy_design_case/layer3_gx_positive_status_provenance.json"
OUTPUTS = [TIME_SOURCE_AUDIT_PATH, AUTHORITY_INVENTORY_PATH]
CASE_ID = "ua-msme-affordable-loans-2022"
FIXED_RUN_STARTED = datetime(2026, 6, 16, 12, 5, 11, tzinfo=UTC)
FIXED_RUN_FINISHED = datetime(2026, 6, 16, 12, 6, 13, tzinfo=UTC)
FIXED_NODE_STARTED = datetime(2026, 6, 16, 12, 5, 19, tzinfo=UTC)
FIXED_NODE_FINISHED = datetime(2026, 6, 16, 12, 5, 47, tzinfo=UTC)
AUTHORITY_INVENTORY_FIELDS = {
    "producer_component",
    "source_artifact_ref",
    "field_path",
    "status_text",
    "candidate_positive_rule",
    "firewall_name",
    "exclusion_reason",
    "resulting_boundary_ref",
    "false_exclusion_review",
    "reviewer",
    "reviewed_at",
}


def declared_outputs() -> list[str]:
    """Return the generated artifacts this validator writes in --write mode."""

    return list(OUTPUTS)


def validate(repo_root: Path, *, write: bool = False) -> dict[str, Any]:
    """Return a drift report for the GY-F3 generated proof family."""

    _ensure_src_path(repo_root)
    issues: list[dict[str, str]] = []
    _validate_public_surface_registration(repo_root, issues)
    expected = build_live_proof_payloads(repo_root)
    _validate_time_source_audit(expected[TIME_SOURCE_AUDIT_PATH], issues)
    _validate_authority_inventory(expected[AUTHORITY_INVENTORY_PATH], issues)
    if write:
        for relative_path, payload in expected.items():
            path = repo_root / relative_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(payload, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
    else:
        for relative_path, expected_payload in expected.items():
            committed = _read_json(repo_root / relative_path, issues)
            if committed != expected_payload:
                issues.append({"code": "layer3_time_source_authority_drift", "path": relative_path})
    return {
        "status": "pass" if not issues else "fail",
        "family_id": FAMILY_ID,
        "checked_artifacts": OUTPUTS,
        "write": write,
        "issues": issues,
    }


def build_live_proof_payloads(repo_root: Path) -> dict[str, dict[str, Any]]:
    """Recompute proof payloads from live temporal, catalog, S12, and firewall owners."""

    from polisyos.runtime.quality.candidate_firewall import (
        CandidateFirewallError,
        assert_candidate_positive_firewall_boundary,
        build_authority_candidate_inventory_rows,
    )

    task0 = _read_json_or_raise(repo_root / TASK0_AUDIT_PATH)
    gx = _read_json_or_raise(repo_root / GX_PROVENANCE_PATH)
    firewall_rows = _firewall_rows(task0)
    inventory_rows = build_authority_candidate_inventory_rows(firewall_rows)
    promotion_result = "not_run"
    if inventory_rows:
        try:
            assert_candidate_positive_firewall_boundary(
                inventory_rows[0],
                surface="authority_candidate_inventory_negative_fixture",
                boundary_ref=None,
            )
        except CandidateFirewallError as exc:
            promotion_result = f"rejected:{exc.code}"
    repair_ticket_rows = [
        row.resulting_boundary_ref
        for row in inventory_rows
        if row.false_exclusion_review.startswith("repair_ticket_required")
    ]
    inventory_payload = {
        "schema_version": "policyos.policy_design_case.layer3_gy.authority_candidate_inventory.v1",
        "owner": "team-runtime-quality",
        "proof_source": "task0_candidate_firewall_recompute",
        "row_count": len(inventory_rows),
        "reconciliation": {
            "task0_candidate_positive_status_count": _task0_candidate_count(task0),
            "gx_candidate_positive_status_count": _int(gx.get("candidate_positive_status_count")),
            "gx_positive_status_count": _int(gx.get("positive_status_count")),
            "expected_candidate_positive_status_count": _int(
                gx.get("candidate_positive_status_count")
            ),
            "expected_count_source_refs": [
                TASK0_AUDIT_PATH,
                GX_PROVENANCE_PATH,
            ],
            "false_exclusion_repair_ticket_count": len(repair_ticket_rows),
            "authority_promotion_negative_fixture": promotion_result,
        },
        "false_exclusion_repair_tickets": repair_ticket_rows,
        "rows": [row.model_dump(mode="json") for row in inventory_rows],
    }
    time_payload = _build_time_source_payload(repo_root)
    return {
        TIME_SOURCE_AUDIT_PATH: time_payload,
        AUTHORITY_INVENTORY_PATH: inventory_payload,
    }


def _build_time_source_payload(repo_root: Path) -> dict[str, Any]:
    from polisyos.core.contracts.runtime import RunDetails, RunTimelineEvent, TemporalScope
    from polisyos.data_forge.read_api.catalog import build_production_data_contract_catalog_graph
    from polisyos.pdc import ValueOfInformationEstimate
    from polisyos.runtime.http.services.temporal import (
        TimeSourceConsistencyAuditProjection,
        build_time_source_consistency_audit_projection,
    )
    from polisyos.runtime.quality.design_axes.resource_economics import (
        allocate_value_of_information,
        build_resource_allocation_policy,
        resolve_s12_resource_refs,
    )
    from polisyos.runtime.quality.proving_ground.proving_ground_conversion import (
        build_g5_s12_demand_growth_evidence,
    )

    with tempfile.TemporaryDirectory(prefix="polisyos-layer3-time-source-") as tmp:
        graph = build_production_data_contract_catalog_graph(graph_root=Path(tmp) / "catalog")
        dataset = graph.search_datasets("ukraine msme credit access", top_k=1)[0]

    catalog_time = _parse_time(dataset.last_updated)
    if catalog_time is None:
        raise AssertionError("production catalog dataset missing last_updated")
    control_job_ref, run_details, node_started, node_finished = _runtime_lifecycle_objects(
        RunDetails,
        RunTimelineEvent,
    )
    temporal_scope = TemporalScope(valid_at=run_details.finished_at, tx_at=run_details.finished_at)
    clean = build_time_source_consistency_audit_projection(
        catalog_watermark=catalog_time,
        source_observed_at=catalog_time,
        source_published_at=catalog_time,
        source_updated_at=catalog_time,
        ingested_at=catalog_time,
        effective_time=catalog_time,
        legal_valid_time=catalog_time,
        transaction_time=run_details.finished_at,
        temporal_scope=temporal_scope,
        run_started_at=run_details.started_at,
        run_finished_at=run_details.finished_at,
        node_started_at=node_started.timestamp,
        node_finished_at=node_finished.timestamp,
        retention_or_expiry=run_details.finished_at + timedelta(days=30),
    )
    stale_watermark = build_time_source_consistency_audit_projection(
        catalog_watermark=catalog_time,
        source_observed_at=run_details.started_at,
        source_published_at=catalog_time,
        source_updated_at=run_details.started_at,
        ingested_at=run_details.started_at,
        effective_time=run_details.started_at,
        legal_valid_time=run_details.started_at,
        transaction_time=run_details.finished_at,
        temporal_scope=temporal_scope,
        run_started_at=run_details.started_at,
        run_finished_at=run_details.finished_at,
        node_started_at=node_started.timestamp,
        node_finished_at=node_finished.timestamp,
        retention_or_expiry=run_details.finished_at + timedelta(days=30),
    )
    legal_outside_replay = build_time_source_consistency_audit_projection(
        catalog_watermark=run_details.finished_at,
        source_observed_at=run_details.finished_at,
        source_published_at=catalog_time,
        source_updated_at=run_details.finished_at,
        ingested_at=run_details.finished_at,
        effective_time=run_details.finished_at,
        legal_valid_time=run_details.finished_at + timedelta(days=1),
        transaction_time=run_details.finished_at,
        temporal_scope=temporal_scope,
        run_started_at=run_details.started_at,
        run_finished_at=run_details.finished_at,
        node_started_at=node_started.timestamp,
        node_finished_at=node_finished.timestamp,
        retention_or_expiry=run_details.finished_at + timedelta(days=30),
    )

    estimates = _voi_estimates(ValueOfInformationEstimate)
    allocation = allocate_value_of_information(case_id=CASE_ID, voi_estimates=estimates)
    policy = build_resource_allocation_policy(
        case_id=CASE_ID,
        delegation_contract_ref="pdc://layer2/s7/ua-msme/delegation-contract",
        principal_ref="principal://ua/policy-design-governance-reviewer",
        mission_ref="mission://ua-msme/credit-access",
        voi_estimates=estimates,
        explore_exploit_dial_ref="pdc://layer2/s7/ua-msme/explore-exploit-dial",
        candidate_policy_refs=(
            "allocation-policy://ua-msme/acquisition-heavy",
            "allocation-policy://ua-msme/balanced-governed",
        ),
    )
    real_refs = [
        allocation.allocation_ref,
        policy.policy_ref,
        allocation.voi_allocations[0].voi_estimate_ref,
    ]
    real_resolutions = resolve_s12_resource_refs(
        real_refs,
        voi_allocations=(allocation,),
        allocation_policies=(policy,),
    )
    g5_artifact_refs = _extract_g5_s12_refs(repo_root)
    g5_ref_resolutions = resolve_s12_resource_refs(
        g5_artifact_refs,
        voi_allocations=(allocation,),
        allocation_policies=(policy,),
    )
    g5_evidence = build_g5_s12_demand_growth_evidence(
        s12_case_signals={
            "demand_act_refs": ["demand-act://ua-msme/first-proving-ground"],
            "certified_envelope_delta_refs": ["envelope-delta://ua-msme/first-proving-ground"],
            "voi_allocation_refs": [allocation.voi_allocations[0].voi_estimate_ref],
        },
        voi_allocations=(allocation,),
        allocation_policies=(policy,),
    )
    authorial_evidence = build_g5_s12_demand_growth_evidence(
        s12_case_signals={
            "demand_act_refs": ["demand-act://ua-msme/first-proving-ground"],
            "certified_envelope_delta_refs": ["envelope-delta://ua-msme/first-proving-ground"],
            "voi_allocation_refs": ["voi://ua-msme/layer3-g5"],
        },
        voi_allocations=(allocation,),
        allocation_policies=(policy,),
    )
    audits = [clean, stale_watermark, legal_outside_replay]
    return {
        "schema_version": (
            "policyos.policy_design_case.layer3_gy."
            "time_source_consistency_audit_projection.v1"
        ),
        "owner": "team-runtime-quality",
        "proof_source": "catalog_temporal_consistency_s12_recompute",
        "catalog_source": {
            "dataset_ref": dataset.id,
            "source": dataset.source,
            "source_dataset_id": dataset.source_dataset_id,
            "catalog_last_updated": dataset.last_updated,
        },
        "runtime_lifecycle_source": {
            "control_job_ref": control_job_ref,
            "run_id": run_details.run_id,
            "node_started_event": node_started.event,
            "node_finished_event": node_finished.event,
        },
        "audits": [audit.model_dump(mode="json") for audit in audits],
        "negative_fixtures": {
            "stale_watermark_fresh_source": stale_watermark.mismatch_disposition,
            "legal_valid_time_outside_as_of_replay": legal_outside_replay.mismatch_disposition,
        },
        "s12_ref_dereference": {
            "real_ref_results": [
                resolution.model_dump(mode="json") for resolution in real_resolutions
            ],
            "g5_surface_ref_results": [
                resolution.model_dump(mode="json") for resolution in g5_ref_resolutions
            ],
            "g5_real_ref_evidence": g5_evidence.model_dump(mode="json"),
            "authorial_negative_fixture": authorial_evidence.model_dump(mode="json"),
        },
        "audit_model": TimeSourceConsistencyAuditProjection.__name__,
    }


def _runtime_lifecycle_objects(
    run_details_cls: Any,
    run_timeline_event_cls: Any,
) -> tuple[str, Any, Any, Any]:
    import polisyos.runtime.http.services.control.run_lifecycle  # noqa: F401
    from polisyos.core.run.context import new_run_id
    from polisyos.runtime.http.services.control_plane_store import ControlPlaneStore

    uuid_iter = _deterministic_uuid_sequence("time-source-authority:lifecycle")
    with tempfile.TemporaryDirectory(prefix="polisyos-time-source-lifecycle-") as tmp:
        store = ControlPlaneStore(backend="sqlite", sqlite_path=Path(tmp) / "control.sqlite3")
        try:
            with patch(
                "polisyos.core.run.context.secrets.token_hex",
                side_effect=lambda size=8: next(uuid_iter).hex[: size * 2],
            ):
                run_id = new_run_id()
                job_id = str(next(uuid_iter))
                with patch(
                    "polisyos.runtime.http.services.control_plane_store._utc_now",
                    return_value=FIXED_RUN_STARTED,
                ):
                    store.create_job(
                        job_id=job_id,
                        kind="workflow_run",
                        run_id=run_id,
                        pipeline_id=None,
                        requested_execution_profile=None,
                        effective_execution_profile="dev",
                        policy_flags={},
                        capability_manifest_ref=None,
                        payload_ref=None,
                        submitted_by="time-source-authority-validator",
                    )
                with patch(
                    "polisyos.runtime.http.services.control_plane_store._utc_now",
                    return_value=FIXED_NODE_STARTED,
                ):
                    store.mark_running(
                        job_id=job_id,
                        worker_id=f"worker-{next(uuid_iter).hex[:16]}",
                    )
                with patch(
                    "polisyos.runtime.http.services.control_plane_store._utc_now",
                    return_value=FIXED_RUN_FINISHED,
                ):
                    store.complete_job(
                        job_id=job_id,
                        run_id=run_id,
                        progress={"status": "completed", "authority_result": "not_applicable"},
                    )
            record = store.get_job(job_id)
            if record is None:
                raise RuntimeError("time/source lifecycle job did not persist")
            started_at = record.started_at or FIXED_RUN_STARTED
            finished_at = record.finished_at or FIXED_RUN_FINISHED
            control_job_ref = f"control-job:{record.job_id}"
            run_details = run_details_cls(
                run_id=str(record.run_id or run_id),
                source_kind="core_run",
                status=str(record.state),
                started_at=started_at,
                finished_at=finished_at,
                duration_ms=int((finished_at - started_at).total_seconds() * 1000),
                control_job_id=control_job_ref,
                has_trace=True,
            )
            node_started = run_timeline_event_cls(
                index=0,
                timestamp=started_at,
                phase="layer3_time_source_authority",
                event="NODE_STARTED",
                span_id=f"node-{next(uuid_iter).hex[:16]}",
            )
            node_finished = run_timeline_event_cls(
                index=1,
                timestamp=finished_at,
                phase="layer3_time_source_authority",
                event="NODE_FINISHED",
                span_id=f"node-{next(uuid_iter).hex[:16]}",
            )
            return control_job_ref, run_details, node_started, node_finished
        finally:
            store.close()


def _validate_public_surface_registration(
    repo_root: Path,
    issues: list[dict[str, str]],
) -> None:
    contract = tomllib.loads(
        (repo_root / "architecture/public_surface/contract.toml").read_text(encoding="utf-8")
    )
    contract_families = {
        item.get("id"): item for item in contract.get("generated_artifact_family", [])
    }
    contract_family = contract_families.get(FAMILY_ID)
    if not contract_family:
        issues.append({"code": "layer3_time_source_authority_public_family_missing"})
    else:
        if set(contract_family.get("outputs") or []) != set(OUTPUTS):
            issues.append({"code": "layer3_time_source_authority_outputs_mismatch"})
        if contract_family.get("owner") != "team-runtime-quality":
            issues.append({"code": "layer3_time_source_authority_owner_mismatch"})
        if contract_family.get("stale_output_behavior") != "fail":
            issues.append({"code": "layer3_time_source_authority_public_stale_not_fail"})
        regenerate = str(contract_family.get("regenerate") or "")
        if "--write" not in regenerate:
            issues.append({"code": "layer3_time_source_authority_regenerate_missing_write"})

    inventory_path = repo_root / "architecture/public_surface/inventory.json"
    if inventory_path.exists():
        inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
        inventory_families = {
            item.get("id"): item
            for item in inventory.get("generated_artifact_families", [])
            if isinstance(item, dict)
        }
        inventory_family = inventory_families.get(FAMILY_ID)
        if inventory_family is None:
            issues.append({"code": "layer3_time_source_authority_inventory_family_missing"})
        elif inventory_family != contract_family:
            issues.append({"code": "layer3_time_source_authority_public_inventory_drift"})


def _validate_time_source_audit(
    payload: dict[str, Any],
    issues: list[dict[str, str]],
) -> None:
    from polisyos.runtime.http.services.temporal import (
        TimeSourceConsistencyAuditProjection,
    )
    from polisyos.runtime.quality.authority import (
        TIME_SOURCE_BLOCKED_FOR_OWNER_REVIEW_DISPOSITION,
        TIME_SOURCE_CONSISTENT_DISPOSITION,
        TIME_SOURCE_INCONSISTENT_DISPOSITION,
    )

    if payload.get("audit_model") != TimeSourceConsistencyAuditProjection.__name__:
        issues.append({"code": "time_source_audit_model_mismatch"})
    audits = payload.get("audits")
    if not isinstance(audits, list) or len(audits) < 3:
        issues.append({"code": "time_source_audits_missing"})
        return
    disposition_schema = TimeSourceConsistencyAuditProjection.model_json_schema()["properties"][
        "mismatch_disposition"
    ]
    allowed_dispositions = set(disposition_schema.get("enum") or [])
    expected_fields = set(TimeSourceConsistencyAuditProjection.model_fields)
    dispositions: set[str] = set()
    for audit in audits:
        if not isinstance(audit, dict):
            issues.append({"code": "time_source_audit_not_object"})
            continue
        if set(audit) != expected_fields:
            issues.append({"code": "time_source_audit_fields_mismatch"})
        disposition = audit.get("mismatch_disposition")
        if not isinstance(disposition, str) or disposition not in allowed_dispositions:
            issues.append({"code": "time_source_disposition_unknown"})
        else:
            dispositions.add(disposition)
        try:
            TimeSourceConsistencyAuditProjection.model_validate(audit)
        except ValidationError:
            issues.append({"code": "time_source_audit_contract_invalid"})
    if TIME_SOURCE_CONSISTENT_DISPOSITION not in dispositions:
        issues.append({"code": "time_source_consistent_fixture_missing"})
    if TIME_SOURCE_INCONSISTENT_DISPOSITION not in dispositions:
        issues.append({"code": "time_source_inconsistent_fixture_missing"})
    if TIME_SOURCE_BLOCKED_FOR_OWNER_REVIEW_DISPOSITION not in dispositions:
        issues.append({"code": "time_source_owner_review_fixture_missing"})

    deref = payload.get("s12_ref_dereference") if isinstance(payload, dict) else {}
    if not isinstance(deref, dict):
        issues.append({"code": "s12_ref_dereference_missing"})
        return
    real = deref.get("real_ref_results")
    if not isinstance(real, list) or not real:
        issues.append({"code": "s12_real_ref_results_missing"})
    elif any(item.get("disposition") != "authority_admitted" for item in real if isinstance(item, dict)):
        issues.append({"code": "s12_real_ref_not_admitted"})
    negative = deref.get("authorial_negative_fixture")
    if not isinstance(negative, dict):
        issues.append({"code": "s12_authorial_negative_fixture_missing"})
    elif "voi://ua-msme/layer3-g5" not in negative.get("candidate_only_s12_refs", []):
        issues.append({"code": "s12_authorial_ref_not_candidate_only"})
    elif negative.get("status") == "pass" or not negative.get("issue_codes"):
        issues.append({"code": "s12_authorial_negative_fixture_not_downgraded"})
    if negative and negative.get("voi_allocation_refs"):
        issues.append({"code": "s12_authorial_ref_reached_authority_surface"})


def _validate_authority_inventory(
    payload: dict[str, Any],
    issues: list[dict[str, str]],
) -> None:
    rows = payload.get("rows")
    if not isinstance(rows, list) or not rows:
        issues.append({"code": "authority_candidate_inventory_rows_missing"})
        return
    for row in rows:
        if not isinstance(row, dict):
            issues.append({"code": "authority_candidate_inventory_row_not_object"})
            continue
        if set(row) != AUTHORITY_INVENTORY_FIELDS:
            issues.append({"code": "authority_candidate_inventory_fields_mismatch"})
        if row.get("firewall_name") != "candidate_positive_status_firewall":
            issues.append({"code": "authority_candidate_inventory_firewall_name_mismatch"})
    reconciliation = payload.get("reconciliation")
    if not isinstance(reconciliation, dict):
        issues.append({"code": "authority_candidate_inventory_reconciliation_missing"})
        return
    row_count = _int(payload.get("row_count"))
    task0_count = _int(reconciliation.get("task0_candidate_positive_status_count"))
    gx_count = _int(reconciliation.get("gx_candidate_positive_status_count"))
    expected_count = _int(reconciliation.get("expected_candidate_positive_status_count"))
    expected_sources = reconciliation.get("expected_count_source_refs")
    if not (row_count == len(rows) == task0_count == gx_count == expected_count):
        issues.append(
            {
                "code": "authority_candidate_inventory_reconciliation_failed",
                "row_count": str(row_count),
                "task0_count": str(task0_count),
                "gx_count": str(gx_count),
                "expected_count": str(expected_count),
            }
        )
    if expected_count <= 0:
        issues.append({"code": "authority_candidate_inventory_expected_count_missing"})
    if expected_sources != [TASK0_AUDIT_PATH, GX_PROVENANCE_PATH]:
        issues.append({"code": "authority_candidate_inventory_expected_sources_mismatch"})
    if _int(reconciliation.get("gx_positive_status_count")) != 0:
        issues.append({"code": "authority_candidate_inventory_positive_status_not_zero"})
    if _int(reconciliation.get("false_exclusion_repair_ticket_count")) != 0:
        issues.append({"code": "authority_candidate_inventory_false_exclusion_ticket_open"})
    if reconciliation.get("authority_promotion_negative_fixture") != (
        "rejected:candidate_positive_firewall_boundary_missing"
    ):
        issues.append({"code": "authority_candidate_inventory_promotion_not_rejected"})


def _extract_g5_s12_refs(repo_root: Path) -> list[str]:
    refs: list[str] = []
    for relative_path in (
        "architecture/policy_design_case/layer3_g5_composed_loop_completeness_gate.json",
        "architecture/policy_design_case/layer3_g5_public_export_projection_refs.json",
        "architecture/policy_design_case/layer2_s12_resource_economics_manifest.json",
    ):
        path = repo_root / relative_path
        if path.exists():
            _collect_s12_refs(json.loads(path.read_text(encoding="utf-8")), refs)
    return sorted(set(refs))


def _collect_s12_refs(value: object, refs: list[str]) -> None:
    if isinstance(value, str) and (
        value.startswith("voi://") or value.startswith("s12://")
    ):
        refs.append(value)
        return
    if isinstance(value, Mapping):
        for item in value.values():
            _collect_s12_refs(item, refs)
        return
    if isinstance(value, list | tuple):
        for item in value:
            _collect_s12_refs(item, refs)


def _voi_estimates(value_of_information_estimate_cls: Any) -> list[Any]:
    return [
        value_of_information_estimate_cls(
            estimate_id="s12_acquisition_voi",
            purpose="Rank unresolved acquisition gaps without scalarizing budgets.",
            budget_dimensions=["acquisition_money", "legal_access"],
            used_by_sites=["layer2_s3_substrate_acquisition"],
            owner="principal-governance",
            rule_version_ref="policyos.layer2.s12.resource_economics.v1",
        ),
        value_of_information_estimate_cls(
            estimate_id="s12_refinement_voi",
            purpose="Prioritize refinement while preserving shadow-only posture.",
            budget_dimensions=["compute"],
            used_by_sites=["layer2.s2.shadow_design_loop"],
            owner="principal-governance",
            rule_version_ref="policyos.layer2.s12.resource_economics.v1",
        ),
        value_of_information_estimate_cls(
            estimate_id="s12_attention_voi",
            purpose="Route high-stakes attention through decision rights.",
            budget_dimensions=["human_attention", "expert_time"],
            used_by_sites=["layer2.s7.attention"],
            owner="principal-governance",
            rule_version_ref="policyos.layer2.s12.resource_economics.v1",
        ),
    ]


def _firewall_rows(task0_payload: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    firewall = task0_payload.get("candidate_positive_firewall")
    if not isinstance(firewall, Mapping):
        return []
    rows = firewall.get("rows")
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, Mapping)]


def _task0_candidate_count(task0_payload: Mapping[str, Any]) -> int:
    firewall = task0_payload.get("candidate_positive_firewall")
    counts = firewall.get("counts") if isinstance(firewall, Mapping) else {}
    return _int(counts.get("candidate_positive_status_count")) if isinstance(counts, Mapping) else 0


def _parse_time(value: str | None) -> datetime | None:
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None
    if len(text) == 4 and text.isdigit():
        return datetime(int(text), 7, 1, 12, 0, 1, tzinfo=UTC)
    parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _ensure_src_path(repo_root: Path) -> None:
    src_path = repo_root / "src"
    for path in (repo_root, src_path):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))


def _read_json(path: Path, issues: list[dict[str, str]]) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        issues.append({"code": "layer3_time_source_authority_missing", "path": str(path)})
    except json.JSONDecodeError as exc:
        issues.append(
            {
                "code": "layer3_time_source_authority_invalid_json",
                "path": str(path),
                "error": str(exc),
            }
        )
    return {}


def _read_json_or_raise(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _int(value: object) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _deterministic_uuid_sequence(seed: str) -> Iterator[uuid.UUID]:
    index = 0
    while True:
        yield uuid.uuid5(uuid.NAMESPACE_URL, f"{seed}:{index}")
        index += 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[3])
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--write", action="store_true")
    parser.add_argument("--output-format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)

    report = validate(args.repo_root.resolve(), write=args.write)
    if args.output_format == "json":
        print(json.dumps(report, indent=2, sort_keys=True))
    elif report["status"] == "pass":
        action = "wrote" if args.write else "checked"
        print(f"PASS: Layer 3 time/source authority proofs {action}.")
    else:
        print("FAIL: Layer 3 time/source authority proofs drifted or are invalid.")
        for issue in report["issues"]:
            print(f"- {issue}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
