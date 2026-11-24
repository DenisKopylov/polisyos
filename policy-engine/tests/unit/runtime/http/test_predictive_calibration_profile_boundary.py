from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from polisyos.calibration.forecast_bridge import EmpiricalCalibrationEvidenceRef
from polisyos.core.artifacts.manifest import CanonInfo, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.core.canon import CanonSpec
from polisyos.runtime.http.services import predictive_calibration


class _RawProfileTamperStore:
    """Preserve typed manifest and payload while changing only the supplied raw profile."""

    def __init__(self, store: FileSystemCAS) -> None:
        self._store = store

    def __getattr__(self, name: str) -> Any:
        return getattr(self._store, name)

    def get_raw_manifest_bytes(
        self, selector: object, *, manifest_profile_sha256: str | None = None
    ) -> bytes:
        raw = self._store.get_raw_manifest_bytes(
            selector, manifest_profile_sha256=manifest_profile_sha256
        )
        manifest = self._store.get_manifest(selector)
        if manifest.kind != predictive_calibration._ASSOCIATION_KIND:
            return raw
        value = json.loads(raw)
        value["canon"]["forbid_floats"] = not value["canon"]["forbid_floats"]
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def test_evidence_ref_adapter_preserves_exact_selected_core_view(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "empirical-evidence-ref-cas")
    ref = store.put_bytes(
        b"{}",
        ArtifactWriteOptions(
            kind="ir.empirical_calibration_evidence",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.calibration.empirical_calibration_evidence",
                version="1.2",
            ),
            canon=CanonInfo.from_spec(CanonSpec(forbid_floats=False)),
        ),
        return_selected_profile=True,
    )
    assert ref.manifest_profile_sha256 is not None

    adapted = predictive_calibration._as_ir_empirical_calibration_evidence_ref(ref)
    assert isinstance(adapted, EmpiricalCalibrationEvidenceRef)
    assert adapted.model_dump(mode="json") == {
        "artifact_id": str(ref.artifact_id),
        "kind": ref.kind,
        "media_type": ref.media_type,
        "manifest_profile_sha256": ref.manifest_profile_sha256,
    }

    profileless = ref.model_copy(update={"manifest_profile_sha256": None})
    assert (
        predictive_calibration._as_ir_empirical_calibration_evidence_ref(
            profileless
        ).manifest_profile_sha256
        is None
    )
    with pytest.raises(ValueError):
        predictive_calibration._as_ir_empirical_calibration_evidence_ref(
            ref.model_copy(update={"kind": "ir.backtest_report"})
        )


def test_association_event_read_refuses_raw_selected_profile_drift_before_dto(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "predictive-profile-cas")
    schema = SchemaInfo(
        name=predictive_calibration._ASSOCIATION_SCHEMA,
        version=predictive_calibration._ASSOCIATION_VERSION,
    )
    ref = store.put_bytes(
        b"{}",
        ArtifactWriteOptions(
            kind=predictive_calibration._ASSOCIATION_KIND,
            media_type="application/json",
            schema=schema,
            canon=CanonInfo.from_spec(CanonSpec()),
        ),
        return_selected_profile=True,
    )
    assert ref.manifest_profile_sha256 is not None

    with pytest.raises(predictive_calibration.PredictiveCalibrationError) as refusal:
        predictive_calibration._load_association(_RawProfileTamperStore(store), ref)
    assert refusal.value.code == "predictive_calibration_association_profile_unverified"


def test_n4_outcome_binding_record_never_equates_identifier_strings() -> None:
    """A matching metric string alone cannot establish the source relation."""
    from types import SimpleNamespace

    from polisyos.runtime.http.services.predictive_calibration import (
        _N4_OUTCOME_BINDING_LIMITATION_CODE,
        _n4_outcome_target_binding_record,
    )

    candidate_source = SimpleNamespace(
        problem=SimpleNamespace(
            outcome_of_interest=SimpleNamespace(
                target_variable="policy_outcome",
                metric_id="policy_outcome_metric",
            )
        )
    )
    matching_name = _n4_outcome_target_binding_record(candidate_source, "policy_outcome_metric")
    sibling_column = _n4_outcome_target_binding_record(candidate_source, "observed_panel_column")
    assert matching_name["status"] == sibling_column["status"] == "not_established"
    assert (
        matching_name["reason_code"]
        == sibling_column["reason_code"]
        == (_N4_OUTCOME_BINDING_LIMITATION_CODE)
    )
    assert matching_name["n4_target_variable"] == "policy_outcome"
    assert matching_name["n4_metric_id"] == "policy_outcome_metric"
    assert matching_name["observed_target_metric"] == "policy_outcome_metric"
    assert sibling_column["observed_target_metric"] == "observed_panel_column"


