from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import BaseModel, ConfigDict

import polisyos.ir.analytics._owner_admission as owner_api
import polisyos.ir.artifacts.contracts as contracts
import polisyos.ir.artifacts.io as io
import polisyos.ir.migrations.base as base
from polisyos.core.artifacts import FileSystemCAS
from polisyos.core.artifacts.ir_adapter import ensure_ir_artifact_store
from polisyos.ir.model_layer.canon import CanonSpec

WIRE = ("tests.central.snapshot-wire", "1")


class Payload(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    schema_version: str
    value: str


def _owner(registry: str, contract_id: str, payload_version_of, validate_source):
    return contracts.ArtifactOwnerDeclaration(
        contract_id=contract_id,
        dto_fqn="tests.central.Payload",
        abi_key="tests.central.Payload@1",
        registry_key=registry,
        kind="tests.central.payload",
        media_type="application/json",
        purpose="test central frozen owner input",
        policy_revision="tests.central.r1",
        accepted_wire_policies=(WIRE,),
        payload_version_of=payload_version_of,
        validate_source=validate_source,
        project_for_consumer=lambda source, _admission: source,
        validate_profile=lambda _profile, _registration: True,
    )


def _representation(
    schema_name: str,
    schema_version: str,
    payload_version: str,
    *,
    current: bool,
    default_write: bool,
):
    return owner_api.OwnedJSONRepresentation(
        schema_name=schema_name,
        schema_version=schema_version,
        payload_version=payload_version,
        wire_policy_ref=WIRE[0],
        wire_policy_revision=WIRE[1],
        profile_ref=None,
        compatibility=base.CompatibilityMode.NONE,
        notes=(),
        readable=True,
        writable=True,
        current=current,
        default_write=default_write,
        readable_from=(),
    )


def _store(tmp_path: Path):
    return ensure_ir_artifact_store(FileSystemCAS(tmp_path / "cas"))


def test_owner_write_freezes_before_validation_and_persists_same_value(tmp_path: Path) -> None:
    registry = f"tests.central.snapshot.{uuid4().hex}"
    schema = f"tests.central.snapshot-schema.{uuid4().hex}"
    contract_id = f"tests.central.Payload.{uuid4().hex}"
    caller_payload = {"schema_version": "1.0", "value": "before-validation"}

    def version_of(payload):
        if not isinstance(payload, Mapping):
            raise TypeError("mapping required")
        return payload.get("schema_version")

    def validate(payload, _admission):
        parsed = Payload.model_validate(dict(payload))
        caller_payload["value"] = "after-validation"
        return parsed

    owner = _owner(registry, contract_id, version_of, validate)
    base.register_schema_version(registry, "1.0", compatibility=base.CompatibilityMode.NONE)
    owner_api.register_owner_representations(
        owner,
        (_representation(schema, "1.0", "1.0", current=True, default_write=True),),
    )

    store = _store(tmp_path)
    ref = io._put_owned_json_artifact(store, caller_payload, owner=owner)
    stored = io.get_json_artifact(store, ref["artifact_id"])

    assert caller_payload["value"] == "after-validation"
    assert stored == {"schema_version": "1.0", "value": "before-validation"}
    result = io._get_owned_json_artifact(store, ref["artifact_id"], owner=owner)
    assert result.value == "before-validation"


def test_later_registered_nondefault_owner_row_uses_public_cas_route(tmp_path: Path) -> None:
    registry = f"tests.central.dynamic-row.{uuid4().hex}"
    schema = f"tests.central.dynamic-row-schema.{uuid4().hex}"
    contract_id = f"tests.central.Payload.{uuid4().hex}"
    owner = owner_api.declare_model_owner(
        Payload,
        contract_id=contract_id,
        dto_fqn="tests.central.Payload",
        abi_key="tests.central.Payload@1",
        registry_key=registry,
        kind="tests.central.payload",
        media_type="application/json",
        purpose="test explicitly registered nondefault wire tuple",
        policy_revision="tests.central.r1",
        accepted_wire_policies=(WIRE,),
        payload_version_field="schema_version",
        validate_profile=owner_api.owner_profile_for_spec(CanonSpec(), profile_ref=None),
        representations=(_representation(schema, "1.0", "1.0", current=True, default_write=True),),
    )
    owner_api.register_owner_representations(
        owner,
        (_representation(schema, "1.0", "2.0", current=False, default_write=False),),
    )

    store = _store(tmp_path)
    ref = io._put_owned_json_artifact(
        store,
        {"schema_version": "2.0", "value": "registered-after-owner"},
        owner=owner,
        schema_name=schema,
        schema_version="1.0",
    )
    fresh_owner = owner_api.declare_model_owner(
        Payload,
        contract_id=contract_id,
        dto_fqn="tests.central.Payload",
        abi_key="tests.central.Payload@1",
        registry_key=registry,
        kind="tests.central.payload",
        media_type="application/json",
        purpose="fresh reader for explicitly registered nondefault wire tuple",
        policy_revision="tests.central.r1",
        accepted_wire_policies=(WIRE,),
        payload_version_field="schema_version",
        validate_profile=owner_api.owner_profile_for_spec(CanonSpec(), profile_ref=None),
        representations=(_representation(schema, "1.0", "1.0", current=True, default_write=True),),
    )
    result = io._get_owned_json_artifact(store, ref["artifact_id"], owner=fresh_owner)

    assert result == Payload(schema_version="2.0", value="registered-after-owner")


def test_selected_profile_flag_validator_is_exact_and_precedes_cas() -> None:
    class Store:
        calls = 0

        def put_json(self, payload, opts, canon_spec=None, *, return_selected_profile=False):
            self.calls += 1
            raise AssertionError("invalid flag must be refused before CAS")

    class TruthyFlag:
        def __bool__(self) -> bool:
            return True

    assert io._validate_return_selected_profile_flag(False) is False
    assert io._validate_return_selected_profile_flag(True) is True
    for invalid in (None, 1, TruthyFlag()):
        with pytest.raises(TypeError, match="return_selected_profile must be a bool"):
            io._validate_return_selected_profile_flag(invalid)

    store = Store()
    with pytest.raises(TypeError, match="return_selected_profile must be a bool"):
        io.put_json_artifact(
            store,
            {"value": "payload"},
            kind="tests.central.profile-flag",
            schema_name="tests.central.ProfileFlag",
            schema_version="1.0",
            return_selected_profile=TruthyFlag(),
        )
    assert store.calls == 0
