# legal_evaluation

Оценка соответствия действий юридическим нормам и генерация предложений по изменениям.

## Архитектура

```
LegalEvaluationRequest
        │
  evaluator_registry.resolve(eval_policy_id)
        │
  evaluate_legality_impl()
        ├── LegalContextBuilder.build()
        │     ├── load PolicySpec, SimulationResult, Metrics, NormPack
        │     └── map observed values → RuleObservation per rule
        ├── evaluate_rule_simple_v1() per rule
        │     └── numeric / boolean / text comparison → RuleFinding
        ├── persist LegalReport → LegalReportRef
        └── propose_changes_impl()
              └── FAIL findings → ChangeProposalRef
```

## Модули

### evaluator_registry.py

Глобальный реестр оценщиков легальности:

- `LexEvaluatorRegistry` — хранит `EvaluatorRecord` по component_id и base_id
- `resolve(eval_policy_id)` — поиск сначала по точному id, затем по base_id (latest version)
- Встроенный: `lex.eval.simple_v1@1.0.0`
- Расширение: entry points `polisyos.lex_evaluators`, bootstrap через `discover_and_bootstrap_evaluators()`
- Поддерживает callable и объекты с методом `evaluate()`

### evaluate.py

Основная логика оценки (`evaluate_legality_impl`):

1. Нормализация запроса: валидация юрисдикции, as_of, norm_pack_ref, eval_policy_id
2. Разрешение Trinity bundle → PolicySpecRef + ModelSpecRef (inline или через CAS)
3. Построение контекста через `LegalContextBuilder`
4. Итерация по правилам NormPack: `evaluate_rule_simple_v1()` для каждого
5. Агрегация findings → summary (counts + compliance_grade: pass/partial/fail)
6. Персистенция отчёта (`lex.legal_report`), запись WorldEvent `EVALUATE_LEGALITY`

### context_builder.py

`LegalContextBuilder` — подготовка данных для оценки:

- Загружает из CAS: PolicySpec, SimulationResult, Metrics, NormPack
- Для каждого правила строит `RuleObservation` с маппингом наблюдаемого значения:
  1. **metrics** — прямой lookup по predicate_id в Metrics.values
  2. **parameter_spec** — через ParameterSpec: intervention_id → param_path → value
  3. **direct_key** — predicate_id как ключ в intervention.params
- Поддерживает типы: numeric (Decimal), boolean, text

### change_proposals.py

Генерация предложений по изменениям на основе отчёта оценки:

**`policy_patch`** — для FAIL findings с числовым threshold:
- Находит policy_json_pointer из evidence_refs
- Генерирует JSON Patch `replace` с рассчитанным значением (учитывает оператор: `<` → threshold - epsilon)

**`add_metric`** — для `missing_observed_value` quality issues:
- Предлагает добавить инструментацию для недостающей метрики
- Определяет metric_type (numeric/boolean/text) по expected

### backends/simple_v1.py

Rule evaluator v1:

- Числовые сравнения: `<`, `<=`, `=`, `>=`, `>` с Decimal precision
- Конвертация единиц: percent↔ratio, km↔m
- Boolean: exact match (true/false) через оператор `=`
- Text: casefold + whitespace-normalized comparison через `=`
- Severity: `info` (PASS/NOT_APPLICABLE), `warning` (UNKNOWN non-strict), `blocker` (FAIL, UNKNOWN strict)

## Зависимости

- `normpack.applicability` — проверка applies_to_context для правил
- `core.contracts.lex` — LegalEvaluationRequest, LegalReportRef, ChangeProposalRef
- `core.contracts.trinity` — PolicySpecRef, ModelSpecRef
- `core.contracts.foundry` — SimulationResult, Metrics
- `core.components` — entry point discovery для плагинов оценщиков
- `ir.norm_pack` — NormPack, NormRule
- `ir.policy_spec` — PolicySpec, ParameterSpec
- `fabric.world` — персистенция событий и фактов
