---
title: Epoch positive path — Stage 1 adjudication
status: complete-pending-an-architect-decision on EP-D01
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

## EP-D01 — решение, на котором применяется stop rule

Уточняющий reuse pass после фиксации EP-F01–08 нашёл узкое нерешённое **значение
producer identity**, а не необходимость назвать институт. Ранний вывод «достаточно
engineering» был шире имеющихся оснований: он принимал требование поля за
определение admission evidence (`P32/P36`).

**Вопрос архитектору:** что именно утверждает `producer_identity_ref` и какое
независимо admitted свидетельство является достаточным для этого утверждения?

| Интерпретация | Что должен доказывать механизм | Различающий случай |
| --- | --- | --- |
| Происхождение от канонического producer | Owner-held emission/origin record связывает каноническое исполнение с точным transition, purpose, query и admitted signing profile | Канонический producer действительно выпустил transition; отдельного grant на minting нет. При доказанном происхождении этот предикат выполнен. |
| Отдельное право producer на выпуск | Помимо origin/signature, независимо admitted role/grant разрешает этому producer выпускать epoch transitions в данной области и времени | Те же байты, подпись, происхождение и scope; grant отсутствует/отозван. Предикат не выполнен. |

Ни один вариант не выбирается этой lane. Назначение конкретного института
остаётся пустым при обоих; конфигурационный slot и проверяющий алгоритм будут
разными из-за **разного утверждения**, а не из-за имени подписанта.

Основания:

- `C5-PREREQ-DV-EPOCH-ADMISSION`, design :378-385, требует producer identity,
  signature и verifier provenance. Оно не выбирает одну из интерпретаций.
- GY-N12 implementation plan, Task 4.4 :8677-8695, называет canonical producer,
  container-owned signer и admitted signing/trust profile, запрещает caller-
  supplied identity. Оно не задаёт достаточное evidence отдельного minting role.
- `CB-D01`, `CB-H01/H02` требуют binding/provenance и реальные predicates;
  наличие требования не создаёт authority source.
- `SignedArtifactEvidenceRecord` (`core/contracts/chronology.py:2327-2339`)
  содержит signing profile и signer provenance, не producer-role relation.
- `SigningConfig` (`core/artifacts/signing.py:168-186`) устанавливает key trust и
  signer identity. `ProducerIdentity` в `runtime/quality/authority.py:494` и
  `attestation.py:101` описывает компонент, не admission этого полномочия.
- Predicate-policy owner provenance и acceptance/holder appointments имеют
  другие authority purposes. Их использование здесь без отдельного правила
  было бы authority-by-adjacency (`P36`).
- Точный подписанный readback в producer заканчивается отказом :1212-1220.
  Это не правило, из которого можно восстановить недостающий positive predicate:
  обе интерпретации согласуются с отказом при отсутствии вообще любого carrier.

**Минимальная способность после решения:** один owner-controlled immutable
источник выбранной связи producer→transition и его independent admission/readback,
проверяющий exact artifact/purpose/query/profile/временные ограничения до выдачи
`PersistedEpochValidityTransition` и до mutation Decision Validity. Имя/схема
источника не фиксируются до решения. Reuse: exact repository
`FileSystemSignedArtifactEvidenceRepository.read_exact`, canonical parsing и
`verify_signed_evidence`; они доказывают байты/подпись, а не выбранную связь.

**Falsifier будущего механизма:** сохранить точные transition bytes, валидную
подпись и admitted key/profile, полную history и оба denominator; заменить
только producer. Для origin-варианта заменить реальный emission proof
самодельной записью; для grant-варианта удалить/отозвать только producer grant.
До pending batch и lifecycle state должен быть отказ. Поля, типы и строки
`producer_identity_ref` остаются прежними. Положительное прохождение при этой
подмене означает, что код всё ещё проверяет signer, а не producer property.

Это bounded finding по прослеженной цепочке первичных документов и source,
не заявление об отсутствии решения во всех возможных документах/deployments.
Архитектор может разрешить его указанием уже действующего finding и конкретного
admission source; тогда нужен reuse, не новый контракт.

