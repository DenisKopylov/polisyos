from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import BaseModel, ValidationError

from polisyos.core.artifacts.canonical_profile import CoreJsonReadLimits
from polisyos.core.artifacts.manifest import (
    ArtifactGovernanceInfo,
    ArtifactRef,
    ArtifactTenantContextInfo,
    ProducerInfo,
    SchemaInfo,
)
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.core.contracts.owned_attempt_anchor import OwnedHTERequestContextV1
from polisyos.foundry.data_plane import (
    HTEInputPreparationRefusal,
    PreparedHTEObservationalInput,
    prepare_hte_observational_input,
)
from polisyos.foundry.data_plane.selected_row_candidate_scope import (
    HTECandidateScopeRoleRefs,
    HTECandidateSelectedMethodIdentity,
    HTESelectedRowCandidateScopeArtifacts,
    HTESelectedRowCandidateScopeRead,
    SelectedHTECandidateScopeBindingRef,
    SelectedHTECandidateScopeRoleRef,
    build_hte_selected_row_candidate_scope,
    load_hte_selected_row_candidate_scope,
)
from polisyos.foundry.methods.catalog.causal.hte_v2 import DoubleMachineLearningV2
from polisyos.ir.observation.bundles import (
    HTE_OBSERVATIONAL_DATA_TARGET,
    OBSERVATION_METHOD_INPUT_KIND,
    OBSERVATION_METHOD_INPUT_SCHEMA_NAME,
    OBSERVATION_METHOD_INPUT_SCHEMA_VERSION,
    ObservationMethodInputEnvelope,
)

_LIMITS = CoreJsonReadLimits(
    max_bytes=1_000_000,
    max_depth=64,
    max_elements=100_000,
    max_manifest_bytes=100_000,
)
_SCHEMA = SchemaInfo(
    name=OBSERVATION_METHOD_INPUT_SCHEMA_NAME,
    version=OBSERVATION_METHOD_INPUT_SCHEMA_VERSION,
)
_GOVERNANCE = ArtifactGovernanceInfo(classification="restricted")
_TENANT = ArtifactTenantContextInfo(tenant_id="candidate-test", cell_id="candidate-cell")


def _payload(*, shift_outcome: float = 0.0) -> dict[str, object]:
    return {
        "outcome": [float(index) / 10 + shift_outcome for index in range(40)],
        "treatment": [index % 2 for index in range(40)],
        "covariates": [[float(index), float(index % 3)] for index in range(40)],
        "confounders": [[float(index % 5)] for index in range(40)],
        "feature_names": ["age", "baseline"],
        "confounder_names": ["risk"],
        "sample_ids": [f"sample-{index}" for index in range(40)],
    }


def _put_source(store: FileSystemCAS, payload: dict[str, object]) -> ArtifactRef:
    envelope = ObservationMethodInputEnvelope(
        contract_target=HTE_OBSERVATIONAL_DATA_TARGET,
        contract_payload=payload,
    )
    ref = store.put_json(
        envelope.model_dump(mode="json"),
        PutOptions(
            kind=OBSERVATION_METHOD_INPUT_KIND,
            media_type="application/json",
            schema=_SCHEMA,
            producer=ProducerInfo(
                component="tests.candidate.selected_row_scope_owner",
                version="1.0",
            ),
            governance=_GOVERNANCE,
            tenant_context=_TENANT,
        ),
        canon_spec=CanonSpec(forbid_floats=False, forbid_nan_inf=True, exclude_none=False),
        return_selected_profile=True,
    )
    assert type(ref) is ArtifactRef
    return ref


def _request_context(*, outcome_id: str = "outcome:declared-candidate") -> OwnedHTERequestContextV1:
    return OwnedHTERequestContextV1(
        request_estimand_status="declared",
        request_estimand="mean_effect_over_selected_x",
        request_target_scope_status="declared",
        request_target_scope="selected_evaluation_rows",
        outcome_variable_status="declared",
        outcome_variable_id=outcome_id,
        treatment_variable_status="declared",
        treatment_variable_id="treatment:declared-candidate",
        contrast_status="declared",
        control_value=0.0,
        treated_value=1.0,
        request_alpha_status="not_established",
        requested_alpha=None,
        requested_guarantee_status="not_established",
        requested_guarantee=None,
    )


