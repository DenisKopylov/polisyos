"""Behavioral controls for a non-authoritative source-execution producer.

These isolated synthetic modules exercise the producer, not owner admission or
N9. Every case runs in a fresh process because process-wide failures are sticky.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_PRODUCT_ROOT = Path(__file__).resolve().parents[4]


def _run_fresh(tmp_path: Path, program: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-I", "-S", "-B", "-c", program, str(_PRODUCT_ROOT), str(tmp_path)],
        text=True,
        capture_output=True,
        check=False,
        timeout=20,
    )


def _assert_case(tmp_path: Path, program: str) -> None:
    result = _run_fresh(tmp_path, program)
    assert result.returncode == 0, result.stderr


def test_selected_bytes_execute_without_replaced_get_code_and_spoofed_metadata(
    tmp_path: Path,
) -> None:
    _assert_case(
        tmp_path,
        r"""
import builtins
import hashlib
import importlib.machinery
import pathlib
import sys

sys.path.insert(0, sys.argv[1])
from tools.loaded_execution_capture import CaptureError, ExpectedSource, SourceExecutionCapture

root = pathlib.Path(sys.argv[2])
package = root / "capture_witness"
package.mkdir()
source = b"value = 'canonical'\n"
(package / "__init__.py").write_bytes(source)
expected = {"capture_witness": ExpectedSource("capture_witness/__init__.py", hashlib.sha256(source).hexdigest())}
capture = SourceExecutionCapture(root, expected)
initial = capture.diagnostic()
assert initial.phase == "new" and initial.status == "not_established"
assert initial.runtime_profile_id is None and initial.currentness_time_role == "not_evaluated"
assert initial.first_unestablished_premise == "appointed_profile" and initial.failed_premise is None
capture.install()
sys.path.insert(0, str(root))
original = importlib.machinery.SourceFileLoader.get_code

def poisoned(self, fullname):
    return compile("value = 'changed'\n", self.path, "exec")

importlib.machinery.SourceFileLoader.get_code = poisoned
try:
    import capture_witness
finally:
    importlib.machinery.SourceFileLoader.get_code = original
assert capture_witness.value == "canonical"
record = capture.completed("capture_witness")
assert record.module is capture_witness
assert record.source_sha256 == hashlib.sha256(source).hexdigest()
assert record.code.co_filename == str(package / "__init__.py")
observed = capture.diagnostic()
assert observed.phase == "collecting" and observed.status == "not_established"
assert observed.completed_module_count == 1 and observed.captured_source_projection_sha256.startswith("sha256:")
assert observed.provider_projection_sha256 is None
capture.assert_retained(frozenset({"capture_witness"}))

class MetadataSpoof:
    def __eq__(self, other):
        builtins.capture_comparator_called = True
        raise AssertionError("candidate comparator executed")
    def __ne__(self, other):
        builtins.capture_comparator_called = True
        raise AssertionError("candidate comparator executed")

builtins.capture_comparator_called = False
capture_witness.__spec__.origin = MetadataSpoof()
try:
    capture.assert_retained(frozenset({"capture_witness"}))
except CaptureError as exc:
    assert str(exc) == "retained_module_changed"
else:
    raise AssertionError("changed spec origin was accepted")
assert capture.failed and not builtins.capture_comparator_called
failed = capture.diagnostic()
assert failed.phase == "failed" and failed.failure_code == "retained_module_changed"
assert failed.failed_premise == "complete_relevant_bindings"
try:
    SourceExecutionCapture(root, expected).install()
except CaptureError as exc:
    assert str(exc) == "capture_process_already_attempted"
else:
    raise AssertionError("failed process was recaptured")
""",
    )


_BINDING_CASE = r"""
import builtins
import hashlib
import importlib
import pathlib
import sys

sys.path.insert(0, sys.argv[1])
from tools.loaded_execution_capture import CaptureError, ExpectedSource, SourceExecutionCapture

root = pathlib.Path(sys.argv[2])
package_name = "capture_bindings"
(root / package_name).mkdir()
provider_name = package_name + ".provider"
consumer_name = package_name + ".consumer"
unrelated_name = package_name + ".unrelated"
files = {
    package_name: (package_name + "/__init__.py", b""),
    provider_name: (package_name + "/provider.py", b"def answer():\n    return 1\n"),
    consumer_name: (package_name + "/consumer.py", b"from .provider import answer\nimport importlib\ncached = importlib.import_module(__package__ + '.provider')\n"),
    unrelated_name: (package_name + "/unrelated.py", b"marker = object()\n"),
}
for name, (relative, content) in files.items():
    (root / relative).write_bytes(content)
