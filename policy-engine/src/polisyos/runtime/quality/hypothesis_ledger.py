"""Hypothesis ledger for candidate-to-authority firewall inputs."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, datetime
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from polisyos.runtime.quality.prompt_tool_ledger import (
    PromptToolParserAuthorityLedger,
    persist_runtime_quality_json_artifact,
)

HYPOTHESIS_LEDGER_SCHEMA_VERSION = "policyos.runtime.hypothesis_ledger.v1"
HYPOTHESIS_LEDGER_KIND = "runtime.hypothesis_ledger"
HYPOTHESIS_LEDGER_SCHEMA = "polisyos.runtime.HypothesisLedger"
HYPOTHESIS_LEDGER_REPORT_KEY = "hypothesis_ledger"
HYPOTHESIS_LEDGER_REF_KEY = "hypothesis_ledger_ref"
HYPOTHESIS_LEDGER_FILENAME = "hypothesis_ledger.json"

HypothesisSourceClass = Literal[
    "llm_candidate",
    "llm_critic",
    "llm_critic_consensus",
    "llm_drafter",
    "deterministic_producer",
    "historical_failure",
    "human_reviewer",
    "public_contestation",
]
HypothesisAdmissionState = Literal[
    "candidate_unverified",
    "rejected_speculation",
    "typed_blocker",
    "limitation",
    "admitted_to_obligation",
    "admitted_to_claim",
]

CANDIDATE_AUTHORITY_SLOTS: tuple[str, ...] = (
    "legal_authority",
    "data_authority",
    "method_authority",
    "participation_authority",
    "closeout_authority",
    "projection_authority",
    "claim_authority",
    "obligation_authority",
)
LLM_SOURCE_CLASSES = frozenset(
    {"llm_candidate", "llm_critic", "llm_critic_consensus", "llm_drafter"}
)


class RuntimeQualityArtifactRef(Protocol):
    """Minimal artifact ref contract returned by runtime-quality persistence helpers."""

    artifact_id: object
    kind: str
    media_type: str


class HypothesisLedgerError(ValueError):
    """Typed hypothesis-ledger invariant violation."""

    def __init__(self, code: str, message: str | None = None) -> None:
        self.code = code
        super().__init__(f"{code}: {message or code}")


class CandidateAuthorityEnvelope(BaseModel):
    """Purpose-scoped authority boundary carried by one candidate record."""

    model_config = ConfigDict(extra="allow", frozen=True)

    authoritative_for: tuple[str, ...] = ("candidate_hypothesis",)
    may_not_use_for: tuple[str, ...] = CANDIDATE_AUTHORITY_SLOTS

    @field_validator("authoritative_for", "may_not_use_for", mode="before")
    @classmethod
    def _coerce_text_tuple(cls, value: object) -> tuple[str, ...]:
        return _coerce_ref_tuple(value)


class HypothesisLedgerEntry(BaseModel):
    """Append-only record for a formulator, critic, reviewer, or producer candidate."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    candidate_id: str = Field(min_length=1)
    candidate_ref: str = Field(min_length=1)
    source_class: HypothesisSourceClass
    candidate_kind: str = Field(min_length=1)
    target_authority_slots: tuple[str, ...]
    target_claim_ids: tuple[str, ...] = Field(default=())
    prompt_fingerprint: str | None = None
    tool_refs: tuple[str, ...] = Field(default=())
    repair_decision_lineage: tuple[str, ...] = Field(default=())
    prompt_tool_ledger_ref: str | None = None
    authority_envelope: CandidateAuthorityEnvelope = Field(
        default_factory=CandidateAuthorityEnvelope
    )
    admission_state: HypothesisAdmissionState = "candidate_unverified"
    producer_validation_refs: tuple[str, ...] = Field(default=())
    reader_validation_refs: tuple[str, ...] = Field(default=())
    admission_ref: str | None = None
    admitted_by: str | None = None
    content: Mapping[str, Any] = Field(default_factory=dict)
    provenance: Mapping[str, Any] = Field(default_factory=dict)
    emitted_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator(
        "candidate_id",
        "candidate_ref",
        "candidate_kind",
        "prompt_fingerprint",
        "prompt_tool_ledger_ref",
        "admission_ref",
        "admitted_by",
        mode="before",
    )
    @classmethod
    def _clean_text_field(cls, value: object) -> str | None:
        return _optional_text(value)

    @field_validator(
        "target_authority_slots",
        "target_claim_ids",
        "tool_refs",
        "repair_decision_lineage",
        "producer_validation_refs",
        "reader_validation_refs",
        mode="before",
    )
    @classmethod
    def _clean_tuple_field(cls, value: object) -> tuple[str, ...]:
        return _coerce_ref_tuple(value)

    @model_validator(mode="after")
    def _validate_candidate_contract(self) -> HypothesisLedgerEntry:
        if not self.target_authority_slots:
            raise ValueError("hypothesis candidates require target_authority_slots")
        if self.admission_state in {"admitted_to_claim", "admitted_to_obligation"} and not (
            self.producer_validation_refs or self.reader_validation_refs
        ):
            raise ValueError("admitted candidates require producer or reader validation refs")
        if (
            self.source_class == "llm_critic_consensus"
            and self.admission_state in {"admitted_to_claim", "admitted_to_obligation"}
            and not (self.producer_validation_refs and self.reader_validation_refs)
        ):
            raise ValueError(
                "critic consensus admission requires reviewer and producer validation refs"
            )
        if self.admission_state == "candidate_unverified":
            missing_forbidden = set(self.target_authority_slots) - set(
                self.authority_envelope.may_not_use_for
            )
            if missing_forbidden:
                raise ValueError(
                    "unverified candidates must forbid target authority slots: "
                    + ",".join(sorted(missing_forbidden))
                )
        return self

    @property
    def has_admission_lineage(self) -> bool:
        """Whether the entry carries the prompt/tool/repair lineage needed downstream."""

        return bool(
            _optional_text(self.prompt_fingerprint)
            and self.tool_refs
            and self.repair_decision_lineage
        )

    @property
    def validation_refs(self) -> tuple[str, ...]:
        """Producer and reader validation refs in stable order."""

        return tuple(
            dict.fromkeys([*self.producer_validation_refs, *self.reader_validation_refs])
        )


