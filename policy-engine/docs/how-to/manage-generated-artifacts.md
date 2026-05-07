# Управление generated artifacts

> Используйте этот guide, когда меняете ABI snapshots, runtime OpenAPI, generated clients/types или любые другие committed generated outputs.

Freshness: 2026-04-17.

## Вход

- изменение в source-of-truth surface: ABI models, runtime routes, connector contracts или tooling registry
- понимание, какой generated family затронут
- решение, должен ли артефакт быть committed или оставаться transient

## Выход

- source + generated outputs синхронизированы
- drift gates проходят
- reviewer видит осмысленную причину обновления, а не случайный regen noise

## Команды

```bash
uv run polisyos-tools architecture guardrails check
uv run --extra ml polisyos-tools diagnostics gen-schema --check
uv run polisyos-tools docs --output docs/reference/tools.md
```

## Источник истины

Machine-readable source of truth:

- `architecture/generated_artifacts.toml`

Human-readable reference map:

- `docs/reference/generated-artifacts.md`

Fabric-specific source-of-truth surfaces:

| Artifact                                                     | Source of truth                                                                   | Check                                                                                                              |
| ------------------------------------------------------------ | --------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------ |
| `schemas/snapshots/fabric/{edge_kind,node_kind}.schema.json` | `src/polisyos/schemas/abi_models.py` and Fabric/world ABI models                               | `uv run --extra ml polisyos-tools diagnostics gen-schema --check`                                                  |
| `schemas/snapshots/fabric/connector_contract_registry.json`  | `tools/quality/validation/fabric_schema_governance.py` and `ALL_SOURCE_CONTRACTS` | `uv run python tools/ci/check_fabric_schema_registry.py --check --evidence-out _build/.tmp/fabric-schema-governance.json` |
| `schemas/snapshots/connectors/contracts.json`                | `polisyos-tools connectors check-contracts` and `ALL_SOURCE_CONTRACTS`                  | `uv run polisyos-tools connectors check-contracts --check`                                                        |
| `tests/_data/fabric/connectors/sources/`                  | recorded upstream connector responses                                             | manual fixture refresh and source-specific replay tests                                                            |

## Базовый цикл

1. Меняете **источник**, а не generated output вручную.
2. Запускаете каноническую regeneration command для нужной family.
3. Проверяете drift guard.
4. Коммитите source + generated outputs вместе, если family имеет `commit_policy = committed`.

## Полезные команды

```bash
uv run polisyos-tools architecture guardrails check
uv run --extra ml polisyos-tools diagnostics gen-schema --check
uv run --extra runtime --extra ml polisyos-tools runtime check-runtime-api-contract
uv run polisyos-tools docs --output docs/reference/tools.md
uv run polisyos-tools connectors check-contracts --check
uv run python tools/ci/check_fabric_schema_registry.py --check --evidence-out _build/.tmp/fabric-schema-governance.json
cd apps/runtime-dashboard && corepack pnpm run generate:api
```

`docs/reference/tools.md` is generated from `tools.registry`; do not hand-edit
its command tables. Change the registry metadata first, then regenerate.

## Когда коммитить, а когда нет

- `commit_policy = committed`: source и generated outputs должны ехать в одном PR.
- `commit_policy = mixed`: коммитьте только review-worthy baselines/evidence artifacts; локальные и transient outputs должны оставаться ignored.
- `drift_gate = manual_review`: автоматический freshness gate не обязателен, но reviewer должен видеть источник, команду и причину обновления.
- Для bundle stats это означает: `_build/apps/runtime-dashboard/dist/bundle-stats.json`
  обычно остаётся локальным output и попадает в PR только если вы намеренно
  продвигаете bundle baseline.

## Если меняется lifecycle rule

Обновите:

1. `architecture/generated_artifacts.toml`
2. `docs/reference/generated-artifacts.md` через `uv run polisyos-tools architecture guardrails sync`
3. ближайший subsystem README, если изменилась recommended start point или location

## Fabric schema compatibility gate

Fabric has two schema surfaces:

- ABI snapshots for stable Fabric/world enum and model boundaries.
- Connector contract snapshots for source payload schemas and downstream
  migration planning.

When connector payload shape changes, update the contract source first, then run
the gates. Do not hand-edit the snapshots.

```bash
uv run polisyos-tools connectors check-contracts --check
uv run python tools/ci/check_fabric_schema_registry.py --check --evidence-out _build/.tmp/fabric-schema-governance.json
uv run pytest tests/repo_quality/tools/test_fabric_schema_governance.py -q
```

If the gate reports a breaking change, add governance metadata to the contract:
owner, reviewer, risk level, migration status, downstream impact summary,
migration note, ADR refs when applicable, and `approved_major_bump=True`.

## Fabric quality and lineage artifacts

Quality and lineage examples should point at current executable artifacts:

- `tests/unit/fabric/test_quality_indicators.py` for `QualityIndicators`,
  `DataFitnessReport`, finite quality bounds, and DuckDB quality identifier
  safety.

- `tests/unit/fabric/test_lineage.py` for `FabricLineageTracker`,
  OpenLineage JSON, visualization graph export, and downstream impact analysis.

- `tests/unit/fabric/data_plane/test_quarantine.py` for CAS-backed
  `QuarantineRecord` report/reprocess artifacts.

- `tests/unit/fabric/data_plane/test_streaming_runtime.py` for
  `fabric.cdc_schema_change` artifacts emitted by streaming/CDC processing.

## Откат

Если regeneration оказался accidental:

1. откатите generated diff;
2. проверьте исходный source-of-truth файл;
3. запустите только релевантный generator/gate ещё раз, чтобы убедиться, что drift ушёл.

## Troubleshooting

- Если `guardrails sync` или schema generation меняют unrelated files, сначала найдите исходный source-of-truth, а не редактируйте generated output вручную.
- Если runtime OpenAPI и клиент расходятся, сначала экспортируйте и проверьте контракт, затем уже регенерируйте client.
- Если reviewer не понимает, почему артефакт изменился, PR ещё не готов: добавьте источник, команду и contract story.
