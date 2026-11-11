"""Registered representation support remains distinct from scientific evidence."""

from __future__ import annotations

from dataclasses import replace

import pytest

from polisyos.foundry.methods._internal.executable_identity import _signature_matches
from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
from polisyos.foundry.methods.catalog.causal.bounds_engine import BoundsEngineMethod
from polisyos.foundry.methods.components.representation import (
    resolved_execution_representation_modes,
)
from polisyos.foundry.methods.selection.cache import (
    _complete_signature_payload,
    _signature_from_payload,
)
from polisyos.foundry.methods.selection.registry import registry_scope
from polisyos.foundry.methods.selection.requirements import (
    select_method_candidates_for_requirements,
)
from polisyos.foundry.validation import method_quality
from polisyos.ir.observation.contract_compilers import BoundsEstimationInput
from polisyos.ir.observation.contracts import IdentificationMode
from polisyos.method_requirement import MethodValidityRequirementSpec


def _requirement(mode=IdentificationMode.BOUNDS_ONLY, *, scientific=False):
    return MethodValidityRequirementSpec(
        requirement_id="representation-need",
        run_id="representation-run",
        claim_id="effect",
        identification_class="bounds",
        method_expectations=["causal_effect_estimation"],
        required_method_families=["causal_effect_estimation"],
        facet_refs=["declared-mode"],
        source_precondition_refs=["policy-spec-mode"],
        requires_runtime_assumption_gates=scientific,
        requires_method_output=False,
        requires_uncertainty_envelope=False,
        requires_limitation_refs=False,
        assumption_validation_needs=[{"assumption_id": "identification_assumptions"}]
        if scientific
        else [],
        metadata={
            "explicit_identification_mode_facets": [
                {
                    "facet_ref": "declared-mode",
                    "identification_mode": mode.value,
                }
            ]
        },
    )


@pytest.fixture
def bound_result():
    with registry_scope() as registry:
        registry.register(BoundsEngineMethod)
        result = MethodDispatcher().dispatch(
            method_class=registry.get(BoundsEngineMethod.signature.fqn),
            signature=BoundsEngineMethod.signature,
            state=BoundsEstimationInput(outcome=[0.1, 0.3, 0.8, 0.9], treatment=[0, 0, 1, 1]),
            params={"use_auto_bounds": False},
            seed=3,
        )
        yield registry, result


def _candidate(result):
    return method_quality.method_candidate_from_execution_result(result)


def _select(candidate, requirement=None):
    return select_method_candidates_for_requirements(
        candidate_methods=[candidate], method_requirements=[requirement or _requirement()]
    )


def test_registered_bounds_call_supports_only_bounds_representation(bound_result):
    _registry, result = bound_result
    assert resolved_execution_representation_modes(result) == ("bounds_only",)
    candidate = _candidate(result)
    assert candidate["method_id"] == BoundsEngineMethod.signature.fqn
    assert _select(candidate)["status"] == "pass"
    summary = candidate["representation_compatibility"][0]
    assert summary["scope"] == "representation_compatibility_only"
    assert summary["identification_established"] is False
    for mode in IdentificationMode:
        if mode is not IdentificationMode.BOUNDS_ONLY:
            assert _select(candidate, _requirement(mode))["status"] == "fail"


def test_representation_support_does_not_satisfy_instance_identification(bound_result):
    _registry, result = bound_result
    report = _select(_candidate(result), _requirement(scientific=True))
    assert report["status"] == "fail"
    assert report["rejected_methods"][0]["reason_code"] == "runtime_assumption_validation_missing"
    scientific_report = method_quality.build_foundry_method_report_from_execution_outputs(
        method_outputs=[{"execution_result": result}],
        method_requirements=[_requirement()],
    )
    assert scientific_report["status"] == "fail"
    assert any(
        issue["code"] == "method_assumptions_missing" for issue in scientific_report["issues"]
    )
    assert all("execution_result" not in row for row in scientific_report["candidate_methods"])


