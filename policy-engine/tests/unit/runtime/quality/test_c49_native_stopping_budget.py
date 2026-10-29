"""Portable real-owner consumers; external wire substituted, physics stays native.

These program witnesses do not establish production scientific authenticity,
selected objective intent, model calibration, or a numerical-work USD price.
"""

from __future__ import annotations

import asyncio
import copy
from decimal import Decimal
from types import SimpleNamespace

import pytest

from polisyos.core.artifacts import read_core_json_artifact
from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.llm.traced_client import TracedLLMClient
from polisyos.foundry.methods.catalog.causal.ncm_engine import NCMEngineMethod
from polisyos.runtime.quality import design_generation as n4
from polisyos.runtime.quality import joint_simulation_horizon as horizon
from polisyos.runtime.quality.generation_cycle import (
    GenerationCycleError,
    _joint_simulation_port_outcome,
    load_joint_simulation_result,
    persist_joint_simulation_result,
)
from polisyos.runtime.quality.generation_source import GenerationSourceRepository
from polisyos.runtime.quality.joint_simulation_horizon import (
    HorizonSpec,
    JointSimulationControllerError,
    JointSimulationHorizonController,
    JointSimulationResult,
    ProofReceiptError,
    build_content_bound_simulation_receipt,
    verify_simulation_receipt,
)
from polisyos.scientist.orchestration.engine.budget import BudgetLimit, BudgetState
from polisyos.scientist.orchestration.engine.budget_ledger import (
    BudgetLedgerProducerRunBinding,
    FileBudgetLedger,
)
from polisyos.scientist.orchestration.engine.budget_middleware import BudgetMiddleware
from polisyos.scientist.orchestration.engine.producer_budget import ProducerBudgetObserver
from tests.unit.runtime.quality.test_design_generation import (
    REPO_ROOT,
    TerminalCriticTransientClient,
    _test_design_problem,
)
from tests.unit.runtime.quality.test_joint_simulation_horizon import _request


class VersionedN4Wire(TerminalCriticTransientClient):
    """Reuse the existing portable three-organ transport, with declared fixture weights."""

    def _response(self, payload, *, role):
        value = super()._response(payload, role=role)
        return SimpleNamespace(
            content=value.content,
            usage=value.usage,
            model=value.model,
            provider=value.provider,
            model_version="fixture-weights-1",
            cost_usd=0.001,
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("profile", "expected_kind"),
    [
        (
            '{"threshold":0.01,"min_iterations":2,"max_iterations":10,"window_size":2}',
            "heuristic_stability",
        ),
        ('{"min_iterations":1,"max_iterations":1,"window_size":2}', "resource_limit"),
    ],
)
async def test_configured_n4_profile_reaches_real_drafter_and_fresh_source_owner(
    tmp_path,
    monkeypatch,
    profile,
    expected_kind,
):
    monkeypatch.setenv("POLISYOS_DRAFTER_CONVERGENCE_JSON", profile)
    monkeypatch.setenv("POLISYOS_N4_TERMINAL_SALVAGE_BACKOFF_BASE_S", "0")
    problem = _test_design_problem()
    problem = problem.model_copy(
        update={
            "nl_provenance": problem.nl_provenance.model_copy(
                update={
                    "source_context": {
                        **problem.nl_provenance.source_context,
                        "tenant_id": "tenant-c49",
                        "cell_id": "cell-c49",
                        "job_id": "job-c49",
                        "run_id": "run-c49",
                    },
                }
            )
        }
    )
    proposal = await n4.generate_design_candidate_proposal_under_a(
        problem,
        model_id=n4.SUPPORTED_GENERATION_MODEL_IDS[1],
        llm_client=VersionedN4Wire(),
        repo_root=REPO_ROOT,
    )
    assert type(proposal) is n4.N4CandidateProposalSource
    state = proposal.draft.convergence_state
    assert state.should_stop and state.stop_kind == expected_kind
    assert not state.scientific_converged and state.profile is not None
    assert state.last_checked_observation.model_version == "fixture-weights-1"
    assert proposal.n5_status == proposal.n8_status == proposal.n9_status == "not_run"
    store_path = tmp_path / "n4-owner-cas"
    writer = GenerationSourceRepository(FileSystemCAS(store_path))
    ref = writer.persist_candidate_proposal(
        job_id="job-c49",
        run_id="run-c49",
        tenant_id="tenant-c49",
        cell_id="cell-c49",
        raw_request=problem.nl_provenance.raw_request,
        problem=problem,
        proposal=proposal,
    )
    fresh = GenerationSourceRepository(FileSystemCAS(store_path)).load_candidate_proposal(
        ref,
        job_id="job-c49",
        run_id="run-c49",
        tenant_id="tenant-c49",
        cell_id="cell-c49",
        raw_request=problem.nl_provenance.raw_request,
    )
    assert fresh.proposal.draft.convergence_state == state
    assert fresh.proposal.draft.confidence_observation == proposal.draft.confidence_observation
    deciding_raw = state.last_checked_observation.source_ref
    import hashlib

    assert any(
        hashlib.sha256(call.raw_llm_response.encode()).hexdigest() == deciding_raw
        for call in fresh.proposal.llm_calls
        if isinstance(call.raw_llm_response, str)
    )


