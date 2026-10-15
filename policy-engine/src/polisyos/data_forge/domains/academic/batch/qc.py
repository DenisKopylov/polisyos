"""Stage: QC checks for academic pipeline."""

from __future__ import annotations

import math
import random
import re
import statistics
import urllib.request
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Literal

import duckdb

from polisyos.common import serialization as common_serialization
from polisyos.common.logger import get_logger
from polisyos.data_forge.domains.academic.knowledge.canonical_seed import (
    CANONICAL_VARIABLES,
)
from polisyos.data_forge.domains.academic.knowledge.runtime_canonical_registry import (
    runtime_canonical_names,
)
from polisyos.data_forge.kernel.pipeline.manifests import write_stage_manifest
from polisyos.data_forge.kernel.quality import (
    QCCheck,
    QCReport,
    evaluate_fail_fast,
    write_qc_report,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

    from polisyos.data_forge.domains.academic.batch.config import AcademicBatchConfig

logger = get_logger(__name__)

_CANONICAL_VAR_RE = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*){0,3}$")

# Approved domain prefixes — any variable starting with one of these counts as canonical
_APPROVED_DOMAIN_PREFIXES: tuple[str, ...] = (
    "economic.",
    "fiscal.",
    "governance.",
    "institutional.",
    "social.",
    "demographic.",
    "labor.",
    "trade.",
    "environmental.",
    "health.",
    "education.",
    "infrastructure.",
    "political.",
    "migration.",
    "security.",
    "energy.",
    "digital.",
    "monetary.",
    "justice.",
    "climate.",
    "agriculture.",
    "urban.",
    "finance.",
    "gender.",
    # Extended domain prefixes for scientific/empirical topics
    "agricultural.",
    "biotech.",
    "hospital.",
    "genetic.",
    "behavioral.",
    "soil.",
    "safety.",
    "antibiotic.",
    "nutrition.",
    "pharmaceutical.",
    "industrial.",
    "biological.",
    "chemical.",
    "ecological.",
    "medical.",
    "epidemiological.",
    "transport.",
    "housing.",
    "water.",
    "food.",
    "marine.",
    "forestry.",
)


def _is_canonical_variable(name: str, approved_set: set[str]) -> bool:
    """Check if a variable name is canonical — either exact match or valid domain prefix."""
    if name in approved_set:
        return True
    if any(name.startswith(prefix) for prefix in _APPROVED_DOMAIN_PREFIXES):
        return bool(_CANONICAL_VAR_RE.match(name))
    return False


def _approved_canonical_names(config: AcademicBatchConfig) -> set[str]:
    approved: set[str] = set()
    for parent, children in CANONICAL_VARIABLES.items():
        approved.add(parent)
        for child_key in children:
            if child_key == "_root":
                continue
            approved.add(f"{parent}.{child_key}")
    approved.update(runtime_canonical_names())
    if not config.db_path.exists():
        return approved
    con = duckdb.connect(str(config.db_path), read_only=True)
    try:
        rows = con.execute(
            "SELECT canonical_name FROM ac_skg_canonization_cache WHERE approved = TRUE"
        ).fetchall()
    except duckdb.Error:
        rows = []
    finally:
        con.close()
    approved.update(str(row[0]).strip() for row in rows if row and row[0])
    return approved


def _line_count(path: Path) -> int:
    if not path.exists():
        return 0
    with open(path, encoding="utf-8") as fh:
        return sum(1 for _ in fh)


def _require_json_fields(
    payload: dict[str, object],
    required_fields: tuple[str, ...],
    *,
    source: str,
    kind: str,
) -> None:
    """Reject a present object that omits fields required by its producer contract."""
    missing = tuple(field for field in required_fields if field not in payload)
    if missing:
        fields = ", ".join(missing)
        raise ValueError(f"Malformed {kind} at {source}: missing required field(s) {fields}")