def test_legacy_s10_pass_does_not_match_fresh_blocked_n4_tier() -> None:
    """Fresh readback rejects a legacy N4 pass whose target relation is absent."""
    from polisyos.runtime.http.services.predictive_calibration import (
        _ASSOCIATION_SCHEMA,
        _LEGACY_ASSOCIATION_SCHEMA,
        PredictiveCalibrationS10Summary,
        _s10_summary_matches,
    )

    legacy = PredictiveCalibrationS10Summary(
        calibration_status="pass",
        forecast_tier="observable_calibrated",
        counterfactual_credibility="not_established",
        numerator=2,
        denominator=2,
        observed_pass_rate=1.0,
        calibration_record_ref="s10://calibration/legacy",
    )
    from polisyos.runtime.quality.design_axes.outcome_prediction import (
        build_prediction_authority_boundary,
    )

    authority_boundary = build_prediction_authority_boundary()
    recomputed = PredictiveCalibrationS10Summary(
        calibration_status="pass",
        forecast_tier="blocked",
        counterfactual_credibility="not_established",
        numerator=2,
        denominator=2,
        observed_pass_rate=1.0,
        calibration_record_ref="s10://calibration/legacy",
        outcome_binding_status="not_established",
        limitation_refs=(
            "s10://calibration/fail-closed/n4_outcome_target_binding_not_established",
        ),
        authority_boundary=authority_boundary,
        may_not_use_for=tuple(authority_boundary.may_not_use_for),
    )
    assert not _s10_summary_matches(
        legacy,
        recomputed,
        association_schema_version=_LEGACY_ASSOCIATION_SCHEMA,
        candidate_source_kind="runtime.quality.n4_candidate_scenario_source",
    )
    assert _s10_summary_matches(
        recomputed,
        recomputed,
        association_schema_version=_ASSOCIATION_SCHEMA,
        candidate_source_kind="runtime.quality.n4_candidate_scenario_source",
    )
    legacy_limited = recomputed.model_copy(
        update={"authority_boundary": None, "may_not_use_for": None}
    )
    assert not _s10_summary_matches(
        legacy_limited,
        recomputed,
        association_schema_version=_LEGACY_ASSOCIATION_SCHEMA,
        candidate_source_kind="runtime.quality.n4_candidate_scenario_source",
    )

    # Matching the seven predictive-grade fields at the same blocked tier
    # cannot substitute for the fresh N4 binding limitation and owner denials.
    same_tier_legacy = PredictiveCalibrationS10Summary(
        calibration_status=recomputed.calibration_status,
        forecast_tier=recomputed.forecast_tier,
        counterfactual_credibility=recomputed.counterfactual_credibility,
        numerator=recomputed.numerator,
        denominator=recomputed.denominator,
        observed_pass_rate=recomputed.observed_pass_rate,
        calibration_record_ref=recomputed.calibration_record_ref,
    )
    assert not _s10_summary_matches(
        same_tier_legacy,
        recomputed,
        association_schema_version=_LEGACY_ASSOCIATION_SCHEMA,
        candidate_source_kind="runtime.quality.n4_candidate_scenario_source",
    )

    # A non-N4 v2 caller keeps the original standalone predictive-grade
    # comparison even when later optional S10 projection fields differ.
    changed_optional_projection = recomputed.model_copy(
        update={"limitation_refs": (), "authority_boundary": None, "may_not_use_for": None}
    )
    assert _s10_summary_matches(
        recomputed,
        changed_optional_projection,
        association_schema_version=_LEGACY_ASSOCIATION_SCHEMA,
        candidate_source_kind="runtime.predictive_forecast",
    )


