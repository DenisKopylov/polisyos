# Freeze Policy v2 (P1 Import Policy v2 aligned)

## Назначение

Freeze-политика фиксирует текущее состояние архитектурного долга и запрещает его рост до окончания P1. Для импорта действует `Import Policy v2`.

## Правила

1. Запрещен рост количества package cycles.
2. Запрещен рост количества import violations.
3. Наличие unmanaged import violations (`import_violations_count > 0`) запрещено в P1 Import Policy v2.
4. Новые исключения разрешены только если заполнены:

   - `id`
   - `owner`
   - `reason`
   - `expires`

5. `expires` не должен быть дальше, чем на 90 дней от даты PR-проверки.
6. Просроченные исключения запрещены.
7. Для новых изменений запрещены deep-import в чужие internal/private модули.
8. Все активные import исключения должны быть отражены в `architecture/imports/exceptions.md` и привязаны к P1 backlog.

## Enforcement

- Метрики снимаются скриптом `tools/quality/lint/collect_arch_metrics.py`.
- Сравнение baseline/current делает `tools/quality/lint/compare_baseline.py`.
- CI workflow: `/.github/workflows/arch-freeze.yml`.
- Для `pull_request` включен blocking-режим.
- Deep-import freeze (`ARCH004/ARCH006`) проверяется по diff baseline/current `import_gate.txt`.

## Политика исключений

- Реестр исключений: `architecture/imports/exceptions.md`.
- Технический источник: `architecture/imports/exceptions.toml`.
- Каждое исключение должно иметь owner и дату истечения.
- Просроченные или некорректные исключения блокируют merge.
