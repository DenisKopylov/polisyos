"""Behavioral proposal for the trusted, bounded Ex-Ante executable witness.

RAW postimage only. This file is not collected or run from LOCAL/raw. Tests
require the Foundry source seam described in foundry-executable-witness-seams.md.
"""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest

from polisyos.core.contracts.foundry import MethodMetricInputCaptureRef, RestrictedMethodCallWitness
from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
from polisyos.foundry.methods.backends.numpy_runner import NumpyRunner
from polisyos.foundry.methods.backends.protocol import MethodResult
from polisyos.foundry.methods.catalog.policy.evaluation import ExAnteSimulationEstimator
from polisyos.foundry.methods.catalog.policy.restricted_executable_profile import (
    TRUSTED_EXANTE_NUMPY_PROFILE,
    _function_sha256,
    _ReadSetMapping,
    verify_persisted_restricted_call_witness,
)

_TRUSTED_EXANTE_PURE_STEP = ExAnteSimulationEstimator.pure_step
_HIDDEN_BASIS_MARKER = "same_output_hidden_basis"


def test_strict_profile_import_succeeds_in_fresh_process() -> None:
    environment = os.environ.copy()
    environment.update({"POLISYOS_STRICT": "1", "FOUNDRY_SHAPE_CHECK": "0"})
    product_root = Path(__file__).resolve().parents[5]
    script = "\n".join(
        (
            "import hashlib",
            "import json",
            "import numpy as np",
            "from dataclasses import replace",
            "from types import SimpleNamespace",
            "from polisyos.foundry.methods.base import _beartype_enabled",
            "from polisyos.foundry.methods.backends.dispatch import MethodDispatcher",
            "from polisyos.foundry.methods.backends.numpy_runner import NumpyRunner",
            "from polisyos.foundry.methods.catalog.policy.evaluation import ExAnteSimulationEstimator",
            "from polisyos.core.contracts.foundry import MethodMetricInputCaptureRef",
            "from polisyos.foundry.methods.catalog.policy.restricted_executable_profile import TRUSTED_EXANTE_NUMPY_PROFILE, _function_sha256, bind_occurrence_call_witness, verify_persisted_restricted_call_witness",
            "operation = ExAnteSimulationEstimator.pure_step",
            "assert not _beartype_enabled()",
            "assert 'strict_pure_step' in operation.__code__.co_qualname",
            "assert TRUSTED_EXANTE_NUMPY_PROFILE.method_operation is operation",
            "assert TRUSTED_EXANTE_NUMPY_PROFILE.method_code_sha256 == _function_sha256(operation)",
            "runner = NumpyRunner()",
            "dispatcher = MethodDispatcher(enable_runtime_selection=False)",
            "dispatcher.register_runner(runner)",
            "result = dispatcher.dispatch(method_class=ExAnteSimulationEstimator, signature=ExAnteSimulationEstimator.signature, state={'baseline': np.asarray([10.0, 20.0, 40.0]), 'scenario': np.asarray([11.0, 18.0, 44.0])}, params={}, seed=7)",
            "assert result.output['result']['mean_change'] == 1.0",
            "assert result.restricted_invocation is not None and result.restricted_invocation.status == 'verified'",
            "assert result.restricted_invocation.state_reads == TRUSTED_EXANTE_NUMPY_PROFILE.expected_state_reads",
            "assert result.restricted_invocation.parameter_reads == TRUSTED_EXANTE_NUMPY_PROFILE.expected_parameter_reads",
            "assert TRUSTED_EXANTE_NUMPY_PROFILE.expected_observed_state_reads == ('baseline', 'scenario', 'baseline', 'scenario')",
            "assert TRUSTED_EXANTE_NUMPY_PROFILE.expected_observed_parameter_reads == ('poverty_line', 'poverty_line')",
            "selected_input = {'baseline': [10.0, 20.0, 40.0], 'scenario': [11.0, 18.0, 44.0], 'params': {}, 'seed': 7}",
            "selected_input_sha256 = hashlib.sha256(json.dumps(selected_input, sort_keys=True, separators=(',', ':')).encode()).hexdigest()",
            "input_ref = MethodMetricInputCaptureRef.model_validate({'artifact_id': 'sha256:' + selected_input_sha256, 'kind': 'foundry.method_metric_input_capture', 'media_type': 'application/json', 'manifest_profile_sha256': 'sha256:' + hashlib.sha256(b'strict-profile-test-input-v1').hexdigest()})",
            "occurrence = SimpleNamespace(occurrence_id='graph-invocation.000001:0:method.exante', invocation_id='graph-invocation.000001', node_id='method.exante', method_fqn=ExAnteSimulationEstimator.signature.fqn, method_version=ExAnteSimulationEstimator.signature.version, method_abi_digest=ExAnteSimulationEstimator.signature.abi_digest())",
            "witness = bind_occurrence_call_witness(evidence=result.restricted_invocation, occurrence=occurrence, input_capture_ref=input_ref, input_capture_status='captured')",
            "assert witness.status == 'verified' and witness.input_capture_ref == input_ref",
            "assert verify_persisted_restricted_call_witness(witness, occurrence=occurrence, expected_input_capture_ref=input_ref, selected_output_slot_id='result', selected_output_value_path=('mean_change',), selected_output_value=1.0)",
            "wrong_evidence = replace(result.restricted_invocation, state_reads=('scenario', 'baseline'))",
            "wrong_witness = bind_occurrence_call_witness(evidence=wrong_evidence, occurrence=occurrence, input_capture_ref=input_ref, input_capture_status='captured')",
            "assert wrong_witness.status == 'unavailable'",
            "wrong_reads = witness.model_copy(update={'state_reads': ('scenario', 'baseline')})",
            "assert not verify_persisted_restricted_call_witness(wrong_reads, occurrence=occurrence, expected_input_capture_ref=input_ref, selected_output_slot_id='result', selected_output_value_path=('mean_change',), selected_output_value=1.0)",
        )
    )
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=product_root,
        env=environment,
        capture_output=True,
        check=False,
        text=True,
        timeout=60,
    )
    assert completed.returncode == 0, completed.stderr


