# Lex Batch

`polisyos.lex.batch` — offline pipeline построения legal knowledge graph из XML-корпуса (ЄДРНПА) с маршрутизацией `deterministic-first + LLM only when irreplaceable`.

## Роль в системе

Подсистема готовит данные для `polisyos.lex.knowledge`:
- парсит карточки и тексты НПА;
- выделяет provisions и структурированные утверждения (SPO);
- собирает DuckDB-граф и опциональные векторные индексы.

## Стадии

`run`:
- `parse` — streaming XML parsing.
- `structure` — извлечение provisions/anchor path.
- `spo` — template/rule/deterministic extraction + LLM gate + audit.
- `graph` — сборка `lex_knowledge_graph.duckdb`.

Отдельные команды:
- `smoke` — быстрый локальный acceptance/smoke прогон с выборкой репрезентативных НПА.
- `embed-local` — локальные embeddings + HNSW.
- `qc` — quality checks для графа и SPO-покрытия.
- `publish` — publish manifest с checksums.
- `stats`, `search` — операционный просмотр результатов.

## Ключевые особенности текущего пайплайна

- Детерминированные enrichments: references и domain classification (включаются/выключаются флагами).
- Template extraction для типовых документов до per-provision обработки.
- Dedup provisions по `text_hash` с `extraction_source=dedup_clone`.
- LLM gate с audit-выборкой и circuit breaker.
- Quality gates на уровне run (можно включить hard-fail через `--quality-fail-on-critical`).

## Режимы LLM gate

- `off` — отправка non-auto кандидатов в LLM при доступном клиенте.
- `balanced` (default) — компромисс между качеством и стоимостью.
- `aggressive` — более экономный маршрут, чаще deterministic/deferred.

Ключевые флаги:
- `--llm-gate-enabled/--no-llm-gate-enabled`
- `--llm-gate-mode off|balanced|aggressive`
- `--llm-gate-threshold`
- `--llm-gate-max-share`
- `--llm-gate-audit-sample-rate`
- `--llm-gate-audit-max-miss-rate-pct`
- `--spo-verify-mode llm|code`
- `--extract-references/--no-extract-references`
- `--extract-domains/--no-extract-domains`

## Шардинг

Поддерживаются `--shard-count` и `--shard-index` для `parse/structure/spo`.

Ограничение: в sharded-режиме stage `graph` не запускается (граф собирается отдельным single-process проходом).

## Переменные окружения

```env
GONKA_API_KEY=...
```

Если ключ не задан, LLM-недоступные маршруты переходят в deterministic/deferred режим.

## Команды

### Smoke

```bash
python -m polisyos.lex.batch smoke \
  --cards data/data_lex/edrnpa_cards_2026-02-08.xml \
  --texts data/data_lex/edrnpa_texts_2026-02-08.xml \
  --output-dir data/lex_knowledge \
  --profile informative \
  --clean-output
```

Smoke-команда:
- сканирует первые matched documents и собирает стратифицированную выборку по `doc_type` и structural cues (`appendix/table/list/article`);
- запускает все product stages до `publish_bundle` без embeddings;
- пишет `smoke/smoke_plan.json`, `smoke/smoke_report.json`, `smoke/smoke_summary.md`.

### Full

```bash
python -m polisyos.lex.batch run \
  --cards data/data_lex/edrnpa_cards_2026-02-08.xml \
  --texts data/data_lex/edrnpa_texts_2026-02-08.xml \
  --output-dir data/lex_knowledge \
  --stages parse,structure,spo,graph \
  --spo-extract-mode light \
  --llm-gate-mode balanced \
  --quality-fail-on-critical \
  --resume
```

### Embeddings + QC + Publish

```bash
python -m polisyos.lex.batch embed-local --output-dir data/lex_knowledge --thermal
python -m polisyos.lex.batch qc --output-dir data/lex_knowledge --fail-fast
python -m polisyos.lex.batch publish --output-dir data/lex_knowledge
```

## Выходные артефакты

- `provisions/**/*.jsonl`
- `spo_results/**/*.jsonl`
- `references/**/*.jsonl`
- `domains/**/*.json`
- `llm_gate_audit.jsonl`
- `manifests/llm_gate.json`
- `lex_knowledge_graph.duckdb`
- `lex_*_embeddings.npz`, `lex_*_index.hnsw`
- `qc_report.json`
- `publish/manifest.json`
