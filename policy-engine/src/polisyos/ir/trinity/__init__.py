"""Canonical Trinity contracts.

ProblemFrame / PolicySpec / ModelSpec are the canonical policy contracts.
TrinityBundle is the canonical payload container for bundling them together.
"""
from __future__ import annotations

from pydantic import Field

from polisyos.ir.governance.policy_spec import PolicySpec
from polisyos.ir.governance.problem_frame import ProblemFrame
from polisyos.ir.kernel.base import KernelModel
from polisyos.ir.model_spec import ModelSpec

TRINITY_BUNDLE_SCHEMA_VERSION = "1.0"
SCHEMA_VERSION_PATTERN = r"^\d+\.\d+$"


class TrinityBundle(KernelModel):
    """Bundle containing the three canonical Trinity artifacts."""

    schema_version: str = Field(TRINITY_BUNDLE_SCHEMA_VERSION, pattern=SCHEMA_VERSION_PATTERN)
    problem_frame: ProblemFrame
    policy_spec: PolicySpec
    model_spec: ModelSpec


__all__ = [
    "ProblemFrame",
    "PolicySpec",
    "ModelSpec",
    "TrinityBundle",
    "TRINITY_BUNDLE_SCHEMA_VERSION",
]
