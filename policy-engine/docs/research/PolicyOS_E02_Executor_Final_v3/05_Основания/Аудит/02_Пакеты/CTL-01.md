# CTL-01 — независимые запуски, пустые предложения и владелец состояния
## Проход C12 · выпуск v010 · 31 октября 2026 · B118 / B119 / LA-015, этап 1/2

**Срез:** `20d9009be21097bfbdc38a546a15cc60213b8ace`. Репозиторий только читался. [Исходное поручение](../05_Источники/CTL-01_исходные_строки.txt) · [точные источники](../05_Источники/C12_источники.json) · [исполненные наблюдения](../04_Проверки/C12_CTL01/bounded_diagnostics.json).

## 1. Содержательный итог

Первоначальные fresh/empty механизмы существенно изменены. Новый полный run действительно получает новый `SearchRunState`; законченный результат — глубокий независимый снимок. Пустые batch ограничены отдельным числом попыток, transient-empty допускает следующий кандидат. Под тем же владельцем уже существуют lifecycle, native driver и совместимый facade; фактический autotune caller использует их напрямую. Не заказывать это повторно.

Но изоляция одного `run_search` ещё не равна изоляции всех взаимодействий с тем же владельцем. **C12-R02:** pending-ответ старого адаптера принимается после замены run-state другим driver и попадает в новый run. **C12-R01:** отказ/отмена генератора прерывает путь до счётчика и финализации, оставляя статус `RUNNING`, неполный снимок затрат и ранее полученные строки только во внутреннем состоянии. Второй механизм частично закреплён существующим characterization-тестом; это незавершённость полезной обработки прерывания, не заявление о неожиданной регрессии.

| ID | Уже сделано / сохранять | Остаток | Уровень проверки |
|---|---|---|---|
| B118 | Свежий state, глубокие snapshots, reset counters/diversity/stopping; запрет двух одновременных full runs | Pending/ask/tell должны быть связаны с фактическим run; отказ допуска не стирает pending | Полные S01/S02 исполнены с fixtures; lifecycle exact excerpts; native UNRUN |
| B119 | Отдельный count successful generation attempts; bounded persistent empty и transient recovery; budget checks вокруг генерации | Started/failed/cancelled attempts и частичный результат прерывания; источник empty-причины | 27 bounded observations; настоящий provider/ledger UNRUN |
| LA-015, этап 1/2 | Извлечение state/lifecycle и общий driver уже наблюдаются; autotune больше не конструирует full-loop facade на прочитанном пути | Приёмка фактического consumer, совместимость и lifecycle/retirement у SRV-03 | Source trace; не полный caller census и не весь LA closure |

**Полного закрытия нет.** Это не отрицание прежних успешных тестов: их текущая пригодность не переаттестована. Review-очередь не меняет implementation dependency CTL-01 → предшественник OPT-01. Частичное чтение SRV-01/SRV-03/CTL-03 не повышает их статусы в реестре.

## 2. Исходная цель и разумная переоценка

E02 требует независимого нового запуска и явного продолжения; завершённый отчёт не должен меняться после следующего run. Пустое предложение должно ограниченно завершаться или ремонтироваться, причём отсутствие предложений не доказывает исчерпания всех вариантов. Оплаченная генерация, отмена и отказ сохраняют свою причину. CTL-01 закрывает лишь первую часть LA-015; конечный владелец закрытия — SRV-03. [E02:1588–1723]

Содержательная цель для системы, где LLM формулирует гипотезы: точно знать, к какому исследованию относится ответ, какие попытки действительно сделаны и что уже получено до сбоя. Ни убедительность LLM-ответа, ни новый UUID не разрешают присоединить старую оценку к другой задаче. Алгоритмическая проверка принадлежности и завершения здесь уместна; универсальный новый генератор гипотез не требуется.