@pytest.mark.parametrize(
    "mutation", ["remove_profile", "remove_registry_profile", "replace_callable", "replace_code"]
)
def test_retained_support_refuses_changed_registered_implementation(
    bound_result, monkeypatch, mutation
):
    _registry, result = bound_result
    original = BoundsEngineMethod.pure_step
    if mutation == "remove_profile":
        monkeypatch.setattr(
            BoundsEngineMethod,
            "signature",
            replace(BoundsEngineMethod.signature, representation_profiles=()),
        )
    elif mutation == "remove_registry_profile":
        entry = _registry.get_entry(BoundsEngineMethod.signature.fqn)
        entry.signature = replace(entry.signature, representation_profiles=())
    elif mutation == "replace_callable":
        monkeypatch.setattr(
            BoundsEngineMethod,
            "pure_step",
            staticmethod(lambda state, params: original(state, params)),
        )
    else:
        monkeypatch.setattr(original, "__code__", (lambda state, params: {}).__code__)
    assert resolved_execution_representation_modes(result) == ()
    assert _select(_candidate(result))["status"] == "fail"


def test_foreign_output_or_expectation_dictionary_cannot_borrow_support(bound_result):
    _registry, result = bound_result
    foreign = replace(result, output=dict(result.output))
    assert resolved_execution_representation_modes(foreign) == ()
    assert _select(_candidate(foreign))["status"] == "fail"
    declared = {
        "method_id": BoundsEngineMethod.signature.fqn,
        "method_family": "causal_effect_estimation",
        "method_expectations": ["causal_effect_estimation", "bounds_only"],
    }
    assert _select(declared)["status"] == "fail"


def test_profiles_round_trip_and_change_semantics_without_abi():
    signature = BoundsEngineMethod.signature
    removed = replace(signature, representation_profiles=())
    assert removed.abi_digest() == signature.abi_digest()
    assert removed.representation_digest() != signature.representation_digest()
    payload = _complete_signature_payload(signature)
    assert _signature_from_payload(payload) == signature
    with pytest.raises(ValueError, match="cache_signature_representation_profiles_missing"):
        _signature_from_payload(
            {key: value for key, value in payload.items() if key != "representation_profiles"}
        )
    assert not _signature_matches(type("Removed", (), {"signature": removed}), signature)


def test_lazy_admission_refuses_removed_profile_with_same_abi(monkeypatch):
    signature = BoundsEngineMethod.signature
    with registry_scope() as registry:
        registry.register_lazy(
            signature,
            BoundsEngineMethod.metadata,
            lambda: BoundsEngineMethod,
            import_target=(BoundsEngineMethod.__module__, BoundsEngineMethod.__qualname__),
        )
        monkeypatch.setattr(
            BoundsEngineMethod, "signature", replace(signature, representation_profiles=())
        )
        with pytest.raises(ValueError, match="lazy_method_signature_mismatch"):
            registry.get(signature.fqn)


def test_persisted_registry_retains_profile_semantics_and_detects_removal(tmp_path, monkeypatch):
    from polisyos.foundry.methods.selection.cache import RegistryPersistenceLayer
    from polisyos.foundry.methods.selection.registry import MethodRegistry

    signature = BoundsEngineMethod.signature
    registry = MethodRegistry._create_fresh()
    registry.register(BoundsEngineMethod)
    layer = RegistryPersistenceLayer(tmp_path / "profiles.sqlite")
    assert layer.snapshot_from(registry) == 1
    restored = MethodRegistry._create_fresh()
    assert layer.restore_into(restored) == 1
    assert (
        restored.get_signature(signature.fqn).representation_profiles
        == signature.representation_profiles
    )
    assert layer.is_cache_valid(registry)
    monkeypatch.setattr(
        BoundsEngineMethod, "signature", replace(signature, representation_profiles=())
    )
    with pytest.raises(ValueError, match="lazy_method_signature_mismatch"):
        restored.get(signature.fqn)


