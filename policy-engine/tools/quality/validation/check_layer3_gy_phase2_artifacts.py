#!/usr/bin/env python3
"""Validate or regenerate committed Layer 3 GY Phase-2 proof artifacts."""

from __future__ import annotations

from time import perf_counter as _timing_perf_counter

_TIMING_STARTED_AT = _timing_perf_counter()

import argparse
import ast
import asyncio
import contextlib
import hashlib
import json
import os
import re
import sys
import tempfile
import tomllib
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from tools.lib.timing import run_timed_entrypoint

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


def recompute_foundry_binding_vocabulary() -> dict[str, Any]:
    """Classify the complete method vocabulary without claiming binding execution.

    Registry identities are reconciled with both immutable snapshot views. Input
    contracts come from each real signature and executable annotation; the
    materializer's target registry is a capability map, never the denominator.
    """
    from collections import Counter
    from dataclasses import is_dataclass
    from typing import get_args, get_type_hints

    from pydantic import BaseModel

    from polisyos.foundry.data_plane.bindings import _METHOD_CONTRACT_ALLOW_REGISTRY
    from polisyos.foundry.methods.catalog import ensure_all_methods_registered
    from polisyos.foundry.methods.catalog.causal.protocols import PanelObservationalData
    from polisyos.foundry.methods.selection.advisor import method_accepts_input_contract
    from polisyos.foundry.methods.selection.registry import MethodRegistry

    def inspect_annotation(
        annotation: object, contract_ids: set[str], typed_inputs: set[str]
    ) -> None:
        contract_id = getattr(annotation, "contract_id", None)
        if isinstance(contract_id, str) and contract_id:
            contract_ids.add(contract_id)
        if isinstance(annotation, type) and (
            issubclass(annotation, BaseModel) or is_dataclass(annotation)
        ):
            typed_inputs.add(f"{annotation.__module__}.{annotation.__qualname__}")
        for argument in get_args(annotation):
            inspect_annotation(argument, contract_ids, typed_inputs)

    registry = MethodRegistry.get_instance()
    bootstrap = ensure_all_methods_registered(registry)
    methods: list[dict[str, Any]] = []
    with registry.snapshot_scope() as snapshot:
        signatures = registry.list_all()
        entries = list(snapshot.entries())
        snapshot_signatures = list(snapshot.signatures())
        identities = {(item.fqn, item.abi_digest()) for item in signatures}
        assert (
            identities
            == {(entry.fqn, entry.signature.abi_digest()) for entry in entries}
            == {(item.fqn, item.abi_digest()) for item in snapshot_signatures}
        )
        assert len(identities) == len(signatures) == len(entries) == len(snapshot_signatures)
        for signature in signatures:
            contract_ids = {slot.contract_id for slot in signature.input_slots if slot.contract_id}
            typed_inputs: set[str] = set()
            errors: list[dict[str, str]] = []
            slots = [
                {"name": slot.name, "contract_id": slot.contract_id}
                for slot in signature.input_slots
            ]

            accepts_panel: bool | None = None
            try:
                method = registry.get(signature.fqn)
                for attribute, parameter in (
                    ("materialize_input", "return"),
                    ("pure_step", "state"),
                ):
                    function = getattr(method, attribute, None)
                    if function is None:
                        continue
                    try:
                        hints = get_type_hints(function)
                        inspect_annotation(hints.get(parameter), contract_ids, typed_inputs)
                    except Exception as exc:
                        errors.append(
                            {"surface": attribute, "error": f"{type(exc).__name__}: {exc}"}
                        )
                accepts_panel = method_accepts_input_contract(
                    method, PanelObservationalData.contract_id
                )
            except Exception as exc:
                errors.append({"surface": "registry.get", "error": f"{type(exc).__name__}: {exc}"})
            targets: list[dict[str, Any]] = []
            for contract_id in sorted(contract_ids):
                target = _METHOD_CONTRACT_ALLOW_REGISTRY.get(contract_id)
                if target is None:
                    targets.append({"contract_id": contract_id, "state": "no_materializer_target"})
                    continue
                try:
                    assert target.model_type.contract_id == contract_id
                    target.model_type.model_json_schema()
                    targets.append(
                        {
                            "contract_id": contract_id,
                            "state": "target_schema_resolved",
                            "target_fqn": target.contract_fqn,
                        }
                    )
                except Exception as exc:
                    errors.append({"surface": contract_id, "error": f"{type(exc).__name__}: {exc}"})
                    targets.append({"contract_id": contract_id, "state": "ambiguous"})
            support = (
                "ambiguous"
                if errors
                else "recorded_panel_compatible"
                if accepts_panel
                else "other_typed_contract"
                if contract_ids
                else "typed_input_without_contract_id"
                if typed_inputs
                else "no_concrete_input_contract_declared"
            )
            methods.append(
                {
                    "method_fqn": signature.fqn,
                    "signature_digest": signature.abi_digest(),
                    "input_slots": slots,
                    "typed_input_fqns": sorted(typed_inputs),
                    "contract_targets": targets,
                    "recorded_panel_compatible": accepts_panel,
                    "support_state": support,
                    "errors": errors,
                }
            )
        primary_slots = {
            (row["method_fqn"], slot["name"], slot["contract_id"])
            for row in methods
            for slot in row["input_slots"]
        }
        independent_slots = {
            (entry.fqn, slot.name, slot.contract_id)
            for entry in entries
            for slot in entry.signature.input_slots
        }
        assert primary_slots == independent_slots
        slot_count = sum(len(row["input_slots"]) for row in methods)
        assert slot_count == len(independent_slots)
        assert identities == {(item.fqn, item.abi_digest()) for item in registry.list_all()}, (
            "Method vocabulary changed during executable-input resolution"
        )
    statuses = dict(sorted(Counter(row["support_state"] for row in methods).items()))
    assert statuses == {
        state: sum(row["support_state"] == state for row in methods) for state in statuses
    }
    return {
        "coverage_claim": "full_vocabulary_classified_not_all_methods_executed",
        "denominator_owner": "MethodRegistry after canonical all-method bootstrap",
        "denominator": {
            "list_all": len(signatures),
            "snapshot_entries": len(entries),
            "snapshot_signatures": len(snapshot_signatures),
            "input_slots": slot_count,
            "snapshot_input_slot_identities": len(independent_slots),
        },
        "bootstrap_errors": [str(error) for error in bootstrap.errors],
        "discovery_errors": list(bootstrap.discovery_errors),
        "support_states": statuses,
        "methods": methods,
    }


