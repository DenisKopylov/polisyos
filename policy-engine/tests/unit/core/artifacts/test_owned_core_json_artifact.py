from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import BaseModel, ConfigDict

from polisyos.common.canonical_profile import CanonicalProfileRefusalError
from polisyos.core.artifacts import (
    ArtifactIntegrityError,
    CanonInfo,
    CoreArtifactOwnerProfile,
    FileSystemCAS,
    PutOptions,
    SchemaInfo,
    artifact_manifest_profile_sha256,
    validate_core_model_json_artifact,
    validate_owned_core_model_json_artifact,
)
from polisyos.core.artifacts.ir_adapter import ensure_ir_artifact_store
from polisyos.core.canon import CanonSpec, to_canonical_bytes
from polisyos.ir.analytics.evidence_bundle import EvidenceBundle, persist_causal_evidence_bundle
from polisyos.ir.registry.refs import TwinNetworkResultRef

_BUNDLE_SCHEMA_NAME = "ir.causal_evidence_bundle"
_BUNDLE_OWNER = CoreArtifactOwnerProfile(
    kind="fabric.evidence_bundle",
    media_type="application/json",
    schema_variants=(
        SchemaInfo(name=_BUNDLE_SCHEMA_NAME, version="1.0"),
        SchemaInfo(name=_BUNDLE_SCHEMA_NAME, version="1.1"),
    ),
    payload_schema_version_by_manifest="not_applicable",
)


class _OwnerlessPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    value: int


class _VersionedPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    schema_version: str
    value: str


class _SentinelSpoof:
    def __eq__(self, other: object) -> bool:
        return isinstance(other, str)


def _put_json_view(
    store: FileSystemCAS,
    payload: object,
    *,
    kind: str,
    media_type: str,
    schema: SchemaInfo | None,
    ensure_ascii: bool = False,
):
    spec = CanonSpec(forbid_floats=False, ensure_ascii=ensure_ascii)
    raw = to_canonical_bytes(payload, spec)
    options = PutOptions(
        kind=kind,
        media_type=media_type,
        schema=schema,
        canon=CanonInfo.from_spec(spec),
    )
    if media_type == "application/json":
        return store.put_json(
            payload,
            options,
            canon_spec=spec,
            return_selected_profile=True,
        )
    return store.put_bytes(raw, options, return_selected_profile=True)


def _bundle_for_schema(version: str) -> EvidenceBundle:
    if version == "1.1":
        return EvidenceBundle(
            run_id="owned-bundle-v1.1",
            query_str="P(Y | do(X))",
            twin_network_result_ref=TwinNetworkResultRef(artifact_id="sha256:" + "a" * 64),
        )
    return EvidenceBundle(run_id="owned-bundle-v1.0", query_str="P(Y | do(X))")


@pytest.mark.parametrize("version", ["1.0", "1.1"])
def test_owned_reader_accepts_actual_evidence_bundle_producer_families(
    tmp_path: Path, version: str
) -> None:
    core_store = FileSystemCAS(tmp_path / f"evidence-{version}")
    ir_store = ensure_ir_artifact_store(core_store)
    bundle = _bundle_for_schema(version)

    if version == "1.0":
        ref = _put_json_view(
            ir_store,
            bundle,
            kind=_BUNDLE_OWNER.kind,
            media_type=_BUNDLE_OWNER.media_type,
            schema=SchemaInfo(name=_BUNDLE_SCHEMA_NAME, version=version),
        )
    else:
        ref = persist_causal_evidence_bundle(ir_store, bundle)
    # The old generic reader remains usable for candidate reads without an owner claim.
    assert validate_core_model_json_artifact(EvidenceBundle, ir_store, ref) == bundle
    result = validate_owned_core_model_json_artifact(
        EvidenceBundle,
        ir_store,
        ref,
        expected_owner=_BUNDLE_OWNER,
    )

    selected_manifest = core_store.get_manifest(result.artifact_ref)
    assert result.value == bundle
    assert result.artifact_ref.kind == "fabric.evidence_bundle"
    assert result.artifact_ref.media_type == "application/json"
    assert str(result.artifact_ref.artifact_id) == str(ref.artifact_id)
    assert result.artifact_ref.manifest_profile_sha256 == artifact_manifest_profile_sha256(
        selected_manifest
    )
    assert result.canon_profile == selected_manifest.canon
    assert selected_manifest.artifact_schema == SchemaInfo(
        name=_BUNDLE_SCHEMA_NAME,
        version=version,
    )


