from __future__ import annotations

import importlib
import sys


def _clear_import_state() -> None:
    prefixes = (
        "polisyos.scientist.search.judge_stack",
        "polisyos.scientist.policy_design",
        "polisyos.scientist.policy_design.objectives",
        "polisyos.scientist.policy_design.output",
        "polisyos.scientist.policy_design.schema",
        "polisyos.scientist.policy_design.search",
        "polisyos.scientist.policy_design.translator",
        "polisyos.scientist.policy_design.critic",
        "polisyos.scientist.policy_design.adversary",
    )
    for module_name in prefixes:
        sys.modules.pop(module_name, None)


def test_judge_stack_imports_without_policy_design_cycle() -> None:
    _clear_import_state()

    module = importlib.import_module("polisyos.scientist.search.judge_stack")

    assert module.JudgeThresholdRegistry.__name__ == "JudgeThresholdRegistry"


def test_policy_design_package_root_resolves_public_exports_lazily() -> None:
    _clear_import_state()

    package = importlib.import_module("polisyos.scientist.policy_design")

    assert package.PolicyEvaluationVector.__name__ == "PolicyEvaluationVector"
    assert package.PolicyArtifactBuildInput.__name__ == "PolicyArtifactBuildInput"
