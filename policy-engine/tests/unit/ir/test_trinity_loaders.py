from __future__ import annotations

import json
from datetime import date
from decimal import Decimal

import pytest
import yaml

from polisyos.core.artifacts import (
    ArtifactRef,
    CanonInfo,
    FileSystemCAS,
    PutOptions,
    SchemaInfo,
    ensure_ir_artifact_store,
    input_ref_from_artifact_ref,
)
from polisyos.core.artifacts.protocol import ArtifactStore
from polisyos.core.contracts.model_input_requirements import (
    ModelInputPhysicalEncoding,
    ModelInputPort,
    ModelInputPortDeclaration,
    persist_model_input_port_declaration,
)
from polisyos.core.contracts.variable_binding import (
    MeasurementAxis,
    MeasurementBindingProfile,
    MeasurementBindingProfileRef,
    ModelInputScope,
    SelectedVariableBindingRef,
    VariableRepresentation,
    VariableRepresentationRef,
    VariableSemanticDefinition,
    VariableSemanticDefinitionRef,
)
from polisyos.ir.artifacts import put_json_artifact
from polisyos.ir.model_layer.canon import CanonSpec, to_canonical_bytes
from polisyos.ir.model_layer.model_spec import ModelInputPortDeclarationRef, ModelSpec
from polisyos.ir.trinity import TrinityBundle
from polisyos.ir.trinity.loaders import (
    TrinityLoadError,
    load_model_spec,
    load_policy_spec,
    load_problem_frame,
    load_trinity_bundle,
    load_trinity_bundle_artifact,
    persist_trinity_bundle_artifact,
)

ZERO_REF = "sha256:" + "0" * 64
TRINITY_OWNER_CANON_SPEC = CanonSpec(forbid_floats=False)


def _persist_model_input_port_declaration(store: ArtifactStore) -> ArtifactRef:
    evidence_ref = store.put_json(
        {"definition": "Nominal treasury dollars in the opening state of this fixture."},
        PutOptions(
            kind="tests.trinity_model_input_definition",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.tests.TrinityModelInputDefinition", version="1.0"),
        ),
        return_selected_profile=True,
    )
    selected_evidence_ref = SelectedVariableBindingRef.model_validate(
        evidence_ref.model_dump(mode="python")
    )
    definition = VariableSemanticDefinition(
        namespace="test.treasury",
        stable_id="opening-stock",
        revision="1",
        meaning="Nominal treasury dollars in the opening state of this fixture.",
        definition_evidence_refs=(selected_evidence_ref,),
    )
    definition_ref = store.put_json(
        definition,
        PutOptions(
            kind=VariableSemanticDefinition.ARTIFACT_KIND,
            media_type=VariableSemanticDefinition.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=VariableSemanticDefinition.ARTIFACT_SCHEMA_NAME,
                version=VariableSemanticDefinition.ARTIFACT_SCHEMA_VERSION,
            ),
            inputs=[input_ref_from_artifact_ref(evidence_ref, role="definition_evidence")],
        ),
        return_selected_profile=True,
    )
    selected_definition_ref = VariableSemanticDefinitionRef.model_validate(
        definition_ref.model_dump(mode="python")
    )
    representation = VariableRepresentation(
        representation_id="test.treasury.opening-stock-usd",
        revision="1",
        semantic_definition_ref=selected_definition_ref,
        quantity_kind="stock",
        measure_form="absolute",
        unit_id="usd",
        scale_to_unit=Decimal("1"),
        time_support="state_start",
        temporal_granularity="annual",
        aggregation="identity",
        grain=("jurisdiction", "period"),
        population_ref="population:treasury",
    )
    representation_ref = store.put_json(
        representation,
        PutOptions(
            kind=VariableRepresentation.ARTIFACT_KIND,
            media_type=VariableRepresentation.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=VariableRepresentation.ARTIFACT_SCHEMA_NAME,
                version=VariableRepresentation.ARTIFACT_SCHEMA_VERSION,
            ),
            inputs=[input_ref_from_artifact_ref(definition_ref, role="semantic_definition")],
        ),
        return_selected_profile=True,
    )
    selected_representation_ref = VariableRepresentationRef.model_validate(
        representation_ref.model_dump(mode="python")
    )
    profile = MeasurementBindingProfile(
        profile_id="test.treasury.opening-stock",
        revision="1",
        required_axes=(
            MeasurementAxis.QUANTITY_KIND,
            MeasurementAxis.MEASURE_FORM,
            MeasurementAxis.UNIT_ID,
            MeasurementAxis.TIME_SUPPORT,
            MeasurementAxis.TEMPORAL_GRANULARITY,
            MeasurementAxis.AGGREGATION,
            MeasurementAxis.GRAIN,
            MeasurementAxis.POPULATION_REF,
        ),
    )
    profile_ref = store.put_json(
        profile,
        PutOptions(
            kind=MeasurementBindingProfile.ARTIFACT_KIND,
            media_type=MeasurementBindingProfile.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=MeasurementBindingProfile.ARTIFACT_SCHEMA_NAME,
                version=MeasurementBindingProfile.ARTIFACT_SCHEMA_VERSION,
            ),
        ),
        return_selected_profile=True,
    )
    selected_profile_ref = MeasurementBindingProfileRef.model_validate(
        profile_ref.model_dump(mode="python")
    )
    port = ModelInputPort(
        port_id="opening-stock",
        slot_id="government.balance",
        state_path="government_balance",
        unit_id="usd",
        purpose="initial_state",
        semantic_definition_ref=selected_definition_ref,
        representation_ref=selected_representation_ref,
        binding_profile_ref=selected_profile_ref,
        scope=ModelInputScope(
            population_ref="population:treasury",
            geography_ref="geography:fixture",
            jurisdiction_ref="jurisdiction:fixture",
            period_start=date(2022, 1, 1),
            period_end=date(2022, 12, 31),
            time_role="observation_time",
        ),
        physical_encoding=ModelInputPhysicalEncoding(
            shape=(), dtype="float32", max_absolute_error=Decimal("0")
        ),
    )
    return persist_model_input_port_declaration(
        store,
        ModelInputPortDeclaration(ports=(port,)),
    )


