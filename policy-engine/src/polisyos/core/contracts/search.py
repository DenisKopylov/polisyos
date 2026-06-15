"""Shared search contracts for Layer 3 runtime-quality search ledgers."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

SEARCH_CONTRACT_SCHEMA_VERSION = "policyos.core.contracts.search.v1"

SearchMatchMode = Literal["exact", "alias", "lexical", "semantic", "relational", "derived"]
SearchCorpusKind = Literal["canonical", "bounded_surrogate", "temp_store", "fixture"]


class _SearchContractModel(BaseModel):
    """Strict base class for shared search DTOs."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class SearchRequest(_SearchContractModel):
    """Reusable search request contract shared across Layer 3 slices."""

    schema_version: Literal[SEARCH_CONTRACT_SCHEMA_VERSION] = SEARCH_CONTRACT_SCHEMA_VERSION
    request_id: str = Field(min_length=1)
    query_text: str = Field(min_length=1)
    construct_refs: tuple[str, ...] = Field(min_length=1)
    intent: str = Field(min_length=1)
    required_layers: tuple[str, ...] = Field(min_length=1)
    authority_purpose: str = Field(min_length=1)
    allowed_modes: tuple[SearchMatchMode, ...] = Field(min_length=1)
    budget: dict[str, object] = Field(default_factory=dict)
    rule_version: str = Field(min_length=1)


class SearchCandidate(_SearchContractModel):
    """One candidate returned by a reusable search ledger."""

    candidate_ref: str = Field(min_length=1)
    source_layer: str = Field(min_length=1)
    match_mode: SearchMatchMode
    score: float = Field(ge=0.0, le=1.0)
    evidence_refs: tuple[str, ...] = Field(default=())
    limitation_refs: tuple[str, ...] = Field(default=())
    authority_boundary: dict[str, object] = Field(default_factory=dict)
    may_not_use_for: tuple[str, ...] = Field(default=())


class SearchLedger(_SearchContractModel):
    """Replayable search ledger with common corpus and frontier semantics."""

    schema_version: Literal[SEARCH_CONTRACT_SCHEMA_VERSION] = SEARCH_CONTRACT_SCHEMA_VERSION
    request_ref: str = Field(min_length=1)
    query_plan: dict[str, object] = Field(default_factory=dict)
    corpus_ref: str = Field(min_length=1)
    corpus_path: str = Field(min_length=1)
    corpus_snapshot_hash: str = Field(pattern=r"^sha256:[0-9a-fA-F]{64}$")
    corpus_kind: SearchCorpusKind
    configured_store_path: str | None = None
    indexes_used: tuple[str, ...] = Field(min_length=1)
    index_version_refs: tuple[str, ...] = Field(default=())
    index_freshness: dict[str, object] = Field(default_factory=dict)
    query_expansion_traces: tuple[dict[str, object], ...] = Field(default=())
    candidates: tuple[SearchCandidate, ...] = Field(default=())
    rejected_candidates: tuple[SearchCandidate, ...] = Field(default=())
    no_hit_frontier: tuple[str, ...] = Field(default=())
    incompleteness: dict[str, object] = Field(default_factory=dict)
    replay_key: str = Field(min_length=1)
    replay_command: str = Field(min_length=1)
    replay_expected_output_hash: str = Field(pattern=r"^sha256:[0-9a-fA-F]{64}$")

    @model_validator(mode="after")
    def _replay_contract_is_executable(self) -> SearchLedger:
        if self.replay_key and not self.replay_command.strip():
            raise ValueError("replay_command is required when replay_key is present")
        return self
