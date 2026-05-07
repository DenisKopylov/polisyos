from __future__ import annotations

import logging

from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.core.contracts.foundry import Metrics
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.ir.analytics.metric_validation_report import (
    FamilyAdjustment,
    MetricComparisonResult,
    MetricValidationReport,
    SignificanceRecord,
    persist_metric_validation_report,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.nodes.builtins.decide.build_decision_packet import BuildDecisionPacketNode
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_METRIC_VALIDATION_REPORT_REF,
    ARTIFACT_METRICS_REF,
    INPUT_DATA_SNAPSHOT_REF,
    INPUT_REGISTRY_BUNDLE_REF,
    INPUT_TRINITY_BUNDLE_REF,
)


def test_build_decision_packet_projects_metric_validation_comparisons(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(
        store=store,
        registry_bundle=registry_bundle,
        run_id="R_packet_metric_validation_small",
    )
    ctx = ExecutionContext(
        store=store,
        run=run,
        logger=logging.getLogger("test.packet.metric_validation.small"),
    )

    trinity_ref = store.put_json(
        {"trinity": {}},
        PutOptions(
            kind="ir.trinity_bundle",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.ir.TrinityBundle", version="1.0"),
        ),
    )
    state_snapshot_ref = store.put_json(
        {"state": {}},
        PutOptions(kind="foundry.state_snapshot", media_type="application/json"),
    )
    data_snapshot_ref = store.put_json(
        {
            "data_ref": {
                "artifact_id": str(state_snapshot_ref.artifact_id),
                "kind": "foundry.state_snapshot",
                "media_type": "application/json",
            }
        },
        PutOptions(kind="fabric.data_snapshot", media_type="application/json"),
    )
    metrics_ref = store.put_json(
        Metrics(values={"accuracy": 0.76}),
        PutOptions(kind="foundry.metrics", media_type="application/json"),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    metric_validation_ref = persist_metric_validation_report(
        store,
        MetricValidationReport(
            report_id="mvr_packet_small",
            dataset_id="holdout_v1",
            task="binary",
            checked_at="2026-04-21T12:00:00Z",
            family_adjustment=FamilyAdjustment(
                method="holm",
                alpha=0.05,
                hypotheses_total=1,
                error_rate_target="FWER",
                dependency_assumption="arbitrary",
            ),
            comparisons=(
                MetricComparisonResult(
                    metric_id="accuracy",
                    metric_direction="higher_is_better",
                    baseline_model_id="baseline",
                    candidate_model_id="candidate",
                    baseline_value=0.71,
                    candidate_value=0.76,
                    delta_value=0.05,
                    significance=SignificanceRecord(
                        test_id="mcnemar_exact",
                        null_hypothesis="Accuracy(candidate) - Accuracy(baseline) = 0",
                        alternative="greater",
                        p_value_raw=0.02,
                        p_value_adj=0.02,
                        alpha=0.05,
                        reject_null_raw=True,
                        reject_null_adj=True,
                    ),
                    family_id="holdout_v1:baseline_vs_candidate",
                    family_scope="per_candidate",
                ),
            ),
        ),
    )

    state = ExperimentState(
        run_id="R_packet_metric_validation_small",
        inputs={
            INPUT_TRINITY_BUNDLE_REF: trinity_ref,
            INPUT_REGISTRY_BUNDLE_REF: registry_bundle,
            INPUT_DATA_SNAPSHOT_REF: data_snapshot_ref,
        },
        artifacts_index={
            ARTIFACT_METRICS_REF: metrics_ref,
            ARTIFACT_METRIC_VALIDATION_REPORT_REF: metric_validation_ref,
        },
        params={"random_seed": 123},
    )

    outcome = BuildDecisionPacketNode().execute(ctx, state)
    payload = from_canonical_bytes(store.get_bytes(outcome.artifacts[0].artifact_id))

    assert payload["metric_validation_report_ref"] == str(metric_validation_ref.artifact_id)
    assert payload["metric_validation_family_adjustment"] == {
        "alpha": 0.05,
        "dependency_assumption": "arbitrary",
        "error_rate_target": "FWER",
        "hypotheses_total": 1,
        "method": "holm",
    }
    assert payload["metric_validation_comparisons"] == [
        {
            "alpha": 0.05,
            "assumption_warnings": [],
            "baseline_model_id": "baseline",
            "baseline_value": 0.71,
            "calibration_warnings": [],
            "candidate_model_id": "candidate",
            "candidate_value": 0.76,
            "ci_high": None,
            "ci_level": None,
            "ci_low": None,
            "delta_value": 0.05,
            "effect_size": None,
            "family_id": "holdout_v1:baseline_vs_candidate",
            "family_scope": "per_candidate",
            "metric_direction": "higher_is_better",
            "metric_id": "accuracy",
            "p_adj": 0.02,
            "p_value": 0.02,
            "resampling_method": None,
            "sample_size_effective": None,
            "significant": True,
            "statistic": None,
            "test_id": "mcnemar_exact",
            "test_label": "McNemar exact",
        }
    ]
    assert payload["metric_significance_summary"]["comparison_count"] == 1
