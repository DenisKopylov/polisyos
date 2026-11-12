"""Completion controls and the actual candidate numerical-call bridge."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from polisyos.core.artifacts import ArtifactRef
from polisyos.runtime.quality import n5_candidate_content as content


@pytest.mark.parametrize(
    ("completed", "failed", "interrupted", "expected"),
    [
        (("a", "b", "c"), (), None, "recomputed"),
        (("a", "b"), (), None, "not_established"),
        (("a", "b", "b"), (), None, "not_established"),
        (("a", "b", "c"), ("d",), None, "not_established"),
        (("a", "b", "d"), (), None, "not_established"),
        (("a", "b", "c"), (), "n5_replication_projection_failed", "not_established"),
    ],
)
def test_completion_compares_full_physical_identity_not_just_counts(
    completed: tuple[str, ...],
    failed: tuple[str, ...],
    interrupted: str | None,
    expected: str,
) -> None:
    work = tuple(
        SimpleNamespace(physical_spec_ref=key, effective_seed=7, status="completed")
        for key in completed
    ) + tuple(
        SimpleNamespace(physical_spec_ref=key, effective_seed=7, status="failed") for key in failed
    )
    result = SimpleNamespace(
        physical_work_observations=work,
        diagnostics={} if interrupted is None else {"physical_work_interruption": interrupted},
    )
    observed = content._completion(result, (("a", 7), ("b", 7), ("c", 7)))
    assert observed.status == expected
    assert observed.completed_units == tuple(sorted((key, 7) for key in completed))


def test_empty_physical_plan_cannot_claim_complete() -> None:
    result = SimpleNamespace(physical_work_observations=(), diagnostics={})
    assert content._completion(result, ()).status == "not_established"


def test_declared_completion_marker_does_not_override_missing_work() -> None:
    with pytest.raises(ValidationError, match="candidate_n5_completion_status_mismatch"):
        content.CandidateN5Completion(
            planned_units=(("a", 7), ("b", 7), ("c", 7)),
            completed_units=(("a", 7), ("b", 7)),
            status="recomputed",
        )


@pytest.mark.parametrize("value", [None, {}, SimpleNamespace(diagnostics={})])
def test_non_result_object_cannot_supply_content_observation(value: object) -> None:
    with pytest.raises(ValueError, match="candidate_n5_content_result_untyped"):
        content._candidate_result_payload(value)


def _replay_test_binding(tmp_path: Path, input_ref: ArtifactRef):
    from decimal import Decimal

    from polisyos.runtime.quality.n5_replay_appointment import N5BlindReplayLaunchSpecV2
    from polisyos.scientist.orchestration.engine.budget import BudgetLimit, BudgetState
    from polisyos.scientist.orchestration.engine.budget_ledger import (
        BudgetInvocationQuotaPolicy,
        BudgetLedgerInvocationProfile,
        BudgetLedgerProducerRunBinding,
        FileBudgetLedger,
    )
    from polisyos.scientist.orchestration.engine.budget_middleware import BudgetMiddleware
    from polisyos.scientist.orchestration.engine.producer_budget import ProducerBudgetObserver

    spec = N5BlindReplayLaunchSpecV2.model_construct(
        selected_candidate_simulation_n5_input_ref=input_ref,
        source_run_id="original-run",
        source_job_id="original-job",
        original_run_id="original-run",
        original_job_id="original-job",
        tenant_id="tenant",
        cell_id="cell",
    )
    binding = BudgetLedgerProducerRunBinding(
        run_id="replay",
        control_job_id="replay-job",
        tenant_id="tenant",
        cell_id="cell",
        profile_id="test",
    )
    policy = BudgetInvocationQuotaPolicy(allocation_id="test", total_units=1, protected_units=1)
    state = BudgetState(limits={"run": BudgetLimit(key="run", max_usd=Decimal(0))})
    budget = ProducerBudgetObserver(
        settlement_store=BudgetMiddleware(
            BudgetState(), ledger=FileBudgetLedger(tmp_path / "ledger")
        ),
        producer_run_binding=binding,
        budget_state=state,
        invocation_quota_profile=BudgetLedgerInvocationProfile.from_policy(binding, policy),
        invocation_purpose="diagnostic",
    )
    return spec, budget


def test_rebuilt_replay_scope_refuses_before_any_numerical_call(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A failed whole-plan preflight cannot reach the selected callable."""
    from polisyos.runtime.quality import acquisition_evaluation
    from polisyos.runtime.quality.joint_simulation_horizon import JointSimulationHorizonController
    from polisyos.runtime.quality.n5_replay_execution import N5ReplayPreflight

    request = object()
    input_ref = ArtifactRef(
        artifact_id="sha256:" + "a" * 64,
        kind="runtime.quality.candidate_simulation_n5_input",
        media_type="application/json",
        manifest_profile_sha256="sha256:" + "b" * 64,
    )
    rebuilt: list[dict[str, object]] = []

    def rebuild(**kwargs: object) -> object:
        rebuilt.append(kwargs)
        return request

    monkeypatch.setattr(acquisition_evaluation, "rebuild_selected_candidate_n5_request", rebuild)
    monkeypatch.setattr(content, "_native_profile", lambda *a, **k: object())
    monkeypatch.setattr(content, "capture_n5_production_image", lambda **k: object())
    monkeypatch.setattr(content, "N5ControlledCallCaptureV3", lambda **k: object())
    monkeypatch.setattr(content, "_numerical_intent", lambda *a: {})
    monkeypatch.setattr(content, "_planned_units", lambda *a: (("unit", 1),))
    monkeypatch.setattr(
        JointSimulationHorizonController,
        "_select_engine",
        lambda *a: SimpleNamespace(
            decision=SimpleNamespace(decision="selected", engine_kind="ncm_parallel_worlds")
        ),
    )
    calls: list[str] = []

    def refuse(_binding: object, scope: content.CandidateN5ContentRun) -> None:
        assert scope.planned_units == (("unit", 1),)
        calls.append("preflight")
        raise ValueError("insufficient_capacity")

    monkeypatch.setattr(N5ReplayPreflight, "check", refuse)
    spec, budget = _replay_test_binding(tmp_path, input_ref)
    controller = JointSimulationHorizonController(producer_budget_observer=budget)
    with content.observe_source_rebuilt_candidate_n5_input(
        store=object(),
        controller=controller,
        spec=spec,
        budget=budget,
    ) as (actual, scope):
        assert actual is request
        assert content.active_candidate_n5_content_run(controller) is scope
        with pytest.raises(ValueError, match="insufficient_capacity"):
            scope.prepare(object(), SimpleNamespace(method_fqn="selected"))
        with pytest.raises(ValueError, match="preflight_not_passed"):
            scope.invoke(lambda: calls.append("numerical"))
    assert calls == ["preflight"]
    assert rebuilt[0]["run_id"] == "original-run"
    assert rebuilt[0]["job_id"] == "original-job"
    assert content.active_candidate_n5_content_run(controller) is None
    with (
        pytest.raises(ValueError, match="budget_binding_mismatch"),
        content.observe_source_rebuilt_candidate_n5_input(
            store=object(), controller=JointSimulationHorizonController(), spec=spec, budget=budget
        ),
    ):
        pass