Не требуется запретить любое переиспользование. Внешний generator, вычислительный backend и допустимый warm corpus могут жить дольше run; их собственный continuation-контракт не нужно сбрасывать произвольно. Проверяется состояние именно запуска, а перенос научных наблюдений остаётся отдельной проверяемой операцией.

## 3. Действительная карта владельцев

```text
SearchController (исторический facade)
  → _SearchLifecycleOwner (config, evaluation, begin/finish)
      → SearchRunState (единственное mutable состояние)
      → _NativeSearchServiceDriver (run_search и ask/tell)
LegacySearchServiceAdapter(controller)
  → тот же controller._lifecycle_owner
SearchLoopRunner.run
  → новый _SearchLifecycleOwner + _NativeSearchServiceDriver
```

`SearchController.run` не содержит второй цикл, а делегирует lifecycle. `run_state.py` предоставляет отдельные операции принятия evaluation/tell и snapshot. `LegacySearchServiceAdapter` наследует действующий native driver, а не заново правит `_history/_best`. В текущем `autotune/runtime.py:1850–1945` наблюдается прямая композиция нового owner и driver; budget scope сохраняется. [S01–S06,S08]

Наличие caller-кода не доказывает частоту его production-вызовов. Не выполнены историческая trace-parity relocation-коммита, полный census string/public/import consumers, установленный wheel, реальные CAS и runtime. Имя `legacy` в комментарии не является основанием удалить работающий facade. Migration scope LA-015 не включает переписывание стратегий, funnel и всех objectives.

## 4. B118 — исправленная независимость обычных full runs

### 4.1. Свежий state вместо очистки общего списка

`_begin_native_run` сначала проверяет transfer basis, затем создаёт новый state с новым search_id, сбрасывает stopping и optional diversity. History, best, Pareto, счётчики генерации/оценки и sentinel начинают новую жизнь. Явные `initial_evaluations` копируются, а не добавляются к прежней случайной истории. [S03:439–555]

P01: A и B на одном owner дали два разных run IDs и по одной новой оценке; B совпал с запуском B на свежем owner в проверенных полях. История A осталась прежней. P02 менял вложенные объекты отчёта и owner в обе стороны: изменения не перешли через границу snapshot. P03 дал warm + новый record с индексами `[-1,0]` в каждом run, без накопления повторного warm. Это исполнение source-body orchestration с фикстурным objective, не подтверждение допуска любого реального warm-start.

`_finish_native_run` берет snapshot и отдельно копирует выдаваемые best/history/frontier/telemetry. P26 с удалением snapshot-copy в нашем harness вернул aliasing: это различающий контроль защищаемого свойства, а не изменение продукта. Не заменять новый объект state на `history.clear()` — такой ремонт снова испортит прежние отчёты.

### 4.2. Нереентрантность полного run действительно действует

`run_search` получает owner lock неблокирующим acquire и освобождает его в `finally`. P12 использовал настоящие `Thread/Event/Lock`: второй full run был отвергнут до замены state, пока первый удерживался внутри дешёвого evaluator. Первый затем закончил работу. Новый процесс, межпроцессный lock и работа сервисного HTTP не проверялись.

В репозитории уже есть тесты fresh snapshot, concurrency и scoped diversity: `test_search_loop.py::TestOptimizationFlow::test_repeated_runs_are_fresh_and_returned_snapshots_stay_stable`, `test_concurrent_runs_are_rejected_as_non_reentrant`, `test_diversity_telemetry_is_scoped_to_each_run`. Их текущие тела прочитаны, штатный pytest не запускался. [S10]

## 5. C12-R02 — старый pending-response пересекает границу нового run

**Серьёзность:** средняя, потенциально высокая при разрешённом совместном использовании facade/adapter. **Уверенность:** высокая в локальном переходе; реальный production scheduling и распространённость не измерены. **Исходная связь:** B118; companion SRV-01/SRV-03.

### 5.1. Причина

