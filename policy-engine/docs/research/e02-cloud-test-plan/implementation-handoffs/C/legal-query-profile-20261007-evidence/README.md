# C5 Legal query-profile evidence packet

This packet preserves the focused source/runtime receipts for the frozen Legal query-profile candidate. It is evidence for review, not the canonical `implementation_handoff.v1`; the machine handoff is intentionally deferred until the independent review pointer arrives.

## Candidate and ancestry

- Slice base: `f428b114f4afb5c9cdde93a8e9bf036abe5ac329`, tree `feda38826ac6cf2a3a5ac38e0e86dd72d72d8730`.
- Candidate implementation: `c60e37e7833b2dbb22af1868e31dc3f519d6a4f2`, tree `8c9eb49a9a7096ed564f74e91b6f7f1bc1f2b714`, branch `codex/e02-C-legal-query-20261007`; c60 is a direct child of the slice base.
- The base already contains the Catalog/DFI dependency history, including Catalog checkpoint `8dfa7f3c544461c0ff081861848fcc5d8523da5b`, DFI `12190b1e8a25a6e9c2edc3b9c08f106e76ea5b63`, and cache/output basis fixes `6cfd7ffca`, `d747ada47`, and `ab44166335130463178e65dfc29a252c96afe479`.
- `git diff --name-only f428b114f4afb5c9cdde93a8e9bf036abe5ac329..c60e37e7833b2dbb22af1868e31dc3f519d6a4f2` yields the complete ten-path slice delta:
  - `policy-engine/docs/reference/lex/batch-pipeline.md`
  - `policy-engine/docs/reference/lex/knowledge.md`
  - `policy-engine/release-fragments/unreleased/2026-10-07-legal-query-profile-binding.toml`
  - `policy-engine/src/polisyos/data_forge/domains/legal/batch/README.md`
  - `policy-engine/src/polisyos/data_forge/domains/legal/batch/embedder.py`
  - `policy-engine/src/polisyos/data_forge/domains/legal/embedding_projection.py`
  - `policy-engine/src/polisyos/lex/knowledge/README.md`
  - `policy-engine/src/polisyos/lex/knowledge/search.py`
  - `policy-engine/src/polisyos/lex/knowledge/store.py`
  - `policy-engine/tests/unit/remediation/test_emb_03.py`

## Property and deciding tests

The gate binds the selected immutable Legal generation to a live encoder identity derived from state-dict weights, module configuration, tokenizer vocabulary/configuration, and device/dimension. The reader derives identity immediately before encoding the request text and again after the canonical normalized encoder call; it rejects unsupported assets, mismatch, or identity drift before `knn_query`. Callers cannot submit an embedding vector as proof of its producer. Each operation retains one selected generation/index/ID snapshot, and the next operation observes selector replacement.

The focused EMB-03 file contains the behavioral controls:

- `test_graph_query_encoder_reads_all_three_selected_legal_generations` exercises entity, fact, and provision consumers through the actual Legal reader and native HNSW index on tiny fixture data.
- `test_live_query_encoder_must_match_selected_generation_before_knn` uses a same-dimension, wrong-weight encoder and confirms zero HNSW queries.
- `test_raw_vector_cannot_bypass_query_profile_gate_and_control_is_discriminating` removes only the intake gate while keeping selected metadata and HNSW; the forged vector selects the decoy, while restoring the gate selects the target.
- `test_encoder_asset_change_during_query_encode_is_rejected_before_knn` mutates encoder weights during the live call and confirms zero HNSW queries.
- `test_concurrent_selector_replacement_keeps_query_on_one_generation` publishes a sibling selector while one request is blocked in encoding; that request uses its old generation, and the following request rejects its now-mismatched encoder.
- `test_wrong_selected_generation_rejects_previous_query_encoder` and `test_previous_rule_generation_is_unsupported_even_with_same_encoder` check re-publication and v1 rule refusal.
- `test_openai_label_does_not_authorize_query_vectors_and_hybrid_falls_back` confirms that an OpenAI model label/key does not construct an uninspectable remote vector producer and that hybrid search falls back to text with a typed unsupported reason.

The shared read-only Python environment loaded real native `hnswlib` 0.8.0 from `hnswlib.cpython-314-darwin.so`, SHA-256 `1995d684a31ecce3f0b2f817e283c7ba0d3bd77c961c0f47f2adb552f8cddf4a`. NumPy was 2.3.5, `numpy/__init__.py` SHA-256 `93924ac4b793328947dfd9eb9355e54eccdfd26a92c8dd52188aed2e52c7eb38`. This establishes native HNSW execution for fixture tests only; the encoder weights/tokenizer and corpus are deterministic fixtures.

## Commands and outputs

Commands ran in `/Users/deniskopylov/.codex/worktrees/e02-c-legal-query-20261007/polisyos` with the read-only interpreter `/Users/deniskopylov/polisyos/policy-engine/.venv/bin/python` and candidate `PYTHONPATH="$PWD/policy-engine/src:$PWD/policy-engine"`.

