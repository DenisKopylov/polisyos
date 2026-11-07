"""Tool dispatch offers a late diagnostic handoff without minting authority."""

from __future__ import annotations

import hashlib
import os
import subprocess
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


@pytest.mark.parametrize("control", ["normal", "missing_export", "substituted"])
def test_completed_owner_callback_is_source_bound_and_never_promotes_identity(
    tmp_path: Path, control: str
) -> None:
    """Handoff waits for owner completion and retains only a non-authoritative report."""
    product = Path(__file__).resolve().parents[3]
    program = r"""
import hashlib, importlib, pathlib, sys, types
product = pathlib.Path(sys.argv[1])
root = pathlib.Path(sys.argv[2])
control = sys.argv[3]
sys.path.insert(0, str(product))
from tools import authority_bootstrap as host_source
host_path = product / 'tools/authority_bootstrap.py'
host_bytes = host_path.read_bytes()
host_code = compile(host_bytes, str(host_path), 'exec', dont_inherit=True)
host = types.ModuleType('_polisyos_early_host')
host.__file__ = str(host_path)
host._HOST_EXECUTION_CODE = host_code
exec(host_code, host.__dict__)
recorder_path = product / 'tools/loaded_execution_capture.py'
recorder_bytes = recorder_path.read_bytes()
recorder_code = compile(recorder_bytes, str(recorder_path), 'exec', dont_inherit=True)
recorder = types.ModuleType('_polisyos_loaded_source_capture')
recorder.__file__ = str(recorder_path)
sys.modules[recorder.__name__] = recorder
exec(recorder_code, recorder.__dict__)
files = {
    'polisyos': ('src/polisyos/__init__.py', b''),
    'polisyos.runtime': ('src/polisyos/runtime/__init__.py', b''),
    'polisyos.runtime.quality': ('src/polisyos/runtime/quality/__init__.py', b''),
    'polisyos.runtime.quality.confidence_ledger': (
        'src/polisyos/runtime/quality/confidence_ledger.py',
        b'''import _polisyos_early_host as early_host
callback_count = 0
endpoint_count = 0
early_host.handoff_if_ready()
def _seal_loaded_execution_capture(recorder_module, capture):
    global callback_count
    callback_count += 1
    return {'status': 'not_established',
            'protected_loaded_execution_status': 'not_established',
            'owner_observation_state': 'retained',
            'owner_observation_scope': 'test source-bound handoff only',
            'currentness_status': 'not_established',
            'candidate_only': True}
def _check_loaded_execution_observation_currentness(capture):
    global endpoint_count
    endpoint_count += 1
    return {'status': 'not_established',
            'protected_loaded_execution_status': 'not_established',
            'owner_observation_state': 'retained',
            'held_binding_endpoint_currentness': 'not_established',
            'protected_through_use': 'not_established',
            'currentness_status': 'not_established',
            'candidate_only': True}
''',
    ),
}
sources = {}
for name, (relative, source) in files.items():
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(source)
    sources[name] = recorder.ExpectedSource(relative, hashlib.sha256(source).hexdigest())
owner_exports = set(host._OWNER_CAPTURE_EXPORTS)
if control == 'missing_export':
    owner_exports.remove('_seal_loaded_execution_capture')
exports = {'polisyos.runtime.quality.confidence_ledger': owner_exports}
capture = recorder.SourceExecutionCapture(root, sources, exports=exports)
capture.install()
surface = host._retained_recorder_surface(recorder, recorder_code)
session = {
    'pid': __import__('os').getpid(),
    'parent_pid': __import__('os').getppid(),
    'recorder': recorder,
    'recorder_code': recorder_code,
    'recorder_surface': surface,
    'capture': capture,
    'host_code': host_code,
    'host_sha256': hashlib.sha256(host_bytes).hexdigest(),
    'recorder_sha256': hashlib.sha256(recorder_bytes).hexdigest(),
    'phase': 'collecting',
    'handoff': host.handoff_if_ready,
}
host._HOST_SESSION = session
sys.modules[host._HOST_MODULE] = host
sys.__dict__[host._HOST_SLOT] = session
sys.path.insert(0, str(root / 'src'))
# The source initializer offers the host while its module is still provisional.
host.handoff_if_ready()
assert session['phase'] == 'collecting'
assert 'owner_capture_attempted' not in session
owner = importlib.import_module('polisyos.runtime.quality.confidence_ledger')
assert session['phase'] == 'collecting'
assert 'owner_capture_attempted' not in session
if control == 'substituted':
    owner._seal_loaded_execution_capture = lambda *args: {'status': 'established'}
host.handoff_if_ready()
if control == 'normal':
    assert owner.callback_count == 1
    assert session['owner_capture_state'] == 'retained'
    report = session['last_owner_diagnostic']
    assert report['status'] == report['protected_loaded_execution_status'] == 'not_established'
    assert report['candidate_only'] is True
    host.handoff_if_ready()
    assert owner.callback_count == 1
    host._check_owner_capture_at_endpoint(session, 'diagnose_before_output')
    assert owner.endpoint_count == 1
    assert session['last_owner_diagnostic']['currentness_status'] == 'not_established'
    assert session['last_owner_diagnostic']['protected_through_use'] == 'not_established'
    host._close_host_capture(session)
    assert session['phase'] == 'closed'
    assert session['owner_capture_state'] == 'retained'
elif control == 'missing_export':
    assert session['phase'] == 'failed'
    assert session['owner_capture_state'] == 'failed'
    assert owner.callback_count == 0
    host._close_host_capture(session)
    assert session['phase'] == 'failed'
else:
    assert session['phase'] == 'failed'
    assert session['owner_capture_state'] == 'failed'
    assert owner.callback_count == 0
    host._close_host_capture(session)
    assert session['phase'] == 'failed'
assert capture.diagnostic().status == 'not_established'
"""
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-S",
            "-B",
            "-c",
            program,
            str(product),
            str(tmp_path / control),
            control,
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr


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
