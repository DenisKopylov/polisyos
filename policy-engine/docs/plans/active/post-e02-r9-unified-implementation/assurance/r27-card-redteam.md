# R27: редтим рабочих карточек R26

Срез исходного плана: `fb9e078b85262b69f76e24255cd25a518102a0d4` (R26).
Это исправление документации исполнения, не реализация, приёмка E02 или новое
решение о product authority. Product verification: **UNRUN**.

Текущая карта: **262 карточки, 121 parent, 11 групп**.
[Короткий обзор](../execution/work-cards/overview.md) ·
[Маршруты](../execution/work-cards/coverage.json) ·
[Registry](../execution/work-cards/registry.json) ·
[Структурный readback](r27-validation.json).

## Как проводился разбор

Девять прямых reviewers прочли назначенные семейства целиком: CAP (25 карточек),
LIF (27), GYD-01–15 (20), GYD-16–33 (44), UI (30), CNT (17), DES (27),
OPS (27), DEB/P0/FINAL (44). Это полный исходный denominator **261 карточка**,
а не 261 независимая capability. Десятый reviewer проверил dispatch/источники и
7 карточек как дополнительный cold-implementer sample. Он не заявляет полного
повторного чтения остальных 254. Дети, продуктовые тесты, builds, установки,
сканирования production data и новые environments не использовались.

Root сверил findings с исходными task/preferred rows и original criteria,
внёс изменения единственным writer и проверил дельты. Отдельные повторные
reviews проверили границы исправлений. Все 388 task-local R19 question slices
и их соответствия 84 исходным question IDs разобраны по содержанию и значению ID;
mirrors в preferred-solutions сверены отдельно. Это не 388 новых требований.

Полные review memos, maps и решающие outputs находятся в ignored
`policy-engine/_build/post-e02-r27-redteam-20261024/`; их pins приведены в
readback receipt. В Git остаются решения и проверяемые маршруты, а не копии
source manifests и сырые отчёты. Историческая [проверка R26](r26-grouping-review.md)
остаётся на своём pin.

## Исправления по классам

| Класс / пример | Что изменено | Свойство будущей проверки |
|---|---|---|
| ID ошибочно связан с индексом соседнего массива | R19 `question_slices[].question_id` соединяется с `question_ids` по значению. Оба selectors указывают того же accountable receiver; смешанные обязанности имеют явные clause uses. | Перестановка массива не меняет исполнителя; wrong/missing ID отвергается. Не путать event arrival с missed duty без события. |
| Отложенная обязанность потерялась в соседнем механизме | LIF-02 duty и bounded observation отделены от native event replay; LIF-07 influence/current-use bindings восстановлены по actual ID. DES-10 shared denominators остаются у parent, конкретные кампании — у своих исполнителей. | Пропущенный срок без события всё равно меняет только enrolled claim; removal проверяет именно свойство, а не arrival marker. |
| Составной fragment назначен слишком узкому исполнителю | CAP-01 query, GYD-15 four FA1/N8 properties, CNT-05 metric/value/floor, R19 mixed slices получили конкретные secondary clauses. Cross-owner references ведут к уже назначенному target scope и не дублируют его работу. | Whole original criterion проверяется на композиции; локальный PASS не закрывает непроверенную часть. |
| Отсутствует настоящий producer | GYD-15 receipt-resolution и data-trust обязаны получить persisted native result с fresh N8 readback. При отсутствии внутреннего producer назначается его минимальное native extension. | Label/self-attested receipt не заменяет запись и фактического reader; Core CAS остаётся единственным byte custodian. |
| Пропущен самостоятельный recovery результат | Добавлена одна карточка `OPS-05.independent-copy-repair` у существующего CAS/archive writer. | Corrupt primary + independently verified permitted copy → verified immutable repaired version → fresh reader. Rehash corrupt primary/same failure-domain mirror не даёт healed. |
| Два владельца одного writer | DES-08 владеет lessons/retrieval; formulator sink delta направляется DES-01, hypothesis binding — DES-02. | Один writer/shared lease; consumer не переписывает supplier под своё удобство. |
| Bootstrap cycle | OPS-01 получает raw read-only effective-profile/build observation от существующего resolver. OPS-03 readiness появляется после commissioning receipt. | Первый запуск не ждёт уже выданной readiness; resolver не дублируется. |
| Слишком общий all-of | CAP-06 private roster нужен только выбранному private/federated profile. First remote call имеет intent до dispatch и reconciliation после него. | Public/non-federated путь не ждёт чужого roster; unknown effect не разрешает слепой retry. |
| Неявный selected supplier | CAP-02 называет exact CAP-01 candidate/profile receipt; CAP-05 — source→applicability→consumer. OPS/DES routes называют нужный output и стадию use. | Отсутствие выбранного output блокирует affected use, но не независимую подготовку и не всю supplier задачу. |
| Формальный no-egress inventory | OPS-12 требует независимо observed live interface/namespace/route set и reconciliation с observer/firewall coverage. | Пропущенный tunnel/update/crash путь оставляет claim not_established; тихие declared interfaces не дают универсальный PASS. |
| Edition без реакции на change | DES-06 включает affected current-view stale/limited, reevaluation и versioned successor при immutable исторической edition. | Старые байты могут читаться as-known, но не сохраняют silently current status. |
| Внутренний reader подменяет public/browser capability | CNT-04/05 назначают actual audience/rights-bound public projection; UI-19 включает browser; UI-08 явно связывает selected AtlasRunDeck. | Browser/public negative сохраняется, даже когда API/audit зелёные. |
| Неполный correction path | UI-02 соединяет выбранную correction с UI-04 event/feed и UI-19 derivative/status mapping. | Caveat-dropped derivative получает changed/unbound; исходный signed parent остаётся историческим. |
| Support ошибочно зависит от коллективного мандата | CNT-05 сохраняет поддержанные conditional results и отдельно principal-authorized hard floors. | Удаление только collective mandate запрещает winner/endorsement, но не уничтожает обоснованный conditional result. |
| Смешаны append admission и позднее чтение | CNT-06 supplies native structural assessment refs; GYD-12/O3 остаётся единственным WMR writer. | Missing structural/rival evidence отказывает **до append**; later-cycle reader проверяет уже admitted generation. |
| Freeze ждёт closure, которую должен проверить replay | FINAL-FREEZE хранит полную stage matrix в registry: 114 owner-readiness routes и полный P0 reconciliation. | 115 incoming routes не означают 115 закрытых findings. Review/replay остаются после freeze; внутренние отсутствующие механизмы не маскируются пустыми статусами. |
| Неразрешимые ссылки/неясный pin | Убраны `units.json.other_field_dispositions` и generic source-selector placeholders. Разделены manifest source base, current plan commit и accepted E02 source. | Холодный исполнитель разрешает exact source row/output и journal/lease refs без локальных scratch files автора. |