def _historical_association_payload(schema_version: str) -> dict[str, Any]:
    """Retain legacy numeric bytes independently of the current nullable example."""
    from copy import deepcopy

    from polisyos.runtime.http.openapi_contract import _predictive_calibration_success_examples

    payload = deepcopy(
        _predictive_calibration_success_examples()["controlled_insufficient_history_candidate"][
            "value"
        ]["association"]
    )
    payload.update(
        schema_version=schema_version,
        observed_numerator=1,
        observed_denominator=2,
        observed_hit_rate=0.5,
        evidence_reason_codes=[],
    )
    payload["s10"].update(
        calibration_status="limit",
        numerator=1,
        denominator=2,
        observed_pass_rate=0.5,
        calibration_record_ref="s10://historical/calibration",
    )
    return payload


def test_legacy_v2_n4_requires_complete_owner_projection_before_fresh_get() -> None:
    """Persisted v2 N4 rows without the current owner projection fail closed."""
    from copy import deepcopy

    from pydantic import ValidationError

    from polisyos.runtime.http.services.predictive_calibration import (
        _LEGACY_ASSOCIATION_SCHEMA,
        PredictiveCalibrationAssociation,
    )

    fresh_payload = _historical_association_payload(_LEGACY_ASSOCIATION_SCHEMA)

    same_tier_legacy = deepcopy(fresh_payload)
    same_tier_legacy["schema_version"] = _LEGACY_ASSOCIATION_SCHEMA
    for field in (
        "outcome_binding_status",
        "limitation_refs",
        "authority_boundary",
        "may_not_use_for",
    ):
        same_tier_legacy["s10"].pop(field, None)
    assert same_tier_legacy["s10"]["forecast_tier"] == "blocked"
    with pytest.raises(ValidationError, match="predictive_calibration_n4_outcome_binding"):
        PredictiveCalibrationAssociation.model_validate(same_tier_legacy)

    legacy_with_binding_markers_but_no_owner_boundary = deepcopy(fresh_payload)
    legacy_with_binding_markers_but_no_owner_boundary["schema_version"] = _LEGACY_ASSOCIATION_SCHEMA
    legacy_with_binding_markers_but_no_owner_boundary["s10"].pop("authority_boundary")
    legacy_with_binding_markers_but_no_owner_boundary["s10"].pop("may_not_use_for")
    legacy_with_binding_markers_but_no_owner_boundary.pop("may_not_use_for")
    with pytest.raises(ValidationError, match="predictive_calibration_n4_outcome_binding"):
        PredictiveCalibrationAssociation.model_validate(
            legacy_with_binding_markers_but_no_owner_boundary
        )

    # An already complete historical row remains parseable as v2. A current
    # nullable projection cannot silently reuse its old observed grade.
    complete_v2 = deepcopy(fresh_payload)
    complete_v2["schema_version"] = _LEGACY_ASSOCIATION_SCHEMA
    reopened = PredictiveCalibrationAssociation.model_validate(complete_v2)
    current = PredictiveCalibrationAssociation.model_validate(_unverified_v5_association_payload())
    assert reopened.schema_version == _LEGACY_ASSOCIATION_SCHEMA
    assert reopened.s10 != current.s10
    assert not predictive_calibration._s10_summary_matches(
        reopened.s10,
        current.s10,
        association_schema_version=_LEGACY_ASSOCIATION_SCHEMA,
        candidate_source_kind="runtime.quality.n4_candidate_scenario_source",
    )


def test_persisted_legacy_v2_n4_without_owner_projection_is_typed_refusal(tmp_path) -> None:
    """The selected CAS GET reader maps unsafe old N4 bytes to a typed refusal."""

    from polisyos.core.artifacts import ArtifactRef
    from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
    from polisyos.core.canon import to_canonical_bytes
    from polisyos.runtime.http.services.predictive_calibration import (
        _ASSOCIATION_KIND,
        _LEGACY_ASSOCIATION_SCHEMA,
        _LEGACY_ASSOCIATION_VERSION,
        PredictiveCalibrationError,
        _load_association,
    )

    payload = _historical_association_payload(_LEGACY_ASSOCIATION_SCHEMA)
    payload["schema_version"] = _LEGACY_ASSOCIATION_SCHEMA
    for field in (
        "outcome_binding_status",
        "limitation_refs",
        "authority_boundary",
        "may_not_use_for",
    ):
        payload["s10"].pop(field, None)

    store = FileSystemCAS(tmp_path / "legacy-v2-n4-admission")
    ref = store.put_bytes(
        to_canonical_bytes(payload, CanonSpec(forbid_floats=False)),
        ArtifactWriteOptions(
            kind=_ASSOCIATION_KIND,
            media_type="application/json",
            schema=SchemaInfo(name=_LEGACY_ASSOCIATION_SCHEMA, version=_LEGACY_ASSOCIATION_VERSION),
            canon=CanonInfo.from_spec(CanonSpec(forbid_floats=False)),
        ),
        return_selected_profile=True,
    )
    assert isinstance(ref, ArtifactRef)
    assert ref.manifest_profile_sha256 is not None
    with pytest.raises(PredictiveCalibrationError) as refusal:
        _load_association(store, ref)
    assert refusal.value.code == "predictive_calibration_association_invalid"


