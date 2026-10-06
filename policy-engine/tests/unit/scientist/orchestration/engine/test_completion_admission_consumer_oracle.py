"""Independent physical-effect consumers of durable LLM completion admission.

The provider is a bounded local fixture with a real append/fsync effect, not a
claim about an external provider's billing. Every child constructs the real
ledger, middleware, traced client and enforcer. Faults target actual ledger
publication syscalls; a fresh process consumes the retained intent.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import stat
import subprocess
import sys
from collections.abc import Callable
from contextlib import AbstractContextManager
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from polisyos.core.llm.traced_client import LLMAccountingError, TracedLLMClient
from polisyos.scientist.orchestration.engine import budget_ledger as ledger_module
from polisyos.scientist.orchestration.engine.budget import BudgetLimit, BudgetState
from polisyos.scientist.orchestration.engine.budget_middleware import BudgetMiddleware
from polisyos.scientist.orchestration.llm.budget_enforcer import LLMBudgetEnforcer
from polisyos.scientist.orchestration.llm.gateway_client import GatewayLLMResponse, GatewayUsage

_LEDGER_ID = "ledger:independent-completion-consumer"
_REQUEST = "same bounded physical request"
_RUN = "independent-completion-run"
_CHILD = (
    "import runpy,sys; "
    "ns=runpy.run_path(sys.argv[1],run_name='completion_consumer_driver'); "
    "ns['_driver'](sys.argv[2:])"
)


def _budget() -> BudgetState:
    return BudgetState(limits={"run": BudgetLimit(key="run", max_usd=Decimal("10"))})


def _read_effects(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines()]


def _snapshot(path: Path) -> dict[str, Any]:
    return ledger_module.FileBudgetLedger(path).snapshot().model_dump(mode="json")


class _PhysicalProvider:
    def __init__(self, ledger: Path, effects: Path, *, cost: Decimal = Decimal("0.02")) -> None:
        self.ledger = ledger
        self.effects = effects
        self.cost = cost
        self.all_entered: asyncio.Event | None = None
        self.release: asyncio.Event | None = None

    def _effect(self, request: dict[str, Any]) -> GatewayLLMResponse:
        # Observe the ledger without adding a second provider admission gate.
        # An escaped call still creates its physical effect even when no intent
        # exists or the optional witness read fails.
        witness_error = None
        ledger_digest = None
        records: dict[str, Any] = {}
        try:
            records = _snapshot(self.ledger)["completion_obligations"]
            ledger_digest = hashlib.sha256(self.ledger.read_bytes()).hexdigest()
        except Exception as exc:
            witness_error = type(exc).__name__
        row = {
            "pid": os.getpid(),
            "request": request,
            "reported_cost": str(self.cost),
            "ledger_sha256_at_effect": ledger_digest,
            "admitted_records_at_effect": records,
            "optional_ledger_witness_error": witness_error,
        }
        payload = (json.dumps(row, sort_keys=True) + "\n").encode()
        fd = os.open(self.effects, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
        try:
            offset = 0
            while offset < len(payload):
                written = os.write(fd, payload[offset:])
                assert written > 0
                offset += written
            os.fsync(fd)
        finally:
            os.close(fd)
        return GatewayLLMResponse(
            content="one real local fixture effect",
            usage=GatewayUsage(
                prompt_tokens=1,
                completion_tokens=1,
                total_tokens=2,
                cost_usd=float(self.cost),
            ),
            request_id=f"local-physical:{os.getpid()}:{len(_read_effects(self.effects))}",
        )

    def invoke(self, prompt: str, **kwargs: Any) -> GatewayLLMResponse:
        return self._effect({"prompt": prompt, **kwargs})

    async def ainvoke(self, prompt: str, **kwargs: Any) -> GatewayLLMResponse:
        return await self.generate(prompt=prompt, **kwargs)

    async def generate(self, **kwargs: Any) -> GatewayLLMResponse:
        response = self._effect(kwargs)
        if self.release is not None:
            if len(_read_effects(self.effects)) == 2:
                assert self.all_entered is not None
                self.all_entered.set()
            await self.release.wait()
        return response


class _PublicationFault(AbstractContextManager["_PublicationFault"]):
    """Interrupt a named real staged snapshot at its publication syscall."""

    def __init__(self, path: Path, operation: str, syscall: str) -> None:
        self.path = path
        self.operation = operation
        self.syscall = syscall
        self.seen: list[dict[str, Any]] = []
        self._fsync = os.fsync
        self._replace = os.replace

    def _matches(self, payload: bytes) -> bool:
        try:
            wire = json.loads(payload)
        except (UnicodeError, ValueError):
            return False
        if not isinstance(wire, dict) or wire.get("ledger_id") != _LEDGER_ID:
            return False
        mutations = wire.get("recent_mutations", [])
        if not mutations or mutations[-1]["operation"] != self.operation:
            return False
        self.seen.append(wire)
        return True

    def _fail_fsync(self, fd: int) -> None:
        if self.syscall == "file_fsync" and stat.S_ISREG(os.fstat(fd).st_mode):
            try:
                payload = os.pread(fd, os.fstat(fd).st_size, 0)
            except OSError:
                payload = b""
            if self._matches(payload):
                raise OSError("independent actual completion staged-file fsync fault")
        self._fsync(fd)

    def _fail_replace(self, source: Any, target: Any, **kwargs: Any) -> None:
        if (
            self.syscall == "replace_before"
            and Path(target) == self.path
            and self._matches(Path(source).read_bytes())
        ):
            raise OSError("independent actual completion replace-before-publication fault")
        self._replace(source, target, **kwargs)

    def __enter__(self) -> _PublicationFault:
        os.fsync = self._fail_fsync
        os.replace = self._fail_replace
        return self

    def __exit__(self, *_args: Any) -> None:
        os.fsync = self._fsync
        os.replace = self._replace


def _enforcer(provider: _PhysicalProvider, middleware: BudgetMiddleware) -> LLMBudgetEnforcer:
    return LLMBudgetEnforcer(
        client=TracedLLMClient(provider, model_name="local-physical-fixture"),
        budget_state=middleware.budget_state,
        budget_keys=["run"],
        model_name="local-physical-fixture",
        run_id=_RUN,
        budget_middleware=middleware,
    )


def _call(enforcer: LLMBudgetEnforcer, mode: str) -> Any:
    kwargs = {"max_tokens": 1, "_prompt_tokens_estimate": 1}
    if mode == "invoke":
        return enforcer.invoke(_REQUEST, **kwargs)
    return asyncio.run(enforcer.generate(user=_REQUEST, **kwargs))


def _attempt(operation: Callable[[], Any]) -> dict[str, Any]:
    try:
        operation()
    except LLMAccountingError as exc:
        return {
            "status": "refused",
            "exception": type(exc).__name__,
            "cause": type(exc.cause).__name__,
            "cause_text": str(exc.cause),
        }
    return {"status": "accepted"}


async def _concurrent_calls(enforcer: LLMBudgetEnforcer, provider: _PhysicalProvider) -> None:
    provider.all_entered = asyncio.Event()
    provider.release = asyncio.Event()
    tasks = [
        asyncio.create_task(
            enforcer.generate(user=_REQUEST, max_tokens=1, _prompt_tokens_estimate=1)
        )
        for _ in range(2)
    ]
    try:
        await asyncio.wait_for(provider.all_entered.wait(), timeout=20)
        assert len(_read_effects(provider.effects)) == 2
        assert len(_snapshot(provider.ledger)["completion_obligations"]) == 2
    finally:
        provider.release.set()
        await asyncio.gather(*tasks)


def _driver(args: list[str]) -> None:
    path, effects = Path(args[0]), Path(args[1])
    action, mode, syscall, source_root = args[2:6]
    assert Path(ledger_module.__file__).resolve().is_relative_to(Path(source_root))
    middleware = BudgetMiddleware(
        _budget(), ledger=ledger_module.FileBudgetLedger(path, ledger_id=_LEDGER_ID)
    )
    provider = _PhysicalProvider(
        path, effects, cost=Decimal("0") if action == "zero" else Decimal("0.02")
    )
    enforcer = _enforcer(provider, middleware)
    before = path.read_bytes()
    out: dict[str, Any] = {"pid": os.getpid(), "owner_epoch": middleware.completion_owner_epoch}
    if action in {"intent_fault", "completion_fault"}:
        operation = "admit_provider_intent" if action == "intent_fault" else "transition_completion"
        with _PublicationFault(path, operation, syscall) as fault:
            out.update(_attempt(lambda: _call(enforcer, mode)))
        out["faulted_staged_snapshots"] = fault.seen
        if action == "completion_fault":
            original = path.read_bytes()
            # A new enforcer with this original initialized middleware shares
            # the live constructor owner; it is not a fresh epoch fence.
            sibling = _enforcer(_PhysicalProvider(path, effects), middleware)
            out["same_live_sibling"] = _attempt(lambda: _call(sibling, mode))
            out["same_live_sibling_kept_ledger"] = path.read_bytes() == original
    elif action == "concurrent":
        asyncio.run(_concurrent_calls(enforcer, provider))
        out["status"] = "accepted"
    else:
        out.update(_attempt(lambda: _call(enforcer, mode)))
    out.update(
        ledger_unchanged=path.read_bytes() == before,
        snapshot=_snapshot(path),
        physical_effects=_read_effects(effects),
        ledger_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
    )
    print(json.dumps(out, sort_keys=True), flush=True)  # noqa: T201 - child result protocol


def _child(path: Path, effects: Path, action: str, mode: str, syscall: str = "") -> dict[str, Any]:
    source_root = Path(ledger_module.__file__).resolve().parents[4]
    command = [
        sys.executable,
        "-c",
        _CHILD,
        str(Path(__file__).resolve()),
        str(path),
        str(effects),
        action,
        mode,
        syscall,
        str(source_root),
    ]
    result = subprocess.run(
        command,
        env={**os.environ, "PYTHONPATH": str(source_root), "POLISYOS_METRICS_PORT": "0"},
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(result.stdout.splitlines()[-1])


@pytest.mark.parametrize("mode", ["invoke", "generate"])
@pytest.mark.parametrize("syscall", ["file_fsync", "replace_before"])
def test_preprovider_atomic_intent_publication_fault_means_no_physical_call(
    tmp_path: Path, mode: str, syscall: str
) -> None:
    path, effects = tmp_path / "ledger.json", tmp_path / "physical-effects.jsonl"
    failed = _child(path, effects, "intent_fault", mode, syscall)
    assert failed["status"] == "refused", failed
    assert failed["physical_effects"] == []
    assert not effects.exists()
    assert failed["ledger_unchanged"] is True
    assert failed["snapshot"]["completion_obligations"] == {}
    assert failed["snapshot"]["state"]["spent"] == {}
    assert failed["snapshot"]["state"]["reserved"] == {}
    staged = failed["faulted_staged_snapshots"]
    assert len(staged) == 1
    assert len(staged[0]["completion_obligations"]) == 1
    assert next(iter(staged[0]["completion_obligations"].values()))["phase"] == "provider_in_flight"


@pytest.mark.parametrize("mode", ["invoke", "generate"])
@pytest.mark.parametrize("syscall", ["file_fsync", "replace_before"])
def test_posteffect_completion_publication_fault_blocks_live_and_fresh_consumers(
    tmp_path: Path, mode: str, syscall: str
) -> None:
    path, effects = tmp_path / "ledger.json", tmp_path / "physical-effects.jsonl"
    failed = _child(path, effects, "completion_fault", mode, syscall)
    assert failed["status"] == "refused", failed
    assert failed["same_live_sibling"]["status"] == "refused", failed
    assert failed["same_live_sibling_kept_ledger"] is True
    assert len(failed["physical_effects"]) == 1
    effect = failed["physical_effects"][0]
    assert effect["pid"] == failed["pid"]
    assert effect["optional_ledger_witness_error"] is None
    pending = failed["snapshot"]["completion_obligations"]
    assert len(pending) == 1
    assert pending == effect["admitted_records_at_effect"]
    record = next(iter(pending.values()))
    assert record["phase"] == "provider_in_flight"
    assert record["owner_epoch"] == failed["owner_epoch"]
    assert record["event_payload"]["kind"] == "provider_intent"
    assert record["event_payload"]["amount"] is None
    assert record["known_receipt_ids"] == []
    assert failed["snapshot"]["state"]["spent"] == {}
    assert failed["ledger_sha256"] == effect["ledger_sha256_at_effect"]
    before = effects.read_bytes()
    for _ in range(2):
        reopened = _child(path, effects, "reopen", mode)
        assert reopened["pid"] != failed["pid"]
        assert reopened["owner_epoch"] != failed["owner_epoch"]
        assert reopened["status"] == "refused", reopened
        assert reopened["snapshot"]["completion_obligations"] == pending
        assert reopened["ledger_unchanged"] is True
        assert effects.read_bytes() == before
        assert len(reopened["physical_effects"]) == 1


@pytest.mark.parametrize("mode", ["invoke", "generate"])
def test_genuine_known_zero_completion_allows_a_fresh_physical_call(
    tmp_path: Path, mode: str
) -> None:
    path, effects = tmp_path / "ledger.json", tmp_path / "physical-effects.jsonl"
    first = _child(path, effects, "zero", mode)
    second = _child(path, effects, "zero", mode)
    assert first["status"] == second["status"] == "accepted"
    assert first["pid"] != second["pid"]
    assert len(second["physical_effects"]) == 2
    assert all(effect["reported_cost"] == "0" for effect in second["physical_effects"])
    assert all(effect["admitted_records_at_effect"] for effect in second["physical_effects"])
    assert second["snapshot"]["completion_obligations"] == {}
    assert second["snapshot"]["state"]["spent"]["run"] == "0"
    receipts = second["snapshot"]["spend_receipts"]
    assert len(receipts) == 2
    assert all(receipt["amount"] == "0" for receipt in receipts.values())


def test_same_live_owner_can_finish_two_genuinely_concurrent_physical_calls(tmp_path: Path) -> None:
    path, effects = tmp_path / "ledger.json", tmp_path / "physical-effects.jsonl"
    observed = _child(path, effects, "concurrent", "generate")
    assert observed["status"] == "accepted"
    assert len(observed["physical_effects"]) == 2
    assert all(effect["admitted_records_at_effect"] for effect in observed["physical_effects"])
    assert observed["snapshot"]["completion_obligations"] == {}
    assert observed["snapshot"]["state"]["spent"]["run"] == "0.04"
    assert len(observed["snapshot"]["spend_receipts"]) == 2
