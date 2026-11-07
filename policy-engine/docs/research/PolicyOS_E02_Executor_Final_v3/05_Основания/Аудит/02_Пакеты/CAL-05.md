# CAL-05 — неактивная ветвь и честная граница JAX
## C47 · 31 октября 2026 года

**Исходный ID:** B185. **Порядок:** 47/127, конец LANE-04. **Срез:** `20d9009be21097bfbdc38a546a15cc60213b8ace`. Только аудит.

## Решение

Исходный unconditional `emit_patches` больше не является текущим поведением: concrete inactive путь не вычисляет selector/emitter и не расходует ключ; traced путь использует `lax.cond`. Важное дополнение — **mapped schedule predicates явно отклоняются**, а mixed schedules обслуживает scalar `lax.map`, поэтому код не обещает, что любой `cond` под `vmap` экономит исполнение.

**20 bounded MATCH, нового подтверждённого R-дефекта нет. Native JAX acceptance не закрыта:** pytest и JAX отсутствуют. Прочитанные gradient/JIT/Hessian tests не выданы за пройденные. Полное закрытие B185 не заявляется.

## 1. Матрица исходного ID

| ID | Исходное основание | Текущее состояние | Остаток |
|---|---|---|---|
| B185 | Inactive emitter всё равно вычислялся; log(0) портил производную либо future-input refusal прерывал prefix | Eager branch отделена от tracer-safe cond; inactive key сохраняется; batching admission защищает conditional execution | C47-G01: настоящий transform/runtime witness; G02: весь допустимый patch contract; G03: actual calibration consumer/authority |

## 2. Producer → consumer, не только локальная маска

