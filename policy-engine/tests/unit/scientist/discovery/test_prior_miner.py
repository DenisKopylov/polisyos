from pathlib import Path

from polisyos.scientist.methods.discovery.prior_miner import PriorMiner, PriorMinerConfig
from polisyos.scientist.methods.discovery.priors import DisputedEdge, GraphPriorBundle, PriorEdge


def _bundle() -> GraphPriorBundle:
    return GraphPriorBundle(
        high_confidence_edges=[
            PriorEdge(
                edge_key="X->Y",
                src="X",
                dst="Y",
                presence_confidence=0.8,
                orientation_confidence=0.7,
                provenance_refs=["prov:x->y"],
            )
        ],
        required_edges=[
            PriorEdge(
                edge_key="A->B",
                src="A",
                dst="B",
                presence_confidence=0.9,
                orientation_confidence=0.85,
                provenance_refs=["prov:a->b"],
            )
        ],
        disputed_edges=[
            DisputedEdge(
                dispute_id="dispute:XZ",
                skeleton_key="X--Z",
                candidate_edges=[
                    PriorEdge(
                        edge_key="X->Z",
                        src="X",
                        dst="Z",
                        presence_confidence=0.5,
                        orientation_confidence=0.5,
                    ),
                    PriorEdge(
                        edge_key="Z->X",
                        src="Z",
                        dst="X",
                        presence_confidence=0.5,
                        orientation_confidence=0.5,
                    ),
                ],
                dispute_reasons=["competing_direction_support"],
            )
        ],
    )


def test_prior_miner_queries_hybrid_skg_and_filters_to_target_edges(monkeypatch, tmp_path) -> None:
    captured: dict[str, object] = {}
    db_path = tmp_path / "mock.duckdb"
    db_path.write_text("", encoding="utf-8")
    index_dir = tmp_path / "index"
    index_dir.mkdir()

    class FakeQuery:
        def __init__(self, db_path: Path, index_dir: Path) -> None:
            captured["db_path"] = db_path
            captured["index_dir"] = index_dir

        def query_prior_for_variables(self, variables, **kwargs):
            captured["variables"] = list(variables)
            captured["kwargs"] = kwargs
            return [
                {
                    "src": "X",
                    "dst": "Y",
                    "direction": "positive",
                    "confidence": 0.8,
                    "n_articles": 3,
                    "article_refs": ["oa:1"],
                    "candidate_layer": "hybrid",
                    "quality_signals": {"layers": ["exact"]},
                    "evidence_strength": "meta_analysis",
                },
                {
                    "src": "A",
                    "dst": "B",
                    "direction": "positive",
                    "confidence": 0.7,
                    "n_articles": 2,
                    "article_refs": ["oa:2"],
                    "candidate_layer": "hybrid",
                    "quality_signals": {},
                    "evidence_strength": "rct",
                },
                {
                    "src": "Z",
                    "dst": "X",
                    "direction": "mixed",
                    "confidence": 0.4,
                    "n_articles": 1,
                    "article_refs": ["oa:3"],
                    "candidate_layer": "hybrid",
                    "quality_signals": {},
                    "evidence_strength": "observational",
                },
                {
                    "src": "Q",
                    "dst": "W",
                    "direction": "mixed",
                    "confidence": 0.9,
                    "n_articles": 1,
                    "article_refs": [],
                    "candidate_layer": "hybrid",
                    "quality_signals": {},
                    "evidence_strength": "observational",
                },
            ]

        def latest_skg_version_id(self):
            return 42

        def skg_snapshot_ref(self, *, version_id=None):
            return f"duckdb:///tmp/mock.duckdb#v{version_id}"

        def close(self):
            captured["closed"] = True

    monkeypatch.setattr("polisyos.scientist.discovery.prior_miner.SKGQuery", FakeQuery)

    miner = PriorMiner(
        config=PriorMinerConfig(
            academic_db_path=str(db_path),
            academic_index_dir=str(index_dir),
        )
    )
    result = miner.mine(_bundle())

    assert captured["db_path"] == db_path
    assert captured["index_dir"] == index_dir
    assert set(captured["variables"]) == {"A", "B", "X", "Y", "Z"}
    assert captured["kwargs"]["edge_layer"] == "hybrid"
    assert {row.edge_key for row in result.support_rows} == {"A->B", "X->Y", "Z->X"}
    assert "X->Z" in result.unresolved_edges
    assert result.skg_version_id == 42
    assert result.skg_snapshot_ref == "duckdb:///tmp/mock.duckdb#v42"
    assert result.status == "ok"
    assert result.source_statuses["academic"].status.value == "available"
    assert captured["closed"] is True


def test_prior_miner_returns_degraded_bundle_when_skg_unavailable(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "mock.duckdb"
    db_path.write_text("", encoding="utf-8")
    index_dir = tmp_path / "index"
    index_dir.mkdir()

    class BrokenQuery:
        def __init__(self, db_path: Path, index_dir: Path) -> None:
            del db_path, index_dir

            raise RuntimeError("db unavailable")

    monkeypatch.setattr("polisyos.scientist.discovery.prior_miner.SKGQuery", BrokenQuery)

    miner = PriorMiner(
        config=PriorMinerConfig(
            academic_db_path=str(db_path),
            academic_index_dir=str(index_dir),
        )
    )
    result = miner.mine(_bundle())

    assert result.status == "degraded"
    assert result.support_rows == []
    assert "academic_prior_query_failed:RuntimeError:db unavailable" in result.warnings
    assert result.source_statuses["academic"].status.value == "query_failed"


def test_prior_miner_returns_degraded_bundle_when_db_path_missing() -> None:
    miner = PriorMiner(
        config=PriorMinerConfig(
            academic_db_path="/tmp/definitely-missing-prior-mine.duckdb",
            academic_index_dir="/tmp/index",
        )
    )

    result = miner.mine(_bundle())

    assert result.status == "degraded"
    assert result.support_rows == []
    assert result.source_statuses["academic"].status.value == "missing_path"
