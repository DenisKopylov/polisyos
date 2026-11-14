"""Observe declared bound-method state without inventing opaque receiver identity."""

from __future__ import annotations

import hashlib
import importlib
import importlib.machinery
import sys

import pytest

from polisyos.runtime.quality import confidence_ledger as ledger
from polisyos.runtime.quality import n5_execution_basis as basis


@pytest.fixture
def recorded_bound_method_module(tmp_path, monkeypatch):
    """Use a real tiny recorder; the supplied bridge is a declared test root."""
    from tools import loaded_execution_capture as recorder_owner
    from tools.loaded_execution_capture import ExpectedSource, SourceExecutionCapture

    source = """from typing import Protocol
class RunnerProtocol(Protocol):
    def execute(self, value=1): ...
class Runner(RunnerProtocol):
    def execute(self, value=1):
        return value
class Slotted:
    __slots__ = ("hidden",)
    def execute(self):
        return self.hidden
class CustomReader:
    def __getattribute__(self, name):
        raise AssertionError("opaque receiver getter must not run")
    def execute(self):
        return 1
"""
    name = "codec_bound_method_sample"
    path = tmp_path / f"{name}.py"
    path.write_text(source)
    capture = SourceExecutionCapture(
        tmp_path,
        {name: ExpectedSource(path.name, hashlib.sha256(path.read_bytes()).hexdigest())},
        exports={name: {"Runner", "Slotted", "CustomReader"}},
    )
    slot = "_polisyos_loaded_execution_owner_v1"
    assert slot not in vars(sys)
    assert recorder_owner._PROCESS_CAPTURE is None
    monkeypatch.setattr(recorder_owner, "_PROCESS_CAPTURE", None)
    monkeypatch.setitem(vars(sys), slot, None)
    monkeypatch.delitem(vars(sys), slot)
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setattr(
        sys,
        "meta_path",
        [
            importlib.machinery.BuiltinImporter,
            importlib.machinery.FrozenImporter,
            importlib.machinery.PathFinder,
        ],
    )
    capture.install()
    try:
        module = importlib.import_module(name)
        # This unit root establishes only actual completed-binding membership;
        # it is not a production host appointment or native-provider proof.
        monkeypatch.setattr(
            ledger,
            "_candidate_n5_host_capture",
            lambda: (capture, None),
        )
        yield module
    finally:
        capture.close()
        sys.modules.pop(name, None)


def test_bound_method_content_tracks_complete_plain_receiver_without_invocation(
    recorded_bound_method_module,
):
    module = recorded_bound_method_module
    first = module.Runner()
    second = module.Runner()
    before = basis.snapshot_n5_callable_content_v3(first.execute)
    assert before is not None
    assert before == basis.snapshot_n5_callable_content_v3(second.execute)
    first.values = [1]
    state_one = basis.snapshot_n5_callable_content_v3(first.execute)
    assert state_one is not None and state_one != before
    first.values[0] = 2
    state_two = basis.snapshot_n5_callable_content_v3(first.execute)
    assert state_two is not None and state_two != state_one
    first.unknown = object()
    assert basis.snapshot_n5_callable_content_v3(first.execute) is None


def test_bound_method_content_refuses_hidden_or_custom_receiver_storage(
    recorded_bound_method_module,
):
    from types import MethodType

    module = recorded_bound_method_module
    slotted = module.Slotted()
    slotted.hidden = 1
    assert basis.snapshot_n5_callable_content_v3(slotted.execute) is None
    custom = module.CustomReader()
    call = MethodType(vars(module.CustomReader)["execute"], custom)
    assert basis.snapshot_n5_callable_content_v3(call) is None


def test_bound_method_content_refuses_same_named_unrecorded_class(recorded_bound_method_module):
    module = recorded_bound_method_module
    replacement = type(
        "Runner", (), {"__module__": module.__name__, "execute": module.Runner.execute}
    )
    assert basis.snapshot_n5_callable_content_v3(replacement().execute) is None


def test_callable_snapshot_refuses_noncallable_with_native_export_reference(monkeypatch):
    # Binding membership and callability are different properties: a native
    # module can also export data. Do not infer the latter from the former.
    monkeypatch.setattr(basis, "_n5_recorded_native_reference", lambda _value: {"selected": True})
    assert basis.snapshot_n5_callable_content_v3(7) is None
