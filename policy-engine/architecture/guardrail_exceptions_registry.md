# Architecture Guardrail Exceptions Registry

Все временные исключения для новых архитектурных guardrails должны иметь owner, expiry и запись в этом реестре.
Используйте `subject_glob`/`detail_glob` для `public_surface`, `generated_artifact`,
`workflow_config`, `readme_policy`, а для `deep_import` — `source_module_glob` и
`target_module_glob`.

| id | check | owner | reason | added_on | expires | status |
| --- | --- | --- | --- | --- | --- | --- |
| `_no-active-exceptions_` | - | - | - | - | - | - |