def _method_identity() -> HTECandidateSelectedMethodIdentity:
    signature = DoubleMachineLearningV2.signature
    return HTECandidateSelectedMethodIdentity(
        method_class=DoubleMachineLearningV2,
        method_fqn=signature.fqn,
        method_version=signature.version,
        method_abi_digest=signature.abi_digest(),
    )


def _prepare(
    store: FileSystemCAS,
    source_ref: ArtifactRef,
) -> PreparedHTEObservationalInput:
    prepared = prepare_hte_observational_input(
        store=store,
        source_ref=source_ref,
        protocol="method_input_envelope_v1",
        method_fqn=DoubleMachineLearningV2.signature.fqn,
        limits=_LIMITS,
        materialization_binding_version="physical_v1",
    )
    assert type(prepared) is PreparedHTEObservationalInput
    assert prepared.materialization_binding_ref is not None
    return prepared


def _produce(
    store: FileSystemCAS,
    prepared: PreparedHTEObservationalInput,
    request_context: OwnedHTERequestContextV1,
):
    assert prepared.materialization_binding_ref is not None
    return build_hte_selected_row_candidate_scope(
        store=store,
        prepared=prepared,
        physical_binding_ref=prepared.materialization_binding_ref,
        request_context=request_context,
        selected_method_identity=_method_identity(),
        limits=_LIMITS,
    )


def _read(
    cas_root: Path,
    artifacts: HTESelectedRowCandidateScopeArtifacts,
    prepared: PreparedHTEObservationalInput,
    request_context: OwnedHTERequestContextV1,
):
    assert prepared.materialization_binding_ref is not None
    return load_hte_selected_row_candidate_scope(
        store=FileSystemCAS.open_existing_read_only(cas_root),
        artifacts=artifacts,
        expected_submitted_ref=prepared.submitted_ref,
        expected_effective_ref=prepared.effective_ref,
        expected_effective_artifact_schema=prepared.effective_artifact_schema,
        expected_physical_binding_ref=prepared.materialization_binding_ref,
        expected_request_context=request_context,
        selected_method_identity=_method_identity(),
        limits=_LIMITS,
    )


def test_actual_producer_and_fresh_bounded_reader_recompute_candidate_roles(
    tmp_path: Path,
) -> None:
    cas_root = tmp_path / "cas"
    store = FileSystemCAS(cas_root, ownership_enforced=False)
    source_ref = _put_source(store, _payload())
    prepared = _prepare(store, source_ref)
    request = _request_context()

    artifacts = _produce(store, prepared, request)
    fresh = _read(cas_root, artifacts, prepared, request)

    assert fresh.binding.observation_count == 40
    assert fresh.binding.control_rows == 20
    assert fresh.binding.treated_rows == 20
    assert fresh.binding.selected_x_shape == (40, 3)
    assert fresh.binding.semantic_alignment_status == "not_established"
    assert fresh.binding.unit_scope_status == "unknown"
    assert fresh.binding.computed_estimand_status == "not_established"
    assert fresh.binding.computed_target_scope_status == "not_established"
    assert fresh.binding.outcome_slot_mapping_origin == "consumer_asserted"
    assert fresh.binding.treatment_slot_mapping_origin == "consumer_asserted"
    assert fresh.population.selected_rows_status == "recomputed"
    assert fresh.outcome.outcome_variable_id == request.outcome_variable_id
    assert fresh.outcome.slot_mapping_origin == "consumer_asserted"
    refs = (
        artifacts.roles.quantity_ref,
        artifacts.roles.treatment_contrast_ref,
        artifacts.roles.population_ref,
        artifacts.roles.outcome_ref,
    )
    assert len({(str(ref.artifact_id), ref.manifest_profile_sha256) for ref in refs}) == 4


