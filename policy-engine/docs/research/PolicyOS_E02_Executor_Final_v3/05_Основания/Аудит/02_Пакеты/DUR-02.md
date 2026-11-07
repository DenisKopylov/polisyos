# DUR-02 — поколение worker и безопасная смена backend

## 1. Решение

**C72, порядок 72/127, LANE-06. B38 и B78 оценены ограниченно; полного закрытия нет.** Срез `20d9009be21097bfbdc38a546a15cc60213b8ace`. Полная исходная карточка: строки 8387–8488. Это свежий проход после внешнего сохранения C71; утраченный прежний C72 не является доказательством.

Основные исходные дефекты больше не соответствуют прочитанным owners: store связывает execution writes с текущим `(job_id, owner, attempt, running, valid lease)`, проверяет affected rows и публикует terminal/progress/event в транзакции. Fallback различает pre-dispatch authority и неизвестный результат после dispatch: второй случай **не запускает local вслепую**. Это полезная реализованная работа, которую нельзя заменить возвратом к старому широкому `except → local`.

Остаётся **C72-R01, низкая серьёзность:** при typed недоступности store heartbeat прекращается без cooperative interruption signal, и handler на том же guard продолжает работу. Это не обход SQL fencing. Native custody/takeover и автоматическое согласованное продолжение после неизвестного исхода — отдельные **G01/G02**, а не выдуманное отсутствие всей реализации.

## 2. Две оси и исходные IDs

| ID | Исходное исправление | Фактическая цепочка способности | Итог |
|---|---|---|---|
| B38 | Старый A не меняет running/completed B; current B завершает, status/event согласованы | Worker связывает attempt → store admission/SQL → current row/progress/event. P01–P03 исполняют actual SQL/transaction methods на fixture schema; P04 различает виды потери heartbeat | Основной repair подтверждён ограниченно. R01 cooperative signal; G01 native custody/процессы |
| B78 | Разрешённый pre-dispatch переход не смешивается с неизвестным post-dispatch | Typed health witness/classifier → fallback decision → primary либо local. После эффекта и потери ответа только outcome_unknown, не второй эффект | P05–P07 подтверждают repair. G02: reconciliation и общий ресурсный контур handover не квалифицированы |

Наличие методов или тестовых файлов не равно закрытию. Неизвестный результат честно останавливает автоматический replay: это безопасное ограничение, но не доказательство способности завершить оставшуюся работу.

## 3. Actual producer → consumer и чтение

**Store.** Bound execution context передаёт точную identity. `_resolve_job_execution_fence` не позволяет caller заменить bound identity; `_job_fence_where` включает состояние и актуальную lease; `_require_fenced_write` требует одну строку. Terminal methods присоединяются к общей транзакции. Admission повторно проверяется при выходе: просроченная lease, сменившийся attempt или owner не получают commit. Допустимый terminal transition может снять lease внутри той же транзакции, не разрушая согласованную публикацию. SQLite `BEGIN IMMEDIATE` и PostgreSQL branch присутствуют; исполнен только SQLite subset [S01:1833–1887, 2112–2188, 6192–6230, 6427–6772, 6959–7072, 9522–9742].

**Worker.** Complete class связывает execution fence и interruption context вокруг handler. `renew=False` выставляет lost, а typed store timeout/unavailable только останавливает pulse. Guard смотрит на lost flag, а не на самостоятельный таймер lease. Эти фактические branches являются основанием R01 [S02:194–308; S09:48–55].

**Fallback.** Private sample должен относиться к тому же health object и свежему probe; typed BLOCK нельзя расширить legacy ALLOW. Без достаточной authority local запрещён. Before-dispatch connection failure классифицируется иначе, чем access/contract failure. Healthy primary вызывается один раз; caught execution failure порождает `PrimaryExecutionOutcomeUnknownError`, не local execution [S03:132–204, 206–348]. Local adapter и checkpoint прочитаны как соседние контракты. Checkpoint имеет собственный resume, но этот wrapper его автоматически не вызывает [S04; S11].

Полные worker/fallback/local/protocol/config и оба regression files прочитаны. Store — крупный файл, проверены полные relevant methods и их transaction consumers, не все 9806 строк. Полные пути, Git blobs, SHA256 и диапазоны находятся в [индексе источников](../05_Источники/C72_источники.json). Идентификаторы Sxx далее относятся к нему.

## 4. Реально выполненные проверки

Все семь наблюдений завершились MATCH. MATCH означает совпадение с описанным наблюдением, включая воспроизведённый residual, **не общий product PASS**.

