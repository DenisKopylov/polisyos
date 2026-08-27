"""Lex-owned command-line search over the legal knowledge store."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from polisyos.lex.knowledge.store import LegalKnowledgeStore
from polisyos.lex.knowledge.types import LegalFactResult


def search_legal_knowledge(
    *,
    output_dir: Path,
    query: str,
    top_k: int = 20,
) -> list[LegalFactResult]:
    """Search grounded legal facts through the Lex-owned store.

    Args:
        output_dir: Directory containing the published DuckDB graph and indexes.
        query: Text query passed to the Lex store.
        top_k: Maximum number of grounded facts to return.

    Returns:
        Typed grounded legal facts in store-defined relevance order.
    """
    store = LegalKnowledgeStore(
        db_path=output_dir / "lex_knowledge_graph.duckdb",
        index_dir=output_dir,
    )
    try:
        return store.text_search_facts(
            query,
            top_k=top_k,
            trust_tier="grounded_fact",
        )
    finally:
        store.close()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m polisyos.lex.knowledge.cli",
        description="Search grounded facts in a published Lex knowledge graph.",
    )
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--query", required=True)
    parser.add_argument("--top-k", type=int, default=20)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the Lex-owned interactive legal-search command."""
    args = _build_parser().parse_args(argv)
    results = search_legal_knowledge(
        output_dir=args.output_dir,
        query=args.query,
        top_k=args.top_k,
    )
    for result in results:
        sys.stdout.write(
            json.dumps(
                result.model_dump(mode="json"),
                ensure_ascii=False,
                sort_keys=True,
            )
            + "\n"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["main", "search_legal_knowledge"]
