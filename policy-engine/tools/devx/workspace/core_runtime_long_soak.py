#!/usr/bin/env python3
"""Run the core-runtime long-soak evidence suite and emit machine-readable reports."""

from __future__ import annotations

import argparse
import asyncio
import gc
import json
import os
import tempfile
import time
import tracemalloc
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path


@dataclass(frozen=True, slots=True)
class MemorySample:
    iteration: int
    current_kib: float
    peak_kib: float


@dataclass(frozen=True, slots=True)
class PlateauCheck:
    passed: bool
    head_max_kib: float
    tail_max_kib: float
    allowance_kib: float


@dataclass(frozen=True, slots=True)
class ScenarioReport:
    scenario_id: str
    title: str
    status: str
    iterations: int
    duration_seconds: float
    avg_iteration_ms: float
    current_memory_kib: float
    peak_memory_kib: float
    plateau: PlateauCheck
    memory_samples: tuple[MemorySample, ...]
    details: dict[str, object]
    error: str | None = None


@dataclass(frozen=True, slots=True)
class LongSoakReport:
    generated_at: str
    sample_every: int
    reports: tuple[ScenarioReport, ...]

    @property
    def failures(self) -> tuple[ScenarioReport, ...]:
        return tuple(report for report in self.reports if report.status != "pass")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the core-runtime long-soak evidence suite.",
    )
    parser.add_argument(
        "--iterations-run-index",
        type=int,
        default=192,
        help="Incremental run-index refresh iterations.",
    )
    parser.add_argument(
        "--iterations-timeline",
        type=int,
        default=192,
        help="Timeline build/query iterations.",
    )
    parser.add_argument(
        "--iterations-async-cas",
        type=int,
        default=192,
        help="Async CAS round-trip iterations.",
    )
    parser.add_argument(
        "--iterations-checkpoint",
        type=int,
        default=192,
        help="Async checkpoint restore-cycle iterations.",
    )
    parser.add_argument(
        "--iterations-cursor-store",
        type=int,
        default=192,
        help="Async cursor-store commit/load iterations.",
    )
    parser.add_argument(
        "--sample-every",
        type=int,
        default=16,
        help="Record one memory sample every N iterations.",
    )
    parser.add_argument(
        "--summary",
        type=Path,
        help="Optional markdown summary output path.",
    )
    parser.add_argument(
        "--json-output",
        type=Path,
        help="Optional JSON output path.",
    )
    return parser


def _touch_trace(trace_path: Path, original_bytes: bytes) -> None:
    trace_path.write_bytes(original_bytes)
    os.utime(trace_path, None)


def _capture_memory_sample(samples: list[MemorySample], iteration: int) -> None:
    gc.collect()
    current, peak = tracemalloc.get_traced_memory()
    samples.append(
        MemorySample(
            iteration=iteration,
            current_kib=round(current / 1024.0, 2),
            peak_kib=round(peak / 1024.0, 2),
        )
    )


