# Architecture Guardrail Exceptions Registry

All temporary exceptions for new architecture guardrails must have an owner, an expiry, and an entry in this registry.
Use `subject_glob`/`detail_glob` for `public_surface`, `generated_artifact`,
`workflow_config`, and `readme_policy`; for `deep_import`, use `source_module_glob` and
`target_module_glob`.

| id                       | check | owner | reason | added_on | expires | status |
| ------------------------ | ----- | ----- | ------ | -------- | ------- | ------ |
| `_no-active-exceptions_` | -     | -     | -      | -        | -       | -      |
