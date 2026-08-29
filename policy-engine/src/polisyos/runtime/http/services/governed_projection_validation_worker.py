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
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from polisyos.runtime.http.services.governed_projection_dependencies import (
    DependencyTracker,
)

_SCHEMA_VERSION = "policyos.runtime.governed_projection.owner_validation.v2"
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
_N13A_CATALOG_PATH = (
    "production_data/datasets_full_phase3full_20260327_183054/dataset_catalog.duckdb"
)
_N13A_SUBSTRATE_PATH = (
    "architecture/policy_design_case/layer3_gy_intervention_substrate_contract.json"
)
_CAPABILITY_PATH = "architecture/policy_design_case/capability_reality_report.json"
_CLUSTER_PATH = "architecture/policy_design_case/cluster_ownership_map.toml"
_HEALTH_PATH = "architecture/policy_design_case/layer3_health_metric_ledgers.toml"
_PROVING_ROOT = "tests/fixtures/universal-corpus"
_CONFIDENCE_LEDGER_PATH = (
    "architecture/policy_design_case/layer3_gy_confidence_ledger_contract.json"
)

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
        "tools.quality.validation.check_layer3_gy_n13a_acquisition_census:main",
        "policyos.layer3.gy.n13a.acquisition_census.v1",
    ),
    "n13a-live-probe-journal": (
        "tools.quality.validation.check_layer3_gy_n13a_acquisition_census:main",
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
    "confidence-ledger-risk-spend": (
        "tools.quality.validation.check_layer3_gy_confidence_ledger:validate_payload",
        "policyos.policy_design_case.layer3_gy.n11_confidence_ledger.v1",
    ),
}


def _sha256(raw: bytes) -> str:
    return f"sha256:{hashlib.sha256(raw).hexdigest()}"


def _aggregate_identity(bindings: Mapping[str, Any]) -> str:
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
        for key, item in value.items():
            if key == "code" and isinstance(item, str) and item:
                codes.append(item)
            codes.extend(_extract_issue_codes(item))
        return codes
    if isinstance(value, Sequence) and not isinstance(
        value,
        (str, bytes, bytearray),
    ):
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


def _validate_n13a_canonical_recompute(root: Path) -> list[str]:
    catalog_path = root / _N13A_CATALOG_PATH
    if not catalog_path.is_file():
        return ["owner_validator_dependency_missing_catalog"]
    from tools.quality.validation import check_layer3_gy_n13a_acquisition_census

    output = io.StringIO()
    owner_root = check_layer3_gy_n13a_acquisition_census.POLICY_ENGINE_ROOT
    check_layer3_gy_n13a_acquisition_census.POLICY_ENGINE_ROOT = root
    try:
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(io.StringIO()):
            return_code = check_layer3_gy_n13a_acquisition_census.main(
                [
                    "--catalog-path",
                    str(catalog_path),
                    "--source-locator",
                    _N13A_CATALOG_PATH,
                    "--capstone-path",
                    str(root / _DEPTH_PATH),
                    "--intervention-substrate-path",
                    str(root / _N13A_SUBSTRATE_PATH),
                    "--value-gate-path",
                    str(root / _VALUE_PATH),
                    "--output",
                    str(root / _N13A_CENSUS_PATH),
                    "--probe-journal-path",
                    str(root / _N13A_JOURNAL_PATH),
                    "--check",
                ]
            )
    finally:
        check_layer3_gy_n13a_acquisition_census.POLICY_ENGINE_ROOT = owner_root
    if return_code == 0:
        return []
    for line in reversed(output.getvalue().splitlines()):
        try:
            report = json.loads(line)
        except json.JSONDecodeError:
            continue
        codes = _extract_issue_codes(report)
        if codes:
            return codes
    return ["n13a_canonical_recompute_failed"]


def _validate_n13a_census(root: Path) -> list[str]:
    return _validate_n13a_canonical_recompute(root)


def _validate_n13a_journal(root: Path) -> list[str]:
    return _validate_n13a_canonical_recompute(root)


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