def test_fresh_reader_rejects_profile_valid_sibling_role_swap(tmp_path: Path) -> None:
    cas_root = tmp_path / "cas"
    store = FileSystemCAS(cas_root, ownership_enforced=False)
    source_ref = _put_source(store, _payload())
    prepared = _prepare(store, source_ref)
    request = _request_context()
    artifacts = _produce(store, prepared, request)

    swapped_roles = HTECandidateScopeRoleRefs(
        quantity_ref=artifacts.roles.outcome_ref,
        treatment_contrast_ref=artifacts.roles.treatment_contrast_ref,
        population_ref=artifacts.roles.population_ref,
        outcome_ref=artifacts.roles.quantity_ref,
    )
    swapped = HTESelectedRowCandidateScopeArtifacts(
        binding_ref=artifacts.binding_ref,
        roles=swapped_roles,
    )
    with pytest.raises(HTEInputPreparationRefusal, match="candidate_scope_artifact_read_refused"):
        _read(cas_root, swapped, prepared, request)


def test_fresh_reader_rejects_valid_same_role_artifact_for_sibling_request(
    tmp_path: Path,
) -> None:
    cas_root = tmp_path / "cas"
    store = FileSystemCAS(cas_root, ownership_enforced=False)
    source_ref = _put_source(store, _payload())
    prepared = _prepare(store, source_ref)
    request = _request_context()
    sibling_request = _request_context(outcome_id="outcome:other-declaration")
    artifacts = _produce(store, prepared, request)
    sibling_artifacts = _produce(store, prepared, sibling_request)

    mixed_roles = artifacts.roles.model_copy(
        update={"outcome_ref": sibling_artifacts.roles.outcome_ref}
    )
    mixed = HTESelectedRowCandidateScopeArtifacts(
        binding_ref=artifacts.binding_ref,
        roles=mixed_roles,
    )
    with pytest.raises(
        HTEInputPreparationRefusal,
        match="candidate_scope_role_recomputation_mismatch:outcome",
    ):
        _read(cas_root, mixed, prepared, request)


def test_fresh_reader_rejects_role_for_sibling_source_rows(tmp_path: Path) -> None:
    cas_root = tmp_path / "cas"
    store = FileSystemCAS(cas_root, ownership_enforced=False)
    source_a = _put_source(store, _payload())
    source_b = _put_source(store, _payload(shift_outcome=100.0))
    prepared_a = _prepare(store, source_a)
    prepared_b = _prepare(store, source_b)
    request = _request_context()
    artifacts_a = _produce(store, prepared_a, request)
    artifacts_b = _produce(store, prepared_b, request)

    mixed_roles = artifacts_a.roles.model_copy(
        update={"outcome_ref": artifacts_b.roles.outcome_ref}
    )
    mixed = HTESelectedRowCandidateScopeArtifacts(
        binding_ref=artifacts_a.binding_ref,
        roles=mixed_roles,
    )
    with pytest.raises(
        HTEInputPreparationRefusal,
        match="candidate_scope_role_recomputation_mismatch:outcome",
    ):
        _read(cas_root, mixed, prepared_a, request)


def test_fresh_reader_rejects_role_with_unexpected_producer(tmp_path: Path) -> None:
    cas_root = tmp_path / "cas"
    store = FileSystemCAS(cas_root, ownership_enforced=False)
    source_ref = _put_source(store, _payload())
    prepared = _prepare(store, source_ref)
    request = _request_context()
    artifacts = _produce(store, prepared, request)

    original_ref = artifacts.roles.outcome_ref
    original_manifest = store.get_manifest(original_ref)
    sibling_ref = store.put_bytes(
        store.get_bytes(original_ref),
        PutOptions(
            kind=original_manifest.kind,
            media_type=original_manifest.media_type,
            schema=original_manifest.artifact_schema,
            producer=ProducerInfo(component="tests.unexpected_scope_producer", version="1"),
            inputs=original_manifest.inputs,
            canon=original_manifest.canon,
            governance=original_manifest.governance,
            tenant_context=original_manifest.tenant_context,
        ),
        return_selected_profile=True,
    )
    assert sibling_ref.artifact_id == original_ref.artifact_id
    wrong_producer_ref = SelectedHTECandidateScopeRoleRef.model_validate(
        sibling_ref.model_dump(mode="json"), strict=True
    )
    mixed_roles = artifacts.roles.model_copy(update={"outcome_ref": wrong_producer_ref})
    mixed = HTESelectedRowCandidateScopeArtifacts(
        binding_ref=artifacts.binding_ref,
        roles=mixed_roles,
    )

    with pytest.raises(
        HTEInputPreparationRefusal,
        match="candidate_scope_artifact_identity_mismatch",
    ):
        _read(cas_root, mixed, prepared, request)