**Disposition:** `complete-pending-an-architect-decision on EP-D01: meaning and
admission evidence of epoch-transition producer identity`. Stage 2 source не
начат по budget/stop rule commissioning. Остальные конкретные engineering gaps
EP-F06/07 не объявлены завершёнными и не названы институционально заблокированными:
они уже направлены в существующие DS18 rows. Нельзя закрыть их фабрикой отказов
или объявить весь remainder одним appointment. После решения build включает
provider/orchestration/verifier/configuration/positive projection chain, перечисленный
в EP-F06, с неизменными исходными negatives.

## Stage 2 — commissioning decision and execution plan

Stage 1 above is preserved verbatim from `7478bc522`. The base of record remains
`034f30c64`; the following sections supersede its pending execution disposition,
not its historical findings. User continuation answers **EP-D01**: producer identity
asserts **canonical execution provenance**, not a separate right to issue. An
owner-held origin/emission record binds actual canonical execution to the exact
transition artifact, purpose, query context and independently admitted signing
profile. Independent admission and exact readback precede the positive wrapper.
Signer provenance never substitutes. Separate minting authority is withheld and
is not implemented.

### Stage 2 change contract

- Existing production caller/terminus: registered run-control POST
  `/decision-validity/epoch-batches` → `ControlPlaneService.admit_epoch_validity_batch`
  → canonical producer/verification bridge → strict Decision Validity intake →
  completed batch → existing claim lifecycle and N9 evidence consumers.
- Preserve every refusal and strict consumer predicate. Empty deployments keep
  typed-empty authority slots. A configured component cannot grant its own trust.
- Build all links independent of an unanswered decision. Stop only the precise
  consumer link whose semantics would have to change; continue other links.
- No source-side generated sync, institutional appointment, push, or edits to
  DEBT-REGISTER.md/LEDGER.md. The original Stage 1 findings are append-only.
- Internal runtime composition is the intended surface; request DTOs remain
  strict and carry only the existing transition/context handles.
- Stage 2 tests/gates use main's exact CPython 3.14.0 executable and the frozen
  dependency basis including `runtime` and `ml`. Gate receipts name the interpreter.

### Stage 2 dependency-ordered work

**Goal:** complete the buildable canonical transition chain while retaining
institutional absence and all refusal semantics.
**Architecture:** reuse immutable owner stores, signed exact evidence, existing
qualification/custody protocols, non-coercive reconciliation and strict batch
intake. One writer owns each source file. Root integrates the actual run-control
route; no parallel endpoint or helper-only completion claim is permitted.
**Tech stack:** typed Python/Pydantic, existing CAS/signing, local durable owner
indices, existing Runtime/Scientist lifecycle services.

1. **Owner evidence and composition slots.** `chronology_proof.py`,
   `chronology_qualification.py`, `semantic_epoch.py`, `chronology_custody.py`,
   focused `epoch_deployment.py`, deployment security/attestation and container
   composition are owned by the qualification/custody executor. Preserve no-arg
   absence constructors; configured services capture an admitted deployment-local
   owner snapshot, never a last-app-wins global. Resolve exact appointment evidence
   using existing consumers. A new institution can fill supported evidence slots
   without rewriting those consumers. Native predicates cannot be fabricated.
2. **Complete input readers and producer/origin.** The producer executor owns
   `epoch_validity_cascade.py` producer sections, `epoch_transition_origin.py` and
   `epoch_transition_inputs.py`. Preserve `produce_and_persist(previous_epoch_ref,
   current_epoch_receipt_ref, requested_query_context_ref, authority_purpose)`.
   Add owner-held origin admission/readback; independent providers derive full
   dependency and owner-disposition receipts from canonical persisted sources.
   No caller-selected list establishes completeness. Root provides the strict
   Scientist owner snapshot seam; absent producer-issued epoch/recipe bindings
   remain explicit, never silently replaced by an empty basis.
3. **Verifier and denominator bridge.** Root owns focused verifier/composition
   code, `epoch_denominator_reconciliation.py` and
   `scientist/validation/decision_validity.py`. The verifier resolves the exact
   signed transition and admitted origin, verifies profile/context/purpose, and
   derives the existing receipt. Runtime outer digest remains distinct from
   Scientist impact digest. Compose sidecar production with the existing exact
   reader; freeze its binding before state writes. Preserve `NoEpochTransitionVerifier`
   and strict legacy behavior wherever its preconditions still select it.
