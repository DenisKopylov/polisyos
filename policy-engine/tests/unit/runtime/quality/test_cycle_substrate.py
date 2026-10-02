from __future__ import annotations

import hashlib
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

import pytest
from pydantic import create_model

from polisyos.core import canon
from polisyos.core.artifacts import ArtifactOwnershipError, FileSystemCAS
from polisyos.core.security import (
    AccessScope,
    reset_current_access_scope,
    set_current_access_scope,
    tenant_scope,
)
from polisyos.pdc import gy_content_hash
from polisyos.runtime.quality import cycle_substrate as cycle_substrate_owner
from polisyos.runtime.quality.cycle_substrate import (
    CandidateLeverEvidence,
    CycleSubstrateContext,
    CycleSubstrateContextArtifactOwner,
    CycleSubstrateContextJobArtifact,
    CycleSubstrateContextOwnerError,
    TransportContextEvidence,
    TransportCovariateObservation,
    build_cycle_substrate_context,
    cycle_substrate_context_binding_hash,
    cycle_substrate_context_content_hash,
)
from polisyos.runtime.quality.design_problem import (
    DESIGN_PROBLEM_V3_SCHEMA_VERSION,
    DesignProblem,
    OutcomeOfInterest,
    _QualifiedOutcomeOfInterestV3,
)
from polisyos.runtime.quality.intervention_substrate import (
    InterventionSubstrateBundle,
    InterventionSubstrateError,
    resolve_intervention_lever,
    resolve_law_bound_lever,
    route_observation_family_method,
)
from polisyos.runtime.quality.substrate_registry import (
    SubstrateCoverage,
    SubstrateLayer,
    SubstrateRegistration,
    SubstrateRegistry,
    SubstrateSchemaRegime,
    SubstrateTrustTier,
    build_substrate_registry,
    build_substrate_registry_entry,
)
from polisyos.runtime.quality.world_model_record import (
    BranchMode,
    DataForgeBindingRef,
    FabricWorldRef,
    FoundryBindingRef,
    PolicySlotBinding,
    ResolvedSubstrateEntryRef,
    SimulationModelRef,
    SkgCausalPriorRef,
    SubstrateRegistryRef,
    WorldModelRecord,
    WorldModelRecordError,
    world_model_record_content_hash,
)


