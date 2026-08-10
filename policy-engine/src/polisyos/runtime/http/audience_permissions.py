"""Server-owned audience eligibility for the runtime permission vocabulary."""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from polisyos.runtime.http.permissions import RuntimePermission
from polisyos.runtime.http.services.governed_projections import (
    AudienceClass,
    ProjectionId,
)

if TYPE_CHECKING:
    from collections.abc import Mapping


PERMISSION_AUDIENCES: Mapping[RuntimePermission, frozenset[AudienceClass]] = MappingProxyType(
    {
        RuntimePermission.ANALYSIS_EXECUTE: frozenset(
            {AudienceClass.EXPERT, AudienceClass.MACHINE}
        ),
        RuntimePermission.ARTIFACTS_BATCH_READ: frozenset(
            {AudienceClass.REVIEWER, AudienceClass.EXPERT, AudienceClass.MACHINE}
        ),
        RuntimePermission.ARTIFACTS_RENDER: frozenset(
            {AudienceClass.REVIEWER, AudienceClass.EXPERT, AudienceClass.MACHINE}
        ),
        RuntimePermission.DASHBOARD_VIEW: frozenset({AudienceClass.REVIEWER, AudienceClass.EXPERT}),
        RuntimePermission.DECISIONS_VALIDITY_PUBLISH: frozenset({AudienceClass.REVIEWER}),
        RuntimePermission.EVIDENCE_ACQUIRE: frozenset(
            {AudienceClass.REVIEWER, AudienceClass.EXPERT}
        ),
        RuntimePermission.EVIDENCE_DISCOVER: frozenset(
            {AudienceClass.EXPERT, AudienceClass.MACHINE}
        ),
        RuntimePermission.EVIDENCE_PREVIEW: frozenset(
            {AudienceClass.EXPERT, AudienceClass.MACHINE}
        ),
        RuntimePermission.EVIDENCE_PROMOTIONS_APPROVE: frozenset({AudienceClass.REVIEWER}),
        RuntimePermission.EVIDENCE_PROMOTIONS_REJECT: frozenset({AudienceClass.REVIEWER}),
        RuntimePermission.EVIDENCE_RESOLVE: frozenset(
            {AudienceClass.EXPERT, AudienceClass.MACHINE}
        ),
        RuntimePermission.EVIDENCE_REVIEW: frozenset(
            {AudienceClass.REVIEWER, AudienceClass.EXPERT}
        ),
        RuntimePermission.EVIDENCE_SAE_ANALYZE: frozenset(
            {AudienceClass.EXPERT, AudienceClass.MACHINE}
        ),
        RuntimePermission.EVIDENCE_VIEW: frozenset(
            {AudienceClass.REVIEWER, AudienceClass.EXPERT, AudienceClass.MACHINE}
        ),
        RuntimePermission.FABRIC_IMPACT_ANALYZE: frozenset(
            {AudienceClass.EXPERT, AudienceClass.MACHINE}
        ),
        RuntimePermission.FABRIC_QUALITY_READ: frozenset(
            {AudienceClass.REVIEWER, AudienceClass.EXPERT, AudienceClass.MACHINE}
        ),
        RuntimePermission.FABRIC_TRUST_READ: frozenset(
            {AudienceClass.REVIEWER, AudienceClass.EXPERT, AudienceClass.MACHINE}
        ),
        RuntimePermission.KNOWLEDGE_SEARCH: frozenset(
            {AudienceClass.REVIEWER, AudienceClass.EXPERT, AudienceClass.MACHINE}
        ),
        RuntimePermission.KNOWLEDGE_TRIGGER: frozenset(
            {AudienceClass.EXPERT, AudienceClass.MACHINE}
        ),
        RuntimePermission.KNOWLEDGE_VIEW: frozenset(
            {AudienceClass.REVIEWER, AudienceClass.EXPERT, AudienceClass.MACHINE}
        ),
        RuntimePermission.LINEAGE_BATCH_READ: frozenset(
            {AudienceClass.REVIEWER, AudienceClass.EXPERT, AudienceClass.MACHINE}
        ),
        RuntimePermission.MOBILITY_ANALYZE: frozenset(
            {AudienceClass.EXPERT, AudienceClass.MACHINE}
        ),
        RuntimePermission.MODE_ANALYST: frozenset({AudienceClass.EXPERT}),
        RuntimePermission.PLATFORM_ADMIN: frozenset({AudienceClass.EXPERT, AudienceClass.MACHINE}),
        RuntimePermission.PLATFORM_VIEW: frozenset(
            {AudienceClass.REVIEWER, AudienceClass.EXPERT, AudienceClass.MACHINE}
        ),
        RuntimePermission.RUNS_BATCH_READ: frozenset(
            {AudienceClass.REVIEWER, AudienceClass.EXPERT, AudienceClass.MACHINE}
        ),
        RuntimePermission.RUNS_FEEDBACK_EVALUATE: frozenset(
            {AudienceClass.EXPERT, AudienceClass.MACHINE}
        ),
        RuntimePermission.RUNS_LAUNCH: frozenset({AudienceClass.EXPERT, AudienceClass.MACHINE}),
        RuntimePermission.RUNS_PRODUCTION_APPROVAL_CREATE: frozenset({AudienceClass.REVIEWER}),
        RuntimePermission.RUNS_REISSUE: frozenset({AudienceClass.REVIEWER}),
        RuntimePermission.RUNS_REVIEW: frozenset({AudienceClass.REVIEWER, AudienceClass.EXPERT}),
        RuntimePermission.RUNS_VIEW: frozenset(
            {AudienceClass.REVIEWER, AudienceClass.EXPERT, AudienceClass.MACHINE}
        ),
        RuntimePermission.SCENARIOS_CREATE: frozenset({AudienceClass.EXPERT}),
    }
)

