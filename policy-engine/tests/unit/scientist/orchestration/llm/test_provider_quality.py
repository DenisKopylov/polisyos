from __future__ import annotations

import hashlib
import json
import math
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from polisyos.runtime.quality.scorecard import build_quality_scorecard
from polisyos.scientist.orchestration.llm.provider_quality import (
    CONTROLLED_GROUNDING_TASK_ID,
    DEFAULT_CONTROLLED_GROUNDING_SCENARIO_PACK_ID,
    DefaultProductionModelChoice,
    ProviderCostOrigin,
    ProviderCostStatus,
    ProviderModelQualityLedger,
    ProviderModelQualityObservation,
    ProviderModelQualityThresholds,
    _ledger_ref,
    build_controlled_grounding_observation,
    build_controlled_provider_model_comparison,
    build_provider_model_quality_ledger,
    compare_provider_models,
    controlled_grounding_task,
    provider_model_evidence_key,
)

NOW = datetime(2026, 5, 13, 12, 0, tzinfo=UTC)


def _observation(
    *,
    provider: str = "simulated",
    model_id: str = "policyos-sim-v1",
    model_fingerprint: str = "fixture-fp",
    lane_kind: str = "simulated",
    scenario_pack_id: str = "public_golden_pack",
    schema_valid: bool = True,
    healing_count: int = 0,
    json_valid: bool = True,
    tool_call_valid: bool = True,
    grounding_valid: bool = True,
    citation_faithfulness_valid: bool = True,
    disagreement_detected: bool = False,
    latency_ms: float = 100.0,
    cost_usd: float | None = 0.0,
    estimated_cost_usd: float | None = None,
    cost_status: ProviderCostStatus = "known",
    cost_origin: ProviderCostOrigin = "reported",
    context_pressure: float = 0.25,
    provider_error_code: str | None = None,
    selected_variant_quality: float = 0.95,
    observed_at: datetime = NOW,
    system_confounded: bool = False,
    confounding_signal: str | None = None,
    upstream_spine_blocker_refs: list[str] | None = None,
) -> ProviderModelQualityObservation:
    return ProviderModelQualityObservation(
        observation_id=f"{provider}-{model_fingerprint}-{latency_ms}",
        lane_id=f"lane-{provider}-{model_fingerprint}-{latency_ms}",
        lane_kind=lane_kind,
        provider=provider,
        model_id=model_id,
        model_fingerprint=model_fingerprint,
        scenario_pack_id=scenario_pack_id,
        scenario_id="scenario-public-1",
        observed_at=observed_at,
        schema_valid=schema_valid,
        healing_count=healing_count,
        json_valid=json_valid,
        tool_call_valid=tool_call_valid,
        grounding_valid=grounding_valid,
        citation_faithfulness_valid=citation_faithfulness_valid,
        disagreement_detected=disagreement_detected,
        latency_ms=latency_ms,
        cost_usd=cost_usd,
        estimated_cost_usd=estimated_cost_usd,
        cost_status=cost_status,
        cost_origin=cost_origin,
        context_pressure=context_pressure,
        provider_error_code=provider_error_code,
        selected_variant_quality=selected_variant_quality,
        quarantined=lane_kind == "quarantined_live",
        system_confounded=system_confounded,
        confounding_signal=confounding_signal,
        upstream_spine_blocker_refs=upstream_spine_blocker_refs or [],
        raw_evidence={
            "api_key": "sk-never-leak",
            "hidden_answer": "HIDDEN_HOLDOUT_ANSWER",
            "operator_note": "safe summary",
        },
    )


