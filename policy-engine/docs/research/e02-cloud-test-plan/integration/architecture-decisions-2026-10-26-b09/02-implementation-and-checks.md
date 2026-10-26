# Реализация и приёмочные сигналы B09 source-only

Это будущая работа исполнителя, не выполненные G проверки. Контракт — [AD-E02-B09-01](01-decision.md). Implementation начинается на actual attached candidate; immutable inputs исследования не разрешают overwrite пяти существующих WIP файлов.

## 1. Последовательность без второй реализации

1. **Source reconciliation.** Прочитать пакет, actual diff и уже реализованные owner fixes. Сверить source frame/WIP hashes с [inputs](inputs.json). Existing first-source-only fixture оставить с прежним UNRUN/ограничением; построить настоящий sequential source producer. Freeze только coherent slice перед deciding wave.
2. **Общий prepared plan.** В `data_state_substrate`, `cycle_substrate`, `candidate_simulation` выделить существующие pure preparation/validation из функций, которые сейчас сразу persist materialization. Source selection и transforms не дублировать. Добавить typed versioned basis и owner relation, используемые как retain, так и reentry. Если готовый equivalent mechanism существует на actual source — wire it.
3. **Decision owner.** В `acquisition_world_growth` после selected positive receipt revalidate source/epoch, resolve latest retained evaluation из verified route fold, prepare обе стороны и issue `AcquisitionEvaluationDecision`. Comparison generic над полным typed plan этого supported schema; exact field/role coverage test запрещает silently drop новых required inputs. Hash/profile/schema mismatch — refusal, missing supported comparison — `not_established`.
4. **Один lifecycle dispatch.** `acquisition_action_service` и execution-port interface получают semantic decision operation после admission. Execute и recovery branches вызывают общий verified dispatcher; два текущих участка service, которые безусловно делают positive→reentry, не должны разойтись. Нижний `execute/recover` по-прежнему сообщает native `world_committed/no_growth`.
5. **История и projection.** Extend route receipts/authority sink/current-action resolver/continuation fold и Core history DTO; reuse существующий verifier в GET. Reentry v3 lineage не подменяется источником новой branch. Обновить generated API/client schemas и runtime dashboard consumer, если они входят в actual generated/public-surface closure.
6. **Reader-first rollout, review, затем affected wave.** Сначала принимаются readers/validators, потом emitter. Параметризованные native/source-bound positive/negative tests у actual owners и ordinary POST→fresh GET — обязательны. Code acceptance и B09 adjudication отдельны.

Конкретный изначальный footprint: `runtime/quality/{acquisition_world_growth,acquisition_route_loop,data_state_substrate,cycle_substrate,candidate_simulation,generation_cycle}.py`, `runtime/http/services/{acquisition_surface_execution,acquisition_action_service}.py`, `runtime/http/services/control/run_lifecycle.py`, `runtime/http/routes/runs.py`, `core/contracts/runtime.py`. Generation/source repository затрагивается, если basis resolution требует его существующих exact input readers; Core не импортирует Runtime. Файлы — owner map, не обязательная квота edits и не исчерпывающий список companions. На actual candidate пройти все uses terminal schema/outcome и affected generated DTO; не ограничиться примерами этого документа.

Для объёмных данных basis — existing immutable base refs/digests плюс typed effective delta, а не полная копия snapshots в памяти или Git. Повторно использовать verified owner projection/streaming hashing; вычислять только затронутую relation, не запускать N5, браузер или LLM для доказательства отсутствия semantic change. Полный read-set определяется actual binding/consumer contract: incremental optimization не оправдывает пропуск зависимых rows. Сохранить только небольшие basis/decision receipts; RAW source custody остаётся у existing CAS/retention owner. Ключ cache, если используется уже существующий owner cache, включает projection rule/codec/schema и dependency identities; stale cached equality не authority.

Один writer на acquisition lifecycle, один на shared schemas/generation; pure basis и verification можно проектировать отдельно, но не создавать два comparators. Scope не требует global E02 freeze или production payload, чтобы доказать controlled property. Current deployment coverage/issuer facts по-прежнему требуют собственных inputs.

## 2. Linearization, crash recovery и выбор предыдущей оценки

