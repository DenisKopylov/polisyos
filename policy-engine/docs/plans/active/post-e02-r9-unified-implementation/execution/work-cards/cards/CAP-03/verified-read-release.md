# CAP-03.verified-read-release — Bind verification to the bytes the reader actually consumes

Группа: [G09 — Развёртывание, исполнители, хранилища и ресурсы](../../groups/G09.md). Родитель: [CAP-03](../../parents/CAP-03.md). Роль: `verification`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** No protected effect/export escapes before the selected integrity contract has verified the consumed bytes.

**Предпочтительное решение.** Resolve ArtifactRef/ArtifactManifest to the actual read handle, version and chunks; verify the bytes the consumer will read and release only after that exact verification remains bound to the admitted root. A digest or separate pre-read check cannot stand in for the consumed bytes. Anchors: core/artifacts/manifest.py:ArtifactRef/ArtifactManifest; runtime/quality/acquisition_executor.py:revalidate_admission_passport.

**Граница владельца.** Existing CAS/object-store reader, version-pin/lease and bounded-streaming owner. Parent native lease family: `write:acquisition-action`, `write:acquisition-passport`. Exact post-E02 paths/overlap are unresolved; do not infer sibling disjointness or create a child lease. Root binds the actual path/lease before writes; cards sharing a native family serialize there.

**Входы.** Exact manifest/version, actual read handle/chunks, integrity rule and release boundary.

**Выход и consumer.** Pinned verified reader or provisional/blocked result with bounded integrity evidence.

**Что можно готовить независимо.** Rebind selected backend read/version pin and resource limits after E02.

**Где результат соединяется с другими.** Join actual CAP-03 fresh-use decision at every protected reader/effect.

**Positive.** Fresh reader consumes the bound version and only releases outputs at the supported verification granularity.

**Distinguishing negative.** Locator swap, mutated late chunk, or corrupt final chunk blocks dependent output.

**Matched removal.** Remove verifier-to-reader binding but keep manifest/hash markers; substitution/premature-egress probe fails.

**Граница контекста.** Root admission is distinct from current rights at sinks, method-specific replay identity, and binding verification to bytes actually read. The preferred-solutions card carries method/stream acceptance beyond the core library property; keep those native owners and compose them rather than giving CAP-03 a new universal mechanism. This is one bounded property view; parent source pins, stage/dispatch, conditional acceptance and mandatory companions remain inherited.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Accepted source/path rebind where used; original stage gate stays inherited.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [CAP-02](../../parents/CAP-02.md) | `direct:owner_readiness`: Consume exact root/read; cost-basis consumes planner artifact.<br>Source: `task.depends_on[1]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [LIF-05](../../parents/LIF-05.md) | `direct:owner_readiness`: Consume shared rights/reservation at relevant effect; no local counter.<br>Source: `task.depends_on[3]`.<br>Условия: original direct relation; source stage rules govern |
| Composition output (не start gate) [CAP-03.root-admission](../../cards/CAP-03/root-admission.md) | Consume only for the exact composition described here: Join actual CAP-03 fresh-use decision at every protected reader/effect. This link is not an unconditional all-of or preparation gate. |
| Composition output (не start gate) [CAP-03.fresh-sink-rights](../../cards/CAP-03/fresh-sink-rights.md) | Consume only for the exact composition described here: Join actual CAP-03 fresh-use decision at every protected reader/effect. This link is not an unconditional all-of or preparation gate. |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `CAP-03`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **execute** — Bind verification to actual read handle/version/chunks and release point; substitution/corruption blocks output.
  `task.acceptance_steps[7]`; `solution.composition_contracts[7]`; `solution.acceptance_discriminators[7]`
- **binding** — Read/version quality reference does not claim filesystem parity.
  `task.r17_extension.quality_cases[0]`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
