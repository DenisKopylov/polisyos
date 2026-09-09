"""Fatal stop and recovery govern the same durable campaign, without erasing evidence."""

from __future__ import annotations

import asyncio
import hashlib
from dataclasses import fields
from pathlib import Path

import pytest

from polisyos.data_forge.domains.academic.batch import reextraction_campaign as owner
from polisyos.data_forge.domains.academic.batch.reextraction_transport import (
    ExtractionRequestError,
    SafeJsonWriter,
)


def _works():
    return [
        {
            "id": f"synthetic:{i}",
            "title": "Constructed study",
            "abstract": "Tax changes employment.",
            "year": 2024,
            "cited_by_count": 2,
            "doi": "",
            "synthetic": True,
        }
        for i in range(8)
    ]


def _plan(works, *, legacy=False):
    extras = {}
    if "execution_epoch" in {field.name for field in fields(owner.CampaignPlan)}:
        extras = {
            "execution_epoch": "v1" if legacy else "v2",
            "fatal_policy": "observe_per_work" if legacy else "stop_systemic",
        }
    return owner.CampaignPlan(
        campaign_id="synthetic:recovery",
        synthetic=True,
        input_count=len(works),
        input_digest="sha256:"
        + hashlib.sha256(
            "".join(owner._digest(work) + "\n" for work in works).encode(),
        ).hexdigest(),
        provider_profile_hash=owner._digest({"synthetic": True}),
        screening_model="synthetic:model",
        extraction_model="synthetic:model",
        concurrency=1,
        queue_capacity=2,
        max_attempts=32,
        max_attempts_per_phase=2,
        owner_source_hash=owner.campaign_owner_projection()["content_hash"],
        **extras,
    )


def _writer():
    return SafeJsonWriter("SYNTHETIC_TEST_CREDENTIAL_NEVER_RETURNED")


class _Transport:
    synthetic = True

    def __init__(self, calls, fail_at=None):
        self.calls = calls
        self.fail_at = fail_at

    def __call__(self, context):
        self.calls.append(context)
        return self

    async def chat(self, **kwargs):
        if len(self.calls) == self.fail_at:
            raise ExtractionRequestError("authentication_error", False, 401)
        return {"relevant": False, "reason": "synthetic control"}, {"prompt_tokens": 1}


def _run(plan, works, root, transport):
    return asyncio.run(
        owner.run_campaign(
            plan,
            works=iter(works),
            output_root=root,
            client_factory=transport,
            safe_write_json=_writer(),
        )
    )


def test_systemic_failure_stops_and_recovery_preserves_completed_work(tmp_path: Path):
    works = _works()
    plan = _plan(works)
    calls = []
    root = tmp_path / "run"
    first = _run(plan, works, root, _Transport(calls, fail_at=2))
    assert len(calls) == 2, "fatal_provider_failure_consumed_the_remaining_frame"
    assert first["execution_status"] == "stopped_fatal"
    assert first["works"] == {"complete": 1, "pending": 7}
    assert first["schema_version"] == "policyos.academic.extraction_campaign.v2"
    stop = first["fatal_stop_ref"]
    stop_bytes = (root / stop["path"]).read_bytes()
    restarted = _run(plan, works, root, _Transport(calls))
    assert len(calls) == 2 and restarted["fatal_stop_ref"] == stop
    with owner.CampaignCheckpoint(root, plan, _writer()) as checkpoint:
        with pytest.raises(ValueError, match="campaign_recovery_stop_mismatch"):
            checkpoint.recover_fatal_stop(
                {**stop, "sha256": "sha256:" + "0" * 64},
                acknowledgment_ref="synthetic:operator",
                reason="Synthetic credential corrected",
            )
        recovery = checkpoint.recover_fatal_stop(
            stop,
            acknowledgment_ref="synthetic:operator",
            reason="Synthetic credential corrected; budgets remain unchanged",
        )
    resumed = _run(plan, works, root, _Transport(calls))
    assert resumed["works"] == {"complete": 8}
    assert len(calls) == 9  # One failed attempt remains spent.
    assert resumed["fatal_stop_ref"] is None
    assert (root / stop["path"]).read_bytes() == stop_bytes
    assert (root / recovery["path"]).exists()
    assert [context.work_id for context in calls].count("synthetic:0") == 1


