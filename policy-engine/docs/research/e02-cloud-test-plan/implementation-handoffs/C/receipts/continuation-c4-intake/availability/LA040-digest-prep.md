# LA-040 digest and input availability delta

Date: 2026-10-07. Read-only source/configuration and file-metadata review. No production table rows, projected text, vectors, model weights, or full database bytes were read, hashed, exported, or written. No product tests, model runs, or source changes were made.

## Pins and criterion

Root C checkout: `/Users/deniskopylov/.codex/worktrees/e02-C-continuation-20261006/polisyos`, branch `codex/e02-C-continuation-20261006`, HEAD `dbe1fb24b33201c7ff967a3227ab88e512e185d4`, tree `c161f86f7265fd90be66361cfd7ec89aa775c249`. The G snapshot is `83e7c0e934d0b40644dec8a24264a0602ef013e7`, tree `dc1a7697f506b23f2db0f1c80bf929fd2d6a2e0d`; criterion baseline is `198076863e143dea9f89f02734b13d50dae3eed5`, tree `2b754a92c27959e2e747738d47ed0b419f3b6dd8`.

The root C54 row at `9b92ce235a6ae85085109b0bec2916a7b3ae732b` binds LA-040 to `CD02` lines 2556–2594, criterion digest `04d9279a2c0e0e0f10649e69a1a06e4e8a4128b384d5b44f2c9cd45fff8ba67a`. The complete original card is `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/source/LA_r09_original.md` at the cited span. It distinguishes current source membership from reusable-vector equivalence: same-ID content changes, a removed member, projection/model changes, and the actual Legal reader are discriminators. It does not require inferring legal currentness or scanning full history.

## Existing discriminator

The canonical digest primitive is `policyos.generation_basis.v1` in `policy-engine/src/polisyos/data_forge/kernel/io/generation_basis.py`. `build_generation_basis` sorts unique member IDs; each member's `content_identity` is SHA-256 of the bytes passed by the producer; `basis_digest` is SHA-256 of canonical JSON containing schema version, basis kind, generator rule version, and the ordered member list. For the reviewed DFI candidate `ab44166335130463178e65dfc29a252c96afe479`, those bytes are the UTF-8 output of `data_forge/domains/legal/embedding_projection.py` after the producer's 32,000-character cap. Basis kinds are `legal_lex_entities_embedding`, `legal_lex_facts_embedding`, and `legal_lex_provisions_embedding`.

The exact producer selectors in `data_forge/domains/legal/batch/embedder.py` are all rows ordered by the corresponding ID: entities use `entity_id` plus names/type/aliases; facts use `fact_id` plus the 14 projected fact fields; provisions use `provision_id` plus `provision_text`. There is no status, `is_latest`, effective-date, or withdrawal filter. This is a deterministic selected-table snapshot, not a legally-current subset.

The exact bounded source selectors, **not executed**, are:

```sql
SELECT entity_id, name_en, name_uk, entity_type, aliases_en, aliases_uk
FROM lex_entities ORDER BY entity_id;

SELECT fact_id, subject_en, subject_uk, predicate, object_en, object_uk,
       fact_text, norm_type, action_canon, norm_type_canon,
       condition_text_uk, exception_text_uk, procedure_text_uk,
       thresholds_json, source_quote_uk
FROM lex_facts ORDER BY fact_id;

SELECT provision_id, provision_text
FROM lex_provisions ORDER BY provision_id;
```

For a permitted future source pass, use `entity_embedding_text`, `fact_embedding_text`, and `provision_embedding_text` from `data_forge/domains/legal/embedding_projection.py`, apply the existing 32,000-character cap, and feed `(id, projected_text.encode("utf-8"))` to `build_generation_basis`. The basis kind for each table is `legal_lex_entities_embedding`, `legal_lex_facts_embedding`, or `legal_lex_provisions_embedding`. An exact full-basis comparison also requires the actual `generator_rule_version` (including the encoder identity) from the matching generation inventory. There is no such inventory here, so inventing a rule string or treating a source-only digest as a matched producer profile would not be a valid acceptance command.

This semantic digest is different from a raw DuckDB file hash. It binds selected IDs and projected text, not unrelated database pages or non-projected columns. Conversely, a whole-file SHA would identify exact container bytes but would not provide the producer's ordered membership discriminator. The root `production_data/manifest.json` contains no checksum for `finalize/lex_knowledge_graph.duckdb`, and the generation inventory contract does not record a source-DB file SHA.

