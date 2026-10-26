# Самостоятельный review: что могло сломать решение

Исследование G от 26 октября 2026 — только Git/текст/stdlib hashes и первичные web sources. Субагенты не использовались. Product code, tests, numerical runs, heavy scans, installs и production data не запускались/не читались. Документы — выбранный архитектурный ответ; implementation ещё должен доказать его.

## Source-grounded выводы

- `acquisition_world_growth.admitted_membership_delta` считает selected epoch и требует positive active membership; `NoGrowthReceipt` отдельно требует `before == after` и literal 0. Значит новая positive occurrence не помещается в no-growth даже при одинаковом value.
- `AcquisitionOwnerExecutionResult` сообщает admission outcome. В `acquisition_action_service` и execute, и recovery positive ветви сейчас идут в reentry; решение переносит развилку выше admission, не заставляя source connector знать N5.
- `_candidate_world_context_handoff` материализует snapshot/world/context, а `admit_context_for_acquired_world` переиздаёт model declaration/NCM views. Поэтому comparison после этого уже нарушил бы обещание «не создавать новый WMR/candidate context». Нужна общая preparation до persist, без второго вычислителя.
- `data_state_substrate` payload содержит acquisition history, receipt/passport/epoch и transaction time; WMR содержит materialization refs/time. Их полный digest нельзя использовать как semantic equality. Но и автоматическое удаление «метаданных» опасно: actual as-of/time/profile inputs могут менять запрос.
- `GenerationCycleController.reenter_after_active_acquisition_overlay` вызывает `_run_cycle` и post-loop composition. Это шире N5. Retain обязан проверить всё, что **действительно пропускает**, сохраняя обязательные дешёвые source/bookkeeping/eligibility реакции.
- Route fold, `resolve_action_generation`, authority sink и GET имеют двухвариантные checks/else branches и schema pins. Новый terminal требует обновить всю consumer chain; один enum в Core DTO недостаточен.

Верифицированы **14 committed pins**, **5 WIP postimages** восстановлены исключительно в памяти из exact patch и совпали с пакетными hashes. Fixture manifest/proposal hashes совпали; fixture остаётся first-source-only/UNRUN согласно пакету. Это проверка custody переданных текстов, не независимый runtime replay или принятие source. Остальные рассмотренные source files отдельно pinned в [inputs.json](inputs.json).

## Атаки и внесённые уточнения

| Контрпример | Ответ выбранного контракта |
| --- | --- |
| Повторное получение того же числа — новое независимое наблюдение/другой год | Effective multiplicity/time/evidence relation учитывается; value equality недостаточна |
| Source/epoch `no_change` совпал, но сменился rule/model/horizon | Relation строится из actual prepared inputs downstream owners |
| Для equality удалили все `*_ref`, timestamps и labels | Только explicit owner-classified occurrence roles; actual time/profile/measurement влияния остаются |
| Старый full WMR hash отличается только от materialization clock | Не меняем WMR content hashing; вводим scoped semantic relation между real inputs |
| Comparison PASS, затем другой route продвинул evaluation | Conditional frontier/lease binding; stale decision не терминализируется |
| Retained branch `continue` пропускает поддельный history join | Fold проверяет growth/decision и равенство retained tuple текущему accumulator |
| Два источника → два независимых подтверждения | Occurrence count не является evidence independence/sample size |
| Старый N5 теперь рекламируется как расчёт по новому source | Старые manifests неизменны; отдельные acquisition и retained-evaluation refs/времена |
| Source принят, процесс упал до terminal | Durable admission восстанавливается без refetch; CAS-only orphan не public success |
| «Same basis» подавил authorized robustness/new hypothesis | Evaluation intent, seed/replications/model/candidate semantics учитываются; повторение допустимо по своему owner path |
| Basis исходного вычисления не сохранён | Только content-bound reconstruction existing owner; иначе неизвестность, не synthetic baseline |
| Equality неизвестна, но author поставил boolean true | Typed equivalent variant требует resolved basis/eligibility; caller declaration не принимается |
| SLO-like запрет: вся неизвестная law/currentness блокирует даже limited candidate | Limited input разрешён существующим scope; неизвестность predicate retention — отдельный блокер. Authority не повышается |
| Spend/action count изменились, поэтому весь N5 обязан повториться | Дешёвые обязательные реакции выполняются отдельно; несемантическое bookkeeping не превращается в numerical intent |
| Новый reader DTO понимает enum, старый sink/UI — нет | Reader-first полный footprint, emission gate и rollback-reader preservation |
| UUID-only repeat всё равно повторяет evaluation из-за conservative fallback | Same-action recovery идемпотентен; unsupported reuse остаётся bounded, а не full B09 PASS. Нет бесконечного background retry по одному UUID |
| Free-grow потребовал поддержать новый profile/schema | Existing owner preparation extension; unsupported required facet закрывает reuse, а не урезает новый метод до старого set_to |
| Equality сравнила receipt целиком, включая новый source ref/derivation time | Semantic projection отделена от custody envelope; обе разные source identities проверяются, но не принуждаются к совпадению |
| Relation equivalent, но revocation/permission запрещает дальнейший retention | Equality не равна eligibility; terminal требует оба predicates на согласованном frontier |
| Decision создан, crash случился до записи его индекса | Recover от durable selected admission; orphan не success, повтор pure comparison допустим, winning terminal один |
| No-growth action ошибочно объявили всегда бесплатной | Retry одной action не списывается дважды; distinct attempt следует existing cost rules, без фиктивного N5 charge |

