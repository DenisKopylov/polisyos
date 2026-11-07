# ECO-01 — две экономические модели и сохранённый normalized-income baseline
## C38 · 31 октября 2026 года

**Исходные IDs:** LA-004, LA-035. **Порядок:** 38/127. **Срез:** `20d9009be21097bfbdc38a546a15cc60213b8ace`. Только аудит.

## Решение

**Содержательные исходные требования присутствуют:** два неэквивалентных economic профиля не слиты; существующая таблица явно разделяет их state, units, clock, tax base/debit, RNG и budget. Старый `policy_loss_fn` теперь принадлежит economic baseline owner, aliases сохраняют identity и исходную формулу.

**22 MATCH, 0 ERROR ограниченного финального запуска; новых R-находок не установлено.** Constant −1 в positive regime не «исправляется» тайно другим welfare objective. Новый optimizer не является prerequisite исходного relocation. Native JAX/state/consumer/import qualification остаётся отдельно незакрытой.

## 1. Матрица исходных задач

| ID | Что установлено | Остаток |
|---|---|---|
| LA-004 | Реальные разные ABI/laws сохранены, profile table существует; matched и divergent observables различены | C38-G01: native chain; C38-G02: конкретный mapping/units/calibration при подстановке |
| LA-035 | `economics/baselines.normalized_income_budget_loss` — единственный owner; старые aliases; реальная formula и guard body | C38-G01: JAX/JIT/grad/import tests; C38-G03: supported caller/lifecycle scope, без требования нового optimizer |

[Полная карточка](../05_Источники/ECO-01_исходные_строки.txt), строки 4711–4892, включая AM02. Позднее замечание о прежнем train не доказывает состояние сегодняшнего high-level training API; LA-023 будет оцениваться в собственном пакете. LK04/LK06/LK08 сохранены: полезные numeric checks, registry view и DomainPlugin ABI не удаляются по сходству названий.

## 2. Конечная таблица текущих профилей

| Ось | GlobalState / PatchMap | Economics plugin |
|---|---|---|
| Результат | PatchMap плюс key; отдельный merge/state consumer | Replacement EconomicState |
| Налоговая база | `reported_income` | **`income`**, marginal brackets и policy multiplier |
| Счёт списания | `agents.income` | **`agents.wealth`**, income не меняется |
| Government balance | Равный противоположный tax/subsidy patch | Такого поля/контрсчёта нет |
| Target/population | Active ∩ target mask | Active mask в выбранных операциях; native target-mask API нет |
| Labor law | Threshold resampling, uniform firm assignment, wage offer × skill | Finding/separation transitions, wage shocks, minimum wage × 2000, hours |
| Employment accounts | Employer IDs, firm labor counts | Employed/hours; нет firms/employer IDs |
| Seed | Fiscal key неизменен; labor возвращает третий split key | Возвращается state; supplied key или fallback domain time_step |
| Clock/units | Суммы за выбранный kernel call; native execution step | Supplied amounts; ×2000 для wage floor, /12 для interest; composite clock и domain clock различны |

