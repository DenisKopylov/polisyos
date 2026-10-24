# OPS-05: пример меньших назначений R25

Форма: `split`. Это проект границ будущей выдачи, не implementation grant или новая приёмка. Основа — R24 `f8e2c66edf6b56a5436e696e669bfe690f68e58b` и корректировки R25; реализация только после E02 acceptance.

[Правила декомпозиции](../README.md) · [Формат рабочего пакета](../work-packet.md) · [Канонический task](../../../tasks.json) · [Preferred solution](../../../solutions/10-operations.md#OPS-05)

## Почему такая граница

The card currently carries three independently falsifiable properties: directional schema compatibility, a cross-store/history restore join, and binding verified bytes to the actual consuming reader and release sink. Keep them as property slices under the existing persistence/read owners; migration, restored state, rights/history, and actual-byte verification must still join before protected use.

## Общие условия родителя

Названные ниже свойства сохраняют все применимые original criteria, extensions, status/authority/time/rights и mandatory companions. Root/lead перед назначением раскладывает **каждый** source clause в существующий coverage journal; этот пример не заменяет такую раскладку. Один actual semantic owner и write lease сохраняются. Независимая подготовка возможна по согласованному интерфейсу; composition и protected use требуют настоящих supplier outputs.

План не даёт права выбирать только удобные profiles или считать unknown applicability исключением. Условный join включается по фактическому контракту/claim. Родитель требует полный selected denominator и fresh end-to-end witness; локальные PASS не суммируются в closure.

## OPS-05.MIGRATION-DIRECTIONS — Directional schema and reader compatibility

**Свойство.** Every selected reader/writer/schema/rule direction can consume the actual persisted representation before rollout or rollback.

**Граница и owner.** ControlPlaneStore migration owner; runtime-state and CAS schema owners remain separate. This slice proves version compatibility, not recovery.

**Входы.** Actual supported readers and writers; State dialects and schema/rule versions; Selected API/worker/profile directions

**Результат.** Versioned expand/dual-read-write/backfill/contract milestones; Direction-specific compatibility decision

**Подготовка.** Enumerate actual selected directions and preserve the established tenant/RLS migration order; use N-1 only where the real matrix proves it.

**Composition join.** OPS-04 consumes worker/API direction; OPS-10 or OPS-12 readers join only when that tier is selected.

**Полезный positive.** A supported mixed reader/writer direction reads the real old/new state and remains usable through the selected rollback direction.

**Различающий negative.** New bytes exist while an actually retained strict old reader cannot decode them; an N-1 label does not authorize rollout.

**Matched removal.** Remove the real read/round-trip check and keep version markers: the fresh restore/rollback reader must refuse or quarantine.

## OPS-05.RESTORE-JOIN — Reconcile the restored control, CAS, rights, and claim frontier

**Свойство.** One selected restore cut is admitted only after required DB/CAS state, allowed retained representation, post-snapshot rights, and material claim/publication history reconcile.

**Граница и owner.** Existing replay-or-restore and ControlPlaneStore owners join DB/PITR, exact CAS mount or bucket/prefix, object/version inventory, LIF-05 retention decisions, LIF-02 claim history, and an allowed continuity witness outside the rollback closure. A receipt, subsystem restore, or bounded sample alone is not complete recovery.

**Входы.** Pinned DB backup/timeline/WAL and accepted control high-water; Exact CAS root/mount/options/topology and required object/version set; Rights/revocation and claim withdrawal/correction/reissue history after the cut; Retention/deletion decisions and independently retained continuity witness

**Результат.** Quarantined restore receipt joining the actual cuts and replay floors; Per-scope fresh-read eligibility or explicit historical/limited/unavailable outcome

**Подготовка.** Bind the selected physical stores, backup method, required representation/use, RPO/RTO and permitted recovery set; distinguish an erased dependency from unexpected loss of required retained bytes.

**Composition join.** Require OPS-10 remote or OPS-12 offline adapter evidence only when selected, LIF-05/LIF-07 actual-use rights and derivative basis, LIF-02 material claim history, plus OPS-05.ACTUAL-BYTES before fresh protected read. Do not require a raw replay for a separately sufficient lawful derivative; do not restore a withdrawn claim.

**Полезный positive.** Restore the selected DB/CAS cut, replay newer revocations and material withdrawals, then allow only the fresh read supported by retained bytes or a sufficient permitted derivative basis; unrelated proven scopes may proceed.

**Различающий negative.** Partial cut, stale revoked copy, missing required history/witness, corrupt required object, or post-reconcile withdrawal keeps only the affected scope quarantined; verified erasure does not authorize reconstructing raw input.

**Matched removal.** Remove rights/claim frontier reconciliation while preserving hashes and restore markers: the fresh protected consumer must detect false currentness.

## OPS-05.ACTUAL-BYTES — Bind verification to bytes actually consumed

**Свойство.** The object/version verified for integrity is the same object/version consumed, and integrity-dependent release waits for the required verification boundary.

**Граница и owner.** Existing qualified immutable handle, version pin, read lease, or verified bounded stream in the native CAS reader and actual consumer/effect sink; not a second archive or full-object RAM copy.

**Входы.** Resolved owner/version and current-use rights; Integrity witness bound to the stable handle or stream; Actual processing, publication, egress, and irreversible-effect sinks

**Результат.** Consumer-bound read witness; Release-allowed or provisional/blocked outcome tied to the verified bytes

**Подготовка.** Select the profile's actual bounded read contract; if only final-chunk integrity is known at end-of-stream, keep dependent outputs provisional until then.

**Composition join.** Join current rights/fences at use and OPS-05.RESTORE-JOIN for restored data; a qualified chunk contract can release only its proven units.

**Полезный positive.** Fresh reader consumes the pinned verified version and releases only after its supported scope is verified.

**Различающий negative.** Locator/version changes after verification or a corrupt final chunk is streamed while a protected egress/publication sink receives partial output.

**Matched removal.** Drop verifier-to-reader or final release binding but retain successful hash/manifest markers: the actual substitution/early-release probe fails.

## Что надо материализовать после E02

Exact candidate/tree и contract pins; полный clause-to-result route; accepted supplier refs; actual read/write/semantic/generated leases; native implementation and consumer paths; полные deciding outputs и parent integration witness. Пока это неизвестно, чтение/подготовка продолжаются, affected implementation/acceptance не выдаётся под выдуманный default.

Новая substantive clause требует delta review затронутого контекста; неизменные siblings не перечитывают весь пакет. Смена исполнителя получает явный checkpoint, действующий контракт и остаток — не память предыдущего чата.

Pattern pass: P01/P02/P13/P27/P29/P35/P37/P38/P39. Все проверки выше — будущие acceptance signals; runtime execution UNRUN.
