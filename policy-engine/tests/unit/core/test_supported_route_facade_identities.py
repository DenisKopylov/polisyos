from __future__ import annotations

from importlib import import_module

import pytest


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


def test_core_contract_facade_exposes_supported_fabric_helpers_and_modules(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    contracts = import_module("polisyos.core.contracts")
    fabric = import_module("polisyos.core.contracts.fabric")
    chronology = import_module("polisyos.core.contracts.chronology")
    epoch = import_module("polisyos.core.contracts.epoch")

    for name in (
        "data_snapshot_reference_fields",
        "data_snapshot_reference_input_roles",
    ):
        assert name in contracts.__all__
        assert getattr(contracts, name) is getattr(fabric, name)

    role_name = "acquisition_native_coordinate_role"
    assert role_name in contracts.__all__
    assert getattr(contracts, role_name) is getattr(epoch, role_name)

    for name, owner in (("chronology", chronology), ("epoch", epoch)):
        assert name in contracts.__all__
        assert getattr(contracts, name) is owner

    fields_name = "data_snapshot_reference_fields"
    monkeypatch.delattr(contracts, fields_name)
    monkeypatch.delitem(contracts._LAZY_IMPORTS, fields_name)
    assert fields_name in contracts.__all__
    with pytest.raises(AttributeError):
        getattr(contracts, fields_name)

    monkeypatch.delattr(contracts, role_name)
    monkeypatch.delitem(contracts._LAZY_IMPORTS, role_name)
    assert role_name in contracts.__all__
    with pytest.raises(AttributeError):
        getattr(contracts, role_name)

    owners = {"chronology": chronology, "epoch": epoch}
    for name in owners:
        monkeypatch.delattr(contracts, name)
        monkeypatch.setattr(contracts, "_SUBMODULES", contracts._SUBMODULES - {name})
        assert name in contracts.__all__
        with pytest.raises(AttributeError):
            getattr(contracts, name)

        # A cached child module need not restore its removed package attribute.
        # Returning the package from a from-list import proves no selected export.
        imported_package = __import__("polisyos.core.contracts", fromlist=[name])
        assert imported_package is contracts
        with pytest.raises(AttributeError):
            getattr(imported_package, name)