## Почему это современное, но небольшое решение

[W3C PROV-DM](https://www.w3.org/TR/prov-dm/) различает entities, activities и отдельные occurrences использования одной entity. Это полезная модель для двух получений тех же данных и одной сохранённой оценки. PROV сам по себе не устанавливает semantic equality или admissibility: PolicyOS relation остаётся у наших owners; отдельную PROV database вводить не требуется.

[Dagster asset versioning](https://docs.dagster.io/guides/build/assets/asset-versioning-and-caching) разделяет code/data versions и отдельно предупреждает, что randomness и косметический source change усложняют memoization. Здесь применяется тот же принцип раздельных identities, но owner-supplied data version или одинаковый seed не принимаются за полный proof; решение сохраняет actual evaluation, не предсказывает bytes нового stochastic run. Dagster внедрять не предлагается.

[RFC 9110, conditional requests](https://www.rfc-editor.org/rfc/rfc9110.html#name-if-match) иллюстрирует lost-update prevention через сравнение с текущим выбранным состоянием. Для PolicyOS это **аналогия обоснования** existing CAS/lease frontier, не требование добавить HTTP If-Match к данному POST. Проверка нескольких dependent selectors должна быть защищена нашим owner commit protocol, а не одной случайной timestamp.

## Итог собственного review

Выбор option 1 сохраняется. Уточнения к исходному предложению существенны: native admission contract не расширяется там, где он уже честно выражает positive delta; relation owner стоит перед side effects материализации; полнота ограничена всей реально пропускаемой continuation; unknown не даёт reuse; новые refs не переписывают прежнюю lineage; rollback обязан сохранить reader.

Новые capability gaps до исполнения: `producer_missing` для owner-issued comparison, `artifact_missing` для его durable receipt, `bridge_missing` для нового terminal/history join, `semantic_test_missing` для второго реального source event. Это состояние **новой** source-retained chain, не отрицание existing admission/reentry capabilities. Нет нового global freeze, source acceptance или закрытых findings.

Pattern pass: P01/P02/P03 — обязательная source→CAS→decision→history→fresh GET chain; P04/P05 — независимые status/authority planes; P07/P08 — версии, original/derivation/admission time; P10/P14 — смысл equality и независимость evidence; P27/P31 — один existing owner mechanism; P29/P32/P33 — real producer + matched removal; P35/P36 — полный packet denominator и исходный B09 criterion; P37/P38 — owner-recomputed predicates вместо hash/enum proxy; P39/P40 — companions не выдавлены из scope, класс ремонта определён; P41 — не заявляется inherited red без replay.
