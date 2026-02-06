# IR Migrations (Runtime)

Runtime миграции поддерживают только канонические Trinity payloads.

## Public API

- `split_to_bundle(payload)`
- `is_trinity_migrated(payload)`
- `migrate_policy_ir_identity(payload)`
- `migrate_policy_ir(payload, target_version=...)`

## Guarantees

- Никакие legacy surface payloads не принимаются runtime миграциями.
- Для невалидного payload выбрасывается ошибка валидации.
- Миграции детерминированы относительно входного JSON.

## Usage

```python
from polisyos.ir.migrations.trinity_migration import split_to_bundle, is_trinity_migrated
from polisyos.ir.loaders import load_policy

bundle = load_policy(payload)
assert is_trinity_migrated(bundle.model_dump(mode="json"))
parts = split_to_bundle(bundle.model_dump(mode="json"))
```

## CLI

Отдельные legacy CLI миграции удалены из `tools/`.
Исторические скрипты перенесены в `docs/archive/`.
