# RES-04 — Точный Foundry checkpoint и неизменяемые sidecars

## 1. Паспорт и результат

**LANE-04 · CP-2 · основание 20d9009be21097bfbdc38a546a15cc60213b8ace · статус: ТЗ, не выполнено.** Технический исполнитель и reviewer назначаются проектом. Исходные ID: B74, B75, B76. Тип: три checkpoint lifecycle/history ремонта + native replay квалификация.

Fresh reader получает полный old либо new snapshot при сбое, без state/history collision и без потери текущего restricted_invocation; exact-request reuse остаётся реальной полезной способностью.

Основания: [аудит](../05_Основания/Аудит/02_Пакеты/RES-04.md), [все остатки](../05_Основания/Аудит/01_Реестры/C46_остатки.json), [неизменная исходная карточка](../05_Основания/Аудит/05_Источники/RES-04_исходные_строки.txt), исходный объединённый план §RES-04 (исторические строки 5649–5771).

## 2. Уже работает — сохранить

- Execution digest связывает effective plan/input/params/seed и diagnostics; occurrence-prefix и live validation replay проверяются до resume.
- Cold/resume7, история6/7 и seed7/7; полный prefix не dispatch повторно, неполный исполняет только suffix.
- Точные per-node outputs/timing/reproducibility, typed validated bound, artifacts/slot arrays; legacy/incomplete history не выдаётся за полную.
- Уникальные поколения, encoded structural paths, content/shape/dtype/path guards, writer lock и pre-publication rollback.
- fail_on_checkpoint_error=False сохраняет вычисление и явные bounded save issues, не обещает успешную persistence.

## 3. Полнота обязательств и disposition

| Основание | Решение | Требования |
|---|---|---|
| C46-R01 | fix: Cleanup обязан различать pre/post manifest publication; после rename referenced sidecars сохраняются даже при fsync error. | REQ-RES-04-03 |
| C46-R02 | fix: Единый envelope/раздельные root prefixes устраняют пересечение state и history без нового канонизатора. | REQ-RES-04-04 |
| C46-R03 | fix: Snapshot/restore переносит текущий typed RestrictedMethodInvocationEvidence или явно отмечает missing historical field, не silently None+complete. | REQ-RES-04-02 |
| C46-G01 | qualify: Native backend result→real FS→fresh reader, actual restricted policy где допустима; DTO fixture не full native proof. | REQ-RES-04-01, REQ-RES-04-02, REQ-RES-04-03, REQ-RES-04-04 |
| C46-G02 | qualify: Сохранить exact-request route и узкий historical scope; standalone plan capability принадлежит CMP-01, не объявлять её по digest. | REQ-RES-04-01, REQ-RES-04-02 |

### Исходные обязанности, не только новые R

- B74: exact effective request и prefix; changed factor/input/seed либо reject либо явный пересчёт, а не stale7. Текущий whole-request reject допустим; универсальный selective ancestor reuse не включать без отдельного scope (REQ01).
- B75: настоящая история6/7, исходная reproducibility и ограничения, включая current restricted evidence; не final_state7/7 и не новая independent observation (REQ02).
- B76: immutable generations, injective path namespace и publication boundary JSON+sidecars; concurrent writers и негативный fresh read (REQ03–04).

## 4. Нормативный контракт

### REQ-RES-04-01
CheckpointingExecutor допускает resume только при совпадении effective request, occurrence-prefix, validation_context/warnings и complete slot-output history. Для x3 multiply2 add1 cold/resume7 с историей6/7; полный checkpoint0 новых dispatch, первый узел checkpoint→1 suffix dispatch. Factor3/input4/seed99/UUID-prefix изменение отвергает старую точку до dispatch; cold counterparts10/9, исходный seed не переписывается. Работающий exact-request resume не блокируется отсутствием универсального selective reuse.

Источник: B74, B75, B76; аудит: C46-G01, C46-G02; проверки: TEST-RES-04-01.

### REQ-RES-04-02
_snapshot_node_result/_restore_node_result переносят все текущие поля MethodResult, в том числе typed restricted_invocation status/limitation/profile/method/runner/input-read/output binding. Historical verified остаётся исходным наблюдением, unavailable не становится verified, None отличим от отсутствующего поля старой схемы. Legacy missing current evidence явно маркируется как неполная соответствующая часть истории и не допускает утверждение complete restricted evidence; при resume, требующем её полноты, существующая incomplete-history граница отказывает. Остальные6/7 outputs, seed/runtime, typed bound и arrays сохраняются.

Источник: B74, B75, B76; аудит: C46-R03, C46-G01, C46-G02; проверки: TEST-RES-04-02.