4. **Production integration and strict consumers.** Root owns
   `runtime/http/services/control/run_lifecycle.py`; container coordination is
   serialized with the composition executor. Resolve canonical owner inputs through
   the existing route, never accept request-supplied authority. Preserve pre-N9
   no-policy/no-signer refusals and strict N9/claim lifecycle checks. An independent
   reader reviews exact consumer assumptions before root edits those branches.
5. **Verification and delivery.** Before each source slice, add a focused failing
   behavioral check; then implement and rerun it. Retain original negatives and
   changed-field/sibling/absence probes. Remove the actual guarded property while
   preserving markers and require the unchanged negative to expose the removal.
   Review deltas, freeze writers, run the final targeted set once, and run registered
   ledger/guardrails each as the sole command in its invocation. Read each clean
   boundary back from the attached branch after commit.

### Stage 2 pattern pass and acceptance

Relevant patterns: P01/P02/P03 (real producer/bridge/surface), P05/P15/P32/P37
(authority from independently verified substance), P07/P08 (exact replay and time),
P29/P31/P33 (structural property and behavioral removal), P34/P35/P41 (bounded
verification and failure provenance). Found gaps are EP-F06/07: complete providers,
origin carrier, positive verifier, production composition and exact consumer bridge.
Initial labels remain `producer_missing`, `bridge_missing`,
`implemented_but_not_orchestrated` until an exercised production chain closes them.

Acceptance is input condition → canonical producer → exact persisted transition
and independently admitted origin → strict receipt/reconciliation → durable batch
and existing lifecycle/API result. Negative acceptance retains no-signature,
no-profile, no-origin, corrupt/omitted source, wrong-purpose/query, incomplete
denominator, and absent/stale appointment refusals. Concurrent write surfaces are
disjoint; Python-heavy checks and final snapshot generation are serialized after
source freeze. Evidence belongs in the lane's gitignored `raw/`, with complete
outputs and SHA-256 in appended journal sections. No fixed total is a stop gate.

### Stage 2 decision boundaries discovered during construction

**EP-D02 — same-epoch adjudication transition.** Task 4.4 in the N12
implementation plan (`2026-08-20-gy-n12-epoch-chronology-implementation.md`,
the same-epoch changed-adjudication/dependency-denominator requirement) includes
a changed owner disposition with unchanged semantic epoch. The actual
`EpochValidityTransitionArtifact._bind_transition` refuses equal previous/current
epochs. The divergent witness is a newly admitted invalidation for an unchanged
native epoch. This lane preserves that validator and builds the distinct-epoch
chain. Only admission of a same-epoch transition requires a ruling; no unrelated
appointment or composition work waits on it.

**EP-D03 — qualified pre-N9 query carrier.** The exact positive native result is
`NativeChronologyQualified`, whose query lives at
`reconciliation.owner_context.query`. The existing
`PersistedEpochPromotionQueryStatement._query_is_derived_from_owner_fields`
instead reads `getattr(result, "query", None)` and refuses that result. The
non-test `_PersistedNegativeEpochQueryOwner.resolve_for_promotion` explicitly
requires `NativeChronologyPolicyResolutionFailed(PolicyAdmissionMissingFailure)`;
the pre-N9 authority gate then reads `stored.query`. A real independently
qualified result therefore cannot enter that existing carrier. The requested
consumer-change rule applies at this exact link. Pending approval, these
consumer predicates stay unchanged. The proposed extension would extract the
query from the qualified reconciliation and keep exact equality, persisted proof
readback, subject/candidate/query binding, and completed-batch verification; it
would not accept an unverified qualified marker. The separate `current` prior
binding refusal and superseded-successor refusal remain intact.

**Execution scheduling correction.** The earlier Stage 2 statement serializing
all Python-heavy checks was too broad. Independent targeted tests with separate
scratch may run concurrently; native owner writes, shared generated snapshots
and final deciding gates remain serialized. Actual import-time complete-source
validation can take minutes; interrupting it produces a non-receipt, never a
product failure or an intended RED.

