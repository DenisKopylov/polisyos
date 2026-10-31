"""Project CAS artifacts into redacted HTTP inspection views.

`ArtifactInspectorService` is a read-only runtime boundary: it loads artifact
manifests and payload bytes from CAS, applies preview limits and secret
redaction, and delegates lineage expansion to `LineageService`.
"""

from __future__ import annotations

import json
import math
from collections.abc import Callable, Mapping
from typing import TYPE_CHECKING, Any, Literal

from pydantic import ValidationError

from polisyos.common.canonical_profile import (
    CanonicalProfileRead,
    CanonicalProfileRefusalError,
)
from polisyos.common.logger import get_logger
from polisyos.core import scan_secret_and_pii
from polisyos.core.artifacts import (
    ArtifactRef,
    CoreJsonManifestBoundedRead,
    CoreJsonReadLimits,
    artifact_manifest_profile_sha256,
    artifact_ref_for_manifest,
    read_core_json_artifact_bounded,
    read_core_manifest_profile,
    read_core_manifest_profile_bounded,
)
from polisyos.core.artifacts.canonical_profile import CoreJsonReadBoundsRefusalError
from polisyos.core.canon.canon_json import CORE_TAG_POLICY_ID
from polisyos.core.contracts.decision_packet_hte import (
    build_decision_packet_legacy_hte_preview,
)
from polisyos.core.contracts.foundry import MethodArtifactOutputPayload
from polisyos.core.contracts.runtime import (
    ArtifactContentPreview,
    ArtifactLineageView,
    ArtifactManifestView,
    ArtifactSchemaView,
    CanonReadStatus,
    DecisionPacketAuthoredBlock,
    DecisionPacketEffectSize,
    DecisionPacketMetricComparisonRow,
    DecisionPacketMetricSignificance,
    DecisionPacketOutlineEntry,
    DecisionPacketPreview,
    DirectMethodExecutionHTESummary,
    PredictiveCoverageDiagnosticPreview,
    PredictiveCoverageScenarioPreview,
    PreviewMode,
)
from polisyos.runtime.quality.authority import (
    AuthoritySurfaceDecision,
    authority_surface_decision,
)
from polisyos.runtime.quality.technical_inspection_evidence import TECHNICAL_INSPECTION_PURPOSE

if TYPE_CHECKING:
    from polisyos.core.artifacts import ArtifactManifest
    from polisyos.core.artifacts.ids import ArtifactID
    from polisyos.core.artifacts.protocol import ArtifactStore

    from .lineage import LineageService

RedactionHook = Callable[[Any, PreviewMode], Any]
_SENSITIVE_KIND_MARKERS = ("secret", "token", "credential", "password", "key_material")
_REDACTED_PREVIEW = "[REDACTED]"
_MAX_PREDICTIVE_COVERAGE_SOURCE_BYTES = 2_000_000
INSPECTOR_JSON_MAX_DEPTH = 128
INSPECTOR_JSON_MAX_ELEMENTS = 100_000
INSPECTOR_MANIFEST_MAX_BYTES = 1_000_000
INSPECTOR_BOUNDED_READ_POLICY_ID = "artifact-inspector-bounded-read@1"
SCHEMA_INSPECTION_POLICY_ID = "artifact-schema-preview@1"


logger = get_logger(__name__)


def _artifact_ref_for_manifest(manifest: ArtifactManifest) -> ArtifactRef:
    """Return the exact CAS view selected for an inspector operation."""
    return artifact_ref_for_manifest(manifest)


def _read_inspector_semantic_json(
    store: ArtifactStore,
    selected_ref: ArtifactRef,
    *,
    max_payload_bytes: int,
    manifest_read: CoreJsonManifestBoundedRead | None = None,
) -> CanonicalProfileRead:
    """Read JSON under the fixed Core policy and exact bounded selected CAS view."""
    if type(max_payload_bytes) is not int or max_payload_bytes < 1:
        raise ValueError("inspector_json_read_limit_invalid")
    header = manifest_read or read_core_manifest_profile_bounded(
        store, selected_ref, max_manifest_bytes=INSPECTOR_MANIFEST_MAX_BYTES
    )
    profile = header.declaration.profile
    if profile is not None and profile.version == "0.3.0":
        # Kind only routes to the defining source. Unsupported .3 owners refuse
        # before opening payload; this Inspector has no generic .3 admission.
        if selected_ref.kind != MethodArtifactOutputPayload.ARTIFACT_KIND:
            raise CanonicalProfileRefusalError("canon_profile_reader_policy_mismatch")
        from polisyos.foundry.execute import read_method_artifact_output_bounded

        owned = read_method_artifact_output_bounded(
            store, selected_ref, max_bytes=max_payload_bytes
        )
        return owned.profile_read
    bounded = read_core_json_artifact_bounded(
        store,
        selected_ref,
        limits=CoreJsonReadLimits(
            max_bytes=max_payload_bytes,
            max_depth=INSPECTOR_JSON_MAX_DEPTH,
            max_elements=INSPECTOR_JSON_MAX_ELEMENTS,
            max_manifest_bytes=INSPECTOR_MANIFEST_MAX_BYTES,
        ),
        manifest_read=header,
    )
    profiled = bounded.profile_read
    if profiled.reader_policy_id != CORE_TAG_POLICY_ID:
        raise CanonicalProfileRefusalError("canon_profile_reader_policy_mismatch")
    return profiled