def test_v3_association_requires_owner_s10_authority_projection() -> None:
    """N4 markers alone cannot stand in for the owner authority envelope."""
    from pydantic import ValidationError

    from polisyos.runtime.http.services.predictive_calibration import (
        PredictiveCalibrationAssociation,
    )

    payload = _historical_association_payload(predictive_calibration._PRIOR_ASSOCIATION_SCHEMA)
    payload["s10"].pop("authority_boundary")
    with pytest.raises(ValidationError, match="predictive_calibration_n4_outcome_binding"):
        PredictiveCalibrationAssociation.model_validate(payload)

    payload = _historical_association_payload(predictive_calibration._PRIOR_ASSOCIATION_SCHEMA)
    payload["s10"]["may_not_use_for"].append("new_owner_denial")
    with pytest.raises(ValidationError, match="predictive_calibration_n4_outcome_binding"):
        PredictiveCalibrationAssociation.model_validate(payload)


@pytest.mark.parametrize(
    "transported_tier",
    [
        "observable_calibrated",
        "transported_limited",
        "simulation_only_advisory",
        "future_unknown_tier",
    ],
)
def test_v3_association_rejects_every_tier_except_blocked_for_unbound_n4(
    transported_tier: str,
) -> None:
    """The API rejects aliases and future values with binding markers left intact."""
    from pydantic import ValidationError

    from polisyos.runtime.http.services.predictive_calibration import (
        PredictiveCalibrationAssociation,
    )

    payload = _historical_association_payload(predictive_calibration._PRIOR_ASSOCIATION_SCHEMA)
    assert payload["s10"]["outcome_binding_status"] == "not_established"
    assert "n4_outcome_target_binding_not_established" in " ".join(
        payload["s10"]["limitation_refs"]
    )
    payload["s10"]["forecast_tier"] = transported_tier
    with pytest.raises(ValidationError, match="predictive_calibration_n4_outcome_binding"):
        PredictiveCalibrationAssociation.model_validate(payload)


def _unverified_v5_association_payload() -> dict[str, Any]:
    """Use a public-shaped candidate while explicitly withholding observations."""
    from copy import deepcopy

    from polisyos.runtime.http.openapi_contract import _predictive_calibration_success_examples

    payload = deepcopy(
        _predictive_calibration_success_examples()["controlled_insufficient_history_candidate"][
            "value"
        ]["association"]
    )
    payload.update(
        schema_version=predictive_calibration._V5_ASSOCIATION_SCHEMA,
        observed_numerator=None,
        observed_denominator=None,
        observed_hit_rate=None,
        owner_suitability="limited",
        evidence_reason_codes=["backtest_source_not_established"],
    )
    payload["s10"].update(
        calibration_status="blocked",
        forecast_tier="blocked",
        numerator=None,
        denominator=None,
        observed_pass_rate=None,
        calibration_record_ref=None,
    )
    payload["s10"]["limitation_refs"] = list(
        dict.fromkeys(
            [
                *payload["s10"]["limitation_refs"],
                "s10://calibration/fail-closed/backtest_source_not_established",
            ]
        )
    )
    return payload