**EP-D04 — native semantic-basis change event carrier.** CB-C03A/D01/D02 require
revalidation when the actual full native semantic basis of an issued certificate
changes. The new `NativeEpochSemanticBasisDeltaProvider` re-reads the native
predecessor/current receipt, reconciles full-basis dependency edges and persists
an exact delta. The existing `AdvisoryPerturbationEvent.source_class` admits
incident, appeal, correction, retraction, legal change and discovered bias; none
means a native semantic-basis change. Serializing the delta as a correction would
invent that assertion. The next link therefore returns
`epoch_native_semantic_change_event_carrier_not_established`. The proposed
`semantic_basis_change` arm requires a consumer ruling, with exact old/new basis
and owner dependency binding preserved. Empty monitor inventory is never evidence
of unchanged native semantics. Other producer, origin, verifier and composition
work does not wait on this link.

### Stage 2 implemented chain and remaining slots

The real call path is the registered run-control route →
`ControlPlaneService.admit_epoch_validity_batch` → the same container-owned
`DecisionValidityService` → `CanonicalEpochTransitionVerifier` →
`EpochTransitionProductionBridge` → `EpochValidityTransitionProducer` → exact
signed repository and `FileEpochTransitionOriginOwner` readback → independent
Scientist impact snapshot → producing reconciliation reader → unchanged strict
batch admission → the existing completed-batch Claim lifecycle bridge. Request
fields remain only transition/context handles. The positive route witness uses
controlled institutional inputs; it does not appoint a deployed institution or
claim that EP-D04's native event boundary has been passed.

The decision-packet path is real production execution:
`ControlPlaneService` legacy workflow / NL pipeline → `scientist.api.run_experiment`
→ selected workflow/context → `BuildDecisionPacketNode` → neutral issuance port
→ Runtime `DecisionPacketEpochIssuanceOwner`. The owner admits only a sealed
canonical completion after packet persistence, freezes native history/basis, and
cross-checks exact packet binding on replay. A complete independently admitted
executable recipe/input resolver is a privileged typed deployment slot. Labels,
request metadata and a signed declaration cannot supply its missing premise.

| Slot | Construction and later configuration | Empty or invalid result |
| --- | --- | --- |
| Predicate-policy admission and native verifier | `EpochDeployment` captures exact policy evidence, trust and existing `PredicatePolicyOwnerProvenanceVerifier`; qualification registry is per deployment | `policy_admission_missing` / `policy_owner_relation_not_established` |
| Transition signer/profile | Deployment captures public trust, exact signed transition and independently admitted signing profile; private signing authority is never synthesized | Original NoSigner remains; missing exact evidence refuses |
| Independent history holder and acceptance | Scoped custody factory captures resolver, registry and repository; exact appointment/retention/readback checks remain existing consumers | Independent holder/acceptance absence remains typed |
| Issuance recipe/native inputs | Privileged `epoch_certificate_issuance_input_resolver`, identical CAS owner in actual packet execution | Persisted typed nonreceipt, no fabricated empty denominator |
| Complete owner adjudications/actions | Privileged `epoch_perturbation_adjudication_provider` and `epoch_owner_disposition_evidence_reader`, independently reloaded exact evidence | Missing basis/action admission refuses; native event carrier is EP-D04 |
| Transition verification/reconciliation | Production composition installs canonical verifier and producing strict reader on the existing DVS owner | NoVerifier and typed unavailable reader remain reachable |

These are configurable mechanisms, not appointments. The native semantic verifier
has a deliberately unresolved semantic hash domain: generic signed transport
cannot establish a predicate's content hash merely because that field was signed.
A validly signed false-hash declaration was admitted by an early implementation;
the same retained falsifier now refuses without an independently supplied native
verifier. This is the same P32/P37 class one level deeper, not a separate right to
mint or a reason to remove verification.

### Stage 2 scope and denominator boundaries

Origin and issuance admission indexes select the actual trusted tenant/cell scope
at operation time, with full readback inside that scope. Unscoped local operation
retains its own root. The verifier emits its own canonical provenance bytes under
the active CAS ownership scope; it cannot grant access to someone else's input.
Native history remains the explicitly configured deployment root. Existing DVS
state tenancy is not redefined by this lane; strict packet/dependency reconciliation
reads the complete existing owner index and never drops an inaccessible member.

Runtime source readers consume the full manifest inventory exposed by their CAS
and reconcile exact source-kind candidates against native owner history. Scientist
impact selection reads both complete `.json` indexes (dependencies and packets)
under the owner lock, then cross-reconciles their relations before target filtering.
An unreadable member refuses. No source-name query, fixed total or empty monitor
list establishes completeness. Runtime outer and Scientist impact denominators
remain distinct, with their relation independently recomputed and frozen once.

