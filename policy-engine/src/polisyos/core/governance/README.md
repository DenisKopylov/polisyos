# Governance — validation profiles и проходы проверки

`core.governance` задает общий каркас валидации для `lex` и `scientist`:
уровни строгости, контекст выполнения pass'ов и legal/safety проверки.

## Состав

```text
governance/
├── profiles.py              # ValidationProfile + ProfileLevel (fast/mvp/strict)
├── passes/base.py           # PassContext + ValidatorPass абстракции
├── passes/safety_pass.py    # проверка механизмов интервенций по registry bundle
├── passes/legal_pass.py     # legal-pass с backend dispatcher
└── legal/
    ├── ast_policy.py        # whitelist AST policy + resource limits
    └── backends/
        ├── stub.py          # заглушка backend (INFO issues)
        └── expr_ast.py      # безопасный AST evaluator для норм
```

## Роль в системе

- Единая модель профилей валидации (`FAST`, `MVP`, `STRICT`) для разных контуров исполнения.
- Базовый `PassContext` для запуска pass'ов поверх `TrinityBundle`, состояния и registry bundle.
- Общий legal runtime c backend-абстракцией (`stub`, `expr_ast`).

## Validation profiles

`ValidationProfile` управляет:

- набором `pass_ids`;
- числовыми порогами (`thresholds`);
- short-circuit поведением (`short_circuit_on_blocker`).

`STRICT` включает legal/quality/uncertainty/equity-гейты и по умолчанию не short-circuit'ит,
чтобы сохранить полный audit trace.

## Legal backends

- `StubBackend`: безопасная заглушка, возвращает INFO-issues для неимплементированных норм.
- `ExpressionASTBackend`: выполняет выражения `when/must/must_not` через `SafeExpressionEvaluator`.
- `ASTPolicy`: явный whitelist AST-узлов и лимиты сложности (`MAX_NODES`, `MAX_DEPTH`, и т.д.),
  без `eval/exec/compile`.

## Связи с другими директориями

- `lex/`: использует legal pass и `contracts.lex.ComplianceIssue`.
- `scientist/`: использует профили и pass'ы для preflight/governance этапов.
- `registry/`: `SafetyPass` проверяет механизмы на базе собранного registry bundle.
- `backends/`: `LegalPass` использует `BackendDispatcher` для выбора rule backend.

## Публичный API

- `polisyos.core.governance`: `ProfileLevel`, `ValidationProfile`
- `polisyos.core.governance.passes`: `PassContext`, `ValidatorPass`, `SafetyPass`, `LegalPass`
- `polisyos.core.governance.legal.backends`: `RuleBackend`, `StubBackend`, `ExpressionASTBackend`
