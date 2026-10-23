# R17: завершённый дизайн, долговременное хранение и переиздание

Проект после фактической приёмки E02. Исследованный baseline `d30e957940c7060ac7efcbb571fe3b763a1eee80`; runtime UNRUN. [R16](06-composition-and-reexecution.md) сохраняется. [Практические работы](../solutions/17-design-custody-and-succession.md), [проверки](../assurance/11-design-custody-succession-access.md), [исследование](../research/design-custody-succession-access-r17.md).

## Уже предусмотрено и что уточняется

LIF-02 уже задаёт enrollment/replay/currentness fence; LIF-04 — durable duty; LIF-05 — actual copies/retention/deletion/restore; LIF-07 — influence и reuse; OPS-05/10 — recovery/CAS; OPS-11 — trust succession и watch cutoff. Это сильная проектная основа, не runtime receipt. Недостаточно явно задана целостная **сохраняемая редакция завершённого дизайна**, проверяемость её понимания спустя годы, длительность watch coverage и переход от пересмотра к переизданию. Дополняем existing owners, не создаём archive platform.

## 1. Что считается сохранённым дизайном

Stable matter/case identity, immutable design edition, отдельные calculation runs, public signed releases и external implementation records связываются native refs. Reuse ратифицированную PolicyMatter/case identity; новая project-global «design family» registry не нужна. Один matter может иметь конкурирующие редакции и разные releases для разных аудиторий. Publication не обязателен для preservation приватного завершённого дизайна; завершение вычисления не завершает custody подписанного claim.

Native closing/PolicyArtifactBundle producer (DES-06) собирает versioned manifest через CAS; LIF-07 проверяет actual dependency closure. Содержание выбирается по obligations завершённого результата, не по всем файлам workspace:

- исходная постановка/мандат, selected candidate и material alternatives, причины исключения/неполноты поиска;
- causal/world/model/executable/rule/measurement versions, exact evidence/input cuts, selected numerical guarantees и ограничения;
- actual results, substantive counterevidence, independent deciding verification, decision/approval records с их реальной authority;
- машиночитаемое представление и читаемая человеком редакция; словарь/схема/representation information, необходимая соответствующему reader для понимания;
- rights, retention, target audience, currentness duty и ссылки на текущую qualification отдельно от исторического issuance.

Manifest различает actual retained bytes, доступный remote/query-only reference, сохранённое разрешённое представление, отсутствующий/удалённый input. External ref сам по себе не доказательство сохранности. Полнота выводится из настоящих producer outputs и owner obligations, не из hand-written списка, который сам объявлен complete. Индекс/backup без достаточной representation information не обеспечивает понимание.

Не копировать в каждую редакцию весь raw dataset, env и tracked code. Content-bound immutable chunks/views, native manifests и permitted references переиспользуются внутри допустимой изоляции. Сохранять decision-relevant search coverage и failures, а не бесконечно все logs/temporary candidates. Selection/compaction policy versioned и не выкидывает противоречащее evidence. Granularity dependency должна позволять честно назвать потерянную возможность при удалении.

## 2. Четыре независимые гарантии

| Гарантия | Необходимая проверка | Чего из неё не следует |
|---|---|---|
| Bit integrity | Actual payload читается, digest сверяется с доверенной связью manifest; membership closure полна в заявленной границе | Истинность, законность, semantic equivalence |
| Readability / interpretability | Fresh reader понимает выбранную representation, units/constructs/limits и exact edition без старого running service | Возможность заново вычислить result |
| Historical replayability | Доступны разрешённые inputs, executable/profile/state и compatible environment; actual replay имеет заявленную гарантию | Current admissibility или безграничная executable portability |
| Current admissibility | Fresh rights/claim/currentness owners разрешают конкретное use на настоящем основании | Неизменность исторической оценки, полномочие исполнить policy |

Эти свойства — раздельные capability predicates, не новый универсальный status enum. Установленная fixity не скрывает schema obsolescence; недоступный executable не делает preserved document ложным. При потере входа replay unavailable явно; запрещено reconstruct history с сегодняшними defaults. Старый executable не запускается из архива автоматически: isolated, resource-bounded, no-egress by default unless expressly admitted, без сохранённых credentials.

## 3. Storage и maintenance protocol

1. DES-06 закрывает exact edition; LIF-07 связывает actual required graph и declared availability; CAS записывает immutable payloads и manifest. Recoverable owner transaction публикует pointer после проверки объектов; частичная запись не complete archive.
2. OPS-05 назначает preservation duty: integrity checks, representation review, recovery exercise и retrieval objective для конкретного класса. Cadence, sample/full-coverage policy и failure domains объясняются риском/cost; universal «хранить N лет» и универсальный storage SLA не вводятся. Выборка доказывает только проверенную часть.
3. При чтении из cold/remote tier: durable retrieval intent, текущий auth/use admission, actual availability/fixity, restore quarantine, post-backup revocation/history reconciliation, fresh consumer. Cold bytes не означают немедленную доступность; timeout не стирает обязанность дать truthful outcome.
4. При corruption: не «починить» исторический hash по испорченным bytes; quarantine affected use, восстановить из independently checked copy, сохранить событие восстановления и verification. Если corroboration нет — повреждение/неустановленная целостность остаются.
5. Migration/re-encryption/rehash создаёт новую representation/placement и relation к прежней. Byte equivalence, semantic equivalence и archive format conformance проверяются отдельно. Старый public signed payload не меняется in place. Verified migration не присваивает старому result новое научное подтверждение.
6. OPS-11 ведёт отдельную crypto-evidence duty: trusted validation material, applicable algorithms/keys, revocation/compromise timing и допустимое renewal до утраты нужного security basis. Новый timestamp/подпись не исправляет уже lost evidence chain и не доказывает истинность содержимого.

