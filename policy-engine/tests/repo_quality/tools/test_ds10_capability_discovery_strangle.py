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


def test_control_capability_manifest_has_no_unchecked_authored_feature_rows() -> None:
    """Reject an import-aliased constructor that contributes to manifest features."""
    checker = _checker()
    sources = {
        "src/polisyos/runtime/http/services/control/generated_probe.py": (
            "from polisyos.core.contracts.control import (\n"
            "    CapabilityFeatureInfo as Feature,\n"
            "    CapabilityManifestResponse as Manifest,\n"
            ")\n"
            "def build(meta):\n"
            "    projected = [Feature(key='generated', label='Generated', "
            "description='probe', category='probe')]\n"
            "    return Manifest(meta=meta, features=projected)\n"
        )
    }

    contributors = checker.control_capability_manifest_contributors(sources)

    assert len(contributors) == 1
    assert contributors[0].startswith(
        "src/polisyos/runtime/http/services/control/generated_probe.py:"
    )


def test_control_capability_openapi_example_has_no_authored_feature_rows() -> None:
    """The public example must exercise the same empty legacy feature plane."""
    from polisyos.runtime.http.app import export_runtime_openapi_schema

    schema = export_runtime_openapi_schema()
    operation = schema["paths"]["/api/v1/control/capabilities"]["get"]
    response = operation["responses"]["200"]["content"]["application/json"]
    example = response["examples"]["default"]["value"]

    assert example["features"] == []
    assert "execution_policy" in example["fallback_rules"]


def test_capability_menu_rejects_hardcoded_picker_rows_and_id_branches() -> None:
    """Require generic capability-menu consumption without ID-specific branches."""
    checker = _checker()
    generated_ref = "".join(("capability", "-", "probe", "-", "7"))
    sources = {
        "apps/runtime-dashboard/src/features/evidence/components/CapabilityDiscoveryPanel.tsx": (
            "import { rows } from './CapabilityDiscoveryRows';\nexport const panel = rows;\n"
        ),
        "apps/runtime-dashboard/src/features/evidence/components/CapabilityDiscoveryRows.tsx": (
            f"const selectedRef = '{generated_ref}';\n"
            "export const rows = [{ capability_ref: selectedRef, resource_kind: 'method' }];\n"
            "export function render(result: { capability_ref: string; resource_kind: string }) {\n"
            "  if (result.capability_ref === selectedRef) return rows;\n"
            "  if (result.resource_kind === 'method') return rows;\n"
            "  return [];\n"
            "}\n"
        ),
        "apps/runtime-dashboard/src/app/surfaces/workspaceConfig.ts": (
            "type WorkspaceConfig = { route: string; tab: string };\n"
            "export const workspaceConfig: WorkspaceConfig = { "
            "route: 'runs', tab: 'overview' };\n"
        ),
    }

    rejected = checker.check_capability_discovery_result_boundary(sources)

    assert any(error.startswith("hardcoded_discovery_result:") for error in rejected)
    assert not any("workspaceConfig" in error for error in rejected)
