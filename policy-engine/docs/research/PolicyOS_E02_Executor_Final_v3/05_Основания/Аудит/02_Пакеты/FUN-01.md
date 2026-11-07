# FUN-01 — версионный ticket и одинаковое full/split продолжение
## C22 · 31 октября 2026 года

**Исходные IDs:** B156, B158, B159. **Порядок:** 22/127, LANE-02. **Срез:** `20d9009be21097bfbdc38a546a15cc60213b8ace`. Только аудит; следующий — FUN-02.

## Решение

**Частичная оценка.** Старое смешение разных contexts и sentinel-ролей устранено более консервативным решением: отдельный запрос не переиспользует целый terminal outcome. Его текущие gates исполняются заново, а независимый источник численного результата должен переиспользоваться у своего owner. Это полезная защита, не основание вернуть старый cache ради совпадения с текстом плана.

Переход L2→L3 теперь проверяется **до** L3, включая прямой `advance(ticket, stage_a)` → `advance(ticket, full)`. Обход scheduler из B158 в ограниченном опыте не воспроизводится. Однако общий continuation остаётся незавершённым: тот же terminal ticket не возобновляется через `advance` даже при изменившемся budget; bound split через `submit(..., _prior_attempt_id=...)` вместо адресного продолжения безусловно очищает stage results и повторяет работу с первой стадии. **C22-R01** описывает этот ограниченный контрактный разрыв, не обход внешних полномочий. **C22-R02** — serializer сохраняет prior traces, но теряет общие parent/lineage/reason вне result-reuse ветви.

**20 observations MATCH, 0 ERROR** в итоговом replay. MATCH означает совпадение с наблюдаемым поведением, включая остатки. Настоящие selected AST методов, DTO, candidate identity и serializer исполнены; evaluator, scheduler, source-score admission, uncertainty, lessons/correlation — явные scoreless фикстуры. Native pytest/PolicyOS/CAS и научные результаты **UNRUN**.

## 1. Две оси: ремонт и полезное продолжение

[Исходный пакет](../05_Источники/FUN-01_исходные_строки.txt) различает научный предмет, численное переиспользование и организационную попытку. LLM вправе предложить новый предмет или новый контекст; orchestration обязан не выдать старый score за измерение нового, сохранить выполненную работу и проверить оставшиеся разрешения.

| ID | Ремонт — сохранить | Содержательный остаток |
|---|---|---|
| B156 | Раздельные tickets независимых requests; strict candidate/proposal equality; свежие gates; opaque context не получает reuse; sentinel не меняет обычную историю | Квалифицировать именно source-owner numerical reuse и independent calibration. Полный outcome cache не является научным источником; его возврат не предлагается |
| B158 | Before-next-stage guard на L2/L3, одинаковый scheduler-stop для full и direct split; решение не списывается второй раз в том же неизменном проходе | Bound Stage A/B повторяет ранние evaluate, а не только gates. Нужен безопасный контракт разделения переоценки допуска и повторного численного исполнения, с actual owners |
| B159 | Terminal не открывается простым advance; freeze и постоянный reject сохраняют запрет; costs/prior traces не стираются | C22-R01: нет доказанного адресного resume остатка по новому основанию; C22-R02: projected parent/lineage/reason не доходят до consumer вне reuse |

## 2. B156: actual identity и осознанно свежая попытка

`_candidate_identity` проверяет, что materialized proposal и фактически переданный payload совпадают. Candidate hash вычисляется по строгому JSON-native предмету; неподдержанные объекты, циклы, nonfinite и небезопасные integer не маскируются случайной сериализацией. Context hash также проверяется strict subject owner. Opaque context делает key uncacheable, но свежая работа разрешена. [S01:145–196,471–545; S03:39–202]

Главное изменение — `submit` **не публикует reusable aggregate decision** в `_ticket_cache`. Независимый запрос создаёт новый ticket; наличие старых `_cached_ticket_for_key`, `_latest_ticket`, `_carry_forward_completed_result` не доказывает активный cache path. P19 проверяет отсутствие вызовов continuation helpers в current orchestrator; поиск охватывает полный файл, но исполнение этих helpers не объявляется интеграцией.

* **P01:** dataset diagnostic 10 затем 20 — два вызова и два tickets; старое значение не возвращено.
* **P02:** sentinel исполняется отдельно; `is_sentinel` обычного ticket не меняется.
* **P03–P04:** одинаковый независимый request и opaque request выполняются свежо; whole-outcome cache пуст. Это **намеренное текущее поведение**, не самостоятельно новый дефект.
* **P18:** explicit prior с изменённым контекстом создаёт новый ticket с parent, lineage и отдельным prior trace; стоимость обеих физических попыток видна.

