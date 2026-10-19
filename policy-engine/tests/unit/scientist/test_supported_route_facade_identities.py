from __future__ import annotations

from importlib import import_module

import pytest


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


def test_policy_design_facade_exposes_phase2_bounds_owner_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    policy_design = import_module("polisyos.scientist.policy_design")
    search = import_module("polisyos.scientist.policy_design.search")
    name = "derive_phase2_parameter_bounds"

    assert name in policy_design.__all__
    assert getattr(policy_design, name) is getattr(search, name)

    monkeypatch.delattr(policy_design, name)
    monkeypatch.delitem(policy_design._SYMBOL_TO_MODULE, name)
    monkeypatch.setattr(
        policy_design,
        "__all__",
        [item for item in policy_design.__all__ if item != name],
    )
    with pytest.raises(AttributeError):
        getattr(policy_design, name)
