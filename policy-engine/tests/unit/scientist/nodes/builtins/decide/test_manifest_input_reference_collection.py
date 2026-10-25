from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import BaseModel

from polisyos.core.artifacts.manifest import ArtifactRef, InputRef
from polisyos.core.artifacts.ownership import ArtifactOwnershipError
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.contracts.decision_validity import (
    DecisionBasisSection,
    DecisionDependencyRef,
    DecisionValidityEnvelope,
)
from polisyos.scientist.nodes.builtins.decide.decision_packet import builder, serialization
from polisyos.scientist.orchestration.engine.state import ExperimentState


def _ref(artifact_id: str, profile: str | None, *, kind: str = "test.evidence") -> ArtifactRef:
    return ArtifactRef(
        artifact_id=artifact_id,
        kind=kind,
        media_type="application/json",
        manifest_profile_sha256=profile,
    )


def _dependency(
    ref: ArtifactRef,
    *,
    profile: str | None = None,
    nested_metadata: dict[str, object] | None = None,
) -> dict[str, object]:
    metadata: dict[str, object] = {
        "media_type": ref.media_type,
        "manifest_profile_sha256": (ref.manifest_profile_sha256 if profile is None else profile),
    }
    if nested_metadata:
        metadata.update(nested_metadata)
    return {
        "kind": "econometric_evidence",
        "key": "hte_completed_source_artifact",
        "artifact_id": str(ref.artifact_id),
        "label": ref.kind,
        "metadata": metadata,
    }


def _state(*refs: tuple[str, ArtifactRef]) -> ExperimentState:
    return ExperimentState(
        run_id="R_manifest_reference_collection",
        inputs=dict(refs),
    )


_DECISION_BASIS_FIELDS = tuple(
    name
    for name, field in DecisionValidityEnvelope.model_fields.items()
    if field.annotation is DecisionBasisSection
)


@pytest.mark.parametrize("basis_name", _DECISION_BASIS_FIELDS)
def test_schema_declared_basis_dependencies_collect_valid_typed_references(
    basis_name: str,
) -> None:
    selected = _ref(_REFERENCE_ID, _REFERENCE_PROFILE)
    payload = {
        "decision_validity_envelope": {basis_name: {"dependencies": [_dependency(selected)]}}
    }

    refs = serialization._build_manifest_inputs(
        payload,
        source_state=_state(("selected", selected)),
    )

    assert len(refs) == 1
    assert refs[0].role == (f"decision_validity_envelope.{basis_name}.dependencies[0]")
    assert refs[0].artifact_id == selected.artifact_id
    assert refs[0].manifest_profile_sha256 == selected.manifest_profile_sha256


@pytest.mark.parametrize("basis_name", _DECISION_BASIS_FIELDS)
def test_schema_declared_basis_refuses_malformed_present_dependency(
    basis_name: str,
) -> None:
    selected = _ref(_REFERENCE_ID, _REFERENCE_PROFILE)
    malformed_dependency = {
        "kind": "econometric_evidence",
        "artifact_id": str(selected.artifact_id),
        "metadata": {"manifest_profile_sha256": _REFERENCE_PROFILE},
    }
    payload = {"decision_validity_envelope": {basis_name: {"dependencies": [malformed_dependency]}}}

    with pytest.raises(ValueError, match="decision_packet_manifest_reference_invalid"):
        serialization._build_manifest_inputs(
            payload,
            source_state=_state(("selected", selected)),
        )


@pytest.mark.parametrize(
    "malformed_envelope",
    [None, [], {}, "invalid"],
    ids=["null", "list", "empty-object", "scalar"],
)
def test_present_empty_or_non_object_envelope_refuses(
    malformed_envelope: object,
) -> None:
    with pytest.raises(ValueError, match="decision_packet_manifest_envelope_invalid"):
        serialization._build_manifest_inputs({"decision_validity_envelope": malformed_envelope})