| Probe | Наблюдение | Граница |
|---|---|---|
| P01 | A/1: renew=false; complete/fail/progress отвергнуты, SQLite dump неизменен. Bound B/2 обновляет progress и завершает с прежним artifact pointer. Поздний A всё ещё отвергнут | Actual SQL, fixture tables/row DTO/projection |
| P02 | Injected event persistence OSError при complete и fail откатывает status/progress/event и fixture outbox | Actual transaction rollback; не actual предметная outbox model |
| P03 | Lease, сделанная expired внутри транзакции, и попытка сменить generation откатываются целиком | Actual UTC и transaction exit admission, без clock stub |
| P04 | renew=false → guard interrupted. Typed store unavailable → heartbeat завершён, guard continued | Actual worker class/native guard; store fixture; оба потока joined |
| P05 | Три unchanged existing fallback tests: unknown after effect, разрешённая временная pre-dispatch ошибка, BLOCK против legacy ALLOW | Isolated bodies, helpers/backend fixtures, не pytest |
| P06 | Healthy success — один primary effect; разрешённые unhealthy/connection cases — один local; permission и message-only RuntimeError — ни одного; effect+lost reply — один primary и outcome_unknown | Реальный собственный SQLite effect journal является fixture, не платёж |
| P07 | Равный, но не тот же health object не удостоверяет probe; legacy ALLOW не расширяет недействительный witness | Actual authority control, не production health service |

Процессные тесты S08 включают реальные current/stale handler, expiry/new attempt, current completion, sibling mutations, CAS diagnostic retention и registered consumer. Они **прочитаны, но не исполнены**. Три выбранных existing bodies находятся в S07:160–238. Не следует переносить их результаты на прочие bodies или actual process suite.

## 5. Подтверждённый остаток C72-R01

При отказе продления `False` worker устанавливает interruption signal. Но при `RuntimeDependencyTimeoutError`/`RuntimeDependencyUnavailableError` pulse выходит без установки lost и без дальнейшего renewal. Handler, выполняющий настоящий cooperative guard, остаётся разрешённым на этой локальной границе. P04 различает оба случая и проверяет cleanup потоков; это не вывод из одного имени exception.

**Нужно:** согласовать невозможность дальше подтверждать lease с существующим signal: остановить дальнейшую работу либо иметь ограниченную политику переподтверждения до истечения срока. Нельзя бесконечно считать compute текущим после навсегда остановленного heartbeat. При этом SQL fencing обязан остаться обязательным: cooperative cancellation не даёт и не отзывает внешние полномочия самостоятельно.

**Предел:** опыт не моделирует реальный takeover и не доказывает защищённую stale write. Actual SQL controls P01–P03, напротив, её отвергают. Не измерены потерянные CPU/GPU минуты или внешний эффект. Низкая серьёзность относится к resource/cooperative lifecycle, не к заявлению о нарушенной безопасности всей custody цепи.

## 6. Что сохранить и что ещё квалифицировать

Сохранить current owner/attempt/lease predicates, affected-row checks, transaction admission на выходе, атомарную связь terminal/progress/event и отдельные terminal proof правила. Сохранённый CAS-артефакт старой попытки может служить диагностике: его не нужно удалять ради отказа прикрепить к current job. Сохранить typed health authority, ограничивающий BLOCK, точную связь witness с probe и fail-closed unknown после dispatch. Не присваивать SQL UPDATE гарантию exactly-once для внешнего действия.

**G01:** supported native process suite должен связать actual worker → actual initialized store → current rows/outbox → CAS/public scoped readback, включая expiry/new completed attempt и event failure. PostgreSQL и межпроцессная блокировка не квалифицированы fixture SQLite опытом.

**G02:** неизвестный post-dispatch исход требует фактической сверки рубежа, результата, владельца и внешнего действия прежде продолжения. Нужен общий LANE-06 контроль existing checkpoint/custody/operation identity и общего deadline/бюджета, а не отдельный новый журнал для этого пакета. C65/RES-01 остаётся самостоятельным ограниченным свидетельством checkpoint; он не переисполнен и не превращён в proof автоматического handover. В текущем wrapper такого автоматического reconcile нет; безопасный отказ не объявлен дефектом сам по себе.

Общая архитектурная цель здесь — расширять существующие универсальные owners и typed contracts. Специальные новые branches для каждого backend/задачи и универсальный детерминированный изобретатель моделей не требуются. Fixture effect подтверждает порядок вызовов, не научную или финансовую достоверность policy результата.

## 7. Команды, среда и статус

Bounded probe: exit 0, **7 MATCH**, **3 existing bodies / 3 cases**, native pytest bodies = 0. AST извлекает complete unchanged definitions; выбранный store class собран из методов. Schema/get_job DTO/quality projection/terminal source/outbox domain — fixtures; SQL, транзакции, affected rows и guard настоящие. Диагностические и tenant contexts, primary/local implementations также fixtures. Ожидаемые warning logs сохранены.

Native pytest attempt: exit 1, pytest отсутствует. Whole worker import блокирован Python-3.14 syntax в `core/contracts/runtime.py:7221`, store import — в `core/artifacts/store.py:2118`. Это Python 3.12.14/Pydantic 2.13.4, а project требует Python 3.14 и Pydantic <2.13; такие блокировки не product defects. Native compatible `common.job_execution_interrupt` и `core.errors` реально импортированы. Репозиторий чист и не менялся; зависимости не устанавливались; сервисы/платные провайдеры не вызывались.

[Команды](../04_Проверки/C72_DUR02/commands.json) · [Диагностика](../04_Проверки/C72_DUR02/bounded_diagnostics.json) · [Точные границы](../04_Проверки/C72_DUR02/native_verification.json) · [Остатки](../01_Реестры/C72_остатки.json).

**72/127 рассмотрены ограниченно. Следующий — WIRE-01. Фаза 2 не начата; это промежуточный checkpoint, не завершение всех работ.**