Driver хранит `_pending_candidates` и `_completed_candidate_ids` у себя, а run-state находится у общего owner. Pending связывается с candidate_id, но не с search_id или поколением owner. `CandidateProposal` несёт service_iteration, а не принадлежность run. `_accept_tell` проверяет предмет candidate/proposal и typed/source-проекции, но проверка предмета не устанавливает принадлежность организационной попытке. [S02:40–141; S05; S03:_accept_tell; S03:_validate_result_candidate_identity]

`SearchController.run` создаёт новый driver с тем же owner. Он очищает только собственные pending, не старый adapter. `_prepare_service_run` при STOPPED снова ставит RUNNING, не создавая новую идентичность. Нормальный same-session ask/tell поэтому поддержан, но тот же переход допускает старый ответ после внешней замены run.

### 5.2. Воспроизведение P16

1. Driver A выдаёт `old-A` через ask; его pending принадлежит run A.
2. Driver B на том же owner начинает новый full run B, оценивает `new-B` и возвращает отдельный snapshot.
3. Старый driver A получает tell для `old-A`.
4. Ответ принимается; текущая история B становится `[new-B, old-A]`, ordinary count — 2, статус — RUNNING, а tell сообщает ID **B**.
5. Уже выданный snapshot B не меняется — это сохраняемый положительный результат, не отсутствие проблемы live-state.

Входной EvaluationBundle-заменитель явно не устанавливает численную оценку: status NOT_ESTABLISHED, is_promising=False, policy_evaluation=None. Тем самым контрпример не зависит от подделки эмпирического evidence или обхода допусков. **Доказана неверная принадлежность history/counters, а не публикация чужого causal effect.** Materializer и source/objective boundaries в harness — заявленные fixtures.

P17 — существенный контроль: если новый run запускается тем же driver, его собственный pending очищается и старый tell отвергается. P28 — два законных ask/tell в одной сессии сохраняют run и работают. P18 сохраняет неизвестный/повторный ID guard; P19 — независимость payload, выданного caller.

### 5.3. Отказ допуска сам изменяет pending — P21

В `service.py:184–190` pending/completed/ask_iteration очищаются **до** acquire owner lock. Поэтому контролируемое занятое состояние lock даёт ожидаемый nonreentrant-отказ, но одновременно уничтожает pending у вызвавшего driver; последующий законный tell получает KeyError. Это соседнее проявление того же неполного контракта жизненного цикла, а не отдельный большой новый framework-дефект.

### 5.4. Минимальное направление

Связать pending с действительным run/epoch существующего owner и проверять эту принадлежность до принятия ответа. Все разрешённые переходы, способные заменить run или принять tell, должны иметь согласованный допуск; альтернативно явно и исполнимо запретить смешанное использование. Мутации reset выполняются только после admission. Старый ответ получает адресный отказ либо допустимое сохранение в своей прежней истории; он не переименовывается в оценку нового run.

P25 показывает только направление: простая harness-проверка прежнего owner ID блокирует этот пример. Это не готовый production patch и не полноценное доказательство race-safety — проверка и commit должны быть согласованы. Не блокировать законное same-session продолжение и не копировать весь owner в каждый adapter.

**Различающая штатная приёмка:** public LegacySearchServiceAdapter.ask → facade.run на том же owner → delayed tell; тот же сценарий с двумя adapters; допустимый tell в прежнем run; refused overlap не теряет pending; реальное конкурентное пересечение только под управляемыми events. Проверять run identity, history/counters, snapshots и source validity раздельно.

## 6. B119 — пустой batch ограничен без фиктивных научных оценок

`_prepare_batch` различает explicit initial_candidate и обращение к generator. Успешный возврат generator увеличивает generation_attempts, затем повторно проверяется бюджет до оценки. `_handle_empty_generation` увеличивает empty-streak; при cap возвращается STOPPED/generation_exhausted. Реальный непустой batch сбрасывает streak и сохраняет transient_empty. [S02:255–288]

