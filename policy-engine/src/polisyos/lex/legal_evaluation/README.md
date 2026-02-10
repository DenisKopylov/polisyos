# legal_evaluation

`lex.legal_evaluation` проверяет соответствие симуляции и политики нормам из `NormPack` и формирует юридический отчёт.

## Что получает на вход

- `LegalEvaluationRequest`
- `PolicySpec` (напрямую или через `trinity_bundle_ref`)
- `SimulationResult` + `Metrics`
- `NormPack`

Все входы загружаются из CAS и валидируются до старта оценки.

## Поток выполнения

```text
normalize request
  -> resolve evaluator (registry)
  -> build LegalContext
  -> evaluate each NormRule
  -> persist lex.legal_report
  -> auto-generate lex.change_proposal
  -> emit EVALUATE_LEGALITY world event
```

## Ключевые модули

### `evaluator_registry.py`

- Глобальный реестр `LexEvaluatorRegistry`.
- Встроенный backend: `lex.eval.simple_v1@1.0.0`.
- Поддержка плагинов через entry points `polisyos.lex_evaluators`.

### `evaluate.py`

Оркестратор end-to-end:
- нормализация запроса (`jurisdiction`, `as_of`, `eval_policy_id`, источники policy refs);
- построение контекста;
- rule-by-rule оценка;
- агрегация `summary/counts/compliance_grade`;
- персистенция `lex.legal_report` и запуск генерации proposals.

### `context_builder.py`

Строит `RuleObservation` для каждой нормы.

Порядок маппинга наблюдаемого значения:
1. `Metrics.values[predicate_id]`
2. `PolicySpec.parameter -> intervention.param_path`
3. direct key в `intervention.params`

Если значение не найдено/неоднозначно, добавляет `quality_issues` (например `missing_observed_value`, `ambiguous_policy_mapping`).

### `backends/simple_v1.py`

Базовый rule evaluator:
- операторы: `<`, `<=`, `=`, `>=`, `>` (numeric), `=` (boolean/text);
- поддержка unit conversion: `percent<->ratio`, `km<->m`;
- статусы: `PASS`, `FAIL`, `UNKNOWN`, `NOT_APPLICABLE`;
- severity зависит от `strict`.

### `change_proposals.py`

Генерирует предложения на основе отчёта:
- `policy_patch` (JSON Patch `replace`) для числовых FAIL-правил;
- `add_metric` для недостающих наблюдений.

## Выходы

- `LegalReportRef` (`lex.legal_report`)
- `list[ChangeProposalRef]` (`lex.change_proposal`)

## Связь с другими директориями

- Потребляет `NormPack` из `policy-engine/src/polisyos/lex/normpack`.
- Использует контракты из `polisyos.core.contracts.lex/trinity/foundry`.
- Пишет provenance в fact log через `polisyos.fabric.world`.
