# Scientist (`polisyos.scientist`)

`scientist` — orchestration layer Policy Engine для выполнения policy-экспериментов поверх `ir`, `foundry`, `fabric`, `lex`, `scholar` и инфраструктуры `core`.

Документ отражает текущее состояние кода на **2026-02-10**.

## Роль в системе

`scientist` отвечает за:
- запуск workflow эксперимента;
- координацию data/compile/simulate/governance шагов;
- сбор итогового `DecisionPacket`;
- воспроизводимость запуска (checkpoint + replay + idempotency).

`scientist` не отвечает за:
- исполнение симуляции как таковое (это `foundry`);
- хранение и очистку исходных данных (это `fabric`);
- интерпретацию юридических норм как доменную подсистему (это `lex`);
- канонические схемы IR (это `ir`).

## Основные точки входа

- `polisyos.scientist.run_experiment(state=None)`
- `polisyos.scientist.workflows.builder.run_default_workflow(initial_state, ...)`

`run_experiment`:
- валидирует вход как `ExperimentState`;
- автогенерирует `run_id`, если он пустой;
- запускает default workflow;
- возвращает финальный `ExperimentState` как `dict`.

Важно: для mapping-входа отклоняются неизвестные top-level ключи (строгая схема).

## Default Workflow (актуальный DAG)

Default spec находится в `workflows/default.py` и использует engine-DAG с node aliases:

```text
start (noop)
├─ build_data_snapshot
│  └─ bind_foundry_inputs
│     └─ run_data_plane_gate
├─ link_trinity
│  └─ compile_foundry
│     └─ run_simulation
│        ├─ run_distributional_analysis
│        └─ propagate_uncertainty
│           └─ run_governance
└─ run_causal_evaluation (depends on build_data_snapshot)

build_decision_packet (depends on run_governance + run_causal_evaluation)
```

Node IDs в default workflow:
- `scientist.node_noop@1.0.0`
- `scientist.node_build_data_snapshot@1.0.0`
- `scientist.node_bind_foundry_inputs@1.0.0`
- `scientist.node_run_data_plane_gate@1.0.0`
- `scientist.node_link_trinity@1.0.0`
- `scientist.node_compile_foundry@1.0.0`
- `scientist.node_run_simulation@1.0.1`
- `scientist.node_run_causal_evaluation@1.1.0`
- `scientist.node_run_distributional_analysis@1.0.0`
- `scientist.node_propagate_uncertainty@1.0.0`
- `scientist.node_run_governance@1.1.0`
- `scientist.node_build_decision_packet@1.4.0`

## Минимальный входной контракт

`ExperimentState` (см. `engine/state.py`) — компактная строгая модель. Критичные входы для default workflow:

- обязательно: `inputs.trinity_bundle_ref`;
- `inputs.registry_bundle_ref` может быть создан автоматически, если не передан;
- обязательно хотя бы один источник данных:
  - `inputs.data_snapshot_ref`, или
  - `inputs.input_bindings_ref`, или
  - `inputs.data_view_request_ref`.

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
├── workflows/                       # default workflow spec + сборка execution context
├── engine/                          # DAG executor, state, registry, checkpoint, idempotency
├── nodes/builtins/                  # data/compile/simulate/governance/decide ноды
├── adapters/                        # порты к foundry/fabric
├── governance/                      # validation pipeline + compatibility слой к core.governance
├── kernel/                          # Phase FSM, budgets, human gate protocol
├── replay_backend.py                # replay decision packet (foundry/scientist strategy)
├── compute/                         # job runner (legacy program + method jobs)
├── orchestrator/                    # DecisionCard рендеринг из decision packet
├── publisher.py                     # helper для canonical decision payload
├── llm/                             # gateway-first LLM client + model profile registry + bridge к core.llm
├── agent/                           # PI/Drafter/Formalizer/Critic + multipass/reflexion
├── search/                          # search loop + strategies (random/grid/BO/MO и др.)
├── doe/                             # sensitivity/adversarial design and analysis
└── backtesting/                     # historical validation и trust scoring
```

## Что используется в default run, а что опционально

Используется в `run_experiment` по умолчанию:
- `workflows`, `engine`, `nodes/builtins`, `adapters`, `governance`, `kernel`, `compute`.

Опциональные/расширенные контуры:
- `agent` (LLM-агенты и multipass drafter);
- `search` и `doe` (optimization и sensitivity/stress experiments);
- `backtesting` (historical validation);
- `orchestrator/decision_card` (human-readable summary поверх packet).

Важно: текущий default DAG **не** запускает автоматически PI→Drafter→Formalizer→Critic цепочку.

## NL Agent Circuit через Runtime Control

Для `POST /api/v1/control/runs/nl` поддерживаются оба режима:

- `llm_model` — legacy single-model запуск;
- `llm_models` — multi-model запуск в рамках одного `run_id` с variant-сравнением.

Основные параметры запуска:

- `max_parallel_models`
- `run_budget_usd`
- `per_model_budget_usd`

Технически LLM-вызовы идут через gateway-first слой (`scientist/llm/gateway_client.py`), а per-model метрики сохраняются в `experiment_state.params.llm_model_variants` и читаются runtime debug/UI.

## Связи с другими директориями

Исходящие зависимости (`scientist -> ...`):
- `core`: artifacts/CAS, observability, components, run context, security, governance base.
- `ir`: Trinity, analytics contracts (causal/distributional/uncertainty/backtest), gate contracts.
- `foundry`: compile/execute и method backends.
- `fabric`: DataSnapshot и quality источники (через `DefaultFabricPort`).
- `lex`: legal evaluation node и legal governance passes.
- `scholar`: knowledge enrichment node.
- `runtime`: replay utilities (`runtime.replay.*`).

Входящие зависимости (`... -> scientist`):
- `core/components/_cli_scientist.py`: `scientist sensitivity run`, `scientist stress-test`, `scientist backtest`.
- `core/components/_cli_replay.py`: replay/resume используют scientist replay/checkpoint.
- `runtime/http/services/debug.py`: читает `scientist.node.*` trace-события для debug.

## Воспроизводимость и эксплуатационные механизмы

- **Idempotency cache**: ключи считаются из `NodeSpec.state_reads` + bind params + `run_id`; успешные `NodeOutcome` кэшируются в CAS.
- **Checkpointing**: после каждого успешного node создается `scientist.checkpoint`; поддержан `resume_from_checkpoint`.
- **Run lock**: `run.lock` предотвращает конкурентный запуск одного `run_id`.
- **Replay backend**: выбирает стратегию `foundry`/`scientist`, строит completeness report, проверяет environment diffs и verification.
- **Observability**: run-span + node-span + governance pass telemetry + SLO метрики.
- **Security hooks**: foundry adapter умеет прокидывать TEE attestation и SBOM-derived refs в execution artifacts.

## Основные артефакты

Типичные выходы default workflow:
- `scientist.decision_packet` (schema `3.1`);
- `scientist.governance_report`;
- `scientist.workflow_report`;
- `scientist.experiment_state`;
- `scientist.checkpoint` (если checkpoint policy включена);
- производные `foundry.*` артефакты (exec plan, simulation result, metrics, envelopes и т.д.).

## Тесты

Основной набор тестов: `policy-engine/tests/scientist/`.

Быстрые команды:

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
- `nodes/README.md`
- `search/README.md`
