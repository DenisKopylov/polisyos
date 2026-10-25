from __future__ import annotations

from collections.abc import Callable, Iterator, MutableMapping
from dataclasses import fields
from datetime import date
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import UUID

import numpy as np
import pytest
from pydantic import BaseModel, ConfigDict, Field

import polisyos.ir.artifacts.io as owned_io
from polisyos.core.artifacts import FileSystemCAS, ensure_ir_artifact_store
from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import (
    ArtifactRef,
    CanonInfo,
    SchemaInfo,
    input_ref_from_artifact_ref,
)
from polisyos.ir.analytics.causal_graph import CausalEdge
from polisyos.ir.analytics.ncm import (
    NCMSpec,
    load_ncm_spec_selected_view,
    persist_ncm_spec_selected_view,
)
from polisyos.ir.artifacts.contracts import ArtifactOwnerDeclaration
from polisyos.ir.model_layer.canon import CanonSpec, CanonViolation
from polisyos.runtime.quality.generation_source import _candidate_simulation_write_options


def _declaration_ref() -> ArtifactRef:
    return ArtifactRef(
        artifact_id=ArtifactID.model_validate("sha256:" + "a" * 64),
        kind="runtime.candidate_model_declaration",
        media_type="application/json",
        manifest_profile_sha256="sha256:" + "b" * 64,
    )


def _options(ref: ArtifactRef) -> object:
    return _candidate_simulation_write_options(
        kind="ir.ncm_spec",
        schema_name="ir.ncm_spec",
        schema_version="1.0",
        job_id="job-owned-write-context",
        run_id="run-owned-write-context",
        tenant_id="tenant-owned-write-context",
        cell_id="cell-owned-write-context",
        source_ref="sha256:" + "c" * 64,
        input_refs=(input_ref_from_artifact_ref(ref, role="candidate_model_declaration"),),
    )


def _mapping(options: object) -> dict[str, object]:
    return {field.name: getattr(options, field.name) for field in fields(options)}


class _SingleSnapshotMapping(MutableMapping[str, object]):
    """Mutate after the returned items snapshot to test coherent admission."""

    def __init__(self, value: dict[str, object]) -> None:
        self.value = value
        self.items_calls = 0

    def __getitem__(self, key: str) -> object:
        return self.value[key]

    def __setitem__(self, key: str, value: object) -> None:
        self.value[key] = value

    def __delitem__(self, key: str) -> None:
        del self.value[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self.value)

    def __len__(self) -> int:
        return len(self.value)

    def items(self) -> Iterator[tuple[str, object]]:
        self.items_calls += 1
        if self.items_calls != 1:
            raise AssertionError("write options Mapping must be snapshotted once")
        captured = tuple(self.value.items())
        self.value["tenant_context"] = {
            "tenant_id": "tenant-mutated-after-snapshot",
            "cell_id": "cell-mutated-after-snapshot",
        }
        return iter(captured)


class _CountingWriter:
    def __init__(self, inner: object) -> None:
        self.inner = inner
        self.put_calls = 0

    def __getattr__(self, name: str) -> object:
        return getattr(self.inner, name)

    def put_bytes(
        self,
        data: bytes,
        opts: object,
        *,
        return_selected_profile: bool = False,
    ) -> object:
        self.put_calls += 1
        return self.inner.put_bytes(
            data,
            opts,
            return_selected_profile=return_selected_profile,
        )


def test_selected_ncm_requires_profile_attestation_before_cas(tmp_path: Path) -> None:
    store = _CountingWriter(ensure_ir_artifact_store(FileSystemCAS(tmp_path / "profileless")))
    with pytest.raises(ValueError, match="ncm_selected_view_profile_attestation_required"):
        persist_ncm_spec_selected_view(
            store,
            NCMSpec(),
            write_options=_options(_declaration_ref()),
            return_selected_profile=False,
        )
    assert store.put_calls == 0