def _is_predictive_coverage_source_byte_cap_refusal(
    error: CoreJsonReadBoundsRefusalError,
) -> bool:
    """Recognize only a complete Core owner measurement of this preview's byte cap.

    The Core bounded reader can establish the same byte-limit refusal either by
    checking the selected member size before streaming or while enforcing its
    streaming bound. The stage is diagnostic; the typed limit and exact owner
    measurements determine whether this preview can safely return no diagnostic.
    """
    limits = error.limits
    observed_payload_bytes = error.observed_payload_bytes
    observed_payload_size = error.observed_payload_size
    cap = _MAX_PREDICTIVE_COVERAGE_SOURCE_BYTES
    return (
        error.code == "canon_profile_bounded_bytes_exceeded"
        and error.limit_name == "max_bytes"
        and type(limits) is CoreJsonReadLimits
        and limits.max_bytes == cap
        and limits.max_manifest_bytes == INSPECTOR_MANIFEST_MAX_BYTES
        and error.max_manifest_bytes == INSPECTOR_MANIFEST_MAX_BYTES
        and error.limit_value == cap
        and error.source_usage_complete is True
        and type(error.observed_manifest_selection_bytes) is int
        and error.observed_manifest_selection_bytes >= 0
        and type(error.observed_manifest_verification_bytes) is int
        and error.observed_manifest_verification_bytes >= 0
        and type(observed_payload_bytes) is int
        and 0 <= observed_payload_bytes <= cap
        and type(observed_payload_size) is int
        and observed_payload_size > cap
        and observed_payload_bytes < observed_payload_size
        and error.observed_source_bytes is not None
        and error.payload_integrity_verified is False
        and error.cleanup_failure_stage is None
        and error.cleanup_exception_type is None
        and error.cleanup_exception_code is None
    )