### REQ-RES-04-03
ChainCheckpoint.save определяет manifest rename как публикацию отдельно от последующего directory fsync подтверждения. До rename failure сохраняет прежний manifest+sidecars и убирает только новые недостижимые файлы. После rename failure не удаляет referenced new sidecars: fresh read видит целиком old либо new, никогда manifest с missing sidecar из cleanup. Durability error остаётся CheckpointSaveError/явной save issue по текущему fail_on_checkpoint_error; success не объявляется. Locks/generation guards сохраняются, orphan cleanup не затрагивает reachable generations.

Источник: B74, B75, B76; аудит: C46-R01, C46-G01; проверки: TEST-RES-04-03.

### REQ-RES-04-04
State и node_results history используют непересекающиеся root namespaces в одном существующем encoded path grammar. Supported state key node_results/0/output/arr не совпадает с history path с тем же suffix; оба массива сохраняют свои values при first и repeat save. Collision до publish отклоняется, а не sidecars.update overwrite. Existing flat a_b и nested a/b остаются разными; content/shape/dtype/path/symlink guards неизменны.

Источник: B74, B75, B76; аудит: C46-R02, C46-G01; проверки: TEST-RES-04-04.

## 5. Техническое решение и producer → consumer

В ChainCheckpoint.save сохранить существующий per-path flock и immutable generation. Устранить R01 разделением _atomic_write_bytes на подготовку/fsync файла, rename с явным publication signal и directory fsync; сигнал должен выставляться непосредственно после успешного replace, а не после возврата helper (тот может уже упасть). Можно передать narrow callback/state marker или вернуть structured outcome через exception, но не угадывать публикацию по exception text. Cleanup новых sidecars разрешён только при подтверждённом prepublication; при неопределённом rename исходе сначала перечитать manifest под writer lock и не удалять потенциально referenced files. R02 предпочтительно один encode envelope {intermediate_state:..., node_results:...} с force_encoded и затем projection в совместимые JSON fields: общий root path делает namespaces injective; альтернативно разные fixed stem namespaces и collision assert. R03 добавить versioned field projection/restore для фактического frozen dataclass RestrictedMethodInvocationEvidence; валидировать Literal поля и tuple/string shapes, не полагаться на то, что dataclass constructor сам валидирует types. Не использовать pickle. Missing schema field отличать от explicit null; новый writer всегда записывает поле. Evidence custody не пересчитывать как runtime current. Current reader сохраняет old ref grammar, новый writer использует безопасное namespace.

### Проверенные owners на срезе
- policy-engine/src/polisyos/foundry/methods/backends/checkpointing.py: ChainCheckpoint.save/load, _atomic_write_bytes, _serialise_state, _snapshot_node_result/_restore_node_result
- policy-engine/src/polisyos/foundry/methods/backends/protocol.py: MethodResult, RestrictedMethodInvocationEvidence
- policy-engine/src/polisyos/foundry/methods/backends/numpy_runner.py: NumpyRunner.execute
- policy-engine/src/polisyos/foundry/methods/backends/dispatch.py: selected runner invocation binding

Не создавать второй transaction/CAS subsystem и не копировать final_state в history. Старый формат читаем в доказанной области; неполная evidence не препятствует отдельному явно неподтверждённому historical inspection, но не authoritative resume.

## 6. Локальная приёмка — все будущие проверки NOT_RUN

### TEST-RES-04-01
- Уровень: native executor→FS→fresh resume.
- Setup: Native actual backend multiply2/add1, explicit slots, seed7, real JSON/NPY and fresh executor; full and first-node checkpoint.
- Действие: Cold/save/load/resume; independently mutate factor/input/seed/UUID/prefix/count/context/history.
- Точный oracle: 7, history6/7 and seeds7/7;0/1 new dispatch respectively; mutations refuse before dispatch, cold factor3→10/input4→9. No reuse claim for independent changed request.
- Ожидаемый класс: positive + negative + boundary.
- Свидетельство: NOT_RUN; предъявить actual command, runtime/backend/import binding, exit/log, exact observed values; отдельный контроль на прежнем дефекте или отключённом механизме.

### TEST-RES-04-02
- Уровень: unit + targeted native integration.
- Setup: Actual MethodResult with timings1/.25/.1, original runtime/fingerprint, warning, array artifact, INDETERMINATE bound and RestrictedMethodInvocationEvidence unavailable+limitation; eligible native restricted case separately.
- Действие: Automatic checkpoint/read/resume; roundtrip all typed fields; malformed status/read tuple/output path; legacy without field versus explicitNone.
- Точный oracle: Field-by-field equivalent evidence and tuple types; unavailable+limitation unchanged, original invocation not recreated; legacy absence visible/incomplete, no inferred verified. Native eligible verified remains historical with original binding; malformed payload load refusal, not defaultNone. History6/7 and typed bounds preserved.
- Ожидаемый класс: positive + negative + boundary.
- Свидетельство: NOT_RUN; предъявить actual command, runtime/backend/import binding, exit/log, exact observed values; отдельный контроль на прежнем дефекте или отключённом механизме.

