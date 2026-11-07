"""Source-owned module facades retain actual bindings without invoking getters."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

_PRODUCT = Path(__file__).resolve().parents[4]

_PROGRAM = r"""
import builtins, hashlib, importlib, pathlib, sys, types
root = pathlib.Path(sys.argv[2])
mode = sys.argv[3]
sys.path.insert(0, sys.argv[1])
from tools.loaded_execution_capture import CaptureError, ExpectedSource, SourceExecutionCapture
package = root / 'recorded_facade'; package.mkdir()
base_source = b'''import builtins, types
class BaseFacade(types.ModuleType):
    def __getattribute__(self, name):
        if builtins.facade_getter_armed:
            builtins.facade_getter_called = True
            raise AssertionError('candidate module getter was invoked')
        return super().__getattribute__(name)
    def alternate(self, name):
        return super().__getattribute__(name)
class OtherFacade(types.ModuleType): pass
'''
provider_source = b'''import sys
from .base import BaseFacade, OtherFacade
def answer(): return 7
class Facade(BaseFacade): pass
sys.modules[__name__].__class__ = Facade
'''
consumer_source = b'''import builtins, importlib, sys, types
from .provider import answer as chosen
class Facade(types.ModuleType):
    def __getattribute__(self, name):
        if builtins.facade_getter_armed:
            builtins.facade_getter_called = True
            raise AssertionError('candidate module getter was invoked')
        return types.ModuleType.__getattribute__(self, name)
sys.modules[__name__].__class__ = Facade
cached = importlib.import_module(__package__ + '.provider')
'''
files = {
    'recorded_facade': ('recorded_facade/__init__.py', b''),
    'recorded_facade.base': ('recorded_facade/base.py', base_source),
    'recorded_facade.provider': ('recorded_facade/provider.py', provider_source),
    'recorded_facade.consumer': ('recorded_facade/consumer.py', consumer_source),
}
for relative, source in files.values():
    (root / relative).write_bytes(source)
capture = SourceExecutionCapture(root, {
    name: ExpectedSource(relative, hashlib.sha256(source).hexdigest())
    for name, (relative, source) in files.items()
}, exports={'recorded_facade.provider': {'answer'}})
builtins.facade_getter_armed = False
builtins.facade_getter_called = False
builtins.facade_comparator_called = False
capture.install(); sys.path.insert(0, str(root))
consumer = importlib.import_module('recorded_facade.consumer')
provider = sys.modules['recorded_facade.provider']
provider_ns = types.ModuleType.__getattribute__(provider, '__dict__')
consumer_ns = types.ModuleType.__getattribute__(consumer, '__dict__')
assert type(provider) is provider_ns['Facade'] and type(consumer) is consumer_ns['Facade']
builtins.facade_getter_armed = True
assert capture.completed('recorded_facade.provider').module is provider
assert capture.completed('recorded_facade.consumer').module is consumer
capture.assert_retained(frozenset({'recorded_facade.provider', 'recorded_facade.consumer'}))
capture.assert_binding('recorded_facade.consumer', 'chosen', 'recorded_facade.provider', 'answer')
events = capture.import_events()
event = next(event for event in events if event.importer is consumer and event.provider is provider
             and event.route == 'builtin_import' and 'answer' in event.requested_exports)
capture.assert_import_binding(event, importer_attribute='chosen', provider_export='answer')
graph = capture.relevant_graph(frozenset({'recorded_facade.consumer'}))
assert 'recorded_facade.provider' in graph.reached_sources
assert not graph.failed_modules and not graph.unresolved_importers
assert consumer_ns['cached'] is provider and not builtins.facade_getter_called
if mode == 'positive':
    assert capture.diagnostic().status == 'not_established'
    capture.close()
    assert capture.diagnostic().phase == 'closed'
    assert not capture._source_owned_module_classes and not builtins.facade_getter_called