P04/P06: пределы 1 и 3 дали ровно 1 и 3 пустых вызова, 0 оценок и 0 history. P07: `[] → [] → candidate` дал 3 генерации и 1 evaluation. P08: пустота между настоящими кандидатами сбрасывается только после непустого ответа. P11: explicit seed не создаёт фиктивный generator-call.

P09/P10 показывают место бюджетной проверки на fixture-owner: оплаченная пустая генерация или непустой batch, исчерпавший лимит, не вызывают evaluator после проверки. Это **не** проверка настоящего ledger и не подтверждение всех затрат. У текущего protected пути реальные `TracedLLMCandidateGenerator`/BudgetMiddleware сверяют выбранного владельца и типизированный binding; соответствующий native test использует реальный FileBudgetLedger и контролируемые provider bytes. Это полезная существующая проверка дизайна, не новый PASS. [S04,S10]

P27 отключил только empty-ограничитель в audit instance и вернул старое поведение до watchdog на шестом callback. Бесконечный процесс не запускался.

### C12-G01 — cap попыток и научное исчерпание не одно и то же

GenerationTransition имеет лишь transient_empty/exhausted, а producer protocol возвращает dict/list. Driver сам назначает exhausted после cap, не потребляя отдельное свидетельство того, почему generator пуст: конечное пространство, временный сбой, необходимость ремонта либо непригодная гипотеза. [S02,S05,S03:_generate_candidates]

Ограничить работу после трёх неуспехов разумно. Не установлено, что какой-либо реальный пользовательский текст уже ошибочно утверждает глобальную оптимальность или отсутствие решений. Поэтому это **граница смысла/дальнейшего действия**, не доказательство ложной production-публикации. Достаточно различать прекращение попыток и действительно известное исчерпание, сохранять producer reason там, где он есть, и deadline/новое основание для допустимого продолжения. Не считать любой empty доказательством и не добавлять фиктивные candidates.

## 7. C12-R01 — ошибка после начала генерации не получает завершённого run-снимка

**Серьёзность:** средняя для отказоустойчивости/учёта, выше при отсутствии внешнего долговременного владельца. **Уверенность:** высокая в проверенном source-переходе. **Исходная связь:** B119; lifecycle companion LA-015.

### 7.1. Наблюдение P13/P14

Generation callback сначала выполняется, и лишь после его возврата прибавляется generation_attempts. В `_run_locked` нет ветви финализации при исключении; `_finish_native_run` достигается только после нормального выхода из while. Внешний finally освобождает lock. [S02:177–272]

| Показатель в опыте | После первого успеха и второго отказа/отмены |
|---|---:|
| Реальных вызовов контролируемого generator | 2 |
| generation_attempts текущего owner | 1 |
| Завершённых строк, оставшихся внутри owner | 1 |
| `_finish_native_run` вызван | Нет |
| Статус owner после исключения | RUNNING |
| Траты external fixture / сохранённого snapshot | 2 / 1 |
| Следующий fresh run заменяет этот state | Да |

RuntimeError и asyncio.CancelledError сохраняют исходный тип/сообщение и выходят наружу; lock освобождается. Это положительные свойства. Ошибка **не проглочена** и не превращена в успешное empty. Но caller не получает частичный SearchResult через проверенный API, а второй начавшийся callback не вошёл в счётчик; post-dispatch снимок бюджета не обновлён.

Не утверждается потеря реального денежного списания: в опыте — простой счётчик external fixture, а настоящий durable provider ledger может отдельно сохранить event. Не установлен исход всего HTTP-job и наличие внешнего сохранения артефактов; проверен локальный owner/driver и его возвращаемый контракт.

### 7.2. Существующий тест это намеренно характеризует

`test_srv_03.py::test_lifecycle_owner_propagates_evaluator_exception_without_failed_transition` явно ожидает RuntimeError, статус RUNNING, ноль принятых iterations и освобождённый lock. Соседний сценарий warm→sentinel→empty→error→resume не бросает exception: его «error» — обычный feedback REJECT, а «resumed» — следующий кандидат внутри того же непрерывного run. Он не доказывает persisted resume после оборванного вычисления. [S12]

