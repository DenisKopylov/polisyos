# tools/architecture

Машиночитаемые guardrails и golden-path scaffolding для Phase 5.

## Что здесь живёт

| Скрипт          | Назначение                                                                                                                                                                                                   |
| --------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `guardrails.py` | Генерирует и проверяет public-surface inventory, deep-import baseline, workflow/toolchain guardrails и generated-artifact lifecycle docs                                                                     |
| `scaffold.py`   | Unified scaffold entrypoint для package README, connector, governance pass, runtime route, benchmark, ADR и runbook; package README scaffold now includes the Phase 7 change-ratchet fields for new surfaces |

## Типовой запуск

```bash
python3 tools/architecture/guardrails.py sync
python3 tools/architecture/guardrails.py check
python3 tools/architecture/scaffold.py package-readme --module polisyos.example --output src/polisyos/example/README.md --dry-run
python3 tools/architecture/scaffold.py connector --name MySource --type REST --dry-run
```

## Источники истины

- `architecture/public_surface.toml`
- `architecture/generated_artifacts.toml`
- `architecture/deep_import_baseline.json`
- `architecture/guardrail_exceptions.toml`

## Exception process

- Каждый temporary exception обязан иметь `id`, `owner`, `reason`, `expires`.
- Для `deep_import` используйте `source_module_glob` и `target_module_glob`.
- Для `public_surface`, `generated_artifact`, `workflow_config`, `readme_policy`
  используйте `subject_glob` и, при необходимости, `detail_glob`.
