# OPS-05.independent-copy-repair — Восстановить объект из проверенной независимой копии

Группа: [G09 — Развёртывание, исполнители, хранилища и ресурсы](../../groups/G09.md). Родитель: [OPS-05](../../parents/OPS-05.md). Роль: `mechanism`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** A corrupt/unreadable retained object is repaired from an independently verified permitted copy when available; lack of a qualified independent source remains explicit and never produces a false healed state.

**Предпочтительное решение.** Extend the existing canonical CAS/archive recovery owner: resolve the selected independent source, verify content and actual failure-domain separation, copy/repair through bounded staging, atomically publish the verified immutable version via the native mechanism, then verify by a fresh reader. Preserve damaged-version evidence and lineage; no in-place history rewrite, second archive, full-object RAM copy or invented universal storage backend.

**Граница владельца.** The existing CAS/archive writer owns all repair mutations and version publication. This card commissions its missing native extension after E02; restore-cut and byte-release consume its output and do not repair independently. Root binds exact shared writer leases and serializes overlapping writes; independent source qualification can proceed in parallel.

**Входы.** Exact damaged object/version and expected integrity basis; permitted independent source copy plus verified failure-domain/provenance evidence; applicable LIF-05 rights and selected backend limits. An unverified mirror or same-failure-domain copy is not automatically independent.

**Выход и consumer.** Persisted repair receipt binding damaged version, verified source/version, independence basis, repair operation, new immutable version and fresh-reader result; or typed no-qualified-copy/refusal. Existing restore and actual read/sink owners consume the exact result.

**Что можно готовить независимо.** Resolve native repair APIs, immutable version publication and independent-copy evidence before mutation. If no qualified copy is available, implement and prove the honest unavailable path while retaining the unsatisfied positive input; do not manufacture copies or authority.

**Где результат соединяется с другими.** restore-cut consumes the repaired version only when that selected restore needed repair; byte-release binds it to actual consumed bytes and current-use rights. Ordinary healthy reads and unrelated restores need no repair receipt. Repair is not currentness/rights reconciliation.

**Positive.** Corrupt selected primary plus independently verified permitted copy yields a verified repaired immutable version; fresh actual reader consumes it with bounded memory and explicit source lineage.

**Distinguishing negative.** Rehashed corrupt primary, wrong object, unqualified or same-failure-domain copy, revoked copy right, failed final integrity or interrupted publication cannot be reported healed. No qualified source stays unavailable without rewriting old evidence.

**Matched removal.** Keep repair/hash/status markers but remove independent-source qualification or final verified-version publication: fresh reader must reject the purported repair or reveal the corrupt/substituted bytes.

**Граница контекста.** One repair transaction/result under one existing writer; schema migration, retained-use permission, restore continuity and output emission remain separate bounded cards. Independent-copy selection is scoped to the actual failure model, not a globally enumerated replica taxonomy.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Each child consumes the accepted E02 source/rebound owner and actual supported boundary; this is the parent dispatch contract, not a new peer dependency.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [OPS-03.profile-readiness](../../cards/OPS-03/profile-readiness.md) | `direct:owner_readiness`: Use selected DB/CAS/profile readiness where the protected restore/read path requires it.<br>Source: `task.depends_on[1]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [LIF-05](../../parents/LIF-05.md) | `direct:owner_readiness; conditional_acceptance_requirements:composition`: Consume current rights, retention/deletion classification and sink-use decisions; OPS-05 does not write those decisions.<br>Source: `task.depends_on[3]`; `task.conditional_acceptance_requirements[0]`.<br>Условия: original direct relation; source stage rules govern; Restore enables current/protected claim or publication reads |
| Supplier [LIF-05](../../parents/LIF-05.md) | `direct:owner_readiness; conditional_acceptance_requirements:composition`: Conditional current/protected restore acceptance joins the same rights/history output; no unrelated claim domain or global wait.<br>Source: `task.depends_on[3]`; `task.conditional_acceptance_requirements[0]`.<br>Условия: original direct relation; source stage rules govern; Restore enables current/protected claim or publication reads |
| Composition output (не start gate) [OPS-05.byte-release](../../cards/OPS-05/byte-release.md) | When repaired bytes are actually released, preserve the verified-version binding through the existing reader/sink; no release on a repair marker alone. |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `OPS-05`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.



### Обязанности внутри составных fragments

- `task.r17_extension.requirement` — Independent-copy repair and bounded cold retrieval obligation; parent retains the aggregate multi-property criterion and this card supplies the repair-specific output. (primary accountability остаётся в coverage; это конкретный подрезультат, не второй writer).
- `task.r17_extension.positive` — Corruption repair names a genuinely independently verified source; parent retains the aggregate multi-property criterion and this card supplies the repair-specific output. (primary accountability остаётся в coverage; это конкретный подрезультат, не второй writer).
- `task.r17_extension.adversarial` — Do not rehash a corrupt primary or treat same-failure-domain copies as independent; parent retains the aggregate multi-property criterion and this card supplies the repair-specific output. (primary accountability остаётся в coverage; это конкретный подрезультат, не второй writer).
- `task.r17_extension.removal` — Fresh reader must distinguish removed repair/source qualification; parent retains the aggregate multi-property criterion and this card supplies the repair-specific output. (primary accountability остаётся в coverage; это конкретный подрезультат, не второй writer).
- `task.r19_extension.question_slices[2]` — Only if the selected forward repair includes corrupt/missing retained-object recovery from an independent copy, supply that bounded object-repair result under the existing CAS/archive writer. This does not implement schema migration, repair a vulnerable executable or satisfy general forward-repair compatibility; schema-directions and the actual native patch owner retain those obligations. (primary accountability остаётся в coverage; это конкретный подрезультат, не второй writer).

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
