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
