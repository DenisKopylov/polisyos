"""Content-bound optional and historical source adapters for the Cycle Board."""

from __future__ import annotations

import json
import re
from hashlib import sha256
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    SerializerFunctionWrapHandler,
    model_serializer,
    model_validator,
)

from polisyos.common.markdown import split_markdown_table_row
from polisyos.runtime.http.services.cycle_board_contracts import (
    HistoricalDS4Disposition,
    HistoricalProducerAvailability,
    HistoricalProducerAvailabilityReadReceipt,
)

if TYPE_CHECKING:
    from typing import Self

N13B_DENIED_ROW_USES = (
    "per_row_movement",
    "row_enumeration",
    "exhaustiveness",
)
_N13B_SOURCE = Path(
    "architecture/policy_design_case/layer3_gy_n13b_acquisition_executor_contract.json"
)
_N13B_SCHEMA_VERSION = "policyos.layer3.gy.n13b.acquisition_executor_contract.v5"
_N13B_RULE_VERSION = "GY-plan-rev18+3.5.12-D1-D6"
_N13B_PRODUCER = (
    "tools.quality.validation.layer3_gy_n13b_acquisition_contract."
    "derive_n13b_acquisition_executor_contract"
)
_DS4_SOURCE = Path("docs/plans/active/atlas-slices/DS4-status-grammar-rebinding-closure.md")
_ATLAS_PLAN_SOURCE = Path("docs/plans/active/POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md")


class N13BGlobalMovementSignal(BaseModel):
    """Optional N13b control-plane evidence denied for every row-level use."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    availability: Literal["available", "artifact_missing", "invalid_source"]
    source_ref: str
    source_content_hash: str | None = None
    schema_version: str | None = None
    rule_version: str | None = None
    producer: str | None = None
    demonstration_status: str | None = None
    reason: str | None = None

    @model_validator(mode="after")
    def _available_identity_is_complete(self) -> Self:
        if self.availability == "available":
            if (
                self.schema_version != _N13B_SCHEMA_VERSION
                or self.rule_version != _N13B_RULE_VERSION
                or self.producer != _N13B_PRODUCER
                or not self.demonstration_status
                or self.source_content_hash is None
            ):
                raise ValueError("available N13b signal requires the admitted owner identity")
        elif self.demonstration_status is not None:
            raise ValueError("unavailable N13b signal cannot publish a demonstration status")
        return self

    @model_serializer(mode="wrap")
    def _omit_unavailable_values(
        self,
        handler: SerializerFunctionWrapHandler,
    ) -> dict[str, Any]:
        return {key: value for key, value in handler(self).items() if value is not None}


class HistoricalDispositionError(ValueError):
    """Reject incomplete or arithmetically inconsistent DS4 owner tables."""


class HistoricalProducerAvailabilityError(ValueError):
    """Refuse historical input while retaining the actual read and selector receipt."""

    def __init__(
        self, message: str, *, read_receipt: HistoricalProducerAvailabilityReadReceipt
    ) -> None:
        super().__init__(message)
        self.read_receipt = read_receipt


def _sha256(raw_bytes: bytes) -> str:
    return f"sha256:{sha256(raw_bytes).hexdigest()}"


def load_n13b_global_movement_signal(repository_root: Path) -> N13BGlobalMovementSignal:
    """Load optional N13b control-plane evidence and hash its exact bytes."""

    source_ref = _N13B_SOURCE.as_posix()
    try:
        raw_bytes = (repository_root / _N13B_SOURCE).read_bytes()
    except OSError as exc:
        return N13BGlobalMovementSignal(
            availability="artifact_missing",
            source_ref=source_ref,
            reason=f"N13b owner artifact is unavailable: {type(exc).__name__}",
        )
    content_hash = _sha256(raw_bytes)
    try:
        payload = json.loads(raw_bytes)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return N13BGlobalMovementSignal(
            availability="invalid_source",
            source_ref=source_ref,
            source_content_hash=content_hash,
            reason=f"N13b owner artifact is invalid JSON: {type(exc).__name__}",
        )
    if not isinstance(payload, dict):
        return N13BGlobalMovementSignal(
            availability="invalid_source",
            source_ref=source_ref,
            source_content_hash=content_hash,
            reason="N13b owner artifact must be a JSON object",
        )
    identity = (
        payload.get("schema_version"),
        payload.get("rule_version"),
        payload.get("producer"),
    )
    if identity != (_N13B_SCHEMA_VERSION, _N13B_RULE_VERSION, _N13B_PRODUCER):
        return N13BGlobalMovementSignal(
            availability="invalid_source",
            source_ref=source_ref,
            source_content_hash=content_hash,
            reason="N13b owner schema, rule, or producer identity is not admitted",
        )
    demonstration_status = payload.get("demonstration_status")
    if not isinstance(demonstration_status, str) or not demonstration_status:
        return N13BGlobalMovementSignal(
            availability="invalid_source",
            source_ref=source_ref,
            source_content_hash=content_hash,
            reason="N13b owner demonstration status is absent or invalid",
        )
    return N13BGlobalMovementSignal(
        availability="available",
        source_ref=source_ref,
        source_content_hash=content_hash,
        schema_version=_N13B_SCHEMA_VERSION,
        rule_version=_N13B_RULE_VERSION,
        producer=_N13B_PRODUCER,
        demonstration_status=demonstration_status,
    )


_DISPOSITION_KEYS = {
    "package": "package",
    "rebind": "rebind",
    "use-as-is": "use_as_is",
    "retire": "retire",
}


def _parse_disposition_counts(text: str) -> dict[str, int]:
    counts = dict.fromkeys(_DISPOSITION_KEYS.values(), 0)
    matches = re.findall(
        r"(\d+)\s+(?:consumer-missing\s+)?(package|rebind|use-as-is|retire)",
        text,
    )
    if not matches:
        raise HistoricalDispositionError("DS4 disposition row has no typed counts")
    for raw_count, raw_kind in matches:
        counts[_DISPOSITION_KEYS[raw_kind]] += int(raw_count)
    return counts


def parse_ds4_realized_disposition(
    source_text: str,
    *,
    source_ref: str,
) -> HistoricalDS4Disposition:
    """Derive DS4's component disposition from every owner table row."""

    rows: list[tuple[str, int, str]] = []
    total_count: int | None = None
    total_call: str | None = None
    for line in source_text.splitlines():
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) < 4 or cells[0] in {"Family", "---"}:
            continue
        if cells[0] == "**Total**":
            try:
                total_count = int(cells[1].strip("*"))
            except ValueError as exc:
                raise HistoricalDispositionError("DS4 total count is invalid") from exc
            total_call = cells[3].strip("*")
            continue
        if not re.fullmatch(r"\d+", cells[1]):
            continue
        rows.append((cells[0].strip("`"), int(cells[1]), cells[3]))
    if total_count is None or total_call is None or not rows:
        raise HistoricalDispositionError("DS4 realized disposition table is incomplete")
    family_names = [row[0] for row in rows]
    if len(family_names) != len(set(family_names)):
        raise HistoricalDispositionError("DS4 realized disposition families are duplicated")
    derived = dict.fromkeys(_DISPOSITION_KEYS.values(), 0)
    row_denominator = 0
    for family, count, final_call in rows:
        row_counts = _parse_disposition_counts(final_call)
        if sum(row_counts.values()) != count:
            raise HistoricalDispositionError(
                f"DS4 family {family} disposition does not reconcile to its count"
            )
        row_denominator += count
        for key, value in row_counts.items():
            derived[key] += value
    declared = _parse_disposition_counts(total_call.replace("/", " "))
    if row_denominator != total_count or derived != declared:
        raise HistoricalDispositionError("DS4 realized disposition total does not reconcile")
    return HistoricalDS4Disposition(
        source_ref=source_ref,
        source_content_hash=_sha256(source_text.encode("utf-8")),
        counts=derived,
        denominator=total_count,
    )


