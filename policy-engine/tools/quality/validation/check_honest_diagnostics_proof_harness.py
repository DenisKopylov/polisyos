#!/usr/bin/env python3
"""Prove Honest Diagnostics production invariants have executable evidence."""

from __future__ import annotations

import argparse
import ast
import json
import sys
import tomllib
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tools.lib.fs import atomic_write_text
from tools.lib.imports import ensure_repo_import_roots

REPO_ROOT, _SRC_ROOT = ensure_repo_import_roots(__file__)

from polisyos.runtime.quality.invariants import (  # noqa: E402
    KNOWN_READINESS_CHECKS,
    MINIMUM_CLOSEOUT_GATES,
    REQUIRED_INVARIANT_FIELDS,
)

SCHEMA_VERSION = "policyos.honest_diagnostics_proof_harness.v1"
TOOL_NAME = "quality.validation.check-honest-diagnostics-proof-harness"

DEFAULT_INVARIANT_REGISTRY = Path("architecture/production_quality/invariant_registry.toml")
DEFAULT_EVENT_REGISTRY = Path("architecture/production_quality/diagnostic_event_types.toml")
DEFAULT_SOURCE_TRUTH_LATTICE = Path("architecture/production_quality/source_truth_lattice.toml")
DEFAULT_SCHEMA_COMPATIBILITY = Path("architecture/production_quality/schema_compatibility.toml")
DEFAULT_MODE_FALLBACK_POLICY = Path(
    "architecture/production_quality/mode_and_fallback_policy.toml"
)
DEFAULT_FITNESS_REGISTRY = Path(
    "architecture/production_quality/diagnostic_fitness_functions.toml"
)
DEFAULT_STATIC_INVENTORY = Path(
    "architecture/baselines/production_quality/evidence_inventory.json"
)
DEFAULT_SCORECARD_SOURCE = Path("src/polisyos/runtime/quality/scorecard.py")

RUNTIME_EVENT_AUTHORITY_ROLES = frozenset(
    {
        "runtime_authority",
        "producer_authority",
        "runtime_blocker",
        "authority_bearing",
        "runtime_consumer",
        "runtime_reconciliation",
        "projection_only",
    }
)
RUNTIME_PRODUCER_EVIDENCE_ROLES = RUNTIME_EVENT_AUTHORITY_ROLES - {"projection_only"}
PROHIBITED_PROOF_TYPES = frozenset(
    {
        "prose",
        "fixture_only_test",
        "static_inventory",
        "canary_generated_file",
        "dashboard_projection",
    }
)
MISSING_PROOF_CODES = {
    "runtime_event": "hds_proof_missing_runtime_event",
    "runtime_producer_evidence": "hds_proof_missing_runtime_producer_evidence",
    "cas_artifact_kind": "hds_proof_missing_cas_artifact_kind",
    "ref_key": "hds_proof_missing_ref_key",
    "bundle_packaging_file": "hds_proof_missing_bundle_packaging_file",
    "scorecard_gate": "hds_proof_missing_scorecard_gate",
    "readiness_check": "hds_proof_missing_readiness_check",
    "approval_public_policy": "hds_proof_missing_approval_public_policy",
    "dashboard_projection_policy": "hds_proof_missing_dashboard_projection_policy",
    "schema_compatibility": "hds_proof_missing_schema_compatibility",
    "mode_fallback_policy": "hds_proof_missing_mode_fallback_policy",
    "negative_test": "hds_proof_missing_negative_test",
    "next_diagnostic_command": "hds_proof_missing_next_diagnostic_command",
    "admissible_proof_source": "hds_proof_missing_admissible_source",
    "final_owner": "hds_proof_missing_final_owner",
    "producer_owner": "hds_proof_missing_producer_owner",
}


@dataclass(frozen=True)
class TestManifestEntry:
    nodeid: str
    path: str
    test_name: str
    markers: tuple[str, ...]
    source: str


@dataclass(frozen=True)
class ProofViolation:
    code: str
    proof_type: str
    invariant_id: str | None
    pql_id: str | None
    minimum_closeout_gate: str | None
    message: str
    evidence: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "proof_type": self.proof_type,
            "invariant_id": self.invariant_id,
            "pql_id": self.pql_id,
            "minimum_closeout_gate": self.minimum_closeout_gate,
            "message": self.message,
            "evidence": self.evidence,
        }