def _validate_confidence_ledger(
    root: Path,
    requested_projection: Mapping[str, Any],
) -> dict[str, Any]:
    """Run the real N11 validator and freeze source/request arithmetic facts."""

    from polisyos.runtime.quality.confidence_ledger import (
        ConfidenceLedgerSemanticReceiptProjection,
        load_confidence_ledger_registry,
    )
    from tools.quality.validation.check_layer3_gy_confidence_ledger import (
        validate_payload,
    )

    artifact = _load_json(root, _CONFIDENCE_LEDGER_PATH)
    issues = _extract_issue_codes(validate_payload(artifact))
    facts: dict[str, Any] = {
        "issue_codes": issues,
        "source_payload_equal": None,
        "registry_content_hash": None,
        "registry_projection_hash": None,
        "frozen_semantic_projection_hash": None,
        "recomputed_total_spend_numerator": None,
        "recomputed_total_spend_denominator": None,
        "registry_delta_numerator": None,
        "registry_delta_denominator": None,
    }
    try:
        semantic = ConfidenceLedgerSemanticReceiptProjection.model_validate_json(
            json.dumps(
                artifact.get("real_ledger_projection"),
                separators=(",", ":"),
                sort_keys=True,
            ),
            strict=True,
        )
        requested = ConfidenceLedgerSemanticReceiptProjection.model_validate_json(
            json.dumps(
                requested_projection,
                separators=(",", ":"),
                sort_keys=True,
            ),
            strict=True,
        )
    except (TypeError, ValueError):
        issues.append("confidence_semantic_projection_invalid")
        return facts
    facts["source_payload_equal"] = semantic.model_dump(
        mode="json"
    ) == requested.model_dump(mode="json")
    if not facts["source_payload_equal"]:
        issues.append("source_projection_payload_mismatch")

    raw_registry_projection = artifact.get("registry_projection")
    if not isinstance(raw_registry_projection, Mapping):
        issues.append("confidence_registry_projection_invalid")
        return facts
    registry_fields = (
        "policy",
        "obligation_pools",
        "proof_profiles",
        "schedule_profiles",
        "instruments",
        "certificate_class_routes",
    )
    try:
        registry_payload = {
            field: raw_registry_projection[field] for field in registry_fields
        }
        registry_payload["schema_version"] = raw_registry_projection[
            "registry_schema_version"
        ]
        registry = load_confidence_ledger_registry(registry_payload)
        registry_content_hash = str(raw_registry_projection["registry_content_hash"])
        registry_projection_hash = str(raw_registry_projection["projection_hash"])
        if registry.content_hash != registry_content_hash:
            raise ValueError("confidence_registry_content_hash_mismatch")
    except (KeyError, TypeError, ValueError):
        issues.append("confidence_registry_projection_invalid")
        return facts

    recomputed_total = sum(
        (check.spend.fraction for check in semantic.checks),
        start=registry.policy.delta.fraction * 0,
    )
    facts.update(
        {
            "registry_content_hash": registry.content_hash,
            "registry_projection_hash": registry_projection_hash,
            "frozen_semantic_projection_hash": semantic.projection_hash,
            "recomputed_total_spend_numerator": recomputed_total.numerator,
            "recomputed_total_spend_denominator": recomputed_total.denominator,
            "registry_delta_numerator": registry.policy.delta.numerator,
            "registry_delta_denominator": registry.policy.delta.denominator,
        }
    )
    return facts


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


def _semantic_projection_hash(
    projection_id: str,
    payload: Mapping[str, Any],
) -> tuple[str, str]:
    if projection_id == "confidence-ledger-risk-spend":
        from polisyos.runtime.quality.confidence_ledger import (
            ConfidenceLedgerSemanticReceiptProjection,
        )

        semantic = ConfidenceLedgerSemanticReceiptProjection.model_validate_json(
            json.dumps(payload, separators=(",", ":"), sort_keys=True),
            strict=True,
        )
        return (
            semantic.projection_hash,
            "policyos.runtime.confidence_ledger.semantic_projection.v1",
        )
    if projection_id in {"n13a-acquisition-census", "n13a-live-probe-journal"}:
        from tools.quality.validation.layer3_gy_n13a_acquisition_census import (
            semantic_content_hash,
        )

        return (
            semantic_content_hash(payload),
            "policyos.layer3.gy.n13a.acquisition_census.v1",
        )
    from polisyos.pdc import gy_content_hash

    return gy_content_hash(payload), "polisyos.pdc.gy_content_hash.v1"


