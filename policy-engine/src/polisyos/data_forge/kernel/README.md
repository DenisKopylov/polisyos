# Data Forge Kernel

- Owner: team-data-forge
- Purpose: shared Data Forge kernel primitives used by domain ingestion, normalization, and pipeline orchestration.
- Allowed contents: stable kernel APIs, internal helpers, runtime contracts, and kernel-local fixtures that are required by package tests.
- Embedding extraction in `embeddings.py` accepts prepared `(id, text)` rows
  and owns the shared encode/index mechanics. Academic and Catalog wrappers
  retain their distinct SQL/text profiles; the Legal builder retains its
  chunked incremental contract. Non-empty generations bind loaded encoder
  weights, tokenizer assets, and module projection settings in their existing
  generation rule version.
- EMB-02 publishes each successful build below `embedding_generations/` with
  NPZ, HNSW (when non-empty), IDs, basis, and inventory bytes, then atomically
  advances `embedding_generation.json`. A typed `empty_generation` is selected
  instead of reusing flat files; flat legacy pairs are read only when no
  selector exists, and a malformed selected generation fails closed.
- Local verification: `uv run pytest tests/unit/data_forge/kernel -q`
- Maintenance: kernel changes must preserve domain package boundaries; deprecated adapters need an owner and sunset in the shim ledger.
- Snapshot finalization writes `data_forge_provenance_manifest.json` and
  `data_forge_snapshot_binding.json` beside the legacy snapshot manifest so
  runtime closeout can inspect official snapshot/release identity, hashes,
  corpus identity, creation time, builder revision, transform lineage, quality
  gates, and claim requirement bindings.
