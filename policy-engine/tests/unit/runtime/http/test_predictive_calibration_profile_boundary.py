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