def _coverage_number(value: object) -> float | None:
    """Return a finite numeric value without coercing strings or booleans."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        numeric = float(value)
    except OverflowError:
        return None
    return numeric if math.isfinite(numeric) else None


def _coverage_count(value: object) -> int | None:
    """Return a non-negative integer count without accepting bool-as-int."""
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def _predictive_coverage_preview(
    payload: object,
    manifest: ArtifactManifest,
    *,
    canon_read_status: CanonReadStatus,
) -> PredictiveCoverageDiagnosticPreview | None:
    """Recompute one persisted predictive interval report without grading it."""
    schema = manifest.artifact_schema
    if (
        manifest.kind != "ir.backtest_report"
        or manifest.media_type != "application/json"
        or schema is None
        or schema.name != "ir.backtest_report"
        or schema.version != "1.0"
    ):
        return None

    shared = {
        "source_artifact_id": str(manifest.artifact_id),
        "source_manifest_profile_sha256": artifact_manifest_profile_sha256(manifest),
        "source_schema_version": "1.0",
        "metric": "predictive_interval_coverage",
        "assessment": "limited",
        "source_materialization": "reader_materialized",
        "canon_read_status": canon_read_status,
        "producer_attestation_status": "not_established",
        "s10_metric_mapping_status": "not_established",
        "s10_threshold_status": "not_established",
        "issuer_status": "not_established",
        "effective_time_status": "not_established",
        "counterfactual_credibility_status": "not_established",
        "causal_effect_status": "not_established",
        "may_not_use_for": [
            "promotion",
            "publication",
            "policy_selection",
            "causal_effect_claim",
        ],
    }

    def invalid(reason: str) -> PredictiveCoverageDiagnosticPreview:
        return PredictiveCoverageDiagnosticPreview(
            **shared,
            measurement_status="invalid_source",
            reason_code=reason,
            scenarios=[],
        )

    if not isinstance(payload, Mapping):
        return invalid("malformed_report_shape")
    metadata = payload.get("metadata")
    degraded_reasons = payload.get("degraded_reasons")
    if (
        payload.get("schema_version") != "1.0"
        or not isinstance(metadata, Mapping)
        or metadata.get("estimand") != "predictive_interval_coverage"
        or metadata.get("authority_scope") != "predictive_only"
        or metadata.get("bridge_status") != "bridge_pending"
        or payload.get("trust_eligible") is not False
        or payload.get("trust_score") is not None
        or payload.get("degraded") is not True
        or not isinstance(degraded_reasons, list)
        or "trust_screening:predictive_only_bridge_pending" not in degraded_reasons
    ):
        return invalid("predictive_scope_not_established")

    scenarios = payload.get("scenarios")
    declared_scenario_count = _coverage_count(payload.get("n_scenarios"))
    if (
        not isinstance(scenarios, list)
        or declared_scenario_count is None
        or declared_scenario_count != len(scenarios)
        or len(scenarios) != 1
    ):
        return invalid("unsupported_report_scope")

    # This bounded diagnostic does not verify native trajectories or replica
    # cohorts. Keep the report inspectable, but do not calculate coverage from
    # their unverified comparisons or trust optional scenario markers alone.
    native_fields = {
        "native_forecast_ref",
        "native_replica_projection",
        "native_request_ref",
        "native_forecast_purpose",
        "native_workflow_status",
        "native_workflow_failures",
        "native_foundry_step_count",
        "native_randomness_scope",
        "native_limitations",
        "native_requested_replicas",
        "native_started_replicas",
        "native_requested_count_status",
        "native_started_count_status",
    }
    native_modes = ("scientist_candidate", "scientist_unavailable")
    if (
        any(
            edge.role.startswith(("native_forecast:", "replica_cohort:"))
            for edge in manifest.inputs
        )
        or payload.get("prediction_mode_effective") in native_modes
        or any(
            isinstance(reason, str) and (reason.startswith("native_") or ": native_" in reason)
            for reason in degraded_reasons
        )
        or any(
            isinstance(scenario, Mapping)
            and isinstance(scenario.get("metadata"), Mapping)
            and (
                bool(native_fields.intersection(scenario["metadata"]))
                or scenario["metadata"].get("prediction_source_effective") in native_modes
            )
            for scenario in scenarios
        )
    ):
        return PredictiveCoverageDiagnosticPreview(
            **shared,
            measurement_status="not_measured",
            reason_code="unsupported_report_scope",
            scenarios=[],
        )

    summaries: list[PredictiveCoverageScenarioPreview] = []
    for scenario in scenarios:
        if not isinstance(scenario, Mapping):
            return invalid("malformed_report_shape")
        scenario_id = scenario.get("scenario_id")
        requested = _coverage_count(scenario.get("requested_count"))
        compared = _coverage_count(scenario.get("compared_count"))
        missing = _coverage_count(scenario.get("missing_count"))
        invalid_count = _coverage_count(scenario.get("invalid_count"))
        interval_requested = _coverage_count(scenario.get("interval_requested_count"))
        interval_available = _coverage_count(scenario.get("interval_available_count"))
        interval_evaluated = _coverage_count(scenario.get("interval_evaluated_count"))
        interval_hits = _coverage_count(scenario.get("interval_hit_count"))
        comparisons = scenario.get("outcome_comparisons")
        if (
            not isinstance(scenario_id, str)
            or not scenario_id
            or requested is None
            or compared is None
            or missing is None
            or invalid_count is None
            or interval_requested is None
            or interval_available is None
            or interval_evaluated is None
            or interval_hits is None
            or not isinstance(comparisons, list)
            or requested != compared + missing + invalid_count
            or compared != len(comparisons)
            or missing != 0
            or invalid_count != 0
            or interval_requested != requested
            or interval_available > interval_requested
            or interval_evaluated > interval_available
            or interval_hits > interval_evaluated
        ):
            return invalid("malformed_interval_counts")

        metric_names: set[str] = set()
        recomputed_available = 0
        recomputed_evaluated = 0
        recomputed_hits = 0
        for comparison in comparisons:
            if not isinstance(comparison, Mapping):
                return invalid("malformed_report_shape")
            metric_name = comparison.get("metric_name")
            y_true = _coverage_number(comparison.get("y_true"))
            lower_raw = comparison.get("ci_lower")
            upper_raw = comparison.get("ci_upper")
            if not isinstance(metric_name, str) or not metric_name or y_true is None:
                return invalid("malformed_report_shape")
            metric_names.add(metric_name)
            if lower_raw is None and upper_raw is None:
                if comparison.get("within_ci") is not None:
                    return invalid("malformed_interval_counts")
                continue
            lower = _coverage_number(lower_raw)
            upper = _coverage_number(upper_raw)
            if lower is None or upper is None or lower > upper:
                return invalid("malformed_interval_counts")
            hit = lower <= y_true <= upper
            if comparison.get("within_ci") is not hit:
                return invalid("malformed_interval_counts")
            recomputed_available += 1
            recomputed_evaluated += 1
            recomputed_hits += int(hit)

        if (
            len(metric_names) != 1
            or recomputed_available != interval_available
            or recomputed_evaluated != interval_evaluated
            or recomputed_hits != interval_hits
        ):
            return invalid("malformed_interval_counts")

        hit_rate = recomputed_hits / recomputed_evaluated if recomputed_evaluated else None
        stored_hit_rate = scenario.get("interval_hit_rate")
        stored_coverage = scenario.get("coverage_probability")
        if hit_rate is None:
            if stored_hit_rate is not None or stored_coverage is not None:
                return invalid("stored_hit_rate_mismatch")
        else:
            stored_hit = _coverage_number(stored_hit_rate)
            stored_coverage_value = _coverage_number(stored_coverage)
            if (
                stored_hit is None
                or stored_coverage_value is None
                or not math.isclose(stored_hit, hit_rate, rel_tol=0.0, abs_tol=1e-12)
                or not math.isclose(stored_coverage_value, hit_rate, rel_tol=0.0, abs_tol=1e-12)
            ):
                return invalid("stored_hit_rate_mismatch")

        nominal_raw = scenario.get("nominal_confidence_level")
        nominal = None if nominal_raw is None else _coverage_number(nominal_raw)
        interval_type = scenario.get("interval_type")
        if (nominal_raw is not None and (nominal is None or not 0.0 < nominal < 1.0)) or (
            interval_type is not None and not isinstance(interval_type, str)
        ):
            return invalid("malformed_report_shape")
        summaries.append(
            PredictiveCoverageScenarioPreview(
                scenario_id=scenario_id,
                metric_name=next(iter(metric_names)),
                interval_requested_count=interval_requested,
                interval_available_count=interval_available,
                interval_evaluated_count=interval_evaluated,
                interval_hit_count=interval_hits,
                nominal_confidence_level=nominal,
                interval_type=interval_type,
                observed_hit_rate=hit_rate,
            )
        )

    # Even a structurally consistent legacy report can replace its comparison
    # rows while retaining selected source edges. This bounded preview does not
    # reconcile those rows to the selected forecast and held-out source values.
    # Keep shape/corruption diagnostics above, but do not publish row-only
    # arithmetic as measured observations.
    return PredictiveCoverageDiagnosticPreview(
        **shared,
        measurement_status="not_measured",
        reason_code="unsupported_report_scope",
        scenarios=[],
    )


class ArtifactSurfaceAdmissionError(RuntimeError):
    """Raised when the composed authority gate blocks an inspector read."""

    def __init__(self, decision: AuthoritySurfaceDecision) -> None:
        self.decision = decision
        super().__init__(
            f"artifact surface admission blocked for {decision.surface}: {decision.reason}"
        )


def _as_float(value: object) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        try:
            return float(stripped)
        except ValueError:
            return None
    return None


def _normalize_text_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    items: list[str] = []
    for item in value:
        if isinstance(item, str):
            stripped = item.strip()
            if stripped:
                items.append(stripped)
    return items


def _normalize_effect_method(value: object) -> str | None:
    if isinstance(value, str):
        lowered = value.strip().lower()
        if not lowered:
            return None
        if "bootstrap" in lowered:
            return "bootstrap"
        if lowered in {"paired_t", "delong_auc", "mcnemar_exact", "mcnemar_chi2"}:
            return "analytic"
        return lowered
    return None


def _normalize_effect_size(
    *,
    effect_value: object,
    ci_low: object = None,
    ci_high: object = None,
    method: object = None,
) -> DecisionPacketEffectSize | None:
    point = _as_float(effect_value)
    low = _as_float(ci_low)
    high = _as_float(ci_high)
    ci_95 = (low, high) if low is not None and high is not None else None
    normalized_method = _normalize_effect_method(method)
    if point is None and ci_95 is None and normalized_method is None:
        return None
    return DecisionPacketEffectSize(
        point=point,
        ci_95=ci_95,
        method=normalized_method,
    )


def _comparison_lookup(
    rows: object,
) -> dict[str, dict[str, object]]:
    lookup: dict[str, dict[str, object]] = {}
    if not isinstance(rows, list):
        return lookup
    for row in rows:
        if not isinstance(row, dict):
            continue
        metric_id = row.get("metric_id")
        if isinstance(metric_id, str) and metric_id not in lookup:
            lookup[metric_id] = row
    return lookup


def _normalize_outline(value: object) -> list[DecisionPacketOutlineEntry]:
    if not isinstance(value, list):
        return []
    items: list[DecisionPacketOutlineEntry] = []
    for entry in value:
        if not isinstance(entry, dict):
            continue
        section_id = entry.get("section_id")
        title = entry.get("title")
        section_type = entry.get("section_type")
        if not isinstance(section_id, str) or not isinstance(title, str):
            continue
        items.append(
            DecisionPacketOutlineEntry(
                section_id=section_id,
                title=title,
                section_type=section_type if isinstance(section_type, str) else None,
            )
        )
    return items


def _normalize_metric_significance(
    value: object,
    *,
    comparison_rows: object,
) -> dict[str, DecisionPacketMetricSignificance]:
    if not isinstance(value, dict):
        return {}
    comparisons = _comparison_lookup(comparison_rows)
    normalized: dict[str, DecisionPacketMetricSignificance] = {}
    for metric_id, entry in value.items():
        if not isinstance(metric_id, str) or not isinstance(entry, dict):
            continue
        comparison = comparisons.get(metric_id, {})
        effect_size = _normalize_effect_size(
            effect_value=entry.get("effect_size"),
            ci_low=comparison.get("ci_low"),
            ci_high=comparison.get("ci_high"),
            method=comparison.get("resampling_method") or entry.get("test_id"),
        )
        normalized[metric_id] = DecisionPacketMetricSignificance(
            baseline_model_id=entry.get("baseline_model_id")
            if isinstance(entry.get("baseline_model_id"), str)
            else None,
            candidate_model_id=entry.get("candidate_model_id")
            if isinstance(entry.get("candidate_model_id"), str)
            else None,
            metric_direction=entry.get("metric_direction")
            if isinstance(entry.get("metric_direction"), str)
            else None,
            baseline_value=_as_float(entry.get("baseline_value")),
            candidate_value=_as_float(entry.get("candidate_value")),
            delta_value=_as_float(entry.get("delta_value")),
            test_id=entry.get("test_id") if isinstance(entry.get("test_id"), str) else None,
            test_label=entry.get("test_label")
            if isinstance(entry.get("test_label"), str)
            else None,
            p_value=_as_float(entry.get("p_value")),
            p_adj=_as_float(entry.get("p_adj")),
            alpha=_as_float(entry.get("alpha")),
            significant=entry.get("significant")
            if isinstance(entry.get("significant"), bool)
            else None,
            effect_size=effect_size,
            assumption_warnings=_normalize_text_list(entry.get("assumption_warnings")),
            calibration_warnings=_normalize_text_list(entry.get("calibration_warnings")),
        )
    return normalized


def _normalize_metric_comparison_rows(
    value: object,
) -> list[DecisionPacketMetricComparisonRow]:
    if not isinstance(value, list):
        return []
    rows: list[DecisionPacketMetricComparisonRow] = []
    for entry in value:
        if not isinstance(entry, dict):
            continue
        metric_id = entry.get("metric_id")
        if not isinstance(metric_id, str):
            continue
        rows.append(
            DecisionPacketMetricComparisonRow(
                metric_id=metric_id,
                metric_direction=entry.get("metric_direction")
                if isinstance(entry.get("metric_direction"), str)
                else None,
                baseline_model_id=entry.get("baseline_model_id")
                if isinstance(entry.get("baseline_model_id"), str)
                else None,
                candidate_model_id=entry.get("candidate_model_id")
                if isinstance(entry.get("candidate_model_id"), str)
                else None,
                baseline_value=_as_float(entry.get("baseline_value")),
                candidate_value=_as_float(entry.get("candidate_value")),
                delta_value=_as_float(entry.get("delta_value")),
                family_id=entry.get("family_id")
                if isinstance(entry.get("family_id"), str)
                else None,
                family_scope=entry.get("family_scope")
                if isinstance(entry.get("family_scope"), str)
                else None,
                sample_size_effective=(
                    int(entry["sample_size_effective"])
                    if isinstance(entry.get("sample_size_effective"), int)
                    else None
                ),
                resampling_method=entry.get("resampling_method")
                if isinstance(entry.get("resampling_method"), str)
                else None,
                test_id=entry.get("test_id") if isinstance(entry.get("test_id"), str) else None,
                test_label=entry.get("test_label")
                if isinstance(entry.get("test_label"), str)
                else None,
                statistic=_as_float(entry.get("statistic")),
                effect_size=_normalize_effect_size(
                    effect_value=entry.get("effect_size"),
                    ci_low=entry.get("ci_low"),
                    ci_high=entry.get("ci_high"),
                    method=entry.get("resampling_method") or entry.get("test_id"),
                ),
                p_value=_as_float(entry.get("p_value")),
                p_adj=_as_float(entry.get("p_adj")),
                alpha=_as_float(entry.get("alpha")),
                significant=entry.get("significant")
                if isinstance(entry.get("significant"), bool)
                else None,
                assumption_warnings=_normalize_text_list(entry.get("assumption_warnings")),
                calibration_warnings=_normalize_text_list(entry.get("calibration_warnings")),
            )
        )
    return rows


def _normalize_authored_blocks(value: object) -> list[DecisionPacketAuthoredBlock]:
    if not isinstance(value, list):
        return []
    blocks: list[DecisionPacketAuthoredBlock] = []
    for entry in value:
        if not isinstance(entry, dict):
            continue
        content = entry.get("content")
        if not isinstance(content, str) or not content.strip():
            continue
        sources_value = entry.get("sources")
        sources: list[dict[str, str]] = []
        if isinstance(sources_value, list):
            for source in sources_value:
                if not isinstance(source, dict):
                    continue
                ref = source.get("ref")
                if not isinstance(ref, str) or not ref.strip():
                    continue
                kind = source.get("kind")
                sources.append(
                    {
                        "ref": ref,
                        "kind": kind if isinstance(kind, str) and kind.strip() else "source",
                    }
                )
        blocks.append(
            DecisionPacketAuthoredBlock(
                id=entry.get("id") if isinstance(entry.get("id"), str) else None,
                content=content,
                author=entry.get("author")
                if isinstance(entry.get("author"), str)
                and entry.get("author") in {"citation", "human", "drafter", "formalizer", "critic"}
                else None,
                author_agent_version=entry.get("author_agent_version")
                if isinstance(entry.get("author_agent_version"), str)
                else None,
                sources=sources,
                timestamp=entry.get("timestamp")
                if isinstance(entry.get("timestamp"), str)
                else None,
                confidence=_as_float(entry.get("confidence")),
                reviewed_by_human=entry.get("reviewed_by_human")
                if isinstance(entry.get("reviewed_by_human"), bool)
                else None,
            )
        )
    return blocks


def _is_modern_hte_summary(payload: Mapping[str, object]) -> bool:
    return any(
        key in payload
        for key in (
            "schema_version",
            "kind",
            "method_fqn",
            "method_abi_digest",
            "owned_attempt_anchor_ref",
            "hte_outcome_ref",
            "resource_evidence",
        )
    )


def _build_decision_packet_preview(payload: object) -> DecisionPacketPreview | None:
    if not isinstance(payload, dict):
        return None
    normalized = dict(payload)
    hte_projection_status: Literal["absent", "typed", "legacy_limited", "invalid"] = "absent"
    typed_hte: DirectMethodExecutionHTESummary | None = None
    limited_hte = None
    if "hte" in payload:
        hte_payload = payload["hte"]
        if hte_payload is None:
            hte_projection_status = "absent"
        elif not isinstance(hte_payload, dict):
            hte_projection_status = "invalid"
        elif _is_modern_hte_summary(hte_payload):
            try:
                hte_json = json.dumps(
                    hte_payload,
                    ensure_ascii=False,
                    allow_nan=False,
                    separators=(",", ":"),
                )
                typed_hte = DirectMethodExecutionHTESummary.model_validate_json(
                    hte_json,
                    strict=True,
                )
            except (TypeError, ValueError, ValidationError):
                hte_projection_status = "invalid"
            else:
                hte_projection_status = "typed"
        else:
            try:
                limited_hte = build_decision_packet_legacy_hte_preview(hte_payload)
            except (TypeError, ValueError, ValidationError):
                hte_projection_status = "invalid"
            else:
                hte_projection_status = "legacy_limited"
    normalized["hte"] = typed_hte
    normalized["hte_projection_status"] = hte_projection_status
    normalized["hte_legacy_limited"] = limited_hte
    normalized["document_outline"] = _normalize_outline(payload.get("document_outline"))
    normalized["metric_validation_comparison_rows"] = _normalize_metric_comparison_rows(
        payload.get("metric_validation_comparison_rows")
    )
    normalized["metric_significance_by_metric"] = _normalize_metric_significance(
        payload.get("metric_significance_by_metric"),
        comparison_rows=payload.get("metric_validation_comparison_rows"),
    )
    normalized["blocks"] = _normalize_authored_blocks(payload.get("blocks"))
    normalized["narrative_blocks"] = _normalize_authored_blocks(payload.get("narrative_blocks"))
    normalized["evidence_summary_blocks"] = _normalize_authored_blocks(
        payload.get("evidence_summary_blocks")
    )
    return DecisionPacketPreview.model_validate(normalized)


class ArtifactInspectorService:
    """Serve manifest/content/schema/lineage projections for one CAS artifact.

    The service never mutates CAS state. Missing artifacts and invalid artifact
    references surface as the underlying `ArtifactStore` exceptions so HTTP
    route handlers can translate them into RFC 7807 responses.
    """

    def __init__(
        self,
        *,
        store: ArtifactStore,
        lineage_service: LineageService,
        default_max_preview_bytes: int = 64 * 1024,
        redaction_hooks: dict[str, RedactionHook] | None = None,
    ) -> None:
        self._store = store
        self._lineage_service = lineage_service
        self._default_max_preview_bytes = min(max(default_max_preview_bytes, 1024), 2_000_000)
        self._redaction_hooks = dict(redaction_hooks or {})

    def get_manifest_view(
        self,
        artifact_id: ArtifactID,
        *,
        manifest: ArtifactManifest | None = None,
    ) -> ArtifactManifestView:
        """Return the manifest metadata used by `/artifacts/{id}/manifest`.

        Args:
            artifact_id: Canonical CAS artifact identifier.

        Returns:
            A normalized manifest projection with schema, producer, input, and
            integrity metadata.

        Raises:
            FileNotFoundError: If the artifact or its manifest sidecar is
                missing from CAS.
        """
        manifest = manifest or self._store.get_manifest(artifact_id)
        payload = manifest.model_dump(mode="json")
        self._assert_surface_admission_allowed(
            payload,
            artifact_id=artifact_id,
            manifest=manifest,
            surface="artifact",
            scope="CAS manifests",
        )
        schema = manifest.artifact_schema
        producer = manifest.producer
        return ArtifactManifestView(
            artifact_id=str(manifest.artifact_id),
            manifest_profile_sha256=artifact_manifest_profile_sha256(manifest),
            kind=manifest.kind,
            media_type=manifest.media_type,
            byte_size=int(manifest.byte_size),
            created_at=manifest.created_at,
            schema_name=schema.name if schema is not None else None,
            schema_version=schema.version if schema is not None else None,
            producer_component=str(producer.component) if producer is not None else None,
            producer_version=producer.version if producer is not None else None,
            inputs=list(manifest.inputs),
            integrity_sha256=manifest.integrity.sha256,
        )

    def get_predictive_coverage_diagnostic(
        self,
        artifact_id: ArtifactID,
        *,
        manifest: ArtifactManifest | None = None,
    ) -> PredictiveCoverageDiagnosticPreview | None:
        """Recompute a limited diagnostic from one exact persisted report view.

        Unsupported kind/schema and oversized reports return ``None`` so the
        HTTP layer can refuse rather than substituting a different report. A
        malformed but supported report returns the existing typed
        ``invalid_source`` diagnostic.
        """
        if manifest is None:
            selected_manifest, declaration = read_core_manifest_profile(self._store, artifact_id)
        else:
            selected_ref = _artifact_ref_for_manifest(manifest)
            selected_manifest, declaration = read_core_manifest_profile(
                self._store,
                selected_ref,
                manifest_profile_sha256=selected_ref.manifest_profile_sha256,
            )
            if selected_manifest != manifest:
                raise CanonicalProfileRefusalError("canon_profile_selected_manifest_changed")
        if declaration.status != "declared":
            raise CanonicalProfileRefusalError("canon_profile_not_verified")
        if selected_manifest.artifact_id != artifact_id:
            raise CanonicalProfileRefusalError("canon_profile_selection_unverified")
        schema = selected_manifest.artifact_schema
        if (
            selected_manifest.kind != "ir.backtest_report"
            or selected_manifest.media_type != "application/json"
            or schema is None
            or schema.name != "ir.backtest_report"
            or schema.version != "1.0"
            or selected_manifest.byte_size > _MAX_PREDICTIVE_COVERAGE_SOURCE_BYTES
        ):
            return None

        selected_ref = _artifact_ref_for_manifest(selected_manifest)
        canon_read_status: CanonReadStatus = "not_evaluated"
        try:
            profiled = _read_inspector_semantic_json(
                self._store,
                selected_ref,
                max_payload_bytes=_MAX_PREDICTIVE_COVERAGE_SOURCE_BYTES,
            )
            payload = profiled.value
            canon_read_status = profiled.status
        except CoreJsonReadBoundsRefusalError as exc:
            if _is_predictive_coverage_source_byte_cap_refusal(exc):
                return None
            raise
        except CanonicalProfileRefusalError:
            raise
        except (
            OverflowError,
            RecursionError,
            TypeError,
            UnicodeDecodeError,
            ValueError,
        ):
            payload = None
        return _predictive_coverage_preview(
            payload,
            selected_manifest,
            canon_read_status=canon_read_status,
        )

    def get_content_preview(
        self,
        artifact_id: ArtifactID,
        *,
        max_bytes: int | None = None,
        manifest: ArtifactManifest | None = None,
        manifest_read: CoreJsonManifestBoundedRead | None = None,
        allow_candidate_predictive_diagnostic_surface: bool = False,
        technical_inspection_evidence_ref: ArtifactRef | None = None,
    ) -> ArtifactContentPreview:
        """Return a bounded, redacted content preview for an artifact payload.

        JSON content and schema-key inspection use the exact selected Core
        bounded-member reader with byte, depth, element, and manifest limits.
        Over-limit JSON is an explicit typed refusal; raw and non-JSON content
        keeps its existing byte representation.

        Args:
            artifact_id: Canonical CAS artifact identifier.
            max_bytes: Optional per-request preview byte limit. Values are
                clamped to [1024, 2_000_000].
            allow_candidate_predictive_diagnostic_surface: Explicitly admit the
                reader-materialized predictive diagnostic sidecar. Defaults off.
            technical_inspection_evidence_ref: Exact selected evidence for the fixed
                technical-inspection purpose, reverified at this read.

        Returns:
            A content preview DTO with mode, truncation metadata, and sanitized
            payload content.

        Raises:
            FileNotFoundError: If the artifact bytes or manifest sidecar do not
                exist from CAS.
            CanonicalProfileRefusalError: If the selected Core profile is invalid
                or the JSON payload exceeds the bounded inspection policy.
        """
        if manifest is None:
            if manifest_read is None:
                manifest_read = read_core_manifest_profile_bounded(
                    self._store,
                    artifact_id,
                    max_manifest_bytes=INSPECTOR_MANIFEST_MAX_BYTES,
                )
            manifest = manifest_read.manifest
        selected_ref = _artifact_ref_for_manifest(manifest)
        preview_limit = _normalize_preview_limit(
            max_bytes,
            default_value=self._default_max_preview_bytes,
        )
        is_json = _is_json_media_type(manifest.media_type)
        requires_source_owner = (
            manifest.canon is not None
            and manifest.canon.version == "0.3.0"
            and (
                manifest.kind == MethodArtifactOutputPayload.ARTIFACT_KIND
                or (
                    manifest.artifact_schema is not None
                    and manifest.artifact_schema.name
                    == MethodArtifactOutputPayload.ARTIFACT_SCHEMA_NAME
                )
            )
        )
        # Unknown non-JSON cohorts retain raw inspection, explicitly without
        # canonical interpretation; known Method selectors require their owner.
        has_uninterpreted_profile = manifest.canon is not None and manifest.canon.version == "0.3.0"
        canon_read_status: CanonReadStatus = (
            "not_evaluated" if is_json or has_uninterpreted_profile else "not_applicable"
        )
        profiled_payload: Any = None
        if is_json or requires_source_owner:
            profiled = _read_inspector_semantic_json(
                self._store,
                selected_ref,
                max_payload_bytes=preview_limit,
                manifest_read=manifest_read,
            )
            data = profiled.raw_payload_bytes
            profiled_payload = profiled.value
            canon_read_status = profiled.status
        else:
            data = self._store.get_bytes(selected_ref)
        byte_size = len(data)
        truncated = byte_size > preview_limit
        preview_bytes = data[:preview_limit]

        mode: PreviewMode = "binary"
        preview: Any = None

        if is_json:
            mode = "json"
            preview = profiled_payload
        elif _is_text_media_type(manifest.media_type) or not truncated:
            text = _decode_text(preview_bytes)
            if text is not None:
                mode = "text"
                preview = text

        if mode != "json" and preview is None:
            mode = "binary"
            preview = preview_bytes.hex()

        self._assert_surface_admission_allowed(
            preview if mode == "json" else data,
            artifact_id=artifact_id,
            manifest=manifest,
            surface="artifact",
            scope="raw artifact content/download routes",
            technical_inspection_evidence_ref=technical_inspection_evidence_ref,
        )
        preview = _apply_redaction_hook(
            hooks=self._redaction_hooks,
            artifact_kind=manifest.kind,
            mode=mode,
            preview=preview,
        )
        preview = _apply_secret_pii_redaction(
            preview,
            artifact_id=str(artifact_id),
        )
        predictive_coverage_diagnostic = (
            _predictive_coverage_preview(
                preview,
                manifest,
                canon_read_status=canon_read_status,
            )
            if allow_candidate_predictive_diagnostic_surface and mode == "json" and not truncated
            else None
        )
        decision_packet_preview = (
            _build_decision_packet_preview(preview)
            if manifest.kind == "scientist.decision_packet" and mode == "json"
            else None
        )

        return ArtifactContentPreview(
            artifact_id=str(artifact_id),
            manifest_profile_sha256=artifact_manifest_profile_sha256(manifest),
            kind=manifest.kind,
            media_type=manifest.media_type,
            mode=mode,
            canon_read_status=canon_read_status,
            size_bytes=byte_size,
            max_bytes=preview_limit,
            truncated=truncated,
            preview=preview,
            decision_packet_preview=decision_packet_preview,
            predictive_coverage_diagnostic=predictive_coverage_diagnostic,
        )

    def get_schema_view(
        self,
        artifact_id: ArtifactID,
        *,
        manifest: ArtifactManifest | None = None,
        manifest_read: CoreJsonManifestBoundedRead | None = None,
        technical_inspection_evidence_ref: ArtifactRef | None = None,
    ) -> ArtifactSchemaView:
        """Return schema metadata plus top-level JSON keys when available.

        Args:
            artifact_id: Canonical CAS artifact identifier.
            technical_inspection_evidence_ref: Exact selected evidence for the fixed
                technical-inspection purpose, reverified at this read.

        Returns:
            A schema projection derived from the manifest and a bounded
            inspection of JSON payload keys.

        Raises:
            FileNotFoundError: If the artifact manifest or bytes are missing.
            CanonicalProfileRefusalError: If selected JSON exceeds the bounded
                inspection policy or fails Core profile conformance.
        """
        if manifest is None:
            if manifest_read is None:
                manifest_read = read_core_manifest_profile_bounded(
                    self._store,
                    artifact_id,
                    max_manifest_bytes=INSPECTOR_MANIFEST_MAX_BYTES,
                )
            manifest = manifest_read.manifest
        schema = manifest.artifact_schema

        selected_ref = _artifact_ref_for_manifest(manifest)
        top_keys: list[str] = []
        is_json = _is_json_media_type(manifest.media_type)
        requires_source_owner = (
            manifest.canon is not None
            and manifest.canon.version == "0.3.0"
            and (
                manifest.kind == MethodArtifactOutputPayload.ARTIFACT_KIND
                or (
                    manifest.artifact_schema is not None
                    and manifest.artifact_schema.name
                    == MethodArtifactOutputPayload.ARTIFACT_SCHEMA_NAME
                )
            )
        )
        # Unknown non-JSON cohorts retain raw inspection, explicitly without
        # canonical interpretation; known Method selectors require their owner.
        has_uninterpreted_profile = manifest.canon is not None and manifest.canon.version == "0.3.0"
        canon_read_status: CanonReadStatus = (
            "not_evaluated" if is_json or has_uninterpreted_profile else "not_applicable"
        )
        if is_json or requires_source_owner:
            schema_limit = _normalize_preview_limit(
                None, default_value=self._default_max_preview_bytes
            )
            try:
                profiled = _read_inspector_semantic_json(
                    self._store,
                    selected_ref,
                    max_payload_bytes=schema_limit,
                    manifest_read=manifest_read,
                )
                canon_read_status = profiled.status
                payload = profiled.value
                if isinstance(payload, dict):
                    top_keys = sorted(str(key) for key in payload)
            except CanonicalProfileRefusalError:
                raise
            except (TypeError, ValueError) as exc:
                logger.debug(
                    "Failed to load schema preview payload for %s: %s",
                    artifact_id,
                    exc,
                )
                top_keys = []
        view = ArtifactSchemaView(
            artifact_id=str(artifact_id),
            manifest_profile_sha256=artifact_manifest_profile_sha256(manifest),
            kind=manifest.kind,
            media_type=manifest.media_type,
            canon_read_status=canon_read_status,
            schema_name=schema.name if schema is not None else None,
            schema_version=schema.version if schema is not None else None,
            top_level_keys=top_keys,
        )
        self._assert_surface_admission_allowed(
            view.model_dump(mode="json"),
            artifact_id=artifact_id,
            manifest=manifest,
            surface="artifact",
            scope="dashboard/public/export packets",
            technical_inspection_evidence_ref=technical_inspection_evidence_ref,
        )
        return view

    def get_lineage_view(
        self,
        artifact_id: ArtifactID,
        *,
        max_depth: int | None = None,
        max_nodes: int | None = None,
        manifest: ArtifactManifest | None = None,
        manifest_profile_sha256: str | None = None,
    ) -> ArtifactLineageView:
        """Build an upstream lineage graph rooted at one artifact.

        Args:
            artifact_id: Root artifact to inspect.
            max_depth: Optional traversal depth override.
            max_nodes: Optional graph size override.
            manifest: Exact resolved root manifest when a profile is selected.
            manifest_profile_sha256: The selected root profile, or `None` for
                an explicitly legacy/default lookup.

        Returns:
            A lineage graph with completeness and corruption flags.
        """
        selected_manifest = manifest or self._store.get_manifest(artifact_id)
        selected_ref = _artifact_ref_for_manifest(selected_manifest)
        self._assert_surface_admission_allowed(
            {
                "lineage_root_artifact_id": str(artifact_id),
                "selected_manifest": selected_manifest.model_dump(mode="json"),
            },
            artifact_id=artifact_id,
            artifact_ref=selected_ref,
            surface="lineage",
            scope="dashboard/public/export packets",
        )
        return self._lineage_service.build_for_artifact_ids(
            [selected_ref],
            max_depth=max_depth,
            max_nodes=max_nodes,
        )

    def _assert_surface_admission_allowed(
        self,
        payload: object,
        *,
        artifact_id: ArtifactID,
        surface: str,
        scope: str,
        manifest: ArtifactManifest | None = None,
        artifact_ref: ArtifactRef | None = None,
        technical_inspection_evidence_ref: ArtifactRef | None = None,
    ) -> None:
        decision = authority_surface_decision(
            payload,
            surface=surface,
            purpose=(
                TECHNICAL_INSPECTION_PURPOSE
                if technical_inspection_evidence_ref is not None
                else None
            ),
            technical_inspection_evidence_ref=technical_inspection_evidence_ref,
            artifact_ref_or_route=f"artifact-inspector://{artifact_id}/{surface}",
            secret_pii_scope=scope,
            block_on_secret_findings=True,
            artifact_store=self._store,
            artifact_id=artifact_id,
            artifact_ref=(
                artifact_ref
                or (_artifact_ref_for_manifest(manifest) if manifest is not None else None)
            ),
            require_cas_integrity=True,
        )
        if decision.blocking or decision.visible_downgrade:
            raise ArtifactSurfaceAdmissionError(decision)


def _normalize_preview_limit(max_bytes: int | None, *, default_value: int) -> int:
    if max_bytes is None:
        return default_value
    return min(max(int(max_bytes), 1024), 2_000_000)


def _decode_text(payload: bytes) -> str | None:
    try:
        return payload.decode("utf-8")
    except UnicodeDecodeError:
        return None


def _is_json_media_type(media_type: str) -> bool:
    normalized = media_type.lower()
    return normalized == "application/json" or normalized.endswith("+json")


def _is_text_media_type(media_type: str) -> bool:
    normalized = media_type.lower()
    return normalized.startswith("text/")


def _apply_redaction_hook(
    *,
    hooks: dict[str, RedactionHook],
    artifact_kind: str,
    mode: PreviewMode,
    preview: Any,
) -> Any:
    lowered_kind = artifact_kind.lower()
    if any(marker in lowered_kind for marker in _SENSITIVE_KIND_MARKERS):
        return _REDACTED_PREVIEW

    hook = hooks.get(artifact_kind) or hooks.get("*")
    if hook is None:
        return preview
    try:
        return hook(preview, mode)
    except (AttributeError, RuntimeError, TypeError, ValueError) as exc:
        logger.warning("Redaction hook failed for kind=%s mode=%s: %s", artifact_kind, mode, exc)
        return _REDACTED_PREVIEW


def _apply_secret_pii_redaction(preview: Any, *, artifact_id: str) -> Any:
    try:
        result = scan_secret_and_pii(
            preview,
            scope="raw artifact content/download routes",
            artifact_ref_or_route=f"artifact-preview://{artifact_id}",
            redact=True,
            block_on_findings=False,
        )
    except (AttributeError, RuntimeError, TypeError, ValueError) as exc:
        logger.warning("Secret/PII preview scan failed for %s: %s", artifact_id, exc)
        return _REDACTED_PREVIEW
    return result.redacted_payload