def test_simulated_lanes_populate_provider_model_quality_metrics() -> None:
    ledger = build_provider_model_quality_ledger(
        [
            _observation(),
            _observation(
                schema_valid=False,
                healing_count=2,
                json_valid=False,
                grounding_valid=False,
                citation_faithfulness_valid=False,
                disagreement_detected=True,
                latency_ms=200.0,
                context_pressure=0.85,
                provider_error_code="schema_validation_failed",
                selected_variant_quality=0.41,
            ),
        ],
        generated_at=NOW,
    )

    key = provider_model_evidence_key(
        provider="simulated",
        model_id="policyos-sim-v1",
        model_fingerprint="fixture-fp",
    )
    entry = ledger.entries_by_key[key]
    metrics = entry.metrics

    assert ledger.schema_version == "policyos.provider_model_quality_ledger.v1"
    assert entry.provider == "simulated"
    assert entry.model_id == "policyos-sim-v1"
    assert entry.model_fingerprint == "fixture-fp"
    assert entry.scenario_pack_ids == ["public_golden_pack"]
    assert entry.evidence_lane_kinds == ["simulated"]
    assert metrics.sample_count == 2
    assert metrics.schema_failure_rate == 0.5
    assert metrics.healing_count == 2
    assert metrics.json_validity_rate == 0.5
    assert metrics.tool_call_validity_rate == 1.0
    assert metrics.grounding_failure_rate == 0.5
    assert metrics.citation_faithfulness_failure_rate == 0.5
    assert metrics.disagreement_rate == 0.5
    assert metrics.latency_ms_avg == 150.0
    assert metrics.cost_usd_total == 0.0
    assert metrics.cost_status == "known"
    assert metrics.cost_origin == "reported"
    assert metrics.cost_known_sample_count == 2
    assert metrics.cost_missing_sample_count == 0
    assert metrics.context_pressure_max == 0.85
    assert metrics.provider_error_rate == 0.5
    assert metrics.selected_variant_quality_avg == 0.68


def test_provider_cost_summary_keeps_unknowns_and_typed_origins() -> None:
    observations = [
        _observation(
            model_fingerprint="legacy-scalar",
            cost_usd=9.0,
            cost_status="missing",
            cost_origin="unknown",
        ),
        _observation(
            model_fingerprint="partial-cost",
            cost_usd=0.25,
            cost_status="missing",
            cost_origin="estimated",
            estimated_cost_usd=0.25,
        ),
        _observation(
            model_fingerprint="partial-cost",
            cost_usd=None,
            cost_status="missing",
            cost_origin="unknown",
        ),
        _observation(
            model_fingerprint="explicit-zero",
            cost_usd=0.0,
            cost_status="known",
            cost_origin="reported",
        ),
        _observation(
            model_fingerprint="estimated-cost",
            cost_usd=None,
            cost_status="missing",
            cost_origin="estimated",
            estimated_cost_usd=0.125,
        ),
        _observation(
            model_fingerprint="invalid-cost",
            cost_usd=None,
            cost_status="invalid",
            cost_origin="unknown",
        ),
    ]
    ledger = build_provider_model_quality_ledger(observations, generated_at=NOW)
    metrics_by_fingerprint = {
        entry.model_fingerprint: entry.metrics for entry in ledger.entries
    }

    legacy_scalar = metrics_by_fingerprint["legacy-scalar"]
    assert legacy_scalar.cost_status == "missing"
    assert legacy_scalar.cost_origin == "unknown"
    assert legacy_scalar.cost_usd_total is None
    assert legacy_scalar.cost_usd_avg is None
    assert legacy_scalar.cost_known_sample_count == 0
    assert legacy_scalar.cost_missing_sample_count == 1

    partial = metrics_by_fingerprint["partial-cost"]
    assert partial.cost_status == "missing"
    assert partial.cost_origin == "mixed"
    assert partial.cost_usd_total is None
    assert partial.cost_usd_avg is None
    assert partial.cost_known_sample_count == 1
    assert partial.cost_missing_sample_count == 1

    zero = metrics_by_fingerprint["explicit-zero"]
    assert zero.cost_status == "known"
    assert zero.cost_origin == "reported"
    assert zero.cost_usd_total == 0.0
    assert zero.cost_usd_avg == 0.0

    estimated = metrics_by_fingerprint["estimated-cost"]
    assert estimated.cost_status == "known"
    assert estimated.cost_origin == "estimated"
    assert estimated.cost_usd_total == 0.125
    assert estimated.cost_usd_avg == 0.125

    assert legacy_scalar.drift_action == zero.drift_action
    assert legacy_scalar.drift_reasons == zero.drift_reasons

    invalid = metrics_by_fingerprint["invalid-cost"]
    assert invalid.cost_status == "invalid"
    assert invalid.cost_usd_total is None
    assert invalid.cost_invalid_sample_count == 1

    comparison_rows = {
        row.model_fingerprint: row
        for row in compare_provider_models(
            ledger,
            scenario_pack_id="public_golden_pack",
        ).rankings
    }
    assert comparison_rows["partial-cost"].cost_status == "missing"
    assert comparison_rows["partial-cost"].cost_origin == "mixed"
    assert comparison_rows["partial-cost"].cost_usd_avg is None
    assert comparison_rows["estimated-cost"].cost_status == "known"
    assert comparison_rows["estimated-cost"].cost_origin == "estimated"


