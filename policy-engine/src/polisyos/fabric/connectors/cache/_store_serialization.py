"""
FetchResult serialization / deserialization for the connector cache.

Strategy:
- DataFrames  -> Parquet (compact, preserves types)
- Dicts/Lists -> Canonical JSON (deterministic)
- Other       -> Pickle with HMAC (fallback, tamper-proof)

Wire format::

    [envelope_len: 4 bytes][envelope: canonical JSON][data: format-specific]

Pickle payloads are HMAC-SHA256 signed to prevent deserialization of
tampered data (mitigates RCE via crafted pickle in compromised cache).
"""

from __future__ import annotations

import hashlib
import hmac
import io
import logging
import os
import pickle
from typing import Any

import pandas as pd

from polisyos.core.canon.canon_json import from_canonical_bytes, to_canonical_bytes
from polisyos.fabric.connectors.base import FetchResult
from polisyos.ir.connectors import DataVersion, PIIScanSummary, QualityTier

from ._store_models import _canon_spec_allow_floats

_logger = logging.getLogger(__name__)

_PICKLE_HMAC_KEY: bytes = os.environ.get("POLISYOS_CACHE_HMAC_KEY", "").encode(
    "utf-8"
) or os.urandom(32)
_HMAC_TAG_LEN = 32  # SHA-256 digest length

__all__ = [
    "ResultSerializer",
]


class ResultSerializer:
    """
    Handles FetchResult serialization/deserialization.

    Strategy:
    - DataFrames -> Parquet (compact, preserves types)
    - Dicts/Lists -> Canonical JSON (deterministic)
    - Other -> Pickle (fallback)

    Format:
        [envelope_len: 4 bytes][envelope: canonical JSON][data: format-specific]
    """

    @staticmethod
    def serialize(result: FetchResult[Any]) -> tuple[bytes, str]:
        # Detect data type and serialize payload
        if isinstance(result.data, pd.DataFrame):
            buffer = io.BytesIO()
            result.data.to_parquet(buffer, compression="snappy")
            data_bytes = buffer.getvalue()
            data_media_type = "application/parquet"
        elif isinstance(result.data, (dict, list)):
            data_bytes = to_canonical_bytes(result.data, _canon_spec_allow_floats())
            data_media_type = "application/json"
        else:
            pickled = pickle.dumps(result.data)
            tag = hmac.new(_PICKLE_HMAC_KEY, pickled, hashlib.sha256).digest()
            data_bytes = tag + pickled
            data_media_type = "application/pickle"

        envelope = {
            "schema_id": result.schema_id,
            "schema_version": result.schema_version,
            "version": result.version.model_dump(mode="json"),
            "fetched_at": result.fetched_at,
            "source_updated_at": result.source_updated_at,
            "evidence_ref": result.evidence_ref.model_dump(mode="json")
            if result.evidence_ref
            else None,
            "completeness": result.completeness,
            "quality_tier": result.quality_tier.value,
            "quality_flags": list(result.quality_flags),
            "row_count": result.row_count,
            "data_media_type": data_media_type,
            "has_more": result.has_more,
            "next_page_token": result.next_page_token,
            "total_count": result.total_count,
            "fetch_duration_ms": result.fetch_duration_ms,
            "bytes_transferred": result.bytes_transferred,
            "resilience": result.resilience.model_dump(mode="json") if result.resilience else None,
            "pii_scan": result.pii_scan.model_dump(mode="json") if result.pii_scan else None,
        }

        envelope_bytes = to_canonical_bytes(envelope, _canon_spec_allow_floats())
        combined = len(envelope_bytes).to_bytes(4, "big") + envelope_bytes + data_bytes
        media_type = f"application/vnd.polisyos.cached-result+{data_media_type}"
        return combined, media_type

    @staticmethod
    def deserialize(data_bytes: bytes) -> FetchResult[Any]:
        envelope_len = int.from_bytes(data_bytes[:4], "big")
        envelope_bytes = data_bytes[4 : 4 + envelope_len]
        payload_bytes = data_bytes[4 + envelope_len :]

        envelope = from_canonical_bytes(envelope_bytes)
        data_media_type = envelope.get("data_media_type")

        if data_media_type == "application/parquet":
            data = pd.read_parquet(io.BytesIO(payload_bytes))
        elif data_media_type == "application/json":
            data = from_canonical_bytes(payload_bytes)
        else:
            if len(payload_bytes) < _HMAC_TAG_LEN:
                raise ValueError("Pickle cache entry too short (missing HMAC tag)")
            stored_tag = payload_bytes[:_HMAC_TAG_LEN]
            pickled = payload_bytes[_HMAC_TAG_LEN:]
            expected_tag = hmac.new(_PICKLE_HMAC_KEY, pickled, hashlib.sha256).digest()
            if not hmac.compare_digest(stored_tag, expected_tag):
                raise ValueError(
                    "Pickle cache HMAC verification failed — "
                    "entry may be tampered or from a different process"
                )
            data = pickle.loads(pickled)  # noqa: S301  — HMAC-verified above

        evidence_ref = envelope.get("evidence_ref")
        if evidence_ref is not None:
            try:
                from polisyos.core.contracts.fabric import EvidenceBundleRef

                evidence_ref = EvidenceBundleRef.model_validate(evidence_ref)
            except Exception:
                evidence_ref = None

        resilience_info = envelope.get("resilience")
        if resilience_info is not None:
            try:
                from polisyos.fabric.connectors.base import ResilienceInfo

                resilience_info = ResilienceInfo.model_validate(resilience_info)
            except Exception:
                resilience_info = None

        pii_scan = envelope.get("pii_scan")
        if pii_scan is not None:
            try:
                pii_scan = PIIScanSummary.model_validate(pii_scan)
            except Exception:
                pii_scan = None

        return FetchResult(
            data=data,
            row_count=envelope["row_count"],
            schema_id=envelope["schema_id"],
            schema_version=envelope["schema_version"],
            version=DataVersion(**envelope["version"]),
            fetched_at=envelope["fetched_at"],
            source_updated_at=envelope.get("source_updated_at"),
            evidence_ref=evidence_ref,
            completeness=envelope["completeness"],
            quality_tier=QualityTier(envelope.get("quality_tier", QualityTier.UNVERIFIED)),
            quality_flags=frozenset(envelope.get("quality_flags", [])),
            has_more=envelope.get("has_more", False),
            next_page_token=envelope.get("next_page_token"),
            total_count=envelope.get("total_count"),
            fetch_duration_ms=envelope.get("fetch_duration_ms", 0.0),
            bytes_transferred=envelope.get("bytes_transferred", 0),
            resilience=resilience_info,
            pii_scan=pii_scan,
        )
