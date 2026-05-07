# Generated Index: Legal Batch

Owner: `team-data-forge`
Last updated: 2026-05-05

## Pipeline Groups

| Group | Representative Modules |
| --- | --- |
| Ingestion and parsing | `xml_parser.py`, `provisions_io.py`, `openai_batch_embeddings.py` |
| Extraction | `spo_extractor.py`, `reference_extractor.py`, `template_extractor.py` |
| Normalization | `canonicalizers.py`, `deterministic_spo*.py`, `legal_unit.py` |
| Quality and confidence | `confidence.py`, `quality_filters.py`, `quality_report.py`, `llm_gate.py` |
| Graph and publication | `graph_builder.py`, `publish.py`, `postprocess.py`, `claim_bridge.py` |
| CLI and orchestration | `cli.py`, `pipeline.py`, `smoke.py`, `progress.py` |

## Tests

The mirrored test subtree is `tests/unit/data_forge/legal_batch/`.