**Существующий selected-admission head достаточен как recovery point.** Порядок:

`executing → outcome_selected(verified native owner receipt) → semantic decision → source-retained terminal`

или

`… → semantic decision → world_committed_reentry_pending → actual reentry → reentry_completed`.

Не добавлять отдельную phase только ради названия source-only. Source-retained predecessor — именно current `outcome_selected` для этого positive growth. Legacy quarantine transitions остаются прежними; reentry terminal по-прежнему требует pending phase и реальный reentry ref. Не разрешать source-retained terminal прямо из unverified `executing`.

Decision CAS persist и event/head append — не одна магическая transaction. Использовать existing idempotent sink, event reconciliation и compare-and-set predecessor/lease. Ключ решения связывает action identity, selected admission, previous evaluation frontier и comparison-rule version; request UUID/clock не создаёт новый semantic result. Terminal подписывается только после readback связанных receipts. Повтор той же action возвращает выбранный terminal, не повторяет fetch, не делает новый N5 и не списывает стоимость повторно.

Recovery находит выбранный decision через существующий scoped event/action index с этим ключом, не через обход CAS или «последний файл». Если crash произошёл до записи discoverable relation, допустимо повторить чистую preparation/comparison от сохранённого admission и текущего frontier; прежний несвязанный blob остаётся orphan по обычной retention policy. Он не является второй occurrence или успешным решением. Повторная проверка после изменения frontier может создать другой decision; только winning conditional terminal выбирает действующий ref. Время повторной derivation не меняет idempotency key.

| Место сбоя | Требуемое восстановление |
| --- | --- |
| Admission выполнен, decision ещё нет | Восстановить existing selected growth через owner; сравнить после revalidation, без нового transport fetch |
| Decision CAS есть, terminal/event ещё нет | Reconcile exact decision, refs, event и current frontier; завершить условно либо пересчитать decision после changed frontier; сам CAS blob не означает terminal |
| Terminal/event есть, ответ потерян | Existing head readback возвращает тот же факт; не выпускать вторую evaluation/history occurrence |
| Одинаковое основание у двух concurrent new sources | Два настоящих acquisition события сохраняются; при допустимом serial frontier оба могут retain одну оценку, но каждый decision связан со своим admission/action |
| Соседняя route изменила candidate context/eligibility после сравнения | Старый decision не коммитит current terminal; re-resolve current evaluation frontier и compare. Одного per-route sequence number недостаточно, если это не защищает общий candidate |
| New-profile reader/owner недоступен после admission | Source receipt сохраняется; typed unresolved/recovery, не no-growth и не неявный retained/reentry |

Сериализуется **selection frontier данного candidate/task**, используя existing current-job lease/action-head guard и owner versions. Не брать глобальный tenant lock на численную работу. Если current guards не покрывают sibling-route/context changes, расширить existing conditional selector одной проверяемой frontier dependency. Проверка «до commit всё совпало» без защиты от изменения между check/write не достаточна. Clock timestamp не является concurrency token.

В dependency frontier входят также использованные native admission/active-overlay и eligibility versions: candidate pointer сам по себе не защищает от параллельного отзыва источника. Existing overlay mutation lock/version и action selector согласуются в короткой ordered critical section на revalidation/terminal selection; CAS immutable bytes можно подготовить заранее. Если stores разные, нужен существующий owner lease/fencing protocol, охватывающий все deciding selectors, а не предположение об общей transaction. Непокрытая race — `verification_missing`, не разрешённая eventual-consistency граница для positive terminal. Последующая revocation после linearization — отдельное событие invalidation, не переписывание исторического решения.

History fold обязан обработать новый variant явно. `quarantined_no_growth` не меняет selected evaluation; `reentry_completed` продвигает её; `source_admitted_evaluation_retained` проверяет relation, новый source и совпадение retained tuple **с текущим аккумулятором fold**, затем оставляет evaluation неизменной. Нельзя просто `continue` без verification: иначе forged receipt прикрепит чужую/устаревшую оценку. Unknown terminal/schema → typed unsupported/unverified, не fall-through в reentry. `resolve_action_generation` принимает новый verified terminal как завершённого predecessor, поэтому дальнейшая acquisition generation не блокируется.

