# Causal Runtime (`polisyos.scientist.causal`)

`causal` — новый Scientist-пакет для execution/readiness раннеров, которые
обрабатывают observation-plane causal contracts и публикуют transportability,
strategic-response, counterfactual и bounds artifacts.

## Роль в системе

- **Зависит от:** `foundry.methods.catalog.causal`, `ir.observation`, `ir.analytics`
- **Используется в:** `nodes.builtins.causal.run_causal_readiness`,
  `nodes.builtins.causal.run_causal_contract_execution`

- Пакет отделяет orchestration-level nodes от доменно-специализированных causal runners.

## Ключевые концепции

- **Proxy identification** — readiness checks для proxy-based identification bundles.
- **Transportability** — transport proof/status evaluation по selection diagrams.
- **Strategic response** — strategic payoff/SCM solve и publication артефактов.
- **Counterfactual queries** — ID*/IDC* based readiness evaluation.
- **Interference readiness** — family-aware interference loss requirements.
- **Bounds execution** — contract-driven bounds estimation runner для C4b tasks.

## Public API

- `BoundsEstimationRunner`
- `CounterfactualQueryRunner`
- `ProxyIdentificationRunner`
- `StrategicResponseRunner`
- `TransportabilityChecker`
- `build_interference_readiness_entries(...)`

Подробности: [Reference →](../../../../docs/reference/scientist/index.md)

## Текущее состояние

- Последнее обновление: 2026-04-03
- Python modules: 3
- Exports: 6
- README создан для нового пакета, которого раньше не было в модульной документации
