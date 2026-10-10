"""Typed Legal fact-generation snapshots for Lex search callers."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from polisyos.core.contracts import ApiMeta, LegalQueryGenerationIntentV1

LexSearchProfileRefusalCode = Literal[
    "query_profile_generation_unavailable",
    "query_profile_malformed",
    "selected_generation_unavailable",
]


class LexSearchProfileAvailableResponse(BaseModel):
    """Expose a selected Legal fact-generation request snapshot.

    This is a snapshot of the selected persisted generation, not a statement
    that its members, index, or encoder remain current. Search revalidates those
    properties when it consumes the snapshot.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    meta: ApiMeta
    status: Literal["available"]
    output_dir: str
    query_generation_intent: tuple[LegalQueryGenerationIntentV1, ...]


class LexSearchProfileRefusedResponse(BaseModel):
    """Return a typed refusal when no selected fact-generation snapshot exists."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    meta: ApiMeta
    status: Literal["refused"]
    output_dir: str
    refusal_code: LexSearchProfileRefusalCode


LexSearchProfileResponse = Annotated[
    LexSearchProfileAvailableResponse | LexSearchProfileRefusedResponse,
    Field(discriminator="status"),
]


def selected_legal_fact_query_intent(
    output_dir: str | Path,
) -> tuple[LegalQueryGenerationIntentV1, ...]:
    """Resolve the persisted selected fact generation into exact request intent.

    The resolver verifies selector, inventory, and generation-member bytes. The
    downstream search still checks the current graph membership and live
    encoder before returning a vector result.
    """
    from polisyos.data_forge.read_api import legal as legal_read_api
    from polisyos.lex.knowledge import LegalQueryProfile, LegalQueryProfileError

    generation = legal_read_api.resolve_embedding_generation(
        Path(output_dir) / ".legal_embedding_generations" / "lex_fact_embeddings"
    )
    if generation is None or not generation.selected or generation.status != "complete":
        raise LegalQueryProfileError("selected_generation_unavailable")

    profile = LegalQueryProfile.from_generation(generation)
    if profile.basis_kind != "legal_lex_facts_embedding":
        raise LegalQueryProfileError("query_profile_malformed")
    try:
        inventory_json = profile.inventory_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise LegalQueryProfileError("query_profile_malformed") from exc

    return (
        LegalQueryGenerationIntentV1(
            basis_kind=profile.basis_kind,
            generation_id=profile.generation_id,
            inventory_json=inventory_json,
        ),
    )


__all__ = [
    "LexSearchProfileAvailableResponse",
    "LexSearchProfileRefusalCode",
    "LexSearchProfileRefusedResponse",
    "LexSearchProfileResponse",
    "selected_legal_fact_query_intent",
]
