# Независимый source-based review: runtime и delivery, E02 v2

## Вывод и уровень доказательства

Проверены **26 текущих пакетов LANE-06 и LANE-12**, полные MD, семантические JSON, общие правила, относящиеся контракты лейнов/интеграции и **32 shared binding**. Для каждого пакета вынесено **70 отдельных решений**: всего **1820**, без пропусков и дубликатов. В назначенных пакетах — **93 REQ и 92 TEST-контракта**.

**Новых подтверждённых дефектов ТЗ/решения/плана приёмки не установлено.** Это не утверждение об отсутствии ошибок в реализации и не разрешение на релиз. Часть критериев удовлетворена явно ограниченным обещанием или будущей квалификацией. Выполнение продуктовых/native-тестов: **NOT_RUN**. Текущие тесты/профили нельзя считать PASS из факта наличия документа. Исторические исправления v1 не переизданы как новые замечания.

Распределение: **695 addressed, 405 bounded, 720 not_applicable, 0 gap, 0 unresolved**. `addressed` означает достаточность сформулированного поведения и будущего свидетельства, а не испытанный продукт; `bounded` — законное ограничение claim, а не скрытый дефект. Полная аргументация каждого решения и привязки к REQ/TEST находятся в `assessments.json`.

Базовая ревизия: `20d9009be21097bfbdc38a546a15cc60213b8ace`. Каталог заморожен SHA-256 `8c8c77e13d9151349b7410b441f97f0f94fbfb7d097150f32c9872fe35a3cb59`. Хеши всех 52 файлов пакетов совпали с текущим индексом. Все доказательные REQ/TEST-ссылки проверены на существование в соответствующем текущем файле.

## Как применены источники

Прочитаны все 70 нормализованных критериев замороженного каталога с источниками и ограничениями применимости. Исследование первоисточников было завершено до этой фазы; повторного web-исследования и нового заявления о личном полном чтении всех внешних документов здесь нет. В `coverage.json` сохранены 67 использованных source-records каталога, их URL/версии/прочитанные разделы и ограничения. Следующие опоры объясняют способ проверки, но сами по себе не доказывают дефект E02:

