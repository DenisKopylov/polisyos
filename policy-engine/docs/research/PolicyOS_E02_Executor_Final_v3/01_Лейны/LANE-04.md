# LANE-04 — Компиляция, экономические профили, обучение и conditional calibration

**EXECUTOR_SPEC_NOT_IMPLEMENTED. Все будущие тесты NOT_RUN.** Основание: `20d9009be21097bfbdc38a546a15cc60213b8ace`. 12 пакетов, 39 REQ и 39 локальных test contracts. Технический исполнитель и независимый reviewer назначаются проектом.

## Точный состав и окна
- [FRY-01](../02_Пакеты/FRY-01.md) · [JSON](../04_Трассировка/FRY-01.json) · CP1
- [FRY-03](../02_Пакеты/FRY-03.md) · [JSON](../04_Трассировка/FRY-03.json) · CP4
- [ECO-01](../02_Пакеты/ECO-01.md) · [JSON](../04_Трассировка/ECO-01.json) · CP4
- [PLG-01](../02_Пакеты/PLG-01.md) · [JSON](../04_Трассировка/PLG-01.json) · CP4
- [PLG-02](../02_Пакеты/PLG-02.md) · [JSON](../04_Трассировка/PLG-02.json) · CP4
- [PLG-03](../02_Пакеты/PLG-03.md) · [JSON](../04_Трассировка/PLG-03.json) · CP4
- [CMP-01](../02_Пакеты/CMP-01.md) · [JSON](../04_Трассировка/CMP-01.json) · CP1
- [CMP-02](../02_Пакеты/CMP-02.md) · [JSON](../04_Трассировка/CMP-02.json) · CP1
- [CMP-03](../02_Пакеты/CMP-03.md) · [JSON](../04_Трассировка/CMP-03.json) · CP1
- [JIT-01](../02_Пакеты/JIT-01.md) · [JSON](../04_Трассировка/JIT-01.json) · CP1
- [RES-04](../02_Пакеты/RES-04.md) · [JSON](../04_Трассировка/RES-04.json) · CP2
- [CAL-05](../02_Пакеты/CAL-05.md) · [JSON](../04_Трассировка/CAL-05.json) · CP4

## Полезный результат и порядок

1. **Compile/freeze:** FRY-01 сохраняет family/IR/treasury contract, CMP-01 связывает static/dynamic/requires и persisted recipe с fresh compiler, CMP-02 сохраняет occurrence/diagnostic gates, CMP-03 исправляет selected-edge diagnostics и preference-optimal matching. Не блокировать работающий sequential route неготовым optional backend; не заменять разрешённую параллельность принудительной последовательностью.
2. **Warm preparation/persistence:** JIT-01 закрывает cache miss→claim race без нового kernel для dynamic-only values. RES-04 сохраняет exact request, отдельные per-node6/7 и original metadata; исправляет post-rename cleanup, state/history namespace и restricted invocation transport. Checkpoint не доказывает standalone executable reconstruction: этой способностью владеет CMP-01.
3. **Economic/learning profiles:** FRY-03 → ECO-01 фиксируют настоящие base/debit/clock/precision профили, не приводят разные законы к одной формуле. PLG-01 discovery изолирует malformed factory, PLG-02 role/CLI не называет historical result обученным, PLG-03 предъявляет actual updates→fresh policy versus no-update.
4. **Conditional calibration:** CAL-05 сохраняет eager skip/tracer-safe cond и полезный scalar-map route. Native transform/callback и actual target-loss/report basis разделены. Это CP4, но не требование завершить trainer перед ordinary compile/run.

Работающий predecessor удовлетворяет dependency без искусственного patch. CMP-01/02/03 делят composer/linker/reconcile boundaries; RES-04 читает их context. PLG-02/03 делят API/CLI result semantics; FRY/ECO/PLG используют shared kernel/profile owners. Резервировать реальные файлы и tests на актуальном commit; не менять test worktree во время job. Path-map MOVE-01/03/04/13/18/20 из исходного плана — ориентир, а не приказ переместить уже работающий owner.

## Единая интеграция

Канонические сценарии: [LANE-04](../03_Интеграция/LANE-04.md). Никаких12 копий тяжёлого harness.

| ID | Связанный путь | Основной различающий oracle |
|---|---|---|
| E02-I04-A | Compile/freeze→native sequential/async→persisted recipe/fresh compiler где применимо | Требования/параметры не исчезают; explicit merge60 UUID-invariant; collision STRICT reject, WARN limitation сохраняется; truthful selected-edge и1020 при исправленном preference. |
| E02-I04-B | Cache→warm current invocation; backend result→FS checkpoint→fresh resume | Dynamic2/3→20/30; race1wrapper, не2; history6/7, seed7; changed request refuses; postrename fault не удаляет referenced sidecars. |
| E02-I04-C | Native economics→actual tiny train→selected artifact→fresh policy/CLI | 1–2 real updates и action effect против independent no-update, ordinary run preserved; unsupported до actor/store, malformed source не мешает later-good. |
| E02-I04-D | Conditional mechanism→JAX transforms/scalar rows→calibration loss/report | Inactive numerical emissions0/gradient1; active derivative1.5; mapped schedule refusal + полезный scalar map; exact input basis. |

