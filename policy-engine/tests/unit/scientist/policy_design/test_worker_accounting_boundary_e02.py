"""Real policy workers must preserve obtained-but-unaccounted provider outcomes.

Only the gateway HTTP/SDK boundary is replaced. The factory, decoder, cache,
tracing, budget wrapper, worker and deterministic fallback are canonical.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import subprocess
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from polisyos.core.llm import response, settlement, traced_client
from polisyos.core.llm.traced_client import LLMAccountingError
from polisyos.scientist.methods.search.readiness import (
    DecisionReadiness,
    DecisionReadinessContract,
)
from polisyos.scientist.orchestration.engine import budget, budget_ledger, budget_middleware
from polisyos.scientist.orchestration.engine.budget import BudgetLimit, BudgetState
from polisyos.scientist.orchestration.engine.budget_ledger import FileBudgetLedger
from polisyos.scientist.orchestration.engine.budget_middleware import BudgetMiddleware
from polisyos.scientist.orchestration.llm import (
    budget_enforcer,
    factory,
    gateway_client,
    prompt_cache,
)
from polisyos.scientist.orchestration.llm.budget_enforcer import LLMBudgetEnforcer
from polisyos.scientist.policy_design import adversary, translator
from polisyos.scientist.policy_design.output import (
    ChampionPolicyDossier,
    ConstraintSatisfactionReport,
    SubgroupImpactReport,
    UncertaintyReport,
)


def _source_origins() -> list[dict[str, str]]:
    root = Path(adversary.__file__).resolve().parents[5]
    declared_root = os.environ.get("E02_WORKER_ACCOUNTING_ROOT")
    if declared_root is not None:
        assert root == Path(declared_root).resolve()
    head = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
    assert head == os.environ.get("E02_WORKER_ACCOUNTING_SHA", head)
    rows = []
    for module in (
        adversary,
        translator,
        factory,
        gateway_client,
        prompt_cache,
        budget_enforcer,
        budget,
        budget_ledger,
        budget_middleware,
        response,
        settlement,
        traced_client,
    ):
        path = Path(module.__file__).resolve()
        assert path.is_relative_to(root / "policy-engine" / "src")
        data = path.read_bytes()
        assert data == subprocess.check_output(
            ["git", "-C", str(root), "show", f"{head}:{path.relative_to(root)}"]
        )
        rows.append(
            {
                "module": module.__name__,
                "path": str(path),
                "sha256": hashlib.sha256(data).hexdigest(),
                "source_sha": head,
            }
        )
    return rows


def _translator_input(state: BudgetState | None) -> translator.TranslatorInputBundle:
    readiness = DecisionReadiness.RECOMMENDATION_READY
    return translator.TranslatorInputBundle(
        dossier=ChampionPolicyDossier(
            candidate_id="actual-worker-candidate",
            candidate_hash="sha256:" + "a" * 64,
            readiness_level=readiness.value,
            executive_summary="Observed candidate evidence.",
            objective_summary={"policy_value": 1.2},
            constraint_summary=[],
            subgroup_harms=[],
            surfaced_assumptions=[],
            uncertainty_summary={},
            transport_summary={},
            governance_summary={},
            stress_summary={},
        ),
        readiness_contract=DecisionReadinessContract(
            readiness_level=readiness,
            required_judges_passed=[],
            required_uncertainty_bounds={},
            mandatory_human_gate=True,
            assumptions_must_be_surfaced=[],
            expiry_conditions=[],
            evidence_depth_required="meta_analytic",
        ),
        constraint_report=ConstraintSatisfactionReport(
            candidate_id="actual-worker-candidate",
            feasible=True,
            constraints=[],
        ),
        subgroup_report=SubgroupImpactReport(
            candidate_id="actual-worker-candidate",
            harmed_subgroups=[],
        ),
        uncertainty_report=UncertaintyReport(
            candidate_id="actual-worker-candidate",
            readiness_level=readiness.value,
            uncertainties={},
            binding_types=[],
        ),
        budget_state=state,
        run_id="same-actual-worker-run",
    )


@pytest.mark.parametrize("worker_kind", ["adversary", "translator"])
@pytest.mark.parametrize(
    "profile",
    [
        "configured-unknown",
        "configured-known",
        "raw-only",
        "mixed",
        "ledgerless",
        "unbudgeted-known",
        "active-loop-raw",
    ],
)
def test_actual_worker_preserves_accounting_unknown_before_fresh_worker(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    worker_kind: str,
    profile: str,
) -> None:
    origins = _source_origins()
    keys = (
        ["policy_adversary"]
        if worker_kind == "adversary"
        else ["policy_translator", "policy_briefing"]
    )
    state = BudgetState(limits={key: BudgetLimit(key=key, max_usd=Decimal("10")) for key in keys})
    ledger_path = tmp_path / "actual-worker-budget.json"
    configured = profile in {"configured-unknown", "configured-known", "mixed"}
    if configured:
        BudgetMiddleware(state, ledger=FileBudgetLedger(ledger_path))
    raw = profile in {"raw-only", "mixed", "active-loop-raw"}
    bundle = _translator_input(state if raw else None)
    cost_kind = "missing-sdk-usage" if profile == "configured-unknown" else "reported-positive"
    actual_content = (
        {
            "scenarios": [
                {
                    "scenario_id": "obtained-scenario",
                    "scenario_type": "shift",
                    "rationale": "Obtained response.",
                }
            ]
        }
        if worker_kind == "adversary"
        else translator.DeterministicPolicyTranslator().translate(bundle).model_dump(mode="json")
    )
    if worker_kind == "translator":
        actual_content["title"] = "Obtained physical provider brief"
    physical = tmp_path / "physical-provider-work.jsonl"
    for key, value in {
        "POLISYOS_LLM_GATEWAY_BASE_URL": "https://worker-oracle.invalid/v1",
        "POLISYOS_LLM_GATEWAY_API_KEY": "sk-worker-oracle-boundary-fixture",
        "POLISYOS_LLM_SIMULATION_MODE": "false",
        "POLISYOS_METRICS_PORT": "0",
    }.items():
        monkeypatch.setenv(key, value)

    async def sdk_boundary(
        self: Any, *, endpoint: str, payload: dict[str, Any], timeout_s: float
    ) -> dict[str, Any]:
        with physical.open("a", encoding="utf-8") as stream:
            stream.write(
                json.dumps({"endpoint": endpoint, "payload": payload, "timeout_s": timeout_s})
                + "\n"
            )
            stream.flush()
            os.fsync(stream.fileno())
        result = {
            "choices": [{"message": {"content": json.dumps(actual_content)}}],
            "model": self.model,
            "provider": "actual-sdk-boundary-fixture",
        }
        if cost_kind == "reported-positive":
            result["usage"] = {
                "prompt_tokens": 7,
                "completion_tokens": 3,
                "total_tokens": 10,
                "cost_usd": 0.02,
            }
        return result

    monkeypatch.setattr(gateway_client.GatewayLLMClient, "_post_json", sdk_boundary)
    observed_errors: list[dict[str, Any]] = []
    caught_worker_errors: list[dict[str, str]] = []
    original_trace = sys.gettrace()

    def observe(frame: Any, event: str, arg: Any) -> Any:
        if event == "exception" and frame.f_code in (
            adversary.ScenarioAdversaryWorker.propose_async.__code__,
            translator.PolicyTranslatorWorker.translate_async.__code__,
        ):
            caught_worker_errors.append({"type": type(arg[1]).__name__, "message": str(arg[1])})
        if event == "exception" and frame.f_code is LLMBudgetEnforcer.generate.__code__:
            error = arg[1]
            if isinstance(error, LLMAccountingError):
                producer = error.event.get("producer_event")
                observed_errors.append(
                    {
                        "type": type(error).__name__,
                        "message": str(error),
                        "amount": str(producer.amount)
                        if producer is not None and producer.amount is not None
                        else None,
                        "cost_origin": getattr(producer, "cost_origin", None),
                        "status": error.event.get("settlement_status"),
                    }
                )
        return observe

    async def invoke_fresh_worker() -> Any:
        middleware = (
            BudgetMiddleware(BudgetState(), ledger=FileBudgetLedger(ledger_path))
            if configured
            else BudgetMiddleware(state)
            if profile == "ledgerless"
            else None
        )
        if worker_kind == "adversary":
            worker = adversary.ScenarioAdversaryWorker(
                adversary.ScenarioAdversaryConfig(model_name="explicit-worker-oracle-model"),
                budget_middleware=middleware,
            )
            surface = adversary.ScenarioAttackSurface(candidate_id="actual-worker-candidate")
            if profile == "active-loop-raw":
                return worker.propose(surface, run_id="same-actual-worker-run", budget_state=state)
            return await worker.propose_async(
                surface,
                run_id="same-actual-worker-run",
                budget_state=state if raw else None,
            )
        worker = translator.PolicyTranslatorWorker(
            translator.PolicyTranslatorConfig(model_name="explicit-worker-oracle-model"),
            budget_middleware=middleware,
        )
        if profile == "active-loop-raw":
            return worker.translate(bundle)
        return await worker.translate_async(bundle)

    outcomes = []
    sys.settrace(observe)
    try:
        for _ in range(2):
            try:
                value = asyncio.run(invoke_fresh_worker())
                outcomes.append(
                    {"returned_type": type(value).__name__, "value": value.model_dump(mode="json")}
                )
            except Exception as exc:
                outcomes.append({"exception": type(exc).__name__, "message": str(exc)})
    finally:
        sys.settrace(original_trace)
    physical_rows = (
        [json.loads(line) for line in physical.read_text().splitlines()]
        if physical.exists()
        else []
    )
    quantities = {
        "worker": worker_kind,
        "cost_kind": cost_kind,
        "origins": origins,
        "physical_calls": len(physical_rows),
        "physical_work": physical_rows,
        "actual_enforcer_errors": observed_errors,
        "caught_worker_errors": caught_worker_errors,
        "worker_outcomes": outcomes,
        "same_budget_state": state.model_dump(mode="json"),
        "profile": profile,
        "reopened_actual_ledger": FileBudgetLedger(ledger_path).snapshot().model_dump(mode="json")
        if configured
        else None,
    }
    print("E02_WORKER_ACCOUNTING " + json.dumps(quantities, sort_keys=True))
    if profile == "configured-unknown":
        assert outcomes[0].get("exception") == "LLMAccountingError", quantities
        assert outcomes[1].get("exception") == "LLMAccountingError", quantities
        assert len(physical_rows) == 1, quantities
        assert (
            observed_errors[0]["amount"] is None and observed_errors[0]["cost_origin"] == "unknown"
        ), quantities
        snapshot = FileBudgetLedger(ledger_path).snapshot()
        assert not snapshot.spend_receipts and not snapshot.state.spent, quantities
        assert all(snapshot.state.reserved[key] > 0 for key in keys), quantities
        assert len(snapshot.completion_obligations) == 1, quantities
        assert next(iter(snapshot.completion_obligations.values())).phase == "cost_unknown", (
            quantities
        )
    elif profile in {"raw-only", "mixed", "ledgerless", "active-loop-raw"}:
        assert all(
            value.get("exception") == "PolicyWorkerAccountingAdmissionError" for value in outcomes
        ), quantities
        assert not physical_rows and not observed_errors, quantities
        assert not state.spent and not state.reserved, quantities
        if configured:
            snapshot = FileBudgetLedger(ledger_path).snapshot()
            assert not snapshot.spend_receipts and not snapshot.completion_obligations, quantities
    else:
        assert not observed_errors and all("exception" not in value for value in outcomes), (
            quantities
        )
        assert len(physical_rows) == 2, quantities
        if worker_kind == "adversary":
            assert all(not value["value"]["fallback_used"] for value in outcomes), quantities
        else:
            assert all(
                value["value"]["title"] == "Obtained physical provider brief" for value in outcomes
            ), quantities
        if configured:
            snapshot = FileBudgetLedger(ledger_path).snapshot()
            assert all(snapshot.state.spent[key] == Decimal("0.04") for key in keys), quantities
            assert not snapshot.completion_obligations, quantities
            assert len(snapshot.spend_receipts) == 2 * len(keys), quantities
        else:
            assert not state.spent and not state.reserved, quantities
