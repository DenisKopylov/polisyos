"""The early tooling launcher preserves source and candidate boundaries."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_PRODUCT = Path(__file__).resolve().parents[3]


def test_source_candidates_follow_relative_imports_and_module_aliases() -> None:
    from tools.authority_bootstrap import _source_export_candidates

    candidates = _source_export_candidates(
        "example.consumer",
        "src/example/consumer.py",
        b"from .provider import Item as Alias\nimport example.other as other\nother.answer()\n",
    )
    assert "Item" in candidates["example.provider"]
    assert "answer" in candidates["example.other"]


def test_retained_recorder_surface_refuses_a_substituted_method() -> None:
    """Only descriptors from the exact compiled recorder are retained."""
    program = r"""
import pathlib
import sys
import types
root = pathlib.Path(sys.argv[1])
sys.path.insert(0, str(root))
from tools import authority_bootstrap as host
path = root / 'tools/loaded_execution_capture.py'
module = types.ModuleType('_test_retained_recorder')
module.__file__ = str(path)
sys.modules[module.__name__] = module
code = compile(path.read_bytes(), str(path), 'exec', dont_inherit=True)
exec(code, module.__dict__)
recorder_type, descriptors, globals_, functions, classes = host._retained_recorder_surface(module, code)
assert recorder_type is module.SourceExecutionCapture
assert any(name == 'diagnostic' for name, value in descriptors)
assert any(name == '_passive_lookup' for name, value in globals_)
assert any(row[0] is module._passive_lookup for row in functions)
assert any(row[0] is module.SourceCaptureDiagnostic for row in classes)
called = []
def forged(self):
    called.append(True)
module.SourceExecutionCapture.diagnostic = forged
try:
    host._retained_recorder_surface(module, code)
except RuntimeError as exc:
    assert str(exc) == 'recorder_descriptor_not_source_owned'
else:
    raise AssertionError('substituted recorder method was retained')
assert called == []
"""
    result = subprocess.run(
        [sys.executable, "-I", "-S", "-B", "-c", program, str(_PRODUCT)],
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr


def test_host_handoff_refuses_changed_recorder_before_calling_it() -> None:
    """The host checks retained recorder state before the first recorder call."""
    program = r"""
import os
import pathlib
import sys
import types
root = pathlib.Path(sys.argv[1])
sys.path.insert(0, str(root))
from tools import authority_bootstrap as host
path = root / 'tools/loaded_execution_capture.py'
code = compile(path.read_bytes(), str(path), 'exec', dont_inherit=True)
owner = types.ModuleType('polisyos.runtime.quality.confidence_ledger')
sys.modules[owner.__name__] = owner
for variant in ('instance', 'method_code', 'helper_code', 'class_method'):
    recorder = types.ModuleType('_recorder_' + variant)
    recorder.__file__ = str(path)
    sys.modules[recorder.__name__] = recorder
    exec(code, recorder.__dict__)
    capture = object.__new__(recorder.SourceExecutionCapture)
    surface = host._retained_recorder_surface(recorder, code)
    session = {'phase': 'collecting', 'pid': os.getpid(), 'parent_pid': os.getppid(),
               'recorder': recorder, 'recorder_code': code, 'recorder_surface': surface,
               'capture': capture, 'last_owner_diagnostic': None}
    host._HOST_SESSION = session
    sys.__dict__[host._HOST_SLOT] = session
    assert host._recorder_surface_unchanged(session)
    called = []
    if variant == 'instance':
        capture.__dict__['completed_binding'] = lambda *args: called.append(True)
    elif variant == 'method_code':
        recorder.SourceExecutionCapture.completed.__code__ = recorder.SourceExecutionCapture._fail.__code__
    elif variant == 'helper_code':
        def forged(mapping, key):
            raise AssertionError('helper executed')
        recorder._passive_lookup.__code__ = forged.__code__
    else:
        def forged_init(self, *args, **kwargs):
            raise AssertionError('class constructor executed')
        recorder.SourceCaptureDiagnostic.__init__ = forged_init
    host.handoff_if_ready()
    assert session['phase'] == 'failed', variant
    assert session['last_owner_diagnostic']['failure'] == 'host_recorder_surface_changed', variant
    assert called == [], variant
class FakeCapture:
    @property
    def __dict__(self):
        raise AssertionError('candidate descriptor executed')