@pytest.mark.parametrize(
    "reverse_schema_order", [False, True], ids=["schema-forward", "schema-reverse"]
)
@pytest.mark.parametrize(
    "reverse_rule_order", [False, True], ids=["rules-forward", "rules-reverse"]
)
def test_same_schema_version_with_different_names_has_order_independent_payload_relation(
    tmp_path: Path,
    reverse_schema_order: bool,
    reverse_rule_order: bool,
) -> None:
    store = FileSystemCAS(tmp_path / "same-version-different-names")
    schema_a = SchemaInfo(name="owner.schema_a", version="manifest-v1")
    schema_b = SchemaInfo(name="owner.schema_b", version="manifest-v1")
    schemas = (schema_a, schema_b)
    rules = (
        ((schema_a.name, schema_a.version), "payload-v1"),
        ((schema_b.name, schema_b.version), "payload-v1"),
    )
    if reverse_schema_order:
        schemas = tuple(reversed(schemas))
    if reverse_rule_order:
        rules = tuple(reversed(rules))
    owner = CoreArtifactOwnerProfile(
        kind="owner.versioned",
        media_type="application/json",
        schema_variants=schemas,
        payload_schema_version_by_manifest=rules,
    )
    assert owner.schema_variants == (schema_a, schema_b)
    assert owner.payload_schema_version_by_manifest == (
        ((schema_a.name, schema_a.version), "payload-v1"),
        ((schema_b.name, schema_b.version), "payload-v1"),
    )
    payload = _VersionedPayload(schema_version="payload-v1", value="same-bytes")
    payload_dict = payload.model_dump(mode="json")
    ref_a = _put_json_view(
        store,
        payload_dict,
        kind=owner.kind,
        media_type=owner.media_type,
        schema=schema_a,
    )
    ref_b = _put_json_view(
        store,
        payload_dict,
        kind=owner.kind,
        media_type=owner.media_type,
        schema=schema_b,
    )

    read_a = validate_owned_core_model_json_artifact(
        _VersionedPayload,
        store,
        ref_a,
        expected_owner=owner,
    )
    read_b = validate_owned_core_model_json_artifact(
        _VersionedPayload,
        store,
        ref_b,
        expected_owner=owner,
    )

    assert ref_a.artifact_id == ref_b.artifact_id
    assert read_a.value == read_b.value == payload
    assert (
        read_a.artifact_ref.manifest_profile_sha256 != read_b.artifact_ref.manifest_profile_sha256
    )


def test_explicit_schema_absence_is_an_owner_state_not_a_fallback(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path / "schema-absent")
    ref = _put_json_view(
        store,
        {"value": 7},
        kind="owner.schema_absent",
        media_type="application/json",
        schema=None,
    )
    owner = CoreArtifactOwnerProfile(
        kind="owner.schema_absent",
        media_type="application/json",
        schema_variants="absent",
        payload_schema_version_by_manifest="not_applicable",
    )

    result = validate_owned_core_model_json_artifact(
        _OwnerlessPayload,
        store,
        ref,
        expected_owner=owner,
    )

    assert result.value == _OwnerlessPayload(value=7)
    assert store.get_manifest(result.artifact_ref).artifact_schema is None


def test_required_schema_does_not_fall_back_when_manifest_schema_is_absent(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path / "unexpected-schema-absence")
    ref = _put_json_view(
        store,
        {"value": 8},
        kind="owner.schema_required",
        media_type="application/json",
        schema=None,
    )
    owner = CoreArtifactOwnerProfile(
        kind="owner.schema_required",
        media_type="application/json",
        schema_variants=(SchemaInfo(name="owner.schema_required", version="1"),),
        payload_schema_version_by_manifest="not_applicable",
    )

    with pytest.raises(CanonicalProfileRefusalError) as error:
        validate_owned_core_model_json_artifact(
            _OwnerlessPayload,
            store,
            ref,
            expected_owner=owner,
        )

    assert error.value.code == "canon_profile_owned_artifact_schema_mismatch"


