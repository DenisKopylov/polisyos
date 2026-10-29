"""Executable fragment for a real retained served-action / fresh-GET test.

Install before the real second positive equal-basis admission, and require a
nonempty records list after fresh GET. The fixture must retain both actual
cycles and the genuine owner action/snapshot; no constructed success carriers.
"""

from __future__ import annotations

from dataclasses import replace
from functools import wraps

import pytest

from polisyos.runtime.quality import acquisition_evaluation as evaluation
from polisyos.runtime.quality import acquisition_evaluation_history as history


def install_history_owner_probe(monkeypatch):
    """Exercise real owner readback plus targeted negative mutations."""
    real_verify = history.verify_retained_route_accumulator
    records = []

    def audited_verify(**kwargs):
        verified = real_verify(**kwargs)
        snapshot = kwargs["snapshot"]
        head = snapshot.head
        control_store = kwargs["control_store"]

        # This is a real older source cycle from the same run, not a fabricated
        # success. A historical match is insufficient after the fold advances.
        run = kwargs["generation_run"]
        assert len(run.cycles) >= 2
        with pytest.raises(ValueError, match="acquisition_retained_source_not_current_accumulator"):
            real_verify(**{**kwargs, "source_cycle": run.cycles[-2]})

        # Keep the selected terminal/decision/basis and SQL frontier after-ref
        # intact, but remove the before-ref returned by the owner store.
        changed_head = replace(head, evaluation_frontier_before_ref=None)
        changed_snapshot = replace(snapshot, head=changed_head)
        real_head_read = control_store.get_acquisition_action_head

        @wraps(real_head_read)
        def changed_head_read(**scope):
            selected = real_head_read(**scope)
            return changed_head if selected == head else selected

        with monkeypatch.context() as control:
            control.setattr(control_store, "get_acquisition_action_head", changed_head_read)
            with pytest.raises(
                ValueError, match="acquisition_retained_frontier_transaction_mismatch"
            ):
                real_verify(**{**kwargs, "snapshot": changed_snapshot})

        # Leave basis records, labels and digests intact but perturb the real
        # replay result; the deciding comparison must use reopened contents.
        real_replay = evaluation.replay_acquisition_basis_for_history
        replay_calls = []

        @wraps(real_replay)
        def changed_replay(**inputs):
            replayed = real_replay(**inputs)
            replay_calls.append(inputs["basis"])
            return replayed.model_copy(
                update={"effective_native_values_hex": replayed.effective_native_values_hex + "00"}
            )

        with monkeypatch.context() as control:
            control.setattr(evaluation, "replay_acquisition_basis_for_history", changed_replay)
            with pytest.raises(ValueError, match="acquisition_retained_basis_replay_mismatch"):
                real_verify(**kwargs)
        assert len(replay_calls) == 2

        # Deny the exact admitted selected source body, not just its name or
        # embedded declaration, while leaving all terminal/decision blobs.
        store = kwargs["artifact_store"]
        selected_source = verified.decision.admitted_source_ref
        target_id = str(selected_source.artifact_id)
        real_get_bytes = store.get_bytes
        denied = []

        @wraps(real_get_bytes)
        def deny_source(selector, *args, **extra):
            selected_id = str(getattr(selector, "artifact_id", selector))
            if selected_id == target_id:
                denied.append(selected_id)
                raise FileNotFoundError("controlled_selected_source_bytes_missing")
            return real_get_bytes(selector, *args, **extra)

        with monkeypatch.context() as control:
            control.setattr(store, "get_bytes", deny_source)
            with pytest.raises((FileNotFoundError, ValueError)):
                real_verify(**kwargs)
        assert denied and set(denied) == {target_id}
        records.append((kwargs, verified))
        return verified

    monkeypatch.setattr(history, "verify_retained_route_accumulator", audited_verify)
    return records


def assert_live_history_owner_was_exercised(records):
    assert records, "no actual retained action was reopened by the fresh history reader"


def install_later_reentry_probe(monkeypatch):
    """Observe the real GET reader's before-action fold for a later reentry."""
    real_verify = history.verify_acquisition_retention_history
    records = []

    @wraps(real_verify)
    def observe(**kwargs):
        verified = real_verify(**kwargs)
        receipt = verified.legacy_receipt
        if receipt is not None and receipt.terminal_outcome == "reentry_completed":
            prior_run = verified.source_generation_run
            prior_cycle = verified.source_cycle
            assert prior_run is not None and prior_cycle is not None
            if prior_cycle.cycle_index > 0:
                assert prior_run.cycles[-1] == prior_cycle
                assert verified.source_evaluation_job_id is not None
                assert verified.source_evaluation_job_id != kwargs["source_job_id"]
                records.append((kwargs, verified))
        return verified

    monkeypatch.setattr(history, "verify_acquisition_retention_history", observe)
    return records


def assert_later_reentry_is_visible(candidate_projection, records):
    """Call with the real fresh GET's candidate-simulation projection."""
    assert records, "no later real reentry was reopened"
    assert candidate_projection["acquisition_history_limitation_code"] is None
    entries = candidate_projection["acquisition_history"]
    for _args, verified in records:
        receipt = verified.legacy_receipt
        assert receipt is not None
        matches = [
            row
            for row in entries
            if row["route_id"] == receipt.route_id
            and row["action_generation"] == receipt.action_generation
        ]
        assert len(matches) == 1
        assert matches[0]["terminal_outcome"] == "reentry_completed"
        assert matches[0]["continuation"] is not None