class CostWire:
    provider = "fixture-cost-wire"

    def __init__(self, amount):
        self.amount = amount

    async def generate(self, **kwargs):
        return SimpleNamespace(
            content="bounded actual provider response",
            cost_usd=self.amount,
            usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1),
        )


def _producer_owner(tmp_path, *, cap="1"):
    store = BudgetMiddleware(BudgetState(), ledger=FileBudgetLedger(tmp_path / "ledger.json"))
    binding = BudgetLedgerProducerRunBinding(
        run_id="native-run-c49",
        tenant_id="tenant-c49",
        cell_id="cell-c49",
        profile_id="profile-c49",
        control_job_id="job-c49",
    )
    state = BudgetState(limits={"run": BudgetLimit(key="run", max_usd=Decimal(cap))})
    return store, binding, state


def _real_provider_charge(store, binding, amount, label):
    client = TracedLLMClient(
        CostWire(amount),
        model_name="fixture-model",
        producer_settlement_store=store,
        producer_budget_key=f"nl-run:{binding.run_id}",
    )
    with store.producer_run_binding_scope(binding, control_job_attempt=1):
        return asyncio.run(client.generate(user=label))


def _native_request():
    return _request().model_copy(
        update={
            "horizon": HorizonSpec(start=0, end=0, step=1),
            "replications": 2,
            "seed": 11,
        }
    )


def test_actual_native_n5_work_units_are_unique_and_fresh_cas_reopens_them(tmp_path):
    store, binding, state = _producer_owner(tmp_path)
    _real_provider_charge(store, binding, 0.2, "before-native-work")
    observer = ProducerBudgetObserver(
        settlement_store=store,
        producer_run_binding=binding,
        budget_state=state,
    )
    request = _native_request()
    result = JointSimulationHorizonController(producer_budget_observer=observer).run(request)
    work = result.physical_work_observations
    # Two singles and one shared pair/joint specification, each at two actual seeds.
    assert len(work) == 6
    assert (
        len({(item.invocation_id, item.physical_spec_ref, item.effective_seed) for item in work})
        == 6
    )
    assert all(item.status == "completed" and item.work_units == 1 for item in work)
    assert all(item.budget_status == "current_owner_checked" for item in work)
    assert all(item.usd_cost is None and item.usd_cost_status == "not_established" for item in work)
    assert all(item.scientific_authenticity == "not_established" for item in work)
    assert len({item.budget_source_basis_digest for item in work}) == 1
    cas_path = tmp_path / "n5-cas"
    ref = persist_joint_simulation_result(result, store=FileSystemCAS(cas_path))
    fresh = load_joint_simulation_result(
        ref, store=FileSystemCAS(cas_path), expected_request=request
    )
    assert fresh.physical_work_observations == work
    events = {item.event_id: item for item in fresh.physical_work_observations}
    for trajectory in fresh.trajectories:
        run_ref = trajectory.diagnostics["physical_run_ref"]
        assert str(ArtifactID.model_validate(run_ref)) == run_ref
        for event_id in trajectory.diagnostics["physical_work_event_ids"]:
            assert events[event_id].physical_spec_ref == ArtifactID.model_validate(run_ref).hex
    pair = fresh.trajectory_for("pairwise", fresh.atom_ids)
    joint = fresh.trajectory_for("joint", fresh.atom_ids)
    assert pair.diagnostics["physical_run_ref"] == joint.diagnostics["physical_run_ref"]
    assert (
        pair.diagnostics["physical_work_event_ids"] == joint.diagnostics["physical_work_event_ids"]
    )
    assert state.spent["run"] == Decimal("0.2")  # N5 work was not converted to money.


