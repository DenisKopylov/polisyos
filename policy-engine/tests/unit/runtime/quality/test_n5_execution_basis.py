"""Retain actionable, bounded diagnostics without granting N5 reuse authority."""

from __future__ import annotations

import json
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