def test_profile_preconditions_are_checked_before_compatibility_projection():
    from polisyos.foundry.methods.components.representation import (
        _applicable_representation_bindings,
    )

    with registry_scope() as registry:
        registry.register(BoundsEngineMethod)
        signature = BoundsEngineMethod.signature
        params = {item.name: item.default for item in signature.parameters}
        state = BoundsEstimationInput(outcome=[0.1, 0.9], treatment=[0, 1])

        def begin(input_state, input_params):
            return _applicable_representation_bindings(
                method_class=BoundsEngineMethod,
                signature=signature,
                operation=BoundsEngineMethod.pure_step,
                postprocessor=None,
                state=input_state,
                params=input_params,
            )

        assert begin(state, {**params, "use_auto_bounds": False})
        assert not begin(state, params)
        assert not begin(
            BoundsEstimationInput(outcome=[0.1, 0.9], treatment=[0.3, 1]),
            {**params, "use_auto_bounds": False},
        )
        assert not begin(
            BoundsEstimationInput(outcome=[0.1, 1.1], treatment=[0, 1]),
            {**params, "use_auto_bounds": False},
        )
        entry = registry.get_entry(signature.fqn)
        entry.signature = replace(signature, representation_profiles=())
        assert not begin(state, {**params, "use_auto_bounds": False})


def test_registry_snapshot_binding_includes_representation_semantics():
    from polisyos.foundry.extensions.registry import _method_registry_snapshot_binding_sha256

    with registry_scope() as registry:
        registry.register(BoundsEngineMethod)
        before = _method_registry_snapshot_binding_sha256(registry.snapshot())
        entry = registry.get_entry(BoundsEngineMethod.signature.fqn)
        entry.signature = replace(entry.signature, representation_profiles=())
        assert entry.signature.abi_digest() == BoundsEngineMethod.signature.abi_digest()
        assert _method_registry_snapshot_binding_sha256(registry.snapshot()) != before


def test_public_selector_and_builder_discard_foreign_outer_payload(bound_result):
    _registry, result = bound_result
    foreign = {
        "execution_result": result,
        "method_id": "causal.foreign.runtime",
        "method_family": "foreign",
        "method_result": {"point_estimate": 999},
        "input_refs": {"foreign": "sha256:" + "f" * 64},
        "runtime_assumption_gates": [
            {"assumption": "identification_assumptions", "status": "pass"}
        ],
    }
    selected = _select(foreign)
    assert selected["status"] == "pass"
    assert selected["selected_methods"][0]["method_id"] == BoundsEngineMethod.signature.fqn
    assert selected["selected_methods"][0]["input_refs"] == {}
    assert selected["selected_methods"][0]["runtime_assumption_gates"] == []
    assert _select(foreign, _requirement(scientific=True))["status"] == "fail"
    report = method_quality.build_foundry_method_report_from_execution_outputs(
        method_outputs=[foreign],
        method_requirements=[_requirement(scientific=True)],
    )
    assert report["method_requirement_statuses"] == {"representation-need": "missing"}
    assert report["candidate_methods"][0]["result_summary"] == {}


def test_observed_capsule_cannot_be_constructed_replaced_or_transplanted(bound_result):
    from copy import deepcopy

    from polisyos.foundry.methods.components.representation import MethodRepresentationCompatibility
    from polisyos.ir.analytics.partial_identification import BoundsBundle

    _registry, result = bound_result
    projection = result.representation_compatibility[0]
    fake = deepcopy(result.output)
    fake["bounds_report"]["lower_bound"] = -0.2
    fake["bounds_report"]["upper_bound"] = 0.2
    native = BoundsBundle.model_validate(fake["bounds_report"])
    with pytest.raises(TypeError):
        MethodRepresentationCompatibility()
    with pytest.raises(TypeError):
        replace(projection, raw_output=fake, native_output=native)
    foreign = replace(result, output=fake)
    assert resolved_execution_representation_modes(foreign) == ()
    assert _select(_candidate(foreign))["status"] == "fail"
    report = method_quality.build_foundry_method_report_from_execution_outputs(
        method_outputs=[foreign],
        method_requirements=[_requirement()],
    )
    assert report["method_requirement_statuses"] == {"representation-need": "missing"}