Это уже отражено в существующем README и проверяется найденными consumer tests; не требуется новый реестр профилей. **Списание wealth не означает налоговую базу wealth.** Calendar conversion, currency meaning и калибровка не выводятся из коэффициентов. [S12:1–54](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/plugins/economics/README.md#L1-L54) [S07:12–48](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/plugins/economics/mechanisms.py#L12-L48) [S07:88–185](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/plugins/economics/mechanisms.py#L88-L185)

## 3. Совпадающие частные regimes не делают модели заменами

P11 flat 25% bracket при одинаковом one-period income даёт одинаковые debit amounts `[25,50]`: native уменьшает income и добавляет government 75, plugin уменьшает wealth и не имеет counteraccount. P12 подстановка wealth вместо income меняет debit на `[250,250]`; это не допустимая неявная конверсия. P13 действующие progressive brackets на income `[25000,50000]` дают debit `[3250,7700]`; при нулевом начальном wealth результат отрицателен. **Gini refresh в probe не исполнялся**; найденные native tests отдельно требуют отказа classical Gini на таком active population. [S07:29–48](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/plugins/economics/mechanisms.py#L29-L48) [S22:237–259](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/foundry/plugins/test_economic_profiles.py#L237-L259)

P14 uniform income 100, non-means-tested transfer и нулевой unemployment benefit совпадают с subsidy rate 0.25 по `[25,25]`, но default means testing даёт `[24.75,24.75]`. Совпадение частной формулы не добавляет plugin government balance и не переносит state ABI. [S07:51–80](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/plugins/economics/mechanisms.py#L51-L80)

P15 transition finding/retention даёт employment `[True,True]`, threshold 0 — `[False,False]`. P16 специально совпавший zero-job regime оставляет обе income arrays нулевыми, но не создаёт у plugin employer IDs, firms или возвращаемый key. P17 наблюдает routing supplied key и fallback от domain clock; **RNG scripted, не JAX**. [S07:83–135](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/plugins/economics/mechanisms.py#L83-L135) [S15:43–95](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/execute/mechanisms/labor.py#L43-L95)

P18 показывает дополнительный предел: plugin active mask исключает inactive agent из find/separation, но wage/income fields не обещаны полностью замороженными. Нельзя переносить более сильный native non-target preservation contract на все plugin fields. Это зафиксировано как различие области модели, не как доказанный сбой authoritative consumer.

P20 исполняет exact ordinary `CompositeExecutor.step` с fixture registry/state: enabled-mechanism filter выбирает taxation, composite clock увеличивается, domain clock остаётся прежним. Настоящие aggregate refresh, selected-Gini admission и complete chex state не исполняются. P21 сохраняет наблюдаемые outputs через ordinary JSON, не CAS. P22 проверяет destination dtype casts только на NumPy backend. [S13:339–376](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/plugins/composite.py#L339-L376)

## 4. Baseline перенесён без подмены цели

Канонический owner содержит формулу:

```text
−mean(income) / max(mean(abs(income)), 1)
+ 10 × (max(min_balance − government_balance, 0) / max(abs(min_balance), 1))²
```

Inputs/calculation — исторический float32 профиль; default minimum −1000. P01 исполняет оба точных aliases и actual reexport helper: callable identity совпадает. Public loss facade по-прежнему использует общий reexport helper; его нельзя удалить вслед за отдельной layout миграцией. [S01:13–42](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/plugins/economics/baselines.py#L13-L42) [S02:1–7](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/_internal/loss.py#L1-L7) [S03:1–5](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/loss.py#L1-L5) [S04:1–26](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/_internal/reexport.py#L1-L26)

P02 сверяет девять regimes с отдельными ручными/Fraction oracles: zero 0, positive −1, negative +1, mixed −3/11, budget breach 9, minimum 0 → penalty 40 и положительный minimum. P03 `[1,−6,2]` при inactive middle entry даёт +1/3: **historical population включает все переданные entries**. P04 добавление нулевого padding меняет low-scale score −0.5 на −0.25. Это не новая active-mask policy. [S01:24–40](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/plugins/economics/baselines.py#L24-L40)

P08 positive scale 1/10/1e6 даёт −1. P19 actual GDPObjective на EconomicState агрегатах различает GDP 300 и 3000, а baseline остаётся −1. Следовательно, GDP/welfare не drop-in successor. P10 EconomicState-shaped input без government_balance отказан AttributeError, а не молча интерпретирован как GlobalState.

## 5. Реальный guard body и границы исполнения

В отличие от прежнего historical probe с identity helper, здесь исполняется **точный `finite_loss_or_inf` body**: P05 все девять nonfinite placements income/balance/minimum возвращают +inf; P06 конечные source inputs с переполнением mean/penalty также заканчиваются +inf; P07 finite vector сохраняется, vector с NaN целиком становится +inf. P09 empty supplied population даёт +inf, не успешный score. Но backend — NumPy-as-jnp, **не native JAX guard/JIT/autodiff**. [S05:161–166](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/execute/_internal/numeric/__init__.py#L161-L166)

Полные native tests уже включают настоящий GlobalState, actual guard, JIT/gradients, all-entry population, fresh-import side-effect checks и registered/composite consumers. Документированное прежнее technical closure исходного LA-035 прочитано и не отменяется искусственным требованием нового optimizer; одновременно оно не превращено в текущий native PASS. [S20:1–116](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/foundry/plugins/test_historical_income_baseline.py#L1-L116) [S21:1–233](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/foundry/plugins/test_economic_profile_consumers.py#L1-L233) [S18:25–46](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/docs/reference/foundry/economic-baseline-profile.md#L25-L46)

Первый harness запуск остановился на неверном извлечении indented method. Исправлен только harness, точный class shell/step извлечён без редактирования product source; полный повтор дал **22 MATCH / 0 ERROR**. Оба logs сохранены. Native pytest попытка на трёх focused files завершилась до collection: `No module named pytest`, exit 1. Ничего не устанавливалось.

## 6. Сохранить и проверить дальше

Сохранить оба профиля, существующую таблицу, named historical baseline и numeric guards. Выполнить найденные native tests в поддерживаемой среде; при конкретной модели/подстановке проверить её units, population, clock, accounting и эмпирические основания. Dynamic external/serialized callers нужны для lifecycle удаления aliases, а не как повод заново проектировать optimizer.

[Диагностика](../04_Проверки/C38_ECO01/bounded_diagnostics.json) · [Команды](../04_Проверки/C38_ECO01/commands.json) · [Native границы](../04_Проверки/C38_ECO01/native_verification.json) · [Источники](../05_Источники/C38_источники.json) · [Остатки](../01_Реестры/C38_остатки.json).

**38/127 пакетов рассмотрены ограниченно; следующий — PLG-01. Полного закрытия нет.**