**HARD training:** preferred bounded repair PLG-03 — честный unsupported до rollout/update/artifact для несовместимого action/likelihood semantics, при сохранённом HARD evaluation и настоящих fluid/relaxed updates. Это снятие неподдержанного claim, **не закрытие полной HARD training capability** и не permanent architecture ban. Если HARD training нужен, владелец выбирает общий action/likelihood implementation и предъявляет executed-action equality/native on-policy oracle до допуска. Общий сценарий E02-I04-C должен выбирать ровно принятую ветку: отказ либо доказанное обучение, не требовать одновременно обе.

## Положительные обязанности и bounded decisions

- CMP-01 standalone persisted recipe/method refs должны достигнуть fresh actual compiler и исполниться: отсутствие route требует узкого общего writer/loader, не одного теста отказа.
- PLG-03 actual learning требует real gradients/Optax updates, finite metrics, сравнения fresh policy с independently initialized no-update; просто иной seed не обучение.
- CMP-03 полнота matching первична, configured preference вторична; содержательная неоднозначность требует explicit choice, не оптимизации названия.
- JIT-01 dtype/shape gap закрывается измерением actual native profile и ограниченным решением abstract/lazy либо no-code documented support, не hidden pure_step.
- CAL-05 patch-template census ограничен фактически admitted каталогом; genuine mismatch требует общего declared contract, не специальной ветки на тест.

## Профили и evidence

P-CORE: Python >=3.14,<3.15, project lock. P-JAX: тот же profile с locked JAX/jaxlib/Optax, deterministic tiny CPU; real tracing/lowering/first/warm стадии учитывать отдельно. Wrapper count не XLA count и не ускорение. Native resource N — один tiny numerical job без параллельных тяжёлых suites; необходимые installations согласуются отдельно.

Controlled Events, fault injection и tiny synthetic data допустимы, но registry/compiler/dispatcher/real optimizer/FS/fresh-reader нельзя заменять заглушкой на принимаемом пути. Numerical tolerances фиксировать по выбранному dtype до запуска (например float32 elementwise 1e-6 для tiny analytic gradients, если actual conditioning допускает); key/binding/IDs/counters exact. Поддержанный float64/x64 профиль проверяется отдельно, не подразумевается.

Предъявить base/patch SHA, caller map, REQ→TEST→commands/logs/exit, actual positive/negative values, отказ прежнего механизма/контроль его удаления, preservation. Полнота JSON:40 residual records,39 remaining obligations,83 preservation obligations, включая shared earlier-stage PLG-02 obligations в PLG-03. Это QA документов, не39 выполненных tests. Полные audit probes доставлены отдельно phase1 ZIP.

## Межлейновые связи и направление

Compile передаётся LANE-01; RES-04 persistence patterns согласуются с LANE-06 без притворства, что FS checkpoint уже Core CAS custody. CAL-05 actual calibration/report lifecycle переиспользует LANE-10 evidence, сохраняя конкретный schedule/input binding.

[Identity/custody §1,§3–6](../05_Основания/Архитектура/policyos-identity-and-custody-boundary.md) и [Custody-time §2–5](../05_Основания/Архитектура/policy-design-custody-time-model.md): исторические данные, текущая применимость, scientific validity и authority различаются. Free-grow означает общий linker/cache/executor/producer contract и полезные native positive paths; дизайн — направление, не повод требовать универсальную идентификацию мира до локального результата. Никаких fictitious training, invented accounts, second registry или специальной ветки на каждый новый механизм.


## Адресные уточнения PROPOSED v2 — ещё не утверждены

PLG-03: existing TEST-PLG-03-02 теперь содержит независимый exact-profile clipped PPO/GAE oracle (направление gradient, normalization epsilon и заранее заданные tolerances), сохраняя actual tiny Optax/artifact witness. Same-shape/same-key inactive finite→NaN pair проверяет native supported padding. Возможное NaN-poisoning пока source-derived гипотеза, не исполненный defect; patch нужен только по фактическому guard/witness result. Active/nonfinite/intermediate-terminal и HARD-training admission остаются прежними. E02-I04-C не заявляет welfare improvement.

Основание: FN-PLG-ORACLE, FN-PLG-INACTIVE. Все будущие product tests NOT_RUN; изменения ожидают независимого peer review.