def test_fresh_owner_exhaustion_between_real_seeds_stops_before_second_call(tmp_path, monkeypatch):
    store, binding, state = _producer_owner(tmp_path)
    _real_provider_charge(store, binding, 0.2, "before-first-seed")
    observer = ProducerBudgetObserver(
        settlement_store=store,
        producer_run_binding=binding,
        budget_state=state,
    )
    original = NCMEngineMethod.pure_step
    calls = []

    def actual_method_then_new_owner_event(method_state, params):
        output = original(method_state, params)  # Real selected NCM computation remains in place.
        calls.append(params["__seed__"])
        if len(calls) == 1:
            _real_provider_charge(store, binding, 0.8, "new-owner-spend-between-seeds")
        return output

    monkeypatch.setattr(
        NCMEngineMethod, "pure_step", staticmethod(actual_method_then_new_owner_event)
    )
    request = _native_request()
    result = JointSimulationHorizonController(producer_budget_observer=observer).run(request)
    assert len(calls) == 1  # Removing per-seed admission must make this assertion fail.
    assert result.diagnostics["physical_work_interruption"] == "n5_current_budget_exhausted"
    assert len(result.physical_work_observations) == 1
    assert result.physical_work_observations[0].status == "completed"
    assert result.trajectories == ()  # A partial replicate set is not a completed role.
    assert observer.last_checked.remaining_usd == Decimal("0")
    cas_path = tmp_path / "interrupted-cas"
    ref = persist_joint_simulation_result(result, store=FileSystemCAS(cas_path))
    # Custody of an interrupted report is not admission as a numerical result.
    fresh_store = FileSystemCAS.open_existing_read_only(cas_path)
    selected = read_core_json_artifact(fresh_store, ref)
    assert selected.status == "declared_bytes_conformant"
    assert selected.selected_artifact_id == str(ref.artifact_id)
    assert selected.selected_manifest_profile_sha256 == ref.manifest_profile_sha256
    payload = selected.value
    fresh = JointSimulationResult.model_validate(payload)
    original_projection = {key: value for key, value in payload.items() if key != "receipt"}
    verify_simulation_receipt(fresh.receipt, original_projection)
    assert fresh.physical_work_observations == result.physical_work_observations
    assert (
        fresh.diagnostics["producer_budget_observations"]
        == result.diagnostics["producer_budget_observations"]
    )
    assert (
        fresh.diagnostics["budget_interruption_basis"]
        == result.diagnostics["budget_interruption_basis"]
    )
    assert fresh.trajectories == ()
    assert fresh.receipt.trajectory_count == 0
    assert fresh.receipt.calibration_status == "no_run"
    assert fresh.receipt.authoritative_for == ()
    assert fresh.receipt.may_not_use_for == ("world_credal_state_shrinkage", "promotion")
    status, blockers = _joint_simulation_port_outcome(fresh)
    assert status == "simulation_blocked"
    assert "n5_current_budget_exhausted" in blockers
    with pytest.raises(GenerationCycleError, match="joint_simulation_result_trajectory_missing"):
        load_joint_simulation_result(ref, store=fresh_store)

    # Original producer bytes and receipt are retained; neither negative is reissued.
    changed_projection = copy.deepcopy(original_projection)
    changed_projection["diagnostics"]["physical_work_observations"] = []
    with pytest.raises(ProofReceiptError, match="receipt_content_mismatch"):
        verify_simulation_receipt(fresh.receipt, changed_projection)
    changed_payload = copy.deepcopy(payload)
    changed_payload["diagnostics"]["physical_work_observations"] = []
    with pytest.raises(ValueError, match="n5_physical_work_unit_count_mismatch"):
        JointSimulationResult.model_validate(changed_payload)

    # A stored audit snapshot cannot admit another call. Reopen the actual owner
    # and ledger for reentry; the settled spend still exhausts the configured cap.
    reopened_store, reopened_binding, reopened_state = _producer_owner(tmp_path)
    reopened_observer = ProducerBudgetObserver(
        settlement_store=reopened_store,
        producer_run_binding=reopened_binding,
        budget_state=reopened_state,
    )
    reentry = JointSimulationHorizonController(producer_budget_observer=reopened_observer).run(
        request
    )
    assert len(calls) == 1
    assert reentry.diagnostics["physical_work_interruption"] == "n5_current_budget_exhausted"
    assert reentry.physical_work_observations == ()
    assert reentry.trajectories == ()
    assert reopened_observer.last_checked.remaining_usd == Decimal("0")


