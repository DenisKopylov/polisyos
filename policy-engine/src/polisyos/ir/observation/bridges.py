"""Standard-bridge contracts for IR observation and policy data."""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from polisyos.ir.observation.contracts import ObservationPanel, ObservationRecord


class ObservationBridgeStandard(str, Enum):
    """External standards covered by the observation bridge layer."""

    SDMX = "sdmx"
    DDI = "ddi"
    FHIR = "fhir"
    CDISC = "cdisc"


class SdmxObservationBridge(BaseModel):
    """Map an IR observation record onto an SDMX-like series/observation payload."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    standard: ObservationBridgeStandard = ObservationBridgeStandard.SDMX
    dataset_id: str = Field(min_length=1)
    series_key: dict[str, str]
    observation_dimension: str
    value: float
    unit: str
    attributes: dict[str, str] = Field(default_factory=dict)


class DdiVariableBridge(BaseModel):
    """Expose DDI-friendly variable metadata derived from one observation contract."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    standard: ObservationBridgeStandard = ObservationBridgeStandard.DDI
    variable_name: str = Field(min_length=1)
    label: str = Field(min_length=1)
    representation_type: str = Field(min_length=1)
    universe_reference: str = Field(min_length=1)
    source_reference: str = Field(min_length=1)


class FhirQuantityBridge(BaseModel):
    """FHIR quantity payload for one observation value."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    value: float
    unit: str = Field(min_length=1)
    system: str = "http://unitsofmeasure.org"


class FhirObservationBridge(BaseModel):
    """FHIR Observation-shaped projection of an IR observation record."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    standard: ObservationBridgeStandard = ObservationBridgeStandard.FHIR
    resource_type: str = "Observation"
    identifier: str = Field(min_length=1)
    status: str = "final"
    code_system: str = Field(min_length=1)
    code: str = Field(min_length=1)
    subject_reference: str = Field(min_length=1)
    effective_start: str
    effective_end: str
    value_quantity: FhirQuantityBridge
    components: dict[str, str] = Field(default_factory=dict)


class CdiscDatasetBridge(BaseModel):
    """CDISC-friendly table mapping for an observation panel."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    standard: ObservationBridgeStandard = ObservationBridgeStandard.CDISC
    domain: str = Field(min_length=2, max_length=8)
    dataset_name: str = Field(min_length=1)
    variable_names: list[str] = Field(min_length=1)
    key_variables: list[str] = Field(min_length=1)
    row_count: int = Field(ge=0)
    notes: list[str] = Field(default_factory=list)


def bridge_observation_record_to_sdmx(
    record: ObservationRecord,
    *,
    dataset_id: str,
    concept_overrides: dict[str, str] | None = None,
) -> SdmxObservationBridge:
    """Project one observation record into an SDMX series/observation shape."""

    series_key = {
        "FAMILY": record.family.value,
        "SCOPE": record.entity_scope.value,
        "METRIC": concept_overrides.get(record.metric_id, record.metric_id)
        if concept_overrides
        else record.metric_id,
        "SOURCE": record.source_id,
    }
    if record.region_code:
        series_key["REGION"] = record.region_code
    if record.sector_id:
        series_key["SECTOR"] = record.sector_id
    return SdmxObservationBridge(
        dataset_id=dataset_id,
        series_key=series_key,
        observation_dimension=record.period_end.isoformat(),
        value=record.observed_value,
        unit=record.unit,
        attributes={
            "REGIME": record.regime_id,
            "SCHEMA_REGIME": record.schema_regime_id,
            "IDENTIFICATION_MODE": record.identification_mode.value,
        },
    )


def bridge_observation_record_to_ddi(
    record: ObservationRecord,
    *,
    variable_label: str | None = None,
) -> DdiVariableBridge:
    """Build a DDI variable descriptor from an observation record contract."""

    return DdiVariableBridge(
        variable_name=record.metric_id,
        label=variable_label or f"{record.family.value}:{record.metric_id}",
        representation_type="numeric",
        universe_reference=record.entity_scope.value,
        source_reference=f"{record.source_id}@{record.source_version}",
    )


def bridge_observation_record_to_fhir(
    record: ObservationRecord,
    *,
    code_system: str = "urn:polisyos:metric",
    subject_prefix: str = "ObservationSubject",
) -> FhirObservationBridge:
    """Project a record into a minimal FHIR Observation structure."""

    subject_id = (
        record.entity_id
        or record.cell_id
        or record.region_code
        or record.sector_id
        or "global"
    )
    return FhirObservationBridge(
        identifier=record.observation_id,
        code_system=code_system,
        code=record.metric_id,
        subject_reference=f"{subject_prefix}/{subject_id}",
        effective_start=record.period_start.isoformat(),
        effective_end=record.period_end.isoformat(),
        value_quantity=FhirQuantityBridge(value=record.observed_value, unit=record.unit),
        components={
            "family": record.family.value,
            "source": record.source_id,
            "identification_mode": record.identification_mode.value,
        },
    )


def bridge_observation_panel_to_cdisc(
    panel: ObservationPanel,
    *,
    domain: str = "QS",
) -> CdiscDatasetBridge:
    """Summarize an observation panel as a CDISC dataset bridge contract."""

    variable_names = sorted(
        {
            "OBSERVATION_ID",
            "FAMILY",
            "METRIC_ID",
            "OBSERVED_VALUE",
            "UNIT",
            "PERIOD_START",
            "PERIOD_END",
            "SOURCE_ID",
        }
    )
    key_variables = ["OBSERVATION_ID", "METRIC_ID", "PERIOD_END"]
    return CdiscDatasetBridge(
        domain=domain,
        dataset_name=f"{panel.family.value}_{panel.time_grain.value}",
        variable_names=variable_names,
        key_variables=key_variables,
        row_count=len(panel.records),
        notes=[
            "IR observation panels map cleanly to row-oriented CDISC exports "
            "when a stable domain is chosen.",
            "Entity locator fields remain optional because scope varies by family.",
        ],
    )


__all__ = [
    "CdiscDatasetBridge",
    "DdiVariableBridge",
    "FhirObservationBridge",
    "FhirQuantityBridge",
    "ObservationBridgeStandard",
    "SdmxObservationBridge",
    "bridge_observation_panel_to_cdisc",
    "bridge_observation_record_to_ddi",
    "bridge_observation_record_to_fhir",
    "bridge_observation_record_to_sdmx",
]
