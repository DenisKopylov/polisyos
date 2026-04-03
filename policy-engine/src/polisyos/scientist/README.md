# Scientist (`polisyos.scientist`)

`scientist` — orchestration-слой PolicyOS, который собирает workflow, запускает
policy-эксперименты, управляет governance/human-gate контуром и публикует
воспроизводимый результат поверх `ir`, `foundry`, `fabric`, `lex`, `scholar`
и `core`.

## Роль в системе

- **Зависит от:** `core`, `ir`, `foundry`, `fabric`, `lex`, `scholar`
- **Используется в:** CLI, runtime control/debug flows, replay tooling, policy-design flows
- `scientist` не реализует доменную математику сам: он оркестрирует state, nodes,
  adapters, governance и публикацию итогового decision surface.

## Ключевые концепции

- **WorkflowSpec + NodeRegistry** — канонический способ собрать исполнимый DAG.
- **ExperimentState** — строгий run-state с checkpoint/resume и trace-friendly индексами.
- **Builtin nodes** — стандартные data/planning/compile/causal/simulate/governance/decide этапы.
- **Causal readiness/execution** — новый контур readiness-проверок и contract execution
  для proxy, transportability, strategic response и counterfactual задач.
- **Governance runtime** — validation passes, human gate, calibration/backtest/stress readouts.
- **Optional surfaces** — `agent`, `search`, `policy_design`, `backtesting`, `orchestrator`.

## Public API

- `run_experiment(...)` — стандартный entrypoint Scientist.
- `ExperimentState` — основной state-контракт workflow-раннера.
- `workflows.*` — запуск и выбор `scientist_default`, `scientist_causal_full`,
  `scientist_discovery`, `scientist_policy_design`.
- `engine.*` — executor, registry, checkpoint, idempotency и runner backends.
- `governance.*` — pre/post-flight API и calibration/stress/backtest readouts.
- `causal.*` — runners для readiness и bounds execution.

Подробности: [Reference →](../../../docs/reference/scientist/index.md)

## Where to Start

- Public facade / compatibility: `src/polisyos/scientist/__init__.py` and `docs/reference/public-surface.md`
- Workflow assembly: `src/polisyos/scientist/workflows/` and `src/polisyos/scientist/engine/`
- Governance changes: `src/polisyos/scientist/governance/README.md` and `docs/how-to/write-governance-pass.md`
- New governance pass scaffold: `python3 tools/architecture/scaffold.py governance-pass --name my_pass --output ... --test-output ... --dry-run`

## Текущее состояние

- Последнее обновление: 2026-04-03
- Python modules: 401
- Root exports: 4 (`ExperimentState`, `get_metrics`, `get_tracer`, `run_experiment`)
- Крупные недавние изменения: новый `causal/`, расширение `governance/`,
  новые builtin causal nodes и C6c policy-design path