def build_proof_payload(
    *,
    repo_root: Path = REPO_ROOT,
    invariant_registry_path: Path = DEFAULT_INVARIANT_REGISTRY,
    event_registry_path: Path = DEFAULT_EVENT_REGISTRY,
    source_truth_lattice_path: Path = DEFAULT_SOURCE_TRUTH_LATTICE,
    schema_compatibility_path: Path = DEFAULT_SCHEMA_COMPATIBILITY,
    mode_fallback_policy_path: Path = DEFAULT_MODE_FALLBACK_POLICY,
    fitness_registry_path: Path = DEFAULT_FITNESS_REGISTRY,
    static_inventory_path: Path = DEFAULT_STATIC_INVENTORY,
    minimum_closeout_gates: Mapping[str, str] = MINIMUM_CLOSEOUT_GATES,
) -> dict[str, Any]:
    """Build a machine-readable proof report for HDS closeout invariants."""

    repo_root = repo_root.resolve()
    violations: list[ProofViolation] = []

    invariant_registry_file = _resolve(repo_root, invariant_registry_path)
    event_registry_file = _resolve(repo_root, event_registry_path)
    source_truth_file = _resolve(repo_root, source_truth_lattice_path)
    schema_file = _resolve(repo_root, schema_compatibility_path)
    mode_policy_file = _resolve(repo_root, mode_fallback_policy_path)
    fitness_file = _resolve(repo_root, fitness_registry_path)
    inventory_file = _resolve(repo_root, static_inventory_path)

    invariant_registry = _load_toml(
        invariant_registry_file,
        proof_type="invariant_registry",
        violations=violations,
    )
    event_registry = _load_toml(
        event_registry_file,
        proof_type="runtime_event_registry",
        violations=violations,
    )
    source_truth_lattice = _load_toml(
        source_truth_file,
        proof_type="source_truth_lattice",
        violations=violations,
    )
    schema_compatibility = _load_toml(
        schema_file,
        proof_type="schema_compatibility",
        violations=violations,
    )
    mode_fallback_policy = _load_toml(
        mode_policy_file,
        proof_type="mode_fallback_policy",
        violations=violations,
    )
    fitness_registry = _load_toml(
        fitness_file,
        proof_type="diagnostic_fitness_registry",
        violations=violations,
    )
    static_inventory = _load_json(
        inventory_file,
        proof_type="static_inventory",
        violations=violations,
    )
    test_manifest = discover_test_manifest(repo_root)

    invariants = _rows(invariant_registry, "invariants")
    invariant_minimum_closeout_gates = {
        _text(row.get("minimum_closeout_gate")) for row in invariants
    }
    for gate in sorted(set(minimum_closeout_gates) - invariant_minimum_closeout_gates):
        violations.append(
            ProofViolation(
                code="hds_proof_missing_invariant_registry_row",
                proof_type="invariant_registry",
                invariant_id=None,
                pql_id=None,
                minimum_closeout_gate=gate,
                message="Known Minimum Closeout Gate is missing from invariant registry.",
                evidence={"minimum_closeout_gate": gate},
            )
        )
    event_index = _event_index(event_registry)
    source_truth_ref_keys = _source_truth_ref_keys(source_truth_lattice)
    schema_contracts = _schema_contracts(schema_compatibility)
    fitness_rows = _rows(fitness_registry, "fitness_functions")
    fitness_by_invariant = _index_by_list(fitness_rows, "invariant_id")
    scorecard_gate_rows = _rows(fitness_registry, "scorecard_gates")
    scorecard_gate_map = _scorecard_gate_map(scorecard_gate_rows)
    scorecard_gate_names = discover_scorecard_gate_names(repo_root)
    readiness_check_names = set(KNOWN_READINESS_CHECKS)
    inventory_summary = _inventory_summary(static_inventory)

    invariant_ids = {_text(row.get("invariant_id")) for row in invariants}
    invariant_scorecard_gates = {
        gate
        for row in invariants
        for gate in _string_list(row.get("scorecard_gate_names"))
    }
    for gate_row in scorecard_gate_rows:
        gate_name = _text(gate_row.get("gate_name") or gate_row.get("name"))
        invariant_id = _text(gate_row.get("invariant_id"))
        if gate_name and (
            gate_name not in invariant_scorecard_gates or invariant_id not in invariant_ids
        ):
            violations.append(
                ProofViolation(
                    code="hds_orphan_scorecard_gate",
                    proof_type="scorecard_gate",
                    invariant_id=invariant_id or None,
                    pql_id=None,
                    minimum_closeout_gate=None,
                    message="Scorecard gate is declared without a matching invariant.",
                    evidence={"gate_name": gate_name},
                )
            )

    invariant_proofs: list[dict[str, Any]] = []
    for index, invariant in enumerate(invariants, start=1):
        proof, proof_violations = _prove_invariant(
            invariant=invariant,
            index=index,
            repo_root=repo_root,
            event_index=event_index,
            source_truth_ref_keys=source_truth_ref_keys,
            schema_contracts=schema_contracts,
            mode_fallback_policy=mode_fallback_policy,
            fitness_rows=fitness_by_invariant.get(_text(invariant.get("invariant_id")), []),
            scorecard_gate_map=scorecard_gate_map,
            scorecard_gate_names=scorecard_gate_names,
            readiness_check_names=readiness_check_names,
            test_manifest=test_manifest,
        )
        invariant_proofs.append(proof)
        violations.extend(proof_violations)

    status = "fail" if violations else "pass"
    return {
        "schema_version": SCHEMA_VERSION,
        "tool": TOOL_NAME,
        "status": status,
        "repo_root": str(repo_root),
        "source": {
            "invariant_registry": _rel(invariant_registry_file, repo_root),
            "diagnostic_event_types": _rel(event_registry_file, repo_root),
            "source_truth_lattice": _rel(source_truth_file, repo_root),
            "schema_compatibility": _rel(schema_file, repo_root),
            "mode_and_fallback_policy": _rel(mode_policy_file, repo_root),
            "diagnostic_fitness_functions": _rel(fitness_file, repo_root),
            "static_inventory": _rel(inventory_file, repo_root),
            "scorecard_source": _rel(repo_root / DEFAULT_SCORECARD_SOURCE, repo_root),
            "test_manifest_count": len(test_manifest),
        },
        "summary": {
            "status": status,
            "invariant_count": len(invariants),
            "known_minimum_closeout_gate_count": len(minimum_closeout_gates),
            "fitness_function_count": len(fitness_rows),
            "runtime_event_type_count": len(event_index),
            "scorecard_gate_count": len(scorecard_gate_rows),
            "actual_scorecard_gate_count": len(scorecard_gate_names),
            "readiness_check_count": len(readiness_check_names),
            "static_inventory_quality_report_count": inventory_summary[
                "quality_report_count"
            ],
            "violation_count": len(violations),
        },
        "invariant_proofs": invariant_proofs,
        "violations": [violation.as_dict() for violation in violations],
    }


