# R17 — Исполнимое продолжение: жизнь дизайна, смена политики и доступ

Baseline `d30e957940c7060ac7efcbb571fe3b763a1eee80`. Предпочтительные решения для будущей реализации после E02, **не приёмка кода**. Прежние 121 task IDs и их полные критерии сохраняются; `r17_extension` обязателен дополнительно и зеркален в preferred-solutions. D1–D7 — разрезы существующих задач, не новые engines/root tasks. [Архитектура хранения](../architecture/07-completed-design-custody.md), [преемственности](../architecture/08-incumbent-policy-succession.md), [доступа](../architecture/09-design-isolation-and-access.md); [проверки](../assurance/11-design-custody-succession-access.md); [dispatch](../execution/09-design-lifetimes-and-access.md).

## Общий contract и миграция

Для каждого решающего predicate owning verifier фиксирует basis `recomputed`, `independently_reconciled`, `consumer_asserted`, `institutionally_supplied` или `not_established` на момент admission. Последние три сами по себе не поднимают authority band. Источник факта может быть учреждением; owner обязан независимо проверить достаточные для своего утверждения provenance/content/applicability, а не превращать self-report в подтверждённую реальность. Неизвестные факты допускают явно условную candidate работу при действительных data permissions. Проверка меняет содержательную premise при сохранённой declaration и должна менять решение либо показывать его bounded limitation.

Исполнитель сначала перепривязывает native owners к принятому E02, затем расширяет существующие contracts. `PolicySpec.policy_id`, candidate ID и layer `PolicyOverrideMode.REPLACE` не означают институциональную замену. Reuse ратифицированный PolicyMatter, case lifecycle, PolicyArtifactBuilder, claim lifecycle/head, epoch history, manifest/lineage и authz/source-use. Новая schema version нужна только для отсутствующего смысла с producer/reader migration; нельзя назначить историческим artifacts несуществующий incumbent, mandate, retention basis или watch owner по default.

Старые bytes сохраняются по applicable rights. Legacy reader показывает известный исторический смысл и typed missing relation; migration adapter создаёт новый derived record с исходным ref, adapter/rule version и limitation. Миграция не делает старый draft enactment и не восполняет потерянные данные. Нет автоматического переподписания старых выпусков или обязательного перерасчёта всех случаев. Доверие, права и актуальность проверяются при конкретном use; protected authority не наследуется через migration.

<a id="D1"></a>
## D1. Завершённый дизайн как сохраняемый интеллектуальный результат

**Owners:** DES-06 producer, LIF-07 influence/manifest, LIF-05 retention/use, OPS-05 retrieval/recovery. Anchor: `scientist/policy_design/output.py::PolicyArtifactBuilder`, `core/artifacts/manifest.py`, `ir/artifacts/lineage.py`; case lifecycle и claim refs остаются у их owners. DES-07 edits создают новую связанную edition.

**Реализация:** closing path строит exact edition manifest с исходным вопросом/целями, материализованными существенными альтернативами и причинами отбора, selected source/world/method/code/rule/profile/units, result/counterevidence/review/claim refs, machine/human renditions и representation dependencies. Сохранять это через existing CAS с recoverable commit, а не копировать tracked/raw данные в каждый пакет. Inventory различает retained bytes, external/query ref, permitted rendition и genuinely unavailable. Closure выводится из действительного selected design/read-set и owning artifact contracts; отсутствующий родитель не исчезает из denominator.

**Ready signal:** independent fresh reader после закрытия и последующего выпуска читает старую edition и её объяснимые ограничения без current pointer или живого author workspace. Раздельно: fixity, intelligibility, historical replay, current admissibility. Ссылки без сохранённых bytes не называются полным offline archive. Historical executable retrieval не запускает код автоматически. **Q01/Q02/Q03.**

**Отклонено:** только zip/CAS hash, вечное хранение всего, второй generic design-store. Free-grow: versioned manifest/representation descriptors и actual closure, не отдельный шаблон архива на каждую политику.

<a id="D2"></a>
## D2. Preservation duty, ключи, удержание и восстановление

**Owners:** OPS-05 storage recovery, OPS-11 trust/evidence renewal and custody transfer; LIF-05 lawful placement/use/delete; optional OPS-10 remote parity, OPS-12 offline profile. Общая continuation/accounting инфраструктура LIF-04/06, не второй scheduler.

