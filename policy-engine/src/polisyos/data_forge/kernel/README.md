# Data Forge Kernel

- Owner: team-data-forge
- Purpose: shared Data Forge kernel primitives used by domain ingestion, normalization, and pipeline orchestration.
- Allowed contents: stable kernel APIs, internal helpers, runtime contracts, and kernel-local fixtures that are required by package tests.
- Embedding extraction in `embeddings.py` accepts prepared `(id, text)` rows
  and owns the shared encode/index mechanics. Academic and Catalog wrappers
  retain their distinct SQL/text profiles; generation publication and reader
  selection remain an EMB-02 concern.
- Non-empty embedding generations bind a digest of the loaded encoder weights,
  module configuration, and tokenizer assets into the existing generator rule
  version. `derive_encoder_identity()` recomputes that candidate digest from a
  loaded encoder; `hnsw_index_matches_vectors()` checks a loaded native index
  against its expected matrix. The existing generation manifest projects the
  persisted digest for audit. The precomputed-vector publisher also requires
  the live encoder when binding an identity and recomputes it inside the
  shared kernel; identity-only or mismatched assertions are rejected. These
  compatibility checks do not attest an arbitrary replacement for the
  encoder's executable `encode` behavior, so admission must be supplied by a
  trusted local encoder provider. Unsupported asset shapes are recorded as
  `encoder=unbound`, which cannot match an identified query encoder.
- The identity derivation canonicalizes only fast-tokenizer backend `padding`
  and `truncation` values that exactly match the shared SentenceTransformer
  encode request: tokenizer side, pad token and IDs, and the owning module's
  `max_seq_length`. It checks the backend's native API properties and confirms
  that deserializing its JSON reproduces those properties before clearing
  request settings on a separate backend copy. This prevents request-time
  state from changing the asset identity while preserving other backend
  material and all high-level tokenizer/module settings. A present malformed
  backend JSON refuses identity derivation. This remains a loaded-asset
  compatibility identity, not proof of arbitrary executable encode behavior.
  Previously selected generations retain their recorded digest; they are not
  rewritten in place and may require a real regeneration before the current
  profile can admit vector reuse or queries.
- Runtime consumers use the lazy Legal and Catalog read facades for shared
  generation references and identity helpers. `embedding_generation_matches_encoder()`
  recomputes the supplied live encoder identity and compares the selected
  complete generation's basis kind, projection rule, model, device, and vector
  dimension as one effective intent. `legal_embedding_generator_rule_version()`
  delegates to the same kernel rule builder used during publication.
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
