from __future__ import annotations

import logging

from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.ir.analytics.distributional import (
    CohortDimension,
    CohortImpact,
    DimensionBreakdown,
    DistributionalReport,
    ImpactDirection,
    MetricUnit,
    persist_distributional_report,
)
from polisyos.ir.analytics.uncertainty import (
    DistributionFamily,
    IntervalSemantics,
    PropagationMethod,
    UncertaintyEnvelope,
    UncertaintySource,
    persist_uncertainty_envelope,
)
from polisyos.scientist.engine.context import ExecutionContext
from polisyos.scientist.engine.state import ExperimentState
from polisyos.scientist.nodes.builtins.decide.build_decision_packet import BuildDecisionPacketNode
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_DISTRIBUTIONAL_REPORT_REF,
    ARTIFACT_ECONOMETRIC_ENVELOPE_REF,
    ARTIFACT_ECONOMETRIC_EVIDENCE_REF,
    ARTIFACT_ECONOMETRIC_RESULT_REF,
    INPUT_DATA_SNAPSHOT_REF,
    INPUT_REGISTRY_BUNDLE_REF,
    INPUT_TRINITY_BUNDLE_REF,
)


def test_decision_packet_includes_distributional_and_econometric_sections(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(store=store, registry_bundle=registry_bundle, run_id="R_packet_dist")
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger("test.packet.dist"))

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

    distributional_ref = persist_distributional_report(
        store,
        DistributionalReport(
            breakdowns=[
                DimensionBreakdown(
                    dimension=CohortDimension.INCOME_QUINTILE,
                    dimension_label="Income Quintiles",
                    primary_metric="income_change_pct",
                    primary_metric_unit=MetricUnit.PERCENT,
                    cohorts=[
                        CohortImpact(
                            cohort_id="Q1",
                            cohort_label="Q1",
                            population_share=0.5,
                            metric_deltas={"income_change_pct": -2.0},
                            impact_direction=ImpactDirection.NEGATIVE,
                            is_vulnerable=True,
                        ),
                        CohortImpact(
                            cohort_id="Q5",
                            cohort_label="Q5",
                            population_share=0.5,
                            metric_deltas={"income_change_pct": 3.0},
                            impact_direction=ImpactDirection.POSITIVE,
                        ),
                    ],
                )
            ]
        ),
    )

    econometric_result_ref = store.put_json(
        {
            "result": {
                "method_name": "iv_2sls",
                "params": {"x_endog": 2},
                "std_errors": {"x_endog": 1},
            }
        },
        PutOptions(kind="scientist.method_result.econometrics.iv", media_type="application/json"),
    )
    econometric_evidence_ref = store.put_json(
        {"method_fqn": "econometrics.iv.two_stage_least_squares@1.0.0"},
        PutOptions(kind="scientist.method_evidence", media_type="application/json"),
    )
    econometric_envelope_ref = persist_uncertainty_envelope(
        store,
        UncertaintyEnvelope(
            point_estimate=1.8,
            confidence_interval=(1.4, 2.2),
            confidence_level=0.95,
            distribution_family=DistributionFamily.NORMAL,
            source=UncertaintySource.CAUSAL,
            propagation_method=PropagationMethod.NONE,
            interval_semantics=IntervalSemantics.CONFIDENCE_INTERVAL,
        ),
    )

    state = ExperimentState(
        run_id="R_packet_dist",
        inputs={
            INPUT_TRINITY_BUNDLE_REF: trinity_ref,
            INPUT_REGISTRY_BUNDLE_REF: registry_bundle,
            INPUT_DATA_SNAPSHOT_REF: data_snapshot_ref,
        },
        artifacts_index={
            ARTIFACT_DISTRIBUTIONAL_REPORT_REF: distributional_ref,
            ARTIFACT_ECONOMETRIC_RESULT_REF: econometric_result_ref,
            ARTIFACT_ECONOMETRIC_EVIDENCE_REF: econometric_evidence_ref,
            ARTIFACT_ECONOMETRIC_ENVELOPE_REF: econometric_envelope_ref,
        },
    )

    outcome = BuildDecisionPacketNode().execute(ctx, state)
    packet_ref = outcome.artifacts[0]
    payload = from_canonical_bytes(store.get_bytes(packet_ref.artifact_id))

    assert payload["artifacts"]["distributional_report_ref"] == str(distributional_ref.artifact_id)
    assert payload["distributional"]["report_ref"] == str(distributional_ref.artifact_id)
    assert payload["econometrics"]["result_ref"] == str(econometric_result_ref.artifact_id)
    assert payload["econometrics"]["envelope_ref"] == str(econometric_envelope_ref.artifact_id)
    assert payload["uncertainty_bounds"]["econometric_effect_point"] == 1.8