def discover_test_manifest(repo_root: Path) -> dict[str, TestManifestEntry]:
    """Discover pytest tests under ``tests/**`` and return nodeid-indexed entries."""

    tests_root = repo_root / "tests"
    if not tests_root.exists():
        return {}
    manifest: dict[str, TestManifestEntry] = {}
    for path in sorted(tests_root.rglob("test_*.py")):
        source = path.read_text(encoding="utf-8")
        try:
            tree = ast.parse(source, filename=str(path))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            if not node.name.startswith("test_"):
                continue
            rel_path = _rel(path, repo_root)
            nodeid = f"{rel_path}::{node.name}"
            manifest[nodeid] = TestManifestEntry(
                nodeid=nodeid,
                path=rel_path,
                test_name=node.name,
                markers=_marker_names(node),
                source=ast.get_source_segment(source, node) or "",
            )
    return manifest


def discover_scorecard_gate_names(repo_root: Path) -> set[str]:
    """Discover scorecard gate names emitted by the runtime scorecard source."""

    path = repo_root / DEFAULT_SCORECARD_SOURCE
    if not path.exists():
        return set()
    source = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError:
        return set()

    gate_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and _decorator_name(node.func) == "_gate":
            gate_name = _keyword_string(node, "name")
            if gate_name:
                gate_names.add(gate_name)
            continue
        if isinstance(node, ast.Assign):
            target_names = _assignment_target_names(node.targets)
            if target_names & {"QUALITY_REPORT_GATE_METADATA", "report_gate_specs"}:
                gate_names.update(_gate_names_from_mapping_node(node.value))
            continue
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "update"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "report_gate_specs"
            and node.args
        ):
            gate_names.update(_gate_names_from_mapping_node(node.args[0]))
    return gate_names


