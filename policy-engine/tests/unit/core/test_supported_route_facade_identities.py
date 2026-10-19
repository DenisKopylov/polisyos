from __future__ import annotations

from importlib import import_module


def test_core_registry_and_contract_facades_preserve_owner_identity() -> None:
    contracts = import_module("polisyos.core.contracts")
    generic = import_module("polisyos.core.registry.generic")
    control = import_module("polisyos.core.contracts.control")
    fabric = import_module("polisyos.core.contracts.fabric")
    foundry = import_module("polisyos.core.contracts.foundry")

    for name in (
        "CompileRequest",
        "ExecPlan",
        "ExecuteRequest",
        "FeedbackConfig",
        "FeedbackConfigRef",
        "FeedbackDiagnosticSpec",
        "FeedbackSolverConfig",
        "FeedbackVariableSpec",
        "FoundryInputBindingTransform",
        "FoundryInputBindings",
        "FoundryInputBindingsRef",
        "ProgramGraph",
        "StateSnapshotRef",
    ):
        assert getattr(contracts, name) is getattr(foundry, name)
    assert contracts.ControlJobResponse is control.ControlJobResponse
    assert contracts.RetrievalSummary is fabric.RetrievalSummary
    assert generic.GenericRegistry is generic.GenericRegistry
    assert import_module("polisyos.core.registry").GenericRegistry is generic.GenericRegistry
