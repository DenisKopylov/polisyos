"""ACQ-01 regression coverage for the N7 requirement handoff."""

from __future__ import annotations

import json
import os
from collections.abc import Iterator, Mapping
from contextlib import contextmanager, nullcontext
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

import polisyos.runtime.quality.generation_cycle as generation_cycle_module
import polisyos.runtime.quality.joint_simulation_horizon as n5_horizon
from polisyos.core.artifacts import ArtifactID as CASArtifactID
from polisyos.core.artifacts import (
    ArtifactManifest,
    ArtifactStore,
    ArtifactWriteOptions,
    FileSystemCAS,
    VerificationReport,
)
from polisyos.core.artifacts import ArtifactRef as CASArtifactRef
from polisyos.core.artifacts import InputRef as CASInputRef
from polisyos.core.canon import CanonSpec
from polisyos.data_requirement import (
    CAPABILITY_REQUIREMENT_RESOLUTION_SCHEMA_VERSION,
    DataQualityMinimums,
    DataRequirementCompilationReport,
    DataRequirementScope,
    DataRequirementSpec,
)
from polisyos.pdc import gy_content_hash
from polisyos.runtime.quality.acquisition_planner import (
    AcquisitionAffectedRegion,
    AcquisitionCaptureProvenance,
    AcquisitionOwnerArtifact,
    AcquisitionReceipt,
    AcquisitionWorldSnapshot,
    RecordedAcquisitionOwnerGateway,
    value_input_world_knowledge_requirement_gap,
)
from polisyos.runtime.quality.cycle_substrate import build_cycle_substrate_context
from polisyos.runtime.quality.data_forge_binding import MeasurementRootExecutionBinding
from polisyos.runtime.quality.design_problem import (
    CandidateLever,
    CandidateLeverSpace,
    DesignObjective,
    DesignProblem,
    DesignStakeholder,
    EvidenceAcquisitionNeeds,
    JurisdictionTimeSemantics,
    NLProvenance,
    OutcomeOfInterest,
)
from polisyos.runtime.quality.generation_cycle import (
    CandidateGroundingObservation,
    GenerationCycleController,
    JointSimulationPort,
    SimulationPortObservation,
    ValuePortObservation,
)
from polisyos.runtime.quality.substrate_registry import (
    SubstrateCoverage,
    SubstrateLayer,
    SubstrateRegistration,
    SubstrateSchemaRegime,
    SubstrateTrustTier,
    build_substrate_registry,
    build_substrate_registry_entry,
)
from polisyos.scientist.orchestration.engine.budget import BudgetLimit, BudgetState

REPO_ROOT = Path(os.environ.get("POLISYOS_TEST_REPO_ROOT", Path(__file__).resolve().parents[3]))
_ACQ01_ROUTE_STORE_UNSPECIFIED = object()
_ACQ01_ROUTE_VALUE_PORT_UNSPECIFIED = object()


class _BaseOnlyArtifactStore:
    """Expose the base store contract while withholding raw manifest bytes."""

    def __init__(self, store: ArtifactStore) -> None:
        self._store = store
        self.read_calls: int = 0

    def has(self, artifact_id: CASArtifactID | CASArtifactRef) -> bool:
        self.read_calls += 1
        return self._store.has(artifact_id)

    def get_bytes(self, artifact_id: CASArtifactID | CASArtifactRef) -> bytes:
        self.read_calls += 1
        return self._store.get_bytes(artifact_id)

    def get_manifest(self, artifact_id: CASArtifactID | CASArtifactRef) -> ArtifactManifest:
        self.read_calls += 1
        return self._store.get_manifest(artifact_id)

    def put_bytes(
        self,
        data: bytes,
        opts: ArtifactWriteOptions,
        *,
        return_selected_profile: bool = False,
    ) -> CASArtifactRef:
        return self._store.put_bytes(data, opts, return_selected_profile=return_selected_profile)

    def put_json(
        self,
        obj: object,
        opts: ArtifactWriteOptions,
        canon_spec: CanonSpec | None = None,
        *,
        return_selected_profile: bool = False,
    ) -> CASArtifactRef:
        return self._store.put_json(
            obj,
            opts,
            canon_spec,
            return_selected_profile=return_selected_profile,
        )

    def verify(self, artifact_id: CASArtifactID | CASArtifactRef) -> VerificationReport:
        self.read_calls += 1
        return self._store.verify(artifact_id)

    def iter_artifact_ids(self) -> list[CASArtifactID]:
        self.read_calls += 1
        return self._store.iter_artifact_ids()


def _contract_testing_measurement_root_binding(
    tmp_path: Path,
) -> MeasurementRootExecutionBinding:
    """Build a test-only binding from a persisted, selected execution scope."""

    from tests._helpers.measurement_execution_binding import (
        measurement_execution_binding,
    )

    return measurement_execution_binding(tmp_path)


def _empty_data_requirement_compilation_report(
    *,
    run_id: str,
    scenario_id: str | None = None,
) -> DataRequirementCompilationReport:
    """Return the compiler's versioned report shape for an empty basis."""

    return DataRequirementCompilationReport(
        run_id=run_id,
        scenario_id=scenario_id,
        specs=(),
        capability_resolution_schema_version=(CAPABILITY_REQUIREMENT_RESOLUTION_SCHEMA_VERSION),
        capability_requirement_resolutions=(),
    )


def _assert_n7_has_no_grounding_result(
    receipt: Mapping[str, Any],
    *,
    cycle: Any,
) -> None:
    """Keep owner writes distinct from both receipt and re-entry grounding."""

    assert receipt["status"] == "completed_no_results"
    rows = receipt["grounding_rederivations"]
    assert len(rows) == 1
    assert tuple(rows[0]["issue_codes"]) == ("generation_result_problem_scope_unestablished",)
    assert cycle.grounding.status == "grounding_unavailable"
    assert tuple(cycle.grounding.issue_codes) == ("generation_result_problem_scope_unestablished",)


def _problem(
    *,
    problem_id: str = "acq_case",
    statement: str = "Ground firm survival with an owner-backed data source.",
    domain: str = "generic_policy",
    runtime_hints: dict[str, Any] | None = None,
) -> DesignProblem:
    return DesignProblem(
        design_problem_id=problem_id,
        problem_statement=statement,
        domain=domain,
        nl_provenance=NLProvenance(
            raw_request=statement,
            source_surface="test_acq_01",
        ),
        authority_profile={
            "requester_authority": "research_lab",
            "requested_authority_level": "research",
            "mandate": "test-only acquisition handoff",
        },
        jurisdiction_time=JurisdictionTimeSemantics(
            region="UA",
            valid_time="2026",
            as_of="2026-09-21",
            policy_time="2026",
            data_time="2026",
        ),
        objectives=[
            DesignObjective(
                objective_id="firm_survival",
                description="Improve firm survival",
                metric_id="firm_survival",
            )
        ],
        stakeholders=[
            DesignStakeholder(
                stakeholder_id="firms",
                name="Firms",
                role="target_population",
            )
        ],
        outcome_of_interest=OutcomeOfInterest(
            target_variable="firm_survival",
            metric_id="firm_survival",
            estimand="average_treatment_effect",
        ),
        candidate_lever_space=CandidateLeverSpace(
            allowed_operator_kinds=["grant"],
            candidate_levers=[
                CandidateLever(
                    lever_id="grant",
                    operator_kind="grant",
                    instrument="Targeted grant",
                    target_slot="government_balance",
                )
            ],
        ),
        evidence_acquisition_needs=EvidenceAcquisitionNeeds(),
        runtime_hints=runtime_hints or {},
    )


def test_n7_caller_specs_and_runtime_hints_are_unbound_not_compiler_basis() -> None:
    hinted = ({"source": "runtime-hint"},)
    alias = ({"source": "compiled-alias"},)
    explicit = ({"source": "explicit"},)
    controller = GenerationCycleController()
    problem = _problem(runtime_hints={"n7_data_requirement_specs": hinted})

    basis = controller._n7_data_requirement_basis_with_report(
        problem,
        acquisition_request={
            "data_requirement_specs": explicit,
            "compiled_requirement_specs": alias,
        },
    )

    assert basis.specs == tuple(basis.compilation_report.specs)
    assert explicit not in basis.specs
    assert alias not in basis.specs
    assert basis.unbound_input_fields == (
        "acquisition_request.data_requirement_specs",
        "acquisition_request.compiled_requirement_specs",
        "runtime_hints.n7_data_requirement_specs",
    )


