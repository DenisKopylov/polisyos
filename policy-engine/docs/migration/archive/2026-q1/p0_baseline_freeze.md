# P0 Baseline & Freeze Plan

## Цель P0

- Зафиксировать измеримый baseline архитектурного долга.
- Заморозить рост долга до начала миграционных фаз.
- Подготовить управляемый backlog для P1+ без массового рефакторинга.

## Границы P0

- В P0 не выполняются массовые переезды модулей.
- В P0 не меняется доменная логика.
- В P0 выполняются только измерение, CI-гейты, правила исключений и приоритизация.

## Исполнение по этапам

1. `D0` Kickoff
- Зафиксированы документы: `p0_baseline_freeze.md`, `p0_dod.md`, `freeze_policy.md`.

2. `D1` Baseline snapshot
- Сняты и сохранены артефакты:
  - `import_gate.txt`
  - `test_collect.txt`
  - `ruff_stats.txt`
  - `summary.json`
  - `baseline_2026-02-10.md`

3. `D2` Freeze в CI (dry-run)
- Добавлен workflow `/.github/workflows/arch-freeze.yml`.
- Добавлен скрипт сравнения baseline: `tools/lint/compare_baseline.py`.
- Dry-run статус публикуется и показывает дельты.
- Dry-run пороги предупреждений:
  - `delta_package_cycles > 0`
  - `delta_import_violations > 0`
  - `delta_test_collect_errors > 0`

4. `D3` Freeze в blocking-режиме
- PR блокируется при росте:
  - `package_cycles_count`
  - `import_violations_count`
  - `test_collect_errors_count`
- PR блокируется при нарушении правил исключений (owner/expires/expiry horizon/expired).

5. `D4` Debt register и приоритизация
- Подготовлены регистры:
  - `import_debt_register.csv`
  - `arch_cycles_register.csv`
  - `p1_refactor_queue.md`

6. `D5` Sign-off
- Подготовлен документ `p0_signoff_2026-02-13.md` с Go/No-Go протоколом.

## Артефакты автоматизации

- Сбор метрик: `tools/lint/collect_arch_metrics.py`
- Сравнение baseline/current: `tools/lint/compare_baseline.py`
- CI freeze pipeline: `/.github/workflows/arch-freeze.yml`

## Статус

- P0 baseline и freeze-гейты внедрены.
- Следующий этап: запуск исполнения очереди P1 из `p1_refactor_queue.md`.
