# DEB-09.delegation-mandate — Проверить signed v2 delegation и mandate owner

Группа: [G06 — Допустимость, полномочия и квалифицированные решения](../../groups/G06.md). Родитель: [DEB-09](../../parents/DEB-09.md). Роль: `input`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Два раздельных purpose-bound результата: DS15 signed-v2 delegation/current mandate для выбранного route; при R18-D23-Q02 — наличие либо отсутствие preaccepted delegation от текущего human principal на exact SDD amendment act/scope. Один не заменяет другой.

**Предпочтительное решение.** Reuse LIF-01 intake и existing DS15 verifier для DS15 evidence; для Q02 сначала найти instrument в accepted history и проверить identity, exact act/scope и currentness по S18-M2. Не создавать appointment/succession service.

**Граница владельца.** Input collector проверяет и связывает evidence; DS15 institution и human principal сохраняют собственные полномочия. Внутренний root назначает поиск/проверку, но не назначает successor. Native paths/lease задаются E02 rebind; неизвестность record не означает необходимость внешнего поставщика кода.

**Входы.** DS15 row: signed-v2 delegation, current mandate-owner evidence, selected purpose/scope, LIF-01 interface. Q02 row отдельно: accepted-history ref, текущая principal identity, preaccepted exact SDD act/scope instrument, dates/expiry/revocation/challenge. Если standing оспаривается, нужен recognized governance source; не требовать нового внешнего акта при уже проверяемом accepted record.

**Выход и consumer.** Два отдельно source-qualified outputs: DS15 admission/typed-empty к selected DS15 reader и Q02 standing record/unresolved к существующему amendment decision process; FINAL-USE потребляет Q02 только если selected use зависит от amendment. W5 crosswalk сверяет роли, не даёт права изменить SDD.

**Что можно готовить независимо.** После разрешённого исходным stage contract source/lease rebind выполнить первые действия ниже; до разрешённой стадии — только назначенное read-only discovery. Actual supplier outputs нужны при их потреблении, а не для всей независимой подготовки. Карточка не добавляет start barrier.

**Где результат соединяется с другими.** DS15 evidence соединяется в selected DS15 admission; Q02 evidence идёт в existing amendment decision record и dependent FINAL-USE. Root сохраняет отдельные purpose/scope/status и output refs, не объединяя их в общий delegation green.

**Positive.** Реальные внешние signed-v2 delegation и current mandate-owner evidence независимо разрешаются и verifier-проверяются; оба связывают один выбранный DS15 purpose/scope, после чего существующий DS15 consumer допускает только эту область. Отдельный Q02 positive: accepted-history instrument связывает реальную current-principal identity, exact amendment act/scope и действующее, неотозванное полномочие; dependent consumer читает только эту область. Это не technical issuer/root succession.

**Distinguishing negative.** Подпись без актуального mandate owner, истёкший мандат или документ для другого purpose/scope оставляет delegation typed-empty/refused. Q02: отсутствие, спорность, истечение/отзыв record либо лишь техническая successor role оставляет amendment предложением; обычная разрешённая engineering и candidate работа по действующим правилам продолжается.

**Matched removal.** Reconciliation probe (LIF-01 verifier и существующий DS15 checker остаются включены): подменить в сохранённом mandate evidence purpose либо valid interval, не меняя `delegation admitted` marker. Проверка привязки обоих внешних актов должна обнаружить расхождение с выбранным DS15 purpose/scope и вернуть typed refusal. Отдельный Q02 binding-substitution control при включённом verifier: удалить/подменить principal identity, exact amendment act/scope либо currentness binding, сохранив имя/подпись; dependent authority consumer не принимает amendment. DS15 и Q02 controls не засчитываются друг за друга.

**Граница контекста.** Два typed intake uses одного evidence-collection назначения, а не два механизма или автоматическая взаимная dependency. DS15 route и Q02 активируются каждый своим выбранным use; отсутствие Q02 не блокирует работу по действующим SDD.

## Первые действия и передача

1. Установить выбранный use: DS15 delegation, Q02 amendment standing либо оба; вести отдельные rows и consumer refs. Для Q02 сначала искать succession/delegation instrument в accepted history.
2. Для DS15 разрешить два реальных evidence artifacts через LIF-01: content/digest, signer provenance, valid interval и exact purpose/scope; не заполнить один слот другим.
3. Для Q02 проверить current-principal identity, exact SDD act/scope, dates, revocation и challenge. При отсутствии/споре записать proposal/unresolved и конкретный следующий source; ordinary authorized engineering продолжается. Recognized governance source нужен для спорного standing, не для каждого read-only поиска.
4. Передать отдельные outputs existing DS15 reader и amendment decision process/dependent FINAL-USE; показать source-specific positive и binding-substitution controls.

**Ответственность и handoff.** Collector не создаёт внешних delegation acts и не ратифицирует amendment. Внутренние lookup/intake/verifier/consumer links — назначенная инженерная работа; root передаёт действительное спорное standing компетентному источнику. Technical issuer/root succession не заменяет полномочие human principal.

Порядок действий внутри назначения не добавляет dependency edges. Примеры проверок дополняют полный назначенный criterion; actual commands/paths закрепляются в [packet](../../../task-decomposition/work-packet.md) после source rebind.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Consume this supplier’s actual accepted output as required by the canonical DEB-09 source dependency; this is a consumption map only and does not alter source stage/dispatch semantics.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [LIF-01](../../parents/LIF-01.md) | `direct:owner_readiness`: Consume this supplier’s actual accepted output as required by the canonical DEB-09 source dependency; this is a consumption map only and does not alter source stage/dispatch semantics.<br>Source: `task.depends_on[1]`.<br>Условия: original direct relation; source stage rules govern |
| Composition output (не start gate) [DEB-09.w5-crosswalk](../../cards/DEB-09/w5-crosswalk.md) | Consume only for the exact composition described here: Read the named output through Fresh DS15 selected-route admission consumer.; composition is limited to this property and the exact original scope. This link is not an unconditional all-of or preparation gate. |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `DEB-09`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **execute** — Primary accountability is DEB-09.delegation-mandate (input collection) for R18-D23-Q02/S18-M2: search accepted history and bind the current human principal’s exact SDD amendment delegation separately from DS15 signer/mandate evidence. Absence/contestation leaves amendment proposed while authorized engineering continues. Embedded question_id and its ID selector match by value; all source positive/adversarial/removal clauses remain required.
  `task.r19_extension.question_slices[0]` (`R18-D23-Q02`); `task.r19_extension.question_ids[0]` (`R18-D23-Q02`)

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