def test_strict_wrapper_fingerprint_binds_captured_contract_and_fqn(monkeypatch) -> None:
    from polisyos.foundry.methods.base import (
        ComplexityClass,
        ComputeBackend,
        FidelityLevel,
        MethodContracts,
        MethodMetadata,
        MethodSignature,
        foundry_method,
    )

    monkeypatch.setenv("POLISYOS_STRICT", "1")
    monkeypatch.setenv("FOUNDRY_SHAPE_CHECK", "0")

    def wrapped_operation(*, namespace: str, contract: str):
        method_signature = MethodSignature(
            name="callable_identity",
            namespace="",
            version="0.0.0",
            input_slots=frozenset(),
            output_slots=frozenset(),
            parameters=(),
            fidelity=FidelityLevel.LOW,
            complexity=ComplexityClass.O_1,
            backend=ComputeBackend.NUMPY,
            supports_jit=False,
            supports_vmap=False,
            supports_grad=False,
        )

        @foundry_method(namespace=namespace)
        class CallableIdentityMethod:
            signature = method_signature
            metadata = MethodMetadata(
                description="Strict callable identity fixture",
                contracts=MethodContracts(preconditions=(contract,)),
            )

            @staticmethod
            def pure_step(state, params):
                return {"value": 1}

        return CallableIdentityMethod.pure_step

    original = wrapped_operation(namespace="test.identity", contract="True")
    changed_contract = wrapped_operation(namespace="test.identity", contract="False")
    changed_fqn = wrapped_operation(namespace="test.other_identity", contract="True")

    assert original.__code__ is changed_contract.__code__ is changed_fqn.__code__
    original_digest = _function_sha256(original)
    contract_digest = _function_sha256(changed_contract)
    fqn_digest = _function_sha256(changed_fqn)
    assert original_digest is not None
    assert contract_digest is not None
    assert fqn_digest is not None
    assert len({original_digest, contract_digest, fqn_digest}) == 3


