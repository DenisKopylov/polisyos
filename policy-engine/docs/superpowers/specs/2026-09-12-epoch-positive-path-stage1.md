---
title: Epoch positive path — Stage 1 adjudication
status: research complete; implementation admission pending mechanism design
owner: codex/epoch-positive-path
created: 2026-09-12
source_base: 034f30c64a79eb2020c04c6f0b0f07c90a74a1ee
authoritative_for: [lane_research_findings, row_scope_adjudication]
may_not_use_for: [institutional_appointment, positive_production_claim, register_status_mutation]
---

# Epoch positive path: что отсутствует на базе

Исследование выполнено на `codex/epoch-positive-path` от точного `source_base`.
Все пути ниже относительно `policy-engine/`, строки относятся к базе. Инструкция
этой lane разрешает Stage 2; этот документ не назначает институты и не меняет
`DEBT-REGISTER.md` или `LEDGER.md`.

## EP-F01 — проверяемая гипотеза и граница измерения

Контрпример, объявленный **до поиска**: положительный переход может называться
`EpochValidityTransitionProducer`, `PersistedEpochValidityTransition`,
`EpochTransitionVerificationReceipt`, проходить через `produce_and_persist` и
`admit_epoch_validity_batch`, не содержать `positive_transition` вообще.
Поэтому нулевой поиск по предположенному имени не используется.
Запрос для обнаружения контрпримера:

```text
rg -n 'EpochValidityTransition|EpochTransitionVerifier|produce_and_persist|admit_epoch_validity_batch|resolve_complete_epoch_dependencies|resolve_complete_owner_adjudications' src
rg -ni 'epochvaliditytransition|epochtransitionverifier|produce_and_persist|admit_epoch_validity_batch|resolve_complete_epoch_dependencies|resolve_complete_owner_adjudications' src
```

Поиск даёт навигацию, не доказательство отсутствия. Для определений и вызовов
используется AST полного Python-набора `src/**/*.py`, отдельно сопоставленного
с файловым обходом; динамический dispatch и внешний deployment не выводятся
из статического нуля. На базе файловый обход и независимый Git-tree дают один набор: **2,654 .py
файла под `policy-engine/src/**`**. AST не находит constructor-вызовов
`EpochValidityTransitionProducer`, `PersistedEpochValidityTransition`,
`EpochTransitionVerificationReceipt` и вызовов `.produce_and_persist` в этом
наборе. Прочитаны все члены, parse/read ошибок и content drift не обнаружено.
Это ограниченный статический результат; заявленные dynamic/external boundaries
остаются unresolved. Исторические census-числа Task B не перенесены на базу.
Полные deciding outputs, параметры и SHA-256 находятся в журнале lane.

## EP-F02 — воспроизведённые исходные anchors

- `src/polisyos/core/contracts/runtime.py:816-846`: строгий
  `InstitutionalAuthorityAbsenceView`, обе роли в `Literal` на :822,
  коды на :827-828, проверка соответствия на :838-844.
- `src/polisyos/runtime/quality/epoch_validity_cascade.py:850-887`:
  `EpochTransitionSigningNonReceipt`, `EpochTransitionSigningAuthority`,
  `NoEpochTransitionSigningAuthority`; точный отказ на :885.
- Исторический номер :1128-1154 теперь лежит у constructor/вызова producer.
  Сам `EpochTransitionHistoryRepository` находится на :890-901;
  `FileSemanticEpochTransitionHistoryAdapter` на :904 уже реализует
  `resolve_transition_manifests`. Наличие интерфейса не приходится изобретать.
- На :2467-2472 настоящий pre-N9 gate возвращает отказ transition signer.
- `epoch_staleness_projection.py:281` действительно передаёт
  `role="epoch_predicate_policy_signer"`. Это consumer refusal, не signer.

## EP-F03 — R1: разбор всего commissioned row set

Полный знаменатель этой таблицы — десять ID из commissioning, сверенные с
точными строками Markdown-register, а не с совпадениями в его revision-прологе.
Классификация — результат чтения первичных артефактов; статус register сохранён.

