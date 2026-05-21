"""Read-only scenario binding index for production-data contracts."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PRODUCTION_DATA_CONTRACT_INDEX_SCHEMA_VERSION = "policyos.production_data_contract_index.v1"

SCENARIO_ADMISSIBLE_REQUIRED_FACETS = (
    "dataset_identity",
    "source_family",
    "dictionary_ref",
    "schema_ref",
    "field_refs",
    "unit_refs",
    "geography_refs",
    "time_coverage_refs",
    "freshness_ref",
    "lineage_refs",
    "transformation_refs",
    "quality_assertion_refs",
    "missingness_refs",
    "outlier_refs",
    "construct_validity_refs",
    "claim_bindability_refs",
)
QUALITY_REQUIRED_FACETS = (
    "freshness_ref",
    "construct_validity_refs",
    "outlier_refs",
)
QUALITY_BOUND_FACETS = (
    "freshness_ref",
    "construct_validity_refs",
    "missingness_refs",
    "outlier_refs",
    "claim_bindability_refs",
)

_FACET_ALIASES: dict[str, tuple[str, ...]] = {
    "dataset_identity": (
        "dataset_identity",
        "dataset_identity_ref",
        "dataset_ref",
        "dataset_id",
    ),
    "source_family": (
        "scenario_source_family",
        "source_family",
        "data_source_family",
        "source_family_id",
        "family",
        "dataset_family",
    ),
    "source_rights": (
        "source_rights",
        "rights_scope",
        "data_rights",
        "usage_rights",
        "license",
        "access_rights",
    ),
    "dictionary_ref": (
        "dictionary_ref",
        "dictionary_refs",
        "data_dictionary_ref",
        "data_dictionary_path",
        "dictionary_path",
    ),
    "schema_ref": (
        "schema_ref",
        "schema_refs",
        "schema_path",
        "expected_schema",
        "required_columns",
        "dtype",
    ),
    "field_refs": (
        "field_refs",
        "fields",
        "columns",
        "required_columns",
        "source_column",
        "metric_id",
    ),
    "unit_refs": ("unit_refs", "units", "unit"),
    "geography_refs": (
        "geography_refs",
        "geographies",
        "jurisdiction",
        "geography_patterns",
        "coverage.geographies",
    ),
    "time_coverage_refs": (
        "time_coverage_refs",
        "time_coverage",
        "temporal_coverage",
        "coverage.period_start",
        "coverage.period_end",
        "granularity",
    ),
    "quality_refs": (
        "quality_refs",
        "quality_ref",
        "quality_report_ref",
        "quality_contract",
        "qc_report_path",
        "benchmark_report_path",
        "trust",
    ),
    "missingness_refs": (
        "missingness_refs",
        "missingness_ref",
        "missingness_report_ref",
        "missingness_profile_ref",
        "missingness.ref",
        "missingness.evidence_ref",
        "missingness.limitation_ref",
    ),
    "lineage_refs": (
        "lineage_refs",
        "lineage_ref",
        "source_system",
        "source_table",
        "source_column",
        "connector_id",
        "dataset_id",
        "profile_id",
    ),
    "transformation_refs": (
        "transformation_refs",
        "transformation_ref",
        "transform_refs",
        "transforms",
        "normalization_ref",
        "filters_template",
        "derivation",
    ),
    "derived_feature_bindings": (
        "derived_feature_bindings",
        "derived_feature_binding_refs",
        "derived_features",
        "feature_bindings",
    ),
    "recency_ref": (
        "recency_ref",
        "recency_refs",
        "freshness_timestamp",
        "as_of",
        "as_of_date",
        "updated_at",
        "last_updated_at",
    ),
    "freshness_ref": (
        "freshness_ref",
        "freshness_refs",
        "freshness.evidence_ref",
        "freshness.ref",
        "freshness_timestamp",
        "as_of",
        "as_of_date",
        "updated_at",
        "last_updated_at",
    ),
    "quality_assertion_refs": (
        "quality_assertion_refs",
        "quality_assertion_ref",
        "quality_assertions",
    ),
    "construct_validity_refs": (
        "construct_validity_refs",
        "construct_validity_ref",
        "construct_validity",
        "construct_ref",
        "construct",
        "validity_report_ref",
    ),
    "outlier_refs": (
        "outlier_refs",
        "outlier_ref",
        "outlier_report_ref",
        "outlier_profile_ref",
        "outlier_profile.ref",
        "outliers_ref",
    ),
    "claim_bindability_refs": (
        "claim_bindability_refs",
        "claim_bindability_ref",
        "claim_bindability",
        "claim_binding_refs",
        "claim_bound_refs",
        "claim_evidence_refs",
    ),
}

_LIMITATION_BY_MISSING_FACET = {
    "freshness_ref": (
        "freshness_evidence_missing",
        "Production data lacks freshness evidence for the scenario claim.",
    ),
    "recency_ref": ("recency_timestamp_missing", "Production data lacks a recency timestamp."),
    "construct_validity_refs": (
        "construct_validity_metric_missing",
        "Production data lacks construct-validity evidence for the scenario claim.",
    ),
    "missingness_refs": (
        "missingness_diagnostic_missing",
        "Production data lacks claim-bindable missingness evidence.",
    ),
    "outlier_refs": (
        "outlier_profile_missing",
        "Production data lacks claim-bindable outlier evidence.",
    ),
    "claim_bindability_refs": (
        "claim_bindability_evidence_missing",
        "Production data lacks refs that bind this source to scenario claims.",
    ),
}

_STATUS_FAIL_VALUES = {"fail", "failed", "error", "blocked", "red"}
_STATUS_WARN_VALUES = {"warn", "warning", "degraded", "yellow"}


@dataclass(frozen=True)
class ProductionDataContractCandidate:
    """One manifest/source-binding/data-contract candidate for scenario evidence."""

    candidate_ref: str
    source_family: str
    bundle_role: str
    contract_id: str | None
    source_binding_id: str | None
    present_facets: tuple[str, ...]
    facet_refs: Mapping[str, Any]
    raw_contract: Mapping[str, Any]
    raw_source_binding: Mapping[str, Any]
    raw_bundle: Mapping[str, Any]

    def to_summary(self) -> dict[str, Any]:
        """Return a JSON-friendly non-secret candidate summary."""

        return {
            "candidate_ref": self.candidate_ref,
            "source_family": self.source_family,
            "bundle_role": self.bundle_role,
            "contract_id": self.contract_id,
            "source_binding_id": self.source_binding_id,
            "present_facets": list(self.present_facets),
        }


class ProductionDataContractIndex:
    """Read production-data manifests and curated contracts for scenario binding."""

    def __init__(
        self,
        *,
        root: Path,
        manifest: Mapping[str, Any],
        data_contracts_path: Path | None,
        source_bindings_path: Path | None,
        candidates: Sequence[ProductionDataContractCandidate],
    ) -> None:
        self.root = root
        self.manifest = manifest
        self.data_contracts_path = data_contracts_path
        self.source_bindings_path = source_bindings_path
        self.candidates = tuple(candidates)

    @classmethod
    def load(cls, root: Path | str) -> ProductionDataContractIndex:
        """Load the read-only contract index rooted at a production_data directory."""

        resolved_root = Path(root).expanduser()
        manifest = _load_mapping(resolved_root / "manifest.json")
        bundles = _manifest_bundles(manifest)
        curated_root = _curated_root(resolved_root, bundles)
        data_contracts_path = curated_root / "data_contracts.json" if curated_root else None
        source_bindings_path = curated_root / "source_bindings.json" if curated_root else None
        contracts_payload = _load_mapping(data_contracts_path) if data_contracts_path else {}
        bindings_payload = _load_mapping(source_bindings_path) if source_bindings_path else {}
        candidates = _build_candidates(
            root=resolved_root,
            bundles=bundles,
            contracts=_rows(contracts_payload, "contracts"),
            source_bindings=_rows(bindings_payload, "bindings"),
        )
        return cls(
            root=resolved_root,
            manifest=manifest,
            data_contracts_path=data_contracts_path,
            source_bindings_path=source_bindings_path,
            candidates=candidates,
        )

    def build_scenario_binding_report(
        self,
        scenario_evidence_contract: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Bind data-domain scenario requirements to production-data candidates."""

        requirements = [
            item
            for item in _rows(scenario_evidence_contract, "requirements")
            if str(item.get("domain") or "").strip().casefold() == "data"
        ]
        findings = [self.bind_requirement(requirement) for requirement in requirements]
        statuses = [str(item.get("status") or "") for item in findings]
        missing_source_families = sorted(
            {
                str(item.get("expected_family"))
                for item in findings
                if item.get("status") == "blocked"
                and item.get("blocker_code") == "scenario_source_family_absent"
                and item.get("expected_family")
            }
        )
        return {
            "schema_version": PRODUCTION_DATA_CONTRACT_INDEX_SCHEMA_VERSION,
            "root": str(self.root),
            "manifest_path": str(self.root / "manifest.json"),
            "data_contracts_path": str(self.data_contracts_path)
            if self.data_contracts_path
            else None,
            "source_bindings_path": str(self.source_bindings_path)
            if self.source_bindings_path
            else None,
            "scenario_contract_id": scenario_evidence_contract.get("contract_id"),
            "scenario_id": scenario_evidence_contract.get("scenario_id"),
            "candidate_count": len(self.candidates),
            "source_families": sorted(
                {
                    candidate.source_family
                    for candidate in self.candidates
                    if candidate.source_family
                }
            ),
            "summary": {
                "requirements": len(requirements),
                "satisfied": statuses.count("satisfied"),
                "failed": statuses.count("failed"),
                "blocked": statuses.count("blocked"),
            },
            "required_scenario_facets": list(SCENARIO_ADMISSIBLE_REQUIRED_FACETS),
            "missing_scenario_source_families": missing_source_families,
            "scenario_binding_findings": findings,
        }

    def bind_requirement(self, requirement: Mapping[str, Any]) -> dict[str, Any]:
        """Bind one data scenario requirement to the best matching candidate."""

        expected_family = _text(requirement.get("expected_family"))
        required_facets = tuple(
            str(item)
            for item in requirement.get("required_facets") or ()
            if str(item).strip()
        )
        admissible_required_facets = tuple(
            dict.fromkeys((*required_facets, *SCENARIO_ADMISSIBLE_REQUIRED_FACETS))
        )
        matching = [
            candidate
            for candidate in self.candidates
            if candidate.source_family.casefold() == expected_family.casefold()
        ]
        if not matching:
            return {
                "requirement_id": requirement.get("requirement_id"),
                "expected_family": expected_family,
                "candidate_ref": None,
                "status": "blocked",
                "blocker_code": "scenario_source_family_absent",
                "missing_facets": sorted(
                    set(admissible_required_facets) | set(QUALITY_REQUIRED_FACETS)
                ),
                "present_facets": [],
                "claim_bindability_status": "blocked",
                "claim_bound_limitations": [],
                "rejected_candidate_source_families": sorted(
                    {
                        candidate.source_family
                        for candidate in self.candidates
                        if candidate.source_family
                    }
                ),
            }

        candidate = _best_candidate(matching, admissible_required_facets)
        present = set(candidate.present_facets)
        missing_required = [
            facet for facet in admissible_required_facets if facet not in present
        ]
        missing_quality = [facet for facet in QUALITY_REQUIRED_FACETS if facet not in present]
        missing_facets = sorted(set(missing_required + missing_quality))
        limitations = _claim_bound_limitations(
            requirement=requirement,
            candidate=candidate,
            missing_facets=missing_facets,
        )
        status = (
            "satisfied"
            if not missing_facets and not _has_fail_limitation(limitations)
            else "failed"
        )
        return {
            "requirement_id": requirement.get("requirement_id"),
            "expected_family": expected_family,
            "candidate_ref": candidate.candidate_ref,
            "status": status,
            "blocker_code": None if status == "satisfied" else "scenario_data_contract_incomplete",
            "missing_facets": missing_facets,
            "present_facets": sorted(present),
            "facet_refs": {
                str(key): _json_like(value)
                for key, value in candidate.facet_refs.items()
            },
            "source_family": candidate.source_family,
            "bundle_role": candidate.bundle_role,
            "contract_id": candidate.contract_id,
            "source_binding_id": candidate.source_binding_id,
            "claim_bindability_status": _claim_bindability_status(
                status=status,
                missing_facets=missing_facets,
                limitations=limitations,
            ),
            "claim_bound_limitations": limitations,
        }


