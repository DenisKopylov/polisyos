# simulator

`lex.simulator` выполняет what-if анализ изменений `NormPack`.

Подсистема нужна, чтобы оценить последствия юридических изменений до применения в основном pipeline.

## Поток

```text
baseline NormPack
  -> mutate (optional)
  -> diff old/new
  -> run compliance passes on both packs
  -> compute deltas + KPI impact
  -> persist diff/report (optional)
```

## Модули

### `mutator.py`

`NormPackMutator` — fluent API для детерминированных изменений:
- `add_norm`, `remove_norm`, `replace_norm`, `modify_norm`
- `set_effective_date`, `with_metadata`
- `build(intent)` формирует новый `pack_id` из канонического payload.

### `diff.py`

`diff_norm_packs(old, new)` строит `NormDiff`:
- классификация: `added/removed/modified/unchanged`
- field-level deltas для измененных правил
- агрегированные счетчики изменений

### `engine.py`

`NormImpactAnalyzer`:
- запускает governance passes (по умолчанию `legal`, `safety`) для обоих пакетов;
- вычисляет переходы комплаенса (`pass_to_fail`, `resolved_issue`, `severity_change`);
- собирает `NormImpactReport` и может персистить `lex.norm_diff` и `lex.norm_impact_report`.

### `report.py`

Pydantic-модели отчета: `NormImpactReport`, `ComplianceDelta`, `AffectedKPI`.

### `cli.py`

Утилиты для локальной работы:
- загрузка NormPack из CAS или JSON-файла;
- рендер markdown-отчета.

## Связь с другими директориями

- Использует `polisyos.core.governance` passes (`LegalPass`, `SafetyPass`, `ValidationProfile`).
- Работает с моделями `NormPack`/`ComplianceIssue` из `polisyos.ir` и `polisyos.core.contracts.lex`.
- Потребляет `NormPack`, собранный в `policy-engine/src/polisyos/lex/normpack`.
