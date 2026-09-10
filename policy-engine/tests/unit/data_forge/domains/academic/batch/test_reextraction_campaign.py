"""A campaign must resume actual committed work without repeating provider calls."""

from __future__ import annotations

import asyncio
import hashlib
import importlib
import importlib.util
import json
import os
import signal
import sqlite3
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import pytest

MODULE = "polisyos.data_forge.domains.academic.batch.reextraction_campaign"


def _owner():
    assert importlib.util.find_spec(MODULE) is not None, "durable_campaign_owner_missing"
    return importlib.import_module(MODULE)


def _safe_write(path: Path, payload: object) -> None:
    value = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    assert "TEST_SECRET_DO_NOT_PERSIST" not in value
    with path.open("x", encoding="utf-8") as stream:
        stream.write(value)


def _work(index: int = 0):
    return {
        "id": f"synthetic:{index}", "title": "Constructed policy study",
        "abstract": "Tax rate reduced employment.", "year": 2024,
        "cited_by_count": 20, "doi": "", "synthetic": True,
    }


def _hash(value):
    return "sha256:" + hashlib.sha256(json.dumps(
        value, sort_keys=True, ensure_ascii=False, separators=(",", ":"),
    ).encode()).hexdigest()


def _plan(owner, works=None, **changes):
    selected = [_work()] if works is None else works
    frame_hash = hashlib.sha256()
    for work in selected:
        frame_hash.update((_hash(work) + "\n").encode())
    payload = {
        "campaign_id": "synthetic:campaign", "synthetic": True,
        "input_count": len(selected), "input_digest": "sha256:" + frame_hash.hexdigest(),
        "provider_profile_hash": _hash({"provider": "constructed"}),
        "screening_model": "synthetic:model", "extraction_model": "synthetic:model",
        "concurrency": 1, "queue_capacity": 2, "max_attempts": 6,
        "max_attempts_per_phase": 2, "retry_unknown": True,
        "owner_source_hash": (
            owner.campaign_owner_projection()["content_hash"]
            if hasattr(owner, "campaign_owner_projection") else None
        ),
    }
    payload.update(changes)
    return owner.CampaignPlan(**payload)


def test_checkpoint_replays_response_and_refuses_rebound_source(tmp_path: Path) -> None:
    """Deleting content binding or response reuse must fail this control."""
    owner = _owner()
    plan = _plan(owner)
    with owner.CampaignCheckpoint(tmp_path / "run", plan, _safe_write) as checkpoint:
        checkpoint.prepare_inputs([_work()])
        work_key = checkpoint.register_work(_work())
        context = checkpoint.begin_attempt(
            work_key, phase="screening", model="synthetic:model", prompt="synthetic prompt",
        )
        checkpoint.finish_attempt(context, {"relevant": True}, {"prompt_tokens": 3})
    with owner.CampaignCheckpoint(tmp_path / "run", plan, _safe_write) as checkpoint:
        assert checkpoint.cached_response(
            work_key, phase="screening", model="synthetic:model", prompt="synthetic prompt",
        ) == ({"relevant": True}, {"prompt_tokens": 3})
        assert checkpoint.cached_response(
            work_key, phase="screening", model="synthetic:model", prompt="changed prompt",
        ) is None
        assert checkpoint.summary()["attempts"] == {"returned": 1}
    with (
        pytest.raises(ValueError, match="campaign_binding_mismatch"),
        owner.CampaignCheckpoint(
            tmp_path / "run", _plan(owner, extraction_model="different:model"), _safe_write,
        ),
    ):
        pass


def test_interrupted_attempt_consumes_budget_and_never_mints_zero_cost(tmp_path: Path) -> None:
    """An unresolved dispatch survives process loss and remains an unknown cost."""
    owner = _owner()
    plan = _plan(owner, max_attempts=1)
    with owner.CampaignCheckpoint(tmp_path / "run", plan, _safe_write) as checkpoint:
        checkpoint.prepare_inputs([_work()])
        key = checkpoint.register_work(_work())
        checkpoint.begin_attempt(key, phase="extraction", model="synthetic:model", prompt="p")
    with owner.CampaignCheckpoint(tmp_path / "run", plan, _safe_write) as checkpoint:
        assert checkpoint.summary()["attempts"] == {"outcome_unknown": 1}
        assert checkpoint.summary()["unknown_usage_attempts"] == 1
        with pytest.raises(ValueError, match="campaign_attempt_budget_exhausted"):
            checkpoint.begin_attempt(key, phase="extraction", model="synthetic:model", prompt="p")