## Уточнение UI-12 без нового требования к окружению

Исходный [DS20-B5 contract](../../atlas-slices/DS20-server-authz-enforcement.md)
и [B5 closure](../../atlas-slices/DS20-server-authz-enforcement-closure.md)
требуют четыре реальных PostgreSQL properties на независимых store/app instances:
one step-up winner, one mutation + one 409, corrupted-head denial before OPA,
fresh-app rejection of unheaded CAS artifact. Они не требуют cloud hosting.

Поэтому commissioned **local или cloud PostgreSQL** допустим для этого generic
receipt; SQLite/mock/single instance — нет. `cloud` в старых source allocation,
resource и receipt labels не добавляет пятого критерия. Карточка явно фиксирует
это source-qualified прочтение; immutable manifest snapshot сохранён для аудита.
Отдельное утверждение о конкретном cloud deployment всё равно требует проверки
этого deployment. До E02 и настоящего execution receipt PostgreSQL остаётся UNRUN.

## Понятность и размер назначения

Новая repair карточка выделяет собственный producer/output и oracle; остальные
найденные проблемы исправляются связями и границами существующих карточек, а не
размножением owners. DES-06/08 остаются связными последовательными checkpoints
одного native writer. UI-02 сохраняет accessibility/locale/security/performance
и qualified human-review companions, которые root связывает с реальными owners
и outputs при dispatch; они не исчезли ради короткой страницы. UI-09 whole-estate
и UI-10 complete consumer denominator не дробятся на частичные closures.

FINAL-FREEZE — честно обозначенная aggregate coordination для 115 routes. Его
короткая карточка ссылается на полную matrix вместо её повторения. Root materializes
точный packet: current plan commit, accepted source, применимые clauses, journal
ref, actual owners/read/write/generated/resource leases и selected supplier outputs.
Шаблон не выдаётся за уже назначенную работу.

Peer question slices связываются общим actual ID: 343 повторяемые peer references
не сохраняются второй копией, их targets выводятся из уже проверенных own routes.
64 явно разобранные связи с existing output contracts остаются в `companion_refs`
(17 из них ведут к parent composition, а не выдуманной leaf-карточке).

`companion_refs` в coverage — navigation, не ещё один DAG или список mandatory
inputs. Если target уже владеет своим question slice, он не получает второй
write assignment из каждого ссылающегося parent. Реальный selected output остаётся
обязательным в указанном contract/use. Unknown ownership — повод разрешить границу
и назначить недостающую внутреннюю работу; не повод считать её external unavailable.

## Что проверено и что ещё нельзя утверждать

Lightweight stdlib readback обходит полный registry/coverage/card/parent/group
denominator, сверяет immutable source bytes, UID/selector сохранность, value-based
question bindings, references, original dependency stages и preparation DAG.
Бounded in-memory negative cases повреждают ID, удаляют fragment и меняют порядок
ID list. Это проверки документационной модели, не продуктовые тесты.

Не утверждается, что карта доказывает всю транзитивную семантику архитектурных
документов или исключает будущие implementation defects. При E02 rebind ещё нужны
actual native paths/owners, source-qualified supplier artifacts, generated surfaces,
backend/rights/resource availability и behavioral fresh-consumer witnesses. Source
freeze, code acceptance, full replay и formal closures этим review не выполнены.

Pattern pass: P01/P02/P03 — producer/bridge/surface; P04/P05/P08 — support,
authority/currentness; P13/P27 — context и single writer; P29/P31/P32/P35/P37/P38 —
полный denominator, actual identity и behavioral discriminator; P39/P40 — companions
не вытесняют механизм, повторные escapes устраняются на уровне общего класса.
