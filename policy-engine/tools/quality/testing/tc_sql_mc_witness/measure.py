"""Measure the present Cloud resource envelope and select conservative phase caps."""

from __future__ import annotations

import json
import os
import platform
import shutil
import sys
from pathlib import Path

root = Path(sys.argv[1]).resolve()
scratch = Path(sys.argv[2]).resolve()


def read(path: str) -> str | None:
    """Read one resource-control value, preserving unreadable as unknown."""
    try:
        return Path(path).read_text().strip()
    except OSError:
        return None


info = {}
for line in (read("/proc/meminfo") or "").splitlines():
    parts = line.split()
    if len(parts) >= 2 and parts[0] in ("MemTotal:", "MemAvailable:"):
        info[parts[0][:-1]] = int(parts[1]) * 1024
maximum = read("/sys/fs/cgroup/memory.max")
current = read("/sys/fs/cgroup/memory.current")
available = info.get("MemAvailable")
if maximum and current and maximum.isdigit() and current.isdigit():
    remaining = max(0, int(maximum) - int(current))
    available = min(available, remaining) if available is not None else remaining
output_disk = shutil.disk_usage(root)
scratch_disk = shutil.disk_usage(scratch)
disk_floor = max(1024**3, int(scratch_disk.total * 0.05))
output_floor = max(1024**3, int(output_disk.total * 0.05))
mem_cap = (
    min(6 * 1024**3, max(0, available - max(512 * 1024**2, int(available * 0.15))))
    if available is not None
    else None
)
safe = (
    mem_cap is not None
    and mem_cap >= 1200 * 1024**2
    and scratch_disk.free >= disk_floor + 1024**3
    and output_disk.free >= output_floor + 256 * 1024**2
)
print(
    json.dumps(
        {
            "platform": platform.platform(),
            "python": sys.version,
            "cpu_count": os.cpu_count(),
            "meminfo_bytes": info,
            "cgroup_max_raw": maximum,
            "cgroup_current_raw": current,
            "effective_available_bytes": available,
            "scratch_path": str(scratch),
            "scratch_total_bytes": scratch_disk.total,
            "scratch_free_bytes": scratch_disk.free,
            "disk_floor_bytes": disk_floor,
            "output_path": str(root),
            "output_total_bytes": output_disk.total,
            "output_free_bytes": output_disk.free,
            "output_floor_bytes": output_floor,
            "memory_cap_bytes": mem_cap,
            "safe_to_start": safe,
            "formula": "effective available is min(MemAvailable, cgroup max-current) when both known; reserve max(512 MiB, 15%); process cap <= 6 GiB; scratch and output floors each max(1 GiB, 5% of their filesystem total), plus 1 GiB initial scratch and 256 MiB initial output allowance; RSS polling is sampled, not a hard kernel limit.",
        },
        indent=2,
        sort_keys=True,
    )
)
