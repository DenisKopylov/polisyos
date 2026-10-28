"""Behavioral proposal for the trusted, bounded Ex-Ante executable witness.

RAW postimage only. This file is not collected or run from LOCAL/raw. Tests
require the Foundry source seam described in foundry-executable-witness-seams.md.
"""

from __future__ import annotations

from dataclasses import asdict
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
    _ReadSetMapping,
    verify_persisted_restricted_call_witness,
)

_TRUSTED_EXANTE_PURE_STEP = ExAnteSimulationEstimator.pure_step
_HIDDEN_BASIS_MARKER = "same_output_hidden_basis"


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
    assert evidence.state_reads == ("baseline", "scenario")
    assert evidence.parameter_reads == ("poverty_line",)
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

    _ = view["baseline"]
    _ = view["scenario"]
    with pytest.raises(KeyError, match="restricted_exante_read_outside_builtin_profile"):
        _ = view["secret"]
    assert view.reads == ("baseline", "scenario")


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
