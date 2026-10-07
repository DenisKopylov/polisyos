"""Observe exact HTTP money through canonical settlement and a fresh D reader.

The D stopping reader is imported from its published immutable Git source,
without replacing the B ledger or creating a second monetary parser. This is
an external-source composition, not acceptance of an integrated D factory.
"""

from __future__ import annotations

import asyncio
import hashlib
import importlib.abc
import importlib.util
import json
import os
import subprocess
import sys
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from aiohttp import web

from polisyos.core.llm.response import extract_llm_response_data
from polisyos.core.llm.traced_client import LLMAccountingError
from polisyos.scientist.orchestration.engine.budget import BudgetLimit, BudgetState
from polisyos.scientist.orchestration.engine.budget_ledger import FileBudgetLedger
from polisyos.scientist.orchestration.engine.budget_middleware import BudgetMiddleware
from polisyos.scientist.orchestration.llm.budget_enforcer import LLMBudgetEnforcer
from polisyos.scientist.orchestration.llm.gateway_client import GatewayLLMClient

_D_SHA = "8f58d7349edefebbac7e7f21e6859f8daa075c1d"
_D_MODULES = (
    "polisyos.common.serialization",
    "polisyos.scientist.methods.search.objective",
    "polisyos.scientist.methods.search.stopping",
)
_CASES = (
    ("tiny-positive", "1e-1000", None),
    ("tiny-negative", "-1e-1000", None),
    ("missing", None, None),
    ("null", "null", None),
    ("integer-zero", "0", Decimal(0)),
    ("decimal-zero", "0.0", Decimal(0)),
    ("negative-integer-zero", "-0", Decimal(0)),
    ("negative-decimal-zero", "-0.0", Decimal(0)),
    ("ordinary-positive", "0.02", Decimal("0.02")),
    ("ordinary-negative", "-0.02", None),
    ("boolean-true", "true", None),
    ("boolean-false", "false", None),
    ("nan", "NaN", None),
    ("positive-infinity", "Infinity", None),
    ("negative-infinity", "-Infinity", None),
)


def _root() -> Path:
    return Path(__file__).resolve().parents[6]


def _source_root() -> Path:
    return Path(os.environ.get("E02_MONEY_SOURCE_ROOT", str(_root()))).resolve()


def _git_bytes(root: Path, sha: str, path: str) -> bytes:
    return subprocess.check_output(["git", "-C", str(root), "show", f"{sha}:{path}"])


def _origins() -> list[dict[str, Any]]:
    root = _source_root()
    sha = os.environ.get("E02_MONEY_SOURCE_SHA")
    if sha:
        assert (
            subprocess.check_output(
                ["git", "-C", str(root), "rev-parse", "HEAD"], text=True
            ).strip()
            == sha
        )
    rows = []
    for name, module in sorted(sys.modules.items()):
        if not name.startswith("polisyos.") or not getattr(module, "__file__", None):
            continue
        path = Path(module.__file__).resolve()
        if not path.is_relative_to(root / "policy-engine/src"):
            continue
        data = path.read_bytes()
        if sha:
            assert data == _git_bytes(root, sha, str(path.relative_to(root))), path
        rows.append({"module": name, "path": str(path), "sha256": hashlib.sha256(data).hexdigest()})
    return rows


