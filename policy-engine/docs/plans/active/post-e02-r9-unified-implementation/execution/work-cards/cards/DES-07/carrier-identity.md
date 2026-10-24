# DES-07.carrier-identity — Установить права, базу и личность носителя

Группа: [G08 — Документы, интерфейсы и понятные человеку результаты](../../groups/G08.md). Родитель: [DES-07](../../parents/DES-07.md). Роль: `input`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** An imported/edited carrier resolves to exact permitted bytes or reference, parent/base edition, rights and mapped/unmapped spans; stripped-ID or stale text remains a distinct unbound revision.

**Предпочтительное решение.** Reuse DES-06’s versioned document schema and existing carrier/storage rights. Preserve original human-authored bytes or exact permitted reference, establish parent/base/CAS identity and deterministic AST/span/cell alignment before semantic routing; do not treat hashes as arbitrary semantic equivalence.

**Граница владельца.** DES-07 owns only the carrier/import route in write:policy-document-owner and write:artifact-document-route lease families after exact rebind. DES-06 is the shared schema/render writer and DES-07 consumes its versioned interface; this does not presume shared paths disjoint. Existing LIF/storage rights owners decide processing/retention; this input card cannot grant them.

**Входы.** DES-06 actual edition/schema and an actual UI revision or edited DOCX carrier; explicit human mapping only for materially ambiguous alignment.; Existing storage/processing/retention rights and parent/base refs; unknown rights mean no retained/imported use.

**Выход и consumer.** A persisted distinct revision/carrier identity with exact source bytes/ref, parent/base, rights disposition and mapped/changed/unmapped span map; unsupported carrier features are preserved/reported as unbound.

**Что можно готовить независимо.** Deterministic alignment and supported carrier parsing can be prepared against the agreed DES-06 interface after E02 source rebind. Rights and exact carrier remain actual input conditions; no kind=input status appoints a supplier.

**Где результат соединяется с другими.** Pass the resolved carrier map to semantic-patch-routing; fresh readers can identify historical parent versus derivative without inheriting parent verification from matching titles/hashes.

**Positive.** An offline imported carrier preserves its source edition or exposes exact changed semantics; dropped caveats remain visible as changed/unbound derivative content.

**Distinguishing negative.** Stale downloaded copy, stripped IDs, renamed target, injected macros/external relationships, unsupported tracked changes or changed assertion cannot inherit prior status or execute imported content.

**Matched removal.** Keep matching text and revision labels but remove exact base/import/rights binding; fresh owner cannot reuse rendition evidence and must treat content as unbound.

**Граница контекста.** This is a truthful carrier input checkpoint, not a new storage-rights service. Carrier integrity does not prove semantic equivalence; exact rights, file family and overlap are resolved only after E02 rebind.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Every card consumes the accepted E02 source/commit and task-scoped source rebind for its own owner readback. The universal acceptance/stage/conditional gate remains the original parent contract; this map adds no second leaf gate or sequencing.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Supplier [DES-06.private-policy-documents](../../cards/DES-06/private-policy-documents.md) | `direct:interface_agreement`: Consumes DES-06’s actual edition/shared schema for import and fresh rendition; DES-06 remains the sole shared schema/render writer.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles разрешаются отдельно, как указано в parent contract. Номера групп и карточек не задают порядок.

## Назначенный нормативный контекст

Основа: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`. Полные selectors и accountable routes — [coverage.json](../../coverage.json), parent `DES-07`. Эти ссылки не требуют чтения всех siblings. Читайте целиком каждый назначенный fragment и необходимые связанные contracts; mixed clause нельзя усечь до удобной части.

- **join** — Carrier security/content integrity clauses (base, macro/relationship, target and changed clause) are checked before any semantic dispatch.
  `task.adversarial`
- **binding** — Actual edited carrier/UI revision and ambiguous mapping choice are inputs to identity/alignment; deterministic alignment remains internal engineering.
  `task.genuine_external_inputs[0]`
- **join** — R17 revision/edition clause 2 belongs to the carrier-identity checkpoint; actual owner status and historical edition remain source-bound.
  `task.r17_extension.adversarial`
- **binding** — Exact offline carrier bytes/base/rights and reimported edits establish the source edition; stripped IDs stay candidate-only. The actual native owner recomputes its own result.
  `task.r19_extension.question_slices[2]`
- **binding** — Imported carrier is a distinct derivative with parent/rights/mapped spans; derivative-only text cannot admit a source event or global stale trigger. The actual native owner recomputes its own result.
  `task.r19_extension.question_slices[3]`
- **binding** — Each source question ID is routed to the card assigned to its matching indexed question_slices clause in this parent; ID coverage preserves lineage and is not semantic proof.
  `task.r19_extension.question_ids[2]`; `task.r19_extension.question_ids[3]`
- **execute** — Offline editable DOCX, stripped IDs, moved tables and annotations are carrier/parser identity inputs; unsupported features remain unbound.
  `solution.implementation_steps[1]`
- **join** — These carrier/security, target, citation and uncertainty mutations are rejected before old status can be inherited.
  `solution.acceptance_discriminators[1]`
- **binding** — Actual carrier or UI revision and human resolution of ambiguous mapping are inputs; no external permission is presumed from the input kind.
  `solution.inputs_to_resolve[0]`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