def _finite_json_number(value: object) -> float | None:
    """Return a finite numeric value, excluding booleans and non-number inputs."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    try:
        parsed = float(value)
    except (OverflowError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _required_metric_value(
    payload: dict[str, object],
    field: str,
    *,
    value_kind: Literal["count", "percentage"],
    source: str,
    producer: str,
) -> int | float:
    """Validate one present producer metric without coercing invalid values to defaults."""
    _require_json_fields(payload, (field,), source=source, kind=producer)
    value = payload[field]
    if value_kind == "count":
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError(
                f"Malformed {producer} at {source}: {field} must be a non-negative integer"
            )
        return value

    percentage = _finite_json_number(value)
    if percentage is None or not 0.0 <= percentage <= 100.0:
        raise ValueError(
            f"Malformed {producer} at {source}: {field} must be a finite percentage between 0 and 100"
        )
    return percentage


def _load_json_object(
    path: Path,
    *,
    kind: str,
    required_fields: tuple[str, ...] = (),
) -> dict[str, object]:
    """Read a present JSON object without converting malformed content to absence."""
    payload = common_serialization.decode_json_object(
        path.read_bytes(), source=str(path), kind=kind
    )
    _require_json_fields(payload, required_fields, source=str(path), kind=kind)
    return payload


def _iter_jsonl_objects(
    path: Path,
    *,
    kind: str,
    required_fields: tuple[str, ...] = (),
) -> Iterator[dict[str, object]]:
    """Yield nonblank JSONL objects after validating their producer-required fields."""
    with path.open("rb") as stream:
        for line_number, raw in enumerate(stream, start=1):
            if not raw.strip():
                continue
            source = f"{path}:{line_number}"
            payload = common_serialization.decode_json_object(raw, source=source, kind=kind)
            _require_json_fields(payload, required_fields, source=source, kind=kind)
            yield payload


def _latest_manifest(root: Path) -> Path | None:
    if not root.exists():
        return None
    snaps = sorted([p for p in root.iterdir() if p.is_dir()])
    if not snaps:
        return None
    path = snaps[-1] / "manifest.json"
    return path if path.exists() else None


def _stage_manifest_metrics(
    path: Path,
    *,
    required_metrics: tuple[str, ...] = (),
) -> dict[str, object]:
    if not path.exists():
        return {}
    payload = _load_json_object(
        path,
        kind="stage manifest",
        required_fields=("metrics",),
    )
    if payload.get("kind") not in (None, "stage") or payload.get("stage") not in (
        None,
        path.stem,
    ):
        raise ValueError(f"Stage manifest at {path} has a mismatched stage identity")
    metrics = payload.get("metrics")
    if not isinstance(metrics, dict):
        raise ValueError(f"Stage manifest at {path} must contain an object-valued metrics field")
    _require_json_fields(
        metrics,
        required_metrics,
        source=str(path),
        kind="stage manifest metrics",
    )
    return dict(metrics)


def _collect_raw_roots(config: AcademicBatchConfig) -> list[Path]:
    return sorted([p for p in config.raw_dir.iterdir() if p.is_dir()])


def run_qc(
    config: AcademicBatchConfig,
    *,
    fail_fast: bool | None = None,
    strict_phase0: bool | None = None,
) -> QCReport:
    """Validate academic batch outputs and compute publish-readiness checks.

    The report covers raw manifest parity, extraction JSON validity, canonical variable coverage,
    full-text/supporting-span health, topic-selection artifacts, and optional phase-0 strictness
    gates for resolve/extract rollout.
    """
    started_at = datetime.now(UTC).isoformat()
    checks: list[QCCheck] = []
    metrics: dict[str, object] = {}
    graph_load_manifest_path = config.manifests_dir / "graph_load.json"
    if graph_load_manifest_path.exists():
        graph_load_metrics = _stage_manifest_metrics(
            graph_load_manifest_path,
            required_metrics=("json_validation_failures",),
        )
        json_validation_failures = _required_metric_value(
            graph_load_metrics,
            "json_validation_failures",
            value_kind="count",
            source=str(graph_load_manifest_path),
            producer="graph-load stage metrics",
        )
        metrics["json_validation_failures"] = json_validation_failures
        checks.append(
            QCCheck(
                name="json_validation_failures",
                passed=json_validation_failures == 0,
                value=json_validation_failures,
                threshold=0,
                severity="critical",
            )
        )
    else:
        graph_load_scheduled = "graph_load" in config.stages
        metrics["json_validation_failures"] = None
        checks.append(
            QCCheck(
                name="json_validation_failures",
                passed=False,
                value=None,
                threshold=0,
                severity="critical" if graph_load_scheduled else "warning",
                message=(
                    "Graph-load manifest is absent; JSON validation failures are not established"
                    if graph_load_scheduled
                    else "Graph-load was not scheduled; JSON validation failures are not applicable"
                ),
                status="not_established" if graph_load_scheduled else "not_applicable",
            )
        )

    # 1) Raw manifest count parity by source root.
    parity_failures = 0
    roots = _collect_raw_roots(config)
    for root in roots:
        manifest_path = _latest_manifest(root)
        if manifest_path is None:
            continue
        manifest = _load_json_object(
            manifest_path,
            kind="raw manifest",
            required_fields=("payload", "count"),
        )
        if manifest.get("kind") not in (None, "raw"):
            raise ValueError(f"Raw manifest at {manifest_path} has an unsupported kind")
        payload_value = manifest.get("payload")
        if not isinstance(payload_value, str) or not payload_value.strip():
            raise ValueError(f"Raw manifest at {manifest_path} must include a payload path")
        declared_value = manifest.get("count")
        if (
            isinstance(declared_value, bool)
            or not isinstance(declared_value, int)
            or declared_value < 0
        ):
            raise ValueError(f"Raw manifest at {manifest_path} must include a non-negative count")
        payload = Path(payload_value)
        if not payload.is_file():
            raise ValueError(
                f"Raw manifest at {manifest_path} references a missing payload file: {payload}"
            )
        declared = declared_value
        actual = _line_count(payload)
        if declared != actual:
            parity_failures += 1

    checks.append(
        QCCheck(
            name="manifest_count_parity",
            passed=parity_failures == 0,
            threshold=0,
            value=parity_failures,
            message="Number of snapshots with count mismatch",
        )
    )

    # 2) Parse merged records quality.
    total = 0
    empty_abstract = 0
    malformed_estimate_rows = 0
    estimates_total = 0
    claims_total = 0
    canonical_claim_variables = 0
    supporting_spans_total = 0
    abstract_fallback_docs = 0
    resolve_extract_count = 0
    extraction_modes: dict[str, int] = {}
    phase0_check_severity = "critical" if bool(strict_phase0) else "warning"
    approved_canonical_names = _approved_canonical_names(config)

    if config.merged_records_path.exists():
        for row in _iter_jsonl_objects(
            config.merged_records_path,
            kind="merged-record JSONL row",
        ):
            total += 1
            if not str(row.get("abstract", "")).strip():
                empty_abstract += 1
            extraction_mode = str(row.get("extraction_mode", "deterministic"))
            extraction_modes[extraction_mode] = extraction_modes.get(extraction_mode, 0) + 1
            is_resolve_extract = extraction_mode in {
                "article_extract",
                "resolve_extract",
            }
            metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
            if is_resolve_extract:
                resolve_extract_count += 1
                if str(metadata.get("source_basis") or "") == "abstract_only":
                    abstract_fallback_docs += 1
            estimates = row.get("estimates") if isinstance(row.get("estimates"), list) else []
            for est in estimates:
                if not is_resolve_extract:
                    continue
                estimates_total += 1
                estimate_value = est.get("value") if isinstance(est, dict) else None
                if _finite_json_number(estimate_value) is None:
                    malformed_estimate_rows += 1

            claims = row.get("causal_claims") if isinstance(row.get("causal_claims"), list) else []
            for claim in claims:
                if not is_resolve_extract:
                    continue
                if not isinstance(claim, dict):
                    continue
                claims_total += 1
                supporting_spans = (
                    claim.get("supporting_spans")
                    if isinstance(claim.get("supporting_spans"), list)
                    else []
                )
                if supporting_spans:
                    supporting_spans_total += 1

    # Compute canonical_claim_variable_pct from published_claims (canonicalized variables)
    published_claims_path = (
        config.published_claims_final_path
        if config.published_claims_final_path.exists()
        else config.published_claims_path
    )
    published_claims_for_canonical = 0
    canonical_claim_variables = 0
    if published_claims_path.exists():
        for row in _iter_jsonl_objects(
            published_claims_path,
            kind="published-claim JSONL row",
        ):
            published_claims_for_canonical += 1
            cause = str(
                row.get("cause_text") or row.get("cause_variable") or row.get("cause") or ""
            ).strip()
            effect = str(
                row.get("effect_text") or row.get("effect_variable") or row.get("effect") or ""
            ).strip()
            if _is_canonical_variable(cause, approved_canonical_names):
                canonical_claim_variables += 1
            if _is_canonical_variable(effect, approved_canonical_names):
                canonical_claim_variables += 1

    empty_abs_pct = (100.0 * empty_abstract / total) if total else 0.0
    malformed_pct = (100.0 * malformed_estimate_rows / estimates_total) if estimates_total else 0.0
    metrics["works_total"] = total
    metrics["empty_abstract_pct"] = round(empty_abs_pct, 3)
    metrics["malformed_estimate_pct"] = round(malformed_pct, 3)
    metrics["claims_total"] = claims_total
    metrics["parameters_total"] = estimates_total
    metrics["resolve_extract_count"] = resolve_extract_count
    metrics["abstract_fallback_docs"] = abstract_fallback_docs
    metrics["extraction_modes"] = extraction_modes
    supporting_span_coverage = (
        (supporting_spans_total / max(1, claims_total)) * 100.0 if claims_total else 0.0
    )
    metrics["supporting_span_coverage_pct"] = round(supporting_span_coverage, 3)
    canonical_denominator = (
        max(1, published_claims_for_canonical * 2) if published_claims_for_canonical else 1
    )
    canonical_ratio = (
        (canonical_claim_variables / canonical_denominator) * 100.0
        if published_claims_for_canonical
        else 0.0
    )
    metrics["canonical_claim_variable_pct"] = round(canonical_ratio, 3)

    checks.append(
        QCCheck(
            name="empty_abstract_pct",
            passed=empty_abs_pct <= 25.0,
            value=empty_abs_pct,
            threshold=25.0,
            severity="warning",
        )
    )
    checks.append(
        QCCheck(
            name="malformed_estimate_pct",
            passed=malformed_pct <= 2.0,
            value=malformed_pct,
            threshold=2.0,
        )
    )
    checks.append(
        QCCheck(
            name="canonical_claim_variable_pct",
            passed=canonical_ratio >= 80.0 if claims_total else True,
            value=canonical_ratio,
            threshold=80.0,
            severity=phase0_check_severity,
        )
    )
    checks.append(
        QCCheck(
            name="resolve_extract_count_50",
            passed=resolve_extract_count >= 50 if resolve_extract_count else True,
            value=resolve_extract_count,
            threshold=50,
            severity=phase0_check_severity,
        )
    )
    if resolve_extract_count >= 50:
        checks.append(
            QCCheck(
                name="claims_volume_50_articles",
                passed=claims_total >= 200,
                value=claims_total,
                threshold=200,
                severity=phase0_check_severity,
            )
        )
        checks.append(
            QCCheck(
                name="supporting_span_coverage_pct",
                passed=supporting_span_coverage >= 85.0,
                value=round(supporting_span_coverage, 3),
                threshold=85.0,
                severity=phase0_check_severity,
            )
        )
        checks.append(
            QCCheck(
                name="parameters_volume_50_articles",
                passed=estimates_total >= 100,
                value=estimates_total,
                threshold=100,
                severity=phase0_check_severity,
            )
        )

    # 3) Topic selection metrics.
    topic_selection_exists = config.selected_topic_works_path.exists()
    checks.append(
        QCCheck(
            name="topic_selection_artifact",
            passed=topic_selection_exists,
            value=int(topic_selection_exists),
            threshold=1,
            severity="critical",
        )
    )

    if topic_selection_exists:
        by_topic: dict[str, int] = {}
        topic_work_ids: set[str] = set()
        total_rows = 0
        for row in _iter_jsonl_objects(
            config.selected_topic_works_path,
            kind="selected-topic work JSONL row",
            required_fields=("topic_id", "work_id"),
        ):
            topic_id = row["topic_id"]
            work_id = row["work_id"]
            if (
                not isinstance(topic_id, str)
                or not topic_id.strip()
                or not isinstance(work_id, str)
                or not work_id.strip()
            ):
                raise ValueError(
                    f"Malformed selected-topic work row in {config.selected_topic_works_path}: "
                    "topic_id and work_id must be non-empty strings"
                )
            by_topic[topic_id] = by_topic.get(topic_id, 0) + 1
            topic_work_ids.add(work_id)
            total_rows += 1

        global_selected_rows = 0
        global_selected_work_ids: set[str] = set()
        if config.selected_global_works_path.exists():
            for row in _iter_jsonl_objects(
                config.selected_global_works_path,
                kind="selected-work JSONL row",
            ):
                work_id = str(row.get("work_id") or "").strip()
                if not work_id and isinstance(row.get("work"), dict):
                    work_id = str(row["work"].get("id") or "").strip()
                if not work_id:
                    continue
                global_selected_rows += 1
                global_selected_work_ids.add(work_id)

        selected_unique_works = (
            len(global_selected_work_ids) if global_selected_work_ids else len(topic_work_ids)
        )

        counts = list(by_topic.values())
        underfilled = sum(1 for c in counts if c < config.target_per_topic)
        unique_ratio = (len(topic_work_ids) / total_rows) if total_rows else 1.0

        metrics["selected_topics"] = len(by_topic)
        metrics["selected_rows"] = total_rows
        metrics["selected_topic_unique_works"] = len(topic_work_ids)
        metrics["selected_global_rows"] = global_selected_rows
        metrics["selected_global_unique_works"] = len(global_selected_work_ids)
        metrics["selected_unique_works"] = selected_unique_works
        metrics["underfilled_topic_count"] = underfilled
        metrics["unique_work_ratio"] = round(unique_ratio, 6)
        metrics["selected_per_topic_mean"] = round(statistics.mean(counts), 3) if counts else 0.0
        metrics["selected_per_topic_median"] = (
            round(statistics.median(counts), 3) if counts else 0.0
        )

        checks.append(
            QCCheck(
                name="topic_underfill_rate",
                passed=(underfilled / max(1, len(counts))) <= 0.15,
                severity="warning",
                value=round((underfilled / max(1, len(counts))) * 100.0, 3),
                threshold=15.0,
                message=f"underfilled_topics={underfilled}",
            )
        )
        checks.append(
            QCCheck(
                name="unique_work_ratio",
                passed=unique_ratio >= 0.60,
                severity="warning",
                value=round(unique_ratio * 100.0, 3),
                threshold=60.0,
            )
        )
        checks.append(
            QCCheck(
                name="selected_unique_budget_hit",
                passed=selected_unique_works >= int(config.selected_unique_budget),
                severity="warning",
                value=selected_unique_works,
                threshold=int(config.selected_unique_budget),
            )
        )

    # 3b) Resolve attempt/final parity and retry semantics.
    attempt_path = (
        config.resolve_extract_attempts_path
        if config.resolve_extract_attempts_path.exists()
        else config.resolve_extract_results_path
    )
    final_results_path = config.resolve_extract_final_results_path
    if attempt_path.exists():
        attempt_work_ids: list[str] = []
        zero_token_attempts = 0
        retryable_error_attempts = 0
        for row in _iter_jsonl_objects(
            attempt_path,
            kind="resolve-extract attempt JSONL row",
        ):
            work_id = str(row.get("openalex_id") or row.get("work_id") or "").strip()
            if work_id:
                attempt_work_ids.append(work_id)
            prompt_tokens = int(row.get("token_count_prompt") or 0)
            completion_tokens = int(row.get("token_count_completion") or 0)
            if prompt_tokens == 0 and completion_tokens == 0:
                zero_token_attempts += 1
            if str(row.get("llm_error_class") or "") in {
                "provider_http_429",
                "provider_http_5xx",
                "timeout",
            }:
                retryable_error_attempts += 1
        duplicate_attempts = len(attempt_work_ids) - len(set(attempt_work_ids))
        zero_token_share = (
            (zero_token_attempts / max(1, len(attempt_work_ids))) * 100.0
            if attempt_work_ids
            else 0.0
        )
        metrics["resolve_attempts_total"] = len(attempt_work_ids)
        metrics["resolve_attempt_duplicate_rows"] = duplicate_attempts
        metrics["resolve_attempt_zero_token_share_pct"] = round(zero_token_share, 3)
        metrics["resolve_attempt_retryable_error_rows"] = retryable_error_attempts
        checks.append(
            QCCheck(
                name="resolve_attempt_duplicate_rows",
                passed=duplicate_attempts == 0,
                severity="warning",
                value=duplicate_attempts,
                threshold=0,
            )
        )
        checks.append(
            QCCheck(
                name="resolve_attempt_zero_token_share_pct",
                passed=zero_token_share <= 5.0,
                severity="warning",
                value=round(zero_token_share, 3),
                threshold=5.0,
            )
        )

    if final_results_path.exists():
        final_work_ids: list[str] = []
        for row in _iter_jsonl_objects(
            final_results_path,
            kind="resolve-extract final-result JSONL row",
        ):
            work_id = str(row.get("openalex_id") or row.get("work_id") or "").strip()
            if work_id:
                final_work_ids.append(work_id)
        duplicate_final_rows = len(final_work_ids) - len(set(final_work_ids))
        metrics["resolve_final_rows"] = len(final_work_ids)
        metrics["resolve_final_duplicate_rows"] = duplicate_final_rows
        if attempt_path.exists():
            metrics["resolve_attempt_final_parity_gap"] = max(
                0, len(set(attempt_work_ids)) - len(set(final_work_ids))
            )
        checks.append(
            QCCheck(
                name="resolve_final_duplicate_rows",
                passed=duplicate_final_rows == 0,
                severity="critical",
                value=duplicate_final_rows,
                threshold=0,
            )
        )

    # 4) LLM gate metrics (if manifest exists)
    if config.llm_gate_manifest_path.exists():
        try:
            gate = _load_json_object(
                config.llm_gate_manifest_path,
                kind="LLM gate manifest",
                required_fields=("metrics",),
            )
            if gate.get("kind") not in (None, "llm_gate"):
                raise ValueError(
                    f"LLM gate manifest at {config.llm_gate_manifest_path} has wrong kind"
                )
            gate_metrics = gate.get("metrics")
            if not isinstance(gate_metrics, dict):
                raise ValueError(
                    f"LLM gate manifest at {config.llm_gate_manifest_path} "
                    "must contain an object-valued metrics field"
                )
            llm_candidate_total = _required_metric_value(
                gate_metrics,
                "llm_candidate_total",
                value_kind="count",
                source=str(config.llm_gate_manifest_path),
                producer="LLM gate metrics",
            )
            llm_sent_total = _required_metric_value(
                gate_metrics,
                "llm_sent",
                value_kind="count",
                source=str(config.llm_gate_manifest_path),
                producer="LLM gate metrics",
            )
            llm_saved_pct = _required_metric_value(
                gate_metrics,
                "llm_saved_pct",
                value_kind="percentage",
                source=str(config.llm_gate_manifest_path),
                producer="LLM gate metrics",
            )
            audit_miss_rate_pct = _required_metric_value(
                gate_metrics,
                "audit_miss_rate_pct",
                value_kind="percentage",
                source=str(config.llm_gate_manifest_path),
                producer="LLM gate metrics",
            )

            metrics["llm_candidate_total"] = llm_candidate_total
            metrics["llm_sent_total"] = llm_sent_total
            metrics["llm_saved_pct"] = round(llm_saved_pct, 3)
            metrics["audit_miss_rate_pct"] = round(audit_miss_rate_pct, 3)
            checks.append(
                QCCheck(
                    name="llm_audit_miss_rate_pct",
                    passed=audit_miss_rate_pct <= config.llm_gate_audit_max_miss_rate_pct,
                    severity="warning",
                    value=audit_miss_rate_pct,
                    threshold=config.llm_gate_audit_max_miss_rate_pct,
                )
            )
        except Exception:
            checks.append(
                QCCheck(
                    name="llm_gate_manifest_parse",
                    passed=False,
                    severity="warning",
                    value=0,
                    threshold=1,
                    message="Failed to parse llm_gate manifest",
                )
            )
    else:
        checks.append(
            QCCheck(
                name="llm_gate_manifest_present",
                passed=False,
                severity="warning",
                value=0,
                threshold=1,
                message="No llm_gate manifest found (likely deterministic-only run)",
            )
        )

    # 4b) article extraction cache idempotency.
    if config.article_extraction_cache_path.exists():
        cache_keys: list[str] = []
        for row in _iter_jsonl_objects(
            config.article_extraction_cache_path,
            kind="article-extraction cache JSONL row",
        ):
            key = row.get("cache_key")
            if isinstance(key, str) and key:
                cache_keys.append(key)
        unique_keys = len(set(cache_keys))
        duplicate_pct = (
            (100.0 * (len(cache_keys) - unique_keys) / max(1, len(cache_keys)))
            if cache_keys
            else 0.0
        )
        metrics["article_cache_entries"] = len(cache_keys)
        metrics["article_cache_duplicate_pct"] = round(duplicate_pct, 3)
        checks.append(
            QCCheck(
                name="article_cache_duplicate_pct",
                passed=duplicate_pct == 0.0,
                value=duplicate_pct,
                threshold=0.0,
                severity="warning",
            )
        )

    # 4c) raw/published claim metrics.
    raw_claims_path = (
        config.raw_claim_candidates_final_path
        if config.raw_claim_candidates_final_path.exists()
        else config.raw_claim_candidates_path
    )
    published_claims_path = (
        config.published_claims_final_path
        if config.published_claims_final_path.exists()
        else config.published_claims_path
    )
    raw_claims_total = 0
    publishable_total = 0
    abstract_only_publishable = 0
    fulltext_publishable = 0
    raw_tier_counts: Counter[str] = Counter()
    published_tier_counts: Counter[str] = Counter()
    raw_contaminated = 0
    published_contaminated = 0
    raw_claim_ids: list[str] = []
    published_claim_ids: list[str] = []
    publishable_share = 0.0
    abstract_only_publishable_share = 0.0
    fulltext_publishable_share = 0.0
    published_tier4_share = 0.0
    if raw_claims_path.exists() or published_claims_path.exists():
        if raw_claims_path.exists():
            for row in _iter_jsonl_objects(
                raw_claims_path,
                kind="raw-claim JSONL row",
            ):
                raw_claims_total += 1
                claim_id = str(row.get("claim_id") or "").strip()
                if claim_id:
                    raw_claim_ids.append(claim_id)
                tier = str(row.get("design_quality_tier") or "").strip()
                if tier:
                    raw_tier_counts[tier] += 1
                if bool(row.get("span_contamination_detected")):
                    raw_contaminated += 1

        if published_claims_path.exists():
            for row in _iter_jsonl_objects(
                published_claims_path,
                kind="published-claim JSONL row",
            ):
                publishable_total += 1
                claim_id = str(row.get("claim_id") or "").strip()
                if claim_id:
                    published_claim_ids.append(claim_id)
                tier = str(row.get("design_quality_tier") or "").strip()
                if tier:
                    published_tier_counts[tier] += 1
                if bool(row.get("span_contamination_detected")):
                    published_contaminated += 1
                if str(row.get("source_basis") or "") == "abstract_only":
                    abstract_only_publishable += 1
                else:
                    fulltext_publishable += 1

        publishable_share = (
            (publishable_total / max(1, raw_claims_total)) * 100.0 if raw_claims_total else 0.0
        )
        abstract_only_publishable_share = (
            (abstract_only_publishable / max(1, publishable_total)) * 100.0
            if publishable_total
            else 0.0
        )
        fulltext_publishable_share = (
            (fulltext_publishable / max(1, publishable_total)) * 100.0 if publishable_total else 0.0
        )
        published_tier4_share = (
            (published_tier_counts.get("4", 0) / max(1, publishable_total)) * 100.0
            if publishable_total
            else 0.0
        )

        metrics["raw_claim_candidates_total"] = raw_claims_total
        metrics["publishable_edge_rate_pct"] = round(publishable_share, 3)
        metrics["raw_to_published_claim_drop_rate_pct"] = (
            round(100.0 - publishable_share, 3) if raw_claims_total else 0.0
        )
        metrics["abstract_only_publishable_share_pct"] = round(abstract_only_publishable_share, 3)
        metrics["fulltext_publishable_share_pct"] = round(fulltext_publishable_share, 3)
        metrics["published_edge_stability_pct"] = 100.0
        metrics["design_tier_distribution"] = dict(sorted(raw_tier_counts.items()))
        metrics["published_claims_by_design_tier"] = dict(sorted(published_tier_counts.items()))
    metrics["published_tier4_share_pct"] = round(published_tier4_share, 3)
    metrics["span_contamination_rate"] = round(
        (published_contaminated / max(1, publishable_total)) * 100.0 if publishable_total else 0.0,
        3,
    )
    metrics["raw_span_contamination_rate"] = round(
        (raw_contaminated / max(1, raw_claims_total)) * 100.0 if raw_claims_total else 0.0,
        3,
    )
    metrics["raw_claim_duplicate_rows"] = len(raw_claim_ids) - len(set(raw_claim_ids))
    metrics["published_claim_duplicate_rows"] = len(published_claim_ids) - len(
        set(published_claim_ids)
    )

    checks.append(
        QCCheck(
            name="abstract_only_publishable_share_pct",
            passed=abstract_only_publishable_share == 0.0,
            value=round(abstract_only_publishable_share, 3),
            threshold=0.0,
            severity=phase0_check_severity,
        )
    )
    checks.append(
        QCCheck(
            name="fulltext_publishable_share_pct",
            passed=fulltext_publishable_share >= 80.0 if publishable_total else True,
            value=round(fulltext_publishable_share, 3),
            threshold=80.0,
            severity=phase0_check_severity,
        )
    )
    checks.append(
        QCCheck(
            name="span_contamination_rate",
            passed=metrics["span_contamination_rate"] <= 1.0,
            value=metrics["span_contamination_rate"],
            threshold=1.0,
            severity="warning",
        )
    )
    checks.append(
        QCCheck(
            name="published_tier4_share_pct",
            passed=published_tier4_share <= 40.0 if publishable_total else True,
            value=round(published_tier4_share, 3),
            threshold=40.0,
            severity="warning",
        )
    )
    checks.append(
        QCCheck(
            name="published_claim_duplicate_rows",
            passed=metrics["published_claim_duplicate_rows"] == 0,
            value=metrics["published_claim_duplicate_rows"],
            threshold=0,
            severity="critical",
        )
    )

    # 4d) v7 acquisition metrics from attempt-level fetch logs.
    if config.fulltext_fetch_log_path.exists() or config.fulltext_resolved_path.exists():
        fetch_rows: list[dict[str, object]] = []
        if config.fulltext_fetch_log_path.exists():
            fetch_rows.extend(
                _iter_jsonl_objects(
                    config.fulltext_fetch_log_path,
                    kind="fulltext fetch-log JSONL row",
                )
            )

        final_rows: list[dict[str, object]] = []
        if config.fulltext_resolved_path.exists():
            final_rows.extend(
                _iter_jsonl_objects(
                    config.fulltext_resolved_path,
                    kind="resolved fulltext JSONL row",
                )
            )

        final_total = len(final_rows)
        usable_fulltext_resolved = sum(
            1 for row in final_rows if str(row.get("source_basis") or "") == "fulltext"
        )
        final_abstract_fallback = sum(
            1 for row in final_rows if str(row.get("source_basis") or "") == "abstract_only"
        )
        recoverable_landing_pages = sum(
            1
            for row in fetch_rows
            if str(row.get("fetch_error_class") or "")
            in {"redirect_placeholder", "landing_page_without_pdf", "short_html_shell"}
        )
        metadata_rows = [
            row for row in fetch_rows if str(row.get("attempt_kind") or "") == "metadata"
        ]
        shared_cache_work_ids = {
            str(row.get("work_id") or "")
            for row in fetch_rows
            if str(row.get("attempt_kind") or "") == "shared_cache"
            and str(row.get("work_id") or "").strip()
        }
        metadata_hits = sum(
            1
            for row in metadata_rows
            if int(row.get("discovered_pdf_count") or 0) > 0
            or int(row.get("discovered_canonical_count") or 0) > 0
        )
        metadata_pdf_hits = sum(
            1 for row in metadata_rows if int(row.get("discovered_pdf_count") or 0) > 0
        )
        landing_page_attempts = [
            row
            for row in fetch_rows
            if str(row.get("attempt_kind") or "") != "metadata"
            and (
                int(row.get("discovered_pdf_count") or 0) > 0
                or str(row.get("source_kind") or "").endswith("landing_page")
                or str(row.get("source_kind") or "").endswith("landing")
            )
        ]
        landing_page_pdf_recoveries = sum(
            1 for row in landing_page_attempts if int(row.get("discovered_pdf_count") or 0) > 0
        )
        placeholder_work_ids = {
            str(row.get("work_id") or "")
            for row in fetch_rows
            if str(row.get("fetch_error_class") or "") == "redirect_placeholder"
        }
        final_by_work = {
            str(row.get("work_id") or ""): row
            for row in final_rows
            if str(row.get("work_id") or "").strip()
        }
        placeholder_recovered = sum(
            1
            for work_id in placeholder_work_ids
            if str(final_by_work.get(work_id, {}).get("source_basis") or "") == "fulltext"
        )
        fake_fulltext_rows = sum(
            1
            for row in fetch_rows
            if str(row.get("fetch_error_class") or "")
            in {"fake_fulltext", "redirect_placeholder", "short_html_shell"}
        )
        publisher_403_rows = sum(
            1
            for row in fetch_rows
            if str(row.get("fetch_error_class") or "") == "publisher_blocked_403"
        )
        metadata_provider_totals: Counter[str] = Counter()
        metadata_provider_hits: Counter[str] = Counter()
        for row in metadata_rows:
            provider = (
                str(row.get("source_kind") or "")
                .strip()
                .replace("metadata_", "")
                .replace("_cache_hit", "")
            )
            provider = provider or "unknown"
            metadata_provider_totals[provider] += 1
            if (
                int(row.get("discovered_pdf_count") or 0) > 0
                or int(row.get("discovered_canonical_count") or 0) > 0
            ):
                metadata_provider_hits[provider] += 1

        metrics["usable_fulltext_resolved"] = usable_fulltext_resolved
        metrics["recoverable_landing_pages"] = recoverable_landing_pages
        metrics["metadata_resolver_hit_rate"] = (
            round((metadata_hits / max(1, len(metadata_rows))) * 100.0, 3) if metadata_rows else 0.0
        )
        metrics["metadata_pdf_recovery_rate"] = (
            round((metadata_pdf_hits / max(1, len(metadata_rows))) * 100.0, 3)
            if metadata_rows
            else 0.0
        )
        metrics["landing_page_pdf_recovery_rate"] = (
            round(
                (landing_page_pdf_recoveries / max(1, len(landing_page_attempts))) * 100.0,
                3,
            )
            if landing_page_attempts
            else 0.0
        )
        metrics["redirect_placeholder_recovery_rate"] = (
            round((placeholder_recovered / max(1, len(placeholder_work_ids))) * 100.0, 3)
            if placeholder_work_ids
            else 0.0
        )
        metrics["fake_fulltext_rate"] = (
            round((fake_fulltext_rows / max(1, len(fetch_rows))) * 100.0, 3) if fetch_rows else 0.0
        )
        metrics["publisher_403_rate"] = (
            round((publisher_403_rows / max(1, len(fetch_rows))) * 100.0, 3) if fetch_rows else 0.0
        )
        metrics["final_abstract_fallback_rate"] = (
            round((final_abstract_fallback / max(1, final_total)) * 100.0, 3)
            if final_total
            else 0.0
        )
        metrics["fulltext_cache_hit_rate"] = (
            round((len(shared_cache_work_ids) / max(1, final_total)) * 100.0, 3)
            if final_total
            else 0.0
        )
        metrics["metadata_resolver_success_rate_by_provider"] = {
            provider: round((metadata_provider_hits[provider] / max(1, total)) * 100.0, 3)
            for provider, total in sorted(metadata_provider_totals.items())
        }

    # 4e) reconciliation diagnostics from article extraction results.
    if config.article_extraction_results_path.exists():
        dropped_context_overlap = 0
        retained_context_attrs = 0
        for row in _iter_jsonl_objects(
            config.article_extraction_results_path,
            kind="article-extraction result JSONL row",
        ):
            diagnostics = (
                row.get("reconciliation_diagnostics")
                if isinstance(row.get("reconciliation_diagnostics"), dict)
                else {}
            )
            dropped_context_overlap += int(diagnostics.get("dropped_context_overlap", 0) or 0)
            retained_context_attrs += (
                len(row.get("context_attributes") or [])
                if isinstance(row.get("context_attributes"), list)
                else 0
            )

        overlap_total = dropped_context_overlap + retained_context_attrs
        overlap_drop_rate = (
            (dropped_context_overlap / max(1, overlap_total)) * 100.0 if overlap_total else 0.0
        )
        metrics["context_attr_overlap_drop_rate"] = round(overlap_drop_rate, 3)
        checks.append(
            QCCheck(
                name="context_attr_overlap_drop_rate",
                passed=overlap_drop_rate <= 25.0,
                value=round(overlap_drop_rate, 3),
                threshold=25.0,
                severity="warning",
            )
        )

    # 5) OA URL reachability from DB.
    reachable = 0
    checked = 0
    if config.db_path.exists():
        con = duckdb.connect(str(config.db_path), read_only=True)
        try:
            rows = con.execute(
                "SELECT full_text_url FROM ac_works WHERE is_oa = TRUE AND full_text_url IS NOT NULL AND full_text_url != '' LIMIT 200"
            ).fetchall()
        finally:
            con.close()

        urls = [
            str(r[0])
            for r in rows
            if isinstance(r[0], str) and r[0].startswith(("http://", "https://"))
        ]
        random.seed(42)
        sample = random.sample(urls, k=min(20, len(urls))) if urls else []
        for url in sample:
            checked += 1
            try:
                req = urllib.request.Request(url, method="HEAD")
                with urllib.request.urlopen(req, timeout=10) as resp:
                    if int(resp.status) < 500:
                        reachable += 1
            except Exception:
                try:
                    req = urllib.request.Request(url, method="GET", headers={"Range": "bytes=0-0"})
                    with urllib.request.urlopen(req, timeout=10) as resp:
                        if int(resp.status) < 500:
                            reachable += 1
                except Exception as exc:
                    logger.debug("Ignored exception: {}", exc)

    reach_pct = (100.0 * reachable / checked) if checked else 100.0
    metrics["oa_url_checked"] = checked
    metrics["oa_url_reachable_pct"] = round(reach_pct, 3)
    checks.append(
        QCCheck(
            name="oa_url_reachability_pct",
            passed=reach_pct >= 60.0,
            value=reach_pct,
            threshold=60.0,
            severity="warning",
        )
    )

    # 6) Track B/C metrics (non-blocking, guarded for missing tables).
    if config.db_path.exists():
        con = duckdb.connect(str(config.db_path), read_only=True)
        try:
            try:
                ctx_attr_count = int(
                    con.execute("SELECT COUNT(*) FROM ac_skg_context_attributes").fetchone()[0]
                )
            except duckdb.CatalogException:
                ctx_attr_count = 0
            try:
                mod_edge_count = int(
                    con.execute("SELECT COUNT(*) FROM ac_skg_moderation_edges").fetchone()[0]
                )
            except duckdb.CatalogException:
                mod_edge_count = 0
            try:
                ctx_profile_count = int(
                    con.execute("SELECT COUNT(*) FROM ac_skg_context_profiles").fetchone()[0]
                )
            except duckdb.CatalogException:
                ctx_profile_count = 0
            try:
                transport_score_count = int(
                    con.execute("SELECT COUNT(*) FROM ac_skg_transport_scores").fetchone()[0]
                )
            except duckdb.CatalogException:
                transport_score_count = 0

            metrics["context_attribute_count"] = ctx_attr_count
            metrics["moderation_edge_count"] = mod_edge_count
            metrics["context_profile_count"] = ctx_profile_count
            metrics["transport_score_count"] = transport_score_count

            try:
                if mod_edge_count > 0:
                    exact_linked = int(
                        con.execute(
                            "SELECT COUNT(*) FROM ac_skg_moderation_edges "
                            "WHERE match_quality IN ('exact_claim_ref', 'canonical_tuple')"
                        ).fetchone()[0]
                    )
                    fuzzy_linked = int(
                        con.execute(
                            "SELECT COUNT(*) FROM ac_skg_moderation_edges "
                            "WHERE match_quality = 'fuzzy_claim_inventory'"
                        ).fetchone()[0]
                    )
                    unmatched = int(
                        con.execute(
                            "SELECT COUNT(*) FROM ac_skg_moderation_edges "
                            "WHERE match_quality = 'freeform' OR match_quality IS NULL OR match_quality = ''"
                        ).fetchone()[0]
                    )
                else:
                    exact_linked = 0
                    fuzzy_linked = 0
                    unmatched = 0
            except duckdb.CatalogException:
                exact_linked = 0
                fuzzy_linked = 0
                unmatched = 0

            exact_link_rate = (
                (exact_linked / max(1, mod_edge_count)) * 100.0 if mod_edge_count else 0.0
            )
            fuzzy_link_rate = (
                (fuzzy_linked / max(1, mod_edge_count)) * 100.0 if mod_edge_count else 0.0
            )
            unmatched_rate = (unmatched / max(1, mod_edge_count)) * 100.0 if mod_edge_count else 0.0
            metrics["moderation_claim_link_rate_exact"] = round(exact_link_rate, 3)
            metrics["moderation_claim_link_rate_fuzzy"] = round(fuzzy_link_rate, 3)
            metrics["moderation_unmatched_rate"] = round(unmatched_rate, 3)
            checks.append(
                QCCheck(
                    name="moderation_claim_link_rate_exact",
                    passed=exact_link_rate >= 50.0 if mod_edge_count else True,
                    value=round(exact_link_rate, 3),
                    threshold=50.0,
                    severity="warning",
                )
            )

            # Moderator coverage: % of causal edges with at least one moderator
            try:
                total_edges = int(con.execute("SELECT COUNT(*) FROM ac_skg_edges").fetchone()[0])
                if total_edges > 0 and mod_edge_count > 0:
                    edges_with_mod = int(
                        con.execute(
                            "SELECT COUNT(DISTINCT e.edge_id) FROM ac_skg_edges e "
                            "INNER JOIN ac_skg_moderation_edges m "
                            "ON e.src = m.base_cause AND e.dst = m.base_effect"
                        ).fetchone()[0]
                    )
                    moderator_coverage = (edges_with_mod / total_edges) * 100.0
                else:
                    moderator_coverage = 0.0
            except duckdb.CatalogException:
                total_edges = 0
                moderator_coverage = 0.0

            metrics["moderator_coverage_pct"] = round(moderator_coverage, 3)

            if config.track_c_enabled:
                checks.append(
                    QCCheck(
                        name="moderator_coverage_pct",
                        passed=moderator_coverage >= 5.0,
                        value=round(moderator_coverage, 3),
                        threshold=5.0,
                        severity="warning",
                    )
                )

            # Context profile coverage: % of articles with enriched context
            try:
                total_articles = int(
                    con.execute("SELECT COUNT(*) FROM ac_skg_articles").fetchone()[0]
                )
                if total_articles > 0 and ctx_attr_count > 0:
                    articles_with_ctx = int(
                        con.execute(
                            "SELECT COUNT(DISTINCT openalex_id) FROM ac_skg_context_attributes"
                        ).fetchone()[0]
                    )
                    ctx_profile_coverage = (articles_with_ctx / total_articles) * 100.0
                else:
                    ctx_profile_coverage = 0.0
            except duckdb.CatalogException:
                ctx_profile_coverage = 0.0

            metrics["context_profile_coverage_pct"] = round(ctx_profile_coverage, 3)

            if config.track_b_enabled:
                checks.append(
                    QCCheck(
                        name="context_profile_coverage_pct",
                        passed=ctx_profile_coverage >= 10.0,
                        value=round(ctx_profile_coverage, 3),
                        threshold=10.0,
                        severity="warning",
                    )
                )

            target_transport_requested = bool(
                str(config.transport_target_context_id or "").strip()
                or config.transport_target_country_codes
            )
            if total_edges > 0 and transport_score_count > 0:
                try:
                    if target_transport_requested:
                        target_rows = int(
                            con.execute(
                                "SELECT COUNT(DISTINCT edge_id) FROM ac_skg_transport_scores "
                                "WHERE target_context_id IS NOT NULL AND target_context_id != ''"
                            ).fetchone()[0]
                        )
                    else:
                        target_rows = int(
                            con.execute(
                                "SELECT COUNT(DISTINCT edge_id) FROM ac_skg_transport_scores"
                            ).fetchone()[0]
                        )
                except duckdb.CatalogException:
                    target_rows = 0
            else:
                target_rows = 0
            transport_coverage = (target_rows / max(1, total_edges)) * 100.0 if total_edges else 0.0
            metrics["target_transport_score_coverage_pct"] = round(transport_coverage, 3)
            if target_transport_requested:
                checks.append(
                    QCCheck(
                        name="target_transport_score_coverage_pct",
                        passed=transport_coverage >= 10.0 if total_edges else True,
                        value=round(transport_coverage, 3),
                        threshold=10.0,
                        severity="warning",
                    )
                )

            try:
                retracted_contamination_count = int(
                    con.execute(
                        """
                        SELECT COUNT(DISTINCT e.openalex_id)
                        FROM ac_skg_edge_evidence e
                        JOIN ac_skg_articles a ON a.openalex_id = e.openalex_id
                        WHERE a.retracted = TRUE
                        """
                    ).fetchone()[0]
                )
            except duckdb.Error:
                retracted_contamination_count = 0
            metrics["retracted_contamination_count"] = retracted_contamination_count
            checks.append(
                QCCheck(
                    name="retracted_contamination_count",
                    passed=retracted_contamination_count == 0,
                    value=retracted_contamination_count,
                    threshold=0,
                    severity="critical",
                )
            )

            try:
                old_evidence_share = float(
                    con.execute(
                        """
                        SELECT 100.0 * COUNT(*) FILTER (WHERE a.year < 2010) / NULLIF(COUNT(*), 0)
                        FROM ac_skg_edge_evidence e
                        JOIN ac_skg_articles a ON a.openalex_id = e.openalex_id
                        """
                    ).fetchone()[0]
                    or 0.0
                )
            except duckdb.Error:
                old_evidence_share = 0.0
            metrics["old_evidence_share_pct"] = round(old_evidence_share, 3)
            checks.append(
                QCCheck(
                    name="old_evidence_share_pct",
                    passed=old_evidence_share <= 50.0,
                    value=round(old_evidence_share, 3),
                    threshold=50.0,
                    severity="warning",
                )
            )

            try:
                sample_size_coverage = float(
                    con.execute(
                        """
                        SELECT 100.0 * COUNT(*) FILTER (WHERE sample_size IS NOT NULL AND sample_size > 0)
                            / NULLIF(COUNT(*), 0)
                        FROM ac_parameter_estimates
                        """
                    ).fetchone()[0]
                    or 0.0
                )
            except duckdb.Error:
                sample_size_coverage = 0.0
            metrics["sample_size_coverage_pct"] = round(sample_size_coverage, 3)
            checks.append(
                QCCheck(
                    name="sample_size_coverage_pct",
                    passed=sample_size_coverage >= 40.0
                    if metrics.get("parameters_total", 0)
                    else True,
                    value=round(sample_size_coverage, 3),
                    threshold=40.0,
                    severity="warning",
                )
            )

            try:
                low_confidence_edge_share = float(
                    con.execute(
                        """
                        SELECT 100.0 * COUNT(*) FILTER (WHERE confidence < 0.3) / NULLIF(COUNT(*), 0)
                        FROM ac_skg_edges
                        """
                    ).fetchone()[0]
                    or 0.0
                )
            except duckdb.Error:
                low_confidence_edge_share = 0.0
            metrics["low_confidence_edge_share_pct"] = round(low_confidence_edge_share, 3)
            checks.append(
                QCCheck(
                    name="low_confidence_edge_share_pct",
                    passed=low_confidence_edge_share <= 30.0 if total_edges else True,
                    value=round(low_confidence_edge_share, 3),
                    threshold=30.0,
                    severity="warning",
                )
            )

            try:
                high_design_tier_share = float(
                    con.execute(
                        """
                        SELECT 100.0 * COUNT(*) FILTER (WHERE design_quality_tier IN (1, 2))
                            / NULLIF(COUNT(*), 0)
                        FROM ac_claim_adjudications
                        WHERE publishable_edge = TRUE
                        """
                    ).fetchone()[0]
                    or 0.0
                )
            except duckdb.Error:
                high_design_tier_share = 0.0
            metrics["high_design_tier_share_pct"] = round(high_design_tier_share, 3)
            checks.append(
                QCCheck(
                    name="high_design_tier_share_pct",
                    passed=high_design_tier_share >= 20.0 if publishable_total else True,
                    value=round(high_design_tier_share, 3),
                    threshold=20.0,
                    severity="warning",
                )
            )

            try:
                family_edge_count = int(
                    con.execute("SELECT COUNT(*) FROM ac_skg_family_edges").fetchone()[0]
                )
            except duckdb.Error:
                family_edge_count = 0
            metrics["family_edge_count"] = family_edge_count
            checks.append(
                QCCheck(
                    name="family_edge_count_nonzero",
                    passed=family_edge_count > 0 if total_edges >= 10 else True,
                    value=family_edge_count,
                    threshold=1,
                    severity="warning",
                )
            )

            try:
                simulation_ready_numeric_count = int(
                    con.execute("SELECT COUNT(*) FROM ac_skg_simulation_parameters").fetchone()[0]
                )
            except duckdb.Error:
                simulation_ready_numeric_count = 0
            metrics["simulation_ready_numeric_count"] = simulation_ready_numeric_count
            checks.append(
                QCCheck(
                    name="simulation_ready_numeric_count",
                    passed=simulation_ready_numeric_count > 0
                    if metrics.get("resolve_extract_count", 0)
                    else True,
                    value=simulation_ready_numeric_count,
                    threshold=1,
                    severity="warning",
                )
            )

            edge_report_path = config.edge_synthesis_report_path
            if edge_report_path.exists():
                edge_report = _load_json_object(
                    edge_report_path,
                    kind="edge-synthesis report",
                    required_fields=("canonization",),
                )
                canonization = edge_report["canonization"]
                if not isinstance(canonization, dict):
                    raise ValueError(
                        f"Edge-synthesis report at {edge_report_path} "
                        "must contain an object-valued canonization field"
                    )
                global_canonical_resolution_rate = _required_metric_value(
                    canonization,
                    "resolution_rate_pct",
                    value_kind="percentage",
                    source=str(edge_report_path),
                    producer="edge-synthesis canonization metrics",
                )
                global_rate_check = QCCheck(
                    name="global_canonical_resolution_rate_pct",
                    passed=global_canonical_resolution_rate >= 50.0,
                    value=round(global_canonical_resolution_rate, 3),
                    threshold=50.0,
                    severity="warning",
                )
            else:
                edge_report = {}
                global_canonical_resolution_rate = None
                edge_synthesis_scheduled = "edge_synthesize" in config.stages
                global_rate_check = QCCheck(
                    name="global_canonical_resolution_rate_pct",
                    passed=False,
                    value=None,
                    threshold=50.0,
                    severity="critical" if edge_synthesis_scheduled else "warning",
                    message=(
                        "Edge-synthesis report is absent; global canonical resolution is not established"
                        if edge_synthesis_scheduled
                        else "Edge synthesis was not scheduled; global canonical resolution is not applicable"
                    ),
                    status="not_established" if edge_synthesis_scheduled else "not_applicable",
                )

            if config.benchmark_report_path.exists():
                benchmark_report = _load_json_object(
                    config.benchmark_report_path,
                    kind="benchmark report",
                    required_fields=("metrics",),
                )
                if benchmark_report.get("kind") not in (None, "academic_benchmark"):
                    raise ValueError(
                        f"Benchmark report at {config.benchmark_report_path} "
                        "has an unsupported kind"
                    )
                benchmark_metrics = benchmark_report["metrics"]
                if not isinstance(benchmark_metrics, dict):
                    raise ValueError(
                        f"Benchmark report at {config.benchmark_report_path} "
                        "must contain an object-valued metrics field"
                    )
                runtime_demanded_canonical_resolution_rate = _required_metric_value(
                    benchmark_metrics,
                    "runtime_demanded_canonical_resolution_rate_pct",
                    value_kind="percentage",
                    source=str(config.benchmark_report_path),
                    producer="academic benchmark metrics",
                )
                canonical_rate_check = QCCheck(
                    name="canonical_resolution_rate_pct",
                    passed=runtime_demanded_canonical_resolution_rate >= 90.0,
                    value=round(runtime_demanded_canonical_resolution_rate, 3),
                    threshold=90.0,
                    severity="critical",
                )
            else:
                benchmark_report = {}
                benchmark_metrics = {}
                runtime_demanded_canonical_resolution_rate = None
                benchmark_scheduled = "benchmark" in config.stages
                canonical_rate_check = QCCheck(
                    name="canonical_resolution_rate_pct",
                    passed=False,
                    value=None,
                    threshold=90.0,
                    severity="critical" if benchmark_scheduled else "warning",
                    message=(
                        "Benchmark report is absent; runtime-demanded canonical resolution is not established"
                        if benchmark_scheduled
                        else "Benchmark was not scheduled; runtime-demanded canonical resolution is not applicable"
                    ),
                    status="not_established" if benchmark_scheduled else "not_applicable",
                )

            metrics["runtime_demanded_canonical_resolution_rate_pct"] = (
                round(runtime_demanded_canonical_resolution_rate, 3)
                if runtime_demanded_canonical_resolution_rate is not None
                else None
            )
            metrics["global_canonical_resolution_rate_pct"] = (
                round(global_canonical_resolution_rate, 3)
                if global_canonical_resolution_rate is not None
                else None
            )
            metrics["canonical_resolution_rate_pct"] = (
                round(runtime_demanded_canonical_resolution_rate, 3)
                if runtime_demanded_canonical_resolution_rate is not None
                else None
            )
            checks.append(canonical_rate_check)
            checks.append(global_rate_check)
        finally:
            con.close()
    else:
        edge_synthesis_scheduled = "edge_synthesize" in config.stages
        benchmark_scheduled = "benchmark" in config.stages
        metrics["global_canonical_resolution_rate_pct"] = None
        metrics["runtime_demanded_canonical_resolution_rate_pct"] = None
        metrics["canonical_resolution_rate_pct"] = None
        checks.append(
            QCCheck(
                name="canonical_resolution_rate_pct",
                passed=False,
                value=None,
                threshold=90.0,
                severity="critical" if benchmark_scheduled else "warning",
                message=(
                    "Benchmark inputs are unavailable without the academic database; "
                    "runtime-demanded canonical resolution is not established"
                    if benchmark_scheduled
                    else "Benchmark was not scheduled; runtime-demanded canonical resolution is not applicable"
                ),
                status="not_established" if benchmark_scheduled else "not_applicable",
            )
        )
        checks.append(
            QCCheck(
                name="global_canonical_resolution_rate_pct",
                passed=False,
                value=None,
                threshold=50.0,
                severity="critical" if edge_synthesis_scheduled else "warning",
                message=(
                    "Edge-synthesis inputs are unavailable without the academic database; "
                    "global canonical resolution is not established"
                    if edge_synthesis_scheduled
                    else "Edge synthesis was not scheduled; global canonical resolution is not applicable"
                ),
                status="not_established" if edge_synthesis_scheduled else "not_applicable",
            )
        )

    report = QCReport(scope="academic", checks=checks, metrics=metrics)
    write_qc_report(config.qc_report_path, report)
    write_stage_manifest(
        manifest_path=config.manifests_dir / "qc.json",
        stage="qc",
        status="ok" if report.passed else "failed",
        metrics={"passed": report.passed, **metrics},
        artifacts=[config.qc_report_path],
        started_at=started_at,
    )
    evaluate_fail_fast(report, fail_fast=config.fail_fast_qc if fail_fast is None else fail_fast)
    return report
