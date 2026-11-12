"""Exercise the real shared N5 configuration owner and constructor handoffs."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal, get_args, get_origin

import pytest
from pydantic import BaseModel, ValidationError

from polisyos.core.artifacts import ArtifactID, ArtifactRef, FileSystemCAS
from polisyos.pdc import gy_content_hash
from polisyos.runtime.quality.candidate_simulation import (
    CandidateScenarioN5Config,
    CandidateScenarioSetToRule,
    CandidateSimulationContextHandoff,
    CandidateSimulationContextInputs,
    CandidateSimulationScenarioProfile,
    candidate_simulation_profile_ref,
)
from polisyos.runtime.quality.cycle_substrate import CycleSubstrateContext
from polisyos.runtime.quality.generation_cycle import (
    GenerationCycleController,
    JointSimulationPort,
)
from polisyos.runtime.quality.joint_simulation_horizon import (
    HorizonSpec,
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


def _candidate_context_fixture(
    tmp_path: Path, *, domain: str = "education"
) -> tuple[CycleSubstrateContext, CandidateSimulationContextHandoff, FileSystemCAS]:
    """Build typed context and handoff using the existing cycle-substrate fixture."""
    from tests.unit.runtime.quality.test_cycle_substrate import _cycle_context

    problem_ref = gy_content_hash({"fixture": "native-n5-context", "domain": domain})
    context = _cycle_context(domain=domain, design_problem_ref=problem_ref)
    inputs = CandidateSimulationContextInputs(
        substrate_registry=context.substrate_registry,
        selected_registry_entry_hashes=context.selected_registry_entry_hashes,
        world_model_record=context.world_model_record,
    )
    profile_values = {
        "profile_id": "native-n5-context-fixture",
        "profile_selection_ref": gy_content_hash({"profile": domain}),
        "context_inputs": inputs,
        "rule": CandidateScenarioSetToRule(
            operator_kind="set_to",
            parameter_id="intensity",
            target_world_slot=f"{domain}.teaching_method",
            unit_id="synthetic_score",
            minimum=0,
            maximum=1,
        ),
        "n5": CandidateScenarioN5Config(
            budget_ref="budget://native-n5-context-fixture",
            horizon=HorizonSpec(start=0, end=0),
        ),
        "limitations": (
            "scenario_only",
            "real_profile_not_established",
            "real_time_not_established",
            "grounding_not_established",
            "s8_blocked",
            "n9_not_admitted",
        ),
    }
    draft = CandidateSimulationScenarioProfile.model_construct(
        **profile_values, content_hash="sha256:" + "0" * 64
    )
    profile = CandidateSimulationScenarioProfile.model_validate(
        {
            **profile_values,
            "content_hash": gy_content_hash(
                draft.model_dump(mode="json", exclude={"content_hash"})
            ),
        }
    )
    handoff = CandidateSimulationContextHandoff(
        context=context,
        context_job_ref=ArtifactRef(
            artifact_id=ArtifactID.from_sha256_hex("a" * 64),
            kind="runtime.quality.cycle_substrate_context_job",
            media_type="application/json",
            manifest_profile_sha256="sha256:" + "b" * 64,
        ),
        profile=profile,
        profile_config_ref=candidate_simulation_profile_ref(profile),
        job_id="native-context-fixture-job",
        run_id="native-context-fixture-run",
        tenant_id="native-context-fixture-tenant",
        cell_id="native-context-fixture-cell",
    )
    store = FileSystemCAS(
        tmp_path / f"{domain}-native-context-cas",
        tenant_id=handoff.tenant_id,
        cell_id=handoff.cell_id,
        ownership_enforced=True,
    )
    return context, handoff, store


def _bound_candidate_port(
    tmp_path: Path, prepared: PreparedJointSimulationConfiguration
) -> tuple[
    JointSimulationPort,
    CycleSubstrateContext,
    CandidateSimulationContextHandoff,
    FileSystemCAS,
]:
    """Return a real port bound to the existing typed context fixture."""
    context, handoff, store = _candidate_context_fixture(tmp_path)
    port = JointSimulationPort(_prepared_n5_configuration=prepared)
    port.bind_candidate_context_once(
        context=context,
        handoff=handoff,
        artifact_store=store,
        currentness_resolver=lambda: True,
    )
    return port, context, handoff, store


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


def test_explicit_policy_conflicts_and_matching_prepared_port_are_handled() -> None:
    prepared = prepare_joint_simulation_configuration()
    with pytest.raises(ValueError, match=r"^n5_prepared_policy_conflict$"):
        JointSimulationHorizonController(
            policy=JointSimulationControllerPolicy(), _prepared_configuration=prepared
        )
    controller = JointSimulationHorizonController(_prepared_configuration=prepared)
    with pytest.raises(ValueError, match=r"^n5_prepared_controller_conflict$"):
        JointSimulationPort(controller=controller, _prepared_n5_configuration=prepared)
    port = JointSimulationPort(_prepared_n5_configuration=prepared)
    generation = GenerationCycleController(
        simulation_port=port, _prepared_n5_configuration=prepared
    )
    assert generation._simulation_port is port
    assert generation._simulation_port._controller is port._controller
    _assert_consumes_exact_configuration(port._controller, prepared)

    changed_settings = _changed_valid_field(prepared.runtime_settings, "shrink_world_credal_state")
    assert changed_settings is not None
    mismatched = prepared.model_copy(update={"runtime_settings": changed_settings})
    with pytest.raises(ValueError, match=r"^n5_prepared_configuration_not_consumed$"):
        GenerationCycleController(simulation_port=port, _prepared_n5_configuration=mismatched)


def test_candidate_port_binds_validated_handoff_once_and_generation_reuses_it(
    tmp_path: Path,
) -> None:
    """A matching native port is retained through context binding and construction."""
    prepared = prepare_joint_simulation_configuration()
    port, context, handoff, store = _bound_candidate_port(tmp_path, prepared)
    generation = GenerationCycleController(
        simulation_port=port,
        _prepared_n5_configuration=prepared,
        artifact_store=store,
        cycle_substrate_context=context,
        candidate_simulation_handoff=handoff,
        candidate_simulation_currentness_resolver=lambda: True,
        authority_scope="contract_testing",
    )

    assert generation._simulation_port is port
    assert port._controller is generation._simulation_port._controller
    assert port._candidate_simulation_handoff == handoff
    assert port._cycle_substrate_context == context
    assert port._artifact_store is store
    assert port._candidate_context_bound_once is True
    _assert_consumes_exact_configuration(port._controller, prepared)


def test_candidate_port_context_binding_refuses_stale_or_mismatched_handoff(
    tmp_path: Path,
) -> None:
    prepared = prepare_joint_simulation_configuration()
    port = JointSimulationPort(_prepared_n5_configuration=prepared)
    context, handoff, store = _candidate_context_fixture(tmp_path)
    other_context, other_handoff, _other_store = _candidate_context_fixture(
        tmp_path, domain="economics"
    )
    with pytest.raises(ValueError, match=r"^candidate_n5_native_context_handoff_mismatch$"):
        port.bind_candidate_context_once(
            context=context,
            handoff=other_handoff,
            artifact_store=store,
            currentness_resolver=lambda: True,
        )
    assert port._candidate_context_bound_once is False
    with pytest.raises(
        ValueError, match=r"^candidate_n5_native_context_currentness_not_established$"
    ):
        port.bind_candidate_context_once(
            context=context,
            handoff=handoff,
            artifact_store=store,
            currentness_resolver=lambda: False,
        )
    assert port._candidate_context_bound_once is False
    port.bind_candidate_context_once(
        context=context,
        handoff=handoff,
        artifact_store=store,
        currentness_resolver=lambda: True,
    )
    with pytest.raises(ValueError, match=r"^candidate_n5_native_context_already_bound_or_used$"):
        port.bind_candidate_context_once(
            context=other_context,
            handoff=other_handoff,
            artifact_store=store,
            currentness_resolver=lambda: True,
        )


def test_candidate_port_refuses_context_binding_after_real_port_entry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The native port becomes single-bind before any producer work is attempted."""
    prepared = prepare_joint_simulation_configuration()
    port = JointSimulationPort(_prepared_n5_configuration=prepared)

    def stop_before_n5(**_kwargs: object) -> None:
        raise RuntimeError("stopped before N5")

    monkeypatch.setattr(port, "_produce", stop_before_n5)
    with pytest.raises(RuntimeError, match="stopped before N5"):
        port(candidate=object(), problem=object(), cycle_index=0)
    context, handoff, store = _candidate_context_fixture(tmp_path)
    with pytest.raises(ValueError, match=r"^candidate_n5_native_context_already_bound_or_used$"):
        port.bind_candidate_context_once(
            context=context,
            handoff=handoff,
            artifact_store=store,
            currentness_resolver=lambda: True,
        )


