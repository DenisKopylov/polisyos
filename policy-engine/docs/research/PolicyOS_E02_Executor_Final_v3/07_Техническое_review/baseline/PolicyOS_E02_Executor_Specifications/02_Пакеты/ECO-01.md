# ECO-01 — Два economic профиля и предметный baseline objective

## 1. Паспорт и результат

**LANE-04 · CP4 · основание 20d9009be21097bfbdc38a546a15cc60213b8ace · статус: ТЗ, не выполнено.** Технический исполнитель и reviewer назначаются проектом. Исходные ID: LA-004, LA-035. Тип: model-profile/baseline native qualification.

Сохранить две разные economic модели и named historical objective; доказать правильное потребление в declared profile без скрытой смены цели.

Основания: [аудит](../05_Основания/Аудит/02_Пакеты/ECO-01.md), [все остатки](../05_Основания/Аудит/01_Реестры/C38_остатки.json), [неизменная исходная карточка](../05_Основания/Аудит/05_Источники/ECO-01_исходные_строки.txt), исходный объединённый план §ECO-01 (исторические строки 4711–4892).

## 2. Уже работает — сохранить

- GlobalState/PatchMap и EconomicState replacement остаются разными ABI; существующая таблица units/clock/base/debit/RNG/accounting сохраняется.
- Plugin tax base income, debit wealth; native reported-income debit income плюс government counteraccount. Нет implicit calendar conversion/target-mask parity.
- Named float32 normalized-income baseline, all-entry population, constant−1 positive regime, budget penalty и actual finite guard. Новый optimizer не обязателен.

Изменение продукта требуется только при воспроизведённом несоответствии ниже; отсутствие native проверки само по себе не дефект. Не создавать искусственный рефакторинг для отчёта.

## 3. Полнота обязательств и disposition

| Основание | Решение | Требования |
|---|---|---|
| C38-G01 | qualify: Настоящие state/JAX/guard/JIT/grad/import/composite consumers, selected Gini domain и dtype. | REQ-ECO-01-01, REQ-ECO-01-02 |
| C38-G02 | qualify: Конкретная подстановка требует explicit observable mapping/units/clock; совпадающий debit не full equivalence. | REQ-ECO-01-01 |
| C38-G03 | lifecycle: Сохранить exact baseline formula/callers; новый objective только отдельным выбором, alias retirement по census. | REQ-ECO-01-02, REQ-ECO-01-03 |

### Исходные обязанности, не только новые R

- LA-004/AM02: richer plugin не доказанная замена; историческое train без update superseded current PLG-02/03 audit и не основание повторно объявить нынешний train фиктивным.
- LA-035 relocation выполнен; GDP/welfare objectives не drop-in successor. Constant−1 — определённая нормализация, не автоматический bug.
- LK04 сохраняет finite/nonnegative/probability helpers с их error/clamp semantics; LK06 registry-view и LK08 DomainPlugin lifecycle не сливаются с kernel.

## 4. Нормативный контракт

### REQ-ECO-01-01
Существующая economic profile table и actual consumers сохраняют state/units/clock/tax base/debit/masks/RNG/accounting distinctions. Flat25% на income[100,200] даёт одинаковый debit[25,50] только как выбранный observable: native уменьшает income и government+75, plugin уменьшает wealth без такого counteraccount. Любая подстановка должна задать mapping и rejected unsupported fields, не выдумывать accounts/calendar. Composite clock и domain clock квалифицируются отдельно; current selected Gini domain не обходится.

Источник: LA-004; аудит: C38-G01, C38-G02; проверки: TEST-ECO-01-01.

### REQ-ECO-01-02
normalized_income_budget_loss сохраняет float32 law −mean(income)/max(mean(abs(income)),1)+10*(max(min_balance−balance,0)/max(abs(min_balance),1))², default min−1000 и все supplied entries. Positive regime mean≥1 остаётся−1 при scaling; zero0, negative+1, breach example9; empty/nonfinite/overflow→+inf через настоящий finite_loss_or_inf. JIT/grad native согласованы, EconomicState без government_balance не притворяется compatible.