@pytest.mark.parametrize("cap", ["0", "0.2"])
def test_independent_exhaustion_prevents_any_native_method_call(tmp_path, monkeypatch, cap):
    store, binding, state = _producer_owner(tmp_path, cap=cap)
    _real_provider_charge(store, binding, 0.2, "exhausted-before-n5")
    observer = ProducerBudgetObserver(
        settlement_store=store,
        producer_run_binding=binding,
        budget_state=state,
    )

    def must_not_run(*args, **kwargs):
        raise AssertionError("native physics began after independently established exhaustion")

    monkeypatch.setattr(NCMEngineMethod, "pure_step", staticmethod(must_not_run))
    result = JointSimulationHorizonController(producer_budget_observer=observer).run(
        _native_request()
    )
    assert result.diagnostics["physical_work_interruption"] == "n5_current_budget_exhausted"
    assert result.physical_work_observations == () and result.trajectories == ()


def _fixture_reissued_payload(result, payload):
    """Persist synthetic bytes with a real receipt so a fresh reader checks their semantics."""
    receipt = build_content_bound_simulation_receipt(
        engine_kind=result.receipt.engine_kind,
        payload=payload,
        diagnostics=payload["diagnostics"],
    )
    trajectories = tuple(
        original.model_copy(update={"diagnostics": supplied["diagnostics"]})
        for original, supplied in zip(result.trajectories, payload["trajectories"], strict=True)
    )
    carrier = result.model_copy(
        update={
            "schema_version": payload["schema_version"],
            "receipt": receipt,
            "diagnostics": payload["diagnostics"],
            "trajectories": trajectories,
        }
    )
    carrier._content_payload = payload
    return carrier


def _work_join_removed():
    """Remove the whole shared work verifier, leaving the original rows and markers."""

    def decode_without_reconciliation(result):
        raw = result.diagnostics.get("physical_work_observations")
        if type(raw) is not list:
            return ()
        return tuple(horizon.PhysicalSimulationWorkObservation.model_validate(item) for item in raw)

    return property(decode_without_reconciliation)