expected = {name: ExpectedSource(relative, hashlib.sha256(content).hexdigest())
            for name, (relative, content) in files.items()}
capture = SourceExecutionCapture(root, expected, exports={provider_name: {"answer"}, unrelated_name: {"marker"}})
capture.install()
sys.path.insert(0, str(root))
consumer = importlib.import_module(consumer_name)
provider = importlib.import_module(provider_name)
unrelated = importlib.import_module(unrelated_name)
unrelated.marker = object()
capture.assert_retained(frozenset({package_name, provider_name, consumer_name}))
capture.assert_binding(consumer_name, "answer", provider_name, "answer")
events = capture.import_events()
direct = [event for event in events if event.importer is consumer and event.provider is provider
          and event.route == "builtin_import" and event.requested_exports == ("answer",)]
cached = [event for event in events if event.importer is consumer and event.provider is provider
          and event.route == "import_module"]
assert len(direct) == 1 and direct[0].retained_exports["answer"] is provider.answer
assert direct[0].unresolved_exports == () and direct[0].caller_code.co_filename == str(root / files[consumer_name][0])
assert len(cached) == 1 and consumer.cached is provider
capture.assert_import_binding(direct[0], importer_attribute="answer", provider_export="answer")

class CollidingKey:
    def __hash__(self):
        return hash("answer")
    def __eq__(self, other):
        if builtins.capture_comparator_armed:
            builtins.capture_comparator_called = True
            raise AssertionError("candidate key comparator executed")
        return False

builtins.capture_comparator_armed = False
builtins.capture_comparator_called = False
collision = CollidingKey()
consumer.__dict__[collision] = object()
builtins.capture_comparator_armed = True
capture.assert_import_binding(direct[0], importer_attribute="answer", provider_export="answer")
assert not builtins.capture_comparator_called
builtins.capture_comparator_armed = False
del consumer.__dict__[collision]

def spoof():
    return 1

original_provider = provider.answer
original_consumer = consumer.answer
if CASE_MODE:
    provider.answer = spoof
consumer.answer = spoof
try:
    capture.assert_import_binding(direct[0], importer_attribute="answer", provider_export="answer")
except CaptureError as exc:
    expected_reason = "retained_export_changed" if CASE_MODE else "import_event_binding_changed"
    assert str(exc) == expected_reason
else:
    raise AssertionError("substituted provider/importer binding was accepted")
assert capture.failed
provider.answer = original_provider
consumer.answer = original_consumer
try:
    capture.assert_import_binding(direct[0], importer_attribute="answer", provider_export="answer")
except CaptureError as exc:
    assert str(exc) == "capture_incomplete"
else:
    raise AssertionError("restored binding revived a failed generation")
"""


def test_importer_only_substitution_is_refused(tmp_path: Path) -> None:
    _assert_case(tmp_path, _BINDING_CASE.replace("CASE_MODE", "False"))


def test_coherent_provider_and_importer_substitution_is_refused(tmp_path: Path) -> None:
    _assert_case(tmp_path, _BINDING_CASE.replace("CASE_MODE", "True"))


_EARLY_CASE = r"""
import hashlib
import pathlib
import sys
import types

sys.path.insert(0, sys.argv[1])
from tools.loaded_execution_capture import CaptureError, ExpectedSource, SourceExecutionCapture

root = pathlib.Path(sys.argv[2])
package = root / "capture_drift"
package.mkdir()
source = b"value = 1\n"
(package / "__init__.py").write_bytes(SOURCE_BYTES)
expected = {"capture_drift": ExpectedSource("capture_drift/__init__.py", hashlib.sha256(source).hexdigest())}
"""


def test_preloaded_module_refuses_and_cannot_retry_in_process(tmp_path: Path) -> None:
    _assert_case(
        tmp_path,
        _EARLY_CASE.replace("SOURCE_BYTES", "source")
        + r"""
sys.modules["capture_drift"] = types.ModuleType("capture_drift")
first = SourceExecutionCapture(root, expected)
try:
    first.install()
