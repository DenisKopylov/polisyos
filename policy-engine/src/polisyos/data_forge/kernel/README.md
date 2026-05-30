# Data Forge Kernel

- Owner: team-data-forge
- Purpose: shared Data Forge kernel primitives used by domain ingestion, normalization, and pipeline orchestration.
- Allowed contents: stable kernel APIs, internal helpers, runtime contracts, and kernel-local fixtures that are required by package tests.
- Local verification: `uv run pytest tests/unit/data_forge/kernel -q`
- Maintenance: kernel changes must preserve domain package boundaries; deprecated adapters need an owner and sunset in the shim ledger.
- Snapshot finalization writes `data_forge_provenance_manifest.json` and
  `data_forge_snapshot_binding.json` beside the legacy snapshot manifest so
  runtime closeout can inspect official snapshot/release identity, hashes,
  corpus identity, creation time, builder revision, transform lineage, quality
  gates, and claim requirement bindings.