def validate_foundry_binding_vocabulary(report: dict[str, Any]) -> list[dict[str, str]]:
    """Recompute vocabulary and reject missing, extra, or changed identities/content."""
    expected = recompute_foundry_binding_vocabulary()
    issues: list[dict[str, str]] = []

    def index(payload: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
        result: dict[tuple[str, str], dict[str, Any]] = {}
        rows = payload.get("methods")
        if not isinstance(rows, list):
            issues.append({"code": "c3_method_vocabulary_rows_unreadable"})
            return result
        for row in rows:
            if (
                not isinstance(row, dict)
                or not isinstance(row.get("method_fqn"), str)
                or not isinstance(row.get("signature_digest"), str)
            ):
                issues.append({"code": "c3_method_vocabulary_row_unreadable"})
                continue
            identity = (row["method_fqn"], row["signature_digest"])
            if identity in result:
                issues.append(
                    {
                        "code": "c3_method_vocabulary_identity_duplicate",
                        "method_fqn": identity[0],
                        "signature_digest": identity[1],
                    }
                )
            result[identity] = row
        return result

    actual_rows, expected_rows = index(report), index(expected)
    for identities, code in (
        (expected_rows.keys() - actual_rows.keys(), "c3_method_vocabulary_identity_missing"),
        (actual_rows.keys() - expected_rows.keys(), "c3_method_vocabulary_identity_extra"),
    ):
        issues.extend(
            {"code": code, "method_fqn": fqn, "signature_digest": digest}
            for fqn, digest in sorted(identities)
        )
    for identity in sorted(actual_rows.keys() & expected_rows.keys()):
        if actual_rows[identity] != expected_rows[identity]:
            issues.append(
                {
                    "code": "c3_method_vocabulary_content_drift",
                    "method_fqn": identity[0],
                    "signature_digest": identity[1],
                }
            )
    if {key: value for key, value in report.items() if key != "methods"} != {
        key: value for key, value in expected.items() if key != "methods"
    }:
        issues.append({"code": "c3_method_vocabulary_basis_drift"})
    return issues


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
        PLAYBOOK_PROOF_PATH: build_playbook_admission_proof(
            repo_root, stable=stable, deviation=deviation, selected=selected,
            registry=registry, store=proof_store,
        ),
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


def build_playbook_admission_proof(
    repo_root: Path,
    *,
    stable: Any,
    deviation: Any,
    selected: Any,
    registry: Any,
    store: Any,
) -> dict[str, Any]:
    """Bind proof to the persisted admissions actually consulted by the loop.

    This callable permits focused C1 verification. The full family producer still
    requires every Foundry, governance and agent proof before returning artifacts.
    """
    from polisyos.core.canon import to_canonical_bytes
    from polisyos.runtime.quality.workspace.scientist_node_adapters import (
        _CANON,
        _read_binding,
    )

    candidates = {
        step.step_id: step for playbook in registry.playbooks.values() for step in playbook.steps
    }
    if len(candidates) != sum(len(item.steps) for item in registry.playbooks.values()):
        raise AssertionError("c1_duplicate_candidate_identity")
    if any(step.admission_state != "candidate_unverified" for step in candidates.values()):
        raise AssertionError("c1_registry_step_already_admitted")
    if not stable.adapter_admissions:
        raise AssertionError("c1_default_trajectory_not_attempted")
    witnesses = []
    raw_witnesses = []
    admitted_invocations = []
    admitted_events = []
    admitted_envelopes = []
    for admission in stable.adapter_admissions:
        candidate = admission.candidate
        if candidates.get(candidate.step_id) != candidate:
            raise AssertionError("c1_admission_candidate_binding_mismatch")
        report = admission.conformance
        if admission.conformance_ref is None or admission.conformance_ref != report.conformance_ref:
            raise AssertionError("c1_conformance_receipt_missing")
        receipt_binding, raw, manifest = _read_binding(
            store, admission.conformance_ref, "conformance",
        )
        if raw != to_canonical_bytes(report.model_dump(mode="json"), _CANON):
            raise AssertionError("c1_conformance_receipt_payload_mismatch")
        if (
            manifest.producer is None
            or str(manifest.producer.component) != candidate.node_id
            or manifest.producer.version != report.rule_version
            or report.node_spec_hash != candidate.node_spec_hash
            or report.contract_hash != candidate.adapter_contract_hash
            or admission.smoke_attempted != report.smoke_attempted
        ):
            raise AssertionError("c1_conformance_provenance_binding_mismatch")
        bindings = [
            *report.input_bindings, *report.source_output_bindings, *report.output_bindings,
            *([report.applicability_binding] if report.applicability_binding else []),
        ]
        semantic_bindings = {}
        for binding in bindings:
            actual, _, bound_manifest = _read_binding(store, binding.artifact_ref, binding.path)
            if actual != binding:
                raise AssertionError(f"c1_admission_byte_binding_mismatch:{binding.path}")
            semantic_manifest = bound_manifest.model_dump(mode="json", by_alias=True)
            del semantic_manifest["created_at"]
            semantic_bindings[(binding.path, str(binding.artifact_ref.artifact_id))] = {
                **binding.model_dump(mode="json", exclude={"manifest_hash"}),
                "manifest_semantic_digest": "sha256:" + hashlib.sha256(
                    to_canonical_bytes(semantic_manifest, _CANON),
                ).hexdigest(),
            }
        execution = report.execution
        if admission.step is not None:
            if not report.passed or not report.smoke_attempted or execution is None:
                raise AssertionError("c1_unverified_operation_admitted")
            if set(candidate.produced_ports) != {item.path for item in report.output_bindings}:
                raise AssertionError("c1_admitted_output_population_mismatch")
            admitted_invocations.append(execution.invocation)
            admitted_events.append(execution.ledger_event)
            admitted_envelopes.extend(execution.artifact_envelopes)
        elif admission.blocker is None or report.passed:
            raise AssertionError("c1_refusal_not_typed")
        raw_witness = {
            "candidate": candidate.model_dump(mode="json"),
            "admission_state": "admitted" if admission.step is not None else "blocked",
            "conformance": report.model_dump(mode="json"),
            "conformance_ref": admission.conformance_ref.model_dump(mode="json"),
            "receipt_byte_binding": receipt_binding.model_dump(mode="json"),
            "smoke_attempted": admission.smoke_attempted,
            "operation_invocation_id": (
                execution.invocation.invocation_id if admission.step is not None else None
            ),
            "blocker": admission.blocker.model_dump(mode="json") if admission.blocker else None,
        }
        raw_witnesses.append(raw_witness)
        semantic_report = report.model_dump(mode="json")
        for field in ("input_bindings", "source_output_bindings", "output_bindings"):
            semantic_report[field] = [
                semantic_bindings[(item.path, str(item.artifact_ref.artifact_id))]
                for item in getattr(report, field)
            ]
        if report.applicability_binding is not None:
            binding = report.applicability_binding
            semantic_report["applicability_binding"] = semantic_bindings[
                (binding.path, str(binding.artifact_ref.artifact_id))
            ]
        semantic_digest = "sha256:" + hashlib.sha256(
            to_canonical_bytes(semantic_report, _CANON),
        ).hexdigest()
        # These raw receipt identities transitively contain input-manifest
        # created_at through their full manifest hashes. Rebind them to the
        # recomputed semantic receipt; retain the originals in command output.
        receipt_manifest = manifest.model_dump(mode="json", by_alias=True)
        del receipt_manifest["created_at"]
        receipt_manifest["artifact_id"] = semantic_digest
        receipt_manifest["integrity"]["sha256"] = semantic_digest.removeprefix("sha256:")
        witnesses.append({
            key: value for key, value in raw_witness.items()
            if key not in {"conformance", "conformance_ref", "receipt_byte_binding"}
        } | {
            "conformance": semantic_report,
            "conformance_semantic_digest": semantic_digest,
            "conformance_manifest_semantic_digest": "sha256:" + hashlib.sha256(
                to_canonical_bytes(receipt_manifest, _CANON),
            ).hexdigest(),
        })
    if (
        stable.operation_invocations != admitted_invocations
        or stable.search_ledger_events != admitted_events
        or stable.artifact_envelopes != admitted_envelopes
    ):
        raise AssertionError("c1_loop_did_not_reuse_exact_admitted_execution")
    strangle = recompute_playbook_admission_strangle(repo_root)
    if strangle["unexpected_callers"]:
        raise AssertionError(f"c1_shape_only_admission_bypass:{strangle['unexpected_callers']}")
    print(json.dumps({
        "proof_id": "c1-admission-cas-readback",
        "raw_run_admissions": raw_witnesses,
    }, sort_keys=True), file=sys.stderr)
    return {
        "schema_version": "policyos.policy_design_case.layer3_gy_phase2.playbook_run_proofs.v3",
        "projection_policy": {
            "excluded_run_emission_field": "ArtifactManifest.created_at",
            "recomputed_dependent_identities": [
                "binding.manifest_hash", "conformance_ref", "receipt_byte_binding",
            ],
            "raw_custody_evidence": "complete_deciding_command_output",
            "semantic_digests_are_cas_addresses": False,
        },
        "proofs": [{
            "proof_id": "phase2-playbook-runtime-chain",
            "proof_source": "loop_admission_conformance_cas_readback_recompute",
            "playbook_ids": sorted(registry.playbooks),
            "playbook_step_source": "canonical_workflow_specs_via_node_registry",
            "candidate_step_ids": sorted(candidates),
            "candidate_steps": [candidates[key].model_dump(mode="json") for key in sorted(candidates)],
            "adapter_admissions": witnesses,
            "selected_playbook_id": selected.playbook_id,
            "legacy_workflow_id_disposition": selected.legacy_workflow_id_disposition,
            "stable_terminal": stable.terminal_state.kind.value,
            "executed_legacy_aliases": [
                item.internal_trace["legacy_alias"] for item in admitted_invocations
            ],
            "out_of_scope_steps": stable.phase2_playbook_trace.out_of_scope_steps,
            "operation_invocation_ids": [item.invocation_id for item in admitted_invocations],
            "search_ledger_event_ids": [item.event_id for item in admitted_events],
            "candidate_artifact_refs": [item.ref.model_dump(mode="json") for item in admitted_envelopes],
            "authority_path_disposition": "loop_only",
            "deviation_terminal": deviation.terminal_state.kind.value,
            "deviation_operation": (
                deviation.phase2_playbook_trace.deviation_operation.value
                if deviation.phase2_playbook_trace.deviation_operation else None
            ),
        }],
        "strangle_receipt": strangle,
    }


def recompute_playbook_admission_strangle(repo_root: Path) -> dict[str, Any]:
    """Enumerate production constructor/raw-execution callers without git exclusions."""
    source_root = repo_root / "src"
    paths = set(source_root.rglob("*.py"))
    independent = {
        Path(directory) / filename
        for directory, _, filenames in os.walk(source_root)
        for filename in filenames if filename.endswith(".py")
    }
    if not paths or paths != independent:
        raise AssertionError("c1_strangle_source_denominator_unresolved")
    allowed = {
        "execute_candidate": (
            "src/polisyos/runtime/quality/workspace/scientist_node_adapters.py",
            "validate_adapter_semantic_preservation",
        ),
        "PlaybookStep": (
            "src/polisyos/runtime/quality/workspace/workflow_playbook_projection.py",
            "admit_playbook_step",
        ),
    }
    callers = []
    for path in sorted(paths):
        relative = path.relative_to(repo_root).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=relative)
        aliases = {
            alias.asname or alias.name: alias.name
            for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
            for alias in node.names
        }
        while True:
            previous = dict(aliases)
            for node in ast.walk(tree):
                if not isinstance(node, (ast.Assign, ast.AnnAssign)):
                    continue
                value = node.value
                target = (
                    value.attr if isinstance(value, ast.Attribute)
                    else aliases.get(value.id, value.id) if isinstance(value, ast.Name)
                    else ""
                )
                if target in allowed:
                    targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                    for target_node in targets:
                        if isinstance(target_node, ast.Name):
                            aliases[target_node.id] = target
            if previous == aliases:
                break

        class Calls(ast.NodeVisitor):
            def __init__(self, source_path: str, import_aliases: dict[str, str]) -> None:
                self.scope: list[str] = []
                self.source_path = source_path
                self.aliases = import_aliases

            def visit_FunctionDef(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
                self.scope.append(node.name)
                self.generic_visit(node)
                self.scope.pop()

            def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
                self.visit_FunctionDef(node)

            def record(self, node: ast.AST, name: str) -> None:
                scope = ".".join(self.scope)
                callers.append({
                    "path": self.source_path, "function": scope, "line": node.lineno,
                    "column": node.col_offset, "target": name,
                    "disposition": (
                        "verifier_smoke_only" if name == "execute_candidate"
                        else "verified_admission_only"
                    ) if (self.source_path, scope) == allowed[name] else "unfenced",
                })

            def visit_Attribute(self, node: ast.Attribute) -> None:
                # Fence the raw method reference itself; assigning it to a new
                # callable name must not create an uncounted sibling path.
                if node.attr == "execute_candidate" and isinstance(node.ctx, ast.Load):
                    self.record(node, node.attr)
                self.generic_visit(node)

            def visit_Call(self, node: ast.Call) -> None:
                name = (
                    node.func.attr if isinstance(node.func, ast.Attribute)
                    else self.aliases.get(node.func.id, node.func.id) if isinstance(node.func, ast.Name)
                    else ""
                )
                if name in allowed and not (
                    name == "execute_candidate" and isinstance(node.func, ast.Attribute)
                ):
                    self.record(node, name)
                if name == "getattr" and len(node.args) > 1:
                    member = node.args[1]
                    if isinstance(member, ast.Constant) and member.value in allowed:
                        self.record(node, member.value)
                self.generic_visit(node)

        Calls(relative, aliases).visit(tree)
    callers.sort(key=lambda item: (item["path"], item["line"], item["column"]))
    return {
        "receipt_id": "layer3-gy-c1-operation-admission-strangle",
        "pattern_id": "P28",
        "predecessor_ref": "WorkspaceLoop.run_intent->ScientistNodeAdapter.execute_candidate",
        "replacement_ref": "workflow_playbook_projection.admit_playbook_step",
        "disposition": "fenced_default_flipped",
        "default_before": "shape_only_step_then_direct_candidate_execution",
        "default_after": "verified_admission_then_reuse_checked_execution",
        "guard_ref": "recompute_playbook_admission_strangle",
        "source_denominator": {"rglob_py": len(paths), "os_walk_py": len(independent)},
        "remaining_callers": callers,
        "unexpected_callers": [item for item in callers if item["disposition"] == "unfenced"],
        "verified_by": [
            "test_c1_playbook_proof_binds_the_admission_the_consumer_used",
            "test_c1_playbook_proof_refuses_changed_receipt_with_markers_intact",
        ],
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
    import sys

    raise SystemExit(
        run_timed_entrypoint(
            main,
            script_path=__file__,
            argv=sys.argv[1:],
            started_perf_counter=_TIMING_STARTED_AT,
        )
    )
