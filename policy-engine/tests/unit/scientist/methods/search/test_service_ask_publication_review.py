"""Independent real CAS controls for acknowledged native ask ownership."""

from __future__ import annotations

import json

import pytest

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.scientist.methods.autotune.runtime import SequenceCandidateGenerator
from polisyos.scientist.methods.search.controller import SearchConfig, SearchController
from polisyos.scientist.methods.search.objective import (
    BudgetDeficitObjective,
    CompositeObjective,
)
from polisyos.scientist.methods.search.service import NativeSearchService
from polisyos.scientist.methods.search.stopping import MaxIterations


def _stage_a(candidate, context):
    return 0.0, True


def _stage_b(candidate, context):
    return {"simulation_results": {"budget_deficit": candidate["cost"]}}


class _FailingPublicationCAS(FileSystemCAS):
    """Fail the real checkpoint port while retaining the native CAS reader."""

    failure = None

    def put_json(self, *args, **kwargs):
        if self.failure == "put":
            raise OSError("independent actual checkpoint put failed")
        return super().put_json(*args, **kwargs)

    def get_verified_snapshot(self, ref):
        if self.failure == "readback":
            raise OSError("independent actual checkpoint readback failed")
        return super().get_verified_snapshot(ref)


def _service(store):
    return NativeSearchService(
        SearchController(
            SearchConfig(
                stopping=MaxIterations(3),
                objective=CompositeObjective([BudgetDeficitObjective()]),
                enable_stage_a=False,
            ),
            SequenceCandidateGenerator([{"cost": 2}, {"cost": 1}, {"cost": 0}]),
            _stage_a,
            _stage_b,
        ),
        store=store,
    )


def _view(service):
    return {
        "generator": service.controller._generator.get_state(),
        "run_state": service.controller._run_state.checkpoint_state(),
        "pending": service._pending_candidates,
        "completed": sorted(service._completed_candidate_ids),
        "initial_ids": sorted(service._initial_candidate_ids),
        "ask_iteration": service._ask_iteration,
        "initial_candidate": service._initial_candidate,
        "checkpoint_ref": service.checkpoint_ref.model_dump(mode="json"),
    }


@pytest.mark.parametrize("failure", [None, "put", "readback"])
def test_ask_publication_live_state_matches_fresh_acknowledged_checkpoint(tmp_path, failure):
    store = _FailingPublicationCAS(tmp_path / "cas")
    live = _service(store)
    first = live.ask(None, None, {})[0]
    evaluation = live.controller._evaluate_for_tell(first.payload, iteration=0, context={})
    live.tell(first.candidate_id, evaluation)
    acknowledged_ref = live.checkpoint_ref
    assert live.controller._generator.get_state()["index"] == 1
    assert not live._pending_candidates
    assert len(live.controller._history) == 1

    store.failure = failure
    if failure is None:
        next_proposals = live.ask(None, None, {})
        assert [proposal.payload for proposal in next_proposals] == [{"cost": 1}]
        assert live.checkpoint_ref != acknowledged_ref
    else:
        with pytest.raises(OSError, match="independent actual checkpoint"):
            live.ask(None, None, {})
        assert live.checkpoint_ref == acknowledged_ref
    store.failure = None

    fresh = _service(FileSystemCAS(tmp_path / "cas"))
    fresh.restore(live.checkpoint_ref)
    live_view, fresh_view = _view(live), _view(fresh)
    print(json.dumps({"failure": failure, "live": live_view, "fresh": fresh_view}, sort_keys=True))
    assert live_view == fresh_view