def _minimal_trinity_payload() -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "problem_frame": {
            "schema_version": "1.0",
            "problem_id": "pf_cas",
            "domain": "custom",
            "objectives": [],
            "kpis": [],
            "success_criteria": [],
            "hard_constraints": [],
            "soft_constraints": [],
            "stakeholders": [],
            "labels": [],
            "notes": [],
        },
        "policy_spec": {
            "schema_version": "1.0",
            "policy_id": "ps_cas",
            "interventions": [],
            "mechanism_bindings": [],
            "parameters": [],
            "labels": [],
            "notes": [],
        },
        "model_spec": {
            "schema_version": "1.0",
            "model_id": "ms_cas",
            "data_snapshot_ref": ZERO_REF,
            "registry_bundle_ref": None,
            "assumptions": [],
            "labels": [],
            "notes": [],
        },
    }


def test_load_problem_frame_from_json_bytes() -> None:
    payload = {
        "schema_version": "1.0",
        "problem_id": "pf_demo",
        "domain": "custom",
        "objectives": [],
        "kpis": [],
        "success_criteria": [],
        "hard_constraints": [],
        "soft_constraints": [],
        "stakeholders": [],
        "labels": [],
        "notes": [],
    }
    data = json.dumps(payload).encode("utf-8")
    model = load_problem_frame(data)
    assert model.problem_id == "pf_demo"


def test_load_policy_spec_from_yaml_bytes() -> None:
    payload = {
        "schema_version": "1.0",
        "policy_id": "ps_demo",
        "interventions": [],
        "mechanism_bindings": [],
        "parameters": [],
        "labels": [],
        "notes": [],
    }
    data = yaml.safe_dump(payload).encode("utf-8")
    model = load_policy_spec(data)
    assert model.policy_id == "ps_demo"


