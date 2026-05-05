"""Explicit blueprint compliance audit matrix for Scientist runtime invariants."""

from __future__ import annotations

import inspect
from importlib import import_module
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from polisyos.scientist.search.artifact_minimality import ArtifactMinimalityMixin


class ComplianceAuditEntry(BaseModel):
    """One blueprint invariant tracked by the explicit Scientist runtime compliance audit."""

    model_config = ConfigDict(extra="forbid")

    invariant_id: str = Field(min_length=1)
    description: str = Field(min_length=1)
    enforcement_kind: Literal["runtime_assertion", "workflow_gate", "test"]
    enforcement_target: str = Field(min_length=1)
    status: Literal["active", "partial"] = "active"


def scientist_blueprint_compliance_audit() -> list[ComplianceAuditEntry]:
    """Return the invariant matrix that the Scientist blueprint treats as non-negotiable."""
    return [
        ComplianceAuditEntry(
            invariant_id="uncertainty.max_when_unassessed",
            description="Absence of assessment is serialized as maximum uncertainty, never low uncertainty.",
            enforcement_kind="test",
            enforcement_target="tests/unit/scientist/search/funnel/test_level0_static.py::test_unassessed_uncertainty_envelope",
        ),
        ComplianceAuditEntry(
            invariant_id="cheap_rejection.failure_card_required",
            description="Cheap-stage rejection emits a TypedFailureCard with remediation context.",
            enforcement_kind="test",
            enforcement_target="tests/unit/scientist/search/test_phase_b_policy_runtime.py",
        ),
        ComplianceAuditEntry(
            invariant_id="promotion.hidden_holdout_required",
            description="Promotion fails closed when hidden holdout, replay, or governance evidence is missing.",
            enforcement_kind="runtime_assertion",
            enforcement_target="polisyos.scientist.search.promotion_evidence.PromotionEvidenceBundle.missing_required_refs",
        ),
        ComplianceAuditEntry(
            invariant_id="promotion.synthetic_evidence_forbidden",
            description="Promotion consumes persisted PromotionEvidenceBundle refs instead of synthesizing holdout/meta evidence.",
            enforcement_kind="workflow_gate",
            enforcement_target="polisyos.scientist.nodes.builtins.decide.run_policy_blueprint_runtime.RunPolicyBlueprintRuntimeNode",
        ),
        ComplianceAuditEntry(
            invariant_id="policy_runtime.blueprint_only",
            description="Production policy workflow resolves to the blueprint-native L0-L6 runtime.",
            enforcement_kind="workflow_gate",
            enforcement_target="polisyos.scientist.workflows.policy_design.policy_design_workflow_spec",
        ),
        ComplianceAuditEntry(
            invariant_id="discovery.workflow.first_class",
            description="Discovery exists as a dedicated first-class Scientist workflow and output bundle surface.",
            enforcement_kind="workflow_gate",
            enforcement_target="polisyos.scientist.workflows.discovery.discovery_workflow_spec",
        ),
        ComplianceAuditEntry(
            invariant_id="cross_layer_refs.cas_pinned",
            description="Cross-layer graph prior inputs must be CAS-pinned and consistent before workflow execution starts.",
            enforcement_kind="runtime_assertion",
            enforcement_target="polisyos.scientist.workflows.builder._pin_cross_layer_input_ref",
        ),
        ComplianceAuditEntry(
            invariant_id="benchmarks.registry_authoritative",
            description="Runtime benchmark assets are resolved through BenchmarkRegistry instead of free-form state params.",
            enforcement_kind="workflow_gate",
            enforcement_target="polisyos.scientist.search.benchmark_registry.BenchmarkRegistry",
        ),
        ComplianceAuditEntry(
            invariant_id="promotion.replay_bundle_required",
            description="Replay bundle is mandatory for promotion; checkpoint refs are not accepted as a replay substitute.",
            enforcement_kind="runtime_assertion",
            enforcement_target="polisyos.scientist.nodes.builtins.decide.run_policy_blueprint_runtime._resolve_replay_bundle_ref",
        ),
        ComplianceAuditEntry(
            invariant_id="transfer.no_cross_domain_surrogate_mixing",
            description="Predictive VOI training never mixes cross-domain observations by default.",
            enforcement_kind="test",
            enforcement_target="tests/unit/scientist/search/test_voi_scheduler.py::test_predictive_voi_does_not_mix_cross_domain_observations_by_default",
        ),
        ComplianceAuditEntry(
            invariant_id="registry.legacy_policy_shortcuts_not_registered",
            description="Legacy policy shortcut nodes are absent from the production builtin registry.",
            enforcement_kind="test",
            enforcement_target="tests/unit/scientist/nodes/test_builtin_registry_cutover.py",
        ),
        ComplianceAuditEntry(
            invariant_id="discovery.required_edges_need_provenance",
            description="Required discovery edges without provenance are rejected.",
            enforcement_kind="test",
            enforcement_target="tests/unit/scientist/nodes/builtins/planning/test_compile_cross_graph_evidence.py",
        ),
        ComplianceAuditEntry(
            invariant_id="public_surface.no_legacy_shortcuts",
            description="Scientist package roots do not advertise legacy shortcut nodes or legacy search adapters.",
            enforcement_kind="test",
            enforcement_target="tests/unit/scientist/facade/test_public_surface_cutover.py",
        ),
        ComplianceAuditEntry(
            invariant_id="artifacts.minimality_tag_required",
            description="Blueprint artifacts expose non-empty artifact_functions minimality tags.",
            enforcement_kind="runtime_assertion",
            enforcement_target="polisyos.scientist.search.compliance_audit.validate_scientist_blueprint_artifact_minimality",
        ),
        ComplianceAuditEntry(
            invariant_id="degraded.synthetic_runtime_caps_readiness",
            description="Synthetic or degraded policy-runtime evidence caps readiness and blocks promotion.",
            enforcement_kind="test",
            enforcement_target="tests/unit/scientist/search/test_phase_b_policy_runtime.py::test_synthetic_runtime_caps_readiness_and_blocks_promotion",
        ),
        ComplianceAuditEntry(
            invariant_id="discovery.strict_seed_reproducibility_measured",
            description="Strict discovery outputs record measured seed reproducibility when replay scores are provided.",
            enforcement_kind="test",
            enforcement_target="tests/unit/scientist/discovery/test_output.py::test_discovery_artifact_builder_marks_measured_seed_reproducibility_when_replay_scores_present",
        ),
    ]