def test_producer_refuses_absent_or_mismatched_physical_binding_without_fallback(
    tmp_path: Path,
) -> None:
    cas_root = tmp_path / "cas"
    store = FileSystemCAS(cas_root, ownership_enforced=False)
    source_a = _put_source(store, _payload())
    source_b = _put_source(store, _payload(shift_outcome=100.0))
    prepared_a = _prepare(store, source_a)
    prepared_b = _prepare(store, source_b)
    assert prepared_a.materialization_binding_ref is not None
    assert prepared_b.materialization_binding_ref is not None
    before = {str(item) for item in store.iter_artifact_ids()}

    with pytest.raises(
        HTEInputPreparationRefusal, match="candidate_scope_physical_binding_required"
    ):
        build_hte_selected_row_candidate_scope(
            store=store,
            prepared=prepared_a,
            physical_binding_ref=None,
            request_context=_request_context(),
            selected_method_identity=_method_identity(),
            limits=_LIMITS,
        )
    with pytest.raises(
        HTEInputPreparationRefusal,
        match="candidate_scope_physical_binding_ref_mismatch",
    ):
        build_hte_selected_row_candidate_scope(
            store=store,
            prepared=prepared_a,
            physical_binding_ref=prepared_b.materialization_binding_ref,
            request_context=_request_context(),
            selected_method_identity=_method_identity(),
            limits=_LIMITS,
        )
    assert {str(item) for item in store.iter_artifact_ids()} == before


def _persist_selected_role(
    store: FileSystemCAS,
    prepared: PreparedHTEObservationalInput,
    binding_ref: SelectedHTECandidateScopeBindingRef,
    model: BaseModel,
    *,
    schema: SchemaInfo,
) -> SelectedHTECandidateScopeRoleRef:
    from polisyos.foundry.data_plane import selected_row_candidate_scope as scope

    physical_ref = prepared.materialization_binding_ref
    assert physical_ref is not None
    physical_core_ref = scope._as_core_artifact_ref(physical_ref)
    binding_core_ref = scope._as_core_artifact_ref(binding_ref)
    role_ref = scope._persist_model(
        store,
        model=model,
        kind=scope.HTE_CANDIDATE_SCOPE_ROLE_KIND,
        schema=schema,
        inputs=scope._input_edges(
            (
                ("candidate_scope_binding", binding_core_ref),
                ("effective_source", prepared.effective_ref),
                ("physical_materialization", physical_core_ref),
            )
        ),
        governance=prepared.source_governance,
        tenant_context=prepared.source_tenant_context,
        limits=_LIMITS,
    )
    return SelectedHTECandidateScopeRoleRef.model_validate(
        role_ref.model_dump(mode="json"),
        strict=True,
    )