def dump_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def render_text(payload: Mapping[str, Any]) -> str:
    lines = [
        f"{TOOL_NAME}: {payload['status']}",
        (
            "invariants={invariant_count} fitness={fitness_function_count} "
            "events={runtime_event_type_count} scorecard_gates={scorecard_gate_count} "
            "violations={violation_count}"
        ).format(**payload["summary"]),
    ]
    for violation in payload.get("violations", []):
        if not isinstance(violation, Mapping):
            continue
        invariant = violation.get("invariant_id") or "<global>"
        lines.append(
            "[fail] {invariant} {proof_type} {code}: {message}".format(
                invariant=invariant,
                proof_type=violation.get("proof_type"),
                code=violation.get("code"),
                message=violation.get("message"),
            )
        )
    return "\n".join(lines) + "\n"


def _prove_invariant(
    *,
    invariant: Mapping[str, Any],
    index: int,
    repo_root: Path,
    event_index: Mapping[str, Mapping[str, Any]],
    source_truth_ref_keys: set[str],
    schema_contracts: set[str],
    mode_fallback_policy: Mapping[str, Any],
    fitness_rows: Sequence[Mapping[str, Any]],
    scorecard_gate_map: Mapping[str, set[str]],
    scorecard_gate_names: set[str],
    readiness_check_names: set[str],
    test_manifest: Mapping[str, TestManifestEntry],
) -> tuple[dict[str, Any], list[ProofViolation]]:
    invariant_id = _text(invariant.get("invariant_id")) or f"invariants[{index}]"
    pql_id = _text(invariant.get("pql_id"))
    closeout_gate = _text(invariant.get("minimum_closeout_gate"))
    violations: list[ProofViolation] = []

    fitness_runtime_events = _union(fitness_rows, "runtime_events")
    fitness_artifact_kinds = _union(fitness_rows, "cas_artifact_kinds")
    fitness_ref_keys = _union(fitness_rows, "ref_keys")
    fitness_bundle_files = _union(fitness_rows, "bundle_packaging_files")
    fitness_scorecard_gates = _union(fitness_rows, "scorecard_gates")
    fitness_readiness_checks = _union(fitness_rows, "readiness_checks")
    fitness_approval_public_policies = _union(fitness_rows, "approval_public_policies")
    fitness_dashboard_policies = _union(fitness_rows, "dashboard_projection_policies")
    fitness_negative_tests = _union(fitness_rows, "negative_tests")
    fitness_next_commands = _union(fitness_rows, "next_diagnostic_commands")

    required_runtime_events = _string_list(invariant.get("runtime_event_names"))
    required_artifacts = _string_list(invariant.get("required_artifact_kinds"))
    required_ref_keys = _string_list(invariant.get("required_ref_keys"))
    required_scorecard_gates = _string_list(invariant.get("scorecard_gate_names"))
    required_schema_contracts = _string_list(invariant.get("required_schema_contracts"))
    negative_tests = _string_list(invariant.get("negative_tests"))
    readiness_check = _text(invariant.get("readiness_check"))
    approval_policy = _text(invariant.get("approval_policy"))
    public_policy = _text(invariant.get("public_artifact_policy"))
    dashboard_policy = _text(invariant.get("dashboard_projection_policy"))
    next_command = _text(invariant.get("next_diagnostic_command"))

    missing_registry_fields = sorted(REQUIRED_INVARIANT_FIELDS - set(invariant))
    if missing_registry_fields:
        violations.append(
            ProofViolation(
                code="hds_invariant_registry_field_missing",
                proof_type="invariant_registry_field",
                invariant_id=invariant_id,
                pql_id=pql_id or None,
                minimum_closeout_gate=closeout_gate or None,
                message="Invariant registry row is missing required machine-checkable fields.",
                evidence={"missing": missing_registry_fields},
            )
        )

    if not _text(invariant.get("final_owner")):
        violations.append(
            _missing(invariant, "final_owner", "Invariant must declare one final owner.")
        )
    if not _string_list(invariant.get("producer_owners")):
        violations.append(
            _missing(
                invariant,
                "producer_owner",
                "Invariant must declare at least one producer owner.",
            )
        )

    missing_events = [
        event_name
        for event_name in required_runtime_events
        if not _event_is_runtime_authority(event_index.get(event_name))
    ]
    if not required_runtime_events or missing_events:
        violations.append(
            _missing(
                invariant,
                "runtime_event",
                "Invariant runtime events must be registered runtime authority events.",
                missing=missing_events or required_runtime_events,
            )
        )
    elif not set(required_runtime_events) <= fitness_runtime_events:
        violations.append(
            _missing(
                invariant,
                "runtime_event",
                "Invariant runtime events must be mapped by a fitness function.",
                missing=sorted(set(required_runtime_events) - fitness_runtime_events),
            )
        )
    if required_scorecard_gates and not any(
        _event_is_runtime_producer_evidence(event_index.get(event_name))
        for event_name in required_runtime_events
    ):
        violations.append(
            _missing(
                invariant,
                "runtime_producer_evidence",
                (
                    "Scorecard gates cannot satisfy closeout without a runtime producer "
                    "or blocker event."
                ),
                missing=required_runtime_events,
            )
        )

    if not required_artifacts or not set(required_artifacts) <= fitness_artifact_kinds:
        violations.append(
            _missing(
                invariant,
                "cas_artifact_kind",
                "Invariant CAS artifact kinds must be mapped by a fitness function.",
                missing=sorted(set(required_artifacts) - fitness_artifact_kinds),
            )
        )

    ref_key_proofs = source_truth_ref_keys | fitness_ref_keys
    if not required_ref_keys or not set(required_ref_keys) <= ref_key_proofs:
        violations.append(
            _missing(
                invariant,
                "ref_key",
                "Invariant ref keys must be present in source-truth or fitness maps.",
                missing=sorted(set(required_ref_keys) - ref_key_proofs),
            )
        )

    valid_bundle_files = [
        file_path
        for file_path in fitness_bundle_files
        if _proof_source_kind(file_path) not in PROHIBITED_PROOF_TYPES
        and (repo_root / file_path).is_file()
    ]
    if not valid_bundle_files:
        violations.append(
            _missing(
                invariant,
                "bundle_packaging_file",
                "Invariant must name an existing non-generated bundle packaging source file.",
                missing=sorted(fitness_bundle_files),
            )
        )

    scorecard_registry_gates = {
        gate
        for gate, invariant_ids in scorecard_gate_map.items()
        if invariant_id in invariant_ids
    }
    missing_scorecard_gates = set(required_scorecard_gates) - (
        fitness_scorecard_gates & scorecard_registry_gates & scorecard_gate_names
    )
    if not required_scorecard_gates or missing_scorecard_gates:
        violations.append(
            _missing(
                invariant,
                "scorecard_gate",
                (
                    "Invariant scorecard gates must exist in scorecard code and map "
                    "through the fitness scorecard gate registry."
                ),
                missing=sorted(missing_scorecard_gates),
            )
        )

    if (
        not readiness_check
        or readiness_check not in readiness_check_names
        or readiness_check not in fitness_readiness_checks
    ):
        violations.append(
            _missing(
                invariant,
                "readiness_check",
                (
                    "Invariant readiness check must map to a known readiness check "
                    "and the fitness registry."
                ),
                missing=[readiness_check] if readiness_check else [],
            )
        )

    required_approval_public = {approval_policy, public_policy} - {""}
    if (
        not required_approval_public
        or not required_approval_public <= fitness_approval_public_policies
    ):
        violations.append(
            _missing(
                invariant,
                "approval_public_policy",
                "Invariant approval and public policies must be mapped by the fitness registry.",
                missing=sorted(required_approval_public - fitness_approval_public_policies),
            )
        )

    if not dashboard_policy or dashboard_policy not in fitness_dashboard_policies:
        violations.append(
            _missing(
                invariant,
                "dashboard_projection_policy",
                "Invariant dashboard projection policy must be mapped by the fitness registry.",
                missing=[dashboard_policy] if dashboard_policy else [],
            )
        )

    missing_schema_contracts = sorted(set(required_schema_contracts) - schema_contracts)
    if not required_schema_contracts or missing_schema_contracts:
        violations.append(
            _missing(
                invariant,
                "schema_compatibility",
                "Invariant schema contracts must be declared in schema compatibility.",
                missing=missing_schema_contracts or required_schema_contracts,
            )
        )

    if not _has_policy_rows(mode_fallback_policy):
        violations.append(
            _missing(
                invariant,
                "mode_fallback_policy",
                "Mode and fallback policy registry must contain closeout policy rows.",
            )
        )

    negative_test_proofs = set(negative_tests)
    if fitness_rows:
        negative_test_proofs &= fitness_negative_tests
    invalid_negative_tests = [
        ref
        for ref in sorted(negative_test_proofs)
        if ref not in test_manifest or _proof_source_kind(ref) in PROHIBITED_PROOF_TYPES
    ]
    if not negative_test_proofs or invalid_negative_tests:
        violations.append(
            _missing(
                invariant,
                "negative_test",
                "Invariant negative tests must point at discovered non-fixture pytest tests.",
                missing=invalid_negative_tests or sorted(negative_tests),
            )
        )

    if not next_command:
        violations.append(
            _missing(
                invariant,
                "next_diagnostic_command",
                "Invariant must declare a next diagnostic command.",
            )
        )
    elif fitness_rows and next_command not in fitness_next_commands:
        violations.append(
            _missing(
                invariant,
                "next_diagnostic_command",
                "Invariant next diagnostic command must be mapped by a fitness function.",
                missing=[next_command],
            )
        )

    proof_sources = _declared_proof_sources(fitness_rows, negative_tests)
    admissible_sources = [
        source
        for source in proof_sources
        if _proof_source_kind(source) not in PROHIBITED_PROOF_TYPES
        and _proof_source_exists(source, repo_root=repo_root, test_manifest=test_manifest)
    ]
    if not admissible_sources:
        violations.append(
            _missing(
                invariant,
                "admissible_proof_source",
                (
                    "Invariant proof cannot be only prose, fixtures, static inventory, "
                    "or canary output."
                ),
                missing=proof_sources,
            )
        )

    proof_status = "fail" if violations else "pass"
    return (
        {
            "invariant_id": invariant_id,
            "minimum_closeout_gate": closeout_gate,
            "pql_id": pql_id,
            "proof_status": proof_status,
            "final_owner": _text(invariant.get("final_owner")),
            "producer_owners": _string_list(invariant.get("producer_owners")),
            "runtime_events": required_runtime_events,
            "cas_artifact_kinds": required_artifacts,
            "ref_keys": required_ref_keys,
            "bundle_packaging_files": sorted(fitness_bundle_files),
            "scorecard_gates": required_scorecard_gates,
            "readiness_check": readiness_check,
            "approval_policy": approval_policy,
            "public_artifact_policy": public_policy,
            "dashboard_projection_policy": dashboard_policy,
            "negative_tests": sorted(negative_test_proofs or negative_tests),
            "next_diagnostic_command": next_command,
            "admissible_proof_sources": sorted(admissible_sources),
        },
        violations,
    )