**Реализация:** versioned preservation profile задаёт риски форматов/носителей/криптографии, scope/coverage/cadence/бюджет проверок, independent-copy repair, bounded cold retrieval и safe migration. Исторический оригинал и новая representation связаны, не подменены. OPS-11 сохраняет доступную verification material и запускает своевременное renewal при выбранной доказанной технологии; RFC 4998 — пример, не обязательный формат. Renewal продлевает проверяемость исторического свидетельства, не текущую истинность или право подписи. Потерянный chain / неизвестный compromise cutoff ограничивает доказательство, новый timestamp не исправляет прошлое.

Hold/retention/erasure/use различаются по применимым основаниям. Не выбирать универсальный срок из operational R3/R4 defaults. Restore должен учесть все более новые rights changes; deny/tombstone переживает все restorable generations либо действует независимый актуальный rights authority. Невозможность восстановить эту историю оставляет выдачу в quarantine. Transfer связывает exact archive/rights/verification/watch duties, recipient intake и принятие duty; export bytes не переносит authority. **Q03/Q04/Q05/Q06.**

**Отклонено:** новый sovereign архив, hash=truth, encrypted=erased, backup=доказанное recovery, TUF=институциональный issuer. Local slice не ждёт cloud; каждый выбранный backend получает собственный фактический witness.

<a id="D3"></a>
## D3. Бounded наблюдение, проверка и переиздание

**Owners:** CAP-04 source producer, CAP-05/LIF-01 применимость, LIF-02 currentness, LIF-04 durable duty, LIF-06 budget, OPS-11 continuing custody; DES-04 полезный revision/research route.

**Реализация:** подписанный или иным образом принятый standing duty называет scope, источники, owner/deputy, срок/периодическую ревизию, trigger semantics и ресурсную ответственность. Source watch имеет проверяемую interval/partition/generation coverage, а не только пустой inbox. Push events дополняются scoped reconciliation/polling для молчаливых источников; cadence задаётся risk/purpose, а не одним cron для всех. Необязательная research freshness не превращается в право утверждать completeness.

Свежий event сначала меняет допустимость затронутого use через LIF-02, затем LIF-04 организует минимальное re-evaluation. Возможны обоснованный no-change, scoped correction/limitation, новый candidate, новое издание при выполненных исходных issuance rules, transfer/cutoff. Numerical rerun нужен только если actual influence изменился; отсутствие compute не оправдывает старый currentness. Малые накопленные изменения сравниваются с последним принятым basis, а не только соседними events. Drift/performance/causal change — разные hypotheses; ложная тревога и delayed labels предусмотрены. **Q07/Q08/Q09.**

**Отклонено:** вечная автоматическая симуляция всех закрытых cases, «cron ran→evidence current», automatic re-sign after rerun. Expiry duty вызывает явный scoped lapse/review/transfer по owning contract, не самовольное юридическое прекращение внешней политики.

<a id="D4"></a>
## D4. Кандидат при действующей политике и подтверждённая преемственность

**Owners:** DES-11 temporal/trajectory adapter + existing GYD-30 execution; DES-03 search/DES-04 revision; CAP-05/CNT-04 actual legal act intake, CAP-04 operational source event; LIF-01/02 receipt→claim reaction, DEB-06 canonical epoch reissue; DES-06/07 documents, UI-04/19 history/currentness. Один current-head writer сохраняется.

**Реализация:** candidate сравнивается с grounded incumbent exposure/commitments и declared uncertainty. Transition включает lag/carryover, shared capacity, residual obligations и scope, где старый режим продолжает действовать. Корректировка при неизвестных фактах возможна как условная кандидатная ветвь, не assertion реального исполнения. Relation/event различает PolicyOS recommendation supersession и внешнее изменение правового/операционного состояния. Содержание и компетенция источника проверяются по выбранному applicable verifier, не по наличию подписи или author status.

Read model вычисляет applicable incumbent set по scope + effective time + known-at cutoff + authority purpose, поддерживает overlap/grandfathering/отложенную дату/исправления/конфликт. Published candidate не переключает incumbent. Institutionally effective act не доказывает operational receipt. Rollback — новый ход с сохранившимися последствиями, не стирание мира. Synthetic institutional fixture доказывает внутренний механизм; настоящая legal/operational authority требует своего input. **Q10/Q11/Q12.**

**Отклонено:** один `current=true`, newest-wins, второй succession engine, обязательный закон/шаблон для любой страны, институциональное execution от PolicyOS. Unknown scope не подменять конкретным default.

<a id="D5"></a>
## D5. Научное обучение через смену режимов

**Owners:** DES-12 study intent/returns, CNT-06/08 inference/transport, GYD-09 confirmatory, GYD-10 exploratory, GYD-12 admitted world write; DES-08 lawful memory. GYD-08 sealed holdout/selection boundary не переоткрывается.