def test_closure_fingerprint_refuses_cyclic_or_unaccounted_dataclass_storage() -> None:
    @dataclass(frozen=True)
    class Captured:
        value: object

    @dataclass(frozen=True, slots=True)
    class SlottedCapture:
        value: object

    def capture(value: object):
        def operation():
            return value

        return operation

    cyclic = Captured(None)
    object.__setattr__(cyclic, "value", cyclic)
    extra_state = Captured("declared")
    object.__setattr__(extra_state, "hidden", "undeclared")

    assert _function_sha256(capture(cyclic)) is None
    assert _function_sha256(capture(extra_state)) is None
    assert _function_sha256(capture(SlottedCapture("hidden-slot"))) is None


def test_invocation_evidence_refuses_incomplete_or_reordered_observed_reads() -> None:
    profile = TRUSTED_EXANTE_NUMPY_PROFILE
    output = {"result": {"mean_change": 1.0}}
    correct_state = profile.expected_observed_state_reads
    correct_parameters = profile.expected_observed_parameter_reads

    for state_reads in (
        correct_state[:-1],
        correct_state + ("baseline",),
        tuple(reversed(correct_state)),
    ):
        evidence = profile.invocation_evidence(
            output=output,
            state_reads=state_reads,
            parameter_reads=correct_parameters,
            parameter_origin="signature_default",
            runner_verified=True,
            backend_runtime_fingerprint="sha256:profile-test",
        )
        assert evidence.status == "unavailable"

    missing_parameter = profile.invocation_evidence(
        output=output,
        state_reads=correct_state,
        parameter_reads=correct_parameters[:-1],
        parameter_origin="signature_default",
        runner_verified=True,
        backend_runtime_fingerprint="sha256:profile-test",
    )
    assert missing_parameter.status == "unavailable"


def _dispatcher(*, runner: NumpyRunner | None = None) -> tuple[MethodDispatcher, NumpyRunner]:
    actual_runner = runner or NumpyRunner()
    dispatcher = MethodDispatcher(enable_runtime_selection=False)
    dispatcher.register_runner(actual_runner)
    return dispatcher, actual_runner


def _run(
    dispatcher: MethodDispatcher,
    *,
    method_class: type = ExAnteSimulationEstimator,
    params: dict[str, Any] | None = None,
) -> MethodResult:
    return dispatcher.dispatch(
        method_class=method_class,
        signature=method_class.signature,
        state={
            "baseline": np.asarray([10.0, 20.0, 40.0]),
            "scenario": np.asarray([11.0, 18.0, 44.0]),
        },
        params={} if params is None else params,
        seed=7,
    )


def test_real_builtin_through_dispatcher_records_the_observed_exact_call() -> None:
    dispatcher, _runner = _dispatcher()

    result = _run(dispatcher)
    evidence = result.restricted_invocation

    assert result.output["result"]["mean_change"] == 1.0
    assert evidence is not None
    assert evidence.status == "verified"
    assert evidence.profile_id == TRUSTED_EXANTE_NUMPY_PROFILE.profile_id
    assert evidence.profile_revision_sha256 == TRUSTED_EXANTE_NUMPY_PROFILE.revision_sha256
    assert evidence.method_callable_sha256 == TRUSTED_EXANTE_NUMPY_PROFILE.method_code_sha256
    assert evidence.runner_callable_sha256 == TRUSTED_EXANTE_NUMPY_PROFILE.runner_code_sha256
    assert (
        evidence.backend_runtime_fingerprint
        == (result.artifacts["backend_runtime_fingerprint"]["fingerprint"])
    )
    assert evidence.method_abi_digest == ExAnteSimulationEstimator.signature.abi_digest()
    assert evidence.state_reads == TRUSTED_EXANTE_NUMPY_PROFILE.expected_state_reads
    assert evidence.parameter_reads == TRUSTED_EXANTE_NUMPY_PROFILE.expected_parameter_reads
    assert evidence.parameter_origin == "signature_default"
    assert evidence.poverty_line_value is None
    assert evidence.output_slot_id == "result"
    assert evidence.output_value_path == ("mean_change",)
    assert evidence.output_value_sha256 is not None