При sequence A→B→B→C сравнивать третью occurrence с выбранной evaluation B, а не первоначальной A и не с последней receipt любого вида. Если позднее приходит A снова после C, это изменение текущего основания; старый совпадающий A из истории не даёт разрешения тихо откатить evaluation. Не превращать историю в неявный cross-run cache.

Acquisition cost/attempt audit сохраняются и учитываются once по существующим правилам. Source-only не выдаёт бесплатный acquisition, не делает фиктивный N5 charge или возврат. Терминал сообщает о завершённом action, а не об удовлетворении всей research requirement: сохранять её реальное состояние. Authorized robustness/new-estimand intent проходит собственный существующий evaluation flow; zero-growth acquisition retry не может самовольно отменить или создать его.

## 3. Migration и совместимость

- **Legacy immutable bytes не менять.** V1 route, unversioned/v2 history и прежние reentry receipts разрешаются прежними exact readers. Не заполнять отсутствующий basis фиктивным defaults. Новые refs не добавляются в manifest старой оценки.
- **Baseline basis из прошлого:** допустимо выпустить новый derivation receipt сейчас, если existing owner может полностью восстановить effective basis из exact persisted N5/context/model inputs и original semantics. Receipt указывает реальное время derivation, старые source refs и rule version. Это не backdated execution. Нельзя реконструировать basis из одного summary/output scalar. Невосстановимо → retain unavailable; уже readable история не ломается.
- **Readers first:** union/version dispatch у CAS owner, sink/head resolver, route fold, GET, OpenAPI/generated clients и UI; затем enable source-retained writer. Старый consumer, не понимающий новый enum, не получает его как старую версию. На развёртывании, где ещё есть старые readers, emission выключен; допустим старый честный reentry с расходом ресурсов. Это временный rollout mode, не full B09 acceptance.
- **Schema selection:** route manifest `2.0` и payload `@2.0` должны совпадать; GET v3 нужен для новой branch. Existing v1 не принимает third outcome. В v2 все variants проходят отдельные инварианты; normal legacy branches могут продолжать читаться/выдаваться по старым версиям. Unknown version не интерпретируется как ближайшая известная.
- **Rollback:** отключить новый emitter, сохранив новый reader. Rollback на старый binary допустим только при доказанной совместимости selected store/истории, иначе это несовместимый rollback. Не удалять CAS/events/heads с новым outcome и не переводить их в quarantine/reentry. Receipt/history refs остаются retention roots existing storage policy.
- **Generated/public companions:** использовать существующие API generators, public-surface contract, README и release fragment; source-only badge должен означать «новый источник; прежняя оценка сохранена», а не «новая оценка». Stable GET snapshots должны показывать both lineage planes и limitations. Нельзя отложить DTO/client consumers после включения writer.

Historical event-time explanation не переписывается при поздней revocation. Новый текущий read/admission evaluation замечает invalidation и ограничивает дальнейшее использование, сохраняя возможность видеть прежний факт в audit. Исторический retention decision не становится lifetime authorization.

## 4. Решающий acceptance matrix

Проверки ниже **UNRUN у G**. Автор выполняет на exact candidate после review при выделенном local compute slot. Controlled WDI transport допустим; consumer path должен быть настоящий ordinary POST → authority/service → producer/epoch → CAS/action head → fresh HTTP GET. HTTP tests без actual producer либо один первый источник не закрывают свойство.