def load_ds4_realized_disposition(repository_root: Path) -> HistoricalDS4Disposition:
    """Read and reconcile the historical DS4 disposition owner record."""

    raw_bytes = (repository_root / _DS4_SOURCE).read_bytes()
    source_text = raw_bytes.decode("utf-8")
    return parse_ds4_realized_disposition(
        source_text,
        source_ref=_DS4_SOURCE.as_posix(),
    )


def load_historical_producer_availability(
    repository_root: Path,
) -> HistoricalProducerAvailability:
    """Parse the environment-relative DS3 denominator from its owner record."""

    source_ref = _ATLAS_PLAN_SOURCE.as_posix()
    receipt = HistoricalProducerAvailabilityReadReceipt(
        source_ref=source_ref,
        read_status="failed",
        status="UNRUN",
        coverage="partial",
        source_content_hash=None,
        read_error=None,
        table_row_denominator=None,
        selected_measurement_cell_count=None,
    )
    try:
        raw_bytes = (repository_root / _ATLAS_PLAN_SOURCE).read_bytes()
    except OSError as exc:
        raise HistoricalProducerAvailabilityError(
            "historical producer availability input is unreadable",
            read_receipt=receipt.model_copy(update={"read_error": type(exc).__name__}),
        ) from exc
    receipt = receipt.model_copy(
        update={
            "read_status": "read",
            "source_content_hash": _sha256(raw_bytes),
        }
    )
    try:
        source_text = raw_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HistoricalProducerAvailabilityError(
            "historical producer availability input is not UTF-8",
            read_receipt=receipt.model_copy(update={"read_error": type(exc).__name__}),
        ) from exc
    measured_cells = []
    table_rows = 0
    for line in source_text.splitlines():
        if not line.lstrip().startswith("|"):
            continue
        table_rows += 1
        cells = split_markdown_table_row(line)
        # Status and debt-title decoration cannot change a historical measurement.
        measured_cells.extend(
            cell.strip() for cell in cells if cell.strip().startswith("DS3 measured")
        )
    receipt = receipt.model_copy(
        update={
            "table_row_denominator": table_rows,
            "selected_measurement_cell_count": len(measured_cells),
            "status": "COMPLETE",
            "coverage": "complete_selected_input",
        }
    )
    if len(measured_cells) != 1:
        raise HistoricalProducerAvailabilityError(
            "historical producer availability owner row is absent or ambiguous",
            read_receipt=receipt,
        )
    match = re.fullmatch(
        r"DS3 measured (\d+) available / "
        r"(\d+) `invalid_source` / (\d+) `artifact_missing` from a worktree WITHOUT "
        r"`production_data`(?:\s+[—–-].*)?",
        measured_cells[0],
    )
    if match is None:
        raise HistoricalProducerAvailabilityError(
            "historical producer availability measurement is malformed", read_receipt=receipt
        )
    return HistoricalProducerAvailability(
        source_ref=_ATLAS_PLAN_SOURCE.as_posix(),
        source_content_hash=_sha256(raw_bytes),
        read_receipt=receipt,
        counts={
            "available": int(match.group(1)),
            "invalid_source": int(match.group(2)),
            "artifact_missing": int(match.group(3)),
        },
    )


__all__ = [
    "N13B_DENIED_ROW_USES",
    "HistoricalDispositionError",
    "N13BGlobalMovementSignal",
    "load_ds4_realized_disposition",
    "load_historical_producer_availability",
    "load_n13b_global_movement_signal",
    "parse_ds4_realized_disposition",
]
