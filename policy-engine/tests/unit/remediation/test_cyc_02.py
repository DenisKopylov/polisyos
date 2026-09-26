"""CYC-02 witnesses for durable N5 output and conditional N8 use."""

from __future__ import annotations

import json
import subprocess
import time
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import polisyos.runtime.quality.generation_cycle as generation_cycle_module
import polisyos.runtime.quality.recursive_generation_cycle as recursive_generation_cycle_module
from polisyos.core.artifacts import ArtifactRef as CASArtifactRef
from polisyos.core.artifacts import FileSystemCAS, PutOptions, SchemaInfo
from polisyos.core.artifacts.backends.config import (
    with_ambient_ownership_enforcement_if_supported,
)
from polisyos.core.canon.canon_json import CanonSpec
from polisyos.core.security.tenant_context import tenant_scope
from polisyos.pdc import (
    ArtifactRef as PDCArtifactRef,
)
from polisyos.pdc import (
    SearchTerminalKind,
    SearchTerminalState,
    gy_content_hash,
)
from polisyos.runtime.http.errors import (
    RuntimeDependencyTimeoutError,
    RuntimeDependencyUnavailableError,
)
from polisyos.runtime.http.resilience import guard_runtime_cas
from polisyos.runtime.quality.cycle_substrate import build_cycle_substrate_context
from polisyos.runtime.quality.design_axes.coupling_composition import (
    CouplingEdge,
    build_coupling_graph,
    derive_recursive_design_graph,
)
from polisyos.runtime.quality.generation_cycle import (
    CandidateGroundingObservation,
    GenerationCycleController,
    GenerationCycleError,
    JointSimulationPort,
    PendingN8ValuePort,
    PromotionPortObservation,
    SimulationPortObservation,
    _DefaultSimulationBoundFoundryValuePort,
    load_joint_simulation_result,
    simulation_evaluation_input_ref,
)
from polisyos.runtime.quality.intervention_atom_binding import (
    intervention_atom_content_hash,
)
from polisyos.runtime.quality.joint_simulation_horizon import (
    JointSimulationHorizonController,
)
from polisyos.runtime.quality.recursive_generation_cycle import (
    _AUTHENTIC_LEGACY_RECURSIVE_V1_CONTENT_HASHES,
    RecursiveCycleBudget,
    RecursiveCycleNode,
    RecursiveGenerationCycleController,
    RecursiveGenerationCycleError,
    RecursiveGenerationCycleRun,
    _is_authenticated_legacy_v1,
)
from polisyos.scientist.orchestration.engine.budget import BudgetLimit, BudgetState
from tests.unit.runtime.quality.test_generation_cycle import (
    _cyc01_owner_bound_n5_case,
    _problem,
)
from tests.unit.runtime.quality.test_joint_simulation_horizon import _request


def test_legacy_recursive_v1_without_n5_cas_ref_reopens_without_new_evidence() -> None:
    """Read the tracked pre-CAS v1 artifact without upgrading its evidence."""

    artifact_path = (
        Path(__file__).resolve().parents[3]
        / "architecture/policy_design_case/layer3_gy_composition_certificates.json"
    )
    payload = json.loads(artifact_path.read_text(encoding="utf-8"))["recursive_runs"][0]
    legacy_hash = payload["content_hash"]

    parsed = RecursiveGenerationCycleRun.model_validate(payload)
    assert parsed.schema_version == "policyos.runtime.recursive_generation_cycle.v1"
    assert parsed.content_hash == legacy_hash
    assert all(node.joint_simulation_ref is None for node in parsed.nodes)

    replayed_payload = parsed.model_dump(mode="json")
    assert replayed_payload["content_hash"] == legacy_hash
    assert all("joint_simulation_ref" not in node for node in replayed_payload["nodes"])

    legacy_parent_index, legacy_parent = next(
        (index, node)
        for index, node in enumerate(payload["nodes"])
        if node["joint_simulation"]
    )
    with pytest.raises(ValueError, match="recursive_simulation_result_requires_cas_ref"):
        RecursiveCycleNode.model_validate(legacy_parent)

    tampered = dict(payload)
    tampered["content_hash"] = "sha256:" + "0" * 64
    with pytest.raises(ValueError, match="recursive_simulation_result_requires_cas_ref"):
        RecursiveGenerationCycleRun.model_validate(tampered)

    recomputed = json.loads(json.dumps(payload))
    recomputed["run_id"] = "recursive:untrusted-recomputed-v1"
    recomputed["content_hash"] = gy_content_hash(
        {key: value for key, value in recomputed.items() if key != "content_hash"}
    )
    with pytest.raises(ValueError, match="recursive_simulation_result_requires_cas_ref"):
        RecursiveGenerationCycleRun.model_validate(recomputed)

    injected_root = json.loads(json.dumps(payload))
    injected_root["nodes"][legacy_parent_index]["legacy_v1_missing_joint_simulation_ref"] = True
    with pytest.raises(ValueError, match="extra_forbidden"):
        RecursiveGenerationCycleRun.model_validate(injected_root)

    injected_node = dict(legacy_parent)
    injected_node["legacy_v1_missing_joint_simulation_ref"] = True
    with pytest.raises(ValueError, match="extra_forbidden"):
        RecursiveCycleNode.model_validate(injected_node)


