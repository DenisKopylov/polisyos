"""Retain actionable, bounded diagnostics without granting N5 reuse authority."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from types import CodeType, FrameType, SimpleNamespace
from typing import Any

import pytest

from polisyos.core.artifacts import ArtifactRef
from polisyos.runtime.quality import confidence_ledger as ledger
from polisyos.runtime.quality import n5_execution_basis as basis


def test_controller_observer_captures_first_frame_once_per_code_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    receiver = object()
    later_receiver = object()
    observer = basis._ControllerExecutionObserver((receiver,))
    executed_code_type = basis._ExecutedCode
    constructions: list[object] = []

    def construct_executed_code(
        module: str,
        code: CodeType,
        namespace: dict[str, Any],
        frame: FrameType,
        receiver_roots: tuple[tuple[str, object], ...] = (),
    ) -> object:
        constructions.append(None)
        return executed_code_type(module, code, namespace, frame, receiver_roots)

    monkeypatch.setattr(basis, "_ExecutedCode", construct_executed_code)

    def observe_first_code(receiver_value: object) -> FrameType:
        frame = sys._getframe()
        observer._observe(frame, "call", None)
        return frame

    def observe_second_code(receiver_value: object) -> FrameType:
        frame = sys._getframe()
        observer._observe(frame, "call", None)
        return frame

    first_frame = observe_first_code(receiver)
    repeated_frame = observe_first_code(later_receiver)

    assert first_frame is not repeated_frame
    assert len(observer.codes) == 1
    assert len(constructions) == 1
    first_observation = next(iter(observer.codes.values()))
    assert first_observation.frame is first_frame
    assert first_observation.receiver_roots == (("receiver_value", receiver),)

    observe_second_code(later_receiver)

    assert len(observer.codes) == 2
    assert len(constructions) == 2


def _missing_selected_module() -> dict[str, Any]:
    """Exercise the actual source reader's typed error, without a numerical run."""
    ledger._loaded_code_manifest_body(
        Path(__file__).parent,
        (("polisyos._n5_missing_selected_module", "not_read.py"),),
    )
    raise AssertionError("the missing selected module must be refused")