def _hash(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


@contextmanager
def _authenticated_tenant_scope(
    *, tenant_id: str, cell_id: str
) -> Iterator[None]:
    scope = AccessScope.for_service(
        tenant_id=tenant_id,
        cell_id=cell_id,
        spiffe_id="spiffe://tests/policyos/cycle-substrate-owner",
    )
    token = set_current_access_scope(scope)
    try:
        with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
            yield
    finally:
        reset_current_access_scope(token)


def _design_problem() -> DesignProblem:
    return DesignProblem.model_validate(
        {
            "schema_version": "policyos.runtime.design_problem.v2",
            "design_problem_id": "education_budget_design",
            "problem_statement": "Improve public school learning outcomes.",
            "domain": "education",
            "nl_provenance": {
                "raw_request": "Improve public school learning outcomes.",
                "source_surface": "runtime.control.nl_request",
            },
            "authority_profile": {
                "requester_authority": "research",
                "requested_authority_level": "research",
                "mandate": "Research-only candidate generation.",
            },
            "jurisdiction_time": {
                "region": "UA",
                "valid_time": "2025",
                "as_of": "2025-12-31",
                "policy_time": "2025",
                "data_time": "2024/2025",
            },
            "objectives": [
                {
                    "objective_id": "improve_learning",
                    "description": "Improve learning outcomes.",
                    "metric_id": "learning_outcomes",
                }
            ],
            "stakeholders": [
                {"stakeholder_id": "students", "name": "Students"}
            ],
            "outcome_of_interest": {
                "target_variable": "learning_outcomes",
                "metric_id": "learning_outcomes",
                "estimand": "P(learning_outcomes | do(teaching_method))",
            },
            "candidate_lever_space": {
                "allowed_operator_kinds": ["teaching_method"],
                "candidate_levers": [
                    {
                        "lever_id": "teaching_method",
                        "operator_kind": "teaching_method",
                        "instrument": "teaching method",
                        "target_slot": "education.teaching_method",
                    }
                ],
            },
            "evidence_acquisition_needs": {"needs": []},
        }
    )


def _qualified_v3_design_problem() -> DesignProblem:
    """Return a current problem whose dotted outcome uses its exact owner type."""

    payload = _design_problem().model_dump(mode="python")
    payload["schema_version"] = DESIGN_PROBLEM_V3_SCHEMA_VERSION
    payload["outcome_of_interest"] = {
        "target_variable": "education.learning_outcomes",
        "metric_id": "learning_outcomes",
        "estimand": "P(learning_outcomes | do(teaching_method))",
        "direction": "maximize",
    }
    problem = DesignProblem.model_validate(payload)
    assert type(problem.outcome_of_interest) is _QualifiedOutcomeOfInterestV3
    return problem


def test_current_cycle_job_refs_preserve_plain_v3_projection_and_support_qualified_v3() -> None:
    """Current identity dispatch keeps old plain V3 refs and admits typed V3 outcomes."""

    from polisyos.runtime.quality.cycle_substrate import (
        _cycle_job_v1_design_problem_ref,
        _cycle_job_v1_profile_selection_ref,
        cycle_job_design_problem_ref,
        cycle_job_profile_selection_ref,
    )

    problem_v2 = _design_problem()
    assert cycle_job_design_problem_ref(problem_v2) == (
        _cycle_job_v1_design_problem_ref(problem_v2)
    )
    assert cycle_job_profile_selection_ref(problem_v2) == (
        _cycle_job_v1_profile_selection_ref(problem_v2)
    )

    payload = _design_problem().model_dump(mode="python")
    payload["schema_version"] = DESIGN_PROBLEM_V3_SCHEMA_VERSION
    plain_v3 = DesignProblem.model_validate(payload)
    assert type(plain_v3.outcome_of_interest) is OutcomeOfInterest
    assert cycle_job_design_problem_ref(plain_v3) == (
        _cycle_job_v1_design_problem_ref(plain_v3)
    )
    assert cycle_job_profile_selection_ref(plain_v3) == (
        _cycle_job_v1_profile_selection_ref(plain_v3)
    )

    qualified_v3 = _qualified_v3_design_problem()
    assert cycle_job_design_problem_ref(qualified_v3).startswith("sha256:")
    assert cycle_job_profile_selection_ref(qualified_v3).startswith("sha256:")
    with pytest.raises(
        CycleSubstrateContextOwnerError,
        match="cycle_substrate_context_job_v1_serializer_model_unregistered",
    ):
        _cycle_job_v1_design_problem_ref(qualified_v3)

    unknown_version = plain_v3.model_copy(
        update={"schema_version": "policyos.runtime.design_problem.v_future"}
    )
    with pytest.raises(
        CycleSubstrateContextOwnerError,
        match="cycle_substrate_context_job_design_problem_schema_unsupported",
    ):
        cycle_job_design_problem_ref(unknown_version)
    with pytest.raises(
        CycleSubstrateContextOwnerError,
        match="cycle_substrate_context_job_design_problem_schema_unsupported",
    ):
        cycle_job_profile_selection_ref(unknown_version)
    with pytest.raises(
        CycleSubstrateContextOwnerError,
        match="cycle_substrate_context_job_v1_nested_schema_unsupported",
    ):
        _cycle_job_v1_design_problem_ref(unknown_version)


def test_cycle_substrate_context_job_parser_returns_typed_failure_for_non_object() -> None:
    """Malformed persisted JSON roots fail through the owner error contract."""

    from polisyos.runtime.quality.cycle_substrate import (
        parse_cycle_substrate_context_job_artifact,
    )

    with pytest.raises(
        CycleSubstrateContextOwnerError,
        match="cycle_substrate_context_job_record_invalid: payload_root_not_object",
    ):
        parse_cycle_substrate_context_job_artifact([])  # type: ignore[arg-type]
    with pytest.raises(
        CycleSubstrateContextOwnerError,
        match="cycle_substrate_context_job_schema_version_unsupported",
    ):
        parse_cycle_substrate_context_job_artifact(
            {"schema_version": "policyos.runtime.cycle_substrate_context_job_artifact.v_future"}
        )


@dataclass
class _TestControlJobRecord:
    job_id: str
    run_id: str | None
    submitted_by: str | None = "fixture-actor"
    state: str = "running"
    lease_owner: str | None = "fixture-worker"
    attempt: int = 1


class _TestCurrentJobExecutionOwner:
    """Narrow fixture for artifact-profile tests; HTTP tests cover real lease ownership."""

    def __init__(self, job_id: str, run_id: str) -> None:
        self.record = _TestControlJobRecord(job_id=job_id, run_id=run_id)

    def current_execution_job_record(self) -> _TestControlJobRecord:
        return self.record


def test_cycle_substrate_context_owner_persists_exact_job_scope_and_reads_direct_ref(
    tmp_path: Any,
) -> None:
    """The runtime store pins one candidate context to the compiled job identity."""

    problem = _design_problem()
    problem_ref = gy_content_hash(problem.model_dump(mode="json"))
    registry = _registry("education")
    world = _world_record(
        "education",
        registry,
        region_or_jurisdiction="UA",
        policy_slot_ids=("education.teaching_method",),
    )
    context = _cycle_context(
        design_problem_ref=problem_ref,
        registry=registry,
        world_model_record=world,
    )
    store = FileSystemCAS(
        tmp_path / "cycle-context-cas",
        ownership_enforced=True,
        ownership_requires_scope=True,
    )
    owner = CycleSubstrateContextArtifactOwner(
        store=store,
        control_store=_TestCurrentJobExecutionOwner(
            "job-context-owner", "run-context-owner"
        ),
    )

    with _authenticated_tenant_scope(
        tenant_id="tenant-context-owner", cell_id="cell-context-owner"
    ):
        ref = owner.persist_for_current_job(context, problem=problem)
        resolved = owner.resolve_for_current_job(ref, problem=problem)
        manifest = store.get_manifest(ref)
        serialized_v1 = cycle_substrate_owner._serialize_cycle_substrate_context_job_artifact(
            resolved
        )
        serialized_bytes = canon.to_canonical_bytes(
            serialized_v1,
            cycle_substrate_owner._CONTEXT_JOB_CANON,
        )
        assert serialized_v1 == resolved.model_dump(mode="json")
        assert store.get_bytes(ref) == serialized_bytes
        assert len(serialized_bytes) == 10_310
        assert hashlib.sha256(serialized_bytes).hexdigest() == (
            "8f410b96785a011c347c3f291c651b58e7d41eccd8ea3775aeecd4c257c1f6bb"
        )
        assert resolved.content_hash == (
            "sha256:e93b6eb4245991820146b9a7233d4639d6675cab2fcfdf54ac9000c9066960b2"
        )
        assert manifest.artifact_schema is not None
        assert manifest.artifact_schema.name == (
            cycle_substrate_owner.CYCLE_SUBSTRATE_CONTEXT_JOB_SCHEMA
        )
        assert manifest.artifact_schema.version == "1.0"
        historical = owner.resolve_historical_job_artifact(
            ref,
            problem=problem,
            expected_job_id="job-context-owner",
            expected_run_id="run-context-owner",
            expected_tenant_id="tenant-context-owner",
            expected_cell_id="cell-context-owner",
        )
        assert type(historical) is CycleSubstrateContextJobArtifact
        assert historical.content_hash == resolved.content_hash

    assert resolved.design_problem_ref == problem_ref
    assert resolved.problem == problem
    assert resolved.context.content_hash == context.content_hash
    assert resolved.context.authority_purpose == "cycle_input_candidate_only"
    assert resolved.profile_admission_status == "not_established"
    assert resolved.s8_status == "blocked"
    assert {
        "design_problem_population_identity_missing",
        "design_problem_time_roles_not_reconciled",
        "owner_profile_admission_missing",
        "s8_current_value_authority_missing",
    }.issubset(resolved.limitation_codes)
    assert {
        "grounding_authority",
        "transport_authority",
        "promotion_authority",
    }.issubset(resolved.context.may_not_use_for)
    assert manifest.tenant_context is not None
    assert manifest.tenant_context.tenant_id == "tenant-context-owner"
    assert manifest.tenant_context.cell_id == "cell-context-owner"
    assert manifest.same_input_closure is not None
    assert manifest.same_input_closure.run_id == "run-context-owner"
    assert manifest.same_input_closure.job_id == "job-context-owner"
    assert manifest.same_input_closure.tenant_id == "tenant-context-owner"
    assert manifest.same_input_closure.cell_id == "cell-context-owner"


def test_cycle_substrate_context_job_v2_roundtrips_qualified_v3_and_removal_turns_red(
    tmp_path: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The V2 owner stores/replays exact qualified V3 while its removal probe fails."""

    from polisyos.runtime.quality.cycle_substrate import (
        CYCLE_SUBSTRATE_CONTEXT_JOB_V2_SCHEMA,
        CycleSubstrateContextJobArtifactV2,
        cycle_job_design_problem_ref,
        cycle_substrate_context_job_content_hash,
    )

    problem = _qualified_v3_design_problem()
    problem_ref = cycle_job_design_problem_ref(problem)
    registry = _registry("education")
    world = _world_record(
        "education",
        registry,
        region_or_jurisdiction="UA",
        policy_slot_ids=("education.teaching_method",),
    )
    context = _cycle_context(
        design_problem_ref=problem_ref,
        registry=registry,
        world_model_record=world,
    )
    store = FileSystemCAS(
        tmp_path / "cycle-context-v2-cas",
        ownership_enforced=True,
        ownership_requires_scope=True,
    )
    owner = CycleSubstrateContextArtifactOwner(
        store=store,
        control_store=_TestCurrentJobExecutionOwner(
            "job-context-v2-owner", "run-context-v2-owner"
        ),
    )

    with _authenticated_tenant_scope(
        tenant_id="tenant-context-v2-owner", cell_id="cell-context-v2-owner"
    ):
        ref = owner.persist_for_current_job(context, problem=problem)
        resolved = owner.resolve_for_current_job(ref, problem=problem)
        manifest = store.get_manifest(ref)
        payload = canon.from_canonical_bytes(store.get_bytes(ref))
        historical = owner.resolve_historical_job_artifact(
            ref,
            problem=problem,
            expected_job_id="job-context-v2-owner",
            expected_run_id="run-context-v2-owner",
            expected_tenant_id="tenant-context-v2-owner",
            expected_cell_id="cell-context-v2-owner",
        )

    assert type(resolved) is CycleSubstrateContextJobArtifactV2
    assert type(historical) is CycleSubstrateContextJobArtifactV2
    assert type(resolved.problem.outcome_of_interest) is _QualifiedOutcomeOfInterestV3
    assert resolved.schema_version == CYCLE_SUBSTRATE_CONTEXT_JOB_V2_SCHEMA
    assert resolved.problem == problem
    assert resolved.design_problem_ref == problem_ref
    assert resolved.context.content_hash == context.content_hash
    assert resolved.profile_admission_status == "not_established"
    assert resolved.s8_status == "blocked"
    assert resolved.authority_purpose == "cycle_input_candidate_only"
    assert manifest.artifact_schema is not None
    assert manifest.artifact_schema.name == CYCLE_SUBSTRATE_CONTEXT_JOB_V2_SCHEMA
    assert manifest.artifact_schema.version == "2.0"
    assert manifest.kind == cycle_substrate_owner.CYCLE_SUBSTRATE_CONTEXT_JOB_KIND
    assert payload["schema_version"] == CYCLE_SUBSTRATE_CONTEXT_JOB_V2_SCHEMA
    assert cycle_substrate_context_job_content_hash(payload) == payload["content_hash"]

    # `model_construct` bypasses Pydantic validators. The serializer and
    # manifest-profile selector must still reject a forged nested schema.
    forged_problem = DesignProblem.model_construct(
        **{
            **resolved.problem.model_dump(mode="python"),
            "schema_version": "policyos.runtime.design_problem.v_future",
        }
    )
    forged_nested_artifact = CycleSubstrateContextJobArtifactV2.model_construct(
        **{**resolved.model_dump(mode="python"), "problem": forged_problem}
    )
    with pytest.raises(
        CycleSubstrateContextOwnerError,
        match="cycle_substrate_context_job_v2_nested_schema_unsupported",
    ):
        cycle_substrate_owner._serialize_cycle_substrate_context_job_artifact(
            forged_nested_artifact
        )

    forged_outer_artifact = CycleSubstrateContextJobArtifactV2.model_construct(
        **{
            **resolved.model_dump(mode="python"),
            "schema_version": "policyos.runtime.cycle_substrate_context_job_artifact.v_future",
        }
    )
    with pytest.raises(
        CycleSubstrateContextOwnerError,
        match="cycle_substrate_context_job_schema_version_unsupported",
    ):
        cycle_substrate_owner._context_job_write_options(forged_outer_artifact)

    v2_fields_without_qualified_outcome = {
        model_type: fields
        for model_type, fields in cycle_substrate_owner._CONTEXT_JOB_V2_EXACT_MODEL_FIELDS.items()
        if model_type is not _QualifiedOutcomeOfInterestV3
    }
    put_json_calls = 0
    original_put_json = store.put_json

    def observe_put_json(*args: Any, **kwargs: Any) -> Any:
        nonlocal put_json_calls
        put_json_calls += 1
        return original_put_json(*args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(
            cycle_substrate_owner,
            "_CONTEXT_JOB_V2_EXACT_MODEL_FIELDS",
            v2_fields_without_qualified_outcome,
        )
        patch.setattr(store, "put_json", observe_put_json)
        with _authenticated_tenant_scope(
            tenant_id="tenant-context-v2-owner", cell_id="cell-context-v2-owner"
        ):
            with pytest.raises(
                CycleSubstrateContextOwnerError,
                match="cycle_substrate_context_job_v2_serializer_model_unregistered",
            ):
                owner.persist_for_current_job(context, problem=problem)
            assert store.verify(ref).ok
    assert put_json_calls == 0

    foreign_outcome_type = create_model(
        "_QualifiedOutcomeOfInterestV3",
        __module__="polisyos.runtime.quality.design_problem",
        target_variable=(str, "education.learning_outcomes"),
        metric_id=(str, "learning_outcomes"),
        estimand=(str, "P(learning_outcomes | do(teaching_method))"),
        direction=(str, "maximize"),
    )
    foreign_outcome = foreign_outcome_type()
    assert type(foreign_outcome) is not _QualifiedOutcomeOfInterestV3
    assert type(foreign_outcome).__module__ == (
        _QualifiedOutcomeOfInterestV3.__module__
    )
    assert type(foreign_outcome).__qualname__ == (
        _QualifiedOutcomeOfInterestV3.__qualname__
    )
    with pytest.raises(
        CycleSubstrateContextOwnerError,
        match="cycle_substrate_context_job_v2_serializer_model_unregistered",
    ):
        cycle_substrate_owner._serialize_context_job_v2_value(foreign_outcome)

    foreign_problem_type = create_model(
        "DesignProblem",
        __module__="polisyos.runtime.quality.design_problem",
        schema_version=(str, DESIGN_PROBLEM_V3_SCHEMA_VERSION),
    )
    foreign_problem = foreign_problem_type()
    assert type(foreign_problem) is not DesignProblem
    assert type(foreign_problem).__module__ == DesignProblem.__module__
    assert type(foreign_problem).__qualname__ == DesignProblem.__qualname__
    with pytest.raises(
        CycleSubstrateContextOwnerError,
        match="cycle_substrate_context_job_v2_serializer_model_unregistered",
    ):
        cycle_substrate_owner._serialize_context_job_v2_value(foreign_problem)

    foreign_outer_type = create_model(
        "CycleSubstrateContextJobArtifactV2",
        __module__="polisyos.runtime.quality.cycle_substrate",
        schema_version=(str, CYCLE_SUBSTRATE_CONTEXT_JOB_V2_SCHEMA),
    )
    foreign_outer = foreign_outer_type()
    assert type(foreign_outer) is not CycleSubstrateContextJobArtifactV2
    assert type(foreign_outer).__module__ == (
        CycleSubstrateContextJobArtifactV2.__module__
    )
    assert type(foreign_outer).__qualname__ == (
        CycleSubstrateContextJobArtifactV2.__qualname__
    )
    with pytest.raises(
        CycleSubstrateContextOwnerError,
        match="cycle_substrate_context_job_v2_serializer_model_unregistered",
    ):
        cycle_substrate_owner._serialize_cycle_substrate_context_job_artifact(
            foreign_outer
        )


def test_cycle_substrate_context_job_v2_keeps_plain_v3_candidate_work_available(
    tmp_path: Any,
) -> None:
    """Plain V3 outcomes use V2 storage without gaining authority or refusing."""

    from polisyos.runtime.quality.cycle_substrate import (
        CYCLE_SUBSTRATE_CONTEXT_JOB_V2_SCHEMA,
        CycleSubstrateContextJobArtifactV2,
        _cycle_job_v1_design_problem_ref,
        cycle_job_design_problem_ref,
    )

    problem_payload = _design_problem().model_dump(mode="python")
    problem_payload["schema_version"] = DESIGN_PROBLEM_V3_SCHEMA_VERSION
    problem = DesignProblem.model_validate(problem_payload)
    assert type(problem.outcome_of_interest) is OutcomeOfInterest
    problem_ref = cycle_job_design_problem_ref(problem)
    assert problem_ref == _cycle_job_v1_design_problem_ref(problem)

    registry = _registry("education")
    world = _world_record(
        "education",
        registry,
        region_or_jurisdiction="UA",
        policy_slot_ids=("education.teaching_method",),
    )
    context = _cycle_context(
        design_problem_ref=problem_ref,
        registry=registry,
        world_model_record=world,
    )
    store = FileSystemCAS(
        tmp_path / "cycle-context-v2-plain-cas",
        ownership_enforced=True,
        ownership_requires_scope=True,
    )
    owner = CycleSubstrateContextArtifactOwner(
        store=store,
        control_store=_TestCurrentJobExecutionOwner(
            "job-context-v2-plain", "run-context-v2-plain"
        ),
    )

    with _authenticated_tenant_scope(
        tenant_id="tenant-context-v2-plain", cell_id="cell-context-v2-plain"
    ):
        ref = owner.persist_for_current_job(context, problem=problem)
        resolved = owner.resolve_for_current_job(ref, problem=problem)

    assert type(resolved) is CycleSubstrateContextJobArtifactV2
    assert resolved.schema_version == CYCLE_SUBSTRATE_CONTEXT_JOB_V2_SCHEMA
    assert resolved.problem == problem
    assert type(resolved.problem.outcome_of_interest) is OutcomeOfInterest
    assert resolved.design_problem_ref == problem_ref
    assert resolved.profile_admission_status == "not_established"
    assert resolved.s8_status == "blocked"


def test_cycle_substrate_context_owner_refuses_wrong_problem_or_job(tmp_path: Any) -> None:
    """A content ref cannot be replayed for another compiled problem or job."""

    problem = _design_problem()
    registry = _registry("education")
    world = _world_record(
        "education",
        registry,
        region_or_jurisdiction="UA",
        policy_slot_ids=("education.teaching_method",),
    )
    context = _cycle_context(
        design_problem_ref=gy_content_hash(problem.model_dump(mode="json")),
        registry=registry,
        world_model_record=world,
    )
    store = FileSystemCAS(
        tmp_path / "cycle-context-cas",
        ownership_enforced=True,
        ownership_requires_scope=True,
    )
    current_job = _TestCurrentJobExecutionOwner(
        "job-context-owner", "run-context-owner"
    )
    owner = CycleSubstrateContextArtifactOwner(
        store=store,
        control_store=current_job,
    )

    with _authenticated_tenant_scope(
        tenant_id="tenant-context-owner", cell_id="cell-context-owner"
    ):
        ref = owner.persist_for_current_job(context, problem=problem)
        with pytest.raises(
            CycleSubstrateContextOwnerError,
            match="cycle_substrate_context_job_binding_mismatch",
        ):
            owner.resolve_for_current_job(
                ref,
                problem=problem.model_copy(
                    update={"problem_statement": "A different compiled problem."}
                ),
            )
        current_job.record.job_id = "foreign-job"
        with pytest.raises(
            CycleSubstrateContextOwnerError,
            match="cycle_substrate_context_job_binding_mismatch",
        ):
            owner.resolve_for_current_job(ref, problem=problem)


def test_cycle_substrate_context_owner_refuses_foreign_tenant_and_cell(
    tmp_path: Any,
) -> None:
    """CAS tenant custody and active job scope both constrain direct resolution."""

    problem = _design_problem()
    registry = _registry("education")
    world = _world_record(
        "education",
        registry,
        region_or_jurisdiction="UA",
        policy_slot_ids=("education.teaching_method",),
    )
    context = _cycle_context(
        design_problem_ref=gy_content_hash(problem.model_dump(mode="json")),
        registry=registry,
        world_model_record=world,
    )
    store = FileSystemCAS(
        tmp_path / "cycle-context-cas",
        ownership_enforced=True,
        ownership_requires_scope=True,
    )
    owner = CycleSubstrateContextArtifactOwner(
        store=store,
        control_store=_TestCurrentJobExecutionOwner(
            "job-context-owner", "run-context-owner"
        ),
    )

    with _authenticated_tenant_scope(
        tenant_id="tenant-context-owner", cell_id="cell-context-owner"
    ):
        ref = owner.persist_for_current_job(context, problem=problem)

    with _authenticated_tenant_scope(
        tenant_id="tenant-foreign", cell_id="cell-foreign"
    ), pytest.raises(ArtifactOwnershipError):
        owner.resolve_for_current_job(ref, problem=problem)


def test_cycle_substrate_context_job_artifact_detects_removed_job_binding(
    tmp_path: Any,
) -> None:
    """Removing the job binding while retaining its markers fails content replay."""

    problem = _design_problem()
    registry = _registry("education")
    world = _world_record(
        "education",
        registry,
        region_or_jurisdiction="UA",
        policy_slot_ids=("education.teaching_method",),
    )
    context = _cycle_context(
        design_problem_ref=gy_content_hash(problem.model_dump(mode="json")),
        registry=registry,
        world_model_record=world,
    )
    store = FileSystemCAS(
        tmp_path / "cycle-context-cas",
        ownership_enforced=True,
        ownership_requires_scope=True,
    )
    owner = CycleSubstrateContextArtifactOwner(
        store=store,
        control_store=_TestCurrentJobExecutionOwner(
            "job-context-owner", "run-context-owner"
        ),
    )
    with _authenticated_tenant_scope(
        tenant_id="tenant-context-owner", cell_id="cell-context-owner"
    ):
        ref = owner.persist_for_current_job(context, problem=problem)
        record = CycleSubstrateContextJobArtifact.model_validate(
            canon.from_canonical_bytes(store.get_bytes(ref))
        )
    payload = record.model_dump(mode="python")
    payload["job_id"] = "foreign-job"

    with pytest.raises(ValueError, match="cycle_substrate_context_job_content_hash_mismatch"):
        CycleSubstrateContextJobArtifact.model_validate(payload)


def _registry(domain: str) -> SubstrateRegistry:
    registration = SubstrateRegistration(
        source_id=f"l2_scholar_kg:{domain}.duckdb",
        family_id=f"{domain}_causal_priors",
        layer=SubstrateLayer.L2,
        coverage=SubstrateCoverage(
            coverage_score=0.8,
            coverage_kind="lane0.causal_claim_coverage",
            coverage_rule_ref=f"lane0://{domain}/coverage",
            observation_count=4,
            metric_binding_count=4,
        ),
        trust_tier=SubstrateTrustTier(
            tier="derived_proxy",
            trust_cap=0.5,
            trust_multiplier=0.6,
            min_coverage=0.0,
            max_coverage=1.0,
            authority_ref=f"lane0://{domain}/trust",
        ),
        identification_mode="causal_prior_candidate",
        schema_regime=SubstrateSchemaRegime(
            schema_regime_id=f"{domain}_schema_v1",
            authority_ref=f"lane0://{domain}/schema",
            source_version="1",
        ),
        data_version=f"{domain}-data-v1",
        snapshot_id=f"{domain}-snapshot-v1",
        source_snapshot_id=f"{domain}-snapshot-v1",
        provenance_refs=(f"lane0://{domain}/causal-claims",),
        authority_refs=(f"lane0://{domain}/registry-owner",),
    )
    entry = build_substrate_registry_entry(registration)
    return build_substrate_registry(
        (entry,),
        producer_ref="tests.unit.runtime.quality.test_cycle_substrate",
        source_catalog_refs=registration.authority_refs,
    )


def _world_record(
    domain: str,
    registry: SubstrateRegistry,
    *,
    resolved_entry_content_hash: str | None = None,
    resolved_family_id: str | None = None,
    duplicate_resolved_family_id: str | None = None,
    world_model_record_id: str | None = None,
    region_or_jurisdiction: str | None = None,
    policy_slot_ids: tuple[str, ...] | None = None,
) -> WorldModelRecord:
    entry = registry.entries[0]
    resolved_entry = ResolvedSubstrateEntryRef(
        source_id=entry.source_id,
        family_id=resolved_family_id or entry.family_id,
        layer=entry.layer,
        coverage_score=entry.coverage.coverage_score,
        trust_tier=entry.trust_tier.tier,
        trust_cap=entry.trust_tier.trust_cap,
        identification_mode=entry.identification_mode,
        schema_regime_id=entry.schema_regime.schema_regime_id,
        data_version=entry.data_version,
        snapshot_id=entry.snapshot_id,
        source_snapshot_id=entry.source_snapshot_id,
        entry_content_hash=(
            resolved_entry_content_hash or entry.entry_content_hash
        ),
    )
    resolved_entries = (resolved_entry,)
    if duplicate_resolved_family_id is not None:
        resolved_entries = (
            resolved_entry.model_copy(
                update={"family_id": duplicate_resolved_family_id}
            ),
            resolved_entry,
        )
    registry_ref = SubstrateRegistryRef(
        substrate_version_id=registry.substrate_version_id,
        content_hash=registry.content_hash,
        registry_artifact_ref=f"lane0://{domain}/substrate-registry",
        resolved_entries=resolved_entries,
    )
    fields: dict[str, Any] = {
        "schema_version": "policyos.runtime.world_model_record.v1",
        "authority_status": "limited",
        "created_at": "2026-07-12T00:00:00+00:00",
        "producer_ref": "tests.unit.runtime.quality.test_cycle_substrate",
        "region_or_jurisdiction": region_or_jurisdiction or f"lane0-{domain}",
        "population_scope": f"{domain}_population",
        "policy_domain": domain,
        "valid_time_scope": "2020/2025",
        "tx_time_scope": "2026-07-12T00:00:00+00:00",
        "resolution": "entity_year",
        "branch_mode": BranchMode.OBSERVED,
        "fabric_world_ref": FabricWorldRef(
            snapshot_root=f"/lane0/{domain}",
            snapshot_id=f"{domain}-snapshot-v1",
            branch="observed",
            world_query_policy="lane0_content_bound",
            provenance_manifest_ref=f"lane0://{domain}/manifest",
            content_query_digest=_hash(f"{domain}:world-query"),
            content_query_row_count=4,
        ),
        "data_forge_binding_ref": DataForgeBindingRef(
            snapshot_id=f"{domain}-snapshot-v1",
            release_id=f"{domain}-release-v1",
            role="domain",
            read_api_identity=f"lane0.{domain}.read_api",
            snapshot_ref=f"lane0://{domain}/snapshot",
            merkle_root=f"merkle:{domain}:v1",
            data_hash=_hash(f"{domain}:data"),
            provenance_manifest_ref=f"lane0://{domain}/data-manifest",
        ),
        "simulation_model_ref": SimulationModelRef(
            model_spec_ref=_hash(f"{domain}:model-spec"),
            model_spec_hash=_hash(f"{domain}:model-hash"),
            model_id=f"model_{domain}",
            data_snapshot_ref=_hash(f"{domain}:data-snapshot"),
            registry_bundle_ref=_hash(f"{domain}:registry-bundle"),
            fidelity_level="boundary",
            calibrated=False,
        ),
        "foundry_binding_ref": FoundryBindingRef(
            input_bindings_ref=_hash(f"{domain}:input-bindings"),
            bound_state_snapshot_ref=_hash(f"{domain}:bound-state"),
            mapping_rules_ref=_hash(f"{domain}:mapping-rules"),
            state_slot_digest=_hash(f"{domain}:state-slots"),
        ),
        "skg_causal_prior_ref": SkgCausalPriorRef(
            skg_snapshot_ref=f"lane0://{domain}/skg",
            skg_version_id=f"{domain}-skg-v1",
            source_data_snapshot_id=f"{domain}-snapshot-v1",
        ),
        "substrate_registry_ref": registry_ref,
        "policy_slot_map": (
            tuple(
                PolicySlotBinding(
                    slot_id=slot_id,
                    state_path=f"substrate.{slot_id}",
                    entity_scope="population",
                    temporal_granularity="year",
                )
                for slot_id in policy_slot_ids
            )
            if policy_slot_ids is not None
            else (
                PolicySlotBinding(
                    slot_id=f"{domain}_outcome",
                    state_path=f"substrate.{domain}.outcome",
                    entity_scope="population",
                    temporal_granularity="year",
                ),
            )
        ),
    }
    draft = WorldModelRecord.model_construct(
        world_model_record_id="world_model_record_0000000000000000",
        content_hash=_hash(f"{domain}:placeholder"),
        **fields,
    )
    content_hash = world_model_record_content_hash(draft)
    return WorldModelRecord(
        world_model_record_id=world_model_record_id
        or f"world_model_record_{content_hash.removeprefix('sha256:')[:16]}",
        content_hash=content_hash,
        **fields,
    )


def _cycle_context(
    *,
    domain: str = "education",
    lever_id: str = "education_teaching_method",
    instrument: str = "education.teaching_method",
    target_concept: str = "education.learning_outcomes",
    transport_covariate: str = "school_quality",
    registry: SubstrateRegistry | None = None,
    world_model_record: WorldModelRecord | None = None,
    intervention_substrate: InterventionSubstrateBundle | None = None,
    design_problem_ref: str | None = None,
) -> CycleSubstrateContext:
    registry = registry or _registry(domain)
    world_model_record = world_model_record or _world_record(domain, registry)
    selected_hash = registry.entries[0].entry_content_hash
    design_problem_ref = design_problem_ref or _hash(f"{domain}:design-problem")
    substrate_input_hash = _hash(f"{domain}:substrate-input")
    context_binding_hash = cycle_substrate_context_binding_hash(
        design_problem_ref=design_problem_ref,
        domain=domain,
        substrate_input_content_hash=substrate_input_hash,
        substrate_registry_content_hash=registry.content_hash,
        world_model_record_id=world_model_record.world_model_record_id,
        world_model_record_content_hash=world_model_record.content_hash,
        world_model_record_authority_status=world_model_record.authority_status,
        selected_registry_entry_hashes=(selected_hash,),
    )
    candidate = CandidateLeverEvidence(
        lever_id=lever_id,
        instrument=instrument,
        target_concept=target_concept,
        status="candidate_unbound",
        entry_content_hash=gy_content_hash(
            {
                "lever_id": lever_id,
                "instrument": instrument,
                "target_concept": target_concept,
            }
        ),
        substrate_input_content_hash=substrate_input_hash,
        selected_registry_entry_hash=selected_hash,
        context_binding_hash=context_binding_hash,
        source_refs=(f"lane0://{domain}/candidate-lever",),
    )
    transport = TransportContextEvidence(
        status="candidate_context_only_not_transport_authority",
        source_context_id=f"{domain}:source",
        target_context_id=f"{domain}:target",
        source_profile_content_hash=_hash(f"{domain}:source-profile"),
        target_profile_content_hash=_hash(f"{domain}:target-profile"),
        substrate_input_content_hash=substrate_input_hash,
        context_binding_hash=context_binding_hash,
        covariates=(
            TransportCovariateObservation(
                canonical_var=transport_covariate,
                source_value=1.0,
                target_value=2.0,
                source_row_content_hash=_hash(f"{domain}:{transport_covariate}:source"),
                target_row_content_hash=_hash(f"{domain}:{transport_covariate}:target"),
            ),
        ),
    )
    return build_cycle_substrate_context(
        design_problem_ref=design_problem_ref,
        domain=domain,
        substrate_registry=registry,
        selected_registry_entry_hashes=(selected_hash,),
        world_model_record=world_model_record,
        intervention_substrate=intervention_substrate,
        candidate_levers=(candidate,),
        transport_context=transport,
        source_pack_content_hash=_hash(f"{domain}:source-pack"),
        substrate_input_content_hash=substrate_input_hash,
    )


def test_world_context_resolution_uses_problem_and_wmr_evidence_not_domain_label() -> None:
    """A producer-scoped label cannot hide an exact content-bound world match."""

    registry = _registry("fiscal_credit")
    world = _world_record(
        "fiscal_credit",
        registry,
        region_or_jurisdiction="UA",
    )
    context = _cycle_context(
        domain="Ukraine economic policy",
        registry=registry,
        world_model_record=world,
    )

    resolved = cycle_substrate_owner.resolve_cycle_substrate_context_for_world(
        (context,),
        design_problem_ref=context.design_problem_ref,
        region_or_jurisdiction="UA",
    )

    assert resolved.content_hash == context.content_hash
    assert resolved.domain == "Ukraine economic policy"
    assert resolved.world_model_record.policy_domain == "fiscal_credit"


def test_world_context_resolution_refuses_no_match_and_ambiguity() -> None:
    """Missing or competing worlds must fail closed instead of selecting first."""

    problem_ref = _hash("shared-design-problem")
    contexts: list[CycleSubstrateContext] = []
    for domain in ("fiscal_credit", "public_finance"):
        registry = _registry(domain)
        contexts.append(
            _cycle_context(
                domain=f"producer-label-{domain}",
                registry=registry,
                world_model_record=_world_record(
                    domain,
                    registry,
                    region_or_jurisdiction="UA",
                ),
                design_problem_ref=problem_ref,
            )
        )

    with pytest.raises(
        WorldModelRecordError,
        match="cycle_substrate_context_unresolved",
    ):
        cycle_substrate_owner.resolve_cycle_substrate_context_for_world(
            tuple(contexts),
            design_problem_ref=problem_ref,
            region_or_jurisdiction="unseen-world",
        )

    with pytest.raises(
        WorldModelRecordError,
        match="cycle_substrate_context_ambiguous",
    ):
        cycle_substrate_owner.resolve_cycle_substrate_context_for_world(
            tuple(contexts),
            design_problem_ref=problem_ref,
            region_or_jurisdiction="UA",
        )


def test_cycle_substrate_context_binds_registry_wmr_and_pack_hashes() -> None:
    context = _cycle_context()

    assert context.substrate_registry_content_hash == context.substrate_registry.content_hash
    assert context.world_model_record_content_hash == context.world_model_record.content_hash
    assert context.source_pack_content_hash == _hash("education:source-pack")
    assert context.substrate_input_content_hash == _hash("education:substrate-input")
    assert {row.status for row in context.candidate_levers} == {"candidate_unbound"}
    assert context.authority_purpose == "cycle_input_candidate_only"


def test_cycle_substrate_context_rejects_stale_registry_hash() -> None:
    payload = _cycle_context().model_dump(mode="python")
    payload["substrate_registry_content_hash"] = _hash("stale")

    with pytest.raises(ValueError, match="cycle_substrate_registry_hash_mismatch"):
        CycleSubstrateContext.model_validate(payload)


def test_cycle_substrate_context_rejects_cross_context_candidate() -> None:
    education = _cycle_context()
    water = _cycle_context(
        domain="water_quality",
        lever_id="riparian_buffer_width",
        instrument="water.riparian_buffer_width",
        target_concept="water.nutrient_load",
        transport_covariate="watershed_slope",
    )
    payload = education.model_dump(mode="python")
    stale_candidate = education.candidate_levers[0].model_copy(
        update={"context_binding_hash": water.context_binding_hash}
    )
    payload["candidate_levers"] = [stale_candidate.model_dump(mode="python")]
    # Recompute the outer envelope so this probe isolates the candidate binding.
    payload["content_hash"] = cycle_substrate_context_content_hash(payload)

    with pytest.raises(ValueError, match="candidate_context_binding_mismatch"):
        CycleSubstrateContext.model_validate(payload)


def test_cycle_substrate_context_rejects_foreign_transport_binding_with_valid_envelope() -> None:
    education = _cycle_context()
    water = _cycle_context(
        domain="water_quality",
        lever_id="riparian_buffer_width",
        instrument="water.riparian_buffer_width",
        target_concept="water.nutrient_load",
        transport_covariate="watershed_slope",
    )
    payload = education.model_dump(mode="python")
    transport = dict(payload["transport_context"])
    transport["context_binding_hash"] = water.context_binding_hash
    payload["transport_context"] = transport
    # Recompute the outer envelope so this probe isolates the transport binding.
    payload["content_hash"] = cycle_substrate_context_content_hash(payload)

    with pytest.raises(ValueError, match="transport_context_binding_mismatch"):
        CycleSubstrateContext.model_validate(payload)


def test_cycle_substrate_context_rejects_wmr_registry_mismatch() -> None:
    education_registry = _registry("education")
    water_world = _world_record("water_quality", _registry("water_quality"))

    with pytest.raises(ValueError, match="wmr_registry_content_mismatch"):
        _cycle_context(
            registry=education_registry,
            world_model_record=water_world,
        )


def test_cycle_substrate_context_rejects_selected_entry_absent_from_wmr() -> None:
    registry = _registry("education")
    world = _world_record(
        "education",
        registry,
        resolved_entry_content_hash=_hash("unrelated-resolved-entry"),
    )

    with pytest.raises(
        ValueError,
        match="cycle_substrate_selected_entry_wmr_unresolved",
    ):
        _cycle_context(registry=registry, world_model_record=world)


def test_cycle_substrate_context_rejects_shaped_wmr_entry_projection() -> None:
    registry = _registry("education")
    shaped_world = _world_record(
        "education",
        registry,
        resolved_family_id="wrong_family_with_valid_entry_hash",
    )

    with pytest.raises(
        ValueError,
        match="cycle_substrate_selected_entry_projection_mismatch",
    ):
        _cycle_context(registry=registry, world_model_record=shaped_world)


def test_cycle_substrate_context_rejects_duplicate_wmr_entry_hashes() -> None:
    registry = _registry("education")
    duplicate_world = _world_record(
        "education",
        registry,
        duplicate_resolved_family_id="contradictory_family",
    )

    with pytest.raises(
        ValueError,
        match="cycle_substrate_wmr_resolved_entry_hash_duplicate",
    ):
        _cycle_context(registry=registry, world_model_record=duplicate_world)


def test_cycle_substrate_context_records_domain_label_drift_as_provenance() -> None:
    registry = _registry("education")
    water_labeled_world = _world_record("water_quality", registry)

    context = _cycle_context(
        domain="education",
        registry=registry,
        world_model_record=water_labeled_world,
    )

    assert context.domain == "education"
    assert context.world_model_record.policy_domain == "water_quality"
    assert context.world_model_record_content_hash == water_labeled_world.content_hash


def test_cycle_substrate_context_rejects_wmr_id_not_derived_from_content() -> None:
    registry = _registry("education")
    shaped_world = _world_record(
        "education",
        registry,
        world_model_record_id="world_model_record_ffffffffffffffff",
    )

    with pytest.raises(ValueError, match="cycle_substrate_wmr_id_mismatch"):
        _cycle_context(registry=registry, world_model_record=shaped_world)


def test_cycle_substrate_context_binds_wmr_authority_status() -> None:
    registry = _registry("education")
    limited_world = _world_record("education", registry)
    publishable_world = limited_world.model_copy(
        update={"authority_status": "publishable"}
    )

    limited = _cycle_context(registry=registry, world_model_record=limited_world)
    publishable = _cycle_context(
        registry=registry,
        world_model_record=publishable_world,
    )

    assert limited.context_binding_hash != publishable.context_binding_hash
    assert limited.content_hash != publishable.content_hash


def test_cycle_substrate_context_rejects_cross_context_transport() -> None:
    education = _cycle_context()
    water = _cycle_context(
        domain="water_quality",
        lever_id="riparian_buffer_width",
        instrument="water.riparian_buffer_width",
        target_concept="water.nutrient_load",
        transport_covariate="watershed_slope",
    )
    payload = education.model_dump(mode="python")
    payload["transport_context"] = water.transport_context.model_dump(mode="python")
    payload["content_hash"] = cycle_substrate_context_content_hash(payload)

    with pytest.raises(ValueError, match="transport_context_binding_mismatch"):
        CycleSubstrateContext.model_validate(payload)


def _intervention_bundle() -> InterventionSubstrateBundle:
    fields: dict[str, Any] = {
        "knob_dictionary": {
            "lane0_knob": {
                "type": "float",
                "min": 0.0,
                "max": 1.0,
            }
        },
        "lex_intervention_map": {},
        "observation_manifest": {},
        "source_refs": {"intervention_knob_dictionary": "lane0://l6/knobs"},
        "source_content_hashes": {
            "intervention_knob_dictionary": _hash("lane0:l6:knobs")
        },
    }
    return InterventionSubstrateBundle(
        **fields,
        content_hash=gy_content_hash(
            {
                "schema_version": "policyos.runtime.intervention_substrate_lift.v2",
                "policy_scenario_templates": {},
                "slot_family_manifest": {},
                "world_mechanism_manifest": {},
                "lex_authority_manifest": {},
                "owner_authority_manifest": {},
                **fields,
            }
        ),
    )


def test_cycle_substrate_context_revalidates_mutated_intervention_bundle() -> None:
    bundle = _intervention_bundle()
    context = _cycle_context(intervention_substrate=bundle)
    bundle.knob_dictionary["forged_after_validation"] = {"type": "float"}
    revalidate = getattr(
        __import__(
            "polisyos.runtime.quality.cycle_substrate",
            fromlist=["revalidate_cycle_substrate_context"],
        ),
        "revalidate_cycle_substrate_context",
        None,
    )

    assert callable(revalidate), "cycle substrate consumption revalidator missing"
    with pytest.raises(
        ValueError,
        match="cycle_substrate_intervention_bundle_hash_mismatch",
    ):
        revalidate(context)


def test_intervention_substrate_bundle_rejects_claimed_hash_at_owner_intake() -> None:
    payload = _intervention_bundle().model_dump(mode="python")
    payload["knob_dictionary"]["forged_before_intake"] = {"type": "float"}

    with pytest.raises(
        ValueError,
        match="intervention_substrate_bundle_content_hash_mismatch",
    ):
        InterventionSubstrateBundle.model_validate(payload)


def test_intervention_resolver_rechecks_bundle_hash_after_nested_mutation() -> None:
    bundle = _intervention_bundle()
    bundle.knob_dictionary["forged_after_intake"] = {"type": "float"}

    with pytest.raises(InterventionSubstrateError) as error:
        resolve_intervention_lever(
            bundle,
            operator_kind="lane0_knob",
            parameter_value=0.5,
        )

    assert error.value.code == "intervention_substrate_bundle_content_hash_mismatch"


def test_law_resolver_rechecks_bundle_hash_before_lex_authority_use() -> None:
    bundle = _intervention_bundle()
    law_ref = "forged_law"
    bundle.lex_intervention_map[law_ref] = {"knob_ids": ["lane0_knob"]}

    with pytest.raises(InterventionSubstrateError) as error:
        resolve_law_bound_lever(
            bundle,
            law_token=law_ref,
            knob_id="lane0_knob",
            parameter_value=0.5,
            legal_store=object(),  # type: ignore[arg-type]
        )

    assert error.value.code == "intervention_substrate_bundle_content_hash_mismatch"


def test_method_router_rechecks_bundle_hash_before_manifest_use() -> None:
    bundle = _intervention_bundle()
    bundle.observation_manifest["forged_route"] = {"family": "forged_family"}

    with pytest.raises(InterventionSubstrateError) as error:
        route_observation_family_method(bundle, family="forged_family")

    assert error.value.code == "intervention_substrate_bundle_content_hash_mismatch"


def test_third_pack_vocabulary_needs_no_engine_branch() -> None:
    context = _cycle_context(
        domain="water_quality",
        lever_id="riparian_buffer_width",
        instrument="water.riparian_buffer_width",
        target_concept="water.nutrient_load",
        transport_covariate="watershed_slope",
    )

    assert context.candidate_levers[0].lever_id == "riparian_buffer_width"
    assert context.candidate_levers[0].instrument == "water.riparian_buffer_width"
    assert context.transport_context is not None
    assert context.transport_context.covariates[0].canonical_var == "watershed_slope"


def test_third_pack_lever_reaches_typed_resolver_refusal_without_code_branch() -> None:
    """A third pack-shaped vocabulary follows the same exact resolver owner."""

    bundle = _intervention_bundle()
    context = _cycle_context(
        domain="water_quality",
        lever_id="riparian_buffer_width",
        instrument="water.riparian_buffer_width",
        target_concept="water.nutrient_load",
        transport_covariate="watershed_slope",
        intervention_substrate=bundle,
    )

    result = resolve_intervention_lever(
        bundle,
        operator_kind="water.riparian_buffer_width",
        parameter_value=3.0,
        cycle_substrate_context=context,
    )

    assert result.status == "candidate_unbound"
    assert result.lever_id == "riparian_buffer_width"
    assert result.reason_code == "knob_operator_unresolved"
    assert result.context_binding_hash == context.context_binding_hash


def test_candidate_resolver_requires_context_bound_l6_owner() -> None:
    """A loose valid bundle cannot fabricate a pack-side refusal."""

    bundle = _intervention_bundle()
    context = _cycle_context(
        domain="water_quality",
        lever_id="riparian_buffer_width",
        instrument="water.riparian_buffer_width",
        target_concept="water.nutrient_load",
        transport_covariate="watershed_slope",
    )

    with pytest.raises(InterventionSubstrateError) as error:
        resolve_intervention_lever(
            bundle,
            operator_kind="water.riparian_buffer_width",
            parameter_value=3.0,
            cycle_substrate_context=context,
        )

    assert error.value.code == "cycle_substrate_l6_bundle_missing"


def test_cycle_substrate_context_rejects_content_hash_tamper() -> None:
    payload = _cycle_context().model_dump(mode="python")
    payload["content_hash"] = _hash("tampered-context")

    with pytest.raises(ValueError, match="cycle_substrate_content_hash_mismatch"):
        CycleSubstrateContext.model_validate(payload)


@pytest.mark.parametrize(
    "refresh_case",
    ["candidate_levers", "transport_context", "both", "none"],
)
def test_configured_candidate_owner_persists_declared_model_in_exact_context(
    tmp_path: Any,
    refresh_case: str,
) -> None:
    """The existing context owner emits only a limited declared NCM selection."""
    from polisyos.runtime.quality.candidate_simulation import (
        CandidateScenarioN5Config,
        CandidateScenarioSetToRule,
        CandidateSimulationContextInputs,
        CandidateSimulationScenarioProfile,
        CandidateSimulationSyntheticModelDeclarationV1,
        candidate_simulation_profile_ref,
    )
    from polisyos.runtime.quality.cycle_substrate import (
        ConfiguredCandidateSimulationContextAdmissionOwner,
        _cycle_job_v1_design_problem_ref,
        _cycle_job_v1_profile_selection_ref,
    )
    from polisyos.runtime.quality.joint_simulation_horizon import HorizonSpec

    problem = _design_problem()
    registry = _registry("education")
    base_world = _world_record(
        "education",
        registry,
        region_or_jurisdiction="UA",
        policy_slot_ids=("education.teaching_method", "learning_outcomes"),
    )
    slots = tuple(
        slot.model_copy(update={"unit": "synthetic_score"})
        for slot in base_world.policy_slot_map
    )
    draft_world = base_world.model_copy(update={"policy_slot_map": slots})
    world_hash = world_model_record_content_hash(draft_world)
    world = draft_world.model_copy(
        update={
            "content_hash": world_hash,
            "world_model_record_id": (
                "world_model_record_" + world_hash.removeprefix("sha256:")[:16]
            ),
        }
    )
    context = _cycle_context(
        registry=registry,
        world_model_record=world,
        design_problem_ref=_cycle_job_v1_design_problem_ref(problem),
    )
    context_inputs = CandidateSimulationContextInputs(
        substrate_registry=context.substrate_registry,
        selected_registry_entry_hashes=context.selected_registry_entry_hashes,
        world_model_record=world,
        intervention_substrate=context.intervention_substrate,
        candidate_levers=(
            context.candidate_levers
            if refresh_case in {"candidate_levers", "both"}
            else ()
        ),
        transport_context=(
            context.transport_context
            if refresh_case in {"transport_context", "both"}
            else None
        ),
        source_pack_content_hash=context.source_pack_content_hash,
        substrate_input_content_hash=context.substrate_input_content_hash,
    )
    rule = CandidateScenarioSetToRule(
        operator_kind="teaching_method_set_to",
        parameter_id="intensity",
        target_world_slot="education.teaching_method",
        unit_id="synthetic_score",
        minimum=0,
        maximum=1,
    )
    n5 = CandidateScenarioN5Config(
        budget_ref="budget://cycle-substrate/declared-candidate",
        horizon=HorizonSpec(start=0, end=0, step=1),
        baseline_state={
            "education.teaching_method": 0.0,
            "learning_outcomes": 0.0,
        },
        seed=7,
        replications=2,
    )
    profile_fields = {
        "schema_version": "policyos.runtime.candidate_simulation_profile.v2",
        "profile_id": "cycle-substrate-declared-candidate",
        "profile_selection_ref": _cycle_job_v1_profile_selection_ref(problem),
        "context_inputs": context_inputs,
        "rule": rule,
        "n5": n5,
        "limitations": (
            "scenario_only",
            "real_profile_not_established",
            "real_time_not_established",
            "grounding_not_established",
            "s8_blocked",
            "n9_not_admitted",
        ),
    }
    profile_draft = CandidateSimulationScenarioProfile.model_construct(
        **profile_fields,
        content_hash="sha256:" + "0" * 64,
    )
    profile = CandidateSimulationScenarioProfile.model_validate(
        {
            **profile_fields,
            "content_hash": gy_content_hash(
                profile_draft.model_dump(mode="json", exclude={"content_hash"})
            ),
        }
    )
    declaration_fields = {
        "schema_version": (
            "policyos.runtime.candidate_simulation.synthetic_model_declaration.v1"
        ),
        "profile_config_ref": candidate_simulation_profile_ref(profile),
        "profile_content_hash": profile.content_hash,
        "profile_selection_ref": profile.profile_selection_ref,
        "target_world_slot": rule.target_world_slot,
        "outcome_variable": "learning_outcomes",
        "target_unit_id": "synthetic_score",
        "outcome_unit_id": "synthetic_score",
        "target_baseline": 0.0,
        "outcome_baseline": 0.0,
        "outcome_per_target_unit": 0.5,
        "outcome_noise_stddev": 0.01,
        "assumption": "declared_candidate_scm_not_empirically_grounded",
    }
    declaration_draft = CandidateSimulationSyntheticModelDeclarationV1.model_construct(
        **declaration_fields,
        content_hash="sha256:" + "0" * 64,
    )
    declaration = CandidateSimulationSyntheticModelDeclarationV1.model_validate(
        {
            **declaration_fields,
            "content_hash": gy_content_hash(
                declaration_draft.model_dump(mode="json", exclude={"content_hash"})
            ),
        }
    )
    store = FileSystemCAS(tmp_path / "candidate-context-cas")
    owner = ConfiguredCandidateSimulationContextAdmissionOwner(
        profiles=(profile,),
        model_declarations=(declaration,),
        store=store,
    )
    if refresh_case != "none":
        with pytest.raises(CycleSubstrateContextOwnerError) as normal_error:
            owner.admit_context(
                problem=problem,
                job_id="job-declared-candidate",
                run_id="run-declared-candidate",
                tenant_id="tenant-declared-candidate",
                cell_id="cell-declared-candidate",
            )
        assert (
            normal_error.value.code
            == "candidate_simulation_context_evidence_refresh_not_established"
        )

        from polisyos.pdc import WorldModelLimitations

        required_blockers = (
            "source_time_not_established",
            "source_to_target_measurement_contract_not_established",
            "causal_coupling_not_established",
        )
        acquired_draft = world.model_copy(
            update={
                "limitations": WorldModelLimitations(
                    admissibility_blockers=required_blockers
                ),
                "world_model_record_id": "world_model_record_" + "0" * 16,
                "content_hash": "sha256:" + "0" * 64,
            }
        )
        acquired_hash = world_model_record_content_hash(acquired_draft)
        acquired_world = acquired_draft.model_copy(
            update={
                "world_model_record_id": (
                    "world_model_record_" + acquired_hash.removeprefix("sha256:")[:16]
                ),
                "content_hash": acquired_hash,
            }
        )
        with pytest.raises(CycleSubstrateContextOwnerError) as acquired_error:
            owner.admit_context_for_acquired_world(
                problem=problem,
                profile_selection_ref=profile.profile_selection_ref,
                world_model_record=acquired_world,
                job_id="job-declared-candidate",
                run_id="run-declared-candidate",
                tenant_id="tenant-declared-candidate",
                cell_id="cell-declared-candidate",
            )
        assert (
            acquired_error.value.code
            == "candidate_simulation_context_evidence_refresh_not_established"
        )
        return

    offer = owner.admit_context(
        problem=problem,
        job_id="job-declared-candidate",
        run_id="run-declared-candidate",
        tenant_id="tenant-declared-candidate",
        cell_id="cell-declared-candidate",
    )
    from polisyos.runtime.quality.candidate_simulation import CandidateSimulationContextOffer

    assert type(offer) is CandidateSimulationContextOffer
    assert offer.profile == profile
    assert offer.model_declaration == declaration
    assert offer.model_declaration_ref is not None
    assert offer.ncm_ref is not None
    assert str(offer.ncm_ref.artifact_id) in (
        offer.context.world_model_record.simulation_model_ref.ncm_refs
    )
    assert offer.context.world_model_record.authority_status == "limited"
    assert offer.context.s8_status == "blocked"

    profile_only_owner = ConfiguredCandidateSimulationContextAdmissionOwner(
        profiles=(profile,)
    )
    profile_only = profile_only_owner.admit_context(
        problem=problem,
        job_id="job-profile-only",
        run_id="run-profile-only",
        tenant_id="tenant-profile-only",
        cell_id="cell-profile-only",
    )
    assert type(profile_only) is CandidateSimulationContextOffer
    assert profile_only.model_declaration is None
    assert profile_only.model_declaration_ref is None
    assert profile_only.ncm_ref is None
    assert profile_only.context.world_model_record == world

    changed_time = problem.jurisdiction_time.model_copy(
        update={"as_of": "2026-06-30"}
    )
    assert owner.admit_context(
        problem=problem.model_copy(update={"jurisdiction_time": changed_time}),
        job_id="job-declared-candidate",
        run_id="run-declared-candidate",
        tenant_id="tenant-declared-candidate",
        cell_id="cell-declared-candidate",
    ) is None