Источник: LA-035; аудит: C38-G01, C38-G03; проверки: TEST-ECO-01-02.

### REQ-ECO-01-03
Old policy_loss_fn aliases сохраняют callable identity и поддержанные import/FQN/serialized consumers до отдельного окна. Если пользователю нужен иной income/welfare ranking, это отдельный named objective/version с независимым oracle, не silently edited baseline. Текущее technical closure relocation не означает свежий native PASS, но не требует нового optimizer для повторного закрытия.

Источник: LA-035; аудит: C38-G03; проверки: TEST-ECO-01-03.

## 5. Техническое решение и producer → consumer

Переиспользовать existing economics/README profile table и baselines.py, не создавать parallel taxonomy. Native test_economic_profiles/consumer checks связывают обе модели с actual state/update_aggregates, а baseline tests — с real numeric guard. Исправлять лишь воспроизведённую profile routing ошибку; нет основания merge fiscal kernels или менять историческую formula. Source plan фраза «wealth tax» уточняется текущим кодом: income-base, wealth-debit.

### Проверенные owners на срезе
- policy-engine/src/polisyos/foundry/plugins/economics/baselines.py: normalized_income_budget_loss
- policy-engine/src/polisyos/foundry/plugins/economics/mechanisms.py: TaxationMechanism.apply, LaborMarketMechanism.apply
- policy-engine/src/polisyos/foundry/plugins/composite.py: CompositeExecutor.step
- policy-engine/src/polisyos/foundry/execute/_internal/numeric/__init__.py: finite_loss_or_inf
- policy-engine/src/polisyos/foundry/methods/_internal/loss.py: historical alias

Выделять shared pure primitive только при доказанном совпадении конкретной операции. Унификация по class name уничтожает разные accounting/state laws.

## 6. Локальная приёмка — все будущие проверки NOT_RUN

### TEST-ECO-01-01
- Уровень: unit + targeted native integration.
- Setup: Real GlobalState и EconomicState, flat/progressive tax, ordinary CompositeExecutor; fixed key, unequal wealth vs income; active/inactive examples.
- Действие: Registered dispatch обеих моделей; flat debit control, default progressive income[25000,50000], labor finding/threshold contrast, composite step и selected Gini refusal.
- Точный oracle: Flat[25,50] с разными state effects; progressive[3250,7700] при policy multiplier1. Wealth не tax base. Negative active wealth не проходит classical Gini admission. Native firms/key и plugin hours/domain clock не fabricated equivalent; inactive plugin wages не обещаны frozen.
- Ожидаемый класс: positive + negative + boundary.
- Свидетельство: NOT_RUN; предъявить actual command, runtime/backend/import binding, exit/log, exact observed values; отдельный контроль на прежнем дефекте или отключённом механизме.

### TEST-ECO-01-02
- Уровень: native JAX/JIT/autodiff + real GlobalState.
- Setup: Existing baseline cases: zero/positive/negative/mixed, scales1/10/1e6, min0/−1000/positive, empty/nonfinite/overflow.
- Действие: Call direct/aliases, jit/grad; padding and inactive-entry controls; actual finite_loss_or_inf vector.
- Точный oracle: Exact formula within float32 tolerance; positive−1 and local gradient≈0, breach9; [1,−6,2] gives+1/3 even inactive middle, padding changes low-scale−.5→−.25. Nonfinite/empty/overflow+inf; vector NaN gives whole+inf. Не менять population silently.
- Ожидаемый класс: positive + negative + boundary.
- Свидетельство: NOT_RUN; предъявить actual command, runtime/backend/import binding, exit/log, exact observed values; отдельный контроль на прежнем дефекте или отключённом механизме.