def test_reopen_report_target_requires_exact_bundle_and_measured_rows(tmp_path: Path) -> None:
    from polisyos.core.artifacts import ArtifactRef, ensure_ir_artifact_store
    from polisyos.ir import InputRef, load_backtest_report, persist_backtest_report
    from polisyos.scientist.methods.backtesting import ForecastOwner
    from tests.unit.remediation.test_frc_02_owner import _request, _rule, _source

    root = tmp_path / "cas"
    store = FileSystemCAS(root)
    result = ForecastOwner(store).run(
        _request(
            _source(store, holdout=[31.0, 32.0, 33.0, 34.0]),
            _rule(store),
            report_id="frc-selected-target-reopen",
        )
    )
    report_ref = result.backtest_report_ref
    bundle_ref = ArtifactRef.model_validate(result.uncertainty_bundle_ref)
    ir_store = ensure_ir_artifact_store(store)
    report = load_backtest_report(ir_store, report_ref)
    assert "target_metric" not in report.metadata

    def resolve(selected_report, selected_bundle=bundle_ref):
        reader = FileSystemCAS(root)
        reopened = load_backtest_report(ensure_ir_artifact_store(reader), selected_report)
        return predictive_calibration._reopen_report_target_metric(
            reader,
            reopened,
            report_ref=ArtifactRef.model_validate(selected_report),
            bundle_ref=selected_bundle,
        )

    assert resolve(report_ref) == "metric"

    foreign_bundle = store.put_bytes(
        store.get_bytes(bundle_ref),
        ArtifactWriteOptions(
            kind=bundle_ref.kind,
            media_type=bundle_ref.media_type,
            schema=SchemaInfo(name="test.retained_bundle_sibling", version="1.0"),
            canon=store.get_manifest(bundle_ref).canon,
        ),
        return_selected_profile=True,
    )
    assert foreign_bundle.artifact_id == bundle_ref.artifact_id
    assert foreign_bundle.manifest_profile_sha256 != bundle_ref.manifest_profile_sha256
    with pytest.raises(
        predictive_calibration.PredictiveCalibrationError,
        match="predictive_calibration_uncertainty_bundle_binding_mismatch",
    ):
        resolve(report_ref, foreign_bundle)

    report_inputs = [
        InputRef(
            artifact_id=str(edge.artifact_id),
            role=edge.role,
            manifest_profile_sha256=edge.manifest_profile_sha256,
        )
        for edge in store.get_manifest(ArtifactRef.model_validate(report_ref)).inputs
    ]
    altered = persist_backtest_report(
        ir_store,
        report.model_copy(update={"metadata": {**report.metadata, "target_metric": "foreign"}}),
        inputs=report_inputs,
    )
    with pytest.raises(
        predictive_calibration.PredictiveCalibrationError,
        match="predictive_calibration_report_target_metric_mismatch",
    ):
        resolve(altered)


def test_v5_candidate_projection_does_not_advertise_diagnostic_rows_as_observed() -> None:
    """Versioned unavailable values remain null through typed API serialization."""
    association = predictive_calibration.PredictiveCalibrationAssociation.model_validate(
        _unverified_v5_association_payload()
    )
    wire = association.model_dump(mode="json")
    assert wire["observed_numerator"] is None
    assert wire["observed_denominator"] is None
    assert wire["observed_hit_rate"] is None
    assert wire["s10"]["calibration_record_ref"] is None
    assert wire["s10"]["calibration_status"] == "blocked"
    assert "backtest_source_not_established" in wire["evidence_reason_codes"]


