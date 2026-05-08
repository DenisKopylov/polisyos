"""Import contract tests for the Scientist methods lane."""

from __future__ import annotations

import importlib
import json
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]


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


def test_phase2_2_governance_validation_package_shims_advertise_closeout() -> None:
    expected = {
        "polisyos.scientist.continuous_governance": (
            "polisyos.scientist.governance.continuous",
            "2026-12-31",
        ),
        "polisyos.scientist.human_review": (
            "polisyos.scientist.governance.human_review",
            "2026-12-31",
        ),
        "polisyos.scientist.policy_verified": (
            "polisyos.scientist.validation.policy_verified",
            "2026-12-31",
        ),
        "polisyos.scientist.verification": (
            "polisyos.scientist.validation.verification",
            "2026-12-31",
        ),
        "polisyos.scientist.verification.ic": (
            "polisyos.scientist.validation.verification.ic",
            "2026-12-31",
        ),
    }

    for legacy_name, (canonical_name, sunset) in expected.items():
        legacy = importlib.import_module(legacy_name)

        assert legacy.__canonical_module__ == canonical_name
        assert legacy.__shim_sunset_date__ == sunset


def test_phase2_2_governance_validation_module_shims_alias_canonical_modules() -> None:
    expected = {
        "polisyos.scientist.continuous_governance.incident": (
            "polisyos.scientist.governance.continuous.incident"
        ),
        "polisyos.scientist.continuous_governance.monitors": (
            "polisyos.scientist.governance.continuous.monitors"
        ),
        "polisyos.scientist.human_review.models": (
            "polisyos.scientist.governance.human_review.models"
        ),
        "polisyos.scientist.human_review.queue": (
            "polisyos.scientist.governance.human_review.queue"
        ),
        "polisyos.scientist.policy_verified.models": (
            "polisyos.scientist.validation.policy_verified.models"
        ),
        "polisyos.scientist.policy_verified.service": (
            "polisyos.scientist.validation.policy_verified.service"
        ),
        "polisyos.scientist.verification.ic.conformance": (
            "polisyos.scientist.validation.verification.ic.conformance"
        ),
        "polisyos.scientist.verification.ic.service": (
            "polisyos.scientist.validation.verification.ic.service"
        ),
    }

    for legacy_name, canonical_name in expected.items():
        legacy = importlib.import_module(legacy_name)
        canonical = importlib.import_module(canonical_name)

        assert legacy is canonical
        assert legacy.__canonical_module__ == canonical_name
        assert legacy.__shim_sunset_date__ == "2026-12-31"


def test_phase2_2_scientist_parallel_families_have_closeout_decisions() -> None:
    inventory = json.loads(
        (
            REPO_ROOT
            / "architecture/baselines/repository_best_in_class_last_mile/"
            "scientist_parallel_implementations.json"
        ).read_text(encoding="utf-8")
    )
    registry = tomllib.loads((REPO_ROOT / "architecture/name_registry.toml").read_text())
    closeouts = {
        entry["family_id"]: entry
        for entry in registry.get("phase2_2_scientist_parallel_closeout", [])
    }

    for family in inventory["families"]:
        closeout = closeouts[family["family_id"]]

        assert closeout["owner"]
        assert closeout["target_phase"] == "2.2"
        assert closeout["canonical_home"] == family["canonical_home"]
        assert closeout["resolution"] != "classification_only"
        assert closeout["legacy_roots"] or closeout["scoped_ok_roots"]
        assert closeout["non_overlap_rationale"]
        assert closeout["test"].endswith("test_phase2_2_scientist_parallel_families_have_closeout_decisions")


def test_phase2_2_scientist_compatibility_roots_are_registered_in_shims() -> None:
    expected = {
        "polisyos.scientist.claims": (
            "polisyos.scientist.evidence.claims",
            "2026-11-30",
        ),
        "polisyos.scientist.continuous_governance": (
            "polisyos.scientist.governance.continuous",
            "2026-12-31",
        ),
        "polisyos.scientist.provenance": (
            "polisyos.scientist.evidence.provenance",
            "2026-11-30",
        ),
        "polisyos.scientist.human_review": (
            "polisyos.scientist.governance.human_review",
            "2026-12-31",
        ),
        "polisyos.scientist.policy_verified": (
            "polisyos.scientist.validation.policy_verified",
            "2026-12-31",
        ),
        "polisyos.scientist.verification": (
            "polisyos.scientist.validation.verification",
            "2026-12-31",
        ),
        "polisyos.scientist.orchestrator": (
            "polisyos.scientist.orchestration.orchestrator",
            "2026-12-31",
        ),
        "polisyos.scientist.workflows": (
            "polisyos.scientist.orchestration.workflows",
            "2026-12-31",
        ),
        "polisyos.scientist.search": (
            "polisyos.scientist.methods.search",
            "2027-03-02",
        ),
        "polisyos.scientist.discovery": (
            "polisyos.scientist.methods.discovery",
            "2027-03-02",
        ),
        "polisyos.scientist.research_dag": (
            "polisyos.scientist.methods.research_dag",
            "2027-03-02",
        ),
    }
    registered = _registered_shims_by_source()

    for source_fqn, (target_fqn, sunset) in expected.items():
        entry = registered[source_fqn]

        assert entry["target_fqn"] == target_fqn
        assert entry["owner"] == "team-scientist"
        assert entry["sunset_date"] == sunset


