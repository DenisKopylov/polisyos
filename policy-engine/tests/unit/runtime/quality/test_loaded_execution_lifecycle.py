"""Source capture closes only after use and cannot be revived."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_PRODUCT = Path(__file__).resolve().parents[4]


def _run(tmp_path: Path, program: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-I", "-S", "-B", "-c", program, str(_PRODUCT), str(tmp_path)],
        capture_output=True,
        text=True,
        check=False,
        timeout=20,
    )


def test_close_releases_held_execution_and_keeps_process_terminal(tmp_path: Path) -> None:
    """The closed capture drops its live hold and cannot authorize later use."""
    program = r"""
import builtins, gc, hashlib, importlib, importlib.machinery, pathlib, sys, weakref
root = pathlib.Path(sys.argv[2]); sys.path.insert(0, sys.argv[1])
from tools.loaded_execution_capture import CaptureError, ExpectedSource, SourceExecutionCapture
source = b'value = 7\n'
(root / 'lifecycle_witness.py').write_bytes(source)
expected = {'lifecycle_witness': ExpectedSource('lifecycle_witness.py', hashlib.sha256(source).hexdigest())}
prior_import, prior_import_module = builtins.__import__, importlib.import_module
prior_pathfinder = vars(importlib.machinery.PathFinder)['find_spec']
capture = SourceExecutionCapture(root, expected, external_source_selector=lambda name, origin: None)
capture.install(); sys.path.insert(0, str(root))
module = importlib.import_module('lifecycle_witness')
assert module.value == 7
capture.assert_retained(frozenset({'lifecycle_witness'}))
held = weakref.ref(module)
sys.modules.pop('lifecycle_witness')
del module
gc.collect()
assert held() is not None
# REMOVE_CLOSE
capture.close()
gc.collect()
assert held() is None, 'live execution remains held'
assert capture.diagnostic().phase == 'closed'
assert capture.diagnostic().status == 'not_established'
assert builtins.__import__ is prior_import and importlib.import_module is prior_import_module
assert vars(importlib.machinery.PathFinder)['find_spec'] is prior_pathfinder
assert all(finder is not capture._finder for finder in sys.meta_path)
for operation in (lambda: capture.completed('lifecycle_witness'),
                  lambda: capture.assert_retained(frozenset({'lifecycle_witness'})),
                  capture.import_events):
    try: operation()
    except CaptureError: pass
    else: raise AssertionError('closed capture served evidence')
try: SourceExecutionCapture(root, expected).install()
except CaptureError as exc: assert str(exc) == 'capture_process_already_attempted'
else: raise AssertionError('closed process was recaptured')
"""
    for mode in ("normal", "remove_close"):
        case_root = tmp_path / mode
        case_root.mkdir()
        source = program.replace(
            "# REMOVE_CLOSE", "capture.close = lambda: None" if mode == "remove_close" else ""
        )
        result = _run(case_root, source)
        if mode == "remove_close":
            print(f"capture release removal exit: {result.returncode}")
            print(result.stderr, end="")
            assert result.returncode != 0
            assert "live execution remains held" in result.stderr
        else:
            assert result.returncode == 0, result.stderr


def test_close_refuses_an_in_progress_initializer(tmp_path: Path) -> None:
    """A module cannot end capture while its own initializer is active."""
    program = r"""
import hashlib, pathlib, sys
root = pathlib.Path(sys.argv[2]); sys.path.insert(0, sys.argv[1])
from tools.loaded_execution_capture import CaptureError, ExpectedSource, SourceExecutionCapture
source = b'''import sys
try:
    sys.__dict__['_polisyos_loaded_execution_owner_v1'].close()
except Exception as exc:
    close_result = str(exc)
'''
(root / 'pending_witness.py').write_bytes(source)
capture = SourceExecutionCapture(root, {'pending_witness': ExpectedSource('pending_witness.py', hashlib.sha256(source).hexdigest())})
capture.install(); sys.path.insert(0, str(root))
import pending_witness
assert pending_witness.close_result == 'capture_incomplete'
assert capture.diagnostic().phase == 'collecting'
capture.assert_retained(frozenset({'pending_witness'}))
capture.close()
assert capture.diagnostic().phase == 'closed'
"""
    result = _run(tmp_path, program)
    assert result.returncode == 0, result.stderr


def test_close_removes_finder_after_partial_installation(tmp_path: Path) -> None:
    """A failed startup still releases a finder inserted before the refusal."""
    program = r"""
