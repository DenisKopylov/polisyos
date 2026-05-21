#!/usr/bin/env python3
"""Build provider/model quality drift ledgers from canary lane evidence."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Iterable

from polisyos.scientist.orchestration.llm.provider_quality import (
    SCHEMA_VERSION,
    DefaultProductionModelChoice,
    ProviderModelQualityObservation,
    build_controlled_provider_model_comparison,
    build_provider_model_quality_ledger,
)

OBSERVATIONS_FILE = "provider_model_quality_observations.json"
DEFAULT_INPUT_ROOT = Path(".polisyos/canary_evidence")
DEFAULT_OUTPUT = Path(".polisyos/provider_quality/provider_model_quality_ledger.json")


def collect_observations_from_bundle(bundle_dir: Path) -> list[ProviderModelQualityObservation]:
    """Collect provider/model quality observations from one evidence bundle."""
    direct = _load_observations_file(bundle_dir)
    if direct:
        return direct
    return _observations_from_llm_variants(bundle_dir)


def collect_observations(input_root: Path) -> list[ProviderModelQualityObservation]:
    """Collect observations from all canary bundles under an input root."""
    if not input_root.exists():
        return []
    bundle_dirs = sorted({path.parent for path in input_root.rglob("bundle.json")})
    observations: list[ProviderModelQualityObservation] = []
    for bundle_dir in bundle_dirs:
        observations.extend(collect_observations_from_bundle(bundle_dir))
    return observations


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    input_root = Path(args.input_root).expanduser()
    output = Path(args.output).expanduser()
    observations = collect_observations(input_root)
    if not observations:
        parser.error(f"no provider quality observations found under {input_root}")

    generated_at = _parse_datetime(args.generated_at) if args.generated_at else None
    default_models = [_parse_default_model(value) for value in args.default_production_model]
    ledger = build_provider_model_quality_ledger(
        observations,
        default_model_choices=default_models,
        generated_at=generated_at,
        max_evidence_age_days=args.max_evidence_age_days,
        hidden_answer_tokens=args.hidden_answer_token,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            ledger.model_dump(mode="json", exclude_none=True),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    if args.controlled_grounding_comparison_output:
        candidate_models = [
            _parse_candidate_model(value) for value in args.candidate_model
        ]
        default_controlled = (
            _parse_default_model(args.default_controlled_model)
            if args.default_controlled_model
            else (default_models[0] if default_models else None)
        )
        if not candidate_models:
            parser.error("--candidate-model is required for controlled grounding comparison")
        if default_controlled is None:
            parser.error(
                "--default-controlled-model or --default-production-model is required "
                "for controlled grounding comparison"
            )
        comparison = build_controlled_provider_model_comparison(
            observations,
            candidate_models=candidate_models,
            default_model_choice=default_controlled,
            generated_at=generated_at,
            min_samples_per_model=args.min_controlled_samples_per_model,
            hidden_answer_tokens=args.hidden_answer_token,
        )
        comparison_output = Path(args.controlled_grounding_comparison_output).expanduser()
        comparison_output.parent.mkdir(parents=True, exist_ok=True)
        comparison_output.write_text(
            json.dumps(
                comparison.model_dump(mode="json", exclude_none=True),
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input-root",
        default=str(DEFAULT_INPUT_ROOT),
        help="Directory containing canary evidence bundles.",
    )
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT),
        help="Path for the provider/model quality ledger JSON.",
    )
    parser.add_argument(
        "--generated-at",
        help="Optional deterministic ISO timestamp for the generated ledger.",
    )
    parser.add_argument(
        "--default-production-model",
        action="append",
        default=[],
        metavar="PROVIDER:MODEL:FINGERPRINT:USAGE",
        help="Default model choice that must have fresh quality evidence.",
    )
    parser.add_argument(
        "--max-evidence-age-days",
        type=int,
        default=14,
        help="Maximum age for default production model quality evidence.",
    )
    parser.add_argument(
        "--hidden-answer-token",
        action="append",
        default=[],
        help="Hidden benchmark token that must be redacted from retained samples.",
    )
    parser.add_argument(
        "--controlled-grounding-comparison-output",
        default="",
        help="Optional path for Qwen/Kimi controlled grounding comparison JSON.",
    )
    parser.add_argument(
        "--candidate-model",
        action="append",
        default=[],
        metavar="PROVIDER:MODEL:FINGERPRINT",
        help="Candidate model to include in controlled grounding comparison.",
    )
    parser.add_argument(
        "--default-controlled-model",
        default="",
        metavar="PROVIDER:MODEL:FINGERPRINT:USAGE",
        help="Default model candidate to gate on controlled grounding evidence.",
    )
    parser.add_argument(
        "--min-controlled-samples-per-model",
        type=int,
        default=3,
        help="Minimum bounded controlled samples required for each candidate model.",
    )
    return parser


def _load_observations_file(bundle_dir: Path) -> list[ProviderModelQualityObservation]:
    candidates = [
        bundle_dir / "quality_evidence" / OBSERVATIONS_FILE,
        bundle_dir / OBSERVATIONS_FILE,
    ]
    bundle = _load_json(bundle_dir / "bundle.json")
    upstream_blockers = _upstream_spine_blocker_refs_from_bundle(bundle_dir)
    quality_files = ((bundle or {}).get("files") or {}).get("quality_evidence")
    if isinstance(quality_files, dict):
        raw_path = quality_files.get("provider_model_quality_observations")
        if isinstance(raw_path, str) and raw_path.strip():
            candidates.insert(0, bundle_dir / raw_path)

    for candidate in candidates:
        payload = _load_json(candidate)
        if payload is None:
            continue
        raw_observations = payload.get("observations") if isinstance(payload, dict) else payload
        if not isinstance(raw_observations, list):
            continue
        return [
            _with_bundle_confounding(
                ProviderModelQualityObservation.model_validate(item),
                upstream_blocker_refs=upstream_blockers,
            )
            for item in raw_observations
            if isinstance(item, dict)
        ]
    return []


def _observations_from_llm_variants(bundle_dir: Path) -> list[ProviderModelQualityObservation]:
    bundle = _load_json(bundle_dir / "bundle.json") or {}
    lane_id = _lane_id(bundle, bundle_dir=bundle_dir)
    lane_kind = _lane_kind(bundle, lane_id=lane_id)
    scenario_pack_id = _scenario_pack_id(bundle_dir, bundle)
    observed_at = _parse_datetime(
        str(bundle.get("created_at") or datetime.now(UTC).isoformat())
    )
    upstream_blockers = _upstream_spine_blocker_refs_from_bundle(bundle_dir)
    observations: list[ProviderModelQualityObservation] = []
    for surface in ("job.json", "run.json", "agents.json"):
        payload = _load_json(bundle_dir / surface)
        for variant in _nested_find_all(payload, "llm_model_variants"):
            if not isinstance(variant, list):
                continue
            for index, item in enumerate(variant):
                if isinstance(item, dict):
                    observations.append(
                        _observation_from_variant(
                            item,
                            lane_id=lane_id,
                            lane_kind=lane_kind,
                            scenario_pack_id=scenario_pack_id,
                            observed_at=observed_at,
                            index=index,
                            upstream_spine_blocker_refs=upstream_blockers,
                        )
                    )
    return observations


def _observation_from_variant(
    variant: dict[str, Any],
    *,
    lane_id: str,
    lane_kind: str,
    scenario_pack_id: str,
    observed_at: datetime,
    index: int,
    upstream_spine_blocker_refs: list[str] | None = None,
) -> ProviderModelQualityObservation:
    failure_code = variant.get("failure_code")
    schema_valid = failure_code != "llm_formalizer_schema_validation_failed"
    provider_error_code = variant.get("provider_error_code") or failure_code
    observation = ProviderModelQualityObservation(
        observation_id=str(variant.get("model_variant_id") or f"{lane_id}-{index}"),
        lane_id=lane_id,
        lane_kind=lane_kind,
        provider=str(variant.get("provider") or "unknown_provider"),
        model_id=str(variant.get("model") or variant.get("model_id") or "unknown_model"),
        model_fingerprint=str(
            variant.get("model_fingerprint")
            or variant.get("fingerprint")
            or variant.get("model")
            or "unknown_fingerprint"
        ),
        scenario_pack_id=scenario_pack_id,
        scenario_id=variant.get("scenario_id"),
        observed_at=observed_at,
        schema_valid=schema_valid,
        healing_count=int(variant.get("schema_healing_count") or 0),
        json_valid=bool(variant.get("json_valid", schema_valid)),
        tool_call_valid=bool(variant.get("tool_call_valid", True)),
        grounding_valid=bool(variant.get("grounding_valid", True)),
        citation_faithfulness_valid=bool(
            variant.get("citation_faithfulness_valid", True)
        ),
        disagreement_detected=bool(variant.get("disagreement_detected", False)),
        latency_ms=_optional_float(variant.get("latency_ms")),
        cost_usd=_optional_float(variant.get("cost_usd") or variant.get("estimated_cost_usd")),
        context_pressure=_optional_float(variant.get("context_pressure")),
        provider_error_code=str(provider_error_code) if provider_error_code else None,
        selected_variant_quality=_optional_float(
            variant.get("selected_variant_quality") or variant.get("quality_score")
        ),
        quarantined=lane_kind == "quarantined_live",
        raw_evidence={
            key: value
            for key, value in variant.items()
            if key
            in {
                "failure_code",
                "model_variant_id",
                "provider_error_code",
                "request_id",
                "status",
            }
        },
    )
    return _with_bundle_confounding(
        observation,
        upstream_blocker_refs=upstream_spine_blocker_refs or [],
    )


def _with_bundle_confounding(
    observation: ProviderModelQualityObservation,
    *,
    upstream_blocker_refs: list[str],
) -> ProviderModelQualityObservation:
    if not upstream_blocker_refs:
        return observation
    live_lane = observation.lane_kind == "quarantined_live" or observation.quarantined
    if not live_lane:
        return observation
    return observation.model_copy(
        update={
            "system_confounded": True,
            "confounding_signal": "upstream_evidence_spine_incomplete",
            "upstream_spine_blocker_refs": list(upstream_blocker_refs),
        }
    )


def _upstream_spine_blocker_refs_from_bundle(bundle_dir: Path) -> list[str]:
    refs: list[str] = []
    for relative, family in (
        ("quality_evidence/scenario_contract_propagation_graph.json", "evidence_spine"),
        ("quality_evidence/claim_registry.json", "claim_registry"),
        ("quality_evidence/semantic_binding_ledger.json", "semantic_binding"),
        ("quality_evidence/policy_design_case.json", "policy_design_case"),
        ("quality_evidence/can_i_closeout_compatibility.json", "closeout"),
    ):
        payload = _load_json(bundle_dir / relative)
        refs.extend(_blocker_refs_from_payload(payload, relative=relative, family=family))
    scorecard = _load_json(bundle_dir / "quality_evidence" / "quality_scorecard.json")
    refs.extend(_scorecard_upstream_blocker_refs(scorecard))
    return sorted(dict.fromkeys(refs))


def _blocker_refs_from_payload(
    payload: object | None,
    *,
    relative: str,
    family: str,
) -> list[str]:
    if not isinstance(payload, dict):
        return []
    refs: list[str] = []
    status = str(payload.get("status") or payload.get("quality_status") or "").casefold()
    if status in {"fail", "failed", "blocked", "block"}:
        refs.append(f"{relative}#/{family}_status:{status}")
    for key in ("findings", "issues", "blockers", "diagnostics"):
        value = payload.get(key)
        if not isinstance(value, list):
            continue
        for index, item in enumerate(value):
            if not isinstance(item, dict):
                continue
            code = str(item.get("code") or item.get("finding_code") or "").strip()
            item_status = str(item.get("status") or "").casefold()
            if code or item_status in {"fail", "failed", "blocked", "block"}:
                refs.append(f"{relative}#/{key}/{index}:{code or item_status}")
    if family == "policy_design_case" and (
        not payload.get("records") or not payload.get("record_families")
    ):
        refs.append(f"{relative}#/record_families:pdc_record_families_missing")
    return refs


def _scorecard_upstream_blocker_refs(scorecard: object | None) -> list[str]:
    if not isinstance(scorecard, dict):
        return []
    gates = scorecard.get("quality_gates")
    if not isinstance(gates, list):
        return []
    refs: list[str] = []
    needles = (
        "evidence_spine",
        "scenario_contract",
        "claim_registry",
        "semantic_binding",
        "policy_design_case",
        "pdc",
        "closeout",
    )
    for index, gate in enumerate(gates):
        if not isinstance(gate, dict):
            continue
        status = str(gate.get("status") or "").casefold()
        if status not in {"fail", "failed", "blocked", "block"}:
            continue
        haystack = " ".join(
            str(gate.get(key) or "")
            for key in ("name", "phase", "code", "root_cause_class")
        ).casefold()
        if any(needle in haystack for needle in needles):
            code = str(gate.get("code") or "upstream_spine_blocker")
            refs.append(f"quality_evidence/quality_scorecard.json#/quality_gates/{index}:{code}")
    return refs


def _parse_default_model(value: str) -> DefaultProductionModelChoice:
    provider, model_id, model_fingerprint, usage = value.split(":", 3)
    return DefaultProductionModelChoice(
        provider=provider,
        model_id=model_id,
        model_fingerprint=model_fingerprint,
        usage=usage,
    )


def _parse_candidate_model(value: str) -> DefaultProductionModelChoice:
    provider, model_id, model_fingerprint = value.split(":", 2)
    return DefaultProductionModelChoice(
        provider=provider,
        model_id=model_id,
        model_fingerprint=model_fingerprint,
        usage="controlled_grounding_candidate",
    )


def _parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _load_json(path: Path) -> object | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _lane_id(bundle: dict[str, Any], *, bundle_dir: Path) -> str:
    command = bundle.get("command")
    if isinstance(command, dict):
        value = command.get("matrix_lane_id") or command.get("lane_id")
        if isinstance(value, str) and value.strip():
            return value.strip()
    return bundle_dir.name


def _lane_kind(bundle: dict[str, Any], *, lane_id: str) -> str:
    provider = ""
    command = bundle.get("command")
    if isinstance(command, dict):
        provider = str(command.get("provider") or "")
    haystack = f"{provider} {lane_id}".casefold()
    if "live" in haystack or "gonka" in haystack:
        return "quarantined_live"
    return "simulated"


def _scenario_pack_id(bundle_dir: Path, bundle: dict[str, Any]) -> str:
    for path in (
        bundle_dir / "quality_evidence" / "golden_scenario_contract.json",
        bundle_dir / "golden_scenario_contract.json",
    ):
        payload = _load_json(path)
        if isinstance(payload, dict):
            pack_id = payload.get("scenario_pack_id") or payload.get("pack_id")
            if isinstance(pack_id, str) and pack_id.strip():
                return pack_id.strip()
            scenario_id = payload.get("scenario_id")
            if isinstance(scenario_id, str) and scenario_id.strip():
                return scenario_id.strip()
    command = bundle.get("command")
    if isinstance(command, dict):
        pack_id = command.get("scenario_pack_id") or command.get("scenario_id")
        if isinstance(pack_id, str) and pack_id.strip():
            return pack_id.strip()
    return "unknown_scenario_pack"


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _nested_find_all(payload: object, key: str) -> Iterable[object]:
    if isinstance(payload, dict):
        if key in payload:
            yield payload[key]
        for value in payload.values():
            yield from _nested_find_all(value, key)
    elif isinstance(payload, list):
        for value in payload:
            yield from _nested_find_all(value, key)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())


__all__ = [
    "DEFAULT_INPUT_ROOT",
    "DEFAULT_OUTPUT",
    "OBSERVATIONS_FILE",
    "SCHEMA_VERSION",
    "collect_observations",
    "collect_observations_from_bundle",
    "main",
]