def _build_candidates(
    *,
    root: Path,
    bundles: Mapping[str, Mapping[str, Any]],
    contracts: Sequence[Mapping[str, Any]],
    source_bindings: Sequence[Mapping[str, Any]],
) -> tuple[ProductionDataContractCandidate, ...]:
    contracts_by_id = {
        contract_id: contract
        for contract in contracts
        if (contract_id := _contract_id(contract))
    }
    emitted: dict[str, ProductionDataContractCandidate] = {}
    curated_bundle = bundles.get("curated") or {}

    for binding in source_bindings:
        contract_id = _contract_id(binding)
        contract = contracts_by_id.get(contract_id or "", {})
        candidate = _candidate_from_rows(
            root=root,
            bundle_role=_text(binding.get("bundle_role")) or "curated",
            bundle=curated_bundle,
            contract=contract,
            source_binding=binding,
        )
        if candidate is not None:
            emitted[candidate.candidate_ref] = candidate

    bound_contract_ids = {_contract_id(binding) for binding in source_bindings}
    for contract in contracts:
        if _contract_id(contract) in bound_contract_ids:
            continue
        candidate = _candidate_from_rows(
            root=root,
            bundle_role=_text(contract.get("bundle_role")) or "curated",
            bundle=curated_bundle,
            contract=contract,
            source_binding={},
        )
        if candidate is not None:
            emitted[candidate.candidate_ref] = candidate

    has_curated_rows = bool(contracts or source_bindings)
    for role, bundle in sorted(bundles.items()):
        if has_curated_rows and str(role).casefold() == "curated":
            continue
        candidate = _candidate_from_rows(
            root=root,
            bundle_role=str(role),
            bundle=bundle,
            contract={},
            source_binding={},
        )
        if candidate is not None:
            emitted.setdefault(candidate.candidate_ref, candidate)
    return tuple(emitted.values())


