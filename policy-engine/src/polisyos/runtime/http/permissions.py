"""Canonical server-owned permission vocabulary for the runtime HTTP API."""

from __future__ import annotations

from enum import StrEnum
from types import MappingProxyType
from typing import TYPE_CHECKING

from polisyos.runtime.http.security import PolicyOSRole

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping
    from typing import Final


class RuntimePermission(StrEnum):
    """Closed action-permission vocabulary owned by the runtime server."""

    ANALYSIS_EXECUTE = "analysis.execute"
    ARTIFACTS_BATCH_READ = "artifacts.batch.read"
    ARTIFACTS_RENDER = "artifacts.render"
    DASHBOARD_VIEW = "dashboard.view"
    DECISIONS_VALIDITY_PUBLISH = "decisions.validity.publish"
    EVIDENCE_ACQUIRE = "evidence.acquire"
    EVIDENCE_DISCOVER = "evidence.discover"
    EVIDENCE_PREVIEW = "evidence.preview"
    EVIDENCE_PROMOTIONS_APPROVE = "evidence.promotions.approve"
    EVIDENCE_PROMOTIONS_REJECT = "evidence.promotions.reject"
    EVIDENCE_RESOLVE = "evidence.resolve"
    EVIDENCE_REVIEW = "evidence.review"
    EVIDENCE_SAE_ANALYZE = "evidence.sae.analyze"
    EVIDENCE_VIEW = "evidence.view"
    FABRIC_IMPACT_ANALYZE = "fabric.impact.analyze"
    FABRIC_QUALITY_READ = "fabric.quality.read"
    FABRIC_TRUST_READ = "fabric.trust.read"
    KNOWLEDGE_SEARCH = "knowledge.search"
    KNOWLEDGE_TRIGGER = "knowledge.trigger"
    KNOWLEDGE_VIEW = "knowledge.view"
    LINEAGE_BATCH_READ = "lineage.batch.read"
    MOBILITY_ANALYZE = "mobility.analyze"
    MODE_ANALYST = "mode.analyst"
    PLATFORM_ADMIN = "platform.admin"
    PLATFORM_VIEW = "platform.view"
    RUNS_BATCH_READ = "runs.batch.read"
    RUNS_FEEDBACK_EVALUATE = "runs.feedback.evaluate"
    RUNS_LAUNCH = "runs.launch"
    RUNS_PRODUCTION_APPROVAL_CREATE = "runs.production_approval.create"
    RUNS_REISSUE = "runs.reissue"
    RUNS_REVIEW = "runs.review"
    RUNS_VIEW = "runs.view"
    SCENARIOS_CREATE = "scenarios.create"


