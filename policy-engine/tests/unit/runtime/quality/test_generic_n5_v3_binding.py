"""Strict generic N5 binding and historical-wire controls."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from enum import StrEnum
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from polisyos.core import canon
from polisyos.core.artifacts.manifest import ArtifactRef, CanonInfo
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.pdc import gy_content_hash
from polisyos.runtime.quality.cycle_substrate import CycleSubstrateContextOwnerError
from polisyos.runtime.quality.generation_cycle import (
    GenerationCycleRun,
    JointSimulationPort,
    SimulationPortObservation,
    _generic_n5_canonical_port_issue,
)
from polisyos.runtime.quality.generic_simulation_admission import (
    _N5_EXECUTION_V3_SCHEMA,
    _N5_TYPED_CANON,
    GenericCycleSimulationAdmissionOwner,
    GenericCycleSimulationN5ExecutionV2,
    GenericCycleSimulationN5ExecutionV3,
    GenericCycleSimulationN5RequestBindingV1,
    GenericCycleSimulationN5RequestBindingV2,
    _n5_typed_execution_content_hash,
    parse_generic_cycle_simulation_n5_execution,
)
from polisyos.runtime.quality.joint_simulation_horizon import JointSimulationRequest
from tests.unit.runtime.quality.test_joint_simulation_horizon import _request

_PRE_GENERIC_SCHEMAS = tuple(
    f"policyos.runtime.generation_cycle_controller.v{version}" for version in range(1, 6)
)
_GENERIC_FIELDS = tuple(
    field_name
    for field_name in SimulationPortObservation.model_fields
    if field_name.startswith("generic_")
)


def test_pre_v6_history_refuses_every_supplied_generic_field_even_when_null() -> None:
    """Old schemas cannot acquire generic input-only fields by default projection."""
    assert "generic_n5_request_binding" in _GENERIC_FIELDS
    assert SimulationPortObservation.model_fields["generic_n5_request_binding"].exclude is True
    for schema_version in _PRE_GENERIC_SCHEMAS:
        for field_name in _GENERIC_FIELDS:
            for supplied_value in (None, {"malformed": True}):
                payload = {
                    "schema_version": schema_version,
                    "cycles": [{"simulation": {field_name: supplied_value}}],
                }
                with pytest.raises(
                    ValidationError,
                    match="generation_cycle_pre_v6_cannot_carry_generic_simulation",
                ):
                    GenerationCycleRun.model_validate(payload)


def _artifact_ref(kind: str, digit: str) -> ArtifactRef:
    return ArtifactRef(
        artifact_id=f"sha256:{digit * 64}",
        kind=kind,
        media_type="application/json",
    )


def _execution_payload(
    *, request_binding: GenericCycleSimulationN5RequestBindingV1 | None
) -> dict[str, Any]:
    request = _request()
    payload: dict[str, Any] = {
        "schema_version": "policyos.runtime.generic_cycle_simulation_n5_execution.v2",
        "authority_purpose": "cycle_input_candidate_only",
        "status": "joint_simulated",
        "job_id": "job-test",
        "run_id": "run-test",
        "source_run_id": "source-run-test",
        "tenant_id": "tenant-test",
        "cell_id": "cell-test",
        "input_ref": _artifact_ref("runtime.quality.generic_cycle_simulation_n5_input", "1"),
        "result_ref": _artifact_ref("polisyos.runtime.joint_simulation_result", "2"),
        "n4_source_ref": _artifact_ref("runtime.generation_source_handoff", "3"),
        "n4_child_profile_family_ref": None,
        "n4_child_profile_set_ref": None,
        "context_job_ref": _artifact_ref("runtime.quality.cycle_substrate_context_job", "4"),
        "profile_ref": _artifact_ref("runtime.quality.generic_cycle_simulation_profile", "5"),
        "child_selection": None,
        "profile_selection_ref": "sha256:" + "6" * 64,
        "world_model_record_content_hash": request.world_model_record.content_hash,
        "candidate_id": "candidate-test",
        "candidate_atom_hash": "sha256:" + "7" * 64,
        "outcome_variable": request.selected_outcomes[0],
        "limitation_code": None,
    }
    if request_binding is not None:
        payload["request_binding"] = request_binding
    draft = GenericCycleSimulationN5ExecutionV2.model_construct(
        **payload,
        content_hash="sha256:" + "0" * 64,
    )
    normalized = draft.model_dump(mode="json", exclude={"content_hash"})
    return {**normalized, "content_hash": gy_content_hash(normalized)}


def test_generic_n5_execution_v2_requires_content_bound_full_request() -> None:
    """Historical V2 keeps its JSON-normalized Any request and remains readable."""
    request = _request()
    request_binding = GenericCycleSimulationN5RequestBindingV1(
        request=request,
        request_content_hash=gy_content_hash(request.model_dump(mode="json")),
    )
    parsed = GenericCycleSimulationN5ExecutionV2.model_validate(
        _execution_payload(request_binding=request_binding)
    )
    assert parsed.request_binding is not None
    legacy_request = JointSimulationRequest.model_validate(request.model_dump(mode="json"))
    assert parsed.request_binding.request == legacy_request
    assert parsed.request_binding.request != request
    assert parsed.request_binding.request_content_hash == request_binding.request_content_hash
    legacy_rate = parsed.request_binding.request.intervention_atoms[0].direct_effect_bundle.params[
        "rate"
    ]
    assert isinstance(legacy_rate, str)

    missing_binding = _execution_payload(request_binding=None)
    with pytest.raises(
        ValidationError,
        match="generic_cycle_simulation_n5_execution_request_binding_missing",
    ):
        GenericCycleSimulationN5ExecutionV2.model_validate(missing_binding)

    bad_binding = request_binding.model_dump(mode="json")
    bad_binding["request_content_hash"] = "sha256:" + "f" * 64
    with pytest.raises(
        ValidationError,
        match="generic_cycle_simulation_n5_request_content_hash_mismatch",
    ):
        GenericCycleSimulationN5RequestBindingV1.model_validate(bad_binding)


def _execution_v3_record(
    request_binding: GenericCycleSimulationN5RequestBindingV2,
) -> GenericCycleSimulationN5ExecutionV3:
    payload = _execution_payload(request_binding=None)
    assert payload.pop("request_binding", None) is None
    payload["schema_version"] = _N5_EXECUTION_V3_SCHEMA
    payload.pop("content_hash")
    draft = GenericCycleSimulationN5ExecutionV3.model_construct(
        **payload,
        request_binding=request_binding,
        content_hash="sha256:" + "0" * 64,
    )
    return GenericCycleSimulationN5ExecutionV3.model_validate(
        {
            **draft.model_dump(mode="python", exclude={"content_hash"}),
            "content_hash": _n5_typed_execution_content_hash(draft),
        }
    )


def test_v3_cas_roundtrip_preserves_typed_request_and_rejects_wrong_profile(
    tmp_path: Path,
) -> None:
    """Core CAS tags preserve Any-valued Decimal parameters and pin their canon profile."""
    request = _request()
    rate = request.intervention_atoms[0].direct_effect_bundle.params["rate"]
    assert isinstance(rate, Decimal)

    binding = GenericCycleSimulationN5RequestBindingV2.from_request(request)
    reopened_binding = GenericCycleSimulationN5RequestBindingV2.model_validate(
        canon.from_canonical_bytes(canon.to_canonical_bytes(binding, _N5_TYPED_CANON))
    )
    assert reopened_binding == binding
    assert isinstance(
        reopened_binding.request.intervention_atoms[0].direct_effect_bundle.params["rate"],
        Decimal,
    )

    string_atom = request.intervention_atoms[0].model_copy(
        update={
            "direct_effect_bundle": request.intervention_atoms[0].direct_effect_bundle.model_copy(
                update={"params": {"rate": str(rate)}}
            )
        }
    )
    string_request = request.model_copy(
        update={"intervention_atoms": (string_atom, *request.intervention_atoms[1:])}
    )
    string_binding = GenericCycleSimulationN5RequestBindingV2.from_request(string_request)
    assert string_binding.request_content_hash != binding.request_content_hash

    tag_map_atom = request.intervention_atoms[0].model_copy(
        update={
            "direct_effect_bundle": request.intervention_atoms[0].direct_effect_bundle.model_copy(
                update={"params": {"rate": {"_type": "decimal", "value": "0.20"}}}
            )
        }
    )
    tag_map_request = request.model_copy(
        update={"intervention_atoms": (tag_map_atom, *request.intervention_atoms[1:])}
    )
    with pytest.raises(
        ValueError,
        match="generic_cycle_simulation_n5_request_canonical_roundtrip_mismatch",
    ):
        GenericCycleSimulationN5RequestBindingV2.from_request(tag_map_request)

    legacy_request = request.model_dump(mode="json")
    legacy_rate = legacy_request["intervention_atoms"][0]["direct_effect_bundle"]["params"]["rate"]
    assert isinstance(legacy_rate, str)
    assert JointSimulationRequest.model_validate(legacy_request) != request

    record = _execution_v3_record(binding)
    store = FileSystemCAS(tmp_path / "cas")
    owner = GenericCycleSimulationAdmissionOwner(profiles=(), store=store)
    options = owner._n5_execution_write_options(record)
    ref = store.put_json(
        record.model_dump(mode="python"),
        options,
        canon_spec=_N5_TYPED_CANON,
    )
    reopened = parse_generic_cycle_simulation_n5_execution(
        canon.from_canonical_bytes(store.get_bytes(ref))
    )
    assert type(reopened) is GenericCycleSimulationN5ExecutionV3
    assert reopened == record
    assert isinstance(
        reopened.request_binding.request.intervention_atoms[0].direct_effect_bundle.params["rate"],
        Decimal,
    )
    assert owner._manifest_matches_record(store.get_manifest(ref), ref, options)

    wrong_canon = canon.CanonSpec(forbid_floats=False)
    wrong_options = replace(options, canon=CanonInfo.from_spec(wrong_canon))
    wrong_ref = store.put_json(
        record.model_dump(mode="python"),
        wrong_options,
        canon_spec=wrong_canon,
    )
    with pytest.raises(
        CycleSubstrateContextOwnerError,
        match="generic_cycle_simulation_n5_execution_manifest_mismatch",
    ):
        owner.resolve_n5_execution(wrong_ref, expected=record)

    with pytest.raises(
        ValueError,
        match="generic_cycle_simulation_input_integrity_failed",
    ):
        owner.resolve_n5_execution(ref, expected=record)


def test_v3_request_roundtrip_refuses_loss_across_the_complete_any_graph() -> None:
    """Open Any values must survive the actual typed request codec without loss."""
    request = _request()

    class CustomStringKey(str):
        pass

    class StringKeyEnum(StrEnum):
        TYPED = "typed-key"

    unsupported_roundtrips = (
        request.model_copy(
            update={"world_credal_state_before": {"ordered_values": ("low", "high")}}
        ),
        request.model_copy(
            update={"world_credal_state_before": {"embedded_model": request.horizon}}
        ),
        request.model_copy(update={"world_credal_state_before": {"negative_zero": -0.0}}),
        request.model_copy(
            update={
                "world_credal_state_before": {
                    "non_utc_datetime": datetime(
                        2026, 10, 11, 12, tzinfo=timezone(timedelta(hours=2))
                    )
                }
            }
        ),
        request.model_copy(
            update={"world_credal_state_before": {"naive_datetime": datetime(2026, 10, 11, 12)}}
        ),
        request.model_copy(
            update={
                "world_credal_state_before": {"nested": {CustomStringKey("typed-key"): "value"}}
            }
        ),
        request.model_copy(
            update={"world_credal_state_before": {"nested": {StringKeyEnum.TYPED: "value"}}}
        ),
    )
    for candidate in unsupported_roundtrips:
        with pytest.raises(
            ValueError,
            match="generic_cycle_simulation_n5_request_canonical_roundtrip_mismatch",
        ):
            GenericCycleSimulationN5RequestBindingV2.from_request(candidate)

    plain_string_request = request.model_copy(
        update={"world_credal_state_before": {"nested": {"typed-key": "value"}}}
    )
    plain_string_binding = GenericCycleSimulationN5RequestBindingV2.from_request(
        plain_string_request
    )
    retained_keys = plain_string_binding.request.world_credal_state_before["nested"].keys()
    assert list(retained_keys) == ["typed-key"]
    assert all(type(key) is str for key in retained_keys)

    unsupported_value = request.model_copy(
        update={"world_credal_state_before": {"unsupported_set": {"left", "right"}}}
    )
    with pytest.raises(
        ValueError,
        match="generic_cycle_simulation_n5_request_canonical_roundtrip_invalid",
    ):
        GenericCycleSimulationN5RequestBindingV2.from_request(unsupported_value)

    unsupported_object = request.model_copy(
        update={"world_credal_state_before": {"unsupported_object": object()}}
    )
    with pytest.raises(
        ValueError,
        match="generic_cycle_simulation_n5_request_canonical_roundtrip_invalid",
    ):
        GenericCycleSimulationN5RequestBindingV2.from_request(unsupported_object)


def test_v3_binding_rejects_tampered_hash_profile_and_unknown_execution_version() -> None:
    """A typed binding cannot be detached from its request or declared canon profile."""
    binding = GenericCycleSimulationN5RequestBindingV2.from_request(_request())
    tampered = binding.model_dump(mode="python")
    tampered["request_content_hash"] = "sha256:" + "f" * 64
    with pytest.raises(
        ValidationError,
        match="generic_cycle_simulation_n5_request_content_hash_mismatch",
    ):
        GenericCycleSimulationN5RequestBindingV2.model_validate(tampered)

    wrong_profile = binding.model_dump(mode="python")
    wrong_profile["canon_profile_id"] = "polisyos.core.canon.json@0.2.0:sha256:" + "0" * 64
    with pytest.raises(ValidationError):
        GenericCycleSimulationN5RequestBindingV2.model_validate(wrong_profile)

    with pytest.raises(
        ValueError,
        match="generic_cycle_simulation_n5_execution_schema_unsupported",
    ):
        parse_generic_cycle_simulation_n5_execution(
            {"schema_version": "policyos.runtime.generic_cycle_simulation_n5_execution.v99"}
        )


def test_generic_n5_rejects_instance_shadowing_of_canonical_port() -> None:
    """A test/custom callable cannot pass as the runtime N5 producer."""
    port = JointSimulationPort()

    def shadowed_call(**_kwargs: object) -> None:
        return None

    port.__dict__["__call__"] = shadowed_call
    issue = _generic_n5_canonical_port_issue(
        port,
        owner=object(),  # type: ignore[arg-type]
        handoff=object(),  # type: ignore[arg-type]
        child_selection=None,
        child_set_ref=None,
        artifact_store=object(),  # type: ignore[arg-type]
        cycle_substrate_context=None,
    )
    if issue != "generic_cycle_simulation_canonical_n5_port_required":
        pytest.fail("N5 refused to reject the instance-shadowed port")


def test_generic_request_binding_without_source_refs_cannot_enter_n8() -> None:
    """A detached request marker is not a generic source chain."""
    request = _request()
    binding = GenericCycleSimulationN5RequestBindingV1(
        request=request,
        request_content_hash=gy_content_hash(request.model_dump(mode="json")),
    )
    with pytest.raises(
        ValidationError,
        match="generic_cycle_simulation_request_binding_without_source_refs",
    ):
        SimulationPortObservation(
            candidate_id="candidate-test",
            status="joint_simulated",
            generic_n5_request_binding=binding,
        )


@pytest.mark.parametrize(
    ("tenant_id", "cell_id", "expected_scope_error"),
    [
        ("tenant-scoped", "generic-n5-replay-cell", None),
        (
            "tenant-foreign",
            "generic-n5-replay-cell",
            "generation_source_owner_profile_mismatch",
        ),
        (
            "tenant-scoped",
            "cell-foreign",
            "generation_source_owner_profile_mismatch",
        ),
    ],
)
def test_generic_n5_execution_replay_loads_the_actual_source_in_scope(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    tenant_id: str,
    cell_id: str,
    expected_scope_error: str | None,
) -> None:
    """N5 replay opens real N4 CAS bytes under the persisted tenant/cell identity."""
    from dataclasses import replace

    from polisyos.runtime.quality import design_generation as n4
    from polisyos.runtime.quality.cycle_substrate import (
        cycle_job_design_problem_ref,
        cycle_job_profile_selection_ref,
    )
    from polisyos.runtime.quality.generation_source import (
        GenerationSourceHandoff,
        GenerationSourceRepository,
    )
    from polisyos.runtime.quality.generic_simulation_admission import (
        GenericCycleSimulationN5ExecutionV1,
        GenericCycleSimulationN5InputV1,
    )
    from tests.unit.runtime.quality.test_cycle_substrate import _cycle_context
    from tests.unit.runtime.quality.test_design_generation import _test_design_problem

    problem = _test_design_problem()
    context = _cycle_context(
        domain=problem.domain,
        design_problem_ref=cycle_job_design_problem_ref(problem),
    )
    context_job_ref = _artifact_ref("runtime.quality.cycle_substrate_context_job", "1")
    profile_ref = _artifact_ref("runtime.quality.generic_cycle_simulation_profile", "2")
    store = FileSystemCAS(tmp_path / "generic-n5-replay-source-cas")
    run_id = "generic-n5-replay-run"
    source_run_id = "generic-n5-replay-source-run"
    job_id = "generic-n5-replay-job"
    source_cell_id = "generic-n5-replay-cell"
    source_tenant_id = "tenant-scoped"
    result = n4.GenerationUnderAResult(
        status="generation_unavailable",
        design_problem_ref=cycle_job_design_problem_ref(problem),
        model_id="synthetic-c2",
        preflight=n4.ModelProfilePreflight(
            status="gateway_unavailable",
            model_id="synthetic-c2",
        ),
        diversity_report=n4.GenerationDiversityReport(
            min_required=1,
            candidate_count=0,
            unique_diversity_key_count=0,
        ),
    )
    source_ref = GenerationSourceRepository(store).persist_ref(
        run_id=source_run_id,
        cycle_index=0,
        problem=problem,
        organ=replace(result.as_organ_run(), cycle_substrate_context=context),
        execution_scope="contract_testing",
        job_id=job_id,
        expected_run_id=run_id,
        tenant_id=source_tenant_id,
        cell_id=source_cell_id,
        context_job_ref=context_job_ref,
        profile_ref=profile_ref,
    )
    input_record = GenericCycleSimulationN5InputV1.model_construct(
        job_id=job_id,
        run_id=run_id,
        source_run_id=source_run_id,
        tenant_id=tenant_id,
        cell_id=cell_id,
        design_problem_ref=cycle_job_design_problem_ref(problem),
        cycle_index=0,
        n4_source_ref=source_ref,
        n4_child_profile_family_ref=None,
        n4_child_profile_set_ref=None,
        child_selection=None,
        context_job_ref=context_job_ref,
        profile_ref=profile_ref,
        profile=object(),
        candidate_id="candidate_0123456789abcdef",
        candidate_atom_hash="sha256:" + "3" * 64,
        outcome_variable="controlled-outcome",
        n5=object(),
        content_hash="sha256:" + "4" * 64,
    )
    record = GenericCycleSimulationN5ExecutionV1.model_construct(
        status="simulation_blocked",
        job_id=job_id,
        run_id=run_id,
        source_run_id=source_run_id,
        tenant_id=tenant_id,
        cell_id=cell_id,
        input_ref=_artifact_ref("runtime.quality.generic_cycle_simulation_n5_input", "5"),
        result_ref=None,
        n4_source_ref=source_ref,
        n4_child_profile_family_ref=None,
        n4_child_profile_set_ref=None,
        child_selection=None,
        context_job_ref=context_job_ref,
        profile_ref=profile_ref,
        profile_selection_ref=cycle_job_profile_selection_ref(problem),
        world_model_record_content_hash=context.world_model_record.content_hash,
        candidate_id=input_record.candidate_id,
        candidate_atom_hash=input_record.candidate_atom_hash,
        outcome_variable=input_record.outcome_variable,
        limitation_code="controlled-source-load-test",
        content_hash="sha256:" + "6" * 64,
    )
    owner = GenericCycleSimulationAdmissionOwner(profiles=(), store=store)

    class _AfterSourceLoadError(Exception):
        pass

    def stop_after_source_load(*_args: object, **_kwargs: object) -> object:
        raise _AfterSourceLoadError

    monkeypatch.setattr(owner, "resolve_profile_historical", stop_after_source_load)
    observed_loads: list[dict[str, object]] = []
    original_load = GenerationSourceRepository.load

    def recording_load(
        repository: GenerationSourceRepository,
        ref: ArtifactRef | str,
        *,
        run_id: str,
        expected_run_id: str | None = None,
        expected_job_id: str | None = None,
        expected_tenant_id: str | None = None,
        expected_cell_id: str | None = None,
        context_job_ref: ArtifactRef | None = None,
        profile_ref: ArtifactRef | None = None,
        n4_child_profile_family_ref: ArtifactRef | None = None,
    ) -> GenerationSourceHandoff:
        observed_loads.append(
            {
                "expected_tenant_id": expected_tenant_id,
                "expected_cell_id": expected_cell_id,
            }
        )
        return original_load(
            repository,
            ref,
            run_id=run_id,
            expected_run_id=expected_run_id,
            expected_job_id=expected_job_id,
            expected_tenant_id=expected_tenant_id,
            expected_cell_id=expected_cell_id,
            context_job_ref=context_job_ref,
            profile_ref=profile_ref,
            n4_child_profile_family_ref=n4_child_profile_family_ref,
        )

    monkeypatch.setattr(GenerationSourceRepository, "load", recording_load)

    if expected_scope_error is None:
        with pytest.raises(_AfterSourceLoadError):
            owner._replay_n5_execution_sources(record, input_record)
    else:
        with pytest.raises(ValueError, match=expected_scope_error):
            owner._replay_n5_execution_sources(record, input_record)

    assert len(observed_loads) == 1
    assert observed_loads[0]["expected_tenant_id"] == tenant_id
    assert observed_loads[0]["expected_cell_id"] == cell_id


def test_generic_profile_join_refuses_v5_context_without_exact_selected_ncm_view(
    tmp_path: Path,
) -> None:
    """A current V5 source context joins only to its exact immutable N5 profile."""

    from polisyos.core.artifacts import ensure_ir_artifact_store
    from polisyos.core.artifacts.manifest import ArtifactRef
    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.ir.analytics.ncm import (
        candidate_ncm_spec_from_declaration,
        persist_ncm_spec,
    )
    from polisyos.pdc import gy_content_hash
    from polisyos.runtime.quality.candidate_simulation import (
        CandidateSimulationContextInputs,
        CandidateSimulationSyntheticModelDeclarationV1,
    )
    from polisyos.runtime.quality.cycle_substrate import (
        CandidateLeverEvidence,
        build_candidate_cycle_substrate_context,
        cycle_job_profile_selection_ref,
    )
    from polisyos.runtime.quality.generic_simulation_admission import (
        GenericCycleN5RequestProfileV1,
        GenericCycleSimulationProfileV1,
    )
    from polisyos.runtime.quality.joint_simulation_horizon import HorizonSpec
    from polisyos.runtime.quality.substrate_registry import persist_substrate_registry
    from polisyos.runtime.quality.world_model_record import (
        derive_candidate_scenario_world_model_record,
        persist_world_model_record,
        world_model_artifact_views,
    )
    from tests._helpers.candidate_cycle_source_profile import (
        build_candidate_cycle_substrate_owner_fixture,
    )

    def hash_model(model_type: type[Any], fields: dict[str, Any]) -> Any:
        draft = model_type.model_construct(
            **fields,
            content_hash="sha256:" + "0" * 64,
        )
        body = draft.model_dump(mode="json", exclude={"content_hash"})
        return model_type.model_validate({**body, "content_hash": gy_content_hash(body)})

    fixture = build_candidate_cycle_substrate_owner_fixture(tmp_path)
    seed_context = fixture.context
    problem = fixture.resolved_context_job.problem
    tenant_id = "tenant-candidate-source-profile-fixture"
    cell_id = "cell-candidate-source-profile-fixture"
    with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
        registry_ref = persist_substrate_registry(
            fixture.artifact_store,
            seed_context.substrate_registry,
        )
    declaration_fields = {
        "profile_config_ref": "runtime-config:b27-v5-n5-composition",
        "profile_content_hash": gy_content_hash("controlled-v5-profile"),
        "profile_selection_ref": cycle_job_profile_selection_ref(problem),
        "target_world_slot": problem.candidate_lever_space.candidate_levers[0].target_slot,
        "outcome_variable": problem.outcome_of_interest.target_variable,
        "target_unit_id": "controlled_target_unit",
        "outcome_unit_id": "controlled_outcome_unit",
        "target_baseline": 0.0,
        "outcome_baseline": 0.0,
        "outcome_per_target_unit": 0.5,
        "outcome_noise_stddev": 0.01,
        "assumption": "declared_candidate_scm_not_empirically_grounded",
    }
    declaration = hash_model(CandidateSimulationSyntheticModelDeclarationV1, declaration_fields)
    ncm = candidate_ncm_spec_from_declaration(declaration)
    with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
        ncm_ref = ArtifactRef.model_validate(
            persist_ncm_spec(ensure_ir_artifact_store(fixture.artifact_store), ncm).model_dump(
                mode="python"
            )
        )
        world = derive_candidate_scenario_world_model_record(
            seed_context.world_model_record,
            ncm_artifact_ref=ncm_ref,
            declaration_content_hash=declaration.content_hash,
            substrate_registry_view_ref=registry_ref,
        )
        world_ref = persist_world_model_record(fixture.artifact_store, world)
    views = world_model_artifact_views(world)
    assert views.substrate_registry_ref == registry_ref
    assert views.ncm_refs == (ncm_ref,)

    context = build_candidate_cycle_substrate_context(
        fixture.root,
        problem=problem,
        world_model_record=world,
        substrate_registry=seed_context.substrate_registry,
    )
    assert context.source_profile is not None
    assert context.source_profile.source_currentness_status == "not_established"
    assert context.candidate_levers

    def build_profile(
        *,
        candidate_levers: tuple[CandidateLeverEvidence, ...] = (),
        selected_ncm_ref: ArtifactRef = ncm_ref,
        context_inputs_override: CandidateSimulationContextInputs | None = None,
    ) -> GenericCycleSimulationProfileV1:
        inputs = context_inputs_override or CandidateSimulationContextInputs(
            substrate_registry=context.substrate_registry,
            selected_registry_entry_hashes=context.selected_registry_entry_hashes,
            world_model_record=world,
            intervention_substrate=context.intervention_substrate,
            candidate_levers=candidate_levers,
            transport_context=None,
            source_pack_content_hash=gy_content_hash("reusable-profile-source-pack"),
            substrate_input_content_hash=gy_content_hash("reusable-profile-substrate-input"),
        )
        fields = {
            "profile_id": "generic-profile-v5-composition-test",
            "profile_selection_ref": cycle_job_profile_selection_ref(problem),
            "profile_selection_kind": "problem",
            "world_model_record_ref": world_ref,
            "substrate_registry_ref": registry_ref,
            "selected_ncm_ref": selected_ncm_ref,
            "context_inputs": inputs,
            "n5": GenericCycleN5RequestProfileV1(
                budget_ref="budget://profile-join-test",
                horizon=HorizonSpec(start=0, end=0, step=1),
                baseline_state={problem.outcome_of_interest.target_variable: 0.0},
            ),
            "limitations": (
                "controlled_inputs_only",
                "currentness_not_established",
                "n5_simulation_not_world_evidence",
                "n9_not_admitted",
                "s8_blocked",
                "source_truth_not_established",
            ),
        }
        return hash_model(GenericCycleSimulationProfileV1, fields)

    profile = build_profile()
    assert (
        context.substrate_input_content_hash != profile.context_inputs.substrate_input_content_hash
    )
    assert context.source_pack_content_hash != profile.context_inputs.source_pack_content_hash
    assert GenericCycleSimulationAdmissionOwner.context_matches_profile(context, profile, problem)

    # A declared generic row has a different context binding and cannot be
    # silently replaced by the source owner's cycle-bound row.
    generic_context = GenericCycleSimulationAdmissionOwner.context_for_profile(profile, problem)
    current_row = context.candidate_levers[0]
    declared_row = current_row.model_copy(
        update={
            "context_binding_hash": generic_context.context_binding_hash,
            "substrate_input_content_hash": generic_context.substrate_input_content_hash,
        }
    )
    declared_profile = build_profile(candidate_levers=(declared_row,))
    assert not GenericCycleSimulationAdmissionOwner.context_matches_profile(
        context,
        declared_profile,
        problem,
    )
    changed_ncm = ArtifactRef.model_validate(
        {
            **ncm_ref.model_dump(mode="python"),
            "artifact_id": "sha256:" + "9" * 64,
        }
    )
    assert not GenericCycleSimulationAdmissionOwner.context_matches_profile(
        context,
        build_profile(selected_ncm_ref=changed_ncm),
        problem,
    )
    mismatched_l6_inputs = profile.context_inputs.model_copy(
        update={"intervention_substrate": None}
    )
    assert not GenericCycleSimulationAdmissionOwner.context_matches_profile(
        context,
        build_profile(context_inputs_override=mismatched_l6_inputs),
        problem,
    )

    revised_problem = problem.model_copy(
        update={
            "runtime_hints": {
                **problem.runtime_hints,
                "generation_cycle_grammar": ("seed", "counterexample_driven"),
                "generation_cycle_revision": {"revision_strategy": "counterexample"},
            }
        }
    )
    assert cycle_job_profile_selection_ref(revised_problem) == profile.profile_selection_ref
    assert not GenericCycleSimulationAdmissionOwner.context_matches_profile(
        context,
        profile,
        revised_problem,
    )
    revised_context = build_candidate_cycle_substrate_context(
        fixture.root,
        problem=revised_problem,
        world_model_record=context.world_model_record,
        substrate_registry=context.substrate_registry,
    )
    assert revised_context.design_problem_ref != context.design_problem_ref
    assert revised_context.substrate_input_content_hash != context.substrate_input_content_hash
    assert revised_context.candidate_levers != context.candidate_levers
    from polisyos.runtime.quality.generation_cycle import (
        _cycle_substrate_revision_scope_projection,
    )

    assert _cycle_substrate_revision_scope_projection(revised_context) == (
        _cycle_substrate_revision_scope_projection(context)
    )
    assert GenericCycleSimulationAdmissionOwner.context_matches_profile(
        revised_context,
        profile,
        revised_problem,
    )
    assert not GenericCycleSimulationAdmissionOwner.context_matches_profile(
        revised_context,
        declared_profile,
        revised_problem,
    )


def test_generic_owner_join_distinguishes_selected_mismatch_from_unknown_replay(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A selected record cannot be paired with another cycle or result reference."""
    from polisyos.runtime.quality.generic_simulation_admission import (
        GenericN5ExecutionJoinExpectation,
    )

    binding = GenericCycleSimulationN5RequestBindingV2.from_request(_request())
    original = _execution_v3_record(binding)
    selected_input = original.input_ref.model_copy(
        update={"manifest_profile_sha256": "sha256:" + "a" * 64}
    )
    assert original.result_ref is not None
    selected_result = original.result_ref.model_copy(
        update={"manifest_profile_sha256": "sha256:" + "b" * 64}
    )
    draft = original.model_copy(update={"input_ref": selected_input, "result_ref": selected_result})
    record = GenericCycleSimulationN5ExecutionV3.model_validate(
        {
            **draft.model_dump(mode="python", exclude={"content_hash"}),
            "content_hash": _n5_typed_execution_content_hash(draft),
        }
    )
    store = FileSystemCAS(tmp_path / "typed-owner-join")
    owner = GenericCycleSimulationAdmissionOwner(profiles=(), store=store)
    ref = store.put_json(
        record.model_dump(mode="python"),
        owner._n5_execution_write_options(record),
        canon_spec=_N5_TYPED_CANON,
        return_selected_profile=True,
    )
    expectation = GenericN5ExecutionJoinExpectation(
        input_ref=record.input_ref,
        result_ref=record.result_ref,
        status=record.status,
        n4_source_ref=record.n4_source_ref,
        context_job_ref=record.context_job_ref,
        profile_ref=record.profile_ref,
        child_family_ref=record.n4_child_profile_family_ref,
        child_set_ref=record.n4_child_profile_set_ref,
        profile_selection_ref=record.profile_selection_ref,
        design_problem_ref="sha256:" + "f" * 64,
        outcome_variable=record.outcome_variable,
        cycle_index=0,
        candidate_id=record.candidate_id,
        candidate_atom_hash=record.candidate_atom_hash,
        world_model_record_content_hash=record.world_model_record_content_hash,
        job_id=record.job_id,
        run_id=record.run_id,
        source_run_id=record.source_run_id,
        tenant_id=record.tenant_id,
        cell_id=record.cell_id,
    )
    for change in (
        {"job_id": "foreign-job"},
        {"run_id": "foreign-run"},
        {"candidate_id": "foreign-candidate"},
        {"tenant_id": "foreign-tenant"},
        {
            "input_ref": ArtifactRef.model_validate(
                {**selected_input.model_dump(mode="json"), "artifact_id": "sha256:" + "c" * 64}
            )
        },
        {
            "result_ref": ArtifactRef.model_validate(
                {**selected_result.model_dump(mode="json"), "artifact_id": "sha256:" + "d" * 64}
            )
        },
    ):
        outcome = owner.resolve_n5_execution_join(
            ref, expected=expectation.model_copy(update=change)
        )
        if "tenant_id" in change:
            assert outcome.status == "invalid"
            assert outcome.code == "generic_n5_execution_scope_refused"
        else:
            assert outcome.status == "mismatch"
        assert outcome.execution is None

    missing = ArtifactRef.model_validate(
        {**ref.model_dump(mode="json"), "artifact_id": "sha256:" + "e" * 64}
    )
    assert owner.resolve_n5_execution_join(missing, expected=expectation).status == "unavailable"
    # A structurally correct record with unavailable dependencies is not proof
    # that the full owner replay succeeded.
    unknown = owner.resolve_n5_execution_join(ref, expected=expectation)
    assert unknown.status in {"unavailable", "not_established"}
    assert unknown.execution is None

    from polisyos.core.artifacts import ArtifactOwnershipError
    from polisyos.core.artifacts.ownership import (
        ArtifactPublicReadClosureUnavailableError,
        ArtifactReadOnlyUnavailableError,
        ArtifactTransactionPendingError,
    )

    errors = (
        (ArtifactReadOnlyUnavailableError("source unavailable"), "unavailable"),
        (
            ArtifactTransactionPendingError(record.input_ref.artifact_id, surface="manifest"),
            "unavailable",
        ),
        (ArtifactPublicReadClosureUnavailableError("record", operation="read"), "unavailable"),
    )
    for error, expected_status in errors:

        def refuse_manifest(*args: Any, _error: Exception = error, **kwargs: Any) -> bytes:
            del args, kwargs
            raise _error

        with monkeypatch.context() as scope:
            scope.setattr(store, "get_raw_manifest_bytes", refuse_manifest)
            observed = owner.resolve_n5_execution_join(ref, expected=expectation)
        assert observed.status == expected_status
        assert observed.execution is None

    from polisyos.runtime.http.errors import RuntimeDependencyUnavailableError

    # The actual owner refusal, including an explicit backend wrapper, is never
    # converted to an invalid/unavailable join. Typed owner unavailability is
    # still a candidate limitation despite being an ownership-error subtype.
    for cause in (
        ArtifactOwnershipError("foreign tenant"),
        PermissionError("backing store permission"),
        ArtifactReadOnlyUnavailableError("source unavailable"),
    ):

        def wrapped_manifest(*args: Any, _cause: Exception = cause, **kwargs: Any) -> bytes:
            del args, kwargs
            raise RuntimeDependencyUnavailableError("backend") from _cause

        with monkeypatch.context() as scope:
            scope.setattr(store, "get_raw_manifest_bytes", wrapped_manifest)
            if isinstance(cause, ArtifactReadOnlyUnavailableError):
                assert owner.resolve_n5_execution_join(ref, expected=expectation).status == (
                    "unavailable"
                )
            else:
                with pytest.raises(type(cause)) as refusal:
                    owner.resolve_n5_execution_join(ref, expected=expectation)
                assert refusal.value is cause