def _candidate_from_rows(
    *,
    root: Path,
    bundle_role: str,
    bundle: Mapping[str, Any],
    contract: Mapping[str, Any],
    source_binding: Mapping[str, Any],
) -> ProductionDataContractCandidate | None:
    rows = (source_binding, contract, bundle)
    source_family = (
        _source_family(source_binding)
        or _source_family(contract)
        or _source_family(bundle)
        or bundle_role
    )
    contract_id = _contract_id(contract) or _contract_id(source_binding)
    source_binding_id = _binding_id(source_binding)
    version_ref = (
        contract_id
        or source_binding_id
        or _text(bundle.get("version_id"))
        or _text(bundle.get("path"))
        or bundle_role
    )
    if not source_family or not version_ref:
        return None
    facet_refs = {
        facet: value
        for facet, value in (
            (facet, _facet_ref(root=root, rows=rows, facet=facet))
            for facet in _FACET_ALIASES
        )
        if _present(value)
    }
    return ProductionDataContractCandidate(
        candidate_ref=(
            f"production_data:{bundle_role}:{source_family}:{_safe_ref_component(version_ref)}"
        ),
        source_family=source_family,
        bundle_role=bundle_role,
        contract_id=contract_id,
        source_binding_id=source_binding_id,
        present_facets=tuple(sorted(facet_refs)),
        facet_refs=facet_refs,
        raw_contract=contract,
        raw_source_binding=source_binding,
        raw_bundle=bundle,
    )


