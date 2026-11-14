"""Source-replayed alignment controls for selected method entity vectors."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import numpy as np
import pytest

from polisyos.core.artifacts import CoreJsonReadLimits
from polisyos.core.artifacts.manifest import ArtifactRef, ProducerInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.core.contracts.entity_axis import (
    EntityAxisMemberId,
    SelectedEntityVectorSourceDescriptor,
)
from polisyos.core.contracts.model_input_requirements import (
    ModelInputPhysicalEncoding,
    ModelInputPort,
)
from polisyos.core.contracts.variable_binding import (
    MeasurementBindingProfileRef,
    ModelInputScope,
    VariableRepresentationRef,
    VariableSemanticDefinitionRef,
)
from polisyos.foundry.data_plane.entity_axis import (
    align_entity_values,
    build_selected_source_entity_axis,
)
from polisyos.foundry.data_plane.selected_method_entity_vector import (
    reconcile_selected_method_entity_vector,
)
from polisyos.foundry.data_plane.selected_tensors import (
    encode_selected_tensor,
    selected_tensor_value_sha256,
)


def _limits() -> CoreJsonReadLimits:
    return CoreJsonReadLimits(
        max_manifest_bytes=100_000,
        max_bytes=1_000_000,
        max_depth=32,
        max_elements=10_000,
    )


def _ref(kind: str) -> ArtifactRef:
    return ArtifactRef.model_validate(
        {
            "artifact_id": "sha256:" + "1" * 64,
            "kind": kind,
            "media_type": "application/json",
            "manifest_profile_sha256": "sha256:" + "2" * 64,
        }
    )


def _case(tmp_path: Path, member_ids: list[str | int], values: list[int | float]):
    store = FileSystemCAS(tmp_path / "cas", ownership_enforced=False)
    source_ref = store.put_json(
        {"members": member_ids, "values": values},
        PutOptions(
            kind="tests.selected_entity_vector_source",
            media_type="application/json",
            producer=ProducerInfo(
                component="tests.unit.foundry.data_plane.test_selected_method_entity_vector",
                version="1.0",
            ),
        ),
        canon_spec=CanonSpec(forbid_floats=False, forbid_nan_inf=True, exclude_none=False),
        return_selected_profile=True,
    )
    assert isinstance(source_ref, ArtifactRef)
    axis_result = build_selected_source_entity_axis(
        store=store,
        source_view_ref=source_ref,
        namespace="selected-fixture-view",
        member_values_pointer="/members",
        limits=_limits(),
    )
    port = ModelInputPort(
        port_id="selected-vector",
        slot_id="policy.input.vector",
        carrier="method_input",
        unit_id="index",
        purpose="simulation_input",
        semantic_definition_ref=VariableSemanticDefinitionRef.model_validate(
            _ref("catalog.variable_semantic_definition").model_dump()
        ),
        representation_ref=VariableRepresentationRef.model_validate(
            _ref("catalog.variable_representation").model_dump()
        ),
        binding_profile_ref=MeasurementBindingProfileRef.model_validate(
            _ref("catalog.measurement_binding_profile").model_dump()
        ),
        scope=ModelInputScope(
            population_ref="population:selected-view",
            geography_ref="geography:fixture",
            jurisdiction_ref="jurisdiction:fixture",
            period_start=date(2024, 1, 1),
            period_end=date(2024, 12, 31),
            time_role="observation_time",
        ),
        entity_axis_ref=axis_result.ref,
        physical_encoding=ModelInputPhysicalEncoding(
            shape=(axis_result.axis.cardinality,),
            dtype="float64",
            max_absolute_error=Decimal("0"),
        ),
    )
    source = SelectedEntityVectorSourceDescriptor(
        source_view_ref=source_ref,
        member_ids_pointer="/members",
        values_pointer="/values",
    )
    encoded = encode_selected_tensor(
        values,
        shape=(len(member_ids),),
        dtype="float64",
        max_absolute_error=Decimal("0"),
    )
    aligned = align_entity_values(
        axis=axis_result.axis,
        member_ids=tuple(
            EntityAxisMemberId(kind="string", value=value)
            if type(value) is str
            else EntityAxisMemberId(kind="integer", value=value)
            for value in member_ids
        ),
        values=encoded,
        dtype="float64",
        unit_id=port.unit_id,
    )
    selected_value = aligned.values
    value_digest = selected_tensor_value_sha256(
        selected_value.dtype, selected_value.shape, selected_value.tobytes(order="C")
    )
    return store, port, source, axis_result, aligned, selected_value, value_digest


def _reconcile(case, *, axis_ref=None, selected_value=None, source=None):
    store, port, descriptor, axis, aligned, value, digest = case
    return reconcile_selected_method_entity_vector(
        store,
        port=port,
        binding_port_id=port.port_id,
        binding_slot_id=port.slot_id,
        source=descriptor if source is None else source,
        axis_ref=axis.ref if axis_ref is None else axis_ref,
        expected_alignment=aligned.identity,
        selected_value=value if selected_value is None else selected_value,
        selected_value_sha256=digest,
        limits=_limits(),
    )


def test_selected_method_vector_replays_ids_values_and_fresh_axis(tmp_path: Path) -> None:
    case = _case(tmp_path, ["firm-b", "firm-a"], [20.0, 10.0])

    reconciled = _reconcile(case)

    assert reconciled.identity == case[4].identity
    assert reconciled.values.tolist() == [10.0, 20.0]
    with pytest.raises(ValueError):
        reconciled.values.setflags(write=True)


def test_selected_method_vector_keeps_integer_and_string_ids_distinct(
    tmp_path: Path,
) -> None:
    case = _case(tmp_path, [3, "3"], [30.0, 3.0])

    axis_members = [(member.kind, member.value) for member in case[3].axis.members]
    source_values_by_typed_id = {("integer", 3): 30.0, ("string", "3"): 3.0}
    independent_expected = [source_values_by_typed_id[member] for member in axis_members]

    assert axis_members == [("integer", 3), ("string", "3")]
    assert independent_expected == [30.0, 3.0]
    assert _reconcile(case).values.tolist() == independent_expected


def test_selected_method_vector_rejects_foreign_axis_even_at_same_shape(
    tmp_path: Path,
) -> None:
    case = _case(tmp_path, ["a", "b"], [1.0, 2.0])
    other = _case(tmp_path / "other", ["x", "y"], [1.0, 2.0])

    with pytest.raises(ValueError, match="method_entity_vector_selected_binding_mismatch"):
        _reconcile(case, axis_ref=other[3].ref)


def test_selected_method_vector_rejects_value_graft_and_scalar_broadcast(
    tmp_path: Path,
) -> None:
    case = _case(tmp_path, ["a", "b"], [1.0, 2.0])

    with pytest.raises(ValueError, match="method_entity_vector_argument_alignment_mismatch"):
        _reconcile(case, selected_value=np.asarray([2.0, 1.0], dtype=np.float64))
    with pytest.raises(ValueError, match="method_entity_vector_argument_shape_or_dtype_mismatch"):
        _reconcile(case, selected_value=np.asarray(1.0, dtype=np.float64))


def test_selected_method_vector_requires_axis_member_pointer_and_value_pointer(
    tmp_path: Path,
) -> None:
    case = _case(tmp_path, ["a", "b"], [1.0, 2.0])
    source = SelectedEntityVectorSourceDescriptor(
        source_view_ref=case[2].source_view_ref,
        member_ids_pointer="/members",
        values_pointer="/missing",
    )

    with pytest.raises(ValueError, match="method_entity_vector_pointer_missing"):
        _reconcile(case, source=source)
