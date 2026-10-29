"""Real CAS publication boundaries; statuses alone cannot establish no writes."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any, ClassVar, Literal

import pytest
from pydantic import BaseModel, ConfigDict

from polisyos.common.canonical_profile import CanonicalProfileRefusalError
from polisyos.core.artifacts import PutOptions
from polisyos.core.artifacts._manifest_lifecycle import ManifestLifecycle
from polisyos.core.artifacts.owned_json import (
    declare_core_json_writer_policy,
    put_core_json_artifact_bounded,
    validate_owned_core_model_json_artifact,
)
from polisyos.core.artifacts.signing import SigningConfig
from polisyos.core.canon import CanonicalResourceLimits, CanonViolation
from polisyos.core.contracts.foundry import MethodArtifactOutputPayload
from polisyos.foundry.execute import read_method_artifact_output_bounded
from polisyos.foundry.execute._internal.graph import _method_artifact_output_writer_policy
from tests._helpers.method_artifact_writer import (
    capture_fixture,
    cas_content,
    local_store,
    produce,
    selected_ref,
)


def test_unbound_policy_refused_before_payload_walk(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("POLISYOS_HPC_OBSERVABILITY_ENABLED", "false")
    store = local_store(tmp_path / "cas")
    before = cas_content(tmp_path / "cas")
    with pytest.raises(CanonicalProfileRefusalError):
        put_core_json_artifact_bounded(store, object(), policy=object(), inputs=())
    assert cas_content(tmp_path / "cas") == before


@pytest.mark.parametrize(("size", "expected"), [(4096, "captured"), (4097, "unavailable")])
def test_actual_manifest_cap_precedes_durable_publication(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, size: int, expected: str
) -> None:
    monkeypatch.setenv("POLISYOS_HPC_OBSERVABILITY_ENABLED", "false")
    store = local_store(tmp_path / "cas")
    capture, occurrence = capture_fixture(store)
    before = cas_content(tmp_path / "cas")
    original = ManifestLifecycle.to_bytes

    def padded(manifest: Any) -> bytes:
        raw = original(manifest)
        assert len(raw) < size
        return raw + b" " * (size - len(raw))

    monkeypatch.setattr(ManifestLifecycle, "to_bytes", staticmethod(padded))
    rows = produce(store, capture, occurrence, {"sidecar": {"value": 1}})
    assert rows[0][0].status == expected
    if expected == "unavailable":
        assert cas_content(tmp_path / "cas") == before
        assert capture.sidecar_refs_used == 0
    else:
        ref = selected_ref(rows)
        assert len(store.get_manifest_bytes(ref)) == 4096
        assert read_method_artifact_output_bounded(store, ref, max_bytes=65536).value[
            "payload"
        ] == {"value": 1}


def test_signing_backend_is_unqualified_without_callback_or_publication(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("POLISYOS_HPC_OBSERVABILITY_ENABLED", "false")
    store = local_store(tmp_path / "cas")
    capture, occurrence = capture_fixture(store)
    store._signing_config = SigningConfig(enabled=True)
    before = cas_content(tmp_path / "cas")
    rows = produce(store, capture, occurrence, {"sidecar": {"value": 1}})
    assert rows[0][0].status == "unavailable"
    assert cas_content(tmp_path / "cas") == before


def test_policy_mutation_refuses_instead_of_reappointing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("POLISYOS_HPC_OBSERVABILITY_ENABLED", "false")
    store = local_store(tmp_path / "cas")
    capture, occurrence = capture_fixture(store)
    policy = _method_artifact_output_writer_policy()
    before = cas_content(tmp_path / "cas")
    original = policy.limits.max_wire_bytes
    try:
        object.__setattr__(policy.limits, "max_wire_bytes", original + 1)
        rows = produce(store, capture, occurrence, {"sidecar": {"value": 1}})
        assert rows[0][0].status == "unavailable"
        assert cas_content(tmp_path / "cas") == before
    finally:
        object.__setattr__(policy.limits, "max_wire_bytes", original)


def test_same_id_selected_wrong_owner_or_profile_rejected_before_payload(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("POLISYOS_HPC_OBSERVABILITY_ENABLED", "false")
    store = local_store(tmp_path / "cas")
    capture, occurrence = capture_fixture(store)
    ref = selected_ref(
        produce(store, capture, occurrence, {"sidecar": {"_type": "decimal", "value": "2"}})
    )
    manifest = store.get_manifest(ref)
    raw = store.get_bytes(ref)
    selected = store.put_bytes(
        raw,
        PutOptions(
            kind="other.owner",
            media_type=manifest.media_type,
            schema=manifest.artifact_schema,
            canon=manifest.canon,
            inputs=manifest.inputs,
            producer=manifest.producer,
        ),
        return_selected_profile=True,
    )
    assert selected.artifact_id == ref.artifact_id

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        pytest.fail("payload opened before owner refusal")

    # Use the real bounded source port; only its payload-opening method is observed.
    monkeypatch.setattr(store, "open_member_bounded", forbidden)
    with pytest.raises(CanonicalProfileRefusalError):
        read_method_artifact_output_bounded(store, selected, max_bytes=65536)


def test_existing_overcap_default_manifest_refuses_before_new_publication(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("POLISYOS_HPC_OBSERVABILITY_ENABLED", "false")
    store = local_store(tmp_path / "cas")
    capture, occurrence = capture_fixture(store)
    raw = {"sidecar": {"answer": 3}}
    ref = selected_ref(produce(store, capture, occurrence, raw))
    path = store._manifest_path_for_ref(ref.artifact_id, None)
    path.write_bytes(path.read_bytes() + b" " * 4096)
    before = cas_content(tmp_path / "cas")
    rows = produce(store, capture, occurrence, raw)
    assert rows[0][0].status == "unavailable"
    assert cas_content(tmp_path / "cas") == before


def test_custom_ownership_callbacks_never_run_for_unqualified_backend(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("POLISYOS_HPC_OBSERVABILITY_ENABLED", "false")
    store = local_store(tmp_path / "cas")
    capture, occurrence = capture_fixture(store)

    class CallbackOwner:
        @property
        def _coordinator(self) -> Any:
            pytest.fail("custom owner callback before refusal")

    store._ownership_index = CallbackOwner()
    before = cas_content(tmp_path / "cas")
    rows = produce(store, capture, occurrence, {"sidecar": {"value": 1}})
    assert rows[0][0].status == "unavailable"
    assert cas_content(tmp_path / "cas") == before


@pytest.mark.parametrize(
    "method",
    ["_put_bounded_core_json_write", "_put_blob_and_manifest_once", "_prepare_sign_on_put"],
)
def test_stock_backend_method_shadows_refuse_before_callback_or_effect(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, method: str
) -> None:
    monkeypatch.setenv("POLISYOS_HPC_OBSERVABILITY_ENABLED", "false")
    store = local_store(tmp_path / "cas")
    capture, occurrence = capture_fixture(store)
    before = cas_content(tmp_path / "cas")

    def substituted(*args: Any, **kwargs: Any) -> Any:
        pytest.fail("instance method shadow entered before refusal")

    monkeypatch.setattr(store, method, substituted)
    rows = produce(store, capture, occurrence, {"sidecar": {"answer": 1}})
    assert rows[0][0].status == "unavailable"
    assert cas_content(tmp_path / "cas") == before


def _declare_like_source(model: type[BaseModel], **changes: Any) -> Any:
    base = _method_artifact_output_writer_policy()
    values = {
        "owner": base.owner,
        "model": model,
        "spec": base.spec,
        "producer_component": base.producer_component,
        "limits": base.limits,
        "read_limits": base.read_limits,
        "input_contracts": base.input_contracts,
        "value_limits": base.value_limits,
    }
    values.update(changes)
    return declare_core_json_writer_policy(**values)


@pytest.mark.parametrize("hook", ["post_init", "custom_init"])
def test_nested_models_are_outside_primitive_writer_domain_before_callbacks(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    hook: str,
) -> None:
    monkeypatch.setenv("POLISYOS_HPC_OBSERVABILITY_ENABLED", "false")
    events = []

    class PostChild(BaseModel):
        model_config = ConfigDict(extra="forbid")
        value: int

        def model_post_init(self, context: Any) -> None:
            events.append("post_init")

    class InitChild(BaseModel):
        model_config = ConfigDict(extra="forbid")
        value: int

        def __init__(self, **data: Any) -> None:
            events.append("custom_init")
            super().__init__(**data)

    child = PostChild if hook == "post_init" else InitChild

    class UnqualifiedNestedDTO(BaseModel):
        model_config = ConfigDict(extra="forbid", frozen=True)
        ARTIFACT_KIND: ClassVar[str] = MethodArtifactOutputPayload.ARTIFACT_KIND
        ARTIFACT_MEDIA_TYPE: ClassVar[str] = MethodArtifactOutputPayload.ARTIFACT_MEDIA_TYPE
        ARTIFACT_SCHEMA_NAME: ClassVar[str] = MethodArtifactOutputPayload.ARTIFACT_SCHEMA_NAME
        ARTIFACT_SCHEMA_VERSION: ClassVar[str] = MethodArtifactOutputPayload.ARTIFACT_SCHEMA_VERSION
        schema_version: Literal["1.0"] = "1.0"
        payload: dict[str, Any]
        child_value: child

    # Local annotations are explicitly resolved; no child instance is constructed.
    UnqualifiedNestedDTO.model_rebuild(_types_namespace={"child": child})
    store = local_store(tmp_path / "cas")
    capture, _occurrence = capture_fixture(store)
    before = cas_content(tmp_path / "cas")
    refusal = None
    try:
        policy = _declare_like_source(UnqualifiedNestedDTO)
        put_core_json_artifact_bounded(
            store,
            {"schema_version": "1.0", "payload": {}, "child_value": {"value": 1}},
            policy=policy,
            inputs=(
                capture.program_graph_ref,
                capture.exec_plan_ref,
                capture.method_metric_binding_set_ref,
            ),
        )
    except CanonicalProfileRefusalError as error:
        refusal = error
    assert events == []
    assert refusal is not None and refusal.code == "core_json_writer_model_domain_unqualified"
    assert cas_content(tmp_path / "cas") == before


@pytest.mark.parametrize(
    "label", ["producer_component", "policy_id", "input_role", "profile_integer"]
)
def test_unbounded_policy_metadata_refuses_before_manifest_materializer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    label: str,
) -> None:
    monkeypatch.setenv("POLISYOS_HPC_OBSERVABILITY_ENABLED", "false")
    store = local_store(tmp_path / "cas")
    capture, occurrence = capture_fixture(store)
    base = _method_artifact_output_writer_policy()
    before = cas_content(tmp_path / "cas")
    materializer_events = []
    original = ManifestLifecycle.to_bytes

    def observed(manifest: Any) -> bytes:
        materializer_events.append(True)
        return original(manifest)

    monkeypatch.setattr(ManifestLifecycle, "to_bytes", staticmethod(observed))
    large = "x" * 1_000_000
    changes: dict[str, Any] = {}
    if label == "producer_component":
        changes["producer_component"] = large
    elif label == "policy_id":
        changes["limits"] = CanonicalResourceLimits(
            large, base.limits.max_wire_bytes, base.limits.max_wire_depth, base.limits.max_elements
        )
    elif label == "input_role":
        changes["input_contracts"] = (
            (large, *base.input_contracts[0][1:]),
            *base.input_contracts[1:],
        )
    else:
        changes["spec"] = replace(base.spec, max_depth=1 << 1_000_000)
    with pytest.raises((CanonicalProfileRefusalError, CanonViolation, TypeError)) as error:
        policy = _declare_like_source(MethodArtifactOutputPayload, **changes)
        put_core_json_artifact_bounded(
            store,
            {
                "schema_version": "1.0",
                "occurrence_id": occurrence.occurrence_id,
                "invocation_id": occurrence.invocation_id,
                "node_id": occurrence.node_id,
                "artifact_key": "sidecar",
                "payload": {},
            },
            policy=policy,
            inputs=(
                capture.program_graph_ref,
                capture.exec_plan_ref,
                capture.method_metric_binding_set_ref,
            ),
        )
    assert materializer_events == []
    assert type(error.value) is CanonViolation
    assert error.value.args == ("canonical_wire_bytes_exceeded",)
    assert cas_content(tmp_path / "cas") == before


def test_legacy_owned_reader_keeps_compatible_metaclass_subclass(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("POLISYOS_HPC_OBSERVABILITY_ENABLED", "false")

    class CompatibleMeta(type(BaseModel)):
        pass

    class LegacyCompatible(MethodArtifactOutputPayload, metaclass=CompatibleMeta):
        pass

    store = local_store(tmp_path / "cas")
    capture, occurrence = capture_fixture(store, "legacy")
    ref = selected_ref(produce(store, capture, occurrence, {"sidecar": {"answer": 2}}))
    read = validate_owned_core_model_json_artifact(
        LegacyCompatible,
        store,
        ref,
        expected_owner=_method_artifact_output_writer_policy().owner,
    )
    assert read.value.payload == {"answer": 2}
    with pytest.raises(CanonicalProfileRefusalError):
        _declare_like_source(LegacyCompatible)
