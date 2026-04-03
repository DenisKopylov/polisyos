# Управление generated artifacts

> Используйте этот guide, когда меняете ABI snapshots, runtime OpenAPI, generated clients/types или любые другие committed generated outputs.

## Источник истины

Machine-readable source of truth:

- `architecture/generated_artifacts.toml`

Human-readable reference map:

- `docs/reference/generated-artifacts.md`

## Базовый цикл

1. Меняете **источник**, а не generated output вручную.
2. Запускаете каноническую regeneration command для нужной family.
3. Проверяете drift guard.
4. Коммитите source + generated outputs вместе, если family имеет `commit_policy = committed`.

## Полезные команды

```bash
python3 tools/architecture/guardrails.py check
PYTHONPATH=src:. uv run --extra ml python tools/diagnostics/gen_schema.py --check
PYTHONPATH=src:. uv run --extra runtime --extra ml python tools/runtime/check_runtime_api_contract.py
cd frontend/runtime-dashboard && npm run generate:api
```

## Когда коммитить, а когда нет

- `commit_policy = committed`: source и generated outputs должны ехать в одном PR.
- `commit_policy = mixed`: коммитьте только review-worthy baselines/evidence artifacts; локальные и transient outputs должны оставаться ignored.
- `drift_gate = manual_review`: автоматический freshness gate не обязателен, но reviewer должен видеть источник, команду и причину обновления.
- Для bundle stats это означает: `frontend/runtime-dashboard/dist/bundle-stats.json`
  обычно остаётся локальным output и попадает в PR только если вы намеренно
  продвигаете bundle baseline.

## Если меняется lifecycle rule

Обновите:

1. `architecture/generated_artifacts.toml`
2. `docs/reference/generated-artifacts.md` через `python3 tools/architecture/guardrails.py sync`
3. ближайший subsystem README, если изменилась recommended start point или location
