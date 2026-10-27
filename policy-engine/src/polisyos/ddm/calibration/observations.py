"""Source-bound finite observation replay for the DDM calibration checker.

This owner enumerates a configured finite software source. It does not certify
production feed delivery, institutional authority, or world completeness.
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from polisyos.ddm.contracts.events import (
    DataQualitySignal,
    PerformanceDegradationEvent,
    ShiftRiskEvent,
)
from polisyos.ddm.contracts.metric_budget import MetricBudgetPolicy

if TYPE_CHECKING:
    from pathlib import Path


class CalibrationInvalidationObservation(BaseModel):
    """One observed trigger in a selected finite source window."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    event_id: str = Field(min_length=1)
    timestamp: AwareDatetime
    trigger: str = Field(min_length=1)


class CalibrationObservationWindow(BaseModel):
    """Complete enumerable contents of one explicitly bounded replay source."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal["polisyos.ddm.finite_observation_window.v1"]
    source_id: str = Field(min_length=1)
    profile: Literal["finite_replay"]
    model_id: str = Field(min_length=1)
    model_version: str = Field(min_length=1)
    calibration_id: str = Field(min_length=1)
    detector_id: str = Field(min_length=1)
    stationarity_regime_id: str = Field(min_length=1)
    report_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    observed_from: AwareDatetime
    observed_through: AwareDatetime
    invalidation_events: tuple[CalibrationInvalidationObservation, ...]
    shift_events: tuple[ShiftRiskEvent, ...]
    degradation_event: PerformanceDegradationEvent | None
    metric_budget: MetricBudgetPolicy
    data_quality_signals: tuple[DataQualitySignal, ...]
    critical_slice_budget_used: float | None

    @model_validator(mode="after")
    def _check_finite_window(self) -> CalibrationObservationWindow:
        if self.observed_from > self.observed_through:
            raise ValueError("observation window is reversed")
        seen: set[str] = set()
        for event in self.invalidation_events:
            if event.event_id in seen:
                raise ValueError("duplicate invalidation event identity")
            seen.add(event.event_id)
            if not self.observed_from <= event.timestamp <= self.observed_through:
                raise ValueError("invalidation event outside selected window")
        # This finite profile is a closed snapshot, not a temporal policy for
        # production feeds. Older event time may be carried as a late fact; a
        # future event is not yet available at the selected checkpoint.
        events = [*self.shift_events, *self.data_quality_signals]
        if self.degradation_event is not None:
            events.append(self.degradation_event)
        if any(event.timestamp > self.observed_through for event in events):
            raise ValueError("future event is outside the finite snapshot checkpoint")
        return self


class CalibrationObservationBinding(BaseModel):
    """Non-authoritative projection of the exact finite source read."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    source_id: str
    profile: Literal["finite_replay"]
    payload_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    observed_from: AwareDatetime
    observed_through: AwareDatetime
    completeness_provenance: Literal["recomputed"] = "recomputed"
    authority_scope: Literal["finite_replay_only"] = "finite_replay_only"


@dataclass(frozen=True)
class _ResolvedCalibrationObservations:
    """Private result of enumerating a configured finite source, never a grant."""

    payload_json: str
    source_path: Path
    source_bytes_sha256: str
    binding: CalibrationObservationBinding

    def is_current(self) -> bool:
        """Detect changed/unavailable selected bytes before any consumer decision."""

        try:
            return (
                hashlib.sha256(_read_selected_file(self.source_path)).hexdigest()
                == self.source_bytes_sha256
            )
        except (OSError, ValueError):
            return False

    def window(self) -> CalibrationObservationWindow:
        """Return a detached value; no mutable source object becomes evidence."""

        return CalibrationObservationWindow.model_validate_json(self.payload_json)


class FiniteCalibrationObservationSource:
    """Resolve one configured replay source, independently of consumer lists.

    An application chooses this source out of band. A registry payload never
    supplies its locator. Every resolve reopens and validates all source bytes.
    The finite source proves a bounded software predicate only; production
    promotion remains unavailable until a legitimate observation owner exists.
    """

    def __init__(self, *, path: Path, source_id: str) -> None:
        self._path = path
        self._source_id = source_id

    def _resolve(
        self,
        *,
        model_id: str | None,
        model_version: str | None,
        calibration_id: str,
        detector_id: str,
        stationarity_regime_id: str,
        report_digest: str,
        effective_at: AwareDatetime,
    ) -> _ResolvedCalibrationObservations:
        data = _read_selected_file(self._path)
        payload = json.loads(data, object_pairs_hook=_unique_object)
        window = CalibrationObservationWindow.model_validate(payload)
        expected = (
            model_id,
            model_version,
            calibration_id,
            detector_id,
            stationarity_regime_id,
            report_digest,
        )
        actual = (
            window.model_id,
            window.model_version,
            window.calibration_id,
            window.detector_id,
            window.stationarity_regime_id,
            window.report_digest,
        )
        if window.source_id != self._source_id or expected != actual:
            raise ValueError("observation source context mismatch")
        if effective_at != window.observed_through:
            raise ValueError("finite replay requires its exact closed snapshot checkpoint")
        normalized = window.model_dump_json()
        return _ResolvedCalibrationObservations(
            payload_json=normalized,
            source_path=self._path,
            source_bytes_sha256=hashlib.sha256(data).hexdigest(),
            binding=CalibrationObservationBinding(
                source_id=window.source_id,
                profile=window.profile,
                payload_sha256=hashlib.sha256(normalized.encode()).hexdigest(),
                observed_from=window.observed_from,
                observed_through=window.observed_through,
            ),
        )


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate observation source key")
        result[key] = value
    return result


def _read_selected_file(path: Path) -> bytes:
    """Read one bounded regular file; never block on a FIFO/device source."""

    if path.is_symlink():
        raise ValueError("observation source must be a regular selected file")
    flags = os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    with os.fdopen(descriptor, "rb") as handle:
        if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
            raise ValueError("observation source must be a regular selected file")
        data = handle.read(1_048_577)
    if len(data) > 1_048_576:
        raise ValueError("finite observation source exceeds replay profile limit")
    return data
