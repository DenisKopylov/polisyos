from __future__ import annotations

import os
from pathlib import Path

import pytest

from polisyos.runtime.quality.credal_reference import (
    AdmissibleCompletion,
    CredalReference,
    CredalReferenceEdge,
    all_essential_confirmed,
    bind_grounding_certificate_reference,
    build_credal_reference,
    build_grounding_backend_availability,
    derive_variable_alignment_edge,
    essential_edge_scope_definition,
    reference_certificate_staleness,
    reference_lift,
    replace_reference_edge,
)

REPO_ROOT = Path(__file__).resolve().parents[4]


@pytest.fixture(scope="module")
def reference() -> CredalReference:
    os.environ.setdefault("JAX_PLATFORM_NAME", "cpu")
    os.environ.setdefault("JAX_PLATFORMS", "cpu")
    return build_credal_reference(REPO_ROOT)


def test_contested_edge_lifts_set_valued_and_blocks_confirmation(
    reference: CredalReference,
) -> None:
    contested = _first_edge(reference, "L2_CONTESTED_EDGE", "contested")

    lift = reference_lift(reference, [contested.key])
    lifted = lift[f"{contested.modality}::{contested.edge_id}"]

    assert lifted["status"] == "contested"
    assert lifted["is_set_valued"] is True
    assert len(lifted["admissible_completions"]) > 1
    assert all_essential_confirmed(reference, [contested.key]) is False
    assert "scalar_confidence" not in str(lifted)


def test_fake_edge_fails_closed_out_of_scope(reference: CredalReference) -> None:
    fake_key = ("L2_CAUSAL_EDGE", "cg0_fake_novel_edge_not_in_reference")

    lift = reference_lift(reference, [fake_key])
    lifted = lift["L2_CAUSAL_EDGE::cg0_fake_novel_edge_not_in_reference"]

    assert lifted["status"] == "out_of_scope"
    assert all_essential_confirmed(reference, [fake_key]) is False


def test_free_grow_alignment_statuses_without_known_edge_table() -> None:
    edge = derive_variable_alignment_edge(
        {
            "approved": True,
            "canonical_name": "cg0.free_grow_reference_probe",
            "confidence": 0.91,
            "method": "unit_test_free_grow_probe",
            "synonym": "cg0 novel alignment synonym",
        }
    )

    assert edge.status == "confirmed"
    assert edge.key == (
        "L2_VARIABLE_ALIGNMENT",
        "cg0 novel alignment synonym->cg0.free_grow_reference_probe",
    )
    assert edge.provenance["signals"]["method"] == "unit_test_free_grow_probe"


def test_expanded_essential_scope_classes_are_counted(reference: CredalReference) -> None:
    counts = reference.denominator_counts()
    scope = essential_edge_scope_definition()
    modalities = {
        edge_class["modality"] for edge_class in scope["included_edge_classes"]
    }

    assert "L2_FAMILY_EDGE" in modalities
    assert "L2_MODERATION_EDGE" in modalities
    assert "L2_DATA_FORGE_VARIABLE_ALIGNMENT" in modalities
    assert "L3_REFERENCE_EDGE" in modalities
    assert counts["L2_FAMILY_EDGE"]["total"] == 15945
    assert counts["L2_MODERATION_EDGE"]["total"] == 25035
    assert counts["L2_DATA_FORGE_VARIABLE_ALIGNMENT"]["total"] == 20326
    assert counts["L3_REFERENCE_EDGE"]["total"] == 73793


def test_reference_repair_stales_dependent_certificate(
    reference: CredalReference,
) -> None:
    contested = _first_edge(reference, "L2_CONTESTED_EDGE", "contested")
    certificate = bind_grounding_certificate_reference(
        reference,
        certificate_id="cg0-unit-staling",
        edge_scope=[contested.key],
    )
    repaired_edge = CredalReferenceEdge(
        modality=contested.modality,
        edge_id=contested.edge_id,
        status="confirmed",
        admissible_completions=(
            AdmissibleCompletion(
                "fixed",
                {"repaired_from": contested.edge_id},
                "unit_test_reference_repair",
            ),
        ),
        provenance={**dict(contested.provenance), "unit_test": "reference_repair"},
        unit=contested.unit,
        scale=contested.scale,
    )

    repaired_reference = replace_reference_edge(reference, repaired_edge)
    staleness = reference_certificate_staleness(certificate, repaired_reference)

    assert repaired_reference.reference_epoch != reference.reference_epoch
    assert staleness.status == "stale"
    assert "scoped_edge_hash_changed" in staleness.reasons


def test_backend_availability_pins_cp_sat_and_defers_dense() -> None:
    backend = build_grounding_backend_availability().to_payload()

    assert backend["required_backend_status"] == "available"
    assert backend["solver"]["name"] == "ortools_cp_sat"
    assert backend["solver"]["available"] is True
    assert backend["solver"]["unsat_core"] == "assumptions"
    assert backend["milp_fallback"]["solver"] == "HiGHS"
    assert backend["sparse"]["name"] == "duckdb_fts"
    assert backend["ann"]["name"] == "hnswlib"
    assert backend["dense"]["status"] == "deferred"


def _first_edge(
    reference: CredalReference,
    modality: str,
    status: str,
) -> CredalReferenceEdge:
    for edge in sorted(reference.essential_edges.values(), key=lambda item: item.key):
        if edge.modality == modality and edge.status == status:
            return edge
    raise AssertionError(f"missing {modality} edge with status {status}")
