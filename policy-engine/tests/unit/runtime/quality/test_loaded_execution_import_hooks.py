"""Source-execution capture must mediate import-hook transitions."""

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


def test_source_owned_finder_keeps_selected_source_under_recorder(tmp_path: Path) -> None:
    """A finder constructed by recorded code cannot preempt selected sources."""
    program = r"""
import hashlib
import pathlib
import sys
sys.path.insert(0, sys.argv[1])
from tools.loaded_execution_capture import CaptureError, ExpectedSource, SourceExecutionCapture
root = pathlib.Path(sys.argv[2])
package = root / 'owned_finder'
package.mkdir()
files = {
    'owned_finder': ('owned_finder/__init__.py', b'''import importlib.abc
import sys
class Finder(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        return None
finder = Finder()
sys.meta_path.insert(0, finder)
from . import child
'''),
    'owned_finder.child': ('owned_finder/child.py', b'value = 7\n'),
}
for relative, source in files.values():
    (root / relative).write_bytes(source)
capture = SourceExecutionCapture(root, {
    name: ExpectedSource(relative, hashlib.sha256(source).hexdigest())
    for name, (relative, source) in files.items()
})
capture.install()
sys.path.insert(0, str(root))
import owned_finder
assert owned_finder.child.value == 7
assert sys.meta_path[0] is capture._finder
capture.assert_retained(frozenset({'owned_finder', 'owned_finder.child'}))
original = owned_finder.Finder.find_spec
owned_finder.Finder.find_spec = lambda self, fullname, path=None, target=None: None
try:
    capture.assert_retained(frozenset({'owned_finder', 'owned_finder.child'}))
except CaptureError as exc:
    assert str(exc) == 'capture_finder_state_changed'
else:
    raise AssertionError('changed source-owned finder was accepted')
finally:
    owned_finder.Finder.find_spec = original
assert capture.failed
"""
    result = _run(tmp_path, program)
    assert result.returncode == 0, result.stderr


def test_unknown_finder_cannot_be_erased_by_restore_and_reimport(tmp_path: Path) -> None:
    """An unqualified finder cannot be retroactively replaced by a clean import."""
    program = r"""
import hashlib
import importlib.abc
import importlib.util
import pathlib
import sys
sys.path.insert(0, sys.argv[1])
from tools.loaded_execution_capture import CaptureError, ExpectedSource, SourceExecutionCapture
root = pathlib.Path(sys.argv[2])
package = root / 'guarded_finder'
package.mkdir()
source = b'value = 7\n'
(package / '__init__.py').write_bytes(source)
capture = SourceExecutionCapture(root, {
    'guarded_finder': ExpectedSource('guarded_finder/__init__.py', hashlib.sha256(source).hexdigest())
})
capture.install()
sys.path.insert(0, str(root))
class Loader(importlib.abc.Loader):
    def create_module(self, spec):
        return None
    def exec_module(self, module):
        module.value = 99
class Finder(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == 'guarded_finder':
            return importlib.util.spec_from_loader(fullname, Loader())
        return None
finder = Finder()
sys.meta_path.insert(0, finder)
import guarded_finder
sys.meta_path.remove(finder)
del sys.modules['guarded_finder']
import guarded_finder
assert guarded_finder.value == 7
try:
    capture.assert_retained(frozenset({'guarded_finder'}))
except CaptureError:
    pass
else:
    raise AssertionError('restored meta path erased the unqualified finder')
assert capture.failed
"""
    normal_root = tmp_path / "normal"
    normal_root.mkdir()
    result = _run(normal_root, program)
    assert result.returncode == 0, result.stderr
    removal_root = tmp_path / "removal"
    removal_root.mkdir()
    removal = _run(
        removal_root,
        program.replace(
            "capture.install()",
            "capture.install()\ncapture._refresh_meta_path = lambda: None",
            1,
        ),
    )
    print(f"finder mediation removal exit: {removal.returncode}")
    print(removal.stdout, end="")
    print(removal.stderr, end="")
    assert removal.returncode != 0
    assert "restored meta path erased the unqualified finder" in removal.stderr
