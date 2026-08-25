"""Behavioral RED witnesses for the DS10 manifest and picker strangles."""

from __future__ import annotations

import importlib.util
from pathlib import Path

CHECKER_PATH = (
    Path(__file__).resolve().parents[3] / "architecture/atlas_surfaces/check_atlas_enforcement.py"
)


def _checker():
    spec = importlib.util.spec_from_file_location("ds10_atlas_enforcement", CHECKER_PATH)
    assert spec is not None and spec.loader is not None
    checker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checker)
    return checker


def test_control_capability_manifest_has_no_authored_feature_rows() -> None:
    """Require the control manifest to project producer-backed discovery only."""
    checker = _checker()

    assert checker.control_capability_manifest_contributors() == ()


def test_capability_menu_rejects_hardcoded_picker_rows_and_id_branches() -> None:
    """Require generic capability-menu consumption without ID-specific branches."""
    checker = _checker()
    sources = {
        "apps/runtime-dashboard/src/features/evidence/CapabilityDiscoveryPanel.tsx": (
            "const menu = [{ capability_ref: 'adapter-42', kind: 'method' }];\n"
            "if (result.capability_ref === 'adapter-42' || result.kind === 'method') return menu;\n"
        ),
        "apps/runtime-dashboard/src/app/surfaces/workspaceConfig.ts": (
            "export const workspaceConfig = { route: 'runs', tab: 'overview' };\n"
        ),
    }

    rejected = checker.check_capability_discovery_result_boundary(sources)

    assert any(error.startswith("hardcoded_discovery_result:") for error in rejected)
    assert not any("workspaceConfig" in error for error in rejected)
