"""Bounded real-work measurements, without latency or memory performance promises."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path


def test_actual_audit_profiles_measure_equal_data_in_separate_processes(tmp_path: Path):
    reports = []
    for audit in ("full", "summary", "none"):
        output = tmp_path / f"{audit}.json"
        env = dict(os.environ)
        env.update(OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1")
        command = [sys.executable, "-B", str(Path(__file__).resolve()), audit, str(output)]
        run = subprocess.run(
            command, env=env, capture_output=True, text=True, timeout=90, check=False
        )
        (tmp_path / f"{audit}.stdout").write_text(run.stdout)
        (tmp_path / f"{audit}.stderr").write_text(run.stderr)
        print(
            json.dumps(
                {
                    "worker_command": command,
                    "return_code": run.returncode,
                    "stdout": run.stdout,
                    "stderr": run.stderr,
                },
                sort_keys=True,
            )
        )
        assert run.returncode == 0, f"{command!r}\n{run.stdout}\n{run.stderr}"
        reports.append(json.loads(output.read_text()))
    assert len({report["pid"] for report in reports}) == 3
    for case in range(2):
        assert len({report["workloads"][case]["input_sha256"] for report in reports}) == 1
        assert len({report["workloads"][case]["data_sha256"] for report in reports}) == 1
        assert len({report["workloads"][case]["lineage_sha256"] for report in reports}) == 1
    print(
        json.dumps(
            {"scope": "fresh workers; peak includes imports and warmup", "profiles": reports},
            sort_keys=True,
        )
    )


def test_stdlib_group_cost_and_traced_allocation_profile(tmp_path: Path):
    import math
    import platform
    import time
    import tracemalloc
    from fractions import Fraction

    from polisyos.common.numeric_reductions import finite_binary64_mean

    reports = []
    iterations = 2_000
    for size in (2, 8, 32):
        values = [10.0 + (i % 5) for i in range(size)]
        if size > 2:
            values[:3] = [1e308, -1e308, 3 * math.ulp(0.0)]
        expected = float(sum(map(Fraction.from_float, values), Fraction()) / size)
        assert finite_binary64_mean(values) == expected
        tracemalloc.start()
        started = time.perf_counter()
        for _ in range(iterations):
            observed = finite_binary64_mean(values)
        seconds = time.perf_counter() - started
        _current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        assert observed == expected and math.isfinite(observed)
        reports.append(
            {
                "group_size": size,
                "iterations": iterations,
                "wall_seconds": seconds,
                "peak_traced_python_bytes": peak,
                "point_hex": observed.hex(),
            }
        )
    report = {
        "python": platform.python_version(),
        "owner": "CPython statistics.mean",
        "scope": "declared finite groups with tracemalloc enabled; not dataframe or total process RSS",
        "groups": reports,
    }
    (tmp_path / "numeric-group-cost.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, sort_keys=True))


def _audit_worker(audit: str, output: Path) -> None:
    import importlib.metadata
    import platform
    import resource
    import time
    from dataclasses import replace

    import pandas as pd

    from polisyos.fabric.connectors.federation import (
        AuditLevel,
        CompositionStrategy,
        ConflictResolver,
        DataComposer,
    )
    from polisyos.fabric.connectors.federation.composer import _read_persisted_lineage
    from polisyos.fabric.connectors.federation.profile import frame_digest
    from tests.unit.fabric.connectors.test_federation_lane07 import _metadata, _request

    level = AuditLevel(audit)
    metadata = [_metadata(name) for name in ("primary", "used", "unused")]

    def execute(rows: int, columns: int):
        names = [f"v{i}" for i in range(columns)]
        frames = [
            pd.DataFrame(
                {
                    "id": range(rows),
                    **{
                        name: [999.0 if i % 2 == 0 else None for i in range(rows)] for name in names
                    },
                }
            ),
            pd.DataFrame({"id": range(rows), **{name: [22.0] * rows for name in names}}),
            pd.DataFrame({"id": range(rows), **{name: [33.0] * rows for name in names}}),
        ]
        request = replace(
            _request(CompositionStrategy.OVERLAY),
            primary_source=metadata[0].connector_id,
            audit_level=level,
            audit_max_entries=32,
            audit_sample_size=8,
        )
        input_digest = hashlib.sha256(
            "".join(frame_digest(frame) for frame in frames).encode()
        ).hexdigest()
        composer = DataComposer(ConflictResolver(request.conflict_policy))
        started = time.perf_counter()
        result, entries = composer.compose(
            list(zip(frames, metadata, strict=True)), request.strategy, request
        )
        seconds = time.perf_counter() - started
        expected = [999.0 if i % 2 == 0 else 22.0 for i in range(rows)]
        assert result["id"].tolist() == list(range(rows))
        assert all(result[name].tolist() == expected for name in names)
        basis = _read_persisted_lineage(result)
        assert basis is not None
        lineage = [
            {column: [origin.token for origin in origins] for column, origins in row.items()}
            for row in basis
        ]
        count = rows // 2 * columns
        summary = composer.get_last_merge_summary()
        assert summary is not None
        if level is AuditLevel.NONE:
            assert not entries and summary.total_conflicts == 0
        else:
            assert summary.total_conflicts == count
            assert len(entries) == (min(count, 32) if level is AuditLevel.FULL else min(count, 8))
        return {
            "rows": rows,
            "value_columns": columns,
            "sources": 3,
            "wall_seconds": seconds,
            "input_sha256": input_digest,
            "data_sha256": frame_digest(result),
            "lineage_sha256": hashlib.sha256(
                json.dumps(lineage, sort_keys=True).encode()
            ).hexdigest(),
            "enabled_total": summary.total_conflicts,
            "retained": len(entries),
        }

    execute(8, 3)  # Same declared warmup in every fresh interpreter.
    workloads = [execute(128, 3), execute(512, 8)]
    raw_peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    report = {
        "pid": os.getpid(),
        "audit": audit,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "backend": {name: importlib.metadata.version(name) for name in ("pandas", "numpy")},
        "peak_process_rss_bytes": raw_peak if sys.platform == "darwin" else raw_peak * 1024,
        "workloads": workloads,
    }
    output.write_text(json.dumps(report, indent=2))


if __name__ == "__main__":
    _audit_worker(sys.argv[1], Path(sys.argv[2]))
