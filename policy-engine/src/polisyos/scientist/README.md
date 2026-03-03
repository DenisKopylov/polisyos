# Scientist (`polisyos.scientist`)

`scientist` — orchestration-слой Policy Engine для запуска policy-экспериментов и сборки воспроизводимого результата поверх `ir`, `foundry`, `fabric`, `lex`, `scholar`, `core`.

Документ отражает текущее состояние кода на **2026-03-03**.

## Роль в системе

`scientist` отвечает за:
- сборку и исполнение workflow DAG;
- координацию этапов data -> planning/preflight -> compile -> simulate -> governance -> decision;
- сериализацию run-артефактов и run-отчетов;
- воспроизводимость (`idempotency`, `checkpoint`, `resume`, `replay`).

`scientist` не реализует доменную математику/хранилища сам:
- доменный execute/compile: `foundry`;
- данные и retrieval: `fabric`;
- канонические IR-контракты: `ir`;
- юридический домен: `lex`.

## Публичные точки входа

- `polisyos.scientist.run_experiment(state=None)` — стандартный entrypoint.
- `polisyos.scientist.workflows.run_default_workflow(...)` — запуск `scientist_default`.
- `polisyos.scientist.workflows.run_causal_full_workflow(...)` — запуск `scientist_causal_full`.
- `polisyos.scientist.engine.resume_from_checkpoint(...)` — resume по checkpoint.

`run_experiment()`:
- валидирует вход как `ExperimentState` (`extra="forbid"`);
- генерирует `run_id`, если пустой;
- отклоняет неизвестные top-level ключи при mapping-входе;
- возвращает финальный `ExperimentState` в виде `dict`.

## Актуальные workflow спецификации

### `scientist_default`

Spec: `workflows/default.py`.

```text
start
├─ build_data_snapshot -> bind_foundry_inputs -> run_data_plane_gate
├─ build_execution_plan -> build_method_catalog_snapshot -> run_preflight -> ready_to_run
└─ link_trinity

compile_foundry (depends: link_trinity + run_data_plane_gate + ready_to_run)
└─ resolve_parameters (depends: compile_foundry + bind_foundry_inputs + run_data_plane_gate)
   └─ run_simulation
      ├─ run_distributional_analysis
      └─ propagate_uncertainty

run_causal_evaluation (depends: build_data_snapshot)
run_governance (depends: propagate_uncertainty + run_distributional_analysis + run_causal_evaluation)
run_evaluator (depends: run_governance)
build_decision_packet (depends: run_governance + run_causal_evaluation + run_evaluator)
```

Ключевые свойства:
- `error_policy="continue"`: независимые ветки продолжаются, зависимые ноды skip при upstream fail;
- preflight-пайплайн обязателен перед compile;
- `run_evaluator` всегда участвует в default-пути.

### `scientist_causal_full` (опционально)

Spec: `workflows/causal_full.py`.

Добавляет causal-ветку:
- `build_literature_prior`
- `reconcile_causal_graph`
- `run_causal_queries`
- `run_causal_ensemble`
- `run_abm_consistency`
- `run_transportability`

Используется для расширенного causal-контура, default-`run_experiment()` его автоматически не запускает.

## Минимальный входной контракт

`ExperimentState` требует:
- обязательно `inputs.trinity_bundle_ref`;
- минимум один источник данных:
  - `inputs.data_snapshot_ref`, или
  - `inputs.input_bindings_ref`, или
  - `inputs.data_view_request_ref`.

`inputs.registry_bundle_ref` можно не передавать: workflow соберет его автоматически.

## Архитектура директории

```text
scientist/
├── api.py, __init__.py          # публичный facade
├── workflows/                   # workflow specs + запуск + context/registry wiring
├── engine/                      # executor, state, protocol, idempotency, checkpoint/resume
├── nodes/                       # builtin DAG-ноды (data/planning/compile/causal/simulate/governance/decide)
├── adapters/                    # bridges к foundry/fabric
├── compute/                     # method/legacy execution jobs
├── governance/                  # validation passes/pipeline + governance report
├── kernel/                      # phase FSM, budgets, human gate protocol
├── llm_cycle.py                 # execution-plan/preflight/evaluator/reproducibility helpers
├── replay_backend.py            # replay (foundry/scientist) + verification
├── llm/                         # gateway-first LLM client + model profile registry
├── agent/                       # PI/Drafter/Formalizer/Critic + multipass/reflexion
├── search/                      # search loop + strategies
├── doe/                         # sensitivity/adversarial design + analysis
├── backtesting/                 # historical validation + trust scoring
└── orchestrator/                # decision-card summary layer
```

## Связи с соседними пакетами

Исходящие зависимости (`scientist -> ...`):
- `core`: CAS/artifacts, run-context, observability, components discovery, security hooks;
- `ir`: trinity/gate/analytics контракты;
- `foundry`: compile/execute и method-инфраструктура;
- `fabric`: data snapshot flows;
- `lex`: legal/governance контракты и проверки;
- `scholar`: optional knowledge enrichment artifacts;
- `runtime.replay`: completeness/verification.

Входящие зависимости (`... -> scientist`):
- CLI (`core/components/_cli_scientist.py`, `_cli_replay.py`);
- runtime/debug tooling, читающие trace/node events.

## Воспроизводимость и эксплуатация

- Idempotency key: `run_id + node_id + snapshot(state_reads) + bind params`.
- Checkpoint: `scientist.checkpoint` + `.polisyos/runs/<run_id>/checkpoint_head.json`.
- Run lock: `.polisyos/runs/<run_id>/run.lock`.
- Resume: fingerprint workflow сверяется с checkpoint metadata.
- Replay backend: стратегии `foundry` и `scientist`, env diff, verification.
- Security bridge: TEE attestation/SBOM как derived artifacts через adapter.

## Поддиректории с отдельной документацией

- `adapters/README.md`
- `agent/README.md`
- `backtesting/README.md`
- `compute/README.md`
- `doe/README.md`
- `engine/README.md`
- `governance/README.md`
- `kernel/README.md`
- `llm/README.md`
- `nodes/README.md`
- `orchestrator/README.md`
- `search/README.md`
- `search/strategies/README.md`
- `workflows/README.md`
