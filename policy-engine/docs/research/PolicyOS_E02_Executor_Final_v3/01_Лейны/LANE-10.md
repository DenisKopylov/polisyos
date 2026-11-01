# LANE-10 — Калибровка, совместный закон и честная исследовательская область

**Статус: SPECIFICATION_NOT_IMPLEMENTED; все будущие тесты NOT_RUN.**

## Точные пакеты

- [CAL-02](../02_Пакеты/CAL-02.md) · [JSON](../04_Трассировка/CAL-02.json)
- [CAL-03](../02_Пакеты/CAL-03.md) · [JSON](../04_Трассировка/CAL-03.json)
- [CAL-04](../02_Пакеты/CAL-04.md) · [JSON](../04_Трассировка/CAL-04.json)
- [CAL-06](../02_Пакеты/CAL-06.md) · [JSON](../04_Трассировка/CAL-06.json)
- [UQS-01](../02_Пакеты/UQS-01.md) · [JSON](../04_Трассировка/UQS-01.json)
- [UQP-01](../02_Пакеты/UQP-01.md) · [JSON](../04_Трассировка/UQP-01.json)
- [UQP-02](../02_Пакеты/UQP-02.md) · [JSON](../04_Трассировка/UQP-02.json)
- [UQP-03](../02_Пакеты/UQP-03.md) · [JSON](../04_Трассировка/UQP-03.json)
- [DOE-01](../02_Пакеты/DOE-01.md) · [JSON](../04_Трассировка/DOE-01.json)
- [DOE-02](../02_Пакеты/DOE-02.md) · [JSON](../04_Трассировка/DOE-02.json)
- [DOE-03](../02_Пакеты/DOE-03.md) · [JSON](../04_Трассировка/DOE-03.json)
- [STR-01](../02_Пакеты/STR-01.md) · [JSON](../04_Трассировка/STR-01.json)

## Порядок и общие owners

1. CAL-01 (LANE-07) предоставляет measurement alignment/split; CAL-02 исправляет только потребление fit mask и stable scale. Затем CAL-03 finite admission и CAL-04 final snapshot. Один writer `foundry/calibration/calibrator.py`; согласовать final objective/state identity до native wave.
2. UQP-01 effective invocation → UQP-02 joint law → UQP-03 result/stop semantics. CAL-06 зависит от CAL-04 и UQP-02; UQS-01 — от CAL-06/UQP-02. Это DAG, не круговое ожидание всего lane.
3. DOE-01 → DOE-02 → DOE-03: один source-design contract/seed/trajectory owner, не три реестра. STR-01 независим по исходному плану и потребляет конечный stress plan; selected intent связывается с существующим request/run-state.
4. DOE/STR принимаются в исходном CP3, CAL/UQ — CP4. Shared files leases согласовать; native JAX/SALib jobs не запускаются параллельно на одном ресурсе.

## Содержательная связанная приёмка

- **E02-I10-A:** реальный tiny differentiable mechanism → training-only fit → finite selected state → report/typed tied covariance. Численные regressions CAL-02/03/04/06 имеют собственные exact oracles. Shared run не заменяет отдельный stationary-tie/overflow контроль.
- **E02-I10-B:** complete fixed/varying invocation → один Gaussian/empirical joint law → delta/MC → actual persisted/fresh consumer. Point mass, tiny empirical tail, mean outside interval, conditional failures и repeated information units должны сохранять свой смысл.
- **E02-I10-C:** actual source design → evaluation → sensitivity/stress. Failed/imputed rows и selected objective intent не скрываются. Useful partial result сохраняется; новый compatible design идёт через общий owner.

Канонические [shared scenarios](../03_Интеграция/LANE-10.md) — единственный integration harness contract. Локальные тесты расширяют существующие owners, не 12 дубликатов полного pipeline. Cross-lane practical stories E02-X01/X02/X03/X04 используют результаты, но не превращают numerical smoke в доказательство реального causal effect.

## Что является отдельной положительной работой

UQS-01 — source-bound independent fusion, не только conservative hull; DOE-01/02 — exact design handoff, не новый fingerprint от текущего plan; STR-01 — independently selected intent, не self-issued rule. CAL-06 сохраняет пригодную A/B uncertainty при unknown C. Каждый missing owner получает bounded inventory/contract/implementation branch и честный unresolved outcome, а не формальное закрытие G запуском тестов.

## Профиль и evidence

Python >=3.14,<3.15, actual lock; native JAX/jaxlib/optax и sensitivity SALib1.5.2 согласно выбранному resolved profile. Не вводить global x64/XLA flags без contract. Allowed seams: synthetic inputs/fixed seed/isolated store, transport spies для передачи kwargs. Для native claim нельзя заменить JAX derivatives/optimizer, SALib, joint sampler, actual persistence или проверяемый fresh reader.

Приёмка ремонта: changed mechanism различается negative oracle, полезный positive path достигает consumer, все preservation bindings выполняются. Предметная validation: representativeness, causal identification, posterior mixing/coverage, missingness, PCA units и stress coverage — отдельные evidence/claims, не автоматически PASS от локальной арифметики.

## Адресные уточнения PROPOSED v2 — ещё не утверждены

CAL-02 исключает evaluation observations до nonlinear loss/AD; zero contribution masked цели допустим только рядом с supported sibling, весь empty fit остаётся no-fit/refusal, model-finiteness guard не маскируется. UQS-01 потребляет общий FED-01 finite-binary64 mean/midpoint owner с предпочтением qualified statistics.mean; Decimal.from_float precision1200 сохраняет независимый arithmetic cross-check без изменения information-unit pooling. DOE-02/03 включают PCA в local stage RNG/source profile. TEST-DOE-03-03 разделяет analytic direct DCT solver fixture и source-bound parameter-only Legendre/Morris model: finite seed preflight, rank/gap/source hashes замораживаются до tested PCA. TEST-DOE-02-02/03 и TEST-DOE-03-05 проверяют whole-pipeline replay/external RNG и fresh provenance. Эти расширения используют прежние shared scenarios/IDs, не подменяют их новым harness.

Основание: FN-CAL-MASK, FN-UQS-STDLIB, FN-DOE-PCA-RNG. Все будущие product tests NOT_RUN; изменения ожидают независимого peer review.