def test_controlled_comparison_preserves_cost_completeness_and_origin() -> None:
    choice = {
        "provider": "fixture-provider",
        "model_id": "fixture-model",
        "model_fingerprint": "fixture-fingerprint",
    }
    observations = [
        _controlled_observation(
            **choice,
            sample_index=0,
            cost_usd=0.001,
            cost_status="known",
            cost_origin="reported",
        ),
        _controlled_observation(
            **choice,
            sample_index=1,
            cost_usd=0.002,
            cost_status="known",
            cost_origin="estimated",
        ),
        _controlled_observation(
            **choice,
            sample_index=2,
            cost_usd=None,
            cost_status="missing",
            cost_origin="unknown",
        ),
    ]

    comparison = build_controlled_provider_model_comparison(
        observations,
        candidate_models=[{**choice, "usage": "candidate"}],
        default_model_choice={**choice, "usage": "policy_drafting"},
        generated_at=NOW,
    )

    row = comparison.rows[0]
    assert row.cost_status == "missing"
    assert row.cost_origin == "mixed"
    assert row.cost_usd_total is None
    assert row.cost_usd_avg is None
    assert row.cost_known_sample_count == 2
    assert row.cost_missing_sample_count == 1


def test_provider_cost_metrics_preserve_precision_and_reject_overflow() -> None:
    tiny_ledger = build_provider_model_quality_ledger(
        [
            _observation(
                model_fingerprint="tiny-positive",
                cost_usd=1e-10,
                latency_ms=100.0,
            ),
            _observation(
                model_fingerprint="tiny-positive",
                cost_usd=2e-10,
                latency_ms=101.0,
            ),
        ],
        generated_at=NOW,
    )
    tiny_metrics = tiny_ledger.entries[0].metrics
    assert tiny_metrics.cost_status == "known"
    assert tiny_metrics.cost_usd_total is not None
    assert math.isclose(tiny_metrics.cost_usd_total, 3e-10, rel_tol=1e-12)
    assert tiny_metrics.cost_usd_avg is not None
    assert math.isclose(tiny_metrics.cost_usd_avg, 1.5e-10, rel_tol=1e-12)

    overflow_ledger = build_provider_model_quality_ledger(
        [
            _observation(
                model_fingerprint="overflow",
                cost_usd=1e308,
                latency_ms=100.0,
            ),
            _observation(
                model_fingerprint="overflow",
                cost_usd=1e308,
                latency_ms=101.0,
            ),
        ],
        generated_at=NOW,
    )
    overflow_metrics = overflow_ledger.entries[0].metrics
    assert overflow_metrics.cost_status == "invalid"
    assert overflow_metrics.cost_usd_total is None
    assert overflow_metrics.cost_usd_avg is None