**Реализация:** actual published/adopted/effective/operational/exposure histories поступают как разные evidence. Selected estimand определяет необходимую детализацию: assignment/eligibility/availability, receipt/dose, policy strategy/version, target/weights, preceding/concurrent exposures, measurement regime и uncertainty. Не требовать индивидуальные записи, если admitted aggregate estimator достаточен; не принимать агрегатный marker, когда property требует другого. Existing method registry решает adequacy; список методов в research не является обязательной новой библиотекой.

Announcement в t1 может вызвать response до effective t2/receipt t3; selected method должен учитывать нужную exposure/awareness или давать сценарий/границу/limitation. Missing receipt не означает отсутствия anticipation. Time-varying confounding, carryover, anticipation, staggered rollout, interference, changing composition, delayed/corrected observations и repeated selection могут изменить interpretation. Новый результат сохраняет old-as-known и отдельно corrected basis; O2 candidate не становится независимым O1 evidence из-за нового номера версии. Protocol/target amendment — revision с selection consequences, не переписывание preregistration. DES-12 может предложить полезное исследование при недостаточной идентификации; не изобретает право провести его. **Q12/Q13/Q14.**

<a id="D6"></a>
## D6. Общий access lifecycle и выбранные deployment modes

**Owners:** OPS-06 authz/object resolver, LIF-05/CAP-03 source use; DES-09 actual tool/provider recipient, DES-08 memory, selected CAP-06/OPS-09 source-side compute, OPS-10 remote, OPS-12 offline. Existing OPA/authz сохраняется предпочтительным, новый IAM не нужен по одному наличию SOTA аналога.

**Реализация:** coarse roles + exact object relations + purpose/audience/context rights, owner-resolved tenant и nonamplifying delegation. Consumer-side generation/causal fences для revocation, retries, streams, materialization и results, включая actual provider egress release. Зафиксировать точку release, порядок относительно revoke и sent/not-sent/indeterminate outcomes; local commit refusal не отзывает уже отправленные bytes. При невозможности строгого порядка — только явно разрешённый bounded in-flight profile; unsupported stronger use не выдавать за safe. Offline snapshot/clock rollback не должен повышать freshness сверх доказанного cutoff. Required policy facts/errors обрабатываются явно; validated schema не восполняет недостающую source authority. Shared cache identity не является permission. Public/derived/LLM output проверяется на actual emitter, а не только API entrance. Режимы выбираются по [architecture09](../architecture/09-design-isolation-and-access.md); local path не блокируется remote/offline parity.

**Ready signal:** разрешённый exact cross-project share даёт полезный результат, исходные данные остаются restricted; revoked/foreign/purpose-changed/provider-deputy запросы блокируются у реального consumer, включая historical archive. **Q15/Q16/Q17/Q18.** Сохранить lawful cross-case learning вместо blanket deny.

<a id="D7"></a>
## D7. История, доступные поверхности и единая приёмка

**Owners:** UI-02/03/04/08/19, DES-06/07, LIF-09, FINAL-*; actual producer-owned statuses остаются у D1–D6. UI не изобретает legal/state facts, publisher не получает внешний mandate.

**Реализация:** coherent API/MACHINE/browser/CLI/audit/document projection показывает edition lineage, old-as-known/current-qualified basis, причины пересмотра, candidate versus real institutional transition, remaining scope, watch/retrieval/access limitations. История append-only в пределах lawful retention; удалённый payload честно unavailable. Candidate/private completion не обязана становиться public. UI-02 initial data-only/typed-empty signer contract сохраняется: signed-positive admission отдельно требует genuine authority. Public metadata/list/link/search paths проходят тот же disclosure scope; исправление записи не обещает отзывать чужие скачанные копии.

**Проверка:** один выбранный путь close→archive→change→new candidate→verified scoped external transition→fresh current/historical readers, с разрешённым и запрещённым получателем. Компонентные witnesses готовятся независимо; общий дорогой replay только в существующем frozen FINAL-REPLAY, не новая R17 wave. До FINAL-USE перечислить доступные modes и реальные guarantees; не требовать всех clouds/estimators/jurisdictions. **Q01–Q18** по выбранным обязанностям. Genuine inputs и unselected/limited scopes не приравнивать к закрытию.

Pattern pass: P01/P02/P03/P04/P05/P07/P08/P09/P10/P13/P14/P15/P27/P29/P31/P32/P35/P37/P38/P40/P41. Target — реальный producer→persisted evidence→owner bridge→fresh consumer/surface, с отдельно доказанными bytes, meaning, authority, time и permission. Все runtime acceptance signals здесь **UNRUN**.