**EP-D03 includes the temporal projection carrier.** The unchanged temporal
service refuses a qualified native result at
`epoch_staleness_epoch_reader_not_established`, and an exact signed result at
`epoch_staleness_transition_reader_not_established`. Wiring configured native
query dependencies into temporal/promotion is implemented; changing these positive
consumer arms remains withheld. Neither branch was made unreachable or replaced
by an authority-granting fallback.

**P40 residual — existing shared DVS state.** Review falsified the first new
impact reader with two tenants sharing exact target bytes: the old global packet
index allowed another tenant's packet into a new snapshot although CAS denied
its read. The new reader now exact-reads and verifies every packet in its complete
owner index before selecting targets. No inaccessible member is skipped. A shared
legacy index can consequently refuse admission when foreign rows are present;
it cannot issue a mixed-scope receipt. The smallest further capability is a
migration to tenant-owned DVS indexes across the existing consumers. This lane
preserves those consumers and records the bounded availability residual against
`ds18-positive-transition-verification-producer-missing`; it is not a signer
appointment and not a claim of positive multi-tenant DVS partitioning.

**Recipe source correction (CB-D04/D12; Task 4.3).** An opaque recipe reference
is not itself an unanswered architecture question. The canonical producer can
emit its actual invocation origin and derive a recipe binding; Task 4.3 expressly
requires no new recipe executor. This computable source work proceeds. Observed
state, NodeSpec and implementation bytes must remain observations until a complete
code/tool/admitted-environment closure is independently established. The existing
Foundry profile admission purpose `n8_method_catalog_reconstruction` is not
relabeled as epoch authority. A missing admitted closure yields its typed
nonreceipt and never a fabricated complete recipe.

### Stage 2: canonical invocation source completed

`BuildDecisionPacketNode.execute` now captures the actual complete serialized
State, RunManifest and NodeSpec before execution, with separate on-disk producer
source and loaded code observations. The immutable invocation preserves finite
float parameters and descriptive dictionaries; an artifact-shaped parameter is
not authority. The absent/default resolver returns a typed nonreceipt before
trying authority-grade source reads, so ordinary candidate production continues.

The Runtime issuance owner derives `_InvocationRecipe` from that invocation and
an independently admitted execution closure, freezes the native epoch history,
reconciles the exact input references, and revalidates source/environment bytes
on readback. Only the private completed execution emitted after actual packet
persistence can finalize the owner index. The actual ControlPlane/NL → Scientist
workflow → node path passes the same configured owner. No separate recipe
interpreter or minting-right mechanism was built.

The native execution-closure implementation remains an explicit deployment
integration contract: it must independently reconcile the full code/tool/admitted
environment denominator for this exact invocation. Neither two equal returned
DTOs nor the literal `independently_reconciled` label establishes completeness.
The configured owner port and its captured-method attestation are implemented;
no production institution or native admission source is selected. The retained
falsifier removes environment revalidation while leaving recipe markers and
makes the unchanged negative fail. This is a bounded P37/P38 source-admission
residual routed to CB-D12 and the existing production row, not a new unanswered
EP-D01 question and not an assertion that the deployed closure is complete.

### Stage 2 row disposition (append-only; Stage 1 remains historical)

The denominator is exactly the commissioned row-ID table in EP-F03, independently
matched to the same register records there. No register status is changed here.

