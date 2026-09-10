"""Exercise M1 producer imports against the wrappers' actual write closure."""

from __future__ import annotations

from importlib import import_module
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.parametrize(
    ("workflow_name", "family_id", "output_names"),
    [
        (
            "check_layer3_gy_n10_cg1_l2_relation_census",
            "policy-design-case-layer3-gy-n10-cg1-l2-relation-census",
            ("layer3_gy_n10_cg1_l2_relation_census.json",),
        ),
        (
            "check_layer3_gy_n13a_acquisition_census",
            "policy-design-case-layer3-gy-n13a-acquisition-census",
            ("layer3_gy_n13a_acquisition_census.json",),
        ),
        (
            "check_layer3_gy_n13b_acquisition_contract",
            "policy-design-case-layer3-gy-n13b-acquisition-executor",
            (
                "layer3_gy_n13b_acquisition_executor_contract.json",
                "layer3_gy_n13b_lifecycle_manifest.json",
                "layer3_gy_n13b_derivation_universality.json",
            ),
        ),
    ],
)
def test_registry_importer_observes_actual_wrapper_write_closure(
    workflow_name: str, family_id: str, output_names: tuple[str, ...]
) -> None:
    """Missing declarations must fail through the real lifecycle import seam."""

    validator = import_module(
        "tools.quality.validation.check_layer3_gy_generated_public_lifecycle_audit"
    )
    workflow = f"tools/quality/validation/{workflow_name}.py"
    issues: list[dict[str, Any]] = []

    outputs = validator._load_producer_declared_outputs(
        REPO_ROOT,
        REPO_ROOT / workflow,
        family_id,
        workflow,
        issues,
        scope_exclusions=(set(), set()),
    )

    assert issues == [], issues
    assert outputs == {
        f"architecture/policy_design_case/{output_name}" for output_name in output_names
    }