def test_dependency_profile_digest_is_joined_to_its_artifact_not_collected_as_blob() -> None:
    artifact_id = "sha256:" + "a" * 64
    profile_hash = "sha256:" + "b" * 64
    profile_blob_ref = _ref(profile_hash, "sha256:" + "c" * 64, kind="test.profile_blob")
    selected_ref = _ref(artifact_id, profile_hash)
    payload = {
        "inputs": {"profile_blob": profile_hash},
        "decision_validity_envelope": {"data_basis": {"dependencies": [_dependency(selected_ref)]}},
    }

    refs = serialization._build_manifest_inputs(
        payload,
        source_state=_state(("selected", selected_ref), ("profile_blob", profile_blob_ref)),
    )
    by_role = {ref.role: ref for ref in refs}

    dependency_role = "decision_validity_envelope.data_basis.dependencies[0]"
    assert set(by_role) == {"input.profile_blob", dependency_role}
    assert by_role[dependency_role].artifact_id == selected_ref.artifact_id
    assert by_role[dependency_role].manifest_profile_sha256 == profile_hash
    assert by_role["input.profile_blob"].artifact_id == profile_blob_ref.artifact_id


def test_dependency_profile_selects_exact_view_when_one_blob_has_multiple_profiles() -> None:
    artifact_id = "sha256:" + "d" * 64
    first = _ref(artifact_id, "sha256:" + "1" * 64)
    selected = _ref(artifact_id, "sha256:" + "2" * 64)
    payload = {
        "decision_validity_envelope": {"data_basis": {"dependencies": [_dependency(selected)]}}
    }

    refs = serialization._build_manifest_inputs(
        payload,
        source_state=_state(("first", first), ("selected", selected)),
    )

    assert len(refs) == 1
    assert refs[0].artifact_id == selected.artifact_id
    assert refs[0].manifest_profile_sha256 == selected.manifest_profile_sha256


def test_dependency_wrong_profile_is_refused_against_available_views() -> None:
    artifact_id = "sha256:" + "e" * 64
    first = _ref(artifact_id, "sha256:" + "3" * 64)
    second = _ref(artifact_id, "sha256:" + "4" * 64)
    payload = {
        "decision_validity_envelope": {
            "data_basis": {
                "dependencies": [
                    _dependency(first, profile="sha256:" + "5" * 64),
                ]
            }
        }
    }

    with pytest.raises(
        ValueError,
        match="decision_packet_manifest_input_profile_mismatch",
    ):
        serialization._build_manifest_inputs(
            payload,
            source_state=_state(("first", first), ("second", second)),
        )


def test_dependency_keeps_nested_typed_ref_inside_business_metadata() -> None:
    selected = _ref("sha256:" + "f" * 64, "sha256:" + "6" * 64)
    nested = _ref("sha256:" + "9" * 64, "sha256:" + "7" * 64, kind="test.nested")
    payload = {
        "decision_validity_envelope": {
            "data_basis": {
                "dependencies": [
                    _dependency(
                        selected,
                        nested_metadata={"source_ref": nested.model_dump(mode="json")},
                    )
                ]
            }
        }
    }

    refs = serialization._build_manifest_inputs(
        payload,
        source_state=_state(("selected", selected), ("nested", nested)),
    )
    by_role = {ref.role: ref for ref in refs}

    assert (
        by_role["decision_validity_envelope.data_basis.dependencies[0]"].manifest_profile_sha256
        == selected.manifest_profile_sha256
    )
    assert (
        by_role[
            "decision_validity_envelope.data_basis.dependencies[0].metadata.source_ref"
        ].manifest_profile_sha256
        == nested.manifest_profile_sha256
    )


def test_untyped_business_metadata_digest_is_not_a_blob_input() -> None:
    digest_ref = _ref("sha256:" + "8" * 64, None, kind="test.digest-looking-blob")
    payload = {
        "decision_validity_envelope": {
            "data_basis": {"summary": {"measurement_digest": str(digest_ref.artifact_id)}}
        }
    }

    refs = serialization._build_manifest_inputs(
        payload,
        source_state=_state(("digest", digest_ref)),
    )

    assert refs == []


