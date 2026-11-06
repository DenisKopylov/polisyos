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
from typing import Any, Literal, cast

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
    DESIGN_PROBLEM_V3_SCHEMA_VERSION,
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


class _RecordingN5Controller(n5_horizon.JointSimulationHorizonController):
    """Record requests while retaining the canonical N5 controller lifecycle."""

    def __init__(self) -> None:
        super().__init__()
        self.requests: list[Any] = []

    def run(self, request: Any) -> Any:
        self.requests.append(request)
        return super().run(request)


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
    expected_grounding_status: Literal["grounding_unavailable", "grounding_gap"] = (
        "grounding_unavailable"
    ),
    expected_cycle_grounding_issue_codes: tuple[str, ...] = (
        "generation_result_problem_scope_unestablished",
    ),
) -> None:
    """Keep owner writes distinct from both receipt and re-entry grounding."""

    assert receipt["status"] == "completed_no_results"
    rows = receipt["grounding_rederivations"]
    assert len(rows) == 1
    assert tuple(rows[0]["issue_codes"]) == ("generation_result_problem_scope_unestablished",)
    assert cycle.grounding.status == expected_grounding_status
    assert tuple(cycle.grounding.issue_codes) == expected_cycle_grounding_issue_codes


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


class _Acq01MacroContextGrounding:
    """Bind the candidate's missing macro-context route to its real test inputs."""

    def __init__(self, *, case: Any, route: Any) -> None:
        from polisyos.runtime.quality.acquisition_planner import (
            grounding_coverage_requirement_gap,
            persist_and_verify_data_requirement_compilation_report,
        )

        self._case = case
        self._route = route
        self._gap_builder = grounding_coverage_requirement_gap
        self.issue_code = f"acquire_data:{case.data_spec.required_data_families[0]}"
        self.compiler_report_binding = persist_and_verify_data_requirement_compilation_report(
            route.store,
            case.compiler_report,
            expected_scenario_id=case.problem.design_problem_id,
        )
        self.report_ref: CASArtifactRef | None = None

    def __call__(
        self,
        *,
        candidate: Any,
        problem: DesignProblem,
        cycle_index: int,
        generation_result: Any | None = None,
    ) -> CandidateGroundingObservation:
        del cycle_index, generation_result
        candidate_id = str(candidate.candidate_id)
        candidate_hash = generation_cycle_module._candidate_content_hash(candidate)
        problem_ref = gy_content_hash(problem.model_dump(mode="json"))
        if (
            candidate_id != self._case.candidate.candidate_id
            or candidate_hash
            != generation_cycle_module._candidate_content_hash(self._case.candidate)
            or problem_ref != gy_content_hash(self._case.problem.model_dump(mode="json"))
        ):
            raise AssertionError("acq01_macro_context_grounding_subject_mismatch")

        measurement_root_ref = self._route.evidence.measurement_root_ref
        data_snapshot_ref = self._route.data_snapshot_ref
        evidence_refs = (
            f"cas://{measurement_root_ref.artifact_id}",
            f"cas://{data_snapshot_ref.artifact_id}",
        )
        payload = {
            "schema_version": "test.policyos.acq01.macro_context_grounding.v1",
            "authority_purpose": "candidate_routing_only",
            "authority_scope": "contract_testing",
            "claim_evidence_use_allowed": False,
            "candidate_binding": {
                "candidate_id": candidate_id,
                "candidate_content_hash": candidate_hash,
            },
            "design_problem_ref": problem_ref,
            "grounding_status": "grounding_gap",
            "issue_codes": [self.issue_code],
            "required_macro_context": {
                "construct_ref": "construct:economic.gdp",
                "compiled_requirement_ref": self._case.data_spec.requirement_id,
                "compiled_requirement_family": self._case.data_spec.required_data_families[0],
                "compiler_report_schema_version": self._case.compiler_report.schema_version,
                "compiler_input_content_hash": self._case.compiler_report.input_content_hash,
                "compiler_report_ref": self.compiler_report_binding.compiler_report_ref.model_dump(
                    mode="json"
                ),
                "compiler_report_digest": self.compiler_report_binding.compiler_report_digest,
                "basis_source": self._case.compiler_report.requirement_basis.source,
                "basis_grade": self._case.compiler_report.requirement_basis.basis_grade,
            },
            "observed_source_context": {
                "measurement_root_ref": measurement_root_ref.model_dump(mode="json"),
                "data_snapshot_ref": data_snapshot_ref.model_dump(mode="json"),
                "source_requirement_ref": self._route.source_requirement.requirement_id,
                "dataset_id": self._route.plan.dataset_id,
            },
            "evidence_refs": [
                measurement_root_ref.model_dump(mode="json"),
                data_snapshot_ref.model_dump(mode="json"),
            ],
            "causal_scope": {
                "macro_context_is_employment_outcome": False,
                "gdp_to_employment_causal_effect_claimed": False,
            },
            "source_authority_status": "not_established",
            "source_currentness_status": "not_established",
        }
        report_ref = self._route.store.put_json(
            payload,
            ArtifactWriteOptions(
                kind="test.policyos.acq01.macro_context_grounding_report",
                media_type="application/json",
            ),
            return_selected_profile=True,
        )
        self.report_ref = report_ref
        report_locator = f"cas://{report_ref.artifact_id}"
        requirement = self._gap_builder(
            candidate_id=candidate_id,
            candidate_content_hash=candidate_hash,
            design_problem_ref=problem_ref,
            issue_codes=(self.issue_code,),
            evidence_refs=evidence_refs,
            authority_level=problem.authority_profile.requested_authority_level,
            grounding_report_ref=report_locator,
        )
        return CandidateGroundingObservation(
            candidate_id=candidate_id,
            status="grounding_gap",
            grounding_score=0.1,
            issue_codes=(self.issue_code,),
            evidence_refs=evidence_refs,
            current_valid=False,
            report_ref=report_locator,
            acquisition_requirement=requirement,
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
    registry = _fixture_world_registry(include_candidate_l2=True)
    selected_l2_hashes = tuple(
        entry.entry_content_hash for entry in registry.entries if entry.layer is SubstrateLayer.L2
    )
    assert len(selected_l2_hashes) == 1
    world = generation_cycle_module._build_boundary_world_model_record(
        repo_root=REPO_ROOT,
        problem=problem,
        outcome="firm_survival",
        policy_slot_ids=("fixture_panel",),
        substrate_registry=registry,
        selected_registry_entry_hashes=selected_l2_hashes,
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


def _fixture_world_registry(*, include_candidate_l2: bool = False) -> Any:
    baseline = _fixture_registration(
        source_id="baseline.fixture_panel",
        snapshot_id="baseline:fixture_panel",
    )
    entries = [build_substrate_registry_entry(baseline)]
    if include_candidate_l2:
        candidate_prior = SubstrateRegistration(
            source_id="candidate.acq01.fixture_panel_l2",
            family_id="fixture_panel_causal_prior_candidate",
            layer=SubstrateLayer.L2,
            coverage=SubstrateCoverage(
                coverage_score=0.0,
                coverage_kind="acq01.explicit_candidate_l2_prior",
                coverage_rule_ref="test://coverage/acq-01/candidate-l2-not-authority",
                dataset_count=0,
                metric_binding_count=0,
                observation_count=0,
            ),
            trust_tier=SubstrateTrustTier(
                tier="candidate_only",
                trust_cap=0.0,
                trust_multiplier=0.0,
                min_coverage=0.0,
                max_coverage=1.0,
                authority_ref="test://authority/acq-01/candidate-l2-not-authority",
            ),
            identification_mode="causal_prior_candidate",
            schema_regime=SubstrateSchemaRegime(
                schema_regime_id="acq01_candidate_l2_fixture_v1",
                authority_ref="test://schema/acq-01/candidate-l2-not-authority",
                source_version="fixture-v1",
            ),
            data_version="acq01-candidate-l2-fixture-v1",
            snapshot_id="acq01-candidate-l2-fixture-v1",
            source_snapshot_id="acq01-candidate-l2-fixture-v1",
            provenance_refs=("test://acq-01/candidate-l2-prior",),
            authority_refs=("test://acq-01/candidate-l2-not-authority",),
        )
        entries.append(build_substrate_registry_entry(candidate_prior))
    return build_substrate_registry(
        tuple(entries),
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
    geography: str = "DE",
    metric: str = "gdp_per_capita",
    time_start: str = "2020",
    time_end: str = "2020",
) -> Iterator[Any]:
    """Resolve and fetch one bounded publisher-fixture WDI source."""
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
        if metric == "gdp":
            # The recorded owner has two genuine country rows. Bind this test's
            # declared single-country request to that country in the catalog
            # fixture rather than accepting an unfiltered US+DE payload.
            alternate_record = alternate_record.model_copy(
                update={
                    "distributions": [
                        distribution.model_copy(
                            update={"default_filters": {"country": [geography]}}
                        )
                        for distribution in alternate_record.distributions
                    ]
                }
            )
        alternate_plan = recorded.plan.model_copy(deep=True)
        alternate_rows = tuple(
            row
            for page in sorted(recorded.http_responses)
            for row in recorded.http_responses[page][1]
        )
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
                    if metric == "gdp_per_capita" and not rows:
                        raise AssertionError("published_wdi_observations_missing")
                    old_request = WorldBankConnector._request_json

                    async def request_json(
                        session: Any, url: str, *, params: Any, connector_id: str
                    ):
                        indicator_id = url.split("/indicator/", 1)[-1]
                        if indicator_id not in {
                            "NY.GDP.PCAP.PP.CD",
                            "NY.GDP.MKTP.CD",
                        }:
                            return await old_request(
                                session, url, params=params, connector_id=connector_id
                            )
                        country_path = url.split("/country/", 1)[1].split("/indicator/", 1)[0]
                        countries = set(country_path.upper().split(";"))
                        if indicator_id == "NY.GDP.PCAP.PP.CD":
                            selected_rows = [
                                (country, year, value)
                                for country, year, value in rows
                                if "ALL" in countries or country in countries
                            ]
                        else:
                            iso2_by_iso3 = {"USA": "US", "DEU": "DE"}
                            iso2_to_iso3 = {value: key for key, value in iso2_by_iso3.items()}
                            requested_iso3 = {
                                iso2_to_iso3.get(country, country) for country in countries
                            }
                            selected_rows = [
                                (
                                    iso2_by_iso3[str(row["countryiso3code"])],
                                    int(row["date"]),
                                    float(row["value"]),
                                )
                                for row in alternate_rows
                                if row.get("countryiso3code") in iso2_by_iso3
                                and ("ALL" in countries or row["countryiso3code"] in requested_iso3)
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
                        iso3 = {
                            "UA": "UKR",
                            "DE": "DEU",
                            "PL": "POL",
                            "RO": "ROU",
                            "MD": "MDA",
                            "US": "USA",
                        }
                        indicator_name = (
                            "GDP per capita, PPP (synthetic fixture)"
                            if indicator_id == "NY.GDP.PCAP.PP.CD"
                            else "GDP (current US$) (synthetic fixture)"
                        )
                        result = [
                            {
                                "indicator": {
                                    "id": indicator_id,
                                    "value": indicator_name,
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
                        metric=metric,
                        geography=geography,
                        time_start=time_start,
                        time_end=time_end,
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
                    expected_plan = (
                        (
                            "gdp_per_capita",
                            "NY.GDP.PCAP.PP.CD",
                            "worldbank.wdi",
                            "worldbank_wdi",
                        )
                        if metric == "gdp_per_capita"
                        else ("gdp", "NY.GDP.MKTP.CD", "worldbank.wdi", "worldbank_wdi")
                    )
                    if (
                        plan.metric_id,
                        plan.dataset_id,
                        plan.connector_id,
                        plan.profile_id,
                    ) != expected_plan:
                        raise AssertionError("published_wdi_plan_identity_mismatch")
                    # The Catalog fallback returns an unfiltered plan. Submit the
                    # need's explicit country to the actual connector and bind
                    # that exact scoped tuple through the Catalog owner.
                    default_countries = tuple(plan.filters.get("country", ()))
                    if default_countries and need.geography not in default_countries:
                        raise AssertionError("published_wdi_default_country_scope_mismatch")
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
    data_spec_override: DataRequirementSpec | None = None,
    compiled_requirement_family: str | None = None,
    world_model_scope: Mapping[str, str] | None = None,
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

    family = compiled_requirement_family or (
        selected_metric if selected_metric is not None else "metric.test"
    )
    if data_spec_override is None:
        data_spec = _fixture_data_requirement_spec().model_copy(
            update={
                "requirement_id": requirement_ref,
                "claim_id": f"claim:{requirement_ref.removeprefix('data-requirement:')}",
                "required_data_families": (family,),
            }
        )
    else:
        expected_compiled_family = compiled_requirement_family or family
        if (
            data_spec_override.requirement_id != requirement_ref
            or data_spec_override.required_data_families != (expected_compiled_family,)
        ):
            raise ValueError("acq01_fixture_compiled_data_spec_binding_mismatch")
        data_spec = data_spec_override.model_copy(deep=True)
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
        scope_overrides = world_model_scope or {}
        region = (
            prior_world.region_or_jurisdiction
            if prior_world is not None
            else scope_overrides.get("region_or_jurisdiction", "UA-30")
        )
        population = (
            prior_world.population_scope
            if prior_world is not None
            else scope_overrides.get("population_scope", "recorded_file_tabular_fixture")
        )
        domain = (
            prior_world.policy_domain
            if prior_world is not None
            else scope_overrides.get("policy_domain", "fiscal_credit")
        )
        valid_time = (
            prior_world.valid_time_scope if prior_world is not None else "2026-09-22/2026-09-22"
        )
        if prior_world is None:
            valid_time = scope_overrides.get("valid_time_scope", valid_time)
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
            source_requirement=source_requirement,
            plan=owner.plan,
            data_need=getattr(owner, "data_need", None),
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
            ),
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
    additional_policy_slot_ids: tuple[str, ...] = (),
    world_model_scope: Mapping[str, str] | None = None,
) -> Any:
    """Build the content-bound pre-acquisition context from existing owners."""

    from polisyos.runtime.quality.world_model_record import build_world_model_record
    from tests._helpers.world_model_record import (
        _build_record,
        _fabric_ref,
        _skg_ref,
        _substrate_registry,
        _write_data_forge_binding,
    )

    owner_root = tmp_path / "before"
    store, world_build, model_spec, registry_bundle_ref = _build_record(
        owner_root,
        artifact_store=artifact_store,
    )
    registry = _substrate_registry()
    if additional_policy_slot_ids or world_model_scope:
        prior = world_build.record
        scope = world_model_scope or {}
        world_build = build_world_model_record(
            store,
            fabric_world_ref=_fabric_ref(owner_root),
            data_forge_snapshot_binding_path=_write_data_forge_binding(owner_root),
            data_snapshot_ref=world_build.data_snapshot_ref,
            model_spec=model_spec,
            skg_causal_prior_ref=_skg_ref(owner_root),
            substrate_registry=registry,
            region_or_jurisdiction=scope.get(
                "region_or_jurisdiction", prior.region_or_jurisdiction
            ),
            population_scope=scope.get("population_scope", prior.population_scope),
            policy_domain=scope.get("policy_domain", prior.policy_domain),
            valid_time_scope=scope.get("valid_time_scope", prior.valid_time_scope),
            tx_time_scope=prior.tx_time_scope,
            resolution=prior.resolution,
            branch_mode=prior.branch_mode,
            policy_slot_ids=tuple(
                dict.fromkeys(
                    (
                        *(binding.slot_id for binding in prior.policy_slot_map),
                        *additional_policy_slot_ids,
                    )
                )
            ),
            producer_ref="tests.unit.remediation.test_acq_01.real_before_context",
            required_substrate_families=tuple(
                dict.fromkeys(entry.family_id for entry in registry.entries)
            ),
            substrate_registry_artifact_ref=prior.substrate_registry_ref.registry_artifact_ref,
            registry_bundle_artifact_ref=registry_bundle_ref,
            _loaded_substrate_registry=registry,
        )
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


def _real_acq01_macro_context_case(
    tmp_path: Path,
    *,
    problem_id: str = "acq_01_real_ports",
) -> Any:
    """Build the employment case with a compiler-grounded nominal-GDP context need."""

    from polisyos.data_requirement import DATA_REQUIREMENT_COMPILATION_SCHEMA_VERSION
    from polisyos.runtime.quality.capability_resolver import RequirementToCapabilityResolver
    from polisyos.runtime.quality.intervention_atom_binding import (
        intervention_atom_content_hash,
    )

    source_family = "wdi_nominal_gdp_annual"
    runtime_hints = {
        "joint_simulation_resource": "method_registry_estimator",
        "joint_simulation_budget_ref": "budget://acq-01/real-ports",
        "joint_simulation_horizon": {"start": 0, "end": 1, "step": 1},
        "joint_simulation_baseline_state": {"employment_retention": 1.0},
        "joint_simulation_variable_map": {"employment_retention": "stock:0"},
        "n7_scope_profile": {
            "profile_id": f"{problem_id}-macro-context-v1",
            "jurisdiction": "US",
            "population": "national_economy",
            "entity_scope": "country",
            "time_window": {"start": "2022-01-01", "end": "2022-12-31"},
            "time_role": "observation_time",
            "granularity": "annual",
            "required_constructs": ["economic.gdp"],
        },
        "joint_simulation_engine_plan": {
            "method_fqn": "simulation.system_dynamics.stock_flow@1.0.0",
            "system_dynamics_state": {
                "initial_stocks": [1.0, 0.0],
                "flow_matrix": [[0.0, 0.1], [0.0, 0.0]],
                "exogenous_inflows": [0.0, 0.0],
            },
            "system_dynamics_params": {"dt": 1.0},
        },
    }
    problem = _problem(
        problem_id=problem_id,
        statement=(
            "Assess a synthetic U.S. tax-relief candidate for employment retention. "
            "Acquire 2022 U.S. nominal GDP as separate macro context; it is not the "
            "employment outcome or a causal effect on jobs."
        ),
        domain="fiscal_credit",
        runtime_hints=runtime_hints,
    )
    problem = problem.model_copy(
        update={
            "schema_version": DESIGN_PROBLEM_V3_SCHEMA_VERSION,
            "jurisdiction_time": problem.jurisdiction_time.model_copy(
                update={
                    "region": "US",
                    "valid_time": "2022",
                    "as_of": "2022-12-31",
                    "policy_time": "2022",
                    "data_time": "2022",
                }
            ),
            "objectives": (
                DesignObjective(
                    objective_id="employment_retention",
                    description="Retain employment in the synthetic scenario.",
                    metric_id="employment_retention",
                ),
            ),
            "stakeholders": (
                DesignStakeholder(
                    stakeholder_id="us_residents",
                    name="U.S. national economy",
                    role="target_population",
                ),
            ),
            "outcome_of_interest": OutcomeOfInterest(
                target_variable="employment_retention",
                metric_id="employment_retention",
                estimand="average_treatment_effect",
            ),
            "candidate_lever_space": CandidateLeverSpace(
                allowed_operator_kinds=["tax_relief_rate"],
                candidate_levers=[
                    CandidateLever(
                        lever_id="tax_relief_rate",
                        operator_kind="tax_relief_rate",
                        instrument="Temporary tax relief",
                        target_slot="global.tax_rate",
                    )
                ],
            ),
        }
    )
    problem = DesignProblem.model_validate(problem.model_dump(mode="python"))

    resolver = RequirementToCapabilityResolver.governed_fixture(REPO_ROOT)
    compiler_controller = GenerationCycleController(
        capability_resolver=resolver,
        repo_root=REPO_ROOT,
    )
    compiled_basis = compiler_controller._n7_data_requirement_basis_with_report(
        problem,
        acquisition_request={"driver": f"acquire_data:{source_family}"},
    )
    if (
        compiled_basis.unbound_input_fields
        or compiled_basis.compilation_report.schema_version
        != DATA_REQUIREMENT_COMPILATION_SCHEMA_VERSION
        or compiled_basis.compilation_report.requirement_basis.source
        != "governed_capability_resolution"
        or compiled_basis.compilation_report.requirement_basis.basis_grade != "recomputed"
        or len(compiled_basis.specs) != 1
        or len(compiled_basis.capability_resolutions) != 1
    ):
        raise AssertionError("acq01_macro_context_compiler_basis_not_governed")
    data_spec = compiled_basis.specs[0]
    resolution = compiled_basis.capability_resolutions[0]
    if (
        type(data_spec) is not DataRequirementSpec
        or data_spec.required_data_families != (source_family,)
        or data_spec.metadata.get("construct_ref") != "construct:economic.gdp"
        or data_spec.metadata.get("capability_binding", {}).get("construct_ref")
        != "construct:economic.gdp"
        or resolution.query.construct != "economic.gdp"
        or resolution.candidate_discovery is None
        or resolution.candidate_discovery.satisfies_claim_evidence
    ):
        raise AssertionError("acq01_macro_context_compiler_denominator_mismatch")

    before_context = _real_acq01_before_context(
        tmp_path / "nominal-gdp-before",
        problem,
        additional_policy_slot_ids=("global.tax_rate",),
        world_model_scope={
            "region_or_jurisdiction": "US",
            "population_scope": "national_economy",
            "policy_domain": "fiscal_credit",
            "valid_time_scope": "2022",
        },
    )
    candidate = _fixture_candidate(
        problem,
        world_ref=before_context.world_model_record.world_model_record_id,
        target_world_slots=("global.tax_rate",),
        candidate_id="candidate_us_tax_relief",
    )
    atom = candidate.atom
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
    intended_downstream_estimand = atom.intended_downstream_estimand.model_copy(
        update={"target_population": "US"}
    )
    atom = atom.model_copy(
        update={
            "causal_do_expr": causal_do_expr,
            "direct_effect_bundle": direct_effect_bundle,
            "intended_downstream_estimand": intended_downstream_estimand,
        }
    )
    atom_content_hash = intervention_atom_content_hash(atom)
    atom = atom.model_copy(
        update={
            "atom_id": f"atom_{atom_content_hash.removeprefix('sha256:')[:16]}",
            "content_hash": atom_content_hash,
        }
    )
    candidate.atom = atom
    candidate.intervention_atoms = (atom,)
    return SimpleNamespace(
        problem=problem,
        data_spec=data_spec,
        compiler_report=compiled_basis.compilation_report,
        capability_resolver=resolver,
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
    grounding_port: Any | None = None,
    capability_resolver: Any | None = None,
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
    if len(case.data_spec.required_data_families) != 1:
        raise ValueError("acq01_fixture_data_family_must_be_unique")
    family = case.data_spec.required_data_families[0]
    controller = GenerationCycleController(
        generation_port=_RouteGenerationPort(),
        grounding_port=grounding_port
        or _FixtureAcquisitionGrounding(issue_code=f"acquire_data:{family}"),
        simulation_port=simulation,
        value_port=selected_value_port,
        acquisition_owner_gateway=gateway,
        capability_resolver=capability_resolver,
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


def _assert_acq01_compiler_planner_preflight(
    *,
    case: Any,
    route: Any,
    repo_root: Path,
) -> tuple[Any, Any, _Acq01MacroContextGrounding]:
    """Prove the real compiler-to-planner route without invoking physical N5."""

    import asyncio

    from polisyos.core.artifacts import load_core_json_artifact
    from polisyos.runtime.quality.acquisition_planner import (
        data_requirement_compilation_report_digest,
    )

    grounding = _Acq01MacroContextGrounding(case=case, route=route)
    simulation = _WorldBoundSimulation()
    controller = _build_acq01_real_route_controller(
        case=case,
        route=route,
        simulation=simulation,
        repo_root=repo_root,
        grounding_port=grounding,
        capability_resolver=case.capability_resolver,
    )
    cycle, _summaries = asyncio.run(
        controller._run_cycle(
            case.problem,
            cycle_index=0,
            budget_state=BudgetState(
                limits={"run": BudgetLimit(key="run", max_usd=Decimal("5.0"))}
            ),
            previous_cycle=None,
            stable_design_problem_ref=gy_content_hash(case.problem.model_dump(mode="json")),
        )
    )
    assert cycle.terminal_kind == "acquisition_required"
    assert len(simulation.world_refs) == 1
    assert simulation.world_refs == [str(case.candidate.atom.world_model_record_ref)]
    assert cycle.grounding.acquisition_requirement is not None
    gap = cycle.grounding.acquisition_requirement
    assert cycle.grounding.report_ref is not None
    assert gap.metadata["source"] == "cgf_grounding_coverage"
    assert gap.metadata["authority_purpose"] == "routing_only"
    assert gap.metadata["satisfaction_status"] == "unsatisfied"
    assert gap.metadata["candidate_binding"]["candidate_id"] == case.candidate.candidate_id
    assert gap.metadata["candidate_binding"]["candidate_content_hash"] == (
        generation_cycle_module._candidate_content_hash(case.candidate)
    )
    assert gap.metadata["candidate_binding"]["design_problem_ref"] == gy_content_hash(
        case.problem.model_dump(mode="json")
    )
    assert gap.metadata["issue_codes"] == [grounding.issue_code]
    assert set(gap.metadata["evidence_refs"]) == set(cycle.grounding.evidence_refs)
    cov_report = load_core_json_artifact(route.store, grounding.report_ref)
    assert cov_report["authority_scope"] == "contract_testing"
    assert cov_report["claim_evidence_use_allowed"] is False
    assert cov_report["candidate_binding"]["candidate_content_hash"] == (
        generation_cycle_module._candidate_content_hash(case.candidate)
    )
    assert cov_report["design_problem_ref"] == gy_content_hash(case.problem.model_dump(mode="json"))
    assert cov_report["required_macro_context"]["construct_ref"] == "construct:economic.gdp"
    assert cov_report["required_macro_context"]["compiled_requirement_ref"] == (
        case.data_spec.requirement_id
    )
    compiler_ref = cov_report["required_macro_context"]["compiler_report_ref"]
    assert compiler_ref["artifact_id"] == str(
        grounding.compiler_report_binding.compiler_report_ref.artifact_id
    )
    assert grounding.compiler_report_binding.compiler_report_digest == (
        data_requirement_compilation_report_digest(case.compiler_report)
    )
    assert cov_report["causal_scope"] == {
        "macro_context_is_employment_outcome": False,
        "gdp_to_employment_causal_effect_claimed": False,
    }
    assert cov_report["source_authority_status"] == "not_established"
    assert cov_report["source_currentness_status"] == "not_established"

    planned = controller._plan_n7_requirement_gap_if_requested(case.problem, cycle=cycle)
    assert planned is not None
    assert planned.basis.unbound_input_fields == ()
    assert planned.basis.routing_limitation_code is None
    assert planned.basis.routed_source_gap == gap
    assert planned.basis.compilation_report.schema_version == (case.compiler_report.schema_version)
    assert planned.basis.compilation_report.input_content_hash == (
        case.compiler_report.input_content_hash
    )
    assert planned.basis.compilation_report.requirement_basis.source == (
        "governed_capability_resolution"
    )
    assert planned.basis.compilation_report.requirement_basis.basis_grade == "recomputed"
    assert planned.basis.specs == (case.data_spec,)
    assert len(planned.basis.capability_resolutions) == 1
    resolution = planned.basis.capability_resolutions[0]
    assert resolution.query.construct == "economic.gdp"
    assert resolution.candidate_discovery is not None
    assert resolution.candidate_discovery.satisfies_claim_evidence is False
    route_records = tuple(
        record
        for record in planned.report.acquisition_records
        if gap.requirement_gap_id in record.scenario_requirement_refs
    )
    assert len(route_records) == 1
    assert route_records[0].compiled_requirement_ref == case.data_spec.requirement_id
    assert planned.report.requirement_basis_binding.compiler_report_ref == (
        grounding.compiler_report_binding.compiler_report_ref
    )

    # A caller-provided spec is never added to, or substituted for, the actual
    # compiler denominator. The planner persists a refusal with no owner route.
    raw_request = dict(cycle.revision_request.strategy_payload["acquisition_request"])
    raw_request["data_requirement_specs"] = [case.data_spec.model_dump(mode="json")]
    strategy_payload = dict(cycle.revision_request.strategy_payload)
    strategy_payload["acquisition_request"] = raw_request
    raw_revision = cycle.revision_request.model_copy(update={"strategy_payload": strategy_payload})
    raw_cycle = cycle.model_copy(update={"revision_request": raw_revision})
    refused = controller._plan_n7_requirement_gap_if_requested(case.problem, cycle=raw_cycle)
    assert refused is not None
    assert refused.basis.unbound_input_fields == ("acquisition_request.data_requirement_specs",)
    assert refused.basis.specs == (case.data_spec,)
    assert refused.report.status == "blocked"
    assert refused.report.basis_limitation_code == "unbound_requirement_input_refused"
    assert refused.report.acquisition_records == ()
    assert refused.cost_basis is None

    # Without the explicit supported construct, the same family driver is only
    # a consumer-asserted selector; it cannot create a governed source mapping.
    raw_hints = dict(case.problem.runtime_hints)
    raw_hints.pop("n7_scope_profile")
    no_construct_problem = case.problem.model_copy(update={"runtime_hints": raw_hints})
    issue_only = GenerationCycleController(
        capability_resolver=case.capability_resolver,
        repo_root=repo_root,
    )._n7_data_requirement_basis_with_report(
        no_construct_problem,
        acquisition_request={"driver": grounding.issue_code},
    )
    assert issue_only.compilation_report.schema_version == case.compiler_report.schema_version
    assert issue_only.compilation_report.requirement_basis.source == (
        "explicit_scenario_family_declaration"
    )
    assert issue_only.compilation_report.requirement_basis.basis_grade == "consumer_asserted"
    assert issue_only.capability_resolutions == ()
    assert issue_only.specs
    assert all(
        spec.metadata.get("construct_ref") is None
        for spec in issue_only.specs
        if isinstance(spec, DataRequirementSpec)
    )
    return cycle, planned, grounding


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


def test_acq01_macro_context_compiler_to_planner_preflight(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The actual N7 planner binds the compiler denominator before any physical N5."""

    case = _real_acq01_macro_context_case(tmp_path)
    store = FileSystemCAS(tmp_path / "preflight-owner-cas")
    with (
        _published_worldbank_owner(
            tmp_path / "preflight-worldbank-owner",
            monkeypatch,
            artifact_store=store,
            geography="US",
            metric="gdp",
            time_start="2022",
            time_end="2022",
        ) as selected_owner,
        _real_acq01_route(
            tmp_path,
            case.problem,
            candidate_content_hash=case.candidate.atom.content_hash,
            candidate_id=case.candidate.candidate_id,
            target_world_slots=("global.tax_rate",),
            requirement_ref=case.data_spec.requirement_id,
            artifact_store=store,
            selected_metric="gdp",
            selected_owner=selected_owner,
            data_spec_override=case.data_spec,
            compiled_requirement_family="wdi_nominal_gdp_annual",
            world_model_scope={
                "region_or_jurisdiction": "US",
                "population_scope": "national_economy",
                "policy_domain": "fiscal_credit",
                "valid_time_scope": "2022",
            },
        ) as route,
    ):
        _assert_acq01_compiler_planner_preflight(
            case=case,
            route=route,
            repo_root=REPO_ROOT,
        )


def test_n7_acq01_reentry_rebinds_real_n5_and_default_n8(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A current scoped source reaches N5 and default N8 with candidate-only value."""
    import asyncio

    from polisyos.runtime.quality.data_forge_binding import (
        build_fabric_measurement_requirement,
    )

    case = _real_acq01_macro_context_case(tmp_path)
    source_family = "gdp"
    # The WDI observation is persisted as a separate context input. N5 uses a
    # normalized toy outcome mapping and does not claim a GDP-to-jobs effect.
    runtime_store = FileSystemCAS(tmp_path / "published-owner-cas")
    with _published_worldbank_owner(
        tmp_path / "published-worldbank-owner",
        monkeypatch,
        artifact_store=runtime_store,
        geography="US",
        metric="gdp",
        time_start="2022",
        time_end="2022",
    ) as selected_owner:
        with _real_acq01_route(
            tmp_path,
            case.problem,
            candidate_content_hash=case.candidate.atom.content_hash,
            candidate_id=case.candidate.candidate_id,
            target_world_slots=("global.tax_rate",),
            requirement_ref=case.data_spec.requirement_id,
            artifact_store=runtime_store,
            selected_metric=source_family,
            selected_owner=selected_owner,
            data_spec_override=case.data_spec,
            compiled_requirement_family="wdi_nominal_gdp_annual",
            world_model_scope={
                "region_or_jurisdiction": "US",
                "population_scope": "national_economy",
                "policy_domain": "fiscal_credit",
                "valid_time_scope": "2022",
            },
        ) as route:
            # Preflight the whole producer -> typed demand/source contract -> WMR
            # binding before invoking N5, so a bad early field cannot hide later
            # scope or owner-family mismatches behind a sequence of reruns.
            expected_catalog_binding = route.catalog.bind_fetch_target(
                metric_id=source_family,
                connector_id="worldbank.wdi",
                request_dataset_id="NY.GDP.MKTP.CD",
                profile_id="worldbank_wdi",
                filters={"country": ["US"]},
            )
            expected_source_requirement = build_fabric_measurement_requirement(
                catalog=route.catalog,
                catalog_binding=expected_catalog_binding,
                design_problem=case.problem,
            )
            expected_data_spec = case.data_spec.model_copy(
                update={
                    "source_requirement_refs": (expected_source_requirement.requirement_id,),
                }
            )
            world_record = route.world_build.record
            route_tax_binding = world_record.slot_binding("global.tax_rate")
            before_tax_binding = case.before_context.world_model_record.slot_binding(
                "global.tax_rate"
            )
            data_need_contract = (
                None
                if route.data_need is None
                else (
                    route.data_need.metric,
                    route.data_need.geography,
                    route.data_need.time_start,
                    route.data_need.time_end,
                    route.data_need.granularity,
                )
            )
            simulation_model_ref = world_record.simulation_model_ref
            source_requirement_scope = route.source_requirement.scope
            actual_route_contract = {
                "selected retrieval plan": (
                    route.plan.metric_id,
                    route.plan.connector_id,
                    route.plan.dataset_id,
                    route.plan.profile_id,
                    route.plan.filters,
                ),
                "typed data need": data_need_contract,
                "compiled request family and scope": (
                    route.data_spec.required_data_families,
                    route.data_spec.requirement_id,
                    route.data_spec.scope.population,
                    route.data_spec.scope.geography,
                    route.data_spec.scope.jurisdiction,
                    route.data_spec.scope.time,
                    route.data_spec.scope.time_role,
                ),
                "compiled requirement source binding": (
                    route.data_spec == expected_data_spec,
                    route.data_spec.source_requirement_refs,
                ),
                "selected source family and scope": (
                    route.source_requirement.required_data_families,
                    (
                        source_requirement_scope.population,
                        source_requirement_scope.geography,
                        source_requirement_scope.jurisdiction,
                        source_requirement_scope.time,
                        source_requirement_scope.time_role,
                    ),
                    route.source_requirement == expected_source_requirement,
                ),
                "measurement root custody": (
                    route.evidence.envelope.model_dump(mode="json")
                    == route.measurement_root.model_dump(mode="json"),
                    route.evidence.payload.source_requirement == expected_source_requirement,
                    route.evidence.payload.authority_scope,
                    route.evidence.payload.limitation,
                ),
                "declared outcome and candidate": (
                    case.problem.objectives[0].metric_id,
                    case.problem.outcome_of_interest.metric_id,
                    case.problem.outcome_of_interest.target_variable,
                    case.candidate.atom.intended_downstream_estimand.metric_id,
                    case.candidate.atom.intended_downstream_estimand.outcome_variables,
                    case.candidate.atom.intended_downstream_estimand.target_population,
                    case.candidate.atom.target_world_slots,
                    case.candidate.atom.causal_do_expr.write_variables,
                    case.candidate.atom.direct_effect_bundle.params.get("target_world_slot"),
                    case.candidate.atom.world_model_record_ref,
                ),
                "declared problem scope": (
                    case.problem.jurisdiction_time.region,
                    case.problem.jurisdiction_time.data_time,
                ),
                "acquired world model scope and snapshot role": (
                    world_record.region_or_jurisdiction,
                    world_record.population_scope,
                    world_record.policy_domain,
                    world_record.valid_time_scope,
                    (
                        simulation_model_ref is not None
                        and simulation_model_ref.data_snapshot_ref
                        == str(route.data_snapshot_ref.artifact_id)
                    ),
                ),
                "acquired and before-context policy slots": (
                    None
                    if route_tax_binding is None
                    else (route_tax_binding.state_path, route_tax_binding.unit),
                    world_record.slot_binding("global.gdp") is None,
                    world_record.slot_binding("employment_retention") is None,
                    None
                    if before_tax_binding is None
                    else (before_tax_binding.state_path, before_tax_binding.unit),
                ),
            }
            expected_route_contract = {
                "selected retrieval plan": (
                    source_family,
                    "worldbank.wdi",
                    "NY.GDP.MKTP.CD",
                    "worldbank_wdi",
                    {"country": ["US"]},
                ),
                "typed data need": (source_family, "US", "2022", "2022", "annual"),
                "compiled request family and scope": (
                    ("wdi_nominal_gdp_annual",),
                    case.data_spec.requirement_id,
                    "national_economy",
                    "geography",
                    "US",
                    "time",
                    "observation_time",
                ),
                "compiled requirement source binding": (
                    True,
                    (expected_source_requirement.requirement_id,),
                ),
                "selected source family and scope": (
                    ("worldbank",),
                    ("U.S. national economy", "US", "US", "2022", "observation_time"),
                    True,
                ),
                "measurement root custody": (
                    True,
                    True,
                    "returned_observations_custody_only",
                    "retrieval_custody_does_not_establish_source_truth",
                ),
                "declared outcome and candidate": (
                    "employment_retention",
                    "employment_retention",
                    "employment_retention",
                    "employment_retention",
                    ("employment_retention",),
                    "US",
                    ("global.tax_rate",),
                    ("global.tax_rate",),
                    "global.tax_rate",
                    case.before_context.world_model_record.world_model_record_id,
                ),
                "declared problem scope": ("US", "2022"),
                "acquired world model scope and snapshot role": (
                    "US",
                    "national_economy",
                    "fiscal_credit",
                    "2022",
                    True,
                ),
                "acquired and before-context policy slots": (
                    ("tax_rate", "ratio"),
                    True,
                    True,
                    ("tax_rate", "ratio"),
                ),
            }
            route_contract_mismatches = {
                field: {"expected": expected, "actual": actual_route_contract[field]}
                for field, expected in expected_route_contract.items()
                if actual_route_contract[field] != expected
            }
            assert not route_contract_mismatches, (
                f"ACQ-01 route contract preflight failed before N5: {route_contract_mismatches!r}"
            )

            n5 = _RecordingN5Controller()
            runtime_store = route.store
            grounding = _Acq01MacroContextGrounding(case=case, route=route)
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
                grounding_port=grounding,
                capability_resolver=case.capability_resolver,
            )

            run = asyncio.run(
                controller.run(
                    case.problem,
                    budget_state=BudgetState(
                        limits={"run": BudgetLimit(key="run", max_usd=Decimal("5.0"))}
                    ),
                    max_cycles=1,
                )
            )

        assert run.synthetic is True
        assert len(run.cycles) == 1
        if len(n5.requests) != 2:
            failed_cycle = run.cycles[0]
            receipt = failed_cycle.acquisition_receipt
            receipt_summary = None
            if receipt is not None:
                rederivations = tuple(receipt.get("grounding_rederivations", ()))
                receipt_summary = {
                    "receipt_id": receipt.get("receipt_id"),
                    "status": receipt.get("status"),
                    "fail_closed_reasons": tuple(receipt.get("fail_closed_reasons", ()))[:6],
                    "owner_artifact_count": len(receipt.get("owner_artifacts", ())),
                    "real_grounding_result_count": receipt.get("real_grounding_result_count"),
                    "grounding_rederivation_count": len(rederivations),
                    "grounding_rederivations": tuple(
                        {
                            "design_id": row.get("design_id"),
                            "status": row.get("status"),
                            "issue_codes": tuple(row.get("issue_codes", ()))[:4],
                        }
                        for row in rederivations[:6]
                        if isinstance(row, dict)
                    ),
                    "grown_world_before_ref": receipt.get("grown_world_before_ref"),
                    "grown_world_after_ref": receipt.get("grown_world_after_ref"),
                }
            routing = failed_cycle.acquisition_routing_report
            route_summary = None
            if routing is not None:
                route_summary = {
                    "status": routing.status,
                    "basis_limitation_code": routing.basis_limitation_code,
                    "records": tuple(
                        {
                            "requirement_gap_ref": row.requirement_gap_ref,
                            "compiled_requirement_ref": row.compiled_requirement_ref,
                            "recommended_strategy": row.recommended_strategy,
                            "terminal_disposition": str(row.terminal_disposition),
                            "status": row.status,
                            "producer_output_present": row.producer_output_ref is not None,
                        }
                        for row in routing.acquisition_records[:6]
                    ),
                }
            failure_context = {
                "n5_request_count": len(n5.requests),
                "run_terminal_status": run.terminal_status,
                "run_blocked_reason": run.blocked_reason,
                "cycle_terminal_kind": failed_cycle.terminal_kind,
                "simulation_status": failed_cycle.simulation.status,
                "grounding_status": failed_cycle.grounding.status,
                "grounding_issue_codes": failed_cycle.grounding.issue_codes,
                "routing_report_ref": (
                    None
                    if failed_cycle.acquisition_routing_report_ref is None
                    else str(failed_cycle.acquisition_routing_report_ref.artifact_id)
                ),
                "routing_report": route_summary,
                "acquisition_receipt": receipt_summary,
            }
            pytest.fail(
                "expected initial and post-acquisition N5 requests; "
                f"bounded cycle state: {failure_context!r}"
            )
        before_request, after_request = n5.requests
        assert all(request.seed == 0 and request.replications == 1 for request in n5.requests)
        assert all(request.budget_ref == "budget://acq-01/real-ports" for request in n5.requests)
        assert before_request.world_model_record == case.before_context.world_model_record
        _assert_n7_world_model_record_semantics(
            after_request.world_model_record,
            route.world_build.record,
        )
        assert (
            after_request.world_model_record_ref == route.world_build.record.world_model_record_id
        )
        assert after_request.world_model_record.simulation_model_ref.data_snapshot_ref == str(
            route.data_snapshot_ref.artifact_id
        )
        assert after_request.world_model_record.slot_binding("employment_retention") is None
        assert after_request.selected_outcomes == ("employment_retention",)
        assert after_request.engine_plan[0].variable_map["global.tax_rate"] == (
            "exogenous_inflows.0"
        )
        assert after_request.engine_plan[0].variable_map["employment_retention"] == "stock:0"
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
        assert cycle.grounding.acquisition_requirement is not None
        assert cycle.grounding.acquisition_requirement.metadata["source"] == (
            "cgf_grounding_coverage"
        )
        assert cycle.grounding.report_ref is not None
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
        assert persisted_n5.schema_version == (
            n5_horizon.JOINT_SIMULATION_HORIZON_NUMERIC_TOLERANCE_SCHEMA_VERSION
        )
        assert persisted_n5.diagnostics["requested_replications"] == 1
        assert persisted_n5.diagnostics["replication_seeds"] == [0]

        engine_input = case.problem.runtime_hints["joint_simulation_engine_plan"]
        engine_state = engine_input["system_dynamics_state"]
        engine_params = engine_input["system_dynamics_params"]
        initial_stocks = tuple(float(value) for value in engine_state["initial_stocks"])
        flow_matrix = tuple(
            tuple(float(value) for value in row) for row in engine_state["flow_matrix"]
        )
        exogenous_inflows = tuple(float(value) for value in engine_state["exogenous_inflows"])
        intervention_inflow = float(
            after_request.intervention_atoms[0].causal_do_expr.assignments[0].value
        )
        dt = float(engine_params["dt"])
        expected_transition_stocks = (
            max(
                0.0,
                initial_stocks[0]
                + dt * flow_matrix[1][0] * initial_stocks[1]
                - dt * flow_matrix[0][1] * initial_stocks[0]
                + dt * intervention_inflow,
            ),
            max(
                0.0,
                initial_stocks[1]
                + dt * flow_matrix[0][1] * initial_stocks[0]
                - dt * flow_matrix[1][0] * initial_stocks[1]
                + dt * exogenous_inflows[1],
            ),
        )
        baseline_outcome = float(
            case.problem.runtime_hints["joint_simulation_baseline_state"]["employment_retention"]
        )
        assert initial_stocks == (1.0, 0.0)
        assert flow_matrix == ((0.0, 0.1), (0.0, 0.0))
        assert exogenous_inflows == (0.0, 0.0)
        assert intervention_inflow == 1.0
        assert dt == 1.0
        assert baseline_outcome == 1.0
        # This oracle covers only the declared synthetic stock-flow model; the
        # acquired GDP observation is not treated as a causal effect input.
        assert expected_transition_stocks == pytest.approx((1.9, 0.1), rel=1e-12, abs=1e-12)
        expected_stock_rows = (
            (0, initial_stocks),
            (1, expected_transition_stocks),
        )
        assert {item.run_level for item in persisted_n5.trajectories} == {
            "individual",
            "joint",
        }
        for trajectory in persisted_n5.trajectories:
            assert trajectory.method_fqn == "simulation.system_dynamics.stock_flow@1.0.0"
            assert trajectory.atom_ids == tuple(
                item.intervention_id for item in after_request.intervention_atoms
            )
            assert len(trajectory.points) == len(expected_stock_rows)
            for point, (expected_step, expected_stocks) in zip(
                trajectory.points,
                expected_stock_rows,
                strict=True,
            ):
                assert point.step == expected_step
                stock_values = point.engine_state["stock_values"]
                assert len(stock_values) == len(expected_stocks)
                for actual_stock, expected_stock in zip(
                    stock_values,
                    expected_stocks,
                    strict=True,
                ):
                    assert actual_stock == pytest.approx(expected_stock, rel=1e-12, abs=1e-12)
                expected_outcome = expected_stocks[0]
                expected_effect = expected_outcome - baseline_outcome
                assert point.outcomes["employment_retention"] == pytest.approx(
                    expected_outcome,
                    rel=1e-12,
                    abs=1e-12,
                )
                assert point.effect["employment_retention"] == pytest.approx(
                    expected_effect,
                    rel=1e-12,
                    abs=1e-12,
                )
                sampling = point.replication_sampling
                assert sampling is not None
                assert sampling.replicate_count == 1
                assert sampling.seeds == (0,)
                assert sampling.samples[0].outcomes["employment_retention"] == pytest.approx(
                    expected_outcome,
                    rel=1e-12,
                    abs=1e-12,
                )
                assert sampling.samples[0].effects["employment_retention"] == pytest.approx(
                    expected_effect,
                    rel=1e-12,
                    abs=1e-12,
                )
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
        assert all(
            record.replicate_count == 1
            and record.seeds == (0,)
            and len(record.samples) == 1
            and set(record.outcomes_standard_error.values()) == {None}
            and set(record.effects_standard_error.values()) == {None}
            for record in point_sampling_records
            if record is not None
        )
        assert "standard_error_not_estimated" in persisted_blockers
        assert {
            "simulation_only_k_sim_not_world_evidence",
            "simulation_effect_basis_not_established",
        }.issubset(persisted_blockers)

        feedback = persisted_n5.feedback_classification
        assert feedback.interaction_sampling_status == "estimated"
        assert feedback.numeric_interaction == "none"
        assert feedback.numeric_interaction_basis == "finite_checked_model_point_estimate_only"
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
        assert {
            "simulation_only_k_sim_not_world_evidence",
            "simulation_effect_basis_not_established",
            "standard_error_not_estimated",
        }.issubset(actual_value_blockers)
        assert "interaction_sampling_not_established" not in actual_value_blockers
        assert "interaction_numeric_classification_unsupported" not in actual_value_blockers
        assert cycle.value_port.numeric_interaction == "none"
        assert (
            cycle.value_port.numeric_interaction_basis == "finite_checked_model_point_estimate_only"
        )
        assert cycle.value_port.interaction_sampling_status == "estimated"
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

    from polisyos.runtime.quality.acquisition_planner import (
        grounding_coverage_requirement_gap,
    )

    problem = _problem(
        problem_id="acq_01_registry_only_reentry",
        runtime_hints={
            "joint_simulation_resource": "method_registry_estimator",
            "joint_simulation_budget_ref": "budget://acq-01/registry-only-reentry",
            "joint_simulation_horizon": {"start": 0, "end": 1, "step": 1},
        },
    )
    data_spec = _compiled_data_requirement_spec(problem, family="fixture_panel")
    assert data_spec.required_data_families == ("fixture_panel",)
    registry = _fixture_world_registry(include_candidate_l2=True)
    selected_l2_hashes = tuple(
        entry.entry_content_hash for entry in registry.entries if entry.layer is SubstrateLayer.L2
    )
    assert len(selected_l2_hashes) == 1
    world = generation_cycle_module._build_boundary_world_model_record(
        repo_root=REPO_ROOT,
        problem=problem,
        outcome="firm_survival",
        policy_slot_ids=("fixture_panel",),
        substrate_registry=registry,
        selected_registry_entry_hashes=selected_l2_hashes,
    )
    problem_ref = gy_content_hash(problem.model_dump(mode="json"))
    context = build_cycle_substrate_context(
        design_problem_ref=problem_ref,
        domain=problem.domain,
        substrate_registry=registry,
        selected_registry_entry_hashes=selected_l2_hashes,
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

    class _CandidateBoundFixtureGrounding:
        def __call__(
            self,
            *,
            candidate: Any,
            problem: DesignProblem,
            cycle_index: int,
            generation_result: Any | None = None,
        ) -> CandidateGroundingObservation:
            del generation_result
            observation = _FixtureAcquisitionGrounding(issue_code="acquire_data:fixture_panel")(
                candidate=candidate,
                problem=problem,
                cycle_index=cycle_index,
            )
            report_ref = f"test://acq-01/{problem.design_problem_id}/grounding-report"
            requirement = grounding_coverage_requirement_gap(
                candidate_id=str(candidate.candidate_id),
                candidate_content_hash=generation_cycle_module._candidate_content_hash(candidate),
                design_problem_ref=gy_content_hash(problem.model_dump(mode="json")),
                issue_codes=observation.issue_codes,
                evidence_refs=observation.evidence_refs,
                authority_level=problem.authority_profile.requested_authority_level,
                grounding_report_ref=report_ref,
            )
            return observation.model_copy(
                update={"report_ref": report_ref, "acquisition_requirement": requirement}
            )

    n5 = _RecordingN5Controller()
    simulation_port = JointSimulationPort(
        controller=n5,
        repo_root=tmp_path,
        cycle_substrate_context=context,
        artifact_store=FileSystemCAS(tmp_path / "n5-result-store"),
    )
    controller = GenerationCycleController(
        generation_port=_BoundFixtureGenerationPort(),
        grounding_port=_CandidateBoundFixtureGrounding(),
        simulation_port=simulation_port,
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
    _assert_n7_has_no_grounding_result(
        receipt,
        cycle=cycle,
        expected_grounding_status="grounding_gap",
        expected_cycle_grounding_issue_codes=("acquire_data:fixture_panel",),
    )
    selected_gap = cycle.grounding.acquisition_requirement
    assert selected_gap is not None
    receipt_specs = tuple(
        DataRequirementSpec.model_validate(spec) for spec in receipt["compiled_requirement_specs"]
    )
    assert receipt_specs == (data_spec,)
    routed_records = receipt["planner_report"]["acquisition_records"]
    assert len(routed_records) == 1
    routed_record = routed_records[0]
    assert routed_record["requirement_family"] == "data_requirement"
    assert routed_record["compiled_requirement_ref"] == data_spec.requirement_id
    assert selected_gap.requirement_gap_id in routed_record["scenario_requirement_refs"]
    assert data_spec.requirement_id in routed_record["scenario_requirement_refs"]
    assert "fixture_panel" in routed_record["scenario_requirement_refs"]
    candidate_binding = selected_gap.metadata["candidate_binding"]
    assert candidate_binding["candidate_id"] == cycle.selected_candidate_ref
    assert candidate_binding["candidate_content_hash"] == cycle.selected_candidate_content_hash
    assert candidate_binding["design_problem_ref"] == cycle.design_problem_ref
    grown_world_ref = receipt["grown_world_after_ref"]
    assert grown_world_ref.startswith("s0://substrate-registry/")
    assert grown_world_ref != context.world_model_record_content_hash
    assert grown_world_ref != context.world_model_record.world_model_record_id
    # The initial N5 request uses the selected before-context WMR. Its current
    # engine-plan limitation is independent of the post-acquisition refusal.
    assert len(n5.requests) == 1
    assert n5.requests[0].world_model_record_ref == context.world_model_record.world_model_record_id
    assert n5.requests[0].world_model_record.content_hash == context.world_model_record.content_hash
    assert cycle.simulation.status == "simulation_blocked"
    assert "method_registry_fqn_missing" in cycle.simulation.authority_blockers
    # A blocked initial N5 call may still persist a result receipt. The
    # registry-only reentry below is the no-side-effect case: it must be
    # rejected before another N5 request or result is produced.

    registry_only_candidate = _fixture_candidate(
        problem,
        world_ref=grown_world_ref,
        candidate_id=str(cycle.selected_candidate_ref),
    )
    reentry_observation = simulation_port(
        candidate=registry_only_candidate,
        problem=problem,
        cycle_index=cycle.cycle_index,
    )
    assert reentry_observation.status == "simulation_blocked"
    assert reentry_observation.authority_blockers == ("world_identity_unresolved",)
    assert reentry_observation.diagnostics["reason"] == "world_identity_unresolved"
    assert reentry_observation.simulation_ref is None
    assert len(n5.requests) == 1


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