- Focused runtime and adversarial tests:
  `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD/policy-engine/src:$PWD/policy-engine" /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python -m pytest policy-engine/tests/unit/remediation/test_emb_03.py -q`
  Exit 0; `20 passed`. Full stdout: `test_emb_03.stdout.txt` (SHA-256 `c66ef7936b32d2201bf6eb901cf69cbc8e71996669c38afe1f70ad40098e04a3`).
- Ruff on all five changed Python files:
  `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD/policy-engine/src:$PWD/policy-engine" /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python -m ruff check policy-engine/src/polisyos/data_forge/domains/legal/embedding_projection.py policy-engine/src/polisyos/data_forge/domains/legal/batch/embedder.py policy-engine/src/polisyos/lex/knowledge/store.py policy-engine/src/polisyos/lex/knowledge/search.py policy-engine/tests/unit/remediation/test_emb_03.py`
  Exit 0; `All checks passed!`. Full stdout: `ruff-changed-python.stdout.txt` (SHA-256 `82b3e6a6c090a57601d22943bd23fca9218d1031dbe5a7b754092f9a156b4f18`). This is a changed-file Ruff check, not a full-repository lint receipt.
- Ruff formatting check on the four modified Python files not carrying pre-existing formatting in `embedder.py`:
  `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD/policy-engine/src:$PWD/policy-engine" /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python -m ruff format --check policy-engine/src/polisyos/data_forge/domains/legal/embedding_projection.py policy-engine/src/polisyos/lex/knowledge/store.py policy-engine/src/polisyos/lex/knowledge/search.py policy-engine/tests/unit/remediation/test_emb_03.py`
  Exit 0; `4 files already formatted`. Full stdout: `ruff-format-check.stdout.txt` (SHA-256 `177f260a5645724013185e4b140c7045cc39e56c0c97b120f5cb23599f85f0de`). The embedder diff is limited to importing the shared v2 rule constant; unrelated formatter churn was reverted.
- Release fragment TOML parse: exit 0; output `{'id': '2026-10-07-legal-query-profile-binding', 'type': 'changed', 'compatibility_changes': 1}` in `release-fragment-parse.stdout.txt` (SHA-256 `6f8e15ee981ffaf46d4c79c7f14205a0a0b0fe1fbbe022088c164ed236e98c71`).
- Candidate module and backend origins: `provenance.py` and full output `import-origins.stdout.txt` (SHA-256 `5339749338b3e4c3c7639dcd7cfb08cc3b1143cdf76df0d444c72f6ebe87bb22`). Python 3.14.0; NumPy 2.3.5; native hnswlib 0.8.0; all six inspected PolisyOS module origins are under this candidate worktree's `policy-engine/src`.
- `git diff --check f428b114f4afb5c9cdde93a8e9bf036abe5ac329..c60e37e7833b2dbb22af1868e31dc3f519d6a4f2` exited 0.

## Warm read-only DB probe

`db_readonly_probe.py` uses the tracked tiny EMB-03 fixtures and real `LegalKnowledgeStore`/embedding builder APIs. Command and environment are retained in `db-readonly-probe-command.txt`; full deciding output is `db_readonly_probe.stdout.txt` (SHA-256 `b84d95fdc6a9dc7f3edcf07a1bae2b1c85823953ded0d3c045bc3f0bb420ad0c`). Python 3.14.0, DuckDB 1.4.3, candidate `PYTHONPATH`; source hashes for `store.py`, `embedder.py`, and `kernel/embeddings.py` match before and after.

The warmed `LegalKnowledgeGraph` returned the target. An ordinary second DuckDB read-write connection against the same file while its read-only Store connection was open was refused with `ConnectionException` (“Can't open a connection to same database file with a different configuration than existing connections”). The supported embedding builder then ran successfully with the warm reader open, published a new selector generation, and the next query re-resolved that generation and returned the target. The database SHA stayed unchanged. No ordinary supported in-place source mutation with unchanged selector was observed; the earlier concern about such a stale-row result is retracted. Failed initial probe attempts are preserved as non-product harness failures: `db_readonly_probe_harness-error.stdout.txt` (wrong result attribute in script) and `db_readonly_probe_fixture-setup-error.stdout.txt` (rerun reused its fixture DB path). Both were corrected before the deciding exit-0 probe.

## Limits and status

- LA-040 is **held for production closure**, not passed on production. The actual Legal DB is present, but a matching selected generation and inspectable production encoder/tokenizer assets were not established. No production corpus or model weights were read.
- The query rule is now `policyos.legal.embedding.v2`; prior v1 generations are refused by the vector reader and require rebuild. The OpenAI constructor arguments remain for compatibility, but remote labels/embeddings do not authorize vector search; hybrid search uses its honest text fallback when local query assets are unsupported.
- No wheel/archive or installed-package check was run. The verified shared environment has no `hatchling` module/distribution (`hatchling-presence.stdout.txt`, SHA-256 `6aac1c0b9759c08eb3b91811f5f6d039360c7a9d7d5041911725307c594831ba`); no install or dependency mutation was attempted.
- This packet records fixture/runtime mechanism evidence and bounded limitations. It does not close findings or replace the pending independent review and canonical machine handoff.
