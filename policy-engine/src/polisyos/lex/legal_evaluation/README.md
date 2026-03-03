# legal_evaluation

`polisyos.lex.legal_evaluation` оценивает соответствие policy/simulation требованиям `NormPack`, формирует юридический отчет и предложения изменений.

## Роль

Подсистема:
- сопоставляет наблюдаемые значения (metrics/policy params) с нормами `NormPack`;
- рассчитывает статусы `PASS/FAIL/UNKNOWN/NOT_APPLICABLE`;
- сохраняет `lex.legal_report` и (при наличии действий) `lex.change_proposal`.

## Входы

- `LegalEvaluationRequest`
- `NormPack` (`kind=lex.norm_pack`)
- `SimulationResult` + `Metrics`
- policy source: `policy_spec_ref` (`model_spec_ref` optional) или `trinity_bundle_ref` (policy/model refs извлекаются во время нормализации request)

## Поток выполнения

```text
normalize request
  -> resolve evaluator (registry)
  -> build LegalContext (policy + simulation + metrics + norm_pack)
  -> evaluate rules (simple_v1 or plugin backend)
  -> persist lex.legal_report
  -> propose_changes_impl
  -> emit EVALUATE_LEGALITY event
```

## Ключевые модули

### `evaluator_registry.py`

- Реестр `LexEvaluatorRegistry`.
- Разрешает `eval_policy_id` как полный `component_id`, так и `base_id` (с выбором latest semver).
- Встроенный evaluator: `lex.eval.simple_v1@1.0.0`.
- Поддержка внешних evaluators через `polisyos.lex_evaluators`.

### `evaluate.py`

Главный оркестратор:
- нормализует request (`jurisdiction`, `as_of`, policy source);
- строит контекст через `LegalContextBuilder`;
- запускает rule evaluation и агрегирует `counts/compliance_grade`;
- сохраняет `lex.legal_report`, затем вызывает `propose_changes_impl`.

### `context_builder.py`

Строит `RuleObservation` для каждой нормы.

Порядок поиска observed value:
- `Metrics.values[predicate_id]`
- `PolicySpec.parameter -> intervention.param_path`
- direct key в `intervention.params`

При проблемах пишет `quality_issues` (`missing_observed_value`, `ambiguous_policy_mapping`, и др.).

### `backends/simple_v1.py`

Базовый backend:
- numeric operators: `<`, `<=`, `=`, `>=`, `>`;
- boolean/text: `=`;
- unit conversion: `percent <-> ratio`, `km <-> m`;
- в `strict=true` неизвестные/неполные случаи чаще переводятся в `FAIL/blocker`.

### `change_proposals.py`

Автогенерация предложений:
- `policy_patch` (`json_patch_v1`, `replace`) для `FAIL` с числовым порогом;
- `add_metric` для `missing_observed_value`.

### `transport_constraints.py`

`LegalConstraintBridge` для transportability:
- извлекает legal constraints по `jurisdiction + policy_domain`;
- учитывает `retroactive`, `transition_period`, `data_license`;
- строит `LegalToDAGMapping` для causal graph;
- helper `is_transport_blocked()` для быстрых HARD-check.

Публичный фасад: `polisyos.lex.api.evaluate_transport_constraints`.

## Выходы

- `lex.legal_report`
- `lex.change_proposal` (может не создаваться, если действий нет)

## Связи

- Потребляет `NormPack` из `policy-engine/src/polisyos/lex/normpack`.
- Использует контракты `polisyos.core.contracts.lex`, `trinity`, `foundry`.
- Пишет semantic facts/events через `polisyos.fabric.world`.
- Может читать legal KG DuckDB для transport constraints.