def _persist_forged_row_scope(
    store: FileSystemCAS,
    prepared: PreparedHTEObservationalInput,
    fresh: HTESelectedRowCandidateScopeRead,
) -> HTESelectedRowCandidateScopeArtifacts:
    from polisyos.foundry.data_plane import selected_row_candidate_scope as scope

    physical_ref = prepared.materialization_binding_ref
    assert physical_ref is not None
    physical_core_ref = scope._as_core_artifact_ref(physical_ref)
    forged_binding = fresh.binding.model_copy(update={"control_rows": 19, "treated_rows": 21})
    raw_binding_ref = scope._persist_model(
        store,
        model=forged_binding,
        kind=scope.HTE_CANDIDATE_SCOPE_BINDING_KIND,
        schema=scope.HTE_CANDIDATE_SCOPE_BINDING_SCHEMA,
        inputs=scope._input_edges(
            (
                ("submitted_source", forged_binding.submitted_ref),
                ("effective_source", forged_binding.effective_ref),
                ("physical_materialization", physical_core_ref),
            )
        ),
        governance=prepared.source_governance,
        tenant_context=prepared.source_tenant_context,
        limits=_LIMITS,
    )
    binding_ref = scope.SelectedHTECandidateScopeBindingRef.model_validate(
        raw_binding_ref.model_dump(mode="json"),
        strict=True,
    )
    assert forged_binding.observed_arm_presence_status == "recomputed"
    assert forged_binding.row_order_sha256 == fresh.binding.row_order_sha256
    assert forged_binding.outcome_value_sha256 == fresh.binding.outcome_value_sha256
    assert (
        forged_binding.control_rows + forged_binding.treated_rows
        == forged_binding.observation_count
    )

    projections = (
        (
            "quantity",
            fresh.quantity.model_copy(update={"candidate_scope_binding_ref": binding_ref}),
        ),
        (
            "treatment_contrast",
            fresh.treatment_contrast.model_copy(
                update={
                    "candidate_scope_binding_ref": binding_ref,
                    "control_rows": 19,
                    "treated_rows": 21,
                }
            ),
        ),
        (
            "population",
            fresh.population.model_copy(update={"candidate_scope_binding_ref": binding_ref}),
        ),
        (
            "outcome",
            fresh.outcome.model_copy(update={"candidate_scope_binding_ref": binding_ref}),
        ),
    )
    role_refs: dict[str, SelectedHTECandidateScopeRoleRef] = {}
    for role, model in projections:
        assert model.model_dump(mode="python").get(
            "candidate_scope_binding_ref"
        ) == binding_ref.model_dump(mode="python")
        role_refs[role] = _persist_selected_role(
            store,
            prepared,
            binding_ref,
            model,
            schema=scope.HTE_CANDIDATE_SCOPE_ROLE_SCHEMA,
        )
    assert role_refs["treatment_contrast"].manifest_profile_sha256 is not None
    return HTESelectedRowCandidateScopeArtifacts(
        binding_ref=binding_ref,
        roles=HTECandidateScopeRoleRefs(
            quantity_ref=role_refs["quantity"],
            treatment_contrast_ref=role_refs["treatment_contrast"],
            population_ref=role_refs["population"],
            outcome_ref=role_refs["outcome"],
        ),
    )


def test_reader_recomputes_rows_when_markers_and_complete_lineage_stay_valid(
    tmp_path: Path,
) -> None:
    from polisyos.foundry.data_plane import selected_row_candidate_scope as scope

    cas_root = tmp_path / "cas"
    store = FileSystemCAS(cas_root, ownership_enforced=False)
    source_ref = _put_source(store, _payload())
    prepared = _prepare(store, source_ref)
    request = _request_context()
    artifacts = _produce(store, prepared, request)
    fresh = _read(cas_root, artifacts, prepared, request)

    forged = _persist_forged_row_scope(store, prepared, fresh)

    # Keep all recomputation markers, the selected source rows, and a complete
    # correctly rooted lineage graph. Only the asserted row counts are forged.
    forged_manifest = store.get_manifest(forged.roles.treatment_contrast_ref)
    assert forged_manifest.inputs is not None
    assert len(forged_manifest.inputs) == 3
    assert forged_manifest.producer.component == scope._CANDIDATE_SCOPE_PRODUCER
    assert fresh.treatment_contrast.observed_arm_presence_status == "recomputed"
    with pytest.raises(
        HTEInputPreparationRefusal,
        match="candidate_scope_binding_recomputation_mismatch",
    ):
        _read(cas_root, forged, prepared, request)