@pytest.mark.parametrize("change", ["native_metadata", "outer_evidence"])
def test_observed_output_mutation_cannot_supply_new_evidence(bound_result, change):
    _registry, result = bound_result
    if change == "native_metadata":
        result.output["bounds_report"]["metadata"]["borrowed"] = "foreign"
    else:
        result.output["method_evidence"] = {
            "runtime_assumption_gates": [
                {"assumption": "identification_assumptions", "status": "pass"}
            ]
        }
    assert resolved_execution_representation_modes(result) == ()
    assert _select(_candidate(result))["status"] == "fail"


def test_shallow_native_model_mutation_invalidates_observed_bytes(bound_result):
    from polisyos.ir.analytics.partial_identification import BoundsBundle

    _registry, result = bound_result
    native = BoundsBundle.model_validate(result.output["bounds_report"])
    result.output["bounds_report"] = native
    assert resolved_execution_representation_modes(result) == ("bounds_only",)
    native.warnings.append("post-call mutation")
    assert resolved_execution_representation_modes(result) == ()
    assert _select(_candidate(result))["status"] == "fail"


@pytest.mark.parametrize("invalid_input", ["mutated_schema", "constructed_metadata"])
def test_invalid_native_input_instance_cannot_gain_representation_support(invalid_input):
    with registry_scope() as registry:
        registry.register(BoundsEngineMethod)
        state = BoundsEstimationInput(outcome=[0.1, 0.3, 0.8, 0.9], treatment=[0, 0, 1, 1])
        if invalid_input == "mutated_schema":
            state.schema_version = "invalid"
        else:
            state = BoundsEstimationInput.model_construct(
                outcome=state.outcome,
                treatment=state.treatment,
                metadata="invalid",
            )
        result = MethodDispatcher().dispatch(
            method_class=BoundsEngineMethod,
            signature=BoundsEngineMethod.signature,
            state=state,
            params={"use_auto_bounds": False},
            seed=3,
        )
        assert "bounds_report" in result.output
        assert resolved_execution_representation_modes(result) == ()
        assert _select(_candidate(result))["status"] == "fail"


def test_generic_emitter_persistence_and_readback_keep_representation_limits(
    bound_result, tmp_path
):
    from polisyos.core.artifacts import load_core_json_artifact
    from polisyos.core.artifacts.store import FileSystemCAS

    _registry, result = bound_result
    emitted = method_quality.build_foundry_method_report_from_execution_outputs(
        method_outputs=[result],
        method_requirements=[_requirement()],
    )
    expected = emitted["runtime_authority_envelope"]
    assert expected["authority_role"] == "historical_audit_projection"
    assert "method_validity" in expected["may_not_use_for"]
    # Persistence itself reconstructs the restriction from the disclosure,
    # independently of a redundant marker or a conflicting broad envelope.
    stripped = {
        key: value for key, value in emitted.items() if key != "representation_projection_scope"
    }
    stripped["runtime_authority_envelope"] = {"authority_role": "producer_authority"}
    store = FileSystemCAS(tmp_path)
    ref = method_quality.persist_foundry_method_report(store, stripped)
    saved = load_core_json_artifact(FileSystemCAS(tmp_path), ref)
    assert saved["runtime_authority_envelope"] == expected
    assert saved["representation_projection_scope"] == "historical_compatibility_audit_only"
    normalized = method_quality.normalize_foundry_method_report(saved)
    assert normalized["runtime_authority_envelope"] == expected
    assert normalized["method_requirement_statuses"] == {"representation-need": "missing"}
