# GYD-15.data-trust — Политика доверия к production data

Группа: [G06 — Допустимость, полномочия и квалифицированные решения](../../groups/G06.md). Родитель: [GYD-15](../../parents/GYD-15.md). Роль: `consumer`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Production-data use is admitted only for the exact resolved source, rights/trust evidence, purpose, audience and tenant/time scope verified by the native owner.

**Предпочтительное решение.** Reuse existing authority interfaces and production builder/N8 consumer; resolve purpose/role/root/content and tenant/time/revocation without creating blanket signer policy.

**Граница владельца.** The assigned GYD-15 lead traces/rebinds the existing accountable source-trust evidence interface and current N8 admission reader, resolving native paths/leases before dispatch and freezing them at accepted-source rebind; actual E02 acceptance remains required for implementation. Existing production-data trust and source-right owners retain their authority: GYD-15 is an N8 admission consumer/composition, not a source-grant writer or trust-root issuer. Missing institutional grants/signer/role/root facts stay typed-empty; do not infer rights from byte integrity, cutoff, toolchain admission or adjacency.

**Входы.** Exact resolved production data from its canonical source/custody path.; Existing scope/content-bound source-use grant or decision and trust/root evidence from the accountable owners; consume OPS-06 read-scope/effect-release evidence when that contract covers this operation, and do not write or refresh a source grant here.; Applicable technical trust-root/generation verification from its existing owner, including OPS-11.trust-root evidence only where that contract applies.; Purpose, audience, role, tenant, validity and revocation scope as actually evidenced by competent sources.; Other FA1 receipts for the N8 join.

**Выход и consumer.** FA1-scoped N8 admission composition/refusal bound to the exact consumed data and existing source-use/trust evidence; it is not a source grant, grant ledger or trust-root act.

**Что можно готовить независимо.** The assigned GYD-15 lead traces/rebinds the existing source-trust evidence interface and current N8 admission consumer; freeze exact path/lease at accepted-source rebind, preserving the E02 dispatch gate. Do not create a source-grant producer.; Resolve institutional purpose/role/root/tenant/time facts as separate evidence; consume the accountable source-right decision and do not create a source-grant writer or signer act.; Route the FA1-scoped composition through the current N8 admission consumer.

**Где результат соединяется с другими.** The current N8 admission consumer composes this FA1-scoped result from the existing source-right/grant and trust evidence; GYD-15 does not write or refresh those grants. OPS-06 or OPS-11 evidence is consumed only when the respective existing contract applies, with no new start edge. N8 also requires the independently reconciled cutoff, canonical-CAS receipt resolution and verified toolchain result.

**Positive.** Independently verified source/rights/trust evidence admits only its permitted use for the bound data and scope.

**Distinguishing negative.** Missing, self-attested, unverifiable, revoked or wrong-purpose/tenant data remains non-authoritative.

**Matched removal.** Remove source/trust binding but keep digest and manifest markers; the N8 consumer refuses authority-bearing use.

**Граница контекста.** G06 admissibility. The task lead owns active engineering discovery/rebind of the internal owner paths; a missing path stays absent/unallocated, while missing institutional evidence stays typed-empty/refused. Keep observed artifacts and FR-AUTH-01 prose non-authoritative; apply independence only where FA1 explicitly requires it.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Accepted E02 source and task-scoped source rebind are the source/version basis consumed by this card; original P0-ACCEPT and parent dispatch semantics remain authoritative.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles разрешаются отдельно, как указано в parent contract. Номера групп и карточек не задают порядок.

## Назначенный нормативный контекст

Основа: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`. Полные selectors и accountable routes — [coverage.json](../../coverage.json), parent `GYD-15`. Эти ссылки не требуют чтения всех siblings. Читайте целиком каждый назначенный fragment и необходимые связанные contracts; mixed clause нельзя усечь до удобной части.

- **execute** — The data-trust card owns this source-specific result or constraint and consumes other owners only through the named interface; no sibling rewrites that native owner.
  `solution.implementation_steps[3]`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
