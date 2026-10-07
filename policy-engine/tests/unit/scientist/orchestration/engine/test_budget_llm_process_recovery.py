"""Real process interruption and caller cancellation of durable LLM consumers.

The SDK boundary is a local provider that fsyncs its actual request, then waits
on a pipe. Ledger, cache, tracing, accounting and protected audit are canonical.
SIGKILL establishes process interruption, not a power-loss or billing claim.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import select
import signal
import subprocess
import sys
from dataclasses import asdict
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from polisyos.core.llm import settlement, traced_client
from polisyos.core.llm.settlement import producer_settlement
from polisyos.core.llm.traced_client import LLMAccountingError, TracedLLMClient
from polisyos.core.security.audit_log_adapter import ChainedAuditLog
from polisyos.core.security.audit_sink import ChainedAuditSink
from polisyos.core.security.audit_verifier import ChainVerifier
from polisyos.scientist.orchestration.engine import budget_ledger, budget_middleware
from polisyos.scientist.orchestration.engine.budget import BudgetLimit, BudgetState
from polisyos.scientist.orchestration.engine.budget_ledger import FileBudgetLedger
from polisyos.scientist.orchestration.engine.budget_middleware import BudgetMiddleware
from polisyos.scientist.orchestration.llm import budget_enforcer, gateway_client, prompt_cache
from polisyos.scientist.orchestration.llm.budget_enforcer import LLMBudgetEnforcer
from polisyos.scientist.orchestration.llm.gateway_client import GatewayLLMResponse, GatewayUsage
from polisyos.scientist.orchestration.llm.prompt_cache import CachingLLMClient, InMemoryPromptCache

_DRIVER = (
    "import runpy,sys; "
    "ns=runpy.run_path(sys.argv[1],run_name='physical_budget_process'); "
    "ns['_driver'](sys.argv[2:])"
)
_RUN = "bounded-process-recovery"


def _rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


def _source_bindings() -> list[dict[str, str]]:
    source_root = Path(os.environ["E02_DUR_PROCESS_SOURCE_ROOT"]).resolve()
    source_sha = os.environ["E02_DUR_PROCESS_SOURCE_SHA"]
    rows = []
    for module in (
        budget_ledger,
        budget_middleware,
        budget_enforcer,
        gateway_client,
        settlement,
        traced_client,
        prompt_cache,
    ):
        path = Path(module.__file__).resolve()
        assert path.is_relative_to(source_root / "policy-engine/src"), path
        expected = subprocess.check_output(
            ["git", "-C", str(source_root), "show", f"{source_sha}:{path.relative_to(source_root)}"]
        )
        assert path.read_bytes() == expected, path
        rows.append(
            {
                "module": module.__name__,
                "path": str(path),
                "sha256": hashlib.sha256(expected).hexdigest(),
            }
        )
    return rows


class _PipeProvider:
    def __init__(self, root: Path, *, gated: bool) -> None:
        self.root = root
        self.gated = gated
        self.entered = asyncio.Event()
        self.release = asyncio.Event()

    async def generate(self, **kwargs: Any) -> GatewayLLMResponse:
        snapshot = FileBudgetLedger(self.root / "ledger.json").snapshot()
        with (self.root / "provider.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(
                json.dumps(
                    {
                        "pid": os.getpid(),
                        "request": kwargs,
                        "intent_snapshot": snapshot.model_dump(mode="json"),
                    },
                    sort_keys=True,
                )
                + "\n"
            )
            stream.flush()
            os.fsync(stream.fileno())
        self.entered.set()
        if self.gated:
            await self.release.wait()
        return GatewayLLMResponse(
            content="observed local SDK result",
            model="default",
            provider="fsynced-local-SDK",
            usage=GatewayUsage(prompt_tokens=3, completion_tokens=2, cost_usd=0.02),
            request_id=f"physical:{os.getpid()}",
            raw=None,
        )


def _stack(root: Path, *, gated: bool) -> tuple[LLMBudgetEnforcer, _PipeProvider]:
    initial = BudgetState(
        limits={key: BudgetLimit(key=key, max_usd=Decimal("10")) for key in ("run", "other")}
    )
    middleware = BudgetMiddleware(initial, ledger=FileBudgetLedger(root / "ledger.json"))
    provider = _PipeProvider(root, gated=gated)
    cache = CachingLLMClient(provider, cache=InMemoryPromptCache(), model="default")
    client = TracedLLMClient(cache, model_name="default", run_id=_RUN)
    audit = ChainedAuditLog(ChainedAuditSink(chain_id=_RUN, local_path=root / "audit.jsonl"))
    enforcer = LLMBudgetEnforcer(
        client=client,
        budget_state=middleware.budget_state,
        budget_keys=["run"],
        model_name="default",
        run_id=_RUN,
        budget_middleware=middleware,
        audit_log=audit,
    )
    return enforcer, provider


async def _call(enforcer: LLMBudgetEnforcer) -> Any:
    return await enforcer.generate(
        user="fixed actual request", max_tokens=4, _prompt_tokens_estimate=3
    )


def _observation(root: Path) -> dict[str, Any]:
    audit_path = root / "audit.jsonl"
    return {
        "snapshot": FileBudgetLedger(root / "ledger.json").snapshot().model_dump(mode="json"),
        "physical_requests": _rows(root / "provider.jsonl"),
        "audit": _rows(audit_path),
        "audit_verification": asdict(ChainVerifier().verify_jsonl_file(audit_path)),
    }


async def _owner(root: Path, mode: str) -> dict[str, Any]:
    enforcer, provider = _stack(root, gated=True)
    caller = asyncio.create_task(_call(enforcer))
    await asyncio.wait_for(provider.entered.wait(), 20)
    before = _observation(root)
    cancelled = False
    if mode == "cancel":
        caller.cancel()
        try:
            await caller
        except asyncio.CancelledError:
            cancelled = True
    print("EFFECT " + json.dumps({"cancelled": cancelled, **before}, sort_keys=True), flush=True)
    command = await asyncio.to_thread(sys.stdin.readline)
    assert command.strip() == "release"
    provider.release.set()
    if mode == "cancel":
        # Wait for the actual BUDGET_COMMITTED sink effect and durable record
        # retirement, not for a task count or a declaration of completion.
        async with asyncio.timeout(20):
            while True:
                observed = _observation(root)
                if not observed["snapshot"]["completion_obligations"] and any(
                    row["payload"]["action"] == "BUDGET_COMMITTED" for row in observed["audit"]
                ):
                    break
                await asyncio.sleep(0)
        response_ack = None
    else:
        response = await caller
        actual = producer_settlement(response)
        assert actual is not None
        response_ack = {
            "event": asdict(actual.event),
            "status": actual.ack.status,
            "durability": actual.ack.durability,
        }
    return {"cancelled": cancelled, "response_ack": response_ack, **_observation(root)}


async def _fresh(root: Path) -> dict[str, Any]:
    enforcer, _ = _stack(root, gated=False)
    old = (root / "ledger.json").read_bytes()
    try:
        await _call(enforcer)
    except LLMAccountingError as error:
        status = {
            "status": "refused",
            "exception": type(error).__name__,
            "cause": type(error.cause).__name__,
        }
    else:
        status = {"status": "accepted"}
    after = (root / "ledger.json").read_bytes()
    # A separate unaffected key remains operational without clearing the
    # uncertain run-key attempt or asserting that the provider charged zero.
    fresh = BudgetMiddleware(BudgetState(), ledger=FileBudgetLedger(root / "ledger.json"))
    other_reserved = fresh.reserve_safe("other", Decimal("0.1"))
    fresh.release_safe("other", Decimal("0.1"))
    return {
        **status,
        "refusal_bytes_unchanged": old == after,
        "other_key_reserved": other_reserved,
        **_observation(root),
    }


def _driver(arguments: list[str]) -> None:
    root, mode = Path(arguments[0]), arguments[1]
    root.mkdir(exist_ok=True)
    bindings = _source_bindings()
    result = asyncio.run(_fresh(root) if mode == "fresh" else _owner(root, mode))
    print(
        "RESULT "
        + json.dumps({"source_bindings": bindings, **result}, sort_keys=True, default=str),
        flush=True,
    )


def _argv(root: Path, mode: str) -> list[str]:
    return [sys.executable, "-c", _DRIVER, str(Path(__file__).resolve()), str(root), mode]


def _read_line(child: subprocess.Popen[str], prefix: str) -> dict[str, Any]:
    assert child.stdout is not None
    ready, _, _ = select.select([child.stdout], [], [], 30)
    assert ready, "actual provider did not reach its file-backed boundary"
    line = child.stdout.readline()
    assert line.startswith(prefix), line
    return json.loads(line.removeprefix(prefix))


@pytest.mark.parametrize("mode", ["healthy", "cancel", "kill"])
def test_real_sdk_process_recovery_keeps_effect_accounting_and_audit_distinct(
    tmp_path: Path, mode: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = Path(__file__).resolve().parents[6]
    sha = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
    monkeypatch.setenv("E02_DUR_PROCESS_SOURCE_ROOT", str(root))
    monkeypatch.setenv("E02_DUR_PROCESS_SOURCE_SHA", sha)
    with subprocess.Popen(
        _argv(tmp_path, "healthy" if mode == "kill" else mode),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    ) as child:
        try:
            effect = _read_line(child, "EFFECT ")
            if mode == "kill":
                child.send_signal(signal.SIGKILL)
                stdout, stderr = child.communicate(timeout=20)
                assert child.returncode == -signal.SIGKILL
                settled = None
            else:
                assert child.stdin is not None
                child.stdin.write("release\n")
                child.stdin.flush()
                stdout, stderr = child.communicate(timeout=30)
                assert child.returncode == 0, stderr
                settled = json.loads(
                    next(
                        line.removeprefix("RESULT ")
                        for line in stdout.splitlines()
                        if line.startswith("RESULT ")
                    )
                )
        finally:
            if child.poll() is None:
                child.kill()
                child.wait()
    completed = subprocess.run(
        _argv(tmp_path, "fresh"), capture_output=True, text=True, timeout=30, check=False
    )
    assert completed.returncode == 0, completed.stderr
    fresh = json.loads(
        next(
            line.removeprefix("RESULT ")
            for line in completed.stdout.splitlines()
            if line.startswith("RESULT ")
        )
    )
    print(
        "PROCESS_RECOVERY "
        + json.dumps(
            {
                "mode": mode,
                "effect": effect,
                "owner": settled,
                "owner_stdout": stdout,
                "owner_stderr": stderr,
                "fresh": fresh,
                "fresh_stderr": completed.stderr,
            },
            sort_keys=True,
        )
    )
    intent = effect["snapshot"]["completion_obligations"]
    assert len(effect["physical_requests"]) == len(intent) == 1
    original = next(iter(intent.values()))
    assert original["phase"] == "provider_in_flight"
    assert Decimal(original["reserved_amounts"]["run"]) > 0
    assert effect["snapshot"]["spend_receipts"] == {}
    assert effect["snapshot"]["state"]["spent"] == {}
    assert fresh["other_key_reserved"] is True
    if mode == "kill":
        assert fresh["status"] == "refused"
        assert fresh["refusal_bytes_unchanged"] is True
        assert len(fresh["physical_requests"]) == 1
        assert fresh["snapshot"]["completion_obligations"] == intent
        assert fresh["snapshot"]["spend_receipts"] == {}
        assert not any(row["payload"]["action"] == "BUDGET_COMMITTED" for row in fresh["audit"])
    else:
        assert settled is not None
        assert settled["cancelled"] is (mode == "cancel")
        assert settled["snapshot"]["completion_obligations"] == {}
        assert settled["snapshot"]["state"]["spent"]["run"] == "0.02"
        assert len(settled["snapshot"]["spend_receipts"]) == 1
        assert settled["audit_verification"]["chain_intact"] is True
        assert (
            len([row for row in settled["audit"] if row["payload"]["action"] == "BUDGET_COMMITTED"])
            == 1
        )
        assert fresh["status"] == "accepted"
        assert len(fresh["physical_requests"]) == 2
        assert fresh["snapshot"]["state"]["spent"]["run"] == "0.04"
        assert len(fresh["snapshot"]["spend_receipts"]) == 2
