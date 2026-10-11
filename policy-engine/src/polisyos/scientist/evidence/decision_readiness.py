"""Shared decision-readiness levels used by evidence and search contracts."""

from __future__ import annotations

from enum import Enum


class DecisionReadiness(str, Enum):
    """Decision readiness level carried by typed claims and promotion artifacts."""

    # Keep serialized enum references stable while source ownership is shared
    # with evidence and the old search module remains a compatibility facade.
    __module__ = "polisyos.scientist.methods.search.readiness"

    RESEARCH_ARTIFACT = "research_artifact"
    ANALYST_ADVISORY = "analyst_advisory"
    EXTERNAL_BRIEFING = "external_briefing"
    SIMULATION_READY = "simulation_ready"
    RECOMMENDATION_READY = "recommendation_ready"
    DEPLOYMENT_READY = "deployment_ready"
