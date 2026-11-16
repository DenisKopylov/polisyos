"""Replay two synthetic held-out domains through the selected vector consumer."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from fractions import Fraction
from pathlib import Path

import pytest

from polisyos.core.artifacts import (
    artifact_ref_identity_key,
    input_ref_from_artifact_ref,
    validate_core_model_json_artifact,
)
from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.contracts.foundry import (
    ExecuteRequest,
    SemanticHorizonStepContext,
    SimulationResultRef,
)
from polisyos.core.contracts.model_input_requirements import load_model_input_obligation_set
from polisyos.core.contracts.variable_binding import (
    VariableRepresentationRef,
    VariableSemanticDefinition,
    VariableSemanticDefinitionRef,
    load_variable_representation,
    variable_representation_manifest_inputs,
)
from polisyos.data_forge.domains.catalog.knowledge import measurement_binding
from polisyos.data_forge.domains.catalog.knowledge.acquisition_authority import (
    DEFAULT_ACQUISITION_AUTHORITY_REGISTRY,
    AcquisitionAuthorityEntry,
    AcquisitionAuthorityError,
    AcquisitionSourceMeasureScope,
    CanonicalAcquisitionAuthority,
    build_authority_entry,
    build_authority_registry,
)
from polisyos.data_forge.read_api.catalog import prepare_registered_entity_vector_input_steps
from polisyos.foundry.data_plane.bindings import (
    build_input_bindings,
    replay_selected_method_input_step_facts,
)
from polisyos.foundry.data_plane.selected_tensors import selected_tensor_value_sha256
from polisyos.foundry.execute import api as execute_api
from tests._helpers.acquisition_production import (
    _baseline,
    _entry,
    _sha,
    _write_l5,
    _write_provision,
)
from tests._helpers.selected_method_entity_vector import (
    SelectedMethodEntityVectorCase,
    SelectedMethodEntityVectorFixtureData,
    prepare_selected_method_entity_vector_case,
    vector_read_limits,
)
from tools.lib.imports import repo_root_from

_CASES = (
    pytest.param(
        SelectedMethodEntityVectorFixtureData(
            namespace="heldout.water_infrastructure",
            stable_id="annual_delivery_batches",
            meaning=(
                "Synthetic annual count of water-infrastructure delivery batches per district; "
                "an artificial test quantity, not a physical water volume."
            ),
            population_ref="population:synthetic-water-districts",
            geography_ref="geography:synthetic-water-districts",
            jurisdiction_ref="jurisdiction:synthetic-water-study",
            member_ids=(
                "water-district-a",
                "water-district-b",
                "water-district-c",
                "water-district-d",
            ),
            annual_values=((8, 20, 36, 56), (16, 24, 32, 48)),
        ),
        (Fraction(1, 3), Fraction(13, 60)),
        id="synthetic-water-delivery-batches",
    ),
    pytest.param(
        SelectedMethodEntityVectorFixtureData(
            namespace="heldout.school_district_activity",
            stable_id="annual_activity_sessions",
            meaning=(
                "Synthetic annual count of school-district activity sessions; an artificial "
                "test quantity, not a claim about actual contact hours."
            ),
            population_ref="population:synthetic-school-districts",
            geography_ref="geography:synthetic-school-districts",
            jurisdiction_ref="jurisdiction:synthetic-school-study",
            member_ids=(
                "school-district-a",
                "school-district-b",
                "school-district-c",
                "school-district-d",
            ),
            annual_values=((12, 18, 30, 60), (15, 25, 35, 45)),
        ),
        (Fraction(13, 40), Fraction(5, 24)),
        id="synthetic-school-activity-sessions",
    ),
)


def _authority_entry(
    definition_ref: VariableSemanticDefinitionRef,
    representation_ref: VariableRepresentationRef,
    fixture: SelectedMethodEntityVectorFixtureData,
    *,
    suffix: str,
) -> AcquisitionAuthorityEntry:
    values = _entry().model_dump(mode="python", exclude={"entry_id"})
    values.update(
        {
            "target_variable": f"unrelated.local.source.label.{fixture.namespace}.{suffix}",
            "landing_dataset_id": f"synthetic-heldout.{fixture.stable_id}.{suffix}",
            "landing_distribution_id": f"synthetic-heldout.{fixture.stable_id}.{suffix}.json",
            "source_catalog_dataset_id": f"synthetic-heldout-catalog.{fixture.stable_id}.{suffix}",
            "source_catalog_distribution_id": (
                f"synthetic-heldout-catalog.{fixture.stable_id}.{suffix}.json"
            ),
            "upstream_metric_id": f"local_metric_{suffix}",
            "catalog_raw_variable": f"local_metric_{suffix}",
            "raw_field": "value",
            "raw_unit": "amount",
            "canonical_unit": "amount",
            "unit_transform": "identity",
            "unit_transform_ref": "fabric://units/amount-identity/v1",
            "source_measure_scope": AcquisitionSourceMeasureScope(
                population=fixture.population_ref,
                temporal_granularity="annual",
                jurisdiction_ref=fixture.jurisdiction_ref,
                time_period_basis="calendar_year",
                source_geography_id=fixture.geography_ref,
                geography_ref=fixture.geography_ref,
            ),
            "source_semantic_definition_ref": definition_ref,
            "source_representation_ref": representation_ref,
            "source_provenance_class": None,
            "evidence_refs": ("fixture://synthetic-heldout/metadata-only/no-observations",),
            "title": f"Synthetic held-out source {suffix}",
            "description": "Test-owned metadata; no empirical observations or fetch permission.",
            "temporal_start": "2020",
            "temporal_end": "2021",
        }
    )
    return build_authority_entry(**values)


def _build_authority(
    tmp_path: Path,
    store: FileSystemCAS,
    fixture: SelectedMethodEntityVectorFixtureData,
    definition_ref: VariableSemanticDefinitionRef,
    representation_ref: VariableRepresentationRef,
) -> tuple[CanonicalAcquisitionAuthority, VariableSemanticDefinitionRef, VariableRepresentationRef]:
    original_definition = validate_core_model_json_artifact(
        VariableSemanticDefinition, store, definition_ref
    )
    wrong_definition = original_definition.model_copy(
        update={
            "revision": "2",
            "meaning": original_definition.meaning + " Different revision and meaning.",
        }
    )
    wrong_definition_raw = store.put_json(
        wrong_definition,
        PutOptions(
            kind=wrong_definition.ARTIFACT_KIND,
            media_type=wrong_definition.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=wrong_definition.ARTIFACT_SCHEMA_NAME,
                version=wrong_definition.ARTIFACT_SCHEMA_VERSION,
            ),
            inputs=[
                input_ref_from_artifact_ref(ref, role="definition_evidence")
                for ref in wrong_definition.definition_evidence_refs
            ],
        ),
        return_selected_profile=True,
    )
    wrong_definition_ref = VariableSemanticDefinitionRef.model_validate(
        wrong_definition_raw.model_dump(mode="json")
    )
    original_representation = load_variable_representation(store, representation_ref)
    wrong_representation = original_representation.model_copy(
        update={
            "representation_id": (
                f"{original_representation.representation_id}.wrong-definition-revision"
            ),
            "semantic_definition_ref": wrong_definition_ref,
        }
    )
    wrong_representation_raw = store.put_json(
        wrong_representation,
        PutOptions(
            kind=wrong_representation.ARTIFACT_KIND,
            media_type=wrong_representation.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=wrong_representation.ARTIFACT_SCHEMA_NAME,
                version=wrong_representation.ARTIFACT_SCHEMA_VERSION,
            ),
            inputs=list(variable_representation_manifest_inputs(wrong_representation)),
        ),
        return_selected_profile=True,
    )
    wrong_representation_ref = VariableRepresentationRef.model_validate(
        wrong_representation_raw.model_dump(mode="json")
    )

    selected_entry = _authority_entry(
        definition_ref, representation_ref, fixture, suffix="unrelated-label"
    )
    wrong_entry = _authority_entry(
        wrong_definition_ref,
        wrong_representation_ref,
        fixture,
        suffix="similar-label-wrong-revision",
    )
    authority_root = tmp_path / "catalog-owner"
    baseline = _baseline(authority_root)
    l5_path = _write_l5(authority_root)
    registry = build_authority_registry(
        baseline_content_sha256=_sha(baseline),
        l5_measurement_registry_sha256=_sha(l5_path),
        entries=(selected_entry, wrong_entry),
    )
    registry_path = authority_root / DEFAULT_ACQUISITION_AUTHORITY_REGISTRY
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(registry.model_dump_json(), encoding="utf-8")
    _write_provision(
        authority_root,
        baseline=baseline,
        l5_path=l5_path,
        baseline_owner_ref="repo://catalog/catalog.duckdb",
    )
    authority = CanonicalAcquisitionAuthority.from_provision(
        repo_root=authority_root,
        baseline_path=baseline,
    )
    return authority, wrong_definition_ref, wrong_representation_ref


def _pairwise_gini(values: tuple[int, ...]) -> Fraction:
    """Compute Gini by pairwise differences, independently of Foundry's rank method."""
    return Fraction(
        sum(abs(left - right) for left in values for right in values),
        2 * len(values) * sum(values),
    )


