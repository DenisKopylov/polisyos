# OPS-11.archive-transfer — Передавать архивную обязанность с проверенным evidence

Группа: [G07 — Долгая custody: актуальность, права и переиздание](../../groups/G07.md). Родитель: [OPS-11](../../parents/OPS-11.md). Роль: `consumer`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** A successor’s preservation duty is counted only after actual acceptance, and any renewal claim is based on retrieved/verified retained bytes under a selected proven protocol.

**Предпочтительное решение.** Reuse OPS-05/LIF-05 storage, recovery, copy, retention and lawful-use owners. OPS-11 supplies trust evidence and accepted-duty transfer; no archive copy/renewal scheduler, retention policy or perpetual duty is created here.

**Граница владельца.** OPS-11 uses its parent `write:exact-path/{canonical_repo_path}` only for succession/duty evidence. OPS-05 owns retrieval/restore and LIF-05 owns rights/copies/retention; exact shared archive/trust lease must be resolved after E02 rebind.

**Входы.** OPS-05 exact retained archive/cold retrieval and verification result; LIF-05 allowed retention/copy and current-use rights; Independent trust/successor evidence from `trust-root`; Actual recipient’s acceptance, duty scope/cadence/resource/cutoff; Fresh protected archive reader

**Выход и consumer.** Accepted archive-duty transfer and content-bound renewal evidence, consumed by existing archive reader and custody owner; no claim from upload/timestamp alone.

**Что можно готовить независимо.** Transfer interface can be prepared independently; renewal acceptance waits for actual retrieval, selected protocol and successor intake. A no-change review is evidence only for its declared coverage/cadence.

**Где результат соединяется с другими.** OPS-05 retains/retrieves bytes, LIF-05 decides lawful copies/use, OPS-11 verifies trust and accepted future duty. Historical evidence validity and current-use permission remain separate.

**Positive.** Admitted successor accepts exact bounded archive duties; retrieved verified bytes support the selected renewal/custody claim and history is retained.

**Distinguishing negative.** Late timestamp repairing missing history, self-signed successor, upload without retrieval, unaccepted duty or perpetual promise without owner/budget cannot pass.

**Matched removal.** Remove independent succession/renewal verification or recipient acceptance but keep status fields; the fresh archive consumer refuses.

**Граница контекста.** Third property is evidence/duty transfer over existing archive owner, not a second archive. Work home G07 because ongoing preservation, succession and rights are the semantic axis.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Each owner/read path rebinds to the accepted source; preserve parent acceptance stage and external-input classification.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Supplier [OPS-05](../../parents/OPS-05.md) | `direct:owner_readiness`: Consume actual retained archive retrieval/restore and verified representation result.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Supplier [LIF-04](../../parents/LIF-04.md) | `direct:owner_readiness`: LIF-04 remains durable duty/trigger owner; OPS-11 supplies accepted owner/scope evidence only.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Supplier [LIF-08](../../parents/LIF-08.md) | `acceptance:composition`: Acceptance dependency where selected reader/migration compatibility affects archive transfer; use actual producer output at composition.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: selected parent composed claim; not a new preparation dependency |
| Composition output (не start gate) [OPS-11.trust-root](../../cards/OPS-11/trust-root.md) | Only for the selected same-scope composition described by this card: OPS-05 retains/retrieves bytes, LIF-05 decides lawful copies/use, OPS-11 verifies trust and accepted future duty. Historical evidence validity and current-use permission remain separate. Independent output production/preparation remains allowed; the original parent join reconciles all required outcomes without making this list an all-of. |
| Composition output (не start gate) [OPS-11.currentness-duty](../../cards/OPS-11/currentness-duty.md) | Only for the selected same-scope composition described by this card: OPS-05 retains/retrieves bytes, LIF-05 decides lawful copies/use, OPS-11 verifies trust and accepted future duty. Historical evidence validity and current-use permission remain separate. Independent output production/preparation remains allowed; the original parent join reconciles all required outcomes without making this list an all-of. |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles разрешаются отдельно, как указано в parent contract. Номера групп и карточек не задают порядок.

## Назначенный нормативный контекст

Основа: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`. Полные selectors и accountable routes — [coverage.json](../../coverage.json), parent `OPS-11`. Эти ссылки не требуют чтения всех siblings. Читайте целиком каждый назначенный fragment и необходимые связанные contracts; mixed clause нельзя усечь до удобной части.

- **binding** — Binding scope, authority, migration, time, input, or lifecycle constraint for archive-transfer; selectors task.r17_extension.delivery_slices[0], task.r17_extension.delivery_slices[2], task.r17_extension.product_verification, task.r19_extension.status, task.r19_extension.product_verification, task.r19_extension.composition_contract_ref remain load-bearing.
  `task.r17_extension.delivery_slices[0]`; `task.r17_extension.delivery_slices[2]`; `task.r17_extension.product_verification`; `task.r19_extension.status`; `task.r19_extension.product_verification`; `task.r19_extension.composition_contract_ref`
- **join** — Distinguishing behavior, consumer surface, or acceptance evidence for archive-transfer; selectors task.r17_extension.adversarial are checked at its actual reader/sink.
  `task.r17_extension.adversarial`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
