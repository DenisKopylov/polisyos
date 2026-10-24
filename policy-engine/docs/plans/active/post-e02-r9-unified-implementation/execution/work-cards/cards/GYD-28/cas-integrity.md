# GYD-28.cas-integrity — Проверить CAS bytes, refs и lifecycle

Группа: [G09 — Развёртывание, исполнители, хранилища и ресурсы](../../groups/G09.md). Родитель: [GYD-28](../../parents/GYD-28.md). Роль: `verification`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Canonical bytes/digest, dedup/ref, tamper, GC retention and dereference are recomputed at actual reader.

**Предпочтительное решение.** Wire or extend the existing CAS object and dereference owner; preserve its typed contract and status/time/provenance semantics.

**Граница владельца.** Within GYD-28's native canonical lease family write:exact-path/{canonical_repo_path}. Exact paths and overlap remain unresolved until accepted E02 lease resolution; do not presume disjointness. Existing CAS object and dereference owner.

**Входы.** canonical output refs; CAS bytes/digest; dedup/retention behavior

**Выход и consumer.** Persisted integrity/dereference receipt

**Что можно готовить независимо.** Preparation may proceed before freeze; final execution follows the parent’s canonical stage and conditional acceptance. No new gate is introduced; resolve accepted E02 source and exact lease before writes.

**Где результат соединяется с другими.** Fresh consumer: actual CAS object reader. CAS integrity is not authority.

**Positive.** Digest matches bytes and referenced blobs survive valid GC/deref.

**Distinguishing negative.** Missing/tampered/lost ref fails despite manifest presence.

**Matched removal.** Alter/delete referenced bytes while retaining digest marker; reader refuses.

**Граница контекста.** CAS integrity is not authority.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Accepted artifact scope and F2 criteria consumed separately by scan, CAS lifecycle and authority reader.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `GYD-28`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **binding** — New storage boundary requires typed adapter/conformance.
  `solution.free_grow.extension_boundary`

### Обязанности внутри составных fragments

- `task.r19_extension.question_slices[0]` — Resolve the exact canonical CAS bytes/root and recompute byte integrity, dedup/ref, tamper, retention, and dereference at the actual reader; digest alone is not the claimed transform. (primary accountability остаётся в coverage; это конкретный подрезультат, не второй writer).

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
