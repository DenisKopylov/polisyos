from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class PIISeverity(str, Enum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class PIIEntityType(str, Enum):
    PERSON = "PERSON"
    EMAIL_ADDRESS = "EMAIL_ADDRESS"
    PHONE_NUMBER = "PHONE_NUMBER"
    LOCATION = "LOCATION"
    DATE_OF_BIRTH = "DATE_OF_BIRTH"
    CREDIT_CARD = "CREDIT_CARD"
    IBAN_CODE = "IBAN_CODE"
    IP_ADDRESS = "IP_ADDRESS"
    NRP = "NRP"
    TAX_ID = "TAX_ID"
    BENEFICIARY_ID = "BENEFICIARY_ID"
    CASE_NUMBER = "CASE_NUMBER"
    NATIONAL_ID = "NATIONAL_ID"
    SOCIAL_SECURITY = "SOCIAL_SECURITY"


PII_SEVERITY_MAP: dict[PIIEntityType, PIISeverity] = {
    PIIEntityType.PERSON: PIISeverity.LOW,
    PIIEntityType.LOCATION: PIISeverity.LOW,
    PIIEntityType.EMAIL_ADDRESS: PIISeverity.MEDIUM,
    PIIEntityType.PHONE_NUMBER: PIISeverity.MEDIUM,
    PIIEntityType.IP_ADDRESS: PIISeverity.MEDIUM,
    PIIEntityType.DATE_OF_BIRTH: PIISeverity.HIGH,
    PIIEntityType.CREDIT_CARD: PIISeverity.HIGH,
    PIIEntityType.IBAN_CODE: PIISeverity.HIGH,
    PIIEntityType.NRP: PIISeverity.HIGH,
    PIIEntityType.CASE_NUMBER: PIISeverity.HIGH,
    PIIEntityType.TAX_ID: PIISeverity.CRITICAL,
    PIIEntityType.BENEFICIARY_ID: PIISeverity.CRITICAL,
    PIIEntityType.NATIONAL_ID: PIISeverity.CRITICAL,
    PIIEntityType.SOCIAL_SECURITY: PIISeverity.CRITICAL,
}


class PIIEntity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entity_type: PIIEntityType
    severity: PIISeverity
    score: float = Field(..., ge=0.0, le=1.0)
    column: str = ""
    start: int = Field(0, ge=0)
    end: int = Field(0, ge=0)
    redacted_text: str = "***"


class PIIScanResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_records_scanned: int = Field(0, ge=0)
    total_entities_found: int = Field(0, ge=0)
    max_severity: PIISeverity = PIISeverity.NONE
    entities_by_type: dict[str, int] = Field(default_factory=dict)
    entities_by_severity: dict[str, int] = Field(default_factory=dict)
    entities: list[PIIEntity] = Field(default_factory=list)
    scan_duration_ms: float = Field(0.0, ge=0.0)
    sampled: bool = False
    sample_rate: float = Field(1.0, ge=0.0, le=1.0)


_SEVERITY_ORDER: tuple[PIISeverity, ...] = (
    PIISeverity.NONE,
    PIISeverity.LOW,
    PIISeverity.MEDIUM,
    PIISeverity.HIGH,
    PIISeverity.CRITICAL,
)


def max_severity(left: PIISeverity, right: PIISeverity) -> PIISeverity:
    return left if _SEVERITY_ORDER.index(left) >= _SEVERITY_ORDER.index(right) else right


def severity_leq(left: str, right: str) -> bool:
    try:
        left_idx = _SEVERITY_ORDER.index(PIISeverity(left))
    except (ValueError, KeyError):
        left_idx = 0
    try:
        right_idx = _SEVERITY_ORDER.index(PIISeverity(right))
    except (ValueError, KeyError):
        right_idx = 0
    return left_idx <= right_idx
