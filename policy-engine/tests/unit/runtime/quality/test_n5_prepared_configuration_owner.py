"""Exercise the real shared N5 configuration owner and constructor handoffs."""

from __future__ import annotations

from typing import Any, Literal, get_args, get_origin

import pytest
from pydantic import BaseModel, ValidationError

from polisyos.runtime.quality.generation_cycle import (
    GenerationCycleController,
    JointSimulationPort,
)
from polisyos.runtime.quality.joint_simulation_horizon import (
    JointSimulationControllerPolicy,
    JointSimulationHorizonController,
    PreparedJointSimulationConfiguration,
    _RuntimeSettings,
    prepare_joint_simulation_configuration,
    require_prepared_joint_simulation_configuration,
)
from polisyos.runtime.quality.n5_execution_basis import exact_n5_content_bytes


def _assert_consumes_exact_configuration(
    controller: JointSimulationHorizonController,
    prepared: PreparedJointSimulationConfiguration,
) -> None:
    """Compare all actual typed fields, including fields added by the owner."""
    assert type(prepared) is PreparedJointSimulationConfiguration
    assert type(prepared.policy) is JointSimulationControllerPolicy
    assert type(prepared.runtime_settings) is _RuntimeSettings
    assert type(controller.policy) is JointSimulationControllerPolicy
    assert type(controller._settings) is _RuntimeSettings
    for model in (
        prepared.policy,
        prepared.runtime_settings,
        controller.policy,
        controller._settings,
    ):
        assert set(vars(model)) == set(type(model).model_fields)
    assert exact_n5_content_bytes(controller.policy) == exact_n5_content_bytes(prepared.policy)
    assert exact_n5_content_bytes(controller._settings) == exact_n5_content_bytes(
        prepared.runtime_settings
    )
    assert exact_n5_content_bytes(controller._prepared_configuration) == exact_n5_content_bytes(
        prepared
    )
    require_prepared_joint_simulation_configuration(controller, prepared)


def _changed_valid_field(model: BaseModel, name: str) -> BaseModel | None:
    """Generate a distinct native value from this controlled model's real schema."""
    field = type(model).model_fields[name]
    value = getattr(model, name)
    if type(value) is bool:
        alternate: Any = not value
    elif get_origin(field.annotation) is Literal:
        candidates = [item for item in get_args(field.annotation) if item != value]
        if not candidates:
            return None  # A literal with exactly one legal value is fixed by type.
        alternate = candidates[0]
    else:
        pytest.fail(f"no native mutation defined for actual configuration field {name!r}")
    values = {key: getattr(model, key) for key in type(model).model_fields}
    values[name] = alternate
    changed = type(model).model_validate(values)
    assert exact_n5_content_bytes(changed) != exact_n5_content_bytes(model)
    return changed


def test_prepared_configuration_is_strict_complete_and_carries_actual_defaults() -> None:
    policy = JointSimulationControllerPolicy()
    prepared = prepare_joint_simulation_configuration(policy=policy)
    assert type(prepared) is PreparedJointSimulationConfiguration
    assert type(prepared.policy) is JointSimulationControllerPolicy
    assert type(prepared.runtime_settings) is _RuntimeSettings
    assert exact_n5_content_bytes(prepared.policy) == exact_n5_content_bytes(policy)
    assert exact_n5_content_bytes(prepared.runtime_settings) == exact_n5_content_bytes(
        _RuntimeSettings()
    )
    for model in (prepared, prepared.policy, prepared.runtime_settings):
        assert set(vars(model)) == set(type(model).model_fields)
    wire = prepared.model_dump(mode="python")
    assert exact_n5_content_bytes(PreparedJointSimulationConfiguration.model_validate(wire)) == (
        exact_n5_content_bytes(prepared)
    )
    for required_name in ("policy", "runtime_settings"):
        missing = {name: value for name, value in wire.items() if name != required_name}
        with pytest.raises(ValidationError):
            PreparedJointSimulationConfiguration.model_validate(missing)
    with pytest.raises(ValidationError):
        PreparedJointSimulationConfiguration.model_validate({**wire, "extra": "unexpected"})
    with pytest.raises(ValidationError):
        prepared.policy = JointSimulationControllerPolicy()


