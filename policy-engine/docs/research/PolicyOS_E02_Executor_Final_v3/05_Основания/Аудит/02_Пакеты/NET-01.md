# NET-01 — владение соединением до подтверждённого cleanup
## C102 · LANE-08 · B87, B89, B90

**Решение: частично подтверждено, не закрыто.** У permit и физического handle теперь есть явные владельцы; неизвестный исход close не превращается в свободную заменяющую ёмкость. Подготовка stream охвачена finalizer, а connect/health/disconnect вынесены из общего lock. Осталась отдельная ошибка: cleanup task, завершившийся `CancelledError`, зацикливает ожидающий shield и блокирует event loop.

Срез `20d9009be21097bfbdc38a546a15cc60213b8ace`. **7 наблюдений:6 MATCH и1 PARTIAL. 29 неизменённых test bodies /37 cases:34 PASS,3 FAIL.** Ещё5 адаптированных current-profile cases не включены в этот PASS-счётчик. **102/127**, далее NET-02.

## 1. Две оси

**Исходный ремонт.** Acquire выполняет резервирование/registration, сетевую работу и публикацию отдельно; поколение, deadline, factory owner и exact handle повторно проверяются. Cancel/close race сохраняет pending owner и возвращает permit ровно один раз после допустимого settlement. Session отличает incomplete cleanup от fully closed и передаёт private pool registry для retry.

**Содержательная способность.** Это не только счётчик: actual pool/session управляет настоящим local FD, который продолжает читаться после injected close failure и становится EBADF только после подтверждённого retry. Same logical key не получает второй private pool до освобождения owner, другой partition остаётся независимым. Эти свойства поддерживают надёжную доставку данных, но не доказывают смысл, актуальность, права или научную истинность источника. LLM остаётся semantic proposer; отсутствие универсального deterministic inventor здесь не дефект.

## 2. Матрица исходных IDs

| ID | Подтверждённое полезное поведение | Остаток |
|---|---|---|
| B87 | Ошибка subscribe очищает acquired handle либо сохраняет exact retry owner. Повторный close завершает незавершённый cleanup. Checkpoint lookup/rewind и primary-error finalizer проверены при актуальном явном lifecycle-only profile. | C102-R01 может остановить cleanup при terminal task cancellation.3 старых tests не доходят до target из-за нового source-owner guard: C102-G02. |
| B89 | Cancel после permit/до registration, cooperative и suppressing connect/health, close-generation race, persistent disconnect failure, mutated handle/clone и repeated release проверены. Physical owner не теряется ради semaphore. | Терминально cancelled cleanup task не распознаётся как завершившийся: C102-R01. Native весь corpus не выполнен. |
| B90 | Gated connect/health не блокирует независимый release; два connect разрешены одновременно при max_size2. Deadline охватывает metadata lock и network admission, поздний handle не публикуется; provider TimeoutError остаётся отличимым. | Admission deadline не является обещанием мгновенно прервать некооперативное physical cleanup. Production throughput/latency не измерялись. |

## 3. Actual owner→consumer

1. `acquire/acquire_with_connector` используют один `_acquire_owned`; absolute monotonic deadline и cancellation count задаются до permit. Под lock резервируется ownership, а factory connect/health исполняются вне него. Публикация проверяет поколение, identity и остаток budget [S01:408–619].
2. Exact object identity маршрутизирует release; одинаковый session_id у clone не освобождает настоящий lease. Мутация admitted owner fields восстанавливается для retirement, а не допускается в reuse. Pending physical owner и `pending_permit` остаются связаны при ошибке close [S01:674–901].
3. `StreamingSourceSession` включает failed subscribe в cleanup; registry сохраняет exact private pool вне обычного cache. Logical stream key освобождается после successful physical closure, а не после удаления из `_in_use` [S02:501–934; S03:599–750; S04:1210–1347].
4. Process создаёт session до `try`, но сама create уже владеет startup cleanup. После успешной create checkpoint lookup, admission, rewind и обработка входят в тот же `try/finally`; cleanup exception добавляется к первичной, не заменяет её [S02:2429–2600,3104–3122].

## 4. Наблюдения и исполнимые границы

