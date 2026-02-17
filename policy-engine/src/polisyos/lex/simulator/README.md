# simulator

`polisyos.lex.simulator` выполняет what-if анализ изменений `NormPack` до применения в основном pipeline.

## Поток

```text
baseline NormPack
  -> (optional) mutate
  -> diff_norm_packs(old, new)
  -> run governance passes for old/new
  -> compute compliance transitions + affected KPI
  -> (optional) persist lex.norm_diff + lex.norm_impact_report
```

## Ключевые модули

### `mutator.py`

`NormPackMutator`:
- детерминированные операции: `add_norm`, `remove_norm`, `replace_norm`, `modify_norm`;
- вспомогательные изменения: `set_effective_date`, `with_metadata`;
- `build(intent)` формирует новый `pack_id` на основе canonical payload и истории операций.

### `diff.py`

`diff_norm_packs(old_pack, new_pack)`:
- классифицирует нормы: `added`, `removed`, `modified`, `unchanged`;
- строит field-level `FieldDelta` для измененных правил;
- возвращает агрегированные счетчики и список затронутых `norm_id`.

### `engine.py`

`NormImpactAnalyzer`:
- запускает validation passes (по умолчанию `legal`, `safety`);
- считает переходы: `pass_to_fail`, `fail_to_pass`, `new_issue`, `resolved_issue`, `severity_change`;
- агрегирует blocker/warning deltas;
- выводит `NormImpactReport`;
- при `persist=True` пишет `lex.norm_diff` и `lex.norm_impact_report` в CAS.

### `report.py`

Модели отчета:
- `NormImpactReport`
- `ComplianceDelta`
- `AffectedKPI`

### `cli.py`

CLI helper-функции:
- загрузка `NormPack` из CAS или JSON;
- рендер markdown-версии impact report.

## Связи с другими директориями

- Использует `polisyos.core.governance` (`LegalPass`, `SafetyPass`, `ValidationProfile`).
- Работает с `NormPack` из `polisyos.ir.norm_pack` и `ComplianceIssue` из `polisyos.core.contracts.lex`.
- Обычно получает `NormPack` из `policy-engine/src/polisyos/lex/normpack`.