def test_fatal_attempt_reconstructs_stop_after_interrupted_publication(tmp_path, monkeypatch):
    works = _works()
    plan = _plan(works)
    calls = []
    root = tmp_path / "run"
    original = getattr(owner.CampaignCheckpoint, "_record_fatal_failure", None)
    assert original is not None, "fatal_stop_reconstruction_owner_missing"

    def interrupted(*args):
        raise RuntimeError("synthetic interruption after durable failed attempt")

    monkeypatch.setattr(owner.CampaignCheckpoint, "_record_fatal_failure", interrupted)
    with pytest.raises(ExceptionGroup):
        _run(plan, works, root, _Transport(calls, fail_at=1))
    monkeypatch.setattr(owner.CampaignCheckpoint, "_record_fatal_failure", original)
    stopped = _run(plan, works, root, _Transport(calls))
    assert len(calls) == 1
    assert stopped["execution_status"] == "stopped_fatal"
    assert stopped["works"] == {"pending": 8}


def test_historical_view_reads_original_epoch_but_cannot_dispatch(tmp_path, monkeypatch):
    works = _works()[:1]
    plan = _plan(works, legacy=True)
    root = tmp_path / "history"
    _run(plan, works, root, _Transport([]))
    before = {p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()}
    monkeypatch.setattr(owner, "campaign_owner_projection", lambda: {"content_hash": "changed"})
    with pytest.raises(ValueError, match="campaign_owner_source_mismatch"):
        owner.CampaignCheckpoint(root, plan, _writer())
    with owner.CampaignCheckpoint.read_only_history(root, plan) as history:
        history.validate_complete_frame()
        assert history.summary()["schema_version"] == "policyos.academic.extraction_campaign.v1"
        assert history.summary()["works"] == {"complete": 1}
        with pytest.raises(ValueError, match="campaign_history_is_read_only"):
            history.begin_attempt(
                next(history.iter_work_keys()),
                phase="screening",
                model="synthetic:model",
                prompt="synthetic",
            )
        with pytest.raises(ValueError, match="campaign_history_is_read_only"):
            history.prepare_inputs(iter(works))
    after = {p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()}
    assert after == before


def test_recovery_requires_all_dispatched_attempts_to_settle(tmp_path):
    works = _works()[:2]
    plan = _plan(works)
    with owner.CampaignCheckpoint(tmp_path / "run", plan, _writer()) as checkpoint:
        checkpoint.prepare_inputs(iter(works))
        keys = list(checkpoint.iter_work_keys())
        earlier = checkpoint.begin_attempt(
            keys[0], phase="screening", model="synthetic:model", prompt="A"
        )
        later = checkpoint.begin_attempt(
            keys[1], phase="screening", model="synthetic:model", prompt="B"
        )
        checkpoint.fail_attempt(
            later, kind="authentication_error", retryable=False, status_code=401
        )
        stop = checkpoint.active_fatal_stop()
        with pytest.raises(ValueError, match="campaign_recovery_requires_quiescence"):
            checkpoint.recover_fatal_stop(
                stop, acknowledgment_ref="synthetic:operator", reason="fixed"
            )
        # Only after the earlier dispatch actually settles may the stop be acknowledged.
        checkpoint.fail_attempt(
            earlier, kind="authentication_error", retryable=False, status_code=401
        )
        checkpoint.recover_fatal_stop(stop, acknowledgment_ref="synthetic:operator", reason="fixed")
        assert checkpoint.active_fatal_stop() is None
        assert checkpoint.summary()["attempts"] == {"failed": 2}
        assert checkpoint.db.execute("SELECT COUNT(*) FROM fatal_stops").fetchone()[0] == 2


def test_historical_reader_includes_valid_wal_without_touching_source(tmp_path):
    import sqlite3

    works = _works()[:1]
    plan = _plan(works, legacy=True)
    root = tmp_path / "wal-history"
    observer = None
    with owner.CampaignCheckpoint(root, plan, _writer()) as checkpoint:
        checkpoint.prepare_inputs(iter(works))
        key = next(checkpoint.iter_work_keys())
        context = checkpoint.begin_attempt(
            key, phase="screening", model="synthetic:model", prompt="A"
        )
        checkpoint.finish_attempt(context, {"relevant": False}, {})
        checkpoint.commit_work(key, status="screening_rejected", record=None)
        observer = sqlite3.connect(root / "checkpoint.sqlite3")
        observer.execute("BEGIN")
        observer.execute("SELECT COUNT(*) FROM works").fetchone()
    try:
        wal = root / "checkpoint.sqlite3-wal"
        assert wal.exists() and wal.stat().st_size > 0, "valid_uncheckpointed_wal_control_missing"
        before = {p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()}
        with owner.CampaignCheckpoint.read_only_history(root, plan) as history:
            import json

            history.validate_complete_frame()
            assert history.summary()["works"] == {"complete": 1}
            view = Path(history._history_temp.name)
            marker = json.loads((view / "snapshot_provenance.json").read_text())
            assert marker["synthetic"] is True and marker["authority_status"] == "candidate_only"
            assert marker["source_synthetic"] is plan.synthetic
        assert not view.exists()
        after = {p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()}
        assert after == before
    finally:
        observer.close()
