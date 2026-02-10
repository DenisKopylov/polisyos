# Scientist Tests

Тестовый контур `tests/scientist` покрывает оркестрацию экспериментов, governance-проходы и AI/поисковые компоненты слоя `polisyos.scientist`.

Актуально на **10 февраля 2026**.

## Роль в системе

- Проверяет исполнение workflow-движка (`executor`, `registry`, default workflows, idempotency).
- Валидирует узлы оркестрации и decision-артефакты (`decision_packet`, `decision_card`, uncertainty/distributional nodes).
- Защищает governance-контур (legal/equity/confidence/pii/norm-execution/validation passes).
- Тестирует search/DOE-подсистемы (portfolio/adversarial/diversity, стратегии оптимизации).

## Снимок структуры

- `58` файлов `test_*.py`
- `63` Python-файла
- `3` файла `conftest.py`
- `1` `README.md`

| Подкаталог | `test_*.py` | Зона ответственности |
|---|---:|---|
| корень `scientist/` | 35 | Engine/workflow, agent protocols, compiler, decision artifacts, nodes |
| `governance/` | 7 | Validation pipeline и governance passes |
| `search/` + `search/strategies/` | 11 | Search loop, portfolio/adversarial/diversity, стратегии |
| `integration/` | 2 | E2E tracing/checkpoint-resume сценарии |
| `doe/` | 2 | Sampling и sensitivity plan |
| `compute/` | 1 | Polyglot runner |

## Ключевые модули

### Engine и workflow

- `test_engine_executor_v0.py`, `test_engine_executor_idempotency.py`, `test_engine_registry_v0.py`
- `test_engine_default_workflow_e1_7.py`, `test_engine_default_workflow_p8.py`
- `test_checkpoint.py`, `test_replay_backend.py`, `test_idempotency.py`

### Agent и drafting контур

- `test_agent_protocols.py`, `test_multipass_drafter.py`, `test_informed_critic.py`
- `test_constitution.py`, `test_drafter_constitution.py`, `test_critic_factory.py`
- `test_rag_index.py`, `test_knowledge_base.py`, `test_norm_loader.py`

### Ноды и артефакты решения

- `test_bind_foundry_inputs_node.py`, `test_data_plane_gate_node.py`
- `test_causal_evaluation_node.py`, `test_distributional_analysis_node.py`
- `test_propagate_uncertainty_node.py`, `test_enrich_knowledge_node_freshness.py`
- `test_decision_packet_node_v3.py`, `test_decision_packet_distributional_econometrics.py`
- `test_decision_card.py`, `test_decision_card_uncertainty_render.py`

### Governance

- `governance/test_validation_pipeline.py`
- `governance/test_norm_execution.py`
- `governance/test_legal_pass.py`, `governance/test_equity_pass.py`
- `governance/test_confidence_pass.py`, `governance/test_pii_check_pass.py`
- `governance/test_shared_shims.py`

### Search / DOE / Compute

- Search: `search/test_search_loop.py`, `search/test_portfolio_search.py`, `search/test_adversarial.py`, `search/test_diversity.py`
- Strategies: `search/strategies/test_bayesian.py`, `test_multi_objective.py`, `test_random_grid.py`, `test_controller_batch.py`, `test_resource_arbiter.py`, `test_space_codec.py`, `test_adapter.py`
- DOE: `doe/test_sampling.py`, `doe/test_sensitivity_plan.py`
- Compute: `compute/test_runner_polyglot.py`

## Инфраструктура тестов

### `conftest.py`

- `tests/scientist/conftest.py` поднимает in-memory OTel exporter и сбрасывает singleton-ы `PolicyOSTracer`/`MetricsRegistry`.
- `tests/scientist/search/strategies/conftest.py` даёт типовые search spaces и helper для synthetic `Evaluation`.
- `tests/scientist/search/conftest.py` зарезервирован под search-специфичные фикстуры.

### Integration и optional зависимости

- `scientist/integration/*` помечены `@pytest.mark.integration`.
- `test_workflow_tracing.py` выполняется только при `POLISYOS_RUN_INTEGRATION=1`.
- `test_feasibility_probe.py` использует `pytest.importorskip("jax")`.
- В `test_multipass_drafter.py` часть кейсов может `skip`-нуться без активного in-memory tracer provider.

## Связи с другими директориями

| Здесь | Связанные директории | Назначение связи |
|---|---|---|
| `tests/scientist/` | `src/polisyos/scientist` | Основной объект тестирования |
| `tests/scientist/` | `src/polisyos/foundry`, `src/polisyos/ir` | Проверка node/workflow-интеграции с simulation и IR |
| `tests/scientist/` | `src/polisyos/core`, `src/polisyos/runtime` | Артефакты, run-context, replay/runtime APIs |
| `tests/scientist/` | `src/polisyos/scholar` | Freshness/knowledge enrichment сценарии |

## Запуск

Команды из `policy-engine/`:

```bash
# весь scientist-контур
pytest tests/scientist -q

# governance/search
pytest tests/scientist/governance -q
pytest tests/scientist/search -q

# integration-кейсы scientist
POLISYOS_RUN_INTEGRATION=1 pytest tests/scientist/integration -q

# отдельные горячие зоны
pytest tests/scientist/test_engine_executor_v0.py -q
pytest tests/scientist/test_decision_packet_node_v3.py -q
pytest tests/scientist/test_multipass_drafter.py -q
```