def test_provider_cost_amounts_reject_boolean_and_nonfinite_values() -> None:
    for field_name in ("cost_usd", "estimated_cost_usd"):
        for invalid_amount in (True, math.inf, math.nan):
            payload = _observation().model_dump()
            payload[field_name] = invalid_amount
            with pytest.raises(ValidationError):
                ProviderModelQualityObservation.model_validate(payload)


def test_legacy_v1_costs_are_not_reemitted_without_typed_provenance() -> None:
    current_ledger = build_provider_model_quality_ledger(
        [
            _observation(
                model_fingerprint="legacy-v1",
                cost_usd=0.25,
                latency_ms=100.0,
            ),
            _observation(
                model_fingerprint="legacy-v1",
                cost_usd=0.75,
                latency_ms=101.0,
            ),
        ],
        generated_at=NOW,
    )
    legacy_payload = json.loads(current_ledger.model_dump_json())
    legacy_metrics_payload = legacy_payload["entries"][0]["metrics"]
    original_total = legacy_metrics_payload["cost_usd_total"]
    original_average = legacy_metrics_payload["cost_usd_avg"]
    for field_name in (
        "cost_status",
        "cost_origin",
        "cost_known_sample_count",
        "cost_missing_sample_count",
        "cost_invalid_sample_count",
    ):
        legacy_metrics_payload.pop(field_name)
    unhashed_legacy_payload = {
        key: value
        for key, value in legacy_payload.items()
        if key != "provider_model_quality_ledger_ref"
    }
    encoded_legacy_payload = json.dumps(
        unhashed_legacy_payload,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    legacy_source_ref = "sha256:" + hashlib.sha256(
        encoded_legacy_payload
    ).hexdigest()
    legacy_payload["provider_model_quality_ledger_ref"] = legacy_source_ref
    legacy_serialized_bytes = json.dumps(
        legacy_payload,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    legacy_ledger = ProviderModelQualityLedger.model_validate(legacy_payload)
    assert json.dumps(
        legacy_payload,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8") == legacy_serialized_bytes
    assert legacy_ledger.provider_model_quality_ledger_ref is None
    assert _ledger_ref(legacy_ledger) != legacy_source_ref
    legacy_metrics = legacy_ledger.entries[0].metrics
    assert legacy_payload["entries"][0]["metrics"]["cost_usd_total"] == original_total
    assert legacy_payload["entries"][0]["metrics"]["cost_usd_avg"] == original_average
    assert "cost_status" not in legacy_payload["entries"][0]["metrics"]
    assert legacy_metrics.cost_status == "missing"
    assert legacy_metrics.cost_origin == "unknown"
    assert legacy_metrics.cost_usd_total is None
    assert legacy_metrics.cost_usd_avg is None

    standard_rows = compare_provider_models(
        legacy_ledger,
        scenario_pack_id="public_golden_pack",
    ).rankings
    assert len(standard_rows) == 1
    assert standard_rows[0].cost_status == "missing"
    assert standard_rows[0].cost_origin == "unknown"
    assert standard_rows[0].cost_usd_avg is None

    choice = {
        "provider": "legacy-provider",
        "model_id": "legacy-model",
        "model_fingerprint": "legacy-controlled-v1",
    }
    legacy_controlled_observations = []
    for sample_index in range(3):
        old_observation_payload = _controlled_observation(
            **choice,
            sample_index=sample_index,
            cost_usd=0.25,
        ).model_dump(mode="json")
        for field_name in (
            "cost_status",
            "cost_origin",
            "estimated_cost_usd",
        ):
            old_observation_payload.pop(field_name)
        legacy_controlled_observations.append(
            ProviderModelQualityObservation.model_validate(old_observation_payload)
        )
    controlled_rows = build_controlled_provider_model_comparison(
        legacy_controlled_observations,
        candidate_models=[{**choice, "usage": "candidate"}],
        default_model_choice={**choice, "usage": "policy_drafting"},
        generated_at=NOW,
    ).rows
    assert len(controlled_rows) == 1
    assert controlled_rows[0].cost_status == "missing"
    assert controlled_rows[0].cost_origin == "unknown"
    assert controlled_rows[0].cost_usd_total is None
    assert controlled_rows[0].cost_usd_avg is None


def test_ledger_sanitizes_credentials_and_hidden_answers() -> None:
    ledger = build_provider_model_quality_ledger(
        [_observation(scenario_pack_id="hidden_holdout")],
        generated_at=NOW,
        hidden_answer_tokens={"HIDDEN_HOLDOUT_ANSWER"},
    )

    key = provider_model_evidence_key(
        provider="simulated",
        model_id="policyos-sim-v1",
        model_fingerprint="fixture-fp",
    )
    rendered = json.dumps(ledger.model_dump(mode="json"), sort_keys=True)

    assert key in ledger.entries_by_key
    assert ledger.entries_by_key[key].evidence_key == key
    assert "sk-never-leak" not in rendered
    assert "HIDDEN_HOLDOUT_ANSWER" not in rendered
    assert "operator_note" in rendered


def test_default_production_models_need_recent_quality_evidence() -> None:
    thresholds = ProviderModelQualityThresholds(
        review_schema_failure_rate=0.20,
        demote_schema_failure_rate=0.40,
        review_selected_variant_quality=0.75,
        demote_selected_variant_quality=0.60,
        block_provider_error_rate=0.50,
    )
    ledger = build_provider_model_quality_ledger(
        [
            _observation(model_fingerprint="good-fp", selected_variant_quality=0.93),
            _observation(
                model_fingerprint="review-fp",
                context_pressure=0.93,
                selected_variant_quality=0.70,
            ),
            _observation(
                model_fingerprint="demote-fp",
                schema_valid=False,
                json_valid=False,
                grounding_valid=False,
                citation_faithfulness_valid=False,
                provider_error_code="provider_timeout",
                selected_variant_quality=0.40,
            ),
            _observation(
                model_fingerprint="stale-fp",
                observed_at=NOW - timedelta(days=30),
            ),
        ],
        default_model_choices=[
            DefaultProductionModelChoice(
                provider="simulated",
                model_id="policyos-sim-v1",
                model_fingerprint="good-fp",
                usage="policy_drafting",
            ),
            DefaultProductionModelChoice(
                provider="simulated",
                model_id="policyos-sim-v1",
                model_fingerprint="review-fp",
                usage="policy_drafting",
            ),
            DefaultProductionModelChoice(
                provider="simulated",
                model_id="policyos-sim-v1",
                model_fingerprint="demote-fp",
                usage="policy_drafting",
            ),
            DefaultProductionModelChoice(
                provider="simulated",
                model_id="policyos-sim-v1",
                model_fingerprint="stale-fp",
                usage="policy_drafting",
            ),
            DefaultProductionModelChoice(
                provider="simulated",
                model_id="missing-model",
                model_fingerprint="missing-fp",
                usage="policy_drafting",
            ),
        ],
        generated_at=NOW,
        thresholds=thresholds,
        max_evidence_age_days=14,
    )

    reviews = {
        review.model_fingerprint: review for review in ledger.default_model_reviews
    }

    assert reviews["good-fp"].action == "approve"
    assert reviews["review-fp"].action == "require_review"
    assert "context_pressure" in reviews["review-fp"].reasons
    assert reviews["demote-fp"].action == "demote"
    assert reviews["stale-fp"].action == "block_production_approval"
    assert "quality_evidence_stale" in reviews["stale-fp"].reasons
    assert reviews["missing-fp"].action == "block_production_approval"
    assert "quality_evidence_missing" in reviews["missing-fp"].reasons


def test_confounded_live_provider_sample_cannot_demote_default_model() -> None:
    ledger = build_provider_model_quality_ledger(
        [
            _observation(
                lane_kind="quarantined_live",
                schema_valid=False,
                json_valid=False,
                grounding_valid=False,
                citation_faithfulness_valid=False,
                provider_error_code="provider_timeout",
                selected_variant_quality=0.20,
                system_confounded=True,
                confounding_signal="upstream_evidence_spine_incomplete",
                upstream_spine_blocker_refs=[
                    "quality_evidence/scenario_contract_propagation_graph.json#/findings/0",
                    "quality_evidence/semantic_binding_ledger.json#/issues/0",
                ],
            )
        ],
        default_model_choices=[
            DefaultProductionModelChoice(
                provider="simulated",
                model_id="policyos-sim-v1",
                model_fingerprint="fixture-fp",
                usage="policy_drafting",
            )
        ],
        generated_at=NOW,
    )

    key = provider_model_evidence_key(
        provider="simulated",
        model_id="policyos-sim-v1",
        model_fingerprint="fixture-fp",
    )
    entry = ledger.entries_by_key[key]
    review = ledger.default_model_reviews[0]

    assert entry.metrics.sample_count == 1
    assert entry.metrics.system_confounded_sample_count == 1
    assert entry.metrics.decision_sample_count == 0
    assert entry.drift_action == "require_review"
    assert "system_confounded_samples_excluded" in entry.drift_reasons
    assert "controlled_evidence_bound_task_required" in entry.drift_reasons
    assert review.action == "require_review"
    assert "system_confounded_samples_excluded" in review.reasons
    assert review.action != "demote"
    assert ledger.summary["status"] == "warn"
    assert ledger.summary["system_confounded_observations"] == 1


def test_model_comparisons_use_scenario_pack_ids_without_hidden_answer_leakage() -> None:
    ledger = build_provider_model_quality_ledger(
        [
            _observation(
                provider="provider-a",
                model_id="model-a",
                model_fingerprint="fp-a",
                scenario_pack_id="hidden_holdout",
                selected_variant_quality=0.83,
            ),
            _observation(
                provider="provider-b",
                model_id="model-b",
                model_fingerprint="fp-b",
                scenario_pack_id="hidden_holdout",
                selected_variant_quality=0.91,
            ),
        ],
        generated_at=NOW,
        hidden_answer_tokens={"HIDDEN_HOLDOUT_ANSWER"},
    )

    comparison = compare_provider_models(ledger, scenario_pack_id="hidden_holdout")
    rendered = json.dumps(comparison.model_dump(mode="json"), sort_keys=True)

    assert comparison.scenario_pack_id == "hidden_holdout"
    assert [row.provider for row in comparison.rankings] == ["provider-b", "provider-a"]
    assert comparison.rankings[0].selected_variant_quality_avg == 0.91
    assert "HIDDEN_HOLDOUT_ANSWER" not in rendered
    assert "hidden_answer" not in rendered


def test_controlled_grounding_task_carries_one_frozen_ref_per_evidence_axis() -> None:
    task = controlled_grounding_task()

    assert task.task_id == CONTROLLED_GROUNDING_TASK_ID
    assert task.scenario_pack_id == DEFAULT_CONTROLLED_GROUNDING_SCENARIO_PACK_ID
    assert set(task.required_evidence_refs) == {
        "data_ref",
        "norm_ref",
        "method_ref",
        "claim_ref",
    }
    for value in task.required_evidence_refs.values():
        assert value.startswith("sha256:")


def test_controlled_model_comparison_blocks_default_promotion_before_three_samples() -> None:
    qwen = {
        "provider": "gonka_proxy",
        "model_id": "Qwen/Qwen3-235B-A22B-Instruct-2507-FP8",
        "model_fingerprint": "qwen-controlled-fp",
    }
    kimi = {
        "provider": "gonka_proxy",
        "model_id": "moonshotai/Kimi-K2.6",
        "model_fingerprint": "kimi-controlled-fp",
    }
    observations = [
        _controlled_observation(**qwen, sample_index=0),
        _controlled_observation(**qwen, sample_index=1),
        *[
            _controlled_observation(**kimi, sample_index=index)
            for index in range(3)
        ],
    ]

    comparison = build_controlled_provider_model_comparison(
        observations,
        candidate_models=[qwen, kimi],
        default_model_choice={
            **qwen,
            "usage": "policy_drafting",
        },
        generated_at=NOW,
    )

    qwen_row = next(row for row in comparison.rows if row.model_id == qwen["model_id"])
    assert comparison.summary["status"] == "fail"
    assert qwen_row.sample_count == 2
    assert comparison.default_model_gate["action"] == "block_production_approval"
    assert "controlled_sample_count_below_minimum" in comparison.default_model_gate["reasons"]


def test_controlled_model_comparison_records_failures_latency_cost_and_fingerprints() -> None:
    qwen = {
        "provider": "gonka_proxy",
        "model_id": "Qwen/Qwen3-235B-A22B-Instruct-2507-FP8",
        "model_fingerprint": "qwen-controlled-fp",
    }
    kimi = {
        "provider": "gonka_proxy",
        "model_id": "moonshotai/Kimi-K2.6",
        "model_fingerprint": "kimi-controlled-fp",
    }
    observations = [
        *[
            _controlled_observation(
                **qwen,
                sample_index=index,
                latency_ms=100 + index,
                cost_usd=0.001,
            )
            for index in range(3)
        ],
        _controlled_observation(
            **kimi,
            sample_index=0,
            schema_valid=False,
            grounding_refs={"data_ref": "sha256:" + "0" * 64},
            refusal_detected=True,
            degradation_behavior="fallback_plain_json",
            latency_ms=250,
            cost_usd=0.002,
        ),
        _controlled_observation(**kimi, sample_index=1, latency_ms=200, cost_usd=0.002),
        _controlled_observation(**kimi, sample_index=2, latency_ms=220, cost_usd=0.002),
    ]

    comparison = build_controlled_provider_model_comparison(
        observations,
        candidate_models=[qwen, kimi],
        default_model_choice={
            **qwen,
            "usage": "policy_drafting",
        },
        generated_at=NOW,
        hidden_answer_tokens={"sk-never-leak"},
    )
    rendered = json.dumps(comparison.model_dump(mode="json"), sort_keys=True)
    kimi_row = next(row for row in comparison.rows if row.model_id == kimi["model_id"])
    qwen_row = next(row for row in comparison.rows if row.model_id == qwen["model_id"])

    assert comparison.summary["status"] == "pass"
    assert comparison.default_model_gate["action"] == "approve"
    assert qwen_row.sample_count == 3
    assert qwen_row.request_fingerprints == [
        "sha256:qwen-controlled-fingerprint-0",
        "sha256:qwen-controlled-fingerprint-1",
        "sha256:qwen-controlled-fingerprint-2",
    ]
    assert qwen_row.cost_usd_total == 0.003
    assert kimi_row.sample_count == 3
    assert kimi_row.schema_failure_rate == 0.333333
    assert kimi_row.grounding_failure_rate == 0.333333
    assert kimi_row.refusal_rate == 0.333333
    assert kimi_row.degradation_rate == 0.333333
    assert kimi_row.latency_ms_avg == 223.333333
    assert "sk-never-leak" not in rendered


def test_provider_quality_drift_blocks_production_scorecard_approval() -> None:
    ledger = build_provider_model_quality_ledger(
        [
            _observation(
                schema_valid=False,
                json_valid=False,
                grounding_valid=False,
                citation_faithfulness_valid=False,
                provider_error_code="provider_timeout",
                selected_variant_quality=0.40,
            )
        ],
        default_model_choices=[
            DefaultProductionModelChoice(
                provider="simulated",
                model_id="policyos-sim-v1",
                model_fingerprint="fixture-fp",
                usage="policy_drafting",
            )
        ],
        generated_at=NOW,
    )

    scorecard = build_quality_scorecard(
        canary_kind="production",
        job_id="job-provider-quality",
        run_id="R_provider_quality",
        execution_status="completed",
        job_payload=_scorecard_job_payload(
            ledger.provider_model_quality_ledger_ref or "sha256:ledger"
        ),
        run_payload=None,
        provider_preflight={"status": "passed"},
        quality_evidence={
            "normative_evidence": {"status": "pass"},
            "fabric_retrieval_trace": {"status": "pass"},
            "foundry_method_report": {"status": "pass"},
            "policy_grounding_matrix": {"status": "pass"},
            "conflict_check": {"status": "pass"},
            "provider_model_quality_ledger": ledger.model_dump(mode="json"),
        },
    )
    provider_gate = next(
        gate
        for gate in scorecard["quality_gates"]
        if gate["name"] == "provider_model_quality_ledger_passed"
        and gate.get("phase") == "provider_model_quality"
    )

    assert provider_gate["status"] == "fail"
    assert provider_gate["code"] == (
        "provider_model_quality_default_model_demoted"
    )
    assert scorecard["quality_status"] == "fail"
    assert scorecard["approval_state"] == "quality_failed"
    assert scorecard["approval_eligibility"]["eligible"] is False
    assert "provider_model_quality_default_model_demoted" in (
        scorecard["approval_eligibility"]["reasons"]
    )


def _scorecard_job_payload(provider_model_quality_ledger_ref: str) -> dict[str, object]:
    return {
        "job_id": "job-provider-quality",
        "run_id": "R_provider_quality",
        "state": "completed",
        "progress": {
            "details": {
                "data_snapshot_ref": "sha256:" + "1" * 64,
                "input_bindings_ref": "sha256:" + "2" * 64,
                "registry_bundle_ref": "sha256:" + "3" * 64,
                "quality_report_ref": "sha256:" + "4" * 64,
                "normative_applicability_report_ref": "sha256:" + "5" * 64,
                "fabric_retrieval_trace_ref": "sha256:" + "6" * 64,
                "foundry_method_report_ref": "sha256:" + "7" * 64,
                "policy_grounding_matrix_ref": "sha256:" + "8" * 64,
                "conflict_check_ref": "sha256:" + "9" * 64,
                "provider_model_quality_ledger_ref": provider_model_quality_ledger_ref,
                "llm_model_variants": [
                    {
                        "model_variant_id": "simulated-default",
                        "model": "policyos-sim-v1",
                        "provider": "simulated",
                        "status": "completed",
                        "schema_healing_count": 1,
                        "prompt_tokens": 120,
                        "completion_tokens": 32,
                        "total_tokens": 152,
                        "cost_usd": 0.0,
                    }
                ],
                "run_performance_summary": {"status": "pass"},
            }
        },
    }


def _controlled_observation(
    *,
    provider: str,
    model_id: str,
    model_fingerprint: str,
    sample_index: int,
    schema_valid: bool = True,
    grounding_refs: dict[str, str] | None = None,
    refusal_detected: bool = False,
    degradation_behavior: str | None = None,
    latency_ms: float = 100.0,
    cost_usd: float | None = 0.001,
    estimated_cost_usd: float | None = None,
    cost_status: ProviderCostStatus = "known",
    cost_origin: ProviderCostOrigin = "reported",
) -> ProviderModelQualityObservation:
    request_fingerprint = (
        "sha256:"
        f"{'qwen' if 'Qwen' in model_id else 'kimi'}-controlled-fingerprint-{sample_index}"
    )
    return build_controlled_grounding_observation(
        provider=provider,
        model_id=model_id,
        model_fingerprint=model_fingerprint,
        sample_index=sample_index,
        observed_at=NOW,
        grounding_refs=grounding_refs,
        schema_valid=schema_valid,
        refusal_detected=refusal_detected,
        degradation_behavior=degradation_behavior,
        request_fingerprint=request_fingerprint,
        latency_ms=latency_ms,
        cost_usd=cost_usd,
        estimated_cost_usd=estimated_cost_usd,
        cost_status=cost_status,
        cost_origin=cost_origin,
        raw_evidence={
            "request_fingerprint": request_fingerprint,
            "api_key": "sk-never-leak",
        },
    )