def _validate_request(request: Mapping[str, Any]) -> dict[str, Any]:
    projection_id = str(request.get("projection_id") or "unknown")
    raw_root = request.get("repository_root")
    raw_bindings = request.get("component_bindings")
    raw_projection_payload = request.get("projection_payload")
    bindings = (
        {str(key): str(value) for key, value in raw_bindings.items()}
        if isinstance(raw_bindings, Mapping)
        else {}
    )
    projection_payload = (
        {str(key): value for key, value in raw_projection_payload.items()}
        if isinstance(raw_projection_payload, Mapping)
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
        "bound_projection_payload_hash": _aggregate_identity(projection_payload),
        "semantic_projection_hash": None,
        "semantic_projection_hash_rule_version": None,
        "dependency_aggregate_identity": _aggregate_identity({}),
        "dependency_bindings": {},
        "issue_codes": [],
        "source_payload_equal": None,
        "registry_content_hash": None,
        "registry_projection_hash": None,
        "frozen_semantic_projection_hash": None,
        "recomputed_total_spend_numerator": None,
        "recomputed_total_spend_denominator": None,
        "registry_delta_numerator": None,
        "registry_delta_denominator": None,
    }
    if (
        not isinstance(raw_root, str)
        or not raw_root
        or not bindings
        or not isinstance(raw_projection_payload, Mapping)
    ):
        result["issue_codes"] = ["validation_request_invalid"]
        return result
    root = Path(raw_root).resolve()
    tracker = DependencyTracker(root)
    for relative_path in bindings:
        try:
            tracker.record(root / _safe_relative_path(relative_path))
        except ValueError:
            continue
    issues: list[str] = []
    semantic_projection_hash: str | None = None
    semantic_hash_rule: str | None = None
    with tracker:
        component_issues = _verify_components(root, bindings)
        issues.extend(component_issues)
        validator = _VALIDATORS.get(projection_id)
        confidence_ledger = projection_id == "confidence-ledger-risk-spend"
        if not issues and validator is None and not confidence_ledger:
            issues.append("owner_validator_unregistered")
        if not issues and confidence_ledger:
            try:
                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(
                    io.StringIO()
                ):
                    facts = _validate_confidence_ledger(root, projection_payload)
                issues.extend(facts.pop("issue_codes"))
                result.update(facts)
            except SystemExit as exc:
                issues.append(f"owner_validator_system_exit_{exc.code}")
            except Exception as exc:  # isolate owner validator failures as data
                error_code = getattr(exc, "code", None)
                issues.append(str(error_code or type(exc).__name__))
        elif not issues and validator is not None:
            try:
                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(
                    io.StringIO()
                ):
                    issues.extend(validator(root))
            except SystemExit as exc:
                issues.append(f"owner_validator_system_exit_{exc.code}")
            except Exception as exc:  # isolate owner validator failures as data
                error_code = getattr(exc, "code", None)
                issues.append(str(error_code or type(exc).__name__))
        if not component_issues:
            after_issues = _verify_components(root, bindings)
            if after_issues:
                issues.append("component_changed_during_validation")
                issues.extend(after_issues)
        if not issues:
            try:
                semantic_projection_hash, semantic_hash_rule = _semantic_projection_hash(
                    projection_id,
                    projection_payload,
                )
            except Exception as exc:  # hash owner failures are typed validation failures
                issues.append(f"semantic_projection_hash_{type(exc).__name__}")
    tracker.record_loaded_modules()
    dependency_bindings, dependency_issues = tracker.receipt()
    issues.extend(dependency_issues)
    normalized = sorted({str(code) for code in issues if str(code)})
    result["issue_codes"] = normalized
    result["status"] = "passed" if not normalized else "failed"
    result["semantic_projection_hash"] = (
        semantic_projection_hash if not normalized else None
    )
    result["semantic_projection_hash_rule_version"] = (
        semantic_hash_rule if not normalized else None
    )
    result["dependency_bindings"] = dependency_bindings
    result["dependency_aggregate_identity"] = _aggregate_identity(dependency_bindings)
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
            "bound_projection_payload_hash": _aggregate_identity({}),
            "semantic_projection_hash": None,
            "semantic_projection_hash_rule_version": None,
            "dependency_aggregate_identity": _aggregate_identity({}),
            "dependency_bindings": {},
            "issue_codes": [type(exc).__name__],
            "source_payload_equal": None,
            "registry_content_hash": None,
            "registry_projection_hash": None,
            "frozen_semantic_projection_hash": None,
            "recomputed_total_spend_numerator": None,
            "recomputed_total_spend_denominator": None,
            "registry_delta_numerator": None,
            "registry_delta_denominator": None,
        }
    sys.stdout.write(json.dumps(result, separators=(",", ":"), sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":  # pragma: no cover - subprocess entrypoint
    raise SystemExit(main())
