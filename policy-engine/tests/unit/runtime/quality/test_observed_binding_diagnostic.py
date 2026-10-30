"""Diagnostic bindings come from actual captured imports, not a source-only closure."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_PRODUCT = Path(__file__).resolve().parents[4]


def test_observed_bindings_refuse_a_restored_consumer_spoof(tmp_path: Path) -> None:
    """Recorded provider and aliased consumer objects remain equal by identity."""
    program = r"""
import __future__, ast, hashlib, importlib, pathlib, sys, types, typing
product = pathlib.Path(sys.argv[1])
root = pathlib.Path(sys.argv[2])
mode = sys.argv[3]
sys.path.insert(0, str(product))
from tools import loaded_execution_capture as recorder
from tools.loaded_execution_capture import CaptureError, ExpectedSource, SourceExecutionCapture
package = root / 'observed_binding'
package.mkdir()
files = {
    'observed_binding': ('observed_binding/__init__.py', b''),
    'observed_binding.hidden': ('observed_binding/hidden.py', b'value = 1\n'),
    'observed_binding.provider': ('observed_binding/provider.py', b'''from typing import Protocol, runtime_checkable
@runtime_checkable
class Capability(Protocol):
    def read(self) -> str: ...
'''),
    'observed_binding.facade': ('observed_binding/facade.py', b'''from . import hidden as local_helper
from .provider import Capability as Alias
'''),
    'observed_binding.consumer': ('observed_binding/consumer.py', b'from .facade import Alias as Chosen\nfrom .facade import Alias as Other\n'),
}
for relative, source in files.values():
    (root / relative).write_bytes(source)
capture = SourceExecutionCapture(root, {
    name: ExpectedSource(path, hashlib.sha256(source).hexdigest())
    for name, (path, source) in files.items()
}, exports={
    'observed_binding.provider': {'Capability'},
    'observed_binding.facade': {'Alias'},
})
capture.install()
sys.path.insert(0, str(root))
consumer = importlib.import_module('observed_binding.consumer')
graph = capture.relevant_graph(frozenset({'observed_binding.consumer'}))
source_file = product / 'src/polisyos/runtime/quality/confidence_ledger.py'
tree = ast.parse(source_file.read_bytes(), filename=str(source_file))
names = {'_passive_capture_lookup', '_source_import_aliases_for_event', '_observed_source_bindings',
         '_observe_unsealed_host_capture'}
functions = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
assert {node.name for node in functions} == names
class TestLedgerError(Exception): pass
scope = {'ast': ast, 'hashlib': hashlib, 'types': types, 'cast': typing.cast, 'Path': pathlib.Path,
         'sys': sys, '__name__': 'observed_binding.consumer', 'ConfidenceLedgerError': TestLedgerError,
         '_NO_EXECUTION_BINDING': object(), '_host_recorder_anchor_matches': lambda *args: True,
         '_loaded_policy_engine_root': lambda: root,
         'capture_loaded_deployment_identity': lambda: types.SimpleNamespace(
              status='not_established', reason_code='fixture_unavailable')}
scope['_diagnose_unqualified_authority_import_candidates'] = lambda *args: (_ for _ in ()).throw(
    AssertionError('source-only closure was invoked')
)
compiled = compile(ast.Module(body=functions, type_ignores=[]), str(source_file), 'exec',
                   flags=__future__.annotations.compiler_flag, dont_inherit=True)
exec(compiled, scope)
observe = scope['_observed_source_bindings']
bindings, disagreements = observe(root, capture, graph)
provider = [row for row in bindings if row[0] == 'observed_binding.provider' and row[1] == 'Capability']
facade = [row for row in bindings if row[0] == 'observed_binding.facade' and row[1] == 'Alias']
assert len(provider) == len(facade) == 1
assert ('observed_binding.facade', 'Alias') in provider[0][3]
assert ('observed_binding.consumer', 'Chosen') in facade[0][3]
assert ('observed_binding.consumer', 'Other') in facade[0][3]
assert not disagreements
assert capture.diagnostic().status == 'not_established'
report = scope['_observe_unsealed_host_capture'](recorder, capture)
assert report['status'] == report['protected_loaded_execution_status'] == 'not_established'
assert report['executed_direct_bindings'] == bindings
assert report['observed_binding_disagreements'] == ()
original = consumer.Chosen
if mode == 'remove_guard':
    capture.assert_import_binding = lambda *args, **kwargs: None
consumer.Chosen = type('Capability', (), {})
bindings, disagreements = observe(root, capture, graph)
assert ('observed_binding.facade', 'Alias', 'observed_binding.consumer', 'Chosen') in disagreements
facade = [row for row in bindings if row[0] == 'observed_binding.facade' and row[1] == 'Alias']
assert ('observed_binding.consumer', 'Other') in facade[0][3]
assert ('observed_binding.consumer', 'Chosen') not in facade[0][3]
event = next(event for event in capture.import_events() if event.provider_name == 'observed_binding.facade'
             and event.importer_name == 'observed_binding.consumer' and event.caller_line == 1)
try:
    capture.assert_import_binding(event, importer_attribute='Chosen', provider_export='Alias')
except CaptureError as exc:
    assert str(exc) == 'import_event_binding_changed'
else:
    raise AssertionError('changed actual consumer binding was accepted')
finally:
    consumer.Chosen = original
assert capture.failed
try:
    observe(root, capture, graph)
except CaptureError:
    pass
else:
    raise AssertionError('restoring consumer erased the failed capture')
"""
    for mode in ("normal", "remove_guard"):
        case_root = tmp_path / mode
        case_root.mkdir()
        result = subprocess.run(
            [sys.executable, "-I", "-S", "-B", "-c", program, str(_PRODUCT), str(case_root), mode],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
        if mode == "remove_guard":
            print(f"binding guard removal exit: {result.returncode}")
            print(result.stderr, end="")
            assert result.returncode != 0
            assert "changed actual consumer binding was accepted" in result.stderr
        else:
            assert result.returncode == 0, result.stderr
