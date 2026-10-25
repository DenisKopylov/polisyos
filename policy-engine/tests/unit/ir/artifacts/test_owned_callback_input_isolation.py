from __future__ import annotations

import threading
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
from polisyos.ir.model_layer.canon import CanonViolation

WIRE = ("tests.central.callback-isolation-wire", "1")


class Payload(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    schema_version: str
    value: str


class TrackingStore:
    def __init__(self, inner, *, before_put=None) -> None:
        self.inner = inner
        self.before_put = before_put
        self.put_calls = 0

    def __getattr__(self, name: str):
        return getattr(self.inner, name)

    def put_json(self, payload, opts, canon_spec=None, *, return_selected_profile=False):
        self.put_calls += 1
        if self.before_put is not None:
            self.before_put()
        return self.inner.put_json(
            payload,
            opts,
            canon_spec=canon_spec,
            return_selected_profile=return_selected_profile,
        )


def _representation(schema_name: str):
    return owner_api.OwnedJSONRepresentation(
        schema_name=schema_name,
        schema_version="1.0",
        payload_version="1.0",
        wire_policy_ref=WIRE[0],
        wire_policy_revision=WIRE[1],
        profile_ref=None,
        compatibility=base.CompatibilityMode.NONE,
        notes=(),
        readable=True,
        writable=True,
        current=True,
        default_write=True,
        readable_from=(),
    )


def _owner(
    registry: str,
    schema: str,
    *,
    payload_version_of,
    validate_source,
    project_for_consumer,
):
    return contracts.ArtifactOwnerDeclaration(
        contract_id=f"tests.central.Payload.{uuid4().hex}",
        dto_fqn="tests.central.Payload",
        abi_key="tests.central.Payload@1",
        registry_key=registry,
        kind="tests.central.callback-payload",
        media_type="application/json",
        purpose="test callback input isolation",
        policy_revision="tests.central.callback-isolation.r1",
        accepted_wire_policies=(WIRE,),
        payload_version_of=payload_version_of,
        validate_source=validate_source,
        project_for_consumer=project_for_consumer,
        validate_profile=lambda _profile, _registration: True,
    )


def _register(owner, schema: str) -> None:
    base.register_schema_version(
        owner.registry_key,
        "1.0",
        compatibility=base.CompatibilityMode.NONE,
    )
    owner_api.register_owner_representations(
        owner,
        (_representation(schema),),
    )


def _store(tmp_path: Path, *, before_put=None) -> TrackingStore:
    inner = ensure_ir_artifact_store(FileSystemCAS(tmp_path / "cas"))
    return TrackingStore(inner, before_put=before_put)


@pytest.mark.parametrize("mutating_stage", ["payload_version", "validate_source", "project"])
def test_owned_write_refuses_synchronous_callback_input_mutation(
    tmp_path: Path,
    mutating_stage: str,
) -> None:
    registry = f"tests.central.callback-mutation.{mutating_stage}.{uuid4().hex}"
    schema = f"tests.central.callback-schema.{uuid4().hex}"

    def version_of(payload):
        if mutating_stage == "payload_version":
            payload["value"] = "mutated-before-owner-validation"
        return payload.get("schema_version")

    def validate(payload, _admission):
        if mutating_stage == "validate_source":
            parsed = Payload.model_validate(dict(payload))
            payload["value"] = "mutated-after-owner-validation"
            return parsed
        if mutating_stage == "project":
            return payload
        return Payload.model_validate(dict(payload))

    def project(source, _admission):
        if mutating_stage == "project":
            source["value"] = "mutated-by-projection"
        return source

    owner = _owner(
        registry,
        schema,
        payload_version_of=version_of,
        validate_source=validate,
        project_for_consumer=project,
    )
    _register(owner, schema)
    store = _store(tmp_path)

    with pytest.raises(CanonViolation, match="ir_owned_artifact_.*mutated"):
        io._put_owned_json_artifact(
            store,
            {"schema_version": "1.0", "value": "before"},
            owner=owner,
        )
    assert store.put_calls == 0


def test_retained_callback_alias_cannot_change_fresh_persisted_decode(
    tmp_path: Path,
) -> None:
    registry = f"tests.central.callback-retained.{uuid4().hex}"
    schema = f"tests.central.callback-schema.{uuid4().hex}"
    persist_started = threading.Event()
    retained: list[dict[str, object]] = []
    worker: list[threading.Thread] = []

    def version_of(payload):
        return payload.get("schema_version")

    def validate(payload, _admission):
        retained.append(payload)
        thread = threading.Thread(
            target=lambda: (
                persist_started.wait(timeout=2),
                payload.__setitem__("value", "late-alias-mutation"),
            ),
            daemon=True,
        )
        worker.append(thread)
        thread.start()
        return payload

    owner = _owner(
        registry,
        schema,
        payload_version_of=version_of,
        validate_source=validate,
        project_for_consumer=lambda source, _admission: source,
    )
    _register(owner, schema)

    def signal_persist() -> None:
        persist_started.set()
        worker[0].join(timeout=2)

    store = _store(tmp_path, before_put=signal_persist)
    ref = io._put_owned_json_artifact(
        store,
        {"schema_version": "1.0", "value": "original"},
        owner=owner,
    )

    assert worker[0].is_alive() is False
    assert retained[0]["value"] == "late-alias-mutation"
    assert io.get_json_artifact(store, ref["artifact_id"]) == {
        "schema_version": "1.0",
        "value": "original",
    }
