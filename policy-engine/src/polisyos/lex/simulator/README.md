# simulator

`polisyos.lex.simulator` выполняет what-if анализ изменений `NormPack` до применения изменений в основном pipeline.

## Роль

Подсистема отвечает за:
- детерминированную мутацию baseline `NormPack`;
- diff между версиями набора норм;
- оценку влияния изменений через governance passes.

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
- операции `add_norm`, `remove_norm`, `replace_norm`, `modify_norm`;
- вспомогательные операции `set_effective_date`, `with_metadata`;
- `build(intent)` формирует новый детерминированный `pack_id` и пишет mutation trace в metadata.

### `diff.py`

`diff_norm_packs(old_pack, new_pack)`:
- классифицирует изменения (`added`, `removed`, `modified`, `unchanged`);
- строит field-level deltas для модифицированных норм;
- возвращает агрегированные счетчики и `affected_norm_ids`.

### `engine.py`

`NormImpactAnalyzer`:
- по умолчанию запускает passes `legal`, `safety`;
- вычисляет переходы `pass_to_fail`, `fail_to_pass`, `new_issue`, `resolved_issue`, `severity_change`;
- агрегирует blocker/warning deltas;
- формирует `NormImpactReport` и при `persist=True` сохраняет `lex.norm_diff` и `lex.norm_impact_report`.

### `report.py`

Модели отчета:
- `NormImpactReport`
- `ComplianceDelta`
- `AffectedKPI`

### `cli.py`

Утилиты:
- загрузка `NormPack` из CAS или JSON;
- markdown-рендер impact report.

## Связи

- Использует `polisyos.core.governance` (`LegalPass`, `SafetyPass`, `ValidationProfile`).
- Работает с `NormPack` (`polisyos.ir.norm_pack`) и `ComplianceIssue` (`polisyos.core.contracts.lex`).
- Типичный upstream: `policy-engine/src/polisyos/lex/normpack`.
