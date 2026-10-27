"""Regression coverage for the debug SimulationResult identity boundary."""

from __future__ import annotations

import pytest

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.runtime.http.services.debug import (
    SimulationResultProjectionError,
    _artifact_refs_from_report_node,
    _require_exact_artifact_ref_binding,
    _unique_workflow_report_node,
)

_ARTIFACT_ID = "sha256:" + "a" * 64
_PROFILE_A = "sha256:" + "b" * 64
_PROFILE_B = "sha256:" + "c" * 64


def _ref(profile: str | None = _PROFILE_A) -> ArtifactRef:
    return ArtifactRef(
        artifact_id=_ARTIFACT_ID,
        kind="foundry.simulation_result",
        media_type="application/json",
        manifest_profile_sha256=profile,
    )


@pytest.mark.parametrize("conflicting_profile", [_PROFILE_B, None])
def test_exact_binding_refuses_profile_difference_or_omission(
    conflicting_profile: str | None,
) -> None:
    """The canonical complete identity treats neither profile variant as a wildcard."""
    with pytest.raises(
        SimulationResultProjectionError,
        match="conflicting simulation result ref",
    ):
        _require_exact_artifact_ref_binding(
            _ref(),
            (_ref(), _ref(conflicting_profile)),
        )


def test_relevant_malformed_node_ref_cannot_be_filtered_before_comparison() -> None:
    """A malformed same-ID sibling remains a fail-closed binding conflict."""
    report = {
        "nodes": [
            {
                "alias": "simulate",
                "artifacts": [
                    _ref().model_dump(mode="json"),
                    _ref().model_dump(mode="json")
                    | {"manifest_profile_sha256": "sha256:not-a-digest"},
                ],
            }
        ]
    }

    row = _unique_workflow_report_node(report, alias="simulate")
    assert row is not None
    with pytest.raises(
        SimulationResultProjectionError,
        match="malformed relevant artifact ref",
    ):
        _artifact_refs_from_report_node(row, relevant_artifact_id=_ref().artifact_id)


@pytest.mark.parametrize("second_profile", [_PROFILE_A, _PROFILE_B, None])
@pytest.mark.parametrize("reverse_rows", [False, True])
def test_named_node_intake_refuses_duplicate_rows_even_when_refs_agree(
    second_profile: str | None, reverse_rows: bool
) -> None:
    """Metadata and refs cannot select different rows of one ambiguous alias."""
    rows = [
        {"alias": "simulate", "node_id": "first", "artifacts": [_ref().model_dump(mode="json")]},
        {
            "alias": "simulate",
            "node_id": "second",
            "artifacts": [_ref(second_profile).model_dump(mode="json")],
        },
    ]
    if reverse_rows:
        rows.reverse()

    with pytest.raises(SimulationResultProjectionError, match="node binding is ambiguous"):
        _unique_workflow_report_node({"nodes": rows}, alias="simulate")


@pytest.mark.parametrize("malformed_row", [None, {}, {"alias": ["simulate"]}])
def test_named_node_intake_refuses_rows_with_unestablished_relevance(
    malformed_row: object,
) -> None:
    """An unparseable alias cannot disappear before the named row is admitted."""
    report = {"nodes": [{"alias": "simulate", "artifacts": []}, malformed_row]}
    with pytest.raises(
        SimulationResultProjectionError,
        match="relevance cannot be established",
    ):
        _unique_workflow_report_node(report, alias="simulate")