The candidate's `kernel/embeddings.py` adds `derive_encoder_identity`: it fingerprints the loaded model state tensors, module/configuration and tokenizer vocabulary/settings/backend material, and puts that digest into `generator_rule_version` with projection rule, model label, device, and dimension. The persisted inventory stores model label/device/dimension and basis; its selected-generation selector hashes the inventory. This would provide a content identity for the loaded encoder if a production generation existed; it is not an externally signed model-release record. Computing a fresh encoder identity requires reading loaded weight/tokenizer state.

The paired CAT candidate `8dfa7f3c544461c0ff081861848fcc5d8523da5b` loads the selected generation and independently re-reads all selected table projections in `LegalKnowledgeStore._load_legal_embedding_index`, comparing ordered IDs and `generation_basis_matches_members` before loading HNSW. That real consumer check necessarily reads source rows and projected text. It does not validate the query-vector model identity: low-level vector search accepts an untagged array.

## Current local input and pair availability

The manifest-selected local database remains at `/Users/deniskopylov/polisyos/policy-engine/production_data/lex/lex-amendment-only-optimized-20260501-v3/finalize/lex_knowledge_graph.duckdb`, size 19,336,278,016 bytes, mode read-only, mtime May 1, 2026 11:09:51. The small root manifest is SHA-256 `9e0e0aa0acd3c91f0120a80a2570be358ff16a63218abcd998f4d6f0212b6105`; its `lex` bundle declares this database and requires QC/benchmark/summary files, but no embedding output, query profile, model revision, or database checksum. `uv.lock` is SHA-256 `785ed273f744d66bccdbe7cb797ed37b616db938dd1c5ed483b2dedd98f294cb`; it pins software dependencies, not a model checkpoint.

Metadata-only file listing of the selected bundle found the DuckDB, QC/benchmark reports, amendment summary, logs, and `claim_exports` files. It found no `.legal_embedding_generations`, `embedding_generation.json`, Legal NPZ/HNSW files, or model config/tokenizer/weight assets in that bundle. The exact default cache paths checked were `~/.cache/huggingface`, `~/.cache/huggingface/hub`, `~/Library/Caches/huggingface/hub`, `~/.cache/torch/sentence_transformers`, `~/.cache/torch/hub/checkpoints`, and `~/.cache/transformers`: the parent HF directory is empty and the others are absent. `HF_HOME`, `HUGGINGFACE_HUB_CACHE`, `TRANSFORMERS_CACHE`, `SENTENCE_TRANSFORMERS_HOME`, and `TORCH_HOME` are unset. This result is limited to those named paths and the selected bundle; it is not a global model-unavailability claim. No other files in the production bundle were opened.

The known profiles do not establish a pair. DFI local embedding defaults to `intfloat/multilingual-e5-large`, device `mps`, 1024 dimensions, normalized vectors. Canonical `LegalKnowledgeGraph` query embedding defaults to remote OpenAI `text-embedding-3-large` and L2-normalizes the returned vector; the `policy_verified` caller supplies an OpenAI key from the environment, while the control lex pipeline uses `text_search` without one. The selected bundle records neither a generated profile nor a query profile. The DFI local profile and the keyed high-level query profile are different; the read API does not bind them together.

## Allowed operation and blocker

The only operation completed under the current restriction is metadata inspection: read the small root manifest, stat the selected database and required companions, list file names under the selected Legal bundle, and inspect the named model-cache directory metadata. The 19-GB DB was not hashed. The local source-membership digest cannot be computed from these metadata: the canonical basis requires reading the selected IDs and projected text, and the current consumer's comparison also reads them. A raw DB hash would require a full 19-GB read, has no manifest field to compare against, and is not an equivalent membership digest.

There is no existing source-only command that computes and persists a Legal member basis without querying those rows; `embed-local` / `build_local_embeddings_and_indexes` additionally loads model weights and writes generation outputs. Under the explicit ban on production row/text reads, no runnable command can establish the criterion's source-membership digest. If the restriction is later changed, the bounded source pass must use the exact three selectors/projections above and retain only count, unique-ID validation, and basis/member digests; an actual persisted Legal generation and matched query profile/model identity must also be supplied for a producer-to-reader comparison. No source table scan or encoding was started here.

Typed result: input-file availability is established, but the selected bundle has no paired Legal generation/query profile and the production membership digest is `not_established` under the current no-row-read restriction. LA-040 remains held; do not call the input unavailable or infer withdrawal/currentness. The minimum next decision belongs to Root: whether to preserve the no-row-read constraint (in which case the criterion remains held) or authorize one bounded read-only membership pass in the shared data slot. C-W04/DFI must identify an actual persisted generation and its compatible served query profile before a source digest could close the pair; the local model cache paths do not provide those inputs. This is the existing LA-040 class, not a new finding.
