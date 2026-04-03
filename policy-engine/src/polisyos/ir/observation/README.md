# Observation (`polisyos.ir.observation`)

`polisyos.ir.observation` связывает сырые measurement/panel данные с causal и
policy execution surface. Пакет вводит семейства наблюдений, entity scopes,
measurement governance, compiler suites и bundle contracts, через которые
`scientist` и `foundry` получают проверяемые observation-derived inputs вместо
ad-hoc in-memory structures.

## Роль в системе

- **Зависит от:** `polisyos.ir.analytics`, `polisyos.ir.artifacts`, `polisyos.ir.kernel`, selected `polisyos.foundry` protocol contracts
- **Используется в:** `polisyos.scientist.causal`, `polisyos.scientist.governance`, `polisyos.foundry.calibration`, `polisyos.foundry.methods`
- Observation layer формирует мост между measurement reality, governance policies и executable causal tasks.

## Ключевые концепции

- **Observation families** — `ObservationFamily`, `EntityScope` и `ObservationRecord` нормализуют source data.
- **Measurement governance** — registries для trust tiers, proxy rules, schema regimes и shock/regime calendars.
- **Family policy mapping** — `ObservationFamilyPolicyRegistry` и governance alias registries сопоставляют family-specific readiness с runtime passes.
- **Contract compilation** — `ObservationContractCompilerSuite` компилирует panel/network/survey/specification-curve payloads в foundry-friendly bundles.
- **Readiness bundles** — `CausalReadinessBundle` агрегирует proxy, transportability, counterfactual и strategic readiness entries.
- **Execution bundles** — `CausalExecutionBundle` несет bounds estimation и temporal DTR tasks для downstream execution.

## Public API

| Type/Function | Description |
|---|---|
| `ObservationRecord`, `ObservationPanel` | Базовые observation contracts для record/panel data |
| `MeasurementRegistry` | Registry measurement trust tiers, proxy rules и freshness logic |
| `SchemaRegimeRegistry`, `RegimeCalendar`, `ShockCalendar` | Контракты regime changes и structural breaks |
| `ObservationFamilyPolicyRegistry` | Family-level governance policy and pass mapping registry |
| `ObservationContractCompilerSuite` | Основной compiler suite для observation-to-contract pipelines |
| `CalibrationTargetBundleCompiler` | Компилятор observation panels в calibration target bundles |
| `CausalReadinessBundle` | Bundle readiness signals для proxy/transport/strategic/counterfactual checks |
| `CausalExecutionBundle` | Bundle executable causal tasks для bounds и temporal DTR execution |

Full reference: [docs/reference/ir/](../../../../docs/reference/ir/index.md)

## Текущее состояние

- Последнее обновление: 2026-04-03
- Files: 9 Python files
- Exports: package facade re-exports 8 implementation modules; verified implementation surface contains 159 class/function definitions
- Detailed export groups: `bundles.py` exports 53 names, `contract_compilers.py` 51, `measurement.py` 13, `governance.py` 9
