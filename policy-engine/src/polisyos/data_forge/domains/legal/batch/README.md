# Legal Batch (`polisyos.data_forge.domains.legal.batch`)

`polisyos.data_forge.domains.legal.batch` owns the moved Lex offline pipeline.
It turns the XML НПА corpus into the legal knowledge graph: parse/structure/SPO
extraction, graph assembly, quality reporting, and publish flow.

## Роль в системе

- **Зависит от:** `polisyos.data_forge.domains.legal.corpus`, `polisyos.fabric`, `polisyos.core`
- **Используется в:** offline benchmark/QC tooling,
  operator smoke/full runs, and cloud Lex runners.
- Пакет собирает DuckDB/HNSW surface для read-only legal search и audit-ready extraction artifacts.

## Ключевые концепции

- **Stage pipeline** — `parse`, `structure`, `spo`, `graph`, `embed-local`, `qc`, `publish` разбивают большой offline run на resume-friendly этапы.
- **Deterministic-first extraction** — templates, rules и deterministic SPO-path покрывают типовые документы до обращения к LLM.
- **Amendment quality layer** — `amendment_detector.py` и `amendment_metrics.py` измеряют target resolution и blocking amendment gaps.
- **Temporal resolution** — `temporal_parser.py` и новый `temporal_resolver.py` строят document/fact temporal envelopes для version-aware downstream logic.
- **Extraction quality filters** — `quality_filters.py` и `hallucination_detector.py` отсекают synthetic subjects, low-quality entities и suspicious SPO output.
- **Operational outputs** — smoke, QC и publish команды формируют manifests и quality reports, а не только raw graph tables.

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

Full reference: [docs/reference/lex/](../../../../docs/reference/lex/index.md)

## Current State

- Last updated: 2026-05-01
- Phase 4/8 cutover moved this runtime into Data Forge and retired the old Lex batch package.
- Canonical CLI: `python -m polisyos.data_forge.domains.legal.batch`.
- Cloud Lex manifest runner imports this Data Forge runtime directly.
