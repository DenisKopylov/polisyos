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
HISTORY_FAMILY_ID = "policy-design-case-layer3-gy-phase2-history-artifacts"
HISTORICAL_OUTPUTS_SHA256 = {
    "architecture/policy_design_case/layer3_gy_phase2_playbook_run_proofs.json": "sha256:fe3a082ba981ce27d2dc459219ea0081609085b5e467277bb66a9049ee7297e3",
    "architecture/policy_design_case/layer3_gy_phase2_foundry_consumption_proofs.json": "sha256:4beee967f38b77738b13ed59a86a70d1100d23ea48bc1e6f1e521a54db7929c0",
}
PLAYBOOK_PROOF_PATH = "architecture/policy_design_case/layer3_gy_phase2_playbook_run_proofs_v4.json"
SPINE_PROOF_PATH = "architecture/policy_design_case/layer3_gy_phase2_spine_repair_proofs.json"
FOUNDRY_PROOF_PATH = (
    "architecture/policy_design_case/layer3_gy_phase2_foundry_consumption_proofs_v3.json"
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


C1_PROOF_SCHEMA = "policyos.policy_design_case.layer3_gy_phase2.playbook_run_proofs.v4"
C3_PROOF_SCHEMA = "policyos.policy_design_case.layer3_gy_phase2.foundry_consumption_proofs.v3"
PROTECTED_OUTPUTS = (SPINE_PROOF_PATH, AGENT_AUDIT_PATH, STRANGLE_RECEIPT_PATH)
PHASE2_SCENARIOS = (
    ("stable", {"verification_required": True}),
    ("synthetic_probe", {"observational_data_ref": "validator-synthetic-probe"}),
    ("deviation", {"force_counterexample": "missing_bounds"}),
)


def declared_outputs() -> list[str]:
    """Return the complete measured family, including protected compare-only members."""

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


def _phase2_json_nodes(value: Any, path: str = "") -> dict[str, Any]:
    """Enumerate every JSON node, preserving absence, null, type and emptiness."""
    if isinstance(value, dict):
        result = {path: {"type": "object", "keys": sorted(value)}}
        for key, item in value.items():
            pointer = key.replace("~", "~0").replace("/", "~1")
            result.update(_phase2_json_nodes(item, path + "/" + pointer))
        return result
    if isinstance(value, list):
        result = {path: {"type": "array", "length": len(value)}}
        for index, item in enumerate(value):
            result.update(_phase2_json_nodes(item, path + "/" + str(index)))
        return result
    return {path: {"type": type(value).__name__, "value": value}}


def _phase2_payload_delta(actual: Any, expected: Any) -> list[str]:
    left, right = _phase2_json_nodes(actual), _phase2_json_nodes(expected)
    absent = object()
    return sorted(
        path
        for path in left.keys() | right.keys()
        if left.get(path, absent) != right.get(path, absent)
    )


def validate(repo_root: Path, *, write: bool = False) -> dict[str, Any]:
    """Recompute all current slots; failed conjuncts stay red even in write mode."""
    src_path = repo_root / "src"
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))
    issues: list[dict[str, Any]] = []
    _validate_generated_artifacts_registration(repo_root, issues)
    expected = build_live_proof_payloads(repo_root)
    if len(OUTPUTS) != len(set(OUTPUTS)) or set(expected) != set(OUTPUTS):
        issues.append(
            {
                "code": "phase2_complete_output_population_mismatch",
                "expected": sorted(OUTPUTS),
                "actual": sorted(expected),
            }
        )
    task_status = {}
    for task, path, schema in (
        ("GY-C1", PLAYBOOK_PROOF_PATH, C1_PROOF_SCHEMA),
        ("GY-C3", FOUNDRY_PROOF_PATH, C3_PROOF_SCHEMA),
    ):
        payload = expected.get(path)
        if not isinstance(payload, dict):
            issues.append({"code": "phase2_task_proof_unavailable", "path": path})
            task_status[task] = "fail"
            continue
        measurement = payload.get("measurement")
        if (
            payload.get("schema_version") != schema
            or not isinstance(measurement, dict)
            or measurement.get("status") not in {"pass", "fail"}
            or not isinstance(measurement.get("issues"), list)
        ):
            issues.append({"code": "phase2_task_measurement_invalid", "path": path})
            task_status[task] = "fail"
            continue
        task_issues = measurement["issues"]
        if any(not isinstance(item, dict) or not item.get("code") for item in task_issues):
            issues.append({"code": "phase2_task_finding_identity_invalid", "path": path})
        else:
            issues.extend(dict(item, task_id=task, artifact_path=path) for item in task_issues)
        task_status[task] = (
            "pass"
            if measurement["status"] == "pass" and not task_issues and payload.get("proofs")
            else "fail"
        )
        if task_status[task] == "fail" and not task_issues:
            issues.append({"code": "phase2_task_decisive_property_unmet", "path": path})
    playbook = expected.get(PLAYBOOK_PROOF_PATH)
    collection = playbook.get("family_collection") if isinstance(playbook, dict) else None
    if not isinstance(collection, dict):
        issues.append({"code": "phase2_family_collection_unavailable"})
    else:
        expected_scenarios = [name for name, _ in PHASE2_SCENARIOS]
        actual_scenarios = [row["scenario"] for row in collection["scenario_attempts"]]
        if (
            actual_scenarios != expected_scenarios
            or len(actual_scenarios) != len(set(actual_scenarios))
            or collection["expected_outputs"] != OUTPUTS
        ):
            issues.append({"code": "phase2_complete_attempt_population_mismatch"})
        issues.extend(collection["component_errors"])
        for row in collection["scenario_attempts"]:
            if row["status"] == "crashed":
                issues.append(row["error"])
            elif row["status"] != "returned":
                issues.append({"code": "phase2_attempt_not_measured", "scenario": row["scenario"]})
    lex = expected.get(STRANGLE_RECEIPT_PATH)
    if isinstance(lex, dict):
        _validate_lex_bounds_strangle_receipt(lex, issues)
    _validate_lex_runtime_injection_fence(repo_root, issues)
    written = []
    for relative_path in OUTPUTS:
        expected_payload = expected.get(relative_path)
        if not isinstance(expected_payload, dict):
            issues.append({"code": "phase2_output_projection_unavailable", "path": relative_path})
            continue
        path = repo_root / relative_path
        if write and relative_path not in PROTECTED_OUTPUTS:
            # A successor may record an honest failed measurement. This does
            # not turn the command green or mutate its historical predecessor.
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(expected_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
            written.append(relative_path)
        else:
            committed = _read_json(path, issues)
            delta = _phase2_payload_delta(committed, expected_payload)
            if delta:
                issues.append(
                    {
                        "code": "phase2_protected_owner_drift"
                        if relative_path in PROTECTED_OUTPUTS
                        else "phase2_artifact_drift",
                        "path": relative_path,
                        "changed_json_node_identities": delta,
                    }
                )
    # Duplicated delivery of one captured failure is one finding identity. Never
    # deduplicate by total/code alone: path/scenario/error details stay bound.
    identities = {json.dumps(issue, sort_keys=True): issue for issue in issues}
    return {
        "status": "pass" if not identities else "fail",
        "family_id": FAMILY_ID,
        "checked_artifacts": list(OUTPUTS),
        "task_measurements": task_status,
        "write": write,
        "written_artifacts": written,
        "issues": [identities[key] for key in sorted(identities)],
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


def _phase2_error(code: str, path: str, exc: Exception) -> dict[str, Any]:
    """Keep an actual failed attempt separate from an empty observation."""
    import traceback

    traceback.print_exception(exc, file=sys.stderr)
    return {"code": code, "path": path, "error_type": type(exc).__name__, "message": str(exc)}


def _attempt_phase2_scenario(loop: Any, name: str, problem: Any) -> dict[str, Any]:
    from polisyos.runtime.quality.workspace.loop import WorkspaceIntentRunResult

    request = problem.model_dump(mode="json")
    try:
        result = loop.run_intent(problem)
        # Validate a mapping, since model_validate(existing_model) does not
        # revalidate a mutated nested container. Keep the original capability:
        # serialized conformance deliberately excludes its checked execution.
        WorkspaceIntentRunResult.model_validate(result.model_dump(mode="json"))
        error = None
    except Exception as exc:
        result = None
        error = _phase2_error("phase2_scenario_crashed", name, exc)
    return {"scenario": name, "request": request, "result": result, "error": error}


def _phase2_attempt_summary(attempt: dict[str, Any]) -> dict[str, Any]:
    result = attempt["result"]
    return {
        "scenario": attempt["scenario"],
        "request": attempt["request"],
        "status": "crashed" if result is None else "returned",
        "error": attempt["error"],
        "terminal": result.terminal_state.kind.value if result is not None else None,
        "method_selection": (
            result.phase2_method_selection.model_dump(mode="json")
            if result is not None and result.phase2_method_selection is not None
            else None
        ),
        "admission_attempts": [
            {
                "step_id": item.candidate.step_id,
                "passed": item.conformance.passed,
                "smoke_attempted": item.smoke_attempted,
                "admitted": item.step is not None,
            }
            for item in result.adapter_admissions
        ]
        if result is not None
        else None,
    }


def _phase2_bytes(value: Any) -> bytes:
    from polisyos.core.canon import CanonSpec, to_canonical_bytes

    return to_canonical_bytes(value, CanonSpec(forbid_floats=False, exclude_none=False))


def _phase2_semantic_digest(value: Any) -> str:
    return "semantic:sha256:" + hashlib.sha256(_phase2_bytes(value)).hexdigest()


def _phase2_replace_bound(value: Any, replacements: dict[str, str]) -> Any:
    # Exact identities only. Unknown fields, nulls and empty containers survive.
    if isinstance(value, str):
        return replacements.get(value, value)
    if isinstance(value, list):
        return [_phase2_replace_bound(item, replacements) for item in value]
    if isinstance(value, dict):
        return {key: _phase2_replace_bound(item, replacements) for key, item in value.items()}
    return value


def _phase2_same_observation_time(value: str, expected: str) -> bool:
    from datetime import datetime

    actual = datetime.fromisoformat(value.replace("Z", "+00:00"))
    bound = datetime.fromisoformat(expected.replace("Z", "+00:00"))
    return actual.tzinfo is not None and bound.tzinfo is not None and actual == bound


def _phase2_cas_projection(
    *,
    store: Any,
    root_ids: list[str],
    readback: dict[str, Any],
) -> dict[str, Any]:
    """Verify the entire current CAS ancestry before projecting owned clocks.

    Raw identities remain in deciding command output. The returned digests are
    explicitly semantic comparison coordinates, never resolvable CAS addresses.
    """
    from polisyos.core.artifacts import ArtifactRef as CoreArtifactRef
    from polisyos.core.canon import CanonSpec, from_canonical_bytes, to_canonical_bytes
    from polisyos.runtime.quality.workspace.foundry_consumption import (
        _method_evidence_semantics,
    )
    from polisyos.runtime.quality.workspace.scientist_node_adapters import (
        _read_binding,
        _reference_closure,
    )

    request, packet = readback["request"], readback["packet"]
    generated_at = request["generated_at"]
    if packet["generated_at"] != generated_at:
        raise ValueError("phase2_constraint_observation_time_mismatch")
    original_method = request.get("method_consumption")
    replacements: dict[str, str] = {}
    historical_evidence: set[str] = set()
    if original_method is not None:
        expected_hash = (
            "sha256:"
            + hashlib.sha256(
                to_canonical_bytes(
                    original_method,
                    CanonSpec(forbid_floats=False),
                )
            ).hexdigest()
        )
        if packet["method_consumption_hash"] != expected_hash:
            raise ValueError("phase2_constraint_original_method_body_mismatch")
        historical_evidence = {
            row["artifact_id"] for row in original_method["record"]["consumed_method_evidence_refs"]
        }
    elif packet["method_consumption_hash"] is not None:
        raise ValueError("phase2_constraint_method_basis_absent")

    rows: dict[str, tuple[Any, bytes, Any]] = {}
    order: list[str] = []
    active: set[str] = set()
    roots: list[Any] = []

    def visit(identity: str) -> None:
        if identity in active:
            raise ValueError("phase2_cas_ancestry_cycle")
        if identity in rows:
            return
        active.add(identity)
        manifest = store.get_manifest(identity)
        ref = CoreArtifactRef(
            artifact_id=manifest.artifact_id,
            kind=manifest.kind,
            media_type=manifest.media_type,
        )
        binding, raw, manifest = _read_binding(store, ref, identity)
        if manifest.byte_size != len(raw):
            raise ValueError("phase2_cas_manifest_byte_size_mismatch")
        parents = [(str(item.artifact_id), item.role) for item in manifest.inputs]
        if len(parents) != len(set(parents)):
            raise ValueError("phase2_duplicate_cas_parent_identity")
        for parent, _ in parents:
            visit(parent)
        active.remove(identity)
        rows[identity] = (binding, raw, manifest)
        order.append(identity)

    if len(root_ids) != len(set(root_ids)):
        raise ValueError("phase2_duplicate_cas_root_identity")
    for identity in root_ids:
        visit(identity)
        roots.append(rows[identity][0].artifact_ref)
    # Second derivation uses the existing adapter owner, walking actual typed
    # refs and actual manifest parents, rather than the projection traversal.
    independent = _reference_closure(store, roots, "phase2_proof_roots")
    if set(rows) != {str(item.artifact_ref.artifact_id) for item in independent}:
        raise ValueError("phase2_cas_closure_identity_mismatch")
    if not historical_evidence <= rows.keys():
        raise ValueError("phase2_method_evidence_outside_verified_ancestry")
    owned_ids = {
        row["artifact_id"] for row in packet["parent_refs"] if row["role"] != "constraint_source"
    } | {root_ids[0]}
    semantic: dict[str, Any] = {}
    raw_receipts = []
    for identity in order:
        binding, raw, manifest = rows[identity]
        raw_receipts.append(
            {
                "binding": binding.model_dump(mode="json"),
                "manifest": manifest.model_dump(mode="json", by_alias=True),
            }
        )
        source = from_canonical_bytes(raw) if manifest.media_type == "application/json" else None
        if identity in historical_evidence:
            source = from_canonical_bytes(_method_evidence_semantics(raw))
        if identity in owned_ids and manifest.kind.startswith("gy.constraint_"):
            producer = manifest.producer
            if (
                producer is None
                or str(producer.component)
                != "polisyos.runtime.quality.workspace.foundry_consumption.ConstraintStoreIngestor"
            ):
                raise ValueError("phase2_constraint_projection_owner_mismatch")
            if manifest.kind == "gy.constraint_store":
                if source["generated_at"] != generated_at:
                    raise ValueError("phase2_constraint_observation_time_mismatch")
                source["generated_at"] = "observed:current_constraint_evaluation"
                if original_method is not None:
                    method_projection = _phase2_replace_bound(original_method, replacements)
                    source["method_consumption_hash"] = _phase2_semantic_digest(method_projection)
            elif manifest.kind == "gy.constraint_obligation_graph":
                graph = source["source_payload"]
                if not _phase2_same_observation_time(graph["generated_at"], generated_at):
                    raise ValueError("phase2_obligation_graph_observation_time_mismatch")
                graph["generated_at"] = "observed:current_constraint_evaluation"
                for collection in ("candidate_ledger", "deferred_or_rejected"):
                    for item in graph[collection]:
                        if not _phase2_same_observation_time(item["observed_at"], generated_at):
                            raise ValueError("phase2_obligation_member_observation_time_mismatch")
                        item["observed_at"] = "observed:current_constraint_evaluation"
        if source is None:
            body_digest = "semantic:sha256:" + hashlib.sha256(raw).hexdigest()
            body = {"raw_content_sha256": hashlib.sha256(raw).hexdigest(), "byte_size": len(raw)}
        else:
            body = _phase2_replace_bound(source, replacements)
            body_digest = _phase2_semantic_digest(body)
        replacements[identity] = body_digest
        replacements["cas://" + identity] = "semantic-ref:" + body_digest
        projected_manifest = _phase2_replace_bound(
            manifest.model_dump(mode="json", by_alias=True),
            replacements,
        )
        del projected_manifest["created_at"]
        projected_manifest["integrity"]["sha256"] = body_digest
        # The raw length has already been verified. The comparison body may
        # differ only by the declared observed-time/evidence-time projections.
        projected_manifest["byte_size"] = (
            len(_phase2_bytes(body)) if source is not None else len(raw)
        )
        semantic[identity] = {
            "content_semantic_digest": body_digest,
            "manifest_semantic_digest": _phase2_semantic_digest(projected_manifest),
            "payload": body,
            "manifest": projected_manifest,
        }
    projected_request = _phase2_replace_bound(request, replacements)
    projected_request["generated_at"] = "observed:current_constraint_evaluation"
    print(
        json.dumps(
            {
                "proof_id": "c3-constraint-and-consumption-cas-readback",
                "actual_readback": readback,
                "raw_closure": raw_receipts,
            },
            sort_keys=True,
        ),
        file=sys.stderr,
    )
    return {
        "roots": [semantic[identity] for identity in root_ids],
        "request": projected_request,
        "closure": sorted(
            semantic.values(),
            key=lambda row: (
                row["content_semantic_digest"],
                row["manifest_semantic_digest"],
            ),
        ),
        "closure_count": len(rows),
        "independent_closure_count": len(
            {str(item.artifact_ref.artifact_id) for item in independent}
        ),
        "projection_policy": {
            "semantic_digests_are_cas_addresses": False,
            "raw_custody_evidence": "complete_deciding_command_output",
            "observed_fields": [
                "ArtifactManifest.created_at",
                "constraint_request.generated_at",
                "constraint_store.generated_at",
                "obligation_graph.generated_at",
                "obligation_graph.candidate_ledger[].observed_at",
                "obligation_graph.deferred_or_rejected[].observed_at",
            ],
            "method_evidence_timing": "existing _method_evidence_semantics after actual replay verification; no cost authority",
        },
    }


def _phase2_constraint_readback(
    *,
    result: Any,
    loop: Any,
    store: Any,
    expected_request: dict[str, Any] | None = None,
) -> dict[str, Any]:
    from polisyos.core.canon import from_canonical_bytes
    from polisyos.runtime.quality.workspace.foundry_consumption import (
        FOUNDRY_CONSUMPTION_RULE_VERSION,
        FoundryConsumptionResult,
    )

    admission = result.constraint_admission
    if admission is None:
        raise ValueError("phase2_constraint_admission_missing")
    readback = from_canonical_bytes(loop.readback_constraint_admission(admission))
    if readback["schema_version"] != "policyos.gy.phase2.ConstraintReadback.v1":
        raise ValueError("phase2_constraint_readback_schema_mismatch")
    packet = readback["packet"]
    if not (
        packet["workspace_id"]
        == readback["request"]["workspace_id"]
        == admission.workspace_id
        == result.workspace_id
    ):
        raise ValueError("phase2_constraint_workspace_binding_mismatch")
    if expected_request is not None and readback["request"]["design_problem"] != expected_request:
        raise ValueError("phase2_constraint_original_request_mismatch")
    identity = str(admission.artifact_ref.artifact_id)
    if from_canonical_bytes(store.get_bytes(identity)) != packet:
        raise ValueError("phase2_constraint_full_payload_mismatch")
    if packet["decision"] != admission.decision.model_dump(mode="json"):
        raise ValueError("phase2_constraint_decision_payload_mismatch")
    decision = packet["decision"]
    expected = (
        [
            *decision["blocking_constraint_ids"],
            *decision["limiting_constraint_ids"],
            *decision["warning_constraint_ids"],
        ]
        if (decision["blocks_promotion"] or decision["downgrades_authority"])
        else []
    )
    blockers = [item for item in result.search_blockers if item.blocked_port == "constraint_store"]
    actual = [item.missing_input for item in blockers]
    if (
        len(expected) != len(set(expected))
        or len(actual) != len(set(actual))
        or set(expected) != set(actual)
    ):
        raise ValueError("phase2_constraint_decision_not_consumed")
    if any(item.applicability_result_ref != identity for item in blockers):
        raise ValueError("phase2_constraint_blocker_receipt_mismatch")
    if not {item.blocker_id for item in blockers} <= set(
        result.terminal_state.blocking_obligations
    ):
        raise ValueError("phase2_constraint_terminal_dropped_blockers")
    roots = [identity]
    if result.method_output_consumption_ref is not None:
        consumption_id = result.method_output_consumption_ref.artifact_id
        from polisyos.core.artifacts.manifest import SchemaInfo
        from polisyos.core.canon import CanonSpec, to_canonical_bytes

        sealed = from_canonical_bytes(
            loop.readback_method_consumption(result.method_output_consumption_ref)
        )
        actual_bytes = store.get_bytes(consumption_id)
        if actual_bytes != to_canonical_bytes(
            {"schema_version": FOUNDRY_CONSUMPTION_RULE_VERSION, **sealed},
            CanonSpec(forbid_floats=False),
        ):
            raise ValueError("phase2_consumption_differed_from_actual_owner_seal")
        raw = from_canonical_bytes(actual_bytes)
        if raw.pop("schema_version") != FOUNDRY_CONSUMPTION_RULE_VERSION:
            raise ValueError("phase2_consumption_epoch_mismatch")
        consumption = FoundryConsumptionResult.model_validate(raw)
        if (
            consumption.record != result.method_output_consumption_record
            or consumption.authority_boundary != result.authority_boundary
            or consumption.input_provenance != result.foundry_input_provenance
            or consumption.constraint_admission_ref is None
            or consumption.constraint_admission_ref.artifact_id != identity
            or consumption.constraint_decision != admission.decision
        ):
            raise ValueError("phase2_consumption_full_loop_readback_mismatch")
        manifest = store.get_manifest(consumption_id)
        if (
            manifest.kind != "gy.method_output_consumption"
            or manifest.artifact_schema
            != SchemaInfo(
                name="policyos.gy.phase2.MethodOutputConsumptionRecord",
                version="3.0",
            )
            or manifest.producer is None
            or str(manifest.producer.component)
            != "polisyos.runtime.quality.workspace.foundry_consumption.FoundryMethodOutputConsumer"
            or manifest.producer.version != FOUNDRY_CONSUMPTION_RULE_VERSION
        ):
            raise ValueError("phase2_consumption_producer_mismatch")
        expected_parents = [
            (ref.artifact_id, role)
            for role, refs in (
                ("method_result", consumption.record.consumed_method_output_refs),
                ("method_evidence", consumption.record.consumed_method_evidence_refs),
                ("measurement_root", consumption.record.measurement_root_refs),
                ("input_binding", [consumption.input_binding_receipt_ref]),
                ("constraint_store", [consumption.constraint_admission_ref]),
            )
            for ref in refs
        ]
        if [(str(item.artifact_id), item.role) for item in manifest.inputs] != expected_parents:
            raise ValueError("phase2_consumption_complete_parents_mismatch")
        roots.append(consumption_id)
    elif result.method_output_consumption_record is not None:
        raise ValueError("phase2_consumption_record_without_receipt")
    return _phase2_cas_projection(store=store, root_ids=roots, readback=readback)


def build_foundry_consumption_proof(
    *,
    attempts: dict[str, Any],
    loop: Any,
    store: Any,
    repo_root: Path,
    return_snapshot: _Phase2ReturnStrangleSnapshot | None = None,
) -> dict[str, Any]:
    """Measure every actual scenario without laundering missing Foundry outputs."""
    if set(attempts) != {name for name, _ in PHASE2_SCENARIOS}:
        raise ValueError("phase2_scenario_population_mismatch")
    issues: list[dict[str, Any]] = []
    proofs = []
    for name, _ in PHASE2_SCENARIOS:
        attempt = attempts[name]
        result = attempt["result"]
        if result is None:
            issues.append(attempt["error"])
            proofs.append({"scenario": name, "result": None, "error": attempt["error"]})
            continue
        record, boundary = result.method_output_consumption_record, result.authority_boundary
        facts = {
            "operation_invocations_present": bool(result.operation_invocations),
            "consumption_record_present": record is not None,
            "consumption_receipt_present": result.method_output_consumption_ref is not None,
            "measurement_rooted": result.foundry_input_provenance == "measurement_rooted",
            "authority_is_measurement": boundary is not None
            and boundary.evidence_kind == "measurement",
            "measurement_roots_present": record is not None and bool(record.measurement_root_refs),
        }
        if name == "stable":
            issues.extend(
                {"code": "c3_" + key + "_unmet", "scenario": name}
                for key, passed in facts.items()
                if not passed
            )
        if name == "synthetic_probe" and (
            record is not None
            or boundary is not None
            or result.terminal_state.kind.value != "search_ceiling_repair_required"
            or not result.search_blockers
        ):
            issues.append({"code": "c3_unbound_synthetic_input_not_refused", "scenario": name})
        if (
            name == "deviation"
            and result.terminal_state.kind.value != "search_ceiling_repair_required"
        ):
            issues.append({"code": "c3_counterexample_terminal_unmet", "scenario": name})
        custody = None
        try:
            custody = _phase2_constraint_readback(
                result=result,
                loop=loop,
                store=store,
                expected_request=attempt["request"],
            )
        except Exception as exc:
            issues.append(_phase2_error("c3_constraint_consumption_readback_failed", name, exc))
        proofs.append(
            {
                "scenario": name,
                "request": attempt["request"],
                "terminal": result.terminal_state.kind.value,
                "decisive_properties": facts,
                "open_production_findings": list(result.open_production_findings),
                "constraint_and_consumption_readback": custody,
                "synthetic_legacy_predicates": {
                    "disposition": "superseded_unsafe_unbound_reference_admission",
                    "synthetic_provenance_observed": result.foundry_input_provenance
                    == "synthetic_probe",
                    "simulation_authority_observed": boundary is not None
                    and boundary.evidence_kind == "simulation",
                    "verifier_execution_not_inferred_from_unrelated_early_refusal": True,
                }
                if name == "synthetic_probe"
                else None,
            }
        )
    return {
        "schema_version": C3_PROOF_SCHEMA,
        "proof_source": "actual_loop_constraint_owner_and_consumption_cas_readback",
        "proofs": proofs,
        "measurement": {"status": "fail" if issues else "pass", "issues": issues},
        "return_strangles": _project_return_strangles(repo_root, "GY-C3", return_snapshot),
    }


def build_live_proof_payloads(repo_root: Path) -> dict[str, dict[str, Any] | None]:
    """Attempt the full fixed family, retaining typed failures without false zeros."""
    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.runtime.quality.design_problem import DesignProblem
    from polisyos.runtime.quality.workspace.loop import WorkspaceLoop
    from polisyos.runtime.quality.workspace.workflow_playbook_projection import (
        build_workflow_playbook_registry,
        select_playbook_for_intent,
    )

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

    root = repo_root / "_build" / "layer3_gy_phase2"
    root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="proof-", dir=root) as temporary:
        store = FileSystemCAS(Path(temporary) / "cas")
        loop = WorkspaceLoop(artifact_store=store)
        attempts = {
            name: _attempt_phase2_scenario(loop, name, _design_problem(**kwargs))
            for name, kwargs in PHASE2_SCENARIOS
        }
        component_errors: list[dict[str, Any]] = []

        def collect(path: str, build: Any) -> dict[str, Any] | None:
            try:
                payload = build()
                if not isinstance(payload, dict):
                    raise TypeError("phase2_component_did_not_return_payload")
                return payload
            except Exception as exc:
                component_errors.append(_phase2_error("phase2_component_crashed", path, exc))
                return None

        stable, deviation = attempts["stable"]["result"], attempts["deviation"]["result"]

        # One complete source census for this family invocation. A census
        # failure remains an ordinary collected component failure; the second
        # task neither retries an expensive failed census nor trusts a supplied
        # dictionary. Every projection still rechecks all source bytes/paths.
        return_snapshot: _Phase2ReturnStrangleSnapshot | None = None
        return_snapshot_error: Exception | None = None

        def current_return_snapshot() -> _Phase2ReturnStrangleSnapshot:
            nonlocal return_snapshot, return_snapshot_error
            if return_snapshot_error is not None:
                raise return_snapshot_error
            if return_snapshot is None:
                try:
                    return_snapshot = _recompute_return_snapshot(repo_root)
                except Exception as exc:
                    return_snapshot_error = exc
                    raise
            return return_snapshot

        def build_c1() -> dict[str, Any]:
            selected = select_playbook_for_intent(
                {
                    "policy_question": "Can Ukraine offer MSME credit guarantees?",
                    "workflow_id": "scientist_discovery",
                }
            )
            registry = build_workflow_playbook_registry()
            return build_playbook_admission_proof(
                repo_root,
                stable=stable,
                deviation=deviation,
                selected=selected,
                registry=registry,
                store=store,
                return_snapshot=current_return_snapshot(),
            )

        playbook = collect(PLAYBOOK_PROOF_PATH, build_c1)
        spine = collect(SPINE_PROOF_PATH, lambda: _build_spine_projection(stable))
        foundry = collect(
            FOUNDRY_PROOF_PATH,
            lambda: build_foundry_consumption_proof(
                attempts=attempts,
                loop=loop,
                store=store,
                repo_root=repo_root,
                return_snapshot=current_return_snapshot(),
            ),
        )
        agent = collect(AGENT_AUDIT_PATH, lambda: _build_agent_projection(store))
        strangle = collect(
            STRANGLE_RECEIPT_PATH, lambda: _build_lex_bounds_strangle_receipt(repo_root)
        )
        c1_issues = [row for row in component_errors if row["path"] == PLAYBOOK_PROOF_PATH]
        for scenario in ("stable", "deviation"):
            if attempts[scenario]["error"] is not None:
                c1_issues.append(attempts[scenario]["error"])
        if (
            deviation is None
            or deviation.terminal_state.kind.value != "search_ceiling_repair_required"
            or deviation.phase2_playbook_trace is None
            or deviation.phase2_playbook_trace.deviation_operation is None
            or deviation.phase2_playbook_trace.deviation_operation.value != "REFINE"
        ):
            c1_issues.append(
                {"code": "c1_counterexample_deviation_missing", "path": PLAYBOOK_PROOF_PATH}
            )
        if playbook is None:
            playbook = {"schema_version": C1_PROOF_SCHEMA, "proofs": None}
        playbook["measurement"] = {
            "status": "fail" if c1_issues else "pass",
            "issues": c1_issues,
            "trajectory_rule": "an actual persisted admission attempt or typed refusal; selection alone does not run",
        }
        if foundry is None:
            foundry = {
                "schema_version": C3_PROOF_SCHEMA,
                "proofs": None,
                "measurement": {
                    "status": "fail",
                    "issues": [
                        row for row in component_errors if row["path"] == FOUNDRY_PROOF_PATH
                    ],
                },
            }
        # All expected slots remain represented. Closed owners are compare-only;
        # an unavailable projection is None plus a named error, never a new proof.
        playbook["family_collection"] = {
            "schema_version": "policyos.gy.phase2.FamilyCollection.v1",
            "scenario_attempts": [
                _phase2_attempt_summary(attempts[name]) for name, _ in PHASE2_SCENARIOS
            ],
            "component_errors": component_errors,
            "expected_outputs": list(OUTPUTS),
        }
        return {
            PLAYBOOK_PROOF_PATH: playbook,
            SPINE_PROOF_PATH: spine,
            FOUNDRY_PROOF_PATH: foundry,
            AGENT_AUDIT_PATH: agent,
            STRANGLE_RECEIPT_PATH: strangle,
        }


def _build_spine_projection(stable: Any) -> dict[str, Any]:
    """Recompute the existing C2 payload without changing its owner behavior."""
    from polisyos.runtime.quality.workspace.spine_repair_gates import (
        BlockedInputProducer,
        GovernanceTailVerifier,
        LexBoundsApplicabilityGate,
    )
    from polisyos.scientist.policy_design import search as policy_search

    if stable is None:
        raise ValueError("phase2_stable_result_unavailable_for_spine_projection")
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

    return {
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
                    blocker.model_dump(mode="json") for blocker in resolved_producer_blockers
                ],
                "default_path_resolved": not resolved_producer_blockers,
            },
            {
                "proof_id": "phase2-governance-tail-six-judge-gate",
                "partial_judge_stack_status": partial_tail.applicability.status,
                "six_judge_stack_status": six_tail.applicability.status,
                "authority_blocked_port": (
                    partial_tail.blocker.blocked_port if partial_tail.blocker is not None else None
                ),
            },
        ],
    }


