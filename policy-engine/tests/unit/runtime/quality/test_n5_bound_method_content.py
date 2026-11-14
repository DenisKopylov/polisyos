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

    source = """import random
import _random
from dataclasses import dataclass
from typing import Protocol
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
class NativeRandom(random.Random):
    def execute(self):
        return self.random()
@dataclass(frozen=True)
class FrozenNativeRandom(_random.Random):
    marker: int = 3
    def execute(self):
        return self.random()
class NativeList(list):
    def execute(self):
        return self[0]
"""
    name = "codec_bound_method_sample"
    path = tmp_path / f"{name}.py"
    path.write_text(source)
    capture = SourceExecutionCapture(
        tmp_path,
        {name: ExpectedSource(path.name, hashlib.sha256(path.read_bytes()).hexdigest())},
        exports={
            name: {
                "Runner",
                "Slotted",
                "CustomReader",
                "NativeRandom",
                "FrozenNativeRandom",
                "NativeList",
            }
        },
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


@pytest.mark.parametrize("receiver_kind", ["NativeRandom", "FrozenNativeRandom", "NativeList"])
def test_bound_receiver_native_ancestor_state_is_unknown(
    recorded_bound_method_module, monkeypatch, receiver_kind
):
    module = recorded_bound_method_module
    cls = vars(module)[receiver_kind]
    if receiver_kind == "FrozenNativeRandom":
        first, second = cls(), cls()
        first.seed(1)
        second.seed(2)
    elif receiver_kind == "NativeList":
        first, second = cls([1]), cls([2])
    else:
        first, second = cls(1), cls(2)
    assert vars(first) == vars(second)
    first_content = basis.snapshot_n5_callable_content_v3(first.execute)
    second_content = basis.snapshot_n5_callable_content_v3(second.execute)
    assert first.execute() != second.execute()
    assert first_content is None and second_content is None
    # Removing the shared physical-storage guard re-establishes an equal key
    # for genuinely different native state, including a frozen dataclass.
    with monkeypatch.context() as control:
        control.setattr(basis, "_require_accounted_n5_instance_layout", lambda *args, **kw: None)
        first_content = basis.snapshot_n5_callable_content_v3(first.execute)
        second_content = basis.snapshot_n5_callable_content_v3(second.execute)
        assert first_content is not None and first_content == second_content


def test_string_enum_native_payload_is_bound_without_calling_override():
    import json
    from enum import Enum

    class Mode(str, Enum):
        FIRST = "one"
        SECOND = "two"

        def __str__(self):
            raise AssertionError("native scalar projection must not dispatch override")

    first = Mode.FIRST
    second = Mode.SECOND
    # All Python instance fields can be made equal; the real Unicode payload
    # remains different and must still distinguish the supported enum values.
    original = vars(second).copy()
    try:
        vars(second).clear()
        vars(second).update(vars(first))
        before = basis._N5ContentGraph().wire(first)
        after = basis._N5ContentGraph().wire(second)
        assert before != after
        assert json.loads(before)["nodes"][0]["native_scalar_payload"] == {"str": "one"}
        assert json.loads(after)["nodes"][0]["native_scalar_payload"] == {"str": "two"}
    finally:
        vars(second).clear()
        vars(second).update(original)