def test_legacy_recursive_v1_allowlist_covers_tracked_sources() -> None:
    """Keep the compatibility allowlist bounded to every tracked v1 identity."""

    repo_root = Path(__file__).resolve().parents[3]
    tracked_paths = subprocess.run(
        [
            "git",
            "grep",
            "-l",
            "--fixed-strings",
            "--",
            "policyos.runtime.recursive_generation_cycle.v1",
            "--",
            "*.json",
            "*.jsonl",
        ],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    discovered: list[dict[str, object]] = []

    def collect(value: object) -> None:
        if isinstance(value, dict):
            if value.get("schema_version") == "policyos.runtime.recursive_generation_cycle.v1":
                discovered.append(value)
            for child in value.values():
                collect(child)
        elif isinstance(value, list):
            for child in value:
                collect(child)

    for relative_path in tracked_paths:
        path = repo_root / relative_path
        source = path.read_text(encoding="utf-8")
        if path.suffix == ".jsonl":
            documents = [json.loads(line) for line in source.splitlines() if line.strip()]
        else:
            documents = [json.loads(source)]
        for document in documents:
            collect(document)

    discovered_hashes = {str(item["content_hash"]) for item in discovered}
    assert len(discovered) == 7
    assert discovered_hashes == _AUTHENTIC_LEGACY_RECURSIVE_V1_CONTENT_HASHES
    assert all(_is_authenticated_legacy_v1(item) for item in discovered)

    invalid = json.loads(json.dumps(discovered[0]))
    invalid["run_id"] = "recursive:untrusted-recomputed-v1"
    invalid["content_hash"] = gy_content_hash(
        {key: value for key, value in invalid.items() if key != "content_hash"}
    )
    assert not _is_authenticated_legacy_v1(invalid)


def _real_n5_observation(
    tmp_path: Path,
    *,
    artifact_store: Any | None = None,
    without_runtime_store: bool = False,
):
    """Run the canonical N5 producer through the real generation-cycle adapter."""

    store = (
        None
        if without_runtime_store
        else artifact_store or FileSystemCAS(tmp_path / "n5-runtime-store")
    )

    problem, context, candidate = _cyc01_owner_bound_n5_case()
    request = _request(
        record=context.world_model_record,
        world_model_record_ref=context.world_model_record.world_model_record_id,
    )
    problem = problem.model_copy(
        update={
            "runtime_hints": {
                **problem.runtime_hints,
                "joint_simulation_request": request,
            }
        }
    )
    # The request is an operational hint, but adding it changes the problem
    # envelope hash.  Rebuild only that envelope around the unchanged WMR and
    # registry so the context remains honestly bound to the final problem.
    context = build_cycle_substrate_context(
        design_problem_ref=gy_content_hash(problem.model_dump(mode="json")),
        domain=context.domain,
        substrate_registry=context.substrate_registry,
        selected_registry_entry_hashes=context.selected_registry_entry_hashes,
        world_model_record=context.world_model_record,
        intervention_substrate=context.intervention_substrate,
        candidate_levers=context.candidate_levers,
        transport_context=context.transport_context,
        source_pack_content_hash=context.source_pack_content_hash,
        substrate_input_content_hash=context.substrate_input_content_hash,
    )
    final_problem_ref = context.design_problem_ref
    rebound_atoms = []
    for atom in candidate.intervention_atoms:
        rebound = atom.model_copy(update={"problem_frame_ref": final_problem_ref})
        rebound_atoms.append(
            rebound.model_copy(
                update={"content_hash": intervention_atom_content_hash(rebound)}
            )
        )
    candidate.intervention_atoms = tuple(rebound_atoms)
    candidate.atom = rebound_atoms[0]
    producer = JointSimulationHorizonController()
    produced_results: list[object] = []

    class _RecordingN5Controller:
        def run(self, concrete_request):
            result = producer.run(concrete_request)
            produced_results.append(result)
            return result

    observation = JointSimulationPort(
        controller=_RecordingN5Controller(),
        repo_root=tmp_path,
        cycle_substrate_context=context,
        artifact_store=store,
    )(candidate=candidate, problem=problem, cycle_index=0)
    if without_runtime_store:
        assert observation.status == "simulation_blocked", observation.model_dump(mode="json")
        assert observation.authority_blockers == ("n5_runtime_store_not_established",)
        assert produced_results == []
    else:
        assert observation.status == "joint_simulated", {
            "status": observation.status,
            "authority_blockers": observation.authority_blockers,
            "diagnostics": observation.diagnostics,
        }
        assert "simulation_only_k_sim_not_world_evidence" in observation.authority_blockers
        assert len(produced_results) == 1
    produced_result = produced_results[0] if produced_results else None
    return problem, context, candidate, observation, produced_result, store


class _RecursiveGenerationPort:
    async def __call__(self, problem: object, *, cycle_index: int) -> SimpleNamespace:
        del problem, cycle_index
        atom = SimpleNamespace(
            intervention_id="recursive_leaf_intervention",
            content_hash="sha256:" + "4" * 64,
            status="candidate_unverified",
            world_model_record_ref="world_model_record_recursive_leaf",
            target_world_slots=("firm_survival",),
        )
        candidate = SimpleNamespace(
            candidate_id="candidate_recursive_leaf",
            atom=atom,
            diversity_key=("recursive", "cyc-02", "leaf", "baseline"),
            status="candidate_unverified",
        )
        ranking = SimpleNamespace(
            candidate_id=candidate.candidate_id,
            score=0.2,
            voi_estimate=0.1,
            trust_level="search_guiding",
            promotion_allowed=False,
        )
        return SimpleNamespace(
            status="generated",
            candidates=(candidate,),
            surrogate_rankings=(ranking,),
            grounding_dispositions=(),
        )


class _RecursiveGroundingPort:
    def __call__(self, *, candidate: Any, **kwargs: Any) -> CandidateGroundingObservation:
        del kwargs
        return CandidateGroundingObservation(
            candidate_id=str(candidate.candidate_id),
            status="grounded_shadow",
            grounding_score=0.2,
            grounding_source="cgf_firewall",
            grounding_disposition="shadow_bound",
            current_valid=False,
        )


class _RecursiveSimulationPort:
    def __call__(self, *, candidate: Any, **kwargs: Any) -> SimulationPortObservation:
        del candidate, kwargs
        return SimulationPortObservation(
            candidate_id="candidate_recursive_leaf",
            status="simulation_pending_n5",
            authority_blockers=("recursive_leaf_joint_request_not_owned",),
        )


class _RecursivePromotionPort:
    def __call__(self, **kwargs: Any) -> PromotionPortObservation:
        del kwargs
        return PromotionPortObservation()


def _recursive_contract_testing_controller(
    repo_root: Path,
    *,
    artifact_store: Any | None = None,
) -> RecursiveGenerationCycleController:

    def factory(_node_ref: str, _problem_input: object) -> GenerationCycleController:
        return GenerationCycleController(
            generation_port=_RecursiveGenerationPort(),
            grounding_port=_RecursiveGroundingPort(),
            simulation_port=_RecursiveSimulationPort(),
            value_port=PendingN8ValuePort(),
            promotion_port=_RecursivePromotionPort(),
            authority_scope="contract_testing",
            repo_root=repo_root,
            artifact_store=artifact_store,
        )

    return RecursiveGenerationCycleController.for_contract_testing(
        cycle_controller_factory=factory,
        repo_root=repo_root,
        artifact_store=artifact_store,
    )


def _recursive_leaf_terminal() -> SearchTerminalState:
    return SearchTerminalState(
        kind=SearchTerminalKind.GROUNDED_ABSTENTION,
        reason="Terminal emitted by the canonical generation-cycle owner.",
        blocking_obligations=["value_gate_pending_n8"],
    )


def _recursive_subdesigns(
    *,
    parent_ref: str,
    child_refs: tuple[str, str],
) -> tuple[object, ...]:
    from tools.quality.validation.check_layer3_gy_composition_artifacts import (
        _synthetic_composition_subdesigns,
    )

    originals = _synthetic_composition_subdesigns(
        artifact_ref_factory=PDCArtifactRef.from_payload,
    )
    return tuple(
        child.model_copy(
            update={
                "workspace_id": child_ref,
                "parent_workspace_id": parent_ref,
                "search_exit": child.search_exit.model_copy(
                    update={
                        "workspace_id": child_ref,
                        "terminal_state": _recursive_leaf_terminal(),
                    }
                ),
            }
        )
        for child, child_ref in zip(originals, child_refs, strict=True)
    )


def _recursive_parent_request(
    *,
    parent_ref: str,
    child_refs: tuple[str, str],
    problem: object,
    world_model_record: object,
) -> object:
    request = _request(
        record=world_model_record,
        world_model_record_ref=world_model_record.world_model_record_id,
    )
    problem_ref = gy_content_hash(problem.model_dump(mode="json"))
    rebound_atoms = []
    for atom in request.intervention_atoms:
        rebound = atom.model_copy(update={"problem_frame_ref": problem_ref})
        content_hash = intervention_atom_content_hash(rebound)
        rebound_atoms.append(
            rebound.model_copy(
                update={
                    "atom_id": f"atom_{content_hash.removeprefix('sha256:')[:16]}",
                    "content_hash": content_hash,
                }
            )
        )
    graph = build_coupling_graph(
        design_ref=parent_ref,
        module_refs=child_refs,
        module_discovery_ref="discovery://cyc-02/recursive-witness",
        interaction_edges=(
            CouplingEdge(
                boundary_ref="boundary://cyc-02/recursive-independent",
                source_module_ref=child_refs[0],
                target_module_ref=child_refs[1],
                relation="independent",
                interaction_strength="none",
                feedback_intensity="none",
                evidence_ref="evidence://cyc-02/recursive-independent",
            ),
        ),
        evidence_state="observed",
        rule_version_ref="repo://rules/cyc-02-recursive-cas",
    )
    return request.model_copy(
        update={"intervention_atoms": tuple(rebound_atoms), "coupling_graph": graph}
    )


def test_k_sim_limitation_remains_a_usable_simulation_input(tmp_path: Path) -> None:
    """K_sim limits authority, but does not make the real N5 input disappear."""

    _problem, _context, _candidate, simulation, _produced, _store = _real_n5_observation(
        tmp_path
    )

    input_ref = simulation_evaluation_input_ref(simulation)

    assert input_ref is not None
    assert simulation.simulation_result_ref is not None
    assert input_ref.content_hash == str(simulation.simulation_result_ref.artifact_id)


def test_n5_transient_store_failure_is_unavailable_not_integrity_invalid(
    tmp_path: Path,
) -> None:
    """A transient backend failure does not become a false corruption verdict."""

    _problem, _context, _candidate, simulation, _produced, store = _real_n5_observation(
        tmp_path
    )
    assert simulation.simulation_result_ref is not None

    class _TransientHasStore:
        def __init__(self, delegate: Any) -> None:
            self._delegate = delegate

        def get_manifest(self, artifact_ref: CASArtifactRef) -> Any:
            return self._delegate.get_manifest(artifact_ref)

        def has(self, _artifact_ref: CASArtifactRef) -> bool:
            raise ConnectionError("temporary artifact-store outage")

    with pytest.raises(
        GenerationCycleError,
        match="joint_simulation_result_unavailable",
    ):
        load_joint_simulation_result(
            simulation.simulation_result_ref,
            store=_TransientHasStore(store),  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    ("failure_mode", "expected_cause"),
    [
        ("unavailable", RuntimeDependencyUnavailableError),
        ("timeout", RuntimeDependencyTimeoutError),
    ],
)
def test_n5_guarded_runtime_store_errors_are_typed_unavailable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure_mode: str,
    expected_cause: type[Exception],
) -> None:
    """Production CAS guard errors become N5 unavailability, not corruption."""

    problem, context, candidate, simulation, _produced, store = _real_n5_observation(
        tmp_path
    )
    assert simulation.simulation_result_ref is not None

    class _GuardFailureTarget:
        def __init__(self, delegate: Any) -> None:
            self._delegate = delegate

        def get_manifest(self, artifact_ref: CASArtifactRef) -> Any:
            return self._delegate.get_manifest(artifact_ref)

        def has(self, _artifact_ref: CASArtifactRef) -> bool:
            if failure_mode == "unavailable":
                raise OSError("temporary CAS I/O failure")
            time.sleep(0.35)
            return True

    if failure_mode == "timeout":
        monkeypatch.setenv("POLISYOS_RUNTIME_CAS_TIMEOUT_SECONDS", "0.1")
    guarded_store = guard_runtime_cas(_GuardFailureTarget(store))
    original_loader = generation_cycle_module.load_joint_simulation_result
    observed_errors: list[GenerationCycleError] = []

    def observe_loader_error(*args: Any, **kwargs: Any) -> Any:
        try:
            return original_loader(*args, **kwargs)
        except GenerationCycleError as exc:
            observed_errors.append(exc)
            raise

    monkeypatch.setattr(
        generation_cycle_module,
        "load_joint_simulation_result",
        observe_loader_error,
    )
    try:
        observation = _DefaultSimulationBoundFoundryValuePort(
            repo_root=tmp_path,
            cycle_substrate_context=context,
            artifact_store=guarded_store,
        )(
            candidate=candidate,
            simulation=simulation,
            problem=problem,
            cycle_index=0,
        )
        assert observation.status == "value_blocked"
        assert observation.authority_blockers == (
            "joint_simulation_result_unavailable",
        )
        assert len(observed_errors) == 1
        assert isinstance(observed_errors[0].__cause__, expected_cause)
    finally:
        guarded_store.close()