def _replace_authority_registry(
    authority: CanonicalAcquisitionAuthority,
    entries: tuple[AcquisitionAuthorityEntry, ...],
) -> None:
    """Rewrite only the test-owned authority registry under its selected temp root."""
    registry = build_authority_registry(
        baseline_content_sha256=authority.provision.baseline_content_sha256,
        l5_measurement_registry_sha256=(authority.provision.l5_measurement_registry_content_sha256),
        entries=entries,
    )
    registry_path = authority.repo_root / DEFAULT_ACQUISITION_AUTHORITY_REGISTRY
    registry_path.write_text(registry.model_dump_json(), encoding="utf-8")


def _fresh_read_vector_results(
    case: SelectedMethodEntityVectorCase,
    result_refs: list[SimulationResultRef],
    expected_values: tuple[tuple[int, ...], tuple[int, ...]],
    expected_gini: tuple[Fraction, Fraction],
) -> list[dict[str, object]]:
    """Read selected values and Gini calls from a fresh read-only Python process."""
    product_root = repo_root_from(__file__).resolve()
    assert (product_root / "src/polisyos").is_dir()
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(product_root / "src")
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    code = r"""
import json
import sys
from io import BytesIO
from pathlib import Path
import numpy as np
from polisyos.core.artifacts import ArtifactRef, validate_core_model_json_artifact
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.contracts.foundry import MethodExecutionBundle, MethodMetricBindingSet, MethodOutputPayload, SimulationResultRef
from polisyos.core.contracts.semantic_input_binding import load_resolved_input_binding_manifest
from polisyos.data_forge.domains.catalog.knowledge.measurement_binding import load_selected_entity_vector_source_meaning
from polisyos.foundry.data_plane.bindings import load_input_bindings
from polisyos.foundry.data_plane.selected_tensors import selected_tensor_value_sha256
from polisyos.foundry.execute import api as execute_api
from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
from polisyos.foundry.methods.catalog.distributional.advanced import GeneralizedGiniEstimator

def forbidden(*args, **kwargs):
    raise AssertionError('fresh held-out consumer attempted execution')

execute_api.execute = forbidden
execute_api.execute_semantic_horizon_step = forbidden
execute_api.execute_program_graph = forbidden
execute_api._execute = forbidden
MethodDispatcher.dispatch = forbidden
GeneralizedGiniEstimator.pure_step = staticmethod(forbidden)
assert Path(execute_api.__file__).resolve().is_relative_to(Path(sys.argv[4]).resolve())
store = FileSystemCAS.open_existing_read_only(Path(sys.argv[1]))
refs = tuple(SimulationResultRef.model_validate(item) for item in json.loads(sys.argv[2]))
expected_values = json.loads(sys.argv[3])
expected_gini = json.loads(sys.argv[5])
admissions = execute_api.admit_semantic_horizon_step_chain(store, refs)
rows = []
for index, (ref, admission) in enumerate(zip(refs, admissions, strict=True)):
    bindings = load_input_bindings(store, admission.basis.input_bindings_ref)
    row, = (row for row in bindings.selected_method_input_steps if row.step_scope.step == index)
    assert bindings.resolved_binding_manifest_ref is not None
    binding_manifest = load_resolved_input_binding_manifest(store, bindings.resolved_binding_manifest_ref)
    vector_step, = (step for step in binding_manifest.entity_vector_steps if step.step_scope.step == index)
    source_meaning = load_selected_entity_vector_source_meaning(store, vector_step.selection.source_meaning_ref)
    assert source_meaning.source_descriptor == vector_step.selection.source_descriptor
    selected = row.input
    value = np.load(BytesIO(store.get_bytes(selected.npy_value_ref)), allow_pickle=False)
    digest = selected_tensor_value_sha256(value.dtype, value.shape, value.tobytes(order='C'))
    assert value.tolist() == expected_values[index]
    assert value.dtype == np.dtype('float64') and value.shape == (4,)
    assert digest == selected.tensor_value_sha256
    edge, = (edge for edge in store.get_manifest(ref).inputs if edge.role == 'method_execution')
    bundle_ref = ArtifactRef(artifact_id=edge.artifact_id, kind=MethodExecutionBundle.ARTIFACT_KIND,
        media_type='application/json', manifest_profile_sha256=edge.manifest_profile_sha256)
    bundle = validate_core_model_json_artifact(MethodExecutionBundle, store, bundle_ref)
    occurrence, = (item for item in bundle.occurrences if item.node_id == 'gini')
    assert occurrence.status == 'succeeded' and occurrence.dispatch is not None
    argument, = (item for item in occurrence.dispatch.input_slot_values if item.slot_id == 'values')
    assert argument.status == 'captured' and argument.value_sha256 == digest
    assert argument.runtime_shape == (4,) and argument.runtime_dtype == np.dtype('float64').str
    output, = (item for item in occurrence.output_slots if item.slot_id == 'result')
    payload = validate_core_model_json_artifact(MethodOutputPayload, store, output.output_ref)
    assert payload.value_path == ('generalized_gini',)
    assert abs(float(payload.value) - expected_gini[index]) <= 1e-15
    binding_set = validate_core_model_json_artifact(MethodMetricBindingSet, store, bundle.method_metric_binding_set_ref)
    binding, = binding_set.bindings
    assert binding.availability == 'unavailable'
    assert 'registered_method_metric_law_missing' in binding.limitation.split(';')
    assert source_meaning.authority_purpose == 'candidate_simulation_input_only'
    assert source_meaning.source_meaning_provenance == 'consumer_asserted'
    assert source_meaning.independent_origin == 'not_established'
    assert source_meaning.source_currentness == 'not_established'
    assert 'semantic_input_limitation:source_meaning_consumer_asserted' in admission.simulation_result.notes
    assert 'semantic_input_limitation:source_scope_consumer_asserted' in admission.simulation_result.notes
    rows.append({'step': index, 'digest': digest, 'gini': payload.value,
                 'source_definition_ref': source_meaning.source_definition_ref.model_dump(mode='json'),
                 'source_representation_ref': source_meaning.source_representation_ref.model_dump(mode='json')})
print(json.dumps(rows, sort_keys=True))
"""
    result = subprocess.run(
        [
            sys.executable,
            "-B",
            "-c",
            code,
            str(case.store_root),
            json.dumps([ref.model_dump(mode="json") for ref in result_refs]),
            json.dumps([list(values) for values in expected_values]),
            str(product_root),
            json.dumps([float(value) for value in expected_gini]),
        ],
        capture_output=True,
        check=False,
        cwd=product_root,
        env=environment,
        text=True,
        timeout=180,
    )
    assert result.returncode == 0, (result.stdout, result.stderr)
    return json.loads(result.stdout)


