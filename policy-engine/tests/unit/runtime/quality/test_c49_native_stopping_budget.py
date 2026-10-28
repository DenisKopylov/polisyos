"""Portable real-owner consumers; external wire substituted, physics stays native.

These program witnesses do not establish production scientific authenticity,
selected objective intent, model calibration, or a numerical-work USD price.
"""

from __future__ import annotations

import asyncio
from decimal import Decimal
from types import SimpleNamespace

import pytest

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.llm.traced_client import TracedLLMClient
from polisyos.foundry.methods.catalog.causal.ncm_engine import NCMEngineMethod
from polisyos.runtime.quality import design_generation as n4
from polisyos.runtime.quality.generation_cycle import (
    load_joint_simulation_result,
    persist_joint_simulation_result,
)
from polisyos.runtime.quality.generation_source import GenerationSourceRepository
from polisyos.runtime.quality.joint_simulation_horizon import (
    HorizonSpec,
    JointSimulationHorizonController,
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
    fresh = load_joint_simulation_result(ref, store=FileSystemCAS(cas_path))
    assert fresh.physical_work_observations == work
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
    result = JointSimulationHorizonController(producer_budget_observer=observer).run(
        _native_request()
    )
    assert len(calls) == 1  # Removing per-seed admission must make this assertion fail.
    assert result.diagnostics["physical_work_interruption"] == "n5_current_budget_exhausted"
    assert len(result.physical_work_observations) == 1
    assert result.physical_work_observations[0].status == "completed"
    assert result.trajectories == ()  # A partial replicate set is not a completed role.
    assert observer.last_checked.remaining_usd == Decimal("0")
    ref = persist_joint_simulation_result(result, store=FileSystemCAS(tmp_path / "interrupted-cas"))
    fresh = load_joint_simulation_result(ref, store=FileSystemCAS(tmp_path / "interrupted-cas"))
    assert fresh.physical_work_observations == result.physical_work_observations


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
