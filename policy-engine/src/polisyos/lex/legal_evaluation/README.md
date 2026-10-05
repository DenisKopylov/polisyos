# Legal Evaluation (`polisyos.lex.legal_evaluation`)

`polisyos.lex.legal_evaluation` сравнивает policy/simulation output с `NormPack`,
строит `lex.legal_report`, формирует change proposals и публикует bridge-слой
между юридическими ограничениями и causal transportability constraints.

## Роль в системе

- **Зависит от:** `polisyos.lex.normpack`, `polisyos.core.contracts.lex`, `polisyos.ir`, `polisyos.fabric.world`
- **Используется в:** policy validation, governance passes, transportability gating, change-proposal flows
- Пакет превращает нормы и observed values в explicit compliance verdicts вместо ad-hoc post-hoc reasoning.

## Ключевые концепции

- **Evaluator registry** — `LexEvaluatorRegistry` поднимает built-in и внешние evaluators по `eval_policy_id`.
- **Context normalization** — `evaluate_legality_impl()` извлекает policy source, metrics и norm context в единый `LegalContext`.
- **Rule observations** — `context_builder.py` резолвит observed values из metrics и policy parameters с явными `quality_issues`.
- **Change proposals** — `propose_changes_impl()` генерирует `policy_patch` или `add_metric` actions для actionable failures.
- **Transport constraints** — `LegalConstraintBridge` и `is_transport_blocked()` связывают legal limits с causal graph/transportability checks.
- **Norm comparison** — `impact_diff.NormImpactAnalyzer` сравнивает два `NormPack`,
  запускает выбранные built-in `legal`/`safety` passes и сохраняет diff/report в CAS.
  Нормы для каждого запуска берутся из сравниваемого pack; одноимённый ключ в
  дополнительном context их не подменяет. `passes=None` выбирает оба pass,
  `passes=()` оставляет только norm diff; неизвестные pass IDs отклоняются.
  Историческое поле `affected_kpis` схемы `1.0` содержит candidate impact topics,
  без измеренной величины или установленного направления эффекта. Старые
  `polisyos.lex.simulator` импорты и CLI используют этот же canonical owner.

## Public API

| Type/Function                                  | Description                                                      |
| ---------------------------------------------- | ---------------------------------------------------------------- |
| `evaluate_legality_impl()`                     | Main legality evaluation orchestrator                            |
| `propose_changes_impl()`                       | Generate change proposals from evaluation failures               |
| `LegalConstraintBridge`                        | Resolve legal constraints for transportability and causal checks |
| `LegalConstraint`, `LegalConstraintSet`        | Typed legal-constraint models                                    |
| `LegalToDAGMapping`, `LegalToDAGMappingType`   | Mapping contracts from legal constraints to DAG semantics        |
| `ConstraintSeverity`, `is_transport_blocked()` | Severity and fast hard-block helpers                             |

Full reference: [docs/reference/lex/](../../../../docs/reference/lex/index.md)

## Current State

- Last updated: 2026-04-03
- Files: 8 Python files
- Exports: 9 symbols in `__init__.py`
- Notable delta: transport-constraint bridge remains a first-class part of the package surface, not just an internal helper