def test_source_and_work_artifacts_are_individually_marked_and_checked(tmp_path: Path) -> None:
    """A completed row never substitutes for its intact source/result artifacts."""
    owner = _owner()
    with owner.CampaignCheckpoint(tmp_path / "run", _plan(owner), _safe_write) as checkpoint:
        key = checkpoint.register_work(_work())
        checkpoint.commit_work(key, status="screening_rejected", record=None)
        output = checkpoint.completed_work(key)
        assert output["synthetic"] is True
        assert output["status"] == "screening_rejected"
        paths = list((tmp_path / "run" / "works").glob("*.json"))
        assert len(paths) == 1
        payload = json.loads(paths[0].read_text())
        payload["status"] = "extracted"
        paths[0].write_text(json.dumps(payload))
        with pytest.raises(ValueError, match="campaign_artifact_hash_mismatch"):
            checkpoint.completed_work(key)


def test_same_output_root_has_one_checkpoint_writer(tmp_path: Path) -> None:
    """Removing the actual process lock must admit the second writer and fail."""
    owner = _owner()
    with (
        owner.CampaignCheckpoint(tmp_path / "run", _plan(owner), _safe_write),
        pytest.raises(ValueError, match="campaign_already_running"),
        owner.CampaignCheckpoint(tmp_path / "run", _plan(owner), _safe_write),
    ):
        pass


def test_plan_intake_recomputes_current_owner_projection(tmp_path: Path) -> None:
    """A supplied source hash cannot substitute for the current owning source bytes."""
    owner = _owner()
    assert hasattr(owner, "campaign_owner_projection"), "recomputed_campaign_source_intake_missing"
    projection = owner.campaign_owner_projection()
    assert projection["sources"]
    assert any(path.endswith("reextraction_transport.py") for path in projection["sources"])
    with pytest.raises(ValueError, match="campaign_owner_source_mismatch"):
        owner.CampaignCheckpoint(
            tmp_path / "wrong", _plan(owner, owner_source_hash=_hash("fake")), _safe_write,
        )
    with pytest.raises(ValueError, match="campaign_owner_source_mismatch"):
        owner.CampaignCheckpoint(
            tmp_path / "absent", _plan(owner, owner_source_hash=None), _safe_write,
        )
    assert not (tmp_path / "wrong").exists()
    assert not (tmp_path / "absent").exists()


def test_complete_work_intake_refuses_empty_or_rebound_identity(tmp_path: Path) -> None:
    """Invalid held inputs must fail at frame intake, before worker dispatch."""
    owner = _owner()
    with owner.CampaignCheckpoint(tmp_path / "run", _plan(owner), _safe_write) as checkpoint:
        checkpoint.register_work(_work())
        with pytest.raises(ValueError, match="campaign_work_identity_rebound"):
            checkpoint.register_work({**_work(), "abstract": "Changed source under same identity."})
        with pytest.raises(ValueError, match="campaign_held_abstract_missing"):
            checkpoint.register_work({**_work(1), "abstract": ""})


def test_dispatch_requires_complete_frame_admission(tmp_path: Path) -> None:
    """Registering a selected work alone cannot bypass the complete input frame."""
    owner = _owner()
    with owner.CampaignCheckpoint(tmp_path / "run", _plan(owner), _safe_write) as checkpoint:
        key = checkpoint.register_work(_work())
        with pytest.raises(ValueError, match="campaign_input_frame_not_admitted"):
            checkpoint.begin_attempt(key, phase="screening", model="synthetic:model", prompt="p")
        assert checkpoint.summary()["attempts"] == {}


