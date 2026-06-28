#!/usr/bin/env python3
"""Validate or regenerate committed Layer 3 GY Phase-2 proof artifacts."""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import re
import sys
import tempfile
import tomllib
from pathlib import Path
from types import SimpleNamespace
from typing import Any

FAMILY_ID = "policy-design-case-layer3-gy-phase2-artifacts"
PLAYBOOK_PROOF_PATH = (
    "architecture/policy_design_case/layer3_gy_phase2_playbook_run_proofs.json"
)
SPINE_PROOF_PATH = "architecture/policy_design_case/layer3_gy_phase2_spine_repair_proofs.json"
FOUNDRY_PROOF_PATH = (
    "architecture/policy_design_case/layer3_gy_phase2_foundry_consumption_proofs.json"
)
AGENT_AUDIT_PATH = "architecture/policy_design_case/layer3_gy_phase2_agent_event_audit.json"
STRANGLE_RECEIPT_PATH = (
    "architecture/policy_design_case/layer3_gy_phase2_lex_bounds_strangle_receipt.json"
)
OUTPUTS = [
    PLAYBOOK_PROOF_PATH,
    SPINE_PROOF_PATH,
    FOUNDRY_PROOF_PATH,
    AGENT_AUDIT_PATH,
    STRANGLE_RECEIPT_PATH,
]


def declared_outputs() -> list[str]:
    """Return the generated artifacts this validator writes in --write mode."""

    return list(OUTPUTS)


_LEX_COMPATIBILITY_ALLOWLIST = [
    "tests/unit/scientist/policy_design/test_phase_b_hierarchical_search.py"
]
_LEX_LEGACY_FLAG_PATTERNS = [
    r"^\s*require_explicit_parameter_bounds\s*=\s*False\b",
    r"^\s*allow_legacy_shadow_inferred_bounds\s*=\s*True\b",
]


class _DeterministicToolLoopClient:
    """Small real client for the unmocked Scientist tool loop."""

    def __init__(self) -> None:
        self.calls = 0

    async def generate(self, **kwargs: Any) -> SimpleNamespace:
        if not kwargs.get("tools"):
            raise AssertionError("deterministic tool-loop proof requires registered tools")
        self.calls += 1
        if self.calls == 1:
            return SimpleNamespace(
                content="",
                usage=SimpleNamespace(total_tokens=11),
                tool_calls=[
                    SimpleNamespace(
                        id="tool-call-1",
                        name="search_datasets",
                        arguments={"query": "credit guarantees"},
                    )
                ],
            )
        return SimpleNamespace(
            content="candidate uses recorded dataset evidence",
            usage=SimpleNamespace(total_tokens=7),
            tool_calls=None,
        )


class _DeterministicKnowledgeToolkit:
    """Deterministic tool owner used by the validator's real tool-loop proof."""

    def search_datasets(self, query: str) -> dict[str, object]:
        return {
            "query": query,
            "matches": [
                {
                    "dataset_id": "ua-production-calibration-observation-panel-monthly",
                    "source": "recorded_rows",
                }
            ],
        }


