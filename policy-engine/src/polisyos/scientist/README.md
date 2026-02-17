# Scientist (`polisyos.scientist`)

`scientist` — orchestration-слой Policy Engine для запуска и воспроизводимого выполнения policy-экспериментов поверх `ir`, `foundry`, `fabric`, `lex`, `scholar` и `core`.

Документ отражает текущее состояние кода на **2026-02-17**.

## Роль в системе

`scientist` отвечает за:
- запуск workflow эксперимента;
- координацию data/plan/compile/simulate/governance шагов;
- сбор итогового `DecisionPacket`;
- воспроизводимость запуска (idempotency cache, checkpoints, replay backend).

`scientist` не отвечает за:
- доменную симуляцию как таковую (`foundry`);
- загрузку/хранение первичных данных (`fabric`);
- канонические контракты/схемы IR (`ir`);
- доменную юридическую интерпретацию (`lex`).

## Основные точки входа

- `polisyos.scientist.run_experiment(state=None)`
- `polisyos.scientist.workflows.builder.run_default_workflow(initial_state, ...)`

`run_experiment()`:
- валидирует вход по `ExperimentState` (`extra="forbid"`);
- генерирует `run_id`, если пустой;
- запускает `scientist_default` workflow;
- возвращает финальный `ExperimentState` как `dict`.

Важно: для mapping-входа отклоняются неизвестные top-level ключи.

## Default Workflow (актуальный DAG)

Spec: `workflows/default.py`.

```text
start (noop)
├─ build_data_snapshot
│  └─ bind_foundry_inputs
│     └─ run_data_plane_gate
├─ build_execution_plan
│  └─ build_method_catalog_snapshot
│     └─ run_preflight
│        └─ ready_to_run
└─ link_trinity

compile_foundry (depends on: link_trinity + run_data_plane_gate + ready_to_run)
├─ run_simulation
│  ├─ run_distributional_analysis
│  └─ propagate_uncertainty
│     └─ run_governance
│        └─ run_evaluator
└─ run_causal_evaluation (depends on build_data_snapshot)

build_decision_packet (depends on: run_governance + run_causal_evaluation + run_evaluator)
```

Ключевые особенности текущего DAG:
- `error_policy="continue"` (независимые ветки продолжают работу; зависимые ноды skip при upstream failure);
- preflight pipeline (`build_execution_plan -> build_method_catalog_snapshot -> run_preflight -> ready_to_run`) обязателен перед compile;
- `run_evaluator` включен в default путь и участвует в финальном `build_decision_packet`.

## Минимальный входной контракт

`ExperimentState` (см. `engine/state.py`) требует:
- обязательно: `inputs.trinity_bundle_ref`;
- источник данных: как минимум один из
  - `inputs.data_snapshot_ref`,
  - `inputs.input_bindings_ref`,
  - `inputs.data_view_request_ref`.

`inputs.registry_bundle_ref` можно не передавать: `run_default_workflow()` создаст его автоматически.

Пример минимального payload:

```python
state = {
    "run_id": "",
    "inputs": {
        "trinity_bundle_ref": {
            "artifact_id": "sha256:...",
            "kind": "ir.trinity_bundle",
            "media_type": "application/json",
        },
        "data_snapshot_ref": {
            "artifact_id": "sha256:...",
            "kind": "fabric.data_snapshot",
            "media_type": "application/json",
        },
    },
    "params": {"random_seed": 42},
}
```

## Архитектура директории

```text
scientist/
├── api.py, __init__.py              # публичный фасад
├── workflows/                       # default workflow spec + сборка execution context/registry
├── engine/                          # state, протоколы, executor, checkpoint, idempotency
├── nodes/builtins/                  # бизнес-ноды (data/planning/compile/simulate/governance/decide)
├── adapters/                        # порты к foundry/fabric
├── governance/                      # validation pipeline + governance report модели
├── kernel/                          # phase FSM, budgets, human gate protocol
├── llm_cycle.py                     # execution plan / preflight / evaluator helpers + persistence
├── replay_backend.py                # replay strategy (foundry/scientist) + verification
├── llm/                             # gateway-first LLM client + model profile registry
├── agent/                           # PI/Drafter/Formalizer/Critic + multipass/reflexion
├── search/                          # search loop + strategies
├── doe/                             # sensitivity/adversarial design + analysis
└── backtesting/                     # historical validation + trust scoring
```

## Что используется в default run, а что опционально

Используется по умолчанию (`run_experiment`):
- `workflows`, `engine`, `nodes/builtins`, `adapters`, `governance`, `kernel`, `compute`, `llm_cycle`.

Опциональные контуры:
- `agent` (LLM-агенты, multipass drafter);
- `search` и `doe` (итеративная оптимизация и стресс/чувствительность);
- `backtesting` (историческая валидация);
- `orchestrator/decision_card` (human-readable summary поверх decision packet).

## Связи с другими директориями

Исходящие зависимости (`scientist -> ...`):
- `core`: CAS/artifacts, observability, components discovery, run context, security.
- `ir`: Trinity, analytics contracts (causal/distributional/uncertainty/backtest), gate contracts.
- `foundry`: compile/execute, method backends, uncertainty/distributional analysis.
- `fabric`: DataSnapshot/DataViewRequest (`DefaultFabricPort`).
- `lex`: legal/gov checks и legal artifacts в governance контурах.
- `scholar`: enrichment/knowledge артефакты (опционально).
- `runtime.replay`: completeness/verification при replay.

Входящие зависимости (`... -> scientist`):
- CLI: `core/components/_cli_scientist.py`, `core/components/_cli_replay.py`;
- runtime/debug сервисы, читающие trace и node-события scientist.

## Воспроизводимость и эксплуатационные механизмы

- **Idempotency cache**: ключ = `run_id + node_id + state_reads snapshot + bind params`.
- **Checkpointing**: после успешных нод пишется `scientist.checkpoint` + head pointer.
- **Run lock**: `.polisyos/runs/<run_id>/run.lock` предотвращает конкурентный запуск.
- **Replay backend**: стратегии `foundry`/`scientist`, completeness report, env diff, verification.
- **Observability**: run/node spans, telemetry по нодам и governance passes.
- **Security hooks**: foundry adapter умеет добавлять TEE attestation и SBOM derived artifacts.

## Основные артефакты

Типичные выходы default workflow:
- `scientist.decision_packet`;
- `scientist.governance_report`;
- `scientist.workflow_report`;
- `scientist.execution_plan`;
- `scientist.preflight_report`;
- `scientist.evaluator_report`;
- `scientist.iteration_state`;
- `scientist.experiment_state`;
- `scientist.checkpoint` (если policy не `off`);
- производные `foundry.*` артефакты (exec plan, simulation result, metrics, environment manifest и др.).

## Тесты

Основной набор тестов: `policy-engine/tests/scientist/`.

```bash
pytest policy-engine/tests/scientist -q
pytest policy-engine/tests/scientist/integration/test_checkpoint_resume.py -q
pytest policy-engine/tests/scientist/integration/test_workflow_tracing.py -q
```

## Поддиректории с отдельной документацией

- `agent/README.md`
- `backtesting/README.md`
- `doe/README.md`
- `engine/README.md`
- `governance/README.md`
- `kernel/README.md`
- `llm/README.md`
- `nodes/README.md`
- `search/README.md`
- `workflows/README.md`