def test_v6_replay_keeps_selected_interval_and_v5_replay_keeps_its_original_shape() -> None:
    """Apply exact interval equality to current rows and preserve v5 absence."""
    from copy import deepcopy

    from pydantic import ValidationError

    from polisyos.runtime.http.services.predictive_calibration import (
        _ASSOCIATION_SCHEMA,
        _METHOD_FQN,
        _V5_ASSOCIATION_SCHEMA,
        PredictiveCalibrationAssociation,
        _association_event_version,
        _s10_summary_matches,
    )
    from polisyos.runtime.quality.generation_cycle import _S10_SUPPORT_LIMITATION_PREFIX

    v5_payload = _unverified_v5_association_payload()
    old = PredictiveCalibrationAssociation.model_validate(v5_payload)
    old_bytes = old.model_dump_json()
    assert "interval_support" not in old.model_dump(mode="json")["s10"]

    v6_payload = deepcopy(v5_payload)
    v6_payload.update(schema_version=_ASSOCIATION_SCHEMA, nominal_confidence_level=0.80)
    v6_payload["uncertainty_bundle_ref"]["kind"] = "ir.forecasting_uncertainty_bundle"
    v6_payload["s10"]["interval_support"] = {
        "bundle_ref": deepcopy(v6_payload["uncertainty_bundle_ref"]),
        "observed_source_ref": deepcopy(v6_payload["observed_source_ref"]),
        "method_fqn": _METHOD_FQN,
        "target_metric": "metric",
        "nominal_coverage": 0.80,
    }
    v6_payload["s10"]["limitation_refs"].append(
        f"{_S10_SUPPORT_LIMITATION_PREFIX}prediction_measurement_unit_not_established"
    )
    current = PredictiveCalibrationAssociation.model_validate(v6_payload)
    candidate_source_kind = current.candidate_source_ref.kind
    assert _association_event_version(old.schema_version) == "5.0"
    assert _association_event_version(current.schema_version) == "6.0"
    assert _s10_summary_matches(
        old.s10,
        current.s10,
        association_schema_version=_V5_ASSOCIATION_SCHEMA,
        candidate_source_kind=candidate_source_kind,
    )
    assert old.model_dump_json() == old_bytes

    removed = current.s10.model_copy(update={"interval_support": None})
    assert not _s10_summary_matches(
        removed,
        current.s10,
        association_schema_version=_ASSOCIATION_SCHEMA,
        candidate_source_kind=candidate_source_kind,
    )
    foreign = deepcopy(v6_payload)
    foreign["s10"]["interval_support"]["bundle_ref"]["manifest_profile_sha256"] = (
        "sha256:" + "f" * 64
    )
    with pytest.raises(
        ValidationError, match="predictive_calibration_s10_interval_binding_mismatch"
    ):
        PredictiveCalibrationAssociation.model_validate(foreign)


