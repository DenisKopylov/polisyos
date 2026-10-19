from __future__ import annotations

import json
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

    def get_manifest_bytes(self, selector: object) -> bytes:
        raw = self._store.get_manifest_bytes(selector)
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


def test_legacy_v2_n4_requires_complete_owner_projection_before_fresh_get() -> None:
    """Persisted v2 N4 rows without the current owner projection fail closed."""
    from copy import deepcopy

    from pydantic import ValidationError

    from polisyos.runtime.http.openapi_contract import _predictive_calibration_success_examples
    from polisyos.runtime.http.services.predictive_calibration import (
        _LEGACY_ASSOCIATION_SCHEMA,
        PredictiveCalibrationAssociation,
    )

    fresh_payload = _predictive_calibration_success_examples()[
        "controlled_insufficient_history_candidate"
    ]["value"]["association"]

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

    # An already complete legacy row is not silently upgraded. It remains v2
    # and must still match the freshly recomputed complete typed projection.
    complete_v2 = deepcopy(fresh_payload)
    complete_v2["schema_version"] = _LEGACY_ASSOCIATION_SCHEMA
    reopened = PredictiveCalibrationAssociation.model_validate(complete_v2)
    current = PredictiveCalibrationAssociation.model_validate(fresh_payload)
    assert reopened.schema_version == _LEGACY_ASSOCIATION_SCHEMA
    assert reopened.s10 == current.s10


def test_persisted_legacy_v2_n4_without_owner_projection_is_typed_refusal(tmp_path) -> None:
    """The selected CAS GET reader maps unsafe old N4 bytes to a typed refusal."""
    from copy import deepcopy

    from polisyos.core.artifacts import ArtifactRef
    from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
    from polisyos.core.canon import to_canonical_bytes
    from polisyos.runtime.http.openapi_contract import _predictive_calibration_success_examples
    from polisyos.runtime.http.services.predictive_calibration import (
        _ASSOCIATION_KIND,
        _LEGACY_ASSOCIATION_SCHEMA,
        _LEGACY_ASSOCIATION_VERSION,
        PredictiveCalibrationError,
        _load_association,
    )

    payload = deepcopy(
        _predictive_calibration_success_examples()["controlled_insufficient_history_candidate"][
            "value"
        ]["association"]
    )
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

    from polisyos.runtime.http.openapi_contract import _predictive_calibration_success_examples
    from polisyos.runtime.http.services.predictive_calibration import (
        PredictiveCalibrationAssociation,
    )

    payload = _predictive_calibration_success_examples()[
        "controlled_insufficient_history_candidate"
    ]["value"]["association"]
    payload["s10"].pop("authority_boundary")
    with pytest.raises(ValidationError, match="predictive_calibration_n4_outcome_binding"):
        PredictiveCalibrationAssociation.model_validate(payload)

    payload = _predictive_calibration_success_examples()[
        "controlled_insufficient_history_candidate"
    ]["value"]["association"]
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

    from polisyos.runtime.http.openapi_contract import _predictive_calibration_success_examples
    from polisyos.runtime.http.services.predictive_calibration import (
        PredictiveCalibrationAssociation,
    )

    response_payload = _predictive_calibration_success_examples()[
        "controlled_insufficient_history_candidate"
    ]["value"]
    payload = response_payload["association"]
    assert payload["s10"]["outcome_binding_status"] == "not_established"
    assert "n4_outcome_target_binding_not_established" in " ".join(
        payload["s10"]["limitation_refs"]
    )
    payload["s10"]["forecast_tier"] = transported_tier
    with pytest.raises(ValidationError, match="predictive_calibration_n4_outcome_binding"):
        PredictiveCalibrationAssociation.model_validate(payload)