except CaptureError as exc:
    assert str(exc) == "selected_package_preloaded"
else:
    raise AssertionError("preloaded module was retroactively adopted")
del sys.modules["capture_drift"]
try:
    SourceExecutionCapture(root, expected).install()
except CaptureError as exc:
    assert str(exc) == "capture_process_already_attempted"
else:
    raise AssertionError("failed process was recaptured")
assert first.failed
""",
    )


def test_post_install_cached_module_refuses_and_candidate_can_continue(tmp_path: Path) -> None:
    _assert_case(
        tmp_path,
        _EARLY_CASE.replace("SOURCE_BYTES", "source")
        + r"""
capture = SourceExecutionCapture(root, expected)
capture.install()
try:
    capture.assert_retained(frozenset())
except CaptureError as exc:
    assert str(exc) == "capture_required_set_invalid"
else:
    raise AssertionError("empty selected set was accepted")
sys.modules["capture_drift"] = types.ModuleType("capture_drift")
try:
    capture.assert_retained(frozenset({"capture_drift"}))
except CaptureError as exc:
    assert str(exc) == "required_module_without_execution"
else:
    raise AssertionError("post-install cached module was accepted")
del sys.modules["capture_drift"]
sys.path.insert(0, str(root))
import capture_drift
assert capture_drift.value == 1 and capture.failed
try:
    SourceExecutionCapture(root, expected).install()
except CaptureError as exc:
    assert str(exc) == "capture_process_already_attempted"
else:
    raise AssertionError("failed process was recaptured")
""",
    )


_LOADER_REIMPORT_CASE = (
    _EARLY_CASE.replace("SOURCE_BYTES", "source")
    + r"""
import importlib.machinery
from tools import loaded_execution_capture as recorder
capture = SourceExecutionCapture(root, expected)
capture.install()
sys.path.insert(0, str(root))
original = recorder._CapturedSourceLoader.exec_module
recorder._CapturedSourceLoader.exec_module = importlib.machinery.SourceFileLoader.exec_module
try:
    import capture_drift
finally:
    recorder._CapturedSourceLoader.exec_module = original
assert capture_drift.value == 1
del sys.modules['capture_drift']
import capture_drift
assert capture_drift.value == 1
if capture.relevant_graph(frozenset({'capture_drift'})).failed_modules != (
    ('capture_drift', 'capture_loader_changed'),
):
    raise AssertionError('loader mutation evidence was lost')
try:
    capture.assert_retained(frozenset({'capture_drift'}))
except CaptureError as exc:
    assert str(exc) == 'required_module_initialization_failed'
else:
    raise AssertionError('an unrecorded initializer was accepted after loader restoration')
assert capture.failed
del sys.modules['capture_drift']
import capture_drift
assert capture_drift.value == 1
try:
    capture.assert_retained(frozenset({'capture_drift'}))
except CaptureError as exc:
    assert str(exc) == 'capture_incomplete'
else:
    raise AssertionError('restoration revived a failed capture')
"""
)


def test_replaced_loader_cannot_be_restored_into_a_valid_capture(tmp_path: Path) -> None:
    normal_root = tmp_path / "normal"
    normal_root.mkdir()
    _assert_case(normal_root, _LOADER_REIMPORT_CASE)

    removal_root = tmp_path / "removal"
    removal_root.mkdir()
    removal_program = _LOADER_REIMPORT_CASE.replace(
        "capture.install()",
        "recorder._captured_loader_intact = lambda: True\ncapture.install()",
        1,
    )
    removal = _run_fresh(removal_root, removal_program)
    print(f"loader anchor removal exit: {removal.returncode}")
    print(removal.stdout, end="")
    print(removal.stderr, end="")
    assert removal.returncode != 0
    assert "loader mutation evidence was lost" in removal.stderr


def test_removed_finder_is_a_terminal_failure(tmp_path: Path) -> None:
    _assert_case(
        tmp_path,
        _EARLY_CASE.replace("SOURCE_BYTES", "source")
        + r"""
capture = SourceExecutionCapture(root, expected)
capture.install()
sys.meta_path.remove(capture._finder)
try:
    capture.assert_retained(frozenset({"capture_drift"}))
except CaptureError as exc:
    assert str(exc) == "capture_finder_changed"
else:
    raise AssertionError("removed capture finder was accepted")
