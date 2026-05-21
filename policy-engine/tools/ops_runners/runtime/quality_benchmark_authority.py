"""Benchmark-authority scenario packs for runtime quality canaries."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from tools.ops_runners.runtime.quality_scenarios import (
    DEFAULT_SCENARIOS_FILE,
    REQUIRED_EVIDENCE_CONTRACT_FIELDS,
    validate_quality_scenario_contract,
)

REQUIRED_PACK_KINDS: tuple[str, ...] = (
    "public",
    "regression",
    "adversarial",
    "hidden",
    "rotating",
)
QUARANTINED_PACK_KINDS: frozenset[str] = frozenset({"hidden", "rotating"})
PROTECTED_PUBLIC_SURFACES: frozenset[str] = frozenset(
    {"public_export", "reusable_memory", "dashboard_fixture"}
)
REQUIRED_THRESHOLD_FIELDS: tuple[str, ...] = (
    "min_contract_coverage",
    "min_admissible_source_hits",
    "max_unacceptable_recommendations",
)
HIDDEN_ANSWER_FIELDS: tuple[str, ...] = (
    "hidden_answer",
    "answer_key",
    "rubric_secret",
)
SENTINEL_STRING_FIELDS: tuple[str, ...] = ("sentinel_strings",)


@dataclass(frozen=True)
class BenchmarkContaminationPolicy:
    """Hidden strings that cannot enter public/exportable artifacts."""

    hidden_answers: frozenset[str] = field(default_factory=frozenset)
    sentinel_strings: frozenset[str] = field(default_factory=frozenset)
    protected_surfaces: frozenset[str] = field(default_factory=lambda: PROTECTED_PUBLIC_SURFACES)


class BenchmarkAuthorityValidationError(ValueError):
    """Raised when benchmark-authority pack metadata is incomplete."""

    def __init__(self, failures: list[dict[str, Any]]) -> None:
        self.failures = failures
        super().__init__("quality benchmark authority validation failed")


class BenchmarkContaminationError(ValueError):
    """Raised when hidden benchmark tokens reach a protected surface."""

    def __init__(self, *, surface: str, findings: list[dict[str, str]]) -> None:
        self.surface = surface
        self.findings = findings
        tokens = ", ".join(
            f"{finding['token_kind']}:{finding['token']}" for finding in findings
        )
        super().__init__(f"{surface} benchmark contamination detected: {tokens}")


class QuarantinedScenarioAccessError(PermissionError):
    """Raised when hidden or rotating packs are loaded without explicit opt-in."""

    def __init__(self, *, pack_id: str, pack_kind: str) -> None:
        self.pack_id = pack_id
        self.pack_kind = pack_kind
        super().__init__(
            f"Scenario pack {pack_id} is quarantined as {pack_kind}; "
            "pass include_quarantined=True for authority-internal access."
        )


def load_quality_benchmark_catalog(
    *,
    scenarios_file: Path | None = None,
) -> dict[str, Any]:
    """Load and validate the benchmark-authority scenario catalog."""

    path = scenarios_file or DEFAULT_SCENARIOS_FILE
    catalog = json.loads(path.read_text(encoding="utf-8"))
    failures = validate_quality_benchmark_catalog(catalog)
    if failures:
        raise BenchmarkAuthorityValidationError(failures)
    return catalog


def validate_quality_benchmark_catalog(catalog: dict[str, Any]) -> list[dict[str, Any]]:
    """Return actionable validation failures for the benchmark-authority catalog."""

    failures: list[dict[str, Any]] = []
    scenarios = catalog.get("scenarios")
    packs = catalog.get("scenario_packs")
    if not isinstance(scenarios, list):
        return [_failure("catalog_missing_scenarios", "Catalog must declare scenarios.")]
    if not isinstance(packs, list):
        return [
            _failure(
                "catalog_missing_scenario_packs",
                "Catalog must declare scenario_packs for benchmark authority.",
            )
        ]

    scenario_index: dict[str, dict[str, Any]] = {}
    for scenario in scenarios:
        if not isinstance(scenario, dict):
            failures.append(_failure("invalid_scenario", "Scenario entries must be objects."))
            continue
        scenario_id = str(scenario.get("scenario_id") or "").strip()
        if not scenario_id:
            failures.append(_failure("scenario_missing_id", "Scenario is missing scenario_id."))
            continue
        try:
            validate_quality_scenario_contract(scenario)
        except Exception as exc:  # pragma: no cover - failure details live in old validator
            failures.append(
                _failure(
                    "scenario_contract_invalid",
                    f"Scenario {scenario_id} failed quality contract validation: {exc}.",
                    scenario_id=scenario_id,
                )
            )
        scenario_index[scenario_id] = scenario

    pack_kinds: set[str] = set()
    assigned_ids: list[str] = []
    for pack in packs:
        if not isinstance(pack, dict):
            failures.append(_failure("invalid_pack", "Scenario pack entries must be objects."))
            continue
        failures.extend(_validate_pack(pack, scenario_index=scenario_index))
        pack_kind = str(pack.get("pack_kind") or "").strip()
        if pack_kind:
            pack_kinds.add(pack_kind)
        assigned_ids.extend(str(item) for item in pack.get("scenario_ids") or [])

    missing_kinds = set(REQUIRED_PACK_KINDS) - pack_kinds
    for pack_kind in sorted(missing_kinds):
        failures.append(
            _failure(
                "missing_pack_kind",
                f"Scenario catalog is missing required {pack_kind} pack.",
                pack_kind=pack_kind,
            )
        )

    duplicate_ids = sorted(
        scenario_id for scenario_id in set(assigned_ids) if assigned_ids.count(scenario_id) > 1
    )
    for scenario_id in duplicate_ids:
        failures.append(
            _failure(
                "duplicate_scenario_pack_assignment",
                f"Scenario {scenario_id} is assigned to more than one pack.",
                scenario_id=scenario_id,
            )
        )
    unassigned_ids = set(scenario_index) - set(assigned_ids)
    for scenario_id in sorted(unassigned_ids):
        failures.append(
            _failure(
                "unassigned_scenario",
                f"Scenario {scenario_id} is not assigned to an authority pack.",
                scenario_id=scenario_id,
            )
        )

    policy = contamination_policy_from_catalog(catalog)
    if not policy.hidden_answers:
        failures.append(
            _failure(
                "missing_hidden_answer_tokens",
                "Hidden packs must declare at least one hidden answer token.",
            )
        )
    if not policy.sentinel_strings:
        failures.append(
            _failure(
                "missing_sentinel_tokens",
                "Quarantined packs must declare sentinel strings.",
            )
        )

    return failures


def load_scenario_pack(
    pack_id: str,
    *,
    scenarios_file: Path | None = None,
    include_quarantined: bool = False,
) -> dict[str, Any]:
    """Load one scenario pack, blocking hidden/rotating packs unless opted in."""

    catalog = load_quality_benchmark_catalog(scenarios_file=scenarios_file)
    pack = _pack_by_id(catalog, pack_id)
    pack_kind = str(pack["pack_kind"])
    if pack_kind in QUARANTINED_PACK_KINDS and not include_quarantined:
        raise QuarantinedScenarioAccessError(pack_id=pack_id, pack_kind=pack_kind)
    return _pack_with_scenarios(catalog, pack)


def export_public_scenario_pack(
    *,
    scenarios_file: Path | None = None,
) -> dict[str, Any]:
    """Return the inspectable public pack with quarantined scenario content removed."""

    catalog = load_quality_benchmark_catalog(scenarios_file=scenarios_file)
    public_pack = next(
        pack for pack in catalog["scenario_packs"] if pack.get("pack_kind") == "public"
    )
    pack = _pack_with_scenarios(catalog, public_pack)
    scenarios = [_strip_private_fields(scenario) for scenario in pack["scenarios"]]
    export = {
        "schema_version": "policyos.quality_benchmark_authority.public_export.v1",
        "source_schema_version": catalog.get("schema_version"),
        "pack_id": pack["pack_id"],
        "pack_kind": pack["pack_kind"],
        "visibility": pack["visibility"],
        "expected_evidence_contract": pack["expected_evidence_contract"],
        "pass_fail_thresholds": pack["pass_fail_thresholds"],
        "scenarios": scenarios,
        "quarantined_pack_counts": _quarantined_pack_counts(catalog),
    }
    assert_no_benchmark_contamination(export, surface="public_export", catalog=catalog)
    return export


def quarantined_scenario_ids(
    *,
    scenarios_file: Path | None = None,
) -> list[str]:
    """Return scenario ids that belong to hidden or rotating packs."""

    catalog = load_quality_benchmark_catalog(scenarios_file=scenarios_file)
    output: list[str] = []
    for pack in catalog["scenario_packs"]:
        if str(pack.get("pack_kind")) in QUARANTINED_PACK_KINDS:
            output.extend(str(scenario_id) for scenario_id in pack.get("scenario_ids") or [])
    return sorted(output)


def contamination_policy_from_catalog(
    catalog: dict[str, Any] | None = None,
    *,
    scenarios_file: Path | None = None,
) -> BenchmarkContaminationPolicy:
    """Build contamination tokens from quarantined hidden and rotating scenarios."""

    active_catalog = catalog or _load_raw_catalog(scenarios_file)
    hidden_answers: set[str] = set()
    sentinel_strings: set[str] = set()
    for scenario in _quarantined_scenarios(active_catalog):
        for field_name in HIDDEN_ANSWER_FIELDS:
            hidden_answers.update(_leaf_strings(scenario.get(field_name)))
        for field_name in SENTINEL_STRING_FIELDS:
            sentinel_strings.update(_leaf_strings(scenario.get(field_name)))
    return BenchmarkContaminationPolicy(
        hidden_answers=frozenset(hidden_answers),
        sentinel_strings=frozenset(sentinel_strings),
    )


def detect_benchmark_contamination(
    payload: Any,
    *,
    surface: str,
    policy: BenchmarkContaminationPolicy | None = None,
    catalog: dict[str, Any] | None = None,
    scenarios_file: Path | None = None,
) -> list[dict[str, str]]:
    """Return hidden-answer and sentinel-string findings for a protected payload."""

    active_policy = policy or contamination_policy_from_catalog(
        catalog,
        scenarios_file=scenarios_file,
    )
    if surface not in active_policy.protected_surfaces:
        return []
    rendered = json.dumps(payload, sort_keys=True, default=str)
    findings: list[dict[str, str]] = []
    for token in sorted(active_policy.hidden_answers, key=len, reverse=True):
        if token and token in rendered:
            findings.append(
                {
                    "surface": surface,
                    "token_kind": "hidden_answer",
                    "token": token,
                    "message": "hidden benchmark answer leaked into protected artifact",
                }
            )
    for token in sorted(active_policy.sentinel_strings, key=len, reverse=True):
        if token and token in rendered:
            findings.append(
                {
                    "surface": surface,
                    "token_kind": "sentinel_string",
                    "token": token,
                    "message": "hidden benchmark sentinel string leaked into protected artifact",
                }
            )
    return _dedupe_findings(findings)


def assert_no_benchmark_contamination(
    payload: Any,
    *,
    surface: str,
    policy: BenchmarkContaminationPolicy | None = None,
    catalog: dict[str, Any] | None = None,
    scenarios_file: Path | None = None,
) -> None:
    """Raise if hidden answers or sentinel strings appear on a protected surface."""

    findings = detect_benchmark_contamination(
        payload,
        surface=surface,
        policy=policy,
        catalog=catalog,
        scenarios_file=scenarios_file,
    )
    if findings:
        raise BenchmarkContaminationError(surface=surface, findings=findings)


def _load_raw_catalog(scenarios_file: Path | None = None) -> dict[str, Any]:
    path = scenarios_file or DEFAULT_SCENARIOS_FILE
    return json.loads(path.read_text(encoding="utf-8"))


def _validate_pack(
    pack: dict[str, Any],
    *,
    scenario_index: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    pack_id = str(pack.get("pack_id") or "").strip()
    pack_kind = str(pack.get("pack_kind") or "").strip()
    if not pack_id:
        failures.append(_failure("pack_missing_id", "Scenario pack is missing pack_id."))
    if pack_kind not in REQUIRED_PACK_KINDS:
        failures.append(
            _failure(
                "invalid_pack_kind",
                f"Scenario pack {pack_id or '<unknown>'} has invalid kind {pack_kind}.",
                pack_id=pack_id,
                pack_kind=pack_kind,
            )
        )
    scenario_ids = pack.get("scenario_ids")
    if not isinstance(scenario_ids, list) or not scenario_ids:
        failures.append(
            _failure(
                "pack_missing_scenario_ids",
                f"Scenario pack {pack_id or '<unknown>'} must list scenario_ids.",
                pack_id=pack_id,
                pack_kind=pack_kind,
            )
        )
    else:
        for scenario_id in scenario_ids:
            if str(scenario_id) not in scenario_index:
                failures.append(
                    _failure(
                        "pack_unknown_scenario_id",
                        f"Scenario pack {pack_id} references unknown scenario {scenario_id}.",
                        pack_id=pack_id,
                        pack_kind=pack_kind,
                        scenario_id=str(scenario_id),
                    )
                )
    failures.extend(_validate_pack_evidence(pack, pack_id=pack_id, pack_kind=pack_kind))
    failures.extend(_validate_pack_thresholds(pack, pack_id=pack_id, pack_kind=pack_kind))
    failures.extend(_validate_quarantine(pack, pack_id=pack_id, pack_kind=pack_kind))
    return failures


def _validate_pack_evidence(
    pack: dict[str, Any],
    *,
    pack_id: str,
    pack_kind: str,
) -> list[dict[str, Any]]:
    evidence = pack.get("expected_evidence_contract")
    if not isinstance(evidence, dict):
        return [
            _failure(
                "pack_missing_evidence_contract",
                f"Scenario pack {pack_id} must declare expected_evidence_contract.",
                pack_id=pack_id,
                pack_kind=pack_kind,
            )
        ]
    failures: list[dict[str, Any]] = []
    for field_name in REQUIRED_EVIDENCE_CONTRACT_FIELDS:
        if evidence.get(field_name) in (None, "", [], {}):
            failures.append(
                _failure(
                    "pack_evidence_contract_missing_field",
                    f"Scenario pack {pack_id} missing evidence field {field_name}.",
                    pack_id=pack_id,
                    pack_kind=pack_kind,
                    missing_evidence_type=field_name,
                )
            )
    return failures


def _validate_pack_thresholds(
    pack: dict[str, Any],
    *,
    pack_id: str,
    pack_kind: str,
) -> list[dict[str, Any]]:
    thresholds = pack.get("pass_fail_thresholds")
    if not isinstance(thresholds, dict):
        return [
            _failure(
                "pack_missing_thresholds",
                f"Scenario pack {pack_id} must declare pass_fail_thresholds.",
                pack_id=pack_id,
                pack_kind=pack_kind,
            )
        ]
    failures: list[dict[str, Any]] = []
    for field_name in REQUIRED_THRESHOLD_FIELDS:
        if thresholds.get(field_name) is None:
            failures.append(
                _failure(
                    "pack_threshold_missing_field",
                    f"Scenario pack {pack_id} missing threshold {field_name}.",
                    pack_id=pack_id,
                    pack_kind=pack_kind,
                )
            )
    if float(thresholds.get("min_contract_coverage") or 0) <= 0:
        failures.append(
            _failure(
                "pack_threshold_invalid_contract_coverage",
                f"Scenario pack {pack_id} must require positive contract coverage.",
                pack_id=pack_id,
                pack_kind=pack_kind,
            )
        )
    if int(thresholds.get("min_admissible_source_hits") or 0) < 1:
        failures.append(
            _failure(
                "pack_threshold_invalid_source_hits",
                f"Scenario pack {pack_id} must require admissible source hits.",
                pack_id=pack_id,
                pack_kind=pack_kind,
            )
        )
    max_unacceptable = thresholds.get("max_unacceptable_recommendations")
    if max_unacceptable is None or int(max_unacceptable) != 0:
        failures.append(
            _failure(
                "pack_threshold_invalid_unacceptable_recommendations",
                f"Scenario pack {pack_id} must fail on unacceptable recommendations.",
                pack_id=pack_id,
                pack_kind=pack_kind,
            )
        )
    return failures


def _validate_quarantine(
    pack: dict[str, Any],
    *,
    pack_id: str,
    pack_kind: str,
) -> list[dict[str, Any]]:
    quarantine = pack.get("quarantine")
    if pack_kind not in QUARANTINED_PACK_KINDS:
        return []
    if not isinstance(quarantine, dict) or not quarantine.get("reason"):
        return [
            _failure(
                "quarantined_pack_missing_policy",
                f"Scenario pack {pack_id} is quarantined but lacks quarantine metadata.",
                pack_id=pack_id,
                pack_kind=pack_kind,
            )
        ]
    return []


def _pack_by_id(catalog: dict[str, Any], pack_id: str) -> dict[str, Any]:
    for pack in catalog["scenario_packs"]:
        if pack.get("pack_id") == pack_id:
            return dict(pack)
    raise KeyError(f"Unknown scenario pack {pack_id}")


def _pack_with_scenarios(catalog: dict[str, Any], pack: dict[str, Any]) -> dict[str, Any]:
    scenario_index = {
        str(scenario["scenario_id"]): scenario for scenario in catalog["scenarios"]
    }
    pack_kind = str(pack["pack_kind"])
    output = dict(pack)
    output["scenarios"] = [
        {**scenario_index[str(scenario_id)], "pack_kind": pack_kind}
        for scenario_id in pack["scenario_ids"]
    ]
    return output


def _quarantined_pack_counts(catalog: dict[str, Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for pack in catalog["scenario_packs"]:
        pack_kind = str(pack.get("pack_kind"))
        if pack_kind in QUARANTINED_PACK_KINDS:
            counts[pack_kind] = len(pack.get("scenario_ids") or [])
    return counts


def _quarantined_scenarios(catalog: dict[str, Any]) -> list[dict[str, Any]]:
    scenario_index = {
        str(scenario.get("scenario_id")): scenario
        for scenario in catalog.get("scenarios", [])
        if isinstance(scenario, dict)
    }
    output: list[dict[str, Any]] = []
    for pack in catalog.get("scenario_packs", []):
        if not isinstance(pack, dict):
            continue
        if str(pack.get("pack_kind")) not in QUARANTINED_PACK_KINDS:
            continue
        for scenario_id in pack.get("scenario_ids") or []:
            scenario = scenario_index.get(str(scenario_id))
            if scenario is not None:
                output.append(scenario)
    return output


def _strip_private_fields(scenario: dict[str, Any]) -> dict[str, Any]:
    scrubbed = dict(scenario)
    for field_name in (*HIDDEN_ANSWER_FIELDS, *SENTINEL_STRING_FIELDS, "rotation"):
        scrubbed.pop(field_name, None)
    return scrubbed


def _leaf_strings(value: Any) -> set[str]:
    if isinstance(value, str):
        text = value.strip()
        return {text} if text else set()
    if isinstance(value, dict):
        output: set[str] = set()
        for item in value.values():
            output.update(_leaf_strings(item))
        return output
    if isinstance(value, list | tuple | set):
        output: set[str] = set()
        for item in value:
            output.update(_leaf_strings(item))
        return output
    return set()


def _dedupe_findings(findings: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[tuple[str, str, str]] = set()
    output: list[dict[str, str]] = []
    for finding in findings:
        key = (finding["surface"], finding["token_kind"], finding["token"])
        if key in seen:
            continue
        seen.add(key)
        output.append(finding)
    return output


def _failure(
    code: str,
    message: str,
    *,
    pack_id: str | None = None,
    pack_kind: str | None = None,
    scenario_id: str | None = None,
    missing_evidence_type: str | None = None,
) -> dict[str, Any]:
    return {
        "code": code,
        "layer": "quality_benchmark_authority",
        "phase": "scenario_pack_validation",
        "pack_id": pack_id,
        "pack_kind": pack_kind,
        "scenario_id": scenario_id,
        "missing_evidence_type": missing_evidence_type,
        "message": message,
        "next_action": "Update golden_quality_scenarios.json benchmark-authority metadata.",
    }


__all__ = [
    "BenchmarkAuthorityValidationError",
    "BenchmarkContaminationError",
    "BenchmarkContaminationPolicy",
    "HIDDEN_ANSWER_FIELDS",
    "PROTECTED_PUBLIC_SURFACES",
    "QUARANTINED_PACK_KINDS",
    "QuarantinedScenarioAccessError",
    "REQUIRED_EVIDENCE_CONTRACT_FIELDS",
    "REQUIRED_PACK_KINDS",
    "REQUIRED_THRESHOLD_FIELDS",
    "SENTINEL_STRING_FIELDS",
    "assert_no_benchmark_contamination",
    "contamination_policy_from_catalog",
    "detect_benchmark_contamination",
    "export_public_scenario_pack",
    "load_quality_benchmark_catalog",
    "load_scenario_pack",
    "quarantined_scenario_ids",
    "validate_quality_benchmark_catalog",
]