def test_n5_replay_does_not_mask_store_programming_errors(tmp_path: Path) -> None:
    """Unexpected store faults surface instead of being mislabeled as corruption."""

    _problem, _context, _candidate, simulation, _produced, store = _real_n5_observation(
        tmp_path
    )
    assert simulation.simulation_result_ref is not None

    class _BrokenHasStore:
        def __init__(self, delegate: Any) -> None:
            self._delegate = delegate

        def get_manifest(self, artifact_ref: CASArtifactRef) -> Any:
            return self._delegate.get_manifest(artifact_ref)

        def has(self, _artifact_ref: CASArtifactRef) -> bool:
            raise AssertionError("store adapter bug")

    with pytest.raises(AssertionError, match="store adapter bug"):
        load_joint_simulation_result(
            simulation.simulation_result_ref,
            store=_BrokenHasStore(store),  # type: ignore[arg-type]
        )


def test_conditional_n8_status_is_not_authority_ready(tmp_path: Path) -> None:
    """The simulation-only value state is explicit and cannot carry N8 receipts."""

    problem, context, candidate, simulation, produced, store = _real_n5_observation(tmp_path)
    observation = _DefaultSimulationBoundFoundryValuePort(
        repo_root=tmp_path,
        cycle_substrate_context=context,
        artifact_store=store,
    )(
        candidate=candidate,
        simulation=simulation,
        problem=problem,
        cycle_index=0,
    )

    assert observation.status == "value_conditional", observation.model_dump(mode="json")
    assert observation.value_receipt is None
    assert observation.method_selection_receipt is None
    assert "simulation_only_k_sim_not_world_evidence" in observation.authority_blockers
    assert simulation.simulation_result_ref is not None
    assert isinstance(simulation.simulation_result_ref, CASArtifactRef)
    assert observation.value_ref == str(simulation.simulation_result_ref.artifact_id)

    reopened = load_joint_simulation_result(
        simulation.simulation_result_ref,
        store=store,
        expected_world_model_record_content_hash=context.world_model_record.content_hash,
    )
    outcome = problem.outcome_of_interest.target_variable
    trajectory = next(
        trajectory
        for trajectory in reopened.trajectories
        if trajectory.points and outcome in trajectory.points[0].effect
    )
    effect = trajectory.points[0].effect[outcome]
    assert isinstance(effect, float)
    produced_trajectory = next(
        candidate_trajectory
        for candidate_trajectory in produced.trajectories
        if candidate_trajectory.run_level == trajectory.run_level
        and candidate_trajectory.atom_ids == trajectory.atom_ids
        and candidate_trajectory.points
        and outcome in candidate_trajectory.points[0].effect
    )
    assert effect == produced_trajectory.points[0].effect[outcome]


