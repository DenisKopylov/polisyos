# Core Tests

`tests/core` покрывает фундамент `polisyos.core`: базовые сервисы, security, contracts/components integration и phase0 primitives.

Актуально на **17 февраля 2026**.

## Состав

- `52` файла `test_*.py`
- `1` `conftest.py` (в `phase0/`)

## Структура

| Подкаталог | `test_*.py` | Что покрывает |
|---|---:|---|
| `core/` (корень) | 10 | cache/pipeline/registry/hashing/llm/discovery/error base |
| `core/phase0/` | 21 | CAS, canon, signing, run context, observability |
| `core/security/` | 16 | identity/authz/router/cell/tenant/RLS/TEE/SBOM/delegation |
| `core/components/` | 3 | bootstrap idempotency, connector-kind compliance, legacy entry-point gates |
| `core/contracts/` | 2 | execution-plan contracts, IR facade refs |

Детали phase0: `policy-engine/tests/core/phase0/README.md`.

## Роль в системе

- Ядро тестовой надежности для остальных слоев (`ir`, `fabric`, `foundry`, `scientist`, `runtime`).
- Проверка security-инвариантов на уровне middleware и storage backends.
- Контроль стабильности registry/contracts surfaces, на которые завязаны остальные подсистемы.

## Связи с кодом

- `policy-engine/src/polisyos/core`
- `policy-engine/src/polisyos/core/security`
- `policy-engine/src/polisyos/core/components`
- `policy-engine/src/polisyos/core/contracts`

## Запуск

```bash
pytest tests/core -q
pytest tests/core/security -q
pytest tests/core/components -q
pytest tests/core/contracts -q
pytest tests/core/phase0 -q
```