def _claim_bound_limitations(
    *,
    requirement: Mapping[str, Any],
    candidate: ProductionDataContractCandidate,
    missing_facets: Sequence[str],
) -> list[dict[str, Any]]:
    limitations: list[dict[str, Any]] = []
    for facet in QUALITY_BOUND_FACETS:
        if facet in missing_facets:
            code, message = _LIMITATION_BY_MISSING_FACET[facet]
            limitations.append(
                _limitation(
                    requirement=requirement,
                    candidate=candidate,
                    facet=facet,
                    code=code,
                    severity="fail",
                    degrade_reason=message,
                )
            )

    missingness_status = _diagnostic_status(
        candidate.raw_contract.get("missingness")
        or candidate.raw_contract.get("missingness_diagnostics")
        or candidate.raw_source_binding.get("missingness")
    )
    if missingness_status in {"fail", "warn"}:
        limitations.append(
            _limitation(
                requirement=requirement,
                candidate=candidate,
                facet="missingness_refs",
                code="production_data_missingness_high",
                severity=missingness_status,
                degrade_reason="Production data has unresolved missingness risk.",
            )
        )

    outlier_status = _diagnostic_status(
        candidate.raw_contract.get("outlier_profile")
        or candidate.raw_contract.get("outliers")
        or candidate.raw_source_binding.get("outlier_profile")
    )
    if outlier_status in {"fail", "warn"}:
        limitations.append(
            _limitation(
                requirement=requirement,
                candidate=candidate,
                facet="outlier_refs",
                code="production_data_outlier_ratio_high",
                severity=outlier_status,
                degrade_reason="Production data has unresolved numeric outlier risk.",
            )
        )
    return _dedupe_limitations(limitations)