def test_n8_input_read_distinguishes_wrapped_owner_denial_from_unavailability() -> None:
    """N8 preserves a selected input refusal before its owner join is available."""
    from types import SimpleNamespace

    from polisyos.core.artifacts import ArtifactOwnershipError
    from polisyos.core.artifacts.ownership import ArtifactReadOnlyUnavailableError
    from polisyos.runtime.http.errors import RuntimeDependencyUnavailableError
    from polisyos.runtime.quality.generation_cycle import _generic_n5_observation_refusal

    marker = object()
    simulation = SimpleNamespace(
        generic_n4_source_ref=marker,
        generic_context_job_ref=marker,
        generic_profile_ref=marker,
        generic_n4_child_profile_family_ref=None,
        generic_n4_child_profile_set_ref=None,
        generic_n5_input_ref=marker,
        generic_n5_execution_ref=marker,
        generic_profile_selection_ref=marker,
        generic_n5_request_binding=None,
    )

    class RefusingOwner:
        def __init__(self, cause: Exception) -> None:
            self.cause = cause

        def get_raw_manifest_bytes(self, _ref: object) -> bytes:
            raise RuntimeDependencyUnavailableError("backend") from self.cause

        def get_manifest(self, _ref: object) -> object:
            raise AssertionError("raw selected view failed before typed manifest")

        def get_bytes(self, _ref: object) -> bytes:
            raise AssertionError("raw selected view failed before payload")

    def read(cause: Exception) -> str | None:
        return _generic_n5_observation_refusal(
            simulation=simulation,  # type: ignore[arg-type]
            candidate=object(),
            problem=object(),  # type: ignore[arg-type]
            world_model_record_content_hash="sha256:" + "0" * 64,
            artifact_store=RefusingOwner(cause),  # type: ignore[arg-type]
            cycle_index=0,
            handoff=None,
            child_selection=None,
            verified_scope=None,
            source_run_id=None,
        )

    assert read(ArtifactOwnershipError("owner denied")) == (
        "generic_cycle_simulation_artifact_scope_refused"
    )
    assert read(ArtifactReadOnlyUnavailableError("source unavailable")) == (
        "n5_execution_request_provenance_not_established"
    )
    with pytest.raises(PermissionError):
        read(PermissionError("filesystem permission"))
    unavailable = ArtifactReadOnlyUnavailableError("reader unavailable")
    unavailable.__cause__ = ArtifactOwnershipError("nested owner denial")
    assert read(unavailable) == "generic_cycle_simulation_artifact_scope_refused"
    unavailable.__cause__ = PermissionError("nested filesystem permission")
    with pytest.raises(PermissionError):
        read(unavailable)