### TEST-RES-04-03
- Уровень: real filesystem failure + concurrency.
- Setup: Old snapshot array[1], new[2]; real rename observer injects OSError only after manifest bytes changed; prepublication error control; two actual writers same manifest.
- Действие: Save fault cases, fresh load active path; repeat with fail_on_checkpoint_error=False and object-array unsupported new value.
- Точный oracle: Before commit old[1]; after rename new[2] remains readable despite reported durability failure; no referenced sidecar removed. Concurrent scalar marker/array belong same generation; permissive compute7 survives with explicit save issues. Old implementation postrename yields missing sidecar.
- Ожидаемый класс: positive + negative + boundary.
- Свидетельство: NOT_RUN; предъявить actual command, runtime/backend/import binding, exit/log, exact observed values; отдельный контроль на прежнем дефекте или отключённом механизме.

### TEST-RES-04-04
- Уровень: real JSON/NPY producer+fresh reader.
- Setup: State contains node_results/0/output/arr=[1], typed history same suffix arr=[2], prefix/history count1; a_b=[3] and a/b=[4].
- Действие: First and repeated same-path saves, both key orders; fresh load; corrupt/missing/dtype/shape/hash refs, pathescape and symlink fixture.
- Точный oracle: All four arrays preserve distinct values and distinct refs across namespace/generation; producer never publishes alias. Each corrupted/unsafe ref refuses; old implementation repeated namespace case content-mismatch fails.
- Ожидаемый класс: positive + negative + boundary.
- Свидетельство: NOT_RUN; предъявить actual command, runtime/backend/import binding, exit/log, exact observed values; отдельный контроль на прежнем дефекте или отключённом механизме.

Повторно использовать/расширить реальные места, а не создавать 127 harness: `policy-engine/tests/unit/remediation/test_res_04.py`. До выбора selector прочитать полный test/fixture. Это проверенные пути, не утверждение о наличии всех предложенных assertions.

Допустимые doubles: controlled fsync/rename fault observer, tiny methods and arrays, delegated dispatch counter. Запрещено: in-memory save вместо filesystem commit race; fake backend вместо native result evidence; regenerated current runtime as historical metadata.

## 7. Общая интеграция и порядок

Shared checkpoint/context с CMP-02; freshness/template compile JIT-01. Координировать patterns публикации с LANE-06 CAS/DUR, но этот FS checkpoint не выдавать за Core CAS custody. CMP-01 владеет standalone persisted recipe capability.

Точные общие сценарии: E02-I04-B из [контракта интеграции](../03_Интеграция/LANE-04.md); одно свидетельство переиспользуется по неизменным input/backend bindings. Зависимости: CMP-02; исходный DAG — ориентир, работающий контракт может удовлетворять ребру без нового ремонта. Общие файлы из §5 интегрировать последовательно с затронутыми owners; lane не новый runtime-реестр и не требование полного CI после каждого пакета.

## 8. Совместимость, история, rollback

Новые fields/refs additive+versioned; legacy reader compatibility определить readback fixture, не тихо переаттестовать старый restricted field. Возможен intentional legacy restricted-resume отказ из-за отсутствия требуемой evidence, с доступным historical inspection/recompute маршрутом. Durability failure после commit не rollback подтверждённого current manifest посредством удаления данных.

## 9. Free-grow и design direction

- Публикация и подтверждение durability различны; текущее видимое поколение нельзя разрушать cleanup старого предположения.
- Историческая invocation evidence переносится как история, не новая независимая проверка и не authority promotion.

Архитектурные источники: [policyos-identity-and-custody-boundary.md §1, §3–6](../05_Основания/Архитектура/policyos-identity-and-custody-boundary.md); [policy-design-custody-time-model.md §2–5](../05_Основания/Архитектура/policy-design-custody-time-model.md). Историческая подлинность и текущая пригодность раздельны; физический layout design-docs не догма.

## 10. Нерешённые решения и передача

Новых блокирующих продуктовых решений не требуется. Реальную доступность supported runtime установить до native проверки; недоступность оформлять NOT_RUN, не PASS.

Предъявить patch/base SHA (либо обоснованный no-code результат), актуальную карту callers, REQ→TEST→evidence, фактические команды/логи, различающий контроль и сохранённые инварианты. Поддержанный native профиль: P-CORE (Python >=3.14,<3.15 и project lock); для native численных/JIT/train проверок P-JAX (тот же lock, JAX/jaxlib/optax, deterministic tiny CPU); для процессов P-PROCESS, для поставки P-PACKAGING. Не устанавливать зависимости без отдельного разрешения. Fixture/source-only, исторические PASS и отсутствие ошибки при импорте не закрывают свежий producer→persistence→fresh-reader. Успешная сериализация/конверсия/подпись не доказывает научной истины или полномочия policy result. Никакое требование/тест этой карточки ещё не исполнены.


Полные probes исходного аудита доставлены отдельно в phase1 ZIP; ссылки аудита на них не означают включение тяжёлой evidence в этот исполнительский комплект.