def _limitation(
    *,
    requirement: Mapping[str, Any],
    candidate: ProductionDataContractCandidate,
    facet: str,
    code: str,
    severity: str,
    degrade_reason: str,
) -> dict[str, Any]:
    requirement_id = _text(requirement.get("requirement_id")) or "scenario:data:unknown"
    return {
        "code": code,
        "facet": facet,
        "severity": severity,
        "claim_scope": [
            str(item)
            for item in requirement.get("claim_scope") or ()
            if str(item).strip()
        ],
        "limitation_ref": (
            _explicit_limitation_ref(candidate, facet)
            or f"limitation:{requirement_id}:{facet}"
        ),
        "degrade_reason": degrade_reason,
        "candidate_ref": candidate.candidate_ref,
        "claim_bindable": True,
    }


def _best_candidate(
    candidates: Sequence[ProductionDataContractCandidate],
    required_facets: Sequence[str],
) -> ProductionDataContractCandidate:
    expected = set(required_facets) | set(QUALITY_REQUIRED_FACETS)
    return max(candidates, key=lambda candidate: len(expected & set(candidate.present_facets)))


def _claim_bindability_status(
    *,
    status: str,
    missing_facets: Sequence[str],
    limitations: Sequence[Mapping[str, Any]],
) -> str:
    if status == "satisfied":
        return "claim_bound"
    non_quality_missing = set(missing_facets) - set(QUALITY_BOUND_FACETS)
    if non_quality_missing:
        return "blocked"
    if limitations:
        return "degraded"
    return "blocked"


def _has_fail_limitation(limitations: Sequence[Mapping[str, Any]]) -> bool:
    return any(str(item.get("severity") or "").casefold() == "fail" for item in limitations)


def _diagnostic_status(value: object) -> str | None:
    if isinstance(value, Mapping):
        status = _text(value.get("status") or value.get("severity"))
        if status.casefold() in _STATUS_FAIL_VALUES:
            return "fail"
        if status.casefold() in _STATUS_WARN_VALUES:
            return "warn"
        for key in ("max_missing_rate", "missing_rate", "max_outlier_ratio", "outlier_ratio"):
            numeric = _float(value.get(key))
            if numeric is not None and numeric > 0.1:
                return "fail"
    return None


