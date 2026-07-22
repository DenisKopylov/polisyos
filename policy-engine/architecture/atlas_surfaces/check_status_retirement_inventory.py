#!/usr/bin/env python3
"""Validate the DS4 status-retirement inventory against live TypeScript."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import subprocess
import sys
from collections import Counter
from collections.abc import Mapping, Sequence
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

ATLAS_DIR = Path(__file__).resolve().parent
REPO_ROOT = ATLAS_DIR.parents[1]
INVENTORY_PATH = ATLAS_DIR / "status-retirement-inventory.json"
INVENTORY_SCHEMA_PATH = ATLAS_DIR / "status-retirement-inventory.schema.json"
WAIST_DEBT_PATH = ATLAS_DIR / "ds4-waist-debt-register.json"
WAIST_SCHEMA_PATH = ATLAS_DIR / "ds4-waist-debt-register.schema.json"
DS1_PATH = ATLAS_DIR / "live-application-readiness-ledger.json"
DS19_PATH = ATLAS_DIR / "frontend-disposition-register.json"
SCAN_PATH = ATLAS_DIR / "status_retirement_scan.mjs"

EXPECTED_CLASSIFICATIONS = {
    "lattice_derived": 15,
    "interaction_state": 24,
    "removed": 8,
}
EXPECTED_WAIST_TARGETS = {
    "ds4-waist-cache-age": "C09",
    "ds4-waist-decision-grade": "C14",
    "ds4-waist-cgf-disposition": "C19",
}


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _schema_errors(
    value: Mapping[str, Any], schema_path: Path, artifact_name: str
) -> list[str]:
    schema = _load_json(schema_path)
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors: list[str] = []
    for error in sorted(validator.iter_errors(value), key=lambda item: list(item.path)):
        location = ".".join(str(part) for part in error.path) or "root"
        errors.append(f"schema:{artifact_name}:{location}:{error.message}")
    return errors


@lru_cache(maxsize=32)
def _scan_json(request_json: str) -> dict[str, Any]:
    completed = subprocess.run(
        ["node", str(SCAN_PATH)],
        cwd=REPO_ROOT,
        input=request_json,
        capture_output=True,
        check=False,
        text=True,
    )
    if completed.returncode != 0:
        raise RuntimeError("status TypeScript scan failed: " + completed.stderr.strip())
    result = json.loads(completed.stdout)
    if not isinstance(result, dict):
        raise RuntimeError("status TypeScript scan returned a non-object")
    return result


def _scan(source_overrides: Mapping[str, str] | None = None) -> dict[str, Any]:
    request = (
        {"sourceOverrides": dict(sorted(source_overrides.items()))}
        if source_overrides is not None
        else {}
    )
    return _scan_json(json.dumps(request, sort_keys=True, separators=(",", ":")))


def _ds1_status_ids(ds1: Mapping[str, Any]) -> set[str]:
    return {
        entry["surface_id"]
        for entry in ds1["entries"]
        if entry["surface_id"].startswith("status-")
    }


def _entry_key_from_fact(fact: Mapping[str, Any]) -> tuple[Any, ...]:
    return (
        fact["kind"],
        fact["path"],
        fact["startLine"],
        fact.get("declarationName"),
        fact.get("fieldName"),
    )


def _entry_key(entry: Mapping[str, Any]) -> tuple[Any, ...]:
    span = entry["source_span"]
    return (
        entry["definition_kind"],
        span["path"],
        span["start_line"],
        span.get("declaration_name"),
        span.get("field_name"),
    )


def _semantic_key(entry: Mapping[str, Any]) -> tuple[Any, ...]:
    span = entry["source_span"]
    return (
        entry["definition_kind"],
        span["path"],
        span["start_line"],
        span.get("declaration_name"),
        span.get("field_name"),
    )


def _definition_identity(entry: Mapping[str, Any]) -> tuple[Any, ...]:
    """Identify an authored definition independently of line-number movement."""
    span = entry["source_span"]
    return (
        entry["definition_kind"],
        span["path"],
        span.get("declaration_name"),
        span.get("field_name"),
    )


def _fact_identity(fact: Mapping[str, Any]) -> tuple[Any, ...]:
    return (
        fact["kind"],
        fact["path"],
        fact.get("declarationName"),
        fact.get("fieldName"),
    )


def _semantic_name(fact: Mapping[str, Any]) -> str:
    return str(fact.get("declarationName") or fact.get("fieldName") or "unknown")


def _consumer_set(consumers: Sequence[Mapping[str, Any]]) -> set[tuple[Any, ...]]:
    return {(item["path"], item["line"], item["kind"]) for item in consumers}


def _validate_sources(inventory: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    source_specs = [
        (inventory["sources"]["ds1"]["path"], inventory["sources"]["ds1"]["sha256"]),
        (inventory["sources"]["ds19"]["path"], inventory["sources"]["ds19"]["sha256"]),
        (
            inventory["sources"]["generated_client"]["canonical_path"],
            inventory["sources"]["generated_client"]["canonical_sha256"],
        ),
        (
            inventory["sources"]["generated_client"]["types_path"],
            inventory["sources"]["generated_client"]["types_sha256"],
        ),
    ]
    for relative, expected_hash in source_specs:
        path = REPO_ROOT / relative
        if not path.exists():
            errors.append(f"inventory_source_missing:{relative}")
        elif _sha256(path) != expected_hash:
            errors.append(f"inventory_source_hash_drift:{relative}")
    return errors


def _validate_ds1_ds19_joins(
    inventory: Mapping[str, Any], ds1: Mapping[str, Any], ds19: Mapping[str, Any]
) -> list[str]:
    errors: list[str] = []
    expected = _ds1_status_ids(ds1)
    ids = [entry["unit_id"] for entry in inventory["entries"]]
    counts = Counter(ids)
    for unit_id, count in sorted(counts.items()):
        if count > 1:
            errors.append(f"ds1_status_join_duplicate:{unit_id}:{count}")
    for unit_id in sorted(expected - set(ids)):
        errors.append(f"ds1_status_join_missing:{unit_id}")
    for unit_id in sorted(set(ids) - expected):
        errors.append(f"ds1_status_join_unknown:{unit_id}")

    register_ids = {
        entry["unit_id"]
        for entry in ds19["entries"]
        if entry["unit_id"].startswith("status-")
    }
    if register_ids != expected:
        errors.append("ds19_status_join_drift")
    collaboration = next(
        (
            entry
            for entry in ds19["entries"]
            if entry["unit_id"] == "status-collaboration-session"
        ),
        None,
    )
    if not collaboration or (
        collaboration["disposition"] != "deleted"
        or collaboration["strangle_status"] != "strangled"
    ):
        errors.append("collaboration_ds19_terminal_receipt_drift")
    return errors


def _validate_denominators(inventory: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    entries = inventory["entries"]
    named = sum(
        entry["definition_kind"] == "named"
        for entry in entries
    ) + sum(entry["definition_kind"] == "deleted" for entry in entries)
    inline = sum(entry["definition_kind"] == "inline" for entry in entries)
    current_named = sum(
        entry["definition_kind"] == "named"
        and entry["current_definition_state"] == "present"
        for entry in entries
    )
    current_inline = sum(
        entry["definition_kind"] == "inline"
        and entry["current_definition_state"] == "present"
        for entry in entries
    )
    deleted = sum(
        entry["current_definition_state"] == "deleted" for entry in entries
    )
    retired = sum(
        entry["current_definition_state"] == "retired" for entry in entries
    )
    actual = {
        "ds1_rows": len(entries),
        "ds1_named": named,
        "ds1_inline": inline,
        "current_named": current_named,
        "current_inline": current_inline,
        "current_total": current_named + current_inline,
        "retired_definitions": retired,
        "already_deleted": deleted,
    }
    if inventory["denominators"] != actual:
        errors.append("current_denominator_drift")
    classifications = Counter(entry["classification"] for entry in entries)
    if dict(classifications) != EXPECTED_CLASSIFICATIONS:
        errors.append(
            "classification_denominator_drift:"
            + json.dumps(dict(sorted(classifications.items())), sort_keys=True)
        )
    return errors


def _validate_generated_anchors(inventory: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    canonical_path = REPO_ROOT / inventory["sources"]["generated_client"]["canonical_path"]
    types_path = REPO_ROOT / inventory["sources"]["generated_client"]["types_path"]
    canonical_lines = canonical_path.read_text(encoding="utf-8").splitlines()
    type_lines = types_path.read_text(encoding="utf-8").splitlines()
    for entry in inventory["entries"]:
        if entry["classification"] != "lattice_derived":
            continue
        unit_id = entry["unit_id"]
        anchor = entry["generated_anchor"]
        symbol = anchor["export_symbol"]
        canonical_line = anchor["canonical_line"]
        schema_line = anchor["schema_line"]
        field = anchor.get("field")
        expected_query = f'{symbol}["{field}"]' if field else symbol
        if entry["owner_type"].get("query") != expected_query:
            errors.append(f"generated_query_drift:{unit_id}")
        source_path = REPO_ROOT / entry["source_span"]["path"]
        if (
            '["' in entry.get("type_expression", "")
            and "@polisyos/runtime-api-client"
            in source_path.read_text(encoding="utf-8")
        ):
            source_query = _resolve_local_generated_query(entry)
            if source_query != expected_query:
                errors.append(f"generated_source_binding_drift:{unit_id}")
        if not (1 <= canonical_line <= len(canonical_lines)) or (
            f"export type {symbol}" not in canonical_lines[canonical_line - 1]
        ):
            errors.append(f"generated_anchor_drift:{unit_id}")
            continue
        expected_schema_fragment = f"{field}:" if field else f"{symbol}:"
        if not (1 <= schema_line <= len(type_lines)) or (
            expected_schema_fragment not in type_lines[schema_line - 1]
        ):
            errors.append(f"generated_anchor_drift:{unit_id}")
    return errors


def _resolve_local_generated_query(entry: Mapping[str, Any]) -> str | None:
    """Resolve a local indexed alias back to its generated-client export."""
    expression = str(entry.get("type_expression", "")).strip()
    indexed = re.fullmatch(r'([A-Za-z_$][\w$]*)\["([^"\n]+)"\]', expression)
    if indexed is None:
        return None
    base, field = indexed.groups()
    source_path = REPO_ROOT / entry["source_span"]["path"]
    source = source_path.read_text(encoding="utf-8")

    generated_imports: dict[str, str] = {}
    for match in re.finditer(
        r'import\s+type\s*\{(?P<body>.*?)\}\s*from\s*'
        r'["\']@polisyos/runtime-api-client["\']\s*;',
        source,
        flags=re.DOTALL,
    ):
        for raw_item in match.group("body").split(","):
            item = raw_item.strip()
            if not item:
                continue
            parts = re.fullmatch(
                r'([A-Za-z_$][\w$]*)(?:\s+as\s+([A-Za-z_$][\w$]*))?',
                item,
            )
            if parts is None:
                continue
            symbol, alias = parts.groups()
            generated_imports[alias or symbol] = symbol

    local_aliases = {
        alias: target
        for alias, target in re.findall(
            r'export\s+type\s+([A-Za-z_$][\w$]*)\s*=\s*'
            r'([A-Za-z_$][\w$]*)\s*;',
            source,
        )
    }
    visited: set[str] = set()
    while base in local_aliases and base not in visited:
        visited.add(base)
        base = local_aliases[base]
    symbol = generated_imports.get(base)
    return f'{symbol}["{field}"]' if symbol else None


def _validate_refs_and_removals(inventory: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    for entry in inventory["entries"]:
        unit_id = entry["unit_id"]
        for reference in entry["verification_refs"]:
            relative = reference.split("#", 1)[0].split(":", 1)[0]
            if not (REPO_ROOT / relative).exists():
                errors.append(f"verification_ref_missing:{unit_id}:{reference}")
        if entry["classification"] == "interaction_state":
            reference = entry.get("authority_slot_barrier_ref", "")
            if not reference or not (
                REPO_ROOT / reference.split("#", 1)[0]
            ).exists():
                errors.append(f"authority_slot_barrier_ref_missing:{unit_id}")
        if entry["current_definition_state"] != "deleted":
            continue
        source_path = REPO_ROOT / entry["source_span"]["path"]
        if source_path.exists():
            errors.append(f"removed_source_survives:{unit_id}")
        evidence = entry.get("removal_evidence", {})
        if all(key in evidence for key in ("pre_deletion_commit", "git_blob")):
            git_ref = (
                f'{evidence["pre_deletion_commit"]}:policy-engine/'
                f'{entry["source_span"]["path"]}'
            )
            completed = subprocess.run(
                ["git", "rev-parse", git_ref],
                cwd=REPO_ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
            if completed.returncode != 0 or completed.stdout.strip() != evidence["git_blob"]:
                errors.append(f"removal_blob_drift:{unit_id}")
    return errors


def _validate_live_scan(
    inventory: Mapping[str, Any], scan: Mapping[str, Any] | None = None
) -> list[str]:
    errors: list[str] = []
    if scan is None:
        scan = _scan()
    facts = {_entry_key_from_fact(fact): fact for fact in scan["definitions"]}
    present_entries = {
        _entry_key(entry): entry
        for entry in inventory["entries"]
        if entry["current_definition_state"] == "present"
    }
    retired_entries = {
        _definition_identity(entry): entry
        for entry in inventory["entries"]
        if entry["current_definition_state"] == "retired"
    }
    retired_fact_keys = {
        key
        for key, fact in facts.items()
        if _fact_identity(fact) in retired_entries
    }
    for key in sorted(retired_fact_keys, key=str):
        entry = retired_entries[_fact_identity(facts[key])]
        errors.append(f"retired_status_definition_survives:{entry['unit_id']}")
    for key in sorted(
        set(facts) - set(present_entries) - retired_fact_keys,
        key=str,
    ):
        fact = facts[key]
        name = fact.get("declarationName") or fact.get("fieldName") or "unknown"
        errors.append(
            f'unregistered_status_definition:{Path(fact["path"]).name}:{name}'
        )
    for key in sorted(set(present_entries) - set(facts), key=str):
        errors.append(f"registered_status_definition_missing:{present_entries[key]['unit_id']}")
    for key in sorted(set(facts) & set(present_entries), key=str):
        fact = facts[key]
        entry = present_entries[key]
        unit_id = entry["unit_id"]
        if fact["members"] != entry["literal_members"]:
            errors.append(f"status_literal_members_drift:{unit_id}")
        if fact["typeExpression"] != entry["type_expression"]:
            errors.append(f"status_type_expression_drift:{unit_id}")
        if _consumer_set(fact["consumers"]) != _consumer_set(entry["consumers"]):
            errors.append(f"status_consumers_drift:{unit_id}")

    named = sum(fact["kind"] == "named" for fact in facts.values())
    inline = sum(fact["kind"] == "inline" for fact in facts.values())
    denominators = inventory["denominators"]
    if (named, inline, named + inline) != (
        denominators["current_named"],
        denominators["current_inline"],
        denominators["current_total"],
    ):
        errors.append("live_status_denominator_drift")
    for leak in scan.get("interactionLeaks", []):
        errors.append(
            "interaction_state_reaches_authority_slot:"
            + Path(leak["path"]).name
        )
    errors.extend(_validate_semantic_candidates(inventory, scan))
    return errors


def _validate_semantic_candidates(
    inventory: Mapping[str, Any], scan: Mapping[str, Any] | None = None
) -> list[str]:
    """Reconcile semantic unions outside the immutable DS1 status denominator."""
    errors: list[str] = []
    if scan is None:
        scan = _scan()

    status_keys = {
        _entry_key_from_fact(fact) for fact in scan.get("definitions", [])
    }
    candidates = {
        _entry_key_from_fact(fact): fact
        for fact in scan.get("authorityCandidates", [])
        if _entry_key_from_fact(fact) not in status_keys
    }
    registered_rows = inventory.get("semantic_exemptions", [])
    if not isinstance(registered_rows, list):
        return ["semantic_exemptions_invalid"]

    registered: dict[tuple[Any, ...], Mapping[str, Any]] = {}
    retired: dict[tuple[Any, ...], Mapping[str, Any]] = {}
    candidate_ids: Counter[str] = Counter()
    for row in registered_rows:
        if not isinstance(row, Mapping):
            errors.append("semantic_exemption_invalid")
            continue
        candidate_id = str(row.get("candidate_id", "unknown"))
        candidate_ids[candidate_id] += 1
        try:
            key = _semantic_key(row)
        except (KeyError, TypeError):
            errors.append(f"semantic_exemption_invalid:{candidate_id}")
            continue
        state = row.get("current_definition_state")
        target = retired if state == "retired" else registered
        if key in registered or key in retired:
            errors.append(f"semantic_definition_join_duplicate:{candidate_id}")
        target[key] = row
        if row.get("does_not_change_ds1_denominator") is not True:
            errors.append(f"semantic_denominator_barrier_missing:{candidate_id}")

    for candidate_id, count in sorted(candidate_ids.items()):
        if count > 1:
            errors.append(f"semantic_candidate_id_duplicate:{candidate_id}:{count}")

    retired_identities = {
        _definition_identity(row): row for row in retired.values()
    }
    retired_candidate_keys = {
        key
        for key, fact in candidates.items()
        if _fact_identity(fact) in retired_identities
    }
    for key in sorted(retired_candidate_keys, key=str):
        row = retired_identities[_fact_identity(candidates[key])]
        errors.append(
            "retired_semantic_definition_survives:"
            + str(row.get("candidate_id", "unknown"))
        )
    for key in sorted(
        set(candidates) - set(registered) - retired_candidate_keys,
        key=str,
    ):
        errors.append(
            f"unregistered_semantic_definition:{_semantic_name(candidates[key])}"
        )
    for key in sorted(set(registered) - set(candidates), key=str):
        errors.append(
            "registered_semantic_definition_missing:"
            + str(registered[key].get("candidate_id", "unknown"))
        )
    for key in sorted(set(candidates) & set(registered), key=str):
        fact = candidates[key]
        row = registered[key]
        candidate_id = str(row.get("candidate_id", "unknown"))
        span = row.get("source_span", {})
        if span.get("end_line") != fact.get("endLine"):
            errors.append(f"semantic_source_span_drift:{candidate_id}")
        if row.get("literal_members") != fact.get("members"):
            errors.append(f"semantic_literal_members_drift:{candidate_id}")
        if row.get("type_expression") != fact.get("typeExpression"):
            errors.append(f"semantic_type_expression_drift:{candidate_id}")
    return errors


def _validate_source_overrides(
    inventory: Mapping[str, Any], source_overrides: Mapping[str, str]
) -> list[str]:
    errors: list[str] = []
    scan = _scan(source_overrides)
    definition_identities = {
        _fact_identity(fact) for fact in scan.get("definitions", [])
    }
    protected_sets = {
        tuple(sorted(entry["literal_members"]))
        for entry in inventory["entries"]
        if entry["classification"] == "lattice_derived"
        and entry["literal_members"]
    }
    for fact in scan.get("definitions", []):
        file_name = Path(fact["path"]).name
        if fact["kind"] == "inline":
            errors.append(
                f'unregistered_status_definition:{file_name}:{fact.get("fieldName", "unknown")}'
            )
            continue
        name = fact.get("declarationName", "unknown")
        if tuple(sorted(fact.get("members", []))) in protected_sets:
            errors.append(f"local_authority_restatement:{name}")
        else:
            errors.append(f"unregistered_status_definition:{file_name}:{name}")
    for fact in scan.get("authorityCandidates", []):
        if _fact_identity(fact) in definition_identities:
            continue
        errors.append(f"unregistered_semantic_definition:{_semantic_name(fact)}")
    for leak in scan.get("interactionLeaks", []):
        errors.append(
            f'interaction_state_reaches_authority_slot:{Path(leak["path"]).name}'
        )
    return errors


def _validate_waist_debt(debt: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    entries = debt.get("entries", [])
    if len(entries) != 3:
        errors.append(f"waist_debt_count:{len(entries)}")
    ids = [entry.get("debt_id") for entry in entries]
    if set(ids) != set(EXPECTED_WAIST_TARGETS) or len(ids) != len(set(ids)):
        errors.append("waist_debt_identity_drift")
    for entry in entries:
        debt_id = entry.get("debt_id", "unknown")
        if entry.get("owner") != "DS5 waist" or entry.get("owner_slice") != "DS5":
            errors.append(f"waist_debt_owner:{debt_id}")
        if EXPECTED_WAIST_TARGETS.get(debt_id) != entry.get("target_cluster"):
            errors.append(f"waist_debt_target:{debt_id}")
        if entry.get("capability_states") != ["bridge_missing", "surface_missing"]:
            errors.append(f"waist_debt_states:{debt_id}")
        anchor = entry.get("generated_client_anchor", {})
        canonical = REPO_ROOT / anchor.get("canonical_path", "missing")
        types = REPO_ROOT / anchor.get("types_path", "missing")
        if not canonical.exists() or not types.exists():
            errors.append(f"waist_debt_anchor_missing:{debt_id}")
            continue
        canonical_text = canonical.read_text(encoding="utf-8")
        types_text = types.read_text(encoding="utf-8")
        symbol = anchor.get("symbol", "")
        if anchor.get("anchor_kind") == "missing_export":
            if symbol in canonical_text or symbol in types_text:
                errors.append(f"waist_debt_missing_export_now_present:{debt_id}")
        elif anchor.get("anchor_kind") == "present_projection":
            canonical_lines = canonical_text.splitlines()
            start = anchor.get("types_start_line", 0)
            end = anchor.get("types_end_line", 0)
            type_block = "\n".join(types_text.splitlines()[max(0, start - 1):end])
            line = anchor.get("canonical_line", 0)
            if (
                not (1 <= line <= len(canonical_lines))
                or f"export type {symbol}" not in canonical_lines[line - 1]
                or symbol not in type_block
            ):
                errors.append(f"waist_debt_anchor_drift:{debt_id}")
    return errors


def validate_inventory(
    inventory: Mapping[str, Any],
    debt: Mapping[str, Any],
    *,
    source_overrides: Mapping[str, str] | None = None,
    live_probes: bool = True,
) -> list[str]:
    """Return deterministic errors for artifact, source, and authority drift."""
    errors = [
        *_schema_errors(inventory, INVENTORY_SCHEMA_PATH, "status-retirement-inventory"),
        *_schema_errors(debt, WAIST_SCHEMA_PATH, "ds4-waist-debt-register"),
    ]
    # Preserve class-level diagnostics even when an outer cardinality/const schema
    # check also fails; deeper validators run only once the strict shapes hold.
    if errors:
        if isinstance(inventory.get("entries"), list):
            errors.extend(
                _validate_ds1_ds19_joins(
                    inventory, _load_json(DS1_PATH), _load_json(DS19_PATH)
                )
            )
        if isinstance(debt.get("entries"), list):
            errors.extend(_validate_waist_debt(debt))
        if isinstance(inventory.get("semantic_exemptions"), list) and live_probes:
            errors.extend(_validate_semantic_candidates(inventory))
        return sorted(set(errors))
    ds1 = _load_json(DS1_PATH)
    ds19 = _load_json(DS19_PATH)
    errors.extend(_validate_sources(inventory))
    errors.extend(_validate_ds1_ds19_joins(inventory, ds1, ds19))
    errors.extend(_validate_denominators(inventory))
    errors.extend(_validate_generated_anchors(inventory))
    errors.extend(_validate_refs_and_removals(inventory))
    errors.extend(_validate_waist_debt(debt))
    if live_probes:
        errors.extend(_validate_live_scan(inventory))
    if source_overrides is not None:
        errors.extend(_validate_source_overrides(inventory, source_overrides))
    return sorted(set(errors))


def _corruption_probes(
    inventory: Mapping[str, Any], debt: Mapping[str, Any]
) -> list[str]:
    escaped: list[str] = []
    probes = {
        "renamed-authority-union": (
            {
                "apps/runtime-dashboard/src/shared/lib/domain/probe.ts": (
                    'export type EvidencePosture = "none" | "disputed" '
                    '| "under_review" | "resolved";\n'
                )
            },
            "local_authority_restatement:EvidencePosture",
        ),
        "inline-authority-synonym": (
            {
                "apps/runtime-dashboard/src/shared/lib/domain/probe.ts": (
                    'export interface Probe { verdict: "approved" | "rejected"; }\n'
                )
            },
            "unregistered_status_definition:probe.ts:verdict",
        ),
        "present-but-fake-import": (
            {
                "apps/runtime-dashboard/src/shared/lib/domain/probe.ts": (
                    'import type { VerificationMetadata } from "@polisyos/runtime-api-client";\n'
                    'export type LocalDispute = "none" | "disputed" '
                    '| "under_review" | "resolved";\n'
                    'export type Marker = VerificationMetadata["dispute_status"];\n'
                )
            },
            "local_authority_restatement:LocalDispute",
        ),
        "sibling-interaction-consumer": (
            {
                "apps/runtime-dashboard/src/shared/lib/domain/probe.ts": (
                    "import { createInteractionState, presentAuthority } "
                    'from "./statusOwnership";\n'
                    'const transport = createInteractionState("ready", "transport");\n'
                    'presentAuthority(transport);\n'
                )
            },
            "interaction_state_reaches_authority_slot:probe.ts",
        ),
        "nullable-semantic-union": (
            {
                "apps/runtime-dashboard/src/shared/lib/domain/probe.ts": (
                    'export type DecisionGrade = "pass" | "fail" | null;\n'
                )
            },
            "unregistered_status_definition:probe.ts:DecisionGrade",
        ),
        "as-const-semantic-vocabulary": (
            {
                "apps/runtime-dashboard/src/shared/lib/domain/probe.ts": (
                    "export const DecisionGradeVocabulary = "
                    '["pass", "fail"] as const;\n'
                )
            },
            "unregistered_semantic_definition:DecisionGradeVocabulary",
        ),
        "aliased-interaction-consumer": (
            {
                "apps/runtime-dashboard/src/shared/lib/domain/probe.ts": (
                    "import { createInteractionState as makeInteraction, "
                    "presentAuthority as showAuthority } "
                    'from "./statusOwnership";\n'
                    'const transport = makeInteraction("ready", "transport");\n'
                    "showAuthority(transport);\n"
                )
            },
            "interaction_state_reaches_authority_slot:probe.ts",
        ),
        "helper-return-interaction-consumer": (
            {
                "apps/runtime-dashboard/src/shared/lib/domain/probe.ts": (
                    "import { createInteractionState, presentAuthority } "
                    'from "./statusOwnership";\n'
                    "function interactionForAuthority() {\n"
                    '  return createInteractionState("ready", "transport");\n'
                    "}\n"
                    "presentAuthority(interactionForAuthority());\n"
                )
            },
            "interaction_state_reaches_authority_slot:probe.ts",
        ),
    }
    for name, (sources, expected) in probes.items():
        errors = validate_inventory(
            inventory, debt, source_overrides=sources, live_probes=False
        )
        if expected not in errors:
            escaped.append(name)

    missing = copy.deepcopy(inventory)
    missing["entries"].pop()
    if not any(
        error.startswith("ds1_status_join_missing:")
        for error in validate_inventory(missing, debt, live_probes=False)
    ):
        escaped.append("missing-ds1-join")
    fourth = copy.deepcopy(debt)
    fourth["entries"].append(copy.deepcopy(fourth["entries"][0]))
    fourth["entries"][-1]["debt_id"] = "ds4-waist-fourth-probe"
    if "waist_debt_count:4" not in validate_inventory(
        inventory, fourth, live_probes=False
    ):
        escaped.append("fourth-waist-row")
    return escaped


def _summary(inventory: Mapping[str, Any], debt: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "classifications": dict(
            sorted(Counter(entry["classification"] for entry in inventory["entries"]).items())
        ),
        "current_authored": inventory["denominators"]["current_total"],
        "ds1_rows": inventory["denominators"]["ds1_rows"],
        "semantic_exemptions": len(inventory["semantic_exemptions"]),
        "semantic_retirement_debt": sum(
            row["disposition"] == "retirement_debt"
            and row["current_definition_state"] == "present"
            for row in inventory["semantic_exemptions"]
        ),
        "waist_debt_rows": len(debt["entries"]),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--corruption-probes", action="store_true")
    args = parser.parse_args(argv)
    inventory = _load_json(INVENTORY_PATH)
    debt = _load_json(WAIST_DEBT_PATH)
    errors = validate_inventory(inventory, debt)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    if args.corruption_probes:
        escaped = _corruption_probes(inventory, debt)
        if escaped:
            print("corruption probes escaped: " + ", ".join(escaped), file=sys.stderr)
            return 1
        print("status-retirement corruption probes: PASS")
    print(json.dumps(_summary(inventory, debt), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
