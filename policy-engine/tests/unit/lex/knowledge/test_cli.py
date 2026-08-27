from __future__ import annotations

import json
from types import SimpleNamespace
from typing import ClassVar

import pytest

from polisyos.lex.knowledge import cli, search_legal_knowledge


class _FakeStore:
    instances: ClassVar[list[_FakeStore]] = []

    def __init__(self, *, db_path, index_dir) -> None:  # type: ignore[no-untyped-def]
        self.db_path = db_path
        self.index_dir = index_dir
        self.closed = False
        self.query: str | None = None
        self.top_k: int | None = None
        self.trust_tier: str | None = None
        type(self).instances.append(self)

    def text_search_facts(
        self,
        query: str,
        *,
        top_k: int,
        trust_tier: str,
    ) -> list[SimpleNamespace]:
        self.query = query
        self.top_k = top_k
        self.trust_tier = trust_tier
        return [SimpleNamespace(fact_id="fact-1")]

    def close(self) -> None:
        self.closed = True


def test_lex_search_command_owns_store_query_and_close(monkeypatch, tmp_path) -> None:
    _FakeStore.instances.clear()
    monkeypatch.setattr(cli, "LegalKnowledgeStore", _FakeStore)

    results = search_legal_knowledge(
        output_dir=tmp_path,
        query="reporting duty",
        top_k=7,
    )

    assert [result.fact_id for result in results] == ["fact-1"]
    [store] = _FakeStore.instances
    assert store.db_path == tmp_path / "lex_knowledge_graph.duckdb"
    assert store.index_dir == tmp_path
    assert store.query == "reporting duty"
    assert store.top_k == 7
    assert store.trust_tier == "grounded_fact"
    assert store.closed is True


def test_lex_search_command_closes_store_when_query_fails(monkeypatch, tmp_path) -> None:
    class _FailingStore(_FakeStore):
        def text_search_facts(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            del args, kwargs
            raise RuntimeError("query failed")

    _FailingStore.instances.clear()
    monkeypatch.setattr(cli, "LegalKnowledgeStore", _FailingStore)

    with pytest.raises(RuntimeError, match="query failed"):
        search_legal_knowledge(output_dir=tmp_path, query="x", top_k=1)

    [store] = _FailingStore.instances
    assert store.closed is True


def test_lex_cli_serializes_typed_search_results(monkeypatch, tmp_path, capsys) -> None:
    result = SimpleNamespace(
        model_dump=lambda **_: {
            "fact_id": "fact-1",
            "predicate": "requires",
            "confidence": 0.9,
        }
    )
    observed: dict[str, object] = {}

    def _fake_search(*, output_dir, query, top_k):  # type: ignore[no-untyped-def]
        observed.update(output_dir=output_dir, query=query, top_k=top_k)
        return [result]

    monkeypatch.setattr(cli, "search_legal_knowledge", _fake_search)

    exit_code = cli.main(
        [
            "--output-dir",
            str(tmp_path),
            "--query",
            "licensing",
            "--top-k",
            "3",
        ]
    )

    assert exit_code == 0
    assert observed == {
        "output_dir": tmp_path,
        "query": "licensing",
        "top_k": 3,
    }
    assert json.loads(capsys.readouterr().out) == {
        "confidence": 0.9,
        "fact_id": "fact-1",
        "predicate": "requires",
    }