def _missing(
    invariant: Mapping[str, Any],
    proof_type: str,
    message: str,
    *,
    missing: Sequence[str] | None = None,
) -> ProofViolation:
    evidence: dict[str, Any] = {}
    if missing is not None:
        evidence["missing"] = list(missing)
    return ProofViolation(
        code=MISSING_PROOF_CODES.get(
            proof_type,
            f"hds_proof_missing_{proof_type.replace('_', '-')}",
        ).replace("-", "_"),
        proof_type=proof_type,
        invariant_id=_text(invariant.get("invariant_id")) or None,
        pql_id=_text(invariant.get("pql_id")) or None,
        minimum_closeout_gate=_text(invariant.get("minimum_closeout_gate")) or None,
        message=message,
        evidence=evidence,
    )


def _load_toml(
    path: Path,
    *,
    proof_type: str,
    violations: list[ProofViolation],
) -> dict[str, Any]:
    try:
        with path.open("rb") as stream:
            payload = tomllib.load(stream)
    except FileNotFoundError:
        violations.append(
            ProofViolation(
                code="hds_registry_missing",
                proof_type=proof_type,
                invariant_id=None,
                pql_id=None,
                minimum_closeout_gate=None,
                message=f"Required HDS registry is missing: {path}",
                evidence={"path": str(path)},
            )
        )
        return {}
    except tomllib.TOMLDecodeError as exc:
        violations.append(
            ProofViolation(
                code="hds_registry_invalid",
                proof_type=proof_type,
                invariant_id=None,
                pql_id=None,
                minimum_closeout_gate=None,
                message=f"Required HDS registry is invalid TOML: {exc}",
                evidence={"path": str(path)},
            )
        )
        return {}
    return payload