def test_phase2_2_evidence_compatibility_roots_are_not_canonical_roots() -> None:
    payload = tomllib.loads(
        (REPO_ROOT / "architecture/packages/scientist.toml").read_text(encoding="utf-8")
    )
    layout = payload["layout"]
    canonical = set(layout["canonical_first_level_roots"])
    compatibility = set(layout["compatibility_shim_roots"])

    for root in {
        "src/polisyos/scientist/claims",
        "src/polisyos/scientist/provenance",
    }:
        assert root not in canonical
        assert root in compatibility


def test_phase2_1_publisher_implementation_lives_in_publishing_module() -> None:
    canonical = importlib.import_module("polisyos.scientist.publishing.publisher")
    facade = importlib.import_module("polisyos.scientist.publishing")
    root_legacy = importlib.import_module("polisyos.scientist.publisher")
    orchestrator_legacy = importlib.import_module(
        "polisyos.scientist.orchestration.orchestrator.publisher"
    )

    assert facade.compile_decision_grade_export is canonical.compile_decision_grade_export
    assert root_legacy.__canonical_module__ == "polisyos.scientist.publishing.publisher"
    assert root_legacy.compile_decision_grade_export is canonical.compile_decision_grade_export
    assert orchestrator_legacy is canonical


def test_phase_0_3_planned_scientist_root_module_shims_import() -> None:
    expected = {
        "polisyos.scientist.decision_validity": (
            "polisyos.scientist.validation.decision_validity",
            "2026-12-31",
        ),
        "polisyos.scientist.error_semantics": (
            "polisyos.scientist.orchestration.engine.error_semantics",
            "2026-12-31",
        ),
        "polisyos.scientist.evidence_sources": (
            "polisyos.scientist.evidence.sources",
            "2026-11-30",
        ),
        "polisyos.scientist.feedback_utils": (
            "polisyos.scientist.feedback.utils",
            "2026-11-30",
        ),
        "polisyos.scientist.frontier_runtime": (
            "polisyos.scientist.orchestration.engine.frontier_runtime",
            "2026-12-31",
        ),
        "polisyos.scientist.latent_separation": (
            "polisyos.scientist.methods.causal.latent_separation",
            "2026-12-31",
        ),
        "polisyos.scientist.llm_cycle": (
            "polisyos.scientist.orchestration.llm.cycle",
            "2026-12-31",
        ),
        "polisyos.scientist.publisher": (
            "polisyos.scientist.publishing.publisher",
            "2026-12-31",
        ),
        "polisyos.scientist.reliability_scorecard": (
            "polisyos.scientist.validation.reliability_scorecard",
            "2026-12-31",
        ),
        "polisyos.scientist.remediation_status": (
            "polisyos.scientist.governance.remediation_status",
            "2026-12-31",
        ),
        "polisyos.scientist.replay_backend": (
            "polisyos.scientist.replay.backend",
            "2026-11-30",
        ),
    }
    planned = _planned_source_moves_by_source()

    for legacy_name, (canonical_name, sunset) in expected.items():
        legacy = importlib.import_module(legacy_name)
        canonical = importlib.import_module(canonical_name)

        assert legacy.__canonical_module__ == canonical_name
        assert legacy.__shim_id__ == planned[legacy_name]["shim_id"]
        assert legacy.__shim_sunset_date__ == sunset
        assert legacy.__all__
        assert planned[legacy_name]["target_fqn"] == canonical_name
        assert planned[legacy_name]["test"].endswith(
            "test_phase_0_3_planned_scientist_root_module_shims_import"
        )
        first_export = legacy.__all__[0]
        assert getattr(legacy, first_export) is getattr(canonical, first_export)


def _planned_source_moves_by_source() -> dict[str, dict[str, object]]:
    payload = tomllib.loads((REPO_ROOT / "architecture/shims.toml").read_text(encoding="utf-8"))
    return {entry["source_fqn"]: entry for entry in payload["planned_source_move"]}


def _registered_shims_by_source() -> dict[str, dict[str, object]]:
    payload = tomllib.loads((REPO_ROOT / "architecture/shims.toml").read_text(encoding="utf-8"))
    return {
        entry["source_fqn"]: entry
        for entry in payload["shim"]
        if entry.get("source_fqn", "").startswith("polisyos.scientist.")
    }
