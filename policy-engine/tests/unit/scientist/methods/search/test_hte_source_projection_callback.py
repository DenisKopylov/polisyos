"""Behavioral controls for the consumer-owned HTE source verification seam."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Literal, cast

import pytest

from polisyos.core.artifacts import ArtifactRef
from polisyos.core.artifacts.canonical_profile import CoreJsonReadLimits
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.scientist.methods.search.uncertainty import (
    SearchHTESourceProjectionError,
    SearchHTESourceProjectionJoin,
    SearchInputDependency,
    SearchUncertaintyHTERequestProjection,
    _resolve_hte_source_projection_join,
)


@dataclass(frozen=True)
class _SelectedBasis:
    selected_method_input_ref: ArtifactRef
    selected_state_input_refs: tuple[SearchInputDependency, ...]
    unit_scope_ref: ArtifactRef | None
    unit_binding_status: Literal["bound", "unknown"] = "bound"


def _ref(kind: str, digit: str) -> ArtifactRef:
    return ArtifactRef(
        artifact_id="sha256:" + digit * 64,
        kind=kind,
        media_type="application/json",
        manifest_profile_sha256="sha256:" + "f" * 64,
    )


def _selected_inputs() -> tuple[_SelectedBasis, SearchUncertaintyHTERequestProjection]:
    source_ref = _ref("ir.observation_method_input", "1")
    assignment_ref = _ref("runtime.value_owner_source_variable_assignment", "2")
    unit_ref = _ref("runtime.value_data_profile", "3")
    return (
        _SelectedBasis(
            selected_method_input_ref=source_ref,
            selected_state_input_refs=(
                SearchInputDependency(role_path="source_variable_assignment", ref=assignment_ref),
            ),
            unit_scope_ref=unit_ref,
        ),
        SearchUncertaintyHTERequestProjection(
            estimand="mean_effect_over_selected_x",
            target_scope="selected_evaluation_rows",
            outcome_variable_id="outcome.effect",
            treatment_variable_id="treatment.policy",
            control_value=0.0,
            treated_value=1.0,
            alpha=0.05,
            requested_guarantee="backend_conditional_interval",
        ),
    )


def _limits() -> CoreJsonReadLimits:
    return CoreJsonReadLimits(
        max_bytes=8_388_608,
        max_depth=64,
        max_elements=200_000,
        max_manifest_bytes=65_536,
    )


def test_missing_source_verifier_is_unavailable_without_importing_an_upper_owner(tmp_path):
    """Absence cannot activate a content join or require Runtime in Scientist."""
    basis, request = _selected_inputs()
    joined, refusal = _resolve_hte_source_projection_join(
        verifier=None,
        store=FileSystemCAS(tmp_path / "cas"),
        selected_method_input_ref=basis.selected_method_input_ref,
        basis=basis,
        request_projection=request,
        limits=_limits(),
    )
    assert joined is None
    assert refusal == "source_projection_verifier_unavailable"


def test_source_verifier_receives_frozen_inputs_and_returns_only_bounded_labels(tmp_path):
    """The seam forwards concrete inputs and reconciles the returned subject."""
    basis, request = _selected_inputs()
    store = FileSystemCAS(tmp_path / "cas")
    limits = _limits()
    calls = []
    expected = SearchHTESourceProjectionJoin(
        selected_method_input_ref=basis.selected_method_input_ref,
        assignment_ref=basis.selected_state_input_refs[0].ref,
        outcome_profile_ref=basis.unit_scope_ref,
    )

    def verify(**kwargs):
        calls.append(kwargs)
        return expected

    joined, refusal = _resolve_hte_source_projection_join(
        verifier=verify,
        store=store,
        selected_method_input_ref=basis.selected_method_input_ref,
        basis=basis,
        request_projection=request,
        limits=limits,
    )
    assert calls == [
        {
            "store": store,
            "selected_method_input_ref": basis.selected_method_input_ref,
            "basis": basis,
            "request_projection": request,
            "limits": limits,
        }
    ]
    assert joined is expected
    assert refusal is None
    assert joined.role_mapping_status == "consumer_asserted"
    assert joined.owner_issuance_status == "not_established"
    assert joined.semantic_alignment_status == "not_established"
    assert joined.source_time_status == "not_established"


@pytest.mark.parametrize(
    "changed_field", ["selected_method_input_ref", "assignment_ref", "outcome_profile_ref"]
)
def test_source_verifier_result_cannot_switch_a_selected_manifest_profile(tmp_path, changed_field):
    """A typed positive for another selected view cannot activate this join."""
    basis, request = _selected_inputs()
    payload = {
        "selected_method_input_ref": basis.selected_method_input_ref,
        "assignment_ref": basis.selected_state_input_refs[0].ref,
        "outcome_profile_ref": basis.unit_scope_ref,
    }
    original = payload[changed_field]
    assert original is not None
    payload[changed_field] = original.model_copy(
        update={"manifest_profile_sha256": "sha256:" + "e" * 64}
    )
    different_view = SearchHTESourceProjectionJoin(**payload)
    joined, refusal = _resolve_hte_source_projection_join(
        verifier=lambda **_kwargs: different_view,
        store=FileSystemCAS(tmp_path / "cas"),
        selected_method_input_ref=basis.selected_method_input_ref,
        basis=basis,
        request_projection=request,
        limits=_limits(),
    )
    assert joined is None
    assert refusal == "source_projection_verifier_subject_mismatch"


def test_optional_source_verifier_typed_refusal_is_a_limit_not_a_completion_failure(tmp_path):
    """An expected source-data refusal stays local to candidate routing."""
    basis, request = _selected_inputs()

    def refuse(**_kwargs):
        raise SearchHTESourceProjectionError("source_projection_rows_invalid")

    joined, refusal = _resolve_hte_source_projection_join(
        verifier=refuse,
        store=FileSystemCAS(tmp_path / "cas"),
        selected_method_input_ref=basis.selected_method_input_ref,
        basis=basis,
        request_projection=request,
        limits=_limits(),
    )
    assert joined is None
    assert refusal == "source_projection_rows_invalid"


def test_present_but_untyped_verifier_result_cannot_activate_a_join(tmp_path):
    """Callback presence and truthiness are not a content-join result."""
    basis, request = _selected_inputs()
    joined, refusal = _resolve_hte_source_projection_join(
        verifier=lambda **_kwargs: cast("SearchHTESourceProjectionJoin", True),
        store=FileSystemCAS(tmp_path / "cas"),
        selected_method_input_ref=basis.selected_method_input_ref,
        basis=basis,
        request_projection=request,
        limits=_limits(),
    )
    assert joined is None
    assert refusal == "source_projection_verifier_result_invalid"


@pytest.mark.parametrize("assignment_count", [0, 2])
def test_verifier_result_cannot_hide_missing_or_ambiguous_frozen_assignment(
    tmp_path, assignment_count
):
    """The consumer independently reconciles the exact selected assignment set."""
    basis, request = _selected_inputs()
    ambiguous_basis = replace(
        basis, selected_state_input_refs=basis.selected_state_input_refs * assignment_count
    )
    claimed_join = SearchHTESourceProjectionJoin(
        selected_method_input_ref=basis.selected_method_input_ref,
        assignment_ref=basis.selected_state_input_refs[0].ref,
        outcome_profile_ref=basis.unit_scope_ref,
    )
    joined, refusal = _resolve_hte_source_projection_join(
        verifier=lambda **_kwargs: claimed_join,
        store=FileSystemCAS(tmp_path / "cas"),
        selected_method_input_ref=basis.selected_method_input_ref,
        basis=ambiguous_basis,
        request_projection=request,
        limits=_limits(),
    )
    assert joined is None
    assert refusal == "source_projection_verifier_subject_mismatch"