def _load_json(
    path: Path,
    *,
    proof_type: str,
    violations: list[ProofViolation],
) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        violations.append(
            ProofViolation(
                code="hds_registry_missing",
                proof_type=proof_type,
                invariant_id=None,
                pql_id=None,
                minimum_closeout_gate=None,
                message=f"Required HDS static inventory is missing: {path}",
                evidence={"path": str(path)},
            )
        )
    except json.JSONDecodeError as exc:
        violations.append(
            ProofViolation(
                code="hds_registry_invalid",
                proof_type=proof_type,
                invariant_id=None,
                pql_id=None,
                minimum_closeout_gate=None,
                message=f"Required HDS static inventory is invalid JSON: {exc}",
                evidence={"path": str(path)},
            )
        )
    return {}


def _event_index(registry: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    events: dict[str, Mapping[str, Any]] = {}
    for row in _rows(registry, "event_types"):
        event_name = _text(
            row.get("name")
            or row.get("event_name")
            or row.get("event_type")
            or row.get("id")
        )
        if event_name:
            events[event_name] = row
    return events


def _event_is_runtime_authority(row: Mapping[str, Any] | None) -> bool:
    if not row:
        return False
    role = _text(row.get("authority_role") or row.get("role"))
    return not role or role in RUNTIME_EVENT_AUTHORITY_ROLES


def _event_is_runtime_producer_evidence(row: Mapping[str, Any] | None) -> bool:
    if not row:
        return False
    role = _text(row.get("authority_role") or row.get("role"))
    return not role or role in RUNTIME_PRODUCER_EVIDENCE_ROLES


def _source_truth_ref_keys(lattice: Mapping[str, Any]) -> set[str]:
    keys: set[str] = set()
    for row in _rows(lattice, "field_families"):
        keys.update(_string_list(row.get("required_ref_keys")))
        keys.update(_string_list(row.get("ref_keys")))
    return keys


def _schema_contracts(registry: Mapping[str, Any]) -> set[str]:
    contracts: set[str] = set()
    for table_name in ("schema_compatibility", "compatibility", "reader_ranges"):
        for row in _rows(registry, table_name):
            for key in (
                "schema_contract",
                "producer_schema",
                "schema_name",
                "schema_family",
            ):
                value = _text(row.get(key))
                if value:
                    contracts.add(value)
            contracts.update(_string_list(row.get("accepted_schema_contracts")))
    return contracts


def _inventory_summary(inventory: Mapping[str, Any]) -> dict[str, int]:
    return {"quality_report_count": len(_rows(inventory, "quality_reports"))}


def _rows(payload: Mapping[str, Any], name: str) -> list[Mapping[str, Any]]:
    rows = payload.get(name)
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, Mapping)]


