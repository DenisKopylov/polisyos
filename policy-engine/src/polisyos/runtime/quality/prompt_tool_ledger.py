"""Prompt, tool, and parser authority ledger for model-assisted runtime steps."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

from polisyos.core.artifacts.manifest import ArtifactRef, InputRef, SchemaInfo
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.core.canon.canon_json import CanonSpec

SCHEMA_VERSION = "policyos.prompt_tool_parser_authority_ledger.v1"
PROMPT_TOOL_LEDGER_KIND = "runtime.prompt_tool_parser_authority_ledger"
PROMPT_TOOL_LEDGER_SCHEMA = "polisyos.runtime.PromptToolParserAuthorityLedger"
PROMPT_TOOL_LEDGER_REPORT_KEY = "prompt_tool_ledger"
PROMPT_TOOL_LEDGER_REF_KEY = "prompt_tool_ledger_ref"
PROMPT_TOOL_LEDGER_FILENAME = "prompt_tool_ledger.json"

AuthorityScope = Literal["evidence", "claims", "scorecard", "approval"]
ValidationStatus = Literal["pass", "fail", "warn", "blocked", "not_applicable"]
RepairDecisionStatus = Literal["applied", "rejected", "not_applicable"]
ToolCallStatus = Literal["pass", "fail", "blocked", "skipped"]

AUTHORITY_SCOPES: tuple[AuthorityScope, ...] = (
    "evidence",
    "claims",
    "scorecard",
    "approval",
)
_PASS_STATUSES = {"pass", "not_applicable"}


class PromptToolLedgerError(ValueError):
    """Typed prompt/tool/parser authority invariant violation."""

    def __init__(self, code: str, message: str | None = None) -> None:
        self.code = code
        super().__init__(message or code)


class PromptTemplateRecord(BaseModel):
    """Prompt/template identity and rendered input authority."""

    model_config = ConfigDict(extra="forbid")

    template_id: str = Field(min_length=1)
    template_version: str = Field(min_length=1)
    template_ref: str | None = None
    rendered_prompt_ref: str | None = None
    rendered_input_refs: tuple[str, ...] = Field(default=())
    template_variables_fingerprint: str | None = None
    prompt_fingerprint: str | None = None

    @field_validator(
        "template_id",
        "template_version",
        "template_ref",
        "rendered_prompt_ref",
        "template_variables_fingerprint",
        "prompt_fingerprint",
    )
    @classmethod
    def _clean_text_field(cls, value: str | None) -> str | None:
        return _optional_text(value)

    @field_validator("rendered_input_refs")
    @classmethod
    def _clean_refs(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return _clean_ref_tuple(values)

    @model_validator(mode="after")
    def _fill_prompt_fingerprint(self) -> PromptTemplateRecord:
        if self.prompt_fingerprint is None:
            self.prompt_fingerprint = _fingerprint(
                {
                    "template_id": self.template_id,
                    "template_version": self.template_version,
                    "template_ref": self.template_ref,
                    "rendered_prompt_ref": self.rendered_prompt_ref,
                    "rendered_input_refs": list(self.rendered_input_refs),
                    "template_variables_fingerprint": self.template_variables_fingerprint,
                }
            )
        return self


class ModelProviderConfig(BaseModel):
    """Provider/model execution configuration for one model-assisted step."""

    model_config = ConfigDict(extra="allow")

    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)
    model_fingerprint: str | None = None
    provider_config_ref: str | None = None
    temperature: float | None = None
    max_tokens: int | None = Field(default=None, ge=0)
    response_format: dict[str, Any] | None = None

    @field_validator("provider", "model", "model_fingerprint", "provider_config_ref")
    @classmethod
    def _clean_text_field(cls, value: str | None) -> str | None:
        return _optional_text(value)


class ToolSchemaRecord(BaseModel):
    """Allowlisted tool schema identity for one callable tool."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    tool_name: str = Field(min_length=1)
    schema_ref: str | None = None
    json_schema: dict[str, Any] | None = Field(default=None, alias="schema")
    schema_fingerprint: str | None = None

    @field_validator("tool_name", "schema_ref", "schema_fingerprint")
    @classmethod
    def _clean_text_field(cls, value: str | None) -> str | None:
        return _optional_text(value)

    @model_validator(mode="after")
    def _fill_schema_fingerprint(self) -> ToolSchemaRecord:
        if self.schema_fingerprint is None:
            if self.json_schema is None and self.schema_ref is None:
                raise ValueError("tool schema requires schema_ref, schema, or schema_fingerprint")
            self.schema_fingerprint = _fingerprint(
                {
                    "tool_name": self.tool_name,
                    "schema_ref": self.schema_ref,
                    "schema": self.json_schema,
                }
            )
        return self


