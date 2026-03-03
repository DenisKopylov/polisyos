# Docs

`polisyos.fabric.docs` — документный pipeline, который готовит CAS-артефакты и world-сегменты для downstream `claims/world`.

## Pipeline

```text
ingest_doc_bytes -> normalize_doc -> structure_doc -> chunk_doc
```

Каждая стадия:

- обновляет `DocMeta`,
- пишет world event,
- формирует world fact segment + append в index.

## Основные модули

- `types.py` — `DocSourceSpec`, options/results dataclasses.
- `ingestion.py` — прием raw bytes, формирование `DocMeta`, запись raw artifact.
- `normalize.py` — decode + mime-aware text normalization через `BackendDispatcher`.
- `structure.py` — anchors/sections + `DocFragment` generation.
- `chunking.py` — char/paragraph chunking + fragment generation.
- `errors.py` — pipeline errors.
- `backends/` — `text_plain`, `text_html`, `pdf` (stub).

## Ограничения и поддержка MIME

- `DocSourceSpec` требует ровно один идентификатор: `canonical_url` или `official_id` или `source_locator`.
- `license` обязателен.
- Нативно поддержаны `text/plain` и `text/html`.
- Любой `text/*` без отдельного backend идет через plain-text normalizer.
- `pdf` backend в core — заглушка (нужны optional deps/расширения).

## Результаты стадий

`DocIngestResult`, `DocNormalizeResult`, `DocStructureResult`, `DocChunkResult` возвращают:

- `doc_source_id`, `doc_version_id`,
- актуальные artifact refs (`raw_ref`, `normalized_ref`, `structure_ref`, `chunks_ref`),
- `doc_meta_artifact_id`,
- `world_event_id`, `world_event_artifact_id`,
- `world_segment_manifest`.

Дополнительно:

- `DocStructureResult.fragment_ids`
- `DocChunkResult.chunk_fragment_ids`

## Связи

- downstream: `fabric.claims`.
- world persistence: `fabric.world.store`.
- доменные модели: `polisyos.ir.world.doc`, `polisyos.ir.citations`.
