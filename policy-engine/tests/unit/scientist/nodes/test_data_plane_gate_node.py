from __future__ import annotations

import logging
from unittest.mock import patch

from polisyos.core.artifacts.manifest import ArtifactRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.contracts.fabric import DataSnapshot
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.state_branching import branch_state as real_branch_state
from polisyos.fabric.quality.quality import QualityIndicators
from polisyos.scientist.nodes.builtins.governance.data_plane_gate import (
    DataPlaneGateNode,
    _quality_report_from_dict,
)
from polisyos.scientist.nodes.builtins.state_keys import INPUT_DATA_SNAPSHOT_REF


def _ctx(store: FileSystemCAS) -> tuple[ExecutionContext, object]:
    registry_bundle_ref = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(store=store, registry_bundle=registry_bundle_ref, run_id="R_gate")
    return (
        ExecutionContext(store=store, run=run, logger=logging.getLogger("test.data_plane_gate")),
        registry_bundle_ref,
    )


def _put_snapshot_with_quality(
    store: FileSystemCAS,
    *,
    tier: str,
    is_fresh: bool,
    pii_total_entities: int,
    pii_max_severity: str,
):
    quality_report_ref = store.put_json(
        {
            "tier": tier,
            "grade": "D" if tier == "bronze" else "B",
            "score": "0.42" if tier == "bronze" else "0.88",
            "freshness_status": {
                "is_fresh": is_fresh,
                "level": "stale" if not is_fresh else "fresh",
                "data_age_seconds": 30 * 24 * 3600 if not is_fresh else 2 * 24 * 3600,
                "message": "freshness violation" if not is_fresh else "fresh",
            },
            "violations": [
                {
                    "rule_type": "quality_flag",
                    "field_name": "income",
                    "severity": "error" if tier == "bronze" else "warning",
                    "message": "quality issue",
                    "expected": "good",
                    "actual": "poor",
                }
            ],
        },
        PutOptions(
            kind="fabric.quality_report",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.fabric.DataQualityReport", version="1.0"),
        ),
    )
    data_ref = store.put_json(
        {"rows": [{"income": 1000}]},
        PutOptions(kind="fabric.tabular_payload", media_type="application/json"),
    )
    snapshot_ref = store.put_json(
        DataSnapshot(
            data_ref=data_ref,
            quality_report_ref=quality_report_ref,
            pii_scan_summary={
                "max_severity": pii_max_severity,
                "total_entities_found": pii_total_entities,
                "entities_by_type": {"person": pii_total_entities},
            },
        ),
        PutOptions(
            kind="fabric.data_snapshot",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.DataSnapshot", version="0.2.0"),
        ),
    )
    return snapshot_ref