def test_collected_foreign_artifact_input_is_refused_by_store_owner(tmp_path: Path) -> None:
    cas_root = tmp_path / "shared-cas"
    writer = FileSystemCAS(cas_root).for_tenant("tenant-a", cell_id="cell-a")
    foreign_writer = FileSystemCAS(cas_root).for_tenant("tenant-b", cell_id="cell-b")
    parent_ref = writer.put_json(
        {"owner": "tenant-a"},
        PutOptions(kind="test.parent", media_type="application/json"),
        return_selected_profile=True,
    )
    assert parent_ref.manifest_profile_sha256 is not None
    inputs = serialization._build_manifest_inputs(
        {"inputs": {"source": str(parent_ref.artifact_id)}},
        source_state=_state(("source", parent_ref)),
    )

    assert len(inputs) == 1
    assert inputs[0].artifact_id == parent_ref.artifact_id
    assert inputs[0].manifest_profile_sha256 == parent_ref.manifest_profile_sha256
    same_owner_child = writer.put_json(
        {"child": True},
        PutOptions(kind="test.child", media_type="application/json", inputs=inputs),
        return_selected_profile=True,
    )
    assert writer.get_manifest(same_owner_child).inputs == inputs
    with pytest.raises(ArtifactOwnershipError):
        foreign_writer.put_json(
            {"child": True},
            PutOptions(
                kind="test.child",
                media_type="application/json",
                inputs=inputs,
            ),
        )


_REFERENCE_ID = "sha256:" + "a" * 64
_REFERENCE_PROFILE = "sha256:" + "b" * 64


@pytest.mark.parametrize(
    "reference",
    [
        pytest.param(
            {"artifact_id": _REFERENCE_ID, "kind": "test.evidence"},
            id="artifact-missing-media-type",
        ),
        pytest.param(
            {"artifact_id": _REFERENCE_ID, "media_type": "application/json"},
            id="artifact-missing-kind",
        ),
        pytest.param(
            {"kind": "test.evidence", "media_type": "application/json"}, id="artifact-missing-id"
        ),
        pytest.param(
            {"artifact_id": None, "kind": "test.evidence", "media_type": "application/json"},
            id="artifact-null-id",
        ),
        pytest.param(
            {"artifact_id": 7, "kind": "test.evidence", "media_type": "application/json"},
            id="artifact-id-wrong-type",
        ),
        pytest.param(
            {"artifact_id": _REFERENCE_ID, "kind": None, "media_type": "application/json"},
            id="artifact-null-kind",
        ),
        pytest.param(
            {"artifact_id": _REFERENCE_ID, "kind": 7, "media_type": "application/json"},
            id="artifact-kind-wrong-type",
        ),
        pytest.param(
            {"artifact_id": _REFERENCE_ID, "kind": "test.evidence", "media_type": None},
            id="artifact-null-media-type",
        ),
        pytest.param(
            {"artifact_id": _REFERENCE_ID, "kind": "test.evidence", "media_type": 7},
            id="artifact-media-type-wrong-type",
        ),
        pytest.param(
            {
                "artifact_id": _REFERENCE_ID,
                "kind": "test.evidence",
                "media_type": "application/json",
                "manifest_profile_sha256": "bad-profile",
            },
            id="artifact-profile-malformed",
        ),
        pytest.param(
            {
                "artifact_id": _REFERENCE_ID,
                "kind": "test.evidence",
                "media_type": "application/json",
                "unexpected": True,
            },
            id="artifact-extra-field",
        ),
        pytest.param(
            {
                "artifact_id": _REFERENCE_ID,
                "kind": "test.evidence",
                "media_type": "application/json",
                7: "non-string-key",
            },
            id="artifact-non-string-key",
        ),
        pytest.param({"artifact_id": _REFERENCE_ID}, id="input-ref-missing-role"),
        pytest.param({"role": "source"}, id="input-ref-missing-id"),
        pytest.param({"artifact_id": None, "role": "source"}, id="input-ref-null-id"),
        pytest.param({"artifact_id": 7, "role": "source"}, id="input-ref-id-wrong-type"),
        pytest.param({"artifact_id": _REFERENCE_ID, "role": None}, id="input-ref-null-role"),
        pytest.param({"artifact_id": _REFERENCE_ID, "role": 7}, id="input-ref-role-wrong-type"),
        pytest.param(
            {
                "artifact_id": _REFERENCE_ID,
                "role": "source",
                "manifest_profile_sha256": "bad-profile",
            },
            id="input-ref-profile-malformed",
        ),
        pytest.param(
            {"artifact_id": _REFERENCE_ID, "role": "source", "unexpected": True},
            id="input-ref-extra-field",
        ),
        pytest.param(
            {"kind": "econometric_evidence", "artifact_id": _REFERENCE_ID, "metadata": {}},
            id="dependency-missing-key",
        ),
        pytest.param(
            {"key": "source", "artifact_id": _REFERENCE_ID, "metadata": {}},
            id="dependency-missing-kind",
        ),
        pytest.param(
            {"kind": None, "key": "source", "artifact_id": _REFERENCE_ID, "metadata": {}},
            id="dependency-null-kind",
        ),
        pytest.param(
            {
                "kind": "econometric_evidence",
                "key": None,
                "artifact_id": _REFERENCE_ID,
                "metadata": {},
            },
            id="dependency-null-key",
        ),
        pytest.param(
            {
                "kind": "unknown_dependency",
                "key": "source",
                "artifact_id": _REFERENCE_ID,
                "metadata": {},
            },
            id="dependency-kind-unknown",
        ),
        pytest.param(
            {
                "kind": "econometric_evidence",
                "key": "source",
                "artifact_id": _REFERENCE_ID,
                "metadata": None,
            },
            id="dependency-null-metadata",
        ),
        pytest.param(
            {
                "kind": "econometric_evidence",
                "key": "source",
                "artifact_id": _REFERENCE_ID,
                "metadata": [],
            },
            id="dependency-metadata-wrong-type",
        ),
        pytest.param(
            {"kind": "econometric_evidence", "key": "source", "artifact_id": 7, "metadata": {}},
            id="dependency-artifact-id-wrong-type",
        ),
        pytest.param(
            {
                "kind": "econometric_evidence",
                "key": "source",
                "artifact_id": "not-an-artifact-id",
                "metadata": {},
            },
            id="dependency-artifact-id-malformed",
        ),
        pytest.param(
            {
                "kind": "econometric_evidence",
                "key": "source",
                "artifact_id": None,
                "metadata": {"manifest_profile_sha256": _REFERENCE_PROFILE},
            },
            id="dependency-profile-without-artifact",
        ),
        pytest.param(
            {
                "kind": "econometric_evidence",
                "key": "source",
                "artifact_id": _REFERENCE_ID,
                "metadata": {"manifest_profile_sha256": 7},
            },
            id="dependency-profile-wrong-type",
        ),
        pytest.param(
            {
                "kind": "econometric_evidence",
                "key": "source",
                "artifact_id": _REFERENCE_ID,
                "metadata": {"manifest_profile_sha256": "bad-profile"},
            },
            id="dependency-profile-malformed",
        ),
        pytest.param(
            {
                "kind": "econometric_evidence",
                "key": "source",
                "artifact_id": _REFERENCE_ID,
                "metadata": {},
                "unexpected": True,
            },
            id="dependency-extra-field",
        ),
    ],
)
def test_declared_reference_mapping_rejects_malformed_union_members(
    reference: dict[str, object],
) -> None:
    selected = _ref(_REFERENCE_ID, _REFERENCE_PROFILE)
    with pytest.raises(ValueError, match="decision_packet_manifest_"):
        serialization._build_manifest_inputs(
            {"hte": {"source_ref": reference}},
            source_state=_state(("selected", selected)),
        )