class HypothesisLedger(BaseModel):
    """Append-only candidate ledger consumed by authority firewalls."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["policyos.runtime.hypothesis_ledger.v1"] = (
        HYPOTHESIS_LEDGER_SCHEMA_VERSION
    )
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    run_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    hypothesis_ledger_ref: str | None = None
    prompt_tool_ledger_ref: str | None = None
    entries: tuple[HypothesisLedgerEntry, ...]
    summary: Mapping[str, Any] = Field(default_factory=dict)

    @field_validator(
        "run_id",
        "job_id",
        "hypothesis_ledger_ref",
        "prompt_tool_ledger_ref",
        mode="before",
    )
    @classmethod
    def _clean_text_field(cls, value: object) -> str | None:
        return _optional_text(value)

    @field_validator("entries")
    @classmethod
    def _require_entries(
        cls,
        values: tuple[HypothesisLedgerEntry, ...],
    ) -> tuple[HypothesisLedgerEntry, ...]:
        if not values:
            raise ValueError("hypothesis ledger requires at least one entry")
        seen: set[str] = set()
        duplicates: list[str] = []
        for entry in values:
            if entry.candidate_id in seen:
                duplicates.append(entry.candidate_id)
            seen.add(entry.candidate_id)
        if duplicates:
            raise ValueError("duplicate hypothesis candidate ids: " + ",".join(duplicates))
        return values

    @model_validator(mode="after")
    def _fill_summary(self) -> HypothesisLedger:
        self.summary = {
            **dict(self.summary or {}),
            "entry_count": len(self.entries),
            "source_classes": sorted({entry.source_class for entry in self.entries}),
            "admission_states": sorted({entry.admission_state for entry in self.entries}),
            "candidate_unverified_count": sum(
                1 for entry in self.entries if entry.admission_state == "candidate_unverified"
            ),
            "admitted_count": sum(
                1
                for entry in self.entries
                if entry.admission_state in {"admitted_to_claim", "admitted_to_obligation"}
            ),
            "lineage_complete_count": sum(
                1 for entry in self.entries if entry.has_admission_lineage
            ),
            "target_authority_slots": sorted(
                {slot for entry in self.entries for slot in entry.target_authority_slots}
            ),
        }
        return self

    def entries_by_ref(self) -> dict[str, HypothesisLedgerEntry]:
        """Return candidate entries keyed by both candidate id and candidate ref."""

        rows: dict[str, HypothesisLedgerEntry] = {}
        for entry in self.entries:
            rows[entry.candidate_id] = entry
            rows[entry.candidate_ref] = entry
        return rows


HypothesisLedgerInput = HypothesisLedger | Mapping[str, Any]


def deserialize_hypothesis_ledger(
    ledger: HypothesisLedgerInput,
) -> HypothesisLedger:
    """Deserialize and validate one hypothesis ledger payload."""

    if isinstance(ledger, HypothesisLedger):
        return ledger
    if isinstance(ledger, Mapping):
        return HypothesisLedger.model_validate(dict(ledger))
    raise TypeError("hypothesis ledger must be a mapping or model")


def serialize_hypothesis_ledger(
    ledger: HypothesisLedgerInput,
) -> dict[str, Any]:
    """Return a JSON-compatible hypothesis ledger payload."""

    return deserialize_hypothesis_ledger(ledger).model_dump(mode="json", exclude_none=True)


def persist_hypothesis_ledger(
    ledger: HypothesisLedgerInput,
    *,
    store: object,
    inputs: Iterable[object] | None = None,
) -> RuntimeQualityArtifactRef:
    """Persist a hypothesis ledger in CAS and return its artifact ref."""

    payload = serialize_hypothesis_ledger(ledger)
    return persist_runtime_quality_json_artifact(
        payload=payload,
        store=store,
        kind=HYPOTHESIS_LEDGER_KIND,
        schema_name=HYPOTHESIS_LEDGER_SCHEMA,
        inputs=inputs,
    )


def append_hypothesis_ledger_entry(
    ledger: HypothesisLedgerInput,
    entry: HypothesisLedgerEntry | Mapping[str, Any],
) -> HypothesisLedger:
    """Return a new ledger with one entry appended, preserving previous entries."""

    parsed = deserialize_hypothesis_ledger(ledger)
    parsed_entry = (
        entry
        if isinstance(entry, HypothesisLedgerEntry)
        else HypothesisLedgerEntry.model_validate(entry)
    )
    return HypothesisLedger.model_validate(
        {
            **parsed.model_dump(mode="json", exclude_none=True),
            "entries": [
                *(row.model_dump(mode="json", exclude_none=True) for row in parsed.entries),
                parsed_entry.model_dump(mode="json", exclude_none=True),
            ],
        }
    )


def build_hypothesis_ledger_from_prompt_tool_ledger(
    *,
    run_id: str,
    job_id: str,
    prompt_tool_ledger: PromptToolParserAuthorityLedger | Mapping[str, Any],
    candidates: Sequence[Mapping[str, Any]],
    hypothesis_ledger_ref: str | None = None,
    generated_at: datetime | None = None,
) -> HypothesisLedger:
    """Build a candidate ledger, inheriting prompt/tool/repair lineage where absent."""

    prompt_ledger = (
        prompt_tool_ledger
        if isinstance(prompt_tool_ledger, PromptToolParserAuthorityLedger)
        else PromptToolParserAuthorityLedger.model_validate(prompt_tool_ledger)
    )
    inherited = _lineage_from_prompt_tool_ledger(prompt_ledger)
    entries = []
    for index, candidate in enumerate(candidates, start=1):
        row = dict(candidate)
        row.setdefault("candidate_id", f"hypothesis-candidate:{run_id}:{index}")
        row.setdefault("candidate_ref", row["candidate_id"])
        row.setdefault("source_class", "llm_candidate")
        row.setdefault("candidate_kind", "candidate")
        row.setdefault("target_authority_slots", ["claim_authority"])
        row.setdefault("prompt_fingerprint", inherited["prompt_fingerprint"])
        row.setdefault("tool_refs", inherited["tool_refs"])
        row.setdefault("repair_decision_lineage", inherited["repair_decision_lineage"])
        row.setdefault("prompt_tool_ledger_ref", prompt_ledger.prompt_tool_ledger_ref)
        row.setdefault("authority_envelope", _candidate_boundary(row))
        entries.append(row)
    return HypothesisLedger.model_validate(
        {
            "schema_version": HYPOTHESIS_LEDGER_SCHEMA_VERSION,
            "generated_at": generated_at or datetime.now(UTC),
            "run_id": run_id,
            "job_id": job_id,
            "hypothesis_ledger_ref": hypothesis_ledger_ref,
            "prompt_tool_ledger_ref": prompt_ledger.prompt_tool_ledger_ref,
            "entries": entries,
        }
    )


def hypothesis_entry_fingerprint(entry: HypothesisLedgerEntry | Mapping[str, Any]) -> str:
    """Return a stable fingerprint for one candidate entry."""

    parsed = (
        entry
        if isinstance(entry, HypothesisLedgerEntry)
        else HypothesisLedgerEntry.model_validate(entry)
    )
    return _fingerprint(parsed.model_dump(mode="json", exclude_none=True))


def _lineage_from_prompt_tool_ledger(
    ledger: PromptToolParserAuthorityLedger,
) -> dict[str, Any]:
    prompt_fingerprint = next(
        (
            step.prompt.prompt_fingerprint
            for step in ledger.steps
            if step.prompt.prompt_fingerprint
        ),
        None,
    )
    tool_refs = tuple(
        dict.fromkeys(
            [
                *(
                    call.output_ref or call.rejection_ref or call.call_ref
                    for step in ledger.steps
                    for call in step.tool_call_refs
                ),
                *(
                    schema.schema_ref or schema.schema_fingerprint
                    for step in ledger.steps
                    for schema in step.tool_schemas
                ),
            ]
        )
    )
    repair_lineage = tuple(
        dict.fromkeys(
            [
                decision.repair_ref
                or decision.approved_by
                or f"{step.step_id}:{decision.decision}:{decision.status}"
                for step in ledger.steps
                for decision in step.repair_decisions
            ]
        )
    )
    return {
        "prompt_fingerprint": prompt_fingerprint,
        "tool_refs": tuple(ref for ref in tool_refs if ref),
        "repair_decision_lineage": repair_lineage,
    }


def _candidate_boundary(row: Mapping[str, Any]) -> dict[str, Any]:
    state = str(row.get("admission_state") or "candidate_unverified")
    target_slots = _coerce_ref_tuple(row.get("target_authority_slots") or ())
    if state == "candidate_unverified":
        may_not = tuple(dict.fromkeys([*CANDIDATE_AUTHORITY_SLOTS, *target_slots]))
        return {
            "authoritative_for": ["candidate_hypothesis"],
            "may_not_use_for": list(may_not),
        }
    return {
        "authoritative_for": list(target_slots or ("candidate_hypothesis",)),
        "may_not_use_for": [
            slot for slot in CANDIDATE_AUTHORITY_SLOTS if slot not in set(target_slots)
        ],
    }


def _fingerprint(payload: object) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or any(char in text for char in "\r\n\t"):
        return None
    return text


def _coerce_ref_tuple(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        values: Iterable[object] = (value,)
    elif isinstance(value, Iterable):
        values = value
    else:
        values = (value,)
    refs: list[str] = []
    for item in values:
        text = _optional_text(item)
        if text is not None and text not in refs:
            refs.append(text)
    return tuple(refs)


__all__ = [
    "CANDIDATE_AUTHORITY_SLOTS",
    "HYPOTHESIS_LEDGER_FILENAME",
    "HYPOTHESIS_LEDGER_KIND",
    "HYPOTHESIS_LEDGER_REF_KEY",
    "HYPOTHESIS_LEDGER_REPORT_KEY",
    "HYPOTHESIS_LEDGER_SCHEMA",
    "HYPOTHESIS_LEDGER_SCHEMA_VERSION",
    "LLM_SOURCE_CLASSES",
    "CandidateAuthorityEnvelope",
    "HypothesisAdmissionState",
    "HypothesisLedger",
    "HypothesisLedgerEntry",
    "HypothesisLedgerError",
    "HypothesisLedgerInput",
    "HypothesisSourceClass",
    "RuntimeQualityArtifactRef",
    "append_hypothesis_ledger_entry",
    "build_hypothesis_ledger_from_prompt_tool_ledger",
    "deserialize_hypothesis_ledger",
    "hypothesis_entry_fingerprint",
    "persist_hypothesis_ledger",
    "serialize_hypothesis_ledger",
]
