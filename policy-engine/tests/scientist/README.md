# Scientist Tests

`tests/scientist` покрывает orchestration layer `polisyos.scientist`: workflow engine, node execution, governance passes, search/DOE и decision artifacts.

Актуально на **17 февраля 2026**.

## Состав

- `60` файлов `test_*.py`
- `3` файла `conftest.py`

## Структура

| Подкаталог | `test_*.py` | Что покрывает |
|---|---:|---|
| `scientist/` (корень) | 37 | engine/executor, nodes, decision artifacts, replay/idempotency |
| `scientist/governance/` | 7 | legal/equity/confidence/pii/norm passes + validation pipeline |
| `scientist/search/` + `search/strategies/` | 11 | search loop, portfolio/diversity/adversarial, стратегии оптимизации |
| `scientist/integration/` | 2 | checkpoint-resume и workflow tracing |
| `scientist/doe/` | 2 | sampling/sensitivity plan |
| `scientist/compute/` | 1 | polyglot runner |

## Ключевые зоны

- Engine/workflow: `test_engine_executor_v0.py`, `test_engine_executor_idempotency.py`, `test_engine_default_workflow_*.py`.
- Node-level behavior: `test_bind_foundry_inputs_node.py`, `test_data_plane_gate_node.py`, `test_distributional_analysis_node.py`, `test_propagate_uncertainty_node.py`.
- Decision artifacts: `test_decision_packet_node_v3.py`, `test_decision_card.py`, `test_failure_index.py`.
- Agent контур: `test_agent_protocols.py`, `test_multipass_drafter.py`, `test_informed_critic.py`, `test_llm_cycle_preflight.py`.

## Integration и окружение

- `scientist/integration/*` помечены `@pytest.mark.integration`.
- `test_workflow_tracing.py` дополнительно требует `POLISYOS_RUN_INTEGRATION=1`.
- Часть тестов условно `skip`-ится при отсутствии optional зависимостей (например, `jax`).

## Связи с кодом

- `policy-engine/src/polisyos/scientist`
- `policy-engine/src/polisyos/foundry`
- `policy-engine/src/polisyos/core`
- `policy-engine/src/polisyos/runtime`

## Запуск

```bash
pytest tests/scientist -q
pytest tests/scientist/governance -q
pytest tests/scientist/search -q
POLISYOS_RUN_INTEGRATION=1 pytest tests/scientist/integration -q
```