def test_capture_preserves_actual_source_error_target_and_throw_site(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    capture = object.__new__(basis.N5ImplementationCapture)
    capture._supported = True
    capture._admission = object()
    capture._observer = SimpleNamespace(active=True, _observe=sys.getprofile(), suspended=False)
    capture._reasons = []
    monkeypatch.setattr(capture, "_current_implementation", _missing_selected_module)

    assert capture.__enter__() is capture
    assert capture._observer.suspended is False
    assert capture._reasons[0] == "canonical_loaded_runtime_mismatch"
    assert "n5_implementation_failure_target:polisyos._n5_missing_selected_module" in (
        capture._reasons
    )
    assert any(
        reason.startswith(
            "n5_implementation_failure_site:"
            "polisyos.runtime.quality.confidence_ledger._loaded_code_manifest_body:"
        )
        for reason in capture._reasons
    )
    assert not any(str(Path(__file__).parent) in reason for reason in capture._reasons)


def test_sealed_failed_capture_keeps_diagnostic_and_never_issues_reuse(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_ref = ArtifactRef(
        artifact_id="sha256:" + "a" * 64,
        kind="n5_input",
        media_type="application/json",
    )
    capture = object.__new__(basis.N5ImplementationCapture)
    capture._admission = SimpleNamespace(input_ref=input_ref)
    capture._sealed = None
    capture._reasons = []
    capture._observer = SimpleNamespace(completed=True, reason=None)
    capture._entry = _missing_selected_module
    capture._codes = {0: SimpleNamespace(code=_missing_selected_module.__code__)}
    capture._trajectory_hash = basis.exact_n5_content_hash([])
    capture._trajectory_bytes = basis.exact_n5_content_bytes([])
    capture._request = {}
    capture._request_bytes = basis.exact_n5_content_bytes({})
    capture.request_hash = basis.exact_n5_content_hash({})
    capture._controller = object()
    capture._configuration_start = None
    monkeypatch.setattr(capture, "_current_implementation", _missing_selected_module)
    result = SimpleNamespace(trajectories=(), content_bound_payload=lambda: {"result": []})

    witness = capture.seal(input_ref=input_ref, result=result)

    assert witness.predicate_provenance == "not_established"
    assert "canonical_loaded_runtime_mismatch" in witness.reason_codes
    assert "n5_implementation_failure_target:polisyos._n5_missing_selected_module" in (
        witness.reason_codes
    )
    assert witness.implementation == {}
    assert witness.content_hash not in basis._ISSUED
    assert (
        basis.N5ExecutionImplementationWitness.model_validate_json(witness.model_dump_json())
        == witness
    )


@pytest.mark.parametrize(
    "detail",
    [
        "source invalid: /private/secret.py",
        "source invalid: https://example.invalid/token",
        "source invalid: polisyos.module\nsecret",
        "source invalid: polisyos.module?token=secret",
        "source invalid: " + "polisyos." + "x" * 512,
        "arbitrary credential or payload",
    ],
)
def test_unsafe_error_detail_is_not_persisted(detail: str) -> None:
    error = ledger.ConfidenceLedgerError("canonical_loaded_runtime_mismatch", detail)
    assert basis._implementation_failure_reasons(error) == ("canonical_loaded_runtime_mismatch",)


def test_detail_prefix_is_discarded_and_noncanonical_error_is_not_enriched() -> None:
    error = ledger.ConfidenceLedgerError(
        "canonical_loaded_runtime_mismatch", "private payload: polisyos.runtime.selected_slot"
    )
    assert basis._implementation_failure_reasons(error) == (
        "canonical_loaded_runtime_mismatch",
        "n5_implementation_failure_target:polisyos.runtime.selected_slot",
    )
    assert basis._implementation_failure_reasons(ValueError("ordinary refusal")) == (
        "ordinary refusal",
    )


def _historical_n5_result(
    input_ref: ArtifactRef,
    *,
    consumed_configuration: dict[str, Any] | None,
    predicate_provenance: str = "not_established",
    reason_codes: tuple[str, ...] = ("canonical_loaded_runtime_mismatch",),
) -> tuple[SimpleNamespace, basis.N5ExecutionImplementationWitness]:
    """Build an owner-reader compatible result and its content-bound witness."""
    from polisyos.core.artifacts import artifact_ref_identity_key
    from polisyos.runtime.quality.joint_simulation_horizon import (
        build_content_bound_simulation_receipt,
    )

    trajectory = {"run_level": "individual", "outcome": 0.5}
    without_witness = {
        "schema_version": "policyos.runtime.joint_simulation_horizon.v5",
        "trajectories": [trajectory],
        "diagnostics": {},
    }
    payload: dict[str, Any] = {
        "schema_version": "N5ExecutionImplementationWitness@1.0",
        "authority_purpose": "candidate_evaluation_retention_only",
        "comparison_scope": "same_live_process_loaded_implementation",
        "process_session": "historical-test-session",
        "input_ref_identity": artifact_ref_identity_key(input_ref),
        "request_content_hash": "sha256:" + "b" * 64,
        "result_without_witness_hash": basis.exact_n5_content_hash(without_witness),
        "trajectory_hash": basis.exact_n5_content_hash([trajectory]),
        "implementation": {},
        "consumed_configuration_values": consumed_configuration,
        "predicate_provenance": predicate_provenance,
        "reason_codes": reason_codes,
    }
    persisted = json.loads(json.dumps(payload))
    witness = basis.N5ExecutionImplementationWitness.model_validate(
        {
            **persisted,
            "content_hash": basis.exact_n5_content_hash(persisted),
        }
    )
    diagnostics = {basis._DIAGNOSTIC_KEY: witness.model_dump(mode="json")}
    result_payload = {**without_witness, "diagnostics": diagnostics}
    receipt = build_content_bound_simulation_receipt(
        engine_kind="ncm_parallel_worlds",
        payload=result_payload,
        diagnostics=diagnostics,
    )
    result = SimpleNamespace(
        receipt=receipt,
        diagnostics=diagnostics,
        trajectories=(SimpleNamespace(model_dump=lambda mode: dict(trajectory)),),
        content_bound_payload=lambda: result_payload,
    )
    return result, witness


def test_candidate_historical_configuration_matches_with_unknown_implementation() -> None:
    from polisyos.core.artifacts import ArtifactRef
    from polisyos.runtime.quality.joint_simulation_horizon import (
        prepare_joint_simulation_configuration,
    )

    prepared = prepare_joint_simulation_configuration()
    input_ref = ArtifactRef(
        artifact_id="sha256:" + "a" * 64,
        kind="runtime.quality.candidate_simulation_n5_input",
        media_type="application/json",
    )
    result, expected = _historical_n5_result(
        input_ref,
        consumed_configuration=basis._exact_native_content(prepared),
    )
    witness = basis.read_n5_execution_implementation_witness(result, input_ref=input_ref)

    assert witness.predicate_provenance == "not_established"
    assert witness == expected
    assert basis._candidate_n5_historical_configuration_matches(witness, prepared)
    assert basis._candidate_n5_experiment_observation_supported(witness, prepared)


@pytest.mark.parametrize("observation", [None, {}, {"unrelated": True}])
def test_candidate_historical_configuration_requires_exact_descriptor(
    observation: dict[str, Any] | None,
) -> None:
    from polisyos.core.artifacts import ArtifactRef
    from polisyos.runtime.quality.joint_simulation_horizon import (
        prepare_joint_simulation_configuration,
    )

    prepared = prepare_joint_simulation_configuration()
    input_ref = ArtifactRef(
        artifact_id="sha256:" + "a" * 64,
        kind="runtime.quality.candidate_simulation_n5_input",
        media_type="application/json",
    )
    result, _ = _historical_n5_result(input_ref, consumed_configuration=observation)
    witness = basis.read_n5_execution_implementation_witness(result, input_ref=input_ref)

    assert not basis._candidate_n5_historical_configuration_matches(witness, prepared)
    assert not basis._candidate_n5_experiment_observation_supported(witness, prepared)


@pytest.mark.parametrize(
    "reason",
    [
        "n5_execution_observer_conflict",
        "n5_execution_observer_interrupted",
        "n5_execution_observer_completion_not_established",
        "n5_selected_implementation_or_input_unsupported",
        "n5_selected_entry_not_observed",
        "n5_observed_trajectory_mismatch",
        "n5_input_changed_during_execution",
        "n5_implementation_changed_during_execution",
        "n5_consumed_configuration_not_established",
    ],
)
def test_candidate_experiment_rejects_physical_observation_failures_even_when_snapshots_match(
    reason: str,
) -> None:
    from polisyos.core.artifacts import ArtifactRef
    from polisyos.runtime.quality.joint_simulation_horizon import (
        prepare_joint_simulation_configuration,
    )

    prepared = prepare_joint_simulation_configuration()
    input_ref = ArtifactRef(
        artifact_id="sha256:" + "a" * 64,
        kind="runtime.quality.candidate_simulation_n5_input",
        media_type="application/json",
    )
    result, _ = _historical_n5_result(
        input_ref,
        consumed_configuration=basis._exact_native_content(prepared),
        reason_codes=("canonical_loaded_runtime_mismatch", reason),
    )
    witness = basis.read_n5_execution_implementation_witness(result, input_ref=input_ref)

    assert basis._candidate_n5_historical_configuration_matches(witness, prepared)
    assert not basis._candidate_n5_experiment_observation_supported(witness, prepared)


def test_candidate_experiment_accepts_only_bounded_source_failure_diagnostics() -> None:
    from polisyos.core.artifacts import ArtifactRef
    from polisyos.runtime.quality.joint_simulation_horizon import (
        prepare_joint_simulation_configuration,
    )

    prepared = prepare_joint_simulation_configuration()
    input_ref = ArtifactRef(
        artifact_id="sha256:" + "a" * 64,
        kind="runtime.quality.candidate_simulation_n5_input",
        media_type="application/json",
    )
    config = basis._exact_native_content(prepared)
    allowed, _ = _historical_n5_result(
        input_ref,
        consumed_configuration=config,
        reason_codes=(
            "canonical_loaded_runtime_mismatch",
            "n5_implementation_failure_site:polisyos.runtime.quality.n5_execution_basis._current_implementation:123",
            "n5_implementation_failure_target:polisyos.runtime.quality.confidence_ledger",
        ),
    )
    unsupported, _ = _historical_n5_result(
        input_ref,
        consumed_configuration=config,
        reason_codes=(
            "canonical_loaded_runtime_mismatch",
            "n5_implementation_failure_site:external.module.function:123",
        ),
    )

    assert basis._candidate_n5_experiment_observation_supported(
        basis.read_n5_execution_implementation_witness(allowed, input_ref=input_ref), prepared
    )
    assert not basis._candidate_n5_experiment_observation_supported(
        basis.read_n5_execution_implementation_witness(unsupported, input_ref=input_ref), prepared
    )


@pytest.fixture
def content_image(tmp_path: Path):
    """Use a whole tiny production image, including an unimported module."""
    root = tmp_path / "product"
    package = root / "src" / "polisyos"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "unimported.py").write_text("VALUE = 1\n", encoding="utf-8")
    (root / "uv.lock").write_text("version = 1\n", encoding="utf-8")
    image = basis.capture_n5_production_image(
        root=root, admitted_profile={"profile": "controlled-unit", "device": "cpu"}
    )
    return root, image


def _content_capture(image, *, effective_inputs=None):
    return basis.N5ControlledCallCapture(
        effective_inputs={"numerical_input": 0} if effective_inputs is None else effective_inputs,
        production_image=image,
    )


def _closed_value(value):
    def operation(offset=0):
        return value + offset

    return operation


def test_v2_controlled_call_distinguishes_five_same_code_closures(content_image) -> None:
    _root, image = content_image
    capture = _content_capture(image)
    functions = [_closed_value(value) for value in range(1, 6)]
    assert all(function.__code__ is functions[0].__code__ for function in functions)

    assert [capture.observe_numerical_call(function) for function in functions] == [1, 2, 3, 4, 5]
    witness = capture.seal()

    assert witness.schema_version == "N5ExecutionContentWitness@2.0"
    assert witness.authority_purpose == "candidate_observation_only"
    assert len(witness.observed_calls) == 5
    assert len({call.callable_content_hash for call in witness.observed_calls}) == 5
    assert len({call.numerical_content_hash for call in witness.observed_calls}) == 5
    assert len({call.local_callable_token for call in witness.observed_calls}) == 5
    assert all(call.status == "returned" for call in witness.observed_calls)
    assert not basis._ISSUED.get(witness.content_hash)


def test_v2_controlled_call_freezes_each_in_place_state_before_seal(content_image) -> None:
    _root, image = content_image
    state = {"value": 1}

    default_values = [0]
    option_values = {"offset": 0}

    def operation(default=default_values, *, options=option_values):
        return state["value"] + default[0] + options["offset"]

    capture = _content_capture(image)
    for value in range(1, 6):
        state["value"] = value
        operation.__defaults__[0][0] = value
        operation.__kwdefaults__["options"]["offset"] = value
        assert capture.observe_numerical_call(operation) == 3 * value
    before_seal = tuple(call.callable_content for call in capture.observed_calls)
    state["value"] = 99
    operation.__defaults__[0][0] = 99
    operation.__kwdefaults__["options"]["offset"] = 99
    witness = capture.seal()

    assert tuple(call.callable_content for call in witness.observed_calls) == before_seal
    assert len(set(before_seal)) == 5
    assert len({call.local_callable_token for call in witness.observed_calls}) == 1
    assert len({call.numerical_content_hash for call in witness.observed_calls}) == 5


def test_v2_numeric_content_excludes_local_object_and_occurrence_tokens(content_image) -> None:
    _root, image = content_image
    left = _content_capture(image)
    right = _content_capture(image)
    assert left.observe_numerical_call(_closed_value(7)) == 7
    assert right.observe_numerical_call(_closed_value(7)) == 7
    left_witness, right_witness = left.seal(), right.seal()
    left_call, right_call = left_witness.observed_calls[0], right_witness.observed_calls[0]

    assert left_call.local_callable_token != right_call.local_callable_token
    assert left_call.numerical_content_hash == right_call.numerical_content_hash
    assert left_witness.content_hash != right_witness.content_hash


def test_v2_opaque_state_is_unknown_without_serializing_it(content_image) -> None:
    _root, image = content_image
    effects = []

    class Opaque:
        def __getattribute__(self, name):
            effects.append(name)
            raise AssertionError("opaque state must not be inspected")

    hidden = Opaque()

    def operation():
        return 4 if hidden is not None else 0

    capture = _content_capture(image)
    assert capture.observe_numerical_call(operation) == 4
    witness = capture.seal()
    call = witness.observed_calls[0]

    assert effects == []
    assert call.callable_content is None
    assert call.numerical_content_hash is None
    predicates = {item.predicate_id: item.provenance for item in call.predicates}
    assert predicates["callable_state"] == "not_established"
    assert predicates["globals_and_full_readset"] == "not_established"
    assert predicates["through_call_state_stability"] == "not_established"


def test_v2_production_image_includes_unimported_paths_and_bytes(content_image) -> None:
    root, before = content_image
    path = root / "src" / "polisyos" / "unimported.py"
    assert {item.relative_path for item in before.python_sources} == {
        "src/polisyos/__init__.py",
        "src/polisyos/unimported.py",
    }
    path.write_text("VALUE = 2\n", encoding="utf-8")
    after = basis.capture_n5_production_image(
        root=root, admitted_profile={"profile": "controlled-unit", "device": "cpu"}
    )

    assert before.content_hash != after.content_hash
    left, right = _content_capture(before), _content_capture(after)
    function = _closed_value(1)
    assert left.observe_numerical_call(function) == right.observe_numerical_call(function) == 1
    assert (
        left.seal().observed_calls[0].numerical_content_hash
        != right.seal().observed_calls[0].numerical_content_hash
    )


def test_v2_content_reader_roundtrips_and_preserves_v1_semantics(content_image) -> None:
    _root, image = content_image
    capture = _content_capture(image)
    capture.observe_numerical_call(_closed_value(3))
    witness = capture.seal()
    read = basis.read_n5_execution_content_witness(json.loads(witness.model_dump_json()))
    assert read == witness
    assert read.authority_purpose == "candidate_observation_only"
    raw = json.loads(witness.model_dump_json())
    raw["observed_calls"][0]["status"] = "raised"
    with pytest.raises(ValueError):
        basis.read_n5_execution_content_witness(raw)
    with pytest.raises(ValueError):
        basis.N5ExecutionImplementationWitness.model_validate(json.loads(witness.model_dump_json()))
    input_ref = ArtifactRef(
        artifact_id="sha256:" + "a" * 64, kind="n5_input", media_type="application/json"
    )
    _result, legacy = _historical_n5_result(input_ref, consumed_configuration=None)
    legacy_wire = legacy.model_dump_json()
    with pytest.raises(ValueError):
        basis.read_n5_execution_content_witness(json.loads(legacy_wire))
    assert (
        basis.N5ExecutionImplementationWitness.model_validate_json(legacy_wire).model_dump_json()
        == legacy_wire
    )


def test_v2_current_globals_are_an_explicit_unsupported_denominator(content_image) -> None:
    """Same supported content is not a proof of equivalent global dependencies."""
    from types import FunctionType

    _root, image = content_image

    def template():
        return example_global  # noqa: F821 - different deliberate function namespaces

    first = FunctionType(template.__code__, {"example_global": 1})
    second = FunctionType(template.__code__, {"example_global": 2})
    left, right = _content_capture(image), _content_capture(image)
    assert left.observe_numerical_call(first) == 1
    assert right.observe_numerical_call(second) == 2
    left_call, right_call = left.seal().observed_calls[0], right.seal().observed_calls[0]
    assert left_call.numerical_content_hash == right_call.numerical_content_hash
    assert {item.predicate_id: item.provenance for item in left_call.predicates}[
        "globals_and_full_readset"
    ] == "not_established"


def test_v2_declared_input_is_frozen_and_not_relabelled_from_result(content_image) -> None:
    _root, image = content_image
    effective = {"numerical_input": {"value": 1}}
    capture = _content_capture(image, effective_inputs=effective)
    initial = capture.numerical_intent_content_hash
    effective["numerical_input"]["value"] = 99
    assert capture.observe_numerical_call(_closed_value(1)) == 1
    witness = capture.seal()
    assert witness.numerical_intent_content_hash == initial
    assert witness.comparison_scope == "supported_pre_invocation_content_only"
    predicates = {item.predicate_id: item.provenance for item in witness.predicates}
    assert predicates["profile_admission"] == "not_established"


def test_v2_failed_actual_call_is_recorded_and_the_exception_is_preserved(content_image) -> None:
    _root, image = content_image
    failure = ValueError("controlled failure")

    def operation():
        raise failure

    capture = _content_capture(image)
    with pytest.raises(ValueError) as caught:
        capture.observe_numerical_call(operation)
    assert caught.value is failure
    witness = capture.seal()
    assert len(witness.observed_calls) == 1
    assert witness.observed_calls[0].status == "raised"
    assert witness.observed_calls[0].output_content is None


@pytest.mark.parametrize("state_kind", ["cycle", "shared"])
def test_v2_strict_function_state_refuses_unrepresented_aliases(content_image, state_kind):
    _root, image = content_image
    state = []
    if state_kind == "cycle":
        state.append(state)

    def operation(left=state, right=state):
        return 1

    capture = _content_capture(image)
    assert capture.observe_numerical_call(operation) == 1
    call = capture.seal().observed_calls[0]
    assert call.callable_content is None
    assert call.numerical_content_hash is None


def test_v2_strict_mode_does_not_change_legacy_normalizer_output() -> None:
    marker = object()

    def operation(value=marker):
        return value

    legacy = ledger._normalize_function_binding(operation)
    assert legacy["defaults"] == {"tuple": [{"singleton_type": "builtins.object"}]}
    with pytest.raises(ValueError, match="n5_callable_state_not_established"):
        ledger._normalize_function_binding(operation, strict=True)
    assert ledger._normalize_function_binding(operation) == legacy


def test_v2_native_typed_fields_are_supported_without_custom_serialization(content_image):
    from dataclasses import dataclass
    from enum import Enum

    from pydantic import BaseModel, ConfigDict

    _root, image = content_image

    class Mode(Enum):
        CHOSEN = "chosen"

    class TypedInput(BaseModel):
        model_config = ConfigDict(extra="forbid", frozen=True)
        value: int
        mode: Mode

    @dataclass(frozen=True, slots=True)
    class NativeInput:
        value: int

    capture = _content_capture(image)

    def operation(value):
        return value.value

    assert capture.observe_numerical_call(operation, TypedInput(value=3, mode=Mode.CHOSEN)) == 3
    assert capture.observe_numerical_call(operation, NativeInput(4)) == 4
    assert all(call.arguments_content is not None for call in capture.seal().observed_calls)


def test_v2_rehashed_unknown_scope_and_invalid_wire_still_refuse(content_image):
    import hashlib

    _root, image = content_image
    capture = _content_capture(image)
    capture.observe_numerical_call(_closed_value(1))
    witness = capture.seal()
    for mutation in ("wire", "scope", "outcome"):
        raw = json.loads(witness.model_dump_json())
        call = raw["observed_calls"][0]
        if mutation == "wire":
            call["output_content"] = "not JSON"
        elif mutation == "scope":
            next(
                item
                for item in call["predicates"]
                if item["predicate_id"] == "globals_and_full_readset"
            )["provenance"] = "recomputed"
        else:
            call["status"] = "raised"
        del raw["content_hash"]
        encoded = json.dumps(
            raw, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
        ).encode()
        raw["content_hash"] = "sha256:" + hashlib.sha256(encoded).hexdigest()
        with pytest.raises(ValueError):
            basis.read_n5_execution_content_witness(raw)


def test_v2_ieee_bits_survive_both_strict_codecs_and_legacy_cache_prewarm(content_image):
    import struct

    _root, image = content_image
    floats = [
        struct.unpack(">d", bytes.fromhex(bits))[0]
        for bits in (
            "7ff8000000000001",
            "7ff8000000000002",
            "fff8000000000001",
            "0000000000000000",
            "8000000000000000",
        )
    ]
    values = floats + [complex(value, -0.0) for value in floats]
    capture = _content_capture(image)

    def retain_value(value):
        def operation():
            return value

        return operation

    for value in values:
        assert capture.observe_numerical_call(retain_value(value)) is value
    calls = capture.seal().observed_calls
    assert len({call.callable_content_hash for call in calls}) == len(values)
    assert len({call.output_content for call in calls}) == len(values)
    assert len({basis._v2_native_wire(value) for value in values}) == len(values)

    def template():
        return 17.0

    cache = ledger._CodeNormalizationCache()
    strict_constants = []
    for value in values:
        code = template.__code__.replace(co_consts=(None, value))
        legacy = ledger._normalize_code_object(code, code_cache=cache)
        strict = ledger._normalize_code_object(code, code_cache=cache, strict=True)
        assert ledger._normalize_code_object(code, code_cache=cache) is legacy
        strict_constants.append(json.dumps(strict["consts"], sort_keys=True))
    assert len(set(strict_constants)) == len(values)
    assert ledger._normalize_code_constant(floats[0]) == {"float_hex": "nan"}


def test_v2_datetime_fold_and_fixed_timezone_content_are_distinct(content_image):
    from datetime import datetime, time, timedelta, timezone

    _root, image = content_image
    values = [datetime(2026, 11, 1, 1, 30, fold=fold) for fold in (0, 1)]
    values += [time(1, 30, fold=fold) for fold in (0, 1)]
    values += [
        datetime(2026, 1, 1, tzinfo=timezone(timedelta(hours=1), name))
        for name in ("one", "another")
    ]
    capture = _content_capture(image)

    def operation(value):
        return value

    for value in values:
        assert capture.observe_numerical_call(operation, value) is value
    calls = capture.seal().observed_calls
    assert all(call.arguments_content is not None for call in calls)
    assert len({call.arguments_content for call in calls}) == len(values)
    assert len({call.output_content for call in calls}) == len(values)


def test_v2_custom_timezone_is_unknown_without_running_callbacks(content_image):
    from datetime import datetime, time, tzinfo

    _root, image = content_image
    effects = []

    class CustomZone(tzinfo):
        def utcoffset(self, value):
            effects.append("offset")
            raise AssertionError("custom timezone callback")

        def tzname(self, value):
            effects.append("name")
            raise AssertionError("custom timezone callback")

    capture = _content_capture(image)

    def operation(value):
        return value

    for value in (datetime(2026, 1, 1, tzinfo=CustomZone()), time(tzinfo=CustomZone())):
        assert capture.observe_numerical_call(operation, value) is value
    assert effects == []
    assert all(
        call.arguments_content is None and call.output_content is None
        for call in capture.seal().observed_calls
    )


def test_v2_nested_calls_keep_entry_order_and_cannot_seal_in_progress(content_image):
    _root, image = content_image
    capture = _content_capture(image)
    inner = _closed_value(7)

    def outer():
        with pytest.raises(ValueError, match="n5_content_capture_in_progress"):
            capture.seal()
        return capture.observe_numerical_call(inner)

    assert capture.observe_numerical_call(outer) == 7
    calls = capture.seal().observed_calls
    assert [call.sequence for call in calls] == [0, 1]
    assert json.loads(calls[1].callable_content)["qualname"] == inner.__qualname__
    assert calls[0].local_callable_token != calls[1].local_callable_token


def test_v2_reader_revalidates_constructed_nested_models(content_image):
    _root, image = content_image
    capture = _content_capture(image)
    capture.observe_numerical_call(_closed_value(1))
    witness = capture.seal()
    invalid_call = witness.observed_calls[0].model_copy(update={"output_content": "invalid JSON"})
    invalid_witness = witness.model_copy(update={"observed_calls": (invalid_call,)})
    with pytest.raises(ValueError):
        basis.read_n5_execution_content_witness(invalid_witness)


def test_v2_reader_refuses_raw_mapping_with_unvalidated_nested_model(content_image):
    _root, image = content_image
    capture = _content_capture(image)
    capture.observe_numerical_call(_closed_value(1))
    witness = capture.seal()
    raw = json.loads(witness.model_dump_json())
    invalid_call = witness.observed_calls[0].model_copy(update={"status": "invalid"})
    raw["observed_calls"] = [invalid_call.model_dump(mode="json")]
    raw["content_hash"] = basis._v2_hash(
        {key: value for key, value in raw.items() if key != "content_hash"}
    )
    # Its digest is coherent; instance shortcut, rather than stale content, is
    # the distinguishing negative. The public reader requires actual JSON wire.
    raw["observed_calls"] = [invalid_call]
    with pytest.raises(ValueError, match="n5_content_witness_wire_required"):
        basis.read_n5_execution_content_witness(raw)


def test_v2_reader_json_domain_refuses_protocols_and_cycles_before_encoding(content_image):
    _root, image = content_image
    capture = _content_capture(image)
    capture.observe_numerical_call(_closed_value(1))
    witness = capture.seal()
    effects = []

    class HostileList(list):
        def __iter__(self):
            effects.append("iterated")
            return super().__iter__()

    cycle = []
    cycle.append(cycle)
    for unsupported in (HostileList([1]), cycle, float("nan"), {1: "non-string key"}):
        raw = json.loads(witness.model_dump_json())
        raw["unrecognized"] = unsupported
        with pytest.raises(ValueError, match="n5_content_witness_wire_required"):
            basis.read_n5_execution_content_witness(raw)
    assert effects == []


def _graph_capture(image, *, effective_inputs=None):
    return basis.N5ControlledCallCaptureV3(
        effective_inputs={"numerical_input": 0} if effective_inputs is None else effective_inputs,
        production_image=image,
    )


def test_v3_recursive_functions_and_native_cycles_have_positional_backrefs(content_image):
    _root, image = content_image

    def recursive(value=3):
        return value if value == 0 else recursive(value - 1) + 1

    cycle = []
    cycle.append(cycle)
    capture = _graph_capture(image)
    assert capture.observe_numerical_call(recursive) == 3
    assert capture.observe_numerical_call(lambda value: value is value[0], cycle)
    calls = capture.seal().observed_calls
    graph = json.loads(calls[0].callable_content)
    assert graph["root"] == {"ref": 0}
    assert graph["nodes"][0]["kind"] == "function"
    assert graph["nodes"][0]["closure"] == [{"ref": 0}]
    assert all(call.numerical_content_hash is not None for call in calls)
    # Same shape, different alias relation must remain distinct.
    assert basis._N5ContentGraph().wire((cycle, cycle)) != basis._N5ContentGraph().wire(
        ([[]], [[]])
    )


def test_v3_mutable_defaults_kwdefaults_and_closure_are_reencoded_per_call(content_image):
    _root, image = content_image
    shared = [1]

    options = {"value": 1}

    def operation(default=shared, *, options=options):
        return default[0] + options["value"] + shared[0]

    capture = _graph_capture(image)
    for number in (1, 2, 3):
        shared[0] = number
        operation.__kwdefaults__["options"]["value"] = number
        assert capture.observe_numerical_call(operation) == 3 * number
    before = tuple(call.callable_content for call in capture.observed_calls)
    shared[0] = 99
    witness = capture.seal()
    assert tuple(call.callable_content for call in witness.observed_calls) == before
    assert len(set(before)) == 3
    assert len({call.local_callable_token for call in witness.observed_calls}) == 1
    assert all(call.numerical_content_hash is not None for call in witness.observed_calls)


def test_v3_same_code_functions_bind_captured_native_content(content_image):
    _root, image = content_image
    capture = _graph_capture(image)
    functions = [_closed_value(number) for number in (1, 2, 1)]
    assert all(function.__code__ is functions[0].__code__ for function in functions)
    for function in functions:
        capture.observe_numerical_call(function)
    calls = capture.seal().observed_calls
    assert calls[0].numerical_content_hash == calls[2].numerical_content_hash
    assert calls[0].numerical_content_hash != calls[1].numerical_content_hash


def test_v3_slotted_opaque_objects_never_become_type_only_equality(content_image):
    _root, image = content_image
    effects = []

    class Slotted:
        __slots__ = ("value",)

        def __getattribute__(self, name):
            effects.append(name)
            raise AssertionError("opaque getter must not run")

    capture = _graph_capture(image)
    for value in (Slotted(), Slotted()):

        def operation(hidden=value):
            return hidden is not None

        assert capture.observe_numerical_call(operation)
    calls = capture.seal().observed_calls
    assert effects == []
    assert all(
        call.callable_content is None and call.numerical_content_hash is None for call in calls
    )


def test_v3_typed_native_fields_preserve_exact_bits_and_do_not_run_serializers(content_image):
    import struct
    from dataclasses import dataclass
    from datetime import datetime
    from decimal import Decimal
    from enum import Enum

    from pydantic import BaseModel, ConfigDict, model_serializer

    _root, image = content_image
    effects = []

    class Mode(Enum):
        FIRST = "first"

    class Input(BaseModel):
        model_config = ConfigDict(extra="forbid")
        values: list[float]
        mode: Mode

        @model_serializer
        def serialize(self):
            effects.append("serializer")
            raise AssertionError("serializer must not run")

    @dataclass(frozen=True, slots=True)
    class Frozen:
        amount: Decimal
        when: datetime
        payload: bytes

    capture = _graph_capture(image)
    for bits in ("7ff8000000000001", "7ff8000000000002", "8000000000000000"):
        value = Input(values=[struct.unpack(">d", bytes.fromhex(bits))[0]], mode=Mode.FIRST)
        assert capture.observe_numerical_call(lambda item: item, value) is value
    for fold in (0, 1):
        value = Frozen(Decimal("1.00"), datetime(2026, 11, 1, 1, 30, fold=fold), b"bytes")
        assert capture.observe_numerical_call(lambda item: item, value) is value
    calls = capture.seal().observed_calls
    assert effects == []
    assert all(call.arguments_content is not None for call in calls)
    assert len({call.arguments_content for call in calls}) == len(calls)


def test_v3_mutable_dataclasses_and_constructed_model_extra_state_stay_unknown(content_image):
    from dataclasses import dataclass

    from pydantic import BaseModel, ConfigDict

    _root, image = content_image

    @dataclass
    class Mutable:
        value: int

    class Input(BaseModel):
        model_config = ConfigDict(extra="forbid")
        value: int

    missing = Input.model_construct()
    extra = Input.model_construct(value=1)
    extra.__dict__["hidden"] = 2
    capture = _graph_capture(image)
    for value in (Mutable(1), missing, extra):
        assert capture.observe_numerical_call(lambda item: item, value) is value
    assert all(call.arguments_content is None for call in capture.seal().observed_calls)


def test_v3_real_strict_pure_step_under_explicit_shape_check_zero_profile(
    content_image, monkeypatch
):
    from polisyos.foundry.methods.base import (
        ComplexityClass,
        ComputeBackend,
        FidelityLevel,
        MethodContracts,
        MethodMetadata,
        MethodSignature,
        _beartype_enabled,
        foundry_method,
    )
    from polisyos.foundry.methods.exceptions import ContractViolationError

    _root, image = content_image
    monkeypatch.setenv("POLISYOS_STRICT", "1")
    monkeypatch.setenv("FOUNDRY_SHAPE_CHECK", "0")
    assert not _beartype_enabled()
    method_signature = MethodSignature(
        name="codec_contract",
        namespace="test.codec",
        version="1.0.0",
        backend=ComputeBackend.NUMPY,
        input_slots=frozenset(),
        output_slots=frozenset(),
        parameters=(),
        fidelity=FidelityLevel.LOW,
        complexity=ComplexityClass.O_1,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    @foundry_method(namespace="test.codec")
    class Method:
        signature = method_signature
        metadata = MethodMetadata(
            description="Strict codec qualification",
            contracts=MethodContracts(preconditions=("state['value'] > 0",)),
        )

        @staticmethod
        def pure_step(state, params):
            return {"value": state["value"] + params["offset"]}

    capture = _graph_capture(image)
    entry = Method.pure_step
    assert "strict_pure_step" in entry.__code__.co_qualname
    assert capture.observe_numerical_call(entry, {"value": 1}, {"offset": 2}) == {"value": 3}
    with pytest.raises(ContractViolationError):
        capture.observe_numerical_call(entry, {"value": 0}, {"offset": 2})
    calls = capture.seal().observed_calls
    assert all(call.callable_content is not None for call in calls)
    graph = json.loads(calls[0].callable_content)
    assert len([row for row in graph["nodes"] if row["kind"] == "function"]) == 2
    assert any(row["kind"] == "dataclass" for row in graph["nodes"])
    assert calls[1].status == "raised"
    assert all(call.numerical_content_hash is not None for call in calls)


def test_v3_roundtrip_dispatch_is_versioned_and_refuses_constructed_nested_models(content_image):
    _root, image = content_image
    capture = _graph_capture(image)
    capture.observe_numerical_call(_closed_value(1))
    witness = capture.seal()
    assert witness.schema_version == "N5ExecutionContentWitness@3.0"
    assert witness.normalization_profile == "supported-native-callable-graph/3"
    assert (
        type(basis.read_n5_execution_content_witness(witness)) is basis.N5ExecutionContentWitnessV3
    )
    raw = json.loads(witness.model_dump_json())
    raw["normalization_profile"] = "supported-native-pre-invocation-content/2"
    raw["content_hash"] = basis._v2_hash({k: v for k, v in raw.items() if k != "content_hash"})
    with pytest.raises(ValueError):
        basis.read_n5_execution_content_witness(raw)
    invalid = witness.observed_calls[0].model_copy(update={"output_content": "not JSON"})
    with pytest.raises(ValueError):
        basis.read_n5_execution_content_witness(
            witness.model_copy(update={"observed_calls": (invalid,)})
        )


def test_v3_classes_and_modules_require_actual_recorder_completed_binding(tmp_path, monkeypatch):
    import hashlib
    import importlib

    from tools import loaded_execution_capture as recorder_owner
    from tools.loaded_execution_capture import ExpectedSource, SourceExecutionCapture

    source = """import sys
self_module = sys.modules[__name__]
class Token:
    pass
def factory():
    cls = Token
    mod = self_module
    def operation():
        return cls is Token and mod is self_module
    return operation
operation = factory()
"""
    module_name = "codec_ref_sample"
    path = tmp_path / (module_name + ".py")
    path.write_text(source)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    recorder = SourceExecutionCapture(
        tmp_path,
        {module_name: ExpectedSource(path.name, digest)},
        exports={module_name: {"Token", "self_module", "operation"}},
    )
    slot = "_polisyos_loaded_execution_owner_v1"
    assert slot not in vars(sys), "test trust root requires a fresh recorder slot"
    # Restore the test process's initially absent slot after closing this actual
    # recorder. This cleanup never restarts/reappoints a production capture.
    monkeypatch.setitem(vars(sys), slot, None)
    monkeypatch.delitem(vars(sys), slot)
    monkeypatch.syspath_prepend(str(tmp_path))
    # This test trust root selects the recorder's supported clean import profile;
    # pytest's assertion-rewrite finder is restored at fixture teardown.
    assert recorder_owner._PROCESS_CAPTURE is None
    monkeypatch.setattr(recorder_owner, "_PROCESS_CAPTURE", None)
    monkeypatch.setattr(
        sys,
        "meta_path",
        [
            importlib.machinery.BuiltinImporter,
            importlib.machinery.FrozenImporter,
            importlib.machinery.PathFinder,
        ],
    )
    recorder.install()
    try:
        module = importlib.import_module(module_name)
        monkeypatch.setattr(
            ledger, "_retained_n5_host_capture", lambda: (SimpleNamespace(capture=recorder), None)
        )
        wire = basis._N5ContentGraph().wire(module.operation)
        rows = json.loads(wire)["nodes"]
        bindings = [row["binding"] for row in rows if row["kind"] == "recorded_binding"]
        assert {row["export"] for row in bindings} == {"Token", "self_module"}
        assert all(row["source_hash"] == digest for row in bindings)
        replacement = type("Token", (), {"__module__": module_name})
        with pytest.raises(ValueError, match="n5_reference_binding_not_established"):
            basis._N5ContentGraph().wire(replacement)
        module.Token = replacement
        with pytest.raises(ValueError, match="n5_reference_binding_not_established"):
            basis._N5ContentGraph().wire(module.operation)
    finally:
        recorder.close()
        sys.modules.pop(module_name, None)


def test_v3_shared_callable_argument_aliases_enter_the_numerical_key(content_image):
    _root, image = content_image
    captured = [1]

    def operation(argument):
        return argument is captured

    capture = _graph_capture(image)
    assert capture.observe_numerical_call(operation, captured)
    assert not capture.observe_numerical_call(operation, [1])
    first, second = capture.seal().observed_calls
    assert first.callable_content == second.callable_content
    assert first.arguments_content != second.arguments_content
    assert first.numerical_content_hash != second.numerical_content_hash


def test_v3_current_callable_snapshot_does_not_invoke_and_tracks_mutation(content_image):
    _root, image = content_image
    effects = []
    captured = [1]

    def operation():
        effects.append("called")
        return captured[0]

    before = basis.snapshot_n5_callable_content_v3(operation)
    assert before is not None
    assert effects == []
    captured[0] = 2
    after = basis.snapshot_n5_callable_content_v3(operation)
    assert before != after
    assert effects == []
    capture = _graph_capture(image)
    assert capture.observe_numerical_call(operation) == 2
    assert capture.seal().observed_calls[0].callable_content == after
    assert basis.snapshot_n5_callable_content_v3(object()) is None


def test_v3_enum_custom_state_is_content_or_unknown_without_getters(content_image):
    from enum import Enum

    _root, image = content_image

    class Choice(Enum):
        SELECTED = "selected"

    capture = _graph_capture(image)
    member = Choice.SELECTED
    member.extra = [1]
    capture.observe_numerical_call(lambda item: item, member)
    member.extra[0] = 2
    capture.observe_numerical_call(lambda item: item, member)
    member.extra = object()
    capture.observe_numerical_call(lambda item: item, member)
    calls = capture.seal().observed_calls
    assert calls[0].arguments_content != calls[1].arguments_content
    assert calls[0].arguments_content is not None and calls[1].arguments_content is not None
    assert calls[2].arguments_content is None


@pytest.mark.parametrize("carrier", ["dataclass", "model", "enum"])
@pytest.mark.parametrize("inherited", [False, True])
def test_v3_typed_instance_extra_slots_stay_unknown_despite_equal_declared_fields(
    content_image, carrier, inherited
):
    from dataclasses import dataclass
    from enum import Enum

    from pydantic import BaseModel, ConfigDict

    _root, image = content_image
    if carrier == "dataclass":
        if inherited:

            class Base:
                __slots__ = ("hidden",)

            @dataclass(frozen=True, slots=True)
            class Payload(Base):
                x: int
        else:

            @dataclass(frozen=True)
            class Payload:
                __slots__ = ("hidden", "x")
                x: int

        left, right = Payload(1), Payload(1)
    elif carrier == "model":

        class Base(BaseModel):
            model_config = ConfigDict(extra="forbid")
            __slots__ = ("hidden",) if inherited else ()
            x: int

        class Payload(Base):
            __slots__ = () if inherited else ("hidden",)

        left, right = Payload(x=1), Payload(x=1)
    else:
        if inherited:

            class Base:
                __slots__ = ("hidden",)

            class Payload(Base, Enum):
                FIRST = 1
                SECOND = 2
        else:

            class Payload(Enum):
                __slots__ = ("hidden",)
                FIRST = 1
                SECOND = 2

        left = right = Payload.FIRST

    def read_hidden(item):
        return item.hidden

    capture = _graph_capture(image)
    object.__setattr__(left, "hidden", 1)
    assert capture.observe_numerical_call(read_hidden, left) == 1
    object.__setattr__(right, "hidden", 2)
    assert capture.observe_numerical_call(read_hidden, right) == 2
    calls = capture.seal().observed_calls
    assert all(
        call.arguments_content is None and call.numerical_content_hash is None for call in calls
    )


def test_v3_shadowed_dataclass_dictionary_does_not_hide_extra_actual_state(content_image):
    from dataclasses import dataclass

    _root, image = content_image
    effects = []

    class Base:
        pass

    @dataclass(frozen=True)
    class Payload(Base):
        x: int

        @property
        def __dict__(self):
            effects.append("getter")
            raise AssertionError("shadowing getter must not run")

    value = Payload(1)
    object.__setattr__(value, "hidden", 2)
    capture = _graph_capture(image)
    assert capture.observe_numerical_call(lambda item: item.hidden, value) == 2
    call = capture.seal().observed_calls[0]
    assert effects == []
    assert call.arguments_content is None and call.numerical_content_hash is None


def test_v3_pydantic_field_set_is_content_and_private_extra_carriers_are_unknown(content_image):
    from pydantic import BaseModel, ConfigDict

    _root, image = content_image
    effects = []

    class Payload(BaseModel):
        model_config = ConfigDict(extra="forbid")
        x: int = 1

    class Falsey:
        def __bool__(self):
            effects.append("bool")
            raise AssertionError("unsupported private/extra carrier must not run")

    capture = _graph_capture(image)
    for value, expected in ((Payload(), 0), (Payload(x=1), 1)):
        assert (
            capture.observe_numerical_call(
                lambda item: len(item.model_dump(exclude_unset=True)), value
            )
            == expected
        )
    for slot in ("__pydantic_private__", "__pydantic_extra__"):
        for unsupported in ({}, Falsey()):
            value = Payload()
            object.__setattr__(value, slot, unsupported)
            assert capture.observe_numerical_call(lambda item: item.x, value) == 1
    calls = capture.seal().observed_calls
    assert calls[0].arguments_content is not None and calls[1].arguments_content is not None
    assert calls[0].arguments_content != calls[1].arguments_content
    assert calls[0].numerical_content_hash != calls[1].numerical_content_hash
    assert all(call.arguments_content is None for call in calls[2:])
    assert effects == []


def _owned_native_graph():
    from polisyos.ir import CausalGraphModel
    from polisyos.ir.analytics.causal_graph import CausalEdge

    return CausalGraphModel(
        graph_type="dag",
        nodes=["X", "Y"],
        edges=[CausalEdge(src="X", dst="Y", metadata={"weights": [1, 2]})],
        metadata={"nested": {"notes": ["initial"]}},
    )


def test_v3_actual_owner_graph_nested_frozen_values_capture_actual_call_arguments(content_image):
    _root, image = content_image
    graph = _owned_native_graph()

    def operation(value):
        return value.edges[0].metadata["weights"][0] + len(value.nodes)

    capture = _graph_capture(image)
    assert capture.observe_numerical_call(operation, graph) == 3
    first = capture.observed_calls[0]
    assert first.arguments_content is not None and first.numerical_content_hash is not None
    rows = json.loads(first.arguments_content)["nodes"]
    carriers = [row for row in rows if row["kind"] == "canonical_immutable_container"]
    assert {row["container_kind"] for row in carriers} == {"list", "mapping"}
    assert all(
        row["owner_profile"] == "polisyos.ir.canonical_immutable_container/1" for row in carriers
    )
    list.__setitem__(graph.edges[0].metadata["weights"], 0, 5)
    assert capture.observe_numerical_call(operation, graph) == 7
    second = capture.seal().observed_calls[1]
    assert first.callable_content == second.callable_content
    assert first.arguments_content != second.arguments_content
    assert first.numerical_content_hash != second.numerical_content_hash
    assert first.arguments_content == capture.observed_calls[0].arguments_content


def test_v3_owned_carrier_cycles_and_callable_argument_aliases_remain_exact(content_image):
    from polisyos.ir import read_canonical_immutable_container

    _root, image = content_image
    graph = _owned_native_graph()
    state = graph.metadata["nested"]["notes"]
    list.append(state, state)
    assert read_canonical_immutable_container(state)[1][1] is state

    def operation(value):
        return value is state and value[1] is state

    capture = _graph_capture(image)
    assert capture.observe_numerical_call(operation, state)
    call = capture.seal().observed_calls[0]
    assert call.callable_content is not None and call.arguments_content is not None
    assert call.numerical_content_hash is not None
    rows = json.loads(call.arguments_content)["nodes"]
    cyclic = [row for row in rows if row["kind"] == "canonical_immutable_container"]
    assert len(cyclic) == 1
    index = rows.index(cyclic[0])
    assert cyclic[0]["items"][1] == {"ref": index}


def test_v3_owned_container_adapter_does_not_admit_extra_state_subclasses_or_callbacks(
    content_image, monkeypatch
):
    _root, image = content_image
    graph = _owned_native_graph()
    owned_type = type(graph.nodes)
    effects = []

    class Extra(owned_type):
        __slots__ = ("hidden",)

        def __iter__(self):
            effects.append("iterated")
            raise AssertionError("unknown extra state must not run")

    capture = _graph_capture(image)
    value = Extra(["X"])
    value.hidden = 1
    assert capture.observe_numerical_call(lambda item: item.hidden, value) == 1
    assert capture.observed_calls[0].arguments_content is None

    def hostile_iterator(self):
        effects.append("iterated")
        raise AssertionError("replaced accessor must not run")

    monkeypatch.setattr(owned_type, "__iter__", hostile_iterator)
    assert capture.observe_numerical_call(lambda item: list.__len__(item), graph.nodes) == 2
    assert capture.seal().observed_calls[1].arguments_content is None
    assert effects == []


@pytest.mark.skipif(
    os.environ.get("FOUNDRY_SHAPE_CHECK") != "0",
    reason="actual native codec seam requires the explicitly selected shape-check-zero profile",
)
def test_v3_real_scm_repeated_numerical_calls_keep_exact_pre_call_state(content_image, tmp_path):
    from collections import Counter
    from dataclasses import fields, is_dataclass
    from types import GetSetDescriptorType, MemberDescriptorType

    from pydantic import BaseModel

    from polisyos.foundry.methods.catalog.causal.ncm_engine import NCMEngineMethod
    from polisyos.foundry.methods.catalog.causal.protocols import NCMQueryData
    from polisyos.ir import read_canonical_immutable_container
    from tests.unit.foundry.methods.catalog.causal.test_ncm_engine import _chain_ncm

    _root, image = content_image
    retained_ncm = _chain_ncm(noise_std=0.0)
    query = NCMQueryData(
        ncm_spec=retained_ncm,
        evidence={"X": 1.0},
        interventions=[{"X": 0.0}, {"X": 1.0}],
        query_vars=["Y"],
        n_samples=16,
    )
    state = {"ncm_query_data": query}
    intent = {"query": query, "seeds": (17, 18), "profile": "actual-scm-chain-codec-unit-v1"}
    capture = _graph_capture(image, effective_inputs=intent)
    entry = NCMEngineMethod.pure_step
    evidence = tmp_path / "actual-scm-seam"
    evidence.mkdir()

    def save(name, value):
        (evidence / name).write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")

    def type_label(value):
        cls = type(value)
        return cls.__module__ + "." + cls.__qualname__

    def encode(value):
        try:
            return {"status": "exact", "wire": basis.N5ControlledCallCaptureV3._native_wire(value)}
        except (ValueError, TypeError, RuntimeError, AttributeError) as error:
            return {"status": "unknown", "error": str(error), "error_type": type(error).__name__}

    def storage_census(value, path, active, rows):
        row = {"path": path, "native_type": type_label(value), **encode(value)}
        rows.append(row)
        if id(value) in active:
            row["cycle_backref"] = True
            return
        active = active | {id(value)}
        kind = type(value)
        children = []
        if isinstance(value, BaseModel):
            actual = object.__getattribute__(value, "__dict__")
            declared = type(value).model_fields
            row["declared_fields"] = sorted(declared)
            row["actual_dictionary"] = {name: type_label(item) for name, item in actual.items()}
            row["extra_instance_fields"] = sorted(set(actual) - set(declared))
            descriptors = []
            for owner in type(value).__mro__:
                for descriptor in vars(owner).values():
                    if type(descriptor) in (GetSetDescriptorType, MemberDescriptorType):
                        descriptors.append(
                            {
                                "owner": owner.__module__ + "." + owner.__qualname__,
                                "name": descriptor.__name__,
                                "kind": type(descriptor).__name__,
                            }
                        )
            row["actual_storage_descriptors"] = descriptors
            children.extend((item, path + "." + name) for name, item in actual.items())
            for slot in ("__pydantic_private__", "__pydantic_extra__", "__pydantic_fields_set__"):
                item = object.__getattribute__(value, slot)
                row[slot + "_type"] = type_label(item)
                if slot == "__pydantic_fields_set__":
                    row[slot + "_value"] = sorted(item)
                children.append((item, path + ".@" + slot))
        elif kind is dict:
            children.extend(
                (item, path + "[" + json.dumps(key) + "]") for key, item in value.items()
            )
        elif kind in (list, tuple, set, frozenset):
            children.extend(
                (item, path + "[" + str(index) + "]") for index, item in enumerate(value)
            )
        elif is_dataclass(value) and not isinstance(value, type):
            children.extend(
                (object.__getattribute__(value, field.name), path + "." + field.name)
                for field in fields(value)
            )
        else:
            owned = read_canonical_immutable_container(value)
            if owned is not None:
                tag, items = owned
                children.extend(
                    ((item, path + "[" + str(index) + "]") for index, item in enumerate(items))
                    if tag == "list"
                    else ((item, path + "[" + json.dumps(key) + "]") for key, item in items)
                )
        for child, child_path in children:
            storage_census(child, child_path, active, rows)

    def audit(stage, params):
        rows = []
        storage_census({"intent": intent, "state": state, "params": params}, "$", set(), rows)
        unknown = [row for row in rows if row["status"] == "unknown"]
        observation = {
            "stage": stage,
            "unit_profile": "tiny synthetic source image; no production code attestation",
            "frozen_intent_content": capture._intent,
            "frozen_intent_hash": capture.numerical_intent_content_hash,
            "current_intent": encode(intent),
            "current_callable": basis.snapshot_n5_callable_content_v3(entry),
            "current_arguments": encode((entry, (state, params), {})),
            "all_storage": rows,
            "all_unknown": unknown,
            "unknown_class_counts": dict(Counter(row["native_type"] for row in unknown)),
        }
        save(stage + ".json", observation)
        return observation

    observations = []
    outputs = []
    for seed in (17, 18):
        params = {"__seed__": seed, "n_samples": 16}
        before = audit("before-" + str(seed), params)
        try:
            result = capture.observe_numerical_call(entry, state, params)
            outputs.append(result)
            save("result-" + str(seed) + ".json", result)
        finally:
            after = audit("after-" + str(seed), params)
        observations.append((before, after))
    witness = capture.seal()
    (evidence / "witness.json").write_text(witness.model_dump_json(indent=2) + "\n")
    save(
        "execution-count.json",
        {
            "actual_ncm_calls": len(outputs),
            "seeds": [17, 18],
            "worlds_per_call": 2,
            "samples_per_world": 16,
        },
    )

    # All evidence above survives a refusal, including a second-call cache or
    # metadata mutation. The zero-noise independent chain is Y = 0.5 + 2 * X.
    assert len(outputs) == len(witness.observed_calls) == 2
    assert witness.numerical_intent_content_hash is not None
    for result, call, (before, after) in zip(
        outputs, witness.observed_calls, observations, strict=True
    ):
        summary = result["counterfactual_result"]
        assert summary["n_worlds"] == 2 and summary["n_samples"] == 16
        assert [world["Y"]["mean"] for world in summary["world_summaries"]] == pytest.approx(
            [0.5, 2.5], rel=0, abs=1e-12
        )
        assert before["all_unknown"] == after["all_unknown"] == []
        assert (
            before["current_intent"]["wire"] == after["current_intent"]["wire"] == capture._intent
        )
        assert before["current_callable"] == after["current_callable"] == call.callable_content
        assert before["current_arguments"]["wire"] == after["current_arguments"]["wire"]
        assert before["current_arguments"]["wire"] == call.arguments_content
        assert call.callable_content_hash is not None and call.numerical_content_hash is not None
        assert call.status == "returned"
    assert (
        witness.observed_calls[0].numerical_content_hash
        != witness.observed_calls[1].numerical_content_hash
    )
    assert basis.read_n5_execution_content_witness(witness) == witness


def test_foundry_bound_call_snapshot_uses_complete_receiver_and_array_bytes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An actual mechanism receiver changes identity when its input data changes."""
    from dataclasses import dataclass

    import jax
    import jax.numpy as jnp

    from polisyos.foundry.execute.mechanisms.fiscal import TaxSubsidy

    first = TaxSubsidy(rate=0.125, n_agents=3)
    equal = TaxSubsidy(rate=0.125, n_agents=3)
    changed_rate = TaxSubsidy(rate=0.25, n_agents=3)
    changed_shape = TaxSubsidy(rate=0.125, n_agents=4)
    initial = basis.snapshot_foundry_mechanism_call(first.emit_patches)
    assert initial == basis.snapshot_foundry_mechanism_call(equal.emit_patches)
    assert initial != basis.snapshot_foundry_mechanism_call(changed_rate.emit_patches)
    assert initial != basis.snapshot_foundry_mechanism_call(changed_shape.emit_patches)
    # A field inherited from the Equinox owner is still a consumed value.
    with monkeypatch.context() as patch:
        patch.setattr(TaxSubsidy, "debug_mode", True)
        assert initial != basis.snapshot_foundry_mechanism_call(first.emit_patches)
    assert initial == basis.snapshot_foundry_mechanism_call(first.emit_patches)
    changed_wrapper = first.emit_patches
    object.__setattr__(changed_wrapper, "unexpected_state", 1)
    with pytest.raises(ValueError, match="n5_foundry_bound_call_not_established"):
        basis.snapshot_foundry_mechanism_call(changed_wrapper)
    from equinox._module import _module as equinox_module

    selected_call = first.emit_patches
    with monkeypatch.context() as patch:
        patch.setattr(
            equinox_module,
            "wrapper_field_names",
            equinox_module.wrapper_field_names | {"unexpected_provider_field"},
        )
        with pytest.raises(ValueError, match="n5_foundry_bound_call_provider_not_established"):
            basis.snapshot_foundry_mechanism_call(selected_call)
    assert basis.snapshot_foundry_call_value(jax.random.PRNGKey(1)) != (
        basis.snapshot_foundry_call_value(jax.random.PRNGKey(2))
    )
    assert basis.snapshot_foundry_call_value(jnp.array([1.0, 2.0])) != (
        basis.snapshot_foundry_call_value(jnp.array([[1.0, 2.0]]))
    )
    assert basis.snapshot_foundry_call_value(jnp.array([1.0, 2.0], dtype=jnp.float32)) != (
        basis.snapshot_foundry_call_value(jnp.array([1, 2], dtype=jnp.int32))
    )
    with pytest.raises(ValueError, match="n5_foundry_call_value_limit_exceeded"):
        basis.snapshot_foundry_call_value(jnp.ones(16385, dtype=jnp.float32))
    with pytest.raises(ValueError, match="n5_foundry_bound_call_not_established"):
        basis.snapshot_foundry_mechanism_call(TaxSubsidy.emit_patches)

    @dataclass
    class UnsupportedReceiver:
        opaque: object

        def emit_patches(self) -> None:
            return None

    with pytest.raises(ValueError, match="n5_foundry_call_value_not_established"):
        basis.snapshot_foundry_mechanism_call(UnsupportedReceiver(object()).emit_patches)


def test_foundry_call_value_refuses_unowned_array_and_enum_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exact input identity covers provider, layout, access and stored state."""
    from collections.abc import Iterator, Mapping
    from dataclasses import dataclass, field
    from enum import Enum

    import jax
    import jax.numpy as jnp
    import numpy as np
    from jax._src.array import ArrayImpl
    from jax._src.lib import xla_client

    from polisyos.foundry.contracts.fidelity import FidelityLevel

    normal = jnp.array([1.0, 2.0], dtype=jnp.float32)
    assert type(normal) is ArrayImpl
    assert basis.snapshot_foundry_call_value(normal) == basis.snapshot_foundry_call_value(normal)
    try:
        object.__setattr__(normal, "policyos_unowned_state", "different")
    except (AttributeError, TypeError):
        pass
    else:
        with pytest.raises(ValueError, match="n5_foundry_array_instance_state_not_established"):
            basis.snapshot_foundry_call_value(normal)
        object.__delattr__(normal, "policyos_unowned_state")
    same_numpy = np.array([1.0, 2.0], dtype=np.float32)
    same_numpy.setflags(write=False)
    assert basis.snapshot_foundry_call_value(normal) != basis.snapshot_foundry_call_value(
        same_numpy
    )
    weak = jnp.asarray(1.0)
    strong = jnp.asarray(1.0, dtype=weak.dtype)
    assert weak.weak_type and not strong.weak_type
    assert basis.snapshot_foundry_call_value(weak) != basis.snapshot_foundry_call_value(strong)
    committed = jax.device_put(normal, jax.devices()[0])
    assert committed.committed and not normal.committed
    assert basis.snapshot_foundry_call_value(normal) != basis.snapshot_foundry_call_value(committed)
    view = same_numpy.view()
    with pytest.raises(ValueError, match="n5_foundry_call_array_layout_not_established"):
        basis.snapshot_foundry_call_value(view)
    metadata_array = np.array([1.0, 2.0], dtype=np.dtype("float32", metadata={"unit": "x"}))
    metadata_array.setflags(write=False)
    with pytest.raises(ValueError, match="n5_foundry_call_array_layout_not_established"):
        basis.snapshot_foundry_call_value(metadata_array)
    fortran = np.asfortranarray(np.arange(6, dtype=np.float32).reshape((2, 3)))
    fortran.setflags(write=False)
    with pytest.raises(ValueError, match="n5_foundry_call_array_layout_not_established"):
        basis.snapshot_foundry_call_value(fortran)
    with monkeypatch.context() as patch:
        patch.setattr(xla_client, "ArrayImpl", object)
        with pytest.raises(ValueError, match="n5_foundry_array_provider_not_established"):
            basis.snapshot_foundry_call_value(normal)
    assert basis.snapshot_foundry_call_value(FidelityLevel.SURROGATE_FLUID) != (
        basis.snapshot_foundry_call_value(FidelityLevel.RELAXED_DISCRETE)
    )

    calls: list[str] = []

    class UnownedArray(jax.Array):
        def __init__(self) -> None:
            self.hidden_state = "not-in-numpy-bytes"

        @property
        def size(self) -> int:
            calls.append("size")
            return 1

        @property
        def dtype(self) -> object:
            calls.append("dtype")
            return jnp.dtype("float32")

        def __array__(self, *args: object, **kwargs: object) -> object:
            calls.append("array")
            return jnp.array([1.0])

    custom = UnownedArray()
    with pytest.raises(ValueError, match="n5_foundry_array_type_not_established"):
        basis.snapshot_foundry_call_value(custom)
    assert calls == []

    class UnownedNumpy(np.ndarray):
        def __array__(self, *args: object, **kwargs: object) -> object:
            calls.append("numpy-array")
            return np.array([1.0])

    custom_numpy = np.array([1.0]).view(UnownedNumpy)
    with pytest.raises(ValueError, match="n5_foundry_call_value_not_established"):
        basis.snapshot_foundry_call_value(custom_numpy)
    assert calls == []

    class StatefulEnum(str, Enum):
        MEMBER = "same"

    StatefulEnum.MEMBER.extra_state = "hidden"  # type: ignore[attr-defined]
    with pytest.raises(ValueError, match="n5_foundry_enum_state_not_established"):
        basis.snapshot_foundry_call_value(StatefulEnum.MEMBER)

    class CustomValueEnum(Enum):
        MEMBER = "same"

        @property
        def value(self) -> str:
            calls.append("enum-value")
            return "same"

    with pytest.raises(ValueError, match="n5_foundry_enum_protocol_not_established"):
        basis.snapshot_foundry_call_value(CustomValueEnum.MEMBER)
    assert calls == []

    class MissingOwnerEnum(Enum):
        MEMBER = "same"

    del MissingOwnerEnum.MEMBER.__dict__["__objclass__"]
    with pytest.raises(ValueError, match="n5_foundry_enum_state_not_established"):
        basis.snapshot_foundry_call_value(MissingOwnerEnum.MEMBER)

    @dataclass
    class ShadowedField:
        number: int

    shadowed = ShadowedField(1)

    def descriptor_getter(_self: object) -> int:
        calls.append("descriptor")
        return 2

    with monkeypatch.context() as patch:
        patch.setattr(ShadowedField, "number", property(descriptor_getter), raising=False)
        with pytest.raises(ValueError, match="n5_foundry_receiver_descriptor_not_established"):
            basis.snapshot_foundry_call_value(shadowed)
    assert calls == []

    @dataclass
    class CustomGetter:
        number: int

        def __getattribute__(self, name: str) -> object:
            calls.append("getter")
            return object.__getattribute__(self, name)

    with pytest.raises(ValueError, match="n5_foundry_receiver_access_not_established"):
        basis.snapshot_foundry_call_value(CustomGetter(1))
    assert calls == []

    class CustomMetadata(Mapping[str, str]):
        def __getitem__(self, key: str) -> str:
            calls.append("metadata-get")
            raise KeyError(key)

        def __iter__(self) -> Iterator[str]:
            calls.append("metadata-iter")
            return iter(())

        def __len__(self) -> int:
            calls.append("metadata-len")
            return 0

    @dataclass
    class CustomMetadataField:
        number: int = field(metadata=CustomMetadata())

    with pytest.raises(ValueError, match="n5_foundry_receiver_metadata_not_established"):
        basis.snapshot_foundry_call_value(CustomMetadataField(1))
    assert calls == []