def test_fresh_work_reader_reconciles_digest_and_ref_and_fails_without_the_join(
    tmp_path, monkeypatch
):
    """Changed work, missing rows and missing trajectory basis refuse at real consumers."""
    request = _native_request()
    result = JointSimulationHorizonController().run(request)
    assert result.physical_work_observations and result.trajectories
    assert _joint_simulation_port_outcome(result, request=request)[0] == "joint_simulated"
    assert _joint_simulation_port_outcome(result)[0] == "joint_simulated"

    for alteration in (
        "digest",
        "missing_rows",
        "null_rows",
        "unknown_with_event_refs",
        "missing_trajectory_basis",
    ):
        payload = copy.deepcopy(result.content_bound_payload())
        event = payload["diagnostics"]["physical_work_observations"][0]
        assert any(
            event["event_id"] in row["diagnostics"]["physical_work_event_ids"]
            for row in payload["trajectories"]
        )
        if alteration == "digest":
            old_digest = event["physical_spec_ref"]
            event["physical_spec_ref"] = ("f" if old_digest != "f" * 64 else "e") * 64
            assert event["physical_spec_ref"] != old_digest
        elif alteration == "missing_rows":
            payload["diagnostics"].pop("physical_work_observations")
        elif alteration == "null_rows":
            payload["diagnostics"]["physical_work_observations"] = None
        elif alteration == "unknown_with_event_refs":
            payload["diagnostics"].pop("physical_work_observations")
            payload["diagnostics"]["physical_work_capture_status"] = "not_established"
            payload["diagnostics"]["physical_work_units"] = 0
            payload["diagnostics"]["producer_budget_observations"] = {}
        else:
            trajectory = payload["trajectories"][0]["diagnostics"]
            trajectory.pop("physical_work_event_ids")
            trajectory.pop("replication_seeds")
        if alteration != "unknown_with_event_refs":
            assert payload["diagnostics"]["physical_work_capture_status"] == "observed"
        store_path = tmp_path / ("work-join-" + alteration)
        carrier = _fixture_reissued_payload(result, payload)
        ref = persist_joint_simulation_result(carrier, store=FileSystemCAS(store_path))

        def fresh_read(ref=ref, store_path=store_path):
            return load_joint_simulation_result(
                ref, store=FileSystemCAS(store_path), expected_request=request
            )

        def candidate_outcomes(carrier=carrier):
            return (
                _joint_simulation_port_outcome(carrier, request=request),
                _joint_simulation_port_outcome(carrier),
            )

        for status, blockers in candidate_outcomes():
            assert status == "simulation_blocked"
            assert "selected_plan_execution_binding_missing" in blockers
        with pytest.raises(GenerationCycleError, match="joint_simulation_result_integrity_invalid"):
            fresh_read()
        with monkeypatch.context() as removal:
            removal.setattr(
                JointSimulationResult, "physical_work_observations", _work_join_removed()
            )
            for status, _ in candidate_outcomes():
                assert status == "joint_simulated"
            if alteration == "missing_trajectory_basis":
                # V3/V4 also validate trajectory seeds in a different owner.
                with pytest.raises(
                    GenerationCycleError, match="joint_simulation_result_integrity_invalid"
                ):
                    fresh_read()
            else:
                assert fresh_read().diagnostics == payload["diagnostics"]
        for status, blockers in candidate_outcomes():
            assert status == "simulation_blocked"
            assert "selected_plan_execution_binding_missing" in blockers
        with pytest.raises(GenerationCycleError, match="joint_simulation_result_integrity_invalid"):
            fresh_read()


