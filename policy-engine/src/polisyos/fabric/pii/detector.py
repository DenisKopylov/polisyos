from __future__ import annotations

import logging
import re
import time
from collections import OrderedDict
from typing import Any

import pandas as pd
from pydantic import BaseModel, Field

from polisyos.core.canon import content_hash as canon_content_hash

from .models import (
    PIIEntity,
    PIIEntityType,
    PIIScanResult,
    PIISeverity,
    PII_SEVERITY_MAP,
    max_severity,
)

logger = logging.getLogger(__name__)

_HIGH_RISK_NAME_PATTERNS = (
    "id",
    "identifier",
    "tax",
    "tin",
    "vat",
    "beneficiary",
    "case",
    "passport",
    "ssn",
    "email",
    "phone",
)

_REGEX_RULES: tuple[tuple[PIIEntityType, re.Pattern[str], float], ...] = (
    (PIIEntityType.EMAIL_ADDRESS, re.compile(r"\b[\w.%+-]+@[\w.-]+\.[A-Za-z]{2,}\b"), 0.95),
    (PIIEntityType.PHONE_NUMBER, re.compile(r"\b(?:\+\d{1,3}[ -]?)?(?:\(?\d{2,4}\)?[ -]?)?\d{3}[ -]?\d{4}\b"), 0.85),
    (PIIEntityType.SOCIAL_SECURITY, re.compile(r"\b(?!000|666|9\d{2})\d{3}-(?!00)\d{2}-(?!0000)\d{4}\b"), 0.95),
    (PIIEntityType.TAX_ID, re.compile(r"\b\d{2}-\d{7}\b"), 0.92),
    (PIIEntityType.BENEFICIARY_ID, re.compile(r"\b(?:BEN|BENF|BNFCRY)[_-]?\d{5,12}\b", re.IGNORECASE), 0.9),
    (PIIEntityType.CASE_NUMBER, re.compile(r"\b(?:CASE|CS|REF)[_-]?\d{4,12}\b", re.IGNORECASE), 0.88),
    (PIIEntityType.NATIONAL_ID, re.compile(r"\b[A-Z0-9]{6,15}\b"), 0.6),
    (PIIEntityType.CREDIT_CARD, re.compile(r"\b(?:\d[ -]*?){13,16}\b"), 0.8),
    (PIIEntityType.IBAN_CODE, re.compile(r"\b[A-Z]{2}[0-9A-Z]{13,32}\b"), 0.8),
    (PIIEntityType.IP_ADDRESS, re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"), 0.9),
)


class PresidioConfig(BaseModel):
    languages: list[str] = Field(default_factory=lambda: ["en"])
    score_threshold: float = 0.7
    max_text_length: int = 100_000
    batch_size: int = 500
    custom_recognizers_enabled: bool = True
    entity_types: list[str] = Field(default_factory=list)
    sample_rate: float = 1.0
    sample_min_rows: int = 50_000
    max_cached_results: int = 512


class PresidioDetector:
    """PII detector with Presidio primary backend and regex fallback."""

    def __init__(self, config: PresidioConfig | None = None) -> None:
        self._config = config or PresidioConfig()
        self._analyzer: Any | None = None
        self._presidio_available = False
        self._cache: OrderedDict[str, PIIScanResult] = OrderedDict()
        self._build_analyzer()

    def _build_analyzer(self) -> None:
        try:
            from presidio_analyzer import AnalyzerEngine, Pattern, PatternRecognizer
        except Exception:
            logger.warning("Presidio is unavailable, using regex fallback detector")
            self._presidio_available = False
            return

        analyzer = AnalyzerEngine()
        if self._config.custom_recognizers_enabled:
            analyzer.registry.add_recognizer(
                PatternRecognizer(
                    supported_entity="TAX_ID",
                    name="PolicyOS Tax ID",
                    patterns=[
                        Pattern(name="us_ein", regex=r"\b\d{2}-\d{7}\b", score=0.9),
                        Pattern(name="generic_tax", regex=r"\b(?:tax[_\s]?id|tin|vat)[:\s]*[\w\d-]{6,20}\b", score=0.75),
                    ],
                    supported_language="en",
                )
            )
            analyzer.registry.add_recognizer(
                PatternRecognizer(
                    supported_entity="BENEFICIARY_ID",
                    name="PolicyOS Beneficiary ID",
                    patterns=[
                        Pattern(name="beneficiary_prefix", regex=r"\b(?:BEN|BENF|BNFCRY)[_-]?\d{5,12}\b", score=0.9),
                        Pattern(name="beneficiary_generic", regex=r"\bbeneficiary[_\s]?(?:id|number|no)[:\s]*[\w\d-]{4,20}\b", score=0.75),
                    ],
                    supported_language="en",
                )
            )
            analyzer.registry.add_recognizer(
                PatternRecognizer(
                    supported_entity="CASE_NUMBER",
                    name="PolicyOS Case Number",
                    patterns=[
                        Pattern(name="case_prefix", regex=r"\b(?:CASE|CS|REF)[_-]?\d{4,12}\b", score=0.88),
                        Pattern(name="case_generic", regex=r"\bcase[_\s]?(?:number|no|id|ref)[:\s]*[\w\d/-]{4,20}\b", score=0.72),
                    ],
                    supported_language="en",
                )
            )
            analyzer.registry.add_recognizer(
                PatternRecognizer(
                    supported_entity="NATIONAL_ID",
                    name="PolicyOS National ID",
                    patterns=[
                        Pattern(name="national_generic", regex=r"\b(?:national[_\s]?id|passport[_\s]?(?:no|number))[:\s]*[\w\d-]{6,20}\b", score=0.82),
                    ],
                    supported_language="en",
                )
            )
            analyzer.registry.add_recognizer(
                PatternRecognizer(
                    supported_entity="SOCIAL_SECURITY",
                    name="PolicyOS Social Security",
                    patterns=[
                        Pattern(name="ssn_dashed", regex=r"\b(?!000|666|9\d{2})\d{3}-(?!00)\d{2}-(?!0000)\d{4}\b", score=0.95),
                    ],
                    supported_language="en",
                )
            )

        self._analyzer = analyzer
        self._presidio_available = True

    def scan_dataframe(
        self,
        df: pd.DataFrame,
        *,
        text_columns: list[str] | None = None,
        content_hash: str | None = None,
    ) -> PIIScanResult:
        started = time.perf_counter()
        if df.empty:
            return PIIScanResult(
                total_records_scanned=0,
                total_entities_found=0,
                max_severity=PIISeverity.NONE,
                scan_duration_ms=(time.perf_counter() - started) * 1000,
            )

        columns = text_columns or self._auto_columns(df)
        cache_key = self._cache_key(content_hash=content_hash, columns=columns)
        if cache_key and cache_key in self._cache:
            cached = self._cache[cache_key]
            return cached.model_copy(
                update={
                    "scan_duration_ms": (time.perf_counter() - started) * 1000,
                }
            )

        sample_df = df
        sampled = False
        sample_rate = self._config.sample_rate
        if len(df) >= self._config.sample_min_rows and 0.0 < sample_rate < 1.0:
            sample_size = max(1, int(len(df) * sample_rate))
            sample_df = df.sample(n=sample_size, random_state=42)
            sampled = True

        entities: list[PIIEntity] = []
        for column in columns:
            if column not in sample_df.columns:
                continue

            series = sample_df[column]
            values = series.dropna().astype(str)
            for text in values:
                if not text:
                    continue
                if len(text) > self._config.max_text_length:
                    text = text[: self._config.max_text_length]

                if self._presidio_available and self._analyzer is not None:
                    entities.extend(self._scan_text_presidio(text, column=column))
                else:
                    entities.extend(self._scan_text_regex(text, column=column))

        result = self._aggregate(
            entities=entities,
            total_records_scanned=len(sample_df),
            sampled=sampled,
            sample_rate=sample_rate,
            elapsed_ms=(time.perf_counter() - started) * 1000,
        )

        if cache_key:
            self._cache[cache_key] = result
            self._cache.move_to_end(cache_key)
            while len(self._cache) > self._config.max_cached_results:
                self._cache.popitem(last=False)

        return result

    def scan_text(self, text: str) -> list[PIIEntity]:
        df = pd.DataFrame({"text": [text]})
        return self.scan_dataframe(df, text_columns=["text"]).entities

    def _scan_text_presidio(self, text: str, *, column: str) -> list[PIIEntity]:
        entities: list[PIIEntity] = []
        try:
            results = self._analyzer.analyze(  # type: ignore[union-attr]
                text=text,
                entities=self._config.entity_types or None,
                language=self._config.languages[0],
                score_threshold=self._config.score_threshold,
            )
        except Exception as exc:
            logger.warning("Presidio analyze failed: %s", exc)
            return entities

        for hit in results:
            try:
                entity_type = PIIEntityType(hit.entity_type)
            except Exception:
                entity_type = PIIEntityType.NRP
            severity = PII_SEVERITY_MAP.get(entity_type, PIISeverity.MEDIUM)
            entities.append(
                PIIEntity(
                    entity_type=entity_type,
                    severity=severity,
                    score=float(hit.score),
                    column=column,
                    start=int(hit.start),
                    end=int(hit.end),
                    redacted_text="***",
                )
            )
        return entities

    def _scan_text_regex(self, text: str, *, column: str) -> list[PIIEntity]:
        entities: list[PIIEntity] = []
        for entity_type, pattern, score in _REGEX_RULES:
            if score < self._config.score_threshold:
                continue
            for match in pattern.finditer(text):
                entities.append(
                    PIIEntity(
                        entity_type=entity_type,
                        severity=PII_SEVERITY_MAP.get(entity_type, PIISeverity.MEDIUM),
                        score=score,
                        column=column,
                        start=match.start(),
                        end=match.end(),
                        redacted_text="***",
                    )
                )
        return entities

    def _auto_columns(self, df: pd.DataFrame) -> list[str]:
        chosen: list[str] = []
        for column in df.columns:
            series = df[column]
            name = str(column).lower()
            is_risky_name = any(token in name for token in _HIGH_RISK_NAME_PATTERNS)
            if pd.api.types.is_string_dtype(series) or series.dtype == "object":
                chosen.append(str(column))
            elif is_risky_name and (pd.api.types.is_integer_dtype(series) or pd.api.types.is_float_dtype(series)):
                chosen.append(str(column))
        return chosen

    def _cache_key(self, *, content_hash: str | None, columns: list[str]) -> str | None:
        if not content_hash:
            return None
        key_payload = {
            "content_hash": content_hash,
            "threshold": self._config.score_threshold,
            "entity_types": sorted(self._config.entity_types),
            "columns": sorted(columns),
            "sample_rate": self._config.sample_rate,
        }
        raw = repr(key_payload).encode("utf-8")
        return canon_content_hash(raw)

    def _aggregate(
        self,
        *,
        entities: list[PIIEntity],
        total_records_scanned: int,
        sampled: bool,
        sample_rate: float,
        elapsed_ms: float,
    ) -> PIIScanResult:
        by_type: dict[str, int] = {}
        by_severity: dict[str, int] = {}
        max_level = PIISeverity.NONE

        for entity in entities:
            by_type[entity.entity_type.value] = by_type.get(entity.entity_type.value, 0) + 1
            by_severity[entity.severity.value] = by_severity.get(entity.severity.value, 0) + 1
            max_level = max_severity(max_level, entity.severity)

        return PIIScanResult(
            total_records_scanned=total_records_scanned,
            total_entities_found=len(entities),
            max_severity=max_level,
            entities_by_type=by_type,
            entities_by_severity=by_severity,
            entities=entities,
            scan_duration_ms=max(elapsed_ms, 0.0),
            sampled=sampled,
            sample_rate=sample_rate,
        )