def test_declared_reference_union_accepts_real_typed_variants_and_null_optional_values() -> None:
    selected = _ref(_REFERENCE_ID, _REFERENCE_PROFILE)
    nested = _ref("sha256:" + "c" * 64, "sha256:" + "d" * 64)
    dependency = DecisionDependencyRef(
        kind="econometric_evidence",
        key="selected",
        artifact_id=str(selected.artifact_id),
        metadata={"manifest_profile_sha256": _REFERENCE_PROFILE, "nested_source_ref": nested},
    )
    profileless_artifact = _ref(_REFERENCE_ID, None)
    profileless_dependency = DecisionDependencyRef(
        kind="econometric_evidence",
        key="selected_without_explicit_profile",
        artifact_id=str(selected.artifact_id),
        metadata={"manifest_profile_sha256": None},
    )
    valid_references: list[tuple[object, bool]] = [
        (selected, False),
        (profileless_artifact, False),
        (profileless_artifact.model_dump(mode="json"), False),
        (selected.model_dump(mode="json"), False),
        (
            InputRef(
                artifact_id=selected.artifact_id,
                role="source",
                manifest_profile_sha256=None,
            ),
            False,
        ),
        (
            {
                "artifact_id": str(selected.artifact_id),
                "role": "source",
                "manifest_profile_sha256": None,
            },
            False,
        ),
        (profileless_dependency, False),
        (profileless_dependency.model_dump(mode="python"), False),
        (dependency, True),
        (dependency.model_dump(mode="python"), True),
        (dependency.model_dump(mode="json"), True),
    ]

    refs = [
        (
            serialization._build_manifest_inputs(
                {"hte": {"source_ref": reference}},
                source_state=_state(("selected", selected), ("nested", nested)),
            ),
            has_nested,
        )
        for reference, has_nested in valid_references
    ]

    for collected, has_nested in refs:
        by_role = {ref.role: ref for ref in collected}
        assert by_role["hte.source_ref"].artifact_id == selected.artifact_id
        assert by_role["hte.source_ref"].manifest_profile_sha256 == _REFERENCE_PROFILE
        nested_role = "hte.source_ref.metadata.nested_source_ref"
        assert (nested_role in by_role) is has_nested
        if has_nested:
            assert by_role[nested_role].artifact_id == nested.artifact_id
            assert by_role[nested_role].manifest_profile_sha256 == nested.manifest_profile_sha256


