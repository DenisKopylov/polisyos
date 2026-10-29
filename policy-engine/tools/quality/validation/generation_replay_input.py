"""Strict versioned candidate replay input; no historical billing or reuse authority."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, model_validator

from polisyos.core.llm import replay_llm_usage_payload
from polisyos.core.llm.response import _usage_quantity
from polisyos.pdc import gy_content_hash
from polisyos.runtime.quality._n4_usage_capture import CallUsageEvidenceV2
from polisyos.runtime.quality.design_generation import LLMGenerationCall


class ReplayCaptureV3(BaseModel):
    """One new capture with unchanged call rows and separate exact usage facts.

    The file is a candidate software-test input. Its journal/event consistency is
    not a signature proving execution or historical provider spend; source/runtime
    qualification and accessible deciding bytes remain separate evidence.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal["policyos.testing.design_generation_replay_input.v3"] = (
        "policyos.testing.design_generation_replay_input.v3"
    )
    authority_scope: Literal["candidate_software_replay_not_billing_authority"] = (
        "candidate_software_replay_not_billing_authority"
    )
    metadata: dict[str, Any]
    source_calls: tuple[LLMGenerationCall, ...]
    call_usage: tuple[CallUsageEvidenceV2, ...]
    content_hash: str

    @model_validator(mode="after")
    def _complete_content_and_call_joins(self) -> Self:
        if self.content_hash != gy_content_hash(
            self.model_dump(mode="json", exclude={"content_hash"})
        ):
            raise ValueError("replay_capture_content_mismatch")
        if not self.source_calls:
            raise ValueError("replay_capture_calls_missing")
        if type(self.metadata.get("model_id")) is not str or not self.metadata["model_id"]:
            raise ValueError("replay_capture_metadata_model_missing")
        if any(call.model_id != self.metadata["model_id"] for call in self.source_calls):
            raise ValueError("replay_capture_metadata_model_mismatch")
        if len(self.source_calls) != len(self.call_usage):
            raise ValueError("replay_capture_usage_denominator_mismatch")
        if [call.call_index for call in self.source_calls] != list(range(len(self.source_calls))):
            raise ValueError("replay_capture_call_order_or_occurrence_mismatch")
        for call, row in zip(self.source_calls, self.call_usage, strict=True):
            if row.observation.usage_source == "response_payload":
                quantity = _usage_quantity(
                    row.observation.provider_usage,
                    row.observation.provider_top_usage,
                    nested_usage_present=row.observation.provider_usage_present,
                )
                actual = (call.prompt_tokens, call.completion_tokens, call.total_tokens)
                expected = (
                    quantity.prompt_tokens or 0,
                    quantity.completion_tokens or 0,
                    quantity.total_tokens
                    or ((quantity.prompt_tokens or 0) + (quantity.completion_tokens or 0)),
                )
                if actual != expected:
                    raise ValueError("replay_capture_raw_normalized_quantity_mismatch")
            if row.producer_context is not None:
                if row.producer_context["stage"] != call.role_hint:
                    raise ValueError("replay_capture_source_stage_mismatch")
                if row.producer_context["subject_ref"] != self.metadata.get("problem_content_ref"):
                    raise ValueError("replay_capture_source_problem_mismatch")
            if (
                row.call_index != call.call_index
                or row.call_content_hash != gy_content_hash(call.model_dump(mode="json"))
                or row.prompt_hash != call.prompt_hash
                or row.model_id != call.model_id
                or row.response_content_hash != gy_content_hash(call.raw_llm_response)
                or row.response_utf8_sha256
                != hashlib.sha256(call.raw_llm_response.encode()).hexdigest()
            ):
                raise ValueError("replay_capture_call_usage_binding_mismatch")
        return self

    def recording(self) -> dict[str, Any]:
        """Derive the legacy client view in memory; never store a second payload copy."""
        responses = [
            response_from_call_payload(call.model_dump(mode="json")) for call in self.source_calls
        ]
        result = {
            **self.metadata,
            "recording_id": "candidate_capture_v3_"
            + self.content_hash.removeprefix("sha256:")[:20],
            "recording_source": "versioned_candidate_capture_input_not_historical_spend",
            "response": responses[0],
            "responses": responses,
        }
        result["recording_content_hash"] = gy_content_hash(result)
        return result

    def usage_for(self, index: int) -> dict[str, Any]:
        """Preserve quantity presence; never reinterpret reuse as fresh provider usage."""
        row = self.call_usage[index]
        observation = row.observation
        settlement = observation.settlement
        unqualified = (
            observation.usage_source != "response_payload"
            or observation.source_was_reuse
            or observation.source_cost_origin in {"reuse", "unknown"}
            or settlement is None
            or settlement.ack_status != "committed"
            or settlement.response_utf8_sha256 != row.response_utf8_sha256
        )
        return replay_llm_usage_payload(
            observation.provider_usage,
            observation.provider_top_usage,
            nested_usage_present=observation.provider_usage_present,
            unknown_provenance=unqualified,
        )


def build_replay_capture(
    *,
    metadata: Mapping[str, Any],
    calls: Sequence[Mapping[str, Any]],
    evidence: Sequence[CallUsageEvidenceV2],
) -> ReplayCaptureV3:
    """Build one versioned input from the actual capture scope, never old counters."""
    body = {
        "schema_version": "policyos.testing.design_generation_replay_input.v3",
        "authority_scope": "candidate_software_replay_not_billing_authority",
        "metadata": dict(metadata),
        "source_calls": [dict(call) for call in calls],
        "call_usage": [row.model_dump(mode="json") for row in evidence],
    }
    return ReplayCaptureV3.model_validate({**body, "content_hash": gy_content_hash(body)})


def read_replay_capture(path: Path) -> ReplayCaptureV3:
    """Read only the exact new schema; unknown versions never fall back to legacy."""
    return ReplayCaptureV3.model_validate_json(path.read_bytes())


def response_from_call_payload(call: Mapping[str, Any]) -> dict[str, Any]:
    """Project unchanged call fields; availability lives only in the v2 sidecar."""
    raw = str(call.get("raw_llm_response") or "")
    index = int(call.get("call_index") or 0)
    return {
        "call_index": index,
        "role": call.get("role_hint") or f"llm_call_{index}",
        "role_hint": call.get("role_hint"),
        "status": call.get("status") or "success",
        "model_id": call.get("model_id"),
        "provider": call.get("provider"),
        "prompt_hash": call.get("prompt_hash"),
        "raw_response": raw,
        "raw_llm_response": raw,
        "raw_response_hash": gy_content_hash(raw),
        "parsed": call.get("parsed_json"),
        "response_format": call.get("response_format"),
        "usage": {
            name: call[name]
            for name in ("prompt_tokens", "completion_tokens", "total_tokens")
            if name in call
        },
        "wall_seconds": float(call.get("wall_seconds") or 0.0),
        "error": {
            "type": call.get("error_type"),
            "message": call.get("error_message"),
            "status": call.get("error_status"),
            "code": call.get("error_code"),
            "retry_after_s": call.get("retry_after_s"),
            "request_id": call.get("request_id"),
        },
        "cache": {"status": call.get("cache_status"), "key": call.get("cache_key")},
    }