ROLE_PERMISSION_GRANTS: Final[Mapping[PolicyOSRole, frozenset[RuntimePermission]]] = (
    MappingProxyType(
        {
            PolicyOSRole.ADMIN: frozenset(
                {
                    RuntimePermission.ANALYSIS_EXECUTE,
                    RuntimePermission.ARTIFACTS_BATCH_READ,
                    RuntimePermission.ARTIFACTS_RENDER,
                    RuntimePermission.DASHBOARD_VIEW,
                    RuntimePermission.DECISIONS_VALIDITY_PUBLISH,
                    RuntimePermission.EVIDENCE_ACQUIRE,
                    RuntimePermission.EVIDENCE_DISCOVER,
                    RuntimePermission.EVIDENCE_PREVIEW,
                    RuntimePermission.EVIDENCE_PROMOTIONS_APPROVE,
                    RuntimePermission.EVIDENCE_PROMOTIONS_REJECT,
                    RuntimePermission.EVIDENCE_RESOLVE,
                    RuntimePermission.EVIDENCE_REVIEW,
                    RuntimePermission.EVIDENCE_SAE_ANALYZE,
                    RuntimePermission.EVIDENCE_VIEW,
                    RuntimePermission.FABRIC_IMPACT_ANALYZE,
                    RuntimePermission.FABRIC_QUALITY_READ,
                    RuntimePermission.FABRIC_TRUST_READ,
                    RuntimePermission.KNOWLEDGE_SEARCH,
                    RuntimePermission.KNOWLEDGE_TRIGGER,
                    RuntimePermission.KNOWLEDGE_VIEW,
                    RuntimePermission.LINEAGE_BATCH_READ,
                    RuntimePermission.MOBILITY_ANALYZE,
                    RuntimePermission.MODE_ANALYST,
                    RuntimePermission.PLATFORM_ADMIN,
                    RuntimePermission.PLATFORM_VIEW,
                    RuntimePermission.RUNS_BATCH_READ,
                    RuntimePermission.RUNS_FEEDBACK_EVALUATE,
                    RuntimePermission.RUNS_LAUNCH,
                    RuntimePermission.RUNS_PRODUCTION_APPROVAL_CREATE,
                    RuntimePermission.RUNS_REISSUE,
                    RuntimePermission.RUNS_REVIEW,
                    RuntimePermission.RUNS_VIEW,
                    RuntimePermission.SCENARIOS_CREATE,
                }
            ),
            PolicyOSRole.ANALYST: frozenset(
                {
                    RuntimePermission.ANALYSIS_EXECUTE,
                    RuntimePermission.ARTIFACTS_BATCH_READ,
                    RuntimePermission.ARTIFACTS_RENDER,
                    RuntimePermission.DASHBOARD_VIEW,
                    RuntimePermission.EVIDENCE_ACQUIRE,
                    RuntimePermission.EVIDENCE_DISCOVER,
                    RuntimePermission.EVIDENCE_PREVIEW,
                    RuntimePermission.EVIDENCE_PROMOTIONS_APPROVE,
                    RuntimePermission.EVIDENCE_PROMOTIONS_REJECT,
                    RuntimePermission.EVIDENCE_RESOLVE,
                    RuntimePermission.EVIDENCE_REVIEW,
                    RuntimePermission.EVIDENCE_SAE_ANALYZE,
                    RuntimePermission.EVIDENCE_VIEW,
                    RuntimePermission.FABRIC_IMPACT_ANALYZE,
                    RuntimePermission.FABRIC_QUALITY_READ,
                    RuntimePermission.FABRIC_TRUST_READ,
                    RuntimePermission.KNOWLEDGE_SEARCH,
                    RuntimePermission.KNOWLEDGE_TRIGGER,
                    RuntimePermission.KNOWLEDGE_VIEW,
                    RuntimePermission.LINEAGE_BATCH_READ,
                    RuntimePermission.MOBILITY_ANALYZE,
                    RuntimePermission.MODE_ANALYST,
                    RuntimePermission.PLATFORM_VIEW,
                    RuntimePermission.RUNS_BATCH_READ,
                    RuntimePermission.RUNS_FEEDBACK_EVALUATE,
                    RuntimePermission.RUNS_LAUNCH,
                    RuntimePermission.RUNS_REVIEW,
                    RuntimePermission.RUNS_VIEW,
                    RuntimePermission.SCENARIOS_CREATE,
                }
            ),
            PolicyOSRole.VIEWER: frozenset(
                {
                    RuntimePermission.ARTIFACTS_BATCH_READ,
                    RuntimePermission.DASHBOARD_VIEW,
                    RuntimePermission.EVIDENCE_VIEW,
                    RuntimePermission.FABRIC_QUALITY_READ,
                    RuntimePermission.FABRIC_TRUST_READ,
                    RuntimePermission.KNOWLEDGE_SEARCH,
                    RuntimePermission.KNOWLEDGE_VIEW,
                    RuntimePermission.LINEAGE_BATCH_READ,
                    RuntimePermission.PLATFORM_VIEW,
                    RuntimePermission.RUNS_BATCH_READ,
                    RuntimePermission.RUNS_VIEW,
                }
            ),
            PolicyOSRole.SERVICE: frozenset(
                {
                    RuntimePermission.ANALYSIS_EXECUTE,
                    RuntimePermission.ARTIFACTS_BATCH_READ,
                    RuntimePermission.ARTIFACTS_RENDER,
                    RuntimePermission.DASHBOARD_VIEW,
                    RuntimePermission.EVIDENCE_DISCOVER,
                    RuntimePermission.EVIDENCE_PREVIEW,
                    RuntimePermission.EVIDENCE_PROMOTIONS_APPROVE,
                    RuntimePermission.EVIDENCE_PROMOTIONS_REJECT,
                    RuntimePermission.EVIDENCE_RESOLVE,
                    RuntimePermission.EVIDENCE_REVIEW,
                    RuntimePermission.EVIDENCE_SAE_ANALYZE,
                    RuntimePermission.EVIDENCE_VIEW,
                    RuntimePermission.FABRIC_IMPACT_ANALYZE,
                    RuntimePermission.FABRIC_QUALITY_READ,
                    RuntimePermission.FABRIC_TRUST_READ,
                    RuntimePermission.KNOWLEDGE_SEARCH,
                    RuntimePermission.KNOWLEDGE_TRIGGER,
                    RuntimePermission.KNOWLEDGE_VIEW,
                    RuntimePermission.LINEAGE_BATCH_READ,
                    RuntimePermission.MOBILITY_ANALYZE,
                    RuntimePermission.MODE_ANALYST,
                    RuntimePermission.PLATFORM_ADMIN,
                    RuntimePermission.PLATFORM_VIEW,
                    RuntimePermission.RUNS_BATCH_READ,
                    RuntimePermission.RUNS_FEEDBACK_EVALUATE,
                    RuntimePermission.RUNS_LAUNCH,
                    RuntimePermission.RUNS_REVIEW,
                    RuntimePermission.RUNS_VIEW,
                }
            ),
            PolicyOSRole.SYSTEM: frozenset(
                {
                    RuntimePermission.ANALYSIS_EXECUTE,
                    RuntimePermission.ARTIFACTS_BATCH_READ,
                    RuntimePermission.ARTIFACTS_RENDER,
                    RuntimePermission.DASHBOARD_VIEW,
                    RuntimePermission.EVIDENCE_DISCOVER,
                    RuntimePermission.EVIDENCE_PREVIEW,
                    RuntimePermission.EVIDENCE_PROMOTIONS_APPROVE,
                    RuntimePermission.EVIDENCE_PROMOTIONS_REJECT,
                    RuntimePermission.EVIDENCE_RESOLVE,
                    RuntimePermission.EVIDENCE_REVIEW,
                    RuntimePermission.EVIDENCE_SAE_ANALYZE,
                    RuntimePermission.EVIDENCE_VIEW,
                    RuntimePermission.FABRIC_IMPACT_ANALYZE,
                    RuntimePermission.FABRIC_QUALITY_READ,
                    RuntimePermission.FABRIC_TRUST_READ,
                    RuntimePermission.KNOWLEDGE_SEARCH,
                    RuntimePermission.KNOWLEDGE_TRIGGER,
                    RuntimePermission.KNOWLEDGE_VIEW,
                    RuntimePermission.LINEAGE_BATCH_READ,
                    RuntimePermission.MOBILITY_ANALYZE,
                    RuntimePermission.MODE_ANALYST,
                    RuntimePermission.PLATFORM_ADMIN,
                    RuntimePermission.PLATFORM_VIEW,
                    RuntimePermission.RUNS_BATCH_READ,
                    RuntimePermission.RUNS_FEEDBACK_EVALUATE,
                    RuntimePermission.RUNS_LAUNCH,
                    RuntimePermission.RUNS_REVIEW,
                    RuntimePermission.RUNS_VIEW,
                }
            ),
        }
    )
)


def permissions_for_roles(roles: Iterable[PolicyOSRole]) -> list[RuntimePermission]:
    """Return the stable union of canonical permissions granted to ``roles``."""
    permissions: set[RuntimePermission] = set()
    for role in roles:
        permissions.update(ROLE_PERMISSION_GRANTS.get(role, ()))
    return sorted(permissions, key=lambda permission: permission.value)