@pytest.mark.parametrize(
    ("kind", "media_type", "schema", "expected_code"),
    [
        (
            "foreign.kind",
            "application/json",
            SchemaInfo(name="owner.schema", version="1"),
            "canon_profile_owned_artifact_kind_mismatch",
        ),
        (
            "owner.kind",
            "application/octet-stream",
            SchemaInfo(name="owner.schema", version="1"),
            "canon_profile_owned_artifact_media_type_mismatch",
        ),
        (
            "owner.kind",
            "application/json",
            SchemaInfo(name="foreign.schema", version="1"),
            "canon_profile_owned_artifact_schema_mismatch",
        ),
        (
            "owner.kind",
            "application/json",
            SchemaInfo(name="owner.schema", version="2"),
            "canon_profile_owned_artifact_schema_mismatch",
        ),
    ],
)
def test_owner_mismatch_refuses_same_content_under_foreign_manifest_views(
    tmp_path: Path,
    kind: str,
    media_type: str,
    schema: SchemaInfo,
    expected_code: str,
) -> None:
    store = FileSystemCAS(tmp_path / expected_code)
    expected_schema = SchemaInfo(name="owner.schema", version="1")
    owner = CoreArtifactOwnerProfile(
        kind="owner.kind",
        media_type="application/json",
        schema_variants=(expected_schema,),
        payload_schema_version_by_manifest="not_applicable",
    )
    valid_ref = _put_json_view(
        store,
        {"value": 11},
        kind=owner.kind,
        media_type=owner.media_type,
        schema=expected_schema,
    )
    selected_manifest = store.get_manifest(valid_ref)
    foreign_ref = store.put_bytes(
        store.get_bytes(valid_ref),
        PutOptions(
            kind=kind,
            media_type=media_type,
            schema=schema,
            canon=selected_manifest.canon,
        ),
        return_selected_profile=True,
    )

    # The generic helper remains a candidate reader when the model declares no owner ABI.
    assert validate_core_model_json_artifact(_OwnerlessPayload, store, foreign_ref).value == 11
    with pytest.raises(CanonicalProfileRefusalError) as error:
        validate_owned_core_model_json_artifact(
            _OwnerlessPayload,
            store,
            foreign_ref,
            expected_owner=owner,
        )

    assert error.value.code == expected_code
    assert foreign_ref.artifact_id == valid_ref.artifact_id


def test_payload_schema_version_relation_rejects_relabelled_same_bytes(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path / "payload-schema-version")
    schema_v1 = SchemaInfo(name="owner.versioned", version="manifest-v1")
    schema_v2 = SchemaInfo(name="owner.versioned", version="manifest-v2")
    owner = CoreArtifactOwnerProfile(
        kind="owner.versioned",
        media_type="application/json",
        schema_variants=(schema_v1, schema_v2),
        payload_schema_version_by_manifest=(
            ((schema_v1.name, schema_v1.version), "payload-v1"),
            ((schema_v2.name, schema_v2.version), "payload-v2"),
        ),
    )
    payload = _VersionedPayload(schema_version="payload-v1", value="unchanged")
    valid_ref = _put_json_view(
        store,
        payload.model_dump(mode="json"),
        kind=owner.kind,
        media_type=owner.media_type,
        schema=schema_v1,
    )
    manifest = store.get_manifest(valid_ref)
    relabelled_ref = store.put_bytes(
        store.get_bytes(valid_ref),
        PutOptions(
            kind=owner.kind,
            media_type=owner.media_type,
            schema=schema_v2,
            canon=manifest.canon,
        ),
        return_selected_profile=True,
    )

    with pytest.raises(CanonicalProfileRefusalError) as error:
        validate_owned_core_model_json_artifact(
            _VersionedPayload,
            store,
            relabelled_ref,
            expected_owner=owner,
        )

    assert error.value.code == "canon_profile_owned_payload_schema_version_mismatch"
    assert relabelled_ref.artifact_id == valid_ref.artifact_id


def test_selected_profile_is_returned_and_wrong_requested_profile_refuses(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path / "selected-profile")
    schema = SchemaInfo(name="owner.profiled", version="1")
    owner = CoreArtifactOwnerProfile(
        kind="owner.profiled",
        media_type="application/json",
        schema_variants=(schema,),
        payload_schema_version_by_manifest="not_applicable",
    )
    payload = {"value": 13}
    default_ref = _put_json_view(
        store,
        payload,
        kind=owner.kind,
        media_type=owner.media_type,
        schema=schema,
    )
    alternate_ref = _put_json_view(
        store,
        payload,
        kind=owner.kind,
        media_type=owner.media_type,
        schema=schema,
        ensure_ascii=True,
    )

    result = validate_owned_core_model_json_artifact(
        _OwnerlessPayload,
        store,
        alternate_ref,
        expected_owner=owner,
    )

    assert default_ref.artifact_id == alternate_ref.artifact_id
    assert result.artifact_ref == alternate_ref
    assert result.canon_profile.ensure_ascii is True
    with pytest.raises(CanonicalProfileRefusalError):
        validate_owned_core_model_json_artifact(
            _OwnerlessPayload,
            store,
            alternate_ref,
            expected_owner=owner,
            manifest_profile_sha256=default_ref.manifest_profile_sha256,
        )


