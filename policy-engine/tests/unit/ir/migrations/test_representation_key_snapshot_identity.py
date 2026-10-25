from __future__ import annotations

from uuid import uuid4

import pytest

import polisyos.ir.migrations.base as base


class MutableText(str):
    def __new__(cls, value: str) -> MutableText:
        instance = super().__new__(cls, value)
        instance.identity_value = value
        return instance

    def __eq__(self, other: object) -> bool:
        return self.identity_value == str(other)

    def __hash__(self) -> int:
        return hash(self.identity_value)


def test_representation_key_rejects_malformed_fields() -> None:
    with pytest.raises(base.MigrationCompatibilityError):
        base.IRRepresentationKey("", "1.0", "1.0")
    with pytest.raises(base.MigrationCompatibilityError):
        base.IRRepresentationKey("test.schema", "1.0", 2)


def test_registry_freezes_relation_keys_before_snapshot_publication() -> None:
    registry = f"tests.central.key-snapshot.{uuid4().hex}"
    owner = f"tests.central.owner.{uuid4().hex}"
    schema = f"tests.central.schema.{uuid4().hex}"
    base.register_schema_version(registry, "1.0", compatibility=base.CompatibilityMode.NONE)
    base.register_schema_version(registry, "1.1", compatibility=base.CompatibilityMode.NONE)
    source = base.register_ir_representation(
        registry_key=registry,
        owner_ref=owner,
        dto_abi="tests.central.Payload@1",
        wire_policy_ref="tests.central.wire",
        wire_policy_revision="1",
        schema_name=schema,
        schema_version="1.0",
        payload_version="1.0",
        readable=True,
        writable=False,
        current=False,
        default_write=False,
    )
    mutable_fields = (
        MutableText(source.schema_name),
        MutableText(source.schema_version),
        MutableText(source.payload_version),
    )
    relation = base.IRRepresentationKey(*mutable_fields)
    current = base.register_ir_representation(
        registry_key=registry,
        owner_ref=owner,
        dto_abi="tests.central.Payload@1",
        wire_policy_ref="tests.central.wire",
        wire_policy_revision="1",
        schema_name=schema,
        schema_version="1.1",
        payload_version="1.1",
        readable=True,
        writable=True,
        current=True,
        default_write=True,
        readable_from=(relation,),
    )

    for value in mutable_fields:
        value.identity_value = "changed"
    snapshot = base.get_ir_owner_registry_snapshot()
    assert type(current.readable_from[0]) is base.IRRepresentationKey
    assert all(
        type(getattr(current.readable_from[0], field)) is str
        for field in ("schema_name", "schema_version", "payload_version")
    )
    admission = base.resolve_owned_representation(
        snapshot,
        registry,
        owner_ref=owner,
        schema_name=schema,
        schema_version="1.0",
        payload_version="1.0",
    )
    assert admission is not None
    assert admission.compatibility_kind is base.IRCompatibilityKind.DIRECT


def test_registration_normalizes_mutable_owner_and_representation_strings() -> None:
    registry = f"tests.central.text-snapshot.{uuid4().hex}"
    owner = f"tests.central.owner.{uuid4().hex}"
    schema = f"tests.central.schema.{uuid4().hex}"
    base.register_schema_version(registry, "1.0", compatibility=base.CompatibilityMode.NONE)
    registry_arg = MutableText(registry)
    owner_arg = MutableText(owner)
    schema_arg = MutableText(schema)
    row = base.register_ir_representation(
        registry_key=registry_arg,
        owner_ref=owner_arg,
        dto_abi=MutableText("tests.central.Payload@1"),
        wire_policy_ref=MutableText("tests.central.wire"),
        wire_policy_revision=MutableText("1"),
        schema_name=schema_arg,
        schema_version=MutableText("1.0"),
        payload_version=MutableText("1.0"),
        readable=True,
        writable=True,
        current=True,
        default_write=True,
    )
    for value in (registry_arg, owner_arg, schema_arg):
        value.identity_value = "changed"
    assert row.registry_key == registry
    assert row.owner_ref == owner
    assert row.schema_name == schema
    assert all(
        type(getattr(row, field)) is str
        for field in (
            "registry_key",
            "owner_ref",
            "dto_abi",
            "wire_policy_ref",
            "wire_policy_revision",
            "schema_name",
            "schema_version",
            "payload_version",
        )
    )


def test_unknown_readable_from_tuple_and_fake_key_are_rejected() -> None:
    registry = f"tests.central.unknown-key.{uuid4().hex}"
    owner = f"tests.central.owner.{uuid4().hex}"
    schema = f"tests.central.schema.{uuid4().hex}"
    base.register_schema_version(registry, "1.0", compatibility=base.CompatibilityMode.NONE)
    fake = ("not", "an", "IRRepresentationKey")
    with pytest.raises(base.MigrationCompatibilityError):
        base.register_ir_representation(
            registry_key=registry,
            owner_ref=owner,
            dto_abi="tests.central.Payload@1",
            wire_policy_ref="tests.central.wire",
            wire_policy_revision="1",
            schema_name=schema,
            schema_version="1.0",
            payload_version="1.0",
            readable=True,
            writable=True,
            current=True,
            default_write=True,
            readable_from=(fake,),
        )
    with pytest.raises(base.MigrationCompatibilityError):
        base.register_ir_representation(
            registry_key=registry,
            owner_ref=owner,
            dto_abi="tests.central.Payload@1",
            wire_policy_ref="tests.central.wire",
            wire_policy_revision="1",
            schema_name=schema,
            schema_version="1.0",
            payload_version="1.0",
            readable=True,
            writable=True,
            current=True,
            default_write=True,
            readable_from=(base.IRRepresentationKey("not.registered", "9.9", "9.9"),),
        )
