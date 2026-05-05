# ADR-0008: Scientist Node Idempotency Contract

- **Дата**: 2026-02-06
- **Статус**: Accepted
- **Roadmap label**: ADR-003

## Контекст

Scientist DAG содержит дорогостоящие и нестабильные операции (Foundry compile/execute, Scholar/Fabric/Lex integration). При повторном запуске или аварийном перезапуске система повторно выполняла уже успешные узлы, что увеличивает стоимость и время выполнения.

## Решение

1. Добавить run-scoped idempotency key для DAG node:

   - `node_id` (включая версию),
   - `run_id`,
   - канонический snapshot `state_reads`,
   - `bind_params`.
2. Реализовать CAS-backed `NodeResultCache`:

   - `ok` outcomes сохраняются как `scientist.node_outcome`,
   - индексная запись сохраняется как `scientist.node_cache_entry`.
3. Интегрировать кэш в `WorkflowExecutor`:

   - cache hit: `NODE_CACHE_HIT`,
   - cache store: `NODE_CACHE_STORE`,
   - fail-open bypass: `NODE_CACHE_BYPASS`.
4. Восстанавливать cache index при restart того же `run_id` через replay `NODE_CACHE_STORE` из trace JSONL.
5. Не кэшировать outcomes со статусом `fail`.
6. Добавить CI guards:

   - `tools/quality/diagnostics/check_state_reads.py`,
   - `tools/quality/diagnostics/check_scientist_node_version_bump.py`.

## Последствия

### Положительные

1. Повторный запуск того же run не дублирует успешную работу узлов.
2. Появляется практический фундамент для checkpoint/resume (Phase 8).
3. Сохраняется совместимость `Node` protocol.
4. Улучшается auditability через trace events.

### Отрицательные

1. Добавляется overhead на key generation и cache lookup/store.
2. Требуется дисциплина обновления `state_reads` и `component_id` версий.
3. Хранилище CAS растет за счет `NodeOutcome`/cache-entry артефактов.

## Альтернативы

1. Кэшировать по hash всего `ExperimentState`: отклонено (избыточная invalidation).
2. Добавить декораторы на каждый node: отклонено (инвазивно и плохо масштабируется).
3. Кэшировать на уровне портов (`FoundryPort`, `ScholarPort`): отклонено (частичное покрытие).
