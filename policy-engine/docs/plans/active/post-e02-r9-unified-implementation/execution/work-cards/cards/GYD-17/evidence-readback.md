# GYD-17.evidence-readback — Свежо проверить CAS артефакты и measurement root

Группа: [G10 — Независимые проверки и качество свидетельств](../../groups/G10.md). Родитель: [GYD-17](../../parents/GYD-17.md). Роль: `verification`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Fresh downstream consumers resolve the complete artifact graph, recompute byte hashes/provenance and obtain authorized measurement-root validation or exact honest ceiling.

**Предпочтительное решение.** Wire or extend the existing Canonical CAS resolver, actual artifact consumers and appointed evidence owner; preserve its typed contract and status/time/provenance semantics.

**Граница владельца.** Within GYD-17's native canonical lease family write:exact-path/{canonical_repo_path}. Exact paths and overlap remain unresolved until accepted E02 lease resolution; do not presume disjointness. Canonical CAS resolver, actual artifact consumers and appointed evidence owner.

**Входы.** production-trigger CAS objects; rule/schema/provenance/input refs; measurement-root evidence

**Выход и consumer.** Fresh readback and evidence-owner root/ceiling receipt

**Что можно готовить независимо.** Preparation may proceed before freeze; final execution follows the parent’s canonical stage and conditional acceptance. No new gate is introduced; resolve accepted E02 source and exact lease before writes.

**Где результат соединяется с другими.** Fresh consumer: actual downstream WorkspaceContract/SearchLedger/FrontierSnapshot/SearchExitContract consumers. Byte integrity, semantic validity and evidence authority are distinct claims.

**Positive.** All named records resolve from the production CAS run with expected identity and hash.

**Distinguishing negative.** Route-only/refusal-only, stale version, missing root or unresolved bytes stays not_established.

**Matched removal.** Remove root, CAS reference or consumer while keeping markers; fresh readback fails.

**Граница контекста.** Byte integrity, semantic validity and evidence authority are distinct claims.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [FINAL-REVIEW.independent-review](../../cards/FINAL-REVIEW/independent-review.md) | `acceptance:composition`: FINAL-REVIEW consumes the fully composed outputs at the canonical composition acceptance stage. It does not block independent preparation or add a leaf/preparation gate.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: selected parent composed claim; not a new preparation dependency |
| Composition output (не start gate) [GYD-17.production-trigger](../../cards/GYD-17/production-trigger.md) | Consume only for the exact composition described here: Fresh consumer: actual downstream WorkspaceContract/SearchLedger/FrontierSnapshot/SearchExitContract consumers. Byte integrity, semantic validity and evidence authority are distinct claims. This link is not an unconditional all-of or preparation gate. |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles разрешаются отдельно, как указано в parent contract. Номера групп и карточек не задают порядок.

## Назначенный нормативный контекст

Основа: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`. Полные selectors и accountable routes — [coverage.json](../../coverage.json), parent `GYD-17`. Эти ссылки не требуют чтения всех siblings. Читайте целиком каждый назначенный fragment и необходимые связанные contracts; mixed clause нельзя усечь до удобной части.

- **execute** — Parent end-to-end property, positive/adversary/removal and surface resolve at actual fresh consumer; failure stays non-authority.
  `task.deliverable`; `task.positive`; `task.adversarial`; `task.removal`; `task.surface`; `task.rollback`; `task.migration`
- **join** — Schema/rule, actual consumers/generated family, migration, journal and review are required companions.
  `task.mandatory_companions[0]`; `task.mandatory_companions[1]`; `task.mandatory_companions[2]`; `task.mandatory_companions[3]`; `task.mandatory_companions[4]`
- **execute** — Final execution requires real trigger, durable named artifacts, canonical hashes and evidence-owner root/ceiling readback.
  `task.final_execution_property`
- **execute** — Read all actual artifacts at real consumers and have appointed evidence owner validate root or exact ceiling.
  `solution.implementation_steps[2]`; `solution.implementation_steps[3]`
- **binding** — One invocation and exact-identity reuse are resource semantics; missing root/CAS/readback fails closed.
  `solution.free_grow.resource_behavior`
- **binding** — Failed/refusal records remain partial diagnostic, non-authority evidence at the fresh readback; missing source/persistence keeps V2 UNRUN/not_established.
  `solution.migration_and_rollback`
- **binding** — Digest is byte binding only; same-code replay is not a second loop; positive/adversary/removal, honest-ceiling deviation and new-consumer readback are decided here.
  `solution.composition_contracts[1]`; `solution.composition_contracts[2]`; `solution.acceptance_discriminators[0]`; `solution.acceptance_discriminators[1]`; `solution.acceptance_discriminators[2]`; `solution.deviation_triggers[0]`; `solution.deviation_triggers[1]`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
