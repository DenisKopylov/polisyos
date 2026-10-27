from __future__ import annotations

import inspect
import json
import uuid
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, get_type_hints

import pytest
from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    from pathlib import Path

import polisyos.ir.artifacts.io as artifact_io
import polisyos.ir.migrations.base as migration_base
from polisyos.core.artifacts import FileSystemCAS
from polisyos.core.artifacts.ir_adapter import ensure_ir_artifact_store
from polisyos.core.canon import CanonSpec as CoreCanonSpec
from polisyos.ir.artifacts.contracts import (
    ArtifactOwnerDeclaration,
    CanonInfo,
    normalize_input_refs,
)
from polisyos.ir.artifacts.io import (
    _get_owned_json_artifact,
    _get_owned_json_artifact_with_bytes,
    _put_owned_json_artifact,
    get_json_artifact,
    put_json_artifact,
)
from polisyos.ir.migrations.base import (
    CompatibilityMode,
    IRRepresentationKey,
    register_ir_representation,
    register_schema_version,
)
from polisyos.ir.model_layer.canon import CanonViolation

WIRE_POLICY = ("test.resource-wire-law", "1")
DTO_FQN = "tests.unit.ir.artifacts.OwnedResourcePayload"


class OwnedResourcePayload(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    schema_version: str
    resource_id: str
    value: str


class CountingStore:
    def __init__(self, store: Any) -> None:
        self.store = store
        self.manifest_reads = 0
        self.payload_reads = 0
        self.put_calls = 0

    def get_manifest_bytes(self, selector: object) -> bytes:
        self.manifest_reads += 1
        return self.store.get_manifest_bytes(selector)

    def get_manifest(self, selector: object) -> object:
        return self.store.get_manifest(selector)

    def get_bytes(self, selector: object) -> bytes:
        self.payload_reads += 1
        return self.store.get_bytes(selector)

    def put_json(
        self,
        obj: object,
        opts: object,
        canon_spec: object = None,
        *,
        return_selected_profile: bool = False,
    ) -> object:
        self.put_calls += 1
        return self.store.put_json(
            obj,
            opts=opts,
            canon_spec=canon_spec,
            return_selected_profile=return_selected_profile,
        )


def _setup_owner_rows():
    registry_key = f"test.owned_resource.{uuid.uuid4().hex}"
    contract_id = f"tests.unit.ir.artifacts.OwnedResourcePayload.{uuid.uuid4().hex}"
    # One old tuple and a current tuple use an explicit direct-read edge. The
    # new resource/version row is current but deliberately not the default writer.
    for version in ("1.0", "1.1"):
        register_schema_version(
            registry_key,
            version,
            compatibility=CompatibilityMode.FULL,
        )
    register_ir_representation(
        registry_key=registry_key,
        owner_ref=contract_id,
        dto_abi=DTO_FQN,
        wire_policy_ref=WIRE_POLICY[0],
        wire_policy_revision=WIRE_POLICY[1],
        schema_name="test.unseen_resource",
        schema_version="1.0",
        payload_version="2.0",
        readable=True,
    )
    register_ir_representation(
        registry_key=registry_key,
        owner_ref=contract_id,
        dto_abi=DTO_FQN,
        wire_policy_ref=WIRE_POLICY[0],
        wire_policy_revision=WIRE_POLICY[1],
        schema_name="test.unseen_resource",
        schema_version="1.1",
        payload_version="2.1",
        readable=True,
        writable=True,
        current=True,
        default_write=True,
        readable_from=(IRRepresentationKey("test.unseen_resource", "1.0", "2.0"),),
    )
    register_ir_representation(
        registry_key=registry_key,
        owner_ref=contract_id,
        dto_abi=DTO_FQN,
        wire_policy_ref=WIRE_POLICY[0],
        wire_policy_revision=WIRE_POLICY[1],
        schema_name="test.new_unseen_resource",
        schema_version="1.0",
        payload_version="2.2",
        readable=True,
        writable=True,
        current=True,
        default_write=False,
    )
    register_schema_version(
        registry_key,
        "1.0",
        compatibility=CompatibilityMode.FULL,
    )
    return registry_key, contract_id


def _owner(
    registry_key: str,
    contract_id: str,
    *,
    accepted_wire_policies: tuple[tuple[str, str], ...] | None = None,
) -> ArtifactOwnerDeclaration:
    return ArtifactOwnerDeclaration(
        contract_id=contract_id,
        dto_fqn=DTO_FQN,
        abi_key="test.owned_resource_payload",
        registry_key=registry_key,
        kind="test.owned_resource",
        media_type="application/json",
        purpose="test.resource_admission",
        policy_revision="test-owner-policy-r1",
        accepted_wire_policies=(
            (WIRE_POLICY,) if accepted_wire_policies is None else accepted_wire_policies
        ),
        payload_version_of=lambda payload: payload.get("schema_version"),
        validate_source=lambda payload, admission: OwnedResourcePayload.model_validate(
            payload,
            strict=True,
        ),
        project_for_consumer=lambda source, admission: source,
        validate_profile=lambda profile, registration: (
            profile == CanonInfo() and registration.profile_ref is None
        ),
    )


def _store(tmp_path: Path):
    return ensure_ir_artifact_store(FileSystemCAS(tmp_path / "cas"))


def test_default_and_registered_nondefault_resource_round_trip_through_fresh_owner_reads(
    tmp_path: Path,
) -> None:
    registry_key, contract_id = _setup_owner_rows()
    store = _store(tmp_path)
    owner = _owner(registry_key, contract_id)

    current_ref = _put_owned_json_artifact(
        store,
        {
            "schema_version": "2.1",
            "resource_id": "unseen-policy-corpus-member",
            "value": "current",
        },
        owner=owner,
    )
    new_resource_ref = _put_owned_json_artifact(
        store,
        {
            "schema_version": "2.2",
            "resource_id": "different-unseen-member",
            "value": "same-owner-wire-law",
        },
        owner=owner,
        schema_name="test.new_unseen_resource",
        schema_version="1.0",
    )

    current = _get_owned_json_artifact_with_bytes(
        store,
        current_ref["artifact_id"],
        owner=_owner(registry_key, contract_id),
    )
    new_resource = _get_owned_json_artifact(
        store,
        new_resource_ref["artifact_id"],
        owner=_owner(registry_key, contract_id),
    )

    assert current.value.schema_version == "2.1"
    assert current.admission.source_registration.payload_version == "2.1"
    assert current.manifest_profile_sha256 == current_ref["manifest_profile_sha256"]
    assert current.raw_bytes
    assert new_resource.schema_version == "2.2"


def test_old_source_route_is_preserved_and_generic_reader_stays_opaque(
    tmp_path,
) -> None:
    registry_key, contract_id = _setup_owner_rows()
    store = _store(tmp_path)
    old_ref = put_json_artifact(
        store,
        {
            "schema_version": "2.0",
            "resource_id": "old-source",
            "value": "historical",
        },
        kind="test.owned_resource",
        schema_name="test.unseen_resource",
        schema_version="1.0",
        return_selected_profile=True,
    )

    # The generic reader proves canonical byte conformance only. Owner admission
    # separately resolves the exact source tuple and its current-reader route.
    assert get_json_artifact(store, old_ref["artifact_id"])["value"] == "historical"
    old_read = _get_owned_json_artifact_with_bytes(
        store,
        old_ref["artifact_id"],
        owner=_owner(registry_key, contract_id),
    )
    assert old_read.admission.source_registration.payload_version == "2.0"
    assert old_read.admission.current_registration.payload_version == "2.1"
    assert old_read.admission.migration_path == ()


def test_wrong_owner_and_wire_policy_refuse_before_payload_bytes(tmp_path) -> None:
    registry_key, contract_id = _setup_owner_rows()
    store = _store(tmp_path)
    ref = _put_owned_json_artifact(
        store,
        {
            "schema_version": "2.1",
            "resource_id": "member",
            "value": "payload",
        },
        owner=_owner(registry_key, contract_id),
    )
    reader = CountingStore(store)

    for owner in (
        _owner(registry_key, f"{contract_id}.foreign"),
        _owner(
            registry_key,
            contract_id,
            accepted_wire_policies=(("foreign-wire-law", "1"),),
        ),
    ):
        with pytest.raises(CanonViolation):
            _get_owned_json_artifact_with_bytes(
                reader,
                ref["artifact_id"],
                owner=owner,
            )
    assert reader.manifest_reads == 2
    assert reader.payload_reads == 0


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("kind", "test.foreign_resource"),
        ("media_type", "text/plain"),
        ("schema.name", "test.foreign_schema"),
        ("schema.version", "9.9"),
    ],
)
def test_wrong_manifest_identity_refuses_before_payload_bytes(
    tmp_path, field: str, value: str
) -> None:
    registry_key, contract_id = _setup_owner_rows()
    store = _store(tmp_path)
    ref = _put_owned_json_artifact(
        store,
        {
            "schema_version": "2.1",
            "resource_id": "member",
            "value": "payload",
        },
        owner=_owner(registry_key, contract_id),
    )

    class WrongKindReader(CountingStore):
        def _manifest(self, selector: object) -> dict[str, Any]:
            manifest = self.store.get_manifest(selector)
            if hasattr(manifest, "model_dump"):
                manifest = manifest.model_dump(mode="json", by_alias=True, exclude_none=True)
            result = dict(manifest)
            if field.startswith("schema."):
                result["schema"] = dict(result["schema"])
                result["schema"][field.partition(".")[2]] = value
            else:
                result[field] = value
            return result

        def get_manifest_bytes(self, selector: object) -> bytes:
            self.manifest_reads += 1
            return json.dumps(
                self._manifest(selector),
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ).encode()

        def get_manifest(self, selector: object) -> object:
            return self._manifest(selector)

    reader = WrongKindReader(store)
    with pytest.raises(CanonViolation):
        _get_owned_json_artifact_with_bytes(
            reader,
            ref["artifact_id"],
            owner=_owner(registry_key, contract_id),
        )
    assert reader.payload_reads == 0