def _evaluate_plateau(samples: tuple[MemorySample, ...]) -> PlateauCheck:
    if len(samples) < 2:
        return PlateauCheck(passed=True, head_max_kib=0.0, tail_max_kib=0.0, allowance_kib=0.0)

    midpoint = max(1, len(samples) // 2)
    head = samples[:midpoint]
    tail = samples[midpoint:]
    head_max = max(sample.current_kib for sample in head)
    tail_max = max(sample.current_kib for sample in tail)
    allowance = max(1024.0, round(head_max * 0.75, 2))
    return PlateauCheck(
        passed=tail_max <= head_max + allowance,
        head_max_kib=head_max,
        tail_max_kib=tail_max,
        allowance_kib=allowance,
    )


def _render_failure(
    scenario_id: str,
    title: str,
    iterations: int,
    samples: tuple[MemorySample, ...],
    exc: BaseException,
) -> ScenarioReport:
    plateau = _evaluate_plateau(samples)
    return ScenarioReport(
        scenario_id=scenario_id,
        title=title,
        status="fail",
        iterations=iterations,
        duration_seconds=0.0,
        avg_iteration_ms=0.0,
        current_memory_kib=samples[-1].current_kib if samples else 0.0,
        peak_memory_kib=samples[-1].peak_kib if samples else 0.0,
        plateau=plateau,
        memory_samples=samples,
        details={},
        error=f"{type(exc).__name__}: {exc}",
    )


def _build_runtime_fixture(root: Path) -> dict[str, object]:
    from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
    from polisyos.core.run.context import RunContext
    from polisyos.runtime.http.dependencies import build_runtime_api_context

    cas_root = root / ".polisyos"
    store = FileSystemCAS(cas_root)
    registry_ref = store.put_json(
        {"registry": {}},
        PutOptions(kind="core.registry_bundle", media_type="application/json"),
    )
    output_ref = store.put_json(
        {"result": True},
        PutOptions(kind="scientist.workflow_report", media_type="application/json"),
    )
    run = RunContext.start(
        store=store,
        registry_bundle=registry_ref,
        run_id="R_core_runtime_long_soak",
        tenant_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        cell_id="cell-a",
    )
    run.emit(
        "scientist.node.prepare",
        "NODE_OK",
        outputs=[output_ref],
        metrics={"duration_ms": 5, "status_ok": 1, "cache_hit": 1},
    )
    run.emit(
        "scientist.node.complete",
        "NODE_OK",
        outputs=[output_ref],
        metrics={"duration_ms": 3, "status_ok": 1},
    )
    run.add_output(output_ref)
    run.finalize(status="completed")
    ctx = build_runtime_api_context(
        cas_root=cas_root,
        core_runs_root=cas_root / "runs",
    )
    return {
        "cas_root": cas_root,
        "ctx": ctx,
        "core_run_id": run.run_manifest.run_id,
        "tenant_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
    }


def _run_index_long_soak(iterations: int, sample_every: int, root: Path) -> ScenarioReport:
    samples: list[MemorySample] = []
    title = "Run index incremental refresh"
    try:
        env = _build_runtime_fixture(root / "run-index")
        ctx = env["ctx"]
        assert hasattr(ctx, "run_index")
        run_index = ctx.run_index
        run_index.refresh(force=True)
        trace_path = run_index.get_run(env["core_run_id"]).run_dir / "trace.jsonl"
        original_bytes = trace_path.read_bytes()
        listed_runs = 0

        tracemalloc.start()
        tracemalloc.reset_peak()
        start = time.perf_counter()
        for index in range(iterations):
            _touch_trace(trace_path, original_bytes)
            run_index.refresh(force=True)
            runs = run_index.list_runs(limit=50, tenant_id=env["tenant_id"])
            assert runs
            assert runs[0][0].run_id == env["core_run_id"]
            listed_runs = len(runs[0])
            if (index + 1) % sample_every == 0 or index + 1 == iterations:
                _capture_memory_sample(samples, index + 1)
        duration = time.perf_counter() - start
        current, peak = tracemalloc.get_traced_memory()
    except (
        AssertionError,
        AttributeError,
        KeyError,
        OSError,
        RuntimeError,
        TypeError,
        ValueError,
    ) as exc:
        return _render_failure(
            "run_index_incremental_refresh", title, iterations, tuple(samples), exc
        )
    finally:
        tracemalloc.stop()

    sample_tuple = tuple(samples)
    plateau = _evaluate_plateau(sample_tuple)
    status = "pass" if plateau.passed else "fail"
    return ScenarioReport(
        scenario_id="run_index_incremental_refresh",
        title=title,
        status=status,
        iterations=iterations,
        duration_seconds=round(duration, 4),
        avg_iteration_ms=round((duration / max(iterations, 1)) * 1000.0, 3),
        current_memory_kib=round(current / 1024.0, 2),
        peak_memory_kib=round(peak / 1024.0, 2),
        plateau=plateau,
        memory_samples=sample_tuple,
        details={"listed_runs": listed_runs},
        error=None if plateau.passed else "Memory plateau assertion failed.",
    )


def _timeline_long_soak(iterations: int, sample_every: int, root: Path) -> ScenarioReport:
    samples: list[MemorySample] = []
    title = "Timeline query/build loops"
    try:
        env = _build_runtime_fixture(root / "timeline")
        ctx = env["ctx"]
        run = ctx.run_index.get_run(env["core_run_id"])
        assert run.trace_path is not None
        original_bytes = run.trace_path.read_bytes()
        total_events = 0

        tracemalloc.start()
        tracemalloc.reset_peak()
        start = time.perf_counter()
        for index in range(iterations):
            if index % max(1, sample_every // 2) == 0:
                _touch_trace(run.trace_path, original_bytes)
            built = ctx.timeline.build_for_run(run).timeline
            assert built.summary.run_id == env["core_run_id"]
            assert built.summary.total_events >= 0
            total_events = built.summary.total_events
            if (index + 1) % sample_every == 0 or index + 1 == iterations:
                _capture_memory_sample(samples, index + 1)
        duration = time.perf_counter() - start
        current, peak = tracemalloc.get_traced_memory()
    except (
        AssertionError,
        AttributeError,
        KeyError,
        OSError,
        RuntimeError,
        TypeError,
        ValueError,
    ) as exc:
        return _render_failure("timeline_build_loops", title, iterations, tuple(samples), exc)
    finally:
        tracemalloc.stop()

    sample_tuple = tuple(samples)
    plateau = _evaluate_plateau(sample_tuple)
    status = "pass" if plateau.passed else "fail"
    return ScenarioReport(
        scenario_id="timeline_build_loops",
        title=title,
        status=status,
        iterations=iterations,
        duration_seconds=round(duration, 4),
        avg_iteration_ms=round((duration / max(iterations, 1)) * 1000.0, 3),
        current_memory_kib=round(current / 1024.0, 2),
        peak_memory_kib=round(peak / 1024.0, 2),
        plateau=plateau,
        memory_samples=sample_tuple,
        details={"timeline_events": total_events},
        error=None if plateau.passed else "Memory plateau assertion failed.",
    )


def _async_cas_long_soak(iterations: int, sample_every: int, root: Path) -> ScenarioReport:
    samples: list[MemorySample] = []
    title = "Async CAS repeated round trips"
    try:
        from polisyos.common.async_tools import run_coro_sync
        from polisyos.core.artifacts.manifest import SchemaInfo
        from polisyos.core.artifacts.write_contract import ArtifactWriteOptions

        env = _build_runtime_fixture(root / "async-cas")
        ctx = env["ctx"]
        async_store = ctx.async_store

        async def _exercise() -> tuple[int, int]:
            payload_bytes = 0
            for batch in range((iterations + 3) // 4):
                refs = await asyncio.gather(
                    *(
                        async_store.put_json(
                            {"payload": f"async-long-soak-{batch * 4 + item}"},
                            ArtifactWriteOptions(
                                kind="runtime.long_soak_async_cas",
                                media_type="application/json",
                                schema=SchemaInfo(name="runtime.LongSoakAsyncCas", version="1.0"),
                            ),
                        )
                        for item in range(min(4, iterations - (batch * 4)))
                    )
                )
                payloads = await asyncio.gather(
                    *(async_store.get_bytes(ref.artifact_id) for ref in refs)
                )
                for payload in payloads:
                    payload_bytes += len(payload)
                completed = min((batch + 1) * 4, iterations)
                if completed % sample_every == 0 or completed == iterations:
                    _capture_memory_sample(samples, completed)
            return iterations, payload_bytes

        tracemalloc.start()
        tracemalloc.reset_peak()
        start = time.perf_counter()
        completed, payload_bytes = run_coro_sync(_exercise(), timeout_seconds=120)
        duration = time.perf_counter() - start
        current, peak = tracemalloc.get_traced_memory()
        assert completed == iterations
    except (
        AssertionError,
        AttributeError,
        KeyError,
        OSError,
        RuntimeError,
        TypeError,
        ValueError,
    ) as exc:
        return _render_failure("async_cas_round_trip", title, iterations, tuple(samples), exc)
    finally:
        tracemalloc.stop()

    sample_tuple = tuple(samples)
    plateau = _evaluate_plateau(sample_tuple)
    status = "pass" if plateau.passed else "fail"
    return ScenarioReport(
        scenario_id="async_cas_round_trip",
        title=title,
        status=status,
        iterations=iterations,
        duration_seconds=round(duration, 4),
        avg_iteration_ms=round((duration / max(iterations, 1)) * 1000.0, 3),
        current_memory_kib=round(current / 1024.0, 2),
        peak_memory_kib=round(peak / 1024.0, 2),
        plateau=plateau,
        memory_samples=sample_tuple,
        details={"payload_bytes": payload_bytes, "concurrency": 4},
        error=None if plateau.passed else "Memory plateau assertion failed.",
    )


def _checkpoint_long_soak(iterations: int, sample_every: int, root: Path) -> ScenarioReport:
    samples: list[MemorySample] = []
    title = "Async checkpoint restore cycles"
    try:
        from polisyos.common.async_tools import run_coro_sync
        from polisyos.core.artifacts.store import FileSystemCAS
        from polisyos.scientist.orchestration.engine.checkpoint import (
            CASCheckpointHook,
            restore_checkpoint_hook_from_runtime_metadata,
            serialize_checkpoint_hook_runtime_metadata,
        )
        from polisyos.scientist.orchestration.engine.state import ExperimentState

        def _build_benchmark_state(step: int) -> ExperimentState:
            return ExperimentState(
                run_id="R_core_runtime_long_soak",
                params={
                    "phase": "SIMULATION",
                    "items": list(range(16)),
                    "metrics": {"policy_cost": 100.0, "fairness": 0.02},
                    "step": step,
                },
            )

        store = FileSystemCAS(root / "checkpoint" / ".polisyos")
        current_hook = CASCheckpointHook(
            store=store,
            run_dir=root / "checkpoint" / "runs" / "R_core_runtime_long_soak",
            checkpoint_policy="strict",
        )

        async def _exercise() -> tuple[int, int]:
            nonlocal current_hook
            last_sequence = -1
            completed_nodes = 0
            for index in range(iterations):
                result = await current_hook.on_node_complete_async(
                    state=_build_benchmark_state(index),
                    alias=f"async_checkpoint_{index}",
                    node_id=f"scientist.node_async_checkpoint_{index}@1.0.0",
                    completed_nodes=[f"async_checkpoint_{item}" for item in range(index + 1)],
                    workflow_id="scientist_benchmark",
                    workflow_fingerprint="e" * 64,
                    cache_entry_ref=None,
                )
                assert result is not None
                metadata = serialize_checkpoint_hook_runtime_metadata(current_hook)
                assert metadata is not None
                completed_nodes = len(metadata.get("completed_nodes", []))
                restored = restore_checkpoint_hook_from_runtime_metadata(metadata)
                assert restored is not None
                current_hook = restored
                last_sequence = result.sequence_number
                if (index + 1) % sample_every == 0 or index + 1 == iterations:
                    _capture_memory_sample(samples, index + 1)
            return last_sequence, completed_nodes

        tracemalloc.start()
        tracemalloc.reset_peak()
        start = time.perf_counter()
        last_sequence, completed_nodes = run_coro_sync(_exercise(), timeout_seconds=180)
        duration = time.perf_counter() - start
        current, peak = tracemalloc.get_traced_memory()
        assert last_sequence == iterations - 1
    except (
        AssertionError,
        AttributeError,
        KeyError,
        OSError,
        RuntimeError,
        TypeError,
        ValueError,
    ) as exc:
        return _render_failure("async_checkpoint_restore", title, iterations, tuple(samples), exc)
    finally:
        tracemalloc.stop()

    sample_tuple = tuple(samples)
    plateau = _evaluate_plateau(sample_tuple)
    status = "pass" if plateau.passed else "fail"
    return ScenarioReport(
        scenario_id="async_checkpoint_restore",
        title=title,
        status=status,
        iterations=iterations,
        duration_seconds=round(duration, 4),
        avg_iteration_ms=round((duration / max(iterations, 1)) * 1000.0, 3),
        current_memory_kib=round(current / 1024.0, 2),
        peak_memory_kib=round(peak / 1024.0, 2),
        plateau=plateau,
        memory_samples=sample_tuple,
        details={"last_sequence": last_sequence, "completed_nodes": completed_nodes},
        error=None if plateau.passed else "Memory plateau assertion failed.",
    )


def _cursor_store_long_soak(iterations: int, sample_every: int, root: Path) -> ScenarioReport:
    samples: list[MemorySample] = []
    title = "Async cursor-store stream progress"
    try:
        from polisyos.common.async_tools import run_coro_sync
        from polisyos.core.artifacts.store import FileSystemCAS
        from polisyos.core.contracts.cursor import (
            CursorState,
            StreamCheckpoint,
            StreamLifecycleState,
            WatermarkType,
        )
        from polisyos.fabric.data_plane.cursor_store import AsyncCursorStoreAdapter, CursorStore

        store = FileSystemCAS(root / "cursor-store" / ".polisyos")
        cursor_store = AsyncCursorStoreAdapter(CursorStore(store), timeout_seconds=2.0)

        async def _exercise() -> int:
            last_offset = -1
            for index in range(iterations):
                cursor = CursorState(
                    cursor_id="stream.jsonl:events",
                    connector_id="stream.jsonl",
                    dataset_id="events",
                    watermark_type=WatermarkType.OFFSET,
                    watermark_value=str(index),
                    created_at=datetime.now(UTC),
                )
                checkpoint = StreamCheckpoint(
                    checkpoint_id=f"stream.jsonl:events:default:{index}",
                    stream_id="stream.jsonl:events:default",
                    connector_id="stream.jsonl",
                    dataset_id="events",
                    partition_key="default",
                    offset=index,
                    resume_token=f"resume-{index}",
                    lifecycle_state=StreamLifecycleState.ACTIVE,
                    created_at=datetime.now(UTC),
                )
                await cursor_store.commit_stream_progress(cursor=cursor, checkpoint=checkpoint)
                latest = await cursor_store.find_latest_stream_checkpoint("stream.jsonl", "events")
                assert latest is not None
                last_offset = latest.offset
                if (index + 1) % sample_every == 0 or index + 1 == iterations:
                    _capture_memory_sample(samples, index + 1)
            return last_offset

        tracemalloc.start()
        tracemalloc.reset_peak()
        start = time.perf_counter()
        last_offset = run_coro_sync(_exercise(), timeout_seconds=120)
        duration = time.perf_counter() - start
        current, peak = tracemalloc.get_traced_memory()
        assert last_offset == iterations - 1
    except (
        AssertionError,
        AttributeError,
        KeyError,
        OSError,
        RuntimeError,
        TypeError,
        ValueError,
    ) as exc:
        return _render_failure(
            "async_cursor_store_stream_progress", title, iterations, tuple(samples), exc
        )
    finally:
        tracemalloc.stop()

    sample_tuple = tuple(samples)
    plateau = _evaluate_plateau(sample_tuple)
    status = "pass" if plateau.passed else "fail"
    return ScenarioReport(
        scenario_id="async_cursor_store_stream_progress",
        title=title,
        status=status,
        iterations=iterations,
        duration_seconds=round(duration, 4),
        avg_iteration_ms=round((duration / max(iterations, 1)) * 1000.0, 3),
        current_memory_kib=round(current / 1024.0, 2),
        peak_memory_kib=round(peak / 1024.0, 2),
        plateau=plateau,
        memory_samples=sample_tuple,
        details={"last_offset": last_offset},
        error=None if plateau.passed else "Memory plateau assertion failed.",
    )


def run_long_soak(
    *,
    iterations_run_index: int,
    iterations_timeline: int,
    iterations_async_cas: int,
    iterations_checkpoint: int,
    iterations_cursor_store: int,
    sample_every: int,
) -> LongSoakReport:
    with tempfile.TemporaryDirectory(prefix="core-runtime-long-soak-") as tmp_dir:
        root = Path(tmp_dir)
        reports = (
            _run_index_long_soak(iterations_run_index, sample_every, root),
            _timeline_long_soak(iterations_timeline, sample_every, root),
            _async_cas_long_soak(iterations_async_cas, sample_every, root),
            _checkpoint_long_soak(iterations_checkpoint, sample_every, root),
            _cursor_store_long_soak(iterations_cursor_store, sample_every, root),
        )
    return LongSoakReport(
        generated_at=datetime.now(UTC).isoformat(),
        sample_every=sample_every,
        reports=reports,
    )


def write_summary(path: Path, report: LongSoakReport) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Core Runtime Long Soak",
        "",
        f"- Generated at: `{report.generated_at}`",
        f"- Sample every: `{report.sample_every}` iterations",
        f"- Failures: `{len(report.failures)}`",
        "",
        "| Scenario | Status | Iterations | Avg ms/iter | Peak KiB | Plateau |",
        "|---|---|---:|---:|---:|---|",
    ]
    for item in report.reports:
        lines.append(
            f"| `{item.scenario_id}` | `{item.status}` | {item.iterations} | "
            f"{item.avg_iteration_ms:.3f} | {item.peak_memory_kib:.2f} | "
            f"{'pass' if item.plateau.passed else 'fail'} |"
        )
    lines.append("")

    for item in report.reports:
        lines.extend(
            [
                f"## {item.title}",
                "",
                f"- Status: `{item.status}`",
                f"- Iterations: `{item.iterations}`",
                f"- Duration seconds: `{item.duration_seconds}`",
                f"- Avg ms/iter: `{item.avg_iteration_ms}`",
                f"- Current memory KiB: `{item.current_memory_kib}`",
                f"- Peak memory KiB: `{item.peak_memory_kib}`",
                f"- Plateau: `{'pass' if item.plateau.passed else 'fail'}` "
                f"(head max `{item.plateau.head_max_kib}` KiB, "
                f"tail max `{item.plateau.tail_max_kib}` KiB, "
                f"allowance `{item.plateau.allowance_kib}` KiB)",
            ]
        )
        if item.details:
            lines.append(f"- Details: `{json.dumps(item.details, sort_keys=True)}`")
        if item.error:
            lines.append(f"- Error: `{item.error}`")
        lines.extend(
            [
                "",
                "### Memory Samples",
                "",
                "| Iteration | Current KiB | Peak KiB |",
                "|---|---:|---:|",
            ]
        )
        for sample in item.memory_samples:
            lines.append(
                f"| {sample.iteration} | {sample.current_kib:.2f} | {sample.peak_kib:.2f} |"
            )
        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")


def write_json(path: Path, report: LongSoakReport) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": report.generated_at,
        "sample_every": report.sample_every,
        "reports": [asdict(item) for item in report.reports],
        "failures": [asdict(item) for item in report.failures],
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    report = run_long_soak(
        iterations_run_index=max(args.iterations_run_index, 1),
        iterations_timeline=max(args.iterations_timeline, 1),
        iterations_async_cas=max(args.iterations_async_cas, 1),
        iterations_checkpoint=max(args.iterations_checkpoint, 1),
        iterations_cursor_store=max(args.iterations_cursor_store, 1),
        sample_every=max(args.sample_every, 1),
    )

    for item in report.reports:
        print(
            f"[{item.status.upper()}] {item.scenario_id} "
            f"iterations={item.iterations} avg_ms={item.avg_iteration_ms:.3f} "
            f"peak_kib={item.peak_memory_kib:.2f}"
        )
        if item.error:
            print(f"  - error: {item.error}")

    if args.summary:
        write_summary(args.summary.resolve(), report)
    if args.json_output:
        write_json(args.json_output.resolve(), report)

    return 1 if report.failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
