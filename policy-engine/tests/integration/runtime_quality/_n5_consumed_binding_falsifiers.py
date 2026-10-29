"""Adversarial controls consuming only a genuine producer-issued N5 witness."""

from __future__ import annotations

import pytest

from polisyos.core.artifacts import ArtifactRef
from polisyos.runtime.quality import n5_execution_basis as basis
from polisyos.runtime.quality.generation_cycle import (
    JointSimulationPort,
    N4GenerationPort,
)
from polisyos.runtime.quality.joint_simulation_horizon import (
    JointSimulationRequest,
    JointSimulationResult,
)
from polisyos.runtime.quality.promotion_sequence import CanonicalN9PromotionPort


def assert_real_n5_instance_entry_shadows_refused(
    *,
    port: JointSimulationPort,
    result: JointSimulationResult,
    request: JointSimulationRequest,
    input_ref: ArtifactRef,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Keep class/source/code markers intact while replacing actual instance edges."""
    witness = basis.reconcile_live_n5_implementation(result, input_ref=input_ref)
    assert witness.predicate_provenance == "recomputed"
    controller = port._controller
    controller_type = type(controller)
    run = controller_type.run
    builder = type(port)._build_candidate_simulation_request
    assert "run" not in vars(controller)
    assert "_build_candidate_simulation_request" not in vars(port)

    # A future call would replay an old, genuine result without executing N5.
    # The real class.run/source still has every original code/hash/name marker.
    with monkeypatch.context() as mutation:
        mutation.setattr(controller, "run", lambda _request: result)
        assert controller_type.run is run
        with pytest.raises(ValueError, match="n5_consumed_receiver_dispatch_not_established"):
            basis.reconcile_live_n5_implementation(result, input_ref=input_ref)
    assert "run" not in vars(controller)
    assert basis.reconcile_live_n5_implementation(result, input_ref=input_ref) == witness

    # Replacing the actual selected port builder must fail even if the shadow
    # could return the same old request. Class/code markers remain untouched.
    with monkeypatch.context() as mutation:
        mutation.setattr(port, "_build_candidate_simulation_request", lambda **_kwargs: request)
        assert type(port)._build_candidate_simulation_request is builder
        with pytest.raises(ValueError, match="n5_consumed_receiver_dispatch_not_established"):
            basis.reconcile_live_n5_implementation(result, input_ref=input_ref)
    assert "_build_candidate_simulation_request" not in vars(port)
    assert basis.reconcile_live_n5_implementation(result, input_ref=input_ref) == witness

    # The verifier must reject an altered selector before running its body.
    calls: list[str] = []

    def changed_selector(_request: object) -> object:
        calls.append("executed")
        raise ValueError("changed selector executed before provenance check")

    with monkeypatch.context() as mutation:
        mutation.setattr(controller, "_select_engine", changed_selector)
        with pytest.raises(ValueError, match="n5_consumed_receiver_dispatch_not_established"):
            basis.reconcile_live_n5_implementation(result, input_ref=input_ref)
    assert not calls
    assert basis.reconcile_live_n5_implementation(result, input_ref=input_ref) == witness


def assert_unconsumed_slots_do_not_change_real_n5_witness(
    *,
    result: JointSimulationResult,
    input_ref: ArtifactRef,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A separate N5 denominator does not weaken the original C95 authority gate."""
    witness = basis.reconcile_live_n5_implementation(result, input_ref=input_ref)
    calls: list[str] = []

    def unconsumed(*_args: object, **_kwargs: object) -> object:
        calls.append("executed")
        raise AssertionError("unconsumed slot entered N5 reconciliation")

    # These patches are explicit adversarial controls after a real execution,
    # never observer plumbing or temporary restoration of canonical code.
    for owner, name in (
        (N4GenerationPort, "__call__"),
        (CanonicalN9PromotionPort, "__call__"),
    ):
        with monkeypatch.context() as mutation:
            mutation.setattr(owner, name, unconsumed)
            assert basis.reconcile_live_n5_implementation(result, input_ref=input_ref) == witness
    assert not calls
