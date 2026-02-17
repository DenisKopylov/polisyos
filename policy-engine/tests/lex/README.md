# Lex Tests

`tests/lex` покрывает `polisyos.lex` в двух контурах: batch pipeline (структурирование/нормализация/качество) и simulator (diff/mutator/impact).

Актуально на **17 февраля 2026**.

## Состав

- `9` файлов `test_*.py`

## Структура

| Подкаталог | `test_*.py` | Что покрывает |
|---|---:|---|
| `lex/batch/` | 6 | canonicalizers, structurer, SPO normalization, quality report, sharding |
| `lex/simulator/` | 3 | norm pack diff, mutation semantics, impact analyzer |

## Ключевые инварианты

- Стабильная нормализация action/norm-type и извлечение thresholds.
- Корректная shard-изоляция (`progress.jsonl`, shard DB paths, doc assignment uniqueness).
- Детерминизм mutator/diff в simulator-контуре.

## Связи с кодом

- `policy-engine/src/polisyos/lex/batch`
- `policy-engine/src/polisyos/lex/simulator`
- `policy-engine/src/polisyos/lex/knowledge`
- `policy-engine/src/polisyos/ir/norm_pack`

## Запуск

```bash
pytest tests/lex -q
pytest tests/lex/batch -q
pytest tests/lex/simulator -q
```