import hashlib, importlib.machinery, pathlib, sys
root = pathlib.Path(sys.argv[2]); sys.path.insert(0, sys.argv[1])
from tools.loaded_execution_capture import CaptureError, ExpectedSource, SourceExecutionCapture
source = b'value = 1\n'; (root / 'witness.py').write_bytes(source)
capture = SourceExecutionCapture(root, {'witness': ExpectedSource('witness.py', hashlib.sha256(source).hexdigest())}, external_source_selector=lambda name, origin: None)
replacement = classmethod(lambda cls, fullname, path=None, target=None: None)
importlib.machinery.PathFinder.find_spec = replacement
try: capture.install()
except CaptureError as exc: assert str(exc) == 'capture_path_finder_changed'
else: raise AssertionError('changed path finder did not refuse installation')
assert capture.failed and any(finder is capture._finder for finder in sys.meta_path)
capture.close()
assert capture.failed and capture.failure_reason == 'capture_path_finder_changed'
assert all(finder is not capture._finder for finder in sys.meta_path), 'failed installation retained its finder'
assert vars(importlib.machinery.PathFinder)['find_spec'] is replacement
"""
    result = _run(tmp_path, program)
    assert result.returncode == 0, result.stderr


def test_close_does_not_invoke_or_overwrite_changed_pathfinder(tmp_path: Path) -> None:
    """A changed lookup is left alone and cannot turn a failed capture green."""
    program = r"""
import gc, hashlib, importlib, importlib.machinery, pathlib, sys, weakref
root = pathlib.Path(sys.argv[2]); sys.path.insert(0, sys.argv[1])
from tools.loaded_execution_capture import CaptureError, ExpectedSource, SourceExecutionCapture
source = b'value = 1\n'; (root / 'witness.py').write_bytes(source)
capture = SourceExecutionCapture(root, {'witness': ExpectedSource('witness.py', hashlib.sha256(source).hexdigest())}, external_source_selector=lambda name, origin: None)
capture.install(); sys.path.insert(0, str(root))
module = importlib.import_module('witness'); held = weakref.ref(module)
sys.modules.pop('witness'); del module
called = []
def forged(cls, *args):
    called.append(True)
    raise AssertionError('candidate finder called')
replacement = classmethod(forged)
type.__setattr__(importlib.machinery.PathFinder, 'find_spec', replacement)
try: capture.close()
except CaptureError as exc: assert str(exc) == 'capture_path_finder_changed'
else: raise AssertionError('changed path finder was accepted')
assert not called
assert vars(importlib.machinery.PathFinder)['find_spec'] is replacement
assert capture.failed and capture.failure_reason == 'capture_path_finder_changed'
gc.collect(); assert held() is None
try: capture.assert_retained(frozenset({'witness'}))
except CaptureError: pass
else: raise AssertionError('failed capture was restored')
"""
    result = _run(tmp_path, program)
    assert result.returncode == 0, result.stderr


def test_close_refuses_changed_source_owned_finder_after_target(tmp_path: Path) -> None:
    """The final endpoint check detects a finder changed after its last use."""
    program = r"""
import hashlib, pathlib, sys
root = pathlib.Path(sys.argv[2]); sys.path.insert(0, sys.argv[1])
from tools.loaded_execution_capture import CaptureError, ExpectedSource, SourceExecutionCapture
source = b'''import sys
class Finder:
    def find_spec(self, fullname, path=None, target=None): return None
    def substitute(self, fullname, path=None, target=None): return None
finder = Finder()
sys.meta_path.append(finder)
'''
(root / 'source_finder.py').write_bytes(source)
capture = SourceExecutionCapture(root, {'source_finder': ExpectedSource('source_finder.py', hashlib.sha256(source).hexdigest())})
capture.install(); sys.path.insert(0, str(root))
import source_finder
capture.assert_retained(frozenset({'source_finder'}))
original = source_finder.Finder.find_spec.__code__
source_finder.Finder.find_spec.__code__ = source_finder.Finder.substitute.__code__
try: capture.close()
except CaptureError as exc: assert str(exc) == 'capture_finder_state_changed'
else: raise AssertionError('changed source finder was accepted during close')
finally: source_finder.Finder.find_spec.__code__ = original
assert capture.failed and capture.failure_reason == 'capture_finder_state_changed'
try: capture.close()
except CaptureError as exc: assert str(exc) == 'capture_not_collecting'
else: raise AssertionError('closed failure was revived')
"""
    result = _run(tmp_path, program)
    assert result.returncode == 0, result.stderr