def test_n7_without_cycle_bound_source_gap_never_calls_owner_gateway(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    controller = GenerationCycleController(
        repo_root=tmp_path,
        authority_scope="contract_testing",
        measurement_root_execution_binding=_contract_testing_measurement_root_binding(tmp_path),
    )
    problem = _problem()

    def unexpected_gateway(_problem: DesignProblem) -> object:
        raise AssertionError("an unbound request must fail before owner use")

    monkeypatch.setattr(controller, "_n7_owner_gateway", unexpected_gateway)
    cycle = SimpleNamespace(
        terminal_kind="acquisition_required",
        cycle_index=0,
        revision_request=SimpleNamespace(strategy_payload={"acquisition_request": {}}),
    )

    assert controller._run_n7_acquisition_if_requested(problem, cycle=cycle) is None


def test_n7_typed_gap_and_spec_aliases_cannot_replace_compiler_output() -> None:
    gap = value_input_world_knowledge_requirement_gap(claim_ref="claim:acq")
    controller = GenerationCycleController()

    basis = controller._n7_data_requirement_basis_with_report(
        _problem(),
        acquisition_request={
            "requirement_gap": gap.model_dump(mode="json"),
            "data_requirement_specs": ({"source": "must-not-replace-gap"},),
            "compiled_requirement_specs": ({"source": "stale-alias"},),
        },
    )

    assert basis.specs == tuple(basis.compilation_report.specs)
    assert gap not in basis.specs
    assert basis.unbound_input_fields == (
        "acquisition_request.requirement_gap",
        "acquisition_request.data_requirement_specs",
        "acquisition_request.compiled_requirement_specs",
    )


def test_n7_fallback_handoff_preserves_statement_domain_scope_and_resolver(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _ResolverPort:
        def resolve(self, _query: object) -> object:
            return object()

    resolver = _ResolverPort()
    captured: list[tuple[object, dict[str, Any]]] = []

    class _RecordingCompiler:
        def __init__(self, *, capability_resolver: object | None = None) -> None:
            captured.append((capability_resolver, {}))

        def compile_for_scenario(
            self, scenario: dict[str, Any]
        ) -> DataRequirementCompilationReport:
            resolver_arg, _ = captured[-1]
            captured[-1] = (resolver_arg, scenario)
            return _empty_data_requirement_compilation_report(
                run_id="acq01-fallback-report",
                scenario_id=str(scenario["scenario_id"]),
            )

    monkeypatch.setattr(generation_cycle_module, "DataRequirementCompiler", _RecordingCompiler)
    controller = GenerationCycleController(capability_resolver=resolver)
    scope_a = {
        "profile_id": "pilot:ua:2026",
        "jurisdiction": "UA",
        "time_window": {"start": "2026-01-01", "end": "2026-12-31"},
    }
    scope_b = {
        "profile_id": "pilot:pl:2027",
        "jurisdiction": "PL",
        "time_window": {"start": "2027-01-01", "end": "2027-12-31"},
    }

    controller._n7_data_requirement_specs(
        _problem(
            statement="Ground employment retention for Ukrainian firms.",
            domain="fiscal_policy",
        ),
        acquisition_request={
            "required_data_families": ("firm_panel",),
            "scope_profile": scope_a,
        },
    )
    controller._n7_data_requirement_specs(
        _problem(
            statement="Ground school attendance for Polish districts.",
            domain="education_policy",
        ),
        acquisition_request={
            "required_data_families": ("attendance_panel",),
            "scope_profile": scope_b,
        },
    )

    assert len(captured) == 2
    assert all(item[0] is resolver for item in captured)
    first, second = (item[1] for item in captured)
    assert first["text"] != second["text"]
    assert first["domain"] != second["domain"]
    assert first["scope_profile"] == scope_a
    assert second["scope_profile"] == scope_b


def test_n7_empty_report_short_circuits_after_real_family_compile(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    actual_reports: list[DataRequirementCompilationReport] = []
    actual_compiler_resolvers: list[object | None] = []
    real_compiler = generation_cycle_module.DataRequirementCompiler

    class _ObservedRealCompiler:
        def __init__(self, *, capability_resolver: object | None = None) -> None:
            actual_compiler_resolvers.append(capability_resolver)
            self._delegate = real_compiler(capability_resolver=capability_resolver)

        def compile_for_scenario(
            self, scenario: Mapping[str, Any]
        ) -> DataRequirementCompilationReport:
            report = self._delegate.compile_for_scenario(scenario)
            actual_reports.append(report)
            return report

    monkeypatch.setattr(generation_cycle_module, "DataRequirementCompiler", _ObservedRealCompiler)
    selected_binding = _contract_testing_measurement_root_binding(tmp_path)
    controller = GenerationCycleController(
        repo_root=tmp_path,
        measurement_root_execution_binding=selected_binding,
        authority_scope="contract_testing",
    )
    problem = _problem()
    acquisition_request = {"required_data_families": ("unresolved_family",)}

    # The actual compiler keeps this requested family as a data requirement.
    # The empty result below is a separate, explicit short-circuit fixture.
    actual_specs, actual_resolutions = controller._n7_data_requirement_basis(
        problem,
        acquisition_request=acquisition_request,
    )
    assert actual_compiler_resolvers == [None]
    assert len(actual_reports) == 1
    actual_report = actual_reports[0]
    assert actual_report.capability_resolution_schema_version == (
        CAPABILITY_REQUIREMENT_RESOLUTION_SCHEMA_VERSION
    )
    assert actual_report.capability_requirement_resolutions == ()
    assert len(actual_specs) == 1
    assert actual_specs[0].required_data_families == ("unresolved_family",)
    assert actual_resolutions == ()

    empty_compiler_resolvers: list[object | None] = []
    empty_reports: list[DataRequirementCompilationReport] = []

    class _EmptyCompiler:
        def __init__(self, *, capability_resolver: object | None = None) -> None:
            empty_compiler_resolvers.append(capability_resolver)

        def compile_for_scenario(
            self, _scenario: Mapping[str, Any]
        ) -> DataRequirementCompilationReport:
            report = _empty_data_requirement_compilation_report(run_id="acq01-empty-report")
            empty_reports.append(report)
            return report

    monkeypatch.setattr(generation_cycle_module, "DataRequirementCompiler", _EmptyCompiler)
    empty_specs, empty_resolutions = controller._n7_data_requirement_basis(
        problem,
        acquisition_request=acquisition_request,
    )
    assert empty_compiler_resolvers == [None]
    assert len(empty_reports) == 1
    assert empty_reports[0].capability_resolution_schema_version == (
        CAPABILITY_REQUIREMENT_RESOLUTION_SCHEMA_VERSION
    )
    assert empty_reports[0].capability_requirement_resolutions == ()
    assert empty_specs == ()
    assert empty_resolutions == ()

    monkeypatch.setattr(
        controller,
        "_n7_world_snapshot",
        lambda *_args, **_kwargs: object(),
    )
    monkeypatch.setattr(controller, "_n7_owner_gateway", lambda *_args: object())

    def _unexpected_closed_loop(**_kwargs: object) -> object:
        raise AssertionError("empty specs and resolutions must not mint an acquisition receipt")

    monkeypatch.setattr(
        generation_cycle_module,
        "run_acquisition_closed_loop",
        _unexpected_closed_loop,
    )
    cycle = SimpleNamespace(
        terminal_kind="acquisition_required",
        cycle_index=0,
        revision_request=SimpleNamespace(
            strategy_payload={"acquisition_request": acquisition_request}
        ),
    )

    assert controller._run_n7_acquisition_if_requested(problem, cycle=cycle) is None
    assert empty_compiler_resolvers == [None, None]
    assert len(empty_reports) == 2


class _FixtureGenerationPort:
    async def __call__(self, problem: DesignProblem, *, cycle_index: int) -> Any:
        del cycle_index
        candidate = _fixture_candidate(problem, world_ref="world://before/acq-01")
        return SimpleNamespace(
            status="generated",
            candidates=(candidate,),
            surrogate_rankings=(
                SimpleNamespace(
                    candidate_id=candidate.candidate_id,
                    score=0.2,
                    voi_estimate=0.2,
                ),
            ),
            grounding_dispositions=(),
        )


class _FixtureAcquisitionGrounding:
    def __init__(self, *, issue_code: str = "acquire_data:fixture_panel") -> None:
        self.issue_code = issue_code

    def __call__(
        self,
        *,
        candidate: Any,
        problem: DesignProblem,
        cycle_index: int,
        generation_result: Any | None = None,
    ) -> CandidateGroundingObservation:
        del problem, cycle_index, generation_result
        return CandidateGroundingObservation(
            candidate_id=str(candidate.candidate_id),
            status="grounding_gap",
            grounding_score=0.1,
            issue_codes=(self.issue_code,),
            current_valid=False,
        )


class _WorldBoundSimulation:
    def __init__(self) -> None:
        self.world_refs: list[str] = []

    def __call__(
        self,
        *,
        candidate: Any,
        problem: DesignProblem,
        cycle_index: int,
    ) -> SimulationPortObservation:
        del problem, cycle_index
        atom = candidate.atom
        from polisyos.runtime.quality.intervention_atom_binding import (
            InterventionAtomBinding,
        )

        assert isinstance(atom, InterventionAtomBinding)
        world_ref = str(atom.world_model_record_ref)
        self.world_refs.append(world_ref)
        return SimulationPortObservation(
            candidate_id=str(candidate.candidate_id),
            status="joint_simulated",
            simulation_ref=f"fixture-simulation:{world_ref}",
            k_world_ref_before=world_ref,
            k_world_ref_after=world_ref,
        )


class _PendingFixtureValue:
    def __call__(
        self,
        *,
        candidate: Any,
        simulation: SimulationPortObservation,
        problem: DesignProblem,
        cycle_index: int,
    ) -> ValuePortObservation:
        del simulation, problem, cycle_index
        return ValuePortObservation(
            status="value_pending_n8",
            candidate_id=str(candidate.candidate_id),
            reason="fixture acquisition test leaves N8 pending",
        )


def _fixture_candidate(
    problem: DesignProblem,
    *,
    world_ref: str,
    target_world_slots: tuple[str, ...] = ("fixture_panel",),
    candidate_id: str = "candidate_fixture_panel",
) -> Any:
    """Return a content-valid canonical atom for the bounded ACQ fixture."""

    from polisyos.runtime.quality.intervention_atom_binding import (
        InterventionAtomBinding,
        intervention_atom_content_hash,
    )
    from tools.quality.validation import (
        check_layer3_gy_design_generation_contract as n4_contract,
    )

    payload = json.loads(
        (
            REPO_ROOT / "architecture/policy_design_case/layer3_gy_design_generation_contract.json"
        ).read_text(encoding="utf-8")
    )
    raw_candidate = n4_contract.first_shadow_bound_recorded_candidate(payload)
    atom = InterventionAtomBinding.model_validate(raw_candidate["atom"])
    atom = atom.model_copy(
        update={
            "problem_frame_ref": gy_content_hash(problem.model_dump(mode="json")),
            "target_world_slots": target_world_slots,
            "normalized_from": None,
            "world_model_record_ref": world_ref,
        }
    )
    atom = atom.model_copy(
        update={
            "atom_id": (
                f"atom_{intervention_atom_content_hash(atom).removeprefix('sha256:')[:16]}"
            ),
            "content_hash": intervention_atom_content_hash(atom),
        }
    )
    atom = InterventionAtomBinding.model_validate(atom.model_dump(mode="python"))
    return SimpleNamespace(
        candidate_id=candidate_id,
        atom=atom,
        intervention_atoms=(atom,),
        diversity_key=("grant", "firms", "fixture", "baseline"),
    )


def test_n7_reentry_candidate_is_accepted_by_real_n5_request_builder(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The re-entry shell supplies a canonical atom to the existing N5 seam."""

    problem = _problem(
        problem_id="acq_01_n5_shape",
        runtime_hints={
            "joint_simulation_resource": "method_registry_estimator",
            "joint_simulation_budget_ref": "budget://acq-01/n5-shape",
            "joint_simulation_horizon": {"start": 0, "end": 1, "step": 1},
        },
    )
    registry = _fixture_world_registry()
    world = generation_cycle_module._build_boundary_world_model_record(
        repo_root=REPO_ROOT,
        problem=problem,
        outcome="firm_survival",
        policy_slot_ids=("fixture_panel",),
        substrate_registry=registry,
        selected_registry_entry_hashes=(registry.entries[0].entry_content_hash,),
    )
    candidate = _fixture_candidate(problem, world_ref=world.world_model_record_id)
    port = JointSimulationPort(repo_root=REPO_ROOT)
    monkeypatch.setattr(
        port,
        "_boundary_world_model_record",
        lambda *, candidate, problem: world,
    )

    request = port._build_joint_simulation_request(candidate=candidate, problem=problem)

    assert request.intervention_atoms == (candidate.atom,)


def _fixture_data_requirement_spec() -> DataRequirementSpec:
    return DataRequirementSpec(
        requirement_id="data-requirement:fixture-panel",
        claim_id="claim-fixture-panel",
        required_data_families=("fixture_panel",),
        scope=DataRequirementScope(
            population="firms",
            geography="UA",
            time="annual",
            time_role="observation_time",
        ),
        recency_horizon="P90D",
        lineage_strictness="strict",
        quality_minima=DataQualityMinimums(min_quality_score=0.8, min_completeness=0.95),
        missingness_tolerance=0.02,
        transformation_tolerance="none",
        admissibility_predicates=("source_family_matches_compiled_requirement",),
        mandatory_facets=("source_contract_ref", "lineage_refs"),
        concept_spine_refs=("concept:firm",),
        authority_profile_refs=("authority_profile.research",),
    )


def _compiled_data_requirement_spec(
    problem: DesignProblem,
    *,
    family: str,
) -> DataRequirementSpec:
    """Return one exact compiler output for the controlled source-family fixture."""

    basis = GenerationCycleController()._n7_data_requirement_basis_with_report(
        problem,
        acquisition_request={"driver": f"acquire_data:{family}"},
    )
    matches = tuple(
        spec
        for spec in basis.specs
        if type(spec) is DataRequirementSpec and spec.required_data_families == (family,)
    )
    if len(matches) != 1:
        raise AssertionError("controlled_compiler_family_must_resolve_to_one_spec")
    return matches[0]


def _acq01_source_requirement_id(problem_id: str) -> str:
    from polisyos.runtime.quality.data_forge_binding import _gy_slug

    return f"req-{_gy_slug(problem_id)}"


def _fixture_registration(*, source_id: str, snapshot_id: str) -> SubstrateRegistration:
    return SubstrateRegistration(
        source_id=source_id,
        family_id="fixture_panel",
        layer=SubstrateLayer.L1,
        coverage=SubstrateCoverage(
            coverage_score=0.9,
            coverage_kind="recorded_owner_response",
            coverage_rule_ref="test://coverage/fixture_panel",
            dataset_count=1,
            metric_binding_count=1,
            observation_count=1,
        ),
        trust_tier=SubstrateTrustTier(
            tier="recorded",
            trust_cap=0.8,
            trust_multiplier=0.8,
            authority_ref="test://trust/fixture_panel",
        ),
        identification_mode="observed_panel",
        schema_regime=SubstrateSchemaRegime(
            schema_regime_id="manifest:fixture_panel",
            authority_ref="test://schema/fixture_panel",
        ),
        data_version="2026-09-22",
        snapshot_id=snapshot_id,
        source_snapshot_id=snapshot_id,
        provenance_refs=(f"test://provenance/{source_id}",),
        authority_refs=("test://authority/fixture_panel",),
    )


def _fixture_world_registry() -> Any:
    baseline = _fixture_registration(
        source_id="baseline.fixture_panel",
        snapshot_id="baseline:fixture_panel",
    )
    return build_substrate_registry(
        (build_substrate_registry_entry(baseline),),
        producer_ref="tests.unit.remediation.test_acq_01",
        source_catalog_refs=("test://acq-01/fixture-catalog",),
    )


def _fixture_owner_artifact(
    requirement_ref: str,
    *,
    candidate_content_hash: str | None = None,
    target_world_slots: tuple[str, ...] = ("fixture_panel",),
) -> AcquisitionOwnerArtifact:
    owner_response = {
        "owner_response_kind": "recorded_local_fixture_owner_response",
        "source_id": "fixture.owner_panel",
        "family_id": "fixture_panel",
        "snapshot_id": "fixture:fixture_panel:2026-09-22",
    }
    registration = _fixture_registration(
        source_id="fixture.owner_panel",
        snapshot_id="fixture:fixture_panel:2026-09-22",
    )
    payload = {
        "owner_response_kind": "real_owner_capture",
        "owner_response": owner_response,
        "raw_owner_response_hash": gy_content_hash(owner_response),
        "acquired_substrate_registrations": [registration.model_dump(mode="json")],
        "candidate_bindings": [
            {
                "candidate_id": "candidate_fixture_panel",
                "candidate_content_hash": (candidate_content_hash or "sha256:" + "1" * 64),
                "target_world_slots": list(target_world_slots),
            }
        ],
    }
    return AcquisitionOwnerArtifact.from_payload(
        owner_component="fabric.ingestion",
        requirement_ref=requirement_ref,
        artifact_ref="fixture://owner/fixture-panel",
        payload=payload,
        cost_usd=0.0,
        quality={"capture": "local_fixture_owner"},
        rights={"license": "test-fixture-only"},
        binding_refs=("candidate_fixture_panel",),
        journal_ref="journal://acq-01/fixture-panel",
        capture_provenance=AcquisitionCaptureProvenance.from_owner_response(
            owner_component="fabric.ingestion",
            owner_endpoint="fixture.owner_panel.acquire",
            owner_request={"requirement_ref": requirement_ref},
            owner_response=payload,
            captured_at=datetime(2026, 9, 22, tzinfo=UTC),
            capture_mode="local_substrate_owner",
        ),
    )


@contextmanager
def _published_worldbank_owner(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    artifact_store: ArtifactStore,
) -> Iterator[Any]:
    """Resolve and fetch the publisher fixture's own synthetic WDI observations."""
    from polisyos.core.contracts.control import DataNeed, DataResolveRequest
    from polisyos.data_forge.domains.catalog.batch import graph_builder
    from polisyos.data_forge.domains.catalog.batch.normalizer import normalize_worldbank
    from polisyos.fabric.connectors.sources.world_bank import WorldBankConnector
    from polisyos.fabric.retrieval.service import RetrievalService
    from tests.unit.fabric.test_retrieval_fetch_custody import (
        _build_full_published_catalog_fixture,
        build_worldbank_fetch_owner,
    )

    publisher_root = tmp_path / "published-catalog"
    publisher_root.mkdir(parents=True, exist_ok=True)
    actual_fetch = WorldBankConnector.fetch
    # The existing connector cassette supplies a second, genuinely distinct
    # WDI target for the same-problem requirement-ID collision control.
    with build_worldbank_fetch_owner(
        tmp_path / "alternate-recorded-source", artifact_store=artifact_store
    ) as recorded:
        alternate_record = recorded.catalog_record.model_copy(deep=True)
        alternate_plan = recorded.plan.model_copy(deep=True)
    with monkeypatch.context() as publisher_patch:
        build_graph = graph_builder.build_graph

        def build_graph_with_normalized_wdi(*, records: Any, **kwargs: Any) -> Any:
            # The shared publisher fixture constructs graph rows directly. Preserve
            # the license from its actual harvested WDI row through the canonical
            # normalizer before the graph and currentness receipts are produced.
            raw_path = publisher_root / "snapshot/datasets/raw/worldbank/snapshot/payload.jsonl"
            raw_rows = [json.loads(line) for line in raw_path.read_text().splitlines()]
            selected = [row for row in raw_rows if row.get("id") == "NY.GDP.PCAP.PP.CD"]
            if len(selected) != 1:
                raise AssertionError("published_wdi_harvest_not_unique")
            normalized = normalize_worldbank(selected[0])
            if not normalized.access.license:
                raise AssertionError("normalized_wdi_license_missing")

            def retain_normalized_source_facet() -> Iterator[Any]:
                matched = 0
                for record in records:
                    if (
                        record.source == normalized.source
                        and record.source_dataset_id == normalized.source_dataset_id
                    ):
                        matched += 1
                        record = record.model_copy(
                            update={
                                "license": normalized.license,
                                "access": record.access.model_copy(
                                    update={"license": normalized.access.license}
                                ),
                            }
                        )
                    yield record
                if matched != 1:
                    raise AssertionError("published_wdi_graph_record_not_unique")
                yield alternate_record

            return build_graph(records=retain_normalized_source_facet(), **kwargs)

        publisher_patch.setattr(graph_builder, "build_graph", build_graph_with_normalized_wdi)
        publisher = _build_full_published_catalog_fixture(publisher_root, publisher_patch)
        try:
            with monkeypatch.context() as fetch_patch:
                # The publisher fixture controls its fetch edge while building.
                # Reentry exercises the real connector with its own recorded edge.
                fetch_patch.setattr(WorldBankConnector, "fetch", actual_fetch)
                with build_worldbank_fetch_owner(
                    tmp_path / "worldbank-transport", artifact_store=artifact_store
                ) as transport:
                    rows = publisher.producer_graph._store._con.execute(
                        "SELECT DISTINCT country_code, year, value FROM ds_observations "
                        "WHERE raw_variable = ? ORDER BY country_code, year",
                        ["NY.GDP.PCAP.PP.CD"],
                    ).fetchall()
                    if not rows:
                        raise AssertionError("published_wdi_observations_missing")
                    old_request = WorldBankConnector._request_json

                    async def request_json(
                        session: Any, url: str, *, params: Any, connector_id: str
                    ):
                        if not url.endswith("/indicator/NY.GDP.PCAP.PP.CD"):
                            return await old_request(
                                session, url, params=params, connector_id=connector_id
                            )
                        country_path = url.split("/country/", 1)[1].split("/indicator/", 1)[0]
                        countries = set(country_path.upper().split(";"))
                        selected_rows = [
                            (country, year, value)
                            for country, year, value in rows
                            if "ALL" in countries or country in countries
                        ]
                        date_range = params.get("date")
                        if date_range:
                            start, _, end = str(date_range).partition(":")
                            first, last = int(start), int(end or start)
                            selected_rows = [
                                row for row in selected_rows if first <= row[1] <= last
                            ]
                        page = int(params.get("page", "1"))
                        per_page = int(params.get("per_page", "1000"))
                        pages = max(1, (len(selected_rows) + per_page - 1) // per_page)
                        page_rows = selected_rows[(page - 1) * per_page : page * per_page]
                        iso3 = {"UA": "UKR", "DE": "DEU", "PL": "POL", "RO": "ROU", "MD": "MDA"}
                        result = [
                            {
                                "indicator": {
                                    "id": "NY.GDP.PCAP.PP.CD",
                                    "value": "GDP per capita, PPP (synthetic fixture)",
                                },
                                "country": {"id": country, "value": country},
                                "countryiso3code": iso3[country],
                                "date": str(year),
                                "value": value,
                                "unit": "",
                                "decimal": 0,
                            }
                            for country, year, value in page_rows
                        ]
                        body = [{"page": page, "pages": pages, "total": len(selected_rows)}, result]
                        return body, {"ETag": '"published-fixture-1"'}, json.dumps(body).encode()

                    fetch_patch.setattr(
                        WorldBankConnector, "_request_json", staticmethod(request_json)
                    )
                    service = RetrievalService(
                        curated_dir=tmp_path,
                        artifact_store=artifact_store,
                        dataset_catalog=publisher.producer_graph,
                        providers=transport.providers,
                    )
                    need = DataNeed(
                        metric="gdp_per_capita",
                        geography="DE",
                        time_start="2020",
                        time_end="2020",
                        granularity="annual",
                        quality_min=0.7,
                    )
                    resolved = service.resolve(
                        DataResolveRequest(
                            data_needs=[need], mode="fastlane", allow_explore_fallback=False
                        ),
                        run_profile="prod_full",
                    )
                    if len(resolved.fetch_plans) != 1:
                        raise AssertionError(f"published_wdi_plan_not_unique:{resolved.warnings}")
                    plan = resolved.fetch_plans[0]
                    if (
                        plan.metric_id != "gdp_per_capita"
                        or plan.dataset_id != "NY.GDP.PCAP.PP.CD"
                        or plan.connector_id != "worldbank.wdi"
                        or plan.profile_id != "worldbank_wdi"
                    ):
                        raise AssertionError("published_wdi_plan_identity_mismatch")
                    # The Catalog fallback returns an unfiltered plan. Submit the
                    # need's explicit country to the actual connector and bind
                    # that exact scoped tuple through the Catalog owner.
                    if plan.filters:
                        raise AssertionError("published_wdi_unexpected_default_filters")
                    plan = plan.model_copy(update={"filters": {"country": [need.geography]}})
                    publisher.producer_graph.bind_fetch_target(
                        metric_id=plan.metric_id,
                        connector_id=plan.connector_id,
                        request_dataset_id=plan.dataset_id,
                        profile_id=plan.profile_id,
                        filters=plan.filters,
                    )
                    yield SimpleNamespace(
                        service=service,
                        graph=publisher.producer_graph,
                        providers=transport.providers,
                        store=artifact_store,
                        plan=plan,
                        alternate_plan=alternate_plan,
                        data_need=need,
                        observations=tuple(rows),
                    )
        finally:
            publisher.producer_graph.close()
            publisher.close()


@contextmanager
def _real_acq01_route(
    tmp_path: Path,
    problem: DesignProblem,
    *,
    candidate_content_hash: str,
    candidate_id: str = "candidate_metric_test",
    target_world_slots: tuple[str, ...] = ("agents.income",),
    requirement_ref: str = "data-requirement:acq-01-file-tabular",
    artifact_store: Any | None = None,
    execution_scope_binding: Any | None = None,
    prior_context: Any | None = None,
    selected_metric: str | None = None,
    selected_owner: Any | None = None,
) -> Any:
    """Build one recorded WorldBank route through the existing owners.

    This fixture deliberately stops at the owner-produced route payload.  The
    controller is expected to consume that payload during N7 re-entry; the
    tests below therefore exercise the missing orchestration bridge rather
    than minting a synthetic world-model reference in the test itself.
    """

    from polisyos.core.contracts.control import DataNeed, DataResolveRequest
    from polisyos.core.registry import build_default_registry_bundle
    from polisyos.runtime.quality.data_forge_binding import (
        MeasurementRootProducer,
        build_fabric_measurement_requirement,
        persist_measurement_root_data_snapshot,
        resolve_measurement_root_evidence,
    )
    from polisyos.runtime.quality.substrate_registry import (
        SubstrateCoverage,
        SubstrateLayer,
        SubstrateRegistration,
        default_substrate_catalog_paths,
        load_l5_catalog_authority,
        persist_measurement_root_substrate_registry,
        persist_substrate_registry,
        register_substrate_entry,
    )
    from polisyos.runtime.quality.world_model_record import (
        BranchMode,
        build_world_model_record,
    )
    from tests._helpers.selected_substrate_source_context import (
        select_substrate_source_context,
    )
    from tests._helpers.world_model_record import (
        _fabric_ref,
        _model_spec,
        _skg_ref,
        _substrate_registry,
        _write_data_forge_binding,
        _write_fabric_world_snapshot,
    )
    from tests.unit.fabric.test_retrieval_fetch_custody import (
        build_worldbank_fetch_owner,
    )

    family = selected_metric if selected_metric is not None else "metric.test"
    data_spec = _fixture_data_requirement_spec().model_copy(
        update={
            "requirement_id": requirement_ref,
            "claim_id": f"claim:{requirement_ref.removeprefix('data-requirement:')}",
            "required_data_families": (family,),
        }
    )
    if prior_context is not None:
        from polisyos.runtime.quality.cycle_substrate import revalidate_cycle_substrate_context

        prior_context = revalidate_cycle_substrate_context(prior_context)
        if (
            prior_context.design_problem_ref != gy_content_hash(problem.model_dump(mode="json"))
            or prior_context.domain != problem.domain
        ):
            raise ValueError("acq01_fixture_prior_context_problem_mismatch")
    tmp_path.mkdir(parents=True, exist_ok=True)
    capture_root = tmp_path / "capture"
    source_owner = (
        nullcontext(selected_owner)
        if selected_owner is not None
        else build_worldbank_fetch_owner(capture_root, artifact_store=artifact_store)
    )
    with source_owner as owner:
        if artifact_store is not None and owner.store is not artifact_store:
            raise ValueError("acq01_fixture_selected_store_mismatch")
        if selected_metric is not None and selected_metric != owner.plan.metric_id:
            raise ValueError("acq01_fixture_selected_metric_mismatch")
        resolved = owner.service.resolve(
            DataResolveRequest(
                data_needs=[getattr(owner, "data_need", DataNeed(metric=owner.plan.metric_id))],
                mode="fastlane",
                catalog_run_profile="prod_full",
            )
        )
        plans = list(resolved.fetch_plans)
        if selected_owner is not None:
            if len(plans) != 1 or any(
                getattr(plans[0], name) != getattr(owner.plan, name)
                for name in ("metric_id", "connector_id", "dataset_id", "profile_id")
            ):
                raise ValueError("acq01_fixture_selected_plan_mismatch")
            plans = [owner.plan]
        execution = owner.service.execute_fetch_plans(
            plans,
            persist_payload=True,
            allow_fallback=False,
        )
        preview = execution.previews[0]
        assert preview.fetch_receipt_ref is not None
        assert preview.metric.payload_ref is not None

        catalog_binding = owner.graph.bind_fetch_target(
            metric_id=owner.plan.metric_id,
            connector_id=preview.metric.connector_id,
            request_dataset_id=preview.metric.dataset_id,
            profile_id=owner.plan.profile_id,
            filters=owner.plan.filters,
        )
        source_requirement = build_fabric_measurement_requirement(
            catalog=owner.graph,
            catalog_binding=catalog_binding,
            design_problem=problem,
        )
        data_spec = data_spec.model_copy(
            update={"source_requirement_refs": (source_requirement.requirement_id,)}
        )
        store = owner.store
        from tests._helpers.measurement_execution_binding import (
            measurement_execution_binding,
        )

        if execution_scope_binding is None:
            execution_scope_binding = measurement_execution_binding(tmp_path)
        measurement_root = MeasurementRootProducer(
            artifact_store=store,
            execution_scope_binding=execution_scope_binding,
        ).produce_from_fabric_fetch(
            fetch_receipt_ref=preview.fetch_receipt_ref,
            catalog=owner.graph,
            providers=owner.providers,
            design_problem=problem,
            source_requirement=source_requirement,
        )
        evidence = resolve_measurement_root_evidence(
            store=store,
            measurement_root=measurement_root,
            catalog=owner.graph,
            providers=owner.providers,
            execution_scope_binding=execution_scope_binding,
        )
        data_snapshot_ref = persist_measurement_root_data_snapshot(
            store=store,
            evidence=evidence,
            execution_scope_binding=execution_scope_binding,
        )
        snapshot_id = str(evidence.payload.payload_ref.artifact_id)

        baseline_registry = (
            prior_context.substrate_registry if prior_context is not None else _substrate_registry()
        )
        baseline_registry_ref = persist_substrate_registry(store, baseline_registry)
        source_workspace = tmp_path / "selected-substrate-source-workspace"
        source_workspace.mkdir()
        source_context = select_substrate_source_context(
            REPO_ROOT,
            workspace_root=source_workspace,
        )
        source_owner_root = source_context.require_source_owner_root(REPO_ROOT)
        l5_authority = load_l5_catalog_authority(
            default_substrate_catalog_paths(source_owner_root),
            repo_root=source_owner_root,
        )
        assert source_context.source_use == "candidate_test_input_only"
        assert source_context.manifest_ref == (
            "repo://production_data/manifest.json#production_data_root_manifest"
        )
        registration = SubstrateRegistration(
            source_id="acquisition:acq-01-file-tabular",
            family_id=family,
            layer=SubstrateLayer.L4,
            coverage=SubstrateCoverage(
                coverage_score=0.42,
                coverage_kind="acquisition_receipt.coverage",
                coverage_rule_ref="receipt://acq-01/file-tabular#coverage",
                dataset_count=1,
                metric_binding_count=1,
                observation_count=evidence.payload.observed_row_count,
            ),
            trust_tier=l5_authority.trust_tiers["weak_anchor"],
            identification_mode="bounds_only",
            schema_regime=l5_authority.latest_schema_regime(),
            data_version="file-tabular-fixture-v1",
            snapshot_id=snapshot_id,
            source_snapshot_id=snapshot_id,
            provenance_refs=(f"cas://{evidence.measurement_root_ref.artifact_id}",),
            authority_refs=(l5_authority.measurement_registry_ref,),
        )
        admission = persist_measurement_root_substrate_registry(
            store,
            baseline_registry=baseline_registry,
            registration=registration,
            l5_authority=l5_authority,
            evidence=evidence,
            baseline_registry_ref=baseline_registry_ref,
            execution_scope_binding=execution_scope_binding,
        )
        # N7's accepted world write creates the runtime registry projection
        # that the receipt hashes.  Persist that exact projection while
        # retaining the canonical measurement-root admission as its evidence
        # and lineage source.
        route_registry = register_substrate_entry(
            baseline_registry,
            registration,
            producer_ref="polisyos.runtime.quality.acquisition_planner.N7",
        )
        route_registry_ref = persist_substrate_registry(
            store,
            route_registry,
            inputs=admission.input_refs,
        )

        world_root = tmp_path / "fresh-world"
        world_root.mkdir(parents=True, exist_ok=True)
        _write_fabric_world_snapshot(world_root, snapshot_id=snapshot_id)
        data_forge_binding_path = _write_data_forge_binding(
            world_root,
            snapshot_id=snapshot_id,
        )
        prior_world = prior_context.world_model_record if prior_context is not None else None
        if prior_world is None:
            registry_ref = build_default_registry_bundle(store).bundle_ref
        else:
            from polisyos.core.registry import load_registry_bundle_content
            from polisyos.runtime.quality.world_model_record import world_model_artifact_views

            registry_ref = world_model_artifact_views(prior_world).registry_bundle_ref
            # ACQ-01 route v1 carries the bundle ID through ModelSpec but has
            # no field for its selected manifest profile. Refuse rather than
            # silently re-resolve a different default at reentry.
            if registry_ref.manifest_profile_sha256 is not None:
                raise ValueError("acq01_fixture_prior_registry_profile_unrepresentable")
            selected = load_registry_bundle_content(store, registry_ref)
            if selected.bundle_ref != registry_ref:
                raise ValueError("acq01_fixture_prior_registry_view_mismatch")
        model_spec = _model_spec(data_snapshot_ref, registry_ref)
        policy_slots = (
            tuple(row.slot_id for row in prior_world.policy_slot_map)
            if prior_world is not None
            else tuple(dict.fromkeys(("agents.income", "government.balance", *target_world_slots)))
        )
        if not set(target_world_slots).issubset(policy_slots):
            raise ValueError("acq01_fixture_target_not_in_prior_world")
        region = prior_world.region_or_jurisdiction if prior_world is not None else "UA-30"
        population = (
            prior_world.population_scope
            if prior_world is not None
            else "recorded_file_tabular_fixture"
        )
        domain = prior_world.policy_domain if prior_world is not None else "fiscal_credit"
        valid_time = (
            prior_world.valid_time_scope if prior_world is not None else "2026-09-22/2026-09-22"
        )
        tx_time = (
            prior_world.tx_time_scope if prior_world is not None else "2026-09-22T00:00:00+00:00"
        )
        resolution = prior_world.resolution if prior_world is not None else "row"
        branch_mode = prior_world.branch_mode if prior_world is not None else BranchMode.OBSERVED
        world_build = build_world_model_record(
            store,
            fabric_world_ref=_fabric_ref(world_root, snapshot_id=snapshot_id),
            data_forge_snapshot_binding_path=data_forge_binding_path,
            data_snapshot_ref=data_snapshot_ref,
            model_spec=model_spec,
            registry_bundle_artifact_ref=registry_ref,
            skg_causal_prior_ref=_skg_ref(world_root, snapshot_id=snapshot_id),
            substrate_registry=route_registry,
            region_or_jurisdiction=region,
            population_scope=population,
            policy_domain=domain,
            valid_time_scope=valid_time,
            tx_time_scope=tx_time,
            resolution=resolution,
            branch_mode=branch_mode,
            policy_slot_ids=policy_slots,
            producer_ref="tests.unit.remediation.test_acq_01.real_route",
            required_substrate_families=(family,),
            substrate_registry_artifact_ref=route_registry_ref,
            _loaded_substrate_registry=route_registry,
        )
        if (
            prior_world is not None
            and world_build.record.policy_slot_map != prior_world.policy_slot_map
        ):
            raise ValueError("acq01_fixture_prior_slot_binding_mismatch")
        selected_entry_hashes = tuple(
            entry.entry_content_hash
            for entry in route_registry.entries
            if entry.family_id == family
        )
        context = build_cycle_substrate_context(
            design_problem_ref=gy_content_hash(problem.model_dump(mode="json")),
            domain=problem.domain,
            substrate_registry=route_registry,
            selected_registry_entry_hashes=selected_entry_hashes,
            world_model_record=world_build.record,
            intervention_substrate=None,
            candidate_levers=(),
            transport_context=None,
            source_pack_content_hash=None,
            substrate_input_content_hash=None,
        )
        captured_fetch = {
            "plan": preview.metric.plan_id,
            "payload_ref": preview.metric.payload_ref.model_dump(mode="json"),
            "fetch_receipt_ref": preview.fetch_receipt_ref.model_dump(mode="json"),
            "catalog_binding_ref": evidence.catalog_binding_ref.model_dump(mode="json"),
        }
        owner_response = {
            "owner_response_kind": "fabric_fetch_capture",
            "captured_fetches": [captured_fetch],
        }
        payload = {
            "owner_response_kind": "real_owner_capture",
            "owner_response": owner_response,
            "raw_owner_response_hash": gy_content_hash(owner_response),
            "acquired_substrate_registrations": [registration.model_dump(mode="json")],
            "candidate_bindings": [
                {
                    "candidate_id": candidate_id,
                    "candidate_content_hash": candidate_content_hash,
                    "target_world_slots": list(target_world_slots),
                }
            ],
            "acq01_route": {
                "route_schema_version": "policyos.runtime.acq01_route.v1",
                "capture_store_root": str(store.root),
                "measurement_root": measurement_root.model_dump(mode="json"),
                "data_snapshot_ref": data_snapshot_ref.model_dump(mode="json"),
                "registry_ref": route_registry_ref.model_dump(mode="json"),
                "baseline_registry_ref": baseline_registry_ref.model_dump(mode="json"),
                "registry": route_registry.model_dump(mode="json"),
                "build_inputs": {
                    "fabric_world_ref": _fabric_ref(
                        world_root,
                        snapshot_id=snapshot_id,
                    ).model_dump(mode="json"),
                    "data_forge_snapshot_binding_path": str(data_forge_binding_path),
                    "data_snapshot_ref": data_snapshot_ref.model_dump(mode="json"),
                    "model_spec": model_spec.model_dump(mode="json"),
                    "skg_causal_prior_ref": _skg_ref(
                        world_root,
                        snapshot_id=snapshot_id,
                    ).model_dump(mode="json"),
                    "region_or_jurisdiction": region,
                    "population_scope": population,
                    "policy_domain": domain,
                    "valid_time_scope": valid_time,
                    "tx_time_scope": tx_time,
                    "resolution": resolution,
                    "branch_mode": branch_mode.value,
                    "policy_slot_ids": list(policy_slots),
                    "producer_ref": "tests.unit.remediation.test_acq_01.real_route",
                    "data_forge_role": "academic",
                    "required_substrate_families": [family],
                },
            },
        }
        owner_artifact = AcquisitionOwnerArtifact.from_payload(
            owner_component="fabric.retrieval",
            requirement_ref=data_spec.requirement_id,
            artifact_ref="owner-capture://acq-01/file-tabular",
            payload=payload,
            cost_usd=0.0,
            quality={"owner_endpoint": "RetrievalService.resolve/execute_fetch_plans"},
            rights={"recording": "owner_response_replay_only"},
            binding_refs=(data_spec.requirement_id, candidate_id),
            journal_ref="journal://n7/acq-01/file-tabular",
            capture_provenance=AcquisitionCaptureProvenance.from_owner_response(
                owner_component="fabric.retrieval",
                owner_endpoint="RetrievalService.resolve/execute_fetch_plans",
                owner_request={"requirement_ref": data_spec.requirement_id},
                owner_response=payload,
                captured_at=datetime(2026, 9, 22, tzinfo=UTC),
                capture_mode="local_substrate_owner",
            ),
        )
        yield SimpleNamespace(
            data_spec=data_spec,
            owner_artifact=owner_artifact,
            store=store,
            measurement_root=measurement_root,
            evidence=evidence,
            data_snapshot_ref=data_snapshot_ref,
            admission=admission,
            execution_scope_binding=execution_scope_binding,
            registry_ref=route_registry_ref,
            world_build=world_build,
            context=context,
            catalog=owner.graph,
            providers=owner.providers,
        )


def test_wdi_requirement_scope_checks_rows_and_complete_annual_denominator() -> None:
    """Requested filters cannot stand in for actual metric, geography, and years."""
    from polisyos.runtime.quality.data_forge_binding import (
        FabricMeasurementRootBindingError,
        _validate_wdi_requirement_rows,
    )

    requirement = _fixture_data_requirement_spec()
    rows = [
        {"country_code": "DEU", "indicator_id": "NY.GDP.PCAP.PP.CD", "year": year, "value": 1.0}
        for year in (2020, 2021)
    ]
    arguments = {
        "requirement": requirement,
        "geography": "DE",
        "start": "2020",
        "end": "2021",
        "dataset_id": "NY.GDP.PCAP.PP.CD",
    }
    _validate_wdi_requirement_rows(rows, **arguments)
    _validate_wdi_requirement_rows(
        rows, **{**arguments, "start": "2020-01-01", "end": "2021-12-31"}
    )
    for start, end, reason in (
        ("2020-12-31", "2020-01-01", "time_order_invalid"),
        ("2020-06-01", "2021-12-31", "partial_year_not_established"),
        ("2020-01-01", "2021-06-30", "partial_year_not_established"),
        ("0000", "2021", "time_unresolved"),
    ):
        with pytest.raises(FabricMeasurementRootBindingError, match=reason):
            _validate_wdi_requirement_rows(rows, **{**arguments, "start": start, "end": end})
    mutations = (
        ([{**rows[0], "indicator_id": "other"}, rows[1]], "scope_mismatch"),
        ([{**rows[0], "country_code": "POL"}, rows[1]], "scope_mismatch"),
        ([rows[0], {**rows[1], "year": 2022}], "scope_mismatch"),
        ([rows[0], rows[0]], "scope_mismatch"),
        ([rows[0]], "coverage_incomplete"),
        ([rows[0], {**rows[1], "value": float("nan")}], "coverage_incomplete"),
        ([rows[0], {**rows[1], "value": 10**1000}], "coverage_incomplete"),
    )
    for altered, reason in mutations:
        with pytest.raises(FabricMeasurementRootBindingError, match=reason):
            _validate_wdi_requirement_rows(altered, **arguments)

    # The connector can fill a missing raw indicator from the request. This
    # bounded row check cannot turn that fallback into independent source truth.
    from polisyos.fabric.connectors.sources.world_bank import normalize_worldbank_records

    raw_rows = [
        {"countryiso3code": "DEU", "date": str(year), "value": 1.0} for year in (2020, 2021)
    ]
    normalized = normalize_worldbank_records(raw_rows, "NY.GDP.PCAP.PP.CD")
    assert all("indicator" not in row for row in raw_rows)
    _validate_wdi_requirement_rows(normalized, **arguments)


def test_acq01_published_wdi_fetch_produces_same_job_measurement_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Resolve current fixture data through Fabric and the fenced measurement owner."""
    import asyncio

    from polisyos.core import artifacts
    from polisyos.core.artifacts import load_core_json_artifact
    from polisyos.core.contracts import DataSnapshot
    from polisyos.core.contracts.control import NaturalLanguageRunRequest
    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.data_requirement.compiler import DataRequirementCompiler
    from polisyos.runtime.http.execution_policy import RuntimePrincipal
    from polisyos.runtime.quality.data_forge_binding import (
        FabricMeasurementRootBindingError,
        MeasurementRootProducer,
        _validate_compiled_fabric_measurement_binding,
        bind_measurement_root_execution_scope,
        build_fabric_measurement_requirement,
        persist_measurement_root_data_snapshot,
        resolve_measurement_root_evidence,
    )
    from tests._helpers.runtime_http import _build_control_service, _valid_intake_for_mode
    from tests.unit.runtime.http.control_service_test_support import bound_nl_authorization_proof
    from tests.unit.runtime.http.test_control_service_di import _fixture_claims

    problem = _problem(
        problem_id="acq01_published_wdi",
        statement="Examine synthetic GDP per capita observations.",
        domain="fiscal_credit",
    )
    problem = problem.model_copy(
        update={
            "jurisdiction_time": problem.jurisdiction_time.model_copy(
                update={"region": "DE", "data_time": "2020"}
            )
        }
    )
    tenant_id, cell_id = "tenant-fixture", "cell-fixture"
    store = FileSystemCAS(tmp_path / "cas").for_tenant(tenant_id, cell_id)
    with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
        service = _build_control_service(tmp_path / "control", artifact_store=store)
    try:
        request = NaturalLanguageRunRequest(
            request=problem.nl_provenance.raw_request,
            llm_model="simulated-qwen",
            context={
                "evaluation_safety_attempt": _valid_intake_for_mode("simulate_only").model_dump(
                    mode="json"
                )
            },
            max_iterations=1,
        )
        claims = _fixture_claims()
        launch = asyncio.run(
            service.launch_nl_run(
                request,
                principal=RuntimePrincipal.from_user_claims(claims),
                authorization_proof=bound_nl_authorization_proof(claims, request),
            )
        )
        lease = service._control_store.lease_next_job(
            worker_id="acq01-measurement", lease_seconds=600
        )
        assert lease is not None and lease.job_id == launch.job_id
        with service._control_store.job_execution_fence(
            job_id=lease.job_id, worker_id=lease.lease_owner, attempt=lease.attempt
        ):
            admission = service._control_store.current_execution_job_admission()
            with service._install_execution_scope(admission.scope):
                binding = bind_measurement_root_execution_scope(
                    admission=admission, job=admission.job, execution_scope=admission.scope
                )
                assert binding.authority_eligible
                with _published_worldbank_owner(
                    tmp_path / "selected-owner", monkeypatch, artifact_store=store
                ) as owner:
                    execution = owner.service.execute_fetch_plans(
                        [owner.plan], persist_payload=True, allow_fallback=False
                    )
                    assert len(execution.previews) == 1
                    preview = execution.previews[0]
                    assert preview.fetch_receipt_ref is not None
                    plan = owner.plan
                    catalog_binding = owner.graph.bind_fetch_target(
                        metric_id=plan.metric_id,
                        connector_id=plan.connector_id,
                        request_dataset_id=plan.dataset_id,
                        profile_id=plan.profile_id,
                        filters=plan.filters,
                    )
                    source_requirement = build_fabric_measurement_requirement(
                        catalog=owner.graph,
                        catalog_binding=catalog_binding,
                        design_problem=problem,
                    )
                    producer = MeasurementRootProducer(
                        artifact_store=store, execution_scope_binding=binding
                    )
                    measurement_root = producer.produce_from_fabric_fetch(
                        fetch_receipt_ref=preview.fetch_receipt_ref,
                        catalog=owner.graph,
                        providers=owner.providers,
                        design_problem=problem,
                        source_requirement=source_requirement,
                    )
                    evidence = resolve_measurement_root_evidence(
                        store=store,
                        measurement_root=measurement_root,
                        catalog=owner.graph,
                        providers=owner.providers,
                        execution_scope_binding=binding,
                    )
                    snapshot_ref = persist_measurement_root_data_snapshot(
                        store=store, evidence=evidence, execution_scope_binding=binding
                    )
                    assert evidence.payload.design_problem == problem
                    assert evidence.payload.observed_row_count == sum(
                        country == "DE" and year == 2020
                        for country, year, _value in owner.observations
                    )
                    snapshot = DataSnapshot.model_validate(
                        load_core_json_artifact(store, snapshot_ref)
                    )
                    assert snapshot.data_ref == evidence.payload.payload_ref
                    assert evidence.payload.source_requirement.required_data_families == (
                        "worldbank",
                    )
                    root_manifest = store.get_manifest(evidence.measurement_root_ref)
                    expected_input = artifacts.input_ref_from_artifact_ref(
                        preview.fetch_receipt_ref, role="fabric_fetch"
                    )
                    assert expected_input.manifest_profile_sha256 is not None
                    assert root_manifest.inputs == [expected_input]
                    assert root_manifest.authority is not None
                    authority_ref = artifacts.resolve_authority_envelope_ref(
                        store, root_manifest.authority
                    )
                    assert store.get_manifest(authority_ref).inputs == [expected_input]

                    def compile_requirement(
                        *, family: str, geography: str, year: str, granularity: str = "annual"
                    ) -> Any:
                        report = DataRequirementCompiler().compile_for_scenario(
                            {
                                "scenario_id": problem.design_problem_id,
                                "text": problem.problem_statement,
                                "domain": problem.domain,
                                "expected_evidence_contract": {
                                    "admissible_data_source_families": [family]
                                },
                                "scenario_profile": {
                                    "profile_id": "fixture-scope",
                                    "jurisdiction": geography,
                                    "time_window": {"start": year, "end": year},
                                    "time_role": "observation_time",
                                    "granularity": granularity,
                                },
                            }
                        )
                        assert len(report.specs) == 1
                        return report.specs[0]

                    requirement = compile_requirement(
                        family="gdp_per_capita", geography="DE", year="2020"
                    )
                    assert (
                        source_requirement.requirement_id not in requirement.source_requirement_refs
                    )
                    join_args = {
                        "store": store,
                        "evidence": evidence,
                        "catalog": owner.graph,
                        "providers": owner.providers,
                        "execution_scope_binding": binding,
                    }
                    limitations = _validate_compiled_fabric_measurement_binding(
                        requirement=requirement, **join_args
                    )
                    assert "catalog_resolution_is_candidate_only" in limitations
                    assert "worldbank_indicator_id_may_be_request_fallback" in limitations
                    year_frequency = compile_requirement(
                        family="gdp_per_capita", geography="DE", year="2020", granularity="Y"
                    )
                    assert (
                        _validate_compiled_fabric_measurement_binding(
                            requirement=year_frequency, **join_args
                        )
                        == limitations
                    )
                    for family, geography, year, reason in (
                        ("unemployment_rate", "DE", "2020", "metric_mismatch"),
                        ("gdp_per_capita", "PL", "2020", "scope_mismatch"),
                        ("gdp_per_capita", "DE", "2021", "scope_mismatch"),
                    ):
                        wrong = compile_requirement(family=family, geography=geography, year=year)
                        with pytest.raises(FabricMeasurementRootBindingError, match=reason):
                            _validate_compiled_fabric_measurement_binding(
                                requirement=wrong, **join_args
                            )

                    alternate = owner.alternate_plan
                    assert alternate.metric_id == "gdp"
                    assert alternate.dataset_id != plan.dataset_id
                    other_execution = owner.service.execute_fetch_plans(
                        [alternate], persist_payload=True, allow_fallback=False
                    )
                    assert len(other_execution.previews) == 1
                    other_receipt = other_execution.previews[0].fetch_receipt_ref
                    assert other_receipt is not None
                    other_binding = owner.graph.bind_fetch_target(
                        metric_id=alternate.metric_id,
                        connector_id=alternate.connector_id,
                        request_dataset_id=alternate.dataset_id,
                        profile_id=alternate.profile_id,
                        filters=alternate.filters,
                    )
                    other_source_requirement = build_fabric_measurement_requirement(
                        catalog=owner.graph,
                        catalog_binding=other_binding,
                        design_problem=problem,
                    )
                    assert (
                        other_source_requirement.requirement_id == source_requirement.requirement_id
                    )
                    assert other_source_requirement != source_requirement
                    other_root = producer.produce_from_fabric_fetch(
                        fetch_receipt_ref=other_receipt,
                        catalog=owner.graph,
                        providers=owner.providers,
                        design_problem=problem,
                        source_requirement=other_source_requirement,
                    )
                    other_evidence = resolve_measurement_root_evidence(
                        store=store,
                        measurement_root=other_root,
                        catalog=owner.graph,
                        providers=owner.providers,
                        execution_scope_binding=binding,
                    )
                    with pytest.raises(
                        FabricMeasurementRootBindingError,
                        match="measurement_requirement_metric_mismatch",
                    ):
                        _validate_compiled_fabric_measurement_binding(
                            **{**join_args, "evidence": other_evidence},
                            requirement=requirement,
                        )

                    altered = source_requirement.model_copy(
                        update={"required_data_families": ("different-source",)}
                    )
                    with pytest.raises(
                        FabricMeasurementRootBindingError,
                        match="measurement_root_source_requirement_mismatch",
                    ):
                        producer.produce_from_fabric_fetch(
                            fetch_receipt_ref=preview.fetch_receipt_ref,
                            catalog=owner.graph,
                            providers=owner.providers,
                            design_problem=problem,
                            source_requirement=altered,
                        )
    finally:
        service.close()


def _real_acq01_before_context(
    tmp_path: Path,
    problem: DesignProblem,
    *,
    artifact_store: Any | None = None,
) -> Any:
    """Build the content-bound pre-acquisition context from existing owners."""

    from tests._helpers.world_model_record import (
        _build_record,
        _substrate_registry,
    )

    _, world_build, _, _ = _build_record(tmp_path / "before", artifact_store=artifact_store)
    registry = _substrate_registry()
    selected_entry_hashes = tuple(entry.entry_content_hash for entry in registry.entries)
    return build_cycle_substrate_context(
        design_problem_ref=gy_content_hash(problem.model_dump(mode="json")),
        domain=problem.domain,
        substrate_registry=registry,
        selected_registry_entry_hashes=selected_entry_hashes,
        world_model_record=world_build.record,
        intervention_substrate=None,
        candidate_levers=(),
        transport_context=None,
        source_pack_content_hash=None,
        substrate_input_content_hash=None,
    )


def _real_acq01_inputs(
    tmp_path: Path,
    *,
    problem_id: str,
    extra_runtime_hints: dict[str, Any] | None = None,
) -> Any:
    data_spec = _fixture_data_requirement_spec().model_copy(
        update={
            "requirement_id": "data-requirement:acq-01-file-tabular",
            "claim_id": "claim:acq-01-file-tabular",
            "required_data_families": ("metric.test",),
            "source_requirement_refs": (_acq01_source_requirement_id(problem_id),),
        }
    )
    runtime_hints = {"n7_data_requirement_specs": (data_spec,)}
    runtime_hints.update(extra_runtime_hints or {})
    problem = _problem(problem_id=problem_id, runtime_hints=runtime_hints)
    before_context = _real_acq01_before_context(tmp_path, problem)
    candidate = _fixture_candidate(
        problem,
        world_ref=before_context.world_model_record.world_model_record_id,
        target_world_slots=("agents.income",),
        candidate_id="candidate_metric_test",
    )
    return SimpleNamespace(
        data_spec=data_spec,
        problem=problem,
        before_context=before_context,
        candidate=candidate,
    )


class _ContextRecordingSimulation:
    def __init__(self) -> None:
        self.controller: GenerationCycleController | None = None
        self.observations: list[tuple[Any, str]] = []

    def __call__(
        self,
        *,
        candidate: Any,
        problem: DesignProblem,
        cycle_index: int,
    ) -> SimulationPortObservation:
        del problem, cycle_index
        context = self.controller._cycle_substrate_context if self.controller else None
        world_ref = str(candidate.atom.world_model_record_ref)
        self.observations.append((context, world_ref))
        return SimulationPortObservation(
            candidate_id=str(candidate.candidate_id),
            status="joint_simulated",
            simulation_ref=f"fixture-simulation:{world_ref}",
            k_world_ref_before=world_ref,
            k_world_ref_after=world_ref,
        )


def _build_acq01_real_route_controller(
    *,
    case: Any,
    route: Any,
    simulation: Any,
    repo_root: Path,
    authority_scope: str = "contract_testing",
    artifact_store: object = _ACQ01_ROUTE_STORE_UNSPECIFIED,
    value_port: Any = _ACQ01_ROUTE_VALUE_PORT_UNSPECIFIED,
) -> GenerationCycleController:
    class _RouteGenerationPort:
        async def __call__(self, current: DesignProblem, *, cycle_index: int) -> Any:
            del current, cycle_index
            return SimpleNamespace(
                status="generated",
                candidates=(case.candidate,),
                surrogate_rankings=(
                    SimpleNamespace(
                        candidate_id=case.candidate.candidate_id,
                        score=0.2,
                        voi_estimate=0.2,
                    ),
                ),
                grounding_dispositions=(),
            )

    gateway = RecordedAcquisitionOwnerGateway(
        artifacts_by_requirement={
            case.data_spec.requirement_id: route.owner_artifact,
        }
    )
    gateway.catalog = route.catalog
    gateway.providers = route.providers
    selected_store = (
        route.store if artifact_store is _ACQ01_ROUTE_STORE_UNSPECIFIED else artifact_store
    )
    selected_value_port = (
        _PendingFixtureValue() if value_port is _ACQ01_ROUTE_VALUE_PORT_UNSPECIFIED else value_port
    )
    controller = GenerationCycleController(
        generation_port=_RouteGenerationPort(),
        grounding_port=_FixtureAcquisitionGrounding(issue_code="acquire_data:metric.test"),
        simulation_port=simulation,
        value_port=selected_value_port,
        acquisition_owner_gateway=gateway,
        artifact_store=(
            cast("ArtifactStore | None", selected_store)
            if authority_scope == "contract_testing"
            else None
        ),
        repo_root=repo_root,
        cycle_substrate_context=case.before_context,
        measurement_root_execution_binding=(
            route.execution_scope_binding if authority_scope == "contract_testing" else None
        ),
        authority_scope=authority_scope,
    )
    if isinstance(simulation, _ContextRecordingSimulation):
        simulation.controller = controller
    return controller


def _receipt_with_route_measurement_profile(
    receipt: AcquisitionReceipt,
    *,
    profile_sha256: str | None,
) -> AcquisitionReceipt:
    """Rebuild one locally captured route with a selected-profile mutation."""

    route_artifacts = tuple(
        artifact
        for artifact in receipt.owner_artifacts
        if isinstance(artifact.payload.get("acq01_route"), dict)
    )
    if len(route_artifacts) != 1:
        raise AssertionError("expected exactly one captured ACQ-01 route")
    route_artifact = route_artifacts[0]
    changed_payload = json.loads(json.dumps(route_artifact.payload))
    changed_payload["acq01_route"]["measurement_root"]["payload_manifest_profile_sha256"] = (
        profile_sha256
    )
    capture = route_artifact.capture_provenance
    if capture is None:
        raise AssertionError("route fixture must retain capture provenance")
    changed_capture = AcquisitionCaptureProvenance.from_owner_response(
        owner_component=capture.owner_component,
        owner_endpoint=capture.owner_endpoint,
        owner_request={"requirement_ref": route_artifact.requirement_ref},
        owner_response=changed_payload,
        captured_at=capture.captured_at,
        capture_mode=capture.capture_mode,
        network_call=capture.network_call,
    )
    changed_artifact = AcquisitionOwnerArtifact.from_payload(
        owner_component=route_artifact.owner_component,
        requirement_ref=route_artifact.requirement_ref,
        artifact_ref=route_artifact.artifact_ref,
        payload=changed_payload,
        cost_usd=route_artifact.cost_usd,
        quality=route_artifact.quality,
        rights=route_artifact.rights,
        binding_refs=route_artifact.binding_refs,
        journal_ref=route_artifact.journal_ref,
        ingested=route_artifact.ingested,
        capture_provenance=changed_capture,
    )
    receipt_data = receipt.model_dump(mode="python")
    receipt_data["owner_artifacts"] = tuple(
        changed_artifact if artifact.artifact_ref == route_artifact.artifact_ref else artifact
        for artifact in receipt.owner_artifacts
    )
    receipt_data["content_hash"] = ""
    return AcquisitionReceipt.model_validate(receipt_data)


def _receipt_with_acq01_route_value(
    receipt: AcquisitionReceipt,
    route_value: object,
) -> AcquisitionReceipt:
    """Rebind the persisted route fixture after changing its typed route value."""

    route_artifacts = tuple(
        artifact
        for artifact in receipt.owner_artifacts
        if isinstance(artifact.payload, Mapping) and "acq01_route" in artifact.payload
    )
    if len(route_artifacts) != 1:
        raise AssertionError("expected exactly one captured ACQ-01 route")
    route_artifact = route_artifacts[0]
    changed_payload = dict(route_artifact.payload)
    changed_payload["acq01_route"] = route_value
    capture = route_artifact.capture_provenance
    if capture is None:
        raise AssertionError("route fixture must retain capture provenance")
    changed_capture = AcquisitionCaptureProvenance.from_owner_response(
        owner_component=capture.owner_component,
        owner_endpoint=capture.owner_endpoint,
        owner_request={"requirement_ref": route_artifact.requirement_ref},
        owner_response=changed_payload,
        captured_at=capture.captured_at,
        capture_mode=capture.capture_mode,
        network_call=capture.network_call,
    )
    changed_artifact = AcquisitionOwnerArtifact.from_payload(
        owner_component=route_artifact.owner_component,
        requirement_ref=route_artifact.requirement_ref,
        artifact_ref=route_artifact.artifact_ref,
        payload=changed_payload,
        cost_usd=route_artifact.cost_usd,
        quality=route_artifact.quality,
        rights=route_artifact.rights,
        binding_refs=route_artifact.binding_refs,
        journal_ref=route_artifact.journal_ref,
        ingested=route_artifact.ingested,
        capture_provenance=changed_capture,
    )
    receipt_data = receipt.model_dump(mode="python")
    receipt_data["owner_artifacts"] = tuple(
        changed_artifact if item.artifact_ref == route_artifact.artifact_ref else item
        for item in receipt.owner_artifacts
    )
    receipt_data["content_hash"] = ""
    return AcquisitionReceipt.model_validate(receipt_data)


def _assert_n7_world_model_record_semantics(actual: Any, expected: Any) -> None:
    """Compare every stable WMR field while allowing reconstruction time to advance."""

    actual_projection = actual.model_dump(mode="json")
    expected_projection = expected.model_dump(mode="json")
    actual_created_at = datetime.fromisoformat(actual_projection.pop("created_at"))
    expected_created_at = datetime.fromisoformat(expected_projection.pop("created_at"))
    assert actual_projection == expected_projection
    assert actual.world_model_record_id == expected.world_model_record_id
    assert actual.content_hash == expected.content_hash
    assert actual_created_at >= expected_created_at


@pytest.mark.asyncio
async def test_production_n7_acq01_route_requires_scope_before_route_cas_and_n5(
    tmp_path: Path,
) -> None:
    """A legacy local route receipt cannot select a production world or re-enter N5."""

    case = _real_acq01_inputs(tmp_path, problem_id="acq_01_production_route_limited")
    with _real_acq01_route(
        tmp_path,
        case.problem,
        candidate_content_hash=case.candidate.atom.content_hash,
    ) as route:
        simulation = _ContextRecordingSimulation()
        controller = _build_acq01_real_route_controller(
            case=case,
            route=route,
            simulation=simulation,
            repo_root=tmp_path,
            authority_scope="production",
        )
        run = await controller.run(
            case.problem,
            budget_state=BudgetState(
                limits={"run": BudgetLimit(key="run", max_usd=Decimal("5.0"))}
            ),
            max_cycles=1,
        )

        assert len(simulation.observations) == 1
        assert simulation.observations[0][0] is case.before_context
        assert (
            simulation.observations[0][1]
            == case.before_context.world_model_record.world_model_record_id
        )
        cycle = run.cycles[0]
        assert cycle.acquisition_receipt is None
        assert cycle.counterexample.diagnostic.code == (
            "n6.acquisition.n7_execution_scope_not_established"
        )
        assert cycle.terminal_kind == "acquisition_required"


@pytest.mark.asyncio
async def test_n7_acq01_route_context_helper_refuses_production_scope_with_valid_route(
    tmp_path: Path,
) -> None:
    """The local route cannot rebuild a WMR outside explicit contract testing."""

    case = _real_acq01_inputs(tmp_path, problem_id="acq_01_helper_production_scope")
    with _real_acq01_route(
        tmp_path,
        case.problem,
        candidate_content_hash=case.candidate.atom.content_hash,
    ) as route:
        contract_controller = _build_acq01_real_route_controller(
            case=case,
            route=route,
            simulation=_WorldBoundSimulation(),
            repo_root=tmp_path,
        )
        producer_prior_context = contract_controller._cycle_substrate_context
        assert producer_prior_context is case.before_context
        run = await contract_controller.run(
            case.problem,
            budget_state=BudgetState(
                limits={"run": BudgetLimit(key="run", max_usd=Decimal("5.0"))}
            ),
            max_cycles=1,
        )
        receipt = AcquisitionReceipt.model_validate(run.acquisition_receipts[0])
        assert run.synthetic is True
        route_payload = route.owner_artifact.payload["acq01_route"]
        assert isinstance(route_payload, dict)
        assert any(
            artifact.payload.get("acq01_route") == route_payload
            for artifact in receipt.owner_artifacts
        )
        assert (
            receipt.grown_world_before_ref == producer_prior_context.world_model_record_content_hash
        )
        assert contract_controller._cycle_substrate_context is not producer_prior_context
        with pytest.raises(generation_cycle_module.GenerationCycleError) as stale_replay:
            contract_controller._rebuild_n7_acq01_route_context(
                case.problem,
                acquisition_receipt=receipt,
                candidate_id=case.candidate.candidate_id,
                candidate_content_hash=case.candidate.atom.content_hash,
                target_world_slots=tuple(case.candidate.atom.target_world_slots),
            )
        assert stale_replay.value.code == "n7_acq01_registry_binding_invalid"

        # Replay the persisted receipt against the exact immutable context from
        # which the real N7 producer created its before-ref. The controller
        # above has already advanced through re-entry and is now a stale reader.
        replay_controller = _build_acq01_real_route_controller(
            case=case,
            route=route,
            simulation=_WorldBoundSimulation(),
            repo_root=tmp_path,
        )
        assert replay_controller._cycle_substrate_context is producer_prior_context
        contract_context = replay_controller._rebuild_n7_acq01_route_context(
            case.problem,
            acquisition_receipt=receipt,
            candidate_id=case.candidate.candidate_id,
            candidate_content_hash=case.candidate.atom.content_hash,
            target_world_slots=tuple(case.candidate.atom.target_world_slots),
        )
        assert contract_context is not None

        # The reader needs the canonical Core JSON/raw-manifest capability,
        # not one concrete backend. Exercise a real non-filesystem wrapper.
        from polisyos.core import artifacts
        from polisyos.core.artifacts.backends.caching_store import CachingArtifactStore

        original_store = replay_controller._artifact_store
        cache_local = artifacts.FileSystemCAS(tmp_path / "route-cache")
        cached_store = CachingArtifactStore(remote=route.store, local=cache_local)
        assert not isinstance(cached_store, artifacts.FileSystemCAS)
        assert isinstance(cached_store, artifacts.ArtifactStore)
        assert isinstance(cached_store, artifacts.CoreJSONArtifactStore)
        try:
            replay_controller._artifact_store = cached_store
            cached_context = replay_controller._rebuild_n7_acq01_route_context(
                case.problem,
                acquisition_receipt=receipt,
                candidate_id=case.candidate.candidate_id,
                candidate_content_hash=case.candidate.atom.content_hash,
                target_world_slots=tuple(case.candidate.atom.target_world_slots),
            )
            assert cached_context is not None
            assert (
                cached_context.world_model_record.world_model_record_id
                == contract_context.world_model_record.world_model_record_id
            )

            # This proxy implements every required base ArtifactStore operation,
            # but deliberately lacks the optional raw-manifest read capability.
            base_store_only = SimpleNamespace(
                has=route.store.has,
                get_bytes=route.store.get_bytes,
                get_manifest=route.store.get_manifest,
                put_bytes=route.store.put_bytes,
                put_json=route.store.put_json,
                verify=route.store.verify,
                iter_artifact_ids=route.store.iter_artifact_ids,
            )
            assert isinstance(base_store_only, artifacts.ArtifactStore)
            assert not isinstance(base_store_only, artifacts.CoreJSONArtifactStore)
            replay_controller._artifact_store = base_store_only
            with pytest.raises(generation_cycle_module.GenerationCycleError) as no_raw_manifest:
                replay_controller._rebuild_n7_acq01_route_context(
                    case.problem,
                    acquisition_receipt=receipt,
                    candidate_id=case.candidate.candidate_id,
                    candidate_content_hash=case.candidate.atom.content_hash,
                    target_world_slots=tuple(case.candidate.atom.target_world_slots),
                )
            assert no_raw_manifest.value.code == "n7_acq01_route_cas_ref_invalid"
        finally:
            replay_controller._artifact_store = original_store
            close = getattr(cache_local, "close", None)
            if callable(close):
                close()

        # Exercise the actual receipt consumer, not a removed private marker helper.
        for nonroute_value in (None, "route-marker", ["not", "a", "route"]):
            nonroute_receipt = _receipt_with_acq01_route_value(receipt, nonroute_value)
            assert (
                replay_controller._rebuild_n7_acq01_route_context(
                    case.problem,
                    acquisition_receipt=nonroute_receipt,
                    candidate_id=case.candidate.candidate_id,
                    candidate_content_hash=case.candidate.atom.content_hash,
                    target_world_slots=tuple(case.candidate.atom.target_world_slots),
                )
                is None
            )
        empty_mapping_receipt = _receipt_with_acq01_route_value(receipt, {})
        with pytest.raises(generation_cycle_module.GenerationCycleError) as empty_route:
            replay_controller._rebuild_n7_acq01_route_context(
                case.problem,
                acquisition_receipt=empty_mapping_receipt,
                candidate_id=case.candidate.candidate_id,
                candidate_content_hash=case.candidate.atom.content_hash,
                target_world_slots=tuple(case.candidate.atom.target_world_slots),
            )
        assert empty_route.value.code == "n7_acq01_route_schema_mismatch"
        selected_profile = route.measurement_root.payload_manifest_profile_sha256
        assert selected_profile is not None
        assert route.evidence.measurement_root_ref.manifest_profile_sha256 == selected_profile
        assert route.admission.input_refs[0].manifest_profile_sha256 == selected_profile
        snapshot_manifest = route.store.get_manifest(route.data_snapshot_ref)
        snapshot_root_inputs = tuple(
            item for item in snapshot_manifest.inputs if item.role == "measurement_root"
        )
        assert snapshot_root_inputs == (
            CASInputRef(
                artifact_id=route.evidence.measurement_root_ref.artifact_id,
                role="measurement_root",
                manifest_profile_sha256=selected_profile,
            ),
        )
        route_payload = route.owner_artifact.payload["acq01_route"]
        registry_ref = CASArtifactRef.model_validate(route_payload["registry_ref"])
        registry_manifest = route.store.get_manifest(registry_ref)
        registry_root_inputs = tuple(
            item for item in registry_manifest.inputs if item.role == "measurement_root"
        )
        assert registry_root_inputs == snapshot_root_inputs
        assert (
            contract_context.world_model_record.world_model_record_id
            != case.before_context.world_model_record.world_model_record_id
        )

        profileless_receipt = _receipt_with_route_measurement_profile(receipt, profile_sha256=None)
        with pytest.raises(generation_cycle_module.GenerationCycleError) as missing_profile:
            replay_controller._rebuild_n7_acq01_route_context(
                case.problem,
                acquisition_receipt=profileless_receipt,
                candidate_id=case.candidate.candidate_id,
                candidate_content_hash=case.candidate.atom.content_hash,
                target_world_slots=tuple(case.candidate.atom.target_world_slots),
            )
        assert missing_profile.value.code == "n7_acq01_measurement_root_custody_invalid"

        production_controller = _build_acq01_real_route_controller(
            case=case,
            route=route,
            simulation=_WorldBoundSimulation(),
            repo_root=tmp_path,
            authority_scope="production",
        )
        # Give the direct-helper probe the exact fixture-selected store, so a
        # missing-store refusal cannot make the scope property appear to pass.
        production_controller._artifact_store = route.store
        with pytest.raises(
            generation_cycle_module.GenerationCycleError,
            match="n7_acq01_route_contract_testing_only",
        ):
            production_controller._rebuild_n7_acq01_route_context(
                case.problem,
                acquisition_receipt=receipt,
                candidate_id=case.candidate.candidate_id,
                candidate_content_hash=case.candidate.atom.content_hash,
                target_world_slots=tuple(case.candidate.atom.target_world_slots),
            )


@pytest.mark.asyncio
async def test_n7_acq01_real_measurement_root_delta_builds_fresh_wmr(
    tmp_path: Path,
) -> None:
    """A real owner delta must rebind N5 to a content-bound WMR, not S0 URI."""

    case = _real_acq01_inputs(tmp_path, problem_id="acq_01_real_wmr")
    with _real_acq01_route(
        tmp_path,
        case.problem,
        candidate_content_hash=case.candidate.atom.content_hash,
    ) as route:
        simulation = _WorldBoundSimulation()
        controller = _build_acq01_real_route_controller(
            case=case,
            route=route,
            simulation=simulation,
            repo_root=tmp_path,
        )
        run = await controller.run(
            case.problem,
            budget_state=BudgetState(
                limits={"run": BudgetLimit(key="run", max_usd=Decimal("5.0"))}
            ),
            max_cycles=1,
        )

        receipt = run.acquisition_receipts[0]
        assert run.synthetic is True
        _assert_n7_has_no_grounding_result(receipt, cycle=run.cycles[0])
        assert route.world_build.data_snapshot_ref == route.data_snapshot_ref
        assert route.world_build.record.simulation_model_ref.data_snapshot_ref == str(
            route.data_snapshot_ref.artifact_id
        )
        assert (
            simulation.world_refs[0] == case.before_context.world_model_record.world_model_record_id
        )
        assert simulation.world_refs[-1] in {
            route.world_build.record.world_model_record_id,
            route.world_build.record.content_hash,
        }
        assert simulation.world_refs[-1] != receipt["grown_world_after_ref"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "selected_store_kind",
    ["missing", "foreign_store", "unsupported_store"],
)
async def test_n7_acq01_route_requires_controller_selected_store(
    tmp_path: Path,
    selected_store_kind: str,
) -> None:
    """A hashed v1 path cannot override or bypass the selected CAS capability."""

    case = _real_acq01_inputs(tmp_path, problem_id="acq_01_foreign_selected_store")
    with _real_acq01_route(
        tmp_path,
        case.problem,
        candidate_content_hash=case.candidate.atom.content_hash,
    ) as route:
        historical_hash = route.owner_artifact.content_hash
        assert route.owner_artifact.payload["acq01_route"]["capture_store_root"] == str(  # noqa: S101
            route.store.root
        )
        foreign_store = FileSystemCAS(tmp_path / "foreign-selected-store")
        selected_store = (
            None
            if selected_store_kind == "missing"
            else object()
            if selected_store_kind == "unsupported_store"
            else foreign_store
        )
        expected_error = (
            "n7_acq01_route_store_not_supplied"
            if selected_store_kind == "missing"
            else "n7_acq01_route_cas_ref_invalid"
        )
        controller = _build_acq01_real_route_controller(
            case=case,
            route=route,
            simulation=_WorldBoundSimulation(),
            repo_root=tmp_path,
            artifact_store=selected_store,
        )

        with pytest.raises(
            generation_cycle_module.GenerationCycleError,
            match=expected_error,
        ):
            await controller.run(
                case.problem,
                budget_state=BudgetState(
                    limits={"run": BudgetLimit(key="run", max_usd=Decimal("5.0"))}
                ),
                max_cycles=1,
            )

        assert route.owner_artifact.content_hash == historical_hash  # noqa: S101


@pytest.mark.asyncio
async def test_n7_acq01_reentry_rebuilds_fresh_context_before_n5_and_n7(
    tmp_path: Path,
) -> None:
    """N7 re-entry must replace the shared context before dependent owners run."""

    case = _real_acq01_inputs(tmp_path, problem_id="acq_01_real_context")
    with _real_acq01_route(
        tmp_path,
        case.problem,
        candidate_content_hash=case.candidate.atom.content_hash,
    ) as route:
        simulation = _ContextRecordingSimulation()
        controller = _build_acq01_real_route_controller(
            case=case,
            route=route,
            simulation=simulation,
            repo_root=tmp_path,
        )
        run = await controller.run(
            case.problem,
            budget_state=BudgetState(
                limits={"run": BudgetLimit(key="run", max_usd=Decimal("5.0"))}
            ),
            max_cycles=1,
        )

        assert len(simulation.observations) == 2
        before, after = simulation.observations
        assert before[0] is case.before_context
        assert after[0] is not None
        assert after[0] is not case.before_context
        _assert_n7_world_model_record_semantics(
            after[0].world_model_record,
            route.world_build.record,
        )
        assert after[0].content_hash != case.before_context.content_hash
        assert {
            "grounding_authority",
            "transport_authority",
            "promotion_authority",
        }.issubset(after[0].may_not_use_for)
        assert after[1] in {
            route.world_build.record.world_model_record_id,
            route.world_build.record.content_hash,
        }
        assert run.cycles[0].simulation.k_world_ref_before == after[1]


@pytest.mark.asyncio
async def test_n7_acq01_reentry_rebinds_real_n5_and_default_n8(
    tmp_path: Path,
) -> None:
    """The accepted route reaches the real JointSimulationPort and default N8."""

    from polisyos.runtime.quality.intervention_atom_binding import (
        intervention_atom_content_hash,
    )

    case = _real_acq01_inputs(
        tmp_path,
        problem_id="acq_01_real_ports",
        extra_runtime_hints={
            "joint_simulation_resource": "method_registry_estimator",
            "joint_simulation_budget_ref": "budget://acq-01/real-ports",
            "joint_simulation_horizon": {"start": 0, "end": 1, "step": 1},
            "joint_simulation_baseline_state": {"firm_survival": 1.0},
            "joint_simulation_variable_map": {"firm_survival": "stock:0"},
            "joint_simulation_engine_plan": {
                "method_fqn": "simulation.system_dynamics.stock_flow@1.0.0",
                "system_dynamics_state": {
                    "initial_stocks": [1.0, 0.0],
                    "flow_matrix": [[0.0, 0.1], [0.0, 0.0]],
                    "exogenous_inflows": [0.0, 0.0],
                },
                "system_dynamics_params": {"dt": 1.0},
            },
        },
    )
    atom = case.candidate.atom
    assignment = atom.causal_do_expr.assignments[0].model_copy(
        update={"value": 1, "value_expr": None}
    )
    expression_payload = {
        **atom.causal_do_expr.expression_payload,
        "assignments": [assignment.model_dump(mode="json")],
    }
    causal_do_expr = atom.causal_do_expr.model_copy(
        update={
            "assignments": (assignment,),
            "expression_payload": expression_payload,
        }
    )
    direct_effect_bundle = atom.direct_effect_bundle.model_copy(
        update={
            "mechanism_config_overrides": {
                **atom.direct_effect_bundle.mechanism_config_overrides,
                "joint_simulation_engine_variable": "exogenous_inflows.0",
            }
        }
    )
    atom = atom.model_copy(
        update={
            "causal_do_expr": causal_do_expr,
            "direct_effect_bundle": direct_effect_bundle,
        }
    )
    atom_content_hash = intervention_atom_content_hash(atom)
    atom = atom.model_copy(
        update={
            "atom_id": f"atom_{atom_content_hash.removeprefix('sha256:')[:16]}",
            "content_hash": atom_content_hash,
        }
    )
    case.candidate.atom = atom
    case.candidate.intervention_atoms = (atom,)
    with _real_acq01_route(
        tmp_path,
        case.problem,
        candidate_content_hash=case.candidate.atom.content_hash,
    ) as route:

        class _RecordingN5Controller:
            def __init__(self) -> None:
                self.requests: list[Any] = []
                self._delegate = generation_cycle_module.JointSimulationHorizonController()

            def run(self, request: Any) -> Any:
                self.requests.append(request)
                return self._delegate.run(request)

        n5 = _RecordingN5Controller()
        runtime_store = route.store
        controller = _build_acq01_real_route_controller(
            case=case,
            route=route,
            simulation=JointSimulationPort(
                controller=n5,
                repo_root=tmp_path,
                cycle_substrate_context=case.before_context,
                artifact_store=runtime_store,
            ),
            repo_root=tmp_path,
            authority_scope="contract_testing",
            artifact_store=runtime_store,
            value_port=None,
        )

        run = await controller.run(
            case.problem,
            budget_state=BudgetState(
                limits={"run": BudgetLimit(key="run", max_usd=Decimal("5.0"))}
            ),
            max_cycles=1,
        )

        assert run.synthetic is True
        assert len(n5.requests) == 2
        before_request, after_request = n5.requests
        assert before_request.world_model_record == case.before_context.world_model_record
        _assert_n7_world_model_record_semantics(
            after_request.world_model_record,
            route.world_build.record,
        )
        assert (
            after_request.world_model_record_ref == route.world_build.record.world_model_record_id
        )
        assert isinstance(
            controller._value_port,
            generation_cycle_module._DefaultSimulationBoundFoundryValuePort,
        )
        assert controller._value_port.cycle_substrate_context is controller._cycle_substrate_context
        assert controller._cycle_substrate_context is not case.before_context
        _assert_n7_world_model_record_semantics(
            controller._cycle_substrate_context.world_model_record,
            route.world_build.record,
        )
        cycle = run.cycles[0]
        assert cycle.simulation.status == "joint_simulated"
        assert cycle.simulation.simulation_result_ref is not None
        persisted_n5 = generation_cycle_module.load_joint_simulation_result(
            cycle.simulation.simulation_result_ref,
            store=runtime_store,
            expected_world_model_record_content_hash=route.world_build.record.content_hash,
            expected_atom_ids=tuple(
                item.intervention_id for item in after_request.intervention_atoms
            ),
        )
        persisted_blockers = tuple(persisted_n5.promotion_ready_value_packet["authority_blockers"])
        assert cycle.simulation.authority_blockers == persisted_blockers
        point_sampling_records = tuple(
            point.replication_sampling
            for trajectory in persisted_n5.trajectories
            for point in trajectory.points
        )
        assert point_sampling_records
        assert all(record is not None for record in point_sampling_records)
        point_sampling_statuses = {
            record.status for record in point_sampling_records if record is not None
        }
        assert point_sampling_statuses == {"standard_error_not_estimated"}
        assert "standard_error_not_estimated" in persisted_blockers
        assert {
            "simulation_only_k_sim_not_world_evidence",
            "simulation_effect_basis_not_established",
        }.issubset(persisted_blockers)

        current_n5_schema = (
            n5_horizon.JOINT_SIMULATION_HORIZON_PAIRED_INTERACTION_UNCERTAINTY_SCHEMA_VERSION
        )
        assert persisted_n5.schema_version == current_n5_schema
        feedback = persisted_n5.feedback_classification
        foundry_limitations: set[str] = set()
        if "standard_error_not_estimated" in point_sampling_statuses:
            foundry_limitations.add("standard_error_not_estimated")
        if feedback.interaction_sampling_status == "not_established":
            foundry_limitations.add("interaction_sampling_not_established")
        elif feedback.interaction_sampling_status == "standard_error_not_estimated":
            foundry_limitations.update(
                {"interaction_sampling_not_established", "standard_error_not_estimated"}
            )
        if feedback.numeric_interaction == "unsupported":
            foundry_limitations.add("interaction_numeric_classification_unsupported")
        if "interaction_sampling_variation_observed" in feedback.limitations:
            foundry_limitations.add("interaction_sampling_variation_observed")
        expected_value_blockers = (
            set(cycle.simulation.authority_blockers) | set(persisted_blockers) | foundry_limitations
        )

        assert cycle.value_port.status == "value_conditional"
        assert cycle.value_port.candidate_id == cycle.selected_candidate_ref
        assert cycle.value_port.evaluation_mode == "simulate_only"
        assert cycle.value_port.decision_grade == "low"
        assert cycle.value_port.value_ref == str(cycle.simulation.simulation_result_ref.artifact_id)
        assert cycle.value_port.n5_interaction_schema_version == persisted_n5.schema_version
        assert cycle.value_port.numeric_interaction == feedback.numeric_interaction
        assert cycle.value_port.numeric_interaction_basis == feedback.numeric_interaction_basis
        assert cycle.value_port.interaction_sampling_status == feedback.interaction_sampling_status
        actual_value_blockers = tuple(cycle.value_port.authority_blockers)
        assert len(actual_value_blockers) == len(set(actual_value_blockers))
        assert set(actual_value_blockers) == expected_value_blockers
        assert cycle.value_port.value_receipt is None
        assert cycle.value_port.method_selection_receipt is None
        assert (
            cycle.value_port.world_model_record_content_hash
            == route.world_build.record.content_hash
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("mutation", ["before_ref", "delta_hash"])
async def test_n7_acq01_reentry_rejects_tampered_receipt_world_binding(
    tmp_path: Path,
    mutation: str,
) -> None:
    """Receipt world refs and delta hashes remain bound to the revalidated CAS route."""

    case = _real_acq01_inputs(tmp_path, problem_id=f"acq_01_tampered_{mutation}")
    with _real_acq01_route(
        tmp_path,
        case.problem,
        candidate_content_hash=case.candidate.atom.content_hash,
    ) as route:
        controller = _build_acq01_real_route_controller(
            case=case,
            route=route,
            simulation=_WorldBoundSimulation(),
            repo_root=tmp_path,
        )
        run = await controller.run(
            case.problem,
            budget_state=BudgetState(
                limits={"run": BudgetLimit(key="run", max_usd=Decimal("5.0"))}
            ),
            max_cycles=1,
        )
        receipt = AcquisitionReceipt.model_validate(run.acquisition_receipts[0])
        tampered = receipt.model_copy(
            update={
                "grown_world_before_ref": (
                    "sha256:" + "f" * 64
                    if mutation == "before_ref"
                    else receipt.grown_world_before_ref
                ),
                "grown_world_delta_hash": (
                    "sha256:" + "e" * 64
                    if mutation == "delta_hash"
                    else receipt.grown_world_delta_hash
                ),
            }
        )
        controller._cycle_substrate_context = case.before_context
        with pytest.raises(
            generation_cycle_module.GenerationCycleError,
            match="n7_acq01_registry_binding_invalid",
        ):
            controller._rebuild_n7_acq01_route_context(
                case.problem,
                acquisition_receipt=tampered,
                candidate_id=case.candidate.candidate_id,
                candidate_content_hash=case.candidate.atom.content_hash,
                target_world_slots=tuple(case.candidate.atom.target_world_slots),
            )


@pytest.mark.asyncio
async def test_n7_acq01_reentry_rejects_registry_version_content_mismatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A version string forged over unchanged registry bytes cannot pass N7."""

    case = _real_acq01_inputs(tmp_path, problem_id="acq_01_tampered_version")
    with _real_acq01_route(
        tmp_path,
        case.problem,
        candidate_content_hash=case.candidate.atom.content_hash,
    ) as route:
        controller = _build_acq01_real_route_controller(
            case=case,
            route=route,
            simulation=_WorldBoundSimulation(),
            repo_root=tmp_path,
        )
        run = await controller.run(
            case.problem,
            budget_state=BudgetState(
                limits={"run": BudgetLimit(key="run", max_usd=Decimal("5.0"))}
            ),
            max_cycles=1,
        )
        receipt = AcquisitionReceipt.model_validate(run.acquisition_receipts[0])
        route_payload = dict(route.owner_artifact.payload)
        route_projection = dict(route_payload["acq01_route"])
        inline_registry = dict(route_projection["registry"])
        forged_version = "substrate_version_" + "f" * 16
        inline_registry["substrate_version_id"] = forged_version
        route_projection["registry"] = inline_registry
        route_payload["acq01_route"] = route_projection
        forged_owner = route.owner_artifact.model_copy(
            update={
                "payload": route_payload,
                "content_hash": gy_content_hash(route_payload),
            }
        )
        outcomes = list(receipt.world_write_outcomes)
        outcomes[0] = outcomes[0].model_copy(
            update={
                "substrate_version_after": forged_version,
                "world_ref_after": f"s0://substrate-registry/{forged_version}",
            }
        )
        tampered = receipt.model_copy(
            update={
                "owner_artifacts": (forged_owner,),
                "world_write_outcomes": tuple(outcomes),
                "grown_world_after_ref": f"s0://substrate-registry/{forged_version}",
            }
        )
        controller._cycle_substrate_context = case.before_context
        import polisyos.runtime.quality.substrate_registry as substrate_registry_module

        original_loader = substrate_registry_module.load_substrate_registry

        def forged_loader(store: Any, ref: Any) -> Any:
            loaded = original_loader(store, ref)
            registry_ref = route_projection["registry_ref"]["artifact_id"]
            if str(ref.artifact_id) == registry_ref:
                return loaded.model_copy(update={"substrate_version_id": forged_version})
            return loaded

        monkeypatch.setattr(
            substrate_registry_module,
            "load_substrate_registry",
            forged_loader,
        )
        with pytest.raises(
            generation_cycle_module.GenerationCycleError,
            match="n7_acq01_registry_binding_invalid",
        ):
            controller._rebuild_n7_acq01_route_context(
                case.problem,
                acquisition_receipt=tampered,
                candidate_id=case.candidate.candidate_id,
                candidate_content_hash=case.candidate.atom.content_hash,
                target_world_slots=tuple(case.candidate.atom.target_world_slots),
            )


@pytest.mark.asyncio
async def test_n7_acq01_reentry_does_not_dispatch_gateway_source_echo(
    tmp_path: Path,
) -> None:
    """Canonical replay ignores an untrusted same-ID source echo from the gateway.

    The canonical producer/replay mismatch witness remains covered by
    ``test_n9_measurement_rechecks_source_requirement_and_problem``; this ACQ
    route falsifier proves that a gateway echo cannot carry this gate.
    """

    from polisyos.runtime.quality.data_forge_binding import (
        _fabric_measurement_envelope,
        _measurement_root_evidence_fingerprint,
        _validate_resolved_measurement_root_evidence,
        resolve_measurement_root_evidence,
    )

    case = _real_acq01_inputs(tmp_path, problem_id="acq_01_tampered_source")
    with _real_acq01_route(
        tmp_path,
        case.problem,
        candidate_content_hash=case.candidate.atom.content_hash,
    ) as route:
        controller = _build_acq01_real_route_controller(
            case=case,
            route=route,
            simulation=_WorldBoundSimulation(),
            repo_root=tmp_path,
        )
        gateway = controller._acquisition_owner_gateway
        canonical_resolver = resolve_measurement_root_evidence
        invoked = False

        def altered_resolver(**kwargs: Any) -> Any:
            nonlocal invoked
            invoked = True
            evidence = canonical_resolver(**kwargs)
            source = evidence.payload.source_requirement
            altered_source = source.model_copy(
                update={
                    "scope": source.scope.model_copy(update={"geography": "ZZ"}),
                }
            )
            altered_payload = evidence.payload.model_copy(
                update={"source_requirement": altered_source}
            )
            execution_scope_binding = kwargs["execution_scope_binding"]
            altered_envelope = _fabric_measurement_envelope(
                altered_payload,
                evidence.envelope.payload_ref,
                execution_scope_binding=execution_scope_binding,
            )
            altered_fingerprint = _measurement_root_evidence_fingerprint(
                envelope=altered_envelope,
                payload=altered_payload,
                measurement_root_ref=evidence.measurement_root_ref,
                fetch_receipt_ref=evidence.fetch_receipt_ref,
                catalog_binding_ref=evidence.catalog_binding_ref,
            )
            altered = evidence.model_copy(
                update={
                    "envelope": altered_envelope,
                    "payload": altered_payload,
                    "evidence_fingerprint": altered_fingerprint,
                }
            )
            _validate_resolved_measurement_root_evidence(
                altered,
                store=kwargs["store"],
                execution_scope_binding=execution_scope_binding,
            )
            return altered

        gateway.resolve_measurement_root_evidence = altered_resolver
        run = await controller.run(
            case.problem,
            budget_state=BudgetState(
                limits={"run": BudgetLimit(key="run", max_usd=Decimal("5.0"))}
            ),
            max_cycles=1,
        )

        assert invoked is False
        _assert_n7_has_no_grounding_result(run.acquisition_receipts[0], cycle=run.cycles[0])


def test_n7_acq01_measurement_root_rejects_same_id_altered_source_requirement(
    tmp_path: Path,
) -> None:
    """The real MeasurementRoot producer rejects same-ID source drift."""

    from polisyos.runtime.quality.data_forge_binding import (
        FabricMeasurementRootBindingError,
        MeasurementRootProducer,
    )

    case = _real_acq01_inputs(tmp_path, problem_id="acq_01_source_requirement_drift")
    from tests._helpers.measurement_execution_binding import (
        measurement_execution_binding,
    )

    execution_scope_binding = measurement_execution_binding(tmp_path)
    with _real_acq01_route(
        tmp_path,
        case.problem,
        candidate_content_hash=case.candidate.atom.content_hash,
    ) as route:
        source_requirement = route.evidence.payload.source_requirement
        altered_source_requirement = source_requirement.model_copy(
            update={
                "scope": source_requirement.scope.model_copy(update={"geography": "ZZ"}),
            }
        )
        assert altered_source_requirement.requirement_id == source_requirement.requirement_id
        with pytest.raises(
            FabricMeasurementRootBindingError,
            match="measurement_root_source_requirement_mismatch",
        ):
            MeasurementRootProducer(
                artifact_store=route.store,
                execution_scope_binding=execution_scope_binding,
            ).produce_from_fabric_fetch(
                fetch_receipt_ref=route.evidence.payload.fetch_receipt_ref,
                catalog=route.catalog,
                providers=route.providers,
                design_problem=case.problem,
                source_requirement=altered_source_requirement,
            )


def test_n7_grounding_fails_closed_without_structural_dependency_membership() -> None:
    """A policy target slot cannot replace a missing data dependency edge."""

    from polisyos.runtime.quality.acquisition_planner import (
        _rederive_grounding_for_affected_region,
    )

    region = AcquisitionAffectedRegion(
        source_slots=("metric.test",),
        neighborhood_slots=("metric.test",),
        dependency_index={"metric.test": ("candidate_other",)},
        design_ids=("candidate_fixture_panel",),
        rederived_design_ids=("candidate_fixture_panel",),
        revalidation_stages={"candidate_fixture_panel": ("grounding",)},
        over_approximation_basis="test_dependency_membership",
    )
    rows = _rederive_grounding_for_affected_region(
        world=AcquisitionWorldSnapshot(world_ref="world://dependency-negative"),
        world_after_ref="world://dependency-negative/after",
        affected_region=region,
        owner_artifacts=(
            _fixture_owner_artifact(
                _fixture_data_requirement_spec().requirement_id,
                target_world_slots=("agents.income",),
            ),
        ),
        design_problem=_problem(problem_id="acq_01_dependency_negative"),
    )

    assert len(rows) == 1
    assert rows[0].status == "grounding_unavailable"
    assert rows[0].issue_codes == ("candidate_not_in_dependency_index",)


@pytest.mark.asyncio
async def test_n7_owner_write_reinvokes_simulation_port_without_claiming_grounding(
    tmp_path: Path,
) -> None:
    data_spec = _fixture_data_requirement_spec()
    registry = _fixture_world_registry()
    world = AcquisitionWorldSnapshot(
        world_ref="world://before/acq-01",
        known_slots=("fixture_panel",),
        dependency_index={"fixture_panel": ("candidate_fixture_panel",)},
        design_revalidation_stages={
            "candidate_fixture_panel": (
                "identification",
                "calibration",
                "value_set",
                "grounding",
            )
        },
        substrate_registry=registry.model_dump(mode="json"),
    )
    problem = _problem(
        problem_id="acq_01_fixture_reentry",
        runtime_hints={
            "n7_data_requirement_specs": (data_spec,),
            "n7_world_snapshot": world,
        },
    )
    simulation = _WorldBoundSimulation()
    candidate = _fixture_candidate(problem, world_ref=world.world_ref)
    controller = GenerationCycleController(
        generation_port=_FixtureGenerationPort(),
        grounding_port=_FixtureAcquisitionGrounding(),
        simulation_port=simulation,
        value_port=_PendingFixtureValue(),
        acquisition_owner_gateway=RecordedAcquisitionOwnerGateway(
            artifacts_by_requirement={
                data_spec.requirement_id: _fixture_owner_artifact(
                    data_spec.requirement_id,
                    candidate_content_hash=candidate.atom.content_hash,
                )
            }
        ),
        measurement_root_execution_binding=_contract_testing_measurement_root_binding(tmp_path),
        authority_scope="contract_testing",
    )

    run = await controller.run(
        problem,
        budget_state=BudgetState(limits={"run": BudgetLimit(key="run", max_usd=Decimal("5.0"))}),
        max_cycles=1,
    )

    assert len(run.acquisition_receipts) == 1
    cycle = run.cycles[0]
    receipt = run.acquisition_receipts[0]
    _assert_n7_has_no_grounding_result(receipt, cycle=cycle)
    assert receipt["grown_world_after_ref"] != world.world_ref
    assert receipt["world_write_outcomes"][0]["status"] == "written"
    assert simulation.world_refs == [world.world_ref, receipt["grown_world_after_ref"]]
    assert run.cycles[0].selected_candidate_content_hash == run.candidate_summaries[0].content_hash
    assert run.cycles[0].selected_candidate_content_hash != candidate.atom.content_hash
    assert run.candidate_summaries[0].source_content_hash == candidate.atom.content_hash
    assert run.cycles[0].simulation.simulation_ref == (
        f"fixture-simulation:{receipt['grown_world_after_ref']}"
    )

    # A later overlay restore must project the persisted N4 identity (H0),
    # not the rebound world-bound occurrence (H1), into source custody.
    controller._restore_source_run(run)
    assert controller._source_expected_identities == [
        (
            run.design_problem_ref,
            candidate.candidate_id,
            candidate.atom.content_hash,
        )
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "binding_mode",
    [
        pytest.param("foreign_hash", id="foreign_hash"),
        pytest.param("foreign_target_slots", id="foreign_target_slots"),
    ],
)
async def test_n7_reentry_rejects_semantically_foreign_owner_binding(
    tmp_path: Path,
    binding_mode: str,
) -> None:
    """A same-ID owner artifact cannot rebind a foreign candidate occurrence."""

    data_spec = _fixture_data_requirement_spec()
    registry = _fixture_world_registry()
    world = AcquisitionWorldSnapshot(
        world_ref="world://before/acq-01",
        known_slots=("fixture_panel",),
        dependency_index={"fixture_panel": ("candidate_fixture_panel",)},
        design_revalidation_stages={
            "candidate_fixture_panel": (
                "identification",
                "calibration",
                "value_set",
                "grounding",
            )
        },
        substrate_registry=registry.model_dump(mode="json"),
    )
    problem = _problem(
        problem_id="acq_01_fixture_binding_rejection",
        runtime_hints={
            "n7_data_requirement_specs": (data_spec,),
            "n7_world_snapshot": world,
        },
    )
    candidate = _fixture_candidate(problem, world_ref=world.world_ref)
    foreign_hash = (
        "sha256:" + "f" * 64
        if candidate.atom.content_hash != "sha256:" + "f" * 64
        else "sha256:" + "e" * 64
    )
    binding_hash = (
        candidate.atom.content_hash if binding_mode == "foreign_target_slots" else foreign_hash
    )
    binding_slots = (
        ("fixture_panel", "forged_panel")
        if binding_mode == "foreign_target_slots"
        else ("fixture_panel",)
    )
    expected_error = (
        "n7_reentry_candidate_target_world_slots_mismatch"
        if binding_mode == "foreign_target_slots"
        else "n7_reentry_candidate_binding_mismatch"
    )
    controller = GenerationCycleController(
        generation_port=_FixtureGenerationPort(),
        grounding_port=_FixtureAcquisitionGrounding(),
        simulation_port=_WorldBoundSimulation(),
        value_port=_PendingFixtureValue(),
        acquisition_owner_gateway=RecordedAcquisitionOwnerGateway(
            artifacts_by_requirement={
                data_spec.requirement_id: _fixture_owner_artifact(
                    data_spec.requirement_id,
                    candidate_content_hash=binding_hash,
                    target_world_slots=binding_slots,
                )
            }
        ),
        measurement_root_execution_binding=_contract_testing_measurement_root_binding(tmp_path),
        authority_scope="contract_testing",
    )

    with pytest.raises(
        generation_cycle_module.GenerationCycleError,
        match=expected_error,
    ):
        await controller.run(
            problem,
            budget_state=BudgetState(
                limits={"run": BudgetLimit(key="run", max_usd=Decimal("5.0"))}
            ),
            max_cycles=1,
        )


@pytest.mark.asyncio
async def test_n7_reentry_does_not_run_n5_from_registry_only_world_ref(
    tmp_path: Path,
) -> None:
    """A registry URI cannot substitute for a content-bound WMR/context."""

    data_spec = _fixture_data_requirement_spec()
    registry = _fixture_world_registry()
    problem = _problem(
        problem_id="acq_01_registry_only_reentry",
        runtime_hints={
            "n7_data_requirement_specs": (data_spec,),
            "joint_simulation_resource": "method_registry_estimator",
            "joint_simulation_budget_ref": "budget://acq-01/registry-only-reentry",
            "joint_simulation_horizon": {"start": 0, "end": 1, "step": 1},
        },
    )
    world = generation_cycle_module._build_boundary_world_model_record(
        repo_root=REPO_ROOT,
        problem=problem,
        outcome="firm_survival",
        policy_slot_ids=("fixture_panel",),
        substrate_registry=registry,
        selected_registry_entry_hashes=(registry.entries[0].entry_content_hash,),
    )
    problem_ref = gy_content_hash(problem.model_dump(mode="json"))
    context = build_cycle_substrate_context(
        design_problem_ref=problem_ref,
        domain=problem.domain,
        substrate_registry=registry,
        selected_registry_entry_hashes=(registry.entries[0].entry_content_hash,),
        world_model_record=world,
        intervention_substrate=None,
        candidate_levers=(),
        transport_context=None,
        source_pack_content_hash=None,
        substrate_input_content_hash=None,
    )
    assert {
        "grounding_authority",
        "transport_authority",
        "promotion_authority",
    }.issubset(context.may_not_use_for)

    class _BoundFixtureGenerationPort:
        async def __call__(self, current: DesignProblem, *, cycle_index: int) -> Any:
            del cycle_index
            candidate = _fixture_candidate(
                current,
                world_ref=world.world_model_record_id,
            )
            return SimpleNamespace(
                status="generated",
                candidates=(candidate,),
                surrogate_rankings=(
                    SimpleNamespace(
                        candidate_id=candidate.candidate_id,
                        score=0.95,
                        voi_estimate=0.95,
                    ),
                ),
                grounding_dispositions=(),
            )

    class _RecordingN5Controller:
        def __init__(self) -> None:
            self.requests: list[object] = []
            self._delegate = generation_cycle_module.JointSimulationHorizonController()

        def run(self, request: object) -> Any:
            self.requests.append(request)
            return self._delegate.run(request)

    n5 = _RecordingN5Controller()
    controller = GenerationCycleController(
        generation_port=_BoundFixtureGenerationPort(),
        grounding_port=_FixtureAcquisitionGrounding(),
        simulation_port=JointSimulationPort(
            controller=n5,
            repo_root=tmp_path,
            cycle_substrate_context=context,
            artifact_store=FileSystemCAS(tmp_path / "n5-result-store"),
        ),
        value_port=_PendingFixtureValue(),
        acquisition_owner_gateway=RecordedAcquisitionOwnerGateway(
            artifacts_by_requirement={
                data_spec.requirement_id: _fixture_owner_artifact(
                    data_spec.requirement_id,
                    candidate_content_hash=_fixture_candidate(
                        problem,
                        world_ref=world.world_model_record_id,
                    ).atom.content_hash,
                )
            }
        ),
        repo_root=tmp_path,
        cycle_substrate_context=context,
        measurement_root_execution_binding=_contract_testing_measurement_root_binding(tmp_path),
        authority_scope="contract_testing",
    )

    run = await controller.run(
        problem,
        budget_state=BudgetState(limits={"run": BudgetLimit(key="run", max_usd=Decimal("5.0"))}),
        min_cycles=1,
        max_cycles=1,
    )

    cycle = run.cycles[0]
    receipt = cycle.acquisition_receipt
    assert receipt is not None
    _assert_n7_has_no_grounding_result(receipt, cycle=cycle)
    grown_world_ref = receipt["grown_world_after_ref"]
    assert grown_world_ref.startswith("s0://substrate-registry/")
    assert grown_world_ref != context.world_model_record_content_hash
    assert grown_world_ref != context.world_model_record.world_model_record_id
    # The initial N5 request has the selected content-bound context. The
    # post-write registry URI is refused before the numerical controller.
    assert len(n5.requests) == 1
    assert n5.requests[0].world_model_record_ref == context.world_model_record.world_model_record_id
    assert n5.requests[0].world_model_record.content_hash == context.world_model_record.content_hash
    assert cycle.simulation.status == "simulation_blocked"
    assert "world_identity_unresolved" in cycle.simulation.authority_blockers
    assert cycle.simulation.simulation_ref is None


@pytest.mark.asyncio
async def test_n7_acq01_reentry_rejects_self_labeled_grounding_mapping(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A mapping that labels itself canonical cannot substitute for the owner DTO."""

    case = _real_acq01_inputs(tmp_path, problem_id="acq_01_self_labeled_grounding_mapping")
    with _real_acq01_route(
        tmp_path,
        case.problem,
        candidate_content_hash=case.candidate.atom.content_hash,
    ) as route:
        simulation = _ContextRecordingSimulation()
        controller = _build_acq01_real_route_controller(
            case=case,
            route=route,
            simulation=simulation,
            repo_root=tmp_path,
        )
        invoked: list[bool] = []
        malformed_present_result = {
            "type": "AcquisitionGroundingRederivation",
            "design_id": case.candidate.candidate_id,
            "source_slots": (),
            "status": "grounding_unavailable",
            "grounding_score": 0.0,
            "report_ref": None,
            "evidence_refs": (),
            "issue_codes": (),
        }

        def return_self_labeled_mapping(*args: Any, **kwargs: Any) -> object:
            invoked.append(True)
            return malformed_present_result

        monkeypatch.setattr(
            generation_cycle_module,
            "_n7_rederived_grounding_for_candidate",
            return_self_labeled_mapping,
        )
        with pytest.raises(
            generation_cycle_module.GenerationCycleError,
            match="N7 grounding rederivation is not the canonical owner result",
        ) as exc_info:
            await controller.run(
                case.problem,
                budget_state=BudgetState(
                    limits={"run": BudgetLimit(key="run", max_usd=Decimal("5.0"))}
                ),
                max_cycles=1,
            )

        assert exc_info.value.code == "n7_receipt_invalid"
        assert invoked == [True]
        # The valid recorded route ran its initial simulation, but the forged
        # self-label did not trigger a second simulation or cycle re-entry.
        assert len(simulation.observations) == 1


def test_n7_core_json_readers_preserve_base_store_refusal_boundary(
    tmp_path: Path,
) -> None:
    """Real CoreJSON readers work; base-only stores refuse before reading."""

    from polisyos.common.canonical_profile import CanonicalProfileRefusalError
    from polisyos.core.artifacts.backends.caching_store import CachingArtifactStore
    from polisyos.runtime.quality.data_forge_binding import (
        FabricMeasurementRootBindingError,
        MeasurementRootBindingError,
        resolve_fabric_measurement_root,
        resolve_measurement_root_evidence,
        verify_recorded_panel_method_input,
    )

    case = _real_acq01_inputs(tmp_path, problem_id="acq_01_core_json_store_boundary")
    with _real_acq01_route(
        tmp_path,
        case.problem,
        candidate_content_hash=case.candidate.atom.content_hash,
    ) as route:
        reader_store = CachingArtifactStore(
            remote=route.store,
            local=FileSystemCAS(tmp_path / "core-json-reader-cache"),
            write_through=True,
        )
        real_evidence = resolve_measurement_root_evidence(
            store=reader_store,
            measurement_root=route.measurement_root,
            catalog=route.catalog,
            providers=route.providers,
            execution_scope_binding=route.execution_scope_binding,
        )
        assert real_evidence == route.evidence

        base_only = _BaseOnlyArtifactStore(reader_store)
        with pytest.raises(FabricMeasurementRootBindingError) as evidence_refusal:
            resolve_measurement_root_evidence(
                store=base_only,
                measurement_root=route.measurement_root,
                catalog=route.catalog,
                providers=route.providers,
                execution_scope_binding=route.execution_scope_binding,
            )
        assert evidence_refusal.value.code == "measurement_root_custody_unresolved"
        assert base_only.read_calls == 0

        selected_profile = route.measurement_root.payload_manifest_profile_sha256
        assert selected_profile is not None
        with pytest.raises(CanonicalProfileRefusalError) as resolver_refusal:
            resolve_fabric_measurement_root(
                store=base_only,
                source_artifact_id=route.measurement_root.payload_ref,
                manifest_profile_sha256=selected_profile,
                catalog=route.catalog,
                providers=route.providers,
                execution_scope_binding=route.execution_scope_binding,
            )
        assert resolver_refusal.value.code == "canon_profile_raw_manifest_unavailable"
        assert base_only.read_calls == 0

        recorded_binding_ref = CASArtifactRef(
            artifact_id=route.evidence.measurement_root_ref.artifact_id,
            kind="runtime.recorded_panel_method_binding",
            media_type="application/json",
        )
        with pytest.raises(MeasurementRootBindingError) as recorded_refusal:
            verify_recorded_panel_method_input(
                store=base_only,
                binding_receipt_ref=recorded_binding_ref,
            )
        assert str(recorded_refusal.value) == "recorded_binding_unreadable"
        assert base_only.read_calls == 0


def test_acq01_fixture_reuses_selected_store_and_prior_owner_context(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The fixture preserves selected inputs without claiming N7 reentry."""
    from polisyos.core.artifacts.store import FileSystemCAS
    from tests._helpers.measurement_execution_binding import measurement_execution_binding

    problem = _problem(problem_id="acq01_selected_owner_fixture")
    store = FileSystemCAS(tmp_path / "selected-cas")
    prior = _real_acq01_before_context(tmp_path, problem, artifact_store=store)
    candidate = _fixture_candidate(
        problem,
        world_ref=prior.world_model_record.world_model_record_id,
        target_world_slots=("agents.income",),
        candidate_id="candidate_metric_test",
    )
    binding = measurement_execution_binding(tmp_path)
    with _real_acq01_route(
        tmp_path,
        problem,
        candidate_content_hash=candidate.atom.content_hash,
        artifact_store=store,
        execution_scope_binding=binding,
        prior_context=prior,
        selected_metric="gdp",
    ) as route:
        assert route.store is store
        assert route.execution_scope_binding is binding
        payload = route.owner_artifact.payload["acq01_route"]
        assert payload["build_inputs"]["required_substrate_families"] == ["gdp"]
        assert payload["build_inputs"]["policy_slot_ids"] == [
            row.slot_id for row in prior.world_model_record.policy_slot_map
        ]
        for field in (
            "region_or_jurisdiction",
            "population_scope",
            "policy_domain",
            "valid_time_scope",
            "tx_time_scope",
            "resolution",
            "branch_mode",
        ):
            assert getattr(route.world_build.record, field) == getattr(
                prior.world_model_record, field
            )
        assert route.world_build.record.policy_slot_map == prior.world_model_record.policy_slot_map
        assert store.get_bytes(route.data_snapshot_ref)
        assert store.get_bytes(route.registry_ref)

    with (
        pytest.raises(ValueError, match="acq01_fixture_selected_metric_mismatch"),
        _real_acq01_route(
            tmp_path / "wrong",
            problem,
            candidate_content_hash=candidate.atom.content_hash,
            selected_metric="not-the-catalog-metric",
        ),
    ):
        raise AssertionError("the mismatched selected metric must refuse before fetch")

    foreign_problem = _problem(problem_id="acq01_foreign_problem")
    with (
        pytest.raises(ValueError, match="acq01_fixture_prior_context_problem_mismatch"),
        _real_acq01_route(
            tmp_path / "foreign",
            foreign_problem,
            candidate_content_hash=candidate.atom.content_hash,
            artifact_store=store,
            prior_context=prior,
            selected_metric="gdp",
        ),
    ):
        raise AssertionError("the foreign problem must refuse before fetch")

    # Build a real alternate registry with the same slot IDs and a different
    # binding. The producer mutation changes the actual selected bundle, not
    # the prior-world declaration; the full-slot comparison must refuse.
    from polisyos.core.registry import build_registry_bundle
    from polisyos.ir.kernel import (
        DEFAULT_CONSTRAINT_REGISTRY,
        DEFAULT_MECHANISM_REGISTRY,
        DEFAULT_MERGE_RULE_REGISTRY,
        DEFAULT_METRIC_REGISTRY,
        DEFAULT_SELECTOR_FIELD_REGISTRY,
        DEFAULT_SLOT_REGISTRY,
        DEFAULT_UNITS_REGISTRY,
        SlotKind,
    )
    from polisyos.runtime.quality import world_model_record as world_owner

    slots = dict(DEFAULT_SLOT_REGISTRY.slots)
    original_slot = slots["agents.income"]
    other_kind = SlotKind.FLOW if original_slot.kind != SlotKind.FLOW else SlotKind.STOCK
    slots["agents.income"] = original_slot.model_copy(update={"kind": other_kind})
    altered_registry = DEFAULT_SLOT_REGISTRY.model_copy(update={"slots": slots})
    alternate = build_registry_bundle(
        store,
        slot_registry=altered_registry,
        merge_registry=DEFAULT_MERGE_RULE_REGISTRY,
        mechanism_registry=DEFAULT_MECHANISM_REGISTRY,
        constraint_registry=DEFAULT_CONSTRAINT_REGISTRY,
        selector_field_registry=DEFAULT_SELECTOR_FIELD_REGISTRY,
        metric_registry=DEFAULT_METRIC_REGISTRY,
        units_registry=DEFAULT_UNITS_REGISTRY,
    )
    real_world_build = world_owner.build_world_model_record

    def build_with_wrong_slots(*args: Any, **kwargs: Any) -> Any:
        kwargs["model_spec"] = kwargs["model_spec"].model_copy(
            update={"registry_bundle_ref": str(alternate.bundle_ref.artifact_id)}
        )
        kwargs["registry_bundle_artifact_ref"] = alternate.bundle_ref
        built = real_world_build(*args, **kwargs)
        assert [row.slot_id for row in built.record.policy_slot_map] == [
            row.slot_id for row in prior.world_model_record.policy_slot_map
        ]
        assert built.record.policy_slot_map != prior.world_model_record.policy_slot_map
        return built

    with monkeypatch.context() as local:
        local.setattr(world_owner, "build_world_model_record", build_with_wrong_slots)
        with (
            pytest.raises(ValueError, match="acq01_fixture_prior_slot_binding_mismatch"),
            _real_acq01_route(
                tmp_path / "wrong-slots",
                problem,
                candidate_content_hash=candidate.atom.content_hash,
                artifact_store=store,
                execution_scope_binding=binding,
                prior_context=prior,
                selected_metric="gdp",
            ),
        ):
            raise AssertionError("the changed same-ID slot binding must refuse")