def _dedupe_limitations(limitations: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: dict[tuple[str, str], dict[str, Any]] = {}
    for item in limitations:
        deduped[(str(item.get("code")), str(item.get("facet")))] = item
    return list(deduped.values())


def _explicit_limitation_ref(
    candidate: ProductionDataContractCandidate,
    facet: str,
) -> str | None:
    rows = (candidate.raw_contract, candidate.raw_source_binding)
    for row in rows:
        for key in (
            f"{facet}_limitation_ref",
            "limitation_ref",
            "degrade_reason_ref",
        ):
            value = _text(row.get(key))
            if value:
                return value
        diagnostic = row.get("missingness" if facet == "missingness_refs" else "outlier_profile")
        if isinstance(diagnostic, Mapping):
            value = _text(diagnostic.get("limitation_ref") or diagnostic.get("degrade_reason_ref"))
            if value:
                return value
    return None


def _facet_ref(
    *,
    root: Path,
    rows: Sequence[Mapping[str, Any]],
    facet: str,
) -> object | None:
    for row in rows:
        for alias in _FACET_ALIASES[facet]:
            value = _deep_get(row, alias)
            if _path_alias_exists(root=root, alias=alias, value=value) or _present(value):
                return value
    return None


def _path_alias_exists(*, root: Path, alias: str, value: object) -> bool:
    if not alias.endswith("_path") or not isinstance(value, str) or not value.strip():
        return False
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = root / path
    return path.exists()


def _source_family(row: Mapping[str, Any]) -> str:
    for key in (
        "scenario_source_family",
        "source_family",
        "data_source_family",
        "source_family_id",
        "family",
        "dataset_family",
    ):
        value = _text(row.get(key))
        if value:
            return value
    return ""


def _contract_id(row: Mapping[str, Any]) -> str | None:
    for key in ("contract_id", "data_contract_id", "metric_id", "metric_ref", "id"):
        value = _text(row.get(key))
        if value:
            return value
    return None


def _binding_id(row: Mapping[str, Any]) -> str | None:
    for key in ("binding_id", "source_binding_id", "id"):
        value = _text(row.get(key))
        if value:
            return value
    connector = _text(row.get("connector_id"))
    dataset = _text(row.get("dataset_id"))
    if connector and dataset:
        return f"{connector}:{dataset}"
    return None


def _curated_root(
    root: Path,
    bundles: Mapping[str, Mapping[str, Any]],
) -> Path | None:
    bundle = bundles.get("curated")
    if bundle is None:
        for role, candidate in bundles.items():
            role_text = str(role).casefold()
            bundle_role = _text(candidate.get("role")).casefold()
            path_text = _text(candidate.get("path")).casefold()
            if "curated" in {role_text, bundle_role} or "curated" in path_text:
                bundle = candidate
                break
    if bundle is None:
        return None
    raw = _text(bundle.get("path") or bundle.get("component_path"))
    if not raw:
        return None
    path = Path(raw).expanduser()
    return path if path.is_absolute() else root / path


def _manifest_bundles(manifest: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    bundles = manifest.get("bundles")
    if not isinstance(bundles, Mapping):
        return {}
    return {
        str(role): bundle
        for role, bundle in bundles.items()
        if isinstance(bundle, Mapping)
    }


def _load_mapping(path: Path | None) -> Mapping[str, Any]:
    if path is None:
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, Mapping) else {}


def _rows(payload: Mapping[str, Any], key: str) -> list[Mapping[str, Any]]:
    value = payload.get(key)
    if isinstance(value, list):
        return [item for item in value if isinstance(item, Mapping)]
    if isinstance(value, Mapping):
        rows = []
        for row_id, row in value.items():
            if isinstance(row, Mapping):
                row_payload = dict(row)
                row_payload.setdefault("id", str(row_id))
                rows.append(row_payload)
        return rows
    if key == "requirements" and isinstance(payload, list):
        return [item for item in payload if isinstance(item, Mapping)]
    return []


def _deep_get(row: Mapping[str, Any], path: str) -> object | None:
    value: object = row
    for part in path.split("."):
        if not isinstance(value, Mapping):
            return None
        value = value.get(part)
    return value


def _present(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return True
    if isinstance(value, Mapping):
        return any(_present(item) for item in value.values())
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return any(_present(item) for item in value)
    return bool(value)


def _text(value: object) -> str:
    return str(value or "").strip()


def _float(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _json_like(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(key): _json_like(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_json_like(item) for item in value]
    return value


def _safe_ref_component(value: str) -> str:
    return value.replace("/", "_").replace(" ", "_")


__all__ = [
    "PRODUCTION_DATA_CONTRACT_INDEX_SCHEMA_VERSION",
    "SCENARIO_ADMISSIBLE_REQUIRED_FACETS",
    "ProductionDataContractCandidate",
    "ProductionDataContractIndex",
]