def test_declared_reference_union_accepts_profileless_dependency_without_blob_input() -> None:
    dependency = DecisionDependencyRef(
        kind="econometric_evidence",
        key="unresolved",
        artifact_id=None,
        metadata={"manifest_profile_sha256": None},
    )

    assert serialization._build_manifest_inputs({"hte": {"source_ref": dependency}}) == []


def test_input_section_preserves_typed_input_ref_and_legacy_bare_id() -> None:
    selected = _ref(_REFERENCE_ID, _REFERENCE_PROFILE)
    typed = serialization._build_manifest_inputs(
        {
            "inputs": {
                "source": InputRef(
                    artifact_id=selected.artifact_id,
                    role="upstream-source",
                    manifest_profile_sha256=None,
                )
            }
        },
        source_state=_state(("selected", selected)),
    )
    legacy = serialization._build_manifest_inputs(
        {"inputs": {"source": str(selected.artifact_id)}},
        source_state=_state(("selected", selected)),
    )

    assert typed == legacy
    assert len(typed) == 1
    assert typed[0].role == "input.source"
    assert typed[0].artifact_id == selected.artifact_id
    assert typed[0].manifest_profile_sha256 == selected.manifest_profile_sha256


class _SelectedReferenceModel(BaseModel):
    artifact_id: str
    kind: str
    media_type: str
    manifest_profile_sha256: str | None = None


class _MalformedReferenceModel(BaseModel):
    artifact_id: object
    kind: object
    media_type: object
    manifest_profile_sha256: object | None = None


class _ReferenceLookalike:
    def __init__(self) -> None:
        self.artifact_id = _REFERENCE_ID
        self.kind = "test.evidence"
        self.media_type = "application/json"


def test_builder_reference_projection_uses_model_fields_and_refuses_invalid_values() -> None:
    selected = _SelectedReferenceModel(
        artifact_id=_REFERENCE_ID,
        kind="test.evidence",
        media_type="application/json",
        manifest_profile_sha256=_REFERENCE_PROFILE,
    )

    refs = builder._model_artifact_refs(selected)

    assert refs == (
        ArtifactRef(
            artifact_id=_REFERENCE_ID,
            kind="test.evidence",
            media_type="application/json",
            manifest_profile_sha256=_REFERENCE_PROFILE,
        ),
    )
    with pytest.raises(ValueError, match="completed_hte_selected_artifact_ref_invalid"):
        builder._model_artifact_refs(
            _MalformedReferenceModel(
                artifact_id=7,
                kind="test.evidence",
                media_type="application/json",
                manifest_profile_sha256=_REFERENCE_PROFILE,
            )
        )
    assert builder._model_artifact_refs(_ReferenceLookalike()) == ()


def test_dependency_nested_declared_reference_rejects_partial_present_mapping() -> None:
    selected = _ref(_REFERENCE_ID, _REFERENCE_PROFILE)
    payload = {
        "decision_validity_envelope": {
            "data_basis": {
                "dependencies": [
                    _dependency(
                        selected,
                        nested_metadata={
                            "source_ref": {
                                "artifact_id": _REFERENCE_ID,
                                "kind": "test.evidence",
                            }
                        },
                    )
                ]
            }
        }
    }

    with pytest.raises(ValueError, match="decision_packet_manifest_reference_invalid"):
        serialization._build_manifest_inputs(
            payload,
            source_state=_state(("selected", selected)),
        )