| ID | Сценарий | Что обязано наблюдаться |
| --- | --- | --- |
| V3-S01 | Sequential e1 изменяет meaningful row/slot относительно prior evaluation | Тот же candidate/task переоценён; новый WMR/N5 input/execution/cycle history; prior artifacts читаются |
| V3-S02 | После S01 настоящий e2: иной RAW/transport receipt, тот же complete effective basis | Native positive delta и новая admitted source; новый verified source-retained terminal; **точные прежние** selected WMR/N5/candidate/cycle refs; нет новых execution/materialization событий |
| V3-S03 | Повтор request/id/time над уже admitted тем же epoch; отдельно retry той же action | Literal-zero no-growth invariant и no second fetch/reentry. Retry той же action не создаёт charge; отдельная action сохраняет свой attempt audit и только реально разрешённые existing cost rules, не фиктивную цену N5 |
| V3-S04 | Ещё e3 equivalent, затем e4 changed | Несколько source-only occurrences не ломают generation/fold; e4 сравнивается с retained current evaluation и правильно reenters |
| V3-S05 | Одинаковый scalar, иные unit/population/year/weights/multiplicity или missingness | Relevant basis меняется/typed refusal; не source-only. Genuine independent observation не дедуплицируется только по value |
| V3-S06 | Изменить mapping/rule, selected profile, model/assumption/calibration, relevant registry facet, horizon/comparator/seed/replications | Каждый actual consumed change приводит к different/reentry либо конкретному refusal. Wrong sibling-profile не становится допустимым от совпадения значений |
| V3-S07 | Изменить prerequisite N6/value/requirement/eligibility, сохранив численный N5 output | Новый terminal не допускает пропуск изменившейся continuation. Проверяется полный skip scope, а не один N5 scalar |
| V3-S08 | Сохранить markers/«equal» hash declaration, убрать required basis facet или подменить owner receipt | Semantic verifier отказывает. Unknown/missing reader/schema не трактуется как equal/default |
| V3-S09 | Remove source-only terminal→history join; CAS/growth/decision bytes оставить | Fresh GET не показывает ложную полную историю: typed incomplete/unverified или failing oracle; наличие blobs не заменяет bridge |
| V3-S10 | Подставить другой tenant/cell/run/task/action или старый, уже не выбранный evaluation | Scope/frontier refusal, без утечки данных/authority; forged continuation нельзя присоединить через совпадающий hash |
| V3-S11 | Сбой на каждой границе admission/decision/event/terminal; response loss; duplicate job | Recovery без refetch/N5/двойного spend; тот же verified selected terminal; orphan decision не public success |
| V3-S12 | Sibling update либо source/overlay revocation между compare и terminal append; два equivalent источника конкурентно | CAS/lease/frontier и native owner fencing предотвращают stale retain; обе genuine occurrences сохраняются, selected evaluation корректна |
| V3-S13 | Legacy v1/unversioned/v2 reads, reader-first writer-disabled, mixed history, rollback emitter | Старые bytes/meaning сохранены; новый status не coercion; unsupported старый reader не выдаёт green/history-drop |
| V3-S14 | Declared limited candidate с source time/currentness unknown | Wiring может PASS в этом scope; false publication/currentness/calibration не появляется. Equality unknown отдельно от allowed limited input |
| V3-S15 | Новый authorized robustness/research intent на прежних данных | Не подавляется как ID-only retry; меняется intent/основание выбранного evaluation flow. Один новый UUID без него не создаёт investigation |
| V3-S16 | Новый required field/consumer dependency в supported plan schema | Она участвует в basis/comparison либо требует explicit supported role/version; старый comparator не остаётся permissive |
| V3-S17 | Legacy prior evaluation без reconstructable effective basis / вообще без execution | Нет ложного retained result. History readable; bounded diagnostic либо разрешённый реальный evaluation |
| V3-S18 | Пара одинаковых canonical rows с меняющейся RAW сериализацией, затем malformed/tagged/numeric corner | Valid formatting-only case S02; malformed не «исправляется» comparator; применён actual selected codec |

В S02 отсутствие работы проверяется по фактическим owner calls **и** persisted event/artifact/head closure, не только monkeypatched counter. Counter может быть дополнительным observer. Независимый oracle сопоставляет подготовленные inputs с потреблённым reentry/N5 path; mutation того же test-only dict не доказывает property. Для set-level claims пересчитать полный selected scope, назвать unresolved classes. Matched removal выполняется на isolated exact candidate и сохраняет relevant markers. Общий replay не заменяет эти distinguishing checks.

Минимум decisive outputs: exact source/tree/profile/toolchain; исходный и новый source/admission identity; actual membership snapshots/delta; old/new effective bases; comparison/retention evidence; предыдущие и selected после действия refs; POST/GET/event outputs; recovery/negative outputs; actual call/resource/spend evidence. Counts пересекающихся checks не суммируются. Raw большие логи остаются ignored с hash; tracked handoff хранит ссылки и полный краткий verdict. External authority/currentness/production population остаются отдельными inputs, не создаются G choice.