@pytest.mark.parametrize(("fixture_data", "expected_gini"), _CASES)
def test_p07_two_held_out_domains_reach_selected_gini_consumer_and_remain_candidates(
    tmp_path: Path,
    fixture_data: SelectedMethodEntityVectorFixtureData,
    expected_gini: tuple[Fraction, Fraction],
) -> None:
    """Exercise semantic selection while test-owned arrays stay untrusted candidate inputs.

    Catalog selects exact definition and representation refs. The array bytes and JSON pointers
    remain the synthetic helper's fixture-owned values; Catalog does not fetch or authorize them.
    """
    product_root = repo_root_from(__file__).resolve()
    assert (product_root / "src/polisyos").is_dir()
    fixture = prepare_selected_method_entity_vector_case(tmp_path, fixture_data=fixture_data)
    case = fixture.case
    try:
        selected_set, _ = load_model_input_obligation_set(case.store, fixture.obligation_set_ref)
        source_definition_ref = fixture.source_inputs[0][1].source_definition_ref
        source_representation_ref = fixture.source_inputs[0][1].source_representation_ref
        authority, wrong_definition_ref, wrong_representation_ref = _build_authority(
            tmp_path,
            case.store,
            fixture_data,
            source_definition_ref,
            source_representation_ref,
        )
        discovery = authority.discover_model_input_source_descriptor(
            case.store,
            model_input_interface_ref=selected_set.invocation.interface_ref,
            port_id=fixture.port.port_id,
            include_query_envelope=True,
        )
        assert discovery.source_semantic_definition_ref == source_definition_ref
        assert discovery.source_representation_ref == source_representation_ref
        assert discovery.semantic_correspondence == "not_established"
        assert discovery.may_not_use_for == (
            "measurement_admission",
            "fetch_permission",
            "claim_evidence",
            "source_currentness",
        )
        assert discovery.query_envelope is not None
        assert tuple(row.entry_id for row in discovery.query_envelope.rows) == (
            discovery.authority_entry_id,
        )
        registry = authority._load_registry()
        indexed = authority._source_entries_for_semantic_definition(
            registry, artifact_ref_identity_key(discovery.source_semantic_definition_ref)
        )
        assert tuple(row.entry_id for row in indexed) == (discovery.authority_entry_id,)
        assert authority._semantic_definition_index_cache is not None
        assert authority._semantic_definition_index_cache.is_complete
        assert authority._semantic_definition_index_cache.eligible_entry_count == 2
        (selected_entry,) = (
            entry for entry in registry.entries if entry.entry_id == discovery.authority_entry_id
        )
        (wrong_entry,) = (entry for entry in registry.entries if entry != selected_entry)
        assert selected_entry.target_variable.startswith("unrelated.local.source.label.")
        assert wrong_entry.target_variable.startswith("unrelated.local.source.label.")
        assert wrong_entry.target_variable != selected_entry.target_variable
        assert (
            wrong_entry.source_semantic_definition_ref != discovery.source_semantic_definition_ref
        )
        assert (
            selected_entry.source_semantic_definition_ref
            == discovery.source_semantic_definition_ref
        )

        original_entries = registry.entries
        _replace_authority_registry(
            authority,
            tuple(
                entry
                for entry in original_entries
                if entry.entry_id != discovery.authority_entry_id
            ),
        )
        with pytest.raises(AcquisitionAuthorityError) as removed:
            authority.discover_model_input_source_descriptor(
                case.store,
                model_input_interface_ref=selected_set.invocation.interface_ref,
                port_id=fixture.port.port_id,
                include_query_envelope=True,
            )
        assert removed.value.code == "model_input_source_descriptor_unresolved"
        assert removed.value.query_envelope is not None
        assert removed.value.query_envelope.rows == ()

        _replace_authority_registry(authority, original_entries)
        assert authority._load_registry().content_sha256 == registry.content_sha256
        restored_discovery = authority.discover_model_input_source_descriptor(
            case.store,
            model_input_interface_ref=selected_set.invocation.interface_ref,
            port_id=fixture.port.port_id,
            include_query_envelope=True,
        )
        assert restored_discovery == discovery

        discovered_inputs = tuple(
            (
                subject,
                meaning.model_copy(
                    update={
                        "source_definition_ref": discovery.source_semantic_definition_ref,
                        "source_representation_ref": discovery.source_representation_ref,
                    }
                ),
            )
            for subject, meaning in fixture.source_inputs
        )
        assert all(
            artifact_ref_identity_key(meaning.source_definition_ref)
            == artifact_ref_identity_key(discovery.source_semantic_definition_ref)
            and artifact_ref_identity_key(meaning.source_representation_ref)
            == artifact_ref_identity_key(discovery.source_representation_ref)
            for _, meaning in discovered_inputs
        )
        assert all(
            meaning.source_descriptor == fixture.source_inputs[index][1].source_descriptor
            and meaning.source_descriptor.source_view_ref == fixture.source_view_ref
            for index, (_, meaning) in enumerate(discovered_inputs)
        )

        wrong_inputs = tuple(
            (
                subject,
                meaning.model_copy(
                    update={
                        "source_definition_ref": wrong_definition_ref,
                        "source_representation_ref": wrong_representation_ref,
                    }
                ),
            )
            for subject, meaning in discovered_inputs
        )
        with pytest.raises(ValueError, match="same_definition_profile_requires_exact_definition"):
            prepare_registered_entity_vector_input_steps(
                case.store,
                data_snapshot_ref=case.data_snapshot_ref,
                obligation_set_ref=fixture.obligation_set_ref,
                source_inputs=wrong_inputs,
                read_limits=vector_read_limits(),
            )

        manifest_ref = prepare_registered_entity_vector_input_steps(
            case.store,
            data_snapshot_ref=case.data_snapshot_ref,
            obligation_set_ref=fixture.obligation_set_ref,
            source_inputs=discovered_inputs,
            read_limits=vector_read_limits(),
        )
        manifest = measurement_binding.load_resolved_input_binding_manifest(
            case.store, manifest_ref
        )
        assert len(manifest.entity_vector_steps) == 2
        for row in manifest.entity_vector_steps:
            meaning = measurement_binding.load_selected_entity_vector_source_meaning(
                case.store, row.selection.source_meaning_ref
            )
            assert artifact_ref_identity_key(meaning.source_definition_ref) == (
                artifact_ref_identity_key(discovery.source_semantic_definition_ref)
            )
            assert artifact_ref_identity_key(meaning.source_representation_ref) == (
                artifact_ref_identity_key(discovery.source_representation_ref)
            )
            assert meaning.authority_purpose == "candidate_simulation_input_only"
            assert meaning.source_meaning_provenance == "consumer_asserted"
            assert meaning.independent_origin == "not_established"
            assert meaning.source_currentness == "not_established"

        built = build_input_bindings(
            case.store,
            data_snapshot_ref=case.data_snapshot_ref,
            registry_bundle_ref=case.registry_bundle_ref,
            resolved_binding_manifest_ref=manifest_ref,
            return_selected_profile=True,
        )
        facts = replay_selected_method_input_step_facts(
            case.store,
            input_bindings_ref=built.input_bindings_ref,
            expected_invocation=selected_set.invocation,
        )
        assert facts.coverage.is_complete
        assert all(row.input_kind == "vector" for row in facts.records)
        assert len(facts.records) == 2
        expected_vectors = fixture_data.annual_values
        for index, record in enumerate(facts.records):
            assert tuple(
                int(value) for value in facts.values[(fixture.port.slot_id, index)].tolist()
            ) == (tuple(sorted(expected_vectors[index])))
            expected_hash = selected_tensor_value_sha256(
                facts.values[(fixture.port.slot_id, index)].dtype,
                facts.values[(fixture.port.slot_id, index)].shape,
                facts.values[(fixture.port.slot_id, index)].tobytes(order="C"),
            )
            assert record.input.tensor_value_sha256 == expected_hash

        request = ExecuteRequest(
            exec_plan_ref=case.exec_plan_ref,
            registry_bundle_ref=case.registry_bundle_ref,
            input_bindings_ref=built.input_bindings_ref,
            return_selected_profile=True,
        )
        result_refs = []
        for index in selected_set.invocation.steps:
            result = execute_api.execute_semantic_horizon_step(
                case.store,
                request,
                expected_invocation=selected_set.invocation,
                step=SemanticHorizonStepContext(
                    obligation_set_ref=fixture.obligation_set_ref,
                    steps=selected_set.invocation.steps,
                    step_index=index,
                    replication_seed=23,
                    previous_result_ref=None if index == 0 else result_refs[-1],
                ),
            )
            assert result.ok and result.simulation_result_ref is not None
            result_refs.append(result.simulation_result_ref)

        independent = tuple(_pairwise_gini(values) for values in expected_vectors)
        assert independent == expected_gini
        cold_rows = _fresh_read_vector_results(case, result_refs, expected_vectors, expected_gini)
        assert all(
            row["source_definition_ref"]
            == discovery.source_semantic_definition_ref.model_dump(mode="json")
            and row["source_representation_ref"]
            == discovery.source_representation_ref.model_dump(mode="json")
            for row in cold_rows
        )
        assert tuple(Fraction(row["gini"]).limit_denominator(10_000) for row in cold_rows) == (
            expected_gini
        )
    finally:
        case.close()