def test_admitted_frame_membership_is_immutable(tmp_path: Path) -> None:
    """Corpus expansion requires another declared campaign, never a mutated frame."""
    owner = _owner()
    with owner.CampaignCheckpoint(tmp_path / "run", _plan(owner), _safe_write) as checkpoint:
        checkpoint.prepare_inputs([_work()])
        first = checkpoint.register_work(_work())
        checkpoint.begin_attempt(first, phase="screening", model="synthetic:model", prompt="p")
        before = {path.name for path in (checkpoint.root / "inputs").iterdir()}
        with pytest.raises(ValueError, match="campaign_input_frame_already_admitted"):
            checkpoint.register_work({**_work(), "id": "synthetic:extra"})
        assert {path.name for path in (checkpoint.root / "inputs").iterdir()} == before
        assert list(checkpoint.iter_work_keys()) == [first]
        assert checkpoint.summary()["attempts"] == {"dispatched": 1}


class _SyntheticTransport:
    """Construct text replies only; exercise the actual extraction and custody owners."""

    def __init__(self):
        self.calls = []
        self.active = 0
        self.peak = 0

    def bind(self, context):
        transport = self

        class Client:
            synthetic = True

            async def chat(self, *, model, temperature, prompt):
                del temperature, prompt
                assert model == "synthetic:model"
                transport.calls.append(context)
                transport.active += 1
                transport.peak = max(transport.peak, transport.active)
                await asyncio.sleep(0.01)
                transport.active -= 1
                if context.phase == "screening":
                    return {"relevant": True}, {"prompt_tokens": 3, "completion_tokens": 2}
                if context.phase == "self_verification":
                    return {"verifications": []}, {"prompt_tokens": 5, "completion_tokens": 3}
                return {
                    "causal_claims": [{
                        "cause_variable": "tax rate", "effect_variable": "employment",
                        "direction": "negative", "evidence_strength": "structural",
                        "claim_extraction_confidence": 0.7, "design_family_hint": "ols",
                        "claim_text": "Tax rate reduced employment.",
                        "supporting_spans": [{"section": "abstract",
                                              "text": "Tax rate reduced employment."}],
                    }], "extraction_confidence": 0.8,
                }, {"prompt_tokens": 7, "completion_tokens": 4}

        return Client()


@pytest.mark.asyncio
@pytest.mark.parametrize(("phase", "reply", "outcome"), [
    ("screening", {"relevant": "false"}, "contract_violation"),
    ("extraction", {}, "contract_violation"),
    ("self_verification", {"verifications": "accepted"}, "verification_unavailable"),
])
async def test_raw_phase_contract_failure_is_not_normalized_into_success(
    tmp_path: Path, phase: str, reply: dict, outcome: str,
) -> None:
    """Removing the raw phase admission must make these misleading defaults pass."""
    owner = _owner()
    transport = _SyntheticTransport()

    def factory(context):
        real = transport.bind(context)

        class Client:
            synthetic = True

            async def chat(self, *, model, temperature, prompt):
                if context.phase == phase:
                    return reply, {"prompt_tokens": 2, "completion_tokens": 1}
                return await real.chat(model=model, temperature=temperature, prompt=prompt)

        return Client()

    report = await owner.run_campaign(
        _plan(owner), works=iter([_work()]), output_root=tmp_path / "run",
        client_factory=factory, safe_write_json=_safe_write,
    )
    assert report["outcomes"] == {outcome: 1}
    with owner.CampaignCheckpoint(tmp_path / "run", _plan(owner), _safe_write) as checkpoint:
        output = checkpoint.completed_work(_hash(_work()))
        if phase == "self_verification":
            assert output["record"]["metadata"]["self_verification_status"] == "unavailable"
        else:
            assert output["record"] is None
    actual = [json.loads(path.read_bytes()) for path in (tmp_path / "run" / "attempts").glob("*.json")]
    assert any(packet.get("parsed") == reply for packet in actual)