assert capture.failed
""",
    )


def test_replaced_import_hook_is_a_terminal_failure(tmp_path: Path) -> None:
    _assert_case(
        tmp_path,
        _EARLY_CASE.replace("SOURCE_BYTES", "source")
        + r"""
import builtins
original = builtins.__import__
capture = SourceExecutionCapture(root, expected)
capture.install()
builtins.__import__ = original
try:
    capture.assert_retained(frozenset({"capture_drift"}))
except CaptureError as exc:
    assert str(exc) == "capture_import_hook_changed"
else:
    raise AssertionError("replaced import hook was accepted")
assert capture.failed
""",
    )


def test_changed_source_refuses_exactly_and_candidate_can_continue(tmp_path: Path) -> None:
    _assert_case(
        tmp_path,
        _EARLY_CASE.replace("SOURCE_BYTES", "b'value = 2\\n'")
        + r"""
capture = SourceExecutionCapture(root, expected)
capture.install()
sys.path.insert(0, str(root))
import capture_drift
assert capture_drift.value == 2
assert not capture.failed
assert capture.relevant_graph(frozenset({"capture_drift"})).failed_modules == (("capture_drift", "selected_source_bytes_mismatch"),)
try:
    capture.assert_retained(frozenset({"capture_drift"}))
except CaptureError as exc:
    assert str(exc) == "required_module_initialization_failed"
else:
    raise AssertionError("failed source was admitted after unrecorded candidate import")
assert capture.failed
try:
    SourceExecutionCapture(root, expected).install()
except CaptureError as exc:
    assert str(exc) == "capture_process_already_attempted"
else:
    raise AssertionError("failed process was recaptured")
""",
    )


def test_initializer_metadata_refusal_does_not_invoke_comparator(tmp_path: Path) -> None:
    _assert_case(
        tmp_path,
        r'''
import builtins
import hashlib
import pathlib
import sys

sys.path.insert(0, sys.argv[1])
from tools.loaded_execution_capture import CaptureError, ExpectedSource, SourceExecutionCapture
root = pathlib.Path(sys.argv[2])
package = root / "capture_invalid_metadata"
package.mkdir()
source = b"""import builtins
class Spoof:
    def __eq__(self, other):
        builtins.capture_comparator_called = True
        raise AssertionError('candidate comparator executed')
    def __ne__(self, other):
        builtins.capture_comparator_called = True
        raise AssertionError('candidate comparator executed')
__file__ = Spoof()
"""
(package / "__init__.py").write_bytes(source)
capture = SourceExecutionCapture(root, {
    "capture_invalid_metadata": ExpectedSource("capture_invalid_metadata/__init__.py", hashlib.sha256(source).hexdigest())
})
builtins.capture_comparator_called = False
capture.install()
sys.path.insert(0, str(root))
import capture_invalid_metadata
assert not capture.failed and not builtins.capture_comparator_called
assert capture.relevant_graph(frozenset({"capture_invalid_metadata"})).failed_modules == (("capture_invalid_metadata", "module_observation_incomplete"),)
try:
    capture.assert_retained(frozenset({"capture_invalid_metadata"}))
except CaptureError as exc:
    assert str(exc) == "required_module_initialization_failed"
else:
    raise AssertionError("failed selected module was accepted")
''',
    )


def test_unrecorded_dynamic_import_caller_cannot_join_capture(tmp_path: Path) -> None:
    _assert_case(
        tmp_path,
        r"""
import hashlib
import pathlib
import sys

sys.path.insert(0, sys.argv[1])
from tools.loaded_execution_capture import CaptureError, ExpectedSource, SourceExecutionCapture
root = pathlib.Path(sys.argv[2])
package = root / "capture_dynamic"
package.mkdir()
source = b"exec(compile('import pathlib', __file__, 'exec'), globals())\n"
(package / "__init__.py").write_bytes(source)
capture = SourceExecutionCapture(root, {
    "capture_dynamic": ExpectedSource("capture_dynamic/__init__.py", hashlib.sha256(source).hexdigest())
})
capture.install()
sys.path.insert(0, str(root))
import capture_dynamic
graph = capture.relevant_graph(frozenset({"capture_dynamic"}))
assert ("capture_dynamic", "import_caller_code_unrecorded") in graph.unresolved_importers
assert graph.status == "not_established" and not capture.failed
""",
    )


def test_forked_child_cannot_reuse_parent_capture(tmp_path: Path) -> None:
    _assert_case(
        tmp_path,
        r"""
