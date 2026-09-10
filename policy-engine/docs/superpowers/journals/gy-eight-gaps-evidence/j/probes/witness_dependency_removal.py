"""Remove actual witness dependency admission while keeping the real GX packet.

Run only after the J source/native tests are explicitly released and installed.
No product file is edited. The retained native controls exercise the existing
full GX semantic consumer against complete real report/basis data.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from tools.quality.validation import check_layer3_gy_loop_artifacts as owner


def main() -> int:
    with patch.object(owner, "_j_require_production_witness_dependency", lambda **kwargs: None):
        return pytest.main([
            "-q", "-rA", "--show-capture=no", "--tb=short",
            "tests/unit/runtime/quality/workspace/test_production_case_proof_custody.py::test_production_p28_refuses_detached_named_witness_dependency",
        ])


if __name__ == "__main__":
    raise SystemExit(main())