### TEST-ECO-01-03
- Уровень: unit + targeted native integration.
- Setup: Current source/FQN/docs/serialized caller census и fresh package imports.
- Действие: Resolve aliases, inspect import side effects and supported consumers; compare GDP300/3000 with baseline control.
- Точный oracle: Alias identity/catches unchanged; GDP criterion distinguishes magnitude, baseline−1 не переименован GDP objective. Census limited explicitly; no new optimizer requirement or unauthorized retirement.
- Ожидаемый класс: positive + negative + boundary.
- Свидетельство: NOT_RUN; предъявить actual command, runtime/backend/import binding, exit/log, exact observed values; отдельный контроль на прежнем дефекте или отключённом механизме.

Повторно использовать/расширить реальные места, а не создавать 127 harness: `policy-engine/tests/unit/foundry/plugins/test_economic_profiles.py`; `policy-engine/tests/unit/foundry/plugins/test_economic_profile_consumers.py`; `policy-engine/tests/unit/foundry/plugins/test_historical_income_baseline.py`. До выбора selector прочитать полный test/fixture. Это проверенные пути, не утверждение о наличии всех предложенных assertions.

Допустимые doubles: малые synthetic economic values и fixed seeds; без выдуманных реальных units/calibration. Запрещено: NumPy/replace-state/identity guard вместо final JAX/state; fixture coincident outputs как evidence full equivalence.

## 7. Общая интеграция и порядок

FRY-03 baseline run и PLG-03 actual train находятся рядом, но не взаимозаменяемы. Shared tiny native profile witness подтверждает declared observables, не universal economics.

Точные общие сценарии: E02-I04-C из [контракта интеграции](../03_Интеграция/LANE-04.md); одно свидетельство переиспользуется по неизменным input/backend bindings. Зависимости: FRY-03; исходный DAG — ориентир, работающий контракт может удовлетворять ребру без нового ремонта. Общие файлы из §5 интегрировать последовательно с затронутыми owners; lane не новый runtime-реестр и не требование полного CI после каждого пакета.

## 8. Совместимость, история, rollback

AM02 историческое замечание о train не переаттестует current high-level route. Alias support отдельно от objective choice; historical float32 results не пересчитывать новым welfare.

## 9. Free-grow и design direction

- Разные модели остаются полезными conditional alternatives; scientific/causal claims требуют собственных оснований.
- Free-grow через явные state/profile/observable contracts, не искусственное слияние всех economics APIs.

Архитектурные источники: [policyos-identity-and-custody-boundary.md §1, §3–6](../05_Основания/Архитектура/policyos-identity-and-custody-boundary.md); [policy-design-custody-time-model.md §2–5](../05_Основания/Архитектура/policy-design-custody-time-model.md). Историческая подлинность и текущая пригодность раздельны; физический layout design-docs не догма.

## 10. Нерешённые решения и передача

- Для конкретного реального use-case отдельно выбрать currency/time/population mapping и calibration evidence; это не блокирует native сохранение existing profiles.

Предъявить patch/base SHA (либо обоснованный no-code результат), актуальную карту callers, REQ→TEST→evidence, фактические команды/логи, различающий контроль и сохранённые инварианты. Поддержанный native профиль: P-CORE (Python >=3.14,<3.15 и project lock); для native численных/JIT/train проверок P-JAX (тот же lock, JAX/jaxlib/optax, deterministic tiny CPU); для процессов P-PROCESS, для поставки P-PACKAGING. Не устанавливать зависимости без отдельного разрешения. Fixture/source-only, исторические PASS и отсутствие ошибки при импорте не закрывают свежий producer→persistence→fresh-reader. Успешная сериализация/конверсия/подпись не доказывает научной истины или полномочия policy result. Никакое требование/тест этой карточки ещё не исполнены.


Полные probes исходного аудита доставлены отдельно в phase1 ZIP; ссылки аудита на них не означают включение тяжёлой evidence в этот исполнительский комплект.
