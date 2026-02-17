# Lex Batch

`polisyos.lex.batch` — offline pipeline для построения legal knowledge graph из XML-корпуса ЄДРНПА.

## Что делает

Стадии `run`:
- `parse` — стриминг XML документов;
- `structure` — выделение provisions/anchors;
- `spo` — LLM extraction норм в формате SPO;
- `graph` — построение DuckDB графа (`lex_entities`, `lex_facts`, `lex_provisions`, ...);
- `embed` — submit embedding batches (OpenAI Batch API).

Отдельные команды:
- `embed-batch submit` / `embed-batch collect`;
- `stats`;
- `search`.

## Переменные окружения

```env
GONKA_API_KEY=...   # нужен для stage=spo
OPENAI_API_KEY=...  # нужен для embed-batch / stage=embed
```

## Базовые сценарии

### 1) Полный проход до графа

```bash
python -m polisyos.lex.batch run \
  --cards data/data_lex/edrnpa_cards_2026-02-08.xml \
  --texts data/data_lex/edrnpa_texts_2026-02-08.xml \
  --output-dir data/lex_knowledge \
  --stages parse,structure,spo,graph \
  --resume
```

### 2) Шардированный прогон (только parse/structure/spo)

```bash
python -m polisyos.lex.batch run \
  --cards data/data_lex/edrnpa_cards_2026-02-08.xml \
  --texts data/data_lex/edrnpa_texts_2026-02-08.xml \
  --output-dir data/lex_knowledge \
  --shard-count 5 \
  --shard-index 0 \
  --stages parse,structure,spo \
  --resume
```

Важно: в sharded mode запрещены `graph` и `embed`; финализация запускается отдельным single-process прогоном.

### 3) Embedding batch workflow

```bash
python -m polisyos.lex.batch embed-batch submit \
  --output-dir data/lex_knowledge \
  --model text-embedding-3-large
```

```bash
python -m polisyos.lex.batch embed-batch collect \
  --output-dir data/lex_knowledge \
  --wait
```

### 4) Быстрая проверка результата

```bash
python -m polisyos.lex.batch stats --output-dir data/lex_knowledge
python -m polisyos.lex.batch search --output-dir data/lex_knowledge --query "бюджетний дефіцит"
```

## Выходные данные

- `provisions/**/*.jsonl` — структурированные фрагменты норм;
- `spo_results/**/*.jsonl` — результаты SPO extraction;
- `lex_knowledge_graph.duckdb` — основной граф;
- `progress.jsonl` / `manifest.jsonl` — checkpoint и манифест прогресса;
- `openai_batches/` — request/response/manifest файлы Batch API;
- `lex_*_embeddings.npz`, `lex_*_index.hnsw` — векторные индексы для `lex.knowledge`.

## Качество и устойчивость

- Quality gates по умолчанию warn-only; для fail-fast используйте `--quality-fail-on-critical`.
- При проблемах с JSON mode у провайдера: `--gonka-disable-json-mode`.
- Для более дешевого/стабильного SPO verify: `--spo-verify-mode code`.
- Для инкрементальных прогонов: `--resume` и `--max-docs`.

## Связь с другими директориями

- Пишет форматы, которые читает `policy-engine/src/polisyos/lex/knowledge`.
- Использует типы `policy-engine/src/polisyos/lex/knowledge/types.py`.
