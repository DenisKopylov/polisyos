# R23: самостоятельный критический разбор R22

24 октября 2026. База: `c71e972d519e84754b5a5fcf31ec601ffe613f65`
(опубликованный R22). Review и изменения выполнены root самостоятельно, без
субагентов. Только документация и лёгкие текстовые/JSON-проверки; product imports,
тесты, сборки, установки и production reads не выполнялись. Реализация остаётся
после фактической приёмки E02; `product_verification=UNRUN`, `closure_ids=[]`.
Новые нормативные SDD не предлагаются и не изменяются.

## Вывод

R22 сохраняет правильную основу: один native owner на семантический invariant,
scoped fences, раздельные assessment/use и retention, actual producer→consumer
joins. Однако четыре места оставляли ложный критерий успеха или ненужное
ограничение. Исправлены существующие задачи, их human/machine решения и будущие
acceptance cases. Новые верхнеуровневые задачи, сервисы, enums, прямые зависимости
и stage barriers не потребовались.

Это содержательное review определённых стыков, а не доказательство оптимальности
всего корпуса или текущего runtime. Основания — точные контракты R22, исходные
обязательства R16/R17 и failure register. Новых внешних технологических фактов
или сравнений библиотек этот раунд не утверждает; web search не требовался.

## R23-01. Reuse не должен превращать все методы в детерминированные

**Дефект.** LIF-01 требовал, чтобы disabling cache сохранял scoped decision;
LIF-07 — qualified result. Между тем [R16, «Как проверять» и Q14](10-composition-reexecution-quality.md)
уже различает deterministic sample-path и statistical guarantees. В короткой
карточке отсутствовала необходимая привязка к invocation intent. Один и тот же
законный случайный метод может дать разные realizations; кэширование одного draw
также нельзя выдавать за новое независимое evidence.

**Решение.** LIF-01/07 и CAP-03 различают:

- возврат именно сохранённого assessment/realization;
- повтор вычисления по его qualified replay contract;
- новый replicate/evaluation/provider response со своим invocation basis.

Это значения существующего native method contract, не новые product enums.
Relevant executable/backend/state/random-stream provenance связывается только
там, где требуется выбранной гарантией. Integer seed сам по себе не доказывает
replay. Cache-off сравнивает один basis/use cut и тот же заранее выбранный
критерий; statistical agreement не заменяет exact referenced artifact. Новый
draw не берётся из старого cache hit, повтор draw не увеличивает число
независимых наблюдений. Текущие rights/retention/freshness fences сохранены.

**Почему это лучше альтернатив.** Всеобщая bitwise equality отрезала бы
поддержанные stochastic/numerical методы. Всеобщая «примерно одинаковая
статистика» позволила бы подменять конкретное историческое свидетельство.
Разделение native guarantees сохраняет обе возможности без нового verifier.