def test_generation_controller_refuses_bound_port_with_different_budget_observer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The prepared native port cannot be rebound to another invocation observer."""
    from polisyos.scientist.orchestration.engine.budget import BudgetLimit, BudgetState
    from polisyos.scientist.orchestration.engine.producer_budget import ProducerBudgetObserver
    from tests.unit.runtime.quality.test_acquisition_candidate_budget_window import _unit_window

    budget_case = _unit_window(tmp_path / "observer", monkeypatch)
    state = BudgetState(limits={"run": BudgetLimit(key="run", max_usd=1)})
    observer_args = {
        "settlement_store": budget_case.service._llm_producer_settlement_store,
        "producer_run_binding": budget_case.binding,
        "budget_state": state,
    }
    original_observer = ProducerBudgetObserver(**observer_args)
    other_observer = ProducerBudgetObserver(**observer_args)
    prepared = prepare_joint_simulation_configuration()
    controller = JointSimulationHorizonController(
        _prepared_configuration=prepared,
        producer_budget_observer=original_observer,
    )
    port = JointSimulationPort(
        controller=controller,
        producer_budget_observer=original_observer,
    )
    context, handoff, store = _candidate_context_fixture(tmp_path)
    port.bind_candidate_context_once(
        context=context,
        handoff=handoff,
        artifact_store=store,
        currentness_resolver=lambda: True,
    )

    with pytest.raises(
        ValueError, match=r"^generation_cycle_native_candidate_port_binding_mismatch$"
    ):
        GenerationCycleController(
            simulation_port=port,
            _prepared_n5_configuration=prepared,
            artifact_store=store,
            cycle_substrate_context=context,
            candidate_simulation_handoff=handoff,
            _producer_budget_reconciler=other_observer,
            authority_scope="contract_testing",
        )


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
