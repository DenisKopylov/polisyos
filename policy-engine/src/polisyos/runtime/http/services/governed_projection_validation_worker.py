"""Isolated owner-validator bridge for governed HTTP projections.

This module is executed as a child process. The runtime HTTP process never imports
the heavy artifact owners or their validators.
"""

from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import io
import json
import re
import sys
import tomllib
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

_SCHEMA_VERSION = "policyos.runtime.governed_projection.owner_validation.v1"
_SHA256_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")

_DEPTH_PATH = "architecture/policy_design_case/layer3_gy_depth_n_universality_contract.json"
_VALUE_PATH = "architecture/policy_design_case/layer3_gy_value_gate_contract.json"
_DISPOSITION_PATH = (
    "architecture/policy_design_case/layer3_gy_generation_cycle_disposition_ledger.json"
)
_ENGINE_PATH = "architecture/policy_design_case/layer3_gy_task0_audit/layer3_gy_engine_census.json"
_FORK_B_PATH = "architecture/policy_design_case/layer3_gy_n10_cg1_l2_relation_census.json"
_ACQUISITION_PATH = "architecture/policy_design_case/layer3_gy_acquisition_contract.json"
_N13A_CENSUS_PATH = "architecture/policy_design_case/layer3_gy_n13a_acquisition_census.json"
_N13A_JOURNAL_PATH = "architecture/policy_design_case/layer3_gy_n13a_live_probe_journal.json"
_CAPABILITY_PATH = "architecture/policy_design_case/capability_reality_report.json"
_CLUSTER_PATH = "architecture/policy_design_case/cluster_ownership_map.toml"
_HEALTH_PATH = "architecture/policy_design_case/layer3_health_metric_ledgers.toml"
_PROVING_ROOT = "tests/fixtures/universal-corpus"

_VALIDATOR_METADATA: dict[str, tuple[str, str]] = {
    "depth-n-cycle-board": (
        "tools.quality.validation.check_layer3_gy_depth_n_universality_contract",
        "policyos.policy_design_case.gy_n10.depth_n_universality.v1",
    ),
    "value-gate": (
        "tools.quality.validation.check_layer3_gy_value_gate_contract:validate_payload",
        "policyos.policy_design_case.layer3_gy.value_gate_contract.v2",
    ),
    "generation-cycle-disposition": (
        "tools.quality.validation.check_layer3_gy_generation_cycle_disposition_ledger:validate_ledger",
        "policyos.policy_design_case.layer3_gy.generation_cycle_disposition_ledger.v1",
    ),
    "engine-census": (
        "tools.quality.validation.check_layer3_gy_engine_census:validate",
        "policyos.policy_design_case.layer3_gy_engine_census.v1",
    ),
    "fork-b-relation-census": (
        "tools.quality.validation.check_layer3_gy_n10_cg1_l2_relation_census:_validate",
        "policyos.gy_n10.cg1_l2_prior_census.compact.v1",
    ),
    "acquisition-routing-contract": (
        "tools.quality.validation.check_layer3_gy_acquisition_contract:validate_payload",
        "policyos.policy_design_case.layer3_gy.acquisition_contract.v1",
    ),
    "n13a-acquisition-census": (
        "tools.quality.validation.layer3_gy_n13a_acquisition_census:CensusManifest",
        "policyos.layer3.gy.n13a.acquisition_census.v1",
    ),
    "n13a-live-probe-journal": (
        "tools.quality.validation.layer3_gy_n13a_acquisition_census:LiveProbeJournal",
        "policyos.layer3.gy.n13a.acquisition_census.v1",
    ),
    "capability-reality": (
        "tools.quality.validation.check_policy_design_case_capability_ratchet:validate_capability_reality_report",
        "policyos.runtime.policy_design_case.capability_ratchet.v1",
    ),
    "cluster-ownership": (
        "tools.quality.validation.check_policy_design_case_cluster_ownership_map:validate_cluster_ownership_map",
        "policyos.policy_design_case.cluster_ownership_map.v1",
    ),
    "layer3-health-metrics": (
        "polisyos.runtime.quality.proving_ground.pre_adapter_grounding_inventory:HealthMetricLedger",
        "policyos.policy_design_case.layer3_g0_discovery_search.v2",
    ),
    "legacy-proving-ground": (
        "polisyos.corpus:load_universal_corpus_fixtures",
        "policyos.universal_corpus_manifest.v1",
    ),
    "surface-readiness": (
        "unregistered:surface-readiness-owner-validator",
        "unregistered",
    ),
}


