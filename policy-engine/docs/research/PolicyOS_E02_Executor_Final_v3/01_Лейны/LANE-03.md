# LANE-03 — Empirical scope, predictive calibration и историческая проверка

**8 исполнительских пакетов. Документы подготовлены; реализация и будущие проверки NOT_RUN.** Основание аудита: `20d9009be21097bfbdc38a546a15cc60213b8ace`. Полнота аудита не означает закрытого ремонта. Общие условия: [правила исполнения](../00_Общее/Правила_исполнения_и_приёмки.md).

## Практический результат

Полезный прогноз, численные интервалы и измеренный holdout результат доходят до свежего потребителя с точным смыслом, источником, единицами, знаменателем и ограничениями. Хорошие числа не создают causal/production authority. Unknown empirical scope не уничтожает допустимую candidate/descriptive работу. Existing ETS→report→neutral evidence→service→S10 bridge **уже существует**: не строить его заново.

| Пакет | Исходные IDs | Содержание текущей работы |
|---|---|---|
| [EMP-01](../02_Пакеты/EMP-01.md) | B16, B31, B33 | Unit-stable ValueOuterSet bounds, range policy, selected source/subgroup scope и полезный candidate transport. |
| [FRC-01](../02_Пакеты/FRC-01.md) | B32, LA-051 этап1 | Summary не повышает input limitation; реальные optional refs/уровень и temporal contract без invented strings. |
| [PCL-01](../02_Пакеты/PCL-01.md) | LA-052, LA-053 | Typed/mapping report одинаково ограничивает receipt; canonical numerical owner и конечный lifecycle alias. |
| [FRC-02](../02_Пакеты/FRC-02.md) | LA-051 этап2/accountable closure | Strict integral counters, native existing bridge, selected N4 outcome↔observed relation и scoped experiment. |
| [BKT-01](../02_Пакеты/BKT-01.md) | B166, B169, B170 | Весь admissible historical feature view, cohort fallback lineage, selected metrics profile, trajectory semantics и полезный ensemble. |
| [BKT-02](../02_Пакеты/BKT-02.md) | B167, B168, B171 | Numerical-range partial preservation; completeness, nominal/type, micro/macro и comparability policy. |
| [BKT-03](../02_Пакеты/BKT-03.md) | B172, B173 | Stable signed mean и genuine backend identity; full CAS/C5b/packet qualification. |
| [BKT-04](../02_Пакеты/BKT-04.md) | B174, B175 | Preserve/qualify выбранных CV folds и early bootstrap selector; intended caller/metric/sampling policy. |

Полные JSON companions находятся в `04_Трассировка/<ID>.json`: 32 audit residual records, 35 remaining obligations и 63 preservation obligations связаны с61 REQ и60 TEST. Это полнота документа, **не**60 выполненных тестов. LA-051 имеет две фазы, но один исходный ID и одного accountable owner FRC-02.

## Порядок, общие файлы и зависимости

1. **EMP/FRC:** исходный CYC-01 предшествует EMP-01/FRC-01 как контракт выбранного candidate/world context. Выполненный predecessor не требует нового patch. EMP-01 закрывает selected data scope и численный boundary; FRC-01 — summary/status/ref transport. Их ограниченные результаты могут быть полезны до полного bridge.
2. **PCL/FRC-02:** PCL-01 нормализует известный continuous report contract на actual dispatcher boundary, не вносит Foundry dependency внутрь generic IR. FRC-02 зависит по исходному плану от FRC-01/PCL-01/EMP-01; native bridge и relation-путь принимаются вместе. Не ждать завершения всех backtesting helpers, если их механизм не затронут.
3. **BKT-01→02→03:** сначала actual view/trajectory/profile/cohort, затем evaluator/aggregate/IR completeness и numeric range, затем descriptive reduction/backend/fresh packet. Один writer `orchestrator.py` и согласованный owner `ir/analytics/backtest.py`: C33 overflow и C34 cancellation — два разных regression, хотя используют общий численный контракт.
4. **BKT-04** независим по исходному predecessor graph. CV selection before materialization и bootstrap selector before RNG сохраняются. У него нет обязанности автоматически подключать helper ко всем runtime/GY путям; actual intended consumer сначала устанавливается конечным census.
5. **Cross-lane:** LANE-01 предоставляет selected candidate/source/context и acquisition; LANE-04 — настоящий dispatcher/numerical execution; LANE-05 — causal estimand/interval semantics, которые нельзя заменять predictive coverage; LANE-06 — native exact-profile CAS, budget/cost и persistence. Эти read-contract impacts не создают новую глобальную архитектуру.

`generation_cycle.py` и predictive service/source schemas согласуются с CYC/ACQ владельцами; PCL report normalizer — с dispatcher owner. Не редактировать общий файл конкурентно и не менять worktree во время test job. Historical path-map/MOVE-17 — подсказка истории, actual пути закреплены в карточках.

## Общая интеграция, не восемь тяжёлых suites

Канонический контракт и инфраструктура: [03_Интеграция/LANE-03.md](../03_Интеграция/LANE-03.md). Здесь только распределение ответственности.