- **RA-07/RA-16**: проверялись наблюдаемый oracle, уровень проверки и реальные сценарные переходы, а не наличие названия теста. [NASA Appendix C](https://www.nasa.gov/reference/appendix-c-how-to-write-a-good-requirement/) и конкретные разделы RA-S03/RA-S11 в каталоге.
- **DRT-01–03, SR-18**: различались намерение, durable receipt, эффект и неизвестный ответ; случайный новый UUID не принимался за безопасное восстановление. Требование ограничено реально заявленным retry/effect boundary. [AWS: idempotent APIs](https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/).
- **DRT-07/14/18**: отмена ожидания не объявлялась физическим прекращением работы, читаемость — crash durability, lease-check — fencing всех mutations. [gRPC Cancellation](https://grpc.io/docs/guides/cancellation/), [PostgreSQL asynchronous commit](https://www.postgresql.org/docs/18/wal-async-commit.html), DRS-12 в каталоге.
- **DAT-01/05/09**: same-bridge roundtrip не заменяет независимый численный anchor, compatibility требует конкретного writer/reader пути, negative должен различать неправильный механизм. [NASEM, Chapter 4](https://www.nationalacademies.org/read/25303/chapter/7), [Software Engineering at Google, Chapter 12](https://abseil.io/resources/swe-book/html/ch12.html).
- **SR-02/04/15/16**: hash/подпись не доказывают назначенного issuer или текущую пригодность; свежесть и фактически загруженный объект важнее удобного marker. Восстановление проверяется на обещанном конечном состоянии, не расширяется до выдуманного RTO/RPO. [SLSA verification](https://slsa.dev/spec/v1.2/verifying-artifacts), [Google SRE data integrity](https://sre.google/sre-book/data-integrity/).

## Существенные результаты по каждому пакету

В каждом пункте ниже приведены решение, различающий контроль и сохранённая граница. Пакетные доказательства читаются вместе с текущими общими E02-GREQ, профилями и shared bindings; shared покрытие не отменяет локальные тесты.

### 1. STA-01 — LANE-06

**Вердикт:** нового gap нет; assessed 70/70 (32 addressed / 16 bounded / 22 not_applicable). Продукт NOT_RUN.

**Контракт и решение.** ordered state journal, branch isolation и protected membership. staged detached merge и итоговое сравнение трёх protected key sets перед commit; alias-aware declared-subtree isolation.

**Различающая приёмка.** root={} отказ без partial commit; y=4 поверх current y=9 при unrelated=new; delete/null/no-write различены; fresh CAS proof и exact costs. Сквозной маршрут: NodeCacheEntry/proof → actual CAS → current-base replay → следующий node; старый unsupported entry — miss/recompute, не частичный hit.

**Не расширять обещание.** finite callback-free graph; checkpoint snapshot не patch; внешний spend/event принимает RUN/DUR, arbitrary object graph и speedup не заявлены. Эти ограничения сохранены, а не использованы для объявления гипотетического дополнительного subsystem обязательным.

**Ключевые критерии/доказательства:** DRT-02, DAT-08; `02_Пакеты/STA-01.md — REQ-STA-01-05; TEST-STA-01-05`; `02_Пакеты/DUR-01.md — REQ-DUR-01-01`; `02_Пакеты/DUR-02.md — REQ-DUR-02-03`; `02_Пакеты/STA-01.md — §6; §8`.

### 2. STA-02 — LANE-06

**Вердикт:** нового gap нет; assessed 70/70 (25 addressed / 15 bounded / 30 not_applicable). Продукт NOT_RUN.

**Контракт и решение.** admitted parameter bundle reuse и current numerical derivation. один materialize-runtime-from-bundle helper после matcher; PreparedSKGRead удерживает same identity/connection до чтения.

**Различающая приёмка.** draws32→128/seed1→9 uses current config, selector0; independent beta mean2/std.6; same-path DuckDB1.25→9.75 меняет key/read. Сквозной маршрут: actual source/key → typed bundle → ParameterTransfer → state → fit/request; missing/null/false/zero/list и close-once проверяются.

**Не расширять обещание.** DEC-STA-02-01 выбирает реальный prior-capable manual/hybrid consumer; GCM unsupported, scientific relevance не выводится из bridge. Эти ограничения сохранены, а не использованы для объявления гипотетического дополнительного subsystem обязательным.

**Ключевые критерии/доказательства:** DAT-05, DAT-07; `02_Пакеты/STA-02.md — TEST-STA-02-01; TEST-STA-02-02; TEST-STA-02-03; TEST-STA-02-04`; `02_Пакеты/STA-02.md — TEST-STA-02-01`.

### 3. EXE-01 — LANE-06

**Вердикт:** нового gap нет; assessed 70/70 (31 addressed / 16 bounded / 23 not_applicable). Продукт NOT_RUN.

**Контракт и решение.** nonblocking completion bridge и action-specific cache admission. один private call_soon_threadsafe handoff/receipt adapter; bounded Common owner сохраняет physical reservation до job completion.

**Различающая приёмка.** три actual await routes продвигают heartbeat до release held worker; valid hit read1/run0 вызывает producer0; cancelled current index не восстанавливается. Сквозной маршрут: run_blocking_async/result_async/retry-thread-async → actual cache/CAS → fresh consumer; read denial до I/O, fail_fast после semaphore.

**Не расширять обещание.** private transport delivery не расширяет arbitrary callbacks; running physical job не убит cancel waiter; measured latency не SLA. Эти ограничения сохранены, а не использованы для объявления гипотетического дополнительного subsystem обязательным.

**Ключевые критерии/доказательства:** DRT-14, DRT-11; `02_Пакеты/EXE-01.md — REQ-EXE-01-02; REQ-EXE-01-03`; `02_Пакеты/RUN-01.md — REQ-RUN-01-02; TEST-RUN-01-02`; `02_Пакеты/EXE-01.md — REQ-EXE-01-01; REQ-EXE-01-04; TEST-EXE-01-01; TEST-EXE-01-04`.

### 4. EXE-02 — LANE-06

**Вердикт:** нового gap нет; assessed 70/70 (23 addressed / 18 bounded / 29 not_applicable). Продукт NOT_RUN.

**Контракт и решение.** readiness admission по реальным target identities. container-aware shared path resolution либо conservative отказ readiness; commit predecessor раньше successor release.

**Различающая приёмка.** list .0/.00/+0/-1 не disjoint; dict 0/00 различны; A→C до B только без B→C; selected-profile native readback. Сквозной маршрут: actual admitted state → dependency scheduler → committed delta → selected artifact/finalizer; existing fixture ABI обновляется без удаления owner checks.

**Не расширять обещание.** unknown container/shape/semantic hooks выбирают safe tier; не новый scheduler и не обещание workload speedup. Эти ограничения сохранены, а не использованы для объявления гипотетического дополнительного subsystem обязательным.

**Ключевые критерии/доказательства:** DRT-20, DRT-21; `02_Пакеты/EXE-02.md — REQ-EXE-02-01; REQ-EXE-02-02; TEST-EXE-02-01; TEST-EXE-02-02`.

### 5. RES-01 — LANE-06

**Вердикт:** нового gap нет; assessed 70/70 (27 addressed / 17 bounded / 26 not_applicable). Продукт NOT_RUN.

**Контракт и решение.** checkpoint identity, required-read sufficiency и exact-ref admission memo. immutable origin fingerprint отдельно residual; exact successful-ref memo инвалидируется eviction/discard и не кэширует failed load.

**Различающая приёмка.** два fresh resume A→B→C дают a=b=c=1 и uninterrupted result; duplicate refs не заменяют missing b; full state без seed допустим. Сквозной маршрут: actual CAS/lock/head/history → fresh residual consumer; functional change refused, allow_replay запускает original plan явно.

**Не расширять обещание.** DEC-RES-01-01 конечный actual list/null grammar; tail optional только по измерению; нет universal object graph или произвольных historical layouts. Эти ограничения сохранены, а не использованы для объявления гипотетического дополнительного subsystem обязательным.

**Ключевые критерии/доказательства:** DAT-03, DAT-08; `02_Пакеты/RES-01.md — REQ-RES-01-01; REQ-RES-01-03; TEST-RES-01-01; TEST-RES-01-03`; `02_Пакеты/RES-01.md — §6; §8`.

### 6. RES-02 — LANE-06

**Вердикт:** нового gap нет; assessed 70/70 (25 addressed / 18 bounded / 27 not_applicable). Продукт NOT_RUN.

**Контракт и решение.** ok-only frontier и одна atomic tier publication. commit/rollback перед CASCheckpointHook.on_tier_complete; fault matrix before blobs/after blobs/before or after head.

**Различающая приёмка.** crash после первого head state n1/frontier[a,b] resume остаётся n1, не2; skip/fail не successful; rollback retains output bytes. Сквозной маршрут: merged state+accepted aliases+refs → durable head → resume/finalizer; current fixture selected-profile ABI сохраняется.

**Не расширять обещание.** native process/crash profile, не blanket power-loss guarantee; output existence не selected authority; serial-only node hook не обобщается на parallel. Эти ограничения сохранены, а не использованы для объявления гипотетического дополнительного subsystem обязательным.

**Ключевые критерии/доказательства:** DRT-21, DRT-07; `02_Пакеты/RES-02.md — REQ-RES-02-02; REQ-RES-02-03; TEST-RES-02-02; TEST-RES-02-03`; `02_Пакеты/RES-02.md — REQ-RES-02-02; TEST-RES-02-02`.

### 7. RES-03 — LANE-06

**Вердикт:** нового gap нет; assessed 70/70 (24 addressed / 15 bounded / 31 not_applicable). Продукт NOT_RUN.

**Контракт и решение.** same-leaf и sibling useful partial result persistence. existing merge-before-raise и cycle/source/history partial link; не forged completed GenerationCycleRecord.

**Различающая приёмка.** actual N5 numbers/bytes/scope/ref и exact late error доступны fresh scoped reader; no terminal success; wrong tenant/profile refused. Сквозной маршрут: N5 persisted result → partial link → failed terminal → public reader; common-basis invalidation ограничивает только dependent authority.

**Не расширять обещание.** DEC-RES-03-01 выбирает existing projection либо typed partial extension; missing N5 environment NOT_RUN, а не готовая способность. Эти ограничения сохранены, а не использованы для объявления гипотетического дополнительного subsystem обязательным.

**Ключевые критерии/доказательства:** SR-07, SR-11; `02_Пакеты/RES-03.md — REQ-RES-03-02; TEST-RES-03-01; TEST-RES-03-02`; `02_Пакеты/RES-03.md — REQ-RES-03-01; REQ-RES-03-02; REQ-RES-03-03; TEST-RES-03-02; TEST-RES-03-03`.

### 8. RUN-01 — LANE-06

**Вердикт:** нового gap нет; assessed 70/70 (28 addressed / 17 bounded / 25 not_applicable). Продукт NOT_RUN.

**Контракт и решение.** deadline/context propagation и pre-admission coroutine ownership. narrow try вокруг submit, close only CORO_CREATED до admission; existing retry/attempt authority и shared executor.

**Различающая приёмка.** fresh CORO_CLOSED/body0 при refused submit; admitted Task не закрыт; общий queue/backoff/publication deadline и contexts A/B/neutral. Сквозной маршрут: request context/deadline → bridge → actual attempt → CAS/claim consumer; typed unknown не допускает blind repeat.

**Не расширять обещание.** noncooperative timeout unknown, не hard real-time kill; explicit owner-unbounded profile; context copy не выдаёт прав. Эти ограничения сохранены, а не использованы для объявления гипотетического дополнительного subsystem обязательным.

**Ключевые критерии/доказательства:** DRT-12, DRT-14; `02_Пакеты/RUN-01.md — REQ-RUN-01-01; REQ-RUN-01-02; TEST-RUN-01-01; TEST-RUN-01-02`.

### 9. RUN-02 — LANE-06

**Вердикт:** нового gap нет; assessed 70/70 (28 addressed / 18 bounded / 24 not_applicable). Продукт NOT_RUN.

**Контракт и решение.** real process transport, EOF classification и owned cleanup. общий EOF classifier без blocking join; framed drain-before-join, parent-issued run/attempt/nonce receipt и fixed delivery grace.

**Различающая приёмка.** sync/async early EOF не compute timeout; exited precedence явно задан; small/1MiB exact receipt; warm numerical child expected value. Сквозной маршрут: real worker/pipe → actual codec → validated receipt → fresh consumer; cleanup только verified own non-parent descendants.

**Не расширять обещание.** Linux/Darwin и warm/cold topology отдельны; unsupported profile NOT_QUALIFIED; независимый EOF repair не ждёт всех платформ. Эти ограничения сохранены, а не использованы для объявления гипотетического дополнительного subsystem обязательным.

**Ключевые критерии/доказательства:** DRT-04, DRT-14; `02_Пакеты/RUN-02.md — REQ-RUN-02-01; REQ-RUN-02-02; TEST-RUN-02-01; TEST-RUN-02-02`; `02_Пакеты/RUN-02.md — REQ-RUN-02-01; REQ-RUN-02-03; TEST-RUN-02-01; TEST-RUN-02-03`.

### 10. RUN-03 — LANE-06

**Вердикт:** нового gap нет; assessed 70/70 (28 addressed / 18 bounded / 24 not_applicable). Продукт NOT_RUN.

**Контракт и решение.** retry baseline, typed classification и known-cost cancellation. fresh declared-write branch на attempt; idempotent known attempt settlement перед re-raise CancelledError; один classifier owner.

**Различающая приёмка.** retry получает x0/list[]; success x1/spend8; fail+cancel сохраняет5+2=7 once; unknown current amount не fabricated0. Сквозной маршрут: actual attempt basis/outcome → real ledger/CAS → fresh budget/trace; unknown effect reconcile без новой UUID, checkpoint continuation отдельно.

**Не расширять обещание.** DEC-RUN-03-01 конечный actual producer return/raise/IPC table; no global arbitrary exception equivalence или external exactly-once. Эти ограничения сохранены, а не использованы для объявления гипотетического дополнительного subsystem обязательным.

**Ключевые критерии/доказательства:** DRT-02, DRT-14; `02_Пакеты/RUN-03.md — REQ-RUN-03-01; REQ-RUN-03-02; REQ-RUN-03-03; REQ-RUN-03-04; TEST-RUN-03-02; TEST-RUN-03-04`.

### 11. DUR-01 — LANE-06

**Вердикт:** нового gap нет; assessed 70/70 (33 addressed / 13 bounded / 24 not_applicable). Продукт NOT_RUN.

**Контракт и решение.** exact-event budget durability acknowledgment и trusted restore. stable lock; temp→file fsync→replace→dir fsync; confirmed resolve под lock и strict readback, не readable=durable.

**Различающая приёмка.** persistent directory fsync fault остаётся unknown на settle/replay/resolve; recovery same receipt/revision once; authentic r не заменяет confirmed r+1. Сквозной маршрут: authorized producer → exact settlement → confirmed ack → fresh budget consumer; restored limits/spend/receipts/revisions сверены с current generation.

**Не расширять обещание.** DEC-DUR-01-01 объявляет local filesystem/recovery source; no power-loss/multi-host proof; отсутствие trusted current recovery source блокирует restore, не ack repair. Эти ограничения сохранены, а не использованы для объявления гипотетического дополнительного subsystem обязательным.

**Ключевые критерии/доказательства:** DRT-07, SR-15; `02_Пакеты/DUR-01.md — REQ-DUR-01-01; REQ-DUR-01-03; TEST-DUR-01-01; TEST-DUR-01-03`; `02_Пакеты/DUR-01.md — REQ-DUR-01-02; DEC-DUR-01-01; TEST-DUR-01-02`.

### 12. DUR-02 — LANE-06

**Вердикт:** нового gap нет; assessed 70/70 (33 addressed / 17 bounded / 20 not_applicable). Продукт NOT_RUN.

**Контракт и решение.** heartbeat loss, transactional stale-worker fence и reconciled handover. lost.set перед окончательным pulse stop; owner/attempt/running/lease SQL predicate плюс commit admission; existing reconcile/resume owner.

**Различающая приёмка.** A после takeover не меняет B через sibling inlets; event/commit fault rollback status/progress/history/outbox; lost reply effect count1 + remaining only. Сквозной маршрут: primary effect/checkpoint → actual reconciliation → new current lease same operation → remaining work с прежним deadline/budget; diagnostic A retained unattached.

**Не расширять обещание.** DEC-DUR-02-01 один supported primary/local pair; ambiguous effect unknown; PostgreSQL отдельно; cooperative signal не SQL fence и не global exactly-once. Эти ограничения сохранены, а не использованы для объявления гипотетического дополнительного subsystem обязательным.

**Ключевые критерии/доказательства:** DRT-18, SR-18; `02_Пакеты/DUR-02.md — REQ-DUR-02-01; REQ-DUR-02-02; TEST-DUR-02-01; TEST-DUR-02-02`; `02_Пакеты/DUR-02.md — REQ-DUR-02-03; TEST-DUR-02-03`.

### 13. WIRE-01 — LANE-06

**Вердикт:** нового gap нет; assessed 70/70 (27 addressed / 15 bounded / 28 not_applicable). Продукт NOT_RUN.

**Контракт и решение.** finite versioned typed state/outcome/safe codec. semantic depth растёт на user-child, не technical tag wrapper; closed registry и exact transmitted-byte digest.

**Различающая приёмка.** каждый accepted writer input читается own reader; Decimal tuple/negative zero exact, bytes/refs/journal retained; malformed tags/depth reject без extra attempt. Сквозной маршрут: actual typed writer → process pipe → corresponding reader/worker; v2 value.inputs отдельно literal legacy fixtures.

**Не расширять обещание.** stdlib и orjson реальные отдельно; legacy read не v2 writer rollback; backend raw parser ceiling может законно сузить admitted profile. Эти ограничения сохранены, а не использованы для объявления гипотетического дополнительного subsystem обязательным.

**Ключевые критерии/доказательства:** DAT-01, DAT-03; `02_Пакеты/WIRE-01.md — REQ-WIRE-01-01; REQ-WIRE-01-02; REQ-WIRE-01-03; TEST-WIRE-01-01; TEST-WIRE-01-02; TEST-WIRE-01-03`.

### 14. CAS-01 — LANE-06

**Вердикт:** нового gap нет; assessed 70/70 (30 addressed / 16 bounded / 24 not_applicable). Продукт NOT_RUN.

**Контракт и решение.** immutable CAS selected views и publication custody. existing exclusive lease writer проверяет input owners, staged members/intents, owner claims, completion; fixed stripes без eviction.

**Различающая приёмка.** один blob, default A неизменен, selected A/B exact provenance; tamper bytes/size/profile refused; revoke input owner между admission/publication. Сквозной маршрут: put A/B → transaction/member publication → restart → fresh selected refs; same content не tenant permission, readonly no lockfile creation.

**Не расширять обещание.** named local filesystem/recovery owner до qualification; corrupt отказ допустим, blob-only provenance запрещена; не universal NFS/FS guarantee. Эти ограничения сохранены, а не использованы для объявления гипотетического дополнительного subsystem обязательным.

**Ключевые критерии/доказательства:** DRT-02, SR-04; `02_Пакеты/CAS-01.md — REQ-CAS-01-01; REQ-CAS-01-03; TEST-CAS-01-01; TEST-CAS-01-03`; `02_Пакеты/CAS-01.md — REQ-CAS-01-03; TEST-CAS-01-01; TEST-CAS-01-03`.

### 15. CAS-02 — LANE-06

**Вердикт:** нового gap нет; assessed 70/70 (32 addressed / 13 bounded / 25 not_applicable). Продукт NOT_RUN.

**Контракт и решение.** closed-group CAS transfer и safe generation publication. directory previous generation retained by default; tar private sibling temp полностью closed/verified/fsynced до atomic replace.

**Различающая приёмка.** failed pre-replace B сохраняет byte-identical importable A; late user note/replaced member сохраняется; actual source→destination selected refs exact. Сквозной маршрут: source CAS → exact directory/tar inventory → verified staged groups → fresh CAS consumer; received/verified/reused/published различаются.

**Не расширять обещание.** no giant archive transaction; post-replace fsync не rollback A; bounded retained-generation decision; unsigned allowed policy сохраняется. Эти ограничения сохранены, а не использованы для объявления гипотетического дополнительного subsystem обязательным.

**Ключевые критерии/доказательства:** DRT-07, SR-11; `02_Пакеты/CAS-02.md — REQ-CAS-02-02; REQ-CAS-02-03; TEST-CAS-02-02; TEST-CAS-02-03`; `02_Пакеты/CAS-02.md — REQ-CAS-02-01; REQ-CAS-02-03; TEST-CAS-02-01; TEST-CAS-02-03`.

### 16. CAS-03 — LANE-06

**Вердикт:** нового gap нет; assessed 70/70 (28 addressed / 13 bounded / 29 not_applicable). Продукт NOT_RUN.

**Контракт и решение.** immutable verified snapshot и cancellable scoped batch census. stop probe внутри scanner/membership/dedup и после StopIteration; existing batch state vocabulary; one local integrity hash + independent crypto work.

**Различающая приёмка.** real Ed25519 sees same bytes; changed trust invalidates; scan/duplicate next stops после cancel; finished row retained, exhausted=false. Сквозной маршрут: selected CAS snapshot → current trust/crypto → bounded batch → actual CLI completeness; local item ERROR отдельно request-wide aborted.

**Не расширять обещание.** pending bound не O(1)memory: report/seen O(N), blob bytes(payload); signal не authorizer и не preemption; actual caller authorizer decision отдельно. Эти ограничения сохранены, а не использованы для объявления гипотетического дополнительного subsystem обязательным.

**Ключевые критерии/доказательства:** DRT-14, SR-04; `02_Пакеты/CAS-03.md — REQ-CAS-03-02; REQ-CAS-03-03; REQ-CAS-03-04; TEST-CAS-03-02; TEST-CAS-03-03; TEST-CAS-03-04`; `02_Пакеты/CAS-03.md — REQ-CAS-03-01; TEST-CAS-03-01; TEST-CAS-03-02`.

### 17. REP-01 — LANE-06

**Вердикт:** нового gap нет; assessed 70/70 (26 addressed / 15 bounded / 29 not_applicable). Продукт NOT_RUN.

**Контракт и решение.** direct Scientist replay activation и preserved Runtime compatibility. existing delayed direct exports/CLI wiring; no new replay subsystem; actual RES checkpoint owner.

**Различающая приёмка.** root10 lazy/shim20 exact identity; check-only producer0, actual replay executes, resume remaining once; tampered packet не исполняется. Сквозной маршрут: producer → CAS → fresh CLI/backend/resume; bit-exact refs не scientific validity, SKIP не PASS.

**Не расширять обещание.** historical RunManifest corpus finite; CI-bounded scientific interpretation UNQUALIFIED без domain oracle; retirement отдельное approved window. Эти ограничения сохранены, а не использованы для объявления гипотетического дополнительного subsystem обязательным.

**Ключевые критерии/доказательства:** DAT-01, DAT-05; `02_Пакеты/REP-01.md — REQ-REP-01-01; REQ-REP-01-02; REQ-REP-01-03; TEST-REP-01-03`; `02_Пакеты/REP-01.md — TEST-REP-01-01; TEST-REP-01-02; TEST-REP-01-03`.

### 18. CAN-01 — LANE-06

**Вердикт:** нового gap нет; assessed 70/70 (26 addressed / 13 bounded / 31 not_applicable). Продукт NOT_RUN.

**Контракт и решение.** strict canonical primitive с separate Core/IR profiles. one common primitive, explicit tags/errors/profile IDs; current decode/reencode conformance gate; no silent default for unknown version.

**Различающая приёмка.** source-qualified bytes/hash/exception goldens; raw aliases readable но nonconformant current writer/selected reader rejected; generic0.3 storage0. Сквозной маршрут: sync/async preflight → selected manifest/CAS → fresh profile reader; unchanged historical IDs, read-only history не current admission.

**Не расширять обещание.** historical corpus finite и alias candidate path только по реальной нужде; bounded enrolled0.3 не generic authority; Runtime/WIRE отдельные codecs. Эти ограничения сохранены, а не использованы для объявления гипотетического дополнительного subsystem обязательным.

**Ключевые критерии/доказательства:** DAT-01, DAT-03; `02_Пакеты/CAN-01.md — REQ-CAN-01-01; REQ-CAN-01-02; REQ-CAN-01-03; TEST-CAN-01-01; TEST-CAN-01-03`.

### 19. MIG-01 — LANE-06

**Вердикт:** нового gap нет; assessed 70/70 (23 addressed / 17 bounded / 30 not_applicable). Продукт NOT_RUN.

**Контракт и решение.** canonical migration CLI и owned atomic temp cleanup. tmp pathname captured immediately; tools.lib.fs single writer и actual SecureOutputRoot; existing real Trinity validator.

**Различающая приёмка.** write/flush/fsync/replace faults preserve old output/input; true Trinity no-op validates nested DTO; JSON/YAML/tuple/error identities separate. Сквозной маршрут: registered/installed CLI → canonical IR migration → atomic _dump → actual loader; missing operational binding no output.

**Не расширять обещание.** no-op validated-unchanged не converted/admitted; cleanup permission failure disclosed; power-loss не доказана OSError test; retired duplicate не возвращается. Эти ограничения сохранены, а не использованы для объявления гипотетического дополнительного subsystem обязательным.

**Ключевые критерии/доказательства:** DRT-07, RA-10; `02_Пакеты/MIG-01.md — §5; §7; §8`; `02_Пакеты/MIG-01.md — REQ-MIG-01-01; TEST-MIG-01-01`; `02_Пакеты/MIG-01.md — §8`.

### 20. MIG-02 — LANE-06

**Вердикт:** нового gap нет; assessed 70/70 (22 addressed / 17 bounded / 31 not_applicable). Продукт NOT_RUN.

**Контракт и решение.** RunManifest path-only normalization с declared root. Runtime converter whole-list preflight/deepcopy, source-root containment; no external copy/--to; uses MIG-01 writer.

**Различающая приёмка.** actual writer→CLI→fresh Runtime reader same path/bytes; collision basename не подставляет unrelated; mixed invalid entry no publication. Сквозной маршрут: RunManifest1.0 producer → normalization copy → native resolver; original bytes unchanged, unsupported layout refusal.

**Не расширять обещание.** point-in-time path identity, не immutable snapshot/relocation; relative root имеет explicit CWD; historical layouts finite. Эти ограничения сохранены, а не использованы для объявления гипотетического дополнительного subsystem обязательным.

**Ключевые критерии/доказательства:** SR-04, DAT-01; `02_Пакеты/MIG-02.md — REQ-MIG-02-01; REQ-MIG-02-02; REQ-MIG-02-03; TEST-MIG-02-01; TEST-MIG-02-02`; `02_Пакеты/MIG-02.md — REQ-MIG-02-02; REQ-MIG-02-03`; `02_Пакеты/MIG-02.md — §8`.

### 21. MIG-04 — LANE-06

**Вердикт:** нового gap нет; assessed 70/70 (23 addressed / 16 bounded / 31 not_applicable). Продукт NOT_RUN.

**Контракт и решение.** Fabric DatasetManifest format conversion и explicit registration. schema-adjacent Fabric callback + neutral Common engine deep-copy/stamp; one shared CLI _dump from MIG-01.

**Различающая приёмка.** complete provided-fields payload admits actual DTO; conflicts/unknown/missing observed, raw_hash/created_at не fabricated; Common import no Fabric. Сквозной маршрут: explicit registered converter → persisted output → real DatasetManifest/ManifestRegistry load/require; independent converted/admitted dispositions.

**Не расширять обещание.** format-only1.0 не target admission/reconciliation; historical mapping finite; optional validation only actual consumer need; legacy adapter support window. Эти ограничения сохранены, а не использованы для объявления гипотетического дополнительного subsystem обязательным.

**Ключевые критерии/доказательства:** DAT-01, DAT-03; `02_Пакеты/MIG-04.md — REQ-MIG-04-01; REQ-MIG-04-02; TEST-MIG-04-01; TEST-MIG-04-02`.

### 22. MIG-05 — LANE-06

**Вердикт:** нового gap нет; assessed 70/70 (23 addressed / 15 bounded / 32 not_applicable). Продукт NOT_RUN.

**Контракт и решение.** registration descriptor fingerprint и separate migration profiles. narrow try cell_contents; stable encoding outside except; existing common linear runner, distinct DataForge graph owner.

**Различающая приёмка.** unsupported capture raises before registry mutation; empty cell only proper marker; two-step Common/IR copy/stamp/error behavior; mutable semantic config control. Сквозной маршрут: callback registration → shared profile runner → actual DTO/public installed consumer; finite external callbacks/historical corpus, no blanket freeze.

**Не расширять обещание.** fingerprint registration snapshot не arbitrary callable identity; observers may mutate; reproducible converter needs explicit config/version, otherwise bounded nonreproducible. Эти ограничения сохранены, а не использованы для объявления гипотетического дополнительного subsystem обязательным.

**Ключевые критерии/доказательства:** DAT-03, DAT-05; `02_Пакеты/MIG-05.md — REQ-MIG-05-01; REQ-MIG-05-02; REQ-MIG-05-03; TEST-MIG-05-01; TEST-MIG-05-02; TEST-MIG-05-03`; `02_Пакеты/MIG-05.md — TEST-MIG-05-01; TEST-MIG-05-02; TEST-MIG-05-03; TEST-MIG-05-04`.

### 23. DFK-01 — LANE-12

**Вердикт:** нового gap нет; assessed 70/70 (24 addressed / 13 bounded / 33 not_applicable). Продукт NOT_RUN.

**Контракт и решение.** three exact legacy schema-surface decisions и installed distribution evidence. reuse schema_fqn_census v3 and existing Q2 origin gate; three independent retain/migrate/remove decisions.

**Различающая приёмка.** finite denominator actual bytes/unknowns; graph tie stable, canonical resources retained; actual wheel/sdist/rebuilt imports вне checkout. Сквозной маршрут: source census → lifecycle delta → installed canonical consumer; LANE-12 build evidence → CYC-05 appointed readiness verifier, не второй issuer.

**Не расширять обещание.** no universal absent consumer/schema inclusion theorem; unknown external obligation named; census не retirement authorization. Эти ограничения сохранены, а не использованы для объявления гипотетического дополнительного subsystem обязательным.

**Ключевые критерии/доказательства:** SR-02, SR-13; `02_Пакеты/DFK-01.md — REQ-DFK-01-02; REQ-DFK-01-03; REQ-DFK-01-04; TEST-DFK-01-02; TEST-DFK-01-03`; `02_Пакеты/CYC-05.md — REQ-CYC-05-04`; `02_Пакеты/DFK-01.md — REQ-DFK-01-01; REQ-DFK-01-05`; `02_Пакеты/DFK-01.md — §8 §10`.

### 24. HYG-02 — LANE-12

**Вердикт:** нового gap нет; assessed 70/70 (23 addressed / 14 bounded / 33 not_applicable). Продукт NOT_RUN.

**Контракт и решение.** actual governance facade migration и Fabric→Lex preservation. switch two actual facade imports first, typed owners remain; _shim decision independent; reuse Q2 installed evidence.

**Различающая приёмка.** Core Legal/Safety exact identity/validators; real Parquet selected columns/provenance; malformed index fail не empty; protected installed exports. Сквозной маршрут: facade/config/plugin → actual canonical pass; Fabric native reader → Lex; old facts unchanged, OPA/root evidence protected.

**Не расширять обещание.** finite helper/governance retirement windows; missing-segment current skip semantics retained; data reader не source authenticity/authority proof. Эти ограничения сохранены, а не использованы для объявления гипотетического дополнительного subsystem обязательным.

**Ключевые критерии/доказательства:** DAT-01, RA-09; `02_Пакеты/HYG-02.md — §5; §6; §7`; `02_Пакеты/HYG-02.md — REQ-HYG-02-02; REQ-HYG-02-03; REQ-HYG-02-04; TEST-HYG-02-02; TEST-HYG-02-03; TEST-HYG-02-04`.

### 25. HYG-04 — LANE-12

**Вердикт:** нового gap нет; assessed 70/70 (23 addressed / 14 bounded / 33 not_applicable). Продукт NOT_RUN.

**Контракт и решение.** bootstrap/benchmark address lifecycle и package smoke. existing Common jax_env and canonical bootstrap; exact three benchmark wrappers migration; one CP6 build/docs/Q2 window.

**Различающая приёмка.** four frozen profile commands recorded без installs; defaults before imports/overrides preserved; late-demo retired reference addressed beyond early guard. Сквозной маршрут: real entrypoint → early setup → bounded native benchmark/demo → actual package inventory; Runtime shell uses generated client, не readiness issuer.

**Не расширять обещание.** recorder не installation/workload proof; bootstrap Linux/Darwin scopes separate; benchmark listing не scientific validation; external obligations finite. Эти ограничения сохранены, а не использованы для объявления гипотетического дополнительного subsystem обязательным.

**Ключевые критерии/доказательства:** DAT-11, RA-07; `02_Пакеты/HYG-04.md — TEST-HYG-04-01; TEST-HYG-04-02; TEST-HYG-04-03; TEST-HYG-04-04`; `02_Пакеты/HYG-04.md — REQ-HYG-04-01; REQ-HYG-04-03; REQ-HYG-04-04`; `02_Пакеты/HYG-04.md — §8 §10 §11`.

### 26. CLI-01 — LANE-12

**Вердикт:** нового gap нет; assessed 70/70 (28 addressed / 16 bounded / 26 not_applicable). Продукт NOT_RUN.

**Контракт и решение.** OpenAPI-generated public client, safe wire keys и AST architecture gate. shared safe computed access/data entries, escaped path segments, own-property presence; TypeScript AST вместо regex; existing full-family generator.

**Различающая приёмка.** nonidentifier/reserved keys exact and own-only; actual TS/JS parse/type/call; three-output drift/UNRUN; bidirectional actual service result/error/binary. Сквозной маршрут: selected schema → private raw → canonical3outputs → generated client → actual scoped Runtime → same JS decoder; CYC-05 consumes build evidence separately.

**Не расширять обещание.** selected allowed GET/POST/binary routes, не103 executions; no external deploy; Node22 locked tooling; external raw consumers finite support decision. Эти ограничения сохранены, а не использованы для объявления гипотетического дополнительного subsystem обязательным.

**Ключевые критерии/доказательства:** SR-08, RA-09; `02_Пакеты/CLI-01.md — §5; §6; §7`; `02_Пакеты/CLI-01.md — REQ-CLI-01-01; REQ-CLI-01-03; TEST-CLI-01-01; TEST-CLI-01-03`.

## Проверенные гипотезы, не ставшие новыми findings

| Возможная претензия | Что обнаружено в текущем v2 / почему не новый дефект |
|---|---|
| DUR-01 примет подлинный, но старый budget snapshot и вернёт потраченные деньги | Текущий REQ/TEST различает readable и подтверждённый receipt, включает restore r поверх подтверждённого r+1, отказ/сверку и сохранение последнего расхода. Важна свежесть, а не одна аутентичность. |
| DUR-02 после потерянного ответа безусловно повторит уже совершённую часть | Контракт требует реальной reconciliation и выполнения только остатка под прежним operation identity, deadline/budget; unknown не преобразуется в no-effect. Fencing касается sibling write-inlets, а не только cooperative stop. |
| RUN-02 проверяет лишь удобный spawn и скрывает Linux fork после JAX | В v2 есть warm-JAX parent и выбранная Linux/start-method qualification; Darwin имеет отдельное свидетельство. Неподдержанный профиль не повод блокировать независимую правку EOF/drain. |
| MIG-05 называет registration snapshot семантикой изменяемого callable | v2 уже разводит эти понятия и требует discriminator изменения config после регистрации. Воспроизводимый converter требует явной стабильной config/version либо ограниченного nonreproducible результата. Narrow except-fix не задерживается произвольной перестройкой identity. |
| CLI-01 закрывается Python GET плюс fake 200 от клиента | v2 требует настоящую ответную сторону маршрута service → generated client → parsed/validated consumer, рядом с prototype/optional/escaping checks. Нет требования исполнять все 103 schema routes или внешнего deploy. |
| LANE-12 installed evidence — только дерево файлов и совпадающий hash | DFK проверяет построенные wheel/sdist/rebuilt и noneditable import вне checkout; build-key handoff связан с CYC-05, назначенным issuer и реальным loaded baseline/current N6. Полностью прочитан CYC-05: drift loaded-vs-disk отдельно негативен. |
| CAS-02 должен всегда требовать подпись | Текущий configured unsigned positive допустим по явной policy. Отказ любой неподписанной группы нарушил бы preservation; верифицированная группа не объявляется глобальной транзакцией. |
| CAS-03 cancellation обязана мгновенно убивать callback и держать O(1) RSS | Текущий pending-work bound не равен bound всей materialized census memory; running callbacks не обещаны preemptible. Проверка отмены размещена и внутри census/dedupe/StopIteration. |
| MIG-02 path-only обязан обеспечивать immutable custody и любое relocation | Явно обещан point-in-time path-only с root/CWD и без basename fallback; дальнейшую custody принимает реальный consumer. Усиление до новой storage subsystem не следует из scope. |
| Same-bridge parity STA-02/REP-01 доказывает научную правильность | STA-02 добавляет независимый численный anchor и настоящий prior-capable consumer decision; REP-01 сохраняет scientific UNQUALIFIED, а не выпускает сертификат из повторяемости. |

## Shared-контракты и незакрытые execution obligations

Полностью прочитаны текущие LANE-06/LANE-12 в `01_Лейны` и `03_Интеграция`; в `Сценарии.json` — нормативные выбранные лейны, global rules и P-CORE/P-PROCESS/P-DATA/P-PACKAGING. Прочитаны все 32 релевантные связи, включая cross-lane X01-B04, X02-B05, X03-B05. Binding покрывает только named part, не отменяет fault/compatibility/discrimination локального TEST. Формальный аудит всех 42 сценариев/12 лейнов выполняется родительской задачей отдельно.

До соответствующей приёмки остаются обязательными названные авторами решения и свидетельства: prior consumer STA-02; finite list/null grammar RES-01; link-vs-typed-partial RES-03; typed cancellation mapping RUN-03; recovery source/fs profile DUR-01; finite actual backend pair и authoritative fencing/reconciliation DUR-02; исторические corpus/support-profile; real installed/build/client routes и назначенный CYC-05 issuer. Их наличие в плане **не равно выполнению**. Они также не записаны как новые дефекты лишь потому, что этот независимый документарный аудит не выполнял продукт.

## Воспроизводимость и границы аудита

- `assessments.json`: 26 сущностей × 70 критериев, packet-specific аргументы, текущие REQ/TEST/section и source_refs; каждый ID ровно один раз.
- `findings.json`: пустой массив; новых подтверждённых findings нет, квота дефектов не применялась.
- `coverage.json`: все входные хеши, полные MD line ranges, точные выбранные JSON scopes, 32 binding, ограничения и source records.
- `validation.json`: **PASS_DOCUMENT_STRUCTURE_ONLY** — покрытие, ссылки, хеши; не продуктовый PASS.
- `progress.json`: итоговое состояние. Промежуточный прогресс сохранялся после каждого пакета.

Код продукта не исполнялся и не менялся; не было installs, native execution, external mutations или edits ТЗ. Независимые stdlib контрпримеры не запускались, поскольку после чтения полного контракта не осталось конкретной новой гипотезы дефекта, для которой они были бы доказательством. Выполнялись только stdlib-проверки структуры/ссылок/хешей audit artifacts. Записаны только файлы назначенной папки. Denied/pending/uncertain внешних действий нет. Чтение исторического v1 не подменяло текущий объект проверки.
