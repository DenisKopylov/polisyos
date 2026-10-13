from __future__ import annotations

import json
from typing import Any

import pytest

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