@pytest.mark.parametrize(
    "owner_args",
    [
        pytest.param(
            {"schema_variants": None, "payload_schema_version_by_manifest": "not_applicable"},
            id="schema-none-is-not-unknown",
        ),
        pytest.param(
            {"schema_variants": (), "payload_schema_version_by_manifest": "not_applicable"},
            id="empty-schema-set",
        ),
        pytest.param(
            {
                "schema_variants": (
                    SchemaInfo(name="owner.schema", version="1"),
                    SchemaInfo(name="owner.schema", version="1"),
                ),
                "payload_schema_version_by_manifest": "not_applicable",
            },
            id="duplicate-schema-variant",
        ),
        pytest.param(
            {
                "schema_variants": (
                    SchemaInfo(name="owner.schema", version="1"),
                    SchemaInfo(name="owner.schema", version="2"),
                ),
                "payload_schema_version_by_manifest": ((("owner.schema", "1"), "1"),),
            },
            id="partial-version-relation",
        ),
        pytest.param(
            {
                "schema_variants": (SchemaInfo(name="owner.schema", version="1"),),
                "payload_schema_version_by_manifest": (
                    (("owner.schema", "1"), "1"),
                    (("owner.schema", "1"), "1"),
                ),
            },
            id="duplicate-version-relation",
        ),
        pytest.param(
            {
                "schema_variants": (SchemaInfo(name="owner.schema", version="1"),),
                "payload_schema_version_by_manifest": ((("owner.schema",), "1"),),
            },
            id="malformed-schema-key-tuple",
        ),
        pytest.param(
            {
                "schema_variants": [SchemaInfo(name="owner.schema", version="1")],
                "payload_schema_version_by_manifest": "not_applicable",
            },
            id="schema-variants-must-be-tuple",
        ),
    ],
)
def test_malformed_owner_profiles_refuse_without_inference(owner_args: dict[str, object]) -> None:
    with pytest.raises(ValueError, match="core_artifact_owner_profile_invalid"):
        CoreArtifactOwnerProfile(
            kind="owner.kind",
            media_type="application/json",
            **owner_args,
        )


@pytest.mark.parametrize(
    "owner_args",
    [
        pytest.param(
            {
                "schema_variants": _SentinelSpoof(),
                "payload_schema_version_by_manifest": "not_applicable",
            },
            id="schema-absence-sentinel-spoof",
        ),
        pytest.param(
            {
                "schema_variants": (SchemaInfo(name="owner.schema", version="1"),),
                "payload_schema_version_by_manifest": _SentinelSpoof(),
            },
            id="payload-nonapplicable-sentinel-spoof",
        ),
        pytest.param(
            {
                "schema_variants": "absent",
                "payload_schema_version_by_manifest": ((_SentinelSpoof(), "payload-v1"),),
            },
            id="absent-rule-key-sentinel-spoof",
        ),
        pytest.param(
            {
                "schema_variants": (SchemaInfo(name="owner.schema", version="1"),),
                "payload_schema_version_by_manifest": (((_SentinelSpoof(), "1"), "payload-v1"),),
            },
            id="schema-key-member-sentinel-spoof",
        ),
    ],
)
def test_sentinel_equality_spoofs_refuse_during_owner_construction(
    owner_args: dict[str, object],
) -> None:
    with pytest.raises(ValueError, match="core_artifact_owner_profile_invalid"):
        CoreArtifactOwnerProfile(
            kind="owner.kind",
            media_type="application/json",
            **owner_args,
        )


@pytest.mark.parametrize(
    ("field_name", "replacement"),
    [
        pytest.param("schema_variants", _SentinelSpoof(), id="schema-snapshot-sentinel-spoof"),
        pytest.param(
            "payload_schema_version_by_manifest",
            _SentinelSpoof(),
            id="payload-snapshot-sentinel-spoof",
        ),
        pytest.param(
            "payload_schema_version_by_manifest",
            ((_SentinelSpoof(), "payload-v1"),),
            id="payload-snapshot-rule-key-spoof",
        ),
        pytest.param("_payload_rules", _SentinelSpoof(), id="rule-snapshot-sentinel-spoof"),
        pytest.param(
            "_payload_rules",
            ((_SentinelSpoof(), "payload-v1"),),
            id="rule-snapshot-key-spoof",
        ),
    ],
)
def test_sentinel_equality_spoofs_refuse_during_snapshot_validation(
    field_name: str,
    replacement: object,
) -> None:
    schema = SchemaInfo(name="owner.schema", version="1")
    owner = CoreArtifactOwnerProfile(
        kind="owner.versioned",
        media_type="application/json",
        schema_variants=(schema,),
        payload_schema_version_by_manifest=(((schema.name, schema.version), "payload-v1"),),
    )
    object.__setattr__(owner, field_name, replacement)

    with pytest.raises(ValueError, match="core_artifact_owner_profile_invalid"):
        validate_owned_core_model_json_artifact(
            _VersionedPayload,
            object(),
            object(),
            expected_owner=owner,
        )


