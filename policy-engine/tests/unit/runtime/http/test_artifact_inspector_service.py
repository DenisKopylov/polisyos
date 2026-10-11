from __future__ import annotations

import json

from polisyos.core.artifacts import FileSystemCAS, PutOptions, SchemaInfo
from polisyos.core.canon.canon_json import CanonSpec
from polisyos.runtime.http.services.artifact_inspector import ArtifactInspectorService
from polisyos.runtime.http.services.lineage import LineageService


def _authority_boundary() -> dict[str, object]:
    return {
        "boundary_id": "boundary-inspector-test",
        "authoritative_for": ["runtime_closeout_authority"],
        "may_not_use_for": ["publication"],
        "source_authority": "inspector_test_fixture",
        "posture": "governed",
        "rule_version_refs": ["policyos.test.authority.v1"],
        "evidence_kind": "measurement",
        "decision_grade": "decision_admissible",
    }


def test_redaction_hook_failure_fails_closed(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    ref = store.put_bytes(
        json.dumps(
            {
                "authority_boundary": _authority_boundary(),
                "value": "safe preview text",
            }
        ).encode("utf-8"),
        PutOptions(kind="test.preview", media_type="application/json"),
    )
    service = ArtifactInspectorService(
        store=store,
        lineage_service=LineageService(store=store),
        redaction_hooks={
            "test.preview": lambda preview, mode: (_ for _ in ()).throw(RuntimeError("boom"))
        },
    )

    preview = service.get_content_preview(ref.artifact_id)

    assert preview.preview == "[REDACTED]"


def test_predictive_content_sidecar_requires_the_candidate_surface_opt_in(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    payload = {
        "authority_boundary": _authority_boundary(),
        "schema_version": "1.0",
        "report_id": "predictive-content-opt-in",
        "metadata": {
            "estimand": "predictive_interval_coverage",
            "authority_scope": "predictive_only",
            "bridge_status": "bridge_pending",
        },
        "degraded_reasons": ["trust_screening:predictive_only_bridge_pending"],
        "degraded": True,
        "trust_eligible": False,
        "trust_score": None,
        "n_scenarios": 1,
        "scenarios": [
            {
                "scenario_id": "one-scenario",
                "requested_count": 1,
                "compared_count": 1,
                "missing_count": 0,
                "invalid_count": 0,
                "interval_requested_count": 1,
                "interval_available_count": 1,
                "interval_evaluated_count": 1,
                "interval_hit_count": 1,
                "interval_hit_rate": 1.0,
                "coverage_probability": 1.0,
                "nominal_confidence_level": 0.9,
                "interval_type": "prediction",
                "outcome_comparisons": [
                    {
                        "metric_name": "metric",
                        "y_true": 2.0,
                        "ci_lower": 1.0,
                        "ci_upper": 3.0,
                        "within_ci": True,
                    }
                ],
            }
        ],
    }
    ref = store.put_json(
        payload,
        PutOptions(
            kind="ir.backtest_report",
            media_type="application/json",
            schema=SchemaInfo(name="ir.backtest_report", version="1.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    service = ArtifactInspectorService(
        store=store,
        lineage_service=LineageService(store=store),
    )

    default_preview = service.get_content_preview(ref.artifact_id)
    opted_in_preview = service.get_content_preview(
        ref.artifact_id,
        allow_candidate_predictive_diagnostic_surface=True,
    )

    assert default_preview.predictive_coverage_diagnostic is None
    assert opted_in_preview.predictive_coverage_diagnostic is not None
    assert (
        opted_in_preview.predictive_coverage_diagnostic.source_materialization
        == "reader_materialized"
    )


def test_decision_packet_preview_adds_typed_sidecar(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    payload = {
        "authority_boundary": _authority_boundary(),
        "document_outline": [
            {
                "section_id": "policy_answer",
                "section_type": "policy",
                "title": "Recommendation",
            }
        ],
        "metric_significance_by_metric": {
            "gdp_change": {
                "effect_size": 0.23,
                "p_value": 0.02,
                "test_id": "paired_t",
                "test_label": "Paired t test",
            }
        },
        "metric_validation_comparison_rows": [
            {
                "metric_id": "gdp_change",
                "effect_size": 0.23,
                "ci_low": 0.12,
                "ci_high": 0.34,
                "resampling_method": "analytic",
                "test_id": "paired_t",
            }
        ],
    }
    ref = store.put_bytes(
        json.dumps(payload).encode("utf-8"),
        PutOptions(
            kind="scientist.decision_packet",
            media_type="application/json",
        ),
    )
    service = ArtifactInspectorService(
        store=store,
        lineage_service=LineageService(store=store),
    )

    preview = service.get_content_preview(ref.artifact_id)

    assert preview.decision_packet_preview is not None
    assert preview.decision_packet_preview.document_outline[0].section_type == "policy"
    structured_effect = preview.decision_packet_preview.metric_significance_by_metric[
        "gdp_change"
    ].effect_size
    assert structured_effect is not None
    assert structured_effect.point == 0.23
    assert structured_effect.ci_95 == (0.12, 0.34)
    assert structured_effect.method == "analytic"