| Original row | Stage 2 disposition |
| --- | --- |
| `ds18-positive-transition-production-unorchestrated` | Canonical invocation/issuance, complete source readers, real producer trigger, exact signed persistence, independent origin admission and lifecycle bridge implemented. Empty native/institutional slots retain refusal; same-epoch, native-event and positive consumer links stop specifically at EP-D02/03/04. No complete deployed positive capability claimed. |
| `ds18-positive-transition-verification-producer-missing` | Canonical verifier and producing reconciliation reader installed through captured deployment on the existing DVS owner. Strict batch consumer unchanged; completed HTTP batch advances the existing Claim ledger in the controlled positive witness. Shared legacy DVS tenancy remains the bounded availability residual above. |
| `GY-DEF23` | EP-D01 origin predicate implemented and read back independently of signer provenance. Signing/native inputs remain configurable empty slots, not unresolved permission to build. |
| `gy-n12-epoch-predicate-policy-authority-unappointed` | Purpose/selection-scoped policy admission, native verifier and persistence registry have captured deployment hooks; default refusal preserved. Appointment is still absent. |
| `gy-n12-epoch-transition-signing-authority-unappointed` | Exact signing evidence/profile slot is configurable; independent producer origin is implemented separately. Appointment absent; positive pre-N9 consumer is precisely EP-D03. |
| `ds18-epoch-predicate-policy-signer-unappointed` | Same scoped mechanism is wired to temporal/promotion composition; no blanket scope equivalence or appointment is asserted. Positive temporal reader is precisely EP-D03. |
| `ds18-epoch-transition-signer-unappointed` | Signing slot stays typed and empty. Existing temporal no-signer refusal and positive-reader boundary remain; no signer-as-origin substitution. |
| `ds18-epoch-history-independent-holder-unappointed` | Custody factory now accepts captured resolver/registry/repository with exact existing appointment/retention/readback checks. Independent holder is unappointed; later configuration does not require rewriting that mechanism. |
| `ds15-semantic-epoch-qualification-authority` | EP-F08 scope finding stands; no acquisition lifecycle source changed. Shared epoch composition changes do not claim this separate row closed. |
| `ds15-fresh-positive-production-route` | EP-F08 observation-delta/same-case re-entry variable stands; no work or closure claimed in this lane. |

Consumer decisions are local stops. EP-D02 changes the equal-epoch invariant;
EP-D03 changes qualified-query and temporal positive consumer carriers; EP-D04
adds the native basis-change event arm. All independent construction above is
carried through despite those pending links. The original Stage 1 frontmatter
and findings are retained verbatim as requested; this appended disposition is
the continuation's current state.

### EP-B01 — incidental backlog: repeated NL authority publication

Destination: **this explicit Stage 2 backlog entry**, owned by Runtime NL authority
publication (`_publish_runtime_quality_report` and its materialization republish).
Trigger: a previously published byte-identical quality report is republished after
materialization refs contain that report's own CAS ID; its expected input closure
then differs from the frozen authority envelope, and publication timestamps can
also differ. The unchanged strict authority consumer correctly rejects.

The full NL module was replayed with identical argv and diagnostic-only wrapper
on current source and a verified product export of slice base `034f30c64` under
CPython3.14.0. Both returned1 with the same failed-node list. This establishes
`base_reproduced`; it does **not** establish P41 inherited exclusion because
changed paths intersect the imported/test denominator. The original expanded
wave remains red. The passing scoped epoch/issuance waves are separate results.

Follow-up acceptance: the publisher must preserve the exact owned publication
identity on reuse, or emit a distinct new authority artifact for a real changed
claim. Choose and test that producer behavior without weakening the strict
consumer. This is outside this epoch producer/configuration slice; no repair or
closure is claimed here. Complete evidence: `epoch-positive-path/raw/nl-importer-adjudication.md`
and `nl-adjudication-evidence-sha256.json` (hashes in the final receipt table).
The reconstructible base export was removed after verification; complete outputs
and the generated migration diagnostic were retained, and linked data/venv targets
were not removed.

### Final boundary and current terminal status

**complete-pending-an-architect-decision on EP-D02, EP-D03 and EP-D04**.

- EP-D02: permit an equal-epoch transition when independently admitted owner
  adjudication/dependency population changed, or retain the existing validator.
- EP-D03: extend the qualified pre-N9 query/temporal positive carriers to consume
  exact independently verified native/transition evidence; current predicates
  continue refusing those unsupported positive shapes.
- EP-D04: admit a native semantic-basis-change event arm; current code refuses
  rather than relabeling that change as a correction.

EP-D01 is implemented as exact canonical execution provenance and independent
owner admission/readback. It is not a separate minting right. All independent
mechanisms and composition hooks are built through the original production caller
and runnable HTTP terminus. Institutional and native source slots remain typed
and empty; no appointment or complete deployed positive capability is claimed.
The native complete execution-closure contract and shared DVS availability
residual remain explicitly bounded above, not silently counted as established.
Stage1 findings and original frontmatter remain historical, byte-for-byte intact.
