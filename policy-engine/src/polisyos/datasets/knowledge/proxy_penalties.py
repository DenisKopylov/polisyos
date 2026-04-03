"""Config-backed proxy penalty registry."""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import yaml


@dataclass(frozen=True)
class ProxyPenaltyOverride:
    """Proxy penalty override public type."""
    country_codes: tuple[str, ...] = ()
    start_year: int | None = None
    end_year: int | None = None
    proxy_penalty: float = 0.0


@dataclass(frozen=True)
class ProxyMetricAlignmentSpec:
    """Proxy metric alignment spec data model."""
    metric_name: str
    canonical_var: str
    confidence: float
    proxy_penalty: float
    country_overrides: dict[str, float] = field(default_factory=dict)
    year_overrides: tuple[ProxyPenaltyOverride, ...] = ()


def default_proxy_metric_alignments_path() -> Path:
    """Default proxy metric alignments path helper."""
    return Path(__file__).resolve().parents[4] / "data" / "dataset_catalog" / "proxy_metric_alignments.yaml"


@lru_cache(maxsize=4)
def load_proxy_metric_alignments(path: Path | None = None) -> dict[str, tuple[ProxyMetricAlignmentSpec, ...]]:
    """Load proxy metric alignments."""
    resolved = (path or default_proxy_metric_alignments_path()).resolve()
    if not resolved.exists():
        return {}
    with open(resolved, "r", encoding="utf-8") as fh:
        payload = yaml.safe_load(fh) or {}
    raw_mappings = payload.get("mappings", {})
    if not isinstance(raw_mappings, dict):
        return {}
    result: dict[str, tuple[ProxyMetricAlignmentSpec, ...]] = {}
    for metric_name, entries in raw_mappings.items():
        if not isinstance(entries, list):
            continue
        specs: list[ProxyMetricAlignmentSpec] = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            year_overrides_raw = entry.get("year_overrides", [])
            year_overrides: list[ProxyPenaltyOverride] = []
            if isinstance(year_overrides_raw, list):
                for item in year_overrides_raw:
                    if not isinstance(item, dict):
                        continue
                    year_overrides.append(
                        ProxyPenaltyOverride(
                            country_codes=tuple(
                                str(code).strip().upper()
                                for code in item.get("country_codes", []) or []
                                if str(code).strip()
                            ),
                            start_year=int(item["start_year"]) if item.get("start_year") is not None else None,
                            end_year=int(item["end_year"]) if item.get("end_year") is not None else None,
                            proxy_penalty=float(item.get("proxy_penalty", 0.0) or 0.0),
                        )
                    )
            country_overrides_raw = entry.get("country_overrides", {})
            country_overrides = {}
            if isinstance(country_overrides_raw, dict):
                country_overrides = {
                    str(country).strip().upper(): float(value or 0.0)
                    for country, value in country_overrides_raw.items()
                    if str(country).strip()
                }
            specs.append(
                ProxyMetricAlignmentSpec(
                    metric_name=str(metric_name).strip(),
                    canonical_var=str(entry.get("canonical_var", "")).strip(),
                    confidence=float(entry.get("confidence", 0.0) or 0.0),
                    proxy_penalty=float(entry.get("proxy_penalty", 0.0) or 0.0),
                    country_overrides=country_overrides,
                    year_overrides=tuple(year_overrides),
                )
            )
        if specs:
            result[str(metric_name).strip()] = tuple(specs)
    return result


def metric_proxy_alignments(metric_name: str, path: Path | None = None) -> tuple[ProxyMetricAlignmentSpec, ...]:
    """Metric proxy alignments helper."""
    mappings = load_proxy_metric_alignments(path)
    return mappings.get(str(metric_name or "").strip(), ())


def resolve_proxy_penalty(
    *,
    metric_name: str | None,
    canonical_var: str,
    base_penalty: float,
    country_code: str | None = None,
    year: int | None = None,
    path: Path | None = None,
) -> float:
    """Resolve proxy penalty."""
    metric = str(metric_name or "").strip()
    if not metric:
        return float(base_penalty)
    country = str(country_code or "").strip().upper()
    for spec in metric_proxy_alignments(metric, path):
        if spec.canonical_var != canonical_var:
            continue
        if country and country in spec.country_overrides:
            return float(spec.country_overrides[country])
        if year is not None:
            for override in spec.year_overrides:
                if override.country_codes and country and country not in override.country_codes:
                    continue
                if override.start_year is not None and year < override.start_year:
                    continue
                if override.end_year is not None and year > override.end_year:
                    continue
                return float(override.proxy_penalty)
        return float(spec.proxy_penalty)
    return float(base_penalty)


def metric_name_from_alignment_evidence(evidence: str) -> str | None:
    """Metric name from alignment evidence helper."""
    marker = "metric_binding_proxy:"
    text = str(evidence or "")
    if marker not in text:
        return None
    tail = text.split(marker, 1)[1].strip()
    if not tail:
        return None
    return tail.split(";", 1)[0].strip() or None
