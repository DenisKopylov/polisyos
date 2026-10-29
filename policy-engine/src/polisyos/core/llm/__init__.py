"""Exports LLM pricing, retry, tracing, and response-normalization helpers."""

from .cost import estimate_cost, estimate_cost_from_text, estimate_cost_from_tokens
from .protocols import LLMClientProtocol
from .response import LLMResponseData, extract_llm_response_data
from .response import _capture_usage_observation as capture_llm_usage_observation
from .response import _recorded_usage_payload as recorded_llm_usage_payload
from .response import _replay_usage_payload as replay_llm_usage_payload
from .response import _usage_quantity as parse_llm_usage_quantity
from .response import _UsageQuantity as LLMUsageQuantity
from .retry import retry_async
from .sanitization import (
    SECRET_AND_PII_SCAN_SCOPES,
    SECRET_PII_DETECTOR_VERSION,
    PromptSanitizer,
    SanitizationRule,
    SecretAndPIIScanReport,
    SecretPIIScanResult,
    scan_secret_and_pii,
)
from .traced_client import PreparedLLMInput, TracedLLMClient

__all__ = [
    "SECRET_AND_PII_SCAN_SCOPES",
    "SECRET_PII_DETECTOR_VERSION",
    "LLMClientProtocol",
    "LLMResponseData",
    "LLMUsageQuantity",
    "PreparedLLMInput",
    "PromptSanitizer",
    "SanitizationRule",
    "SecretAndPIIScanReport",
    "SecretPIIScanResult",
    "TracedLLMClient",
    "capture_llm_usage_observation",
    "estimate_cost",
    "estimate_cost_from_text",
    "estimate_cost_from_tokens",
    "extract_llm_response_data",
    "parse_llm_usage_quantity",
    "recorded_llm_usage_payload",
    "replay_llm_usage_payload",
    "retry_async",
    "scan_secret_and_pii",
]

# Exact owner routes added for the E02 deep-import migration.
from polisyos.core.llm.response import (
    normalize_llm_cost_evidence as normalize_llm_cost_evidence,
)
from polisyos.core.llm.settlement import (
    LLMProducerAdmissionGuard as LLMProducerAdmissionGuard,
)
from polisyos.core.llm.settlement import (
    LLMProducerEvent as LLMProducerEvent,
)
from polisyos.core.llm.settlement import (
    LLMProducerIntent as LLMProducerIntent,
)
from polisyos.core.llm.settlement import (
    LLMSettlementOwnershipError as LLMSettlementOwnershipError,
)

__all__.extend(
    [
        "LLMProducerAdmissionGuard",
        "LLMProducerEvent",
        "LLMProducerIntent",
        "LLMSettlementOwnershipError",
        "normalize_llm_cost_evidence",
    ]
)