Поэтому нельзя назвать R01 внезапной регрессией без historical replay. Его статус в аудите — **сохраняемый ограниченный raise-path, не завершённая способность к частичному результату прерывания**. Переход к новой семантике нужно сделать намеренно и обновить characterization, а не просто «починить красный тест».

### 7.3. Минимальное направление

Развести начатую попытку, завершённое предложение и оценивание; текущий generation_attempts может сохранить свою объявленную семантику completed-call, но тогда started/failed/cancelled должны не теряться. При exception/cancel сохранить завершённую часть и адресную причину под прежним run, актуализировать учёт через существующего owner, затем сохранить предусмотренное распространение exception/cancellation. Результат может идти через типизированное прерывание, attached snapshot или существующий event/artifact-контракт — не обязательно возвращать обычный success-DTO.

Не ловить любое исключение как `[]`, не подавлять отмену, не начинать автоматически новое платное обращение, не копировать бюджет в альтернативный ledger и не повышать partial до converged. Доступность уже завершённой работы и ошибка следующего шага — совместимые состояния.

**Штатная приёмка:** один хороший кандидат → отказ генератора после provider settlement → сохранённая частичная история и правильный run; cancellation после settlement; отказ до dispatch; evaluator failure; negative source/budget controls; свежий consumer по действительной ref. Проверять started/completed/failed и реальные расходы раздельно.

## 8. Соседние наблюдения, не закрывающие следующие пакеты

**C12-A01 / B121, следующий CTL-03.** `apply_evaluation_transition` не добавляет sentinel в ordinary history и не увеличивает evaluation_iterations. Это правильно для обучения. Но full-loop hard limit и текущий MaxIterations читают именно ordinary/evaluation_iterations. В P22 генератор, выдававший только sentinels, при hard_limit=1 сделал четыре evaluator-фикстуры; пятый callback остановлен нашим watchdog, ordinary_count=0. Полной попытки бесконечного запуска не было. Настоящий MaxIterations прочитан, в probe он заменён эквивалентным по выбранному счётчику fixture. [S01,S02,S07]

Контроли P23/P24: независимый ресурсный предел остановил поток; explicit initial sentinel штатно завершился после одной оценки. Значит, не доказан обход всех budget guards. Нужен общий конечный ресурс/attempt-counter для последовательности контрольных вычислений без превращения их в обучающие строки. Основная оценка B121 оставлена следующему CTL-03.

**C12-A02 / SRV-01.** Четыре явно инициированных caller-вызова ask с пустыми ответами оставили owner generation_attempts=0 и generation_transition=None (P20). Это не внутренний бесконечный loop: каждый ask вызвал caller. Но одинаковая оплачиваемая операция имеет разные счётчики в двух API; соседний контракт должен назвать владельца учёта и stopping/resume, не случайно копировать часть run_search в ask.

## 9. Тестовая база и конкретный тестовый остаток

Предложенный историческим E02 `tests/unit/remediation/test_ctl_01.py` по текущему pinned path дал 404. Это не отсутствие проверок: S09/S10/S12 содержат relevant fresh/empty/shared-owner/concurrency/cutover tests. Исторический `test_native_search_lifecycle.py` тоже не используется как найденная команда. Нужны нынешние selectors, не восстановление старых имён ради формы.

**C12-T01, source-level:** `test_controller_api.py::test_search_controller_uses_facade_default_metrics_binding` создаёт SearchController без stage_a/stage_b/evaluators. Текущий `_SearchLifecycleOwner.__init__` до установки metrics безусловно требует оба evaluator и поднимает `SearchController requires Stage A and Stage B evaluators`. Поэтому этот тест не достигает утверждения об identity metrics. Это чтение пары test/constructor, не штатный результат pytest. Минимальное изменение теста — передать законные no-op evaluator ports, не ослаблять production-constructor. [S03:110–127,S11]

