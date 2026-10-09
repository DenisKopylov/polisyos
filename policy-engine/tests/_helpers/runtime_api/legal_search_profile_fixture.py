"""Small actual-producer fixture for Legal selected-generation search tests."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import duckdb
import numpy as np


class _FixtureTokenizer:
    def get_vocab(self) -> dict[str, int]:
        return {"<unk>": 0, "legal": 1, "fixture": 2}

    @property
    def special_tokens_map(self) -> dict[str, str]:
        return {"unk_token": "<unk>"}

    def get_added_vocab(self) -> dict[str, int]:
        return {}


class FixtureLegalQueryEncoder:
    """Deterministic CPU encoder used only by the controlled fixture."""

    def __init__(self) -> None:
        self.device = "cpu"
        self.dimension = 4
        self.config = {"fixture": "legal-search", "dimension": self.dimension}
        self.tokenizer = _FixtureTokenizer()
        self.weight = np.asarray([1.0, 2.0, 3.0, 4.0], dtype=np.float32)

    def state_dict(self) -> dict[str, np.ndarray]:
        return {"fixture.weight": self.weight.copy()}

    def modules(self) -> tuple[FixtureLegalQueryEncoder, ...]:
        return (self,)

    def get_config_dict(self) -> dict[str, object]:
        return dict(self.config)

    def get_sentence_embedding_dimension(self) -> int:
        return self.dimension

    def encode(
        self,
        texts: list[str],
        *,
        normalize_embeddings: bool = True,
        **_kwargs: object,
    ) -> np.ndarray:
        rows: list[np.ndarray] = []
        for text in texts:
            scale = float((len(text) % 7) + 1)
            vector = np.asarray(
                [scale, scale + 1, scale + 2, scale + 3],
                dtype=np.float32,
            )
            if normalize_embeddings:
                vector = vector / np.linalg.norm(vector)
            rows.append(vector)
        return np.vstack(rows)


@dataclass(frozen=True, slots=True)
class LegalSearchProfileFixture:
    """Persisted Legal test database and the exact encoder that produced it."""

    output_dir: Path
    encoder: FixtureLegalQueryEncoder


def build_legal_search_profile_fixture(output_dir: Path) -> LegalSearchProfileFixture:
    """Build a tiny graph and selected generations through the Legal producer."""
    from polisyos.data_forge.domains.legal.batch.embedder import (
        build_local_embeddings_and_indexes,
    )

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    database = output_dir / "lex_knowledge_graph.duckdb"
    connection = duckdb.connect(str(database))
    try:
        connection.execute(
            "CREATE TABLE lex_entities (entity_id VARCHAR, name_en VARCHAR, name_uk VARCHAR, "
            "entity_type VARCHAR, aliases_en VARCHAR, aliases_uk VARCHAR)"
        )
        connection.execute(
            "INSERT INTO lex_entities VALUES "
            "('entity-1', 'Annual leave', 'Щорічна відпустка', 'concept', '', '')"
        )
        connection.execute(
            "CREATE TABLE lex_facts (fact_id VARCHAR, subject_en VARCHAR, subject_uk VARCHAR, "
            "predicate VARCHAR, object_en VARCHAR, object_uk VARCHAR, fact_text VARCHAR, "
            "norm_type VARCHAR, action_canon VARCHAR, norm_type_canon VARCHAR, "
            "condition_text_uk VARCHAR, exception_text_uk VARCHAR, procedure_text_uk VARCHAR, "
            "thresholds_json VARCHAR, source_quote_uk VARCHAR, trust_tier VARCHAR)"
        )
        connection.execute(
            "INSERT INTO lex_facts VALUES ('fact-annual-leave', 'Worker', 'Працівник', "
            "'is entitled to', 'annual leave', 'щорічну відпустку', "
            "'Worker is entitled to annual leave', 'right', 'entitlement', 'entitlement', "
            "'', '', '', '{}', 'Працівник має право на щорічну відпустку', 'grounded_fact')"
        )
        connection.execute(
            "CREATE TABLE lex_provisions (provision_id VARCHAR, provision_text VARCHAR)"
        )
        connection.execute(
            "INSERT INTO lex_provisions VALUES ('provision-1', 'Annual leave fixture provision')"
        )
        connection.execute("CHECKPOINT")
    finally:
        connection.close()

    encoder = FixtureLegalQueryEncoder()
    build_local_embeddings_and_indexes(
        db_path=database,
        output_dir=output_dir,
        embedding_model="controlled-legal-search-fixture",
        embedding_device="cpu",
        embedding_batch_size=2,
        embedding_chunk_size=8,
        encoder=encoder,
    )
    return LegalSearchProfileFixture(output_dir=output_dir, encoder=encoder)


__all__ = [
    "FixtureLegalQueryEncoder",
    "LegalSearchProfileFixture",
    "build_legal_search_profile_fixture",
]