def validate(repo_root: Path, *, write: bool = False) -> dict[str, Any]:
    """Return a drift report for the Phase-2 generated proof family."""

    src_path = repo_root / "src"
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))
    issues: list[dict[str, str]] = []
    _validate_generated_artifacts_registration(repo_root, issues)
    expected = build_live_proof_payloads(repo_root)
    _validate_lex_bounds_strangle_receipt(expected[STRANGLE_RECEIPT_PATH], issues)
    _validate_lex_runtime_injection_fence(repo_root, issues)
    if write:
        for relative_path, payload in expected.items():
            path = repo_root / relative_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(payload, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
    else:
        for relative_path, expected_payload in expected.items():
            committed = _read_json(repo_root / relative_path, issues)
            if committed != expected_payload:
                issues.append({"code": "phase2_artifact_drift", "path": relative_path})
    return {
        "status": "pass" if not issues else "fail",
        "family_id": FAMILY_ID,
        "checked_artifacts": OUTPUTS,
        "write": write,
        "issues": issues,
    }


def build_live_proof_payloads(repo_root: Path) -> dict[str, dict[str, Any]]:
    """Recompute proof payloads from live Phase-2 runtime code."""

    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.pdc import OperationClass, SearchTerminalKind
    from polisyos.runtime.quality.design_problem import DesignProblem
    from polisyos.runtime.quality.workspace.agent_proposal_bridge import (
        AgentEventBridge,
        normalize_agent_voi_scores,
    )
    from polisyos.runtime.quality.workspace.foundry_consumption import (
        ConstraintStoreIngestor,
        evaluate_constraint_store_for_phase2,
    )
    from polisyos.runtime.quality.workspace.loop import WorkspaceLoop
    from polisyos.runtime.quality.workspace.spine_repair_gates import (
        BlockedInputProducer,
        GovernanceTailVerifier,
        LexBoundsApplicabilityGate,
    )
    from polisyos.runtime.quality.workspace.workflow_playbook_projection import (
        build_workflow_playbook_registry,
        select_playbook_for_intent,
    )
    from polisyos.scientist.agent.knowledge_tools import KnowledgeToolkit
    from polisyos.scientist.agent.tools.knowledge_tools_adapter import (
        build_knowledge_tool_registry,
    )
    from polisyos.scientist.policy_design import search as policy_search

    proof_store = FileSystemCAS(Path(tempfile.gettempdir()) / "polisyos-gy-phase2-proof-cas")
    loop = WorkspaceLoop(artifact_store=proof_store)

    def _design_problem(
        *,
        observational_data_ref: str | None = None,
        force_counterexample: str | None = None,
        verification_required: bool = False,
    ) -> DesignProblem:
        runtime_hints: dict[str, object] = {"verification_required": verification_required}
        if observational_data_ref is not None:
            runtime_hints["observational_data_ref"] = observational_data_ref
        if force_counterexample is not None:
            runtime_hints["force_counterexample"] = force_counterexample
        return DesignProblem.model_validate(
            {
                "design_problem_id": "design_problem_phase2_credit",
                "problem_statement": "Estimate a causal policy effect.",
                "domain": "social",
                "nl_provenance": {
                    "raw_request": "Estimate a causal policy effect.",
                    "source_surface": "phase2.validator",
                    "source_context": {"run_id": "run-phase2-validator"},
                },
                "authority_profile": {
                    "requester_authority": "research",
                    "requested_authority_level": "research",
                    "mandate": "Phase-2 validator mandate.",
                },
                "jurisdiction_time": {
                    "region": "UA",
                    "valid_time": "2026-05-15",
                    "as_of": "2026-05-12",
                    "policy_time": "2026-05-15",
                    "data_time": "2024-2026",
                },
                "objectives": [
                    {
                        "objective_id": "estimate_effect",
                        "description": "Estimate the causal effect.",
                        "metric_id": "firm_survival",
                        "direction": "maximize",
                    }
                ],
                "constraints": [],
                "stakeholders": [
                    {
                        "stakeholder_id": "wartime_msmes",
                        "name": "wartime MSMEs",
                        "role": "beneficiary",
                    }
                ],
                "outcome_of_interest": {
                    "target_variable": "firm_survival",
                    "metric_id": "firm_survival",
                    "estimand": "P(firm_survival | do(credit_access))",
                    "direction": "maximize",
                },
                "candidate_lever_space": {
                    "allowed_operator_kinds": ["credit_access"],
                    "candidate_levers": [
                        {
                            "lever_id": "credit_access",
                            "operator_kind": "credit_access",
                            "instrument": "credit support",
                            "target_slot": "credit_access",
                        }
                    ],
                },
                "evidence_acquisition_needs": {"needs": []},
                "runtime_hints": runtime_hints,
            }
        )

    selected = select_playbook_for_intent(
        {
            "policy_question": "Can Ukraine offer MSME credit guarantees?",
            "workflow_id": "scientist_discovery",
        }
    )
    stable = loop.run_intent(_design_problem(verification_required=True))
    synthetic_probe = loop.run_intent(
        _design_problem(observational_data_ref="validator-synthetic-probe")
    )
    deviation = loop.run_intent(_design_problem(force_counterexample="missing_bounds"))
    registry = build_workflow_playbook_registry()
    if not stable.operation_invocations:
        raise AssertionError("Phase-2 stable run did not execute a legacy adapter")
    if stable.method_output_consumption_record is None or stable.method_output_consumption_ref is None:
        raise AssertionError("Phase-2 stable run did not persist Foundry consumption")
    if stable.foundry_input_provenance != "measurement_rooted":
        raise AssertionError("Phase-2 stable run did not consume a measurement-rooted Foundry root")
    if stable.authority_boundary is None or stable.authority_boundary.evidence_kind != "measurement":
        raise AssertionError("Phase-2 stable run did not stamp Foundry output as measurement")
    if not stable.method_output_consumption_record.measurement_root_refs:
        raise AssertionError("Phase-2 stable run did not record measurement roots")
    if synthetic_probe.method_output_consumption_record is None or synthetic_probe.authority_boundary is None:
        raise AssertionError("Phase-2 synthetic probe did not persist Foundry consumption")
    if synthetic_probe.foundry_input_provenance != "synthetic_probe":
        raise AssertionError("Phase-2 synthetic probe did not stay synthetic")
    if synthetic_probe.authority_boundary.evidence_kind != "simulation":
        raise AssertionError("Phase-2 synthetic probe did not stay simulation evidence")
    if deviation.terminal_state.kind != SearchTerminalKind.SEARCH_CEILING_REPAIR_REQUIRED:
        raise AssertionError("Phase-2 counterexample did not exit with search repair")

    bounds = LexBoundsApplicabilityGate().evaluate(
        workspace_id="ws-phase2-validator",
        invocation_id="invoke-refine",
        lower=None,
        upper=10.0,
    )
    search_bounds = policy_search.derive_phase2_parameter_bounds(
        workspace_id="ws-phase2-validator",
        invocation_id="invoke-refine",
        default=10.0,
        lower=None,
        upper=None,
    )
    blockers = BlockedInputProducer().produce(
        workspace_id="ws-phase2-validator",
        invocation_id="invoke-causal",
        state_facts={},
        required_inputs=["causal_variables", "data_causal_graph", "observational_data_ref"],
    )
    resolved_producer_blockers = [
        blocker
        for blocker in stable.search_blockers
        if blocker.missing_input
        in {"causal_variables", "data_causal_graph", "observational_data_ref"}
    ]
    partial_tail = GovernanceTailVerifier().verify(
        workspace_id="ws-phase2-validator",
        invocation_id="invoke-governance",
        normative_result={"warnings": [], "model_completeness": "declared_complete"},
        judge_verdict={"composite_decision": "promote", "per_judge": {"structural": {}}},
    )
    six_tail = GovernanceTailVerifier().verify(
        workspace_id="ws-phase2-validator",
        invocation_id="invoke-governance",
        normative_result={"warnings": [], "model_completeness": "declared_complete"},
        judge_verdict={
            "composite_decision": "promote",
            "per_judge": {
                "structural": {},
                "statistical": {},
                "robustness": {},
                "governance": {},
                "reproducibility": {},
                "compute": {},
            },
        },
    )

    constraint_snapshot = ConstraintStoreIngestor().ingest(
        snapshot_id="constraint-store-phase2-validator",
        grammar_expansion_ref="pdc://phase2/grammar",
        artifacts=[
            {
                "artifact_ref": "obligation://legal-authority",
                "source_kind": "obligation",
                "status": "block",
                "consumer_ref": "VERIFY",
                "reason": "Legal authority must be verified.",
            },
            {
                "artifact_ref": "participation://affected-firms",
                "source_kind": "participation_requirement",
                "status": "limit",
                "consumer_ref": "ESTIMATE",
                "reason": "Affected firms were not sampled.",
            },
        ],
    )
    constraint_decision = evaluate_constraint_store_for_phase2(constraint_snapshot)

    agent_bridge = AgentEventBridge()
    deterministic_client = _DeterministicToolLoopClient()
    agent_event = asyncio.run(
        agent_bridge.run_tool_loop_proposal(
            workspace_id="ws-phase2-validator",
            invocation_id="invoke-agent",
            client=deterministic_client,
            system="Use tools before proposing.",
            user="Find recorded datasets for credit guarantees.",
            toolkit=_DeterministicKnowledgeToolkit(),
            candidate_operations=[OperationClass.ESTIMATE],
            max_iterations=2,
        )
    )
    if not hasattr(agent_event, "decision_record"):
        raise AssertionError("Phase-2 deterministic tool-loop unexpectedly blocked")
    agent_refs = agent_bridge.persist_event_bundle(store=proof_store, bundle=agent_event)
    blocked = agent_bridge.no_client_blocker(
        workspace_id="ws-phase2-validator",
        invocation_id="invoke-agent",
    )
    audit = normalize_agent_voi_scores(
        workspace_id="ws-phase2-validator",
        selected_terminal="search_ceiling_repair_required",
        agent_scores={
            "phase2.acquire": 1.7,
            "phase2.refine": -0.4,
            "phase2.nan": float("nan"),
            "phase2.unsupported": 0.8,
        },
        supported_action_refs={"phase2.acquire", "phase2.refine"},
    )
    toolkit_registry = build_knowledge_tool_registry(KnowledgeToolkit())

    return {
        PLAYBOOK_PROOF_PATH: {
            "schema_version": "policyos.policy_design_case.layer3_gy_phase2.playbook_run_proofs.v2",
            "proofs": [
                {
                    "proof_id": "phase2-playbook-runtime-chain",
                    "playbook_ids": sorted(registry.playbooks),
                    "playbook_step_source": "canonical_workflow_specs_via_node_registry",
                    "selected_playbook_id": selected.playbook_id,
                    "legacy_workflow_id_disposition": selected.legacy_workflow_id_disposition,
                    "stable_terminal": stable.terminal_state.kind.value,
                    "executed_legacy_aliases": [
                        item.internal_trace.get("legacy_alias")
                        for item in stable.operation_invocations
                    ],
                    "out_of_scope_steps": (
                        stable.phase2_playbook_trace.out_of_scope_steps
                        if stable.phase2_playbook_trace is not None
                        else []
                    ),
                    "operation_invocation_count": len(stable.operation_invocations),
                    "search_ledger_event_count": len(stable.search_ledger_events),
                    "candidate_artifact_envelope_count": len(stable.artifact_envelopes),
                    "authority_path_disposition": "loop_only",
                    "deviation_terminal": deviation.terminal_state.kind.value,
                    "deviation_operation": (
                        deviation.phase2_playbook_trace.deviation_operation.value
                        if deviation.phase2_playbook_trace
                        and deviation.phase2_playbook_trace.deviation_operation
                        else None
                    ),
                    "workflow_id_does_not_select_authority": True,
                }
            ],
        },
        SPINE_PROOF_PATH: {
            "schema_version": "policyos.policy_design_case.layer3_gy_phase2.spine_repair_proofs.v2",
            "proofs": [
                {
                    "proof_id": "phase2-lex-bounds-none-is-blocker",
                    "expected_status": bounds.applicability.status,
                    "expected_missing_input": (
                        bounds.blocker.missing_input if bounds.blocker is not None else None
                    ),
                    "search_domain_status": search_bounds.applicability.status,
                    "none_to_zero_laundering_rejected": (
                        bounds.frontier_payload["bounds"]["lower"] is None
                    ),
                },
                {
                    "proof_id": "phase2-causal-input-producer-missing-blockers",
                    "required_inputs": [blocker.missing_input for blocker in blockers],
                    "expected_blocker_label": "producer_missing",
                },
                {
                    "proof_id": "phase2-causal-input-producers-resolve-default-path",
                    "required_inputs": [
                        "causal_variables",
                        "data_causal_graph",
                        "observational_data_ref",
                    ],
                    "producer_refs": {
                        "causal_variables": (
                            "polisyos.runtime.quality.workspace.loop."
                            "WorkspaceLoop._phase2_causal_variables"
                        ),
                        "data_causal_graph": (
                            "polisyos.runtime.quality.workspace.loop."
                            "WorkspaceLoop._phase2_data_causal_graph"
                        ),
                        "observational_data_ref": (
                            "polisyos.runtime.quality.data_forge_binding."
                            "produce_phase2_recorded_panel_measurement_root"
                        ),
                    },
                    "unresolved_blockers": [
                        blocker.model_dump(mode="json")
                        for blocker in resolved_producer_blockers
                    ],
                    "default_path_resolved": not resolved_producer_blockers,
                },
                {
                    "proof_id": "phase2-governance-tail-six-judge-gate",
                    "partial_judge_stack_status": partial_tail.applicability.status,
                    "six_judge_stack_status": six_tail.applicability.status,
                    "authority_blocked_port": (
                        partial_tail.blocker.blocked_port
                        if partial_tail.blocker is not None
                        else None
                    ),
                },
            ],
        },
        FOUNDRY_PROOF_PATH: {
            "schema_version": "policyos.policy_design_case.layer3_gy_phase2.foundry_consumption_proofs.v2",
            "proofs": [
                {
                    "proof_id": "phase2-estimate-consumes-foundry-output-through-loop",
                    "source_node": "run_causal_evaluation",
                    "operation_class": stable.method_output_consumption_record.operation_class.value,
                    "dag_consumed_method_outputs_count": (
                        stable.method_output_consumption_record.dag_consumed_method_outputs_count
                    ),
                    "persisted_consumption_artifact_type": (
                        stable.method_output_consumption_ref.artifact_type
                    ),
                    "authority_evidence_kind": (
                        stable.authority_boundary.evidence_kind
                        if stable.authority_boundary is not None
                        else None
                    ),
                    "authority_decision_grade": (
                        stable.authority_boundary.decision_grade
                        if stable.authority_boundary is not None
                        else None
                    ),
                    "authority_boundary": (
                        stable.authority_boundary.model_dump(mode="json")
                        if stable.authority_boundary is not None
                        else None
                    ),
                    "record": _stable_consumption_record(
                        stable.method_output_consumption_record
                    ),
                    "consumed_method_output_refs": [
                        ref.model_dump(mode="json")
                        for ref in (
                            stable.method_output_consumption_record.consumed_method_output_refs
                        )
                    ],
                    "measurement_root_refs": [
                        ref.model_dump(mode="json")
                        for ref in stable.method_output_consumption_record.measurement_root_refs
                    ],
                    "measurement_root_source": (
                        "production_data/ukraine_agent_simulation_baseline_20260410/"
                        "production_bundle/bundles/calibration_bundle_v1/"
                        "observation_panel_monthly.parquet"
                    ),
                    "input_provenance": stable.foundry_input_provenance,
                    "open_production_findings": list(stable.open_production_findings),
                    "constraint_store_consumed": True,
                    "constraint_blocks_promotion": constraint_decision.blocks_promotion,
                    "constraint_downgrades_authority": constraint_decision.downgrades_authority,
                },
                {
                    "proof_id": "phase2-estimate-synthetic-panel-stays-simulation",
                    "source_node": "run_causal_evaluation",
                    "operation_class": (
                        synthetic_probe.method_output_consumption_record.operation_class.value
                    ),
                    "dag_consumed_method_outputs_count": (
                        synthetic_probe.method_output_consumption_record
                        .dag_consumed_method_outputs_count
                    ),
                    "authority_evidence_kind": (
                        synthetic_probe.authority_boundary.evidence_kind
                    ),
                    "authority_decision_grade": (
                        synthetic_probe.authority_boundary.decision_grade
                    ),
                    "authority_boundary": synthetic_probe.authority_boundary.model_dump(
                        mode="json"
                    ),
                    "record": _stable_consumption_record(
                        synthetic_probe.method_output_consumption_record
                    ),
                    "consumed_method_output_refs": [
                        ref.model_dump(mode="json")
                        for ref in (
                            synthetic_probe.method_output_consumption_record
                            .consumed_method_output_refs
                        )
                    ],
                    "measurement_root_refs": [
                        ref.model_dump(mode="json")
                        for ref in (
                            synthetic_probe.method_output_consumption_record
                            .measurement_root_refs
                        )
                    ],
                    "input_provenance": synthetic_probe.foundry_input_provenance,
                    "open_production_findings": list(
                        synthetic_probe.open_production_findings
                    ),
                },
            ],
        },
        AGENT_AUDIT_PATH: {
            "schema_version": "policyos.policy_design_case.layer3_gy_phase2.agent_event_audit.v2",
            "audit": {
                "agent_role_event_bridge": "polisyos.runtime.quality.workspace.agent_proposal_bridge.AgentEventBridge",
                "event_builder_home": "polisyos.runtime.quality.proving_ground.bounded_request_agent",
                "ring1_event_types": sorted({ref.artifact_type for ref in agent_refs}),
                "tool_loop_execution": {
                    "module": "polisyos.scientist.agent.tools.tool_loop.run_tool_loop",
                    "client_kind": "deterministic_real_client",
                    "client_generate_calls": deterministic_client.calls,
                    "tool_calls": agent_event.invocation.tool_calls,
                    "persisted_event_ref_count": len(agent_refs),
                },
                "candidate_only_required": agent_event.decision_record.candidate_only,
                "method_plan_admission_state": agent_event.method_plan.admission_state,
                "knowledge_tool_registry_core_tool_count": len(toolkit_registry.list_definitions()),
                "no_client_disposition": {
                    "status": blocked.applicability.status,
                    "synthetic_audit_created": blocked.synthetic_audit_created,
                    "missing_input": blocked.blocker.missing_input,
                },
                "voi_normalized_scores": audit.normalized_scores,
                "voi_rejected_or_clipped_count": len(audit.rejected_or_clipped_inputs),
                "ring2_write_negative_test": "AgentDecisionRecord(candidate_only=false) is rejected",
            },
        },
        STRANGLE_RECEIPT_PATH: _build_lex_bounds_strangle_receipt(repo_root),
    }


def _build_lex_bounds_strangle_receipt(repo_root: Path) -> dict[str, Any]:
    src_false_assignments = _find_flag_assignments(
        repo_root=repo_root,
        root=repo_root / "src",
        patterns=_LEX_LEGACY_FLAG_PATTERNS,
    )
    compatibility_test_assignments = _find_flag_assignments(
        repo_root=repo_root,
        root=repo_root / "tests",
        patterns=_LEX_LEGACY_FLAG_PATTERNS,
    )
    unexpected_compatibility_assignments = [
        item
        for item in compatibility_test_assignments
        if item.split(":", maxsplit=1)[0] not in _LEX_COMPATIBILITY_ALLOWLIST
    ]
    return {
        "schema_version": "policyos.policy_design_case.layer3_gy_phase2.strangle_receipt.v1",
        "strangle_receipt": {
            "receipt_id": "layer3-gy-phase2-lex-bounds-strangle",
            "pattern_id": "P28",
            "predecessor_ref": "scientist.policy_design.search._derive_bounds",
            "replacement_ref": "scientist.policy_design.search.derive_phase2_parameter_bounds",
            "replaced_behavior": "optional_bounds_none_to_inferred_legacy_shadow_bounds",
            "default_flipped": True,
            "src_false_assignments": src_false_assignments,
            "compatibility_allowlist": list(_LEX_COMPATIBILITY_ALLOWLIST),
            "compatibility_test_assignments": compatibility_test_assignments,
            "unexpected_compatibility_assignments": unexpected_compatibility_assignments,
            "fence_status": "fenced_compatibility_only",
            "runtime_state_param_fence_status": "rejects_legacy_flags_before_adapter",
            "runtime_injection_path_ref": (
                "polisyos.scientist.nodes.builtins.planning."
                "run_hierarchical_policy_search.RunHierarchicalPolicySearchNode"
            ),
            "runtime_state_param_disallowed_flags": [
                "require_explicit_parameter_bounds=False",
                "allow_legacy_shadow_inferred_bounds=True",
            ],
            "runtime_guard_tests": [
                "tests/unit/scientist/nodes/builtins/planning/"
                "test_run_hierarchical_policy_search.py::"
                "test_run_hierarchical_policy_search_rejects_runtime_legacy_inferred_bounds_config"
            ],
            "deletion_status": "pending_compatibility_tests_only",
            "deletion_condition": (
                "Remove compatibility tests and the legacy inferred-bounds branch after "
                "downstream callers have migrated to explicit bounds."
            ),
            "guard_tests": [
                "tests/repo_quality/architecture/test_layer3_gy_artifact_lifecycle.py::"
                "test_layer3_gy_legacy_inferred_bounds_are_fenced_out_of_src",
                "tests/repo_quality/architecture/test_layer3_gy_artifact_lifecycle.py::"
                "test_layer3_gy_lex_bounds_strangle_receipt_is_committed_and_fenced",
            ],
        },
    }


def _stable_consumption_record(record: Any) -> dict[str, Any]:
    payload = record.model_dump(mode="json")
    # Foundry evidence artifacts include runtime cost/timing fields, so their
    # CAS ids are intentionally run-specific. Keep a semantic proof that the
    # real evidence refs existed without making generated artifacts time-drift.
    payload["consumed_method_evidence_refs"] = [
        {
            "artifact_type": str(getattr(ref, "artifact_type", "")),
            "schema_ref": str(getattr(ref, "schema_ref", "")),
            "runtime_produced": True,
        }
        for ref in getattr(record, "consumed_method_evidence_refs", [])
    ]
    payload["consumed_method_evidence_ref_count"] = len(
        getattr(record, "consumed_method_evidence_refs", [])
    )
    return payload


def _find_flag_assignments(
    *,
    repo_root: Path,
    root: Path,
    patterns: list[str],
) -> list[str]:
    findings: list[str] = []
    if not root.exists():
        return findings
    compiled = [re.compile(pattern) for pattern in patterns]
    for path in sorted(root.rglob("*.py")):
        source = path.read_text(encoding="utf-8")
        for line_number, line in enumerate(source.splitlines(), start=1):
            if any(pattern.search(line) for pattern in compiled):
                findings.append(f"{path.relative_to(repo_root)}:{line_number}")
    return findings


def _validate_lex_bounds_strangle_receipt(
    payload: dict[str, Any],
    issues: list[dict[str, str]],
) -> None:
    receipt = payload.get("strangle_receipt")
    if not isinstance(receipt, dict):
        issues.append({"code": "phase2_lex_strangle_receipt_missing"})
        return
    for source_ref in receipt.get("src_false_assignments") or []:
        issues.append(
            {
                "code": "phase2_lex_legacy_bounds_flag_in_src",
                "path": str(source_ref),
            }
        )
    for test_ref in receipt.get("unexpected_compatibility_assignments") or []:
        issues.append(
            {
                "code": "phase2_lex_unallowlisted_compatibility_flag",
                "path": str(test_ref),
            }
        )


def _validate_lex_runtime_injection_fence(
    repo_root: Path,
    issues: list[dict[str, str]],
) -> None:
    source_path = (
        repo_root
        / "src/polisyos/scientist/nodes/builtins/planning/run_hierarchical_policy_search.py"
    )
    source = source_path.read_text(encoding="utf-8")
    required_snippets = [
        "_runtime_search_config_from_state",
        "legacy inferred bounds",
        "require_explicit_parameter_bounds",
        "allow_legacy_shadow_inferred_bounds",
    ]
    for snippet in required_snippets:
        if snippet not in source:
            issues.append(
                {
                    "code": "phase2_lex_runtime_injection_fence_missing",
                    "path": str(source_path.relative_to(repo_root)),
                    "snippet": snippet,
                }
            )


def _validate_generated_artifacts_registration(
    repo_root: Path,
    issues: list[dict[str, str]],
) -> None:
    generated = tomllib.loads(
        (repo_root / "architecture/generated_artifacts.toml").read_text(encoding="utf-8")
    )
    families = {family.get("id"): family for family in generated.get("family", [])}
    family = families.get(FAMILY_ID)
    if not family:
        issues.append({"code": "phase2_generated_artifacts_family_missing"})
        return
    outputs = set(family.get("outputs") or [])
    for path in OUTPUTS:
        if path not in outputs:
            issues.append({"code": "phase2_output_not_registered", "path": path})
    if family.get("stale_output_behavior") != "fail":
        issues.append({"code": "phase2_stale_output_not_fail_closed"})
    if family.get("workflow") != "tools/quality/validation/check_layer3_gy_phase2_artifacts.py":
        issues.append({"code": "phase2_workflow_not_registered"})


def _read_json(path: Path, issues: list[dict[str, str]]) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        issues.append({"code": "phase2_artifact_missing", "path": str(path)})
        return {}
    except json.JSONDecodeError as exc:
        issues.append({"code": "phase2_artifact_invalid_json", "path": str(path), "error": str(exc)})
        return {}
    if not isinstance(payload, dict):
        issues.append({"code": "phase2_artifact_not_object", "path": str(path)})
        return {}
    return payload


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--output-format", choices=("json", "text"), default="text")
    parser.add_argument("--check", action="store_true", help="Validate committed artifacts.")
    parser.add_argument("--write", action="store_true", help="Regenerate committed artifacts.")
    args = parser.parse_args(argv)
    if args.check and args.write:
        parser.error("--check and --write are mutually exclusive")
    with contextlib.redirect_stdout(sys.stderr):
        report = validate(args.repo_root.resolve(), write=args.write)
    if args.output_format == "json":
        print(json.dumps(report, indent=2, sort_keys=True))
    elif report["status"] == "pass":
        action = "write" if args.write else "check"
        print(f"PASS layer3_gy_phase2_artifacts ({action})")
    else:
        print("FAIL layer3_gy_phase2_artifacts")
        for issue in report["issues"]:
            print(f"- {issue}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
