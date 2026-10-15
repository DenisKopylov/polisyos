from __future__ import annotations

from dataclasses import dataclass

import pytest

from polisyos.common.canonical_profile import CanonicalProfileRefusalError
from polisyos.core.artifacts import CanonInfo, FileSystemCAS, PutOptions, SchemaInfo
from polisyos.core.artifacts.canonical_profile import validate_core_model_json_artifact
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.canon import CanonSpec, to_canonical_bytes
from polisyos.core.contracts.fabric import DataSnapshot
from polisyos.core.contracts.foundry import Metrics, ProgramGraph


@dataclass(frozen=True)
class _OwnedPayload:
    model: type
    payload: object


def _owner_payloads() -> tuple[_OwnedPayload, ...]:
    ref = ArtifactRef(
        artifact_id="sha256:" + "a" * 64,
        kind="fabric.tabular_payload",
        media_type="application/json",
    )
    return (
        _OwnedPayload(
            ProgramGraph,
            ProgramGraph(
                ir_ref=ArtifactRef(
                    artifact_id="sha256:" + "b" * 64,
                    kind="ir.policy_spec",
                    media_type="application/json",
                )
            ),
        ),
        _OwnedPayload(DataSnapshot, DataSnapshot(data_ref=ref)),
        _OwnedPayload(Metrics, Metrics(values={"count": 1})),
    )


def _store_selected_view(
    store: FileSystemCAS,
    owner: type,
    raw_payload: bytes,
    *,
    kind: str | None = None,
    media_type: str | None = None,
    schema_name: str | None = None,
    schema_version: str | None = None,
) -> ArtifactRef:
    spec = CanonSpec(forbid_floats=False, exclude_none=False)
    return store.put_bytes(
        raw_payload,
        PutOptions(
            kind=kind or owner.ARTIFACT_KIND,
            media_type=media_type or owner.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=schema_name or owner.ARTIFACT_SCHEMA_NAME,
                version=schema_version or owner.ARTIFACT_SCHEMA_VERSION,
            ),
            canon=CanonInfo.from_spec(spec),
        ),
        return_selected_profile=True,
    )


@pytest.mark.parametrize("owned", _owner_payloads())
def test_selected_owner_admission_accepts_exact_profile_and_rejects_same_bytes_under_siblings(
    tmp_path,
    owned: _OwnedPayload,
) -> None:
    store = FileSystemCAS(tmp_path / owned.model.__name__)
    spec = CanonSpec(forbid_floats=False, exclude_none=False)
    raw_payload = to_canonical_bytes(owned.payload, spec)

    exact_ref = _store_selected_view(store, owned.model, raw_payload)
    admitted = validate_core_model_json_artifact(owned.model, store, exact_ref)
    assert admitted == owned.payload

    wrong_views = (
        (
            {"kind": "test.unowned_kind"},
            "canon_profile_typed_artifact_kind_mismatch",
        ),
        (
            {"schema_name": "polisyos.test.UnrelatedPayload"},
            "canon_profile_typed_artifact_schema_name_mismatch",
        ),
        (
            {"schema_version": "9.9"},
            "canon_profile_typed_artifact_schema_version_unsupported",
        ),
        (
            {"media_type": "text/plain"},
            "canon_profile_typed_artifact_media_type_mismatch",
        ),
    )
    for profile_change, refusal_code in wrong_views:
        wrong_ref = _store_selected_view(
            store,
            owned.model,
            raw_payload,
            **profile_change,
        )
        assert wrong_ref.artifact_id == exact_ref.artifact_id
        assert wrong_ref.manifest_profile_sha256 != exact_ref.manifest_profile_sha256
        with pytest.raises(CanonicalProfileRefusalError, match=refusal_code):
            validate_core_model_json_artifact(owned.model, store, wrong_ref)
