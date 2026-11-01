# JIT-01 — текущие defaults, terminal flight и подготовка без оценки
## C45 · 31 октября 2026 года

**Исходные IDs:** B49, B50, B53. **Порядок:** 45/127. **Срез:** `20d9009be21097bfbdc38a546a15cc60213b8ace`. Только аудит.

## Решение

B49 имеет реальное разделение `_CompiledKernel` и текущей dynamic binding. B50 исправляет старый порядок notification/publication и переносит flights к общему cache. B53 больше не вызывает `pure_step` ради подготовки объявленной формы и отказывает при неизвестной data-dependent shape.

**Остался конкретный дефект B50:** между cache miss и claim лидерства нет повторной проверки уже опубликованного результата. Управляемое чередование даёт две сборки wrapper на том же поколении вместо одной. Это лишняя работа, не воспроизведение старого stale-value дефекта.

**22 итоговых bounded MATCH; native pytest и JAX BLOCKED.** Non-JIT исполнение точных owners не названо native JIT acceptance.

## 1. Матрица исходных IDs

| ID | Подтверждённая полезная реализация | Остаток |
|---|---|---|
| B49 | Новая dynamic binding при прежнем kernel; старый handle не меняется; array defaults сравниваются корректно | G01 настоящий JAX/JIT и измерение machine reuse |
| B50 | Publication до event; общий cache coordinator; bounded wait/cancel/error/invalidation | R01 miss→claim race; G01 native qualification |
| B53 | Declared shapes без preparatory evaluation; отказ unknown shape; live executor повторно сверяет plan | G01 native; G02 dtype/shape/runtime границы |

[Полная карточка](../05_Источники/JIT-01_исходные_строки.txt), строки 5530–5648.

## 2. B49 — сохранены и reuse, и текущие значения