if set(PERMISSION_AUDIENCES) != set(RuntimePermission):
    raise RuntimeError("audience permissions must cover every RuntimePermission exactly once")

AUDIENCE_PERMISSIONS: Mapping[AudienceClass, frozenset[RuntimePermission]] = MappingProxyType(
    {
        audience: frozenset(
            permission
            for permission, audiences in PERMISSION_AUDIENCES.items()
            if audience in audiences
        )
        for audience in AudienceClass
    }
)
_PROJECTION_AUDIENCE_PERMISSION: Mapping[AudienceClass, RuntimePermission] = MappingProxyType(
    {
        AudienceClass.EXPERT: RuntimePermission.MODE_ANALYST,
        AudienceClass.MACHINE: RuntimePermission.PLATFORM_VIEW,
    }
)


def permissions_for_audience(audience: AudienceClass) -> frozenset[RuntimePermission]:
    """Return the immutable eligible permission set for one canonical audience."""
    if not isinstance(audience, AudienceClass):
        raise TypeError("audience must be an AudienceClass")
    return AUDIENCE_PERMISSIONS[audience]


def permission_for_projection(projection_id: ProjectionId) -> RuntimePermission:
    """Return the exact permission required by one emitted governed projection."""
    if not isinstance(projection_id, ProjectionId):
        raise TypeError("projection_id must be a ProjectionId")
    from polisyos.runtime.http.services.governed_projections import projection_audience

    try:
        return _PROJECTION_AUDIENCE_PERMISSION[projection_audience(projection_id)]
    except KeyError as exc:
        raise ValueError(f"no privileged projection permission for {projection_id.value}") from exc


def projection_permission_allows(
    projection_id: ProjectionId, permission: RuntimePermission
) -> bool:
    """Return whether an exact permission admits the named projection."""
    if not isinstance(permission, RuntimePermission):
        raise TypeError("permission must be a RuntimePermission")
    return permission is permission_for_projection(projection_id)


__all__ = [
    "AUDIENCE_PERMISSIONS",
    "PERMISSION_AUDIENCES",
    "permission_for_projection",
    "permissions_for_audience",
    "projection_permission_allows",
]