@pytest.mark.asyncio
async def test_real_extractor_streams_bounded_workers_and_reuses_complete_results(
    tmp_path: Path,
) -> None:
    """Removing the bounded queue or durable output replay must fail this control."""
    owner = _owner()
    assert hasattr(owner, "run_campaign"), "bounded_campaign_bridge_missing"
    works = [_work(index) for index in range(7)]
    plan = _plan(owner, works, concurrency=4, queue_capacity=4, max_attempts=42)
    transport = _SyntheticTransport()
    report = await owner.run_campaign(
        plan, works=iter(works), output_root=tmp_path / "run",
        client_factory=transport.bind, safe_write_json=_safe_write,
    )
    assert report["works"] == {"complete": 7}
    assert report["outcomes"] == {"extracted": 7}
    assert report["attempts"] == {"returned": 21}
    assert 1 < transport.peak <= 4
    assert report["queue_peak"] <= 4
    with owner.CampaignCheckpoint(tmp_path / "run", plan, _safe_write) as checkpoint:
        for key in checkpoint.iter_work_keys():
            output = checkpoint.completed_work(key)
            assert output["record"]["metadata"]["source_provenance"]["synthetic"] is True
            claim = output["record"]["causal_claims"][0]
            assert claim["occurrence"]["synthetic"] is True
            assert claim["vocabulary"]["evidence_strength"] == "structural"
    before = {str(path.relative_to(tmp_path)): path.read_bytes()
              for path in (tmp_path / "run" / "works").glob("*.json")}
    transport.calls.clear()
    resumed = await owner.run_campaign(
        plan, works=iter(works), output_root=tmp_path / "run",
        client_factory=transport.bind, safe_write_json=_safe_write,
    )
    assert transport.calls == []
    assert resumed["works"] == {"complete": 7}
    assert before == {str(path.relative_to(tmp_path)): path.read_bytes()
                      for path in (tmp_path / "run" / "works").glob("*.json")}


@pytest.mark.asyncio
async def test_run_strangle_recomputes_actual_checkpoint_replay(tmp_path: Path, monkeypatch) -> None:
    """Removing durable replay while keeping receipt markers must make the proof fail."""
    owner = _owner()
    transport = _SyntheticTransport()
    plan = _plan(owner)
    report = await owner.run_campaign(
        plan, works=iter([_work()]), output_root=tmp_path / "run",
        client_factory=transport.bind, safe_write_json=_safe_write,
    )
    assert "strangle_ref" in report, "run_emitted_checkpoint_strangle_missing"
    receipt = json.loads((tmp_path / "run" / report["strangle_ref"]["path"]).read_bytes())
    assert receipt["synthetic"] is True
    assert receipt["default_flipped"] is True
    assert receipt["completed_work_count"] == 1
    assert receipt["provider_replay_attempts"] == 0
    with owner.CampaignCheckpoint(tmp_path / "run", plan, _safe_write) as checkpoint:
        monkeypatch.setattr(checkpoint, "completed_work", lambda *_: None)
        monkeypatch.setattr(checkpoint, "cached_response", lambda *_, **__: None)
        with pytest.raises(ValueError, match="campaign_checkpoint_replay_strangle_failed"):
            await owner.recompute_campaign_strangle(checkpoint)


@pytest.mark.asyncio
async def test_complete_frame_mismatch_refuses_before_any_provider_call(tmp_path: Path) -> None:
    owner = _owner()
    assert hasattr(owner, "run_campaign"), "bounded_campaign_bridge_missing"
    transport = _SyntheticTransport()
    with pytest.raises(ValueError, match="campaign_input_frame_mismatch"):
        await owner.run_campaign(
            _plan(owner), works=iter([_work(1)]), output_root=tmp_path / "run",
            client_factory=transport.bind, safe_write_json=_safe_write,
        )
    assert transport.calls == []


class _JournalledTransport(_SyntheticTransport):
    def __init__(self, root: Path, interrupt: bool):
        super().__init__()
        self.root = root
        self.interrupt = interrupt

    def bind(self, context):
        client = super().bind(context)
        transport = self

        class Client:
            synthetic = True

            async def chat(self, *, model, temperature, prompt):
                with (transport.root / "synthetic-provider-calls.jsonl").open("a") as stream:
                    stream.write(json.dumps({
                        "synthetic": True, "work_id": context.work_id, "phase": context.phase,
                        "attempt_id": context.attempt_id, "ordinal": context.attempt_ordinal,
                    }) + "\n")
                    stream.flush()
                    os.fsync(stream.fileno())
                if (transport.interrupt and context.work_id == "synthetic:1"
                        and context.phase == "extraction"):
                    _safe_write(transport.root / "kill-ready.json", {
                        "synthetic": True, "attempt_id": context.attempt_id,
                    })
                    await asyncio.Event().wait()
                return await client.chat(model=model, temperature=temperature, prompt=prompt)

        return Client()


