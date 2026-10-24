# GYD-27.ring2-refusal — Отказать Ring-2 без trusted verifier

Группа: [G06 — Допустимость, полномочия и квалифицированные решения](../../groups/G06.md). Родитель: [GYD-27](../../parents/GYD-27.md). Роль: `verification`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Construction/admission resolves exact proof content and trusted verifier provenance; self-attestation cannot construct Ring-2.

**Предпочтительное решение.** Wire or extend the existing trusted-verifier construction/admission boundary; preserve its typed contract and status/time/provenance semantics.

**Граница владельца.** Within GYD-27's native canonical lease family write:exact-path/{canonical_repo_path}. Exact paths and overlap remain unresolved until accepted E02 lease resolution; do not presume disjointness. Existing trusted-verifier construction/admission boundary.

**Входы.** proof bytes and scope; trusted verifier appointment/provenance; construction contract

**Выход и consumer.** Persisted Ring-2 admission/refusal result

**Что можно готовить независимо.** Preparation may proceed before freeze; final execution follows the parent’s canonical stage and conditional acceptance. No new gate is introduced; resolve accepted E02 source and exact lease before writes.

**Где результат соединяется с другими.** Fresh consumer: actual constructor/admission consumer. Authority provenance is resolved and frozen at admission.

**Positive.** Supported trusted proof reaches intended admission.

**Distinguishing negative.** Agent-created proof or forged/self-validating verifier is refused.

**Matched removal.** Remove trusted verifier evidence but retain proof/status marker; constructor refuses.

**Граница контекста.** Authority provenance is resolved and frozen at admission.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Accepted event-role, trusted-verifier and VOI-basis criteria are consumed separately.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles разрешаются отдельно, как указано в parent contract. Номера групп и карточек не задают порядок.

## Назначенный нормативный контекст

Основа: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`. Полные selectors и accountable routes — [coverage.json](../../coverage.json), parent `GYD-27`. Эти ссылки не требуют чтения всех siblings. Читайте целиком каждый назначенный fragment и необходимые связанные contracts; mixed clause нельзя усечь до удобной части.

- **execute** — Validate Ring-2 proof at construction/admission against trusted verifier provenance.
  `solution.implementation_steps[2]`
- **binding** — New authority role/verifier needs typed provenance; caller/LLM cannot assign it.
  `solution.free_grow.extension_boundary`
- **execute** — Resolve, content-bind and verify provenance at construction.
  `solution.composition_contracts[1]`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
