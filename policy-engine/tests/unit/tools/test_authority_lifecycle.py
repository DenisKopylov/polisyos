"""The early host closes capture only after its target emits a result."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_PRODUCT = Path(__file__).resolve().parents[3]


def test_host_closes_after_target_and_preserves_failures() -> None:
    """Return, exception, and substituted-close paths remain distinct."""
    program = r"""
import base64, hashlib, importlib, os, pathlib, socket, sys, types
root = pathlib.Path(sys.argv[1]); mode = sys.argv[2]
path = root / 'tools/authority_bootstrap.py'
host = types.ModuleType('_test_early_host'); host.__file__ = str(path); sys.modules[host.__name__] = host
host_code = compile(path.read_bytes(), str(path), 'exec', dont_inherit=True)
exec(host_code, host.__dict__); host._HOST_EXECUTION_CODE = host_code
recorder_path = root / 'tools/loaded_execution_capture.py'; recorder_source = recorder_path.read_bytes()
tools_source = root / 'tools/__init__.py'
ledger_source = root / 'src/polisyos/runtime/quality/confidence_ledger.py'
sources = {
    'tools': ('tools/__init__.py', hashlib.sha256(tools_source.read_bytes()).hexdigest()),
    'polisyos.runtime.quality.confidence_ledger': ('src/polisyos/runtime/quality/confidence_ledger.py', hashlib.sha256(ledger_source.read_bytes()).hexdigest()),
}
request = {
    'parent_pid': os.getppid(), 'root': str(root), 'mode': 'tools', 'argv': [],
    'source_frame': {'lock_sha256': hashlib.sha256((root / 'uv.lock').read_bytes()).hexdigest()},
    'sources': sources, 'exports': {}, 'unparsed_sources': [],
    'host_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
    'recorder_path': str(recorder_path), 'recorder_source': base64.b64encode(recorder_source).decode(),
    'recorder_sha256': hashlib.sha256(recorder_source).hexdigest(),
    'parent_startup_isolated': True,
}
class Output:
    def __init__(self, stream): self.stream, self.written, self.flushed = stream, False, False
    def write(self, text):
        if 'target-result' in text: self.written = True
        return self.stream.write(text)
    def flush(self):
        if self.written: self.flushed = True
        return self.stream.flush()
output = Output(sys.stdout); sys.stdout = output
called = []
def target(target_mode, arguments):
    assert target_mode == 'tools' and arguments == []
    capture = host._HOST_SESSION['capture']
    importlib.import_module('tools')
    assert capture.completed('tools').module is sys.modules['tools']
    print('target-result')
    if mode in ('tamper', 'raise_tamper'):
        capture.close = lambda: called.append(True)
    if mode == 'skip_close':
        host._close_host_capture = lambda session: None
    if mode in ('raise', 'raise_tamper'):
        raise RuntimeError('target-failure')
    return 7
host._invoke_entry = target
left, right = socket.socketpair()
try:
    try: result = host._child_main(left, request)
    except RuntimeError as exc:
        assert str(exc) == ('host_recorder_surface_changed' if mode in ('tamper', 'raise_tamper') else 'target-failure')
        assert mode in ('tamper', 'raise', 'raise_tamper')
        if mode == 'raise_tamper':
            assert isinstance(exc.__context__, RuntimeError) and str(exc.__context__) == 'target-failure'
    else:
        assert mode in ('return', 'skip_close') and result == 7
    assert output.flushed
    session = host._HOST_SESSION; capture = session['capture']
    if mode in ('tamper', 'raise_tamper'):
        assert session['phase'] == 'failed' and not called
    else:
        assert session['phase'] == 'closed' and capture.diagnostic().phase == 'closed', 'host scope remained open'
        assert capture.diagnostic().status == 'not_established'
        try: capture.completed('tools')
        except ImportError: pass
        else: raise AssertionError('closed host retained usable authority evidence')
finally:
    left.close(); right.close(); sys.stdout = output.stream
"""
    for mode in ("return", "raise", "tamper", "raise_tamper", "skip_close"):
        result = subprocess.run(
            [sys.executable, "-I", "-S", "-B", "-c", program, str(_PRODUCT), mode],
            capture_output=True,
            text=True,
            check=False,
            timeout=20,
        )
        if mode == "skip_close":
            print(f"host close removal exit: {result.returncode}")
            print(result.stderr, end="")
            assert result.returncode != 0
            assert "host scope remained open" in result.stderr
        else:
            assert result.returncode == 0, f"{mode}: {result.stderr}"