| Scenario ID | Ответственный механизм | Обязательные варианты |
|---|---|---|
| **E02-I03-A** | EMP-01 source/value scope; FRC-01 summary | Unit conversion и extreme finite bounds, subgroup/source limitation, limited input не становится pass от10/10 counts; полезный conditional forecast сохраняется. |
| **E02-I03-B** | FRC-02 real ETS/service bridge; PCL-01 receipt boundary | Одинаковые train/shape, разные holdout; nominal не observations; fractional counts; exact selected refs/time/model/rule; typed/JSON receipt equivalence; положительная selected outcome relation и адресный fallback без неё. |
| **E02-I03-C** | BKT-01 input/execution, BKT-02 evaluation, BKT-03 fresh packet; BKT-04 lightweight caller variant | Actual prefix refs и derived leakage control; scalar/trajectory/selected-profile; cohort preservation; complete/partial/range-limited reports; micro invariance; constant/cancellation residual; real SciPy/unavailable; full CAS/C5b/packet. CV/bootstrap variants только по actual intended caller. |

Переиспользовать существующие `test_frc_02_empirical_bridge.py`, `test_predictive_calibration_profile_owner_binding.py`, `test_backtesting.py`, `test_bkt_02.py`, `test_bkt_03.py`, `test_decision_packet_node_v3.py`, `test_cv.py`, `test_bootstrap.py`. Карточки указывают точные paths/selectors; новые TEST-IDs — требования, не выдуманные существующие pytest имена. Одно evidence может обслужить несколько REQ только при совпадающих inputs/profile/backend; это не несколько независимых научных экспериментов.

## Положительные способности, которые нельзя свести к запуску pytest

- EMP-01: выбранные source population/time/subgroup и настоящий causal graph transport, а не страна/маска как универсальное доказательство.
- FRC-01: реальные optional source/method/sensitivity refs либо честное отсутствие, не fabricated authority-shaped URI.
- FRC-02: применимая persisted outcome↔observed relation; unconditional N4 refusal заменяется только после проверенного positive path. Series calibration остаётся доступной без relation.
- BKT-01: допустимые feature dependencies/as-of и semantic trajectory contract; один полезный coordinate-wise ensemble, не scalar average+repetition.
- BKT-02: comparable quantities/units/weights до pooling; per-stratum output при несовместимости.
- BKT-04: selected consumer metric denominator и sampling unit; generic helper может оставаться public-only без фиктивной runtime activation.

Конечные DEC в карточках задают варианты, критерий и обязательный результат. Unknown corpus/issuer не превращать в fabricated authority; scientific qualification остаётся отдельно от принятого software repair.

## Совместимость и приёмка

P-CORE — Python3.14 по project lock; P-ANALYTICS — actual selected numeric backend/extras. Никаких автоматических installs. Controlled synthetic inputs/LLM proposals/clock/faults допустимы для механизма; numerical producer, canonical serializer/CAS, selected resolver и fresh consumer нельзя подменять готовым ответом там, где они принимаются.

Сохранить historical ValueOuterSet/evidence/report bytes и versioned read semantics; old scalar/list либо old positive receipts не переаттестовываются автоматически. Alias retirement PCL-01 требует finite surface census/поддержанного окна; default retain. Numerical range repair не ослабляет strict source reconciliation, не подставляет0/inf и не выбрасывает годные rows. Rollback capability возвращает адресную limitation, а не прежний false positive.

На сдачу: base/patch, точные owner/caller maps, REQ→TEST→shared variant→actual command/log/exit, independent oracles, old-mechanism/removal controls, полезный positive consumer result, historical compatibility и открытые scientific decisions. Отдельно source-only, fixture, native и practical scientific evidence. Наличие теста, bounded MATCH и написанный документ не означают product PASS.

## Design direction без догматизма

[Universal policy target — D0](../05_Основания/Архитектура/universal-policy-design-target-architecture-and-gap.md): reusable typed source/quantity/trajectory/measurement contracts позволяют новый совместимый случай без новой ветки по названию политики. LLM предлагает смысл/метод; система проверяет конкретные применимость и данные, а не обязана детерминированно изобретать любые модели.

[Evidence substitution — K01, K07–K08](../05_Основания/Архитектура/wave5-evidence-substitution-ratification.md): numeric consistency, source identity, current applicability и authority различны. LK01/LK29/LK30 сохраняют различие predictive calibration, simulator parameter calibration, drift monitoring, S10 record и production admission. Новая общая способность допустима; новый global calibration/replay/provenance service здесь не нужен.

## Адресные уточнения PROPOSED v2 — ещё не утверждены

BKT-02: finite representable residual/absolute_error остаётся useful comparison row и даёт representable MAE/RMSE даже при unavailable residual²/SSE. Versioned sufficient-stat availability и numerical-range limitation отдельно от row validity; requested denominator/trust не повышаются. TEST-BKT-02-01/02/05/07 расширяют E02-I03-C actual evaluator→persistence→fresh reconciliation; новый shared harness не создаётся.

Основание: FN-BKT-RANGE. Все будущие product tests NOT_RUN; изменения ожидают независимого peer review.