def test_explicit_none_is_admitted_with_its_distinct_exact_origin() -> None:
    dispatcher, _runner = _dispatcher()

    result = _run(dispatcher, params={"poverty_line": None})

    assert result.output["result"]["mean_change"] == 1.0
    assert result.restricted_invocation is not None
    assert result.restricted_invocation.status == "verified"
    assert result.restricted_invocation.parameter_origin == "explicit_parameter"


def test_explicit_non_none_parameter_is_not_admitted_by_literal_profile() -> None:
    dispatcher, _runner = _dispatcher()

    result = _run(dispatcher, params={"poverty_line": 20.0})

    assert result.output["result"]["mean_change"] == 1.0
    assert result.restricted_invocation is not None
    assert result.restricted_invocation.status == "unavailable"
    assert result.restricted_invocation.parameter_origin == "not_established"


def test_same_scalar_lookalike_class_has_no_verified_profile() -> None:
    class ExAnteLookalike:
        signature = ExAnteSimulationEstimator.signature
        pure_step = staticmethod(ExAnteSimulationEstimator.pure_step)

    dispatcher, _runner = _dispatcher()
    result = _run(dispatcher, method_class=ExAnteLookalike)

    assert result.output["result"]["mean_change"] == 1.0
    assert result.restricted_invocation is not None
    assert result.restricted_invocation.status == "unavailable"
    assert result.restricted_invocation.limitation == (
        "restricted_exante_method_or_runner_identity_mismatch"
    )


def test_hidden_global_same_scalar_replacement_is_not_admitted(monkeypatch) -> None:
    def hidden_reader(state, params):
        output = _TRUSTED_EXANTE_PURE_STEP(state, params)
        _ = _HIDDEN_BASIS_MARKER
        return output

    monkeypatch.setattr(ExAnteSimulationEstimator, "pure_step", staticmethod(hidden_reader))
    dispatcher, _runner = _dispatcher()

    result = _run(dispatcher)

    assert result.output["result"]["mean_change"] == 1.0
    assert result.restricted_invocation is not None
    assert result.restricted_invocation.status == "unavailable"


def test_replaced_dispatch_bound_method_is_invoked_but_cannot_claim_profile(monkeypatch) -> None:
    dispatcher, runner = _dispatcher()
    original_execute = runner.execute

    def lookalike_execute(**kwargs):
        # It returns the same actual scalar through the original implementation,
        # but the dispatcher-selected callable is a different local reference.
        return original_execute(**kwargs)

    monkeypatch.setattr(runner, "execute", lookalike_execute)
    result = _run(dispatcher)

    assert result.output["result"]["mean_change"] == 1.0
    assert result.restricted_invocation is not None
    assert result.restricted_invocation.status == "unavailable"
    assert result.restricted_invocation.limitation in {
        "restricted_exante_method_or_runner_identity_mismatch",
        "restricted_exante_dispatch_runner_identity_mismatch",
    }


def test_recorder_refuses_unlisted_keys_and_preserves_access_order() -> None:
    view = _ReadSetMapping(
        {"baseline": [10.0], "scenario": [11.0], "secret": [0.0]},
        allowed=("baseline", "scenario"),
    )

    assert view.values() == ([10.0], [11.0])
    _ = view["baseline"]
    _ = view["scenario"]
    with pytest.raises(KeyError, match="restricted_exante_read_outside_builtin_profile"):
        _ = view["secret"]
    assert view.reads == ("baseline", "scenario", "baseline", "scenario")


