from __future__ import annotations

# ruff: noqa: S101
from importlib import import_module
from typing import TYPE_CHECKING
from uuid import uuid4

if TYPE_CHECKING:
    from pathlib import Path

    from polisyos.ir.artifacts import ArtifactStore
    from polisyos.ir.artifacts.contracts import ArtifactOwnerDeclaration

import pytest
from pydantic import BaseModel, ConfigDict

from polisyos.core.artifacts import FileSystemCAS
from polisyos.core.artifacts.ir_adapter import ensure_ir_artifact_store
from polisyos.ir.analytics._owner_admission import (
    OwnedJSONRepresentation,
    declare_model_owner,
    owner_profile_for_spec,
)
from polisyos.ir.artifacts.io import (
    _get_owned_json_artifact,
    _put_owned_json_artifact,
)
from polisyos.ir.migrations.base import (
    CompatibilityMode,
    get_schema_rule,
)
from polisyos.ir.model_layer.canon import CanonSpec, CanonViolation

WIRE_POLICY = ("tests.ir.analytics.owner-admission-wire", "1")


class StrictPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    schema_version: str
    resource_id: str
    value: str


class CountingStore:
    def __init__(self, store: ArtifactStore) -> None:
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


def _representation(
    *,
    schema_name: str,
    registry_version: str,
    payload_version: str,
    compatibility: CompatibilityMode = CompatibilityMode.NONE,
    notes: tuple[str, ...] = (),
) -> OwnedJSONRepresentation:
    return OwnedJSONRepresentation(
        schema_name=schema_name,
        schema_version=registry_version,
        payload_version=payload_version,
        wire_policy_ref=WIRE_POLICY[0],
        wire_policy_revision=WIRE_POLICY[1],
        profile_ref=None,
        compatibility=compatibility,
        notes=notes,
        readable=True,
        writable=True,
        current=True,
        default_write=True,
        readable_from=(),
    )


def _owner(
    registry_key: str,
    contract_id: str,
    *,
    schema_name: str,
    compatibility: CompatibilityMode = CompatibilityMode.NONE,
    notes: tuple[str, ...] = (),
    spec: CanonSpec | None = None,
) -> ArtifactOwnerDeclaration[StrictPayload, StrictPayload]:
    selected_spec = CanonSpec() if spec is None else spec
    return declare_model_owner(
        StrictPayload,
        contract_id=contract_id,
        dto_fqn="tests.unit.ir.analytics.StrictPayload",
        abi_key="tests.unit.ir.analytics.StrictPayload@1",
        registry_key=registry_key,
        kind="tests.ir.analytics.strict_payload",
        media_type="application/json",
        purpose="test exact analytics owner admission",
        policy_revision="test-owner-policy-r1",
        accepted_wire_policies=(WIRE_POLICY,),
        payload_version_field="schema_version",
        validate_profile=owner_profile_for_spec(selected_spec, profile_ref=None),
        representations=(
            _representation(
                schema_name=schema_name,
                registry_version="1.0",
                payload_version="1.0",
                compatibility=compatibility,
                notes=notes,
            ),
        ),
    )


def _store(tmp_path: Path) -> ArtifactStore:
    return ensure_ir_artifact_store(FileSystemCAS(tmp_path / "cas"))


def test_owner_helper_persists_then_reads_with_a_fresh_typed_declaration(
    tmp_path: Path,
) -> None:
    registry_key = f"test.analytics.owner.{uuid4().hex}"
    contract_id = f"tests.unit.ir.analytics.StrictPayload.{uuid4().hex}"
    schema_name = f"test.unseen_policy_resource.{uuid4().hex}"
    store = _store(tmp_path)

    writer = _owner(registry_key, contract_id, schema_name=schema_name)
    ref = _put_owned_json_artifact(
        store,
        {
            "schema_version": "1.0",
            "resource_id": "new-resource-grammar-member",
            "value": "producer-to-CAS",
        },
        owner=writer,
    )

    fresh_reader = _owner(registry_key, contract_id, schema_name=schema_name)
    result = _get_owned_json_artifact(store, ref["artifact_id"], owner=fresh_reader)

    assert isinstance(result, StrictPayload)
    assert result.resource_id == "new-resource-grammar-member"
    assert result.value == "producer-to-CAS"


def test_wrong_profile_and_model_construct_source_fail_before_payload_or_cas(
    tmp_path: Path,
) -> None:
    registry_key = f"test.analytics.owner.{uuid4().hex}"
    contract_id = f"tests.unit.ir.analytics.StrictPayload.{uuid4().hex}"
    schema_name = f"test.unseen_policy_resource.{uuid4().hex}"
    store = _store(tmp_path)
    owner = _owner(registry_key, contract_id, schema_name=schema_name)
    ref = _put_owned_json_artifact(
        store,
        {"schema_version": "1.0", "resource_id": "candidate", "value": "safe"},
        owner=owner,
    )

    counted_read = CountingStore(store)
    wrong_profile_owner = _owner(
        registry_key,
        contract_id,
        schema_name=schema_name,
        spec=CanonSpec(forbid_floats=False),
    )
    with pytest.raises(CanonViolation, match="ir_owned_artifact_profile_refused"):
        _get_owned_json_artifact(
            counted_read,
            ref["artifact_id"],
            owner=wrong_profile_owner,
        )
    assert counted_read.manifest_reads == 1
    assert counted_read.payload_reads == 0

    counted_write = CountingStore(store)
    malformed_constructed = StrictPayload.model_construct(
        schema_version="1.0",
        resource_id="candidate",
    )
    with pytest.raises(CanonViolation, match="ir_owned_artifact_payload_version_invalid"):
        _put_owned_json_artifact(counted_write, malformed_constructed, owner=owner)
    assert counted_write.put_calls == 0


def test_existing_full_compatibility_rule_is_reused_only_when_declared_exactly() -> None:
    import_module("polisyos.ir.migrations.schema_registry")

    registry_key = "literature_causal_prior"
    schema_name = "literature_causal_prior"
    existing = get_schema_rule(registry_key, "1.0")
    assert existing is not None
    assert existing.mode is CompatibilityMode.FULL
    contract_id = f"tests.unit.ir.analytics.StrictPayload.{uuid4().hex}"

    owner = _owner(
        registry_key,
        contract_id,
        schema_name=schema_name,
        compatibility=CompatibilityMode.FULL,
        notes=("Literature causal prior 1.0 has no declared schema successors yet.",),
    )
    with pytest.raises(ValueError, match="analytics representation conflicts"):
        _owner(
            registry_key,
            f"{contract_id}.wrong-law",
            schema_name=schema_name,
        )

    assert owner.contract_id == contract_id
    current = get_schema_rule(registry_key, "1.0")
    assert current is not None
    assert current.mode is existing.mode
    assert current.notes == existing.notes
    assert current.readable_versions == existing.readable_versions
    assert current.writable_versions == existing.writable_versions
