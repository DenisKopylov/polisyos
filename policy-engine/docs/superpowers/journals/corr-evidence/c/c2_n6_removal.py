"""Remove the N6 transition binding in memory while retaining its markers."""

from unittest.mock import patch

import pytest


def main() -> int:
    """Require the unchanged actual-owner governing-value negative to turn red."""
    from tools.quality.validation import check_layer3_gy_generation_cycle_contract as owner

    prefix = "tests/repo_quality/tools/test_layer3_gy_generation_cycle_contract.py::"
    with patch.object(owner, "_is_authorized_controller_source_reissue", lambda *_args: True):
        return int(
            pytest.main(
                [
                    prefix + "test_source_reissue_preserves_actual_fresh_payload",
                    prefix + "test_source_reissue_rejects_every_changed_binding"
                    "[unrelated_governing_value]",
                    "-q",
                ]
            )
        )


if __name__ == "__main__":
    raise SystemExit(main())
