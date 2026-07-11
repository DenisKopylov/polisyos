"""Structurally separate non-promotable agents for NL contract tests."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict


class NLContractTestingAuthorityStamp(BaseModel):
    """Type-constrained authority fence for the mock-agent NL lane."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    authority_scope: Literal["contract_testing"] = "contract_testing"
    production_promotable: Literal[False] = False
    non_promotable_reason: Literal["nl_mock_agents_contract_testing_only"] = (
        "nl_mock_agents_contract_testing_only"
    )


def build_nl_contract_testing_agents() -> tuple[object, object, object, object, object]:
    """Construct the former mock agent set only for the explicit test lane."""

    from polisyos.scientist.agent.critic import MockCriticAgent
    from polisyos.scientist.agent.data_need_extractor import MockDataNeedExtractorAgent
    from polisyos.scientist.agent.drafter_clients import MockDrafterAgent
    from polisyos.scientist.agent.formalizer import MockFormalizerAgent
    from polisyos.scientist.agent.pi import MockPIAgent

    return (
        MockPIAgent(),
        MockDataNeedExtractorAgent(),
        MockDrafterAgent(),
        MockFormalizerAgent(),
        MockCriticAgent(),
    )


__all__ = ["NLContractTestingAuthorityStamp", "build_nl_contract_testing_agents"]
