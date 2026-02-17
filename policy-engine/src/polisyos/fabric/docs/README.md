# Docs

`polisyos.fabric.docs` — документный конвейер Fabric, который подготавливает CAS-артефакты для extraction/claims и world-проекций.

## Pipeline

```text
ingest_doc_bytes -> normalize_doc -> structure_doc -> chunk_doc
```

Каждая стадия обновляет `DocMeta`, публикует world event и пишет segment manifest.

## Основные модули

- `types.py` — `DocSourceSpec`, options/results dataclasses.
- `ingestion.py` — прием raw bytes, генерация `DocMeta`, запись raw artifact.
- `normalize.py` — decode + mime-aware text normalization.
- `structure.py` — anchors/sections/fragment metadata.
- `chunking.py` — разбиение на chunk fragments (fixed или paragraph boundary).
- `errors.py` — доменные ошибки pipeline.
- `backends/` — `text_plain`, `text_html`, `pdf` (stub backend).

## Ключевые ограничения

- `DocSourceSpec` требует ровно один идентификатор из: `canonical_url`, `official_id`, `source_locator`.
- `license` обязателен.
- Core-реализация нормализации поддерживает `text/plain` и `text/html`.
- `pdf` backend в текущем пакете остается заглушкой и требует расширений/optional deps.

## Что возвращают стадии

Все result-модели (`DocIngestResult`, `DocNormalizeResult`, `DocStructureResult`, `DocChunkResult`) содержат:

- `doc_source_id`, `doc_version_id`,
- актуальные artifact refs (`raw_ref`, `normalized_ref`, `structure_ref`, `chunks_ref`),
- `doc_meta_artifact_id`,
- `world_event_id`, `world_event_artifact_id`,
- `world_segment_manifest`.

Дополнительно:

- `DocStructureResult.fragment_ids` — фрагменты структуры.
- `DocChunkResult.chunk_fragment_ids` — итоговые chunk fragments.

## Связи

- `fabric.claims` — downstream extraction (`extract_claims_from_doc`).
- `fabric.world.store` — эмиссия/персист world-фактов и событий.
- `polisyos.ir.world.doc` и `polisyos.ir.citations` — доменные модели документов и локаторов.
