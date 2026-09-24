"""Run only CR1 and its named existing owner test through the cold composition root."""

import sys

import polisyos.runtime.http.services.control  # noqa: F401 - supported cold import order
import pytest

if __name__ == "__main__":
    raise SystemExit(pytest.main([
        "tests/unit/runtime/quality/test_adaptation_transition.py",
        "tests/unit/runtime/http/test_control_plane_store.py::"
        "test_control_plane_store_tracks_worker_leases_and_outbox",
        "-o", "addopts=", "-q", "-s", *sys.argv[1:],
    ]))
