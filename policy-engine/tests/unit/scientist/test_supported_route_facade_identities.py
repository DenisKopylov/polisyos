from __future__ import annotations


def test_scientist_subpackage_facades_preserve_owner_protocols() -> None:
    from polisyos.scientist.agent import (
        CriticAgent,
        DataNeedExtractorAgent,
        DrafterAgent,
        FormalizerAgent,
        PIAgent,
    )
    from polisyos.scientist.agent.protocols import (
        CriticAgent as OwnerCriticAgent,
    )
    from polisyos.scientist.agent.protocols import (
        DataNeedExtractorAgent as OwnerDataNeedExtractorAgent,
    )
    from polisyos.scientist.agent.protocols import (
        DrafterAgent as OwnerDrafterAgent,
    )
    from polisyos.scientist.agent.protocols import (
        FormalizerAgent as OwnerFormalizerAgent,
    )
    from polisyos.scientist.agent.protocols import (
        PIAgent as OwnerPIAgent,
    )
    from polisyos.scientist.policy_design import PolicyCandidateSchema
    from polisyos.scientist.policy_design.schema import (
        PolicyCandidateSchema as OwnerPolicyCandidateSchema,
    )

    assert CriticAgent is OwnerCriticAgent
    assert DataNeedExtractorAgent is OwnerDataNeedExtractorAgent
    assert DrafterAgent is OwnerDrafterAgent
    assert FormalizerAgent is OwnerFormalizerAgent
    assert PIAgent is OwnerPIAgent
    assert PolicyCandidateSchema is OwnerPolicyCandidateSchema