def _synthetic_processing_clock(monkeypatch=None, *, day: int = 1) -> None:
    """Declare the same constructed semantic clock separately from real wall time."""
    from polisyos.data_forge.domains.academic.batch import article_extractor

    class ConstructedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 1, day, tzinfo=UTC).astimezone(tz or UTC)

    if monkeypatch is None:
        article_extractor.datetime = ConstructedDateTime
    else:
        monkeypatch.setattr(article_extractor, "datetime", ConstructedDateTime)


async def _subprocess_worker(root: Path, mode: str = "inflight") -> None:
    owner = _owner()
    _synthetic_processing_clock()
    works = [_work(index) for index in range(3)]
    root.mkdir(parents=True, exist_ok=True)
    transport = _JournalledTransport(root, interrupt=mode == "inflight")
    if mode == "publication":
        original_write = owner.CampaignCheckpoint._write_packet

        def interrupt_published_work(self, path, packet):
            result = original_write(self, path, packet)
            if path.parent.name == "works" and packet["work_key"] == _hash(_work()):
                _safe_write(root / "kill-ready.json", {"synthetic": True, "stage": mode})
                while True:
                    time.sleep(0.05)
            return result

        owner.CampaignCheckpoint._write_packet = interrupt_published_work
    await owner.run_campaign(
        _plan(owner, works, max_attempts=18), works=iter(works), output_root=root / "run",
        client_factory=transport.bind, safe_write_json=_safe_write,
    )


