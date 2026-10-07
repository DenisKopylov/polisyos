"""A stdlib-only coordinator preserves distinct CAS producer/consumer processes."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration


def _worker(tmp_path, action):
    worker = Path(__file__).with_name("vector_transfer_process_worker.py")
    argv = [sys.executable, str(worker), action, str(tmp_path)]
    result = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    (tmp_path / (action + ".txt")).write_bytes(result.stdout)
    print("ACTUAL_PROCESS_COMMAND", argv, "EXIT", result.returncode)
    print(result.stdout.decode(errors="replace"))
    assert result.returncode == 0


def test_second_process_consumes_exact_cas_snapshot_and_preserves_failed_generation(tmp_path):
    for backend in ("hnswlib", "torch", "botorch", "gpytorch"):
        if importlib.util.find_spec(backend) is None:
            pytest.skip(f"UNRUN: second-process transfer profile requires {backend}")
    print("COORDINATOR_TORCH_IMPORTED", "torch" in sys.modules)
    _worker(tmp_path, "produce")
    _worker(tmp_path, "receive")


def test_actual_native_loader_exception_keeps_the_old_generation(tmp_path):
    if importlib.util.find_spec("hnswlib") is None:
        pytest.skip("UNRUN: native HNSW loader control requires hnswlib")
    _worker(tmp_path, "corrupted_native")
