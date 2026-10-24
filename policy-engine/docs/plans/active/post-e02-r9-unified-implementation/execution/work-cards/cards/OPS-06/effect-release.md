# OPS-06.effect-release — Повторно сверять grant на фактическом выпуске

Группа: [G06 — Допустимость, полномочия и квалифицированные решения](../../groups/G06.md). Родитель: [OPS-06](../../parents/OPS-06.md). Роль: `consumer`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** A provider/source effect or byte release occurs only when the exact source/query, actor, purpose, recipient and time grant is still valid at the irreversible release boundary.

**Предпочтительное решение.** Use the existing source-right decision owner and each connector/effect sink. Re-resolve at execution, retry, resume and immediately before release; network perimeter is supplementary evidence only.

**Граница владельца.** OPS-06 writes the semantic decision/fence under the same canonical `write:exact-path/{canonical_repo_path}` family; source, network, sink and connector owners remain separate. Exact paths and shared-owner intersections are unknown until accepted-source rebind.

**Входы.** Current source/rightsholder grant and source/query identity; OPS-04/LIF-04 durable attempt, retry/resume identity; OPS-07 scoped credential (not permission); Selected egress/network observation and actual sink

**Выход и consumer.** Released effect or durable refused/limited receipt with source/use grant provenance and release-time validity, read by the source/provider effect owner and audit surface.

**Что можно готовить независимо.** The decision and fence can be prepared against agreed source/sink contract. Protected execution requires actual current source-use evidence at the effect boundary; if the selected profile cannot fence a racing revocation, record an explicit in-flight limitation.

**Где результат соединяется с другими.** The read policy may be shared, but read projection and irreversible source effect are independent emission planes. OPS-07 secret health and network allow rules do not authorize; LIF-05 controls retention/copies and the institution supplies its act.

**Positive.** Exact currently granted source action succeeds with purpose, recipient, audience and time bound to the attempt; permitted release is visible in the authorized audit surface.

**Distinguishing negative.** Grant revocation winning before release, wrong query/recipient, unauthorized existence metadata or unapproved egress blocks the affected effect.

**Matched removal.** Remove consumer-side grant resolution or release-time check while keeping labels; the actual forbidden provider/read sink still receives no bytes/effect.

**Граница контекста.** One existing policy authority feeds a distinct actual effect fence. R17 obligation includes the whole access lifecycle but remains an input/output contract; P09/P15 prevent stale or credential content from becoming permission.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Both planes rebind against actual E02 accepted readers and source/effect sinks; inherited parent stage and leases apply.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Supplier [OPS-01.commissioning](../../cards/OPS-01/commissioning.md) | `direct:owner_readiness`: Consume the selected source/use scope and commissioned audience/purpose boundaries.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Supplier [OPS-03.profile-readiness](../../cards/OPS-03/profile-readiness.md) | `direct:owner_readiness`: Consume only the readiness result for the selected route/profile, not source permission.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles разрешаются отдельно, как указано в parent contract. Номера групп и карточек не задают порядок.

## Назначенный нормативный контекст

Основа: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`. Полные selectors и accountable routes — [coverage.json](../../coverage.json), parent `OPS-06`. Эти ссылки не требуют чтения всех siblings. Читайте целиком каждый назначенный fragment и необходимые связанные contracts; mixed clause нельзя усечь до удобной части.

- **execute** — Direct result/preferred path for effect-release; selectors solution.implementation_steps[2] name the work and native owner seam.
  `solution.implementation_steps[2]`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