| ID | Что реально решает строку | Capability / граница |
| --- | --- | --- |
| `ds18-positive-transition-production-unorchestrated` | Отсутствующий engineering chain: полный источник зависимостей и owner adjudications, producer identity readback, завершающая выдача, production trigger и reconciliation wiring. Подписи отдельно. | `implemented_but_not_orchestrated` недостаточно описывает финальный безусловный отказ producer; также `producer_missing` для полных providers, `bridge_missing` для orchestration. EP-F06. |
| `ds18-positive-transition-verification-producer-missing` | Отсутствующий положительный verifier и его production composition. Старое противоречие знаменателей снято GY-CR4; verifier provenance остаётся отдельным пустым слотом. | `producer_missing` + `bridge_missing`, не отсутствующий scope и не нерешённый выбор хеша. EP-F05. |
| `GY-DEF23` | Институциональное signing/producer-identity условие; engineering remainder уже отнесён к DS18 production. | Не закрывается адаптером истории или тестовым verifier. EP-F06/07. |
| `gy-n12-epoch-predicate-policy-authority-unappointed` | Назначение purpose/selection-scoped predicate-policy authority и независимо admitted точные артефакты. | Appointment `absent/unallocated`; действующий код делает явный unallocated отказ. EP-F04. |
| `gy-n12-epoch-transition-signing-authority-unappointed` | Назначение transition signer **и** отдельно удерживаемой producer identity; wiring conjunct вынесен 2026-08-31. | Appointment; подпись не доказывает собственную producer identity. EP-F04/07. |
| `ds18-epoch-predicate-policy-signer-unappointed` | Predicate-policy appointment; DS18 уже показывает отказ. | Тот же role mechanism, но отображение не выдаёт admission. EP-F04. |
| `ds18-epoch-transition-signer-unappointed` | Transition signing appointment; DS18 показывает отказ signer. | Общая signer role не доказывает равенство всей GY obligation. EP-F04. |
| `ds18-epoch-history-independent-holder-unappointed` | Независимый holder с полным принятым history и readback evidence. | Invocation/persistence/audit уже существуют; whole-history authenticity не установлена. EP-F07. |
| `ds15-semantic-epoch-qualification-authority` | Qualification/activation acquisition epoch через predicate-policy admission. | Другой lifecycle, durable negative bridge построен; positive composition не выводится из него. EP-F08; остановить работу этой строки в transition lane. |
| `ds15-fresh-positive-production-route` | Реальный admitted observation delta плюс same-case re-entry, не подпись перехода. | Текущий production port принудительно no-growth; `bridge_missing` остаётся независимо от appointment. EP-F08; отдельная acquisition lane. |

Первичные артефакты, прочитанные за строками:

- Register :420-424 → DS18 plan `DS18-CC10`, §14/§15 и §Capability-list
  re-derivation (:1383-1404); DS18 closeout journal; Task Q journal
  `2026-09-01-debt-q-remeasure-and-typing.md`, точные row findings :948-976;
  `UNINVOKED-DS18-02/03/04` в spec `2026-09-10-uninvoked-ds18.md`.
- Register :423-424/:541 → Task B journal
  `2026-08-30-debt-b-epoch-decision-validity.md` (:958 далее), его implementation
  plan Task 9; GY-CR4 journal `2026-09-02-gy-cr4-denominator-seam.md`,
  точные dispositions этих ID :597-607 и закрытый denominator row :445.
- Register :428/:550 → DS15 plan `DS15-EPOCH-QUALIFICATION-NOT-ESTABLISHED`
  (:2005), fresh-positive boundary (:2053), `U15-F03/U15-F05` в
  `2026-09-10-uninvoked-ds15.md`; реальные acquisition owners (EP-F08).
- Qualification/custody/transition semantics → GY-N12 closure basis
  `CB-B09`, `CB-C04`, `CB-D01`–`CB-D06D`, `CB-H08`, `CB-J06`.

## EP-F04 — R2: две заявленные редукции

Правило: редукция **целых obligations** допустима, если совпадают authority
slot с purpose/selection scope, operative refusal mechanism и недостающее
условие. Общий текст или одинаковый код отказа сам по себе этого не доказывает.

**Predicate-policy pair: общая роль и центральный refusal mechanism подтверждены;
полная взаимозаменяемость строк/appointments не подтверждена.** DS18 через
`services/temporal.py:444` и GY gate через `epoch_validity_cascade.py:2430`
вызывают `SemanticEpochService.qualify_chronology_query`; тот достигает
`QualificationConsumer.qualify`, `chronology_qualification.py:224-236`.
Unallocated ветвь возвращает `PolicyAdmissionMissingFailure` до чтения индекса.
DS18 проецирует этот результат; GY преобразует его в gate nonreceipt на :2460.
Это общий policy admission owner и код `policy_admission_missing`, различные
обёртки и query instances. Одно назначение закроет обе строки только если его
полный selection key действительно покрывает оба случая; generic название роли
не даёт blanket authority. Допустима консолидация описания слота, не автоматическое
закрытие одной строки другой.