class ToolCallRecord(BaseModel):
    """One model-requested tool call and its persisted result refs."""

    model_config = ConfigDict(extra="forbid")

    tool_name: str = Field(min_length=1)
    call_ref: str = Field(min_length=1)
    output_ref: str | None = None
    rejection_ref: str | None = None
    status: ToolCallStatus = "pass"

    @field_validator("tool_name", "call_ref", "output_ref", "rejection_ref")
    @classmethod
    def _clean_text_field(cls, value: str | None) -> str | None:
        return _optional_text(value)

    @model_validator(mode="after")
    def _require_result_ref(self) -> ToolCallRecord:
        if self.status == "pass" and self.output_ref is None:
            raise ValueError("passing tool calls require output_ref")
        if self.status in {"blocked", "fail"} and self.rejection_ref is None:
            raise ValueError("blocked or failed tool calls require rejection_ref")
        return self


class ParserContract(BaseModel):
    """Parser contract used to turn model output into runtime artifacts."""

    model_config = ConfigDict(extra="forbid")

    parser_id: str = Field(min_length=1)
    parser_version: str = Field(min_length=1)
    contract_ref: str = Field(min_length=1)
    input_schema_ref: str = Field(min_length=1)
    output_schema_ref: str = Field(min_length=1)

    @field_validator(
        "parser_id",
        "parser_version",
        "contract_ref",
        "input_schema_ref",
        "output_schema_ref",
    )
    @classmethod
    def _clean_text_field(cls, value: str) -> str:
        return _non_empty(value)


class ValidationRef(BaseModel):
    """Validation artifact that proves parser/output contract status."""

    model_config = ConfigDict(extra="forbid")

    validator_id: str = Field(min_length=1)
    status: ValidationStatus
    validation_ref: str = Field(min_length=1)

    @field_validator("validator_id", "validation_ref")
    @classmethod
    def _clean_text_field(cls, value: str) -> str:
        return _non_empty(value)


class RepairDecision(BaseModel):
    """Recorded repair or healing decision for prompt/parser/tool output."""

    model_config = ConfigDict(extra="forbid")

    decision: str = Field(min_length=1)
    status: RepairDecisionStatus
    reason: str = Field(min_length=1)
    repair_ref: str | None = None
    approved_by: str | None = None

    @field_validator("decision", "reason", "repair_ref", "approved_by")
    @classmethod
    def _clean_text_field(cls, value: str | None) -> str | None:
        return _optional_text(value)

    @model_validator(mode="after")
    def _require_applied_ref(self) -> RepairDecision:
        if self.status == "applied" and self.repair_ref is None:
            raise ValueError("applied repair decisions require repair_ref")
        return self


class AuthorityHandoffRef(BaseModel):
    """Consumer handoff proving where model-assisted output became authority."""

    model_config = ConfigDict(extra="forbid")

    scope: AuthorityScope
    handoff_ref: str = Field(min_length=1)
    consumer: str = Field(min_length=1)
    status: ValidationStatus = "pass"

    @field_validator("handoff_ref", "consumer")
    @classmethod
    def _clean_text_field(cls, value: str) -> str:
        return _non_empty(value)