import hashlib
import os
import pathlib
import sys

sys.path.insert(0, sys.argv[1])
from tools.loaded_execution_capture import CaptureError, ExpectedSource, SourceExecutionCapture
root = pathlib.Path(sys.argv[2])
package = root / "capture_fork"
package.mkdir()
source = b"value = 1\n"
(package / "__init__.py").write_bytes(source)
expected = {"capture_fork": ExpectedSource("capture_fork/__init__.py", hashlib.sha256(source).hexdigest())}
capture = SourceExecutionCapture(root, expected)
capture.install()
sys.path.insert(0, str(root))
import capture_fork
capture.assert_retained(frozenset({"capture_fork"}))
parent_pid = os.getpid()
pid = os.fork()
if pid == 0:
    os.getpid = lambda: parent_pid
    try:
        capture.assert_retained(frozenset({"capture_fork"}))
    except CaptureError as exc:
        if str(exc) != "capture_inherited_across_fork":
            os._exit(2)
    else:
        os._exit(3)
    if capture.diagnostic().failure_code != "capture_inherited_across_fork":
        os._exit(4)
    try:
        SourceExecutionCapture(root, expected).install()
    except CaptureError as exc:
        os._exit(0 if str(exc) == "capture_process_already_attempted" else 5)
    os._exit(6)
_, status = os.waitpid(pid, 0)
assert os.waitstatus_to_exitcode(status) == 0
capture.assert_retained(frozenset({"capture_fork"}))
""",
    )


def test_cycle_is_provisional_and_unrelated_failure_is_scoped(tmp_path: Path) -> None:
    _assert_case(
        tmp_path,
        r"""
import builtins
import hashlib
import pathlib
import sys

sys.path.insert(0, sys.argv[1])
from tools.loaded_execution_capture import CaptureError, ExpectedSource, SourceExecutionCapture
root = pathlib.Path(sys.argv[2])
package = root / "capture_cycle"
package.mkdir()
files = {
    "capture_cycle": ("capture_cycle/__init__.py", b"from . import child\nready = True\n"),
    "capture_cycle.child": ("capture_cycle/child.py", b"import builtins\nfrom tools.loaded_execution_capture import CaptureError\ntry:\n    builtins.capture_test.completed('capture_cycle')\nexcept CaptureError as exc:\n    provisional = str(exc) == 'module_not_completed'\nelse:\n    provisional = False\n"),
    "capture_cycle.broken": ("capture_cycle/broken.py", b"raise RuntimeError('initializer failed')\n"),
}
for name, (relative, content) in files.items():
    (root / relative).write_bytes(content)
expected = {name: ExpectedSource(relative, hashlib.sha256(content).hexdigest())
            for name, (relative, content) in files.items()}
capture = SourceExecutionCapture(root, expected)
builtins.capture_test = capture
capture.install()
sys.path.insert(0, str(root))
import capture_cycle
assert capture_cycle.child.provisional
assert capture.completed("capture_cycle").module is capture_cycle
capture.assert_retained(frozenset({"capture_cycle", "capture_cycle.child"}))
try:
    import capture_cycle.broken
except RuntimeError:
    pass
else:
    raise AssertionError("broken initializer unexpectedly succeeded")
assert not capture.failed
graph = capture.relevant_graph(frozenset({"capture_cycle"}))
assert not graph.failed_modules and not graph.failed_imports
capture.assert_retained(frozenset({"capture_cycle", "capture_cycle.child"}))
try:
    capture.assert_retained(frozenset({"capture_cycle.broken"}))
except CaptureError as exc:
    assert str(exc) == "required_module_initialization_failed"
    pass
else:
    raise AssertionError("required failed initializer was accepted")
assert capture.failed
""",
    )


def test_reimported_recorder_cannot_restart_failed_process_owner(tmp_path: Path) -> None:
    _assert_case(
        tmp_path,
        r"""
import hashlib
import importlib.util
import pathlib
import sys
import types
sys.path.insert(0, sys.argv[1])
from tools import loaded_execution_capture as original
root = pathlib.Path(sys.argv[2])
package = root / 'capture_once'
package.mkdir()
source = b'value = 1\n'
(package / '__init__.py').write_bytes(source)
expected = {'capture_once': original.ExpectedSource('capture_once/__init__.py', hashlib.sha256(source).hexdigest())}
sys.modules['capture_once'] = types.ModuleType('capture_once')
first = original.SourceExecutionCapture(root, expected)
try:
    first.install()