OPS-10 остаётся selected remote adapter; local custody route не зависит от его готовности. «Есть backup» и «можно recover с правами и историей» — разные claims. Replica в том же failure domain не считается независимой recovery copy без основания. Tenant-local dedup не переносится автоматически на cross-tenant storage или shared encryption keys.

## 4. Retention, holds, deletion и offboarding

Applicability/retention owner получает реальную source/license/law/purpose basis: что разрешено/обязательно хранить, до какого события/срока, допустимые readers, какие copies controlled. Legal hold сохраняет только назначенный scope и не даёт права продолжать анализ/публикацию. Conflict retain-vs-delete направляется к надлежащему owner; алгоритм не придумывает правовую иерархию. Пока нет lawful action basis, affected operations ограничиваются с ясным residual, не выдаётся универсальное обещание сохранить или удалить всё.

Actual placements включают warm/cold replicas, export packages, cache/embeddings, backup и provider-held artifacts в доказуемом control scope. Deletion tombstone и policy generation живут **как минимум относительно всего ещё допустимого restore frontier**, а не просто TTL удалённого объекта; иначе старый backup воскресит запрет. Backup restore обязан пройти quarantine/reconcile до любого readable head. Если suppression history потеряна, восстановленные bytes не становятся автоматически доступными.

Cryptographic erasure требует установленного key hierarchy и полного applicable key/copy denominator; shared key, exported plaintext, provider cache, old wrapped DEK или recovered key разрушают blanket erasure claim. Удаление locator/manifest не доказательство physical purge. Не хранить sensitive identifiers/hash в tombstone, если их retention/visibility не разрешены. Разрешённый факт прежнего решения и unavailable reason может пережить payload; нельзя обещать даже это без lawful basis.

Offboarding: передать exact custody package и права через verified recipient intake, провести actual recovery/read check, принять обязанности successor с непрерывностью либо явным gap/cutoff. Экспорт байтов не переносит source license, подпись или duty автоматически. Retirement собственного сервиса завершает подписанную обязанность только по ратифицированному transfer/cutoff, не нажатием archive.

## 5. Как проверять актуальность завершённого дизайна

Для каждого standing claim назначается existing OPS-11/LIF-04 duty с scope, owner/deputy, term, источниками, review triggers/cadence, method и authority порогов, resource reserve, overdue reaction, successor/cutoff. Publication с current promise требует настоящего enrolled watch. Historical as-of assertion не получает бесконечное current promise из UI default.

Два комплементарных пути: admitted events с replay continuity и periodic reconciliation с actual source-supported cuts/journals/independent witness. Inbox empty, latest timestamp и успешный cron не доказывают coverage. Coverage receipt связывает actual watched dependency denominator, source incarnation/partition, cut/high-water/replay floor, covered interval, gaps, method и limits. Consumer не может сам подтвердить полноту declared source set; completeness относительно known basis не обещает обнаружить всё новое знание в мире.

Сигналы: data correction/retraction; новые observations и delayed outcomes; law/mandate/rights change; calibration/model/executable change; changed external conditions/incumbent exposure; complaints/incidents как evidence; source outage; representation/crypto risk. Новые evidence classes вводятся native registry/adapters, а не бесконечным central switch. При необходимости обновляется и dependency discovery: не только старые subscribed parents.

Scientific drift, performance loss и causal effect — разные hypotheses. Repeated monitoring требует selected method-valid error control; threshold не supplies normative authority. Cumulative materiality считается относительно последнего принятого basis, не сбрасывается каждым малым событием. Несколько subthreshold shifts могут изменить decision. Missing labels/observations не нулевой effect. False alarm может завершиться обоснованным no-change assessment.

Outcome маршруты:

- **Covered no-change assessment:** actual bounded reconciliation подтверждает прежнюю квалификацию в данном scope; новая assessment receipt, прежние signed bytes неизменны.
- **Immediate limitation/correction:** affected public/currentness reaction без ожидания нового расчёта; LIF-02 и existing durable correction surface. Это действие над собственной подписью.
- **Reanalysis/new candidate:** actual bounded R16 duty → new calculation/design branch; previous operational policy пока не заменена.
- **Reissue:** authoritative native issuer принимает новый exact basis/review, публикует новую edition/release с причиной, predecessor и scoped effective semantics. Связанный update notice для наших records проходит existing custody delivery; delivery attempt ≠ human acknowledgement.
- **End/transfer:** accepted successor либо authorized cutoff, recorded gap и honest historical projection.

Один outcome не обязан немедленно вести к следующему. На исчерпание ресурсов — overdue/pending/limited по owning contract и escalation, не silent success; LIF-06 сохраняет минимальную capacity для custody reaction. Нельзя обещать currentness при неисполнимом watch contract.

Pattern pass: P01/P02/P04/P05/P07/P08/P09/P10/P13/P14/P29/P31/P32/P35/P37/P38/P40. [R17 assurance](../assurance/11-design-custody-succession-access.md) задаёт полезные цепочки и removal; все runtime guarantees пока UNRUN.