def test_fresh_work_reader_preserves_legacy_exact_bare_join(tmp_path, monkeypatch):
    """Synthetic legacy v1 bytes still reopen without being rewritten or upgraded."""
    request = _native_request()
    result = JointSimulationHorizonController().run(request)
    payload = copy.deepcopy(result.content_bound_payload())
    for trajectory in payload["trajectories"]:
        diagnostics = trajectory["diagnostics"]
        diagnostics["physical_run_ref"] = ArtifactID.model_validate(
            diagnostics["physical_run_ref"]
        ).hex
    store_path = tmp_path / "legacy-work-cas"
    ref = persist_joint_simulation_result(
        _fixture_reissued_payload(result, payload), store=FileSystemCAS(store_path)
    )
    fresh = load_joint_simulation_result(ref, store=FileSystemCAS(store_path))
    events = {item.event_id: item for item in fresh.physical_work_observations}
    assert events and all(
        item.schema_version == "policyos.runtime.physical_simulation_work.v1"
        for item in events.values()
    )
    for trajectory in fresh.trajectories:
        for event_id in trajectory.diagnostics["physical_work_event_ids"]:
            assert events[event_id].physical_spec_ref == trajectory.diagnostics["physical_run_ref"]
    assert fresh.content_bound_payload() == payload
    # The older event join is readable, but it cannot establish the canonical
    # selected-request binding that the real current consumer recomputes.
    with pytest.raises(
        GenerationCycleError, match="joint_simulation_result_execution_binding_invalid"
    ):
        load_joint_simulation_result(ref, store=FileSystemCAS(store_path), expected_request=request)

    # Preserve a separate unobserved historical shape when no work is claimed.
    unknown = copy.deepcopy(result.content_bound_payload())
    unknown["diagnostics"].pop("physical_work_observations")
    unknown["diagnostics"]["physical_work_capture_status"] = "not_established"
    unknown["diagnostics"]["physical_work_units"] = 0
    unknown["diagnostics"]["producer_budget_observations"] = {}
    for trajectory in unknown["trajectories"]:
        trajectory["diagnostics"].pop("physical_work_event_ids")
    unknown_ref = persist_joint_simulation_result(
        _fixture_reissued_payload(result, unknown), store=FileSystemCAS(store_path)
    )
    unknown_fresh = load_joint_simulation_result(
        unknown_ref, store=FileSystemCAS(store_path), expected_request=request
    )
    assert unknown_fresh.physical_work_observations == ()
    assert unknown_fresh.diagnostics["physical_work_capture_status"] == "not_established"

    # Synthetic v1 bytes that claim observed work without its root/trajectory
    # basis must now refuse, even though the former local empty-list check
    # could accept that shape. No historical incidence is asserted.
    unsupported = copy.deepcopy(result.content_bound_payload())
    unsupported["schema_version"] = "policyos.runtime.joint_simulation_horizon.v1"
    unsupported["diagnostics"].pop("requested_replications")
    unsupported["diagnostics"].pop("replication_seeds")
    for trajectory in unsupported["trajectories"]:
        trajectory["diagnostics"].pop("physical_work_event_ids")
        trajectory["diagnostics"].pop("replication_seeds")
    unsupported_ref = persist_joint_simulation_result(
        _fixture_reissued_payload(result, unsupported), store=FileSystemCAS(store_path)
    )
    with pytest.raises(GenerationCycleError, match="joint_simulation_result_integrity_invalid"):
        load_joint_simulation_result(unsupported_ref, store=FileSystemCAS(store_path))
    with monkeypatch.context() as removal:
        removal.setattr(JointSimulationResult, "physical_work_observations", _work_join_removed())
        assert (
            load_joint_simulation_result(
                unsupported_ref, store=FileSystemCAS(store_path)
            ).schema_version
            == "policyos.runtime.joint_simulation_horizon.v1"
        )
    with pytest.raises(GenerationCycleError, match="joint_simulation_result_integrity_invalid"):
        load_joint_simulation_result(unsupported_ref, store=FileSystemCAS(store_path))


@pytest.mark.parametrize(
    "foreign_ref",
    ["sha512:" + "1" * 64, "sha256:" + "A" * 64, "sha256:" + "1" * 63, "1" * 64],
)
def test_physical_work_refuses_invalid_run_reference_before_native_call(foreign_ref, monkeypatch):
    monkeypatch.setattr(horizon, "_physical_run_ref", lambda *args: foreign_ref)

    def must_not_run(*args, **kwargs):
        raise AssertionError("native work began with an invalid physical run reference")

    monkeypatch.setattr(NCMEngineMethod, "pure_step", staticmethod(must_not_run))
    with pytest.raises(JointSimulationControllerError, match="n5_physical_run_ref_invalid"):
        JointSimulationHorizonController().run(_native_request())


@pytest.mark.parametrize("prefix", ["sha512:", "other:"])
def test_fresh_work_reader_refuses_unknown_algorithm_with_the_same_digest(tmp_path, prefix):
    result = JointSimulationHorizonController().run(_native_request())
    payload = copy.deepcopy(result.content_bound_payload())
    old_ref = payload["trajectories"][0]["diagnostics"]["physical_run_ref"]
    digest = ArtifactID.model_validate(old_ref).hex
    for trajectory in payload["trajectories"]:
        if trajectory["diagnostics"]["physical_run_ref"] == old_ref:
            trajectory["diagnostics"]["physical_run_ref"] = prefix + digest
    store_path = tmp_path / "foreign-algorithm-cas"
    ref = persist_joint_simulation_result(
        _fixture_reissued_payload(result, payload), store=FileSystemCAS(store_path)
    )
    with pytest.raises(GenerationCycleError, match="joint_simulation_result_integrity_invalid"):
        load_joint_simulation_result(ref, store=FileSystemCAS(store_path))