**Transition pair: строгая редукция опровергнута.** DS18 получает фактический
`NoEpochTransitionSigningAuthority.sign_transition(b"")` из `temporal.py:453`;
GY pre-N9 на :2467 выдаёт тот же код без обращения к signing authority вообще.
Кроме того, GY row явно требует независимо удерживаемую producer identity,
которую signing bytes не могут назначить. Контрпример: назначить signer и оставить
producer identity отсутствующей — signer obligation может быть удовлетворена,
но producer на :1212-1220 всё ещё откажет. Общая часть — signer role; ни кодовый
путь, ни вся конъюнкция не тождественны. Пары нельзя арифметически вычесть как
дубликаты всего positive-path work.

## EP-F05 — знаменатели: решение уже принято

`epoch-dependency-denominator-defined-twice-incompatibly` закрыт по GY-CR4
в register :445. Runtime epoch basis и Scientist decision impact описывают разные
популяции. `EpochTransitionDenominatorReconciliationReceipt` сохраняет обе,
производится и читается `epoch_denominator_reconciliation.py`; неизменяемый
admission binding сохраняет точный handle для replay. Решение не требует
выравнивать хеши. GY-CR4 journal, disposition
`ds18-positive-transition-verification-producer-missing` :599 явно говорит
**unblocked, not closed** и запрещает выдавать seam-positive за DS18 production.

`DecisionValidityService.__init__` (:523) принимает reader, по умолчанию `None`;
legacy ветвь :691 продолжает требовать свой знаменатель. Реальный reader с
`verifier_provenance_ref=None` отказывает `epoch_denominator_reconciliation_unavailable`
на :294. Это оставшаяся composition и empty authority slot, не новая архитектурная
неопределённость.

## EP-F06 — R3: объект допуска и реально отсутствующая цепочка

Объект на границе Scientist — **`EpochTransitionVerificationReceipt`**
(`core/contracts/decision_validity.py:795`), произведённый verifier из точного
**`EpochValidityTransitionArtifact`**. Receipt замораживает ref/hash, query,
purpose, verifier provenance, полную dependency/target популяцию, owner
adjudication denominator и `independently_reconciled` provenance.

До verifier обязан существовать **`PersistedEpochValidityTransition`**
(`epoch_validity_cascade.py:837`): точные signed bytes, signing profile,
независимая producer identity и signer provenance. Producer
`EpochValidityTransitionProducer.produce_and_persist` (:1139) уже резолвит
историю, providers и строит artifact, но:

1. :1148-1153 немедленно возвращает реальный no-signer nonreceipt;
2. даже после exact signed readback :1194-1204 финал :1212-1220 **безусловно
   отказывает** `epoch_transition_exact_evidence_unavailable`; положительный
   result type пока не производится этой функцией;
3. `NoEpochTransitionVerifier.verify` (`decision_validity.py:499-512`) всегда
   поднимает `verifier_not_configured`;
4. pre-N9 authority gate :2467-2472 также безусловно отказывает после qualification.

Consumer `DecisionValidityService.admit_epoch_validity_batch` (:664) проверяет
verifier receipt, замораживает complete target denominator перед записью,
применяет lifecycle effects и сохраняет completion/batch artifacts (:890-932).
GY gate/N9 evidence resolver должны затем потреблять completed owner evidence.
`EpochValidityPendingBatch` не означает completed; successful signature не
означает допустимую текущую policy recommendation.

Имеющийся non-test intake caller — `ControlPlaneService.admit_epoch_validity_batch`
(`runtime/http/services/control/run_lifecycle.py:3594`), вызываемый существующим HTTP control
`epoch_validity_batch`. Терминус — `runtime/http/routes/control.py:557`, зарегистрированный run-control route;
existing pre-N9 gate — место production orchestration при generation.
Импорт, test helper или DS18 вызов signer с пустыми байтами не заменяет producer.

Минимальный правильный pattern: canonical owner evidence → complete dependency
и disposition readers → transition producer → exact signed persistence + независимая
producer identity → verifier + non-coercive denominator reconciliation → strict
batch intake → pre-N9/N9/lifecycle consumers → audit/API/projection. Пустая
appointment конфигурация отказывает в authority band, но не является причиной
оставить algorithm без положительной ветви.

## EP-F07 — R4: слоты назначений и config-vs-rewrite

