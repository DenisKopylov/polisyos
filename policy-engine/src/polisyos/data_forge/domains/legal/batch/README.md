# Legal Batch (`polisyos.data_forge.domains.legal.batch`)

`polisyos.data_forge.domains.legal.batch` owns the moved Lex offline pipeline.
It turns the XML legal-acts corpus into the legal knowledge graph: parse/structure/SPO
extraction, graph assembly, quality reporting, and publish flow.

## Role in the system

- **Depends on:** `polisyos.data_forge.domains.legal.corpus`, `polisyos.fabric`, `polisyos.core`
- **Used by:** offline benchmark/QC tooling,
  operator smoke/full runs, and cloud Lex runners.
- The package builds the DuckDB/HNSW surface for read-only legal search and audit-ready extraction artifacts.

## Key concepts

- **Stage pipeline** — `parse`, `structure`, `spo`, `graph`, `embed-local`, `qc`, and `publish` split a large offline run into resumable stages.
- **Deterministic-first extraction** — templates, rules, and the deterministic SPO path cover typical documents before the pipeline calls an LLM.
- **Amendment quality layer** — `amendment_detector.py` and `amendment_metrics.py` measure target resolution and blocking amendment gaps.
- **Temporal resolution** — `temporal_parser.py` and `temporal_resolver.py` build document and fact temporal envelopes for version-aware downstream logic.
- **Extraction quality filters** — `quality_filters.py` and `hallucination_detector.py` reject synthetic subjects, low-quality entities, and suspicious SPO output.
- **Content-bound Legal embeddings** — `embedding_projection.py` is the shared entity/fact/provision text projection. `embedder.py` reads one table snapshot, fingerprints the loaded encoder assets, and binds that identity plus each projected member into the selected generation. Incremental reuse requires the same member bytes and encoder identity.
- **Controlled local runtime profile** — `embed-local --runtime-material-profile-root PATH` asks the existing `LegalRuntimeMaterialOwner` to resolve the source-pinned model from `PATH/hf-cache` and verify `PATH/asset-file-manifest.txt`. An omitted profile keeps the legacy unowned candidate-generation path; an explicit invalid profile raises a typed refusal and never falls back.
- **Operational outputs** — smoke, QC, and publish commands produce manifests and quality reports, not only raw graph tables.

## Public API

| Type/Function                         | Description                                                       |
| ------------------------------------- | ----------------------------------------------------------------- |
| `pipeline.py`                         | Main orchestration for staged batch runs                          |
| `amendment_detector.py`               | Detect amendment-heavy documents and target-resolution candidates |
| `collect_amendment_quality_metrics()` | Shared amendment QC metrics for benchmark and report stages       |
| `quality_filters.py`                  | Deterministic filters for low-quality threshold/entity extraction |
| `temporal_resolver.py`                | Deterministic temporal envelopes for docs and facts               |
| `qc.py`, `quality_report.py`          | Batch-level quality checks and report assembly                    |
| `publish.py`                          | Publish manifests and bundle metadata for completed runs          |

Full reference: [docs/reference/lex/](../../../../../../docs/reference/lex/index.md)

## Current State

- Last updated: 2026-10-15
- Phase 4/8 cutover moved this runtime into Data Forge and retired the old Lex batch package.
- Canonical CLI: `python -m polisyos.data_forge.domains.legal.batch`.
- Controlled local generation example:

  ```bash
  python -m polisyos.data_forge.domains.legal.batch embed-local \
    --output-dir /path/to/legal-output \
    --runtime-material-profile-root /path/to/legal-runtime-profile
  ```

  The profile root is operator-local configuration, not evidence of legal
  authority, production source currentness, or publication readiness. The
  selected model and manifest remain source-pinned.
- Cloud Lex manifest runner imports this Data Forge runtime directly.
- Existing selected generations without a bound encoder identity are not reused or admitted for vector queries; rerun `embed-local` to publish a compatible generation.