except original.CaptureError:
    pass
else:
    raise AssertionError('preloaded package was accepted')
del sys.modules['capture_once']
spec = importlib.util.spec_from_file_location('replacement_capture', original.__file__)
replacement = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = replacement
spec.loader.exec_module(replacement)
again = {'capture_once': replacement.ExpectedSource('capture_once/__init__.py', hashlib.sha256(source).hexdigest())}
try:
    replacement.SourceExecutionCapture(root, again).install()
except replacement.CaptureError as exc:
    assert str(exc) == 'capture_process_already_attempted'
else:
    raise AssertionError('second module instance restarted failed process owner')
""",
    )


def test_reachable_failed_import_and_unrelated_failure_have_distinct_graphs(tmp_path: Path) -> None:
    _assert_case(
        tmp_path,
        r"""
import hashlib
import importlib
import pathlib
import sys
sys.path.insert(0, sys.argv[1])
from tools.loaded_execution_capture import ExpectedSource, SourceExecutionCapture
root = pathlib.Path(sys.argv[2])
package = root / 'capture_graph'
package.mkdir()
files = {
    'capture_graph': ('capture_graph/__init__.py', b''),
    'capture_graph.provider': ('capture_graph/provider.py', b'item = object()\n'),
    'capture_graph.consumer': ('capture_graph/consumer.py', b'from .provider import item as alias\n'),
    'capture_graph.broken': ('capture_graph/broken.py', b'raise RuntimeError("broken")\n'),
    'capture_graph.dependent': ('capture_graph/dependent.py', b'try:\n    from . import broken\nexcept RuntimeError:\n    pass\n'),
}
for relative, source in files.values():
    (root / relative).write_bytes(source)
capture = SourceExecutionCapture(root, {name: ExpectedSource(path, hashlib.sha256(source).hexdigest()) for name, (path, source) in files.items()}, exports={'capture_graph.provider': {'item'}})
capture.install()
sys.path.insert(0, str(root))
consumer = importlib.import_module('capture_graph.consumer')
assert capture.completed_binding('capture_graph.provider', 'item') is consumer.alias
events = [event for event in capture.import_events() if event.importer_name == 'capture_graph.consumer' and event.provider_name == 'capture_graph.provider']
assert len(events) == 1 and events[0].caller_line == 1
capture.assert_import_binding(events[0], importer_attribute='alias', provider_export='item')
try:
    importlib.import_module('capture_graph.broken')
except RuntimeError:
    pass
else:
    raise AssertionError('broken initializer returned normally')
good = capture.relevant_graph(frozenset({'capture_graph.consumer'}))
assert 'capture_graph.provider' in good.reached_sources
assert not good.failed_modules and not good.failed_imports and good.status == 'not_established'
capture.assert_retained(frozenset({'capture_graph.consumer', 'capture_graph.provider'}))
# A caught failed import is still an actual edge of this dependent graph.
importlib.import_module('capture_graph.dependent')
bad = capture.relevant_graph(frozenset({'capture_graph.dependent'}))
assert bad.failed_imports
assert bad.status == 'not_established'
""",
    )


def test_completed_binding_rejects_same_name_replacement(tmp_path: Path) -> None:
    _assert_case(
        tmp_path,
        r"""
import hashlib
import pathlib
import sys
sys.path.insert(0, sys.argv[1])
from tools.loaded_execution_capture import CaptureError, ExpectedSource, SourceExecutionCapture
root = pathlib.Path(sys.argv[2])
package = root / 'capture_binding'
package.mkdir()
source = b'class Capability:\n    pass\n'
(package / '__init__.py').write_bytes(source)
capture = SourceExecutionCapture(root, {'capture_binding': ExpectedSource('capture_binding/__init__.py', hashlib.sha256(source).hexdigest())}, exports={'capture_binding': {'Capability'}})
capture.install()
sys.path.insert(0, str(root))
import capture_binding
original = capture.completed_binding('capture_binding', 'Capability')
assert original is capture_binding.Capability
capture_binding.Capability = type('Capability', (), {})
try:
    capture.completed_binding('capture_binding', 'Capability')