| Slot | Что уже есть | Чего нельзя назвать готовой конфигурацией |
| --- | --- | --- |
| Predicate-policy signer | Полный policy selection/admission/provenance contract, qualification consumer и scoped refusal | Production composition выбирает `from_unallocated_policy_authority`; `_ChronologyPersistenceRegistry` не имеет production appointment hook. Позднее назначение пока потребует owner-controlled composition change. |
| Transition signer + independent producer identity | `EpochTransitionSigningAuthority` и строгий no-signer result; signed evidence repository | Producer identity отсутствует как consumable provider у producer; финальный отказ безусловен. Требуется механизм exact independent identity admission, а не замена signer provenance. Это engineering defect. |
| Independent history holder | `EpochAnchorAppointmentResolver`, `AnchorHolder`, registry, retain/readback verifier и `EpochAnchorCustodyService` | Production factory `chronology_custody.py:715-723` no-arg, жёстко задаёт отсутствующие resolver/registry/repository. Generic проверку переписывать не надо, но owner-controlled deployment configuration ещё требуется. |

`epoch_custody_audit.audit_epoch_custody` (:106-116) действительно вызывает
provider, сохраняет и перечитывает результат. CLI `python -m
polisyos.runtime.quality.epoch_custody_audit --request PATH --cas-root PATH`
является runnable terminus. Его `authority_scope=custody_provider_invocation_only`
и `request_reference_verification=not_established` (:46-49) не устанавливают
whole-history authenticity. `FileSemanticEpochTransitionHistoryAdapter` доказывает
точный local history/predecessor read, не независимое custody.

Правило уже решено: identity §9(5)/(6), `S0-K03`/`S0-K06`; назначение не
блокирует build и pure verification не является signing. Их `may_not_use_for`
запрещают выводить capability/implementation authorization из самой философии.
Источник разрешения этой lane — commissioning пользователя; источник проверки
семантики — читаемые owners и GY-N12 finding IDs.

## EP-F08 — R5: DS15 отделён по deciding variable

`U15-F03` различает served chronology query и persisted acquisition producer;
`U15-F05` прямо не претендует на signed validity-transition chain.
`admit_acquisition_with_semantic_epoch` (`acquisition_executor.py:1703-1846`)
делает qualification, затем history append и activation; policy failure выходит
до activation. CLI `acquisition_epoch_admission.py:97-98` намеренно не принимает
`ActivatedSemanticEpochAdmissionReceipt`: это durable-negative bridge.

Контрпример утверждению fresh row «institutional half alone»:
`WorldBankWDIAcquisitionExecutionPort.execute` в
`runtime/http/services/acquisition_surface_execution.py:380-426` всегда возвращает
`quarantined_no_growth`, `admitted_observation_delta=0`; `reenter`/`resume_reentry`
на :428-446 отказывают. Назначение predicate-policy signer при неизменном этом
коде не создаёт delta или same-case re-entry. Поэтому это самостоятельная
acquisition bridge/production-instance задача, а не transition signer.

Назначенный маршрут наблюдений: обе существующие DS15 row IDs с этим finding;
их source здесь не меняется, новые реестровые строки не создаются.

## Pattern pass и граница следующего этапа

- `P01/P02/P12`: существующий producer с безусловным финальным отказом не считать
  готовым оркестрируемым positive capability.
- `P05/P15/P32/P37`: запретить self-appointment, signer-as-producer identity и
  consumer-declared complete denominators. Readback должен проверять содержание.
- `P07/P08`: сохранить purpose/query, old/current epoch и оба owner denominators.
- `P29/P33/P38`: removal probe отключает поведение при сохранённых DTO/markers;
  отказ подставного verifier и запись реального результата должны исчезнуть в тесте.
- `P35/P36`: не наследовать нули по вымышленным именам и stale row blockers;
  cite finding IDs и полный измеренный набор.
- `P40`: второй escape того же класса требует расширить механизм или назвать
  ограниченный остаток с falsifier; косметику не превращать в новый раунд.

Ни одно прочитанное основание не делает engineering work зависимым от выбора
института. Stage 1 выявил конкретные build gaps; **само отсутствие назначения не
является основанием применить stop rule**. Следующий design pass должен выбрать
reuse существующих signed-evidence и canonical-owner APIs без выдумывания
источника authority. Если окажется, что для complete positive chain необходимо
новое неразрешённое семантическое решение, оно должно быть названо с контрпримером,
а не обозначено словом appointment.

Дополнительный surface witness: `services/temporal.py:444-461` отвергает
положительную qualification/transition как `*_reader_not_established`.
Назначение signer само не подключит положительный DS18 reader; это `bridge_missing`
в существующей production row, не новая institutional obligation.