def _build_agent_projection(proof_store: Any) -> dict[str, Any]:
    """Recompute the existing I payload without changing agent admission."""
    from polisyos.pdc import OperationClass
    from polisyos.runtime.quality.workspace.agent_proposal_bridge import (
        AgentEventBridge,
        normalize_agent_voi_scores,
    )
    from polisyos.scientist.agent.knowledge_tools import KnowledgeToolkit
    from polisyos.scientist.agent.tools.knowledge_tools_adapter import build_knowledge_tool_registry

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
    }


def build_playbook_admission_proof(
    repo_root: Path,
    *,
    stable: Any,
    deviation: Any,
    selected: Any,
    registry: Any,
    store: Any,
    return_snapshot: _Phase2ReturnStrangleSnapshot | None = None,
) -> dict[str, Any]:
    """Bind proof to the persisted admissions actually consulted by the loop.

    This callable permits focused C1 verification. The full family producer
    retains independent task results and reports every unavailable conjunct.
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
    if stable is None or not stable.adapter_admissions:
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
            store,
            admission.conformance_ref,
            "conformance",
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
            *report.input_bindings,
            *report.source_output_bindings,
            *report.output_bindings,
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
                "manifest_semantic_digest": "sha256:"
                + hashlib.sha256(
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
        semantic_digest = (
            "sha256:"
            + hashlib.sha256(
                to_canonical_bytes(semantic_report, _CANON),
            ).hexdigest()
        )
        # These raw receipt identities transitively contain input-manifest
        # created_at through their full manifest hashes. Rebind them to the
        # recomputed semantic receipt; retain the originals in command output.
        receipt_manifest = manifest.model_dump(mode="json", by_alias=True)
        del receipt_manifest["created_at"]
        receipt_manifest["artifact_id"] = semantic_digest
        receipt_manifest["integrity"]["sha256"] = semantic_digest.removeprefix("sha256:")
        witnesses.append(
            {
                key: value
                for key, value in raw_witness.items()
                if key not in {"conformance", "conformance_ref", "receipt_byte_binding"}
            }
            | {
                "conformance": semantic_report,
                "conformance_semantic_digest": semantic_digest,
                "conformance_manifest_semantic_digest": "sha256:"
                + hashlib.sha256(
                    to_canonical_bytes(receipt_manifest, _CANON),
                ).hexdigest(),
            }
        )
    if (
        stable.operation_invocations != admitted_invocations
        or stable.search_ledger_events != admitted_events
        or stable.artifact_envelopes != admitted_envelopes
    ):
        raise AssertionError("c1_loop_did_not_reuse_exact_admitted_execution")
    strangle = recompute_playbook_admission_strangle(repo_root)
    if strangle["unexpected_callers"]:
        raise AssertionError(f"c1_shape_only_admission_bypass:{strangle['unexpected_callers']}")
    print(
        json.dumps(
            {
                "proof_id": "c1-admission-cas-readback",
                "raw_run_admissions": raw_witnesses,
            },
            sort_keys=True,
        ),
        file=sys.stderr,
    )
    return {
        "schema_version": C1_PROOF_SCHEMA,
        "projection_policy": {
            "excluded_run_emission_field": "ArtifactManifest.created_at",
            "recomputed_dependent_identities": [
                "binding.manifest_hash",
                "conformance_ref",
                "receipt_byte_binding",
            ],
            "raw_custody_evidence": "complete_deciding_command_output",
            "semantic_digests_are_cas_addresses": False,
        },
        "proofs": [
            {
                "proof_id": "phase2-playbook-runtime-chain",
                "proof_source": "loop_admission_conformance_cas_readback_recompute",
                "playbook_ids": sorted(registry.playbooks),
                "playbook_step_source": "canonical_workflow_specs_via_node_registry",
                "candidate_step_ids": sorted(candidates),
                "candidate_steps": [
                    candidates[key].model_dump(mode="json") for key in sorted(candidates)
                ],
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
                "candidate_artifact_refs": [
                    item.ref.model_dump(mode="json") for item in admitted_envelopes
                ],
                "authority_path_disposition": "loop_only",
                "deviation_terminal": deviation.terminal_state.kind.value
                if deviation is not None
                else None,
                "deviation_operation": (
                    deviation.phase2_playbook_trace.deviation_operation.value
                    if deviation is not None
                    and deviation.phase2_playbook_trace is not None
                    and deviation.phase2_playbook_trace.deviation_operation
                    else None
                ),
            }
        ],
        "strangle_receipt": strangle,
        "return_strangles": _project_return_strangles(repo_root, "GY-C1", return_snapshot),
    }


_RETURN_PREDECESSOR = "e2cf7f10f2853b7561034b8e0ba699e6bacd32ba"
_RETURN_LOOP = "src/polisyos/runtime/quality/workspace/loop.py"
_RETURN_CONSTRAINT = "src/polisyos/runtime/quality/workspace/foundry_consumption.py"
_RETURN_SCM = "src/polisyos/foundry/methods/catalog/causal/synthetic_control.py"
_RETURN_ENGINE = "src/polisyos/scientist/orchestration/engine/"
_RETURN_EVIDENCE = "docs/superpowers/journals/gy-eight-gaps-evidence/"
_RETURN_SNAPSHOT_ISSUER = object()


class _Phase2ReturnStrangleSnapshot:
    """A single same-family measurement; JSON or a caller census cannot issue it."""

    def __init__(self, repo_root: Path, payload: dict[str, Any], *, issuer: object) -> None:
        if issuer is not _RETURN_SNAPSHOT_ISSUER:
            raise ValueError("phase2_return_snapshot_not_owner_issued")
        self.__root = repo_root.resolve()
        self.__payload = json.dumps(payload, sort_keys=True, allow_nan=False).encode()
        self.__basis = payload["caller_basis"]["source_basis_hash"]
        self._require_current_source()

    def _require_current_source(self) -> None:
        hashes = {
            path.relative_to(self.__root).as_posix(): "sha256:"
            + hashlib.sha256(path.read_bytes()).hexdigest()
            for scope in ("src", "tools", "tests")
            for path in (self.__root / scope).rglob("*.py")
        }
        current = (
            "sha256:" + hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()
        )
        if current != self.__basis:
            raise ValueError("phase2_return_snapshot_source_changed")

    def project(self, repo_root: Path, *, task_id: str | None = None) -> dict[str, Any]:
        if repo_root.resolve() != self.__root:
            raise ValueError("phase2_return_snapshot_root_mismatch")
        self._require_current_source()
        payload = json.loads(self.__payload)
        if task_id is None:
            return payload
        payload["receipts"] = [row for row in payload["receipts"] if row["task_id"] == task_id]
        if not payload["receipts"]:
            raise ValueError("phase2_return_snapshot_task_not_owned")
        indices = sorted(
            {
                int(pointer.rsplit("/", 1)[-1])
                for row in payload["receipts"]
                for pointer in row["remaining_callers"]
            }
        )
        mapping = {original: selected for selected, original in enumerate(indices)}
        basis = payload["caller_basis"]
        basis["references"] = [basis["references"][index] for index in indices]
        basis["reference_projection_task"] = task_id
        for receipt in payload["receipts"]:
            receipt["remaining_callers"] = [
                f"#/caller_basis/references/{mapping[int(pointer.rsplit('/', 1)[-1])]}"
                for pointer in receipt["remaining_callers"]
            ]
        return payload


def _recompute_return_snapshot(repo_root: Path) -> _Phase2ReturnStrangleSnapshot:
    return _Phase2ReturnStrangleSnapshot(
        repo_root, _measure_phase2_return_strangles(repo_root), issuer=_RETURN_SNAPSHOT_ISSUER
    )


def recompute_phase2_return_strangles(
    repo_root: Path, *, task_id: str | None = None
) -> dict[str, Any]:
    """Recompute standalone; family production reuses its one private source-bound snapshot."""
    return _recompute_return_snapshot(repo_root).project(repo_root, task_id=task_id)


def _project_return_strangles(
    repo_root: Path, task_id: str, snapshot: _Phase2ReturnStrangleSnapshot | None
) -> dict[str, Any]:
    if snapshot is None:
        return recompute_phase2_return_strangles(repo_root, task_id=task_id)
    if type(snapshot) is not _Phase2ReturnStrangleSnapshot:
        raise ValueError("phase2_return_snapshot_not_owner_issued")
    return snapshot.project(repo_root, task_id=task_id)


def _return_function_nodes(source: str) -> dict[str, Any]:
    result: dict[str, Any] = {}

    def visit(node: ast.AST, scope: tuple[str, ...] = ()) -> None:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            scope = (*scope, node.name)
            result[".".join(scope)] = node
        for child in ast.iter_child_nodes(node):
            visit(child, scope)

    visit(ast.parse(source))
    return result


def _phase2_return_caller_basis(repo_root: Path) -> dict[str, Any]:
    """Reconcile every current Python path and relevant literal call/reference."""
    import io
    import tokenize

    roots = ("src", "tools", "tests")
    paths = {path for root in roots for path in (repo_root / root).rglob("*.py")}
    independent = {
        Path(directory) / name
        for root in roots
        for directory, _, names in os.walk(repo_root / root)
        for name in names
        if name.endswith(".py")
    }
    if not paths or paths != independent:
        raise ValueError("phase2_return_caller_denominator_unresolved")
    functions = {
        "select_value_method_for_problem",
        "select_method_for_input_contract",
        "_phase2_value_method_selection",
        "evaluate_constraint_store_for_phase2",
        "_phase2_constraint_blockers",
        "decode_node_outcome",
        "_fit_scm_weights",
        "augmented_synthetic_control",
    }
    owner_types = {"ConstraintStoreIngestor", "NodeOutcome", "SyntheticControlMethod"}
    references = []
    snapshots = {}
    ast_terminals, token_terminals = set(), set()

    def scan(path: Path) -> None:
        relative = path.relative_to(repo_root).as_posix()
        raw = path.read_bytes()
        source = raw.decode("utf-8")
        source_lines = source.splitlines()
        snapshots[relative] = "sha256:" + hashlib.sha256(raw).hexdigest()
        tree = ast.parse(source, filename=relative)
        scopes: list[str] = []
        aliases: list[dict[str, str]] = [{}]

        def resolve(node: ast.AST | None) -> str:
            if isinstance(node, ast.Name):
                for table in reversed(aliases):
                    if node.id in table:
                        return table[node.id]
                return node.id
            if isinstance(node, ast.Attribute):
                return resolve(node.value) + "." + node.attr
            if isinstance(node, ast.Call):
                if (
                    isinstance(node.func, ast.Name)
                    and node.func.id == "getattr"
                    and len(node.args) >= 2
                ):
                    member = node.args[1]
                    if isinstance(member, ast.Constant) and isinstance(member.value, str):
                        return resolve(node.args[0]) + "." + member.value
                target = resolve(node.func)
                return target if target.rsplit(".", 1)[-1] in owner_types else "<returned>"
            if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
                choices = [resolve(node.left), resolve(node.right)]
                return next(
                    (item for item in choices if item.rsplit(".", 1)[-1] in owner_types), "<union>"
                )
            return "<dynamic>"

        def relevant(target: str) -> bool:
            return target.rsplit(".", 1)[-1] in functions or any(
                part in owner_types for part in target.split(".")
            )

        def record(node: ast.AST, target: str, role: str) -> None:
            references.append(
                {
                    "path": relative,
                    "function": ".".join(scopes),
                    "line": node.lineno,
                    "column": node.col_offset,
                    "target": target,
                    "role": role,
                    "star_keyword": isinstance(node, ast.Call)
                    and any(item.arg is None for item in node.keywords),
                }
            )

        class Walk(ast.NodeVisitor):
            def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
                for item in node.names:
                    aliases[-1][item.asname or item.name] = f"{node.module}.{item.name}"

            def visit_Import(self, node: ast.Import) -> None:
                for item in node.names:
                    aliases[-1][item.asname or item.name.split(".")[0]] = (
                        item.name if item.asname else item.name.split(".")[0]
                    )

            def visit_ClassDef(self, node: ast.ClassDef) -> None:
                scopes.append(node.name)
                aliases.append({"self": node.name})
                self.generic_visit(node)
                aliases.pop()
                scopes.pop()

            def visit_FunctionDef(self, node: Any) -> None:
                scopes.append(node.name)
                aliases.append({})
                for arg in (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs):
                    target = resolve(arg.annotation)
                    if relevant(target):
                        aliases[-1][arg.arg] = target
                self.generic_visit(node)
                aliases.pop()
                scopes.pop()

            def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
                self.visit_FunctionDef(node)

            def visit_Assign(self, node: ast.Assign) -> None:
                self.generic_visit(node)
                target = resolve(node.value)
                if relevant(target):
                    for item in node.targets:
                        if isinstance(item, ast.Name):
                            aliases[-1][item.id] = target

            def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
                self.generic_visit(node)
                target = resolve(node.annotation) if node.annotation else resolve(node.value)
                if isinstance(node.target, ast.Name) and relevant(target):
                    aliases[-1][node.target.id] = target

            def visit_Call(self, node: ast.Call) -> None:
                target = resolve(node.func)
                if relevant(target):
                    record(node, target, "call")
                self.generic_visit(node)

            def visit_Name(self, node: ast.Name) -> None:
                if node.id in functions | owner_types:
                    ast_terminals.add((relative, node.lineno, node.col_offset, node.id))
                if isinstance(node.ctx, ast.Load) and relevant(resolve(node)):
                    record(node, resolve(node), "reference")

            def visit_Attribute(self, node: ast.Attribute) -> None:
                if node.attr in functions | owner_types:
                    ast_terminals.add(
                        (relative, node.end_lineno, node.end_col_offset - len(node.attr), node.attr)
                    )
                if isinstance(node.ctx, ast.Load) and relevant(resolve(node)):
                    record(node, resolve(node), "reference")
                self.generic_visit(node)

        Walk().visit(tree)
        # Independent lexical reconciliation covers the literal target-token
        # population, with AST context used only to classify calls/aliases.
        for token in tokenize.generate_tokens(io.StringIO(source).readline):
            if token.type == tokenize.NAME and token.string in functions | owner_types:
                token_terminals.add((relative, *token.start, token.string))
        # Definitions/import tokens do not constitute load/store expressions.
        for node in ast.walk(tree):
            if (
                isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                and node.name in functions | owner_types
            ):
                line = source_lines[node.lineno - 1]
                start = line.index(node.name, node.col_offset)
                ast_terminals.add((relative, node.lineno, start, node.name))
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = (
                    set((node.module or "").split("."))
                    if isinstance(node, ast.ImportFrom)
                    else set()
                )
                for item in node.names:
                    names.update(item.name.split("."))
                    if item.asname:
                        names.add(item.asname)
                if names.intersection(functions | owner_types):
                    lines = source_lines[node.lineno - 1 : node.end_lineno]
                    lines[0] = lines[0][node.col_offset :]
                    lines[-1] = lines[-1][
                        : node.end_col_offset - (node.col_offset if len(lines) == 1 else 0)
                    ]
                    for token in tokenize.generate_tokens(io.StringIO("\n".join(lines)).readline):
                        if token.type == tokenize.NAME and token.string in functions | owner_types:
                            ast_terminals.add(
                                (
                                    relative,
                                    node.lineno + token.start[0] - 1,
                                    token.start[1]
                                    + (node.col_offset if token.start[0] == 1 else 0),
                                    token.string,
                                )
                            )

    for path in sorted(paths):
        scan(path)
    if ast_terminals != token_terminals:
        raise ValueError(
            "phase2_return_literal_identity_reconciliation_failed:"
            + repr(
                {
                    "only_ast": sorted(ast_terminals - token_terminals),
                    "only_token": sorted(token_terminals - ast_terminals),
                }
            )
        )
    changed = [
        relative
        for relative, value in snapshots.items()
        if "sha256:" + hashlib.sha256((repo_root / relative).read_bytes()).hexdigest() != value
    ]
    reread = {path for root in roots for path in (repo_root / root).rglob("*.py")}
    if changed or reread != paths:
        raise ValueError("phase2_return_caller_source_changed")
    return {
        "source_denominator": {
            "roots": list(roots),
            "file_type": "all current .py",
            "rglob": len(paths),
            "os_walk": len(independent),
        },
        "literal_identity_reconciliation": {
            "ast": len(ast_terminals),
            "tokenize": len(token_terminals),
        },
        "source_basis_hash": "sha256:"
        + hashlib.sha256(json.dumps(snapshots, sort_keys=True).encode()).hexdigest(),
        "references": sorted(
            references, key=lambda row: (row["path"], row["line"], row["column"], row["role"])
        ),
        "source_changed": [],
    }


def _phase2_return_fence_issues(basis: dict[str, Any]) -> list[dict[str, Any]]:
    issues = []
    engine_allowed = {
        (_RETURN_ENGINE + "protocol.py", "decode_node_outcome"),
        (_RETURN_ENGINE + "executor.py", "WorkflowExecutor.execute"),
        (_RETURN_ENGINE + "async_executor.py", "AsyncWorkflowExecutor._execute_node"),
        (
            "src/polisyos/runtime/quality/workspace/scientist_node_adapters.py",
            "_validated_node_outcome",
        ),
    }
    for row in basis["references"]:
        if not row["path"].startswith("src/"):
            continue
        terminal = row["target"].rsplit(".", 1)[-1]
        if terminal == "select_value_method_for_problem" and row["path"].startswith(
            "src/polisyos/runtime/quality/workspace/"
        ):
            issues.append({"code": "phase2_causal_n8_predecessor_reached", **row})
        if "ConstraintStoreIngestor.ingest" in row["target"]:
            issues.append({"code": "phase2_retired_constraint_ingress_reached", **row})
        if (
            row["target"].endswith("NodeOutcome.model_validate")
            and (row["path"], row["function"]) not in engine_allowed
        ):
            issues.append({"code": "phase2_unclassified_base_outcome_reconstruction", **row})
        if (
            row["role"] == "call"
            and row["target"].rsplit(".", 1)[-1] == "NodeOutcome"
            and row.get("star_keyword")
        ):
            issues.append({"code": "phase2_base_outcome_star_reconstruction", **row})
    expected = (
        (_RETURN_SCM, "augmented_synthetic_control", "_fit_scm_weights"),
        (_RETURN_SCM, "SyntheticControlMethod.pure_step", "_fit_scm_weights"),
        (_RETURN_LOOP, "_phase2_value_method_selection", "select_method_for_input_contract"),
        (_RETURN_LOOP, "WorkspaceLoop.run_intent", "ConstraintStoreIngestor.produce"),
        (_RETURN_LOOP, "WorkspaceLoop.run_intent", "ConstraintStoreIngestor.reconcile_method"),
        (_RETURN_LOOP, "_phase2_constraint_blockers", "evaluate_constraint_store_for_phase2"),
        (
            _RETURN_CONSTRAINT,
            "evaluate_constraint_store_for_phase2",
            "ConstraintStoreIngestor.require",
        ),
        (_RETURN_ENGINE + "idempotency.py", "NodeResultCache.get", "decode_node_outcome"),
        (_RETURN_ENGINE + "idempotency.py", "NodeResultCache.load_entry", "decode_node_outcome"),
        (_RETURN_ENGINE + "retry.py", "_execute_with_timeout_process", "decode_node_outcome"),
        (_RETURN_ENGINE + "retry.py", "_execute_with_timeout_process_async", "decode_node_outcome"),
        (_RETURN_ENGINE + "runner/serialization.py", "deserialize_outcome", "decode_node_outcome"),
    )
    for path, function, target in expected:
        if not any(
            row["path"] == path
            and row["function"] == function
            and row["role"] == "call"
            and row["target"].endswith(target)
            for row in basis["references"]
        ):
            issues.append(
                {
                    "code": "phase2_replacement_default_not_consulted",
                    "path": path,
                    "function": function,
                    "target": target,
                }
            )
    return issues


def _phase2_return_delta(repo_root: Path, path: str, name: str) -> dict[str, Any]:
    import difflib
    import subprocess

    original = subprocess.check_output(
        ["git", "show", f"{_RETURN_PREDECESSOR}:policy-engine/{path}"], cwd=repo_root, text=True
    )
    current = (repo_root / path).read_text()
    old, new = _return_function_nodes(original)[name], _return_function_nodes(current)[name]
    before, after = (
        original.splitlines()[old.lineno - 1 : old.end_lineno],
        current.splitlines()[new.lineno - 1 : new.end_lineno],
    )
    removed = sum(
        line.startswith("-") and not line.startswith("---")
        for line in difflib.unified_diff(before, after)
    )
    independent = sum(
        end - start
        for tag, start, end, _, _ in difflib.SequenceMatcher(a=before, b=after).get_opcodes()
        if tag in {"replace", "delete"}
    )
    if not removed or removed != independent:
        raise ValueError("phase2_return_predecessor_not_removed:" + name)
    return {
        "predecessor_ref": f"{path}@{_RETURN_PREDECESSOR}#{name}",
        "replacement_ref": f"{path}@sha256:{hashlib.sha256(current.encode()).hexdigest()}#{name}",
        "removed_loc": {"unified_diff": removed, "sequence_opcodes": independent},
    }


def _measure_scm_call_preservation(repo_root: Path) -> dict[str, Any]:
    """Reconcile the complete old/current numerical call-expression population."""
    import io
    import subprocess
    import tokenize
    from collections import Counter

    previous = subprocess.check_output(
        ["git", "show", f"{_RETURN_PREDECESSOR}:policy-engine/{_RETURN_SCM}"],
        cwd=repo_root,
        text=True,
    )
    current = (repo_root / _RETURN_SCM).read_text()

    def calls(source: str) -> Counter[tuple[str, str]]:
        result: Counter[tuple[str, str]] = Counter()
        scopes: list[str] = []

        class Walk(ast.NodeVisitor):
            def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
                scopes.append(node.name)
                self.generic_visit(node)
                scopes.pop()

            def visit_ClassDef(self, node: ast.ClassDef) -> None:
                scopes.append(node.name)
                self.generic_visit(node)
                scopes.pop()

            def visit_Call(self, node: ast.Call) -> None:
                if isinstance(node.func, ast.Name) and node.func.id == "_fit_scm_weights":
                    result[(".".join(scopes), ast.dump(node, include_attributes=False))] += 1
                self.generic_visit(node)

        Walk().visit(ast.parse(source))
        tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))
        independent = sum(
            token.type == tokenize.NAME
            and token.string == "_fit_scm_weights"
            and tokens[index + 1].string == "("
            and tokens[index - 1].string != "def"
            for index, token in enumerate(tokens)
        )
        if not result or result.total() != independent:
            raise ValueError("phase2_scm_numerical_call_population_unresolved")
        return result

    before, after = calls(previous), calls(current)
    if before != after:
        raise ValueError(
            "phase2_scm_numerical_call_population_changed:"
            + repr(
                {
                    "removed": list((before - after).elements()),
                    "added": list((after - before).elements()),
                }
            )
        )
    return {
        "preserved_owner_call_count": after.total(),
        "independent_token_call_count": after.total(),
        "call_expression_identity_delta": [],
        "meaning": "complete numerical owner call population preserved from the pinned predecessor; current targets use the sole verified helper",
    }


def _measure_current_scm_epoch(repo_root: Path) -> dict[str, Any]:
    """Read the real registered successor and exercise retired exact lookup."""
    from polisyos.foundry.methods import MethodNotFoundError, MethodRegistry
    from polisyos.foundry.methods.catalog.causal import ensure_causal_methods_registered
    from polisyos.foundry.methods.catalog.causal.synthetic_control import SyntheticControlMethod

    registry = MethodRegistry.get_instance()
    ensure_causal_methods_registered(registry)
    current = registry.get("causal.inference.synthetic_control@2.0.0")
    if (
        current is not SyntheticControlMethod
        or current.signature.fqn != "causal.inference.synthetic_control@2.0.0"
    ):
        raise ValueError("phase2_scm_current_registration_mismatch")
    try:
        registry.get("causal.inference.synthetic_control@1.0.0")
    except MethodNotFoundError:
        retired = "MethodNotFoundError"
    else:
        raise ValueError("phase2_scm_retired_epoch_still_registered")
    return {
        "current_method_fqn": current.signature.fqn,
        "current_signature_digest": current.signature.stable_digest(),
        "retired_method_fqn": "causal.inference.synthetic_control@1.0.0",
        "retired_lookup_outcome": retired,
        "predicate_class": "recomputed",
        "numerical_call_custody": _measure_scm_call_preservation(repo_root),
        "scope": "actual current registry lookup; numerical adequacy is separately exercised by native and actual recorded-consumer controls",
    }


def _measure_phase2_return_strangles(repo_root: Path) -> dict[str, Any]:
    """Emit current defaults/caller fences, bound to actual prior semantic removals."""
    basis = _phase2_return_caller_basis(repo_root)
    issues = _phase2_return_fence_issues(basis)
    if issues:
        raise ValueError("phase2_return_predecessor_unfenced:" + json.dumps(issues, sort_keys=True))
    ingress = _return_function_nodes((repo_root / _RETURN_CONSTRAINT).read_text())[
        "ConstraintStoreIngestor.ingest"
    ]
    executable = [
        node
        for node in ingress.body
        if not (
            isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        )
    ]
    if len(executable) != 1 or not isinstance(executable[0], ast.Raise):
        raise ValueError("phase2_retired_constraint_ingress_not_unconditionally_refused")
    scm_epoch = _measure_current_scm_epoch(repo_root)
    specifications = (
        (
            "c3-scm-numerical-solution",
            "GY-C3",
            "raw_objective_and_optimizer_success_flag",
            "single_v2_registration_common_objective_exact_convex_gap",
            [(_RETURN_SCM, "_fit_scm_weights")],
            ["c3/return/scm-solver-removal.json"],
        ),
        (
            "c1-causal-input-selection",
            "GY-C1",
            "n8_value_method_population",
            "input_contract_and_report_port_candidate_population",
            [(_RETURN_LOOP, "_phase2_value_method_selection")],
            ["c1/return/selector-route-removal.json"],
        ),
        (
            "c3-constraint-owner-admission",
            "GY-C3",
            "caller_status_or_resolved_reference",
            "complete_owner_basis_cas_recomputation_and_consumed_decision",
            [
                (_RETURN_CONSTRAINT, "ConstraintStoreIngestor.ingest"),
                (_RETURN_CONSTRAINT, "evaluate_constraint_store_for_phase2"),
            ],
            [
                "c3/return/constraints-decision-consumption-removal.json",
                "c3/return/constraints-method-reconciliation-removal.json",
                "c3/return/constraints-emission-content-removal.json",
            ],
        ),
        (
            "c1-output-aware-wire",
            "GY-C1",
            "base_outcome_reconstruction_drops_supplied_subtype",
            "strict_protocol_decoder_and_current_attempt_output_disposition",
            [
                (_RETURN_ENGINE + "idempotency.py", "NodeResultCache.get"),
                (_RETURN_ENGINE + "retry.py", "_execute_with_timeout_process"),
                (_RETURN_ENGINE + "retry.py", "_execute_with_timeout_process_async"),
                (_RETURN_ENGINE + "runner/serialization.py", "deserialize_outcome"),
            ],
            [
                "c3/return/output-current-emission-removal.json",
                "c3/return/output-wire-decoder-removal.json",
                "c3/return/output-cache-custody-removal.json",
            ],
        ),
    )
    receipts = []
    for identifier, task, before, after, paths, evidence in specifications:
        verification = []
        for relative in evidence:
            path = repo_root / (_RETURN_EVIDENCE + relative)
            raw = path.read_bytes()
            receipt = json.loads(raw)
            # These are retained prior semantic witnesses, not runtime
            # authority established by an exit code or nonempty stdout. Their
            # command disposition excludes a timeout or missing recorded output;
            # it does not establish which assertion failed. Actual current
            # proofs and reconciled native controls remain independent.
            if (
                receipt.get("returncode") != 1
                or receipt.get("timed_out") is not False
                or not receipt.get("stdout")
            ):
                raise ValueError("phase2_return_semantic_removal_receipt_invalid:" + relative)
            verification.append(
                {
                    "ref": f"{_RETURN_EVIDENCE}{relative}@sha256:{hashlib.sha256(raw).hexdigest()}",
                    "meaning": "retained_prior_semantic_removal_witness_not_current_runtime_authority",
                }
            )
        members = [_phase2_return_delta(repo_root, path, name) for path, name in paths]
        group = (
            "scm"
            if identifier == "c3-scm-numerical-solution"
            else "constraint"
            if task == "GY-C3"
            else "wire"
            if identifier == "c1-output-aware-wire"
            else "selector"
        )
        caller_indices = []
        for index, row in enumerate(basis["references"]):
            target = row["target"]
            caller_group = (
                "scm"
                if "SyntheticControlMethod" in target.split(".")
                or target.endswith(("_fit_scm_weights", "augmented_synthetic_control"))
                else "constraint"
                if (
                    "ConstraintStoreIngestor" in target
                    or target.endswith(
                        ("evaluate_constraint_store_for_phase2", "_phase2_constraint_blockers")
                    )
                )
                else "wire"
                if ("NodeOutcome" in target or target.endswith("decode_node_outcome"))
                else "selector"
            )
            if caller_group == group:
                caller_indices.append(index)
        receipts.append(
            {
                "receipt_id": "layer3-gy-" + identifier + "-strangle",
                "pattern_id": "P28",
                "task_id": task,
                "predecessor_ref": [member["predecessor_ref"] for member in members],
                "replacement_ref": [member["replacement_ref"] for member in members],
                "disposition": "fenced_default_flipped",
                "default_before": before,
                "default_after": after,
                "replaced_members": members,
                "removed_loc": {
                    "unified_diff": sum(
                        member["removed_loc"]["unified_diff"] for member in members
                    ),
                    "sequence_opcodes": sum(
                        member["removed_loc"]["sequence_opcodes"] for member in members
                    ),
                },
                "remaining_callers": [
                    f"#/caller_basis/references/{index}" for index in caller_indices
                ],
                "guard_ref": "_phase2_return_fence_issues; actual native route/readback/decoder controls",
                "remaining_callers_disposition": (
                    "Every enumerated SCM helper/class caller resolves the single current owner; explicit retired registry lookup refuses. No N8 authority or historical artifact is reissued here."
                    if group == "scm"
                    else "N8 value callers remain their unchanged owner; retired constraint ingress has no admitted caller; ordinary outcome construction/in-memory validation retains its original contract"
                ),
                "verified_by": verification,
                **({"method_epoch": scm_epoch} if group == "scm" else {}),
            }
        )
    # Keep the indexed complete basis intact: per-receipt caller pointers must
    # resolve to the exact enumerated identity after serialization.
    return {
        "schema_version": "policyos.gy.phase2.return_strangles.v1",
        "caller_basis": basis,
        "receipts": receipts,
        "semantic_basis": "current actual loop/CAS proof plus independently retained actual removal outputs; static tokens alone do not establish the property",
    }


def recompute_playbook_admission_strangle(repo_root: Path) -> dict[str, Any]:
    """Enumerate production constructor/raw-execution callers without git exclusions."""
    source_root = repo_root / "src"
    paths = set(source_root.rglob("*.py"))
    independent = {
        Path(directory) / filename
        for directory, _, filenames in os.walk(source_root)
        for filename in filenames
        if filename.endswith(".py")
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
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
            for alias in node.names
        }
        while True:
            previous = dict(aliases)
            for node in ast.walk(tree):
                if not isinstance(node, (ast.Assign, ast.AnnAssign)):
                    continue
                value = node.value
                target = (
                    value.attr
                    if isinstance(value, ast.Attribute)
                    else aliases.get(value.id, value.id)
                    if isinstance(value, ast.Name)
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
                callers.append(
                    {
                        "path": self.source_path,
                        "function": scope,
                        "line": node.lineno,
                        "column": node.col_offset,
                        "target": name,
                        "disposition": (
                            "verifier_smoke_only"
                            if name == "execute_candidate"
                            else "verified_admission_only"
                        )
                        if (self.source_path, scope) == allowed[name]
                        else "unfenced",
                    }
                )

            def visit_Attribute(self, node: ast.Attribute) -> None:
                # Fence the raw method reference itself; assigning it to a new
                # callable name must not create an uncounted sibling path.
                if node.attr == "execute_candidate" and isinstance(node.ctx, ast.Load):
                    self.record(node, node.attr)
                self.generic_visit(node)

            def visit_Call(self, node: ast.Call) -> None:
                name = (
                    node.func.attr
                    if isinstance(node.func, ast.Attribute)
                    else self.aliases.get(node.func.id, node.func.id)
                    if isinstance(node.func, ast.Name)
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
    registry_path = repo_root / "architecture/generated_artifacts.toml"
    try:
        generated = tomllib.loads(registry_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, tomllib.TOMLDecodeError) as exc:
        issues.append({"code": "phase2_generated_registry_unreadable", "error": str(exc)})
        generated = {}
    families = generated.get("family", [])
    if not isinstance(families, list) or any(not isinstance(item, dict) for item in families):
        issues.append({"code": "phase2_generated_registry_families_invalid"})
        families = []
    expected_families = (
        (FAMILY_ID, tuple(OUTPUTS), "generated_committed"),
        (HISTORY_FAMILY_ID, tuple(HISTORICAL_OUTPUTS_SHA256), "source_committed"),
    )
    owner_path = "tools/quality/validation/check_layer3_gy_phase2_artifacts.py"
    for family_id, expected_outputs, lifecycle in expected_families:
        matches = [item for item in families if item.get("id") == family_id]
        if not matches:
            code = (
                "phase2_generated_artifacts_family_missing"
                if family_id == FAMILY_ID
                else "phase2_history_family_missing"
            )
            issues.append({"code": code, "family": family_id})
        if len(matches) > 1:
            issues.append({"code": "phase2_family_id_duplicate", "family": family_id})
        for family in matches:
            raw_outputs = family.get("outputs")
            if not isinstance(raw_outputs, list) or any(
                not isinstance(path, str) for path in raw_outputs
            ):
                issues.append({"code": "phase2_family_outputs_invalid", "family": family_id})
                outputs = []
            else:
                outputs = raw_outputs
            for path in sorted(set(outputs)):
                if outputs.count(path) != 1:
                    issues.append(
                        {"code": "phase2_output_duplicate", "family": family_id, "path": path}
                    )
                if path not in expected_outputs:
                    issues.append(
                        {
                            "code": "phase2_output_outside_owned_epoch",
                            "family": family_id,
                            "path": path,
                        }
                    )
            for path in expected_outputs:
                if path not in outputs:
                    issues.append(
                        {"code": "phase2_output_not_registered", "family": family_id, "path": path}
                    )
            if family.get("lifecycle") != lifecycle:
                issues.append({"code": "phase2_family_lifecycle_invalid", "family": family_id})
            if family.get("stale_output_behavior") != "fail":
                issues.append({"code": "phase2_stale_output_not_fail_closed", "family": family_id})
            if family.get("workflow") != owner_path:
                issues.append({"code": "phase2_workflow_not_registered", "family": family_id})
            if family_id == HISTORY_FAMILY_ID and (
                family.get("source_integrity_sha256") != HISTORICAL_OUTPUTS_SHA256
            ):
                issues.append({"code": "phase2_history_integrity_declaration_invalid"})
        # Reconcile ownership against the complete registry, not only the two
        # matched blocks: a second family cannot silently claim these epochs.
        for path in expected_outputs:
            for family in families:
                outputs = family.get("outputs")
                if family.get("id") != family_id and isinstance(outputs, list) and path in outputs:
                    issues.append(
                        {
                            "code": "phase2_output_owner_conflict",
                            "path": path,
                            "family": str(family.get("id")),
                            "expected_family": family_id,
                        }
                    )
    # Historical custody is independently checked even if registration is
    # missing or malformed. The current --write path never reissues these bytes.
    for relative_path, expected_hash in HISTORICAL_OUTPUTS_SHA256.items():
        try:
            raw = (repo_root / relative_path).read_bytes()
        except FileNotFoundError:
            issues.append({"code": "phase2_history_artifact_missing", "path": relative_path})
            continue
        except OSError as exc:
            issues.append(
                {
                    "code": "phase2_history_artifact_unreadable",
                    "path": relative_path,
                    "error": str(exc),
                }
            )
            continue
        actual_hash = "sha256:" + hashlib.sha256(raw).hexdigest()
        if actual_hash != expected_hash:
            issues.append(
                {
                    "code": "phase2_history_artifact_changed",
                    "path": relative_path,
                    "expected_hash": expected_hash,
                    "actual_hash": actual_hash,
                }
            )


def _read_json(path: Path, issues: list[dict[str, str]]) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        issues.append({"code": "phase2_artifact_missing", "path": str(path)})
        return {}
    except json.JSONDecodeError as exc:
        issues.append(
            {"code": "phase2_artifact_invalid_json", "path": str(path), "error": str(exc)}
        )
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
