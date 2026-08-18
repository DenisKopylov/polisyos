#!/usr/bin/env python3
"""Validate and project the fixed canonical sources for Atlas health metrics."""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.metadata
import json
import platform
import re
import sys
from pathlib import Path
from typing import Any, Literal, NoReturn

from jsonschema import Draft202012Validator, FormatChecker

REPO_ROOT = Path(__file__).resolve().parents[3]
READINESS_PATH = Path(
    "architecture/atlas_surfaces/live-application-readiness-ledger.json"
)
READINESS_SCHEMA_PATH = Path(
    "architecture/atlas_surfaces/surface-readiness-ledger.schema.json"
)
ADOPTION_PATH = Path("architecture/atlas_surfaces/atlas-v15-adoption-ledger.json")
ADOPTION_SCHEMA_PATH = Path("architecture/atlas_surfaces/adoption-ledger.schema.json")
AUDIENCE_PROXY_PATH = Path(
    "tests/unit/runtime/http/test_authorization_audience_denials.py"
)
CLUSTER_MAP_PATH = Path("architecture/policy_design_case/cluster_ownership_map.toml")
CLUSTER_INVENTORY_PATH = Path("architecture/policy_design_case/inventory.json")
CLUSTER_RATCHET_PATH = Path(
    "architecture/policy_design_case/capability_reality_report.json"
)
FAILURE_REGISTER_PATH = Path(
    "docs/reference/policy-design-case-failure-patterns.md"
)
CLUSTER_VALIDATOR_PATH = Path(
    "tools/quality/validation/check_policy_design_case_cluster_ownership_map.py"
)
IMPLEMENTATION_PATH = Path(
    "apps/runtime-dashboard/scripts/validate_atlas_health_sources.py"
)
PROJECTION_SCHEMA = {
    "id": "polisyos.atlas.health-source-projection",
    "version": "1.0.0",
}
PRODUCER_ID = "polisyos.atlas.health_source_validator"
PRODUCER_VERSION = "1.0.0"
OwnerName = Literal["readiness", "adoption"]
OWNER_IDENTITY_KEYS: dict[OwnerName, str] = {
    "readiness": "surface_id",
    "adoption": "id",
}


class AtlasHealthSourceError(ValueError):
    """Report a fail-closed canonical-source validation error."""


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise AtlasHealthSourceError(f"duplicate JSON key: {key}")
        value[key] = item
    return value


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=_reject_duplicate_keys,
    )
    if not isinstance(value, dict):
        raise AtlasHealthSourceError(f"{path} must contain one JSON object")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _source_ref(path: Path, role: str) -> dict[str, str]:
    return {"path": path.as_posix(), "sha256": _sha256(REPO_ROOT / path), "role": role}


def _bind_adoption_schema(schema: dict[str, Any]) -> dict[str, Any]:
    readiness_schema = _load_json(REPO_ROOT / READINESS_SCHEMA_PATH)
    bound = copy.deepcopy(schema)
    external_defs = {
        "authorityBoundary": readiness_schema["$defs"]["authorityBoundary"],
        "owningSlice": readiness_schema["$defs"]["owningSlice"],
        "componentMaturity": readiness_schema["$defs"]["componentMaturity"],
        "surfaceAudience": readiness_schema["$defs"]["surfaceAudience"],
    }
    bound["$defs"].update(external_defs)

    def bind(value: object) -> None:
        if isinstance(value, dict):
            reference = value.get("$ref")
            if isinstance(reference, str) and reference.startswith(
                "surface-readiness-ledger.schema.json#/$defs/"
            ):
                value["$ref"] = "#/$defs/" + reference.rsplit("/", 1)[1]
            for child in value.values():
                bind(child)
        elif isinstance(value, list):
            for child in value:
                bind(child)

    bind(bound)
    return bound