def _index_by_list(
    rows: Iterable[Mapping[str, Any]],
    field: str,
) -> dict[str, list[Mapping[str, Any]]]:
    index: dict[str, list[Mapping[str, Any]]] = {}
    for row in rows:
        key = _text(row.get(field))
        if not key:
            continue
        index.setdefault(key, []).append(row)
    return index


def _scorecard_gate_map(rows: Iterable[Mapping[str, Any]]) -> dict[str, set[str]]:
    index: dict[str, set[str]] = {}
    for row in rows:
        gate = _text(row.get("gate_name") or row.get("name"))
        invariant_id = _text(row.get("invariant_id"))
        if gate and invariant_id:
            index.setdefault(gate, set()).add(invariant_id)
    return index


def _union(rows: Sequence[Mapping[str, Any]], field: str) -> set[str]:
    values: set[str] = set()
    for row in rows:
        values.update(_string_list(row.get(field)))
    return values


def _declared_proof_sources(
    fitness_rows: Sequence[Mapping[str, Any]],
    negative_tests: Sequence[str],
) -> list[str]:
    declared: list[str] = []
    for row in fitness_rows:
        if "proof_sources" in row:
            declared.extend(_string_list(row.get("proof_sources")))
    if declared:
        return sorted(set(declared))
    return sorted(set(negative_tests))


