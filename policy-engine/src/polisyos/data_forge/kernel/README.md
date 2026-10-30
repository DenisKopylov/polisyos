# Data Forge Kernel

- Owner: team-data-forge
- Purpose: shared Data Forge kernel primitives used by domain ingestion, normalization, and pipeline orchestration.
- Allowed contents: stable kernel APIs, internal helpers, runtime contracts, and kernel-local fixtures that are required by package tests.
- The `polisyos.data_forge.kernel.runtime` child is kernel-local runtime support; it is distinct from Foundry execution utilities and the top-level Runtime lifecycle/API package.
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
  advances `embedding_generation.json` before refreshing either flat
  compatibility file. If a flat copy fails, `EmbeddingCompatibilityProjectionError`
  reports the selected generation and failed target; a flat pair may be mixed
  and the caller must not treat it as the selected generation. A typed
  `empty_generation` is selected instead of reusing flat files; the resolver
  exposes a legacy pair only when no selector exists, and malformed selected
  generations fail closed. Academic and Catalog vector readers require a
  selected generation; they admit a native cosine index only when its complete
  labels and stored vectors match the selected finite float32 matrix. This
  compatibility check does not prove that the matrix was produced by the
  declared encoder or prevent a concurrent filesystem writer.
- Local verification: `uv run pytest tests/unit/data_forge/kernel -q`
- Maintenance: kernel changes must preserve domain package boundaries; deprecated adapters need an owner and sunset in the shim ledger.
- Snapshot finalization writes `data_forge_provenance_manifest.json` and
  `data_forge_snapshot_binding.json` beside the legacy snapshot manifest so
  runtime closeout can inspect official snapshot/release identity, hashes,
  corpus identity, creation time, builder revision, transform lineage, quality
  gates, and claim requirement bindings.

- Generic Data Forge failures (`DataForgeError`, `DataForgeValidationError`,
  `SchemaCompatibilityError`, and `SnapshotCommitError`) are owned by this
  kernel package. Legal corpus exception semantics stay with
  `domains/legal/contracts.py`; generic artifact readers default to the kernel
  validation error and domain callers select their own error class explicitly.

## Write-free publish and binding meaning

`prepare_publish_manifest` is the actual publisher's shared input constructor.
The snapshot finalizer uses one full binding-row constructor for writing and
historical readback. `prepare_snapshot_binding_meaning` projects explicit owner
occurrence roles at constructor inputs; `read_snapshot_binding_meaning` first
recomputes the entire emitted row/provenance and source-copy relations. Supplied
claim/transform fields retain their meaning; no output-prefix stripping is used.
The current candidate profile refuses QC-report-dependent meaning until that
owner relation is supplied. Occurrence tokens in a prospective meaning projection
are variable roles, never issued artifact refs or claims that a new publish ran.