def test_schema_less_payload_requires_explicit_absent_relation(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path / "schema-less-versioned")
    ref = _put_json_view(
        store,
        {"schema_version": "payload-v1", "value": "x"},
        kind="owner.schema_less_versioned",
        media_type="application/json",
        schema=None,
    )
    owner = CoreArtifactOwnerProfile(
        kind="owner.schema_less_versioned",
        media_type="application/json",
        schema_variants="absent",
        payload_schema_version_by_manifest=(("absent", "payload-v1"),),
    )

    result = validate_owned_core_model_json_artifact(
        _VersionedPayload,
        store,
        ref,
        expected_owner=owner,
    )

    assert result.value == _VersionedPayload(schema_version="payload-v1", value="x")


def test_literal_absent_schema_version_is_not_the_absent_schema_state(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path / "schema-version-absent-literal")
    schema = SchemaInfo(name="owner.schema", version="absent")
    owner = CoreArtifactOwnerProfile(
        kind="owner.versioned",
        media_type="application/json",
        schema_variants=(schema,),
        payload_schema_version_by_manifest=(((schema.name, schema.version), "payload-v1"),),
    )
    ref = _put_json_view(
        store,
        {"schema_version": "payload-v1", "value": "x"},
        kind=owner.kind,
        media_type=owner.media_type,
        schema=schema,
    )

    result = validate_owned_core_model_json_artifact(
        _VersionedPayload,
        store,
        ref,
        expected_owner=owner,
    )

    assert result.value == _VersionedPayload(schema_version="payload-v1", value="x")
    assert store.get_manifest(result.artifact_ref).artifact_schema == schema


@pytest.mark.parametrize("mutated_index", [0, 1], ids=["first-schema", "second-schema"])
def test_owner_profile_copies_schema_values_and_refuses_nested_mutation(
    mutated_index: int,
) -> None:
    supplied_schema_a = SchemaInfo(name="owner.copied.a", version="1")
    supplied_schema_b = SchemaInfo(name="owner.copied.b", version="1")
    owner = CoreArtifactOwnerProfile(
        kind="owner.copied",
        media_type="application/json",
        schema_variants=(supplied_schema_b, supplied_schema_a),
        payload_schema_version_by_manifest="not_applicable",
    )
    supplied_schema_a.name = "changed.input.a"
    supplied_schema_b.name = "changed.input.b"

    assert owner.schema_variants == (
        SchemaInfo(name="owner.copied.a", version="1"),
        SchemaInfo(name="owner.copied.b", version="1"),
    )
    owner.schema_variants[mutated_index].name = "mutated.owner.profile"
    with pytest.raises(ValueError, match="core_artifact_owner_profile_invalid"):
        validate_owned_core_model_json_artifact(
            _OwnerlessPayload,
            object(),
            object(),
            expected_owner=owner,
        )


def test_missing_expected_owner_refuses_without_generic_fallback(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path / "missing-expected-owner")
    ref = _put_json_view(
        store,
        {"value": 9},
        kind="owner.required",
        media_type="application/json",
        schema=None,
    )

    with pytest.raises(CanonicalProfileRefusalError) as error:
        validate_owned_core_model_json_artifact(
            _OwnerlessPayload,
            store,
            ref,
            expected_owner=None,
        )

    assert error.value.code == "canon_profile_owned_artifact_owner_invalid"


def test_corrupt_blob_refuses_after_actual_cas_read(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path / "corrupt-cas")
    schema = SchemaInfo(name="owner.corrupt", version="1")
    owner = CoreArtifactOwnerProfile(
        kind="owner.corrupt",
        media_type="application/json",
        schema_variants=(schema,),
        payload_schema_version_by_manifest="not_applicable",
    )
    ref = _put_json_view(
        store,
        {"value": 5},
        kind=owner.kind,
        media_type=owner.media_type,
        schema=schema,
    )
    blob_path, _manifest_path = store._paths(ref.artifact_id)
    blob_path.write_bytes(b'{"value":6}')

    with pytest.raises(ArtifactIntegrityError):
        validate_owned_core_model_json_artifact(
            _OwnerlessPayload,
            store,
            ref,
            expected_owner=owner,
        )