fake_session = {'recorder': recorder, 'recorder_code': code, 'recorder_surface': (FakeCapture, (), (), (), ()), 'capture': FakeCapture()}
assert not host._recorder_surface_unchanged(fake_session)
"""
    result = subprocess.run(
        [sys.executable, "-I", "-S", "-B", "-c", program, str(_PRODUCT)],
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr


def test_host_accepts_installed_recorder_through_normal_diagnostic() -> None:
    """A normal diagnostic leaves the installed recorder's bindings intact."""
    program = r"""
import hashlib
import pathlib
import sys
import types
root = pathlib.Path(sys.argv[1])
sys.path.insert(0, str(root))
from tools import authority_bootstrap as host
path = root / 'tools/loaded_execution_capture.py'
recorder = types.ModuleType('_installed_recorder')
recorder.__file__ = str(path)
sys.modules[recorder.__name__] = recorder
code = compile(path.read_bytes(), str(path), 'exec', dont_inherit=True)
exec(code, recorder.__dict__)
source = root / 'src/polisyos/__init__.py'
expected = recorder.ExpectedSource('src/polisyos/__init__.py', hashlib.sha256(source.read_bytes()).hexdigest())
capture = recorder.SourceExecutionCapture(root, {'polisyos': expected})
capture.install()
surface = host._retained_recorder_surface(recorder, code)
session = {'recorder': recorder, 'recorder_code': code, 'recorder_surface': surface, 'capture': capture}
assert host._recorder_surface_unchanged(session)
assert capture.diagnostic().status == 'not_established'
assert host._recorder_surface_unchanged(session)
"""
    result = subprocess.run(
        [sys.executable, "-I", "-S", "-B", "-c", program, str(_PRODUCT)],
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr


def test_isolated_candidate_fallback_finds_checkout_sources(tmp_path: Path) -> None:
    """A refused source snapshot still permits candidate CLI imports."""
    tools = tmp_path / "tools"
    runner = tools / "ops_runners"
    package = tmp_path / "src/polisyos"
    runner.mkdir(parents=True)
    package.mkdir(parents=True)
    (tools / "__init__.py").write_text("", encoding="utf-8")
    (runner / "__init__.py").write_text("", encoding="utf-8")
    (package / "__init__.py").write_text("value = 'candidate'\n", encoding="utf-8")
    (runner / "runtime_cli.py").write_text(
        "from polisyos import value\ndef main(argv):\n    print(value, *argv)\n    return 0\n",
        encoding="utf-8",
    )
    script = """
import pathlib
import sys
product = sys.argv[1]
sys.path.insert(0, product)
from tools import authority_bootstrap as host
host._PRODUCT = pathlib.Path(sys.argv[2])
sys.path.remove(product)
sys.modules.pop('tools.authority_bootstrap', None)
sys.modules.pop('tools', None)
if sys.argv[3] == 'without_paths':
    host.Path.is_dir = lambda self: False
raise SystemExit(host.runtime_main(['ok']))
"""

    def run(mode: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-I", "-S", "-B", "-c", script, str(_PRODUCT), str(tmp_path), mode],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )

    result = run("normal")
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "candidate ok"
    removal = run("without_paths")
    print(f"fallback removal exit: {removal.returncode}")
    print(removal.stdout, end="")
    print(removal.stderr, end="")
    assert removal.returncode != 0
    assert "No module named 'tools'" in removal.stderr


def test_candidate_test_and_diagnose_modes_are_available_without_a_source_snapshot(
    tmp_path: Path,
) -> None:
    """Both advertised modes retain candidate behavior when source selection fails."""
    script = """
import pathlib
import sys
product = sys.argv[1]
root = pathlib.Path(sys.argv[2])
mode = sys.argv[3]
control = sys.argv[4]
sys.path.insert(0, product)
from tools import authority_bootstrap as host
host._PRODUCT = root
host._REPOSITORY = root
sys.path.remove(product)
if control == 'legacy_dispatch':
    original = host._invoke_entry
    def incomplete_dispatch(mode, args, **kwargs):
        if mode not in host._ENTRY_TARGETS:
            raise RuntimeError('host_target_unsupported')
        return original(mode, args, **kwargs)
    host._invoke_entry = incomplete_dispatch
elif control == 'borrowed_session':
    host._HOST_SESSION = {'profile': {'authority': True},
                          'last_owner_diagnostic': {'status': 'established'}}
if mode == 'test':
    args = ['-o', 'addopts=', '-p', 'no:cacheprovider', '-q',
            '--basetemp=' + str(root / 'nested-pytest'), str(root / 'test_candidate_smoke.py')]
else:
    args = []
raise SystemExit(host._launch(mode, args))
"""

    def run(root: Path, mode: str, control: str = "normal") -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                "-I",
                "-S",
                "-B",
                "-c",
                script,
                str(_PRODUCT),
                str(root),
                mode,
                control,
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=120,
        )

    for case in ("missing_checkout", "snapshot_error"):
        root = tmp_path / case
        root.mkdir()
        (root / "test_candidate_smoke.py").write_text(
            "def test_candidate():\n    assert True\n", encoding="utf-8"
        )
        if case == "snapshot_error":
            (root / "src/polisyos").mkdir(parents=True)
            (root / ".venv/bin").mkdir(parents=True)
            (root / ".venv/bin/python").write_text("", encoding="utf-8")
            (root / "uv.lock").write_text("", encoding="utf-8")
        test_run = run(root, "test")
        assert test_run.returncode == 0, test_run.stdout + test_run.stderr
        assert "1 passed" in test_run.stdout
        diagnostic = run(root, "diagnose")
        assert diagnostic.returncode == 0, diagnostic.stderr
        report = json.loads(diagnostic.stdout)
        assert report["profile"]["authority"] is False
        assert report["owner"]["status"] == "not_established"
        assert report["owner"]["failure"] == (
            "source_checkout_unavailable"
            if case == "missing_checkout"
            else "source_snapshot_unavailable"
        )

    removal = run(tmp_path / "missing_checkout", "diagnose", "legacy_dispatch")
    print(f"candidate dispatcher removal exit: {removal.returncode}")
    print(removal.stdout, end="")
    print(removal.stderr, end="")
    assert removal.returncode != 0
    assert "host_target_unsupported" in removal.stderr
    borrowed = run(tmp_path / "snapshot_error", "diagnose", "borrowed_session")
    assert borrowed.returncode == 0, borrowed.stderr
    borrowed_report = json.loads(borrowed.stdout)
    assert borrowed_report["profile"]["authority"] is False
    assert borrowed_report["owner"]["status"] == "not_established"
    assert borrowed_report["owner"]["failure"] == "source_snapshot_unavailable"
