"""Selection of exact current policy-source references across state projections."""

from __future__ import annotations

from polisyos.core.artifacts import ArtifactStore
from polisyos.core.artifacts.manifest import (
    ArtifactRef,
    artifact_ref_identity_key,
    input_ref_from_artifact_ref,
)


def select_policy_source_ref(
    direct: ArtifactRef | None,
    indexed: ArtifactRef | None,
) -> ArtifactRef | None:
    """Resolve agreeing source selectors without treating selection as provenance.

    Raises:
        ValueError: When both selectors identify different selected artifacts.
    """
    if direct is not None and indexed is not None:
        if artifact_ref_identity_key(direct) != artifact_ref_identity_key(indexed):
            raise ValueError("policy_source_selection_conflict")
    return direct if direct is not None else indexed


def require_selected_policy_source_bindings(
    store: ArtifactStore,
    *,
    request_ref: ArtifactRef,
    option_ref: ArtifactRef,
    source_report_ref: ArtifactRef,
) -> None:
    """Require the selected options and source report to bind the exact request.

    These source edges establish a selection join, not producer provenance or
    legal authority. Historical artifacts without selected edges remain readable.

    Raises:
        ValueError: When an edge is missing, duplicated, or identifies another
            artifact occurrence or manifest profile.
    """
    if any(
        ref.manifest_profile_sha256 is None for ref in (request_ref, option_ref, source_report_ref)
    ):
        raise ValueError("policy_source_binding_not_established")
    for owner_ref, role, expected_ref in (
        (source_report_ref, "policy_request_frame", request_ref),
        (option_ref, "policy_request_frame", request_ref),
        (option_ref, "source_verification_report", source_report_ref),
    ):
        actual = [item for item in store.get_manifest(owner_ref).inputs if item.role == role]
        if actual != [input_ref_from_artifact_ref(expected_ref, role=role)]:
            raise ValueError("policy_source_binding_not_established")