else:
    facade = provider_ns['Facade']
    base = provider_ns['BaseFacade']
    if mode == 'remove_guard':
        capture._source_class_matches = lambda *args, **kwargs: True
        mode = 'method_code'
    if mode == 'method_code':
        method = vars(base)['__getattribute__']; original = method.__code__
        method.__code__ = vars(base)['alternate'].__code__
        restore = lambda: setattr(method, '__code__', original)
    elif mode == 'class_metadata':
        original = facade.__name__; facade.__name__ = 'SubstitutedFacade'
        restore = lambda: setattr(facade, '__name__', original)
    elif mode == 'spoof_class_name':
        class Spoof(str):
            def __eq__(self, other):
                builtins.facade_comparator_called = True
                raise AssertionError('candidate class-name comparator executed')
        original = facade.__name__; facade.__name__ = Spoof('Facade')
        restore = lambda: setattr(facade, '__name__', original)
    elif mode == 'method_defaults':
        method = vars(base)['__getattribute__']; original = method.__defaults__
        method.__defaults__ = ('altered',)
        restore = lambda: setattr(method, '__defaults__', original)
    elif mode == 'mro':
        original = facade.__bases__
        facade.__bases__ = (provider_ns['OtherFacade'],)
        restore = lambda: setattr(facade, '__bases__', original)
    elif mode == 'provider':
        original = provider_ns['answer']; provider_ns['answer'] = lambda: 7
        restore = lambda: provider_ns.__setitem__('answer', original)
    elif mode == 'metadata':
        class Spoof:
            def __eq__(self, other):
                builtins.facade_comparator_called = True
                raise AssertionError('candidate metadata comparator executed')
        spec = provider_ns['__spec__']; original = spec.origin; spec.origin = Spoof()
        restore = lambda: setattr(spec, 'origin', original)
    elif mode == 'base_metadata':
        base_ns = types.ModuleType.__getattribute__(sys.modules['recorded_facade.base'], '__dict__')
        spec = base_ns['__spec__']; original = spec.origin; spec.origin = object()
        restore = lambda: setattr(spec, 'origin', original)
    elif mode == 'class':
        original = type(provider); provider.__class__ = provider_ns['OtherFacade']
        restore = lambda: types.ModuleType.__setattr__(provider, '__class__', original)
    else:
        raise AssertionError('unknown test mode')
    try:
        capture.assert_import_binding(event, importer_attribute='chosen', provider_export='answer')
    except CaptureError:
        pass
    else:
        raise AssertionError('module facade drift was accepted')
    finally:
        restore()
    assert capture.failed and not builtins.facade_getter_called and not builtins.facade_comparator_called
    try:
        capture.assert_retained(frozenset({'recorded_facade.provider'}))
    except CaptureError:
        pass
    else:
        raise AssertionError('restoration revived the failed capture')
    capture.close()
    assert capture.failed and not capture._source_owned_module_classes
"""


@pytest.mark.parametrize(
    "mode",
    [
        "positive",
        "method_code",
        "class_metadata",
        "spoof_class_name",
        "method_defaults",
        "mro",
        "provider",
        "metadata",
        "base_metadata",
        "class",
        "remove_guard",
    ],
)
def test_source_owned_facade_binding_and_sticky_mutation(tmp_path: Path, mode: str) -> None:
    """Actual recorded provider/importer roles must stay source-owned and passive."""
    result = subprocess.run(
        [sys.executable, "-I", "-S", "-B", "-c", _PROGRAM, str(_PRODUCT), str(tmp_path), mode],
        capture_output=True,
        text=True,
        check=False,
        timeout=20,
    )
    if mode == "remove_guard":
        print(f"module class guard removal exit: {result.returncode}")
        print(result.stderr, end="")
        assert result.returncode != 0
        assert "module facade drift was accepted" in result.stderr
    else:
        assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    "mode",
    ["foreign_class", "dict_descriptor", "mutable_class", "mutable_default", "mutable_closure"],
)
def test_unknown_or_descriptor_spoofed_module_class_is_not_admitted(
    tmp_path: Path, mode: str
) -> None:
    """An unknown class or hostile dictionary descriptor is never executed by inspection."""
    program = r"""
import builtins, hashlib, importlib, pathlib, sys, types
root = pathlib.Path(sys.argv[2]); mode = sys.argv[3]
sys.path.insert(0, sys.argv[1])
from tools.loaded_execution_capture import CaptureError, ExpectedSource, SourceExecutionCapture
class Foreign(types.ModuleType): pass
builtins.foreign_module_class = Foreign
builtins.dict_descriptor_called = False
if mode == 'foreign_class':
    source = b'import builtins, sys\nsys.modules[__name__].__class__ = builtins.foreign_module_class\n'
elif mode == 'dict_descriptor':
    source = b'''import builtins, sys, types
class Facade(types.ModuleType):
    @property
    def __dict__(self):
        builtins.dict_descriptor_called = True
        raise AssertionError('candidate __dict__ descriptor executed')
sys.modules[__name__].__class__ = Facade
'''
elif mode == 'mutable_class':
    source = b'import sys, types\nclass Facade(types.ModuleType):\n    state = {}\nsys.modules[__name__].__class__ = Facade\n'
elif mode == 'mutable_default':
    source = b'import sys, types\nclass Facade(types.ModuleType):\n    def __getattribute__(self, name, state={}): return types.ModuleType.__getattribute__(self, name)\nsys.modules[__name__].__class__ = Facade\n'
else:
    source = b'''import sys, types
def make_facade():
    state = {}
    class Facade(types.ModuleType):
        def __getattribute__(self, name):
            if state: return None
            return types.ModuleType.__getattribute__(self, name)
    return Facade
Facade = make_facade()
sys.modules[__name__].__class__ = Facade
'''
(root / 'unqualified_facade.py').write_bytes(source)
capture = SourceExecutionCapture(root, {'unqualified_facade': ExpectedSource('unqualified_facade.py', hashlib.sha256(source).hexdigest())})
capture.install(); sys.path.insert(0, str(root))
importlib.import_module('unqualified_facade')
assert not builtins.dict_descriptor_called
try:
    capture.assert_retained(frozenset({'unqualified_facade'}))
