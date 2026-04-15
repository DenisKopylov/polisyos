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
