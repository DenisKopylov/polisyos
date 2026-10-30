"""Actual configured implementation binding for an admitted child composition."""

from __future__ import annotations

import types

import pytest

from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.scientist.orchestration.engine.component_identity import (
    _capture_configured_component_owner,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.protocol import NodeOutcome, NodeSpec
from polisyos.scientist.orchestration.engine.state import ExperimentState


class _ConfiguredNode:
    extra_write = False

    def __init__(self, value: int) -> None:
        self.value = value

    def bind(self, params: dict[str, int]) -> _ConfiguredNode:
        return type(self)(params.get("value", self.value))

    @property
    def spec(self) -> NodeSpec:
        return NodeSpec(
            metadata=ComponentMetadata(
                component_id=ComponentId.parse("scientist.node_configured_identity_probe@1.0.0"),
                kind=ComponentKind.SCIENTIST_NODE,
                abi_targets={"world_abi": "1.x"},
                display_name="Configured identity probe",
                capabilities=Capability.SCIENTIST_NODE,
            ),
            state_writes=["params.actual_value", *(["params.secret"] if self.extra_write else [])],
        )

    def execute(self, ctx: ExecutionContext | None, state: ExperimentState) -> NodeOutcome:
        del ctx
        state.params["actual_value"] = self.value
        return NodeOutcome(status="ok", state=state)


def test_configured_identity_binds_real_nondefault_implementation() -> None:
    registered = _ConfiguredNode(0)
    owner = _capture_configured_component_owner(registered, {"value": 7})
    actual = owner.bound_node
    identity = owner.reconcile(registered, actual, {"value": 7})
    assert identity.component_id == str(actual.spec.metadata.component_id)
    assert identity.bound_state_sha256 != owner.registered_state_sha256
    # The check guards the real selected callable, not a marker-only dummy.
    state = ExperimentState(run_id="configured-member")
    result = owner.execute(None, state)
    assert result.state.params["actual_value"] == 7


@pytest.mark.parametrize("substitution", ["registration", "binding", "params"])
def test_configured_identity_refuses_substitution_before_dispatch(substitution: str) -> None:
    registered = _ConfiguredNode(0)
    owner = _capture_configured_component_owner(registered, {"value": 7})
    actual = owner.bound_node
    selected_registration = _ConfiguredNode(0) if substitution == "registration" else registered
    selected_bound = _ConfiguredNode(8) if substitution == "binding" else actual
    selected_params = {"value": 8} if substitution == "params" else {"value": 7}
    with pytest.raises(ValueError, match="child_component_.*changed"):
        owner.reconcile(selected_registration, selected_bound, selected_params)


def test_configured_identity_detects_actual_callable_code_replacement(monkeypatch) -> None:
    registered = _ConfiguredNode(0)
    owner = _capture_configured_component_owner(registered, {"value": 7})
    actual = owner.bound_node

    def changed(self, ctx, state):
        raise AssertionError("the substituted implementation must not execute")

    monkeypatch.setattr(_ConfiguredNode.execute, "__code__", changed.__code__)
    with pytest.raises(ValueError, match="engine_component_callable_changed"):
        owner.reconcile(registered, actual, {"value": 7})


def test_configured_identity_detects_instance_dispatch_override(monkeypatch) -> None:
    registered = _ConfiguredNode(0)
    owner = _capture_configured_component_owner(registered, {"value": 7})
    actual = owner.bound_node
    monkeypatch.setattr(actual, "execute", lambda _ctx, _state: None)
    with pytest.raises(ValueError, match="child_component_actual_dispatch_changed"):
        owner.reconcile(registered, actual, {"value": 7})


def test_configured_identity_detects_registration_state_mutation() -> None:
    registered = _ConfiguredNode(0)
    owner = _capture_configured_component_owner(registered, {"value": 7})
    actual = owner.bound_node
    registered.value = 4
    with pytest.raises(ValueError, match="child_component_registered_state_changed"):
        owner.reconcile(registered, actual, {"value": 7})


def _substituted_execute(self, ctx, state):
    del self, ctx
    state.params["actual_value"] = 999
    return NodeOutcome(status="ok", state=state)


class _DispatchingNode(_ConfiguredNode):
    override_dispatch = False

    def __getattribute__(self, name):
        if name == "execute" and type(self).override_dispatch:
            return types.MethodType(_substituted_execute, self)
        return super().__getattribute__(name)


class _LookupChangingNode(_ConfiguredNode):
    lookup_count = 0
    change_after_first = False

    def __getattribute__(self, name):
        if name == "execute" and type(self).change_after_first:
            type(self).lookup_count += 1
            if type(self).lookup_count > 1:
                return types.MethodType(_substituted_execute, self)
        return super().__getattribute__(name)


def test_configured_dispatch_uses_checked_target_without_second_lookup(monkeypatch) -> None:
    from polisyos.scientist.orchestration.engine import component_identity

    registered = _LookupChangingNode(0)
    owner = _capture_configured_component_owner(registered, {"value": 7})
    monkeypatch.setattr(_LookupChangingNode, "change_after_first", True)
    monkeypatch.setattr(_LookupChangingNode, "lookup_count", 0)
    result = owner.execute(None, ExperimentState(run_id="held-dispatch"))
    assert result.state.params["actual_value"] == 7
    assert _LookupChangingNode.lookup_count == 1
    # Keep the same checks/markers but remove the held-target property. A
    # second attribute lookup selects different real work, exposing the gap.
    with monkeypatch.context() as removal:
        removal.setattr(
            component_identity,
            "_invoke_configured_dispatch",
            lambda captured, ctx, state: captured.bound_node.execute(ctx, state),
        )
        _LookupChangingNode.lookup_count = 0
        changed = owner.execute(None, ExperimentState(run_id="held-dispatch-removal"))
        assert changed.state.params["actual_value"] == 999
    _LookupChangingNode.lookup_count = 0
    restored = owner.execute(None, ExperimentState(run_id="held-dispatch-restored"))
    assert restored.state.params["actual_value"] == 7


def test_configured_identity_recomputes_spec_content_with_markers_intact(monkeypatch) -> None:
    registered = _ConfiguredNode(0)
    owner = _capture_configured_component_owner(registered, {"value": 7})
    actual = owner.bound_node
    component_id = str(actual.spec.metadata.component_id)
    monkeypatch.setattr(_ConfiguredNode, "extra_write", True)
    assert str(actual.spec.metadata.component_id) == component_id
    with pytest.raises(ValueError, match="engine_component_spec_changed"):
        owner.reconcile(registered, actual, {"value": 7})


def test_configured_identity_rejects_an_unrelated_supplied_bound_result() -> None:
    registered = _ConfiguredNode(0)
    owner = _capture_configured_component_owner(registered, {"value": 7})
    assert owner.bound_node.value == 7
    with pytest.raises(ValueError, match="child_component_bound_object_changed"):
        owner.reconcile(registered, _ConfiguredNode(99), {"value": 7})
    # A different instance with the same type and fields is still not the
    # registered binder's retained result; shape equality is not ownership.
    same_state = _ConfiguredNode(7)
    assert vars(same_state) == vars(owner.bound_node)
    with pytest.raises(ValueError, match="child_component_bound_object_changed"):
        owner.reconcile(registered, same_state, {"value": 7})