| ID | Результат |
|---|---|
| P01 |19 unchanged pool bodies/27 cases PASS: deadline/cancellation, late handle, provider timeout, owner mismatch, malformed/mutated handle, retry и exact permit accounting. |
| P02 |2 unchanged admission-race bodies PASS. Close во время connect ждёт реального FD retirement; cancel после permit сохраняет независимый sibling FD и возвращает только свой slot. |
| P03 |8 unchanged session bodies:5 PASS,3 FAIL до intended injected lookup/rewind/poll. Generic raw harness MATCH не заменяет assertion outcomes; итог PARTIAL. |
| P04 |Actual release зацикливается на cancelled cleanup task:10000 shield iterations, heartbeat не запускается, external child timeout3s и exit-9. MATCH означает воспроизведение дефекта. |
| P05 |5 отдельно адаптированных lifecycle diagnostics MATCH:3 finalizer ветви и2 physical FD producer→registry retry→fresh consumer цепочки. Явный disabled dedupe/at_least_once; CAS fixture, не native custody. |
| P06 |Удаление только физического close при прежних success counters ломает actual fstat oracle. Проверка видит ресурс, а не только объявленный статус. |
| P07 |4 bounded ordering controls: независимый release при gated connect/health, два concurrent connect и свободный metadata lock при disconnect. Не performance benchmark. |

[Диагностика](../04_Проверки/C102_NET01/bounded_diagnostics.json) · [команды](../04_Проверки/C102_NET01/commands.json) · [основной probe](../04_Проверки/C102_NET01/probe_net01.py) · [terminal cancellation](../04_Проверки/C102_NET01/probe_cancelled_cleanup.py) · [current profile](../04_Проверки/C102_NET01/probe_current_contract.py) · [порядок операций](../04_Проверки/C102_NET01/probe_concurrency.py).

## 5. Подтверждённый остаток C102-R01

`_close_connection` распространяет `CancelledError`; shared cleanup task становится `done=True,cancelled=True`. `_cleanup_pooled` безусловно повторяет `await asyncio.shield(cleanup_task)` внутри `while True`, принимая каждый terminal outcome за новую отмену caller. Повторное ожидание завершённого cancelled task не приостанавливает выполнение. Код не доходит до `cleanup_task.result()` и корректного retained-owner settlement [S01:867–900,1037–1070].

В контролируемом actual public acquire→release connector сам выбрасывает CancelledError из disconnect. Наблюдение source line882 зарегистрировало10000 повторов; heartbeat через200ms не исполнился, faulthandler сохранил stack внутри pool, внешний watchdog остановил только fixture child через3s. Production частота, потеря данных, утечка дескрипторов или overcommit этим не доказаны.

**Что осталось:** отличать caller cancellation при ещё активной физической очистке от terminal cancellation самой owned task. Сохранить exact retry owner, не освобождать permit при неизвестном close, не убрать shielding и не подавить отмену как успех. Existing normal/caller-cancel/persistent-error controls должны остаться зелёными; терминальный случай должен завершаться без busy loop.

## 6. Сохранить и доквалифицировать

Сохранить generation check, absolute admission budget, source-specific timeout, immutable admitted identity, exact-object release, retryable private pool и logical-key fence. Не увеличивать max_size и не заменять протокол голым BaseException+release. Физическая очистка может продолжаться за admission deadline — это честный ownership, не само по себе ошибка.

**C102-G02:**3 прежних finalizer tests теперь останавливаются на `source-owned event/version contract is unavailable`. Их FAIL сохранены. Отдельные актуальные invocations разрешают только lifecycle-only disabled-dedupe profile; это не повод убрать source-owner gate или объявить native suite PASS.

**C102-G01:** Python3.12.14 не supported3.14; native pool import блокируется TypeVar(default=...), native streaming —3.14 exception syntax; pytest отсутствует. Package shells и один dependency import adapter не меняют production algorithm, но не являются native graph. Real OS file evidence не равнозначно проверке live network drivers, native CAS/tenant/input closure или production нагрузке. Полный cross-loop/recovery corpus не выполнен.

[Исходная карточка](../05_Источники/NET-01_исходные_строки.txt) · [источники с SHA и Git blobs](../05_Источники/C102_источники.json) · [остатки](../01_Реестры/C102_остатки.json) · [границы](../04_Проверки/C102_NET01/Чтение_и_границы.md).

**102/127 — промежуточный аудит; следующий NET-02. Фаза заданий исполнителю не начата.**
