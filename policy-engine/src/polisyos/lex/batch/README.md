# Lex Batch

`polisyos.lex.batch` — offline pipeline для построения legal knowledge graph из XML-корпуса ЄДРНПА с режимом `LLM only when irreplaceable`.

## Стадии

`run`:
- `parse` — стриминг XML документов.
- `structure` — выделение provisions/anchors.
- `spo` — deterministic extractors + two-stage LLM gating.
- `graph` — построение DuckDB графа (`lex_entities`, `lex_facts`, `lex_provisions`, `lex_references`, `lex_doc_domains`).

Отдельно:
- `embed-local` — локальные sentence-transformers embeddings + HNSW.
- `qc` — контроль качества, включая метрики gate-аудита.
- `publish` — publish manifest с checksums.
- `stats`, `search`.

## Режимы LLM gate

- `off`: всё non-auto идёт в LLM.
- `balanced` (default): LLM только для сложных provision, остальное auto/deferred.
- `aggressive`: более высокий порог отправки в LLM.

Ключевые флаги:
- `--llm-gate-enabled/--no-llm-gate-enabled`
- `--llm-gate-mode off|balanced|aggressive`
- `--llm-gate-threshold`
- `--llm-gate-max-share`
- `--llm-gate-audit-sample-rate`
- `--llm-gate-audit-max-miss-rate-pct`
- `--extract-references/--no-extract-references`
- `--extract-domains/--no-extract-domains`

## Переменные окружения

```env
GONKA_API_KEY=...
```

Если ключ не задан, `spo` работает в deterministic-only режиме (без LLM вызовов).

## Команды

### Smoke

```bash
python -m polisyos.lex.batch run \
  --cards data/data_lex/edrnpa_cards_2026-02-08.xml \
  --texts data/data_lex/edrnpa_texts_2026-02-08.xml \
  --output-dir data/lex_knowledge \
  --stages parse,structure,spo \
  --spo-extract-mode light \
  --llm-gate-mode balanced \
  --max-docs 1000 \
  --resume
```

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

## Интерпретация аудита

- `audit_miss_rate_pct` показывает, как часто LLM на аудиторной подвыборке находит больше утверждений, чем deterministic route.
- Целевой порог: `<= 3%`.

Если `audit_miss_rate_pct > 3%`:
1. Снизить `--llm-gate-threshold` (например, `0.55 -> 0.45`).
2. Увеличить `--llm-gate-audit-sample-rate` (например, `0.02 -> 0.05`).
3. Перезапустить `spo` с `--resume`.

## Выходные данные

- `provisions/**/*.jsonl` — структурированные фрагменты норм.
- `spo_results/**/*.jsonl` — результаты SPO extraction с provenance (`extraction_source`, `gate_score`, `gate_reason_codes`).
- `references/**/*.jsonl` — детерминированно извлечённые ссылки.
- `domains/**/*.json` — domain scoring по документам.
- `llm_gate_audit.jsonl` — аудит-подвыборка и miss-счёт.
- `manifests/llm_gate.json` — агрегированные метрики gate.
- `lex_knowledge_graph.duckdb` — основной граф.
- `lex_*_embeddings.npz`, `lex_*_index.hnsw` — локальные векторные индексы.
- `qc_report.json` — отчёт качества.
- `publish/manifest.json` — publish manifest.