Cache key включает static params, входные shape/dtype, backend fingerprint и execution flags; dynamic values туда не добавлены. При hit одинаковые defaults возвращают handle, изменившиеся — новую дешёвую binding поверх того же kernel. Closure получает собственный `bound_defaults`; core получает dynamic tuple при вызове. [S01:476–526](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/compiler/__init__.py#L476-L526) [S01:631–647](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/compiler/__init__.py#L631-L647) [S02:258–275](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/compiler/specialization.py#L258-L275)

- **P01:** old coefficient 2 → **20**; warm coefficient 3 → **30**; independent cold coefficient 3 → **30** на входе 10, без явного override. Для первых двух **1 kernel construction**, distinct handles и одна actual `_kernel` identity.
- **P02:** dynamic override даёт 40; unknown/static override отказывает, static требует recompilation.
- **P03:** array defaults дают [20,30] и [40,50], равные массивы возвращают старый handle без ambiguous truthiness; kernel один.
- **P04:** изменения static/input shape/dtype/backend различают specialization; ни один счётчик не назван числом XLA-компиляций.
- **P18/P19:** actual process-local executable identity разделяет разные selected implementations одного FQN; `_compile_resolved` связывает явно выбранный owner, не ambient registry. [S03:13–54](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/_internal/executable_identity.py#L13-L54) [S01:760–790](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/compiler/__init__.py#L760-L790)

Producer→consumer существует: dispatcher создаёт JaxRunner, runner вызывает `_compile_resolved`, передаёт актуальные dynamic params и seed/RNG, исполняет bound handle и возвращает result envelope. Эти runner/dispatcher bodies **прочитаны, не исполнены** здесь. Они не теряют текущий payload по одному лишь историческому B49. [S10:970–1013](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/backends/dispatch.py#L970-L1013) [S09:48–137](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/backends/jax_runner.py#L48-L137)

## 3. B50 — что исправлено и где осталась гонка

Cache теперь владеет flights для всех compiler instances. `publish_flight` под generation lock делает `_put_unlocked`, устанавливает `flight.result`, затем event. Ошибка и invalidation имеют terminal outcome; follower имеет deadline/cancel path. [S01:145–212](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/compiler/__init__.py#L145-L212) [S01:529–544](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/compiler/__init__.py#L529-L544)

P05/P06 синхронизируют фактическое присоединение follower через delegate `claim_flight`, не через предположение «в cache есть flight». Один и два compiler instances получают **один kernel** с собственными defaults 20/30. P07–P09 проверяют build exception, publication exception и контролируемый BaseException: followers освобождаются, flights очищены. P10 проверяет deadline/cancel, лидер завершает свою работу. P11 инвалидирует generation во время сборки: старый put отвергнут, текущая попытка заканчивается в generation 1. P13 отдельно подтверждает result/cache до notification. P22 отвергает zero/negative/NaN/infinite timeout до сборки.

### C45-R01 — cache miss устаревает до получения лидерства

Порядок в current `compile`: `cache.get` → `claim_flight` → при leader сразу `_compile_method`. Проверки cache после claim нет. [S01:643–650](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/compiler/__init__.py#L643-L650) [S01:692–710](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/compiler/__init__.py#L692-L710)

**P12 задаёт точное чередование реальными Events:**

1. Первый лидер остановлен в начале сборки; второй запрос получает cache miss.
2. Второй запрос остановлен непосредственно перед actual `claim_flight`.
3. Первый лидер заканчивает и публикует result; проверено, что cache содержит его и flight уже удалён.
4. Второй запрос продолжает claim, становится новым лидером и снова строит kernel.

Получены **2 разных `_kernel`**, одна specialization/implementation/generation 0, оба численных результата **20**. Это не старый notify-before-publish сценарий и не ошибка current dynamic defaults. Измерена wrapper construction, не XLA. Требуется согласовать повторную проверку результата с текущим coordinator, сохранив generation guard и не удерживая lock во время тяжёлой работы. Новый lock service не нужен.

## 4. B53 — подготовка не оценивает методы повторно

`compile_chain` replay-проверяет actual plan, собирает объявленные формы, компилирует handles и вызывает `_update_output_shapes`, а не `pure_step`. Symbolic dimensions выводятся из входов; неразрешённый output помечается unresolved и удаляет stale sample placeholder. [S01:847–918](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/compiler/__init__.py#L847-L918) [S01:945–1019](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/compiler/__init__.py#L945-L1019)

P14 строит actual composer chain с requirements ordering и whole-state methods. До исполнения **0+0** pure steps; настоящий `CompiledChainExecutor` даёт **0.5**, вызывает producer и consumer ровно по одному разу. Повторная warm preparation не добавляет оценок. Downstream scalar shape `()` заменяет неправильный vector placeholder. P15 unknown data-dependent shape отказывает при **0+0** вызовов, не подставляет старую sample shape. P16 отвергает inconsistent symbolic и concrete dimensions.

P17 сохраняет полезный explicit warmup: три вызова с текущим coefficient 3, один kernel construction. Здесь audit subclass явно задаёт `jit=False`; это проверка wiring/counts, не native warmup. Нужный warmup сам по себе не defect. `compile_time_ms` измеряет строительство wrapper, не весь XLA lifecycle. [S01:1021–1042](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/compiler/__init__.py#L1021-L1042)

**P21 уточняет границу, а не доказывает неверный JIT result:** prepared consumer specialization имеет dtype **float32** из placeholder, actual producer возвращает **int64**; non-JIT consumer корректно получает **6**. Scalar shape правильная, но dtype не выведен из producer. Перед утверждением native specialization accuracy нужны соответствующие actual JAX controls; возврат скрытого полного оценивания ради dtype не предлагается.

## 5. Полезный scope не расширяется молча

Compiled executor повторно сверяет context/occurrences/signatures/static specialization (P20 удаление context отказывает до pure_step). Он возвращает raw state и отдельно exposes diagnostics; current README прямо не обещает transferable result envelope или full DAG slot routing. Наш whole-state witness использует этот поддержанный маршрут, а не маскирует отсутствие routing. [S01:1089–1122](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/compiler/__init__.py#L1089-L1122) [S12:42–59](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/compiler/README.md#L42-L59)

Cache identity process-local, не persistent source provenance; mutable globals/closures не заморожены. Это явно заявленная граница, не основание приписать cache долговременный scientific/authority контракт. Policy validity и empirical evidence не следуют из 20/30 или отсутствия лишних вызовов.

## 6. Исполнение и воспроизводимые ограничения

Полностью прочитан focused `test_jit_01.py`, **656 строк**, включая tiny native JAX test. Native pytest не дошёл до collection; отдельный import JAX также отказал из-за отсутствующего module. Установок и изменений source нет.

Первый external harness остановился до observations: отсутствовал `threading` в extracted-definition namespace. После локального исправления — 20 MATCH, затем расширенный полный fresh запуск — **22 MATCH / 0 ERROR**. Исходная ошибка, snapshots scripts и все logs сохранены.

Реальные locks/events и source owners исполнялись. Registry/hash/import/error metadata seams раскрыты; NumPy заменяет только normalization, а `jax.jit`/`vmap` shim **намеренно отказывает**, чтобы нельзя было выдать fake JIT за native pass.

[Диагностика](../04_Проверки/C45_JIT01/bounded_diagnostics.json) · [Команды](../04_Проверки/C45_JIT01/commands.json) · [Native границы](../04_Проверки/C45_JIT01/native_verification.json) · [Источники](../05_Источники/C45_источники.json) · [Остатки](../01_Реестры/C45_остатки.json).

**45/127 пакетов рассмотрены ограниченно; 108 уникальных B/LA частично оценены. Следующий — RES-04. Полного закрытия нет.**
