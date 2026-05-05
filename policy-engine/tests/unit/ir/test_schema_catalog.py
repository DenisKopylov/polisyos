from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from polisyos.ir import (
    enumerate_ir_exports,
    get_ir_schema_catalog,
    get_ir_type,
    list_ir_types,
)
from polisyos.ir.schema_catalog import IRPublicStatus


def test_schema_catalog_exposes_root_metadata() -> None:
    catalog = get_ir_schema_catalog()
    assert len(catalog.types) >= 700

    hte = get_ir_type("HTEResult")
    assert hte.schema_version == "1.0"
    assert hte.public_status is IRPublicStatus.ROOT_FACADE
    assert hte.docs_link.endswith("#polisyos-ir-analytics-hte-hteresult")

    subgroup_field = next(field for field in hte.fields if field.name == "subgroup_effects")
    assert "polisyos.ir.analytics.hte.SubgroupEffect" in subgroup_field.references


def test_schema_catalog_lists_section_filters_and_bridge_exports() -> None:
    observation_types = list_ir_types(section="observation")
    assert any(entry.name == "ObservationRecord" for entry in observation_types)
    governance_types = list_ir_types(section="governance")
    assert any(entry.name == "TemporalPolicyConstraint" for entry in governance_types)

    analytics_exports = enumerate_ir_exports("analytics")
    world_exports = enumerate_ir_exports("world")
    assert any(entry.export_name == "DoWhyGraphBridge" for entry in analytics_exports)
    assert any(entry.export_name == "LatentConfounderContract" for entry in analytics_exports)
    assert any(entry.export_name == "ProvODocument" for entry in world_exports)


def test_generated_reference_catalog_is_current() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    result = subprocess.run(
        [sys.executable, "tools/quality/diagnostics/generate_ir_reference_catalog.py", "--check"],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr or result.stdout