def test_persisted_witness_is_recomputed_against_occurrence_and_input_capture() -> None:
    dispatcher, _runner = _dispatcher()
    result = _run(dispatcher)
    evidence = result.restricted_invocation
    assert evidence is not None and evidence.status == "verified"

    input_ref = MethodMetricInputCaptureRef.model_validate(
        {
            "artifact_id": "sha256:" + "a" * 64,
            "kind": "foundry.method_metric_input_capture",
            "media_type": "application/json",
            "manifest_profile_sha256": "sha256:" + "b" * 64,
        }
    )
    occurrence = SimpleNamespace(
        occurrence_id="graph-invocation.000001:0:method.exante",
        invocation_id="graph-invocation.000001",
        node_id="method.exante",
    )
    persisted = RestrictedMethodCallWitness.model_validate(
        {
            **asdict(evidence),
            "occurrence_id": occurrence.occurrence_id,
            "invocation_id": occurrence.invocation_id,
            "node_id": occurrence.node_id,
            "input_capture_ref": input_ref,
        }
    )

    assert verify_persisted_restricted_call_witness(
        persisted,
        occurrence=occurrence,
        expected_input_capture_ref=input_ref,
        selected_output_slot_id="result",
        selected_output_value_path=("mean_change",),
        selected_output_value=1.0,
    )
    # The real bounded reader has a distinct Pydantic reference subclass;
    # compare complete selected identity, not model class identity.
    from polisyos.scientist.methods.search.objective import SelectedMethodMetricArtifactRef

    selected_ref = SelectedMethodMetricArtifactRef.model_validate(
        input_ref.model_dump(mode="python")
    )
    assert verify_persisted_restricted_call_witness(
        persisted,
        occurrence=occurrence,
        expected_input_capture_ref=selected_ref,
        selected_output_slot_id="result",
        selected_output_value_path=("mean_change",),
        selected_output_value=1.0,
    )
    assert not verify_persisted_restricted_call_witness(
        persisted,
        occurrence=occurrence,
        expected_input_capture_ref=selected_ref.model_copy(
            update={"manifest_profile_sha256": "sha256:" + "c" * 64}
        ),
        selected_output_slot_id="result",
        selected_output_value_path=("mean_change",),
        selected_output_value=1.0,
    )
    assert not verify_persisted_restricted_call_witness(
        persisted,
        occurrence=occurrence,
        expected_input_capture_ref=selected_ref,
        selected_output_slot_id="result",
        selected_output_value_path=("mean_change",),
        selected_output_value=1.0,
        expected_backend_runtime_fingerprint="other-posture",
    )
    forged_occurrence = persisted.model_copy(
        update={"occurrence_id": "graph-invocation.other:0:method.exante"}
    )
    assert not verify_persisted_restricted_call_witness(
        forged_occurrence,
        occurrence=occurrence,
        expected_input_capture_ref=input_ref,
        selected_output_slot_id="result",
        selected_output_value_path=("mean_change",),
        selected_output_value=1.0,
    )
    assert not verify_persisted_restricted_call_witness(
        persisted,
        occurrence=occurrence,
        expected_input_capture_ref=None,
        selected_output_slot_id="result",
        selected_output_value_path=("mean_change",),
        selected_output_value=1.0,
    )
    assert not verify_persisted_restricted_call_witness(
        persisted,
        occurrence=occurrence,
        expected_input_capture_ref=input_ref,
        selected_output_slot_id="result",
        selected_output_value_path=("some_other_scalar",),
        selected_output_value=1.0,
    )
    assert not verify_persisted_restricted_call_witness(
        persisted,
        occurrence=occurrence,
        expected_input_capture_ref=input_ref,
        selected_output_slot_id="result",
        selected_output_value_path=("mean_change",),
        selected_output_value=2.0,
    )