def test_data_plane_gate_blocks_strict_profile_on_quality_and_pii(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    ctx, _ = _ctx(store)
    snapshot_ref = _put_snapshot_with_quality(
        store,
        tier="bronze",
        is_fresh=False,
        pii_total_entities=2,
        pii_max_severity="high",
    )
    state = ExperimentState(
        run_id="R_gate_block",
        inputs={INPUT_DATA_SNAPSHOT_REF: snapshot_ref},
        params={"governance_profile": "strict", "tenant_tier": "shared"},
    )

    outcome = DataPlaneGateNode().execute(ctx, state)

    assert outcome.status == "fail"
    assert outcome.error is not None
    assert outcome.error.code == "governance.data_plane_blocked"
    assert outcome.state.params.get("data_plane_gate_blocked") is True


def test_data_plane_gate_allows_mvp_profile_without_blockers(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    ctx, _ = _ctx(store)
    snapshot_ref = _put_snapshot_with_quality(
        store,
        tier="silver",
        is_fresh=True,
        pii_total_entities=0,
        pii_max_severity="none",
    )
    state = ExperimentState(
        run_id="R_gate_pass",
        inputs={INPUT_DATA_SNAPSHOT_REF: snapshot_ref},
        params={"governance_profile": "mvp", "tenant_tier": "shared"},
    )

    outcome = DataPlaneGateNode().execute(ctx, state)

    assert outcome.status == "ok"
    assert outcome.state.params.get("data_plane_gate_blocked") is False
    issues = outcome.state.params.get("data_plane_gate_issues")
    assert isinstance(issues, list)


def test_data_plane_gate_records_degraded_event_for_invalid_quality_report(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    ctx, _ = _ctx(store)
    data_ref = store.put_json(
        {"rows": [{"income": 1000}]},
        PutOptions(kind="fabric.tabular_payload", media_type="application/json"),
    )
    missing_quality_report_ref = ArtifactRef.model_validate(
        {
            "artifact_id": "sha256:" + ("e" * 64),
            "kind": "fabric.quality_report",
            "media_type": "application/json",
        }
    )
    snapshot_ref = store.put_json(
        DataSnapshot(
            data_ref=data_ref,
            quality_report_ref=missing_quality_report_ref,
            pii_scan_summary={"max_severity": "none", "total_entities_found": 0},
        ),
        PutOptions(
            kind="fabric.data_snapshot",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.DataSnapshot", version="0.2.0"),
        ),
    )
    state = ExperimentState(
        run_id="R_gate_quality_degraded",
        inputs={INPUT_DATA_SNAPSHOT_REF: snapshot_ref},
        params={"governance_profile": "mvp", "tenant_tier": "shared"},
    )

    outcome = DataPlaneGateNode().execute(ctx, state)

    assert outcome.status == "ok"
    degraded = [
        event for event in outcome.events if event.code == "data_plane_gate.quality_report_degraded"
    ]
    assert degraded
    assert degraded[0].attrs["reason"] == "quality_report_load_failed"
    assert outcome.state.params.get("data_plane_gate_blocked") is False


def test_data_plane_gate_uses_branch_state_for_param_outputs(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    ctx, _ = _ctx(store)
    snapshot_ref = _put_snapshot_with_quality(
        store,
        tier="silver",
        is_fresh=True,
        pii_total_entities=0,
        pii_max_severity="none",
    )
    state = ExperimentState(
        run_id="R_gate_branch_state",
        inputs={INPUT_DATA_SNAPSHOT_REF: snapshot_ref},
        params={
            "governance_profile": "mvp",
            "tenant_tier": "shared",
            "nested": {"baseline": True},
        },
    )
    observed: dict[str, tuple[str, ...]] = {}

    def _spy_branch(base_state, *, write_paths=()):
        observed["write_paths"] = tuple(write_paths)
        return real_branch_state(base_state, write_paths=write_paths)

    with patch(
        "polisyos.scientist.nodes.builtins.governance.data_plane_gate.branch_state",
        _spy_branch,
    ):
        outcome = DataPlaneGateNode().execute(ctx, state)

    assert outcome.status == "ok"
    assert observed["write_paths"] == (
        "params.data_plane_gate_profile",
        "params.data_plane_gate_issues",
        "params.data_plane_gate_blocked",
        "params.pii_scan_results",
    )
    assert "data_plane_gate_profile" not in state.params
    assert state.params["nested"] == {"baseline": True}
    assert outcome.state.params["data_plane_gate_profile"] == "mvp"


def test_quality_report_proxy_exposes_cache_age_for_quality_fitness() -> None:
    report = _quality_report_from_dict(
        {
            "tier": "silver",
            "grade": "B",
            "score": 0.88,
            "completeness_score": 0.95,
            "row_count": 10,
            "validated_at": "2026-05-09T00:00:00Z",
            "freshness_status": {
                "is_fresh": True,
                "cache_age_seconds": 172800,
                "message": "served from cache",
            },
            "violations": [],
        }
    )

    assert report.freshness_status.data_age_seconds is None
    assert report.freshness_status.cache_age_seconds == 172800
    indicators = QualityIndicators.from_quality_report(report)
    assert indicators.staleness_days == 2