def test_selected_ncm_mapping_is_snapshotted_once_and_round_trips_runtime_context(
    tmp_path: Path,
) -> None:
    declaration_ref = _declaration_ref()
    options = _SingleSnapshotMapping(_mapping(_options(declaration_ref)))
    store = ensure_ir_artifact_store(FileSystemCAS(tmp_path / "cas"))

    selected_ref = persist_ncm_spec_selected_view(
        store,
        NCMSpec(),
        write_options=options,
    )

    assert options.items_calls == 1
    manifest = store.get_manifest(selected_ref)
    assert manifest.tenant_context.tenant_id == "tenant-owned-write-context"
    assert manifest.tenant_context.cell_id == "cell-owned-write-context"
    assert manifest.same_input_closure.job_id == "job-owned-write-context"
    assert manifest.same_input_closure.run_id == "run-owned-write-context"
    assert manifest.same_input_closure.status == "candidate_only"
    assert len(manifest.inputs) == 1
    assert manifest.inputs[0].role == "candidate_model_declaration"
    assert manifest.inputs[0].manifest_profile_sha256 == declaration_ref.manifest_profile_sha256
    loaded = load_ncm_spec_selected_view(
        store,
        selected_ref,
        expected_tenant_id="tenant-owned-write-context",
        expected_cell_id="cell-owned-write-context",
        expected_declaration_ref=declaration_ref,
    )
    assert loaded == NCMSpec()


@pytest.mark.parametrize(
    ("field", "replacement", "error"),
    [
        (
            "kind",
            "ir.unowned_kind",
            "ir_owned_artifact_write_options_reserved_field_mismatch",
        ),
        (
            "schema",
            SchemaInfo(name="ir.ncm_spec", version="9.9"),
            "ir_owned_artifact_write_override_unregistered",
        ),
        (
            "canon",
            CanonInfo.from_spec(CanonSpec(forbid_floats=False)),
            "ir_owned_artifact_write_options_profile_mismatch",
        ),
    ],
)
def test_selected_ncm_reserved_tuple_drift_refuses_before_cas(
    tmp_path: Path,
    field: str,
    replacement: object,
    error: str,
) -> None:
    options = _mapping(_options(_declaration_ref()))
    options[field] = replacement
    store = _CountingWriter(ensure_ir_artifact_store(FileSystemCAS(tmp_path / field)))

    with pytest.raises(CanonViolation, match=error):
        persist_ncm_spec_selected_view(
            store,
            NCMSpec(),
            write_options=options,
        )

    assert store.put_calls == 0


def test_selected_ncm_option_snapshot_rejects_nested_duck_model_dump_before_cas(
    tmp_path: Path,
) -> None:
    class DuckCanon:
        calls = 0

        def model_dump(self, **_kwargs: object) -> dict[str, object]:
            self.calls += 1
            return CanonInfo.from_spec(
                CanonSpec(forbid_floats=False, exclude_none=False)
            ).model_dump(mode="python")

    duck = DuckCanon()
    options = _mapping(_options(_declaration_ref()))
    options["canon"] = duck
    store = _CountingWriter(ensure_ir_artifact_store(FileSystemCAS(tmp_path / "duck")))

    with pytest.raises(CanonViolation, match="ir_owned_artifact_write_options_invalid"):
        persist_ncm_spec_selected_view(
            store,
            NCMSpec(),
            write_options=options,
        )

    assert duck.calls == 0
    assert store.put_calls == 0


def test_selected_ncm_reconciles_store_manifest_against_frozen_context(
    tmp_path: Path,
) -> None:
    inner = ensure_ir_artifact_store(FileSystemCAS(tmp_path / "mutating-store"))

    class MutatingWriter:
        def __getattr__(self, name: str) -> object:
            return getattr(inner, name)

        def put_bytes(
            self,
            data: bytes,
            opts: object,
            *,
            return_selected_profile: bool = False,
        ) -> object:
            opts.tenant_context["tenant_id"] = "tenant-mutated-by-store-callback"
            return inner.put_bytes(
                data,
                opts,
                return_selected_profile=return_selected_profile,
            )

    with pytest.raises(
        CanonViolation,
        match="ir_owned_artifact_selected_manifest_options_mismatch",
    ):
        persist_ncm_spec_selected_view(
            MutatingWriter(),
            NCMSpec(),
            write_options=_options(_declaration_ref()),
        )