**Различающие проверки.** Frozen-realization replay positive; отдельный
fresh-replicate positive с method-valid uncertainty/dependence accounting;
reused draw as new evidence negative; removal invocation relation при
сохранённых seed/cache markers. При смене use cut старое admission не переносится.
Задачи: [CAP-03](../solutions/01-capture.md#CAP-03),
[LIF-01](../solutions/02-custody.md#LIF-01),
[LIF-07](../solutions/03-lineage.md#LIF-07); R16 C3/Q06/Q14 companions обновлены.

## R23-02. Порядок receipt не является порядком состояния источника

**Дефект.** R22 корректно отделил local observation journal от внешней continuity,
но CAP-04/LIF-02 не задавали различающий случай перекрывающихся polls. A начал
раньше, B увидел изменение и fenced use, затем A вернул старые bytes. Его более
поздняя запись в local journal не подтверждает возвращение источника к A и не
может снять уже известную invalidation.

**Решение.** Existing capture/claim owners связывают attempt, actual
request/observation interval, expected observed head и основание сопоставимости.
Native source-order evidence используется там, где оно есть. Stale/incomparable
reply сохраняется как разрешённое historical/conflicting evidence; снять fence
можно только actual scoped reconciliation. При недостаточном основании —
bounded follow-up или limitation. Clock/opaque ETag/arrival offset не назначают
succession. Даже удачная reconciliation восстанавливает только подтверждённый
observation/as-of use, не пропущенную непрерывность или правовой effective time.

**Почему это лучше альтернатив.** Глобальная сериализация сетевых запросов
подавляет параллельность и не доказывает freshness внешних replicas. Last-arrival
wins теряет known facts. Сериализуется лишь нужное head transition; независимые
источники и чтения остаются параллельными, LIF-03 не получает второго writer.

**Различающие проверки.** Обратный порядок завершения A/B; B coverage-loss вместо
нового root; supported successor/reconciliation positive; unrelated scope
progress. Удаление expected-head/order reconciliation при сохранённом журнале
обнаруживается actual fresh consumer. Задачи:
[CAP-04](../solutions/01-capture.md#CAP-04),
[LIF-02](../solutions/02-custody.md#LIF-02); R16 C4/Q09 companions обновлены.

## R23-03. Recovery обязан проверять требуемое, а не восстанавливать запрещённое

**Дефект.** OPS-05 step «verify all referenced bytes» конфликтовал с уже
поддержанным query-only/result-receipt и lawful erasure. Он также мог превратить
весь архив в обязательный full-payload startup scan. Отдельно его краткий
deliverable/rollback и deployment guide всё ещё называли N-1 вместо полного
фактически поддержанного directional compatibility set.

**Решение.** Native representation/use contract и actual LIF-05 outcome задают
recovery obligations:

- required retained payload проверяется и доступен до его protected use;
- lawful result/receipt проверяется по своему execution/content binding,
  без требования скопировать запрещённые raw inputs;
- verified-erased dependency остаётся явно unavailable; зависящий use не
  становится допустимым от одного разрешения удалить bytes;
- неожиданная потеря объекта, который backup обязан был сохранить, остаётся
  дефектом и входит в recovery coverage/RPO report.

Control, rights, material Claim histories, surviving continuity witness и
enablement fence из R22 сохраняются. Где native profile допускает scoped cold
retrieval, нужный объект проверяется до его использования. Это не утверждение
целостности всего архива; отдельно выбранные full preservation obligations
остаются обязательными. Неизвестный historical head не переиздаётся молча.
Действительно независимая fresh candidate работа может идти по своим grounds,
не уничтожая старую duty или неизвестный исторический interval.

Финальное собственное review нашло companion в OPS-04: implementation уже
поддерживал independent rolling, но rollback предписывал откатывать worker/API
вместе. Теперь coordinated rollback обязателен лишь там, где его требует
actual supported matrix; допустимые mixed-version направления сохраняются.

Compatibility выводится по направлениям reader/writer/schema/rule: retained N-3
read может оставаться обязательным при writers N/N-1. Хранение артефакта само
по себе не обещает поддержку всех старых writers или formats навсегда.

**Почему это лучше альтернатив.** Полный rebuild всего архива нарушает
query-only/retention и масштабирование; игнорирование всех missing refs скрывает
реальную потерю и ломает custody. Scoped obligations сохраняют честную полезную
работу и не ослабляют требуемый verification denominator.

**Различающие проверки.** Mixed archive positive; forbidden reconstruction и
unexpected retained-object loss negatives; corrupted cold object обнаруживается
до его protected use; independent scope не ждёт чужой erased dependency.
Совместимость проверяется по actual supported pairs, не одной N-1 строке.
Задачи: [OPS-04](../solutions/10-operations.md#OPS-04),
[OPS-05](../solutions/10-operations.md#OPS-05),
[deployment companion](../operations/01-deployment.md#r23-recovery-scope-and-compatibility-clarification).

## R23-04. Review-required не закрывает обещание обслуживания

**Дефект.** R22 разрешал «service opportunity or bounded terminal/review outcome».
Без уточнения это допускает вечный цикл review→retry→review, который формально
проходит progress probe. Повторный status не делает услугу оказанной и не
устраняет уже пропущенный custody interval.

**Решение.** Различать selected service/aging promise, явно ограниченный
best-effort outcome и unresolved review. Native duty owner сохраняет исходный
age, actual review owner и следующий trigger/escalation либо допустимый
cutoff/transfer. Новый retry ID не сбрасывает clock. Review может обосновать
новый bounded continuation plan, но не переписывает lapse и не считается
execution. LIF-02 меняет affected claim/coverage при пропущенной обязанности,
не ожидая тяжёлого compute или review. Автоматический native review разрешён;
новый обязательный human-approval stage не вводится.

**Почему это лучше альтернатив.** Обещать любой job успешное исполнение при
любой нагрузке невозможно; считать каждый отказ полезным service уничтожает
смысл commissioned guarantee. Class-specific promise плюс честный unresolved
outcome сохраняет оба режима без универсального SLA или scheduler.

**Различающие проверки.** Реальный service-class progress под заявленной
нагрузкой; отдельный best-effort refusal; endless review loop negative;
removal overdue→claim reaction при сохранённых metrics. Tasks:
[LIF-04](../solutions/02-custody.md#LIF-04),
[LIF-06](../solutions/03-lineage.md#LIF-06),
[OPS-08](../solutions/10-operations.md#OPS-08); R16 C7/Q13 companions обновлены.

## Повторная собственная атака и сохранённые границы

1. **Stochastic как лазейка.** Нельзя постфактум выбрать tolerance/criterion,
   объявить duplicate независимым или заменить exact artifact новым draw.
   Qualified deterministic методы сохраняют строгий replay там, где он обещан.
2. **Expected-head как ложная freshness.** Fencing ограничивает наш transition,
   не гарантирует порядок replicas внешнего сайта. Поэтому ambiguous reply не
   очищает known fence, а reconciliation остаётся observation/as-of scoped.
3. **Lazy restore как пропуск проверки.** Control/history fence до enablement;
   required object verification до protected use; actual RPO/coverage отдельно.
   Запрещено объявлять corpus integrity по одному manifest или sampled hash.
4. **Erasure как переиздание.** Новый independently grounded use не восстанавливает
   старую current подпись, не возвращает отозванные права и не прекращает duty.
5. **Review как замаскированный success.** Даже named owner не proof of service.
   Score должен считать реальное свойство selected class; unresolved duty имеет
   следующий accountable trigger и немедленную честную coverage projection.

Не изменены R22 controlled-proxy target proof, per-predicate legal qualification,
allocation lifetime accounting, actual retention owner и раздельные structural/
effect write rules. Предложенные контрпримеры не требуют их отменять. Параллельность
остаётся stage/scoped: эти уточнения не требуют завершить whole LIF до CAP и не
вводят global observation/cache/recovery lock. D01–D08 и принятые SDD не переоткрыты.

## Проверка и handoff

[Документарный receipt](r23-validation.json) пересчитывает complete task/solution
set, direct DAG, extension mirrors, question routes, local Markdown targets,
изменённые cards и unchanged stage requirements. Пересчитаны 121 task/solution,
368 unchanged direct edges, 84 question IDs / 388 task routes; исправлены 10 task
rows с human/machine mirrors. Это проверка документации,
не product verification. Старые receipts сохраняют исходные pins и scope.

При реализации все новые signals проходят настоящий producer→permitted artifact
→native bridge→fresh consumer/surface. Из текста нельзя заключить, что capability
уже существует: фактические `producer_missing`, `bridge_missing`,
`verification_missing` или `semantic_test_missing` устанавливаются после E02
rebind по реальному коду. Scope текущей работы — исправленный план.

Pattern pass: P01/P02/P04/P05/P07/P08/P09/P10/P13/P14/P27/P29/P31/P32/P35/P37/P38/P40.
R23-01/02/03/04 — уточнения прежних классов на relation/consumer границе, не четыре
новых универсальных подсистемы. Собственный финальный review не назван независимым.