@pytest.mark.parametrize(
    "override",
    [
        {"schema_name": "unregistered"},
        {"schema_name": "test.unseen_resource", "schema_version": ""},
        {"schema_name": "test.unseen_resource", "schema_version": False},
        {"schema_name": "test.unseen_resource", "schema_version": 0},
        {"schema_name": "test.unseen_resource", "schema_version": None},
        {"schema_name": None, "schema_version": "1.1"},
        {"schema_name": False, "schema_version": "1.1"},
        {"schema_name": 0, "schema_version": "1.1"},
        {"schema_name": "", "schema_version": "1.1"},
    ],
)
def test_unknown_or_malformed_write_override_refuses_before_cas(
    tmp_path: Path, override: dict[str, Any]
) -> None:
    registry_key, contract_id = _setup_owner_rows()
    store = CountingStore(_store(tmp_path))
    owner = _owner(registry_key, contract_id)
    payload = {"schema_version": "2.1", "resource_id": "member", "value": "payload"}

    with pytest.raises(CanonViolation):
        _put_owned_json_artifact(store, payload, owner=owner, **override)
    assert store.put_calls == 0


def test_incomplete_write_override_refuses_before_cas(tmp_path) -> None:
    registry_key, contract_id = _setup_owner_rows()
    store = CountingStore(_store(tmp_path))
    with pytest.raises(CanonViolation):
        _put_owned_json_artifact(
            store,
            {"schema_version": "2.1", "resource_id": "member", "value": "payload"},
            owner=_owner(registry_key, contract_id),
            schema_name="test.unseen_resource",
        )
    assert store.put_calls == 0