def test_load_model_spec_from_json_bytes() -> None:
    payload = {
        "schema_version": "1.0",
        "model_id": "ms_demo",
        "data_snapshot_ref": ZERO_REF,
        "registry_bundle_ref": None,
        "assumptions": [],
        "labels": [],
        "notes": [],
    }
    data = json.dumps(payload).encode("utf-8")
    model = load_model_spec(data)
    assert model.model_id == "ms_demo"


def test_load_model_spec_1_1_requires_explicit_target_schema_version() -> None:
    declaration_ref = {
        "artifact_id": "sha256:" + "1" * 64,
        "kind": "ir.model_input_port_declaration",
        "media_type": "application/json",
        "manifest_profile_sha256": "sha256:" + "2" * 64,
    }
    payload = {
        "schema_version": "1.1",
        "model_id": "ms_with_ports",
        "data_snapshot_ref": ZERO_REF,
        "model_input_port_declaration_ref": declaration_ref,
    }
    data = json.dumps(payload).encode("utf-8")

    model = load_model_spec(data, target_schema_version="1.1")

    assert model.schema_version == "1.1"
    assert model.model_input_port_declaration_ref is not None
    assert str(model.model_input_port_declaration_ref.artifact_id) == declaration_ref["artifact_id"]
    with pytest.raises(TrinityLoadError, match="Unsupported schema_version"):
        load_model_spec(data)


def test_load_trinity_bundle_from_mapping() -> None:
    payload = {
        "schema_version": "1.0",
        "problem_frame": {
            "schema_version": "1.0",
            "problem_id": "pf_demo",
            "domain": "custom",
            "objectives": [],
            "kpis": [],
            "success_criteria": [],
            "hard_constraints": [],
            "soft_constraints": [],
            "stakeholders": [],
            "labels": [],
            "notes": [],
        },
        "policy_spec": {
            "schema_version": "1.0",
            "policy_id": "ps_demo",
            "interventions": [],
            "mechanism_bindings": [],
            "parameters": [],
            "labels": [],
            "notes": [],
        },
        "model_spec": {
            "schema_version": "1.0",
            "model_id": "ms_demo",
            "data_snapshot_ref": ZERO_REF,
            "registry_bundle_ref": None,
            "assumptions": [],
            "labels": [],
            "notes": [],
        },
    }
    bundle = load_trinity_bundle(payload)
    assert isinstance(bundle, TrinityBundle)


def test_load_trinity_bundle_artifact_uses_selected_owner_manifest(tmp_path) -> None:
    store = ensure_ir_artifact_store(FileSystemCAS(tmp_path / "cas"))
    payload = _minimal_trinity_payload()
    put_json_artifact(
        store,
        payload,
        kind=TrinityBundle.ARTIFACT_KIND,
        schema_name="polisyos.ir.OtherPayload",
        schema_version="9.0",
        canon_spec=TRINITY_OWNER_CANON_SPEC,
    )
    selected_ref = put_json_artifact(
        store,
        payload,
        kind=TrinityBundle.ARTIFACT_KIND,
        schema_name=TrinityBundle.ARTIFACT_SCHEMA_NAME,
        schema_version=TrinityBundle.ARTIFACT_SCHEMA_VERSION,
        canon_spec=TRINITY_OWNER_CANON_SPEC,
        return_selected_profile=True,
    )

    bundle = load_trinity_bundle_artifact(store, selected_ref)

    assert bundle.problem_frame.problem_id == "pf_cas"
    with pytest.raises(TrinityLoadError, match="manifest"):
        load_trinity_bundle_artifact(store, selected_ref["artifact_id"])


