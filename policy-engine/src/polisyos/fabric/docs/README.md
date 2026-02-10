# Docs

`polisyos.fabric.docs` — конвейер обработки документных источников, который готовит артефакты для извлечения claims.

## Pipeline

```text
ingest_doc_bytes -> normalize_doc -> structure_doc -> chunk_doc
```

Каждый шаг обновляет `DocMeta`, создает world event/facts и пишет segment manifest.

## Состав

- `types.py` — `DocSourceSpec`, options/results dataclasses
- `ingestion.py` — прием raw bytes в CAS, генерация `DocMeta`
- `normalize.py` — decode + text normalization + mime-aware extractor
- `structure.py` — построение anchors/sections + `DocFragment`
- `chunking.py` — char/paragraph chunking + `DocFragment`
- `errors.py` — ошибки pipeline (`DocValidationError`, `DocNotReadyError`, ...)
- `backends/` — `text_html`, `text_plain`, `pdf` stubs

## Важные ограничения текущей реализации

- `DocSourceSpec` требует ровно один идентификатор: `canonical_url` или `official_id` или `source_locator`.
- `license` обязателен.
- Нормализация поддерживает `text/plain` и `text/html` в core-режиме.
- PDF backend в текущем ядре не активен: для него нужны optional зависимости/расширение реализации.

## Что возвращают стадии

Все стадии возвращают typed result c:

- `doc_source_id`, `doc_version_id`
- актуальными artifact refs (`raw_ref`/`normalized_ref`/`structure_ref`/`chunks_ref`)
- `doc_meta_artifact_id`
- `world_event_id` + `world_event_artifact_id`
- `world_segment_manifest`

`chunk_doc` дополнительно возвращает `chunk_fragment_ids`.

## Связи

- `claims/` — основной downstream потребитель (`extract_claims_from_doc`)
- `world/store` — эмиссия и персист world-фактов/событий
- `polisyos.ir.world.doc` / `polisyos.ir.citations` — доменные модели документа и локаторов
