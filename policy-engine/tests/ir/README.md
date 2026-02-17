# IR Tests

`tests/ir` проверяет слой `polisyos.ir`: loaders/migrations, registry fragments, аналитические модели и архитектурные ограничения IR.

Актуально на **17 февраля 2026**.

## Состав

- `10` файлов `test_*.py`

## Что покрывается

- Загрузка и миграции:
  - `test_loaders.py`
  - `test_trinity_loaders.py`
  - `test_registry_fragments.py`
  - `test_registry_fragments_components.py`
- Контракты данных/аналитики:
  - `test_queries_contracts.py`
  - `test_uncertainty.py`
  - `test_hte_backtest.py`
  - `test_policy_portfolio.py`
- Архитектурные инварианты:
  - `test_no_core_imports.py` (запрет `ir -> core` imports)
  - `test_canon_hash_parity.py` (parity с `core.canon`)

## Роль в системе

- IR остается независимым модельным слоем.
- Контракты IR остаются совместимыми для downstream слоев (`fabric`, `foundry`, `scientist`).

## Связи с кодом

- `policy-engine/src/polisyos/ir`
- `policy-engine/src/polisyos/ir/trinity`
- `policy-engine/src/polisyos/ir/analytics`

## Запуск

```bash
pytest tests/ir -q
pytest tests/ir/test_no_core_imports.py -q
pytest tests/ir/test_loaders.py -q
```
