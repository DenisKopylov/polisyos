#!/usr/bin/env python3
"""Validate the Layer 3 GY generation-cycle disposition ledger."""

from __future__ import annotations

import argparse
import asyncio
import copy
import importlib
import importlib.util
import json
import os
import re
import sys
import tomllib
from pathlib import Path
from types import SimpleNamespace
from typing import Any

DEFAULT_LEDGER_PATH = Path(
    "architecture/policy_design_case/layer3_gy_generation_cycle_disposition_ledger.json"
)
NOTEBOOK_PATH = Path("architecture/policy_design_case/layer3_gy_n0_investigation.md")
FAMILY_ID = "policy-design-case-layer3-gy-generation-cycle-disposition-ledger"
SCHEMA_VERSION = (
    "policyos.policy_design_case.layer3_gy.generation_cycle_disposition_ledger.v1"
)
DISPOSITIONS = {"USE_AS_IS", "REWORK_TO_FIT", "DELETE"}
TASK_STATUSES = {"pending", "landed"}
STRANGLE_STATUSES = {"pending", "strangled"}
REQUIRED_TASKS = {
    *{f"GY-N{index}" for index in range(1, 11)},
    "GY-N-V",
    "GY-S0",
    "GY-S1",
    "GY-S2",
    "GY-S3",
    "GY-O1",
    "GY-O2",
    "GY-O3",
}
REQUIRED_BRIDGES = {
    "DesignProblem",
    "InterventionAtomBinding",
    "WorldModelRecord",
    "JointSimulationHorizonController",
    "ValueOuterSet",
}
STRANGLE_RECEIPT_FIELDS = {
    "predecessor_ref",
    "replacement_ref",
    "disposition",
    "required_disposition",
    "default_before",
    "default_after",
    "guard_ref",
    "remaining_callers",
    "remaining_callers_disposition",
    "removed_loc",
    "verified_by",
    "superseded_path",
    "consuming_task",
    "strangle_condition",
    "status",
}
NOTEBOOK_SECTION_DISPOSITIONS = {
    "USE_AS_IS:": "USE_AS_IS",
    "REWORK_TO_FIT:": "REWORK_TO_FIT",
    "DELETE / COMPATIBILITY-ONLY candidates:": "DELETE",
}
NOTEBOOK_OWNER_BULLET_RE = re.compile(
    r"^- owner_id: `(?P<owner_id>[a-z0-9_]+)`; "
    r"owner_path: `(?P<owner_path>[^`]+)` - (?P<body>.+)$"
)


def declared_outputs() -> list[str]:
    """Return committed outputs owned by this validator."""

    return [DEFAULT_LEDGER_PATH.as_posix()]


def load_ledger(
    repo_root: Path,
    ledger_path: Path | str = DEFAULT_LEDGER_PATH,
) -> dict[str, Any]:
    """Read the committed disposition ledger."""

    path = repo_root / ledger_path
    return json.loads(path.read_text(encoding="utf-8"))


def validate(
    repo_root: Path,
    *,
    ledger_path: Path | str = DEFAULT_LEDGER_PATH,
) -> dict[str, Any]:
    """Validate the committed ledger against the current tree."""

    return validate_ledger(repo_root, load_ledger(repo_root, ledger_path))


def validate_ledger(repo_root: Path, ledger: dict[str, Any]) -> dict[str, Any]:
    """Validate a ledger payload against live code and dependency probes."""

    repo_root = repo_root.resolve()
    _ensure_src_path(repo_root)
    issues: list[dict[str, Any]] = []
    if ledger.get("schema_version") != SCHEMA_VERSION:
        issues.append(
            {
                "code": "schema_version_drift",
                "expected": SCHEMA_VERSION,
                "actual": ledger.get("schema_version"),
            }
        )
    if ledger.get("gy_lifecycle_marker") != SCHEMA_VERSION:
        issues.append({"code": "gy_lifecycle_marker_drift"})

    owners = _list_of_dicts(ledger.get("owners"), field="owners", issues=issues)
    owner_by_id: dict[str, dict[str, Any]] = {}
    for owner in owners:
        owner_id = str(owner.get("owner_id") or "")
        if not owner_id:
            issues.append({"code": "owner_id_missing"})
            continue
        if owner_id in owner_by_id:
            issues.append({"code": "owner_id_duplicate", "owner_id": owner_id})
        owner_by_id[owner_id] = owner
        _validate_owner(repo_root, owner, issues)
    notebook_owners = _validate_notebook_fidelity(repo_root, owner_by_id, issues)

    tasks = _dict_of_dicts(ledger.get("tasks"), field="tasks", issues=issues)
    for task_id in REQUIRED_TASKS:
        task = tasks.get(task_id)
        if not task:
            issues.append({"code": "task_status_missing", "task_id": task_id})
            continue
        status = task.get("status")
        if status not in TASK_STATUSES:
            issues.append({"code": "task_status_invalid", "task_id": task_id, "status": status})

    bridges = _dict_of_dicts(ledger.get("bridge_artifacts"), field="bridge_artifacts", issues=issues)
    for bridge_id in REQUIRED_BRIDGES:
        bridge = bridges.get(bridge_id)
        if not bridge:
            issues.append({"code": "bridge_artifact_missing", "bridge": bridge_id})
            continue
        task_id = bridge.get("consuming_task")
        if task_id not in tasks:
            issues.append(
                {"code": "bridge_artifact_task_missing", "bridge": bridge_id, "task_id": task_id}
            )

    _validate_task_mapping(ledger, owner_by_id, tasks, issues)
    strangle_summary = _validate_strangle_obligations(repo_root, owners, tasks, issues)
    method_gate = _validate_method_availability_gate(repo_root, ledger, issues)
    _validate_registration(repo_root, issues)
    summary = _summary(owners, ledger, strangle_summary, notebook_owners)
    status = "pass" if not issues else "fail"
    return {
        "status": status,
        "issues": issues,
        "summary": summary,
        "method_availability_gate": method_gate,
    }


def corrupt_field_drift_check(repo_root: Path) -> dict[str, Any]:
    """Return the intentionally failing verifier self-check report."""

    ledger = copy.deepcopy(load_ledger(repo_root))
    owners = ledger.get("owners")
    if isinstance(owners, list) and owners and isinstance(owners[0], dict):
        owners[0]["owner_path"] = "src/polisyos/fabricated/no_owner.py:1"
    report = validate_ledger(repo_root, ledger)
    issues = list(report["issues"])
    if issues:
        return {
            "status": "fail",
            "issues": [
                {
                    "code": "corrupt_field_drift_detected",
                    "detected_issue_codes": sorted(
                        {
                            str(issue.get("code"))
                            for issue in issues
                            if isinstance(issue, dict) and issue.get("code")
                        }
                    ),
                },
                *issues,
            ],
            "summary": report["summary"],
            "method_availability_gate": report["method_availability_gate"],
        }
    return {
        "status": "pass",
        "issues": [{"code": "corrupt_field_drift_not_detected"}],
        "summary": report["summary"],
        "method_availability_gate": report["method_availability_gate"],
    }


def _validate_owner(repo_root: Path, owner: dict[str, Any], issues: list[dict[str, Any]]) -> None:
    owner_id = str(owner.get("owner_id") or "")
    disposition = owner.get("disposition")
    if disposition not in DISPOSITIONS:
        issues.append(
            {
                "code": "owner_disposition_invalid",
                "owner_id": owner_id,
                "disposition": disposition,
            }
        )
    if not str(owner.get("focus") or "").strip():
        issues.append({"code": "owner_focus_missing", "owner_id": owner_id})
    if not str(owner.get("rationale") or "").strip():
        issues.append({"code": "owner_rationale_missing", "owner_id": owner_id})
    consuming_task = owner.get("consuming_task")
    if consuming_task and consuming_task not in REQUIRED_TASKS:
        issues.append(
            {"code": "owner_consuming_task_unknown", "owner_id": owner_id, "task_id": consuming_task}
        )
    if not _anchor_resolves(repo_root, str(owner.get("owner_path") or "")):
        issues.append(
            {
                "code": "owner_anchor_unresolved",
                "owner_id": owner_id,
                "owner_path": owner.get("owner_path"),
            }
        )
    if disposition in {"REWORK_TO_FIT", "DELETE"} and not isinstance(
        owner.get("strangle_receipt"),
        dict,
    ):
        issues.append({"code": "strangle_receipt_missing", "owner_id": owner_id})