class _GenericDefaultN5Store(FileSystemCAS):
    """Keep a generic JSON view as default while returning N5's selected view."""

    def __init__(self, root: Path) -> None:
        super().__init__(root)
        self.generic_view_ref: CASArtifactRef | None = None

    def put_json(
        self,
        obj: object,
        opts: PutOptions,
        canon_spec: CanonSpec | None = None,
    ) -> CASArtifactRef:
        if (
            opts.kind == "polisyos.runtime.joint_simulation_result"
            and self.generic_view_ref is None
        ):
            self.generic_view_ref = super().put_json(
                obj,
                PutOptions(
                    kind="application/json",
                    media_type="application/json",
                    schema=SchemaInfo(name="application/json", version="1"),
                ),
                canon_spec=canon_spec,
            )
        return super().put_json(obj, opts, canon_spec=canon_spec)


def test_n5_result_has_reopenable_cas_reference(tmp_path: Path) -> None:
    """The selected N5 view remains distinct from another honest view of its bytes."""

    store = _GenericDefaultN5Store(tmp_path / "n5-multiview-store")
    _problem, _context, _candidate, simulation, produced, supplied_store = (
        _real_n5_observation(tmp_path, artifact_store=store)
    )
    assert supplied_store is store
    result_ref = simulation.simulation_result_ref
    assert result_ref is not None
    assert result_ref.kind == "polisyos.runtime.joint_simulation_result"
    generic_ref = store.generic_view_ref
    assert generic_ref is not None
    assert generic_ref.artifact_id == result_ref.artifact_id
    assert generic_ref.manifest_profile_sha256 is None
    assert result_ref.manifest_profile_sha256 is not None

    generic_manifest = store.get_manifest(generic_ref)
    assert generic_manifest.kind == "application/json"
    manifest = store.get_manifest(result_ref)
    payload = json.loads(store.get_bytes(result_ref))
    assert manifest.artifact_schema is not None
    assert manifest.artifact_schema.name == "policyos.runtime.n5.joint_simulation_result"
    assert payload["receipt"]["payload_hash"] == produced.receipt.payload_hash
    assert payload["trajectories"]

    reopened = load_joint_simulation_result(
        result_ref,
        store=store,
        expected_world_model_record_content_hash=(
            produced.world_model_record_content_hash
        ),
        expected_atom_ids=produced.atom_ids,
    )
    assert reopened.trajectories == produced.trajectories
    assert reopened.world_model_record_content_hash == (
        produced.world_model_record_content_hash
    )

    wrong_profile_ref = result_ref.model_copy(
        update={"manifest_profile_sha256": "sha256:" + "f" * 64}
    )
    with pytest.raises(
        GenerationCycleError,
        match="joint_simulation_result_unavailable",
    ):
        load_joint_simulation_result(wrong_profile_ref, store=store)

    missing_ref = CASArtifactRef(
        artifact_id="sha256:" + "f" * 64,
        kind=result_ref.kind,
        media_type=result_ref.media_type,
    )
    with pytest.raises(GenerationCycleError, match="joint_simulation_result_unavailable"):
        load_joint_simulation_result(missing_ref, store=store)

    blob_path, selected_manifest_path = store.get_paths(result_ref)
    default_manifest_path = store.get_paths(generic_ref)[1]
    assert selected_manifest_path != default_manifest_path
    original_blob = blob_path.read_bytes()
    blob_path.write_bytes(original_blob + b"tampered")
    try:
        with pytest.raises(
            GenerationCycleError,
            match="joint_simulation_result_integrity_invalid",
        ):
            load_joint_simulation_result(result_ref, store=store)
    finally:
        blob_path.write_bytes(original_blob)

    original_manifest = selected_manifest_path.read_bytes()
    selected_manifest_path.write_bytes(b"{}")
    try:
        with pytest.raises(
            GenerationCycleError,
            match="joint_simulation_result_integrity_invalid",
        ):
            load_joint_simulation_result(result_ref, store=store)
        assert store.get_manifest(generic_ref).kind == "application/json"
    finally:
        selected_manifest_path.write_bytes(original_manifest)

    with pytest.raises(GenerationCycleError, match="joint_simulation_result_wmr_mismatch"):
        load_joint_simulation_result(
            result_ref,
            store=store,
            expected_world_model_record_content_hash="sha256:" + "e" * 64,
        )
    with pytest.raises(GenerationCycleError, match="joint_simulation_result_atom_binding"):
        load_joint_simulation_result(
            result_ref,
            store=store,
            expected_atom_ids=("foreign-model-atom",),
        )


