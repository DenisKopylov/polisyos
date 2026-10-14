# Управление generated artifacts

> Используйте этот guide, когда меняете ABI snapshots, runtime OpenAPI, generated clients/types или любые другие committed generated outputs.

Owner: `@platform-owners` for this procedure; each artifact family's `owner` and `approval_owner` are declared in the registry.
Source of truth: `architecture/generated_artifacts.toml`; the rendered lookup is `docs/reference/generated-artifacts.md`.

Source reviewed at `47e1e59b569a5b922611f71a7f53fb6320abea4c` on 2026-10-14.
This was a read-only inspection of the artifact registry, listed generator and
check entrypoints, contributor environment, and the workflows that retain
evidence. No generator, check, test, CI workflow, or GitHub artifact was run or
queried. This is a source review, not a freshness or generation receipt.

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
cd policy-engine
uv run polisyos-tools architecture guardrails check
uv run --extra ml polisyos-tools diagnostics gen-schema --check
uv run polisyos-tools docs --output docs/reference/tools.md
```

These are examples, not a substitute for the selected family's exact
`check_command`. Start from the family entry in
[`architecture/generated_artifacts.toml`](https://github.com/DenisKopylov/polisyos/blob/78a7b7b9cdab2b16e9d4ecd56c15bece38728f3b/policy-engine/architecture/generated_artifacts.toml)
and use its `check_cwd`, `check_command`, `regenerate_commands`, output set, and
`commit_policy`. The supported contributor baseline is Python 3.14.x and
`uv 0.9.21`; schema and documentation commands use the `docs`/`ml` extras as
shown. A dashboard client generation also needs Node 22.x, Corepack, and the
locked install documented in [`CONTRIBUTING.md`](https://github.com/DenisKopylov/polisyos/blob/78a7b7b9cdab2b16e9d4ecd56c15bece38728f3b/policy-engine/CONTRIBUTING.md):
`corepack pnpm install --frozen-lockfile --ignore-scripts` from the product
root, then run the family command from its registered `check_cwd`.

## Источник истины

Machine-readable source of truth:

- `architecture/generated_artifacts.toml`

Human-readable reference map:

- `docs/reference/generated-artifacts.md`

Примеры зарегистрированных families:

| Registered family                    | Source of truth in the registry                                                                                                 | Registered check command                                                                                                  |
| ------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------- |
| `abi-schema-snapshots`               | `src/polisyos/schemas/abi_models.py` and declared Pydantic/Enum contracts                                                       | `uv run --extra ml polisyos-tools diagnostics gen-schema --check`                                                         |
| `fabric-connector-contract-registry` | `polisyos.fabric.connectors.sources._contracts.ALL_SOURCE_CONTRACTS` and `tools/quality/validation/fabric_schema_governance.py` | `uv run python tools/ci/check_fabric_schema_registry.py --check --evidence-out _build/.tmp/fabric-schema-governance.json` |
| `runtime-openapi-snapshot`           | Runtime HTTP FastAPI app factory and DTO contracts                                                                              | `uv run --extra runtime --extra ml python tools/ops_runners/runtime/check_runtime_api_contract.py --skip-client-drift`    |
| `runtime-dashboard-api-types`        | `schemas/runtime_api_v1.openapi.json`                                                                                           | `corepack pnpm run generate:api` (from `apps/runtime-dashboard/`, after the locked install)                               |

This table is an entry point only. The registry is authoritative for the full
outputs, precise owner/approval owner, generator, lifecycle, and command
arguments; use those exact values if they differ from the examples here. The
connector-contract CLI check is useful for its own contract surface, but it is
not a generated family unless that output is registered there. At this source
pin, the matching registered regeneration commands are:

- `abi-schema-snapshots` (from `policy-engine/`):
  `uv run --extra ml polisyos-tools diagnostics gen-schema`
- `fabric-connector-contract-registry` (from `policy-engine/`):
  `uv run python tools/ci/check_fabric_schema_registry.py --update`
- `runtime-openapi-snapshot` (from `policy-engine/`):
  `PYTHONPATH=src:. uv run --extra runtime --extra ml python tools/ops_runners/runtime/export_runtime_openapi.py --output schemas/runtime_api_v1.openapi.json`
- `runtime-dashboard-api-types` (from `policy-engine/`; run after the locked
  install above):
  `corepack pnpm --filter @polisyos/runtime-dashboard run generate:api -- --openapi schemas/runtime_api_v1.openapi.json`

Run only the selected family's command; these entries do not imply that every
family needs regeneration in one change.

## Повторяемый цикл и receipt

1. Из product root `policy-engine/`, проверьте текущий source pin и локальное
   состояние: `git rev-parse HEAD` и `git status --short`. Запишите версии из
   `python3 --version`, `uv --version` и, для client generation,
   `node --version` / `corepack pnpm --version`. Provision the `docs` profile
   from `CONTRIBUTING.md` first.
2. Найдите family по выходному пути в `architecture/generated_artifacts.toml`.
   Сверьте `source_of_truth`, `check_cwd`, `check_command`,
   `regenerate_commands`, `outputs`, `commit_policy`, `owner` и
   `approval_owner`. Сначала запустите ровно `check_command` из указанного
   `check_cwd`; не подменяйте failed или unavailable check строковым поиском.
3. Если зарегистрированный drift требует обновления, измените source, затем
   запустите только зарегистрированную regeneration command для этой family.
   Повторите зарегистрированную проверку после генерации и проверьте
   `git diff --check`, `git status --short` и diff каждого объявленного output.
   `architecture guardrails check` проверяет саму registry definition; это не
   заменяет family-specific check.
4. Для review зафиксируйте repository commit SHA, поддерживаемые tool versions,
   точные команды и их outcomes, список generated paths и SHA-256 каждого
   retained output (`shasum -a 256 <path>`). В PR summary укажите, был ли
   output regenerated, остался ли diff и кто указан `approval_owner`.
5. Коммитьте source вместе с generated outputs только согласно
   `commit_policy`. Если проверка не запускалась, пишите `UNRUN` и называйте
   отсутствующую зависимость; отсутствие результата не является успехом.

Не сохраняйте hash для невоспроизводимого runner temp path как будто он был
проверен позже: приложите его к run id и сроку хранения либо явно назовите
receipt локальным/временным.

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

## Переносимость и хранение evidence

Committed generated outputs доступны reviewer'ам в Git в ветке и после merge.
Локальные результаты под `_build/.tmp/`, `_build/` и другими ignored paths
не появляются в PR и не доступны другим участникам только потому, что команда
успешно завершилась. У команды `check_fabric_schema_registry.py` локальный
`--evidence-out _build/.tmp/fabric-schema-governance.json` — именно такой
временный файл. В `.github/workflows/fabric-remediation.yml` есть отдельный
upload step с artifact `fabric-schema-governance`, путём
`_build/.tmp/test-reports/fabric-schema-governance.json` и retention 14 дней;
это отдельный workflow output, а не автоматическая публикация локального
`--evidence-out` файла.

Ссылка на evidence должна вести на доступный Actions run и на скачиваемый
artifact с его точным именем. Сверяйте run commit SHA и загруженный файл; не
считайте, что artifact существует только потому, что workflow в source его
объявляет. Это выбранные примеры на проверенном source pin, не полный
перечень artifact uploads и не свидетельство актуальной live retention policy.
В них ABI reports и workflow
policy summary — 14 дней в `.github/workflows/abi.yml`; PR Standard reports —
14 дней в `.github/workflows/ci.yml`; Fabric schema governance evidence —
14 дней в `.github/workflows/fabric-remediation.yml`; некоторые Core Runtime
release-review evidence bundles — 30 дней в
`.github/workflows/core-runtime-release-gate.yml`. Указанный срок начинается
для успешно загруженного artifact и не доказывает его наличие в конкретном
run.

Если gate упал, передавайте владельцу artifact family точные run URL, commit,
failed step, command и текст ошибки; прикрепляйте загруженный artifact до
истечения его срока. Если gate или upload не выполнялся, отчёт отсутствует,
или срок истёк, укажите `UNRUN` или `unavailable`, причину и путь повторить
зарегистрированную проверку. Не подменяйте этот receipt новым локальным
запуском и не выдавайте локальный log за прежний CI результат. Для источников,
генераторов и approval сверяйте конкретную family в registry; для изменения
workflow hand off идёт к `@platform-owners`.

Архивирование/долгосрочное хранение не означает копирование `_build` в
репозиторий или создание незарегистрированного upload. Сохраняйте только через
уже объявленный owner/approval path и зарегистрированный committed output либо
доступный workflow artifact. Если такого пути или достаточного срока нет,
зафиксируйте это как границу текущего evidence contract и согласуйте решение с
family owner; это не основание придумывать новый CI artifact.

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