def _validate_notebook_fidelity(
    repo_root: Path,
    owner_by_id: dict[str, dict[str, Any]],
    issues: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    notebook_owners = _parse_notebook_candidate_owners(repo_root, issues)
    for owner_id, expected in notebook_owners.items():
        owner = owner_by_id.get(owner_id)
        if owner is None:
            issues.append(
                {
                    "code": "notebook_owner_missing_from_ledger",
                    "owner_id": owner_id,
                    "notebook_ref": expected["notebook_ref"],
                }
            )
            continue
        if owner.get("disposition") != expected["disposition"]:
            issues.append(
                {
                    "code": "disposition_mismatch_with_notebook",
                    "owner_id": owner_id,
                    "expected": expected["disposition"],
                    "actual": owner.get("disposition"),
                    "notebook_ref": expected["notebook_ref"],
                }
            )
        if owner.get("owner_path") != expected["owner_path"]:
            issues.append(
                {
                    "code": "owner_path_mismatch_with_notebook",
                    "owner_id": owner_id,
                    "expected": expected["owner_path"],
                    "actual": owner.get("owner_path"),
                    "notebook_ref": expected["notebook_ref"],
                }
            )
        _validate_source_notebook_refs(owner, expected, issues)
    for owner_id in sorted(set(owner_by_id) - set(notebook_owners)):
        issues.append({"code": "ledger_owner_not_in_notebook", "owner_id": owner_id})
    return notebook_owners


def _parse_notebook_candidate_owners(
    repo_root: Path,
    issues: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    notebook_path = repo_root / NOTEBOOK_PATH
    if not notebook_path.is_file():
        issues.append({"code": "notebook_source_missing", "path": NOTEBOOK_PATH.as_posix()})
        return {}
    lines = notebook_path.read_text(encoding="utf-8").splitlines()
    try:
        start_index = lines.index("### C. Reuse / Rework / Delete Candidates")
        end_index = lines.index("## GY-N1..N7 -> Owners Mapping")
    except ValueError as exc:
        issues.append({"code": "notebook_candidate_section_missing", "detail": str(exc)})
        return {}

    current_disposition: str | None = None
    owners: dict[str, dict[str, Any]] = {}
    for line_index in range(start_index + 1, end_index):
        line_number = line_index + 1
        stripped = lines[line_index].strip()
        if not stripped:
            continue
        if stripped in NOTEBOOK_SECTION_DISPOSITIONS:
            current_disposition = NOTEBOOK_SECTION_DISPOSITIONS[stripped]
            continue
        if not stripped.startswith("- "):
            continue
        if current_disposition is None:
            issues.append({"code": "notebook_owner_bullet_outside_disposition", "line": line_number})
            continue
        match = NOTEBOOK_OWNER_BULLET_RE.match(stripped)
        if match is None:
            issues.append(
                {
                    "code": "notebook_owner_bullet_unparseable",
                    "line": line_number,
                    "text": stripped,
                }
            )
            continue
        owner_id = match.group("owner_id")
        owner_path = match.group("owner_path")
        notebook_ref = f"{NOTEBOOK_PATH.as_posix()}:{line_number}"
        if owner_id in owners:
            issues.append({"code": "notebook_owner_duplicate", "owner_id": owner_id})
        if not _anchor_resolves(repo_root, owner_path):
            issues.append(
                {
                    "code": "notebook_owner_anchor_unresolved",
                    "owner_id": owner_id,
                    "owner_path": owner_path,
                    "notebook_ref": notebook_ref,
                }
            )
        owners[owner_id] = {
            "owner_id": owner_id,
            "owner_path": owner_path,
            "disposition": current_disposition,
            "line": line_number,
            "notebook_ref": notebook_ref,
            "text": stripped,
        }
    return owners


def _validate_source_notebook_refs(
    owner: dict[str, Any],
    expected: dict[str, Any],
    issues: list[dict[str, Any]],
) -> None:
    owner_id = str(owner.get("owner_id") or "")
    refs = owner.get("source_notebook_refs")
    if not isinstance(refs, list) or not refs:
        issues.append(
            {
                "code": "source_notebook_ref_unresolved",
                "owner_id": owner_id,
                "expected": expected["notebook_ref"],
                "actual": refs,
            }
        )
        return
    expected_ref = str(expected["notebook_ref"])
    for ref in refs:
        if ref != expected_ref:
            issues.append(
                {
                    "code": "source_notebook_ref_unresolved",
                    "owner_id": owner_id,
                    "expected": expected_ref,
                    "actual": ref,
                }
            )


def _anchor_resolves(repo_root: Path, anchor: str) -> bool:
    if ":" not in anchor:
        return False
    relative, raw_line = anchor.rsplit(":", maxsplit=1)
    if not raw_line.isdigit():
        return False
    line_number = int(raw_line)
    if line_number < 1:
        return False
    path = repo_root / relative
    if not path.is_file():
        return False
    try:
        return line_number <= sum(1 for _ in path.open(encoding="utf-8"))
    except UnicodeDecodeError:
        return False


def _validate_task_mapping(
    ledger: dict[str, Any],
    owner_by_id: dict[str, dict[str, Any]],
    tasks: dict[str, dict[str, Any]],
    issues: list[dict[str, Any]],
) -> None:
    mapping = _dict_of_dicts(ledger.get("task_owner_mapping"), field="task_owner_mapping", issues=issues)
    for task_id in REQUIRED_TASKS:
        if task_id not in mapping:
            issues.append({"code": "task_mapping_missing", "task_id": task_id})
    for task_id, row in mapping.items():
        if task_id not in tasks:
            issues.append({"code": "task_mapping_task_unknown", "task_id": task_id})
        owner_ids = row.get("owner_ids")
        if not isinstance(owner_ids, list) or not owner_ids:
            issues.append({"code": "task_mapping_owner_ids_missing", "task_id": task_id})
            continue
        for owner_id in owner_ids:
            if owner_id not in owner_by_id:
                issues.append(
                    {
                        "code": "task_mapping_owner_missing_from_ledger",
                        "task_id": task_id,
                        "owner_id": owner_id,
                    }
                )


def _validate_strangle_obligations(
    repo_root: Path,
    owners: list[dict[str, Any]],
    tasks: dict[str, dict[str, Any]],
    issues: list[dict[str, Any]],
) -> dict[str, int]:
    summary = {"pending": 0, "landed_checked": 0, "strangled": 0}
    for owner in owners:
        disposition = owner.get("disposition")
        if disposition not in {"REWORK_TO_FIT", "DELETE"}:
            continue
        owner_id = str(owner.get("owner_id") or "")
        receipt = owner.get("strangle_receipt")
        if not isinstance(receipt, dict):
            continue
        missing = sorted(field for field in STRANGLE_RECEIPT_FIELDS if field not in receipt)
        if missing:
            issues.append(
                {"code": "strangle_receipt_field_missing", "owner_id": owner_id, "fields": missing}
            )
        status = receipt.get("status")
        if status not in STRANGLE_STATUSES:
            issues.append({"code": "strangle_receipt_status_invalid", "owner_id": owner_id})
        consuming_task = str(receipt.get("consuming_task") or owner.get("consuming_task") or "")
        task_status = (tasks.get(consuming_task) or {}).get("status")
        if task_status == "landed":
            summary["landed_checked"] += 1
            condition_holds = _evaluate_strangle_condition(
                repo_root,
                receipt.get("strangle_condition"),
            )
            if status != "strangled" or not condition_holds:
                issues.append(
                    {
                        "code": "landed_owner_not_strangled",
                        "owner_id": owner_id,
                        "consuming_task": consuming_task,
                        "status": status,
                        "condition_holds": condition_holds,
                    }
                )
            else:
                summary["strangled"] += 1
        elif status == "pending":
            summary["pending"] += 1
    return summary


def _evaluate_strangle_condition(repo_root: Path, condition: object) -> bool:
    if not isinstance(condition, dict):
        return False
    kind = condition.get("kind")
    if kind == "path_absent":
        path = repo_root / str(condition.get("path") or "")
        return not path.exists()
    if kind == "text_absent":
        path = repo_root / str(condition.get("path") or "")
        pattern = str(condition.get("pattern") or "")
        if not path.exists():
            return True
        if not path.is_file() or not pattern:
            return False
        text = path.read_text(encoding="utf-8")
        return not _contains_pattern(text, pattern, regex=bool(condition.get("regex")))
    if kind == "text_absent_under":
        root = repo_root / str(condition.get("root") or "")
        pattern = str(condition.get("pattern") or "")
        if not root.exists() or not pattern:
            return True
        suffixes = tuple(condition.get("suffixes") or [".py"])
        for path in root.rglob("*"):
            if path.is_file() and path.suffix in suffixes:
                try:
                    text = path.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    continue
                if _contains_pattern(text, pattern, regex=bool(condition.get("regex"))):
                    return False
        return True
    if kind == "plain_policy_nl_not_verified_default":
        return _plain_policy_nl_not_verified_default()
    if kind == "workspace_run_intent_rejects_raw_dict":
        return _workspace_run_intent_rejects_raw_dict()
    if kind == "design_problem_bridge_projects_existing_surfaces":
        return _design_problem_bridge_projects_existing_surfaces()
    if kind == "design_problem_front_door_gateway_tool_calling":
        return _design_problem_front_door_gateway_tool_calling()
    if kind == "intervention_atom_binding_round_trip_preserves_halves":
        return _intervention_atom_binding_round_trip_preserves_halves()
    if kind == "intervention_atom_binding_measurement_expectations_metadata_only":
        return _intervention_atom_binding_measurement_expectations_metadata_only()
    if kind == "world_model_record_bridge_landed":
        return _world_model_record_bridge_landed(repo_root)
    if kind == "production_data_substrate_registry_landed":
        return _production_data_substrate_registry_landed(repo_root)
    if kind == "intervention_substrate_lift_landed":
        return _intervention_substrate_lift_landed(repo_root)
    if kind == "value_outer_set_contract_importable":
        return _value_outer_set_contract_importable()
    if kind == "value_outer_set_strangle_receipt_landed":
        return _value_outer_set_strangle_receipt_landed(repo_root)
    return False


def _plain_policy_nl_not_verified_default() -> bool:
    from polisyos.scientist.orchestration.engine.state import ExperimentState
    from polisyos.scientist.orchestration.workflows.selection import resolve_workflow_id

    state = ExperimentState(
        run_id="R_gy_n1_plain_policy_strangle",
        params={"policy_question": "Can Ukraine offer MSME credit guarantees?"},
    )
    return resolve_workflow_id(state) == "scientist_policy_design"


def _workspace_run_intent_rejects_raw_dict() -> bool:
    from polisyos.runtime.quality.workspace.loop import WorkspaceLoop

    try:
        WorkspaceLoop().run_intent({"policy_question": "raw dict must be rejected"})  # type: ignore[arg-type]
    except TypeError:
        return True
    return False


def _design_problem_bridge_projects_existing_surfaces() -> bool:
    problem = _sample_design_problem()
    scientist_frame = problem.to_scientist_problem_frame()
    ir_frame = problem.to_ir_problem_frame()
    request_frame = problem.to_policy_request_frame()
    model_spec = problem.to_model_spec(data_snapshot_ref="sha256:" + "4" * 64)
    return (
        scientist_frame.problem_statement == problem.problem_statement
        and ir_frame.problem_id == problem.design_problem_id
        and request_frame.policy_question == problem.problem_statement
        and model_spec.time_semantics == problem.jurisdiction_time.time_semantics
    )


def _design_problem_front_door_gateway_tool_calling() -> bool:
    from polisyos.runtime.http.services.control.nl_pipeline import (
        build_design_problem_from_nl_request,
    )
    from polisyos.scientist.orchestration.llm.gateway_client import (
        GatewayLLMResponse,
        GatewayToolCall,
    )

    class _Gateway:
        def __init__(self) -> None:
            self.generate_kwargs: dict[str, Any] | None = None

        async def list_model_ids(self, *, timeout: float | None = None) -> list[str]:
            return ["Qwen/Qwen3-235B-A22B-Instruct-2507-FP8", "MiniMaxAI/MiniMax-M2.7"]

        async def generate(self, **kwargs: Any) -> GatewayLLMResponse:
            self.generate_kwargs = kwargs
            return GatewayLLMResponse(
                content="",
                model="Qwen/Qwen3-235B-A22B-Instruct-2507-FP8",
                provider="gateway",
                tool_calls=[
                    GatewayToolCall(
                        id="call-design-problem",
                        name="emit_design_problem",
                        arguments=_sample_design_problem().model_dump(mode="json"),
                    )
                ],
            )

    class _SpanSupportClient:
        async def generate(self, **kwargs: Any) -> SimpleNamespace:
            return SimpleNamespace(
                content="",
                model="deterministic-span-support",
                provider="validator",
                request_id="validator-span-support",
                tool_calls=[
                    SimpleNamespace(
                        id="call-span-support",
                        name="layer3_gy_record_span_support_judgment",
                        arguments={
                            "decision": "entails",
                            "confidence": 0.93,
                            "rationale": "deterministic validator judgment",
                        },
                    )
                ],
                raw={"validator": "layer3_gy_generation_cycle_disposition_ledger"},
            )

    async def _run() -> bool:
        gateway = _Gateway()
        problem = await build_design_problem_from_nl_request(
            nl_request=(
                "Design a wartime MSME credit guarantee for Ukraine within the stated "
                "UAH 10b budget cap."
            ),
            context={"jurisdiction": "UA", "requested_authority_level": "research"},
            model_name="Qwen/Qwen3-235B-A22B-Instruct-2507-FP8",
            gateway_client=gateway,
            span_support_client=_SpanSupportClient(),
        )
        kwargs = gateway.generate_kwargs or {}
        tool_choice = kwargs.get("tool_choice")
        return (
            problem.design_problem_id == "design_problem_ua_msme_credit"
            and isinstance(kwargs.get("tools"), list)
            and isinstance(tool_choice, dict)
            and tool_choice.get("function", {}).get("name") == "emit_design_problem"
        )

    return asyncio.run(_run())


def _sample_design_problem() -> Any:
    from polisyos.runtime.quality.design_problem import DesignProblem

    return DesignProblem.model_validate(
        {
            "design_problem_id": "design_problem_ua_msme_credit",
            "problem_statement": "Wartime MSMEs face liquidity constraints.",
            "domain": "social",
            "nl_provenance": {
                "raw_request": (
                    "Design a wartime MSME credit guarantee for Ukraine within the stated "
                    "UAH 10b budget cap."
                ),
                "source_surface": "validator",
                "source_context": {"run_id": "run-gy-n1-validator"},
            },
            "authority_profile": {
                "requester_authority": "research",
                "requested_authority_level": "research",
                "mandate": "Cabinet research mandate.",
            },
            "jurisdiction_time": {
                "region": "UA",
                "valid_time": "2026-05-15",
                "as_of": "2026-05-12",
                "policy_time": "2026-05-15",
                "data_time": "2024-2026",
                "time_semantics": {"frequency": "Q", "start_date": "2024-01-01", "step_count": 8},
            },
            "objectives": [
                {
                    "objective_id": "increase_msme_survival",
                    "description": "Increase MSME survival.",
                    "metric_id": "msme_survival_rate",
                    "direction": "maximize",
                }
            ],
            "constraints": [
                {
                    "constraint_id": "budget_cap",
                    "description": "Stay within the stated UAH 10b budget cap.",
                    "hard": True,
                    "admissibility_basis": "request_text",
                    "source_text": "UAH 10b budget cap",
                }
            ],
            "stakeholders": [
                {
                    "stakeholder_id": "wartime_msmes",
                    "name": "wartime MSMEs",
                    "role": "beneficiary",
                }
            ],
            "outcome_of_interest": {
                "target_variable": "firm_survival",
                "metric_id": "msme_survival_rate",
                "estimand": "P(firm_survival | do(credit_access))",
                "direction": "maximize",
            },
            "candidate_lever_space": {
                "allowed_operator_kinds": ["credit_guarantee"],
                "candidate_levers": [
                    {
                        "lever_id": "credit_access_guarantee",
                        "operator_kind": "credit_guarantee",
                        "instrument": "credit guarantee",
                        "target_slot": "credit_access",
                    }
                ],
            },
            "evidence_acquisition_needs": {
                "needs": [
                    {
                        "need_id": "credit_panel",
                        "question": "Measure credit access and firm survival.",
                        "required_for": "outcome_of_interest",
                        "status": "required",
                        "source_hint": "measurement_root",
                    }
                ]
            },
            "model_spec_ref": "sha256:" + "2" * 64,
        }
    )


def _sample_intervention_atom_binding_inputs() -> dict[str, Any]:
    from decimal import Decimal

    from polisyos.ir.analytics.interventions import (
        IdentificationBackend,
        InterventionContext,
        InterventionReduction,
        NodeIntervention,
        ProofKernelInterventionType,
        QueryTarget,
        QueryTargetKind,
        VariableAssignment,
        identification_plan_for_intervention,
    )
    from polisyos.ir.governance.policy_spec import InterventionSpec, PolicySpec
    from polisyos.ir.governance.problem_frame import ProblemDomain, ProblemFrame
    from polisyos.ir.governance.schedule import ScheduleSpec
    from polisyos.ir.governance.selector_expr import SelectorPredicate
    from polisyos.ir.kernel import (
        DEFAULT_MECHANISM_REGISTRY,
        DEFAULT_MERGE_RULE_REGISTRY,
        DEFAULT_METRIC_REGISTRY,
        DEFAULT_SELECTOR_FIELD_REGISTRY,
        DEFAULT_SLOT_REGISTRY,
        DEFAULT_UNITS_REGISTRY,
        ConstraintRegistry,
    )
    from polisyos.ir.linker import link_trinity
    from polisyos.ir.model_layer.model_spec import ModelSpec
    from polisyos.ir.model_layer.types import SelectorOperator
    from polisyos.ir.observation.contracts import IdentificationMode, StrategicResponseChannel
    from polisyos.ir.registry.refs import InteractionComplexRef, InterferenceCertificateRef
    from polisyos.ir.registry.registry_fragments import RegistryBundle
    from polisyos.ir.trinity import TrinityBundle
    from polisyos.pdc import gy_content_hash
    from polisyos.runtime.quality.intervention_atom_binding import (
        INTERVENTION_ATOM_BINDING_SCHEMA_VERSION,
        CausalAssignmentProjection,
        CausalDoExpression,
        DirectEffectBundle,
        IdentificationPlanRef,
        IntendedDownstreamEstimand,
        InterventionAtomBinding,
        OperatorKind,
        TargetSelectorBinding,
        _content_payload_from_fields,
        build_intervention_atom_binding,
        intervention_atom_target_selector_ref,
    )

    intervention = InterventionSpec(
        intervention_id="credit_access_subsidy",
        kind="tax_subsidy",
        target=SelectorPredicate(field="id", operator=SelectorOperator.EQUALS, value="all"),
        schedule=ScheduleSpec(start_step=2, end_step=6, duration_steps=5),
        params={"rate": Decimal("0.20"), "eligibility_floor": Decimal("75000.00")},
        priority=7,
        enabled=False,
        lex_provision_ref="lex://ua/msme-credit-guarantee/section-4",
        target_population_type="wartime_msme",
        target_sector_ids=["manufacturing", "logistics"],
        target_region_ids=["UA-30", "UA-46"],
        measurement_expectations={
            "legacy_note": "Track firm survival after credit access changes.",
            "panel_window": "2026Q1-2026Q4",
        },
        identification_mode=IdentificationMode.INTERFERENCE_AWARE,
        strategic_response_expected=True,
        transmission_channels=[
            StrategicResponseChannel.BUDGET_CHANNEL,
            StrategicResponseChannel.COMPLIANCE_CHANNEL,
        ],
        notes=["non_default_round_trip_probe"],
    )
    bundle = TrinityBundle(
        problem_frame=ProblemFrame(problem_id="problem_ua_msme_credit", domain=ProblemDomain.FISCAL),
        policy_spec=PolicySpec(
            policy_id="policy_ua_msme_credit",
            problem_frame_ref="sha256:" + "a" * 64,
            interventions=[intervention],
        ),
        model_spec=ModelSpec(
            model_id="model_ua_msme",
            data_snapshot_ref="sha256:" + "b" * 64,
        ),
    )
    linked_bundle, report = link_trinity(
        bundle,
        RegistryBundle(
            mechanisms=DEFAULT_MECHANISM_REGISTRY,
            slots=DEFAULT_SLOT_REGISTRY,
            merge_rules=DEFAULT_MERGE_RULE_REGISTRY,
            selector_fields=DEFAULT_SELECTOR_FIELD_REGISTRY,
            units=DEFAULT_UNITS_REGISTRY,
            metrics=DEFAULT_METRIC_REGISTRY,
            constraints=ConstraintRegistry(constraints={}),
        ),
    )
    if not report.ok:
        raise AssertionError(report.issues)
    causal = NodeIntervention(
        assignments=(
            VariableAssignment(
                variable="agents.income",
                value=0,
                value_expr="income + subsidy(rate)",
            ),
        )
    )
    query_target = QueryTarget(
        target_kind=QueryTargetKind.CONTRAST,
        outcome_variables=("firm_survival",),
        conditioning=("baseline_credit_access",),
        functional="average_treatment_effect",
    )
    context = InterventionContext(
        source_domain="observed_ua_msme_panel",
        target_domain="wartime_msme",
        selection_diagram_ref=intervention_atom_target_selector_ref(intervention),
        interaction_complex_ref=InteractionComplexRef(artifact_id="sha256:" + "4" * 64),
        interference_certificate_ref=InterferenceCertificateRef(
            artifact_id="sha256:" + "5" * 64
        ),
        available_data_refs=(
            "data_snapshot:ua_msme_credit_panel",
            "data_snapshot:ua_wartime_firm_survival",
        ),
        assumptions=("target_selector_content_bound", "positivity_by_region_sector"),
    )
    base_identification_plan = identification_plan_for_intervention(causal)
    identification_conditions = tuple(
        condition.model_copy(update={"required": False})
        if index == 0
        else condition
        for index, condition in enumerate(base_identification_plan.conditions)
    )
    identification_plan = base_identification_plan.model_copy(
        update={
            "conditions": identification_conditions,
            "reductions": (
                InterventionReduction(
                    from_type=ProofKernelInterventionType.NODE,
                    to_type=ProofKernelInterventionType.NODE,
                    rule_name="round_trip_node_identity",
                    backend=IdentificationBackend.ID,
                    description="Non-default round-trip reduction witness.",
                ),
            ),
            "notes": ("non_default_identification_plan_note",),
        }
    )
    expected_estimand = IntendedDownstreamEstimand(
        target_kind=query_target.target_kind,
        outcome_variables=query_target.outcome_variables,
        conditioning_set=query_target.conditioning,
        source_population="observed_ua_msme_panel",
        target_population="wartime_msme",
        functional=query_target.functional,
        metric_id="msme_survival_rate",
        unit_id="ratio",
    )
    plan_payload = identification_plan.model_dump(mode="json")
    expected_plan_ref = IdentificationPlanRef(
        plan_ref=gy_content_hash(plan_payload),
        intervention_type=identification_plan.intervention_type,
        backend=str(identification_plan.backend.value),
        status=str(identification_plan.native_status.value),
        theorem_family=identification_plan.theorem_family,
        conditions=tuple(
            condition.model_dump(mode="json") for condition in identification_plan.conditions
        ),
        reductions=tuple(
            reduction.model_dump(mode="json") for reduction in identification_plan.reductions
        ),
        notes=tuple(identification_plan.notes),
    )
    proof_type = ProofKernelInterventionType(causal.intervention_type)
    linked_intervention = linked_bundle.bindings.interventions[0]
    selector_ref = intervention_atom_target_selector_ref(intervention)
    write_variables = tuple(sorted(assignment.variable for assignment in causal.assignments))
    expected_fields: dict[str, Any] = {
        "schema_version": INTERVENTION_ATOM_BINDING_SCHEMA_VERSION,
        "problem_frame_ref": "sha256:" + "a" * 64,
        "policy_spec_ref": "sha256:" + "c" * 64,
        "intervention_id": intervention.intervention_id,
        "operator_kind": OperatorKind(
            trinity_kind=intervention.kind,
            proof_kernel_type=proof_type,
        ),
        "target_selector": TargetSelectorBinding(
            trinity_target=intervention.target.model_dump(mode="json"),
            target_population_type=intervention.target_population_type,
            target_sector_ids=tuple(intervention.target_sector_ids),
            target_region_ids=tuple(intervention.target_region_ids),
            selector_content_ref=selector_ref,
        ),
        "target_world_slots": tuple(linked_intervention.writes_slots),
        "read_slots": tuple(linked_intervention.reads_slots),
        "direct_effect_bundle": DirectEffectBundle(
            params=intervention.params,
            schedule=intervention.schedule.model_dump(mode="json"),
            priority=intervention.priority,
            mechanism_id=linked_intervention.mechanism_id,
            mechanism_config_overrides={"merge_policy": "sum_income_delta"},
            transform_refs=("transform:subsidy_rate_to_income_delta",),
            coerce_refs=("coerce:decimal_rate",),
            lex_provision_ref=intervention.lex_provision_ref,
            enabled=intervention.enabled,
            identification_mode=str(intervention.identification_mode.value),
            strategic_response_expected=intervention.strategic_response_expected,
            transmission_channels=tuple(
                item.model_dump(mode="json")
                if hasattr(item, "model_dump")
                else item
                for item in intervention.transmission_channels
            ),
            notes=tuple(intervention.notes),
        ),
        "causal_do_expr": CausalDoExpression(
            intervention_type=proof_type,
            assignments=tuple(
                CausalAssignmentProjection(
                    variable=assignment.variable,
                    value=assignment.value,
                    value_expr=assignment.value_expr,
                )
                for assignment in causal.assignments
            ),
            expression_payload=causal.model_dump(mode="json"),
            write_variables=write_variables,
            selection_context_ref=selector_ref,
            context=context.model_dump(mode="json"),
        ),
        "intended_downstream_estimand": expected_estimand,
        "causal_path_or_identification_plan_ref": expected_plan_ref,
        "world_model_record_ref": "world_model_record_ua_msme_v1",
        "measurement_expectations": dict(intervention.measurement_expectations),
        "measurement_expectations_authority": "supporting_metadata",
        "producer_ref": "validator:intervention_atom_binding",
        "provenance_refs": ("trinity_bundle:policy_ua_msme_credit", "proof_kernel:node_do_income"),
        "status": "grounded",
    }
    content_hash = gy_content_hash(_content_payload_from_fields(expected_fields))
    expected_atom = InterventionAtomBinding(
        atom_id=f"atom_{content_hash.removeprefix('sha256:')[:16]}",
        content_hash=content_hash,
        **expected_fields,
    )
    atom = build_intervention_atom_binding(
        problem_frame_ref="sha256:" + "a" * 64,
        policy_spec_ref="sha256:" + "c" * 64,
        intervention=intervention,
        linked_intervention=linked_intervention,
        causal_intervention=causal,
        query_target=query_target,
        identification_plan=identification_plan,
        causal_context=context,
        world_model_record_ref="world_model_record_ua_msme_v1",
        producer_ref="validator:intervention_atom_binding",
        provenance_refs=("trinity_bundle:policy_ua_msme_credit", "proof_kernel:node_do_income"),
        operator_proof_type_map={"tax_subsidy": "node"},
        estimand_metric_id="msme_survival_rate",
        estimand_unit_id="ratio",
        source_population="observed_ua_msme_panel",
        target_population="wartime_msme",
        mechanism_config_overrides={"merge_policy": "sum_income_delta"},
        transform_refs=("transform:subsidy_rate_to_income_delta",),
        coerce_refs=("coerce:decimal_rate",),
        status="grounded",
    )
    return {
        "intervention": intervention,
        "causal": causal,
        "query_target": query_target,
        "causal_context": context,
        "identification_plan": identification_plan,
        "expected_estimand": expected_estimand,
        "expected_plan_ref": expected_plan_ref,
        "expected_atom_dump": expected_atom.model_dump(mode="json"),
        "atom": atom,
    }


def _sample_intervention_atom_binding() -> Any:
    return _sample_intervention_atom_binding_inputs()["atom"]


def _intervention_atom_binding_sample_default_justifications() -> dict[str, str]:
    return {
        "atom.schema_version": (
            "artifact schema sentinel; constrained to "
            "INTERVENTION_ATOM_BINDING_SCHEMA_VERSION"
        ),
        "atom.measurement_expectations_authority": (
            "measurement expectations are metadata-only by contract; constrained to "
            "supporting_metadata"
        ),
        "intervention.target.kind": (
            "selector discriminator; constrained by SelectorPredicate"
        ),
        "causal.intervention_type": (
            "proof-kernel discriminator; constrained by NodeIntervention"
        ),
        "causal_context.interaction_complex_ref.kind": (
            "artifact reference discriminator; constrained by InteractionComplexRef"
        ),
        "causal_context.interaction_complex_ref.media_type": (
            "artifact reference media type; constrained by InteractionComplexRef"
        ),
        "causal_context.interference_certificate_ref.kind": (
            "artifact reference discriminator; constrained by InterferenceCertificateRef"
        ),
        "causal_context.interference_certificate_ref.media_type": (
            "artifact reference media type; constrained by InterferenceCertificateRef"
        ),
    }


def _contains_pydantic_model(value: Any) -> bool:
    from collections.abc import Mapping, Sequence

    from pydantic import BaseModel

    if isinstance(value, BaseModel):
        return True
    if isinstance(value, Mapping):
        return any(_contains_pydantic_model(item) for item in value.values())
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return any(_contains_pydantic_model(item) for item in value)
    return False


def _intervention_atom_binding_sample_roots(sample: dict[str, Any]) -> dict[str, Any]:
    return {
        str(root_name): root
        for root_name, root in sorted(sample.items())
        if _contains_pydantic_model(root)
    }


def _field_default_value(field: Any) -> tuple[bool, Any]:
    from pydantic_core import PydanticUndefined

    if field.default is not PydanticUndefined:
        return True, field.default
    if field.default_factory is not None:
        return True, field.default_factory()
    return False, None


def _sample_default_constraint_holds(field_path: str, value: Any) -> bool:
    from polisyos.runtime.quality.intervention_atom_binding import (
        INTERVENTION_ATOM_BINDING_SCHEMA_VERSION,
    )

    constrained_values = {
        "atom.schema_version": INTERVENTION_ATOM_BINDING_SCHEMA_VERSION,
        "atom.measurement_expectations_authority": "supporting_metadata",
        "intervention.target.kind": "predicate",
        "causal.intervention_type": "node",
        "causal_context.interaction_complex_ref.kind": "ir.interaction_complex",
        "causal_context.interaction_complex_ref.media_type": "application/json",
        "causal_context.interference_certificate_ref.kind": "ir.interference_certificate",
        "causal_context.interference_certificate_ref.media_type": "application/json",
    }
    if field_path not in constrained_values:
        return False
    return value == constrained_values[field_path]


def _intervention_atom_binding_sample_non_default_report(
    sample: dict[str, Any],
) -> dict[str, Any]:
    from collections.abc import Mapping, Sequence

    from pydantic import BaseModel

    justifications = _intervention_atom_binding_sample_default_justifications()
    issues: list[dict[str, Any]] = []
    justified_default_fields: set[str] = set()

    def walk(value: Any, field_path: str) -> None:
        if isinstance(value, BaseModel):
            for field_name, field in value.__class__.model_fields.items():
                child = getattr(value, field_name)
                child_path = f"{field_path}.{field_name}"
                has_default, default = _field_default_value(field)
                if has_default and child == default:
                    if child_path not in justifications:
                        issues.append(
                            {
                                "code": (
                                    "intervention_atom_binding_sample_default_unjustified"
                                ),
                                "field_path": child_path,
                            }
                        )
                    elif not _sample_default_constraint_holds(child_path, child):
                        issues.append(
                            {
                                "code": (
                                    "intervention_atom_binding_sample_default_constraint_unmet"
                                ),
                                "field_path": child_path,
                            }
                        )
                    else:
                        justified_default_fields.add(child_path)
                walk(child, child_path)
            return
        if isinstance(value, Mapping):
            for key, child in value.items():
                walk(child, f"{field_path}.{key}")
            return
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
            for index, child in enumerate(value):
                walk(child, f"{field_path}[{index}]")

    for root_name, root in _intervention_atom_binding_sample_roots(sample).items():
        walk(root, root_name)

    for stale_path in sorted(set(justifications) - justified_default_fields):
        issues.append(
            {
                "code": "intervention_atom_binding_sample_default_justification_unused",
                "field_path": stale_path,
            }
        )

    return {
        "status": "pass" if not issues else "fail",
        "issues": issues,
        "justified_default_fields": sorted(justified_default_fields),
        "required_justified_default_fields": sorted(justifications),
    }


def _intervention_atom_binding_round_trip_report() -> dict[str, Any]:
    from polisyos.runtime.quality.intervention_atom_binding import (
        InterventionAtomBinding,
        consume_intervention_atom_for_cycle,
    )

    sample = _sample_intervention_atom_binding_inputs()
    atom = sample["atom"]
    expected_atom_dump = sample["expected_atom_dump"]
    actual_atom_dump = atom.model_dump(mode="json")
    atom_field_ids = set(InterventionAtomBinding.model_fields)
    compared_field_ids = set(expected_atom_dump)
    sample_non_default_report = _intervention_atom_binding_sample_non_default_report(sample)
    issues: list[dict[str, Any]] = []
    issues.extend(sample_non_default_report["issues"])
    if compared_field_ids != atom_field_ids:
        issues.append(
            {
                "code": "intervention_atom_binding_round_trip_field_coverage_incomplete",
                "missing_fields": sorted(atom_field_ids - compared_field_ids),
                "extra_fields": sorted(compared_field_ids - atom_field_ids),
            }
        )
    for field_id in sorted(atom_field_ids & compared_field_ids):
        if actual_atom_dump.get(field_id) != expected_atom_dump.get(field_id):
            issues.append(
                {
                    "code": "intervention_atom_binding_round_trip_field_mismatch",
                    "field": field_id,
                }
            )
    trinity = atom.to_trinity_intervention_spec()
    causal = atom.to_node_intervention()
    query_target = atom.to_query_target()
    consumer_input = consume_intervention_atom_for_cycle(atom)
    projection_checks = {
        "trinity_intervention": (
            trinity.model_dump(mode="json"),
            sample["intervention"].model_dump(mode="json"),
        ),
        "causal_intervention": (
            causal.model_dump(mode="json"),
            sample["causal"].model_dump(mode="json"),
        ),
        "query_target": (
            query_target.model_dump(mode="json"),
            sample["query_target"].model_dump(mode="json"),
        ),
        "consumer_causal_do_expr": (
            consumer_input.causal_do_expr.model_dump(mode="json"),
            atom.causal_do_expr.model_dump(mode="json"),
        ),
        "consumer_target_world_slots": (
            list(consumer_input.target_world_slots),
            list(atom.target_world_slots),
        ),
        "consumer_intended_downstream_estimand": (
            consumer_input.intended_downstream_estimand.model_dump(mode="json"),
            atom.intended_downstream_estimand.model_dump(mode="json"),
        ),
    }
    for projection_id, (actual, expected) in projection_checks.items():
        if actual != expected:
            issues.append(
                {
                    "code": "intervention_atom_binding_round_trip_projection_mismatch",
                    "projection": projection_id,
                }
            )
    return {
        "status": "pass" if not issues else "fail",
        "issues": issues,
        "atom_field_ids": sorted(atom_field_ids),
        "compared_atom_field_ids": sorted(compared_field_ids),
        "sample_non_default": sample_non_default_report,
    }


def _intervention_atom_binding_round_trip_preserves_halves() -> bool:
    return _intervention_atom_binding_round_trip_report()["status"] == "pass"


def _intervention_atom_binding_measurement_expectations_metadata_only() -> bool:
    atom = _sample_intervention_atom_binding()
    return (
        bool(atom.measurement_expectations)
        and atom.measurement_expectations_authority == "supporting_metadata"
        and atom.authoritative_action_outcome_link is atom.intended_downstream_estimand
        and atom.intended_downstream_estimand.metric_id == "msme_survival_rate"
    )


def _world_model_record_bridge_landed(repo_root: Path) -> bool:
    module_path = repo_root / "src/polisyos/runtime/quality/world_model_record.py"
    if not module_path.is_file():
        return False
    text = module_path.read_text(encoding="utf-8")
    required_markers = {
        "class WorldModelRecord",
        "def build_world_model_record",
        "build_input_bindings",
        "FabricWorldRef",
        "DataForgeBindingRef",
        "ModelSpec",
        "FoundryBindingRef",
        "SkgCausalPriorRef",
        "consume_world_model_record_for_simulation",
        "resolve_intervention_atom_world_binding",
        "world_substrate_version_mismatch",
        "world_slot_state_path_missing",
    }
    if not all(marker in text for marker in required_markers):
        return False
    runtime_quality_root = repo_root / "src/polisyos/runtime/quality"
    if any(runtime_quality_root.rglob("gy_n3_*.py")):
        return False
    for path in runtime_quality_root.rglob("*.py"):
        try:
            source = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if re.search(r"class\s+\w*(?:WorldStore|WorldStateEngine|StateEngine)\b", source):
            return False
    try:
        from polisyos.runtime.quality.world_model_record import (
            WORLD_MODEL_RECORD_ARTIFACT_KIND,
            WORLD_MODEL_RECORD_SCHEMA_VERSION,
            WorldModelRecord,
            consume_world_model_record_for_simulation,
            resolve_intervention_atom_world_binding,
        )
    except Exception:
        return False
    return (
        WORLD_MODEL_RECORD_SCHEMA_VERSION == "policyos.runtime.world_model_record.v1"
        and WORLD_MODEL_RECORD_ARTIFACT_KIND == "runtime.quality.world_model_record"
        and WorldModelRecord.model_config.get("extra") == "forbid"
        and callable(consume_world_model_record_for_simulation)
        and callable(resolve_intervention_atom_world_binding)
    )


def _production_data_substrate_registry_landed(repo_root: Path) -> bool:
    module_path = repo_root / "src/polisyos/runtime/quality/substrate_registry.py"
    if not module_path.is_file():
        return False
    text = module_path.read_text(encoding="utf-8")
    required_markers = {
        "class SubstrateRegistry",
        "class SubstrateRegistryEntry",
        "class SubstrateRegistration",
        "def build_substrate_registry_from_existing_catalogs",
        "def register_substrate_entry",
        "measurement_registry.json",
        "identification_mode_registry.json",
        "schema_regime_registry.json",
        "dataset_catalog.duckdb",
        "substrate_coverage_inflated",
        "substrate_trust_cap_inflated",
        "substrate_trust_multiplier_inflated",
        "substrate_identification_mode_inflated",
    }
    if not all(marker in text for marker in required_markers):
        return False
    runtime_quality_root = repo_root / "src/polisyos/runtime/quality"
    if any(runtime_quality_root.rglob("gy_s0_*.py")):
        return False
    forbidden_source_list_markers = {
        "HARDCODED_SUBSTRATE_SOURCE_IDS",
        "SUBSTRATE_SOURCE_ALLOWLIST",
        "SUBSTRATE_FAMILY_ALLOWLIST",
    }
    for path in runtime_quality_root.rglob("*.py"):
        try:
            source = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if any(marker in source for marker in forbidden_source_list_markers):
            return False
    world_model_path = repo_root / "src/polisyos/runtime/quality/world_model_record.py"
    if not world_model_path.is_file():
        return False
    world_model_text = world_model_path.read_text(encoding="utf-8")
    if "substrate_registry_ref" not in world_model_text or "required_substrate_families" not in (
        world_model_text
    ):
        return False
    try:
        from polisyos.runtime.quality.substrate_registry import (
            SubstrateCoverage,
            SubstrateLayer,
            SubstrateRegistration,
            SubstrateRegistry,
            SubstrateRegistryEntry,
            SubstrateTrustTier,
            build_substrate_registry_from_existing_catalogs,
            default_substrate_catalog_paths,
            load_l5_catalog_authority,
            register_substrate_entry,
        )
        from tools.quality.validation.check_production_data_substrate_registry_contract import (
            substrate_registry_trust_tier_bounds_behavior_report,
        )

        if SubstrateRegistry.model_config.get("extra") != "forbid":
            return False
        if SubstrateRegistryEntry.model_config.get("extra") != "forbid":
            return False
        if SubstrateRegistration.model_config.get("extra") != "forbid":
            return False
        behavior = substrate_registry_trust_tier_bounds_behavior_report(repo_root)
        if behavior["status"] != "pass":
            return False
        l5 = load_l5_catalog_authority(default_substrate_catalog_paths(repo_root))
        registry = build_substrate_registry_from_existing_catalogs(repo_root)
        layers = {entry.layer for entry in registry.entries}
        if not {SubstrateLayer.L1, SubstrateLayer.L2, SubstrateLayer.L3, SubstrateLayer.L4, SubstrateLayer.L5, SubstrateLayer.L6} <= layers:
            return False
        proxy = registry.resolve(family_id="household_distribution", layer=SubstrateLayer.L5)[
            0
        ]
        if proxy.identification_mode != "proxy_identified":
            return False
        expected_proxy_tier = l5.expected_trust_tier("household_distribution")
        if proxy.trust_tier.tier != expected_proxy_tier.tier:
            return False
        weak_l1 = registry.resolve(
            source_id="l1_dcat:data_gov_ua_broad",
            family_id="dcat_source:data_gov_ua_broad",
            layer=SubstrateLayer.L1,
        )[0]
        if weak_l1.trust_tier.tier != "weak_anchor":
            return False
        registration = SubstrateRegistration(
            source_id="ledger-probe-source",
            family_id="ledger_probe_family",
            layer=SubstrateLayer.L4,
            coverage=SubstrateCoverage(
                coverage_score=0.33,
                coverage_kind="ledger_probe.coverage",
                coverage_rule_ref="ledger://probe#coverage",
            ),
            trust_tier=SubstrateTrustTier(
                tier="weak_anchor",
                trust_cap=0.25,
                trust_multiplier=0.6,
                min_coverage=0.0,
                max_coverage=1.0,
                authority_ref=l5.trust_tiers["weak_anchor"].authority_ref,
            ),
            identification_mode="bounds_only",
            schema_regime=l5.latest_schema_regime(),
            data_version="ledger-probe-v1",
            snapshot_id="ledger-probe-v1",
            source_snapshot_id="ledger-probe-v1",
            provenance_refs=("ledger://probe",),
            authority_refs=(l5.measurement_registry_ref,),
        )
        updated = register_substrate_entry(registry, registration, l5_authority=l5)
        resolved = updated.resolve(
            source_id="ledger-probe-source",
            family_id="ledger_probe_family",
            layer=SubstrateLayer.L4,
        )[0]
        return (
            updated.substrate_version_id != registry.substrate_version_id
            and resolved.entry_content_hash.startswith("sha256:")
        )
    except Exception:
        return False


def _intervention_substrate_lift_landed(repo_root: Path) -> bool:
    try:
        from polisyos.runtime.quality.intervention_substrate import (
            intervention_substrate_behavior_report,
        )
        from polisyos.runtime.quality.substrate_registry import (
            SubstrateLayer,
            build_substrate_registry_from_existing_catalogs,
        )
        from tools.quality.validation.check_layer3_gy_intervention_substrate_contract import (
            validate as validate_intervention_substrate_contract,
        )

        behavior = intervention_substrate_behavior_report(repo_root)
        contract = validate_intervention_substrate_contract(repo_root)
        registry = build_substrate_registry_from_existing_catalogs(repo_root)
        l6_families = {
            entry.family_id
            for entry in registry.resolve(layer=SubstrateLayer.L6)
        }
        required_families = {
            "l6_intervention_knob_dictionary",
            "l6_lex_intervention_map",
            "l6_observation_contract_routes",
            "l6_policy_scenario_templates",
        }
        return (
            behavior.get("status") == "pass"
            and contract.get("status") == "pass"
            and required_families <= l6_families
        )
    except Exception:
        return False


def _value_outer_set_contract_importable() -> bool:
    try:
        from polisyos.core.contracts import DataTrust, ValueOuterSet

        value_set = ValueOuterSet.interval_box(
            coordinates=("metric",),
            lower=(1.0,),
            upper=(2.0,),
            identification_mode="proxy_identified",
            assumptions=("ledger_probe",),
            assumption_status="externally_supported",
            calibration_scope={"measurement": "ledger_probe"},
            data_trust=DataTrust(
                tier="derived_proxy",
                trust_cap=0.6,
                trust_multiplier=0.6,
                min_coverage=0.35,
                max_coverage=0.85,
                promotion_floor=0.5,
                authority_ref="ledger://l5/trust_tier/derived_proxy",
            ),
            world_model_record_ref="world_model_record_ledger_probe",
            epoch="ledger_epoch",
            representation_status="certified",
        )
        non_certified = ValueOuterSet.model_validate(
            {
                **value_set.model_dump(mode="json"),
                "representation_status": "search_only",
                "width": (),
            }
        )
        zero_trust = ValueOuterSet.model_validate(
            {
                **value_set.model_dump(mode="json"),
                "data_trust": {
                    "tier": "synthetic_zero_trust",
                    "trust_cap": 0.0,
                    "trust_multiplier": 1.0,
                    "min_coverage": 0.0,
                    "max_coverage": 1.0,
                    "promotion_floor": 0.5,
                    "authority_ref": "ledger://l5/trust_tier/synthetic_zero_trust",
                },
                "width": (),
            }
        )
        return (
            value_set.identification_status == "proxy"
            and value_set.width == (1.0,)
            and value_set.promotion_decision().promotable
            and not non_certified.promotion_decision().promotable
            and not zero_trust.promotion_decision().promotable
            and "data_trust_zero" in zero_trust.promotion_decision().reasons
            and value_set.compare(value_set, force_timeout=True) == "unknown"
        )
    except Exception:
        return False


def _value_outer_set_strangle_receipt_landed(repo_root: Path) -> bool:
    try:
        from tools.quality.validation.check_layer3_gy_value_outer_set_strangle_receipt import (
            validate,
        )

        return validate(repo_root)["status"] == "pass"
    except Exception:
        return False


def _contains_pattern(text: str, pattern: str, *, regex: bool) -> bool:
    if regex:
        return re.search(pattern, text, flags=re.M) is not None
    return pattern in text


def _validate_method_availability_gate(
    repo_root: Path,
    ledger: dict[str, Any],
    issues: list[dict[str, Any]],
) -> dict[str, Any]:
    gate = ledger.get("method_availability_gate")
    if not isinstance(gate, dict):
        issues.append({"code": "method_availability_gate_missing"})
        gate = {}
    expected = gate.get("expected")
    if not isinstance(expected, dict):
        issues.append({"code": "method_availability_gate_expected_missing"})
        expected = {}
    live = _probe_method_availability_gate(repo_root)
    for method_id, expected_row in expected.items():
        if not isinstance(expected_row, dict):
            issues.append({"code": "method_availability_expected_row_invalid", "method": method_id})
            continue
        live_row = live.get(method_id)
        if not live_row:
            issues.append({"code": "method_availability_live_probe_missing", "method": method_id})
            continue
        optional_available = bool(expected_row.get("optional_available"))
        expected_available = bool(expected_row.get("available"))
        live_available = bool(live_row.get("available"))
        smoke_status = str(live_row.get("smoke_status") or "")
        if optional_available:
            if live_available and smoke_status != "pass":
                issues.append(
                    {
                        "code": "method_availability_gate_drift",
                        "method": method_id,
                        "expected_available": "optional",
                        "live_available": live_available,
                        "smoke_status": smoke_status,
                        "detail": live_row.get("detail"),
                    }
                )
            if not live_available and smoke_status != "unavailable":
                issues.append(
                    {
                        "code": "method_availability_gate_drift",
                        "method": method_id,
                        "expected_available": "optional",
                        "live_available": live_available,
                        "smoke_status": smoke_status,
                        "detail": live_row.get("detail"),
                    }
                )
            continue
        if expected_available != live_available or (
            expected_available and smoke_status != "pass"
        ):
            issues.append(
                {
                    "code": "method_availability_gate_drift",
                    "method": method_id,
                    "expected_available": expected_available,
                    "live_available": live_available,
                    "smoke_status": smoke_status,
                    "detail": live_row.get("detail"),
                }
            )
    decision = gate.get("decision")
    if decision != "stay_on_python_3_14":
        issues.append({"code": "method_availability_decision_drift", "decision": decision})
    return {
        "decision": decision,
        "expected_unavailable": sorted(
            method_id
            for method_id, row in expected.items()
            if isinstance(row, dict)
            and not bool(row.get("available"))
            and not bool(row.get("optional_available"))
        ),
        "expected_available": sorted(
            method_id
            for method_id, row in expected.items()
            if isinstance(row, dict)
            and bool(row.get("available"))
            and not bool(row.get("optional_available"))
        ),
        "expected_optional_available": sorted(
            method_id
            for method_id, row in expected.items()
            if isinstance(row, dict) and bool(row.get("optional_available"))
        ),
        "live": live,
    }


def _probe_method_availability_gate(repo_root: Path) -> dict[str, dict[str, Any]]:
    _ensure_src_path(repo_root)
    os.environ.setdefault("JAX_PLATFORMS", "cpu")
    probes: dict[str, dict[str, Any]] = {}
    for module_name in ("econml", "dowhy"):
        probes[module_name] = _probe_unavailable_import(module_name)
    probes["cvxpy"] = _probe_optional_cvxpy()
    probes["statsmodels"] = _probe_compute("statsmodels", _smoke_statsmodels)
    probes["jax"] = _probe_compute("jax", _smoke_jax)
    probes["scipy"] = _probe_compute("scipy", _smoke_scipy)
    probes["pymoo"] = _probe_compute("pymoo", _smoke_pymoo)
    probes["foundry_bayesian_variational"] = _probe_compute(
        "foundry_bayesian_variational",
        _smoke_foundry_bayesian_variational,
    )
    probes["foundry_bayesian_bvar"] = _probe_compute(
        "foundry_bayesian_bvar",
        _smoke_foundry_bayesian_bvar,
    )
    probes["foundry_transport"] = _probe_compute("foundry_transport", _smoke_foundry_transport)
    return probes


def _probe_unavailable_import(module_name: str) -> dict[str, Any]:
    spec = importlib.util.find_spec(module_name)
    if spec is None:
        return {
            "available": False,
            "smoke_status": "unavailable",
            "detail": "ModuleNotFoundError",
        }
    try:
        importlib.import_module(module_name)
    except ModuleNotFoundError as exc:
        return {"available": False, "smoke_status": "unavailable", "detail": str(exc)}
    except Exception as exc:
        return {"available": False, "smoke_status": "import_error", "detail": repr(exc)}
    return {"available": True, "smoke_status": "imported", "detail": "import succeeded"}


def _probe_compute(method_id: str, smoke: Any) -> dict[str, Any]:
    try:
        detail = smoke()
    except Exception as exc:
        return {
            "available": False,
            "smoke_status": "fail",
            "detail": f"{type(exc).__name__}: {exc}",
        }
    return {"available": True, "smoke_status": "pass", "detail": detail, "method": method_id}


def _probe_optional_cvxpy() -> dict[str, Any]:
    if importlib.util.find_spec("cvxpy") is None:
        return {
            "available": False,
            "smoke_status": "unavailable",
            "detail": "ModuleNotFoundError",
        }
    return _probe_compute("cvxpy", _smoke_cvxpy)


def _smoke_statsmodels() -> str:
    import numpy as np
    import statsmodels.api as sm

    x = np.array([1.0, 2.0, 3.0, 4.0])
    y = 1.0 + 2.0 * x
    fit = sm.OLS(y, sm.add_constant(x)).fit()
    return f"ols_slope={float(fit.params[1]):.6f}"


def _smoke_jax() -> str:
    import jax.numpy as jnp

    value = float(jnp.asarray([1.0, 2.0]).sum().item())
    return f"array_sum={value:.6f};platforms={os.environ.get('JAX_PLATFORMS', '')}"


def _smoke_scipy() -> str:
    from scipy.optimize import minimize

    result = minimize(lambda value: (value[0] - 2.0) ** 2, [0.0])
    return f"quadratic_argmin={float(result.x[0]):.6f}"


def _smoke_pymoo() -> str:
    from pymoo.algorithms.moo.nsga2 import NSGA2
    from pymoo.optimize import minimize
    from pymoo.problems import get_problem

    result = minimize(get_problem("zdt1", n_var=3), NSGA2(pop_size=8), ("n_gen", 1), seed=1)
    return f"nsga2_front_shape={tuple(result.F.shape)}"


def _smoke_cvxpy() -> str:
    import cvxpy as cp

    value = cp.Variable()
    problem = cp.Problem(cp.Minimize((value - 2.0) ** 2))
    optimum = problem.solve()
    return f"status={problem.status};value={float(optimum):.6f};x={float(value.value):.6f}"


def _smoke_foundry_bayesian_variational() -> str:
    from polisyos.foundry.methods.catalog.bayesian.variational import MeanFieldVIEstimator
    from polisyos.foundry.methods.catalog.ml.protocols import TabularData

    state = TabularData(
        features=[
            [1.0, 0.0],
            [1.0, 1.0],
            [1.0, 2.0],
            [1.0, 3.0],
            [1.0, 4.0],
            [1.0, 5.0],
        ],
        target=[1.0, 2.0, 3.0, 4.0, 5.0, 6.0],
    )
    result = MeanFieldVIEstimator.pure_step(
        state,
        {"max_iter": 5, "prior_scale": 2.0, "noise_variance": 1.0},
    )
    return f"vi_beta1={float(result['posterior_mean'][1]):.6f}"


def _smoke_foundry_bayesian_bvar() -> str:
    import numpy as np

    from polisyos.foundry.methods.catalog.econometrics.expansion import BayesianVAREstimator
    from polisyos.foundry.methods.catalog.econometrics.protocols import TimeSeriesData

    state = TimeSeriesData(
        endog=np.column_stack(
            [np.arange(12, dtype=float), np.arange(12, dtype=float) * 2.0 + 1.0]
        )
    )
    result = BayesianVAREstimator.pure_step(state, {"n_lags": 1, "prior_scale": 0.5})
    return f"bvar_method={result['result'].method_name};n_obs={result['result'].n_obs}"


def _smoke_foundry_transport() -> str:
    from polisyos.foundry.methods.catalog.causal.transport_engine import solve_transportability
    from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, GraphType
    from polisyos.ir.analytics.context import ContextProfile
    from polisyos.ir.analytics.transportability import SelectionDiagram

    graph = CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["x", "y"],
        edges=[CausalEdge(src="x", dst="y")],
    )
    diagram = SelectionDiagram(
        base_graph=graph,
        source_context=ContextProfile(context_id="source"),
        target_context=ContextProfile(context_id="target"),
    )
    result = solve_transportability(
        selection_diagram=diagram,
        query_treatment="x",
        query_outcome="y",
    )
    return f"transport_status={result.status.value};mode={result.transport_mode.value}"


def _validate_registration(repo_root: Path, issues: list[dict[str, Any]]) -> None:
    generated_path = repo_root / "architecture/generated_artifacts.toml"
    if not generated_path.is_file():
        issues.append({"code": "generated_artifacts_registry_missing"})
    else:
        generated = tomllib.loads(generated_path.read_text(encoding="utf-8"))
        families = {family.get("id"): family for family in generated.get("family", [])}
        family = families.get(FAMILY_ID)
        if not isinstance(family, dict):
            issues.append({"code": "generated_artifacts_family_missing", "family_id": FAMILY_ID})
        else:
            outputs = set(family.get("outputs") or [])
            if DEFAULT_LEDGER_PATH.as_posix() not in outputs:
                issues.append({"code": "generated_artifacts_output_missing"})
            if family.get("lifecycle") != "source_committed":
                issues.append({"code": "generated_artifacts_lifecycle_invalid"})
            if family.get("gy_lifecycle_family") is not True:
                issues.append({"code": "generated_artifacts_gy_lifecycle_missing"})
            if family.get("stale_output_behavior") != "fail":
                issues.append({"code": "generated_artifacts_stale_policy_invalid"})
            if family.get("workflow") != (
                "tools/quality/validation/check_layer3_gy_generation_cycle_disposition_ledger.py"
            ):
                issues.append({"code": "generated_artifacts_workflow_invalid"})
    inventory_path = repo_root / "architecture/policy_design_case/inventory.json"
    if not inventory_path.is_file():
        issues.append({"code": "policy_design_case_inventory_missing"})
        return
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    paths = {
        artifact.get("path")
        for artifact in inventory.get("artifacts", [])
        if isinstance(artifact, dict)
    }
    if DEFAULT_LEDGER_PATH.as_posix() not in paths:
        issues.append({"code": "policy_design_case_inventory_output_missing"})


def _summary(
    owners: list[dict[str, Any]],
    ledger: dict[str, Any],
    strangle_summary: dict[str, int],
    notebook_owners: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    counts = dict.fromkeys(sorted(DISPOSITIONS), 0)
    for owner in owners:
        disposition = owner.get("disposition")
        if disposition in counts:
            counts[disposition] += 1
    mapping = ledger.get("task_owner_mapping")
    missing_count = 0
    if isinstance(mapping, dict):
        owner_ids = {
            str(owner.get("owner_id"))
            for owner in owners
            if isinstance(owner, dict) and owner.get("owner_id")
        }
        for row in mapping.values():
            if isinstance(row, dict):
                for owner_id in row.get("owner_ids") or []:
                    if owner_id not in owner_ids:
                        missing_count += 1
    source_reconciliation = ledger.get("source_reconciliation")
    if not isinstance(source_reconciliation, dict):
        source_reconciliation = {}
    return {
        "owner_count": len(owners),
        "notebook_owner_count": len(notebook_owners),
        "disposition_counts": counts,
        "source_reconciliation": source_reconciliation,
        "pending_strangle_obligations": strangle_summary["pending"],
        "landed_strangle_obligations_checked": strangle_summary["landed_checked"],
        "strangled_obligations_checked": strangle_summary["strangled"],
        "task_mapping_missing_owner_count": missing_count,
    }


def _ensure_src_path(repo_root: Path) -> None:
    for path in (repo_root, repo_root / "src"):
        value = path.as_posix()
        if value not in sys.path:
            sys.path.insert(0, value)


def _list_of_dicts(
    value: object,
    *,
    field: str,
    issues: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        issues.append({"code": f"{field}_missing_or_invalid"})
        return []
    rows: list[dict[str, Any]] = []
    for index, item in enumerate(value):
        if isinstance(item, dict):
            rows.append(item)
        else:
            issues.append({"code": f"{field}_row_invalid", "index": index})
    return rows


def _dict_of_dicts(
    value: object,
    *,
    field: str,
    issues: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    if not isinstance(value, dict):
        issues.append({"code": f"{field}_missing_or_invalid"})
        return {}
    rows: dict[str, dict[str, Any]] = {}
    for key, item in value.items():
        if isinstance(item, dict):
            rows[str(key)] = item
        else:
            issues.append({"code": f"{field}_row_invalid", "key": key})
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[3],
        help="Repository root containing architecture/ and src/.",
    )
    parser.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER_PATH)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--corrupt-field-drift-check", action="store_true")
    parser.add_argument("--output-format", choices={"text", "json"}, default="text")
    args = parser.parse_args()

    if args.corrupt_field_drift_check:
        report = corrupt_field_drift_check(args.repo_root)
    else:
        report = validate(args.repo_root, ledger_path=args.ledger)

    if args.output_format == "json":
        print(json.dumps(report, indent=2, sort_keys=True))
    elif report["status"] == "pass":
        print("PASS layer3_gy_generation_cycle_disposition_ledger")
    else:
        print("FAIL layer3_gy_generation_cycle_disposition_ledger")
        for issue in report["issues"]:
            print(f"- {issue.get('code')}: {issue}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