Новые `test_funnel_subject_identity.py` именно требуют fresh independent requests, recheck изменившегося lesson owner, real L1 после новых lessons и L5 после calibration ban. Это разумные отрицательные контроли против старого «тот же hash — значит можно не проверять gates». Их нельзя отменять ради старого test, ожидающего один вызов навсегда. [S05, полный файл прочитан]

**Граница:** P01/P02 используют диагностическое поле, не source-bound objective. Ни восстановление validity научного результата, ни статистическая независимость sentinel здесь не аттестуются. Независимость контроля требует действительных replicate/data/model basis, не просто нового UUID.

## 3. B158: переход защищён, форма API всё ещё меняет выполненную работу

[Advance owner, S01:648–879](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/search/funnel/orchestrator.py#L648-L879) проверяет pending edge перед запуском следующего stage, если предыдущий уровень 2/3. `_maybe_schedule_transition` также вызывается после результата; уже принятое решение для того же next_level не вычисляется снова. При target=2 первый вызов оставляет edge pending, а второй `advance` проверяет его перед L3. [S01:1407–1449]

Исполнены scoreless стадии 2, 3, 4 с неизменными candidate/context и без mutable owners. Scheduler — явная фикстура, фиксирует ребро (2,3); каждая стадия сообщает estimated cost=0.1.

| Путь | Scheduler=advance: вызовы L2/L3/L4 | Scheduler=defer: вызовы | Вызовы scheduler |
|---|---:|---:|---:|
| Full | 1 / 1 / 1 | 1 / 0 / 0 | 1 |
| Direct split на том же ticket | 1 / 1 / 1 | 1 / 0 / 0 | 1 |
| Bound Stage A/B с переданным prior ticket | **2 / 1 / 1** | **2 / 0 / 0** | 1 |

P05–P10. Во всех defer-профилях L3 **не запускается**. В advance-профиле full/direct estimated aggregate=0.3, bound=0.4; реальная сумма trace не скрывается. Конечный action в scoreless опыте — `defer`, поскольку source-admitted score не установлен; выполнение уровней не объявлено научным успехом.

Bound reset присутствует в реальном lifecycle: `_evaluate_candidate` получает ticket через `funnel_prior_ticket_id` только от двух callables одного concrete owner и передаёт его Stage B через `invoke_candidate_evaluator`. Это не только неиспользуемый private путь. [S03:134–172; S07:956–1040]

Почему нельзя просто убрать reset: lessons, correlation/access и другие owners могут измениться между Stage A/B даже при одинаковом JSON context. Их свежая проверка нужна. Почему всё же осталась задача: reset вызывает **целый `stage.evaluate`**, а не отдельную дешёвую ревалидацию допуска; текущий L2 evaluate включает symbolic identification, adjustment, positivity, proxy estimation, transport/refutation и persistence readiness. Оценка длительности/цены создаётся снова. [S08:107–262] Полный native L2 здесь не запускался, поэтому размер повторных затрат и наличие inner source cache отдельно не доказаны.

## 4. C22-R01 — continuation не отделён от повторного полного исполнения

**Тип:** подтверждённый локальный разрыв заявленного continuation-контракта; **важность:** средняя для stateful/API-профиля; **уверенность:** высокая в control flow, ограниченная в native численных затратах.

* **P11:** повторный прямой `advance` terminal defer без нового основания не исполняет ничего — сохранить.
* **P14:** budget изменён, scheduler теперь разрешает, но прямой `advance` всё равно ничего не делает: terminal проверяется до попытки актуализировать transition.
* **P12:** explicit prior и тот же context без нового budget/owner основания переводят **тот же объект** из terminal в активный, очищают stage_results и повторяют L2. Scheduler снова defer; L3 не прошёл, но повторная ранняя работа уже произведена.
* **P15:** при изменённом budget explicit prior действительно позволяет дойти дальше, но trace становится L2,L2,L3,L4, а не L2,L3,L4. Существующий результат не выбран как переиспользуемый; отдельного проверенного successor с адресным остатком не создано.
* **P16–P17:** freeze при неизменном owner не даёт вычислений, постоянный stage reject не исчезает. После снятия freeze direct terminal всё ещё закрыт; explicit prior reset запускает работу и сохраняет новые gates.

Решающая ветвь `submit` проверяет same context, но не terminal action, изменившийся terminal_basis и не ограничение «live Stage A». Затем прямо очищает results, снимает terminal и начинает с первого уровня. [S01:518–545] `_can_reuse_continuation` и `_carry_forward_continuation` существуют, но не подключены; **не предлагается механически подключить их**, поскольку они не являются доказанным владельцем всех современных admission contracts.

Это не доказанный обход внешнего бюджета/ACL и не претензия к законному новому независимому запросу P13. Остаток касается обещанного сохранного **continuation**: сейчас публичная возможность ограничена либо неподвижным terminal, либо повторным запуском stages. Нужен существующий owner-путь, который различает новое разрешение, re-gating и reuse пригодной неизменяемой работы. Если whole-stage reuse больше не разрешён по современной модели, это следует явно отразить в контракте и измерить допустимое inner-source reuse; не обещать «только остаток» по наличию старого helper.

Минимальные различающие проверки: неизменный terminal не порождает новую физическую работу как resume; изменившийся допустимый budget/owner basis ревалидирует нужное ребро; source-bound предыдущая работа переиспользуется лишь после актуальных gates; постоянный blocker не исчезает; retry_cheaper выбирает действительно другой разрешённый план. Нельзя просто выставить `is_terminal=False`, спрятать cost или обходить freeze новым UUID.

## 5. C22-R02 — часть lineage остаётся только в памяти

**Тип:** подтверждённый локальный producer→projection разрыв; **важность:** низкая/средняя для аудита продолжений. `_serialize_funnel_outcome` всегда сохраняет `prior_attempt_ticket_id`, prior trace и полную цепочку prior_attempt_history. Но `parent_ticket_id`, `lineage`, `continuation_reason` добавляются только при `result_reuse_source_ticket_id is not None`. Нынешние explicit-linked requests создаются с `result_reuse_source_ticket_id=None`. [S09:574–740]

**P20:** actual serializer body + JSON round trip: typed outcome содержит parent и lineage длины 2, projection их не содержит; prior_attempt_history длины 1 сохранена. Значит, **история не потеряна целиком**, и из prior refs часть связи восстановима. Теряется явная общая семантика lineage/reason, в том числе `live_split_gates_rechecked`. Consumer в blueprint записывает именно эту projection в `new_state.params['funnel_outcome']` и `['_funnel_outcome']`, а не исходный dataclass. [S09:973–993,1140–1170]

Минимальное направление — сохранить эти существующие fields для всех применимых attempts либо явно версионировать их отсутствие. Новый журнал/архитектура не нужны. Actual storage, blueprint run и downstream reload **UNRUN**; исполнен именно producer serializer, не весь consumer.

## 6. Tests: полезные, но противоречивые ожидания

**C22-G01 — native qualification.** `pytest` отсутствует (реальный availability command C19 exit 1); Python 3.12.14, требуемый repository профиль 3.14 не запущен. Новые fixtures не равны project tests. Source/CAS/work packets, learned VOI, correlated observations, lessons, access owner и uncertainty admission не выполнялись.

**C22-G02 — согласовать test intent, не автоматически вернуть старое поведение.** Полностью прочитан `test_transition_accounting_semantics.py`: terminal reuse, implicit live split и unchanged/changed budget tests ожидают старый cache path. Старый `test_stage_b_reuses_cached_stage_a_progress` ожидает hit без explicit prior. Current submit этого не делает, а новые subject-identity tests требуют fresh gates. Это исходные assertions, **не результат native pytest**. Перед закрытием нужно разрешить противоречие: где новая организационная попытка, где реальный split и что именно является reusable source. Удаление всех старых tests без нового distinguishing coverage тоже не решение.

**C22-G03 — reuse и calibration authority.** Новый ticket и новая sentinel-метка не доказывают независимое научное наблюдение. Путь actual immutable numerical owner→fresh admission→current stage consumer необходимо исполнить отдельно, включая реальный источник/replica. Отсутствие whole-ticket cache не означает отсутствия всей системы reuse; её внутренние owners этим пакетом не исчерпаны.

## 7. Доказательства и воспроизводимость

Actual definitions сверены с Git blob и исполнены без изменения repository. Настоящие dataclass StageResult/FunnelTicket/FunnelOutcome, Pydantic EvaluationBundle, candidate strict validation/hash и source serializer использованы в bounded harness. Project imports удалены; score admission остаётся NOT_ESTABLISHED; scheduler, stage, budget, envelope, logger, transfer context и recording/source gates — явные фикстуры. Ни один scalar не назван измеренным score.

Первая попытка: 17 MATCH, 2 ERROR — ошибка **аудиторского loader**, который отфильтровал `with_proposal` у второго класса. Исправлен только audit harness. Промежуточный повтор: 19 MATCH/0 ERROR. После добавления P20 итог: **20 MATCH/0 ERROR, exit 0**. Исходный error log сохранён; промежуточный короткий результат отдельно отмечен как transcript summary, не полный log. Репозиторий/зависимости неизменны.

[Диагностика](../04_Проверки/C22_FUN01/bounded_diagnostics.json) · [команды](../04_Проверки/C22_FUN01/commands.json) · [границы](../04_Проверки/C22_FUN01/Чтение_и_границы.md) · [источники](../05_Источники/C22_источники.json) · [остатки](../01_Реестры/C22_остатки.json).

**22/127 пакетов рассмотрены ограниченно; 56 уникальных B/LA частично оценены; полного закрытия нет.** Все 21 предыдущих reports/evidence сохранены. Следующий — **FUN-02 / B157, B160, B162, B165**.
