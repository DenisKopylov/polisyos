# Contract Tests

`tests/contract` проверяет стабильность контрактов между слоями: модели IR, ABI-снимки, typed refs, migration/compatibility правила и golden records.

Актуально на **17 февраля 2026**.

## Состав

- `18` файлов `test_*.py`
- `1` `conftest.py` (fixture `golden_records` из `golden_records.json`)

## Что покрывается

### Trinity / IR контракты

- `test_trinity_contracts.py`
- `test_trinity_migration.py`
- `test_trinity_linker_contract.py`
- `test_ir_migrations.py`

Проверяются: валидность Trinity bundle, linker-ограничения, миграции schema-version, совместимость загрузчиков.

### Foundry / Scientist / Core contract surface

- `test_foundry_facade_contracts.py`
- `test_foundry_input_bindings_contract.py`
- `test_scientist_workflow_spec_contract.py`
- `test_kernel_models.py`

Проверяются: canonical serialization, typed artifact refs, input bindings, kernel model invariants.

### Governance / World / Citation контракты

- `test_gate_models.py`, `test_gate_protocol.py`
- `test_world_abi_contract.py`
- `test_citations_contract.py`
- `test_applicability_contract.py`

Проверяются: human-gate модели и протокол, world entities/ids, citation/locator правила, applicability refs.

### Совместимость и стабильность

- `test_abi_diff_tool.py`
- `test_golden_record_ids.py`
- `test_run_experiment_slo.py`
- `test_slo_metrics.py`
- `test_security_metrics_helpers.py`

Проверяются: ABI diff budget, стабильность canonical hashes/ID, SLO и security telemetry helpers.

## Связи с кодом

- `policy-engine/src/polisyos/core/contracts`
- `policy-engine/src/polisyos/ir`
- `policy-engine/src/polisyos/foundry`
- `policy-engine/src/polisyos/scientist`
- `policy-engine/tools/diagnostics/abi_diff.py`

## Запуск

```bash
pytest tests/contract -q

# точечно
pytest tests/contract/test_trinity_contracts.py -q
pytest tests/contract/test_abi_diff_tool.py -q
pytest tests/contract/test_golden_record_ids.py -q
```
