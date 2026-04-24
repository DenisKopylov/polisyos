#!/usr/bin/env python3
"""Benchmark for streaming_windowed ingestion mode.

Measures:
  - chunks/sec throughput
  - peak RSS memory usage
  - CAS write throughput (bytes/sec)

Usage:
    python benchmarks/streaming_windowed_bench.py [--chunks N] [--rows-per-chunk M]
"""

from __future__ import annotations

import argparse
import resource
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

# Ensure src is on the path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


def _get_rss_mb() -> float:
    """Get current RSS in MB (macOS/Linux)."""
    usage = resource.getrusage(resource.RUSAGE_SELF)
    # macOS returns bytes, Linux returns KB
    if sys.platform == "darwin":
        return usage.ru_maxrss / (1024 * 1024)
    return usage.ru_maxrss / 1024


def _generate_mock_chunks(num_chunks: int, rows_per_chunk: int) -> list[dict]:
    """Generate mock chunk data for benchmarking."""
    chunks = []
    for i in range(num_chunks):
        chunks.append(
            {
                "chunk_index": i,
                "row_count": rows_per_chunk,
                "is_first": i == 0,
                "is_last": i == num_chunks - 1,
                "data": [
                    {"time": f"2025-{(i % 12) + 1:02d}", "value": float(j + i * rows_per_chunk)}
                    for j in range(rows_per_chunk)
                ],
            }
        )
    return chunks


def run_benchmark(num_chunks: int, rows_per_chunk: int) -> None:
    from polisyos.fabric.data_plane.modes import run_streaming_windowed

    mock_chunks = _generate_mock_chunks(num_chunks, rows_per_chunk)
    total_rows = num_chunks * rows_per_chunk

    manifest = {"datasets": [{"connector_id": "bench.conn", "dataset_id": "bench_ds"}]}

    with tempfile.TemporaryDirectory(prefix="polisyos_bench_") as tmpdir:
        cas_root = Path(tmpdir) / ".polisyos"

        rss_before = _get_rss_mb()
        t0 = time.perf_counter()

        with patch(
            "polisyos.fabric.data_plane.modes._fetch_stream_for_dataset",
            return_value=mock_chunks,
        ):
            result = run_streaming_windowed(
                connector_manifest=manifest,
                source="benchmark",
                license_name="open",
                cas_root=cas_root,
                produce_snapshot=True,
            )

        t1 = time.perf_counter()
        rss_after = _get_rss_mb()

        elapsed = t1 - t0
        chunks_per_sec = num_chunks / elapsed if elapsed > 0 else float("inf")
        rows_per_sec = total_rows / elapsed if elapsed > 0 else float("inf")

        # Measure CAS directory size
        cas_size_bytes = sum(f.stat().st_size for f in cas_root.rglob("*") if f.is_file())

        print("=" * 60)
        print("Streaming Windowed Benchmark Results")
        print("=" * 60)
        print(f"  Chunks:          {num_chunks}")
        print(f"  Rows/chunk:      {rows_per_chunk}")
        print(f"  Total rows:      {total_rows}")
        print(f"  Elapsed:         {elapsed:.3f}s")
        print(f"  Chunks/sec:      {chunks_per_sec:.1f}")
        print(f"  Rows/sec:        {rows_per_sec:.1f}")
        print(f"  RSS before:      {rss_before:.1f} MB")
        print(f"  RSS after:       {rss_after:.1f} MB")
        print(f"  Peak RSS delta:  {rss_after - rss_before:.1f} MB")
        print(f"  CAS total size:  {cas_size_bytes / 1024:.1f} KB")
        print(f"  CAS write rate:  {cas_size_bytes / elapsed / 1024:.1f} KB/s")
        print(f"  Datasets:        {result.datasets_fetched}")
        print(f"  Has evidence:    {result.evidence_bundle_ref is not None}")
        print(f"  Has snapshot:    {result.data_snapshot_ref is not None}")
        print("=" * 60)


def main() -> None:
    parser = argparse.ArgumentParser(description="Streaming windowed benchmark")
    parser.add_argument("--chunks", type=int, default=50, help="Number of chunks")
    parser.add_argument("--rows-per-chunk", type=int, default=100, help="Rows per chunk")
    args = parser.parse_args()

    print(f"Running benchmark: {args.chunks} chunks x {args.rows_per_chunk} rows/chunk")
    run_benchmark(args.chunks, args.rows_per_chunk)


if __name__ == "__main__":
    main()
