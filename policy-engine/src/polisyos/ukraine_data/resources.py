"""Resource tracking helpers for the Ukraine Part B build stack."""

from __future__ import annotations

import json
import os
import platform
import resource
import shutil
import time
from pathlib import Path
from typing import Any

from polisyos.batch_common.paths import ensure_dirs


def directory_size_bytes(path: Path) -> int:
    total = 0
    if not path.exists():
        return 0
    for root, _, files in os.walk(path):
        for name in files:
            file_path = Path(root) / name
            try:
                total += file_path.stat().st_size
            except FileNotFoundError:
                continue
    return total


def directory_size_gib(path: Path) -> float:
    """Return recursive directory size in GiB."""

    return float(directory_size_bytes(path)) / (1024.0 ** 3)


def current_peak_rss_gib() -> float:
    """Return the current process peak RSS in GiB."""

    raw = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if platform.system() == "Darwin":
        bytes_value = float(raw)
    else:
        bytes_value = float(raw) * 1024.0
    return bytes_value / (1024.0 ** 3)


class ResourceTracker:
    """Track wall time and storage usage for one stage execution."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.started_at = time.monotonic()
        self.initial_bytes = directory_size_bytes(root)

    @property
    def peak_rss_gib(self) -> float:
        """Return the current peak RSS snapshot for the tracked process."""

        return current_peak_rss_gib()

    def finish(self) -> dict[str, float]:
        """Return elapsed, disk delta, and peak RSS metrics."""

        elapsed_s = time.monotonic() - self.started_at
        final_bytes = directory_size_bytes(self.root)
        return {
            "elapsed_s": elapsed_s,
            "disk_delta_gib": max(0.0, final_bytes - self.initial_bytes) / (1024.0 ** 3),
            "peak_rss_gib": current_peak_rss_gib(),
        }


def append_resource_usage(path: Path, payload: dict[str, Any]) -> None:
    """Append one JSON line to the resource-usage stream."""

    ensure_dirs(path.parent)
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=True, sort_keys=True))
        handle.write("\n")


def write_stage_metrics(path: Path, payload: dict[str, Any]) -> Path:
    """Write the latest stage metrics snapshot."""

    ensure_dirs(path.parent)
    path.write_text(
        json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return path


def write_prometheus_metrics(path: Path, metrics: dict[str, float]) -> Path:
    """Write a minimal Prometheus textfile collector payload."""

    ensure_dirs(path.parent)
    lines = []
    for key, value in sorted(metrics.items()):
        metric_name = key if key.startswith("ukraine_data_") else f"ukraine_data_{key}"
        metric_name = metric_name.replace("-", "_")
        metric_base_name = metric_name.split("{", 1)[0]
        lines.append(f"# TYPE {metric_base_name} gauge")
        lines.append(f"{metric_name} {float(value)}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def free_disk_gib(path: Path) -> float:
    """Return free disk space for the filesystem containing ``path``."""

    probe_path = path
    while not probe_path.exists() and probe_path != probe_path.parent:
        probe_path = probe_path.parent
    usage = shutil.disk_usage(probe_path)
    return float(usage.free) / (1024.0 ** 3)


def total_ram_gib() -> float:
    """Return total physical RAM in GiB when available."""

    page_size = os.sysconf("SC_PAGE_SIZE")
    pages = os.sysconf("SC_PHYS_PAGES")
    return float(page_size * pages) / (1024.0 ** 3)


__all__ = [
    "ResourceTracker",
    "append_resource_usage",
    "current_peak_rss_gib",
    "directory_size_bytes",
    "directory_size_gib",
    "free_disk_gib",
    "total_ram_gib",
    "write_prometheus_metrics",
    "write_stage_metrics",
]
