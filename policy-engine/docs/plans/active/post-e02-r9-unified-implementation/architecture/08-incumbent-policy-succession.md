# R17: новый дизайн при уже исполняющейся политике

Проект после E02. [Custody](07-completed-design-custody.md), [access](09-design-isolation-and-access.md), [работы](../solutions/17-design-custody-and-succession.md). PolicyOS проектирует и хранит собственное обоснование; принятие закона, прекращение программы, уведомления адресатам, платежи и физическое исполнение принадлежат институтам. Их typed evidence интегрируется, не заменяется внутренним статусом.

## 1. Не один `current_design`

Нужны отдельные native identities и отношения: PolicyMatter/case, design edition, calculation/evidence revision, public release, external institutional instrument/act, actual implementation/exposure episode. Reuse existing case/PDC/claim/artifact/event owners; accepted-source rebind разрешает exact schemas. Это logical roles, не обязательный новый класс на каждое слово.

Отдельно отвечать на вопросы «последняя разработанная альтернатива», «допустимая опубликованная рекомендация», «принята институтом», «юридически действует в выбранной области», «есть evidence фактического исполнения», «какой вариант учитывается в анализе эффектов». Их нельзя свести к линейной status лестнице: возможны частичное вступление, contested acts, phased rollout, suspension, отмена с residual obligations и одновременные режимы.

Refines/corrects/supersedes **наше утверждение**, proposes replacement **policy candidate**, legally changes **instrument**, observed changes **implementation** — разные relationship meanings. Перечень открыт; new relation требует typed contract и actual verifier/consumer, не произвольный edge label. Policy-level evidence не даёт права принимать individual administrative decisions.

## 2. Что рассчитывать при перепроектировании

DES-11/03 принимают actual or explicitly assumed incumbent state на decision cutoff: история interventions/exposure, уже взятые commitments, installed capacity, текущие recipients/cohorts, lagged effects, switching/exit costs и constraints. Unknown actual history задаётся как unknown/scenario; не заменять её planned deployment из старого документа.

Сравнивать допустимые alternatives: continue incumbent, изменять parameters, phased substitution, temporary overlap, bounded pilot, stop/withdraw where authority permits, acquire information/delay. Это compositional alternatives, не domain templates или всегда обязательный menu. Новый дизайн оценивается **с переходом**, а не только по долгосрочному equilibrium в пустом мире. Предыдущие sunk resources учитываются как facts/remaining obligations и сравнение incremental future consequences; уже потраченное нельзя второй раз начислить как расход нового выбора. Distributional consequences и noncommuting paths сохраняются.

Simulated rollback — counterfactual, не отмена фактического вмешательства. Реальное возвратное решение создаёт новую transition episode; не восстанавливает старый snapshot мира, полномочия или privacy budget. Частичный rollout в одном регионе не отключает прежнюю policy в остальных; модель должна показывать overlap/coverage gaps и carryover/spillover effects.

DES-12 предлагает information acquisition, если evidence недостаточно для выбора перехода. Количественная оптимальность не подменяет mandate/value authority; conditional alternatives остаются полезны без выдуманных weights/permissions.

## 3. External replacement intake

1. CAP-05 получает source-qualified legal/institutional act; operational/exposure input идёт через CAP-04 source-specific adapter, чей canonical source/custodian и path назначаются при accepted-source rebind; CAP-04 persistence и LIF-01/02 verification/currentness сохраняют источник и exact record. Discovery/LLM extract только candidate.
2. Native verifier связывает actor/issuer competence для конкретного утверждения, predecessor/successor versions, affected instrument/provision/target population/territory, time/effect scope, exclusions/transitional rules, supporting source content и correction/revocation chain. Required facets выводятся из actual owner contract, не закрытого списка этой записки.
3. Separate evidence bands: institution **сообщила** событие; документ **аутентичен и применим**; independently reconciled **юридическое действие**; наблюдается **операционное исполнение**. Даже подлинная подпись не устанавливает весь последний band. Присваивать только проверенное утверждение, с provenance и unknowns.
4. Событие и его interpretation persist append-only через existing evidence/claim lifecycle owner. Replay/dedupe использует source identity/incarnation; correction не перезаписывает initial received event. Human review — typed input со своим mandate, не blanket override.
5. LIF-02 вычисляет affected claim/assessment reactions; DES-04 может создать bounded reevaluation duty; UI-04/19 и DES-06 получают same owner projection. Arrival event не автоматически разрешает защищённую publication/claim advance.

