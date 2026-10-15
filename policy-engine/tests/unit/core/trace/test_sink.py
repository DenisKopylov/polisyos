from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor

from polisyos.core.trace import CompositeTraceSink, JsonlTraceSink, TraceRecord


class _RecordingSink:
    def __init__(self) -> None:
        self.records: list[TraceRecord] = []

    def emit(self, rec: TraceRecord) -> None:
        self.records.append(rec)


class _FailingSink:
    def emit(self, rec: TraceRecord) -> None:
        del rec
        raise RuntimeError("boom")


def test_composite_trace_sink_isolates_sink_failures() -> None:
    recording = _RecordingSink()
    sink = CompositeTraceSink([_FailingSink(), recording])

    sink.emit(TraceRecord(run_id="R_trace", phase="phase", event="event"))

    assert len(recording.records) == 1


def test_jsonl_trace_sink_serializes_concurrent_writes(tmp_path) -> None:
    sink = JsonlTraceSink(tmp_path / "trace.jsonl")

    def _emit(i: int) -> None:
        sink.emit(TraceRecord(run_id=f"R_{i}", phase="phase", event=f"event_{i}"))

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(_emit, range(64)))

    lines = (tmp_path / "trace.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 64
    for line in lines:
        payload = json.loads(line)
        assert payload["phase"] == "phase"


def test_jsonl_trace_sink_emit_many_keeps_one_batch_contiguous(tmp_path) -> None:
    sink = JsonlTraceSink(tmp_path / "trace.jsonl")
    batch = [
        TraceRecord(run_id="R_trace", phase="worker", event=f"batch_{index}") for index in range(3)
    ]

    with ThreadPoolExecutor(max_workers=2) as pool:
        batch_future = pool.submit(sink.emit_many, batch)
        single_future = pool.submit(
            sink.emit,
            TraceRecord(run_id="R_trace", phase="parent", event="single"),
        )
        batch_future.result()
        single_future.result()

    events = [
        json.loads(line)["event"]
        for line in (tmp_path / "trace.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert events in (
        ["batch_0", "batch_1", "batch_2", "single"],
        ["single", "batch_0", "batch_1", "batch_2"],
    )


def test_emit_only_sink_does_not_claim_batch_capability() -> None:
    from polisyos.core.trace import BatchTraceSink

    assert not isinstance(_RecordingSink(), BatchTraceSink)