def _projection_owner(
    project: Callable[[Any, Any], Any],
) -> ArtifactOwnerDeclaration[Any, Any]:
    return ArtifactOwnerDeclaration(
        contract_id="tests.owner-projection.Payload",
        dto_fqn="tests.owner-projection.Payload",
        abi_key="tests.owner-projection.Payload@1",
        registry_key="tests.owner-projection.registry",
        kind="tests.owner-projection.payload",
        media_type="application/json",
        purpose="test structural source mutation refusal",
        policy_revision="tests.owner-projection.r1",
        accepted_wire_policies=(("tests.owner-projection.wire", "1"),),
        payload_version_of=lambda _payload: None,
        validate_source=lambda payload, _admission: payload,
        project_for_consumer=project,
        validate_profile=lambda _profile, _registration: True,
    )


def test_owned_projection_accepts_unchanged_numpy_source_without_equality() -> None:
    class ArrayPayload(BaseModel):
        model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

        cluster_id: np.ndarray

        def __eq__(self, _other: object) -> bool:
            raise AssertionError("projection must not invoke DTO equality")

    source = ArrayPayload(cluster_id=np.asarray([0, 0, 1, 1], dtype=np.int64))
    owner = _projection_owner(lambda callback_source, _admission: callback_source)

    projected = owned_io._project_owner_source(owner, source, object())

    assert projected is not source
    np.testing.assert_array_equal(projected.cluster_id, np.asarray([0, 0, 1, 1]))


@pytest.mark.parametrize("mutated_field", ["cluster_id", "hidden_value"])
def test_owned_projection_rejects_mutation_even_when_dto_equality_lies(
    mutated_field: str,
) -> None:
    class EqualityLaunderingPayload(BaseModel):
        model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

        cluster_id: np.ndarray
        hidden_value: str = Field(exclude=True)

        def __eq__(self, _other: object) -> bool:
            return True

    def mutate(source: EqualityLaunderingPayload, _admission: object) -> EqualityLaunderingPayload:
        if mutated_field == "cluster_id":
            source.cluster_id[0] = 9
        else:
            source.hidden_value = "mutated-but-excluded"
        return source

    source = EqualityLaunderingPayload(
        cluster_id=np.asarray([0, 0, 1, 1], dtype=np.int64),
        hidden_value="before",
    )
    owner = _projection_owner(mutate)

    with pytest.raises(
        CanonViolation,
        match="ir_owned_artifact_projection_input_mutated",
    ):
        owned_io._project_owner_source(owner, source, object())

    assert source.hidden_value == "before"
    np.testing.assert_array_equal(source.cluster_id, np.asarray([0, 0, 1, 1]))


def test_owned_projection_snapshots_frozen_graph_container_subclasses() -> None:
    edge = CausalEdge(
        src="policy.input",
        dst="policy.outcome",
        metadata={"nested": [{"status": "source"}]},
    )
    owner = _projection_owner(lambda callback_source, _admission: callback_source)

    projected = owned_io._project_owner_source(owner, edge, object())

    assert projected.metadata["nested"][0]["status"] == "source"

    def mutate_frozen_nested_value(
        callback_source: CausalEdge,
        _admission: object,
    ) -> CausalEdge:
        nested = dict.__getitem__(callback_source.metadata, "nested")
        list.__setitem__(nested, 0, {"status": "mutated"})
        return callback_source

    with pytest.raises(
        CanonViolation,
        match="ir_owned_artifact_projection_input_mutated",
    ):
        owned_io._project_owner_source(
            _projection_owner(mutate_frozen_nested_value),
            edge,
            object(),
        )

    assert edge.metadata["nested"][0]["status"] == "source"


def test_owned_projection_fails_closed_on_unsupported_source_value() -> None:
    class OpaqueValue:
        pass

    class OpaquePayload(BaseModel):
        model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

        value: OpaqueValue

    calls = 0

    def project(source: OpaquePayload, _admission: object) -> OpaquePayload:
        nonlocal calls
        calls += 1
        return source

    with pytest.raises(CanonViolation, match="ir_owned_artifact_projection_refused"):
        owned_io._project_owner_source(
            _projection_owner(project),
            OpaquePayload(value=OpaqueValue()),
            object(),
        )

    assert calls == 0


