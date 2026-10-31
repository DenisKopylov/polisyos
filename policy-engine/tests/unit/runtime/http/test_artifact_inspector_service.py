from __future__ import annotations

from polisyos.core.artifacts import (
    CanonInfo,
    FileSystemCAS,
    PutOptions,
    SchemaInfo,
    input_ref_from_artifact_ref,
)
from polisyos.core.artifacts.canonical_profile import (
    CoreJsonReadBoundsRefusalError,
    CoreJsonReadLimits,
    read_core_json_artifact_bounded,
)
from polisyos.core.canon import to_canonical_bytes
from polisyos.core.canon.canon_json import CORE_TAG_POLICY_ID, CanonSpec
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
        to_canonical_bytes(
            {
                "authority_boundary": _authority_boundary(),
                "value": "safe preview text",
            }
        ),
        PutOptions(kind="test.preview", media_type="application/json", canon=CanonInfo()),
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


def test_predictive_content_sidecar_requires_the_candidate_surface_opt_in(
    tmp_path,
) -> None:
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
    assert opted_in_preview.predictive_coverage_diagnostic.measurement_status == "not_measured"
    assert opted_in_preview.predictive_coverage_diagnostic.reason_code == "unsupported_report_scope"
    assert opted_in_preview.predictive_coverage_diagnostic.scenarios == []

    # Preserve the exact report bytes and put native evidence only in the
    # selected cohort edge. The bounded preview cannot verify that trajectory.
    native_ref = store.put_json(
        {"candidate": "native"},
        PutOptions(kind="scientist.backtest.native_forecast", media_type="application/json"),
        return_selected_profile=True,
    )
    cohort_ref = store.put_json(
        {"replica": 1},
        PutOptions(
            kind="scientist.backtest.replica_cohort",
            media_type="application/json",
            inputs=[input_ref_from_artifact_ref(native_ref, role="native_forecast:1")],
        ),
        return_selected_profile=True,
    )
    sibling = store.put_json(
        payload,
        PutOptions(
            kind="ir.backtest_report",
            media_type="application/json",
            schema=SchemaInfo(name="ir.backtest_report", version="1.0"),
            inputs=[input_ref_from_artifact_ref(cohort_ref, role="replica_cohort:one-scenario")],
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    assert sibling.artifact_id == ref.artifact_id
    sibling_manifest = store.get_manifest(sibling)
    diagnostic = service.get_predictive_coverage_diagnostic(
        sibling.artifact_id, manifest=sibling_manifest
    )
    assert diagnostic is not None
    assert diagnostic.measurement_status == "not_measured"
    assert diagnostic.reason_code == "unsupported_report_scope"
    assert diagnostic.scenarios == []
    raw_preview = service.get_content_preview(
        sibling.artifact_id,
        manifest=sibling_manifest,
        allow_candidate_predictive_diagnostic_surface=True,
    )
    assert raw_preview.preview == opted_in_preview.preview
    assert raw_preview.predictive_coverage_diagnostic == diagnostic

    legacy_cohort = store.put_json(
        {"replica": "legacy"},
        PutOptions(kind="scientist.backtest.replica_cohort", media_type="application/json"),
        return_selected_profile=True,
    )
    legacy_report = store.put_json(
        payload,
        PutOptions(
            kind="ir.backtest_report",
            media_type="application/json",
            schema=SchemaInfo(name="ir.backtest_report", version="1.0"),
            inputs=[input_ref_from_artifact_ref(legacy_cohort, role="replica_cohort:one-scenario")],
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    legacy_diagnostic = service.get_predictive_coverage_diagnostic(
        legacy_report.artifact_id, manifest=store.get_manifest(legacy_report)
    )
    assert legacy_diagnostic is not None
    assert legacy_diagnostic.measurement_status == "not_measured"
    assert legacy_diagnostic.reason_code == "unsupported_report_scope"

    # These are structurally valid synthetic interval payloads, not native
    # interval production. Retained native modes or reasons still prevent a
    # measurement even when native metadata and edges have been stripped.
    from copy import deepcopy

    for marker in ("scenario_mode", "report_mode", "reason", "replica_projection"):
        changed_payload = deepcopy(payload)
        if marker == "scenario_mode":
            changed_payload["prediction_mode_effective"] = "mixed"
            changed_payload["scenarios"][0]["metadata"] = {
                "prediction_source_effective": "scientist_candidate"
            }
        elif marker == "report_mode":
            changed_payload["prediction_mode_effective"] = "scientist_unavailable"
        elif marker == "reason":
            changed_payload["degraded_reasons"].append(
                "one-scenario: native_temporal_mapping_not_established"
            )
        else:
            changed_payload["scenarios"][0]["metadata"] = {"native_replica_projection": {}}
        changed_ref = store.put_json(
            changed_payload,
            PutOptions(
                kind="ir.backtest_report",
                media_type="application/json",
                schema=SchemaInfo(name="ir.backtest_report", version="1.0"),
            ),
            canon_spec=CanonSpec(forbid_floats=False),
            return_selected_profile=True,
        )
        changed_diagnostic = service.get_predictive_coverage_diagnostic(
            changed_ref.artifact_id, manifest=store.get_manifest(changed_ref)
        )
        assert changed_diagnostic is not None
        assert changed_diagnostic.measurement_status == "not_measured"
        assert changed_diagnostic.reason_code == "unsupported_report_scope"


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
    spec = CanonSpec(forbid_floats=False)
    ref = store.put_bytes(
        to_canonical_bytes(payload, spec),
        PutOptions(
            kind="scientist.decision_packet",
            media_type="application/json",
            canon=CanonInfo(forbid_floats=False),
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


def test_bounded_json_inspection_refuses_before_reading_over_cap_bytes(
    tmp_path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    payload = to_canonical_bytes({"large": "x" * 1_200})
    ref = store.put_bytes(
        payload,
        PutOptions(
            kind="test.bounded_preview",
            media_type="application/json",
            schema=SchemaInfo(name="test.bounded_preview", version="1"),
            canon=CanonInfo(),
        ),
        return_selected_profile=True,
    )
    manifest = store.get_manifest_by_profile(ref.artifact_id, ref.manifest_profile_sha256)

    class ReadSpy:
        def __init__(self, target):
            self.target = target
            self.bounded_opens = 0
            self.get_bytes_calls = 0

        def __getattr__(self, name):
            return getattr(self.target, name)

        def open_member_bounded(self, *args, **kwargs):
            self.bounded_opens += 1
            return self.target.open_member_bounded(*args, **kwargs)

        def get_bytes(self, selector):
            self.get_bytes_calls += 1
            return self.target.get_bytes(selector)

    observed_store = ReadSpy(store)
    service = ArtifactInspectorService(
        store=observed_store,
        lineage_service=LineageService(store=store),
        default_max_preview_bytes=1024,
    )

    try:
        service.get_content_preview(ref.artifact_id, max_bytes=1024, manifest=manifest)
    except CoreJsonReadBoundsRefusalError as exc:
        refusal = exc
    else:
        raise AssertionError("over-limit JSON was materialized")

    assert refusal.code == "canon_profile_bounded_bytes_exceeded"
    assert refusal.limit_name == "max_bytes"
    assert refusal.observed_payload_bytes == 0
    assert refusal.observed_payload_size == len(payload)
    assert refusal.payload_integrity_verified is False
    assert observed_store.bounded_opens == 1
    assert observed_store.get_bytes_calls == 0


def test_small_json_inspection_records_core_policy_and_uses_bounded_owner(
    tmp_path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    payload = {
        "authority_boundary": _authority_boundary(),
        "value": "selected",
    }
    ref = store.put_bytes(
        to_canonical_bytes(payload),
        PutOptions(
            kind="test.bounded_preview",
            media_type="application/json",
            schema=SchemaInfo(name="test.bounded_preview", version="1"),
            canon=CanonInfo(),
        ),
        return_selected_profile=True,
    )
    service = ArtifactInspectorService(
        store=store,
        lineage_service=LineageService(store=store),
        default_max_preview_bytes=1024,
    )

    preview = service.get_content_preview(ref.artifact_id)

    assert preview.mode == "json"
    assert preview.preview == payload
    assert preview.canon_read_status == "declared_bytes_conformant"
    bounded = read_core_json_artifact_bounded(
        store,
        ref,
        limits=CoreJsonReadLimits(
            max_bytes=1024,
            max_depth=128,
            max_elements=100_000,
            max_manifest_bytes=1_000_000,
        ),
    )
    assert bounded.profile_read.reader_policy_id == CORE_TAG_POLICY_ID
    assert ref.manifest_profile_sha256 is not None


def _actual_hte_wire_fixture(name: str) -> dict[str, object]:
    import json
    from pathlib import Path

    overlay_root = Path(__file__).resolve().parents[4]
    fixture = (
        overlay_root / "apps/runtime-dashboard/src/features/artifacts/domain/__test__/wire" / name
    )
    return json.loads(fixture.read_text())


def _decision_packet_preview_with_hte(tmp_path, hte: object):
    store = FileSystemCAS(tmp_path / "cas")
    payload = {"authority_boundary": _authority_boundary(), "hte": hte}
    ref = store.put_bytes(
        to_canonical_bytes(payload, CanonSpec(forbid_floats=False)),
        PutOptions(
            kind="scientist.decision_packet",
            media_type="application/json",
            canon=CanonInfo(forbid_floats=False),
        ),
    )
    service = ArtifactInspectorService(
        store=store,
        lineage_service=LineageService(store=store),
    )
    return service.get_content_preview(ref.artifact_id)


def test_decision_packet_hte_null_is_explicitly_absent(tmp_path) -> None:
    preview = _decision_packet_preview_with_hte(tmp_path, None)

    sidecar = preview.decision_packet_preview
    assert sidecar is not None
    assert sidecar.hte_projection_status == "absent"
    assert sidecar.hte is None
    assert sidecar.hte_legacy_limited is None


def test_decision_packet_hte_parses_actual_runtime_json_dto_with_tuple_fields(
    tmp_path,
) -> None:
    summary = _actual_hte_wire_fixture("runtime-r5-point-owner-builder.json")

    preview = _decision_packet_preview_with_hte(tmp_path, summary)

    sidecar = preview.decision_packet_preview
    assert sidecar is not None
    assert sidecar.hte_projection_status == "typed"
    assert sidecar.hte is not None
    assert sidecar.hte.kind == "point_estimate"
    assert sidecar.hte.hte_result_ref is None
    assert sidecar.hte.point_result_ref is not None


def test_decision_packet_hte_legacy_builder_wire_is_limited_and_unlinked(
    tmp_path,
) -> None:
    legacy = _actual_hte_wire_fixture("legacy-builder-wire.json")

    preview = _decision_packet_preview_with_hte(tmp_path, legacy)

    sidecar = preview.decision_packet_preview
    assert sidecar is not None
    assert sidecar.hte_projection_status == "legacy_limited"
    assert sidecar.hte is None
    limited = sidecar.hte_legacy_limited
    assert limited is not None
    assert limited.kind == "legacy_limited"
    assert limited.availability == "available"
    assert limited.source_result_ref == legacy["result_ref"]
    assert limited.ate == legacy["ate"]
    assert limited.bounds_meaning_status == "not_established"
    assert limited.conditional_coverage_status == "not_established"
    assert limited.population_coverage_status == "not_established"
    assert limited.authority_status == "limited_display_only"


def test_decision_packet_hte_parse_failure_has_no_legacy_numbers(tmp_path) -> None:
    legacy = {
        "result_ref": "sha256:" + "d" * 64,
        "parse_warning": "hte_result_parse_failed",
    }

    preview = _decision_packet_preview_with_hte(tmp_path, legacy)

    sidecar = preview.decision_packet_preview
    assert sidecar is not None
    assert sidecar.hte_projection_status == "legacy_limited"
    assert sidecar.hte is None
    limited = sidecar.hte_legacy_limited
    assert limited is not None
    assert limited.availability == "unavailable"
    assert limited.ate is None
    assert limited.ate_ci_lower is None
    assert limited.ate_ci_upper is None
    assert limited.top_features == []
    assert limited.warnings == []
    assert limited.parse_warning == "hte_result_parse_failed"


def test_decision_packet_hte_malformed_modern_never_falls_back_to_legacy(
    tmp_path,
) -> None:
    legacy = _actual_hte_wire_fixture("legacy-builder-wire.json")
    mixed = {
        **legacy,
        "kind": "point_estimate",
        "schema_version": "1.0",
    }

    preview = _decision_packet_preview_with_hte(tmp_path, mixed)

    sidecar = preview.decision_packet_preview
    assert sidecar is not None
    assert sidecar.hte_projection_status == "invalid"
    assert sidecar.hte is None
    assert sidecar.hte_legacy_limited is None