def validate_owner_instance(owner: OwnerName, value: dict[str, Any]) -> None:
    """Validate a complete owner instance against its canonical Draft 2020-12 schema.

    Args:
        owner: Fixed canonical owner identity.
        value: Complete decoded owner object.

    Raises:
        AtlasHealthSourceError: If the schema or instance is invalid.
    """

    schema_path = READINESS_SCHEMA_PATH if owner == "readiness" else ADOPTION_SCHEMA_PATH
    schema = _load_json(REPO_ROOT / schema_path)
    if owner == "adoption":
        schema = _bind_adoption_schema(schema)
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(value), key=lambda item: list(item.absolute_path))
    if errors:
        error = errors[0]
        location = "/".join(str(part) for part in error.absolute_path) or "root"
        raise AtlasHealthSourceError(f"{owner} schema violation at {location}: {error.message}")

    identity_key = OWNER_IDENTITY_KEYS[owner]
    seen: set[str] = set()
    duplicates: set[str] = set()
    for entry in value["entries"]:
        identity = entry[identity_key]
        if identity in seen:
            duplicates.add(identity)
        seen.add(identity)
    if duplicates:
        raise AtlasHealthSourceError(
            f"{owner} entries duplicate {identity_key}: {sorted(duplicates)!r}"
        )


def _cluster_projection() -> dict[str, Any]:
    source_root = str(REPO_ROOT)
    if source_root not in sys.path:
        sys.path.insert(0, source_root)
    from tools.quality.validation.check_policy_design_case_cluster_ownership_map import (
        validate_cluster_ownership_map,
    )

    report = validate_cluster_ownership_map(REPO_ROOT)
    if report.get("status") != "pass" or report.get("issues") != []:
        raise AtlasHealthSourceError("canonical cluster ownership validation did not pass")
    summary = report.get("summary")
    if not isinstance(summary, dict):
        raise AtlasHealthSourceError("canonical cluster ownership report has no summary")
    state_counts = summary.get("state_counts")
    closure = summary.get("open_cell_closure")
    if not isinstance(state_counts, dict) or not isinstance(closure, dict):
        raise AtlasHealthSourceError("canonical cluster ownership summary is incomplete")
    return {
        "cell_count": summary["cell_count"],
        "implemented_cell_count": state_counts.get("implemented", 0),
        "surface_missing_count": state_counts.get("surface_missing", 0),
        "implemented_but_not_orchestrated_count": state_counts.get(
            "implemented_but_not_orchestrated", 0
        ),
        "open_or_incomplete_count": summary["open_or_incomplete_count"],
        "open_cell_count": closure["open_cell_count"],
        "closure_contract_count": closure["closure_contract_count"],
        "source_refs": [
            _source_ref(CLUSTER_MAP_PATH, "complete_cluster_map_owner"),
            _source_ref(CLUSTER_INVENTORY_PATH, "cluster_inventory_dependency"),
            _source_ref(CLUSTER_RATCHET_PATH, "capability_ratchet_dependency"),
            _source_ref(FAILURE_REGISTER_PATH, "failure_vocabulary_dependency"),
            _source_ref(CLUSTER_VALIDATOR_PATH, "subordinate_recomputation"),
        ],
    }


def build_source_projection() -> dict[str, Any]:
    """Validate complete fixed owners and return their recomputed health projection."""

    readiness = _load_json(REPO_ROOT / READINESS_PATH)
    adoption = _load_json(REPO_ROOT / ADOPTION_PATH)
    validate_owner_instance("readiness", readiness)
    validate_owner_instance("adoption", adoption)

    readiness_entries = readiness["entries"]
    adoption_entries = adoption["entries"]
    stable_entries = [entry for entry in adoption_entries if entry["maturity"] == "stable"]
    stable_with_browser_and_at = sum(
        {
            evidence["kind"]
            for evidence in entry["evidence_refs"]
        }.issuperset({"browser", "at_manual"})
        for entry in stable_entries
    )
    audience_source = (REPO_ROOT / AUDIENCE_PROXY_PATH).read_text(encoding="utf-8")
    proxy_test_count = len(re.findall(r"^def test_[a-z0-9_]+\(", audience_source, re.MULTILINE))

    return {
        "projection_schema": PROJECTION_SCHEMA,
        "producer": {
            "producer_id": PRODUCER_ID,
            "producer_version": PRODUCER_VERSION,
            "python_executable": str(Path(sys.executable).resolve()),
            "python_version": platform.python_version(),
            "jsonschema_version": importlib.metadata.version("jsonschema"),
            "schema_dialect": Draft202012Validator.META_SCHEMA["$schema"],
            "implementation_ref": _source_ref(
                IMPLEMENTATION_PATH, "canonical_source_validator"
            ),
        },
        "readiness": {
            "as_of": readiness["as_of"],
            "entry_count": len(readiness_entries),
            "machine_audience_count": sum(
                "MACHINE" in entry["audiences"] for entry in readiness_entries
            ),
            "implemented_entry_count": sum(
                entry["readiness_state"] == "implemented"
                for entry in readiness_entries
            ),
            "source_refs": [
                _source_ref(READINESS_PATH, "complete_readiness_population"),
                _source_ref(READINESS_SCHEMA_PATH, "readiness_owner_schema"),
            ],
        },
        "audience": {
            "proxy_test_count": proxy_test_count,
            "source_refs": [
                _source_ref(
                    AUDIENCE_PROXY_PATH,
                    "incomplete_server_denial_proxy_set",
                )
            ],
        },
        "cluster": _cluster_projection(),
        "adoption": {
            "as_of": adoption["as_of"],
            "entry_count": len(adoption_entries),
            "stable_component_count": len(stable_entries),
            "stable_with_browser_and_at_count": stable_with_browser_and_at,
            "source_refs": [
                _source_ref(ADOPTION_PATH, "complete_component_maturity_population"),
                _source_ref(ADOPTION_SCHEMA_PATH, "adoption_owner_schema"),
                _source_ref(READINESS_SCHEMA_PATH, "adoption_external_schema_dependency"),
            ],
        },
    }