def _proof_source_exists(
    source: str,
    *,
    repo_root: Path,
    test_manifest: Mapping[str, TestManifestEntry],
) -> bool:
    if "::" in source:
        return source in test_manifest
    return (repo_root / source).exists()


def _proof_source_kind(source: str) -> str:
    path_text = source.split("::", 1)[0]
    normalized = path_text.replace("\\", "/")
    if normalized.endswith((".md", ".rst", ".txt")) or normalized.startswith("docs/"):
        return "prose"
    if normalized == DEFAULT_STATIC_INVENTORY.as_posix() or normalized.endswith(
        "/architecture/baselines/production_quality/evidence_inventory.json"
    ):
        return "static_inventory"
    if (
        normalized.startswith("tests/fixtures/")
        or "/tests/fixtures/" in normalized
        or "/fixtures/" in normalized
    ):
        return "fixture_only_test"
    if (
        normalized.startswith("_build/")
        or normalized.startswith(".polisyos/")
        or normalized.startswith("quality_evidence/")
        or "/quality_evidence/" in normalized
        or normalized.endswith("bundle.json")
    ):
        return "canary_generated_file"
    if normalized.startswith("apps/runtime-dashboard/"):
        return "dashboard_projection"
    return "executable_test_or_source"


def _has_policy_rows(payload: Mapping[str, Any]) -> bool:
    return any(isinstance(value, list) and value for value in payload.values())


def _keyword_string(node: ast.Call, keyword_name: str) -> str:
    for keyword in node.keywords:
        if keyword.arg == keyword_name and isinstance(keyword.value, ast.Constant):
            return _text(keyword.value.value)
    return ""


def _assignment_target_names(targets: Sequence[ast.expr]) -> set[str]:
    names: set[str] = set()
    for target in targets:
        if isinstance(target, ast.Name):
            names.add(target.id)
        elif isinstance(target, ast.Tuple | ast.List):
            names.update(_assignment_target_names(target.elts))
    return names


def _gate_names_from_mapping_node(node: ast.AST) -> set[str]:
    if not isinstance(node, ast.Dict):
        return set()
    gate_names: set[str] = set()
    for value in node.values:
        if not isinstance(value, ast.Tuple | ast.List) or not value.elts:
            continue
        first = value.elts[0]
        if isinstance(first, ast.Constant):
            gate_name = _text(first.value)
            if gate_name:
                gate_names.add(gate_name)
    return gate_names


def _marker_names(node: ast.FunctionDef | ast.AsyncFunctionDef) -> tuple[str, ...]:
    names: list[str] = []
    for decorator in node.decorator_list:
        name = _decorator_name(decorator)
        if name:
            names.append(name)
    return tuple(names)


def _decorator_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _decorator_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    if isinstance(node, ast.Call):
        return _decorator_name(node.func)
    return None


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def _text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _resolve(repo_root: Path, path: Path) -> Path:
    return path if path.is_absolute() else repo_root / path


def _rel(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--json-output", type=Path)
    parser.add_argument("--output-format", choices=("text", "json"), default="text")
    parser.add_argument("--require-passing", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    repo_root = args.repo_root.resolve()
    payload = build_proof_payload(repo_root=repo_root)
    rendered = dump_json(payload) if args.output_format == "json" else render_text(payload)
    if args.json_output is not None:
        atomic_write_text(_resolve(repo_root, args.json_output), dump_json(payload))
    else:
        sys.stdout.write(rendered)
    if payload["status"] != "pass":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