Некоторые warm/cost characterization fixtures используют bare objective_value без полного source-assessment. Их численная пригодность зависит от текущего OPT-01/CTL-03-контракта и не доказана нашими заменителями. Не объявлять весь suite зелёным и не молча приводить production к старому test expectation.

## 10. Матрица приёмки текущего участка

| Требование | Уже имеющееся свидетельство | Точный остаток |
|---|---|---|
| Два fresh запуска как два свежих owner | P01–P03 + S03 + native tests read | Настоящие DTO/objective/consumer на поддержанном Python |
| История законченного run стабильна | P02/P26; source deepcopy | Native serialized/readback, большие данные/ссылки по их контракту |
| Overlap full runs не заменяет state | P12 с настоящими threads/events | Распространить корректную границу на разрешённый ask/tell/facade mix |
| Постоянный empty конечен | P04/P06/P27; S09 | Полезная точная причина остановки; не научная полнота |
| Transient empty допускает кандидат | P07/P08; S09 | Реальный producer/consumer и расход генерации |
| Ошибка/отмена не стирает полученное | Причина пропагируется, lock freed; P13–P15 | R01 partial snapshot + attempt/cost owner reconciliation |
| Запоздалый ответ остаётся в своей попытке | Generic subject guards работают, P17/P18/P28 | R02 проверка поколения и атомарность admission/reset/tell |
| Один transition owner, не второй loop | S01–S06/S08, точные bodies | Остальные CTL-03/SRV-01/SRV-03 и compatibility/retirement |

## 11. Выполнено и доказательные границы

**27 наблюдений: 17 сохраняемых свойств, 4 строки двух контрпримеров, 2 соседние границы, 1 соседний B121, 1 direction-control, 2 removal-controls.** Все последние наблюдения MATCH. Пропущен идентификатор P05; это сохранённая нумерация, не скрытый 28-й результат. MATCH означает совпадение наблюдения с заявленным ожиданием, а не PASS всей платформы.

Полные `run_state.py` и `service.py` сверены с Git blob и исполнены без редактирования их bytes. Lifecycle — выбранные вербатимные тела в отдельной audit-оболочке; class wrappers/import setup принадлежат harness, полной Git-blob-сверки lifecycle нет. Реальны Python threading/locks/deepcopy и Pydantic field validation CandidateProposal. Objective, record DTOs, materialization/hash, logger, registry/source/budget/evaluator boundaries — явные fixtures. Проверки обычного scalar не подтверждают source admission реального score.

Первый запуск имел SyntaxError нашей harness-строки default generator — отсутствовала закрывающая скобка списка. Исправлена одна скобка в probe, исходный source и лог сохранены. Ни source PolicyOS, ни критерии наблюдений для обхода ошибки не изменялись. Последующий полный запуск выполнен заново.

**UNRUN:** полные project imports, native pytest, реальный LLM/provider, действительная paid settlement, Foundry simulation, WMR, CAS, HTTP, UI и весь autotune сценарий. Системный Python 3.13.5 не является заявленным baseline проекта 3.14.x. Зависимости не устанавливались; репозиторий не менялся; вычисления только в облачном контейнере. Контейнерный доступ к raw-source недоступен по DNS; connector pin reads и два blob-checks не выдаются за полный checkout.

## 12. Приоритетный остаток без новых подсистем

Сначала обеспечить принадлежность delayed tell и сохранить pending при отказе допуска. Затем оформить прерванную попытку с частичной историей и реальным budget-owner, сохранив оригинальные exceptions/cancellation. Нормальное fresh/empty поведение защищено existing tests и не должно переписываться. Потом CTL-03 согласует счётчики ordinary/training/sentinel и typed eligibility; SRV-01/SRV-03 доведут consumer-contract и cutover. Для закрытия LA-015 недостаточно наличия этого файла или нового имени класса.

**Следующий пакет исходного порядка — CTL-03: B120/B121/B123.** Соседние результаты здесь — вход к проверке, а не их полная приёмка.
