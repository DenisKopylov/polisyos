"""Scholar producer bindings for Policy Design Case spine consumers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from polisyos.scholar_requirement import (
    ScholarSupportRequirementSpec,
    normalize_scholar_support_requirement_specs,
)

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence


def build_scholar_spine_evidence_binding(
    *,
    literature_refs: Sequence[Any] | None = None,
    spine_context: Mapping[str, Any] | None = None,
    blocker_refs: Sequence[Any] | None = None,
    requirement_specs: Sequence[Mapping[str, Any] | ScholarSupportRequirementSpec]
    | None = None,
) -> dict[str, Any]:
    """Return Scholar's spine-consumer fields for literature evidence."""

    from polisyos.core import contracts as core_contracts

    requirements = normalize_scholar_support_requirement_specs(requirement_specs)
    return {
        "schema_version": "policyos.scholar.spine_evidence_binding.v1",
        "requirement_refs": [requirement.requirement_id for requirement in requirements],
        "requirements": [requirement.model_dump(mode="json") for requirement in requirements],
        **core_contracts.build_producer_spine_binding_fields(
            component="scholar",
            spine_context=spine_context,
            candidate_refs=tuple(literature_refs or ()),
            blocker_refs=tuple(blocker_refs or ()),
        ),
    }


__all__ = ["build_scholar_spine_evidence_binding"]
