"""Red witness for the unimplemented DS10 discovery posture contract."""

from __future__ import annotations

import pytest


def test_capability_discovery_postures_use_three_independent_producers() -> None:
    """Require discovery, execution, and authority to have distinct producers."""
    pytest.fail(
        "DS10 C01 missing: no capability-discovery composer proves three independent producers"
    )
