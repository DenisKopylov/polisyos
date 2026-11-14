"""Wire and boundary checks for explicitly selected method input contracts."""

from datetime import date
from decimal import Decimal
from hashlib import sha256

import pytest

from polisyos.core.artifacts import ArtifactRef
from polisyos.core.canon import CanonSpec, to_canonical_bytes
from polisyos.core.contracts.entity_axis import (
    EntityAxisValueIdentity,
    SelectedEntityVectorSourceDescriptor,
)
from polisyos.core.contracts.execution_plan import ExecutionPlan, MethodDagNode
from polisyos.core.contracts.foundry import (
    FoundryInputBindingRule,
    FoundryInputBindings,
    FoundrySelectedMethodInput,
    FoundrySelectedMethodInputAtStep,
    FoundrySelectedMethodVectorInput,
    ProgramNode,
    StateSnapshotRef,
)
from polisyos.core.contracts.model_input_period_steps import ModelInputStepScope
from polisyos.core.contracts.model_input_requirements import (
    ModelInputPhysicalEncoding,
    ModelInputPort,
    ModelInputPortDeclaration,
    ProgramGraphInputDependency,
)
from polisyos.core.contracts.semantic_input_binding import ResolvedInputBindingManifestRef
from polisyos.core.contracts.variable_binding import (
    MeasurementBindingProfileRef,
    ModelInputScope,
    VariableRepresentationRef,
    VariableSemanticDefinitionRef,
)


def _ref(kind: str, media_type: str = "application/json") -> ArtifactRef:
    return ArtifactRef.model_validate(
        {
            "artifact_id": "sha256:" + "1" * 64,
            "kind": kind,
            "media_type": media_type,
            "manifest_profile_sha256": "sha256:" + "2" * 64,
        }
    )


def test_state_writes_are_versioned_and_legacy_fields_stay_absent() -> None:
    legacy = MethodDagNode(node_id="n", method_fqn="test.method@1", reads_slots=["a"])
    assert "state_writes" not in legacy.model_dump(mode="json")
    assert ExecutionPlan(plan_id="p", method_dag=[legacy]).schema_version == "1.0"
    explicit = MethodDagNode(node_id="n", method_fqn="test.method@1", state_writes=[])
    with pytest.raises(ValueError):
        ExecutionPlan(plan_id="p", method_dag=[explicit])
    assert ExecutionPlan(plan_id="p", schema_version="1.1", method_dag=[explicit]).method_dag == [
        explicit
    ]
    node = ProgramNode(node_id="n", node_kind="method", method_fqn="test.method@1", inputs=["a"])
    assert "input_ports" not in node.model_dump(mode="json")
    with pytest.raises(ValueError):
        MethodDagNode(node_id="n", method_fqn="test.method@1", state_writes=["a", "a"])


def test_selected_method_input_rejects_wrong_profile_and_nonfinite_values() -> None:
    values = {
        "model_input_obligation_ref": _ref("runtime.quality.model_input_obligation"),
        "binding_id": "binding",
        "port_id": "port",
        "slot_id": "slot",
        "canonical_value": Decimal("-6000000000"),
        "dtype": "float32",
        "shape": (),
        "npy_value_ref": _ref("foundry.selected_method_input_value", "application/x-npy"),
        "value_sha256": "a" * 64,
    }
    assert FoundrySelectedMethodInput(**values).canonical_value == Decimal("-6000000000")
    for field, bad in (
        ("canonical_value", Decimal("NaN")),
        ("canonical_value", 1.0),
        ("value_sha256", "a" * 63),
        ("npy_value_ref", _ref("wrong", "application/json")),
        ("shape", (0,)),
    ):
        with pytest.raises(ValueError):
            FoundrySelectedMethodInput(**(values | {field: bad}))