@pytest.mark.asyncio
async def test_recursive_parent_keeps_n5_cas_reference(tmp_path: Path) -> None:
    """The real recursive parent route persists the N5 result before composition."""

    root = "design://cyc-02/recursive-root"
    child_refs = ("design://cyc-02/recursive-a", "design://cyc-02/recursive-b")
    parent_problem, context, _candidate = _cyc01_owner_bound_n5_case()
    problems = {
        root: parent_problem,
        child_refs[0]: _problem("cyc02_recursive_a"),
        child_refs[1]: _problem("cyc02_recursive_b"),
    }
    graph = derive_recursive_design_graph(
        design_ref=root,
        module_refs=child_refs,
        parent_child_edges=((root, child_refs[0]), (root, child_refs[1])),
        rule_version_ref="repo://rules/cyc-02-recursive-cas",
    )
    request = _recursive_parent_request(
        parent_ref=root,
        child_refs=child_refs,
        problem=parent_problem,
        world_model_record=context.world_model_record,
    )
    store = FileSystemCAS(tmp_path / "recursive-parent-store")
    controller = _recursive_contract_testing_controller(
        tmp_path,
        artifact_store=store,
    )
    subdesigns = _recursive_subdesigns(parent_ref=root, child_refs=child_refs)

    run = await controller.run(
        graph,
        problems_by_node=problems,
        budget_state=BudgetState(
            limits={"run": BudgetLimit(key="run", max_usd=Decimal("5.0"))}
        ),
        recursive_budget=RecursiveCycleBudget(
            max_depth=1,
            max_nodes=3,
            min_cycles_per_leaf=1,
            max_cycles_per_leaf=1,
        ),
        joint_simulation_requests_by_node={root: request},
        subdesign_contracts_by_node={root: subdesigns},
    )

    routed_by_ref = {node.node_ref: node for node in run.nodes}
    supplied_by_ref = {subdesign.workspace_id: subdesign for subdesign in subdesigns}
    for child_ref in child_refs:
        supplied = supplied_by_ref[child_ref].search_exit.terminal_state.model_dump(mode="json")
        routed = routed_by_ref[child_ref].terminal.model_dump(mode="json")
        differences = {
            field: {"supplied": supplied[field], "routed": routed[field]}
            for field in supplied
            if supplied[field] != routed[field]
        }
        assert not differences, (
            f"{child_ref} terminal mismatch: "
            f"{json.dumps(differences, sort_keys=True, separators=(',', ':'))}"
        )

    root_node = next(node for node in run.nodes if node.node_ref == root)
    assert root_node.joint_simulation is not None
    assert root_node.joint_simulation_ref is not None
    assert root_node.joint_simulation_ref.kind == "polisyos.runtime.joint_simulation_result"

    from polisyos.runtime.quality.generation_cycle import load_joint_simulation_result

    reopened = load_joint_simulation_result(
        root_node.joint_simulation_ref,
        store=store,
        expected_world_model_record_content_hash=(
            root_node.joint_simulation.world_model_record_content_hash
        ),
        expected_atom_ids=root_node.joint_simulation.atom_ids,
    )
    assert reopened.trajectories == root_node.joint_simulation.trajectories


