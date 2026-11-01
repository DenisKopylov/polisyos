# CAS-01 — First-writer, честная ref и bounded lock ownership

## 1. Паспорт и результат

**LANE-06 · CP2 · основание 20d9009be21097bfbdc38a546a15cc60213b8ace · статус: ТЗ, не выполнено.** Технический исполнитель и reviewer назначаются проектом. Исходные ID: B150, B151, B153. Тип: квалификация действующего ремонта + исправление тестового ABI.

Подтвердить на настоящем FileSystemCAS, что content-дедупликация не переписывает происхождение, immutable selected views остаются точными, а публикация и восстановление не обходят custody.

Основания: [аудит](../05_Основания/Аудит/02_Пакеты/CAS-01.md), [все остатки](../05_Основания/Аудит/01_Реестры/C74_остатки.json), [неизменная исходная карточка](../05_Основания/Аудит/05_Источники/CAS-01_исходные_строки.txt), исходный объединённый план §CAS-01 (исторические строки 8562–8687).

## 2. Уже работает — сохранить

- Первый default manifest и его история неизменны; новый producer/profile тех же bytes получает собственный immutable view и точный ArtifactRef.
- Повтор одного профиля идемпотентен: один blob, подтверждённые размер/hash/profile; corrupt existing blob/manifest не объявляется успешной дедупликацией.
- Фиксированные stripes, порядок root→stripe→flock, opaque lease и запрет foreign-ID nesting; ожидание не выселяет lock держателя.
- Atomic publication и read-only create_lock_files=False; content hash — identity, не полномочие (LK20).

Изменение продукта требуется только при воспроизведённом несоответствии ниже; отсутствие native проверки само по себе не дефект. Не создавать искусственный рефакторинг для отчёта.

## 3. Полнота обязательств и disposition

| Основание | Решение | Требования |
|---|---|---|
| C74-G01 | qualify: Native custody, durable ownership, sign-on-put и pending recovery проверяются настоящими owners, не selected-method fixtures. | REQ-CAS-01-01, REQ-CAS-01-03 |
| C74-G02 | fix: Обновить только observer ABI create_lock_files; прежний тестовый TypeError не доказывает product regression. | REQ-CAS-01-02 |
| C74-G03 | lifecycle: Квалифицировать поддержанный filesystem/crash profile и явную authorized quarantine/refusal policy; не обещать универсальную FS durability. | REQ-CAS-01-03 |

### Исходные обязанности, не только новые R

- B150: один blob допускает разные неизменяемые provenance views, но не last-writer-wins manifest.
- B151: при существующем повреждении честный отказ удовлетворяет контракту; автоматическое восстановление происхождения по одним bytes не требуется и запрещено без авторитетного источника.
- B153: bounded coordinator metadata не равно доказанной ограниченной памяти всей операции или throughput; lock lifetime охватывает holder и waiters.

## 4. Нормативный контракт

### REQ-CAS-01-01
Native put одинаковых bytes с профилями A/B возвращает один content ID, неизменный default A и разные точные selected refs; fresh store читает каждый профиль с исходными producer/inputs/kind/media. Повтор A не создаёт новый view; изменение bytes/size/profile существующего члена даёт действующий integrity refusal до успешного результата.

Источник: B150, B151; аудит: C74-G01; проверки: TEST-CAS-01-01.

### REQ-CAS-01-02
Тестовый observer artifact_lease принимает и передаёт keyword create_lock_files с действующим default; readonly route явно передаёт False. Coordinator сохраняет bounded stripe table, reentrant same-ID lease и отказ shared→exclusive/foreign-ID nesting; никакая правка теста не убирает readonly запрет создания lock files.

Источник: B153; аудит: C74-G02; проверки: TEST-CAS-01-02.

### REQ-CAS-01-03
Реальная публикация проверяет tenant/cell и input owners под lease, не выдаёт непроверенный pending intent за завершённый, а после restart допускает только существующее проверенное recovery. Для заранее объявленного local filesystem профиля fault injection до/после member publication и owner-claim fsync даёт сохранённый старый view либо явный pending/unknown отказ; ни fabricated provenance, ни ложный PASS.

Источник: B150, B151, B153; аудит: C74-G01, C74-G03; проверки: TEST-CAS-01-03.

## 5. Техническое решение и producer → consumer

Переиспользовать действующий FileSystemCAS._put_blob_and_manifest_once: exclusive artifact lease → повторная _require_input_owners → manifest profile selection → stage members/transaction intent → публикация immutable members → owner claims → recomputed completion. Не создавать второй writer. Product patch нужен только при новом native расхождении; известный ремонт — observer ABI. В проверках вывести точные refs, manifest bytes, число физических blobs и custody disposition. При corrupt existing объекте сохранить диагностируемый отказ; recovery не должен реконструировать producer/inputs из content hash.

### Проверенные owners на срезе
- policy-engine/src/polisyos/core/artifacts/store.py: FileSystemCAS._put_blob_and_manifest_once, put_bytes
- policy-engine/src/polisyos/core/artifacts/_manifest_lifecycle.py: ManifestLifecycle.profile_projection, validate_profile
- policy-engine/src/polisyos/core/artifacts/_atomic_write.py: AtomicFileWriter
- policy-engine/src/polisyos/core/artifacts/ownership.py: ownership publication contracts

Не заменять fixed stripes per-ID кешем с eviction: это повторно вводит два lock для одного ID. Не добавлять глобальный repair daemon; узкий native lifecycle тест и существующий отказ дешевле и честнее.

## 6. Локальная приёмка — все будущие проверки NOT_RUN