except CaptureError:
    pass
else:
    raise AssertionError('unqualified module class was accepted')
assert not builtins.dict_descriptor_called
"""
    result = subprocess.run(
        [sys.executable, "-I", "-S", "-B", "-c", program, str(_PRODUCT), str(tmp_path), mode],
        capture_output=True,
        text=True,
        check=False,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("mode", ["positive", "class_code"])
def test_actual_foundry_module_facade_roles_are_retained(mode: str) -> None:
    """The real Foundry initializers produce the same bounded module-class evidence."""
    program = r"""
import hashlib, importlib, pathlib, sys, types
root = pathlib.Path(sys.argv[1]); mode = sys.argv[2]
sys.path.insert(0, str(root))
from tools.loaded_execution_capture import CaptureError, ExpectedSource, SourceExecutionCapture
files = {
    'polisyos': 'src/polisyos/__init__.py',
    'polisyos.foundry': 'src/polisyos/foundry/__init__.py',
    'polisyos.foundry.compile': 'src/polisyos/foundry/compile/__init__.py',
    'polisyos.foundry.execute': 'src/polisyos/foundry/execute/__init__.py',
}
capture = SourceExecutionCapture(root, {
    name: ExpectedSource(path, hashlib.sha256((root / path).read_bytes()).hexdigest())
    for name, path in files.items()
})
capture.install(); sys.path.insert(0, str(root / 'src'))
foundry = importlib.import_module('polisyos.foundry')
compiler = importlib.import_module('polisyos.foundry.compile')
executor = importlib.import_module('polisyos.foundry.execute')
for name, module in [('polisyos.foundry', foundry),
                     ('polisyos.foundry.compile', compiler),
                     ('polisyos.foundry.execute', executor)]:
    assert type(module) is not types.ModuleType
    assert capture.completed(name).module is module
capture.assert_retained(frozenset(files))
parent_ns = capture.retained_module_namespace('polisyos.foundry')
assert parent_ns['compile'] is compiler and parent_ns['execute'] is executor
assert foundry.compile is compiler and foundry.execute is executor
assert capture.diagnostic().status == 'not_established'
if mode == 'class_code':
    method = vars(type(compiler))['__call__']; original = method.__code__
    method.__code__ = vars(type(executor))['__call__'].__code__
    try:
        capture.assert_retained(frozenset({'polisyos.foundry.compile'}))
    except CaptureError:
        pass
    else:
        raise AssertionError('actual Foundry class code drift was accepted')
    finally:
        method.__code__ = original
    try:
        capture.assert_retained(frozenset({'polisyos.foundry.compile'}))
    except CaptureError:
        pass
    else:
        raise AssertionError('restoration revived the actual Foundry capture')
capture.close()
"""
    result = subprocess.run(
        [sys.executable, "-I", "-S", "-B", "-c", program, str(_PRODUCT), mode],
        capture_output=True,
        text=True,
        check=False,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr


def test_class_construction_provider_substitution_remains_unqualified(tmp_path: Path) -> None:
    """Matching namespace metadata does not prove the class-construction provider."""
    program = r"""
import builtins, hashlib, importlib, pathlib, sys, types
root = pathlib.Path(sys.argv[2])
sys.path.insert(0, sys.argv[1])
from tools.loaded_execution_capture import ExpectedSource, SourceExecutionCapture
source = b'''import sys, types
class Facade(types.ModuleType):
    def __getattribute__(self, name): return types.ModuleType.__getattribute__(self, name)
sys.modules[__name__].__class__ = Facade
'''
(root / 'substituted_facade.py').write_bytes(source)
capture = SourceExecutionCapture(root, {
    'substituted_facade': ExpectedSource(
        'substituted_facade.py', hashlib.sha256(source).hexdigest()
    )
})
fake = type('Facade', (types.ModuleType,), {'__module__': 'substituted_facade'})
original = builtins.__build_class__
def substitute(function, name, *bases, **keywords):
    if name == 'Facade':
        return fake
    return original(function, name, *bases, **keywords)
builtins.__build_class__ = substitute
try:
    capture.install()
    sys.path.insert(0, str(root))
    module = importlib.import_module('substituted_facade')
finally:
    builtins.__build_class__ = original
assert type(module) is fake
capture.assert_retained(frozenset({'substituted_facade'}))
reference = capture._source_owned_module_classes['substituted_facade']
assert reference.module_type is fake and reference.classes[0].functions == ()
assert capture.diagnostic().status == 'not_established'
capture.close()
"""
    result = subprocess.run(
        [sys.executable, "-I", "-S", "-B", "-c", program, str(_PRODUCT), str(tmp_path)],
        capture_output=True,
        text=True,
        check=False,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr
