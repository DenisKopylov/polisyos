# CAS-03 — Одна проверка bytes и bounded batch verification

## 1. Паспорт и результат

**LANE-06 · CP2 · основание 20d9009be21097bfbdc38a546a15cc60213b8ace · статус: ТЗ, не выполнено.** Технический исполнитель и reviewer назначаются проектом. Исходные ID: B152, B154, B155. Тип: cancellable inventory + signature/batch qualification.

Отмена проходит внутрь default census и explicit dedup iterator, не допускает бесконечного чтения повторов и не превращается в complete. Сохраняются single verified snapshot, bounded pending и честный partial report.

Основания: [аудит](../05_Основания/Аудит/02_Пакеты/CAS-03.md), [все остатки](../05_Основания/Аудит/01_Реестры/C76_остатки.json), [неизменная исходная карточка](../05_Основания/Аудит/05_Источники/CAS-03_исходные_строки.txt), исходный объединённый план §CAS-03 (исторические строки 8781–8892).

## 2. Уже работает — сохранить

- Integrity/signature используют один immutable проверенный snapshot; один локальный integrity hash не отменяет самостоятельный hash криптографического verifier.
- Local ERROR не теряет независимые результаты; общий отказ/отмена дают partial/aborted, а не valid complete; BaseException не поглощается.
- Bounded pending и context propagation; request-owned authorization-loss signal только прекращает новые admissions, не является authorizer.
- Default census проверяет canonical membership активного scope; unrelated tenant/signature churn не равен membership change.

## 3. Полнота обязательств и disposition

| Основание | Решение | Требования |
|---|---|---|
| C76-R01 | fix: Cancel проверяется внутри полного filesystem census и scope membership preparation, а не только вокруг next(). | REQ-CAS-03-02 |
| C76-R02 | fix: Dedup проверяет stop на каждом consumed duplicate; StopIteration повторно проверяет cancel/auth loss перед complete. | REQ-CAS-03-03 |
| C76-G01 | qualify: Реальные custody/CLI/native import. Учесть C78 correction: PEP695 поддержан Python3.12; прежнее exclusion было harness, не parser defect. | REQ-CAS-03-01, REQ-CAS-03-04 |
| C76-G02 | capability: Измерить bounded work/memory и проверить caller-owned authorizer integration; не выдавать signal primitive за полный auth lifecycle. | REQ-CAS-03-02, REQ-CAS-03-03, REQ-CAS-03-04 |

### Исходные обязанности, не только новые R

- B152: reuse доверенного locally verified bytes-view без нового пути чтения и без внешнего checksum-as-proof; trust/revocation проверять текущие, не global validity cache.
- B154: local fault→typed item ERROR, global failure→aborted с сохранением завершённых rows; CLI не делает completeness из legacy report.ok.
- B155: ограничить consumption и pending, включая скрытые подготовительные loops; full report/seen set по-прежнему O(N), whole blob snapshot занимает bytes(payload).

## 4. Нормативный контракт

### REQ-CAS-03-01
Integrity→signature на одном immutable snapshot читает один blob и соответствующий manifest view, выполняет один локальный content integrity hash и проверяет signature именно этих bytes. Настоящий Ed25519 verifier сохраняет свои вычисления, trust/revocation/current custody; tamper/size/profile mismatch отказаны.

Источник: B152; аудит: C76-G01; проверки: TEST-CAS-03-01.

### REQ-CAS-03-02
Default batch census принимает cooperative stop probe из batch boundary и проверяет его до каждого filesystem scan/entry-processing и в последующих membership/visibility loops, включая recheck. После наблюдённой отмены не начинает следующую scan/member admission; возвращает aborted/cancelled с уже готовыми rows, inventory_exhausted=False. Сохраняется полная scoped canonical membership validation для успешного complete; cancellation не маскируется inventory_failed.

Источник: B155, B154; аудит: C76-R01, C76-G02; проверки: TEST-CAS-03-02.

### REQ-CAS-03-03
Explicit canonical-ID iterator проверяет stop перед каждым обращением к source и после возврата элемента, в том числе duplicate. _run_bounded при StopIteration проверяет cancel/auth loss до exhausted=True. Если источник в своём next() установил cancel и затем исчерпался после повторов, результат aborted/cancelled, не complete; первый finished row сохранён, новых submits нет. Seen set и report остаются честно O(N).

Источник: B155, B154; аудит: C76-R02, C76-G02; проверки: TEST-CAS-03-03.

### REQ-CAS-03-04
Native verify/sign batch и CLI отражают actual state, admitted/finished, inventory_exhausted и abort_reason, отдельно от item validity. Configured request authorizer вызывает BatchAuthorizationLossSignal только после фактической общей потери authorization; это прекращает admissions, не preempts уже running callbacks. Local PermissionError остаётся item ERROR, общий loss — aborted, CLI не возвращает success для незавершённого обязательного набора.

Источник: B154, B155; аудит: C76-G01, C76-G02; проверки: TEST-CAS-03-04.

## 5. Техническое решение и producer → consumer

Протянуть один optional stop probe/cancellation context от FileSystemCAS batch wrappers к _authenticated_default_inventory_cursor, _capture_default_inventory_state, _capture_inventory_member_paths и explicit _iter_canonical_artifact_ids. Не создавать второй scanner. Для остановки внутри generator выбрать узкий private sentinel/control exception либо typed cursor status, который _run_bounded распознаёт как cancelled/authorization_lost, не generic inventory_failed; публичные статусы уже существуют. Stop check также после StopIteration необходим независимо от iterator patch. Default complete сохраняет before/after active-scope membership comparison. Signature snapshot путь не менять ради cancellation.

### Проверенные owners на срезе
- policy-engine/src/polisyos/core/artifacts/store.py: _iter_canonical_artifact_ids, _capture_inventory_member_paths, _capture_default_inventory_state, _authenticated_default_inventory_cursor
- policy-engine/src/polisyos/core/artifacts/_signature_ops.py: _run_bounded, _run_in_context, verify_signature
- policy-engine/src/polisyos/core/artifacts/_integrity_ops.py: verified snapshot preparation
- policy-engine/src/polisyos/core/artifacts/batch_control.py: BatchAuthorizationLossSignal
- policy-engine/src/polisyos/core/components/_cli_crypto.py: batch CLI report presentation

Нельзя убрать complete census/authorization checks ради streaming. Чистое pending-window исправление уже есть, но не прерывает работу внутри next(). Новый distributed batch service или streaming report API не требуется; возможен позже только при измеренной потребности.

## 6. Локальная приёмка — все будущие проверки NOT_RUN

### TEST-CAS-03-01
- Уровень: unit + targeted native integration.
- Setup: Реальный CAS A/B и keyring, snapshot read/hash counters; valid/invalid/revoked key fixtures через настоящую crypto.
- Действие: Verify selected profile, затем tamper blob, size, manifest and signature; сменить trust после первой valid проверки.
- Точный oracle: Один локальный integrity hash и один snapshot read на операцию, verifier выполняет собственную проверку; каждый tamper/отзыв отказан. Cache по content ID не переживает trust change.
- Ожидаемый класс: positive + negative + boundary.
- Свидетельство: NOT_RUN; предъявить actual command, runtime/backend/import binding, exit/log, exact observed values; отдельный контроль на прежнем дефекте или отключённом механизме.

### TEST-CAS-03-02
- Уровень: unit + targeted native integration.
- Setup: Default inventory с десятками shard dirs, controlled scanner ставит cancel при первом scan; отдельно cancel во время visibility и exhaustion recheck.
- Действие: Запустить native batch с pending_window=2; сравнить original behavior контроль; нормальный проход с unrelated tenant/signature churn.
- Точный oracle: После обнаружения cancel ни одного нового scan/admission; уже начатый bounded syscall можно завершить. state aborted, reason cancelled, exhausted false; успешный полный проход подтверждает scope membership, нарушение canonical names отказано, unrelated churn не ломает complete.
- Ожидаемый класс: positive + negative + boundary.
- Свидетельство: NOT_RUN; предъявить actual command, runtime/backend/import binding, exit/log, exact observed values; отдельный контроль на прежнем дефекте или отключённом механизме.

### TEST-CAS-03-03
- Уровень: unit + targeted native integration.
- Setup: Explicit generator: первый ID завершён, при следующем запросе ставит cancel и выдаёт до200 одинаковых ID; отдельный endless duplicates source, отдельный empty/end source setting cancel.
- Действие: Verify/sign с window1; измерить next calls и submits, затем нормальный finite dedup case.
- Точный oracle: После первого наблюдения cancel source больше не читается; в отличие от прежних200 consumed не more than текущий in-flight next; admitted=finished=1 в базовом case, preserved row, exhausted false, aborted/cancelled. Нормальные duplicates без cancel не создают повторные callbacks.
- Ожидаемый класс: positive + negative + boundary.
- Свидетельство: NOT_RUN; предъявить actual command, runtime/backend/import binding, exit/log, exact observed values; отдельный контроль на прежнем дефекте или отключённом механизме.

### TEST-CAS-03-04
- Уровень: native CAS + configured request scope + CLI.
- Setup: Полные imports на P-CORE; реальный owner/trust route, local failing item и authorizer-loss barrier; small batch.
- Действие: Valid/unsigned/invalid/revoked/local error, global loss mid-flight, CLI JSON/text; измерить peak pending и отдельно N-dependent report/seen bytes.
- Точный oracle: Typed row outcomes и report state совпадают в API/CLI; nonzero для failed mandatory completion. Pending≤declared window; no post-loss admissions; running results сохраняются. Evidence не утверждает O(1)total memory или preemption; authorizer источник установлен явно.
- Ожидаемый класс: positive + negative + boundary.
- Свидетельство: NOT_RUN; предъявить actual command, runtime/backend/import binding, exit/log, exact observed values; отдельный контроль на прежнем дефекте или отключённом механизме.

Повторно использовать/расширить реальные места, а не создавать 127 harness: `policy-engine/tests/unit/remediation/test_cas_03.py`; `policy-engine/tests/unit/remediation/test_b154_batch_completion.py`. До выбора selector прочитать полный test/fixture. Это проверенные пути, не утверждение о наличии всех предложенных assertions.

Допустимые doubles: scan barriers/counters, controlled source iterators и local fault injection; криптография настоящая. Запрещено: подмена signal авторизацией, SourceRange extraction вместо полного native import, fake Ed25519 final oracle.

## 7. Общая интеграция и порядок

Получить exact imported refs CAS-02, проверить signature fresh reader и report completeness. Общий custody setup один; cancellation локальная и не требует повторного большого экспорта.

Точные общие сценарии: E02-I06-D из [контракта интеграции](../03_Интеграция/LANE-06.md); одно свидетельство переиспользуется по неизменным input/backend bindings. Зависимости: CAS-01; исходный DAG — ориентир, работающий контракт может удовлетворять ребру без нового ремонта. Общие файлы из §5 интегрировать последовательно с затронутыми owners; lane не новый runtime-реестр и не требование полного CI после каждого пакета.

## 8. Совместимость, история, rollback

Новые stop параметры private/optional; публичные result enum/status не менять без необходимости. Уточнение [C76 в C78](../05_Основания/Аудит/03_Основания/Уточнение_C76_в_C78.md) заменяет ошибочное объяснение PEP695, но не превращает fixture custody в native PASS. Исторические evidence не переписывать.

## 9. Free-grow и design direction

- Отмена — operational disposition, не научная/криптографическая invalidity; завершённость и достоверность отдельны.
- Сохраняем scoped owner authority и текущий trust lifecycle; bounded pending не выдаём за бесплатное масштабирование.

Архитектурные источники: [policyos-identity-and-custody-boundary.md §1, §3–6](../05_Основания/Архитектура/policyos-identity-and-custody-boundary.md); [policy-design-custody-time-model.md §2–5](../05_Основания/Архитектура/policy-design-custody-time-model.md). Историческая подлинность и текущая пригодность раздельны; физический layout design-docs не догма.

Полные исторические probes/commands/logs остаются в отдельно доставленном phase1 ZIP; ссылки внутри копий аудита на `04_Проверки` относятся к нему, не к новым исполненным проверкам этого комплекта.

## 10. Нерешённые решения и передача

- Выбрать private cancellation propagation форму после чтения всех scanner callers; сохранить existing public status vocabulary.
- Определить actual request-scope authorizer owner для native G02. Если route отсутствует, реализовать узкое явное caller wiring либо оставить capability недоказанной; одного signal test недостаточно.

Предъявить patch/base SHA (либо обоснованный no-code результат), актуальную карту callers, REQ→TEST→evidence, фактические команды/логи, различающий контроль и сохранённые инварианты. Поддержанный native профиль: P-CORE (Python >=3.14,<3.15 и project lock); для процессов P-PROCESS, для поставки P-PACKAGING. Не устанавливать зависимости без отдельного разрешения. Fixture/source-only, исторические PASS и отсутствие ошибки при импорте не закрывают свежий producer→persistence→fresh-reader. Успешная сериализация/конверсия/подпись не доказывает научной истины или полномочия policy result. Никакое требование/тест этой карточки ещё не исполнены.