def test_wrong_registered_profile_refuses_before_payload_bytes(tmp_path) -> None:
    registry_key, contract_id = _setup_owner_rows()
    store = _store(tmp_path)
    ref = _put_owned_json_artifact(
        store,
        {
            "schema_version": "2.1",
            "resource_id": "member",
            "value": "payload",
        },
        owner=_owner(registry_key, contract_id),
    )

    class WrongProfileReader(CountingStore):
        def _manifest(self, selector: object) -> dict[str, Any]:
            manifest = self.store.get_manifest(selector)
            if hasattr(manifest, "model_dump"):
                manifest = manifest.model_dump(mode="json", by_alias=True, exclude_none=True)
            result = dict(manifest)
            result["canon"] = dict(result["canon"])
            result["canon"]["forbid_floats"] = False
            return result

        def get_manifest_bytes(self, selector: object) -> bytes:
            self.manifest_reads += 1
            return json.dumps(
                self._manifest(selector),
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ).encode()

        def get_manifest(self, selector: object) -> object:
            return self._manifest(selector)

    reader = WrongProfileReader(store)
    # Use the ID only, so the selected-view profile hash is not the earlier profile.
    with pytest.raises(CanonViolation, match="ir_owned_artifact_profile_refused"):
        _get_owned_json_artifact_with_bytes(
            reader,
            ref["artifact_id"],
            owner=_owner(registry_key, contract_id),
        )
    assert reader.payload_reads == 0


@pytest.mark.parametrize("mismatch", ["dto_fqn", "wire_policy"])
def test_existing_owner_row_with_wrong_dto_or_wire_refuses_before_payload(
    tmp_path: Path, mismatch: str
) -> None:
    from dataclasses import replace

    registry_key, contract_id = _setup_owner_rows()
    store = _store(tmp_path)
    owner = _owner(registry_key, contract_id)
    ref = _put_owned_json_artifact(
        store,
        {"schema_version": "2.1", "resource_id": "member", "value": "payload"},
        owner=owner,
    )
    if mismatch == "dto_fqn":
        mismatched_owner = replace(owner, dto_fqn=owner.dto_fqn + ".unexpected")
    else:
        mismatched_owner = _owner(
            registry_key, contract_id, accepted_wire_policies=(("other-wire-law", "1"),)
        )

    reader = CountingStore(store)
    with pytest.raises(CanonViolation, match="ir_owned_artifact_owner_contract_mismatch"):
        _get_owned_json_artifact_with_bytes(reader, ref["artifact_id"], owner=mismatched_owner)
    assert reader.payload_reads == 0