@pytest.mark.asyncio
async def test_recursive_parent_without_store_refuses_before_n5_execution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No-store refusal precedes parent N5; leaf currentness is outside this seam."""

    root = "design://cyc-02/no-store-root"
    child_refs = ("design://cyc-02/no-store-a", "design://cyc-02/no-store-b")
    parent_problem, context, _candidate = _cyc01_owner_bound_n5_case()
    problems = {
        root: parent_problem,
        child_refs[0]: _problem("cyc02_no_store_a"),
        child_refs[1]: _problem("cyc02_no_store_b"),
    }
    graph = derive_recursive_design_graph(
        design_ref=root,
        module_refs=child_refs,
        parent_child_edges=((root, child_refs[0]), (root, child_refs[1])),
        rule_version_ref="repo://rules/cyc-02-recursive-no-store",
    )
    request = _recursive_parent_request(
        parent_ref=root,
        child_refs=child_refs,
        problem=parent_problem,
        world_model_record=context.world_model_record,
    )
    controller = _recursive_contract_testing_controller(tmp_path)

    class _N5ControllerSentinel:
        calls = 0

        def run(self, _request: object) -> object:
            self.calls += 1
            raise AssertionError("parent N5 controller ran without its runtime store")

    n5_sentinel = _N5ControllerSentinel()
    controller._joint_simulation_controller = n5_sentinel  # type: ignore[assignment]
    # The pinned public-parent selector fails before this seam at R2 currentness.
    # This narrow run keeps that validator out of the subject under test without
    # changing production validation or claiming a served whole-parent witness.
    monkeypatch.setattr(
        recursive_generation_cycle_module,
        "validate_generation_cycle_run",
        lambda *_args, **_kwargs: (),
    )

    with pytest.raises(
        RecursiveGenerationCycleError,
        match="recursive_n5_runtime_store_not_established",
    ):
        await controller.run(
            graph,
            problems_by_node=problems,
            budget_state=BudgetState(
                limits={"run": BudgetLimit(key="run", max_usd=Decimal("5.0"))}
            ),
            recursive_budget=RecursiveCycleBudget(
                max_depth=1,
                max_nodes=3,
                min_cycles_per_leaf=1,
                max_cycles_per_leaf=1,
            ),
            joint_simulation_requests_by_node={root: request},
            subdesign_contracts_by_node={
                root: _recursive_subdesigns(parent_ref=root, child_refs=child_refs)
            },
        )

    assert n5_sentinel.calls == 0


def test_n5_replay_uses_supplied_guarded_tenant_store(tmp_path: Path) -> None:
    """The N5 writer and N8 reader share the caller's tenant-owned store."""

    store = guard_runtime_cas(
        with_ambient_ownership_enforcement_if_supported(
            FileSystemCAS(tmp_path / "guarded-runtime-store")
        )
    )
    try:
        with tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"):
            problem, context, candidate, simulation, _produced, supplied_store = (
                _real_n5_observation(tmp_path, artifact_store=store)
            )
            assert supplied_store is store
            observation = _DefaultSimulationBoundFoundryValuePort(
                repo_root=tmp_path,
                cycle_substrate_context=context,
                artifact_store=supplied_store,
            )(
                candidate=candidate,
                simulation=simulation,
                problem=problem,
                cycle_index=0,
            )
            assert observation.status == "value_conditional"
            assert simulation.simulation_result_ref is not None

        with (
            tenant_scope(None, tenant_id="tenant-b", cell_id="cell-b"),
            pytest.raises(
                GenerationCycleError,
                match="joint_simulation_result_unavailable",
            ),
        ):
            load_joint_simulation_result(
                simulation.simulation_result_ref,
                store=store,
            )
    finally:
        store.close()


def test_n5_does_not_execute_without_runtime_owned_store(tmp_path: Path) -> None:
    """A valid request cannot execute if N5 cannot durably replay its result."""

    _problem, _context, _candidate, simulation, _produced, store = _real_n5_observation(
        tmp_path,
        without_runtime_store=True,
    )

    assert store is None
    assert simulation.status == "simulation_blocked"
    assert simulation.simulation_result_ref is None
    assert simulation.authority_blockers == ("n5_runtime_store_not_established",)