def test_selected_trinity_reopens_model_input_port_declaration_ref(tmp_path) -> None:
    store = ensure_ir_artifact_store(FileSystemCAS(tmp_path / "cas"))
    declaration = _persist_model_input_port_declaration(store)
    declaration_ref = ModelInputPortDeclarationRef.from_selected_write(
        declaration.model_dump(mode="python")
    )
    bundle = load_trinity_bundle(_minimal_trinity_payload())
    model_spec = ModelSpec(
        schema_version="1.1",
        model_id="ms_with_ports",
        data_snapshot_ref=ZERO_REF,
        model_input_port_declaration_ref=declaration_ref,
    )
    bundle = bundle.model_copy(update={"model_spec": model_spec})
    selected_bundle_ref = persist_trinity_bundle_artifact(
        store,
        bundle,
        inputs=[
            input_ref_from_artifact_ref(
                declaration,
                role="model_input_port_declaration",
            )
        ],
    )

    reopened = load_trinity_bundle_artifact(store, selected_bundle_ref)

    assert reopened.schema_version == "1.0"
    assert reopened.model_spec == model_spec
    assert reopened.model_spec.model_input_port_declaration_ref == declaration_ref
    assert store.get_manifest(selected_bundle_ref).inputs == [
        input_ref_from_artifact_ref(declaration, role="model_input_port_declaration")
    ]


@pytest.mark.parametrize(
    ("manifest_version", "payload_version", "error_match"),
    [
        ("1.0", "1.0", None),
        ("1.0", "9.0", "Unsupported schema_version"),
        ("9.0", "1.0", "manifest"),
    ],
)
def test_load_trinity_bundle_artifact_requires_matching_payload_and_manifest_version(
    tmp_path,
    manifest_version: str,
    payload_version: str,
    error_match: str | None,
) -> None:
    store = ensure_ir_artifact_store(FileSystemCAS(tmp_path / "cas"))
    payload = _minimal_trinity_payload()
    payload["schema_version"] = payload_version
    selected_ref = put_json_artifact(
        store,
        payload,
        kind=TrinityBundle.ARTIFACT_KIND,
        schema_name=TrinityBundle.ARTIFACT_SCHEMA_NAME,
        schema_version=manifest_version,
        canon_spec=TRINITY_OWNER_CANON_SPEC,
        return_selected_profile=True,
    )

    if error_match is None:
        bundle = load_trinity_bundle_artifact(store, selected_ref)
        assert bundle.schema_version == manifest_version
    else:
        with pytest.raises(TrinityLoadError, match=error_match):
            load_trinity_bundle_artifact(store, selected_ref)


@pytest.mark.parametrize(
    ("kind", "media_type", "schema_name", "schema_version"),
    [
        ("other.kind", "application/json", TrinityBundle.ARTIFACT_SCHEMA_NAME, "1.0"),
        (
            TrinityBundle.ARTIFACT_KIND,
            "application/yaml",
            TrinityBundle.ARTIFACT_SCHEMA_NAME,
            "1.0",
        ),
        (TrinityBundle.ARTIFACT_KIND, "application/json", "polisyos.ir.OtherPayload", "1.0"),
        (
            TrinityBundle.ARTIFACT_KIND,
            "application/json",
            TrinityBundle.ARTIFACT_SCHEMA_NAME,
            "9.0",
        ),
    ],
)
def test_load_trinity_bundle_artifact_refuses_wrong_owner_metadata(
    tmp_path, kind: str, media_type: str, schema_name: str, schema_version: str
) -> None:
    core_store = FileSystemCAS(tmp_path / "cas")
    store = ensure_ir_artifact_store(core_store)
    options = PutOptions(
        kind=kind,
        media_type=media_type,
        schema=SchemaInfo(name=schema_name, version=schema_version),
        canon=CanonInfo.from_spec(TRINITY_OWNER_CANON_SPEC),
    )
    if media_type == "application/json":
        selected_ref = core_store.put_json(
            _minimal_trinity_payload(),
            options,
            canon_spec=TRINITY_OWNER_CANON_SPEC,
            return_selected_profile=True,
        )
    else:
        selected_ref = core_store.put_bytes(
            to_canonical_bytes(_minimal_trinity_payload(), TRINITY_OWNER_CANON_SPEC),
            options,
            return_selected_profile=True,
        )

    with pytest.raises(TrinityLoadError, match="manifest"):
        load_trinity_bundle_artifact(store, selected_ref)