_MINIMALITY_AUDIT_MODULES = (
    "polisyos.scientist.policy_design.output",
    "polisyos.scientist.discovery.output",
    "polisyos.scientist.discovery.priors",
    "polisyos.scientist.discovery.aggregator",
    "polisyos.scientist.discovery.stability",
    "polisyos.scientist.discovery.utility_judge",
    "polisyos.scientist.discovery.active",
    "polisyos.scientist.search.readiness",
    "polisyos.scientist.search.actionable_side_information",
)


def validate_scientist_blueprint_artifact_minimality() -> list[str]:
    """Verify schema-versioned blueprint artifacts expose non-empty minimality tags."""

    problems: list[str] = []
    for module_name in _MINIMALITY_AUDIT_MODULES:
        module = import_module(module_name)
        for name, obj in vars(module).items():
            if not inspect.isclass(obj):
                continue
            if obj.__module__ != module.__name__:
                continue
            if not issubclass(obj, BaseModel):
                continue
            model_fields = getattr(obj, "model_fields", {})
            if "schema_version" not in model_fields:
                continue
            if not issubclass(obj, ArtifactMinimalityMixin):
                problems.append(f"{module_name}.{name}: missing ArtifactMinimalityMixin")
                continue
            field_info = model_fields.get("artifact_functions")
            if field_info is None:
                problems.append(f"{module_name}.{name}: missing artifact_functions field")
                continue
            default_factory = getattr(field_info, "default_factory", None)
            try:
                default_value = (
                    default_factory() if default_factory is not None else field_info.default
                )
            except Exception as exc:
                problems.append(
                    f"{module_name}.{name}: artifact_functions default_factory failed: {type(exc).__name__}"
                )
                continue
            if not default_value:
                problems.append(f"{module_name}.{name}: artifact_functions default is empty")
    return problems


def validate_scientist_blueprint_compliance_targets() -> list[str]:
    """Resolve every audit target to a real symbol or test file path."""

    repo_root = Path(__file__).resolve().parents[4]
    problems: list[str] = []
    for entry in scientist_blueprint_compliance_audit():
        target = entry.enforcement_target
        if entry.enforcement_kind == "test":
            target_path = (repo_root / target.split("::", 1)[0]).resolve()
            if not target_path.exists():
                problems.append(f"{entry.invariant_id}: missing test target {target}")
            continue
        module = None
        attr_path = ""
        parts = target.split(".")
        for index in range(len(parts), 0, -1):
            candidate_module = ".".join(parts[:index])
            try:
                module = import_module(candidate_module)
            except Exception:
                continue
            attr_path = ".".join(parts[index:])
            break
        if module is None:
            problems.append(f"{entry.invariant_id}: import failed for {target}")
            continue
        if not attr_path:
            continue
        current = module
        for attr in attr_path.split("."):
            if not hasattr(current, attr):
                problems.append(f"{entry.invariant_id}: missing attribute {target}")
                break
            current = getattr(current, attr)
    return problems


__all__ = [
    "ComplianceAuditEntry",
    "scientist_blueprint_compliance_audit",
    "validate_scientist_blueprint_artifact_minimality",
    "validate_scientist_blueprint_compliance_targets",
]
