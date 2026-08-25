"""Red witnesses for the unimplemented DS10 manifest strangle."""

from __future__ import annotations

import pytest


def test_control_capability_manifest_has_no_authored_feature_rows() -> None:
    """Require the control manifest to project producer-backed discovery only."""
    pytest.fail("DS10 C01 missing: control capability manifest still has authored feature rows")


def test_capability_menu_rejects_hardcoded_picker_rows_and_id_branches() -> None:
    """Require generic capability-menu consumption without ID-specific branches."""
    pytest.fail("DS10 C01 missing: capability menu has no generic picker strangle")