class _DGitLoader(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    """Run the three real published reader dependencies in a fresh process."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.rows: list[dict[str, Any]] = []

    def find_spec(self, fullname: str, path: Any = None, target: Any = None) -> Any:
        del path, target
        if fullname in _D_MODULES:
            return importlib.util.spec_from_loader(fullname, self)
        return None

    def create_module(self, spec: Any) -> None:
        del spec
        return None

    def exec_module(self, module: Any) -> None:
        relative = "policy-engine/src/" + module.__name__.replace(".", "/") + ".py"
        data = _git_bytes(self.root, _D_SHA, relative)
        module.__file__ = f"git-object:{_D_SHA}:{relative}"
        self.rows.append(
            {
                "module": module.__name__,
                "source_sha": _D_SHA,
                "path": relative,
                "bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            }
        )
        # S102: execute hash-recorded immutable canonical Git source, not input code.
        exec(compile(data, module.__file__, "exec"), module.__dict__)  # noqa: S102


def _fresh_reader(path: Path) -> dict[str, Any]:
    # Imports here occur after the loader is installed by the child entrypoint.
    from polisyos.scientist.methods.search.stopping import CostBudgetStopping

    before = path.read_bytes()
    ledger = FileBudgetLedger(path, ledger_id="ledger:raw-http-money")
    snapshot = ledger.snapshot()
    middleware = BudgetMiddleware(BudgetState(), ledger=ledger)
    error = None
    try:
        middleware.pre_check("fresh-D-action", "run")
    except Exception as exc:
        error = type(exc).__name__
    state = {} if error else {"cumulative_cost_usd": snapshot.state.spent.get("run", Decimal(0))}
    stopping = CostBudgetStopping(1).check([], state)
    assert path.read_bytes() == before
    return {
        "pid": os.getpid(),
        "snapshot": snapshot.model_dump(mode="json"),
        "admission_error": error,
        "should_stop": stopping.should_stop,
        "details": stopping.details,
        "reason": stopping.reason,
        "ledger_bytes_sha256": hashlib.sha256(before).hexdigest(),
    }


def _raw_response(lexeme: str | None) -> bytes:
    cost = "" if lexeme is None else '"cost_usd":' + lexeme
    return (
        '{"choices":[{"message":{"content":"actual HTTP answer",'
        '"tool_calls":[{"id":"tool-1","function":{"name":"observe",'
        '"arguments":"{\\"count\\":2,\\"ratio\\":0.125}"}}]}}],'
        '"usage":{' + cost + '},"model":"gpt-4o","provider":"local-http",'
        '"noncost":{"count":2,"ratio":0.125}}'
    ).encode()


async def _exercise(tmp_path: Path, lexeme: str | None) -> dict[str, Any]:
    origins_before = _origins()
    raw = _raw_response(lexeme)
    (tmp_path / "response.bin").write_bytes(raw)
    requests = []

    async def respond(request: web.Request) -> web.Response:
        request_body = await request.read()
        row = {
            "body": request_body.decode(),
            "idempotency_key": request.headers.get("x-idempotency-key"),
        }
        requests.append(row)
        with (tmp_path / "http-work.jsonl").open("a") as stream:
            stream.write(json.dumps(row) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        return web.Response(body=raw, content_type="application/json")

    app = web.Application()
    app.router.add_post("/chat/completions", respond)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    assert site._server is not None
    port = site._server.sockets[0].getsockname()[1]
    gateway = GatewayLLMClient(
        base_url=f"http://127.0.0.1:{port}", api_key="", model="gpt-4o", max_retries=0
    )
    ledger_path = tmp_path / "budget.json"
    ledger = FileBudgetLedger(ledger_path, ledger_id="ledger:raw-http-money")
    middleware = BudgetMiddleware(
        BudgetState(limits={"run": BudgetLimit(key="run", max_usd=Decimal(10))}), ledger=ledger
    )
    enforcer = LLMBudgetEnforcer(
        client=gateway,
        budget_state=middleware.budget_state,
        budget_keys=["run"],
        budget_middleware=middleware,
        model_name="gpt-4o",
        run_id="raw-http-money",
        metrics=SimpleNamespace(
            llm_cost_usd=None,
            llm_calls_total=None,
            llm_tokens_total=None,
            scientist_llm_budget_utilization=None,
            scientist_llm_cost_anomalies_total=None,
        ),
    )
    result: Any = None
    error = None
    try:
        result = await enforcer.generate(
            user="actual request", max_tokens=2, _prompt_tokens_estimate=1
        )
    except LLMAccountingError as exc:
        result, error = exc.response, exc
    finally:
        await gateway.aclose()
        await runner.cleanup()
    parsed = extract_llm_response_data(result)
    snapshot = ledger.snapshot()
    child_env = dict(os.environ)
    command = [sys.executable, str(Path(__file__).resolve()), "--fresh-reader", str(ledger_path)]
    child = await asyncio.to_thread(
        subprocess.run, command, env=child_env, capture_output=True, text=True, check=False
    )
    (tmp_path / "fresh-reader.stdout.txt").write_text(child.stdout)
    (tmp_path / "fresh-reader.stderr.txt").write_text(child.stderr)
    assert child.returncode == 0, child.stderr
    fresh = json.loads(
        next(
            line.removeprefix("EXACT_MONEY_READER ")
            for line in child.stdout.splitlines()
            if line.startswith("EXACT_MONEY_READER ")
        )
    )
    observation = {
        "raw": raw.decode(),
        "raw_sha256": hashlib.sha256(raw).hexdigest(),
        "lexeme": lexeme,
        "independent_decimal": str(Decimal(lexeme))
        if lexeme not in (None, "null", "true", "false")
        else None,
        "http_requests": requests,
        "port": port,
        "parent_pid": os.getpid(),
        "result_error": type(error).__name__ if error else None,
        "cost_status": parsed.cost_status,
        "usage_status": parsed.usage_status,
        "cost": str(parsed.cost_usd) if parsed.cost_usd is not None else None,
        "fresh": fresh,
        "snapshot": snapshot.model_dump(mode="json"),
        "child_command": command,
        "source_origins_before": origins_before,
        "source_origins_after": _origins(),
    }
    (tmp_path / "observations.json").write_text(
        json.dumps(observation, indent=2, default=str) + "\n"
    )
    print("EXACT_MONEY_ACTUAL " + json.dumps(observation, default=str))
    assert len(requests) == 1 and requests[0]["idempotency_key"]
    assert fresh["pid"] != os.getpid()
    assert fresh["snapshot"] == observation["snapshot"]
    # Real tool argument decoder compatibility is separate from monetary intake.
    assert result.tool_calls[0].arguments == {"count": 2, "ratio": 0.125}
    assert type(result.tool_calls[0].arguments["count"]) is int
    assert type(result.tool_calls[0].arguments["ratio"]) is float
    return observation


@pytest.mark.parametrize(("profile", "lexeme", "expected"), _CASES, ids=[row[0] for row in _CASES])
def test_http_money_does_not_become_zero_in_durable_reader(
    tmp_path: Path, profile: str, lexeme: str | None, expected: Decimal | None
) -> None:
    del profile
    observed = asyncio.run(_exercise(tmp_path, lexeme))
    state = observed["snapshot"]["state"]
    receipts = observed["snapshot"]["spend_receipts"]
    fresh = observed["fresh"]
    if expected is None:
        assert observed["result_error"] == "LLMAccountingError", observed
        assert not receipts and observed["snapshot"]["completion_obligations"], observed
        assert Decimal(state["reserved"]["run"]) > 0
        assert fresh["admission_error"] == "BudgetLedgerCompletionPendingError", fresh
        assert fresh["should_stop"] and not fresh["details"]["budget_available"], fresh
    else:
        assert observed["result_error"] is None, observed
        assert len(receipts) == 1 and not observed["snapshot"]["completion_obligations"], observed
        receipt = next(iter(receipts.values()))
        assert Decimal(receipt["amount"]) == expected
        assert Decimal(state["spent"]["run"]) == expected
        assert Decimal(state["reserved"]["run"]) == 0
        assert fresh["admission_error"] is None and not fresh["should_stop"]
        assert (
            fresh["details"]["budget_available"]
            and Decimal(str(fresh["details"]["cost"])) == expected
        )


if __name__ == "__main__":
    assert len(sys.argv) == 3 and sys.argv[1] == "--fresh-reader"
    # This module's parent-side imports already loaded B serialization. Removing
    # only these exact modules selects the external published D reader afresh.
    for _name in _D_MODULES:
        sys.modules.pop(_name, None)
    _loader = _DGitLoader(_source_root())
    sys.meta_path.insert(0, _loader)
    _observed = _fresh_reader(Path(sys.argv[2]))
    _observed["d_source"] = _loader.rows
    print("EXACT_MONEY_READER " + json.dumps(_observed, default=str))