def _expect_invalid(owner: OwnerName, value: dict[str, Any], name: str) -> str:
    try:
        validate_owner_instance(owner, value)
    except AtlasHealthSourceError:
        return name
    raise AtlasHealthSourceError(f"corruption probe escaped: {name}")


def run_corruption_probes() -> list[str]:
    """Prove canonical required/extra/unique/format/enum/stable constraints fail."""

    readiness = _load_json(REPO_ROOT / READINESS_PATH)
    adoption = _load_json(REPO_ROOT / ADOPTION_PATH)
    probes: list[str] = []

    candidate = copy.deepcopy(readiness)
    candidate.pop("schema_version")
    probes.append(_expect_invalid("readiness", candidate, "readiness_required"))
    candidate = copy.deepcopy(readiness)
    candidate["forged"] = True
    probes.append(
        _expect_invalid("readiness", candidate, "readiness_additional_property")
    )
    candidate = copy.deepcopy(readiness)
    candidate["entries"][0]["audiences"] = ["PUBLIC", "PUBLIC"]
    probes.append(
        _expect_invalid("readiness", candidate, "readiness_unique_audience")
    )
    candidate = copy.deepcopy(readiness)
    candidate["entries"][0]["updated_at"] = "not-a-date-time"
    probes.append(
        _expect_invalid("readiness", candidate, "readiness_datetime_format")
    )
    candidate = copy.deepcopy(readiness)
    candidate["entries"].append(copy.deepcopy(candidate["entries"][0]))
    probes.append(
        _expect_invalid(
            "readiness", candidate, "readiness_duplicate_surface_id"
        )
    )

    candidate = copy.deepcopy(adoption)
    candidate["entries"][0]["maturity"] = "production"
    probes.append(_expect_invalid("adoption", candidate, "adoption_enum"))
    candidate = copy.deepcopy(adoption)
    candidate["entries"][0]["decided_at"] = "not-a-date"
    probes.append(_expect_invalid("adoption", candidate, "adoption_date_format"))
    candidate = copy.deepcopy(adoption)
    candidate["entries"][0]["maturity"] = "stable"
    candidate["entries"][0]["evidence_refs"] = [
        {"kind": "code_reference", "ref": "repo://candidate", "as_of": "2026-08-16"}
    ]
    probes.append(
        _expect_invalid("adoption", candidate, "adoption_stable_evidence")
    )
    candidate = copy.deepcopy(adoption)
    candidate["entries"].append(copy.deepcopy(candidate["entries"][0]))
    probes.append(_expect_invalid("adoption", candidate, "adoption_duplicate_id"))
    return probes


def _fail(message: str) -> NoReturn:
    sys.stderr.write(message + "\n")
    raise SystemExit(1)


def main() -> None:
    """Emit the fixed source projection or run in-memory corruption probes."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corruption-probes", action="store_true")
    args = parser.parse_args()
    try:
        value: object
        if args.corruption_probes:
            value = {"ok": True, "probes": run_corruption_probes()}
        else:
            value = build_source_projection()
    except Exception as exc:
        _fail(f"{type(exc).__name__}: {exc}")
    sys.stdout.write(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    )


if __name__ == "__main__":
    main()