class PromptToolLedgerFinding(BaseModel):
    """Operator-facing prompt/tool symptom classification."""

    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1)
    severity: Literal["info", "warn", "fail"] = "warn"
    failure_reason: str = Field(min_length=1)
    step_id: str = Field(min_length=1)
    validator_ref: str = Field(min_length=1)
    upstream_spine_blocker_refs: tuple[str, ...] = Field(default=())

    @field_validator("code", "failure_reason", "step_id", "validator_ref")
    @classmethod
    def _clean_text_field(cls, value: str) -> str:
        return _non_empty(value)

    @field_validator("upstream_spine_blocker_refs")
    @classmethod
    def _clean_refs(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return _clean_ref_tuple(values)


class ModelAssistedStepLedger(BaseModel):
    """One model-assisted step that can influence runtime authority."""

    model_config = ConfigDict(extra="forbid")

    step_id: str = Field(min_length=1)
    step_kind: str = Field(min_length=1)
    authority_scopes: tuple[AuthorityScope, ...]
    prompt: PromptTemplateRecord
    model_provider: ModelProviderConfig
    tool_allowlist: tuple[str, ...] = Field(default=())
    tool_schemas: tuple[ToolSchemaRecord, ...] = Field(default=())
    tool_call_refs: tuple[ToolCallRecord, ...] = Field(default=())
    output_refs: tuple[str, ...]
    parser_contract: ParserContract
    validation_refs: tuple[ValidationRef, ...]
    repair_decisions: tuple[RepairDecision, ...] = Field(default=())
    authority_handoff_refs: tuple[AuthorityHandoffRef, ...]

    @field_validator("step_id", "step_kind")
    @classmethod
    def _clean_text_field(cls, value: str) -> str:
        return _non_empty(value)

    @field_validator("tool_allowlist", "output_refs")
    @classmethod
    def _clean_refs(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return _clean_ref_tuple(values)

    @field_validator("authority_scopes")
    @classmethod
    def _require_authority_scope(
        cls,
        values: tuple[AuthorityScope, ...],
    ) -> tuple[AuthorityScope, ...]:
        if not values:
            raise ValueError("model-assisted steps require at least one authority scope")
        return tuple(dict.fromkeys(values))

    @model_validator(mode="after")
    def _validate_authority_materials(self) -> ModelAssistedStepLedger:
        allowlist = set(self.tool_allowlist)
        schema_tools = {schema.tool_name for schema in self.tool_schemas}
        if allowlist and not allowlist <= schema_tools:
            missing = sorted(allowlist - schema_tools)
            raise ValueError("tool_allowlist missing schemas: " + ", ".join(missing))
        for call in self.tool_call_refs:
            if call.tool_name not in allowlist:
                raise ValueError(f"tool call not in allowlist: {call.tool_name}")
            if call.tool_name not in schema_tools:
                raise ValueError(f"tool call missing schema: {call.tool_name}")
        if not self.prompt.rendered_input_refs:
            raise ValueError("authority steps require rendered_input_refs")
        if not self.output_refs:
            raise ValueError("authority steps require output_refs")
        if not self.validation_refs:
            raise ValueError("authority steps require validation_refs")
        if not self.authority_handoff_refs:
            raise ValueError("authority steps require authority_handoff_refs")
        return self


class PromptToolParserAuthorityLedger(BaseModel):
    """Durable authority ledger for prompt/tool/parser mediated runtime outputs."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = SCHEMA_VERSION
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    run_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    model_variant_id: str | None = None
    prompt_tool_ledger_ref: str | None = None
    steps: tuple[ModelAssistedStepLedger, ...]
    findings: tuple[PromptToolLedgerFinding, ...] = Field(default=())
    summary: dict[str, Any] = Field(default_factory=dict)

    @field_validator("schema_version")
    @classmethod
    def _require_schema_version(cls, value: str) -> str:
        if value != SCHEMA_VERSION:
            raise ValueError(f"unsupported prompt/tool/parser ledger schema: {value}")
        return value

    @field_validator("run_id", "job_id", "model_variant_id", "prompt_tool_ledger_ref")
    @classmethod
    def _clean_text_field(cls, value: str | None) -> str | None:
        return _optional_text(value)

    @field_validator("steps")
    @classmethod
    def _require_steps(
        cls,
        values: tuple[ModelAssistedStepLedger, ...],
    ) -> tuple[ModelAssistedStepLedger, ...]:
        if not values:
            raise ValueError("prompt/tool/parser ledger requires at least one step")
        return values

    @model_validator(mode="after")
    def _fill_summary(self) -> PromptToolParserAuthorityLedger:
        scopes = sorted({scope for step in self.steps for scope in step.authority_scopes})
        tool_names = sorted({tool for step in self.steps for tool in step.tool_allowlist})
        repair_count = sum(len(step.repair_decisions) for step in self.steps)
        status = (
            "pass"
            if self._has_required_authority_scopes(AUTHORITY_SCOPES)
            and self._steps_have_passing_validation()
            else "fail"
        )
        self.summary = {
            **dict(self.summary or {}),
            "status": status,
            "step_count": len(self.steps),
            "authority_scopes": scopes,
            "tool_count": len(tool_names),
            "tool_names": tool_names,
            "repair_decision_count": repair_count,
            "finding_count": len(self.findings),
            "upstream_spine_blocker_refs": sorted(
                {
                    ref
                    for finding in self.findings
                    for ref in finding.upstream_spine_blocker_refs
                }
            ),
        }
        return self

    def _has_required_authority_scopes(self, scopes: Sequence[str]) -> bool:
        present = {scope for step in self.steps for scope in step.authority_scopes}
        return set(scopes) <= present

    def _steps_have_passing_validation(self) -> bool:
        return all(
            any(ref.status in _PASS_STATUSES for ref in step.validation_refs)
            and any(handoff.status in _PASS_STATUSES for handoff in step.authority_handoff_refs)
            for step in self.steps
        )


@dataclass(frozen=True)
class PromptToolParserAuthorityValidation:
    """Scorecard-friendly validation result for prompt/tool/parser authority."""

    satisfied: bool
    missing_codes: tuple[str, ...]
    step_count: int
    authority_scopes: tuple[str, ...]


def validate_prompt_tool_parser_authority(
    payload: PromptToolParserAuthorityLedger | Mapping[str, Any] | None,
    *,
    required_scopes: Sequence[str] = AUTHORITY_SCOPES,
) -> PromptToolParserAuthorityValidation:
    """Validate a ledger as authority for prompt/tool/parser mediated outputs."""

    if payload is None:
        return PromptToolParserAuthorityValidation(
            satisfied=False,
            missing_codes=("prompt_tool_parser_authority_ledger_missing",),
            step_count=0,
            authority_scopes=(),
        )
    try:
        ledger = (
            payload
            if isinstance(payload, PromptToolParserAuthorityLedger)
            else PromptToolParserAuthorityLedger.model_validate(payload)
        )
    except ValidationError:
        return PromptToolParserAuthorityValidation(
            satisfied=False,
            missing_codes=("prompt_tool_parser_authority_ledger_invalid",),
            step_count=0,
            authority_scopes=(),
        )

    scopes = tuple(sorted({scope for step in ledger.steps for scope in step.authority_scopes}))
    missing = tuple(
        f"prompt_tool_parser_{scope}_handoff_missing"
        for scope in required_scopes
        if scope not in scopes
    )
    status = str(ledger.summary.get("status") or "").casefold()
    if status not in {"pass", "ok", "passed"}:
        missing = (*missing, "prompt_tool_parser_authority_ledger_not_passing")
    return PromptToolParserAuthorityValidation(
        satisfied=not missing,
        missing_codes=missing,
        step_count=len(ledger.steps),
        authority_scopes=scopes,
    )


def serialize_prompt_tool_ledger(
    ledger: PromptToolParserAuthorityLedger | Mapping[str, Any],
) -> dict[str, Any]:
    """Return JSON-compatible prompt/tool/parser ledger payload."""

    parsed = (
        ledger
        if isinstance(ledger, PromptToolParserAuthorityLedger)
        else PromptToolParserAuthorityLedger.model_validate(ledger)
    )
    return parsed.model_dump(mode="json", exclude_none=True, by_alias=True)


def persist_prompt_tool_ledger(
    ledger: PromptToolParserAuthorityLedger | Mapping[str, Any],
    *,
    store: Any,
    inputs: Iterable[InputRef] | None = None,
) -> ArtifactRef:
    """Persist a prompt/tool/parser authority ledger in CAS and return its ref."""

    payload = serialize_prompt_tool_ledger(ledger)
    return store.put_json(
        payload,
        ArtifactWriteOptions(
            kind=PROMPT_TOOL_LEDGER_KIND,
            media_type="application/json",
            schema=SchemaInfo(name=PROMPT_TOOL_LEDGER_SCHEMA, version="1.0"),
            inputs=list(inputs or []),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )


def build_prompt_tool_ledger_from_model_variant(
    *,
    run_id: str,
    job_id: str,
    variant: Mapping[str, Any],
    rendered_input_refs: Iterable[str],
    output_refs: Iterable[str],
    authority_handoff_refs: Iterable[str],
    generated_at: datetime | None = None,
) -> PromptToolParserAuthorityLedger:
    """Build a conservative ledger from a runtime model-variant summary."""

    variant_id = _optional_text(variant.get("model_variant_id")) or "unknown_variant"
    model = _optional_text(variant.get("model")) or "unknown_model"
    provider = _optional_text(variant.get("provider")) or "unknown_provider"
    base_inputs = tuple(_clean_refs(rendered_input_refs))
    base_outputs = tuple(_clean_refs(output_refs))
    handoff_values = tuple(_clean_refs(authority_handoff_refs))
    if not base_inputs:
        base_inputs = (f"model_variant_id:{variant_id}",)
    if not base_outputs:
        base_outputs = (f"model_variant_id:{variant_id}:output",)
    if not handoff_values:
        handoff_values = base_outputs

    raw_steps = variant.get("steps")
    step_rows = (
        [dict(item) for item in raw_steps if isinstance(item, Mapping)]
        if isinstance(raw_steps, list)
        else []
    )
    if not step_rows:
        step_rows = [
            {
                "agent": "model_variant",
                "action": "model_variant_output",
                "status": variant.get("status") or "completed",
            }
        ]

    steps = []
    for index, row in enumerate(step_rows, start=1):
        action = _optional_text(row.get("action")) or f"model_step_{index}"
        agent = _optional_text(row.get("agent")) or "llm_agent"
        status = str(row.get("status") or "ok").casefold()
        validation_status: ValidationStatus = (
            "pass" if status in {"ok", "completed", "pass", "success"} else "fail"
        )
        steps.append(
            {
                "step_id": f"{variant_id}:{agent}:{action}:{index}",
                "step_kind": action,
                "authority_scopes": list(AUTHORITY_SCOPES),
                "prompt": {
                    "template_id": f"{agent}.{action}",
                    "template_version": "runtime-inferred",
                    "rendered_input_refs": list(base_inputs),
                    "template_variables_fingerprint": _fingerprint(dict(row.get("details") or {})),
                },
                "model_provider": {
                    "provider": provider,
                    "model": model,
                    "model_fingerprint": _optional_text(
                        variant.get("model_fingerprint") or variant.get("fingerprint")
                    ),
                },
                "tool_allowlist": [],
                "tool_schemas": [],
                "tool_call_refs": [],
                "output_refs": list(base_outputs),
                "parser_contract": {
                    "parser_id": f"{agent}.{action}.parser",
                    "parser_version": "runtime-inferred",
                    "contract_ref": handoff_values[0],
                    "input_schema_ref": base_inputs[0],
                    "output_schema_ref": base_outputs[0],
                },
                "validation_refs": [
                    {
                        "validator_id": f"{agent}.{action}.status",
                        "status": validation_status,
                        "validation_ref": handoff_values[0],
                    }
                ],
                "repair_decisions": [
                    {
                        "decision": "schema_healing_not_required"
                        if int(variant.get("schema_healing_count") or 0) <= 0
                        else "schema_healing_applied",
                        "status": "not_applicable"
                        if int(variant.get("schema_healing_count") or 0) <= 0
                        else "applied",
                        "reason": (
                            "Runtime variant reported no schema healing."
                            if int(variant.get("schema_healing_count") or 0) <= 0
                            else "Runtime variant reported schema healing."
                        ),
                        **(
                            {"repair_ref": handoff_values[0]}
                            if int(variant.get("schema_healing_count") or 0) > 0
                            else {}
                        ),
                    }
                ],
                "authority_handoff_refs": [
                    {
                        "scope": scope,
                        "handoff_ref": handoff_values[min(pos, len(handoff_values) - 1)],
                        "consumer": f"runtime.{scope}",
                        "status": "pass",
                    }
                    for pos, scope in enumerate(AUTHORITY_SCOPES)
                ],
            }
        )
    return PromptToolParserAuthorityLedger.model_validate(
        {
            "generated_at": generated_at or datetime.now(UTC),
            "run_id": run_id,
            "job_id": job_id,
            "model_variant_id": variant_id,
            "steps": steps,
        }
    )


def _fingerprint(payload: Any) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or any(char in text for char in "\r\n\t"):
        return None
    return text


def _non_empty(value: Any) -> str:
    text = _optional_text(value)
    if text is None:
        raise ValueError("value must be non-empty text")
    return text


def _clean_refs(values: Iterable[Any]) -> list[str]:
    refs: list[str] = []
    for value in values:
        text = _optional_text(value)
        if text is not None and text not in refs:
            refs.append(text)
    return refs


def _clean_ref_tuple(values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(_clean_refs(values))


__all__ = [
    "AUTHORITY_SCOPES",
    "PROMPT_TOOL_LEDGER_FILENAME",
    "PROMPT_TOOL_LEDGER_KIND",
    "PROMPT_TOOL_LEDGER_REF_KEY",
    "PROMPT_TOOL_LEDGER_REPORT_KEY",
    "SCHEMA_VERSION",
    "AuthorityHandoffRef",
    "ModelAssistedStepLedger",
    "ModelProviderConfig",
    "ParserContract",
    "PromptTemplateRecord",
    "PromptToolLedgerFinding",
    "PromptToolLedgerError",
    "PromptToolParserAuthorityLedger",
    "PromptToolParserAuthorityValidation",
    "RepairDecision",
    "ToolCallRecord",
    "ToolSchemaRecord",
    "ValidationRef",
    "build_prompt_tool_ledger_from_model_variant",
    "persist_prompt_tool_ledger",
    "serialize_prompt_tool_ledger",
    "validate_prompt_tool_parser_authority",
]
