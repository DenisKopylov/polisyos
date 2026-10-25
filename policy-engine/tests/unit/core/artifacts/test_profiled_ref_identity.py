from __future__ import annotations

from pathlib import Path
from typing import ClassVar

import pytest
from pydantic import BaseModel, ConfigDict

import polisyos.core.artifacts._profiled_ref as profiled
import polisyos.ir.artifacts.contracts as contracts
from polisyos.core.artifacts import FileSystemCAS, PutOptions
from polisyos.ir.registry.refs import ArtifactRefModel


class ForgedRef(ArtifactRefModel):
    replacement_id: ClassVar[str] = ""

    def model_dump(self, *args, **kwargs):
        result = super().model_dump(*args, **kwargs)
        result["artifact_id"] = self.replacement_id
        return result


class RefWrapper(BaseModel):
    model_config = ConfigDict(extra="forbid")

    artifact_id: str
    kind: str
    media_type: str
    manifest_profile_sha256: str | None = None


def test_normalizer_and_profile_binder_refuse_substituted_projection(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    original = store.put_json(
        {"value": "selected"},
        PutOptions(kind="test.ref", media_type="application/json"),
    )
    alternate = store.put_json(
        {"value": "alternate"},
        PutOptions(kind="test.ref", media_type="application/json"),
    )
    ForgedRef.replacement_id = str(alternate.artifact_id)
    forged = ForgedRef(
        artifact_id=original.artifact_id,
        kind=original.kind,
        media_type=original.media_type,
    )

    with pytest.raises(TypeError, match="projection"):
        contracts.normalize_artifact_ref(forged)
    with pytest.raises(ValueError, match="artifact_manifest_ref_identity_mismatch"):
        profiled.profile_bound_ref(store, forged)


def test_honest_generic_wrapper_remains_supported(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    original = store.put_json(
        {"value": "selected"},
        PutOptions(kind="test.wrapper", media_type="application/json"),
    )
    wrapper = RefWrapper(
        artifact_id=str(original.artifact_id),
        kind=original.kind,
        media_type="application/json",
    )

    selected = profiled.profile_bound_ref(store, wrapper)

    assert isinstance(selected, RefWrapper)
    assert selected.artifact_id == str(original.artifact_id)
    assert selected.manifest_profile_sha256 is not None
    assert contracts.normalize_artifact_ref(selected)["artifact_id"] == str(original.artifact_id)