except CaptureError as exc:
    assert str(exc) == 'retained_export_changed'
else:
    raise AssertionError('same-name replacement satisfied retained binding')
assert capture.failed
""",
    )


def test_capture_retains_only_selected_bindings_and_rejects_unselected_lookup(
    tmp_path: Path,
) -> None:
    _assert_case(
        tmp_path,
        r"""
import hashlib
import pathlib
import sys
sys.path.insert(0, sys.argv[1])
from tools.loaded_execution_capture import CaptureError, ExpectedSource, SourceExecutionCapture
root = pathlib.Path(sys.argv[2])
package = root / 'capture_selective'
package.mkdir()
source = b'selected = object()\nunused_candidate = object()\nunrelated = object()\n'
(package / '__init__.py').write_bytes(source)
capture = SourceExecutionCapture(
    root,
    {'capture_selective': ExpectedSource('capture_selective/__init__.py', hashlib.sha256(source).hexdigest())},
    exports={'capture_selective': {'selected', 'unused_candidate'}},
)
capture.install()
sys.path.insert(0, str(root))
import capture_selective
record = capture.completed('capture_selective')
assert set(record.watched_exports) == {'selected', 'unused_candidate'}
assert not hasattr(record, 'completed_bindings')
selected = capture.completed_binding('capture_selective', 'selected')
capture_selective.unrelated = object()
capture_selective.unused_candidate = object()
assert capture.completed_binding('capture_selective', 'selected') is selected
try:
    capture.completed_binding('capture_selective', 'unrelated')
except CaptureError as exc:
    assert str(exc) == 'provider_export_not_recorded'
else:
    raise AssertionError('unselected binding was adopted retrospectively')
""",
    )


def test_unloaded_selected_source_does_not_need_to_exist(tmp_path: Path) -> None:
    _assert_case(
        tmp_path,
        r"""
import hashlib
import pathlib
import sys
sys.path.insert(0, sys.argv[1])
from tools.loaded_execution_capture import ExpectedSource, SourceExecutionCapture
root = pathlib.Path(sys.argv[2])
package = root / 'capture_unused'
package.mkdir()
source = b'value = 1\n'
(package / '__init__.py').write_bytes(source)
capture = SourceExecutionCapture(root, {
    'capture_unused': ExpectedSource('capture_unused/__init__.py', hashlib.sha256(source).hexdigest()),
    'capture_unused.unused': ExpectedSource('capture_unused/absent.py', '0' * 64),
})
capture.install()
sys.path.insert(0, str(root))
import capture_unused
capture.assert_retained(frozenset({'capture_unused'}))
graph = capture.relevant_graph(frozenset({'capture_unused'}))
assert 'capture_unused.unused' not in graph.reached_sources
assert not graph.failed_modules and graph.status == 'not_established'
""",
    )


def test_unselected_source_and_reload_continue_as_candidates(tmp_path: Path) -> None:
    _assert_case(
        tmp_path,
        r"""
import builtins
import hashlib
import importlib
import pathlib
import sys
sys.path.insert(0, sys.argv[1])
from tools.loaded_execution_capture import CaptureError, ExpectedSource, SourceExecutionCapture
root = pathlib.Path(sys.argv[2])
package = root / 'capture_candidate'
package.mkdir()
source = b'import builtins\nbuiltins.candidate_executions = getattr(builtins, "candidate_executions", 0) + 1\n'
(package / '__init__.py').write_bytes(source)
(package / 'unselected.py').write_bytes(b'value = 7\n')
capture = SourceExecutionCapture(root, {'capture_candidate': ExpectedSource('capture_candidate/__init__.py', hashlib.sha256(source).hexdigest())})
capture.install()
sys.path.insert(0, str(root))
import capture_candidate
unselected = importlib.import_module('capture_candidate.unselected')
assert unselected.value == 7
assert not capture.failed
assert capture.relevant_graph(frozenset({'capture_candidate'})).failed_modules == ()
importlib.reload(capture_candidate)
assert builtins.candidate_executions == 2
assert not capture.failed
try:
    capture.assert_retained(frozenset({'capture_candidate'}))
except CaptureError as exc:
    assert str(exc) == 'required_module_initialization_failed'
else:
    raise AssertionError('reloaded module retained prior execution authority')