def test_stock_v3_event_reopens_exact_association_for_both_lookups(tmp_path: Path) -> None:
    """Read the historical writer's CAS payload and durable event without promoting its grade."""
    from polisyos.core.artifacts import ArtifactRef, ensure_ir_artifact_store
    from polisyos.ir import CanonSpec as IRCanonSpec
    from polisyos.ir import InputRef, put_json_artifact
    from polisyos.runtime.http.services.control_plane_store import ControlPlaneStore
    from polisyos.runtime.quality.diagnostic_events import DiagnosticEvent
    from polisyos.runtime.quality.event_log import RuntimeDiagnosticEventLog

    fixture_path = (
        Path(__file__).resolve().parents[3]
        / "fixtures/runtime_quality/diagnostic_events/predictive_calibration_v3_association_event.json"
    )
    history = json.loads(fixture_path.read_bytes())
    assert history["writer_revision"] == "791b9c339b286b03e2d9b3bc23e153c61c091202"
    raw_association = history["association_json"].encode()
    association = json.loads(raw_association)
    writer = FileSystemCAS(tmp_path / "cas")
    edges = []
    for manifest_role in history["association_input_roles"]:
        field = (
            "empirical_evidence"
            if manifest_role == "empirical_calibration_evidence"
            else (manifest_role)
        )
        expected_ref = ArtifactRef.model_validate(association[f"{field}_ref"])
        ref = writer.put_bytes(
            json.dumps({"fixture": "historical-v3", "role": field}, separators=(",", ":")).encode(),
            ArtifactWriteOptions(
                kind=expected_ref.kind,
                media_type=expected_ref.media_type,
                schema=SchemaInfo(
                    name="test.predictive_calibration.historical_input", version="1.0"
                ),
            ),
            return_selected_profile=True,
        )
        assert ref == expected_ref
        edges.append(
            InputRef(
                artifact_id=ref.artifact_id,
                role=manifest_role,
                manifest_profile_sha256=ref.manifest_profile_sha256,
            )
        )

    def association_view(schema_name: str) -> ArtifactRef:
        return ArtifactRef.model_validate(
            put_json_artifact(
                ensure_ir_artifact_store(writer),
                association,
                kind=predictive_calibration._ASSOCIATION_KIND,
                schema_name=schema_name,
                schema_version="3.0",
                inputs=edges,
                canon_spec=IRCanonSpec(forbid_floats=False),
                return_selected_profile=True,
            )
        )

    event_payload = history["event_payload"]
    saved_ref = association_view(association["schema_version"])
    assert saved_ref == ArtifactRef.model_validate(event_payload["association_ref"])
    assert writer.get_bytes(saved_ref) == raw_association
    event = DiagnosticEvent.model_validate(history["event"])
    store_path = tmp_path / "control.sqlite3"
    log = RuntimeDiagnosticEventLog(
        store=ControlPlaneStore(backend="sqlite", sqlite_path=store_path),
        artifact_store=writer,
    )
    saved_event = log.append(event, payload=event_payload)
    assert saved_event.payload_sha256 == history["event_payload_sha256"]

    reader = FileSystemCAS(writer.root)
    fresh_log = RuntimeDiagnosticEventLog(
        store=ControlPlaneStore(backend="sqlite", sqlite_path=store_path),
        artifact_store=reader,
    )
    by_run = fresh_log.list_events(run_id=event.run_id, job_id=event.job_id, limit=1000)
    by_intent = fresh_log.list_events(event_id=event.event_id, limit=2)
    assert by_run == by_intent == [saved_event]
    for opened_event in (*by_run, *by_intent):
        payload = predictive_calibration._read_event_payload(reader, opened_event)
        assert payload == event_payload
        ref, reopened = predictive_calibration._load_association_for_event(
            reader, opened_event.event, payload
        )
        assert ref == saved_ref
        assert reader.get_bytes(ref) == raw_association
        assert reopened.schema_version == association["schema_version"]
        assert reopened.event_id == event.event_id
        assert reopened.s10.forecast_tier == "blocked"
        assert reopened.s10.interval_support is None
        assert reopened.assessment == "limited"

    foreign = association_view("test.foreign_predictive_association")
    assert foreign.artifact_id == saved_ref.artifact_id
    assert foreign.manifest_profile_sha256 != saved_ref.manifest_profile_sha256
    unknown_event = event.model_copy(
        update={"event_id": "evt-v3-unknown", "dedupe_key": "v3-control-unknown"}
    )
    unknown = log.append(unknown_event, payload={**event_payload, "schema_version": "99.0"})
    with pytest.raises(
        predictive_calibration.PredictiveCalibrationError,
        match="predictive_calibration_event_payload_schema_mismatch",
    ):
        predictive_calibration._read_event_payload(reader, unknown)

    controls = (
        (
            {"schema_version": "6.0"},
            "predictive_calibration_event_association_binding_mismatch",
        ),
        (
            {"association_ref": foreign.model_dump(mode="json")},
            "predictive_calibration_association_manifest_mismatch",
        ),
    )
    for index, (patch, expected_code) in enumerate(controls):
        foreign_event = event.model_copy(
            update={"event_id": f"evt-v3-control-{index}", "dedupe_key": f"v3-control-{index}"}
        )
        rejected = log.append(foreign_event, payload={**event_payload, **patch})
        payload = predictive_calibration._read_event_payload(reader, rejected)
        with pytest.raises(predictive_calibration.PredictiveCalibrationError, match=expected_code):
            predictive_calibration._load_association_for_event(reader, rejected.event, payload)


@pytest.mark.parametrize(
    "corruption",
    ["row_counts", "missing_reason", "missing_limitation", "record", "s10_counts"],
)
def test_v5_candidate_refuses_observation_authority_without_source_reconciliation(
    corruption: str,
) -> None:
    """Same-shape row numbers or removed limitations cannot promote a candidate."""
    from pydantic import ValidationError

    payload = _unverified_v5_association_payload()
    if corruption == "row_counts":
        payload.update(observed_numerator=2, observed_denominator=2, observed_hit_rate=1.0)
    elif corruption == "missing_reason":
        payload["evidence_reason_codes"] = []
    elif corruption == "missing_limitation":
        payload["s10"]["limitation_refs"].remove(
            "s10://calibration/fail-closed/backtest_source_not_established"
        )
    elif corruption == "record":
        payload["s10"]["calibration_record_ref"] = "s10://row-only/calibration"
    else:
        payload["s10"].update(numerator=2, denominator=2, observed_pass_rate=1.0)
    with pytest.raises(ValidationError, match=r"predictive_calibration_(unavailable|observations)"):
        predictive_calibration.PredictiveCalibrationAssociation.model_validate(payload)
