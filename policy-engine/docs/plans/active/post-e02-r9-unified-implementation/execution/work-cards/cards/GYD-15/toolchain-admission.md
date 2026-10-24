# GYD-15.toolchain-admission — Допуск фактической платформы и toolchain

Группа: [G09 — Развёртывание, исполнители, хранилища и ресурсы](../../groups/G09.md). Родитель: [GYD-15](../../parents/GYD-15.md). Роль: `mechanism`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** N8 admits only a supported runtime/toolchain profile whose actual interpreter/platform/package identity is verified and bound to the selected contract.

**Предпочтительное решение.** Reuse the current Foundry/runtime platform and dependency-authority interfaces; bind the accepted identity to the exact executable, root, installation and cutoff receipt.

**Граница владельца.** The assigned GYD-15 lead traces/rebinds the existing native platform/toolchain producer, supported-profile source and reader, resolving exact paths/leases before dispatch and freezing them at accepted-source rebind; actual E02 acceptance remains the implementation gate. Actual runtime/install identity and supported-profile facts are separate evidence inputs; engineering allocation cannot certify them. Identity, runtime instance and package coordinates stay distinct. This card does not write subtree cutoff, receipt custody or data trust.

**Входы.** OPS-01.commissioning receipt for the selected runtime where its contract applies, including its exact build/config and effective-profile evidence; consume it, do not reissue it.; Current runtime/toolchain identity and installation read from the selected live environment and bound to the exact executable/root/install.; Supported profile and versioned contract from its accountable source.; Task-lead rebind of the existing producer/verifier/reader plus provenance and resolved cutoff receipt.; Fresh N8 consumer.

**Выход и consumer.** Persisted FA1 profile-admission/refusal result consumed by N8, bound to the exact runtime/install and applicable existing commissioning evidence; it does not issue commissioning or runtime identity.

**Что можно готовить независимо.** The assigned GYD-15 lead traces/rebinds the actual producer, verifier, supported-profile source and reader; freeze native paths/leases at accepted-source rebind after retaining the E02 dispatch gate.; Bind interpreter/platform/package identity to the exact executable/root/install/cutoff.; Preserve negative-only behavior for unsupported or unverified profiles.

**Где результат соединяется с другими.** At the existing N8 consumer, compose the FA1 supported-profile check with the applicable OPS-01 commissioning evidence and current identity read from the exact selected runtime/install. OPS-01 and the runtime producer remain the evidence owners; these are consumed interfaces, not new start edges or a second profile/identity registry. Join with the other three FA1 receipts; an institutionally supplied identity label alone cannot turn the gate green.

**Positive.** A supported verified runtime profile reaches N8 with actual runtime and installation identity bound.

**Distinguishing negative.** Missing/unsupported profile, copied or redirected runtime, swapped install or local self-attestation refuses.

**Matched removal.** Remove actual identity verification but keep profile labels; fresh N8 reader refuses.

**Граница контекста.** G09 deployment/platform boundary. Treat platform identity as institutionally supplied only when evidenced; its verification and supported-profile predicate must still be resolved/recomputed as applicable (P37/P38). No inferred trust from labels.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Accepted E02 source and task-scoped source rebind are the source/version basis consumed by this card; original P0-ACCEPT and parent dispatch semantics remain authoritative.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles разрешаются отдельно, как указано в parent contract. Номера групп и карточек не задают порядок.

## Назначенный нормативный контекст

Основа: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`. Полные selectors и accountable routes — [coverage.json](../../coverage.json), parent `GYD-15`. Эти ссылки не требуют чтения всех siblings. Читайте целиком каждый назначенный fragment и необходимые связанные contracts; mixed clause нельзя усечь до удобной части.

- **execute** — The toolchain-admission card owns this source-specific result or constraint and consumes other owners only through the named interface; no sibling rewrites that native owner.
  `solution.implementation_steps[2]`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