def test_method_carrier_and_dependency_require_the_versioned_contract() -> None:
    common = {
        "port_id": "flow",
        "slot_id": "flow",
        "unit_id": "usd",
        "purpose": "simulation_input",
        "semantic_definition_ref": VariableSemanticDefinitionRef.model_validate(
            _ref("catalog.variable_semantic_definition").model_dump()
        ),
        "representation_ref": VariableRepresentationRef.model_validate(
            _ref("catalog.variable_representation").model_dump()
        ),
        "binding_profile_ref": MeasurementBindingProfileRef.model_validate(
            _ref("catalog.measurement_binding_profile").model_dump()
        ),
        "scope": ModelInputScope(
            population_ref="population:test",
            geography_ref="geography:test",
            jurisdiction_ref="jurisdiction:test",
            period_start=date(2024, 1, 1),
            period_end=date(2024, 12, 31),
            time_role="observation_time",
        ),
        "physical_encoding": ModelInputPhysicalEncoding(
            shape=(), dtype="float32", max_absolute_error=Decimal(0)
        ),
    }
    legacy = ModelInputPort(**common, state_path="gdp")
    assert "carrier" not in legacy.model_dump(mode="json")
    method = ModelInputPort(**common, carrier="method_input")
    assert "state_path" not in method.model_dump(mode="json")
    with pytest.raises(ValueError):
        ModelInputPortDeclaration(ports=(method,))
    assert ModelInputPortDeclaration(schema_version="1.1", ports=(method,)).ports == (method,)
    with pytest.raises(ValueError):
        ModelInputPort(**common, carrier="method_input", state_path="gdp")
    with pytest.raises(ValueError):
        ProgramGraphInputDependency(node_id="n", kind="method_read", first_required_step=0)
    assert (
        ProgramGraphInputDependency(
            node_id="n", kind="method_read", first_required_step=0, method_abi_digest="a" * 64
        ).kind
        == "method_read"
    )
    with pytest.raises(ValueError):
        ProgramGraphInputDependency(
            node_id="n", kind="mechanism_read", first_required_step=0, method_abi_digest="a" * 64
        )


def test_method_input_binding_version_matrix() -> None:
    selected = FoundrySelectedMethodInput(
        model_input_obligation_ref=_ref("runtime.quality.model_input_obligation"),
        binding_id="binding",
        port_id="port",
        slot_id="slot",
        canonical_value=Decimal(1),
        dtype="float32",
        shape=(),
        npy_value_ref=_ref("foundry.selected_method_input_value", "application/x-npy"),
        value_sha256="a" * 64,
    )
    fields = {
        "data_snapshot_ref": _ref("fabric.data_snapshot"),
        "registry_bundle_ref": _ref("core.registry_bundle"),
        "bound_state_snapshot_ref": StateSnapshotRef.model_validate(
            _ref("foundry.state_snapshot").model_dump()
        ),
    }
    legacy = FoundryInputBindings(**fields)
    assert "selected_method_inputs" not in legacy.model_dump(mode="json")
    manifest_ref = ResolvedInputBindingManifestRef.model_validate(
        _ref("foundry.resolved_input_binding_manifest").model_dump()
    )
    binding = FoundryInputBindings(
        **fields,
        schema_version="1.4",
        resolved_binding_manifest_ref=manifest_ref,
        selected_method_inputs=(selected,),
    )
    assert binding.selected_method_inputs == (selected,)
    legacy_payload = binding.model_dump(mode="json")
    assert "selected_method_input_steps" not in legacy_payload
    assert sha256(to_canonical_bytes(legacy_payload, CanonSpec())).hexdigest() == (
        "8a96c7e6ee5b9905a9b9cd199945659e27fe309b6acab8851046081cc9933806"
    )
    with pytest.raises(ValueError):
        FoundryInputBindings(**fields, selected_method_inputs=(selected,))
    with pytest.raises(ValueError):
        FoundryInputBindings(
            **fields,
            schema_version="1.4",
            resolved_binding_manifest_ref=manifest_ref,
            selected_method_inputs=(selected, selected),
        )
    with pytest.raises(ValueError):
        FoundryInputBindings(
            **fields,
            schema_version="1.4",
            resolved_binding_manifest_ref=manifest_ref,
            selected_method_inputs=(selected,),
            registered_sql_admission_ref=_ref("sql.admission"),
        )
    with pytest.raises(ValueError, match="foundry_input_bindings_method_inputs_version_mismatch"):
        FoundryInputBindings(
            **fields,
            selected_method_input_steps=(),
        )


def _input_scope(year: int = 2024) -> ModelInputScope:
    return ModelInputScope(
        population_ref="population:test",
        geography_ref="geography:test",
        jurisdiction_ref="jurisdiction:test",
        period_start=date(year, 1, 1),
        period_end=date(year, 12, 31),
        time_role="observation_time",
    )


def _selected_vector() -> FoundrySelectedMethodVectorInput:
    digest = "sha256:" + "a" * 64
    return FoundrySelectedMethodVectorInput(
        model_input_obligation_ref=_ref("runtime.quality.model_input_obligation"),
        binding_id="binding-step-0",
        port_id="port",
        slot_id="slot",
        npy_value_ref=_ref("foundry.selected_method_input_value", "application/x-npy"),
        entity_axis_ref=_ref("foundry.selected_entity_axis"),
        source_descriptor=SelectedEntityVectorSourceDescriptor(
            source_view_ref=_ref("tests.selected_source_view"),
            member_ids_pointer="/members/ids",
            values_pointer="/members/values",
        ),
        alignment_identity=EntityAxisValueIdentity(
            axis_sha256=digest,
            unit_id="usd",
            dtype="float64",
            shape=(2,),
            input_order_sha256=digest,
            value_sha256=digest,
            aligned_value_sha256=digest,
            alignment_sha256=digest,
        ),
        tensor_value_sha256="b" * 64,
    )