Не делать lookup «последний документ заменяет всё предыдущее». Полезные queries имеют explicit scope + effective time + known-at cut + authority/evidence purpose. Два несовместимых act references — contested relation; не last-writer-wins. Retroactive effective date не означает, что PolicyOS или actor знал акт до получения/verification. Supersession graph для одной fixed relation/scope не допускает необъяснимых self/cyclic links; циклическая политическая история A→B→new A-version остаётся нормальной последовательностью новых editions/events, а не переписыванием A.

## 4. Что хранить в истории

Immutable edition и originally issued bytes; actual revision/assessment/interpretation events с correction links; scoped relations между predecessors/successors; институциональные evidence refs; actor/purpose/authority basis; valid/effective/observed/received/verified/issued times; причина изменения; оставшиеся obligations, unresolved disputes и watch duty. Metadata само может быть sensitive и проходит access control.

«Альтернатива предложена» и «замена произошла» показываются в разных смысловых полосах. Пользователь должен видеть: что было известно при исходном выборе; что изменилось; что рекомендовано; кто действительно решил; для кого/когда решение применимо; что наблюдается в исполнении; что осталось от старого режима. Все summaries привязаны к exact owner projection; сравнение diff текста не доказывает semantic replacement.

Signed public release остаётся fixed. Текущий статус дополняется отдельной owner-qualified projection/correction notice. Старые публичные copies невозможно гарантированно отозвать: first-party surfaces обновляются, managed subscriptions получают durable attempt/receipt, external dissemination scope явно ограничен. Это коррекция собственных records, не государственный notification service.

## 5. Оценка эффекта после замены

GYD-08/09/10/12 и CNT-06 сохраняют exposure history и target/estimand versions. Published assignment, legal eligibility, offered service и actually received treatment различаются; all-person record не обязателен, если source/метод допускает корректное агрегированное evidence. Direct access к private individuals не возникает из требования более точной оценки.

Anticipation, staggered adoption, nonadherence, treatment switching, treatment-confounder feedback, delayed labels, spillovers и residual effects могут нарушить простой before/after или unchanged-cohort estimator. Метод выбирается по достаточным assumptions/identification, не по удобству available API. Новая policy может менять сам процесс измерения; apparent KPI improvement не обязательно эффект. Нет автоматического pooling эффектов разных editions или ad hoc averaging; retrospective re-estimation сохраняет historical as-known-then comparison и возможность honest bounds/limitation.

Announcement exposure требует отдельного selected-method рассмотрения: достоверное объявление V2 в t1 может изменить поведение до legal t2 и receipt t3. При известном таком эффекте receipt-only baseline не допустим. Неизвестная awareness/scope ведёт к сценариям, границам или limitation, а не default «нет anticipation». Это уточнение существующей strategic-response модели, не требование всегда собирать индивидуальные awareness records.

## 6. Конкретный сквозной falsifier

V1 действует в регионах R и S. V2 рассчитан и опубликован; это не меняет implementation state. Verified act назначает V2 для новых entrants R с даты t2, оставляя старые cohorts V1. Actual feed сообщает старт в R на t3>t2; в S нет смены. Later correction уточняет t3. Fresh public/currentness reader и effect estimator должны показать соответствующие bands/cuts/cohorts, не одну «V2 active» строку. New candidate V3 сравнивается с этой смешанной историей и residual V1 obligations. Неизвестный feed для S не становится zero exposure. Удалить actual scoped act/exposure consumption при сохранённых labels — positive должен fail.

Pattern pass: P02/P04/P05/P07/P08/P10/P14/P17/P19/P20/P21/P23/P24/P26/P31/P32/P37/P38. Не расширяет SDD custody boundary; никаких институциональных acts PolicyOS не выполняет. Runtime UNRUN.