`compile_program` разрешает schedule, создаёт mechanism, проверяет selector structure и фиксирует deterministic rank/dependency map. Отсутствующее schedule требует положительный horizon, а не выдуманный будущий input. `Calibrator._build_bundle` действительно вызывает этот owner; `_execute_forward` направляет bundle в `run_pure_scan` либо ordered batch objective, затем traces идут в target loss. [S01:154–312](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/calibration/pure_executor.py#L154-L312) [S03:1940–1975](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/calibration/calibrator.py#L1940-L1975) [S03:2749–2795](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/calibration/calibrator.py#L2749-L2795)

Ordered objective вызывает `apply_nodes_batch`, сохраняет positional row/state/time/key alignment и отдельно вычисляет validity. Batch executor использует scalar `lax.map`, не mapped-predicate vmap. Это существующая связь, которую следует сохранять, а не заменять дополнительным execution subsystem. [S01:746–782](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/calibration/pure_executor.py#L746-L782) [S03:264–333](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/calibration/calibrator.py#L264-L333)

Этот маршрут создаёт **synthetic traces**. Корректное расписание не превращает их в independent observed data, не доказывает качество model proposal или научную валидность calibrated report. Full optimizer/CAS/report не исполнялись.

## 3. Как устранена исходная ошибка

`_concrete_bool` не вызывает bool у tracer. Active eager ветвь вычисляет реальный selector и emitter; inactive строит neutral patches из declared output slots и receiving state. Traced active/inactive branches разделены `lax.cond`; inactive возвращает исходный key. Neutral records затем маскируются в merge, а dependency flush остаётся перед dependent node. [S01:537–605](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/calibration/pure_executor.py#L537-L605) [S01:633–743](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/calibration/pure_executor.py#L633-L743)

- **P01:** четыре inactive шага (до начала и после конца), emitter с активным refusal на нулевом income: 0 emissions, 0 splits, исходные нули и key 7 сохранены.
- **P02–P04:** active x=2 получает настоящий x+log(x), один derived scripted subkey; active invalid x=0 либо отказывает, либо сохраняет -inf от незащищённого log. Нет подмены входа или `nan_to_num`.
- **P05/P06:** inactive не вычисляет даже runtime selector; active actual evaluator передаёт `[False, True]`. P05 использует manually prepared bundle, а P16 отдельно показывает compile-time отказ unknown selector: runtime skip не снимает structural admission.
- **P07:** SUM, OVERRIDE, PRIORITY, ERROR сохраняют исходное состояние для двух inactive writers. ERROR не считает neutral records действительными writers.
- **P08/P09:** dependent reader видит уже применённые `[5,5]`; независимые writers по одному base=2 суммарно дают 9, а не нечаянное последовательное обновление.

Все эти исполнения используют exact source bodies с **NumPy algebra и scripted integer keys**, не настоящий JAX PRNG/gradient. P20 специально подтверждает, что native scan в harness не заменён тихим Python success.

## 4. Реальный fiscal kernel внутри ограниченного маршрута

P10 выполняет canonical `IncomeTax` algebra, actual selector evaluator, actual merge и dependent reader. Для income `[100,200]`, rate .1 и age>=30:

| t | income / dependent read | government revenue | scripted key |
|---:|---|---:|---:|
| 0 | `[100,200]` | 0 | 9 — активен только reader |
| 1 | `[100,180]` | 20 | 11 — tax и reader |
| 2 | `[100,200]` | 0 | 7 — оба вне schedule |

P18 сравнивает active/neutral patch signatures этого producer на float32 receiving state: slots, single-record keys, shapes и dtypes совпали. Однако GlobalState/registry/factory/Equinox base здесь structural fixtures; это **не installed native tax integration**. Existing repository tests содержат именно такой более сильный native path, включая реальный typed selector и gradient `[1,.9]`, но сейчас он только прочитан. [S12:112–149](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/execute/mechanisms/fiscal.py#L112-L149) [S05:846–1074](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/foundry/calibration/test_pure_executor_semantics.py#L846-L1074)

## 5. Почему mapped schedules запрещены, а не «исправлены» маской

Custom batching rule отказывает, если predicate mapped, включая массив одинаковых steps: доказанная homogeneity в traced contract отсутствует. Shared scalar schedule со state-vmap разрешён; per-row schedules используют scalar map. Direct P11/P12 проверяют body admission, **не сами JAX transformations**. [S01:608–630](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/calibration/pure_executor.py#L608-L630)

Существующие tests сильнее обычного Python counter: `jax.debug.callback` наблюдает numerical execution, `effects_barrier` отделяет от tracing; проверены eager/JIT/grad/Hessian, `vmap(jit)`, mixed scalar map, одинаковые mapped steps и удаление admission. Последний control показывает, что finite value/gradient сами по себе могут не обнаружить лишнее inactive execution. Эти полезные tests нельзя заменить одними числовыми asserts или отменить guard ради поддержки любого vmap. [S05:609–845](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/foundry/calibration/test_pure_executor_semantics.py#L609-L845)

## 6. Что ещё доказать, не объявляя гипотезы багами

**C47-G01:** выполнить native semantics suite на поддержанной среде. Здесь не измерены настоящий inactive derivative=1, active derivative=1.5, Hessian, runtime callback или ускорение; source assertions не являются результатом запуска.

**C47-G02:** neutral map создаёт по одному record на declared output, SUM — delta, остальные — value. Допускаемые actual emitters должны давать совместимые pytree/count/keys/shape/dtype. Один canonical fiscal witness полезен, но не покрывает весь каталог, несколько records и dtype transitions. Конкретного admissible native mismatch здесь не установлено; это qualification gap, не подтверждённая ошибка. Сохранять compile-time шаблон без численного вызова inactive emitter. [S01:553–586](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/calibration/pure_executor.py#L553-L586) [S01:785–800](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/calibration/pure_executor.py#L785-L800)

**C47-G03:** отдельно квалифицировать actual calibration/report lifecycle и empirical basis. Не требовать от schedule repair универсального изобретателя моделей; LLM остаётся semantic proposer, а evidence/custody границы — самостоятельными.

## 7. Команды и итог

Existing `test_pure_executor_semantics.py` (1074 строки) прочитан целиком. Предложенный планом `test_cal_05.py` не найден, но это **не отсутствие coverage**. Native pytest остановлен до collection: `No module named pytest`; отдельный import JAX также exit 1. Dependencies не устанавливались, checkout чист.

[Диагностика](../04_Проверки/C47_CAL05/bounded_diagnostics.json) · [Команды](../04_Проверки/C47_CAL05/commands.json) · [Границы](../04_Проверки/C47_CAL05/native_verification.json) · [Источники](../05_Источники/C47_источники.json) · [Остатки](../01_Реестры/C47_остатки.json).

**47/127 пакетов рассмотрены ограниченно; 112 уникальных B/LA частично оценены. Следующий — GRF-01, LANE-05. Полного закрытия нет.**