def test_method_input_binding_v15_step_rows_are_unique_and_exclude_legacy_rows() -> None:
    fields = {
        "data_snapshot_ref": _ref("fabric.data_snapshot"),
        "registry_bundle_ref": _ref("core.registry_bundle"),
        "bound_state_snapshot_ref": StateSnapshotRef.model_validate(
            _ref("foundry.state_snapshot").model_dump()
        ),
        "resolved_binding_manifest_ref": ResolvedInputBindingManifestRef.model_validate(
            _ref("foundry.resolved_input_binding_manifest").model_dump()
        ),
    }
    scalar = FoundrySelectedMethodInput(
        model_input_obligation_ref=_ref("runtime.quality.model_input_obligation"),
        binding_id="binding-step-0",
        port_id="port",
        slot_id="slot",
        canonical_value=Decimal(1),
        dtype="float32",
        shape=(),
        npy_value_ref=_ref("foundry.selected_method_input_value", "application/x-npy"),
        value_sha256="a" * 64,
    )
    row = FoundrySelectedMethodInputAtStep(
        step_scope=ModelInputStepScope(port_id="port", step=0, scope=_input_scope()),
        input_kind="scalar",
        input=scalar,
    )
    next_year = row.model_copy(
        update={
            "step_scope": ModelInputStepScope(port_id="port", step=1, scope=_input_scope(2025)),
            "input": scalar.model_copy(update={"binding_id": "binding-step-1"}),
        }
    )
    binding = FoundryInputBindings(
        **fields,
        schema_version="1.5",
        selected_method_input_steps=(row, next_year),
    )

    payload = binding.model_dump(mode="json")
    assert payload["selected_method_input_steps"][0]["step_scope"]["step"] == 0
    assert "selected_method_inputs" not in payload
    with pytest.raises(ValueError, match="foundry_input_bindings_method_input_steps_duplicate"):
        FoundryInputBindings(
            **fields,
            schema_version="1.5",
            selected_method_input_steps=(row, row),
        )
    with pytest.raises(
        ValueError, match="foundry_input_bindings_method_input_step_binding_duplicate"
    ):
        FoundryInputBindings(
            **fields,
            schema_version="1.5",
            selected_method_input_steps=(
                row,
                row.model_copy(update={"step_scope": next_year.step_scope}),
            ),
        )
    with pytest.raises(ValueError, match="foundry_input_bindings_method_input_steps_order_invalid"):
        FoundryInputBindings(
            **fields,
            schema_version="1.5",
            selected_method_input_steps=(next_year, row),
        )
    with pytest.raises(ValueError, match="foundry_input_bindings_method_inputs_version_mismatch"):
        FoundryInputBindings(
            **fields,
            schema_version="1.5",
            selected_method_inputs=(scalar,),
            selected_method_input_steps=(row,),
        )


def test_method_input_binding_v15_vector_carries_axis_and_source_identity() -> None:
    fields = {
        "data_snapshot_ref": _ref("fabric.data_snapshot"),
        "registry_bundle_ref": _ref("core.registry_bundle"),
        "bound_state_snapshot_ref": StateSnapshotRef.model_validate(
            _ref("foundry.state_snapshot").model_dump()
        ),
        "resolved_binding_manifest_ref": ResolvedInputBindingManifestRef.model_validate(
            _ref("foundry.resolved_input_binding_manifest").model_dump()
        ),
    }
    vector = _selected_vector()
    row = FoundrySelectedMethodInputAtStep(
        step_scope=ModelInputStepScope(port_id="port", step=0, scope=_input_scope()),
        input_kind="vector",
        input=vector,
    )
    binding = FoundryInputBindings(
        **fields,
        schema_version="1.5",
        selected_method_input_steps=(row,),
    )

    assert binding.selected_method_input_steps == (row,)
    assert row.input.alignment_identity.axis_sha256 == vector.alignment_identity.axis_sha256
    with pytest.raises(
        ValueError, match="foundry_input_bindings_method_input_step_shadows_state_slot"
    ):
        FoundryInputBindings(
            **fields,
            schema_version="1.5",
            rules=(
                FoundryInputBindingRule(
                    binding_id="state-binding",
                    source_path="state.balance",
                    target_slot_id="slot",
                ),
            ),
            selected_method_input_steps=(row,),
        )