def test_reader_rejects_valid_selected_profile_with_wrong_role_schema_and_correct_content(
    tmp_path: Path,
) -> None:
    from polisyos.foundry.data_plane import selected_row_candidate_scope as scope

    cas_root = tmp_path / "cas"
    store = FileSystemCAS(cas_root, ownership_enforced=False)
    source_ref = _put_source(store, _payload())
    prepared = _prepare(store, source_ref)
    request = _request_context()
    artifacts = _produce(store, prepared, request)
    fresh = _read(cas_root, artifacts, prepared, request)

    wrong_schema = SchemaInfo(
        name=scope.HTE_CANDIDATE_SCOPE_ROLE_SCHEMA.name,
        version="9.9",
    )
    wrong_schema_ref = _persist_selected_role(
        store,
        prepared,
        artifacts.binding_ref,
        fresh.outcome,
        schema=wrong_schema,
    )
    assert wrong_schema_ref.manifest_profile_sha256 is not None
    manifest = store.get_manifest(wrong_schema_ref)
    assert manifest.artifact_schema == wrong_schema
    assert manifest.inputs is not None
    assert len(manifest.inputs) == 3

    mixed_roles = artifacts.roles.model_copy(update={"outcome_ref": wrong_schema_ref})
    forged = artifacts.model_copy(update={"roles": mixed_roles})
    with pytest.raises(
        HTEInputPreparationRefusal,
        match="candidate_scope_artifact_identity_mismatch",
    ):
        _read(cas_root, forged, prepared, request)


def test_selected_scope_refs_reject_wrong_kind_and_media_type(tmp_path: Path) -> None:
    cas_root = tmp_path / "cas"
    store = FileSystemCAS(cas_root, ownership_enforced=False)
    source_ref = _put_source(store, _payload())
    prepared = _prepare(store, source_ref)
    request = _request_context()
    artifacts = _produce(store, prepared, request)

    invalid_payloads = (
        (
            SelectedHTECandidateScopeBindingRef,
            artifacts.binding_ref,
            "kind",
            "unrelated.kind",
        ),
        (
            SelectedHTECandidateScopeBindingRef,
            artifacts.binding_ref,
            "media_type",
            "application/octet-stream",
        ),
        (
            SelectedHTECandidateScopeRoleRef,
            artifacts.roles.outcome_ref,
            "kind",
            "unrelated.kind",
        ),
        (
            SelectedHTECandidateScopeRoleRef,
            artifacts.roles.outcome_ref,
            "media_type",
            "application/octet-stream",
        ),
    )
    for ref_type, ref, field_name, invalid_value in invalid_payloads:
        payload = ref.model_dump(mode="json")
        payload[field_name] = invalid_value
        with pytest.raises(ValidationError):
            ref_type.model_validate(payload, strict=True)


def test_selected_scope_ref_schema_defaults_match_runtime_kind_and_media_type(
    tmp_path: Path,
) -> None:
    cas_root = tmp_path / "cas"
    store = FileSystemCAS(cas_root, ownership_enforced=False)
    source_ref = _put_source(store, _payload())
    prepared = _prepare(store, source_ref)
    artifacts = _produce(store, prepared, _request_context())

    ref_contracts = (
        (
            SelectedHTECandidateScopeBindingRef,
            artifacts.binding_ref,
            "foundry.hte.selected_row_candidate_scope_binding",
        ),
        (
            SelectedHTECandidateScopeRoleRef,
            artifacts.roles.outcome_ref,
            "foundry.hte.selected_row_candidate_scope_role",
        ),
    )
    for ref_type, runtime_ref, expected_kind in ref_contracts:
        schema = ref_type.model_json_schema()
        properties = schema["properties"]
        assert runtime_ref.kind == expected_kind
        assert runtime_ref.media_type == "application/json"
        assert ref_type.model_fields["kind"].default == expected_kind
        assert properties["kind"]["default"] == expected_kind
        assert properties["kind"]["const"] == expected_kind
        assert ref_type.model_fields["media_type"].default == "application/json"
        assert properties["media_type"]["default"] == "application/json"
        assert properties["media_type"]["const"] == "application/json"