@pytest.mark.asyncio
async def test_actual_sigkill_restart_retains_completed_identity_sets(
    tmp_path: Path, monkeypatch,
) -> None:
    """Kill a real OS worker between phase intent and response, then replay it."""
    owner = _owner()
    _synthetic_processing_clock(monkeypatch)
    works = [_work(index) for index in range(3)]
    plan = _plan(owner, works, max_attempts=18)
    uninterrupted = _SyntheticTransport()
    await owner.run_campaign(
        plan, works=iter(works), output_root=tmp_path / "control",
        client_factory=uninterrupted.bind, safe_write_json=_safe_write,
    )
    root = tmp_path / "interrupted"
    child = subprocess.Popen([
        sys.executable, "-m",
        "tests.unit.data_forge.domains.academic.batch.test_reextraction_campaign", str(root),
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    deadline = time.monotonic() + 120
    try:
        while not (root / "kill-ready.json").exists():
            if child.poll() is not None:
                stdout, stderr = child.communicate(timeout=20)
                pytest.fail(json.dumps({"error": "synthetic_worker_terminated_before_barrier",
                                        "stdout": stdout, "stderr": stderr}))
            assert time.monotonic() < deadline, "synthetic_worker_barrier_timeout"
            await asyncio.sleep(0.05)
        child.send_signal(signal.SIGKILL)
        stdout, stderr = child.communicate(timeout=20)
        assert child.returncode == -signal.SIGKILL
    finally:
        if child.poll() is None:
            child.kill()
            child.communicate(timeout=20)
    before = {path.stem: path.read_bytes() for path in (root / "run" / "works").glob("*.json")}
    assert set(before) == {_hash(_work())[7:]}
    transport = _JournalledTransport(root, interrupt=False)
    report = await owner.run_campaign(
        plan, works=iter(works), output_root=root / "run",
        client_factory=transport.bind, safe_write_json=_safe_write,
    )
    expected = {path.stem: path.read_bytes()
                for path in (tmp_path / "control" / "works").glob("*.json")}
    observed = {path.stem: path.read_bytes() for path in (root / "run" / "works").glob("*.json")}
    expected_values = {key: json.loads(body) for key, body in expected.items()}
    observed_values = {key: json.loads(body) for key, body in observed.items()}
    # The interrupted execution honestly has an extra unknown dispatch. Compare
    # every candidate/result field; its complete differing attempt lineage is
    # independently reconciled below instead of pretending the histories match.
    assert {
        key: {field: value for field, value in body.items() if field != "phase_artifacts"}
        for key, body in observed_values.items()
    } == {
        key: {field: value for field, value in body.items() if field != "phase_artifacts"}
        for key, body in expected_values.items()
    }
    assert all(observed[key] == body for key, body in before.items())
    with sqlite3.connect(root / "run" / "checkpoint.sqlite3") as connection:
        db_keys = {row[0][7:] for row in connection.execute(
            "SELECT work_key FROM works WHERE state='complete'",
        )}
    assert db_keys == set(observed) == {_hash(work)[7:] for work in works}
    calls = [json.loads(line) for line in (root / "synthetic-provider-calls.jsonl").read_text()
             .splitlines()]
    all_pairs = {(work["id"], phase) for work in works
                 for phase in ("screening", "extraction", "self_verification")}
    assert {(call["work_id"], call["phase"]) for call in calls} == all_pairs
    assert len({call["attempt_id"] for call in calls}) == len(calls)
    assert {(call["work_id"], call["phase"]) for call in calls if call["ordinal"] > 1} == {
        ("synthetic:1", "extraction"),
    }
    assert len(calls) == len(all_pairs) + 1
    assert report["attempts"] == {"outcome_unknown": 1, "returned": 9}
    assert report["unknown_usage_attempts"] == 1
    assert not list((root / "run").rglob("*.pending"))
    sys.stdout.write(json.dumps({
        "synthetic": True, "child_returncode": child.returncode,
        "child_stdout": stdout, "child_stderr": stderr,
        "completed_artifact_ids": sorted(observed), "completed_database_ids": sorted(db_keys),
        "complete_candidate_values_equal": True,
        "synthetic_processing_clock": "2026-01-01T00:00:00+00:00",
        "provider_pairs": sorted(all_pairs), "attempt_states": report["attempts"],
        "unknown_usage_attempts": report["unknown_usage_attempts"],
    }, sort_keys=True) + "\n")


@pytest.mark.asyncio
async def test_sigkill_after_work_publication_replays_original_bytes(
    tmp_path: Path, monkeypatch,
) -> None:
    """Restart must adopt an emitted work even if its SQLite commit was interrupted."""
    owner = _owner()
    root = tmp_path / "publication"
    child = subprocess.Popen([
        sys.executable, "-m",
        "tests.unit.data_forge.domains.academic.batch.test_reextraction_campaign",
        str(root), "publication",
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    deadline = time.monotonic() + 120
    try:
        while not (root / "kill-ready.json").exists():
            if child.poll() is not None:
                stdout, stderr = child.communicate(timeout=20)
                pytest.fail(json.dumps({"error": "publication_barrier_unreached",
                                        "stdout": stdout, "stderr": stderr}))
            assert time.monotonic() < deadline, "publication_barrier_timeout"
            await asyncio.sleep(0.05)
        child.send_signal(signal.SIGKILL)
        stdout, stderr = child.communicate(timeout=20)
        assert child.returncode == -signal.SIGKILL
    finally:
        if child.poll() is None:
            child.kill()
            child.communicate(timeout=20)
    path = root / "run" / "works" / f"{_hash(_work())[7:]}.json"
    original_bytes = path.read_bytes()
    with sqlite3.connect(root / "run" / "checkpoint.sqlite3") as connection:
        assert connection.execute("SELECT COUNT(*) FROM works WHERE state='complete'").fetchone() == (
            0,
        )
    _synthetic_processing_clock(monkeypatch, day=2)
    works = [_work(index) for index in range(3)]
    transport = _JournalledTransport(root, interrupt=False)
    report = await owner.run_campaign(
        _plan(owner, works, max_attempts=18), works=iter(works), output_root=root / "run",
        client_factory=transport.bind, safe_write_json=_safe_write,
    )
    assert path.read_bytes() == original_bytes
    assert report["works"] == {"complete": 3}
    assert report["attempts"] == {"returned": 9}
    assert not any(context.work_id == "synthetic:0" for context in transport.calls)
    sys.stdout.write(json.dumps({"synthetic": True, "child_returncode": child.returncode,
                                 "published_work_original_bytes_retained": True,
                                 "resumed_report": report, "child_stdout": stdout,
                                 "child_stderr": stderr}) + "\n")


if __name__ == "__main__":
    asyncio.run(_subprocess_worker(Path(sys.argv[1]), sys.argv[2] if len(sys.argv) > 2 else "inflight"))
