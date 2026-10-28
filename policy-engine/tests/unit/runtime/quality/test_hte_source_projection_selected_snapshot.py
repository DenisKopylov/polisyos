"""Actual selected-CAS source joins without fitting an EconML estimator."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import pytest

from polisyos.core.artifacts import ArtifactRef
from polisyos.core.artifacts.canonical_profile import CoreJsonReadLimits
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.security.tenant_context import tenant_scope
from polisyos.runtime.quality.hte_source_projection import verify_hte_source_projection_join
from polisyos.scientist.methods.search.uncertainty import (
    SearchHTESourceProjectionError,
    SearchInputDependency,
    SearchUncertaintyHTERequestProjection,
)
from tests.unit.runtime.http.test_search_hte_first_assessment_outbox import (
    _put_profile_bound_v2_hte_source,
)


@dataclass(frozen=True)
class _SelectedBasis:
    selected_method_input_ref: ArtifactRef
    selected_state_input_refs: tuple[SearchInputDependency, ...]
    unit_scope_ref: ArtifactRef
    unit_binding_status: Literal["bound"] = "bound"


@pytest.mark.parametrize(
    ("variant", "reason"),
    [
        ("joined", None),
        ("trimmed-unit", None),
        ("missing-edge", "source_assignment_edge_missing_or_ambiguous"),
        ("duplicate-cell", "acquire_data:value_owner_unit_binding_ambiguous"),
        ("mixed-units", "acquire_data:value_owner_unit_binding_ambiguous"),
        ("alternate-profile", "source_unit_scope_profile_mismatch"),
    ],
)
def test_actual_selected_snapshot_join_preserves_limits(tmp_path, variant, reason) -> None:
    """A unit-bound declaration cannot substitute for the actual selected join."""
    store = FileSystemCAS(tmp_path / "cas", ownership_enforced=True)
    with tenant_scope(None, tenant_id="tenant-native-join", cell_id="cell-native-join"):
        source, assignment, profile = _put_profile_bound_v2_hte_source(
            store,
            tenant_id="tenant-native-join",
            cell_id="cell-native-join",
            tmp_path=tmp_path,
            run_id="selected-" + variant,
            include_assignment_edge=variant != "missing-edge",
            projection_fault=variant
            if variant in {"duplicate-cell", "mixed-units", "trimmed-unit"}
            else None,
            alternate_unit_scope_profile=variant == "alternate-profile",
        )
        basis = _SelectedBasis(
            source,
            (SearchInputDependency(role_path="source_variable_assignment", ref=assignment),),
            profile,
        )
        request = SearchUncertaintyHTERequestProjection(
            estimand="mean_effect_over_selected_x",
            target_scope="selected_evaluation_rows",
            outcome_variable_id="outcome.effect",
            treatment_variable_id="treatment.policy",
            control_value=0.0,
            treated_value=1.0,
            alpha=0.05,
            requested_guarantee="backend_conditional_interval",
        )
        kwargs = {
            "store": store,
            "selected_method_input_ref": source,
            "basis": basis,
            "request_projection": request,
            "limits": CoreJsonReadLimits(
                max_bytes=8_388_608, max_depth=64, max_elements=200_000, max_manifest_bytes=65_536
            ),
        }
        if reason is not None:
            with pytest.raises(SearchHTESourceProjectionError) as refused:
                verify_hte_source_projection_join(**kwargs)
            assert refused.value.reason_code == reason
        else:
            joined = verify_hte_source_projection_join(**kwargs)
            assert joined.selected_method_input_ref == source
            assert joined.assignment_ref == assignment
            assert joined.outcome_profile_ref == profile
            assert joined.role_mapping_status == "consumer_asserted"
            assert joined.owner_issuance_status == "not_established"
            assert joined.semantic_alignment_status == "not_established"