def test_selected_writer_without_neutral_options_preparer_refuses_before_cas(
    tmp_path: Path,
) -> None:
    inner = ensure_ir_artifact_store(FileSystemCAS(tmp_path / "missing-preparer"))

    class LegacySelectedWriter:
        def __init__(self) -> None:
            self.put_calls = 0

        def __getattr__(self, name: str) -> object:
            if name == "prepare_owned_write_options":
                raise AttributeError(name)
            return getattr(inner, name)

        def put_bytes(
            self,
            data: bytes,
            opts: object,
            *,
            return_selected_profile: bool = False,
        ) -> object:
            self.put_calls += 1
            return inner.put_bytes(
                data,
                opts,
                return_selected_profile=return_selected_profile,
            )

    store = LegacySelectedWriter()
    with pytest.raises(
        CanonViolation,
        match="ir_owned_artifact_write_options_preparer_unavailable",
    ):
        persist_ncm_spec_selected_view(
            store,
            NCMSpec(),
            write_options=_options(_declaration_ref()),
        )

    assert store.put_calls == 0


class _TypedMappingKey(Enum):
    HORIZON = "horizon"


def _typed_mapping_for_projection() -> dict[Any, Any]:
    return {
        1: "integer-key",
        "1": "string-key",
        (2, "horizon"): {"context": {"context_value": "source"}},
        _TypedMappingKey.HORIZON: "enum-key",
        Decimal("1.25"): "decimal-key",
        date(2024, 1, 2): "date-key",
        UUID("12345678-1234-5678-1234-567812345678"): "uuid-key",
    }


def test_owned_mapping_snapshot_preserves_typed_keys_and_ignores_insertion_order() -> None:
    mapping = _typed_mapping_for_projection()
    reversed_mapping = dict(reversed(tuple(mapping.items())))

    assert owned_io._owner_source_semantic_bytes(mapping) == owned_io._owner_source_semantic_bytes(
        reversed_mapping
    )
    assert owned_io._owner_source_semantic_bytes(
        {1: "same"}
    ) != owned_io._owner_source_semantic_bytes({"1": "same"})


def test_owned_projection_accepts_unchanged_typed_mapping_source() -> None:
    class TypedMappingPayload(BaseModel):
        model_config = ConfigDict(extra="forbid")

        values: dict[Any, Any]

    source = TypedMappingPayload(values=_typed_mapping_for_projection())
    projected = owned_io._project_owner_source(
        _projection_owner(lambda callback_source, _admission: callback_source),
        source,
        object(),
    )

    assert projected is not source
    assert owned_io._owner_source_semantic_bytes(
        projected.values
    ) == owned_io._owner_source_semantic_bytes(source.values)


@pytest.mark.parametrize("mutation", ["rekey", "hidden_value"])
def test_owned_projection_rejects_typed_mapping_key_and_hidden_value_mutation(
    mutation: str,
) -> None:
    class TypedMappingPayload(BaseModel):
        model_config = ConfigDict(extra="forbid")

        values: dict[Any, Any]

    def mutate(source: TypedMappingPayload, _admission: object) -> TypedMappingPayload:
        if mutation == "rekey":
            source.values["1"] = source.values.pop(1)
        else:
            source.values[(2, "horizon")]["context"]["context_value"] = "mutated"
        return source

    source = TypedMappingPayload(values=_typed_mapping_for_projection())
    with pytest.raises(CanonViolation, match="ir_owned_artifact_projection_input_mutated"):
        owned_io._project_owner_source(_projection_owner(mutate), source, object())

    assert source.values[1] == "integer-key"
    assert source.values["1"] == "string-key"
    assert source.values[(2, "horizon")]["context"]["context_value"] == "source"


def test_owned_projection_fails_closed_on_unsupported_mapping_key_before_callback() -> None:
    class OpaqueKey:
        pass

    class OpaqueKeyPayload(BaseModel):
        model_config = ConfigDict(arbitrary_types_allowed=True)

        values: dict[Any, Any]

    calls = 0

    def project(source: OpaqueKeyPayload, _admission: object) -> OpaqueKeyPayload:
        nonlocal calls
        calls += 1
        return source

    source = OpaqueKeyPayload(values={OpaqueKey(): "value"})
    with pytest.raises(CanonViolation, match="ir_owned_artifact_projection_refused"):
        owned_io._project_owner_source(_projection_owner(project), source, object())

    assert calls == 0
