# Governance — профили и валидационные pass'ы

`core.governance` задает общий каркас проверки для `scientist` и `lex`: профиль строгости, контекст pass execution и legal/safety проверки.

## Состав

```text
governance/
├── profiles.py            # ValidationProfile + ProfileLevel (fast/mvp/strict)
├── passes/base.py         # PassContext + ValidatorPass
├── passes/safety_pass.py  # проверка механизмов интервенции
├── passes/legal_pass.py   # legal pass с backend dispatcher
└── legal/
    ├── ast_policy.py      # whitelist AST policy
    └── backends/
        ├── stub.py        # безопасный placeholder backend
        └── expr_ast.py    # AST-based expression evaluator
```

## ValidationProfile

`ValidationProfile` управляет:
- `pass_ids` (какие проверки запускать)
- `thresholds` (числовые пороги)
- `short_circuit_on_blocker`

Профили:
- `FAST`: быстрые preflight-checks
- `MVP`: стандартный runtime набор
- `STRICT`: полный набор (включая legal/quality/human-review) без short-circuit по умолчанию

## Pass execution

`PassContext` содержит:
- `ir` (`TrinityBundle`)
- `state` (budget/usage/служебные данные)
- `registry_bundle`
- `profile`
- `run_id`

Любой pass реализует `ValidatorPass.validate(ctx) -> list[ComplianceIssue]`.

## Legal backend слой

`LegalPass` поддерживает backend режимы:
- `stub` — always-safe заглушка
- `expr_ast` — ограниченный AST evaluator (без `eval/exec`)

По умолчанию legal-pass выполняется в `STRICT` профиле (или при явном включении).

## Связи

- `lex`: `ComplianceIssue`, legal norm evaluation
- `scientist`: governance/preflight orchestration
- `registry`: source для safety validation по механизмам
- `backends`: generic `BackendDispatcher` для backend resolution
