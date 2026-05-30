"""Import contract tests for the Scientist methods lane."""

from __future__ import annotations

import importlib
import importlib.util
import json
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]


def _find_spec(module_name: str) -> object | None:
    try:
        return importlib.util.find_spec(module_name)
    except ModuleNotFoundError:
        return None


def test_zero_noncompat_shims_are_removed_from_import_surface() -> None:
    removed_imports = (
        "polisyos.foundry.methods.catalog_snapshot",
        "polisyos.foundry.methods.consensus",
        "polisyos.foundry.methods.linker",
        "polisyos.foundry.methods.merge_engine",
        "polisyos.foundry.methods.plan_optimizer",
        "polisyos.foundry.methods.slot_schema",
        "polisyos.foundry.methods.specialization",
        "polisyos.scientist.autotune",
        "polisyos.scientist.causal",
        "polisyos.scientist.compute.advanced_methods",
        "polisyos.scientist.continuous_governance",
        "polisyos.scientist.discovery",
        "polisyos.scientist.discovery.prior_miner",
        "polisyos.scientist.discovery.schema",
        "polisyos.scientist.discovery.workers",
        "polisyos.scientist.doe",
        "polisyos.scientist.kernel",
        "polisyos.scientist.llm",
        "polisyos.scientist.memory",
        "polisyos.scientist.orchestration.orchestrator.publisher",
        "polisyos.scientist.orchestrator",
        "polisyos.scientist.orchestrator.publisher",
        "polisyos.scientist.policy_verified",
        "polisyos.scientist.verification",
        "polisyos.scientist.workflows.selection",
    )

    for module_name in removed_imports:
        assert _find_spec(module_name) is None, module_name


def test_tiny_batch_a_shims_are_removed_from_import_surface() -> None:
    removed_imports = (
        "polisyos.foundry.agent_metrics",
        "polisyos.foundry.agents",
        "polisyos.foundry.conflict_checker",
        "polisyos.foundry.constraints_engine",
        "polisyos.foundry.cost_model",
        "polisyos.foundry.layout",
        "polisyos.foundry.loss",
        "polisyos.foundry.mechanism_design",
        "polisyos.foundry.merge_engine",
        "polisyos.foundry.patch_vm",
        "polisyos.foundry.profiles",
        "polisyos.foundry.queue",
        "polisyos.foundry.registry",
        "polisyos.foundry.social_weights",
        "polisyos.foundry.specs",
        "polisyos.foundry.trace",
        "polisyos.foundry.utils",
        "polisyos.foundry.welfare_bounds",
        "polisyos.scientist.decision_validity",
        "polisyos.scientist.error_semantics",
        "polisyos.scientist.frontier_runtime",
        "polisyos.scientist.latent_separation",
        "polisyos.scientist.llm_cycle",
        "polisyos.scientist.reliability_scorecard",
        "polisyos.scientist.remediation_status",
    )

    for module_name in removed_imports:
        assert _find_spec(module_name) is None, module_name


def test_tiny_batch_b_shims_are_removed_from_import_surface() -> None:
    removed_imports = (
        "polisyos.foundry.executor",
        "polisyos.foundry.quickstart",
        "polisyos.ir.predicate",
        "polisyos.ir.units",
        "polisyos.scientist.evidence_sources",
        "polisyos.scientist.feedback_utils",
        "polisyos.scientist.publisher",
        "polisyos.scientist.replay_backend",
    )

    for module_name in removed_imports:
        assert _find_spec(module_name) is None, module_name


def test_tiny_batch_c_package_shims_are_removed_from_import_surface() -> None:
    removed_imports = (
        "polisyos.scientist.claims",
        "polisyos.scientist.claims.audit",
        "polisyos.scientist.claims.diff",
        "polisyos.scientist.claims.export",
        "polisyos.scientist.claims.ledger",
        "polisyos.scientist.claims.lifecycle",
        "polisyos.scientist.claims.models",
        "polisyos.scientist.claims.projections",
        "polisyos.scientist.claims.readiness",
        "polisyos.scientist.claims.validators",
        "polisyos.scientist.engine",
        "polisyos.scientist.engine.state",
        "polisyos.scientist.search",
        "polisyos.scientist.search.judge_stack",
        "polisyos.scientist.search.objective",
        "polisyos.scientist.search.funnel",
        "polisyos.scientist.search.funnel.level2_causal",
        "polisyos.scientist.search.strategies",
        "polisyos.scientist.search.strategies.grid",
        "polisyos.scientist.workflows",
        "polisyos.scientist.workflows.builder",
        "polisyos.scientist.human_review",
        "polisyos.scientist.human_review.models",
        "polisyos.scientist.provenance",
        "polisyos.scientist.provenance.run_dag",
        "polisyos.scientist.research_dag",
        "polisyos.scientist.research_dag.models",
        "polisyos.scientist.backtesting",
        "polisyos.scientist.backtesting.composition_bridge",
        "polisyos.scientist.backtesting.plan",
        "polisyos.scientist.backtesting.temporal",
    )

    for module_name in removed_imports:
        assert _find_spec(module_name) is None, module_name


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
        assert (
            closeout["legacy_roots"]
            or closeout["scoped_ok_roots"]
            or closeout.get("retired_legacy_roots")
        )
        assert closeout["non_overlap_rationale"]
        assert closeout["test"].endswith("test_phase2_2_scientist_parallel_families_have_closeout_decisions")


def test_phase2_2_retired_compatibility_roots_are_not_registered_in_shims() -> None:
    registered = _registered_shims_by_source()

    assert "polisyos.scientist.claims" not in registered
    assert "polisyos.scientist.search" not in registered


def test_phase2_2_evidence_compatibility_roots_are_not_canonical_roots() -> None:
    payload = tomllib.loads(
        (REPO_ROOT / "architecture/packages/scientist.toml").read_text(encoding="utf-8")
    )
    layout = payload["layout"]
    canonical = set(layout["canonical_first_level_roots"])
    compatibility = set(layout["compatibility_shim_roots"])

    assert "src/polisyos/scientist/claims" not in canonical
    assert "src/polisyos/scientist/claims" not in compatibility
    assert "src/polisyos/scientist/search" not in canonical
    assert "src/polisyos/scientist/search" not in compatibility


def test_phase2_1_publisher_implementation_lives_in_publishing_module() -> None:
    canonical = importlib.import_module("polisyos.scientist.publishing.publisher")
    facade = importlib.import_module("polisyos.scientist.publishing")

    assert facade.compile_decision_grade_export is canonical.compile_decision_grade_export


def _registered_shims_by_source() -> dict[str, dict[str, object]]:
    payload = tomllib.loads((REPO_ROOT / "architecture/shims.toml").read_text(encoding="utf-8"))
    return {
        entry["source_fqn"]: entry
        for entry in payload["shim"]
        if entry.get("source_fqn", "").startswith("polisyos.scientist.")
    }
