"""Tool dispatch offers a late diagnostic handoff without minting authority."""

from __future__ import annotations

import hashlib
import os
import sys
import types
from pathlib import Path

import pytest

from tools.lib import preflight, runner


def test_counterfeit_host_callback_is_not_invoked(monkeypatch: pytest.MonkeyPatch) -> None:
    """Coherently forged process slots cannot make the runner call candidate code."""
    fake = types.ModuleType("_polisyos_early_host")
    invoked: list[str] = []
    fake.invoked = invoked
    fake_code = compile("def handoff_if_ready():\n    invoked.append('called')\n", "fake", "exec")
    exec(fake_code, fake.__dict__)  # noqa: S102 - construct a counterfeit host for this negative test
    host_path = Path(runner.__file__).resolve().parents[1] / "authority_bootstrap.py"
    source = host_path.read_bytes()
    selected_code = compile(source, str(host_path), "exec", dont_inherit=True)
    fake._HOST_EXECUTION_CODE = selected_code
    session = {
        "pid": os.getpid(),
        "parent_pid": os.getppid(),
        "phase": "collecting",
        "handoff": fake.handoff_if_ready,
        "host_code": selected_code,
        "host_sha256": hashlib.sha256(source).hexdigest(),
    }
    fake._HOST_SESSION = session
    monkeypatch.setitem(sys.modules, fake.__name__, fake)
    monkeypatch.setitem(sys.__dict__, "_polisyos_loaded_host_v1", session)
    monkeypatch.setattr(runner, "_HOST_HANDOFF", fake.handoff_if_ready)
    monkeypatch.setattr(runner, "_HOST_HANDOFF_ANCHOR", fake.handoff_if_ready)
    monkeypatch.setattr(runner, "_HOST_HANDOFF_GLOBALS", fake.__dict__)
    monkeypatch.setattr(
        runner.subprocess, "run", lambda *args, **kwargs: types.SimpleNamespace(stdout=source)
    )
    runner._offer_host_handoff()
    assert invoked == []


@pytest.mark.parametrize("helper_change", ["none", "code", "callable"])
def test_actual_host_code_receives_handoff_in_a_candidate_session(
    monkeypatch: pytest.MonkeyPatch, helper_change: str
) -> None:
    """The actual host code receives the offer and rejects an incomplete capture."""
    host_path = Path(runner.__file__).resolve().parents[1] / "authority_bootstrap.py"
    source = host_path.read_bytes()
    code = compile(source, str(host_path), "exec", dont_inherit=True)
    host = types.ModuleType("_polisyos_early_host")
    host.__file__ = str(host_path)
    host._HOST_EXECUTION_CODE = code
    exec(code, host.__dict__)  # noqa: S102 - candidate-only host dispatch fixture
    session = {
        "pid": os.getpid(),
        "parent_pid": os.getppid(),
        "phase": "collecting",
        "handoff": host.handoff_if_ready,
        "host_code": code,
        "host_sha256": hashlib.sha256(source).hexdigest(),
        "capture": None,
    }
    host._HOST_SESSION = session
    monkeypatch.setitem(sys.modules, host.__name__, host)
    monkeypatch.setitem(sys.__dict__, "_polisyos_loaded_host_v1", session)
    monkeypatch.setattr(runner, "_HOST_HANDOFF", host.handoff_if_ready)
    monkeypatch.setattr(runner, "_HOST_HANDOFF_ANCHOR", host.handoff_if_ready)
    monkeypatch.setattr(runner, "_HOST_HANDOFF_GLOBALS", host.__dict__)
    monkeypatch.setattr(
        runner.subprocess, "run", lambda *args, **kwargs: types.SimpleNamespace(stdout=source)
    )
    invoked: list[str] = []
    if helper_change == "code":
        monkeypatch.setattr(
            host._recorder_surface_unchanged, "__code__", host.handoff_if_ready.__code__
        )
    elif helper_change == "callable":

        class Candidate:
            def __call__(self, value: object) -> bool:
                invoked.append("candidate")
                return False

        monkeypatch.setattr(host, "_recorder_surface_unchanged", Candidate())
    runner._offer_host_handoff()
    if helper_change != "none":
        assert session["phase"] == "collecting"
    else:
        assert session["phase"] == "failed"
        assert session["last_owner_diagnostic"]["failure"] == "host_recorder_surface_changed"
    assert invoked == []


def test_compiled_comparison_never_calls_candidate_constant_equality() -> None:
    """A forged code constant is rejected through passive builtin type checks."""

    class Candidate:
        def __eq__(self, other: object) -> bool:
            raise AssertionError("candidate equality ran")

    original = compile("value = 1\n", "fixture", "exec", dont_inherit=True)
    forged = original.replace(co_consts=(Candidate(),))
    assert not runner._same_compiled_value(forged, forged)


def test_preflight_offers_handoff_after_dotted_lookup(monkeypatch: pytest.MonkeyPatch) -> None:
    """A dotted lookup may import the owner before the selected tool loads."""
    events: list[str] = []

    def find_spec(name: str) -> object:
        events.append(f"find:{name}")
        return object()

    monkeypatch.setattr(preflight.importlib.util, "find_spec", find_spec)
    monkeypatch.setattr(preflight, "_offer_host_handoff", lambda: events.append("handoff"))
    spec = runner.ToolSpec(
        name="candidate",
        zone="test",
        category="test",
        module="target",
        required_imports=("x.y", "a.b"),
    )
    assert preflight.run_preflight(spec).ok
    assert events == ["find:x.y", "find:a.b", "handoff"]


def test_runner_offers_handoff_after_import_before_target(monkeypatch: pytest.MonkeyPatch) -> None:
    """The ordinary dispatcher offers a post-initializer handoff before use."""
    events: list[str] = []
    module = types.ModuleType("target")

    def main(argv: object) -> int:
        events.append("target")
        return 0

    module.main = main

    def import_module(name: str) -> types.ModuleType:
        events.append(f"import:{name}")
        return module

    monkeypatch.setattr(runner.importlib, "import_module", import_module)
    monkeypatch.setattr(runner, "_offer_host_handoff", lambda: events.append("handoff"))
    spec = runner.ToolSpec(name="candidate", zone="test", category="test", module="target")
    assert runner.invoke_tool_main(spec, []) == 0
    assert events == ["import:target", "handoff", "target"]