### TEST-CAS-01-01
- Уровень: unit + targeted native integration.
- Setup: Инициализированный FileSystemCAS с temporary durable owner index, tenant T/cell C и реальными input artifact refs; payload b'x', профили A/B с разными producer.
- Действие: put A, put B, повтор A; открыть новый store; прочитать оба selected refs и default; затем отдельно повредить blob, byte_size и view selector.
- Точный oracle: Один blob; A default байты неизменны; selected A/B дают исходные metadata; повтор не меняет view bytes; каждый tamper отказ без возврата ложного ref. Другой tenant не получает право от совпадения ID.
- Ожидаемый класс: positive + negative + boundary.
- Свидетельство: NOT_RUN; предъявить actual command, runtime/backend/import binding, exit/log, exact observed values; отдельный контроль на прежнем дефекте или отключённом механизме.

### TEST-CAS-01-02
- Уровень: unit + targeted native integration.
- Setup: Существующие test_cas_01 observer и native coordinator на temporary root.
- Действие: Пропустить create_lock_files через observer; readonly verify в непишущем root; два holder/waiter same-ID, несколько ID и запрещённые nested modes.
- Точный oracle: Нет TypeError; readonly не создаёт lockfile; максимум фиксированного stripe table не растёт по ID; waiter не входит пока holder не вышел; same-ID reentrance допустим, запрещённые upgrade/foreign nesting отказаны.
- Ожидаемый класс: positive + negative + boundary.
- Свидетельство: NOT_RUN; предъявить actual command, runtime/backend/import binding, exit/log, exact observed values; отдельный контроль на прежнем дефекте или отключённом механизме.

### TEST-CAS-01-03
- Уровень: native custody + process restart + filesystem faults.
- Setup: Настоящие owner index, signer и transaction intents; локальный fs profile записан в evidence.
- Действие: Отказать каждому значимому write/fsync boundary, перезапустить store; вернуть доступ и повторить operation; отдельно отозвать input owner между admission и publication.
- Точный oracle: Нет provenance overwrite/unauthorized claim; pending не читается как complete; восстановление использует проверенные intent/member bindings, не blob-only provenance. Коррупция честно отказана; карантин только отдельным authorized действием. До/после visibility/durability различены.
- Ожидаемый класс: positive + negative + boundary.
- Свидетельство: NOT_RUN; предъявить actual command, runtime/backend/import binding, exit/log, exact observed values; отдельный контроль на прежнем дефекте или отключённом механизме.

Повторно использовать/расширить реальные места, а не создавать 127 harness: `policy-engine/tests/unit/remediation/test_cas_01.py`. До выбора selector прочитать полный test/fixture. Это проверенные пути, не утверждение о наличии всех предложенных assertions.

Допустимые doubles: управляемый fsync/clock fault и observer counters при сохранении настоящей публикации и custody. Запрещено: подмена ownership/index/sign-on-put в финальном native доказательстве; stub чтение manifest вместо fresh reader.

## 7. Общая интеграция и порядок

Публикация A/B здесь является единственным seed для CAS-02 transfer и CAS-03 signature; повторно не создавать три несовместимых CAS harness. Передать selected refs и owner context вместе с exact export inventory.

Точные общие сценарии: E02-I06-D из [контракта интеграции](../03_Интеграция/LANE-06.md); одно свидетельство переиспользуется по неизменным input/backend bindings. Зависимости: нет обязательного нового предшественника; исходный DAG — ориентир, работающий контракт может удовлетворять ребру без нового ремонта. Общие файлы из §5 интегрировать последовательно с затронутыми owners; lane не новый runtime-реестр и не требование полного CI после каждого пакета.

## 8. Совместимость, история, rollback

Default profileless selector сохраняет историческую семантику; точный selected-profile запрос не меняет старый default. Observer change тестовый, не публичный API. При native отказе оставить старый store/intents для диагностики; cleanup только test-owned root. Filesystem capability документировать без обещания NFS/сетевой durability.

## 9. Free-grow и design direction

- Immutable provenance views реализуют custody boundary без переноса существующего storage layout.
- Scope, content identity и authorization остаются различными; расширение профиля не требует нового coordinator.

Архитектурные источники: [policyos-identity-and-custody-boundary.md §1, §3–6](../05_Основания/Архитектура/policyos-identity-and-custody-boundary.md); [policy-design-custody-time-model.md §2–5](../05_Основания/Архитектура/policy-design-custody-time-model.md). Историческая подлинность и текущая пригодность раздельны; физический layout design-docs не догма.

Полные исторические probes/commands/logs остаются в отдельно доставленном phase1 ZIP; ссылки внутри копий аудита на `04_Проверки` относятся к нему, не к новым исполненным проверкам этого комплекта.

## 10. Нерешённые решения и передача

- До native квалификации назвать поддержанный filesystem и допустимый recovery/quarantine owner. Без этого G03 остаётся открытым operational limitation, не скрытым PASS.

Предъявить patch/base SHA (либо обоснованный no-code результат), актуальную карту callers, REQ→TEST→evidence, фактические команды/логи, различающий контроль и сохранённые инварианты. Поддержанный native профиль: P-CORE (Python >=3.14,<3.15 и project lock); для процессов P-PROCESS, для поставки P-PACKAGING. Не устанавливать зависимости без отдельного разрешения. Fixture/source-only, исторические PASS и отсутствие ошибки при импорте не закрывают свежий producer→persistence→fresh-reader. Успешная сериализация/конверсия/подпись не доказывает научной истины или полномочия policy result. Никакое требование/тест этой карточки ещё не исполнены.