""",
    )


def test_unadmitted_preexisting_import_hook_refuses_capture_but_not_candidate(
    tmp_path: Path,
) -> None:
    _assert_case(
        tmp_path,
        r"""
import hashlib
import pathlib
import sys
sys.path.insert(0, sys.argv[1])
from tools.loaded_execution_capture import CaptureError, ExpectedSource, SourceExecutionCapture
root = pathlib.Path(sys.argv[2])
package = root / 'capture_custom_hook'
package.mkdir()
source = b'value = 3\n'
(package / '__init__.py').write_bytes(source)
class HarmlessFinder:
    def find_spec(self, fullname, path=None, target=None):
        return None
sys.meta_path.insert(0, HarmlessFinder())
capture = SourceExecutionCapture(root, {'capture_custom_hook': ExpectedSource('capture_custom_hook/__init__.py', hashlib.sha256(source).hexdigest())})
try:
    capture.install()
except CaptureError as exc:
    assert str(exc) == 'capture_preexisting_import_hooks_unsupported'
else:
    raise AssertionError('unadmitted import hook was accepted')
assert capture.failed
sys.path.insert(0, str(root))
import capture_custom_hook
assert capture_custom_hook.value == 3
""",
    )


def test_standard_protocol_cache_and_lazy_annotation_warming_stays_unsealed(tmp_path: Path) -> None:
    _assert_case(
        tmp_path,
        r"""
import hashlib
import pathlib
import sys
import types
import typing
cold = typing._lazy_annotationlib
assert type(cold).__name__ == '_LazyAnnotationLib'
sys.path.insert(0, sys.argv[1])
from tools.loaded_execution_capture import CaptureError, ExpectedSource, SourceExecutionCapture
root = pathlib.Path(sys.argv[2])
package = root / 'capture_warm'
package.mkdir()
source = b'from typing import Protocol, runtime_checkable\n@runtime_checkable\nclass Readable(Protocol):\n    def read(self) -> str: ...\nclass Reader:\n    def read(self) -> str: return "ok"\n'
(package / '__init__.py').write_bytes(source)
capture = SourceExecutionCapture(root, {'capture_warm': ExpectedSource('capture_warm/__init__.py', hashlib.sha256(source).hexdigest())}, exports={'capture_warm': {'Readable'}})
capture.install()
sys.path.insert(0, str(root))
import capture_warm
original = capture.completed_binding('capture_warm', 'Readable')
assert isinstance(capture_warm.Reader(), original)
assert isinstance(capture_warm.Reader(), original)
if type(typing._lazy_annotationlib) is not types.ModuleType:
    _ = typing._lazy_annotationlib.Format
assert typing._lazy_annotationlib is sys.modules['annotationlib']
assert typing._lazy_annotationlib is not cold
assert capture.completed_binding('capture_warm', 'Readable') is original
assert capture.diagnostic().status == 'not_established'
capture_warm.Readable = type('Readable', (), {})
try:
    capture.completed_binding('capture_warm', 'Readable')
except CaptureError as exc:
    assert str(exc) == 'retained_export_changed'
else:
    raise AssertionError('warm-state check accepted a different provider')
""",
    )


def test_failed_relative_imports_are_recorded_without_stopping_candidates(tmp_path: Path) -> None:
    _assert_case(
        tmp_path,
        r"""
import hashlib
import importlib
import pathlib
import sys
sys.path.insert(0, sys.argv[1])
from tools.loaded_execution_capture import ExpectedSource, SourceExecutionCapture
root = pathlib.Path(sys.argv[2])
package = root / 'capture_relative'
package.mkdir()
source = b'''import importlib
try:
    importlib.import_module('.missing', __package__)
except ModuleNotFoundError:
    pass
try:
    importlib.import_module('...outside', __package__)
except ImportError:
    pass
ready = True
'''
(package / '__init__.py').write_bytes(source)
capture = SourceExecutionCapture(root, {'capture_relative': ExpectedSource('capture_relative/__init__.py', hashlib.sha256(source).hexdigest())})
capture.install()
sys.path.insert(0, str(root))
import capture_relative
assert capture_relative.ready and not capture.failed
graph = capture.relevant_graph(frozenset({'capture_relative'}))
assert ('capture_relative', 'capture_relative.missing') in graph.failed_imports
assert ('capture_relative', None) in graph.failed_imports
assert graph.status == 'not_established'
""",
    )