def test_absent_owner_row_remains_unregistered_before_payload(tmp_path: Path) -> None:
    registry_key, contract_id = _setup_owner_rows()
    store = _store(tmp_path)
    ref = put_json_artifact(
        store,
        {"schema_version": "2.1", "resource_id": "member", "value": "payload"},
        kind="test.owned_resource",
        schema_name="test.absent_resource",
        schema_version="1.0",
        return_selected_profile=True,
    )
    reader = CountingStore(store)
    with pytest.raises(CanonViolation, match="ir_owned_artifact_representation_unregistered"):
        _get_owned_json_artifact_with_bytes(
            reader, ref["artifact_id"], owner=_owner(registry_key, contract_id)
        )
    assert reader.payload_reads == 0


def test_invalid_owner_preflight_snapshot_refuses_before_payload(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from dataclasses import replace

    registry_key, contract_id = _setup_owner_rows()
    store = _store(tmp_path)
    owner = _owner(registry_key, contract_id)
    ref = _put_owned_json_artifact(
        store,
        {"schema_version": "2.1", "resource_id": "member", "value": "payload"},
        owner=owner,
    )
    original = migration_base.find_owned_representation

    def wrong_snapshot(*args: object, **kwargs: object) -> object:
        found = original(*args, **kwargs)
        assert found is not None
        return replace(found, snapshot_revision="invalid-snapshot")

    monkeypatch.setattr(migration_base, "find_owned_representation", wrong_snapshot)
    reader = CountingStore(store)
    with pytest.raises(CanonViolation, match="ir_owned_artifact_registry_invalid"):
        _get_owned_json_artifact_with_bytes(reader, ref["artifact_id"], owner=owner)
    assert reader.payload_reads == 0


@pytest.mark.parametrize("mismatch", ["source_wire", "current_dto", "current_wire"])
def test_postdecode_registered_source_or_current_owner_mismatch_is_distinct(
    tmp_path: Path, mismatch: str
) -> None:
    registry_key = f"test.owned_route.{uuid.uuid4().hex}"
    contract_id = f"tests.unit.ir.artifacts.OwnedRoute.{uuid.uuid4().hex}"
    source_key = IRRepresentationKey("test.unseen_resource", "1.0", "2.0")
    if mismatch == "source_wire":
        register_schema_version(registry_key, "1.0", compatibility=CompatibilityMode.FULL)
        variant_key = IRRepresentationKey("test.unseen_resource", "1.0", "2.2")
        register_ir_representation(
            registry_key=registry_key,
            owner_ref=contract_id,
            dto_abi=DTO_FQN,
            wire_policy_ref="other-wire-law",
            wire_policy_revision="1",
            schema_name=variant_key.schema_name,
            schema_version=variant_key.schema_version,
            payload_version=variant_key.payload_version,
            readable=True,
        )
        register_ir_representation(
            registry_key=registry_key,
            owner_ref=contract_id,
            dto_abi=DTO_FQN,
            wire_policy_ref=WIRE_POLICY[0],
            wire_policy_revision=WIRE_POLICY[1],
            schema_name=source_key.schema_name,
            schema_version=source_key.schema_version,
            payload_version=source_key.payload_version,
            readable=True,
            writable=True,
            current=True,
            default_write=True,
            readable_from=(variant_key,),
        )
        manifest_version, payload_version = "1.0", "2.2"
    else:
        register_schema_version(registry_key, "1.0", compatibility=CompatibilityMode.FULL)
        register_schema_version(registry_key, "1.1", compatibility=CompatibilityMode.FULL)
        register_ir_representation(
            registry_key=registry_key,
            owner_ref=contract_id,
            dto_abi=DTO_FQN,
            wire_policy_ref=WIRE_POLICY[0],
            wire_policy_revision=WIRE_POLICY[1],
            schema_name=source_key.schema_name,
            schema_version=source_key.schema_version,
            payload_version=source_key.payload_version,
            readable=True,
        )
        current_abi = DTO_FQN + ".next" if mismatch == "current_dto" else DTO_FQN
        current_wire = ("other-wire-law", "1") if mismatch == "current_wire" else WIRE_POLICY
        register_ir_representation(
            registry_key=registry_key,
            owner_ref=contract_id,
            dto_abi=current_abi,
            wire_policy_ref=current_wire[0],
            wire_policy_revision=current_wire[1],
            schema_name=source_key.schema_name,
            schema_version="1.1",
            payload_version="2.1",
            readable=True,
            writable=True,
            current=True,
            default_write=True,
            readable_from=(source_key,),
        )
        manifest_version, payload_version = "1.0", "2.0"
    owner = _owner(registry_key, contract_id)
    store = _store(tmp_path)
    ref = put_json_artifact(
        store,
        {
            "schema_version": payload_version,
            "resource_id": "member",
            "value": "payload",
        },
        kind="test.owned_resource",
        schema_name=source_key.schema_name,
        schema_version=manifest_version,
        return_selected_profile=True,
    )
    reader = CountingStore(store)
    with pytest.raises(CanonViolation, match="ir_owned_artifact_owner_contract_mismatch"):
        _get_owned_json_artifact_with_bytes(reader, ref["artifact_id"], owner=owner)
    assert reader.payload_reads == 1


def test_payload_bytes_are_hash_bound_before_owner_projection(tmp_path) -> None:
    registry_key, contract_id = _setup_owner_rows()
    store = _store(tmp_path)
    ref = _put_owned_json_artifact(
        store,
        {
            "schema_version": "2.1",
            "resource_id": "member",
            "value": "payload",
        },
        owner=_owner(registry_key, contract_id),
    )

    class TamperedPayloadReader(CountingStore):
        def get_bytes(self, selector: object) -> bytes:
            self.payload_reads += 1
            return self.store.get_bytes(selector) + b" "

    reader = TamperedPayloadReader(store)
    with pytest.raises(CanonViolation, match="ir_artifact_payload_identity_mismatch"):
        _get_owned_json_artifact_with_bytes(
            reader,
            ref["artifact_id"],
            owner=_owner(registry_key, contract_id),
        )
    assert reader.payload_reads == 1


def test_payload_version_not_registered_refuses_after_content_hash_read(
    tmp_path,
) -> None:
    registry_key, contract_id = _setup_owner_rows()
    store = _store(tmp_path)
    foreign_ref = put_json_artifact(
        store,
        {
            "schema_version": "9.9",
            "resource_id": "member",
            "value": "payload",
        },
        kind="test.owned_resource",
        schema_name="test.unseen_resource",
        schema_version="1.1",
        return_selected_profile=True,
    )
    reader = CountingStore(store)

    with pytest.raises(CanonViolation):
        _get_owned_json_artifact_with_bytes(
            reader,
            foreign_ref["artifact_id"],
            owner=_owner(registry_key, contract_id),
        )
    assert reader.payload_reads == 1


def test_generic_reader_and_type_introspection_abi_remain_available() -> None:
    assert artifact_io.InputRefLike is not None
    hints = get_type_hints(artifact_io.put_json_artifact)
    assert hints["inputs"] == Sequence[artifact_io.InputRefLike] | None
    assert list(inspect.signature(artifact_io._get_json_artifact_with_bytes).parameters) == [
        "store",
        "artifact_id",
    ]
    assert artifact_io.get_json_artifact_with_bytes is artifact_io._get_json_artifact_with_bytes


def test_owned_writer_preserves_profileless_api_refusal_before_put() -> None:
    registry_key, contract_id = _setup_owner_rows()

    class LegacyWriter:
        put_calls = 0

        def put_json(self, obj: object, opts: object, canon_spec: object = None) -> object:
            self.put_calls += 1
            raise AssertionError("unsupported selected-profile writer must not be called")

    store = LegacyWriter()
    with pytest.raises(
        NotImplementedError,
        match="artifact_store_return_selected_profile_unsupported",
    ):
        _put_owned_json_artifact(
            store,
            {"schema_version": "2.1", "resource_id": "member", "value": "payload"},
            owner=_owner(registry_key, contract_id),
        )
    assert store.put_calls == 0


@pytest.mark.parametrize("bad_inputs", [False, 0, "", b"", {"not-a-sequence": True}])
def test_generic_writer_and_lineage_helpers_reject_malformed_present_inputs_before_cas(
    tmp_path: Path, bad_inputs: object
) -> None:
    with pytest.raises(CanonViolation, match="ir_artifact_inputs_invalid"):
        normalize_input_refs(bad_inputs)
    with pytest.raises(CanonViolation, match="ir_artifact_inputs_invalid"):
        artifact_io.normalize_input_sequence(bad_inputs)
    store = CountingStore(_store(tmp_path))
    with pytest.raises(CanonViolation, match="ir_artifact_inputs_invalid"):
        put_json_artifact(
            store,
            {"value": "candidate"},
            kind="test.generic_input_contract",
            schema_name="test.generic_input_contract",
            schema_version="1.0",
            inputs=bad_inputs,
        )
    assert store.put_calls == 0


@pytest.mark.parametrize(
    "bad_spec",
    [
        False,
        0,
        object(),
        pytest.param(CoreCanonSpec(forbid_floats=False), id="foreign-core-canon-spec"),
    ],
)
def test_generic_writer_rejects_malformed_present_canon_spec_before_cas(
    tmp_path: Path, bad_spec: object
) -> None:
    store = CountingStore(_store(tmp_path))
    with pytest.raises(CanonViolation, match="ir_artifact_canon_spec_invalid"):
        put_json_artifact(
            store,
            {"value": "candidate"},
            kind="test.generic_canon_contract",
            schema_name="test.generic_canon_contract",
            schema_version="1.0",
            canon_spec=bad_spec,
        )
    assert store.put_calls == 0


@pytest.mark.parametrize("empty_inputs", [None, [], ()])
def test_generic_writer_preserves_absent_and_valid_explicit_empty_lineage(
    tmp_path: Path, empty_inputs: object
) -> None:
    assert normalize_input_refs(empty_inputs) == []
    store = CountingStore(_store(tmp_path))
    payload = {"value": "empty-lineage-is-valid"}
    ref = put_json_artifact(
        store,
        payload,
        kind="test.generic_empty_lineage",
        schema_name="test.generic_empty_lineage",
        schema_version="1.0",
        inputs=empty_inputs,
    )
    assert store.put_calls == 1
    assert get_json_artifact(store, ref["artifact_id"]) == payload


def test_unknown_history_is_generic_opaque_but_refused_by_typed_owner(
    tmp_path: Path,
) -> None:
    registry_key, contract_id = _setup_owner_rows()
    store = _store(tmp_path)
    payload = {
        "schema_version": "9.9",
        "resource_id": "unknown-history",
        "value": "preserve-as-opaque-json",
    }
    ref = put_json_artifact(
        store,
        payload,
        kind="test.owned_resource",
        schema_name="test.unknown_history",
        schema_version="9.0",
        return_selected_profile=True,
    )

    opaque, raw_bytes = artifact_io.get_json_artifact_with_bytes(store, ref["artifact_id"])
    assert opaque == payload
    assert raw_bytes == store.get_bytes(ref["artifact_id"])

    reader = CountingStore(store)
    with pytest.raises(
        CanonViolation,
        match="ir_owned_artifact_representation_unregistered",
    ):
        _get_owned_json_artifact_with_bytes(
            reader,
            ref["artifact_id"],
            owner=_owner(registry_key, contract_id),
        )
    assert reader.manifest_reads == 1
    assert reader.payload_reads == 0


class RolloutPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    schema_version: str
    resource_id: str
    value: str
    rolled_forward: bool = False


ROLLOUT_DTO_FQN = "tests.unit.ir.artifacts.RolloutPayload"
ROLLOUT_SCHEMA = "test.rollout_resource"
ROLLOUT_KIND = "test.rollout_resource"
ROLLOUT_OLD_WIRE = ("test.rollout.old-wire", "1")
ROLLOUT_NEW_WIRE = ("test.rollout.new-wire", "2")


def _rollout_owner(registry_key: str, contract_id: str) -> ArtifactOwnerDeclaration:
    def project(source: RolloutPayload, admission: Any) -> RolloutPayload:
        if admission.migration_path:
            from polisyos.ir.migrations.base import migrate_artifact

            value = migrate_artifact(
                source.model_dump(),
                registry_key,
                admission.migration_path[-1],
            )
        else:
            value = source.model_dump()
        return RolloutPayload.model_validate(value, strict=True)

    return ArtifactOwnerDeclaration(
        contract_id=contract_id,
        dto_fqn=ROLLOUT_DTO_FQN,
        abi_key="test.rollout_payload",
        registry_key=registry_key,
        kind=ROLLOUT_KIND,
        media_type="application/json",
        purpose="test.rollout_admission",
        policy_revision="test-rollout-owner-r1",
        accepted_wire_policies=(ROLLOUT_OLD_WIRE, ROLLOUT_NEW_WIRE),
        payload_version_of=lambda payload: payload.get("schema_version"),
        validate_source=lambda payload, admission: RolloutPayload.model_validate(
            payload,
            strict=True,
        ),
        project_for_consumer=project,
        validate_profile=lambda profile, registration: (
            profile == CanonInfo() and registration.profile_ref is None
        ),
    )


def test_owned_forward_read_old_reader_refusal_and_rollback_preserve_cas_bytes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry_key = f"test.rollout.current.{uuid.uuid4().hex}"
    contract_id = f"tests.unit.ir.artifacts.RolloutOwner.{uuid.uuid4().hex}"
    old_registry_key = f"test.rollout.old_reader.{uuid.uuid4().hex}"
    old_contract_id = f"tests.unit.ir.artifacts.OldRolloutOwner.{uuid.uuid4().hex}"
    register_schema_version(registry_key, "1.0", compatibility=CompatibilityMode.FULL)
    register_schema_version(registry_key, "1.1", compatibility=CompatibilityMode.FULL)
    register_schema_version(old_registry_key, "1.0", compatibility=CompatibilityMode.FULL)

    def upgrade(payload: dict[str, object]) -> dict[str, object]:
        return {
            **payload,
            "schema_version": "2.1",
            "rolled_forward": True,
        }

    from polisyos.ir.migrations.base import register_migration

    register_migration(
        registry_key,
        "2.0",
        "2.1",
        compatibility=CompatibilityMode.BACKWARD,
    )(upgrade)

    register_ir_representation(
        registry_key=registry_key,
        owner_ref=contract_id,
        dto_abi=ROLLOUT_DTO_FQN,
        wire_policy_ref=ROLLOUT_OLD_WIRE[0],
        wire_policy_revision=ROLLOUT_OLD_WIRE[1],
        schema_name=ROLLOUT_SCHEMA,
        schema_version="1.0",
        payload_version="2.0",
        readable=True,
        writable=True,
    )
    register_ir_representation(
        registry_key=registry_key,
        owner_ref=contract_id,
        dto_abi=ROLLOUT_DTO_FQN,
        wire_policy_ref=ROLLOUT_NEW_WIRE[0],
        wire_policy_revision=ROLLOUT_NEW_WIRE[1],
        schema_name=ROLLOUT_SCHEMA,
        schema_version="1.1",
        payload_version="2.1",
        readable=True,
        writable=True,
        current=True,
        default_write=True,
    )
    register_ir_representation(
        registry_key=old_registry_key,
        owner_ref=old_contract_id,
        dto_abi=ROLLOUT_DTO_FQN,
        wire_policy_ref=ROLLOUT_OLD_WIRE[0],
        wire_policy_revision=ROLLOUT_OLD_WIRE[1],
        schema_name=ROLLOUT_SCHEMA,
        schema_version="1.0",
        payload_version="2.0",
        readable=True,
        writable=True,
        current=True,
        default_write=True,
    )
    new_owner = _rollout_owner(registry_key, contract_id)
    old_owner = _rollout_owner(old_registry_key, old_contract_id)
    store = _store(tmp_path)
    original_payload = {
        "schema_version": "2.0",
        "resource_id": "historical-member",
        "value": "original-old-wire",
    }
    old_ref = put_json_artifact(
        store,
        original_payload,
        kind=ROLLOUT_KIND,
        schema_name=ROLLOUT_SCHEMA,
        schema_version="1.0",
        return_selected_profile=True,
    )
    old_id = old_ref["artifact_id"]
    original_payload_bytes = store.get_bytes(old_id)
    original_manifest_bytes = store.get_manifest_bytes(old_id)

    old_reader_view = _get_owned_json_artifact_with_bytes(
        store,
        old_id,
        owner=old_owner,
    )
    assert old_reader_view.value.rolled_forward is False
    forward_view = _get_owned_json_artifact_with_bytes(
        store,
        old_id,
        owner=new_owner,
    )
    assert forward_view.admission.compatibility_kind is migration_base.IRCompatibilityKind.MIGRATION
    assert forward_view.admission.migration_path == ("2.0", "2.1")
    assert forward_view.value.schema_version == "2.1"
    assert forward_view.value.rolled_forward is True
    assert forward_view.raw_bytes == original_payload_bytes

    new_writer = CountingStore(store)
    current_ref = _put_owned_json_artifact(
        new_writer,
        {
            "schema_version": "2.1",
            "resource_id": "forward-member",
            "value": "new-wire",
            "rolled_forward": True,
        },
        owner=new_owner,
    )
    current_id = current_ref["artifact_id"]
    current_payload_bytes = store.get_bytes(current_id)
    current_manifest_bytes = store.get_manifest_bytes(current_id)
    old_reader = CountingStore(store)
    with pytest.raises(
        CanonViolation,
        match="ir_owned_artifact_representation_unregistered",
    ):
        _get_owned_json_artifact_with_bytes(
            old_reader,
            current_id,
            owner=old_owner,
        )
    assert old_reader.manifest_reads == 1
    assert old_reader.payload_reads == 0

    rollback_payload = dict(original_payload)
    rollback_ref = _put_owned_json_artifact(
        store,
        rollback_payload,
        owner=new_owner,
        schema_name=ROLLOUT_SCHEMA,
        schema_version="1.0",
    )
    rollback_id = rollback_ref["artifact_id"]
    rollback_view = _get_owned_json_artifact_with_bytes(
        store,
        rollback_id,
        owner=new_owner,
    )
    assert (
        rollback_view.admission.compatibility_kind is migration_base.IRCompatibilityKind.MIGRATION
    )
    assert rollback_view.value.rolled_forward is True
    assert store.get_bytes(rollback_id) == original_payload_bytes
    assert store.get_manifest_bytes(old_id) == original_manifest_bytes
    assert store.get_bytes(old_id) == original_payload_bytes
    assert store.get_bytes(current_id) == current_payload_bytes
    assert store.get_manifest_bytes(current_id) == current_manifest_bytes

    assert (
        migration_base.find_writable_representation(
            migration_base.get_ir_owner_registry_snapshot(),
            registry_key,
            owner_ref=contract_id,
            schema_name=ROLLOUT_SCHEMA,
            schema_version="1.1",
            payload_version="2.1",
        )
        is not None
    )
    assert (
        migration_base.resolve_owned_representation(
            migration_base.get_ir_owner_registry_snapshot(),
            registry_key,
            owner_ref=contract_id,
            schema_name=ROLLOUT_SCHEMA,
            schema_version="1.1",
            payload_version="2.1",
        )
        is not None
    )
    original_resolver = migration_base.resolve_owned_representation
    refusal_store = CountingStore(store)
    monkeypatch.setattr(migration_base, "resolve_owned_representation", lambda *a, **k: None)
    with pytest.raises(CanonViolation, match="ir_owned_artifact_write_route_unavailable"):
        _put_owned_json_artifact(
            refusal_store,
            {
                "schema_version": "2.1",
                "resource_id": "must-not-write",
                "value": "no-route",
                "rolled_forward": True,
            },
            owner=new_owner,
        )
    assert refusal_store.put_calls == 0
    monkeypatch.setattr(migration_base, "resolve_owned_representation", original_resolver)


def test_owned_direct_read_crosses_wire_policies_through_real_cas(
    tmp_path: Path,
) -> None:
    registry_key = f"test.cross_wire_direct.{uuid.uuid4().hex}"
    contract_id = f"tests.unit.ir.artifacts.CrossWireOwner.{uuid.uuid4().hex}"
    schema_name = "test.cross_wire_direct_resource"
    old_wire_policy = ("test.cross_wire.old-law", "1")
    current_wire_policy = ("test.cross_wire.current-law", "2")
    old_key = IRRepresentationKey(schema_name, "1.0", "2.0")

    register_schema_version(registry_key, "1.0", compatibility=CompatibilityMode.FULL)
    register_schema_version(registry_key, "1.1", compatibility=CompatibilityMode.FULL)
    register_ir_representation(
        registry_key=registry_key,
        owner_ref=contract_id,
        dto_abi=DTO_FQN,
        wire_policy_ref=old_wire_policy[0],
        wire_policy_revision=old_wire_policy[1],
        schema_name=schema_name,
        schema_version="1.0",
        payload_version="2.0",
        readable=True,
    )
    register_ir_representation(
        registry_key=registry_key,
        owner_ref=contract_id,
        dto_abi=DTO_FQN,
        wire_policy_ref=current_wire_policy[0],
        wire_policy_revision=current_wire_policy[1],
        schema_name=schema_name,
        schema_version="1.1",
        payload_version="2.1",
        readable=True,
        writable=True,
        current=True,
        default_write=True,
        readable_from=(old_key,),
    )
    owner = _owner(
        registry_key,
        contract_id,
        accepted_wire_policies=(old_wire_policy, current_wire_policy),
    )
    store = _store(tmp_path)
    original_payload = {
        "schema_version": "2.0",
        "resource_id": "cross-wire-historical-member",
        "value": "read-through-explicit-owner-route",
    }
    ref = put_json_artifact(
        store,
        original_payload,
        kind="test.owned_resource",
        schema_name=schema_name,
        schema_version="1.0",
        return_selected_profile=True,
    )
    artifact_id = ref["artifact_id"]
    original_payload_bytes = store.get_bytes(artifact_id)
    original_manifest_bytes = store.get_manifest_bytes(artifact_id)

    reader = CountingStore(store)
    admitted = _get_owned_json_artifact_with_bytes(
        reader,
        artifact_id,
        owner=owner,
    )

    assert owner.accepted_wire_policies == (old_wire_policy, current_wire_policy)
    assert admitted.admission.compatibility_kind is migration_base.IRCompatibilityKind.DIRECT
    assert admitted.admission.migration_path == ()
    assert admitted.admission.source_registration.key == old_key
    assert admitted.admission.source_registration.wire_policy_ref == old_wire_policy[0]
    assert admitted.admission.source_registration.wire_policy_revision == old_wire_policy[1]
    assert admitted.admission.current_registration.wire_policy_ref == current_wire_policy[0]
    assert admitted.admission.current_registration.wire_policy_revision == current_wire_policy[1]
    assert admitted.value == OwnedResourcePayload.model_validate(
        original_payload,
        strict=True,
    )
    assert admitted.raw_bytes == original_payload_bytes
    assert reader.manifest_reads == 1
    assert reader.payload_reads == 1
    assert store.get_bytes(artifact_id) == original_payload_bytes
    assert store.get_manifest_bytes(artifact_id) == original_manifest_bytes
