"""Golden production-quality scenario contracts for PolicyOS canaries."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from polisyos.runtime.quality.scenario_evidence_contract import (
    normalize_scenario_evidence_contract,
)

DEFAULT_QUALITY_SCENARIO_ID = "ukraine_msme_wartime_credit_support"
DEFAULT_SCENARIOS_FILE = Path(__file__).with_name("golden_quality_scenarios.json")
REQUIRED_TOP_LEVEL_FIELDS = (
    "scenario_id",
    "request",
    "domain_hint",
    "context",
    "expected_evidence_contract",
)
REQUIRED_CONTEXT_FIELDS = (
    "country",
    "policy_domain",
    "query_outcome",
    "query_treatment",
)
REQUIRED_EVIDENCE_CONTRACT_FIELDS = (
    "normative_fact_classes",
    "admissible_data_source_families",
    "foundry_method_expectations",
    "conflict_checks",
    "unacceptable_recommendations",
)


class QualityScenarioContractError(ValueError):
    """Raised when a golden scenario contract is incomplete or malformed."""

    def __init__(self, failures: list[dict[str, Any]]) -> None:
        self.failures = failures
        super().__init__("quality scenario contract validation failed")


def _failure(
    *,
    code: str = "golden_scenario_contract_missing_field",
    scenario_id: str,
    missing_evidence_type: str,
    message: str,
    next_action: str,
) -> dict[str, Any]:
    return {
        "code": code,
        "layer": "quality_scenarios",
        "phase": "contract_validation",
        "scenario_id": scenario_id,
        "missing_evidence_type": missing_evidence_type,
        "message": message,
        "next_action": next_action,
    }


def _load_catalog(path: Path | None = None) -> dict[str, Any]:
    scenario_path = path or DEFAULT_SCENARIOS_FILE
    payload = json.loads(scenario_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise QualityScenarioContractError(
            [
                _failure(
                    scenario_id="catalog",
                    missing_evidence_type="catalog",
                    message="Scenario catalog must be a JSON object.",
                    next_action="Rewrite the golden scenario catalog as a JSON object.",
                )
            ]
        )
    return payload


def _quarantined_scenario_ids(catalog: dict[str, Any]) -> set[str]:
    packs = catalog.get("scenario_packs")
    if not isinstance(packs, list):
        return set()
    quarantined: set[str] = set()
    for pack in packs:
        if not isinstance(pack, dict):
            continue
        pack_kind = str(pack.get("pack_kind") or "").strip().casefold()
        if pack_kind not in {"hidden", "rotating"}:
            continue
        quarantined.update(str(item) for item in pack.get("scenario_ids") or [])
    return quarantined


def _pack_kind_for_scenario(catalog: dict[str, Any], scenario_id: str) -> str | None:
    packs = catalog.get("scenario_packs")
    if not isinstance(packs, list):
        return None
    for pack in packs:
        if not isinstance(pack, dict):
            continue
        if scenario_id in {str(item) for item in pack.get("scenario_ids") or []}:
            return str(pack.get("pack_kind") or "").strip()
    return None


def _scenario_index(
    path: Path | None = None,
    *,
    include_quarantined: bool = False,
) -> dict[str, dict[str, Any]]:
    catalog = _load_catalog(path)
    scenarios = catalog.get("scenarios")
    if not isinstance(scenarios, list):
        raise QualityScenarioContractError(
            [
                _failure(
                    scenario_id="catalog",
                    missing_evidence_type="scenarios",
                    message="Scenario catalog must contain a scenarios list.",
                    next_action="Add a non-empty scenarios list to the golden scenario catalog.",
                )
            ]
        )
    quarantined_ids = _quarantined_scenario_ids(catalog)
    index: dict[str, dict[str, Any]] = {}
    for item in scenarios:
        if not isinstance(item, dict):
            continue
        scenario_id = str(item.get("scenario_id") or "").strip()
        if scenario_id and (include_quarantined or scenario_id not in quarantined_ids):
            index[scenario_id] = item
    return index


def available_quality_scenario_ids(
    *,
    scenarios_file: Path | None = None,
    include_quarantined: bool = False,
) -> list[str]:
    """Return known golden quality scenario ids."""
    return sorted(
        _scenario_index(
            scenarios_file,
            include_quarantined=include_quarantined,
        ).keys()
    )


def validate_quality_scenario_contract(contract: dict[str, Any]) -> None:
    """Validate one golden scenario contract and raise actionable failures."""
    scenario_id = str(contract.get("scenario_id") or "unknown_scenario")
    failures: list[dict[str, Any]] = []

    for field in REQUIRED_TOP_LEVEL_FIELDS:
        if contract.get(field) in (None, "", [], {}):
            failures.append(
                _failure(
                    scenario_id=scenario_id,
                    missing_evidence_type=field,
                    message=f"Golden scenario is missing required field {field}.",
                    next_action=f"Add {field} to the golden scenario contract.",
                )
            )

    context = contract.get("context")
    if isinstance(context, dict):
        for field in REQUIRED_CONTEXT_FIELDS:
            if context.get(field) in (None, "", [], {}):
                failures.append(
                    _failure(
                        scenario_id=scenario_id,
                        missing_evidence_type=f"context.{field}",
                        message=f"Golden scenario context is missing {field}.",
                        next_action=f"Add context.{field} to the scenario contract.",
                    )
                )

    expected = contract.get("expected_evidence_contract")
    if isinstance(expected, dict):
        for field in REQUIRED_EVIDENCE_CONTRACT_FIELDS:
            if expected.get(field) in (None, "", [], {}):
                failures.append(
                    _failure(
                        scenario_id=scenario_id,
                        missing_evidence_type=field,
                        message=f"Expected evidence contract is missing {field}.",
                        next_action=(
                            "Declare the expected evidence class so quality failures "
                            "can identify the owning layer."
                        ),
                    )
                )

    if failures:
        raise QualityScenarioContractError(failures)


def load_quality_scenario_contract(
    scenario_id: str = DEFAULT_QUALITY_SCENARIO_ID,
    *,
    scenarios_file: Path | None = None,
    include_quarantined: bool = False,
) -> dict[str, Any]:
    """Load and validate one golden quality scenario contract."""
    catalog = _load_catalog(scenarios_file)
    quarantined_ids = _quarantined_scenario_ids(catalog)
    if scenario_id in quarantined_ids and not include_quarantined:
        pack_kind = _pack_kind_for_scenario(catalog, scenario_id) or "quarantined"
        raise QualityScenarioContractError(
            [
                _failure(
                    code="quality_scenario_quarantined",
                    scenario_id=scenario_id,
                    missing_evidence_type="scenario_quarantine",
                    message=(
                        f"Quality scenario {scenario_id} belongs to a quarantined "
                        f"{pack_kind} pack and cannot be loaded through public scenario APIs."
                    ),
                    next_action=(
                        "Pass include_quarantined=True only from benchmark-authority "
                        "internal code that never exports hidden answers."
                    ),
                )
            ]
        )

    index = _scenario_index(
        scenarios_file,
        include_quarantined=include_quarantined,
    )
    if scenario_id not in index:
        raise QualityScenarioContractError(
            [
                _failure(
                    scenario_id=scenario_id,
                    missing_evidence_type="scenario_id",
                    message=f"Unknown quality scenario id {scenario_id}.",
                    next_action=(
                        "Use one of: " + ", ".join(sorted(index))
                        if index
                        else "Add at least one scenario to the catalog."
                    ),
                )
            ]
        )
    contract = dict(index[scenario_id])
    pack_kind = _pack_kind_for_scenario(catalog, scenario_id)
    if pack_kind:
        contract.setdefault("pack", pack_kind)
    validate_quality_scenario_contract(contract)
    contract["scenario_evidence_contract"] = normalize_scenario_evidence_contract(
        contract
    ).to_dict()
    return contract


__all__ = [
    "DEFAULT_QUALITY_SCENARIO_ID",
    "DEFAULT_SCENARIOS_FILE",
    "QualityScenarioContractError",
    "available_quality_scenario_ids",
    "load_quality_scenario_contract",
    "validate_quality_scenario_contract",
]
