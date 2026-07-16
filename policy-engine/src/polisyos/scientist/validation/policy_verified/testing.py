"""Explicit non-promotable fixtures for policy-verified contract tests."""

from __future__ import annotations

import asyncio
from typing import Literal

from pydantic import BaseModel, ConfigDict

from polisyos.core.artifacts.manifest import ArtifactRef, SchemaInfo
from polisyos.core.artifacts.store import PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.scientist.agent.formalizer import MockFormalizerAgent
from polisyos.scientist.agent.protocols import DraftResult
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.validation.policy_verified.models import PolicyOptionSet, PolicyRequestFrame

_NON_PROMOTABLE_REASON = "policy_verified_contract_fixture_non_promotable"


class PolicyVerifiedContractFixture(BaseModel):
    """Authority fence around an explicitly requested contract-test Trinity fixture."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    artifact_ref: ArtifactRef
    authority_scope: Literal["contract_testing"] = "contract_testing"
    promotion_allowed: Literal[False] = False
    non_promotable_reason: Literal[
        "policy_verified_contract_fixture_non_promotable"
    ] = _NON_PROMOTABLE_REASON


def formalize_policy_option_set_for_contract_testing(
    ctx: ExecutionContext,
    frame: PolicyRequestFrame,
    option_set: PolicyOptionSet,
) -> PolicyVerifiedContractFixture:
    """Build the former mock policy only on the explicit contract-test surface."""

    primary = (option_set.verified_options or option_set.hypothesis_options or [None])[0]
    if primary is None:
        raise ValueError("policy_verified_contract_fixture_option_missing")
    draft = DraftResult(
        draft_id=f"contract_testing_{frame.request_id}_{primary.option_id}",
        problem_frame_ref=frame.request_id,
        narrative=primary.summary,
        interventions=[
            {
                "name": primary.title,
                "description": primary.summary,
                "mechanism_type": "tax_subsidy",
                "target_population": "all",
                "parameters": {"rate": "0.1"},
                "rationale": primary.summary,
            }
        ],
        rationale="Contract-testing fixture; never production authority.",
        confidence=0.7,
    )
    bundle = asyncio.run(MockFormalizerAgent().formalize(draft))
    artifact = ctx.store.put_json(
        bundle,
        PutOptions(
            kind="ir.trinity_bundle.contract_testing",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.ir.TrinityBundle.contract_testing",
                version=str(bundle.schema_version),
            ),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return PolicyVerifiedContractFixture(artifact_ref=artifact)


__all__ = [
    "PolicyVerifiedContractFixture",
    "formalize_policy_option_set_for_contract_testing",
]