def test_actual_controller_rejects_replay_engine_change_before_dispatch(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A later PG selection cannot bypass the NCM pre-call guard."""
    from polisyos.runtime.quality import acquisition_evaluation
    from polisyos.runtime.quality.joint_simulation_horizon import JointSimulationHorizonController
    from tests.unit.runtime.quality.test_joint_simulation_horizon import _request

    request = _request()
    selected_input = ArtifactRef(
        artifact_id="sha256:" + "a" * 64,
        kind="runtime.quality.candidate_simulation_n5_input",
        media_type="application/json",
        manifest_profile_sha256="sha256:" + "b" * 64,
    )
    spec, budget = _replay_test_binding(tmp_path, selected_input)
    controller = JointSimulationHorizonController(producer_budget_observer=budget)
    ncm = SimpleNamespace(decision="selected", engine_kind="ncm_parallel_worlds")
    decision = SimpleNamespace(decision="selected", engine_kind="program_graph")
    selections = iter((ncm, decision))
    monkeypatch.setattr(
        controller, "_select_engine", lambda _request: SimpleNamespace(decision=next(selections))
    )
    monkeypatch.setattr(
        acquisition_evaluation, "rebuild_selected_candidate_n5_request", lambda **_kwargs: request
    )
    with (
        content.observe_source_rebuilt_candidate_n5_input(
            store=object(),
            controller=controller,
            spec=spec,
            budget=budget,
        ),
        pytest.raises(ValueError, match="replay_engine_capture_unsupported"),
    ):
        controller.run(request)
    # Existing ordinary producer contexts do not acquire this replay restriction.
    ordinary = content.CandidateN5ContentRun(
        controller=controller, request=request, input_ref=selected_input
    )
    ordinary.require_replay_engine(decision)
    with pytest.raises(ValueError, match="preflight_not_canonical"):
        content.CandidateN5ContentRun(
            controller=controller,
            request=request,
            input_ref=selected_input,
            replay_preflight=lambda _scope: None,
        )


def _profile_payload_read(result):
    """Count actual GY invocations without replacing the native rule callable."""
    import cProfile

    from polisyos.pdc import gy_content_hash

    profile = cProfile.Profile()
    try:
        value = profile.runcall(content._candidate_result_payload, result)
    finally:
        calls = sum(
            entry.callcount
            for entry in profile.getstats()
            if entry.code is gy_content_hash.__code__
        )
    return value, calls


@pytest.mark.parametrize(
    ("case", "expected_hash_calls", "refused"),
    [
        ("native_exact", 0, False),
        ("typed_mutation", 2, True),
        ("private_mutation", 2, True),
        ("bool_int", 2, True),
        ("signed_zero", 2, True),
        ("nan", 2, True),
        ("infinity", 2, True),
        ("mapping_proxy", 2, True),
        ("cycle", 1, True),
        ("tuple", 2, False),
        ("decimal", 2, False),
        ("volatile", 2, False),
        ("custom_rules", 2, False),
        ("mutable_rules", 2, False),
        ("custom_hash", 2, False),
    ],
)
def test_payload_exact_positive_shortcut_preserves_legacy_fallback(
    case: str, expected_hash_calls: int, refused: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Check the comparison only; the partial DTO supplies no result/receipt proof."""
    import cProfile
    from decimal import Decimal
    from types import MappingProxyType

    import polisyos.pdc as pdc
    import polisyos.pdc._impl.gy_waist as gy
    from polisyos.runtime.quality.joint_simulation_horizon import JointSimulationResult

    actual_value = {"bool_int": True, "signed_zero": -0.0}.get(case, 1)
    if case == "decimal":
        actual_value = "1.00"
    if case == "mapping_proxy":
        actual_value = {"nested": 1}
    elif case in {"cycle", "tuple"}:
        actual_value = [1]
    diagnostics = {"semantic": actual_value}
    if case == "volatile":
        diagnostics = {"generated_at": "after"}
    result = JointSimulationResult.model_construct(diagnostics=diagnostics)
    result._content_payload = deepcopy(result.model_dump(mode="json", exclude={"receipt"}))
    if case == "typed_mutation":
        result = result.model_copy(update={"diagnostics": {"semantic": 2}})
    elif case in {"private_mutation", "bool_int", "signed_zero", "nan", "decimal"}:
        result._content_payload["diagnostics"]["semantic"] = {
            "private_mutation": 2,
            "bool_int": 1,
            "signed_zero": 0.0,
            "nan": float("nan"),
            "decimal": Decimal("1.00"),
        }[case]
    elif case == "mapping_proxy":
        result._content_payload["diagnostics"]["semantic"] = MappingProxyType({"nested": 1})
    elif case == "infinity":
        result._content_payload["diagnostics"]["semantic"] = float("inf")
    elif case == "cycle":
        cycle = []
        cycle.append(cycle)
        result._content_payload["diagnostics"]["semantic"] = cycle
    elif case == "tuple":
        result._content_payload["diagnostics"]["semantic"] = (1,)
    elif case == "volatile":
        result._content_payload["diagnostics"]["generated_at"] = "before"
    elif case in {"custom_rules", "mutable_rules"}:
        rules = ("semantic",) if case == "custom_rules" else ["semantic"]
        monkeypatch.setattr(gy, "GY_CONTENT_HASH_EXCLUDED_FIELDS", rules)
    elif case == "custom_hash":
        native_hash = pdc.gy_content_hash

        def custom_hash(value):
            return native_hash(value)

        monkeypatch.setattr(pdc, "gy_content_hash", custom_hash)
    actual_hash = pdc.gy_content_hash
    profile = cProfile.Profile()
    if case == "cycle":
        with pytest.raises(RecursionError):
            profile.runcall(content._candidate_result_payload, result)
    elif refused:
        with pytest.raises(ValueError, match="candidate_n5_content_result_payload_mismatch"):
            profile.runcall(content._candidate_result_payload, result)
    else:
        assert (
            profile.runcall(content._candidate_result_payload, result)
            == result.content_bound_payload()
        )
    calls = sum(
        entry.callcount for entry in profile.getstats() if entry.code is actual_hash.__code__
    )
    assert calls == expected_hash_calls


def test_observation_wire_refuses_hostile_native_values_before_encoding() -> None:
    """The shared wire boundary rejects protocols; no receipt proof is substituted."""
    effects = []

    class HostileList(list):
        def __iter__(self):
            effects.append("iterated")
            return super().__iter__()

    cycle = []
    cycle.append(cycle)
    constructed = content.N5ExecutionContentWitnessV3.model_construct()
    for unsupported in (
        HostileList([1]),
        cycle,
        float("nan"),
        float("inf"),
        {1: "non-string key"},
        constructed,
    ):
        with pytest.raises(ValueError, match="n5_content_witness_wire_required"):
            content._read_candidate_n5_observation_wire({"witness": {"nested": unsupported}})
    assert effects == []
    for wrong_root in (None, [], constructed):
        with pytest.raises(ValueError, match="n5_content_witness_wire_required"):
            content._read_candidate_n5_observation_wire({"witness": wrong_root})


@pytest.mark.integration
def test_real_ncm_bridge_records_selected_calls_and_binds_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Exercise numerical producer; source-input authority is a separate port test."""
    from polisyos.foundry.methods.catalog.causal import ensure_causal_methods_registered
    from polisyos.foundry.methods.selection.registry import MethodRegistry
    from polisyos.runtime.quality.joint_simulation_horizon import (
        HorizonSpec,
        JointSimulationHorizonController,
        JointSimulationResult,
    )
    from tests.unit.runtime.quality.test_joint_simulation_horizon import _request

    request = _request().model_copy(update={"horizon": HorizonSpec(start=0, end=0, step=1)})
    configured_registry = MethodRegistry._create_fresh()
    controller = JointSimulationHorizonController(method_registry=configured_registry)
    singleton = MethodRegistry.get_instance()
    ensure_causal_methods_registered(singleton)
    selected_input = ArtifactRef(
        artifact_id="sha256:" + "a" * 64,
        kind="runtime.quality.candidate_simulation_n5_input",
        media_type="application/json",
        manifest_profile_sha256="sha256:" + "b" * 64,
    )
    scope = content.CandidateN5ContentRun(
        controller=controller, request=request, input_ref=selected_input
    )
    selection = controller._select_engine(request)
    assert selection.decision.decision == "selected"
    assert selection.decision.method_fqn is not None
    selected_step = configured_registry.get(selection.decision.method_fqn).pure_step
    preflight = content._native_profile(
        controller._prepared_configuration, numerical_callable=selected_step
    )
    (tmp_path / "profile-preflight.json").write_text(preflight.model_dump_json(), encoding="utf-8")
    assert preflight.profile_identity_predicate == "recomputed", preflight.reason_codes
    token = content._ACTIVE.set(scope)
    try:
        original = controller.run(request)
    finally:
        content._ACTIVE.reset(token)
    result = content.bind_candidate_n5_content_observation(original, scope=scope)
    # Keep the deciding bytes even when a later invariant fails. Reconciliation
    # of the saved native profiles needs no second physical numerical run.
    (tmp_path / "result.json").write_text(result.model_dump_json(), encoding="utf-8")
    (tmp_path / "request.json").write_text(request.model_dump_json(), encoding="utf-8")
    assert scope.profile is not None
    (tmp_path / "profile-before.json").write_text(scope.profile.model_dump_json(), encoding="utf-8")
    joint = result.trajectory_for("joint", ("income_subsidy", "balance_grant"))
    assert joint.points[-1].outcomes["firm_survival"] == pytest.approx(11.0)
    assert controller._last_n5_implementation_capture is None
    import cProfile

    witness_profile = cProfile.Profile()
    observed = witness_profile.runcall(
        content.read_candidate_n5_content_observation,
        result,
        input_ref=selected_input,
        expected_request=request,
    )
    assert (
        sum(
            entry.callcount
            for entry in witness_profile.getstats()
            if entry.code is content.N5ExecutionContentWitnessV3._content.__code__
        )
        == 1
    )
    (tmp_path / "profile-after.json").write_text(
        observed.execution_profile.model_dump_json(), encoding="utf-8"
    )
    comparison = content.reconcile_recorded_n5_profile_content(
        scope.profile, observed.execution_profile
    )
    (tmp_path / "profile-comparison.json").write_text(
        comparison.model_dump_json(), encoding="utf-8"
    )
    assert observed.witness.schema_version == "N5ExecutionContentWitness@3.0"
    assert len(observed.witness.observed_calls) == len(observed.completion.planned_units) == 3
    assert observed.completion.status == "recomputed"
    assert observed.protected_use_allowed is False
    assert observed.independent_verification == "not_established"
    assert observed.profile_stability == "recomputed", {
        "before": scope.profile.reason_codes,
        "after": observed.execution_profile.reason_codes,
        "comparison": comparison.reason_codes,
        "missing": comparison.missing_provider_identities,
        "changed": comparison.changed_provider_identities,
    }
    assert observed.source_image_stability == "recomputed"
    assert observed.execution_profile.profile_identity_predicate == "recomputed"
    _, payload_hash_calls = _profile_payload_read(result)
    assert payload_hash_calls == 0
    historical_reads = []
    actual_read = content.read_candidate_n5_content_observation

    def counted_read(*args, **kwargs):
        historical_reads.append(kwargs)
        return actual_read(*args, **kwargs)

    with monkeypatch.context() as scoped:
        scoped.setattr(content, "read_candidate_n5_content_observation", counted_read)
        identity = content.read_candidate_n5_declared_implementation(
            result,
            input_ref=selected_input,
            prepared_configuration=controller._prepared_configuration,
            expected_request=request,
        )
        assert (
            content.reconcile_candidate_n5_declared_implementation(
                result,
                input_ref=selected_input,
                prepared_configuration=controller._prepared_configuration,
                expected_request=request,
                current_n5_controller=controller,
            )
            == identity
        )
        assert len(historical_reads) == 2  # one declared read, one reconciliation read
    changed_request = request.model_copy(update={"replications": 2})
    with pytest.raises(ValueError, match="candidate_n5_content_source_plan_mismatch"):
        content.read_candidate_n5_declared_implementation(
            result,
            input_ref=selected_input,
            prepared_configuration=controller._prepared_configuration,
            expected_request=changed_request,
        )
    with pytest.raises(ValueError, match="candidate_n5_content_source_request_not_established"):
        content.read_candidate_n5_declared_implementation(
            result,
            input_ref=selected_input,
            prepared_configuration=controller._prepared_configuration,
        )
    # A producer cannot make two out of three units look complete by shortening
    # its own denominator. Rehashing the envelope still leaves the independently
    # resolved request's three-unit plan unchanged.
    short_values = observed.model_dump(mode="json", exclude={"content_hash"})
    short_units = short_values["completion"]["planned_units"][:2]
    short_values["completion"].update(
        planned_units=short_units, completed_units=deepcopy(short_units)
    )
    shortened = content.CandidateN5ContentObservation.model_validate_json(
        json.dumps(
            {**short_values, "content_hash": content.exact_n5_content_hash(short_values)},
            allow_nan=False,
        )
    )
    with pytest.raises(ValueError, match="candidate_n5_content_source_plan_mismatch"):
        content._require_resolved_request_binding(shortened, result, request)

    # Change the actual configured registry, leaving the global registry alone.
    # The same FQN/signature does not imply the same callable at execution.
    selected_method = configured_registry.get(observed.method_fqn)
    singleton_method = singleton.get(observed.method_fqn)

    class ChangedConfiguredMethod(selected_method):
        @staticmethod
        def pure_step(*args: object, **kwargs: object) -> object:
            raise AssertionError("retention must not execute the changed numerical callable")

    configured_registry.register(ChangedConfiguredMethod, override=True)
    try:
        assert singleton.get(observed.method_fqn) is singleton_method
        with pytest.raises(ValueError, match="candidate_n5_current_declared_identity_changed"):
            content.reconcile_candidate_n5_declared_implementation(
                result,
                input_ref=selected_input,
                prepared_configuration=controller._prepared_configuration,
                expected_request=request,
                current_n5_controller=controller,
            )
    finally:
        configured_registry.register(selected_method, override=True)
    # A new model instance has no producer issuance map or local-object token
    # lookup. The persisted content reader still verifies the exact joins.
    fresh = JointSimulationResult.model_validate_json(result.model_dump_json())
    assert (
        content.read_candidate_n5_content_observation(fresh, input_ref=selected_input) == observed
    )
    stale_cache = fresh.model_copy(update={"world_model_record_ref": "forged-world"})
    stale_cache._content_payload = deepcopy(result.content_bound_payload())
    with pytest.raises(ValueError, match="candidate_n5_content_result_payload_mismatch"):
        content.read_candidate_n5_content_observation(stale_cache, input_ref=selected_input)
    foreign = selected_input.model_copy(update={"manifest_profile_sha256": "sha256:" + "c" * 64})
    with pytest.raises(ValueError, match="candidate_n5_content_input_mismatch"):
        content.read_candidate_n5_content_observation(fresh, input_ref=foreign)
    # Removal keeps the ordinary numerical receipt, but cannot supply identity.
    with pytest.raises(ValueError, match="candidate_n5_content_observation_missing"):
        content.read_candidate_n5_content_observation(original, input_ref=selected_input)

    # Seal must reread the actual consumer aliases, even if its prepared object
    # remains unchanged. No numerical call or result is repeated for this check.
    original_settings = controller._settings
    controller._settings = original_settings.model_copy(
        update={"fabricate_interaction_terms": not original_settings.fabricate_interaction_terms}
    )
    try:
        changed = content.bind_candidate_n5_content_observation(original, scope=scope)
        changed_observation = content.read_candidate_n5_content_observation(
            changed, input_ref=selected_input, expected_request=request
        )
        assert changed_observation.profile_stability == "not_established"
        with pytest.raises(ValueError, match="candidate_n5_declared_identity_not_established"):
            content.read_candidate_n5_declared_implementation(
                changed,
                input_ref=selected_input,
                prepared_configuration=controller._prepared_configuration,
                expected_request=request,
            )
    finally:
        controller._settings = original_settings