def _sha256(raw: bytes) -> str:
    return f"sha256:{hashlib.sha256(raw).hexdigest()}"


def _aggregate_identity(bindings: Mapping[str, str]) -> str:
    canonical = json.dumps(
        dict(sorted(bindings.items())),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return _sha256(canonical)


def _safe_relative_path(value: str) -> Path:
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError("component_path_invalid")
    return path


def _verify_components(root: Path, bindings: Mapping[str, str]) -> list[str]:
    issues: list[str] = []
    for relative_path, expected_hash in sorted(bindings.items()):
        try:
            path = _safe_relative_path(relative_path)
        except ValueError:
            issues.append("component_path_invalid")
            continue
        if _SHA256_PATTERN.fullmatch(expected_hash) is None:
            issues.append("component_hash_format_invalid")
            continue
        try:
            actual_hash = _sha256((root / path).read_bytes())
        except OSError:
            issues.append("component_missing")
            continue
        if actual_hash != expected_hash:
            issues.append("component_hash_mismatch")
    return sorted(set(issues))


def _load_json(root: Path, relative_path: str) -> dict[str, Any]:
    value = json.loads((root / relative_path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("source_top_level_not_object")
    return value


def _load_toml(root: Path, relative_path: str) -> dict[str, Any]:
    value = tomllib.loads((root / relative_path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("source_top_level_not_object")
    return value


def _identity_issues(
    payload: Mapping[str, Any],
    *,
    schema_version: str,
    rule_version: str | None = None,
) -> list[str]:
    issues: list[str] = []
    if payload.get("schema_version") != schema_version:
        issues.append("schema_version_mismatch")
    if rule_version is not None and payload.get("rule_version") != rule_version:
        issues.append("rule_version_mismatch")
    return issues


def _extract_issue_codes(value: object) -> list[str]:
    if isinstance(value, Mapping):
        codes: list[str] = []
        code = value.get("code")
        if isinstance(code, str) and code:
            codes.append(code)
        for key in ("issues", "violations", "errors"):
            codes.extend(_extract_issue_codes(value.get(key)))
        return codes
    if isinstance(value, (list, tuple)):
        return [code for item in value for code in _extract_issue_codes(item)]
    return []


def _missing_runtime_dependencies(*module_names: str) -> list[str]:
    missing: list[str] = []
    for name in module_names:
        try:
            available = importlib.util.find_spec(name) is not None
        except ModuleNotFoundError:
            available = False
        if not available:
            missing.append(f"owner_validator_dependency_missing_{name.replace('.', '_')}")
    return missing


def _validate_depth(root: Path) -> list[str]:
    payload = _load_json(root, _DEPTH_PATH)
    issues = _identity_issues(
        payload,
        schema_version="policyos.policy_design_case.gy_n10.depth_n_universality.v1",
        rule_version="policyos.layer3.gy.n10.depth_n_universality.v1",
    )
    issues.extend(_missing_runtime_dependencies("ortools.sat.python.cp_model"))
    if issues:
        return issues
    from tools.quality.validation.check_layer3_gy_depth_n_universality_contract import (
        validate_payload,
    )

    issues.extend(_extract_issue_codes(validate_payload(payload)))
    return issues


def _validate_value(root: Path) -> list[str]:
    payload = _load_json(root, _VALUE_PATH)
    issues = _identity_issues(
        payload,
        schema_version="policyos.policy_design_case.layer3_gy.value_gate_contract.v2",
        rule_version="policyos.layer3.gy.n8.value_gate.v2",
    )
    issues.extend(_missing_runtime_dependencies("ortools.sat.python.cp_model"))
    if issues:
        return issues
    from tools.quality.validation.check_layer3_gy_value_gate_contract import validate_payload

    issues.extend(_extract_issue_codes(validate_payload(payload)))
    return issues


def _validate_disposition(root: Path) -> list[str]:
    payload = _load_json(root, _DISPOSITION_PATH)
    issues = _identity_issues(
        payload,
        schema_version=(
            "policyos.policy_design_case.layer3_gy.generation_cycle_disposition_ledger.v1"
        ),
    )
    issues.extend(_missing_runtime_dependencies("ortools.sat.python.cp_model"))
    if issues:
        return issues
    from tools.quality.validation.check_layer3_gy_generation_cycle_disposition_ledger import (
        validate_ledger,
    )

    issues.extend(_extract_issue_codes(validate_ledger(root, payload)))
    return issues


def _validate_engine(root: Path) -> list[str]:
    payload = _load_json(root, _ENGINE_PATH)
    issues = _identity_issues(
        payload,
        schema_version="policyos.policy_design_case.layer3_gy_engine_census.v1",
        rule_version="policyos.layer3.gy.engine_reality_census.v1",
    )
    from tools.quality.validation.check_layer3_gy_engine_census import validate

    issues.extend(_extract_issue_codes(validate(payload)))
    return issues


def _validate_fork_b(root: Path) -> list[str]:
    payload = _load_json(root, _FORK_B_PATH)
    issues = _identity_issues(
        payload,
        schema_version="policyos.gy_n10.cg1_l2_prior_census.compact.v1",
        rule_version="policyos.layer3.gy.n10.cg1_relation_extension.v1",
    )
    from tools.quality.validation.check_layer3_gy_n10_cg1_l2_relation_census import (
        _validate,
    )

    _validate(payload)
    return issues


def _validate_acquisition(root: Path) -> list[str]:
    payload = _load_json(root, _ACQUISITION_PATH)
    issues = _identity_issues(
        payload,
        schema_version="policyos.policy_design_case.layer3_gy.acquisition_contract.v1",
    )
    issues.extend(_missing_runtime_dependencies("ortools.sat.python.cp_model"))
    if issues:
        return issues
    from tools.quality.validation.check_layer3_gy_acquisition_contract import validate_payload

    issues.extend(_extract_issue_codes(validate_payload(payload)))
    return issues


def _validate_n13a_census(root: Path) -> list[str]:
    from tools.quality.validation.layer3_gy_n13a_acquisition_census import (
        read_census_manifest,
        read_live_probe_journal,
        semantic_content_hash,
    )

    census = read_census_manifest(root / _N13A_CENSUS_PATH)
    journal = read_live_probe_journal(root / _N13A_JOURNAL_PATH)
    if census.journal_content_sha256 != semantic_content_hash(journal):
        return ["journal_semantic_content_hash_mismatch"]
    return []


def _validate_n13a_journal(root: Path) -> list[str]:
    from tools.quality.validation.layer3_gy_n13a_acquisition_census import (
        read_live_probe_journal,
    )

    read_live_probe_journal(root / _N13A_JOURNAL_PATH)
    return []


def _validate_capability(root: Path) -> list[str]:
    payload = _load_json(root, _CAPABILITY_PATH)
    from tools.quality.validation.check_policy_design_case_capability_ratchet import (
        validate_capability_reality_report,
    )

    result = validate_capability_reality_report(payload, repo_root=root)
    return _extract_issue_codes(result)


def _validate_cluster(root: Path) -> list[str]:
    payload = _load_toml(root, _CLUSTER_PATH)
    issues = _identity_issues(
        payload,
        schema_version="policyos.policy_design_case.cluster_ownership_map.v1",
    )
    from tools.quality.validation.check_policy_design_case_cluster_ownership_map import (
        validate_cluster_ownership_map,
    )

    issues.extend(_extract_issue_codes(validate_cluster_ownership_map(root)))
    return issues


def _validate_health(root: Path) -> list[str]:
    payload = _load_toml(root, _HEALTH_PATH)
    issues = _identity_issues(
        payload,
        schema_version="policyos.policy_design_case.layer3_g0_discovery_search.v2",
        rule_version="policyos.layer3.g0.discovery_search_free_growth.v2",
    )
    from polisyos.runtime.quality.proving_ground.pre_adapter_grounding_inventory import (
        HealthMetricLedger,
        _health_metric_ledgers,
    )

    rows = payload.get("health_metric_ledgers")
    if not isinstance(rows, list):
        return [*issues, "health_metric_ledgers_missing"]
    actual = tuple(HealthMetricLedger.model_validate(row) for row in rows)
    expected = tuple(_health_metric_ledgers())
    if actual != expected:
        issues.append("health_metric_ledgers_owner_drift")
    return issues


def _validate_proving_ground(root: Path) -> list[str]:
    from polisyos.corpus import (
        load_universal_corpus_fixtures,
        load_universal_corpus_manifest,
    )

    fixture_root = root / _PROVING_ROOT
    manifest = load_universal_corpus_manifest(fixture_root)
    fixtures = load_universal_corpus_fixtures(fixture_root)
    if len(manifest.fixtures) != 13 or len(fixtures) != 13:
        return ["legacy_proving_ground_denominator_mismatch"]
    return []


_VALIDATORS: dict[str, Callable[[Path], list[str]]] = {
    "depth-n-cycle-board": _validate_depth,
    "value-gate": _validate_value,
    "generation-cycle-disposition": _validate_disposition,
    "engine-census": _validate_engine,
    "fork-b-relation-census": _validate_fork_b,
    "acquisition-routing-contract": _validate_acquisition,
    "n13a-acquisition-census": _validate_n13a_census,
    "n13a-live-probe-journal": _validate_n13a_journal,
    "capability-reality": _validate_capability,
    "cluster-ownership": _validate_cluster,
    "layer3-health-metrics": _validate_health,
    "legacy-proving-ground": _validate_proving_ground,
}


def _validate_request(request: Mapping[str, Any]) -> dict[str, Any]:
    projection_id = str(request.get("projection_id") or "unknown")
    raw_root = request.get("repository_root")
    raw_bindings = request.get("component_bindings")
    bindings = (
        {str(key): str(value) for key, value in raw_bindings.items()}
        if isinstance(raw_bindings, Mapping)
        else {}
    )
    validator_id, validator_version = _VALIDATOR_METADATA.get(
        projection_id,
        ("unregistered:unknown-projection", "unregistered"),
    )
    result = {
        "schema_version": _SCHEMA_VERSION,
        "projection_id": projection_id,
        "validator_id": validator_id,
        "validator_version": validator_version,
        "status": "failed",
        "bound_aggregate_identity": _aggregate_identity(bindings),
        "bound_source_identities": dict(sorted(bindings.items())),
        "issue_codes": [],
    }
    if not isinstance(raw_root, str) or not raw_root or not bindings:
        result["issue_codes"] = ["validation_request_invalid"]
        return result
    root = Path(raw_root).resolve()
    issues = _verify_components(root, bindings)
    if issues:
        result["issue_codes"] = issues
        return result
    validator = _VALIDATORS.get(projection_id)
    if validator is None:
        result["issue_codes"] = ["owner_validator_unregistered"]
        return result
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            issues.extend(validator(root))
    except SystemExit as exc:
        issues.append(f"owner_validator_system_exit_{exc.code}")
    except Exception as exc:  # isolate owner validator failures as data
        error_code = getattr(exc, "code", None)
        issues.append(str(error_code or type(exc).__name__))
    after_issues = _verify_components(root, bindings)
    if after_issues:
        issues.append("component_changed_during_validation")
        issues.extend(after_issues)
    normalized = sorted({str(code) for code in issues if str(code)})
    result["issue_codes"] = normalized
    result["status"] = "passed" if not normalized else "failed"
    return result


def main() -> int:
    """Validate one stdin request and emit exactly one machine-readable result."""

    try:
        request = json.loads(sys.stdin.read())
        if not isinstance(request, Mapping):
            request = {}
        result = _validate_request(request)
    except Exception as exc:  # worker must preserve typed failure output
        result = {
            "schema_version": _SCHEMA_VERSION,
            "projection_id": "unknown",
            "validator_id": "unregistered:worker-request",
            "validator_version": "unregistered",
            "status": "failed",
            "bound_aggregate_identity": _aggregate_identity({}),
            "bound_source_identities": {},
            "issue_codes": [type(exc).__name__],
        }
    sys.stdout.write(json.dumps(result, separators=(",", ":"), sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":  # pragma: no cover - subprocess entrypoint
    raise SystemExit(main())
