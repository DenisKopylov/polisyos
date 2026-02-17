# legal_evaluation

`polisyos.lex.legal_evaluation` оценивает соответствие policy/simulation требованиям `NormPack` и формирует юридический отчет.

## Входы

- `LegalEvaluationRequest`
- `NormPack` (`kind=lex.norm_pack`)
- `SimulationResult` + `Metrics`
- `PolicySpec`/`ModelSpec`:
  - либо через `policy_spec_ref` (`model_spec_ref` optional);
  - либо через `trinity_bundle_ref` (внутри request нормализации).

## Поток выполнения

```text
normalize request
  -> resolve evaluator from registry
  -> build LegalContext (policy + simulation + metrics + norm_pack)
  -> evaluate each rule (simple_v1 or plugin backend)
  -> persist lex.legal_report
  -> generate lex.change_proposal (optional)
  -> emit EVALUATE_LEGALITY world event
```

## Ключевые модули

### `evaluator_registry.py`

- Реестр `LexEvaluatorRegistry`.
- Встроенный evaluator: `lex.eval.simple_v1@1.0.0`.
- Поддержка внешних evaluator-компонентов через `polisyos.lex_evaluators`.

### `evaluate.py`

Главный оркестратор:
- нормализует request (`jurisdiction`, `as_of`, `eval_policy_id`);
- загружает policy refs из `trinity_bundle_ref`, если нужно;
- запускает оценку по нормам;
- агрегирует `counts` и `compliance_grade`;
- сохраняет `lex.legal_report` и вызывает `propose_changes_impl`.

### `context_builder.py`

Строит `RuleObservation` для каждой нормы. Порядок поиска observed value:
1. `Metrics.values[predicate_id]`
2. `PolicySpec.parameter -> intervention.param_path`
3. direct key в `intervention.params`

Если маппинг отсутствует/неоднозначен, пишет `quality_issues` (`missing_observed_value`, `ambiguous_policy_mapping`, и др.).

### `backends/simple_v1.py`

Базовый evaluator:
- числовые операторы: `<`, `<=`, `=`, `>=`, `>`;
- boolean/text: `=`;
- unit conversion: `percent <-> ratio`, `km <-> m`;
- статусы: `PASS`, `FAIL`, `UNKNOWN`, `NOT_APPLICABLE`;
- в `strict=true` неизвестные/неполные случаи трактуются жестче.

### `change_proposals.py`

Автогенерация предложений:
- `policy_patch` (JSON Patch `replace`) для `FAIL` с числовым threshold;
- `add_metric` для `missing_observed_value`.

## Выходы

- `lex.legal_report`
- `lex.change_proposal` (может быть пустым списком)

## Связи с другими директориями

- Потребляет `NormPack` из `policy-engine/src/polisyos/lex/normpack`.
- Использует контракты `polisyos.core.contracts.lex`, `trinity`, `foundry`.
- Пишет semantic facts/events через `polisyos.fabric.world`.
