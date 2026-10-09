"""Exercise the declared same-assets/replaced-callable limitation natively."""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import types

import hnswlib
import pytest


def main():
    repo = Path(sys.argv[1])
    path = repo / "policy-engine/tests/unit/remediation/test_emb_03.py"
    spec = importlib.util.spec_from_file_location("orch02_encoder_fixture", path)
    fixture = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = fixture
    spec.loader.exec_module(fixture)
    out = Path(os.environ["ORCH02_OUTPUT_DIR"])
    tmp = Path(tempfile.mkdtemp(prefix="callable-residual-", dir=out))
    db = tmp / "lex.duckdb"
    fixture._prepare_lex_db(db, entities=[("entity-target", "target entity"), ("entity-decoy", "decoy entity")])
    fixture._prepare_legal_search_rows(db)
    fixture.legal_embedder.build_local_embeddings_and_indexes(
        db_path=db, output_dir=tmp, embedding_model="legal-fixture-model", embedding_device="cpu",
        encoder=fixture._DirectionalLegalEncoder(revision=0))
    profiles = fixture._legal_query_profile(tmp)
    encoder = fixture._DirectionalLegalEncoder(revision=0)
    identity_before = fixture.derive_encoder_identity(encoder)
    original_encode = encoder.encode
    def substituted_encode(self, texts, **kwargs):
        # Same object type/config/tokenizer/weights; only executable behavior differs.
        vectors = original_encode(texts, **kwargs)
        return vectors[:, [1, 0, 2, 3]]
    encoder.encode = types.MethodType(substituted_encode, encoder)
    identity_after = fixture.derive_encoder_identity(encoder)
    assert identity_before == identity_after
    knn_calls = []
    native_knn = hnswlib.Index.knn_query
    with pytest.MonkeyPatch.context() as mp:
        def record_native(index, *args, **kwargs):
            result = native_knn(index, *args, **kwargs)
            knn_calls.append({"labels": result[0].tolist(), "distances": result[1].tolist()})
            return result
        mp.setattr(hnswlib.Index, "knn_query", record_native)
        graph = fixture.LegalKnowledgeGraph(db, tmp, query_encoder=encoder, query_profile=profiles)
        try:
            substituted = [x.entity_id for x in graph.search_entities("target", top_k=1, min_similarity=0.0)]
            encoder.encode = original_encode
            restored = [x.entity_id for x in graph.search_entities("target", top_k=1, min_similarity=0.0)]
        finally:
            graph.close()
    assert substituted == ["entity-decoy"]
    assert restored == ["entity-target"]
    report = {"verdict": "DECLARED_RESIDUAL_REPRODUCED", "identity_unchanged": True,
              "generation_profile_preserved": True, "encoder_and_membership_guards_preserved": True,
              "substituted_result": substituted, "restored_result": restored,
              "encoded_texts": encoder.encoded_texts, "native_knn_calls": knn_calls,
              "boundary": "asset/config/tokenizer identity does not attest replaced executable encode behavior"}
    (out / "semantic.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
