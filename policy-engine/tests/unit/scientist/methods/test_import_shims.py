"""Import contract tests for the Scientist methods lane."""

from __future__ import annotations

import importlib


def test_search_module_shim_aliases_canonical_module() -> None:
    legacy = importlib.import_module("polisyos.scientist.search.objective")
    canonical = importlib.import_module("polisyos.scientist.methods.search.objective")

    assert legacy is canonical
    assert legacy.ObjectiveValue is canonical.ObjectiveValue
    assert legacy.__shim_sunset_date__ == "2027-03-02"


def test_discovery_module_shim_aliases_canonical_module() -> None:
    legacy = importlib.import_module("polisyos.scientist.discovery.schema")
    canonical = importlib.import_module("polisyos.scientist.methods.discovery.schema")

    assert legacy is canonical
    assert legacy.GraphHypothesis is canonical.GraphHypothesis
    assert legacy.__shim_sunset_date__ == "2027-03-02"


def test_research_dag_module_shim_aliases_canonical_module() -> None:
    legacy = importlib.import_module("polisyos.scientist.research_dag.models")
    canonical = importlib.import_module("polisyos.scientist.methods.research_dag.models")

    assert legacy is canonical
    assert legacy.ResearchDAGArtifact is canonical.ResearchDAGArtifact
    assert legacy.__shim_sunset_date__ == "2027-03-02"


def test_method_package_shims_advertise_canonical_home_and_sunset() -> None:
    expected = {
        "polisyos.scientist.search": "polisyos.scientist.methods.search",
        "polisyos.scientist.discovery": "polisyos.scientist.methods.discovery",
        "polisyos.scientist.research_dag": "polisyos.scientist.methods.research_dag",
    }

    for legacy_name, canonical_name in expected.items():
        module = importlib.import_module(legacy_name)

        assert module.__canonical_module__ == canonical_name
        assert module.__shim_sunset_date__ == "2027-03-02"


def test_workflow_selection_legacy_import_targets_orchestration_boundary() -> None:
    legacy = importlib.import_module("polisyos.scientist.workflows.selection")
    canonical = importlib.import_module("polisyos.scientist.orchestration.workflows.selection")

    assert legacy is canonical
    assert legacy.resolve_workflow_id is canonical.resolve_workflow_id


def test_phase45_method_shims_alias_canonical_modules() -> None:
    expected = {
        "polisyos.scientist.autotune.models": "polisyos.scientist.methods.autotune.models",
        "polisyos.scientist.backtesting.plan": "polisyos.scientist.methods.backtesting.plan",
        "polisyos.scientist.causal.validity": "polisyos.scientist.methods.causal.validity",
        "polisyos.scientist.compute.advanced_methods": "polisyos.scientist.methods.advanced",
        "polisyos.scientist.doe.designs": "polisyos.scientist.methods.doe.designs",
    }

    for legacy_name, canonical_name in expected.items():
        legacy = importlib.import_module(legacy_name)
        canonical = importlib.import_module(canonical_name)

        assert legacy is canonical
        assert legacy.__shim_sunset_date__ == "2026-12-31"


def test_phase45_orchestration_shims_alias_canonical_modules() -> None:
    expected = {
        "polisyos.scientist.engine.state": "polisyos.scientist.orchestration.engine.state",
        "polisyos.scientist.kernel.fsm": "polisyos.scientist.orchestration.kernel.fsm",
        "polisyos.scientist.llm.gateway_client": (
            "polisyos.scientist.orchestration.llm.gateway_client"
        ),
        "polisyos.scientist.memory.failure_lessons": (
            "polisyos.scientist.orchestration.memory.failure_lessons"
        ),
        "polisyos.scientist.orchestrator.decision_card": (
            "polisyos.scientist.orchestration.orchestrator.decision_card"
        ),
        "polisyos.scientist.workflows.builder": (
            "polisyos.scientist.orchestration.workflows.builder"
        ),
    }

    for legacy_name, canonical_name in expected.items():
        legacy = importlib.import_module(legacy_name)
        canonical = importlib.import_module(canonical_name)

        assert legacy is canonical
        assert legacy.__shim_sunset_date__ == "2026-12-31"
