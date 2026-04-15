# Definition of Done: P0 Baseline & Freeze

## DoD P0

1. Baseline зафиксирован
- Есть `summary.json` как единый источник правды метрик.
- Есть полный набор D1-артефактов (`import_gate.txt`, `test_collect.txt`, `ruff_stats.txt`, `baseline_2026-02-10.md`).

2. Freeze-гейты в CI активны
- Workflow `/.github/workflows/arch-freeze.yml` выполняет сбор current-метрик.
- `dry-run` режим публикует дельты к baseline.
- `blocking` режим для PR запрещает регресс архитектурных метрик.

3. Exceptions управляемы
- Используются `import_exceptions.toml` и `import_exceptions_registry.md`.
- Каждое исключение обязано иметь `id`, `owner`, `reason`, `expires`.
- `expires` не дальше чем на 90 дней.
- Просроченные исключения блокируют PR.

4. Долг структурирован
- Сформированы `import_debt_register.csv` и `arch_cycles_register.csv`.
- Подготовлена приоритизированная очередь `p1_refactor_queue.md`.

5. Sign-off готов
- Есть `p0_signoff_2026-02-13.md` с явным Go/No-Go протоколом.

## Результат DoD

- CI гарантирует no-regression по архитектурным метрикам.
- Архитектурный долг представлен как управляемый backlog, а не неструктурированный шум.
- Команда может безопасно переходить к P1 миграциям.
