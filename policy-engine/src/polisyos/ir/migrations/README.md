# Migrations (`polisyos.ir.migrations`)

`polisyos.ir.migrations` отвечает за runtime migration только канонического
policy IR payload. Модуль intentionally узкий: он не пытается реанимировать
legacy non-Trinity surface, а поддерживает версионирование `TrinityBundle`
внутри допустимой schema lineage.

## Роль в системе

- **Зависит от:** `polisyos.ir.trinity`
- **Используется в:** `polisyos.ir.loaders`, runtime ingestion, compatibility checks
- Migration layer изолирует schema-version transitions от остального code path.

## Ключевые концепции

- **Policy IR artifact** — canonical migration target всегда `policy_ir`.
- **Version parsing** — допустим только формат `MAJOR.MINOR`.
- **Controlled major bumps** — major transitions требуют явного `allow_major=True`.
- **Identity migration** — текущая цепочка регистрирует только `1.0 -> 1.0`.
- **Legacy rejection** — payloads с `semantic` или `2.*` version family блокируются как pre-Trinity surface.

## Public API

| Type/Function | Description |
|---|---|
| `IR_ARTIFACT` | Canonical artifact family name для policy IR |
| `IR_CURRENT_VERSION` | Текущая поддерживаемая версия policy IR |
| `parse_version()` | Парсит `MAJOR.MINOR` schema version |
| `is_major_bump()` | Определяет, требуется ли guarded major transition |
| `register_migration()` | Регистрирует migration step в shared registry |
| `migrate_policy_ir()` | Прогоняет payload через canonical migration chain |

Full reference: [docs/reference/ir/](../../../../docs/reference/ir/index.md)

## Текущее состояние

- Последнее обновление: 2026-04-03
- Files: 5 Python files
- Exports: 6 public names in `__init__.py`
- Current migration chain: только Trinity `1.0 -> 1.0`; observation additions не вводят отдельной migration ветки
