# OPS-05.byte-release — Связать проверенные байты с reader и sink

Группа: [G09 — Развёртывание, исполнители, хранилища и ресурсы](../../groups/G09.md). Родитель: [OPS-05](../../parents/OPS-05.md). Роль: `consumer`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** The object/version verified for integrity is the object/version actually consumed, and integrity-dependent release waits for its required verification boundary.

**Предпочтительное решение.** Reuse the canonical CAS reader’s qualified immutable handle/version pin, read lease or verified bounded stream, and the actual effect/export/publication sink fence. No second archive, whole-object RAM copy or mandatory double scan.

**Граница владельца.** Any code write remains with the native CAS reader and actual consumer/sink owner; OPS-05 holds only its parent restore resource family. Resolve exact read/sink paths and semantic-owner overlap after E02 rebind; shared owners serialize regardless of card labels.

**Входы.** Exact resolved immutable object/version and selected integrity contract; restore-cut provenance only if this selected read consumes a restored object/version; LIF-05 current-use rights at protected read/release; Actual CAS fresh reader and irreversible effect/export/publication sink

**Выход и consumer.** Bound reader result and release-fence evidence for the selected object/use; consumed by the protected reader/effect sink, with no claim of full corpus integrity.

**Что можно готовить независимо.** Reader/stream contract and sink interface can be agreed independently. Composition requires verified bytes to remain bound through actual consumption; if integrity is end-of-stream, output stays provisional until then. Earlier chunk release requires an independently qualified chunk contract.

**Где результат соединяется с другими.** Join exact resolved object/version, current-use authorization and actual reader/sink. Consume restore-cut provenance only for an object/version admitted through that restore cut; ordinary non-restored reads need no restore receipt. Selected chunk-level release is permitted only for independently verified units and cannot claim whole-stream integrity.

**Positive.** Exact stable object supports the permitted use; bounded buffer/read work meets the selected profile and sink receives output only after the required integrity boundary.

**Distinguishing negative.** Locator/version substitution, mutated later chunk, corrupt final chunk or an integrity-dependent partial egress cannot authorize/use the object; unaffected unrelated output need not wait.

**Matched removal.** Remove verifier-to-actual-reader binding or release fence but retain hash/manifest/error markers; substitution and premature-egress probes fail.

**Граница контекста.** One byte-integrity property crosses the existing CAS reader and sink; end-of-stream vs qualified chunk semantics remain explicit. P31/P32/P38 require the single real intake and actual release choke point.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Each child consumes the accepted E02 source/rebound owner and actual supported boundary; this is the parent dispatch contract, not a new peer dependency.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [OPS-03.profile-readiness](../../cards/OPS-03/profile-readiness.md) | `direct:owner_readiness`: Use selected DB/CAS/profile readiness where the protected restore/read path requires it.<br>Source: `task.depends_on[1]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [LIF-05](../../parents/LIF-05.md) | `direct:owner_readiness; conditional_acceptance_requirements:composition`: Consume current rights, retention/deletion classification and sink-use decisions; OPS-05 does not write those decisions.<br>Source: `task.depends_on[3]`; `task.conditional_acceptance_requirements[0]`.<br>Условия: original direct relation; source stage rules govern; Restore enables current/protected claim or publication reads |
| Composition output (не start gate) [OPS-05.restore-cut](../../cards/OPS-05/restore-cut.md) | Only when the selected protected read consumes an object/version admitted through this restore cut. Ordinary non-restored reads still require current LIF-05 rights and actual CAS reader/sink binding, without a restore receipt. |
| Composition output (не start gate) [OPS-05.retained-uses](../../cards/OPS-05/retained-uses.md) | When protected use of a retained/restored representation requires the selected rights/retention decision. Current-use authorization for ordinary non-restored reads still comes from the canonical LIF-05 owner, without making restore-specific reconciliation mandatory. |
| Composition output (не start gate) [OPS-05.independent-copy-repair](../../cards/OPS-05/independent-copy-repair.md) | Only when this reader consumes a repaired version, bind the exact repair receipt/version through the actual read. Ordinary healthy reads need no repair receipt. |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `OPS-05`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **binding** — Binding scope, authority, migration, time, input, or lifecycle constraint for byte-release; selectors solution.composition_contracts[4] remain load-bearing.
  `solution.composition_contracts[4]`
- **join** — Distinguishing behavior, consumer surface, or acceptance evidence for byte-release; selectors task.acceptance_steps[7], task.r17_extension.quality_cases[3], solution.acceptance_discriminators[5] are checked at its actual reader/sink.
  `task.acceptance_steps[7]`; `task.r17_extension.quality_cases[3]`; `solution.acceptance_discriminators[5]`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