def test_prepared_horizon_checks_every_actual_mutable_configuration_field() -> None:
    prepared = prepare_joint_simulation_configuration()
    controller = JointSimulationHorizonController(_prepared_configuration=prepared)
    _assert_consumes_exact_configuration(controller, prepared)
    checked: set[tuple[str, str]] = set()
    for model_name in ("policy", "runtime_settings"):
        model = getattr(prepared, model_name)
        for name in type(model).model_fields:
            changed = _changed_valid_field(model, name)
            if changed is None:
                continue
            mutated = prepared.model_copy(update={model_name: changed})
            assert exact_n5_content_bytes(mutated) != exact_n5_content_bytes(prepared)
            with pytest.raises(ValueError, match=r"^n5_prepared_configuration_not_consumed$"):
                require_prepared_joint_simulation_configuration(controller, mutated)
            checked.add((model_name, name))
    assert checked, "the actual controlled configuration has no distinguishable field"
    _assert_consumes_exact_configuration(controller, prepared)


def test_default_rebuild_cannot_change_a_prepared_controller_or_forwarding_chain() -> None:
    """The old selected values survive a real default change and Pydantic rebuild."""
    prepared = prepare_joint_simulation_configuration()
    original = exact_n5_content_bytes(prepared)
    field = _RuntimeSettings.model_fields["shrink_world_credal_state"]
    prior_default = field.default
    assert type(prior_default) is bool
    assert prepared.runtime_settings.shrink_world_credal_state is prior_default
    try:
        field.default = not prior_default
        _RuntimeSettings.model_rebuild(force=True)
        current = prepare_joint_simulation_configuration()
        assert current.runtime_settings.shrink_world_credal_state is not prior_default
        assert exact_n5_content_bytes(current) != original
        assert exact_n5_content_bytes(prepared) == original

        direct = JointSimulationHorizonController(_prepared_configuration=prepared)
        port = JointSimulationPort(_prepared_n5_configuration=prepared)
        generation = GenerationCycleController(_prepared_n5_configuration=prepared)
        assert type(port._controller) is JointSimulationHorizonController
        assert type(generation._simulation_port) is JointSimulationPort
        for controller in (direct, port._controller, generation._simulation_port._controller):
            _assert_consumes_exact_configuration(controller, prepared)
            assert controller._settings.shrink_world_credal_state is prior_default
            with pytest.raises(ValueError, match=r"^n5_prepared_configuration_not_consumed$"):
                require_prepared_joint_simulation_configuration(controller, current)

        fresh = JointSimulationHorizonController()
        _assert_consumes_exact_configuration(fresh, current)
        assert fresh._settings.shrink_world_credal_state is not prior_default
    finally:
        field.default = prior_default
        _RuntimeSettings.model_rebuild(force=True)


def test_explicit_policy_controller_and_port_conflicts_are_refused() -> None:
    prepared = prepare_joint_simulation_configuration()
    with pytest.raises(ValueError, match=r"^n5_prepared_policy_conflict$"):
        JointSimulationHorizonController(
            policy=JointSimulationControllerPolicy(), _prepared_configuration=prepared
        )
    controller = JointSimulationHorizonController(_prepared_configuration=prepared)
    with pytest.raises(ValueError, match=r"^n5_prepared_controller_conflict$"):
        JointSimulationPort(controller=controller, _prepared_n5_configuration=prepared)
    port = JointSimulationPort(_prepared_n5_configuration=prepared)
    with pytest.raises(ValueError, match=r"^generation_cycle_prepared_n5_port_conflict$"):
        GenerationCycleController(simulation_port=port, _prepared_n5_configuration=prepared)


def test_untyped_descriptor_never_becomes_a_prepared_configuration() -> None:
    invalid = object()
    controller = JointSimulationHorizonController()
    with pytest.raises(TypeError, match=r"^n5_prepared_configuration_untyped$"):
        require_prepared_joint_simulation_configuration(controller, invalid)
    with pytest.raises(TypeError, match=r"^n5_prepared_configuration_untyped$"):
        JointSimulationHorizonController(_prepared_configuration=invalid)
    with pytest.raises(TypeError, match=r"^n5_prepared_configuration_untyped$"):
        JointSimulationPort(_prepared_n5_configuration=invalid)
    with pytest.raises(TypeError, match=r"^n5_prepared_configuration_untyped$"):
        GenerationCycleController(_prepared_n5_configuration=invalid)
